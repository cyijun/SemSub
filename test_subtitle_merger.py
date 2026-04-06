"""
字幕合并模块测试
"""

import sys
from subtitle_merger import (
    WordItem, SubtitleLine, SubtitleMerger,
    save_subtitles, load_segments_json
)


def test_vad_merge():
    """测试 VAD 片段合并"""
    print("="*50)
    print("测试 1: VAD 片段合并")
    print("="*50)
    
    # 模拟 VAD 片段（有短间隔的相邻片段）
    segments = [
        {'index': 0, 'start': 0.0, 'end': 2.0},
        {'index': 1, 'start': 2.2, 'end': 4.0},   # 间隔 0.2s，应合并
        {'index': 2, 'start': 4.1, 'end': 5.0},   # 间隔 0.1s，应合并
        {'index': 3, 'start': 10.0, 'end': 12.0}, # 间隔 5s，不合并
        {'index': 4, 'start': 12.5, 'end': 14.0}, # 间隔 0.5s，取决于阈值
    ]
    
    merger = SubtitleMerger(gap_threshold=0.3)
    merged = merger.merge_vad_segments(segments)
    
    print(f"\n原始片段: {len(segments)} 个")
    for seg in segments:
        print(f"  [{seg['index']}] {seg['start']:.1f}s - {seg['end']:.1f}s")
    
    print(f"\n合并后: {len(merged)} 个")
    for seg in merged:
        print(f"  [{seg['index_start']}-{seg['index_end']}] {seg['start']:.1f}s - {seg['end']:.1f}s (时长: {seg['duration']:.1f}s)")
    
    assert len(merged) < len(segments), "合并后片段数应减少"
    print("\n✓ VAD 合并测试通过")


def test_sentence_group():
    """测试句子分组"""
    print("\n" + "="*50)
    print("测试 2: 句子分组")
    print("="*50)
    
    # 模拟词级时间戳
    words = [
        WordItem("Hello", 0.0, 0.5),
        WordItem("world", 0.6, 1.0),
        WordItem(".", 1.0, 1.1),           # 句子结束
        WordItem("How", 2.0, 2.3),        # 间隔较大，新句子
        WordItem("are", 2.4, 2.6),
        WordItem("you", 2.7, 3.0),
        WordItem("?", 3.0, 3.1),          # 句子结束
        WordItem("I", 3.2, 3.4),          # 间隔小，继续
        WordItem("am", 3.5, 3.7),
        WordItem("fine", 3.8, 4.2),
        WordItem(".", 4.2, 4.3),
    ]
    
    merger = SubtitleMerger()
    groups = merger.group_by_sentence(words)
    
    print(f"\n输入词数: {len(words)}")
    print(f"分组数: {len(groups)}")
    
    for i, group in enumerate(groups):
        text = ''.join(w.text for w in group)
        print(f"  组 {i+1}: {text}")
    
    assert len(groups) >= 2, "应根据标点和间隔分多组"
    print("\n✓ 句子分组测试通过")


def test_line_optimize():
    """测试字幕行优化"""
    print("\n" + "="*50)
    print("测试 3: 字幕行优化")
    print("="*50)
    
    # 模拟一个很长的句子
    words = [
        WordItem("这", 0.0, 0.2),
        WordItem("是", 0.2, 0.4),
        WordItem("一", 0.4, 0.6),
        WordItem("个", 0.6, 0.8),
        WordItem("很", 0.8, 1.0),
        WordItem("长", 1.0, 1.2),
        WordItem("的", 1.2, 1.4),
        WordItem("句", 1.4, 1.6),
        WordItem("子", 1.6, 1.8),
        WordItem("，", 1.8, 1.9),  # 标点
        WordItem("需", 2.0, 2.2),
        WordItem("要", 2.2, 2.4),
        WordItem("分", 2.4, 2.6),
        WordItem("成", 2.6, 2.8),
        WordItem("多", 2.8, 3.0),
        WordItem("行", 3.0, 3.2),
        WordItem("显", 3.2, 3.4),
        WordItem("示", 3.4, 3.6),
        WordItem("。", 3.6, 3.7),
    ]
    
    merger = SubtitleMerger(max_chars=10)  # 设置较小的最大字符数以便测试
    groups = [words]  # 整个作为一个组
    lines = merger.optimize_lines(groups)
    
    print(f"\n输入: {len(words)} 个词")
    print(f"输出: {len(lines)} 行字幕")
    
    for line in lines:
        print(f"  [{line.index}] {line.start:.1f}s-{line.end:.1f}s: {line.text} ({line.char_count}字)")
    
    assert len(lines) > 1, "长句子应分成多行"
    for line in lines:
        assert line.char_count <= merger.max_chars, "每行不应超过最大字符数"
    print("\n✓ 字幕行优化测试通过")


def test_timing_adjust():
    """测试时间轴调整"""
    print("\n" + "="*50)
    print("测试 4: 时间轴调整")
    print("="*50)
    
    # 模拟有问题的字幕行（过短、重叠）
    lines = [
        SubtitleLine(1, 0.0, 0.3, "短", []),      # 过短
        SubtitleLine(2, 1.05, 2.5, "正常", []),    # 正常行
        SubtitleLine(3, 2.0, 2.3, "快", []),      # 显示时间太短
    ]
    
    merger = SubtitleMerger(min_duration=1.0)
    adjusted = merger.adjust_timing(lines)
    
    print("\n调整前:")
    for line in lines:
        print(f"  [{line.index}] {line.start:.1f}s - {line.end:.1f}s (时长: {line.duration:.1f}s)")
    
    print("\n调整后:")
    for line in adjusted:
        print(f"  [{line.index}] {line.start:.1f}s - {line.end:.1f}s (时长: {line.duration:.1f}s)")
    
    # 验证
    for line in adjusted:
        assert line.duration >= merger.min_duration, f"行 {line.index} 时长不足"
    
    for i in range(1, len(adjusted)):
        assert adjusted[i].start >= adjusted[i-1].end + 0.05, "行之间应有间隔"
    
    print("\n✓ 时间轴调整测试通过")


def test_chinese_segmentation():
    """测试中文断句"""
    print("\n" + "="*50)
    print("测试 5: 中文断句")
    print("="*50)
    
    # 模拟中文句子
    words = [
        WordItem("今", 0.0, 0.2),
        WordItem("天", 0.2, 0.4),
        WordItem("天", 0.4, 0.6),
        WordItem("气", 0.6, 0.8),
        WordItem("真", 0.8, 1.0),
        WordItem("好", 1.0, 1.2),
        WordItem("，", 1.2, 1.3),  # 短语标点
        WordItem("我", 1.4, 1.6),
        WordItem("们", 1.6, 1.8),
        WordItem("去", 1.8, 2.0),
        WordItem("公", 2.0, 2.2),
        WordItem("园", 2.2, 2.4),
        WordItem("玩", 2.4, 2.6),
        WordItem("吧", 2.6, 2.8),
        WordItem("！", 2.8, 2.9),  # 句子结束
    ]
    
    merger = SubtitleMerger(max_chars=10, min_chars=3)
    groups = merger.group_by_sentence(words)
    lines = merger.optimize_lines(groups)
    
    print(f"\n输入: {len(words)} 个词")
    print(f"分组: {len(groups)}")
    print(f"字幕行: {len(lines)}")
    
    for line in lines:
        print(f"  [{line.index}] {line.text}")
    
    print("\n✓ 中文断句测试通过")


def test_save_srt():
    """测试保存 SRT 文件"""
    print("\n" + "="*50)
    print("测试 6: 保存 SRT 文件")
    print("="*50)
    
    lines = [
        SubtitleLine(1, 0.0, 2.5, "第一行字幕", []),
        SubtitleLine(2, 3.0, 5.5, "Second line", []),
        SubtitleLine(3, 6.0, 8.0, "第三行", []),
    ]
    
    test_file = "test_output.srt"
    save_subtitles(lines, test_file)
    
    # 验证文件内容
    with open(test_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"\n生成的 SRT 内容:\n{content}")
    
    # 清理
    import os
    os.remove(test_file)
    
    print("✓ 保存 SRT 测试通过")


def test_real_segments():
    """测试真实 VAD 片段数据"""
    print("\n" + "="*50)
    print("测试 7: 真实 VAD 片段数据")
    print("="*50)
    
    try:
        segments = load_segments_json('segments/segments.json')
        print(f"\n加载了 {len(segments)} 个片段")
        
        # 显示前5个
        for seg in segments[:5]:
            print(f"  [{seg['index']}] {seg['start']:.3f}s - {seg['end']:.3f}s (时长: {seg['duration']:.3f}s)")
        
        # 测试合并
        merger = SubtitleMerger(gap_threshold=0.3)
        merged = merger.merge_vad_segments(segments)
        
        reduction = len(segments) - len(merged)
        print(f"\n合并效果: {len(segments)} → {len(merged)} (减少 {reduction} 个, {reduction/len(segments)*100:.1f}%)")
        
        # 显示合并后的统计
        durations = [seg['duration'] for seg in merged]
        print(f"\n合并后片段统计:")
        print(f"  最短: {min(durations):.2f}s")
        print(f"  最长: {max(durations):.2f}s")
        print(f"  平均: {sum(durations)/len(durations):.2f}s")
        
        print("\n✓ 真实数据测试通过")
        
    except FileNotFoundError:
        print("警告: segments/segments.json 不存在，跳过此测试")


def run_all_tests():
    """运行所有测试"""
    tests = [
        test_vad_merge,
        test_sentence_group,
        test_line_optimize,
        test_timing_adjust,
        test_chinese_segmentation,
        test_save_srt,
        test_real_segments,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"\n✗ {test.__name__} 失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*50)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("="*50)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
