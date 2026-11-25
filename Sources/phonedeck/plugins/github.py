#!/usr/bin/env python3
"""Your open GitHub pull requests with CI and review state, plus PRs waiting on your review.

Uses the GitHub CLI (`gh`), signed in with `gh auth login`. Read-only.
"""
import json, shutil, subprocess

OUT = {"type": "github", "id": "github", "name": "GitHub", "color": "#8B949E"}
Q = """query { viewer { pullRequests(states: OPEN, first: 20, orderBy: {field: UPDATED_AT, direction: DESC}) { nodes {
  number title url isDraft updatedAt reviewDecision repository { nameWithOwner }
  commits(last: 1) { nodes { commit { statusCheckRollup { state } } } } } } }
  search(query: "is:pr is:open review-requested:@me archived:false", type: ISSUE, first: 20) { issueCount nodes { ... on PullRequest {
  number title url updatedAt repository { nameWithOwner } } } } }"""


def main():
    if not shutil.which("gh"):
        return {**OUT, "available": False, "setup": "Install the GitHub CLI and run gh auth login."}
    r = subprocess.run(["gh", "api", "graphql", "-f", "query=" + Q], capture_output=True, text=True, timeout=20)
    if r.returncode != 0:
        return {**OUT, "available": True, "error": (r.stderr.strip().splitlines() or ["gh failed"])[-1][:140]}
    d = json.loads(r.stdout).get("data") or {}
    ci = {"SUCCESS": "pass", "FAILURE": "fail", "ERROR": "fail", "PENDING": "running", "EXPECTED": "running"}
    prs = []
    for n in ((d.get("viewer") or {}).get("pullRequests") or {}).get("nodes") or []:
        roll = (((n.get("commits") or {}).get("nodes") or [{}])[0].get("commit") or {}).get("statusCheckRollup") or {}
        prs.append({"repo": n["repository"]["nameWithOwner"], "number": n["number"], "title": n["title"], "url": n["url"],
                    "draft": n.get("isDraft"), "ci": ci.get(roll.get("state"), "none"),
                    "review": {"APPROVED": "approved", "CHANGES_REQUESTED": "changes"}.get(n.get("reviewDecision") or "", "waiting"),
                    "updatedAt": n.get("updatedAt")})
    reviews = [{"repo": n["repository"]["nameWithOwner"], "number": n["number"], "title": n["title"], "url": n["url"], "updatedAt": n.get("updatedAt")}
               for n in (d.get("search") or {}).get("nodes") or [] if n]
    return {**OUT, "available": True, "prs": prs, "reviews": reviews}


print(json.dumps(main()))
