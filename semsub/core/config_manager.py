"""
配置管理器
支持多层配置合并：命令行参数 > 项目配置 > 用户配置 > 预设
"""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

from .config import PipelineConfig, VADConfig, SubtitleConfig, ASRConfig, LLMProcessConfig, OutputConfig


@dataclass
class ConfigSource:
    """配置来源"""
    name: str
    path: Optional[Path]
    config: Dict[str, Any]


class ConfigManager:
    """配置管理器"""

    def __init__(self):
        self.user_config_dir = Path.home() / ".config" / "semsub"
        self.user_config_file = self.user_config_dir / "config.yaml"
        self.project_config_file = Path("./semsub.yaml")
        self.presets_dir = Path(__file__).parent.parent / "presets"

    def load(
        self,
        preset: Optional[str] = None,
        config_file: Optional[Path] = None,
        cli_overrides: Optional[Dict[str, Any]] = None
    ) -> PipelineConfig:
        """
        加载配置（按优先级合并）

        优先级（高 -> 低）：
        1. CLI 参数
        2. 指定配置文件
        3. 项目配置 (./semsub.yaml)
        4. 用户配置 (~/.config/semsub/config.yaml)
        5. 预设配置
        6. 默认配置

        Args:
            preset: 预设名称
            config_file: 指定配置文件路径
            cli_overrides: CLI 参数覆盖

        Returns:
            合并后的配置
        """
        # 1. 从默认配置开始
        config = PipelineConfig()

        # 2. 应用预设
        if preset:
            config = self._apply_preset(config, preset)

        # 3. 合并用户配置
        if self.user_config_file.exists():
            config = self._merge_config(config, self._load_yaml(self.user_config_file))

        # 4. 合并项目配置
        if self.project_config_file.exists():
            config = self._merge_config(config, self._load_yaml(self.project_config_file))

        # 5. 合并指定配置文件
        if config_file and config_file.exists():
            config = self._merge_config(config, self._load_yaml(config_file))

        # 6. 应用 CLI 覆盖
        if cli_overrides:
            config = self._apply_overrides(config, cli_overrides)

        return config

    def save_user_config(self, config: PipelineConfig):
        """保存到用户配置"""
        self.user_config_dir.mkdir(parents=True, exist_ok=True)
        self._save_yaml(config, self.user_config_file)

    def save_project_config(self, config: PipelineConfig):
        """保存到项目配置"""
        self._save_yaml(config, self.project_config_file)

    def list_presets(self) -> Dict[str, str]:
        """列出所有预设"""
        presets = {}
        if self.presets_dir.exists():
            for f in self.presets_dir.glob("*.yaml"):
                data = self._load_yaml(f)
                presets[f.stem] = data.get("name", f.stem)
        return presets

    def load_preset(self, name: str) -> Optional[Dict[str, Any]]:
        """加载预设"""
        preset_file = self.presets_dir / f"{name}.yaml"
        if preset_file.exists():
            return self._load_yaml(preset_file)
        return None

    def get_config_value(self, config: PipelineConfig, key: str) -> Any:
        """获取配置值（支持点号路径）"""
        parts = key.split(".")
        current = config
        for part in parts:
            if hasattr(current, part):
                current = getattr(current, part)
            else:
                return None
        return current

    def set_config_value(self, config: PipelineConfig, key: str, value: Any):
        """设置配置值（支持点号路径）"""
        parts = key.split(".")
        current = config
        for part in parts[:-1]:
            if hasattr(current, part):
                current = getattr(current, part)
            else:
                return False

        last_part = parts[-1]
        if hasattr(current, last_part):
            # 类型转换
            current_value = getattr(current, last_part)
            if isinstance(current_value, bool):
                value = value.lower() in ("true", "1", "yes", "on")
            elif isinstance(current_value, int):
                value = int(value)
            elif isinstance(current_value, float):
                value = float(value)
            setattr(current, last_part, value)
            return True
        return False

    def _apply_preset(self, config: PipelineConfig, preset_name: str) -> PipelineConfig:
        """应用预设"""
        preset_data = self.load_preset(preset_name)
        if preset_data:
            return self._merge_config(config, preset_data)
        return config

    def _merge_config(self, base: PipelineConfig, override: Dict[str, Any]) -> PipelineConfig:
        """合并配置"""
        # 创建副本
        data = self._config_to_dict(base)

        # 递归合并
        def merge_dict(base_dict, override_dict):
            for key, value in override_dict.items():
                if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                    merge_dict(base_dict[key], value)
                else:
                    base_dict[key] = value

        merge_dict(data, override)

        # 转换回对象
        return PipelineConfig(**data)

    def _apply_overrides(self, config: PipelineConfig, overrides: Dict[str, Any]) -> PipelineConfig:
        """应用 CLI 覆盖"""
        for key, value in overrides.items():
            self.set_config_value(config, key, value)
        return config

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """加载 YAML 文件"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def _save_yaml(self, config: PipelineConfig, path: Path):
        """保存 YAML 文件"""
        data = self._config_to_dict(config)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    def _config_to_dict(self, config: PipelineConfig) -> Dict[str, Any]:
        """配置转字典"""
        return {
            "vad": {
                "threshold": config.vad.threshold,
                "min_speech_duration_ms": config.vad.min_speech_duration_ms,
                "min_silence_duration_ms": config.vad.min_silence_duration_ms,
            },
            "subtitle": {
                "max_chars": config.subtitle.max_chars,
                "max_chars_en": config.subtitle.max_chars_en,
                "min_chars": config.subtitle.min_chars,
                "max_duration": config.subtitle.max_duration,
                "min_duration": config.subtitle.min_duration,
                "gap_threshold": config.subtitle.gap_threshold,
                "max_segment_duration": config.subtitle.max_segment_duration,
                "max_gap_within_line": config.subtitle.max_gap_within_line,
                "target_reading_speed": config.subtitle.target_reading_speed,
                "prefer_longer_lines": config.subtitle.prefer_longer_lines,
                "min_line_duration": config.subtitle.min_line_duration,
            },
            "asr": {
                "model_path": config.asr.model_path,
                "aligner_path": config.asr.aligner_path,
                "device": config.asr.device,
                "batch_size": config.asr.batch_size,
                "language": config.asr.language,
            },
            "llm": {
                "enabled": config.llm.enabled,
                "provider": config.llm.provider,
                "api_key": config.llm.api_key,
                "base_url": config.llm.base_url,
                "model": config.llm.model,
                "prompt_template": config.llm.prompt_template,
                "output_mode": config.llm.output_mode,
                "batch_size": config.llm.batch_size,
                "preserve_timing": config.llm.preserve_timing,
                "max_tokens": config.llm.max_tokens,
                "temperature": config.llm.temperature,
                "timeout": config.llm.timeout,
                "target_language": config.llm.target_language,
            },
            "output": {
                "format": config.output.format,
                "save_intermediate": config.output.save_intermediate,
                "output_dir": config.output.output_dir,
            },
        }


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """获取全局配置管理器"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
