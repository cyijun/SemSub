"""
LLM 后处理阶段 - 翻译/纠错/润色
支持 Workspace
"""

import asyncio
from pathlib import Path
from typing import Optional, List, Dict

from .base import WorkspacePipelineStage
from ..progress import ProgressReporter, PipelineStage, StageProgress
from ..workspace import StageContext
from ..state_models import ArtifactInfo
from ..config import LLMProcessConfig
from ..models import SubtitleLine
from ..llm import LLMConfig, OpenAICompatibleProvider
from ..prompts import PromptManager


class LLMPostprocessStage(WorkspacePipelineStage):
    """LLM 后处理阶段"""

    name = "LLM 后处理"
    stage_id = "05_llm_postprocess"

    def __init__(self, config: LLMProcessConfig):
        self.config = config
        self.provider = None
        self.prompt_manager = PromptManager()

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

    def _init_provider(self):
        """初始化 LLM 提供商"""
        if self.provider is not None:
            return

        llm_config = LLMConfig(
            provider=self.config.provider,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            timeout=self.config.timeout,
        )

        self.provider = OpenAICompatibleProvider(llm_config)

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

        if not self.config.enabled:
            if reporter:
                reporter.on_log("LLM 后处理未启用，跳过")
            # 直接复制输入到输出
            ctx.save_artifact("subtitles", subtitles_data, "json")
            return {
                "artifacts": {
                    "subtitles": ArtifactInfo(
                        path="subtitles.json",
                        type="json"
                    )
                },
                "statistics": {
                    "enabled": False,
                    "total_lines": len(lines)
                }
            }

        if not self.config.api_key or not self.config.base_url:
            if reporter:
                reporter.on_log("LLM 未配置 API Key 或 Base URL，跳过", "warning")
            ctx.save_artifact("subtitles", subtitles_data, "json")
            return {
                "artifacts": {
                    "subtitles": ArtifactInfo(
                        path="subtitles.json",
                        type="json"
                    )
                },
                "statistics": {
                    "skipped": True,
                    "reason": "未配置 API Key 或 Base URL",
                    "total_lines": len(lines)
                }
            }

        self._init_provider()

        # 获取提示词模板
        template = self.prompt_manager.get_template(self.config.prompt_template)
        if template is None:
            template = self.prompt_manager.get_template("correct.zh")

        if reporter:
            reporter.on_stage_start(PipelineStage.LLM_POSTPROCESS, len(lines))
            reporter.on_log(f"开始 LLM 后处理，共 {len(lines)} 行，批次大小: {self.config.batch_size}")

        # 分批处理
        all_processed = []
        batch_size = self.config.batch_size
        processed_count = 0
        failed_count = 0

        for i in range(0, len(lines), batch_size):
            if reporter:
                reporter.check_cancelled()

            batch_end = min(i + batch_size, len(lines))
            batch = lines[i:batch_end]

            if reporter:
                reporter.on_progress(StageProgress.create(
                    PipelineStage.LLM_POSTPROCESS,
                    i,
                    len(lines),
                    f"处理第 {i+1}-{batch_end} 行"
                ))

            # 构建批次数据
            from ..llm.base import SubtitleBatch
            subtitle_batch = SubtitleBatch(
                lines=batch,
                context_before="".join(l.text for l in lines[max(0, i-2):i]),
            )

            # 调用 LLM
            try:
                processed = asyncio.run(self._process_batch(subtitle_batch, template))
                all_processed.extend(processed)
                processed_count += len(processed)
            except Exception as e:
                if reporter:
                    reporter.on_log(f"LLM 处理批次失败: {e}，使用原文", "warning")
                all_processed.extend(batch)
                failed_count += len(batch)

        # 重新编号
        for i, line in enumerate(all_processed, 1):
            line.index = i

        # 保存结果
        result_data = [self._line_to_dict(line) for line in all_processed]
        ctx.save_artifact("subtitles", result_data, "json")

        # 统计
        changed_count = sum(
            1 for orig, new in zip(lines, all_processed)
            if orig.text != new.text
        )

        if reporter:
            reporter.on_progress(StageProgress.create(
                PipelineStage.LLM_POSTPROCESS,
                len(lines),
                len(lines),
                f"LLM 后处理完成，修改 {changed_count} 行"
            ))

        return {
            "artifacts": {
                "subtitles": ArtifactInfo(
                    path="subtitles.json",
                    type="json"
                )
            },
            "statistics": {
                "enabled": True,
                "total_lines": len(lines),
                "changed_lines": changed_count,
                "failed_lines": failed_count,
                "change_ratio": round(changed_count / len(lines) * 100, 1) if lines else 0
            }
        }

    async def _process_batch(self, batch, template):
        """处理单个批次"""
        from ..llm.base import LLMOutputMode

        mode_map = {
            "correct": LLMOutputMode.CORRECT,
            "translate": LLMOutputMode.TRANSLATE,
            "bilingual": LLMOutputMode.BILINGUAL,
        }
        mode = mode_map.get(self.config.output_mode, LLMOutputMode.CORRECT)

        return await self.provider.process_batch(batch, template, mode)

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
        self.provider = None
