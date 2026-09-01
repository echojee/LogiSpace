import { ArrowRight, Check, LoaderCircle, Search, ShieldCheck, Sparkles } from "lucide-react";

type Unit = { unit_id: string; domain: string; question: string; why_it_matters: string; budget: { max_queries: number; max_pages: number } };
type Perspective = { perspective_id: string; title: string; description: string; is_basic: boolean };
type OutlineNode = { section_id: string; title: string; purpose: string; research_questions: string[]; search_directions: string[]; open_questions: string[] };
type Memo = { title: string; objective: string; scope: string; reconnaissance_summary: string; mandatory_units: Unit[]; signature_units: Unit[]; perspectives: Perspective[]; research_turns: unknown[]; direct_outline?: { nodes: OutlineNode[] }; research_outline?: { nodes: OutlineNode[] }; revision: number; strategy: "build_and_verify" | "review_strengthen_and_correct" };

const domainNames: Record<string, string> = { relationships: "人物关系", multiple_timelines: "多重时间线", tricks: "诡计", murder_methods: "杀人手法" };

export default function PlanMemoEditor({ memo, busy, selectedUnitIds, error, onToggleUnit, onEdit, onEditUnit, onSave, onApprove }: {
  memo: Memo; busy: string; selectedUnitIds: string[]; error?: string;
  onToggleUnit: (unitId: string) => void;
  onEdit: (field: "title" | "objective" | "scope" | "reconnaissance_summary", value: string) => void;
  onEditUnit: (index: number, field: "question" | "why_it_matters", value: string) => void;
  onSave: () => void; onApprove: () => void;
}) {
  const selected = new Set(selectedUnitIds);
  return <section className="memoStage">
    <header><div><p className="v04Eyebrow">PLAN MEMO / REVISION {memo.revision}</p><h2>{memo.strategy === "build_and_verify" ? "审阅新作品的特色研究方案" : "审阅已有作品的复核强化方案"}</h2></div><span className="memoScout"><Search/>初步侦察已完成</span></header>
    <div className="memoFields">
      <label><span>备忘录标题</span><input value={memo.title} onChange={(event) => onEdit("title", event.target.value)}/></label>
      <label><span>研究目标</span><textarea rows={2} value={memo.objective} onChange={(event) => onEdit("objective", event.target.value)}/></label>
      <label><span>作品与来源边界</span><input value={memo.scope} onChange={(event) => onEdit("scope", event.target.value)}/></label>
      <label><span>初步侦察摘要</span><textarea rows={4} value={memo.reconnaissance_summary} onChange={(event) => onEdit("reconnaissance_summary", event.target.value)}/></label>
    </div>
    {!!memo.perspectives.length && <div className="memoPerspectives"><h3><Sparkles/>双视角问题发现</h3><div>{memo.perspectives.map((perspective) => <span key={perspective.perspective_id}><b>{perspective.is_basic ? "基础 · " : "作品专属 · "}{perspective.title}</b>{perspective.description}</span>)}</div><small>{memo.research_turns.length} 轮内部侦察对话已用于增强大纲；临时答案不会直接进入知识库。</small></div>}
    {error && <div className="memoRetryNotice"><ShieldCheck/><div><b>上次研究未完成，计划已保留</b><p>{error}</p></div></div>}
    {memo.research_outline && <div className="memoOutline"><h3><Search/>研究增强大纲 / Plan Prompt</h3>{memo.research_outline.nodes.map((node, index) => <article className={selected.has(node.section_id) ? "" : "disabledPlan"} key={node.section_id}><label className="todoCheck"><input type="checkbox" checked={selected.has(node.section_id)} onChange={() => onToggleUnit(node.section_id)}/><span>{String(index + 1).padStart(2, "0")}</span></label><div><b>{node.title}</b><p>{node.purpose}</p>{node.research_questions.map((question) => <p className="outlineQuestion" key={question}>▸ {question}</p>)}</div><small>{node.search_directions.length} 搜索方向 · {node.open_questions.length} 未决问题</small></article>)}</div>}
    <div className="memoFeatures">
      <h3><ShieldCheck/>基础研究待办 · 可按本轮需要取消</h3>
      {memo.mandatory_units.map((unit, index) => <article className={`memoTodo mandatory ${selected.has(unit.unit_id) ? "" : "disabledPlan"}`} key={unit.unit_id}><label className="todoCheck"><input type="checkbox" checked={selected.has(unit.unit_id)} onChange={() => onToggleUnit(unit.unit_id)}/><span>{String(index + 1).padStart(2, "0")}</span></label><div><b>{domainNames[unit.domain] ?? unit.domain}</b><p>{unit.question}</p></div><p>{unit.why_it_matters}</p><small>{unit.budget.max_queries} queries / {unit.budget.max_pages} pages</small></article>)}
      <h3><Sparkles/>作品专属研究待办 · 可编辑、可取消</h3>
      {memo.signature_units.map((unit, index) => <article className={`memoTodo ${selected.has(unit.unit_id) ? "" : "disabledPlan"}`} key={unit.unit_id}><label className="todoCheck"><input type="checkbox" checked={selected.has(unit.unit_id)} onChange={() => onToggleUnit(unit.unit_id)}/><span>{String(index + memo.mandatory_units.length + 1).padStart(2, "0")}</span></label><input aria-label={`特色研究问题 ${index + 1}`} value={unit.question} onChange={(event) => onEditUnit(index, "question", event.target.value)}/><textarea aria-label={`特色研究意义 ${index + 1}`} rows={3} value={unit.why_it_matters} onChange={(event) => onEditUnit(index, "why_it_matters", event.target.value)}/><small>{unit.budget.max_queries} queries / {unit.budget.max_pages} pages</small></article>)}
    </div>
    <div className="approvalBar"><p>已选择 {selectedUnitIds.length} 项。批准后，所选计划会整体封装为一次 Plan Prompt，由 OpenAI API 完成搜索、写作和报告输出。</p><div><button className="secondaryV04" onClick={onSave} disabled={busy === "save-memo"}>{busy === "save-memo" ? <LoaderCircle className="spin"/> : <Check/>}保存 Memo</button><button onClick={onApprove} disabled={busy === "approve-plan" || selectedUnitIds.length === 0}>{busy === "approve-plan" ? <LoaderCircle className="spin"/> : <ArrowRight/>}批准并开始研究</button></div></div>
  </section>;
}
