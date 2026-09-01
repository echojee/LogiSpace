from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from pathlib import Path


def _load_local_env() -> None:
    env_file = Path(__file__).resolve().parents[3] / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


_load_local_env()

from app.routes import (
    chat, conversations, dossiers, health, knowledge_memory, library, reports, research_jobs,
    research_v2, research_v3, research_v4_evaluation, research_v4_full,
    research_v4_publish, research_v4_routing, user_memory, visualizations, works,
)

app = FastAPI(
    title="LogiSpace API",
    version="0.3.0",
    description="Spoiler-aware WorkDossier research API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_origin_regex=r"^http://(?:localhost|127\.0\.0\.1):\d+$",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(works.router, prefix="/works", tags=["works"])
app.include_router(research_jobs.router, prefix="/research-jobs", tags=["research-jobs"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])
app.include_router(dossiers.router, prefix="/dossiers", tags=["dossiers"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
app.include_router(research_v3.router, prefix="/research/jobs", tags=["research-v3"])
app.include_router(research_v2.router, prefix="/research", tags=["research-v2-compat"])
app.include_router(research_v4_full.router, prefix="/research/v4/jobs", tags=["research-v4"])
app.include_router(research_v4_routing.router, prefix="/research/v4", tags=["research-v4-routing"])
app.include_router(research_v4_publish.router, prefix="/research/v4/jobs", tags=["research-v4-publish"])
app.include_router(research_v4_evaluation.router, prefix="/research/v4/jobs", tags=["research-v4-evaluation"])
app.include_router(library.router, prefix="/library", tags=["library"])
app.include_router(knowledge_memory.router, prefix="/knowledge", tags=["knowledge-memory"])
app.include_router(user_memory.router, prefix="/memory/user", tags=["user-memory"])
app.include_router(visualizations.router, prefix="/knowledge", tags=["visualization-skills"])
