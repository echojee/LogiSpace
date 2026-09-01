"use client";

import { useEffect, useId, useRef, useState } from "react";

export default function MermaidPreview({ source }: { source: string }) {
  const id = useId().replace(/:/g, "_");
  const target = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    async function render() {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "neutral" });
        const result = await mermaid.render(`mermaid_${id}`, source);
        if (active && target.current) target.current.innerHTML = result.svg;
      } catch { if (active) setError("Mermaid 无法渲染，已保留源代码供检查。"); }
    }
    void render();
    return () => { active = false; };
  }, [id, source]);
  return <div className="mermaidPreview">{error && <p className="errorText">{error}</p>}<div ref={target}/><details><summary>查看 Mermaid 源码</summary><pre>{source}</pre></details></div>;
}
