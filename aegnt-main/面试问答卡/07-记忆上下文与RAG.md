# 面试问答卡 07 · 记忆、上下文与 RAG

> 覆盖：W7 / W8。对应 JD：上下文窗口管理、长短期记忆机制、RAG/向量检索。

---

## Q1：Agent 的记忆分几层？上下文压缩怎么工作？为什么是结构化的？

### 【模范回答】

Agent 记忆分三层，从短到长。

**第一层短期记忆**，就是 `AgentState.context`——对话消息历史，每轮推理喂给模型的那一坨。这是最基础的记忆，但问题是它会越来越长，最终超出模型上下文窗口。这就是我 W3 手写 ReAct 时撞上的第一个坑：跑几轮历史就堆成山。

**第二层上下文压缩**，治的就是上面这个病。框架在每轮推理前检查 token，当占用超过 `trigger_ratio`（默认 0.8，即上下文 80%）时触发压缩。怎么压？关键——**不是简单截断尾巴，而是让模型生成一份结构化摘要**。它把 SummarySchema（五字段：task_overview 核心请求、current_state 已完成、important_discoveries 关键发现/踩过的坑、next_steps 待办、context_to_preserve 要保留的偏好）包装成一个工具，调 `generate_structured_output` 让模型按这五段产出摘要，再用 `summary_template` 渲染，最后用这份摘要替换掉旧的历史消息。留 10%（`reserve_ratio`）的近期消息不压，保证最近上下文连贯。

**为什么是结构化而不是散文摘要**？这是设计精髓。如果只让模型「概括一下对话」，它容易丢关键信息——尤其是「我做到哪了、踩过什么坑、下一步干啥」。结构化五字段强制模型把「任务进度档案」写全：当前状态、重要发现、下一步、要保留的约束。这样压缩后 Agent 接着干，长程任务不漂——它知道自己干到哪、发现了什么、接下来该干嘛。比截断尾巴聪明得多，这是框架能支撑长任务的关键。我手写时只会砍掉旧消息，框架这套结构化压缩是真的「会总结进度」。

**第三层长期记忆**，解决「跨会话记住」的问题。短期 context 只在单次会话，会话结束就没了。长期记忆有三种方案：**AgenticMemory**——Agent 自己往工作目录写 Markdown（`Memory/MEMORY.md` + 主题文件），零外部依赖、透明可控，你能直接看它记了啥；**Mem0**——接 mem0 服务，跨 session 记忆，适合多用户共享记忆；**ReMe**——嵌入式，后台自动记录 + 向量检索，省心但黑盒。选型看需求：要透明可控零依赖选 AgenticMemory，要跨会话/多用户选 Mem0，要省心自动选 ReMe。

这三层 + 工具结果截断（`tool_result_limit=50000`，工具返回超 5 万 token 截断，治我手写时的第二个坑），构成了完整的上下文治理。W03 我手写撞的「上下文爆炸」「工具结果过长」两个坑，框架这里一次性解决了。

> **要点速记**：① 三层——短期(context历史)/压缩(超80%触发结构化SummarySchema五字段摘要)/长期(AgenticMemory文件/Mem0跨session/ReMe嵌入式)；② 压缩不是截断是结构化总结，五字段=任务进度档案防长程漂；③ 长期记忆选型：透明选AgenticMemory/跨会话选Mem0/省心选ReMe；④ 工具结果 tool_result_limit=50000 截断。
>
> **源码佐证**：`_compress_context_impl`（`agent/_agent.py:327`，触发阈值 `:351`、切分 `:382`、调 structured output `:465`、模板渲染 `:520`、替换 state `:536-537`，循环内调用点 `:759`）；SummarySchema（`_config.py:9`）；ContextConfig（`:51`：trigger_ratio=0.8/reserve_ratio=0.1/tool_result_limit=50000）；三种长期记忆中间件（`middleware/_longterm_memory/_agentic_memory/_middleware.py:208` 等）。
>
> **压轴一句话**：三层记忆——短期是历史、压缩超80%触发结构化五字段摘要（任务进度档案防漂，不是截断）、长期三选一看跨不跨session；工具结果超5万token截断——手写撞的坑框架全填了。

---

## Q2：RAG 的两种模式是什么？怎么选？怎么搭一条 RAG 链路？

### 【模范回答】

RAG，检索增强生成，核心是「先检索相关片段，再把它塞进 prompt 让模型基于查到的证据回答」，避免模型瞎编。agentscope 提供两种注入模式，区别在「谁来决定检索时机」。

**static 模式**：用 `RAGMiddleware`，在用户首轮提问时**自动检索**，把命中的片段用 `HintBlock`（给模型的隐式提示，不回显给用户）**一次性注入**。模型是**被动**看到这些资料然后回答。优点是简单省事，用户不用管检索；缺点是模型没法决定「要不要再查、查什么」，复杂多步检索做不到。

**agentic 模式**（默认）：暴露一个 `search_knowledge` 工具给 Agent，模型**主动**决定何时检索、检索什么、检索几次。比如模型可以先查 A 主题，看完发现不够再查 B，多轮检索直到信息够了再回答。模型是主动的。

**怎么选**：简单问答（单次检索够）用 static 省事；复杂多步检索（要多次查询、动态判断信息够不够）用 agentic。生产默认推荐 agentic，灵活。

**怎么搭一条 RAG 链路**，分两阶段。**建库阶段**：解析文档（parser，支持 PDF/Word/PPT/Excel/Text/Image）→ 分块（chunker，`ApproxTokenChunker` 按 chunk_size/overlap）→ 向量化（embedding，如 `DashScopeEmbeddingModel`，注意它的 `dimensions` 是必填参数）→ 存向量库（vector_store，Qdrant/MilvusLite/MongoDB）。这些组装成一个 `KnowledgeBase` 句柄。**检索使用**：用户问题向量化 → 向量库找 Top-K 相似片段 → 注入 prompt（static 自动注入 HintBlock / agentic 让模型调 search_knowledge）。

一个实战细节：向量库可以用 `QdrantStore(location=":memory:")` 内存版零依赖跑通，生产换持久化部署。多租户场景 `KnowledgeBase` 支持 `metadata_filter` 按 tenant 隔离，一个 collection 存多租户数据但检索不串。

RAG 治理上还要注意：检索质量——chunk_size 太大切不准、太小丢上下文，要调；可以用 rerank（检索后二次排序）提质量；embedding 模型选 embedding 维度要和向量库一致。这些是 RAG 效果的关键，不只是「接通」就行。

> **要点速记**：① 两种模式：static(自动检索HintBlock被动注入)/agentic(search_knowledge工具主动搜，默认推荐)；② 简单问答用static、复杂多步用agentic；③ 建库链路：parse→chunk→embed→vector_store 组装成 KnowledgeBase；④ 检索 query向量化+TopK+注入；⑤ 治理：chunk_size调参/rerank/embedding维度一致/多租户metadata_filter。
>
> **源码佐证**：`KnowledgeBase`（`rag/_knowledge.py`，insert_document/search/list_documents）；parser/chunker/vdb（`rag/_parser/`/`_chunker/`/`_vdb/`）；`RAGMiddleware`（`middleware/_rag.py:456`，Parameters.mode=static/agentic）；`DashScopeEmbeddingModel(credential, model, dimensions)`（dimensions 必填，`embedding/_dashscope/_model.py:109`）；双模式示例 `examples/rag/integrate_with_agent.py`。
>
> **压轴一句话**：RAG 两模式——static 自动注入被动看、agentic 暴露search_knowledge工具主动搜(默认推荐)；链路是 parse→chunk→embed→vector_store 建库 + query向量化TopK注入检索，chunk_size/rerank/维度一致决定效果。