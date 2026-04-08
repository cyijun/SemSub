"""
LLM 字幕处理器 - 统一的 LLM 处理逻辑

提取自 llm_postprocess_stage.py 和 srt_llm_processor.py 的公共逻辑
"""

import asyncio
from typing import Optional, List, Dict, Any

from ..config import LLMProcessConfig
from ..models import SubtitleLine
from ..progress import ProgressReporter, PipelineStage, StageProgress, SilentProgressReporter
from ..prompts import PromptManager
from .base import LLMConfig, SubtitleBatch, LLMOutputMode, PromptTemplate
from .openai_compatible import OpenAICompatibleProvider


class LLMSubtitleProcessor:
    """
    统一的 LLM 字幕处理器

    支持：
    1. 纠错优化
    2. 翻译
    3. 双语输出

    被以下模块使用：
    - llm_postprocess_stage.py - 管道阶段
    - srt_llm_processor.py - 独立 SRT 处理
    """

    def __init__(self, config: LLMProcessConfig):
        """
        初始化处理器

        Args:
            config: LLM 处理配置
        """
        self.config = config
        self.provider: Optional[OpenAICompatibleProvider] = None
        self.prompt_manager = PromptManager()

    def _init_provider(self) -> None:
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

    def process(
        self,
        lines: List[SubtitleLine],
        reporter: Optional[ProgressReporter] = None,
        template: Optional[PromptTemplate] = None,
    ) -> tuple[List[SubtitleLine], Dict[str, Any]]:
        """
        处理字幕列表

        Args:
            lines: 字幕行列表
            reporter: 进度报告器
            template: 提示词模板（可选，默认使用 config.prompt_template）

        Returns:
            (处理后字幕, 统计信息)
        """
        if reporter is None:
            reporter = SilentProgressReporter()

        # 获取提示词模板
        if template is None:
            template = self.prompt_manager.get_template(self.config.prompt_template)
        if template is None:
            template = self.prompt_manager.get_template("correct.zh")
            reporter.on_log("使用默认模板: correct.zh")

        # 检查配置
        if not self.config.enabled:
            reporter.on_log("LLM 后处理未启用，跳过处理")
            return lines, {"enabled": False, "total_lines": len(lines)}

        if not self.config.api_key or not self.config.base_url:
            reporter.on_log("LLM 未配置 API Key 或 Base URL，跳过处理", "warning")
            return lines, {"enabled": True, "skipped": True, "reason": "未配置 API Key 或 Base URL", "total_lines": len(lines)}

        self._init_provider()

        # 分批处理
        reporter.on_stage_start(PipelineStage.LLM_POSTPROCESS, len(lines))
        reporter.on_log(f"开始 LLM 后处理，共 {len(lines)} 行，批次大小: {self.config.batch_size}")

        all_processed: List[SubtitleLine] = []
        batch_size = self.config.batch_size
        failed_count = 0

        for i in range(0, len(lines), batch_size):
            reporter.check_cancelled()

            batch_end = min(i + batch_size, len(lines))
            batch = lines[i:batch_end]

            reporter.on_progress(StageProgress.create(
                PipelineStage.LLM_POSTPROCESS,
                i,
                len(lines),
                f"处理第 {i+1}-{batch_end} 行"
            ))

            # 构建批次数据
            subtitle_batch = SubtitleBatch(
                lines=batch,
                context_before="".join(l.text for l in lines[max(0, i-2):i]),
            )

            # 调用 LLM
            try:
                processed = asyncio.run(self._process_batch(subtitle_batch, template))
                all_processed.extend(processed)
            except RuntimeError as e:
                # API 错误（如认证失败、超时等）- 记录并使用原文
                reporter.on_log(f"LLM API 错误: {e}，使用原文", "warning")
                all_processed.extend(batch)
                failed_count += len(batch)
            except Exception as e:
                # 意外错误 - 记录为错误级别
                reporter.on_log(f"LLM 处理意外错误: {type(e).__name__}: {e}，使用原文", "error")
                all_processed.extend(batch)
                failed_count += len(batch)

        # 重新编号
        for i, line in enumerate(all_processed, 1):
            line.index = i

        # 统计
        changed_count = sum(
            1 for orig, new in zip(lines, all_processed)
            if orig.text != new.text
        )

        reporter.on_progress(StageProgress.create(
            PipelineStage.LLM_POSTPROCESS,
            len(lines),
            len(lines),
            f"LLM 后处理完成，修改 {changed_count} 行"
        ))

        reporter.on_stage_complete(PipelineStage.LLM_POSTPROCESS, {
            "total": len(lines),
            "changed": changed_count,
            "failed": failed_count,
        })

        return all_processed, {
            "enabled": True,
            "total_lines": len(lines),
            "changed_lines": changed_count,
            "failed_lines": failed_count,
            "change_ratio": round(changed_count / len(lines) * 100, 1) if lines else 0,
        }

    async def _process_batch(self, batch: SubtitleBatch, template: PromptTemplate) -> List[SubtitleLine]:
        """处理单个批次"""
        mode_map = {
            "correct": LLMOutputMode.CORRECT,
            "translate": LLMOutputMode.TRANSLATE,
            "bilingual": LLMOutputMode.BILINGUAL,
        }
        mode = mode_map.get(self.config.output_mode, LLMOutputMode.CORRECT)

        return await self.provider.process_batch(batch, template, mode)

    async def health_check(self) -> bool:
        """
        检查 LLM 服务健康状态

        Returns:
            True 如果服务正常
        """
        if not self.config.enabled or not self.config.api_key or not self.config.base_url:
            return False

        if self.provider is None:
            self._init_provider()

        return await self.provider.health_check()

    def get_available_templates(self) -> Dict[str, str]:
        """
        获取可用的提示词模板列表

        Returns:
            模板名称到描述的映射
        """
        return self.prompt_manager.list_templates()

    def cleanup(self):
        """清理资源"""
        self.provider = None
