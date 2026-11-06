#!/usr/bin/env python3
"""Assemble the GitHub repo  hinli2021/cubcodegame  from this workspace and (optionally) push it.

    python3 make_repo.py           # build /tmp/cubcodegame and commit
    python3 make_repo.py --push    # ...then push to GitHub
                                   #    (SSH deploy key ~/.ssh/cubcodegame_deploy,
                                   #     or HTTPS when the env var GH_TOKEN holds a token)

Repo layout
    index.html      the treasure-lock app (also the GitHub Pages home page)
    print/          leader guide + the 3 print-ready PDFs
    images/         individual card / sign images
    source/         build scripts + art, enough to regenerate everything
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = '/tmp/cubcodegame'                     # outside the workspace (snapshot size cap)
OWNER, NAME = 'hinli2021', 'cubcodegame'
PAGES_URL = f'https://{OWNER}.github.io/{NAME}/'
PKG = 'Scout82_Treasure_Hunt_Package'
ZIP = f'{BASE}/{PKG}.zip'
KEY = os.path.expanduser('~/.ssh/cubcodegame_deploy')
AUTHOR = ('hinli2021', '85391869+hinli2021@users.noreply.github.com')   # GitHub no-reply address
MESSAGE = ("Add The Guardian's Lost Treasure (守護者的失落寶藏)\n\n"
           "Cub Scout treasure hunt for Scout Group 82: treasure-lock app (index.html),\n"
           "leader guide, print-ready PDFs, individual images and the build source.")

SOURCE = ['build.py', 'build_teams.py', 'build_code.py', 'build_app.py', 'build_package.py', 'make_repo.py',
          'app/template.html',
          'assets/scroll_bg.jpg', 'assets/card_frame.jpg', 'assets/card_frame_clean.png',
          'assets/card_frame_square.png', 'assets/illus_1.jpg', 'assets/illus_2.jpg', 'assets/illus_3.jpg',
          'assets/illus_4.jpg', 'assets/icons', 'assets/app2',
          'assets/app/shot_main.jpg', 'assets/app/shot_open.jpg']

# (file, 內容, 頁數, 紙張) — mirrors build_package.PRINTS
PRINT_TABLE = [
    ('00_Leader_Guide.pdf', '領袖指南：列印清單、佈置、遊戲流程、App 用法、答案速查。⚠️ **內含答案，請勿讓隊員看到**', '4', '—'),
    ('1_Scroll_and_Team_Clue_Cards_A4.pdf', '故事卷軸（第 1 頁）＋ 4 隊線索卡（第 2–5 頁，每頁 1 隊 4 張）', '5',
     '卷軸：普通紙或米色紙；線索卡：200–250gsm 卡紙'),
    ('2_Square_Sign_Cards_A4.pdf', '神秘符號卡（每頁 1 隊 4 張；符號四印有拼圖剪線）', '4', '200–250gsm 卡紙，建議過膠'),
    ('3_Decoder_Cards_A4.pdf', '密碼翻譯提示（4 隊各 1 張，同一頁）', '1', '200–250gsm 卡紙'),
]

README = f"""# 守護者的失落寶藏 · Cub Code Game

**第 82 旅幼童軍 · 尋寶解碼遊戲**: *The Guardian's Lost Treasure*. A printable treasure hunt and code-breaking game for Cub Scouts, with an interactive treasure-lock finale.

![寶藏封印 App](source/assets/app/shot_main.jpg)

四隊幼童軍（紅、藍、綠、黃）逐張尋找線索卡、收集神秘符號卡，再用解碼卡把符號譯成英文字母，拼出各隊的數字。最後四隊合力在「寶藏封印」App 輸入四位密碼，打開寶箱！

## 🔓 寶藏封印 App：`index.html`

- **離線使用：** 下載 `index.html`，用 Chrome、Edge 或 Safari 開啟（單一檔案，毋須上網）。
- **網上版：** 開啟 GitHub Pages 後，可直接到 {PAGES_URL}
- **玩法：** 每隊轉動自己顏色的轉輪，再按「開鎖」。點擊守護精靈（小狼）可聽取提示。
- **重玩：** 長按右下角「按住重新上鎖」約 1 秒。
- **更改密碼：** 網址後加 `?code=1234`，或用文字編輯器把 `index.html` 內 `PASSCODE` 一行的數字改掉。

## 🖨️ 列印檔：`print/`

| 檔案 | 內容 | 頁數 | 紙張 |
|---|---|---|---|
""" + ''.join(f'| [`{f}`](print/{f}) | {d} | {n} | {p} |\n' for f, d, n, p in PRINT_TABLE) + """
## 🖼️ 單張圖片：`images/`

故事卷軸、各隊的線索卡／符號卡／解碼卡（`Red_Team/`、`Blue_Team/`、`Green_Team/`、`Yellow_Team/`），以及 A–Z 和空格共 27 個符號（`Signs_A-Z_and_Blank/`）。

## 🛠️ 原始碼：`source/`

用 Python 製作腳本和美術素材，可重新生成所有卡片、PDF 和 App：

```bash
pip install pillow numpy opencv-python-headless reportlab img2pdf cairosvg jieba pymupdf fonttools brotli
cd source
python3 build.py && python3 build_teams.py && python3 build_code.py   # 卷軸、線索卡、符號卡、解碼卡
python3 build_app.py                                                 # 寶藏封印 App → app/index.html
python3 build_package.py                                             # 領袖指南 + 物資包 ZIP
```

## 鳴謝 Credits

- 字型 Fonts：霞鶩文楷 TC（LXGW WenKai TC）、Noto Serif TC、Cinzel，SIL Open Font License 1.1
- 圖示 Icons：Lucide，ISC License
- 插圖 Illustrations：AI 生成 (AI-generated)
"""

GITIGNORE = '__pycache__/\n*.pyc\n.DS_Store\nThumbs.db\n'


def run(*cmd, env=None, cwd=REPO):
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def assemble():
    if os.path.exists(REPO):
        shutil.rmtree(REPO)
    os.makedirs(REPO)
    # the app (identical to the one inside the package)
    shutil.copy(f'{BASE}/app/index.html', f'{REPO}/index.html')
    # print files + individual images, taken from the package ZIP (loose copies were cleaned)
    os.makedirs(f'{REPO}/print')
    shutil.copy(f'{BASE}/00_Leader_Guide.pdf', f'{REPO}/print/00_Leader_Guide.pdf')
    with zipfile.ZipFile(ZIP) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            rel = info.filename[len(PKG) + 1:]
            if rel.startswith('01_Print_Files/'):
                dst = f'{REPO}/print/{rel.split("/", 1)[1]}'
            elif rel.startswith('02_Individual_Images/'):
                dst = f'{REPO}/images/{rel.split("/", 1)[1]}'
            else:
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'wb') as f:
                f.write(z.read(info))
    # build source
    for rel in SOURCE:
        src, dst = f'{BASE}/{rel}', f'{REPO}/source/{rel}'
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.isdir(src):
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__'))
        else:
            shutil.copy(src, dst)
    for f, _, _, _ in PRINT_TABLE:
        assert os.path.exists(f'{REPO}/print/{f}'), f'missing print/{f}'
    with open(f'{REPO}/README.md', 'w', encoding='utf-8') as f:
        f.write(README)
    with open(f'{REPO}/.gitignore', 'w') as f:
        f.write(GITIGNORE)
    open(f'{REPO}/.nojekyll', 'w').close()          # serve files as-is on GitHub Pages
    # commit
    run('git', 'init', '-q', '-b', 'main')
    run('git', 'config', 'user.name', AUTHOR[0])
    run('git', 'config', 'user.email', AUTHOR[1])
    run('git', 'add', '-A')
    run('git', 'commit', '-q', '-m', MESSAGE)
    n = subprocess.run(['git', 'ls-files'], cwd=REPO, capture_output=True, text=True).stdout.count('\n')
    size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(REPO) if '/.git' not in d for f in fs)
    head = subprocess.run(['git', 'log', '--oneline', '-1'], cwd=REPO, capture_output=True, text=True).stdout.strip()
    print(f'repo ok  {n} files  {size / 1e6:.1f} MB  {REPO}  [{head}]')


def push():
    token = os.environ.get('GH_TOKEN', '').strip()
    if token:                                       # HTTPS with a token, never written to disk
        auth = base64.b64encode(f'x-access-token:{token}'.encode()).decode()
        run('git', '-c', f'http.extraHeader=Authorization: Basic {auth}', '-c', 'http.postBuffer=524288000',
            'push', '-u', f'https://github.com/{OWNER}/{NAME}.git', 'main')
        enable_pages(token)
    else:                                           # SSH with the repo's deploy key
        os.chmod(KEY, 0o600)
        env = dict(os.environ, GIT_SSH_COMMAND=f'ssh -i {KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new')
        run('git', 'push', '-u', f'git@github.com:{OWNER}/{NAME}.git', 'main', env=env)
    print('pushed  https://github.com/' + f'{OWNER}/{NAME}')


def enable_pages(token):
    req = urllib.request.Request(f'https://api.github.com/repos/{OWNER}/{NAME}/pages', method='POST',
                                 data=json.dumps({'source': {'branch': 'main', 'path': '/'}}).encode(),
                                 headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json'})
    try:
        urllib.request.urlopen(req, timeout=30)
        print('GitHub Pages enabled ->', PAGES_URL)
    except Exception as e:                          # no Pages permission / already enabled
        print('GitHub Pages not enabled automatically:', e)


if __name__ == '__main__':
    assemble()
    if '--push' in sys.argv:
        push()
