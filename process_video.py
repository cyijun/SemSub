#!/usr/bin/env python
"""
视频字幕处理 - 分步执行
"""
import sys
import torch
import torchaudio
import subprocess
import json
from pathlib import Path

def step1_extract_audio(video_path):
    """步骤1: 提取音频"""
    video_path = Path(video_path)
    wav_path = video_path.with_suffix('.wav')
    
    if wav_path.exists():
        print(f"[SKIP] 音频已存在: {wav_path}")
        return wav_path
    
    print(f"[STEP 1/3] 提取音频: {video_path.name}")
    cmd = ['ffmpeg', '-y', '-i', str(video_path), '-vn', '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000', str(wav_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg 失败: {result.stderr[:200]}")
    
    size_mb = wav_path.stat().st_size / (1024*1024)
    print(f"[DONE] 音频: {wav_path} ({size_mb:.1f} MB)")
    return wav_path

def step2_vad_split(wav_path, segments_json):
    """步骤2: VAD分割"""
    wav_path = Path(wav_path)
    segments_json = Path(segments_json)
    
    if segments_json.exists():
        print(f"[SKIP] 片段信息已存在: {segments_json}")
        segments = json.load(open(segments_json))
        return segments
    
    print(f"[STEP 2/3] VAD 语音分割: {wav_path.name}")
    
    model, utils = torch.hub.load('snakers4/silero-vad', model='silero_vad', force_reload=False, verbose=False)
    (get_speech_timestamps, _, read_audio, _, _) = utils
    
    wav = read_audio(str(wav_path), sampling_rate=16000)
    duration = len(wav) / 16000
    
    print(f"  音频时长: {duration/60:.1f} 分钟")
    print(f"  检测语音片段...")
    
    speech_timestamps = get_speech_timestamps(
        wav, model, sampling_rate=16000,
        threshold=0.5, min_speech_duration_ms=250, min_silence_duration_ms=500,
    )
    
    segments = [{'index': i, 'start': ts['start']/16000, 'end': ts['end']/16000, 
                 'duration': (ts['end']-ts['start'])/16000} 
                for i, ts in enumerate(speech_timestamps)]
    
    # 保存
    with open(segments_json, 'w', encoding='utf-8') as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)
    
    total_speech = sum(s['duration'] for s in segments)
    print(f"[DONE] 片段数: {len(segments)}, 语音占比: {total_speech/duration*100:.1f}%")
    return segments

def step3_transcribe(segments_json, wav_path, output_srt):
    """步骤3: 转录 (使用现有脚本)"""
    from transcribe_segments import SegmentTranscriber
    
    segments = json.load(open(segments_json))
    wav_path = Path(wav_path)
    output_srt = Path(output_srt)
    
    # 创建临时片段目录
    temp_dir = wav_path.parent / 'temp_segments'
    temp_dir.mkdir(exist_ok=True)
    
    # 加载音频
    import torchaudio
    wav, sr = torchaudio.load(wav_path)
    wav = wav.squeeze()
    
    # 保存片段
    print(f"[STEP 3/3] 准备 {len(segments)} 个音频片段...")
    for seg in segments:
        seg_file = temp_dir / f"segment_{seg['index']:04d}_{seg['start']:.3f}_{seg['end']:.3f}.wav"
        if seg_file.exists():
            continue
        start_sample = int(seg['start'] * 16000)
        end_sample = int(seg['end'] * 16000)
        seg_wav = wav[start_sample:end_sample]
        torchaudio.save(str(seg_file), seg_wav.unsqueeze(0), 16000)
    
    # 保存片段信息
    seg_info = []
    for seg in segments:
        seg_file = temp_dir / f"segment_{seg['index']:04d}_{seg['start']:.3f}_{seg['end']:.3f}.wav"
        seg_info.append({**seg, 'file': seg_file.name})
    
    with open(temp_dir / 'segments.json', 'w', encoding='utf-8') as f:
        json.dump(seg_info, f, ensure_ascii=False, indent=2)
    
    print(f"  片段目录: {temp_dir}")
    print(f"  开始转录 (使用 transcribe_segments.py)...")
    
    # 使用现有转录器
    transcriber = SegmentTranscriber(batch_size=8, language=None)
    results = transcriber.transcribe_all(
        segments_dir=str(temp_dir),
        output_txt=str(output_srt.with_suffix('.txt')),
        output_json=str(output_srt.with_suffix('.json')),
    )
    
    return results

def main():
    if len(sys.argv) < 2:
        print("用法: python process_video.py <视频文件>")
        sys.exit(1)
    
    video_path = Path(sys.argv[1])
    wav_path = video_path.with_suffix('.wav')
    segments_json = video_path.with_suffix('.segments.json')
    output_srt = video_path.with_suffix('.srt')
    
    print("="*60)
    print(f"视频字幕生成: {video_path.name}")
    print("="*60)
    
    # 步骤1: 提取音频
    wav_path = step1_extract_audio(video_path)
    
    # 步骤2: VAD分割
    segments = step2_vad_split(wav_path, segments_json)
    
    # 步骤3: 转录
    print(f"\n准备转录 {len(segments)} 个片段...")
    print("这是一个长时间任务，将在后台继续执行。")
    
    results = step3_transcribe(segments_json, wav_path, output_srt)
    
    print("\n" + "="*60)
    print("完成!")
    print(f"字幕: {output_srt}")

if __name__ == "__main__":
    main()
