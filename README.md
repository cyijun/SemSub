# SemSub - Intelligent Subtitle Generator

[中文](README.zh.md) | **English**

Generate high-quality subtitles from videos using Qwen3-ASR and Silero VAD.

```bash
# Quick start - single video
python -m semsub.cli generate video.mp4

# With GUI (recommended)
python -m semsub gui
```

## Features

- **Accurate Transcription**: Qwen3-ASR-1.7B + Forced Aligner for precise word-level timestamps
- **Smart Optimization**: Intelligent line breaking, merging, and duration control
- **LLM Enhancement**: Error correction, translation, and bilingual subtitles
- **Batch Processing**: Process entire directories with one command
- **Resume Support**: Interrupted processing can resume from checkpoints
- **SRT Processing**: Browser upload/download for standalone SRT correction and translation
- **Dual-Layer Config**: VSCode-style project and user configuration management

## Installation

```bash
# 1. Clone and setup
python -m venv venv && source venv/bin/activate
pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt

# 2. Download models to local path
# - https://huggingface.co/Qwen/Qwen3-ASR-1.7B
# - https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B

# 3. Configure model paths
mkdir -p ~/.config/semsub
cat > ~/.config/semsub/config.yaml << 'EOF'
asr:
  model_path: "/path/to/Qwen3-ASR-1.7B"
  aligner_path: "/path/to/Qwen3-ForcedAligner-0.6B"
  device: "cuda:0"
EOF
```

## Usage Guide

### Gradio Web GUI (Recommended)

The easiest way to use SemSub:

```bash
python -m semsub gui
# Open http://localhost:7860 in your browser
```

**Features:**
- Enter video file paths directly (no upload, supports large files)
- 5 pages: Quick Start, Batch Processing, SRT Processing, Workspaces, Settings
- Real-time progress with stage-by-stage status
- Full ASR/VAD/Subtitle/LLM configuration
- **SRT Processing**: Drag-and-drop or click to upload SRT files, download processed output, view history with delete support
- **Dual-Layer Config**: Switch between Project Config (`./semsub.yaml`) and User Config (`~/.config/semsub/config.yaml`) with source badges per section

**Quick Start Flow:**
1. Go to "Quick Start" page
2. Enter video path(s): `/path/to/movie.mp4`
3. Select preset (optional): `movie`, `documentary`, or `animation`
4. Click "Generate Subtitles"

### CLI Commands

#### Generate Subtitles

**Single video:**
```bash
# Basic usage
python -m semsub.cli generate video.mp4

# Specify output file
python -m semsub.cli generate video.mp4 -o output.srt

# Use movie preset with LLM correction
python -m semsub.cli generate video.mp4 --preset movie --llm --llm-mode correct

# Translate to English
python -m semsub.cli generate video.mp4 --llm --llm-mode translate -l Chinese
```

**Batch processing:**
```bash
# Process entire directory
python -m semsub.cli generate ./movies/ --output-dir ./subtitles/

# Skip videos that already have subtitles
python -m semsub.cli generate ./season1/ --output-dir ./subs/ --skip-existing

# Continue on error (don't stop on failed videos)
python -m semsub.cli generate ./videos/ --continue-on-error

# Mixed input (files + directories)
python -m semsub.cli generate video1.mp4 ./episodes/ video2.mkv --output-dir ./output/
```

**Process specific stage range:**
```bash
# Only run ASR and subtitle optimization (skip audio extract/VAD if done)
python -m semsub.cli generate video.mp4 --from 03_asr_transcribe --to 04_subtitle_optimize
```

#### Check Status

```bash
# View processing status
python -m semsub.cli status video.mp4

# Example output:
# Workspace: /path/to/.semsub
# Video: video.mp4
# Status: Running (ASR Transcription 15/42)
#
# Stage Status:
#   ✓ Audio Extract     completed    00:05
#   ✓ VAD Split         completed    00:03
#   ▶ ASR Transcribe    running      02:05  35%
#   ⏸ Subtitle Optimize pending
#   ⏸ LLM Postprocess   pending (disabled)
```

#### Retry Failed Stage

```bash
# Force re-run from a specific stage
python -m semsub.cli run-stage video.mp4 03_asr_transcribe --force

# Resume from checkpoint (ASR stage only)
python -m semsub.cli run-stage video.mp4 03_asr_transcribe --resume
```

**Stage IDs:** `01_audio_extract`, `02_vad_split`, `03_asr_transcribe`, `04_subtitle_optimize`, `05_llm_postprocess`

#### Workspace Management

```bash
# Initialize workspace (without processing)
python -m semsub.cli init video.mp4

# Clean workspace to free disk space
python -m semsub.cli clean video.mp4

# Clean all workspaces in a directory
for d in ./*/.semsub; do python -m semsub.cli clean "${d%/.semsub}"; done
```

#### Process Existing SRT

**CLI:**
```bash
# Correct ASR errors using LLM
python -m semsub.cli process-srt input.srt -o output.srt --llm-mode correct

# Translate subtitles
python -m semsub.cli process-srt input.srt -o output.srt --llm-mode translate
```

**Web GUI:**
1. Go to "SRT Processing" page
2. Upload SRT file via drag-and-drop or click to select
3. Choose LLM mode (correct / translate / bilingual)
4. Click "Process" and download the output when complete
5. View and manage past tasks in the history list

Default output directory: `temp/semsub_outputs/` (with automatic deduplication: `file.processed.srt`, `file.processed(1).srt`, etc.)

## Scene Presets

| Preset | Use Case | Key Settings |
|--------|----------|--------------|
| `movie` | Dialogue-dense films | max_chars=40, gap_threshold=0.3s |
| `documentary` | Narration content | max_chars=35, gap_threshold=0.5s, min_silence=800ms |
| `animation` | Fast-paced content | max_chars=30, max_duration=4.0s, gap_threshold=0.2s |

```bash
python -m semsub.cli generate video.mp4 --preset documentary
```

## Configuration

Configuration hierarchy (highest to lowest priority):
1. CLI arguments
2. Project config (`./semsub.yaml`)
3. User config (`~/.config/semsub/config.yaml`)
4. Built-in presets

In the Web GUI Settings page, you can switch between **Project Config** and **User Config** (VSCode-style). It defaults to project config if it exists, since it has the highest priority. Each config section (ASR/VAD/Subtitle/LLM/Output) shows a **source badge** indicating whether the value comes from the project config, user config, or built-in default. When editing the user config, a warning is shown if a project config exists, because project config values will override user config values at runtime.

### Essential Settings

```yaml
# ~/.config/semsub/config.yaml
asr:
  model_path: "/mnt/g/models/Qwen3-ASR-1.7B"
  aligner_path: "/mnt/g/models/Qwen3-ForcedAligner-0.6B"
  device: "cuda:0"
  batch_size: 8

# LLM configuration (optional)
llm:
  enabled: true
  api_key: "your-api-key"
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"
```

### Common Options

| Option | Description | Example |
|--------|-------------|---------|
| `-o, --output` | Output file path | `-o output.srt` |
| `--output-dir` | Output directory for batch | `--output-dir ./subs/` |
| `--preset` | Scene preset | `--preset movie` |
| `-l, --language` | Audio language | `-l Chinese` |
| `--llm` | Enable LLM post-processing | `--llm` |
| `--llm-mode` | LLM mode: correct/translate/bilingual | `--llm-mode translate` |
| `--skip-existing` | Skip if output exists | `--skip-existing` |
| `--continue-on-error` | Continue on failure | `--continue-on-error` |

## Python API

```python
from pathlib import Path
from semsub import PipelineConfig, SubtitlePipeline

# Basic usage
config = PipelineConfig()
pipeline = SubtitlePipeline(config)
output = pipeline.generate(Path("video.mp4"))

# Custom configuration
config = PipelineConfig()
config.asr.batch_size = 16
config.subtitle.max_chars = 35
config.llm.enabled = True
config.llm.api_key = "your-api-key"

# Batch processing
from semsub.core.batch_scanner import VideoScanner
from semsub.core.batch_pipeline import BatchPipeline

tasks = VideoScanner().scan([Path("./movies/")], recursive=True)
result = BatchPipeline(config).process(tasks)
```

## FAQ

**Q: How do I change model paths?**
```bash
python -m semsub.cli config edit
# Add: asr: { model_path: "/your/path" }
```

**Q: Can I resume interrupted processing?**
Yes, run the same command again. ASR stage automatically resumes from checkpoint.

**Q: How much disk space is needed?**
Workspace uses ~30% of video size for extracted audio. Clean with `python -m semsub.cli clean video.mp4`.

**Q: Supported LLM providers?**
Any OpenAI-compatible API: DeepSeek, Kimi, Qwen, OpenAI, etc.

**Q: CPU-only mode?**
Set `asr.device: "cpu"` in config. Note: Very slow, not recommended.

**Q: Why does my config change revert after saving?**
Check if a project config (`./semsub.yaml`) exists. Project config has higher priority than user config (`~/.config/semsub/config.yaml`). If you edit the user config but a project config exists with the same key, the project config value will take effect. Edit the project config directly, or delete it if you want user config to apply.

## License

MIT License
