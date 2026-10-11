"""
REAL contribution heatmap -> assets/contrib-heatmap.svg

Reads your actual contribution calendar from the GitHub GraphQL API and draws it
with the same animated style as the original chart. Run by .github/workflows/heatmap.yml
(daily); you can also run it locally:

  GH_TOKEN=<token> GH_USER=<username> python scripts/live_heatmap.py

Public contributions are counted with the built-in GITHUB_TOKEN. To include private
contributions, add a classic personal access token (scope: read:user) as the repo secret
GH_STATS_TOKEN and turn on "Private contributions" in your profile's contribution settings.
"""
import datetime as dt
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
import make_heatmap as hm  # noqa: E402

QUERY = """query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{
weeks{contributionDays{date contributionCount weekday}}}}}}"""


def fetch(user, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": user}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "live-heatmap"})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.load(r)
    if res.get("errors") or not res.get("data", {}).get("user"):
        raise SystemExit(f"GitHub API error: {res.get('errors') or 'user not found'}")
    weeks = res["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [(dt.date.fromisoformat(d["date"]), d["contributionCount"], d["weekday"])
            for w in weeks for d in w["contributionDays"]]
    # the chart is drawn in columns of 7 starting on Sunday: pad a partial first week
    first, _, wd = days[0]
    data = [(first - dt.timedelta(days=wd - i), 0) for i in range(wd)]
    return data + [(d, c) for d, c, _ in days]


def main():
    user = os.environ.get("GH_USER") or os.environ["GITHUB_REPOSITORY_OWNER"]
    token = os.environ["GH_TOKEN"]
    data = fetch(user, token)
    st = hm.stats(data)
    out = os.path.join(hm.ROOT, "assets", "contrib-heatmap.svg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write(hm.svg(data, st))
    print("wrote", out, st)


if __name__ == "__main__":
    main()
