"""
ProgressReporter implementation that writes to JobManager for SSE consumption.
"""

from typing import List, Any

from semsub.core.progress import ProgressReporter, StageProgress, PipelineStage, CancellationError
from .job_manager import JobManager, JobStatus


class WebProgressReporter(ProgressReporter):
    """将进度写入 JobManager，供 SSE 推送"""

    def __init__(self, job_id: str, job_manager: JobManager):
        super().__init__()
        self.job_id = job_id
        self.job_manager = job_manager

    def on_pipeline_start(self, stages: List[PipelineStage]):
        self.job_manager.set_status(self.job_id, JobStatus.RUNNING)
        stage_names = ", ".join(str(s) for s in stages)
        self.job_manager.append_log(self.job_id, f"[PIPELINE] 开始: {stage_names}")

    def on_stage_start(self, stage: PipelineStage, total: int):
        self.job_manager.update_progress(self.job_id, 0.0, str(stage), f"开始: {stage}")
        self.job_manager.append_log(self.job_id, f"[STAGE] 开始 {stage}")

    def on_progress(self, progress: StageProgress):
        self.job_manager.update_progress(
            self.job_id,
            round(progress.percent, 1),
            str(progress.stage),
            progress.message,
        )

    def on_stage_complete(self, stage: PipelineStage, result: Any):
        self.job_manager.append_log(self.job_id, f"[STAGE] 完成 {stage}")

    def on_pipeline_complete(self, output_path: str):
        self.job_manager.set_status(
            self.job_id,
            JobStatus.COMPLETED,
            result={"output_path": output_path},
        )
        self.job_manager.append_log(self.job_id, f"[PIPELINE] 完成: {output_path}")

    def on_error(self, stage: PipelineStage, error: Exception):
        self.job_manager.set_status(
            self.job_id,
            JobStatus.FAILED,
            error=str(error),
        )
        self.job_manager.append_log(
            self.job_id, f"[ERROR] {stage}: {error}"
        )

    def on_log(self, message: str, level: str = "info"):
        self.job_manager.append_log(
            self.job_id, f"[{level.upper()}] {message}"
        )

    def check_cancelled(self):
        if self.job_manager.is_cancelled(self.job_id):
            raise CancellationError("操作已取消")
