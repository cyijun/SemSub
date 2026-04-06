# SemSub Project Documentation

## Project Overview

This is a **speech recognition and subtitle generation project** that uses Alibaba's Qwen3-ASR models for automatic speech recognition (ASR) and Silero VAD (Voice Activity Detection) for audio segmentation.

The project consists of Jupyter notebooks that demonstrate:
1. Using Qwen3-ASR models to transcribe audio files with automatic language detection
2. Performing forced alignment for timestamp generation
3. Using Silero VAD to detect and segment speech regions from audio/video files
4. Extracting audio from video files using FFmpeg

## Project Structure

```
/mnt/d/temp/SemSub/
├── install.sh       # uv installer script (version 0.11.2) for Python package management
├── qwenasr.ipynb    # Qwen3-ASR model usage examples
└── sub.ipynb        # Subtitle generation using Silero VAD and audio segmentation
```

## Technology Stack

### Programming Environment
- **Python Version**: 3.12.13
- **Package Manager**: uv (Astral's Python package installer) - version 0.11.2
- **Kernel**: `qwen3-asr` (Jupyter kernel)

### Core Dependencies
| Package | Purpose |
|---------|---------|
| torch | PyTorch deep learning framework |
| qwen_asr | Qwen3-ASR model interface for speech recognition |
| torchaudio | Audio processing and I/O |
| silero_vad | Voice Activity Detection |
| torchcodec | Audio/video codec support (for torchaudio backend) |
| FFmpeg | Audio extraction from video files |

### Model Requirements
- **Qwen3-ASR-1.7B** - Main ASR model for speech-to-text transcription
- **Qwen3-ForcedAligner-0.6B** (optional) - For timestamp alignment
- **Silero VAD** - Speech segmentation model (loaded via torch.hub)

### Hardware Requirements
- CUDA-capable GPU recommended (notebooks use `cuda:0`)
- Sufficient VRAM for loading ASR models

## Build and Setup Instructions

### 1. Install uv (Python Package Manager)

The `install.sh` script is the official uv installer (version 0.11.2) from Astral:

```bash
# Install uv to ~/.local/bin by default
./install.sh

# Or install to a specific directory
UV_INSTALL_DIR=/custom/path ./install.sh

# Without modifying PATH
UV_NO_MODIFY_PATH=1 ./install.sh
```

The installer supports multiple platforms:
- Linux (x86_64, aarch64, armv7, i686, etc.)
- macOS (x86_64, Apple Silicon)
- Windows (MSVC toolchain)

### 2. Create Python Environment

```bash
# Using uv to create a virtual environment
uv venv --python 3.12

# Activate the environment
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate  # Windows
```

### 3. Install Dependencies

```bash
# Install PyTorch with CUDA support
uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# Install Qwen3-ASR
uv pip install qwen_asr

# Install Silero VAD dependencies
uv pip install silero-vad

# Install torchcodec (required for torchaudio backend)
uv pip install torchcodec
```

### 4. Download Models

Models are loaded from local paths or HuggingFace:
- Qwen3-ASR-1.7B: Download to `/mnt/g/models/Qwen3-ASR-1.7B`
- Qwen3-ForcedAligner-0.6B: Download to `/mnt/g/models/Qwen3-ForcedAligner-0.6B`

## Usage

### Qwen3-ASR Speech Recognition (`qwenasr.ipynb`)

```python
import torch
from qwen_asr import Qwen3ASRModel

# Load the model
model = Qwen3ASRModel.from_pretrained(
    '/path/to/Qwen3-ASR-1.7B',
    dtype=torch.bfloat16,
    device_map="cuda:0",
    max_inference_batch_size=32,
    max_new_tokens=256,
)

# Transcribe audio
results = model.transcribe(
    audio="path/to/audio.wav",
    language=None,  # Auto-detect language, or specify "English", "Chinese", etc.
)

print(results[0].language)
print(results[0].text)
```

### Forced Alignment with Timestamps

```python
model = Qwen3ASRModel.from_pretrained(
    '/path/to/Qwen3-ASR-1.7B',
    dtype=torch.bfloat16,
    device_map="cuda:0",
    forced_aligner='/path/to/Qwen3-ForcedAligner-0.6B',
    forced_aligner_kwargs=dict(
        dtype=torch.bfloat16,
        device_map="cuda:0",
    ),
)

results = model.transcribe(
    audio=["audio1.wav", "audio2.wav"],
    language=["Chinese", "English"],
    return_time_stamps=True,
)
```

### Audio Segmentation with Silero VAD (`sub.ipynb`)

```python
import torch
import torchaudio

# Load Silero VAD model
model, utils = torch.hub.load(
    repo_or_dir='snakers4/silero-vad',
    model='silero_vad',
    force_reload=False
)
(get_speech_timestamps, save_audio, read_audio, VADIterator, collect_chunks) = utils

# Read audio
wav = read_audio("audio.wav", sampling_rate=16000)

# Get speech timestamps
speech_timestamps = get_speech_timestamps(
    wav,
    model,
    sampling_rate=16000,
    threshold=0.5,
    min_speech_duration_ms=250,
    min_silence_duration_ms=500,
)
```

### Video to Audio Extraction

```python
import subprocess
from pathlib import Path

def extract_audio(video_path, output_wav=None, sample_rate=16000):
    video_path = Path(video_path)
    if output_wav is None:
        output_wav = video_path.with_suffix('.wav')
    
    cmd = [
        'ffmpeg', '-y', '-i', str(video_path),
        '-vn',  # No video
        '-acodec', 'pcm_s16le',  # 16-bit PCM
        '-ac', '1',  # Mono
        '-ar', str(sample_rate),  # 16kHz
        str(output_wav)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_wav
```

## Code Organization

### Notebooks

1. **`qwenasr.ipynb`** - Qwen3-ASR examples:
   - Basic transcription with automatic language detection
   - Batch transcription with forced alignment for timestamps
   - Multilingual support (Chinese, English, etc.)

2. **`sub.ipynb`** - Subtitle generation pipeline:
   - Video to audio conversion using FFmpeg
   - Voice activity detection using Silero VAD
   - Audio segmentation and saving with metadata
   - Statistics generation for speech segments

### Data Flow

```
Video File → FFmpeg → WAV Audio → Silero VAD → Speech Segments → Qwen3-ASR → Transcription + Timestamps
```

## Development Conventions

### Language
- Comments and documentation are primarily in **Chinese**
- Variable names use English

### Configuration Parameters

#### VAD Parameters
- `threshold`: 0.5 (speech detection sensitivity)
- `min_speech_duration_ms`: 250 (ignore speech shorter than 250ms)
- `min_silence_duration_ms`: 500 (split segments at 500ms silence)
- `sampling_rate`: 16000 Hz

#### ASR Parameters
- `dtype`: `torch.bfloat16` for memory efficiency
- `max_new_tokens`: 256 (maximum output length)
- `max_inference_batch_size`: 32 (batch processing size)

### Path Conventions
- Windows paths use forward slashes or escaped backslashes
- Linux paths use absolute paths like `/mnt/g/models/`
- Output directory: `segments/` for audio segments

## Known Issues and Solutions

### 1. FFmpeg Compatibility
- **Issue**: FFmpeg DLL loading errors on Windows
- **Solution**: Install "full-shared" version of FFmpeg with all DLLs

### 2. torchcodec Compatibility
- **Issue**: PyTorch version (2.11.0+cu130) may not be compatible with torchcodec
- **Solution**: Check [torchcodec compatibility table](https://github.com/pytorch/torchcodec?tab=readme-ov-file#installing-torchcodec)

### 3. Kernel Crashes
- **Issue**: Jupyter kernel crashes during audio processing
- **Solution**: Ensure sufficient memory and correct CUDA drivers

## Testing

This project uses Jupyter notebooks for interactive development. To verify the setup:

1. Run all cells in `qwenasr.ipynb` to verify ASR functionality
2. Run all cells in `sub.ipynb` to verify VAD and segmentation

## Security Considerations

1. **Model Downloads**: Models are downloaded from official sources:
   - Qwen models: HuggingFace or local paths
   - Silero VAD: GitHub repository `snakers4/silero-vad`

2. **Audio URLs**: Notebooks use HTTPS URLs for sample audio files from `qianwen-res.oss-cn-beijing.aliyuncs.com`

3. **FFmpeg**: Ensure FFmpeg is installed from trusted sources to avoid codec vulnerabilities

## References

- [Qwen3-ASR Documentation](https://huggingface.co/Qwen)
- [Silero VAD GitHub](https://github.com/snakers4/silero-vad)
- [uv Documentation](https://docs.astral.sh/uv/)
- [torchaudio Documentation](https://pytorch.org/audio/stable/index.html)
