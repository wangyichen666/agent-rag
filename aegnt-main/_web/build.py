#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建脚本：把 2027年/ 文档+代码生成纯静态 dist/。零三方依赖。
用法：
  python3 build.py --selftest   # 仅跑自测
  python3 build.py              # 自测 + 构建
基于 _web/PLAN.md 的 Task 1-6 实现。
"""
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

DOC_DIRS = {
    "地基": ROOT / "阶段一-地基",
    "框架": ROOT / "阶段二-框架",
    "产品": ROOT / "阶段三-产品",
    "面试卡": ROOT / "面试问答卡",
    "checklist": ROOT / "改造checklist",
}

EXPLANATIONS = {}
_ep = Path(__file__).resolve().parent / "explanations.json"
if _ep.exists():
    EXPLANATIONS = json.loads(_ep.read_text(encoding="utf-8"))


# ============ Task 1: code_id + 路径解析 ============
def make_code_id(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def resolve_code_ref(ref: str):
    """返回 (kind, disk_path, highlight_line) 或 None。
    kind: 'local' | 'src'"""
    # 本地代码 code/w##/x.ext
    m = re.match(r"^code/(w\d+/[\w/]+\.\w+)$", ref)
    if m:
        p = CODE_DIR / m.group(1)
        return ("local", p, None) if p.exists() else None

    # 源码：模块路径.py[:行号]
    m = re.match(r"^(.+?)\.py(?::(\d+))?$", ref)
    if not m:
        m2 = re.match(r"^(.+):(\d+)$", ref)
        if not m2:
            return None
        path_part, line = m2.group(1), int(m2.group(2))
        if not path_part.endswith(".py"):
            path_part += ".py"
    else:
        path_part, line = m.group(1) + ".py", (int(m.group(2)) if m.group(2) else None)

    # 去前缀，保留相对模块路径
    path_part = re.sub(r"^/?(agentscope/src/agentscope|src/agentscope|agentscope)/", "", path_part)
    path_part = re.sub(r"^/?(QwenPaw-main/src/qwenpaw|src/qwenpaw|qwenpaw)/", "", path_part)
    path_part = path_part.lstrip("/")

    for base in (AS_SRC, QP_SRC):
        cand = base / path_part
        if cand.exists():
            return ("src", cand, line)
        if "/" not in path_part:  # 纯文件名回退
            hit = list(base.rglob(path_part))
            if hit:
                return ("src", hit[0], line)
    return None


# ============ Task 2: Markdown → HTML + 代码链接 ============
CODE_REF_RE = re.compile(
    r"(?<![A-Za-z0-9/])"
    r"((?:code/w\d+/[\w/]+\.\w+)"
    r"|(?:[A-Za-z0-9_][\w/]*\.py(?:\:\d+)?))"
)


def inline_md(text: str) -> str:
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", lambda m: f'<code class="inline">{html_lib.escape(m.group(1))}</code>', text)

    def repl(m):
        ref = m.group(1)
        cid = make_code_id(ref)
        resolved = resolve_code_ref(ref)
        cls = "code-link" + ("" if resolved else " code-link-missing")
        return f'<a class="{cls}" data-code="{cid}" data-ref="{html_lib.escape(ref)}">{html_lib.escape(ref)}</a>'

    text = CODE_REF_RE.sub(repl, text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                  lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)
    return text


def md_to_html(md: str) -> str:
    lines = md.split("\n")
    out, i = [], 0
    in_code, code_buf = False, []
    in_list = False
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            if not in_code:
                in_code, code_buf = True, []
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
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            if in_list:
                out.append("</ul>"); in_list = False
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline_md(m.group(2))}</h{lvl}>")
            i += 1
            continue
        if line.strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[i + 1].strip()):
            if in_list:
                out.append("</ul>"); in_list = False
            out.append("<table>")
            out.append("<tr>" + "".join(f"<th>{inline_md(c.strip())}</th>" for c in line.strip().strip("|").split("|")) + "</tr>")
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = lines[i].strip().strip("|").split("|")
                out.append("<tr>" + "".join(f"<td>{inline_md(c.strip())}</td>" for c in cells) + "</tr>")
                i += 1
            out.append("</table>")
            continue
        if re.match(r"^\s*[-*]\s+", line):
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append(f"<li>{inline_md(re.sub(r'^\s*[-*]\s+', '', line))}</li>")
            i += 1
            continue
        if in_list:
            out.append("</ul>"); in_list = False
        if not line.strip():
            out.append("")
            i += 1
            continue
        out.append(f"<p>{inline_md(line)}</p>")
        i += 1
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


# ============ Task 3: 代码高亮（零依赖） ============
PY_KEYWORDS = ["def","class","return","if","elif","else","for","while","try","except",
    "finally","with","import","from","as","async","await","yield","lambda","None","True",
    "False","self","in","not","and","or","is","pass","break","continue","raise","global",
    "nonlocal","assert","del"]

def highlight_python(code: str) -> str:
    """占位法：先 escape，把字符串/注释段换成唯一占位（防关键字正则误伤已插入的标签），
    再做关键字高亮，最后还原占位。"""
    out = ['<div class="code-body">']
    kw_re = re.compile(r"\b(" + "|".join(PY_KEYWORDS) + r")\b")
    placeholders = []

    def stash(html_seg):
        placeholders.append(html_seg)
        return f"\x00{len(placeholders) - 1}\x00"

    for idx, line in enumerate(code.split("\n"), 1):
        esc = html_lib.escape(line)
        # 字符串先占位（含三引号跨行不在单行处理范围，单行 "..." '...' 足够阅读用）
        esc = re.sub(r'(&quot;.*?&quot;|&#x27;.*?&#x27;)',
                     lambda m: stash(f'<span class="c-str">{m.group(1)}</span>'), esc)
        # 注释占位
        esc = re.sub(r'(#.*)$',
                     lambda m: stash(f'<span class="c-com">{m.group(1)}</span>'), esc)
        # 关键字（现在不会碰到已插入的 span 标签了）
        esc = kw_re.sub(r'<span class="c-kw">\1</span>', esc)
        # 还原占位
        def restore(m):
            return placeholders[int(m.group(1))]
        esc = re.sub(r"\x00(\d+)\x00", restore, esc)
        out.append(f'<div class="c-line" data-line="{idx}"><span class="c-no">{idx}</span><span class="c-src">{esc or "&nbsp;"}</span></div>')
    out.append("</div>")
    return "\n".join(out)


# ============ Task 4: code 条目 + 知识点 ============
KNOWLEDGE_TABLE = [
    (["_reply_impl", "_reasoning", "_check_next_action", "agent/_agent.py", "agent/__init__"], "统一 Agent 内核 / ReAct 推理循环",
     "2.0 只有统一 Agent 类（组合>继承）。_reply_impl 内建 reasoning-acting 循环：_check_next_action 决定退出还是继续推理，max_iters 默认 20 兜底。Thought→Action→Observation 交替。"),
    (["compress_context", "summary_schema", "summaryschema", "agent/_config.py", "_compress_context"], "上下文压缩",
     "超 trigger_ratio(0.8) 触发，按 reserve_ratio(0.1) 切分，用 SummarySchema 五字段（task_overview/current_state/important_discoveries/next_steps/context_to_preserve）做结构化摘要替换历史，非简单截断。"),
    (["toolkit", "_toolkit", "call_tool", "_adapters", "functiontool", "_tool_group", "resettools"], "工具体系",
     "Toolkit 统管；FunctionTool 从签名+docstring 自动 schema；MCPTool 远端代理；call_tool 统一执行；ToolGroup 分组按需激活，ResetTools 元工具切换（最终状态非增量）。"),
    (["_mcp_client", "mcp/_config", "stdiomcpconfig", "httpmcpconfig"], "MCP 客户端",
     "MCPClient 连 Server，list_tools 动态发现；StdioMCPConfig/HttpMCPConfig 两种传输；stdio 必须 stateful 且显式 connect/close。"),
    (["ragmiddleware", "_knowledge.py", "_rag.py", "approx_token_chunker", "_vdb", "_parser"], "RAG",
     "static（RAGMiddleware 自动检索 HintBlock 一次注入） / agentic（暴露 search_knowledge 工具主动搜）；KnowledgeBase 绑 embedding+vector_store；parser→chunker→embed 入库。"),
    (["envelope.py", "runtime/runtime", "executor.py", "builder.py", "agentscope/_router"], "Runtime 与 SSE 工业化",
     "Envelope 状态机把碎 AgentEvent 翻译成带 seq 标准 SSE；Runtime 8 阶段可插拔 hook（鉴权/限流/审计）；AgentBuilder 依赖注入式组装。框架 reply_stream 是原料，这层是加工线。"),
    (["loop/gates", "doom_loop", "budget.py", "iteration.py", "rubric.py", "file_loop", "loop_gate.py"], "Loop 治理（Loop Engineering）",
     "StopGate 可插拔：DoomLoopGate（死循环）/BudgetGate（超预算）/IterationGate（超迭代）/FileLoopGate（文件循环）/RubricGate（评分不达标）各治一种失控，比单靠 max_iters 精准。"),
    (["tool_adapter", "policyguardedtool", "tool_guard", "sandbox", "execution_level"], "权限与沙箱",
     "PolicyGuardedTool 策略引擎 + STRICT/SMART/AUTO/OFF 四档执行级别 + 内核级沙箱（macOS Seatbelt / Linux bubblewrap·landlock / Windows AppContainer）防 prompt 注入逃逸；ApprovalService 人在回路。"),
    (["team_create", "team_say", "team_delete", "agent_create", "message_bus", "multi_agent_manager", "_session.py"], "多 Agent 编排",
     "服务层 Team 工具（TeamCreate/AgentCreate/TeamSay）+ MessageBus（InMemory/Redis）；Leader 动态调度 Worker；非 1.0 代码 pipeline；MultiAgentManager 管生命周期零停机重载。"),
    (["_tracing", "token_usage", "langfuse", "model_wrapper", "_attributes"], "可观测性",
     "TracingMiddleware 出 agent/llm/tool 三类 OTel span；TokenRecordingModelWrapper 包装模型记 token；TokenUsageManager 聚合；Langfuse 产品侧看板；Budget gate 熔断。"),
    (["generate_structured_output", "_event.py", "message/_base", "message/_block", "_model_response"], "消息与事件",
     "Msg.content 是 ContentBlock 列表（Text/Thinking/ToolCall/ToolResult/Data/HintBlock）；reply_stream 是 AsyncGenerator[AgentEvent]；文本增量取 .delta；generate_structured_output 用工具调用模拟强制结构化输出。"),
    (["model/_base.py", "model/_model_response", "_model_usage", "chatmodelbase"], "模型调用基类",
     "ChatModelBase.__call__ 是统一入口（async），max_retries 重试+流式累加；generate_structured_output 强制结构化；换 provider 只换 model 类+credential，业务代码不改（Formatter 隔离）。"),
    (["credential/", "_credential", "credentialbase"], "凭证管理",
     "CredentialBase 子类（DashScope/OpenAI/Anthropic...）存 api_key 为 SecretStr；model+credential 配对使用。"),
    (["middleware/_budget", "replybudgetcontrol"], "预算控制中间件",
     "ReplyBudgetControlMiddleware 代理回复预算，超即熔断；与 BudgetGate呼应，控单次回复 token。"),
    (["embedding/", "embeddingmodel"], "向量化模型",
     "DashScopeEmbeddingModel 等，dimensions 必填（v4 用 1024）；RAG 入库的向量化用此类。"),
    (["formatter/", "_formatter_base", "_dashscope_formatter", "_anthropic_formatter"], "Formatter 模型适配",
     "把统一 Msg 翻译成各 provider 原生格式；每 provider 双格式化器（Chat 单 Agent / MultiAgent 折叠 history）；换 provider 业务代码不改。"),
    (["react_agent.py", "codingmode"], "QwenPawAgent 产品扩展",
     "QwenPawAgent(CodingModeMixin, Agent) 继承框架 Agent 二次扩展：重写 compress_context（Scroll 策略）、_reasoning（媒体剥离+停止门控接入）、state_dict（持久化+1.x 迁移）。框架给块，产品加料。"),
    (["drivers/handlers/mcp", "agentscope_tool.py", "drivers/adapters"], "Driver 协议中立层",
     "QwenPaw 的协议中立连接器：MCPDriverHandler 处理 MCP 传输，DriverCapabilityTool(ToolBase) 把外部能力包成 agentscope 工具，check_permissions 嵌入权限。"),
]


def match_knowledge_points(disk_path: Path) -> list:
    p = str(disk_path).lower()
    hits = []
    for keys, title, body in KNOWLEDGE_TABLE:
        if any(k.lower() in p for k in keys):
            hits.append({"title": title, "body": body})
    return hits[:4]


def explain_fallback(code_id, kind, disk_path) -> str:
    name = disk_path.name
    if kind == "local":
        return (f"{name} 是本教程的可运行示例代码，示范对应周次核心概念；"
                f"顶部注释含运行前置依赖与预期输出，建议结合左侧源码与对应周文档「动手作业」一起读。")
    return (f"{name} 来自 agentscope/QwenPaw 框架源码。结合左侧源码与右侧知识点理解此处设计意图；"
            f"点「反向链接」可回到引用它的教程章节。")


def build_code_entry(code_id, ref_first, refs, doc_index):
    resolved = resolve_code_ref(ref_first)
    if not resolved:
        return {"code_id": code_id, "missing": True, "ref": ref_first,
                "title": ref_first, "source_path": "", "highlight_line": None,
                "code_html": "", "explanation": "（源码文件未找到，可能路径已变化）",
                "knowledge_points": [], "related_docs": []}
    kind, disk_path, hl = resolved
    try:
        code_text = disk_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {"code_id": code_id, "missing": True, "ref": ref_first,
                "title": ref_first, "source_path": "", "highlight_line": None,
                "code_html": "", "explanation": "（读取失败）",
                "knowledge_points": [], "related_docs": []}
    if disk_path.suffix == ".py":
        code_html = highlight_python(code_text)
    else:
        code_html = "<pre>" + html_lib.escape(code_text) + "</pre>"

    related, explanation_parts = [], []
    for doc_id, dinfo in doc_index.items():
        if code_id in dinfo["code_ids"]:
            related.append(doc_id)
            # 该 code 出现在此 doc，直接取此 doc 的讲解段落（不强求 ref 逐字出现，
            # 因为每周文档的「源码精读」段落就是讲这些引用文件的）
            for para in dinfo["explain_paragraphs"][:2]:
                explanation_parts.append(f"【{doc_id}】" + para)
    explanation = "\n\n".join(explanation_parts[:4]) if explanation_parts else ""
    kps = match_knowledge_points(disk_path)

    extra = EXPLANATIONS.get(code_id)
    if not extra:
        name = disk_path.name
        # 歧义文件名按所在目录选带后缀的 key
        p = str(disk_path).lower()
        if name == "_base.py":
            extra = EXPLANATIONS.get("_base.py-MODEL" if "model" in p else "_base.py-MSG" if "message" in p else name)
        elif name == "_model.py":
            extra = EXPLANATIONS.get("_model.py-EMB" if "embedding" in p else "_model.py-DS")
        elif name == "base.py":
            extra = EXPLANATIONS.get("base.py-GATE" if "loop" in p else name)
        elif name == "_rag.py":
            extra = EXPLANATIONS.get("_rag.py-MW" if "middleware" in p else name)
        else:
            extra = EXPLANATIONS.get(name)
        if not extra:
            extra = EXPLANATIONS.get(name)
    if extra:
        explanation = extra
    elif not explanation:
        explanation = explain_fallback(code_id, kind, disk_path)

    try:
        rel = str(disk_path.relative_to(Path("/Users/zhongyou/Desktop/github")))
    except ValueError:
        rel = str(disk_path)
    title = disk_path.name + (f":{hl}" if hl else "")
    return {
        "code_id": code_id, "kind": kind, "title": title,
        "source_path": rel, "highlight_line": hl,
        "code_html": code_html, "lines": code_text.count("\n") + 1,
        "explanation": explanation, "knowledge_points": kps,
        "related_docs": related,
    }


# ============ Task 5: 文档索引 + tree + search ============
def scan_all_docs():
    files = []
    readme = ROOT / "README.md"
    if readme.exists():
        files.append(("总览", "README", readme))
    for stage, d in DOC_DIRS.items():
        for md in sorted(d.glob("*.md")):
            files.append((stage, md.stem, md))

    stage_order = {"总览": 0, "地基": 1, "框架": 2, "产品": 3, "面试卡": 4, "checklist": 5}
    files.sort(key=lambda x: (stage_order.get(x[0], 9), natural_key(x[1])))

    docs, code_refs = [], {}
    for idx, (stage, doc_id, md) in enumerate(files):
        md_text = md.read_text(encoding="utf-8")
        html = md_to_html(md_text)
        code_ids = set()
        for m in CODE_REF_RE.finditer(md_text):
            ref = m.group(1)
            cid = make_code_id(ref)
            code_ids.add(cid)
            code_refs.setdefault(cid, {"first_ref": ref, "all_refs": set()})
            code_refs[cid]["all_refs"].add(ref)
        explain_paragraphs = []
        for m in re.finditer(r"(源码精读|动手作业|工作原理|精读)[^\n]*\n((?:.+\n?){1,40})", md_text, re.I):
            explain_paragraphs.append(m.group(2).strip())
        tm = re.match(r"#\s+(.*)", md_text)
        title = tm.group(1) if tm else doc_id
        toc = [{"level": len(m.group(1)), "text": m.group(2)}
               for m in re.finditer(r"^(#{1,6})\s+(.*)$", md_text, re.M)]
        docs.append({"doc_id": doc_id, "title": title, "stage": stage, "html": html,
                     "toc": toc, "prev": None, "next": None,
                     "code_ids": code_ids, "explain_paragraphs": explain_paragraphs,
                     "path": str(md.relative_to(ROOT))})
    for i, d in enumerate(docs):
        d["prev"] = docs[i - 1]["doc_id"] if i > 0 else None
        d["next"] = docs[i + 1]["doc_id"] if i + 1 < len(docs) else None
    for d in docs:
        d["code_ids"] = sorted(d["code_ids"])
    code_refs = {k: {"first_ref": v["first_ref"], "all_refs": sorted(v["all_refs"])}
                 for k, v in code_refs.items()}
    return docs, code_refs


def natural_key(s):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def build_search_index(docs, code_entries):
    def tokenize(s):
        return [w for w in re.split(r"[\s,，。:：;；()（）\[\]【】{}\"'`/\\|]+", s.lower()) if w]
    inv, docs_idx = {}, []
    for d in docs:
        plain = re.sub(r"<[^>]+>", " ", d["html"])
        tokens = set(tokenize(d["title"])) | set(tokenize(plain))
        docs_idx.append({"doc_id": d["doc_id"], "title": d["title"], "stage": d["stage"]})
        for t in tokens:
            inv.setdefault(t, []).append(d["doc_id"])
    code_idx = [{"code_id": c["code_id"], "title": c.get("title", "")}
                for c in code_entries if not c.get("missing")]
    return {"inv": inv, "documents": docs_idx, "code_index": code_idx}


# ============ Task 6: 写出 dist ============
def write_js(path: Path, var: str, obj):
    lv = var if var.startswith("window.") else "window." + var
    path.parent.mkdir(parents=True, exist_ok=True)
    # 若是带下标赋值（如 __code__["id"]），前置对象初始化，避免首加载时 undefined
    init = ""
    m = re.match(r'window\.(\w+)\[', lv)
    if m:
        init = f"window.{m.group(1)} = window.{m.group(1)} || {{}};\n"
    path.write_text(f"{init}{lv} = {json.dumps(obj, ensure_ascii=False, default=list)};\n",
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
        if not e.get("missing"):
            write_js(DIST / "data" / "code" / f"{cid}.js", f'__code__["{cid}"]', e)
        else:
            write_js(DIST / "data" / "code" / f"{cid}.js", f'__code__["{cid}"]', e)
    code_map = {e["code_id"]: (not e.get("missing")) for e in code_entries}

    print("[3/4] 写 docs / tree / search / code_map ...")
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
    write_js(DIST / "data" / "search.js", "__search__", build_search_index(docs, code_entries))
    write_js(DIST / "data" / "code_map.js", "__code_map__", code_map)

    print(f"[4/4] 完成。dist 在: {DIST}")
    print(f"      docs={len(docs)} code_entries={len(code_entries)} "
          f"missing={sum(1 for e in code_entries if e.get('missing'))}")


# ============ 自测 ============
def _selftest():
    ok = True
    # Task1
    for ref, expected in [
        ("code/w04/quickstart.py", ("local", CODE_DIR / "w04" / "quickstart.py", None)),
        ("agent/_agent.py:664", ("src", AS_SRC / "agent" / "_agent.py", 664)),
        ("runtime/envelope.py:27", ("src", QP_SRC / "runtime" / "envelope.py", 27)),
    ]:
        got = resolve_code_ref(ref)
        if got != expected:
            print(f"FAIL resolve {ref!r}: got {got} want {expected}"); ok = False
        else:
            print(f"PASS resolve {ref!r}")
    g = resolve_code_ref("_agent.py:100")
    assert g and g[0] == "src" and g[2] == 100, f"fallback fail: {g}"
    print("PASS resolve fallback _agent.py:100")

    # Task2
    md = "# 标题\n## 二级\n看 `agent/_agent.py:664` 和 code/w04/quickstart.py\n"
    h = md_to_html(md)
    assert "<h1>" in h and 'data-code="' in h and ">agent/_agent.py:664</a>" in h, h
    print("PASS md_to_html + code link")

    # Task3
    hh = highlight_python("def f():\n    return 'x'  # hi\n")
    assert 'data-line="1"' in hh and 'data-line="2"' in hh and 'c-kw' in hh and 'c-str' in hh and 'c-com' in hh
    print("PASS highlight_python")

    # Task4
    e = build_code_entry(make_code_id("code/w04/quickstart.py"), "code/w04/quickstart.py",
                         ["code/w04/quickstart.py"], {})
    assert not e.get("missing") and e["kind"] == "local" and "c-line" in e["code_html"]
    print("PASS build_code_entry (local)")
    e2 = build_code_entry(make_code_id("agent/_agent.py:664"), "agent/_agent.py:664",
                          ["agent/_agent.py:664"], {})
    assert e2["kind"] == "src" and e2["highlight_line"] == 664
    print("PASS build_code_entry (src)")

    # Task5
    docs, r2 = scan_all_docs()
    assert len(docs) >= 25 and len(r2) > 0, f"docs={len(docs)} refs={len(r2)}"
    print(f"PASS scan_all_docs: {len(docs)} docs, {len(r2)} code refs")
    print("ALL OK" if ok else "HAS FAILURES")
    return ok


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(0 if _selftest() else 1)
    if not _selftest():
        print("自测失败，中止构建"); sys.exit(1)
    build_all()