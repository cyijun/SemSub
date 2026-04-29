"""
In-memory job manager for tracking subtitle generation tasks.
"""

import uuid
import threading
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field


class JobType(str, Enum):
    GENERATE = "generate"
    BATCH = "batch"
    SRT_PROCESS = "srt_process"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobState(BaseModel):
    """任务状态"""
    id: str
    type: JobType
    status: JobStatus = JobStatus.PENDING
    params: Dict[str, Any] = Field(default_factory=dict)
    progress_percent: float = 0.0
    current_stage: Optional[str] = None
    message: str = ""
    logs: List[str] = Field(default_factory=list)
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    cancelled: bool = False

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class JobManager:
    """内存任务管理器（线程安全）"""

    def __init__(self):
        self._jobs: Dict[str, JobState] = {}
        self._lock = threading.Lock()

    def create_job(self, job_type: JobType, params: Dict[str, Any]) -> str:
        job_id = f"job-{uuid.uuid4().hex[:8]}"
        job = JobState(id=job_id, type=job_type, params=params)
        with self._lock:
            self._jobs[job_id] = job
        return job_id

    def get_job(self, job_id: str) -> Optional[JobState]:
        with self._lock:
            return self._jobs.get(job_id)

    def update_progress(self, job_id: str, percent: float, stage: str = "", message: str = ""):
        with self._lock:
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.progress_percent = percent
                job.current_stage = stage
                job.message = message

    def append_log(self, job_id: str, message: str):
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].logs.append(message)
                # 保留最近 500 条
                if len(self._jobs[job_id].logs) > 500:
                    self._jobs[job_id].logs = self._jobs[job_id].logs[-500:]

    def set_status(
        self,
        job_id: str,
        status: JobStatus,
        error: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ):
        with self._lock:
            if job_id not in self._jobs:
                return
            job = self._jobs[job_id]
            job.status = status
            if error is not None:
                job.error = error
            if result is not None:
                job.result = result
            if status == JobStatus.RUNNING:
                job.started_at = datetime.now()
            if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                job.completed_at = datetime.now()

    def is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.cancelled if job else False

    def cancel_job(self, job_id: str) -> bool:
        with self._lock:
            if job_id not in self._jobs:
                return False
            job = self._jobs[job_id]
            job.cancelled = True
            job.status = JobStatus.CANCELLED
            return True

    def delete_job(self, job_id: str) -> bool:
        with self._lock:
            if job_id not in self._jobs:
                return False
            del self._jobs[job_id]
            return True

    def list_jobs(self) -> List[JobState]:
        with self._lock:
            return list(self._jobs.values())

    def cleanup_old_jobs(self, max_age_hours: int = 24):
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        with self._lock:
            to_remove = [
                jid for jid, job in self._jobs.items()
                if job.completed_at and job.completed_at < cutoff
            ]
            for jid in to_remove:
                del self._jobs[jid]
