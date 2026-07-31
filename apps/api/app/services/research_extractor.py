from __future__ import annotations
import json
from uuid import uuid4
from app.services.llm import gateway
from app.services.retrieval import RankedChunk
from logispace_domain.models_v3 import ClaimV3,EvidenceV3,PlanItemV3

def extract(work_title:str,media_type:str,items:list[PlanItemV3],ranked:dict[str,list[RankedChunk]])->tuple[list[EvidenceV3],list[ClaimV3],dict[str,int]]:
    if not gateway.available:return [],[],{"input_tokens":0,"output_tokens":0,"model_calls":0}
    chunk_map={r.chunk.chunk_id:r for values in ranked.values() for r in values}
    payload={"work":{"title":work_title,"media_type":media_type},"questions":[{"section":i.section,"question":i.question,"chunks":[{"chunk_id":r.chunk.chunk_id,"source_id":r.chunk.source_id,"text":r.chunk.content} for r in ranked.get(i.section,[])]} for i in items if ranked.get(i.section)]}
    instructions='''Extract source-grounded knowledge for a WorkDossier. Return only a JSON array. Each item must contain section, claim_text, claim_type (fact|inference|interpretation), and evidence: [{chunk_id, quote}]. quote MUST be an exact contiguous substring of that chunk. Keep works and adaptations separate. Do not use prior knowledge. Omit unsupported claims. Prefer concise claims and at most 3 claims per section.'''
    data,result=gateway.respond_json(instructions=instructions,input_text=json.dumps(payload,ensure_ascii=False),research=True)
    if not isinstance(data,list):raise RuntimeError("Extraction response must be a JSON array")
    evidence=[];claims=[]
    for raw in data:
        if not isinstance(raw,dict) or raw.get("section") not in {i.section for i in items}:continue
        linked=[];source_ids=set()
        for cited in raw.get("evidence",[]):
            ranked_chunk=chunk_map.get(cited.get("chunk_id"));quote=cited.get("quote","")
            if not ranked_chunk or not quote or quote not in ranked_chunk.chunk.content:continue
            chunk=ranked_chunk.chunk;ev=EvidenceV3(evidence_id=f"ev_{uuid4().hex[:10]}",snapshot_id=chunk.snapshot_id,source_id=chunk.source_id,section=raw["section"],locator=chunk.locator|{"chunk_id":chunk.chunk_id},quote=quote,relevance_score=min(1,ranked_chunk.score/(ranked_chunk.score+1)))
            evidence.append(ev);linked.append(ev.evidence_id);source_ids.add(ev.source_id)
        text=str(raw.get("claim_text","")).strip()
        if not text or not linked:continue
        claim_type=raw.get("claim_type","fact") if raw.get("claim_type") in {"fact","inference","interpretation"} else "fact"
        high_risk=raw["section"] in {"crime_execution","murder_method","solution","controversies"}
        support="supported" if (len(source_ids)>=2 or not high_risk) and claim_type=="fact" else "partially_supported"
        claims.append(ClaimV3(claim_id=f"claim_{uuid4().hex[:10]}",section=raw["section"],text=text,claim_type=claim_type,evidence_ids=linked,support_status=support,media_version=media_type))
    return evidence,claims,{"input_tokens":result.input_tokens,"output_tokens":result.output_tokens,"model_calls":1}


def verify(claims:list[ClaimV3],evidence:list[EvidenceV3])->tuple[list[ClaimV3],dict[str,int],list[str]]:
    if not claims:return [],{"input_tokens":0,"output_tokens":0,"model_calls":0},[]
    if not gateway.available:return [],{"input_tokens":0,"output_tokens":0,"model_calls":0},["Model unavailable for final Claim verification"]
    by_id={item.evidence_id:item for item in evidence}
    payload=[{"claim_id":claim.claim_id,"section":claim.section,"text":claim.text,"claim_type":claim.claim_type,"evidence":[{"quote":by_id[eid].quote,"source_id":by_id[eid].source_id} for eid in claim.evidence_ids if eid in by_id]} for claim in claims]
    instructions="""Verify whether each claim is supported by its quoted evidence. Return only a JSON array with claim_id, status (supported|partially_supported|inferred|conflicted|unsupported), and reason. Mark version mixing or contradictory evidence conflicted. Mark conclusions exceeding the quote inferred or unsupported. Do not add claims."""
    data,result=gateway.respond_json(instructions=instructions,input_text=json.dumps(payload,ensure_ascii=False),research=True)
    decisions={item.get("claim_id"):item for item in data if isinstance(item,dict)} if isinstance(data,list) else {}
    accepted=[];notes=[];allowed={"supported","partially_supported","inferred","conflicted","unsupported"}
    for claim in claims:
        decision=decisions.get(claim.claim_id);status=decision.get("status") if decision else "unsupported"
        if status not in allowed:status="unsupported"
        claim.support_status=status
        if decision and decision.get("reason"):notes.append(f"{claim.claim_id}: {decision['reason']}")
        if status!="unsupported":accepted.append(claim)
    return accepted,{"input_tokens":result.input_tokens,"output_tokens":result.output_tokens,"model_calls":1},notes
