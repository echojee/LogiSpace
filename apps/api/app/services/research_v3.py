from __future__ import annotations
import hashlib,json,os,re,time
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from threading import Thread
from urllib.parse import quote,urlparse
from urllib.request import Request,urlopen
from uuid import uuid4
from fastapi import HTTPException
from logispace_domain import dossiers as dossiers
from logispace_domain.models import DossierEntity,Work,WorkDossier
from logispace_domain.models_v3 import *
from app.services import research_repository as repo
from app.services.search_providers import SearchHit, search as web_search
from app.services.retrieval import chunk_snapshot, rank
from app.services.research_extractor import extract as extract_batch, verify as verify_batch
from app.services.llm import gateway
from app.services.research_synthesis import build_package, build_report

DATA=Path(__file__).resolve().parents[4]/"data"; OBJECTS=DATA/"runtime"/"objects"
TYPES={"characters":{"Character","CollectiveActor"},"relationships":set(),"locations_objects":{"Location","Object"},"timeline_truth":{"Event"},"timeline_investigation":{"Reveal"},"timeline_narrative":{"NarrativeUnit"},"clues_testimony":{"Clue","Testimony"},"crime_execution":{"CrimeExecution"},"murder_method":{"MurderMethod"},"trick_misdirection":{"Trick"},"solution":{"SolutionModel"},"creation_background":{"CreationBackground"},"adaptations":{"Adaptation"},"controversies":{"Controversy"}}
QUESTIONS={s:f"What verified information belongs in {s}?" for s in SECTIONS}
class TextHTML(HTMLParser):
 def __init__(self): super().__init__();self.parts=[];self.skip=0
 def handle_starttag(self,t,a):
  if t in {"script","style","nav","footer","aside"}:self.skip+=1
 def handle_endtag(self,t):
  if t in {"script","style","nav","footer","aside"} and self.skip:self.skip-=1
 def handle_data(self,d):
  if not self.skip and d.strip():self.parts.append(d.strip())
def baseline(work:Work)->WorkDossier:return WorkDossier(work=work,dossier_version="0.0.0",entities=[],relations=[],golden_questions=[],revision_findings=[])
def coverage(d:WorkDossier)->list[CoverageV3]:
 out=[CoverageV3(section="identity",status="needs_evidence",structure_count=1,knowledge_gaps=["Identity needs external evidence"])]
 for section in SECTIONS[1:]:
  expected=TYPES[section]; count=len(d.relations) if section=="relationships" else sum(e.entity_type in expected for e in d.entities)
  out.append(CoverageV3(section=section,status="needs_evidence" if count else "missing",structure_count=count,knowledge_gaps=[] if count else [f"{section} has no structured content"]))
 return out
def make_plan(job:JobV3)->ResearchPlanV3:
 items=[]
 for c in job.coverage:
  if c.status not in {"sufficient","not_applicable"}:
   title=job.work.canonical_title; q=QUESTIONS[c.section]
   items.append(PlanItemV3(section=c.section,question=q,priority=5 if c.section in {"identity","characters","timeline_truth","clues_testimony","solution"} else 3,queries=[f'"{title}"',f'"{title}" {c.section}',f'"{title}" analysis'],preferred_sources=["primary_text","scholarly_analysis"],minimum_sources=2))
 enabled=[i for i in items if i.enabled]; queries=min(job.budget.max_queries,sum(min(len(i.queries),job.budget.max_queries_per_section) for i in enabled))
 return ResearchPlanV3(items=items,estimated_queries=queries,estimated_sources=min(job.budget.max_sources,queries*2),estimated_model_tokens=min(job.budget.max_model_tokens,max(4000,len(enabled)*2500)))
def create(req:ResearchJobCreateV3)->JobV3:
 if bool(req.work_id)==bool(req.work):raise HTTPException(422,"Provide exactly one of work_id or work")
 d=dossiers.get_dossier(req.work_id) if req.work_id else None
 if req.work_id and d is None:raise HTTPException(404,"Work not found")
 work=d.work if d else req.work; base=d or baseline(work); target="0.1.0" if base.dossier_version=="0.0.0" else _next(base.dossier_version)
 job=JobV3(job_id=f"research_{uuid4().hex[:12]}",work=work,base_version=base.dossier_version,target_version=target,status="inventorying",budget=req.budget,source_urls=req.source_urls)
 job.coverage=coverage(base);job.status="planning";job.plan=make_plan(job);job.status="awaiting_plan_approval";repo.save(job,"Plan ready for approval");return job
def _next(v):a,b,_=map(int,v.split("."));return f"{a}.{b+1}.0"
def get(j):
 x=repo.load(j)
 if not x:raise HTTPException(404,"Research job not found")
 return x
def _dispatch(job_id:str):
 if os.getenv("LOGISPACE_INLINE_WORKER","true").lower() in {"1","true","yes"}:Thread(target=run,args=(job_id,),daemon=True).start()

def approve(j,req:PlanApprovalV3):
 job=get(j)
 if job.status!="awaiting_plan_approval":raise HTTPException(409,"Plan is not awaiting approval")
 if req.items is not None:job.plan.items=req.items
 if not any(i.enabled for i in job.plan.items):raise HTTPException(422,"Enable at least one plan item")
 job.plan=make_plan(job.model_copy(update={"coverage":[c for c in job.coverage if any(i.enabled and i.section==c.section for i in job.plan.items)]})) if req.items is None else job.plan
 job.plan.approved=True;job.status="searching";job.updated_at=datetime.utcnow();repo.save(job,"Plan approved");_dispatch(j);return job
def search_urls(job,item):
 if job.source_urls:return job.source_urls
 query=item.queries[0]
 for host in ("zh.wikipedia.org","en.wikipedia.org"):
  url=f"https://{host}/w/api.php?action=opensearch&limit=5&format=json&search="+quote(query)
  for attempt in range(2):
   try:
    data=json.loads(urlopen(Request(url,headers={"User-Agent":"LogiSpace/0.3"}),timeout=15).read())
    if data[3]:return data[3]
   except Exception as e:
    job.errors.append(f"search {host} attempt {attempt+1}: {e}")
 return []
def fetch(job,url,index):
 sid=f"source_{job.job_id}_{index}"
 last_error=None
 for attempt in range(2):
  try:
   raw=urlopen(Request(url,headers={"User-Agent":"LogiSpace/0.3"}),timeout=20).read(2_000_000)
   if raw.startswith(b"%PDF"):
    import pypdf,io
    text="\n".join(p.extract_text() or "" for p in pypdf.PdfReader(io.BytesIO(raw)).pages)
   else:
    parser=TextHTML();parser.feed(raw.decode("utf-8","replace"));text="\n".join(parser.parts)
   text=re.sub(r"\n{3,}","\n\n",text).strip();h=hashlib.sha256(text.encode()).hexdigest();OBJECTS.mkdir(parents=True,exist_ok=True);path=OBJECTS/f"{h}.txt"
   cached=path.exists()
   if not cached:path.write_text(text,encoding="utf-8")
   return SnapshotV3(snapshot_id=f"snap_{h[:16]}",source_id=sid,url=url,content_hash=h,content_path=str(path),content=text,fetch_status="cached" if cached else "fetched")
  except Exception as e:
   last_error=e;job.errors.append(f"read retry {attempt+1} for {url}: {e}")
 return SnapshotV3(snapshot_id=f"snap_failed_{uuid4().hex[:8]}",source_id=sid,url=url,content_hash=hashlib.sha256((url+str(last_error)).encode()).hexdigest(),content_path="",fetch_status="failed",error=str(last_error))
def run(j):
 job=get(j)
 try:
  enabled=sorted((i for i in job.plan.items if i.enabled),key=lambda x:-x.priority)
  hits=[]
  if job.source_urls:
   hits=[SearchHit(u,u.rsplit("/",1)[-1] or u,"","provided",1.0) for u in job.source_urls]
  else:
   seen_queries=set()
   for item in enabled:
    for query_text in item.queries[:job.budget.max_queries_per_section]:
     if job.usage.queries>=job.budget.max_queries:break
     if query_text in seen_queries:continue
     seen_queries.add(query_text)
     found,errors=web_search(query_text,job.work.canonical_title,job.work.media_type.value,job.budget.max_search_hits_per_query)
     job.errors.extend(errors);job.usage.queries+=1;selected=found[:job.budget.max_pages_to_fetch_per_query];hits.extend(selected);job.search_hits.extend(SearchHitV3(url=h.url,title=h.title,snippet=h.snippet,provider=h.provider,score=h.score,query=query_text) for h in selected)
    if job.usage.queries>=job.budget.max_queries:break
  unique={hit.url:hit for hit in sorted(hits,key=lambda x:x.score,reverse=True) if hit.score>=.4 or hit.provider=="provided"}
  job.usage.search_rounds=1;job.status="reading";repo.save(job,"Ranked search funnel complete; reading source bodies")
  for idx,hit in enumerate(list(unique.values())[:job.budget.max_sources]):
   latest=repo.load(job.job_id)
   if latest and latest.status in {"paused","cancelled"}:return
   snap=fetch(job,hit.url,idx);job.snapshots.append(snap);job.sources.append(SourceV3(source_id=snap.source_id,url=hit.url,title=hit.title,source_type=hit.provider,credibility=hit.score if snap.fetch_status!="failed" else .1));job.usage.pages_fetched+=1
  good=[snap for snap in job.snapshots if snap.fetch_status!="failed" and snap.content]
  job.usage.sources=len(good)
  if not good:
   job.status="partially_completed";job.errors.append("No readable source body; preserved search results and checkpoints");repo.save(job,"No readable sources");return
  chunks=[chunk for snap in good for chunk in chunk_snapshot(snap)]
  ranked={item.section:rank(chunks,item.question+" "+" ".join([job.work.canonical_title,*job.work.aliases]),job.budget.max_evidence_chunks_per_question) for item in enabled}
  if not any(ranked.values()):
   job.status="partially_completed";job.errors.append("No source chunks matched the approved research questions");repo.save(job,"Retrieval produced no candidates");return
  job.status="extracting";repo.save(job,"BM25 retrieval complete; starting batched extraction")
  if not gateway.available:
   job.status="partially_completed";job.errors.append("OPENAI_API_KEY is required for grounded Evidence and Claim extraction");repo.save(job,"Source research preserved; model extraction unavailable");return
  for offset in range(0,len(enabled),5):
   if job.usage.model_calls>=job.budget.max_model_calls or job.usage.model_tokens>=job.budget.max_model_tokens:break
   batch=enabled[offset:offset+5];evidence,claims,usage=extract_batch(job.work.canonical_title,job.work.media_type.value,batch,ranked)
   job.evidence.extend(evidence);job.claims.extend(claims);job.usage.model_calls+=usage["model_calls"];job.usage.input_tokens+=usage["input_tokens"];job.usage.output_tokens+=usage["output_tokens"];job.usage.model_tokens=job.usage.input_tokens+job.usage.output_tokens
  job.status="verifying";repo.save(job,"Exact-quote validation complete; verifying claims")
  if job.claims and job.usage.model_calls<job.budget.max_model_calls:
   verified,verify_usage,notes=verify_batch(job.claims,job.evidence);job.claims=verified;job.errors.extend(notes);job.usage.model_calls+=verify_usage["model_calls"];job.usage.input_tokens+=verify_usage["input_tokens"];job.usage.output_tokens+=verify_usage["output_tokens"];job.usage.model_tokens=job.usage.input_tokens+job.usage.output_tokens
  snapshots={snap.snapshot_id:snap for snap in good};valid_evidence={ev.evidence_id:ev for ev in job.evidence if ev.snapshot_id in snapshots and ev.quote in snapshots[ev.snapshot_id].content}
  job.evidence=list(valid_evidence.values());job.claims=[claim for claim in job.claims if claim.support_status!="unsupported" and claim.evidence_ids and all(eid in valid_evidence for eid in claim.evidence_ids)]
  base=dossiers.get_dossier(job.work.work_id) or baseline(job.work)
  if job.claims:
   job.status="proposing";job.report=build_report(job.work,job.target_version,job.claims);job.knowledge_package=build_package(job.work,job.target_version,base,job.claims);repo.save(job,"Readable report and knowledge package generated")
  for claim in job.claims:
   operation="flag_conflict" if claim.support_status=="conflicted" else "add_claim"
   payload={"entity_type":"Claim","name":claim.text[:80],"summary":claim.text,"attributes":{"claim_id":claim.claim_id,"section":claim.section,"claim_type":claim.claim_type,"media_version":claim.media_version,"evidence_ids":claim.evidence_ids,"support_status":claim.support_status}}
   job.proposals.append(ProposalV3(proposal_id=f"proposal_{uuid4().hex[:10]}",operation=operation,target_section=claim.section,summary=claim.text[:180],payload=payload,claim_ids=[claim.claim_id],evidence_ids=claim.evidence_ids))
  for coverage_item in job.coverage:
   section_evidence=[e for e in job.evidence if e.section==coverage_item.section];source_ids={e.source_id for e in section_evidence};coverage_item.evidence_count=len(section_evidence);coverage_item.source_count=len(source_ids);coverage_item.average_source_quality=sum(s.credibility for s in job.sources if s.source_id in source_ids)/max(1,len(source_ids));coverage_item.status="sufficient" if any(c.section==coverage_item.section and c.support_status=="supported" for c in job.claims) else "needs_evidence"
  if not job.claims:
   exhausted=job.usage.model_calls>=job.budget.max_model_calls or job.usage.model_tokens>=job.budget.max_model_tokens;job.status="budget_exhausted" if exhausted else "partially_completed";job.errors.append("No verified claims were produced; source and retrieval checkpoints were preserved");repo.save(job,"No publishable claims");return
  draft=base.model_copy(deep=True);draft.dossier_version=job.target_version;job.draft=draft;job.diff={"added_entities":0,"added_relations":0,"added_claims":len(job.claims),"conflicts":sum(c.support_status=="conflicted" for c in job.claims)};job.status="needs_review";repo.save(job,"Grounded claims verified; human review required")
 except Exception as error:
  job.status="partially_completed";job.errors.append(str(error));repo.save(job,"Research stopped with recoverable partial results")
def review(j,r:ReviewV3):
 job=get(j)
 for p in job.proposals:p.review_status="approved" if p.proposal_id in r.approved_proposal_ids else "rejected" if p.proposal_id in r.rejected_proposal_ids else p.review_status
 repo.save(job,"Proposal review saved");return job
def publish(j):
 job=get(j)
 if job.status!="needs_review" or not job.draft:raise HTTPException(409,"Job is not publishable")
 approved=[p for p in job.proposals if p.review_status=="approved"]
 if not approved:raise HTTPException(409,"Approve at least one proposal")
 evidence={e.evidence_id:e for e in job.evidence};snaps={s.snapshot_id:s for s in job.snapshots}
 for p in approved:
  if not p.payload:raise HTTPException(409,"Proposal payload cannot be empty")
  for eid in p.evidence_ids:
   ev=evidence.get(eid);snap=snaps.get(ev.snapshot_id) if ev else None
   if not ev or not snap or ev.quote not in snap.content:raise HTTPException(409,"Proposal has no verifiable evidence")
  if p.operation=="add_claim":job.draft.entities.append(DossierEntity(entity_id=p.payload["attributes"]["claim_id"],entity_type="Claim",name=p.payload["name"],summary=p.payload["summary"],attributes=p.payload["attributes"]))
 approved_claim_ids={claim_id for proposal in approved for claim_id in proposal.claim_ids};approved_claims=[claim for claim in job.claims if claim.claim_id in approved_claim_ids];base=dossiers.get_dossier(job.work.work_id) or baseline(job.work);job.report=build_report(job.work,job.target_version,approved_claims);job.knowledge_package=build_package(job.work,job.target_version,base,approved_claims)
 job.diff["added_entities"]=len(approved);_write_dossier(job);job.status="published";repo.save(job,"Dossier published");return job
def _write_dossier(job):
 root=DATA/"works"/job.work.work_id;v=root/"versions"/job.target_version;v.mkdir(parents=True,exist_ok=True);(v/"dossier.json").write_text(job.draft.model_dump_json(indent=2),encoding="utf-8")
 if job.report:(v/"report.json").write_text(job.report.model_dump_json(indent=2),encoding="utf-8")
 if job.knowledge_package:(v/"knowledge-package.json").write_text(job.knowledge_package.model_dump_json(indent=2),encoding="utf-8")
 manifest={"work_id":job.work.work_id,"current_dossier_version":job.target_version,"ontology_version":job.draft.ontology_version,"dossier_versions":[job.target_version]};mp=root/"manifest.json"
 if mp.exists():manifest=json.loads(mp.read_text(encoding="utf-8"));manifest["current_dossier_version"]=job.target_version;manifest.setdefault("dossier_versions",[]).append(job.target_version) if job.target_version not in manifest.setdefault("dossier_versions",[]) else None
 mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8");cat=json.loads((DATA/"catalog.json").read_text(encoding="utf-8"));
 if not any(x["work_id"]==job.work.work_id for x in cat["works"]):cat["works"].append({"work_id":job.work.work_id,"manifest":f"works/{job.work.work_id}/manifest.json"});(DATA/"catalog.json").write_text(json.dumps(cat,ensure_ascii=False,indent=2),encoding="utf-8")
 dossiers._catalog.cache_clear();dossiers.get_dossier.cache_clear()
