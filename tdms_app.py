"""
TDMS  -  Technical Document Management System  (offline, one laptop)

  * Library   : folders on the left, documents on the right, open files inside tabs
  * Dashboard : charts of what has been uploaded
  * Admin     : Users, Activity log, Branding / Rules / Backup (Administrator sign-in only)
  * Drag and drop files in and out (built in), Ctrl+C / Ctrl+V of files, favourites, version history, recycle bin

Keep these files in ONE folder:
    tdms_app.py  tdms_core.py  tdms_graphics.py  tdms_widgets.py  tdms_admin.py  tdms_native.py  tdms_viewers.py  app_icon.ico  app_icon.png  logo.png
Run:   python tdms_app.py        (or Run_App.bat)
Needs: pip install pillow       (optional add-on:  pymupdf = PDF viewer)
"""
import os
import sys


def enable_dpi_awareness():
    if os.name != "nt":
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


enable_dpi_awareness()

import base64       # noqa: E402
import datetime as dt   # noqa: E402
import importlib    # noqa: E402
import re           # noqa: E402
import shutil      # noqa: E402
import subprocess   # noqa: E402
import time         # noqa: E402
import tkinter as tk    # noqa: E402
from pathlib import Path    # noqa: E402
from tkinter import filedialog, messagebox, ttk     # noqa: E402

FROZEN = getattr(sys, "frozen", False)
BASE = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
RES = getattr(sys, "_MEIPASS", BASE)
if not FROZEN:
    sys.path.insert(0, BASE)
    _missing = [f for f in ("tdms_admin.py", "tdms_core.py", "tdms_graphics.py", "tdms_widgets.py", "tdms_native.py", "tdms_viewers.py") if not os.path.exists(os.path.join(BASE, f))]
    if _missing:
        try:
            _r = tk.Tk()
            _r.withdraw()
            messagebox.showerror("TDMS - files are missing", "These files are not in the TDMS folder:\n\n    " + "\n    ".join(_missing) + "\n\nCopy them into the same folder as tdms_app.py and start again.\n\nFolder:  " + BASE)
        except Exception:
            print("Missing files:", _missing)
        sys.exit(1)

import tdms_admin as adm        # noqa: E402
import tdms_core as core        # noqa: E402
import tdms_graphics as g       # noqa: E402
import tdms_native as native   # noqa: E402
import tdms_viewers as viewers   # noqa: E402
import tdms_widgets as W        # noqa: E402
from tdms_widgets import P, px, FONT, RButton, Card, Field, PillGroup, TabBar, SearchBox, FormDialog, ask_yes_no   # noqa: E402

from tdms_viewers import ViewerMixin    # noqa: E402

APP_VERSION = core.VERSION
MAIN_KEYS = ("library", "dashboard", "users", "activity", "admin")
MAIN_COLORS = {"library": "#2E6DB4", "dashboard": "#00897B", "users": "#8E44AD", "activity": "#F28C1E", "admin": "#607D8B"}


def _timed(name):
    """Writes a line to tdms_perf.log when an action takes longer than 0.15 s (helps find what feels slow)."""
    def deco(fn):
        def wrap(*a, **k):
            t = time.perf_counter()
            try:
                return fn(*a, **k)
            finally:
                ms = (time.perf_counter() - t) * 1000
                if ms > 150:
                    try:
                        p = os.path.join(BASE, "tdms_perf.log")
                        if os.path.exists(p) and os.path.getsize(p) > 200_000:
                            os.remove(p)
                        with open(p, "a", encoding="utf-8") as f:
                            f.write(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}  {name:<18} {ms:7.0f} ms\n")
                    except Exception:
                        pass
        wrap.__name__ = fn.__name__
        return wrap
    return deco


def open_path(path):
    try:
        if os.name == "nt":
            os.startfile(str(path))
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as e:
        messagebox.showerror("Cannot open", f"No program is set up to open this.\n{e}")


class AppBase(ViewerMixin):
    """All the screens.  Mixed with tk.Tk."""

    def __init__(self):
        super().__init__()
        try:
            W.set_scale(max(1.0, min(3.0, float(self.tk.call("tk", "scaling")) / (96 / 72))))
        except Exception:
            W.set_scale(1.0)
        core.init()
        self.S = core.Settings()
        core.daily_backup(self.S)
        core.auto_purge(self.S.get("trash_days") or 30)
        self.prefs = core.Prefs()
        self.user = None
        self.pages, self.builders, self.hooks, self.mru, self.doc_keys = {}, {}, {}, [], {}
        self.current = None
        self.sort = ("pos", False)
        self._tc = {}
        self.login_mode = "user"
        self._refs, self._toast, self._idle_job, self._dash_job = {}, None, None, None
        self.last = time.time()
        self.drop_ok = False
        self.apply_brand("light")
        self.title(self.S.get("app_name"))
        try:
            sw, sh = int(self.winfo_screenwidth()), int(self.winfo_screenheight())
        except Exception:
            sw, sh = 1366, 768
        w, h = min(px(1320), sw - 40), min(px(820), sh - 80)
        x, y = max(0, (sw - w) // 2), max(0, (sh - h) // 4)
        m = re.match(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$", self.S.get("geometry", ""))
        if m:
            w, h = min(int(m.group(1)), sw - 20), min(int(m.group(2)), sh - 40)
            x, y = min(max(int(m.group(3)), 0), max(0, sw - 200)), min(max(int(m.group(4)), 0), max(0, sh - 150))
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(min(px(1040), sw - 40), min(px(640), sh - 80))
        self.set_icon()
        self.update_idletasks()
        self.style_titlebar()
        self.drop_ok = native.enable_drop(self, self.on_native_drop)
        self.bind_all("<KeyPress>", self.touch, add="+")
        self.bind_all("<Button>", self.touch, add="+")
        self.setup_wheel()
        self._ptr = (0, 0)
        self.after(2000, self.flush_loop)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_login()

    # ------------------------------------------------------------ small helpers
    def is_admin(self):
        return bool(self.user and self.user.get("role") == "admin")

    def log(self, action, detail=""):
        core.log(self.user["username"] if self.user else "-", action, detail)

    def toast(self, text, kind="ok", ms=3200):
        W.toast(self, text, kind, ms)

    def open_path(self, p):
        open_path(p)

    def setup_wheel(self):
        """Mouse wheel and two-finger touchpad scrolling that also works for small touchpad steps."""
        for cls in ("Treeview", "Text", "Listbox"):
            try:
                self.unbind_class(cls, "<MouseWheel>")
            except Exception:
                pass
        self._wacc = 0.0
        self.bind_all("<MouseWheel>", self.on_wheel, add="+")
        self.bind_all("<Shift-MouseWheel>", self.on_hwheel, add="+")

    def _scroll_target(self, e):
        try:
            w = self.winfo_containing(e.x_root, e.y_root)
        except Exception:
            return None
        while w is not None:
            if w.winfo_class() in ("Treeview", "Listbox", "Text"):
                return w
            w = getattr(w, "master", None)
        return None

    def on_wheel(self, e):
        if e.state & 4:                       # Ctrl = zoom, handled by the viewers
            return
        w = self._scroll_target(e)
        if w is not None:
            self._wacc += e.delta
            steps = int(self._wacc / 30)      # one mouse notch (120) = 4 rows; touchpad steps add up
            if steps:
                self._wacc -= steps * 30
                try:
                    w.yview_scroll(-steps, "units")
                except Exception:
                    pass

    def on_hwheel(self, e):
        w = self._scroll_target(e)
        if w is not None:
            try:
                w.xview_scroll(-1 if e.delta > 0 else 1, "units")
            except Exception:
                pass

    def flush_loop(self):
        core.flush()
        try:
            self.after(2000, self.flush_loop)
        except tk.TclError:
            pass

    def touch(self, _e=None):
        self.last = time.time()

    def report_callback_exception(self, exc, val, tb):
        import traceback
        text = "".join(traceback.format_exception(exc, val, tb))
        try:
            with open(os.path.join(BASE, "tdms_error.log"), "a", encoding="utf-8") as f:
                f.write(f"\n[{dt.datetime.now():%Y-%m-%d %H:%M:%S}]\n{text}")
        except Exception:
            pass
        try:
            self.toast(f"Something went wrong: {val}", "err", 6000)
        except Exception:
            pass

    def style_titlebar(self, color=None):
        """Colour the window title bar like the selected tab (Windows 11); the sign-in screen uses the brand navy."""
        color = color or P.NAVY
        if color == getattr(self, "_tb_color", None):
            return
        self._tb_color = color
        c = color.lstrip("#")
        lum = (0.299 * int(c[0:2], 16) + 0.587 * int(c[2:4], 16) + 0.114 * int(c[4:6], 16)) / 255
        native.set_titlebar(self, color, "#FFFFFF" if lum < 0.66 else "#1B2733", lum < 0.66)

    def restart(self):
        try:
            core.close_db()
        except Exception:
            pass
        try:
            subprocess.Popen([sys.executable] + ([] if FROZEN else [os.path.abspath(sys.argv[0])]))
        finally:
            self.destroy()
            os._exit(0)

    def on_close(self):
        try:
            if self.state() == "normal":
                self.S.set("geometry", self.geometry())
            core.close_db()
        finally:
            self.destroy()

    # ------------------------------------------------------------ branding / pictures
    def apply_brand(self, theme=None):
        s = self.S
        theme = theme or (self.prefs.get("theme", "light") if self.user else "light")
        acc = self.prefs.get("accent", "") if self.user else ""
        acc = core.ACCENT_NAMES.get(acc, acc)
        W.set_palette(theme, s.get("brand_red"), s.get("brand_blue"), s.get("brand_navy"), acc if core.is_hex(acc) else "")
        self.configure(bg=P.BG)

    def set_icon(self):
        ico, png = os.path.join(BASE, "app_icon.ico"), os.path.join(BASE, "app_icon.png")
        if not os.path.exists(ico):
            ico = os.path.join(RES, "app_icon.ico")
        if not os.path.exists(png):
            png = os.path.join(RES, "app_icon.png")
        try:
            if os.name == "nt" and os.path.exists(ico):
                self.iconbitmap(default=ico)
        except Exception:
            pass
        try:
            self._refs["icon"] = tk.PhotoImage(file=png) if os.path.exists(png) else W.photo_of(g.make_icon_image(256).resize((128, 128)))
            self.iconphoto(True, self._refs["icon"])
        except Exception:
            pass

    def logo_path(self):
        return g.find_logo(core.ROOT, core.BASE, core.RES)

    def logo_image(self, height):
        p = self.logo_path()
        if not p:
            return None
        try:
            from PIL import Image
            im = Image.open(p).convert("RGBA")
            bb = im.convert("RGB").point(lambda v: 255 - v).getbbox()
            if bb:
                im = im.crop(bb)
            h = px(height)
            im = im.resize((max(1, int(im.width * h / im.height)), h), Image.LANCZOS)
            return W.photo_of(im)
        except Exception:
            return None

    def app_icon_image(self, size):
        try:
            from PIL import Image
            ip = os.path.join(BASE, "app_icon.png")
            if not os.path.exists(ip):
                ip = os.path.join(RES, "app_icon.png")
            im = Image.open(ip).convert("RGBA") if os.path.exists(ip) else g.make_icon_image(256)
            return W.photo_of(im.resize((px(size), px(size)), Image.LANCZOS))
        except Exception:
            return None

    def avatar_image(self, size, u=None):
        u = u or self.user or {}
        n = px(size)
        if u.get("photo"):
            p = core.PHOTOS / u["photo"]
            if p.exists():
                im = core.round_photo(p, n, ring=P.ACCENT, ring_w=2)
                if im is not None:
                    return W.photo_of(im)
        return W.photo_of(g.initials_circle(n, core.initials(u.get("name", "")), P.ACCENT))

    def type_colors(self):
        return {k: self.prefs.get("fc_" + k) for k in list(core.FT) + ["file"] if core.is_hex(self.prefs.get("fc_" + k))}

    def type_color(self, key):
        return self._tc.get(key) or (core.FT[key][2] if key in core.FT else core.FT_OTHER[1])

    def compact(self):
        return bool(self.user) and self.prefs.get("compact", "0") == "1"

    def row_icon(self):
        return 16 if self.compact() else 22

    def ficon(self, key, size=22):
        col = self.type_color(key)
        return W.cached_photo(("ft", key, size, col), lambda: g.ft_icon(core.ICON_TEXT.get(key, "FILE"), col, px(size)))

    def folder_img(self, color=None):
        n = 16 if self.compact() else 20
        col = color if core.is_hex(color) else None
        return W.cached_photo(("folder", n, col or "-"), lambda: g.folder_icon(px(n), col))

    def style_ttk(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except Exception:
            pass
        cp = self.compact()
        st.configure("Treeview", rowheight=px(23 if cp else 30), font=(FONT, 9 if cp else 10), background=P.CARD, fieldbackground=P.CARD, foreground=P.INK, borderwidth=0)
        dark = P.theme == "dark"
        hbg = P.PILL if dark else P.NAVY
        st.configure("Treeview.Heading", font=(FONT, 9, "bold"), background=hbg, foreground=P.INK if dark else "#FFFFFF", relief="flat", padding=(px(10), px(8)))
        st.map("Treeview.Heading", background=[("active", g.mix(hbg, "#FFFFFF", 0.22))], foreground=[("active", P.INK if dark else "#FFFFFF")])
        st.map("Treeview", background=[("selected", P.BLUE)], foreground=[("selected", "#FFFFFF")])
        st.configure("TCombobox", padding=px(4), arrowsize=px(14), fieldbackground=P.FIELD, background=P.SOFT, foreground=P.INK, bordercolor=P.LINE, lightcolor=P.LINE, darkcolor=P.LINE, arrowcolor=P.INK)
        st.map("TCombobox", fieldbackground=[("readonly", P.FIELD)], foreground=[("readonly", P.INK)])
        for o in ("Vertical", "Horizontal"):
            st.configure(f"{o}.TScrollbar", background=P.SOFT, troughcolor=P.CARD, bordercolor=P.CARD, arrowcolor=P.MUTED)
        self.option_add("*TCombobox*Listbox.background", P.FIELD)
        self.option_add("*TCombobox*Listbox.foreground", P.INK)
        self.option_add("*TCombobox*Listbox.selectBackground", P.SEL)
        self.option_add("*TCombobox*Listbox.selectForeground", P.INK)

    # ------------------------------------------------------------ shell, header, tabs
    def build_shell(self, login=False):
        self._cancel_jobs()
        for w in self.winfo_children():
            w.destroy()
        self.pages, self.builders, self.hooks, self.mru, self.doc_keys, self.current = {}, {}, {}, [], {}, None
        self.mapped = set()
        self.configure(bg=P.BG)
        self.style_ttk()
        self.head = tk.Frame(self, bg=P.HEAD)
        left = tk.Frame(self.head, bg=P.HEAD)
        left.pack(side="left", padx=px(20), pady=px(8))
        self._refs["logo"] = self.logo_image(30)
        if self._refs["logo"]:
            tk.Label(left, image=self._refs["logo"], bg=P.HEAD).pack(side="left")
        else:
            tk.Label(left, text=self.S.get("company"), bg=P.HEAD, fg=P.RED, font=(FONT, 15, "bold")).pack(side="left")
        tk.Frame(left, bg=P.LINE, width=1, height=px(28)).pack(side="left", padx=px(14))
        self._refs["appicon"] = self.app_icon_image(32)
        if self._refs["appicon"]:
            tk.Label(left, image=self._refs["appicon"], bg=P.HEAD).pack(side="left", padx=(0, px(10)))
        nm = tk.Frame(left, bg=P.HEAD)
        nm.pack(side="left")
        tk.Label(nm, text=self.S.get("app_name"), bg=P.HEAD, fg=P.TITLE, font=(FONT, 14, "bold")).pack(anchor="w")
        tk.Label(nm, text=self.S.get("subtitle"), bg=P.HEAD, fg=P.MUTED, font=(FONT, 8)).pack(anchor="w")
        self.search_host = tk.Frame(self.head, bg=P.HEAD)
        self.search_host.pack(side="left", padx=px(26))
        self.head_right = tk.Frame(self.head, bg=P.HEAD)
        self.head_right.pack(side="right", padx=px(20), pady=px(6))
        self.accent_line = tk.Frame(self, bg=P.ACCENT, height=px(3))
        self.tabs_host = tk.Frame(self, bg=P.HEAD)
        self.foot = tk.Label(self, text=f"{self.S.get('app_name')}  v{APP_VERSION}", bg=P.BG, fg=P.MUTED, font=(FONT, 8), anchor="e", padx=px(16))
        if not login:
            self.head.pack(fill="x")
            self.accent_line.pack(fill="x")
            self.tabs_host.pack(fill="x")
            self.foot.pack(side="bottom", fill="x")
        self.body = tk.Frame(self, bg=P.BG)
        self.body.pack(fill="both", expand=True)

    def _cancel_jobs(self):
        for j in (self._idle_job, self._dash_job):
            if j:
                try:
                    self.after_cancel(j)
                except Exception:
                    pass
        self._idle_job = self._dash_job = None

    def refresh_header(self):
        for host in (self.head_right, self.search_host, self.tabs_host):
            for w in host.winfo_children():
                w.destroy()
        if not self.user:
            return
        self.gsearch = SearchBox(self.search_host, "Search all documents...", self.global_search, width=38)
        self.gsearch.pack()
        RButton(self.head_right, "Sign out", self.logout, "soft").pack(side="right", padx=(px(12), 0))
        RButton(self.head_right, "\u263E" if P.theme == "light" else "\u2600", self.toggle_theme, "soft", width=px(40)).pack(side="right", padx=(px(8), 0))
        box = tk.Frame(self.head_right, bg=P.HEAD, cursor="hand2")
        box.pack(side="right")
        self._refs["avatar"] = self.avatar_image(46)
        parts = [box]
        lb = tk.Label(box, image=self._refs["avatar"], bg=P.HEAD, cursor="hand2")
        lb.pack(side="left", padx=(0, px(10)))
        txt = tk.Frame(box, bg=P.HEAD, cursor="hand2")
        txt.pack(side="left")
        n = tk.Label(txt, text=self.user["name"], bg=P.HEAD, fg=P.INK, font=(FONT, 10, "bold"), anchor="w", cursor="hand2")
        n.pack(anchor="w")
        mail = self.user.get("email") or self.user["username"]
        em = tk.Label(txt, text=mail, bg=P.HEAD, fg=P.MUTED, font=(FONT, 8), anchor="w", cursor="hand2")
        em.pack(anchor="w")
        sub = (f"#{self.user['emp_id']}   |   " if self.user.get("emp_id") else "") + ("ADMINISTRATOR" if self.is_admin() else "USER")
        s = tk.Label(txt, text=sub, bg=P.HEAD, fg=P.ACCENT if self.is_admin() else P.BLUE, font=(FONT, 8, "bold"), anchor="w", cursor="hand2")
        s.pack(anchor="w")
        arrow = tk.Label(box, text="\u25BE", bg=P.HEAD, fg=P.MUTED, font=(FONT, 11), cursor="hand2")
        arrow.pack(side="left", padx=(px(8), 0))
        for w in parts + [lb, txt, n, em, s, arrow]:
            w.bind("<Button-1>", self.user_menu)
        tk.Frame(self.tabs_host, bg=P.LINE, height=1).pack(side="bottom", fill="x")
        self.tabbar = TabBar(self.tabs_host, self.show_page, self.close_page)
        self.tabbar.pack(side="left", padx=px(14))

    def user_menu(self, e=None):
        m = tk.Menu(self, tearoff=0, font=(FONT, 10), bg=P.CARD, fg=P.INK, activebackground=P.ACCENT, activeforeground="#FFFFFF", bd=0)
        m.add_command(label=self.user.get("email") or self.user["username"], state="disabled")
        m.add_separator()
        m.add_command(label="My profile and settings", command=lambda: self.open_profile())
        m.add_command(label="Change photo", command=self.pick_photo)
        m.add_command(label="Change password", command=self.change_password_dialog)
        m.add_command(label="Shortcuts and tips", command=self.show_help)
        m.add_separator()
        m.add_command(label="Sign out", command=self.logout)
        try:
            m.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            m.grab_release()

    def update_pending(self):
        tb = getattr(self, "tabbar", None)
        if not self.is_admin() or tb is None or "users" not in tb.tabs:
            return
        n = core.stats(0)["pending"]
        self.tabbar.rename("users", f"Users  ({n})" if n else "Users")

    def tab_imgs(self, kind, n=18):
        col = MAIN_COLORS.get(kind, "#607D8B")
        return (W.cached_photo(("tabi", kind, n, col), lambda: g.tab_icon(kind, px(n), col)), W.cached_photo(("tabw", kind, n), lambda: g.tab_icon(kind, px(n), "#FFFFFF")))

    def ficon_on(self, key, size=18):
        col = self.type_color(key)
        return W.cached_photo(("fti", key, size, col), lambda: g.ft_icon(core.ICON_TEXT.get(key, "FILE"), col, px(size), inverse=True))

    def add_page(self, key, title, builder, closable=False, image=None, hook=None, color=None, image_on=None):
        self.builders[key] = builder
        if hook:
            self.hooks[key] = hook
        if image is None and key in MAIN_COLORS:
            image, image_on = self.tab_imgs(key)
        self.tabbar.add(key, title, image, closable, color or MAIN_COLORS.get(key), image_on)

    def _unmap(self, key):
        if key != self.current and key in self.pages and key in self.mapped:
            self.pages[key].place_forget()
            self.mapped.discard(key)

    @_timed("show_page")
    def show_page(self, key):
        if key not in self.builders:
            return
        prev = self.current
        if key not in self.pages:
            try:
                f = self.builders[key](self.body)
            except Exception as e:
                self.report_callback_exception(type(e), e, e.__traceback__)
                return
            f.place(x=0, y=0, relwidth=1, relheight=1)
            self.pages[key] = f
            self.mapped.add(key)
            if key == "dashboard":
                f.lower()
                self.current = key
                try:
                    self.update_idletasks()
                    self.refresh_dashboard()
                    self.render_dash()
                    self.update_idletasks()
                except tk.TclError:
                    pass
        if key not in self.mapped:
            self.pages[key].place(x=0, y=0, relwidth=1, relheight=1)
            self.mapped.add(key)
        self.pages[key].lift()
        self.current = key
        if prev and prev != key and prev in self.pages:
            self.after_idle(lambda p=prev: self._unmap(p))
        self.tabbar.select(key)
        self.style_titlebar(self.tabbar.tabs[key]["color"])
        if key in self.mru:
            self.mru.remove(key)
        self.mru.append(key)
        h = self.hooks.get(key)
        if h:
            self.after_idle(h)

    def close_page(self, key):
        if key in MAIN_KEYS or key not in self.builders:
            return
        f = self.pages.pop(key, None)
        self.mapped.discard(key)
        if f is not None:
            f.destroy()
        self.builders.pop(key, None)
        self.hooks.pop(key, None)
        self.tabbar.remove(key)
        if key in self.mru:
            self.mru.remove(key)
        for did, k in list(self.doc_keys.items()):
            if k == key:
                del self.doc_keys[did]
        if self.current == key:
            self.current = None
            self.show_page(self.mru[-1] if self.mru else "library")

    def close_current(self):
        if self.current and self.current not in MAIN_KEYS:
            self.close_page(self.current)

    def close_doc_pages(self):
        for key in list(self.doc_keys.values()):
            self.close_page(key)

    def build_main_pages(self):
        self.add_page("library", "Library", self.build_library, hook=self.on_library_show)
        self.add_page("dashboard", "Dashboard", self.build_dashboard, hook=self.refresh_dashboard)
        if self.is_admin():
            self.add_page("users", "Users", lambda p: adm.UsersPage(self, p), hook=lambda: self.pages["users"].refresh())
            self.add_page("activity", "Activity", lambda p: adm.ActivityPage(self, p), hook=lambda: self.pages["activity"].refresh())
            self.add_page("admin", "Admin", lambda p: adm.AdminPage(self, p))
        self.update_pending()

    @_timed("rebuild")
    def rebuild(self, keep=None):
        """Draw everything again (after a theme / brand / colour change)."""
        self._tc = self.type_colors() if self.user else {}
        cur = keep or (self.current if self.current in MAIN_KEYS else "library")
        self.apply_brand()
        self.build_shell()
        self.refresh_header()
        self.build_main_pages()
        self.bind_keys()
        self._tb_color = None
        self.show_page(cur if cur in self.builders else "library")

    def bind_keys(self):
        self.bind("<Control-f>", lambda e: self.gsearch.focus())
        self.bind("<Control-n>", lambda e: self.add_docs_dialog() if self.current == "library" else None)
        self.bind("<Control-w>", lambda e: self.close_current())
        self.bind("<Control-Tab>", lambda e: self.next_tab())

    def next_tab(self):
        keys = self.tabbar.order
        if keys and self.current in keys:
            self.show_page(keys[(keys.index(self.current) + 1) % len(keys)])

    # ------------------------------------------------------------ login
    @_timed("show_login")
    def show_login(self, message=""):
        for k in ("<Control-f>", "<Control-n>", "<Control-w>", "<Control-Tab>"):
            self.unbind(k)
        self.user = None
        self._tc = {}
        self.prefs.load(None)
        self.apply_brand("light")
        self.build_shell(login=True)
        self.refresh_header()
        self._tb_color = None
        self.style_titlebar()
        s = self.S
        self.bg_label = tk.Label(self.body, bd=0, bg=P.BG)
        self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        self._bg_size, self._bg_job = None, None
        self.body.bind("<Configure>", lambda e: self.login_bg_later())
        card = Card(self.body)
        card.place(relx=0.5, rely=0.5, anchor="center")
        try:
            from PIL import Image
            lp = self.logo_path()
            logo = Image.open(lp).convert("RGBA") if lp else None
            hero = g.hero_panel(px(380), px(520), g.mix(P.NAVY, "#000000", 0.25), P.BLUE, P.ACCENT, s.get("app_name"), s.get("subtitle"),
                                ["Folders arranged your way", "PDF, Word, Excel, PowerPoint inside the app", "Drag and drop files in and out", "Works offline - data stays on this laptop"],
                                short=s.get("short_name"), logo=logo)
            self._refs["hero"] = W.photo_of(hero.convert("RGB"))
            tk.Label(card.body, image=self._refs["hero"], bd=0).pack(side="left")
        except Exception:
            pass
        form = tk.Frame(card.body, bg=P.CARD, padx=px(36), pady=px(26))
        form.pack(side="left", fill="y")
        tk.Label(form, text="Welcome back", bg=P.CARD, fg=P.TITLE, font=(FONT, 20, "bold")).pack(anchor="w")
        tk.Label(form, text="Sign in to continue.", bg=P.CARD, fg=P.MUTED, font=(FONT, 9)).pack(anchor="w", pady=(px(2), px(12)))
        seg = PillGroup(form, [("user", "User", P.PRIMARY), ("admin", "Administrator", P.PRIMARY)], command=lambda v: self.login_form(v))
        seg.pack(fill="x")
        seg.set(self.login_mode)
        self.login_host = tk.Frame(form, bg=P.CARD)
        self.login_host.pack(fill="x")
        self.login_form(self.login_mode, message)
        tk.Label(form, text=f"{s.get('app_name')}  v{APP_VERSION}", bg=P.CARD, fg=P.MUTED, font=(FONT, 8)).pack(side="bottom", anchor="e")
        self.bind("<Return>", lambda e: self.do_login())

    def login_bg_later(self):
        if getattr(self, "_bg_job", None):
            try:
                self.after_cancel(self._bg_job)
            except Exception:
                pass
        self._bg_job = self.after(120, self.draw_login_bg)

    def draw_login_bg(self):
        self._bg_job = None
        if self.user or not hasattr(self, "bg_label"):
            return
        try:
            w, h = self.body.winfo_width(), self.body.winfo_height()
            if w < 100 or h < 100 or (w, h) == self._bg_size:
                return
            self._bg_size = (w, h)
            im = g.login_background(w, h, self.S.get("login_bg") or "ocean", accent=self.S.get("brand_red"), blue=self.S.get("brand_blue"), navy=self.S.get("brand_navy"))
            self._refs["loginbg"] = W.photo_of(im)
            self.bg_label.configure(image=self._refs["loginbg"])
        except tk.TclError:
            pass

    def login_form(self, mode, message=""):
        self.login_mode = mode
        for w in self.login_host.winfo_children():
            w.destroy()
        box = self.login_host
        last = self.S.get("last_login" if mode == "user" else "last_admin", "")
        self.f_email = Field(box, "EMAIL ID" if mode == "user" else "ADMIN USER NAME OR EMAIL", width=32, value=last)
        self.f_email.pack(fill="x", pady=(px(14), 0))
        self.f_pass = Field(box, "PASSWORD", secret=True, width=32)
        self.f_pass.pack(fill="x", pady=(px(10), 0))
        self.remember = tk.BooleanVar(value=bool(last))
        row = tk.Frame(box, bg=P.CARD)
        row.pack(fill="x", pady=(px(8), 0))
        tk.Checkbutton(row, text="Remember me", variable=self.remember, bg=P.CARD, activebackground=P.CARD, fg=P.INK, selectcolor=P.FIELD, bd=0, highlightthickness=0,
                       font=(FONT, 9), cursor="hand2").pack(side="left")
        fp = tk.Label(row, text="Forgot username or password?", bg=P.CARD, fg=P.BLUE, cursor="hand2", font=(FONT, 9, "bold"))
        fp.pack(side="right")
        fp.bind("<Button-1>", lambda e: self.recover())
        self.login_err = tk.Label(box, text=message, bg=P.CARD, fg=P.ERR, font=(FONT, 9), anchor="w", justify="left", wraplength=px(320))
        self.login_err.pack(fill="x", pady=(px(6), 0))
        RButton(box, "Sign in", self.do_login, "main", big=True, width=px(318)).pack(fill="x", pady=(px(8), 0))
        if mode == "user" and self.S.flag("allow_signup"):
            tk.Frame(box, bg=P.LINE, height=1).pack(fill="x", pady=(px(16), px(10)))
            r2 = tk.Frame(box, bg=P.CARD)
            r2.pack(fill="x")
            tk.Label(r2, text="New user?", bg=P.CARD, fg=P.MUTED, font=(FONT, 9)).pack(side="left")
            link = tk.Label(r2, text="Create account", bg=P.CARD, fg=P.BLUE, cursor="hand2", font=(FONT, 9, "bold"))
            link.pack(side="left", padx=(px(6), 0))
            link.bind("<Button-1>", lambda e: self.create_account())
        (self.f_pass if last else self.f_email).entry.focus_set()

    def do_login(self):
        login, pw = self.f_email.get(), self.f_pass.raw()
        if not login or not pw:
            return self.login_err.configure(text="Enter your email ID and password.")
        u = core.check_login(login, pw)
        if not u:
            core.log(login[:60], "failed login")
            return self.login_err.configure(text="Wrong email ID or password.")
        if u["pending"]:
            return self.login_err.configure(text="Your account is waiting for admin approval.")
        if not u["active"]:
            return self.login_err.configure(text="This account is disabled. Ask your admin.")
        if self.login_mode == "admin" and u["role"] != "admin":
            return self.login_err.configure(text="This account is not an administrator. Use the User tab.")
        if self.login_mode == "user" and u["role"] == "admin":
            return self.login_err.configure(text="Administrators sign in on the Administrator tab.")
        self.S.set("last_login" if self.login_mode == "user" else "last_admin", login.lower() if self.remember.get() else "")
        self.sign_in(dict(u))

    def sign_in(self, u):
        self.unbind("<Return>")
        self.user = u
        self.prefs.load(u["id"])
        self.log("login")
        self.rebuild("dashboard" if self.prefs.get("start_dash") == "1" else "library")
        self.last = time.time()
        self.idle_check()
        self.after(350, self.first_run_checks)

    def first_run_checks(self):
        u = self.user
        if not u:
            return
        if self.is_admin() and core.checkpw("admin123", u["pw"]):
            messagebox.showwarning("Change the admin password", "The admin password is still the default (admin123).\nPlease change it now.")
            self.change_password_dialog()
        if not u.get("question"):
            self.set_question_dialog(first=True)
        n = core.stats(0)["pending"] if self.is_admin() else 0
        if n:
            self.toast(f"{n} account request(s) are waiting in the Users tab.", "warn", 6000)

    def logout(self):
        if self.user:
            self.log("logout")
        core.flush()
        self.show_login()

    def idle_check(self):
        if not self.user:
            return
        try:
            p = (self.winfo_pointerx(), self.winfo_pointery())
            if p != self._ptr:
                self._ptr, self.last = p, time.time()
        except tk.TclError:
            pass
        m = int(self.prefs.get("idle", "0") or 0)
        if m and time.time() - self.last > m * 60:
            self._idle_job = None
            self.show_login(f"You were signed out after {m} minutes of inactivity.")
            return
        self._idle_job = self.after(15000, self.idle_check)

    # ------------------------------------------------------------ account dialogs
    def create_account(self):
        s = self.S
        dom = s.get("email_domain").strip().lstrip("@").lower()
        minlen = int(s.get("min_password") or 8)
        appr = s.flag("require_approval")

        def check(v):
            e = v["email"].lower()
            if not v["name"] or not v["an"]:
                return "Please fill in your name and the security answer."
            if not core.EMAIL_RE.fullmatch(e):
                return "Please enter a valid email ID, for example name@company.com."
            if dom and not e.endswith("@" + dom):
                return f"Please use your company email (@{dom})."
            if core.q("select 1 from users where username=? or lower(email)=?", (e, e)):
                return "That email ID is already registered."
            return core.pw_error(v["pw"], v["pw2"], minlen)
        v = FormDialog(self, "Create account", [("name", "FULL NAME", "text", "", ""), ("email", "EMAIL ID (YOUR SIGN-IN NAME)", "text", "", f"Use your @{dom} address" if dom else ""),
                                                ("emp", "EMPLOYEE ID", "text", "", ""), ("dept", "DEPARTMENT", "text", "", ""), ("pw", "PASSWORD", "secret", "", f"At least {minlen} characters"),
                                                ("pw2", "CONFIRM PASSWORD", "secret", "", ""), ("qn", "SECURITY QUESTION", "combo", core.QUESTIONS, ""), ("an", "YOUR ANSWER", "secret", "", "Used to recover your account")],
                       ok="Create account", intro="An admin will approve your account before you can sign in." if appr else "", validate=check, width=480).run()
        if not v:
            return
        e = v["email"].lower()
        core.ex("insert into users(username,name,pw,role,active,pending,question,answer,emp_id,dept,email,created) values(?,?,?,'user',?,?,?,?,?,?,?,?)",
                (e, v["name"], core.hashpw(v["pw"]), 0 if appr else 1, 1 if appr else 0, v["qn"], core.hashpw(v["an"].strip().lower()), v["emp"], v["dept"], e, core.now()))
        core.log(e, "account requested" if appr else "account created")
        if appr:
            self.login_form("user", "Request sent. Your admin will approve it, then you can sign in.")
        else:
            self.f_email.set(e)
            self.login_err.configure(fg=P.GREEN, text="Account created. Sign in with your email ID and password.")

    def recover(self):
        v = FormDialog(self, "Recover your account", [("u", "EMAIL ID OR EMPLOYEE ID", "text", self.f_email.get(), "")], ok="Next",
                       intro="Forgot your username or password? Enter your email ID or employee ID. You will be asked your security question.").run()
        if not v:
            return
        key = v["u"].lower()
        r = core.q("select * from users where (username=? or lower(email)=? or lower(emp_id)=?) and active=1", (key, key, key)) if key else []
        if not r or not r[0]["question"]:
            return messagebox.showinfo("Cannot recover here", "No account with a security question was found for that.\nAsk your admin to reset your password.")
        r = r[0]
        minlen = int(self.S.get("min_password") or 8)

        def check(x):
            if not core.checkpw(x["a"].strip().lower(), r["answer"]):
                core.log(r["username"], "failed recovery")
                return "That answer is not correct."
            return core.pw_error(x["n"], x["c"], minlen) if (x["n"] or x["c"]) else None
        x = FormDialog(self, "Verify it is you", [("a", "YOUR ANSWER", "secret", "", r["question"]), ("n", "NEW PASSWORD (OPTIONAL)", "secret", "", "Leave both password boxes empty to only see your username"),
                                                  ("c", "CONFIRM NEW PASSWORD", "secret", "", "")], ok="Verify", validate=check).run()
        if not x:
            return
        if x["n"]:
            core.ex("update users set pw=? where id=?", (core.hashpw(x["n"]), r["id"]))
            core.log(r["username"], "password reset (question)")
            messagebox.showinfo("Account recovered", f"Your username is:  {r['username']}\n\nYour password was changed. You can sign in now.")
        else:
            messagebox.showinfo("Your username", f"Your username is:  {r['username']}")

    def change_password_dialog(self):
        minlen = int(self.S.get("min_password") or 8)

        def check(v):
            if not core.checkpw(v["cur"], self.user["pw"]):
                return "Your current password is wrong."
            return core.pw_error(v["n"], v["c"], minlen)
        v = FormDialog(self, "Change password", [("cur", "CURRENT PASSWORD", "secret", "", ""), ("n", "NEW PASSWORD", "secret", "", f"At least {minlen} characters"), ("c", "CONFIRM NEW PASSWORD", "secret", "", "")],
                       ok="Change password", validate=check).run()
        if v:
            self.user["pw"] = core.hashpw(v["n"])
            core.ex("update users set pw=? where id=?", (self.user["pw"], self.user["id"]))
            self.log("password changed")
            self.toast("Password changed.")

    def set_question_dialog(self, first=False):
        def check(v):
            if not core.checkpw(v["cur"], self.user["pw"]):
                return "Your password is wrong."
            return None if v["an"].strip() else "Type your answer."
        v = FormDialog(self, "Security question", [("cur", "YOUR PASSWORD", "secret", "", ""), ("qn", "SECURITY QUESTION", "combo", (core.QUESTIONS, self.user.get("question") or core.QUESTIONS[0]), ""),
                                                   ("an", "YOUR ANSWER", "secret", "", "")], ok="Save",
                       intro="Used to recover your username or password if you forget it." + ("  You can skip this and set it later in your profile." if first else ""), validate=check).run()
        if v:
            core.ex("update users set question=?, answer=? where id=?", (v["qn"], core.hashpw(v["an"].strip().lower()), self.user["id"]))
            self.user["question"] = v["qn"]
            self.log("security question set")
            self.toast("Security question saved.")

    def pick_photo(self, uid=None):
        f = filedialog.askopenfilename(title="Choose a photo", filetypes=[("Pictures", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"), ("All files", "*.*")])
        if not f:
            return False
        try:
            core.save_photo(uid or self.user["id"], f)
        except Exception as e:
            self.toast(f"Could not use that picture: {e}", "err")
            return False
        self.after_user_change(uid or self.user["id"])
        return True

    def after_user_change(self, uid):
        if self.user and uid == self.user["id"]:
            self.user = dict(core.q("select * from users where id=?", (uid,))[0])
            self.refresh_header_only()
        if "users" in self.pages:
            self.pages["users"].refresh()

    def refresh_header_only(self):
        keep = self.current
        self.refresh_header()
        self.build_tabs_again(keep)

    def build_tabs_again(self, keep):
        """Header was redrawn: put the tabs back (pages stay as they are)."""
        for key in list(self.builders):
            title = {"library": "Library", "dashboard": "Dashboard", "users": "Users", "activity": "Activity", "admin": "Admin"}.get(key)
            if title:
                ic, on = self.tab_imgs(key)
                self.tabbar.add(key, title, ic, False, MAIN_COLORS.get(key), on)
            else:
                d = core.get_doc(int(key.split(":")[1])) if key.startswith("doc:") else None
                kk = core.ftype(d["filename"])[0] if d else "file"
                self.tabbar.add(key, (d["title"][:30] if d else key), self.ficon(kk, 18) if d else None, True, self.type_color(kk), self.ficon_on(kk) if d else None)
        if keep:
            self.tabbar.select(keep)
        self.update_pending()

    # ------------------------------------------------------------ library page
    @_timed("build_library")
    def build_library(self, parent):
        page = tk.Frame(parent, bg=P.BG)
        wrap = tk.Frame(page, bg=P.BG)
        wrap.pack(fill="both", expand=True, padx=px(10), pady=px(8))
        wrap.columnconfigure(1, weight=1)
        wrap.rowconfigure(0, weight=1)
        admin = self.is_admin()
        self.fc = Card(wrap)
        self.fc.grid(row=0, column=0, sticky="ns", padx=(0, px(10)))
        self.fc.configure(width=px(262))
        self.fc.pack_propagate(False)
        self.fc.body.configure(padx=px(10), pady=px(8))
        fb = self.fc.body
        head = tk.Frame(fb, bg=P.CARD)
        head.pack(fill="x", pady=(0, px(6)))
        tk.Label(head, text="Folders", bg=P.CARD, fg=P.TITLE, font=(FONT, 12, "bold")).pack(side="left")
        if admin:
            mb = RButton(head, "Manage  \u25BE", None, "soft")
            mb.pack(side="right")
            mb.command = lambda: adm.popup(mb, self.folder_menu_items())
        # Recycle bin: always visible at the bottom of the folder list
        self.bin_row = tk.Frame(fb, bg=P.CARD, cursor="hand2")
        self.bin_row.pack(side="bottom", fill="x", pady=(px(6), 0))
        tk.Frame(self.bin_row, bg=P.LINE, height=1).pack(fill="x")
        brow = tk.Frame(self.bin_row, bg=P.CARD, cursor="hand2")
        brow.pack(fill="x", pady=(px(4), 0))
        self._bin_ico = W.photo_of(g.trash_icon(px(22), "#E0713F"), ("trash", 22))
        bi = tk.Label(brow, image=self._bin_ico, bg=P.CARD, cursor="hand2")
        bi.pack(side="left", padx=(px(6), px(8)), pady=px(5))
        bt = tk.Label(brow, text="Recycle bin", bg=P.CARD, fg=P.INK, font=(FONT, 10), cursor="hand2")
        bt.pack(side="left")
        self.bin_count = tk.Label(brow, text="", bg=P.CARD, fg=P.MUTED, font=(FONT, 9, "bold"), cursor="hand2")
        self.bin_count.pack(side="right", padx=px(8))
        self.bin_parts = [self.bin_row, brow, bi, bt, self.bin_count]
        for w_ in self.bin_parts:
            w_.bind("<Button-1>", lambda e: self.show_bin())
        th = tk.Frame(fb, bg=P.CARD)
        th.pack(fill="both", expand=True)
        self.ct = ttk.Treeview(th, show="tree", selectmode="browse")
        sb = ttk.Scrollbar(th, command=self.ct.yview)
        self.ct.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.ct.pack(side="left", fill="both", expand=True)
        rc = Card(wrap)
        rc.grid(row=0, column=1, sticky="nsew")
        rc.body.configure(padx=px(10), pady=px(8))
        rb = rc.body
        v0 = self.prefs.get("view", core.VIEWS[0])
        self.view = tk.StringVar(value=v0 if v0 in core.VIEWS[:-1] else core.VIEWS[0])
        lab = self.prefs.get("order", next(iter(core.ORDERS)))
        self.sort = core.ORDERS.get(lab, ("pos", False))
        self.order = tk.StringVar(value=lab if lab in core.ORDERS else next(iter(core.ORDERS)))
        self.v_compact = tk.BooleanVar(value=self.compact())
        self.v_details = tk.BooleanVar(value=self.prefs.get("details", "1") == "1")
        self.v_folders = tk.BooleanVar(value=self.prefs.get("folders_hidden", "0") != "1")
        self.v_preview = tk.BooleanVar(value=self.prefs.get("preview", "0") == "1")
        cols = (("type", "Type", 150), ("status", "Status", 110), ("cat", "Folder", 200), ("size", "Size", 90), ("by", "Added by", 150), ("added", "Added", 160))
        if self.prefs.get("cols_v") != "7":
            cs = self.prefs.get("cols", "type,cat,size,by,added").split(",")
            if "status" not in cs:
                cs.insert(1 if "type" in cs else 0, "status")
            self.prefs.set("cols", ",".join(cs))
            self.prefs.set("cols_v", "7")
        shown0 = self.prefs.get("cols", "type,status,cat,size,by,added").split(",")
        self.v_cols = {k: tk.BooleanVar(value=k in shown0) for k, _, _ in cols}
        # one slim row of tools (everything else is in View / More)
        tb = tk.Frame(rb, bg=P.CARD)
        tb.pack(fill="x")
        self.search = SearchBox(tb, "Search in library...", lambda t: self.load_docs(), width=22)
        self.search.pack(side="left")
        self.search.var.trace_add("write", lambda *a: self.search_later())
        vb = RButton(tb, "View  \u25BE", None, "soft")
        vb.pack(side="left", padx=(px(8), 0))
        vb.command = lambda: self.view_menu(vb)
        RButton(tb, "Folders", lambda: (self.v_folders.set(not self.v_folders.get()), self.toggle_folders()), "soft").pack(side="left", padx=(px(6), 0))
        mb2 = RButton(tb, "More  \u25BE", None, "soft")
        mb2.pack(side="right")
        mb2.command = lambda: adm.popup(mb2, self.more_items())
        RButton(tb, "Delete", self.delete_docs, "danger").pack(side="right", padx=(0, px(6)))
        RButton(tb, "\u2713 All", self.select_all, "soft", width=px(54)).pack(side="right", padx=(0, px(6)))
        RButton(tb, "\u25BC", lambda: self.move_docs_pos(1), "soft", width=px(38)).pack(side="right", padx=(0, px(4)))
        RButton(tb, "\u25B2", lambda: self.move_docs_pos(-1), "soft", width=px(38)).pack(side="right", padx=(0, px(4)))
        RButton(tb, "\u2605", self.toggle_fav, "soft", width=px(38)).pack(side="right", padx=(0, px(6)))
        RButton(tb, "Open", self.open_sel, "navy").pack(side="right", padx=(0, px(6)))
        ab = RButton(tb, "+ Add  \u25BE", None, "main")
        ab.pack(side="right", padx=(0, px(6)))
        ab.command = lambda: adm.popup(ab, [("Documents...", self.add_docs_dialog), ("A folder with its files...", self.add_folder_dialog), ("A web link...", self.add_link_dialog)]
                                   + ([(None, None), ("New empty folder...", lambda: self.add_cat(False)), ("New empty subfolder...", lambda: self.add_cat(True))] if self.is_admin() else []))
        cr = tk.Frame(rb, bg=P.CARD)
        cr.pack(fill="x", pady=(px(8), px(4)))
        self.crumb_box = tk.Frame(cr, bg=P.CARD)
        self.crumb_box.pack(side="left")
        self.count = tk.Label(cr, text="", bg=P.CARD, fg=P.MUTED, font=(FONT, 9))
        self.count.pack(side="left", padx=px(10))
        self.tfilter = "all"
        self.chips = PillGroup(cr, [("all", "All", P.PRIMARY), ("pdf", "PDF", self.type_color("pdf")), ("doc", "Word", self.type_color("doc")), ("xls", "Excel", self.type_color("xls")),
                                    ("ppt", "PPT", self.type_color("ppt")), ("img", "Images", self.type_color("img")), ("vid", "Video", self.type_color("vid")), ("link", "Links", self.type_color("link"))],
                               command=self.set_tfilter)
        self.chips.pack(side="right")
        self.chips.set("all")
        mid = tk.Frame(rb, bg=P.CARD)
        mid.pack(fill="both", expand=True)
        mid.columnconfigure(0, weight=1)
        mid.rowconfigure(0, weight=1)
        th2 = tk.Frame(mid, bg=P.CARD)
        th2.grid(row=0, column=0, sticky="nsew")
        self.pv = tk.Frame(mid, bg=P.TILE, width=px(300))
        self.pv.grid(row=0, column=1, sticky="ns", padx=(px(8), 0))
        self.pv.grid_propagate(False)
        self.build_preview()
        if not self.v_preview.get():
            self.pv.grid_remove()
        self.dt = ttk.Treeview(th2, columns=[c[0] for c in cols], show="tree headings", selectmode="extended")
        vs = ttk.Scrollbar(th2, command=self.dt.yview)
        hs = ttk.Scrollbar(th2, orient="horizontal", command=self.dt.xview)
        self.dt.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.dt.heading("#0", text="Name", anchor="w", command=lambda: self.sort_by("title"))
        self.dt.column("#0", width=px(560), minwidth=px(240), anchor="w", stretch=True)
        for k, t, w in cols:
            self.dt.heading(k, text=t, anchor="w", command=lambda k=k: self.sort_by(k))
            self.dt.column(k, width=px(w), minwidth=px(70), anchor="w", stretch=False)
        self.dt.configure(displaycolumns=[k for k, _, _ in cols if self.v_cols[k].get()] or ["type"])
        self.dt.tag_configure("odd", background=P.TILE)
        for tk_ in list(core.FT) + ["file"]:                     # optional: a very soft colour of each file type behind its row
            c_ = self.type_color(tk_)
            self.dt.tag_configure("t_" + tk_, background=g.mix(c_, P.CARD, 0.94))
            self.dt.tag_configure("t_" + tk_ + "o", background=g.mix(c_, P.CARD, 0.89))
        self.dt.tag_configure("sel", background=P.BLUE, foreground="#FFFFFF")          # created last = strongest, so the selected rows always show
        self._hov, self._dt_sig = "", None
        hs.pack(side="bottom", fill="x")
        vs.pack(side="right", fill="y")
        self.dt.pack(side="left", fill="both", expand=True)
        self.empty = tk.Label(th2, bg=P.CARD, fg=P.MUTED, justify="center", font=(FONT, 12))
        self.det = tk.Label(rb, text="", bg=P.CARD, fg=P.MUTED, font=(FONT, 9), anchor="w", justify="left")
        if self.v_details.get():
            self.det.pack(fill="x", pady=(px(4), 0))
        if not self.v_folders.get():
            self.fc.grid_remove()
        self.dt.bind("<Double-1>", lambda e: self.open_sel() if self.dt.identify_region(e.x, e.y) not in ("heading", "separator") else None)
        self.dt.bind("<Return>", lambda e: self.open_sel())
        self.dt.bind("<Delete>", lambda e: self.delete_docs())
        self.dt.bind("<F2>", lambda e: self.rename_doc())
        self.dt.bind("<Control-c>", lambda e: self.copy_files())
        self.dt.bind("<Control-v>", lambda e: self.paste_files())
        self.dt.bind("<Control-a>", lambda e: (self.dt.selection_set(self.dt.get_children()), "break")[1])
        self.dt.bind("<<TreeviewSelect>>", lambda e: self.show_details())
        self.dt.bind("<Button-3>", lambda e: self.doc_context(e))
        self.ct.bind("<<TreeviewSelect>>", lambda e: self.on_cat())
        if admin:
            self.ct.bind("<Button-3>", lambda e: self.folder_context(e))
            self.ct.bind("<Alt-Up>", lambda e: self.reorder(-1))
            self.ct.bind("<Alt-Down>", lambda e: self.reorder(1))
        self._search_job = None
        self.refresh_cats()
        lc = self.prefs.get("last_cat", "")
        if lc and self.prefs.get("remember", "1") == "1" and self.view.get() == core.VIEWS[0] and self.ct.exists(f"c{lc}"):
            self.ct.selection_set(f"c{lc}")
            self.ct.see(f"c{lc}")
        self.dt.bind("<Alt-Up>", lambda e: (self.move_docs_pos(-1), "break")[1])
        self.dt.bind("<Alt-Down>", lambda e: (self.move_docs_pos(1), "break")[1])
        self.dt.bind("<ButtonPress-1>", self.drag_press, add="+")
        self.dt.bind("<B1-Motion>", self.drag_motion, add="+")
        self._d0, self._dragging = None, False
        self.load_docs()
        return page

    # ---- the View menu: everything about how the list looks, in one place
    def view_menu(self, widget):
        m = tk.Menu(widget, tearoff=0, font=(FONT, 10), bg=P.CARD, fg=P.INK, activebackground=P.ACCENT, activeforeground="#FFFFFF", bd=0, selectcolor=P.ACCENT)
        m.add_command(label="SHOW", state="disabled")
        for v in core.VIEWS:
            m.add_radiobutton(label="   " + v, variable=self.view, value=v, command=lambda v=v: self.set_view(v))
        m.add_separator()
        o = tk.Menu(m, tearoff=0, font=(FONT, 10), bg=P.CARD, fg=P.INK, activebackground=P.ACCENT, activeforeground="#FFFFFF", bd=0, selectcolor=P.ACCENT)
        for lab in core.ORDERS:
            o.add_radiobutton(label=lab, variable=self.order, value=lab, command=self.on_order)
        m.add_cascade(label="Order by", menu=o)
        c = tk.Menu(m, tearoff=0, font=(FONT, 10), bg=P.CARD, fg=P.INK, activebackground=P.ACCENT, activeforeground="#FFFFFF", bd=0, selectcolor=P.ACCENT)
        for k, t in core.COLS:
            c.add_checkbutton(label=t, variable=self.v_cols[k], command=self.apply_columns)
        m.add_cascade(label="Columns", menu=c)
        m.add_separator()
        m.add_checkbutton(label="Compact rows", variable=self.v_compact, command=self.toggle_compact)
        m.add_checkbutton(label="Details line under the list", variable=self.v_details, command=self.toggle_details)
        m.add_checkbutton(label="Folders panel", variable=self.v_folders, command=self.toggle_folders)
        m.add_checkbutton(label="Preview panel", variable=self.v_preview, command=self.toggle_preview)
        try:
            m.tk_popup(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())
        finally:
            m.grab_release()

    def set_view(self, v):
        self.view.set(v)
        self.set_bin_active(v == "Recycle bin")
        if v == "Recycle bin" and self.ct.selection():
            self.ct.selection_remove(*self.ct.selection())
        self.load_docs()

    def show_bin(self):
        if self.search.get():
            self.search.clear()
        self.set_view("Recycle bin")

    def set_bin_active(self, on):
        bg = P.SEL if on else P.CARD
        for w_ in self.bin_parts:
            w_.configure(bg=bg)

    def toggle_folders(self):
        show = self.v_folders.get()
        self.prefs.set("folders_hidden", "0" if show else "1")
        if show:
            self.fc.grid()
        else:
            self.fc.grid_remove()

    def toggle_details(self):
        on = self.v_details.get()
        self.prefs.set("details", "1" if on else "0")
        if on:
            self.det.pack(fill="x", pady=(px(4), 0))
        else:
            self.det.pack_forget()

    # ---- clickable folder path and one-click type filter
    def crumb_parts(self):
        v = self.view.get()
        if v != core.VIEWS[0]:
            return [(v, None)]
        c, parts = self.cur_cat(), []
        while c:
            r = core.q("select name,parent_id from categories where id=?", (c,))[0]
            parts.insert(0, (r["name"], c))
            c = r["parent_id"]
        return parts or [("Library", None)]

    def draw_crumb(self, search=""):
        for w_ in self.crumb_box.winfo_children():
            w_.destroy()
        parts = self.crumb_parts()
        for i, (name, cid) in enumerate(parts):
            last = i == len(parts) - 1 and not search
            lb = tk.Label(self.crumb_box, text=name, bg=P.CARD, fg=P.TITLE if last else P.BLUE, font=(FONT, 12, "bold" if last else "normal"), cursor="" if (last or not cid) else "hand2")
            lb.pack(side="left")
            if cid and not last:
                lb.bind("<Button-1>", lambda e, c=cid: self.goto_cat(c))
            if i < len(parts) - 1:
                tk.Label(self.crumb_box, text="  \u203A  ", bg=P.CARD, fg=P.MUTED, font=(FONT, 11)).pack(side="left")
        if search:
            tk.Label(self.crumb_box, text=f'   -   "{search}"', bg=P.CARD, fg=P.MUTED, font=(FONT, 12)).pack(side="left")

    def goto_cat(self, cid):
        if self.ct.exists(f"c{cid}"):
            self.ct.selection_set(f"c{cid}")
            self.ct.see(f"c{cid}")

    def set_tfilter(self, v):
        self.tfilter = v or "all"
        self.load_docs()

    # ---- preview panel
    def build_preview(self):
        f = self.pv
        self.pv_img = tk.Label(f, bg=P.TILE)
        self.pv_img.pack(pady=(px(14), px(8)))
        self.pv_title = tk.Label(f, text="", bg=P.TILE, fg=P.TITLE, font=(FONT, 11, "bold"), wraplength=px(268), justify="left")
        self.pv_title.pack(anchor="w", padx=px(14))
        self.pv_badge = tk.Label(f, text="", bg=P.TILE, fg="#FFFFFF", font=(FONT, 8, "bold"), padx=px(8), pady=px(2))
        self.pv_badge.pack(anchor="w", padx=px(14), pady=(px(6), 0))
        self.pv_facts = tk.Label(f, text="Select a document to see its preview.", bg=P.TILE, fg=P.MUTED, font=(FONT, 9), justify="left", wraplength=px(268), anchor="w")
        self.pv_facts.pack(anchor="w", padx=px(14), pady=(px(10), 0))
        bt = tk.Frame(f, bg=P.TILE)
        bt.pack(side="bottom", fill="x", padx=px(14), pady=px(12))
        RButton(bt, "Open", self.open_sel, "navy").pack(side="left")
        RButton(bt, "Details", self.edit_details, "soft").pack(side="left", padx=(px(6), 0))
        self._thumbs, self._pvjob = {}, None

    def toggle_preview(self):
        on = self.v_preview.get()
        self.prefs.set("preview", "1" if on else "0")
        if on:
            self.pv.grid()
            self.update_preview()
        else:
            self.pv.grid_remove()

    def preview_later(self):
        if not self.v_preview.get():
            return
        if self._pvjob:
            try:
                self.after_cancel(self._pvjob)
            except Exception:
                pass
        self._pvjob = self.after(140, self.update_preview)

    def thumb(self, d):
        key = (d["id"], d["size"], d["ver"], P.theme)
        if key in self._thumbs:
            return self._thumbs[key]
        p, k = core.FILES / d["stored"], core.ftype(d["filename"])[0]
        im = None
        try:
            from PIL import Image
            if p.suffix.lower() in core.IMG_EXT:
                im = Image.open(p)
                im.load()
                im.thumbnail((px(268), px(230)))
            elif p.suffix.lower() == ".pdf" and viewers.fitz:
                import io
                doc = viewers.fitz.open(str(p))
                pg = doc[0]
                sc = px(268) / pg.rect.width
                im = Image.open(io.BytesIO(doc[0].get_pixmap(matrix=viewers.fitz.Matrix(sc, sc), alpha=False).tobytes("png")))
                doc.close()
                if im.height > px(240):
                    im = im.crop((0, 0, im.width, px(240)))
        except Exception:
            im = None
        ph = W.photo_of(im.convert("RGBA")) if im is not None else self.ficon(k, 72)
        if len(self._thumbs) > 60:
            self._thumbs.clear()
        self._thumbs[key] = ph
        return ph

    @_timed("update_preview")
    def update_preview(self):
        self._pvjob = None
        if not self.v_preview.get():
            return
        try:
            sel = self.dt.selection()
            if len(sel) > 1:
                marks = ",".join("?" * min(len(sel), 900))
                tot = core.q(f"select coalesce(sum(size),0) s from docs where id in ({marks})", tuple(int(i) for i in sel[:900]))[0]["s"]
                self.pv_img.configure(image="")
                self.pv_title.configure(text=f"{len(sel)} documents selected")
                self.pv_badge.configure(text="", bg=P.TILE)
                self.pv_facts.configure(text="Total size: " + core.size(tot))
                return
            ds = self.sel_docs()
            if not ds:
                self.pv_img.configure(image="")
                self.pv_title.configure(text="")
                self.pv_badge.configure(text="", bg=P.TILE)
                self.pv_facts.configure(text="Select a document to see its preview.")
                return
            if len(ds) > 1:
                self.pv_img.configure(image="")
                self.pv_title.configure(text=f"{len(ds)} documents selected")
                self.pv_badge.configure(text="", bg=P.TILE)
                self.pv_facts.configure(text="Total size: " + core.size(sum(d["size"] or 0 for d in ds)))
                return
            d = ds[0]
            k, label, _ = core.ftype(d["filename"])
            ph = self.thumb(d)
            self.pv_img.configure(image=ph)
            self.pv_img.image = ph
            self.pv_title.configure(text=d["title"])
            self.pv_badge.configure(text=label.upper(), bg=self.type_color(k))
            fmt = self.prefs.get("datefmt", "ISO")
            lines = [f"Size:  {core.size(d['size'])}", f"Folder:  {d['cat'] or ''}", f"Version:  {d['ver'] or 1}", f"Added by:  {d['who'] or ''}", f"Added:  {core.fmt_date(d['created'], fmt)}"]
            if d["status"]:
                lines.insert(1, f"Status:  {d['status']}")
            if d["review"]:
                lines.insert(2 if d["status"] else 1, f"Review date:  {d['review']}")
            if d["tags"]:
                lines.append(f"Tags:  {d['tags']}")
            if d["descr"]:
                lines.append("\n" + d["descr"])
            self.pv_facts.configure(text="\n".join(lines))
        except tk.TclError:
            pass

    # ---- small extras
    def toggle_theme(self):
        self.prefs.set("theme", "light" if P.theme == "dark" else "dark")
        self.rebuild()

    def export_zip(self):
        ds = self.need_docs()
        if not ds:
            return
        f = filedialog.asksaveasfilename(defaultextension=".zip", initialfile=f"TDMS_documents_{dt.date.today():%Y%m%d}.zip", filetypes=[("Zip file", "*.zip")])
        if not f:
            return
        self.config(cursor="watch")
        self.update_idletasks()
        n = core.zip_documents(ds, f)
        self.config(cursor="")
        self.log("zip export", f"{n} file(s)")
        self.toast(f"{n} document(s) saved in the ZIP.")

    def show_help(self):
        d = W.Dialog(self, "Shortcuts and tips", width=640)
        rows = [("Ctrl + F", "Search all documents"), ("Ctrl + N", "Add documents"), ("F2", "Rename the selected document"), ("Delete", "Move to the Recycle bin"), ("Alt + Up / Down", "Move documents (or folders) up / down"),
                ("Ctrl + A", "Select all documents"), ("Ctrl + C / Ctrl + V", "Copy / paste files (also with Explorer)"), ("Ctrl + W", "Close the open tab"), ("Ctrl + Tab", "Go to the next tab"),
                ("Ctrl + wheel, pinch", "Zoom a PDF or a picture"), ("Drag files in", "From any drive onto the list or onto a folder"), ("Drag files out", "From the list to Explorer, the desktop or an e-mail"),
                ("View > Preview panel", "See a thumbnail and the facts of the selected document"), ("Details", "Set a status (Draft, In review, Approved, Obsolete) and a review date")]
        g_ = tk.Frame(d.body, bg=P.CARD)
        g_.pack(fill="x", pady=(px(8), 0))
        for i, (k, t) in enumerate(rows):
            tk.Label(g_, text=k, bg=P.CARD, fg=P.BLUE, font=(FONT, 10, "bold"), width=22, anchor="w").grid(row=i, column=0, sticky="w", pady=px(3))
            tk.Label(g_, text=t, bg=P.CARD, fg=P.INK, font=(FONT, 10), anchor="w").grid(row=i, column=1, sticky="w")
        RButton(d.bar, "Close", d.destroy, "soft", big=True).pack(side="right")
        d.show()

    def apply_columns(self):
        keys = [k for k, _ in core.COLS if self.v_cols[k].get()] or ["type"]
        self.prefs.set("cols", ",".join(keys))
        self.dt.configure(displaycolumns=keys)

    def on_library_show(self):
        try:
            if core.docs_stamp() != getattr(self, "_lib_stamp", None):
                self.load_docs()
        except tk.TclError:
            pass

    def search_later(self):
        if getattr(self, "_search_job", None):
            self.after_cancel(self._search_job)
        self._search_job = self.after(260, self.load_docs)

    def on_cat(self):
        if self.cur_cat() is None:               # the Recycle bin was clicked (no folder selected): leave the view alone
            return
        if self.search.get():
            self.search.clear()
        self.view.set(core.VIEWS[0])
        self.set_bin_active(False)
        self.load_docs()
        c = self.cur_cat()
        if c:
            self.prefs.set("last_cat", c)

    def post_menu(self, items, e):
        m = tk.Menu(self, tearoff=0, font=(FONT, 10), bg=P.CARD, fg=P.INK, activebackground=P.ACCENT, activeforeground="#FFFFFF", bd=0)
        for label, cmd in items:
            m.add_separator() if label is None else m.add_command(label=label, command=cmd)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def doc_context(self, e):
        i = self.dt.identify_row(e.y)
        if i and i not in self.dt.selection():
            self.dt.selection_set(i)
        head = [] if self.view.get() == "Recycle bin" else [("Open in tab", self.open_sel), ("Favorite on / off", self.toggle_fav), (None, None)]
        self.post_menu(head + self.more_items(), e)

    def folder_context(self, e):
        i = self.ct.identify_row(e.y)
        if i:
            self.ct.selection_set(i)
        self.post_menu(self.folder_menu_items(), e)

    def more_items(self):
        if self.view.get() == "Recycle bin":
            items = [("Restore", self.restore_docs), ("Delete forever   (Del)", self.delete_docs)]
            return items + ([(None, None), ("Empty the Recycle bin", self.empty_bin)] if self.is_admin() else [])
        return [("Details, tags and description...", self.edit_details), ("Rename   (F2)", self.rename_doc), ("Move to folder...", self.move_docs), ("New version of this document...", self.new_version),
                ("Version history...", self.version_history), (None, None), ("Select all   (Ctrl+A)", self.select_all), ("Copy file(s)   (Ctrl+C)", self.copy_files),
                ("Paste file(s) here   (Ctrl+V)", self.paste_files), ("Save a copy...", self.save_copy), ("Save selected as ZIP...", self.export_zip), ("Export this list (CSV)...", self.export_list), (None, None),
                ("Move to Recycle bin   (Del)", self.delete_docs)]

    def folder_menu_items(self):
        return [("New folder...", lambda: self.add_cat(False)), ("New subfolder...  (inside the selected folder)", lambda: self.add_cat(True)), (None, None), ("Rename...", self.rename_cat),
                (None, None), ("Move up   (Alt+Up)", lambda: self.reorder(-1)), ("Move down   (Alt+Down)", lambda: self.reorder(1)),
                ("Move into another folder...", self.move_cat_into), (None, None), ("Folder colour...", self.color_cat), ("Reset folder colour", lambda: self.color_cat(True)), (None, None),
                ("Delete folder and its documents...", self.delete_cat)]

    # ------------------------------------------------------------ folders
    @_timed("refresh_cats")
    def refresh_cats(self, select=None):
        keep = [i for i in self.all_iids() if self.ct.item(i, "open")]
        sel = select or self.cur_cat()
        self.ct.delete(*self.ct.get_children())
        by_parent = {}
        for r in core.q("select * from categories order by sort,id"):
            by_parent.setdefault(r["parent_id"], []).append(r)

        def fill(parent, pid):
            for r in by_parent.get(parent, []):
                iid = f"c{r['id']}"
                self.ct.insert(pid, "end", iid=iid, text="  " + r["name"], image=self.folder_img(r["color"]))
                fill(r["id"], iid)
        fill(None, "")
        for i in keep:
            if self.ct.exists(i):
                self.ct.item(i, open=True)
        if sel and self.ct.exists(f"c{sel}"):
            self.ct.selection_set(f"c{sel}")
            self.ct.see(f"c{sel}")

    def all_iids(self, p=""):
        out = []
        for i in self.ct.get_children(p):
            out += [i] + self.all_iids(i)
        return out

    def cur_cat(self):
        s = self.ct.selection() if hasattr(self, "ct") else ()
        return int(s[0][1:]) if s else None

    def cat_row(self):
        c = self.cur_cat()
        if not c:
            self.toast("Click a folder on the left first.", "warn")
            return None
        return core.q("select * from categories where id=?", (c,))[0]

    def reorder(self, delta):
        r = self.cat_row()
        if not r:
            return
        ids = [s["id"] for s in core.q("select id from categories where parent_id is ? order by sort,id", (r["parent_id"],))]
        i = ids.index(r["id"])
        j = i + delta
        if 0 <= j < len(ids):
            ids[i], ids[j] = ids[j], ids[i]
            for n, cid in enumerate(ids, 1):
                core.ex("update categories set sort=? where id=?", (n, cid))
            self.log("reorder folder", r["name"])
            self.refresh_cats(r["id"])

    def add_cat(self, sub):
        parent = self.cur_cat() if sub else None
        if sub and not parent:
            return self.toast("Click the parent folder on the left first, then choose New subfolder.", "warn")
        v = FormDialog(self, "New subfolder" if sub else "New folder", [("n", "FOLDER NAME", "text", "", "")], ok="Create", validate=lambda v: None if v["n"] else "Type a name.").run()
        if v:
            i, _ = core.ex("insert into categories(name,parent_id,sort) values(?,?,(select coalesce(max(sort),0)+1 from categories where parent_id is ?))", (v["n"], parent, parent))
            self.log("add folder", v["n"])
            self.refresh_cats(i)
            if parent:
                self.ct.item(f"c{parent}", open=True)
            self.toast(f"Folder \"{v['n']}\" created.")

    def rename_cat(self):
        r = self.cat_row()
        if not r:
            return
        v = FormDialog(self, "Rename folder", [("n", "FOLDER NAME", "text", r["name"], "")], ok="Rename", validate=lambda v: None if v["n"] else "Type a name.").run()
        if v:
            self.close_doc_pages()
            try:
                core.relocate(r["id"], name=v["n"])
            except (ValueError, OSError) as e:
                return self.toast(str(e), "err")
            self.log("rename folder", f"{r['name']} -> {v['n']}")
            self.refresh_cats(r["id"])
            self.load_docs()

    def move_cat_into(self):
        r = self.cat_row()
        if not r:
            return
        ch = core.folder_choices(core.descendants(r["id"]), True)
        cur = next((l for l, i in ch if i == r["parent_id"]), ch[0][0])
        v = FormDialog(self, "Move folder", [("to", f"MOVE \"{r['name']}\" INTO", "combo", ([l for l, _ in ch], cur), "")], ok="Move").run()
        if not v:
            return
        self.close_doc_pages()
        parent = dict(ch)[v["to"]]
        try:
            core.relocate(r["id"], parent=parent)
        except (ValueError, OSError) as e:
            return self.toast(str(e), "err")
        core.ex("update categories set sort=(select coalesce(max(sort),0)+1 from categories where parent_id is ?) where id=?", (parent, r["id"]))
        self.log("move folder", r["name"])
        self.refresh_cats(r["id"])
        self.load_docs()

    def color_cat(self, reset=False):
        r = self.cat_row()
        if not r:
            return
        if reset:
            core.set_cat_color(r["id"], None)
        else:
            from tkinter import colorchooser
            c = colorchooser.askcolor(color=r["color"] or "#FAC846", parent=self, title="Folder colour")[1]
            if not c:
                return
            core.set_cat_color(r["id"], c.upper())
        self.log("folder colour", r["name"])
        self.refresh_cats(r["id"])

    def delete_cat(self):
        r = self.cat_row()
        if not r:
            return
        ids = core.descendants(r["id"])
        n = core.q(f"select count(*) c from docs where deleted=0 and category_id in ({','.join('?' * len(ids))})", tuple(ids))[0]["c"]
        text = (f"Delete the folder \"{r['name']}\"" + (f" and its {len(ids) - 1} sub-folder(s)" if len(ids) > 1 else "") + ".\n" +
                (f"{n} document(s) inside move to the Recycle bin, where you can restore them." if n else "It is empty."))
        if ask_yes_no(self, "Delete folder", text, "Delete folder", "Cancel", "danger"):
            self.close_doc_pages()
            docs, folders = core.delete_folder_tree(r["id"], self.user["id"])
            self.log("delete folder", f"{r['name']} ({folders} folder(s), {docs} document(s))")
            self.refresh_cats()
            self.load_docs()
            self.toast(f"Deleted {folders} folder(s). {docs} document(s) are in the Recycle bin.")

    # ------------------------------------------------------------ document list
    def sort_by(self, k):
        self.sort = (k, not self.sort[1] if self.sort[0] == k else False)
        self.order.set("")
        self.load_docs()

    def on_order(self):
        lab = self.order.get()
        self.sort = core.ORDERS.get(lab, ("pos", False))
        self.prefs.set("order", lab)
        self.load_docs()

    def select_all(self):
        kids = self.dt.get_children()
        if len(self.dt.selection()) == len(kids) and kids:
            self.dt.selection_remove(*kids)
        else:
            self.dt.selection_set(kids)

    def toggle_compact(self):
        self.prefs.set("compact", "1" if self.v_compact.get() else "0")
        self.style_ttk()
        self.refresh_cats()
        self.load_docs()

    def move_docs_pos(self, delta):
        ds = [d for d in self.need_docs() if self.can_edit(d)]
        if not ds:
            return
        cats = {d["category_id"] for d in ds}
        if self.view.get() != core.VIEWS[0] or len(cats) != 1:
            return self.toast("Open one folder first, then move its documents up or down.", "info")
        first = next(iter(core.ORDERS))
        if self.sort != ("pos", False):
            self.sort = ("pos", False)
            self.order.set(first)
            self.prefs.set("order", first)
        core.reorder_docs(cats.pop(), [d["id"] for d in ds], delta)
        self.reselect([d["id"] for d in ds])

    def crumb_text(self):
        v = self.view.get()
        if v != core.VIEWS[0]:
            return v
        c, names = self.cur_cat(), []
        while c:
            r = core.q("select name,parent_id from categories where id=?", (c,))[0]
            names.insert(0, r["name"])
            c = r["parent_id"]
        return "  >  ".join(names) if names else "Library"

    @_timed("load_docs")
    def load_docs(self):
        try:
            s, v = self.search.get(), self.view.get()
            rows = core.doc_rows(v, s, self.user["id"], self.cur_cat(), self.sort, self.is_admin())
            if self.tfilter != "all":
                keep = core.TYPE_CHIPS[self.tfilter]
                rows = [r for r in rows if core.ftype(r["filename"])[0] in keep]
            fmt = self.prefs.get("datefmt", "ISO")
            bin_ = v == "Recycle bin"
            tint = self.prefs.get("row_tint", "0") == "1"
            self.dt.heading("added", text="Deleted" if bin_ else "Added")
            items = []
            for n, r in enumerate(rows):
                k, label, _ = core.ftype(r["filename"])
                ver = f"   v{r['ver']}" if (r["ver"] or 1) > 1 else ""
                items.append((str(r["id"]), "  " + ("\u2605 " if r["fav"] else "") + r["title"] + ver, k, ((f"t_{k}" + ("o" if n % 2 else "")),) if tint else (("odd",) if n % 2 else ()),
                              (label, r["status"] or "", r["cat"] or "", core.size(r["size"]), r["who"] or "", core.fmt_date(r["deleted_at"] if bin_ else r["created"], fmt))))
            skey = (self.row_icon(), tuple(sorted(self._tc.items())), P.theme)
            if getattr(self, "_dt_skey", None) != skey:
                self._dt_skey, self._dt_sig = skey, None
            old = self._dt_sig
            if old != items:
                if old is not None and [o[0] for o in old] == [i[0] for i in items]:       # same documents in the same order: update only what changed
                    for o, i in zip(old, items):
                        if o != i:
                            self.dt.item(i[0], text=i[1], image=self.ficon(i[2], self.row_icon()), tags=i[3], values=i[4])
                    self._seltags = set()
                    self.update_sel_tags()
                else:
                    self.dt.delete(*self.dt.get_children())
                    for i in items:
                        self.dt.insert("", "end", iid=i[0], text=i[1], image=self.ficon(i[2], self.row_icon()), tags=i[3], values=i[4])
                    self._seltags = set()
                self._dt_sig = items
            self.draw_crumb(s)
            self._count = f"{len(rows)} document(s)" + (f"   |   kept {self.S.get('trash_days')} days, then removed" if bin_ else "")
            self._total = len(rows)
            self.count.configure(text=self._count)
            self.det.configure(text="")
            if rows:
                self.empty.place_forget()
            else:
                self.empty.configure(text=(f"No documents match \"{s}\"." if s else "The Recycle bin is empty." if bin_ else
                                           "Pick a folder on the left to see its documents,\nor use the search box above." if v == core.VIEWS[0] and not self.cur_cat()
                                           else "This folder is empty.\n\nDrag files here, or press  + Add documents." if v == core.VIEWS[0] else "Nothing to show for this view yet."))
                self.empty.place(relx=.5, rely=.4, anchor="center")
            self._lib_stamp = core.docs_stamp()
            n_ = core.trash_count(self.user["id"], self.is_admin())
            self.bin_count.configure(text=str(n_) if n_ else "")
        except tk.TclError:
            pass

    def update_count(self):
        n = len(self.dt.selection())
        self.count.configure(text=f"{n} selected of {getattr(self, '_total', 0)}" if n > 1 else getattr(self, "_count", ""))

    def update_sel_tags(self):
        cur, prev = set(self.dt.selection()), getattr(self, "_seltags", set())
        for iid in prev - cur:
            if self.dt.exists(iid):
                self.dt.item(iid, tags=[t for t in (self.dt.item(iid, "tags") or ()) if t != "sel"])
        for iid in cur - prev:
            self.dt.item(iid, tags=[t for t in (self.dt.item(iid, "tags") or ()) if t not in ("hover", "sel")] + ["sel"])
        self._seltags = cur

    def show_details(self):
        self.update_sel_tags()
        self.update_count()
        self.preview_later()
        n_ = len(self.dt.selection())
        if n_ > 1:
            return self.det.configure(text=f"{n_} documents selected")
        ds = self.sel_docs() if n_ == 1 else []
        if not ds:
            return self.det.configure(text="")
        d = ds[0]
        t = (f"{d['title']}   |   {core.ftype(d['filename'])[1]}   |   version {d['ver'] or 1}   |   {core.size(d['size'])}   |   {d['cat']}   |   {d['who']}, "
             f"{core.fmt_date(d['created'], self.prefs.get('datefmt', 'ISO'))}")
        if d["status"]:
            t += f"   |   {d['status']}"
        if d["review"]:
            t += f"   |   review {d['review']}"
        if d["tags"]:
            t += f"   |   tags: {d['tags']}"
        if d["descr"]:
            t += f"   |   {d['descr']}"
        self.det.configure(text=t)

    def sel_docs(self):
        return [d for d in (core.get_doc(int(i)) for i in self.dt.selection()) if d]

    def need_docs(self, one=False):
        ds = self.sel_docs()
        if not ds:
            self.toast("Click a document in the list first.", "warn")
        return ds[:1] if one else ds

    def can_edit(self, d):
        if self.is_admin() or d["uploader_id"] == self.user["id"]:
            return True
        self.toast("Only an admin or the person who added it can change this document.", "warn")
        return False

    def reselect(self, ids):
        self.load_docs()
        for i in ids:
            if self.dt.exists(str(i)):
                self.dt.selection_add(str(i))

    # ------------------------------------------------------------ adding documents (button, drag and drop, paste)
    def add_docs_dialog(self):
        f = filedialog.askopenfilenames(title="Choose documents to add")
        if f:
            self.add_paths(f)

    def progress_start(self, title):
        d = W.Dialog(self, title, width=500)
        d.name = tk.Label(d.body, text="", bg=P.CARD, fg=P.INK, font=(FONT, 10), anchor="w")
        d.name.pack(fill="x", pady=(px(10), px(6)))
        d.bar_cv = tk.Canvas(d.body, height=px(10), bg=P.PILL, highlightthickness=0)
        d.bar_cv.pack(fill="x")
        d.fill = d.bar_cv.create_rectangle(0, 0, 0, px(10), fill=P.ACCENT, outline="")
        d.pct = tk.Label(d.body, text="Starting...", bg=P.CARD, fg=P.MUTED, font=(FONT, 9), anchor="w")
        d.pct.pack(fill="x", pady=(px(6), 0))
        W.center_on(d, self)
        d.deiconify()
        d.grab_set()
        d.update()
        self._pd, self._pd_t = d, 0

    def progress_cb(self, done, total, name):
        d = getattr(self, "_pd", None)
        if not d:
            return
        t = time.time()
        if t - self._pd_t < 0.08 and done < total:
            return
        self._pd_t = t
        try:
            d.name.configure(text=name)
            d.bar_cv.coords(d.fill, 0, 0, int(d.bar_cv.winfo_width() * done / max(1, total)), px(10))
            d.pct.configure(text=f"{core.size(done)} of {core.size(total)}")
            d.update()
        except tk.TclError:
            pass

    def progress_end(self):
        d, self._pd = getattr(self, "_pd", None), None
        if d:
            try:
                d.grab_release()
                d.destroy()
            except tk.TclError:
                pass

    def add_folder_dialog(self):
        f = filedialog.askdirectory(title="Choose a folder to add (with everything inside it)")
        if f:
            self.add_paths([f])

    def add_link_dialog(self):
        cat = self.cur_cat()
        if not cat:
            return self.toast("Pick a folder on the left first.", "warn")
        v = FormDialog(self, "Add a web link", [("n", "NAME", "text", "", ""), ("u", "WEB ADDRESS", "text", "https://", "")], ok="Add link",
                       validate=lambda v: "Type a name." if not v["n"] else None if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://\S+$", v["u"]) else "Type the full address, for example https://www.example.com").run()
        if v:
            core.add_link(cat, v["n"], v["u"], self.user["id"])
            self.log("add link", v["n"])
            self.load_docs()
            self.toast("Web link added. Double-click it to open the page in your browser.")

    @_timed("add_paths")
    def add_paths(self, paths):
        cat = self.cur_cat()
        if not cat:
            return self.toast("Pick a folder on the left first, then add documents.", "warn")
        if self.view.get() != core.VIEWS[0]:
            self.view.set(core.VIEWS[0])
        dirs = [Path(p) for p in paths if Path(p).is_dir()]
        if dirs:
            self.progress_start("Adding folder")
            total, bad, last = 0, [], None
            try:
                for dpath in dirs:
                    last, a, b = core.import_folder(dpath, cat, self.user["id"], self.progress_cb)
                    total += a
                    bad += b
            finally:
                self.progress_end()
            self.log("add folder", f"{len(dirs)} folder(s), {total} file(s)")
            self.refresh_cats(last)
            self.ct.item(f"c{cat}", open=True)
            self.toast(f"Added {len(dirs)} folder(s) with {total} document(s). Click them in the tree to open." + (f"  {len(bad)} skipped." if bad else ""), "ok" if not bad else "warn")
            paths = [p for p in paths if not Path(p).is_dir()]
            if not paths:
                return
        files = core.expand_paths(paths)
        if not files:
            return self.toast("No files found to add.", "warn")
        if len(files) > 60 and not ask_yes_no(self, "Add many files", f"Add {len(files)} files to this folder?", "Add", "Cancel"):
            return
        titles = [None] * len(files)
        if len(files) == 1:
            f = files[0]
            same = core.find_same_name(cat, f.stem, f.suffix)
            if same:
                o1, o2 = "Save as a new version of the existing document", "Keep both (this one gets a new name)"
                v = FormDialog(self, "Same name found", [("how", "WHAT SHOULD HAPPEN?", "combo", ([o1, o2], o1), "")], ok="Continue",
                               intro=f"\"{same['filename']}\" is already in this folder.").run()
                if not v:
                    return
                if v["how"] == o1:
                    self.close_doc_pages()
                    core.add_version(same, f, self.user["id"], "")
                    self.log("new version", same["title"])
                    self.load_docs()
                    return self.toast(f"Saved as version {(same['ver'] or 1) + 1} of \"{same['title']}\".")
            v = FormDialog(self, "Name this document", [("n", "DOCUMENT NAME", "text", f.stem, "")], ok="Add", intro=f"File: {f.name}\nThe extension {f.suffix or '(none)'} is kept.",
                           validate=lambda v: None if v["n"] else "Type a name.").run()
            if not v:
                return
            titles = [v["n"]]
        big = sum(f.stat().st_size for f in files) > 25 * 1024 * 1024
        if big:
            self.progress_start("Adding documents")
        try:
            added, bad = core.add_files(cat, list(zip(files, titles)), self.user["id"], self.progress_cb if big else None)
        finally:
            if big:
                self.progress_end()
        if added:
            self.log("add documents", f"{added} file(s) to {self.crumb_text()}")
        self.load_docs()
        self.toast(f"Added {added} document(s)." + (f"  {len(bad)} skipped." if bad else ""), "ok" if added and not bad else "warn")
        if bad:
            messagebox.showwarning("Some files were skipped", "\n".join(bad[:12]))

    def on_native_drop(self, files, sx, sy):
        """Files dropped from Explorer onto the TDMS window."""
        if not self.user:
            return self.toast("Sign in first, then drop your files.", "info")
        if self.current != "library":
            self.show_page("library")
            self.update_idletasks()
        try:
            if self.winfo_containing(sx, sy) is self.ct:
                i = self.ct.identify_row(sy - self.ct.winfo_rooty())
                if i:
                    self.ct.selection_set(i)
        except Exception:
            pass
        self.add_paths(files)

    def drag_press(self, e):
        self._d0 = (e.x, e.y, self.dt.identify_row(e.y), tuple(self.dt.selection()))

    def drag_motion(self, e):
        d0 = getattr(self, "_d0", None)
        if not d0 or self._dragging or self.view.get() == "Recycle bin":
            return
        x0, y0, row, sel = d0
        if row and (abs(e.x - x0) > 12 or abs(e.y - y0) > 12):
            self._dragging, self._d0 = True, None
            self.after(10, lambda ids=list(sel) if row in sel else [row]: self.do_drag(ids))
            return "break"

    def do_drag(self, ids):
        try:
            docs = [core.get_doc(int(i)) for i in ids]
            paths = [str(core.FILES / d["stored"]) for d in docs if d and (core.FILES / d["stored"]).exists()]
            if paths and not native.drag_files(self, paths):
                self.toast("Dragging out is not available here. Use Ctrl+C, then Ctrl+V, or More > Save a copy.", "warn", 6000)
        except Exception as e:
            self.toast(f"Drag failed: {e}", "err")
        finally:
            self._dragging = False
            try:
                self.dt.event_generate("<ButtonRelease-1>")
                self.dt.selection_set([i for i in ids if self.dt.exists(i)])
            except Exception:
                pass

    def copy_files(self):
        ds = self.sel_docs()
        if not ds:
            return
        if core.clip_files_set([str(core.FILES / d["stored"]) for d in ds]):
            self.toast(f"{len(ds)} file(s) copied. Paste them with Ctrl+V in Explorer, e-mail or chat.")
        else:
            self.toast("Could not copy to the clipboard. Use Save a copy instead.", "warn")

    def paste_files(self):
        paths = core.clip_files_get()
        if not paths:
            return self.toast("No files on the clipboard. Copy files in Explorer first (Ctrl+C).", "info")
        self.add_paths(paths)

    # ------------------------------------------------------------ document actions
    def open_sel(self):
        for d in self.need_docs()[:6]:
            self.open_doc(d)

    def rename_doc(self):
        ds = self.need_docs(True)
        if not ds or not self.can_edit(ds[0]):
            return
        d = ds[0]
        v = FormDialog(self, "Rename document", [("n", "NEW NAME", "text", d["title"], "")], ok="Rename", intro=f"The extension {Path(d['filename']).suffix or '(none)'} is kept.",
                       validate=lambda v: None if v["n"] else "Type a name.").run()
        if v:
            self.close_doc_pages()
            err = core.rename_doc(d, v["n"])
            if err:
                return self.toast(err, "err")
            self.log("rename document", f"{d['title']} -> {v['n']}")
            self.reselect([d["id"]])

    def edit_details(self):
        ds = self.need_docs(True)
        if not ds or not self.can_edit(ds[0]):
            return
        d = ds[0]
        v = FormDialog(self, "Document details", [("n", "NAME", "text", d["title"], ""), ("status", "STATUS", "combo", (core.STATUSES, d["status"] or "(none)"), ""),
                                                  ("review", "REVIEW DATE", "text", d["review"] or "", "Optional, like 2026-12-31. You are reminded on the Dashboard."),
                                                  ("tags", "TAGS", "text", d["tags"] or "", "Separate with commas. Tags are searchable."), ("desc", "DESCRIPTION", "text", d["descr"] or "", "")],
                       ok="Save", validate=lambda v: "Type a name." if not v["n"] else ("The review date must look like 2026-12-31." if v["review"] and not core.valid_date(v["review"]) else None)).run()
        if not v:
            return
        self.close_doc_pages()
        err = core.rename_doc(d, v["n"])
        if err:
            return self.toast(err, "err")
        core.ex("update docs set tags=?, descr=?, status=?, review=? where id=?", (v["tags"], v["desc"], "" if v["status"] == "(none)" else v["status"], v["review"], d["id"]))
        self.log("edit details", v["n"])
        self.reselect([d["id"]])

    def move_docs(self):
        ds = [d for d in self.need_docs() if self.can_edit(d)]
        if not ds:
            return
        ch = core.folder_choices()
        cur = next((l for l, i in ch if i == ds[0]["category_id"]), ch[0][0])
        v = FormDialog(self, "Move to folder", [("to", "MOVE TO FOLDER", "combo", ([l for l, _ in ch], cur), "")], ok="Move").run()
        if not v:
            return
        cat = dict(ch)[v["to"]]
        self.close_doc_pages()
        for d in ds:
            if d["category_id"] != cat:
                core.move_doc(d, cat)
        self.log("move documents", f"{len(ds)} to {v['to']}")
        self.load_docs()
        self.toast(f"Moved {len(ds)} document(s).")

    def toggle_fav(self):
        ds = self.need_docs()
        for d in ds:
            core.toggle_fav(self.user["id"], d["id"])
        if ds:
            self.reselect([d["id"] for d in ds])

    def save_copy(self):
        ds = self.need_docs()
        if not ds:
            return
        if len(ds) == 1:
            dest = filedialog.asksaveasfilename(initialfile=ds[0]["filename"])
            if dest:
                shutil.copy2(core.FILES / ds[0]["stored"], dest)
                self.toast("Copy saved.")
        else:
            folder = filedialog.askdirectory(title="Choose a folder for the copies")
            if folder:
                for d in ds:
                    shutil.copy2(core.FILES / d["stored"], os.path.join(folder, d["filename"]))
                self.toast(f"{len(ds)} copies saved.")
        self.log("save copy", f"{len(ds)} file(s)")

    def delete_docs(self):
        ds = [d for d in self.need_docs() if self.can_edit(d)]
        if not ds:
            return
        if self.view.get() == "Recycle bin":
            return self.purge_docs(ds)
        if self.prefs.get("confirm_delete", "1") == "1" and not ask_yes_no(self, "Move to Recycle bin", f"Move {len(ds)} document(s) to the Recycle bin?" if len(ds) > 1 else f"Move \"{ds[0]['title']}\" to the Recycle bin?",
                                                                            "Move", "Cancel", "danger"):
            return
        for d in ds:
            if f"doc:{d['id']}" in self.builders:
                self.close_page(f"doc:{d['id']}")
            core.trash_doc(d, self.user["id"])
        self.log("delete", f"{len(ds)} document(s) to Recycle bin")
        self.load_docs()
        self.toast(f"Moved {len(ds)} document(s) to the Recycle bin. You can restore them there.")

    def restore_docs(self):
        ds = [d for d in self.need_docs() if self.can_edit(d)]
        for d in ds:
            core.restore_doc(d)
        if ds:
            self.log("restore", f"{len(ds)} document(s)")
            self.load_docs()
            self.toast(f"Restored {len(ds)} document(s).")

    def purge_docs(self, ds):
        if ask_yes_no(self, "Delete forever", f"Delete {len(ds)} document(s) forever?\nThis cannot be undone.", "Delete forever", "Cancel", "danger"):
            for d in ds:
                core.purge_doc(d)
            self.log("purge", f"{len(ds)} document(s)")
            self.load_docs()
            self.toast(f"Deleted {len(ds)} document(s) forever.")

    def empty_bin(self):
        rows = core.q("select * from docs where deleted=1")
        if not rows:
            return self.toast("The Recycle bin is already empty.", "info")
        self.purge_docs(rows)

    def new_version(self):
        ds = self.need_docs(True)
        if not ds or not self.can_edit(ds[0]):
            return
        d = ds[0]
        f = filedialog.askopenfilename(title=f"Choose the new version of \"{d['title']}\"")
        if not f:
            return
        v = FormDialog(self, "New version", [("note", "WHAT CHANGED?", "text", "", "Optional")], ok="Save new version", intro=f"The current file is kept as version {d['ver'] or 1}.").run()
        if v is None:
            return
        self.close_doc_pages()
        core.add_version(d, f, self.user["id"], v["note"])
        self.log("new version", d["title"])
        self.reselect([d["id"]])
        self.toast(f"Saved as version {(d['ver'] or 1) + 1}.")

    def version_history(self):
        ds = self.need_docs(True)
        if ds:
            VersionsDialog(self, ds[0]).show()

    def after_version_change(self, did):
        self.close_doc_pages()
        self.reselect([did])

    def export_list(self):
        items = [self.dt.item(i) for i in self.dt.get_children()]
        if not items:
            return self.toast("There is nothing in the list to export.", "info")
        f = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=f"TDMS_list_{dt.date.today():%Y%m%d}.csv", filetypes=[("CSV file", "*.csv")])
        if not f:
            return
        import csv
        with open(f, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["Name", "Type", "Status", "Folder", "Size", "Added by", "Added"])
            for it in items:
                w.writerow([it["text"].replace("\u2605", "").strip()] + list(it["values"]))
        self.toast("The list was saved. You can open it in Excel.")

    def global_search(self, text):
        text = (text or "").strip()
        if not text:
            return
        self.show_page("library")
        self.view.set("All documents")
        self.set_bin_active(False)
        self.search.set(text)
        self.load_docs()


    # ------------------------------------------------------------ dashboard
    @_timed("build_dashboard")
    def build_dashboard(self, parent):
        sf = W.ScrollFrame(parent)
        wrap = tk.Frame(sf.inner, bg=P.BG)
        wrap.pack(fill="both", expand=True, padx=px(14), pady=px(12))
        wrap.columnconfigure(0, weight=3, uniform="d")
        wrap.columnconfigure(1, weight=2, uniform="d")
        admin = self.is_admin()
        self.dcards, self.dl = {}, {}

        def card(key, title, r, c, span=1):
            cd = Card(wrap)
            cd.grid(row=r, column=c, columnspan=span, sticky="nsew", padx=(0, px(7)) if (c == 0 and span == 1) else (px(7), 0) if c == 1 else 0, pady=(0, px(12)))
            tk.Label(cd.body, text=title, bg=P.CARD, fg=P.TITLE, font=(FONT, 11, "bold")).pack(anchor="w")
            self.dcards[key] = cd
            return cd

        def pic(key, cd):
            self.dl[key] = tk.Label(cd.body, bg=P.CARD)
            self.dl[key].pack(anchor="w", pady=(px(8), 0))

        def tree(cd, cols):
            th = tk.Frame(cd.body, bg=P.CARD)
            th.pack(fill="both", expand=True, pady=(px(8), 0))
            t = ttk.Treeview(th, columns=[c[0] for c in cols[1:]], show="tree headings", height=6)
            for k, h, w in cols:
                t.heading(k, text=h, anchor="w")
                t.column(k, width=px(w), anchor="w")
            t.tag_configure("odd", background=P.TILE)
            t.tag_configure("late", foreground="#D32F2F")
            t.pack(fill="both", expand=True)
            return t
        # --- numbers at a glance (each with a short remark)
        defs = [("docs", "Documents", P.ACCENT), ("size", "Storage used", "#2E6DB4"), ("folders", "Folders", "#D4A017"), ("week", "Added this week", "#1D8348"), ("mine", "Added by you", "#8E44AD"),
                ("fav", "Favorites", "#F2B01E"), ("versions", "Versions kept", "#0097A7"), ("trash", "In Recycle bin", "#E0713F")] + ([("users", "Active users", "#3F51B5"), ("pending", "Waiting for approval", "#F28C1E")] if admin else [])
        tiles = tk.Frame(wrap, bg=P.BG)
        tiles.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, px(12)))
        self.tv, self.tvs = {}, {}
        for i, (k, t, col) in enumerate(defs):
            r_, c_ = divmod(i, 5)
            tiles.columnconfigure(c_, weight=1, uniform="t")
            c = Card(tiles)
            c.grid(row=r_, column=c_, sticky="nsew", padx=(0 if c_ == 0 else px(10), 0), pady=(0 if r_ == 0 else px(10), 0))
            tk.Frame(c.body, bg=col, height=px(4), width=px(40)).pack(anchor="w")
            self.tv[k], self.tvs[k] = tk.StringVar(value="-"), tk.StringVar(value="")
            tk.Label(c.body, textvariable=self.tv[k], bg=P.CARD, fg=P.TITLE, font=(FONT, 22, "bold")).pack(anchor="w", pady=(px(8), 0))
            tk.Label(c.body, text=t, bg=P.CARD, fg=P.INK, font=(FONT, 9)).pack(anchor="w")
            tk.Label(c.body, textvariable=self.tvs[k], bg=P.CARD, fg=P.MUTED, font=(FONT, 8)).pack(anchor="w")
        # --- quick review: jump straight back into your documents
        qf = tk.Frame(wrap, bg=P.BG)
        qf.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, px(12)))
        for i in range(3):
            qf.columnconfigure(i, weight=1, uniform="q")

        def qcard(i, title):
            cd = Card(qf)
            cd.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else px(6), 0 if i == 2 else px(6)))
            tk.Label(cd.body, text=title, bg=P.CARD, fg=P.TITLE, font=(FONT, 11, "bold")).pack(anchor="w")
            return cd
        self.q1 = tree(qcard(0, "Recently opened by you"), (("#0", "Name", 210), ("cat", "Folder", 120)))
        self.q2 = tree(qcard(1, "Your favorites"), (("#0", "Name", 210), ("cat", "Folder", 120)))
        self.q3 = tree(qcard(2, "Most opened"), (("#0", "Name", 220), ("n", "Opens", 60)))
        for t_ in (self.q1, self.q2, self.q3):
            t_.bind("<Double-1>", lambda e, t_=t_: self.open_from(t_, e))
        # --- charts
        pic("up", card("up", "Uploads in the last 14 days", 2, 0))
        ct = card("ty", "Documents by type", 2, 1)
        inner = tk.Frame(ct.body, bg=P.CARD)
        inner.pack(fill="both", expand=True, pady=(px(8), 0))
        self.dl["ty"] = tk.Label(inner, bg=P.CARD)
        self.dl["ty"].pack(side="left")
        self.legend = tk.Frame(inner, bg=P.CARD)
        self.legend.pack(side="left", padx=px(18))
        pic("wk", card("wk", "Weekly trend (last 12 weeks)", 3, 0))
        pic("st", card("st", "Storage by file type", 3, 1))
        pic("fo", card("fo", "Top folders", 4, 0))
        pic("co", card("co", "Top contributors", 4, 1))
        self.rt = tree(card("rc", "Recently added", 5, 0), (("#0", "Name", 280), ("cat", "Folder", 160), ("by", "Added by", 120), ("added", "Added", 140)))
        self.rt.bind("<Double-1>", lambda e: self.open_from(self.rt, e))
        self.lt = tree(card("lg", "Largest files", 5, 1), (("#0", "Name", 240), ("cat", "Folder", 150), ("size", "Size", 90)))
        self.lt.bind("<Double-1>", lambda e: self.open_from(self.lt, e))
        self.rv = tree(card("rv", "Review due in the next 30 days", 6, 0), (("#0", "Name", 230), ("due", "Due", 130), ("status", "Status", 100)))
        self.rv.bind("<Double-1>", lambda e: self.open_from(self.rv, e))
        pic("ss", card("ss", "Documents by status", 6, 1))
        if admin:
            self.at = tree(card("ac", "Recent activity", 7, 0, 2), (("#0", "Time", 160), ("user", "User", 220), ("action", "Action", 200)))
        wrap.bind("<Configure>", lambda e: self.dash_later())
        self._dash_tries = 0
        return sf

    @_timed("refresh_dashboard")
    def refresh_dashboard(self):
        if "dashboard" not in self.pages:
            return
        stamp = (core.docs_stamp(), core.logs_stamp(), self.user["id"], tuple(sorted(self._tc.items())))
        if stamp == getattr(self, "_dash_stamp", None):
            return self.dash_later(30)          # same data: only make sure the charts fit the window
        self._dash_stamp = stamp
        st, ex_, wc = core.stats(self.user["id"]), core.extra_stats(), core.week_compare()
        diff = wc["this"] - wc["prev"]
        nums = {"docs": st["docs"], "size": core.size(st["size"]), "folders": st["folders"], "week": ex_["week"], "mine": st["mine"], "fav": st["fav"], "versions": ex_["versions"], "trash": st["trash"],
                "users": st["users"], "pending": st["pending"]}
        subs = {"docs": f"+{wc['this']} in the last 7 days", "size": f"+{wc['mb']} MB in the last 7 days", "folders": "in the library", "week": ("\u25B2 " if diff > 0 else "\u25BC " if diff < 0 else "= ") + f"{abs(diff)} vs the week before",
                "mine": f"{round(100 * st['mine'] / max(1, st['docs']))}% of all documents", "fav": "quick access", "versions": "older versions you can restore", "trash": f"removed after {self.S.get('trash_days')} days",
                "users": "can sign in", "pending": "please review" if st["pending"] else "all clear"}
        for k, v in nums.items():
            if k in self.tv:
                self.tv[k].set(str(v))
                self.tvs[k].set(subs.get(k, ""))
        fmt = self.prefs.get("datefmt", "ISO")

        def fill(tv, docs, extra=None):
            tv.delete(*tv.get_children())
            if not docs:
                tv.insert("", "end", iid="none", text="  nothing here yet")
            for n, d in enumerate(docs):
                tv.insert("", "end", iid=str(d["id"]), text="  " + d["title"], image=self.ficon(core.ftype(d["filename"])[0], 18), tags=("odd",) if n % 2 else (),
                          values=extra(d) if extra else (d["cat"] or "",))
        fill(self.q1, core.recent_opened(self.user["id"], 7))
        fill(self.q2, core.favorites_list(self.user["id"], 7))
        mo = core.most_opened(7)
        counts = {d["id"]: c for d, c in mo}
        fill(self.q3, [d for d, _ in mo], lambda d: (f"{counts.get(d['id'], 0)}x",))
        fill(self.rt, core.recent_docs(8), lambda r: (r["cat"] or "", r["who"] or "", core.fmt_date(r["created"], fmt)))
        fill(self.lt, core.largest_files(8), lambda r: (r["cat"] or "", core.size(r["size"])))
        self.rv.delete(*self.rv.get_children())
        due, today_ = core.review_due(30, 8), dt.date.today().isoformat()
        if not due:
            self.rv.insert("", "end", iid="none", text="  nothing is due for review")
        for n, d in enumerate(due):
            late = d["review"] < today_
            self.rv.insert("", "end", iid=str(d["id"]), text="  " + d["title"], image=self.ficon(core.ftype(d["filename"])[0], 18), tags=("late",) if late else (("odd",) if n % 2 else ()),
                           values=(("overdue  " if late else "") + d["review"], d["status"] or ""))
        if self.is_admin():
            self.at.delete(*self.at.get_children())
            for n, r in enumerate(core.recent_activity(10)):
                self.at.insert("", "end", text=core.fmt_date(r["ts"], fmt), tags=("odd",) if n % 2 else (), values=(r["user"], f"{r['action']}   {r['detail'] or ''}"[:90]))
        self.dash_data = {"up": core.uploads_by_day(14), "ty": core.type_counts(self._tc), "wk": core.week_counts(12), "st": core.storage_by_type(self._tc), "fo": core.top_folders(6), "co": core.top_contributors(6), "ss": core.status_counts()}
        self._dash_tries = 0
        self.dash_later(60)

    def dash_later(self, ms=220):
        if self._dash_job:
            try:
                self.after_cancel(self._dash_job)
            except Exception:
                pass
        self._dash_job = self.after(ms, self.render_dash)

    @_timed("render_dash")
    def render_dash(self):
        self._dash_job = None
        if self.current != "dashboard" or not hasattr(self, "dash_data"):
            return
        try:
            wd = {k: self.dcards[k].winfo_width() - px(44) for k in ("up", "ty", "wk", "st", "fo", "co", "ss")}
            if min(wd.values()) < px(160):
                if self._dash_tries < 8:
                    self._dash_tries += 1
                    self.dash_later(120)
                return
            key = (tuple(wd.values()), getattr(self, "_dash_stamp", None))
            if key == getattr(self, "_dash_key", None):
                return
            self._dash_key = key
            d, h = self.dash_data, px(190)
            up = d["up"]
            vals = [n for _, n in up]
            self._refs["up"] = W.photo_of(g.bars(wd["up"], h, [x.strftime("%d") for x, _ in up], vals, P.ACCENT, P.CARD, ink=P.INK, muted=P.MUTED, grid=P.CHART_GRID, vmax=max(4, max(vals))))
            wk = d["wk"]
            self._refs["wk"] = W.photo_of(g.area(wd["wk"], h, [x.strftime("%d %b") for x, _ in wk], [n for _, n in wk], P.BLUE, P.CARD, ink=P.INK, muted=P.MUTED, grid=P.CHART_GRID))
            ty = d["ty"]
            self._refs["ty"] = W.photo_of(g.donut(px(170), [(n, c) for _, n, c in ty], P.CARD, big=str(sum(n for _, n, _ in ty)), small="documents", ink=P.INK, muted=P.MUTED))
            for w in self.legend.winfo_children():
                w.destroy()
            for lab, n, c in ty:
                row = tk.Frame(self.legend, bg=P.CARD)
                row.pack(anchor="w", pady=px(3))
                tk.Frame(row, bg=c, width=px(11), height=px(11)).pack(side="left", padx=(0, px(8)))
                tk.Label(row, text=f"{lab}   {n}", bg=P.CARD, fg=P.INK, font=(FONT, 10)).pack(side="left")
            if not ty:
                tk.Label(self.legend, text="No documents yet", bg=P.CARD, fg=P.MUTED, font=(FONT, 10)).pack()
            st = d["st"]
            self._refs["st"] = W.photo_of(g.hbars(wd["st"], h, [(lab, mb) for lab, mb, _ in st], P.BLUE, P.CARD, ink=P.INK, muted=P.MUTED, track=P.CHART_TRACK, colors=[c for _, _, c in st], suffix=" MB", label_w=120))
            self._refs["fo"] = W.photo_of(g.hbars(wd["fo"], h, d["fo"], P.BLUE, P.CARD, ink=P.INK, muted=P.MUTED, track=P.CHART_TRACK))
            self._refs["co"] = W.photo_of(g.hbars(wd["co"], h, d["co"], "#8E44AD", P.CARD, ink=P.INK, muted=P.MUTED, track=P.CHART_TRACK))
            ss = d["ss"]
            self._refs["ss"] = W.photo_of(g.hbars(wd["ss"], h, [(lab, n) for lab, n, _ in ss], P.BLUE, P.CARD, ink=P.INK, muted=P.MUTED, track=P.CHART_TRACK, colors=[c for _, _, c in ss], label_w=110))
            for k in ("up", "wk", "ty", "st", "fo", "co", "ss"):
                self.dl[k].configure(image=self._refs[k])
        except tk.TclError:
            pass

    def open_from(self, tree, e):
        s = tree.selection()
        if s and s[0].isdigit() and tree.identify_region(e.x, e.y) not in ("heading", "separator"):
            d = core.get_doc(int(s[0]))
            if d:
                self.open_doc(d)

    # ------------------------------------------------------------ opening documents inside tabs
    @_timed("open_doc")
    def open_doc(self, d):
        key = f"doc:{d['id']}"
        if d["deleted"]:
            return self.toast("This document is in the Recycle bin. Restore it first.", "warn")
        if key in self.builders:
            return self.show_page(key)
        p = core.FILES / d["stored"]
        if not p.exists():
            return self.toast("This file is no longer in the data folder.", "err")
        self.log("open", d["stored"])
        k = core.ftype(d["filename"])[0]
        self.doc_keys[d["id"]] = key
        self.add_page(key, d["title"][:30], lambda parent, d=d: self.build_doc_page(parent, d), closable=True, image=self.ficon(k, 18), color=self.type_color(k), image_on=self.ficon_on(k))
        self.show_page(key)

    # ------------------------------------------------------------ profile and settings
    def open_profile(self, uid=None):
        SettingsDialog(self, uid).show()


class SettingsDialog(W.Dialog):
    """Profile | Security | Preferences  (own account)  or just Profile (an admin editing someone else)."""

    def __init__(self, app, uid=None):
        self.app = app
        self.u = core.q("select * from users where id=?", (uid or app.user["id"],))[0]
        self.own = self.u["id"] == app.user["id"]
        super().__init__(app, "My profile and settings" if self.own else f"Profile - {self.u['username']}", width=640)
        self.changed = False
        RButton(self.bar, "Close", self.close, "soft", big=True).pack(side="right")
        self.pills = None
        if self.own:
            self.pills = PillGroup(self.body, [("profile", "Profile", P.PRIMARY), ("security", "Security", P.PRIMARY), ("prefs", "Preferences", P.PRIMARY), ("colors", "Colours", P.PRIMARY)], command=self.tab)
            self.pills.pack(fill="x", pady=(px(8), px(10)))
            self.pills.set("profile")
        self.host = tk.Frame(self.body, bg=P.CARD)
        self.host.pack(fill="both", expand=True)
        self.tab("profile")

    def tab(self, key):
        for w in self.host.winfo_children():
            w.destroy()
        self.err.configure(text="")
        getattr(self, "t_" + key)(self.host)

    def close(self):
        self.destroy()
        if self.changed:
            self.app.rebuild()

    def t_colors(self, f):
        tk.Label(f, text="Choose the colour of each file type. It is used for the file icon, the tab and the charts.\nFolder colours: right-click a folder (admin) > Folder colour.", bg=P.CARD, fg=P.MUTED,
                 font=(FONT, 9), justify="left").pack(anchor="w", pady=(0, px(8)))
        grid = tk.Frame(f, bg=P.CARD)
        grid.pack(fill="x")
        types = [(k, v[0], v[2]) for k, v in core.FT.items()] + [("file", core.FT_OTHER[0], core.FT_OTHER[1])]
        for i, (k, label, col) in enumerate(types):
            r_, c_ = i % 7, i // 7
            cell = tk.Frame(grid, bg=P.CARD)
            cell.grid(row=r_, column=c_, sticky="w", padx=(0, px(26)), pady=px(3))
            sw = tk.Label(cell, text="      ", bg=self.app.type_color(k), bd=1, relief="solid")
            sw.pack(side="left")
            tk.Label(cell, text=label, bg=P.CARD, fg=P.INK, font=(FONT, 10), width=15, anchor="w").pack(side="left", padx=px(8))
            RButton(cell, "Change", lambda k=k, sw=sw: self.pick_type(k, sw), "soft").pack(side="left")
        RButton(f, "Reset all to the original colours", self.reset_colors, "ghost").pack(anchor="w", pady=(px(14), 0))

    def pick_type(self, k, sw):
        from tkinter import colorchooser
        c = colorchooser.askcolor(color=self.app.type_color(k), parent=self, title="Choose a colour")[1]
        if c:
            self.app.prefs.set("fc_" + k, c.upper())
            self.app._tc = self.app.type_colors()
            sw.configure(bg=c)
            self.changed = True

    def reset_colors(self):
        for k in list(core.FT) + ["file"]:
            self.app.prefs.set("fc_" + k, "")
        self.app._tc = {}
        self.changed = True
        self.tab("colors")

    def draw_avatar(self):
        u = core.q("select * from users where id=?", (self.u["id"],))[0]
        self._av = self.app.avatar_image(120, dict(u))
        self.av.configure(image=self._av)

    def t_profile(self, f):
        app, u = self.app, self.u
        admin = app.is_admin()
        can = admin or self.own
        left = tk.Frame(f, bg=P.CARD)
        left.pack(side="left", anchor="n", padx=(0, px(26)))
        self.av = tk.Label(left, bg=P.CARD)
        self.av.pack()
        self.draw_avatar()
        if can:
            RButton(left, "Change photo", self.photo, "soft").pack(pady=(px(10), px(4)), fill="x")
            RButton(left, "Remove photo", self.nophoto, "ghost").pack(fill="x")
        right = tk.Frame(f, bg=P.CARD)
        right.pack(side="left", fill="x", expand=True)
        self.fl = {}
        for k, lab, ed in (("name", "FULL NAME", can), ("emp_id", "EMPLOYEE ID" + ("" if admin else "  (set by admin)"), admin), ("dept", "DEPARTMENT", can),
                           ("designation", "DESIGNATION", can), ("email", "EMAIL ID (ALSO YOUR SIGN-IN)", can), ("phone", "PHONE", can)):
            fld = Field(right, lab, width=34, value=u[k] or "")
            fld.pack(fill="x", pady=(px(6), 0))
            if not ed:
                fld.lock()
            self.fl[k] = fld
        self.role = tk.StringVar(value=u["role"])
        if admin and not self.own:
            tk.Label(right, text="ROLE", bg=P.CARD, fg=P.MUTED, font=(FONT, 8, "bold"), anchor="w").pack(fill="x", pady=(px(8), 0))
            W.ttk_combo(right, self.role, ["user", "admin"], 30).pack(fill="x", pady=(px(3), 0))
        if can:
            RButton(right, "Save profile", self.save_profile, "main", big=True).pack(anchor="e", pady=(px(14), 0))

    def photo(self):
        if self.app.pick_photo(self.u["id"]):
            self.draw_avatar()

    def nophoto(self):
        core.remove_photo(self.u["id"])
        self.draw_avatar()
        self.app.after_user_change(self.u["id"])

    def save_profile(self):
        v = {k: f.get() for k, f in self.fl.items()}
        if not v["name"]:
            return self.fail("The name cannot be empty.")
        e = v["email"].lower()
        if e and not core.EMAIL_RE.fullmatch(e):
            return self.fail("Please enter a valid email ID.")
        if e and core.q("select 1 from users where id!=? and (lower(email)=? or username=?)", (self.u["id"], e, e)):
            return self.fail("That email ID is already used by another account.")
        emp = v["emp_id"] if self.app.is_admin() else (self.u["emp_id"] or "")
        core.ex("update users set name=?, emp_id=?, dept=?, designation=?, email=?, phone=?, role=? where id=?",
                (v["name"], emp, v["dept"], v["designation"], e, v["phone"], self.role.get() if (self.app.is_admin() and not self.own) else self.u["role"], self.u["id"]))
        self.app.log("profile updated", self.u["username"])
        self.app.after_user_change(self.u["id"])
        self.app.toast("Profile saved.")
        self.destroy()

    def t_security(self, f):
        q_ = self.app.user.get("question") or "Not set yet"
        tk.Label(f, text="PASSWORD", bg=P.CARD, fg=P.MUTED, font=(FONT, 8, "bold")).pack(anchor="w", pady=(px(6), px(4)))
        RButton(f, "Change password...", self.app.change_password_dialog, "soft").pack(anchor="w")
        tk.Label(f, text="SECURITY QUESTION  (lets you recover your username or password)", bg=P.CARD, fg=P.MUTED, font=(FONT, 8, "bold")).pack(anchor="w", pady=(px(20), px(4)))
        tk.Label(f, text=q_, bg=P.CARD, fg=P.INK, font=(FONT, 10)).pack(anchor="w", pady=(0, px(6)))
        RButton(f, "Set or change the question...", self.app.set_question_dialog, "soft").pack(anchor="w")

    def t_prefs(self, f):
        app = self.app
        pr = app.prefs
        g_ = tk.Frame(f, bg=P.CARD)
        g_.pack(fill="x")
        self.pv = {}

        def row(r, text, widget):
            tk.Label(g_, text=text, bg=P.CARD, fg=P.MUTED, font=(FONT, 9), anchor="e", width=18).grid(row=r, column=0, sticky="e", padx=(0, px(12)), pady=px(5))
            widget.grid(row=r, column=1, sticky="w", pady=px(5))
        self.theme = PillGroup(g_, [("light", "Light", P.PRIMARY), ("dark", "Dark", P.PRIMARY)])
        self.theme.set(pr.get("theme", "light"))
        row(0, "Theme", self.theme)
        names = ["Brand colour"] + list(core.ACCENT_NAMES) + ["Custom colour..."]
        cur = pr.get("accent", "")
        self.custom = [cur if core.is_hex(cur) else "#E8312F"]
        self.acc = tk.StringVar(value="Custom colour..." if core.is_hex(cur) else (cur if cur in core.ACCENT_NAMES else "Brand colour"))
        cb = W.ttk_combo(g_, self.acc, names, 24)
        cb.bind("<<ComboboxSelected>>", self.pick_accent)
        row(1, "Accent colour", cb)
        self.datef = tk.StringVar(value=core.DATE_LABELS.get(pr.get("datefmt", "ISO"), core.DATE_LABELS["ISO"]))
        row(2, "Date format", W.ttk_combo(g_, self.datef, list(core.DATE_LABELS.values()), 24))
        self.viewv = tk.StringVar(value=pr.get("view", core.VIEWS[0]))
        row(3, "Default library view", W.ttk_combo(g_, self.viewv, core.VIEWS, 24))
        self.idle = tk.StringVar(value=next((k for k, m in core.IDLE.items() if str(m) == pr.get("idle", "0")), "Never"))
        row(4, "Sign me out after", W.ttk_combo(g_, self.idle, list(core.IDLE), 24))
        cols = tk.Frame(g_, bg=P.CARD)
        shown = pr.get("cols", "type,status,cat,size,by,added").split(",")
        self.cvars = {}
        for k, t in core.COLS:
            self.cvars[k] = tk.BooleanVar(value=k in shown)
            tk.Checkbutton(cols, text=t, variable=self.cvars[k], bg=P.CARD, activebackground=P.CARD, fg=P.INK, selectcolor=P.FIELD, bd=0, highlightthickness=0, font=(FONT, 9)).pack(side="left", padx=(0, px(8)))
        row(5, "Columns in the list", cols)
        box = tk.Frame(f, bg=P.CARD)
        box.pack(fill="x", pady=(px(8), 0))
        for k, t, d in (("row_tint", "Add a soft colour to each row by file type", "0"), ("confirm_delete", "Ask before deleting a document", "1"), ("remember", "Remember the last folder I used", "1"), ("details", "Show the details line under the list", "1"),
                        ("start_dash", "Start on the Dashboard after I sign in", "0"), ("auto_open2", "Also open file types TDMS cannot show in their own program", "0")):
            self.pv[k] = tk.BooleanVar(value=pr.get(k, d) == "1")
            tk.Checkbutton(box, text=t, variable=self.pv[k], bg=P.CARD, activebackground=P.CARD, fg=P.INK, selectcolor=P.FIELD, bd=0, highlightthickness=0, font=(FONT, 10), cursor="hand2").pack(anchor="w", pady=px(2))
        RButton(f, "Save preferences", self.save_prefs, "main", big=True).pack(anchor="e", pady=(px(12), 0))

    def pick_accent(self, _e=None):
        if self.acc.get() == "Custom colour...":
            from tkinter import colorchooser
            c = colorchooser.askcolor(color=self.custom[0], parent=self, title="Choose an accent colour")[1]
            if c:
                self.custom[0] = c.upper()
            else:
                self.acc.set("Brand colour")

    def save_prefs(self):
        app, pr = self.app, self.app.prefs
        accent = "" if self.acc.get() == "Brand colour" else self.custom[0] if self.acc.get() == "Custom colour..." else self.acc.get()
        look_changed = (pr.get("theme", "light"), pr.get("accent", "")) != (self.theme.get() or "light", accent)
        pr.set("theme", self.theme.get() or "light")
        pr.set("accent", accent)
        pr.set("datefmt", next((k for k, v in core.DATE_LABELS.items() if v == self.datef.get()), "ISO"))
        pr.set("view", self.viewv.get())
        pr.set("idle", core.IDLE[self.idle.get()])
        pr.set("cols", ",".join(k for k, v in self.cvars.items() if v.get()) or "type")
        for k, v in self.pv.items():
            pr.set(k, "1" if v.get() else "0")
        app.log("preferences saved")
        self.destroy()
        app.rebuild()
        app.toast("Preferences saved.")


class VersionsDialog(W.Dialog):
    """Current file + every older version.  Open, save a copy, or restore one."""

    def __init__(self, app, d):
        self.app, self.did = app, d["id"]
        super().__init__(app, f"Versions - {d['title']}", width=740)
        holder, self.tv = adm.table(self.body, [("ver", "Version", 110), ("file", "File", 240), ("size", "Size", 90), ("by", "By", 150), ("date", "Date", 140), ("note", "Note", 200)], height=8)
        holder.pack(fill="both", expand=True, pady=(px(10), 0))
        RButton(self.bar, "Close", self.destroy, "soft", big=True).pack(side="right")
        RButton(self.bar, "Restore this version", self.restore, "main", big=True).pack(side="right", padx=px(6))
        RButton(self.bar, "Save a copy...", self.save_copy, "soft", big=True).pack(side="right", padx=px(6))
        RButton(self.bar, "Open", self.open, "navy", big=True).pack(side="right")
        self.load()

    def load(self):
        d = core.get_doc(self.did)
        self.tv.delete(*self.tv.get_children())
        who = core.q("select name from users where id=?", (d["updated_by"] or d["uploader_id"],))
        self.tv.insert("", "end", iid="cur", values=(f"v{d['ver'] or 1}  (current)", d["filename"], core.size(d["size"]), who[0]["name"] if who else "", d["created"], d["vnote"] or ""))
        for v in core.versions_of(self.did):
            self.tv.insert("", "end", iid=f"v{v['id']}", values=(f"v{v['ver']}", v["filename"], core.size(v["size"]), v["who"] or "", v["created"], v["note"] or ""))
        self.tv.selection_set("cur")

    def sel(self):
        s = self.tv.selection()
        return s[0] if s else None

    def path(self, iid):
        if iid == "cur":
            return core.FILES / core.get_doc(self.did)["stored"]
        v = core.q("select * from versions where id=?", (int(iid[1:]),)) if iid else []
        return core.FILES / v[0]["stored"] if v else None

    def open(self):
        p = self.path(self.sel())
        if p and p.exists():
            open_path(p)
        else:
            self.fail("That file is not available.")

    def save_copy(self):
        p = self.path(self.sel())
        if not p or not p.exists():
            return self.fail("That file is not available.")
        dest = filedialog.asksaveasfilename(initialfile=p.name, parent=self)
        if dest:
            shutil.copy2(p, dest)
            self.app.toast("Copy saved.")

    def restore(self):
        iid = self.sel()
        if not iid or iid == "cur":
            return self.fail("Pick an older version to restore.")
        v = core.q("select * from versions where id=?", (int(iid[1:]),))
        if not v:
            return
        core.restore_version(core.get_doc(self.did), v[0], self.app.user["id"])
        self.app.log("restore version", f"v{v[0]['ver']}")
        self.app.after_version_change(self.did)
        self.load()
        self.app.toast(f"Version {v[0]['ver']} is now the current file.")


class App(AppBase, tk.Tk):
    pass


def main():
    App().mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        with open(os.path.join(BASE, "tdms_error.log"), "a", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
