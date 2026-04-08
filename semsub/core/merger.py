"""
字幕合并优化模块

从 subtitle_merger.py 迁移优化
提供智能的字幕合并、断句和时间轴优化功能
"""

import re
from typing import List, Dict, Optional
from .models import WordItem, SubtitleLine
from .config import SubtitleConfig


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

    def __init__(self, config: SubtitleConfig):
        self.config = config

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

            if gap < self.config.gap_threshold and combined_duration < self.config.max_segment_duration:
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

        return merged

    def group_by_sentence(self, words: List[WordItem]) -> List[List[WordItem]]:
        """
        按句子/语义分组

        分组规则：
        1. 在句子结束标点处断开
        2. 词间间隔过大（>1.5秒）处断开
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

            # 1. 时间间隔过大（只有间隔很大才断开，避免把连续说话分成多组）
            if gap > 1.5:  # 从1.0增加到1.5秒
                need_new_group = True

            # 2. 前一个词是句子结束标点
            # 如果当前组已经有一定长度，且与当前词间隔较大，才开启新分组
            if prev_word.text and prev_word.text[-1] in self.SENTENCE_END_PUNCT:
                # 只有在达到一定长度且与下一个词间隔较大时才断开
                # 避免把标点后的第一个字分到下一组
                if current_chars >= self.config.min_chars * 2 and gap > 0.3:
                    need_new_group = True

            # 3. 当前组过长（超过两倍最大长度）
            if current_chars + word_len > self.config.max_chars * 2:
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

    def _has_punctuation(self, words: List[WordItem]) -> bool:
        """检查词列表中是否包含标点符号"""
        for word in words:
            if word.text and word.text[-1] in self.SENTENCE_END_PUNCT + self.PHRASE_END_PUNCT:
                return True
        return False

    def _find_break_point(self, words: List[WordItem], max_chars: int, max_duration: Optional[float] = None) -> int:
        """
        找到最佳断句位置 - 严格标点优先策略

        核心原则：
        1. 优先在句子结束标点处断开
        2. 其次在短语标点处断开
        3. 如果没有标点，尽量保持整组（返回全部长度）
        4. 只有极端超长且超时才强制断句
        """
        if not words:
            return 0

        # 第一遍遍历：找句子结束标点
        last_sentence_end = -1
        for i, word in enumerate(words):
            if word.text and word.text[-1] in self.SENTENCE_END_PUNCT:
                last_sentence_end = i
                # 如果在合理范围内，直接返回
                char_count = sum(len(words[k].text) for k in range(i + 1))
                if char_count <= max_chars + 15:  # 允许15字溢出
                    return i + 1

        # 找到了句子结束标点（即使超出限制），使用它
        if last_sentence_end > 0:
            return last_sentence_end + 1

        # 第二遍：找短语标点
        last_phrase_end = -1
        for i, word in enumerate(words):
            if word.text and word.text[-1] in self.PHRASE_END_PUNCT:
                last_phrase_end = i
                char_count = sum(len(words[k].text) for k in range(i + 1))
                if char_count <= max_chars + 10:  # 允许10字溢出
                    return i + 1

        if last_phrase_end > 0:
            return last_phrase_end + 1

        # 第三遍：检查时间限制（只有给定了max_duration才检查）
        if max_duration:
            for i, word in enumerate(words):
                current_duration = word.end - words[0].start
                if current_duration > max_duration:
                    # 回退找标点
                    for j in range(min(i, len(words) - 1), -1, -1):
                        if words[j].text and words[j].text[-1] in self.SENTENCE_END_PUNCT + self.PHRASE_END_PUNCT:
                            return j + 1
                    # 强制断句
                    return max(1, i)

        # 没有标点或未达到强制条件，返回全部（保持语义完整）
        return len(words)

    def optimize_lines(self, sentence_groups: List[List[WordItem]]) -> List[SubtitleLine]:
        """
        优化每行长度和时长

        策略：
        1. 按标点优先断句
        2. 控制每行字符数
        3. 控制每行显示时长（超过 max_duration 强制分割）
        """
        lines = []
        line_index = 1

        for group in sentence_groups:
            # 检测语言类型（简单判断：是否有中文字符）
            has_chinese = any('\u4e00' <= c <= '\u9fff' for word in group for c in word.text)
            max_chars = self.config.max_chars if has_chinese else self.config.max_chars_en

            # 计算整组时长
            group_duration = group[-1].end - group[0].start if group else 0

            # 如果整组较短且时长合适，作为一行
            total_chars = sum(len(w.text) for w in group)
            if total_chars <= max_chars and group_duration <= self.config.max_duration and len(group) > 0:
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
            group_lines = []  # 临时存储这个句子组的行
            while remaining:
                # 计算当前剩余的时长
                remaining_duration = remaining[-1].end - remaining[0].start if remaining else 0

                # 标点优先断句，不强制按时间分割
                # 只有极端超长（>10秒）才考虑时间限制
                max_duration_for_break = None
                if remaining_duration > self.config.max_duration + 4.0:  # 只有超过max_duration+4秒才强制
                    max_duration_for_break = self.config.max_duration + 2.0  # 给2秒余量

                break_point = self._find_break_point(remaining, max_chars, max_duration_for_break)

                line_words = remaining[:break_point]
                remaining = remaining[break_point:]

                if not line_words:
                    break

                start = line_words[0].start
                end = line_words[-1].end
                text = ''.join(w.text for w in line_words)

                group_lines.append(SubtitleLine(
                    index=0,  # 稍后重新编号
                    start=start,
                    end=end,
                    text=text,
                    words=line_words
                ))

            # 检查最后一行是否太短，如果是则尝试与前一行合并
            if len(group_lines) >= 2:
                last_line = group_lines[-1]
                if last_line.char_count < self.config.min_chars:
                    # 最后一行太短，尝试合并到前一行
                    prev_line = group_lines[-2]
                    combined_chars = prev_line.char_count + last_line.char_count
                    combined_duration = last_line.end - prev_line.start
                    # 合并后不能超过字符数限制
                    if combined_chars <= max_chars + 5:
                        # 合并两行
                        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in prev_line.text + last_line.text)
                        if has_chinese:
                            prev_line.text = prev_line.text + last_line.text
                        else:
                            prev_line.text = prev_line.text + ' ' + last_line.text
                        prev_line.end = last_line.end
                        prev_line.words.extend(last_line.words)
                        group_lines.pop()  # 移除最后一行

            # 添加到总列表
            for line in group_lines:
                line.index = line_index
                lines.append(line)
                line_index += 1

        return lines

    def adjust_timing(self, lines: List[SubtitleLine]) -> List[SubtitleLine]:
        """
        调整时间轴

        优化点：
        1. 确保最小显示时长
        2. 消除行间重叠
        3. 保持原始结束时间（只在必要时调整）
        4. 根据阅读速度调整（如果太快）
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

            # 1. 确保最小显示时长（如果太短则延长）
            if new_line.duration < self.config.min_duration:
                new_line.end = new_line.start + self.config.min_duration

            # 2. 确保最少显示 min_line_duration（防止切换太快看花眼）
            if new_line.duration < self.config.min_line_duration:
                new_line.end = new_line.start + self.config.min_line_duration

            # 3. 消除与前一行重叠
            if adjusted:
                prev_end = adjusted[-1].end
                if new_line.start < prev_end + 0.05:
                    new_line.start = prev_end + 0.05
                    # 确保开始不晚于结束
                    if new_line.start >= new_line.end:
                        new_line.end = new_line.start + self.config.min_duration

            # 3. 检查阅读速度，如果太快则适当延长（但不超过max_duration）
            speed = new_line.reading_speed
            if speed > self.config.target_reading_speed * 1.5:  # 超过目标速度的50%
                # 计算理想的显示时长
                target_duration = new_line.char_count / self.config.target_reading_speed
                target_duration = min(target_duration, self.config.max_duration)
                target_duration = max(target_duration, new_line.duration)  # 不缩短原时长
                new_line.end = new_line.start + target_duration

            adjusted.append(new_line)

        return adjusted

    def merge_short_lines(self, lines: List[SubtitleLine], min_gap: float = 0.5) -> List[SubtitleLine]:
        """
        合并过短的连续行 - 更积极的合并策略

        合并条件（满足任一即可）：
        1. 当前行太短（小于 min_chars），且与下一行间隔小
        2. 两行总长度不超过 max_chars，且间隔很小
        3. 当前行 duration 太短（小于 min_line_duration），且可以合并
        """
        if not lines:
            return []

        merged = []
        current = lines[0]

        for next_line in lines[1:]:
            gap = next_line.start - current.end
            combined_chars = current.char_count + next_line.char_count

            # 判断是否应该合并
            should_merge = False

            # 条件1：当前行太短（字符数少于 min_chars）
            if current.char_count < self.config.min_chars and gap < min_gap:
                should_merge = True

            # 条件2：两行都很短，且合并后不超过限制
            if (current.char_count < self.config.min_chars * 1.5 and
                next_line.char_count < self.config.min_chars * 1.5 and
                combined_chars <= self.config.max_chars and
                gap < min_gap):
                should_merge = True

            # 条件3：当前行显示时间太短（容易看花眼）
            if current.duration < self.config.min_line_duration and gap < min_gap * 0.5:
                if combined_chars <= self.config.max_chars:
                    should_merge = True

            # 条件4：优先合并短行（配置开启时）
            if (self.config.prefer_longer_lines and
                combined_chars <= self.config.max_chars and
                gap < 0.3):  # 间隔很小
                should_merge = True

            # 条件5：当前行结尾没有标点，且下一行间隔小，尝试合并
            # （优先保证语义完整，即使可能稍微超过字符限制）
            current_ends_with_punct = current.text and current.text[-1] in self.SENTENCE_END_PUNCT + self.PHRASE_END_PUNCT
            next_ends_with_punct = next_line.text and next_line.text[-1] in self.SENTENCE_END_PUNCT + self.PHRASE_END_PUNCT
            if (not current_ends_with_punct and
                current.char_count < 20 and  # 放宽到20字符
                gap < 0.3 and  # 间隔很小
                combined_chars <= self.config.max_chars + 10):  # 允许稍微超限
                should_merge = True

            # 条件6：当前行不以标点结尾，下一行以标点结尾，且间隔很小，优先合并
            if (not current_ends_with_punct and
                next_ends_with_punct and
                gap < 0.3 and
                combined_chars <= self.config.max_chars + 5):
                should_merge = True

            if should_merge:
                # 合并两行，智能处理中英文空格
                has_chinese = any('\u4e00' <= c <= '\u9fff' for c in current.text + next_line.text)
                if has_chinese:
                    current.text = current.text + next_line.text  # 中文直接拼接
                else:
                    current.text = current.text + ' ' + next_line.text  # 英文加空格
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

    def process(self, segments: List[Dict], word_alignments: List[WordItem]) -> List[SubtitleLine]:
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

        # 修复断裂的常用词
        lines = self._fix_broken_words(lines)

        return lines

    def _fix_broken_words(self, lines: List[SubtitleLine]) -> List[SubtitleLine]:
        """
        修复在行边界断裂的常用词和孤立标点
        例如："你可" + "以自己" -> "你可以" + "自己"
              "老师，" + "\"" -> "老师，\""
        """
        if len(lines) < 2:
            return lines

        # 常见双字词，避免在中间断开
        common_words = {'可以', '自己', '一个', '没有', '怎么', '什么', '这样', '那种'}
        # 孤立的标点符号，应该合并到相邻行
        isolated_punct = {'"', '"', '\u201c', '\u201d', '\u2018', '\u2019', '（', '）', '(', ')', '【', '】', '[', ']'}

        i = 0
        while i < len(lines) - 1:
            current = lines[i]
            next_line = lines[i + 1]

            # 情况1：下一行以孤立标点开头，把标点合并到当前行
            if next_line.text and next_line.text[0] in isolated_punct:
                # 提取开头的标点
                punct_end = 0
                while punct_end < len(next_line.text) and next_line.text[punct_end] in isolated_punct:
                    punct_end += 1
                punct_part = next_line.text[:punct_end]
                rest_part = next_line.text[punct_end:]

                current.text += punct_part
                # 安全地获取时间戳
                if punct_end > 0 and next_line.words and punct_end <= len(next_line.words):
                    current.end = next_line.words[punct_end - 1].end
                    current.words.extend(next_line.words[:punct_end])

                if rest_part:
                    next_line.text = rest_part
                    if next_line.words and punct_end < len(next_line.words):
                        next_line.start = next_line.words[punct_end].start
                    next_line.words = next_line.words[punct_end:] if punct_end < len(next_line.words) else []
                else:
                    lines.pop(i + 1)
                    continue

            # 情况2：当前行以孤立标点结尾，合并到下一行（如果下一行很短）
            if current.text and current.text[-1] in isolated_punct:
                if i > 0 and len(current.text) <= 2:
                    prev = lines[i - 1]
                    prev.text += current.text
                    prev.end = current.end
                    prev.words.extend(current.words)
                    lines.pop(i)
                    continue

            # 检查当前行结尾和下一行开头是否组成常见词
            if len(current.text) >= 1 and len(next_line.text) >= 1:
                # 检查各种组合
                for word in common_words:
                    if len(word) == 2:
                        # 检查当前行以第一个字结尾，下一行以第二个字开头
                        if current.text.endswith(word[0]) and next_line.text.startswith(word[1]):
                            # 需要调整：把下一行的第一个字移到当前行
                            if len(next_line.text) > 1 and next_line.char_count > self.config.min_chars:
                                char_to_move = next_line.text[0]
                                current.text += char_to_move
                                current.end = next_line.words[0].end
                                current.words.append(next_line.words[0])
                                next_line.text = next_line.text[1:]
                                next_line.start = next_line.words[1].start if len(next_line.words) > 1 else next_line.start
                                next_line.words = next_line.words[1:]
                                break

            i += 1

        # 重新编号
        for i, line in enumerate(lines):
            line.index = i + 1

        return lines


def save_subtitles(lines: List[SubtitleLine], output_path: str, fmt: str = 'srt'):
    """保存字幕文件"""
    from pathlib import Path
    output_path = Path(output_path)

    with open(output_path, 'w', encoding='utf-8') as f:
        if fmt == 'vtt':
            f.write("WEBVTT\n\n")
            for line in lines:
                f.write(line.to_vtt() + "\n")
        else:
            for line in lines:
                f.write(line.to_srt() + "\n")

    return output_path
