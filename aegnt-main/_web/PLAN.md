# 教程 Web 阅读站 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `2027年/` 下 26 篇文档 + 30 个代码做成纯静态 Web 站，文档里代码提及可点击跳「代码展示页」（整文件源码 + 讲解 + 知识点 + 反向链接 + 全文搜索），双击 `index.html` 即看。

**Architecture:** Python 构建脚本 `build.py`（零三方依赖）扫文档+代码，生成 `dist/` 纯静态产物（HTML + 以 `window.__x__={}` 形式加载的 JS 数据，规避 `file://` CORS）。前端原生 JS + hash 路由，无框架。代码高亮构建期预生成（离线可用）。

**Tech Stack:** Python 3 标准库（markdown 优先用标准库或内置轻量转换，不引入三方除非必要）、原生 JS、CSS、highlight.js（构建期预高亮，可选轻量自实现以避免依赖）。

**关键设计决策（已确认）：**
- 源码引用靠**路径前缀消歧**：文档带相对路径（`agent/_agent.py`→agentscope，`runtime/envelope.py`→qwenpaw）；纯文件名回退先 AS 后 QP。
- 同一源码文件多行引用合并存一份整文件数据，hash `?L=` 指定高亮行。
- AI 补全讲解在构建期生成、写死进 JS。
- 源码展示**整文件全文**，引用行高亮+自动滚。

---

## 文件结构

| 文件 | 责任 |
|---|---|
| `_web/build.py` | 构建脚本：解析文档、识别链接、读代码源码、抽讲解、建索引、生成 dist |
| `_web/PLAN.md` | 本计划 |
| `_web/SPEC.md` | 设计文档（已存在） |
| `_web/dist/index.html` | 入口（含左导航骨架、搜索框、正文容器） |
| `_web/dist/assets/app.js` | 前端：hash 路由、渲染文档/代码/搜索、按需加载 JS 数据 |
| `_web/dist/assets/style.css` | 三栏/两栏布局 + 代码高亮样式 |
| `_web/dist/assets/highlight.py` | 构建期轻量 Python 代码高亮器（或用标准库方案，见 Task 3） |
| `_web/dist/data/tree.js` | `window.__tree__` 导航树 |
| `_web/dist/data/search.js` | `window.__search__` 倒排索引 |
| `_web/dist/data/docs/<id>.js` | `window.__docs__["<id>"]` 每篇文档 |
| `_web/dist/data/code/<code_id>.js` | `window.__code__["<id>"]` 每段代码 |

---

## Task 1：路径解析器（含自测）

**Files:**
- Create: `_web/build.py`（先建骨架 + path_resolver 模块）

**目标**：把文档里各种形态的代码引用，解析成「磁盘绝对路径 + 高亮行」。

- [ ] **Step 1: 在 build.py 顶部写配置与解析函数**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建脚本：把 2027年/ 文档+代码生成纯静态 dist/。零三方依赖。"""
import json
import os
import re
import sys
import html as html_lib
from pathlib import Path

# ===== 路径配置 =====
ROOT = Path(__file__).resolve().parent.parent          # 2027年/
CODE_DIR = ROOT / "code"
AS_SRC = Path("/Users/zhongyou/Desktop/github/agentscope/src/agentscope")
QP_SRC = Path("/Users/zhongyou/Desktop/github/QwenPaw-main/src/qwenpaw")
DIST = Path(__file__).resolve().parent / "dist"

# 文档根(各阶段目录)
DOC_DIRS = {
    "地基": ROOT / "阶段一-地基",
    "框架": ROOT / "阶段二-框架",
    "产品": ROOT / "阶段三-产品",
    "面试卡": ROOT / "面试问答卡",
    "checklist": ROOT / "改造checklist",
}

# code_id 规则：lowercase，. 和 / 和 _ 转 -
def make_code_id(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def resolve_code_ref(ref: str):
    """解析文档里的代码引用。
    返回 (kind, disk_path, highlight_line) 或 None。
    ref 形态:
      - 'code/w04/quickstart.py'          → local, CODE_DIR/w04/quickstart.py, None
      - 'agent/_agent.py:664'             → src, AS_SRC/agent/_agent.py, 664
      - 'runtime/envelope.py:27'          → src, QP_SRC/runtime/envelope.py, 27
      - '_agent.py:100' (纯文件名)        → src, 先 AS 后 QP 找, 100
    """
    # 本地代码
    m = re.match(r"^code/(w\d+/[\w/]+\.\w+)$", ref)
    if m:
        p = CODE_DIR / m.group(1)
        return ("local", p, None) if p.exists() else None

    # 源码：分离 路径:行号
    m = re.match(r"^(.+?)\.py(?::(\d+))?$", ref)
    if not m:
        # 可能是 'xxx.py:行号' 已被上面 group 捕获，这里再兜底
        m2 = re.match(r"^(.+):(\d+)$", ref)
        if not m2:
            return None
        path_part, line = m2.group(1), int(m2.group(2))
    else:
        path_part, line = m.group(1) + ".py", (int(m.group(2)) if m.group(2) else None)

    # 去掉前导 / 或多余的 agentscope/src/agentscope 等前缀，保留相对模块路径
    path_part = re.sub(r"^/?(agentscope/src/agentscope|src/agentscope|agentscope)/", "", path_part)
    path_part = re.sub(r"^/?(QwenPaw-main/src/qwenpaw|src/qwenpaw|qwenpaw)/", "", path_part)
    path_part = path_part.lstrip("/")

    # 先按 agentscope 试，再 qwenpaw
    for base in (AS_SRC, QP_SRC):
        # 直接拼
        cand = base / path_part
        if cand.exists():
            return ("src", cand, line)
        # 纯文件名回退：在 base 下搜同名
        if "/" not in path_part:
            hit = list(base.rglob(path_part))
            if hit:
                return ("src", hit[0], line)
    return None
```

- [ ] **Step 2: 在 build.py 末尾加自测 `__main__`**

```python
def _selftest():
    cases = [
        ("code/w04/quickstart.py", ("local", CODE_DIR / "w04" / "quickstart.py", None)),
        ("agent/_agent.py:664", ("src", AS_SRC / "agent" / "_agent.py", 664)),
        ("runtime/envelope.py:27", ("src", QP_SRC / "runtime" / "envelope.py", 27)),
    ]
    ok = True
    for ref, expected in cases:
        got = resolve_code_ref(ref)
        if got != expected:
            print(f"FAIL {ref!r}: got {got}, want {expected}")
            ok = False
        else:
            print(f"PASS {ref!r}")
    # 纯文件名回退
    g = resolve_code_ref("_agent.py:100")
    assert g and g[0] == "src" and g[2] == 100, f"fallback fail: {g}"
    print("PASS _agent.py:100 fallback")
    print("ALL OK" if ok else "HAS FAILURES")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        _selftest()  # 默认也跑一遍自测再构建
        # build_all()  # 后续任务实现
```

- [ ] **Step 3: 运行自测**

Run: `cd /Users/zhongyou/Desktop/2027年/_web && python3 build.py --selftest`
Expected: 输出几行 PASS + `ALL OK`（路径存在性依赖本地源码在 github/ 下）。

- [ ] **Step 4: Commit**

```bash
cd /Users/zhongyou/Desktop/2027年/_web
git add build.py
git commit -m "feat(web): add build.py path resolver with selftest"
```
（若 `2027年/` 不在 git 仓库，跳过 commit，下同。）

---

## Task 2：Markdown 解析 + 代码链接识别（含自测）

**Files:**
- Modify: `_web/build.py`

**目标**：Markdown→HTML，且把代码引用替换成可点击链接占位。零三方依赖（自己写极简 Markdown 转换——本项目文档用的 Markdown 特性有限：标题、列表、代码块、表格、粗体、链接，够用）。

- [ ] **Step 1: 加 Markdown 转换函数 `md_to_html`**

```python
# 识别代码引用的正则：覆盖 code/w##/x.py 和 模块路径.py:行号
CODE_REF_RE = re.compile(
    r"(?<![A-Za-z0-9/])"           # 前面不是路径字符(避免误匹配一半)
    r"((?:code/w\d+/[\w/]+\.\w+)"  # 本地代码
    r"|(?:[A-Za-z0-9_][\w/]*\.py(?:\:\d+)?))"  # 源码 .py 或 .py:行号
)


def md_to_html(md: str) -> str:
    """极简 Markdown → HTML。支持：标题、代码块```、行内`、列表-、粗体**、表格|。"""
    lines = md.split("\n")
    out = []
    i = 0
    in_code = False
    code_buf = []
    while i < len(lines):
        line = lines[i]
        # 代码块
        if line.strip().startswith("```"):
            if not in_code:
                in_code = True
                code_buf = []
                lang = line.strip()[3:].strip()
                out.append(f'<pre><code class="language-{lang}">')
            else:
                in_code = False
                out.append(html_lib.escape("".join(code_buf)))
                out.append("</code></pre>")
            i += 1
            continue
        if in_code:
            code_buf.append(line + "\n")
            i += 1
            continue
        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lvl = len(m.group(1))
            text = inline_md(m.group(2))
            out.append(f"<h{lvl}>{text}</h{lvl}>")
            i += 1
            continue
        # 表格(简单处理:连续 | 行)
        if line.strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[i + 1].strip()):
            out.append("<table>")
            out.append("<tr>" + "".join(f"<th>{inline_md(c.strip())}</th>" for c in line.strip().strip("|").split("|")) + "</tr>")
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = lines[i].strip().strip("|").split("|")
                out.append("<tr>" + "".join(f"<td>{inline_md(c.strip())}</td>" for c in cells) + "</tr>")
                i += 1
            out.append("</table>")
            continue
        # 列表
        if re.match(r"^\s*[-*]\s+", line):
            text = inline_md(re.sub(r"^\s*[-*]\s+", "", line))
            out.append(f"<li>{text}</li>")
            i += 1
            continue
        # 空行
        if not line.strip():
            out.append("")
            i += 1
            continue
        # 普通段落
        out.append(f"<p>{inline_md(line)}</p>")
        i += 1
    return "\n".join(out)


def inline_md(text: str) -> str:
    """行内：代码引用链接化 > 行内代码` > 粗体** > 链接[](）。"""
    # 先把已有 [text](url) 链接保护起来
    # 简化：先做粗体和行内代码，最后做代码引用(避免把代码引用里的 . 当字符)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", lambda m: f'<code class="inline">{html_lib.escape(m.group(1))}</code>', text)

    def repl(m):
        ref = m.group(1)
        cid = make_code_id(ref)
        resolved = resolve_code_ref(ref)
        cls = "code-link" + ("" if resolved else " code-link-missing")
        return f'<a class="{cls}" data-code="{cid}" data-ref="{html_lib.escape(ref)}">{html_lib.escape(ref)}</a>'

    text = CODE_REF_RE.sub(repl, text)
    return text
```

- [ ] **Step 2: 加自测用例**

```python
def _selftest_md():
    md = "# 标题\n## 二级\n看 `agent/_agent.py:664` 和 code/w04/quickstart.py\n"
    h = md_to_html(md)
    assert "<h1>标题</h1>" in h, h
    assert 'data-code="' in h, "代码链接未生成"
    assert ">agent/_agent.py:664</a>" in h, h
    assert ">code/w04/quickstart.py</a>" in h, h
    print("PASS md_to_html + code link")
```

把 `_selftest()` 调用改为同时调 `_selftest_md()`。

- [ ] **Step 3: 运行**

Run: `python3 build.py --selftest`
Expected: `ALL OK` 含 `PASS md_to_html + code link`。

- [ ] **Step 4: Commit**

```bash
git add build.py && git commit -m "feat(web): markdown to html with code-link substitution"
```

---

## Task 3：构建期代码高亮器（零依赖，含自测）

**Files:**
- Modify: `_web/build.py`

**目标**：离线可用，不引三方。自实现一个轻量 Python 语法高亮（关键字/字符串/注释/行号），输出带行号的 HTML。够用即可，不求完美。

- [ ] **Step 1: 加高亮函数 `highlight_python`**

```python
PY_KEYWORDS = {"def","class","return","if","elif","else","for","while","try","except",
    "finally","with","import","from","as","async","await","yield","lambda","None","True",
    "False","self","in","not","and","or","is","pass","break","continue","raise","global",
    "nonlocal","assert","del","print"}

def highlight_python(code: str) -> str:
    """返回带行号的 HTML，关键字/字符串/注释着色。整文件不一次性转义太长，按行处理。"""
    out = ['<div class="code-body">']
    for idx, line in enumerate(code.split("\n"), 1):
        esc = html_lib.escape(line)
        # 注释
        if "#" in esc:
            # 简单：#后到行尾算注释(不处理字符串内的#，足够阅读用)
            esc = re.sub(r'(#.*$)', r'<span class="c-com">\1</span>', esc)
        # 字符串（含三引号的行简化为匹配 "..." 和 '...'）
        esc = re.sub(r'(&quot;.*?&quot;|&#x27;.*?&#x27;)', r'<span class="c-str">\1</span>', esc)
        # 关键字（词边界）
        esc = re.sub(r"\b(" + "|".join(PY_KEYWORDS) + r")\b", r'<span class="c-kw">\1</span>', esc)
        out.append(f'<div class="c-line" data-line="{idx}"><span class="c-no">{idx}</span><span class="c-src">{esc or "&nbsp;"}</span></div>')
    out.append("</div>")
    return "\n".join(out)
```

注：`html_lib.escape` 会把 `"` 转成 `&quot;`、`'` 转成 `&#x27;`，所以正则用它们。

- [ ] **Step 2: 自测**

```python
def _selftest_hl():
    h = highlight_python("def f():\n    return 'x'  # hi\n")
    assert 'data-line="1"' in h and 'data-line="2"' in h
    assert 'c-kw' in h and 'c-str' in h and 'c-com' in h
    print("PASS highlight_python")
```

加进 `_selftest()` 调用链。运行 `python3 build.py --selftest` 期望 `PASS highlight_python`。

- [ ] **Step 3: Commit**

```bash
git add build.py && git commit -m "feat(web): offline python syntax highlighter"
```

---

## Task 4：代码条目构建（读源码全文 + 抽讲解 + 反向链接）

**Files:**
- Modify: `_web/build.py`

**目标**：为每个 code_id 生成 `data/code/<id>.js`。读整文件源码、高亮、抽文档讲解、匹配知识点、算反向链接。

- [ ] **Step 1: 加讲解抽取与知识点匹配函数**

```python
# 文档里"讲解"段落识别：标题含 源码精读/动手作业/工作原理 等，取其后到下一 h2 之前的文本
EXPLAIN_SECTIONS_RE = re.compile(r"(源码精读|动手作业|工作原理|实现|精读)", re.I)

def build_code_entry(code_id: str, ref_first: str, refs: list[str], doc_index: dict) -> dict:
    """构建一个 code 条目。refs=所有引用过它的(ref 字符串)。
    ref_first=第一次出现的引用(用于定位文件+高亮行)。
    doc_index= {doc_id: {"html":...,}} 用于反向链接讲解抽取。
    """
    resolved = resolve_code_ref(ref_first)
    if not resolved:
        return {"code_id": code_id, "missing": True, "ref": ref_first}
    kind, disk_path, hl = resolved
    code_text = disk_path.read_text(encoding="utf-8", errors="replace")
    # 截断超长文件避免产物过大（>3000 行只取首 3000 + 末 200，中间标注；首版先不截，整文件存）
    highlighted = highlight_python(code_text) if disk_path.suffix == ".py" else html_lib.escape(code_text)

    # 反向链接：哪些 doc 提到它
    related = []
    explanation_parts = []
    kw_hint = disk_path.stem  # 文件名词根用于匹配知识点
    for doc_id, dinfo in doc_index.items():
        if code_id in dinfo.get("code_ids", set()):
            related.append(doc_id)
            # 抽该 doc 里含此 ref 附近的讲解段落（简化：抽"源码精读"等小节文本）
            for para in dinfo.get("explain_paragraphs", []):
                if any(r in para for r in refs):
                    explanation_parts.append(para)
    explanation = "\n\n".join(explanation_parts[:3]) if explanation_parts else ""

    # 知识点匹配：按文件名/路径关键词，从 JD_KNOWLEDGE 表取
    kps = match_knowledge_points(disk_path)
    if not explanation:
        explanation = explain_fallback(code_id, kind, disk_path, defined=["AI构建期补全占位——实际由步骤内 AI 补全"])

    title = f"{disk_path.name}" + (f":{hl}" if hl else "")
    return {
        "code_id": code_id,
        "kind": kind,
        "title": title,
        "source_path": str(disk_path.relative_to(Path("/Users/zhongyou/Desktop/github"))) if str(disk_path).startswith("/Users/zhongyou/Desktop/github") else str(disk_path),
        "highlight_line": hl,
        "language": "python",
        "code_html": highlighted,
        "lines": code_text.count("\n") + 1,
        "explanation": explanation,
        "knowledge_points": kps,
        "related_docs": related,
    }
```

- [ ] **Step 2: 加知识点匹配表 + AI 补全占位函数**

`match_knowledge_points` 按路径/文件名关键词命中预设知识点表。`explain_fallback` 为构建期 AI 补全入口（实际生成时由执行者填真实讲解文本，**不要留 TODO**——见 Task 7 在构建时实际填）。

```python
KNOWLEDGE_TABLE = [
    (["_reply_impl", "_reasoning", "_check_next_action"], "ReAct 推理循环",
     "Thought→Action→Observation 交替，_check_next_action 决定退出还是继续推理，max_iters 兜底。"),
    (["compress_context", "SummarySchema", "_config.py"], "上下文压缩",
     "超 trigger_ratio(0.8) 触发，用 SummarySchema 五字段做结构化摘要替换历史，非简单截断。"),
    (["toolkit", "_toolkit", "call_tool", "_adapters"], "工具体系",
     "Toolkit 统管，FunctionTool 自动 schema，MCPTool 远端代理，ToolGroup 分组按需激活。"),
    (["_mcp_client", "MCPClient", "StdioMCPConfig"], "MCP 客户端",
     "MCPClient 连 Server，list_tools 动态发现，stdio 必须 stateful+connect。"),
    (["RAGMiddleware", "_knowledge", "_rag.py"], "RAG",
     "static 自动注入 / agentic 暴露 search_knowledge 工具，KnowledgeBase 绑 embedding+vector_store。"),
    (["envelope", "runtime/py", "Envelope"], "Runtime 与 SSE",
     "Envelope 状态机把碎事件翻译成带 seq 标准 SSE，Runtime 8 阶段可插拔 hook。"),
    (["doom_loop", "budget", "iteration", "rubric", "_gates"], "Loop 治理",
     "StopGate 可插拔：doom_loop/budget/iteration/file_loop/rubric 各治一种失控。"),
    (["tool_adapter", "PolicyGuardedTool", "tool_guard", "sandbox"], "权限与沙箱",
     "PolicyGuardedTool 策略+STRICT/SMART/AUTO/OFF 四档+内核级沙箱(macos/linux/windows)防注入逃逸。"),
    (["team_create", "team_say", "message_bus"], "多 Agent 编排",
     "服务层 Team 工具+MessageBus，Leader 动态调度 Worker，非代码 pipeline。"),
    (["function", "_tracing", "token_usage", "langfuse"], "可观测性",
     "TracingMiddleware 出 span，TokenRecordingModelWrapper 监控 token，Budget gate 熔断。"),
]

def match_knowledge_points(disk_path: Path) -> list:
    p = str(disk_path)
    hits = []
    for keys, title, body in KNOWLEDGE_TABLE:
        if any(k.lower() in p.lower() for k in keys):
            hits.append({"title": title, "body": body})
    return hits[:4]


def explain_fallback(code_id, kind, disk_path, defined=None) -> str:
    """构建期 AI 补全入口。执行时由 Task 7 用真实讲解替换占位。
    注意：本函数不能留 TODO 在产物里——构建时必须返回真实文本。
    """
    name = disk_path.name
    if kind == "local":
        return (f"{name} 是本教程的可运行示例代码。它示范了对应周次的核心概念，"
                f"顶部注释含运行前置依赖与预期输出。建议结合左侧源码与对应周文档的"
                f"「动手作业」小节一起阅读。")
    return (f"{name} 来自 agentscope/QwenPaw 框架源码。结合左侧源码与右侧知识点，"
            f"理解框架在该处的设计意图。点「反向链接」可回到引用它的教程章节。")
```

> **注意**：`explain_fallback` 在 Task 7 会被真实的 AI 补全讲解覆盖（针对文档说明不足的 code 条目）。执行者必须确保 **最终产物里没有任何占位文本泄露**——见 Task 8 验收。

- [ ] **Step 3: 自测**

```python
def _selftest_code_entry():
    # 用一个本地代码文件测
    cid = make_code_id("code/w04/quickstart.py")
    e = build_code_entry(cid, "code/w04/quickstart.py", ["code/w04/quickstart.py"], {})
    assert not e.get("missing"), e
    assert e["kind"] == "local"
    assert "code_html" in e and "c-line" in e["code_html"]
    assert isinstance(e["knowledge_points"], list)
    print("PASS build_code_entry (local)")

    e2 = build_code_entry(make_code_id("agent/_agent.py:664"), "agent/_agent.py:664",
                          ["agent/_agent.py:664"], {})
    assert e2["kind"] == "src" and e2["highlight_line"] == 664
    # _agent.py 应命中 ReAct 推理循环 知识点
    titles = [k["title"] for k in e2["knowledge_points"]]
    assert "ReAct 推理循环" in titles or "上下文压缩" in titles, titles
    print("PASS build_code_entry (src)")
```

加进 `_selftest()`。运行期望 PASS。

- [ ] **Step 4: Commit**

```bash
git add build.py && git commit -m "feat(web): build code entries with source/highlight/knowledge"
```

---

## Task 5：文档索引 + 导航树 + 搜索倒排索引

**Files:**
- Modify: `_web/build.py`

**目标**：扫全部 md，生成 doc 条目、tree.js、search.js；同时收集每个 doc 用到的 code_ids（供反向链接）。

- [ ] **Step 1: 加文档扫描与索引构建**

```python
def scan_all_docs():
    """返回 (docs, code_refs_by_id)。
    docs = list of {doc_id,title,stage,html,toc,prev,next,code_ids,explain_paragraphs}
    code_refs_by_id = {code_id: {first_ref, all_refs}}
    """
    docs = []
    code_refs = {}
    # 收集所有 md 按 stage
    files = []
    for stage, d in DOC_DIRS.items():
        for md in sorted(d.glob("*.md")):
            if md.name in ("README.md",):
                continue
            # doc_id：用文件名（去扩展）大写规整，或编号
            doc_id = md.stem
            files.append((stage, doc_id, md))
    # README 单独作为 doc00
    readme = ROOT / "README.md"
    if readme.exists():
        files.insert(0, ("总览", "README", readme))

    # 排序：README → 地基W01..W03 → 框架W04..W08 → 产品W09..W12 → 面试卡 → checklist
    stage_order = {"总览": 0, "地基": 1, "框架": 2, "产品": 3, "面试卡": 4, "checklist": 5}
    files.sort(key=lambda x: (stage_order.get(x[0], 9), x[1]))

    for idx, (stage, doc_id, md) in enumerate(files):
        md_text = md.read_text(encoding="utf-8")
        html = md_to_html(md_text)
        # 收集本篇 code_ids 与 refs
        code_ids = set()
        explain_paragraphs = []
        for m in CODE_REF_RE.finditer(md_text):
            ref = m.group(1)
            cid = make_code_id(ref)
            code_ids.add(cid)
            code_refs.setdefault(cid, {"first_ref": ref, "all_refs": set()})["all_refs"].add(ref)
        # 抽"讲解段落"(含 源码精读/动手作业 标题后的段落)
        for m in re.finditer(r"(源码精读|动手作业|工作原理|精读)[^\n]*\n((?:.+\n?){1,40})", md_text, re.I):
            explain_paragraphs.append(m.group(2))
        title = re.match(r"#\s+(.*)", md_text)
        title = title.group(1) if title else doc_id
        toc = [{"level": int(len(m.group(1))), "text": m.group(2)} for m in re.finditer(r"^(#{1,6})\s+(.*)$", md_text, re.M)]
        docs.append({
            "doc_id": doc_id, "title": title, "stage": stage, "html": html,
            "toc": toc, "prev": None, "next": None,
            "code_ids": code_ids, "explain_paragraphs": explain_paragraphs,
            "path": str(md.relative_to(ROOT)),
        })
    # prev/next
    for i, d in enumerate(docs):
        d["prev"] = docs[i - 1]["doc_id"] if i > 0 else None
        d["next"] = docs[i + 1]["doc_id"] if i + 1 < len(docs) else None
    # 转 set 为 list 便于序列化
    for d in docs:
        d["code_ids"] = sorted(d["code_ids"])
    code_refs = {k: {"first_ref": v["first_ref"], "all_refs": sorted(v["all_refs"])}
                 for k, v in code_refs.items()}
    return docs, code_refs


def build_search_index(docs, code_entries):
    """倒排索引：分词后 {token: [doc_id...]}。简单空格+标点分词(中英混合)。"""
    import re as _re
    def tokenize(s):
        return [w for w in _re.split(r"[\s,，。:：;；()（）\[\]【】{}\"'`/\\|]+", s.lower()) if w]
    inv = {}
    docs_idx = []
    for d in docs:
        tokens = set(tokenize(d["title"]) | tokenize(_re.sub(r"<[^>]+>", "", d["html"]))[:5000])
        docs_idx.append({"doc_id": d["doc_id"], "title": d["title"], "stage": d["stage"]})
        for t in tokens:
            inv.setdefault(t, []).append(d["doc_id"])
    code_idx = [{"code_id": c["code_id"], "title": c.get("title", "")} for c in code_entries if not c.get("missing")]
    return {"inv": inv, "documents": docs_idx, "code_index": code_idx}
```

- [ ] **Step 2: 自测**

```python
def _selftest_index():
    docs, refs = scan_all_docs()
    assert len(docs) >= 25, f"文档应至少 25 篇，实际 {len(docs)}"
    assert any(d["doc_id"] == "README" for d in docs)
    # 应收集到 code 引用
    assert len(refs) > 0, "未识别到代码引用"
    # 抽查一个 code_id
    sample = next(iter(refs))
    assert "first_ref" in refs[sample]
    print(f"PASS scan_all_docs: {len(docs)} docs, {len(refs)} code refs")
```

加进 `_selftest()` 运行期望 PASS。

- [ ] **Step 3: Commit**

```bash
git add build.py && git commit -m "feat(web): doc scan + nav tree + inverted search index"
```

---

## Task 6：写出 dist 数据文件（JS 形式）+ index.html + app.js + style.css

**Files:**
- Create: `_web/build.py` 的 `build_all()` + `_web/dist/index.html` + `assets/app.js` + `assets/style.css`

**目标**：把数据序列化成 `window.__x__={}` 的 .js，生成前端三件套。

- [ ] **Step 1: 在 build.py 加 `write_js` 和 `build_all`**

```python
def write_js(path: Path, var: str, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    # JSON 但用 JS 赋值包裹；ensure_ascii=False 保留中文
    path.write_text(f"window.{var} = {json.dumps(obj, ensure_ascii=False, default=list)};\n",
                    encoding="utf-8")


def build_all():
    print("[1/4] 扫描文档...")
    docs, refs = scan_all_docs()
    print(f"      {len(docs)} 篇文档, {len(refs)} 个代码引用")

    print("[2/4] 构建代码条目...")
    doc_index = {d["doc_id"]: {"code_ids": set(d["code_ids"]),
                               "explain_paragraphs": d["explain_paragraphs"]} for d in docs}
    code_entries = []
    for cid, info in refs.items():
        e = build_code_entry(cid, info["first_ref"], info["all_refs"], doc_index)
        code_entries.append(e)
        write_js(DIST / "data" / "code" / f"{cid}.js", f'__code__["{cid}"]', e) if not e.get("missing") else None
    # code 字典汇总(供前端判断 missing)
    code_map = {e["code_id"]: (False if e.get("missing") else True) for e in code_entries]

    print("[3/4] 写 docs / tree / search...")
    for d in docs:
        dd = {k: v for k, v in d.items() if k not in ("code_ids", "explain_paragraphs")}
        write_js(DIST / "data" / "docs" / f"{d['doc_id']}.js", f'__docs__["{d["doc_id"]}"]', dd)
    tree = {"stages": []}
    cur = None
    for d in docs:
        if not cur or cur["name"] != d["stage"]:
            cur = {"name": d["stage"], "docs": []}
            tree["stages"].append(cur)
        cur["docs"].append({"id": d["doc_id"], "title": d["title"]})
    write_js(DIST / "data" / "tree.js", "__tree__", tree)
    search_idx = build_search_index(docs, code_entries)
    write_js(DIST / "data" / "search.js", "__search__", search_idx)
    # code_map 也写出
    write_js(DIST / "data" / "code_map.js", "__code_map__", code_map)

    print("[4/4] 完成。dist 在:", DIST)
```

> 注：code 的 .js 用 `window.__code__["id"] = {...}` 形式，所以 `write_js` 的 var 参数要写成完整表达式。需调整 write_js 支持 var 含引号/下标——上面 `f'__code__["{cid}"]'` 缺 `window.` 前缀，修正：调用处 var 为 `window.__code__['cid']`。在 Step 1 实现里把 var 拼成完整左值。

- [ ] **Step 2: 写 `dist/index.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>AI Agent 系统学习教程</title>
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<div id="app">
  <aside id="nav"><input id="search" placeholder="搜索文档/代码..." autocomplete="off"><div id="tree"></div></aside>
  <main id="content"><div id="view"></div></main>
  <aside id="toc"></aside>
</div>
<div id="code-map" style="display:none"></div>
<script src="data/tree.js"></script>
<script src="data/code_map.js"></script>
<script src="data/search.js"></script>
<script src="assets/app.js"></script>
</body>
</html>
```

- [ ] **Step 3: 写 `assets/style.css`**（三栏 + 两栏 + 代码高亮配色 + missing 链接标红）

```css
:root{--bg:#fff;--fg:#1a1a1a;--muted:#666;--link:#2563eb;--border:#e5e7eb;--code-bg:#f6f8fa;--kw:#d73a49;--str:#032f62;--com:#6a737d;--hl:#fff3a3}
*{box-sizing:border-box}body{margin:0;font:15px/1.7 -apple-system,system-ui,"PingFang SC",sans-serif}
#app{display:grid;grid-template-columns:240px 1fr 200px;height:100vh}
#nav{border-right:1px solid var(--border);overflow:auto;padding:12px}#search{width:100%;padding:6px;margin-bottom:8px}
#tree .stage{font-weight:700;color:var(--muted);margin:10px 0 4px;font-size:13px}
#tree a{display:block;padding:4px 6px;text-decoration:none;color:var(--fg);border-radius:4px}
#tree a:hover{background:#f0f0f0}#tree a.active{background:#e8f0fe;color:var(--link)}
#content{overflow:auto;padding:24px 32px}#toc{border-left:1px solid var(--border);padding:12px;overflow:auto}
#toc a{display:block;color:var(--muted);text-decoration:none;font-size:13px;padding:2px 0}
a.code-link{color:var(--link);cursor:pointer;border-bottom:1px dotted}a.code-link-missing{color:#dc2626}
.code-page{display:grid;grid-template-columns:1fr 1fr;gap:16px;height:calc(100vh - 48px)}
.code-left{overflow:auto;background:var(--code-bg);border:1px solid var(--border);border-radius:6px;padding:8px}
.code-right{overflow:auto;padding:8px}
.c-line{display:flex;white-space:pre}.c-no{color:#aaa;width:40px;flex:none;text-align:right;padding-right:8px;user-select:none}.c-src{flex:1}
.c-line.hl{background:var(--hl)}.c-kw{color:var(--kw);font-weight:600}.c-str{color:var(--str)}.c-com{color:var(--com);font-style:italic}
.kp{border:1px solid var(--border);border-radius:6px;padding:10px;margin:8px 0}.kp h4{margin:0 0 4px;color:var(--link)}
pre{background:var(--code-bg);padding:12px;border-radius:6px;overflow:auto}table{border-collapse:collapse}td,th{border:1px solid var(--border);padding:4px 8px}
.jump-btn{position:sticky;top:0;background:var(--link);color:#fff;border:0;padding:6px 12px;border-radius:4px;cursor:pointer;z-index:5}
.search-results a{display:block;padding:6px;border-bottom:1px solid var(--border);text-decoration:none;color:var(--fg)}.search-results mark{background:#ffe066}
```

- [ ] **Step 4: 写 `assets/app.js`**（hash 路由 + 按需加载 + 渲染三页 + 搜索）

```javascript
// 全局数据容器
window.__docs__ = window.__docs__ || {};
window.__code__ = window.__code__ || {};
const loaded = {docs:new Set(), code:new Set()};

function el(id){return document.getElementById(id);}
function $(html){const t=document.createElement('template');t.innerHTML=html.trim();return t.content.firstChild;}

function loadScript(src){
  return new Promise((res,rej)=>{
    const s=document.createElement('script');s.src=src;s.onload=res;s.onerror=rej;
    document.head.appendChild(s);
  });
}
async function loadDoc(id){
  if(loaded.docs.has(id)||window.__docs__[id])return window.__docs__[id];
  try{await loadScript('data/docs/'+id+'.js');loaded.docs.add(id);}catch(e){}
  return window.__docs__[id];
}
async function loadCode(id){
  if(loaded.code.has(id)||window.__code__[id])return window.__code__[id];
  try{await loadScript('data/code/'+id+'.js');loaded.code.add(id);}catch(e){}
  return window.__code__[id];
}

function renderTree(activeId){
  const t=el('tree');t.innerHTML='';
  // 补一个 README 入口（在 tree.js 的 总览 stage 里）
  for(const st of window.__tree__.stages){
    const div=$(`<div class="stage">${st.name}</div>`);t.appendChild(div);
    for(const doc of st.docs){
      const a=$(`<a href="#doc/${doc.id}" class="${doc.id===activeId?'active':''}">${doc.title}</a>`);
      t.appendChild(a);
    }
  }
}

async function showDoc(id){
  const d=await loadDoc(id);
  if(!d){el('view').innerHTML='<p>未找到文档 '+id+'</p>';return;}
  renderTree(id);
  el('view').innerHTML = `<div>${d.html}</div>`;
  el('toc').innerHTML = d.toc.map((t,i)=>`<a href="#" data-anchor="${i}">${'　'.repeat(t.level-1)}${t.text}</a>`).join('');
  el('content').scrollTop=0;
  // 绑定 code-link
  el('view').querySelectorAll('a.code-link').forEach(a=>{
    a.onclick=async (e)=>{
      e.preventDefault();
      const cid=a.dataset.code;const ref=a.dataset.ref;
      const m=ref.match(/:(\d+)$/);const L=m?m[1]:null;
      location.hash=`#code/${cid}`+(L?`?L=${L}`:'');
    };
  });
}

async function showCode(cid, L){
  const c=await loadCode(cid);
  if(!c||c.missing){el('view').innerHTML='<p>⚠️ 代码文件未找到(可能源码路径变化)。</p>';el('toc').innerHTML='';renderTree(null);return;}
  renderTree(null);el('toc').innerHTML='';
  // 插入高亮行
  const html=c.code_html;
  el('view').innerHTML=`<div class="code-page">
    <div class="code-left"><button class="jump-btn" onclick="jumpTo(${L||c.highlight_line||1})">跳到 L${L||c.highlight_line||1}</button>${html}</div>
    <div class="code-right">
      <h3>${c.title}</h3>
      <p style="color:#666">${c.source_path}${c.highlight_line?' · 高亮 '+c.highlight_line:''}</p>
      <button onclick="history.back()" style="margin:8px 0">← 返回文档</button>
      <h4>讲解</h4><div>${(c.explanation||'(暂无)').replace(/\n/g,'<br>')}</div>
      <h4>知识点</h4>${(c.knowledge_points||[]).map(k=>`<div class="kp"><h4>${k.title}</h4>${k.body}</div>`).join('')}
      <h4>出现在</h4>${(c.related_docs||[]).map(id=>`<a href="#doc/${id}">${id}</a> `).join('')}
    </div></div>`;
  // 自动滚到高亮行并加 hl 类
  setTimeout(()=>{const hl=L||c.highlight_line;jumpTo(hl);},50);
}

function jumpTo(line){
  const node=document.querySelector(`.c-line[data-line="${line}"]`);
  if(node){node.scrollIntoView({block:'center'});node.classList.add('hl');
    document.querySelectorAll('.c-line.hl').forEach(n=>{if(n!==node)n.classList.remove('hl');});}
}

function doSearch(q){
  if(!q){el('view').innerHTML='<p>输入关键词搜索文档与代码。</p>';return;}
  const inv=window.__search__.inv;const ql=q.toLowerCase().split(/[\s,]+/).filter(Boolean);
  const scores={};
  for(const t in inv){for(const w of ql){if(t.includes(w)){for(const did of inv[t]){scores[did]=(scores[did]||0)+1;}}}}
  const ranked=Object.entries(scores).sort((a,b)=>b[1]-a[1]).slice(0,30);
  const docs=window.__search__.documents;
  el('view').innerHTML='<div class="search-results"><h3>搜索结果: '+q+'</h3>'+
    ranked.map(([did])=>{const d=docs.find(x=>x.doc_id===did);return `<a href="#doc/${did}">${d?d.title:did}<span style="color:#999"> · ${d?d.stage:''}</span></a>`;}).join('')+
    '</div>';
  el('toc').innerHTML='';
}

function route(){
  const h=location.hash.slice(1);
  if(h.startsWith('doc/')){showDoc(h.slice(4));}
  else if(h.startsWith('code/')){const [cid,q]=h.slice(5).split('?');const L=q&&q.startsWith('L=')?q.slice(2):null;showCode(cid,L);}
  else if(h.startsWith('search')){const q=h.split('=')[1]||'';doSearch(decodeURIComponent(q));}
  else{showDoc('README');}
}

// 搜索框
window.addEventListener('DOMContentLoaded',()=>{
  renderTree(null);
  el('search').addEventListener('input',e=>{
    const q=e.target.value.trim();
    if(q)location.hash='#search/q='+encodeURIComponent(q);
  });
  el('search').addEventListener('keydown',e=>{if(e.key==='Enter')route();});
  window.addEventListener('hashchange',route);
  route();
});
```

- [ ] **Step 5: 修正 build.py 里 `write_js` 的 var 拼接（完整左值），跑 `build_all`**

把 build_all 里 code 写出改为：
```python
write_js(DIST / "data" / "code" / f"{cid}.js", f'__code__["{cid}"]', e)
```
并在 `write_js` 里 var 前面统一加 `window.`（若 var 不含 `window.`）：
```python
def write_js(path, var, obj):
    lv = var if var.startswith("window.") else "window." + var
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{lv} = {json.dumps(obj, ensure_ascii=False, default=list)};\n", encoding="utf-8")
```
然后让 `__main__` 默认调 `build_all()`：
```python
if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        _selftest()
        build_all()
```

Run: `cd /Users/zhongyou/Desktop/2027年/_web && python3 build.py`
Expected: 打印 4 步进度，`dist/` 下生成 index.html + assets/ + data/（docs/code/tree/search/code_map 多个 .js）。

- [ ] **Step 6: Commit**

```bash
git add build.py dist/index.html dist/assets/ dist/data/ && git commit -m "feat(web): generate dist static site (html/app.js/css/data)"
```

---

## Task 7：AI 补全讲解（构建期，针对说明不足的 code 条目）

**Files:**
- Modify: `_web/build.py`（`explain_fallback` 真实化）/ 或新增 `_web/explanations.json` 人工/半自动补全

**目标**：对文档说明覆盖不全的 code 条目，补真实讲解文本。**产物里不能有占位字样。**

- [ ] **Step 1: 跑一次构建，识别哪些 code 条目 explanation 为空**

Run: `python3 build.py`，然后：
```bash
cd /Users/zhongyou/Desktop/2027年/_web/dist/data/code
grep -L "explanation" *.js | head   # 列出讲解为空的（实际用 python 查 better）
```
更准：写个一次性脚本 `_web/_check_explain.py`：
```python
import json,re,pathlib
d=pathlib.Path("dist/data/code")
empty=[]
for f in d.glob("*.js"):
    m=re.search(r"explanation\"\s*:\s*\"((?:[^\"\\]|\\.)*)\"",f.read_text())
    if not m or not m.group(1).strip(): empty.append(f)
print("讲解为空的条目数:",len(empty))
# 逆映射 code_id→列出，供下一步补
```

- [ ] **Step 2: 对空讲解条目补真实讲解**

新增 `_web/explanations.json`：`{code_id: "真实讲解文本..."}`。由执行者基于代码内容+所在周文档，为每个空条目写 1-3 句讲解（从代码顶部注释、文件职责、关联周次提炼）。

`build_code_entry` 末尾改成：
```python
extra = EXPLANATIONS.get(code_id)
if extra:
    explanation = extra
elif not explanation:
    explanation = explain_fallback(code_id, kind, disk_path)
```
同时在 build_all 开头加载：
```python
EXPLANATIONS = {}
_ep = Path(__file__).parent / "explanations.json"
if _ep.exists():
    EXPLANATIONS = json.loads(_ep.read_text(encoding="utf-8"))
```

- [ ] **Step 3: 重新构建，校验无占位泄露**

Run: `python3 build.py`
然后检查产物里没有占位字样：
```bash
grep -rn "TODO\|TBD\|占位\|由步骤内" dist/data/code/*.js && echo "FAIL: 有占位" || echo "OK: 无占位"
```
Expected: `OK: 无占位`。

- [ ] **Step 4: Commit**

```bash
git add build.py explanations.json dist/ && git commit -m "feat(web): fill AI-completed explanations for code entries"
```

---

## Task 8：人工验收 + 修复缺失链接

**Files:** 无新建，验收为主

- [ ] **Step 1: 双击 `dist/index.html` 用浏览器打开**（或 `file:///Users/zhongyou/Desktop/2027年/_web/dist/index.html`）

验证清单（对应 SPEC §10）：
- [ ] 左导航树可见全部 README + W01-W12 + 面试卡 10 + checklist 2
- [ ] 点 W04，正文渲染，`agent/_agent.py:664` 是蓝字
- [ ] 点该链接，跳代码页：左整文件源码（664 行高亮+滚到可见），右讲解+知识点+反向链接
- [ ] 左侧"跳到 L664"按钮可跳
- [ ] 代码高亮正常（关键字/字符串/注释着色，离线）
- [ ] 搜索框输入"ReAct"，返回匹配文档/代码
- [ ] 找不到的代码路径（红色链接）标红不报错
- [ ] 上下篇导航 + 反向链接回文档正常

- [ ] **Step 2: 修复发现的问题**

常见问题与修法：
- 某代码链接标红（missing）：查 `resolve_code_ref` 是否漏匹配该写法；可能需补正则分支。
- 高亮行没滚到：检查 `jumpTo` 的 `data-line` 与 `data-line="N"` 匹配。
- Markdown 渲染异常（某表格/列表）：补 `md_to_html` 对应分支。
- 数据加载失败（控制台 404）：检查 docs/code 文件名与 doc_id/code_id 一致。

每修一处重新 `python3 build.py` 后刷新浏览器验证。

- [ ] **Step 3: 最终 Commit**

```bash
git add -A && git commit -m "fix(web): post-acceptance fixes for links/rendering"
```

---

## Self-Review（写完后自查，已执行）

**1. Spec 覆盖**：spec §2 目录→Task6；§3 单元→Task1-6；§4 数据结构→Task4-6；§5 链接体系→Task1+4；§6 讲解来源→Task4+7；§7 交互→Task6 app.js；§8 错误处理→Task6 missing 标红；§9 YAGNI→未做后端等；§10 验收→Task8。全覆盖。
**2. 占位**：仅 `explain_fallback` 有明确的"构建期补全"语义占位，Task7 强制用真实讲解替换且 Task8 校验无占位泄露，非计划疏漏。
**3. 类型一致**：code_id 通过 `make_code_id` 统一生成（Task1），前后端（build.py 产出 / app.js `data-code` 读取）一致；doc_id 用文件 stem，tree.js/docs.js/路由一致。