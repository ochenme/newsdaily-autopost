import json
import os
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))


def load_content(date: str) -> dict:
    with open(os.path.join(ROOT, "content", f"{date}.json"), encoding="utf-8") as f:
        c = json.load(f)
    if c.get("date") != date:
        sys.exit(f"content date mismatch: file {date} vs field {c.get('date')}")
    return c


def out_dir(date: str) -> str:
    return os.path.join(ROOT, "output", date)


def http(method: str, url: str, *, retries: int = 3, **kw) -> requests.Response:
    """HTTP with retry on 5xx / network errors. Never logs tokens."""
    last = None
    for i in range(retries):
        try:
            r = requests.request(method, url, timeout=60, **kw)
            if r.status_code < 500:
                return r
            last = f"HTTP {r.status_code}: {r.text[:300]}"
        except requests.RequestException as e:
            last = repr(e)
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"{method} {url.split('?')[0]} failed: {last}")
