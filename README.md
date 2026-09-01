# LogiSpace

LogiSpace is a spoiler-aware mystery research workspace. The MVP focuses on one credible loop:

1. Resolve a work identity.
2. Create a research job.
3. Collect and normalize source evidence.
4. Map evidence into mystery-domain ontology objects.
5. Write claims with citations.
6. Verify claim support.
7. Publish a versioned report into the user's personal library.

## Repository Layout

```text
apps/
  api/            FastAPI service and route layer
  web/            Next.js web shell
packages/
  domain/         Pydantic schemas, ontology, spoiler rules
  research/       Planner, pipeline state machine, stage contracts
  evaluation/     Golden data and regression harness
infra/            Docker Compose, database bootstrap, deployment notes
docs/             ADRs, data dictionary, operating notes
```

## First Local API Run

```powershell
$env:PYTHONPATH="packages/domain;packages/research;apps/api"
python -m pip install fastapi uvicorn pydantic
uvicorn app.main:app --app-dir apps/api --reload
```

## First Local Web Run

```powershell
cd apps/web
npm install
npm run dev
```

## Current Scope

This scaffold intentionally uses a deterministic mock research pipeline. Real search, Agent-Reach adapters, Cognee, and model calls should be added after the report schema, spoiler policy, and claim-evidence contract are stable.

## WorkDossier v0 Closed Loop

The v0 loop is API-backed and keeps every work as an independent primary data asset:

1. `GET /dossiers` loads the catalog of versioned WorkDossiers.
2. `GET /dossiers/{work_id}/views` derives four product views inside one work namespace.
3. `POST /dossiers/qa` runs a golden question only inside explicit `source_work_ids`.
4. `GET /dossiers/ontology/revision` reports the shared Ontology 0.2 revision findings.

Each work is stored separately under `data/works/{work_id}/versions/{dossier_version}/dossier.json`. `data/catalog.json` registers assets but never merges their entities.

### Validate

```powershell
$env:PYTHONPATH="packages/domain;packages/research;apps/api"
python -m pytest -q

cd apps/web
pnpm install
pnpm run build
```

### Run the full loop

```powershell
$env:PYTHONPATH="packages/domain;packages/research;apps/api"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

cd apps/web
pnpm start --hostname 127.0.0.1 --port 3000
```

Open `http://127.0.0.1:3000`, choose one or more primary databases, switch the active work, and run its golden QA. A successful run displays the answer, evidence entity IDs, exact source scope, and `VERIFIED`.

## Memory MVP

The v0.4 runtime persists three reusable memory layers without replacing the existing orchestrator:

- **Work Memory** keeps runtime snapshots, unit state, search caches, and an append-only execution journal. Resume with `POST /research/v4/jobs/{job_id}/resume` and inspect `GET /research/v4/jobs/{job_id}/checkpoints`.
- **Knowledge Memory** treats a reviewed, published `verified-knowledge.json` plus `case-file.json` as an immutable work/media/version-scoped knowledge asset. Browse it under `/knowledge/works` or in the web Knowledge Library.
- **User Memory** stores explicit preferences for the local `local_default` profile through `GET/PATCH/DELETE /memory/user` and supplies defaults to Deep Research and compact context to Quick QA.

After Knowledge Memory exists, `POST /knowledge/works/{work_id}/visualizations` deterministically projects supported relationship or timeline objects into Mermaid. Visualization generation is optional and never mutates Verified Knowledge.
