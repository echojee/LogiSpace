import Link from "next/link";
import { ArrowRight, BookOpen, MessageCircle } from "lucide-react";

export default function Home() {
  return <main className="home"><section className="homeHero"><p className="eyebrow">PERSONAL MYSTERY KNOWLEDGE BASE</p><h1>从一次提问，进入作品的推理结构。</h1><p>检索《嫌疑人X的献身》《罗杰疑案》《东方快车谋杀案》中的人物关系、时间线、诡计与杀人手法。</p></section><section className="entryGrid"><Link href="/chat" className="entryCard orange"><MessageCircle/><small>01 / ASK</small><h2>对话检索</h2><p>用自然语言提问，答案来自结构化 WorkDossier，并附带证据实体与知识页面链接。</p><span>开始提问 <ArrowRight size={16}/></span></Link><Link href="/library" className="entryCard green"><BookOpen/><small>02 / EXPLORE</small><h2>个人悬疑知识库</h2><p>从作品集或诡计集进入，浏览人物关系、时间线、诡计和杀人手法。</p><span>进入知识库 <ArrowRight size={16}/></span></Link></section></main>;
}