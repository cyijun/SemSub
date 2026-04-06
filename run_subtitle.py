#!/usr/bin/env python
"""
简化版字幕生成脚本 - 用于处理单个视频
"""
import sys
import torch
import torchaudio
import subprocess
from pathlib import Path

def extract_audio(video_path, output_wav=None):
    """提取音频"""
    video_path = Path(video_path)
    if output_wav is None:
        output_wav = video_path.with_suffix('.wav')
    else:
        output_wav = Path(output_wav)
    
    if output_wav.exists():
        print(f"音频已存在: {output_wav}")
        return output_wav
    
    print(f"提取音频: {video_path} -> {output_wav}")
    cmd = [
        'ffmpeg', '-y', '-i', str(video_path),
        '-vn', '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000',
        str(output_wav)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FFmpeg 错误: {result.stderr}")
        raise RuntimeError("音频提取失败")
    
    print(f"音频提取完成: {output_wav}")
    return output_wav

def vad_split(wav_path):
    """VAD分割"""
    print(f"\n加载 VAD 模型...")
    model, utils = torch.hub.load('snakers4/silero-vad', model='silero_vad', force_reload=False)
    (get_speech_timestamps, _, read_audio, _, _) = utils
    
    print(f"读取音频: {wav_path}")
    wav = read_audio(str(wav_path), sampling_rate=16000)
    
    print("检测语音片段...")
    speech_timestamps = get_speech_timestamps(
        wav, model, sampling_rate=16000,
        threshold=0.5,
        min_speech_duration_ms=250,
        min_silence_duration_ms=500,
    )
    
    segments = [
        {
            'index': i,
            'start': ts['start'] / 16000,
            'end': ts['end'] / 16000,
            'duration': (ts['end'] - ts['start']) / 16000,
        }
        for i, ts in enumerate(speech_timestamps)
    ]
    
    print(f"检测到 {len(segments)} 个语音片段")
    return segments, wav

def transcribe_segments(segments, wav, video_path):
    """转录音频片段"""
    from qwen_asr import Qwen3ASRModel
    
    print(f"\n加载 ASR 模型...")
    model = Qwen3ASRModel.from_pretrained(
        '/mnt/g/models/Qwen3-ASR-1.7B',
        dtype=torch.bfloat16,
        device_map="cuda:0",
        forced_aligner='/mnt/g/models/Qwen3-ForcedAligner-0.6B',
        forced_aligner_kwargs=dict(dtype=torch.bfloat16, device_map="cuda:0"),
    )
    
    results = []
    batch_size = 8
    total = len(segments)
    
    import tempfile
    import json
    
    # 创建临时目录保存片段
    temp_dir = Path(tempfile.mkdtemp(prefix="segments_"))
    print(f"临时目录: {temp_dir}")
    
    # 保存片段信息
    segments_json = video_path.with_suffix('.segments.json')
    with open(segments_json, 'w', encoding='utf-8') as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)
    print(f"片段信息: {segments_json}")
    
    print(f"\n开始转录 {total} 个片段...")
    
    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch_segments = segments[batch_start:batch_end]
        
        print(f"\n处理批次 {batch_start//batch_size + 1}/{(total-1)//batch_size + 1} ({batch_start}-{batch_end-1})")
        
        # 保存音频片段
        batch_files = []
        for seg in batch_segments:
            start_sample = int(seg['start'] * 16000)
            end_sample = int(seg['end'] * 16000)
            seg_wav = wav[start_sample:end_sample]
            
            seg_file = temp_dir / f"seg_{seg['index']:04d}.wav"
            torchaudio.save(str(seg_file), seg_wav.unsqueeze(0), 16000)
            batch_files.append(seg_file)
        
        # 批量转录
        batch_results = model.transcribe(
            audio=[str(f) for f in batch_files],
            language=[None] * len(batch_files),  # 自动检测
            return_time_stamps=True,
        )
        
        # 保存结果
        for seg, result in zip(batch_segments, batch_results):
            words = []
            if result.time_stamps and result.time_stamps.items:
                for item in result.time_stamps.items:
                    words.append({
                        'text': item.text,
                        'start': item.start_time + seg['start'],
                        'end': item.end_time + seg['start'],
                    })
            
            results.append({
                'index': seg['index'],
                'start': seg['start'],
                'end': seg['end'],
                'text': result.text,
                'language': result.language if hasattr(result, 'language') else 'unknown',
                'words': words,
            })
            
            progress = len(results) / total * 100
            print(f"  [{seg['index']:04d}] [{progress:5.1f}%] {result.text[:60]}{'...' if len(result.text) > 60 else ''}")
    
    # 清理临时目录
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)
    
    return results

def save_subtitles(results, output_srt):
    """保存字幕"""
    from subtitle_merger import SubtitleMerger, save_subtitles
    
    # 创建字幕行
    lines = []
    for i, r in enumerate(results):
        words = [type('W', (), {'text': w['text'], 'start': w['start'], 'end': w['end']})() 
                 for w in r.get('words', [])]
        
        lines.append(type('L', (), {
            'index': i + 1,
            'start': r['start'],
            'end': r['end'],
            'text': r['text'],
            'words': words,
            'char_count': len(r['text']),
            'duration': r['end'] - r['start'],
            'reading_speed': len(r['text']) / max(r['end'] - r['start'], 0.1),
            'to_srt': lambda self: f"{self.index}\n{self._fmt(self.start)} --> {self._fmt(self.end)}\n{self.text}\n",
            '_fmt': lambda self, s: f"{int(s//3600):02d}:{int((s%3600)//60):02d}:{s%60:06.3f}".replace('.', ','),
        })())
    
    # 保存
    with open(output_srt, 'w', encoding='utf-8') as f:
        for line in lines:
            f.write(line.to_srt())
            f.write('\n')
    
    print(f"\n字幕已保存: {output_srt}")
    return lines

def main(video_path):
    """主流程"""
    video_path = Path(video_path)
    print("="*60)
    print(f"处理视频: {video_path}")
    print("="*60)
    
    # 1. 提取音频
    print("\n步骤 1/4: 提取音频")
    wav_path = extract_audio(video_path)
    
    # 2. VAD分割
    print("\n步骤 2/4: VAD 语音分割")
    segments, wav = vad_split(wav_path)
    
    # 3. 转录
    print("\n步骤 3/4: ASR 转录")
    results = transcribe_segments(segments, wav, video_path)
    
    # 4. 保存字幕
    print("\n步骤 4/4: 保存字幕")
    output_srt = video_path.with_suffix('.srt')
    lines = save_subtitles(results, output_srt)
    
    # 统计
    print("\n" + "="*60)
    print("处理完成")
    print("="*60)
    print(f"视频: {video_path}")
    print(f"片段数: {len(segments)}")
    print(f"字幕行: {len(lines)}")
    print(f"输出: {output_srt}")
    
    # 保存 JSON
    output_json = video_path.with_suffix('.transcription.json')
    import json
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"JSON: {output_json}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python run_subtitle.py <视频文件>")
        sys.exit(1)
    
    main(sys.argv[1])
