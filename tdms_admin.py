"""
TDMS admin pages  -  Users, Activity log, and the Admin tab (Branding, Rules, Backup & add-ons).
Each page is a Frame that the main window shows in a tab.
"""
import csv
import datetime as dt
import os
import shutil
import sys
import tkinter as tk
import zipfile
from tkinter import colorchooser, filedialog, messagebox, ttk

import tdms_core as core
import tdms_graphics as g
import tdms_widgets as W
from tdms_widgets import P, px, FONT, RButton, Card, Field, PillGroup, SearchBox, FormDialog, ask_yes_no


def table(parent, cols, height=14, multi=False):
    """Styled list with a scrollbar.  cols = [(key, title, width)]  ->  (holder_frame, treeview)"""
    holder = tk.Frame(parent, bg=P.CARD)
    tv = ttk.Treeview(holder, columns=[c[0] for c in cols], show="headings", selectmode="extended" if multi else "browse", height=height)
    sb = ttk.Scrollbar(holder, command=tv.yview)
    tv.configure(yscrollcommand=sb.set)
    for k, t, w in cols:
        tv.heading(k, text=t, anchor="w")
        tv.column(k, width=px(w), anchor="w")
    sb.pack(side="right", fill="y")
    tv.pack(side="left", fill="both", expand=True)
    tv.tag_configure("odd", background=P.TILE)
    return holder, tv


def title_row(card_body, text, sub=""):
    row = tk.Frame(card_body, bg=P.CARD)
    row.pack(fill="x")
    tk.Label(row, text=text, bg=P.CARD, fg=P.TITLE, font=(FONT, 16, "bold")).pack(side="left")
    if sub:
        tk.Label(row, text=sub, bg=P.CARD, fg=P.MUTED, font=(FONT, 9)).pack(side="left", padx=(px(12), 0), pady=(px(6), 0))
    return row


def popup(widget, items):
    m = tk.Menu(widget, tearoff=0, font=(FONT, 10), bg=P.CARD, fg=P.INK, activebackground=P.ACCENT, activeforeground="#FFFFFF", bd=0)
    for label, cmd in items:
        m.add_separator() if label is None else m.add_command(label=label, command=cmd)
    try:
        m.tk_popup(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())
    finally:
        m.grab_release()


# =============================================================================== users
class UsersPage(tk.Frame):
    def __init__(self, app, parent):
        super().__init__(parent, bg=P.BG)
        self.app = app
        card = Card(self)
        card.pack(fill="both", expand=True, padx=px(16), pady=px(14))
        b = card.body
        top = title_row(b, "Users")
        self.search = SearchBox(top, "Search users...", lambda t: self.refresh(), width=24)
        self.search.pack(side="left", padx=px(18))
        self.search.var.trace_add("write", lambda *a: self.after(200, self.refresh))
        more = RButton(top, "More  \u25BE", None, "soft")
        more.pack(side="right", padx=(px(6), 0))
        more.command = lambda: popup(more, [("Profile / edit...", self.profile), ("Enable or disable", self.toggle), ("Reset password...", self.reset), (None, None), ("Delete user...", self.delete)])
        RButton(top, "Reject", self.reject, "soft").pack(side="right", padx=(px(6), 0))
        RButton(top, "Approve", self.approve, "navy").pack(side="right", padx=(px(6), 0))
        RButton(top, "+ Add user", self.add, "main").pack(side="right", padx=(px(6), 0))
        self.banner = tk.Label(b, text="", bg="#FFF4E5", fg="#8A4B00", font=(FONT, 10, "bold"), anchor="w", padx=px(12), pady=px(8))
        holder, self.tv = table(b, [("user", "Sign-in ID", 230), ("name", "Name", 170), ("emp", "Employee ID", 100), ("dept", "Department", 140), ("role", "Role", 90), ("status", "Status", 160)], height=16)
        holder.pack(fill="both", expand=True, pady=(px(12), 0))
        self.tv.tag_configure("pend", background="#FFF4E5")
        self.tv.bind("<Double-1>", lambda e: self.profile() if self.tv.identify_region(e.x, e.y) != "heading" else None)
        self.refresh()

    def refresh(self):
        if not self.winfo_exists():
            return
        text = self.search.get().lower()
        keep = self.tv.selection()
        self.tv.delete(*self.tv.get_children())
        n = 0
        for r in core.q("select * from users order by pending desc, id"):
            hay = " ".join(str(r[k] or "") for k in ("username", "name", "emp_id", "dept", "email")).lower()
            if text and text not in hay:
                continue
            tags = ("pend",) if r["pending"] else (("odd",) if n % 2 else ())
            self.tv.insert("", "end", iid=str(r["id"]), tags=tags, values=(r["username"], r["name"], r["emp_id"] or "", r["dept"] or "", "Administrator" if r["role"] == "admin" else "User",
                                                                      "Waiting for approval" if r["pending"] else "Active" if r["active"] else "Disabled"))
            n += 1
        for k in keep:
            if self.tv.exists(k):
                self.tv.selection_set(k)
        p = core.stats(0)["pending"]
        if p:
            self.banner.configure(text=f"\u26A0   {p} account request(s) waiting.  Select one and press Approve (or Reject).")
            self.banner.pack(fill="x", pady=(px(10), 0), before=self.tv.master)
        else:
            self.banner.pack_forget()
        self.app.update_pending()

    def pick(self):
        s = self.tv.selection()
        if not s:
            self.app.toast("Click a user in the list first.", "warn")
            return None
        return core.q("select * from users where id=?", (int(s[0]),))[0]

    def add(self):
        minlen = int(self.app.S.get("min_password") or 8)

        def check(v):
            if not core.EMAIL_RE.fullmatch(v["email"].lower()):
                return "Enter a valid email ID, for example name@company.com."
            if not v["name"]:
                return "Enter the full name."
            if core.q("select 1 from users where username=? or lower(email)=?", (v["email"].lower(), v["email"].lower())):
                return "That email ID is already registered."
            return core.pw_error(v["pw"], v["pw"], minlen)
        v = FormDialog(self.app, "Add user", [("email", "EMAIL ID (SIGN-IN NAME)", "text", "", ""), ("name", "FULL NAME", "text", "", ""), ("emp", "EMPLOYEE ID", "text", "", ""),
                                              ("dept", "DEPARTMENT", "text", "", ""), ("pw", "PASSWORD", "secret", "", f"At least {minlen} characters"), ("role", "ROLE", "combo", (["user", "admin"], "user"), "")],
                       ok="Add user", validate=check).run()
        if not v:
            return
        e = v["email"].lower()
        core.ex("insert into users(username,name,pw,role,emp_id,dept,email,created) values(?,?,?,?,?,?,?,?)", (e, v["name"], core.hashpw(v["pw"]), v["role"], v["emp"], v["dept"], e, core.now()))
        self.app.log("user added", e)
        self.app.toast(f"User {e} added.")
        self.refresh()

    def approve(self):
        r = self.pick()
        if not r:
            return
        if not r["pending"]:
            return self.app.toast("That account is not waiting for approval.", "info")
        core.ex("update users set active=1, pending=0 where id=?", (r["id"],))
        self.app.log("account approved", r["username"])
        self.app.toast(f"{r['name']} can sign in now.")
        self.refresh()

    def reject(self):
        r = self.pick()
        if not r:
            return
        if not r["pending"]:
            return self.app.toast("Only accounts waiting for approval can be rejected.", "info")
        if ask_yes_no(self.app, "Reject request", f"Remove the account request from {r['username']}?", "Reject", "Cancel", "danger"):
            core.ex("delete from users where id=?", (r["id"],))
            self.app.log("account rejected", r["username"])
            self.refresh()

    def profile(self):
        r = self.pick()
        if r:
            self.app.open_profile(r["id"])

    def toggle(self):
        r = self.pick()
        if not r:
            return
        if r["id"] == self.app.user["id"]:
            return self.app.toast("You cannot disable your own account.", "warn")
        if r["pending"]:
            return self.app.toast("Approve this account first.", "info")
        core.ex("update users set active=1-active where id=?", (r["id"],))
        self.app.log("user enabled/disabled", r["username"])
        self.refresh()

    def reset(self):
        r = self.pick()
        if not r:
            return
        minlen = int(self.app.S.get("min_password") or 8)
        v = FormDialog(self.app, "Reset password", [("pw", "NEW PASSWORD", "secret", "", f"At least {minlen} characters")], ok="Reset", intro=f"User: {r['username']}",
                       validate=lambda v: core.pw_error(v["pw"], v["pw"], minlen)).run()
        if v:
            core.ex("update users set pw=? where id=?", (core.hashpw(v["pw"]), r["id"]))
            self.app.log("password reset", r["username"])
            self.app.toast("Password reset.")

    def delete(self):
        r = self.pick()
        if not r:
            return
        if r["id"] == self.app.user["id"]:
            return self.app.toast("You cannot delete your own account.", "warn")
        if ask_yes_no(self.app, "Delete user", f"Delete {r['name']} ({r['username']})?\nTheir documents stay in the library.", "Delete", "Cancel", "danger"):
            for t, c in (("favorites", "user_id"), ("prefs", "user_id"), ("users", "id")):
                core.ex(f"delete from {t} where {c}=?", (r["id"],))
            self.app.log("user deleted", r["username"])
            self.refresh()


# =============================================================================== activity log
class ActivityPage(tk.Frame):
    def __init__(self, app, parent):
        super().__init__(parent, bg=P.BG)
        self.app = app
        card = Card(self)
        card.pack(fill="both", expand=True, padx=px(16), pady=px(14))
        b = card.body
        top = title_row(b, "Activity log", "sign-ins, uploads, changes")
        RButton(top, "Export CSV", self.export, "soft").pack(side="right", padx=(px(6), 0))
        RButton(top, "Refresh", self.refresh, "soft").pack(side="right", padx=(px(6), 0))
        self.search = SearchBox(top, "Filter...", lambda t: self.refresh(), width=24)
        self.search.pack(side="right", padx=px(10))
        self.search.var.trace_add("write", lambda *a: self.after(250, self.refresh))
        holder, self.tv = table(b, [("ts", "Time", 140), ("user", "User", 210), ("action", "Action", 170), ("detail", "Detail", 520)], height=18)
        holder.pack(fill="both", expand=True, pady=(px(12), 0))
        self.refresh()

    def refresh(self):
        if not self.winfo_exists():
            return
        t = self.search.get().lower()
        core.flush()
        self.tv.delete(*self.tv.get_children())
        n = 0
        for r in core.q("select * from logs order by id desc limit 1500"):
            if t and t not in f"{r['user']} {r['action']} {r['detail']}".lower():
                continue
            self.tv.insert("", "end", tags=("odd",) if n % 2 else (), values=(r["ts"], r["user"], r["action"], r["detail"]))
            n += 1

    def export(self):
        f = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=f"TDMS_activity_{dt.date.today():%Y%m%d}.csv", filetypes=[("CSV file", "*.csv")])
        if not f:
            return
        with open(f, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["Time", "User", "Action", "Detail"])
            core.flush()
            for r in core.q("select * from logs order by id"):
                w.writerow([r["ts"], r["user"], r["action"], r["detail"]])
        self.app.toast("Activity log saved.")


# =============================================================================== admin tab
class AdminPage(tk.Frame):
    """Branding | Rules | Backup & add-ons"""

    def __init__(self, app, parent):
        super().__init__(parent, bg=P.BG)
        self.app = app
        card = Card(self)
        card.pack(fill="both", expand=True, padx=px(16), pady=px(14))
        self.b = card.body
        title_row(self.b, "Administration", "make TDMS look and behave the way you want")
        nav = PillGroup(self.b, [("brand", "Branding", P.PRIMARY), ("rules", "Rules", P.PRIMARY), ("backup", "Backup & add-ons", P.PRIMARY)], command=self.show)
        nav.pack(anchor="w", pady=(px(12), px(8)))
        self.nav = nav
        self.host = tk.Frame(self.b, bg=P.CARD)
        self.host.pack(fill="both", expand=True)
        nav.set("brand")
        self.show("brand")

    def show(self, key):
        for w in self.host.winfo_children():
            w.destroy()
        getattr(self, "page_" + key)(self.host)

    # ------------------------------------------------------------- branding
    def page_brand(self, host):
        S = self.app.S
        left = tk.Frame(host, bg=P.CARD)
        left.pack(side="left", fill="y", padx=(0, px(40)))
        self.f = {}
        for k, label in (("app_name", "APPLICATION NAME"), ("short_name", "SHORT NAME (ICON TEXT)"), ("company", "COMPANY"), ("subtitle", "SUBTITLE"), ("tagline", "TAGLINE")):
            f = Field(left, label, width=34, value=S.get(k))
            f.pack(fill="x", pady=(px(6), 0))
            self.f[k] = f
        right = tk.Frame(host, bg=P.CARD)
        right.pack(side="left", fill="y")
        W.section_label(right, "BRAND COLOURS").pack(anchor="w", pady=(px(6), px(4)))
        self.colors = {k: S.get(k) for k in ("brand_red", "brand_blue", "brand_navy")}
        self.sw = {}
        for k, lab in (("brand_red", "Accent (buttons, highlights)"), ("brand_blue", "Secondary (links, charts)"), ("brand_navy", "Dark (titles, icon background)")):
            row = tk.Frame(right, bg=P.CARD)
            row.pack(fill="x", pady=px(3))
            sw = tk.Label(row, text="      ", bg=self.colors[k], bd=1, relief="solid")
            sw.pack(side="left")
            self.sw[k] = sw
            tk.Label(row, text=lab, bg=P.CARD, fg=P.INK, font=(FONT, 10), width=30, anchor="w").pack(side="left", padx=px(10))
            RButton(row, "Choose...", lambda k=k: self.pick_color(k), "soft").pack(side="left")
        W.section_label(right, "LOGO AND ICON").pack(anchor="w", pady=(px(16), px(4)))
        row = tk.Frame(right, bg=P.CARD)
        row.pack(anchor="w")
        RButton(row, "Upload logo...", self.upload_logo, "soft").pack(side="left")
        RButton(row, "Use default logo", self.reset_logo, "soft").pack(side="left", padx=px(6))
        RButton(right, "Make app icon from my colours", self.make_icon, "soft").pack(anchor="w", pady=(px(8), 0))
        tk.Label(right, text="After changing the icon, build the .exe again so the taskbar shows it.", bg=P.CARD, fg=P.MUTED, font=(FONT, 8)).pack(anchor="w", pady=(px(4), 0))
        W.section_label(right, "LOGIN SCREEN BACKGROUND").pack(anchor="w", pady=(px(16), px(4)))
        self.login_bg = PillGroup(right, [(k, v[3], P.PRIMARY) for k, v in g.LOGIN_PRESETS.items()], command=self.preview_bg)
        self.login_bg.pack(anchor="w")
        self.login_bg.set(S.get("login_bg") or "ocean")
        self.bgprev = tk.Label(right, bg=P.CARD)
        self.bgprev.pack(anchor="w", pady=(px(8), 0))
        self.preview_bg(self.login_bg.get())
        RButton(host, "Save and apply", self.save_brand, "main", big=True).place(relx=1.0, rely=1.0, x=-px(6), y=-px(6), anchor="se")

    def preview_bg(self, key):
        c = self.colors
        self._bgp = W.photo_of(g.login_background(px(250), px(130), key or "ocean", accent=c["brand_red"], blue=c["brand_blue"], navy=c["brand_navy"]))
        self.bgprev.configure(image=self._bgp)

    def pick_color(self, k):
        c = colorchooser.askcolor(color=self.colors[k], parent=self.app, title="Choose a colour")[1]
        if c:
            self.colors[k] = c.upper()
            self.sw[k].configure(bg=c)

    def upload_logo(self):
        f = filedialog.askopenfilename(title="Choose a logo (PNG)", filetypes=[("PNG image", "*.png")])
        if f:
            shutil.copy2(f, core.ROOT / "logo.png")
            self.app.log("logo changed")
            self.app.toast("Logo saved. Press Save and apply.", "info")

    def reset_logo(self):
        (core.ROOT / "logo.png").unlink(missing_ok=True)
        self.app.toast("The default logo will be used. Press Save and apply.", "info")

    def make_icon(self):
        try:
            c = self.colors
            g.save_icon(os.path.join(core.BASE, "app_icon.png"), os.path.join(core.BASE, "app_icon.ico"), navy=c["brand_navy"], blue=c["brand_blue"], red=c["brand_red"],
                        text=(self.f["short_name"].get() or "TDMS")[:5])
            self.app.toast("New app_icon.png / app_icon.ico saved. Build the .exe again to use it.")
        except Exception as e:
            self.app.toast(f"Could not make the icon: {e}", "err")

    def save_brand(self):
        for k, f in self.f.items():
            self.app.S.set(k, f.get())
        for k, v in self.colors.items():
            self.app.S.set(k, v)
        self.app.S.set("login_bg", self.login_bg.get() or "ocean")
        self.app.log("branding saved")
        self.app.rebuild(keep="admin")
        self.app.toast("Saved. The new look is active.")

    # ------------------------------------------------------------- rules
    def page_rules(self, host):
        S = self.app.S
        col = tk.Frame(host, bg=P.CARD)
        col.pack(anchor="w")
        self.flags = {}
        for k, t in (("allow_signup", "Allow people to create their own account on the sign-in screen"), ("require_approval", "New accounts must be approved by an admin"),
                     ("auto_backup", "Back up the database automatically once a day")):
            v = tk.BooleanVar(value=S.flag(k))
            tk.Checkbutton(col, text=t, variable=v, bg=P.CARD, activebackground=P.CARD, fg=P.INK, selectcolor=P.FIELD, bd=0, highlightthickness=0, font=(FONT, 10), cursor="hand2").pack(anchor="w", pady=px(5))
            self.flags[k] = v
        self.rf = {}
        for k, label, hint in (("email_domain", "ONLY ALLOW SIGN-UPS FROM THIS EMAIL DOMAIN", "Example: addverb.com   (empty = any email)"), ("min_password", "MINIMUM PASSWORD LENGTH", "Between 4 and 32"),
                               ("max_mb", "LARGEST FILE ALLOWED (MB)", "0 = no limit"), ("trash_days", "KEEP DELETED FILES IN THE RECYCLE BIN (DAYS)", "Between 1 and 365")):
            f = Field(col, label, width=34, value=S.get(k), hint=hint)
            f.pack(fill="x", pady=(px(10), 0))
            self.rf[k] = f
        RButton(col, "Save rules", self.save_rules, "main", big=True).pack(anchor="w", pady=(px(18), 0))

    def save_rules(self):
        try:
            mp = max(4, min(32, int(self.rf["min_password"].get() or 8)))
            mb = max(0, float(self.rf["max_mb"].get() or 0))
            td = max(1, min(365, int(self.rf["trash_days"].get() or 30)))
        except ValueError:
            return self.app.toast("Password length and file size must be numbers.", "err")
        for k, v in self.flags.items():
            self.app.S.set(k, "1" if v.get() else "0")
        self.app.S.set("email_domain", self.rf["email_domain"].get().lstrip("@").lower())
        self.app.S.set("min_password", mp)
        self.app.S.set("max_mb", mb)
        self.app.S.set("trash_days", td)
        self.app.log("rules saved")
        self.app.toast("Rules saved.")

    # ------------------------------------------------------------- backup + add-ons
    def page_backup(self, host):
        left = tk.Frame(host, bg=P.CARD)
        left.pack(side="left", fill="y", padx=(0, px(50)))
        W.section_label(left, "BACKUP").pack(anchor="w", pady=(px(6), px(6)))
        for t, c, k in (("Back up everything (ZIP)...", self.backup, "main"), ("Restore from a backup...", self.restore, "soft"), ("Open the data folder", lambda: self.app.open_path(core.ROOT), "soft"),
                        ("Change my password...", self.app.change_password_dialog, "soft")):
            RButton(left, t, c, k).pack(anchor="w", pady=px(4))
        tk.Label(left, text=f"Data folder:\n{core.ROOT}", bg=P.CARD, fg=P.MUTED, font=(FONT, 8), justify="left", wraplength=px(330)).pack(anchor="w", pady=(px(12), 0))
        right = tk.Frame(host, bg=P.CARD)
        right.pack(side="left", fill="y")
        W.section_label(right, "ADD-ONS (ONE-TIME DOWNLOAD, NEEDS INTERNET)").pack(anchor="w", pady=(px(6), px(6)))
        self.addon_row(right, "PDF viewer inside the app", "pymupdf", self.app.have_pdf(), "ready")
        tk.Label(right, text="Word, Excel, PowerPoint viewers, pictures and drag and drop need no add-on.\nAfter installing, close and open TDMS again.", bg=P.CARD, fg=P.MUTED, font=(FONT, 9), justify="left").pack(anchor="w", pady=(px(10), 0))
        st = core.stats(0)
        W.section_label(right, "ABOUT").pack(anchor="w", pady=(px(22), px(6)))
        for t in (f"{self.app.S.get('company')} {self.app.S.get('app_name')}   version {core.VERSION}", f"{st['docs']} documents   |   {core.size(st['size'])}   |   {st['users']} users   |   {st['trash']} in the Recycle bin",
                  "Drag and drop in: " + ("on" if self.app.drop_ok else "not available"), "Drag and drop out: " + ("on" if self.app.drop_ok else "not available (use Ctrl+C then Ctrl+V)")):
            tk.Label(right, text=t, bg=P.CARD, fg=P.INK, font=(FONT, 9), anchor="w").pack(anchor="w", pady=1)

    def addon_row(self, parent, label, package, ok, ok_text):
        row = tk.Frame(parent, bg=P.CARD)
        row.pack(fill="x", pady=px(5))
        tk.Label(row, text=label, bg=P.CARD, fg=P.INK, font=(FONT, 10), width=34, anchor="w").pack(side="left")
        if ok:
            tk.Label(row, text="\u2713  " + ok_text, bg=P.CARD, fg=P.GREEN, font=(FONT, 10, "bold")).pack(side="left")
        else:
            RButton(row, "Install", lambda: self.install(package, row), "main").pack(side="left")

    def install(self, package, row):
        self.app.toast(f"Installing {package}... please wait.", "info", 60000)
        self.app.config(cursor="watch")
        self.app.update()
        ok, text = core.pip_install(package)
        self.app.config(cursor="")
        if ok:
            self.app.toast("Installed. Close and open TDMS again to use it.")
        else:
            self.app.toast("Install failed. " + text[-160:], "err", 9000)

    def backup(self):
        f = filedialog.asksaveasfilename(defaultextension=".zip", initialfile=f"TDMS_backup_{dt.date.today():%Y%m%d}.zip", filetypes=[("Zip file", "*.zip")])
        if f:
            shutil.make_archive(f[:-4], "zip", core.ROOT)
            self.app.log("backup", f)
            self.app.toast("Backup saved.")

    def restore(self):
        f = filedialog.askopenfilename(title="Choose a TDMS backup (ZIP)", filetypes=[("Zip file", "*.zip")])
        if not f:
            return
        if not ask_yes_no(self.app, "Restore backup", "This replaces the current users, folders and documents with the backup.\nTDMS will restart.", "Restore", "Cancel", "danger"):
            return
        try:
            core.close_db()
            with zipfile.ZipFile(f) as z:
                z.extractall(core.ROOT)
        except Exception as e:
            return messagebox.showerror("Restore", str(e))
        self.app.restart()
