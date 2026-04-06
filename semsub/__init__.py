"""
SemSub - 智能字幕生成器

一个兼具命令行和 GUI 的字幕生成软件，支持：
- VAD 语音分割 (Silero)
- ASR 语音识别 (Qwen3-ASR)
- 字幕优化合并
- LLM 后处理（翻译/纠错）
"""

__version__ = "1.0.0"
__author__ = "SemSub Team"

from .core.config import PipelineConfig
from .core.pipeline import SubtitlePipeline

__all__ = ["PipelineConfig", "SubtitlePipeline"]
