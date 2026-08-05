# LogiSpace 0.4 深度研究架构升级技术方案

> 状态：Proposed  
> 日期：2026-08-02  
> 范围：深度研究规划、检索、证据处理、档案呈现、知识沉淀、评测与 Agent 运行约束

## 1. 版本目标

0.4 在保留 0.3 可信证据与发布闭环的基础上，引入受控的 Agentic Research Layer。

0.4 不以“更多 Agent”或“更长报告”为成功标准，而以三个结果为目标：

1. **高效**：缩小搜索空间，以更少查询、页面和 token 获得更多有效 Evidence。
2. **准确**：任何可发布知识均能沿 `Claim → Evidence → Snapshot → Source` 回溯，且不发生媒体版本污染。
3. **有特色**：每部作品同时具备四个知识库必修板块和自身独特的研究主线，最终呈现为可读、可探索的深度档案。

核心定义：

> Supervisor 决定研究什么，Search Agent 决定下一步怎么搜，Curator 将材料整理成候选知识，Verifier 决定证据支持什么，Writer 决定如何表达，确定性 Mapper 决定如何形成知识库变更建议，人工审核决定是否发布。

## 2. 相对 0.3 的架构决策

0.4 不是替换 0.3，而是在其外层增加自主研究能力。

### 2.1 继续保留

- Work / media version 身份确认；
- 固定状态机、BudgetLedger、checkpoint 和任务恢复；
- SourceDocument、SourceSnapshot、DocumentChunk；
- EvidenceSpan、Claim、ClaimEvidence；
- exact quote 与 locator 校验；
- KnowledgeProposal、人工 Review、Deposit、Publish；
- WorkDossier 版本化和 diff；
- 无证据禁止发布。

### 2.2 升级或替换

| 0.3 | 0.4 |
|---|---|
| 固定章节 Plan | 必修板块 + 作品特色的双轨 Plan |
| 预生成固定查询 | Source Pack 引导的受控 ReAct 搜索 |
| 全网搜索优先 | 本地知识 → 限域搜索 → 权威核验 → 开放 Web |
| SearchHit 单一 score | Search Utility 与 Evidence Authority 分离 |
| chunk 直接批量抽取 Claim | Evidence 聚类 → 原子 Claim → 领域对象 → 跨板块连接 |
| 单次 Claim 验证 | 确定性校验 + 语义验证 + 来源独立性 + 全局一致性 |
| 按 section 拼接报告 | 围绕作品研究主线组织 Case File |
| report / package 分别生成 | 从统一 Verified Knowledge Layer 双投影 |

### 2.3 双执行模式

0.4 保留两条模式：

- `fast`：沿用 0.3 确定性流程，适合小范围补全、指定来源和低预算任务。
- `deep`：启用 Supervisor 与受控 Agent，适合新作品、完整档案、复杂诡计和冲突研究。

任何 Agentic 改动必须与 `fast` 基线比较，不能只以主观报告质量验收。

## 3. 总体架构

```text
User Goal + WorkDossier + Version Scope
                    ↓
             Supervisor Agent
          生成双轨 Research Plan
                    ↓
              Plan Approval
                    ↓
             Web Search Agent
       + Mystery Search Routing Skill
       + Source Packs / Source Registry
                    ↓
        Source → Snapshot → Chunk
                    ↓
       Evidence Candidate Inbox
                    ↓
       Knowledge Curator Agent
                    ↓
     Claim / Domain Object Candidates
                    ↓
        Verification Agent（知识验证）
                    ↓
     Verified Knowledge Layer + Gaps
              ↙             ↘
     需要补查？             研究完成
        ↓                    ↓
    Supervisor        ┌──────┴──────┐
    修订 Plan         ↓             ↓
                 Dossier Writer   Knowledge Mapper
                       ↓             ↓
                 Case File      KnowledgeProposals
                       ↓             ↓
               表达/引用审计       人工审核
                       └──────┬──────┘
                              ↓
                       Deposit / Publish
```

架构原则：

- 外层是确定性状态机，内层只有 Search 等局部阶段允许 ReAct；
- Agent 只能提交候选，不可直接修改正式知识库；
- Supervisor 管理研究过程，但不是事实裁判；
- Writer 与知识库不是上下游关系，而是同一验证知识层的并列投影；
- 可用代码验证的规则不交给模型；
- 冲突、未知和不适用是一等结果，不为了填满结构而编造。

## 4. Research Plan：必修与特色双轨

### 4.1 ResearchBrief

```json
{
  "work_id": "...",
  "media_version": "original_novel",
  "user_goal": "全面理解作品的诡计结构",
  "audience": "已读完原著的推理爱好者",
  "spoiler_level": "full",
  "output_mode": "case_file_and_knowledge",
  "budget_profile": "standard",
  "allowed_source_scope": "bilingual_mystery_default"
}
```

### 4.2 必修轨道

每部作品必须检查四个知识库板块：

1. 人物关系图；
2. 多重时间线；
3. 诡计集；
4. 杀人手法集。

“必须研究”表示必须完成覆盖判断，不表示必须生成条目。每个板块最终状态为：

```text
sufficient
needs_update
missing
conflicted
not_applicable
```

`not_applicable` 必须有理由和证据，不能用来逃避研究；`missing` 可以是合法结果。

### 4.3 特色轨道

Supervisor 根据用户目标、现有档案、初步 Coverage、作品结构和第一轮发现生成作品特有研究重点，例如：

- 不可靠叙述与信息省略；
- 群体犯罪与协同证言；
- 封闭空间的行动窗口；
- 数学化犯罪设计；
- 公平推理争议；
- 原著与改编的关键差异；
- 特定社会、历史或创作背景。

特色轨道可以跨越四个板块，不受固定 section 限制。

### 4.4 ResearchUnit

```json
{
  "unit_id": "ru_narrative_01",
  "track": "signature",
  "domain": "timeline_narrative",
  "question": "叙述在哪些位置压缩或省略了关键行动？",
  "why_it_matters": "解释叙述性诡计如何对读者成立",
  "required_outputs": ["claim", "timeline_alignment", "trick_component"],
  "evidence_requirements": {
    "requires_primary_source": true,
    "minimum_independent_sources": 1,
    "requires_counterevidence_search": true
  },
  "budget": {
    "max_steps": 8,
    "max_queries": 5,
    "max_pages": 8
  },
  "done_when": [
    "关键行动有原文定位",
    "真实事件与叙述位置完成对齐",
    "无法确认的作者意图明确标为解读"
  ]
}
```

每个 Unit 必须说明“为什么研究、需要什么证据、什么时候完成”。

### 4.5 预算分配

四个必修板块有最低保留预算，特色研究使用弹性预算。Supervisor 可以调整但不能挪用全部必修预算。

```json
{
  "mandatory_reserve": {
    "relationships": 2,
    "multiple_timelines": 3,
    "tricks": 3,
    "murder_methods": 2
  },
  "signature_flexible_queries": 8,
  "verification_reserve_ratio": 0.2
}
```

## 5. Supervisor Agent

### 5.1 输入

- ResearchBrief；
- 当前 WorkDossier 和 Coverage；
- 已有 verified Claims / entities / events；
- 已有来源、查询和失败历史摘要；
- 预算和版本范围；
- 每轮 FindingBundle、VerificationResult 和 GapState。

### 5.2 能力

- 生成双轨 Plan；
- 判断作品独特研究重点；
- 将目标拆成有限 Research Units；
- 排序优先级和分配预算；
- 合并重复问题；
- 根据新证据修订 Plan；
- 针对冲突派发补查或反证任务；
- 判断是否进入下一轮或结束研究。

### 5.3 禁止能力

- 不直接产生可发布 Claim；
- 不修改 Evidence；
- 不绕过 Verifier；
- 不直接写入 WorkDossier；
- 不直接批准 Proposal；
- 不扩大作品或媒体版本范围；
- 不因档案结构不完整而补写事实。

### 5.4 完成条件

Supervisor 只能建议 `complete_research`，确定性 Orchestrator 还需检查：

```text
四个必修板块均完成 coverage decision
AND 所有高优先级 Research Units 已完成或标记不可获得
AND 关键 Claims 满足 Evidence Requirement
AND 高风险冲突已解决或显式保留
AND verification reserve 未被挪用
AND 预算和版本约束通过
```

## 6. Web Search Agent：受控 ReAct

### 6.1 ReAct 循环

```text
Observe：Research Unit、已有证据、Source Pack、查询历史、剩余预算
Reason：选择预期信息增益最高的下一步
Act：search / fetch / find / follow citation / compare version
Evaluate：相关性、身份、版本、重复性、正文可读性、新颖性
Update：提交候选 Evidence、冲突、未知和后续问题
Stop：达到完成条件或边际收益不足
```

只保存 action 摘要、参数、结果、成本和决策理由，不暴露或依赖模型隐式思维过程。

### 6.2 工具白名单

```text
search_web
search_domains
fetch_page
read_pdf
read_transcript
find_in_source
follow_citation
compare_versions
submit_findings
```

初期不提供任意代码执行、任意浏览器操作、自由生成子 Agent 或知识库写入工具。

### 6.3 输出 FindingBundle

```json
{
  "research_unit_id": "ru_...",
  "summary": "...",
  "source_candidates": [],
  "snapshot_ids": [],
  "evidence_candidates": [],
  "counterevidence_candidates": [],
  "unresolved_questions": [],
  "suggested_followups": [],
  "queries_executed": [],
  "urls_rejected": [],
  "stop_reason": "evidence_requirement_met",
  "usage": {}
}
```

Search Agent 只能提名 Evidence，不能宣布 Claim 成立。

### 6.4 停止条件

- `done_when` 和 Evidence Requirement 满足；
- 连续两次 action 没有新增 Evidence、冲突或有效线索；
- 新来源与已有来源高度重复；
- 剩余材料不可访问；
- 需要人工判断版本；
- Unit 预算耗尽。

## 7. Mystery Search Routing Skill

Skill 不参与作品研究规划，只辅助 Search Agent 高效检索。

### 7.1 职责

1. 根据问题类型选择中英文 Source Pack；
2. 提供标题、别名、角色名和悬疑术语的查询模板；
3. 定义平台读取和 locator 方法；
4. 定义平台切换与扩大搜索范围的条件；
5. 区分平台的 Search Utility 和 Evidence Authority；
6. 控制每层查询、页面和视频转写预算。

### 7.2 不负责

- 不决定作品研究重点；
- 不生成 Research Units；
- 不判断 Claim 是否成立；
- 不设计档案结构；
- 不修改知识库 Schema；
- 不承担安全边界。

### 7.3 Source Pack

首批建议：

```text
identity_and_edition
primary_text_and_script
relationships
multiple_timelines
trick_and_misdirection
murder_method
creation_background
adaptation
reception_and_controversy
academic_analysis
```

每个 Pack 同时包含中英文来源，而不是分成两条市场流程。

示例：

```yaml
id: reception_and_controversy
high_priority:
  - book.douban.com
  - zhihu.com
  - selected_mystery_forums
  - goodreads.com
  - reddit.com
  - crimereads.com
secondary:
  - bilibili.com
  - youtube.com
  - mysteryscenemag.com
  - strandmag.com
  - xiaohongshu.com
budget:
  max_queries: 4
  max_hits_per_query: 5
  max_pages: 6
switch_policy:
  - if: no_relevant_hit_after_2_queries
    action: expand_to_secondary
  - if: claim_requires_primary_evidence
    action: route_to_primary_text_and_script
  - if: novelty_below_threshold_twice
    action: stop
```

### 7.4 中文社区平台定位

- 豆瓣：译本、版本、长书评、接受史和争议；
- 知乎：解释型回答、诡计分析、公平性和延伸来源；
- 专业推理论坛：冷门资料、诡计分类、历史讨论和异议；
- B站：长视频解析、时间线和改编比较，必须有字幕/转写和时间戳；
- 小红书：近期传播、新版信息、读者关注和关键词发现，通常不作为关键事实证据。

### 7.5 英文平台定位

- 作者官网、出版社、British Library：身份、背景、官方资料；
- Project Gutenberg、Internet Archive、HathiTrust、Google Books：合法可访问文本或历史材料，需检查版本与权利；
- CrimeReads、The Strand、Mystery Scene：专业评论、访谈和类型研究；
- Goodreads：版本、读者接受和争议发现；
- Reddit：读者分析、反驳、冷门问题和遗漏线索；
- TV Tropes / Fandom：术语、类型和改编线索，只用于查询扩展；
- OpenAlex、Crossref、Semantic Scholar、JSTOR、Project MUSE、机构库：学术发现和可访问全文。

### 7.6 有限搜索漏斗

```text
Level 0：本地 WorkDossier、历史 Evidence/Snapshot、用户文件
Level 1：当前问题的核心 Source Pack
Level 2：一手或权威来源核验
Level 3：相邻平台与视频/论坛扩展
Level 4：开放 Web fallback
```

建议外部搜索预算分配：

```text
核心 Source Pack：60%
权威核验：25%
相邻扩展：10%
开放 Web：5%
```

### 7.7 双维度来源评价

```json
{
  "research_value": 0.90,
  "evidence_authority": 0.42,
  "source_role": "controversy_discovery"
}
```

- `research_value`：能否快速发现线索、观点和原始来源；
- `evidence_authority`：能否直接支持当前 Claim 类型。

高搜索优先级不等于高证据权威性。

## 8. Source Registry 与正文获取

### 8.1 SourceRegistryEntry

```text
platform/domain
source_family
market/language
preferred_for
prohibited_as_sole_support_for
access_mode
authority dimensions
version risk
independence group
locator strategy
copyright/retention policy
```

Registry 独立版本化，站点、API 和访问规则变化时不修改 Agent prompt。

### 8.2 搜索与抓取分离

- Search Provider 只负责候选 URL 和 metadata；
- Reader 统一获取并冻结正文；
- 任何 snippet 只能是 Research Lead，不能成为强 Evidence；
- HTML、PDF、论坛楼层、视频字幕和图片 OCR 使用不同 locator；
- 同一 URL / content hash 跨 Agent 和跨任务复用。

### 8.3 平台定位

```text
网页：段落、heading、CSS/文本锚点
PDF：页码、块、字符位置
论坛：主题、楼层、作者、时间
视频：video ID、起止时间戳、字幕文本
图片帖子：图片序号、OCR 文本、原图 hash
```

## 9. Knowledge Curator Agent

### 9.1 职责

- Evidence 去重与语义聚类；
- 将复合叙述拆成原子 ClaimCandidate；
- 区分 Fact、Inference、Interpretation、Conflict、Unknown；
- 生成四个必修板块的候选领域对象；
- 建立人物、事件、证言、线索、诡计和杀人手法之间的连接；
- 保留缺失字段、冲突和后续问题。

### 9.2 领域对象

#### 人物关系

```text
source_character_id
target_character_id
relation_type
valid_during
public_or_hidden
claim_ids
```

#### 多重时间线

```text
canonical_event_id
truth_event
investigation_reveal
narrative_presentation
alignment_type
participant_ids
claim_ids
```

#### 诡计

```text
trick_type
preconditions
execution
concealment
misdirected_party
apparent_explanation
true_explanation
reveal_point
clue_ids
claim_ids
```

#### 杀人手法

```text
method_type
preparation
execution_steps
tools
time_window
concealment
detection_breakthrough
claim_ids
```

### 9.3 约束

- 不为了结构完整而推断缺失值；
- 不将相似措辞直接当作同一事实；
- 不决定 Claim 是否可发布；
- 不删除冲突；
- 大批材料按 Research Unit / Evidence cluster 分批整理，避免单次上下文过大。

## 10. Verification Agent

### 10.1 确定性验证优先

代码检查：

- quote 存在于 Snapshot；
- hash、locator 和引用完整；
- Source/Snapshot/Evidence/Claim 外键有效；
- media version 一致；
- Schema 合法；
-实体引用存在；
-预算合法；
-关键 Claim 具有 Evidence。

### 10.2 模型语义验证

- Evidence 是否直接支持 Claim；
- Claim 是否扩大原意；
- Fact、Inference、Interpretation 分类是否正确；
- 来源是否互相独立；
- 是否混用原著、译本和改编；
- 是否存在反向 Evidence；
-时间、人物、诡计和杀人手法是否全局自洽。

### 10.3 支持状态

```text
supported
partially_supported
inferred
interpretive
conflicted
unsupported
```

验证结果必须包含有效/拒绝 Evidence、问题类型、理由和建议补查项。

### 10.4 高风险 Claim

以下内容默认高风险：

- 凶手、共谋关系；
- 精确时间和不在场证明；
- 杀人方法关键步骤；
- 作者创作意图；
- 争议性唯一解释；
- 原著与改编差异。

高风险 Claim 要求一手证据或两个真正独立来源；无法满足时保留为推断、争议或未知。

### 10.5 写后审计

档案完成后再次检查：

- 每个事实 block 是否绑定 verified claim IDs；
- Writer 是否加入新事实；
- 是否把部分支持写成确定事实；
- 是否遗漏限定词、冲突或版本说明；
- 图表与正文是否一致；
- 摘要是否比正文更绝对。

## 11. Verified Knowledge Layer

这是任务级、尚未发布的统一事实层：

```text
VerifiedClaims
VerifiedEntities
VerifiedRelations
VerifiedEvents
TimelineAlignments
VerifiedClues/Testimonies
VerifiedTricks
VerifiedMurderMethods
Conflicts
Unknowns
EvidenceLinks
```

新增 `ClaimGraph` 关系：

```text
Evidence ─supports/opposes→ Claim
Claim ─depends_on→ Claim
Claim ─contradicts→ Claim
Claim ─about→ Entity/Event/Clue/Version
```

0.4 可先用关系表实现，不要求图数据库。

## 12. 深度档案 Case File

### 12.1 三层阅读结构

#### 一分钟读懂

- 研究主线；
- 本轮关键发现；
- 可靠度和主要限制；
- 作品与版本范围；
- 剧透等级。

#### 核心档案

- 人物与关系；
- 真实 / 调查 / 叙事多重时间线；
- 线索首次出现、初始解释、重解释和最终作用；
- 诡计的前提、执行、遮蔽、误导和揭示；
- 杀人手法的准备、实施、掩盖和识破；
- 作品独特研究重点；
- 改编差异和争议地图（适用时）。

#### 证据与研究附录

- 可展开 EvidenceCard；
- 按来源角色分组的来源清单；
- 未解决问题；
- 被排除来源及理由；
- 人类可读 Research Trace 摘要。

### 12.2 Writer 权限

Writer 只读取 Verified Knowledge Layer、档案模板和剧透策略，不读取未筛选网页或被拒绝 Claims。每个内容块必须关联 claim IDs：

```json
{
  "block_id": "block_...",
  "type": "analysis",
  "text": "...",
  "claim_ids": ["claim_01"],
  "evidence_ids": ["ev_01"]
}
```

Writer 可以决定结构、顺序、详略和表达组件，不能新增事实或修改验证状态。

## 13. 知识库沉淀

知识库不从报告抽取，而从 Verified Knowledge Layer 映射：

```text
Verified Character → add_entity
Verified Relation → add_relation
Verified Timeline Event/Alignment → add_timeline_event
Verified Trick → add_trick
Verified Murder Method → add_murder_method
Verified Conflict → flag_conflict
```

能用代码映射的部分由确定性 Knowledge Mapper 完成。模型只辅助实体消歧、事件合并和类型分类，并输出建议，不直接写库。

完整链路：

```text
Verified Knowledge
→ KnowledgeProposal
→ Human Review
→ Transactional Deposit
→ DossierDiff
→ Versioned Publish
```

## 14. 状态机

```text
created
awaiting_identity_confirmation
inventorying
supervisor_planning
awaiting_plan_approval
searching
curating
verifying
reflecting
replanning
knowledge_frozen
writing
auditing
mapping
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

只有 Orchestrator 可以变更主状态。Agent 返回建议和产物，不直接跳转阶段。

每个 Research Unit 独立保存：

```text
unit status
attempt
lease / heartbeat
budget reservation
queries/actions
FindingBundle
verification result
stop reason
checkpoint hash
```

## 15. Agent 工程约束

- 工具白名单和能力令牌；
- Unit 级 step/query/page/token 上限；
- Supervisor 级并发上限，初期最多 3 个并行 Unit；
- URL/query/action 指纹去重；
- 共享 Source/Snapshot/Chunk 缓存；
- 写入隔离：Agent 只写任务 inbox；
- Verifier 与 Search/Curator 自由推理上下文隔离；
- structured output + Schema validation + retry；
- prompt、model、skill、registry 和 tool 版本全部进入 trace；
- prompt injection、SSRF、私网、重定向、MIME、响应大小和凭据由工具层控制；
- 视频、论坛和图片必须有稳定 locator 才能成为 Evidence；
- 取消任务保留审计元数据，未使用大正文按策略清理。

## 16. 数据契约

新增或升级：

```text
ResearchBrief
ResearchPlanRevision
ResearchTrack
ResearchUnit
EvidenceRequirement
SourcePack
SourceRegistryEntry
QueryCandidate / QueryRun
AgentAction / ResearchTrace
FindingBundle
EvidenceCandidate / EvidenceCard
ClaimCandidate / VerificationResult
RelationshipCandidate
TimelineEventCandidate / TimelineAlignment
TrickCandidate
MurderMethodCandidate
ClaimRelation
VerifiedKnowledgeSnapshot
DossierViewModel / DossierBlock
ResearchDelta
EvaluationRun / MetricResult
```

重要模型调整：

- `SearchHit.score` 拆成可解释分项；
- `Source.credibility` 拆为 authority、relevance、version match、independence、retrievability；
- Claim 正式成为一级模型，不伪装为 `DossierEntity(type=Claim)`；
- Proposal 增加 `add_trick`、`add_murder_method`、timeline alignment 等强类型 payload；
- `ResearchReport` 变为 Case File 的 presentation projection，不是唯一研究成果。

## 17. 评测体系

### 17.1 Supervisor / Plan

- 四个必修板块检查覆盖率 = 100%；
- 作品特色问题人工相关性；
- Research Unit 可执行率；
- Evidence Requirement 完整率；
- 预算分配合理性；
- 重复或无效 Unit 比例。

### 17.2 Search

- `SourceRecall@K`；
- `EvidenceRecall@K`；
- 首个有效 Evidence 的查询数和耗时；
- Source Pack 命中率；
- 开放 Web fallback 比例；
- 可读正文率；
- 重复 URL / 内容率；
- 中文平台有效信息占比；
- 每条有效 Evidence 的成本。

### 17.3 Evidence / Claim

- exact quote validity = 100%；
- citation entailment；
- citation completeness；
- source independence；
- Claim precision / recall；
- Fact/Inference/Interpretation 分类准确率；
- conflict detection；
- media-version contamination = 0。

### 17.4 四个知识板块

- 人物实体与关系准确率；
- 三条时间线内部与跨线一致性；
- 线索—诡计—揭示闭环率；
- 杀人方法步骤完整性和事件一致性；
- Proposal Schema 和应用成功率。

### 17.5 Case File

- 必答问题覆盖；
- verified Claim 表达忠实度；
- 四个板块呈现覆盖；
- 特色研究主线清晰度；
- 引用可复核性；
- 人类评分：结构、可读性、洞察力、冗余、可信度；
- 人工复核核心结论耗时。

### 17.6 Agent / System

- 无效 action 和循环率；
- 重复查询率；
- budget violation = 0；
- checkpoint 恢复率；
- 部分完成价值；
- 同题多次运行稳定性；
- prompt injection 与恶意来源抵抗；
- 相比 0.3 的有效 Evidence / 成本增益。

LLM-as-a-judge 只评估主观质量；引用、Schema、版本、预算和数据完整性使用确定性指标或人工抽检。

## 18. 黄金评测集

首批三部作品继续使用：

- 《罗杰疑案》；
- 《东方快车谋杀案》；
- 《嫌疑人X的献身》。

每部准备：

```text
ResearchBrief
四个必修板块 Coverage
3–5 个特色 Research Units
中英文 Source Packs
relevant / irrelevant / adversarial sources
golden Evidence spans
supported / contradicted / version-confused Claims
人物关系、三重时间线、诡计和杀人手法 golden objects
expected Case File blocks
expected KnowledgeProposals
```

所有 provider、ReAct 和多轮规划实验都在同一评测集上与 0.3 比较。

## 19. 分阶段开发计划

### Phase 0：冻结 0.3 基线与评测

- 建立三部作品 golden Research Units 和数据；
- 实现 Search、Evidence、Claim、版本污染、四板块和成本指标；
- 录制当前 0.3 输出、成本、延迟和人工审核耗时；
- 补齐 Claim 一级模型和 Proposal 强类型决策。

**退出条件**：能用同一套指标比较 0.3 和任何 0.4 实验。

### Phase 1：双轨 Plan

- 实现 ResearchBrief、ResearchUnit、EvidenceRequirement；
- Supervisor 只生成 Plan，不执行搜索；
- 强制四个必修板块 Coverage；
- 支持特色轨道和 Plan 审批；
- 对 Supervisor Plan 做离线人工评测。

**退出条件**：三部黄金作品均生成合格必修 Plan 和明显不同的特色 Plan。

### Phase 2：Source Pack Skill 与搜索漏斗

- 建立 Mystery Search Routing Skill；
- 建立 Source Registry 和首批中英文 Source Packs；
- 搜索与 Reader 分离；
- 实现 Search Utility / Evidence Authority；
- 对搜索 provider 和 Source Pack 做 bake-off；
- 开放 Web 仅作为最后 fallback。

**退出条件**：相同预算下 `EvidenceRecall@K` 或有效 Evidence 成本显著优于 0.3。

### Phase 3：单个受控 Search Agent

- 实现 Unit 级 ReAct；
- 工具白名单、step/query/page 上限；
- action trace、loop detection、stop reason；
- 共享缓存和预算预留；
- 不引入多个并行 Search Agent。

**退出条件**：Agent 路线在质量上超过固定查询，且成本、循环和重复率达标。

### Phase 4：Curator 与 Verifier

- Evidence 聚类和原子 Claim；
- 四个板块候选对象；
- 确定性验证器；
- 批量语义 Verifier；
- 来源独立性、版本与跨对象一致性；
- 补查请求返回 Supervisor。

**退出条件**：引用、Claim 和版本指标达到发布门槛，Verifier 的错误检出收益可量化。

### Phase 5：Verified Knowledge 双投影

- Verified Knowledge Snapshot；
- ClaimGraph 关系；
- Case File ViewModel 和结构化 Writer；
- 写后引用审计；
- 确定性 Knowledge Mapper；
- Proposal Review、Deposit 和 Publish 对接。

**退出条件**：档案和知识库来自同一 Claim/Evidence 集，跨视图不一致为 0。

### Phase 6：有限并发与增量记忆

- Supervisor 最多并行 2–3 个 Research Units；
- Unit 隔离状态、lease 和 checkpoint；
- Source / Research / Knowledge / Presentation 四类记忆；
- ResearchDelta；
- 根据审核反馈校准 Source Pack 与验证策略。

并发只在单 Agent 路线稳定后引入。

## 20. 首个 0.4 里程碑

范围限定为《罗杰疑案》：

1. Supervisor 生成四个必修板块和不可靠叙述特色轨道；
2. 用户可审阅 Plan；
3. Search Agent 使用中英文 Source Pack 完成有限 ReAct；
4. 社区平台用于发现争议，关键情节回到原文或强来源核验；
5. Curator 生成原子 Claims、时间线对齐和诡计候选；
6. Verifier 检查引用、版本、独立性和反证；
7. 生成包含三重时间线、线索链、诡计剖面和杀人手法的 Case File；
8. 从相同 Verified Knowledge 生成强类型 KnowledgeProposals；
9. 人工审核后发布新 WorkDossier 版本。

建议验收线：

```text
四个必修板块检查覆盖率 = 100%
exact quote validity = 100%
关键 Claim 引用完整率 ≥ 95%
媒体版本污染率 = 0
高优先级 Research Unit 完成率 ≥ 80%
无效/重复 Agent action < 15%
开放 Web 查询占比 ≤ 10%
有效 Evidence / 成本不低于 0.3
档案与知识库跨视图不一致 = 0
人工可在 15 分钟内复核核心结论
```

## 21. 风险与反模式

### 21.1 不允许的实现

- 让 Supervisor 直接写最终事实；
- 让 Search Agent 把 snippet 当 Evidence；
- 先写报告再从报告抽知识库；
- 按人物、时间线、诡计、杀人手法分别建立互不共享事实的 Agent；
- 用一个全局 credibility 分数代替来源角色；
- 仅靠 prompt 保证版本、预算和安全；
- 为每条 Claim 单独调用 Verifier；
- 一开始就启用大规模并行和自由 sub-agent；
- 以报告长度或来源数量作为主要质量指标。

### 21.2 主要风险

- Supervisor 初始重点错误导致确认偏差；
- ReAct 增加成本和运行不稳定性；
- 社区来源高命中但低权威；
- Curator 上下文过大；
- Verifier 被误认为万能兜底；
- 多轮搜索产生重复页面和同源“伪独立”；
- Writer 在过渡句中加入新事实；
- 当前领域 Schema 无法承接复杂候选对象。

所有风险都必须通过数据契约、工具权限、预算、评测和人工门控制，而不是只修改 prompt。

## 22. 最终架构原则

0.4 的最终边界如下：

```text
Supervisor：保证“必须研究什么”和“这部作品独特在哪里”
Search Skill：保证“先在高命中率的中英文领域站点中查”
Search Agent：保证“根据证据动态决定下一步怎么搜”
Curator：保证“材料被整理成原子、结构化候选知识”
Verifier：保证“候选知识只表达证据真正支持的内容”
Writer：保证“验证知识被组织成有特色、可读的深度档案”
Mapper：保证“相同知识被安全转换为知识库变更”
0.3 内核：保证“证据、审核、版本和发布始终可追溯”
```

0.4 的技术路线不是从确定性工作流转向完全自治 Agent，而是：

> 在可信数据和发布内核上，引入有限、可观测、可评测、可停止的研究自主性。
