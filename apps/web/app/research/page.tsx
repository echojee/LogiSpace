"use client";

import {
  AlertTriangle, ArrowRight, BookOpen, Check, CheckCircle2, ChevronDown,
  Database, Gauge, LoaderCircle, Network, Play,
  RefreshCw, Search, Send, ShieldCheck, Sparkles, X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import "./v04.css";
import PlanMemoEditor from "./PlanMemoEditor";

import "./v04-new-work.css";
import "./v04-memo.css";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type WorkItem = { work: { work_id: string; canonical_title: string; creators: string[]; media_type: string }; dossier_version: string };
type ResolvedWork = { work_id: string; canonical_title: string; aliases: string[]; media_type: string; release_year?: number; creators: string[] };
type Resolution = { resolution_id: string; candidates: ResolvedWork[]; needs_confirmation: boolean; resolved_work?: ResolvedWork };
type Coverage = { domain: string; status: string; reason: string; existing_object_ids: string[] };
type ResearchUnit = {
  unit_id: string; track: "mandatory" | "signature"; domain: string; question: string;
  why_it_matters: string; required_outputs: string[]; priority: number; status: string;
  evidence_requirements: { requires_primary_source: boolean; minimum_independent_sources: number; requires_counterevidence_search: boolean };
  budget: { max_steps: number; max_queries: number; max_pages: number }; done_when: string[];
};
type Action = { sequence: number; action: string; decision_summary: string; result_summary: string };
type UnitCheckpoint = {
  research_unit_id: string; status: string; attempt: number; error?: string;
  finding_bundle?: { summary: string; stop_reason: string; source_candidates: unknown[]; evidence_candidates: unknown[]; counterevidence_candidates: unknown[]; actions: Action[]; usage: Record<string, number> };
  curated?: { claims: unknown[]; domain_objects: unknown[]; conflicts: string[]; unknowns: string[] };
  verification_results: { claim_id: string; status: string; reason: string; issues: { code: string; detail: string }[] }[];
};
type Block = { block_id: string; layer: "one_minute" | "core" | "appendix"; block_type: string; title: string; text: string; claim_ids: string[]; evidence_ids: string[] };
type Proposal = { proposal_id: string; operation: string; target_section: string; payload: Record<string, unknown>; claim_ids: string[]; evidence_ids: string[]; review_status: "pending" | "approved" | "rejected" };
type Job = {
  job_id: string; work: { work_id: string; canonical_title: string }; status: string;
  brief: { user_goal: string; media_version: string; audience: string };
  plan?: { revision: number; rationale: string; approved: boolean; coverage: Coverage[]; units: ResearchUnit[]; budget: { verification_reserve_ratio: number }; strategy: "build_and_verify" | "review_strengthen_and_correct" };
  units: Record<string, UnitCheckpoint>; errors: string[]; published_version?: string;
  reconnaissance?: { summary: string; edition_scope: string; candidate_features: string[]; contamination_risks: string[]; sources: { title: string; url: string }[] };
  plan_memo?: { title: string; objective: string; scope: string; reconnaissance_summary: string; signature_units: ResearchUnit[]; risks: string[]; revision: number; strategy: "build_and_verify" | "review_strengthen_and_correct" };
  planning_failure?: { stage: string; code: string; message: string; retryable: boolean; attempt: number };
  search_session?: { queries: string[]; snapshots: Record<string, string>; cache_hits: number; duplicate_queries_avoided: number };

  verified_knowledge?: { snapshot_id: string; claims: unknown[]; domain_objects: unknown[]; conflicts: string[]; unknowns: string[]; gaps: { research_unit_id: string; status: string; reasons: string[] }[]; evidence_ids: string[] };
  case_file?: { title: string; research_mainline: string; reliability_note: string; blocks: Block[] };
  proposals: Proposal[]; projection_audit?: { passed: boolean; issues: string[] };
};
type Metric = { name: string; value: number; target?: number; passed?: boolean; detail: string };

const domainNames: Record<string, string> = {
  relationships: "人物关系", multiple_timelines: "多重时间线", tricks: "诡计结构",
  murder_methods: "杀人手法", timeline_narrative: "叙事时间线", work_signature: "作品特色",
};
const statusNames: Record<string, string> = {
  created: "任务已创建", reconnaissance_running: "初步侦察中", supervisor_planning: "计划生成中", planning_failed: "计划生成失败",
  awaiting_plan_approval: "等待计划审批", searching: "检索中", curating: "知识整理",
  verifying: "证据验证", reflecting: "等待补查", knowledge_frozen: "知识已冻结",
  writing: "档案写作", auditing: "一致性审计", mapping: "知识映射",
  needs_review: "等待人工审核", depositing: "正在沉淀", published: "已发布",
  approved: "已批准", searched: "检索完成", curated: "整理完成", verified: "验证完成",
  failed: "失败", planned: "待审批",
};
const metricNames: Record<string, string> = {
  mandatory_coverage: "必修覆盖", exact_quote_validity: "原文引用有效率",
  media_version_contamination: "版本污染率", high_priority_unit_completion: "高优先级完成率",
  invalid_or_duplicate_action_rate: "无效/重复动作率", duplicate_query_rate: "重复查询率",
  open_web_query_ratio: "开放 Web 占比", cross_projection_consistency: "跨投影一致性",
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, { ...options, headers: { "Content-Type": "application/json", ...(options?.headers ?? {}) } });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail ?? `请求失败（${response.status}）`);
  return data as T;
}

export default function ResearchPage() {
  const [works, setWorks] = useState<WorkItem[]>([]);
  const [worksLoading, setWorksLoading] = useState(true);
  const [worksError, setWorksError] = useState("");
  const [workId, setWorkId] = useState("");
  const [workMode, setWorkMode] = useState<"new" | "existing">("new");
  const [newTitle, setNewTitle] = useState("");
  const [mediaType, setMediaType] = useState("novel");
  const [resolutionId, setResolutionId] = useState("");
  const [candidates, setCandidates] = useState<ResolvedWork[]>([]);
  const [goal, setGoal] = useState("全面研究作品的诡计结构、多重时间线与不可靠叙述");
  const [audience, setAudience] = useState("已读完原著的推理爱好者");
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [decisions, setDecisions] = useState<Record<string, "approved" | "rejected">>({});
  const [caseLayer, setCaseLayer] = useState<"one_minute" | "core" | "appendix">("one_minute");

  async function loadWorks() {
    setWorksLoading(true); setWorksError("");
    try {
      const items = await request<WorkItem[]>("/dossiers");
      setWorks(items);
      setWorkId((current) => current && items.some((item) => item.work.work_id === current) ? current : items[0]?.work.work_id ?? "");
      if (!items.length) setWorksError("知识库中还没有已发布作品。");
    } catch (reason) {
      setWorks([]); setWorkId("");
      setWorksError(reason instanceof Error ? `加载已有作品失败：${reason.message}` : "加载已有作品失败");
    } finally { setWorksLoading(false); }
  }

  useEffect(() => { void loadWorks(); }, []);

  useEffect(() => {
    if (!job || !["created", "reconnaissance_running", "supervisor_planning"].includes(job.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const next = await request<Job>(`/research/v4/jobs/${job.job_id}`);
        setJob(next);
        if (next.status === "planning_failed" && next.planning_failure) setError(next.planning_failure.message);
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "读取规划进度失败");
      }
    }, 1200);
    return () => window.clearInterval(timer);
  }, [job?.job_id, job?.status]);

  const units = job?.plan?.units ?? [];
  const checkpoints = job?.units ?? {};
  const verifiedCount = units.filter((unit) => checkpoints[unit.unit_id]?.status === "verified").length;
  const progress = units.length ? Math.round((verifiedCount / units.length) * 100) : 0;
  const allVerified = units.length > 0 && verifiedCount === units.length;
  const allDecided = job?.proposals.length ? job.proposals.every((proposal) => decisions[proposal.proposal_id]) : false;
  const caseBlocks = useMemo(() => job?.case_file?.blocks.filter((block) => block.layer === caseLayer) ?? [], [job, caseLayer]);

  async function perform(label: string, action: () => Promise<Job>) {
    setBusy(label); setError("");
    try { const next = await action(); setJob(next); return next; }
    catch (reason) { setError(reason instanceof Error ? reason.message : "操作失败"); }
    finally { setBusy(""); }
  }

  async function createJob(workOrEvent?: ResolvedWork | unknown) {
    const work = workOrEvent && typeof workOrEvent === "object" && "work_id" in workOrEvent ? workOrEvent as ResolvedWork : undefined;
    let identity: { work_id: string } | { work: ResolvedWork };
    if (workMode === "existing") {
      identity = { work_id: workId };
    } else {
      let resolved = work;
      if (!resolved) {
        setBusy("resolve"); setError("");
        try {
          const resolution = await request<Resolution>("/works/resolve", {
            method: "POST", body: JSON.stringify({ query: newTitle, media_type: mediaType }),
          });
          setResolutionId(resolution.resolution_id);
          if (resolution.needs_confirmation) {
            setCandidates(resolution.candidates); setBusy(""); return;
          }
          resolved = resolution.resolved_work;
        } catch (reason) {
          setError(reason instanceof Error ? reason.message : "\u4f5c\u54c1\u89e3\u6790\u5931\u8d25"); setBusy(""); return;
        }
      }
      if (!resolved) return;
      identity = { work: resolved };
    }
    const resolvedWorkId = "work" in identity ? identity.work.work_id : identity.work_id;
    const selectedMediaType = "work" in identity ? identity.work.media_type : works.find((item) => item.work.work_id === identity.work_id)?.work.media_type ?? "novel";
    await perform("create", () => request<Job>("/research/v4/jobs", {
      method: "POST",
      body: JSON.stringify({
        ...identity,
        brief: { work_id: resolvedWorkId, media_version: `original_${selectedMediaType}`, user_goal: goal, audience,
          spoiler_level: "full", output_mode: "case_file_and_knowledge", budget_profile: "standard",
          allowed_source_scope: "bilingual_mystery_default" },
      }),
    }));
  }

  async function confirmCandidate(work: ResolvedWork) {
    setBusy("resolve"); setError("");
    try {
      const confirmed = await request<Resolution>(`/works/resolve/${resolutionId}/confirm`, {
        method: "POST", body: JSON.stringify({ work_id: work.work_id }),
      });
      setCandidates([]); setBusy("");
      if (confirmed.resolved_work) await createJob(confirmed.resolved_work);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "\u4f5c\u54c1\u786e\u8ba4\u5931\u8d25"); setBusy("");
    }
  }

  function editMemo(field: "title" | "objective" | "scope" | "reconnaissance_summary", value: string) {
    setJob((current) => current?.plan_memo ? { ...current, plan_memo: { ...current.plan_memo, [field]: value } } : current);
  }

  function editSignature(index: number, field: "question" | "why_it_matters", value: string) {
    setJob((current) => {
      if (!current?.plan_memo) return current;
      const signature_units = current.plan_memo.signature_units.map((unit, unitIndex) => unitIndex === index ? { ...unit, [field]: value } : unit);
      return { ...current, plan_memo: { ...current.plan_memo, signature_units } };
    });
  }

  async function saveMemo() {
    if (!job?.plan_memo) return;
    const { revision: _revision, strategy: _strategy, ...memo } = job.plan_memo;
    await perform("save-memo", () => request<Job>(`/research/v4/jobs/${job.job_id}/plan/memo`, {
      method: "PATCH", body: JSON.stringify(memo),
    }));
  }

  async function runUnifiedSearch() {
    if (!job) return;
    await perform("unified-search", () => request<Job>(`/research/v4/jobs/${job.job_id}/search/run`, {
      method: "POST", body: "{}",
    }));
  }
  async function retryPlanning() {
    if (!job) return;
    await perform("retry-plan", () => request<Job>(`/research/v4/jobs/${job.job_id}/plan/retry`, { method: "POST", body: "{}" }));
  }
  async function approvePlan() {
    if (!job) return;
    await perform("approve-plan", () => request<Job>(`/research/v4/jobs/${job.job_id}/plan/approve`, { method: "POST", body: "{}" }));
  }

  async function runUnit(unit: ResearchUnit) {
    if (!job) return;
    const checkpoint = checkpoints[unit.unit_id];
    const hasEvidence = Boolean(checkpoint.finding_bundle?.evidence_candidates.length);
    const nextAction = checkpoint.status === "approved" || checkpoint.status === "failed" || (checkpoint.status === "searched" && !hasEvidence) ? "search"
      : checkpoint.status === "searched" ? "curate" : checkpoint.status === "curated" ? "verify" : "";
    if (!nextAction) return;
    await perform(unit.unit_id, () => request<Job>(`/research/v4/jobs/${job.job_id}/units/${unit.unit_id}/${nextAction}`, { method: "POST" }));
  }

  async function freeze() {
    if (!job) return;
    await perform("freeze", () => request<Job>(`/research/v4/jobs/${job.job_id}/freeze`, { method: "POST" }));
  }

  async function project() {
    if (!job) return;
    await perform("project", () => request<Job>(`/research/v4/jobs/${job.job_id}/project`, { method: "POST" }));
  }

  async function loadEvaluation() {
    if (!job) return;
    setBusy("evaluation");
    try { const result = await request<{ metrics: Metric[] }>(`/research/v4/jobs/${job.job_id}/evaluation`); setMetrics(result.metrics); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "评测读取失败"); }
    finally { setBusy(""); }
  }

  async function submitReview() {
    if (!job || !allDecided) return;
    const next = await perform("review", () => request<Job>(`/research/v4/jobs/${job.job_id}/review`, {
      method: "POST", body: JSON.stringify({
        approved_proposal_ids: Object.entries(decisions).filter(([, value]) => value === "approved").map(([id]) => id),
        rejected_proposal_ids: Object.entries(decisions).filter(([, value]) => value === "rejected").map(([id]) => id),
      }),
    }));
    if (next) setDecisions(Object.fromEntries(next.proposals.map((proposal) => [proposal.proposal_id, proposal.review_status])) as Record<string, "approved" | "rejected">);
  }

  async function publish() {
    if (!job) return;
    setBusy("publish"); setError("");
    try {
      const result = await request<{ job: Job }>(`/research/v4/jobs/${job.job_id}/publish`, { method: "POST" });
      setJob(result.job);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "发布失败"); }
    finally { setBusy(""); }
  }

  function reset() { setJob(null); setMetrics([]); setDecisions({}); setError(""); }

  return <main className="v04Page">
    <section className="v04Hero">
      <div><p className="v04Eyebrow">AGENTIC RESEARCH · WORKDOSSIER 0.4</p><h1>把调查过程，变成<br/><em>可验证的知识。</em></h1></div>
      <p>Supervisor 规划研究，Search Agent 追踪证据，Verifier 守住事实边界。最终档案和知识库变更来自同一份验证知识。</p>
    </section>

    {!job ? <section className="v04Intake">
      <div className="intakeIndex">01</div><div className="intakeBody">
        <div className="sectionTitle"><span>研究任务</span><h2>从一个明确的问题开始</h2></div>
        <div className="workModeTabs"><button className={workMode === "new" ? "active" : ""} onClick={() => { setWorkMode("new"); setCandidates([]); }}>{"\u65b0\u4f5c\u54c1"}</button><button className={workMode === "existing" ? "active" : ""} onClick={() => { setWorkMode("existing"); setCandidates([]); }}>{"\u5df2\u6709\u4f5c\u54c1"}</button></div>
        {workMode === "new" && <div className="newWorkFields"><label><span>{"\u4f5c\u54c1\u540d\u79f0"}</span><input value={newTitle} onChange={(event) => setNewTitle(event.target.value)} placeholder={"\u4f8b\u5982\uff1a\u65e0\u4eba\u751f\u8fd8"} /></label><label><span>{"\u5a92\u4f53\u7c7b\u578b"}</span><select value={mediaType} onChange={(event) => setMediaType(event.target.value)}><option value="novel">{"\u5c0f\u8bf4"}</option><option value="film">{"\u7535\u5f71"}</option><option value="series">{"\u5267\u96c6"}</option><option value="game">{"\u6e38\u620f"}</option><option value="manga">{"\u6f2b\u753b"}</option></select></label></div>}
        <div className="intakeGrid">
          {workMode === "existing" && <label><span>选择作品</span><select value={workId} onChange={(event) => setWorkId(event.target.value)} disabled={worksLoading}>{works.map((item) => <option key={item.work.work_id} value={item.work.work_id}>{item.work.canonical_title} · {item.dossier_version}</option>)}</select></label>}
          <label><span>目标读者</span><input value={audience} onChange={(event) => setAudience(event.target.value)} /></label>
          <label className="wide"><span>你想弄清什么？</span><textarea value={goal} onChange={(event) => setGoal(event.target.value)} rows={4}/></label>
        </div>
        {workMode === "existing" && worksError && <p className="errorText">{worksError} <button type="button" className="textButton" onClick={() => void loadWorks()}>重新加载</button></p>}
        <div className="intakeFoot"><div><ShieldCheck/><span>原著版本隔离</span></div><div><Gauge/><span>受控预算</span></div><div><Database/><span>发布前人工审核</span></div><button onClick={createJob} disabled={!goal.trim() || Boolean(busy) || (workMode === "new" ? !newTitle.trim() : !workId)}>{busy === "create" ? <LoaderCircle className="spin"/> : <Sparkles/>}让 Supervisor 生成计划</button></div>
        {candidates.length > 0 && <div className="identityCandidates"><header><b>{"\u8bf7\u9009\u62e9\u5177\u4f53\u4f5c\u54c1"}</b><span>{"\u6839\u636e\u4f5c\u8005\u3001\u5e74\u4efd\u548c\u7c7b\u578b\u786e\u8ba4\u7814\u7a76\u5bf9\u8c61"}</span></header>{candidates.map((candidate) => <button key={candidate.work_id} onClick={() => confirmCandidate(candidate)}><div><b>{candidate.canonical_title}</b><span>{candidate.creators.join(" / ") || "Unknown creator"} / {candidate.release_year || "Unknown year"} / {candidate.media_type}</span></div><ArrowRight/></button>)}</div>}
      </div>
    </section> : <>
      <section className="jobRail">
        <div><button className="textButton" onClick={reset}>← 新研究</button><small>{job.job_id}</small><h2>《{job.work.canonical_title}》</h2></div>
        <div className="jobProgress"><span>{statusNames[job.status] ?? job.status}</span><div><i style={{ width: `${progress}%` }}/></div><b>{verifiedCount}/{units.length} Units verified</b></div>
      </section>

      {["created", "reconnaissance_running", "supervisor_planning"].includes(job.status) && <section className="planStage"><header><div><p className="v04Eyebrow">SUPERVISOR PLANNING</p><h2>正在生成可审核的研究计划</h2><p>任务已经保存。页面会自动读取初步侦察与 Supervisor 的最新进度。</p></div><LoaderCircle className="spin"/></header></section>}
      {job.status === "planning_failed" && <section className="planStage"><header><div><p className="v04Eyebrow">PLANNING FAILED</p><h2>研究计划尚未生成</h2><p>{job.planning_failure?.message ?? "规划阶段失败，可以安全重试。"}</p></div><button className="primaryV04" onClick={retryPlanning} disabled={busy === "retry-plan"}>{busy === "retry-plan" ? <LoaderCircle className="spin"/> : <RefreshCw/>}重试规划</button></header></section>}
      {job.status === "awaiting_plan_approval" && job.plan_memo && <PlanMemoEditor memo={job.plan_memo} busy={busy} onEdit={editMemo} onEditUnit={editSignature} onSave={saveMemo} onApprove={approvePlan}/>}
      {job.plan?.approved && !job.case_file && <section className="executionStage">
        <header><div><p className="v04Eyebrow">RESEARCH ORCHESTRATOR</p><h2>逐个 Unit 建立证据链</h2></div>{allVerified && <button className="primaryV04" onClick={freeze} disabled={busy === "freeze"}>{busy === "freeze" ? <LoaderCircle className="spin"/> : <ShieldCheck/>}冻结验证知识</button>}{job.status === "knowledge_frozen" && <button className="primaryV04" onClick={project} disabled={busy === "project"}>{busy === "project" ? <LoaderCircle className="spin"/> : <BookOpen/>}生成档案与知识建议</button>}</header>
        {units.some((unit) => { const checkpoint = checkpoints[unit.unit_id]; return checkpoint?.status === "approved" || checkpoint?.status === "failed" || (checkpoint?.status === "searched" && !checkpoint.finding_bundle?.evidence_candidates.length); }) && <div className="unifiedSearchBar"><div><Search/><span><b>Unified Web Search Agent</b><small>{job.search_session?.queries.length ?? 0} queries / {Object.keys(job.search_session?.snapshots ?? {}).length} shared snapshots</small></span></div><button onClick={runUnifiedSearch} disabled={busy === "unified-search"}>{busy === "unified-search" ? <LoaderCircle className="spin"/> : <Play/>}运行统一搜索</button></div>}
        <div className="unitBoard">{units.map((unit, index) => <UnitCard key={unit.unit_id} unit={unit} checkpoint={checkpoints[unit.unit_id]} index={index + 1} busy={busy === unit.unit_id} onRun={() => runUnit(unit)}/>)}</div>
        {job.verified_knowledge && <KnowledgeFreeze job={job}/>}
      </section>}

      {job.case_file && <section className="resultStage">
        <div className="caseFile">
          <header><p className="v04Eyebrow">VERIFIED CASE FILE</p><h2>{job.case_file.title}</h2><p>{job.case_file.research_mainline}</p><small><ShieldCheck/> {job.case_file.reliability_note}</small></header>
          <div className="layerTabs">{(["one_minute", "core", "appendix"] as const).map((layer) => <button key={layer} className={caseLayer === layer ? "active" : ""} onClick={() => setCaseLayer(layer)}>{layer === "one_minute" ? "一分钟读懂" : layer === "core" ? "核心档案" : "证据附录"}</button>)}</div>
          <div className="caseBlocks">{caseBlocks.map((block) => <article key={block.block_id}><span>{block.block_type}</span><h3>{block.title}</h3><p>{block.text}</p><footer><b>{block.claim_ids.length} Claims</b><b>{block.evidence_ids.length} Evidence</b></footer></article>)}</div>
        </div>
        <aside className="reviewPanel"><header><p className="v04Eyebrow">HUMAN REVIEW</p><h2>知识库变更</h2><p>每一项都必须明确批准或拒绝。</p></header>
          <div className="proposalStack">{job.proposals.map((proposal) => <article key={proposal.proposal_id} className={decisions[proposal.proposal_id] ?? proposal.review_status}><div><span>{proposal.operation}</span><b>{proposal.target_section}</b><p>{String(proposal.payload.summary ?? proposal.payload.name ?? "结构化知识变更")}</p><small>{proposal.claim_ids.length} Claims · {proposal.evidence_ids.length} Evidence</small></div><div className="decisionButtons"><button aria-label="批准" onClick={() => setDecisions((current) => ({ ...current, [proposal.proposal_id]: "approved" }))}><Check/></button><button aria-label="拒绝" onClick={() => setDecisions((current) => ({ ...current, [proposal.proposal_id]: "rejected" }))}><X/></button></div></article>)}</div>
          <div className="reviewActions"><button onClick={submitReview} disabled={!allDecided || busy === "review"}>{busy === "review" ? <LoaderCircle className="spin"/> : <ShieldCheck/>}提交审核决定</button><button className="publishButton" onClick={publish} disabled={job.proposals.some((proposal) => proposal.review_status === "pending") || !job.proposals.some((proposal) => proposal.review_status === "approved") || busy === "publish"}>{busy === "publish" ? <LoaderCircle className="spin"/> : <Send/>}发布新 WorkDossier</button></div>
        </aside>
      </section>}

      <section className="evaluationStage"><header><div><p className="v04Eyebrow">DETERMINISTIC EVALUATION</p><h2>不是“看起来不错”，而是可测量</h2></div><button onClick={loadEvaluation} disabled={busy === "evaluation"}>{busy === "evaluation" ? <LoaderCircle className="spin"/> : <RefreshCw/>}刷新评测</button></header>{metrics.length > 0 && <div className="metricBoard">{metrics.map((metric) => <article key={metric.name} className={metric.passed ? "pass" : "fail"}><div>{metric.passed ? <CheckCircle2/> : <AlertTriangle/>}<span>{metricNames[metric.name] ?? metric.name}</span></div><strong>{metric.name.includes("contamination") || metric.name.includes("rate") || metric.name.includes("ratio") ? `${(metric.value * 100).toFixed(1)}%` : `${Math.round(metric.value * 100)}%`}</strong><small>目标 {metric.target === undefined ? "—" : `${Math.round(metric.target * 100)}%`}</small></article>)}</div>}</section>
    </>}
    {job?.status === "published" && <div className="publishedToast"><CheckCircle2/><div><b>WorkDossier {job.published_version} 已发布</b><span>验证知识、档案与 ResearchDelta 已完成版本化沉淀。</span></div></div>}
    {error && <div className="v04Error"><AlertTriangle/><span>{error}</span><button onClick={() => setError("")}><X/></button></div>}
  </main>;
}

function UnitCard({ unit, checkpoint, index, busy, onRun }: { unit: ResearchUnit; checkpoint: UnitCheckpoint; index: number; busy: boolean; onRun: () => void }) {
  const needsSearch = checkpoint?.status === "approved" || checkpoint?.status === "failed" || (checkpoint?.status === "searched" && !checkpoint.finding_bundle?.evidence_candidates.length);
  const nextLabel = needsSearch ? "\u91cd\u8bd5 Search Agent" : checkpoint?.status === "searched" ? "\u4ea4\u7ed9 Curator" : checkpoint?.status === "curated" ? "\u8fd0\u884c Verifier" : "\u5df2\u9a8c\u8bc1";
  return <article className={`unitCard ${checkpoint?.status ?? "planned"}`}><div className="unitNumber">{String(index).padStart(2, "0")}</div><div className="unitContent"><header><div><span>{unit.track === "mandatory" ? "MANDATORY" : "SIGNATURE"}</span><b>{domainNames[unit.domain] ?? unit.domain}</b></div><i>{statusNames[checkpoint?.status] ?? checkpoint?.status}</i></header><h3>{unit.question}</h3><p>{unit.why_it_matters}</p>{checkpoint?.finding_bundle && <details className="trace"><summary><Network/>Research Trace · {checkpoint.finding_bundle.actions.length} actions <ChevronDown/></summary>{checkpoint.finding_bundle.actions.map((action) => <div key={action.sequence}><b>{action.sequence}. {action.action}</b><span>{action.decision_summary}</span><small>{action.result_summary}</small></div>)}</details>}{checkpoint?.verification_results?.length > 0 && <div className="verificationList">{checkpoint.verification_results.map((result) => <span key={result.claim_id} className={result.status}>{result.status} · {result.reason}</span>)}</div>}</div><div className="unitAction"><div><span>{checkpoint?.finding_bundle?.evidence_candidates.length ?? 0}</span><small>Evidence</small></div><button onClick={onRun} disabled={busy || checkpoint?.status === "verified"}>{busy ? <LoaderCircle className="spin"/> : checkpoint?.status === "verified" ? <Check/> : <Play/>}{nextLabel}</button></div></article>;
}

function KnowledgeFreeze({ job }: { job: Job }) {
  const knowledge = job.verified_knowledge!;
  return <section className="freezePanel"><div><ShieldCheck/><span>VERIFIED KNOWLEDGE</span><h3>{knowledge.claims.length} Claims 已进入统一事实层</h3><p>{knowledge.domain_objects.length} 个领域对象 · {knowledge.evidence_ids.length} 条证据 · {knowledge.conflicts.length} 个冲突 · {knowledge.unknowns.length} 个未知</p></div><div className="gapList">{knowledge.gaps.map((gap) => <span key={gap.research_unit_id} className={gap.status}>{gap.status === "resolved" ? <Check/> : <AlertTriangle/>}{gap.research_unit_id}</span>)}</div></section>;
}
