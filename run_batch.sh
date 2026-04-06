#!/bin/bash
# 视频字幕生成批处理脚本
# 用法: ./run_batch.sh

cd /mnt/d/temp/SemSub
source ~/miniconda3/etc/profile.d/conda.sh
conda activate qwen3-asr

echo "=========================================="
echo "视频字幕生成"
echo "=========================================="

# 视频文件
VIDEO="./第8课_丹青全才_秀出丛林.mp4"

echo "步骤 1/3: 提取音频"
if [ ! -f "${VIDEO%.mp4}.wav" ]; then
    ffmpeg -y -i "$VIDEO" -vn -acodec pcm_s16le -ac 1 -ar 16000 "${VIDEO%.mp4}.wav"
else
    echo "  [SKIP] 音频已存在"
fi

echo ""
echo "步骤 2/3: VAD 分割"
if [ ! -f "${VIDEO%.mp4}.segments.json" ]; then
    python -c "
import torch
import torchaudio
import json
from pathlib import Path

video_path = Path('$VIDEO')
wav_path = video_path.with_suffix('.wav')
segments_json = video_path.with_suffix('.segments.json')

model, utils = torch.hub.load('snakers4/silero-vad', model='silero_vad', force_reload=False, verbose=False)
(get_speech_timestamps, _, read_audio, _, _) = utils

wav = read_audio(str(wav_path), sampling_rate=16000)
speech_timestamps = get_speech_timestamps(wav, model, sampling_rate=16000, threshold=0.5, min_speech_duration_ms=250, min_silence_duration_ms=500)

segments = [{'index': i, 'start': ts['start']/16000, 'end': ts['end']/16000, 'duration': (ts['end']-ts['start'])/16000} for i, ts in enumerate(speech_timestamps)]

with open(segments_json, 'w') as f:
    json.dump(segments, f, ensure_ascii=False, indent=2)

print(f'片段数: {len(segments)}')
"
else
    echo "  [SKIP] 片段信息已存在"
fi

echo ""
echo "步骤 3/3: ASR 转录"
echo "  这是一个长时间任务，进度会自动保存..."
echo ""

# 切分片段
python -c "
import torch
import torchaudio
import json
from pathlib import Path

video_path = Path('$VIDEO')
wav_path = video_path.with_suffix('.wav')
segments = json.load(open(video_path.with_suffix('.segments.json')))

seg_dir = Path('video_segments')
seg_dir.mkdir(exist_ok=True)

wav, sr = torchaudio.load(wav_path)
wav = wav.squeeze()

for seg in segments:
    seg_file = seg_dir / f\"segment_{seg['index']:04d}_{seg['start']:.3f}_{seg['end']:.3f}.wav\"
    if seg_file.exists():
        continue
    start_sample = int(seg['start'] * 16000)
    end_sample = int(seg['end'] * 16000)
    seg_wav = wav[start_sample:end_sample]
    torchaudio.save(str(seg_file), seg_wav.unsqueeze(0), 16000)

seg_info = [{**s, 'file': f\"segment_{s['index']:04d}_{s['start']:.3f}_{s['end']:.3f}.wav\"} for s in segments]
with open(seg_dir / 'segments.json', 'w') as f:
    json.dump(seg_info, f, ensure_ascii=False, indent=2)

print(f'片段准备完成: {len(segments)} 个')
"

# 转录
python transcribe_segments.py -i video_segments -o "${VIDEO%.mp4}.txt" -b 16

echo ""
echo "=========================================="
echo "完成!"
echo "字幕文件: ${VIDEO%.mp4}.txt"
echo "=========================================="
