"""
OpenAI 兼容接口实现
支持 DeepSeek、Kimi、通义千问等国内 API
"""

import asyncio
from typing import List

from openai import AsyncOpenAI, APIError

from .base import LLMProvider, LLMConfig, SubtitleBatch, PromptTemplate, LLMOutputMode
from ..models import SubtitleLine


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容接口提供商"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout,
        )

    async def process_batch(
        self,
        batch: SubtitleBatch,
        prompt_template: PromptTemplate,
        mode: LLMOutputMode,
    ) -> List[SubtitleLine]:
        """处理一批字幕"""
        messages = self._build_messages(batch, prompt_template)

        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )

            content = response.choices[0].message.content
            return self._parse_response(content, batch.lines, mode)

        except APIError as e:
            raise RuntimeError(f"API 错误: {e}")

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 简单测试：调用 models 列表
            await self.client.models.list()
            return True
        except Exception:
            return False

    def _parse_response(
        self,
        content: str,
        original_lines: List[SubtitleLine],
        mode: LLMOutputMode,
    ) -> List[SubtitleLine]:
        """解析 LLM 响应"""
        import re

        processed_lines = []

        # 策略1：提取 [数字] 内容 格式的行
        pattern = r'^\[(\d+)\]\s*(.+?)$'
        matches = []
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            match = re.match(pattern, line)
            if match:
                idx = int(match.group(1))
                text = match.group(2).strip()
                # 过滤掉 LLM 的额外说明（通常包含括号或特殊标记）
                if text and not text.startswith('（') and not text.startswith('('):
                    matches.append((idx, text))

        if matches and len(matches) >= len(original_lines) * 0.5:
            # 使用匹配结果，按序号处理
            for idx, text in matches:
                if 0 <= idx < len(original_lines):
                    original = original_lines[idx]
                    processed_lines.append(self._create_processed_line(
                        original, text, mode
                    ))
        else:
            # 策略2：简单按行分割，过滤掉明显不是字幕的行
            lines = []
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                # 跳过 LLM 的说明文字（通常以括号开头或包含特定关键词）
                if line.startswith('（') or line.startswith('('):
                    continue
                if '可能存在' in line or '故未修改' in line or '句子不完整' in line:
                    continue
                lines.append(line)

            for i, original in enumerate(original_lines):
                if i < len(lines):
                    processed_lines.append(self._create_processed_line(
                        original, lines[i], mode
                    ))
                else:
                    processed_lines.append(original)

        return processed_lines

    def _create_processed_line(
        self,
        original: SubtitleLine,
        new_text: str,
        mode: LLMOutputMode,
    ) -> SubtitleLine:
        """创建处理后的字幕行"""
        line = SubtitleLine(
            index=original.index,
            start=original.start,
            end=original.end,
            text=new_text,
            words=original.words,
        )

        if mode == LLMOutputMode.BILINGUAL:
            line.original_text = original.text
            line.is_translated = True
        elif mode == LLMOutputMode.TRANSLATE:
            line.original_text = original.text
            line.text = new_text
            line.is_translated = True
        else:  # CORRECT
            line.original_text = original.text if new_text != original.text else ""

        return line
