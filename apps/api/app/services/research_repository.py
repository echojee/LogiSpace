from __future__ import annotations
import os, sqlite3
from pathlib import Path
from threading import RLock
from logispace_domain.models_v3 import JobV3

_ROOT=Path(os.getenv("LOGISPACE_RUNTIME_DIR",Path(__file__).resolve().parents[4]/"data"/"runtime")); _DB=_ROOT/"logispace-v03.sqlite3"; _LOCK=RLock()
SCHEMA="""
CREATE TABLE IF NOT EXISTS research_jobs(job_id TEXT PRIMARY KEY,work_id TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS research_job_events(job_id TEXT NOT NULL,sequence INTEGER NOT NULL,status TEXT NOT NULL,detail TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(job_id,sequence));
CREATE TABLE IF NOT EXISTS search_hits(job_id TEXT NOT NULL,url TEXT NOT NULL,title TEXT NOT NULL,snippet TEXT NOT NULL,provider TEXT NOT NULL,score REAL NOT NULL,query TEXT NOT NULL,PRIMARY KEY(job_id,url));
CREATE TABLE IF NOT EXISTS source_documents(source_id TEXT PRIMARY KEY,job_id TEXT NOT NULL,url TEXT NOT NULL,title TEXT NOT NULL,source_type TEXT NOT NULL,credibility REAL NOT NULL);
CREATE TABLE IF NOT EXISTS source_snapshots(snapshot_id TEXT PRIMARY KEY,job_id TEXT NOT NULL,source_id TEXT NOT NULL,url TEXT NOT NULL,content_hash TEXT NOT NULL UNIQUE,content_path TEXT NOT NULL,fetch_status TEXT NOT NULL,captured_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence_spans(evidence_id TEXT PRIMARY KEY,job_id TEXT NOT NULL,snapshot_id TEXT NOT NULL,locator TEXT NOT NULL,quote TEXT NOT NULL,relevance_score REAL NOT NULL);
CREATE TABLE IF NOT EXISTS claims(claim_id TEXT PRIMARY KEY,job_id TEXT NOT NULL,section TEXT NOT NULL,text TEXT NOT NULL,support_status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS knowledge_proposals(proposal_id TEXT PRIMARY KEY,job_id TEXT NOT NULL,operation TEXT NOT NULL,payload TEXT NOT NULL,review_status TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON research_jobs(status); CREATE INDEX IF NOT EXISTS idx_events_job ON research_job_events(job_id,sequence);
"""
def connect():
    _ROOT.mkdir(parents=True,exist_ok=True); db=sqlite3.connect(_DB,timeout=10); db.executescript(SCHEMA); return db
def save(job:JobV3,detail:str="state checkpoint"):
    with _LOCK,connect() as db:
        db.execute("INSERT INTO research_jobs VALUES(?,?,?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET status=excluded.status,payload=excluded.payload,updated_at=excluded.updated_at",(job.job_id,job.work.work_id,job.status,job.model_dump_json(),job.created_at.isoformat(),job.updated_at.isoformat()))
        seq=db.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM research_job_events WHERE job_id=?",(job.job_id,)).fetchone()[0]
        db.execute("INSERT INTO research_job_events VALUES(?,?,?,?,datetime('now'))",(job.job_id,seq,job.status,detail))
        for hit in job.search_hits:
            db.execute("INSERT OR REPLACE INTO search_hits VALUES(?,?,?,?,?,?,?)",(job.job_id,hit.url,hit.title,hit.snippet,hit.provider,hit.score,hit.query))
        for source in job.sources:
            db.execute("INSERT OR REPLACE INTO source_documents VALUES(?,?,?,?,?,?)",(source.source_id,job.job_id,source.url,source.title,source.source_type,source.credibility))
        for snapshot in job.snapshots:
            db.execute("INSERT OR REPLACE INTO source_snapshots VALUES(?,?,?,?,?,?,?,?)",(snapshot.snapshot_id,job.job_id,snapshot.source_id,snapshot.url,snapshot.content_hash,snapshot.content_path,snapshot.fetch_status,snapshot.captured_at.isoformat()))
        for evidence in job.evidence:
            import json
            db.execute("INSERT OR REPLACE INTO evidence_spans VALUES(?,?,?,?,?,?)",(evidence.evidence_id,job.job_id,evidence.snapshot_id,json.dumps(evidence.locator),evidence.quote,evidence.relevance_score))
        for claim in job.claims:
            db.execute("INSERT OR REPLACE INTO claims VALUES(?,?,?,?,?)",(claim.claim_id,job.job_id,claim.section,claim.text,claim.support_status))
        for proposal in job.proposals:
            db.execute("INSERT OR REPLACE INTO knowledge_proposals VALUES(?,?,?,?,?)",(proposal.proposal_id,job.job_id,proposal.operation,json.dumps(proposal.payload),proposal.review_status))
def load(job_id:str)->JobV3|None:
    with connect() as db: row=db.execute("SELECT payload FROM research_jobs WHERE job_id=?",(job_id,)).fetchone()
    return JobV3.model_validate_json(row[0]) if row else None
def list_jobs()->list[JobV3]:
    with connect() as db: rows=db.execute("SELECT payload FROM research_jobs ORDER BY updated_at DESC").fetchall()
    return [JobV3.model_validate_json(r[0]) for r in rows]
def events(job_id:str)->list[dict]:
    with connect() as db: rows=db.execute("SELECT sequence,status,detail,created_at FROM research_job_events WHERE job_id=? ORDER BY sequence",(job_id,)).fetchall()
    return [dict(zip(("sequence","status","detail","created_at"),r)) for r in rows]


if os.getenv("DATABASE_URL","").startswith(("postgres://","postgresql://")):
    from app.services import postgres_research_repository as _postgres
    save=_postgres.save
    load=_postgres.load
    list_jobs=_postgres.list_jobs
    events=_postgres.events
