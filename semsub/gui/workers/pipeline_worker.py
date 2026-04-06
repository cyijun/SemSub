"""
管道工作线程 - 在后台执行字幕生成
"""

from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

from ...core.config import PipelineConfig
from ...core.pipeline import SubtitlePipeline
from ...core.progress import (
    ProgressReporter,
    PipelineStage,
    StageProgress,
)


class PipelineWorker(QThread):
    """管道工作线程"""

    progress = pyqtSignal(int, str)  # 百分比, 消息
    log = pyqtSignal(str)  # 日志消息
    finished = pyqtSignal(str)  # 输出路径
    error = pyqtSignal(str)  # 错误消息
    cancelled = pyqtSignal()  # 取消信号

    def __init__(self, config: PipelineConfig, video_path: Path, output_path: Path = None):
        super().__init__()
        self.config = config
        self.video_path = video_path
        self.output_path = output_path
        self._is_running = True
        self._reporter = None

    def run(self):
        """运行管道"""
        try:
            self._reporter = QtProgressReporter(self)
            pipeline = SubtitlePipeline(self.config)
            output = pipeline.generate(self.video_path, self.output_path, self._reporter)

            if self._is_running:
                self.finished.emit(str(output))
        except CancellationError:
            self.log.emit("操作已取消")
        except Exception as e:
            if self._is_running:
                self.error.emit(str(e))

    def stop(self):
        """停止处理"""
        self._is_running = False
        self.cancelled.emit()
        # 等待线程结束，但最多3秒
        if not self.wait(3000):
            self.log.emit("警告：线程未能及时停止")


class QtProgressReporter(ProgressReporter):
    """Qt 进度报告器"""

    def __init__(self, worker: PipelineWorker):
        super().__init__()
        self.worker = worker
        self.current_stage = None
        self.stage_progress = 0
        # 连接 worker 的取消信号
        worker.cancelled.connect(self.cancel)

    def on_pipeline_start(self, stages):
        self.worker.log.emit(f"开始处理，共 {len(stages)} 个阶段")
        self.worker.progress.emit(0, "开始处理...")

    def on_stage_start(self, stage: PipelineStage, total: int):
        self.current_stage = stage
        self.stage_progress = 0
        self.worker.log.emit(f"阶段: {stage}")
        self.worker.progress.emit(self._calc_percent(), f"{stage}...")

    def on_progress(self, progress: StageProgress):
        self.stage_progress = progress.percent
        self.worker.progress.emit(
            self._calc_percent(),
            f"{progress.stage}: {progress.message}"
        )

    def on_stage_complete(self, stage: PipelineStage, result):
        self.worker.log.emit(f"✓ {stage} 完成")

    def on_pipeline_complete(self, output_path: str):
        self.worker.progress.emit(100, "完成")

    def on_error(self, stage: PipelineStage, error: Exception):
        self.worker.log.emit(f"✗ {stage} 错误: {error}")

    def on_log(self, message: str, level: str = "info"):
        self.worker.log.emit(message)

    def _calc_percent(self) -> int:
        """计算总体进度"""
        if not self.current_stage:
            return 0
        # 简化的进度计算：每个阶段约 20%
        stage_index = list(PipelineStage).index(self.current_stage)
        base = stage_index * 20
        current = int(self.stage_progress * 0.2)
        return min(base + current, 100)
