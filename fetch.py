#!/usr/bin/env python3
"""Fetch pull requests and discussions for each repo into data/<repo>.json.

Uses the GitHub GraphQL API through `gh api graphql`, so `gh auth login` is the
only setup. Re-running refetches everything; the repos are small enough.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from config import OWNER, REPOS

DATA = Path(__file__).parent / "data"

ACTOR = "author { login __typename }"

PR_QUERY = f"""
query($owner: String!, $name: String!, $after: String) {{
  repository(owner: $owner, name: $name) {{
    pullRequests(first: 40, after: $after, orderBy: {{field: CREATED_AT, direction: ASC}}) {{
      pageInfo {{ hasNextPage endCursor }}
      nodes {{
        number title state isDraft createdAt mergedAt closedAt
        {ACTOR} authorAssociation
        mergedBy {{ login }}
        labels(first: 20) {{ nodes {{ name }} }}
        comments(first: 30) {{ nodes {{ {ACTOR} createdAt }} }}
        reviews(first: 30) {{ nodes {{ {ACTOR} submittedAt state }} }}
        timelineItems(first: 10, itemTypes: [READY_FOR_REVIEW_EVENT, CLOSED_EVENT]) {{
          nodes {{
            __typename
            ... on ReadyForReviewEvent {{ createdAt }}
            ... on ClosedEvent {{ createdAt actor {{ login __typename }} }}
          }}
        }}
      }}
    }}
  }}
}}
"""

DISCUSSION_QUERY = f"""
query($owner: String!, $name: String!, $after: String) {{
  repository(owner: $owner, name: $name) {{
    discussions(first: 50, after: $after, orderBy: {{field: CREATED_AT, direction: ASC}}) {{
      pageInfo {{ hasNextPage endCursor }}
      nodes {{
        number title createdAt closedAt answerChosenAt
        {ACTOR}
        category {{ name }}
        labels(first: 10) {{ nodes {{ name }} }}
        comments(first: 20) {{
          nodes {{
            {ACTOR} createdAt
            replies(first: 10) {{ nodes {{ {ACTOR} createdAt }} }}
          }}
        }}
      }}
    }}
  }}
}}
"""


def graphql(query, **variables):
    args = ["gh", "api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        if value is not None:
            args += ["-F", f"{key}={value}"]
    for attempt in range(5):
        proc = subprocess.run(args, capture_output=True, text=True)
        if proc.returncode == 0:
            return json.loads(proc.stdout)["data"]
        print(f"  retry {attempt + 1}: {proc.stderr.strip()[:200]}", file=sys.stderr)
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(proc.stderr)


def paginate(query, field, name):
    nodes, after = [], None
    while True:
        conn = graphql(query, owner=OWNER, name=name, after=after)["repository"][field]
        nodes += conn["nodes"]
        print(f"  {field}: {len(nodes)}", file=sys.stderr, end="\r")
        if not conn["pageInfo"]["hasNextPage"]:
            print(file=sys.stderr)
            return nodes
        after = conn["pageInfo"]["endCursor"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repos", nargs="*", help="subset of repo names from config.py")
    args = parser.parse_args()

    DATA.mkdir(exist_ok=True)
    for repo in REPOS:
        if args.repos and repo["name"] not in args.repos:
            continue
        print(f"{OWNER}/{repo['name']}", file=sys.stderr)
        out = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "pulls": paginate(PR_QUERY, "pullRequests", repo["name"]),
            "discussions": (
                paginate(DISCUSSION_QUERY, "discussions", repo["name"])
                if repo.get("discussions")
                else []
            ),
        }
        (DATA / f"{repo['name']}.json").write_text(json.dumps(out))


if __name__ == "__main__":
    main()
