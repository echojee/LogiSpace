import { ArrowRight, Check, LoaderCircle, Search, ShieldCheck, Sparkles } from "lucide-react";

type Unit = { unit_id: string; question: string; why_it_matters: string; budget: { max_queries: number; max_pages: number } };
type Memo = { title: string; objective: string; scope: string; reconnaissance_summary: string; signature_units: Unit[]; revision: number; strategy: "build_and_verify" | "review_strengthen_and_correct" };

export default function PlanMemoEditor({ memo, busy, onEdit, onEditUnit, onSave, onApprove }: {
  memo: Memo; busy: string;
  onEdit: (field: "title" | "objective" | "scope" | "reconnaissance_summary", value: string) => void;
  onEditUnit: (index: number, field: "question" | "why_it_matters", value: string) => void;
  onSave: () => void; onApprove: () => void;
}) {
  return <section className="memoStage">
    <header><div><p className="v04Eyebrow">PLAN MEMO / REVISION {memo.revision}</p><h2>{memo.strategy === "build_and_verify" ? "审阅新作品的特色研究方案" : "审阅已有作品的复核强化方案"}</h2></div><span className="memoScout"><Search/>初步侦察已完成</span></header>
    <div className="memoFields">
      <label><span>备忘录标题</span><input value={memo.title} onChange={(event) => onEdit("title", event.target.value)}/></label>
      <label><span>研究目标</span><textarea rows={2} value={memo.objective} onChange={(event) => onEdit("objective", event.target.value)}/></label>
      <label><span>作品与来源边界</span><input value={memo.scope} onChange={(event) => onEdit("scope", event.target.value)}/></label>
      <label><span>初步侦察摘要</span><textarea rows={4} value={memo.reconnaissance_summary} onChange={(event) => onEdit("reconnaissance_summary", event.target.value)}/></label>
    </div>
    <div className="memoFeatures"><h3><Sparkles/>作品专属研究方向</h3>{memo.signature_units.map((unit, index) => <article key={unit.unit_id}><span>FEATURE {String(index + 1).padStart(2, "0")}</span><input value={unit.question} onChange={(event) => onEditUnit(index, "question", event.target.value)}/><textarea rows={3} value={unit.why_it_matters} onChange={(event) => onEditUnit(index, "why_it_matters", event.target.value)}/><small>{unit.budget.max_queries} queries / {unit.budget.max_pages} pages</small></article>)}</div>
    <div className="mandatoryNote"><ShieldCheck/><div><b>基础研究协议在后台执行</b><p>{memo.strategy === "build_and_verify" ? "人物关系、多重时间线、诡计结构与杀人手法会建立并验证新基线，不占用 Memo 的审阅篇幅。" : "人物关系、多重时间线、诡计结构与杀人手法会复核、强化并纠错，不占用 Memo 的审阅篇幅。"}</p></div></div>
    <div className="approvalBar"><p>可以先保存修改，批准后才启动统一搜索会话。</p><div><button className="secondaryV04" onClick={onSave} disabled={busy === "save-memo"}>{busy === "save-memo" ? <LoaderCircle className="spin"/> : <Check/>}保存 Memo</button><button onClick={onApprove} disabled={busy === "approve-plan"}>{busy === "approve-plan" ? <LoaderCircle className="spin"/> : <ArrowRight/>}批准并进入研究</button></div></div>
  </section>;
}
