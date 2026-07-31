import Link from "next/link";
import "./globals.css";
import "./v02.css";
export const metadata={title:"LogiSpace｜悬疑作品知识空间",description:"快速问答与作品级深度研究，让 WorkDossier 持续成长。"};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="zh-CN"><body><header className="siteHeader"><Link href="/" className="logo"><span>LS</span>LogiSpace</Link><nav><Link href="/chat">快速对话</Link><Link href="/research">深度研究</Link><Link href="/library">知识库</Link></nav></header>{children}<footer className="siteFooter"><span>LogiSpace · WorkDossier 0.3</span><span>对话消费知识 · 研究生产知识</span></footer></body></html>}
