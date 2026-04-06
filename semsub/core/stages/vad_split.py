"""
VAD 语音分割阶段 - 使用 Silero VAD
支持 Workspace
"""

from pathlib import Path
from typing import Optional, List, Dict
import json

import torch

from .base import WorkspacePipelineStage
from ..progress import ProgressReporter, PipelineStage, StageProgress
from ..workspace import StageContext
from ..state_models import ArtifactInfo
from ..config import VADConfig


class VADSplitStage(WorkspacePipelineStage):
    """VAD 分割阶段"""

    name = "VAD 分割"
    stage_id = "02_vad_split"

    def __init__(self, config: VADConfig, sample_rate: int = 16000):
        self.config = config
        self.sample_rate = sample_rate
        self.model = None
        self.utils = None

    def get_input_spec(self):
        return {
            "dependencies": ["01_audio_extract"],
            "artifacts": {
                "audio": {"type": "wav", "from_stage": "01_audio_extract"}
            },
            "parameters": {
                "threshold": float,
                "min_speech_duration_ms": int,
                "min_silence_duration_ms": int,
                "sample_rate": int
            }
        }

    def get_output_spec(self):
        return {
            "artifacts": {
                "segments": {"type": "json", "description": "语音片段列表"},
                "audio_tensor": {"type": "pt", "description": "音频张量"}
            }
        }

    def _load_model(self):
        """加载 VAD 模型"""
        if self.model is not None:
            return

        self.model, self.utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
        )
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = self.model.to(device)

    def execute(
        self,
        ctx: StageContext,
        reporter: Optional[ProgressReporter] = None
    ) -> dict:
        """
        VAD 语音分割

        Args:
            ctx: 阶段上下文
            reporter: 进度报告器

        Returns:
            {"artifacts": {"segments": [...], "audio_tensor": Path}, "statistics": {...}}
        """
        # 加载输入 audio artifact
        audio_path = ctx.resolve_input_artifact("audio")
        if audio_path is None:
            raise FileNotFoundError("找不到输入音频文件")

        self._load_model()

        if reporter:
            reporter.check_cancelled()
            reporter.on_stage_start(PipelineStage.VAD_SPLIT, 1)
            reporter.on_log(f"VAD 分割: {audio_path.name}")

        get_speech_timestamps = self.utils[0]
        read_audio = self.utils[2]

        # 读取音频
        wav = read_audio(str(audio_path), sampling_rate=self.sample_rate)
        if isinstance(wav, torch.Tensor):
            device = next(self.model.parameters()).device
            wav = wav.to(device)

        total_duration = len(wav) / self.sample_rate

        # 获取语音时间戳
        speech_timestamps = get_speech_timestamps(
            wav,
            self.model,
            sampling_rate=self.sample_rate,
            threshold=self.config.threshold,
            min_speech_duration_ms=self.config.min_speech_duration_ms,
            min_silence_duration_ms=self.config.min_silence_duration_ms,
        )

        # 转换为秒
        segments = [
            {
                'index': i,
                'start': ts['start'] / self.sample_rate,
                'end': ts['end'] / self.sample_rate,
                'duration': (ts['end'] - ts['start']) / self.sample_rate,
            }
            for i, ts in enumerate(speech_timestamps)
        ]

        # 保存 segments
        ctx.ensure_dir()
        segments_path = ctx.save_artifact("segments", segments, "json")

        # 保存音频张量（用于后续阶段）
        audio_tensor_path = ctx.stage_dir / "audio_tensor.pt"
        torch.save(wav, audio_tensor_path)

        speech_ratio = sum(s['duration'] for s in segments) / total_duration * 100

        if reporter:
            reporter.on_progress(StageProgress.create(
                PipelineStage.VAD_SPLIT, 1, 1,
                f"检测到 {len(segments)} 个语音片段，语音占比: {speech_ratio:.1f}%"
            ))

        return {
            "artifacts": {
                "segments": ArtifactInfo(
                    path="segments.json",
                    type="json"
                ),
                "audio_tensor": ArtifactInfo(
                    path="audio_tensor.pt",
                    type="pt"
                )
            },
            "statistics": {
                "total_segments": len(segments),
                "total_duration_sec": total_duration,
                "speech_duration_sec": sum(s['duration'] for s in segments),
                "speech_ratio_percent": round(speech_ratio, 2)
            }
        }

    def cleanup(self):
        """清理模型"""
        if self.model is not None:
            del self.model
            self.model = None
        if self.utils is not None:
            del self.utils
            self.utils = None
        torch.cuda.empty_cache()
