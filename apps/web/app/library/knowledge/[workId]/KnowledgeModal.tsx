"use client";

import { ReactNode, useEffect } from "react";
import { X } from "lucide-react";

export default function KnowledgeModal({ title, children, onClose, wide = false }: { title: string; children: ReactNode; onClose: () => void; wide?: boolean }) {
  useEffect(() => {
    function close(event: KeyboardEvent) { if (event.key === "Escape") onClose(); }
    document.addEventListener("keydown", close);
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", close); document.body.style.overflow = ""; };
  }, [onClose]);
  return <div className="knowledgeModalBackdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><section className={`knowledgeModal ${wide ? "wide" : ""}`} role="dialog" aria-modal="true" aria-label={title}><header><div><p className="eyebrow">KNOWLEDGE VIEW</p><h2>{title}</h2></div><button onClick={onClose} aria-label="关闭"><X/></button></header><div className="knowledgeModalBody">{children}</div></section></div>;
}
