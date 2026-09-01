"use client";

import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Clock3, LoaderCircle, Network, Skull, WandSparkles } from "lucide-react";
import KnowledgeModal from "./KnowledgeModal";
import RelationshipGraph, { RelationshipEdge, RelationshipNode } from "./RelationshipGraph";
import TimelineView, { TimelineEvent } from "./TimelineView";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
type DomainObject = { object_id: string; object_type: "character" | "relationship" | "timeline_alignment" | "trick" | "murder_method"; payload: Record<string, unknown>; claim_ids: string[] };
type Block = { block_id: string; block_type: string; title: string; text: string };
type Memory = { media_version: string; knowledge_version: string; case_file: { title: string; research_mainline: string; reliability_note: string; blocks: Block[] }; verified_knowledge: { claims: unknown[]; domain_objects: DomainObject[] } };
type Visualization = { title: string; relationship_nodes: RelationshipNode[]; relationship_edges: RelationshipEdge[]; timeline_events: TimelineEvent[]; timeline_scale: string; timeline_tracks: Record<string, string>; source_entity_ids: string[]; source_claim_ids: string[]; warnings: string[] };
type Panel = "relationships" | "timeline" | "tricks" | "methods" | "";

function objectTitle(item: DomainObject) {
  return String(item.payload.title || item.payload.name || (item.object_type === "trick" ? "未命名诡计" : "未命名手法"));
}

export default function KnowledgeWorkPage() {
  const { workId } = useParams<{ workId: string }>();
  const [memory, setMemory] = useState<Memory | null>(null);
  const [visualizations, setVisualizations] = useState<Partial<Record<"relationships" | "timeline", Visualization>>>({});
  const [panel, setPanel] = useState<Panel>("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  useEffect(() => { fetch(`${API}/knowledge/works/${workId}`).then(async (response) => { if (!response.ok) throw new Error((await response.json()).detail); return response.json(); }).then(setMemory).catch(() => setError("无法读取该作品的 Knowledge Memory。")); }, [workId]);

  const domainObjects = useMemo(() => memory?.verified_knowledge.domain_objects || [], [memory]);
  const tricks = useMemo(() => domainObjects.filter((item) => item.object_type === "trick"), [domainObjects]);
  const methods = useMemo(() => domainObjects.filter((item) => item.object_type === "murder_method"), [domainObjects]);

  async function openVisualization(type: "relationships" | "timeline") {
    setPanel(type);
    if (visualizations[type]) return;
    setBusy(type); setError("");
    try {
      const response = await fetch(`${API}/knowledge/works/${workId}/visualizations`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ visualization_type: type === "relationships" ? "character_relationship" : "timeline", knowledge_version: "current" }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail);
      setVisualizations((current) => ({ ...current, [type]: data }));
    } catch { setError("生成失败：当前知识可能还没有足够的结构化支持。"); }
    finally { setBusy(""); }
  }

  if (!memory && !error) return <main className="loading">正在载入 Knowledge Memory…</main>;
  return <main className="libraryPage knowledgeWorkPage">{memory && <>
    <section className="workHero"><small>KNOWLEDGE {memory.knowledge_version}</small><h1>{memory.case_file.title}</h1><p>{memory.media_version} · {memory.verified_knowledge.claims.length} Claims · {domainObjects.length} Domain Objects</p></section>
    <section className="knowledgeDossier"><p className="eyebrow">RESEARCH MAINLINE</p><h2>{memory.case_file.research_mainline}</h2><p>{memory.case_file.reliability_note}</p><details><summary>查看完整研究档案</summary>{memory.case_file.blocks.map((block) => <article key={block.block_id}><h3>{block.title}</h3><p>{block.text}</p></article>)}</details></section>
    <section className="knowledgeFourGrid">
      <button onClick={() => void openVisualization("relationships")}><Network/><small>RELATIONSHIP</small><h2>人物关系</h2><p>交互查看人物、关系方向与支持 Claims。</p><span>打开关系图 →</span></button>
      <button onClick={() => void openVisualization("timeline")}><Clock3/><small>ADAPTIVE TRACKS</small><h2>时间线</h2><p>按作品结构选择真实、调查或读者时间线。</p><span>打开时间线 →</span></button>
      <button onClick={() => setPanel("tricks")}><WandSparkles/><small>TRICKS · {tricks.length}</small><h2>诡计</h2><p>读书卡片形式整理误导与机制。</p><span>查看卡片 →</span></button>
      <button onClick={() => setPanel("methods")}><Skull/><small>METHODS · {methods.length}</small><h2>杀人手法</h2><p>区分物理实施方式与叙事诡计。</p><span>查看卡片 →</span></button>
    </section>
  </>}
  {error && <p className="errorText knowledgeNotice">{error}</p>}
  {panel && memory && <KnowledgeModal title={{ relationships: "人物关系", timeline: "时间线", tricks: "诡计", methods: "杀人手法" }[panel]} wide={panel === "relationships" || panel === "timeline"} onClose={() => setPanel("")}>
    {busy === panel && <div className="modalLoading"><LoaderCircle className="spin"/>正在构建结构化视图…</div>}
    {panel === "relationships" && visualizations.relationships && <RelationshipGraph nodes={visualizations.relationships.relationship_nodes} edges={visualizations.relationships.relationship_edges}/>} 
    {panel === "timeline" && visualizations.timeline && <TimelineView events={visualizations.timeline.timeline_events} tracks={visualizations.timeline.timeline_tracks} scale={visualizations.timeline.timeline_scale}/>} 
    {panel === "tricks" && <div className="readingCardGrid">{tricks.length ? tricks.map((item) => <article key={item.object_id}><WandSparkles/><small>{item.claim_ids.length} CLAIMS</small><h3>{objectTitle(item)}</h3><p>{String(item.payload.summary || item.payload.mechanism || "暂无补充说明。")}</p></article>) : <p className="emptyPanel">报告中没有足够的引用支持来提取诡计卡片。</p>}</div>}
    {panel === "methods" && <div className="readingCardGrid">{methods.length ? methods.map((item) => <article className="dark" key={item.object_id}><Skull/><small>{item.claim_ids.length} CLAIMS</small><h3>{objectTitle(item)}</h3><p>{String(item.payload.summary || item.payload.execution || "暂无补充说明。")}</p></article>) : <p className="emptyPanel">报告中没有足够的引用支持来提取杀人手法卡片。</p>}</div>}
  </KnowledgeModal>}
  </main>;
}
