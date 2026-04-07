"""
SRT LLM 处理器 - 独立的 SRT 文件 LLM 后处理
无需 workspace，直接处理 SRT 文件
"""

import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any

from .config import LLMProcessConfig
from .models import SubtitleLine
from .llm import LLMConfig, OpenAICompatibleProvider
from .llm.base import SubtitleBatch, LLMOutputMode, PromptTemplate
from .prompts import PromptManager
from .progress import ProgressReporter, PipelineStage, StageProgress, SilentProgressReporter
from .utils.srt_parser import parse_srt, write_srt


class SRTLLMProcessor:
    """
    独立的 SRT 文件 LLM 处理器

    功能：
    1. 读取 SRT 文件
    2. 使用 LLM 进行纠错/翻译/双语处理
    3. 输出处理后的 SRT 文件

    示例：
        config = LLMProcessConfig(
            enabled=True,
            api_key="your-key",
            base_url="https://api.example.com/v1",
            model="deepseek-chat",
            output_mode="correct",  # correct | translate | bilingual
            batch_size=10
        )
        processor = SRTLLMProcessor(config)
        processor.process_file("input.srt", "output.srt")
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

    def process_file(
        self,
        input_path: Path | str,
        output_path: Path | str,
        reporter: Optional[ProgressReporter] = None
    ) -> Dict[str, Any]:
        """
        处理 SRT 文件

        Args:
            input_path: 输入 SRT 文件路径
            output_path: 输出 SRT 文件路径
            reporter: 进度报告器（可选）

        Returns:
            处理统计信息字典
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        if reporter is None:
            reporter = SilentProgressReporter()

        # 检查是否启用
        if not self.config.enabled:
            reporter.on_log("LLM 后处理未启用，直接复制文件")
            # 直接复制文件
            content = input_path.read_text(encoding="utf-8")
            output_path.write_text(content, encoding="utf-8")
            return {
                "enabled": False,
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_lines": 0
            }

        # 检查配置
        if not self.config.api_key or not self.config.base_url:
            reporter.on_log("LLM 未配置 API Key 或 Base URL，跳过处理", "warning")
            content = input_path.read_text(encoding="utf-8")
            output_path.write_text(content, encoding="utf-8")
            return {
                "enabled": True,
                "skipped": True,
                "reason": "未配置 API Key 或 Base URL",
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_lines": 0
            }

        # 读取 SRT 文件
        reporter.on_log(f"读取 SRT 文件: {input_path}")
        content = input_path.read_text(encoding="utf-8")
        lines = parse_srt(content)

        if not lines:
            reporter.on_log("SRT 文件为空或解析失败", "warning")
            output_path.write_text(content, encoding="utf-8")
            return {
                "enabled": True,
                "input_path": str(input_path),
                "output_path": str(output_path),
                "total_lines": 0,
                "changed_lines": 0
            }

        reporter.on_log(f"解析到 {len(lines)} 行字幕")

        # 初始化 LLM 提供商
        self._init_provider()

        # 获取提示词模板
        template = self.prompt_manager.get_template(self.config.prompt_template)
        if template is None:
            template = self.prompt_manager.get_template("correct.zh")
            reporter.on_log(f"使用默认模板: correct.zh")

        # 处理字幕
        processed_lines = self._process_subtitles(lines, template, reporter)

        # 重新编号
        for i, line in enumerate(processed_lines, 1):
            line.index = i

        # 生成 SRT 内容并保存
        srt_content = write_srt(processed_lines)
        output_path.write_text(srt_content, encoding="utf-8")

        # 统计
        changed_count = sum(
            1 for orig, new in zip(lines, processed_lines)
            if orig.text != new.text
        )

        reporter.on_log(
            f"处理完成: 共 {len(lines)} 行, 修改 {changed_count} 行 "
            f"({changed_count / len(lines) * 100:.1f}%)"
        )

        return {
            "enabled": True,
            "input_path": str(input_path),
            "output_path": str(output_path),
            "total_lines": len(lines),
            "changed_lines": changed_count,
            "failed_lines": 0,  # SRT 处理不保留失败计数，失败时使用原文
            "change_ratio": round(changed_count / len(lines) * 100, 1) if lines else 0
        }

    def _process_subtitles(
        self,
        lines: List[SubtitleLine],
        template: PromptTemplate,
        reporter: ProgressReporter
    ) -> List[SubtitleLine]:
        """
        分批处理字幕

        Args:
            lines: 字幕行列表
            template: 提示词模板
            reporter: 进度报告器

        Returns:
            处理后的字幕行列表
        """
        reporter.on_stage_start(PipelineStage.LLM_POSTPROCESS, len(lines))
        reporter.on_log(
            f"开始 LLM 后处理，共 {len(lines)} 行，批次大小: {self.config.batch_size}"
        )

        all_processed: List[SubtitleLine] = []
        batch_size = self.config.batch_size

        for i in range(0, len(lines), batch_size):
            reporter.check_cancelled()

            batch_end = min(i + batch_size, len(lines))
            batch_lines = lines[i:batch_end]

            reporter.on_progress(StageProgress.create(
                PipelineStage.LLM_POSTPROCESS,
                i,
                len(lines),
                f"处理第 {i+1}-{batch_end} 行"
            ))

            # 构建批次数据
            subtitle_batch = SubtitleBatch(
                lines=batch_lines,
                context_before="".join(l.text for l in lines[max(0, i-2):i]),
            )

            # 调用 LLM 处理
            try:
                processed = asyncio.run(self._process_batch(subtitle_batch, template))
                all_processed.extend(processed)
            except Exception as e:
                reporter.on_log(f"LLM 处理批次失败: {e}，使用原文", "warning")
                all_processed.extend(batch_lines)

        reporter.on_stage_complete(PipelineStage.LLM_POSTPROCESS, {
            "total": len(lines),
            "processed": len(all_processed)
        })

        return all_processed

    async def _process_batch(
        self,
        batch: SubtitleBatch,
        template: PromptTemplate
    ) -> List[SubtitleLine]:
        """
        处理单个批次

        Args:
            batch: 字幕批次
            template: 提示词模板

        Returns:
            处理后的字幕行列表
        """
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
