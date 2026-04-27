"""
API routes for SemSub Web GUI.

Includes:
- File system browsing endpoints
- Job management endpoints (create, status, list, cancel)
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, BackgroundTasks

from semsub.core.pipeline import SubtitlePipeline
from semsub.core.config_manager import get_config_manager
from ..job_manager import JobManager, JobType, JobStatus
from ..progress_reporter import WebProgressReporter

router = APIRouter()

FORBIDDEN_ROOTS = {"/etc", "/root", "/proc", "/sys", "/dev", "/boot"}


def _is_path_allowed(target: Path) -> bool:
    """Check if a path is allowed for browsing."""
    resolved = target.resolve()
    for forbidden in FORBIDDEN_ROOTS:
        try:
            resolved.relative_to(Path(forbidden).resolve())
            return False
        except ValueError:
            pass
    return True


# ---------------------------------------------------------------------------
# File System API
# ---------------------------------------------------------------------------

@router.get("/fs/home")
async def get_home():
    """Return the user's home directory path."""
    return {"path": str(Path.home())}


@router.get("/fs/browse")
async def browse(path: str = Query(...)):
    """Browse a directory and return its contents."""
    target = Path(path).expanduser()
    if not _is_path_allowed(target):
        raise HTTPException(status_code=403, detail="访问被拒绝")
    if not target.exists():
        raise HTTPException(status_code=404, detail="路径不存在")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="不是目录")

    items = []
    for item in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
        stat = item.stat()
        items.append({
            "name": item.name,
            "type": "dir" if item.is_dir() else "file",
            "size": stat.st_size if item.is_file() else None,
            "ext": item.suffix if item.is_file() else None,
        })

    parent = str(target.parent) if target.parent != target else None
    return {"current": str(target.resolve()), "parent": parent, "items": items}


# ---------------------------------------------------------------------------
# Job Generation API
# ---------------------------------------------------------------------------

def _run_generate(job_id, job_manager, video_path, config, output_path):
    """Background task that runs the subtitle generation pipeline."""
    reporter = WebProgressReporter(job_id, job_manager)
    try:
        pipeline = SubtitlePipeline(config)
        out = pipeline.generate(
            Path(video_path),
            output_path=Path(output_path) if output_path else None,
            reporter=reporter,
        )
        job_manager.set_status(job_id, JobStatus.COMPLETED, result={"output_path": str(out)})
    except Exception as e:
        reporter.on_error(None, e)
        job_manager.set_status(job_id, JobStatus.FAILED, error=str(e))


@router.post("/job/generate")
async def create_generate_job(
    request: Request,
    background_tasks: BackgroundTasks,
    video_path: str,
    preset: Optional[str] = None,
    language: Optional[str] = None,
    output_path: Optional[str] = None,
    output_format: Optional[str] = None,
    llm_enabled: Optional[bool] = None,
):
    """Create a new subtitle generation job and run it in the background."""
    # Verify video file exists
    if not Path(video_path).exists():
        raise HTTPException(status_code=404, detail=f"视频文件不存在: {video_path}")

    config_manager = get_config_manager()
    overrides = {}
    if language:
        overrides["asr.language"] = language
    if output_format:
        overrides["output.format"] = output_format
    if llm_enabled is not None:
        overrides["llm.enabled"] = str(llm_enabled)
    config = config_manager.load(preset=preset, cli_overrides=overrides or None)

    job_manager = request.app.state.job_manager
    job_id = job_manager.create_job(
        JobType.GENERATE,
        params={"video_path": video_path, "preset": preset},
    )
    background_tasks.add_task(_run_generate, job_id, job_manager, video_path, config, output_path)
    return {"job_id": job_id, "status": "pending"}


@router.get("/job/{job_id}/status")
async def get_job_status(request: Request, job_id: str):
    """Get the status of a specific job."""
    job = request.app.state.job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job.model_dump()


@router.get("/job/list")
async def list_jobs(request: Request):
    """List all jobs."""
    jobs = request.app.state.job_manager.list_jobs()
    return [job.model_dump() for job in jobs]


@router.post("/job/{job_id}/cancel")
async def cancel_job(request: Request, job_id: str):
    """Cancel a running or pending job."""
    if request.app.state.job_manager.cancel_job(job_id):
        return {"status": "cancelled"}
    raise HTTPException(status_code=404, detail="任务不存在")
