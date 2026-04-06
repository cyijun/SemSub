"""
提示词模板管理
"""

import yaml
from pathlib import Path
from typing import Dict, Optional

from ..llm.base import PromptTemplate, LLMOutputMode


class PromptManager:
    """提示词模板管理器"""

    def __init__(self, templates_dir: Optional[Path] = None):
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "templates"
        self.templates_dir = templates_dir
        self._templates: Dict[str, PromptTemplate] = {}
        self._load_builtin_templates()

    def _load_builtin_templates(self):
        """加载内置模板"""
        # 中文纠错模板
        self._templates["correct.zh"] = PromptTemplate(
            name="correct.zh",
            description="中文纠错优化",
            system_prompt='你是一位专业的字幕校对专家。请仔细审阅以下字幕文本，纠正其中的错误：\n1. 同音字错误（如"背景"应为"北京"）\n2. 标点符号使用不当\n3. 明显的语法错误\n4. 专业术语拼写错误\n\n请保持原文的语气和风格，仅纠正明显的错误。输出格式：每行前加 [序号]',
            user_prompt='请纠正以下字幕文本中的错误：\n\n{text}\n\n请按原格式返回纠正后的文本。',
            mode=LLMOutputMode.CORRECT,
        )

        # 英文翻译模板
        self._templates["translate.en"] = PromptTemplate(
            name="translate.en",
            description="翻译成英文",
            system_prompt='你是一位专业的字幕翻译专家。请将以下中文字幕翻译成地道的英文。\n要求：\n1. 翻译要准确传达原意\n2. 使用简洁自然的英文表达\n3. 考虑字幕的阅读速度和长度\n4. 保持口语化风格\n\n输出格式：每行前加 [序号]',
            user_prompt='请将以下中文字幕翻译成英文：\n\n{text}\n\n请按原格式返回翻译后的文本。',
            mode=LLMOutputMode.TRANSLATE,
        )

        # 双语字幕模板
        self._templates["bilingual"] = PromptTemplate(
            name="bilingual",
            description="双语字幕",
            system_prompt='你是一位专业的字幕翻译专家。请将以下字幕翻译成目标语言，并输出双语格式。\n格式要求：原文 | 译文\n\n要求：\n1. 翻译准确传达原意\n2. 使用简洁自然的表达\n3. 双语之间用 | 分隔\n\n输出格式：每行前加 [序号]',
            user_prompt='请将以下字幕翻译成目标语言，输出双语格式：\n\n{text}\n\n请按 [序号] 原文 | 译文 的格式返回。',
            mode=LLMOutputMode.BILINGUAL,
        )

    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """获取模板"""
        return self._templates.get(name)

    def list_templates(self) -> Dict[str, str]:
        """列出所有模板"""
        return {name: t.description for name, t in self._templates.items()}

    def add_template(self, template: PromptTemplate):
        """添加模板"""
        self._templates[template.name] = template

    def load_from_file(self, path: Path) -> PromptTemplate:
        """从 YAML 文件加载模板"""
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        template = PromptTemplate(
            name=data["name"],
            description=data["description"],
            system_prompt=data["system_prompt"],
            user_prompt=data["user_prompt"],
            mode=LLMOutputMode(data.get("mode", "correct")),
        )
        self._templates[template.name] = template
        return template
