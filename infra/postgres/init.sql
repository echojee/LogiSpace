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
