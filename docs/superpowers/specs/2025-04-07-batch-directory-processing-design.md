# SemSub 批量目录处理设计文档

## 背景与目标

### 当前问题
- CLI 和 GUI 都只支持单个视频文件处理
- 用户需要逐个选择文件，操作繁琐
- 没有批量处理能力，不适合剧集、系列视频处理

### 设计目标
1. **目录作为输入**：支持递归扫描目录下的所有视频文件
2. **批量处理**：串行处理多个视频，统一管理进度
3. **灵活输出**：支持原目录输出或集中输出到指定目录
4. **错误处理**：遇到错误立即停止（默认），方便排查问题

---

## 核心设计决策

| 决策项 | 选择 | 说明 |
|--------|------|------|
| 扫描策略 | 递归扫描 | 扫描所有子目录中的视频文件 |
| 并行处理 | 串行处理 | 一个接一个处理，资源占用稳定 |
| 错误处理 | 立即停止 | 遇到错误立即停止，方便排查 |
| 输出位置 | 两者支持 | 默认原目录，可选 `--output-dir` |

---

## 数据结构设计

### VideoTask - 单个视频任务
```python
class VideoTask(BaseModel):
    """批量任务中的单个视频任务"""
    video_path: str
    output_path: str  # 目标字幕路径
    status: StageStatus = StageStatus.PENDING
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    workspace_path: Optional[str] = None
```

### BatchProgressInfo - 批量任务进度
```python
class BatchProgressInfo(BaseModel):
    """批量任务进度"""
    current_index: int = 0
    total_count: int = 0
    current_video: Optional[str] = None
    current_video_status: Optional[PipelineStatus] = None
    completed_count: int = 0
    failed_count: int = 0
    
    @property
    def percent(self) -> float:
        # 整体进度 = 已完成视频数/总数 + 当前视频进度/总数
        ...
```

### BatchTask - 批量任务（持久化支持）
```python
class BatchTask(BaseModel):
    """批量任务（可持久化，支持断点续传）"""
    task_id: str  # 唯一标识
    created_at: datetime
    updated_at: datetime
    
    input_paths: List[str]  # 原始输入
    output_dir: Optional[str] = None
    videos: List[VideoTask] = Field(default_factory=list)
    
    status: StageStatus = StageStatus.PENDING
    current_index: int = 0
    
    config_hash: str  # 配置快照
    config_snapshot: Dict[str, Any]
```

---

## CLI 接口设计

### 修改 generate 命令
```python
@click.command()
@click.argument("inputs", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("--output-dir", "-o", type=click.Path(), help="指定输出目录")
@click.option("--skip-existing", is_flag=True, help="跳过已存在字幕的视频")
@click.option("--continue-on-error", is_flag=True, help="遇到错误继续处理")
def generate(inputs, output_dir, skip_existing, continue_on_error, ...):
    """
    生成字幕
    
    INPUTS 可以是视频文件或目录（支持混合，递归扫描）
    
    示例：
        semsub generate video.mp4
        semsub generate ./movies/
        semsub generate ./movies/ ./series/ --output-dir ./subtitles/
        semsub generate video1.mp4 ./season1/ video2.mkv
    """
```

### 批量执行报告
成功示例：
```
批量处理完成: 5/5 成功
总耗时: 15:32

视频列表:
  ✓ movie1.mp4  [03:15]  → movie1.srt
  ✓ movie2.mp4  [02:48]  → movie2.srt
  ✓ series/ep1.mkv [04:02] → series/ep1.srt
  ✓ series/ep2.mkv [03:50] → series/ep2.srt
  ✓ series/ep3.mkv [01:37] → series/ep3.srt
```

失败示例：
```
批量处理中断: 2/5 成功, 1/5 失败
已处理: movie1.mp4, movie2.mp4
失败: series/ep1.mkv
错误: CUDA out of memory
```

---

## GUI 界面设计

### 主要改动

1. **文件选择区域**
   - 改为 QListWidget 显示已扫描的视频列表
   - "选择文件" + "选择目录" 两个按钮
   - 添加 "清空" 按钮

2. **批量进度显示**
   - 两个进度条：
     - 整体进度（视频级别）
     - 当前视频进度（阶段级别）
   - 统计信息：已完成数、待处理数、预计剩余时间

3. **Worker 修改**
   - 改为 `BatchPipelineWorker`
   - 内部循环处理视频队列
   - 新增信号：`video_started`, `video_finished`, `batch_progress`

### 界面布局
```
┌─────────────────────────────────────────────────────────────┐
│  SemSub - 智能字幕生成器                           [设置] │
├─────────────────────────────────────────────────────────────┤
│  [视频文件] 已扫描到 5 个视频                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 📹 movie1.mp4                                        │   │
│  │ 📹 movie2.mp4                                        │   │
│  │ 📁 series/ep1.mkv                                    │   │
│  │ 📁 series/ep2.mkv                                    │   │
│  │ ▶ series/ep3.mkv  ⏳ 处理中...                       │   │
│  └─────────────────────────────────────────────────────┘   │
│  [添加文件] [添加目录] [清空]                               │
│                                                             │
│  [处理进度]                                                 │
│  整体进度: [████████░░] 80% (4/5 视频)                      │
│  当前视频: [████░░░░░░] 40% - ep3.mkv (ASR转录)             │
│                                                             │
│  统计: ✓ 已完成: 4  ⏳ 待处理: 1  预计剩余: 12分钟          │
└─────────────────────────────────────────────────────────────┘
```

---

## 核心组件设计

### VideoScanner - 视频扫描器
```python
class VideoScanner:
    """扫描目录收集视频文件"""
    
    VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.m4v'}
    
    def scan(self, paths: List[Path], recursive: bool = True) -> List[Path]:
        """扫描路径列表，返回视频文件列表（去重）"""
        
    def resolve_output_path(self, video_path: Path, output_dir: Optional[Path] = None) -> Path:
        """确定字幕输出路径"""
```

### BatchPipeline - 批量管道
```python
class BatchPipeline:
    """批量处理多个视频"""
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        
    def process(
        self,
        videos: List[VideoTask],
        reporter: Optional[BatchReporter] = None,
        continue_on_error: bool = False
    ) -> BatchResult:
        """串行处理视频列表"""
        for i, video in enumerate(videos):
            # 更新当前索引
            # 调用 SubtitlePipeline.generate()
            # 遇到错误时根据 continue_on_error 决定
```

### BatchReporter - 批量进度报告
```python
class BatchReporter(ProgressReporter):
    """聚合多个视频的进度报告"""
    
    def __init__(self):
        self.batch_info = BatchProgressInfo()
        
    def on_video_start(self, video_path: Path, index: int, total: int):
        """开始处理新视频"""
        
    def on_video_progress(self, status: PipelineStatus):
        """当前视频的进度更新"""
        
    def on_video_finish(self, video_path: Path, success: bool, output_path: Optional[Path] = None):
        """视频处理完成"""
```

---

## 实现步骤

### 1. 数据模型扩展
- 在 `state_models.py` 中添加 `VideoTask`, `BatchProgressInfo`, `BatchTask`

### 2. 核心组件实现
- 创建 `semsub/core/batch_scanner.py` - VideoScanner 实现
- 创建 `semsub/core/batch_pipeline.py` - BatchPipeline 实现

### 3. CLI 修改
- 修改 `semsub/cli/commands/generate.py` - 支持多输入和目录

### 4. GUI 修改
- 修改 `semsub/gui/main_window.py` - 批量界面
- 创建 `semsub/gui/workers/batch_worker.py` - 批量工作线程

### 5. 测试
- 测试目录扫描、递归、过滤
- 测试批量处理、错误处理
- 测试 CLI 和 GUI

---

## 关键代码路径

| 组件 | 文件路径 |
|------|----------|
| 数据模型 | `semsub/core/state_models.py` |
| 视频扫描 | `semsub/core/batch_scanner.py` (新增) |
| 批量管道 | `semsub/core/batch_pipeline.py` (新增) |
| CLI 命令 | `semsub/cli/commands/generate.py` |
| GUI 主窗口 | `semsub/gui/main_window.py` |
| GUI Worker | `semsub/gui/workers/batch_worker.py` (新增) |

---

## 设计确认

此设计已确认：
- ✅ 递归扫描目录
- ✅ 串行处理视频
- ✅ 立即停止错误处理
- ✅ 灵活输出位置（原目录或指定目录）
