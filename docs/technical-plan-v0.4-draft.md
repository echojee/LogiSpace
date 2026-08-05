# LogiSpace 0.4 深度研究技术方案（草稿）

> 状态：Draft / 用于讨论，不代表已冻结的实现合同  
> 日期：2026-08-02

## 1. 目标与产品判断

0.4 不把“深度研究”定义为生成一篇更长的文章，而定义为：

> 围绕一个已确认的作品版本，把用户目标转译为可验证的研究问题；自主选择查询、来源和下一步行动；产出可追溯、可比较、可复用的作品档案，并明确展示已知、推断、争议和未知。

三个北极星指标：

1. **高效**：相同预算下获得更多“新增且可用”的证据，而不是更多网页或 token。
2. **准确**：关键结论可定位、可复核，版本不混用，事实、推断和解读不混写。
3. **有特色**：输出不是通用百科文章，而是推理作品特有的多时间线、线索—误导—揭示、犯罪方法、叙事结构和争议档案。

0.3 已经建立 `Source → Snapshot → Evidence → Claim → Proposal → Dossier` 证据链，这是应保留的核心资产。0.4 要补上的不是更多流水线阶段，而是一个明确的**研究策略层**。

## 2. 对标项目与可借鉴之处

| 项目 | 核心做法 | 借鉴 | 不直接照搬 |
|---|---|---|---|
| [OpenAI Deep Research](https://help.openai.com/en/articles/10500283-deep-research) | 先确认目标与计划；允许限制来源；运行时可调整；最终报告含引用、来源和活动历史 | 可编辑 Plan、来源范围、活动轨迹、可复核报告 | 闭源实现不可作为架构依赖 |
| [Open Deep Research](https://github.com/langchain-ai/open_deep_research) | 可配置搜索、MCP 和模型；研究、压缩、报告模型分工；现版本使用 agent，旧版包含 workflow 与 supervisor/researcher 两条路线 | provider 抽象、研究/压缩/写作分工、Deep Research Bench 接入 | 不采用无边界的通用研究上下文；成本规模不适合 MVP |
| [STORM / Co-STORM](https://github.com/stanford-oval/storm) | 多视角提问，先形成大纲再写作；Co-STORM 引入人与 agent 共建知识空间 | “视角”驱动未知发现；先研究后成文；概念级知识库 | 不按 Wikipedia 长文作为唯一结果形态 |
| [GPT Researcher](https://github.com/assafelovic/gpt-researcher) | 将主题拆成子问题，并行检索、抓取、汇总，再生成带引用报告 | 查询并发、模块化 retriever/scraper、报告流水线 | 不把网页摘要直接当作证据，不只做一次性报告 |
| [PaperQA2](https://github.com/Future-House/paper-qa) | 文档级检索、证据上下文化、精确引用；用 LitQA2 做端到端评测 | 文档优先、证据选择与答案生成分离、任务级 benchmark | 其科学论文来源假设不能直接迁移到文学与影视研究 |
| [DeerFlow](https://github.com/bytedance/deer-flow) | lead agent、隔离 sub-agent、skills、文件系统、长期记忆、上下文压缩 | 隔离上下文、结构化交接、渐进加载能力、长任务记忆 | 不让 sub-agent 直接修改正式档案或无限派生任务 |

结论：0.4 应采用 **STORM 的多视角问题发现 + Open Deep Research 的可配置研究循环 + PaperQA2 的证据纪律 + DeerFlow 的隔离执行**，保留 LogiSpace 自己的 WorkDossier、剧透控制与版本发布机制。

## 3. 总体架构：外层状态机，内层 ReAct

```text
Research Brief（研究目标与边界）
  ↓
Deterministic Orchestrator（状态、预算、checkpoint、权限）
  ↓
Planner → Research Units（问题、视角、证据需求、来源策略）
  ↓
Research Supervisor
  ├─ Researcher A（人物/关系）─┐
  ├─ Researcher B（三重时间线）├→ Evidence Inbox
  └─ Researcher C（诡计/解答）─┘
  ↓
Evidence Pipeline（抓取、快照、切块、去重、重排、验证）
  ↓
Claim & Conflict Engine（支持、反证、独立性、版本一致性）
  ↓
Dossier Composer（领域化视图 + 可读叙事）
  ↓
Evaluator → Human Review → Deposit / Publish
  ↓
Research Memory（来源、查询、证据、结论、失败经验）
```

### 3.1 为什么不是纯 ReAct

纯 ReAct 适合局部探索，但不适合承担完整任务生命周期。它容易重复查询、遗漏覆盖面、超预算，并且难以复现“为什么停止”。因此：

- **允许 ReAct 决定**：下一条查询、是否打开页面、是否追踪新实体、是否寻找反证、是否请求第二来源。
- **不允许 ReAct 决定**：扩大作品/版本范围、突破预算、跳过引用校验、直接写入 Dossier、自动发布。
- 每个 agent loop 必须有 `max_steps`、预算配额、可用工具白名单、明确完成条件和结构化输出。
- 每次 action 都写入 `ResearchTrace`，包括理由、工具、输入摘要、结果、成本和下一步判断。

推荐每个 Research Unit 最多 6–10 个 ReAct 步骤；超过后返回当前证据与未解决问题，由 Supervisor 决定是否增配预算。

## 4. 搜什么：从固定章节变成研究任务卡

新增顶层对象 `ResearchBrief`：

```json
{
  "work_id": "...",
  "media_version": "original_novel",
  "user_goal": "理解叙述性诡计如何成立",
  "audience": "读完原著的推理爱好者",
  "output_mode": "case_file",
  "spoiler_level": "full",
  "source_policy": "balanced",
  "must_answer": [],
  "must_not_cover": [],
  "budget_profile": "standard"
}
```

Planner 不应直接生成搜索词，而应先生成 `ResearchUnit`：

```json
{
  "unit_id": "ru_narrative_gap_01",
  "section": "timeline_narrative",
  "perspective": "narratology",
  "question": "叙述在哪些位置压缩、转述或省略了关键行动？",
  "why_it_matters": "用于解释诡计如何对读者成立",
  "expected_claim_types": ["fact", "interpretation"],
  "evidence_requirements": {
    "preferred_source_families": ["primary_text", "scholarly_analysis"],
    "minimum_independent_sources": 2,
    "requires_primary_source": true,
    "requires_counterevidence_search": true
  },
  "done_when": ["关键文本有精确定位", "解释得到独立分析支持或明确标为推断"]
}
```

### 4.1 Plan 的三层结构

1. **Coverage Plan**：已有档案缺什么、冲突在哪里、用户真正想知道什么。
2. **Research Plan**：拆成有限 Research Units，并定义证据需求与完成条件。
3. **Execution Plan**：为每个 Unit 生成首轮 query portfolio、来源路由和预算；运行时允许 agent 调整。

### 4.2 多视角不是多个角色扮演提示词

推理作品建议内置以下“研究镜头”，Planner 按问题选择 2–4 个，而不是全开：

- 文本事实：人物、地点、物件、行动、证言。
- 时间与因果：真实 / 调查 / 叙事三重时间线。
- 线索逻辑：线索何时出现、指向什么、如何被重新解释。
- 叙事学：视角、信息遮蔽、不可靠叙述、公平性。
- 版本学：原著、译本、影视改编的差异。
- 接受史：评论、争议、奖项、影响与后续作品。

Plan 质量门槛：每个 Unit 必须回答“为什么查、需要什么证据、什么时候算完成”，否则不进入执行。

## 5. 怎么搜：查询组合与自适应研究循环

### 5.1 Query Portfolio

不要为每个章节固定生成三条近义 query。每个 Research Unit 首轮生成互补查询：

- `identity`：精确作品名 + 作者/年份/外部 ID，防止同名和版本混淆。
- `primary`：作品名 + 章节/角色/原文短语，寻找一手文本或可定位材料。
- `analysis`：作品名 + 研究概念，如 narrative omission / fair play。
- `authority`：限定出版社、作者官网、学术数据库、档案馆。
- `counter`：寻找反例、异议、不同版本或争议解释。
- `multilingual`：中文标题、原名、日文/英文别名分别查询，最后跨语言去重。

### 5.2 ReAct 研究回合

```text
Observe：当前 Unit 的已知、证据缺口、来源分布、剩余预算
Think：选择信息增益最高的下一步
Act：search / fetch / find_in_source / follow_citation / compare_versions
Validate：页面可读性、身份匹配、来源类别、是否新增证据
Update：写入 evidence inbox 与 gap state
Stop / Continue：按完成条件和边际收益判断
```

停止条件以“边际信息增益”而非页面数为核心：

- 必答问题已满足证据门槛；
- 连续两次 action 没有产生新 Evidence 或新冲突；
- 新来源与已有来源高度重复；
- 剩余问题只能依赖不可访问材料；
- 预算耗尽或需要人工解决版本歧义。

## 6. 去哪搜：搜索平台与来源路由

### 6.1 Provider 选择建议

| Provider | 优势 | 局限 | 0.4 建议 |
|---|---|---|---|
| [Brave Search API](https://brave.com/search/api/) | 独立网页索引，覆盖通用 Web，适合做稳定基础召回 | 仍需自行抓正文和做语义重排 | **主召回 provider** |
| [Tavily](https://docs.tavily.com/documentation/api-reference/endpoint/search) | 面向 agent，支持 raw content、域名过滤和不同 search depth | 高级搜索成本更高，返回内容仍需本地核验 | **快速原型 / fallback / 新闻型查询** |
| [Exa](https://exa.ai/docs/reference/search) | 语义检索、highlights、正文内容接口，适合“找相似分析” | 不能替代通用关键词搜索；成本需实测 | **分析类与长尾来源补充召回** |
| DuckDuckGo HTML | 无正式稳定合同、易受页面变化影响 | 可用性与可观测性弱 | 仅开发 fallback，不作生产主源 |
| Wikipedia API | 身份确认和线索入口方便 | 聚合来源，不能承担关键结论的唯一证据 | identity / seed source，不作为强证据终点 |
| Google Custom Search JSON API | 历史生态成熟 | 官方已要求现有客户在 2027-01-01 前迁移 | 不作为 0.4 新依赖 |

建议先做小规模 provider bake-off，而不是凭印象定型：用 30–50 个固定 Research Units，比较 `Recall@10`、可读正文率、优质来源率、重复率、中文/外文覆盖、P95 延迟和“每条有效 Evidence 成本”。

默认组合建议：**Brave 负责广召回，Exa 负责分析类补充，Tavily 负责快速 fallback；正文统一由 LogiSpace Reader 获取和冻结**。这样搜索结果与证据边界仍掌握在自己手中。

### 6.2 来源路由，而不是所有问题搜同一个 Web

建立 `SourceRegistry` 与领域路由：

- 身份/书目信息：出版社、ISBN/图书馆目录、作者官网、IMDb/TMDB 等结构化源。
- 原始文本：用户合法提供文本、公共领域文本、授权电子书、剧本或字幕；遵守版权与访问策略。
- 学术分析：Crossref、OpenAlex、Semantic Scholar、JSTOR 等元数据或可访问全文。
- 访谈/创作背景：作者、出版社、博物馆、权威媒体原始访谈。
- 接受史/争议：同期评论、专业书评、学术论文；社区内容只作为观点样本。
- 改编：制片方、官方演职员资料、可靠影视数据库和访谈。

每个来源记录 `family / authority / independence_group / media_version / language / access_mode / terms / freshness`，从而判断“两个 URL”是否其实是同一稿件转载。

## 7. 怎么选择：两阶段排序与证据效用

搜索命中排序与证据排序必须分开。

### 7.1 页面选择分数

```text
PageUtility =
  0.25 × identity_match
+ 0.20 × question_relevance
+ 0.15 × source_authority
+ 0.10 × source_independence
+ 0.10 × version_match
+ 0.10 × retrievability
+ 0.10 × novelty
- penalties(spam, aggregation, paywall, duplication, version_risk)
```

分数只负责排序，不直接证明事实。权重应由 golden set 调参，并保存每个分项，便于解释为何读取或跳过页面。

### 7.2 Evidence 选择

Evidence 需要同时满足：

- exact quote 可在不可变 Snapshot 中定位；
- 与具体 Claim 的 entailment 足够强；
- 作品身份和媒体版本一致；
- locator 稳定；
- 来源类别适合该 Claim；
- 关键结论有独立来源或一手来源；
- 与其他 Evidence 不只是转载或同源复述。

引入 `EvidenceCard`：原文、上下文、来源类型、版本、支持/反对哪个 Claim、可信理由、限制、独立性组。agent 可以提名 Evidence，但确定性 validator 决定它能否进入证据池。

## 8. 怎么处理：Claim、冲突与“未知”都是一等对象

0.4 将内容分为四种状态，并在 UI 中显式区分：

- **Fact**：来源直接陈述且证据充分。
- **Inference**：由多个事实推导，必须展示推导链。
- **Interpretation**：分析视角，有作者或学术观点归属。
- **Unknown / Conflict**：材料不足或来源冲突，不强行合并。

新增 `ClaimGraph`：

```text
Evidence ─supports/opposes→ Claim
Claim ─depends_on→ Claim
Claim ─contradicts→ Claim
Claim ─about→ Entity / Event / Clue / Version
```

这不是要求立刻引入图数据库；0.4 可以先用关系表表达。价值在于报告能展示“结论如何成立”，评测也能从单条引用升级到推理链。

## 9. 怎么呈现：从报告升级为可读档案

最终产物建议叫 **Case File / 作品研究档案**，包含三层：

### 9.1 一分钟读懂

- 研究结论摘要；
- 本轮新增了什么；
- 可靠度与主要限制；
- 剧透等级与版本范围。

### 9.2 领域化核心视图

- 三重时间线并排：真实发生 / 调查发现 / 读者获知；
- 线索链：首次出现 → 初始解释 → 重解释 → 最终作用；
- 诡计剖面：前提、执行、遮蔽、误导对象、揭示点、公平性；
- 人物关系与动机变化；
- 版本差异；
- 争议地图：观点 A / B、各自证据、未决点。

### 9.3 证据与研究附录

- 每段结论的内联引用；
- 点击引用展开 EvidenceCard 与上下文；
- 来源清单按类型和可信度分组；
- 未解决问题、被排除来源及原因；
- Research Trace 的人类可读摘要，而非暴露模型思维过程。

Composer 使用“先结构、后叙事”：先从 ClaimGraph 生成 `DossierViewModel`，再让模型在不新增事实的前提下润色段落。所有生成句必须回指 claim IDs；无 Claim 的句子只能是标题、过渡或明确标注的编辑性总结。

## 10. 怎么评测：分层评测，而不是只看最终文风

### 10.1 Retrieval

- `SourceRecall@K`：golden 来源是否进入候选。
- `EvidenceRecall@K`：golden 证据片段是否被召回。
- 可读正文率、去重率、版本误配率、优质来源率。
- 每条有效 Evidence 的查询数、页面数、成本和延迟。

### 10.2 Evidence / Claim

- Quote validity：引用是否逐字存在。
- Citation entailment：引用是否支持结论。
- Citation completeness：可验证事实是否都有引用。
- Source independence：关键 Claim 是否真的由独立来源支持。
- Claim precision / recall：对 golden claims 的准确率与覆盖率。
- Conflict detection、事实/推断/解读分类准确率、版本污染率。

### 10.3 Dossier

- 必答问题覆盖率；
- 三重时间线一致性；
- 线索—揭示闭环率；
- 实体和关系完整性；
- 剧透策略违规；
- 人类评分：可读性、结构清晰度、洞察力、冗余度、可复核性。

### 10.4 Agent / System

- 成功率、部分完成价值、恢复率；
- 无效 action 比例、重复查询率、循环率；
- token、搜索、抓取和时间预算遵守率；
- 同题多次运行的结论稳定性；
- prompt injection 与恶意网页内容抵抗测试。

### 10.5 评测集

保留三部黄金作品，但不只准备“黄金报告”，而应准备：

```text
ResearchBrief
→ golden ResearchUnits
→ relevant / irrelevant / adversarial sources
→ golden Evidence spans
→ supported / contradicted / version-confused Claims
→ expected Dossier views
```

另外抽取 10–20 个通用研究问题接入 [Deep Research Bench](https://github.com/langchain-ai/open_deep_research) 风格的报告评测，检验通用研究能力；产品主指标仍以 LogiSpace 领域集为准。LLM-as-a-judge 只做辅助，引用正确性与 Schema/版本约束尽量使用确定性检查或人工抽检。

## 11. 怎么沉淀：四类记忆，禁止把整份报告塞进向量库

1. **Source Memory**：URL canonicalization、快照 hash、抓取结果、来源画像、转载关系、访问失败经验。
2. **Research Memory**：Research Unit、查询、命中、action trace、停止原因和成本。
3. **Knowledge Memory**：审核后的 ClaimGraph、实体、时间线、线索链和冲突；这是正式知识。
4. **Presentation Memory**：用户偏好的语言、详略、视图和剧透设置；不与事实知识混存。

复用顺序：先查已发布知识 → 再查历史 Evidence/Snapshot → 再运行新搜索。历史未审核的 agent 总结只能作为查询线索，不能作为事实来源。

建议为每次发布生成 `ResearchDelta`：新增、强化、削弱、冲突、废弃的 Claim，以及它们对应的来源变化。这样下一次研究是增量维护，不是从零生成新报告。

## 12. 多 Agent 的职责、权限与约束

### 12.1 推荐角色

- **Planner**：只生成和修订 Research Units，不搜索、不写结论。
- **Supervisor**：分配 Unit、控制并发、合并 gap 状态，不直接发布。
- **Researcher**：在一个 Unit 和限定工具集内 ReAct，提交候选证据与未解决问题。
- **Source Specialist（可选）**：处理 PDF、长文本、跨语言或版本比对。
- **Verifier**：寻找反证、检查引用支持和来源独立性；与 Researcher 上下文隔离。
- **Composer**：只读取 verified claims，生成档案视图。
- **Critic/Evaluator**：执行质量门槛，不能自行改写 Claim 来“修复”失败。

### 12.2 工程护栏

- 能力令牌：每个 agent 只能调用允许的工具和来源域。
- 预算租约：Supervisor 给子任务预留预算，未用额度回收。
- 结构化交接：agent 只返回 schema 合法的 `FindingBundle`。
- 数据血缘：任何 Claim 必须指向 Evidence，任何 Evidence 必须指向 Snapshot。
- 隔离上下文：Verifier 不读取 Researcher 的自由文本推理，只看 Claim 和 Evidence。
- 幂等与 checkpoint：每个 Unit 可单独重试，不重复扣除已缓存抓取成本。
- 循环探测：query/action 指纹去重；低信息增益连续出现即停止。
- 写入隔离：agent 只能写工作区 inbox；Deposit 是唯一可修改 Draft 的组件。
- 人工门：身份歧义、版本冲突、关键争议和发布继续要求人工确认。

## 13. 建议的数据契约

0.4 建议新增或升级：

```text
ResearchBrief
ResearchUnit
EvidenceRequirement
QueryCandidate / QueryRun
SourceRegistryEntry / SourceIndependenceGroup
AgentAction / ResearchTrace
FindingBundle
EvidenceCard
ClaimRelation / ClaimGraph
ResearchDelta
DossierViewModel
EvaluationRun / MetricResult
```

现有 `PlanItemV3` 可迁移为 `ResearchUnit`；`SearchHitV3.score` 应拆成可解释的 score components；`SourceV3.credibility` 不再是单一全局分数，而是 authority、relevance、version match、independence 等维度；`ResearchReportV3` 成为多个 presentation projection 之一，而非唯一成果。

## 14. 推荐的实施顺序

### Phase 0：先建评测基线

- 为三部黄金作品各准备 8–12 个 Research Units。
- 建立固定搜索结果和正文 fixture。
- 实现来源召回、Evidence、Claim、版本污染和成本指标。
- 记录当前 0.3 基线，避免 0.4“更复杂但更差”。

### Phase 1：Plan 与来源策略

- 引入 ResearchBrief、ResearchUnit、EvidenceRequirement。
- 实现 Query Portfolio 和 SourceRegistry。
- 对 Brave / Tavily / Exa 做 provider bake-off，再确定默认组合。
- 前端支持用户编辑研究重点、来源范围和完成标准。

### Phase 2：受控 ReAct Researcher

- 固定外层状态机，先只启用一个 Researcher。
- 提供 search、fetch、find、follow citation、compare version 五类工具。
- 加入 step/budget/loop guard 与 FindingBundle。
- 与确定性 0.3 路线做 A/B：有效证据率、成本、覆盖和稳定性。

### Phase 3：Verifier 与有限并行

- 对高优先级 Unit 并行 2–3 个隔离 Researcher。
- 增加独立 Verifier，专门找反证和版本污染。
- Supervisor 只按 gap 和边际收益追加任务，禁止无限分叉。

### Phase 4：特色档案

- 构建 ClaimGraph 与 DossierViewModel。
- 先上线三重时间线和线索链，再上线诡计剖面、版本差异和争议地图。
- 报告、卡片、时间线、关系图全部来自同一 verified knowledge layer。

### Phase 5：增量沉淀

- Source / Research / Knowledge / Presentation 四类记忆分层。
- ResearchDelta 与来源变化监测。
- 基于用户审核反馈校准来源、查询和呈现策略。

## 15. 0.4 首个里程碑的范围建议

首个里程碑不要一次实现多 Agent。建议定义为：

> 对《罗杰疑案》的 10 个固定 Research Units，系统能生成可编辑 Plan；使用可切换 provider 完成搜索；单个受控 ReAct Researcher 在预算内提交 EvidenceCard；Verifier 检查引用、版本和反证；最终生成包含三重时间线、线索链与来源附录的 Case File，并通过可重复的领域评测。

验收建议：

- golden source `Recall@10 ≥ 0.8`；
- exact quote validity = 100%；
- 关键 Claim 引用完整率 ≥ 95%；
- 媒体版本污染率 = 0；
- 至少 80% 的 Research Units 达到其 `done_when`；
- 无效/重复 agent action < 15%；
- 同预算下“有效 Evidence / 成本”不低于 0.3；
- 人工审核者可在 15 分钟内复核核心结论和来源。

## 16. 需要产品与技术共同确认的决策

1. 第一优先呈现是“三重时间线 + 线索链”，还是“诡计剖面 + 争议地图”？
2. 用户合法提供的原文能否作为主要一手证据，并以何种保留策略存储？
3. 学术数据库元数据与可能受限全文的访问边界是什么？
4. 0.4 是否允许“仅研究、不入库”的临时 Case File？
5. 关键 Claim 的双来源要求，哪些情况可由单一一手来源替代？
6. provider bake-off 的月度预算和目标语言覆盖范围。

在这些决策确认前，最安全的推进方式是先完成 Phase 0：评测基线和 Research Unit 数据集。它能让后续对 ReAct、provider 和多 Agent 的每次调整都有可比较证据。
