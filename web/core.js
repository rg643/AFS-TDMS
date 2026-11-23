/* TDMS web - shared helpers, state, server calls and small UI parts (menus, dialogs, toasts) */
"use strict";
const S = {
  me: null, prefs: {}, brand: {}, types: {}, statuses: [], statusColors: {}, chips: [], questions: [], exactOk: false,
  route: "library", tabs: [], folders: [], bin: 0, expanded: new Set(),
  view: "folder", cat: null, docs: [], total: 0, sel: new Set(), anchor: null, order: "pos", desc: false, chip: "all", q: "",
  stamp: null, pending: 0
};
const MAIN_COLORS = { library: "#2E6DB4", dashboard: "#1D8348", users: "#8E44AD", activity: "#F28C1E", admin: "#607D8B" };

/* ---------- tiny DOM builder: h("div", {class:"x", onclick: fn}, child, "text") ---------- */
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style" && typeof v === "object") { for (const [sk, sv] of Object.entries(v)) { if (sk.startsWith("--")) el.style.setProperty(sk, sv); else el.style[sk] = sv; } }
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (k === "value") el.value = v;
    else if (k === "checked" || k === "disabled" || k === "selected") el[k] = !!v;
    else if (k === "dataset") Object.assign(el.dataset, v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  add(el, kids);
  return el;
}
function add(el, ...kids) {
  for (const k of kids.flat(Infinity)) {
    if (k === null || k === undefined || k === false) continue;
    el.appendChild(k instanceof Node ? k : document.createTextNode(String(k)));
  }
  return el;
}
const $ = (s, el) => (el || document).querySelector(s);
const $$ = (s, el) => [...(el || document).querySelectorAll(s)];
function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); return el; }
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

/* ---------- formatting ---------- */
function fmtSize(n) {
  n = Number(n) || 0;
  const u = ["B", "KB", "MB", "GB", "TB"]; let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return (i === 0 ? n.toFixed(0) : n.toFixed(1)) + " " + u[i];
}
function fmtDate(s) {
  if (!s) return "";
  const m = /^(\d{4})-(\d\d)-(\d\d)(?:[ T](\d\d):(\d\d))?/.exec(s);
  if (!m) return s;
  const [, y, mo, d, hh, mm] = m, style = S.prefs.datefmt || "ISO", t = hh ? ` ${hh}:${mm}` : "";
  const mon = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][+mo - 1];
  if (style === "DMY") return `${d}-${mo}-${y}${t}`;
  if (style === "Long") return `${+d} ${mon} ${y}${hh ? ", " + hh + ":" + mm : ""}`;
  return `${y}-${mo}-${d}${t}`;
}
function typeColor(t) { return (S.prefs["fc_" + t] && /^#[0-9a-f]{6}$/i.test(S.prefs["fc_" + t])) ? S.prefs["fc_" + t] : ((S.types[t] || S.types.file || {}).color || "#90A4AE"); }
function iconUrl(t, size) { return `/icon/ft/${t}.png?s=${Math.round(size * (window.devicePixelRatio > 1 ? 2 : 1))}&c=${typeColor(t).slice(1)}`; }
function fileIcon(t, size = 22) { return h("img", { src: iconUrl(t, size), width: size, height: size, alt: "", draggable: "false" }); }
function folderIcon(color, size = 20) { return h("img", { src: `/icon/folder/f.png?s=${size * (window.devicePixelRatio > 1 ? 2 : 1)}${color ? "&c=" + color.slice(1) : ""}`, width: size, height: size, alt: "", draggable: "false" }); }
function avatar(uid, size = 36, bust = "") { return h("img", { src: `/api/users/${uid}/photo?s=${size * 2}${bust}`, width: size, height: size, alt: "", style: { borderRadius: "50%" } }); }
function statusBadge(st) { return st ? h("span", { class: "badge", style: { "--c": S.statusColors[st] || "#90A4AE" } }, st) : ""; }
function isAdmin() { return S.me && S.me.role === "admin"; }
function theme() { return document.documentElement.dataset.theme === "dark" ? "dark" : "light"; }

/* ---------- server calls ---------- */
class ApiError extends Error { constructor(msg, code) { super(msg); this.code = code; } }
async function api(path, opts = {}) {
  const o = { method: opts.method || "GET", headers: { "X-Requested-With": "tdms" }, credentials: "same-origin" };
  if (opts.body !== undefined) { o.headers["Content-Type"] = "application/json"; o.body = JSON.stringify(opts.body); }
  if (opts.form) o.body = opts.form;
  let r;
  try { r = await fetch(path, o); } catch (e) { throw new ApiError("Cannot reach the server. Check the network.", 0); }
  let data = null;
  try { data = await r.json(); } catch (e) { /* not JSON */ }
  if (!r.ok) {
    if (r.status === 401 && S.me && !opts.quiet) { S.me = null; if (window.showLogin) showLogin("Your session ended. Please sign in again."); }
    throw new ApiError((data && data.error) || `Server error (${r.status})`, r.status);
  }
  return data;
}
const post = (p, body) => api(p, { method: "POST", body: body || {} });
async function savePrefs(obj) { Object.assign(S.prefs, obj); try { await post("/api/prefs", obj); } catch (e) { /* ignore */ } }

/* ---------- toasts ---------- */
function toast(msg, kind) {
  const t = h("div", { class: "toast " + (kind || "") }, svgIcon(kind === "err" ? "warn" : kind === "ok" ? "check" : "info2", 18), h("span", {}, msg));
  $("#toasts").appendChild(t);
  setTimeout(() => t.remove(), kind === "err" ? 6000 : 3200);
}
const toastErr = e => toast(e && e.message ? e.message : String(e), "err");

/* ---------- popup menu: items = [{label, fn, dis, sep, hd, check}] ---------- */
let _menu = null;
function closeMenu() { if (_menu) { _menu.remove(); _menu = null; } }
function popMenu(items, x, y, anchor) {
  closeMenu();
  const m = h("div", { class: "menu" });
  for (const it of items) {
    if (!it) continue;
    if (it.sep) { m.appendChild(h("div", { class: "sep" })); continue; }
    if (it.hd) { m.appendChild(h("div", { class: "hd" }, it.hd)); continue; }
    m.appendChild(h("div", { class: "it" + (it.dis ? " dis" : ""), onclick: e => { e.stopPropagation(); closeMenu(); it.fn && it.fn(); } },
      it.check !== undefined ? h("span", { class: "ck" }, it.check ? "\u2713" : "") : null, it.label));
  }
  document.body.appendChild(m);
  const r = anchor ? anchor.getBoundingClientRect() : null;
  let px = r ? r.left : x, py = r ? r.bottom + 4 : y;
  const w = m.offsetWidth, hh = m.offsetHeight;
  if (px + w > innerWidth - 8) px = Math.max(8, innerWidth - w - 8);
  if (py + hh > innerHeight - 8) py = Math.max(8, (r ? r.top - hh - 4 : innerHeight - hh - 8));
  m.style.left = px + "px"; m.style.top = py + "px";
  _menu = m;
}
document.addEventListener("click", closeMenu);
document.addEventListener("scroll", closeMenu, true);
window.addEventListener("resize", closeMenu);

/* ---------- dialogs ---------- */
function dialog({ title, body, buttons, width, onclose }) {
  const ov = h("div", { class: "overlay" });
  const err = h("div", { class: "err" });
  const dlg = h("div", { class: "dlg", style: { "--w": (width || 520) + "px" } },
    title ? h("div", { class: "hd" }, h("span", {}, title), h("button", { class: "xbtn", type: "button", title: "Close", onclick: () => api_.close() }, svgIcon("x", 18))) : null, h("div", { class: "bd" }, body, err), h("div", { class: "ft" }));
  ov.appendChild(dlg);
  const api_ = {
    el: dlg, err: m => { err.textContent = m || ""; },
    close: () => { ov.remove(); document.removeEventListener("keydown", esc); onclose && onclose(); },
    btn: {}
  };
  const ft = $(".ft", dlg);
  for (const b of buttons || [{ text: "Close" }]) {
    const el = h("button", { class: "btn " + (b.kind || ""), onclick: async () => {
      if (!b.fn) return api_.close();
      el.disabled = true; api_.err("");
      try { const r = await b.fn(api_); if (r !== false) api_.close(); } catch (e) { api_.err(e.message || String(e)); }
      el.disabled = false;
    } }, b.text);
    api_.btn[b.text] = el; ft.appendChild(el);
  }
  const esc = e => { if (e.key === "Escape" && !b_locked) api_.close(); };
  let b_locked = false;
  api_.lock = () => { b_locked = true; };
  document.addEventListener("keydown", esc);
  ov.addEventListener("mousedown", e => { if (e.target === ov && !b_locked) api_.close(); });
  document.body.appendChild(ov);
  const first = $("input,select,textarea", dlg); if (first) setTimeout(() => first.focus(), 30);
  return api_;
}
function confirmDlg(title, text, okText = "OK", kind = "primary") {
  return new Promise(res => {
    let done = false;
    const d = dialog({ title, width: 460, body: h("p", { style: { whiteSpace: "pre-line", margin: "6px 0" } }, text), onclose: () => { if (!done) res(false); },
      buttons: [{ text: "Cancel" }, { text: okText, kind, fn: () => { done = true; res(true); } }] });
  });
}
function promptDlg(title, label, value = "", okText = "OK") {
  return new Promise(res => {
    let done = false;
    const inp = h("input", { class: "inp", value, onkeydown: e => { if (e.key === "Enter") d.btn[okText].click(); } });
    const d = dialog({ title, width: 440, body: [h("label", { class: "lbl" }, label), inp], onclose: () => { if (!done) res(null); },
      buttons: [{ text: "Cancel" }, { text: okText, kind: "primary", fn: dd => { if (!inp.value.trim()) { dd.err("Please type a value."); return false; } done = true; res(inp.value.trim()); } }] });
  });
}
/* a labelled field row for forms */
function field(label, input, hint) { return h("div", {}, h("label", { class: "lbl" }, label), input, hint ? h("div", { class: "muted small", style: { marginTop: "4px" } }, hint) : null); }
function select(options, value, cls = "inp") {
  const s = h("select", { class: cls });
  for (const o of options) { const [v, t] = Array.isArray(o) ? o : [o, o]; s.appendChild(h("option", { value: v, selected: v === value }, t)); }
  return s;
}
function pills(options, value, onchange) {
  const box = h("div", { class: "pills" });
  options.forEach(([v, t]) => box.appendChild(h("button", { type: "button", class: v === value ? "on" : "", dataset: { v }, onclick: () => { $$("button", box).forEach(b => b.classList.toggle("on", b.dataset.v === v)); box.value = v; onchange && onchange(v); } }, t)));
  box.value = value;
  return box;
}
function download(url) { const a = h("a", { href: url }); document.body.appendChild(a); a.click(); a.remove(); }
function downloadText(name, text, mime = "text/csv") {
  const url = URL.createObjectURL(new Blob([text], { type: mime + ";charset=utf-8" }));
  const a = h("a", { href: url, download: name }); document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 2000);
}
function applyBrand(b) {
  S.brand = b || S.brand;
  const r = document.documentElement.style;
  if (S.brand.red) r.setProperty("--red", S.brand.red);
  if (S.brand.blue) r.setProperty("--blue", S.brand.blue);
  if (S.brand.navy) r.setProperty("--navy", S.brand.navy);
  document.title = S.brand.app_name || "TDMS";
}
function applyTheme(t) { document.documentElement.dataset.theme = t === "dark" ? "dark" : "light"; }

/* small line icons (fixed, trusted markup) */
const ICONS = {
  mail: '<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="m4 7.5 8 6 8-6"/>',
  lock: '<rect x="4.5" y="10.5" width="15" height="10" rx="2.5"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/>',
  eye: '<path d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
  eyeoff: '<path d="M3 3l18 18"/><path d="M10.6 6a10 10 0 0 1 1.4-.1c6.4 0 10 6.1 10 6.1a17 17 0 0 1-3.3 4M6.4 7.5C3.8 9.3 2 12 2 12s3.6 6.5 10 6.5c1.5 0 2.9-.4 4.1-1"/><path d="M9.9 10a3 3 0 0 0 4.1 4.1"/>',
  shield: '<path d="M12 3 5 6v5.5c0 4.4 2.9 8 7 9.5 4.1-1.5 7-5.1 7-9.5V6l-7-3Z"/><path d="m9 12 2.2 2.2L15.5 10"/>',
  warn: '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5M12 16.5v.01"/>',
  info2: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.8v.01"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  open: '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4"/>',
  star: '<path d="m12 3.5 2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9 6.8 19.6l1-5.8L3.5 9.7l5.9-.9L12 3.5Z"/>',
  up: '<path d="m6 15 6-6 6 6"/>',
  down: '<path d="m6 9 6 6 6-6"/>',
  checkall: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/>',
  more: '<circle cx="5" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="19" cy="12" r="1.4"/>',
  sliders: '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
  sidebar: '<rect x="3.5" y="4.5" width="17" height="15" rx="2.5"/><path d="M9.5 4.5v15"/>',
  download: '<path d="M12 4v11M7.5 10.5 12 15l4.5-4.5M5 19h14"/>',
  restore: '<path d="M4 9h11a5 5 0 0 1 0 10H8"/><path d="m8 5-4 4 4 4"/>',
  file: '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/>',
  db: '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/>',
  folder: '<path d="M3.5 7a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2V7Z"/>',
  calendar: '<rect x="4" y="5.5" width="16" height="14.5" rx="2.5"/><path d="M8 3.5v4M16 3.5v4M4 10h16"/>',
  user: '<circle cx="12" cy="8.5" r="3.5"/><path d="M5 20c.6-3.6 3.5-5.5 7-5.5s6.4 1.9 7 5.5"/>',
  users: '<circle cx="9" cy="9" r="3"/><path d="M3.5 19c.5-3 2.7-4.6 5.5-4.6s5 1.6 5.5 4.6"/><circle cx="17" cy="9.5" r="2.4"/><path d="M16.5 14.5c2.4 0 4 1.3 4.5 3.7"/>',
  layers: '<path d="m12 4 8 4.5-8 4.5-8-4.5L12 4Z"/><path d="m4 12.5 8 4.5 8-4.5M4 16.5 12 21l8-4.5"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  upload: '<path d="M12 16V5M7.5 9.5 12 5l4.5 4.5M5 19h14"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-14.5-3.5L4 9M4 4v5h5M4 13a8 8 0 0 0 14.5 3.5L20 15M20 20v-5h-5"/>',
  link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
  edit: '<path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16v4Z"/>',
  pdf: '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5M9.5 15h5M9.5 18h3"/>'
};
function svgIcon(name, size) {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("fill", "none"); s.setAttribute("stroke", "currentColor"); s.setAttribute("stroke-width", "1.8"); s.setAttribute("stroke-linecap", "round"); s.setAttribute("stroke-linejoin", "round");
  if (size) { s.setAttribute("width", size); s.setAttribute("height", size); }
  s.innerHTML = ICONS[name] || "";
  return s;
}

/* ---------- building blocks used on every page ---------- */
function iconBtn(icon, label, fn, cls = "", dis = false, title = "") {
  return h("button", { class: "btn " + cls + (label ? "" : " sq"), onclick: e => { e.stopPropagation(); fn && fn(e); }, disabled: dis, title: title || label || "" }, icon ? svgIcon(icon, 16) : null, label ? h("span", {}, label) : null);
}
function pageHead(title, sub, ...actions) {
  return h("div", { class: "pagehead" }, h("div", { class: "grow" }, h("h1", {}, title), sub ? h("p", {}, sub) : null), h("div", { class: "row" }, actions));
}
function emptyState(icon, title, hint, ...actions) {
  return h("div", { class: "empty" }, h("div", { class: "ei" }, svgIcon(icon, 30)), h("div", { class: "et" }, title), hint ? h("div", { class: "eh" }, hint) : null, actions.length ? h("div", { class: "row", style: { justifyContent: "center", marginTop: "14px" } }, actions) : null);
}
function skeleton(rows = 8) {
  return h("div", { class: "skelbox" }, ...Array.from({ length: rows }, (_, i) => h("div", { class: "skelrow" }, h("i", { class: "skel", style: { width: "22px" } }), h("i", { class: "skel", style: { width: 30 + (i * 37) % 38 + "%" } }), h("i", { class: "skel", style: { width: "12%", marginLeft: "auto" } }))));
}
