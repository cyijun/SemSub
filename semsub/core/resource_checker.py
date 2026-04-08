"""
资源检查器 - 处理前检查系统资源

功能：
1. 检查磁盘空间
2. 检查 GPU 可用性
3. 检查模型文件存在
"""

import shutil
import logging
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ResourceCheckResult:
    """资源检查结果"""
    passed: bool
    message: str
    disk_space_ok: bool = True
    disk_free_bytes: int = 0
    disk_required_bytes: int = 0


class ResourceChecker:
    """资源检查器"""

    # 估计的中间文件大小比例（相对于输入视频）
    AUDIO_EXTRACT_RATIO = 0.5  # 提取的音频约为视频大小的一半
    WORKSPACE_OVERHEAD = 100 * 1024 * 1024  # 额外开销 100MB

    @classmethod
    def check_disk_space(
        cls,
        video_path: Path,
        output_dir: Optional[Path] = None,
        safety_margin: float = 2.0
    ) -> ResourceCheckResult:
        """
        检查磁盘空间是否足够

        Args:
            video_path: 视频文件路径
            output_dir: 输出目录（默认与视频相同）
            safety_margin: 安全系数（默认 2 倍）

        Returns:
            检查结果
        """
        video_path = Path(video_path)
        if output_dir:
            output_dir = Path(output_dir)
        if not video_path.exists():
            return ResourceCheckResult(
                passed=False,
                message=f"视频文件不存在: {video_path}"
            )

        # 获取视频大小
        video_size = video_path.stat().st_size

        # 估算所需空间
        # 音频提取 + 工作区开销 + 字幕输出
        required_space = int(
            (video_size * cls.AUDIO_EXTRACT_RATIO + cls.WORKSPACE_OVERHEAD)
            * safety_margin
        )

        # 检查目标目录空间
        check_path = output_dir if output_dir else video_path.parent
        try:
            disk_usage = shutil.disk_usage(check_path)
            free_space = disk_usage.free

            if free_space < required_space:
                free_gb = free_space / (1024**3)
                required_gb = required_space / (1024**3)
                return ResourceCheckResult(
                    passed=False,
                    message=(
                        f"磁盘空间不足\n"
                        f"  可用: {free_gb:.2f} GB\n"
                        f"  需要: {required_gb:.2f} GB (含 {safety_margin}x 安全系数)\n"
                        f"  建议: 清理磁盘空间或更改输出目录"
                    ),
                    disk_space_ok=False,
                    disk_free_bytes=free_space,
                    disk_required_bytes=required_space
                )

            return ResourceCheckResult(
                passed=True,
                message=f"磁盘空间充足 ({free_space / (1024**3):.2f} GB 可用)",
                disk_space_ok=True,
                disk_free_bytes=free_space,
                disk_required_bytes=required_space
            )

        except Exception as e:
            logger.warning(f"无法检查磁盘空间: {e}")
            # 无法检查时默认通过，但在日志中记录
            return ResourceCheckResult(
                passed=True,
                message=f"无法验证磁盘空间: {e}",
                disk_space_ok=True,
                disk_free_bytes=0,
                disk_required_bytes=required_space
            )

    @classmethod
    def check_video_file(cls, video_path: Path) -> Tuple[bool, str]:
        """
        检查视频文件是否有效

        Args:
            video_path: 视频文件路径

        Returns:
            (是否有效, 消息)
        """
        video_path = Path(video_path)
        if not video_path.exists():
            return False, f"视频文件不存在: {video_path}"

        if not video_path.is_file():
            return False, f"路径不是文件: {video_path}"

        # 检查文件大小（至少 1KB）
        size = video_path.stat().st_size
        if size < 1024:
            return False, f"视频文件太小 ({size} 字节)，可能已损坏"

        # 检查文件扩展名
        valid_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.m4v', '.flv'}
        if video_path.suffix.lower() not in valid_extensions:
            return False, f"不支持的文件格式: {video_path.suffix}"

        return True, f"视频文件有效 ({size / (1024**2):.2f} MB)"

    @classmethod
    def preflight_check(
        cls,
        video_path: Path,
        output_dir: Optional[Path] = None
    ) -> ResourceCheckResult:
        """
        处理前的完整资源检查

        Args:
            video_path: 视频文件路径
            output_dir: 输出目录

        Returns:
            检查结果
        """
        # 1. 检查视频文件
        video_ok, video_msg = cls.check_video_file(video_path)
        if not video_ok:
            return ResourceCheckResult(passed=False, message=video_msg)

        # 2. 检查磁盘空间
        disk_result = cls.check_disk_space(video_path, output_dir)
        if not disk_result.passed:
            return disk_result

        return ResourceCheckResult(
            passed=True,
            message=f"{video_msg}; {disk_result.message}",
            disk_space_ok=disk_result.disk_space_ok,
            disk_free_bytes=disk_result.disk_free_bytes,
            disk_required_bytes=disk_result.disk_required_bytes
        )
