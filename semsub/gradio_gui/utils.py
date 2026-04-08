"""
工具函数
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import asdict

from ..core.config import PipelineConfig, VADConfig, SubtitleConfig, ASRConfig, LLMProcessConfig, OutputConfig
from ..core.config_manager import get_config_manager
from ..core.batch_scanner import VideoScanner


# 预设配置
PRESETS = {
    "movie": {
        "name": "电影",
        "icon": "🎬",
        "description": "适合快节奏对话的电影，字幕切换较快",
        "config": {
            "subtitle": {"max_chars": 40, "max_duration": 6.0, "gap_threshold": 0.3, "min_silence_duration_ms": 500},
            "vad": {"threshold": 0.5, "min_speech_duration_ms": 250, "min_silence_duration_ms": 500},
        }
    },
    "documentary": {
        "name": "纪录片",
        "icon": "📹",
        "description": "适合慢速旁白，字幕保持时间较长",
        "config": {
            "subtitle": {"max_chars": 35, "max_duration": 7.0, "gap_threshold": 0.5, "min_silence_duration_ms": 800},
            "vad": {"threshold": 0.5, "min_speech_duration_ms": 300, "min_silence_duration_ms": 800},
        }
    },
    "animation": {
        "name": "动画",
        "icon": "🎨",
        "description": "适合快速对白，字幕精简",
        "config": {
            "subtitle": {"max_chars": 30, "max_duration": 4.0, "gap_threshold": 0.2, "min_silence_duration_ms": 400},
            "vad": {"threshold": 0.5, "min_speech_duration_ms": 200, "min_silence_duration_ms": 400},
        }
    },
}


def apply_preset_to_config(config: PipelineConfig, preset_name: str) -> PipelineConfig:
    """应用预设到配置"""
    preset = PRESETS.get(preset_name)
    if not preset:
        return config

    # 创建新配置
    new_config = PipelineConfig(**config.model_dump())

    preset_config = preset.get("config", {})

    # 应用字幕配置
    if "subtitle" in preset_config:
        for key, value in preset_config["subtitle"].items():
            if hasattr(new_config.subtitle, key):
                setattr(new_config.subtitle, key, value)

    # 应用 VAD 配置
    if "vad" in preset_config:
        for key, value in preset_config["vad"].items():
            if hasattr(new_config.vad, key):
                setattr(new_config.vad, key, value)

    return new_config


def get_preset_choices() -> List[Tuple[str, str]]:
    """获取预设选项列表"""
    return [
        (f"{p['icon']} {p['name']}", key)
        for key, p in PRESETS.items()
    ]


def get_preset_description(preset_name: str) -> str:
    """获取预设描述"""
    preset = PRESETS.get(preset_name)
    if preset:
        return f"{preset['icon']} {preset['name']}: {preset['description']}"
    return ""


# 语言选项
LANGUAGE_OPTIONS = [
    ("🌐 自动检测", None),
    ("🇨🇳 中文", "zh"),
    ("🇺🇸 English", "en"),
    ("🇯🇵 日本語", "ja"),
    ("🇰🇷 한국어", "ko"),
    ("🇫🇷 Français", "fr"),
    ("🇩🇪 Deutsch", "de"),
    ("🇪🇸 Español", "es"),
]


def get_language_choices() -> List[Tuple[str, Optional[str]]]:
    """获取语言选项"""
    return LANGUAGE_OPTIONS


# 输出格式选项
FORMAT_OPTIONS = [
    ("SRT 格式", "srt"),
    ("VTT 格式", "vtt"),
    ("JSON 格式", "json"),
]


def get_format_choices() -> List[Tuple[str, str]]:
    """获取格式选项"""
    return FORMAT_OPTIONS


# LLM 模式选项
LLM_MODE_OPTIONS = [
    ("纠错优化", "correct"),
    ("翻译成其他语言", "translate"),
    ("双语字幕", "bilingual"),
]


def get_llm_mode_choices() -> List[Tuple[str, str]]:
    """获取 LLM 模式选项"""
    return LLM_MODE_OPTIONS


# LLM 提供商选项
LLM_PROVIDER_OPTIONS = [
    ("OpenAI 兼容", "openai_compatible"),
    ("Ollama", "ollama"),
]


# 模型选项
MODEL_OPTIONS = [
    "deepseek-chat",
    "deepseek-reasoner",
    "moonshot-v1-8k",
    "moonshot-v1-32k",
    "qwen-turbo",
    "qwen-plus",
    "gpt-3.5-turbo",
    "gpt-4",
    "gpt-4-turbo",
]


def load_config() -> PipelineConfig:
    """加载配置"""
    config_manager = get_config_manager()
    return config_manager.load()


def save_config(config: PipelineConfig, location: str = "user") -> bool:
    """保存配置

    Args:
        config: 配置对象
        location: 保存位置 ("user" 或 "project")
    """
    try:
        config_manager = get_config_manager()
        if location == "user":
            config_manager.save_user_config(config)
        else:
            config_manager.save_project_config(config)
        return True
    except Exception as e:
        print(f"保存配置失败: {e}")
        return False


def scan_videos(paths: List[Path], recursive: bool = True) -> List[Any]:
    """扫描视频文件"""
    scanner = VideoScanner()
    return scanner.scan(paths, recursive=recursive)


def format_duration(seconds: float) -> str:
    """格式化时长"""
    if seconds < 60:
        return f"{seconds:.0f}秒"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}分钟"
    else:
        hours = seconds / 3600
        return f"{hours:.2f}小时"


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_stage_icon(stage_id: str) -> str:
    """获取阶段图标"""
    icons = {
        "01_audio_extract": "🔊",
        "02_vad_split": "✂️",
        "03_asr_transcribe": "📝",
        "04_subtitle_optimize": "🎬",
        "05_llm_postprocess": "🤖",
    }
    return icons.get(stage_id, "📋")


def get_stage_name(stage_id: str) -> str:
    """获取阶段名称"""
    names = {
        "01_audio_extract": "音频提取",
        "02_vad_split": "VAD 分割",
        "03_asr_transcribe": "ASR 转录",
        "04_subtitle_optimize": "字幕优化",
        "05_llm_postprocess": "LLM 后处理",
    }
    return names.get(stage_id, stage_id)


def create_progress_html(progress: float, message: str = "") -> str:
    """创建进度条 HTML"""
    return f"""
    <div style="width: 100%; background-color: #f0f0f0; border-radius: 10px; overflow: hidden; margin: 10px 0;">
        <div style="width: {progress}%; background: linear-gradient(90deg, #4a90d9, #357abd);
                    height: 24px; border-radius: 10px; transition: width 0.3s ease;
                    display: flex; align-items: center; justify-content: center;">
            <span style="color: white; font-weight: bold; font-size: 12px;">{progress:.1f}%</span>
        </div>
    </div>
    <div style="text-align: center; color: #666; font-size: 14px;">{message}</div>
    """


def create_stage_status_html(stages: List[Dict[str, Any]], current_stage: Optional[str] = None) -> str:
    """创建阶段状态 HTML"""
    icons = {
        "pending": "⭕",
        "running": "🔄",
        "completed": "✅",
        "failed": "❌",
    }

    html = '<div style="display: flex; flex-wrap: wrap; gap: 10px; margin: 15px 0;">'

    for stage in stages:
        stage_id = stage.get("stage_id", "")
        status = stage.get("status", "pending")
        name = stage.get("name", stage_id)
        icon = icons.get(status, "⭕")

        is_current = stage_id == current_stage
        border = "2px solid #4a90d9" if is_current else "1px solid #ddd"
        bg_color = "#f0f7ff" if is_current else "#fafafa"

        html += f"""
        <div style="flex: 1; min-width: 120px; padding: 10px; border: {border};
                    border-radius: 8px; background-color: {bg_color}; text-align: center;">
            <div style="font-size: 20px; margin-bottom: 5px;">{icon}</div>
            <div style="font-size: 12px; color: #333;">{name}</div>
            <div style="font-size: 11px; color: #666;">{stage.get('message', '')}</div>
        </div>
        """

    html += '</div>'
    return html


def ensure_output_dir(video_path: Path, output_dir: Optional[str] = None) -> Path:
    """确保输出目录存在"""
    if output_dir:
        out_dir = Path(output_dir)
    else:
        out_dir = video_path.parent

    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def get_output_path(video_path: Path, format: str = "srt", output_dir: Optional[str] = None) -> Path:
    """获取输出文件路径"""
    out_dir = ensure_output_dir(video_path, output_dir)
    return out_dir / f"{video_path.stem}.{format}"


class VideoFileInfo:
    """视频文件信息"""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.name = self.path.name
        self.size = self.path.stat().st_size if self.path.exists() else 0
        self.exists = self.path.exists()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "size": format_file_size(self.size),
            "exists": self.exists,
        }


def check_subtitle_exists(video_path: Path, format: str = "srt") -> bool:
    """检查字幕文件是否已存在"""
    subtitle_path = video_path.with_suffix(f".{format}")
    return subtitle_path.exists()
