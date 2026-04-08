# SemSub - Intelligent Subtitle Generator

[中文](README.zh.md) | **English**

A powerful subtitle generation tool with both CLI and GUI interfaces, powered by Qwen3-ASR and Silero VAD. Supports batch processing, workspace management, and LLM post-processing.

## Features

- **Voice Activity Detection**: Silero VAD for detecting speech segments
- **Speech Recognition**: Qwen3-ASR-1.7B + Forced Aligner for precise word-level timestamps
- **Subtitle Optimization**: Intelligent merging, sentence breaking, and duration control
- **LLM Post-processing**: Error correction, translation, and bilingual subtitle support
- **Batch Processing**: Recursive directory scanning with parallel video processing
- **Workspace Management**: Stage-based execution with resume capability
- **Scene Presets**: Optimized configurations for movies, documentaries, and animation

## Installation

### System Requirements

- Python 3.10+
- CUDA 12.8 (recommended for GPU acceleration)
- FFmpeg (must be available in system PATH)

### Installation Steps

```bash
# Clone the repository
git clone https://github.com/cyijun/SemSub.git
cd SemSub

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install PyTorch (CUDA 12.8)
pip install torch==2.7.1 torchvision==0.22.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu128

# Install project dependencies
pip install -r requirements.txt
```

### Model Download

Download the following models to your local machine:

- **ASR Model**: [Qwen3-ASR-1.7B](https://huggingface.co/Qwen/Qwen3-ASR-1.7B)
- **Aligner Model**: [Qwen3-ForcedAligner-0.6B](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B)

Specify model paths in the configuration file (see Configuration section).

## Quick Start

### 1. Generate Subtitles for a Single Video

```bash
python -m semsub.cli generate video.mp4
```

### 2. Launch GUI

**Gradio Web GUI (Recommended):**
```bash
python -m semsub gui
```

Then open http://localhost:7860 in your browser.

**Features:**
- File path input (no upload required, supports large files)
- 5 pages: Quick Start, Batch Processing, SRT Processing, Workspaces, Settings
- Real-time progress display and log output
- Complete ASR/VAD/Subtitle/LLM configuration

**Legacy PyQt6 GUI:**
```bash
python -m semsub.gui.app
```

**GUI Usage Flow:**
1. Enter video file path in the text box (e.g., `/path/to/movie.mp4`)
2. Click "Refresh List" to load file information
3. Select scene preset and configure options (optional)
4. Click "Generate Subtitles" to start processing

### 3. Batch Process a Directory

```bash
python -m semsub.cli generate ./movies/ --output-dir ./subtitles/
```

## CLI Commands

### `generate` - Generate Subtitles

Basic usage:
```bash
python -m semsub.cli generate <input> [options]
```

**Input** can be:
- Single video file: `video.mp4`
- Multiple files: `video1.mp4 video2.mp4`
- Directory: `./movies/` (auto-recursive scanning)

**Common Options**:

| Option | Description | Example |
|--------|-------------|---------|
| `-o, --output` | Single file output path | `-o output.srt` |
| `--output-dir` | Batch output directory | `--output-dir ./subs/` |
| `--preset` | Use preset configuration | `--preset movie` |
| `-l, --language` | Specify language | `-l Chinese` |
| `-f, --format` | Output format (srt/vtt/json) | `-f srt` |
| `--llm` | Enable LLM post-processing | `--llm` |
| `--llm-mode` | LLM mode (correct/translate/bilingual) | `--llm-mode translate` |
| `--skip-existing` | Skip videos with existing subtitles | `--skip-existing` |
| `--continue-on-error` | Continue processing on error | `--continue-on-error` |

**Examples**:

```bash
# Basic usage
python -m semsub.cli generate video.mp4

# Use movie preset with LLM correction
python -m semsub.cli generate video.mp4 --preset movie --llm --llm-mode correct

# Batch process directory, skip existing
python -m semsub.cli generate ./season1/ --output-dir ./subs/ --skip-existing

# Mixed input (files + directories)
python -m semsub.cli generate video1.mp4 ./episodes/ video2.mkv --output-dir ./output/
```

### `status` - Check Workspace Status

```bash
# View video processing status
python -m semsub.cli status video.mp4

# Verbose output (includes file paths)
python -m semsub.cli status video.mp4 --verbose
```

Example output:
```
Workspace: /path/to/.semsub
Video: video.mp4
Status: Running (ASR Transcription 15/42)

Stage Status:
  ✓ Audio Extract     completed    00:05
  ✓ VAD Split         completed    00:03
  ▶ ASR Transcribe    running      02:05  35%
  ⏸ Subtitle Optimize pending
  ⏸ LLM Postprocess   pending (disabled)
```

### `run-stage` - Execute Single Stage

For debugging or restarting from a specific stage:

```bash
# Run specific stage
python -m semsub.cli run-stage video.mp4 03_asr_transcribe

# Force re-execution (cascades to dependent stages)
python -m semsub.cli run-stage video.mp4 04_subtitle_optimize --force

# Resume from checkpoint (ASR stage only)
python -m semsub.cli run-stage video.mp4 03_asr_transcribe --resume
```

**Stage IDs**:
- `01_audio_extract` - Audio extraction
- `02_vad_split` - VAD segmentation
- `03_asr_transcribe` - ASR transcription
- `04_subtitle_optimize` - Subtitle optimization
- `05_llm_postprocess` - LLM post-processing

### `init` / `clean` - Workspace Management

```bash
# Initialize workspace (without execution)
python -m semsub.cli init video.mp4

# Clean workspace
python -m semsub.cli clean video.mp4

# Clean but keep output subtitles
python -m semsub.cli clean video.mp4 --keep-output
```

### `config` - Configuration Management

```bash
# Show current configuration
python -m semsub.cli config show

# Show configuration (including defaults)
python -m semsub.cli config show --all

# Edit user configuration
python -m semsub.cli config edit
```

## Scene Presets

SemSub provides three presets optimized for specific scenarios:

### `movie` - Movie (Default)

Optimized for dialogue-dense movie scenes.

```yaml
subtitle:
  max_chars: 40              # Max 40 characters per line
  max_duration: 6.0          # Max 6 seconds display
  gap_threshold: 0.3         # Merge segments closer than 0.3s
vad:
  min_silence_duration_ms: 300
```

### `documentary` - Documentary

Optimized for narration-heavy content.

```yaml
subtitle:
  max_chars: 35
  max_duration: 7.0          # Longer display time
  gap_threshold: 0.5         # Larger merge threshold
vad:
  min_silence_duration_ms: 800
```

### `animation` - Animation

Optimized for fast-paced animated content.

```yaml
subtitle:
  max_chars: 30
  max_duration: 4.0          # Faster switching
  gap_threshold: 0.2
  target_reading_speed: 8.0  # Target reading speed 8 chars/sec
vad:
  min_silence_duration_ms: 200
```

**Using Presets**:
```bash
python -m semsub.cli generate video.mp4 --preset documentary
```

## Configuration

Configuration uses YAML format with four-level override hierarchy:

1. **CLI Arguments** (highest priority)
2. **Project Config** (`./semsub.yaml`)
3. **User Config** (`~/.config/semsub/config.yaml`)
4. **Built-in Presets** (lowest priority)

### Full Configuration Example

```yaml
# ASR Configuration
asr:
  model_path: "/mnt/g/models/Qwen3-ASR-1.7B"
  aligner_path: "/mnt/g/models/Qwen3-ForcedAligner-0.6B"
  device: "cuda:0"
  batch_size: 8
  language: null              # null = auto-detect

# VAD Configuration
vad:
  threshold: 0.5
  min_speech_duration_ms: 250
  min_silence_duration_ms: 500

# Subtitle Optimization
subtitle:
  max_chars: 40               # Max Chinese characters per line
  max_chars_en: 80            # Max English characters per line
  min_chars: 10               # Min characters per line
  max_duration: 6.0           # Max display duration (seconds)
  min_duration: 1.0           # Min display duration (seconds)
  gap_threshold: 0.3          # VAD segment merge threshold (seconds)
  target_reading_speed: 6.0   # Target reading speed (chars/sec)

# LLM Post-processing
llm:
  enabled: false
  provider: "openai_compatible"
  api_key: ""                 # Your API key
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"
  prompt_template: "correct.zh"
  output_mode: "correct"      # correct/translate/bilingual
  batch_size: 10
  max_tokens: 4096
  temperature: 0.3
  timeout: 60

# Output Configuration
output:
  format: "srt"               # srt/vtt/json
  save_intermediate: false    # Save intermediate files
```

### Creating User Configuration

Recommended to create user config before first run:

```bash
mkdir -p ~/.config/semsub
cat > ~/.config/semsub/config.yaml << 'EOF'
asr:
  model_path: "/path/to/Qwen3-ASR-1.7B"
  aligner_path: "/path/to/Qwen3-ForcedAligner-0.6B"
  device: "cuda:0"

llm:
  api_key: "your-api-key-here"
  base_url: "https://api.deepseek.com/v1"
EOF
```

## Workspace

SemSub uses a workspace mechanism to manage the processing pipeline. A `.semsub/` hidden directory is created in the video's directory by default.

### Workspace Structure

```
video.mp4
.semsub/
├── state.json               # Global state
├── config.yaml              # Config snapshot
├── 01_audio_extract/
│   ├── state.json           # Stage state
│   ├── input.json           # Input dependencies
│   ├── output.json          # Output descriptors
│   └── audio.wav            # Actual audio file
├── 02_vad_split/
│   └── segments.json        # Speech segments
├── 03_asr_transcribe/
│   ├── transcripts.json     # Transcription results
│   └── checkpoint.json      # Resume checkpoint
└── ...
```

### Workspace Benefits

1. **Resume Capability**: ASR transcription can resume from interruption
2. **Stage Debugging**: Individual stage execution and retry
3. **Config Snapshot**: Saves processing config for traceability
4. **Intermediate Results**: View/export outputs from each stage

### Cleaning Workspace

Clean up after processing to save disk space:

```bash
# Delete workspace only, keep subtitles
python -m semsub.cli clean video.mp4

# Check workspace size
du -sh video.mp4/.semsub
```

**Note**: After deleting the workspace, resume is not possible and full reprocessing is required.

## LLM Post-processing

Supports OpenAI-compatible APIs for:

### Correction Mode (`correct`)

Fix ASR errors like homophones and punctuation.

```bash
python -m semsub.cli generate video.mp4 --llm --llm-mode correct
```

### Translation Mode (`translate`)

Translate subtitles to target language.

```bash
python -m semsub.cli generate video.mp4 --llm --llm-mode translate
```

Set `target_language` in config:
```yaml
llm:
  output_mode: "translate"
  target_language: "English"
```

### Bilingual Mode (`bilingual`)

Display both original and translated text.

```bash
python -m semsub.cli generate video.mp4 --llm --llm-mode bilingual
```

### Supported LLM Services

- **DeepSeek**: `https://api.deepseek.com/v1`
- **Kimi**: `https://api.moonshot.cn/v1`
- **Qwen**: `https://dashscope.aliyuncs.com/compatible-mode/v1`

## GUI Usage

**Gradio Web GUI (Recommended):**

```bash
python -m semsub gui
```

Then open http://localhost:7860 in your browser.

### Interface Features

1. **File Path Input**: Enter video file paths directly (no upload required)
2. **Batch Processing**: Add multiple files to queue
3. **Real-time Progress**: Progress bars and stage status
4. **Settings**: Configure ASR/VAD/Subtitle/LLM parameters
5. **Workspace Management**: View and manage processing workspaces

### Usage Flow

1. **Quick Start**: Enter video path(s), configure options, click "Generate Subtitles"
2. **Batch Processing**: Add multiple video paths, configure batch settings
3. **SRT Processing**: Upload existing SRT files for LLM correction/translation
4. **Settings**: Adjust ASR models, VAD parameters, subtitle optimization, LLM config

**Legacy PyQt6 GUI:**

```bash
python -m semsub.gui.app
```

Note: PyQt6 GUI is no longer maintained. Please use Gradio Web GUI.

## Python API

### Basic Usage

```python
from pathlib import Path
from semsub import PipelineConfig, SubtitlePipeline

# Create configuration
config = PipelineConfig()

# Create pipeline
pipeline = SubtitlePipeline(config)

# Generate subtitles
output = pipeline.generate(Path("video.mp4"))
print(f"Subtitle saved: {output}")
```

### Custom Configuration

```python
from semsub import PipelineConfig

config = PipelineConfig()

# Modify ASR config
config.asr.batch_size = 16
config.asr.language = "Chinese"

# Modify subtitle config
config.subtitle.max_chars = 35
config.subtitle.max_duration = 5.0

# Enable LLM
config.llm.enabled = True
config.llm.api_key = "your-api-key"
config.llm.base_url = "https://api.deepseek.com/v1"
```

### Batch Processing

```python
from pathlib import Path
from semsub.core.batch_scanner import VideoScanner
from semsub.core.batch_pipeline import BatchPipeline
from semsub import PipelineConfig

config = PipelineConfig()

# Scan videos
scanner = VideoScanner()
tasks = scanner.scan(
    paths=[Path("./movies/")],
    recursive=True,
    skip_existing=True
)

# Batch process
pipeline = BatchPipeline(config)
result = pipeline.process(tasks)

print(f"Success: {result.completed_count}/{result.total_count}")
```

## FAQ

### Q: How to specify output filename?

Single file mode:
```bash
python -m semsub.cli generate video.mp4 -o mysubtitle.srt
```

Batch mode:
```bash
python -m semsub.cli generate ./movies/ --output-dir ./subs/
# Output: ./subs/movie1.srt, ./subs/movie2.srt ...
```

### Q: How to retry after failure?

Check status:
```bash
python -m semsub.cli status video.mp4
```

Retry from failed stage:
```bash
python -m semsub.cli run-stage video.mp4 03_asr_transcribe --force
```

### Q: How to change model paths?

Edit user configuration:
```bash
python -m semsub.cli config edit
```

Add:
```yaml
asr:
  model_path: "/your/path/Qwen3-ASR-1.7B"
  aligner_path: "/your/path/Qwen3-ForcedAligner-0.6B"
```

### Q: Why is FFmpeg required?

FFmpeg is used for audio extraction from videos. Ensure FFmpeg is installed and in system PATH:

```bash
ffmpeg -version
```

### Q: How to disable GPU?

Set in configuration:
```yaml
asr:
  device: "cpu"
```

**Note**: CPU inference is very slow, not recommended.

### Q: Workspace taking too much space?

The workspace contains extracted audio files (~30% of original video size). Clean after processing:

```bash
python -m semsub.cli clean video.mp4
```

## Project Structure

```
semsub/
├── core/                    # Core modules
│   ├── config.py            # Configuration dataclasses
│   ├── models.py            # Data models
│   ├── merger.py            # Subtitle merge optimization
│   ├── pipeline.py          # Main pipeline
│   ├── workspace.py         # Workspace management
│   ├── batch_scanner.py     # Video scanning
│   ├── batch_pipeline.py    # Batch processing
│   ├── stages/              # Processing stages
│   │   ├── audio_extract.py
│   │   ├── vad_split.py
│   │   ├── asr_transcribe.py
│   │   ├── subtitle_optimize.py
│   │   └── llm_postprocess.py
│   ├── llm/                 # LLM interfaces
│   └── prompts/             # Prompt templates
├── cli/                     # Command-line interface
├── gradio_gui/              # Gradio Web GUI (recommended)
│   ├── app.py               # Gradio app entry
│   ├── pages/               # Page modules
│   │   ├── home.py          # Quick start page
│   │   ├── batch.py         # Batch processing page
│   │   ├── srt_process.py   # SRT processing page
│   │   ├── workspaces.py    # Workspace management
│   │   └── settings.py      # Settings page
│   ├── state.py             # Global state management
│   └── utils.py             # Utility functions
├── gui/                     # PyQt6 graphical interface (legacy)
└── presets/                 # Scene presets
```

## Dependencies

- Python 3.10+
- PyTorch 2.7.1 + CUDA 12.8
- qwen-asr 0.0.6
- silero-vad 6.2.1
- gradio 6.x (Web GUI)
- openai 1.109.1

**Optional:**
- playwright + pytest-playwright (for GUI testing)

## License

MIT License
