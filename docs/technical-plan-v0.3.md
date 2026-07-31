# LogiSpace 0.3 深度研究技术方案

## 1. 版本目标

LogiSpace 0.3 要把“深度研究”从演示功能升级为真实、可追溯、成本可控、支持失败恢复的最小闭环。

核心结果：

1. 用户既能研究已有作品，也能输入数据库外的新作品。
2. 新作品只要求输入作品名和类型；作者、年份、版本存在多个可信候选时，再由系统请求用户确认。
3. 研究开始前生成基于 WorkDossier 的可审核 Plan。
4. 系统真实搜索并读取网页正文，而不是只保存搜索摘要。
5. 所有新增知识都形成 `Source → Evidence → Claim → Proposal` 证据链。
6. Proposal 经人工审核后，能够真实修改 WorkDossier 并发布新版本。
7. 搜索、来源、模型调用和 token 都有明确预算及停止条件。
8. 任务在后台运行，能够显示进度、错误、重试和部分完成结果。

0.3 不追求自由多 Agent、图数据库、全自动发布和完整的论文生态集成。

## 2. 架构决策

0.3 采用“单编排器、固定状态工作流”，暂不实现多个自由 Agent。

技术思路来源：

- Open Deep Research：有状态研究图、节点编排、checkpoint 和研究循环。
- STORM：先研究后写作、多视角研究提纲和基于新证据的追问。
- PaperQA2：文档切块、候选召回、重排、上下文化证据和精确引用。
- WorkDossier：最终领域知识结构、剧透控制、审核和版本发布。

总体流程：

```text
选择已有作品或输入新作品
  → 身份解析/必要时用户确认
  → 加载或创建 WorkDossier 基线
  → Coverage 分析
  → 生成 Research Plan
  → 用户批准 Plan
  → 生成有限查询
  → 搜索摘要初筛
  → 读取少量高质量来源
  → 正文清洗、切块与本地召回
  → Evidence 和 Claim 抽取
  → Claim 验证与冲突检测
  → 若有关键缺口且预算允许，则进入下一轮
  → 生成结构化 Proposal
  → 人工审核
  → 发布新版 WorkDossier
```

## 3. 新作品身份确认

### 3.1 用户输入

用户只需提供：

```text
作品名
作品类型：小说 / 电影 / 剧集 / 游戏 / 漫画
```

不要求用户预先填写作者、年份或具体版本。

### 3.2 解析逻辑

系统按以下顺序解析：

1. 标题和别名规范化。
2. 检索本地 catalog。
3. 搜索外部候选。
4. 根据标题、类型、作者、年份和外部标识聚合去重。
5. 计算候选置信度。

处理规则：

- 单一高置信候选：直接继续。
- 多个可信候选：状态进入 `awaiting_identity_confirmation`，向用户展示作者、年份、类型和版本差异。
- 没有可靠候选：要求用户重新输入或补充最少信息。

用户确认后才建立稳定 `work_id`。新作品创建 `0.0.0` 研究基线，审核发布后形成 `0.1.0`。

## 4. WorkDossier 驱动的 Research Plan

### 4.1 固定一级提纲

```text
identity
characters
relationships
locations_objects
timeline_truth
timeline_investigation
timeline_narrative
clues_testimony
crime_execution
murder_method
trick_misdirection
solution
creation_background
adaptations
controversies
```

### 4.2 Coverage 状态

每个板块计算结构覆盖、证据覆盖、来源数量、来源质量和冲突数量，输出：

```text
sufficient
needs_evidence
missing
conflicted
not_applicable
```

已有作品只研究 `needs_evidence`、`missing` 和 `conflicted` 板块。新作品以核心板块为默认研究范围。

### 4.3 低成本 Plan 生成

每个板块预置 2～4 个研究问题模板。Planner 首先使用规则和模板，仅在模板明显不适用时调用一次低成本模型补充问题。

每个 Plan 项包含：

```json
{
  "section": "timeline_narrative",
  "question": "叙述在哪些位置省略或压缩了关键行动？",
  "priority": 5,
  "queries": [
    "作品名 narrative omission",
    "作品名 叙述诡计 文本分析"
  ],
  "preferred_sources": ["primary_text", "scholarly_analysis"],
  "minimum_sources": 2
}
```

用户在正式研究前可以：

- 启用或禁用板块；
- 调整优先级；
- 增加自定义问题；
- 限制只研究原著或指定改编；
- 查看预计查询数、来源数和 token 预算；
- 批准 Plan。

## 5. 最小 token 搜索策略

### 5.1 搜索漏斗

```text
知识缺口
  → 2～3 个精确查询
  → 搜索引擎返回标题、URL、snippet
  → 本地规则评分和去重
  → 每个查询只读取 3～5 个高分页面
  → 网页正文清洗和切块
  → BM25/全文检索召回
  → 可选语义检索
  → 只将 5～8 个最佳片段交给模型
```

### 5.2 来源评分

优先考虑：

- 标题是否包含作品名或别名；
- 作者、年份和媒体版本是否匹配；
- 来源类型与完整性；
- 域名质量；
- 是否包含可访问正文；
- 是否与已有来源重复；
- 是否为聚合页或无出处内容。

搜索结果不是证据。只有成功读取并保存定位信息的原文才能成为强证据。

### 5.3 正文控制

- 不把完整网页交给模型。
- 移除导航、广告、推荐和评论。
- 使用内容 hash 去重和缓存。
- 按标题、段落、章节或页码切块。
- 每个候选片段控制在约 500～1200 字符。
- 相同来源在后续任务中复用，不重复下载和处理。

### 5.4 默认预算

```json
{
  "max_search_rounds": 2,
  "max_queries": 20,
  "max_queries_per_section": 3,
  "max_search_hits_per_query": 10,
  "max_pages_to_fetch_per_query": 3,
  "max_sources": 15,
  "max_evidence_chunks_per_question": 6,
  "max_model_calls": 6,
  "max_model_tokens": 50000
}
```

普通增量研究目标：1～2 轮、5～12 个查询、5～10 个实际来源、2～4 次模型调用。

### 5.5 停止条件

满足任一条件即停止：

- 必需板块达到 sufficient；
- 关键 Claim 已有可靠证据；
- 高风险 Claim 已有两个独立来源；
- 连续一轮没有新增有效 Evidence；
- 查询、来源、模型调用或 token 预算耗尽；
- 剩余缺口只能依赖不可访问材料；
- 出现必须人工判断的版本冲突。

## 6. 模型调用设计

每轮最多使用三类模型调用：

1. 可选 Plan 补充：仅在固定模板不足时使用低成本模型。
2. 批量 Evidence/Claim 抽取：同一板块多个片段一次处理。
3. 最终 Claim 验证：只验证进入 Proposal 的候选 Claim。

模型分工：

```text
查询生成与初筛：规则和模板
文本检索：BM25/本地全文检索
Plan 补充：低成本模型
Evidence 抽取：中等模型批处理
关键 Claim 验证：较强模型
Draft 合并：纯代码
```

禁止为每个搜索结果调用一次模型，也禁止使用模型重写整个 WorkDossier。

## 7. 证据链模型

### 7.1 SourceDocument

记录逻辑来源、规范 URL、标题、来源类型、媒体版本和可信度。

### 7.2 SourceSnapshot

记录实际读取内容、抓取时间、内容 hash、正文位置和抓取状态。快照不可变，以保证研究可复现。

### 7.3 EvidenceSpan

```json
{
  "evidence_id": "ev_001",
  "snapshot_id": "snap_001",
  "locator": {"page": 12, "paragraph": 4},
  "quote": "来源中的真实原文",
  "relevance_score": 0.91
}
```

约束：`quote` 必须能在 SourceSnapshot 中逐字找到。

### 7.4 Claim

```json
{
  "claim_id": "claim_001",
  "section": "timeline_truth",
  "text": "待写入的事实或解释",
  "claim_type": "fact",
  "evidence_ids": ["ev_001"],
  "support_status": "supported",
  "spoiler_level": "full",
  "media_version": "original_novel"
}
```

支持状态：

```text
supported
partially_supported
inferred
conflicted
unsupported
```

### 7.5 KnowledgeProposal

Proposal 必须携带可实际应用的强类型 payload，例如 `add_entity`、`add_relation`、`add_timeline_event`、`add_claim` 或 `flag_conflict`。空 payload 不允许发布。

## 8. Claim 验证

验证内容：

- Evidence 是否真的支持 Claim；
- quote 是否来自保存的原文；
- 来源是否相互独立；
- 是否混入其他改编版本；
- 时间顺序是否矛盾；
- 实体别名是否正确对齐；
- 内容是事实、推断还是解释；
- 剧透级别是否正确；
- 是否只有低可信度来源。

`unsupported` Claim 不得进入 Draft；`conflicted` Claim 只能生成冲突 Proposal，交给用户判断。

## 9. 后台任务与恢复

创建任务：

```http
POST /research/jobs
→ 202 Accepted
→ job_id
```

推荐技术栈：

- FastAPI：API；
- 固定状态图：0.3 编排；
- PostgreSQL：任务、来源、Evidence、Claim 和 Proposal；
- PostgreSQL checkpoint：断点恢复；
- Redis + ARQ：后台队列；
- SSE：前端进度；
- httpx：异步请求；
- trafilatura：HTML 正文；
- PyMuPDF：PDF；
- PostgreSQL FTS 或 Tantivy：关键词召回；
- Pydantic：结构化模型和输出校验。

0.3 暂不引入 Celery、Temporal、Neo4j、Elasticsearch、Qdrant 和自由多 Agent。

任务状态：

```text
created
awaiting_identity_confirmation
inventorying
planning
awaiting_plan_approval
searching
reading
extracting
verifying
reflecting
drafting
needs_review
partially_completed
budget_exhausted
published
failed
```

搜索超时应进入 retrying/fallback，而不是直接 failed。单个来源失败不应终止整个任务。

## 10. API 设计

### 10.1 作品身份

```http
POST /works/resolve
POST /works/resolve/{resolution_id}/confirm
```

### 10.2 研究任务

```http
POST /research/jobs
GET  /research/jobs/{job_id}
GET  /research/jobs/{job_id}/events
GET  /research/jobs/{job_id}/plan
POST /research/jobs/{job_id}/plan/approve
POST /research/jobs/{job_id}/pause
POST /research/jobs/{job_id}/resume
POST /research/jobs/{job_id}/cancel
POST /research/jobs/{job_id}/retry
GET  /research/jobs/{job_id}/coverage
GET  /research/jobs/{job_id}/sources
GET  /research/jobs/{job_id}/evidence
GET  /research/jobs/{job_id}/claims
GET  /research/jobs/{job_id}/proposals
GET  /research/jobs/{job_id}/draft
POST /research/jobs/{job_id}/review
POST /research/jobs/{job_id}/publish
```

## 11. 前端体验

研究界面分为四步：

1. 创建研究：选择已有作品，或输入作品名和类型。
2. 身份确认：只有多个候选时才要求选择作者、年份或版本。
3. Plan：查看板块、知识缺口、问题、预算并批准。
4. 任务与审核：查看进度、来源、token、错误、Proposal 和 WorkDossier diff。

审核界面并排显示：

```text
知识变更 | 支持 Claim | 原始证据 | 来源与定位
```

发布前显示真实差异，例如新增实体、关系、时间线事件、Claim 和冲突数量。

## 12. 数据存储

运行任务不再以 JSON 文件作为正式主存储。核心表：

```text
works
work_aliases
work_external_ids
work_versions
research_jobs
research_job_steps
research_plans
research_questions
search_runs
search_hits
source_documents
source_snapshots
document_chunks
evidence_spans
claims
claim_evidence
knowledge_proposals
proposal_reviews
dossier_drafts
published_dossiers
```

PostgreSQL 存储结构化数据；HTML、PDF 和大型正文快照存本地对象目录或 MinIO/S3。

## 13. 实施阶段

### 阶段 A：真实来源闭环

- 统一研究 API；
- 后台任务；
- 搜索 provider；
- HTML/PDF Reader；
- SourceSnapshot；
- EvidenceSpan；
- 错误、重试和进度展示。

### 阶段 B：Plan 与成本控制

- WorkDossier Coverage；
- 固定问题模板；
- Plan 审核；
- 搜索漏斗；
- 预算与停止条件；
- 缓存和去重。

### 阶段 C：结构化知识增量

- Claim 和验证；
- 强类型 Proposal；
- Proposal 应用器；
- WorkDossier diff；
- 审核后真实发布。

### 阶段 D：新作品

- 作品名和类型输入；
- 候选身份解析；
- 多候选用户确认；
- 新建研究基线；
- 首次发布 0.1.0。

多 Researcher 并行和更复杂的 STORM 式动态追问留到 0.4。

## 14. 测试与评估

单元和集成测试必须覆盖：

- 单一候选自动继续；
- 多个候选请求用户确认；
- Plan 生成、编辑和批准；
- 搜索预算强制执行；
- provider fallback；
- 网页读取和内容去重；
- Evidence quote 可在 SourceSnapshot 中找到；
- Claim 验证；
- Proposal payload 可应用；
- WorkDossier diff；
- timeout 重试；
- checkpoint 恢复；
- 无证据时禁止发布。

使用固定录制的搜索和网页数据运行 CI，真实 provider 测试放入独立 integration suite。

首批黄金作品：

- 《罗杰疑案》；
- 《东方快车谋杀案》；
- 《嫌疑人X的献身》。

## 15. 0.3 验收标准

1. 用户能输入数据库外的新作品和类型。
2. 多个可信候选时系统请求用户确认，单一候选不增加操作负担。
3. 系统生成 WorkDossier 驱动的 Plan，用户可删减后启动。
4. 系统真实读取并缓存网页或 PDF 正文。
5. 不把完整网页直接发送给模型。
6. 每条新增 Claim 都能定位到网页段落、章节或 PDF 页码。
7. Proposal 包含可以实际执行的结构化 payload。
8. 审核后 Draft 相对基线产生真实知识差异。
9. 已有作品可以发布增量版本。
10. 新作品可以发布首个 0.1.0。
11. 搜索超时能够重试或降级，并展示具体原因。
12. 普通增量研究默认不超过 6 次模型调用。
13. 达到预算后保留已有成果并进入部分完成状态。
14. 无真实证据的新增事实不得发布。

## 16. 最终定义

LogiSpace 0.3 是：

> 单编排器、固定领域提纲、有限搜索、本地筛选、批量模型抽取、证据级审核、版本化发布的 WorkDossier 深度研究系统。

0.3 首先保证证据真实性、成本可控和产品闭环；0.4 再在这一基础上增加并行 Researcher 和更动态的研究策略。
