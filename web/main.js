/* TDMS web - shell, login, router, live updates */
"use strict";
const ROUTES_ADMIN = new Set(["users", "activity", "admin"]);

function go(r) { if (location.hash === "#/" + r) route(); else location.hash = "#/" + r; }
window.addEventListener("hashchange", () => { if (S.me) route(); });

/* ---------- login ---------- */
function showLogin(message) {
  S.me = null; closeMenu(); clear($("#app")); clearInterval(S.poll);
  applyTheme(localStorage.getItem("tdms_theme") || "light");
  const b = S.brand, dpr = window.devicePixelRatio > 1 ? 1.5 : 1;
  const w = Math.min(1200, Math.round(innerWidth * 0.55 * dpr)), hh = Math.min(1600, Math.round(innerHeight * dpr));
  let mode = "user";
  const id = h("input", { class: "inp", placeholder: "name@company.com", value: localStorage.getItem("tdms_login") || "", autocomplete: "username" });
  const pw = h("input", { class: "inp", type: "password", autocomplete: "current-password", onkeydown: e => { if (e.key === "Enter") submit(); } });
  const rem = h("input", { type: "checkbox", checked: !!localStorage.getItem("tdms_login") });
  const err = h("div", { class: "err", style: { color: "#D32F2F", minHeight: "20px", marginTop: "8px" } }, message || "");
  const btn = h("button", { class: "btn primary big", style: { width: "100%", marginTop: "10px" }, onclick: () => submit() }, "Sign in");
  const tabs = pills([["user", "User"], ["admin", "Administrator"]], "user", v => { mode = v; });
  async function submit() {
    err.textContent = ""; btn.disabled = true;
    try {
      const r = await post("/api/login", { login: id.value.trim(), password: pw.value, mode });
      if (rem.checked) localStorage.setItem("tdms_login", id.value.trim()); else localStorage.removeItem("tdms_login");
      start(r);
    } catch (e) { err.textContent = e.message; btn.disabled = false; pw.select(); }
  }
  const links = h("div", { class: "links" }, b.allow_signup ? h("a", { onclick: createAccount }, "Create account") : h("span"), h("a", { onclick: recover }, "Forgot password?"));
  const box = h("div", { class: "box" }, h("img", { class: "logo", src: "/brand/logo.png", alt: "", onerror: e => e.target.remove() }), h("h1", {}, b.app_name || "TDMS"), h("div", { class: "muted", style: { marginBottom: "16px" } }, b.subtitle || ""),
    tabs, h("label", { class: "lbl" }, "Email ID"), id, h("label", { class: "lbl" }, "Password"), pw, h("label", { class: "sw" }, rem, "Remember my email ID"), err, btn, links);
  add($("#app"), h("div", { class: "login", style: { backgroundImage: `url(/brand/bg.png?w=${Math.min(1600, Math.round(innerWidth))}&h=${Math.min(1000, Math.round(innerHeight))})` } }, h("div", { class: "hero", style: { backgroundImage: `url(/brand/hero.png?w=${w}&h=${hh})` } }), h("div", { class: "formside" }, box)));
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
  S.order = S.prefs.order_key || "pos"; S.desc = S.prefs.order_desc === "1"; S.view = "folder"; S.cat = +S.prefs.last_cat || null; S.q = ""; S.sel.clear(); S.tabs = [];
  const t = S.prefs.theme || localStorage.getItem("tdms_theme") || "light"; applyTheme(t); localStorage.setItem("tdms_theme", t);
  renderShell();
  clearInterval(S.poll); S.poll = setInterval(poll, 15000);
  if (S.mustChange) setTimeout(mustChangeDialog, 400);
  else if (me.needs_question) setTimeout(() => toast("Tip: set a security question in My profile so you can recover your password.", ""), 1500);
}
function renderShell() {
  const app = clear($("#app")), b = S.brand;
  const gs = h("input", { type: "search", placeholder: "Search all documents...", onkeydown: e => { if (e.key === "Enter" && gs.value.trim()) { S.view = "all"; S.cat = null; S.q = gs.value.trim(); S.sel.clear(); gs.value = ""; go("library"); if (S.route === "library") route(); } } });
  const prof = h("button", { class: "profile", onclick: e => { e.stopPropagation(); popMenu([{ label: "My profile and settings...", fn: () => profileDialog() }, { label: "Dark / light theme", fn: toggleTheme }, { label: "Shortcuts and tips", fn: helpDialog }, { sep: 1 }, { label: "Sign out", fn: logout }], 0, 0, e.currentTarget); } },
    avatar(S.me.id, 36, "&v=" + (S.me.has_photo ? 1 : 0)), h("div", {}, h("div", { class: "nm" }, S.me.name), h("div", { class: "em" }, [S.me.email || S.me.username, S.me.emp_id ? "#" + S.me.emp_id : "", S.me.role === "admin" ? "ADMINISTRATOR" : "USER"].filter(Boolean).join("  \u00B7  "))));
  const top = h("div", { class: "top" }, h("img", { class: "logo", src: "/brand/logo.png?" + (S.logoBust || ""), alt: "", onerror: e => e.target.remove() }), h("div", { class: "sep" }), h("div", {}, h("div", { class: "appname" }, b.app_name), h("div", { class: "apptag" }, b.subtitle)),
    h("div", { class: "gsearch search wide" }, gs), h("button", { class: "btn sq", title: "Dark / light", onclick: toggleTheme }, theme() === "dark" ? "\u2600" : "\u263E"), prof);
  S.tabBar = h("div", { class: "tabs" }); S.page = h("div", { class: "page" });
  add(app, h("div", { class: "shell" }, top, S.tabBar, S.page));
  renderTabs(); route();
}
function toggleTheme() { const t = theme() === "dark" ? "light" : "dark"; applyTheme(t); localStorage.setItem("tdms_theme", t); savePrefs({ theme: t }); renderShell(); }
function logout() { post("/api/logout").catch(() => { }).finally(() => { S.me = null; showLogin(); }); }
function renderTabs() {
  if (!S.tabBar) return;
  clear(S.tabBar);
  const mk = (key, label, color, icon, iconW, closable, onclick, badge) => h("button", { class: "tab" + (S.route === key ? " on" : ""), style: { "--c": color }, onclick },
    h("img", { class: "ic-c", src: icon, alt: "" }), h("img", { class: "ic-w", src: iconW, alt: "" }), h("span", { class: "ttl" }, label), badge ? h("span", { class: "dot" }, badge) : "",
    closable ? h("span", { class: "x", title: "Close", onclick: e => { e.stopPropagation(); closeTab(closable); } }, "\u00D7") : "");
  const main = [["library", "Library"], ["dashboard", "Dashboard"]]; if (isAdmin()) main.push(["users", "Users"], ["activity", "Activity"], ["admin", "Admin"]);
  for (const [k, label] of main) S.tabBar.appendChild(mk(k, label, MAIN_COLORS[k], `/icon/tab/${k}.png?s=36&c=${MAIN_COLORS[k].slice(1)}`, `/icon/tab/${k}.png?s=36&c=FFFFFF`, 0, () => go(k), k === "users" && S.pending ? S.pending : ""));
  for (const t of S.tabs) S.tabBar.appendChild(mk("doc/" + t.id, t.title, typeColor(t.type), iconUrl(t.type, 18), `/icon/ft/${t.type}.png?s=36&c=${typeColor(t.type).slice(1)}&inv=1`, t.id, () => go("doc/" + t.id)));
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
  if (S.pending !== c.pending) { S.pending = c.pending; renderTabs(); }
  if (S.lastStamp === undefined) { S.lastStamp = s; return; }
  if (s === S.lastStamp) return;
  S.lastStamp = s;
  if (S.route === "library" && L.root && L.root.isConnected && !document.querySelector(".overlay")) { await refreshLibrary(); }
  else if (S.route === "dashboard" && !document.querySelector(".overlay")) renderDashboard(S.page);
}
function helpDialog() {
  const rows = [["/", "Search all documents"], ["Ctrl + A", "Select all documents"], ["Delete", "Move the selected documents to the Recycle bin"], ["F2", "Rename the selected document"], ["Enter", "Open the selected documents in tabs"], ["Alt + Up / Down", "Move documents up / down in the folder"],
    ["Shift + click", "Select a range"], ["Ctrl + click", "Add one to the selection"], ["Drag files in", "Drop files or a whole folder on the list to upload"], ["Right-click", "More actions on a document or a folder"], ["View > Preview panel", "Thumbnail and facts of the selected document"], ["Details", "Set a status and a review date; the Dashboard reminds you"]];
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
