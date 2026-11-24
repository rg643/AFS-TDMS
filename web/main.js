/* TDMS web - shell, login, router, live updates */
"use strict";
const ROUTES_ADMIN = new Set(["approvals", "users", "activity", "admin"]);

function go(r) { if (location.hash === "#/" + r) route(); else location.hash = "#/" + r; }
window.addEventListener("hashchange", () => { if (S.me) route(); });

/* ---------- login ---------- */
function showLogin(message) {
  S.me = null; closeMenu(); clear($("#app")); clearInterval(S.poll);
  applyTheme(localStorage.getItem("tdms_theme") || "light");
  const b = S.brand;
  let mode = "user", shown = false;
  const id = h("input", { class: "inp", placeholder: "name@company.com", value: localStorage.getItem("tdms_login") || "", autocomplete: "username", spellcheck: "false" });
  const pw = h("input", { class: "inp", type: "password", placeholder: "Enter your password", autocomplete: "current-password", onkeydown: e => { if (e.key === "Enter") submit(); } });
  id.addEventListener("keydown", e => { if (e.key === "Enter") pw.focus(); });
  const eye = h("button", { class: "eye", type: "button", title: "Show / hide password", tabindex: "-1", onclick: () => { shown = !shown; pw.type = shown ? "text" : "password"; clear(eye); eye.appendChild(svgIcon(shown ? "eyeoff" : "eye")); } }, svgIcon("eye"));
  const rem = h("input", { type: "checkbox", checked: !!localStorage.getItem("tdms_login") });
  const alertBox = h("div", {});
  const say = (msg, info) => { clear(alertBox); if (msg) alertBox.appendChild(h("div", { class: "alert" + (info ? " info" : "") }, svgIcon("warn", 18), h("span", {}, msg))); };
  say(message, true);
  const btn = h("button", { class: "btn primary go", onclick: () => submit() }, "Sign in");
  const seg = pills([["user", "User"], ["admin", "Administrator"]], "user", v => { mode = v; });
  async function submit() {
    say(""); btn.disabled = true; btn.textContent = "Signing in...";
    try {
      const r = await post("/api/login", { login: id.value.trim(), password: pw.value, mode });
      if (rem.checked) localStorage.setItem("tdms_login", id.value.trim()); else localStorage.removeItem("tdms_login");
      start(r);
    } catch (e) { say(e.message); btn.disabled = false; btn.textContent = "Sign in"; pw.select(); }
  }
  const logo = src => h("img", { src, alt: "", onerror: e => e.target.parentElement.style.display = "none" });
  const brand = h("div", { class: "brand" },
    h("div", { class: "tile" }, logo("/brand/logo.png?" + (S.logoBust || ""))),
    h("div", {}, h("h2", { class: "bname" }, b.app_name || "TDMS"), h("div", { class: "bsub" }, b.subtitle || ""), h("div", { class: "rule" }), h("div", { class: "btag" }, b.tagline || "")),
    h("div", { class: "bfoot" }, "\u00A9 " + new Date().getFullYear() + "  " + (b.company || "")));
  const form = h("div", { class: "formside" },
    h("div", { class: "mlogo" }, logo("/brand/logo.png?" + (S.logoBust || ""))),
    h("h1", {}, "Welcome back"), h("div", { class: "lead" }, "Sign in to your " + (b.app_name || "TDMS") + " account to continue."),
    seg, alertBox,
    h("label", { class: "lbl" }, "Email ID"), h("div", { class: "ifield" }, svgIcon("mail"), id),
    h("label", { class: "lbl" }, "Password"), h("div", { class: "ifield" }, svgIcon("lock"), pw, eye),
    h("div", { class: "rowlinks" }, h("label", {}, rem, "Remember my email ID"), h("a", { onclick: recover }, "Forgot password?")),
    btn,
    b.allow_signup ? h("div", { class: "newhere" }, "New here?  ", h("a", { onclick: createAccount }, "Create an account")) : null,
    h("div", { class: "secure" }, svgIcon("shield"), "Secure sign-in  \u00B7  activity is recorded"));
  const bg = `/brand/bg.png?w=${Math.min(1600, Math.round(innerWidth))}&h=${Math.min(1000, Math.round(innerHeight))}`;
  add($("#app"), h("div", { class: "login", style: { backgroundImage: `url(${bg})` } }, h("div", { class: "auth" }, brand, form)));
  (id.value ? pw : id).focus();
}
function createAccount() {
  const f = { name: h("input", { class: "inp" }), email: h("input", { class: "inp", placeholder: S.brand.email_domain ? "name@" + S.brand.email_domain : "name@company.com" }), emp: h("input", { class: "inp" }), dept: h("input", { class: "inp" }),
    pw: h("input", { class: "inp", type: "password" }), pw2: h("input", { class: "inp", type: "password" }), q: select(S.questions, S.questions[0]), a: h("input", { class: "inp" }) };
  dialog({ title: "Create account", width: 540, body: [h("p", { class: "muted" }, S.brand.require_approval ? "An administrator must approve your account before you can sign in." : ""), field("FULL NAME", f.name), field("EMAIL ID", f.email), h("div", { class: "form2" }, field("EMPLOYEE ID", f.emp), field("DEPARTMENT", f.dept)),
    h("div", { class: "form2" }, field("PASSWORD", f.pw, `At least ${S.brand.min_password} characters`), field("REPEAT PASSWORD", f.pw2)), field("SECURITY QUESTION", f.q), field("ANSWER", f.a)],
    buttons: [{ text: "Cancel" }, { text: "Create account", kind: "primary", fn: async d => {
      if (f.pw.value !== f.pw2.value) throw new Error("The two passwords are not the same.");
      const r = await post("/api/register", { name: f.name.value, email: f.email.value, emp_id: f.emp.value, dept: f.dept.value, password: f.pw.value, question: f.q.value, answer: f.a.value });
      toast(r.pending ? "Account requested. You can sign in after an admin approves it." : "Account created. You can sign in now.", "ok");
    } }] });
}
function recover() {
  const id = h("input", { class: "inp", placeholder: "Email ID or employee ID" }), body = h("div", {}), state = {};
  const step1 = () => { clear(body); add(body, field("YOUR EMAIL ID OR EMPLOYEE ID", id)); };
  const step2 = q => { clear(body); const a = h("input", { class: "inp" }), n1 = h("input", { class: "inp", type: "password" }), n2 = h("input", { class: "inp", type: "password" }); state.a = a; state.n1 = n1; state.n2 = n2; add(body, h("p", {}, h("b", {}, q)), field("YOUR ANSWER", a), field("NEW PASSWORD", n1, `At least ${S.brand.min_password} characters`), field("REPEAT NEW PASSWORD", n2)); };
  step1();
  dialog({ title: "Forgot password", width: 480, body, buttons: [{ text: "Cancel" }, { text: "Continue", kind: "primary", fn: async () => {
    if (!state.a) { const r = await post("/api/recover/question", { id: id.value }); step2(r.question); return false; }
    if (state.n1.value !== state.n2.value) throw new Error("The two passwords are not the same.");
    const r = await post("/api/recover/verify", { id: id.value, answer: state.a.value, new_password: state.n1.value });
    toast(`Password changed. Sign in as ${r.username}.`, "ok");
  } }] });
}

/* ---------- shell ---------- */
async function start(me) {
  S.me = me.user; S.prefs = me.prefs; applyBrand(me.brand); S.types = me.types; S.statuses = me.statuses; S.statusColors = me.status_colors; S.chips = me.chips; S.questions = me.questions; S.exactOk = me.exact_ok; S.mustChange = me.must_change;
  S.order = S.prefs.order_key || "pos"; S.desc = S.prefs.order_desc === "1"; S.view = "folder"; S.cat = +S.prefs.last_cat || null; S.q = ""; S.sel.clear(); S.tabs = []; S.prev = null; S.countsSeen = false; S.counts = { pending_docs: 0, pending_users: 0, my_pending: 0, my_rejected: 0 };
  const t = S.prefs.theme || localStorage.getItem("tdms_theme") || "light"; applyTheme(t); localStorage.setItem("tdms_theme", t);
  renderShell();
  clearInterval(S.poll); S.poll = setInterval(poll, 15000); refreshCounts(); startIdleWatch(me.idle_minutes);
  if (S.mustChange) setTimeout(mustChangeDialog, 400);
  else if (me.needs_question) setTimeout(() => toast("Tip: set a security question in My profile so you can recover your password.", ""), 1500);
}
function renderShell() {
  const app = clear($("#app")), b = S.brand;
  const gs = h("input", { type: "search", placeholder: "Search all documents...", value: S.q || "", autocomplete: "off", spellcheck: "false",
    oninput: debounce(() => setSearch(gs.value), 280), onkeydown: e => { if (e.key === "Enter") setSearch(gs.value); else if (e.key === "Escape") { gs.value = ""; setSearch(""); gs.blur(); } } });
  S.gs = gs;
  const prof = h("button", { class: "profile", title: "Account", onclick: e => { e.stopPropagation(); profilePanel(e.currentTarget); } },
    avatar(S.me.id, 34, "&v=" + (S.me.has_photo ? 1 : 0)), h("span", { class: "pt" }, h("span", { class: "nm" }, S.me.name), roleBadge(S.me.role)), svgIcon("down", 14));
  const top = h("div", { class: "top" }, h("img", { class: "logo", src: "/brand/logo.png?" + (S.logoBust || ""), alt: "", onerror: e => e.target.remove() }), h("div", { class: "sep" }), h("div", {}, h("div", { class: "appname" }, b.app_name), h("div", { class: "apptag" }, b.subtitle)),
    h("div", { class: "gsearch search wide" }, gs, h("kbd", {}, "/")), S.me.role === "viewer" ? null : h("button", { class: "btn sq ghost bell", title: "Notifications", onclick: e => { e.stopPropagation(); bellPanel(e.currentTarget); } }, svgIcon("bell", 18), (S.bellDot = h("span", { class: "bdot hidden" }))),
    h("button", { class: "btn sq ghost", title: "Dark / light theme", onclick: toggleTheme }, svgIcon(theme() === "dark" ? "sun" : "moon", 18)), prof);
  S.tabBar = h("div", { class: "tabs" }); S.page = h("div", { class: "page" });
  add(app, h("div", { class: "shell" }, top, S.tabBar, S.page));
  renderTabs(); updateBell(); route();
}
/* the account card in the top corner */
function profilePanel(anchor) {
  const u = S.me, dark = theme() === "dark";
  const item = (icon, label, fn, cls = "") => h("div", { class: "pm-it " + cls, onclick: () => { closeMenu(); fn(); } }, svgIcon(icon, 17), h("span", {}, label));
  popNode(h("div", { class: "pmenu" },
    h("div", { class: "pm-head" }, avatar(u.id, 56, "&v=" + (u.has_photo ? 1 : 0)), h("div", { class: "pm-who" }, h("div", { class: "pm-name" }, u.name), h("div", { class: "muted small" }, u.email || u.username),
      h("div", { class: "pm-meta" }, roleBadge(u.role), u.emp_id ? h("span", { class: "muted small" }, "#" + u.emp_id) : "", u.dept ? h("span", { class: "muted small" }, u.dept) : ""))),
    h("div", { class: "pm-list" }, item("settings", "My profile and settings", () => profileDialog()), S.installPrompt ? item("download", "Install as an app", () => { S.installPrompt.prompt(); S.installPrompt = null; }) : null, item(dark ? "sun" : "moon", dark ? "Switch to light theme" : "Switch to dark theme", toggleTheme), item("keyboard", "Shortcuts and tips", helpDialog)),
    h("div", { class: "pm-list pm-foot" }, item("logout", "Sign out", logout, "danger"))), anchor, true);
}
function toggleTheme() { const t = theme() === "dark" ? "light" : "dark"; applyTheme(t); localStorage.setItem("tdms_theme", t); savePrefs({ theme: t }); renderShell(); }
/* sign out after a while without any activity (set in Admin > Rules) */
function startIdleWatch(min) {
  clearInterval(S.idleTimer); S.idleMin = +min || 0;
  if (!S.idleMin) return;
  S.lastAct = Date.now();
  if (!S.idleBound) { ["mousemove", "keydown", "click", "scroll", "touchstart", "wheel"].forEach(ev => window.addEventListener(ev, () => { S.lastAct = Date.now(); }, { passive: true, capture: true })); S.idleBound = true; }
  S.idleTimer = setInterval(() => {
    if (!S.me || !S.idleMin) return;
    if (document.querySelector(".uploads")) { S.lastAct = Date.now(); return; }
    if (Date.now() - S.lastAct > S.idleMin * 60000) { const mins = S.idleMin; clearInterval(S.idleTimer); post("/api/logout").catch(() => { }).finally(() => { S.me = null; showLogin(`You were signed out after ${mins} minute(s) without activity.`); }); }
  }, Math.min(30000, Math.max(1000, S.idleMin * 60000 / 4)));
}
function logout() { post("/api/logout").catch(() => { }).finally(() => { S.me = null; showLogin(); }); }
function renderTabs() {
  if (!S.tabBar) return;
  clear(S.tabBar);
  const mk = (key, label, color, icons, closable, onclick, badge) => h("button", { class: "tab" + (S.route === key ? " on" : ""), style: { "--c": color }, onclick },
    icons.svg ? h("span", { class: "ic-c" }, svgIcon(icons.svg, 18)) : h("img", { class: "ic-c", src: icons.c, alt: "" }), icons.svg ? h("span", { class: "ic-w" }, svgIcon(icons.svg, 18)) : h("img", { class: "ic-w", src: icons.w, alt: "" }),
    h("span", { class: "ttl" }, label), badge ? h("span", { class: "dot" }, badge) : "", closable ? h("span", { class: "x", title: "Close", onclick: e => { e.stopPropagation(); closeTab(closable); } }, "\u00D7") : "");
  const main = [["library", "Library"], ["dashboard", "Dashboard"]]; if (isAdmin()) main.push(["approvals", "Approvals"], ["users", "Users"], ["activity", "Activity"], ["admin", "Admin"]);
  const badges = { approvals: S.counts.pending_docs, users: S.counts.pending_users };
  for (const [k, label] of main) S.tabBar.appendChild(mk(k, label, MAIN_COLORS[k], k === "approvals" ? { svg: "inbox" } : { c: `/icon/tab/${k}.png?s=36&c=${MAIN_COLORS[k].slice(1)}`, w: `/icon/tab/${k}.png?s=36&c=FFFFFF` }, 0, () => go(k), badges[k] || ""));
  for (const t of S.tabs) S.tabBar.appendChild(mk("doc/" + t.id, t.title, typeColor(t.type), { c: iconUrl(t.type, 18), w: `/icon/ft/${t.type}.png?s=36&c=${typeColor(t.type).slice(1)}&inv=1` }, t.id, () => go("doc/" + t.id)));
}
function refreshBadges() { renderTabs(); }

/* ---------- router ---------- */
function route() {
  if (!S.me || !S.page) return;
  const r = (location.hash.replace(/^#\//, "") || "library").split("?")[0];
  S.route = r; closeMenu();
  if (ROUTES_ADMIN.has(r) && !isAdmin()) return go("library");
  renderTabs();
  S.page.className = "page" + (r === "library" || r.startsWith("doc/") ? " nopad" : "");
  S.page.style.overflow = r === "library" || r.startsWith("doc/") ? "hidden" : "auto";
  if (r === "library") renderLibrary(S.page);
  else if (r === "dashboard") renderDashboard(S.page);
  else if (r === "approvals") renderApprovals(S.page);
  else if (r === "users") renderUsers(S.page);
  else if (r === "activity") renderActivity(S.page);
  else if (r === "admin") renderAdmin(S.page);
  else if (r.startsWith("doc/")) { const id = +r.slice(4); if (!S.tabs.some(t => t.id === id)) S.tabs.push({ id, title: "Document " + id, type: "file" }); renderTabs(); renderViewer(S.page, id); }
  else go("library");
}

/* ---------- live updates (other people add documents) ---------- */
async function poll() {
  if (!S.me || document.hidden) return;
  let c; try { c = await api("/api/changes", { quiet: true }); } catch (e) { return; }
  const s = JSON.stringify([c.docs, c.logs]);
  applyCounts(c, true);
  if (S.lastStamp === undefined) { S.lastStamp = s; return; }
  if (s === S.lastStamp) return;
  S.lastStamp = s;
  if (S.route === "library" && L.root && L.root.isConnected && !document.querySelector(".overlay")) { await refreshLibrary(); }
  else if (S.route === "dashboard" && !document.querySelector(".overlay")) renderDashboard(S.page);
  else if (S.route === "approvals" && !document.querySelector(".overlay")) renderApprovals(S.page);
}
function helpDialog() {
  const rows = [["/", "Search all documents"], ["Ctrl + A", "Select all documents"], ["Delete", "Move the selected documents to the Recycle bin"], ["F2", "Rename the selected document"], ["Enter", "Open the selected documents in tabs"], ["Alt + Up / Down", "Move documents up / down in the folder"],
    ["Shift + click", "Select a range"], ["Ctrl + click", "Add one to the selection"], ["Drag files in", "Drop files or a whole folder on the list to upload"], ["Right-click", "More actions on a document or a folder"], ["View > Preview panel", "Thumbnail and facts of the selected document"], ["Details", "Set a status and a review date; the Dashboard reminds you"], ["Approval", "Documents you add wait for an admin; see them under View > My uploads"], ["New folder", "Users can create folders and subfolders; admins also rename, move and delete them"], ["Drag a document", "Drop it on a folder in the list on the left to move it"], ["Comments", "Open a document and press Comments to discuss it with the team"], ["Copy link", "More > Copy link, or inside a document, to send a direct link"]];
  dialog({ title: "Shortcuts and tips", width: 640, body: h("table", { class: "mini" }, h("tbody", {}, ...rows.map(([k, t]) => h("tr", { style: { cursor: "default" } }, h("td", {}, h("b", { style: { color: "var(--blue)" } }, k)), h("td", {}, t))))) });
}
document.addEventListener("keydown", e => {
  if (e.key === "/" && S.me && !["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName) && !document.querySelector(".overlay")) { e.preventDefault(); const i = $(".gsearch input"); if (i) i.focus(); }
});

/* ---------- start ---------- */
(async function init() {
  try { const b = await api("/api/brand"); S.questions = b.questions || []; applyBrand(b); } catch (e) { /* offline: keep defaults */ }
  try { start(await api("/api/me", { quiet: true })); }
  catch (e) { showLogin(); }
})();

/* ---------- numbers behind the tab badges, the bell and the banners ---------- */
function applyCounts(c, notify) {
  const old = S.counts;
  S.counts = { pending_docs: c.pending_docs || 0, pending_users: c.pending || 0, my_pending: c.my_pending || 0, my_rejected: c.my_rejected || 0 };
  if (notify && S.me && S.me.role === "user" && S.countsSeen) {
    if (S.counts.my_rejected > old.my_rejected) toast("One of your uploads was rejected. Open  View > My uploads  to see why.", "err");
    else if (S.counts.my_pending < old.my_pending) toast("Good news: an upload of yours was approved. It is now in the library.", "ok");
  }
  S.countsSeen = true;
  renderTabs(); updateBell();
  if (S.route === "library" && L.root && L.root.isConnected) renderBanner();
}
async function refreshCounts() { if (!S.me) return; try { applyCounts(await api("/api/changes", { quiet: true }), false); } catch (e) { /* ignore */ } }
function updateBell() {
  if (!S.bellDot) return;
  const c = S.counts, n = isAdmin() ? c.pending_docs + c.pending_users : c.my_pending + c.my_rejected;
  S.bellDot.textContent = n > 9 ? "9+" : String(n); S.bellDot.classList.toggle("hidden", !n);
}
function bellPanel(anchor) {
  const c = S.counts, rows = [];
  if (isAdmin()) {
    if (c.pending_docs) rows.push(["inbox", `${c.pending_docs} document(s) waiting for approval`, "Review uploads", () => go("approvals")]);
    if (c.pending_users) rows.push(["users", `${c.pending_users} account(s) waiting for approval`, "Review accounts", () => go("users")]);
  } else {
    if (c.my_rejected) rows.push(["warn", `${c.my_rejected} of your uploads were rejected`, "See why", showMyUploads]);
    if (c.my_pending) rows.push(["clock", `${c.my_pending} of your uploads are waiting for approval`, "View my uploads", showMyUploads]);
  }
  popNode(h("div", { class: "notif" }, h("div", { class: "nf-head" }, "Notifications"),
    rows.length ? rows.map(([ic, t, lab, fn]) => h("div", { class: "nf-it", onclick: () => { closeMenu(); fn(); } }, h("span", { class: "nf-ic" }, svgIcon(ic, 18)), h("div", {}, h("div", {}, t), h("div", { class: "small", style: { color: "var(--blue)" } }, lab + " \u203A")))) :
      h("div", { class: "nf-empty" }, svgIcon("check", 22), h("div", {}, "You are all caught up."))), anchor, true);
}

window.addEventListener("beforeinstallprompt", e => { e.preventDefault(); S.installPrompt = e; });
if ("serviceWorker" in navigator) window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => { }));
