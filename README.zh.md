# SemSub - 智能字幕生成器

**中文** | [English](README.md)

一个兼具命令行(CLI)和图形界面(GUI)的字幕生成软件，基于 Qwen3-ASR 和 Silero VAD，支持批量处理、工作区管理和 LLM 后处理。

## 功能特性

- **语音分割**: Silero VAD 检测语音片段
- **语音识别**: Qwen3-ASR-1.7B + Forced Aligner 生成精准时间轴
- **字幕优化**: 智能合并、断句、时长控制
- **LLM 后处理**: 支持纠错、翻译、双语字幕
- **批量处理**: 递归扫描目录，批量生成字幕
- **工作区管理**: 分阶段执行，支持断点续传
- **多场景预设**: 电影、纪录片、动画优化配置

## 安装

### 系统要求

- Python 3.10+
- CUDA 12.8 (推荐，用于 GPU 加速)
- FFmpeg (系统 PATH 中可用)

### 安装步骤

```bash
# 克隆仓库
git clone https://github.com/cyijun/SemSub.git
cd SemSub

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装 PyTorch (CUDA 12.8)
pip install torch==2.7.1 torchvision==0.22.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu128

# 安装项目依赖
pip install -r requirements.txt
```

### 模型下载

需要下载以下模型到本地：

- **ASR 模型**: [Qwen3-ASR-1.7B](https://huggingface.co/Qwen/Qwen3-ASR-1.7B)
- **对齐模型**: [Qwen3-ForcedAligner-0.6B](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B)

在配置文件中指定模型路径（见配置说明）。

## 快速开始

### 1. 生成单视频字幕

```bash
python -m semsub.cli generate video.mp4
```

### 2. 启动图形界面

```bash
python -m semsub.gui.app
```

### 3. 批量处理目录

```bash
python -m semsub.cli generate ./movies/ --output-dir ./subtitles/
```

## CLI 命令详解

### `generate` - 生成字幕

基本用法：
```bash
python -m semsub.cli generate <输入路径> [选项]
```

**输入路径**可以是：
- 单个视频文件: `video.mp4`
- 多个文件: `video1.mp4 video2.mp4`
- 目录: `./movies/`（自动递归扫描）

**常用选项**:

| 选项 | 说明 | 示例 |
|------|------|------|
| `-o, --output` | 单文件输出路径 | `-o output.srt` |
| `--output-dir` | 批量输出目录 | `--output-dir ./subs/` |
| `--preset` | 使用预设配置 | `--preset movie` |
| `-l, --language` | 指定语言 | `-l Chinese` |
| `-f, --format` | 输出格式 (srt/vtt/json) | `-f srt` |
| `--llm` | 启用 LLM 后处理 | `--llm` |
| `--llm-mode` | LLM 模式 (correct/translate/bilingual) | `--llm-mode translate` |
| `--skip-existing` | 跳过已有字幕的视频 | `--skip-existing` |
| `--continue-on-error` | 出错继续处理 | `--continue-on-error` |

**示例**:

```bash
# 基本用法
python -m semsub.cli generate video.mp4

# 使用电影预设，启用 LLM 纠错
python -m semsub.cli generate video.mp4 --preset movie --llm --llm-mode correct

# 批量处理目录，跳过已存在的字幕
python -m semsub.cli generate ./season1/ --output-dir ./subs/ --skip-existing

# 混合输入（文件+目录）
python -m semsub.cli generate video1.mp4 ./episodes/ video2.mkv --output-dir ./output/
```

### `status` - 查看工作区状态

```bash
# 查看视频处理状态
python -m semsub.cli status video.mp4

# 详细输出（包含文件路径）
python -m semsub.cli status video.mp4 --verbose
```

输出示例：
```
工作区: /path/to/.semsub
视频: video.mp4
状态: 运行中 (ASR 转录 15/42)

阶段状态:
  ✓ 音频提取     completed    00:05
  ✓ VAD 分割     completed    00:03
  ▶ ASR 转录     running      02:05  35%
  ⏸ 字幕优化     pending
  ⏸ LLM后处理   pending (未启用)
```

### `run-stage` - 执行单个阶段

用于调试或从特定阶段重新开始：

```bash
# 运行特定阶段
python -m semsub.cli run-stage video.mp4 03_asr_transcribe

# 强制重新执行（会级联影响后续阶段）
python -m semsub.cli run-stage video.mp4 04_subtitle_optimize --force

# 从检查点恢复（仅 ASR 阶段支持）
python -m semsub.cli run-stage video.mp4 03_asr_transcribe --resume
```

**阶段 ID 列表**:
- `01_audio_extract` - 音频提取
- `02_vad_split` - VAD 分割
- `03_asr_transcribe` - ASR 转录
- `04_subtitle_optimize` - 字幕优化
- `05_llm_postprocess` - LLM 后处理

### `init` / `clean` - 工作区管理

```bash
# 初始化工作区（不执行）
python -m semsub.cli init video.mp4

# 清理工作区
python -m semsub.cli clean video.mp4

# 清理但保留输出字幕
python -m semsub.cli clean video.mp4 --keep-output
```

### `config` - 配置管理

```bash
# 查看当前配置
python -m semsub.cli config show

# 查看配置（包含默认值）
python -m semsub.cli config show --all

# 编辑用户配置
python -m semsub.cli config edit
```

## 场景预设

SemSub 提供三种针对特定场景的优化预设：

### `movie` - 电影（默认）

适合对白密集的电影场景。

```yaml
subtitle:
  max_chars: 40              # 每行最多 40 字符
  max_duration: 6.0          # 最长显示 6 秒
  gap_threshold: 0.3         # 合并间隔小于 0.3s 的片段
vad:
  min_silence_duration_ms: 300
```

### `documentary` - 纪录片

适合旁白 narration 场景。

```yaml
subtitle:
  max_chars: 35
  max_duration: 7.0          # 更长显示时间
  gap_threshold: 0.5         # 更大合并阈值
vad:
  min_silence_duration_ms: 800
```

### `animation` - 动画

适合语速较快的动画场景。

```yaml
subtitle:
  max_chars: 30
  max_duration: 4.0          # 更快切换
  gap_threshold: 0.2
  target_reading_speed: 8.0  # 目标阅读速度 8 字符/秒
vad:
  min_silence_duration_ms: 200
```

**使用预设**:
```bash
python -m semsub.cli generate video.mp4 --preset documentary
```

## 配置详解

配置文件使用 YAML 格式，支持三级覆盖：

1. **命令行参数** (最高优先级)
2. **项目配置** (`./semsub.yaml`)
3. **用户配置** (`~/.config/semsub/config.yaml`)
4. **内置预设** (最低优先级)

### 完整配置示例

```yaml
# ASR 配置
asr:
  model_path: "/mnt/g/models/Qwen3-ASR-1.7B"
  aligner_path: "/mnt/g/models/Qwen3-ForcedAligner-0.6B"
  device: "cuda:0"
  batch_size: 8
  language: null              # null = 自动检测

# VAD 配置
vad:
  threshold: 0.5
  min_speech_duration_ms: 250
  min_silence_duration_ms: 500

# 字幕优化配置
subtitle:
  max_chars: 40               # 中文每行最大字符
  max_chars_en: 80            # 英文每行最大字符
  min_chars: 10               # 每行最小字符
  max_duration: 6.0           # 每行最大显示时长（秒）
  min_duration: 1.0           # 每行最小显示时长（秒）
  gap_threshold: 0.3          # VAD 片段合并阈值（秒）
  target_reading_speed: 6.0   # 目标阅读速度（字符/秒）

# LLM 后处理配置
llm:
  enabled: false
  provider: "openai_compatible"
  api_key: ""                 # 你的 API key
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"
  prompt_template: "correct.zh"
  output_mode: "correct"      # correct/translate/bilingual
  batch_size: 10
  max_tokens: 4096
  temperature: 0.3
  timeout: 60

# 输出配置
output:
  format: "srt"               # srt/vtt/json
  save_intermediate: false    # 保存中间文件
```

### 生成用户配置

首次运行前建议创建用户配置文件：

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

## 工作区说明

SemSub 使用工作区（Workspace）机制管理处理流程，默认在视频所在目录创建 `.semsub/` 隐藏目录。

### 工作区结构

```
video.mp4
.semsub/
├── state.json               # 全局状态
├── config.yaml              # 配置快照
├── 01_audio_extract/
│   ├── state.json           # 阶段状态
│   ├── input.json           # 输入依赖
│   ├── output.json          # 输出描述
│   └── audio.wav            # 实际音频文件
├── 02_vad_split/
│   └── segments.json        # 语音片段
├── 03_asr_transcribe/
│   ├── transcripts.json     # 转录结果
│   └── checkpoint.json      # 断点续传进度
└── ...
```

### 工作区用途

1. **断点续传**: ASR 转录中断后可从中断处恢复
2. **分阶段调试**: 可单独执行、重试某个阶段
3. **配置快照**: 保存处理时的配置，便于追溯
4. **中间结果**: 可查看/导出各阶段输出

### 清理工作区

处理完成后可删除工作区节省空间：

```bash
# 仅删除工作区，保留字幕
python -m semsub.cli clean video.mp4

# 查看工作区占用空间
du -sh video.mp4/.semsub
```

**注意**: 删除工作区后无法断点续传，需重新完整处理。

## LLM 后处理

支持 OpenAI 兼容接口，可用于：

### 纠错模式 (`correct`)

修正语音识别错误，如同音字、标点等。

```bash
python -m semsub.cli generate video.mp4 --llm --llm-mode correct
```

### 翻译模式 (`translate`)

将字幕翻译为目标语言。

```bash
python -m semsub.cli generate video.mp4 --llm --llm-mode translate
```

在配置中设置 `target_language`：
```yaml
llm:
  output_mode: "translate"
  target_language: "English"
```

### 双语模式 (`bilingual`)

原文和译文同时显示。

```bash
python -m semsub.cli generate video.mp4 --llm --llm-mode bilingual
```

### 支持的 LLM 服务

- **DeepSeek**: `https://api.deepseek.com/v1`
- **Kimi**: `https://api.moonshot.cn/v1`
- **通义千问**: `https://dashscope.aliyuncs.com/compatible-mode/v1`

## GUI 使用说明

启动图形界面：

```bash
python -m semsub.gui.app
```

### 界面功能

1. **文件选择**: 支持拖拽或点击选择视频文件/目录
2. **批量列表**: 显示待处理的视频队列
3. **双进度条**: 整体进度 + 当前视频进度
4. **阶段可视化**: 5 个处理阶段的状态显示
5. **实时日志**: 查看处理日志输出

### 使用流程

1. 点击「添加文件」或「添加目录」选择视频
2. 选择预设配置（可选）
3. 勾选「启用 LLM」并配置（可选）
4. 点击「开始处理」

## Python API

### 基础用法

```python
from pathlib import Path
from semsub import PipelineConfig, SubtitlePipeline

# 创建配置
config = PipelineConfig()

# 创建管道
pipeline = SubtitlePipeline(config)

# 生成字幕
output = pipeline.generate(Path("video.mp4"))
print(f"字幕已保存: {output}")
```

### 自定义配置

```python
from semsub import PipelineConfig

config = PipelineConfig()

# 修改 ASR 配置
config.asr.batch_size = 16
config.asr.language = "Chinese"

# 修改字幕配置
config.subtitle.max_chars = 35
config.subtitle.max_duration = 5.0

# 启用 LLM
config.llm.enabled = True
config.llm.api_key = "your-api-key"
config.llm.base_url = "https://api.deepseek.com/v1"
```

### 批量处理

```python
from pathlib import Path
from semsub.core.batch_scanner import VideoScanner
from semsub.core.batch_pipeline import BatchPipeline
from semsub import PipelineConfig

config = PipelineConfig()

# 扫描视频
scanner = VideoScanner()
tasks = scanner.scan(
    paths=[Path("./movies/")],
    recursive=True,
    skip_existing=True
)

# 批量处理
pipeline = BatchPipeline(config)
result = pipeline.process(tasks)

print(f"成功: {result.completed_count}/{result.total_count}")
```

## 常见问题

### Q: 如何指定输出文件名？

单文件模式：
```bash
python -m semsub.cli generate video.mp4 -o mysubtitle.srt
```

批量模式：
```bash
python -m semsub.cli generate ./movies/ --output-dir ./subs/
# 输出: ./subs/movie1.srt, ./subs/movie2.srt ...
```

### Q: 处理失败如何重试？

查看状态：
```bash
python -m semsub.cli status video.mp4
```

从失败阶段重试：
```bash
python -m semsub.cli run-stage video.mp4 03_asr_transcribe --force
```

### Q: 如何更改模型路径？

编辑用户配置文件：
```bash
python -m semsub.cli config edit
```

添加：
```yaml
asr:
  model_path: "/your/path/Qwen3-ASR-1.7B"
  aligner_path: "/your/path/Qwen3-ForcedAligner-0.6B"
```

### Q: 为什么需要 FFmpeg？

FFmpeg 用于从视频提取音频。请确保 FFmpeg 已安装并在系统 PATH 中：

```bash
ffmpeg -version
```

### Q: 如何禁用 GPU？

在配置中设置：
```yaml
asr:
  device: "cpu"
```

**注意**: CPU 推理速度很慢，不推荐。

### Q: 工作区占用太多空间？

工作区包含提取的音频文件（约原视频 30%），处理完成后可清理：

```bash
python -m semsub.cli clean video.mp4
```

## 项目结构

```
semsub/
├── core/                    # 核心模块
│   ├── config.py            # 配置数据类
│   ├── models.py            # 数据模型
│   ├── merger.py            # 字幕合并优化
│   ├── pipeline.py          # 主管道
│   ├── workspace.py         # 工作区管理
│   ├── batch_scanner.py     # 视频扫描
│   ├── batch_pipeline.py    # 批量处理
│   ├── stages/              # 处理阶段
│   │   ├── audio_extract.py
│   │   ├── vad_split.py
│   │   ├── asr_transcribe.py
│   │   ├── subtitle_optimize.py
│   │   └── llm_postprocess.py
│   ├── llm/                 # LLM 接口
│   └── prompts/             # 提示词模板
├── cli/                     # 命令行界面
├── gui/                     # PyQt6 图形界面
└── presets/                 # 场景预设
```

## 依赖版本

- Python 3.10+
- PyTorch 2.7.1 + CUDA 12.8
- qwen-asr 0.0.6
- silero-vad 6.2.1
- PyQt6 6.11.0
- openai 1.109.1

## License

MIT License
