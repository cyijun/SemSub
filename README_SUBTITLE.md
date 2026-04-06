# 优化字幕生成方案

基于 Qwen3-ASR + ForcedAligner + Silero VAD 的电影字幕生成方案，提供智能的字幕拼接优化。

## 文件结构

```
/mnt/d/temp/SemSub/
├── subtitle_merger.py        # 字幕合并优化核心模块
├── generate_subtitles.py     # 完整字幕生成流程
├── subtitle_generator.ipynb  # 使用演示 notebook
├── test_subtitle_merger.py   # 单元测试
└── README_SUBTITLE.md        # 本文档
```

## 核心优化策略

### 1. VAD 片段合并

将间隔小于阈值的相邻片段合并，减少片段数量，提高 ASR 效率。

```python
# 300ms 以内的间隔会合并
GAP_THRESHOLD = 0.3  # 秒
```

### 2. 智能断句

- **基于标点符号**：优先在句子结束标点后断句（。！？.!?）
- **基于短语边界**：其次在短语标点后断句（，,；;、）
- **时间间隔检测**：词间间隔大于1秒时强制断句
- **字符数限制**：每行不超过最大字符数（中文40/英文80）

### 3. 时间轴优化

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| `min_duration` | 1.0s | 最小显示时长 |
| `max_duration` | 6.0s | 最大显示时长 |
| `target_reading_speed` | 6.0 字/秒 | 目标阅读速度 |

## 快速开始

### 方式 1: 一行代码生成字幕

```python
from generate_subtitles import quick_generate

srt_path = quick_generate(
    video_path='/path/to/movie.mp4',
    language='Chinese',  # 或 'English' 或 None(自动检测)
)
```

### 方式 2: 使用配置对象

```python
from generate_subtitles import MovieSubtitleGenerator, SubtitleConfig

config = SubtitleConfig(
    asr_model_path='/mnt/g/models/Qwen3-ASR-1.7B',
    aligner_path='/mnt/g/models/Qwen3-ForcedAligner-0.6B',
    language='Chinese',
    max_chars=40,
    max_duration=6.0,
)

generator = MovieSubtitleGenerator(config)
srt_path = generator.generate('/path/to/movie.mp4', 'output.srt')
```

### 方式 3: 命令行

```bash
python generate_subtitles.py /path/to/movie.mp4 -o output.srt -l Chinese
```

## 参数调优

### 电影场景（对话密集）

```python
config = SubtitleConfig(
    language='Chinese',
    max_chars=40,
    gap_threshold=0.3,               # 合并短间隔
    vad_min_silence_duration_ms=300,  # 较短分段间隔
)
```

### 纪录片场景（旁白为主）

```python
config = SubtitleConfig(
    language='Chinese',
    max_chars=35,                    # 稍短，方便阅读
    max_duration=7.0,                # 显示更久
    gap_threshold=0.5,               # 不太合并
    vad_min_silence_duration_ms=800, # 较长停顿才分段
)
```

### 动画场景（语速快）

```python
config = SubtitleConfig(
    max_chars=30,                    # 较短
    max_duration=4.0,                # 显示时间短
    gap_threshold=0.2,               # 积极合并
    target_reading_speed=8.0,        # 适应快语速
)
```

## 处理流程

```
视频文件
    ↓
[1. 音频提取] ──→ FFmpeg ──→ WAV (16kHz)
    ↓
[2. VAD 分割] ──→ Silero VAD ──→ 语音片段列表
    ↓
[3. 片段合并] ──→ 合并间隔 < 300ms 的相邻片段
    ↓
[4. ASR+对齐] ──→ Qwen3-ASR + ForcedAligner ──→ 词级时间戳
    ↓
[5. 句子分组] ──→ 按标点和间隔分组
    ↓
[6. 行优化] ──→ 控制长度和时长
    ↓
[7. 时间调整] ──→ 平滑时间轴、消除重叠
    ↓
[8. 输出 SRT] ──→ 最终字幕文件
```

## API 文档

### SubtitleMerger

```python
from subtitle_merger import SubtitleMerger

merger = SubtitleMerger(
    max_chars=40,              # 每行最大字符数
    max_chars_en=80,           # 英文每行最大字符
    min_chars=4,               # 每行最小字符数
    max_duration=6.0,          # 每行最大显示时长
    min_duration=1.0,          # 每行最小显示时长
    gap_threshold=0.3,         # VAD 片段合并阈值
    target_reading_speed=6.0,  # 目标阅读速度
)

# 完整处理流程
subtitle_lines = merger.process(vad_segments, word_alignments)
```

### MovieSubtitleGenerator

```python
from generate_subtitles import MovieSubtitleGenerator

generator = MovieSubtitleGenerator(config)

# 生成字幕
srt_path = generator.generate(
    video_path='/path/to/video.mp4',
    output_srt='/path/to/output.srt',
    save_intermediate=True,  # 保存 VAD 和词对齐结果
)
```

## 测试

```bash
python test_subtitle_merger.py
```

测试内容包括：
- VAD 片段合并
- 句子分组
- 字幕行优化
- 时间轴调整
- 中文断句
- SRT 文件保存
- 真实数据测试

## 示例输出

生成的 SRT 格式：

```srt
1
00:00:21,154 --> 00:00:25,500
今天天气真好，

2
00:00:25,550 --> 00:00:30,000
我们去公园玩吧！

3
00:00:30,200 --> 00:00:35,000
这是一个很长的句子，
需要分成多行显示。
```

## 优化效果对比

| 指标 | 基础方案 | 优化方案 |
|------|----------|----------|
| 片段处理 | 311 段独立处理 | 智能合并后约 150-200 段 |
| 断句方式 | 固定字符数 | 智能标点断句 |
| 时间精度 | 直接使用 ASR | 平滑 + 边界对齐 |
| 阅读体验 | 可能过快/过慢 | 速度自适应调整 |
| 片段间隙 | 可能断句不当 | 智能合并短间隙 |

## 依赖

```bash
# 基础依赖
pip install torch torchaudio
pip install qwen_asr

# VAD
pip install silero-vad

# 可选：FFmpeg（系统安装）
```

## 注意事项

1. **模型路径**：修改 `SubtitleConfig` 中的 `asr_model_path` 和 `aligner_path` 为你的实际路径
2. **GPU 内存**：首次加载模型需要较多显存，请确保有足够的 GPU 内存
3. **处理时间**：长视频处理可能需要较长时间，建议先测试短视频
