# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a speech recognition and subtitle generation project (SemSub) that generates optimized movie subtitles using:
- **Qwen3-ASR-1.7B** for speech-to-text transcription
- **Qwen3-ForcedAligner-0.6B** for word-level timestamp alignment
- **Silero VAD** for voice activity detection and audio segmentation
- **FFmpeg** for audio extraction from video files

## Common Commands

### Run Tests
```bash
python test_subtitle_merger.py
```

### Generate Subtitles for a Video

**Complete pipeline (recommended):**
```bash
python generate_subtitles.py /path/to/video.mp4 -o output.srt -l Chinese
```

**Simplified version:**
```bash
python run_subtitle.py /path/to/video.mp4
```

**Step-by-step processing:**
```bash
python process_video.py /path/to/video.mp4
```

**Batch processing with shell script:**
```bash
./run_batch.sh
```

### Transcribe Existing Segments Only
```bash
python transcribe_segments.py -i video_segments -o output.txt -b 16
```

### Quick Python API Usage
```python
from generate_subtitles import quick_generate
srt_path = quick_generate(video_path='/path/to/video.mp4', language='Chinese')
```

## High-Level Architecture

### Data Flow Pipeline

```
Video File (.mp4)
    ↓
[Audio Extraction] ── FFmpeg ──→ WAV (16kHz, mono, 16-bit PCM)
    ↓
[VAD Splitting] ── Silero VAD ──→ Speech Segments (JSON)
    ↓
[Segment Merging] ── gap_threshold (0.3s) ──→ Merged Segments
    ↓
[ASR + Forced Align] ── Qwen3-ASR + ForcedAligner ──→ Word-level timestamps
    ↓
[Subtitle Optimization] ── SubtitleMerger ──→ Optimized subtitle lines
    ↓
[Output] ── SRT/VTT/TXT/JSON
```

### Core Modules

| File | Purpose |
|------|---------|
| `subtitle_merger.py` | Core optimization engine. Handles VAD segment merging, intelligent sentence breaking, timing adjustment, and reading speed optimization. |
| `generate_subtitles.py` | Complete subtitle generation pipeline with `MovieSubtitleGenerator` class and `SubtitleConfig` dataclass. |
| `transcribe_segments.py` | Batch transcription of pre-segmented audio files with checkpoint/resume support. |
| `run_subtitle.py` | Simplified end-to-end script for single video processing. |
| `process_video.py` | Step-by-step processing with skip logic for existing files. |

### Key Optimization Strategies (in SubtitleMerger)

1. **VAD Segment Merging**: Merges adjacent segments with gaps < 0.3s (configurable via `gap_threshold`)
2. **Intelligent Sentence Breaking**: Prioritizes breaking at sentence-ending punctuation (。！？.!?), then phrase punctuation (，,；;、)
3. **Timing Adjustment**: Ensures minimum 1.0s and maximum 6.0s display duration per line
4. **Reading Speed Control**: Targets 6.0 chars/second (Chinese) with adaptive adjustment

### Configuration Parameters

Key defaults in `SubtitleConfig`:
```python
max_chars = 40              # Chinese chars per line
max_chars_en = 80           # English chars per line
max_duration = 6.0          # Max display seconds per line
min_duration = 1.0          # Min display seconds per line
gap_threshold = 0.3         # VAD segment merge threshold (seconds)
batch_size = 8              # ASR batch processing size
vad_threshold = 0.5
vad_min_speech_duration_ms = 250
vad_min_silence_duration_ms = 500
```

### Model Paths

Default model locations (configured in `SubtitleConfig`):
- ASR Model: `/mnt/g/models/Qwen3-ASR-1.7B`
- Aligner Model: `/mnt/g/models/Qwen3-ForcedAligner-0.6B`

### Language Handling

- Set `language=None` for automatic language detection
- Supported: "Chinese", "English", "Japanese", etc.
- Language affects character limits and reading speed calculations

### Intermediate File Formats

During processing, these files are generated:
- `{video}.wav` - Extracted audio (16kHz mono)
- `{video}.segments.json` - VAD speech segments with start/end timestamps
- `{video}.transcription.json` - ASR results with word-level timestamps
- `{video}.srt` - Final subtitle output
- `{video}.checkpoint.json` - Resume progress for interrupted transcriptions

### Scene-Based Configuration Tuning

**Movies (dense dialogue):**
```python
max_chars=40, max_duration=6.0, gap_threshold=0.3, vad_min_silence_duration_ms=300
```

**Documentaries (narration):**
```python
max_chars=35, max_duration=7.0, gap_threshold=0.5, vad_min_silence_duration_ms=800
```

**Animation (fast speech):**
```python
max_chars=30, max_duration=4.0, gap_threshold=0.2, target_reading_speed=8.0
```

## Dependencies

Core packages (Python 3.12):
```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install qwen_asr silero-vad torchcodec
```

System requirement: FFmpeg installed and available in PATH.

## Development Notes

- Comments and documentation are primarily in Chinese
- Variable names use English
- GPU (CUDA) is strongly recommended for ASR model inference
- The codebase uses `torch.bfloat16` for memory efficiency
