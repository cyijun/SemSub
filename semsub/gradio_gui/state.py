"""
全局状态管理

管理正在进行的任务和处理状态
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import threading


class JobStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StageInfo:
    """阶段信息"""
    stage_id: str
    name: str
    status: str  # pending, running, completed, failed
    progress: float = 0.0
    message: str = ""
    duration_ms: Optional[int] = None


@dataclass
class ProcessingJob:
    """处理任务"""
    id: str
    video_path: Path
    status: JobStatus
    progress: float
    message: str
    result: Optional[Path] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    stages: List[StageInfo] = field(default_factory=list)
    current_stage: Optional[str] = None
    cancel_requested: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "video_path": str(self.video_path),
            "video_name": self.video_path.name,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "result": str(self.result) if self.result else None,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "stages": [
                {
                    "stage_id": s.stage_id,
                    "name": s.name,
                    "status": s.status,
                    "progress": s.progress,
                    "message": s.message,
                }
                for s in self.stages
            ],
            "current_stage": self.current_stage,
        }


class StateManager:
    """状态管理器 - 线程安全"""

    def __init__(self):
        self._jobs: Dict[str, ProcessingJob] = {}
        self._lock = threading.RLock()
        self._callbacks: Dict[str, List[Callable]] = {}

    def create_job(self, video_path: Path) -> ProcessingJob:
        """创建新任务"""
        job_id = str(uuid.uuid4())[:8]
        job = ProcessingJob(
            id=job_id,
            video_path=video_path,
            status=JobStatus.PENDING,
            progress=0.0,
            message="等待开始...",
        )
        with self._lock:
            self._jobs[job_id] = job
        self._notify("job_created", job)
        return job

    def get_job(self, job_id: str) -> Optional[ProcessingJob]:
        """获取任务"""
        with self._lock:
            return self._jobs.get(job_id)

    def update_job(
        self,
        job_id: str,
        status: Optional[JobStatus] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        result: Optional[Path] = None,
        error: Optional[str] = None,
    ):
        """更新任务状态"""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return

            if status is not None:
                job.status = status
                if status == JobStatus.RUNNING and job.started_at is None:
                    job.started_at = datetime.now()
                if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                    job.completed_at = datetime.now()

            if progress is not None:
                job.progress = progress
            if message is not None:
                job.message = message
            if result is not None:
                job.result = result
            if error is not None:
                job.error = error

        self._notify("job_updated", job)

    def update_stage(
        self,
        job_id: str,
        stage_id: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
    ):
        """更新阶段状态"""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return

            # 查找或创建阶段
            stage = None
            for s in job.stages:
                if s.stage_id == stage_id:
                    stage = s
                    break

            if stage is None:
                from semsub.core.pipeline import SubtitlePipeline
                name_map = {
                    "01_audio_extract": "音频提取",
                    "02_vad_split": "VAD 分割",
                    "03_asr_transcribe": "ASR 转录",
                    "04_subtitle_optimize": "字幕优化",
                    "05_llm_postprocess": "LLM 后处理",
                }
                stage = StageInfo(
                    stage_id=stage_id,
                    name=name_map.get(stage_id, stage_id),
                    status="pending",
                )
                job.stages.append(stage)

            if status is not None:
                stage.status = status
                if status == "running":
                    job.current_stage = stage_id
            if progress is not None:
                stage.progress = progress
            if message is not None:
                stage.message = message

        self._notify("stage_updated", job, stage)

    def request_cancel(self, job_id: str) -> bool:
        """请求取消任务"""
        with self._lock:
            job = self._jobs.get(job_id)
            if job and job.status == JobStatus.RUNNING:
                job.cancel_requested = True
                return True
            return False

    def is_cancel_requested(self, job_id: str) -> bool:
        """检查是否请求取消"""
        with self._lock:
            job = self._jobs.get(job_id)
            return job.cancel_requested if job else False

    def list_jobs(self, status: Optional[JobStatus] = None) -> List[ProcessingJob]:
        """列出所有任务"""
        with self._lock:
            jobs = list(self._jobs.values())
            if status:
                jobs = [j for j in jobs if j.status == status]
            return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    def delete_job(self, job_id: str) -> bool:
        """删除任务"""
        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                return True
            return False

    def clear_completed(self) -> int:
        """清理已完成的任务"""
        with self._lock:
            to_remove = [
                jid for jid, job in self._jobs.items()
                if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)
            ]
            for jid in to_remove:
                del self._jobs[jid]
            return len(to_remove)

    def subscribe(self, event: str, callback: Callable):
        """订阅事件"""
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable):
        """取消订阅"""
        if event in self._callbacks:
            self._callbacks[event] = [
                c for c in self._callbacks[event] if c != callback
            ]

    def _notify(self, event: str, *args):
        """通知订阅者"""
        for callback in self._callbacks.get(event, []):
            try:
                callback(*args)
            except Exception:
                pass


# 全局状态管理器实例
state_manager = StateManager()


class ProgressReporter:
    """用于 Gradio 的进度报告器"""

    STAGE_NAMES = {
        "01_audio_extract": "音频提取",
        "02_vad_split": "VAD 分割",
        "03_asr_transcribe": "ASR 转录",
        "04_subtitle_optimize": "字幕优化",
        "05_llm_postprocess": "LLM 后处理",
    }

    def __init__(self, job_id: str):
        self.job_id = job_id

    def on_stage_start(self, stage_id: str, total: int):
        """阶段开始"""
        state_manager.update_stage(
            self.job_id,
            stage_id,
            status="running",
            message="开始执行...",
        )

    def on_progress(self, progress_or_stage, current=None, total=None, message=""):
        """进度更新 - 支持两种调用方式:
        1. on_progress(stage_id, current, total, message) - 旧方式
        2. on_progress(StageProgress) - 核心接口方式
        """
        # 处理 StageProgress 对象（核心接口）
        if hasattr(progress_or_stage, 'stage'):
            stage = progress_or_stage.stage
            current = progress_or_stage.current
            total = progress_or_stage.total
            message = progress_or_stage.message
            # 将 PipelineStage 转换为 stage_id
            stage_id = str(stage).lower().replace('_', '')[:2]
        else:
            # 旧方式：直接传入参数
            stage_id = progress_or_stage

        progress_pct = (current / total * 100) if total and total > 0 else 0
        state_manager.update_stage(
            self.job_id,
            stage_id,
            status="running",
            progress=progress_pct,
            message=message,
        )
        # 更新整体进度
        stages = ["01_audio_extract", "02_vad_split", "03_asr_transcribe",
                  "04_subtitle_optimize", "05_llm_postprocess"]
        stage_idx = stages.index(stage_id) if stage_id in stages else 0
        overall_progress = (stage_idx * 20) + (progress_pct * 0.2)
        state_manager.update_job(self.job_id, progress=overall_progress)

    def on_stage_complete(self, stage_id: str, success: bool):
        """阶段完成"""
        state_manager.update_stage(
            self.job_id,
            stage_id,
            status="completed" if success else "failed",
            progress=100.0,
            message="完成" if success else "失败",
        )

    def on_error(self, stage_id: str, error: Exception):
        """错误处理"""
        state_manager.update_stage(
            self.job_id,
            stage_id,
            status="failed",
            message=f"错误: {str(error)}",
        )
        state_manager.update_job(
            self.job_id,
            status=JobStatus.FAILED,
            error=str(error),
        )

    def on_log(self, message: str):
        """日志消息"""
        state_manager.update_job(self.job_id, message=message)

    def check_cancelled(self) -> bool:
        """检查是否被取消"""
        job = state_manager.get_job(self.job_id)
        if job:
            return job.status == JobStatus.CANCELLED
        return False
