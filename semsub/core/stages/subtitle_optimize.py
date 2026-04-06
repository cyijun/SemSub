"""
字幕优化阶段 - 使用 SubtitleMerger
支持 Workspace
"""

from typing import Optional, List, Dict
import json

from .base import WorkspacePipelineStage
from ..progress import ProgressReporter, PipelineStage, StageProgress
from ..workspace import StageContext
from ..state_models import ArtifactInfo
from ..config import SubtitleConfig
from ..models import WordItem, SubtitleLine
from ..merger import SubtitleMerger


class SubtitleOptimizeStage(WorkspacePipelineStage):
    """字幕优化阶段"""

    name = "字幕优化"
    stage_id = "04_subtitle_optimize"

    def __init__(self, config: SubtitleConfig):
        self.config = config
        self.merger = SubtitleMerger(config)

    def get_input_spec(self):
        return {
            "dependencies": ["02_vad_split", "03_asr_transcribe"],
            "artifacts": {
                "segments": {"type": "json", "from_stage": "02_vad_split"},
                "transcripts": {"type": "json", "from_stage": "03_asr_transcribe"}
            },
            "parameters": {
                "max_chars": int,
                "max_duration": float,
                "min_duration": float,
                "gap_threshold": float
            }
        }

    def get_output_spec(self):
        return {
            "artifacts": {
                "subtitles": {"type": "json", "description": "优化后的字幕行"}
            }
        }

    def execute(
        self,
        ctx: StageContext,
        reporter: Optional[ProgressReporter] = None
    ) -> dict:
        """
        优化字幕

        Args:
            ctx: 阶段上下文
            reporter: 进度报告器

        Returns:
            {"artifacts": {"subtitles": [...]}, "statistics": {...}}
        """
        # 加载输入
        segments = ctx.load_artifact("segments", from_input=True)
        transcripts = ctx.load_artifact("transcripts", from_input=True)

        if segments is None:
            raise FileNotFoundError("找不到输入 segments 文件")
        if transcripts is None:
            raise FileNotFoundError("找不到输入 transcripts 文件")

        if reporter:
            reporter.on_stage_start(PipelineStage.SUBTITLE_OPTIMIZE, 1)
            reporter.on_log("开始优化字幕...")

        # 转换 transcripts 为 TranscriptSegment 对象
        from ..models import TranscriptSegment
        transcript_segments = []
        for t in transcripts:
            words = [WordItem(**w) for w in t.get("words", [])]
            transcript_segments.append(TranscriptSegment(
                start=t["start"],
                end=t["end"],
                text=t["text"],
                words=words
            ))

        # 合并所有字级时间戳
        all_words = []
        for seg in transcript_segments:
            all_words.extend(seg.words)
        all_words.sort(key=lambda w: w.start)

        # 使用 merger 处理
        lines = self.merger.process(segments, all_words)

        # 转换为字典列表
        subtitles_data = [self._line_to_dict(line) for line in lines]

        # 保存结果
        ctx.save_artifact("subtitles", subtitles_data, "json")

        # 计算统计信息
        total_chars = sum(len(line.text) for line in lines)
        avg_chars = round(total_chars / len(lines), 1) if lines else 0
        avg_duration = round(sum(line.duration for line in lines) / len(lines), 2) if lines else 0

        # 统计以标点结尾的行数
        punct_ending = sum(
            1 for line in lines
            if line.text and line.text[-1] in '。！？.!?""''）]'
        )
        punct_ratio = round(punct_ending / len(lines) * 100, 1) if lines else 0

        if reporter:
            reporter.on_progress(StageProgress.create(
                PipelineStage.SUBTITLE_OPTIMIZE, 1, 1,
                f"优化完成，生成 {len(lines)} 行字幕"
            ))

        return {
            "artifacts": {
                "subtitles": ArtifactInfo(
                    path="subtitles.json",
                    type="json"
                )
            },
            "statistics": {
                "total_lines": len(lines),
                "total_chars": total_chars,
                "avg_chars_per_line": avg_chars,
                "avg_duration_sec": avg_duration,
                "punct_ending_lines": punct_ending,
                "punct_ending_ratio": punct_ratio
            }
        }

    def _line_to_dict(self, line: SubtitleLine) -> dict:
        """转换 SubtitleLine 为字典"""
        return {
            "index": line.index,
            "start": line.start,
            "end": line.end,
            "text": line.text,
            "words": [{"text": w.text, "start": w.start, "end": w.end} for w in line.words],
            "original_text": line.original_text,
            "is_translated": line.is_translated
        }
