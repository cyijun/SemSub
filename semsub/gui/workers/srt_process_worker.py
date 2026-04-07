"""
SRT 处理工作线程
用于独立的 SRT 文件 LLM 后处理
"""

from pathlib import Path
from typing import Optional
from PyQt6.QtCore import QThread, pyqtSignal

from ...core.config import LLMProcessConfig
from ...core.srt_llm_processor import SRTLLMProcessor
from ...core.progress import ProgressReporter, PipelineStage, StageProgress


class SRTProcessWorker(QThread):
    """SRT 文件处理工作线程"""

    # 信号定义
    started_signal = pyqtSignal()                   # 处理开始
    progress_signal = pyqtSignal(int, str)          # percent, message
    finished_signal = pyqtSignal(bool, str)         # success, message
    error_signal = pyqtSignal(str)                  # error message
    log_signal = pyqtSignal(str)                    # log message

    def __init__(
        self,
        input_path: Path,
        output_path: Path,
        config: LLMProcessConfig
    ):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.config = config
        self._is_cancelled = False

    def run(self):
        """执行 SRT 处理"""
        try:
            self.started_signal.emit()
            self.log_signal.emit(f"开始处理 SRT 文件: {self.input_path}")

            # 创建处理器
            processor = SRTLLMProcessor(self.config)

            # 创建进度报告器
            class QtProgressReporter:
                def __init__(self, worker):
                    self.worker = worker

                def on_stage_start(self, stage, total):
                    self.worker.log_signal.emit(f"阶段开始: {stage.name}")

                def on_progress(self, progress):
                    self.worker.progress_signal.emit(
                        int(progress.percent),
                        progress.message or "处理中..."
                    )

                def on_stage_complete(self, stage, result):
                    self.worker.log_signal.emit(f"阶段完成: {stage.name}")

                def on_error(self, stage, error):
                    self.worker.error_signal.emit(f"{stage.name} 错误: {error}")

                def on_log(self, message, level="info"):
                    self.worker.log_signal.emit(message)

                def check_cancelled(self):
                    if self.worker._is_cancelled:
                        raise InterruptedError("处理已取消")

            reporter = QtProgressReporter(self)

            # 执行处理
            result = processor.process_file(
                self.input_path,
                self.output_path,
                reporter
            )

            if self._is_cancelled:
                self.finished_signal.emit(False, "已取消")
            else:
                total_lines = result.get("total_lines", 0)
                changed_lines = result.get("changed_lines", 0)
                change_ratio = result.get("change_ratio", 0)

                msg = (
                    f"处理完成！共 {total_lines} 行字幕，"
                    f"修改 {changed_lines} 行 ({change_ratio}%)"
                )
                self.finished_signal.emit(True, msg)

        except InterruptedError:
            self.finished_signal.emit(False, "已取消")
        except Exception as e:
            self.error_signal.emit(str(e))
            self.finished_signal.emit(False, str(e))

    def cancel(self):
        """取消处理"""
        self._is_cancelled = True
        self.log_signal.emit("正在取消...")
