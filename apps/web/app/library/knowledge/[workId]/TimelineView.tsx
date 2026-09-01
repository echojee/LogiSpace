"use client";

import { useMemo, useState } from "react";

export type TimelineEvent = {
  event_id: string;
  title: string;
  summary: string;
  order: number;
  track: string;
  time_label: string;
  source_claim_ids: string[];
};

const TRACKS: Record<string, string> = {
  objective: "真实时间线",
  truth: "真实时间线",
  investigation: "调查时间线",
  reveal: "读者时间线",
  narrative: "读者时间线",
  reader: "读者时间线",
};

export default function TimelineView({ events, tracks, scale }: { events: TimelineEvent[]; tracks: Record<string, string>; scale: string }) {
  const [selected, setSelected] = useState<TimelineEvent | null>(null);
  const grouped = useMemo(() => Object.entries(events.reduce<Record<string, TimelineEvent[]>>((result, event) => {
    (result[event.track] ||= []).push(event);
    return result;
  }, {})).map(([track, items]) => [track, items.sort((a, b) => a.order - b.order)] as const), [events]);

  if (!events.length) return <p className="emptyPanel">报告中没有足够的引用支持来生成时间线。</p>;
  return <div className="interactiveViz timelineView"><p className="timelineScaleNote">{scale === "ordinal" ? "按事件顺序排列；档案没有明确时刻时不伪造日期。" : "按档案中的时间标签与事件顺序排列。"}</p><div className="timelineLanes">{grouped.map(([track, items]) => <section className="timelineLane" key={track}><h3>{tracks[track] || TRACKS[track] || track}</h3><div className="timelineLaneScroll"><div className="timelineLaneRail">{items.map((event) => <button key={event.event_id} className={selected?.event_id === event.event_id ? "active" : ""} onClick={() => setSelected(event)}><small>{event.time_label || `顺序 ${event.order}`}</small><span>{event.title}</span></button>)}</div></div></section>)}</div>{selected ? <article className="timelineDetail"><small>{tracks[selected.track] || TRACKS[selected.track] || selected.track} · {selected.time_label || `顺序 ${selected.order}`}</small><h3>{selected.title}</h3><p>{selected.summary || "暂无补充说明。"}</p><span>{selected.source_claim_ids.length} 条 Claims</span></article> : <p className="vizSelection">点击任一事件查看档案中的详细说明。</p>}</div>;
}
