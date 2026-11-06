#!/usr/bin/env python3
"""Build the self-contained treasure-lock web app  ->  app/index.html

Everything (images, fonts, icons, code) is inlined, so the single HTML file works offline:
double-click it, or open it in Chrome / Edge / Safari.   The passcode comes from build_code.TEAM_WORDS
(team order 紅 → 藍 → 綠 → 黃), so it always matches the printed cards.

    python3 build_app.py            process art + build app/index.html
"""
import base64
import io
import json
import os
import re
import urllib.request

import numpy as np
from PIL import Image
from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

import build as B
import build_code as C
import build_teams as T

BASE = B.BASE
SRC = f'{BASE}/assets/app2'          # storybook ink-and-watercolour art (matches the printed clue cards)
OUT = f'{BASE}/app'
IMG = f'{OUT}/img'
TPL = f'{OUT}/template.html'
ICON_DIR = f'{BASE}/assets/icons'
LUCIDE = 'https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/{}.svg'
UI_ICONS = ['key-round', 'volume-2', 'volume-x', 'maximize', 'minimize', 'flame', 'lightbulb', 'handshake',
            'award', 'rotate-ccw', 'sparkles', 'chevron-up', 'chevron-down']

# union crop of the two chest renders (pixel-aligned, 1024x1024 on white) and landmarks in raw-image pixels
CROP = (39, 97, 972, 911)
LANDMARKS = {
    'hasp': (632, 481),        # hinge of the front hasp
    'closedTop': (0, 165), 'bottom': (0, 899), 'left': (62, 0), 'right': (960, 0),
    'chainL': (112, 352), 'chainR': (946, 352),   # left / right ends of the lid (chains wrap round the lid)
    'inside': (545, 420),      # centre of the treasure pile (open chest)
    'centerX': (511, 0),       # visual centre of the chest
}
INK = (58, 34, 16)             # dark-brown ink of the illustrations
RED_INK = (128, 42, 24)        # red-brown border lines of the cards
K = 2                          # UI assets are rendered at 2x the stage size (sharp on HiDPI screens)


def passcode():
    return ''.join(str(C.DIGIT[C.TEAM_WORDS[t['key']]]) for t in T.TEAMS)


# ------------------------------------------------------------------ art
def key_white(path, close=2):
    """Cut an ink-outlined drawing out of its plain white backdrop.  The background is the near-white region
    connected to the image border (the dark outline - with small gaps sealed - fences off white areas inside);
    a thin band along the edge gets alpha from darkness and is un-premultiplied (no white fringe)."""
    import cv2
    a = np.asarray(Image.open(path).convert('RGB')).astype(np.float32)
    mn, mx = a.min(-1), a.max(-1)
    L = a @ np.array([0.299, 0.587, 0.114], np.float32)
    ink = cv2.dilate((L < 150).astype(np.uint8), np.ones((2 * close + 1,) * 2, np.uint8))
    cand = ((mn > 226) & (mx - mn < 28) & (ink == 0)).astype(np.uint8)
    n, lab = cv2.connectedComponents(cand, connectivity=4)
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    outside = np.isin(lab, border[border > 0]).astype(np.uint8)
    band = cv2.dilate(outside, np.ones((2 * close + 5,) * 2, np.uint8)) - outside
    soft = np.clip((252 - mn) / 62, 0, 1)
    alpha = np.where(outside > 0, 0.0, np.where(band > 0, soft, 1.0)).astype(np.float32)
    alpha = cv2.GaussianBlur(alpha, (0, 0), 0.55)
    am = np.maximum(alpha, 1e-3)[..., None]
    rgb = np.clip((a - (1 - alpha[..., None]) * 255) / am, 0, 255)
    rgb = np.where(alpha[..., None] > 0.985, a, rgb)
    alpha = np.where(alpha < 0.04, 0, alpha)
    return Image.fromarray(np.dstack([rgb, alpha * 255]).clip(0, 255).astype(np.uint8), 'RGBA')


def chest_meta():
    x0, y0, x1, y1 = CROP
    w, h = x1 - x0, y1 - y0
    m = {'w': w, 'h': h}
    for k, (x, y) in LANDMARKS.items():
        m[k] = [round((x - x0) / w, 4), round((y - y0) / h, 4)]
    return m


def spirit():
    im = key_white(f'{SRC}/wolf_raw.png')               # guardian spirit: a friendly wolf (fox_raw.png = old fox)
    ys, xs = np.where(np.asarray(im.getchannel('A')) > 10)
    pad = 10
    im = im.crop((max(xs.min() - pad, 0), max(ys.min() - pad, 0), min(xs.max() + pad, im.width), min(ys.max() + pad, im.height)))
    return im.resize((640, round(640 * im.height / im.width)), Image.LANCZOS)


# ---- procedural pieces drawn in the cards' ink-and-watercolour style (ss = supersampling factor)
def _noise(h, w, cell, sigma, rng):
    import cv2
    n = rng.normal(0, 1, (h // cell + 3, w // cell + 3)).astype(np.float32)
    n = cv2.GaussianBlur(cv2.resize(n, (w, h), interpolation=cv2.INTER_CUBIC), (0, 0), sigma)
    return n / (np.abs(n).max() + 1e-6)


def _wash(mask, base, rng, scale, top=0.10, bottom=-0.17, pool=0.15):
    """watercolour wash inside mask: blotchy variation, paper grain, pigment pooling at the edge."""
    import cv2
    h, w = mask.shape
    n1, n2 = _noise(h, w, int(70 * scale), 18 * scale, rng), _noise(h, w, int(22 * scale), 5 * scale, rng)
    grain = cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), 0.7 * scale)
    grain /= np.abs(grain).max() + 1e-6
    dist = cv2.distanceTransform((mask > 0.5).astype(np.uint8), cv2.DIST_L2, 5)
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    tex = 1 + 0.075 * n1 + 0.035 * n2 + 0.035 * grain + top * (1 - yy) + bottom * yy - pool * np.exp(-dist / (8 * scale))
    return np.array(base, np.float32)[None, None, :] * tex[..., None]


def _paper(w, h):
    """parchment texture from the printed scroll art (no text in that region)."""
    sc = Image.open(f'{BASE}/assets/scroll_bg.jpg').convert('RGB')
    W, H = sc.size
    return np.asarray(sc.crop((int(W * .22), int(H * .30), int(W * .78), int(H * .62))).resize((w, h), Image.LANCZOS)).astype(np.float32)


def _over(dst, rgb, alpha):
    """alpha-composite a solid colour / image (rgb) with coverage alpha onto float RGBA dst (in place)."""
    a = alpha[..., None]
    out_a = a + dst[..., 3:4] * (1 - a)
    dst[..., :3] = (np.broadcast_to(rgb, dst[..., :3].shape) * a + dst[..., :3] * dst[..., 3:4] * (1 - a)) / np.maximum(out_a, 1e-6)
    dst[..., 3:4] = out_a


def _img(out):
    o = out.copy()
    o[..., 3] *= 255
    return Image.fromarray(o.clip(0, 255).astype(np.uint8), 'RGBA')


def _mask(size, draw):
    from PIL import ImageDraw
    m = Image.new('L', size, 0)
    draw(ImageDraw.Draw(m))
    return np.asarray(m).astype(np.float32) / 255


def compass(R, ink=RED_INK, paper=(241, 226, 190), ss=4):
    """compass rose like the corners of the clue-card frame (parchment disc hides lines passing beneath)."""
    import math
    from PIL import ImageDraw
    size = int(R * 2.7)
    c = size * ss / 2
    im = Image.new('RGBA', (size * ss, size * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = R * ss
    lw = max(1, round(R * ss * 0.05))
    d.ellipse([c - r * 1.02, c - r * 1.02, c + r * 1.02, c + r * 1.02], fill=paper + (255,))
    d.ellipse([c - r, c - r, c + r, c + r], outline=ink + (255,), width=lw)
    d.ellipse([c - r * .8, c - r * .8, c + r * .8, c + r * .8], outline=ink + (255,), width=max(1, lw * 2 // 3))
    for k in range(32):
        t = k / 32 * 2 * math.pi
        r1 = r * (.8 if k % 4 == 0 else .88)
        d.line([(c + r1 * math.cos(t), c + r1 * math.sin(t)), (c + r * math.cos(t), c + r * math.sin(t))], fill=ink + (255,), width=max(1, lw // 2))

    def point(t, length, half):
        tip = (c + length * math.cos(t), c + length * math.sin(t))
        lft = (c + half * math.cos(t - math.pi / 2), c + half * math.sin(t - math.pi / 2))
        rgt = (c + half * math.cos(t + math.pi / 2), c + half * math.sin(t + math.pi / 2))
        d.polygon([(c, c), lft, tip], fill=ink + (255,))
        d.polygon([(c, c), rgt, tip], fill=paper + (255,), outline=ink + (255,), width=max(1, lw * 2 // 3))
    for k in range(4):
        point(math.pi / 4 + k * math.pi / 2, r * .78, r * .13)
    for k in range(4):
        point(-math.pi / 2 + k * math.pi / 2, r * 1.32, r * .2)
    d.ellipse([c - r * .12, c - r * .12, c + r * .12, c + r * .12], fill=paper + (255,), outline=ink + (255,), width=lw)
    return im.resize((size, size), Image.LANCZOS)


BODY = (600, 380)              # lock body in stage px; dial plate inset PLATE px
PLATE = 28


def lock_body(seed=7):
    """big cartoon padlock body: golden watercolour metal, thick ink outline, recessed parchment dial plate
    framed with the clue cards' triple red-brown lines and compass corners."""
    import cv2
    rng = np.random.default_rng(seed)
    ss = 2
    s = K * ss                                        # drawing scale (stage px -> supersampled px)
    W, H = BODY[0] * s, BODY[1] * s
    o = 4 * s                                         # outline sits fully inside the bitmap
    R = 58 * s
    body = _mask((W, H), lambda d: d.rounded_rectangle([o, o, W - o, H - o], radius=R, fill=255))
    out = np.zeros((H, W, 4), np.float32)
    gold = _wash(body, (226, 176, 82), rng, s, top=0.12, bottom=-0.2)
    _over(out, gold, body)
    # cartoon highlight along the upper-left rim, soft shadow along the lower rim
    hi = _mask((W, H), lambda d: (d.line([(o + 13 * s, H - 150 * s), (o + 13 * s, o + R)], fill=255, width=int(7 * s)),
                                  d.arc([o + 13 * s, o + 13 * s, o + 2 * R - 13 * s, o + 2 * R - 13 * s], 180, 270, fill=255, width=int(7 * s)),
                                  d.line([(o + R, o + 13 * s), (300 * s, o + 13 * s)], fill=255, width=int(7 * s))))
    hi = cv2.GaussianBlur(hi, (0, 0), 1.6 * s) * body
    _over(out, np.array([255, 246, 210], np.float32), hi * 0.75)
    # rivets on the rim
    pts = [(x * s, y * s) for x in (15, BODY[0] - 15) for y in (110, 190, 270)]
    rr = 7 * s

    def each(fn):
        def draw(d):
            for cx, cy in pts:
                fn(d, cx, cy)
        return draw
    rv = _mask((W, H), each(lambda d, cx, cy: d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=255)))
    _over(out, np.array([240, 200, 110], np.float32), rv)
    ring = _mask((W, H), each(lambda d, cx, cy: d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=255, width=int(2.2 * s))))
    _over(out, np.array(INK, np.float32), ring)
    dot = _mask((W, H), each(lambda d, cx, cy: d.ellipse([cx - rr * .55, cy - rr * .6, cx - rr * .05, cy - rr * .15], fill=255)))
    _over(out, np.array([255, 248, 220], np.float32), dot * .9)
    # recessed parchment plate
    p0, p1 = PLATE * s, (BODY[0] - PLATE) * s
    q0, q1 = PLATE * s, (BODY[1] - PLATE) * s
    pr = 32 * s
    plate = _mask((W, H), lambda d: d.rounded_rectangle([p0, q0, p1, q1], radius=pr, fill=255))
    paper = np.zeros((H, W, 3), np.float32)
    paper[q0:q1, p0:p1] = _paper(p1 - p0, q1 - q0)
    pd = cv2.distanceTransform((plate > 0.5).astype(np.uint8), cv2.DIST_L2, 5)
    yy = (np.arange(H, dtype=np.float32)[:, None] - q0) / (q1 - q0)
    shade = 1 - 0.30 * np.exp(-pd / (7 * s)) * (0.45 + 0.55 * np.clip(1 - yy, 0, 1)) - 0.05 * np.clip(yy, 0, 1)
    paper = paper * 1.04 * shade[..., None]
    _over(out, paper, plate)
    # triple border lines (like the card frame) and the plate's ink edge
    for ins, wd in ((9, 1.7), (13.5, 1.2), (17.5, 1.7)):
        ln = _mask((W, H), lambda d: d.rounded_rectangle([p0 + ins * s, q0 + ins * s, p1 - ins * s, q1 - ins * s],
                                                         radius=max(4, pr - ins * s), outline=255, width=max(1, round(wd * s))))
        _over(out, np.array(RED_INK, np.float32), ln * 0.9)
    edge = _mask((W, H), lambda d: d.rounded_rectangle([p0, q0, p1, q1], radius=pr, outline=255, width=int(3 * s)))
    _over(out, np.array(INK, np.float32), edge)
    # thick ink outline with a little variation in density
    ol = _mask((W, H), lambda d: d.rounded_rectangle([o, o, W - o, H - o], radius=R, outline=255, width=int(7 * s)))
    ol *= 0.88 + 0.12 * (_noise(H, W, 30 * s, 6 * s, rng) * .5 + .5)
    _over(out, np.array(INK, np.float32), ol)
    im = _img(out).resize((BODY[0] * K, BODY[1] * K), Image.LANCZOS)
    cp = compass(15 * K)
    for x, y in ((PLATE + 15, PLATE + 15), (BODY[0] - PLATE - 15, PLATE + 15), (PLATE + 15, BODY[1] - PLATE - 15),
                 (BODY[0] - PLATE - 15, BODY[1] - PLATE - 15)):
        im.alpha_composite(cp, (x * K - cp.width // 2, y * K - cp.height // 2))
    return im


SHACKLE = dict(ro=164, t=46, vis=190, hidden=96, pad=8)    # outer radius, thickness, visible height, hidden leg


def shackle(seed=11):
    import cv2
    g = SHACKLE
    rng = np.random.default_rng(seed)
    ss = 2
    s = K * ss
    W = (2 * g['ro'] + 2 * g['pad']) * s
    H = (g['pad'] + g['vis'] + g['hidden']) * s
    cx, cy = W / 2, (g['pad'] + g['ro']) * s
    rm = (g['ro'] - g['t'] / 2) * s
    tw = g['t'] * s
    m = _mask((W, H), lambda d: (d.arc([cx - rm - tw / 2, cy - rm - tw / 2, cx + rm + tw / 2, cy + rm + tw / 2], 180, 360, fill=255, width=int(tw)),
                                 d.rectangle([cx - rm - tw / 2, cy, cx - rm + tw / 2, H], fill=255),
                                 d.rectangle([cx + rm - tw / 2, cy, cx + rm + tw / 2, H], fill=255)))
    m = (cv2.GaussianBlur(m, (0, 0), 0.8) > 0.5).astype(np.float32)
    out = np.zeros((H, W, 4), np.float32)
    dist = cv2.distanceTransform((m > 0.5).astype(np.uint8), cv2.DIST_L2, 5) / (tw / 2)
    tube = 0.8 + 0.32 * np.sqrt(np.clip(dist, 0, 1))                     # rounded-bar shading
    gold = _wash(m, (222, 170, 76), rng, s, top=.06, bottom=-.08, pool=0) * tube[..., None]
    _over(out, gold, cv2.GaussianBlur(m, (0, 0), 0.6))
    hl = _mask((W, H), lambda d: (d.arc([cx - rm - tw * .18, cy - rm - tw * .18, cx + rm + tw * .18, cy + rm + tw * .18], 196, 268, fill=255, width=int(7 * s)),
                                  d.line([(cx - rm - tw * .18, cy - 4 * s), (cx - rm - tw * .18, cy + 30 * s)], fill=255, width=int(7 * s))))
    _over(out, np.array([255, 247, 214], np.float32), cv2.GaussianBlur(hl, (0, 0), 1.4 * s) * .8)
    er = cv2.erode(m, np.ones((int(6 * s), int(6 * s)), np.uint8))
    ink = np.clip(m - er, 0, 1)
    ink[int(H - 2 * s):] = 0                                               # open (hidden) leg ends
    _over(out, np.array(INK, np.float32), cv2.GaussianBlur(ink, (0, 0), 0.7))
    return _img(out).resize((W // ss, H // ss), Image.LANCZOS)


def medal_frame():
    """rope-ring medallion (as on the clue cards) with a parchment centre; the icon is drawn by the app."""
    r_out, r_in = 60 * K, 45 * K
    ring = B.rope_ring(r_in, r_out, S=3)
    size = ring.width
    disc = _mask((size * 2, size * 2), lambda d: d.ellipse([size - (r_in + 4) * 2, size - (r_in + 4) * 2, size + (r_in + 4) * 2, size + (r_in + 4) * 2], fill=255))
    disc = np.asarray(Image.fromarray((disc * 255).astype(np.uint8)).resize((size, size), Image.LANCZOS)).astype(np.float32) / 255
    out = np.zeros((size, size, 4), np.float32)
    _over(out, _paper(size, size) * 1.05, disc)
    im = _img(out)
    im.alpha_composite(ring)
    return im


def scroll_cutout():
    """the printed scroll art with its white surround keyed out (border-connected near-white only)"""
    import cv2
    a = np.asarray(Image.open(f'{BASE}/assets/scroll_bg.jpg').convert('RGB'))
    s = a.astype(np.int16)
    mn, mx = s.min(-1), s.max(-1)
    cand = ((mn > 224) & (mx - mn < 24)).astype(np.uint8)
    n, lab = cv2.connectedComponents(cand, connectivity=4)
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    alpha = (~np.isin(lab, border[border > 0])).astype(np.float32)
    alpha = cv2.GaussianBlur(cv2.erode(alpha, np.ones((3, 3), np.uint8)), (0, 0), 1.2)
    im = Image.fromarray(np.dstack([a, (alpha * 255).astype(np.uint8)]), 'RGBA')
    return im.resize((round(im.width * 980 / im.height), 980), Image.LANCZOS)


def process_art():
    os.makedirs(IMG, exist_ok=True)
    for f in os.listdir(IMG):                       # drop images of the previous (night) style
        os.remove(f'{IMG}/{f}')
    key_white(f'{SRC}/chest_closed_raw.png').crop(CROP).save(f'{IMG}/chest_closed.webp', quality=88, method=6)
    key_white(f'{SRC}/chest_open_raw.png').crop(CROP).save(f'{IMG}/chest_open.webp', quality=88, method=6)
    spirit().save(f'{IMG}/spirit.webp', quality=90, method=6)
    Image.open(f'{SRC}/bg_raw.jpg').convert('RGB').save(f'{IMG}/bg.jpg', quality=86, optimize=True, progressive=True)
    scroll_cutout().save(f'{IMG}/scroll.webp', quality=86, method=6)
    sc = Image.open(f'{BASE}/assets/scroll_bg.jpg').convert('RGB')
    W, H = sc.size
    sc.crop((int(W * .27), int(H * .25), int(W * .73), int(H * .58))).resize((620, 600), Image.LANCZOS) \
      .save(f'{IMG}/parch.jpg', quality=80, optimize=True)
    ui_pieces()


def ui_pieces():
    lock_body().save(f'{IMG}/lock_body.webp', quality=90, method=6)
    shackle().save(f'{IMG}/shackle.webp', quality=90, method=6)
    T.wax_seal(52 * K, T.TEAMS[0]['seal'], '封', seed=5, S=2).save(f'{IMG}/seal.webp', quality=90, method=6)
    compass(30 * K).save(f'{IMG}/compass.webp', quality=90, method=6)
    medal_frame().save(f'{IMG}/medal.webp', quality=90, method=6)


def list_img():
    for f in sorted(os.listdir(IMG)):
        print(f'  {f:18s} {os.path.getsize(f"{IMG}/{f}") / 1024:7.0f} KB')


# ------------------------------------------------------------------ icons / fonts
def icon_inner(name):
    p = f'{ICON_DIR}/{name}.svg'
    if not os.path.exists(p):
        os.makedirs(ICON_DIR, exist_ok=True)
        with urllib.request.urlopen(LUCIDE.format(name), timeout=30) as r:
            open(p, 'wb').write(r.read())
    s = open(p, encoding='utf-8').read()
    s = re.sub(r'<!--.*?-->', '', s, flags=re.S)
    return re.sub(r'\s+', ' ', re.search(r'<svg[^>]*>(.*)</svg>', s, re.S).group(1)).strip()


def font_b64(path, text, instance=None):
    f = TTFont(path)
    if instance:
        f = instancer.instantiateVariableFont(f, instance)
    o = subset.Options()
    o.flavor = 'woff2'
    o.layout_features = ['*']
    o.notdef_outline = True
    s = subset.Subsetter(o)
    s.populate(text=text)
    s.subset(f)
    buf = io.BytesIO()
    f.flavor = 'woff2'
    f.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


def data_uri(path):
    mime = {'.jpg': 'image/jpeg', '.webp': 'image/webp', '.png': 'image/png'}[os.path.splitext(path)[1]]
    return f'data:{mime};base64,' + base64.b64encode(open(path, 'rb').read()).decode()


# ------------------------------------------------------------------ html
def hx(c):
    return '#%02x%02x%02x' % tuple(c)


def build_html():
    tpl = open(TPL, encoding='utf-8').read()
    code = passcode()
    icons = {n: icon_inner(n) for n in UI_ICONS}
    signs = [[L, C.label_of(L), icon_inner(icon)] for L, icon, zh in C.CODE]
    text = ''.join(sorted(set(tpl))) + ''.join(chr(c) for c in range(32, 127)) + '「」『』，。！？：；、…—·＋→'
    rep = {
        '{{FONT_KAI_R}}': font_b64(B.KAI_R, text),
        '{{FONT_KAI_B}}': font_b64(B.KAI_B, text),
        '{{FONT_CINZEL}}': font_b64(f'{B.FD}/Cinzel-VF.ttf', '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ', {'wght': 700}),
        '{{IMG_BG}}': data_uri(f'{IMG}/bg.jpg'),
        '{{IMG_CHEST_CLOSED}}': data_uri(f'{IMG}/chest_closed.webp'),
        '{{IMG_CHEST_OPEN}}': data_uri(f'{IMG}/chest_open.webp'),
        '{{IMG_SPIRIT}}': data_uri(f'{IMG}/spirit.webp'),
        '{{IMG_PARCH}}': data_uri(f'{IMG}/parch.jpg'),
        '{{IMG_SCROLL}}': data_uri(f'{IMG}/scroll.webp'),
        '{{IMG_LOCK}}': data_uri(f'{IMG}/lock_body.webp'),
        '{{IMG_SHACKLE}}': data_uri(f'{IMG}/shackle.webp'),
        '{{IMG_SEAL}}': data_uri(f'{IMG}/seal.webp'),
        '{{IMG_COMPASS}}': data_uri(f'{IMG}/compass.webp'),
        '{{IMG_MEDAL}}': data_uri(f'{IMG}/medal.webp'),
        '{{CHEST_META}}': json.dumps(chest_meta()),
        '{{ICONS}}': json.dumps(icons, ensure_ascii=False),
        '{{SIGNS}}': json.dumps(signs, ensure_ascii=False),
        '{{PASSCODE}}': code,
        '{{TEAMS}}': json.dumps([{'k': t['key'], 'n': t['name'], 'c': hx(t['ribbon']), 'd': hx(t['dark']), 'f': hx(t['fold']),
                                  'r': hx(t['rule']), 'o': hx(t['on'])} for t in T.TEAMS], ensure_ascii=False),
    }
    for k, v in rep.items():
        assert k in tpl, k
        tpl = tpl.replace(k, v)
    left = re.findall(r'\{\{[A-Z_]+\}\}', tpl)
    assert not left, left
    open(f'{OUT}/index.html', 'w', encoding='utf-8').write(tpl)
    print(f'app ok  passcode {code}  {os.path.getsize(f"{OUT}/index.html") / 1e6:.2f} MB  {OUT}/index.html')


if __name__ == '__main__':
    process_art()
    list_img()
    if os.path.exists(TPL):
        build_html()
