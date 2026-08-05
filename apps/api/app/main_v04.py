"""Unified LogiSpace 0.4 API entrypoint."""

from app.main import app
from app.routes import research_v4_evaluation, research_v4_full, research_v4_publish, research_v4_routing

app.include_router(research_v4_full.router, prefix="/research/v4/jobs", tags=["research-v4"])
app.include_router(research_v4_routing.router, prefix="/research/v4", tags=["research-v4-routing"])
app.include_router(research_v4_publish.router, prefix="/research/v4/jobs", tags=["research-v4-publish"])
app.include_router(research_v4_evaluation.router, prefix="/research/v4/jobs", tags=["research-v4-evaluation"])
