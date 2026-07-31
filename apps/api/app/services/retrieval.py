from __future__ import annotations
from dataclasses import dataclass
from math import log
import re
from logispace_domain.models_v3 import SnapshotV3
@dataclass(frozen=True)
class Chunk:
    chunk_id:str;snapshot_id:str;source_id:str;locator:dict;content:str
@dataclass(frozen=True)
class RankedChunk:
    chunk:Chunk;score:float
def tokens(text:str)->list[str]:
    text=text.casefold();out=re.findall(r"[a-z0-9]{2,}",text);zh="".join(re.findall(r"[\u4e00-\u9fff]",text));out.extend(zh[i:i+2] for i in range(max(0,len(zh)-1)));return out
def chunk_snapshot(snapshot:SnapshotV3,min_chars:int=80,max_chars:int=1200)->list[Chunk]:
    paragraphs=[re.sub(r"\s+"," ",x).strip() for x in snapshot.content.splitlines()]
    out=[];buffer=[];start=1;size=0
    def flush(end):
        nonlocal buffer,start,size
        content="\n".join(buffer).strip()
        if len(content)>=min_chars:out.append(Chunk(f"chunk_{snapshot.snapshot_id}_{len(out)}",snapshot.snapshot_id,snapshot.source_id,{"paragraph_start":start,"paragraph_end":end},content))
        buffer=[];size=0
    for number,p in enumerate(paragraphs,1):
        if not p:continue
        if not buffer:start=number
        if size+len(p)>max_chars and buffer:flush(number-1);start=number
        if len(p)>max_chars:
            for offset in range(0,len(p),max_chars):
                part=p[offset:offset+max_chars]
                if len(part)>=min_chars:out.append(Chunk(f"chunk_{snapshot.snapshot_id}_{len(out)}",snapshot.snapshot_id,snapshot.source_id,{"paragraph_start":number,"paragraph_end":number,"char_start":offset},part))
            buffer=[];size=0
        else:buffer.append(p);size+=len(p)
    if buffer:flush(len(paragraphs))
    return out
def rank(chunks:list[Chunk],query:str,limit:int=6)->list[RankedChunk]:
    if not chunks:return []
    docs=[tokens(c.content) for c in chunks];q=tokens(query);avg=sum(map(len,docs))/max(1,len(docs));df={t:sum(t in d for d in docs) for t in set(q)};result=[]
    for chunk,doc in zip(chunks,docs):
        score=0.0
        for term in q:
            tf=doc.count(term);idf=log(1+(len(docs)-df.get(term,0)+.5)/(df.get(term,0)+.5));score+=idf*(tf*2.2)/(tf+1.2*(.25+.75*len(doc)/max(1,avg))) if tf else 0
        if score>0:result.append(RankedChunk(chunk,score))
    return sorted(result,key=lambda x:x.score,reverse=True)[:limit]
