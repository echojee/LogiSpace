from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import chat, conversations, dossiers, health, library, reports, research_jobs, research_v2, research_v3, works

app = FastAPI(
    title="LogiSpace API",
    version="0.3.0",
    description="Spoiler-aware WorkDossier research API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=True,
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
app.include_router(library.router, prefix="/library", tags=["library"])
