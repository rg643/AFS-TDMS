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
  const t = h("div", { class: "toast " + (kind || "") }, msg);
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
    title ? h("div", { class: "hd" }, title) : null, h("div", { class: "bd" }, body, err), h("div", { class: "ft" }));
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
