from __future__ import annotations
from dataclasses import dataclass
from html.parser import HTMLParser
import json,re
from urllib.parse import parse_qs,quote,urlparse,unquote
from urllib.request import Request,urlopen

@dataclass(frozen=True)
class SearchHit:
    url:str; title:str; snippet:str; provider:str; score:float=0.0
class _DDG(HTMLParser):
    def __init__(self):super().__init__();self.hits=[];self._href=None;self._title=[];self._snippet=[];self._in_title=False;self._in_snippet=False
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs);classes=set(attrs.get("class","").split())
        if tag=="a" and "result__a" in classes:self._href=attrs.get("href");self._title=[];self._in_title=True
        if "result__snippet" in classes:self._snippet=[];self._in_snippet=True
    def handle_endtag(self,tag):
        if tag=="a" and self._in_title:
            self._in_title=False
            if self._href:self.hits.append([self._href," ".join(self._title).strip(),""])
        if self._in_snippet and tag in {"a","div","span"}:
            self._in_snippet=False
            if self.hits:self.hits[-1][2]=" ".join(self._snippet).strip()
    def handle_data(self,data):
        if self._in_title:self._title.append(data)
        if self._in_snippet:self._snippet.append(data)
def _real_url(value:str)->str:
    parsed=urlparse(value)
    if parsed.netloc.endswith("duckduckgo.com"):
        target=parse_qs(parsed.query).get("uddg",[value])[0];return unquote(target)
    return value
def duckduckgo(query:str,limit:int=10,timeout:int=15)->list[SearchHit]:
    req=Request("https://html.duckduckgo.com/html/?q="+quote(query),headers={"User-Agent":"Mozilla/5.0 LogiSpace/0.3"})
    parser=_DDG();parser.feed(urlopen(req,timeout=timeout).read(1_000_000).decode("utf-8","replace"))
    return [SearchHit(_real_url(u),t,s,"duckduckgo") for u,t,s in parser.hits[:limit] if u.startswith(("http://","https://"))]
def wikipedia(query:str,limit:int=5,timeout:int=15)->list[SearchHit]:
    for host in ("zh.wikipedia.org","en.wikipedia.org"):
        url=f"https://{host}/w/api.php?action=opensearch&format=json&limit={limit}&search="+quote(query)
        data=json.loads(urlopen(Request(url,headers={"User-Agent":"LogiSpace/0.3"}),timeout=timeout).read())
        hits=[SearchHit(u,t,s,"wikipedia") for t,s,u in zip(data[1],data[2],data[3])]
        if hits:return hits
    return []
def _terms(text:str)->set[str]:
    text=text.casefold();words=set(re.findall(r"[a-z0-9]{2,}|[\u4e00-\u9fff]{2,}",text))
    chinese="".join(re.findall(r"[\u4e00-\u9fff]",text));words.update(chinese[i:i+2] for i in range(max(0,len(chinese)-1)))
    return words
def score(hit:SearchHit,title:str,media_type:str)->float:
    wanted=_terms(title);hay=_terms(hit.title+" "+hit.snippet);overlap=len(wanted&hay)/max(1,len(wanted));domain=urlparse(hit.url).netloc.lower()
    quality=.2 if any(x in domain for x in ("wikipedia.org","britannica.com","edu","org","gov")) else .05
    penalty=.35 if any(x in hit.url.lower() for x in ("search?","/tag/","/category/")) else 0
    return max(0,min(1,.55*overlap+quality+.1*(media_type in (hit.title+hit.snippet).casefold())-penalty))
def search(query:str,title:str,media_type:str,limit:int=10)->tuple[list[SearchHit],list[str]]:
    errors=[];hits=[]
    for name,provider in (("duckduckgo",duckduckgo),("wikipedia",wikipedia)):
        try:
            hits=provider(query,limit)
            if hits:break
        except Exception as exc:errors.append(f"{name}: {exc}")
    unique={}
    for hit in hits:
        normalized=hit.url.split("#",1)[0].rstrip("/");ranked=SearchHit(normalized,hit.title,hit.snippet,hit.provider,score(hit,title,media_type))
        if normalized not in unique or ranked.score>unique[normalized].score:unique[normalized]=ranked
    return sorted(unique.values(),key=lambda h:h.score,reverse=True)[:limit],errors
