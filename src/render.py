"""ND 知日報 card renderer.

Fixed 1080x1350 (4:5) template. All positions were measured from the reference card and
must not change between days. Text is placed by the *ink top* of the glyphs so every card
lines up pixel-for-pixel regardless of content.
"""
from __future__ import annotations

import glob
import os

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps, ImageStat

W, H = 1080, 1350

_FONT_CACHE: dict = {}


def _font_file(weight: str) -> str:
    cands = glob.glob(f"/usr/share/fonts/**/NotoSerifCJK-{weight}.ttc", recursive=True)
    if not cands:
        raise FileNotFoundError(f"NotoSerifCJK-{weight}.ttc not found (install fonts-noto-cjk)")
    return cands[0]


def F(weight: str, size: int) -> ImageFont.FreeTypeFont:
    key = (weight, size)
    if key not in _FONT_CACHE:
        # index 3 inside the Noto Serif CJK collection = Traditional Chinese (TC)
        f = ImageFont.truetype(_font_file(weight), size, index=3)
        assert "TC" in f.getname()[0], f.getname()
        _FONT_CACHE[key] = f
    return _FONT_CACHE[key]


# ---------------- template spec (px) — DO NOT CHANGE without Jimmy's approval ----------------
RULE_X0, RULE_X1 = 78, 1002
C_RED = "#E9786B"
C_BODY = "#E0E1E4"
SPEC = {
    "account":  dict(x=79, font=("Bold", 40),    color="#E9EAED", ink_top=85),
    "rule1":    dict(y=134),
    "meta":     dict(x=79, font=("Regular", 26), color="#BDC6D0", ink_top=179),
    "kicker":   dict(x=80, font=("Bold", 33),    color=C_RED,     ink_top=266),
    "headline": dict(x=80, font=("Bold", 62),    color="#ECEDF0", ink_top=322, max_width=920),
    "body":     dict(x=84, font=("Regular", 30), color=C_BODY,    ink_top=525, pitch=52, width=900, max_lines=3),
    # 因應策略 block (optional per card): sits between body and rule2, in the empty photo area
    "strategy": dict(panel_x0=78, panel_x1=1002, panel_top=770, pad_top=32, label="因應策略",
                     label_x=110, label_font=("Bold", 28), text_x=110, text_font=("Regular", 28),
                     text_color="#E6E7EA", gap=22, pitch=48, width=862, max_lines=3, pad_bottom=34),
    "rule2":    dict(y=1154),
    "watch":    dict(label_x=81, items_x=202, font=("Bold", 30), ink_top=1198, max_width=800),
    "footer":   dict(x=80, font=("Regular", 21), color="#BAC0C8", ink_top=1283),
}
NO_LINE_START = "，。、；：！？）」』%％"


def _ink_text(d: ImageDraw.ImageDraw, x: float, ink_top: float, text: str, font, fill):
    ref = d.textbbox((0, 0), "國", font=font)  # consistent line top for CJK + Latin mixes
    d.text((x, ink_top - ref[1]), text, font=font, fill=fill)


def wrap(text: str, font, width: int) -> list[str]:
    d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines, cur = [], ""
    for ch in text:
        if cur and d.textlength(cur + ch, font=font) > width:
            if ch in NO_LINE_START:  # keep punctuation on the previous line
                lines.append(cur + ch)
                cur = ""
                continue
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def validate_card(card: dict) -> list[str]:
    """Return a list of problems (empty = OK)."""
    errs = []
    for k in ("kicker", "headline", "body", "watch", "bg_query"):
        if not card.get(k):
            errs.append(f"missing {k}")
    if errs:
        return errs
    d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    s = SPEC
    if d.textlength(card["headline"], font=F(*s["headline"]["font"])) > s["headline"]["max_width"]:
        errs.append(f"headline too wide: {card['headline']}")
    n = len(wrap(card["body"], F(*s["body"]["font"]), s["body"]["width"]))
    if n > s["body"]["max_lines"]:
        errs.append(f"body {n} lines (max {s['body']['max_lines']}): {card['headline']}")
    if d.textlength("、".join(card["watch"]), font=F(*s["watch"]["font"])) > s["watch"]["max_width"]:
        errs.append(f"watch items too wide: {card['watch']}")
    if card.get("strategy"):
        st = s["strategy"]
        n = len(wrap(card["strategy"], F(*st["text_font"]), st["width"]))
        if n > st["max_lines"]:
            errs.append(f"strategy {n} lines (max {st['max_lines']}): {card['headline']}")
    return errs


def prepare_bg(src) -> Image.Image:
    img = src if isinstance(src, Image.Image) else Image.open(src)
    img = ImageOps.fit(img.convert("RGB"), (W, H), Image.LANCZOS, centering=(0.5, 0.6))
    # Unify the look across very different photos: pull saturation down so every card
    # reads as the same dark-navy family as the reference card.
    img = ImageEnhance.Color(img).enhance(0.55)
    # Legibility overlay: navy tint, darkest behind the text zone (top half), lighter lower-middle
    # so the photo shows, dark again behind the 留意/footer zone.
    over = Image.new("RGBA", (W, H))
    od = ImageDraw.Draw(over)
    for y in range(H):
        t = y / H
        if t < 0.48:
            a = 185
        elif t < 0.62:
            a = int(185 - (t - 0.48) / 0.14 * 85)   # 185 → 100
        elif t < 0.80:
            a = 100
        else:
            a = int(100 + (t - 0.80) / 0.20 * 90)   # 100 → 190
        od.line([(0, y), (W, y)], fill=(8, 14, 26, a))
    return Image.alpha_composite(img.convert("RGBA"), over)


def _draw_strategy(im: Image.Image, text: str, accent: str) -> Image.Image:
    st = SPEC["strategy"]
    tf, lf = F(*st["text_font"]), F(*st["label_font"])
    lines = wrap(text, tf, st["width"])
    label_top = st["panel_top"] + st["pad_top"]
    text_top = label_top + 28 + st["gap"]
    bottom = text_top + (len(lines) - 1) * st["pitch"] + 28 + st["pad_bottom"]
    # translucent dark panel + thin accent bar on the left, so the block reads as a distinct "takeaway"
    over = Image.new("RGBA", im.size)
    od = ImageDraw.Draw(over)
    od.rounded_rectangle([st["panel_x0"], st["panel_top"], st["panel_x1"], bottom], radius=10, fill=(6, 11, 22, 165))
    im = Image.alpha_composite(im, over)
    d = ImageDraw.Draw(im)
    d.rectangle([st["panel_x0"], st["panel_top"] + 10, st["panel_x0"] + 3, bottom - 10], fill=accent)
    _ink_text(d, st["label_x"], label_top, st["label"], lf, accent)
    for i, ln in enumerate(lines):
        _ink_text(d, st["text_x"], text_top + i * st["pitch"], ln, tf, st["text_color"])
    return im


def render(card: dict, bg, out: str, *, date: str, account: str, footer: str, category: str):
    errs = validate_card(card)
    if errs:
        raise ValueError("; ".join(errs))
    im = prepare_bg(bg)
    d = ImageDraw.Draw(im)
    s = SPEC
    # Accent colour adapts to the background: coral red by default, amber if the photo is red-toned
    r_, g_, b_ = ImageStat.Stat(im.convert("RGB").crop((0, 0, W, H))).mean
    accent = "#F2C46D" if (r_ > g_ + 12 and r_ > b_ + 12) else C_RED
    s = {**s, "kicker": {**s["kicker"], "color": accent}}
    _ink_text(d, s["account"]["x"], s["account"]["ink_top"], account, F(*s["account"]["font"]), s["account"]["color"])
    d.rectangle([RULE_X0, s["rule1"]["y"], RULE_X1, s["rule1"]["y"] + 1], fill="#FFFFFF")
    _ink_text(d, s["meta"]["x"], s["meta"]["ink_top"], f"{category}｜{date}", F(*s["meta"]["font"]), s["meta"]["color"])
    _ink_text(d, s["kicker"]["x"], s["kicker"]["ink_top"], card["kicker"], F(*s["kicker"]["font"]), s["kicker"]["color"])
    _ink_text(d, s["headline"]["x"], s["headline"]["ink_top"], card["headline"], F(*s["headline"]["font"]), s["headline"]["color"])
    b = s["body"]
    bf = F(*b["font"])
    for i, ln in enumerate(wrap(card["body"], bf, b["width"])):
        _ink_text(d, b["x"], b["ink_top"] + i * b["pitch"], ln, bf, b["color"])
    if card.get("strategy"):
        im = _draw_strategy(im, card["strategy"], accent)
        d = ImageDraw.Draw(im)
    d.rectangle([RULE_X0, s["rule2"]["y"], RULE_X1, s["rule2"]["y"] + 1], fill="#FFFFFF")
    w = s["watch"]
    wf = F(*w["font"])
    _ink_text(d, w["label_x"], w["ink_top"], "留意", wf, accent)
    bar_x = w["label_x"] + d.textlength("留意", font=wf) + 12
    d.rectangle([bar_x, w["ink_top"] + 1, bar_x + 1, w["ink_top"] + 28], fill=accent)
    _ink_text(d, w["items_x"], w["ink_top"], "、".join(card["watch"]), wf, C_BODY)
    _ink_text(d, s["footer"]["x"], s["footer"]["ink_top"], footer, F(*s["footer"]["font"]), s["footer"]["color"])
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    im.convert("RGB").save(out, "JPEG", quality=92, optimize=True)  # IG API requires JPEG
