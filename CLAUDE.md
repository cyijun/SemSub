# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SemSub is a speech recognition and subtitle generation project with both CLI and GUI interfaces. It generates optimized movie subtitles using:
- **Qwen3-ASR-1.7B** for speech-to-text transcription
- **Qwen3-ForcedAligner-0.6B** for word-level timestamp alignment
- **Silero VAD** for voice activity detection
- **FFmpeg** for audio extraction

## Common Commands

### Run Tests

**Legacy tests:**
```bash
python test_new_arch.py
python test_subtitle_merger.py
```

**pytest (GUI tests require pytest-qt):**
```bash
# Install pytest-qt first
pip install pytest-qt

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_gui.py -v

# Run GUI tests (requires display)
pytest tests/test_gui.py -v --qt-api pyqt6

# Run with coverage
pytest tests/ --cov=semsub --cov-report=term-missing
```

### CLI - Generate Subtitles

**Single video:**
```bash
python -m semsub.cli generate video.mp4
python -m semsub.cli generate video.mp4 -o output.srt --preset movie
```

**Batch directory processing:**
```bash
python -m semsub.cli generate ./movies/
python -m semsub.cli generate ./season1/ ./season2/ --output-dir ./subtitles/
python -m semsub.cli generate ./videos/ --skip-existing --continue-on-error
```

**Stage-specific execution:**
```bash
# View status
python -m semsub.cli status video.mp4

# Run specific stage
python -m semsub.cli run-stage video.mp4 03_asr_transcribe

# Force re-run from a stage
python -m semsub.cli run-stage video.mp4 04_subtitle_optimize --force

# Execute range
python -m semsub.cli generate video.mp4 --from 03_asr_transcribe --to 04_subtitle_optimize
```

**Workspace management:**
```bash
python -m semsub.cli init video.mp4
python -m semsub.cli clean video.mp4          # Remove workspace
python -m semsub.cli clean video.mp4 --all    # Include output files
```

### GUI

**Gradio Web GUI (推荐):**
```bash
# 启动 Gradio Web 界面
python -m semsub gui

# 指定端口
python -m semsub gui --port 7860

# 创建公开分享链接
python -m semsub gui --share

# 直接启动 Gradio GUI 模块
python -m semsub.gradio_gui
```

**PyQt6 GUI (旧版):**
```bash
python -m semsub.gui.app
```

### Process SRT Files (Standalone LLM Processing)
```bash
# Process existing SRT file with LLM
python -m semsub.cli process-srt input.srt -o output.srt --llm-mode correct

# With specific provider and response format
python -m semsub.cli process-srt input.srt -o output.srt \
    --provider ollama \
    --response-format tool_calling \
    --llm-mode translate
```

### Legacy Scripts (still functional)
```bash
python generate_subtitles.py video.mp4
python run_subtitle.py video.mp4
```

## High-Level Architecture

### Package Structure

```
semsub/
├── core/                    # Core business logic
│   ├── pipeline.py          # SubtitlePipeline, StageExecutor
│   ├── workspace.py         # WorkspaceManager, Workspace, StageContext
│   ├── state_models.py      # Pydantic models for state persistence
│   ├── config.py            # PipelineConfig dataclass
│   ├── progress.py          # ProgressReporter interfaces
│   ├── merger.py            # Subtitle optimization engine
│   ├── models.py            # SubtitleLine data class
│   ├── batch_scanner.py     # VideoScanner for directory input
│   ├── batch_pipeline.py    # BatchPipeline for multi-video processing
│   ├── stages/              # 5 processing stages
│   │   ├── base.py          # PipelineStage abstract base
│   │   ├── audio_extract.py # Stage 01: FFmpeg audio extraction
│   │   ├── vad_split.py     # Stage 02: Silero VAD segmentation
│   │   ├── asr_transcribe.py# Stage 03: Qwen ASR + forced alignment
│   │   ├── subtitle_optimize.py  # Stage 04: SubtitleMerger
│   │   └── llm_postprocess.py    # Stage 05: LLM correction/translation
│   ├── llm/                 # LLM provider implementations
│   └── utils/               # File I/O utilities
├── cli/                     # Command-line interface
│   ├── main.py              # CLI entry point
│   └── commands/            # Subcommands (generate, status, run_stage, gui, etc.)
├── gui/                     # PyQt6 graphical interface (legacy)
│   ├── app.py               # GUI entry point
│   ├── main_window.py       # Main window with batch processing
│   ├── workers/             # QThread workers
│   │   ├── pipeline_worker.py
│   │   └── batch_worker.py
│   └── widgets/             # Custom widgets
│       ├── stage_flow_widget.py
│       └── workspace_panel.py
└── gradio_gui/              # Gradio Web GUI (recommended)
    ├── app.py               # Gradio app entry
    ├── pages/               # Page modules
    │   ├── home.py          # Quick start page
    │   ├── batch.py         # Batch processing page
    │   ├── srt_process.py   # SRT processing page
    │   ├── workspaces.py    # Workspace management page
    │   └── settings.py      # Settings page
    ├── state.py             # Global state management
    └── utils.py             # Utility functions
```

### Pipeline Stages

| Stage ID | Name | Input | Output | Dependencies |
|----------|------|-------|--------|--------------|
| 01_audio_extract | 音频提取 | video.mp4 | audio.wav | - |
| 02_vad_split | VAD分割 | audio.wav | segments.json | 01 |
| 03_asr_transcribe | ASR转录 | audio.wav, segments.json | transcripts.json | 02 |
| 04_subtitle_optimize | 字幕优化 | segments.json, transcripts.json | subtitles.json | 02, 03 |
| 05_llm_postprocess | LLM后处理 | subtitles.json | subtitles_llm.json | 04 |

### Workspace System

Each video gets a `.semsub/` workspace directory for persistence:

```
video.mp4
.semsub/
├── state.json               # Global workspace state
├── config.yaml              # Config snapshot at creation
├── 01_audio_extract/
│   ├── state.json           # Stage status (pending/running/completed/failed)
│   ├── input.json           # Dependencies and parameters
│   ├── output.json          # Output artifacts and statistics
│   └── audio.wav            # Actual artifact file
├── 02_vad_split/
│   ├── state.json
│   ├── input.json
│   ├── output.json
│   └── segments.json
└── ... (other stages)
```

**Key classes:**
- `WorkspaceManager`: Creates/opens workspaces, computes video hashes
- `Workspace`: Represents a workspace, manages stage contexts, handles locking
- `StageContext`: Per-stage I/O, artifact loading/saving, checkpoint management

### Data Flow

```
Input (file or directory)
    ↓
[VideoScanner] ──→ List[VideoTask]
    ↓
[BatchPipeline] (if multiple videos)
    ↓
[SubtitlePipeline.generate()]
    ↓
[WorkspaceManager] ──→ Workspace
    ↓
For each stage in STAGE_ORDER:
    [StageExecutor]
        - Check dependencies
        - Prepare input artifacts
        - Execute stage implementation
        - Save output artifacts
        - Update state
    ↓
Export final subtitles
```

### Configuration System

**Hierarchy** (highest to lowest priority):
1. CLI arguments (`--language`, `--preset`)
2. Project config (`./semsub.yaml`)
3. User config (`~/.config/semsub/config.yaml`)
4. Built-in preset defaults

**Presets:**
- `movie`: Dense dialogue (max_chars=40, gap_threshold=0.3s)
- `documentary`: Narration (max_chars=35, gap_threshold=0.5s, min_silence=800ms)
- `animation`: Fast speech (max_chars=30, max_duration=4.0s, gap_threshold=0.2s)

### Key Configuration Parameters

```python
# ASR
batch_size = 8              # Inference batch size
language = None             # Auto-detect if None
model_path = "/mnt/g/models/Qwen3-ASR-1.7B"
aligner_path = "/mnt/g/models/Qwen3-ForcedAligner-0.6B"

# VAD
threshold = 0.5
min_speech_duration_ms = 250
min_silence_duration_ms = 500

# Subtitle optimization
max_chars = 40              # Chinese characters per line
max_chars_en = 80           # English characters per line
max_duration = 6.0          # Seconds per line
min_duration = 1.0
gap_threshold = 0.3         # Merge VAD segments closer than this

# LLM Configuration
llm:
  enabled: false
  provider: "openai_compatible"  # Options: openai_compatible, ollama
  response_format: "auto"        # Options: auto, prompt, tool_calling
  api_key: ""
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"
```

### Progress Reporting

```python
# CLI uses RichProgressReporter with live progress bars
# GUI uses QtBatchReporter that emits signals to main thread

class ProgressReporter:
    def on_stage_start(self, stage: PipelineStage, total: int)
    def on_progress(self, progress: StageProgress)
    def on_stage_complete(self, stage: PipelineStage, result)
    def on_error(self, stage: PipelineStage, error: Exception)
```

### Stage Implementation Pattern

```python
class MyStage(PipelineStage):
    name = "My Stage"
    stage_id = "XX_stage_name"

    def execute(self, ctx: StageContext, reporter=None) -> Dict[str, Any]:
        # 1. Load input artifacts from dependencies
        audio_path = ctx.resolve_input_artifact("audio")
        segments = ctx.load_artifact("segments", from_input=True)

        # 2. Load checkpoint if resumable
        checkpoint = ctx.load_checkpoint()

        # 3. Process
        for i, item in enumerate(items):
            # Report progress
            if reporter:
                reporter.on_progress(StageProgress(...))
            # Save checkpoint periodically
            ctx.save_checkpoint({"current": i})

        # 4. Save output artifacts
        output_path = ctx.save_artifact("results", data, "json")

        # 5. Return output spec
        return {
            "artifacts": {"results": {"path": output_path.name}},
            "statistics": {"total": len(items)}
        }
```

### Batch Processing

When directory input is provided:
1. `VideoScanner.scan()` recursively finds all video files
2. `VideoTask` objects created with input/output paths
3. `BatchPipeline.process()` executes serially:
   - One video at a time (predictable resource usage)
   - Per-video progress aggregated into batch progress
   - `--continue-on-error`: continue to next video on failure
   - `--skip-existing`: skip videos that already have output subtitles

## Development Notes

- Comments and docs are primarily in Chinese
- Variable names use English
- Uses `torch.bfloat16` for memory efficiency
- GPU strongly recommended for ASR inference
- File locking via `fcntl.flock` prevents concurrent workspace access
- Atomic file writes via temp file + rename pattern
- Video file hash computed from first 1MB + size + mtime for change detection

### GUI Development Critical Notes

**1. Signal module limitation**
`signal.signal()` only works in the main thread. When using file locking in worker threads (QThread), the code checks `threading.current_thread() is threading.main_thread()` before using signals.

**2. WorkspaceManager API (Common bug source)**
Correct usage in GUI workers:
```python
# Correct
manager = WorkspaceManager(video_path)  # First arg is video_path, not config
workspace = manager.open()  # Returns None if not exists
if workspace is None:
    workspace = manager.initialize(config)
stage_context = workspace.get_stage(stage_id)  # Use get_stage(), not get_stage_context()

# Incorrect (do not use)
manager = WorkspaceManager(config)
workspace = manager.get_workspace(video_path)  # Method doesn't exist
stage_context = workspace.get_stage_context(stage_id)  # Method doesn't exist
```

**3. Qt imports in GUI modules**
Always check for missing imports when adding new Qt classes:
```python
# Common missing imports that cause NameError at runtime
from PyQt6.QtWidgets import QFileDialog, QMessageBox  # Often forgotten
```

## Dependencies

```bash
# PyTorch with CUDA
pip install torch==2.7.1 torchvision==0.22.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu128

# Core dependencies
pip install qwen-asr silero-vad torchcodec PyQt6 openai click rich pyyaml pydantic

# System requirement: FFmpeg in PATH
```
