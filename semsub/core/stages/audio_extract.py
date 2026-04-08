"""
音频提取阶段 - 使用 FFmpeg
支持 Workspace
"""

import subprocess
import re
from pathlib import Path
from typing import Optional

from .base import WorkspacePipelineStage
from ..progress import ProgressReporter, PipelineStage, StageProgress
from ..workspace import StageContext
from ..state_models import ArtifactInfo


class FFmpegError(Exception):
    """FFmpeg 错误，包含友好的错误信息"""

    # 常见错误模式到友好提示的映射
    ERROR_PATTERNS = {
        r'No such file or directory': '视频文件不存在或无法访问',
        r'Invalid data found when processing input': '视频文件损坏或格式不支持',
        r'codec not currently supported in container': '容器格式不支持此音频编码',
        r'Unknown encoder': '未知的音频编码器',
        r'Permission denied': '权限不足，无法读取文件或写入输出',
        r'No space left on device': '磁盘空间不足',
        r'Cannot allocate memory': '内存不足',
        r'Conversion failed': '音频转换失败，可能是源文件编码问题',
    }

    def __init__(self, returncode: int, cmd: list, stderr: str, original_error: Optional[Exception] = None):
        self.returncode = returncode
        self.cmd = cmd
        self.stderr = stderr
        self.original_error = original_error
        self.friendly_message = self._parse_error(stderr)
        super().__init__(self.friendly_message)

    def _parse_error(self, stderr: str) -> str:
        """解析 FFmpeg 错误输出，返回友好的错误信息"""
        for pattern, message in self.ERROR_PATTERNS.items():
            if re.search(pattern, stderr, re.IGNORECASE):
                return f"{message}\n\n详细错误: {stderr[:200]}"

        # 默认错误信息
        return f"FFmpeg 音频提取失败 (返回码: {self.returncode})\n\n详细错误: {stderr[:200]}"

    def __str__(self) -> str:
        return self.friendly_message


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
            raise FFmpegError(
                result.returncode, cmd,
                stderr=result.stderr
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

    def cleanup(self):
        """清理资源（此阶段无需 GPU，空实现）"""
        pass
