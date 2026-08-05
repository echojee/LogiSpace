"""Agent planning plus controlled Source Pack routing for LogiSpace 0.4."""

from app.main import app
from app.routes import research_v4_agent, research_v4_routing

app.include_router(
    research_v4_agent.router,
    prefix="/research/v4/jobs",
    tags=["research-v4-agent"],
)
app.include_router(
    research_v4_routing.router,
    prefix="/research/v4",
    tags=["research-v4-routing"],
)
