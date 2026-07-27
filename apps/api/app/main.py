from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import chat, dossiers, health, library, reports, research_jobs, works

app = FastAPI(
    title="LogiSpace API",
    version="0.2.0",
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
app.include_router(library.router, prefix="/library", tags=["library"])
