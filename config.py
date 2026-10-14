OWNER = "harbor-framework"

REPOS = [
    {"name": "harbor", "label": "Harbor"},
    {"name": "terminal-bench", "label": "Terminal-Bench", "discussions": True},
    {"name": "terminal-bench-science", "label": "TB-Science", "discussions": True},
]

# Logins counted as maintainers even if they never merged a PR. Anyone who has
# merged a PR in any repo, or whose association is OWNER/MEMBER/COLLABORATOR,
# is detected automatically.
EXTRA_MAINTAINERS = set()

# Accounts that post as users but are automation.
EXTRA_BOTS = {
    "github-actions",
    "dependabot",
    "copilot-pull-request-reviewer",
    "codecov-commenter",
    "scaleai-bot",
}
