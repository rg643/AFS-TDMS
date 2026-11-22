"""
TDMS widgets  -  the look of the application (light / dark theme, rounded
buttons, soft-shadow cards, fields, tabs, toast messages, dialogs).
"""
import os
import tkinter as tk
from tkinter import font as tkfont

from PIL import ImageTk

import tdms_graphics as g

VERSION = "7.1"
FONT = "Segoe UI" if os.name == "nt" else "DejaVu Sans"
SCALE = 1.0


def set_scale(v):
    global SCALE
    SCALE = v


def px(n):
    return max(1, int(round(n * SCALE)))


class Palette:
    pass


P = Palette()


def set_palette(theme="light", red="#E8312F", blue="#2E6DB4", navy="#1F3A5F", accent=""):
    """Fills P with every colour the app uses.  Call again (and rebuild) to change theme."""
    P.theme = theme
    P.RED, P.BLUE, P.NAVY, P.GREEN = red, blue, navy, "#2E8B57"
    P.ACCENT = accent or red
    P.ERR = "#C62828"
    if theme == "dark":
        P.BG, P.CARD, P.LINE = "#0E1624", "#182234", "#2A374D"
        P.INK, P.MUTED, P.PILL = "#E6ECF5", "#93A1B5", "#233047"
        P.FIELD, P.HEAD, P.TITLE = "#101A2B", "#131D2E", "#9CC2F5"
        P.PRIMARY, P.SOFT, P.SOFT_OVER = "#2F5D9A", "#243249", "#2E4060"
        P.TILE, P.DUE_BG, P.DUE_FG = "#1D2A40", "#3A2C14", "#F5B15A"
        P.TINT = {"WO": "#1D3556", "CO": "#1B3A2B", "LEAVE": "#4A2326"}
        P.CHIP = {"work": ("#17342A", "#6FD39B"), "WO": ("#1D3556", "#8DBCF2"),
                  "CO": ("#1B3A2B", "#7FD39A"), "LEAVE": ("#4A2326", "#F29B9B"),
                  "due": ("#3A2C14", "#F5B15A"), "empty": ("#182234", "#6E7C92")}
        P.SEL = "#2F4C7A"
        P.HOVER = "#22344F"
        P.CHART_TRACK, P.CHART_GRID = "#26344B", "#26344B"
    else:
        P.BG, P.CARD, P.LINE = "#EEF2F7", "#FFFFFF", "#DDE3EA"
        P.INK, P.MUTED, P.PILL = "#1E2A38", "#6B7785", "#EDF0F5"
        P.FIELD, P.HEAD, P.TITLE = "#FFFFFF", "#FFFFFF", navy
        P.PRIMARY, P.SOFT, P.SOFT_OVER = navy, "#E8ECF1", "#D6DDE6"
        P.TILE, P.DUE_BG, P.DUE_FG = "#F6F8FB", "#FFF1DC", "#B45F06"
        P.TINT = {"WO": "#DCEAFB", "CO": "#DDF1E3", "LEAVE": "#FCE0E0"}
        P.CHIP = {"work": ("#E3F4EA", "#1E7B49"), "WO": ("#DCEAFB", blue),
                  "CO": ("#DDF1E3", "#2E8B57"), "LEAVE": ("#FCE0E0", "#C62828"),
                  "due": ("#FFF1DC", "#B45F06"), "empty": ("#FFFFFF", "#9AA5B4")}
        P.SEL = "#CFE0F5"
        P.HOVER = "#E9F1FB"
        P.CHART_TRACK, P.CHART_GRID = "#E3E8EF", "#E3E8EF"


set_palette()


def bg_of(widget, default=None):
    try:
        return widget.cget("bg")
    except Exception:
        return default or P.CARD


def hover(widget, normal, over):
    widget.bind("<Enter>", lambda e: widget.configure(bg=over))
    widget.bind("<Leave>", lambda e: widget.configure(bg=normal))


_photo_cache = {}


def photo_of(img, key=None):
    """PIL -> PhotoImage, cached by key so Tk does not lose the picture."""
    if key is not None and key in _photo_cache:
        return _photo_cache[key]
    ph = ImageTk.PhotoImage(img)
    if key is not None:
        if len(_photo_cache) > 4000:
            _photo_cache.clear()
        _photo_cache[key] = ph
    return ph


def cached_photo(key, make):
    """Picture from the cache; make() (which draws it with Pillow) runs only the first time."""
    ph = _photo_cache.get(key)
    return ph if ph is not None else photo_of(make(), key)


# ================================================================ rounded button
class RButton(tk.Canvas):
    """Smooth rounded button.  kind: main | navy | soft | ghost | danger | success"""

    def __init__(self, parent, text, command=None, kind="soft", big=False, width=None):
        self.kind, self.command, self.text = kind, command, text
        self._bgc = bg_of(parent, P.CARD)
        weight = "bold" if kind in ("main", "navy", "danger", "success") else "normal"
        self._font = tkfont.Font(family=FONT, size=10 if big else 9, weight=weight)
        h = px(40 if big else 32)
        w = width or (self._font.measure(text) + px(38 if big else 28))
        super().__init__(parent, width=w, height=h, bg=self._bgc, highlightthickness=0, bd=0,
                         cursor="hand2")
        self._over, self._down, self._enabled = False, False, True
        self._ref = None
        self._bw, self._bh = int(w), int(h)
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", lambda e: self._set(over=True))
        self.bind("<Leave>", lambda e: self._set(over=False, down=False))
        self.bind("<ButtonPress-1>", lambda e: self._set(down=True))
        self.bind("<ButtonRelease-1>", self._release)
        self._draw()

    def _set(self, over=None, down=None):
        if over is not None:
            self._over = over
        if down is not None:
            self._down = down
        self._draw()

    def _release(self, _e):
        was = self._down
        self._set(down=False)
        if was and self._enabled and self.command:
            self.after(10, self.command)

    def _colors(self):
        k = self.kind
        base = {"main": (P.ACCENT, "#FFFFFF"), "navy": (P.PRIMARY, "#FFFFFF"),
                "soft": (P.SOFT, P.INK), "ghost": (P.CARD, P.TITLE),
                "danger": (P.ERR, "#FFFFFF"), "success": (P.GREEN, "#FFFFFF")}[k]
        fill, fg = base
        if not self._enabled:
            return g.mix(fill, self._bgc, 0.6), g.mix(fg, self._bgc, 0.5)
        if self._down:
            fill = g.mix(fill, "#000000", 0.22)
        elif self._over:
            if k == "soft":
                fill = P.SOFT_OVER
            elif k == "ghost":
                fill = P.SOFT
            else:
                fill = g.mix(fill, "#000000", 0.14)
        return fill, fg

    def _draw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 8 or h < 8:
            w, h = self._bw, self._bh
        fill, fg = self._colors()
        sig = (w, h, fill, fg, self.text)
        if sig == getattr(self, "_sig", None):
            return
        self._sig = sig
        r = max(px(8), h // 2 - px(3)) if h < px(36) else px(10)
        img = g.rounded_box(w, h, r, fill, canvas_bg=self._bgc)
        self._ref = photo_of(img, ("btn", w, h, r, fill, self._bgc))
        if getattr(self, "_items", None):          # update in place - no delete/redraw flash
            self.itemconfigure(self._items[0], image=self._ref)
            self.itemconfigure(self._items[1], text=self.text, fill=fg, font=self._font)
            self.coords(self._items[1], w / 2, h / 2)
        else:
            self._items = (self.create_image(0, 0, image=self._ref, anchor="nw"),
                           self.create_text(w / 2, h / 2, text=self.text, fill=fg, font=self._font))

    def set_text(self, text):
        self.text = text
        self._draw()

    def set_enabled(self, flag):
        self._enabled = flag
        self.configure(cursor="hand2" if flag else "arrow")
        self._draw()


# ======================================================================== card
class Card(tk.Frame):
    """White panel with a thin border.  Put widgets into  card.body .
    A plain Frame: Tk sizes it to its content by itself (no canvas tricks)."""

    def __init__(self, parent, expand=False, radius=14, bg=None, autow=False):
        super().__init__(parent, bg=P.LINE)
        self.expand = expand
        self.body = tk.Frame(self, bg=P.CARD, padx=px(16), pady=px(14))
        self.body.pack(fill="both", expand=True, padx=1, pady=1)

    def set_width(self, w):
        """Fixed width (height still follows the layout)."""
        self.configure(width=w)
        self.pack_propagate(False)

    def fit(self, update=True):          # kept for old callers - nothing to do now
        pass


# ======================================================================= fields
class Field(tk.Frame):
    """Label + flat text box with a focus line (optionally a password box)."""

    def __init__(self, parent, label, secret=False, width=32, bg=None, value="", hint=""):
        bg = bg or P.CARD
        super().__init__(parent, bg=bg)
        self._bg = bg
        tk.Label(self, text=label, bg=bg, fg=P.MUTED, font=(FONT, 8, "bold"), anchor="w").pack(fill="x")
        self.box = tk.Frame(self, bg=P.LINE)
        self.box.pack(fill="x", pady=(px(3), 0))
        inner = tk.Frame(self.box, bg=P.FIELD)
        inner.pack(fill="x", padx=1, pady=1)
        self.var = tk.StringVar(value=value)
        self.entry = tk.Entry(inner, textvariable=self.var, relief="flat", bd=0, width=width,
                              highlightthickness=0, font=(FONT, 11), bg=P.FIELD, fg=P.INK,
                              insertbackground=P.INK, show="•" if secret else "")
        self.entry.pack(side="left", fill="x", expand=True, ipady=px(6), padx=(px(8), 0))
        self.secret = secret
        if secret:
            self.eye = tk.Label(inner, text="Show", bg=P.FIELD, fg=P.BLUE, cursor="hand2",
                                font=(FONT, 9, "bold"), padx=px(10))
            self.eye.pack(side="right")
            self.eye.bind("<Button-1>", self._toggle)
        self.entry.bind("<FocusIn>", lambda e: self.box.configure(bg=P.BLUE))
        self.entry.bind("<FocusOut>", lambda e: self.box.configure(bg=P.LINE))
        if hint:
            tk.Label(self, text=hint, bg=bg, fg=P.MUTED, font=(FONT, 8), anchor="w").pack(fill="x")

    def _toggle(self, _e=None):
        hidden = self.entry.cget("show") != ""
        self.entry.configure(show="" if hidden else "•")
        self.eye.configure(text="Hide" if hidden else "Show")

    def get(self):
        return self.var.get().strip()

    def raw(self):
        return self.var.get()

    def set(self, v):
        self.var.set(v)

    def lock(self):
        self.entry.configure(state="disabled", disabledbackground=P.PILL, disabledforeground=P.MUTED)


class StrengthBar(tk.Canvas):
    COLORS = ["#C62828", "#E67E22", "#E6B800", "#2E8B57"]
    NAMES = ["Too short", "Weak", "Okay", "Good", "Strong"]

    def __init__(self, parent, bg=None):
        super().__init__(parent, height=px(18), bg=bg or P.CARD, highlightthickness=0)
        self.level = 0
        self.bind("<Configure>", lambda e: self.show(self.level))

    def show(self, level):
        self.level = level
        self.delete("all")
        w = max(self.winfo_width(), 50)
        seg = (w - px(60)) / 4
        for i in range(4):
            x = i * (seg + px(4))
            on = level > i
            self.create_rectangle(x, px(4), x + seg, px(9),
                                  fill=self.COLORS[min(level - 1, 3)] if on else P.LINE, width=0)
        self.create_text(w - px(2), px(7), anchor="e", fill=P.MUTED, font=(FONT, 8),
                         text=self.NAMES[level] if level else "")


# ===================================================================== choices
class PillGroup(tk.Frame):
    """A row of choice buttons (one selected).  items = [(value, text, colour)]"""

    def __init__(self, parent, items, command=None, bg=None):
        super().__init__(parent, bg=bg or P.CARD)
        self.items, self.command = list(items), command
        self.value, self.enabled, self.labels = None, True, {}
        self._build()

    def _build(self):
        for w in self.winfo_children():
            w.destroy()
        self.labels = {}
        for i, (val, text, _c) in enumerate(self.items):
            lb = tk.Label(self, text=text, padx=px(8), pady=px(5), cursor="hand2",
                          font=(FONT, 9, "bold"))
            lb.grid(row=0, column=i, padx=(0 if i == 0 else px(4), 0), sticky="ew")
            self.columnconfigure(i, weight=1)
            lb.bind("<Button-1>", lambda e, v=val: self.choose(v))
            self.labels[val] = lb
        self._paint()

    def set_items(self, items):
        self.items = list(items)
        self._build()

    def choose(self, val):
        if not self.enabled:
            return
        self.value = val
        self._paint()
        if self.command:
            self.command(val)

    def set(self, val):
        self.value = val
        self._paint()

    def get(self):
        return self.value or ""

    def enable(self, flag):
        self.enabled = flag
        self._paint()
        for lb in self.labels.values():
            lb.configure(cursor="hand2" if flag else "arrow")

    def _paint(self):
        for val, _t, color in self.items:
            lb = self.labels.get(val)
            if lb is None:
                continue
            if not self.enabled:
                lb.configure(bg=P.PILL, fg=g.mix(P.MUTED, P.PILL, 0.5))
            elif val == self.value:
                lb.configure(bg=color, fg="white")
            else:
                lb.configure(bg=P.PILL, fg=P.INK)


class NavBar(tk.Frame):
    """Header tabs with a coloured underline on the active one."""

    def __init__(self, parent, items, command, bg=None):
        bg = bg or P.HEAD
        super().__init__(parent, bg=bg)
        self.cmd, self.items, self.parts, self.active = command, items, {}, None
        for key, text in items:
            cell = tk.Frame(self, bg=bg, cursor="hand2")
            cell.pack(side="left", padx=(0, px(4)))
            lb = tk.Label(cell, text=text, bg=bg, fg=P.MUTED, font=(FONT, 10, "bold"),
                          padx=px(14), pady=px(8), cursor="hand2")
            lb.pack()
            bar = tk.Frame(cell, bg=bg, height=px(3))
            bar.pack(fill="x")
            for w in (cell, lb):
                w.bind("<Button-1>", lambda e, k=key: self.select(k, True))
            lb.bind("<Enter>", lambda e, k=key: self._hov(k, True))
            lb.bind("<Leave>", lambda e, k=key: self._hov(k, False))
            self.parts[key] = (lb, bar)
        self._bg = bg

    def _hov(self, k, on):
        if k != self.active:
            self.parts[k][0].configure(fg=P.INK if on else P.MUTED)

    def select(self, key, fire=False):
        self.active = key
        for k, (lb, bar) in self.parts.items():
            on = k == key
            lb.configure(fg=P.TITLE if on else P.MUTED)
            bar.configure(bg=P.ACCENT if on else self._bg)
        if fire:
            self.cmd(key)


# ====================================================================== helpers
def toast(root, text, kind="ok", ms=3200):
    """Small message that slides in at the bottom-right and disappears."""
    col = {"ok": P.GREEN, "warn": "#E6B800", "err": P.ERR, "info": P.BLUE}.get(kind, P.GREEN)
    old = getattr(root, "_toast", None)
    if old is not None:
        try:
            old.destroy()
        except Exception:
            pass
    f = tk.Frame(root, bg=col)
    inner = tk.Frame(f, bg=P.CARD)
    inner.pack(padx=(px(5), 0), fill="both")
    tk.Label(inner, text=text, bg=P.CARD, fg=P.INK, font=(FONT, 10), justify="left",
             wraplength=px(380), padx=px(14), pady=px(10)).pack()
    f.place(relx=1.0, rely=1.0, x=-px(20), y=-px(46), anchor="se")
    f.lift()
    root._toast = f
    root.after(ms, lambda: f.destroy() if f.winfo_exists() else None)


def center_on(win, parent):
    win.update_idletasks()
    try:
        x = parent.winfo_rootx() + (parent.winfo_width() - win.winfo_width()) // 2
        y = parent.winfo_rooty() + max(10, (parent.winfo_height() - win.winfo_height()) // 3)
        win.geometry(f"+{max(0, x)}+{max(0, y)}")
    except Exception:
        pass


class Dialog(tk.Toplevel):
    """Base for pop-up windows:  title, optional intro, .body frame, button row."""

    def __init__(self, parent, title, intro="", width=460):
        super().__init__(parent)
        self.withdraw()                       # stay hidden until built and centred (no flicker)
        self.title(title)
        self.configure(bg=P.CARD)
        self.resizable(False, False)
        self.transient(parent)
        self.parent = parent
        self.result = None
        tk.Frame(self, bg=P.ACCENT, height=px(4)).pack(fill="x")
        self.shell = tk.Frame(self, bg=P.CARD, padx=px(26), pady=px(18))
        self.shell.pack(fill="both", expand=True)
        tk.Label(self.shell, text=title, bg=P.CARD, fg=P.TITLE, font=(FONT, 14, "bold")).pack(anchor="w")
        if intro:
            tk.Label(self.shell, text=intro, bg=P.CARD, fg=P.MUTED, font=(FONT, 9), justify="left",
                     wraplength=px(width - 20)).pack(anchor="w", pady=(px(4), px(2)))
        self.body = tk.Frame(self.shell, bg=P.CARD)
        self.body.pack(fill="both", expand=True)
        self.err = tk.Label(self.shell, text="", bg=P.CARD, fg=P.ERR, font=(FONT, 9), anchor="w",
                            justify="left", wraplength=px(width - 20))
        self.err.pack(fill="x", pady=(px(8), 0))
        self.bar = tk.Frame(self.shell, bg=P.CARD)
        self.bar.pack(fill="x", pady=(px(6), 0))
        self.bind("<Escape>", lambda e: self.destroy())

    def buttons(self, ok_text, ok_cmd, kind="main", cancel=True):
        RButton(self.bar, ok_text, ok_cmd, kind, big=True).pack(side="right")
        if cancel:
            RButton(self.bar, "Cancel", self.destroy, "soft", big=True).pack(side="right", padx=(0, px(8)))

    def show(self, focus=None):
        center_on(self, self.parent)
        self.deiconify()
        try:
            import tdms_native
            tdms_native.set_titlebar(self, P.NAVY, "#FFFFFF", True)
        except Exception:
            pass
        if focus is not None:
            focus.focus_set()
        try:
            self.wait_visibility()
            self.grab_set()
        except Exception:
            pass
        self.wait_window(self)
        return self.result

    def fail(self, msg):
        self.err.configure(text=msg)


def ask_yes_no(parent, title, text, yes="Yes", no="Cancel", kind="main"):
    d = Dialog(parent, title, text, width=420)
    d.result = False

    def go():
        d.result = True
        d.destroy()
    d.body.pack_forget()
    d.buttons(yes, go, kind)
    for w in d.bar.winfo_children():
        if isinstance(w, RButton) and w.text == "Cancel":
            w.set_text(no)
    return bool(d.show())


def section_label(parent, text, bg=None, fg=None):
    return tk.Label(parent, text=text, bg=bg or P.CARD, fg=fg or P.MUTED,
                    font=(FONT, 8, "bold"), anchor="w")


# ===================================================================== tabs (some closable)
class TabBar(tk.Frame):
    """Colour-filled rounded tabs with a soft shadow.  add(key, text, image, closable, color, image_on):
    the selected tab is solid colour with white text and a white icon; the others are a soft tint of their colour."""
    H = 36
    SH = 4

    def __init__(self, parent, on_select, on_close, bg=None):
        bg = bg or P.HEAD
        super().__init__(parent, bg=bg)
        self._bg, self.on_select, self.on_close = bg, on_select, on_close
        self.tabs, self.order, self.active, self.hover = {}, [], None, None
        self._font = tkfont.Font(family=FONT, size=10, weight="bold")
        self._refs = {}

    def add(self, key, text, image=None, closable=False, color=None, image_on=None):
        if key in self.tabs:
            return
        cv = tk.Canvas(self, bg=self._bg, highlightthickness=0, bd=0, cursor="hand2")
        cv.pack(side="left", padx=(0, px(2)), pady=(px(4), px(2)))
        self.tabs[key] = {"cv": cv, "text": text, "image": image, "image_on": image_on or image, "closable": closable, "color": color or P.ACCENT, "items": None}
        self.order.append(key)
        cv.bind("<Button-1>", lambda e, k=key: self._click(k, e))
        cv.bind("<Button-2>", lambda e, k=key: self.on_close(k) if self.tabs[k]["closable"] else None)
        cv.bind("<Enter>", lambda e, k=key: self._hover(k))
        cv.bind("<Leave>", lambda e, k=key: self._hover(None))
        self._layout(key)
        self._paint()

    def _layout(self, key):
        t = self.tabs[key]
        pad, gap, sh = px(14), px(8), px(self.SH)
        iw = t["image"].width() if t["image"] else 0
        tw = self._font.measure(t["text"])
        w = pad + (iw + gap if t["image"] else 0) + tw + (px(26) if t["closable"] else 0) + pad
        h = px(self.H)
        t["w"], t["h"], t["sh"], t["tx"] = w, h, sh, sh + pad + (iw + gap if t["image"] else 0)
        cv = t["cv"]
        cv.configure(width=w + 2 * sh, height=h + 2 * sh)
        cv.delete("all")
        bgi = cv.create_image(0, 0, anchor="nw")
        ico = cv.create_image(sh + pad, sh + h / 2, anchor="w") if t["image"] else None
        txt = cv.create_text(t["tx"], sh + h / 2, anchor="w", text=t["text"], font=self._font)
        x = cv.create_text(w + sh - px(13), sh + h / 2, text="\u2715", font=(FONT, 9)) if t["closable"] else None
        t["items"] = (bgi, ico, txt, x)

    def _paint(self):
        for k, t in self.tabs.items():
            on, hv = k == self.active, k == self.hover
            col = t["color"]
            fill = col if on else g.mix(col, self._bg, 0.70 if hv else 0.82)
            key = ("tab", t["w"], t["h"], fill, self._bg, t["sh"], on)
            self._refs[key] = cached_photo(key, lambda t=t, fill=fill, on=on: g.rounded_box(t["w"] + 2 * t["sh"], t["h"] + 2 * t["sh"], px(10), fill, shadow=t["sh"], shadow_alpha=70 if on else 38, shadow_dy=2, canvas_bg=self._bg))
            cv, (bgi, ico, txt, x) = t["cv"], t["items"]
            cv.itemconfigure(bgi, image=self._refs[key])
            cv.itemconfigure(txt, fill="#FFFFFF" if on else P.INK)
            if ico:
                cv.itemconfigure(ico, image=t["image_on"] if on else t["image"])
            if x:
                cv.itemconfigure(x, fill="#FFFFFF" if on else P.MUTED)

    def _hover(self, key):
        if key != self.hover:
            self.hover = key
            self._paint()

    def _click(self, key, e):
        t = self.tabs.get(key)
        if not t:
            return
        if t["closable"] and e.x > t["w"] + t["sh"] - px(26):
            return self.on_close(key)
        self.select(key, True)

    def select(self, key, fire=False):
        self.active = key
        self._paint()
        if fire and self.on_select:
            self.on_select(key)

    def rename(self, key, text):
        if key in self.tabs:
            self.tabs[key]["text"] = text
            self._layout(key)
            self._paint()

    def remove(self, key):
        t = self.tabs.pop(key, None)
        if t:
            t["cv"].destroy()
            self.order.remove(key)

    def clear(self):
        for k in list(self.tabs):
            self.remove(k)
        self.active = None


_SCROLL_PAGES = []


def _scroll_wheel(e):
    """ONE handler for every scrolling page (smooth with a touchpad)."""
    if e.state & 4:
        return
    for sf in list(_SCROLL_PAGES):
        try:
            if not sf.winfo_exists():
                _SCROLL_PAGES.remove(sf)
                continue
            w = sf.winfo_containing(e.x_root, e.y_root)
        except Exception:
            continue
        while w is not None and w is not sf:
            if w.winfo_class() in ("Treeview", "Text", "Listbox"):
                return
            w = getattr(w, "master", None)
        if w is sf and sf.inner.winfo_height() > sf.cv.winfo_height():
            bb = sf.cv.bbox("all")
            th = max(1, (bb[3] - bb[1]) if bb else 1)
            sf.cv.yview_moveto(max(0.0, (sf.cv.canvasy(0) - e.delta * 0.9) / th))
            return


class ScrollFrame(tk.Frame):
    """A page that scrolls up/down with the mouse wheel or a touchpad.  Put widgets into  .inner"""

    def __init__(self, parent, bg=None):
        bg = bg or P.BG
        super().__init__(parent, bg=bg)
        self.cv = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.vs = ttk_scrollbar(self, self.cv.yview)
        self.cv.configure(yscrollcommand=self.vs.set)
        self.vs.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.cv, bg=bg)
        self._win = self.cv.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        self.cv.bind("<Configure>", lambda e: self.cv.itemconfigure(self._win, width=e.width))
        if not _SCROLL_PAGES:
            self.bind_all("<MouseWheel>", _scroll_wheel, add="+")
        _SCROLL_PAGES.append(self)
        self.bind("<Destroy>", lambda e: _SCROLL_PAGES.remove(self) if (e.widget is self and self in _SCROLL_PAGES) else None)


def ttk_scrollbar(parent, command):
    from tkinter import ttk
    return ttk.Scrollbar(parent, command=command)


# ===================================================================== search box
class SearchBox(tk.Frame):
    """Small flat text box with a hint text and an Enter callback."""

    def __init__(self, parent, hint="Search...", command=None, width=26, bg=None):
        super().__init__(parent, bg=P.LINE)
        self.hint, self.command = hint, command
        inner = tk.Frame(self, bg=P.FIELD)
        inner.pack(fill="x", padx=1, pady=1)
        self.var = tk.StringVar()
        self.entry = tk.Entry(inner, textvariable=self.var, relief="flat", bd=0, width=width, highlightthickness=0, font=(FONT, 10),
                              bg=P.FIELD, fg=P.MUTED, insertbackground=P.INK)
        self.entry.pack(side="left", fill="x", expand=True, ipady=px(5), padx=(px(8), 0))
        self.clear_lb = tk.Label(inner, text="\u2715", bg=P.FIELD, fg=P.MUTED, cursor="hand2", font=(FONT, 9), padx=px(8))
        self.clear_lb.bind("<Button-1>", lambda e: self.clear(True))
        self._hinting = True
        self.var.set(hint)
        self.entry.bind("<FocusIn>", self._in)
        self.entry.bind("<FocusOut>", self._out)
        self.entry.bind("<Return>", lambda e: self.command and self.command(self.get()))
        self.var.trace_add("write", lambda *a: self._sync())

    def _in(self, _e=None):
        self.configure(bg=P.BLUE)
        if self._hinting:
            self._hinting = False
            self.var.set("")
            self.entry.configure(fg=P.INK)

    def _out(self, _e=None):
        self.configure(bg=P.LINE)
        if not self.var.get().strip():
            self._hinting = True
            self.var.set(self.hint)
            self.entry.configure(fg=P.MUTED)

    def _sync(self):
        if self._hinting or not self.var.get():
            self.clear_lb.pack_forget()
        else:
            self.clear_lb.pack(side="right")

    def get(self):
        return "" if self._hinting else self.var.get().strip()

    def set(self, text):
        self._hinting = False
        self.entry.configure(fg=P.INK)
        self.var.set(text)
        if not text:
            self._out()

    def clear(self, fire=False):
        self.set("")
        if fire and self.command:
            self.command("")

    def focus(self):
        self.entry.focus_set()


# ===================================================================== form dialog
class FormDialog(Dialog):
    """specs = [(key, label, kind, default, hint)] with kind text | secret | combo | check.
    validate(values) -> error text or None.  run() returns a dict of values or None."""

    def __init__(self, parent, title, specs, ok="Save", intro="", width=460, validate=None, kind="main"):
        super().__init__(parent, title, intro, width)
        self.validate, self.vars, self.first = validate, {}, None
        for key, label, k, default, hint in specs:
            if k in ("text", "secret"):
                f = Field(self.body, label, secret=(k == "secret"), width=36, value=default or "", hint=hint or "")
                f.pack(fill="x", pady=(px(8), 0))
                self.vars[key] = f
                self.first = self.first or f.entry
            elif k == "combo":
                values, dflt = default if isinstance(default, tuple) else (default, default[0])
                tk.Label(self.body, text=label, bg=P.CARD, fg=P.MUTED, font=(FONT, 8, "bold"), anchor="w").pack(fill="x", pady=(px(8), 0))
                var = tk.StringVar(value=dflt)
                ttk_combo(self.body, var, values).pack(fill="x", pady=(px(3), 0))
                self.vars[key] = var
            elif k == "check":
                var = tk.BooleanVar(value=bool(default))
                tk.Checkbutton(self.body, text=label, variable=var, bg=P.CARD, activebackground=P.CARD, fg=P.INK, selectcolor=P.FIELD, bd=0,
                               highlightthickness=0, font=(FONT, 10), cursor="hand2").pack(anchor="w", pady=(px(10), 0))
                self.vars[key] = var
        self.buttons(ok, self._ok, kind)
        self.bind("<Return>", lambda e: self._ok())

    def _ok(self):
        vals = {}
        for k, v in self.vars.items():
            vals[k] = (v.raw() if v.secret else v.get()) if isinstance(v, Field) else (v.get().strip() if isinstance(v.get(), str) else v.get())
        err = self.validate(vals) if self.validate else None
        if err:
            return self.fail(err)
        self.result = vals
        self.destroy()

    def run(self):
        return self.show(self.first)


def ttk_combo(parent, var, values, width=30):
    from tkinter import ttk
    return ttk.Combobox(parent, textvariable=var, values=list(values), state="readonly", width=width, font=(FONT, 10))
