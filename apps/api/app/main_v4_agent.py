"""Agent-driven LogiSpace 0.4 API entrypoint."""

from app.main import app
from app.routes import research_v4_agent

app.include_router(
    research_v4_agent.router,
    prefix="/research/v4/jobs",
    tags=["research-v4-agent"],
)
