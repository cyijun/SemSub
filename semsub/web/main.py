"""
FastAPI application for SemSub Web GUI.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .job_manager import JobManager
from .routes import api, pages, sse


def create_app() -> FastAPI:
    app = FastAPI(
        title="SemSub Web GUI",
        description="Web interface for SemSub subtitle generator",
        version="1.0.0",
    )

    # Static files
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Templates
    templates_dir = Path(__file__).parent / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))

    # Shared state
    app.state.job_manager = JobManager()
    app.state.templates = templates

    # Register routes
    app.include_router(api.router, prefix="/api")
    app.include_router(sse.router, prefix="/api")
    app.include_router(pages.router)

    return app


app = create_app()
