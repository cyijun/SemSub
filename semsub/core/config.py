"""
配置数据类定义
使用 Pydantic 进行类型验证
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from pathlib import Path


class VADConfig(BaseModel):
    """VAD 配置"""
    threshold: float = 0.5
    min_speech_duration_ms: int = 250
    min_silence_duration_ms: int = 500


class SubtitleConfig(BaseModel):
    """字幕优化配置"""
    max_chars: int = 20           # 中文每行最大字符
    max_chars_en: int = 40        # 英文每行最大字符
    min_chars: int = 10           # 每行最小字符数（防止切太碎）
    max_duration: float = 6.0     # 每行最大显示时长
    min_duration: float = 1.0     # 每行最小显示时长
    gap_threshold: float = 0.3    # VAD 片段合并阈值
    max_segment_duration: float = 12.0
    max_gap_within_line: float = 0.5
    target_reading_speed: float = 6.0  # 目标阅读速度（字符/秒）
    # 新增：控制字幕切换频率的参数
    prefer_longer_lines: bool = True   # 优先合并成更长的行
    min_line_duration: float = 2.0     # 每行最少显示2秒（避免切换太快）


class ASRConfig(BaseModel):
    """ASR 配置"""
    model_path: str = "/mnt/g/models/Qwen3-ASR-1.7B"
    aligner_path: str = "/mnt/g/models/Qwen3-ForcedAligner-0.6B"
    device: str = "cuda:0"
    batch_size: int = 8
    language: Optional[str] = None  # None=自动检测


class LLMProcessConfig(BaseModel):
    """LLM 后处理配置"""
    enabled: bool = False
    provider: str = "openai_compatible"
    api_key: str = ""
    base_url: str = ""
    model: str = "deepseek-chat"
    prompt_template: str = "correct.zh"
    output_mode: Literal["correct", "translate", "bilingual"] = "correct"
    batch_size: int = 10
    preserve_timing: bool = True
    max_tokens: int = 4096
    temperature: float = 0.3
    timeout: int = 60
    target_language: str = "English"  # 翻译目标语言


class OutputConfig(BaseModel):
    """输出配置"""
    format: Literal["srt", "vtt", "json"] = "srt"
    save_intermediate: bool = False
    output_dir: Optional[str] = None  # None 表示与视频相同目录


class PipelineConfig(BaseModel):
    """完整的管道配置"""
    vad: VADConfig = Field(default_factory=VADConfig)
    subtitle: SubtitleConfig = Field(default_factory=SubtitleConfig)
    asr: ASRConfig = Field(default_factory=ASRConfig)
    llm: LLMProcessConfig = Field(default_factory=LLMProcessConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    def to_yaml(self) -> str:
        """导出为 YAML 格式"""
        import yaml
        return yaml.dump(self.model_dump(), allow_unicode=True, sort_keys=False)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "PipelineConfig":
        """从 YAML 加载"""
        import yaml
        data = yaml.safe_load(yaml_str)
        return cls(**data)

    def save_to_file(self, path: Path):
        """保存到文件"""
        path.write_text(self.to_yaml(), encoding="utf-8")

    @classmethod
    def load_from_file(cls, path: Path) -> "PipelineConfig":
        """从文件加载"""
        return cls.from_yaml(path.read_text(encoding="utf-8"))
