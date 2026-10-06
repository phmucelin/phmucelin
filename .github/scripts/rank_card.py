#!/usr/bin/env python3
"""Gera um card de rank (S, A+, A, A-, B+, B, B-, C+, C) com atividade privada.

Usa a mesma formula do github-readme-stats (src/calculateRank.js), mas conta
commits em repositorios privados (restrictedContributionsCount), que o servico
publico nao enxerga. O card mostra so totais, nunca nome de repositorio privado.
"""
import datetime
import json
import os
import sys
import urllib.request
from html import escape

TOKEN = os.environ["GITHUB_TOKEN"]
OUT = sys.argv[1] if len(sys.argv) > 1 else "profile-summary-card-output/tokyonight/5-rank.svg"


def gql(query, variables=None):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(f"GraphQL: {body['errors']}")
    return body["data"]


def collect():
    base = gql(
        """{ viewer { login name createdAt followers { totalCount }
        pullRequests { totalCount }
        openIssues: issues(states: OPEN) { totalCount }
        closedIssues: issues(states: CLOSED) { totalCount }
        contributionsCollection { totalPullRequestReviewContributions } } }"""
    )["viewer"]

    stars, after = 0, None
    while True:
        page = gql(
            """query($after: String) { viewer { repositories(first: 100, ownerAffiliations: OWNER, after: $after) {
            pageInfo { hasNextPage endCursor } nodes { stargazerCount } } } }""",
            {"after": after},
        )["viewer"]["repositories"]
        stars += sum(n["stargazerCount"] for n in page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]

    commits = 0
    for year in range(int(base["createdAt"][:4]), datetime.date.today().year + 1):
        c = gql(
            """query($from: DateTime!, $to: DateTime!) { viewer { contributionsCollection(from: $from, to: $to) {
            totalCommitContributions restrictedContributionsCount } } }""",
            {"from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"},
        )["viewer"]["contributionsCollection"]
        commits += c["totalCommitContributions"] + c["restrictedContributionsCount"]

    return {
        "name": base["name"] or base["login"],
        "commits": commits,
        "prs": base["pullRequests"]["totalCount"],
        "issues": base["openIssues"]["totalCount"] + base["closedIssues"]["totalCount"],
        "reviews": base["contributionsCollection"]["totalPullRequestReviewContributions"],
        "stars": stars,
        "followers": base["followers"]["totalCount"],
    }


def calculate_rank(s):
    exp_cdf = lambda x: 1 - 2**-x
    log_cdf = lambda x: x / (1 + x)
    rank = 1 - (
        2 * exp_cdf(s["commits"] / 1000)
        + 3 * exp_cdf(s["prs"] / 50)
        + 1 * exp_cdf(s["issues"] / 25)
        + 1 * exp_cdf(s["reviews"] / 2)
        + 4 * log_cdf(s["stars"] / 50)
        + 1 * log_cdf(s["followers"] / 10)
    ) / 12
    pct = rank * 100
    thresholds = [1, 12.5, 25, 37.5, 50, 62.5, 75, 87.5, 100]
    levels = ["S", "A+", "A", "A-", "B+", "B", "B-", "C+", "C"]
    return levels[next(i for i, t in enumerate(thresholds) if pct <= t)], pct


def fmt(n):
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def render(s, level, pct):
    rows = [
        ("Total Commits", s["commits"]),
        ("Total PRs", s["prs"]),
        ("Total Issues", s["issues"]),
        ("Total Reviews", s["reviews"]),
        ("Total Stars", s["stars"]),
        ("Followers", s["followers"]),
    ]
    text = "".join(
        f'<text x="25" y="{68 + i * 21}" class="label">{escape(k)}:</text>'
        f'<text x="165" y="{68 + i * 21}" class="value">{fmt(v)}</text>'
        for i, (k, v) in enumerate(rows)
    )
    circ = 2 * 3.141592653589793 * 40
    filled = circ * max(0.0, min(1.0, (100 - pct) / 100))
    title = escape(f"{s['name']}'s GitHub Rank")
    return f"""<svg width="450" height="195" viewBox="0 0 450 195" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{title}: {escape(level)}">
  <style>
    .title {{ font: 600 18px 'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif; fill: #70a5fd }}
    .label {{ font: 600 14px 'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif; fill: #38bdae }}
    .value {{ font: 600 14px 'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif; fill: #bf91f3 }}
    .level {{ font: 800 24px 'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif; fill: #38bdae }}
  </style>
  <rect x="0.5" y="0.5" rx="4.5" width="449" height="194" fill="#1a1b27"/>
  <text x="25" y="35" class="title">{title}</text>
  {text}
  <g transform="translate(360, 105)">
    <circle r="40" fill="none" stroke="#70a5fd" stroke-width="6" opacity="0.2"/>
    <circle r="40" fill="none" stroke="#70a5fd" stroke-width="6" stroke-linecap="round" stroke-dasharray="{filled:.2f} {circ:.2f}" transform="rotate(-90)"/>
    <text class="level" text-anchor="middle" dominant-baseline="central">{escape(level)}</text>
  </g>
</svg>
"""


if __name__ == "__main__":
    stats = collect()
    level, pct = calculate_rank(stats)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(render(stats, level, pct))
    print(f"{level} ({pct:.1f}%) {stats}")
