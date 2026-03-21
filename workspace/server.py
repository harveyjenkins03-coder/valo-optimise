from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_socketio import SocketIO, emit, disconnect
import os, json, datetime, hashlib, time, secrets

# ── Config loading ────────────────────────────────────────────────────────────
_CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'workspace.cfg')

def _load_cfg():
    cfg = {}
    try:
        with open(_CFG_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    k, _, v = line.partition('=')
                    cfg[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return cfg

_cfg = _load_cfg()
_PASSWORD = _cfg.get('PASSWORD', 'valo2024')
_SESSION_SECRET = _cfg.get('SESSION_SECRET', secrets.token_hex(32))

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = _SESSION_SECRET
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOWED_EXT = {'.py', '.md', '.txt', '.json', '.bat', '.gitignore', '.cfg', '.ini'}
online_users = {}  # sid -> {name, color, file}
COLORS = ["#ff4655", "#00d4aa", "#ffd700", "#5ba3f5", "#ff9f43"]

# ── Rate limiting ─────────────────────────────────────────────────────────────
# { ip: {'count': int, 'locked_until': float} }
_login_attempts = {}
_MAX_ATTEMPTS = 5
_LOCKOUT_SECONDS = 60


def _make_hash(pwd):
    import hashlib
    return hashlib.sha256(pwd.encode()).hexdigest()


def _check_rate_limit(ip):
    """Return (allowed: bool, seconds_remaining: int)."""
    now = time.time()
    rec = _login_attempts.get(ip)
    if rec is None:
        return True, 0
    if rec.get('locked_until', 0) > now:
        remaining = int(rec['locked_until'] - now) + 1
        return False, remaining
    # Lockout expired — reset
    if rec.get('locked_until', 0) and rec['locked_until'] <= now:
        _login_attempts[ip] = {'count': 0, 'locked_until': 0}
    return True, 0


def _record_failure(ip):
    now = time.time()
    rec = _login_attempts.setdefault(ip, {'count': 0, 'locked_until': 0})
    rec['count'] += 1
    if rec['count'] >= _MAX_ATTEMPTS:
        rec['locked_until'] = now + _LOCKOUT_SECONDS


def _clear_failures(ip):
    _login_attempts.pop(ip, None)


# ── Auth helpers ──────────────────────────────────────────────────────────────
def _authed():
    return session.get('authed') is True


def _require_auth():
    """Return a redirect response if not authenticated, else None."""
    if not _authed():
        return redirect(url_for('login'))
    return None


# ── File tree ─────────────────────────────────────────────────────────────────
def get_file_tree(root):
    """Return nested dict of project files (skip hidden, __pycache__, workspace/)"""
    tree = []
    skip_dirs = {'__pycache__', '.git', 'workspace', 'notion_import', 'backups'}
    try:
        items = sorted(os.listdir(root))
    except PermissionError:
        return tree
    for item in items:
        full = os.path.join(root, item)
        if item.startswith('.') and item not in {'.gitignore'}:
            continue
        if os.path.isdir(full):
            if item in skip_dirs:
                continue
            children = get_file_tree(full)
            if children:
                tree.append({'name': item, 'type': 'dir', 'children': children})
        else:
            ext = os.path.splitext(item)[1].lower()
            if ext in ALLOWED_EXT:
                tree.append({
                    'name': item,
                    'type': 'file',
                    'path': os.path.relpath(full, PROJECT_ROOT).replace('\\', '/')
                })
    return tree


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    guard = _require_auth()
    if guard:
        return guard
    return render_template('index.html')


@app.route('/login', methods=['GET'])
def login():
    if _authed():
        return redirect(url_for('index'))
    return render_template('login.html', error=None)


@app.route('/login', methods=['POST'])
def login_post():
    ip = request.remote_addr or '0.0.0.0'
    allowed, wait = _check_rate_limit(ip)
    if not allowed:
        return render_template('login.html',
                               error=f'Too many failed attempts. Try again in {wait}s.'), 429

    submitted = request.form.get('password', '')
    if _make_hash(submitted) == _make_hash(_PASSWORD):
        _clear_failures(ip)
        session.clear()
        session['authed'] = True
        return redirect(url_for('index'))
    else:
        _record_failure(ip)
        allowed2, wait2 = _check_rate_limit(ip)
        if not allowed2:
            msg = f'Too many failed attempts. Locked out for {wait2}s.'
        else:
            remaining = _MAX_ATTEMPTS - _login_attempts.get(ip, {}).get('count', 0)
            msg = f'Incorrect password. {remaining} attempt(s) remaining.'
        return render_template('login.html', error=msg), 401


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/api/files')
def api_files():
    guard = _require_auth()
    if guard:
        return guard
    return jsonify(get_file_tree(PROJECT_ROOT))


@app.route('/api/file')
def api_read():
    guard = _require_auth()
    if guard:
        return guard
    rel = request.args.get('path', '')
    full = os.path.normpath(os.path.join(PROJECT_ROOT, rel))
    if not os.path.normcase(full).startswith(os.path.normcase(PROJECT_ROOT)):
        return jsonify({'error': 'forbidden'}), 403
    try:
        with open(full, 'r', encoding='utf-8', errors='replace') as f:
            return jsonify({'content': f.read(), 'path': rel})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/file', methods=['POST'])
def api_write():
    guard = _require_auth()
    if guard:
        return guard
    data = request.json
    rel = data.get('path', '')
    content = data.get('content', '')
    full = os.path.normpath(os.path.join(PROJECT_ROOT, rel))
    if not os.path.normcase(full).startswith(os.path.normcase(PROJECT_ROOT)):
        return jsonify({'error': 'forbidden'}), 403
    ext = os.path.splitext(full)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({'error': 'file type not allowed'}), 403
    try:
        with open(full, 'w', encoding='utf-8') as f:
            f.write(content)
        socketio.emit('file_saved', {
            'path': rel,
            'by': data.get('user', 'Unknown')
        })
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Socket events ─────────────────────────────────────────────────────────────
@socketio.on('connect')
def on_connect():
    if not session.get('authed'):
        return False  # disconnect unauthenticated clients


@socketio.on('join')
def on_join(data):
    name = data.get('name', 'Dev')
    color = COLORS[len(online_users) % len(COLORS)]
    online_users[request.sid] = {'name': name, 'color': color, 'file': None}
    emit('users_update', list(online_users.values()), broadcast=True)
    emit('chat_message', {
        'user': 'System',
        'msg': f'{name} joined the workspace',
        'color': '#6b7a99',
        'time': _ts()
    }, broadcast=True)


@socketio.on('disconnect')
def on_disconnect():
    user = online_users.pop(request.sid, {})
    if user:
        emit('users_update', list(online_users.values()), broadcast=True)
        emit('chat_message', {
            'user': 'System',
            'msg': f"{user['name']} left",
            'color': '#6b7a99',
            'time': _ts()
        }, broadcast=True)


@socketio.on('viewing_file')
def on_viewing(data):
    if request.sid in online_users:
        online_users[request.sid]['file'] = data.get('path')
    emit('users_update', list(online_users.values()), broadcast=True)


@socketio.on('chat')
def on_chat(data):
    user = online_users.get(request.sid, {})
    emit('chat_message', {
        'user': user.get('name', '?'),
        'msg': data.get('msg', ''),
        'color': user.get('color', '#fff'),
        'time': _ts()
    }, broadcast=True)


def _ts():
    return datetime.datetime.now().strftime('%H:%M')


if __name__ == '__main__':
    print(f"\n  VALO OPTIMISE WORKSPACE")
    print(f"  Running at: http://localhost:8080")
    print(f"  Project: {PROJECT_ROOT}\n")
    socketio.run(app, host='0.0.0.0', port=8080, debug=False, allow_unsafe_werkzeug=True)
