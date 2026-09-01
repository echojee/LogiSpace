"use client";

import { useEffect, useMemo, useRef, useState } from "react";

export type RelationshipEdge = {
  source_id: string;
  source_label: string;
  relation: string;
  target_id: string;
  target_label: string;
  source_claim_ids: string[];
};

export type RelationshipNode = {
  character_id: string;
  label: string;
  summary: string;
  source_claim_ids: string[];
};

export default function RelationshipGraph({ nodes, edges }: { nodes: RelationshipNode[]; edges: RelationshipEdge[] }) {
  const target = useRef<HTMLDivElement>(null);
  const [selection, setSelection] = useState("点击人物或关系可查看详情。");
  const elements = useMemo(() => {
    const knownNodes = new Map<string, RelationshipNode>();
    nodes.forEach((node) => knownNodes.set(node.character_id, node));
    edges.forEach((edge) => {
      if (!knownNodes.has(edge.source_id)) knownNodes.set(edge.source_id, { character_id: edge.source_id, label: edge.source_label, summary: "", source_claim_ids: edge.source_claim_ids });
      if (!knownNodes.has(edge.target_id)) knownNodes.set(edge.target_id, { character_id: edge.target_id, label: edge.target_label, summary: "", source_claim_ids: edge.source_claim_ids });
    });
    return [
      ...Array.from(knownNodes.values(), (node) => ({ data: { id: node.character_id, label: node.label, summary: node.summary, claims: node.source_claim_ids.length } })),
      ...edges.map((edge, index) => ({
        data: {
          id: `edge_${index}_${edge.source_id}_${edge.target_id}`,
          source: edge.source_id,
          target: edge.target_id,
          label: edge.relation,
          claims: edge.source_claim_ids.length,
        },
      })),
    ];
  }, [edges, nodes]);

  useEffect(() => {
    if (!target.current || !edges.length) return;
    let disposed = false;
    let instance: { destroy: () => void } | null = null;
    void import("cytoscape").then(({ default: cytoscape }) => {
      if (disposed || !target.current) return;
      const cy = cytoscape({
        container: target.current,
        elements,
        layout: { name: "concentric", animate: false, padding: 70, avoidOverlap: true, minNodeSpacing: 72, spacingFactor: 1.45 },
        style: [
          { selector: "node", style: { "background-color": "#174f3d", label: "data(label)", color: "#17201d", "font-size": 12, "font-weight": "bold", "text-valign": "bottom", "text-margin-y": 9, "text-wrap": "wrap", "text-max-width": "92px", width: 38, height: 38, "border-width": 4, "border-color": "#d7e44c" } },
          { selector: "edge", style: { width: 1.6, "line-color": "#aab2ae", "target-arrow-color": "#aab2ae", "target-arrow-shape": "triangle", "curve-style": "unbundled-bezier", "control-point-step-size": 48, opacity: 0.68 } },
          { selector: "edge.showLabel", style: { label: "data(label)", "font-size": 11, color: "#26332e", "text-background-color": "#fffdf7", "text-background-opacity": 1, "text-background-padding": "4px", "text-border-color": "#d8ddd9", "text-border-width": 1, opacity: 1, "z-index": 10 } },
          { selector: ":selected", style: { "background-color": "#e56d3e", "line-color": "#e56d3e", "target-arrow-color": "#e56d3e" } },
        ],
      });
      cy.on("tap", "node", (event) => {
        const node = event.target;
        const neighbors = node.connectedEdges();
        cy.elements().removeClass("dimmed");
        setSelection(`${node.data("label")} · ${neighbors.length} 条关系${node.data("summary") ? ` · ${node.data("summary")}` : ""}`);
      });
      cy.on("tap", "edge", (event) => {
        const edge = event.target;
        cy.edges().removeClass("showLabel");
        edge.addClass("showLabel");
        setSelection(`${edge.source().data("label")} — ${edge.data("label")} → ${edge.target().data("label")} · ${edge.data("claims")} 条 Claims`);
      });
      cy.on("mouseover", "edge", (event) => event.target.addClass("showLabel"));
      cy.on("mouseout", "edge", (event) => { if (!event.target.selected()) event.target.removeClass("showLabel"); });
      instance = cy;
    });
    return () => { disposed = true; instance?.destroy(); };
  }, [elements]);

  if (!nodes.length && !edges.length) return <p className="emptyPanel">报告中没有足够的引用支持来生成人物关系。</p>;
  return <div className="interactiveViz"><div ref={target} className="cytoscapeCanvas"/><p className="vizSelection">{selection}</p></div>;
}
