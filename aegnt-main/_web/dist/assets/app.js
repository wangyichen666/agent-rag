// app.js — 纯静态前端：hash 路由 + 按需加载数据 + 渲染文档/代码/搜索
window.__docs__ = window.__docs__ || {};
window.__code__ = window.__code__ || {};
window.__explanations = window.__explanations || {};
const loaded = { docs: new Set(), code: new Set() };

const $ = (id) => document.getElementById(id);
function mk(html) { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstChild; }
function esc(s) { return String(s || "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

// ---- 按需加载数据 JS (规避 file:// CORS：用 <script> 加载) ----
function loadScript(src) {
  return new Promise((res, rej) => {
    const s = document.createElement("script");
    s.src = src; s.onload = res; s.onerror = () => rej(new Error("load fail " + src));
    document.head.appendChild(s);
  });
}
async function loadDoc(id) {
  if (window.__docs__[id]) return window.__docs__[id];
  if (loaded.docs.has(id)) return null;
  try { await loadScript("data/docs/" + encodeURIComponent(id) + ".js"); loaded.docs.add(id); }
  catch (e) { return null; }
  return window.__docs__[id] || null;
}
async function loadCode(id) {
  if (window.__code__[id]) return window.__code__[id];
  if (loaded.code.has(id)) return null;
  try { await loadScript("data/code/" + encodeURIComponent(id) + ".js"); loaded.code.add(id); }
  catch (e) { return null; }
  return window.__code__[id] || null;
}

// ---- 导航树 ----
function renderTree(activeId) {
  const t = $("tree"); t.innerHTML = "";
  if (!window.__tree__) return;
  for (const st of window.__tree__.stages) {
    t.appendChild(mk(`<div class="stage">${esc(st.name)}</div>`));
    for (const doc of st.docs) {
      const a = mk(`<a data-doc="${esc(doc.id)}" class="${doc.id === activeId ? "active" : ""}">${esc(doc.title)}</a>`);
      a.onclick = (e) => { e.preventDefault(); location.hash = "#doc/" + doc.id; };
      t.appendChild(a);
    }
  }
}

// ---- 文档页 ----
async function showDoc(id) {
  renderTree(id);
  const d = await loadDoc(id);
  if (!d) { $("view").innerHTML = `<div class="empty">未找到文档 ${esc(id)}</div>`; $("toc").innerHTML = ""; return; }
  $("view").innerHTML = `<div>${d.html}</div>`;
  // 右侧目录
  let tocHtml = `<div class="toc-title">本页目录</div>`;
  d.toc.forEach((t, i) => {
    tocHtml += `<a data-level="${t.level}" data-anchor="${i}">${esc(t.text)}</a>`;
  });
  $("toc").innerHTML = tocHtml;
  // 绑定 code-link
  $("view").querySelectorAll("a.code-link").forEach(a => {
    a.onclick = (e) => {
      e.preventDefault();
      const cid = a.dataset.code, ref = a.dataset.ref;
      const m = ref.match(/:(\d+)$/);
      location.hash = "#code/" + cid + (m ? "?L=" + m[1] : "");
    };
  });
  // 目录锚点
  $("toc").querySelectorAll("a[data-anchor]").forEach(a => {
    a.onclick = (e) => {
      e.preventDefault();
      const idx = +a.dataset.anchor;
      // 跳到对应标题（用文本匹配简单定位）
      const target = d.toc[idx];
      const heads = $("view").querySelectorAll("h1,h2,h3,h4,h5,h6");
      for (const h of heads) { if (h.textContent.trim() === target.text) { h.scrollIntoView({ behavior: "smooth", block: "start" }); break; } }
    };
  });
  // 上下篇
  const nav = [];
  if (d.prev) nav.push(`<a href="#doc/${d.prev}">← 上一篇</a>`);
  nav.push(`<span></span>`);
  if (d.next) nav.push(`<a href="#doc/${d.next}">下一篇 →</a>`);
  $("view").appendChild(mk(`<div class="prev-next">${nav.join("")}</div>`));
  $("content").scrollTop = 0;
}

// ---- 代码页 (左源码右讲解) ----
async function showCode(cid, L) {
  renderTree(null);
  $("toc").innerHTML = "";
  const c = await loadCode(cid);
  if (!c) { $("view").innerHTML = `<div class="empty">代码条目未加载：${esc(cid)}</div>`; return; }
  const hl = L || c.highlight_line;
  const isMissing = c.missing;
  const kpHtml = (c.knowledge_points || []).map(k => `<div class="kp"><h4>${esc(k.title)}</h4><p>${esc(k.body)}</p></div>`).join("");
  const relHtml = (c.related_docs || []).map(id => `<a href="#doc/${esc(id)}">${esc(id)}</a>`).join("");
  $("view").innerHTML = `
    <div class="code-page">
      <div class="code-left">
        <div class="code-head">
          <button class="jump-btn" id="jumpBtn">跳到 L${esc(hl || 1)}</button>
          <span style="font-size:12px;color:#999;margin-left:8px">${esc(c.source_path || "")}${c.lines ? " · " + c.lines + " 行" : ""}</span>
        </div>
        ${isMissing ? '<div class="empty">⚠️ 源码文件未找到（可能路径已变化）。参考文档讲解。</div>' : (c.code_html || "")}
      </div>
      <div class="code-right">
        <button onclick="history.back()" style="margin-bottom:8px">← 返回文档</button>
        <h2>${esc(c.title || cid)}</h2>
        <h3 style="margin-top:18px">讲解</h3>
        <div class="explain-box">${(c.explanation || "（暂无讲解）").split("\n").map(p => esc(p)).join("<br>")}</div>
        ${kpHtml ? `<h3>相关知识点</h3>${kpHtml}` : ""}
        ${relHtml ? `<h3 style="margin-top:14px">出现在文档</h3><div class="rel-links">${relHtml}</div>` : ""}
      </div>
    </div>`;
  if (!isMissing && hl) {
    setTimeout(() => jumpTo(hl), 60);
    $("jumpBtn").onclick = () => jumpTo(hl);
  } else if ($("jumpBtn")) {
    $("jumpBtn").style.display = "none";
  }
}

function jumpTo(line) {
  const node = document.querySelector(`.c-line[data-line="${line}"]`);
  if (!node) return;
  document.querySelectorAll(".c-line.hl").forEach(n => n.classList.remove("hl"));
  node.scrollIntoView({ block: "center" });
  node.classList.add("hl");
}

// ---- 搜索 ----
function doSearch(q) {
  if (!q || !q.trim()) { $("view").innerHTML = `<div class="empty">输入关键词搜索文档与代码</div>`; $("toc").innerHTML = ""; return; }
  const inv = (window.__search__ && window.__search__.inv) || {};
  const docs = (window.__search__ && window.__search__.documents) || [];
  const words = q.toLowerCase().split(/[\s,，]+/).filter(Boolean);
  const scores = {};
  for (const t in inv) {
    for (const w of words) {
      if (t.includes(w)) { for (const did of inv[t]) scores[did] = (scores[did] || 0) + 1; }
    }
  }
  const ranked = Object.entries(scores).sort((a, b) => b[1] - a[1]).slice(0, 40);
  let html = `<div class="search-results"><h3>搜索 “${esc(q)}” → ${ranked.length} 条结果</h3>`;
  if (!ranked.length) html += `<div class="empty">无匹配</div>`;
  for (const [did] of ranked) {
    const d = docs.find(x => x.doc_id === did);
    html += `<a class="res" href="#doc/${esc(did)}">${esc(d ? d.title : did)}<span class="meta"> · ${esc(d ? d.stage : "")}</span></a>`;
  }
  html += `</div>`;
  $("view").innerHTML = html;
  $("toc").innerHTML = "";
}

// ---- 路由 ----
function route() {
  const h = location.hash.slice(1);
  if (h.startsWith("doc/")) return showDoc(decodeURIComponent(h.slice(4)));
  if (h.startsWith("code/")) {
    const rest = h.slice(5);
    const [cid, q] = rest.split("?");
    const L = q && q.startsWith("L=") ? q.slice(2) : null;
    return showCode(decodeURIComponent(cid), L);
  }
  if (h.startsWith("search")) {
    const q = h.split("=")[1] ? decodeURIComponent(h.slice(h.indexOf("=") + 1)) : "";
    return doSearch(q);
  }
  return showDoc("README");
}

window.addEventListener("DOMContentLoaded", () => {
  renderTree(null);
  let searchTimer;
  $("search").addEventListener("input", (e) => {
    const q = e.target.value.trim();
    clearTimeout(searchTimer);
    if (!q) return;
    searchTimer = setTimeout(() => { location.hash = "#search/q=" + encodeURIComponent(q); }, 250);
  });
  window.addEventListener("hashchange", route);
  route();
});