"""
SRT 解析工具
"""

from typing import List
from ..models import SubtitleLine


def parse_srt(content: str) -> List[SubtitleLine]:
    """
    解析 SRT 格式文本

    Args:
        content: SRT 格式字符串

    Returns:
        List[SubtitleLine]: 字幕行列表
    """
    lines = []
    blocks = content.strip().split('\n\n')

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        lines_in_block = block.split('\n')
        if len(lines_in_block) < 2:
            continue

        # 第一行是序号
        try:
            index = int(lines_in_block[0].strip())
        except ValueError:
            continue

        # 第二行是时间戳
        timestamp_line = lines_in_block[1].strip()
        if '-->' not in timestamp_line:
            continue

        # 解析时间戳
        try:
            start_str, end_str = timestamp_line.split('-->')
            start = _parse_time(start_str.strip())
            end = _parse_time(end_str.strip())
        except (ValueError, IndexError):
            continue

        # 剩余行是文本
        text_lines = lines_in_block[2:]
        text = '\n'.join(text_lines).strip()

        if not text:
            continue

        subtitle_line = SubtitleLine(
            index=index,
            start=start,
            end=end,
            text=text,
            words=[],  # SRT 导入时没有词级时间戳
            original_text=text,
            is_translated=False
        )
        lines.append(subtitle_line)

    return lines


def write_srt(lines: List[SubtitleLine]) -> str:
    """
    生成 SRT 格式文本

    Args:
        lines: 字幕行列表

    Returns:
        str: SRT 格式字符串
    """
    if not lines:
        return ""

    srt_blocks = []
    for line in lines:
        # 确保索引是正整数
        index = max(1, line.index)

        # 格式化时间戳
        start_time = _format_time(line.start)
        end_time = _format_time(line.end)

        # 构建块
        block = f"{index}\n{start_time} --> {end_time}\n{line.text}\n"
        srt_blocks.append(block)

    return '\n'.join(srt_blocks)


def _parse_time(time_str: str) -> float:
    """
    解析 SRT 时间戳为秒数

    格式: HH:MM:SS,mmm 或 HH:MM:SS.mmm
    """
    # 统一使用点号
    time_str = time_str.replace(',', '.')

    parts = time_str.split(':')
    if len(parts) != 3:
        raise ValueError(f"Invalid time format: {time_str}")

    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])

    return hours * 3600 + minutes * 60 + seconds


def _format_time(seconds: float) -> str:
    """
    将秒数格式化为 SRT 时间戳

    格式: HH:MM:SS,mmm
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace(".", ",")