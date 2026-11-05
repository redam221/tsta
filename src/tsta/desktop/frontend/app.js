/* TSTA Desktop — frontend logic (talks to Python via pywebview.api) */

let api = null;

const state = {
  tree: null,          // current tree payload (nodes dict + root_id)
  selectedId: null,
  collapsed: {},       // nodeId -> true if answer hidden
  pendingAsk: null,    // parent nodeId while asking a follow-up
  trees: [],           // list from sidebar
  attachments: [],     // current tree's uploaded files
};

/* ── tiny helpers ─────────────────────────────────────────── */
const $ = (sel) => document.querySelector(sel);

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function toast(msg, type = "") {
  const el = $("#toast");
  el.textContent = msg;
  el.className = "toast show " + type;
  clearTimeout(el._t);
  el._t = setTimeout(() => (el.className = "toast " + type), 3200);
}

function relTime(iso) {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (isNaN(t)) return "";
  const d = Date.now() - t;
  const m = Math.floor(d / 60000);
  if (m < 1) return "刚刚";
  if (m < 60) return m + " 分钟前";
  const h = Math.floor(m / 60);
  if (h < 24) return h + " 小时前";
  const days = Math.floor(h / 24);
  if (days < 30) return days + " 天前";
  return new Date(iso).toLocaleDateString();
}

/* ── minimal markdown renderer (escapes first → safe) ─────── */
function renderMd(src) {
  if (!src) return "";
  // protect code blocks from newline→<br> conversion below
  const blocks = [];
  let s = esc(src).replace(/```([\s\S]*?)```/g, (m, code) => {
    blocks.push(`<pre class="md-code">${code.trim()}</pre>`);
    return `\u0000CODE${blocks.length - 1}\u0000`;
  });
  s = s.replace(/`([^`\n]+)`/g, '<code class="md-inline">$1</code>');
  s = s.replace(/^#{4,}\s*(.+)$/gm, '<h4 class="md-h4">$1</h4>');
  s = s.replace(/^###\s*(.+)$/gm, '<h4 class="md-h4">$1</h4>');
  s = s.replace(/^##\s*(.+)$/gm, '<h3 class="md-h3">$1</h3>');
  s = s.replace(/^#\s*(.+)$/gm, '<h3 class="md-h3">$1</h3>');
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/^[-*•]\s+(.+)$/gm, '<div class="md-li">· $1</div>');
  s = s.replace(/^(\d+)[.)]\s+(.+)$/gm, '<div class="md-li">$1. $2</div>');
  s = s.replace(/\n/g, "<br>");
  s = s.replace(/\u0000CODE(\d+)\u0000/g, (m, i) => blocks[+i]);
  return s;
}

/* ── boot ─────────────────────────────────────────────────── */
window.addEventListener("pywebviewready", () => {
  api = window.pywebview.api;
  bindEvents();
  refreshTrees();
  initChat();
});

function bindEvents() {
  // sidebar / topbar
  $("#btn-new-tree").addEventListener("click", openNewTree);
  $("#btn-empty-new").addEventListener("click", openNewTree);
  $("#btn-settings").addEventListener("click", openSettings);
  $("#btn-export").addEventListener("click", doExport);
  $("#btn-pick-root-files").addEventListener("click", pickRootFiles);
  $("#btn-close-detail").addEventListener("click", () => hideDetail());

  // new tree modal
  $("#btn-confirm-new").addEventListener("click", confirmNewTree);
  $("#input-root").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) confirmNewTree();
  });

  // ask modal
  $("#btn-confirm-ask").addEventListener("click", confirmAsk);
  $("#input-ask").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) confirmAsk();
  });

  // settings modal
  $("#set-provider").addEventListener("change", onProviderChange);
  $("#btn-save-settings").addEventListener("click", saveSettings);
  $("#btn-test").addEventListener("click", testConnection);

  // export modal
  $("#btn-copy-export").addEventListener("click", copyExport);

  // file note modal
  $("#btn-confirm-note").addEventListener("click", confirmNote);

  // tree canvas — delegated clicks
  $("#tree-canvas").addEventListener("click", onCanvasClick);

  // chat
  $("#btn-chat-send").addEventListener("click", sendChat);
  $("#btn-chat-clear").addEventListener("click", clearChat);
  $("#btn-chat-pop").addEventListener("click", popChat);
  $("#btn-chat-remerge").addEventListener("click", remergeChat);
  $("#chat-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); sendChat(); }
  });

  // mindmap
  $("#btn-map-collapse").addEventListener("click", toggleMindmap);

  // close buttons on all overlays
  document.querySelectorAll("[data-close]").forEach((b) =>
    b.addEventListener("click", () => closeAllOverlays())
  );
}

/* ── overlays ─────────────────────────────────────────────── */
function showOverlay(id) {
  closeAllOverlays();
  $("#" + id).classList.add("show");
}
function closeAllOverlays() {
  document.querySelectorAll(".overlay").forEach((o) => o.classList.remove("show"));
}

/* ── trees list ───────────────────────────────────────────── */
async function refreshTrees(selectId) {
  const list = await api.list_trees();
  state.trees = list;
  const el = $("#tree-list");
  if (!list.length) {
    el.innerHTML = '<div class="tree-item" style="color:var(--text-faint);cursor:default;">暂无知识树</div>';
  } else {
    el.innerHTML = list.map((t) => `
      <div class="tree-item ${t.id === (state.tree && state.tree.id) ? "active" : ""}"
           data-tree="${t.id}">
        <span class="tree-item-name">${esc(t.name)}</span>
        <span class="tree-item-meta">${t.node_count}</span>
        <span class="tree-item-del" data-del="${t.id}">✕</span>
      </div>`).join("");
    el.querySelectorAll(".tree-item[data-tree]").forEach((item) =>
      item.addEventListener("click", (e) => {
        if (e.target.dataset.del) return;
        loadTree(item.dataset.tree);
      })
    );
    el.querySelectorAll(".tree-item-del").forEach((d) =>
      d.addEventListener("click", async (e) => {
        e.stopPropagation();
        if (!confirm("删除这棵知识树？该操作不可恢复。")) return;
        await api.delete_tree(d.dataset.del);
        state.tree = null; state.selectedId = null;
        await refreshTrees();
        renderTree();
      })
    );
  }
  if (selectId) loadTree(selectId);
  else if (list.length && !state.tree) loadTree(list[0].id);
}

async function loadTree(id) {
  const r = await api.load_tree(id);
  if (!r.ok) return toast(r.message, "error");
  state.tree = r.tree;
  state.selectedId = null;
  hideDetail();
  await refreshTrees();
  renderTree();
}

/* ── new tree ─────────────────────────────────────────────── */
function openNewTree() {
  $("#input-root").value = "";
  renderRootFiles([]);
  showOverlay("overlay-new");
  setTimeout(() => $("#input-root").focus(), 50);
}
async function confirmNewTree() {
  const q = $("#input-root").value.trim();
  if (!q) return toast("请输入根问题", "error");
  closeAllOverlays();
  toast("正在生成根节点…");
  const r = await api.new_tree(q);
  if (!r.ok) return toast(r.message, "error");
  state.tree = r.tree;
  state.selectedId = null;
  await refreshTrees(r.tree.id);
  renderTree();
  toast("知识树已创建", "ok");
}

/* ── tree rendering ───────────────────────────────────────── */
function renderTree() {
  const canvas = $("#tree-canvas");
  const empty = $("#empty-state");
  if (!state.tree || !state.tree.root_id || !state.tree.nodes[state.tree.root_id]) {
    canvas.style.display = "none";
    empty.style.display = "flex";
    $("#tree-title").textContent = "未打开知识树";
    hideDetail();
    renderStats();
    renderMindmap();
    return;
  }
  empty.style.display = "none";
  canvas.style.display = "block";
  canvas.innerHTML = renderNode(state.tree.root_id, true);
  $("#tree-title").textContent = state.tree.name;
  renderStats();
  renderMindmap();
}

function renderNode(nodeId, isRoot) {
  const node = state.tree.nodes[nodeId];
  if (!node) return "";
  const children = (node.children_ids || []).map((cid) => renderNode(cid, false)).join("");
  const collapsed = state.collapsed[nodeId];
  const selected = state.selectedId === nodeId ? "selected" : "";
  const kids = (node.children_ids || []).length;
  const hasAnswer = !!node.answer;
  const files = node.attachments || [];
  return `
  <div class="node-wrap ${isRoot ? "root" : ""}">
    <div class="node-card ${selected}" data-id="${nodeId}">
      <div class="node-head" data-action="select">
        ${isRoot ? "" : '<span class="node-branch">└</span>'}
        <div class="node-q">${isRoot ? '<span class="tag-root">ROOT</span>' : ""}${esc(node.question)}</div>
        <div class="node-meta">${relTime(node.created_at)}</div>
      </div>
      ${hasAnswer ? `<div class="node-answer ${collapsed ? "collapsed" : ""}">${renderMd(node.answer)}</div>` : ""}
      ${files.length ? `
        <div class="node-files">
          ${files.map((f, fi) => `
            <div class="node-file">
              <span class="node-file-name">${esc(f.name)}</span>
              ${f.note ? `<span class="node-file-note" title="${esc(f.note)}">${esc(f.note)}</span>` : ""}
              <span class="node-file-op" data-fnote="${nodeId}:${fi}" title="添加/编辑说明">✎</span>
              <span class="node-file-op" data-frm="${nodeId}:${fi}" title="移除文件">✕</span>
            </div>`).join("")}
        </div>` : ""}
      <div class="node-foot">
        <button class="node-action" data-action="ask">＋ 追问</button>
        <button class="node-action" data-action="upload">＋ 文件</button>
        ${hasAnswer ? `<button class="node-action" data-action="collapse">${collapsed ? "展开" : "收起"}</button>` : ""}
        <button class="node-action" data-action="path">路径</button>
        <button class="node-action" data-action="edit">编辑</button>
        <button class="node-action danger" data-action="delete">删除</button>
        <span class="node-count">${kids ? kids + " 个分支" : "叶节点"}</span>
      </div>
    </div>
    <div class="node-children">${children}</div>
  </div>`;
}

function renderStats() {
  const t = state.tree;
  const el = $("#tree-stats");
  if (!t || !t.root_id) { el.textContent = ""; return; }
  el.textContent = `节点 ${t.node_count} · 深度 ${t.max_depth} · 叶子 ${t.leaf_count}`;
}

/* ── canvas interactions ──────────────────────────────────── */
function onCanvasClick(e) {
  const card = e.target.closest(".node-card");
  if (!card) return;
  const id = card.dataset.id;
  const action = e.target.dataset.action;

  // node file operations
  if (e.target.dataset.fnote) {
    const [nid, idx] = e.target.dataset.fnote.split(":");
    openNodeNote(nid, parseInt(idx, 10));
    return;
  }
  if (e.target.dataset.frm) {
    const [nid, idx] = e.target.dataset.frm.split(":");
    removeNodeFile(nid, parseInt(idx, 10));
    return;
  }

  if (action === "select") { selectNode(id); return; }
  if (action === "ask") { openAsk(id); return; }
  if (action === "upload") { addFilesToNode(id); return; }
  if (action === "collapse") { state.collapsed[id] = !state.collapsed[id]; renderTree(); return; }
  if (action === "path") { selectNode(id, true); return; }
  if (action === "edit") { openEdit(id); return; }
  if (action === "delete") { deleteNode(id); return; }
  // clicking anywhere else on the card selects it
  selectNode(id);
}

function selectNode(id, showPath = false) {
  state.selectedId = id;
  renderTree();
  showDetail(id, showPath);
}

function hideDetail() {
  $("#right-col").classList.remove("has-detail");
}

/* ── ask follow-up ────────────────────────────────────────── */
function openAsk(parentId) {
  state.pendingAsk = parentId;
  const parent = state.tree.nodes[parentId];
  $("#ask-parent-preview").textContent = "父节点：" + parent.question;
  $("#input-ask").value = "";
  showOverlay("overlay-ask");
  setTimeout(() => $("#input-ask").focus(), 50);
}
async function confirmAsk() {
  const q = $("#input-ask").value.trim();
  if (!q) return toast("请输入追问内容", "error");
  const parentId = state.pendingAsk;
  closeAllOverlays();
  toast("正在思考…");
  const r = await api.ask(parentId, q);
  if (!r.ok) return toast(r.message, "error");
  state.tree = r.tree;
  state.collapsed[r.node.id] = false;
  state.selectedId = r.node.id;
  await refreshTrees();
  renderTree();
  showDetail(r.node.id);
  toast("已生成新节点", "ok");
}

/* ── delete node ──────────────────────────────────────────── */
async function deleteNode(id) {
  const node = state.tree.nodes[id];
  if (!confirm("删除该节点及其所有分支？")) return;
  const r = await api.delete_node(id);
  if (!r.ok) return toast(r.message, "error");
  state.tree = r.tree;
  if (state.selectedId === id) hideDetail();
  await refreshTrees();
  renderTree();
  toast("已删除", "ok");
}

/* ── edit node ───────────────────────────────────────────── */
function openEdit(id) {
  selectNode(id);
  const body = $("#detail-body");
  body.querySelectorAll("[data-edit-q], [data-edit-a]").forEach((el) => {
    el.removeAttribute("disabled");
    el.style.borderColor = "var(--accent-line)";
  });
  body.querySelector("[data-edit-q]").focus();
}

/* ── detail panel ─────────────────────────────────────────── */
async function showDetail(id, showPath = false) {
  $("#right-col").classList.add("has-detail");
  const node = state.tree.nodes[id];
  const body = $("#detail-body");

  body.innerHTML = `
    <div class="detail-section">
      <h4>问题</h4>
      <textarea class="input detail-q" data-edit-q disabled rows="2">${esc(node.question)}</textarea>
    </div>
    <div class="detail-section">
      <h4>回答</h4>
      <textarea class="input detail-a" data-edit-a disabled rows="12">${esc(node.answer || "")}</textarea>
    </div>
    <div class="detail-section">
      <h4>思考路径</h4>
      <div class="path-list" id="path-list"><span style="color:var(--text-faint)">加载中…</span></div>
    </div>
    <div class="modal-actions">
      <button class="btn ghost" data-action="save-edit">保存修改</button>
    </div>
  `;

  body.querySelector("[data-action=save-edit]").addEventListener("click", async () => {
    const q = body.querySelector("[data-edit-q]").value.trim();
    const a = body.querySelector("[data-edit-a]").value;
    const r = await api.edit_node(id, q || null, a);
    if (!r.ok) return toast(r.message, "error");
    state.tree.nodes[id].question = q || node.question;
    state.tree.nodes[id].answer = a;
    await refreshTrees();
    renderTree();
    toast("已保存", "ok");
  });

  // load path
  const pr = await api.trace_path(id);
  const plist = $("#path-list");
  if (pr.ok && pr.path.length) {
    plist.innerHTML = pr.path.map((p, i) => `
      <div class="path-node ${p.id === id ? "current" : ""}">
        <div class="path-q">${i + 1}. ${esc(p.question)}</div>
      </div>`).join("");
  } else {
    plist.innerHTML = '<span style="color:var(--text-faint)">无</span>';
  }
}

/* ── settings ─────────────────────────────────────────────── */
async function openSettings() {
  const s = await api.get_settings();
  const sel = $("#set-provider");
  sel.innerHTML = Object.entries(s.providers).map(([k, v]) =>
    `<option value="${k}">${esc(v.label)}</option>`).join("");
  sel.value = s.provider;
  $("#set-base-url").value = s.base_url || "";
  $("#set-api-key").value = s.api_key || "";
  $("#set-model").value = s.model || "";
  $("#set-temp").value = s.temperature;
  $("#set-max-tokens").value = s.max_tokens;
  $("#test-result").textContent = "";
  $("#test-result").className = "test-result";
  showOverlay("overlay-settings");
}

function onProviderChange() {
  const key = $("#set-provider").value;
  const s = { providers: {} };
  // fetch preset values without re-reading settings
  const presets = {
    deepseek: ["https://api.deepseek.com/v1", "deepseek-chat"],
    doubao: ["https://ark.cn-beijing.volces.com/api/v3", "doubao-seed-1-6-250615"],
    siliconflow: ["https://api.siliconflow.cn/v1", "deepseek-ai/DeepSeek-V3"],
    openai: ["https://api.openai.com/v1", "gpt-4o"],
    custom: ["", ""],
  };
  const p = presets[key];
  if (p) {
    $("#set-base-url").value = p[0];
    $("#set-model").value = p[1];
  }
}

async function saveSettings() {
  const data = {
    provider: $("#set-provider").value,
    base_url: $("#set-base-url").value.trim(),
    api_key: $("#set-api-key").value.trim(),
    model: $("#set-model").value.trim(),
    temperature: parseFloat($("#set-temp").value) || 0.3,
    max_tokens: parseInt($("#set-max-tokens").value) || 2048,
  };
  if (!data.api_key) return toast("请填写 API Key", "error");
  const r = await api.save_settings(data);
  if (r.ok) {
    closeAllOverlays();
    toast("设置已保存", "ok");
  }
}

async function testConnection() {
  // persist first so the test uses the exact values on screen
  const data = {
    provider: $("#set-provider").value,
    base_url: $("#set-base-url").value.trim(),
    api_key: $("#set-api-key").value.trim(),
    model: $("#set-model").value.trim(),
    temperature: parseFloat($("#set-temp").value) || 0.3,
    max_tokens: parseInt($("#set-max-tokens").value) || 2048,
  };
  const el = $("#test-result");
  el.className = "test-result";
  el.textContent = "测试中…";
  await api.save_settings(data);
  const r = await api.test_connection();
  el.textContent = r.message;
  el.className = "test-result " + (r.ok ? "ok" : "fail");
}

/* ── export ───────────────────────────────────────────────── */
async function doExport() {
  if (!state.tree) return toast("请先打开一个知识树", "error");
  const r = await api.export_paths();
  if (!r.ok) return toast(r.message, "error");
  $("#export-output").value = r.paths.join("\n\n════════════════════\n\n");
  showOverlay("overlay-export");
}
function copyExport() {
  const el = $("#export-output");
  el.select();
  document.execCommand("copy");
  toast("已复制到剪贴板", "ok");
}

/* ── files (per-node) ────────────────────────────────────── */
function fmtChars(n) {
  if (n >= 1000) return (n / 1000).toFixed(1) + "k";
  return n + "";
}

// root-question file staging (new-tree modal)
async function pickRootFiles() {
  const r = await api.pick_files_to_pending();
  if (r.cancelled) return;
  if (!r.ok) return toast(r.message, "error");
  renderRootFiles(r.pending);
  const errors = (r.added || []).filter((a) => a.error);
  if (errors.length) {
    toast(errors.map((a) => a.name + "：" + a.error).join("；"), "error");
  }
}

function renderRootFiles(list) {
  const el = $("#root-file-list");
  if (!list || !list.length) {
    el.innerHTML = '<div class="file-empty">未添加文件（可选）</div>';
    return;
  }
  el.innerHTML = list.map((f, i) => `
    <div class="file-chip">
      <span class="file-chip-name">${esc(f.name)}</span>
      <span class="file-chip-size">${fmtChars(f.chars)} 字</span>
      <span class="file-chip-x" data-pending-rm="${i}" title="移除">✕</span>
    </div>`).join("");
  el.querySelectorAll("[data-pending-rm]").forEach((x) =>
    x.addEventListener("click", async () => {
      await api.remove_pending_file(parseInt(x.dataset.pendingRm, 10));
      renderRootFiles((await api.list_pending()).pending);
    }));
}

// node-level file upload / note / remove
async function addFilesToNode(nodeId) {
  const r = await api.add_files_to_node(nodeId);
  if (r.cancelled) return;
  if (!r.ok) return toast(r.message, "error");
  state.tree = r.tree;
  renderTree();
  const added = r.added || [];
  const errors = added.filter((a) => a.error);
  if (errors.length) toast(errors.map((a) => a.name + "：" + a.error).join("；"), "error");
  else if (added.length) toast("已添加 " + added.length + " 个文件", "ok");
}

let noteNodeId = null;
let noteIndex = null;
function openNodeNote(nodeId, index) {
  noteNodeId = nodeId;
  noteIndex = index;
  const node = state.tree.nodes[nodeId];
  const f = node && node.attachments && node.attachments[index];
  if (!f) return;
  $("#note-filename").textContent = f.name;
  $("#input-note").value = f.note || "";
  showOverlay("overlay-note");
  setTimeout(() => $("#input-note").focus(), 50);
}
async function confirmNote() {
  const note = $("#input-note").value.trim();
  const r = await api.add_node_file_note(noteNodeId, noteIndex, note);
  if (!r.ok) return toast(r.message, "error");
  closeAllOverlays();
  state.tree.nodes[noteNodeId] = r.node;
  renderTree();
  toast("说明已保存", "ok");
}

async function removeNodeFile(nodeId, index) {
  const r = await api.remove_node_file(nodeId, index);
  if (!r.ok) return toast(r.message, "error");
  state.tree.nodes[nodeId] = r.node;
  renderTree();
}

/* ── chat (dockable / detachable) ────────────────────────── */
async function initChat() {
  const r = await api.chat_history();
  if (r.ok) renderChatMessages(r.messages);
}

function renderChatMessages(messages) {
  const el = $("#chat-msgs");
  if (!messages || !messages.length) {
    el.innerHTML = '<div class="chat-empty">开始和 AI 对话吧</div>';
    return;
  }
  el.innerHTML = messages.map((m) => `
    <div class="chat-msg ${m.role}">
      <div class="chat-bubble">${m.role === "assistant" ? renderMd(m.content) : esc(m.content)}</div>
    </div>`).join("");
  el.scrollTop = el.scrollHeight;
}

async function sendChat() {
  const input = $("#chat-input");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  const r = await api.chat_send(text);
  if (!r.ok) { input.value = text; return toast(r.message, "error"); }
  renderChatMessages(r.messages);
}

async function clearChat() {
  if (!confirm("清空所有对话记录？")) return;
  const r = await api.chat_clear();
  renderChatMessages(r.messages);
}

async function popChat() {
  const r = await api.pop_chat();
  if (!r.ok) return toast(r.message, "error");
}

async function remergeChat() {
  const r = await api.merge_chat();
  if (!r.ok) return toast(r.message, "error");
}

// Called by Python when the chat is detached into its own window.
window.__chatPoppedOut = function () {
  $("#chat-popped-hint").style.display = "flex";
  $("#chat-msgs").style.display = "none";
  $(".chat-input-row").style.display = "none";
};

// Called by Python when the chat is re-docked (merge button or window ✕).
window.__chatMergedBack = async function () {
  $("#chat-popped-hint").style.display = "none";
  $("#chat-msgs").style.display = "flex";
  $(".chat-input-row").style.display = "flex";
  const r = await api.chat_history();
  if (r.ok) renderChatMessages(r.messages);
};

/* ── mind map (parent-child overview) ────────────────────── */
const mindmapState = { collapsed: false };

function toggleMindmap() {
  mindmapState.collapsed = !mindmapState.collapsed;
  renderMindmap();
}

function renderMindmap() {
  const wrap = $("#mindmap");
  const body = $("#mindmap-body");
  const t = state.tree;

  if (!t || !t.root_id || !t.nodes[t.root_id]) {
    wrap.style.display = "none";
    return;
  }
  wrap.style.display = "flex";
  wrap.classList.toggle("collapsed", mindmapState.collapsed);
  $("#btn-map-collapse").textContent = mindmapState.collapsed ? "＋" : "—";
  if (mindmapState.collapsed) {
    body.innerHTML = "";
    return;
  }

  const kidsOf = (id) => (t.nodes[id].children_ids || []).filter((c) => t.nodes[c]);

  // Horizontal tree layout: depth → x, leaf order → y, parent centered on children.
  const pos = {};
  let leaf = 0;
  function layout(id, depth) {
    const kids = kidsOf(id);
    if (!kids.length) { pos[id] = { x: depth, y: leaf++ }; return; }
    let s = 0;
    for (const c of kids) { layout(c, depth + 1); s += pos[c].y; }
    pos[id] = { x: depth, y: s / kids.length };
  }
  layout(t.root_id, 0);

  const nodeW = 128, nodeH = 24, hGap = 44, vGap = 14, pad = 16;
  const px = (id) => pad + pos[id].x * (nodeW + hGap);
  const py = (id) => pad + pos[id].y * (nodeH + vGap);

  const edges = [];
  const nodesHtml = [];
  let maxDepth = 0;
  function walk(id) {
    if (pos[id].x > maxDepth) maxDepth = pos[id].x;
    const kids = kidsOf(id);
    for (const c of kids) {
      const x1 = px(id) + nodeW, y1 = py(id) + nodeH / 2;
      const x2 = px(c), y2 = py(c) + nodeH / 2;
      const mx = (x1 + x2) / 2;
      edges.push(`M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`);
      walk(c);
    }
    const n = t.nodes[id];
    const label = n.question.length > 14 ? n.question.slice(0, 14) + "…" : n.question;
    nodesHtml.push(`
      <g class="mm-node${id === t.root_id ? " root" : ""}${id === state.selectedId ? " sel" : ""}"
         data-id="${id}" transform="translate(${px(id)}, ${py(id)})">
        <rect width="${nodeW}" height="${nodeH}" rx="6"/>
        <text x="${nodeW / 2}" y="${nodeH / 2 + 1}" text-anchor="middle">${esc(label)}</text>
        <title>${esc(n.question)}</title>
      </g>`);
  }
  walk(t.root_id);

  const width = pad * 2 + maxDepth * (nodeW + hGap) + nodeW;
  const height = pad * 2 + (leaf - 1) * (nodeH + vGap) + nodeH;

  body.innerHTML = `<svg viewBox="0 0 ${width} ${Math.max(height, 80)}" preserveAspectRatio="xMidYMid meet">
    <g class="mm-edges"><path d="${edges.join("")}"/></g>
    ${nodesHtml.join("")}
  </svg>`;

  body.querySelectorAll(".mm-node").forEach((g) =>
    g.addEventListener("click", () => selectNode(g.getAttribute("data-id")))
  );
}
