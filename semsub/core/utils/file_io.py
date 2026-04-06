"""
文件 I/O 工具函数
"""

import json
import hashlib
import shutil
from pathlib import Path
from typing import Any, Union, Optional
import os
import tempfile


class AtomicFileWriter:
    """原子文件写入器 - 确保文件写入是原子的"""

    def __init__(self, target_path: Union[str, Path], mode: str = "w"):
        self.target_path = Path(target_path)
        self.mode = mode
        self.temp_file = None
        self._closed = False

    def __enter__(self):
        # 在同一目录创建临时文件，确保原子重命名
        self.temp_file = tempfile.NamedTemporaryFile(
            mode=self.mode,
            suffix=".tmp",
            prefix=f".tmp_{self.target_path.name}_",
            dir=str(self.target_path.parent),
            delete=False,
        )
        return self.temp_file

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._closed:
            return

        self._closed = True
        if self.temp_file:
            self.temp_file.close()
            if exc_type is None:
                # 成功：原子重命名
                os.rename(self.temp_file.name, self.target_path)
            else:
                # 失败：删除临时文件
                os.unlink(self.temp_file.name)


def safe_write_json(path: Union[str, Path], data: Any, indent: int = 2):
    """安全地写入 JSON 文件（原子写入）"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with AtomicFileWriter(path, mode="w") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False, default=str)
        f.write("\n")


def safe_read_json(path: Union[str, Path], default: Any = None) -> Any:
    """安全地读取 JSON 文件"""
    path = Path(path)
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_file_hash(
    path: Union[str, Path],
    algorithm: str = "sha256",
    chunk_size: int = 8192
) -> str:
    """计算文件哈希"""
    hasher = hashlib.new(algorithm)
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return f"{algorithm}:{hasher.hexdigest()}"


def compute_file_hash_fast(
    path: Union[str, Path],
    sample_size: int = 1024 * 1024  # 1MB
) -> str:
    """
    快速计算文件哈希（仅采样前 N 字节 + 文件大小 + 修改时间）

    适用于大文件，速度更快但碰撞概率略高
    """
    path = Path(path)
    stat = path.stat()
    size = stat.st_size
    mtime = stat.st_mtime

    hasher = hashlib.sha256()
    hasher.update(f"{size}:{mtime}:".encode())

    with open(path, "rb") as f:
        chunk = f.read(sample_size)
        hasher.update(chunk)

    return f"sha256:{hasher.hexdigest()}"


def copy_with_hardlink(
    src: Union[str, Path],
    dst: Union[str, Path],
    use_hardlink: bool = True
) -> Path:
    """
    复制文件，优先使用硬链接

    硬链接的优点：
    - 不占用额外磁盘空间
    - 速度快（只是创建目录项）

    缺点：
    - 只能同一文件系统
    - 编辑一个文件会影响另一个
    """
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    if use_hardlink:
        try:
            # 尝试硬链接
            if not dst.exists():
                os.link(src, dst)
                return dst
        except (OSError, FileExistsError):
            pass

    # 回退到复制
    shutil.copy2(src, dst)
    return dst


def ensure_dir(path: Union[str, Path]) -> Path:
    """确保目录存在，返回 Path 对象"""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_file_size(path: Union[str, Path]) -> int:
    """获取文件大小（字节）"""
    return Path(path).stat().st_size


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小为人类可读形式"""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def read_text_lines(path: Union[str, Path], encoding: str = "utf-8") -> list[str]:
    """读取文本文件为行列表"""
    path = Path(path)
    if not path.exists():
        return []
    return path.read_text(encoding=encoding).splitlines()


def write_text_lines(
    path: Union[str, Path],
    lines: list[str],
    encoding: str = "utf-8",
    newline: str = "\n"
):
    """写入行列表到文本文件"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(newline.join(lines) + newline, encoding=encoding)
