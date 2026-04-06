"""
进度报告接口定义
用于解耦核心逻辑与 UI 层
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Optional, List


class PipelineStage(Enum):
    """管道阶段枚举"""
    AUDIO_EXTRACT = auto()
    VAD_SPLIT = auto()
    ASR_TRANSCRIBE = auto()
    SUBTITLE_OPTIMIZE = auto()
    LLM_POSTPROCESS = auto()
    SAVE_OUTPUT = auto()

    def __str__(self) -> str:
        names = {
            PipelineStage.AUDIO_EXTRACT: "音频提取",
            PipelineStage.VAD_SPLIT: "VAD 分割",
            PipelineStage.ASR_TRANSCRIBE: "ASR 转录",
            PipelineStage.SUBTITLE_OPTIMIZE: "字幕优化",
            PipelineStage.LLM_POSTPROCESS: "LLM 后处理",
            PipelineStage.SAVE_OUTPUT: "保存输出",
        }
        return names.get(self, self.name)


@dataclass
class StageProgress:
    """阶段进度数据"""
    stage: PipelineStage
    current: int
    total: int
    message: str
    percent: float  # 0-100

    @classmethod
    def create(cls, stage: PipelineStage, current: int, total: int, message: str = "") -> "StageProgress":
        percent = (current / total * 100) if total > 0 else 0
        return cls(stage=stage, current=current, total=total, message=message, percent=percent)


class CancellationError(Exception):
    """取消错误"""
    pass


class ProgressReporter(ABC):
    """进度报告接口 - CLI 和 GUI 分别实现"""

    def __init__(self):
        self._cancelled = False

    def cancel(self):
        """标记为取消"""
        self._cancelled = True

    def is_cancelled(self) -> bool:
        """检查是否已取消"""
        return self._cancelled

    def check_cancelled(self):
        """检查是否已取消，如果是则抛出异常"""
        if self._cancelled:
            raise CancellationError("操作已取消")

    @abstractmethod
    def on_pipeline_start(self, stages: List[PipelineStage]):
        """管道开始"""
        pass

    @abstractmethod
    def on_stage_start(self, stage: PipelineStage, total: int):
        """阶段开始"""
        pass

    @abstractmethod
    def on_progress(self, progress: StageProgress):
        """进度更新"""
        pass

    @abstractmethod
    def on_stage_complete(self, stage: PipelineStage, result: Any):
        """阶段完成"""
        pass

    @abstractmethod
    def on_pipeline_complete(self, output_path: str):
        """管道完成"""
        pass

    @abstractmethod
    def on_error(self, stage: PipelineStage, error: Exception):
        """发生错误"""
        pass

    @abstractmethod
    def on_log(self, message: str, level: str = "info"):
        """日志消息"""
        pass


class SilentProgressReporter(ProgressReporter):
    """静默进度报告器（用于无 UI 场景）"""

    def __init__(self):
        super().__init__()

    def on_pipeline_start(self, stages: List[PipelineStage]):
        pass

    def on_stage_start(self, stage: PipelineStage, total: int):
        pass

    def on_progress(self, progress: StageProgress):
        pass

    def on_stage_complete(self, stage: PipelineStage, result: Any):
        pass

    def on_pipeline_complete(self, output_path: str):
        pass

    def on_error(self, stage: PipelineStage, error: Exception):
        pass

    def on_log(self, message: str, level: str = "info"):
        pass
