"""
数据模型定义
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class WordItem:
    """词级对齐结果"""
    text: str
    start: float
    end: float

    def __post_init__(self):
        # 确保时间戳合理
        if self.end < self.start:
            self.end = self.start + 0.1


@dataclass
class TranscriptSegment:
    """转录片段 - 包含完整文本（含标点）和字级别时间戳"""
    start: float
    end: float
    text: str  # 完整文本，含标点
    words: List[WordItem]  # 字级别时间戳（可能不含标点）

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class SubtitleLine:
    """字幕行"""
    index: int
    start: float
    end: float
    text: str
    words: List[WordItem] = field(default_factory=list)
    # LLM 后处理相关
    original_text: str = ""  # 原文（如果经过翻译/纠错）
    is_translated: bool = False
    translation_confidence: float = 0.0

    def to_srt(self) -> str:
        """转换为 SRT 格式"""
        return f"{self.index}\n{self._fmt_time(self.start)} --> {self._fmt_time(self.end)}\n{self.text}\n"

    def to_vtt(self) -> str:
        """转换为 WebVTT 格式"""
        return f"{self._fmt_time(self.start, vtt=True)} --> {self._fmt_time(self.end, vtt=True)}\n{self.text}\n"

    @staticmethod
    def _fmt_time(seconds: float, vtt: bool = False) -> str:
        """格式化时间"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        if vtt:
            return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace(".", ",")

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def char_count(self) -> int:
        """字符数（中文算1个，英文算1个）"""
        return len(self.text.replace(" ", ""))

    @property
    def reading_speed(self) -> float:
        """阅读速度（字符/秒）"""
        if self.duration <= 0:
            return 0
        return self.char_count / self.duration

    @classmethod
    def from_dict(cls, data: dict) -> "SubtitleLine":
        """从字典创建"""
        words = [WordItem(**w) for w in data.get("words", [])]
        return cls(
            index=data["index"],
            start=data["start"],
            end=data["end"],
            text=data["text"],
            words=words,
            original_text=data.get("original_text", ""),
            is_translated=data.get("is_translated", False),
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "index": self.index,
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "words": [{"text": w.text, "start": w.start, "end": w.end} for w in self.words],
            "original_text": self.original_text,
            "is_translated": self.is_translated,
        }
