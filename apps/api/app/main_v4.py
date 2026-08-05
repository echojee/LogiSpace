"""LogiSpace 0.4 API entrypoint.

It extends the stable 0.3 application without changing the existing entrypoint.
Run with: uvicorn app.main_v4:app --app-dir apps/api
"""

from app.main import app
from app.routes import research_v4

app.include_router(research_v4.router, prefix="/research/v4/jobs", tags=["research-v4"])
