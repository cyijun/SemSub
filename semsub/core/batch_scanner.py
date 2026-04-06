"""
视频目录扫描器
支持递归扫描目录收集视频文件
"""

from pathlib import Path
from typing import List, Optional, Set

from ..core.state_models import VideoTask, StageStatus


class VideoScanner:
    """扫描目录收集视频文件"""

    VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.m4v', '.flv', '.wmv'}
    SUBTITLE_EXTENSIONS = {'.srt', '.vtt', '.ass', '.ssa'}

    def __init__(self, video_extensions: Optional[Set[str]] = None):
        """
        Args:
            video_extensions: 自定义视频扩展名集合，默认使用常见格式
        """
        self.video_extensions = video_extensions or self.VIDEO_EXTENSIONS

    def scan(
        self,
        paths: List[Path],
        recursive: bool = True,
        skip_existing: bool = False,
        output_dir: Optional[Path] = None,
        output_format: str = "srt"
    ) -> List[VideoTask]:
        """
        扫描路径列表，返回视频任务列表

        Args:
            paths: 文件或目录路径列表
            recursive: 是否递归扫描子目录
            skip_existing: 是否跳过已存在字幕的视频
            output_dir: 指定输出目录（None表示与视频同目录）
            output_format: 输出格式后缀

        Returns:
            VideoTask 列表（已去重）
        """
        video_files: Set[Path] = set()

        for path in paths:
            path = Path(path)
            if not path.exists():
                continue

            if path.is_file():
                if self._is_video_file(path):
                    video_files.add(path.resolve())
            elif path.is_dir():
                video_files.update(self._scan_directory(path, recursive))

        # 转换为列表并排序（保持确定性顺序）
        sorted_videos = sorted(video_files, key=lambda p: str(p))

        # 构建 VideoTask 列表
        tasks = []
        for video_path in sorted_videos:
            output_path = self._resolve_output_path(video_path, output_dir, output_format)

            # 检查是否跳过已存在的字幕
            if skip_existing and output_path.exists():
                continue

            tasks.append(VideoTask(
                video_path=str(video_path),
                output_path=str(output_path)
            ))

        return tasks

    def _is_video_file(self, path: Path) -> bool:
        """检查是否是视频文件"""
        return path.suffix.lower() in self.video_extensions

    def _scan_directory(self, directory: Path, recursive: bool) -> Set[Path]:
        """扫描目录收集视频文件"""
        videos = set()

        if recursive:
            for path in directory.rglob("*"):
                if path.is_file() and self._is_video_file(path):
                    videos.add(path.resolve())
        else:
            for path in directory.iterdir():
                if path.is_file() and self._is_video_file(path):
                    videos.add(path.resolve())

        return videos

    def _resolve_output_path(
        self,
        video_path: Path,
        output_dir: Optional[Path],
        output_format: str
    ) -> Path:
        """确定字幕输出路径"""
        if output_dir:
            # 使用指定输出目录，保持相对目录结构
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            return output_dir / f"{video_path.stem}.{output_format}"
        else:
            # 与视频同目录
            return video_path.with_suffix(f".{output_format}")
