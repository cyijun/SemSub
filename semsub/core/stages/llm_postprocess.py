"""
LLM 后处理阶段 - 翻译/纠错/润色
支持 Workspace
"""

from pathlib import Path
from typing import Optional

from .base import WorkspacePipelineStage
from ..progress import ProgressReporter
from ..workspace import StageContext
from ..state_models import ArtifactInfo
from ..config import LLMProcessConfig
from ..models import SubtitleLine
from ..llm import LLMSubtitleProcessor


class LLMPostprocessStage(WorkspacePipelineStage):
    """LLM 后处理阶段"""

    name = "LLM 后处理"
    stage_id = "05_llm_postprocess"

    def __init__(self, config: LLMProcessConfig):
        self.config = config
        self.processor = LLMSubtitleProcessor(config)

    def get_input_spec(self):
        return {
            "dependencies": ["04_subtitle_optimize"],
            "artifacts": {
                "subtitles": {"type": "json", "from_stage": "04_subtitle_optimize"}
            },
            "parameters": {
                "enabled": bool,
                "provider": str,
                "model": str,
                "batch_size": int,
                "output_mode": str
            }
        }

    def get_output_spec(self):
        return {
            "artifacts": {
                "subtitles": {"type": "json", "description": "后处理后的字幕"}
            }
        }

    def execute(
        self,
        ctx: StageContext,
        reporter: Optional[ProgressReporter] = None
    ) -> dict:
        """
        执行 LLM 后处理

        Args:
            ctx: 阶段上下文
            reporter: 进度报告器

        Returns:
            {"artifacts": {"subtitles": [...]}, "statistics": {...}}
        """
        # 加载输入字幕
        subtitles_data = ctx.load_artifact("subtitles", from_input=True)
        if subtitles_data is None:
            raise FileNotFoundError("找不到输入字幕文件")

        # 转换为 SubtitleLine 对象
        lines = [SubtitleLine.from_dict(d) for d in subtitles_data]

        # 使用统一处理器处理
        processed_lines, stats = self.processor.process(lines, reporter)

        # 保存结果
        result_data = [self._line_to_dict(line) for line in processed_lines]
        ctx.save_artifact("subtitles", result_data, "json")

        return {
            "artifacts": {
                "subtitles": ArtifactInfo(
                    path="subtitles.json",
                    type="json"
                )
            },
            "statistics": stats
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

    def cleanup(self):
        """清理资源"""
        self.processor.cleanup()
