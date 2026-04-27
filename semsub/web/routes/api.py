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


# ---------------------------------------------------------------------------
# Batch API
# ---------------------------------------------------------------------------

def _run_batch(job_id, job_manager, directory, config, output_dir, skip_existing, continue_on_error):
    """Background task that runs batch processing."""
    from semsub.core.batch_scanner import VideoScanner
    from semsub.core.batch_pipeline import BatchPipeline
    from semsub.core.pipeline import SubtitlePipeline
    reporter = WebProgressReporter(job_id, job_manager)
    try:
        scanner = VideoScanner()
        video_tasks = scanner.scan([Path(directory)])
        if not video_tasks:
            job_manager.set_status(job_id, JobStatus.COMPLETED, result={"message": "未找到视频文件"})
            return
        if output_dir:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            for task in video_tasks:
                task.output_path = str(out / Path(task.output_path).name)
        pipeline = SubtitlePipeline(config)
        batch = BatchPipeline(pipeline)
        result = batch.process(video_tasks, continue_on_error=continue_on_error)
        job_manager.set_status(job_id, JobStatus.COMPLETED, result={
            "completed": result.completed_count,
            "failed": result.failed_count,
            "total": result.total_count,
        })
    except Exception as e:
        reporter.on_error(None, e)
        job_manager.set_status(job_id, JobStatus.FAILED, error=str(e))


@router.post("/job/batch")
async def create_batch_job(
    request: Request,
    background_tasks: BackgroundTasks,
    directory: str,
    preset: Optional[str] = None,
    output_dir: Optional[str] = None,
    skip_existing: bool = False,
    continue_on_error: bool = True,
):
    target = Path(directory).expanduser()
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail="目录不存在")

    config_manager = get_config_manager()
    config = config_manager.load(preset=preset)

    job_manager = request.app.state.job_manager
    job_id = job_manager.create_job(
        JobType.BATCH,
        params={"directory": directory, "preset": preset},
    )
    background_tasks.add_task(_run_batch, job_id, job_manager, directory, config, output_dir, skip_existing, continue_on_error)
    return {"job_id": job_id, "status": "pending"}


# ---------------------------------------------------------------------------
# SRT Process API
# ---------------------------------------------------------------------------

def _run_srt_process(job_id, job_manager, srt_path, mode, provider, response_format, target_language, output_path):
    """Background task that runs SRT processing."""
    from semsub.core.srt_llm_processor import SRTLLMProcessor
    reporter = WebProgressReporter(job_id, job_manager)
    try:
        config_manager = get_config_manager()
        config = config_manager.load()
        if provider:
            config.llm.provider = provider
        if target_language:
            config.llm.target_language = target_language
        processor = SRTLLMProcessor(config.llm)
        reporter.on_log(f"开始 SRT 处理: {srt_path}")
        out = Path(output_path) if output_path else Path(srt_path).with_suffix(".processed.srt")
        result = processor.process_file(
            Path(srt_path),
            out,
            reporter=reporter,
        )
        job_manager.set_status(job_id, JobStatus.COMPLETED, result={"output_path": str(result.get("output_path", out))})
    except Exception as e:
        reporter.on_error(None, e)
        job_manager.set_status(job_id, JobStatus.FAILED, error=str(e))


@router.post("/job/srt-process")
async def create_srt_process_job(
    request: Request,
    background_tasks: BackgroundTasks,
    srt_path: str,
    mode: str = "correct",
    provider: Optional[str] = None,
    response_format: Optional[str] = None,
    target_language: Optional[str] = None,
    output_path: Optional[str] = None,
):
    target = Path(srt_path).expanduser()
    if not target.exists():
        raise HTTPException(status_code=404, detail="SRT 文件不存在")
    job_manager = request.app.state.job_manager
    job_id = job_manager.create_job(
        JobType.SRT_PROCESS,
        params={"srt_path": srt_path, "mode": mode},
    )
    background_tasks.add_task(_run_srt_process, job_id, job_manager, srt_path, mode, provider, response_format, target_language, output_path)
    return {"job_id": job_id, "status": "pending"}


# ---------------------------------------------------------------------------
# Workspace API
# ---------------------------------------------------------------------------

@router.get("/workspaces")
async def list_workspaces(request: Request):
    """List all discovered workspace directories."""
    workspaces = []
    for ws_dir in Path(".").rglob(".semsub"):
        if not ws_dir.is_dir():
            continue
        state_path = ws_dir / "state.json"
        if state_path.exists():
            try:
                import json
                data = json.loads(state_path.read_text())
                workspaces.append({
                    "path": str(ws_dir),
                    "video_path": data.get("video_path", "unknown"),
                    "status": data.get("overall_status", "unknown"),
                    "current_stage": data.get("current_stage"),
                })
            except Exception:
                pass
    return workspaces


@router.get("/workspace/status")
async def get_workspace_status(video_path: str = Query(...)):
    """Get workspace status for a specific video."""
    config_manager = get_config_manager()
    config = config_manager.load()
    pipeline = SubtitlePipeline(config)
    status = pipeline.get_status(Path(video_path).expanduser())
    if status is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    return {
        "video_path": status.video_path,
        "overall_status": status.overall_status.value,
        "current_stage": status.current_stage,
        "progress_percent": status.progress_percent,
        "stage_summary": {
            k: {"status": v[0].value, "duration_sec": v[1]}
            for k, v in status.stage_summary.items()
        },
    }


# ---------------------------------------------------------------------------
# Config API
# ---------------------------------------------------------------------------

def _mask_api_key(config_dict):
    """Mask API key in config dict for safe display."""
    result = dict(config_dict)
    if "llm" in result and "api_key" in result["llm"]:
        key = result["llm"]["api_key"]
        if key and len(key) > 8:
            result["llm"]["api_key"] = key[:4] + "****" + key[-4:]
    return result


@router.get("/config")
async def get_config():
    """Get current merged configuration."""
    config_manager = get_config_manager()
    config = config_manager.load()
    return _mask_api_key(config.model_dump())


@router.post("/config")
async def save_config(request: Request):
    """Save configuration to user config file."""
    from pydantic import ValidationError
    body = await request.json()
    config_manager = get_config_manager()
    try:
        from semsub.core.config import PipelineConfig
        config = PipelineConfig(**body)
        config_manager.save_user_config(config)
        return {"status": "saved"}
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/config/reset")
async def reset_config():
    """Reset user configuration to defaults."""
    config_manager = get_config_manager()
    from semsub.core.config import PipelineConfig
    config = PipelineConfig()
    config_manager.save_user_config(config)
    return {"status": "reset"}


@router.get("/config/export")
async def export_config():
    """Export current configuration as YAML."""
    config_manager = get_config_manager()
    config = config_manager.load()
    return {"yaml": config.to_yaml()}
