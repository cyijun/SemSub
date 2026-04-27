"""
Page routes for SemSub Web GUI.

Renders Jinja2 templates for the web interface.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """Home / Quick start page."""
    return request.app.state.templates.TemplateResponse(request, "home.html")


@router.get("/generate", response_class=HTMLResponse)
async def generate_page(request: Request):
    """Single video generation page."""
    return request.app.state.templates.TemplateResponse(request, "generate.html")


@router.get("/batch", response_class=HTMLResponse)
async def batch_page(request: Request):
    """Batch processing page."""
    return request.app.state.templates.TemplateResponse(request, "batch.html")


@router.get("/srt-process", response_class=HTMLResponse)
async def srt_process_page(request: Request):
    """SRT processing page."""
    return request.app.state.templates.TemplateResponse(request, "srt_process.html")


@router.get("/workspaces", response_class=HTMLResponse)
async def workspaces_page(request: Request):
    """Workspace management page."""
    return request.app.state.templates.TemplateResponse(request, "workspaces.html")


@router.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    """Configuration page."""
    return request.app.state.templates.TemplateResponse(request, "config.html")
