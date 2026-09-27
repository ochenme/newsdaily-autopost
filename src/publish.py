"""Publish output/<date>/*.jpg as a carousel to Instagram and Threads.

usage: python src/publish.py <YYYY-MM-DD> <commit-sha> [--now] [--force]
  --now    don't wait for post_time
  --force  allow publishing content whose date is not today (Taipei)
Each platform is recorded in output/<date>/posted.json so re-runs never double-post.
"""
import datetime as dt
import glob
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

from common import CFG, http, load_content, out_dir

TZ = ZoneInfo(CFG["timezone"])


def wait_until_post_time(date: str, now_flag: bool, force: bool):
    now = dt.datetime.now(TZ)
    if date != now.strftime("%Y-%m-%d") and not force:
        sys.exit(f"refusing: content date {date} != today {now:%Y-%m-%d} (use --force)")
    hh, mm = map(int, CFG["post_time"].split(":"))
    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if not now_flag and now < target:
        secs = (target - now).total_seconds()
        if secs > 3 * 3600:
            sys.exit(f"too early to wait ({secs/3600:.1f}h); refusing")
        print(f"waiting {secs:.0f}s until {CFG['post_time']} {CFG['timezone']}")
        time.sleep(secs)


def _ok(r, what):
    if r.status_code != 200:
        raise RuntimeError(f"{what} failed HTTP {r.status_code}: {r.text[:500]}")
    return r.json()


def _poll(base, cid, token, field, done, err_vals, what, tries=30):
    for _ in range(tries):
        st = _ok(http("GET", f"{base}/{cid}", params={"fields": field, "access_token": token}), f"{what} status")
        v = st.get(field)
        if v == done:
            return
        if v in err_vals:
            raise RuntimeError(f"{what} container {cid} status {v}: {st}")
        time.sleep(5)
    raise RuntimeError(f"{what} container {cid} not ready after {tries*5}s")


def post_instagram(urls, caption):
    token = os.environ["IG_ACCESS_TOKEN"]
    base = f"https://graph.instagram.com/{CFG['ig_api_version']}"
    me = _ok(http("GET", f"{base}/me", params={"fields": "user_id,username", "access_token": token}), "IG me")
    uid = me.get("user_id") or me["id"]
    print(f"IG account: @{me.get('username')}")
    kids = []
    for u in urls:
        j = _ok(http("POST", f"{base}/{uid}/media",
                     params={"image_url": u, "is_carousel_item": "true", "access_token": token}), "IG item")
        kids.append(j["id"])
    for k in kids:
        _poll(base, k, token, "status_code", "FINISHED", {"ERROR", "EXPIRED"}, "IG item")
    car = _ok(http("POST", f"{base}/{uid}/media",
                   params={"media_type": "CAROUSEL", "children": ",".join(kids),
                           "caption": caption, "access_token": token}), "IG carousel")["id"]
    _poll(base, car, token, "status_code", "FINISHED", {"ERROR", "EXPIRED"}, "IG carousel")
    pub = _ok(http("POST", f"{base}/{uid}/media_publish",
                   params={"creation_id": car, "access_token": token}), "IG publish")
    return pub["id"]


def post_threads(urls, text):
    token = os.environ["THREADS_ACCESS_TOKEN"]
    base = f"https://graph.threads.net/{CFG['threads_api_version']}"
    me = _ok(http("GET", f"{base}/me", params={"fields": "id,username", "access_token": token}), "Threads me")
    uid = me["id"]
    print(f"Threads account: @{me.get('username')}")
    kids = []
    for u in urls:
        j = _ok(http("POST", f"{base}/{uid}/threads",
                     params={"media_type": "IMAGE", "image_url": u, "is_carousel_item": "true",
                             "access_token": token}), "Threads item")
        kids.append(j["id"])
    for k in kids:
        _poll(base, k, token, "status", "FINISHED", {"ERROR", "EXPIRED"}, "Threads item")
    car = _ok(http("POST", f"{base}/{uid}/threads",
                   params={"media_type": "CAROUSEL", "children": ",".join(kids), "text": text,
                           "access_token": token}), "Threads carousel")["id"]
    _poll(base, car, token, "status", "FINISHED", {"ERROR", "EXPIRED"}, "Threads carousel")
    pub = _ok(http("POST", f"{base}/{uid}/threads_publish",
                   params={"creation_id": car, "access_token": token}), "Threads publish")
    return pub["id"]


def main():
    date, sha = sys.argv[1], sys.argv[2]
    c = load_content(date)
    od = out_dir(date)
    imgs = sorted(glob.glob(os.path.join(od, "[0-9][0-9].jpg")))
    if len(imgs) != len(c["cards"]):
        sys.exit(f"expected {len(c['cards'])} images, found {len(imgs)}")
    urls = [f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/{sha}/output/{date}/{os.path.basename(p)}"
            for p in imgs]
    for u in urls:  # make sure the public URLs actually serve a JPEG before handing them to Meta
        r = http("GET", u)
        if r.status_code != 200 or not r.content[:3] == b"\xff\xd8\xff":
            sys.exit(f"image URL not publicly readable: {u} ({r.status_code})")

    posted_path = os.path.join(od, "posted.json")
    posted = json.load(open(posted_path)) if os.path.exists(posted_path) else {}
    wait_until_post_time(date, "--now" in sys.argv, "--force" in sys.argv)

    failures = []
    for name, fn, limit in (("instagram", post_instagram, CFG["ig_max_chars"]),
                            ("threads", post_threads, CFG["threads_max_chars"])):
        if posted.get(name):
            print(f"{name}: already posted ({posted[name]}), skipping")
            continue
        try:
            pid = fn(urls, c["caption"][:limit])
            posted[name] = {"id": pid, "at": dt.datetime.now(TZ).isoformat(timespec="seconds")}
            print(f"{name}: PUBLISHED id={pid}")
        except Exception as e:  # keep going so one platform failing doesn't block the other
            failures.append(f"{name}: {e}")
            print(f"{name}: FAILED {e}")
        json.dump(posted, open(posted_path, "w"), indent=1)
    if failures:
        sys.exit("PUBLISH FAILURES:\n" + "\n".join(failures))


if __name__ == "__main__":
    main()
