"""
单阶段执行工作线程
用于执行 pipeline 的单个阶段
"""

from pathlib import Path
from typing import Optional
from PyQt6.QtCore import QThread, pyqtSignal

from ...core.config import PipelineConfig
from ...core.workspace import WorkspaceManager


class StageWorker(QThread):
    """单阶段执行工作线程"""

    # 信号定义
    started_signal = pyqtSignal(str)           # stage_id
    progress_signal = pyqtSignal(int, str)     # percent, message
    finished_signal = pyqtSignal(bool, str)    # success, message
    error_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)

    def __init__(
        self,
        video_path: Path,
        stage_id: str,
        config: PipelineConfig,
        force: bool = False,
        resume: bool = False
    ):
        super().__init__()
        self.video_path = video_path
        self.stage_id = stage_id
        self.config = config
        self.force = force
        self.resume = resume
        self._is_cancelled = False

    def run(self):
        """执行阶段"""
        try:
            self.started_signal.emit(self.stage_id)
            self.log_signal.emit(f"开始执行阶段: {self.stage_id}")

            # 获取阶段类
            stage_class = self._get_stage_class(self.stage_id)
            if not stage_class:
                raise ValueError(f"未知的阶段 ID: {self.stage_id}")

            # 创建工作区
            manager = WorkspaceManager(self.video_path)
            workspace = manager.open()
            if workspace is None:
                workspace = manager.initialize(self.config)

            # 获取或创建阶段上下文
            stage_context = workspace.get_stage(self.stage_id)

            # 检查依赖
            if not self.force:
                deps_ok, missing = self._check_dependencies(workspace, self.stage_id)
                if not deps_ok:
                    raise ValueError(f"依赖未满足: {', '.join(missing)}")

            # 执行阶段
            stage = stage_class(self.config)

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

            reporter = QtProgressReporter(self)

            # 执行
            result = stage.execute(stage_context, reporter)

            if self._is_cancelled:
                self.finished_signal.emit(False, "已取消")
            else:
                self.finished_signal.emit(True, f"阶段 {self.stage_id} 执行完成")

        except Exception as e:
            self.error_signal.emit(str(e))
            self.finished_signal.emit(False, str(e))

    def _get_stage_class(self, stage_id: str) -> Optional[type]:
        """获取阶段类"""
        from ...core.stages.audio_extract import AudioExtractStage
        from ...core.stages.vad_split import VADSplitStage
        from ...core.stages.asr_transcribe import ASRTranscribeStage
        from ...core.stages.subtitle_optimize import SubtitleOptimizeStage
        from ...core.stages.llm_postprocess import LLMPostprocessStage

        stage_map = {
            "01_audio_extract": AudioExtractStage,
            "02_vad_split": VADSplitStage,
            "03_asr_transcribe": ASRTranscribeStage,
            "04_subtitle_optimize": SubtitleOptimizeStage,
            "05_llm_postprocess": LLMPostprocessStage,
        }
        return stage_map.get(stage_id)

    def _check_dependencies(self, workspace, stage_id: str) -> tuple[bool, list]:
        """检查依赖是否满足"""
        from ...core.state_models import StageStatus

        # 获取阶段依赖关系
        deps_map = {
            "01_audio_extract": [],
            "02_vad_split": ["01_audio_extract"],
            "03_asr_transcribe": ["02_vad_split"],
            "04_subtitle_optimize": ["02_vad_split", "03_asr_transcribe"],
            "05_llm_postprocess": ["04_subtitle_optimize"],
        }

        missing = []
        for dep_id in deps_map.get(stage_id, []):
            stage_context = workspace.get_stage(dep_id)
            if stage_context.get_state().status != StageStatus.COMPLETED:
                missing.append(dep_id)

        return len(missing) == 0, missing

    def cancel(self):
        """取消执行"""
        self._is_cancelled = True
        self.log_signal.emit("正在取消...")
