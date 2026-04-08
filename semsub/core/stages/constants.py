"""
阶段常量定义
所有与阶段相关的常量集中在此定义，避免多处重复
"""
from typing import Dict, List

# 阶段执行顺序
STAGE_ORDER: List[str] = [
    "01_audio_extract",
    "02_vad_split",
    "03_asr_transcribe",
    "04_subtitle_optimize",
    "05_llm_postprocess",
]

# 阶段依赖关系
STAGE_DEPENDENCIES: Dict[str, List[str]] = {
    "01_audio_extract": [],
    "02_vad_split": ["01_audio_extract"],
    "03_asr_transcribe": ["02_vad_split"],
    "04_subtitle_optimize": ["02_vad_split", "03_asr_transcribe"],
    "05_llm_postprocess": ["04_subtitle_optimize"],
}

# 阶段显示名称
STAGE_NAMES: Dict[str, str] = {
    "01_audio_extract": "音频提取",
    "02_vad_split": "VAD 分割",
    "03_asr_transcribe": "ASR 转录",
    "04_subtitle_optimize": "字幕优化",
    "05_llm_postprocess": "LLM 后处理",
}

# PipelineStage 枚举映射（用于 ProgressReporter）
STAGE_TO_ENUM_MAP: Dict[str, str] = {
    "01_audio_extract": "AUDIO_EXTRACT",
    "02_vad_split": "VAD_SPLIT",
    "03_asr_transcribe": "ASR_TRANSCRIBE",
    "04_subtitle_optimize": "SUBTITLE_OPTIMIZE",
    "05_llm_postprocess": "LLM_POSTPROCESS",
}
