"""
音频提取阶段 - 使用 FFmpeg
支持 Workspace
"""

import subprocess
from pathlib import Path
from typing import Optional

from .base import WorkspacePipelineStage
from ..progress import ProgressReporter, PipelineStage, StageProgress
from ..workspace import StageContext
from ..state_models import ArtifactInfo


class AudioExtractStage(WorkspacePipelineStage):
    """音频提取阶段"""

    name = "音频提取"
    stage_id = "01_audio_extract"

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate

    def get_input_spec(self):
        return {
            "dependencies": [],
            "artifacts": {
                "video": {"type": "video"}
            },
            "parameters": {
                "sample_rate": int
            }
        }

    def get_output_spec(self):
        return {
            "artifacts": {
                "audio": {"type": "wav", "description": "提取的音频文件"}
            }
        }

    def execute(
        self,
        ctx: StageContext,
        reporter: Optional[ProgressReporter] = None
    ) -> dict:
        """
        从视频提取音频

        Args:
            ctx: 阶段上下文，ctx.workspace.video_path 包含视频路径
            reporter: 进度报告器

        Returns:
            {"artifacts": {"audio": Path}, "statistics": {...}}
        """
        video_path = ctx.workspace.video_path

        if not video_path.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        ctx.ensure_dir()
        output_wav = ctx.stage_dir / "audio.wav"

        if reporter:
            reporter.check_cancelled()
            reporter.on_stage_start(PipelineStage.AUDIO_EXTRACT, 1)
            reporter.on_log(f"提取音频: {video_path.name}")

        cmd = [
            'ffmpeg', '-y', '-i', str(video_path),
            '-vn',                    # 无视频
            '-acodec', 'pcm_s16le',   # 16位 PCM
            '-ac', '1',               # 单声道
            '-ar', str(self.sample_rate),  # 采样率
            str(output_wav)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, cmd,
                output=result.stdout, stderr=result.stderr
            )

        # 获取输出文件大小
        import os
        file_size = os.path.getsize(output_wav)

        if reporter:
            reporter.on_progress(StageProgress.create(
                PipelineStage.AUDIO_EXTRACT, 1, 1,
                f"音频已提取: {output_wav.name} ({file_size / 1024 / 1024:.1f} MB)"
            ))

        return {
            "artifacts": {
                "audio": ArtifactInfo(
                    path="audio.wav",
                    type="wav",
                    size_bytes=file_size
                )
            },
            "statistics": {
                "sample_rate": self.sample_rate,
                "channels": 1,
                "format": "pcm_s16le"
            }
        }
