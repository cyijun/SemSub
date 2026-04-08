"""
批量处理管道
串行处理多个视频文件
"""

import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .config import PipelineConfig
from .pipeline import SubtitlePipeline
from .state_models import VideoTask, BatchResult, StageStatus, PipelineStatus
from .progress import BatchReporter, SilentProgressReporter


class BatchPipeline:
    """批量处理多个视频"""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.pipeline = SubtitlePipeline(config)

    def process(
        self,
        tasks: List[VideoTask],
        reporter: Optional[BatchReporter] = None,
        continue_on_error: bool = False
    ) -> BatchResult:
        """
        串行处理视频任务列表

        Args:
            tasks: VideoTask 列表
            reporter: 进度报告器
            continue_on_error: 遇到错误是否继续处理其他视频

        Returns:
            BatchResult 处理结果
        """
        if reporter is None:
            reporter = BatchReporter()

        if not tasks:
            return BatchResult(success=True, total_count=0, completed_count=0, failed_count=0)

        reporter.on_batch_start(len(tasks))
        start_time = datetime.now()

        for i, task in enumerate(tasks):
            video_path = Path(task.video_path)
            output_path = Path(task.output_path)

            reporter.on_video_start(video_path, i)
            task.started_at = datetime.now()
            task.status = StageStatus.RUNNING

            try:
                # 创建包装器来捕获单个视频的进度
                video_reporter = self._create_video_reporter(reporter)

                # 执行单个视频处理
                result_path = self.pipeline.generate(
                    video_path=video_path,
                    output_path=output_path,
                    reporter=video_reporter
                )

                task.status = StageStatus.COMPLETED
                task.completed_at = datetime.now()
                task.duration_ms = int((task.completed_at - task.started_at).total_seconds() * 1000)
                reporter.on_video_finish(video_path, success=True)

            except Exception as e:
                task.status = StageStatus.FAILED
                task.error_message = str(e)
                task.completed_at = datetime.now()
                task.duration_ms = int((task.completed_at - task.started_at).total_seconds() * 1000) if task.started_at else 0

                reporter.on_video_finish(video_path, success=False, error_msg=str(e))

                if not continue_on_error:
                    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                    reporter.on_batch_finish(success=False, error_msg=str(e))
                    return BatchResult(
                        success=False,
                        total_count=len(tasks),
                        completed_count=reporter.batch_info.completed_count,
                        failed_count=reporter.batch_info.failed_count + 1,
                        tasks=tasks,
                        total_duration_ms=duration_ms,
                        error_message=str(e)
                    )

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        reporter.on_batch_finish(success=True)

        return BatchResult(
            success=True,
            total_count=len(tasks),
            completed_count=reporter.batch_info.completed_count,
            failed_count=reporter.batch_info.failed_count,
            tasks=tasks,
            total_duration_ms=duration_ms
        )

    def _create_video_reporter(self, batch_reporter: BatchReporter):
        """创建包装器捕获单个视频的进度并转发到批量报告器"""
        from .progress import StageProgress

        class VideoReporterProxy(SilentProgressReporter):
            def on_progress(self, progress: StageProgress):
                # 更新当前视频状态
                if batch_reporter.batch_info.current_video_status:
                    batch_reporter.batch_info.current_video_status.progress_percent = progress.percent
                batch_reporter._report()

            def on_stage_complete(self, stage, result=None):
                # 更新当前阶段信息
                if batch_reporter.batch_info.current_video_status:
                    batch_reporter.batch_info.current_video_status.current_stage = str(stage)
                batch_reporter._report()

            def on_log(self, message: str, level: str = "info"):
                # 转发日志消息到批量报告器
                if batch_reporter.batch_info.current_video_status:
                    batch_reporter.batch_info.current_video_status.message = message
                batch_reporter._report()

        return VideoReporterProxy()
