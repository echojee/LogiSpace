# 深度研究项目源码调研报告

> 调研日期：2026-08-02  
> 范围：OpenAI Deep Research、Open Deep Research、STORM / Co-STORM、GPT Researcher、PaperQA2、DeerFlow  
> 本报告只分析这些项目本身，不提出 LogiSpace 的技术方案。

## 1. 调研方法与版本

本报告以各项目公开文档、论文和 GitHub 当前源码为依据。开源项目使用浅克隆后直接阅读入口、状态、工具、检索、生成、持久化和评测模块；以下 commit 用于避免未来代码变化导致描述失真：

| 项目 | 调研 commit | commit 时间 |
|---|---|---|
| Open Deep Research | `d337ae32ed4ff8f4c6fbe192ba3bf1b2d6610799` | 2026-07-25 |
| STORM / Co-STORM | `fb951af7744dab086e34962e9bc6fe878e145f83` | 2025-09-30 |
| GPT Researcher | `5d84d2f5553e70a2765a8ff3a0d2672d60437ce8` | 2026-07-14 |
| PaperQA2 | `d7675d7b7eddeb3535e8c260399c5bbeeb818c50` | 2026-06-05 |
| DeerFlow | `7025ccee403d016cfaeeb6f011475a370ff81e0d` | 2026-08-02 |

OpenAI Deep Research 没有公开产品源码，因此该节只引用[官方产品说明](https://help.openai.com/en/articles/10500283-deep-research)和[系统卡](https://openai.com/index/deep-research-system-card/)。任何无法由官方材料验证的内部实现都不会当作事实描述。

## 2. 总览：六个项目实际上属于四种架构

| 类型 | 项目 | 核心抽象 |
|---|---|---|
| 产品级长时浏览 Agent | OpenAI Deep Research | 用户目标、可编辑计划、工具化浏览、可引用报告 |
| Supervisor–Researcher Agent Graph | Open Deep Research | LangGraph state、Supervisor ReAct、Researcher ReAct、压缩与报告 |
| 知识策展流水线 | STORM / Co-STORM | 多视角访谈、Information Table、Outline、Section、协作话语协议 |
| 搜索—抓取—压缩—写作系统 | GPT Researcher | Retriever/Scraper 插件、并发子查询、递归 breadth/depth、报告生成 |
| Agentic RAG 环境 | PaperQA2 | Environment、ToolSelector、Paper Search、Evidence Gathering、Answer |
| 通用 Agent Harness | DeerFlow 2.0 | Middleware、Skills、Sub-agent、Sandbox、Filesystem、Memory、Gateway |

它们并不是同一种“深度研究 Agent”的不同实现。STORM 的目标是知识策展和百科式写作，PaperQA2 的目标是科学文献问答，DeerFlow 2.0 的目标已经是通用长任务运行时。比较时应关注机制，不应只比较 Agent 数量。

---

## 3. OpenAI Deep Research

### 3.1 可确认的整体架构

从公开资料可确认的产品流程是：

```text
用户描述目标
  → 选择允许使用的来源（Web、上传文件、连接应用、指定站点）
  → 系统提出研究计划并允许用户修改
  → 长时多步搜索、阅读、解释、分析与动态转向
  → 生成结构化报告、内联引用和来源链接
  → 展示活动历史，可下载 Markdown / Word / PDF
```

官方系统卡将其描述为针对复杂任务训练的 agentic capability，可以在互联网文本、图片和 PDF 之间多步研究，遇到新信息时调整方向，也能执行 Python 做数据分析。官方产品说明强调：计划可审阅、来源可限定、运行可中断和调整、输出带引用及活动历史。

### 3.2 亮点功能及公开可见的技术机制

#### 亮点 A：研究前对齐，而不是直接搜索

系统可先提澄清问题，并生成可编辑研究计划。这里最重要的不是 UI，而是把用户自然语言请求转换为一个稳定的中间任务表示，使后续长时执行不必反复依赖原始对话。

公开资料没有披露该表示的 Schema、Planner prompt 或图结构，因此无法判断它究竟是静态 Plan-and-Execute、动态 ReAct，还是混合架构。

#### 亮点 B：来源作用域是一等配置

用户可以选择公共 Web、上传文件、连接应用或特定站点。技术上至少需要：

- 不同检索后端的统一工具接口；
- 来源权限随任务传播；
- 引用对象保留原始来源身份；
- 报告生成不能把不同权限域的内容混成不可追溯文本。

这些是由产品行为可以合理推出的系统需求，但具体内部实现未公开。

#### 亮点 C：长时动态研究

系统卡明确提到它能根据遇到的信息 pivot。说明执行过程不是一次性 `query → top-k → summarize`，而需要保留中间观察并动态决定下一步搜索、读取或分析动作。

#### 亮点 D：安全浏览是系统能力，而不仅是提示词

系统卡重点讨论网页 prompt injection、隐私、代码执行与任意 URL 风险。例如系统级限制不允许模型任意构造 URL，以降低通过 URL 参数泄漏敏感信息的风险。这说明安全边界位于浏览/工具层，而不是仅要求模型“忽略恶意指令”。

### 3.3 评测

公开系统卡披露了浏览能力、安全和风险评测，但没有发布完整的产品质量评测代码。报告质量、引用忠实度、搜索覆盖、成本控制的内部 benchmark 细节不可从公开源码验证。

### 3.4 技术局限与研究边界

- 无公开源码，无法判断状态存储、并发、重试、checkpoint 和引用绑定的具体实现。
- 不能根据产品体验反向断言其使用某个特定框架或 ReAct prompt。
- 它适合用作产品体验和安全边界对标，不适合作为可复刻的源码架构样板。

---

## 4. Open Deep Research

源码：[langchain-ai/open_deep_research](https://github.com/langchain-ai/open_deep_research)

### 4.1 整体技术架构

当前实现高度集中在 [`deep_researcher.py`](https://github.com/langchain-ai/open_deep_research/blob/d337ae32ed4ff8f4c6fbe192ba3bf1b2d6610799/src/open_deep_research/deep_researcher.py)，由三个 LangGraph 组成：

```text
Main Graph
  clarify_with_user
    → write_research_brief
    → supervisor_subgraph
    → final_report_generation

Supervisor Subgraph
  supervisor (LLM + ConductResearch / ResearchComplete / think_tool)
    ↔ supervisor_tools
        └─ 并行调用 N 个 researcher_subgraph

Researcher Subgraph
  researcher (LLM + search/MCP/think tools)
    ↔ researcher_tools
    → compress_research
```

状态分层定义在 `state.py`：

- `AgentState`：用户 messages、research brief、raw notes、compressed notes、final report；
- `SupervisorState`：supervisor messages、research iterations、notes；
- `ResearcherState`：独立消息历史、tool-call iteration、research topic、压缩结果；
- reducer 决定字段是 append 还是 override，避免子图输出错误累加。

### 4.2 亮点 A：两层 ReAct，而不是预先展开完整计划

`write_research_brief` 先用 structured output 生成一个聚焦的 `ResearchQuestion.research_brief`。之后 Supervisor 并不必然生成完整静态任务列表，而是在循环中使用三类工具：

- `think_tool`：记录战略反思；
- `ConductResearch(research_topic)`：派发一个研究单元；
- `ResearchComplete`：结束研究。

`supervisor_tools` 一次收集当前模型发出的全部 `ConductResearch` 调用，截断到 `max_concurrent_research_units`，然后用 `asyncio.gather` 并行执行 researcher 子图。研究结果作为 `ToolMessage` 返回 Supervisor，Supervisor 再决定是否补查。

这使 Plan 具有动态性：计划是 Supervisor 的工具调用轨迹，而不是单独持久化的 DAG。

### 4.3 亮点 B：研究者上下文隔离与强制压缩

每个 researcher 只收到一个 `research_topic`，有自己的 `researcher_messages`。其工具来自 `get_all_tools(config)`，包括 Tavily、OpenAI/Anthropic native web search、MCP 和 `think_tool`。

Researcher 每轮让模型选择工具，`researcher_tools` 并发执行同一轮多个 tool calls；达到 `max_react_tool_calls`、模型不再调用工具或出现原生搜索终止信号后，进入 `compress_research`。压缩模型把长工具历史变为：

- `compressed_research`：给 Supervisor 使用的短结果；
- `raw_notes`：给最终报告和 groundedness 评测保留的原始研究材料。

这种“双通道输出”解决了两个不同问题：Supervisor 需要短上下文继续规划，而最终写作与评测仍需要较完整的来源笔记。

### 4.4 亮点 C：模型职责与成本层级可配置

`Configuration` 分开配置：

- summarization model；
- research model；
- compression model；
- final report model；
- 每类模型的 max tokens；
- Supervisor iteration、Researcher tool calls、并发研究单元；
- search API 和 MCP 工具。

搜索网页过长时由 summarization model 先压缩，Researcher 负责决策，compression model 负责研究单元收敛，final report model 只消费聚合后的 notes。这不是简单的“多个 Agent”，而是按上下文规模和任务性质拆模型调用。

### 4.5 亮点 D：Provider 与 MCP 统一成工具

`get_all_tools` 根据配置选择 Tavily、OpenAI native web search、Anthropic native search 或 MCP。MCP 配置包含服务 URL、允许暴露的工具名和鉴权要求。Researcher 不需要了解后端类型，只面对工具 Schema。

### 4.6 失败控制

- structured output 使用 retry；
- Supervisor 有 `max_researcher_iterations`；
- Researcher 有 `max_react_tool_calls`；
- 并发有 `max_concurrent_research_units`；
- 工具调用由 `execute_tool_safely` 转成文本错误而非直接击穿图；
- token limit 时尝试清理到最近 AI message 或提前进入压缩/写作。

但源码中 Supervisor 的异常分支包含 `if is_token_limit_exceeded(...) or True`，意味着任何异常都会直接结束研究阶段。这是一种保守降级，也会掩盖可恢复错误。

### 4.7 报告生成与引用

最终报告模型读取 `research_brief + notes` 生成 Markdown。引用主要来自搜索工具输出与压缩笔记中的 URL，最终 prompt 要求保留引用。它没有像 PaperQA2 那样建立独立 Evidence 对象或对每条 Claim 做确定性引用校验。

### 4.8 评测

`tests/evaluators.py` 使用结构化 LLM-as-a-judge 评估：

- relevance；
- structure/cohesiveness；
- correctness（对参考答案）；
- completeness；
- groundedness（从报告抽 Claim，与 raw notes 比较）；
- overall quality：研究深度、来源质量、分析严谨、实用价值、平衡性、写作。

项目通过 LangSmith 运行 Deep Research Bench，并保留不同模型组合的实验结果。其优势是端到端可比较；局限是主要依赖 Judge，且 groundedness 是“报告对 raw notes”，并不等于“raw notes 对原网页”。

### 4.9 架构评价

最强之处是用很少代码表达了清晰的层级 Agent Graph、并发和上下文压缩。最弱之处是知识数据结构较薄：核心产物仍是 notes 和 Markdown，来源、证据、Claim、冲突没有正式的领域对象。

---

## 5. STORM / Co-STORM

源码：[stanford-oval/storm](https://github.com/stanford-oval/storm)

### 5.1 STORM 的四阶段架构

`STORMWikiRunner` 在 `storm_wiki/engine.py` 中编排四个可替换模块：

```text
Knowledge Curation
  → Outline Generation
  → Article Generation
  → Article Polishing
```

接口集中在 `knowledge_storm/interface.py`，具体 Wiki 实现在 `storm_wiki/modules/`。各阶段产物会落地到文件，例如：

- `conversation_log.json`；
- `raw_search_results.json`；
- `storm_gen_outline.txt`；
- `direct_gen_outline.txt`；
- draft / polished article；
- run configuration 与 LLM usage。

阶段可以跳过并从本地文件恢复，所以它更像可重放的知识策展流水线，而不是单一对话 Agent。

### 5.2 亮点 A：通过 Persona 发现“未知的未知”

`StormPersonaGenerator` 不是随意编造角色。它先检索同类 Wikipedia 页面，抽取已有编辑视角，再生成针对当前主题的 persona。随后 `StormKnowledgeCurationModule` 为每个 persona 启动一条独立访谈。

每条访谈由两个组件组成：

- `WikiWriter`：基于 persona 和最近对话，每次只提出一个问题；
- `TopicExpert`：把问题转换为若干搜索查询，检索结果，然后基于 snippet 生成带编号引用的回答。

不同 persona 的访谈由 `ThreadPoolExecutor` 并行执行。这一机制的技术重点不是多 Agent 数量，而是**让问题空间产生系统性差异**，从而提高主题覆盖。

### 5.3 亮点 B：检索增强大纲，而不是先写固定大纲

Outline Generation 同时生成两份大纲：

1. 只基于主题直接生成的 draft outline；
2. 基于多视角对话和收集信息生成并优化的 STORM outline。

这使检索影响“文章应该包含什么”，而不只是为预设章节填内容。STORM 论文的核心贡献也集中在这一点：先通过多视角问答发现内容空间，再组织结构。

### 5.4 亮点 C：Information Table 是研究与写作之间的中间层

访谈不会直接拼成文章，而被转换成 `StormInformationTable`。它保存：

- persona 与 dialogue turns；
- 问题、查询、搜索结果和回答；
- URL 到编号引用的映射；
- 可供后续向量检索的信息条目。

文章生成前调用 `prepare_table_for_retrieval()` 建索引。每个一级 section 使用 outline 节点作为 query，从 Information Table 重新召回 top-k 信息，再并行写 section。这样“研究过程顺序”和“文章结构顺序”解耦。

### 5.5 亮点 D：引用编号在数据层统一管理

写 section 时，收集的信息被重新编号为 `[1]...[n]`；`StormArticle.update_section` 将局部编号映射回全局 reference table。后处理会清理无效、未使用或不连续引用。相比最终阶段让模型自由添加 URL，这种方式更稳定。

不过 STORM 的 evidence 粒度主要还是搜索 snippet / information item，并非不可变正文快照和精确 quote。

### 5.6 文章生成与润色

`StormArticleGenerationModule` 对一级 section 并行执行：

```text
section outline
  → 从 Information Table 检索 section-specific info
  → LLM 生成带本地引用的 section
  → 合并到 StormArticle
  → citation/reference 后处理
```

Polishing 模块主要删除重复内容、改善连贯性并生成 lead section。润色阶段不重新研究，因此事实边界原则上由前面的 Information Table 决定。

### 5.7 Co-STORM：从流水线升级为协作知识空间

Co-STORM 引入：

- Moderator；
- 多个 Expert agents；
- Simulated User / 真实用户；
- General Knowledge Provider / Pure RAG agent；
- `DiscourseManager`；
- 层级 Knowledge Base。

最关键的不是“多人聊天”，而是 `DiscourseManager.get_next_turn_policy()`。它根据会话历史、连续专家发言数、上一轮是否为问题等规则，决定：

- 下一轮由谁说；
- 是否更新专家列表；
- 是否重组知识库；
- 是否润色 utterance。

知识通过 `InformationInsertionModule` 插入层级 concept tree，Moderator 可以基于覆盖缺口发起新问题。人类用户加入的内容与专家输出进入同一个 shared conceptual space，最终再从 Knowledge Base 生成文章。

### 5.8 评测与局限

STORM 论文评测重点包括 outline quality、article organization、coverage 与 citation。源码更偏研究复现实验和结果落盘，没有 Open Deep Research 那种完整在线 evaluator harness。

技术局限：

- 依赖 LLM 生成 persona、查询、大纲和段落，误差会跨阶段传播；
- 检索证据多以 snippet 为核心；
- 文章目标强绑定 Wikipedia 风格；
- thread-based 并发简单有效，但缺少生产级 lease/checkpoint/分布式任务语义；
- Co-STORM 的对话协议和知识树比 STORM 强，但复杂度显著更高。

---

## 6. GPT Researcher

源码：[assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher)

### 6.1 总体架构：一个门面，多条执行路径

`GPTResearcher` 是总门面，组合多个 skill：

```text
GPTResearcher
  ├─ ResearchConductor   搜索计划与研究执行
  ├─ BrowserManager      抓取网页
  ├─ ContextManager      上下文选择
  ├─ SourceCurator       来源筛选
  ├─ ReportGenerator     报告、大纲、引用、导出
  ├─ DeepResearchSkill   递归 breadth/depth 研究
  └─ ImageGenerator      报告配图
```

经典路径：

```text
choose_agent/role
  → 初始搜索
  → LLM 生成 sub-queries
  → 多 Retriever 搜索
  → URL 去重与抓取
  → embedding compression
  → 汇总 context
  → 报告大纲与 section 写作
  → references / TOC / 图片 / 导出
```

Deep Research 路径则绕到 `DeepResearchSkill`，采用递归树搜索，最后仍把 context 交回统一 ReportGenerator。

### 6.2 亮点 A：Retriever 与 Scraper 是两个独立插件面

项目支持 Tavily、Brave、Exa、Serper、SerpAPI、Google、Bing、DuckDuckGo、Searx、Arxiv、Semantic Scholar、OpenAlex、PubMed Central、MCP 等 Retriever。

Retriever 只负责返回候选 URL / metadata，Scraper 再选择 BeautifulSoup、browser/nodriver、PyMuPDF、Firecrawl、Tavily Extract 等读取正文。这种分离允许“搜索 API 很强但正文能力弱”或“指定 URL 直接抓取”等组合。

`get_search_results` 将同步 HTTP retriever 放入 `asyncio.to_thread`，避免阻塞事件循环；同一子查询可并行调用多个 Retriever，多个 sub-query 也通过 `asyncio.gather` 并行。

### 6.3 亮点 B：经典模式是 Plan-and-Solve，不是自由 ReAct

`ResearchConductor.plan_research` 先取得初始搜索结果，再调用 strategic LLM 生成 sub-queries。随后对 sub-query 并行执行固定流程。模型主要负责：

- 选择 agent role；
- 生成查询；
- 从文本中提取和压缩上下文；
- 写大纲和报告。

工具调用顺序主要由代码控制。因此经典模式比 ReAct 更可预测，也更容易并发和估算成本。

### 6.4 亮点 C：Context Compression 控制长网页成本

`ContextCompressor` 使用 LangChain `DocumentCompressorPipeline`：

1. `RecursiveCharacterTextSplitter(chunk_size=1000, overlap=100)`；
2. Embedding similarity filter；
3. 返回 top relevant chunks。

小文档集合存在 fast path：当总字符数低于阈值且文档数不超过 max results 时，跳过切块和 embedding，直接格式化正文。这是一个实际的成本/延迟优化。

项目还提供 `WrittenContentCompressor`，在写长报告的后续章节时从已写内容中召回相关段落，减少章节间重复和上下文膨胀。

### 6.5 亮点 D：递归 Deep Research 的 breadth/depth 树

`DeepResearchSkill` 的执行方式：

```text
generate_search_queries(query, breadth)
  → 为每条 query 启动一个新的 GPTResearcher
  → 并发执行，Semaphore 限流
  → process_research_results 提取 learnings、citations、follow-up questions
  → 汇总 visited_urls、sources、context
  → 若 depth > 1：
       用 follow-up questions 构造下一层 query
       breadth = max(2, breadth // 2)
       depth = depth - 1
```

它是递归 plan-and-search tree，而不是每个节点通用 ReAct。`visited_urls` 在父子 Researcher 间共享以避免重复抓取；`asyncio.Semaphore` 控制并发；某一层全部失败时立即停止下降，防止空结果产生无限 follow-up。

### 6.6 亮点 E：来源类型和 MCP 策略可配置

支持 Web、Local、Hybrid、Azure、LangChain Documents、Vector Store。Hybrid 使用 `asyncio.gather` 同时研究本地文档与 Web。

MCP 有三种策略：

- `fast`：只对原始 query 执行；
- `deep`：对所有 sub-query 执行；
- `disabled`。

这是少见的把“工具调用深度”作为成本旋钮暴露出来的设计。

### 6.7 报告与引用

`ReportGenerator` 支持 research report、detailed report、subtopic report、outline 等类型。详细报告会拆 section，分别研究和写作，再合并 TOC、references、图片，并可导出 Markdown、PDF、DOCX。

引用主要依赖 context 中保留 URL，并通过 prompt 与 `add_references` 后处理形成 references。递归模式将 `learning → source URL` 存为字典，再把 `[Source: URL]` 注入最终 context。

这套设计强调“来源跟踪”，但不是 Claim–Evidence 数据模型：同一 learning 只映射一个 URL，引用是否真正支持句子主要依赖模型和文本上下文。

### 6.8 运行与可观测性

- WebSocket / log handler 推送研究阶段和成本；
- `research_costs` 与 `step_costs` 记录调用成本；
- `visited_urls` 去重；
- WorkerPool 控制抓取；
- LangSmith 可追踪 LangGraph/Agent 路线；
- 有 FastAPI + 静态前端和 Next.js 前端两套 UI。

### 6.9 技术局限

- 经典模式、DeepResearchSkill、多 Agent 示例、MCP 路线并存，架构面较宽，维护和配置复杂；
- 来源质量的公开主张较多依赖“多抓一些网站”，缺少强 Claim-level verification；
- DeepResearchSkill 里 learnings/citations/context 是松散 list/dict，递归合并容易丢失更细粒度 provenance；
- 抓取模块存在较多 provider-specific 分支；
- context trimming 偏启发式，可能保留最近内容而丢掉早期高价值证据。

---

## 7. PaperQA2

源码：[Future-House/paper-qa](https://github.com/Future-House/paper-qa)

### 7.1 整体架构：把 RAG 做成 Agent Environment

PaperQA2 不是让多个 Researcher 写报告，而是把科学文献问答抽象成带状态的环境：

```text
ToolSelector Agent
  ↕ observation / ToolRequest
PaperQAEnvironment
  ├─ paper_search
  ├─ gather_evidence
  ├─ gen_answer
  ├─ reset
  └─ complete
       ↓
EnvironmentState
  ├─ Docs
  └─ PQASession(question, contexts, answer, cost, tool_history)
```

主入口 `agent_query`：构建/加载 Tantivy 索引，运行 Agent，完成后把 AnswerResponse 写入独立 `answers` 索引，使历史答案也可检索。

### 7.2 亮点 A：Agent 自主性被限制在五个领域工具内

默认 Agent 使用 Aviary `ToolSelector`。每一步必须返回 `ToolRequestMessage`，否则环境回答“You must call tools to proceed”。工具语义明确：

- `paper_search(query, min_year, max_year)`：向 Docs 引入新论文；
- `gather_evidence(question)`：从当前论文中检索和建立 Evidence context；
- `gen_answer()`：只基于当前 Evidence 尝试回答；
- `reset()`：清空错误 Evidence，保留论文集合；
- `complete(has_successful_answer)`：明确结束并报告确定/不确定。

Agent 可以反复换 query、换 evidence question、失败后 reset，再决定完成。这是受约束的 ReAct：自主性发生在工具顺序与参数，数据操作仍由领域代码实现。

项目同时提供 `fake` agent，固定执行三次 search → gather evidence → answer → complete。它用于降低 token、回归测试或把 Agent 决策和底层 RAG 性能分开评测。

### 7.3 亮点 B：Environment 提供强制终止和故障降级

`run_aviary_agent` 有 timestep 上限和总 timeout。发生超时、轨迹失败，或 Agent 从未调用 `gen_answer` 时，`_run_with_timeout_failure` 会强制调用 GenerateAnswer，以当前证据返回尽可能有用的结果。

`EnvironmentState.status` 每轮向 Agent报告：

- Paper Count；
- Relevant Papers；
- Current Evidence；
- Current Cost。

Agent 因而不是只读自然语言历史，也能根据结构化运行指标决定继续搜还是回答。

### 7.4 亮点 C：Evidence Gathering 是两级重排

PaperQA2 的核心算法：

1. 对论文全文切块并 embedding；
2. 用 question 向量召回 top-k chunks；
3. 对每个 chunk 调 summary LLM，生成“面向当前问题”的 evidence summary；
4. summary prompt 要求保留数字、公式和直接引语，并输出 1–10 relevance score；
5. 过滤低分 context；
6. Answer LLM 只读取筛选后的 contexts。

`gather_evidence` 返回新增 Evidence 数和当前最佳 Evidence 给 Agent，Agent可以据此继续补论文或换问题措辞。

相比直接把向量 top-k 交给 Answer LLM，这里把“片段是否相关”变成显式中间判断，也用 query-specific summary 压缩全文。

### 7.5 亮点 D：文献元数据与正文是共同的数据资产

Paper search 使用 Tantivy 本地全文索引。文档引入后会从 Crossref、Semantic Scholar、OpenAlex、Unpaywall 等补全 DOI、作者、期刊、年份、开放获取、引用数；还有 retraction 和 journal quality 处理。

`DocDetails` 与正文 chunk 关联，引用 key 由文档元数据生成，而不是只保留 URL。科学文献场景中，这显著提高去重、引用格式和来源筛选质量。

### 7.6 亮点 E：多模态文档解析

当前 readers 支持 PDF、文本、Office、代码，以及表格、图片、数学公式等 media。PDF parser 可替换为 PyPDF、Docling、Nemotron Parse。页码和 media 会进入 chunk；summary LLM 可以同时消费文字和媒体，enrichment LLM 可以为媒体生成用于 embedding 的描述。

### 7.7 引用机制

每个 Context 带稳定 citation key 和 formatted citation。Answer prompt 明确要求：

- 只能使用上下文中的 citation keys；
- 在支持句末引用；
- 不允许自造或拼接 citation key；
- 可限制 answer max sources。

底层会清除 evidence summary 中可能与最终 citation 冲突的原始引用，再由系统自己的 key 统一引用。这比让模型复制论文里的编号更可靠。

但它仍主要保证“引用来自所给 Context”；对每句话的 entailment 需要额外评测，不能仅凭 citation key 存在就认定正确。

### 7.8 配置与评测工程

`Settings` 将 evidence_k、relevance cutoff、summary length、max sources、并发、模型、agent timeout/timesteps 等集中管理，并提供 fast、high_quality、tier limits、clinical trials 等预设配置。

PaperQA2 的论文使用 LitQA2 等科学问答 benchmark；源码拥有大量录制 HTTP cassette、索引、解析、元数据、工具和端到端测试。Agent 与 RAG 可以分开测试：fake agent 固定调用路径，ToolSelector 测策略收益。

### 7.9 技术局限

- 对高质量论文、DOI 和学术元数据的假设很强；
- 默认输出是问答而非长篇多章节档案；
- query-specific summary 会引入压缩误差；
- 科学来源的 journal/citation-count 信号并不等同于事实正确性；
- Agent 的“成功”部分依赖其调用 `complete(has_successful_answer)` 的自我判断。

---

## 8. DeerFlow 2.0

源码：[bytedance/deer-flow](https://github.com/bytedance/deer-flow)

### 8.1 定位变化

DeerFlow 1.x 是深度研究框架；2.0 已重写为通用 long-horizon SuperAgent harness。因此当前源码更适合研究“如何运行和约束 Agent”，而不是研究搜索/引用算法。

### 8.2 系统架构

```text
Browser / IM / API Client
  → Nginx :2026
  → FastAPI Gateway :8001
      ├─ LangGraph-compatible threads/runs API
      ├─ Embedded Agent Runtime
      ├─ SSE event streaming
      ├─ Model / MCP / Skills / Upload / Artifact APIs
      └─ Checkpoint / Auth / Scheduler
  → Lead Agent
      → Middleware Chain
      → Model + Tools + System Prompt
      → Sub-agents / Sandbox / Filesystem
```

默认生产入口不是单独 LangGraph Server，而是 Gateway 内嵌 runtime，同时保持 LangGraph-compatible API。这使产品可以控制鉴权、线程、流式事件、文件与运行生命周期。

### 8.3 亮点 A：Agent 能力由 Middleware 组合

`make_lead_agent` 创建 Agent 时按顺序装配 middleware，例如：

- ThreadDataMiddleware：创建线程 workspace/uploads/outputs；
- UploadsMiddleware：解析上传文件；
- SandboxMiddleware：获取执行环境；
- SummarizationMiddleware：上下文压缩；
- TitleMiddleware：自动标题；
- TodoListMiddleware：Plan mode；
- ViewImageMiddleware：视觉输入；
- ClarificationMiddleware：用户澄清；
- Skills / Memory / Sub-agent 等扩展。

技术意义是把横切能力放在模型调用前后，而不是全塞进 system prompt。middleware 可以修改 state、消息、工具集合和输出，且能单测。

### 8.4 亮点 B：Plan mode 是状态与工具，不只是模型承诺

Plan mode 使用 `TodoListMiddleware` 把 todos 加入 ThreadState，并提供任务更新工具。计划项具有状态，UI 可以显示进度。模型通过工具写入/更新计划，而不是在自然语言里说“我会做三步”。

Plan mode 可以按运行模式启用；轻任务不必承担完整计划开销。

### 8.5 亮点 C：Sub-agent 是隔离任务，而不是共享长对话

Lead agent 通过 task tool 创建 sub-agent：

- 子 Agent 收到明确任务描述；
- 使用独立上下文，避免主线程所有消息复制过去；
- 可以配置不同模型、工具、skills；
- 结果以结构化/文本结果返回 Lead；
- 主 Agent 负责整合，不让子 Agent 直接占满主上下文。

task tool 和 middleware 负责调度、状态同步、错误恢复与 usage 归属。与简单 `asyncio.gather` 的区别是它处在完整 thread/run/checkpoint 生命周期中。

### 8.6 亮点 D：上下文工程以文件系统为中心

每个线程有虚拟路径：

```text
/mnt/user-data/uploads
/mnt/user-data/workspace
/mnt/user-data/outputs
```

长文本、中间成果和最终 artifact 放入文件系统，消息只保留路径和摘要。SummarizationMiddleware 在达到阈值时压缩旧对话；Skills 渐进加载，只有相关 skill 的 `SKILL.md` 和引用资源进入上下文。

这种设计将 context window 视为缓存，而不是永久数据库。

### 8.7 亮点 E：Sandbox 是可替换基础设施

定义 `SandboxProvider.acquire/get/release` 与 Sandbox 的 command/file 接口。实现包括：

- LocalSandboxProvider：开发使用，文件隔离但不等同安全容器；
- AioSandboxProvider：容器化隔离；
- E2B 等 community provider。

SandboxMiddleware 在运行开始获取环境并把虚拟路径映射到实际目录。生产 provider 处理 lease、ownership、reconnect、warm pool、orphan/duplicate 清理。工具只面对统一 sandbox 接口。

### 8.8 亮点 F：运行时护栏

Guardrails 不仅在 prompt 中：

- 工具白名单和动态 tool filtering；
- 本地 shell 默认禁用或受 provider 限制；
- thread/user 路径隔离；
- tool-call 历史断裂时注入占位结果，修复严格模型的协议状态；
- checkpoint lineage；
- SSE 中明确区分 run event；
- authorization 在 route 与 tool 两层测试；
- 安全终止和 replay fixture。

### 8.9 亮点 G：长期记忆与 Skills

Memory 与 ThreadState 分开，跨线程保存用户偏好和稳定事实；更新时去重。Skills 以 Markdown 工作流包表达，可带脚本和参考资源，按需加载。Agent 因此可以“学会一种流程”而不必改 runtime 代码。

### 8.10 评测与局限

当前仓库大量测试集中在 runtime 工程：授权、sandbox、checkpoint、streaming、replay、middleware、tool filtering。它不是引用质量 benchmark。

局限：

- 2.0 是通用 harness，研究领域的数据模型、证据与引用要由 skill/application 自己实现；
- middleware、gateway、sandbox、channels、skills、memory 形成较大系统面；
- 高度自治 Agent 的任务质量仍取决于 prompt、模型和工具；
- Plan/todo 保证过程可见，不保证研究计划本身正确。

---

## 9. 横向技术比较

### 9.1 计划方式

| 项目 | 计划表示 | 动态调整 |
|---|---|---|
| OpenAI Deep Research | 可编辑计划，内部表示未公开 | 支持运行中调整 |
| Open Deep Research | Research Brief + Supervisor tool-call trajectory | 强，Supervisor 循环补查 |
| STORM | Persona conversations + retrieval-informed outline | 研究阶段按对话动态，大纲阶段相对固定 |
| GPT Researcher | LLM sub-query list；Deep 模式为 breadth/depth tree | 经典模式中等，Deep 模式递归扩展 |
| PaperQA2 | 无全局 outline；Agent 根据环境状态选择工具 | 强，但仅限文献问答工具空间 |
| DeerFlow | Todo state + Lead Agent 动态派发 task | 强，面向通用长任务 |

### 9.2 搜索与信息处理

| 项目 | 召回 | 正文/片段处理 | 中间知识形态 |
|---|---|---|---|
| Open Deep Research | Tavily/native search/MCP | 网页压缩 + research compression | raw notes + compressed notes |
| STORM | 可替换 RM / VectorRM | 搜索 snippets，后建 Information Table 检索 | Dialogue + Information Table |
| GPT Researcher | 大量 Retriever 插件 | 多 Scraper + embedding compression | context lists / sources / learnings |
| PaperQA2 | Tantivy 本地论文索引 | 全文 chunk → vector top-k → LLM summary/rerank | Docs + Context Evidence + Session |
| DeerFlow | 由 tool/skill 决定 | 文件系统、浏览器、通用工具 | thread files + messages + memory |

### 9.3 Agent 自主性与约束

| 项目 | 自主性 | 主要约束 |
|---|---|---|
| Open Deep Research | Supervisor 与 Researcher 双层 ReAct | iteration、tool-call、并发上限、压缩 |
| STORM | 受模块化访谈协议约束 | persona、最大轮次、最大 query、固定四阶段 |
| GPT Researcher | 经典模式低到中；递归模式中 | breadth/depth、Semaphore、visited URLs、配置 |
| PaperQA2 | 工具选择层高，数据操作层低 | 五个领域工具、timeout、timesteps、cost/status、complete |
| DeerFlow | 很高 | middleware、sandbox、权限、tool filter、checkpoint、filesystem |

### 9.4 引用可靠性

从源码机制看，可粗略分为：

1. **PaperQA2**：Context 与 citation key 是正式数据对象，机制最强；
2. **STORM**：Information Table 和局部—全局引用编号映射较稳定，但证据常为 snippet；
3. **Open Deep Research / GPT Researcher**：URL 随 notes/context 传播，最终主要由 prompt 约束引用；
4. **DeerFlow**：runtime 本身不定义引用语义，由研究 skill 决定。

这里评价的是“引用机制强度”，不是最终报告事实正确率。

### 9.5 持久化与可恢复性

- STORM：阶段文件明确，适合离线重放，但不是生产任务数据库。
- PaperQA2：本地论文/答案索引和可序列化 Docs 强，Agent trajectory 恢复不是主要目标。
- Open Deep Research：依赖 LangGraph state/checkpointer 部署能力，仓库核心代码以 state graph 为主。
- GPT Researcher：主要是进程内对象、visited URLs、context 和 UI 事件，长任务耐久语义相对弱。
- DeerFlow：thread/run/checkpoint、filesystem、sandbox ownership、replay 最完整，工程运行时最强。

## 10. 最值得关注的源码级设计模式

### 10.1 Researcher 输出应分“原始材料”和“给上级的压缩结果”

Open Deep Research 的 `raw_notes + compressed_research` 是很实用的上下文模式：一份保证审计和最终写作材料，一份保证 Supervisor 能继续思考。

### 10.2 让检索改变结构，而不只是填充结构

STORM 先多视角研究，再生成大纲；其特色来自问题发现机制，而非更长的生成 prompt。

### 10.3 将 RAG 变成有状态工具环境

PaperQA2 把 search、evidence、answer、reset、complete 做成工具，并把论文数、证据数、成本反馈给 Agent。这比给通用 Agent 一个 `search_web` 工具更容易约束和评测。

### 10.4 搜索与抓取应是两个 adapter 层

GPT Researcher 的 Retriever/Scraper 分离允许独立替换搜索召回和正文读取，也能组合 local/hybrid/MCP 来源。

### 10.5 多 Agent 的核心是上下文与权限隔离

Open Deep Research 的 ResearcherState 和 DeerFlow 的 sub-agent/thread filesystem 都说明：有效多 Agent 不是多几个角色提示词，而是独立状态、有限工具、结构化交接、并发上限和明确终止。

### 10.6 工程护栏应位于模型之外

PaperQA2 的 Environment、DeerFlow 的 middleware/sandbox/auth、Open Deep Research 的图边与 iteration limits 都把约束写进代码。只依赖 system prompt 不能形成可靠的长任务系统。

## 11. 结论

这六个项目分别解决了深度研究的不同难题：

- OpenAI Deep Research 展示了完整产品体验与安全边界；
- Open Deep Research 给出了最简洁的 Supervisor–Researcher ReAct 图；
- STORM 解决了多视角问题发现、检索增强大纲和知识策展；
- GPT Researcher 提供了最广的搜索/抓取插件面和递归研究树；
- PaperQA2 在证据选择、引用数据结构和受控 Agentic RAG 上最扎实；
- DeerFlow 2.0 在 sandbox、middleware、sub-agent、文件系统、checkpoint 和长期运行工程上最完整。

不存在一个项目同时拥有最强搜索覆盖、最强证据纪律、最强领域呈现和最强生产运行时。源码显示，优秀深度研究系统通常不是“一个更聪明的 Agent”，而是三个层面的组合：

```text
研究策略（如何发现和分解问题）
× 证据系统（如何检索、压缩、引用和验证）
× Agent Runtime（如何并发、隔离、恢复和约束）
```

后续若继续调研，最有价值的下一步不是再增加项目数量，而是围绕同一批 benchmark 复现这几种机制：静态 sub-query、Supervisor ReAct、多视角访谈、PaperQA2 tool environment 和 breadth/depth recursion，并比较它们在覆盖、引用、成本和稳定性上的差异。
