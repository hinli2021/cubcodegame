#!/usr/bin/env python3
"""Compile the 守護者的失落寶藏 materials into one downloadable package.

    python3 build_package.py          build 00_Leader_Guide.pdf + Scout82_Treasure_Hunt_Package.zip
    python3 build_package.py --clean  ...then delete the loose copies that are now inside the ZIP
                                      (rebuild them any time with build.py / build_teams.py / build_code.py)

Needs the outputs of build.py, build_teams.py, build_code.py and build_app.py (app/index.html) to exist.
"""
import io
import os
import sys
import zipfile

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.fonts import addMapping
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image as RLImage, KeepTogether, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.flowables import HRFlowable

import build as B
import build_teams as T
import build_code as C

BASE = B.BASE
PKG = 'Scout82_Treasure_Hunt_Package'
ZIP = f'{BASE}/{PKG}.zip'
GUIDE = f'{BASE}/00_Leader_Guide.pdf'
TMP = '/tmp/guide_assets'

# (name inside the zip, source file, 內容, pages, paper)
PRINTS = [
    ('1_Scroll_and_Team_Clue_Cards_A4.pdf', 'PRINT_scroll_and_team_cards_A4.pdf',
     '故事卷軸（第 1 頁）＋ 4 隊線索卡（第 2–5 頁，每頁 1 隊 4 張）', 5,
     '卷軸：普通紙或米色紙<br/>線索卡：200–250gsm 卡紙'),
    ('2_Square_Sign_Cards_A4.pdf', 'PRINT_code_square_sign_cards_A4.pdf',
     '神秘符號卡（每頁 1 隊 4 張；符號四印有拼圖剪線）', 4, '200–250gsm 卡紙，建議過膠'),
    ('3_Decoder_Cards_A4.pdf', 'PRINT_code_hint_cards_A4.pdf',
     '密碼翻譯提示（4 隊各 1 張，同一頁）', 1, '200–250gsm 卡紙'),
]
# by-products of build_teams.py / build_code.py that are not part of the package (removed by --clean)
NOT_PACKAGED = ['PRINT_big_team_cards_A4_landscape.pdf', 'PRINT_code_hint_cards_BIG_A4_landscape.pdf',
                'PRINT_code_sign_tokens_A4.pdf']
APP = f'{B.BASE}/app/index.html'
APP_ZIP = '03_Treasure_Lock_App/Treasure_Lock_App.html'
WHERE = ['領袖保管', '指定範圍', '房間隱蔽處', '分散碎片（拼圖）']


def rgb(c):
    return colors.Color(c[0] / 255, c[1] / 255, c[2] / 255)


INK, TITLE, BROWN = rgb(B.INK), rgb(B.TITLE), rgb(B.BROWN)
PARCH, PARCH2, LINE, GREY = rgb((247, 240, 224)), rgb((240, 228, 204)), rgb((200, 176, 140)), rgb((130, 112, 92))
SAFE_RED = rgb((160, 32, 20))
ZH = {row[0]: row[2] for row in C.CODE}
ICON = {row[0]: row[1] for row in C.CODE}


# ------------------------------------------------------------------ guide assets
def sign_file(L):
    return 'blank_ghost.png' if L == '_' else f'{L}_{ICON[L]}.png'


def prep_assets():
    os.makedirs(TMP, exist_ok=True)
    for L in ZH:
        im = Image.open(f'{BASE}/code/signs/{sign_file(L)}').convert('RGBA')
        bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
        Image.alpha_composite(bg, im).convert('RGB').resize((160, 160), Image.LANCZOS).save(f'{TMP}/sign_{L}.png')
    thumbs = {'scroll': 'scroll_A4.jpg', 'clue': 'team_cards/red/red_card_1_leader.jpg',
              'square': 'code/square_cards/red_1_F.jpg', 'decoder': 'code/hint_card_red.jpg'}
    in_zip = {'team_cards/red/red_card_1_leader.jpg': 'Red_Team/Red_Clue_Card_1_Leader.jpg',
              'code/square_cards/red_1_F.jpg': 'Red_Team/Red_Sign_Card_1_F.jpg',
              'code/hint_card_red.jpg': 'Red_Team/Red_Decoder_Card.jpg'}
    for k, f in thumbs.items():
        if os.path.exists(f'{BASE}/{f}'):
            im = Image.open(f'{BASE}/{f}').convert('RGB')
        else:                                 # loose card images removed by --clean: read them from the package
            with zipfile.ZipFile(ZIP) as z:
                im = Image.open(io.BytesIO(z.read(f'{PKG}/02_Individual_Images/{in_zip[f]}'))).convert('RGB')
        im.thumbnail((420, 420), Image.LANCZOS)
        im.save(f'{TMP}/thumb_{k}.jpg', quality=88)


# ------------------------------------------------------------------ styles
def styles():
    pdfmetrics.registerFont(TTFont('Kai', B.KAI_R))
    pdfmetrics.registerFont(TTFont('KaiB', B.KAI_B))
    for b in (0, 1):
        for i in (0, 1):
            addMapping('Kai', b, i, 'KaiB' if b else 'Kai')
    s = {}
    s['base'] = ParagraphStyle('base', fontName='Kai', fontSize=10.5, leading=16.5, textColor=INK, wordWrap='CJK')
    s['h1'] = ParagraphStyle('h1', parent=s['base'], fontName='KaiB', fontSize=15, leading=20, textColor=TITLE,
                             spaceBefore=4, spaceAfter=2)
    s['step'] = ParagraphStyle('step', parent=s['base'], leftIndent=17, bulletIndent=0, bulletFontName='KaiB',
                               bulletColor=TITLE, spaceAfter=2.5)
    s['dot'] = ParagraphStyle('dot', parent=s['step'], bulletFontName='Kai', bulletColor=BROWN)
    s['cell'] = ParagraphStyle('cell', parent=s['base'], fontSize=9.5, leading=13.5)
    s['cellc'] = ParagraphStyle('cellc', parent=s['cell'], alignment=1)
    s['head'] = ParagraphStyle('head', parent=s['cellc'], fontName='KaiB', textColor=TITLE)
    s['small'] = ParagraphStyle('small', parent=s['base'], fontSize=8.5, leading=12.5, textColor=GREY)
    s['tree'] = ParagraphStyle('tree', parent=s['base'], fontSize=9.5, leading=14)
    return s


def section(s, zh, en):
    return [Spacer(1, 5),
            Paragraph(f'{zh}<font name="Kai" size="10" color="#8a6a4a">　{en}</font>', s['h1']),
            HRFlowable(width='100%', thickness=0.8, color=LINE, spaceBefore=1, spaceAfter=6)]


def steps(s, items, numbered=True, style='step'):
    out = []
    for i, txt in enumerate(items):
        out.append(Paragraph(txt, s[style], bulletText=f'{i + 1}.' if numbered else '•'))
    return out


def deco(canv, doc):
    w, h = A4
    canv.saveState()
    canv.setStrokeColor(LINE)
    canv.setLineWidth(0.6)
    canv.line(16 * mm, h - 12 * mm, w - 16 * mm, h - 12 * mm)
    canv.line(16 * mm, 13 * mm, w - 16 * mm, 13 * mm)
    canv.setFont('Kai', 8.5)
    canv.setFillColor(GREY)
    canv.drawString(16 * mm, h - 10.3 * mm, '守護者的失落寶藏 · 領袖指南 Leader Guide')
    canv.setFillColor(SAFE_RED)
    canv.drawRightString(w - 16 * mm, h - 10.3 * mm, '領袖專用 · 內含答案，請勿讓隊員看到')
    canv.setFillColor(GREY)
    canv.drawCentredString(w / 2, 8.5 * mm, f'— {doc.page} —')
    canv.restoreState()


def team_text_col(t):
    return '#422402' if t['key'] == 'yellow' else '#ffffff'


def hexc(c):
    return '#%02x%02x%02x' % tuple(c)


# ------------------------------------------------------------------ guide content
def build_guide():
    prep_assets()
    s = styles()
    W = A4[0] - 32 * mm
    story = []

    # title block
    title = [Paragraph('<font color="#8a6a4a">第 82 旅幼童軍 · 尋寶活動物資包</font>',
                       ParagraphStyle('k', parent=s['base'], alignment=1, fontSize=11)),
             Paragraph('守護者的失落寶藏', ParagraphStyle('t', parent=s['base'], fontName='KaiB', fontSize=27,
                                                    leading=36, alignment=1, textColor=TITLE)),
             Paragraph('領袖指南　<font size="12" color="#8a6a4a">Leader Guide</font>',
                       ParagraphStyle('st', parent=s['base'], fontName='KaiB', fontSize=15, leading=20,
                                      alignment=1, textColor=BROWN))]
    tb = Table([[title]], colWidths=[W])
    tb.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), PARCH), ('BOX', (0, 0), (-1, -1), 1, LINE),
                            ('TOPPADDING', (0, 0), (-1, -1), 9), ('BOTTOMPADDING', (0, 0), (-1, -1), 11),
                            ('ROUNDEDCORNERS', [6, 6, 6, 6])]))
    story += [tb, Spacer(1, 10)]

    # flow strip
    def thumb(k, h):
        im = Image.open(f'{TMP}/thumb_{k}.jpg')
        return RLImage(f'{TMP}/thumb_{k}.jpg', width=h * im.width / im.height, height=h)
    arrow = Paragraph('<font name="KaiB" size="16" color="#b08a5a">→</font>', s['cellc'])
    code_box = Table([[Paragraph('寶藏密碼', s['head'])],
                      [Paragraph('<font name="KaiB" size="22" color="#62180a">4591</font>',
                                 ParagraphStyle('c', parent=s['cellc'], leading=26))]],
                     colWidths=[25 * mm], rowHeights=[8 * mm, 13 * mm])
    code_box.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), PARCH2), ('BOX', (0, 0), (-1, -1), 1.2, TITLE),
                                  ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('ROUNDEDCORNERS', [5, 5, 5, 5])]))
    imgs = [thumb('scroll', 33 * mm), thumb('clue', 33 * mm), thumb('square', 27 * mm), thumb('decoder', 33 * mm),
            code_box]
    caps = ['① 故事卷軸<br/><font size="8.5" color="#82705c">開場讀出預言</font>',
            '② 線索卡 ×4<br/><font size="8.5" color="#82705c">逐張領取</font>',
            '③ 神秘符號卡 ×4<br/><font size="8.5" color="#82705c">每張 = 1 個字母</font>',
            '④ 解碼卡<br/><font size="8.5" color="#82705c">符號 → 英文字母</font>',
            '⑤ 寶藏封印 App<br/><font size="8.5" color="#82705c">四隊合力輸入密碼</font>']
    row1, row2 = [], []
    for i in range(5):
        row1.append(imgs[i])
        row2.append(Paragraph(caps[i], s['cellc']))
        if i < 4:
            row1.append(arrow)
            row2.append('')
    cw_item, cw_arr = 28.4 * mm, (W - 5 * 28.4 * mm) / 4
    fs = Table([row1, row2], colWidths=[cw_item, cw_arr] * 4 + [cw_item])
    fs.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                            ('VALIGN', (0, 1), (-1, 1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 1),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 1), ('TOPPADDING', (0, 1), (-1, 1), 5)]))
    story += [fs]

    # 1. overview
    story += section(s, '一、遊戲概覽', 'Overview')
    story += steps(s, [
        '全團分成<b>紅、藍、綠、黃</b> 4 隊。每隊有自己顏色的一套物資，卡上的隊色和蠟封（紅／藍／綠／黃）方便分辨。',
        '<b>線索卡逐張領取</b>：每隊先拿 1 張線索卡，找到它指示的<b>神秘符號卡</b>後，回到領袖處出示，'
        '才可領取下一張。4 張的次序不限（由隊伍選擇或領袖隨機派發）。',
        '用<b>「密碼翻譯提示」解碼卡</b>把 4 個符號翻譯成英文字母，拼出隊伍的<b>英文數字</b>。',
        '4 隊合力，在<b>「寶藏封印」App</b> 的四色轉輪上輸入各自的數字（<b>紅 → 藍 → 綠 → 黃</b>），'
        '寶藏密碼 <b>4591</b> 一對，寶箱便會打開，正好呼應預言：「唯有 4 隊並肩作戰……」。'],
        numbered=False, style='dot')

    # 2. print list
    story += section(s, '二、列印清單', 'What to print')
    rows = [[Paragraph(h, s['head']) for h in ('', '檔案（01_Print_Files 資料夾）', '內容', '頁數', '建議紙張')]]
    for i, (zn, src, what, pages, paper) in enumerate(PRINTS):
        rows.append([Paragraph(f'<font name="KaiB" color="#62180a">{i + 1}</font>', s['cellc']),
                     Paragraph(zn.replace('_', '_<font size="1"> </font>'), s['cell']),
                     Paragraph(what, s['cell']), Paragraph(str(pages), s['cellc']), Paragraph(paper, s['cell'])])
    pt = Table(rows, colWidths=[8 * mm, 56 * mm, 58 * mm, 11 * mm, W - 133 * mm], repeatRows=1)
    pst = [('GRID', (0, 0), (-1, -1), 0.5, LINE), ('BACKGROUND', (0, 0), (-1, 0), PARCH2),
           ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 4),
           ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]
    for r in (1, 2, 3):
        pst.append(('BACKGROUND', (0, r), (0, r), PARCH))
    pt.setStyle(TableStyle(pst))
    story += [pt, Spacer(1, 7)]
    story += [KeepTogether(steps(s, [
        '以<b>彩色</b>及<b>「實際大小（100%）」</b>列印，卡片尺寸最準確。',
        '沿虛線剪下。每頁底部的灰色「藏卡對照／領袖參考」文字在裁切範圍以外，剪卡時會一併剪走，隊員不會看到答案。',
        '符號四的卡印有<b>拼圖剪線</b>：先剪出整張卡，再沿拼圖線剪成 4 塊碎片。',
        '建議先過膠再剪，卡片更耐用；用竹竿撈取時也不怕弄皺。',
        '解碼卡沒有記錄欄，每隊另需<b>紙和筆</b>，記下符號和字母。'], numbered=False, style='dot'))]

    # 3. setup + answer table
    sec3 = section(s, '三、佈置與藏卡', 'Setup — where each card goes')
    hdr = [Paragraph('隊伍', s['head']), Paragraph('英文數字', s['head'])] + \
          [Paragraph(f'符號{C.NUMS[k]}<br/><font name="Kai" size="8.5" color="#82705c">{WHERE[k]}</font>', s['head'])
           for k in range(4)]
    rows, tst = [hdr], [('GRID', (0, 0), (-1, -1), 0.5, LINE), ('BACKGROUND', (0, 0), (-1, 0), PARCH2),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 3),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]
    for r, t in enumerate(T.TEAMS, start=1):
        word = C.TEAM_WORDS[t['key']]
        shown = 'ONE ＋ 空格' if word == 'ONE_' else word
        row = [Paragraph(f'<font name="KaiB" size="11" color="{team_text_col(t)}">{t["name"]}</font>', s['cellc']),
               Paragraph(f'<font name="KaiB" color="{hexc(t["dark"])}">{shown}</font><br/>'
                         f'= <font name="KaiB" size="13" color="{hexc(t["dark"])}">{C.DIGIT[word]}</font>',
                         s['cellc'])]
        for L in word:
            lab = '空格' if L == '_' else L
            row.append(Paragraph(f'<img src="{TMP}/sign_{L}.png" width="25" height="25" valign="middle"/>'
                                 f'　{ZH[L]} <font name="KaiB">{lab}</font>', s['cellc']))
        rows.append(row)
        tst.append(('BACKGROUND', (0, r), (0, r), rgb(t['band'])))
    at = Table(rows, colWidths=[17 * mm, 25 * mm] + [(W - 42 * mm) / 4] * 4)
    at.setStyle(TableStyle(tst))
    story += [KeepTogether(sec3 + [at]), Spacer(1, 7)]
    story += steps(s, [
        '<b>符號一 · 領袖保管</b>：交給該隊領袖。隊員完成領袖的「指定任務挑戰」後，才可換取這張卡。',
        '<b>符號二 · 指定範圍</b>：藏在指定活動範圍內「看得見卻容易忽略」的高處或夾縫。隊員不可用手，'
        '要合作用竹竿或其他工具撈出來（請預備竹竿／工具）。',
        '<b>符號三 · 房間隱蔽處</b>：藏在房間的隱蔽死角，例如大型物件背後、桌子下方或角落邊緣。',
        '<b>符號四 · 分散碎片</b>：沿拼圖線剪成 4 塊，分散藏在房間各個不起眼的角落。',
        '不同隊伍會有相同的符號（例如紅隊和藍隊都有「月亮」），請提醒隊員<b>只收集自己隊色的卡</b>。',
        '符號卡沒有印上「一二三四」；每頁符號卡底部的「藏卡對照」列明哪張卡放哪裏，剪卡前可先核對。',
        '<b>線索站</b>：領袖保管每隊的 4 張線索卡，按隊色分好（例如用信封或夾子），方便逐張派發。'])
    kit = Table([[Paragraph('<b>每隊領取</b>', s['head']), Paragraph('<b>領袖預備</b>', s['head']),
                  Paragraph('<b>場地物資</b>', s['head'])],
                 [Paragraph('□ 第 1 張線索卡（隊色）<br/>□ 解碼卡 1 張<br/>□ 紙和筆', s['cell']),
                  Paragraph('□ 各隊其餘線索卡（逐張派發）<br/>□ 各隊的符號一卡＋「指定任務挑戰」<br/>'
                            '□ 電腦／平板（已開啟寶藏封印 App）<br/>□ 實體獎品（開鎖後頒發，如有）', s['cell']),
                  Paragraph('□ 竹竿／撈取工具<br/>□ 已藏好符號二、三及符號四碎片<br/>□ 喇叭；投影機或大螢幕（選用）',
                            s['cell'])]],
                colWidths=[W / 3] * 3)
    kit.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.5, LINE), ('BACKGROUND', (0, 0), (-1, 0), PARCH2),
                             ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 4),
                             ('BOTTOMPADDING', (0, 0), (-1, -1), 6), ('LEFTPADDING', (0, 1), (-1, 1), 8)]))
    story += [Spacer(1, 6), KeepTogether([Paragraph('<b>物資分發清單</b>', s['base']), Spacer(1, 3), kit])]

    # 4. game flow
    story += section(s, '四、遊戲流程', 'How the game runs')
    flow = steps(s, [
        '<b>開場</b>：領袖讀出故事卷軸，宣讀預言，向每隊派發<b>第 1 張線索卡</b>、解碼卡和紙筆。',
        '<b>逐張尋找</b>：按手上的線索卡找出該張神秘符號卡（符號四要先集齊 4 塊碎片並拼好），'
        '然後回到領袖處出示，<b>換取下一張線索卡</b>，如此類推，直至集齊 4 張符號卡。'
        '下一張派哪張，可由隊伍選擇或領袖隨機決定。',
        '<b>解碼</b>：對照解碼卡，把每個符號翻譯成英文字母，按符號一至四的次序拼出英文數字。'
        '即使次序弄亂，也可把 4 個字母重新排列（例如 U、R、F、O → FOUR）。',
        '<b>空格</b>：黃隊的「幽靈」符號代表空格：O、N、E、空格 → ONE → 1。',
        '<b>開啟寶藏</b>：4 隊集合到「寶藏封印」App 前，每隊在自己顏色的轉輪上輸入數字'
        '（紅 4、藍 5、綠 9、黃 1），再一起按<b>「開鎖」</b>，寶箱便會打開！'])
    note = Table([[Paragraph('<font name="KaiB" color="#7d5a0c">★ App 提示</font>　轉輪已按 紅 → 藍 → 綠 → 黃 排列，'
                             '每隊只需轉自己顏色的一格，毋須另外說明合併次序。輸入錯誤時守護精靈會鼓勵隊員；'
                             '連錯 3 次後，會輪流提示「英文數字換成阿拉伯數字」、「轉輪次序」和「幽靈＝空格」。',
                             s['cell'])]], colWidths=[W])
    note.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), rgb((252, 244, 220))),
                              ('BOX', (0, 0), (-1, -1), 0.8, rgb((214, 176, 100))),
                              ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                              ('LEFTPADDING', (0, 0), (-1, -1), 8), ('ROUNDEDCORNERS', [4, 4, 4, 4])]))
    story += flow[:-1] + [KeepTogether([flow[-1], Spacer(1, 3), note])]

    # 5. the treasure-lock app
    app = section(s, '五、寶藏封印 App', 'The treasure-lock app')
    sw = (W - 6 * mm) / 2
    shots = Table([[RLImage(f'{BASE}/assets/app/shot_main.jpg', width=sw, height=sw * 9 / 16),
                    RLImage(f'{BASE}/assets/app/shot_open.jpg', width=sw, height=sw * 9 / 16)],
                   [Paragraph('開鎖前：四色轉輪密碼鎖、鎖鏈和守護精靈', s['cellc']),
                    Paragraph('開鎖後：鎖鏈斷開，寶箱打開，頒發四枚徽章', s['cellc'])]],
                  colWidths=[sw + 3 * mm] * 2)
    shots.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                               ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                               ('TOPPADDING', (0, 1), (-1, 1), 3)]))
    app += [shots, Spacer(1, 6)]
    app += steps(s, [
        '<b>開啟</b>：物資包內的 <b>03_Treasure_Lock_App/Treasure_Lock_App.html</b>（單一檔案，<b>毋須上網</b>）。'
        '用 Chrome、Edge 或 Safari 開啟；電腦、平板或手機均可，橫放／直放會自動調整版面。',
        '<b>準備</b>：按右上角按鈕進入<b>全螢幕</b>，並開啟喇叭（有音效及背景音樂，右上角可靜音）。'
        '可接駁投影機，讓全團一起看。',
        '<b>開始</b>：卷軸畫面按「開始解封」，寶箱會落在祭壇上，被鎖鏈和金鎖封住。',
        '<b>輸入</b>：每隊轉動自己顏色的轉輪：點擊轉輪上／下半部、上下拖動、按 ▲▼、用滑鼠滾輪，'
        '或用鍵盤直接打數字（Enter ＝ 開鎖）。點擊守護精靈（小狼）可聽取提示。',
        '<b>開鎖</b>：密碼正確時鎖鏈斷開、寶箱打開、金幣寶石飛出，並頒發「勇氣、智慧、團結、榮譽」四枚徽章。',
        '<b>重玩</b>：長按右下角「按住重新上鎖」約 1 秒，即可重設給下一團使用。',
        '<b>更改密碼</b>：在網址最後加上 <b>?code=1234</b>；或用文字編輯器打開 HTML，'
        '把 PASSCODE 一行中的 4591 改成新密碼。'])
    story += [KeepTogether(app)]

    # 6. answer key
    ans = []
    ans += section(s, '六、答案速查', 'Answer key')
    cells = []
    for t in T.TEAMS:
        word = C.TEAM_WORDS[t['key']]
        shown = 'ONE＋空格' if word == 'ONE_' else word
        cells.append(Paragraph(f'<font name="KaiB" color="{hexc(t["dark"])}">{t["name"]}</font><br/>'
                               f'{shown} = <font name="KaiB" size="15" color="{hexc(t["dark"])}">{C.DIGIT[word]}</font>',
                               s['cellc']))
    cells.append(Paragraph('寶藏密碼<br/><font name="KaiB" size="20" color="#62180a">4591</font>',
                           ParagraphStyle('cb', parent=s['cellc'], leading=22)))
    ak = Table([cells], colWidths=[(W - 40 * mm) / 4] * 4 + [40 * mm], rowHeights=[17 * mm])
    ak.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.5, LINE), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('BACKGROUND', (-1, 0), (-1, 0), PARCH2), ('BOX', (-1, 0), (-1, 0), 1.2, TITLE)]))
    ans += [ak, Spacer(1, 8), Paragraph('<b>密碼對照表</b>（與解碼卡相同）', s['base']), Spacer(1, 3)]
    grid, row = [], []
    for L, icon, zh in C.CODE:
        lab = '空格' if L == '_' else L
        row.append([RLImage(f'{TMP}/sign_{L}.png', width=8.6 * mm, height=8.6 * mm),
                    Paragraph(f'<font name="KaiB" size="11" color="#62180a">{lab}</font> '
                              f'<font size="8.5" color="#82705c">{zh}</font>', s['cellc'])])
        if len(row) == 9:
            grid.append(row)
            row = []
    ct = Table(grid, colWidths=[W / 9] * 9)
    ct.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.5, LINE), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
    ans += [ct]
    story += [KeepTogether(ans)]

    # 7. package contents
    pkg = section(s, '七、物資包內容', 'Package contents')
    tree = [(0, f'<b>{PKG}/</b>'),
            (1, '├ 00_Leader_Guide.pdf　<font color="#82705c">本指南</font>'),
            (1, '├ <b>01_Print_Files/</b>　<font color="#82705c">列印檔（見第二部分）</font>'),
            (1, '├ <b>02_Individual_Images/</b>　<font color="#82705c">單張高解像度圖片，方便另行排版或補印</font>'),
            (2, '├ Scroll_A4.jpg　<font color="#82705c">故事卷軸</font>'),
            (2, '├ Red_Team/ · Blue_Team/ · Green_Team/ · Yellow_Team/'),
            (3, '<font color="#82705c">每隊：線索卡 ×4（Clue_Card）、符號卡 ×4（Sign_Card，檔名標明字母）、解碼卡（Decoder_Card）</font>'),
            (2, '└ Signs_A-Z_and_Blank/　<font color="#82705c">27 個透明背景符號圖（PNG）</font>'),
            (1, '└ <b>03_Treasure_Lock_App/</b>'),
            (2, '└ Treasure_Lock_App.html　<font color="#82705c">寶藏封印 App（離線使用，見第五部分）</font>')]
    pkg += [Paragraph(x, ParagraphStyle(f'tree{lv}', parent=s['tree'], leftIndent=lv * 13)) for lv, x in tree]
    pkg += [Spacer(1, 10),
            Paragraph('符號圖示：Lucide Icons（ISC 授權）　字體：霞鶩文楷 TC、Noto Serif TC、Cinzel（SIL Open Font License）'
                      '　卷軸紙紋、卡框、插圖及 App 圖像由 AI 生成；App 音效以 Web Audio 即時合成。', s['small'])]
    story += [KeepTogether(pkg)]

    doc = BaseDocTemplate(GUIDE, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=17 * mm,
                          bottomMargin=18 * mm, title='守護者的失落寶藏 · 領袖指南', author='第 82 旅幼童軍')
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='f', leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id='p', frames=[frame], onPage=deco)])
    doc.build(story)
    print('guide ok', GUIDE)


# ------------------------------------------------------------------ zip
def package_items():
    items = [(f'{PKG}/00_Leader_Guide.pdf', GUIDE)]
    for zn, src, *_ in PRINTS:
        items.append((f'{PKG}/01_Print_Files/{zn}', f'{BASE}/{src}'))
    img = f'{PKG}/02_Individual_Images'
    items.append((f'{img}/Scroll_A4.jpg', f'{BASE}/scroll_A4.jpg'))
    for t in T.TEAMS:
        key, TN = t['key'], t['key'].capitalize()
        folder = f'{img}/{TN}_Team'
        for i, c in enumerate(B.CARDS):
            items.append((f'{folder}/{TN}_Clue_Card_{i + 1}_{c["slug"].capitalize()}.jpg',
                          f'{BASE}/team_cards/{key}/{key}_card_{i + 1}_{c["slug"]}.jpg'))
        for k, L in enumerate(C.TEAM_WORDS[key]):
            lab = 'blank' if L == '_' else L
            items.append((f'{folder}/{TN}_Sign_Card_{k + 1}_{lab}.jpg', f'{BASE}/code/square_cards/{key}_{k + 1}_{lab}.jpg'))
        items.append((f'{folder}/{TN}_Decoder_Card.jpg', f'{BASE}/code/hint_card_{key}.jpg'))
    for f in sorted(os.listdir(f'{BASE}/code/signs')):
        items.append((f'{img}/Signs_A-Z_and_Blank/{f}', f'{BASE}/code/signs/{f}'))
    items.append((f'{PKG}/{APP_ZIP}', APP))
    return items


def build_zip():
    items = package_items()
    missing = [src for _, src in items if not os.path.exists(src)]
    assert not missing, f'missing (rebuild first): {missing}'
    tmp = ZIP + '.part'
    with zipfile.ZipFile(tmp, 'w') as z:
        for zn, src in items:
            ct = zipfile.ZIP_STORED if src.endswith(('.jpg', '.png')) else zipfile.ZIP_DEFLATED
            z.write(src, zn, compress_type=ct)
    os.replace(tmp, ZIP)
    with zipfile.ZipFile(ZIP) as z:
        bad = z.testzip()
        assert bad is None, bad
        n = len(z.namelist())
    print(f'zip ok  {n} files  {os.path.getsize(ZIP) / 1e6:.1f} MB  {ZIP}')
    return items


def refresh_zip():
    """update an existing package in place (after --clean the loose card images are gone):
    copy every entry of the current ZIP, swapping in the freshly built guide and app."""
    swap = {f'{PKG}/00_Leader_Guide.pdf': GUIDE, f'{PKG}/{APP_ZIP}': APP}
    tmp = ZIP + '.part'
    with zipfile.ZipFile(ZIP) as zin, zipfile.ZipFile(tmp, 'w') as zout:
        names = zin.namelist()
        assert all(k in names for k in swap), 'package layout changed - run a full build'
        for info in zin.infolist():
            if info.filename in swap:
                zout.write(swap[info.filename], info.filename, compress_type=zipfile.ZIP_DEFLATED)
            else:
                zout.writestr(info, zin.read(info.filename))
    with zipfile.ZipFile(tmp) as z:
        bad = z.testzip()
        assert bad is None, bad
        n = len(z.namelist())
    os.replace(tmp, ZIP)
    print(f'zip refreshed  {n} files  {os.path.getsize(ZIP) / 1e6:.1f} MB  {ZIP}')


def clean(items):
    """remove loose copies that now live inside the ZIP (keeps the guide, scroll and signs)."""
    keep = {GUIDE, f'{BASE}/scroll_A4.jpg', APP}
    removed = 0
    for _, src in items:
        if src in keep or '/code/signs/' in src:
            continue
        if os.path.exists(src):
            os.remove(src)
            removed += 1
    for f in NOT_PACKAGED:
        if os.path.exists(f'{BASE}/{f}'):
            os.remove(f'{BASE}/{f}')
            removed += 1
    print('cleaned', removed, 'loose files')


if __name__ == '__main__':
    build_guide()
    if '--refresh' in sys.argv:          # loose sources already cleaned: swap guide + app inside the ZIP
        refresh_zip()
        sys.exit()
    items = build_zip()
    if '--clean' in sys.argv:
        clean(items)
