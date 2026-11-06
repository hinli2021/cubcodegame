#!/usr/bin/env python3
"""守護者密碼: 27 signs (A–Z + blank), team decoder cards, square sign cards to collect, sign tokens.

Answers:  紅隊 FOUR · 藍隊 FIVE · 綠隊 NINE · 黃隊 ONE_  (each card = one letter)  →  4 5 9 1
Sign shapes: Lucide icons (ISC licence) restyled as hand-inked marks.
Run:  python3 build_code.py
"""
import os, io, math
import numpy as np, cv2, cairosvg
from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageFilter
import build as B
import build_teams as T

ICONS = f'{B.ASSETS}/icons'
OUT = f'{B.BASE}/code'
CINZEL = f'{B.FD}/Cinzel-VF.ttf'
NUMS = '一二三四'

# letter -> (lucide icon, Chinese name).  No sign's English name starts with its own letter.
CODE = [
    ('A', 'tent', '帳篷'), ('B', 'star', '星星'), ('C', 'key-round', '鑰匙'), ('D', 'flame', '火焰'),
    ('E', 'anchor', '船錨'), ('F', 'moon', '月亮'), ('G', 'bell', '鈴鐺'), ('H', 'fish', '魚'),
    ('I', 'shield', '盾牌'), ('J', 'crown', '皇冠'), ('K', 'leaf', '葉子'), ('L', 'sailboat', '帆船'),
    ('M', 'snowflake', '雪花'), ('N', 'sun', '太陽'), ('O', 'bird', '小鳥'), ('P', 'hourglass', '沙漏'),
    ('Q', 'eye', '眼睛'), ('R', 'cloud', '雲朵'), ('S', 'gem', '寶石'), ('T', 'mountain', '高山'),
    ('U', 'paw-print', '爪印'), ('V', 'telescope', '望遠鏡'), ('W', 'tree-pine', '松樹'), ('X', 'zap', '閃電'),
    ('Y', 'shell', '貝殼'), ('Z', 'turtle', '烏龜'), ('_', 'ghost', '幽靈'),
]
ICON_OF = {L: icon for L, icon, zh in CODE}
TEAM_WORDS = {'red': 'FOUR', 'blue': 'FIVE', 'green': 'NINE', 'yellow': 'ONE_'}   # one number per team
DIGIT = {'FOUR': 4, 'FIVE': 5, 'NINE': 9, 'ONE_': 1}

def ensure_icons():
    import urllib.request
    os.makedirs(ICONS, exist_ok=True)
    for L, icon, zh in CODE:
        p = f'{ICONS}/{icon}.svg'
        if not os.path.exists(p):
            urllib.request.urlretrieve(f'https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/{icon}.svg', p)

def cinzel(size, weight='Bold'):
    f = ImageFont.truetype(CINZEL, size)
    f.set_variation_by_name(weight)
    return f

def label_of(L):
    return '空格' if L == '_' else L

# ---------------------------------------------------------------- signs
def sign_mask(icon, size, stroke=2.35, rough=True, seed=0):
    """render a Lucide icon as an 'inked' alpha mask (L image, size×size)."""
    svg = open(f'{ICONS}/{icon}.svg').read()
    svg = svg.replace('currentColor', '#000').replace('stroke-width="2"', f'stroke-width="{stroke}"')
    S = 2
    png = cairosvg.svg2png(bytestring=svg.encode(), output_width=size * S, output_height=size * S)
    a = np.asarray(Image.open(io.BytesIO(png)).convert('RGBA'))[..., 3].astype(np.float32) / 255
    if rough:                                       # slightly irregular, hand-inked edges
        rng = np.random.default_rng(seed)
        n = cv2.GaussianBlur(rng.normal(0, 1, a.shape).astype(np.float32), (0, 0), 1.6 * S)
        n /= np.abs(n).max() + 1e-6
        a = cv2.GaussianBlur(a, (0, 0), 0.9 * S)
        a = np.clip((a + 0.22 * n - 0.5) * 3.2 + 0.5, 0, 1)
    return Image.fromarray((a * 255).astype(np.uint8)).resize((size, size), Image.LANCZOS)

def ink_paste(canvas, mask, xy, color):
    """multiply-blend coloured ink through mask (ink soaking into parchment)."""
    x, y = int(round(xy[0])), int(round(xy[1]))
    box = (x, y, x + mask.width, y + mask.height)
    region = canvas.crop(box)
    region.paste(ImageChops.multiply(region, Image.new('RGB', mask.size, color)), (0, 0), mask)
    canvas.paste(region, box[:2])

def mount(card, bgm, t, seed):
    """put a parchment card (any size) on the team-coloured board."""
    h, w = bgm.shape
    W, H = w + 2 * T.BAND, h + 2 * T.BAND
    board = T.coloured_board((W, H), t['band'], seed=seed)
    alpha = np.zeros((H, W), np.float32)
    alpha[T.BAND:T.BAND + h, T.BAND:T.BAND + w] = 1 - bgm
    shadow = cv2.GaussianBlur(np.roll(np.roll(alpha, 9, axis=0), 5, axis=1), (0, 0), 10)
    board *= (1 - 0.45 * shadow)[..., None]
    big = np.zeros((H, W, 3), np.float32)
    big[T.BAND:T.BAND + h, T.BAND:T.BAND + w] = np.asarray(card).astype(np.float32)
    out = board * (1 - alpha[..., None]) + big * alpha[..., None]
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))

def header(d, cx, y, t, what):
    hw = T.runs_tracked(d, cx, y, [('守護者的失落寶藏 · ', B.F(B.KAI_B, 42), B.INK2),
                                  (f"{t['name']}{what}", B.F(B.KAI_B, 46), t['dark'])], track=0.12)
    for sx in (-1, 1):
        B.star4(d, cx + sx * (hw / 2 + 34), y - 15, 13, 4, t['dark'])

def ribbon_title(card, paper, t, cx, band_cy, band_w, band_h, title, size, seal_idx, seal_R=112):
    rib, (bx, by) = T.team_ribbon(band_w, band_h, t)
    rx, ry = cx - band_w / 2 - bx, band_cy - band_h / 2 - by
    B.drop_shadow(card, rib.getchannel('A'), (rx, ry), offset=(0, 12), blur=12, strength=0.5)
    T.comp_tinted(card, paper, rib, (rx, ry))
    tf = B.F(B.KAI_B, size)
    if t['key'] != 'yellow':
        sh = Image.new('L', card.size, 0)
        B.text_tracked(ImageDraw.Draw(sh), cx + 3, band_cy + 0.36 * size + 4, title, tf, 200, track=0.08)
        B.drop_shadow(card, sh, (0, 0), offset=(0, 0), blur=3, strength=0.6, color=(30, 10, 4))
    B.text_tracked(ImageDraw.Draw(card), cx, band_cy + 0.36 * size, title, tf, t['on'], track=0.08)
    seal = T.wax_seal(seal_R, t['seal'], t['ch'], seed=seal_idx)
    sxy = (cx - band_w / 2 - 118 - seal.width / 2, band_cy + 10 - seal.height / 2)
    B.drop_shadow(card, seal.getchannel('A'), sxy, offset=(6, 12), blur=10, strength=0.55, color=(40, 25, 15))
    B.comp_normal(card, seal, sxy)

def tag_title(card, paper, d, t, cx, y, label, tag_h=72, reach=470):
    lf = B.F(B.KAI_B, 46)
    lw = B.text_tracked(ImageDraw.Draw(Image.new('L', (10, 10))), 0, 0, label, lf, 0, track=0.12)
    tag_w = int(lw + 64)
    for sx in (-1, 1):
        B.taper(d, cx + sx * (tag_w / 2 + 26), cx + sx * reach, y + tag_h / 2, 5, t['dark'])
        B.star4(d, cx + sx * (reach + 18), y + tag_h / 2, 10, 3, t['dark'])
    return lambda c: (T.comp_tinted(c, paper, T.team_tag(tag_w, tag_h, t), (cx - (tag_w + 8) / 2, y - 4)),
                      B.text_tracked(ImageDraw.Draw(c), cx, y + tag_h / 2 + 0.36 * 46, label, lf, t['on'], track=0.12))

def arrow(d, ax, ay, col, L=30):
    d.line([(ax - L / 2, ay), (ax + L / 2 - 6, ay)], fill=col, width=5)
    d.polygon([(ax + L / 2 + 4, ay), (ax + L / 2 - 10, ay - 11), (ax + L / 2 - 10, ay + 11)], fill=col)

# ---------------------------------------------------------------- decoder / hint card (portrait)
def make_hint_card(t, frame, bgm, inner, idx):
    card = T.tint_lines(frame, inner, t['dark'])
    paper = card.copy()
    cx = B.CARD_W // 2
    ink = Image.new('RGB', card.size, (255, 255, 255))
    d = ImageDraw.Draw(ink)
    header(d, cx, 290, t, '解碼卡')
    B.text_tracked(d, cx, 606, '把找到的符號對照下表，翻譯成英文字母！', B.F(B.KAI_B, 48), B.BROWN, track=0.04)

    # 27 signs in a brick pattern: rows of 5 / 4 / 5 / 4 / 5 / 4 (hint table only, no record section)
    row_sizes = [5, 4, 5, 4, 5, 4]
    cw, chh, gx, gy, gy0, ss = 226, 248, 26, 14, 652, 150
    lf = cinzel(60)
    capH = -lf.getbbox('H', anchor='ls')[1]
    band_c = (176 + chh) / 2 - 3                      # visual centre of the letter band
    assert sum(row_sizes) == len(CODE)
    cells, i = [], 0
    for r, nin in enumerate(row_sizes):
        y = gy0 + r * (chh + gy)
        for col in range(nin):
            L, icon, zh = CODE[i]
            x = cx - (nin * cw + (nin - 1) * gx) / 2 + col * (cw + gx)
            cells.append((x, y, L, icon))
            d.rounded_rectangle([x, y, x + cw, y + chh], radius=24, fill=(244, 234, 212), outline=t['dark'], width=4)
            d.line([(x + 22, y + 176), (x + cw - 22, y + 176)], fill=(200, 176, 140), width=3)
            if L == '_':
                d.text((x + cw / 2, y + band_c + 2), '空格', font=B.F(B.KAI_B, 46), fill=t['dark'], anchor='mm')
            else:
                d.text((x + cw / 2, y + band_c + capH / 2), L, font=lf, fill=t['dark'], anchor='ms')
            i += 1
    card = ImageChops.multiply(card, ink)
    for i, (x, y, L, icon) in enumerate(cells):
        m = sign_mask(icon, ss, seed=i)
        ink_paste(card, m, (x + cw / 2 - ss / 2, y + 14), B.INK)
    ribbon_title(card, paper, t, cx, 446, 860, 132, '密碼翻譯提示', 78, idx + 11)
    return mount(card, bgm, t, seed=100 + idx)

# ---------------------------------------------------------------- square frame
def prep_square():
    small = Image.open(f'{B.ASSETS}/card_frame_square.png').convert('RGB')
    a = np.asarray(small).copy()
    h, w = a.shape[:2]
    mask = np.zeros((h + 2, w + 2), np.uint8)
    flags = 4 | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)
    for sx, sy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2)]:
        if mask[sy + 1, sx + 1] == 0:
            cv2.floodFill(a, mask, (sx, sy), (0, 0, 0), (18,) * 3, (18,) * 3, flags)
    bg = mask[1:-1, 1:-1].astype(np.float32) / 255
    bg = cv2.GaussianBlur(cv2.dilate(bg, np.ones((3, 3), np.uint8)), (0, 0), 0.9)
    S = 2 * w
    big = small.resize((S, S), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=2, percent=50, threshold=2))
    bgm = cv2.resize(bg, (S, S), interpolation=cv2.INTER_LINEAR)
    inner = cv2.erode((bgm < 0.02).astype(np.uint8), np.ones((37, 37), np.uint8))
    inner = cv2.GaussianBlur(inner.astype(np.float32), (0, 0), 6)
    return big, bgm, inner

def jigsaw_path(p0, p1, knobs, size=36):
    """straight segment p0→p1 with classic puzzle tabs at fractions `knobs` [(f, side)]."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    nx, ny = -uy, ux
    neck, R, h = 0.35 * size, 0.62 * size, 0.95 * size
    beta = math.acos(neck / R)
    P = lambda a, b: (x0 + ux * a + nx * b, y0 + uy * a + ny * b)
    pts = [(x0, y0)]
    for f, s in sorted(knobs):
        c = f * L
        pts.append(P(c - neck, 0))
        for phi in np.linspace(math.pi + beta, -beta, 48):
            pts.append(P(c + R * math.cos(phi), s * (h + R * math.sin(phi))))
        pts.append(P(c + neck, 0))
    pts.append((x1, y1))
    return pts

def dashed_poly(d, pts, col, w, dash=20, gap=12):
    acc, on = 0.0, True
    for (xa, ya), (xb, yb) in zip(pts[:-1], pts[1:]):
        seg = math.hypot(xb - xa, yb - ya)
        t = 0.0
        while t < seg:
            lim = (dash if on else gap) - acc
            step = min(lim, seg - t)
            if on:
                d.line([(xa + (xb - xa) * t / seg, ya + (yb - ya) * t / seg),
                        (xa + (xb - xa) * (t + step) / seg, ya + (yb - ya) * (t + step) / seg)], fill=col, width=w)
            t += step
            acc += step
            if acc >= (dash if on else gap) - 1e-6:
                acc, on = 0.0, not on

def make_square_card(t, k, L, frame, bgm, inner, idx):
    S = frame.width
    card = T.tint_lines(frame, inner, t['dark'])
    paper = card.copy()
    cx = S // 2
    mcy, r_img = 948, 350
    ink = Image.new('RGB', card.size, (255, 255, 255))
    d = ImageDraw.Draw(ink)
    header(d, cx, 290, t, '符號卡')
    B.text_tracked(d, cx, 1430, '對照解碼卡 · 把符號翻譯成字母', B.F(B.KAI_B, 42), B.INK2, track=0.04)
    card = ImageChops.multiply(card, ink)
    disc = Image.new('L', (2 * (r_img + 40), 2 * (r_img + 40)), 0)
    ImageDraw.Draw(disc).ellipse([0, 0, disc.width - 1, disc.height - 1], fill=255)
    B.drop_shadow(card, disc, (cx - disc.width / 2, mcy - disc.height / 2), offset=(6, 14), blur=18, strength=0.4)
    # light parchment medallion face with a soft recessed edge (covers the shadow inside)
    face = paper.crop((cx - r_img, mcy - r_img, cx + r_img, mcy + r_img))
    face = np.asarray(Image.blend(face, Image.new('RGB', face.size, (252, 246, 232)), 0.38)).astype(np.float32)
    yy, xx = np.mgrid[0:2 * r_img, 0:2 * r_img].astype(np.float32)
    dxy, dyy = xx - r_img, yy - r_img
    dist = np.hypot(dxy, dyy)
    edge = np.clip((dist - (r_img - 46)) / 46, 0, 1)
    tl = np.clip(0.55 + 0.45 * (-0.6 * dxy - 0.8 * dyy) / r_img, 0, 1)
    face *= (1 - 0.16 * edge * tl)[..., None]
    fm = Image.new('L', (8 * r_img, 8 * r_img), 0)
    ImageDraw.Draw(fm).ellipse([0, 0, 8 * r_img - 1, 8 * r_img - 1], fill=255)
    card.paste(Image.fromarray(face.clip(0, 255).astype(np.uint8)), (cx - r_img, mcy - r_img),
               fm.resize((2 * r_img, 2 * r_img), Image.LANCZOS))
    m = sign_mask(ICON_OF[L], 470, stroke=2.2, seed=idx)
    ink_paste(card, m, (cx - 235, mcy - 235), B.INK)
    rp = T.ring_patch(r_img + 2, r_img - 16, t['ribbon'])
    T.comp_tinted(card, paper, rp, (cx - rp.width / 2, mcy - rp.height / 2))
    ring = B.rope_ring(r_img, r_img + 44)
    B.comp_normal(card, ring, (cx - ring.width / 2, mcy - ring.height / 2))
    ribbon_title(card, paper, t, cx, 428, 600, 124, '神秘符號', 76, idx + 31, seal_R=100)
    out = mount(card, bgm, t, seed=200 + idx)
    if k == 3:                                         # 符號四 → 4 jigsaw fragments
        dd = ImageDraw.Draw(out)
        o, W = T.BAND, out.width
        vpath = jigsaw_path((cx + o, 0), (cx + o, W), [((660 + o) / W, 1), ((1232 + o) / W, -1)], size=58)
        hpath = jigsaw_path((0, mcy + o), (W, mcy + o), [(0.25, -1), (0.75, 1)], size=58)
        for p in (vpath, hpath):
            dd.line(p, fill=(255, 255, 255), width=9, joint='curve')
            dashed_poly(dd, p, (70, 50, 35), 4)
    return out

# ---------------------------------------------------------------- sign tokens (spares)
def make_token(icon, t, size, paper_src, seed):
    board = T.coloured_board((size, size), t['band'], seed=seed)
    D = int(size * 0.80)
    o = (size - D) // 2
    dm = Image.new('L', (D * 4, D * 4), 0)
    ImageDraw.Draw(dm).ellipse([0, 0, D * 4 - 1, D * 4 - 1], fill=255)
    dm = dm.resize((D, D), Image.LANCZOS)
    sh = Image.new('L', (size, size), 0)
    sh.paste(dm, (o + 3, o + 6))
    sh = np.asarray(sh.filter(ImageFilter.GaussianBlur(6))).astype(np.float32) / 255
    board *= (1 - 0.45 * sh)[..., None]
    tile = Image.fromarray(board.clip(0, 255).astype(np.uint8))
    rng = np.random.default_rng(seed)
    ox, oy = int(rng.integers(260, 700)), int(rng.integers(500, 1500))
    tile.paste(paper_src.crop((ox, oy, ox + 520, oy + 520)).resize((D, D), Image.LANCZOS), (o, o), dm)
    dr = ImageDraw.Draw(tile)
    rr = D / 2 - 10
    dr.ellipse([size / 2 - rr, size / 2 - rr, size / 2 + rr, size / 2 + rr], outline=t['dark'], width=4)
    sm = sign_mask(icon, int(D * 0.62), seed=seed)
    ink_paste(tile, sm, (size / 2 - sm.width / 2, size / 2 - sm.height / 2 - 2), t['dark'])
    dr.text((size / 2, size - o / 2 - 1), t['ch'], font=B.F(B.KAI_B, int(o * 0.74)),
            fill=t['on'] if t['key'] != 'yellow' else (90, 50, 0), anchor='mm')
    m = Image.new('L', (size * 4, size * 4), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size * 4 - 1, size * 4 - 1], radius=int(size * 0.12 * 4), fill=255)
    out = tile.convert('RGBA')
    out.putalpha(m.resize((size, size), Image.LANCZOS))
    return out

def token_sheet(t, paper_src):
    page = Image.new('RGB', B.A4, (255, 255, 255))
    d = ImageDraw.Draw(page)
    pitch, size, cols = 472, 402, 5
    mx, my = (B.A4[0] - cols * pitch) // 2, 430
    title_col = t['dark']
    d.text((B.A4[0] / 2, 170), f"{t['name']} · 後備符號（共 27 個）", font=B.F(B.KAI_B, 72), fill=title_col, anchor='ms')
    d.text((B.A4[0] / 2, 250), '後備用：需要額外符號時才剪出（沿虛線剪下）。灰色小字只供領袖辨認，剪下後不會留在符號上。',
           font=B.F(B.KAI_R, 36), fill=(120, 110, 100), anchor='ms')
    gray = (170, 170, 170)
    for i, (L, icon, zh) in enumerate(CODE):
        r, c = divmod(i, cols)
        x = mx + c * pitch + (pitch - size) // 2
        y = my + r * pitch + (pitch - size) // 2 + 14
        tok = make_token(icon, t, size, paper_src, seed=i + 7)
        page.paste(tok, (x, y), tok)
        d.text((x + 4, y - 14), f'{label_of(L)}  {zh}', font=B.F(B.KAI_R, 30), fill=(150, 150, 150), anchor='ls')
        for p0, p1 in [((x - 10, y - 8), (x + size + 10, y - 8)), ((x - 10, y + size + 10), (x + size + 10, y + size + 10)),
                       ((x - 10, y - 8), (x - 10, y + size + 10)), ((x + size + 10, y - 8), (x + size + 10, y + size + 10))]:
            B._dashed(d, p0, p1, col=gray, dash=14, gapl=10, wdt=2)
    return page

# ---------------------------------------------------------------- main
if __name__ == '__main__':
    B.check_glyphs()
    ensure_icons()
    os.makedirs(f'{OUT}/signs', exist_ok=True)
    for f in os.listdir(f'{OUT}/signs'):
        os.remove(f'{OUT}/signs/{f}')
    for i, (L, icon, zh) in enumerate(CODE):
        m = sign_mask(icon, 600, seed=i)
        im = Image.new('RGBA', m.size, B.INK + (0,))
        im.putalpha(m)
        im.save(f"{OUT}/signs/{'blank' if L == '_' else L}_{icon}.png")
    neutral = dict(T.TEAMS[0], dark=(110, 80, 50), cut=(255, 255, 255))
    A4L = (B.A4[1], B.A4[0])

    # decoder cards
    frame, bgm, inner = T.prep_frame()
    hints = []
    for ti, t in enumerate(T.TEAMS):
        im = make_hint_card(t, frame, bgm, inner, ti)
        im.save(f"{OUT}/hint_card_{t['key']}.jpg", quality=90, dpi=(300, 300))
        hints.append(im)
    print('decoder cards ok')
    sheet4 = T.team_sheet(hints, neutral, 2, 2, B.A4, 1110, label='四隊解碼卡（每隊 1 張）· 沿虛線剪下')
    bigs = [T.team_sheet(hints[k:k + 2], neutral, 2, 1, A4L, 1530, label='解碼卡（大尺寸）· 沿虛線剪下') for k in (0, 2)]

    # square sign cards (collectables): each team = one number word, each card = one letter
    sq, sbgm, sinner = prep_square()
    os.makedirs(f'{OUT}/square_cards', exist_ok=True)
    for f in os.listdir(f'{OUT}/square_cards'):
        os.remove(f'{OUT}/square_cards/{f}')
    sq_pages = []
    for ti, t in enumerate(T.TEAMS):
        word = TEAM_WORDS[t['key']]
        cards = []
        for k, L in enumerate(word):
            im = make_square_card(t, k, L, sq, sbgm, sinner, ti * 4 + k)
            im.save(f"{OUT}/square_cards/{t['key']}_{k + 1}_{'blank' if L == '_' else L}.jpg", quality=90, dpi=(300, 300))
            cards.append(im)
        page = T.team_sheet(cards, t, 2, 2, B.A4, 1157, label=f"{t['name']}符號卡（共 4 張）· 沿虛線剪下")
        d = ImageDraw.Draw(page)
        yb = (B.A4[1] + 2 * 1157) // 2 + 90
        zh = {row[0]: row[2] for row in CODE}
        where = ['領袖保管', '藏在指定範圍', '藏在房間隱蔽處', '剪成 4 塊拼圖碎片分散收藏']
        line = '藏卡對照：' + '　'.join(f'符號{NUMS[k]} {zh[L]} → {where[k]}' for k, L in enumerate(word))
        fs = 36
        while d.textlength(line, font=B.F(B.KAI_R, fs)) > 2300:
            fs -= 1
        d.text((B.A4[0] / 2, yb), line, font=B.F(B.KAI_R, fs), fill=(110, 100, 90), anchor='ms')
        d.text((B.A4[0] / 2, yb + 60), f"（領袖參考：{t['name']} = {word.replace('_', '＋空格')} → {DIGIT[word]}　·　四隊合併：紅 4　藍 5　綠 9　黃 1）",
               font=B.F(B.KAI_R, 32), fill=(160, 150, 140), anchor='ms')
        sq_pages.append(page)
        print('square cards', t['name'], word)

    # spare tokens
    toks = [token_sheet(t, frame) for t in T.TEAMS]

    T.save_pdf(f'{B.BASE}/PRINT_code_hint_cards_A4.pdf', [sheet4], (210, 297))
    T.save_pdf(f'{B.BASE}/PRINT_code_hint_cards_BIG_A4_landscape.pdf', bigs, (297, 210))
    T.save_pdf(f'{B.BASE}/PRINT_code_square_sign_cards_A4.pdf', sq_pages, (210, 297))
    T.save_pdf(f'{B.BASE}/PRINT_code_sign_tokens_A4.pdf', toks, (210, 297))
    print('done')
