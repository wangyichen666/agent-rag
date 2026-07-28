# 07 RAG 框架选型与自研决策

> 本文档记录 Python AI 层（agent-rag-python）在「是否引入 RAG 框架」这一关键选型上的决策依据、主流框架对比，以及分阶段的「摘零件」演进计划。
> 决策结论：**M1/M2 阶段自研薄封装，不整体引入 LangChain / LlamaIndex 等全家桶；按需从框架中摘取单个能力补短板。**

## 1. 当前实现：自研薄封装，非框架驱动

### 1.1 用到的「积木」（库 ≠ 框架）

| 层 | 用到的库 | 性质 |
|---|---|---|
| Web 服务 | FastAPI + Uvicorn | Web 框架，非 RAG 框架 |
| 模型推理 | FlagEmbedding（BGE-M3 / bge-reranker-v2-m3） | 模型库 |
| 向量库 | pymilvus | 客户端 SDK |
| 文档解析 | PyMuPDF、python-docx | 解析库 |
| LLM 调用 | httpx 直连 OpenAI 兼容协议 | 手写客户端 |
| 切分 / 检索 / RRF / Rerank 编排 / Prompt / SSE | **全部手写** | 自研核心 |

核心链路分布在 `app/rag/retriever.py`、`app/rag/generator.py`、`app/services/chat_service.py`，合计约数百行代码，**没有 import 任何 LangChain / LlamaIndex / Haystack 模块**，`requirements.txt` 也不含这些依赖。

### 1.2 自研核心组件清单

| 组件 | 文件 | 行数级 | 说明 |
|---|---|---|---|
| 文档解析 | `rag/parsers.py` | ~200 | PDF/DOCX/MD，页眉页脚清洗、断行修复、表格转 Markdown |
| 切分 | `rag/chunkers.py` | ~180 | 结构感知 + 递归字符双策略，标题路径 metadata |
| Embedding | `rag/embedder.py` | ~150 | BGE-M3 稠密+稀疏，懒加载 + hash LRU 缓存 |
| 向量库 | `rag/vector_store.py` | ~200 | 抽象基类 + Milvus 实现 + InMemory 联调实现 |
| 混合检索 | `rag/retriever.py` | ~100 | 双路召回 + RRF 融合 |
| Rerank | `rag/reranker.py` | ~80 | bge-reranker，sigmoid 归一化 + 故障降级 |
| 生成 | `rag/generator.py` | ~180 | Query 改写、Prompt 组装（编号引用+token 预算）、OpenAI 兼容流式 |
| 编排 | `services/chat_service.py` | ~120 | meta/token/done/error SSE 事件流 |

## 2. 为什么选择自研

### 2.1 可控性

RAG 的效果瓶颈集中在四个点：**切分粒度、混合检索权重、Rerank 阈值、Prompt 模板**。这些必须能逐行调整、逐参数验证。框架把它们藏进多层抽象（Retriever → BaseRetriever → VectorStoreRetriever → ...），调一个参数要翻好几层源码，违背「效果可调」的核心诉求。

### 2.2 不黑盒，可观测

每次问答的 query 改写结果、双路召回命中数、每个候选的 rerank 分数，都通过 SSE `done` 事件的 `retrieval` 字段透传，并由 Java 侧落库到 `message.retrieval_debug`。出 bad case 时能立刻定位是「检索没召回」还是「Rerank 排错」还是「Prompt 丢了上下文」。框架的 chain 一旦出错，调试链路很长。

### 2.3 依赖轻、不踩版本坑

- LangChain 半年大改一次 API（0.1 → 0.2 → 0.3 不兼容变更频发），全家桶拉进来几十个传递依赖
- 自研核心只依赖模型库 + 向量库 SDK + httpx，依赖树扁平，升级风险低
- 镜像体积小、启动快：Python 镜像不装 LangChain 全家桶可省数百 MB

### 2.4 代码量本身不大

RAG 主链路（解析→切分→检索→Rerank→Prompt→生成）自研约 1000 行。引入 LangChain 反而要先学一套抽象再绕着它写，ROI 不高。框架的真正价值在「Agent 多步决策 / 工具编排」这类复杂场景，而 M1/M2 阶段还用不到。

## 3. 主流 RAG 框架对比

| 框架 | 定位 | 优势 | 不适合当前项目的地方 |
|---|---|---|---|
| **LangChain / LangGraph** | 全家桶 + Agent 编排 | 生态最大、连接器多、LangGraph 状态机强 | 重、抽象层多、黑盒、版本变动剧烈 |
| **LlamaIndex** | 专注 RAG、数据连接器丰富 | 检索抽象成熟、评测工具全 | 检索/Rerank 流程较死、定制成本高 |
| **Haystack**（deepset） | 工程化 pipeline | Pipeline 模式清晰、偏生产 | 生态比 LangChain 小、社区偏英文 |
| **Dify / FastGPT / MaxKB** | 低代码平台 | 开箱即用、非开发团队友好 | 本项目要自建可控系统，平台化反而限制定制 |
| **RAGFlow**（InfiniFlow） | 开源 RAG 引擎，DeepDoc 解析强 | 文档解析质量高 | 整体替换而非嵌入，架构耦合 |

**关键判断**：本项目定位是「自建、可控、可演进的企业系统」，而非「快速搭一个 demo」。低代码平台（Dify/FastGPT）方向不符；全家桶框架（LangChain/LlamaIndex）在 M1/M2 阶段的 ROI 低于自研。

## 4. 摘零件演进计划（不整体上框架，按需引入单点能力）

原则：**主链路保持自研，只在某一环遇到自研成本过高时，从框架/开源项目里摘取该环节的成熟实现单点替换。** 接口已预留扩展点。

| 时机 | 引入什么 | 替换哪个组件 | 收益 | 接入方式 |
|---|---|---|---|---|
| PDF 解析质量不够（双栏/表格/扫描件） | **MinerU** 或 **unstructured** | `rag/parsers.py` 的 quality 通道 | 版面分析 + 表格结构识别 + OCR | 已预留 `parser: "quality"` 参数，新增一个 Parser 实现即可 |
| 需要标准化评测 | **RAGAS** | 新增 `tests/eval/` | Faithfulness / Answer Relevancy 自动化指标 | 只跑评测，不碰主链路；读 `message` 表的历史问答 |
| 走到 Agentic RAG（检索不到自动改写重检/换库/联网） | **LangGraph** | `services/chat_service.py` 编排层 | 多步决策状态机自研成本高 | 此时框架价值才体现，评估后决定是否替换编排层 |
| 需要复杂 Tool Calling / 函数调用 | OpenAI SDK 的 function calling | `rag/generator.py` | 标准化工具协议 | 直接用 SDK，仍不引入 LangChain |
| 多模态（图片/表格理解） | 多模态模型 + 表格问答（Text2SQL） | 新增 `rag/multimodal/` | 结构化数据问答 | 独立模块，不影响文本 RAG 链路 |

## 5. 什么时候应该重新评估「上框架」

出现以下任一信号时，重新评估是否整体引入框架：

1. **Agent 需求成为主线**：需要多步推理、工具编排、自主决策（不再是单轮检索→生成）
2. **数据源种类爆炸**：需要接入十几种异构数据源（Notion/Confluence/飞书/Jira...），自研连接器成本超过收益
3. **团队人力不足**：维护自研链路的人力跟不上，需要框架的「开箱即用」降低维护负担
4. **评测显示自研链路在某个环节系统性落后**：且该环节框架有成熟实现、自研追赶成本高

在此之前，自研 + 摘零件是最优解。

## 6. 决策记录

- **决策**：M1/M2 阶段 Python AI 层采用自研薄封装，不引入 LangChain / LlamaIndex / Haystack 等 RAG 框架
- **依据**：可控性、可观测性、依赖轻、代码量可控（见第 2 节）
- **演进策略**：按需摘零件（见第 4 节），主链路保持自研
- **复审触发条件**：见第 5 节
- **影响范围**：仅 agent-rag-python 的 AI 编排层；Java 业务层与前端不受影响
