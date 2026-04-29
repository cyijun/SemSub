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

**pytest:**
```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_gradio_gui.py -v

# Run end-to-end tests (requires GUI server running)
pytest tests/test_gradio_e2e.py -v -s

# Run with coverage
pytest tests/ --cov=semsub --cov-report=term-missing
```

**Playwright Tests (Gradio GUI):**
```bash
# Install Playwright
pip install playwright pytest-playwright

# Run GUI tests
pytest tests/test_gradio_gui.py -v

# Run E2E tests with sample video
pytest tests/test_gradio_e2e.py -v -s
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

**GUI 特性：**
- 文件路径输入（无需上传，支持大文件）
- 5 个功能页面：快速开始、批量处理、SRT处理、工作区、设置
- 实时进度显示和日志输出
- 完整的 ASR/VAD/字幕/LLM 配置界面

### Web API Endpoints

**文件操作：**
- `POST /api/upload` - 文件上传，返回 `{path, filename}`
- `GET /api/download?path=&filename=` - 安全文件下载（支持 temp 目录、workspace 目录、job output_path）

**配置管理：**
- `GET /api/config/project` - 获取项目级配置
- `GET /api/config/source` - 获取各配置段的来源信息 `{sources, has_project_config, has_user_config}`
- `POST /api/config?target=user|project` - 保存配置到指定层级

**任务管理：**
- `DELETE /api/job/{job_id}` - 删除任务记录

**Web GUI (FastAPI + Jinja2):**
```bash
# 启动 Web 界面
python -m semsub.web.main

# 指定端口
python -m semsub.web.main --port 8080
```

**Web GUI 特性：**
- 浏览器端文件上传与下载
- SSE 实时进度推送
- 双层配置管理（project / user）
- SRT 独立处理工作流

**PyQt6 GUI (旧版，不再维护):**
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
├── gui/                     # PyQt6 graphical interface (legacy, unmaintained)
│   ├── app.py               # GUI entry point
│   ├── workers/             # QThread workers
│   └── widgets/             # Custom widgets
├── gradio_gui/              # Gradio Web GUI (recommended)
│   ├── app.py               # Gradio app entry
│   ├── pages/               # Page modules
│   │   ├── home.py          # Quick start page (file path input)
│   │   ├── batch.py         # Batch processing page
│   │   ├── srt_process.py   # SRT processing page
│   │   ├── workspaces.py    # Workspace management page
│   │   └── settings.py      # Settings page (ASR/VAD/Subtitle/LLM tabs)
│   ├── state.py             # Global state management with ProcessingJob
│   └── utils.py             # Utility functions
└── web/                     # FastAPI + Jinja2 Web GUI
    ├── main.py              # FastAPI app entry
    ├── job_manager.py       # In-memory job tracking
    ├── progress_reporter.py # WebProgressReporter (SSE)
    ├── routes/
    │   └── api.py           # REST API endpoints
    ├── static/              # CSS, JS assets
    └── templates/           # Jinja2 templates
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

**Web GUI 双层配置管理：**
- 设置页面加载 `/config/project` 或 `/config/user`，而非 merged config
- `POST /config?target=` 保存到指定层级
- `/config/source` 返回各段的来源，前端用来显示 source badge
- 默认层为 project（如果存在），因为它是实际生效的最高优先级配置

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

### SRT 处理浏览器工作流

Web GUI 的 SRT 处理页面采用浏览器端上传/下载模式：

1. **上传**：前端 `FormData` → `POST /api/upload` → 存到 `temp/semsub_uploads/`
2. **处理**：前端提交路径 → `POST /api/job/srt-process`（带 `original_filename`）→ 后台 `_run_srt_process`
3. **输出**：默认到 `temp/semsub_outputs/`，自动重名处理
4. **下载**：`/api/download?path=&filename=` + `<a download>` 属性
5. **进度**：SSE `/api/sse/job/{job_id}`
6. **历史**：`GET /api/job/list` 过滤 `type === 'srt_process'`

### File Download 安全机制

- `/download` 允许的目录：UPLOAD_DIR、OUTPUT_DIR、tempdir、workspace `.semsub` 目录
- 额外允许：任何已完成 job 的 `result.output_path`
- `?filename=` 参数设置 Content-Disposition 友好文件名

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

### GUI Development

**Gradio GUI Architecture:**
- Uses Gradio 6.x with Blocks API
- Pages are defined in `semsub/gradio_gui/pages/`
- State management in `semsub/gradio_gui/state.py` with `StateManager` and `ProcessingJob`
- File path input instead of file upload (supports large files without browser upload)

**Gradio File Path Input Pattern:**
```python
# Gradio GUI uses file path input (not upload) for large files
file_path_input = gr.Textbox(
    label="视频文件路径（每行一个）",
    placeholder="/path/to/movie.mp4\n/path/to/another.mkv",
    lines=3,
)

# Parse paths on the server side
paths = parse_video_paths(path_text)  # Returns List[Path]
```

**WorkspaceManager API (Common bug source)**
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

### Progress Reporter Compatibility

The `ProgressReporter` interface supports both old and new calling conventions:
```python
# Old way (stage_id as string)
reporter.on_progress("03_asr_transcribe", current=10, total=100, message="Processing...")

# New way (StageProgress object from core)
reporter.on_progress(StageProgress(stage=stage, current=10, total=100, message="..."))
```

## Dependencies

```bash
# PyTorch with CUDA
pip install torch==2.7.1 torchvision==0.22.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu128

# Core dependencies
pip install qwen-asr silero-vad torchcodec openai click rich pyyaml pydantic

# Gradio GUI
pip install gradio

# Testing
pip install pytest playwright pytest-playwright

# System requirement: FFmpeg in PATH
```
