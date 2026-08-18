#!/usr/bin/env python
"""
Dataset Annotator  (port 49145)
啟動：python app.py <dataset_path> [--dir]
"""
import sys, io, mimetypes, json, re, base64, hashlib
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import argparse
from pathlib import Path
from collections import defaultdict, OrderedDict
from flask import (Flask, request, jsonify, render_template, send_file,
                   abort, session, redirect, url_for)
from cryptography.fernet import Fernet
try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None

# ─── 啟動參數 ──────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description='Simple dataset annotator')
parser.add_argument('dataset_path', help='Path to dataset root')
parser.add_argument('--dir', action='store_true',
                    help='Label directories instead of individual files')
parser.add_argument('--debug', action='store_true',
                    help='Show debug label in UI and CLI output')
parser.add_argument('--template', type=str,
                    help='Path to JSON/YAML template configuration')
parser.add_argument('--no-login', action='store_true',
                    help='Bypass login even if password is set')
cli_args = parser.parse_args()

# ─── 常數 ──────────────────────────────────────────────────────────────
IMAGE_EXTS   = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif'}
VIDEO_EXTS   = {'.mp4', '.mov', '.avi', '.mkv'}
AUDIO_EXTS   = {'.mp3', '.wav', '.ogg'}
TEXT_EXTS    = {'.txt', '.csv', '.json', '.yaml', '.yml'}

MEDIA_FILE_EXTS  = IMAGE_EXTS | VIDEO_EXTS | AUDIO_EXTS | TEXT_EXTS
CACHE_SIZE        = 5
DIR_MODE          = cli_args.dir
DEBUG_MODE        = cli_args.debug
BYPASS_LOGIN     = cli_args.no_login
QUICK_LABEL_NAME  = 'system_label_meta_txt'
DIR_LABEL_NAME    = 'system_label_dir_meta_txt'
TEMPLATE_CONFIG   = {}
DEFAULT_ORDERING = ['meta_json', 'WD14_txt', 'caption\\d+_txt']
ORDERING_PATTERNS: list[re.Pattern] = [re.compile(p) for p in DEFAULT_ORDERING]
ANNOTATION_RULES: list[tuple[re.Pattern, dict]] = []

# ─── 讀取本地配置 ───────────────────────────────────────────────────────
CONFIG_FILE = Path('config.yaml')
CONFIG      = {}
PASSWORD    = ''
SECRET_KEY  = 'secret'
if CONFIG_FILE.exists():
    try:
        if yaml:
            CONFIG = yaml.safe_load(CONFIG_FILE.read_text()) or {}
        else:
            CONFIG = {}
            for line in CONFIG_FILE.read_text().splitlines():
                line = line.split('#', 1)[0].strip()
                if ':' in line:
                    k, v = line.split(':', 1)
                    CONFIG[k.strip()] = v.strip()
        PASSWORD   = str(CONFIG.get('password', ''))
        SECRET_KEY = str(CONFIG.get('secret_key', SECRET_KEY))
    except Exception:
        CONFIG = {}

if cli_args.template:
    try:
        text = Path(cli_args.template).read_text(encoding='utf-8')
        try:
            TEMPLATE_CONFIG = json.loads(text)
        except json.JSONDecodeError:
            if yaml:
                TEMPLATE_CONFIG = yaml.safe_load(text) or {}
            else:
                print('PyYAML not installed; YAML template unsupported', file=sys.stderr)
    except Exception as e:
        print(f'Failed to load template: {e}', file=sys.stderr)

if TEMPLATE_CONFIG:
    ORDERING_PATTERNS = [re.compile(p) for p in
                         TEMPLATE_CONFIG.get('ordering', DEFAULT_ORDERING)
                         if isinstance(p, str)]
    ann = TEMPLATE_CONFIG.get('annotations') or {}
    for pat, cfg in ann.items():
        try:
            r = re.compile(pat)
        except re.error as e:  # pragma: no cover - invalid regex
            print(f'Invalid regex {pat}: {e}', file=sys.stderr)
            continue
        rule = {
            'readonly' : cfg.get('readonly', True),
            'functions': cfg.get('functions') or []
        }
        if rule['functions'] and not rule['readonly']:
            print(f'Template error: functions require readonly for {pat}',
                  file=sys.stderr)
            rule['readonly'] = True
        ANNOTATION_RULES.append((r, rule))

# ─── Flask 與全域狀態 ───────────────────────────────────────────────────
app       = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = SECRET_KEY
DATA_ROOT = Path(cli_args.dataset_path).expanduser().resolve()
INDEX: list[dict] = []                      # [{id, media, annos}]
IMG_CACHE: OrderedDict[Path, bytes] = OrderedDict()

def resolve_data_path(relative_path: str | Path) -> Path:
    """Resolve a dataset path without allowing symlink or parent traversal."""
    if not isinstance(relative_path, (str, Path)):
        raise ValueError('Dataset path must be text')
    candidate = (DATA_ROOT / relative_path).resolve()
    try:
        candidate.relative_to(DATA_ROOT)
    except ValueError as exc:
        raise ValueError('Dataset path escapes the configured root') from exc
    return candidate

# ─── 標準加解密函式 (Fernet) ─────────────────────────────────────────────
FERNET: Fernet | None = None
PBKDF2_SALT = b"data_viewer_salt"
if PASSWORD:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=PBKDF2_SALT,
        iterations=100_000,
        backend=default_backend(),
    )
    key = base64.urlsafe_b64encode(kdf.derive(PASSWORD.encode("utf-8")))
    FERNET = Fernet(key)

def encrypt(text: str) -> str:
    if not FERNET:
        return text
    return FERNET.encrypt(text.encode("utf-8")).decode("utf-8")

def decrypt(text: str) -> str:
    if not FERNET:
        return text
    try:
        return FERNET.decrypt(text.encode("utf-8")).decode("utf-8")
    except Exception:
        return ''

# ─── 建立索引 ──────────────────────────────────────────────────────────
def build_index(root: Path, template: dict | None = None):
    """
    命名規則  
      filename = A . B  
      若  '_' not in B             →  主要媒體（原檔）  
      若  '_'  in B  (恰 1~n 個)    →  註解檔 (labeler_suffix)  
      例：image1.jpg,  image1.caption_txt,  image1._txt
    """
    groups: dict[str, list[Path]] = defaultdict(list)
    for fp in root.rglob('*'):
        if fp.is_file() and '.' in fp.name:
            rel  = fp.relative_to(root)
            base = str(rel).rsplit('.', 1)[0]
            groups[base].append(fp)

    ordering = []
    if template:
        ordering = [re.compile(p) for p in template.get('ordering', []) if isinstance(p, str)]
    elif ORDERING_PATTERNS:
        ordering = ORDERING_PATTERNS

    for data_id, files in sorted(groups.items()):
        media_candidates = []
        annos            = []

        for f in files:
            ext_str = f.name.rsplit('.', 1)[1]     # B
            if '_' in ext_str:                     # annotation
                # 取 '_' 之後最後一段做副檔名判定
                label_ext = '.' + ext_str.rsplit('_', 1)[-1].lower()
                if label_ext in TEXT_EXTS:
                    annos.append(f)
            else:                                  # potential media
                if f.suffix.lower() in MEDIA_FILE_EXTS:
                    media_candidates.append(f)

        if not media_candidates:                   # 無真媒體 → 略過
            continue

        # 優先序：IMAGE < VIDEO < AUDIO < TEXT
        prio = {**{e:0 for e in IMAGE_EXTS},
                **{e:1 for e in VIDEO_EXTS},
                **{e:2 for e in AUDIO_EXTS},
                **{e:3 for e in TEXT_EXTS}}
        media = sorted(media_candidates, key=lambda f: prio[f.suffix.lower()])[0]

        if ordering:
            def prio_ann(f: Path):
                for i, pat in enumerate(ordering):
                    if pat.fullmatch(f.name):
                        return i
                return len(ordering)
            annos.sort(key=lambda f: (prio_ann(f), f.name))

        rel_media = media.relative_to(root)
        dir_name  = rel_media.parts[0] if len(rel_media.parts) > 1 else ''

        INDEX.append({'id': data_id,
                      'media': media,
                      'annos': annos,
                      'dir'  : dir_name})

build_index(DATA_ROOT, TEMPLATE_CONFIG)
TOTAL = len(INDEX)

# 依據第一層資料夾建立索引（dir -> 首張 idx）
DIR_FIRST_IDX: dict[str, int] = {}
DIR_ORDER: list[str] = []
for i, ent in enumerate(INDEX):
    d = ent['dir']
    if d not in DIR_FIRST_IDX:
        DIR_FIRST_IDX[d] = i
        DIR_ORDER.append(d)


# ─── 快取 ──────────────────────────────────────────────────────────────
def preload(idx: int):
    for i in range(idx+1, min(idx+6, TOTAL)):
        fp = INDEX[i]['media']
        if fp.suffix.lower() in IMAGE_EXTS:
            if fp not in IMG_CACHE:
                if len(IMG_CACHE) >= CACHE_SIZE:
                    IMG_CACHE.popitem(last=False)
                IMG_CACHE[fp] = fp.read_bytes()

# ─── 認證 ─────────────────────────────────────────────────────────────
@app.before_request
def require_login():
    if not PASSWORD or BYPASS_LOGIN:
        return
    if request.path.startswith('/static') or request.endpoint in ('login', 'api_encrypt', 'api_decrypt'):
        return
    if session.get('logged_in'):
        return
    if request.path.startswith('/api'):
        return abort(401)
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if not PASSWORD or BYPASS_LOGIN:
        return redirect(url_for('home'))
    err = ''
    if request.method == 'POST':
        if request.form.get('password') == PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('home'))
        err = 'Invalid password'
    return render_template('login.html', error=err)

# ─── API ──────────────────────────────────────────────────────────────
@app.route('/')
def home():
    return render_template('index.html', total=TOTAL,
                           dir_mode=DIR_MODE, debug_mode=DEBUG_MODE,
                           template=TEMPLATE_CONFIG)

@app.route('/api/item/<int:idx>')
def api_item(idx: int):
    if idx < 0 or idx >= TOTAL:
        abort(404)
    ent = INDEX[idx]
    fp  = ent['media']
    kind = ('image' if fp.suffix.lower() in IMAGE_EXTS else
            'video' if fp.suffix.lower() in VIDEO_EXTS else
            'audio' if fp.suffix.lower() in AUDIO_EXTS else
            'text')

    annos = []
    hidden_count = 0
    for f in ent['annos']:
        try:
            txt = f.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            txt = ''

        name_part = f.name.rsplit('.', 1)[1]
        rule = None
        for pat, cfg in ANNOTATION_RULES:
            if pat.fullmatch(name_part):
                rule = cfg
                break
        if TEMPLATE_CONFIG and not rule and not f.name.endswith('.' + QUICK_LABEL_NAME):
            hidden_count += 1
            continue
        readonly = rule['readonly'] if rule else False
        funcs = []
        if rule and rule['functions']:
            ann_ext = '.' + name_part.rsplit('_', 1)[-1].lower()
            is_json = ann_ext in {'.json', '.yaml', '.yml', '.json5'}
            data_obj = None
            if is_json:
                try:
                    data_obj = json.loads(txt)
                except Exception:
                    if yaml:
                        try:
                            data_obj = yaml.safe_load(txt)
                        except Exception:
                            data_obj = None
            lines = txt.splitlines()
            for fc in rule['functions']:
                val = ''
                expr = fc.get('filter', '')
                highlight = ''
                if is_json and data_obj is not None:
                    try:
                        val = str(eval(expr, {}, {'data': data_obj}))
                    except Exception:
                        val = ''
                else:
                    for ln in lines:
                        if expr in ln:
                            val = ln
                            highlight = expr
                            break
                funcs.append({'name': fc.get('name', ''),
                              'value': val,
                              'highlight': highlight})

        annos.append({'filename': str(f.relative_to(DATA_ROOT)),
                      'content': txt,
                      'readonly': readonly,
                      'functions': funcs})

    dir_name = ent['dir']
    dir_path = DATA_ROOT / dir_name if dir_name else DATA_ROOT
    dir_label = ''
    dl_file = dir_path / DIR_LABEL_NAME
    if dl_file.exists():
        try:
            dir_label = dl_file.read_text(encoding='utf-8', errors='ignore').strip()
        except Exception:
            dir_label = ''

    dpos = DIR_ORDER.index(dir_name)
    prev_dir = DIR_ORDER[(dpos - 1) % len(DIR_ORDER)]
    next_dir = DIR_ORDER[(dpos + 1) % len(DIR_ORDER)]
    dir_prev_idx = DIR_FIRST_IDX[prev_dir]
    dir_next_idx = DIR_FIRST_IDX[next_dir]

    preload(idx)
    return jsonify({
        'idx'         : idx,
        'id'          : ent['id'],
        'media_url'   : f'/file/{fp.relative_to(DATA_ROOT)}',
        'media_kind'  : kind,
        'media_name'  : str(fp.relative_to(DATA_ROOT)),
        'annotations' : annos,
        'template'    : TEMPLATE_CONFIG,
        'dir_name'    : dir_name,
        'dir_label'   : dir_label,
        'dir_prev_idx': dir_prev_idx,
        'dir_next_idx': dir_next_idx,
        'hidden_count': hidden_count
    })

@app.route('/api/item/<int:idx>', methods=['POST'])
def api_save(idx: int):
    if idx < 0 or idx >= TOTAL:
        abort(404)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        abort(400)
    ent     = INDEX[idx]

    # 1. annotation 協定儲存
    for row in payload.get('annotations', []):
        try:
            path = resolve_data_path(row['filename'])
            content = row['content']
            if not isinstance(content, str):
                raise ValueError('Annotation content must be text')
        except (KeyError, TypeError, ValueError):
            abort(400)
        path.write_text(content, encoding='utf-8')
        if path not in ent['annos']:
            ent['annos'].append(path)

    # 2. 快速標籤
    quick = (payload.get('quick_label') or '').strip()
    if quick:
        if DIR_MODE:
            dpath = DATA_ROOT / (ent['dir'] or '')
            qpath = dpath / DIR_LABEL_NAME
            qpath.write_text(quick + '\n', encoding='utf-8')
        else:
            qpath = DATA_ROOT / f'{ent["id"]}.{QUICK_LABEL_NAME}'
            qpath.write_text(quick + '\n', encoding='utf-8')
            if qpath not in ent['annos']:
                ent['annos'].append(qpath)

    return jsonify({'status': 'ok'})

@app.route('/api/encrypt', methods=['POST'])
def api_encrypt():
    data = request.get_json(force=True)
    txt = data.get('text', '')
    return jsonify({'result': encrypt(txt)})

@app.route('/api/decrypt', methods=['POST'])
def api_decrypt():
    data = request.get_json(force=True)
    txt = data.get('text', '')
    return jsonify({'result': decrypt(txt)})

@app.route('/file/<path:fname>')
def serve_file(fname):
    try:
        fp = resolve_data_path(fname)
    except ValueError:
        abort(404)
    if not fp.is_file():
        abort(404)
    if fp in IMG_CACHE:
        return send_file(io.BytesIO(IMG_CACHE[fp]),
                         mimetype=mimetypes.guess_type(fp)[0] or 'application/octet-stream')
    return send_file(fp)

if __name__ == '__main__':
    print(f'📂 Dataset: {DATA_ROOT}')
    print(f'🔢 Total  : {TOTAL} items')
    if DIR_MODE:
        print('📁 DIRECTORY MODE')
    if DEBUG_MODE:
        print('🛠 DEBUG MODE')
    app.run(host='0.0.0.0', port=49145, threaded=True)
