# Procedural stand-in photo (no internet here); real runs use Pexels photos.
from PIL import Image, ImageDraw, ImageFilter
import random
def night_scene(seed=1, W=1080, H=1350):
    random.seed(seed)
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    hz = 760
    for y in range(H):
        t = y / hz if y < hz else 1
        c = (int(10 + 30*t**3), int(18 + 30*t**3), int(38 + 40*t**3))
        d.line([(0, y), (W, y)], fill=c)
    # skyline
    x = 0
    lights = []
    while x < W:
        bw = random.randint(30, 90); bh = random.randint(40, 260) if 250 < x < 900 else random.randint(20, 120)
        d.rectangle([x, hz - bh, x + bw, hz], fill=(9, 13, 22))
        for wy in range(hz - bh + 8, hz - 4, 12):
            for wx in range(x + 5, x + bw - 5, 10):
                if random.random() < 0.28: lights.append((wx, wy))
        x += bw + random.randint(0, 8)
    glow = Image.new("RGB", (W, H)); gd = ImageDraw.Draw(glow)
    for (wx, wy) in lights:
        col = random.choice([(255, 196, 120), (255, 214, 160), (200, 220, 255)])
        d.rectangle([wx, wy, wx + 3, wy + 4], fill=col)
        gd.ellipse([wx - 6, wy - 6, wx + 9, wy + 10], fill=tuple(int(c*0.5) for c in col))
        # reflection streak on water
        ry = hz + (hz - wy) * 0.6
        if ry < H: gd.line([(wx, ry), (wx, min(H, ry + random.randint(20, 90)))], fill=tuple(int(c*0.35) for c in col), width=2)
    # water
    for y in range(hz, H):
        t = (y - hz) / (H - hz)
        d.line([(0, y), (W, y)], fill=(int(8+6*(1-t)), int(12+8*(1-t)), int(24+14*(1-t))))
    im = Image.blend(im, Image.eval(Image.composite(im, im, Image.new("L", (W, H), 255)), lambda v: v), 0)
    im = Image.composite(im, im, Image.new("L", (W, H), 255))
    from PIL import ImageChops
    im = ImageChops.add(im, glow.filter(ImageFilter.GaussianBlur(6)))
    # redraw skyline lights crisp above water haze
    noise = Image.effect_noise((W, H), 12).convert("RGB")
    im = Image.blend(im, ImageChops.add(im, noise, scale=6), 0.25)
    return im
