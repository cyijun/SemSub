# 字幕生成完整流程详解

## 一、整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         电影字幕生成流程                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ 视频文件  │───→│ 音频提取  │───→│ VAD分割  │───→│ ASR识别  │              │
│  │  .mp4    │    │ FFmpeg   │    │SileroVAD │    │Qwen3-ASR │              │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘              │
│                                                       │                      │
│                              ┌────────────────────────┘                      │
│                              ↓                                              │
│                       ┌──────────┐    ┌──────────┐    ┌──────────┐         │
│                       │词级对齐  │───→│字幕优化  │───→│输出字幕  │         │
│                       │ForcedAlign│   │ Merger   │    │ SRT/TXT  │         │
│                       └──────────┘    └──────────┘    └──────────┘         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 二、详细步骤说明

### 步骤 1: 音频提取 (Audio Extraction)

**工具**: FFmpeg  
**输入**: 视频文件 (mp4/mkv/avi等)  
**输出**: 16kHz 单声道 WAV

```bash
ffmpeg -i video.mp4 -vn -acodec pcm_s16le -ac 1 -ar 16000 audio.wav
```

**参数说明**:
- `-vn`: 去掉视频
- `-acodec pcm_s16le`: 16位 PCM 编码
- `-ac 1`: 单声道
- `-ar 16000`: 16kHz 采样率

---

### 步骤 2: VAD 语音分割 (Voice Activity Detection)

**工具**: Silero VAD  
**作用**: 从音频中检测出有语音的片段，去除静音

**关键参数**:
```python
threshold = 0.5                    # 检测阈值 (0-1)
min_speech_duration_ms = 250       # 最小语音长度 (忽略短于250ms的)
min_silence_duration_ms = 500      # 静音分割点 (500ms静音视为分段)
```

**输出示例**:
```json
[
  {"index": 0, "start": 21.154, "end": 30.494, "duration": 9.34},
  {"index": 1, "start": 30.978, "end": 33.278, "duration": 2.30},
  ...
]
```

**实际效果**:
- 原始音频: 23.65 分钟
- VAD 检测: 311 个语音片段
- 语音占比: 60.5%

---

### 步骤 3: ASR 语音识别 (Automatic Speech Recognition)

**工具**: Qwen3-ASR-1.7B  
**功能**: 将语音转换为文本

**特点**:
- 支持多语言自动检测 (日语/英语/中文等)
- 批量处理提高效率
- 输出整句文本

**批处理**:
```python
batch_size = 16  # 一次处理16个片段
```

**输出示例**:
```
[0000] こんにちは、お待たせしました。本日ストレッチを担当させていただく...
[0001] 今日はご指名ありがとうございます。
[0002] どうですか。
```

---

### 步骤 4: Forced Alignment 强制对齐

**工具**: Qwen3-ForcedAligner-0.6B  
**作用**: 将文本与音频时间戳精确对齐到**字/词级别**

**输出格式**:
```python
ForcedAlignItem(
    text='こ',
    start_time=0.0,
    end_time=0.24
)
```

**意义**: 
- 知道每个字在什么时候说
- 为字幕提供精确的时间轴

---

### 步骤 5: 字幕优化 (Subtitle Optimization)

**核心模块**: `SubtitleMerger`  
**输入**: VAD片段 + 词级时间戳  
**输出**: 优化后的字幕行

#### 5.1 VAD 片段合并

**问题**: VAD 分割可能过于细碎，一句话被切分到多个片段

**策略**: 合并间隔 < 300ms 的相邻片段
```python
gap_threshold = 0.3  # 300ms

# 合并前: [片段A] 0.2s 间隔 [片段B]
# 合并后: [片段A+片段B]
```

**效果**: 311 个片段 → 约 150-200 个合并片段

#### 5.2 智能断句

**目标**: 将长句子分成适合阅读的字幕行

**断句优先级**:
1. **句子结束标点** (。！？.!?) - 最优先
2. **短语标点** (，,；;、) - 其次
3. **字符数限制** (中文40字/英文80字) - 强制断句

**示例**:
```
原文: "这是一个很长的句子，需要分成多行显示。"

优化后:
  行1: "这是一个很长的句子，" (10字)
  行2: "需要分成多行显示。" (9字)
```

#### 5.3 时间轴优化

**调整策略**:
| 问题 | 解决方案 |
|------|----------|
| 显示时间太短 | 延长到最少 1.0 秒 |
| 显示时间太长 | 缩短到最多 6.0 秒 |
| 阅读速度太快 | 根据字数调整 (目标 6 字/秒) |
| 行之间重叠 | 添加 50ms 间隔 |

---

### 步骤 6: 输出字幕

**支持格式**:
- **SRT**: 标准字幕格式
- **VTT**: WebVTT 格式
- **TXT**: 纯文本 (带时间戳)
- **JSON**: 结构化数据

**SRT 格式示例**:
```srt
1
00:00:21,154 --> 00:00:25,500
こんにちは、お待たせしました。

2
00:00:25,550 --> 00:00:30,000
本日ストレッチを担当させていただきます。
```

---

## 三、代码调用关系

```
generate_subtitles.py (主流程)
    ├── extract_audio()          # FFmpeg 提取音频
    ├── vad_split()              # Silero VAD 分割
    ├── transcribe_segments()    # ASR + ForcedAlign 识别
    │       └── Qwen3ASRModel
    │           ├── ASR 识别文本
    │           └── ForcedAligner 对齐时间戳
    └── merger.process()         # 字幕优化
            ├── merge_vad_segments()   # 合并片段
            ├── group_by_sentence()    # 句子分组
            ├── optimize_lines()       # 优化行长度
            └── adjust_timing()        # 调整时间轴
```

---

## 四、两种使用方式

### 方式 A: 完整字幕生成

生成标准 SRT 字幕文件 (含优化):

```python
from generate_subtitles import MovieSubtitleGenerator, SubtitleConfig

config = SubtitleConfig(language=None)  # 自动语言检测
generator = MovieSubtitleGenerator(config)
generator.generate("movie.mp4", "output.srt")
```

**流程**: 视频 → 音频 → VAD → ASR → 对齐 → 优化 → SRT

### 方式 B: 仅转录文本

快速生成 TXT 文本 (无优化):

```python
from transcribe_segments import quick_transcribe

quick_transcribe(segments_dir="segments", output_txt="result.txt")
```

**流程**: 音频片段 → ASR → TXT

---

## 五、关键参数配置

### 不同场景推荐配置

#### 电影 (对话密集)
```python
max_chars = 40
max_duration = 6.0
gap_threshold = 0.3          # 积极合并短间隔
vad_min_silence_duration_ms = 300
```

#### 纪录片 (旁白为主)
```python
max_chars = 35               # 稍短，方便阅读
max_duration = 7.0           # 显示更久
gap_threshold = 0.5          # 不太合并
vad_min_silence_duration_ms = 800
```

#### 动画 (语速快)
```python
max_chars = 30
max_duration = 4.0
gap_threshold = 0.2          # 积极合并
target_reading_speed = 8.0   # 适应快语速
```

---

## 六、数据流转示例

以 10 秒音频为例:

```
原始音频 (10s)
    │
    ▼
┌─────────────────────────────────────┐
│ VAD 分割                            │
│ [0:2] 说话... [2:3]静音 [3:8]说话... │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 片段合并 (间隔<0.3s的合并)            │
│ [0:2] + [3:8] → [0:8] (合并后)       │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ ASR + ForcedAlign                   │
│ 文本: "今天天气真好我们去公园"         │
│ 时间: [0:2]今 [2:3]天 [3:5]天 [5:6]气 │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 字幕优化                            │
│ 行1: "今天天气真好，" [0:3.5]         │
│ 行2: "我们去公园。"   [3.5:6]         │
└─────────────────────────────────────┘
    │
    ▼
输出 SRT
```

---

## 七、项目文件清单

| 文件 | 作用 |
|------|------|
| `subtitle_merger.py` | 字幕优化核心模块 |
| `generate_subtitles.py` | 完整字幕生成流程 |
| `transcribe_segments.py` | 仅转录文本 (快速) |
| `subtitle_generator.ipynb` | 使用演示 notebook |
| `test_subtitle_merger.py` | 单元测试 |
| `transcription.txt` | 转录结果 (文本) |
| `transcription.json` | 转录结果 (JSON) |

---

## 八、技术栈

| 组件 | 技术 |
|------|------|
| 音频处理 | FFmpeg, torchaudio |
| VAD | Silero VAD |
| ASR | Qwen3-ASR-1.7B |
| 对齐 | Qwen3-ForcedAligner-0.6B |
| 深度学习 | PyTorch |
| 语言 | Python 3.12 |
