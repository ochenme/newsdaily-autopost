"""Build step: validate content, fetch Pexels backgrounds, render cards into output/<date>/.

usage: python src/build.py <YYYY-MM-DD> [--offline]
--offline uses a procedural placeholder background (for local validation without network).
"""
import io
import json
import os
import sys

from PIL import Image

from common import CFG, ROOT, http, load_content, out_dir
from render import render, validate_card

USED_PATH = os.path.join(ROOT, "data", "used_photos.json")
GENERIC = ["city night lights", "dark ocean night", "night skyline"]


def validate_content(c: dict) -> None:
    errs = []
    n = len(c.get("cards", []))
    if not c.get("sample") and not 5 <= n <= 8:
        errs.append(f"need 5-8 cards, got {n}")
    for i, card in enumerate(c.get("cards", []), 1):
        errs += [f"card{i}: {e}" for e in validate_card(card)]
    cap = c.get("caption", "")
    if not cap:
        errs.append("missing caption")
    if len(cap) > CFG["threads_max_chars"]:
        errs.append(f"caption {len(cap)} chars > Threads limit {CFG['threads_max_chars']}")
    if errs:
        sys.exit("CONTENT INVALID:\n- " + "\n- ".join(errs))


def pexels_by_id(pid: int) -> tuple[Image.Image, dict]:
    r = http("GET", f"https://api.pexels.com/v1/photos/{pid}", headers={"Authorization": os.environ["PEXELS_API_KEY"]})
    if r.status_code != 200:
        raise RuntimeError(f"Pexels photo {pid} failed {r.status_code}: {r.text[:200]}")
    p = r.json()
    url = f"{p['src']['original']}?auto=compress&cs=tinysrgb&fit=crop&w=1080&h=1350"
    img = Image.open(io.BytesIO(http("GET", url).content))
    return img, {"query": f"id:{pid}", "id": p["id"], "photographer": p["photographer"], "url": p["url"]}


def pexels_photo(queries: list[str], used: set) -> tuple[Image.Image, dict]:
    key = os.environ["PEXELS_API_KEY"]
    for q in queries:
        r = http("GET", "https://api.pexels.com/v1/search",
                 headers={"Authorization": key},
                 params={"query": q, "orientation": "portrait", "size": "large", "per_page": 30})
        if r.status_code != 200:
            raise RuntimeError(f"Pexels search failed {r.status_code}: {r.text[:200]}")
        photos = [p for p in r.json().get("photos", []) if p["id"] not in used]
        if not photos:
            continue
        # Relevance first (Pexels order), then prefer a reasonably dark photo among the top hits,
        # because the template is designed for dark backgrounds.
        def lum(p):
            h = (p.get("avg_color") or "#808080").lstrip("#")
            r_, g_, b_ = (int(h[i:i + 2], 16) for i in (0, 2, 4))
            return 0.2126 * r_ + 0.7152 * g_ + 0.0722 * b_
        top = photos[:8]
        dark = [p for p in top if lum(p) < 110]
        p = dark[0] if dark else min(top, key=lum)
        url = f"{p['src']['original']}?auto=compress&cs=tinysrgb&fit=crop&w=1080&h=1350"
        img = Image.open(io.BytesIO(http("GET", url).content))
        return img, {"query": q, "id": p["id"], "photographer": p["photographer"], "url": p["url"]}
    raise RuntimeError(f"no Pexels result for {queries}")


def main():
    date = sys.argv[1]
    offline = "--offline" in sys.argv
    c = load_content(date)
    validate_content(c)
    # Skip re-rendering if the cards are unchanged and already built (keeps approved images stable)
    import hashlib
    sig = hashlib.sha256(json.dumps(c["cards"], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    sig_path = os.path.join(out_dir(date), "cards.sha256")
    have = all(os.path.exists(os.path.join(out_dir(date), f"{i:02d}.jpg")) for i in range(1, len(c["cards"]) + 1))
    if not offline and have and os.path.exists(sig_path) and open(sig_path).read().strip() == sig:
        print("cards unchanged and already built — skipping render")
        return
    used_list = json.load(open(USED_PATH)) if os.path.exists(USED_PATH) else []
    used = set(used_list)
    # offline = validation only: render into a temp dir so placeholder images never get committed
    od = __import__("tempfile").mkdtemp(prefix="cards-") if offline else out_dir(date)
    os.makedirs(od, exist_ok=True)
    credits = []
    mmdd = date[5:7] + "." + date[8:10]
    for i, card in enumerate(c["cards"], 1):
        if offline:
            from placeholder_bg import night_scene
            bg, meta = night_scene(seed=i), {"query": card["bg_query"], "id": None}
        elif card.get("bg_id"):  # optional: pin an exact Pexels photo
            bg, meta = pexels_by_id(int(card["bg_id"]))
        else:
            bg, meta = pexels_photo([card["bg_query"], *card.get("bg_fallback", []), *GENERIC], used)
            used.add(meta["id"])
            used_list.append(meta["id"])
        render(card, bg, os.path.join(od, f"{i:02d}.jpg"), date=mmdd,
               account=CFG["account_name"], footer=CFG["footer"], category=CFG["category"])
        credits.append(meta)
        print(f"card {i:02d} ok  bg={meta.get('query')} id={meta.get('id')}")
    json.dump(credits, open(os.path.join(od, "credits.json"), "w"), ensure_ascii=False, indent=1)
    if not offline:
        open(sig_path, "w").write(sig)
    if not offline:
        os.makedirs(os.path.dirname(USED_PATH), exist_ok=True)
        json.dump(used_list[-2000:], open(USED_PATH, "w"))  # remember recent photos to avoid repeats
    print(f"built {len(c['cards'])} cards -> {od}")


if __name__ == "__main__":
    main()
