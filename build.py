#!/usr/bin/env python3
"""Turn data/<repo>.json into a single self-contained site/index.html.

Each PR and discussion is reduced to a few timestamps and flags; the page does
the aggregation so the time-window filter can recompute everything.
"""

import json
from datetime import datetime
from pathlib import Path

from config import EXTRA_BOTS, EXTRA_MAINTAINERS, OWNER, REPOS

ROOT = Path(__file__).parent
TEAM_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}


def ts(value):
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()) if value else None


def login(actor):
    return (actor or {}).get("login")


def is_bot(actor):
    if not actor:
        return True  # deleted accounts ("ghost") carry no signal either way
    name = actor["login"]
    return actor["__typename"] == "Bot" or name.endswith("[bot]") or name in EXTRA_BOTS


def first_human(events, author):
    """Earliest timestamp among (actor, time) pairs from a human other than the author."""
    times = [t for actor, t in events if t and not is_bot(actor) and login(actor) != author]
    return min(times) if times else None


def kind(labels):
    if "new task" in labels:
        return "new"
    if "task fix" in labels:
        return "fix"
    return "other"


def load():
    raw = {r["name"]: json.loads((ROOT / "data" / f"{r['name']}.json").read_text()) for r in REPOS}

    # Maintainers are pooled across repos: someone with merge rights in one
    # repo is part of the sponsoring team everywhere.
    team = set(EXTRA_MAINTAINERS)
    for data in raw.values():
        for pr in data["pulls"]:
            if pr["mergedBy"] and not is_bot(pr["mergedBy"] | {"__typename": "User"}):
                team.add(pr["mergedBy"]["login"])
            if pr["authorAssociation"] in TEAM_ASSOCIATIONS and not is_bot(pr["author"]):
                team.add(pr["author"]["login"])

    pulls, discussions = [], []
    for index, repo in enumerate(REPOS):
        data = raw[repo["name"]]
        for pr in data["pulls"]:
            author = login(pr["author"])
            if is_bot(pr["author"]):
                continue
            labels = {label["name"] for label in pr["labels"]["nodes"]}
            timeline = pr["timelineItems"]["nodes"]
            ready = [ts(e["createdAt"]) for e in timeline if e["__typename"] == "ReadyForReviewEvent"]
            comments = [(c["author"], ts(c["createdAt"])) for c in pr["comments"]["nodes"]]
            reviews = [
                (r["author"], ts(r["submittedAt"]))
                for r in pr["reviews"]["nodes"]
                if r["state"] != "PENDING"
            ]
            state = pr["state"].lower()
            pulls.append(
                {
                    "r": index,
                    "n": pr["number"],
                    # Titles are only shown for open PRs; dropping the rest keeps the page small.
                    "t": pr["title"] if state == "open" else None,
                    "a": author,
                    "m": author in team,
                    "k": kind(labels),
                    "s": state,
                    "c": ts(pr["createdAt"]),
                    # Start review clocks when the PR left draft, if it ever did.
                    "rd": None if pr["isDraft"] else max(ready, default=ts(pr["createdAt"])),
                    "e": ts(pr["mergedAt"] or pr["closedAt"]),
                    "rv": first_human(reviews, author),
                    # A first reply is a comment or review from a human other
                    # than the author. Closing or merging silently doesn't count.
                    "fr": first_human(comments + reviews, author),
                }
            )
        for d in data["discussions"]:
            author = login(d["author"])
            replies = []
            for c in d["comments"]["nodes"]:
                replies.append((c["author"], ts(c["createdAt"])))
                replies += [(r["author"], ts(r["createdAt"])) for r in c["replies"]["nodes"]]
            labels = {label["name"] for label in d["labels"]["nodes"]}
            decision = (
                "approved" if any("approved" in l for l in labels)
                else "declined" if any("declined" in l for l in labels)
                else None
            )
            discussions.append(
                {
                    "r": index,
                    "n": d["number"],
                    "cat": d["category"]["name"],
                    "c": ts(d["createdAt"]),
                    "fr": first_human(replies, author),
                    "ans": ts(d["answerChosenAt"]),
                    "dec": decision,
                }
            )

    fetched = min(ts(data["fetched_at"]) for data in raw.values())
    return {
        "owner": OWNER,
        "repos": [{"name": r["name"], "label": r["label"]} for r in REPOS],
        "fetched": fetched,
        "maintainers": sorted(team),
        "pulls": pulls,
        "discussions": discussions,
    }


def main():
    payload = json.dumps(load(), separators=(",", ":")).replace("</", "<\\/")
    html = (ROOT / "template.html").read_text().replace("/*DATA*/null", payload)
    (ROOT / "site").mkdir(exist_ok=True)
    (ROOT / "site" / "index.html").write_text(html)
    print(f"wrote {ROOT / 'site' / 'index.html'}")


if __name__ == "__main__":
    main()
