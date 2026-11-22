/* TDMS web - document tabs and viewers, dashboard, users, activity, admin, profile */
"use strict";

/* ================================================================ document tabs ================================================================ */
function openDoc(d) {
  const doc = typeof d === "object" ? d : (S.docs.find(x => x.id === d) || { id: d, title: "Document " + d, type: "file" });
  if (!S.tabs.some(t => t.id === doc.id)) S.tabs.push({ id: doc.id, title: doc.title, type: doc.type });
  go("doc/" + doc.id);
}
function closeTab(id) {
  const i = S.tabs.findIndex(t => t.id === id); if (i < 0) return;
  S.tabs.splice(i, 1);
  if (S.route === "doc/" + id) go(S.tabs.length ? "doc/" + S.tabs[Math.min(i, S.tabs.length - 1)].id : "library"); else renderTabs();
}
function closeTabsFor(ids) { const set = new Set(ids); const was = S.route; S.tabs = S.tabs.filter(t => !set.has(t.id)); if (was.startsWith("doc/") && set.has(+was.slice(4))) go("library"); else renderTabs(); }
function refreshTabTitle(id, title) { const t = S.tabs.find(x => x.id === id); if (t) { t.title = title; renderTabs(); } }

async function renderViewer(root, id) {
  clear(root);
  root.appendChild(h("div", { class: "center muted" }, "Opening..."));
  let r, doc;
  try { [r, doc] = await Promise.all([api(`/api/docs/${id}/render`), api(`/api/docs/${id}`)]); }
  catch (e) { clear(root); root.appendChild(h("div", { class: "center" }, h("div", {}, h("h3", {}, "Cannot open this document"), h("p", { class: "muted" }, e.message), h("button", { class: "btn", onclick: () => closeTab(id) }, "Close tab")))); return; }
  doc = doc.doc;
  const tab = S.tabs.find(t => t.id === id); if (tab) { tab.title = doc.title; renderTabs(); }
  post(`/api/docs/${id}/open`).catch(() => { });
  const body = h("div", { class: "vbody" });
  const bar = h("div", { class: "vbar" }, h("h2", {}, doc.title), h("span", { class: "badge", style: { "--c": typeColor(doc.type) } }, doc.type_label), statusBadge(doc.status), h("span", { class: "spacer" }));
  const favBtn = h("button", { class: "btn", onclick: async () => { try { await post("/api/docs/fav", { ids: [id], on: !doc.fav }); doc.fav = !doc.fav; favBtn.textContent = doc.fav ? "\u2605 Favorite" : "\u2606 Favorite"; } catch (e) { toastErr(e); } } }, doc.fav ? "\u2605 Favorite" : "\u2606 Favorite");
  add(bar, favBtn, h("button", { class: "btn", onclick: () => download(`/files/${id}/download`) }, "Download"), h("button", { class: "btn ghost", onclick: () => closeTab(id) }, "Close"));
  const exactable = [".docx", ".xlsx", ".xlsm", ".pptx"].includes(r.ext) && S.exactOk;
  if (exactable) {
    const eb = h("button", { class: "btn navy" }, "Exact view (PDF)"); let exact = false;
    eb.onclick = () => { exact = !exact; eb.textContent = exact ? "Simple view" : "Exact view (PDF)"; clear(body); if (exact) body.appendChild(h("iframe", { src: `/files/${id}/exact.pdf` })); else drawKind(body, r, id); };
    bar.insertBefore(eb, favBtn);
  }
  clear(root); add(root, h("div", { class: "viewer" }, bar, body));
  drawKind(body, r, id);
}
function drawKind(body, r, id) {
  clear(body);
  const k = r.kind;
  if (k === "pdf") {
    body.appendChild(h("iframe", { src: `/files/${id}/inline#view=FitH` }));
    body.appendChild(h("div", { class: "muted small", style: { position: "absolute" } }));
  } else if (k === "image") imageViewer(body, `/files/${id}/inline`);
  else if (k === "video") body.appendChild(h("video", { src: `/files/${id}/inline`, controls: true, autoplay: false, preload: "metadata" }));
  else if (k === "audio") body.appendChild(h("div", { class: "center" }, h("div", {}, h("h3", {}, r.title), h("audio", { src: `/files/${id}/inline`, controls: true }))));
  else if (k === "html") { const p = h("div", { class: "docpage" }); p.innerHTML = r.html; body.appendChild(p); sanitizeInto(p); }
  else if (k === "table") tableViewer(body, r, id);
  else if (k === "text") textEditor(body, r, id);
  else if (k === "link") body.appendChild(h("div", { class: "center" }, h("div", {}, h("h3", {}, "Web link"), h("p", { class: "url" }, r.url || "(no address found)"), h("div", {}, r.url ? h("a", { class: "btn primary big", href: r.url, target: "_blank", rel: "noopener noreferrer" }, "Open the link") : ""))));
  else body.appendChild(h("div", { class: "center" }, h("div", {}, h("h3", {}, k === "office" ? "This older Office format cannot be shown in the browser" : "No preview for this file type"), h("p", { class: "muted" }, r.note || "Download it to open it on your computer."),
    h("div", { class: "row", style: { justifyContent: "center" } }, h("button", { class: "btn primary big", onclick: () => download(`/files/${id}/download`) }, "Download"), S.exactOk && k === "office" ? h("a", { class: "btn navy big", href: `/files/${id}/exact.pdf`, target: "_blank" }, "View as PDF") : ""))));
}
/* the server already escapes document text; this removes anything executable as a second safety net */
function sanitizeInto(el) { $$("script,iframe,object,embed,link,style", el).forEach(n => n.remove()); $$("*", el).forEach(n => [...n.attributes].forEach(a => { if (/^on/i.test(a.name) || /^(javascript|data):/i.test(a.value)) n.removeAttribute(a.name); })); }

function imageViewer(body, src) {
  const box = h("div", { class: "imgv" }), img = h("img", { src, alt: "", draggable: "false" });
  let sc = 1, tx = 0, ty = 0, fitSc = 1;
  const apply = () => { img.style.transform = `translate(${tx}px,${ty}px) scale(${sc})`; };
  const fit = () => { const w = box.clientWidth, hh = box.clientHeight, iw = img.naturalWidth || 1, ih = img.naturalHeight || 1; fitSc = Math.min(w / iw, hh / ih, 1); sc = fitSc; tx = (w - iw * sc) / 2; ty = (hh - ih * sc) / 2; apply(); };
  const zoomAt = (f, cx, cy) => { const ns = Math.max(0.05, Math.min(16, sc * f)); tx = cx - (cx - tx) * (ns / sc); ty = cy - (cy - ty) * (ns / sc); sc = ns; apply(); };
  const center = f => zoomAt(f, box.clientWidth / 2, box.clientHeight / 2);
  img.onload = fit;
  add(box, img, h("div", { class: "zb" }, h("button", { class: "btn sq", onclick: () => center(1.25) }, "+"), h("button", { class: "btn sq", onclick: () => center(0.8) }, "\u2212"), h("button", { class: "btn", onclick: fit }, "Fit"), h("button", { class: "btn", onclick: () => { sc = 1; tx = (box.clientWidth - img.naturalWidth) / 2; ty = (box.clientHeight - img.naturalHeight) / 2; apply(); } }, "100%")));
  box.addEventListener("wheel", e => { e.preventDefault(); const r = box.getBoundingClientRect(); zoomAt(Math.pow(1.0018, -e.deltaY * (e.ctrlKey ? 3 : 1)), e.clientX - r.left, e.clientY - r.top); }, { passive: false });
  const pts = new Map(); let d0 = 0;
  box.addEventListener("pointerdown", e => { if (e.target.closest(".zb")) return; box.setPointerCapture(e.pointerId); pts.set(e.pointerId, [e.clientX, e.clientY]); box.style.cursor = "grabbing"; if (pts.size === 2) { const [a, b] = [...pts.values()]; d0 = Math.hypot(a[0] - b[0], a[1] - b[1]); } });
  box.addEventListener("pointermove", e => {
    if (!pts.has(e.pointerId)) return; const old = pts.get(e.pointerId); pts.set(e.pointerId, [e.clientX, e.clientY]);
    if (pts.size === 1) { tx += e.clientX - old[0]; ty += e.clientY - old[1]; apply(); }
    else if (pts.size === 2) { const [a, b] = [...pts.values()], d1 = Math.hypot(a[0] - b[0], a[1] - b[1]), r = box.getBoundingClientRect(); if (d0) zoomAt(d1 / d0, (a[0] + b[0]) / 2 - r.left, (a[1] + b[1]) / 2 - r.top); d0 = d1; }
  });
  const up = e => { pts.delete(e.pointerId); box.style.cursor = "grab"; d0 = 0; };
  box.addEventListener("pointerup", up); box.addEventListener("pointercancel", up);
  box.addEventListener("dblclick", () => { if (Math.abs(sc - fitSc) < 0.01) { sc = 1; tx = (box.clientWidth - img.naturalWidth) / 2; ty = (box.clientHeight - img.naturalHeight) / 2; apply(); } else fit(); });
  body.appendChild(box); body.style.overflow = "hidden";
}
function tableViewer(body, r, id) {
  let hdr = !!r.header, data = r.sheets[0].rows;
  const wrap = h("div", { style: { overflow: "auto", height: "100%" } }), holder = h("div", {});
  const draw = () => {
    clear(holder);
    if (!data.length) return holder.appendChild(h("div", { class: "empty" }, "This sheet is empty."));
    const w = Math.max(...data.map(r_ => r_.length)), head = h("tr", {}, h("th", { class: "rn" }, ""));
    const first = hdr ? data[0] : null;
    for (let c = 0; c < w; c++) head.appendChild(h("th", {}, first ? (first[c] ?? "") : colName(c)));
    const tb = h("tbody"), rows = hdr ? data.slice(1) : data;
    rows.forEach((row, i) => { const tr = h("tr", {}, h("td", { class: "rn" }, i + 1)); for (let c = 0; c < w; c++) tr.appendChild(h("td", {}, row[c] ?? "")); tb.appendChild(tr); });
    holder.appendChild(h("table", { class: "sheet" }, h("thead", {}, head), tb));
  };
  const bar = h("div", { class: "sheetbar" }, h("label", { class: "row small" }, h("input", { type: "checkbox", checked: hdr, onchange: e => { hdr = e.target.checked; draw(); } }), "First row is the header"),
    h("span", { class: "muted small" }, `${data.length} row(s)` + (data.length >= 3000 ? " (first 3000 shown)" : "")));
  if (r.names && r.names.length > 1) r.names.forEach(n => bar.appendChild(h("button", { class: "chip" + (n === r.sheet ? " on" : ""), onclick: async () => { try { const x = await api(`/api/docs/${id}/render?sheet=${encodeURIComponent(n)}`); r = x; data = x.sheets[0].rows; $$(".chip", bar).forEach(c => c.classList.toggle("on", c.textContent === n)); draw(); } catch (e) { toastErr(e); } } }, n)));
  bar.appendChild(h("button", { class: "btn", style: { marginLeft: "auto" }, onclick: () => { const q = s => '"' + String(s ?? "").replace(/"/g, '""') + '"'; downloadText((r.title || "sheet") + ".csv", "\ufeff" + data.map(x => x.map(q).join(",")).join("\r\n")); } }, "Save as CSV"));
  add(wrap, holder, bar); body.appendChild(wrap); draw();
}
function colName(i) { let s = ""; i++; while (i > 0) { const m = (i - 1) % 26; s = String.fromCharCode(65 + m) + s; i = Math.floor((i - 1) / 26); } return s; }
function textEditor(body, r, id) {
  const ta = h("textarea", { class: "editor", spellcheck: "false", readonly: !r.editable }, r.text); ta.value = r.text;
  const save = async () => { try { await api(`/api/docs/${id}/text`, { method: "PUT", body: { text: ta.value } }); toast("Saved.", "ok"); } catch (e) { toastErr(e); } };
  ta.addEventListener("keydown", e => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); if (r.editable) save(); } });
  body.style.display = "flex"; body.style.flexDirection = "column";
  add(body, h("div", { class: "sheetbar", style: { position: "static", borderTop: 0, borderBottom: "1px solid var(--line)" } }, r.editable ? h("button", { class: "btn primary", onclick: save }, "Save  (Ctrl+S)") : h("span", { class: "muted small" }, "Read only - you did not add this document"), h("span", { class: "muted small" }, ta.value.length + " characters")), ta);
}

/* ================================================================ dashboard ================================================================ */
const TILE_COLORS = { docs: "var(--red)", size: "#2E6DB4", folders: "#D4A017", week: "#1D8348", mine: "#8E44AD", fav: "#F2B01E", versions: "#0097A7", trash: "#E0713F", users: "#3F51B5", pending: "#F28C1E" };
let _dash = null;
async function renderDashboard(root) {
  clear(root);
  const wrap = h("div", {}); root.appendChild(wrap); _dash = wrap;
  let d; try { d = await api("/api/dashboard"); } catch (e) { return toastErr(e); }
  if (_dash !== wrap) return;
  const chart = (name, hh, extra = "") => h("img", { class: "chartimg", dataset: { chart: name, h: hh, extra }, alt: "" });
  const docTable = (rows, cols2) => !rows.length ? h("div", { class: "muted small", style: { padding: "10px 4px" } }, "Nothing here yet.") :
    h("table", { class: "mini" }, h("tbody", {}, ...rows.map(x => h("tr", { class: x.late ? "late" : "", onclick: () => openDoc(x) }, h("td", {}, fileIcon(x.type, 18), x.title), ...cols2(x).map(c => h("td", { class: "muted" }, c))))));
  add(wrap,
    h("div", { class: "tiles" }, ...d.tiles.map(t => h("div", { class: "card tile", style: { "--c": TILE_COLORS[t.key] || "var(--blue)" } }, h("div", { class: "bar" }), h("div", { class: "v" }, String(t.value)), h("div", { class: "l" }, t.label), h("div", { class: "s" }, t.sub)))),
    h("div", { class: "grid3" }, h("div", { class: "card" }, h("h3", {}, "Recently opened by you"), docTable(d.opened, x => [x.cat])), h("div", { class: "card" }, h("h3", {}, "Your favorites"), docTable(d.favorites, x => [x.cat])),
      h("div", { class: "card" }, h("h3", {}, "Most opened"), docTable(d.most, x => [x.opens + "x"]))),
    h("div", { class: "grid2" }, h("div", { class: "card" }, h("h3", {}, "Uploads in the last 14 days"), chart("uploads", 190)),
      h("div", { class: "card" }, h("h3", {}, "Documents by type"), h("div", { class: "row", style: { alignItems: "center" } }, chart("types", 190, "square"), h("div", { class: "legend" }, ...d.types.map(t => h("div", {}, h("i", { style: { background: t.color } }), `${t.label}  (${t.n})`)))))),
    h("div", { class: "grid2" }, h("div", { class: "card" }, h("h3", {}, "Weekly trend (last 12 weeks)"), chart("trend", 190)), h("div", { class: "card" }, h("h3", {}, "Storage by file type"), chart("storage", 190))),
    h("div", { class: "grid2" }, h("div", { class: "card" }, h("h3", {}, "Top folders"), chart("folders", 190)), h("div", { class: "card" }, h("h3", {}, "Top contributors"), chart("people", 190))),
    h("div", { class: "grid2" }, h("div", { class: "card" }, h("h3", {}, "Recently added"), docTable(d.recent, x => [x.cat, x.who, fmtDate(x.created)])), h("div", { class: "card" }, h("h3", {}, "Largest files"), docTable(d.largest, x => [x.cat, fmtSize(x.size)]))),
    h("div", { class: "grid2" }, h("div", { class: "card" }, h("h3", {}, "Review due in the next 30 days"), docTable(d.review, x => [(x.late ? "overdue  " : "") + x.review, x.status])), h("div", { class: "card" }, h("h3", {}, "Documents by status"), chart("status", 190))),
    d.activity ? h("div", { class: "card" }, h("h3", {}, "Recent activity"), h("table", { class: "mini" }, h("tbody", {}, ...d.activity.map(a => h("tr", { style: { cursor: "default" } }, h("td", { class: "muted" }, fmtDate(a.ts)), h("td", {}, a.user), h("td", {}, a.action + "   " + a.detail)))))) : null);
  layoutCharts(wrap, d.stamp);
}
function layoutCharts(wrap, stamp) {
  const draw = () => $$("img[data-chart]", wrap).forEach(img => {
    const box = img.parentElement, sq = img.dataset.extra === "square", hh = +img.dataset.h;
    const w = sq ? hh : Math.max(200, Math.floor(box.clientWidth || 400));
    const key = `${w}x${hh}-${theme()}`; if (img.dataset.key === key) return; img.dataset.key = key;
    img.src = `/chart/${img.dataset.chart}.png?w=${w}&h=${hh}&theme=${theme()}&t=${encodeURIComponent(JSON.stringify(stamp))}`;
    if (sq) { img.style.width = hh + "px"; }
  });
  requestAnimationFrame(draw);
  if (wrap._ro) wrap._ro.disconnect();
  wrap._ro = new ResizeObserver(debounce(draw, 200)); wrap._ro.observe(wrap);
}

/* ================================================================ users ================================================================ */
async function renderUsers(root) {
  clear(root);
  let r; try { r = await api("/api/users"); } catch (e) { return toastErr(e); }
  const pending = r.users.filter(u => u.pending).length;
  const act = (label, fn, cls = "") => h("button", { class: "btn " + cls, style: { marginRight: "4px" }, onclick: fn }, label);
  const run = (path, body, msg) => async () => { try { await post(path, body); toast(msg, "ok"); renderUsers(root); refreshBadges(); } catch (e) { toastErr(e); } };
  const rows = r.users.map(u => h("tr", {}, h("td", {}, avatar(u.id, 34, "&v=" + (u.has_photo ? 1 : 0))), h("td", {}, h("b", {}, u.name), h("div", { class: "muted small" }, u.email || u.username)), h("td", {}, "#" + (u.emp_id || "-")), h("td", {}, u.dept),
    h("td", {}, h("span", { class: "badge", style: { "--c": u.role === "admin" ? "var(--red)" : "#607D8B" } }, u.role === "admin" ? "ADMIN" : "USER")),
    h("td", {}, u.pending ? h("span", { class: "badge", style: { "--c": "#F28C1E" } }, "WAITING") : u.active ? h("span", { class: "badge", style: { "--c": "#1D8348" } }, "ACTIVE") : h("span", { class: "badge", style: { "--c": "#90A4AE" } }, "DISABLED")),
    h("td", {}, u.pending ? [act("Approve", run(`/api/users/${u.id}/approve`, {}, "Approved."), "primary"), act("Reject", async () => { if (await confirmDlg("Reject", `Reject the request from ${u.name}?`, "Reject", "danger")) run(`/api/users/${u.id}/reject`, {}, "Rejected.")(); })] :
      [act("Edit", () => profileDialog(u, () => renderUsers(root))), act("Reset password", () => resetPassword(u)), u.id === S.me.id ? "" : act(u.active ? "Disable" : "Enable", run(`/api/users/${u.id}/toggle`, {}, "Done.")),
        u.id === S.me.id ? "" : act("Delete", async () => { if (await confirmDlg("Delete user", `Delete ${u.name}? Their documents stay in the library.`, "Delete", "danger")) run(`/api/users/${u.id}/delete`, {}, "Deleted.")(); })])));
  add(root, h("div", { class: "card" }, h("div", { class: "row" }, h("h3", { style: { margin: 0 } }, `Users  (${r.users.length})`), pending ? h("span", { class: "badge", style: { "--c": "#F28C1E" } }, pending + " waiting for approval") : "", h("span", { class: "spacer" }), h("button", { class: "btn primary", onclick: () => addUserDialog(() => renderUsers(root)) }, "+ Add user")),
    h("div", { style: { overflow: "auto", marginTop: "10px" } }, h("table", { class: "table2" }, h("thead", {}, h("tr", {}, ...["", "Name", "Employee ID", "Department", "Role", "Status", ""].map(x => h("th", {}, x)))), h("tbody", {}, ...rows)))));
}
function addUserDialog(done) {
  const f = { email: h("input", { class: "inp", placeholder: "name@company.com" }), name: h("input", { class: "inp" }), emp: h("input", { class: "inp" }), dept: h("input", { class: "inp" }), pw: h("input", { class: "inp", type: "password" }), role: select([["user", "User"], ["admin", "Administrator"]], "user") };
  dialog({ title: "Add user", width: 520, body: [field("EMAIL ID (used to sign in)", f.email), field("FULL NAME", f.name), h("div", { class: "form2" }, field("EMPLOYEE ID", f.emp), field("DEPARTMENT", f.dept)), h("div", { class: "form2" }, field("PASSWORD", f.pw, `At least ${S.brand.min_password} characters`), field("ROLE", f.role))],
    buttons: [{ text: "Cancel" }, { text: "Add user", kind: "primary", fn: async () => { await post("/api/users", { email: f.email.value, name: f.name.value, emp_id: f.emp.value, dept: f.dept.value, password: f.pw.value, role: f.role.value }); toast("User added.", "ok"); done(); } }] });
}
function resetPassword(u) {
  const pw = h("input", { class: "inp", type: "text", placeholder: "New password" });
  dialog({ title: `Reset password - ${u.name}`, width: 440, body: [field("NEW PASSWORD", pw, `At least ${S.brand.min_password} characters. Tell them to change it after signing in.`)], buttons: [{ text: "Cancel" }, { text: "Reset", kind: "primary", fn: async () => { await post(`/api/users/${u.id}/reset`, { password: pw.value }); toast("Password reset.", "ok"); } }] });
}

/* ================================================================ activity ================================================================ */
async function renderActivity(root) {
  clear(root);
  const tb = h("tbody"), q = h("input", { type: "search", placeholder: "Search the log...", oninput: debounce(load, 250) }), count = h("span", { class: "muted small" });
  let rows = [];
  async function load() {
    try { rows = (await api("/api/admin/activity?q=" + encodeURIComponent(q.value.trim()))).rows; } catch (e) { return toastErr(e); }
    clear(tb); rows.forEach(r => tb.appendChild(h("tr", {}, h("td", { class: "muted", style: { whiteSpace: "nowrap" } }, fmtDate(r.ts)), h("td", {}, r.user), h("td", {}, r.action), h("td", { class: "muted" }, r.detail)))); count.textContent = rows.length + " entries";
  }
  add(root, h("div", { class: "card" }, h("div", { class: "row" }, h("h3", { style: { margin: 0 } }, "Activity"), h("div", { class: "search" }, q), count, h("span", { class: "spacer" }),
    h("button", { class: "btn", onclick: () => { const c = s => '"' + String(s ?? "").replace(/"/g, '""') + '"'; downloadText("TDMS_activity.csv", "\ufeff" + ["Time,User,Action,Detail", ...rows.map(r => [r.ts, r.user, r.action, r.detail].map(c).join(","))].join("\r\n")); } }, "Export CSV")),
    h("div", { style: { overflow: "auto", marginTop: "10px" } }, h("table", { class: "table2" }, h("thead", {}, h("tr", {}, ...["Time", "User", "Action", "Detail"].map(x => h("th", {}, x)))), tb))));
  load();
}

/* ================================================================ admin ================================================================ */
async function renderAdmin(root) {
  clear(root);
  let s, info; try { [s, info] = await Promise.all([api("/api/admin/settings"), api("/api/admin/info")]); } catch (e) { return toastErr(e); }
  const inp = (k, ph = "") => h("input", { class: "inp", value: s[k], placeholder: ph });
  const col = k => { const c = h("input", { type: "color", value: s[k] }), t = h("input", { class: "inp", value: s[k], style: { width: "110px" }, oninput: () => { if (/^#[0-9a-f]{6}$/i.test(t.value)) c.value = t.value; } }); c.oninput = () => { t.value = c.value; }; const w = h("div", { class: "coltile" }, c, t); w.get = () => t.value; return w; };
  const f = { app_name: inp("app_name"), short_name: inp("short_name"), company: inp("company"), subtitle: inp("subtitle"), tagline: inp("tagline"), brand_red: col("brand_red"), brand_blue: col("brand_blue"), brand_navy: col("brand_navy"),
    login_bg: select([["ocean", "Ocean"], ["midnight", "Midnight"], ["sunrise", "Sunrise"], ["slate", "Slate"]], s.login_bg), email_domain: inp("email_domain", "addverb.com"), min_password: inp("min_password"), max_mb: inp("max_mb", "0 = no limit"), trash_days: inp("trash_days") };
  const sw = (k, label) => { const c = h("input", { type: "checkbox", checked: s[k] === "1" }); c.get = () => (c.checked ? "1" : "0"); return [h("label", { class: "sw" }, c, label), c]; };
  const [swSign, cSign] = sw("allow_signup", "Allow people to create their own account"), [swAppr, cAppr] = sw("require_approval", "New accounts must be approved by an admin");
  const save = async () => {
    const body = {}; for (const [k, v] of Object.entries(f)) body[k] = v.get ? v.get() : v.value; body.allow_signup = cSign.get(); body.require_approval = cAppr.get();
    try { const r = await post("/api/admin/settings", body); applyBrand(r.brand); renderShell(); toast("Settings saved.", "ok"); } catch (e) { toastErr(e); }
  };
  const logoIn = h("input", { type: "file", accept: "image/*", style: { display: "none" }, onchange: async () => { const fd = new FormData(); fd.append("file", logoIn.files[0]); try { await api("/api/admin/logo", { method: "POST", form: fd }); toast("Logo changed.", "ok"); S.logoBust = Date.now(); renderShell(); } catch (e) { toastErr(e); } } });
  add(root, h("div", { class: "grid2e" },
    h("div", { class: "card" }, h("h3", {}, "Branding"), field("APPLICATION NAME", f.app_name), h("div", { class: "form2" }, field("SHORT NAME", f.short_name), field("COMPANY", f.company)), field("SUBTITLE", f.subtitle), field("TAGLINE", f.tagline),
      h("div", { class: "form2" }, field("ACCENT COLOUR", f.brand_red), field("BLUE", f.brand_blue)), h("div", { class: "form2" }, field("NAVY (table headings)", f.brand_navy), field("LOGIN BACKGROUND", f.login_bg)),
      h("div", { class: "row", style: { marginTop: "14px" } }, h("button", { class: "btn", onclick: () => logoIn.click() }, "Change logo..."), h("button", { class: "btn ghost", onclick: async () => { await api("/api/admin/logo", { method: "DELETE" }); toast("Logo reset.", "ok"); S.logoBust = Date.now(); renderShell(); } }, "Use the default logo"), logoIn)),
    h("div", { class: "card" }, h("h3", {}, "Rules"), swSign, swAppr, field("ONLY THIS EMAIL DOMAIN CAN SIGN UP", f.email_domain, "Leave empty to allow any domain"), h("div", { class: "form2" }, field("MINIMUM PASSWORD LENGTH", f.min_password), field("MAX FILE SIZE (MB)", f.max_mb)), field("KEEP DELETED DOCUMENTS (DAYS)", f.trash_days))),
    h("div", { class: "row", style: { margin: "0 0 12px" } }, h("button", { class: "btn primary big", onclick: save }, "Save settings")),
    h("div", { class: "grid2e" },
      h("div", { class: "card" }, h("h3", {}, "Share with your team"), h("p", { class: "muted" }, "Team members open one of these addresses in their browser (same network or VPN):"), ...info.urls.map(u => h("div", {}, h("span", { class: "url" }, u))), info.urls.length ? "" : h("div", { class: "muted" }, "No network address found."),
        h("p", { class: "muted small", style: { marginTop: "12px" } }, "From outside the office use a secure tunnel (Cloudflare Tunnel or Tailscale) - see README_WEB.txt.")),
      h("div", { class: "card" }, h("h3", {}, "Server"), h("table", { class: "mini" }, h("tbody", {}, ...[["Version", info.version], ["Python", info.python], ["Data folder", info.data], ["Disk free", info.disk_free], ["PDF thumbnails", info.pdf_thumbs ? "on" : "off (pip install pymupdf)"], ["Exact Office view", info.office ? "available (needs Microsoft Office)" : "only on a Windows server with Office"]].map(([a, b]) => h("tr", { style: { cursor: "default" } }, h("td", { class: "muted" }, a), h("td", {}, b))))),
        h("div", { class: "row", style: { marginTop: "12px" } }, h("button", { class: "btn", onclick: () => download("/api/admin/backup") }, "Download database backup")))));
}

/* ================================================================ profile and settings ================================================================ */
function profileDialog(user, done) {
  const self = !user || user.id === S.me.id, u = user || S.me;
  const f = { name: h("input", { class: "inp", value: u.name }), email: h("input", { class: "inp", value: u.email }), emp: h("input", { class: "inp", value: u.emp_id, disabled: !isAdmin() }), dept: h("input", { class: "inp", value: u.dept }), des: h("input", { class: "inp", value: u.designation }), phone: h("input", { class: "inp", value: u.phone }),
    role: select([["user", "User"], ["admin", "Administrator"]], u.role) };
  f.role.disabled = !isAdmin() || self;
  const photoIn = h("input", { type: "file", accept: "image/*", style: { display: "none" }, onchange: async () => { const fd = new FormData(); fd.append("file", photoIn.files[0]); try { await api(`/api/users/${u.id}/photo`, { method: "POST", form: fd }); toast("Photo saved.", "ok"); if (self) { await reloadMe(); } if (done) done(); } catch (e) { toastErr(e); } } });
  const save = async () => { const r = await post(`/api/users/${u.id}`, { name: f.name.value, email: f.email.value, emp_id: f.emp.value, dept: f.dept.value, designation: f.des.value, phone: f.phone.value, role: f.role.value }); if (self) { S.me = r.user; renderShell(); } toast("Profile saved.", "ok"); if (done) done(); };
  const prof = h("div", {}, h("div", { class: "row", style: { margin: "6px 0" } }, avatar(u.id, 64, "&v=" + Date.now()), h("button", { class: "btn", onclick: () => photoIn.click() }, "Change photo..."), h("button", { class: "btn ghost", onclick: async () => { await api(`/api/users/${u.id}/photo`, { method: "DELETE" }); if (self) await reloadMe(); if (done) done(); toast("Photo removed.", "ok"); } }, "Remove"), photoIn),
    field("FULL NAME", f.name), field("EMAIL ID", f.email), h("div", { class: "form2" }, field("EMPLOYEE ID", f.emp, isAdmin() ? "" : "Only an admin can change this"), field("DEPARTMENT", f.dept)), h("div", { class: "form2" }, field("DESIGNATION", f.des), field("PHONE", f.phone)), isAdmin() && !self ? field("ROLE", f.role) : "");
  if (!self) return dialog({ title: "Profile - " + u.name, width: 560, body: prof, buttons: [{ text: "Cancel" }, { text: "Save", kind: "primary", fn: save }] });
  const cur = h("input", { class: "inp", type: "password" }), n1 = h("input", { class: "inp", type: "password" }), n2 = h("input", { class: "inp", type: "password" });
  const q = select(S.questions, S.questions[0]), ans = h("input", { class: "inp" }), qpw = h("input", { class: "inp", type: "password" });
  const security = h("div", {}, h("h4", { style: { margin: "6px 0 0" } }, "Change password"), field("CURRENT PASSWORD", cur), h("div", { class: "form2" }, field("NEW PASSWORD", n1, `At least ${S.brand.min_password} characters`), field("REPEAT NEW PASSWORD", n2)),
    h("button", { class: "btn primary", style: { marginTop: "10px" }, onclick: async e => { try { if (n1.value !== n2.value) throw new Error("The two new passwords are not the same."); await post("/api/password", { current: cur.value, new: n1.value }); toast("Password changed.", "ok"); cur.value = n1.value = n2.value = ""; } catch (x) { toastErr(x); } } }, "Change password"),
    h("h4", { style: { margin: "22px 0 0" } }, "Security question (to recover a forgotten password)"), field("QUESTION", q), field("ANSWER", ans), field("YOUR PASSWORD", qpw),
    h("button", { class: "btn", style: { marginTop: "10px" }, onclick: async () => { try { await post("/api/question", { question: q.value, answer: ans.value, password: qpw.value }); S.me.has_question = true; toast("Security question saved.", "ok"); ans.value = qpw.value = ""; } catch (x) { toastErr(x); } } }, "Save question"));
  const themeP = pills([["light", "Light"], ["dark", "Dark"]], theme(), v => { applyTheme(v); savePrefs({ theme: v }); renderShell(); }), dfmt = select([["ISO", "2026-10-30 14:05"], ["DMY", "30-10-2026 14:05"], ["Long", "30 Oct 2026, 14:05"]], S.prefs.datefmt || "ISO");
  dfmt.onchange = () => { savePrefs({ datefmt: dfmt.value }); route(); };
  const cc = h("input", { type: "checkbox", checked: compact(), onchange: () => { savePrefs({ compact: cc.checked ? "1" : "0" }); route(); } });
  const colorsBox = h("div", { class: "form2" }, ...Object.entries(S.types).map(([k, t]) => { const i = h("input", { type: "color", value: typeColor(k), style: { width: "42px", height: "30px", border: "1px solid var(--line)", borderRadius: "6px", padding: "1px", background: "var(--input)" }, onchange: () => { savePrefs({ ["fc_" + k]: i.value }); } }); return h("label", { class: "row", style: { margin: "4px 0" } }, i, t.label); }));
  const prefs = h("div", {}, field("THEME", themeP), field("DATE FORMAT", dfmt), h("label", { class: "sw" }, cc, "Compact rows in the document list"), h("h4", { style: { margin: "18px 0 6px" } }, "File type colours"), colorsBox,
    h("button", { class: "btn ghost", style: { marginTop: "8px" }, onclick: async () => { const reset = {}; Object.keys(S.types).forEach(k => reset["fc_" + k] = ""); await savePrefs(reset); toast("Colours reset.", "ok"); route(); } }, "Reset colours"));
  const panes = { Profile: prof, Security: security, Preferences: prefs };
  const box = h("div", {}), tabs = pills(Object.keys(panes).map(k => [k, k]), "Profile", k => { clear(box); box.appendChild(panes[k]); });
  box.appendChild(prof);
  dialog({ title: "My profile and settings", width: 600, body: [h("div", { style: { marginBottom: "6px" } }, tabs), box], buttons: [{ text: "Close" }, { text: "Save profile", kind: "primary", fn: async () => { await save(); return true; } }] });
}
async function reloadMe() { const r = await api("/api/me"); S.me = r.user; S.prefs = r.prefs; renderShell(); }
function mustChangeDialog() {
  const cur = h("input", { class: "inp", type: "password", autocomplete: "current-password" }), n1 = h("input", { class: "inp", type: "password" }), n2 = h("input", { class: "inp", type: "password" });
  const d = dialog({ title: "Set a new password", width: 460, body: [h("p", { class: "muted" }, "This account still uses the starting password. Please choose your own password now."), field("CURRENT PASSWORD", cur), field("NEW PASSWORD", n1, `At least ${S.brand.min_password} characters`), field("REPEAT NEW PASSWORD", n2)],
    buttons: [{ text: "Later" }, { text: "Change password", kind: "primary", fn: async () => { if (n1.value !== n2.value) throw new Error("The two new passwords are not the same."); await post("/api/password", { current: cur.value, new: n1.value }); toast("Password changed.", "ok"); S.mustChange = false; } }] });
}
