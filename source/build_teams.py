#!/usr/bin/env python3
"""Colour-coded TEAM clue cards: 4 teams × 4 clues = 16 cards.

Re-uses the typesetting engine, content and helpers from build.py.
Run:  python3 build_teams.py
"""
import os, io, math
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageFilter
import build as B

OUT = f'{B.BASE}/team_cards'
SERIF_VF = f'{B.FD}/NotoSerifTC-VF.ttf'
BAND = 48                                   # extra coloured border around the 1696×2528 card

TEAMS = [
    dict(key='red', name='紅隊', ch='紅',
         band=(178, 40, 30), ribbon=(198, 54, 38), tail=(160, 40, 28), fold=(98, 22, 14),
         dark=(132, 26, 16), seal=(180, 36, 26), on=(255, 247, 226), rule=(236, 196, 112), cut=(255, 255, 255)),
    dict(key='blue', name='藍隊', ch='藍',
         band=(30, 84, 170), ribbon=(40, 100, 200), tail=(30, 78, 162), fold=(16, 42, 100),
         dark=(22, 58, 136), seal=(32, 84, 176), on=(255, 247, 226), rule=(236, 206, 130), cut=(255, 255, 255)),
    dict(key='green', name='綠隊', ch='綠',
         band=(34, 124, 62), ribbon=(42, 142, 72), tail=(32, 112, 56), fold=(16, 64, 30),
         dark=(20, 88, 40), seal=(34, 124, 60), on=(255, 247, 226), rule=(236, 206, 130), cut=(255, 255, 255)),
    dict(key='yellow', name='黃隊', ch='黃',
         band=(242, 188, 26), ribbon=(250, 204, 44), tail=(228, 170, 28), fold=(160, 108, 8),
         dark=(128, 82, 0), seal=(238, 178, 20), on=(66, 36, 2), rule=(140, 92, 10), cut=(90, 60, 10)),
]

# ---------------------------------------------------------------- frame preparation
def prep_frame():
    small = Image.open(f'{B.ASSETS}/card_frame_clean.png').convert('RGB')
    a = np.asarray(small).copy()
    h, w = a.shape[:2]
    mask = np.zeros((h + 2, w + 2), np.uint8)
    flags = 4 | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)
    for sx, sy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2)]:
        if mask[sy + 1, sx + 1] == 0:
            cv2.floodFill(a, mask, (sx, sy), (0, 0, 0), (18,) * 3, (18,) * 3, flags)
    bg = mask[1:-1, 1:-1].astype(np.float32) / 255
    bg = cv2.dilate(bg, np.ones((3, 3), np.uint8))            # swallow the light halo
    bg = cv2.GaussianBlur(bg, (0, 0), 0.9)
    big = small.resize((B.CARD_W, B.CARD_H), Image.LANCZOS).filter(
        ImageFilter.UnsharpMask(radius=2, percent=50, threshold=2))
    bgm = cv2.resize(bg, (B.CARD_W, B.CARD_H), interpolation=cv2.INTER_LINEAR)
    inner = cv2.erode((bgm < 0.02).astype(np.uint8), np.ones((37, 37), np.uint8))
    inner = cv2.GaussianBlur(inner.astype(np.float32), (0, 0), 6)
    return big, bgm, inner

def tint_lines(img, inner, color):
    """recolour the dark ink of border lines & corner compasses in the team colour."""
    a = np.asarray(img).astype(np.float32)
    L = a @ np.array([0.299, 0.587, 0.114], np.float32)
    d = np.clip((150 - L) / 95, 0, 1) * inner
    out = a * (1 - d[..., None]) + np.array(color, np.float32)[None, None, :] * d[..., None]
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))

def coloured_board(size, color, seed):
    W, H = size
    rng = np.random.default_rng(seed)
    low = rng.normal(0, 1, (H // 24 + 2, W // 24 + 2)).astype(np.float32)
    low = cv2.GaussianBlur(cv2.resize(low, (W, H), interpolation=cv2.INTER_CUBIC), (0, 0), 18)
    low /= np.abs(low).max() + 1e-6
    fine = cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 0.9)
    fine /= np.abs(fine).max() + 1e-6
    tex = 1 + 0.06 * low + 0.03 * fine
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    edge = np.clip(np.minimum(np.minimum(xx, W - 1 - xx) / W, np.minimum(yy, H - 1 - yy) / H) / 0.03, 0, 1)
    tex *= 0.9 + 0.1 * edge
    return np.array(color, np.float32)[None, None, :] * tex[..., None]

# ---------------------------------------------------------------- coloured elements
def comp_tinted(canvas, paper, patch, xy, strength=0.7):
    """paste a coloured RGBA patch, modulated by the parchment's own texture (keeps true hues)."""
    x, y = int(round(xy[0])), int(round(xy[1]))
    box = (x, y, x + patch.width, y + patch.height)
    L = np.asarray(paper.crop(box).convert('L')).astype(np.float32)
    tex = np.clip((L / max(L.mean(), 1)) ** strength, 0.82, 1.12)
    rgb = np.asarray(patch.convert('RGB')).astype(np.float32) * tex[..., None]
    region = canvas.crop(box)
    region.paste(Image.fromarray(rgb.clip(0, 255).astype(np.uint8)), (0, 0), patch.getchannel('A'))
    canvas.paste(region, (x, y))

def team_ribbon(band_w, band_h, t, S=3):
    tail, drop = int(band_h * 0.95), int(band_h * 0.30)
    notch, fold = int(band_h * 0.32), int(band_h * 0.42)
    W, H = band_w + 2 * tail + 24, band_h + drop + 24
    im = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x0, y0 = 12 + tail, 12
    x1, y1 = x0 + band_w, y0 + band_h
    ty0, ty1 = y0 + drop, y1 + drop
    P = lambda pts: [(x * S, y * S) for x, y in pts]
    lw, LINE = int(2.6 * S), (50, 24, 10)
    d.polygon(P([(x0 + fold, ty0), (x0 - tail, ty0), (x0 - tail + notch, (ty0 + ty1) / 2), (x0 - tail, ty1), (x0 + fold, ty1)]),
              fill=t['tail'], outline=LINE, width=lw)
    d.polygon(P([(x1 - fold, ty0), (x1 + tail, ty0), (x1 + tail - notch, (ty0 + ty1) / 2), (x1 + tail, ty1), (x1 - fold, ty1)]),
              fill=t['tail'], outline=LINE, width=lw)
    d.polygon(P([(x0, y1), (x0 + fold, y1), (x0 + fold, ty1)]), fill=t['fold'], outline=LINE, width=lw)
    d.polygon(P([(x1, y1), (x1 - fold, y1), (x1 - fold, ty1)]), fill=t['fold'], outline=LINE, width=lw)
    d.rectangle(P([(x0, y0), (x1, y1)]), fill=t['ribbon'], outline=LINE, width=lw)
    ins = 12
    d.rectangle(P([(x0 + ins, y0 + ins), (x1 - ins, y1 - ins)]), outline=t['rule'], width=int(2 * S))
    return im.resize((W, H), Image.LANCZOS), (x0, y0)

def team_tag(w, h, t, S=3):
    im = Image.new('RGBA', ((w + 8) * S, (h + 8) * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([4 * S, 4 * S, (w + 4) * S, (h + 4) * S], radius=16 * S, fill=t['ribbon'],
                        outline=(50, 24, 10), width=int(2.4 * S))
    d.rounded_rectangle([12 * S, 12 * S, (w - 4) * S, (h - 4) * S], radius=10 * S, outline=t['rule'], width=int(1.8 * S))
    return im.resize((w + 8, h + 8), Image.LANCZOS)

def wax_seal(R, color, ch, seed=1, S=2):
    """procedural wax seal with an embossed team character."""
    size = int(R * 2.3)
    Wp = size * S
    c = Wp / 2
    rng = np.random.default_rng(seed)
    ph = rng.uniform(0, 2 * np.pi, 3)
    yy, xx = np.mgrid[0:Wp, 0:Wp].astype(np.float32)
    dx, dy = (xx - c) / S, (yy - c) / S
    r, th = np.hypot(dx, dy), np.arctan2(dy, dx)
    edge = R * (1 + 0.035 * np.sin(5 * th + ph[0]) + 0.025 * np.sin(9 * th + ph[1]) + 0.012 * np.sin(19 * th + ph[2]))
    alpha = np.clip((edge - r) * 0.9 + 0.5, 0, 1)
    nx, ny = dx / R, dy / R
    shade = 1.0 + 0.17 * (-nx * 0.6 - ny * 0.8)                       # light from top-left
    rin = 0.70 * R
    dirc = (nx * 0.6 + ny * 0.8) / np.maximum(np.hypot(nx, ny), 1e-3)
    wall = np.exp(-((r - rin) / (0.045 * R)) ** 2)
    shade += wall * 0.24 * dirc                                       # pressed-in stamp wall
    shade *= np.where(r < rin, 0.88, 1.0)
    shade *= 1 - 0.28 * np.clip((r - 0.86 * edge) / (0.14 * edge), 0, 1)   # rounded wax edge
    # embossed character
    m = Image.new('L', (Wp, Wp), 0)
    f = ImageFont.truetype(SERIF_VF, int(rin * 1.32 * S))
    f.set_variation_by_name('Black')
    ImageDraw.Draw(m).text((c, c + 0.02 * R * S), ch, font=f, fill=255, anchor='mm')
    M = np.asarray(m.filter(ImageFilter.GaussianBlur(0.8 * S))).astype(np.float32) / 255
    k = int(3 * S)
    Ms = np.zeros_like(M)
    Ms[k:, k:] = M[:-k, :-k]
    light_wax = (0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]) > 150
    if light_wax:                                   # yellow: darker, deeper-looking character
        shade += 0.42 * (M - Ms) - 0.22 * M
    else:                                           # dark wax: brighter raised character
        shade += 0.46 * (M - Ms) + 0.24 * M
    # dotted ring
    ring = np.zeros_like(M)
    for a in np.linspace(0, 2 * np.pi, 28, endpoint=False):
        px, py = c + 0.84 * R * S * np.cos(a), c + 0.84 * R * S * np.sin(a)
        ring = np.maximum(ring, np.exp(-(((xx - px) ** 2 + (yy - py) ** 2) / (2 * (0.022 * R * S) ** 2))))
    shade += 0.20 * ring
    rgb = np.array(color, np.float32)[None, None, :] * shade[..., None]
    spec = np.exp(-((((dx + 0.42 * R) * 0.8 + (dy + 0.48 * R) * 0.6) / (0.28 * R)) ** 2
                    + (((dx + 0.42 * R) * -0.6 + (dy + 0.48 * R) * 0.8) / (0.10 * R)) ** 2))
    rgb = rgb * (1 - 0.35 * spec[..., None]) + 255 * 0.35 * spec[..., None]
    out = np.dstack([rgb.clip(0, 255), (alpha * 255)[..., None]]).astype(np.uint8)
    return Image.fromarray(out, 'RGBA').resize((size, size), Image.LANCZOS)

def ring_patch(r_out, r_in, color, S=3):
    size = int(2 * r_out + 4)
    im = Image.new('RGBA', (size * S, size * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = size * S / 2
    d.ellipse([c - r_out * S, c - r_out * S, c + r_out * S, c + r_out * S], fill=color + (255,))
    d.ellipse([c - r_in * S, c - r_in * S, c + r_in * S, c + r_in * S], fill=(0, 0, 0, 0))
    return im.resize((size, size), Image.LANCZOS)

def runs_tracked(d, cx, base_y, runs, track=0.0):
    """single line, several (text, font, colour) runs, centred with letter-spacing."""
    items = [(ch, f, col) for t, f, col in runs for ch in t]
    widths = [f.getlength(ch) for ch, f, _ in items]
    total = sum(widths) + sum(track * f.size for _, f, _ in items[:-1])
    x = cx - total / 2
    for (ch, f, col), w in zip(items, widths):
        d.text((x, base_y), ch, font=f, fill=col, anchor='ls')
        x += w + track * f.size
    return total

# ---------------------------------------------------------------- one card
def make_team_card(c, t, frame, bgm, inner, idx):
    card = tint_lines(frame, inner, t['dark'])
    paper = card.copy()                              # clean parchment = texture source
    cx = B.CARD_W // 2

    # header: 守護者的失落寶藏 · X隊線索卡
    ink = Image.new('RGB', card.size, (255, 255, 255))
    d = ImageDraw.Draw(ink)
    hw = runs_tracked(d, cx, 290, [('守護者的失落寶藏 · ', B.F(B.KAI_B, 42), B.INK2),
                                    (f"{t['name']}線索卡", B.F(B.KAI_B, 46), t['dark'])], track=0.12)
    for sx in (-1, 1):
        B.star4(d, cx + sx * (hw / 2 + 34), 275, 13, 4, t['dark'])
    card = ImageChops.multiply(card, ink)

    # medallion + team ring
    med_cy, r_img, rope_w = 726, 352, 46
    src = Image.open(f"{B.ASSETS}/{c['illus']}").convert('RGB')
    sx_, sy_, sr = c['crop']
    pic = src.crop((sx_ - sr, sy_ - sr, sx_ + sr, sy_ + sr)).resize((2 * r_img, 2 * r_img), Image.LANCZOS)
    m = Image.new('L', (8 * r_img, 8 * r_img), 0)
    ImageDraw.Draw(m).ellipse([0, 0, 8 * r_img - 1, 8 * r_img - 1], fill=255)
    m = m.resize((2 * r_img, 2 * r_img), Image.LANCZOS)
    Rs = r_img + rope_w - 8
    disc = Image.new('L', (2 * Rs, 2 * Rs), 0)
    ImageDraw.Draw(disc).ellipse([0, 0, 2 * Rs - 1, 2 * Rs - 1], fill=255)
    B.drop_shadow(card, disc, (cx - Rs, med_cy - Rs), offset=(8, 18), blur=22, strength=0.55)
    card.paste(pic, (cx - r_img, med_cy - r_img), m)
    rp = ring_patch(r_img - 6, r_img - 24, t['ribbon'])
    B.comp_normal(card, rp, (cx - rp.width / 2, med_cy - rp.height / 2))
    ring = B.rope_ring(r_img - 10, r_img - 10 + rope_w)
    B.comp_normal(card, ring, (cx - ring.width / 2, med_cy - ring.height / 2))

    # wax seal (upper-left of the medallion)
    sR = 128
    seal = wax_seal(sR, t['seal'], t['ch'], seed=idx + 3)
    ang = math.radians(-150)
    scx, scy = cx + 470 * math.cos(ang), med_cy + 470 * math.sin(ang)
    sxy = (scx - seal.width / 2, scy - seal.height / 2)
    B.drop_shadow(card, seal.getchannel('A'), sxy, offset=(6, 12), blur=10, strength=0.55, color=(40, 25, 15))
    B.comp_normal(card, seal, sxy)

    # ribbon title
    band_w, band_h, band_cy = 1030, 142, 1112
    rib, (bx, by) = team_ribbon(band_w, band_h, t)
    rx, ry = cx - band_w / 2 - bx, band_cy - band_h / 2 - by
    B.drop_shadow(card, rib.getchannel('A'), (rx, ry), offset=(0, 12), blur=12, strength=0.5)
    comp_tinted(card, paper, rib, (rx, ry))
    title = f"符號{c['num']}：{c['name']}"
    tf = B.F(B.KAI_B, 78)
    if tf.getlength(title) > band_w - 130:
        tf = B.F(B.KAI_B, int(78 * (band_w - 130) / tf.getlength(title)))
    if t['key'] != 'yellow':
        sh = Image.new('L', card.size, 0)
        B.text_tracked(ImageDraw.Draw(sh), cx + 3, band_cy + 0.36 * tf.size + 4, title, tf, 200)
        B.drop_shadow(card, sh, (0, 0), offset=(0, 0), blur=3, strength=0.6, color=(30, 10, 4))
    B.text_tracked(ImageDraw.Draw(card), cx, band_cy + 0.36 * tf.size, title, tf, t['on'])

    # text block
    QW, TW = 1116, int(1116 // 60) * 60
    TX0 = cx - TW // 2
    TOP, BOTTOM = band_cy + band_h / 2 + 58, 2232
    Lq = B.layout(B.tokenize(B.runs_from(c['quote'], B.St(B.F(B.KAI_B, 64), B.BROWN))), QW)
    lhq = 64 * 1.50
    Lt = B.layout(B.tokenize(B.runs_from(c['tip'], B.St(B.F(B.KAI_R, 60), B.INK), B.St(B.F(B.KAI_B, 60), t['dark']))), TW)
    lht = 60 * 1.55
    tag_h, g1, g2 = 80, 50, 34
    total = len(Lq) * lhq + g1 + tag_h + g2 + len(Lt) * lht
    y = TOP + (BOTTOM - TOP - total) / 2
    ink = Image.new('RGB', card.size, (255, 255, 255))
    d = ImageDraw.Draw(ink)
    y = B.draw_lines(d, Lq, cx - QW / 2, y, QW, lhq, 'center')
    y += g1
    tag_y = y
    lf = B.F(B.KAI_B, 46)
    lab_w = B.text_tracked(ImageDraw.Draw(Image.new('L', (10, 10))), 0, 0, B.TIP_LABEL, lf, 0, track=0.12)
    tag_w = int(lab_w + 64)
    for sx in (-1, 1):
        B.taper(d, cx + sx * (tag_w / 2 + 26), cx + sx * 470, tag_y + tag_h / 2, 5, t['dark'])
        B.star4(d, cx + sx * 488, tag_y + tag_h / 2, 10, 3, t['dark'])
    y += tag_h + g2
    B.draw_lines(d, Lt, TX0, y, TW, lht, 'justify')
    card = ImageChops.multiply(card, ink)
    tp = team_tag(tag_w, tag_h, t)
    comp_tinted(card, paper, tp, (cx - tp.width / 2, tag_y - 4))
    B.text_tracked(ImageDraw.Draw(card), cx, tag_y + tag_h / 2 + 0.36 * 46, B.TIP_LABEL, lf, t['on'], track=0.12)

    # mount the parchment on team-coloured card
    W, H = B.CARD_W + 2 * BAND, B.CARD_H + 2 * BAND
    board = coloured_board((W, H), t['band'], seed=idx)
    alpha = np.zeros((H, W), np.float32)
    alpha[BAND:BAND + B.CARD_H, BAND:BAND + B.CARD_W] = 1 - bgm
    shadow = cv2.GaussianBlur(np.roll(np.roll(alpha, 9, axis=0), 5, axis=1), (0, 0), 10)
    board *= (1 - 0.45 * shadow)[..., None]
    big = np.zeros((H, W, 3), np.float32)
    big[BAND:BAND + B.CARD_H, BAND:BAND + B.CARD_W] = np.asarray(card).astype(np.float32)
    out = board * (1 - alpha[..., None]) + big * alpha[..., None]
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))

# ---------------------------------------------------------------- sheets
def team_sheet(cards, t, cols, rows, page_size, cw, label_size=34, label=None):
    page = Image.new('RGB', page_size, (255, 255, 255))
    ch = round(cw * cards[0].height / cards[0].width)
    mx, my = (page_size[0] - cols * cw) // 2, (page_size[1] - rows * ch) // 2
    for i, c in enumerate(cards):
        page.paste(c.resize((cw, ch), Image.LANCZOS), (mx + (i % cols) * cw, my + (i // cols) * ch))
    d = ImageDraw.Draw(page)
    # inner cut lines (dashed, contrasting colour) + crop marks outside the block
    for k in range(1, cols):
        B._dashed(d, (mx + k * cw, my), (mx + k * cw, my + rows * ch), col=t['cut'], wdt=4)
    for k in range(1, rows):
        B._dashed(d, (mx, my + k * ch), (mx + cols * cw, my + k * ch), col=t['cut'], wdt=4)
    gray = (150, 150, 150)
    for k in (0, cols):                      # outer crop marks only (inner cuts are dashed)
        x = mx + k * cw
        d.line([(x, my - 46), (x, my - 10)], fill=gray, width=3)
        d.line([(x, my + rows * ch + 10), (x, my + rows * ch + 46)], fill=gray, width=3)
    for k in (0, rows):
        y = my + k * ch
        d.line([(mx - 46, y), (mx - 10, y)], fill=gray, width=3)
        d.line([(mx + cols * cw + 10, y), (mx + cols * cw + 46, y)], fill=gray, width=3)
    d.text((page_size[0] / 2, my - 24), label or f"{t['name']}線索卡（共 4 張）· 沿虛線剪下", font=B.F(B.KAI_B, label_size),
           fill=t['dark'] if t['key'] != 'yellow' else (150, 100, 0), anchor='ms')
    return page

def save_pdf(path, images, page_mm):
    import img2pdf
    pages = []
    for im in images:                       # ≈255 dpi JPEG pages keep the PDFs light but print-sharp
        b = io.BytesIO()
        im = im.resize((round(im.width * 0.85), round(im.height * 0.85)), Image.LANCZOS)
        im.save(b, 'JPEG', quality=90, subsampling=0)
        pages.append(b.getvalue())
    lf = img2pdf.get_layout_fun((img2pdf.mm_to_pt(page_mm[0]), img2pdf.mm_to_pt(page_mm[1])))
    with open(path, 'wb') as fh:
        fh.write(img2pdf.convert(pages, layout_fun=lf))

if __name__ == '__main__':
    import sys
    only = sys.argv[1:]                      # optional: limit to team keys for quick previews
    B.check_glyphs()
    frame, bgm, inner = prep_frame()
    os.makedirs(OUT, exist_ok=True)
    sheets, bigs = [], []
    for ti, t in enumerate(TEAMS):
        if only and t['key'] not in only:
            continue
        cards = []
        for i, c in enumerate(B.CARDS, 1):
            im = make_team_card(c, t, frame, bgm, inner, ti * 4 + i)
            os.makedirs(f"{OUT}/{t['key']}", exist_ok=True)
            im.save(f"{OUT}/{t['key']}/{t['key']}_card_{i}_{c['slug']}.jpg", quality=90, dpi=(300, 300))
            cards.append(im)
        s4 = team_sheet(cards, t, 2, 2, B.A4, 1110)
        sheets.append(s4)
        A4L = (B.A4[1], B.A4[0])
        for k in (0, 2):
            bigs.append(team_sheet(cards[k:k + 2], t, 2, 1, A4L, 1530))
        print('team', t['name'], 'done')
    if not only:
        scroll = Image.open(f'{B.BASE}/scroll_A4.jpg').convert('RGB')
        save_pdf(f'{B.BASE}/PRINT_scroll_and_team_cards_A4.pdf', [scroll] + sheets, (210, 297))
        save_pdf(f'{B.BASE}/PRINT_big_team_cards_A4_landscape.pdf', bigs, (297, 210))
    print('done')
