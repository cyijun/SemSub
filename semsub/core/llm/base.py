"""
LLM 提供商抽象接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List
from enum import Enum

from ..models import SubtitleLine


class LLMOutputMode(Enum):
    """LLM 输出模式"""
    CORRECT = "correct"       # 仅纠错，保持原文语言
    TRANSLATE = "translate"   # 翻译为目标语言
    BILINGUAL = "bilingual"   # 双语输出（原文+译文）


@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: str = "openai_compatible"
    api_key: str = ""
    base_url: str = ""
    model: str = "deepseek-chat"
    max_tokens: int = 4096
    temperature: float = 0.3
    timeout: int = 60


@dataclass
class SubtitleBatch:
    """待处理的一组字幕"""
    lines: List[SubtitleLine]
    context_before: str = ""  # 前文（用于连贯性）
    context_after: str = ""   # 后文


class PromptTemplate:
    """提示词模板"""
    def __init__(
        self,
        name: str,
        description: str,
        system_prompt: str,
        user_prompt: str,
        mode: LLMOutputMode = LLMOutputMode.CORRECT,
    ):
        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.mode = mode

    def format(self, subtitles: List[SubtitleLine], **kwargs) -> str:
        """格式化提示词"""
        text = "\n".join(f"[{i}] {line.text}" for i, line in enumerate(subtitles))
        return self.user_prompt.format(text=text, **kwargs)


class LLMProvider(ABC):
    """LLM 提供商抽象接口"""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    async def process_batch(
        self,
        batch: SubtitleBatch,
        prompt_template: PromptTemplate,
        mode: LLMOutputMode,
    ) -> List[SubtitleLine]:
        """处理一批字幕"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass

    def _build_messages(
        self,
        batch: SubtitleBatch,
        prompt_template: PromptTemplate,
    ) -> List[dict]:
        """构建消息列表"""
        messages = [
            {"role": "system", "content": prompt_template.system_prompt},
        ]

        user_content = prompt_template.format(batch.lines)

        if batch.context_before:
            user_content = f"前文:\n{batch.context_before}\n\n{user_content}"

        messages.append({"role": "user", "content": user_content})
        return messages
