# SemSub - 智能字幕生成器

**中文** | [English](README.md)

基于 Qwen3-ASR 和 Silero VAD 的高质量字幕生成工具。

```bash
# 快速开始 - 单视频
python -m semsub.cli generate video.mp4

# 图形界面（推荐）
python -m semsub gui
```

## 功能特性

- **精准识别**: Qwen3-ASR-1.7B + Forced Aligner 实现词级时间戳
- **智能优化**: 自动断句、合并、时长控制
- **LLM 增强**: 错别字纠正、翻译、双语字幕
- **批量处理**: 一行命令处理整个目录
- **断点续传**: 中断后可从中断处恢复
- **SRT 浏览器上传/下载**: Web GUI 支持拖拽上传 SRT 文件，处理完成后直接下载
- **双层配置管理**: VSCode 风格的项目配置 + 用户配置切换编辑

## 安装

```bash
# 1. 创建环境并安装
python -m venv venv && source venv/bin/activate
pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt

# 2. 下载模型到本地
# - https://huggingface.co/Qwen/Qwen3-ASR-1.7B
# - https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B

# 3. 配置模型路径
mkdir -p ~/.config/semsub
cat > ~/.config/semsub/config.yaml << 'EOF'
asr:
  model_path: "/path/to/Qwen3-ASR-1.7B"
  aligner_path: "/path/to/Qwen3-ForcedAligner-0.6B"
  device: "cuda:0"
EOF
```

## 使用指南

### Gradio Web 图形界面（推荐）

最简单的使用方式：

```bash
python -m semsub gui
# 浏览器打开 http://localhost:7860
```

**功能特点：**
- 直接输入视频文件路径（无需上传，支持大文件）
- 5 个功能页面：快速开始、批量处理、SRT 处理、工作区、设置
- 实时进度显示，分阶段展示处理状态
- 完整的 ASR/VAD/字幕/LLM 参数配置
- **SRT 处理增强**: 支持浏览器拖拽上传 SRT 文件，处理完成后直接下载，带历史记录管理
- **双层配置管理**: 可切换编辑「项目配置」（`./semsub.yaml`）和「用户配置」（`~/.config/semsub/config.yaml`），每项参数显示来源标记

**快速开始流程：**
1. 进入「快速开始」页面
2. 输入视频路径：`/path/to/movie.mp4`
3. 选择场景预设（可选）：`movie`（电影）、`documentary`（纪录片）、`animation`（动画）
4. 点击「生成字幕」

### 命令行使用

#### 生成字幕

**单视频处理：**
```bash
# 基础用法
python -m semsub.cli generate video.mp4

# 指定输出文件
python -m semsub.cli generate video.mp4 -o output.srt

# 使用电影预设 + LLM 纠错
python -m semsub.cli generate video.mp4 --preset movie --llm --llm-mode correct

# 翻译成英文
python -m semsub.cli generate video.mp4 --llm --llm-mode translate -l Chinese
```

**批量处理：**
```bash
# 处理整个目录
python -m semsub.cli generate ./movies/ --output-dir ./subtitles/

# 跳过已有字幕的视频
python -m semsub.cli generate ./season1/ --output-dir ./subs/ --skip-existing

# 出错继续（不中断批量任务）
python -m semsub.cli generate ./videos/ --continue-on-error

# 混合输入（文件+目录）
python -m semsub.cli generate video1.mp4 ./episodes/ video2.mkv --output-dir ./output/
```

**执行指定阶段：**
```bash
# 只执行 ASR 和字幕优化（跳过音频提取/VAD）
python -m semsub.cli generate video.mp4 --from 03_asr_transcribe --to 04_subtitle_optimize
```

#### 查看状态

```bash
# 查看处理状态
python -m semsub.cli status video.mp4

# 示例输出：
# 工作区: /path/to/.semsub
# 视频: video.mp4
# 状态: 运行中 (ASR 转录 15/42)
#
# 阶段状态:
#   ✓ 音频提取     已完成    00:05
#   ✓ VAD 分割     已完成    00:03
#   ▶ ASR 转录     运行中    02:05  35%
#   ⏸ 字幕优化     等待中
#   ⏸ LLM 后处理   等待中 (未启用)
```

#### 重试失败阶段

```bash
# 从指定阶段强制重新执行
python -m semsub.cli run-stage video.mp4 03_asr_transcribe --force

# 从检查点恢复（仅 ASR 阶段支持）
python -m semsub.cli run-stage video.mp4 03_asr_transcribe --resume
```

**阶段 ID：** `01_audio_extract`（音频提取）、`02_vad_split`（VAD 分割）、`03_asr_transcribe`（ASR 转录）、`04_subtitle_optimize`（字幕优化）、`05_llm_postprocess`（LLM 后处理）

#### 工作区管理

```bash
# 初始化工作区（不执行处理）
python -m semsub.cli init video.mp4

# 清理工作区释放磁盘空间
python -m semsub.cli clean video.mp4

# 批量清理目录下的所有工作区
for d in ./*/.semsub; do python -m semsub.cli clean "${d%/.semsub}"; done
```

#### 处理已有 SRT 文件

```bash
# 使用 LLM 纠正 ASR 错误
python -m semsub.cli process-srt input.srt -o output.srt --llm-mode correct

# 翻译字幕
python -m semsub.cli process-srt input.srt -o output.srt --llm-mode translate
```

#### Web GUI SRT 处理

在 Gradio Web 界面的「SRT 处理」页面，你可以：

1. **上传 SRT 文件**：点击选择或拖拽文件到上传区域
2. **选择处理模式**：纠错 / 翻译 / 双语字幕
3. **开始处理**：调用 LLM 处理字幕内容
4. **下载结果**：处理完成后点击下载，输出文件名为 `original.processed.srt`
5. **查看历史**：历史记录列表显示文件名、处理模式、状态和时间，支持删除记录

默认输出路径为 `temp/semsub_outputs/`，自动处理重名（`file.processed.srt`、`file.processed(1).srt` 等）。

## 场景预设

| 预设 | 适用场景 | 关键参数 |
|------|----------|----------|
| `movie` | 对白密集的电影 | max_chars=40, gap_threshold=0.3s |
| `documentary` | 旁白解说内容 | max_chars=35, gap_threshold=0.5s, min_silence=800ms |
| `animation` | 语速较快的动画 | max_chars=30, max_duration=4.0s, gap_threshold=0.2s |

```bash
python -m semsub.cli generate video.mp4 --preset documentary
```

## 配置说明

配置优先级（从高到低）：
1. 命令行参数
2. 项目配置（`./semsub.yaml`）
3. 用户配置（`~/.config/semsub/config.yaml`）
4. 内置预设

### Web GUI 双层配置管理

在 Gradio Web 界面的「设置」页面，支持 VSCode 风格的双层配置切换：

- **项目配置**（`./semsub.yaml`）：当前目录下的项目级配置，优先级最高。默认显示此配置（如果存在）。
- **用户配置**（`~/.config/semsub/config.yaml`）：全局用户级配置，对所有项目生效。

每个配置分类（ASR / VAD / 字幕 / LLM / 输出）中，每项参数会显示其来源标记：**项目**、**用户** 或 **默认**。编辑用户配置时，如果项目配置存在，页面会提示「项目配置将覆盖此处的设置」，帮助你理解实际生效的值。

### 必需配置

```yaml
# ~/.config/semsub/config.yaml
asr:
  model_path: "/mnt/g/models/Qwen3-ASR-1.7B"
  aligner_path: "/mnt/g/models/Qwen3-ForcedAligner-0.6B"
  device: "cuda:0"
  batch_size: 8

# LLM 配置（可选）
llm:
  enabled: true
  api_key: "your-api-key"
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"
```

### 常用选项

| 选项 | 说明 | 示例 |
|------|------|------|
| `-o, --output` | 指定输出文件 | `-o output.srt` |
| `--output-dir` | 批量输出目录 | `--output-dir ./subs/` |
| `--preset` | 场景预设 | `--preset movie` |
| `-l, --language` | 音频语言 | `-l Chinese` |
| `--llm` | 启用 LLM 后处理 | `--llm` |
| `--llm-mode` | LLM 模式：纠错/翻译/双语 | `--llm-mode translate` |
| `--skip-existing` | 跳过已有输出 | `--skip-existing` |
| `--continue-on-error` | 出错继续执行 | `--continue-on-error` |

## Python API

```python
from pathlib import Path
from semsub import PipelineConfig, SubtitlePipeline

# 基础用法
config = PipelineConfig()
pipeline = SubtitlePipeline(config)
output = pipeline.generate(Path("video.mp4"))

# 自定义配置
config = PipelineConfig()
config.asr.batch_size = 16
config.subtitle.max_chars = 35
config.llm.enabled = True
config.llm.api_key = "your-api-key"

# 批量处理
from semsub.core.batch_scanner import VideoScanner
from semsub.core.batch_pipeline import BatchPipeline

tasks = VideoScanner().scan([Path("./movies/")], recursive=True)
result = BatchPipeline(config).process(tasks)
```

## 常见问题

**Q: 如何修改模型路径？**
```bash
python -m semsub.cli config edit
# 添加：asr: { model_path: "/your/path" }
```

**Q: 处理中断后可以恢复吗？**
可以，重新执行相同命令即可。ASR 阶段会自动从检查点恢复。

**Q: 需要多少磁盘空间？**
工作区占用约原视频 30% 的空间用于提取音频。处理完后可用 `python -m semsub.cli clean video.mp4` 清理。

**Q: 支持哪些 LLM 服务商？**
任何 OpenAI 兼容接口：DeepSeek、Kimi、通义千问、OpenAI 等。

**Q: 能否只用 CPU？**
配置中设置 `asr.device: "cpu"`。注意：速度很慢，不推荐。

**Q: 在 Web GUI 的设置页面保存后，为什么值又变回去了？**
这是因为配置优先级导致的。例如你在用户配置中修改了 `asr.batch_size`，但项目配置（`./semsub.yaml`）中也存在相同的设置，由于项目配置优先级更高，实际生效的仍然是项目配置的值。页面会显示来源标记提示你该值来自项目配置。要修改这个值，请切换到「项目配置」标签页进行编辑，或者删除项目配置中的对应项。

## 许可证

MIT License
