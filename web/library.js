/* TDMS web - Library page */
"use strict";
const L = { root: null };           // references to the library's parts
const COLS = [["type", "Type", "type"], ["status", "Status", "status"], ["cat", "Folder", "cat"], ["size", "Size", "size"], ["by", "Added by", "by"], ["added", "Added", "added"]];
const VIEWS = [["uploads", "My uploads"], ["folder", "Selected folder"], ["all", "All documents"], ["favorites", "My favorites"], ["mine", "Added by me"], ["recent", "Recent (last 30 days)"], ["bin", "Recycle bin"]];
const ORDERS = [["My order (use up / down)", "pos", false], ["Name A-Z", "title", false], ["Name Z-A", "title", true], ["Newest first", "added", true], ["Oldest first", "added", false],
  ["Largest first", "size", true], ["Type", "type", false], ["Status", "status", false]];
const cols = () => (S.prefs.cols || "type,status,cat,size,by,added").split(",").filter(c => COLS.some(x => x[0] === c));
const compact = () => S.prefs.compact === "1";
const flag = (k, d = "0") => (S.prefs[k] ?? d) === "1";

/* ---------- data ---------- */
async function loadFolders() {
  const r = await api("/api/folders");
  S.folders = r.folders; S.bin = r.bin;
}
const childrenOf = pid => S.folders.filter(f => (f.parent_id || null) === (pid || null));
const folderById = id => S.folders.find(f => f.id === id);
function subtreeIds(id) { const out = [id]; for (const c of childrenOf(id)) out.push(...subtreeIds(c.id)); return out; }
function folderPath(id) { const out = []; let f = folderById(id); while (f) { out.unshift(f); f = f.parent_id ? folderById(f.parent_id) : null; } return out; }

async function loadDocs() {
  if (S.view === "folder" && !S.cat) { S.docs = []; S.total = 0; S.sel.clear(); return; }
  const p = new URLSearchParams({ view: S.view, order: S.order, desc: S.desc ? 1 : 0, type: S.chip, q: S.q });
  if (S.cat) p.set("cat", S.cat);
  const r = await api("/api/docs?" + p);
  S.docs = r.docs; S.total = r.total; S.stamp = r.stamp;
  const ids = new Set(S.docs.map(d => d.id));
  for (const i of [...S.sel]) if (!ids.has(i)) S.sel.delete(i);
}
async function refreshLibrary(rebuildTree = true) {
  try { await Promise.all([loadFolders(), loadDocs()]); } catch (e) { return toastErr(e); }
  if (L.root && L.root.isConnected) { if (rebuildTree) renderTree(); renderToolbar(); renderList(); }
}
const selDocs = () => S.docs.filter(d => S.sel.has(d.id));
const selIds = () => [...S.sel];

/* ---------- page ---------- */
function renderLibrary(root) {
  clear(root);
  L.root = root;
  const hidden = flag("folders_hidden");
  L.folders = h("div", { class: "card folders" + (hidden ? " hidden" : "") });
  L.tree = h("div", { class: "tree" });
  L.bin = h("div", { class: "binrow" + (isViewer() ? " hidden" : ""), onclick: () => setView("bin") }, h("img", { src: "/icon/trash/t.png?s=44&c=E0713F", width: 22, height: 22 }), h("span", {}, "Recycle bin"), h("span", { class: "cnt" }));
  const manage = isAdmin() ? h("button", { class: "btn", onclick: e => { e.stopPropagation(); popMenu(folderMenuItems(), 0, 0, e.currentTarget); } }, "Manage \u25BE") :
    canWrite() ? iconBtn("folderplus", "New", e => popMenu(userFolderMenu(), 0, 0, e.currentTarget), "", false, "Create a folder or a subfolder") : null;
  add(L.folders, h("div", { class: "head" }, h("b", {}, "Folders"), manage), L.tree, L.bin);
  L.tbar = h("div", { class: "toolbar" });
  L.crumb = h("div", { class: "crumb" });
  L.count = h("span", { class: "muted small" });
  L.chips = h("div", { class: "chips" });
  L.table = h("div", { class: "tablewrap" });
  L.preview = h("div", { class: "preview hidden" });
  L.det = h("div", { class: "detline" });
  L.banner = h("div", {});
  L.main = h("div", { class: "card main" }, L.tbar, L.banner, h("div", { class: "crumbrow" }, L.crumb, L.count, L.chips), h("div", { class: "split" }, L.table, L.preview), L.det);
  add(root, h("div", { class: "lib" }, L.folders, L.main));
  setupDrop(L.main);
  renderChips();
  renderToolbar();
  refreshLibrary().then(() => {
    if (S.view === "folder" && !S.cat) {
      const last = +S.prefs.last_cat;
      const pick = folderById(last) ? last : (childrenOf(null)[0] || {}).id;
      if (pick) selectFolder(pick);
    }
  });
}

/* ---------- folder tree ---------- */
function renderTree() {
  clear(L.tree);
  const draw = (pid, depth) => {
    for (const f of childrenOf(pid)) {
      const kids = childrenOf(f.id), open = S.expanded.has(f.id);
      const on = S.view === "folder" && S.cat === f.id;
      const node = h("div", { class: "node" + (on ? " on" : ""), style: { paddingLeft: 4 + depth * 16 + "px" }, dataset: { id: f.id },
        onclick: () => selectFolder(f.id), oncontextmenu: e => { if (!isAdmin()) return; e.preventDefault(); selectFolder(f.id); popMenu(folderMenuItems(), e.clientX, e.clientY); } },
        h("span", { class: "arr", onclick: e => { e.stopPropagation(); if (open) S.expanded.delete(f.id); else S.expanded.add(f.id); renderTree(); } }, kids.length ? (open ? "\u25BC" : "\u25B6") : ""),
        folderIcon(f.color), h("span", { class: "nm", title: f.name }, f.name), f.count ? h("span", { class: "cnt" }, f.count) : null);
      L.tree.appendChild(node);
      if (kids.length && open) draw(f.id, depth + 1);
    }
  };
  draw(null, 0);
  const n = $(".cnt", L.bin); n.textContent = S.bin ? S.bin : "";
  L.bin.classList.toggle("on", S.view === "bin");
  const on = $(".node.on", L.tree); if (on) on.scrollIntoView({ block: "nearest" });
}
function selectFolder(id) {
  for (const p of folderPath(id)) if (p.id !== id) S.expanded.add(p.id);
  S.view = "folder"; S.cat = id; clearSearch();
  S.sel.clear(); S.anchor = null;
  savePrefs({ last_cat: id });
  renderTree(); renderToolbar();
  if (L.table) { clear(L.table); L.table.appendChild(skeleton(7)); }
  loadDocs().then(renderList).catch(toastErr);
}
function clearSearch() { S.q = ""; S.prev = null; if (S.gs) S.gs.value = ""; }
/* the ONE search box (top of the page): searches all documents; clearing it returns to the folder you were in */
function setSearch(v) {
  v = (v || "").trim();
  if (v === S.q) return;
  if (v && !S.q) S.prev = { view: S.view, cat: S.cat };
  S.q = v;
  if (v) { S.view = "all"; S.cat = null; }
  else if (S.prev) { S.view = S.prev.view; S.cat = S.prev.cat; S.prev = null; if (S.view === "folder" && !S.cat) S.cat = +S.prefs.last_cat || null; }
  S.sel.clear(); S.anchor = null;
  if (S.route !== "library") { go("library"); return; }
  renderTree(); renderToolbar();
  if (L.table) { clear(L.table); L.table.appendChild(skeleton(6)); }
  loadDocs().then(renderList).catch(toastErr);
}
function setView(v) {
  clearSearch();
  S.view = v; S.sel.clear(); S.anchor = null; if (v !== "folder") S.cat = v === "bin" || v === "folder" ? null : S.cat;
  if (v !== "folder") S.cat = null;
  if (v === "folder" && !S.cat) S.cat = +S.prefs.last_cat || (childrenOf(null)[0] || {}).id;
  renderTree(); renderToolbar();
  loadDocs().then(renderList).catch(toastErr);
}
function userFolderMenu() {
  const f = S.cat && S.view === "folder" ? folderById(S.cat) : null;
  return [{ label: "New folder...", fn: () => newFolder(null) }, { label: "New subfolder...  (inside the selected one)", dis: !f, fn: () => newFolder(f.id) }];
}
function showMyUploads() { clearSearch(); S.view = "uploads"; S.cat = null; S.sel.clear(); if (S.route === "library" && L.root && L.root.isConnected) setView("uploads"); else go("library"); }
function folderMenuItems() {
  const f = S.cat && S.view === "folder" ? folderById(S.cat) : null;
  return [{ label: "New folder...", fn: () => newFolder(null) }, { label: "New subfolder...  (inside the selected one)", dis: !f, fn: () => newFolder(f.id) }, { sep: 1 },
    { label: "Rename...", dis: !f, fn: renameFolder }, { label: "Move up", dis: !f, fn: () => moveFolder(-1) }, { label: "Move down", dis: !f, fn: () => moveFolder(1) },
    { label: "Move into another folder...", dis: !f, fn: moveFolderInto }, { sep: 1 }, { label: "Folder colour...", dis: !f, fn: colorFolder }, { label: "Reset folder colour", dis: !f || !f.color, fn: () => api(`/api/folders/${f.id}`, { method: "PUT", body: { color: "" } }).then(() => refreshLibrary()).catch(toastErr) },
    { sep: 1 }, { label: "Delete folder and its documents...", dis: !f, fn: deleteFolder }];
}
async function newFolder(parent) {
  const name = await promptDlg(parent ? "New subfolder" : "New folder", "FOLDER NAME", "", "Create");
  if (!name) return;
  try { const r = await post("/api/folders", { name, parent_id: parent }); if (parent) S.expanded.add(parent); await refreshLibrary(); selectFolder(r.id); toast(`Folder "${name}" created.`, "ok"); } catch (e) { toastErr(e); }
}
async function renameFolder() {
  const f = folderById(S.cat); const name = await promptDlg("Rename folder", "FOLDER NAME", f.name, "Rename"); if (!name) return;
  try { await api(`/api/folders/${f.id}`, { method: "PUT", body: { name } }); await refreshLibrary(); } catch (e) { toastErr(e); }
}
async function moveFolder(delta) { try { await post(`/api/folders/${S.cat}/move`, { delta }); await refreshLibrary(); } catch (e) { toastErr(e); } }
async function moveFolderInto() {
  const f = folderById(S.cat), bad = new Set(subtreeIds(f.id));
  const dest = await pickFolder("Move folder into...", bad, true); if (dest === undefined) return;
  try { await api(`/api/folders/${f.id}`, { method: "PUT", body: { parent_id: dest } }); await refreshLibrary(); } catch (e) { toastErr(e); }
}
function colorFolder() {
  const f = folderById(S.cat), inp = h("input", { type: "color", value: f.color || "#F2B01E", style: { width: "100%", height: "80px", border: 0, background: "none" } });
  dialog({ title: "Folder colour", width: 360, body: inp, buttons: [{ text: "Cancel" }, { text: "Use colour", kind: "primary", fn: async () => { await api(`/api/folders/${f.id}`, { method: "PUT", body: { color: inp.value } }); await refreshLibrary(); } }] });
}
async function deleteFolder() {
  const f = folderById(S.cat), ids = subtreeIds(f.id), n = ids.reduce((a, i) => a + (folderById(i).count || 0), 0);
  const ok = await confirmDlg("Delete folder", `Delete the folder "${f.name}"` + (ids.length > 1 ? ` and its ${ids.length - 1} sub-folder(s)` : "") + `.\n` + (n ? `${n} document(s) inside move to the Recycle bin, where you can restore them.` : "It is empty."), "Delete folder", "danger");
  if (!ok) return;
  try { const r = await api(`/api/folders/${f.id}`, { method: "DELETE" }); S.cat = null; await refreshLibrary(); const first = childrenOf(null)[0]; if (first) selectFolder(first.id); toast(`Deleted ${r.folders} folder(s). ${r.docs} document(s) are in the Recycle bin.`, "ok"); } catch (e) { toastErr(e); }
}
/* choose a folder from a list (returns id, null for top level, undefined if cancelled) */
function pickFolder(title, exclude = new Set(), allowTop = false) {
  return new Promise(res => {
    let chosen = allowTop ? null : undefined, done = false;
    const box = h("div", { class: "tree", style: { maxHeight: "50vh" } });
    const draw = (pid, depth) => childrenOf(pid).forEach(f => {
      if (exclude.has(f.id)) return;
      const n = h("div", { class: "node", style: { paddingLeft: 6 + depth * 16 + "px" }, onclick: () => { chosen = f.id; $$(".node", box).forEach(x => x.classList.remove("on")); n.classList.add("on"); } }, folderIcon(f.color), h("span", { class: "nm" }, f.name));
      box.appendChild(n); draw(f.id, depth + 1);
    });
    if (allowTop) { const t = h("div", { class: "node on", onclick: () => { chosen = null; $$(".node", box).forEach(x => x.classList.remove("on")); t.classList.add("on"); } }, h("span", { class: "nm" }, "(top level)")); box.appendChild(t); }
    draw(null, 0);
    dialog({ title, width: 460, body: box, onclose: () => { if (!done) res(undefined); }, buttons: [{ text: "Cancel" }, { text: "Choose", kind: "primary", fn: d => { if (chosen === undefined) { d.err("Click a folder first."); return false; } done = true; res(chosen); } }] });
  });
}

/* ---------- toolbar ---------- */
function renderToolbar() {
  clear(L.tbar);
  const w = canWrite(), bin = S.view === "bin", one = S.sel.size === 1, any = S.sel.size > 0;
  const grp = (...b) => h("div", { class: "tgroup" }, ...b);
  const sep = () => h("span", { class: "vsep" });
  const rb = iconBtn("refresh", "Refresh", async () => { rb.classList.add("spin"); try { await refreshLibrary(); } finally { rb.classList.remove("spin"); } }, "", false, "Reload the folders and documents");
  add(L.tbar, iconBtn("sliders", "View", e => popMenu(viewMenuItems(), 0, 0, e.currentTarget), "", false, "Show, order, columns and layout"),
    iconBtn("sidebar", "Folders", () => { savePrefs({ folders_hidden: flag("folders_hidden") ? "0" : "1" }); L.folders.classList.toggle("hidden", flag("folders_hidden")); }, "", false, "Show / hide the folder panel"), rb,
    w ? null : h("span", { class: "rolepill", title: "Your account can read and download documents" }, svgIcon("eye", 14), "Read-only access"), h("span", { class: "spacer" }));
  if (!w) {
    add(L.tbar, iconBtn("open", "Open", () => selIds().forEach(openDoc), "navy", !any, "Open in a tab"), iconBtn("star", "", () => favSel(), "", !any, "Favorite on / off"), iconBtn("download", "Download", downloadSel, "", !any, "Download the selected documents"),
      iconBtn("checkall", "", selectAll, "", false, "Select all   (Ctrl+A)"), iconBtn("more", "", e => popMenu(moreItems(), 0, 0, e.currentTarget), "", false, "More"));
  } else if (S.view === "uploads") {
    add(L.tbar, iconBtn("open", "Open", () => selIds().forEach(openDoc), "navy", !any, "Open in a tab"), iconBtn("checkall", "", selectAll, "", false, "Select all"), iconBtn("trash", "Cancel upload", () => deleteSel(false), "dangerline", !any, "Remove this upload"));
  } else if (bin) {
    add(L.tbar, iconBtn("restore", "Restore", restoreSel, "navy", !any), iconBtn("checkall", "", selectAll, "", false, "Select all"), iconBtn("trash", "Delete forever", () => deleteSel(true), "dangerline", !any), iconBtn("more", "", e => popMenu(moreItems(), 0, 0, e.currentTarget), "", false, "More"));
  } else {
    add(L.tbar, iconBtn("plus", "Add", e => popMenu(addItems(), 0, 0, e.currentTarget), "primary", false, "Upload files, a folder or a web link"), sep(),
      grp(iconBtn("open", "Open", () => selIds().forEach(openDoc), "", !any, "Open in a tab"), iconBtn("star", "", () => favSel(), "", !any, "Favorite on / off"), iconBtn("download", "", downloadSel, "", !any, "Download")),
      grp(iconBtn("up", "", () => moveSel(-1), "", !one && !any, "Move up   (Alt+Up)"), iconBtn("down", "", () => moveSel(1), "", !one && !any, "Move down   (Alt+Down)")),
      iconBtn("checkall", "", selectAll, "", false, "Select all   (Ctrl+A)"), sep(), iconBtn("trash", "Delete", () => deleteSel(false), "dangerline", !any, "Move to the Recycle bin   (Del)"), iconBtn("more", "", e => popMenu(moreItems(), 0, 0, e.currentTarget), "", false, "More actions"));
  }
}
function addItems() {
  const items = [{ label: "Upload files...", fn: () => pickFiles(false) }, { label: "Upload a folder with its files...", fn: () => pickFiles(true) }, { label: "Add a web link...", fn: addLink }];
  if (canWrite()) items.push({ sep: 1 }, { label: "New folder...", fn: () => newFolder(null) }, { label: "New subfolder...", dis: !(S.view === "folder" && S.cat), fn: () => newFolder(S.cat) });
  return items;
}
function viewMenuItems() {
  const items = [{ hd: "SHOW" }];
  for (const [v, t] of VIEWS) if (!(isViewer() && v === "bin") && !(v === "uploads" && S.me.role !== "user")) items.push({ label: t + (v === "uploads" && (S.counts.my_pending + S.counts.my_rejected) ? `   (${S.counts.my_pending + S.counts.my_rejected})` : ""), check: S.view === v, fn: () => setView(v) });
  items.push({ sep: 1 }, { hd: "ORDER BY" });
  for (const [t, k, d] of ORDERS) items.push({ label: t, check: S.order === k && S.desc === d, fn: () => { S.order = k; S.desc = d; savePrefs({ order_key: k, order_desc: d ? "1" : "0" }); loadDocs().then(renderList).catch(toastErr); } });
  items.push({ sep: 1 }, { hd: "COLUMNS" });
  for (const [k, t] of COLS) items.push({ label: t, check: cols().includes(k), fn: () => { const c = cols(); const n = c.includes(k) ? c.filter(x => x !== k) : COLS.map(x => x[0]).filter(x => c.includes(x) || x === k); savePrefs({ cols: n.join(",") || "type" }); renderList(); } });
  items.push({ sep: 1 }, { label: "Compact rows", check: compact(), fn: () => { savePrefs({ compact: compact() ? "0" : "1" }); renderList(); } },
    { label: "Details line under the list", check: flag("details", "1"), fn: () => { savePrefs({ details: flag("details", "1") ? "0" : "1" }); updateDetails(); } },
    { label: "Preview panel", check: flag("preview"), fn: () => { savePrefs({ preview: flag("preview") ? "0" : "1" }); renderPreview(); } });
  return items;
}
function moreItems() {
  const any = S.sel.size > 0, one = S.sel.size === 1;
  if (isViewer()) return [{ label: "Download", dis: !any, fn: downloadSel }, { label: "Save selected as ZIP", dis: !any, fn: zipSel }, { label: "Export this list (CSV)", fn: exportList }, { sep: 1 }, { label: "Select all   (Ctrl+A)", fn: selectAll }];
  if (S.view === "bin") return [{ label: "Restore", dis: !any, fn: restoreSel }, { label: "Delete forever", dis: !any, fn: () => deleteSel(true) }, isAdmin() ? { sep: 1 } : null, isAdmin() ? { label: "Empty the Recycle bin", fn: emptyBin } : null];
  return [{ label: "Details, status, tags...", dis: !one, fn: editDetails }, { label: "Rename   (F2)", dis: !one, fn: renameDoc }, { label: "Move to folder...", dis: !any, fn: moveDocs }, { label: "New version of this document...", dis: !one, fn: newVersion },
    { label: "Version history...", dis: !one, fn: versionHistory }, { sep: 1 }, { label: "Download", dis: !any, fn: downloadSel }, { label: "Save selected as ZIP", dis: !any, fn: zipSel }, { label: "Export this list (CSV)", fn: exportList },
    { label: "Select all   (Ctrl+A)", fn: selectAll }, { sep: 1 }, { label: "Move to Recycle bin   (Del)", dis: !any, fn: () => deleteSel(false) }];
}

/* ---------- crumb, chips ---------- */
function renderChips() {
  clear(L.chips);
  const labels = { all: "All", pdf: "PDF", doc: "Word", xls: "Excel", ppt: "PPT", img: "Images", vid: "Video", link: "Links" };
  for (const k of S.chips) L.chips.appendChild(h("button", { class: "chip" + (S.chip === k ? " on" : ""), style: { "--c": k === "all" ? "var(--navy)" : typeColor(k) }, onclick: () => { S.chip = k; renderChips(); loadDocs().then(renderList).catch(toastErr); } }, labels[k] || k));
}
function renderCrumb() {
  clear(L.crumb);
  if (S.view !== "folder") { L.crumb.appendChild(h("b", {}, (VIEWS.find(v => v[0] === S.view) || [])[1] || "Library")); }
  else {
    const path = S.cat ? folderPath(S.cat) : [];
    if (!path.length) L.crumb.appendChild(h("b", {}, "Library"));
    path.forEach((f, i) => { if (i) L.crumb.appendChild(h("i", {}, "\u203A")); L.crumb.appendChild(i === path.length - 1 && !S.q ? h("b", {}, f.name) : h("a", { onclick: () => selectFolder(f.id) }, f.name)); });
  }
  if (S.q) L.crumb.appendChild(h("span", { class: "muted", style: { marginLeft: "10px" } }, `-  "${S.q}"`));
}

/* ---------- list ---------- */
function renderBanner() {
  clear(L.banner);
  if (S.view === "uploads") return;
  const c = S.counts, bar = (kind, icon, text, label, fn) => L.banner.appendChild(h("div", { class: "banner " + kind }, svgIcon(icon, 18), h("span", { class: "grow" }, text), h("button", { class: "btn", onclick: fn }, label)));
  if (isAdmin() && c.pending_docs) bar("warn", "inbox", `${c.pending_docs} document(s) added by users are waiting for your approval.`, "Review now", () => go("approvals"));
  else if (S.me.role === "user") {
    if (c.my_pending) bar("warn", "clock", `${c.my_pending} of your uploads are waiting for admin approval. Others will see them after it is approved.`, "View my uploads", showMyUploads);
    if (c.my_rejected) bar("bad", "warn", `${c.my_rejected} of your uploads were rejected.`, "See why", showMyUploads);
  }
}
function renderList() {
  renderBanner(); renderCrumb(); renderChips();
  const c = cols(), bin = S.view === "bin";
  L.count.textContent = S.total > S.docs.length ? `${S.docs.length} of ${S.total} document(s)` : `${S.total} document(s)`;
  clear(L.table);
  if (!S.docs.length) {
    L.table.appendChild(S.view === "folder" && !S.cat ? emptyState("folder", "Choose a folder", "Pick a folder on the left to see its documents.") :
      S.q ? emptyState("search", "No matching documents", `Nothing matches "${S.q}". Try another word or clear the search.`) :
      S.chip !== "all" ? emptyState("file", "No documents of this type", "Choose All to see everything in this folder.") :
      bin ? emptyState("trash", "The Recycle bin is empty", "Deleted documents wait here before they are removed for good.") :
      emptyState("upload", "This folder is empty", "Drag files or a whole folder here, or use Add.", S.view === "folder" ? iconBtn("upload", "Upload files", () => pickFiles(false), "primary") : null));
    renderToolbar(); updateDetails(); renderPreview(); return;
  }
  const arrow = k => S.order === k ? h("span", { class: "ar" }, S.desc ? "\u25BC" : "\u25B2") : "";
  const head = h("tr", {}, h("th", { class: "ck" }, h("input", { type: "checkbox", onclick: e => { e.stopPropagation(); e.target.checked ? selectAll() : clearSel(); } })),
    h("th", { onclick: () => sortBy("title") }, "Name", arrow("title")),
    ...COLS.filter(x => c.includes(x[0])).map(([k, t, sk]) => h("th", { class: "c-" + k, onclick: () => sortBy(sk) }, k === "added" && bin ? "Deleted" : t, arrow(sk))));
  const body = h("tbody");
  for (const d of S.docs) {
    const tr = h("tr", { dataset: { id: d.id }, class: S.sel.has(d.id) ? "sel" : "", onclick: e => rowClick(e, d), ondblclick: () => bin ? null : openDoc(d.id), oncontextmenu: e => rowMenu(e, d) },
      h("td", { class: "ck" }, h("input", { type: "checkbox", checked: S.sel.has(d.id), onclick: e => { e.stopPropagation(); toggleSel(d.id); } })),
      h("td", { title: d.filename }, h("div", { class: "nm2" }, fileIcon(d.type, compact() ? 18 : 22), h("span", {}, d.fav ? h("span", { class: "star" }, "\u2605 ") : "", d.title, d.ver > 1 ? h("span", { class: "ver" }, "v" + d.ver) : ""))));
    for (const [k] of COLS.filter(x => c.includes(x[0]))) {
      const v = { type: d.type_label, status: d.appr ? apprBadge(d) : statusBadge(d.status), cat: d.cat, size: fmtSize(d.size), by: d.who, added: fmtDate(bin ? d.deleted_at : d.created) }[k];
      tr.appendChild(h("td", { class: "c-" + k }, v));
    }
    body.appendChild(tr);
  }
  L.table.appendChild(h("table", { class: "docs" + (compact() ? " compact" : "") }, h("thead", {}, head), body));
  const all = $("th.ck input", L.table); if (all) all.checked = S.sel.size > 0 && S.sel.size === S.docs.length;
  renderToolbar(); updateDetails(); renderPreview();
}
function sortBy(k) { if (S.order === k) S.desc = !S.desc; else { S.order = k; S.desc = false; } savePrefs({ order_key: S.order, order_desc: S.desc ? "1" : "0" }); loadDocs().then(renderList).catch(toastErr); }
function paintSel() {
  $$("tbody tr", L.table).forEach(tr => { const on = S.sel.has(+tr.dataset.id); tr.classList.toggle("sel", on); const cb = $("input", tr); if (cb) cb.checked = on; });
  const all = $("th.ck input", L.table); if (all) all.checked = S.sel.size > 0 && S.sel.size === S.docs.length;
  renderToolbar(); updateDetails(); renderPreview();
}
function rowClick(e, d) {
  if (e.shiftKey && S.anchor !== null) {
    const ids = S.docs.map(x => x.id), a = ids.indexOf(S.anchor), b = ids.indexOf(d.id);
    S.sel = new Set(ids.slice(Math.min(a, b), Math.max(a, b) + 1));
  } else if (e.ctrlKey || e.metaKey) { toggleSel(d.id, true); return; }
  else { S.sel = new Set([d.id]); S.anchor = d.id; }
  paintSel();
}
function toggleSel(id, quiet) { if (S.sel.has(id)) S.sel.delete(id); else S.sel.add(id); S.anchor = id; paintSel(); }
function selectAll() { S.sel = new Set(S.docs.map(d => d.id)); paintSel(); }
function clearSel() { S.sel.clear(); paintSel(); }
function rowMenu(e, d) {
  e.preventDefault();
  if (!S.sel.has(d.id)) { S.sel = new Set([d.id]); S.anchor = d.id; paintSel(); }
  const bin = S.view === "bin";
  popMenu(bin ? moreItems() : [{ label: "Open in tab", fn: () => selIds().forEach(openDoc) }, { label: "Favorite on / off", fn: () => favSel() }, { sep: 1 }, ...moreItems()], e.clientX, e.clientY);
}
function updateDetails() {
  const show = flag("details", "1");
  L.det.classList.toggle("hidden", !show);
  if (!show) return;
  const ds = selDocs();
  if (ds.length > 1) { L.det.textContent = `${ds.length} documents selected  |  ${fmtSize(ds.reduce((a, d) => a + d.size, 0))}`; return; }
  if (!ds.length) { L.det.textContent = ""; return; }
  const d = ds[0], bits = [d.title, d.type_label, `version ${d.ver}`, fmtSize(d.size), d.cat, `${d.who}, ${fmtDate(d.created)}`];
  if (d.appr === "pending") bits.push("waiting for admin approval"); if (d.appr === "rejected") bits.push("rejected: " + (d.appr_note || "no reason given"));
  if (d.status) bits.push(d.status); if (d.review) bits.push("review " + d.review); if (d.tags) bits.push("tags: " + d.tags); if (d.descr) bits.push(d.descr);
  L.det.textContent = bits.join("   |   ");
}
function renderPreview() {
  const show = flag("preview"), ds = selDocs();
  L.preview.classList.toggle("hidden", !show);
  if (!show) return;
  clear(L.preview);
  if (!ds.length) { L.preview.appendChild(h("div", { class: "muted" }, "Select a document to see its preview.")); return; }
  if (ds.length > 1) { L.preview.appendChild(h("h4", {}, `${ds.length} documents selected`)); L.preview.appendChild(h("div", { class: "muted" }, "Total size: " + fmtSize(ds.reduce((a, d) => a + d.size, 0)))); return; }
  const d = ds[0], img = h("img", { src: `/api/docs/${d.id}/thumb.png?w=260`, alt: "", onerror: e => { e.target.replaceWith(fileIcon(d.type, 72)); } });
  const dl = h("dl", {}, ...[["Size", fmtSize(d.size)], d.status ? ["Status", d.status] : null, d.review ? ["Review date", d.review] : null, ["Folder", d.cat], ["Version", d.ver], ["Added by", d.who], ["Added", fmtDate(d.created)], d.tags ? ["Tags", d.tags] : null].filter(Boolean).flatMap(([a, b]) => [h("dt", {}, a), h("dd", {}, String(b))]));
  add(L.preview, h("div", { class: "thumb" }, img), h("h4", {}, d.title), h("span", { class: "badge", style: { "--c": typeColor(d.type) } }, d.type_label.toUpperCase()), dl, d.descr ? h("p", { class: "muted small" }, d.descr) : null,
    h("div", { class: "row" }, S.view === "bin" ? null : h("button", { class: "btn navy", onclick: () => openDoc(d.id) }, "Open"), h("button", { class: "btn", onclick: () => download(`/files/${d.id}/download`) }, "Download")));
}

/* ---------- actions on documents ---------- */
async function favSel() { const ids = selIds(); if (!ids.length) return; try { const allFav = selDocs().every(d => d.fav); await post("/api/docs/fav", { ids, on: !allFav }); await loadDocs(); renderList(); } catch (e) { toastErr(e); } }
async function moveSel(delta) {
  if (S.view !== "folder") return toast("Open a folder first to change the order of its documents.");
  if (S.order !== "pos" || S.desc) { S.order = "pos"; S.desc = false; }
  try { await post("/api/docs/reorder", { ids: selIds(), delta }); await loadDocs(); renderList(); const tr = $("tbody tr.sel", L.table); if (tr) tr.scrollIntoView({ block: "nearest" }); } catch (e) { toastErr(e); }
}
async function deleteSel(forever) {
  const ds = selDocs(); if (!ds.length) return;
  const mine = S.view === "uploads";
  const ok = await confirmDlg(mine ? "Cancel upload" : forever ? "Delete forever" : "Move to Recycle bin", mine ? `Cancel ${ds.length} upload(s)?\nThe files will be removed.` : forever ? `Delete ${ds.length} document(s) forever?\nThis cannot be undone.` : `Move ${ds.length} document(s) to the Recycle bin?\nYou can restore them from there.`, mine ? "Cancel upload" : forever ? "Delete forever" : "Move to Recycle bin", "danger");
  if (!ok) return;
  try { const r = await post("/api/docs/delete", { ids: selIds(), forever }); S.sel.clear(); closeTabsFor(ds.map(d => d.id)); await refreshLibrary(); toast(r.skipped ? `${r.done} done, ${r.skipped} skipped (only an admin or the person who added a document can remove it).` : forever ? "Deleted." : "Moved to the Recycle bin.", r.skipped ? "" : "ok"); } catch (e) { toastErr(e); }
}
async function restoreSel() { try { const r = await post("/api/docs/restore", { ids: selIds() }); S.sel.clear(); await refreshLibrary(); toast(`${r.done} document(s) restored.`, "ok"); } catch (e) { toastErr(e); } }
async function emptyBin() { if (!await confirmDlg("Empty the Recycle bin", "Delete everything in the Recycle bin forever?", "Empty it", "danger")) return; try { await post("/api/bin/empty"); S.sel.clear(); await refreshLibrary(); toast("The Recycle bin is empty.", "ok"); } catch (e) { toastErr(e); } }
function downloadSel() { const ds = selDocs(); if (ds.length === 1) download(`/files/${ds[0].id}/download`); else zipSel(); }
async function zipSel() {
  const ids = selIds(); if (!ids.length) return;
  toast("Preparing the ZIP...");
  try {
    const r = await fetch("/api/zip", { method: "POST", headers: { "X-Requested-With": "tdms", "Content-Type": "application/json" }, body: JSON.stringify({ ids }) });
    if (!r.ok) throw new Error((await r.json()).error || "Could not make the ZIP.");
    const url = URL.createObjectURL(await r.blob()), a = h("a", { href: url, download: `TDMS_documents_${new Date().toISOString().slice(0, 10).replace(/-/g, "")}.zip` });
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 5000);
  } catch (e) { toastErr(e); }
}
function exportList() {
  const q = s => '"' + String(s ?? "").replace(/"/g, '""') + '"';
  const rows = [["Name", "Type", "Status", "Folder", "Size", "Added by", "Added"].map(q).join(",")];
  for (const d of S.docs) rows.push([d.title, d.type_label, d.status, d.cat, fmtSize(d.size), d.who, fmtDate(d.created)].map(q).join(","));
  downloadText("TDMS_list.csv", "\ufeff" + rows.join("\r\n"));
}
async function renameDoc() {
  const d = selDocs()[0]; if (!d) return;
  const name = await promptDlg("Rename", "NAME", d.title, "Rename"); if (!name || name === d.title) return;
  try { await api(`/api/docs/${d.id}`, { method: "PUT", body: { title: name } }); await refreshLibrary(false); refreshTabTitle(d.id, name); } catch (e) { toastErr(e); }
}
function editDetails() {
  const d = selDocs()[0]; if (!d) return;
  const name = h("input", { class: "inp", value: d.title }), st = select(S.statuses, d.status || "(none)"), rev = h("input", { class: "inp", type: "date", value: d.review || "" });
  const tags = h("input", { class: "inp", value: d.tags }), desc = h("textarea", { class: "inp", rows: 3 }, d.descr);
  dialog({ title: "Document details", width: 520, body: [field("NAME", name), h("div", { class: "form2" }, field("STATUS", st), field("REVIEW DATE", rev)), field("TAGS", tags, "Separate with commas. Tags are searchable."), field("DESCRIPTION", desc)],
    buttons: [{ text: "Cancel" }, { text: "Save", kind: "primary", fn: async () => {
      await api(`/api/docs/${d.id}`, { method: "PUT", body: { title: name.value.trim(), status: st.value, review: rev.value, tags: tags.value, descr: desc.value } });
      await refreshLibrary(false); refreshTabTitle(d.id, name.value.trim());
    } }] });
}
async function moveDocs() {
  const dest = await pickFolder("Move to folder..."); if (dest === undefined || dest === null) return;
  try { const r = await post("/api/docs/move", { ids: selIds(), cat: dest }); S.sel.clear(); await refreshLibrary(); toast(`${r.done} document(s) moved.`, "ok"); } catch (e) { toastErr(e); }
}
function newVersion() {
  const d = selDocs()[0]; if (!d) return;
  const file = h("input", { type: "file", class: "inp", style: { height: "auto", padding: "8px" } }), note = h("input", { class: "inp", placeholder: "What changed? (optional)" });
  dialog({ title: `New version of "${d.title}"`, width: 480, body: [h("p", { class: "muted" }, `The current file (version ${d.ver}) is kept in the version history.`), field("CHOOSE THE NEW FILE", file), field("NOTE", note)],
    buttons: [{ text: "Cancel" }, { text: "Upload", kind: "primary", fn: async () => {
      if (!file.files[0]) throw new Error("Choose the new file first.");
      const f = new FormData(); f.append("file", file.files[0]); f.append("note", note.value);
      await api(`/api/docs/${d.id}/version`, { method: "POST", form: f }); await refreshLibrary(false); toast("New version saved.", "ok");
    } }] });
}
async function versionHistory() {
  const d = selDocs()[0]; if (!d) return;
  let r; try { r = await api(`/api/docs/${d.id}/versions`); } catch (e) { return toastErr(e); }
  const t = h("table", { class: "table2" }, h("thead", {}, h("tr", {}, ...["Version", "File", "Size", "By", "Date", "Note", ""].map(x => h("th", {}, x)))),
    h("tbody", {}, ...r.versions.map(v => h("tr", {}, h("td", {}, "v" + v.ver, v.current ? h("span", { class: "badge", style: { "--c": "#1D8348", marginLeft: "6px" } }, "current") : ""), h("td", {}, v.filename), h("td", {}, fmtSize(v.size)), h("td", {}, v.who), h("td", {}, fmtDate(v.created)), h("td", {}, v.note),
      h("td", {}, h("button", { class: "btn", onclick: () => download(v.current ? `/files/${d.id}/download` : `/files/${d.id}/v/${v.id}`) }, "Download"), v.current ? "" : h("button", { class: "btn", style: { marginLeft: "6px" }, onclick: async () => { if (!await confirmDlg("Restore version", `Make version ${v.ver} the current file?\nThe current one stays in the history.`, "Restore")) return; try { await post(`/api/docs/${d.id}/versions/${v.id}/restore`); dlg.close(); await refreshLibrary(false); toast("Version restored.", "ok"); } catch (e) { toastErr(e); } } }, "Restore"))))));
  const dlg = dialog({ title: `Version history - ${d.title}`, width: 860, body: h("div", { style: { overflow: "auto" } }, t), buttons: [{ text: "Close" }] });
}
async function addLink() {
  if (S.view !== "folder" || !S.cat) return toast("Open a folder first, then add the link.");
  const name = h("input", { class: "inp", placeholder: "Name, for example Training video" }), url = h("input", { class: "inp", placeholder: "https://..." });
  dialog({ title: "Add a web link", width: 480, body: [field("NAME", name), field("ADDRESS", url)], buttons: [{ text: "Cancel" }, { text: "Add", kind: "primary", fn: async () => { await post("/api/links", { cat: S.cat, name: name.value.trim(), url: url.value.trim() }); await refreshLibrary(); toast("Link added.", "ok"); } }] });
}

/* ---------- upload ---------- */
function pickFiles(folder) {
  if (S.view !== "folder" || !S.cat) return toast("Open a folder first, then add your files.");
  const inp = h("input", { type: "file", multiple: true, style: { display: "none" } });
  if (folder) inp.webkitdirectory = true;
  inp.onchange = () => { const items = [...inp.files].map(f => ({ file: f, rel: f.webkitRelativePath || "" })); inp.remove(); startUpload(items, S.cat); };
  document.body.appendChild(inp); inp.click();
}
function setupDrop(zone) {
  if (isViewer()) return;
  let depth = 0, ov = null;
  const stop = e => { e.preventDefault(); e.stopPropagation(); };
  const hasFiles = e => e.dataTransfer && [...(e.dataTransfer.types || [])].includes("Files");
  zone.addEventListener("dragenter", e => { if (!hasFiles(e)) return; stop(e); if (++depth === 1) { ov = h("div", { class: "drop" }, S.view === "folder" && S.cat ? `Drop to add to "${(folderById(S.cat) || {}).name}"` : "Open a folder first"); zone.appendChild(ov); } });
  zone.addEventListener("dragover", e => { if (hasFiles(e)) { stop(e); e.dataTransfer.dropEffect = "copy"; } });
  zone.addEventListener("dragleave", e => { if (!hasFiles(e)) return; stop(e); if (--depth <= 0) { depth = 0; if (ov) ov.remove(); ov = null; } });
  zone.addEventListener("drop", async e => {
    if (!hasFiles(e)) return; stop(e); depth = 0; if (ov) ov.remove(); ov = null;
    if (S.view !== "folder" || !S.cat) return toast("Open a folder first, then drop your files.");
    const items = await collectDropped(e.dataTransfer); if (items.length) startUpload(items, S.cat);
  });
}
async function collectDropped(dt) {
  const out = [], entries = [];
  for (const it of dt.items || []) { const en = it.webkitGetAsEntry && it.webkitGetAsEntry(); if (en) entries.push(en); }
  if (!entries.length) return [...dt.files].map(f => ({ file: f, rel: "" }));
  const walk = async (en, path) => {
    if (en.isFile) { const f = await new Promise((ok, no) => en.file(ok, no)); out.push({ file: f, rel: path + en.name }); }
    else if (en.isDirectory) {
      const rd = en.createReader(); let batch;
      do { batch = await new Promise((ok, no) => rd.readEntries(ok, no)); for (const c of batch) await walk(c, path + en.name + "/"); } while (batch.length);
    }
  };
  for (const en of entries) await walk(en, "");
  return out;
}
const Up = { box: null, list: null };
function upPanel() {
  if (Up.box && Up.box.isConnected) return;
  Up.list = h("div", {});
  Up.box = h("div", { class: "uploads" }, h("div", { class: "row" }, h("b", { class: "grow" }, "Uploading"), h("button", { class: "btn ghost sq", onclick: () => Up.box.remove() }, "\u2715")), Up.list);
  document.body.appendChild(Up.box);
}
function xhrForm(url, fd, onprog) {
  return new Promise(res => {
    const x = new XMLHttpRequest(); x.open("POST", url); x.setRequestHeader("X-Requested-With", "tdms");
    if (onprog) x.upload.onprogress = e => e.lengthComputable && onprog(e.loaded / e.total);
    x.onload = () => { let j = {}; try { j = JSON.parse(x.responseText); } catch (e) { /* ignore */ } res({ status: x.status, json: j }); };
    x.onerror = () => res({ status: 0, json: { error: "Network error." } });
    x.send(fd);
  });
}
const pieceMB = () => +localStorage.getItem("tdms_chunk_mb") || 40;         // big files travel in pieces (works through tunnels that limit one request to 100 MB)
const sleep = ms => new Promise(r => setTimeout(r, ms));
function randomId() { const a = new Uint8Array(12); (crypto.getRandomValues ? crypto.getRandomValues(a) : a.forEach((_, i) => a[i] = Math.random() * 256)); return [...a].map(b => b.toString(16).padStart(2, "0")).join(""); }
async function sendFile(cat, it, mode, onprog, st) {
  if (it.file.size <= pieceMB() * 1024 * 1024) {
    const f = new FormData(); f.append("cat", cat); f.append("file", it.file, it.file.name); f.append("relpath", it.rel || ""); if (mode) f.append("mode", mode);
    return xhrForm("/api/upload", f, onprog);
  }
  const piece = pieceMB() * 1024 * 1024, total = Math.ceil(it.file.size / piece); st.uid = st.uid || randomId();
  if (!st.sent) {
    for (let i = 0; i < total; i++) {
      let r, tries = 0;
      do {
        tries++;
        const f = new FormData(); f.append("uid", st.uid); f.append("index", i); f.append("total", total); f.append("chunk", it.file.slice(i * piece, (i + 1) * piece), "part");
        r = await xhrForm("/api/upload/chunk", f, p => onprog((i + p) / total));
        if (r.status === 200) break;
        if (r.status >= 400 && r.status < 500 && r.status !== 408 && r.status !== 429) return r;
        await sleep(1500 * tries);
      } while (tries < 4);
      if (r.status !== 200) return { status: 0, json: { error: "The connection broke. Please upload this file again." } };
    }
    st.sent = true;
  }
  try {
    const r = await fetch("/api/upload/finish", { method: "POST", headers: { "X-Requested-With": "tdms", "Content-Type": "application/json" }, body: JSON.stringify({ uid: st.uid, total, cat, filename: it.file.name, relpath: it.rel || "", mode: mode || "" }) });
    let j = {}; try { j = await r.json(); } catch (e) { /* ignore */ }
    return { status: r.status, json: j };
  } catch (e) { return { status: 0, json: { error: "Network error." } }; }
}
function askConflict(name) {
  return new Promise(res => {
    const all = h("input", { type: "checkbox" }); let done = false;
    const pick = mode => ({ text: { version: "Save as new version", rename: "Keep both", skip: "Skip" }[mode], kind: mode === "version" ? "primary" : "", fn: () => { done = true; res({ mode, all: all.checked }); } });
    dialog({ title: "A document with this name exists", width: 520, onclose: () => { if (!done) res({ mode: "skip", all: false }); },
      body: [h("p", {}, `"${name}" is already in this folder.`), h("label", { class: "sw" }, all, "Do the same for the other files that already exist")], buttons: [pick("skip"), pick("rename"), ...(isAdmin() ? [pick("version")] : [])] });
  });
}
async function startUpload(items, cat) {
  const max = items.length; if (!max) return;
  upPanel();
  let ok = 0, fail = 0, skipped = 0, sticky = null, pend = 0;
  for (const it of items) {
    const row = h("div", { class: "u" }, h("div", {}, (it.rel || it.file.name)), h("div", { class: "bar" }, h("i")));
    Up.list.appendChild(row);
    const bar = $("i", row), set = p => { bar.style.width = Math.round(p * 100) + "%"; };
    const st = {};
    let r = await sendFile(cat, it, null, set, st);
    if (r.status === 409) {
      let choice = sticky; if (!choice) { choice = await askConflict(it.file.name); if (choice.all) sticky = choice; }
      if (choice.mode === "skip") { skipped++; row.firstChild.textContent += "  (skipped)"; bar.style.width = "100%"; continue; }
      r = await sendFile(cat, it, choice.mode, set, st);
    }
    if (r.status === 200) { ok++; if (r.json && r.json.pending) pend++; bar.style.width = "100%"; bar.style.background = "#1D8348"; }
    else { fail++; bar.style.width = "100%"; bar.style.background = "#D32F2F"; row.appendChild(h("div", { style: { color: "#D32F2F" } }, (r.json && r.json.error) || "Failed")); }
  }
  toast(`${ok} uploaded${pend ? `  -  ${pend} waiting for admin approval` : ""}${skipped ? `, ${skipped} skipped` : ""}${fail ? `, ${fail} failed` : ""}.`, fail ? "err" : "ok");
  refreshCounts();
  setTimeout(() => { if (Up.box) Up.box.remove(); }, fail ? 15000 : 2500);
  await refreshLibrary();
}

/* ---------- keyboard ---------- */
document.addEventListener("keydown", e => {
  if (S.route !== "library" || !L.root || !L.root.isConnected || document.querySelector(".overlay")) return;
  const tag = (e.target.tagName || "").toLowerCase(); if (tag === "input" || tag === "textarea" || tag === "select") { if (!(e.target.type === "checkbox")) return; }
  if (e.key === "Delete" && S.sel.size && canWrite()) { e.preventDefault(); deleteSel(S.view === "bin"); }
  else if (e.key === "F2" && S.sel.size === 1 && canWrite()) { e.preventDefault(); renameDoc(); }
  else if (e.key === "Enter" && S.sel.size && S.view !== "bin") { e.preventDefault(); selIds().forEach(openDoc); }
  else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") { e.preventDefault(); selectAll(); }
  else if (e.altKey && e.key === "ArrowUp" && canWrite()) { e.preventDefault(); moveSel(-1); }
  else if (e.altKey && e.key === "ArrowDown" && canWrite()) { e.preventDefault(); moveSel(1); }
  else if (e.key === "Escape") clearSel();
});
