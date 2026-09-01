import type { Metadata } from "next";
import { headers } from "next/headers";
import Link from "next/link";
import "./globals.css";
import "./v02.css";
import "./knowledge.css";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host") ?? "127.0.0.1:3000";
  const protocol = requestHeaders.get("x-forwarded-proto") ?? (host.startsWith("localhost") || host.startsWith("127.0.0.1") ? "http" : "https");
  const image = `${protocol}://${host}/og.png`;
  return {
    title: "LogiSpace 0.4｜可验证的悬疑研究空间",
    description: "Supervisor、Search Agent 与 Verifier 协作，把调查过程沉淀为可追溯的 WorkDossier。",
    openGraph: {
      title: "LogiSpace 0.4",
      description: "把调查过程，变成可验证的知识。",
      images: [{ url: image, width: 1672, height: 941, alt: "LogiSpace 0.4 可验证研究工作台" }],
    },
    twitter: {
      card: "summary_large_image",
      title: "LogiSpace 0.4",
      description: "把调查过程，变成可验证的知识。",
      images: [image],
    },
  };
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="zh-CN"><body>
    <header className="siteHeader">
      <Link href="/" className="logo"><span>LS</span>LogiSpace</Link>
      <nav><Link href="/chat">快速对话</Link><Link href="/research">Agent 深度研究</Link><Link href="/library">知识库</Link></nav>
    </header>
    {children}
    <footer className="siteFooter"><span>LogiSpace · WorkDossier 0.4</span><span>有限自主 · 证据可溯 · 人工发布</span></footer>
  </body></html>;
}
