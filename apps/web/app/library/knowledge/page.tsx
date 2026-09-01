"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BookOpen, Clapperboard } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
type KnowledgeWork = { work_id: string; title: string; media_type: string; release_year?: number; creators: string[]; cover_url?: string; media_version: string; current_knowledge_version: string; domains: string[] };

export default function KnowledgeMemoryLibrary() {
  const [items, setItems] = useState<KnowledgeWork[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { fetch(`${API}/knowledge/works`).then((response) => { if (!response.ok) throw new Error(); return response.json(); }).then(setItems).catch(() => setError("无法读取 Knowledge Memory。")); }, []);
  return <main className="libraryPage"><section className="pageIntro compact"><p className="eyebrow">RESEARCHED WORKS</p><h1>已研究作品</h1><p>每部完成深度研究的作品都沉淀为独立知识空间。选择作品后，在同一页面查看人物关系、时间线、诡计和杀人手法。</p></section>{error && <p className="errorText knowledgeNotice">{error}</p>}{!error && !items.length && <p className="knowledgeNotice">尚无已沉淀的研究作品。请先完成一次深度研究并批准进入知识库。</p>}<div className="knowledgePosterGrid">{items.map((item, index) => <Link href={`/library/knowledge/${item.work_id}`} key={item.work_id} className={`knowledgePoster posterTone${index % 5}`}>
    <div className="posterArtwork">{item.cover_url ? <img src={item.cover_url} alt={`《${item.title}》封面`}/> : <><span>{item.media_type === "novel" ? <BookOpen/> : <Clapperboard/>}</span><strong>{item.title}</strong><small>{item.media_type === "novel" ? "MYSTERY FICTION" : "SCREEN MYSTERY"}</small></>}</div>
    <div className="posterMeta"><small>KNOWLEDGE {item.current_knowledge_version}</small><h2>《{item.title}》</h2><p>{[...(item.creators || []), item.release_year].filter(Boolean).join(" · ") || item.media_version}</p><span>{item.domains.length}/4 个知识领域</span></div>
  </Link>)}</div></main>;
}
