"""
TDMS viewers  -  what opens inside a tab:
  PDF (scroll like Adobe, select and copy text, find), Word, Excel / CSV tables, PowerPoint, pictures with zoom,
  video / audio, web links, text files, and an "exact view" of Office files through Microsoft Office.
Mixed into the main window as  ViewerMixin.
"""
import base64
import bisect
import importlib
import os
import subprocess
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, ttk

import tdms_core as core
import tdms_graphics as g
import tdms_widgets as W
from tdms_widgets import P, px, FONT, RButton, SearchBox

try:
    import fitz     # PyMuPDF
except Exception:
    fitz = None


def open_path(path):
    try:
        if os.name == "nt":
            os.startfile(str(path))
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


def mci(cmd):
    import ctypes
    buf = ctypes.create_unicode_buffer(256)
    err = ctypes.windll.winmm.mciSendStringW(cmd, buf, 255, 0)
    return err, buf.value


def mci_error(err):
    import ctypes
    buf = ctypes.create_unicode_buffer(256)
    ctypes.windll.winmm.mciGetErrorStringW(err, buf, 255)
    return buf.value or f"media error {err}"


def fill_table(tv, rows, header=False):
    """Show rows (lists of text) in a Treeview with sensible column widths."""
    heads = rows[0] if (header and rows) else []
    body = rows[1:] if header and rows else rows
    n = min(80, max((len(r) for r in rows), default=1)) or 1
    cols = ["rn"] + [core.colname(i) for i in range(n)]
    tv.delete(*tv.get_children())
    tv.configure(columns=cols)
    sample = rows[:300]
    for i, c in enumerate(cols):
        if i == 0:
            w, t = px(54), "#"
        else:
            longest = max((len(r[i - 1]) for r in sample if i - 1 < len(r)), default=4)
            w = px(min(max(longest * 7 + 24, 70), 520))
            t = (heads[i - 1] if i - 1 < len(heads) and heads[i - 1] else core.colname(i - 1))
        tv.heading(c, text=t, anchor="w")
        tv.column(c, width=w, anchor="w", stretch=False)
    off = 2 if header else 1
    for i, r in enumerate(body, off):
        tv.insert("", "end", tags=("odd",) if i % 2 == 0 else (), values=[i] + (r + [""] * n)[:n])
    return len(rows)


# =============================================================================== PDF (continuous, selectable)
class PdfView(tk.Frame):
    PAD = 14

    def __init__(self, app, parent, pdf_path):
        super().__init__(parent, bg=P.CARD)
        self.app = app
        self.doc = fitz.open(str(pdf_path))
        if self.doc.needs_pass:
            raise ValueError("This PDF is password-protected.")
        self.n = len(self.doc)
        self.sizes = [(self.doc[i].rect.width, self.doc[i].rect.height) for i in range(self.n)]
        self.z, self.offs, self.xs, self.total = 1.0, [], [0] * self.n, 1
        self.items, self.photos, self.words = {}, {}, {}
        self.sel, self.anchor, self._drag = None, None, False
        self.matches, self.mi, self.last_q, self._job, self._cfg, self._t = [], -1, None, None, None, 0
        self._zf, self._zj, self.total_w = 1.0, None, 1
        tb = tk.Frame(self, bg=P.CARD)
        tb.pack(fill="x", pady=(0, px(8)))
        self.plab, self.zlab, self.mlab = tk.StringVar(), tk.StringVar(value="100%"), tk.StringVar()
        RButton(tb, "Fit width", self.fit_width, "soft").pack(side="left", padx=(0, px(6)))
        RButton(tb, "\u2212", lambda: self.zoom_by(1 / 1.2), "soft", width=px(40)).pack(side="left")
        tk.Label(tb, textvariable=self.zlab, bg=P.CARD, fg=P.MUTED, font=(FONT, 9), width=6).pack(side="left")
        RButton(tb, "+", lambda: self.zoom_by(1.2), "soft", width=px(40)).pack(side="left", padx=(0, px(14)))
        tk.Label(tb, text="Page", bg=P.CARD, fg=P.MUTED, font=(FONT, 9)).pack(side="left")
        self.pe = tk.Entry(tb, width=5, relief="flat", bd=0, highlightthickness=1, highlightbackground=P.LINE, highlightcolor=P.BLUE, font=(FONT, 10), justify="center", bg=P.FIELD, fg=P.INK, insertbackground=P.INK)
        self.pe.pack(side="left", padx=px(6), ipady=px(4))
        self.pe.bind("<Return>", self.go_entry)
        tk.Label(tb, textvariable=self.plab, bg=P.CARD, fg=P.MUTED, font=(FONT, 9)).pack(side="left")
        RButton(tb, "Copy text", self.copy_sel, "soft").pack(side="right", padx=(px(6), 0))
        RButton(tb, "\u25BC", lambda: self.find_step(1), "soft", width=px(40)).pack(side="right")
        RButton(tb, "\u25B2", lambda: self.find_step(-1), "soft", width=px(40)).pack(side="right", padx=px(4))
        tk.Label(tb, textvariable=self.mlab, bg=P.CARD, fg=P.MUTED, font=(FONT, 9), width=9).pack(side="right")
        self.fe = SearchBox(tb, "Find in PDF...", lambda t: self.find_step(1), width=20)
        self.fe.pack(side="right", padx=(0, px(6)))
        wrap = tk.Frame(self, bg=P.CARD)
        wrap.pack(fill="both", expand=True)
        self.cv = tk.Canvas(wrap, bg="#DCE2E8" if P.theme == "light" else "#0B111B", highlightthickness=0, yscrollincrement=px(30))
        self.vs = ttk.Scrollbar(wrap, command=self.cv.yview)
        self.hs = ttk.Scrollbar(wrap, orient="horizontal", command=self.cv.xview)
        self.cv.configure(yscrollcommand=self.on_scroll, xscrollcommand=self.hs.set)
        self.hs.pack(side="bottom", fill="x")
        self.vs.pack(side="right", fill="y")
        self.cv.pack(fill="both", expand=True)
        cv = self.cv
        cv.bind("<Enter>", lambda e: cv.focus_set())
        cv.bind("<MouseWheel>", self.wheel)
        cv.bind("<Shift-MouseWheel>", lambda e: (cv.xview_moveto(max(0.0, (cv.canvasx(0) - e.delta * 0.9) / max(1, self.total_w))), "break")[1])
        cv.bind("<Control-MouseWheel>", self.zoom_wheel)
        cv.bind("<ButtonPress-1>", self.press)
        cv.bind("<B1-Motion>", self.drag)
        cv.bind("<ButtonRelease-1>", lambda e: setattr(self, "_drag", False))
        cv.bind("<Double-Button-1>", self.dbl)
        cv.bind("<Motion>", self.hover)
        cv.bind("<Control-c>", lambda e: self.copy_sel())
        cv.bind("<Control-a>", lambda e: self.select_all())
        cv.bind("<Control-f>", lambda e: self.fe.focus())
        cv.bind("<Button-3>", self.menu)
        cv.bind("<Prior>", lambda e: (cv.yview_scroll(-8, "units"), self.sched()))
        cv.bind("<Next>", lambda e: (cv.yview_scroll(8, "units"), self.sched()))
        cv.bind("<Home>", lambda e: self.goto(0))
        cv.bind("<End>", lambda e: self.goto(self.n - 1))
        cv.bind("<Up>", lambda e: (cv.yview_scroll(-2, "units"), self.sched()))
        cv.bind("<Down>", lambda e: (cv.yview_scroll(2, "units"), self.sched()))
        cv.bind("<Configure>", self.on_cfg)
        self.bind("<Destroy>", self.on_destroy)
        self.layout()
        self.after(160, self.fit_width)

    # ---- geometry
    def k(self):
        return self.z * W.SCALE * 96 / 72

    def layout(self):
        k = self.k()
        y, self.offs = self.PAD, []
        for w, h in self.sizes:
            self.offs.append(y)
            y += h * k + self.PAD
        self.total = max(1, y)
        cw = max(self.cv.winfo_width(), max(w for w, _ in self.sizes) * k + 2 * self.PAD)
        self.total_w = cw
        for i, (w, h) in enumerate(self.sizes):
            self.xs[i] = (cw - w * k) / 2
        self.cv.delete("all")
        self.items, self.photos = {}, {}
        self.cv.configure(scrollregion=(0, 0, cw, self.total))
        for i, (w, h) in enumerate(self.sizes):
            self.cv.create_rectangle(self.xs[i], self.offs[i], self.xs[i] + w * k, self.offs[i] + h * k, fill="white", outline="#B8C2CC")
        self.zlab.set(f"{int(self.z * 100)}%")
        self.render_visible()

    def relayout(self):
        p = self.cur_page()
        h = self.sizes[p][1] * self.k()
        frac = (self.cv.canvasy(0) - self.offs[p]) / h if (self.offs and h) else 0
        self.layout()
        self.cv.yview_moveto(max(0, self.offs[p] + frac * self.sizes[p][1] * self.k()) / self.total)
        self.sched()

    def on_cfg(self, e):
        if self._cfg:
            self.after_cancel(self._cfg)
        self._cfg = self.after(140, self.relayout)

    def wheel(self, e):
        """Mouse wheel and two-finger touchpad scrolling (small steps add up smoothly)."""
        if e.state & 4:
            return self.zoom_wheel(e)
        self.cv.yview_moveto(max(0.0, (self.cv.canvasy(0) - e.delta * 0.9) / self.total))
        self.sched()
        return "break"

    def zoom_wheel(self, e):
        """Ctrl + wheel, and pinch in / out on a touchpad (Windows sends it as Ctrl + wheel)."""
        self._zf *= 1.1 ** (e.delta / 120)
        if not self._zj:
            self._zj = self.after(70, self._apply_zoom)
        return "break"

    def _apply_zoom(self):
        f, self._zf, self._zj = self._zf, 1.0, None
        if abs(f - 1) > 0.004:
            self.zoom_by(f)

    def on_scroll(self, a, b):
        self.vs.set(a, b)
        self.sched()

    def sched(self):
        if self._job:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
        self._job = self.after(25, self.render_visible)

    # ---- drawing pages
    def render_visible(self):
        self._job = None
        if not self.offs or not self.winfo_exists():
            return
        k, top = self.k(), self.cv.canvasy(0)
        bot = top + self.cv.winfo_height()
        vis = [i for i in range(self.n) if self.offs[i] + self.sizes[i][1] * k >= top - 300 and self.offs[i] <= bot + 300]
        for i in vis:
            if i not in self.items:
                self.draw_page(i)
        first = vis[0] if vis else 0
        for i in list(self.items):
            if i not in vis and abs(i - first) > 4:
                self.cv.delete(self.items.pop(i))
                self.photos.pop(i, None)
        self.draw_sel()
        self.draw_hits()
        p = self.cur_page()
        self.plab.set(f"of {self.n}")
        if self.focus_get() is not self.pe:
            self.pe.delete(0, "end")
            self.pe.insert(0, str(p + 1))

    def draw_page(self, i):
        k = self.k()
        pix = self.doc[i].get_pixmap(matrix=fitz.Matrix(k, k), alpha=False)
        try:                                    # raw pixels: much faster than PNG encode + decode
            ph = tk.PhotoImage(data=pix.tobytes("ppm"))
        except Exception:
            ph = tk.PhotoImage(data=base64.b64encode(pix.tobytes("png")).decode())
        self.photos[i] = ph
        self.items[i] = self.cv.create_image(self.xs[i], self.offs[i], anchor="nw", image=ph)

    def cur_page(self):
        if not self.offs:
            return 0
        mid = self.cv.canvasy(self.cv.winfo_height() / 3)
        return max(0, min(self.n - 1, bisect.bisect_right(self.offs, mid) - 1))

    def goto(self, i, dy=0):
        i = max(0, min(self.n - 1, i))
        self.cv.yview_moveto(max(0, self.offs[i] - self.PAD + dy) / self.total)
        self.sched()

    def go_entry(self, _e=None):
        try:
            self.goto(int(self.pe.get()) - 1)
        except ValueError:
            pass
        self.cv.focus_set()

    def zoom_by(self, f):
        self.z = max(.3, min(4.0, self.z * f))
        self.relayout()

    def fit_width(self):
        try:
            avail = max(200, self.cv.winfo_width() - 2 * self.PAD - px(6))
            self.z = max(.3, min(4.0, avail / (max(w for w, _ in self.sizes) * W.SCALE * 96 / 72)))
            self.relayout()
        except tk.TclError:
            pass

    # ---- text: words, hit test, selection, copy
    def words_of(self, i):
        if i not in self.words:
            ws = list(self.doc[i].get_text("words"))
            ws.sort(key=lambda w: (w[5], w[6], w[7]))
            self.words[i] = ws
        return self.words[i]

    def page_at(self, cy):
        if not self.offs:
            return None
        return max(0, min(self.n - 1, bisect.bisect_right(self.offs, cy) - 1))

    def hit(self, cx, cy):
        i = self.page_at(cy)
        if i is None:
            return None
        k = self.k()
        x, y = (cx - self.xs[i]) / k, (cy - self.offs[i]) / k
        best, bd = None, 1e18
        for j, w in enumerate(self.words_of(i)):
            dx = max(w[0] - x, 0, x - w[2])
            dy = max(w[1] - y, 0, y - w[3])
            d = dx * dx + dy * dy * 4
            if d < bd:
                bd, best = d, j
                if d == 0:
                    break
        return (i, best, bd) if best is not None else None

    def press(self, e):
        self.cv.focus_set()
        h = self.hit(self.cv.canvasx(e.x), self.cv.canvasy(e.y))
        self._drag = True
        self.anchor = (h[0], h[1]) if h else None
        self.sel = (self.anchor, self.anchor) if h else None
        self.draw_sel()

    def drag(self, e):
        if not self._drag or not self.anchor:
            return
        h = self.hit(self.cv.canvasx(e.x), self.cv.canvasy(e.y))
        if h:
            self.sel = (self.anchor, (h[0], h[1]))
        if e.y < px(24):
            self.cv.yview_scroll(-1, "units")
        elif e.y > self.cv.winfo_height() - px(24):
            self.cv.yview_scroll(1, "units")
        self.draw_sel()
        self.sched()

    def dbl(self, e):
        h = self.hit(self.cv.canvasx(e.x), self.cv.canvasy(e.y))
        if h:
            self.sel = ((h[0], h[1]), (h[0], h[1]))
            self.draw_sel()

    def hover(self, e):
        t = time.time()
        if self._drag or t - self._t < 0.04:
            return
        self._t = t
        h = self.hit(self.cv.canvasx(e.x), self.cv.canvasy(e.y))
        self.cv.configure(cursor="xterm" if h and h[2] == 0 else "arrow")

    def sel_range(self):
        if not self.sel or not self.sel[0] or not self.sel[1]:
            return None
        a, b = self.sel
        return (a, b) if a <= b else (b, a)

    def select_all(self):
        last = self.n - 1
        self.words_of(last)
        self.sel = ((0, 0), (last, max(0, len(self.words_of(last)) - 1)))
        self.draw_sel()

    def draw_sel(self):
        self.cv.delete("sel")
        r = self.sel_range()
        if not r:
            return
        (p1, i1), (p2, i2) = r
        for p in range(p1, p2 + 1):
            if p not in self.items:
                continue
            ws = self.words_of(p)
            lo, hi = (i1 if p == p1 else 0), (i2 if p == p2 else len(ws) - 1)
            line = None
            for j in range(lo, hi + 1):
                w = ws[j]
                key = (w[5], w[6])
                if line and line[0] == key:
                    line[1], line[2], line[3], line[4] = min(line[1], w[0]), min(line[2], w[1]), max(line[3], w[2]), max(line[4], w[3])
                else:
                    if line:
                        self._rect(p, line, "#1A73E8", "gray25", "sel")
                    line = [key, w[0], w[1], w[2], w[3]]
            if line:
                self._rect(p, line, "#1A73E8", "gray25", "sel")
        self.cv.tag_raise("sel")

    def _rect(self, p, l, fill, stip, tag):
        k, x, y = self.k(), self.xs[p], self.offs[p]
        self.cv.create_rectangle(x + l[1] * k, y + l[2] * k, x + l[3] * k, y + l[4] * k, fill=fill, outline="", stipple=stip, tags=(tag,))

    def sel_text(self):
        r = self.sel_range()
        if not r:
            return ""
        (p1, i1), (p2, i2) = r
        out, prev = [], None
        for p in range(p1, p2 + 1):
            ws = self.words_of(p)
            for j in range(i1 if p == p1 else 0, (i2 if p == p2 else len(ws) - 1) + 1):
                w = ws[j]
                key = (p, w[5], w[6])
                out.append(w[4] if prev is None else (" " + w[4]) if key == prev else ("\n" + w[4]))
                prev = key
        return "".join(out)

    def copy_sel(self):
        t = self.sel_text()
        if not t:
            return self.app.toast("Select some text first (drag over it, or double-click a word).", "info")
        self.app.clipboard_clear()
        self.app.clipboard_append(t)
        self.app.toast(f"Copied {len(t.split())} words.")

    def menu(self, e):
        m = tk.Menu(self, tearoff=0, font=(FONT, 10), bg=P.CARD, fg=P.INK, activebackground=P.ACCENT, activeforeground="#FFFFFF", bd=0)
        m.add_command(label="Copy", command=self.copy_sel)
        m.add_command(label="Select all text", command=self.select_all)
        m.add_command(label="Find...", command=self.fe.focus)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    # ---- find
    def find_step(self, step):
        t = self.fe.get()
        if not t:
            return
        if t != self.last_q:
            self.last_q, self.matches, self.mi = t, [], -1
            for i in range(self.n):
                for r in self.doc[i].search_for(t):
                    self.matches.append((i, r))
                if len(self.matches) > 800:
                    break
        if not self.matches:
            self.mlab.set("0 found")
            return
        self.mi = (self.mi + step) % len(self.matches)
        i, r = self.matches[self.mi]
        self.mlab.set(f"{self.mi + 1} of {len(self.matches)}")
        self.cv.yview_moveto(max(0, self.offs[i] + r.y0 * self.k() - self.cv.winfo_height() * 0.3) / self.total)
        self.sched()

    def draw_hits(self):
        self.cv.delete("hit")
        for n, (i, r) in enumerate(self.matches):
            if i in self.items:
                self._rect(i, (None, r.x0, r.y0, r.x1, r.y1), "#FF9800" if n == self.mi else "#FFD400", "gray50", "hit")
        self.cv.tag_raise("sel")

    def on_destroy(self, e):
        if e.widget is self:
            try:
                self.doc.close()
            except Exception:
                pass


# =============================================================================== the mixin
class ViewerMixin:
    def have_pdf(self):
        return fitz is not None

    def save_path(self, p):
        dest = filedialog.asksaveasfilename(initialfile=p.name)
        if dest:
            import shutil
            shutil.copy2(p, dest)
            self.toast("Copy saved.")

    def vbar(self, body, p, d=None, exact=False):
        bar = tk.Frame(body, bg=P.CARD)
        bar.pack(fill="x", pady=(0, px(10)))
        tk.Label(bar, text=p.name, bg=P.CARD, fg=P.TITLE, font=(FONT, 13, "bold")).pack(side="left", padx=(0, px(16)))
        RButton(bar, "Open in program", lambda: open_path(p), "soft").pack(side="right", padx=(px(6), 0))
        RButton(bar, "Save a copy", lambda: self.save_path(p), "soft").pack(side="right")
        if exact and d is not None:
            RButton(bar, "Exact view (PDF)", lambda: self.switch_exact(body, d, p), "navy").pack(side="right", padx=(0, px(6)))
        return bar

    def switch_exact(self, body, d, p):
        for w in body.winfo_children():
            w.destroy()
        self.v_office(body, d, p)

    def build_doc_page(self, parent, d):
        page = tk.Frame(parent, bg=P.BG)
        card = W.Card(page)
        card.pack(fill="both", expand=True, padx=px(16), pady=px(14))
        body = card.body
        p = core.FILES / d["stored"]
        ext = p.suffix.lower()
        k, label, _ = core.ftype(d["filename"])
        if ext in core.TEXT and p.stat().st_size < 5_000_000:
            viewer = self.v_text
        elif ext == ".pdf":
            viewer = self.v_pdf
        elif ext == ".docx":
            viewer = self.v_docx
        elif ext in (".doc", ".rtf", ".odt", ".xls", ".xlsb", ".ppt", ".pps", ".ppsx"):
            viewer = self.v_office
        elif ext in (".xlsx", ".xlsm"):
            viewer = self.v_xlsx
        elif ext == ".pptx":
            viewer = self.v_pptx
        elif ext in core.CSV_EXT:
            viewer = self.v_csv
        elif ext in core.IMG_EXT:
            viewer = self.v_image
        elif ext in core.LINK_EXT or ext in core.WEB_EXT:
            viewer = self.v_link
        elif ext in core.VIDEO_EXT:
            viewer = self.v_media
        elif ext in core.AUDIO_EXT:
            viewer = lambda b, dd, pp: self.v_media(b, dd, pp, audio=True)
        else:
            viewer = None
        try:
            if viewer:
                viewer(body, d, p)
            else:
                self.v_other(body, p, k, label)
        except Exception as e:
            for w in body.winfo_children():
                w.destroy()
            self.v_other(body, p, k, label, f"This file could not be shown inside the app ({e}).")
        return page

    def text_box(self, body, mono=False, wrap="word"):
        holder = tk.Frame(body, bg=P.LINE)
        holder.pack(fill="both", expand=True)
        t = tk.Text(holder, wrap=wrap, bd=0, relief="flat", padx=px(24), pady=px(16), bg=P.FIELD, fg=P.INK, insertbackground=P.INK, selectbackground=P.SEL, selectforeground=P.INK,
                    font=(("Consolas" if os.name == "nt" else "DejaVu Sans Mono") if mono else FONT, 11), spacing3=px(4))
        sb = ttk.Scrollbar(holder, command=t.yview)
        t.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        t.pack(fill="both", expand=True, padx=1, pady=1)
        return t

    # ---- text
    def v_text(self, body, d, p):
        raw = p.read_bytes()
        try:
            txt, enc = raw.decode("utf-8"), "utf-8"
        except UnicodeDecodeError:
            txt, enc = raw.decode("cp1252", errors="replace"), "cp1252"
        crlf = "\r\n" in txt
        txt = txt.replace("\r\n", "\n")
        bar = self.vbar(body, p)
        st = tk.StringVar()
        t = self.text_box(body, mono=True)
        t.configure(undo=True)

        def save():
            data = t.get("1.0", "end-1c")
            data = data.replace("\n", "\r\n") if crlf else data
            p.write_bytes(data.encode(enc, errors="replace"))
            core.ex("update docs set size=? where id=?", (p.stat().st_size, d["id"]))
            self.log("edit", d["stored"])
            st.set("Saved " + core.now())
            self.load_docs()
        RButton(bar, "Save  (Ctrl+S)", save, "main").pack(side="left")
        tk.Label(bar, textvariable=st, bg=P.CARD, fg=P.MUTED, font=(FONT, 9)).pack(side="left", padx=px(12))
        t.insert("1.0", txt)
        t.edit_reset()
        t.bind("<Control-s>", lambda e: (save(), "break")[1])

    # ---- tables (Excel / CSV)
    def table_view(self, body, rows_fn, header_default, note_extra=""):
        holder = tk.Frame(body, bg=P.CARD)
        holder.pack(fill="both", expand=True)
        tv = ttk.Treeview(holder, show="headings", selectmode="extended")
        vs = ttk.Scrollbar(holder, command=tv.yview)
        hs = ttk.Scrollbar(holder, orient="horizontal", command=tv.xview)
        tv.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        hs.pack(side="bottom", fill="x")
        vs.pack(side="right", fill="y")
        tv.pack(fill="both", expand=True)
        tv.tag_configure("odd", background=P.TILE)

        def copy_rows(_e=None):
            sel = tv.selection() or tv.get_children()
            text = "\n".join("\t".join(str(x) for x in tv.item(i, "values")[1:]) for i in sel)
            self.clipboard_clear()
            self.clipboard_append(text)
            self.toast(f"Copied {len(sel)} row(s).")
            return "break"
        tv.bind("<Control-c>", copy_rows)
        tv.bind("<Control-a>", lambda e: (tv.selection_set(tv.get_children()), "break")[1])
        return tv, copy_rows

    def v_xlsx(self, body, d, p):
        sheets, shared = core.xlsx_meta(p)
        if not sheets:
            raise ValueError("no sheets found")
        bar = self.vbar(body, p, d, exact=True)
        sv, hv = tk.StringVar(value=sheets[0][0]), tk.BooleanVar(value=False)
        tk.Label(bar, text="Sheet", bg=P.CARD, fg=P.MUTED, font=(FONT, 9)).pack(side="left")
        cb = W.ttk_combo(bar, sv, [s[0] for s in sheets], 22)
        cb.pack(side="left", padx=px(8))
        tk.Checkbutton(bar, text="First row = headings", variable=hv, bg=P.CARD, activebackground=P.CARD, fg=P.INK, selectcolor=P.FIELD, bd=0, highlightthickness=0, font=(FONT, 9),
                       command=lambda: show()).pack(side="left", padx=px(8))
        note = tk.Label(bar, text="", bg=P.CARD, fg=P.MUTED, font=(FONT, 9))
        note.pack(side="left", padx=px(8))
        tv, copy_rows = self.table_view(body, None, False)
        RButton(bar, "Copy rows", copy_rows, "soft").pack(side="left", padx=px(6))

        def show(*_):
            rows = core.xlsx_rows(p, dict(sheets)[sv.get()], shared)
            n = fill_table(tv, rows, hv.get())
            note.configure(text=f"{n} rows" + ("  (first 3000 shown)" if n >= 3000 else "") + "   |   Ctrl+C copies the selected rows")
        cb.bind("<<ComboboxSelected>>", show)
        show()

    def v_csv(self, body, d, p):
        rows = core.read_csv_rows(p)
        bar = self.vbar(body, p)
        hv = tk.BooleanVar(value=True)
        RButton(bar, "Edit as text", lambda: (self.clear_body(body), self.v_text(body, d, p)), "soft").pack(side="left")
        tk.Checkbutton(bar, text="First row = headings", variable=hv, bg=P.CARD, activebackground=P.CARD, fg=P.INK, selectcolor=P.FIELD, bd=0, highlightthickness=0, font=(FONT, 9),
                       command=lambda: show()).pack(side="left", padx=px(12))
        note = tk.Label(bar, text="", bg=P.CARD, fg=P.MUTED, font=(FONT, 9))
        note.pack(side="left", padx=px(8))
        tv, copy_rows = self.table_view(body, None, True)
        RButton(bar, "Copy rows", copy_rows, "soft").pack(side="left", padx=px(6))

        def show():
            n = fill_table(tv, rows, hv.get())
            note.configure(text=f"{n} rows   |   Ctrl+C copies the selected rows")
        show()

    def clear_body(self, body):
        for w in body.winfo_children():
            w.destroy()

    # ---- Word / PowerPoint (built-in, fast)
    def v_docx(self, body, d, p):
        blocks = core.read_docx(p)
        self.vbar(body, p, d, exact=True)
        t = self.text_box(body)
        t.configure(padx=px(70), pady=px(24))
        for nm, f in (("h1", (FONT, 22, "bold")), ("h2", (FONT, 16, "bold")), ("h3", (FONT, 13, "bold")), ("b", (FONT, 11, "bold")), ("i", (FONT, 11, "italic")),
                      ("tbl", ("Consolas" if os.name == "nt" else "DejaVu Sans Mono", 10))):
            t.tag_configure(nm, font=f)
        t.tag_configure("tbl", background=P.TILE, lmargin1=px(10), lmargin2=px(10))
        for b in blocks:
            if b[0] == "p":
                _, style, bullet, runs = b
                s = style.lower().replace(" ", "")
                head = "h1" if s.startswith(("title", "heading1")) else "h2" if s.startswith("heading2") else "h3" if s.startswith(("heading3", "heading4")) else None
                if bullet:
                    t.insert("end", "  \u2022  ")
                for text, bold, ital in runs:
                    t.insert("end", text, (head,) if head else tuple(x for x in ("b" if bold else None, "i" if ital else None) if x))
                t.insert("end", "\n")
            else:
                for row in b[1]:
                    t.insert("end", "  " + "   |   ".join(c.strip() for c in row) + "\n", "tbl")
                t.insert("end", "\n")
        if not blocks:
            t.insert("end", "This document has no text to show.")
        t.bind("<Key>", lambda e: "break" if not (e.state & 4) else None)      # read-only, but selecting and Ctrl+C still work

    def v_pptx(self, body, d, p):
        slides = core.read_pptx(p)
        bar = self.vbar(body, p, d, exact=True)
        tk.Label(bar, text="Text view of the slides.  Press  Exact view (PDF)  for the real slides.", bg=P.CARD, fg=P.MUTED, font=(FONT, 9)).pack(side="left")
        t = self.text_box(body)
        t.tag_configure("sl", background=P.PILL, foreground=P.MUTED, font=(FONT, 10, "bold"), spacing1=px(14), spacing3=px(8))
        t.tag_configure("ti", font=(FONT, 17, "bold"), spacing3=px(8))
        for i, items in enumerate(slides, 1):
            t.insert("end", f"  Slide {i}\n", "sl")
            for title, text in items:
                t.insert("end", text + "\n" if title else "  \u2022  " + text + "\n", "ti" if title else ())
            if not items:
                t.insert("end", "(no text on this slide)\n")
            t.insert("end", "\n")
        if not slides:
            t.insert("end", "No slides found in this file.")
        t.bind("<Key>", lambda e: "break" if not (e.state & 4) else None)

    # ---- PDF
    def v_pdf(self, body, d, p):
        if fitz is None:
            return self.v_need_fitz(body, d, p)
        self.vbar(body, p)
        PdfView(self, body, p).pack(fill="both", expand=True)

    def v_office(self, body, d, p):
        """Show an Office file exactly as in Word / Excel / PowerPoint (made into a PDF by Microsoft Office)."""
        self.vbar(body, p)
        wrap = tk.Frame(body, bg=P.CARD)
        wrap.pack(fill="both", expand=True)
        if fitz is None:
            return self.v_need_fitz(wrap, d, p)
        msg = tk.Label(wrap, text="Preparing the exact view with Microsoft Office...\nThis takes a few seconds the first time.", bg=P.CARD, fg=P.MUTED, font=(FONT, 11), justify="center")
        msg.pack(expand=True)
        cache = core.ROOT / "cache"
        cache.mkdir(exist_ok=True)
        out = cache / f"{d['id']}_{p.stat().st_mtime_ns}.pdf"
        res = {}

        def work():
            try:
                if not out.exists():
                    core.office_to_pdf(p, out)
            except Exception as e:
                res["err"] = str(e)
        th = threading.Thread(target=work, daemon=True)
        th.start()

        def poll():
            try:
                if not wrap.winfo_exists():
                    return
                if th.is_alive():
                    return wrap.after(300, poll)
                msg.destroy()
                if "err" in res:
                    tk.Label(wrap, text=res["err"] + "\n\nOpen it in its own program instead.", bg=P.CARD, fg=P.MUTED, font=(FONT, 10), justify="center", wraplength=px(520)).pack(pady=(px(40), px(10)))
                    RButton(wrap, "Open in program", lambda: open_path(p), "main", big=True).pack()
                else:
                    PdfView(self, wrap, out).pack(fill="both", expand=True)
            except tk.TclError:
                pass
        wrap.after(300, poll)

    def v_need_fitz(self, body, d, p):
        wrap = tk.Frame(body, bg=P.CARD)
        wrap.pack(expand=True)
        tk.Label(wrap, text="PDF viewer add-on needed", bg=P.CARD, fg=P.TITLE, font=(FONT, 16, "bold")).pack(pady=(px(40), px(6)))
        tk.Label(wrap, text="To read PDF files inside TDMS, install the free PDF engine (PyMuPDF).\nIt is a one-time download of about 20 MB and needs internet once.", bg=P.CARD, fg=P.MUTED, font=(FONT, 10), justify="center").pack(pady=px(8))
        st = tk.StringVar()

        def inst():
            global fitz
            st.set("Installing, please wait...")
            self.config(cursor="watch")
            self.update()
            ok, text = core.pip_install("pymupdf")
            self.config(cursor="")
            if ok:
                importlib.invalidate_caches()
                try:
                    fitz = importlib.import_module("fitz")
                except Exception:
                    fitz = None
            if fitz:
                self.close_page(f"doc:{d['id']}")
                self.open_doc(d)
            else:
                st.set("Install failed. " + text[-200:])
        RButton(wrap, "Install PDF viewer now", inst, "main", big=True).pack(pady=px(8))
        tk.Label(wrap, textvariable=st, bg=P.CARD, fg=P.MUTED, font=(FONT, 9), wraplength=px(520)).pack()
        RButton(wrap, "Open in PDF reader instead", lambda: open_path(p), "soft").pack(pady=(px(14), 0))

    # ---- pictures with zoom
    def v_image(self, body, d, p):
        from PIL import Image
        bar = self.vbar(body, p)
        im0 = Image.open(p)
        im0.load()
        im0 = im0.convert("RGBA")
        st = {"z": 1.0, "fit": True}
        zl = tk.StringVar()
        cv = tk.Canvas(body, bg="#DCE2E8" if P.theme == "light" else "#0B111B", highlightthickness=0)
        vs = ttk.Scrollbar(body, command=cv.yview)
        hs = ttk.Scrollbar(body, orient="horizontal", command=cv.xview)
        cv.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        hs.pack(side="bottom", fill="x")
        vs.pack(side="right", fill="y")
        cv.pack(fill="both", expand=True)

        def render():
            cw, ch = max(100, cv.winfo_width()), max(100, cv.winfo_height())
            if st["fit"]:
                st["z"] = min(cw / im0.width, ch / im0.height, 1.0)
            z = max(.05, min(st["z"], 8.0))
            w, h = max(1, int(im0.width * z)), max(1, int(im0.height * z))
            if w * h > 60_000_000:
                return
            im = im0.resize((w, h), Image.LANCZOS if z < 1 else Image.BICUBIC)
            ph = W.photo_of(im)
            cv.delete("all")
            x, y = max(0, (cw - w) // 2), max(0, (ch - h) // 2)
            cv.create_image(x, y, anchor="nw", image=ph)
            cv.image = ph
            cv.configure(scrollregion=(0, 0, max(w, cw), max(h, ch)))
            zl.set(f"{int(z * 100)}%     {im0.width} x {im0.height} px")

        def zoom(f):
            st["fit"] = False
            st["z"] = max(.05, min(8.0, st["z"] * f))
            render()

        def fit():
            st["fit"] = True
            render()

        def one():
            st["fit"], st["z"] = False, 1.0
            render()
        RButton(bar, "Fit", fit, "soft").pack(side="left", padx=(0, px(6)))
        RButton(bar, "\u2212", lambda: zoom(1 / 1.25), "soft", width=px(40)).pack(side="left")
        RButton(bar, "+", lambda: zoom(1.25), "soft", width=px(40)).pack(side="left", padx=px(6))
        RButton(bar, "100%", one, "soft").pack(side="left")
        tk.Label(bar, textvariable=zl, bg=P.CARD, fg=P.MUTED, font=(FONT, 9)).pack(side="left", padx=px(12))
        zs = {"f": 1.0, "j": None}

        def zwheel(e):
            zs["f"] *= 1.1 ** (e.delta / 120)
            if not zs["j"]:
                def go():
                    f, zs["f"], zs["j"] = zs["f"], 1.0, None
                    if abs(f - 1) > 0.004:
                        zoom(f)
                zs["j"] = cv.after(70, go)
            return "break"

        def swheel(e):
            if e.state & 4:
                return zwheel(e)
            bb = cv.bbox("all")
            cv.yview_moveto(max(0.0, (cv.canvasy(0) - e.delta * 0.9) / max(1, (bb[3] - bb[1]) if bb else 1)))
            return "break"
        cv.bind("<Control-MouseWheel>", zwheel)
        cv.bind("<MouseWheel>", swheel)
        cv.bind("<ButtonPress-1>", lambda e: cv.scan_mark(e.x, e.y))
        cv.bind("<B1-Motion>", lambda e: cv.scan_dragto(e.x, e.y, gain=1))
        cv.bind("<Double-Button-1>", lambda e: fit() if not st["fit"] else one())
        cv.bind("<Configure>", lambda e: render() if st["fit"] else None)
        body.after(120, render)

    # ---- web links
    def v_link(self, body, d, p):
        ext = p.suffix.lower()
        url = core.read_url(p) if ext in core.LINK_EXT else p.resolve().as_uri()
        self.vbar(body, p)
        wrap = tk.Frame(body, bg=P.CARD)
        wrap.pack(expand=True)
        self._refs["big"] = self.ficon("link", 64)
        tk.Label(wrap, image=self._refs["big"], bg=P.CARD).pack(pady=(px(40), px(10)))
        tk.Label(wrap, text=d["title"], bg=P.CARD, fg=P.TITLE, font=(FONT, 16, "bold")).pack()
        tk.Label(wrap, text=url or "No address found in this file.", bg=P.CARD, fg=P.BLUE, font=(FONT, 11), wraplength=px(640)).pack(pady=px(10))
        if url:
            RButton(wrap, "Open in browser", lambda: webbrowser.open(url), "main", big=True).pack(pady=px(6))
            RButton(wrap, "Copy link", lambda: (self.clipboard_clear(), self.clipboard_append(url), self.toast("Link copied.")), "soft").pack(pady=px(4))
            if self.prefs.get("link_auto", "1") == "1":
                webbrowser.open(url)

    # ---- video and audio (Windows media engine, no add-on)
    def v_media(self, body, d, p, audio=False):
        if os.name != "nt":
            raise RuntimeError("Playing audio and video needs Windows.")
        self.vbar(body, p)
        stage = tk.Frame(body, bg=P.CARD if audio else "#000000")
        stage.pack(fill="both", expand=True)
        if audio:
            self._refs["big"] = self.ficon("aud", 64)
            tk.Label(stage, image=self._refs["big"], bg=P.CARD).pack(expand=True)
        ctl = tk.Frame(body, bg=P.CARD)
        ctl.pack(fill="x", pady=(px(8), 0))
        stage.update_idletasks()
        alias = f"tdms{d['id']}x{int(time.time()) % 100000}"
        mci(f"close {alias}")
        hw = stage.winfo_id()
        if audio:
            err, _ = mci(f'open "{p}" type mpegvideo alias {alias}')
            if err:
                err, _ = mci(f'open "{p}" alias {alias}')
        else:
            err, _ = mci(f'open "{p}" type mpegvideo alias {alias} parent {hw} style child')
            if err:
                err, _ = mci(f'open "{p}" alias {alias} parent {hw} style child')
        if err:
            raise RuntimeError(mci_error(err))
        mci(f"set {alias} time format milliseconds")
        _, ln = mci(f"status {alias} length")
        total = max(1, int(ln or 1))
        src = (640, 360)
        if not audio:
            _, wh = mci(f"where {alias} source")
            try:
                a = [int(x) for x in wh.split()]
                src = (max(1, a[2]), max(1, a[3]))
            except Exception:
                pass
        state = {"drag": False, "closed": False}
        pos, tl, vol = tk.DoubleVar(value=0), tk.StringVar(value="0:00"), tk.IntVar(value=80)
        btn = RButton(ctl, "Pause", None, "main", width=px(84))
        btn.pack(side="left")

        def fit(_e=None):
            if audio or state["closed"]:
                return
            w, h = stage.winfo_width(), stage.winfo_height()
            s = min(w / src[0], h / src[1])
            w2, h2 = max(1, int(src[0] * s)), max(1, int(src[1] * s))
            mci(f"put {alias} window at {(w - w2) // 2} {(h - h2) // 2} {w2} {h2}")

        def mode():
            return mci(f"status {alias} mode")[1]

        def toggle():
            m = mode()
            if m == "playing":
                mci(f"pause {alias}")
                btn.set_text("Play")
            else:
                if m == "stopped":
                    mci(f"seek {alias} to start")
                    mci(f"play {alias}")
                else:
                    mci(f"resume {alias}") if m == "paused" else mci(f"play {alias}")
                btn.set_text("Pause")

        def stop():
            mci(f"stop {alias}")
            mci(f"seek {alias} to start")
            btn.set_text("Play")
            pos.set(0)
        btn.command = toggle
        RButton(ctl, "Stop", stop, "soft", width=px(70)).pack(side="left", padx=px(6))
        sc = tk.Scale(ctl, from_=0, to=1000, orient="horizontal", variable=pos, showvalue=False, bd=0, highlightthickness=0, troughcolor=P.PILL, bg=P.CARD, length=px(520), sliderlength=px(16))
        sc.pack(side="left", padx=px(10), fill="x", expand=True)
        tk.Label(ctl, textvariable=tl, bg=P.CARD, fg=P.MUTED, font=(FONT, 9), width=12).pack(side="left")
        tk.Label(ctl, text="Volume", bg=P.CARD, fg=P.MUTED, font=(FONT, 9)).pack(side="left", padx=(px(10), px(4)))
        vs = tk.Scale(ctl, from_=0, to=100, orient="horizontal", variable=vol, showvalue=False, bd=0, highlightthickness=0, troughcolor=P.PILL, bg=P.CARD, length=px(100), sliderlength=px(14),
                      command=lambda v: mci(f"setaudio {alias} volume to {int(float(v)) * 10}"))
        vs.pack(side="left")
        sc.bind("<ButtonPress-1>", lambda e: state.update(drag=True))

        def seek(_e=None):
            state["drag"] = False
            mci(f"seek {alias} to {int(pos.get() / 1000 * total)}")
            if btn.text == "Pause":
                mci(f"play {alias}")
        sc.bind("<ButtonRelease-1>", seek)

        def fmt(ms):
            s = int(ms / 1000)
            return f"{s // 60}:{s % 60:02d}"

        def tick():
            if state["closed"]:
                return
            try:
                if not state["drag"]:
                    _, ps = mci(f"status {alias} position")
                    cur = int(ps or 0)
                    pos.set(cur / total * 1000)
                    tl.set(f"{fmt(cur)} / {fmt(total)}")
                    if mode() == "stopped" and btn.text == "Pause":
                        btn.set_text("Play")
                stage.after(400, tick)
            except tk.TclError:
                pass

        def on_destroy(e):
            if e.widget is stage:
                state["closed"] = True
                mci(f"close {alias}")
        stage.bind("<Destroy>", on_destroy)
        stage.bind("<Configure>", fit)
        mci(f"setaudio {alias} volume to 800")
        fit()
        mci(f"play {alias}")
        tick()

    # ---- everything else
    def v_other(self, body, p, key, label, note=""):
        wrap = tk.Frame(body, bg=P.CARD)
        wrap.pack(expand=True)
        self._refs["big"] = self.ficon(key, 64)
        tk.Label(wrap, image=self._refs["big"], bg=P.CARD).pack(pady=(px(40), px(8)))
        tk.Label(wrap, text=p.name, bg=P.CARD, fg=P.TITLE, font=(FONT, 15, "bold")).pack()
        tk.Label(wrap, text=f"{label}   |   {core.size(p.stat().st_size)}", bg=P.CARD, fg=P.MUTED, font=(FONT, 10)).pack()
        tk.Label(wrap, text=(note + "\n\n" if note else "") + "This file type cannot be shown inside TDMS.\nOpen it in its own program. Changes you save there go into the TDMS data folder.",
                 bg=P.CARD, fg=P.MUTED, font=(FONT, 10), justify="center", wraplength=px(520)).pack(pady=px(14))
        RButton(wrap, "Open in program", lambda: open_path(p), "main", big=True).pack(pady=px(6))
        RButton(wrap, "Show in folder", lambda: subprocess.Popen(["explorer", "/select,", str(p)]) if os.name == "nt" else open_path(p.parent), "soft").pack(pady=px(4))
        if self.prefs.get("auto_open2", "0") == "1":
            open_path(p)
