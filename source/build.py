#!/usr/bin/env python3
"""Build print-ready props for 守護者的失落寶藏 (scroll + 4 clue cards).

Artwork = AI-generated backgrounds/illustrations in ./assets
Text    = typeset here with LXGW WenKai TC (OFL), so every Chinese character is exact.
Run:  python3 build.py            (add --debug to draw layout guides)
"""
import re, math, sys, os
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageFilter
from fontTools.ttLib import TTFont

BASE = os.path.dirname(os.path.abspath(__file__))
ASSETS = f'{BASE}/assets'
FD = os.path.expanduser('~/.cache/scout_fonts')      # fonts are cached outside the workspace
_GF = 'https://raw.githubusercontent.com/google/fonts/main/ofl'
FONT_URLS = {
    'LXGWWenKaiTC-Regular.ttf': f'{_GF}/lxgwwenkaitc/LXGWWenKaiTC-Regular.ttf',
    'LXGWWenKaiTC-Bold.ttf': f'{_GF}/lxgwwenkaitc/LXGWWenKaiTC-Bold.ttf',
    'NotoSerifTC-VF.ttf': f'{_GF}/notoseriftc/NotoSerifTC%5Bwght%5D.ttf',
    'Cinzel-VF.ttf': f'{_GF}/cinzel/Cinzel%5Bwght%5D.ttf',
}
def ensure_fonts():
    import urllib.request
    os.makedirs(FD, exist_ok=True)
    for fn, url in FONT_URLS.items():
        p = f'{FD}/{fn}'
        if not os.path.exists(p) or os.path.getsize(p) < 10000:
            print('downloading font', fn)
            urllib.request.urlretrieve(url, p)
ensure_fonts()
KAI_R = f'{FD}/LXGWWenKaiTC-Regular.ttf'
KAI_B = f'{FD}/LXGWWenKaiTC-Bold.ttf'
DEBUG = '--debug' in sys.argv

# ---------------------------------------------------------------- palette
INK = (50, 29, 13)        # body text (sepia ink)
INK2 = (96, 60, 30)       # soft headers
BROWN = (82, 40, 12)      # riddle text
RED = (150, 30, 16)       # emphasis
TITLE = (98, 24, 9)
CREAM = (255, 247, 226)
A4 = (2480, 3508)         # 300 dpi

# ---------------------------------------------------------------- content
SCROLL_TITLE = '守護者的失落寶藏'
SCROLL_P1 = ('在很久以前，我們第 82 旅的資深守護者們在營地裡藏了一箱象徵著勇氣、智慧、團結與榮譽的'
             '**「傳奇寶藏」**。然而，隨著時間流逝，寶藏的下落逐漸成謎，只留下一張泛黃的古老羊皮卷。')
SCROLL_P2 = '傳說中，寶藏被強大的密碼封印著，單靠個人的力量是無法打開它的。森林的守護精靈留下了一個預言：'
SCROLL_PROPHECY = '「唯有 4 隊並肩作戰，\n集齊 4 個隱藏在各處的神秘符號，\n並通過三大考驗，解開最終謎題，\n才能讓失落的寶藏重見天日！」'
SCROLL_P3 = '隊員們，你們準備好迎接挑戰了嗎？戴好你們的童軍帽，擦亮雙眼，一場驚險刺激的解謎冒險現在正式開始！'

CARDS = [
    dict(num='一', name='領袖保管', slug='leader', illus='illus_1.jpg', crop=(512, 505, 500),
         quote='「掌管智慧與秩序的人，\n手中握著第一道曙光。」',
         tip='去找帶領你們的領袖吧！但要得到這枚符號，你們必須先完成領袖交給你們的**「指定任務挑戰」**，'
             '證明你們具備幼童軍的優秀品格，才能換取線索！'),
    dict(num='二', name='指定範圍', slug='area', illus='illus_2.jpg', crop=(512, 512, 500),
         quote='「它藏在看得見卻容易忽略的角落，\n需要眾人合力，借用竹竿\n與大自然的力量才能將它勾回。」',
         tip='環顧四周指定的活動範圍內，別用雙手，試試看團隊合作，用竹竿或其他工具在夾縫或高處把它**「撈」**出來！'),
    dict(num='三', name='房間隱蔽處', slug='hidden', illus='illus_3.jpg', crop=(530, 515, 494),
         quote='「當光線照不到陰影，\n秘密就靜靜躺在那裡。\n尋找平時最安靜、\n最容易被忽略的掩蔽之處。」',
         tip='仔細搜查房間裡的隱蔽死角（例如大型物件的背後、桌子下方或角落邊緣），符號三就藏在那裡等待細心的偵探。'),
    dict(num='四', name='分散碎片的字母', slug='fragments', illus='illus_4.jpg', crop=(512, 512, 500),
         quote='「零落的星光終將拼湊成銀河。\n它不只存在一個地方，\n而是化作碎片，靜靜躲在\n房間各個不起眼的隱蔽角落。」',
         tip='這枚符號化成了許多分散的字母碎片！大家別急著找單一目標，分頭在房間的各處隱蔽處搜尋，'
             '集齊所有碎片拼起來，就是你們要找的符號四！'),
]
CARD_HEADER = '守護者的失落寶藏 · 線索卡'
TIP_LABEL = '行動提示'

# ---------------------------------------------------------------- fonts / glyph check
_fc = {}
def F(path, size):
    k = (path, size)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(path, size)
    return _fc[k]

def check_glyphs():
    texts = [SCROLL_TITLE, SCROLL_P1, SCROLL_P2, SCROLL_PROPHECY, SCROLL_P3, CARD_HEADER, TIP_LABEL]
    for c in CARDS:
        texts += [c['quote'], c['tip'], f"符號{c['num']}：{c['name']}"]
    for p in (KAI_R, KAI_B):
        cmap = TTFont(p, lazy=True).getBestCmap()
        miss = sorted({ch for t in texts for ch in t if ch not in '\n *' and ord(ch) not in cmap})
        assert not miss, f'missing glyphs in {p}: {miss}'

# ---------------------------------------------------------------- CJK text engine
class St:
    def __init__(self, font, color):
        self.font, self.color = font, color

NO_START = set('，。、！？：；」』）】》〉…—‧·,.!?:;)]}%～')   # may not begin a line
NO_END = set('「『（【《〈([{')                               # may not end a line
PUNCT_C = set('，。、；：！？')                              # centred punctuation (TC style)
OPENERS = set('「『（【《〈')                                # ink sits in right half of the em box
CLOSERS = set('」』）】》〉')                                # ink sits in left half of the em box

import jieba, logging
jieba.setLogLevel(logging.WARNING)
for _w in ['你們', '我們', '隊員們', '守護者們', '單一', '目標', '幼童軍', '童軍帽', '泛黃', '一張', '羊皮卷',
           '符號一', '符號二', '符號三', '符號四', '拼起來', '試試看', '別急著', '大自然', '看得見', '掩蔽之處',
           '重見天日', '並肩作戰', '神秘符號', '三大考驗', '最終謎題', '解謎冒險', '驚險刺激', '正式開始',
           '擦亮雙眼', '準備好', '迎接挑戰', '第一道', '曙光', '隱蔽死角', '大型物件', '角落邊緣', '偵探', '夾縫',
           '高處', '竹竿', '眾人合力', '活動範圍', '環顧四周', '字母碎片', '隱蔽處', '集齊', '營地', '一箱',
           '象徵著', '下落', '成謎', '留下', '封印著', '個人', '守護精靈', '預言', '傳奇寶藏', '換取線索',
           '優秀品格', '指定任務', '細心', '等待', '分頭', '各處', '搜尋', '化作', '碎片', '不起眼', '零落',
           '星光', '拼湊', '銀河', '秘密', '靜靜', '光線', '陰影', '安靜', '容易', '忽略', '角落', '勾回']:
    jieba.add_word(_w, freq=200000)

def runs_from(text, base, emph=None):
    out = []
    for p in re.split(r'(\*\*.+?\*\*)', text):
        if not p:
            continue
        if p.startswith('**'):
            out.append((p[2:-2], emph or base, True))
        else:
            out.append((p, base, False))
    return out

def tokenize(runs):
    U, pos = [], 0
    plain = ''.join(r[0] for r in runs)
    bounds, o = set(), 0
    for seg in plain.split('\n'):
        for wd in jieba.cut(seg, HMM=True):
            bounds.add(o)
            o += len(wd)
        bounds.add(o)
        o += 1                                   # the newline
    for ri, (t, st, is_emph) in enumerate(runs):
        for m in re.finditer(r'[A-Za-z0-9]+|\n| |.', t):
            s = m.group(0)
            fs = st.font.size
            if s == '\n':
                kind, w = 'nl', 0.0
            elif s == ' ':
                kind, w = 'space', fs * 0.25
            elif s in PUNCT_C:
                kind, w = 'pc', st.font.getlength(s)
            elif s in OPENERS:
                kind, w = 'open', st.font.getlength(s)
            elif s in CLOSERS:
                kind, w = 'close', st.font.getlength(s)
            elif re.match(r'[A-Za-z0-9]', s):
                kind, w = 'latin', st.font.getlength(s)
            else:
                kind, w = 'char', st.font.getlength(s)
            U.append({'t': s, 'st': st, 'w': w, 'w0': w, 'kind': kind, 'shift': 0.0,
                      'run': ri, 'emph': is_emph, 'wb': pos in bounds})
            pos += len(s)
    for a, b in zip(U, U[1:]):                   # punctuation-pair compression
        if a['kind'] == 'close' and b['kind'] in ('pc', 'close'):
            a['w'] = a['w0'] * 0.5
        if a['kind'] in ('pc', 'open') and b['kind'] == 'open':
            b['w'] = b['w0'] * 0.5
            b['shift'] = -b['w0'] * 0.5
    return U

def unit_cap(u, w=None):
    fs = u['st'].font.size
    k = u['kind']
    w = u['w'] if w is None else w
    if k == 'pc':
        return 0.30 * fs
    if k in ('open', 'close'):
        return 0.30 * fs if w >= u['w0'] else 0.0
    if k == 'char':
        return 0.04 * fs
    if k == 'latin':
        return 0.02 * fs
    return 0.0

def _dp_break(S, max_w, indent):
    """Knuth-Plass-style optimal breaking for one paragraph segment."""
    n = len(S)
    if n == 0:
        return []
    fs = max(u['st'].font.size for u in S)
    INF = float('inf')
    best, prev = [INF] * (n + 1), [-1] * (n + 1)
    best[0] = 0.0

    def can_break(j):
        return S[j]['t'] not in NO_START and S[j - 1]['t'] not in NO_END

    def brk_pen(j):
        a, b = S[j - 1], S[j]
        p = 0.0
        if a['emph'] and b['emph'] and a['run'] == b['run']:
            p += 90                                # never split a highlighted phrase if avoidable
        elif not b['wb']:
            p += 30                                # avoid splitting a word
        if a['kind'] in ('pc', 'close'):
            p -= 6                                 # breaking after punctuation reads best
        return p

    for i in range(n):
        if best[i] == INF or (i > 0 and not can_break(i)):
            continue
        s = i
        while s < n and S[s]['kind'] == 'space':
            s += 1
        w = indent if i == 0 else 0.0
        caps = 0.0
        for j in range(s + 1, n + 1):
            u = S[j - 1]
            uwid = u['w0'] if (j - 1 == s and u['kind'] == 'open') else u['w']
            w += uwid
            caps += unit_cap(u, uwid)
            w_eff = w - (u['w'] if u['kind'] == 'space' else 0.0)
            if w_eff > max_w + caps and j > s + 1:
                break
            if j < n and not can_break(j):
                continue
            last = j == n
            if w_eff > max_w:
                cost = 25 * ((w_eff - max_w) / fs) ** 2 + 2
            else:
                cost = 0.0 if last else 14 * ((max_w - w_eff) / fs) ** 2
            if last and i > 0:
                nch = sum(1 for x in S[s:j] if x['kind'] != 'space')
                cost += 80 if nch <= 2 else (25 if nch <= 4 else 0)
            cost += 5
            tot = best[i] + cost + (brk_pen(j) if j < n else 0.0)
            if tot < best[j]:
                best[j], prev[j] = tot, i
    if best[n] == INF:
        raise RuntimeError('no feasible line breaking')
    spans, j = [], n
    while j > 0:
        spans.append((prev[j], j))
        j = prev[j]
    spans.reverse()
    lines = []
    for i, j in spans:
        s = i
        while s < j and S[s]['kind'] == 'space':
            s += 1
        L = [dict(u) for u in S[s:j]]
        while L and L[-1]['kind'] == 'space':
            L.pop()
        if L and L[0]['kind'] == 'open':
            L[0]['w'], L[0]['shift'] = L[0]['w0'], 0.0
        ind = indent if i == 0 else 0.0
        nat = ind + sum(u['w'] for u in L)
        lines.append({'u': L, 'ind': ind, 'last': j == n, 'w': nat, 'squeeze': max(0.0, nat - max_w)})
    return lines

def layout(U, max_w, indent=0.0):
    segs, cur = [], []
    for u in U:
        if u['kind'] == 'nl':
            segs.append(cur)
            cur = []
        else:
            cur.append(u)
    segs.append(cur)
    lines = []
    for k, seg in enumerate(segs):
        lines += _dp_break(seg, max_w, indent if k == 0 else 0.0)
    return lines

def draw_lines(d, lines, x, y, max_w, lh, align='justify', vc=0.36):
    for L in lines:
        U = L['u']
        if U:
            fs = max(u['st'].font.size for u in U)
            base = y + lh / 2 + vc * fs
            red, gap = [0.0] * len(U), 0.0
            if L['squeeze'] > 0:
                caps = [unit_cap(u) for u in U]
                tot = sum(caps) or 1.0
                red = [L['squeeze'] * c / tot for c in caps]
            elif align == 'justify' and not L['last'] and len(U) > 1:
                gap = (max_w - L['w']) / (len(U) - 1)
                if gap > 0.35 * fs:
                    gap = 0.0
            if align == 'center':
                xx = x + (max_w - (L['w'] - sum(red))) / 2 + L['ind']
            else:
                xx = x + L['ind']
            for u, r in zip(U, red):
                k = u['kind']
                if k not in ('space', 'nl'):
                    sh = u['shift'] + (-r if k == 'open' else 0.0 if k == 'close' else -r / 2)
                    d.text((xx + sh, base), u['t'], font=u['st'].font, fill=u['st'].color, anchor='ls')
                xx += u['w'] - r + gap
        y += lh
    return y

def text_tracked(d, cx, base_y, text, font, fill, track=0.0, **kw):
    ws = [font.getlength(c) for c in text]
    total = sum(ws) + track * font.size * (len(text) - 1)
    x = cx - total / 2
    for c, w in zip(text, ws):
        d.text((x, base_y), c, font=font, fill=fill, anchor='ls', **kw)
        x += w + track * font.size
    return total

# ---------------------------------------------------------------- compositing helpers
def comp_multiply(canvas, patch, xy):
    """multiply-blend an RGBA patch (paint soaking into parchment)."""
    x, y = int(round(xy[0])), int(round(xy[1]))
    region = canvas.crop((x, y, x + patch.width, y + patch.height))
    mult = ImageChops.multiply(region, patch.convert('RGB'))
    region.paste(mult, (0, 0), patch.getchannel('A'))
    canvas.paste(region, (x, y))

def comp_normal(canvas, patch, xy):
    canvas.paste(patch.convert('RGB'), (int(round(xy[0])), int(round(xy[1]))), patch.getchannel('A'))

def drop_shadow(canvas, alpha_L, xy, offset=(0, 10), blur=14, strength=0.45, color=(70, 45, 25)):
    pad = blur * 3
    m = Image.new('L', (alpha_L.width + 2 * pad, alpha_L.height + 2 * pad), 0)
    m.paste(alpha_L, (pad, pad))
    m = m.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * strength))
    x, y = int(xy[0]) - pad + offset[0], int(xy[1]) - pad + offset[1]
    region = canvas.crop((x, y, x + m.width, y + m.height))
    mult = ImageChops.multiply(region, Image.new('RGB', m.size, color))
    canvas.paste(Image.composite(mult, region, m), (x, y))

def glow(canvas, mask_L, color=(255, 249, 230), strength=0.75, blur=16):
    m = mask_L.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: min(255, int(v * strength * 1.6)))
    return Image.composite(Image.new('RGB', canvas.size, color), canvas, m)

def whiten(img, tol=12):
    """push the off-white page background to pure white (cleaner printing)."""
    a = np.asarray(img).copy()
    h, w = a.shape[:2]
    mask = np.zeros((h + 2, w + 2), np.uint8)
    flags = 4 | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE | (255 << 8)
    seeds = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2)]
    white_pt = np.median(np.array([a[y, x] for x, y in seeds], np.float32), axis=0)
    for sx, sy in seeds:
        if mask[sy + 1, sx + 1] == 0:
            cv2.floodFill(a, mask, (sx, sy), (0, 0, 0), (tol,) * 3, (tol,) * 3, flags)
    m = mask[1:-1, 1:-1].astype(np.float32) / 255
    m = cv2.dilate(m, np.ones((7, 7), np.uint8))
    m = cv2.GaussianBlur(m, (0, 0), 5)
    corrected = np.clip(a.astype(np.float32) * (255.0 / white_pt), 0, 255)
    out = a.astype(np.float32) * (1 - m[..., None]) + corrected * m[..., None]
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))

# ---------------------------------------------------------------- ornaments
def star4(d, cx, cy, R, r, fill):
    pts = []
    for k in range(8):
        a = math.pi / 4 * k - math.pi / 2
        rad = R if k % 2 == 0 else r
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    d.polygon(pts, fill=fill)

def taper(d, x_thick, x_point, y, thick, fill):
    d.polygon([(x_thick, y - thick / 2), (x_point, y), (x_thick, y + thick / 2)], fill=fill)

def divider(d, cx, y, half, fill, s=1.0):
    taper(d, cx - 44 * s, cx - half, y, 6 * s, fill)
    taper(d, cx + 44 * s, cx + half, y, 6 * s, fill)
    star4(d, cx, y, 26 * s, 7.5 * s, fill)
    for sx in (-1, 1):
        star4(d, cx + sx * (half + 20 * s), y, 10 * s, 3 * s, fill)

def rope_ring(r_in, r_out, S=3):
    base, hi, line = (204, 165, 104), (240, 216, 170), (72, 42, 18)
    size = int(2 * r_out + 12)
    c = size / 2 * S
    im = Image.new('RGBA', (size * S, size * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rm = (r_in + r_out) / 2 * S
    T = (r_out - r_in) * S
    a, b = T * 0.56, T * 0.25
    n = int(2 * math.pi * rm / (T * 0.47))
    tilt = math.radians(42)
    lw = max(1, int(round(2.3 * S)))
    for k in range(n):
        th = 2 * math.pi * k / n
        px, py = c + rm * math.cos(th), c + rm * math.sin(th)
        phi = th + math.pi / 2 + tilt
        cp, sp = math.cos(phi), math.sin(phi)

        def ell(aa, bb, oy=0.0):
            pts = []
            for t in range(0, 360, 10):
                tt = math.radians(t)
                ex, ey = aa * math.cos(tt), bb * math.sin(tt) + oy
                pts.append((px + ex * cp - ey * sp, py + ex * sp + ey * cp))
            return pts
        d.polygon(ell(a, b), fill=base, outline=line, width=lw)
        d.polygon(ell(a * 0.6, b * 0.36, -b * 0.3), fill=hi)
    return im.resize((size, size), Image.LANCZOS)

def ribbon_patch(band_w, band_h, S=3):
    tail, drop = int(band_h * 0.95), int(band_h * 0.30)
    notch, fold = int(band_h * 0.32), int(band_h * 0.42)
    W, H = band_w + 2 * tail + 24, band_h + drop + 24
    im = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x0, y0 = 12 + tail, 12
    x1, y1 = x0 + band_w, y0 + band_h
    ty0, ty1 = y0 + drop, y1 + drop
    P = lambda pts: [(x * S, y * S) for x, y in pts]
    lw = int(2.6 * S)
    LINE = (58, 20, 8)
    d.polygon(P([(x0 + fold, ty0), (x0 - tail, ty0), (x0 - tail + notch, (ty0 + ty1) / 2), (x0 - tail, ty1), (x0 + fold, ty1)]),
              fill=(150, 38, 26), outline=LINE, width=lw)
    d.polygon(P([(x1 - fold, ty0), (x1 + tail, ty0), (x1 + tail - notch, (ty0 + ty1) / 2), (x1 + tail, ty1), (x1 - fold, ty1)]),
              fill=(150, 38, 26), outline=LINE, width=lw)
    d.polygon(P([(x0, y1), (x0 + fold, y1), (x0 + fold, ty1)]), fill=(92, 20, 12), outline=LINE, width=lw)
    d.polygon(P([(x1, y1), (x1 - fold, y1), (x1 - fold, ty1)]), fill=(92, 20, 12), outline=LINE, width=lw)
    d.rectangle(P([(x0, y0), (x1, y1)]), fill=(184, 50, 33), outline=LINE, width=lw)
    ins = 12
    d.rectangle(P([(x0 + ins, y0 + ins), (x1 - ins, y1 - ins)]), outline=(226, 182, 100), width=int(2 * S))
    return im.resize((W, H), Image.LANCZOS), (x0, y0)

def tag_patch(w, h, S=3):
    im = Image.new('RGBA', ((w + 8) * S, (h + 8) * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([4 * S, 4 * S, (w + 4) * S, (h + 4) * S], radius=16 * S, fill=(178, 46, 30),
                        outline=(58, 20, 8), width=int(2.4 * S))
    d.rounded_rectangle([12 * S, 12 * S, (w - 4) * S, (h - 4) * S], radius=10 * S, outline=(226, 182, 100),
                        width=int(1.8 * S))
    return im.resize((w + 8, h + 8), Image.LANCZOS)

def medallion(canvas, illus_path, crop, cx, cy, r_img, rope_w):
    src = Image.open(illus_path).convert('RGB')
    sx, sy, sr = crop
    pic = src.crop((sx - sr, sy - sr, sx + sr, sy + sr)).resize((2 * r_img, 2 * r_img), Image.LANCZOS)
    m = Image.new('L', (8 * r_img, 8 * r_img), 0)
    ImageDraw.Draw(m).ellipse([0, 0, 8 * r_img - 1, 8 * r_img - 1], fill=255)
    m = m.resize((2 * r_img, 2 * r_img), Image.LANCZOS)
    R = r_img + rope_w - 8
    disc = Image.new('L', (2 * R, 2 * R), 0)
    ImageDraw.Draw(disc).ellipse([0, 0, 2 * R - 1, 2 * R - 1], fill=255)
    drop_shadow(canvas, disc, (cx - R, cy - R), offset=(8, 18), blur=22, strength=0.55)
    canvas.paste(pic, (cx - r_img, cy - r_img), m)
    ring = rope_ring(r_img - 10, r_img - 10 + rope_w)
    comp_normal(canvas, ring, (cx - ring.width / 2, cy - ring.height / 2))
    return R

# ---------------------------------------------------------------- SCROLL
def make_scroll():
    bg = whiten(Image.open(f'{ASSETS}/scroll_bg.jpg').convert('RGB'))
    s = A4[1] / bg.height
    nw = round(bg.width * s)
    page = Image.new('RGB', A4, (255, 255, 255))
    ox = (A4[0] - nw) // 2
    page.paste(bg.resize((nw, A4[1]), Image.LANCZOS), (ox, 0))

    cx = 1242                        # optical centre of the parchment
    ZX0, ZX1 = 672, 1812             # usable column (clear of the margin drawings)
    TOP, BOTTOM = 860, 2705          # body zone (below title, above treasure chest)

    # --- title with soft light halo
    tfont = F(KAI_B, 108)
    t_base = 712
    mask = Image.new('L', A4, 0)
    text_tracked(ImageDraw.Draw(mask), cx, t_base, SCROLL_TITLE, tfont, 255, track=0.07)
    page = glow(page, mask, strength=0.8, blur=18)

    ink = Image.new('RGB', A4, (255, 255, 255))
    d = ImageDraw.Draw(ink)
    text_tracked(d, cx, t_base, SCROLL_TITLE, tfont, TITLE, track=0.07)
    divider(d, cx, 786, 330, (120, 62, 26), s=1.0)

    # --- body: pick the largest size that fits
    for fs in (64, 63, 62, 61, 60, 59, 58, 56, 54):
        W = int((ZX1 - ZX0) // fs) * fs       # whole number of characters per line
        X0, X1 = cx - W // 2, cx + W // 2
        body = St(F(KAI_R, fs), INK)
        emph = St(F(KAI_B, fs), RED)
        pro = St(F(KAI_B, fs + 2), RED)
        lh, lhp = fs * 1.70, (fs + 2) * 1.58
        L1 = layout(tokenize(runs_from(SCROLL_P1, body, emph)), W, indent=2 * fs)
        L2 = layout(tokenize(runs_from(SCROLL_P2, body)), W, indent=2 * fs)
        LP = layout(tokenize(runs_from(SCROLL_PROPHECY, pro)), W)
        L3 = layout(tokenize(runs_from(SCROLL_P3, body)), W, indent=2 * fs)
        gap_p, gap_pro = fs * 0.55, fs * 0.75
        total = (len(L1) + len(L2) + len(L3)) * lh + len(LP) * lhp + gap_p + 2 * gap_pro
        if total <= BOTTOM - TOP:
            break
    extra = (BOTTOM - TOP) - total
    gap_p += min(extra * 0.2, fs * 0.4)
    gap_pro += min(extra * 0.2, fs * 0.4)
    total = (len(L1) + len(L2) + len(L3)) * lh + len(LP) * lhp + gap_p + 2 * gap_pro
    y = TOP + ((BOTTOM - TOP) - total) / 2
    y = draw_lines(d, L1, X0, y, W, lh, 'justify')
    y += gap_p
    y = draw_lines(d, L2, X0, y, W, lh, 'justify')
    y += gap_pro
    y = draw_lines(d, LP, X0, y, W, lhp, 'center')
    y += gap_pro
    y = draw_lines(d, L3, X0, y, W, lh, 'justify')
    print(f'scroll body font {fs}px, lines {len(L1)}+{len(L2)}+{len(LP)}+{len(L3)}, ends y={y:.0f}')

    page = ImageChops.multiply(page, ink)
    if DEBUG:
        dd = ImageDraw.Draw(page)
        dd.rectangle([X0, TOP, X1, BOTTOM], outline=(0, 120, 255), width=3)
        dd.rectangle([X0, 590, X1, 800], outline=(255, 0, 160), width=3)
    return page

# ---------------------------------------------------------------- CARDS
CARD_W, CARD_H = 1696, 2528

def make_card(c):
    frame = whiten(Image.open(f'{ASSETS}/card_frame_clean.png').convert('RGB'))
    card = frame.resize((CARD_W, CARD_H), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=2, percent=50, threshold=2))
    cx = CARD_W // 2

    # header
    ink = Image.new('RGB', card.size, (255, 255, 255))
    d = ImageDraw.Draw(ink)
    hw = text_tracked(d, cx, 290, CARD_HEADER, F(KAI_B, 42), INK2, track=0.14)
    for sx in (-1, 1):
        star4(d, cx + sx * (hw / 2 + 34), 275, 13, 4, INK2)
    card = ImageChops.multiply(card, ink)

    # medallion + ribbon (badge composition)
    med_cy, r_img, rope_w = 726, 352, 46
    medallion(card, f"{ASSETS}/{c['illus']}", c['crop'], cx, med_cy, r_img, rope_w)
    band_w, band_h, band_cy = 1030, 142, 1112
    rib, (bx, by) = ribbon_patch(band_w, band_h)
    rx, ry = cx - band_w / 2 - bx, band_cy - band_h / 2 - by
    drop_shadow(card, rib.getchannel('A'), (rx, ry), offset=(0, 12), blur=12, strength=0.5)
    comp_multiply(card, rib, (rx, ry))
    title = f"符號{c['num']}：{c['name']}"
    td = ImageDraw.Draw(card)
    tf = F(KAI_B, 78)
    tw = tf.getlength(title)
    if tw > band_w - 130:
        tf = F(KAI_B, int(78 * (band_w - 130) / tw))
    sh = Image.new('L', card.size, 0)
    text_tracked(ImageDraw.Draw(sh), cx + 3, band_cy + 0.36 * tf.size + 4, title, tf, 200)
    drop_shadow(card, sh, (0, 0), offset=(0, 0), blur=3, strength=0.6, color=(40, 8, 4))
    text_tracked(td, cx, band_cy + 0.36 * tf.size, title, tf, CREAM)

    # text block (riddle, section label, action tip) – vertically centred in the free area
    QW = 1116                                   # riddle lines are hand-broken & centred
    TW = int(1116 // 60) * 60                   # action-tip column = whole characters
    TX0, TX1 = cx - TW // 2, cx + TW // 2
    TOP, BOTTOM = band_cy + band_h / 2 + 58, 2232
    qst = St(F(KAI_B, 64), BROWN)
    Lq = layout(tokenize(runs_from(c['quote'], qst)), QW)
    lhq = 64 * 1.50
    tst, temph = St(F(KAI_R, 60), INK), St(F(KAI_B, 60), RED)
    Lt = layout(tokenize(runs_from(c['tip'], tst, temph)), TW)
    lht = 60 * 1.55
    tag_h, g1, g2 = 80, 50, 34
    total = len(Lq) * lhq + g1 + tag_h + g2 + len(Lt) * lht
    y = TOP + (BOTTOM - TOP - total) / 2

    ink = Image.new('RGB', card.size, (255, 255, 255))
    d = ImageDraw.Draw(ink)
    y = draw_lines(d, Lq, cx - QW / 2, y, QW, lhq, 'center')
    y += g1
    tag_y = y
    lf = F(KAI_B, 46)
    lab_w = text_tracked(ImageDraw.Draw(Image.new('L', (10, 10))), 0, 0, TIP_LABEL, lf, 0, track=0.12)
    tag_w = int(lab_w + 64)
    for sx in (-1, 1):
        taper(d, cx + sx * (tag_w / 2 + 26), cx + sx * 470, tag_y + tag_h / 2, 5, (120, 62, 26))
        star4(d, cx + sx * 488, tag_y + tag_h / 2, 10, 3, (120, 62, 26))
    y += tag_h + g2
    y = draw_lines(d, Lt, TX0, y, TW, lht, 'justify')
    card = ImageChops.multiply(card, ink)

    tp = tag_patch(tag_w, tag_h)
    comp_multiply(card, tp, (cx - tp.width / 2, tag_y - 4))
    text_tracked(ImageDraw.Draw(card), cx, tag_y + tag_h / 2 + 0.36 * 46, TIP_LABEL, lf, CREAM, track=0.12)  # label

    if DEBUG:
        dd = ImageDraw.Draw(card)
        dd.rectangle([TX0, TOP, TX1, BOTTOM], outline=(0, 120, 255), width=3)
    print(f"card {c['num']}: riddle {len(Lq)} lines, tip {len(Lt)} lines, block ends y={y:.0f}")
    return card

# ---------------------------------------------------------------- cut sheets
def _dashed(d, p0, p1, col=(160, 160, 160), dash=26, gapl=16, wdt=3):
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    t = 0
    while t < L:
        e = min(L, t + dash)
        d.line([(x0 + ux * t, y0 + uy * t), (x0 + ux * e, y0 + uy * e)], fill=col, width=wdt)
        t += dash + gapl

def make_sheet(cards, cols, rows, page_size, card_w):
    """cards laid edge-to-edge (one cut separates neighbours) with dashed cut lines."""
    page = Image.new('RGB', page_size, (255, 255, 255))
    cw = card_w
    ch = round(cw * CARD_H / CARD_W)
    mx, my = (page_size[0] - cols * cw) // 2, (page_size[1] - rows * ch) // 2
    for i, c in enumerate(cards):
        page.paste(c.resize((cw, ch), Image.LANCZOS), (mx + (i % cols) * cw, my + (i // cols) * ch))
    d = ImageDraw.Draw(page)
    ext = 40
    for k in range(cols + 1):
        x = mx + k * cw
        _dashed(d, (x, my - ext), (x, my + rows * ch + ext))
    for k in range(rows + 1):
        y = my + k * ch
        _dashed(d, (mx - ext, y), (mx + cols * cw + ext, y))
    d.text((page_size[0] / 2, my - 20), '✂  沿虛線剪下（也可沿羊皮紙撕邊剪出，更有古卷感）'.replace('✂  ', ''),
           font=F(KAI_R, 30), fill=(150, 150, 150), anchor='ms')
    return page

def save_pdf(path, images, page_mm):
    import img2pdf, io
    pages = []
    for im in images:
        b = io.BytesIO()
        im.save(b, 'JPEG', quality=94, dpi=(300, 300), subsampling=0)
        pages.append(b.getvalue())
    lf = img2pdf.get_layout_fun((img2pdf.mm_to_pt(page_mm[0]), img2pdf.mm_to_pt(page_mm[1])))
    with open(path, 'wb') as fh:
        fh.write(img2pdf.convert(pages, layout_fun=lf))

# ---------------------------------------------------------------- main
if __name__ == '__main__':
    check_glyphs()
    os.makedirs(f'{BASE}/cards', exist_ok=True)
    scroll = make_scroll()
    scroll.save(f'{BASE}/scroll_A4.jpg', quality=95, dpi=(300, 300), subsampling=0)
    cards = []
    for i, c in enumerate(CARDS, 1):
        im = make_card(c)
        im.save(f"{BASE}/cards/card_{i}_{c['slug']}.png", dpi=(300, 300))
        cards.append(im)
    # 4 cards on one portrait A4 (each ≈ 94 × 140 mm)
    sheet4 = make_sheet(cards, 2, 2, A4, 1110)
    sheet4.save(f'{BASE}/clue_cards_A4_4up.png', dpi=(300, 300))
    # BIG cards: 2 per landscape A4 (each ≈ 129 × 192 mm) – easier for kids to read
    A4L = (A4[1], A4[0])
    big = [make_sheet(cards[k:k + 2], 2, 1, A4L, 1520) for k in (0, 2)]
    for k, im in enumerate(big, 1):
        im.save(f'{BASE}/cards/big_cards_A4_landscape_p{k}.png', dpi=(300, 300))
    if not DEBUG:
        save_pdf(f'{BASE}/print_scroll_and_cards_A4.pdf', [scroll, sheet4], (210, 297))
        save_pdf(f'{BASE}/print_big_cards_A4_landscape.pdf', big, (297, 210))
    print('done')
