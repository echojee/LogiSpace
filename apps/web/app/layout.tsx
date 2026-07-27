import Link from "next/link";
import "./globals.css";

export const metadata = {
  title: "LogiSpace｜个人悬疑知识库",
  description: "检索推理作品中的人物关系、时间线、诡计与杀人手法",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="zh-CN"><body><header className="siteHeader"><Link href="/" className="logo"><span>LS</span>LogiSpace</Link><nav><Link href="/chat">对话</Link><Link href="/library">个人悬疑知识库</Link></nav></header>{children}<footer className="siteFooter"><span>LogiSpace · WorkDossier v0</span><span>三个独立作品数据库</span></footer></body></html>;
}