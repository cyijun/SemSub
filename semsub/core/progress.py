"""
进度报告接口定义
用于解耦核心逻辑与 UI 层
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional, List

from .state_models import BatchProgressInfo, PipelineStatus


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


class BatchReporter:
    """批量处理进度报告器"""

    def __init__(self):
        self.batch_info = BatchProgressInfo()
        self._start_time = None

    def on_batch_start(self, total_count: int):
        """批量处理开始"""
        from datetime import datetime
        self._start_time = datetime.now()
        self.batch_info = BatchProgressInfo(total_count=total_count)
        self._report()

    def on_video_start(self, video_path: Path, index: int):
        """开始处理新视频"""
        self.batch_info.current_index = index
        self.batch_info.current_video = video_path.name
        self.batch_info.current_video_status = None
        self._report()

    def on_video_progress(self, status: PipelineStatus):
        """当前视频的进度更新"""
        self.batch_info.current_video_status = status
        self._report()

    def on_video_finish(self, video_path: Path, success: bool, error_msg: Optional[str] = None):
        """视频处理完成"""
        if success:
            self.batch_info.completed_count += 1
        else:
            self.batch_info.failed_count += 1
            if error_msg:
                print(f"✗ {video_path.name}: {error_msg}")
        self.batch_info.current_video = None
        self.batch_info.current_video_status = None
        self._report()

    def on_batch_finish(self, success: bool, error_msg: Optional[str] = None):
        """批量处理完成"""
        from datetime import datetime
        duration = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0

        print(f"\n{'='*50}")
        if success:
            print(f"批量处理完成: {self.batch_info.completed_count}/{self.batch_info.total_count} 成功")
        else:
            print(f"批量处理中断: {self.batch_info.completed_count}/{self.batch_info.total_count} 成功")
            if self.batch_info.failed_count > 0:
                print(f"失败: {self.batch_info.failed_count} 个")
        print(f"总耗时: {int(duration//60)}分{int(duration%60)}秒")
        print(f"{'='*50}")

    def _report(self):
        """输出进度报告（可被覆盖）"""
        if not hasattr(self, '_last_report'):
            self._last_report = 0

        # 每 10% 或视频切换时报告
        current_percent = int(self.batch_info.percent)
        if current_percent >= self._last_report + 10 or self.batch_info.current_video is None:
            self._last_report = current_percent
            print(f"进度: [{self._progress_bar(current_percent)}] {current_percent}% "
                  f"({self.batch_info.completed_count + self.batch_info.failed_count}/{self.batch_info.total_count})")

    def _progress_bar(self, percent: int, width: int = 20) -> str:
        """生成进度条字符串"""
        filled = int(width * percent / 100)
        return "█" * filled + "░" * (width - filled)
