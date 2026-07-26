# 设计文档 · 教程 Web 阅读站（纯静态）

> 日期：2026-07-14
> 目标：把 `2027年/` 下的 26 篇文档 + 30 个代码 + 面试卡/checklist 做成一个可双击打开的纯静态 Web 站，文档里的代码提及可点击跳到「代码展示页」（整文件源码 + 讲解 + 知识点 + 反向链接），带全文搜索。

---

## 1. 范围与约束（已确认）

- **形态**：纯静态站点。最终产物双击 `index.html` 用 `file://` 协议即可看，**无需启动服务、无需 node**。Python 仅在「构建期」用一次。
- **范围**：全部内容——12 周文档 + 导读 + 面试卡 10 张 + 改造 checklist 2 份 + 对应代码。
- **讲解来源**：复用文档已有讲解（源码精读/动手作业小节）+ 面试卡知识点匹配 + AI 构建期补全。**全部预生成进静态数据，前端不联网**。
- **链接**：自动识别文档里所有代码路径（本地 `code/w##/x.py` + 源码 `path/x.py:行号`）。
- **源码展示**：整文件全文（即使上千行），引用行高亮 + 自动滚到该行 + 「跳到引用行」按钮。
- **代码高亮**：构建期预生成（离线可用，无 CDN 依赖）。
- **全文搜索**：首版做。构建期生成倒排索引，前端 JS 搜。
- **使用场景**：本地自用，但产物自包含（用到的源码片段/全文已内嵌），挪到哪都能看。

## 2. 目录结构

```
2027年/_web/
├── SPEC.md                      # 本文件
├── build.py                     # 构建脚本（Python，零三方依赖）
├── dist/                        # 构建产物（双击 index.html 即看）
│   ├── index.html
│   ├── assets/
│   │   ├── app.js               # 前端逻辑（原生 JS，hash 路由，无框架）
│   │   └── style.css
│   └── data/
│       ├── tree.js              # window.__tree__ = {...}  导航树
│       ├── search.js            # window.__search__ = {...}  搜索倒排索引
│       ├── docs/W##.js          # window.__docs__["W##"] = {...}  每篇文档（按需加载）
│       └── code/<code_id>.js    # window.__code__["<id>"] = {...}  每段代码（按需加载）
```

数据用 `.js`（`window.__xxx__ = {...}`）而非 `.json`，因为 `file://` 协议下 `fetch()` 本地 JSON 会被 CORS 拦截，而 `<script>` 加载不受限。这是纯静态 + 双击打开的标准套路。

## 3. 三个单元的职责边界

### 3.1 build.py（构建脚本，单一职责拆函数）

| 函数 | 职责 | 依赖 |
|---|---|---|
| `parse_markdown(md_text) -> html` | Markdown → HTML（标题层级、代码块、表格） | Python 标准库或自带轻量转换 |
| `scan_code_links(html, doc_id) -> html` | 正则识别代码路径，替换成 `<a class=code-link data-code=...>`；收集本篇用到的 code_id | 无 |
| `build_code_entry(code_id) -> dict` | 为一个 code_id 生成展示数据：读代码全文（本地 code/ 或 agentscope/QwenPaw 源码）+ 抽文档讲解 + 匹配知识点 + 算反向链接 | 文档索引、源码磁盘 |
| `build_search_index(docs) -> dict` | 对所有文档标题+正文+代码标题分词，建倒排 | docs 列表 |
| `write_data_js(path, var, obj)` | 序列化成 `window.__var__ = {...}` 写文件 | 无 |

每个函数单一职责，可独立测试。

### 3.2 dist/index.html + assets/app.js（前端）

| 函数 | 职责 |
|---|---|
| `router()` | hash 路由分发：`#doc/<id>` / `#code/<id>` / `#search?q=` |
| `render_doc(doc_id)` | 渲染文档三栏；代码链接绑定点击 → 路由到代码页 |
| `render_code(code_id, from_line)` | 渲染代码两栏；左栏整文件+引用行高亮+滚动；右栏讲解/知识点/反向链接 |
| `render_search(query)` | 渲染搜索结果 |
| `load_data(kind, id)` | 按需 `<script>` 注入加载 docs/code 数据 |

## 4. 数据结构

### 4.1 code 数据（`data/code/<code_id>.js`）
```json
{
  "code_id": "src-agentscope-agent-_agent-py-L664",
  "kind": "src | local",
  "title": "Agent._reply_impl（推理循环）",
  "source_path": "src/agentscope/agent/_agent.py",
  "highlight_line": 664,              // 默认高亮行（src 才有，local 无）；前端可被 hash ?L= 覆盖
  "language": "python",
  "code": "...整文件全文（已读好内嵌）...",
  "lines": 2837,                       // 总行数
  "explanation": "这是 reasoning-acting 核心循环...",  // 文档抽取 + AI 补全
  "knowledge_points": [
    {"title": "ReAct 循环", "body": "Thought→Action→Observation 交替..."}
  ],
  "related_docs": ["W04", "W03"]       // 反向链接：哪些文档提到它
}
```

### 4.2 doc 数据（`data/docs/W##.js`）
```json
{
  "doc_id": "W04",
  "title": "W04 · AgentScope 入门与 Agent 内核",
  "stage": "框架",                      // 地基/框架/产品/面试卡/checklist
  "html": "...文档 HTML，代码引用已替换成 <a class=code-link>...",
  "toc": [{"level":2,"text":"3. 源码精读","anchor":"sec-3"}],
  "prev": "W03", "next": "W05"
}
```

### 4.3 tree（`data/tree.js`）
```json
{"stages": [
  {"name":"地基","docs":[{"id":"W01","title":"..."},{"id":"W02","title":"..."},...]},
  {"name":"框架","docs":[...]},
  {"name":"产品","docs":[...]},
  {"name":"面试卡","docs":[{"id":"Q01","title":"..."},...]},
  {"name":"checklist","docs":[...]}
]}
```

### 4.4 search（`data/search.js`）
```json
{
  "documents": [
    {"doc_id":"W04","title":"...","stage":"框架",
     "tokens":["agent","内核","reply_impl",...]}
  ],
  "code_index": [
    {"code_id":"...","title":"...","tokens":["_reply_impl",...]}
  ]
}
```

## 5. 链接识别与 code_id 体系

文档里两类代码引用，正则自动识别：

| 类型 | 文档写法 | code_id 规则 | 展示 |
|---|---|---|---|
| 本地代码 | `code/w04/quickstart.py` | `local-<周>-<文件名>` | 整文件全文，无固定高亮行 |
| 源码 | `agent/_agent.py:664` | `src-<去符号路径>-L664` | 整文件全文，664 行高亮+自动滚 |

- code_id 全小写、点/斜杠/下划线转连字符，保证文件名安全。
- 同一文件多行引用（如 `:664` 和 `:327`）合并成一个 code_id（取首个行号为 highlight_line）或分别建条目（首版：合并成一个，highlight 取文档首次出现的行，避免重复存大文件）。**首版策略：同一源码文件只存一份整文件数据，多个引用共享，highlight_line 随点击的行变化（前端用 hash 带 `#code/<id>?L=664` 指定高亮行）。**

## 6. 讲解内容来源（构建期生成）

| 内容 | 来源 | 落地 |
|---|---|---|
| explanation（段讲解） | 文档「源码精读/动手作业」小节按 code_id 归并抽取 | 抽不到的，构建期 AI 补全 |
| knowledge_points | 面试卡 + 文档「原理铺垫」按主题词匹配 | 缺失项构建期 AI 补全 |
| related_docs | 反向扫描哪些文档引用此 code_id | 全自动 |

**AI 补全仅在构建期一次性生成、写死进 JS**，前端零网络。

## 7. 前端交互

### 7.1 文档页（三栏）
左导航树（按 stage 分组，当前页高亮）｜中正文（代码路径为蓝字链接）｜右目录（标题锚点）。上下篇导航。

### 7.2 代码页（两栏）
左：整文件 + 行号 + 引用行高亮 + 自动滚到引用行 + 顶部「跳到 L664」按钮。
右：讲解 + 知识点卡片 + 反向链接（点击回文档）+「返回文档」按钮。

### 7.3 搜索
顶部搜索框，输入实时搜倒排索引，结果列表（文档标题+片段高亮 / 代码标题），点击跳转。

## 8. 错误处理
- 代码路径找不到对应文件 → 链接标红 + 悬停「未找到」，不阻断阅读。
- 数据加载失败 → 友好提示。

## 9. 不做（YAGNI）
- 不做后端、不做数据库、不做用户系统。
- 不做在线编辑/运行代码。
- 不做暗色主题切换（首版单主题，留 CSS 变量便于后加）。
- 不做多语言。

## 10. 验收标准
1. 双击 `dist/index.html`，浏览器打开，左侧导航树可见全部 12 周+面试卡+checklist。
2. 点任意周文档，正文渲染，代码路径是可点击蓝字。
3. 点代码链接，跳代码页：左整文件源码 + 引用行高亮滚动，右讲解+知识点+反向链接。
4. 搜索框输入关键词，返回匹配文档和代码。
5. 代码高亮正常（离线，无 CDN）。
6. 文档里找不到的代码路径标红提示，不报错。