"""
Server-Sent Events (SSE) routes for real-time job progress updates.
"""

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

router = APIRouter()


async def _job_event_stream(job_id: str, job_manager):
    """Generate SSE events for a job's progress."""
    last_json = None

    while True:
        job = job_manager.get_job(job_id)
        if not job:
            yield f"event: error\ndata: {json.dumps({'message': '任务不存在'})}\n\n"
            break

        current_json = job.model_dump_json()
        # Only send if state changed
        if current_json != last_json:
            last_json = current_json
            yield f"event: update\ndata: {current_json}\n\n"

        if job.status.value in ("completed", "failed", "cancelled"):
            yield f"event: done\ndata: {json.dumps({'status': job.status.value})}\n\n"
            break

        await asyncio.sleep(1)


@router.get("/sse/job/{job_id}")
async def job_sse(request: Request, job_id: str):
    """Stream real-time updates for a job via SSE."""
    job_manager = request.app.state.job_manager
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    return StreamingResponse(
        _job_event_stream(job_id, job_manager),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
