CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS works (
  work_id TEXT PRIMARY KEY,
  canonical_title TEXT NOT NULL,
  media_type TEXT NOT NULL DEFAULT 'unknown',
  release_year INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS work_aliases (
  alias_id BIGSERIAL PRIMARY KEY,
  work_id TEXT NOT NULL REFERENCES works(work_id),
  alias TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS research_jobs (
  job_id TEXT PRIMARY KEY,
  work_id TEXT NOT NULL REFERENCES works(work_id),
  status TEXT NOT NULL,
  report_schema_version TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS source_documents (
  source_id TEXT PRIMARY KEY,
  job_id TEXT REFERENCES research_jobs(job_id),
  url TEXT NOT NULL,
  title TEXT NOT NULL,
  source_type TEXT NOT NULL,
  credibility NUMERIC NOT NULL,
  captured_text TEXT NOT NULL,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS evidence_items (
  evidence_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES source_documents(source_id),
  locator TEXT NOT NULL,
  quote TEXT NOT NULL,
  ontology_type TEXT NOT NULL,
  confidence NUMERIC NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
  claim_id TEXT PRIMARY KEY,
  work_id TEXT NOT NULL REFERENCES works(work_id),
  section TEXT NOT NULL,
  text TEXT NOT NULL,
  importance INTEGER NOT NULL,
  spoiler_level TEXT NOT NULL,
  support_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claim_evidence (
  claim_id TEXT NOT NULL REFERENCES claims(claim_id),
  evidence_id TEXT NOT NULL REFERENCES evidence_items(evidence_id),
  PRIMARY KEY (claim_id, evidence_id)
);

CREATE TABLE IF NOT EXISTS report_versions (
  report_id TEXT PRIMARY KEY,
  work_id TEXT NOT NULL REFERENCES works(work_id),
  schema_version TEXT NOT NULL,
  quality_score NUMERIC,
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_work_states (
  user_id TEXT NOT NULL,
  work_id TEXT NOT NULL REFERENCES works(work_id),
  state TEXT NOT NULL DEFAULT 'unknown',
  rating INTEGER,
  spoiler_level_allowed TEXT NOT NULL DEFAULT 'none',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, work_id)
);

-- LogiSpace 0.3 research workflow
CREATE TABLE IF NOT EXISTS work_external_ids (work_id TEXT NOT NULL REFERENCES works(work_id), provider TEXT NOT NULL, external_id TEXT NOT NULL, PRIMARY KEY(provider, external_id));
CREATE TABLE IF NOT EXISTS work_versions (work_id TEXT NOT NULL REFERENCES works(work_id), version_id TEXT NOT NULL, label TEXT, release_year INTEGER, PRIMARY KEY(work_id, version_id));
ALTER TABLE research_jobs ADD COLUMN IF NOT EXISTS payload JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE research_jobs ADD COLUMN IF NOT EXISTS error_detail TEXT;
CREATE TABLE IF NOT EXISTS research_job_steps (job_id TEXT NOT NULL REFERENCES research_jobs(job_id), sequence INTEGER NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY(job_id, sequence));
CREATE TABLE IF NOT EXISTS research_plans (job_id TEXT PRIMARY KEY REFERENCES research_jobs(job_id), plan JSONB NOT NULL, approved_at TIMESTAMPTZ);
CREATE TABLE IF NOT EXISTS research_questions (question_id BIGSERIAL PRIMARY KEY, job_id TEXT NOT NULL REFERENCES research_jobs(job_id), section TEXT NOT NULL, question TEXT NOT NULL, priority INTEGER NOT NULL, enabled BOOLEAN NOT NULL DEFAULT true);
CREATE TABLE IF NOT EXISTS search_runs (search_run_id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES research_jobs(job_id), query TEXT NOT NULL, provider TEXT NOT NULL, status TEXT NOT NULL, error_detail TEXT);
CREATE TABLE IF NOT EXISTS search_hits (hit_id BIGSERIAL PRIMARY KEY, search_run_id TEXT NOT NULL REFERENCES search_runs(search_run_id), url TEXT NOT NULL, title TEXT NOT NULL, snippet TEXT, score NUMERIC);
CREATE TABLE IF NOT EXISTS source_snapshots (snapshot_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES source_documents(source_id), content_hash TEXT NOT NULL UNIQUE, object_path TEXT NOT NULL, fetch_status TEXT NOT NULL, captured_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS document_chunks (chunk_id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL REFERENCES source_snapshots(snapshot_id), locator JSONB NOT NULL, content TEXT NOT NULL, content_tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED);
CREATE INDEX IF NOT EXISTS document_chunks_fts ON document_chunks USING GIN(content_tsv);
CREATE TABLE IF NOT EXISTS evidence_spans (evidence_id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL REFERENCES source_snapshots(snapshot_id), locator JSONB NOT NULL, quote TEXT NOT NULL, relevance_score NUMERIC NOT NULL CHECK(relevance_score BETWEEN 0 AND 1));
CREATE TABLE IF NOT EXISTS knowledge_proposals (proposal_id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES research_jobs(job_id), operation TEXT NOT NULL, target_section TEXT NOT NULL, payload JSONB NOT NULL CHECK(payload <> '{}'::jsonb), review_status TEXT NOT NULL DEFAULT 'pending');
CREATE TABLE IF NOT EXISTS proposal_reviews (proposal_id TEXT NOT NULL REFERENCES knowledge_proposals(proposal_id), reviewer_id TEXT NOT NULL, decision TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY(proposal_id, reviewer_id));
CREATE TABLE IF NOT EXISTS dossier_drafts (job_id TEXT PRIMARY KEY REFERENCES research_jobs(job_id), base_version TEXT NOT NULL, target_version TEXT NOT NULL, dossier JSONB NOT NULL, diff JSONB NOT NULL);
CREATE TABLE IF NOT EXISTS published_dossiers (work_id TEXT NOT NULL REFERENCES works(work_id), version TEXT NOT NULL, dossier JSONB NOT NULL, published_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY(work_id, version));
ALTER TABLE claims ADD COLUMN IF NOT EXISTS job_id TEXT REFERENCES research_jobs(job_id);
ALTER TABLE claims ADD COLUMN IF NOT EXISTS claim_type TEXT NOT NULL DEFAULT 'fact';
ALTER TABLE claims ADD COLUMN IF NOT EXISTS media_version TEXT NOT NULL DEFAULT 'selected';
