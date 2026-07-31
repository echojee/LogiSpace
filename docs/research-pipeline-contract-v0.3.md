# LogiSpace 0.3 深度研究流水线契约与边界报告

> 状态：架构决策草案  
> 目标：在继续实现前，统一 `Plan → Search → Summarize → Deposit` 的阶段目的、数据边界、质量门槛、成本控制与失败恢复语义。  
> 结论：原四段链路应细化为可审计的固定流水线；“Summarize”不再作为单一阶段存在。

## 1. 执行摘要

LogiSpace 0.3 的深度研究不是“搜索后生成一篇总结”，而是生产一个可以安全合并和发布的知识增量。最终结果必须同时满足：

1. 身份明确：研究对象是确定的作品及媒体版本。
2. 来源真实：搜索命中必须进一步读取正文；snippet 不能成为强证据。
3. 证据可复现：每条 Evidence 可以定位到不可变 SourceSnapshot 中的原文。
4. Claim 可验证：Claim 的支持状态由证据、来源独立性、版本一致性和内容类型共同决定。
5. 变更可执行：Proposal 必须携带符合 WorkDossier Schema 的强类型 payload。
6. 发布可回滚：Deposit 和 Publish 必须是幂等、事务化、版本化的操作。
7. 成本可控制：查询、页面、来源、模型调用和 token 都有硬预算与停止条件。
8. 失败可恢复：每个昂贵阶段完成后保存 checkpoint，重试不重复产生费用或脏数据。

建议的正式流水线：

```text
Resolve Identity
→ Inventory
→ Plan
→ Discover
→ Acquire
→ Normalize
→ Retrieve
→ Extract Evidence
→ Verify Claims
→ Propose Changes
→ Human Review
→ Deposit
→ Publish
```

其中：

- `Discover` 只发现候选来源；
- `Acquire` 才实际获取内容；
- `Retrieve` 只选出与问题相关的正文块；
- `Extract Evidence` 只建立原文证据和候选 Claim；
- `Verify Claims` 决定 Claim 能否用于知识变更；
- `Deposit` 只应用已批准 Proposal，不调用模型；
- `Publish` 只做版本发布，不改变审核内容。

## 2. 总体设计原则

### 2.1 阶段产物优先

每个阶段都必须产出结构化、可持久化、可独立检查的 artifact。禁止仅通过一个不断变大的内存对象隐式传递状态。

核心 artifact：

```text
WorkResolution
BaselineDossier
CoverageSnapshot
ResearchPlanRevision
SearchRun / SearchHit
SourceDocument / SourceSnapshot
DocumentChunk
RetrievalSet
EvidenceSpan
ClaimCandidate / VerifiedClaim
KnowledgeProposal
ProposalReview
DossierDraft / DossierDiff
PublishedDossier
```

### 2.2 控制面与数据面分离

控制面负责：

- 状态迁移；
- 预算；
- 重试和超时；
- checkpoint；
- 暂停、恢复和取消；
- 人工审批门。

数据面负责：

- 搜索结果；
- 正文和快照；
- 文档块；
- Evidence、Claim、Proposal；
- Dossier 草稿和发布版本。

控制状态不能代替数据产物。例如 `status=extracting` 不能说明抽取了什么，必须能查询对应 Evidence 和错误记录。

### 2.3 事实、推断和解释分离

Claim 必须明确属于：

```text
fact
inference
interpretation
```

三者使用不同发布门槛：

- `fact`：必须有直接证据；
- `inference`：必须展示推理依据，默认不能伪装为作品事实；
- `interpretation`：必须保留观点来源，不得写成唯一事实。

### 2.4 搜索不是证据

`SearchHit.snippet` 只用于初筛和排序，禁止进入 EvidenceSpan。只有成功读取的 SourceSnapshot 正文才能提供强证据。

### 2.5 模型不是数据库写入器

模型可以提出结构化候选，但不能直接修改 WorkDossier。所有写入均经过：

```text
模型候选
→ Pydantic 校验
→ Evidence/Claim 验证
→ Proposal
→ 人工审核
→ 纯代码应用器
```

## 3. 阶段详解

## 3.1 Resolve Identity：作品身份解析

### 目的

把用户输入的作品名和类型解析为稳定的作品身份及媒体版本，防止后续研究混入同名作品、翻拍版或其他媒介。

### 输入

```json
{
  "title": "作品名",
  "media_type": "novel | film | series | game | manga"
}
```

作者、年份和版本不是必填输入。

### 输出

`WorkResolution`：

```json
{
  "resolution_id": "...",
  "normalized_query": "...",
  "candidates": [],
  "decision": "resolved | awaiting_confirmation | unresolved",
  "selected_work": null,
  "evidence": [],
  "confidence": 0.0
}
```

### 边界

负责：

- 标题和别名规范化；
- 本地 catalog 匹配；
- 外部身份候选搜索；
- 标题、类型、作者、年份、外部 ID 聚类去重；
- 候选置信度计算；
- 必要时请求用户确认。

不负责：

- 研究作品内容；
- 建立人物、时间线或诡计知识；
- 因找不到身份而猜测作者或年份。

### 控制与优化

- 精确别名匹配优先于模糊匹配；
- 媒体类型不一致时不得自动合并；
- 单一高置信候选自动继续；
- 多个可信候选必须暂停；
- 只有用户确认或高置信唯一候选才能生成稳定 `work_id`；
- 外部身份查询结果应缓存，避免重复搜索。

### 失败语义

- 无可靠候选：`unresolved`，要求重新输入或补充最少信息；
- provider 超时：保留本地候选，标记解析降级；
- 多候选：`awaiting_identity_confirmation`，不是失败。

### 验收指标

- 黄金作品身份准确率；
- 单候选自动继续率；
- 错误合并率；
- 不必要确认率；
- 外部解析平均查询数。

## 3.2 Inventory：加载基线和知识盘点

### 目的

建立研究起点，明确哪些知识已存在、哪些有证据、哪些有冲突，避免每次全量重做。

### 输入

- 已确认 `Work`；
- 当前 Published WorkDossier（如果存在）；
- 已保存的 Source、Evidence 和 Claim 索引。

### 输出

- `BaselineDossier`；
- `CoverageSnapshot`；
- 基线版本号；
- 可复用来源和正文快照清单。

新作品基线固定为 `0.0.0`；已有作品使用当前发布版本。

### 边界

负责：

- 加载和验证基线 Schema；
- 统计结构覆盖、证据覆盖、来源质量和冲突；
- 判断板块是否 `not_applicable`；
- 识别可复用的已抓取来源。

不负责：

- 生成新研究问题；
- 联网搜索；
- 修改基线。

### 控制与优化

Coverage 必须分别计算：

```text
structure_count
verified_claim_count
evidence_count
independent_source_count
average_source_quality
conflict_count
staleness
```

Coverage 状态：

```text
sufficient
needs_evidence
missing
conflicted
not_applicable
```

已有结构但无证据应为 `needs_evidence`，不能视为 sufficient。

### 失败语义

- 基线 Schema 无效：任务 `failed`，禁止继续；
- 部分索引不可用：允许从 Dossier 重新构建；
- 历史快照缺失：标记证据失效，重新进入研究范围。

### 验收指标

- Coverage 与人工审计一致率；
- 已有来源复用率；
- 重复研究比例；
- 错误 sufficient 比例。

## 3.3 Plan：生成可审核研究计划

### 目的

把 Coverage 缺口转换为有限、明确、可预算的研究问题和查询策略。

### 输入

- Work 身份；
- CoverageSnapshot；
- 用户研究范围；
- 总预算和媒体版本限制。

### 输出

不可变的 `ResearchPlanRevision`：

```json
{
  "plan_id": "...",
  "revision": 1,
  "items": [],
  "budget": {},
  "source_policy": {},
  "estimated_cost": {},
  "approved_at": null
}
```

### 边界

负责：

- 选择要研究的板块；
- 为每个板块生成问题；
- 生成短而精确的搜索查询；
- 定义来源偏好和最低来源数；
- 估算查询、页面、来源、模型调用和 token。

不负责：

- 执行搜索；
- 读取网页；
- 预先生成答案；
- 修改 WorkDossier。

### 控制与优化

- 规则模板优先；
- 只有模板明显不足时调用一次低成本 Planner；
- 同一查询跨板块去重；
- 查询应是检索表达式，不是完整研究问题；
- 用户修改后生成新 revision，不覆盖旧 Plan；
- Plan 批准后冻结；若要修改，创建新 revision 并重新审批；
- 原著与指定改编限制写入 Plan 的 `media_scope`，而不是仅写在 prompt。

### 失败语义

- 没有启用板块：返回 422，不启动任务；
- 估算超过总预算：要求删减或明确提高预算；
- Planner 模型失败：退回规则模板，不阻断任务。

### 验收指标

- 每个问题平均查询数；
- 查询重复率；
- Plan 修改率；
- 预计成本与实际成本偏差；
- 无效研究问题比例。

## 3.4 Discover：发现候选来源

### 目的

使用有限查询发现可能相关的来源，并保留搜索过程，不把搜索摘要当证据。

### 输入

- 已批准 Plan；
- SearchProvider 配置；
- 查询预算；
- Work 标题、别名、作者、年份和媒体版本。

### 输出

- `SearchRun`；
- `SearchHit`；
- provider 错误和 fallback 记录；
- 去重、评分后的候选 URL 队列。

### 边界

负责：

- 调用搜索 provider；
- 保存标题、URL、snippet 和排名；
- URL 规范化和去重；
- 本地相关性与来源质量评分；
- provider fallback。

不负责：

- 宣称页面内容支持某个结论；
- 把 snippet 写入 Evidence；
- 下载整页正文。

### 控制与优化

评分至少考虑：

- 标题/别名匹配；
- 媒体类型、作者和年份匹配；
- 域名质量；
- 来源类型；
- 是否为聚合页、标签页或搜索页；
- 与已有 URL、canonical URL 和内容 hash 的重复；
- 是否已有可复用快照。

硬限制：

```text
max_queries
max_queries_per_section
max_search_hits_per_query
max_search_rounds
```

查询零命中必须被记录，不能静默变成“没有来源”。

### 失败语义

- 单 provider 超时：`retrying`，随后 fallback；
- 全部 provider 失败：保留 Plan 和 SearchRun，进入 `partially_completed`；
- 某个查询零命中：允许其他查询继续。

### 验收指标

- 高分命中可读率；
- 无关来源抓取率；
- 查询零命中率；
- provider fallback 成功率；
- 每个有效来源消耗的查询数。

## 3.5 Acquire：获取真实正文

### 目的

把候选 URL 转换为可复现的不可变 SourceSnapshot。

### 输入

- 排序后的 SearchHit；
- 可复用快照缓存；
- 页面预算和超时策略。

### 输出

- `SourceDocument`：逻辑来源；
- `SourceSnapshot`：一次实际抓取的不可变内容；
- 抓取状态、HTTP 元数据、内容 hash 和 object path。

### 边界

负责：

- HTTP 获取和重试；
- 重定向和 canonical URL；
- HTML、PDF 类型识别；
- 抓取正文原始内容；
- 内容 hash 去重；
- 缓存复用；
- 记录失败原因。

不负责：

- 判断内容与问题是否相关；
- 生成 Evidence 或 Claim；
- 用搜索 snippet 代替失败正文。

### 控制与优化

- 每查询最多读取 3 个高分页面；
- 全任务最多 15 个来源；
- 设置响应体大小上限；
- 对 robots、登录墙、付费墙和反爬状态分类；
- 相同内容 hash 只保存一个对象；
- SourceDocument 可有多个 Snapshot，但 Snapshot 不可变；
- PDF 必须保存页码映射；HTML 必须保存正文段落映射；
- 失败页面只记录元数据，不创建伪正文。

### 失败语义

- 单页面失败：继续其他页面；
- timeout：有限重试，随后 fallback；
- 不支持的格式：标记 `unsupported_media`；
- 正文为空：标记 `empty_body`；
- 全部页面失败：`partially_completed`。

### 验收指标

- 正文读取成功率；
- 内容去重率；
- 缓存命中率；
- 平均正文字符数；
- 单来源失败对任务完成率的影响。

## 3.6 Normalize：正文清洗与结构化切块

### 目的

把正文转成可检索、保留定位信息的 DocumentChunk，减少发送给模型的无关内容。

### 输入

- SourceSnapshot 原始正文；
- HTML DOM、PDF 页码或文本段落映射。

### 输出

`DocumentChunk`：

```json
{
  "chunk_id": "...",
  "snapshot_id": "...",
  "locator": {
    "page": null,
    "paragraph_start": 12,
    "paragraph_end": 15
  },
  "content": "...",
  "token_count": 0
}
```

### 边界

负责：

- 移除导航、广告、推荐和评论；
- 保留标题、章节、段落或页码结构；
- 切块和轻微重叠；
- 计算全文检索索引；
- 检测语言和异常编码。

不负责：

- 改写正文；
- 总结正文；
- 修复来源中的事实错误；
- 生成 Claim。

### 控制与优化

- chunk 目标长度 500–1200 字符；
- 不能跨 PDF 页或明显章节边界无条件拼接；
- locator 必须能映射回 Snapshot；
- 编码异常或乱码块不得进入模型；
- 小段落可以聚合，但原始段落范围必须保留；
- 切块结果由 `content_hash + chunker_version` 缓存。

### 失败语义

- 无有效块：来源保留，但不进入 Retrieve；
- locator 无法建立：不得作为强证据来源；
- 清洗质量低：降低来源质量并记录 warning。

### 验收指标

- chunk locator 可回溯率；
- 噪声块比例；
- 平均块长度；
- 编码异常率；
- 重复块比例。

## 3.7 Retrieve：为研究问题召回正文块

### 目的

从已获取正文中，为每个研究问题选出少量最相关上下文。

### 输入

- ResearchPlanItem；
- DocumentChunk 索引；
- Work 标题和别名；
- 来源质量信息。

### 输出

`RetrievalSet`：

```json
{
  "question_id": "...",
  "candidates": [
    {
      "chunk_id": "...",
      "lexical_score": 0.0,
      "semantic_score": null,
      "source_quality": 0.0,
      "final_score": 0.0
    }
  ]
}
```

### 边界

负责：

- BM25/PostgreSQL FTS 召回；
- 可选语义召回；
- 混合排序；
- 来源多样性控制；
- 每个问题限制候选片段数。

不负责：

- 判断 Claim 真伪；
- 生成总结；
- 把检索相关性当作证据支持度。

### 控制与优化

- 默认每问题最多 6 个块；
- 同一来源不能垄断全部候选；
- 查询包含作品标题、别名和问题关键词；
- 中文至少支持字符 bigram 或合适分词；
- BM25 零结果时允许经过审计的 fallback，但不能直接取任意首段；
- 语义检索是可选增强，不应成为 0.3 的单点依赖。

### 失败语义

- 某问题无召回：标记该板块 `needs_evidence`；
- 全部问题无召回：保留来源，任务部分完成；
- 索引失败：可以重建，不重新下载正文。

### 验收指标

- Recall@6；
- 来源多样性；
- 无关块比例；
- 每个有效 Evidence 的候选块数；
- 重建索引耗时。

## 3.8 Extract Evidence：批量抽取证据和候选 Claim

### 目的

只基于 RetrievalSet 中的正文块，批量生成可定位 EvidenceSpan 和 ClaimCandidate。

### 输入

- 1–5 个同批 PlanItem；
- 每问题最多 6 个正文块；
- Work 和媒体版本上下文；
- 严格 JSON Schema。

### 输出

- `EvidenceSpan`；
- `ClaimCandidate`；
- 模型调用和 token 用量；
- Schema 或 quote 校验错误。

### 边界

负责：

- 选择支持 Claim 的原文 quote；
- 生成简洁候选 Claim；
- 标注 fact/inference/interpretation；
- 标注媒体版本；
- 批量处理多个问题。

不负责：

- 使用模型先验补充来源中不存在的信息；
- 判定最终支持状态；
- 生成 Proposal；
- 修改 Dossier。

### 控制与优化

- quote 必须是 chunk 中的连续逐字子串；
- chunk 必须属于保存的 Snapshot；
- 模型返回无效 JSON 时整批失败并可重试；
- 无效 quote 仅丢弃对应 Evidence，不污染其他结果；
- 每批最多处理 5 个板块；
- 全任务抽取调用目标 3 次以内；
- 输入只包含候选片段，不包含完整网页；
- Prompt 必须禁止使用模型先验。

### 失败语义

- 无模型凭证：保留 Discover/Acquire/Retrieve 成果，`partially_completed`；
- 部分 quote 无效：丢弃并记录；
- 整批 Schema 无效：有限重试，仍失败则保留其他批次；
- 没有任何有效 Evidence：不得进入 Deposit。

### 验收指标

- exact quote 通过率；
- 每次模型调用产生的有效 Evidence 数；
- Schema 有效率；
- 人工判断的 Evidence 相关率；
- 每条 Evidence token 成本。

## 3.9 Verify Claims：Claim 支持和冲突验证

### 目的

判断候选 Claim 是否被证据真正支持，并识别推断、冲突、版本混用和低质量来源风险。

### 输入

- ClaimCandidate；
- EvidenceSpan；
- SourceDocument 和 Snapshot 元数据；
- Work 媒体版本；
- 已有 VerifiedClaim。

### 输出

`VerifiedClaim`：

```text
supported
partially_supported
inferred
conflicted
unsupported
```

以及验证原因和冲突组。

### 边界

负责：

- 验证 quote 是否实际支持 Claim；
- 检查来源独立性；
- 检查原著/改编版本一致性；
- 检测与已有 Claim 的冲突；
- 区分事实、推断和解释；
- 检查剧透级别。

不负责：

- 搜索新来源；
- 自动解决需要人工判断的冲突；
- 修改 Claim 以“适配”证据；
- 创建 Dossier 变更。

### 控制与优化

- `unsupported` 不得进入 Proposal；
- `conflicted` 只能生成 `flag_conflict` Proposal；
- 高风险板块至少需要两个独立来源才能 supported：
  - crime_execution；
  - murder_method；
  - solution；
  - controversies。
- 同域转载和相同内容 hash 不算独立来源；
- 最终验证只处理将进入 Proposal 的 Claim；
- 全任务验证模型调用目标 1 次。

### 失败语义

- 验证模型失败：Claim 保持 candidate，不得发布；
- 来源不足：partial，而不是 supported；
- 版本冲突：conflicted，等待人工决定；
- 所有 Claim unsupported：任务部分完成，不生成知识变更。

### 验收指标

- supported 精确率；
- unsupported 漏放率；
- 版本混用检出率；
- 冲突检出率；
- 人工复核推翻率。

## 3.10 Propose Changes：生成强类型知识变更

### 目的

把 VerifiedClaim 转换为可以由纯代码应用到 WorkDossier 的结构化操作。

### 输入

- VerifiedClaim；
- 基线 WorkDossier；
- Dossier Schema 和 ontology；
- 实体别名索引。

### 输出

`KnowledgeProposal`：

```json
{
  "proposal_id": "...",
  "operation": "add_entity",
  "target_section": "characters",
  "payload": {},
  "claim_ids": [],
  "evidence_ids": [],
  "preconditions": {},
  "review_status": "pending"
}
```

### 边界

负责：

- 选择操作类型；
- 实体对齐和去重；
- 构造强类型 payload；
- 声明应用前置条件；
- 关联 Claim 和 Evidence。

不负责：

- 自动批准 Proposal；
- 直接修改 Draft；
- 用 `Claim` 实体绕过正式 Dossier Schema；
- 把自然语言摘要当成 payload。

### 控制与优化

支持的操作应明确建模：

```text
add_entity
update_entity
add_relation
add_timeline_event
add_claim_record
flag_conflict
mark_not_applicable
```

关键约束：

- payload 不能为空；
- payload 必须通过操作专属 Pydantic 模型；
- `preconditions` 包含基线版本和目标对象 hash，防止并发覆盖；
- 已存在等价实体时生成 update/merge，而不是重复 add；
- Claim 应进入独立 Claim 记录或 Dossier 正式字段，不应临时伪装为普通 DossierEntity。

### 失败语义

- 无法映射到 Schema：标记 `unmappable`，不得发布；
- 实体对齐歧义：请求人工选择；
- 前置条件不满足：Deposit 时拒绝并重新基于最新版本生成。

### 验收指标

- payload Schema 通过率；
- Proposal 可应用率；
- 重复实体产生率；
- 人工修改 Proposal 比例；
- 无法映射 Claim 比例。

## 3.11 Human Review：证据级人工审核

### 目的

让用户在知识进入正式 Dossier 前检查变更、Claim、原始证据和来源定位。

### 输入

- KnowledgeProposal；
- VerifiedClaim；
- EvidenceSpan；
- SourceDocument/Snapshot；
- 预计 Dossier diff。

### 输出

- `ProposalReview`；
- approved/rejected/needs_changes；
- 审核备注；
- 审核人和时间。

### 边界

负责：

- 展示完整可追溯链；
- 逐条或批量审批；
- 冲突选择；
- 记录审核决定。

不负责：

- 隐式重新运行模型；
- 自动修改证据原文；
- 在 UI 中绕过 Proposal Schema 直接编辑数据库。

### 控制与优化

界面并排显示：

```text
知识变更 | 支持 Claim | 原始 Evidence | 来源与 locator
```

必须支持：

- 按板块过滤；
- 查看媒体版本；
- 展开 SourceSnapshot 上下文；
- 查看冲突双方；
- 显示预计 diff；
- 分离“批准”与“发布”动作。

### 失败语义

- 审核过期：若基线版本变化，所有批准状态失效；
- 部分批准：只对 approved Proposal 生成 Draft；
- 冲突未决：相关 Proposal 不可 Deposit。

### 验收指标

- 审核平均耗时；
- Proposal 拒绝率；
- 发布后纠错率；
- 审核人查看证据比例；
- 批量批准后回滚比例。

## 3.12 Deposit：应用批准的知识变更

### 目的

通过纯代码、事务化、幂等的应用器，把批准 Proposal 合并到 Draft WorkDossier。

### 输入

- 基线 WorkDossier；
- approved Proposal；
- Proposal preconditions；
- 目标 Schema/ontology 版本。

### 输出

- `DossierDraft`；
- `DossierDiff`；
- 每条 Proposal 的应用结果；
- 质量检查结果。

### 边界

负责：

- 重新加载最新基线；
- 校验前置条件；
- 按依赖顺序应用 Proposal；
- 运行 Schema、引用完整性和关系完整性检查；
- 生成真实 diff；
- 保存草稿。

不负责：

- 搜索或调用模型；
- 自动改变审核内容；
- 发布版本；
- 对失败 Proposal 静默降级。

### 控制与优化

- 整个 Deposit 使用数据库事务；
- 每条 Proposal 有幂等键；
- 相同 Proposal 重试不能重复添加实体；
- 先实体、后关系、再时间线和 Claim 引用；
- 任一强一致性检查失败时整体回滚，或明确采用可审计的部分应用策略；
- 推荐 0.3 使用整体回滚，降低复杂度；
- diff 必须由实际应用结果计算，不能由 Proposal 数量估算。

### 失败语义

- 基线版本变化：`stale_plan`，拒绝 Deposit；
- payload 无效：拒绝对应 Proposal；
- 引用不存在：事务回滚；
- 重复提交：返回已有 Deposit 结果。

### 验收指标

- 幂等测试通过率；
- Proposal 实际应用率；
- diff 准确率；
- Deposit 回滚率；
- 发布前 Schema 错误数。

## 3.13 Publish：发布版本化 WorkDossier

### 目的

把通过质量门槛的 Draft 原子发布为新的正式版本。

### 输入

- DossierDraft；
- DossierDiff；
- Review 记录；
- 发布质量报告。

### 输出

- `PublishedDossier`；
- 新版本号；
- manifest/current version 更新；
- 审计记录。

### 边界

负责：

- 计算目标版本；
- 原子写入发布记录；
- 更新 current pointer；
- 保存 base/target/diff/review 审计；
- 使检索索引感知新版本。

不负责：

- 修改 Draft 内容；
- 自动批准审核；
- 在无真实 Evidence 时发布；
- 覆盖旧发布版本。

### 控制与优化

版本规则：

- 新作品：`0.0.0 → 0.1.0`；
- 已有作品普通增量：次版本递增；
- Schema/ontology 不兼容变化：单独迁移，不由普通研究任务决定。

发布门槛：

- 至少一个 approved 且成功应用的 Proposal；
- 所有新增 fact Claim 有可定位 Evidence；
- 无 unsupported Claim；
- unresolved conflict 不进入事实字段；
- Dossier Schema 和引用完整性通过；
- diff 非空；
- Review 未过期。

### 失败语义

- current version 已变化：拒绝发布并重新 Deposit；
- 索引更新失败：Dossier 发布可成功，但标记索引待重试；
- pointer 更新失败：事务回滚，不产生半发布状态。

### 验收指标

- 发布成功率；
- 半发布事件数（目标必须为 0）；
- 发布后索引延迟；
- 回滚成功率；
- 发布后证据断链数（目标必须为 0）。

## 4. 跨阶段控制设计

## 4.1 固定状态机

推荐状态：

```text
created
awaiting_identity_confirmation
inventorying
planning
awaiting_plan_approval
discovering
acquiring
normalizing
retrieving
extracting
verifying
proposing
needs_review
depositing
ready_to_publish
published
paused
retrying
partially_completed
budget_exhausted
cancelled
failed
```

状态迁移原则：

- 只有 orchestrator 可以改变主状态；
- worker 执行阶段函数，但通过原子 compare-and-set 领取阶段；
- 每个阶段有 `attempt_id`、lease 和 heartbeat；
- 超时 worker 的 lease 可被新 worker 接管；
- `pause` 在安全检查点生效；
- `cancel` 不删除已有产物；
- `retry` 从最近完整 checkpoint 继续。

## 4.2 幂等和 checkpoint

每个阶段的幂等键：

```text
identity: normalized_title + media_type + resolver_version
plan: coverage_hash + planner_version + user_scope
search: provider + normalized_query + search_window
snapshot: canonical_url + response_hash
chunk: snapshot_hash + chunker_version
retrieval: question_hash + index_version + retriever_version
extraction: retrieval_set_hash + prompt_version + model
verification: claim_set_hash + verifier_version + model
proposal: verified_claim_hash + base_dossier_hash + mapper_version
deposit: approved_proposal_set_hash + base_dossier_hash
publish: work_id + target_version + draft_hash
```

只有完整阶段产物才能成为 checkpoint。阶段执行一半产生的临时记录要么标记 attempt，要么在重试前清理。

## 4.3 预算模型

预算必须统一由 `BudgetLedger` 管理，而不是各函数自行累加。

```json
{
  "search_rounds": {"used": 0, "limit": 2},
  "queries": {"used": 0, "limit": 20},
  "pages": {"used": 0, "limit": 15},
  "model_calls": {"used": 0, "limit": 6},
  "model_tokens": {"used": 0, "limit": 50000}
}
```

执行任何收费或昂贵操作前必须原子预留预算，完成后结算实际用量；失败也记录成本。

推荐模型调用分配：

```text
Plan 补充：0–1 次
Evidence/Claim 批量抽取：1–3 次
最终 Claim 验证：1 次
总计：2–5 次，硬上限 6 次
```

## 4.4 停止和反思条件

每轮结束后由规则函数决定是否进入下一轮，不使用自由 Agent：

停止条件：

- 核心板块达到 sufficient；
- 关键 Claim 已有可靠证据；
- 高风险 Claim 有两个独立来源；
- 本轮没有新增有效 Evidence；
- 任一预算耗尽；
- 剩余材料不可访问；
- 出现需要人工决定的版本冲突。

允许第二轮的条件：

- 仍有高优先级缺口；
- 第一轮产生了能明确转化为新查询的缺口；
- 查询和页面预算仍足够；
- 预计新增价值大于成本阈值。

## 4.5 错误分类

错误必须结构化：

```text
configuration_error
provider_timeout
provider_rate_limit
zero_search_hits
http_error
robots_denied
paywall
unsupported_media
empty_body
parse_error
encoding_error
retrieval_empty
model_unavailable
model_timeout
invalid_model_json
invalid_quote
claim_unsupported
version_conflict
proposal_unmappable
stale_baseline
deposit_conflict
publish_conflict
budget_exhausted
```

每类错误定义：是否可重试、最大次数、fallback、是否影响整个任务。

## 5. 数据存储边界

## 5.1 PostgreSQL

存储结构化、可查询、需要事务的数据：

```text
works
work_aliases
work_external_ids
work_versions
work_resolutions
research_jobs
research_job_attempts
research_job_events
coverage_snapshots
research_plans
research_plan_items
search_runs
search_hits
source_documents
source_snapshots
document_chunks
retrieval_sets
retrieval_candidates
evidence_spans
claim_candidates
verified_claims
claim_evidence
claim_conflicts
knowledge_proposals
proposal_reviews
deposit_runs
dossier_drafts
dossier_diffs
published_dossiers
```

## 5.2 对象存储

存储体积大、不可变的内容：

- 原始 HTML；
- 原始 PDF；
- 清洗后的正文；
- 必要的页面渲染或 OCR 产物。

PostgreSQL 仅保存 hash、路径、MIME、大小和抓取元数据。

## 5.3 Redis/队列

Redis 只负责：

- 待执行任务；
- worker lease/heartbeat；
- 短期事件通知；
- 限流计数。

Redis 不是事实存储。队列丢失后应能从 PostgreSQL 未完成状态重建。

## 6. API 边界

建议保留文档中的资源 API，并增加 revision/attempt 语义：

```text
POST /works/resolve
POST /works/resolve/{resolution_id}/confirm

POST /research/jobs
GET  /research/jobs/{job_id}
GET  /research/jobs/{job_id}/events

GET  /research/jobs/{job_id}/coverage
GET  /research/jobs/{job_id}/plan
POST /research/jobs/{job_id}/plan/revisions
POST /research/jobs/{job_id}/plan/{revision}/approve

GET  /research/jobs/{job_id}/search-runs
GET  /research/jobs/{job_id}/sources
GET  /research/jobs/{job_id}/snapshots
GET  /research/jobs/{job_id}/retrieval
GET  /research/jobs/{job_id}/evidence
GET  /research/jobs/{job_id}/claims
GET  /research/jobs/{job_id}/proposals

POST /research/jobs/{job_id}/review
POST /research/jobs/{job_id}/deposit
GET  /research/jobs/{job_id}/draft
GET  /research/jobs/{job_id}/diff
POST /research/jobs/{job_id}/publish

POST /research/jobs/{job_id}/pause
POST /research/jobs/{job_id}/resume
POST /research/jobs/{job_id}/cancel
POST /research/jobs/{job_id}/retry
```

`POST /research/jobs` 返回 202。任何长耗时操作都不能占用请求直到研究完成。

## 7. 质量门槛

## 7.1 阶段门槛

| 阶段 | 进入下一阶段的最低条件 |
|---|---|
| Identity | 稳定 work_id，媒体版本明确 |
| Plan | 至少一个启用问题，预算合法，已审批 |
| Discover | 至少一个达到阈值的 SearchHit，或明确部分完成 |
| Acquire | 至少一个成功 SourceSnapshot |
| Normalize | 至少一个有 locator 的 DocumentChunk |
| Retrieve | 至少一个问题有候选块 |
| Extract | 至少一个 exact-quote EvidenceSpan |
| Verify | 至少一个非 unsupported Claim |
| Propose | 至少一个通过强类型 Schema 的 Proposal |
| Review | 至少一个 approved Proposal，冲突已处理 |
| Deposit | Draft Schema、引用完整性、diff 全部通过 |
| Publish | Review 未过期，diff 非空，证据链完整 |

## 7.2 发布禁止条件

满足任意一项即禁止发布：

- 新增事实没有 Evidence；
- quote 不在 Snapshot；
- Snapshot 不可读取或 hash 不一致；
- unsupported Claim 被 Proposal 引用；
- conflicted Claim 被当作确定事实写入；
- Proposal payload 为空或 Schema 不合法；
- 基线版本已经变化；
- Draft diff 为空；
- Review 已过期；
- Dossier 引用完整性失败。

## 8. 测试策略

## 8.1 单元测试

- 标题和别名规范化；
- 身份候选聚类和置信度；
- Coverage 计算；
- 查询模板和去重；
- URL canonicalization；
- 来源评分；
- HTML/PDF locator；
- 内容 hash 去重；
- 中文 BM25；
- exact quote 校验；
- Claim 来源独立性；
- Proposal payload Schema；
- Proposal 应用器幂等性；
- diff 计算。

## 8.2 录制集成测试

固定保存：

- 搜索 provider 响应；
- HTML/PDF 原始内容；
- 模型 JSON 输出；
- 预期 Evidence、Claim、Proposal 和 diff。

录制测试必须验证整条链，而不是 mock 掉中间所有阶段。

## 8.3 真实 provider 测试

放在独立 integration suite：

- 每日或手动运行；
- 不作为普通 CI 的稳定性依赖；
- 记录 provider 延迟、零命中、正文成功率和格式漂移。

## 8.4 黄金作品验收

三部黄金作品：

- 《罗杰疑案》；
- 《东方快车谋杀案》；
- 《嫌疑人X的献身》。

每部作品至少准备：

- 身份黄金数据；
- 5–10 个核心研究问题；
- 允许使用的固定来源；
- Evidence locator；
- 关键 Claim 及支持状态；
- 预期 WorkDossier diff；
- 应被识别的版本混用或冲突案例。

## 9. 可观测性

每个 job 需要记录：

- 当前阶段和阶段耗时；
- 每阶段 attempt；
- 查询、命中、页面和来源数量；
- HTTP 失败类别；
- 正文字符数和 chunk 数；
- 每问题召回数量；
- exact quote 通过率；
- Claim 各支持状态数量；
- Proposal 审核结果；
- 预算使用量；
- checkpoint 和恢复次数；
- 最终停止原因。

推荐事件示例：

```json
{
  "event_type": "stage_completed",
  "job_id": "...",
  "stage": "acquiring",
  "attempt": 2,
  "metrics": {
    "pages_attempted": 8,
    "snapshots_created": 5,
    "cache_hits": 2
  },
  "errors": []
}
```

## 10. 安全与合规

- 限制允许的 URL scheme 为 HTTP/HTTPS；测试 fixture 的 file URL 只能在测试环境开启；
- 防止 SSRF：禁止访问 loopback、私网、link-local 和云元数据地址；
- 限制重定向次数和响应体大小；
- 不在日志中保存 API key、Cookie 或 Authorization；
- 对抓取内容进行 MIME 验证；
- 保存引用必要片段和定位，避免无必要复制整篇受版权保护内容到用户输出；
- 对对象存储设置访问控制和保留策略；
- 用户取消任务后保留审计元数据，按策略删除未使用正文。

## 11. 推荐实施顺序

### 阶段 1：冻结契约

1. 确认本报告中的阶段划分；
2. 确认 Claim 是否作为 WorkDossier 正式一级字段，而不是 DossierEntity；
3. 确认 PostgreSQL 是 0.3 唯一正式 runtime store；
4. 确认 Redis + ARQ 为生产 worker，SQLite/inline 仅用于开发和测试；
5. 冻结 Proposal 操作类型和 payload Schema。

### 阶段 2：持久化和 orchestrator

1. 建立迁移系统；
2. 实现 repository interface；
3. 实现 job lease、attempt、heartbeat；
4. 实现固定状态迁移；
5. 实现 BudgetLedger；
6. 实现 checkpoint 恢复测试。

### 阶段 3：研究数据面

1. SearchProvider 接口和录制 provider；
2. HTML/PDF Reader；
3. SourceSnapshot/object store；
4. chunker 和 FTS；
5. RetrievalSet；
6. 批量抽取和 quote validator；
7. Claim verifier。

### 阶段 4：知识合并

1. Proposal 强类型模型；
2. 实体对齐器；
3. 纯代码 ProposalApplier；
4. diff；
5. review；
6. Deposit 事务；
7. Publish 和 rollback。

### 阶段 5：产品与验收

1. 四步前端；
2. SSE 进度；
3. 证据级审核；
4. 三部黄金作品；
5. 成本和质量评测；
6. 真实 provider 演示；
7. 达标后提交 0.3。

## 12. 继续开发前需要确认的决策

以下决策会显著改变后续实现，不应由代码临时决定：

1. **Claim 在 WorkDossier 中的位置**  
   推荐：加入正式 `claims` 字段，实体通过 `entity_ids` 引用 Claim；不要把 Claim 伪装为 `DossierEntity(entity_type="Claim")`。

2. **正式运行存储**  
   推荐：PostgreSQL 是唯一正式 store；SQLite 只作为测试 adapter。运行时不能在两种存储之间产生不同语义。

3. **后台执行方式**  
   推荐：Redis + ARQ，数据库保存真实状态和 lease；进程内 Thread 只用于本地开发。

4. **Deposit 失败策略**  
   推荐：0.3 使用整批事务回滚；部分应用留到后续版本。

5. **来源策略**  
   推荐：provider 可插拔；Wikipedia 只能作为 fallback，不能作为唯一研究来源。

6. **模型策略**  
   推荐：抽取模型和验证模型可配置；没有模型凭证时任务只能停在 Retrieve 后并保留成果。

7. **发布责任**  
   推荐：0.3 坚持人工审核后发布，不提供无人值守自动发布。

## 13. 最终定义

LogiSpace 0.3 的真实深度研究应定义为：

> 在已确认作品和媒体版本范围内，由固定 orchestrator 根据 WorkDossier 缺口生成有限 Plan，通过真实搜索和正文读取获得不可变来源快照，使用本地检索选出少量上下文，批量抽取可逐字定位的 Evidence 和 Claim，验证来源独立性、版本一致性与支持状态，再将通过审核的强类型 Proposal 事务化应用到 Draft，并以不可覆盖的版本发布。

如果任何新增事实无法沿以下链路回溯，则不属于可发布的 0.3 研究成果：

```text
Published Dossier field
← Applied Proposal
← Approved ProposalReview
← Verified Claim
← EvidenceSpan
← DocumentChunk
← SourceSnapshot
← SourceDocument
← SearchHit / supplied source provenance
```
