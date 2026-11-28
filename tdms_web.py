"""
TDMS WEB  -  the same document system, in the browser, for the whole team.

Run:    python tdms_web.py        (or Run_Server.bat)
Open:   http://<this-computer's-IP>:8080   from any computer on the network
Needs:  pip install flask pillow          (optional: waitress = faster server, pymupdf = PDF thumbnails)
Data:   the folder AFS_TDMS_Data next to this file (same data as the desktop program)
"""
import base64
import datetime as dt
import io
import json
import mimetypes
import os
import re
import secrets
import socket
import sys
import tempfile
import threading
import time
from functools import wraps
from pathlib import Path

import requests
from flask import Flask, Response, jsonify, request, send_file, send_from_directory, session

import tdms_core as core
import tdms_graphics as g

try:
    import fitz     # PyMuPDF (optional: PDF thumbnails)
except Exception:
    fitz = None

BASE = core.BASE
WEB = BASE / "web"
CONFIG_FILE = core.ROOT / "web_config.json"
VIEW_MAP = {"uploads": "My uploads", "folder": "Selected folder", "all": "All documents", "favorites": "My favorites", "mine": "Added by me", "recent": "Recent (last 30 days)", "bin": "Recycle bin"}
SORT_KEYS = {"pos", "title", "type", "size", "added", "by", "cat", "status"}
PREF_KEYS = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
INLINE_OK = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
             ".mp4": "video/mp4", ".m4v": "video/mp4", ".webm": "video/webm", ".mov": "video/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg", ".m4a": "audio/mp4",
             ".aac": "audio/aac", ".txt": "text/plain; charset=utf-8", ".log": "text/plain; charset=utf-8", ".md": "text/plain; charset=utf-8", ".json": "text/plain; charset=utf-8",
             ".xml": "text/plain; charset=utf-8", ".csv": "text/plain; charset=utf-8"}
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
S = None                       # settings (created in create_app)

# ---- SharePoint (Power Automate flow): a copy of every approved document is sent to SharePoint
FLOW_URL = os.environ.get("TDMS_SHAREPOINT_FLOW_URL") or "https://default9d0bf1ed9dbb4ad2b95eefaf178699.37.environment.api.powerplatform.com:443/powerautomate/automations/direct/cu/29/workflows/81de89cdb6e546d9b4f348d7d655f3aa/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=ysPgU2hmogGpbmARhzS4B_IfhZkTNPFaqa-jvAU34HU"

def upload_to_sharepoint(path, folder_path):
    with open(path, "rb") as f:
        content = base64.b64encode(f.read()).decode()

    payload = {
        "filename": path.name,
        "folder": folder_path,
        "filecontent": content
    }

    r = requests.post(FLOW_URL, json=payload, timeout=300)

    if r.status_code not in (200, 201, 202):
        raise Exception(f"SharePoint upload failed (HTTP {r.status_code}): {r.text[:200]}")

    try:
        return r.json()
    except ValueError:
        return {}

_FAILS, _FLOCK = {}, threading.Lock()
_OFFICE_LOCK = threading.Lock()


class ApiError(Exception):
    def __init__(self, msg, code=400):
        super().__init__(msg)
        self.code = code


def load_config():
    cfg = {"host": "0.0.0.0", "port": 8080, "behind_proxy": False}
    try:
        if CONFIG_FILE.exists():
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        else:
            CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception:
        pass
    return cfg


def jerr(msg, code=400):
    r = jsonify({"error": msg})
    r.status_code = code
    return r


def body():
    return request.get_json(force=True, silent=True) or {}


def client_ip():
    return request.remote_addr or "?"


def too_many(ip, limit=8):
    with _FLOCK:
        items = [t for t in _FAILS.get(ip, []) if time.time() - t < 600]
        _FAILS[ip] = items
        return len(items) >= limit


def note_fail(ip):
    with _FLOCK:
        _FAILS.setdefault(ip, []).append(time.time())


_TOUCH = {}


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    r = core.q("select * from users where id=? and active=1 and pending=0", (uid,))
    if not r:
        return None
    sid = session.get("sid")
    if sid:
        if not core.session_ok(sid):                      # an admin ended this session, or it was signed out
            return None
        t = time.time()
        if t - _TOUCH.get(sid, 0) > 30:
            _TOUCH[sid] = t
            core.session_touch(sid)
    return r[0]


ROLES = ("user", "viewer", "admin")
# every option the admin can change (Admin > Notifications / Upload window / Audit trail). Values are "1" / "0" or text.
FEATURES = {"notif_enabled": "1", "notif_popup": "1", "notif_docs": "1", "notif_folders": "1", "notif_versions": "1", "notif_own": "0", "notif_role_admin": "1", "notif_role_user": "1", "notif_role_viewer": "1", "notif_retention": "30",
            "ud_enabled": "1", "ud_newfolder": "1", "ud_version": "1", "ud_desc": "1", "ud_tags": "1", "ud_status": "1", "ud_review": "0", "ud_comment": "1", "ud_req_desc": "0", "ud_req_version": "0", "ud_default_version": "1.0",
            "name_format": "title", "name_acronyms": "PLC,HMI,SOP,ICD,IO,FAT,SAT,AMR,AGV,RGV,ASRS,WMS,WCS,SCADA,VFD,BOM,ISO,PDF,CAD",
            "log_ip": "1", "log_device": "1", "log_access": "1", "log_retention": "0"}
NUMERIC_FEATURES = {"notif_retention", "log_retention"}
TEXT_FEATURES = {"ud_default_version", "name_format", "name_acronyms"}


def feat(k):
    v = S.get(k)
    if v == "-":                      # the admin cleared the text on purpose
        return ""
    return v if v != "" else FEATURES[k]


def on(k):
    return feat(k) == "1"


def features_payload():
    return {k: feat(k) for k in FEATURES}


def acronyms():
    return [a.strip() for a in feat("name_acronyms").split(",") if a.strip()]


def device_of(ua):
    """'Chrome on Windows' from a browser identification string"""
    ua = ua or ""
    if not ua:
        return ""
    b = "Edge" if "Edg/" in ua else "Opera" if "OPR/" in ua else "Chrome" if ("Chrome/" in ua or "CriOS" in ua) else "Firefox" if "Firefox/" in ua else "Safari" if "Safari/" in ua else "Browser"
    o = "Windows" if "Windows" in ua else "Android" if "Android" in ua else "iPhone / iPad" if ("iPhone" in ua or "iPad" in ua) else "Mac" if "Macintosh" in ua else "Linux" if "Linux" in ua else ""
    return f"{b} on {o}" if o else b


def is_viewer(u):
    return u["role"] == "viewer"


def dd(r, u):
    """a document as JSON for this person (viewers can never edit)"""
    d = core.doc_dict(r, u["id"], is_admin(u))
    if is_viewer(u):
        d["can_edit"] = False
    return d


def api(admin=False, auth=True, write=False):
    """Every JSON route: signed-in check, admin check, viewer (read-only) check, and a header that other websites cannot add (CSRF)."""
    def deco(fn):
        @wraps(fn)
        def wrap(*a, **k):
            if request.method not in ("GET", "HEAD") and request.headers.get("X-Requested-With") != "tdms":
                return jerr("Blocked request.", 403)
            u = current_user() if auth else None
            if auth and not u:
                return jerr("Please sign in.", 401)
            if admin and u["role"] != "admin":
                return jerr("Administrators only.", 403)
            if write and u["role"] == "viewer":
                return jerr("Viewer accounts can read and download documents, but cannot change anything.", 403)
            try:
                return fn(u, *a, **k)
            except ApiError as e:
                return jerr(str(e), e.code)
        return wrap
    return deco


def ids_of(d, limit=2000):
    try:
        ids = [int(i) for i in (d.get("ids") or [])][:limit]
    except (TypeError, ValueError):
        raise ApiError("Bad list of documents.")
    return ids


def is_admin(u):
    return u["role"] == "admin"


def brand():
    return {"app_name": S.get("app_name"), "short_name": S.get("short_name"), "company": S.get("company"), "subtitle": S.get("subtitle"), "tagline": S.get("tagline"),
            "red": S.get("brand_red"), "blue": S.get("brand_blue"), "navy": S.get("brand_navy"), "login_bg": S.get("login_bg") or "ocean", "allow_signup": S.flag("allow_signup"),
            "email_domain": S.get("email_domain"), "min_password": int(S.get("min_password") or 8), "require_approval": S.flag("require_approval"), "default_role": S.get("default_role") if S.get("default_role") in ("user", "viewer") else "user", "upload_approval": S.get("upload_approval") != "0"}


def type_table():
    t = {k: {"label": v[0], "color": v[2], "text": core.ICON_TEXT.get(k, "FILE")} for k, v in core.FT.items()}
    t["file"] = {"label": core.FT_OTHER[0], "color": core.FT_OTHER[1], "text": "FILE"}
    return t


def me_payload(u):
    return {"user": core.user_dict(u), "prefs": core.prefs_of(u["id"]), "brand": brand(), "version": core.VERSION, "types": type_table(),
            "must_change": bool(is_admin(u) and core.checkpw("admin123", u["pw"])), "needs_question": not u["question"], "exact_ok": os.name == "nt", "roles": list(ROLES), "idle_minutes": float(S.get("idle_minutes") or 60), "features": features_payload(), "statuses": core.STATUSES,
            "status_colors": core.STATUS_COLORS, "chips": list(core.TYPE_CHIPS), "orders": {k: list(v) for k, v in core.ORDERS.items()}, "questions": core.QUESTIONS}


def needs_approval(u):
    """uploads by normal users wait for an administrator (can be switched off in Admin > Rules)"""
    return u["role"] == "user" and S.get("upload_approval") != "0"


def notify(kind, u, doc=None, cat=None, title="", detail=""):
    """Tell everybody what was added (shown as a popup and in the bell list). Pending uploads are NOT announced until they are approved."""
    if on("notif_enabled"):
        core.add_event(kind, u, doc, cat, title, detail)


def ensure_cat(parent, name, u):
    """find or create a folder; a NEW folder is announced"""
    name = (name or "").strip()[:120] or "Folder"
    found = core.q("select id from categories where parent_id is ? and name=?", (parent, name))
    if found:
        return found[0]["id"]
    cid = core.get_or_make_cat(parent, name)
    path = "/".join(c["name"] for c in [core.q("select name from categories where id=?", (x,))[0] for x in ([cid] if not parent else [parent, cid])])
    notify("folder_created", u, None, cid, name, f"inside {path.rsplit('/', 1)[0]}" if parent else "top level")
    core.log(u["username"], "add folder (web)", name, ref=None)
    return cid


def allowed_kinds(u):
    if not on("notif_enabled") or not on(f"notif_role_{u['role']}"):
        return []
    return [k for k, f in (("doc_added", "notif_docs"), ("folder_created", "notif_folders"), ("doc_version", "notif_versions")) if on(f)]


def apply_upload_meta(did, u, m):
    """details typed in the Add window: version label, description, tags, status, review date, first comment (only the parts the admin switched on)"""
    sets, vals = [], []
    if on("ud_enabled"):
        if on("ud_version") and m.get("version"):
            sets.append("vlabel=?"); vals.append(m["version"][:40])
        if on("ud_desc") and m.get("descr"):
            sets.append("descr=?"); vals.append(m["descr"][:2000])
        if on("ud_tags") and m.get("tags"):
            sets.append("tags=?"); vals.append(m["tags"][:300])
        if on("ud_status") and m.get("status") in core.STATUSES[1:]:
            sets.append("status=?"); vals.append(m["status"])
        if on("ud_review") and m.get("review") and core.valid_date(m["review"]):
            sets.append("review=?"); vals.append(m["review"])
    if sets:
        core.ex(f"update docs set {', '.join(sets)} where id=?", (*vals, did))
    if on("ud_enabled") and on("ud_comment") and (m.get("comment") or "").strip():
        core.add_comment(did, u["id"], m["comment"])


def check_upload_meta(m):
    if on("ud_enabled"):
        if on("ud_req_version") and on("ud_version") and not (m.get("version") or "").strip():
            raise ApiError("Please type the version.")
        if on("ud_req_desc") and on("ud_desc") and not (m.get("descr") or "").strip():
            raise ApiError("Please type a short description.")
        if m.get("review") and not core.valid_date(m["review"]):
            raise ApiError("The review date must look like 2026-12-31.")


def final_title(raw_title, filename):
    base = (raw_title or "").strip() or Path(filename).stem
    return core.format_title(base, feat("name_format"), acronyms()) or None


def get_doc_or_404(did, u, allow_deleted=False):
    d = core.get_doc(did)
    if not d:
        raise ApiError("Document not found.", 404)
    st = d["deleted"] or 0
    if st in (2, 3):                                  # waiting for approval / rejected: only the person who added it, and admins
        if not (is_admin(u) or d["uploader_id"] == u["id"]):
            raise ApiError("Document not found.", 404)
    elif st == 1 and (not allow_deleted or not (is_admin(u) or d["uploader_id"] == u["id"])):
        raise ApiError("Document not found.", 404)
    return d


def need_edit(d, u):
    if not (is_admin(u) or d["uploader_id"] == u["id"]):
        raise ApiError("Only an admin or the person who added it can change this document.", 403)


def doc_json(d, u):
    r = core.get_doc(d["id"]) if not isinstance(d, dict) and "fav" not in d.keys() else d
    return dd(r, u)


def fav_aware(did, u):
    r = core.q(core.DOC_SQL + " where d.id=?", (u["id"], did))
    return dd(r[0], u) if r else None


def type_colors_of(uid):
    return {k[3:]: v for k, v in core.prefs_of(uid).items() if k.startswith("fc_") and core.is_hex(v)}


def palette(theme):
    if theme == "dark":
        return dict(bg="#1B2636", ink="#E8EEF7", muted="#8FA0B8", grid="#2C3A50", track="#2C3A50")
    return dict(bg="#FFFFFF", ink="#1E2A38", muted="#6B7785", grid="#E3E8EF", track="#E3E8EF")


def png(img, max_age=0):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    r = Response(buf.getvalue(), mimetype="image/png")
    r.headers["Cache-Control"] = f"private, max-age={max_age}" if max_age else "no-store"
    return r


def local_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        ips.update(i for i in socket.gethostbyname_ex(socket.gethostname())[2] if not i.startswith("127."))
    except Exception:
        pass
    return sorted(ips)


def create_app():
    global S
    core.init()
    S = core.Settings()
    cfg = load_config()
    app = Flask(__name__, static_folder=str(WEB), static_url_path="/static")
    key_file = core.ROOT / "web_secret.key"
    if not key_file.exists():
        key_file.write_text(secrets.token_hex(32))
    app.secret_key = key_file.read_text().strip()
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_NAME="tdms_session", PERMANENT_SESSION_LIFETIME=dt.timedelta(hours=12),
                      JSON_SORT_KEYS=False, MAX_CONTENT_LENGTH=None)
    from werkzeug.middleware.proxy_fix import ProxyFix
    from flask.sessions import SecureCookieSessionInterface

    class LocalProxyFix:
        """Believe X-Forwarded-* headers only when they come from THIS computer (cloudflared / tailscale), never from the internet."""
        def __init__(self, inner):
            self.inner, self.fix = inner, ProxyFix(inner, x_for=1, x_proto=1, x_host=1)

        def __call__(self, environ, start_response):
            if cfg.get("behind_proxy") or environ.get("REMOTE_ADDR") in ("127.0.0.1", "::1"):
                return self.fix(environ, start_response)
            return self.inner(environ, start_response)
    app.wsgi_app = LocalProxyFix(app.wsgi_app)

    class DynamicSession(SecureCookieSessionInterface):
        def get_cookie_secure(self, app_):
            return request.is_secure          # https (tunnel) -> Secure cookie; plain http inside the office -> normal cookie
    app.session_interface = DynamicSession()

    @app.before_request
    def audit_context():
        """Every log line remembers who did it (id), from which address, with which device and in which session."""
        core.set_ctx(session.get("uid"), client_ip() if on("log_ip") else "", request.headers.get("User-Agent", "") if on("log_device") else "", session.get("sid", ""))

    @app.after_request
    def headers(r):
        r.headers["X-Content-Type-Options"] = "nosniff"
        r.headers["Referrer-Policy"] = "same-origin"
        r.headers["X-Frame-Options"] = "SAMEORIGIN"
        if r.mimetype == "text/html":
            r.headers["Cache-Control"] = "no-store"
            r.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; frame-src 'self'; media-src 'self' blob:; object-src 'self'; base-uri 'self'; form-action 'self'"
        return r

    # ------------------------------------------------------------------ pages
    @app.get("/")
    def index():
        return send_from_directory(WEB, "index.html")

    @app.get("/sw.js")
    def service_worker():
        r = send_from_directory(WEB, "sw.js", mimetype="application/javascript")
        r.headers["Cache-Control"] = "no-cache"
        r.headers["Service-Worker-Allowed"] = "/"
        return r

    @app.get("/manifest.webmanifest")
    def manifest():
        b = brand()
        r = jsonify({"name": b["app_name"], "short_name": b["short_name"] or b["app_name"], "description": b["subtitle"], "start_url": "/", "scope": "/", "display": "standalone", "background_color": "#F3F6FA", "theme_color": b["navy"],
                     "icons": [{"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}]})
        r.mimetype = "application/manifest+json"
        return r

    @app.get("/favicon.ico")
    def favicon():
        p = BASE / "app_icon.ico"
        return send_file(p, mimetype="image/x-icon", max_age=86400) if p.exists() else ("", 404)

    @app.get("/api/ping")
    def ping():
        return jsonify({"ok": True, "version": core.VERSION})

    @app.get("/api/brand")
    @api(auth=False)
    def brand_public(_):
        return jsonify({**brand(), "questions": core.QUESTIONS})

    @app.get("/brand/logo.png")
    def brand_logo():
        p = g.find_logo(core.ROOT, BASE)
        return send_file(p, mimetype="image/png", max_age=300) if p else ("", 404)

    @app.get("/brand/hero.png")
    def brand_hero():
        from PIL import Image
        w, h = min(1200, int(request.args.get("w", 520))), min(1600, int(request.args.get("h", 700)))
        lp = g.find_logo(core.ROOT, BASE)
        logo = Image.open(lp).convert("RGBA") if lp else None
        b = brand()
        hero = g.hero_panel(w, h, g.mix(b["navy"], "#000000", 0.25), b["blue"], b["red"], b["app_name"], b["subtitle"],
                            ["Folders arranged your way", "PDF, Word, Excel, PowerPoint in the browser", "Drag and drop files in and out", "One place for the whole team"], short=b["short_name"], logo=logo)
        return png(hero.convert("RGB"), 300)

    @app.get("/brand/bg.png")
    def brand_bg():
        w, h = min(2400, int(request.args.get("w", 1280))), min(1600, int(request.args.get("h", 720)))
        b = brand()
        return png(g.login_background(w, h, b["login_bg"], accent=b["red"], blue=b["blue"], navy=b["navy"]), 300)

    # ------------------------------------------------------------------ sign in / account
    @app.post("/api/login")
    @api(auth=False)
    def login(_):
        d = body()
        ip, login_id = client_ip(), str(d.get("login", "")).strip()
        acct = "u:" + login_id.lower()
        if too_many(ip) or too_many(acct, 10):
            raise ApiError("Too many attempts. Please wait a few minutes.", 429)
        u = core.check_login(login_id, str(d.get("password", "")))
        if not u:
            note_fail(ip)
            note_fail(acct)
            core.log(login_id[:60], "failed login (web)", ip)
            raise ApiError("Wrong email ID or password.", 401)
        if u["pending"]:
            raise ApiError("Your account is waiting for admin approval.", 403)
        if not u["active"]:
            raise ApiError("This account is disabled. Ask your admin.", 403)
        mode = d.get("mode", "user")
        if mode == "admin" and u["role"] != "admin":
            raise ApiError("This account is not an administrator. Use the User tab.", 403)
        if mode == "user" and u["role"] == "admin":
            raise ApiError("Administrators sign in on the Administrator tab.", 403)
        session.clear()
        session["uid"] = u["id"]
        session["sid"] = secrets.token_hex(16)
        session.permanent = True
        ua = request.headers.get("User-Agent", "")
        core.session_start(session["sid"], u, ip if on("log_ip") else "", ua if on("log_device") else "")
        core.set_ctx(u["id"], ip if on("log_ip") else "", ua if on("log_device") else "", session["sid"])
        core.log(u["username"], "login (web)", ip)
        return jsonify(me_payload(u))

    @app.post("/api/logout")
    @api(auth=False)
    def logout(_):
        u = current_user()
        if u:
            core.log(u["username"], "logout (web)")
        if session.get("sid"):
            core.session_end(session["sid"])
        session.clear()
        return jsonify({"ok": True})

    @app.get("/api/me")
    @api()
    def me(u):
        return jsonify(me_payload(u))

    @app.post("/api/prefs")
    @api()
    def prefs_save(u):
        n = 0
        for k, v in body().items():
            if PREF_KEYS.match(str(k)) and len(str(v)) <= 300:
                core.set_pref(u["id"], k, v)
                n += 1
        return jsonify({"ok": True, "saved": n})

    @app.post("/api/register")
    @api(auth=False)
    def register(_):
        d = body()
        if not S.flag("allow_signup"):
            raise ApiError("Self sign-up is switched off. Ask your admin for an account.", 403)
        e, name, pw = str(d.get("email", "")).strip().lower(), str(d.get("name", "")).strip(), str(d.get("password", ""))
        dom = S.get("email_domain").strip().lstrip("@").lower()
        minlen = int(S.get("min_password") or 8)
        if not name or not str(d.get("answer", "")).strip():
            raise ApiError("Please fill in your name and the security answer.")
        if not core.EMAIL_RE.fullmatch(e):
            raise ApiError("Please enter a valid email ID, for example name@company.com.")
        if dom and not e.endswith("@" + dom):
            raise ApiError(f"Please use your company email (@{dom}).")
        if core.q("select 1 from users where username=? or lower(email)=?", (e, e)):
            raise ApiError("That email ID is already registered.")
        err = core.pw_error(pw, pw, minlen)
        if err:
            raise ApiError(err)
        if d.get("question") not in core.QUESTIONS:
            raise ApiError("Choose a security question.")
        appr = S.flag("require_approval")
        core.ex("insert into users(username,name,pw,role,active,pending,question,answer,emp_id,dept,email,created) values(?,?,?,?,?,?,?,?,?,?,?,?)",
                (e, name, core.hashpw(pw), S.get("default_role") if S.get("default_role") in ("user", "viewer") else "user", 0 if appr else 1, 1 if appr else 0, d["question"], core.hashpw(str(d["answer"]).strip().lower()), str(d.get("emp_id", "")).strip()[:40],
                 str(d.get("dept", "")).strip()[:60], e, core.now()))
        core.log(e, "account requested (web)" if appr else "account created (web)")
        return jsonify({"ok": True, "pending": appr})

    @app.post("/api/recover/question")
    @api(auth=False)
    def recover_q(_):
        key = str(body().get("id", "")).strip().lower()
        if too_many(client_ip()):
            raise ApiError("Too many attempts. Please wait a few minutes.", 429)
        r = core.q("select * from users where (username=? or lower(email)=? or lower(emp_id)=?) and active=1", (key, key, key)) if key else []
        if not r or not r[0]["question"]:
            note_fail(client_ip())
            raise ApiError("No account with a security question was found. Ask your admin to reset your password.", 404)
        return jsonify({"question": r[0]["question"]})

    @app.post("/api/recover/verify")
    @api(auth=False)
    def recover_v(_):
        d = body()
        key, minlen = str(d.get("id", "")).strip().lower(), int(S.get("min_password") or 8)
        if too_many(client_ip()):
            raise ApiError("Too many attempts. Please wait a few minutes.", 429)
        r = core.q("select * from users where (username=? or lower(email)=? or lower(emp_id)=?) and active=1", (key, key, key)) if key else []
        if not r or not r[0]["question"] or not core.checkpw(str(d.get("answer", "")).strip().lower(), r[0]["answer"] or ""):
            note_fail(client_ip())
            core.log(key[:60], "failed recovery (web)")
            raise ApiError("That answer is not correct.", 403)
        npw = str(d.get("new_password", ""))
        if npw:
            err = core.pw_error(npw, npw, minlen)
            if err:
                raise ApiError(err)
            core.ex("update users set pw=? where id=?", (core.hashpw(npw), r[0]["id"]))
            core.log(r[0]["username"], "password reset by question (web)")
        return jsonify({"username": r[0]["username"], "changed": bool(npw)})

    @app.post("/api/password")
    @api()
    def change_password(u):
        d, minlen = body(), int(S.get("min_password") or 8)
        if not core.checkpw(str(d.get("current", "")), u["pw"]):
            raise ApiError("Your current password is wrong.", 403)
        err = core.pw_error(str(d.get("new", "")), str(d.get("new", "")), minlen)
        if err:
            raise ApiError(err)
        core.ex("update users set pw=? where id=?", (core.hashpw(d["new"]), u["id"]))
        core.log(u["username"], "password changed (web)")
        return jsonify({"ok": True})

    @app.post("/api/question")
    @api()
    def set_question(u):
        d = body()
        if not core.checkpw(str(d.get("password", "")), u["pw"]):
            raise ApiError("Your password is wrong.", 403)
        if d.get("question") not in core.QUESTIONS or not str(d.get("answer", "")).strip():
            raise ApiError("Choose a question and type the answer.")
        core.ex("update users set question=?, answer=? where id=?", (d["question"], core.hashpw(str(d["answer"]).strip().lower()), u["id"]))
        return jsonify({"ok": True})

    # ------------------------------------------------------------------ profile, photos, users
    def load_user(uid):
        r = core.q("select * from users where id=?", (uid,))
        if not r:
            raise ApiError("User not found.", 404)
        return r[0]

    @app.get("/api/users")
    @api(admin=True)
    def users_list(u):
        ll = core.last_logins()
        out = []
        for r in core.q("select * from users order by pending desc, id"):
            x = core.user_dict(r)
            x["last_login"] = ll.get(r["username"], "")
            out.append(x)
        return jsonify({"users": out})

    @app.post("/api/users")
    @api(admin=True)
    def users_add(u):
        d, minlen = body(), int(S.get("min_password") or 8)
        e = str(d.get("email", "")).strip().lower()
        if not core.EMAIL_RE.fullmatch(e) or not str(d.get("name", "")).strip():
            raise ApiError("Enter a valid email ID and the full name.")
        if core.q("select 1 from users where username=? or lower(email)=?", (e, e)):
            raise ApiError("That email ID is already registered.")
        err = core.pw_error(str(d.get("password", "")), str(d.get("password", "")), minlen)
        if err:
            raise ApiError(err)
        role = d.get("role") if d.get("role") in ROLES else "user"
        core.ex("insert into users(username,name,pw,role,emp_id,dept,email,created) values(?,?,?,?,?,?,?,?)",
                (e, str(d["name"]).strip(), core.hashpw(d["password"]), role, str(d.get("emp_id", "")).strip(), str(d.get("dept", "")).strip(), e, core.now()))
        core.log(u["username"], "user added (web)", e)
        return jsonify({"ok": True})

    @app.post("/api/users/<int:uid>")
    @api()
    def users_update(u, uid):
        if uid != u["id"] and not is_admin(u):
            raise ApiError("Not allowed.", 403)
        t, d = load_user(uid), body()
        name = str(d.get("name", t["name"])).strip()
        if not name:
            raise ApiError("The name cannot be empty.")
        email = str(d.get("email", t["email"] or "")).strip().lower()
        if email and not core.EMAIL_RE.fullmatch(email):
            raise ApiError("Please enter a valid email ID.")
        if email and core.q("select 1 from users where id!=? and (lower(email)=? or username=?)", (uid, email, email)):
            raise ApiError("That email ID is already used by another account.")
        emp = str(d.get("emp_id", t["emp_id"] or "")).strip() if is_admin(u) else (t["emp_id"] or "")
        role = t["role"]
        if is_admin(u) and uid != u["id"] and d.get("role") in ROLES:
            role = d["role"]
        core.ex("update users set name=?, emp_id=?, dept=?, designation=?, email=?, phone=?, role=? where id=?",
                (name, emp, str(d.get("dept", t["dept"] or "")).strip()[:80], str(d.get("designation", t["designation"] or "")).strip()[:80], email,
                 str(d.get("phone", t["phone"] or "")).strip()[:40], role, uid))
        core.log(u["username"], "profile updated (web)", t["username"])
        return jsonify({"user": core.user_dict(load_user(uid))})

    def user_action(u, uid, what):
        t = load_user(uid)
        if what == "approve" and t["pending"]:
            role = body().get("role")
            core.ex("update users set active=1, pending=0, role=? where id=?", (role if role in ROLES else (t["role"] if t["role"] in ROLES else "user"), uid))
        elif what == "reject" and t["pending"]:
            core.ex("delete from users where id=?", (uid,))
        elif what == "toggle":
            if uid == u["id"]:
                raise ApiError("You cannot disable your own account.")
            if t["pending"]:
                raise ApiError("Approve this account first.")
            core.ex("update users set active=1-active where id=?", (uid,))
        elif what == "delete":
            if uid == u["id"]:
                raise ApiError("You cannot delete your own account.")
            for tb, col in (("favorites", "user_id"), ("prefs", "user_id"), ("users", "id")):
                core.ex(f"delete from {tb} where {col}=?", (uid,))
        elif what == "reset":
            pw, minlen = str(body().get("password", "")), int(S.get("min_password") or 8)
            err = core.pw_error(pw, pw, minlen)
            if err:
                raise ApiError(err)
            core.ex("update users set pw=? where id=?", (core.hashpw(pw), uid))
        else:
            raise ApiError("Nothing to do.")
        core.log(u["username"], f"user {what} (web)", t["username"] + (f" as {body().get('role')}" if what == "approve" and body().get("role") else ""))
        return jsonify({"ok": True})

    @app.post("/api/users/<int:uid>/<what>")
    @api(admin=True)
    def users_action(u, uid, what):
        return user_action(u, uid, what)

    @app.get("/api/users/<int:uid>/photo")
    @api()
    def user_photo(u, uid):
        t, px = load_user(uid), max(24, min(256, int(request.args.get("s", 64))))
        p = core.PHOTOS / t["photo"] if t["photo"] else None
        img = core.round_photo(p, px) if p and p.exists() else None
        if img is None:
            img = g.initials_circle(px, core.initials(t["name"]), S.get("brand_red"))
        r = png(img)
        r.headers["Cache-Control"] = "private, max-age=60"
        return r

    @app.post("/api/users/<int:uid>/photo")
    @api()
    def user_photo_set(u, uid):
        if uid != u["id"] and not is_admin(u):
            raise ApiError("Not allowed.", 403)
        f = request.files.get("file")
        if not f:
            raise ApiError("Choose a picture.")
        tmp = core.ROOT / "tmp"
        tmp.mkdir(exist_ok=True)
        p = tmp / f"photo_{secrets.token_hex(5)}"
        f.save(p)
        try:
            core.save_photo(uid, p)
        except Exception:
            raise ApiError("That file is not a picture we can use.")
        finally:
            p.unlink(missing_ok=True)
        return jsonify({"ok": True})

    @app.delete("/api/users/<int:uid>/photo")
    @api()
    def user_photo_del(u, uid):
        if uid != u["id"] and not is_admin(u):
            raise ApiError("Not allowed.", 403)
        core.remove_photo(uid)
        return jsonify({"ok": True})

    # ------------------------------------------------------------------ folders
    def folders_payload():
        counts = {r["c"]: r["n"] for r in core.q("select category_id c, count(*) n from docs where deleted=0 group by category_id")}
        return [{"id": r["id"], "name": r["name"], "parent_id": r["parent_id"], "color": r["color"] if core.is_hex(r["color"]) else "", "count": counts.get(r["id"], 0)}
                for r in core.q("select * from categories order by sort,id")]

    @app.get("/api/folders")
    @api()
    def folders_get(u):
        return jsonify({"folders": folders_payload(), "bin": 0 if is_viewer(u) else core.trash_count(u["id"], is_admin(u))})

    def need_cat(cid):
        r = core.q("select * from categories where id=?", (cid,))
        if not r:
            raise ApiError("Folder not found.", 404)
        return r[0]

    @app.post("/api/folders")
    @api(write=True)
    def folders_add(u):
        d = body()
        name, parent = str(d.get("name", "")).strip(), d.get("parent_id") or None
        if not name:
            raise ApiError("Type a folder name.")
        if parent:
            need_cat(int(parent))
        if core.q("select 1 from categories where parent_id is ? and lower(name)=?", (parent, name.lower())):
            raise ApiError("A folder with that name already exists here.")
        i = core.ex("insert into categories(name,parent_id,sort) values(?,?,(select coalesce(max(sort),0)+1 from categories where parent_id is ?))", (name, parent, parent))[0]
        notify("folder_created", u, None, i, name, "inside " + core.q("select name from categories where id=?", (parent,))[0]["name"] if parent else "top level")
        core.log(u["username"], "add folder (web)", name)
        return jsonify({"id": i})

    @app.put("/api/folders/<int:cid>")
    @api(admin=True)
    def folders_update(u, cid):
        r, d = need_cat(cid), body()
        if "color" in d:
            core.set_cat_color(cid, d["color"] if core.is_hex(d.get("color")) else None)
        try:
            if "name" in d and str(d["name"]).strip() and str(d["name"]).strip() != r["name"]:
                core.relocate(cid, name=str(d["name"]).strip())
            if "parent_id" in d and (d["parent_id"] or None) != r["parent_id"]:
                np_ = d["parent_id"] or None
                if np_ and (int(np_) in core.descendants(cid)):
                    raise ApiError("A folder cannot go inside itself.")
                core.relocate(cid, parent=int(np_) if np_ else None)
                core.ex("update categories set sort=(select coalesce(max(sort),0)+1 from categories where parent_id is ?) where id=?", (int(np_) if np_ else None, cid))
        except (ValueError, OSError) as e:
            raise ApiError(str(e))
        core.log(u["username"], "folder changed (web)", r["name"])
        return jsonify({"ok": True})

    @app.post("/api/folders/<int:cid>/move")
    @api(admin=True)
    def folders_move(u, cid):
        r, delta = need_cat(cid), -1 if int(body().get("delta", 0)) < 0 else 1
        ids = [s["id"] for s in core.q("select id from categories where parent_id is ? order by sort,id", (r["parent_id"],))]
        i = ids.index(cid)
        j = i + delta
        if 0 <= j < len(ids):
            ids[i], ids[j] = ids[j], ids[i]
            for n, x in enumerate(ids, 1):
                core.ex("update categories set sort=? where id=?", (n, x))
        return jsonify({"ok": True})

    @app.delete("/api/folders/<int:cid>")
    @api(admin=True)
    def folders_delete(u, cid):
        r = need_cat(cid)
        docs, folders = core.delete_folder_tree(cid, u["id"])
        core.log(u["username"], "delete folder (web)", f"{r['name']} ({folders} folder(s), {docs} document(s))")
        return jsonify({"docs": docs, "folders": folders})

    # ------------------------------------------------------------------ documents: list and edit
    @app.get("/api/docs")
    @api()
    def docs_list(u):
        a = request.args
        view = VIEW_MAP.get(a.get("view", "folder"), VIEW_MAP["folder"])
        if view == "Recycle bin" and is_viewer(u):
            raise ApiError("Viewer accounts do not have a Recycle bin.", 403)
        if view == "My uploads":          # my documents that wait for approval, or were rejected
            rows = core.q(core.DOC_SQL + " where d.uploader_id=? and d.deleted in (2,3) order by d.id desc", (u["id"], u["id"]))
            t_ = a.get("q", "").strip().lower()
            if t_:
                rows = [r for r in rows if t_ in f"{r['title']} {r['filename']}".lower()]
            return jsonify({"docs": [dd(r, u) for r in rows], "total": len(rows), "stamp": list(core.docs_stamp())})
        try:
            cat = int(a.get("cat")) if a.get("cat") else None
        except ValueError:
            cat = None
        sort = a.get("order", "pos")
        sort = sort if sort in SORT_KEYS else "pos"
        rows = core.doc_rows(view, a.get("q", ""), u["id"], cat, (sort, a.get("desc") == "1"), is_admin(u))
        chip = a.get("type", "all")
        if chip in core.TYPE_CHIPS and core.TYPE_CHIPS[chip]:
            rows = [r for r in rows if core.ftype(r["filename"])[0] in core.TYPE_CHIPS[chip]]
        out = [dd(r, u) for r in rows[:3000]]
        return jsonify({"docs": out, "total": len(rows), "stamp": list(core.docs_stamp())})

    @app.get("/api/docs/<int:did>")
    @api()
    def doc_get(u, did):
        get_doc_or_404(did, u, True)
        return jsonify({"doc": fav_aware(did, u)})

    @app.put("/api/docs/<int:did>")
    @api(write=True)
    def doc_update(u, did):
        d, data = get_doc_or_404(did, u), body()
        need_edit(d, u)
        title = str(data.get("title", d["title"])).strip()
        if not title:
            raise ApiError("Type a name.")
        review = str(data.get("review", d["review"] or "")).strip()
        if review and not core.valid_date(review):
            raise ApiError("The review date must look like 2026-12-31.")
        status = str(data.get("status", d["status"] or ""))
        if status in ("(none)",):
            status = ""
        if status and status not in core.STATUSES:
            raise ApiError("Unknown status.")
        err = core.rename_doc(d, title)
        if err:
            raise ApiError(err)
        core.ex("update docs set tags=?, descr=?, status=?, review=?, vlabel=? where id=?", (str(data.get("tags", d["tags"] or ""))[:300], str(data.get("descr", d["descr"] or ""))[:2000], status, review, str(data.get("vlabel", d["vlabel"] or ""))[:40], did))
        core.log(u["username"], "edit details (web)", title)
        return jsonify({"doc": fav_aware(did, u)})

    def each_doc(u, ids, fn, allow_deleted=False):
        done = skipped = 0
        for i in ids:
            d = core.get_doc(i)
            if not d or (d["deleted"] or 0) != (1 if allow_deleted else 0) or not (is_admin(u) or d["uploader_id"] == u["id"]):
                skipped += 1
                continue
            fn(d)
            done += 1
        return {"done": done, "skipped": skipped}

    @app.post("/api/docs/delete")
    @api(write=True)
    def docs_delete(u):
        d = body()
        ids = ids_of(d)
        cancelled = 0
        for i in list(ids):                      # cancelling an upload that was never approved removes it for good
            r_ = core.get_doc(i)
            if r_ and (r_["deleted"] or 0) in (2, 3) and (is_admin(u) or r_["uploader_id"] == u["id"]):
                core.purge_doc(r_)
                ids.remove(i)
                cancelled += 1
        if d.get("forever"):
            res = each_doc(u, ids, core.purge_doc, allow_deleted=True)
            core.log(u["username"], "purge (web)", f"{res['done']} document(s)")
        else:
            res = each_doc(u, ids, lambda x: core.trash_doc(x, u["id"]))
            core.log(u["username"], "delete (web)", f"{res['done']} document(s) to Recycle bin")
        res["done"] += cancelled
        return jsonify(res)

    @app.post("/api/docs/restore")
    @api(write=True)
    def docs_restore(u):
        res = each_doc(u, ids_of(body()), core.restore_doc, allow_deleted=True)
        core.log(u["username"], "restore (web)", f"{res['done']} document(s)")
        return jsonify(res)

    @app.post("/api/bin/empty")
    @api(admin=True)
    def bin_empty(u):
        rows = core.q("select * from docs where deleted=1")
        for d in rows:
            core.purge_doc(d)
        core.log(u["username"], "empty Recycle bin (web)", f"{len(rows)} document(s)")
        return jsonify({"done": len(rows)})

    @app.get("/api/approvals")
    @api(admin=True)
    def approvals(u):
        st = 3 if request.args.get("state") == "rejected" else 2
        rows = core.q(core.DOC_SQL + " where d.deleted=? order by d.id", (u["id"], st))
        out = [dd(r, u) for r in rows]
        for x in out:
            x["duplicate_of"] = core.find_duplicate_of(x["id"])
        return jsonify({"docs": out, "pending": core.pending_counts(u["id"])["docs"]})

    @app.post("/api/approvals/approve")
    @api(admin=True)
    def approvals_approve(u):
        ids = ids_of(body())
        waiting = [core.get_doc(i) for i in ids]
        waiting = [d for d in waiting if d and (d["deleted"] or 0) in (2, 3)]
        n = core.approve_docs(ids, u["id"])
        for d in waiting:
            up = core.q("select * from users where id=?", (d["uploader_id"],))
            if up:
                notify("doc_added", up[0], d["id"], d["category_id"], d["title"], d["filename"] + f"  (approved by {u['name']})")
            core.log(u["username"], "approve upload (web)", d["stored"], ref=d["id"])
        core.log(u["username"], "approve upload (web)", f"{n} document(s)")
        return jsonify({"done": n})

    @app.post("/api/approvals/reject")
    @api(admin=True)
    def approvals_reject(u):
        d = body()
        n = core.reject_docs(ids_of(d), u["id"], str(d.get("reason", "")).strip())
        core.log(u["username"], "reject upload (web)", f"{n} document(s)")
        return jsonify({"done": n})

    @app.get("/api/docs/<int:did>/comments")
    @api()
    def comments_get(u, did):
        get_doc_or_404(did, u)
        return jsonify({"comments": [{"id": r["id"], "user_id": r["user_id"], "name": r["name"], "created": r["created"], "body": r["body"], "can_delete": bool(is_admin(u) or r["user_id"] == u["id"])} for r in core.list_comments(did)]})

    @app.post("/api/docs/<int:did>/comments")
    @api(write=True)
    def comments_add(u, did):
        get_doc_or_404(did, u)
        text = str(body().get("body", "")).strip()
        if not text:
            raise ApiError("Write something first.")
        core.add_comment(did, u["id"], text)
        core.log(u["username"], "comment (web)", core.get_doc(did)["stored"], ref=did)
        return jsonify({"ok": True})

    @app.delete("/api/comments/<int:cid>")
    @api(write=True)
    def comments_delete(u, cid):
        r = core.q("select * from comments where id=?", (cid,))
        if not r:
            raise ApiError("Comment not found.", 404)
        if not (is_admin(u) or r[0]["user_id"] == u["id"]):
            raise ApiError("You can only delete your own comments.", 403)
        core.ex("delete from comments where id=?", (cid,))
        return jsonify({"ok": True})

    @app.post("/api/docs/bulk")
    @api(write=True)
    def docs_bulk(u):
        d = body()
        status, review = d.get("status"), d.get("review")
        add_tags = [t.strip() for t in str(d.get("tags_add", "")).split(",") if t.strip()]
        if status in ("(none)",):
            status = ""
        if status is not None and status != "" and status not in core.STATUSES:
            raise ApiError("Unknown status.")
        if review not in (None, "") and not core.valid_date(str(review)):
            raise ApiError("The review date must look like 2026-12-31.")

        def apply(x):
            if status is not None:
                core.ex("update docs set status=? where id=?", (status, x["id"]))
            if review is not None:
                core.ex("update docs set review=? where id=?", (str(review), x["id"]))
            if add_tags:
                cur = [t.strip() for t in (x["tags"] or "").split(",") if t.strip()]
                merged = cur + [t for t in add_tags if t.lower() not in {c.lower() for c in cur}]
                core.ex("update docs set tags=? where id=?", (", ".join(merged)[:300], x["id"]))
        res = each_doc(u, ids_of(d), apply)
        core.log(u["username"], "bulk edit (web)", f"{res['done']} document(s)")
        return jsonify(res)

    @app.post("/api/docs/move")
    @api(write=True)
    def docs_move(u):
        d = body()
        cat = int(d.get("cat") or 0)
        need_cat(cat)
        res = each_doc(u, ids_of(d), lambda x: core.move_doc(x, cat) if x["category_id"] != cat else None)
        core.log(u["username"], "move documents (web)", f"{res['done']}")
        return jsonify(res)

    @app.post("/api/docs/fav")
    @api()
    def docs_fav(u):
        d = body()
        on = d.get("on")
        for i in ids_of(d):
            x = core.get_doc(i)
            if not x or (x["deleted"] or 0) != 0:
                continue
            has = bool(core.q("select 1 from favorites where user_id=? and doc_id=?", (u["id"], i)))
            if on is None or bool(on) != has:
                core.toggle_fav(u["id"], i)
        return jsonify({"ok": True})

    @app.post("/api/docs/reorder")
    @api(write=True)
    def docs_reorder(u):
        d = body()
        ids = ids_of(d)
        rows = [core.get_doc(i) for i in ids]
        rows = [r for r in rows if r and not r["deleted"]]
        cats = {r["category_id"] for r in rows}
        if len(cats) != 1:
            raise ApiError("Open one folder first, then move its documents.")
        for r in rows:
            need_edit(r, u)
        core.reorder_docs(cats.pop(), [r["id"] for r in rows], -1 if int(d.get("delta", 0)) < 0 else 1)
        return jsonify({"ok": True})

    @app.post("/api/links")
    @api(write=True)
    def link_add(u):
        d = body()
        cat = int(d.get("cat") or 0)
        need_cat(cat)
        name, url = str(d.get("name", "")).strip(), str(d.get("url", "")).strip()
        if not name:
            raise ApiError("Type a name.")
        if not re.match(r"^https?://\S+$", url):
            raise ApiError("Type the full address, for example https://www.example.com")
        pend = needs_approval(u)
        p = core.add_link(cat, name, url, u["id"], pending=pend)
        core.log(u["username"], "add link (web)" + (" - waiting for approval" if pend else ""), name)
        if not pend:
            r_ = core.q("select id from docs where stored=? order by id desc limit 1", (str(p.relative_to(core.FILES)),))
            notify("doc_added", u, r_[0]["id"] if r_ else None, cat, name, "web link")
        return jsonify({"ok": True, "file": p.name, "pending": bool(pend)})

    # ------------------------------------------------------------------ upload and versions
    def max_bytes():
        try:
            return int(float(S.get("max_mb") or 0) * 1024 * 1024)
        except ValueError:
            return 0

    @app.post("/api/upload")
    @api(write=True)
    def upload(u):
        f = request.files.get("file")
        if not f or not f.filename:
            raise ApiError("No file received.")
        cat = int(request.form.get("cat") or 0)
        need_cat(cat)
        rel = [p for p in str(request.form.get("relpath", "")).replace("\\", "/").split("/")[:-1] if p and p not in (".", "..")]
        meta = {k: str(request.form.get(k, "")).strip() for k in ("version", "descr", "tags", "status", "review", "comment")}
        check_upload_meta(meta)
        for part in rel[:12]:
            cat = ensure_cat(cat, part, u)
        pend = needs_approval(u)
        if pend and request.form.get("mode") == "version":
            raise ApiError("New versions of a document must be uploaded by an administrator. Upload it as a new document instead.", 403)
        try:
            did, how = core.add_stream(cat, f.filename, f.stream, u["id"], final_title(request.form.get("title"), f.filename), request.form.get("mode") or None, max_bytes(), str(request.form.get("note", ""))[:200], pending=pend)
        except core.NameConflict as e:
            return jsonify({"conflict": dd(core.get_doc(e.doc["id"]), u)}), 409
        except ValueError as e:
            raise ApiError(str(e), 413)
        if how == "added":
            apply_upload_meta(did, u, meta)
        core.log(u["username"], f"upload {how} (web)" + (" - waiting for approval" if pend and how == "added" else ""), f.filename, ref=did)
        if how == "added" and not pend:
            notify("doc_added", u, did, cat, core.get_doc(did)["title"], f.filename)
        elif how == "version":
            notify("doc_version", u, did, cat, core.get_doc(did)["title"], "new version")
        return jsonify({"id": did, "how": how, "cat_id": cat, "pending": bool(pend and how == "added"), "duplicate_of": core.find_duplicate_of(did) if how == "added" else None})

    UID_RE = re.compile(r"^[a-f0-9]{16,40}$")

    def chunk_dir(u, uid):
        if not UID_RE.match(uid or ""):
            raise ApiError("Bad upload id.")
        return core.ROOT / "tmp" / "chunks" / f"{u['id']}_{uid}"

    @app.post("/api/upload/chunk")
    @api(write=True)
    def upload_chunk(u):
        try:
            idx, total = int(request.form.get("index", -1)), int(request.form.get("total", 0))
        except ValueError:
            raise ApiError("Bad upload piece.")
        f = request.files.get("chunk")
        d = chunk_dir(u, request.form.get("uid", ""))
        if not f or idx < 0 or total < 1 or total > 20000 or idx >= total:
            raise ApiError("Bad upload piece.")
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / f"{idx:05d}.tmp"
        core._spool(f.stream, tmp)
        os.replace(tmp, d / f"{idx:05d}.part")
        mb = max_bytes()
        if mb and sum(p.stat().st_size for p in d.glob("*.part")) > mb:
            import shutil
            shutil.rmtree(d, ignore_errors=True)
            raise ApiError(f"The file is bigger than the allowed size ({core.size(mb)}).", 413)
        return jsonify({"ok": True})

    class ChainReader:
        def __init__(self, paths):
            self.paths, self.i, self.f = list(paths), 0, None

        def read(self, n=-1):
            while True:
                if self.f is None:
                    if self.i >= len(self.paths):
                        return b""
                    self.f = open(self.paths[self.i], "rb")
                    self.i += 1
                b = self.f.read(n if n and n > 0 else 1024 * 1024)
                if b:
                    return b
                self.f.close()
                self.f = None

        def close(self):
            if self.f:
                self.f.close()
                self.f = None

    @app.post("/api/upload/finish")
    @api(write=True)
    def upload_finish(u):
        import shutil
        d = body()
        dirp = chunk_dir(u, str(d.get("uid", "")))
        try:
            total, cat = int(d.get("total", 0)), int(d.get("cat") or 0)
        except ValueError:
            raise ApiError("Bad upload.")
        parts = [dirp / f"{i:05d}.part" for i in range(total)]
        if total < 1 or not dirp.exists() or not all(p.exists() for p in parts):
            raise ApiError("Some pieces did not arrive. Please upload the file again.", 400)
        need_cat(cat)
        meta = {k: str(d.get(k, "")).strip() for k in ("version", "descr", "tags", "status", "review", "comment")}
        check_upload_meta(meta)
        rel = [p for p in str(d.get("relpath", "")).replace("\\", "/").split("/")[:-1] if p and p not in (".", "..")]
        for part in rel[:12]:
            cat = ensure_cat(cat, part, u)
        name = str(d.get("filename", "")).strip() or "file"
        rd = ChainReader(parts)
        keep = False
        pend = needs_approval(u)
        if pend and d.get("mode") == "version":
            raise ApiError("New versions of a document must be uploaded by an administrator. Upload it as a new document instead.", 403)
        try:
            did, how = core.add_stream(cat, name, rd, u["id"], final_title(d.get("title"), name), d.get("mode") or None, max_bytes(), str(d.get("note", ""))[:200], pending=pend)
        except core.NameConflict as e:
            keep = True
            return jsonify({"conflict": dd(core.get_doc(e.doc["id"]), u)}), 409
        except ValueError as e:
            raise ApiError(str(e), 413)
        finally:
            rd.close()
            if not keep:
                shutil.rmtree(dirp, ignore_errors=True)
        if how == "added":
            apply_upload_meta(did, u, meta)
        core.log(u["username"], f"upload {how} (web)" + (" - waiting for approval" if pend and how == "added" else ""), name, ref=did)
        if how == "added" and not pend:
            notify("doc_added", u, did, cat, core.get_doc(did)["title"], name)
        elif how == "version":
            notify("doc_version", u, did, cat, core.get_doc(did)["title"], "new version")
        return jsonify({"id": did, "how": how, "cat_id": cat, "pending": bool(pend and how == "added"), "duplicate_of": core.find_duplicate_of(did) if how == "added" else None})

    @app.post("/api/docs/<int:did>/version")
    @api(write=True)
    def version_new(u, did):
        d = get_doc_or_404(did, u)
        need_edit(d, u)
        if (d["deleted"] or 0) != 0:
            raise ApiError("Wait until this document is approved.", 400)
        if needs_approval(u):
            raise ApiError("New versions of a document must be uploaded by an administrator.", 403)
        f = request.files.get("file")
        if not f:
            raise ApiError("Choose the new file.")
        try:
            core.add_stream(d["category_id"], d["filename"], f.stream, u["id"], None, "version", max_bytes(), str(request.form.get("note", ""))[:200])
        except ValueError as e:
            raise ApiError(str(e), 413)
        core.log(u["username"], "new version (web)", d["title"], ref=did)
        notify("doc_version", u, did, d["category_id"], d["title"], "new version")
        return jsonify({"doc": fav_aware(did, u)})

    @app.get("/api/docs/<int:did>/versions")
    @api()
    def versions_get(u, did):
        d = get_doc_or_404(did, u)
        who = core.q("select name from users where id=?", (d["updated_by"] or d["uploader_id"],))
        cur = {"id": 0, "ver": d["ver"] or 1, "filename": d["filename"], "size": d["size"], "who": who[0]["name"] if who else "", "created": d["created"], "note": d["vnote"] or "", "current": True}
        old = [{"id": v["id"], "ver": v["ver"], "filename": v["filename"], "size": v["size"], "who": v["who"] or "", "created": v["created"], "note": v["note"] or "", "current": False} for v in core.versions_of(did)]
        return jsonify({"versions": [cur] + old})

    @app.post("/api/docs/<int:did>/versions/<int:vid>/restore")
    @api(write=True)
    def version_restore(u, did, vid):
        d = get_doc_or_404(did, u)
        need_edit(d, u)
        v = core.q("select * from versions where id=? and doc_id=?", (vid, did))
        if not v:
            raise ApiError("Version not found.", 404)
        core.restore_version(d, v[0], u["id"])
        return jsonify({"doc": fav_aware(did, u)})

    # ------------------------------------------------------------------ download and view
    def send_doc(d, inline, path=None, name=None):
        p = path or (core.FILES / d["stored"])
        if not p.exists():
            raise ApiError("The file is missing on the server.", 404)
        ext = p.suffix.lower()
        ok_inline = inline and ext in INLINE_OK
        return send_file(p, mimetype=INLINE_OK.get(ext) if ok_inline else (mimetypes.guess_type(p.name)[0] or "application/octet-stream"), as_attachment=not ok_inline,
                         download_name=name or d["filename"], conditional=True, max_age=0)

    @app.get("/files/<int:did>/download")
    @api()
    def file_download(u, did):
        d = get_doc_or_404(did, u)
        if on("log_access"):
            core.log(u["username"], "download (web)", d["stored"], ref=did)
        return send_doc(d, False)

    @app.get("/files/<int:did>/inline")
    @api()
    def file_inline(u, did):
        return send_doc(get_doc_or_404(did, u), True)

    @app.get("/files/<int:did>/v/<int:vid>")
    @api()
    def file_version(u, did, vid):
        d = get_doc_or_404(did, u)
        v = core.q("select * from versions where id=? and doc_id=?", (vid, did))
        if not v:
            raise ApiError("Version not found.", 404)
        return send_doc(d, False, core.FILES / v[0]["stored"], v[0]["filename"])

    @app.get("/files/<int:did>/exact.pdf")
    @api()
    def file_exact(u, did):
        """Exact page view of Word / Excel / PowerPoint (needs Windows + Microsoft Office on the server)."""
        d = get_doc_or_404(did, u)
        p = core.FILES / d["stored"]
        if not p.exists():
            raise ApiError("The file is missing on the server.", 404)
        if os.name != "nt":
            raise ApiError("Exact view needs the server to run on Windows with Microsoft Office.", 501)
        cache = core.ROOT / "cache"
        cache.mkdir(exist_ok=True)
        out = cache / f"{did}_{p.stat().st_mtime_ns}.pdf"
        if not out.exists():
            with _OFFICE_LOCK:
                try:
                    if not out.exists():
                        core.office_to_pdf(p, out)
                except Exception as e:
                    raise ApiError(str(e), 502)
        return send_file(out, mimetype="application/pdf", conditional=True, max_age=0)

    @app.post("/api/docs/<int:did>/open")
    @api()
    def doc_opened(u, did):
        d = get_doc_or_404(did, u)
        if on("log_access"):
            core.log(u["username"], "open", d["stored"], ref=did)
        return jsonify({"ok": True})

    def esc(t):
        return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    @app.get("/api/docs/<int:did>/render")
    @api()
    def doc_render(u, did):
        d = get_doc_or_404(did, u)
        p, ext = core.FILES / d["stored"], Path(d["filename"]).suffix.lower()
        if not p.exists():
            raise ApiError("The file is missing on the server.", 404)
        info = {"id": did, "title": d["title"], "filename": d["filename"], "ext": ext}
        try:
            if ext == ".pdf":
                return jsonify({**info, "kind": "pdf"})
            if ext in core.IMG_EXT and ext in INLINE_OK:
                return jsonify({**info, "kind": "image"})
            if ext in core.VIDEO_EXT and ext in INLINE_OK:
                return jsonify({**info, "kind": "video"})
            if ext in core.AUDIO_EXT and ext in INLINE_OK:
                return jsonify({**info, "kind": "audio"})
            if ext in core.LINK_EXT:
                return jsonify({**info, "kind": "link", "url": core.read_url(p) or ""})
            if ext in core.CSV_EXT:
                return jsonify({**info, "kind": "table", "sheets": [{"name": "Data", "rows": core.read_csv_rows(p)}], "header": True})
            if ext in (".xlsx", ".xlsm"):
                sheets, shared = core.xlsx_meta(p)
                want = request.args.get("sheet")
                names = [s[0] for s in sheets]
                pick = want if want in names else (names[0] if names else None)
                rows = core.xlsx_rows(p, dict(sheets)[pick], shared) if pick else []
                return jsonify({**info, "kind": "table", "names": names, "sheet": pick, "sheets": [{"name": pick, "rows": rows}], "header": False, "exact": True})
            if ext == ".docx":
                out = []
                for b in core.read_docx(p):
                    if b[0] == "p":
                        _, style, bullet, runs = b
                        s = style.lower().replace(" ", "")
                        tag = "h1" if s.startswith(("title", "heading1")) else "h2" if s.startswith("heading2") else "h3" if s.startswith(("heading3", "heading4")) else "p"
                        inner = "".join(("<b>%s</b>" if bd else "<i>%s</i>" if it else "%s") % esc(t).replace("\n", "<br>") for t, bd, it in runs)
                        out.append(f"<li>{inner}</li>" if bullet else f"<{tag}>{inner or '&nbsp;'}</{tag}>")
                    else:
                        out.append("<table>" + "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>" for row in b[1]) + "</table>")
                return jsonify({**info, "kind": "html", "html": "".join(out) or "<p>This document has no text to show.</p>", "exact": True})
            if ext == ".pptx":
                out = []
                for i, items in enumerate(core.read_pptx(p), 1):
                    out.append(f'<div class="slide"><div class="slide-n">Slide {i}</div>' + "".join(f"<h2>{esc(t)}</h2>" if tt else f"<li>{esc(t)}</li>" for tt, t in items) + "</div>")
                return jsonify({**info, "kind": "html", "html": "".join(out) or "<p>No slides found.</p>", "exact": True})
            if ext in core.TEXT and p.stat().st_size < 3_000_000:
                raw = p.read_bytes()
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    text = raw.decode("cp1252", errors="replace")
                return jsonify({**info, "kind": "text", "text": text, "editable": bool((is_admin(u) or d["uploader_id"] == u["id"]) and not is_viewer(u))})
            if ext in (".doc", ".rtf", ".odt", ".xls", ".xlsb", ".ppt", ".pps", ".ppsx"):
                return jsonify({**info, "kind": "office"})
        except Exception as e:
            return jsonify({**info, "kind": "other", "note": f"This file could not be shown ({e})."})
        return jsonify({**info, "kind": "other"})

    @app.put("/api/docs/<int:did>/text")
    @api(write=True)
    def text_save(u, did):
        d = get_doc_or_404(did, u)
        need_edit(d, u)
        p = core.FILES / d["stored"]
        if Path(d["filename"]).suffix.lower() not in core.TEXT:
            raise ApiError("This file cannot be edited here.")
        text = str(body().get("text", ""))
        p.write_bytes(text.replace("\r\n", "\n").replace("\n", "\r\n" if b"\r\n" in p.read_bytes()[:200000] else "\n").encode("utf-8"))
        core.ex("update docs set size=?, sha=NULL where id=?", (p.stat().st_size, did))
        core.log(u["username"], "edit text (web)", d["stored"])
        return jsonify({"ok": True})

    @app.get("/api/docs/<int:did>/thumb.png")
    @api()
    def doc_thumb(u, did):
        from PIL import Image
        d = get_doc_or_404(did, u)
        p, ext = core.FILES / d["stored"], Path(d["filename"]).suffix.lower()
        w = max(60, min(600, int(request.args.get("w", 260))))
        im = None
        try:
            if ext in core.IMG_EXT and p.exists():
                im = Image.open(p)
                im.load()
                im.thumbnail((w, int(w * 1.1)))
            elif ext == ".pdf" and fitz and p.exists():
                doc = fitz.open(str(p))
                pg = doc[0]
                s = w / pg.rect.width
                im = Image.open(io.BytesIO(pg.get_pixmap(matrix=fitz.Matrix(s, s), alpha=False).tobytes("png")))
                doc.close()
                im = im.crop((0, 0, im.width, min(im.height, int(w * 1.2))))
        except Exception:
            im = None
        if im is None:
            return jsonify({"error": "no thumbnail"}), 404
        r = png(im.convert("RGBA"))
        r.headers["Cache-Control"] = "private, max-age=300"
        return r

    @app.post("/api/zip")
    @api()
    def zip_docs(u):
        rows = [core.q(core.DOC_SQL + " where d.id=? and d.deleted=0", (0, i)) for i in ids_of(body(), 500)]
        docs = [r[0] for r in rows if r]
        if not docs:
            raise ApiError("Choose documents first.")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip", dir=str(core.ROOT / "tmp") if (core.ROOT / "tmp").exists() else None)
        tmp.close()
        n = core.zip_documents(docs, tmp.name)
        core.log(u["username"], "zip export (web)", f"{n} file(s)")
        resp = send_file(tmp.name, mimetype="application/zip", as_attachment=True, download_name=f"TDMS_documents_{dt.date.today():%Y%m%d}.zip")
        resp.call_on_close(lambda: Path(tmp.name).unlink(missing_ok=True))
        return resp

    # ------------------------------------------------------------------ pictures: icons and charts
    @app.get("/icon/<kind>/<name>.png")
    def icon(kind, name):
        s = max(12, min(160, int(request.args.get("s", 24))))
        col = "#" + request.args.get("c", "").lstrip("#")
        col = col if core.is_hex(col) else None
        if kind == "ft":
            k = name if name in core.FT or name == "file" else "file"
            c = col or (core.FT[k][2] if k in core.FT else core.FT_OTHER[1])
            img = g.ft_icon(core.ICON_TEXT.get(k, "FILE"), c, s, inverse=request.args.get("inv") == "1")
        elif kind == "folder":
            img = g.folder_icon(s, col)
        elif kind == "trash":
            img = g.trash_icon(s, col or "#E0713F")
        elif kind == "tab":
            img = g.tab_icon(name, s, col or "#FFFFFF")
        else:
            return ("", 404)
        r = png(img, 86400)
        r.headers["Cache-Control"] = "public, max-age=86400"
        return r

    @app.get("/chart/<name>.png")
    @api()
    def chart(u, name):
        w, h = max(200, min(1400, int(request.args.get("w", 600)))), max(100, min(500, int(request.args.get("h", 190))))
        pal = palette(request.args.get("theme", "light"))
        b, tc = brand(), type_colors_of(u["id"])
        if name == "uploads":
            up = core.uploads_by_day(14)
            vals = [n for _, n in up]
            img = g.bars(w, h, [x.strftime("%d") for x, _ in up], vals, b["red"], pal["bg"], ink=pal["ink"], muted=pal["muted"], grid=pal["grid"], vmax=max(4, max(vals)))
        elif name == "trend":
            wk = core.week_counts(12)
            img = g.area(w, h, [x.strftime("%d %b") for x, _ in wk], [n for _, n in wk], b["blue"], pal["bg"], ink=pal["ink"], muted=pal["muted"], grid=pal["grid"])
        elif name == "types":
            ty = core.type_counts(tc)
            img = g.donut(h, [(n, c) for _, n, c in ty], pal["bg"], big=str(sum(n for _, n, _ in ty)), small="documents", ink=pal["ink"], muted=pal["muted"])
        elif name == "storage":
            st = core.storage_by_type(tc)
            img = g.hbars(w, h, [(lab, mb) for lab, mb, _ in st], b["blue"], pal["bg"], ink=pal["ink"], muted=pal["muted"], track=pal["track"], colors=[c for _, _, c in st], suffix=" MB", label_w=120)
        elif name == "folders":
            img = g.hbars(w, h, core.top_folders(6), b["blue"], pal["bg"], ink=pal["ink"], muted=pal["muted"], track=pal["track"])
        elif name == "people":
            img = g.hbars(w, h, core.top_contributors(6), "#8E44AD", pal["bg"], ink=pal["ink"], muted=pal["muted"], track=pal["track"])
        elif name == "status":
            ss = core.status_counts()
            img = g.hbars(w, h, [(lab, n) for lab, n, _ in ss], b["blue"], pal["bg"], ink=pal["ink"], muted=pal["muted"], track=pal["track"], colors=[c for _, _, c in ss], label_w=110)
        else:
            return ("", 404)
        return png(img.convert("RGB"))

    # ------------------------------------------------------------------ dashboard and live changes
    def ev_dict(r):
        return {"id": r["id"], "ts": r["ts"], "kind": r["kind"], "user_id": r["user_id"], "name": r["user_name"], "emp_id": r["emp_id"] or "", "doc_id": r["doc_id"], "cat_id": r["cat_id"], "cat": r["cat_name"] or "", "title": r["title"] or "", "detail": r["detail"] or ""}

    @app.get("/api/notifications")
    @api()
    def notifications(u):
        try:
            since = int(request.args.get("since", 0))
        except ValueError:
            since = 0
        kinds = allowed_kinds(u)
        rows = core.events_since(since, kinds, 60) if kinds else []
        own = on("notif_own")
        items = [ev_dict(r) for r in rows if own or r["user_id"] != u["id"]]
        seen = int(core.prefs_of(u["id"]).get("seen_event", 0) or 0)
        unread = 0
        if kinds:
            marks = ",".join("?" * len(kinds))
            unread = core.q(f"select count(*) c from events where id>? and kind in ({marks})" + ("" if own else " and user_id!=?"), (seen, *kinds, *(() if own else (u["id"],))))[0]["c"]
        return jsonify({"events": items, "latest": core.latest_event_id(), "unread": unread, "seen": seen, "popup": on("notif_popup") and bool(kinds)})

    @app.post("/api/notifications/seen")
    @api()
    def notifications_seen(u):
        try:
            core.set_pref(u["id"], "seen_event", int(body().get("id", 0)))
        except (TypeError, ValueError):
            raise ApiError("Bad number.")
        return jsonify({"ok": True})

    @app.get("/api/changes")
    @api()
    def changes(u):
        pc = core.pending_counts(u["id"])
        return jsonify({"docs": list(core.docs_stamp()), "logs": core.logs_stamp(), "pending": core.stats(0)["pending"] if is_admin(u) else 0,
                        "pending_docs": pc["docs"] if is_admin(u) else 0, "my_pending": pc["mine_pending"], "my_rejected": pc["mine_rejected"], "event_id": core.latest_event_id() if allowed_kinds(u) else 0})

    def slim(rows, u, extra=None):
        out = []
        for r in rows:
            d = dd(r, u)
            if extra:
                d.update(extra(r))
            out.append(d)
        return out

    @app.get("/api/dashboard")
    @api()
    def dashboard(u):
        st, ex_, wc = core.stats(u["id"]), core.extra_stats(), core.week_compare()
        diff = wc["this"] - wc["prev"]
        tiles = [{"key": "docs", "label": "Documents", "value": st["docs"], "sub": f"+{wc['this']} in the last 7 days"}, {"key": "size", "label": "Storage used", "value": core.size(st["size"]), "sub": f"+{wc['mb']} MB in the last 7 days"},
                 {"key": "folders", "label": "Folders", "value": st["folders"], "sub": "in the library"},
                 {"key": "week", "label": "Added this week", "value": ex_["week"], "sub": ("\u25B2 " if diff > 0 else "\u25BC " if diff < 0 else "= ") + f"{abs(diff)} vs the week before"},
                 {"key": "mine", "label": "Added by you", "value": st["mine"], "sub": f"{round(100 * st['mine'] / max(1, st['docs']))}% of all documents"},
                 {"key": "fav", "label": "Favorites", "value": st["fav"], "sub": "quick access"}, {"key": "versions", "label": "Versions kept", "value": ex_["versions"], "sub": "older versions you can restore"},
                 {"key": "trash", "label": "In Recycle bin", "value": st["trash"], "sub": f"removed after {S.get('trash_days')} days"}]
        pc = core.pending_counts(u["id"])
        if is_admin(u):
            tiles += [{"key": "uploads", "label": "Uploads waiting", "value": pc["docs"], "sub": "please review" if pc["docs"] else "all clear"}]
        elif not is_viewer(u):
            tiles += [{"key": "uploads", "label": "My uploads waiting", "value": pc["mine_pending"], "sub": f"{pc['mine_rejected']} rejected" if pc["mine_rejected"] else "waiting for an admin"}]
        if is_admin(u):
            tiles += [{"key": "users", "label": "Active users", "value": st["users"], "sub": "can sign in"}, {"key": "pending", "label": "Waiting for approval", "value": st["pending"], "sub": "please review" if st["pending"] else "all clear"}]
        mo = core.most_opened(7)
        counts = {d["id"]: c for d, c in mo}
        today = dt.date.today().isoformat()
        out = {"tiles": tiles, "opened": slim(core.recent_opened(u["id"], 7), u), "favorites": slim(core.favorites_list(u["id"], 7), u),
               "most": slim([d for d, _ in mo], u, lambda r: {"opens": counts.get(r["id"], 0)}), "recent": slim(core.recent_docs(8), u), "largest": slim(core.largest_files(8), u),
               "review": slim(core.review_due(30, 8), u, lambda r: {"late": (r["review"] or "") < today}), "status": [{"label": l, "n": n, "color": c} for l, n, c in core.status_counts()],
               "types": [{"label": l, "n": n, "color": c} for l, n, c in core.type_counts(type_colors_of(u["id"]))], "stamp": [list(core.docs_stamp()), core.logs_stamp()]}
        if is_admin(u):
            out["activity"] = [{"ts": r["ts"], "user": r["user"], "action": r["action"], "detail": r["detail"] or ""} for r in core.recent_activity(10)]
        return jsonify(out)

    # ------------------------------------------------------------------ admin
    ADMIN_KEYS = {"app_name", "short_name", "company", "subtitle", "tagline", "brand_red", "brand_blue", "brand_navy", "login_bg", "allow_signup", "require_approval", "email_domain",
                  "min_password", "max_mb", "auto_backup", "trash_days", "default_role", "upload_approval", "idle_minutes"} | set(FEATURES)

    @app.get("/api/admin/settings")
    @api(admin=True)
    def admin_settings(u):
        return jsonify({**{k: S.get(k) for k in sorted(ADMIN_KEYS - set(FEATURES))}, **features_payload()})

    @app.post("/api/admin/settings")
    @api(admin=True)
    def admin_settings_save(u):
        d = body()
        for k, v in d.items():
            if k not in ADMIN_KEYS:
                continue
            v = str(v).strip()
            if k.startswith("brand_") and not HEX.match(v):
                raise ApiError("Colours must look like #E8312F.")
            if k == "login_bg" and v not in g.LOGIN_PRESETS:
                raise ApiError("Unknown login background.")
            if k in ("allow_signup", "require_approval", "auto_backup", "upload_approval"):
                v = "1" if v in ("1", "true", "True", "on") else "0"
            if k == "min_password":
                v = str(max(4, min(32, int(v or 8))))
            if k == "trash_days":
                v = str(max(1, min(365, int(v or 30))))
            if k == "max_mb":
                v = str(max(0.0, float(v or 0)))
            if k == "idle_minutes":
                try:
                    v = str(max(0.0, min(1440.0, float(v or 60))))
                except ValueError:
                    raise ApiError("Type the minutes as a number, 0 = never.")
            if k in FEATURES:
                if FEATURES[k] in ("0", "1") and k not in NUMERIC_FEATURES and k not in TEXT_FEATURES:
                    v = "1" if v in ("1", "true", "True", "on") else "0"
                elif k in NUMERIC_FEATURES:
                    try:
                        v = str(max(0, min(3650, int(float(v or 0)))))
                    except ValueError:
                        raise ApiError("Type the days as a whole number (0 = keep forever).")
                elif k == "name_format" and v not in ("title", "upper", "lower", "sentence", "none"):
                    raise ApiError("Unknown file name style.")
                elif k == "name_acronyms":
                    v = ",".join(a.strip().upper() for a in v.split(",") if a.strip())[:400]
                elif k == "ud_default_version":
                    v = v[:20]
                S.set(k, v if v != "" else "0" if k in NUMERIC_FEATURES else "-")
                continue
            if k == "default_role" and v not in ("user", "viewer"):
                raise ApiError("New accounts can start as User or Viewer.")
            if k == "email_domain":
                v = v.lstrip("@").lower()
            if k in ("app_name", "short_name") and not v:
                raise ApiError("Names cannot be empty.")
            S.set(k, v[:120])
        core.log(u["username"], "settings saved (web)")
        return jsonify({"brand": brand()})

    @app.post("/api/admin/logo")
    @api(admin=True)
    def admin_logo(u):
        from PIL import Image
        f = request.files.get("file")
        if not f:
            raise ApiError("Choose a picture.")
        try:
            im = Image.open(f.stream).convert("RGBA")
        except Exception:
            raise ApiError("That file is not a picture.")
        im.thumbnail((1200, 600))
        im.save(core.ROOT / "logo.png", "PNG")
        core.log(u["username"], "logo changed (web)")
        return jsonify({"ok": True})

    @app.delete("/api/admin/logo")
    @api(admin=True)
    def admin_logo_reset(u):
        (core.ROOT / "logo.png").unlink(missing_ok=True)
        return jsonify({"ok": True})

    def kind_of(action):
        a = (action or "").lower()
        if a.startswith(("login", "logout", "failed login", "failed recovery")):
            return "login"
        if a.startswith(("upload", "add link", "new version", "edit text")):
            return "upload"
        if a in ("open",) or a.startswith("download") or a.startswith("zip"):
            return "access"
        if a.startswith(("delete", "purge", "restore", "empty")):
            return "delete"
        if a.startswith(("approve", "reject")):
            return "approval"
        if a.startswith(("add folder", "folder", "delete folder")):
            return "folder"
        if a.startswith(("user ", "account", "password", "profile", "security")):
            return "account"
        if a.startswith("settings"):
            return "settings"
        return "other"

    @app.get("/api/admin/activity")
    @api(admin=True)
    def admin_activity(u):
        """The audit trail: who (name + id), what, which document, when (to the second), from which address, with which device, in which session."""
        core.flush()
        a = request.args
        t, who, kind = a.get("q", "").lower().strip(), a.get("user", "").strip().lower(), a.get("kind", "all")
        d_from, d_to = a.get("from", "").strip(), a.get("to", "").strip()
        sql = ("select l.*, coalesce(u.name,u2.name,l.user) name, coalesce(u.emp_id,u2.emp_id,'') emp_id, d.title doc_title from logs l left join users u on u.id=l.uid left join users u2 on u2.username=l.user "
               "left join docs d on d.id=l.ref order by l.id desc limit 8000")
        rows = []
        for r in core.q(sql):
            k = kind_of(r["action"])
            if kind != "all" and k != kind:
                continue
            if who and who not in f"{r['user']} {r['name']} {r['emp_id']}".lower():
                continue
            if d_from and (r["ts"] or "")[:10] < d_from or d_to and (r["ts"] or "")[:10] > d_to:
                continue
            row = {"id": r["id"], "ts": r["ts"], "user": r["user"], "name": r["name"], "emp_id": r["emp_id"], "uid": r["uid"], "action": r["action"], "kind": k, "detail": r["detail"] or "", "ip": r["ip"] or "",
                   "device": device_of(r["ua"]), "sid": (r["sid"] or "")[:8], "ref": r["ref"], "doc_title": r["doc_title"] or ""}
            if t and t not in " ".join(str(v) for v in row.values()).lower():
                continue
            rows.append(row)
            if len(rows) >= 2000:
                break
        return jsonify({"rows": rows})

    @app.get("/api/admin/sessions")
    @api(admin=True)
    def admin_sessions(u):
        out, now_ = [], dt.datetime.now()
        for r in core.sessions_list():
            try:
                idle = (now_ - dt.datetime.strptime(r["last_seen"], "%Y-%m-%d %H:%M:%S")).total_seconds()
            except (TypeError, ValueError):
                idle = 1e9
            live = not r["logout_at"] and not r["revoked"] and idle < 300
            out.append({"sid": r["sid"], "short": r["sid"][:8], "user_id": r["user_id"], "username": r["username"], "name": r["name"], "emp_id": r["emp_id"], "role": r["role"], "ip": r["ip"] or "", "device": device_of(r["ua"]),
                        "login_at": r["login_at"], "last_seen": r["last_seen"], "logout_at": r["logout_at"] or "", "revoked": bool(r["revoked"]), "online": live, "current": r["sid"] == session.get("sid")})
        return jsonify({"sessions": out})

    @app.post("/api/admin/sessions/<sid>/revoke")
    @api(admin=True)
    def admin_session_revoke(u, sid):
        if sid == session.get("sid"):
            raise ApiError("That is your own session. Use Sign out.")
        if not core.q("select 1 from sessions where sid=?", (sid,)):
            raise ApiError("Session not found.", 404)
        core.session_end(sid, revoked=True)
        core.log(u["username"], "session ended by admin (web)", sid[:8])
        return jsonify({"ok": True})

    @app.get("/api/admin/backup")
    @api(admin=True)
    def admin_backup(u):
        import sqlite3
        core.flush()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        tmp.close()
        dst = sqlite3.connect(tmp.name)
        with core._LOCK:
            core.conn().backup(dst)
        dst.close()
        core.log(u["username"], "database backup downloaded (web)")
        resp = send_file(tmp.name, mimetype="application/octet-stream", as_attachment=True, download_name=f"tdms_backup_{dt.date.today():%Y%m%d}.db")
        resp.call_on_close(lambda: Path(tmp.name).unlink(missing_ok=True))
        return resp

    @app.get("/api/admin/duplicates")
    @api(admin=True)
    def admin_duplicates(u):
        groups = core.duplicate_groups()
        return jsonify({"groups": [{"size": g_["size"], "wasted": g_["wasted"], "docs": [dd(r, u) for r in g_["docs"]]} for g_ in groups], "wasted": sum(g_["wasted"] for g_ in groups)})

    @app.get("/api/admin/info")
    @api(admin=True)
    def admin_info(u):
        import shutil
        cfg = load_config()
        free = shutil.disk_usage(core.ROOT).free
        return jsonify({"version": core.VERSION, "python": sys.version.split()[0], "data": str(core.ROOT), "port": cfg["port"], "urls": [f"http://{ip}:{cfg['port']}" for ip in local_ips()],
                        "disk_free": core.size(free), "pdf_thumbs": bool(fitz), "office": os.name == "nt", "behind_proxy": bool(cfg.get("behind_proxy")), "stats": core.stats(u["id"])})

    @app.errorhandler(404)
    def nf(e):
        if request.path.startswith("/api/") or request.path.startswith("/files/"):
            return jerr("Not found.", 404)
        return send_from_directory(WEB, "index.html")

    @app.errorhandler(413)
    def too_big(e):
        return jerr("The file is bigger than the server allows.", 413)

    @app.errorhandler(500)
    def boom(e):
        try:
            with open(BASE / "tdms_web_error.log", "a", encoding="utf-8") as f:
                import traceback
                f.write(f"\n[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {request.method} {request.path}\n{traceback.format_exc()}")
        except Exception:
            pass
        return jerr("Something went wrong on the server. It was written to tdms_web_error.log.", 500)

    return app


def purge_chunks(hours=24):
    import shutil
    base = core.ROOT / "tmp" / "chunks"
    if not base.exists():
        return
    for d in base.iterdir():
        try:
            if time.time() - d.stat().st_mtime > hours * 3600:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass


def flush_loop():
    n = 0
    while True:
        time.sleep(2)
        n += 1
        try:
            core.flush()
            if n % 900 == 0:
                purge_chunks()
                try:
                    core.purge_events(int(feat("notif_retention") or 0))
                    days = int(feat("log_retention") or 0)
                    if days > 0:
                        core.ex("delete from logs where ts < ?", ((dt.datetime.now() - dt.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S"),))
                except Exception:
                    pass
        except Exception:
            pass


def main():
    if "--reset-admin" in sys.argv:
        core.init()
        core.ex("update users set pw=?, active=1, pending=0 where username='admin'", (core.hashpw("admin123"),))
        print("Admin password reset to admin123")
        return
    app = create_app()
    cfg = load_config()
    port = int(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--port=")), cfg["port"]))
    host = cfg["host"]
    threading.Thread(target=flush_loop, daemon=True).start()
    purge_chunks()
    core.daily_backup(S)
    core.auto_purge(int(float(S.get("trash_days") or 30)))
    print("\n  TDMS web is running.\n")
    print(f"  On this computer :  http://localhost:{port}")
    for ip in local_ips():
        print(f"  On your network  :  http://{ip}:{port}")
    print("\n  Keep this window open. Press Ctrl+C to stop.\n")
    try:
        from waitress import serve
        serve(app, host=host, port=port, threads=12, max_request_body_size=40 * 1024 ** 3, channel_timeout=300, ident="TDMS")
    except ImportError:
        app.run(host=host, port=port, threaded=True)


if __name__ == "__main__":
    main()
