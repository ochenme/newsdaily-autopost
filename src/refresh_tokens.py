"""Refresh the 60-day IG / Threads long-lived tokens and write them back to repo secrets.

Needs env IG_ACCESS_TOKEN, THREADS_ACCESS_TOKEN, GH_TOKEN (= GH_PAT with Secrets:write), GITHUB_REPOSITORY.
Tokens are never printed.
"""
import os
import subprocess
import sys

from common import http

JOBS = [
    ("IG_ACCESS_TOKEN", "https://graph.instagram.com/refresh_access_token", "ig_refresh_token"),
    ("THREADS_ACCESS_TOKEN", "https://graph.threads.net/refresh_access_token", "th_refresh_token"),
]

fail = []
for name, url, grant in JOBS:
    tok = os.environ.get(name)
    if not tok:
        fail.append(f"{name}: secret missing")
        continue
    r = http("GET", url, params={"grant_type": grant, "access_token": tok})
    if r.status_code != 200 or "access_token" not in r.json():
        fail.append(f"{name}: refresh failed HTTP {r.status_code}: {r.text[:300]}")
        continue
    new = r.json()["access_token"]
    print(f"::add-mask::{new}")
    p = subprocess.run(["gh", "secret", "set", name, "--repo", os.environ["GITHUB_REPOSITORY"]],
                       input=new, text=True, capture_output=True)
    if p.returncode != 0:
        fail.append(f"{name}: gh secret set failed: {p.stderr[:300]}")
    else:
        days = int(r.json().get("expires_in", 0)) // 86400
        print(f"{name}: refreshed, valid ~{days} days")
if fail:
    sys.exit("\n".join(fail))
