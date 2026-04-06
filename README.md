# SemSub - 智能字幕生成器

一个兼具命令行(CLI)和图形界面(GUI)的字幕生成软件，支持：
- VAD 语音分割 (Silero VAD)
- ASR 语音识别 (Qwen3-ASR)
- 字幕优化合并
- LLM 后处理（翻译/纠错）

## 安装

```bash
# 使用 uv 安装（推荐）
uv pip install torch==2.7.1 torchvision==0.22.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu128

# 安装项目依赖
pip install -r requirements.txt

# 或使用 uv
uv pip install -r requirements.txt
```

## 使用方式

### 1. 命令行界面 (CLI)

```bash
# 生成字幕（基本用法）
python -m semsub.cli generate video.mp4

# 指定输出路径
python -m semsub.cli generate video.mp4 -o output.srt

# 使用预设配置（电影/纪录片/动画）
python -m semsub.cli generate video.mp4 --preset movie

# 启用 LLM 后处理（纠错）
python -m semsub.cli generate video.mp4 --llm --llm-prompt correct.zh

# 启用 LLM 翻译
python -m semsub.cli generate video.mp4 --llm --llm-mode translate

# 查看配置
python -m semsub.cli config show
```

### 2. 图形界面 (GUI)

```bash
# 启动 GUI
python -m semsub.gui.app

# 或使用快捷命令（安装后）
semsub-gui
```

GUI 功能：
- 拖拽选择视频文件
- 可视化配置（VAD/字幕/LLM）
- 实时进度显示
- 日志输出

### 3. Python API

```python
from semsub import PipelineConfig, SubtitlePipeline
from pathlib import Path

# 创建配置
config = PipelineConfig()
config.llm.enabled = True
config.llm.api_key = "your-api-key"
config.llm.base_url = "https://api.deepseek.com/v1"

# 创建管道并生成字幕
pipeline = SubtitlePipeline(config)
output = pipeline.generate(Path("video.mp4"))
print(f"字幕已保存: {output}")
```

## 项目结构

```
semsub/
├── core/              # 核心模块（纯业务逻辑）
│   ├── config.py      # 配置数据类
│   ├── models.py      # 数据模型
│   ├── merger.py      # 字幕合并优化
│   ├── pipeline.py    # 主管道
│   ├── progress.py    # 进度报告接口
│   ├── stages/        # 处理阶段
│   ├── llm/           # LLM 后处理
│   └── prompts/       # 提示词模板
├── cli/               # 命令行界面
├── gui/               # PyQt6 图形界面
└── presets/           # 场景预设配置
```

## LLM 后处理

支持国内 OpenAI 兼容接口：
- DeepSeek (api.deepseek.com)
- Kimi (api.moonshot.cn)
- 通义千问 (dashscope.aliyuncs.com)

三种输出模式：
1. **纠错** - 修正同音字、标点等错误
2. **翻译** - 翻译为目标语言
3. **双语** - 原文+译文同时显示

## 配置说明

配置文件存储位置：
- 用户配置：`~/.config/semsub/config.yaml`
- 项目配置：`./semsub.yaml`

配置优先级：
命令行参数 > 项目配置 > 用户配置 > 内置预设

## 测试

```bash
# 运行测试
python test_new_arch.py
```

## 依赖版本

关键依赖：
- PyTorch 2.7.1 + CUDA 12.8
- qwen-asr 0.0.6
- silero-vad 6.2.1
- PyQt6 6.11.0
- openai 1.109.1
