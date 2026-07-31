from __future__ import annotations
import json,os
from logispace_domain.models_v3 import JobV3
URL=os.environ["DATABASE_URL"]
def connect():
 import psycopg
 return psycopg.connect(URL)
def save(job:JobV3,detail:str="state checkpoint"):
 with connect() as db,db.cursor() as cur:
  cur.execute("INSERT INTO works(work_id,canonical_title,media_type,release_year) VALUES(%s,%s,%s,%s) ON CONFLICT(work_id) DO UPDATE SET canonical_title=excluded.canonical_title,media_type=excluded.media_type,release_year=excluded.release_year",(job.work.work_id,job.work.canonical_title,job.work.media_type.value,job.work.release_year))
  cur.execute("INSERT INTO research_jobs(job_id,work_id,status,report_schema_version,payload,created_at,updated_at) VALUES(%s,%s,%s,'0.3',%s::jsonb,%s,%s) ON CONFLICT(job_id) DO UPDATE SET status=excluded.status,payload=excluded.payload,updated_at=excluded.updated_at",(job.job_id,job.work.work_id,job.status,job.model_dump_json(),job.created_at,job.updated_at))
  cur.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM research_job_steps WHERE job_id=%s",(job.job_id,));seq=cur.fetchone()[0]
  cur.execute("INSERT INTO research_job_steps(job_id,sequence,status,detail) VALUES(%s,%s,%s,%s)",(job.job_id,seq,job.status,detail))
  for source in job.sources:
   cur.execute("INSERT INTO source_documents(source_id,job_id,url,title,source_type,credibility,captured_text) VALUES(%s,%s,%s,%s,%s,%s,'') ON CONFLICT(source_id) DO UPDATE SET title=excluded.title,credibility=excluded.credibility",(source.source_id,job.job_id,source.url,source.title,source.source_type,source.credibility))
  for snapshot in job.snapshots:
   if snapshot.fetch_status!="failed":cur.execute("INSERT INTO source_snapshots(snapshot_id,source_id,content_hash,object_path,fetch_status,captured_at) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(snapshot_id) DO NOTHING",(snapshot.snapshot_id,snapshot.source_id,snapshot.content_hash,snapshot.content_path,snapshot.fetch_status,snapshot.captured_at))
  for evidence in job.evidence:
   cur.execute("INSERT INTO evidence_spans(evidence_id,snapshot_id,locator,quote,relevance_score) VALUES(%s,%s,%s::jsonb,%s,%s) ON CONFLICT(evidence_id) DO NOTHING",(evidence.evidence_id,evidence.snapshot_id,json.dumps(evidence.locator),evidence.quote,evidence.relevance_score))
  for claim in job.claims:
   cur.execute("INSERT INTO claims(claim_id,work_id,section,text,importance,spoiler_level,support_status,job_id,claim_type,media_version) VALUES(%s,%s,%s,%s,3,%s,%s,%s,%s,%s) ON CONFLICT(claim_id) DO UPDATE SET support_status=excluded.support_status",(claim.claim_id,job.work.work_id,claim.section,claim.text,claim.spoiler_level.value,claim.support_status,job.job_id,claim.claim_type,claim.media_version))
  for proposal in job.proposals:
   cur.execute("INSERT INTO knowledge_proposals(proposal_id,job_id,operation,target_section,payload,review_status) VALUES(%s,%s,%s,%s,%s::jsonb,%s) ON CONFLICT(proposal_id) DO UPDATE SET review_status=excluded.review_status",(proposal.proposal_id,job.job_id,proposal.operation,proposal.target_section,json.dumps(proposal.payload),proposal.review_status))
  if job.draft:cur.execute("INSERT INTO dossier_drafts(job_id,base_version,target_version,dossier,diff) VALUES(%s,%s,%s,%s::jsonb,%s::jsonb) ON CONFLICT(job_id) DO UPDATE SET dossier=excluded.dossier,diff=excluded.diff",(job.job_id,job.base_version,job.target_version,job.draft.model_dump_json(),json.dumps(job.diff)))
def load(job_id:str)->JobV3|None:
 with connect() as db,db.cursor() as cur:cur.execute("SELECT payload FROM research_jobs WHERE job_id=%s",(job_id,));row=cur.fetchone()
 return JobV3.model_validate(row[0]) if row else None
def list_jobs()->list[JobV3]:
 with connect() as db,db.cursor() as cur:cur.execute("SELECT payload FROM research_jobs ORDER BY updated_at DESC");rows=cur.fetchall()
 return [JobV3.model_validate(row[0]) for row in rows]
def events(job_id:str)->list[dict]:
 with connect() as db,db.cursor() as cur:cur.execute("SELECT sequence,status,detail,created_at FROM research_job_steps WHERE job_id=%s ORDER BY sequence",(job_id,));rows=cur.fetchall()
 return [dict(zip(("sequence","status","detail","created_at"),row)) for row in rows]
