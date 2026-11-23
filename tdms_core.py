"""
TDMS core  -  data, settings, file readers.  No window code here, so it can be tested without a screen.
"""
import base64, collections, csv, datetime as dt, hashlib, io, os, re, secrets, shutil, sqlite3, subprocess, sys, threading, webbrowser, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

VERSION = "8.0"
FROZEN = getattr(sys, "frozen", False)
BASE = Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parent
RES = Path(getattr(sys, "_MEIPASS", BASE))
ROOT = BASE / "AFS_TDMS_Data"
FILES = ROOT / "files"
PHOTOS = ROOT / "photos"
DB = ROOT / "tdms.db"
FILES.mkdir(parents=True, exist_ok=True)

TEXT = {".txt", ".log", ".md", ".ini", ".json", ".xml", ".bat", ".cfg", ".py", ".sql", ".yaml", ".yml"}
IMG_EXT = {".png", ".gif", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".mpg", ".mpeg", ".m4v", ".webm"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".wma", ".flac", ".ogg"}
CSV_EXT = {".csv", ".tsv"}
LINK_EXT = {".url", ".webloc"}
WEB_EXT = {".html", ".htm"}
OFFICE_PDF = {".doc", ".docx", ".rtf", ".odt", ".xls", ".xlsx", ".xlsm", ".xlsb", ".ppt", ".pptx", ".pps", ".ppsx"}
FT = {"pdf": ("PDF document", {".pdf"}, "#E2352B"), "doc": ("Word document", {".doc", ".docx", ".rtf", ".odt"}, "#2B579A"),
      "xls": ("Excel workbook", {".xls", ".xlsx", ".xlsm", ".xlsb"}, "#1D8348"), "csv": ("CSV table", CSV_EXT, "#26A69A"),
      "ppt": ("PowerPoint", {".ppt", ".pptx", ".pps", ".ppsx"}, "#F28C1E"), "img": ("Image", IMG_EXT | {".svg"}, "#8E44AD"),
      "link": ("Web link", LINK_EXT | WEB_EXT, "#0097A7"), "zip": ("Archive", {".zip", ".rar", ".7z", ".tar", ".gz"}, "#D4A017"),
      "vid": ("Video", VIDEO_EXT, "#D81B60"), "aud": ("Audio", AUDIO_EXT, "#3F51B5"), "txt": ("Text file", TEXT, "#607D8B"),
      "cad": ("Drawing / CAD", {".dwg", ".dxf", ".step", ".stp", ".igs"}, "#795548")}
ICON_TEXT = {"pdf": "PDF", "doc": "DOC", "xls": "XLS", "csv": "CSV", "ppt": "PPT", "img": "IMG", "link": "WEB", "zip": "ZIP", "vid": "VID", "aud": "AUD", "txt": "TXT", "cad": "CAD", "file": "FILE"}
VIEWS = ["Selected folder", "All documents", "My favorites", "Added by me", "Recent (last 30 days)", "Recycle bin"]
COLS = (("type", "Type"), ("status", "Status"), ("cat", "Folder"), ("size", "Size"), ("by", "Added by"), ("added", "Added"))
STATUSES = ["(none)", "Draft", "In review", "Approved", "Obsolete"]
STATUS_COLORS = {"Draft": "#F28C1E", "In review": "#2E6DB4", "Approved": "#1D8348", "Obsolete": "#90A4AE"}
TYPE_CHIPS = {"all": None, "pdf": {"pdf"}, "doc": {"doc"}, "xls": {"xls", "csv"}, "ppt": {"ppt"}, "img": {"img"}, "vid": {"vid", "aud"}, "link": {"link"}}
ORDERS = {"My order (use up / down)": ("pos", False), "Name A-Z": ("title", False), "Name Z-A": ("title", True), "Newest first": ("added", True),
          "Oldest first": ("added", False), "Largest first": ("size", True), "Type": ("type", False), "Status": ("status", False)}
IDLE = {"Never": 0, "5 minutes": 5, "10 minutes": 10, "15 minutes": 15, "30 minutes": 30}
DATE_LABELS = {"ISO": "2026-10-30 14:05", "DMY": "30-10-2026 14:05", "Long": "30 Oct 2026, 14:05"}
QUESTIONS = ["What was the name of your first school?", "What is your mother's maiden name?", "What was your first pet's name?",
             "In which city were you born?", "What was your first job?", "What is your favourite teacher's name?"]
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
CATEGORIES = ["0.PLC Function Block FB", "1.AMR", "2.Zippy", "3.Cruiser_Child", "4.Cruiser 360/4-Way shuttle", "5.1 RGV/Travect", "5.MultiPro (Mother)_With_Child",
              "6.T-Car", "7.Sort-IE", "8.MLS_Medius", "9.1_Modular Quadron", "9.Quadron", "10.PTL", "11.Rapido Controller", "12.Crane_Skyron", "13.Conveyor All Card",
              "14.Buffer Conveyor", "15.Pallet Conveyor", "16.Pallet Lift_(Siemens PLC)", "17.Tote Conveyor", "18.Tote/Carton Lift_(Omron PLC)", "19.Pop-UP", "20.ZPA",
              "21.NZPA", "22.Murr & I/O Card", "23.Barcode Scanner", "24.HOPT", "24.P&A (Print and Apply)", "25.Saftey PLC & Relay", "26.Li-Dar_2D/3D", "27.All Drive",
              "28.VFD", "29.Wi-Fi Devices", "30.Wieght Checker_WC", "ALL SOP Mixing", "FMS", "Kepware"]
ACCENT_NAMES = {"Addverb Red": "#E8312F", "Corporate Blue": "#125CAA", "Teal": "#0F7B8A", "Green": "#1F8A4C", "Purple": "#6B4BB8", "Charcoal": "#37474F"}
FT_OTHER = ("Other file", "#90A4AE")
def ftype(name):
    ext = Path(name).suffix.lower()
    for k, (label, exts, col) in FT.items():
        if ext in exts:
            return k, label, col
    return "file", FT_OTHER[0], FT_OTHER[1]


# ------------------------------------------------------------------ database
_conn = None
_LOCK = threading.RLock()


def conn():
    global _conn
    if _conn is None:
        ROOT.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(DB), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        try:
            _conn.execute("PRAGMA synchronous=NORMAL")
            _conn.execute("PRAGMA temp_store=MEMORY")
        except sqlite3.Error:
            pass
    return _conn


_WQ = []          # small writes (activity log, preferences) wait here and are saved together - no disk wait on every click


def flush():
    """Save the waiting small writes in ONE transaction."""
    global _WQ
    with _LOCK:
        if not _WQ or _conn is None:
            return
        items, _WQ = _WQ, []
        try:
            c = conn()
            for sql, args in items:
                c.execute(sql, args)
            c.commit()
        except sqlite3.Error:
            pass


def close_db():
    global _conn
    flush()
    if _conn is not None:
        try:
            _conn.close()
        finally:
            _conn = None


def ex(sql, a=()):
    with _LOCK:
        c = conn()
        cur = c.execute(sql, a)
        rows = cur.fetchall()
        c.commit()
        return cur.lastrowid, rows


def q(sql, a=()):
    with _LOCK:
        return conn().execute(sql, a).fetchall()


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def log(user, action, detail=""):
    _WQ.append(("insert into logs(ts,user,action,detail) values(?,?,?,?)", (now(), user, action, detail)))


# ------------------------------------------------------------------ small helpers
def hashpw(p, salt=None):
    salt = salt or secrets.token_hex(8)
    return salt + "$" + hashlib.pbkdf2_hmac("sha256", p.encode(), salt.encode(), 200_000).hex()


def checkpw(p, s):
    try:
        return secrets.compare_digest(hashpw(p, s.split("$")[0]), s)
    except Exception:
        return False


def safe(s):
    return re.sub(r'[\\/:*?"<>|]+', "_", s).strip().rstrip(".") or "_"


def size(n):
    n = n or 0
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


def initials(name):
    p = [x for x in re.split(r"\s+", (name or "").strip()) if x]
    return ((p[0][0] + (p[-1][0] if len(p) > 1 else "")).upper()) if p else "?"


def is_hex(c):
    return bool(re.match(r"^#[0-9a-fA-F]{6}$", str(c or "")))


def pw_error(n, c, minlen=8):
    return f"The password needs at least {minlen} characters." if len(n) < minlen else "The two passwords do not match." if n != c else None


def fmt_date(s, style="ISO"):
    try:
        d = dt.datetime.strptime(s, "%Y-%m-%d %H:%M")
    except Exception:
        return s or ""
    return d.strftime({"ISO": "%Y-%m-%d %H:%M", "DMY": "%d-%m-%Y %H:%M", "Long": "%d %b %Y, %H:%M"}.get(style, "%Y-%m-%d %H:%M"))


def unique_path(folder, stem, ext):
    p = Path(folder) / (stem + ext)
    n = 2
    while p.exists():
        p = Path(folder) / f"{stem} ({n}){ext}"
        n += 1
    return p


def expand_paths(paths):
    """Files and the files inside dropped folders."""
    out = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            out += [f for f in p.rglob("*") if f.is_file() and not f.name.startswith(("~$", "."))]
        elif p.is_file():
            out.append(p)
    return out


def _ps(cmd, timeout=8):   # noqa
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd], capture_output=True, text=True, timeout=timeout, creationflags=flags)


def clip_files_set(paths):
    """Put real files on the Windows clipboard so Ctrl+V in Explorer / mail / chat pastes them."""
    if os.name != "nt" or not paths:
        return False
    try:
        return _ps("Set-Clipboard -LiteralPath " + ",".join("'" + str(p).replace("'", "''") + "'" for p in paths)).returncode == 0
    except Exception:
        return False


def clip_files_get():
    if os.name != "nt":
        return []
    try:
        r = _ps("Get-Clipboard -Format FileDropList | ForEach-Object { $_.FullName }")
        return [x.strip() for x in r.stdout.splitlines() if x.strip()] if r.returncode == 0 else []
    except Exception:
        return []


# ------------------------------------------------------------------ settings and preferences
DEFAULTS = {"app_name": "TDMS", "short_name": "TDMS", "company": "AFS", "subtitle": "Document Management System", "tagline": "Human | Robot | Possibilities",
            "brand_red": "#E8312F", "brand_blue": "#2E6DB4", "brand_navy": "#1F3A5F", "allow_signup": "1", "require_approval": "1", "email_domain": "",
            "min_password": "8", "auto_backup": "1", "max_mb": "0", "last_login": "", "last_admin": "admin", "login_bg": "ocean", "trash_days": "30"}


class Settings:
    def __init__(self):
        self.cache = {r["k"]: r["v"] for r in q("select k,v from settings")}

    def get(self, k, d=None):
        v = self.cache.get(k)
        if v is None or (v == "" and k in ("app_name", "short_name", "brand_red", "brand_blue", "brand_navy", "subtitle")):
            return DEFAULTS.get(k, "") if d is None else d
        return v

    def flag(self, k):
        return self.get(k) == "1"

    def set(self, k, v):
        ex("insert or replace into settings(k,v) values(?,?)", (k, str(v)))
        self.cache[k] = str(v)


class Prefs:
    def __init__(self):
        self.uid, self.d = None, {}

    def load(self, uid):
        self.uid = uid
        self.d = {r["k"]: r["v"] for r in q("select k,v from prefs where user_id=?", (uid,))} if uid else {}

    def get(self, k, d=""):
        return self.d.get(k, d)

    def set(self, k, v):
        if self.uid:
            _WQ.append(("insert or replace into prefs(user_id,k,v) values(?,?,?)", (self.uid, k, str(v))))
        self.d[k] = str(v)


# ------------------------------------------------------------------ schema
def init():
    ex("""create table if not exists users(id integer primary key, username text unique, name text, pw text, role text default 'user', active integer default 1)""")
    ex("create table if not exists categories(id integer primary key, name text, parent_id integer)")
    ex("""create table if not exists docs(id integer primary key, title text, category_id integer, filename text, stored text, size integer, uploader_id integer, created text)""")
    ex("create table if not exists logs(id integer primary key, ts text, user text, action text, detail text)")
    ex("create table if not exists settings(k text primary key, v text)")
    ex("create table if not exists prefs(user_id integer, k text, v text, primary key(user_id,k))")
    ex("create table if not exists favorites(user_id integer, doc_id integer, primary key(user_id,doc_id))")
    cols = lambda t: [r["name"] for r in q(f"pragma table_info({t})")]
    for c, t in (("question", "text"), ("answer", "text"), ("pending", "integer default 0"), ("emp_id", "text"), ("dept", "text"), ("designation", "text"),
                 ("email", "text"), ("phone", "text"), ("photo", "text"), ("created", "text"), ("must_change", "integer default 0")):
        if c not in cols("users"):
            ex(f"alter table users add column {c} {t}")
    for c in ("descr", "tags"):
        if c not in cols("docs"):
            ex(f"alter table docs add column {c} text")
    for c_, t_ in (("status", "text"), ("review", "text")):
        if c_ not in cols("docs"):
            ex(f"alter table docs add column {c_} {t_}")
    for c_, t_ in (("deleted", "integer default 0"), ("deleted_at", "text"), ("deleted_by", "integer"), ("trash", "text"), ("ver", "integer default 1"), ("updated_by", "integer"), ("vnote", "text"), ("appr_note", "text"), ("appr_by", "integer"), ("appr_at", "text")):
        if c_ not in cols("docs"):
            ex(f"alter table docs add column {c_} {t_}")
    ex("""create table if not exists versions(id integer primary key, doc_id integer, ver integer, stored text, filename text, size integer, uploader_id integer, created text, note text)""")
    ex("create index if not exists ix_ver_doc on versions(doc_id)")
    if "color" not in cols("categories"):
        ex("alter table categories add column color text")
    if "pos" not in cols("docs"):
        ex("alter table docs add column pos integer")
        ex("update docs set pos=id")
    if "sort" not in cols("categories"):
        ex("alter table categories add column sort integer")
        ex("update categories set sort=id")
    ex("update users set created=? where created is null", (now(),))
    ex("create index if not exists ix_docs_cat on docs(category_id)")
    ex("create index if not exists ix_docs_created on docs(created)")
    if not q("select 1 from users where role='admin'"):
        ex("insert into users(username,name,pw,role,created,must_change) values('admin','Administrator',?,'admin',?,1)", (hashpw("admin123"), now()))
    if not q("select 1 from categories"):
        for i, n in enumerate(CATEGORIES, 1):
            ex("insert into categories(name,parent_id,sort) values(?,NULL,?)", (n, i))


def daily_backup(settings):
    if not settings.flag("auto_backup"):
        return
    try:
        d = ROOT / "backups"
        d.mkdir(exist_ok=True)
        f = d / f"tdms_{dt.date.today():%Y%m%d}.db"
        if not f.exists():
            t = sqlite3.connect(str(f))
            conn().backup(t)
            t.close()
            for old in sorted(d.glob("tdms_*.db"))[:-10]:
                old.unlink()
    except Exception:
        pass


# ------------------------------------------------------------------ users
def find_users(login):
    k = (login or "").strip().lower()
    return q("select * from users where username=? or lower(email)=?", (k, k)) if k else []


def check_login(login, password):
    for u in find_users(login):
        if checkpw(password, u["pw"]):
            return u
    return None


def save_photo(uid, src):
    from PIL import Image, ImageOps
    PHOTOS.mkdir(exist_ok=True)
    ImageOps.fit(Image.open(src).convert("RGBA"), (256, 256)).save(PHOTOS / f"u{uid}.png")
    for old in PHOTOS.glob(f"u{uid}.*"):
        if old.name != f"u{uid}.png":
            old.unlink(missing_ok=True)
    ex("update users set photo=? where id=?", (f"u{uid}.png", uid))


def remove_photo(uid):
    for old in PHOTOS.glob(f"u{uid}.*"):
        old.unlink(missing_ok=True)
    ex("update users set photo=NULL where id=?", (uid,))


def round_photo(path, px, ring=None, ring_w=0):
    from PIL import Image, ImageDraw
    try:
        im = Image.open(path).convert("RGBA")
    except Exception:
        return None
    big = px * 4
    im = im.resize((big, big), Image.LANCZOS)
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, big - 1, big - 1], fill=255)
    out = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    if ring and ring_w:
        ImageDraw.Draw(out).ellipse([0, 0, big - 1, big - 1], outline=ring, width=ring_w * 4)
    return out.resize((px, px), Image.LANCZOS)


# ------------------------------------------------------------------ folders
def catpath(cid):
    parts = []
    while cid:
        r = q("select name,parent_id from categories where id=?", (cid,))[0]
        parts.insert(0, safe(r["name"]))
        cid = r["parent_id"]
    return Path(*parts)


def descendants(cid):
    out = {cid}
    for r in q("select id from categories where parent_id=?", (cid,)):
        out |= descendants(r["id"])
    return out


def folder_choices(exclude=(), top=False):
    out = [("(Top level)", None)] if top else []

    def walk(p, prefix):
        for r in q("select * from categories where parent_id is ? order by sort,id", (p,)):
            if r["id"] not in exclude:
                lab = prefix + r["name"]
                out.append((lab, r["id"]))
                walk(r["id"], lab + "  >  ")
    walk(None, "")
    return out


def relocate(cid, parent=..., name=None):
    """Rename and/or move a folder, on disk and in the database."""
    r = q("select * from categories where id=?", (cid,))[0]
    old = catpath(cid)
    np_ = r["parent_id"] if parent is ... else parent
    nn = name or r["name"]
    new = (catpath(np_) if np_ else Path()) / safe(nn)
    if new != old and (FILES / new).exists():
        raise ValueError("A folder with that name already exists there.")
    ex("update categories set parent_id=?, name=? where id=?", (np_, nn, cid))
    if new == old:
        return
    if (FILES / old).exists():
        (FILES / new).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(FILES / old), str(FILES / new))
    for d in q("select id,stored from docs"):
        sp = Path(d["stored"])
        if sp.parts[:len(old.parts)] == old.parts:
            ex("update docs set stored=? where id=?", (str(Path(*new.parts, *sp.parts[len(old.parts):])), d["id"]))


# ------------------------------------------------------------------ documents
DOC_SQL = ("select d.*, c.name cat, u.name who, (d.id in (select doc_id from favorites where user_id=?)) fav from docs d "
           "left join categories c on c.id=d.category_id left join users u on u.id=d.uploader_id")


def get_doc(did):
    r = q(DOC_SQL + " where d.id=?", (0, did))
    return r[0] if r else None


def doc_rows(view, search, uid, cat, sort=("title", False), admin=False):
    where, args = [], [uid]
    s = (search or "").strip()
    if view == "Recycle bin":
        where.append("d.deleted=1")
        if not admin:
            where.append("d.uploader_id=?")
            args.append(uid)
    else:
        where.append("d.deleted=0")
        if view == "My favorites":
            where.append("d.id in (select doc_id from favorites where user_id=?)")
            args.append(uid)
        elif view == "Added by me":
            where.append("d.uploader_id=?")
            args.append(uid)
        elif view.startswith("Recent"):
            where.append("d.created >= ?")
            args.append((dt.datetime.now() - dt.timedelta(days=30)).strftime("%Y-%m-%d %H:%M"))
        elif view == "Selected folder" and not s:
            where.append("d.category_id=?")
            args.append(cat or -1)
    if s:
        where.append("(d.title like ? or d.filename like ? or d.tags like ? or d.descr like ?)")
        args += [f"%{s}%"] * 4
    rows = q(DOC_SQL + " where " + " and ".join(where), tuple(args))
    key = {"title": lambda r: (r["title"] or "").lower(), "type": lambda r: ftype(r["filename"])[1], "cat": lambda r: (r["cat"] or "").lower(),
           "size": lambda r: r["size"] or 0, "by": lambda r: (r["who"] or "").lower(), "added": lambda r: (r["deleted_at"] if view == "Recycle bin" else r["created"]) or "",
           "pos": lambda r: (r["pos"] if r["pos"] is not None else r["id"], r["id"]), "status": lambda r: (r["status"] or "~")}[sort[0]]
    return sorted(rows, key=key, reverse=sort[1])


def find_same_name(cat, stem, ext):
    r = q(DOC_SQL + " where d.category_id=? and d.deleted=0 and lower(d.filename)=?", (0, cat, (safe(stem) + ext).lower()))
    return r[0] if r else None


def docs_stamp():
    """Changes whenever anything in the document list changes (used to skip needless redraws)."""
    r = q("select count(*) c, coalesce(max(id),0) m, coalesce(sum(size),0) s, coalesce(sum(deleted),0) d, coalesce(sum(ver),0) v, coalesce(max(created),'') t, "
          "coalesce(sum(length(title)+length(coalesce(tags,''))+length(coalesce(descr,''))+length(coalesce(status,''))+length(coalesce(review,''))+coalesce(category_id,0)"
          "+unicode(substr(title,1,1))+unicode(substr(title,-1))+unicode(substr(coalesce(status,' '),1,1))+cast(replace(coalesce(nullif(review,''),'0'),'-','') as integer)%100000),0) x from docs")[0]
    return (r["c"], r["m"], r["s"], r["d"], r["v"], r["t"], r["x"], q("select count(*) c from favorites")[0]["c"])


def copy_with_progress(src, dest, cb=None, chunk=4 * 1024 * 1024):
    """Copy a file in pieces so the window can stay alive; cb(bytes_just_copied) after each piece."""
    with open(src, "rb") as fi, open(dest, "wb") as fo:
        while True:
            buf = fi.read(chunk)
            if not buf:
                break
            fo.write(buf)
            if cb:
                cb(len(buf))
    try:
        shutil.copystat(src, dest)
    except OSError:
        pass


def add_files(cat, items, uid, progress=None):
    """items = [(source_path, title)].  progress(done_bytes, total_bytes, file_name).  Returns (added_count, problems)."""
    total = sum(Path(s).stat().st_size for s, _ in items if Path(s).exists())
    done = [0]
    folder = FILES / catpath(cat)
    folder.mkdir(parents=True, exist_ok=True)
    maxb = int(float(Settings().get("max_mb") or 0) * 1024 * 1024)
    added, bad, rows = 0, [], []
    pos = q("select coalesce(max(pos),0) m from docs where category_id=?", (cat,))[0]["m"]
    for src, title in items:
        src = Path(src)
        try:
            if maxb and src.stat().st_size > maxb:
                bad.append(f"{src.name}: bigger than the allowed size")
                continue
            dest = unique_path(folder, safe(title or src.stem), src.suffix)
            if progress:
                progress(done[0], total, src.name)
            def tick(n, name=src.name):
                done[0] += n
                if progress:
                    progress(done[0], total, name)
            copy_with_progress(src, dest, tick if progress else None)
            pos += 1
            rows.append((dest.stem, cat, dest.name, str(dest.relative_to(FILES)), dest.stat().st_size, uid, now(), pos))
            added += 1
        except Exception as e:
            bad.append(f"{src.name}: {e}")
    if rows:
        c = conn()
        c.executemany("insert into docs(title,category_id,filename,stored,size,uploader_id,created,pos) values(?,?,?,?,?,?,?,?)", rows)
        c.commit()
    return added, bad


def rename_doc(d, name):
    name = safe(name)
    if name == d["title"]:
        return None
    p = FILES / d["stored"]
    dest = p.with_name(name + Path(d["filename"]).suffix)
    if dest != p and dest.exists():
        return f"\"{dest.name}\" already exists in this folder."
    if p.exists():
        p.rename(dest)
    ex("update docs set title=?, filename=?, stored=? where id=?", (name, dest.name, str(dest.relative_to(FILES)), d["id"]))
    return None


def move_doc(d, cat):
    folder = FILES / catpath(cat)
    folder.mkdir(parents=True, exist_ok=True)
    p = FILES / d["stored"]
    dest = unique_path(folder, Path(d["filename"]).stem, Path(d["filename"]).suffix)
    if p.exists():
        shutil.move(str(p), str(dest))
    ex("update docs set category_id=?, filename=?, stored=?, pos=(select coalesce(max(pos),0)+1 from docs where category_id=?) where id=?", (cat, dest.name, str(dest.relative_to(FILES)), cat, d["id"]))


def trash_doc(d, uid):
    """Soft delete: the file goes to the Recycle bin folder and can be restored."""
    p = FILES / d["stored"]
    tdir = FILES / "_trash"
    tdir.mkdir(exist_ok=True)
    dest = tdir / f"{d['id']}_{d['filename']}"
    if p.exists():
        shutil.move(str(p), str(dest))
    ex("update docs set deleted=1, deleted_at=?, deleted_by=?, trash=? where id=?", (now(), uid, str(dest.relative_to(FILES)), d["id"]))


def restore_doc(d):
    src = FILES / (d["trash"] or "-")
    cat = d["category_id"]
    if not cat or not q("select 1 from categories where id=?", (cat,)):          # its folder was deleted: put it in "Restored documents"
        found = q("select id from categories where parent_id is NULL and name='Restored documents'")
        cat = found[0]["id"] if found else ex("insert into categories(name,parent_id,sort) values('Restored documents',NULL,(select coalesce(max(sort),0)+1 from categories where parent_id is NULL))")[0]
        folder = FILES / catpath(cat)
        folder.mkdir(parents=True, exist_ok=True)
        dest = unique_path(folder, Path(d["filename"]).stem, Path(d["filename"]).suffix)
    else:
        dest = FILES / d["stored"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest = unique_path(dest.parent, dest.stem, dest.suffix)
    if src.exists():
        shutil.move(str(src), str(dest))
    ex("update docs set deleted=0, deleted_at=NULL, deleted_by=NULL, trash=NULL, category_id=?, stored=?, filename=? where id=?", (cat, str(dest.relative_to(FILES)), dest.name, d["id"]))


def purge_doc(d):
    """Delete for good (file, old versions, favourites, record)."""
    if d["trash"]:
        (FILES / d["trash"]).unlink(missing_ok=True)
    (FILES / d["stored"]).unlink(missing_ok=True)
    vd = FILES / "_versions" / str(d["id"])
    if vd.exists():
        shutil.rmtree(vd, ignore_errors=True)
    for t in ("versions", "favorites"):
        ex(f"delete from {t} where doc_id=?", (d["id"],))
    ex("delete from docs where id=?", (d["id"],))


def auto_purge(days):
    try:
        cutoff = (dt.datetime.now() - dt.timedelta(days=max(1, int(days)))).strftime("%Y-%m-%d %H:%M")
        for d in q("select * from docs where deleted=1 and deleted_at < ?", (cutoff,)):
            purge_doc(d)
    except Exception:
        pass


# ------------------------------------------------------------------ version history
def versions_of(did):
    return q("select v.*, u.name who from versions v left join users u on u.id=v.uploader_id where v.doc_id=? order by v.ver desc", (did,))


def add_version(d, src, uid, note=""):
    """Keep the current file as an old version and make `src` the new current file."""
    src = Path(src)
    cur = FILES / d["stored"]
    ver = int(d["ver"] or 1)
    vdir = FILES / "_versions" / str(d["id"])
    vdir.mkdir(parents=True, exist_ok=True)
    arch = vdir / f"v{ver}_{d['filename']}"
    if cur.exists():
        shutil.move(str(cur), str(arch))
    ex("insert into versions(doc_id,ver,stored,filename,size,uploader_id,created,note) values(?,?,?,?,?,?,?,?)",
       (d["id"], ver, str(arch.relative_to(FILES)), d["filename"], arch.stat().st_size if arch.exists() else 0, d["updated_by"] or d["uploader_id"], d["created"], d["vnote"] or ""))
    dest = unique_path(cur.parent, safe(d["title"]), src.suffix)
    shutil.copy2(src, dest)
    ex("update docs set filename=?, stored=?, size=?, created=?, ver=?, updated_by=?, vnote=? where id=?",
       (dest.name, str(dest.relative_to(FILES)), dest.stat().st_size, now(), ver + 1, uid, note, d["id"]))


def restore_version(d, vrow, uid):
    add_version(d, FILES / vrow["stored"], uid, f"Restored from version {vrow['ver']}")


def toggle_fav(uid, did):
    if q("select 1 from favorites where user_id=? and doc_id=?", (uid, did)):
        ex("delete from favorites where user_id=? and doc_id=?", (uid, did))
    else:
        ex("insert into favorites(user_id,doc_id) values(?,?)", (uid, did))


# ------------------------------------------------------------------ dashboard numbers
def stats(uid):
    n = q("select count(*) c, coalesce(sum(size),0) s from docs where deleted=0")[0]
    return {"docs": n["c"], "size": n["s"], "folders": q("select count(*) c from categories")[0]["c"],
            "mine": q("select count(*) c from docs where uploader_id=? and deleted=0", (uid,))[0]["c"],
            "fav": q("select count(*) c from favorites f join docs d on d.id=f.doc_id where f.user_id=? and d.deleted=0", (uid,))[0]["c"],
            "users": q("select count(*) c from users where active=1")[0]["c"], "pending": q("select count(*) c from users where pending=1")[0]["c"],
            "trash": q("select count(*) c from docs where deleted=1")[0]["c"]}


def uploads_by_day(days=14):
    today = dt.date.today()
    per = {r["d"]: r["c"] for r in q("select substr(created,1,10) d, count(*) c from docs where deleted=0 and created >= ? group by d", ((today - dt.timedelta(days=days - 1)).isoformat(),))}
    return [(today - dt.timedelta(days=i), per.get((today - dt.timedelta(days=i)).isoformat(), 0)) for i in range(days - 1, -1, -1)]


def type_info(colors=None):
    info = {k: (v[0], (colors or {}).get(k) or v[2]) for k, v in FT.items()}
    info["file"] = (FT_OTHER[0], (colors or {}).get("file") or FT_OTHER[1])
    return info


def type_counts(colors=None):
    cnt = collections.Counter(ftype(r["filename"])[0] for r in q("select filename from docs where deleted=0"))
    info = type_info(colors)
    return [(info[k][0], n, info[k][1]) for k, n in cnt.most_common(8)]


def storage_by_type(colors=None):
    acc = collections.defaultdict(int)
    for r in q("select filename,size from docs where deleted=0"):
        acc[ftype(r["filename"])[0]] += r["size"] or 0
    info = type_info(colors)
    return [(info[k][0], round(v / 1048576, 1), info[k][1]) for k, v in sorted(acc.items(), key=lambda kv: -kv[1])[:8]]


def week_counts(n=12):
    today = dt.date.today()
    first = today - dt.timedelta(days=today.weekday()) - dt.timedelta(weeks=n - 1)
    per = collections.Counter()
    for r in q("select substr(created,1,10) d from docs where deleted=0 and created >= ?", (first.isoformat(),)):
        try:
            d = dt.date.fromisoformat(r["d"])
            per[d - dt.timedelta(days=d.weekday())] += 1
        except ValueError:
            pass
    return [(first + dt.timedelta(weeks=i), per.get(first + dt.timedelta(weeks=i), 0)) for i in range(n)]


def top_contributors(n=6):
    return [(r["nm"], r["n"]) for r in q("select u.name nm, count(*) n from docs d join users u on u.id=d.uploader_id where d.deleted=0 group by u.id order by n desc, u.name limit ?", (n,))]


def largest_files(n=6):
    return q(DOC_SQL + " where d.deleted=0 order by d.size desc limit ?", (0, n))


def recent_activity(n=8):
    flush()
    return q("select * from logs order by id desc limit ?", (n,))


def extra_stats():
    wk = (dt.date.today() - dt.timedelta(days=6)).isoformat()
    return {"week": q("select count(*) c from docs where deleted=0 and substr(created,1,10) >= ?", (wk,))[0]["c"], "versions": q("select count(*) c from versions")[0]["c"]}


def top_folders(n=6):
    return [(r["nm"], r["n"]) for r in q("select c.name nm, count(*) n from docs d join categories c on c.id=d.category_id where d.deleted=0 group by c.id order by n desc, c.name limit ?", (n,))]


def recent_docs(n=12):
    return q(DOC_SQL + " where d.deleted=0 order by d.id desc limit ?", (0, n))


# ------------------------------------------------------------------ readers: Word / PowerPoint / Excel (no extra packages)
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
DA = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
PP = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def read_docx(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    out = []

    def para(p):
        st = p.find(f"{W}pPr/{W}pStyle")
        style = (st.get(W + "val") if st is not None else "") or ""
        bullet = p.find(f"{W}pPr/{W}numPr") is not None
        runs = []
        for r in p.iter(W + "r"):
            t = "".join((x.text or "") if x.tag == W + "t" else "\t" if x.tag == W + "tab" else "\n" if x.tag == W + "br" else "" for x in r)
            if not t:
                continue
            rp = r.find(W + "rPr")
            b = rp is not None and rp.find(W + "b") is not None and rp.find(W + "b").get(W + "val") not in ("0", "false")
            i = rp is not None and rp.find(W + "i") is not None
            runs.append((t, b, i))
        return style, bullet, runs
    for el in root.find(W + "body"):
        if el.tag == W + "p":
            out.append(("p",) + para(el))
        elif el.tag == W + "tbl":
            out.append(("t", [["".join(t.text or "" for t in tc.iter(W + "t")) for tc in tr.findall(W + "tc")] for tr in el.iter(W + "tr")]))
    return out


def read_pptx(path):
    with zipfile.ZipFile(path) as z:
        names = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), key=lambda n: int(re.findall(r"\d+", n)[-1]))
        slides = []
        for n in names:
            items = []
            for sp in ET.fromstring(z.read(n)).iter(PP + "sp"):
                ph = sp.find(f"{PP}nvSpPr/{PP}nvPr/{PP}ph")
                title = ph is not None and ph.get("type") in ("title", "ctrTitle")
                for p in sp.iter(DA + "p"):
                    t = "".join(x.text or "" for x in p.iter(DA + "t")).strip()
                    if t:
                        items.append((title, t))
            slides.append(items)
    return slides


def xlsx_meta(path):
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            shared = ["".join(t.text or "" for t in si.iter(SS + "t")) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(SS + "si")]
        rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
        sheets = []
        for sh in ET.fromstring(z.read("xl/workbook.xml")).iter(SS + "sheet"):
            t = (rels.get(sh.get(RID)) or "").lstrip("/")
            sheets.append((sh.get("name"), t if t.startswith("xl/") else "xl/" + t))
    return sheets, shared


def xlsx_rows(path, target, shared, limit=3000):
    def ci(ref):
        n = 0
        for ch in re.match(r"[A-Z]+", ref).group():
            n = n * 26 + ord(ch) - 64
        return n - 1
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read(target))
    rows = []
    for row in root.iter(SS + "row"):
        cells = {}
        for c in row.findall(SS + "c"):
            t = c.get("t")
            v = c.find(SS + "v")
            if t == "s" and v is not None:
                val = shared[int(v.text)]
            elif t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter(SS + "t"))
            elif t == "b" and v is not None:
                val = "TRUE" if v.text == "1" else "FALSE"
            else:
                val = (v.text or "") if v is not None else ""
            cells[ci(c.get("r"))] = val.replace("\r", " ").replace("\n", " ")
        ri = int(row.get("r") or len(rows) + 1)
        while len(rows) < ri - 1 and len(rows) < limit:
            rows.append([])
        rows.append([cells.get(i, "") for i in range(max(cells) + 1)] if cells else [])
        if len(rows) >= limit:
            break
    return rows


def colname(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


# ------------------------------------------------------------------ add-ons (one-click install)
def pip_install(package):
    """Returns (ok, text).  Not possible inside the packaged .exe."""
    if FROZEN:
        return False, "This is the packaged .exe. Install the add-on with  pip install " + package + "  and rebuild it, or start the app with Run_App.bat."
    try:
        r = subprocess.run([sys.executable, "-m", "pip", "install", package], capture_output=True, text=True, timeout=600, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.returncode == 0, (r.stdout + "\n" + r.stderr)[-600:]
    except Exception as e:
        return False, str(e)


# ------------------------------------------------------------------ folder colour, document order, folder import, web links
def set_cat_color(cid, color):
    ex("update categories set color=? where id=?", (color or None, cid))


def reorder_docs(cat, ids, delta):
    """Move the selected documents one place up (-1) or down (+1) inside their folder."""
    order = [r["id"] for r in q("select id from docs where category_id=? and deleted=0 order by coalesce(pos,id), id", (cat,))]
    sel = set(ids)
    if delta < 0:
        for i in range(1, len(order)):
            if order[i] in sel and order[i - 1] not in sel:
                order[i - 1], order[i] = order[i], order[i - 1]
    else:
        for i in range(len(order) - 2, -1, -1):
            if order[i] in sel and order[i + 1] not in sel:
                order[i], order[i + 1] = order[i + 1], order[i]
    cn = conn()
    cn.executemany("update docs set pos=? where id=?", [(n, did) for n, did in enumerate(order, 1)])
    cn.commit()


def import_folder(src, parent_cat, uid, progress=None):
    """Copy a whole folder (with sub-folders) into the library as folders + documents.  -> (folder id, files added, problems)"""
    src = Path(src)
    name = src.name or "Imported folder"
    found = q("select id from categories where parent_id is ? and name=?", (parent_cat, name))
    cid = found[0]["id"] if found else ex("insert into categories(name,parent_id,sort) values(?,?,(select coalesce(max(sort),0)+1 from categories where parent_id is ?))", (name, parent_cat, parent_cat))[0]
    added, bad = 0, []
    files = [f for f in sorted(src.iterdir()) if f.is_file() and not f.name.startswith(("~$", "."))]
    if files:
        a, b = add_files(cid, [(f, None) for f in files], uid, progress)
        added += a
        bad += b
    for sub in sorted(p for p in src.iterdir() if p.is_dir() and not p.name.startswith(".")):
        _, a, b = import_folder(sub, cid, uid, progress)
        added += a
        bad += b
    return cid, added, bad


def read_url(path):
    p = Path(path)
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    if p.suffix.lower() == ".url":
        for line in txt.splitlines():
            if line.strip().lower().startswith("url="):
                return line.split("=", 1)[1].strip()
    elif p.suffix.lower() == ".webloc":
        m = re.search(r"<string>\s*([a-zA-Z]+://[^<\s]+)\s*</string>", txt)
        if m:
            return m.group(1)
    return None


def add_link(cat, name, url, uid, pending=False):
    folder = FILES / catpath(cat)
    folder.mkdir(parents=True, exist_ok=True)
    p = unique_path(folder, safe(name), ".url")
    p.write_text(f"[InternetShortcut]\nURL={url}\n", encoding="utf-8")
    pos = q("select coalesce(max(pos),0)+1 m from docs where category_id=?", (cat,))[0]["m"]
    ex("insert into docs(title,category_id,filename,stored,size,uploader_id,created,pos,deleted) values(?,?,?,?,?,?,?,?,?)", (p.stem, cat, p.name, str(p.relative_to(FILES)), p.stat().st_size, uid, now(), pos, PENDING if pending else 0))
    return p


def read_csv_rows(path, limit=5000):
    raw = Path(path).read_bytes()[:8_000_000]
    text = ""
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel_tab if Path(path).suffix.lower() == ".tsv" else csv.excel
    rows = []
    for row in csv.reader(io.StringIO(text), dialect):
        rows.append([x.replace("\r", " ").replace("\n", " ") for x in row])
        if len(rows) >= limit:
            break
    return rows


# ------------------------------------------------------------------ exact view of Office files (needs Microsoft Office on this PC)
def office_to_pdf(src, dst, timeout=180):
    ext = Path(src).suffix.lower()
    if os.name != "nt":
        raise RuntimeError("Exact view needs Windows with Microsoft Office.")
    s, d = str(src).replace("'", "''"), str(dst).replace("'", "''")
    if ext in (".doc", ".docx", ".rtf", ".odt"):
        script = (f"$ErrorActionPreference='Stop'; $a=New-Object -ComObject Word.Application; $a.Visible=$false; $a.DisplayAlerts=0; "
                  f"try {{ $x=$a.Documents.Open('{s}',$false,$true); $x.ExportAsFixedFormat('{d}',17); $x.Close(0) }} finally {{ $a.Quit() }}")
    elif ext in (".xls", ".xlsx", ".xlsm", ".xlsb"):
        script = (f"$ErrorActionPreference='Stop'; $a=New-Object -ComObject Excel.Application; $a.Visible=$false; $a.DisplayAlerts=$false; "
                  f"try {{ $x=$a.Workbooks.Open('{s}',0,$true); $x.ExportAsFixedFormat(0,'{d}'); $x.Close($false) }} finally {{ $a.Quit() }}")
    elif ext in (".ppt", ".pptx", ".pps", ".ppsx"):
        script = (f"$ErrorActionPreference='Stop'; $a=New-Object -ComObject PowerPoint.Application; "
                  f"try {{ $x=$a.Presentations.Open('{s}',-1,0,0); $x.SaveAs('{d}',32); $x.Close() }} finally {{ $a.Quit() }}")
    else:
        raise RuntimeError("This file type cannot be converted.")
    r = _ps(script, timeout=timeout)
    if r.returncode != 0 or not Path(dst).exists():
        msg = (r.stderr or r.stdout or "").strip()
        raise RuntimeError("Microsoft Office could not open this file." + (f"  ({msg[-160:]})" if msg else ""))


# ------------------------------------------------------------------ recycle bin count, folder tree removal, quick-review lists
def trash_count(uid, admin):
    return q("select count(*) c from docs where deleted=1" + ("" if admin else " and uploader_id=?"), () if admin else (uid,))[0]["c"]


def delete_folder_tree(cid, uid):
    """Move every document in the folder and its sub-folders to the Recycle bin, then remove the folders.  -> (documents, folders)"""
    ids = sorted(descendants(cid))
    base = FILES / catpath(cid)
    marks = ",".join("?" * len(ids))
    docs = q(f"select * from docs where deleted=0 and category_id in ({marks})", tuple(ids))
    for d in docs:
        trash_doc(d, uid)
    for d in q(f"select * from docs where deleted in (2,3) and category_id in ({marks})", tuple(ids)):      # uploads that were never approved go away with the folder
        purge_doc(d)
    ex(f"delete from categories where id in ({marks})", tuple(ids))
    for dp, _dn, _fn in os.walk(base, topdown=False):          # remove only the folders that are now empty
        try:
            os.rmdir(dp)
        except OSError:
            pass
    return len(docs), len(ids)


def logs_stamp():
    flush()
    return q("select coalesce(max(id),0) m from logs")[0]["m"]


def _docs_by_stored(rows):
    out = []
    for r in rows:
        d = q(DOC_SQL + " where d.stored=? and d.deleted=0", (0, r["detail"]))
        if d:
            out.append((d[0], r["c"] if "c" in r.keys() else 0))
    return out


def recent_opened(uid, n=7):
    flush()
    me = q("select username from users where id=?", (uid,))
    if not me:
        return []
    rows = q("select detail, max(id) m from logs where action='open' and user=? group by detail order by m desc limit 40", (me[0]["username"],))
    return [d for d, _ in _docs_by_stored(rows)][:n]


def most_opened(n=7):
    flush()
    rows = q("select detail, count(*) c from logs where action='open' group by detail order by c desc limit 40")
    return _docs_by_stored(rows)[:n]


def favorites_list(uid, n=7):
    return q(DOC_SQL + " where d.deleted=0 and d.id in (select doc_id from favorites where user_id=?) order by d.id desc limit ?", (uid, uid, n))


def week_compare():
    today = dt.date.today()
    a, b, c_ = (today - dt.timedelta(days=6)).isoformat(), (today - dt.timedelta(days=13)).isoformat(), (today - dt.timedelta(days=7)).isoformat()
    this = q("select count(*) c, coalesce(sum(size),0) s from docs where deleted=0 and substr(created,1,10) >= ?", (a,))[0]
    prev = q("select count(*) c from docs where deleted=0 and substr(created,1,10) >= ? and substr(created,1,10) <= ?", (b, c_))[0]["c"]
    return {"this": this["c"], "prev": prev, "mb": round((this["s"] or 0) / 1048576, 1)}


# ------------------------------------------------------------------ document status and review dates
def status_counts():
    cnt = collections.Counter((r["status"] or "") for r in q("select status from docs where deleted=0"))
    return [(s, cnt.get(s, 0), STATUS_COLORS[s]) for s in STATUSES[1:]] + [("No status", cnt.get("", 0), "#B0BEC5")]


def review_due(days=30, n=8):
    limit = (dt.date.today() + dt.timedelta(days=days)).isoformat()
    return q(DOC_SQL + " where d.deleted=0 and d.review is not null and d.review != '' and d.review <= ? order by d.review limit ?", (0, limit, n))


def valid_date(s):
    try:
        dt.date.fromisoformat(s)
        return True
    except ValueError:
        return False


def zip_documents(docs, dest):
    """Write the documents into a ZIP (one folder per library folder).  -> number of files"""
    used, n = set(), 0
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for d in docs:
            p = FILES / d["stored"]
            if not p.exists():
                continue
            arc = f"{safe(d['cat'] or 'Documents')}/{d['filename']}"
            i = 2
            while arc.lower() in used:
                arc = f"{safe(d['cat'] or 'Documents')}/{Path(d['filename']).stem} ({i}){Path(d['filename']).suffix}"
                i += 1
            used.add(arc.lower())
            z.write(p, arc)
            n += 1
    return n


# ------------------------------------------------------------------ helpers used by the web server
PENDING, REJECTED = 2, 3        # docs.deleted: 0 = in the library, 1 = Recycle bin, 2 = waiting for admin approval, 3 = rejected


class NameConflict(Exception):
    def __init__(self, doc):
        super().__init__("same name")
        self.doc = doc


def get_or_make_cat(parent, name):
    name = (name or "").strip() or "Folder"
    found = q("select id from categories where parent_id is ? and name=?", (parent, name))
    if found:
        return found[0]["id"]
    return ex("insert into categories(name,parent_id,sort) values(?,?,(select coalesce(max(sort),0)+1 from categories where parent_id is ?))", (name, parent, parent))[0]


def _spool(fileobj, dest, maxbytes=0, chunk=1024 * 1024):
    n = 0
    with open(dest, "wb") as fo:
        while True:
            buf = fileobj.read(chunk)
            if not buf:
                break
            n += len(buf)
            if maxbytes and n > maxbytes:
                fo.close()
                Path(dest).unlink(missing_ok=True)
                raise ValueError(f"The file is bigger than the allowed size ({size(maxbytes)}).")
            fo.write(buf)
    return n


def add_stream(cat, filename, fileobj, uid, title=None, mode=None, maxbytes=0, note="", pending=False):
    """Save an uploaded file.  mode: None (ask if the name exists) | 'version' | 'rename' | 'skip'.  -> (doc id, 'added'|'version'|'skipped')"""
    name = safe(Path(filename).name)
    stem, ext = Path(name).stem, Path(name).suffix
    same = find_same_name(cat, stem, ext)
    if same and mode is None:
        raise NameConflict(same)
    if same and mode == "skip":
        return same["id"], "skipped"
    if same and mode == "version":
        tmpdir = ROOT / "tmp"
        tmpdir.mkdir(exist_ok=True)
        tmp = tmpdir / f"up_{secrets.token_hex(6)}{ext}"
        try:
            _spool(fileobj, tmp, maxbytes)
            add_version(same, tmp, uid, note)
        finally:
            tmp.unlink(missing_ok=True)
        return same["id"], "version"
    folder = FILES / catpath(cat)
    folder.mkdir(parents=True, exist_ok=True)
    dest = unique_path(folder, safe(title or stem), ext)
    n = _spool(fileobj, dest, maxbytes)
    pos = q("select coalesce(max(pos),0)+1 m from docs where category_id=?", (cat,))[0]["m"]
    did = ex("insert into docs(title,category_id,filename,stored,size,uploader_id,created,pos,deleted) values(?,?,?,?,?,?,?,?,?)",
             (dest.stem, cat, dest.name, str(dest.relative_to(FILES)), n, uid, now(), pos, PENDING if pending else 0))[0]
    if not pending:                                  # a document that waits for approval is NOT sent to SharePoint yet
        push_to_sharepoint(dest, catpath(cat))
    return did, "added"


def prefs_of(uid):
    return {r["k"]: r["v"] for r in q("select k,v from prefs where user_id=?", (uid,))}


def set_pref(uid, k, v):
    ex("insert or replace into prefs(user_id,k,v) values(?,?,?)", (uid, k, str(v)))


def doc_dict(r, uid, admin):
    k, label, _ = ftype(r["filename"])
    return {"id": r["id"], "title": r["title"], "filename": r["filename"], "ext": Path(r["filename"]).suffix.lower(), "type": k, "type_label": label, "size": r["size"] or 0,
            "cat_id": r["category_id"], "cat": r["cat"] or "", "status": r["status"] or "", "review": r["review"] or "", "tags": r["tags"] or "", "descr": r["descr"] or "",
            "ver": r["ver"] or 1, "fav": bool(r["fav"]), "who": r["who"] or "", "uploader_id": r["uploader_id"], "created": r["created"] or "", "deleted_at": r["deleted_at"] or "",
            "pos": r["pos"], "can_edit": bool(admin or r["uploader_id"] == uid),
            "appr": {2: "pending", 3: "rejected"}.get(r["deleted"] or 0, ""), "appr_note": r["appr_note"] or ""}


def user_dict(u):
    return {"id": u["id"], "username": u["username"], "name": u["name"], "email": u["email"] or "", "emp_id": u["emp_id"] or "", "dept": u["dept"] or "", "designation": u["designation"] or "",
            "phone": u["phone"] or "", "role": u["role"], "active": bool(u["active"]), "pending": bool(u["pending"]), "has_photo": bool(u["photo"]), "has_question": bool(u["question"]),
            "created": u["created"] or ""}


# ------------------------------------------------------------------ approval of uploads
def pending_counts(uid):
    return {"docs": q("select count(*) c from docs where deleted=2")[0]["c"], "mine_pending": q("select count(*) c from docs where deleted=2 and uploader_id=?", (uid,))[0]["c"],
            "mine_rejected": q("select count(*) c from docs where deleted=3 and uploader_id=?", (uid,))[0]["c"]}


def approve_docs(ids, uid):
    n = 0
    for i in ids:
        if q("select 1 from docs where id=? and deleted in (2,3)", (i,)):
            ex("update docs set deleted=0, appr_by=?, appr_at=?, appr_note=NULL where id=?", (uid, now(), i))
            d = get_doc(i)
            if d:                                    # approved -> now send the copy to SharePoint
                push_to_sharepoint(FILES / d["stored"], Path(d["stored"]).parent.as_posix())
            n += 1
    return n


def reject_docs(ids, uid, reason=""):
    n = 0
    for i in ids:
        if q("select 1 from docs where id=? and deleted=2", (i,)):
            ex("update docs set deleted=3, appr_by=?, appr_at=?, appr_note=? where id=?", (uid, now(), (reason or "")[:300], i))
            n += 1
    return n


# ------------------------------------------------------------------ SharePoint copy (needs tdms_web.upload_to_sharepoint; does nothing in the desktop program)
_SP_LOCK = threading.Lock()


def push_to_sharepoint(path, folder):
    """Send a copy of a document to SharePoint in the background. One file at a time (big files use a lot of memory).
    A SharePoint problem is written to the Activity log and never breaks the upload or the approval."""
    sp_folder = str(folder).replace("\\", "/")

    def work():
        with _SP_LOCK:
            try:
                import tdms_web
            except ImportError:
                return                                  # desktop program: no SharePoint
            try:
                tdms_web.upload_to_sharepoint(Path(path), sp_folder)
            except Exception as e:
                print("SharePoint upload failed:", e)
                log("system", "SharePoint upload failed", f"{Path(path).name}: {e}"[:300])
    threading.Thread(target=work, daemon=True).start()
