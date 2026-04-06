"""
批量处理工作线程
"""

from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from ...core.config import PipelineConfig
from ...core.batch_pipeline import BatchPipeline
from ...core.state_models import VideoTask, BatchResult, StageStatus


class BatchWorker(QThread):
    """批量处理工作线程"""

    # 批量级别信号
    batch_started = pyqtSignal(int)  # total_count
    batch_progress = pyqtSignal(int, int, str)  # current_index, total_count, current_video_name
    batch_finished = pyqtSignal(bool, int, int, int)  # success, completed, failed, total
    batch_error = pyqtSignal(str)

    # 单个视频级别信号
    video_started = pyqtSignal(str, int, int)  # video_path, index, total
    video_progress = pyqtSignal(int, str)  # percent, message
    video_finished = pyqtSignal(str, bool, str)  # video_path, success, output_path

    # 日志信号
    log = pyqtSignal(str)

    def __init__(
        self,
        config: PipelineConfig,
        tasks: List[VideoTask],
        continue_on_error: bool = False
    ):
        super().__init__()
        self.config = config
        self.tasks = tasks
        self.continue_on_error = continue_on_error
        self._is_cancelled = False

    def run(self):
        """执行批量处理"""
        try:
            self.batch_started.emit(len(self.tasks))

            pipeline = BatchPipeline(self.config)

            # 创建自定义报告器
            reporter = self._create_reporter()

            result = pipeline.process(
                tasks=self.tasks,
                reporter=reporter,
                continue_on_error=self.continue_on_error
            )

            self.batch_finished.emit(
                result.success,
                result.completed_count,
                result.failed_count,
                result.total_count
            )

        except Exception as e:
            self.batch_error.emit(str(e))

    def _create_reporter(self):
        """创建 Qt 信号报告器"""
        from ...core.progress import BatchReporter
        from ...core.state_models import PipelineStatus

        class QtBatchReporter(BatchReporter):
            def __init__(self, worker):
                super().__init__()
                self.worker = worker

            def on_video_start(self, video_path: Path, index: int):
                super().on_video_start(video_path, index)
                self.worker.video_started.emit(str(video_path), index, self.batch_info.total_count)
                self.worker.batch_progress.emit(index, self.batch_info.total_count, video_path.name)

            def on_video_progress(self, status: PipelineStatus):
                super().on_video_progress(status)
                if status:
                    self.worker.video_progress.emit(
                        int(status.progress_percent),
                        f"{status.current_stage or 'processing'}"
                    )

            def on_video_finish(self, video_path: Path, success: bool, error_msg: Optional[str] = None):
                super().on_video_finish(video_path, success, error_msg)
                self.worker.video_finished.emit(
                    str(video_path),
                    success,
                    "" if success else (error_msg or "")
                )

            def on_batch_start(self, total_count: int):
                super().on_batch_start(total_count)
                self.worker.log.emit(f"开始批量处理 {total_count} 个视频...")

            def on_batch_finish(self, success: bool, error_msg: Optional[str] = None):
                super().on_batch_finish(success, error_msg)
                if success:
                    self.worker.log.emit("批量处理完成")
                else:
                    self.worker.log.emit(f"批量处理中断: {error_msg or 'Unknown error'}")

        return QtBatchReporter(self)

    def cancel(self):
        """取消处理"""
        self._is_cancelled = True
        self.log.emit("正在取消...")
