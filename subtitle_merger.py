"""
优化字幕拼接模块

提供智能的字幕合并、断句和时间轴优化功能
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple


@dataclass
class WordItem:
    """词级对齐结果"""
    text: str
    start: float
    end: float
    
    def __post_init__(self):
        # 确保时间戳合理
        if self.end < self.start:
            self.end = self.start + 0.1


@dataclass
class SubtitleLine:
    """字幕行"""
    index: int
    start: float
    end: float
    text: str
    words: List[WordItem] = field(default_factory=list)
    
    def to_srt(self) -> str:
        """转换为 SRT 格式"""
        return f"{self.index}\n{self._fmt_time(self.start)} --> {self._fmt_time(self.end)}\n{self.text}\n"
    
    def to_vtt(self) -> str:
        """转换为 WebVTT 格式"""
        return f"{self._fmt_time(self.start, vtt=True)} --> {self._fmt_time(self.end, vtt=True)}\n{self.text}\n"
    
    @staticmethod
    def _fmt_time(seconds: float, vtt: bool = False) -> str:
        """格式化时间"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        if vtt:
            return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace('.', ',')
    
    @property
    def duration(self) -> float:
        return self.end - self.start
    
    @property
    def char_count(self) -> int:
        """字符数（中文算1个，英文算1个）"""
        return len(self.text.replace(' ', ''))
    
    @property
    def reading_speed(self) -> float:
        """阅读速度（字符/秒）"""
        if self.duration <= 0:
            return 0
        return self.char_count / self.duration


class SubtitleMerger:
    """
    字幕合并优化器
    
    核心优化策略：
    1. VAD 片段合并 - 合并间隔小于阈值的相邻片段
    2. 智能断句 - 基于标点符号和字符数
    3. 时间轴优化 - 平滑时间戳、调整显示时长
    """
    
    # 句子结束标点
    SENTENCE_END_PUNCT = '。！？.!?。'
    # 短语结束标点
    PHRASE_END_PUNCT = '，,；;、'
    
    def __init__(
        self,
        max_chars: int = 40,           # 每行最大字符数（中文）
        max_chars_en: int = 80,        # 每行最大字符数（英文）
        min_chars: int = 4,            # 每行最小字符数
        max_duration: float = 6.0,     # 每行最大显示时长（秒）
        min_duration: float = 1.0,     # 每行最小显示时长（秒）
        gap_threshold: float = 0.3,    # 合并 VAD 片段的间隔阈值（秒）
        max_segment_duration: float = 12.0,  # 合并后片段最大时长
        max_gap_within_line: float = 0.5,    # 行内词间最大间隔（秒）
        target_reading_speed: float = 6.0,   # 目标阅读速度（字符/秒）
    ):
        self.max_chars = max_chars
        self.max_chars_en = max_chars_en
        self.min_chars = min_chars
        self.max_duration = max_duration
        self.min_duration = min_duration
        self.gap_threshold = gap_threshold
        self.max_segment_duration = max_segment_duration
        self.max_gap_within_line = max_gap_within_line
        self.target_reading_speed = target_reading_speed
    
    def merge_vad_segments(self, segments: List[Dict]) -> List[Dict]:
        """
        合并相邻的 VAD 片段
        
        合并条件：
        1. 间隔小于 gap_threshold
        2. 合并后总时长不超过 max_segment_duration
        """
        if not segments:
            return []
        
        merged = []
        current = {
            'start': segments[0]['start'],
            'end': segments[0]['end'],
            'index_start': segments[0].get('index', 0),
            'index_end': segments[0].get('index', 0),
        }
        
        for seg in segments[1:]:
            gap = seg['start'] - current['end']
            combined_duration = seg['end'] - current['start']
            
            if gap < self.gap_threshold and combined_duration < self.max_segment_duration:
                # 合并片段
                current['end'] = seg['end']
                current['index_end'] = seg.get('index', current['index_end'])
            else:
                # 保存当前片段，开始新片段
                current['duration'] = current['end'] - current['start']
                merged.append(current)
                current = {
                    'start': seg['start'],
                    'end': seg['end'],
                    'index_start': seg.get('index', 0),
                    'index_end': seg.get('index', 0),
                }
        
        # 添加最后一个片段
        current['duration'] = current['end'] - current['start']
        merged.append(current)
        
        print(f"VAD 片段: {len(segments)} → 合并后: {len(merged)}")
        return merged
    
    def group_by_sentence(self, words: List[WordItem]) -> List[List[WordItem]]:
        """
        按句子/语义分组
        
        分组规则：
        1. 在句子结束标点处断开
        2. 词间间隔过大（>1秒）处断开
        3. 避免过长句子（超过 max_chars * 2）
        """
        if not words:
            return []
        
        groups = []
        current_group = [words[0]]
        current_chars = len(words[0].text)
        
        for i in range(1, len(words)):
            prev_word = words[i - 1]
            word = words[i]
            
            gap = word.start - prev_word.end
            word_len = len(word.text)
            
            # 判断是否需要新分组
            need_new_group = False
            
            # 1. 时间间隔过大
            if gap > 1.0:
                need_new_group = True
            
            # 2. 前一个词是句子结束标点，且当前组已有一定长度
            if prev_word.text and prev_word.text[-1] in self.SENTENCE_END_PUNCT:
                if current_chars >= self.min_chars * 2:
                    need_new_group = True
            
            # 3. 当前组过长（超过两倍最大长度）
            if current_chars + word_len > self.max_chars * 2:
                need_new_group = True
            
            if need_new_group:
                groups.append(current_group)
                current_group = [word]
                current_chars = word_len
            else:
                current_group.append(word)
                current_chars += word_len
        
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _find_break_point(self, words: List[WordItem], max_chars: int) -> int:
        """
        找到最佳断句位置
        
        优先级：
        1. 句子结束标点（且长度 > min_chars）
        2. 短语结束标点（且长度 > min_chars * 2）
        3. 空格位置（英文）
        4. 强制在 max_chars 处断开
        """
        total_chars = 0
        last_sentence_end = -1
        last_phrase_end = -1
        last_space = -1
        
        for i, word in enumerate(words):
            word_len = len(word.text)
            total_chars += word_len
            
            if total_chars > max_chars:
                # 优先在句子结束处断句
                if last_sentence_end > 0:
                    return last_sentence_end + 1
                # 其次在短语结束处
                if last_phrase_end > 0:
                    return last_phrase_end + 1
                # 英文空格位置
                if last_space > 0:
                    return last_space + 1
                # 强制断句
                return max(1, i)
            
            # 记录标点位置
            if word.text and word.text[-1] in self.SENTENCE_END_PUNCT:
                if total_chars >= self.min_chars:
                    last_sentence_end = i
            elif word.text and word.text[-1] in self.PHRASE_END_PUNCT:
                if total_chars >= self.min_chars * 2:
                    last_phrase_end = i
            
            # 记录空格位置（英文）
            if ' ' in word.text:
                last_space = i
        
        return len(words)
    
    def optimize_lines(self, sentence_groups: List[List[WordItem]]) -> List[SubtitleLine]:
        """
        优化每行长度和时长
        
        策略：
        1. 按标点优先断句
        2. 控制每行字符数
        3. 控制每行显示时长
        """
        lines = []
        line_index = 1
        
        for group in sentence_groups:
            # 检测语言类型（简单判断：是否有中文字符）
            has_chinese = any('\u4e00' <= c <= '\u9fff' for word in group for c in word.text)
            max_chars = self.max_chars if has_chinese else self.max_chars_en
            
            # 如果整组较短，作为一行
            total_chars = sum(len(w.text) for w in group)
            if total_chars <= max_chars and len(group) > 0:
                start = group[0].start
                end = group[-1].end
                text = ''.join(w.text for w in group)
                
                lines.append(SubtitleLine(
                    index=line_index,
                    start=start,
                    end=end,
                    text=text,
                    words=group[:]
                ))
                line_index += 1
                continue
            
            # 需要分割成多行
            remaining = group[:]
            while remaining:
                break_point = self._find_break_point(remaining, max_chars)
                
                line_words = remaining[:break_point]
                remaining = remaining[break_point:]
                
                if not line_words:
                    break
                
                start = line_words[0].start
                end = line_words[-1].end
                text = ''.join(w.text for w in line_words)
                
                lines.append(SubtitleLine(
                    index=line_index,
                    start=start,
                    end=end,
                    text=text,
                    words=line_words
                ))
                line_index += 1
        
        return lines
    
    def adjust_timing(self, lines: List[SubtitleLine]) -> List[SubtitleLine]:
        """
        调整时间轴
        
        优化点：
        1. 确保最小显示时长
        2. 消除行间重叠
        3. 调整阅读速度
        4. 添加适当的间隙
        """
        if not lines:
            return []
        
        adjusted = []
        
        for i, line in enumerate(lines):
            # 深拷贝
            new_line = SubtitleLine(
                index=i + 1,  # 重新编号
                start=line.start,
                end=line.end,
                text=line.text,
                words=line.words[:]
            )
            
            # 1. 确保最小显示时长
            if new_line.duration < self.min_duration:
                new_line.end = new_line.start + self.min_duration
            
            # 2. 确保最大显示时长
            if new_line.duration > self.max_duration:
                new_line.end = new_line.start + self.max_duration
            
            # 3. 消除与前一行重叠
            if adjusted:
                prev_end = adjusted[-1].end
                if new_line.start < prev_end + 0.05:
                    new_line.start = prev_end + 0.05
                    # 保持时长，调整结束时间
                    new_line.end = max(new_line.end, new_line.start + self.min_duration)
            
            # 4. 根据阅读速度调整（如果太快）
            speed = new_line.reading_speed
            if speed > self.target_reading_speed * 1.3:  # 超过目标速度的 30%
                target_duration = new_line.char_count / self.target_reading_speed
                target_duration = min(target_duration, self.max_duration)
                target_duration = max(target_duration, self.min_duration)
                new_line.end = new_line.start + target_duration
            
            adjusted.append(new_line)
        
        return adjusted
    
    def merge_short_lines(self, lines: List[SubtitleLine], min_gap: float = 0.3) -> List[SubtitleLine]:
        """
        合并过短的连续行
        
        如果两行都很短（小于 min_chars * 2），且间隔很小，则合并
        """
        if not lines:
            return []
        
        merged = []
        current = lines[0]
        
        for next_line in lines[1:]:
            gap = next_line.start - current.end
            
            # 合并条件
            can_merge = (
                gap < min_gap and
                current.char_count + next_line.char_count <= self.max_chars and
                current.char_count < self.min_chars * 2
            )
            
            if can_merge:
                # 合并两行
                current.text = current.text + ' ' + next_line.text if ' ' in next_line.text else current.text + next_line.text
                current.end = next_line.end
                current.words.extend(next_line.words)
            else:
                merged.append(current)
                current = next_line
        
        merged.append(current)
        
        # 重新编号
        for i, line in enumerate(merged):
            line.index = i + 1
        
        return merged
    
    def process(self, 
                segments: List[Dict], 
                word_alignments: List[WordItem]) -> List[SubtitleLine]:
        """
        完整的处理流程
        
        Args:
            segments: VAD 分割的片段列表
            word_alignments: ForcedAligner 输出的词级时间戳
        
        Returns:
            优化后的字幕行列表
        """
        # 1. 合并 VAD 片段
        merged_segments = self.merge_vad_segments(segments)
        
        # 2. 按句子分组
        sentence_groups = self.group_by_sentence(word_alignments)
        
        # 3. 优化字幕行
        lines = self.optimize_lines(sentence_groups)
        
        # 4. 合并过短的行
        lines = self.merge_short_lines(lines)
        
        # 5. 调整时间轴
        lines = self.adjust_timing(lines)
        
        return lines


def save_subtitles(lines: List[SubtitleLine], output_path: str, fmt: str = 'srt'):
    """保存字幕文件"""
    output_path = Path(output_path)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        if fmt == 'vtt':
            f.write("WEBVTT\n\n")
            for line in lines:
                f.write(line.to_vtt() + "\n")
        else:
            for line in lines:
                f.write(line.to_srt() + "\n")
    
    print(f"字幕已保存: {output_path} ({len(lines)} 行)")


def load_segments_json(json_path: str) -> List[Dict]:
    """从 JSON 文件加载 VAD 片段信息"""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# 使用示例
if __name__ == "__main__":
    # 示例：手动构造一些测试数据
    test_words = [
        WordItem("Hello", 0.0, 0.5),
        WordItem("world", 0.6, 1.0),
        WordItem(".", 1.0, 1.1),
        WordItem("This", 1.5, 1.8),
        WordItem("is", 1.9, 2.0),
        WordItem("a", 2.1, 2.2),
        WordItem("test", 2.3, 2.6),
        WordItem(".", 2.6, 2.7),
    ]
    
    test_segments = [
        {'start': 0.0, 'end': 1.2, 'index': 0},
        {'start': 1.5, 'end': 2.8, 'index': 1},
    ]
    
    merger = SubtitleMerger(max_chars=40)
    lines = merger.process(test_segments, test_words)
    
    for line in lines:
        print(line.to_srt())
