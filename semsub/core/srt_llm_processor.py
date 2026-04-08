"""
SRT LLM 处理器 - 独立的 SRT 文件 LLM 后处理
无需 workspace，直接处理 SRT 文件

使用统一的 LLMSubtitleProcessor 实现
"""

from pathlib import Path
from typing import Optional, Dict, Any

from .config import LLMProcessConfig
from .models import SubtitleLine
from .llm import LLMSubtitleProcessor
from .progress import ProgressReporter, SilentProgressReporter
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

    注意：此实现使用 LLMSubtitleProcessor 作为底层处理引擎
    """

    def __init__(self, config: LLMProcessConfig):
        """
        初始化处理器

        Args:
            config: LLM 处理配置
        """
        self.config = config
        self.processor = LLMSubtitleProcessor(config)

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

        # 使用统一处理器处理字幕
        processed_lines, stats = self.processor.process(lines, reporter)

        # 重新编号
        for i, line in enumerate(processed_lines, 1):
            line.index = i

        # 生成 SRT 内容并保存
        srt_content = write_srt(processed_lines)
        output_path.write_text(srt_content, encoding="utf-8")

        reporter.on_log(
            f"处理完成: 共 {stats['total_lines']} 行, 修改 {stats['changed_lines']} 行 "
            f"({stats.get('change_ratio', 0):.1f}%)"
        )

        return {
            **stats,
            "input_path": str(input_path),
            "output_path": str(output_path),
        }

    async def health_check(self) -> bool:
        """
        检查 LLM 服务健康状态

        Returns:
            True 如果服务正常
        """
        return await self.processor.health_check()

    def get_available_templates(self) -> Dict[str, str]:
        """
        获取可用的提示词模板列表

        Returns:
            模板名称到描述的映射
        """
        return self.processor.get_available_templates()

    def cleanup(self):
        """清理资源"""
        self.processor.cleanup()
