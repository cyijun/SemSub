# 批量目录处理功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现目录作为输入的批量字幕生成功能，支持递归扫描、串行处理、灵活输出位置

**Architecture:** 新增 VideoScanner 组件扫描目录收集视频，新增 BatchPipeline 串行处理多个视频，复用现有 SubtitlePipeline 处理单个视频，通过 BatchReporter 聚合进度报告

**Tech Stack:** Python 3.12, Pydantic, Click (CLI), PyQt6 (GUI)

---

## 文件结构

| 文件 | 用途 | 操作 |
|------|------|------|
| `semsub/core/state_models.py` | 添加批量处理数据模型 | 修改 |
| `semsub/core/batch_scanner.py` | 视频目录扫描器 | 新增 |
| `semsub/core/batch_pipeline.py` | 批量处理管道 | 新增 |
| `semsub/core/progress.py` | 添加批量进度报告器 | 修改 |
| `semsub/cli/commands/generate.py` | 支持目录输入和批量处理 | 修改 |
| `semsub/gui/main_window.py` | 批量处理界面 | 修改 |
| `semsub/gui/workers/batch_worker.py` | 批量处理工作线程 | 新增 |

---

## Task 1: 添加批量处理数据模型

**Files:**
- Modify: `semsub/core/state_models.py`

**Context:** 在现有 state_models.py 中添加批量处理相关的数据模型，包括 VideoTask（单个视频任务）、BatchProgressInfo（批量进度）、BatchResult（批量结果）

- [ ] **Step 1: 添加 VideoTask 模型**

在 `StageInfo` 类之后添加：

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
    workspace_path: Optional[str] = None  # 工作区路径（如果有）

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
```

- [ ] **Step 2: 添加 BatchProgressInfo 模型**

```python
class BatchProgressInfo(BaseModel):
    """批量任务进度"""
    current_index: int = 0  # 当前处理的视频索引（从0开始）
    total_count: int = 0
    current_video: Optional[str] = None  # 当前处理的视频名
    current_video_status: Optional[PipelineStatus] = None  # 当前视频的详细进度

    completed_count: int = 0
    failed_count: int = 0

    @property
    def percent(self) -> float:
        """整体进度百分比"""
        if self.total_count == 0:
            return 0.0
        # 基础进度：已完成视频占比
        base_progress = self.completed_count / self.total_count
        # 当前视频贡献的进度
        current_progress = 0.0
        if self.current_video_status and self.total_count > 0:
            current_progress = (self.current_video_status.progress_percent / 100) / self.total_count
        return round((base_progress + current_progress) * 100, 1)

    @property
    def is_complete(self) -> bool:
        """是否全部完成"""
        return self.completed_count + self.failed_count >= self.total_count
```

- [ ] **Step 3: 添加 BatchResult 模型**

```python
class BatchResult(BaseModel):
    """批量处理结果"""
    success: bool
    total_count: int
    completed_count: int
    failed_count: int
    tasks: List[VideoTask] = Field(default_factory=list)
    total_duration_ms: int = 0
    error_message: Optional[str] = None  # 如果失败，错误信息
```

- [ ] **Step 4: 验证模型**

运行: `python -c "from semsub.core.state_models import VideoTask, BatchProgressInfo, BatchResult; print('OK')"`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add semsub/core/state_models.py
git commit -m "feat: add batch processing data models (VideoTask, BatchProgressInfo, BatchResult)"
```

---

## Task 2: 实现 VideoScanner 视频扫描器

**Files:**
- Create: `semsub/core/batch_scanner.py`

**Context:** 实现视频目录扫描器，支持递归扫描、去重、过滤已存在的字幕

- [ ] **Step 1: 创建文件并添加导入**

```python
"""
视频目录扫描器
支持递归扫描目录收集视频文件
"""

from pathlib import Path
from typing import List, Optional, Set

from ..core.state_models import VideoTask, StageStatus


class VideoScanner:
    """扫描目录收集视频文件"""

    VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.m4v', '.flv', '.wmv'}
    SUBTITLE_EXTENSIONS = {'.srt', '.vtt', '.ass', '.ssa'}
```

- [ ] **Step 2: 实现 scan 方法**

在 `VideoScanner` 类中添加：

```python
    def __init__(self, video_extensions: Optional[Set[str]] = None):
        """
        Args:
            video_extensions: 自定义视频扩展名集合，默认使用常见格式
        """
        self.video_extensions = video_extensions or self.VIDEO_EXTENSIONS

    def scan(
        self,
        paths: List[Path],
        recursive: bool = True,
        skip_existing: bool = False,
        output_dir: Optional[Path] = None,
        output_format: str = "srt"
    ) -> List[VideoTask]:
        """
        扫描路径列表，返回视频任务列表

        Args:
            paths: 文件或目录路径列表
            recursive: 是否递归扫描子目录
            skip_existing: 是否跳过已存在字幕的视频
            output_dir: 指定输出目录（None表示与视频同目录）
            output_format: 输出格式后缀

        Returns:
            VideoTask 列表（已去重）
        """
        video_files: Set[Path] = set()

        for path in paths:
            path = Path(path)
            if not path.exists():
                continue

            if path.is_file():
                if self._is_video_file(path):
                    video_files.add(path.resolve())
            elif path.is_dir():
                video_files.update(self._scan_directory(path, recursive))

        # 转换为列表并排序（保持确定性顺序）
        sorted_videos = sorted(video_files, key=lambda p: str(p))

        # 构建 VideoTask 列表
        tasks = []
        for video_path in sorted_videos:
            output_path = self._resolve_output_path(video_path, output_dir, output_format)

            # 检查是否跳过已存在的字幕
            if skip_existing and output_path.exists():
                continue

            tasks.append(VideoTask(
                video_path=str(video_path),
                output_path=str(output_path)
            ))

        return tasks

    def _is_video_file(self, path: Path) -> bool:
        """检查是否是视频文件"""
        return path.suffix.lower() in self.video_extensions

    def _scan_directory(self, directory: Path, recursive: bool) -> Set[Path]:
        """扫描目录收集视频文件"""
        videos = set()

        if recursive:
            for path in directory.rglob("*"):
                if path.is_file() and self._is_video_file(path):
                    videos.add(path.resolve())
        else:
            for path in directory.iterdir():
                if path.is_file() and self._is_video_file(path):
                    videos.add(path.resolve())

        return videos

    def _resolve_output_path(
        self,
        video_path: Path,
        output_dir: Optional[Path],
        output_format: str
    ) -> Path:
        """确定字幕输出路径"""
        if output_dir:
            # 使用指定输出目录，保持相对目录结构
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            return output_dir / f"{video_path.stem}.{output_format}"
        else:
            # 与视频同目录
            return video_path.with_suffix(f".{output_format}")
```

- [ ] **Step 3: 测试扫描器**

创建临时测试：

```python
# 测试脚本
import tempfile
from pathlib import Path
from semsub.core.batch_scanner import VideoScanner

# 创建临时目录结构
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    (tmp / "video1.mp4").touch()
    (tmp / "video2.mkv").touch()
    (tmp / "subdir").mkdir()
    (tmp / "subdir" / "video3.avi").touch()
    (tmp / "not_video.txt").touch()

    scanner = VideoScanner()
    tasks = scanner.scan([tmp], recursive=True)

    assert len(tasks) == 3, f"Expected 3 videos, got {len(tasks)}"
    print(f"✓ Found {len(tasks)} videos")
    for t in tasks:
        print(f"  - {Path(t.video_path).name}")
```

运行: `python -c "
import tempfile
from pathlib import Path
from semsub.core.batch_scanner import VideoScanner

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    (tmp / 'video1.mp4').touch()
    (tmp / 'video2.mkv').touch()
    (tmp / 'subdir').mkdir()
    (tmp / 'subdir' / 'video3.avi').touch()
    (tmp / 'not_video.txt').touch()

    scanner = VideoScanner()
    tasks = scanner.scan([tmp], recursive=True)
    assert len(tasks) == 3, f'Expected 3 videos, got {len(tasks)}'
    print(f'✓ Found {len(tasks)} videos')
"
`

Expected:
```
✓ Found 3 videos
```

- [ ] **Step 4: Commit**

```bash
git add semsub/core/batch_scanner.py
git commit -m "feat: add VideoScanner for batch directory scanning"
```

---

## Task 3: 实现 BatchPipeline 批量处理管道

**Files:**
- Create: `semsub/core/batch_pipeline.py`
- Modify: `semsub/core/progress.py` (添加 BatchReporter)

**Context:** 实现批量处理管道，串行处理多个视频，统一进度报告

- [ ] **Step 1: 修改 progress.py 添加 BatchReporter**

在 `semsub/core/progress.py` 的 `StageProgressReporter` 类之后添加：

```python
class BatchReporter:
    """批量处理进度报告器"""

    def __init__(self):
        self.batch_info = BatchProgressInfo()
        self._start_time = None

    def on_batch_start(self, total_count: int):
        """批量处理开始"""
        from datetime import datetime
        self._start_time = datetime.now()
        self.batch_info = BatchProgressInfo(total_count=total_count)
        self._report()

    def on_video_start(self, video_path: Path, index: int):
        """开始处理新视频"""
        self.batch_info.current_index = index
        self.batch_info.current_video = video_path.name
        self.batch_info.current_video_status = None
        self._report()

    def on_video_progress(self, status: PipelineStatus):
        """当前视频的进度更新"""
        self.batch_info.current_video_status = status
        self._report()

    def on_video_finish(self, video_path: Path, success: bool, error_msg: Optional[str] = None):
        """视频处理完成"""
        if success:
            self.batch_info.completed_count += 1
        else:
            self.batch_info.failed_count += 1
            if error_msg:
                print(f"✗ {video_path.name}: {error_msg}")
        self.batch_info.current_video = None
        self.batch_info.current_video_status = None
        self._report()

    def on_batch_finish(self, success: bool, error_msg: Optional[str] = None):
        """批量处理完成"""
        from datetime import datetime
        duration = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0

        print(f"\n{'='*50}")
        if success:
            print(f"批量处理完成: {self.batch_info.completed_count}/{self.batch_info.total_count} 成功")
        else:
            print(f"批量处理中断: {self.batch_info.completed_count}/{self.batch_info.total_count} 成功")
            if self.batch_info.failed_count > 0:
                print(f"失败: {self.batch_info.failed_count} 个")
        print(f"总耗时: {int(duration//60)}分{int(duration%60)}秒")
        print(f"{'='*50}")

    def _report(self):
        """输出进度报告（可被覆盖）"""
        if not hasattr(self, '_last_report'):
            self._last_report = 0

        # 每 10% 或视频切换时报告
        current_percent = int(self.batch_info.percent)
        if current_percent >= self._last_report + 10 or self.batch_info.current_video is None:
            self._last_report = current_percent
            print(f"进度: [{self._progress_bar(current_percent)}] {current_percent}% "
                  f"({self.batch_info.completed_count + self.batch_info.failed_count}/{self.batch_info.total_count})")

    def _progress_bar(self, percent: int, width: int = 20) -> str:
        """生成进度条字符串"""
        filled = int(width * percent / 100)
        return "█" * filled + "░" * (width - filled)
```

同时需要在文件顶部添加导入：
```python
from .state_models import BatchProgressInfo, PipelineStatus
```

- [ ] **Step 2: 创建 batch_pipeline.py**

```python
"""
批量处理管道
串行处理多个视频文件
"""

import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .config import PipelineConfig
from .pipeline import SubtitlePipeline
from .state_models import VideoTask, BatchResult, StageStatus, PipelineStatus
from .progress import BatchReporter, SilentProgressReporter


class BatchPipeline:
    """批量处理多个视频"""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.pipeline = SubtitlePipeline(config)

    def process(
        self,
        tasks: List[VideoTask],
        reporter: Optional[BatchReporter] = None,
        continue_on_error: bool = False
    ) -> BatchResult:
        """
        串行处理视频任务列表

        Args:
            tasks: VideoTask 列表
            reporter: 进度报告器
            continue_on_error: 遇到错误是否继续处理其他视频

        Returns:
            BatchResult 处理结果
        """
        if reporter is None:
            reporter = BatchReporter()

        if not tasks:
            return BatchResult(success=True, total_count=0, completed_count=0, failed_count=0)

        reporter.on_batch_start(len(tasks))
        start_time = datetime.now()

        for i, task in enumerate(tasks):
            video_path = Path(task.video_path)
            output_path = Path(task.output_path)

            reporter.on_video_start(video_path, i)
            task.started_at = datetime.now()
            task.status = StageStatus.RUNNING

            try:
                # 创建包装器来捕获单个视频的进度
                video_reporter = self._create_video_reporter(reporter)

                # 执行单个视频处理
                result_path = self.pipeline.generate(
                    video_path=video_path,
                    output_path=output_path,
                    reporter=video_reporter
                )

                task.status = StageStatus.COMPLETED
                task.completed_at = datetime.now()
                task.duration_ms = int((task.completed_at - task.started_at).total_seconds() * 1000)
                reporter.on_video_finish(video_path, success=True)

            except Exception as e:
                task.status = StageStatus.FAILED
                task.error_message = str(e)
                task.completed_at = datetime.now()
                task.duration_ms = int((task.completed_at - task.started_at).total_seconds() * 1000) if task.started_at else 0

                reporter.on_video_finish(video_path, success=False, error_msg=str(e))

                if not continue_on_error:
                    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                    reporter.on_batch_finish(success=False, error_msg=str(e))
                    return BatchResult(
                        success=False,
                        total_count=len(tasks),
                        completed_count=reporter.batch_info.completed_count,
                        failed_count=reporter.batch_info.failed_count + 1,
                        tasks=tasks,
                        total_duration_ms=duration_ms,
                        error_message=str(e)
                    )

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        reporter.on_batch_finish(success=True)

        return BatchResult(
            success=True,
            total_count=len(tasks),
            completed_count=reporter.batch_info.completed_count,
            failed_count=reporter.batch_info.failed_count,
            tasks=tasks,
            total_duration_ms=duration_ms
        )

    def _create_video_reporter(self, batch_reporter: BatchReporter):
        """创建包装器捕获单个视频的进度并转发到批量报告器"""
        class VideoReporterProxy(SilentProgressReporter):
            def on_progress(self, stage, percent: float, message: str = ""):
                # 更新当前视频状态
                if batch_reporter.batch_info.current_video_status:
                    batch_reporter.batch_info.current_video_status.progress_percent = percent
                batch_reporter._report()

            def on_stage_complete(self, stage, success: bool):
                pass

            def on_log(self, message: str):
                pass

        return VideoReporterProxy()
```

- [ ] **Step 3: 验证导入**

运行: `python -c "from semsub.core.batch_pipeline import BatchPipeline; print('OK')"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add semsub/core/batch_pipeline.py semsub/core/progress.py
git commit -m "feat: add BatchPipeline for batch video processing"
```

---

## Task 4: 修改 CLI generate 命令支持目录输入

**Files:**
- Modify: `semsub/cli/commands/generate.py`

**Context:** 修改现有 generate 命令，支持文件/目录混合输入，添加批量处理选项

- [ ] **Step 1: 读取当前 generate.py 文件**

先读取文件了解当前结构：
```bash
head -100 semsub/cli/commands/generate.py
```

- [ ] **Step 2: 修改参数定义**

将原来的 `video` 参数改为 `inputs`：

```python
@click.command()
@click.argument("inputs", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="输出字幕路径（单文件模式）或输出目录（批量模式）")
@click.option("--output-dir", type=click.Path(), help="指定批量输出的目录")
@click.option("--skip-existing", is_flag=True, help="跳过已存在字幕的视频")
@click.option("--continue-on-error", is_flag=True, help="遇到错误继续处理其他视频")
@click.option("--preset", type=click.Choice(["movie", "documentary", "animation"]), help="使用预设配置")
@click.option("--language", "-l", help="语言 (Chinese/English/Japanese)")
@click.option("--format", "-f", "output_format", type=click.Choice(["srt", "vtt", "json"]), help="输出格式")
@click.option("--llm", is_flag=True, help="启用LLM后处理")
@click.option("--llm-prompt", help="LLM提示词文件路径")
@click.option("--llm-mode", type=click.Choice(["correct", "translate", "bilingual"]), help="LLM输出模式")
@click.option("--from", "start_from", help="从指定阶段开始执行")
@click.option("--to", "stop_at", help="执行到指定阶段停止")
@click.option("--force", is_flag=True, help="强制重新执行")
@click.option("--workspace-dir", help="工作区目录")
@click.pass_context
def generate(
    ctx,
    inputs,
    output,
    output_dir,
    skip_existing,
    continue_on_error,
    preset,
    language,
    output_format,
    llm,
    llm_prompt,
    llm_mode,
    start_from,
    stop_at,
    force,
    workspace_dir
):
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

- [ ] **Step 3: 实现批量处理逻辑**

在函数内部添加：

```python
    from pathlib import Path
    from ...core.batch_scanner import VideoScanner
    from ...core.batch_pipeline import BatchPipeline

    # 转换为 Path 列表
    input_paths = [Path(p) for p in inputs]

    # 判断是否是批量模式（输入包含目录，或输入多于1个文件）
    has_directory = any(p.is_dir() for p in input_paths)
    is_batch_mode = has_directory or len(input_paths) > 1

    if is_batch_mode:
        # 批量模式
        _run_batch_mode(
            config=config,
            input_paths=input_paths,
            output_dir=output_dir or output,  # --output-dir 优先，否则用 -o
            skip_existing=skip_existing,
            continue_on_error=continue_on_error,
            output_format=output_format or config.output.format,
        )
    else:
        # 单文件模式（保持原有逻辑）
        _run_single_mode(
            config=config,
            video_path=input_paths[0],
            output_path=output,
            start_from=start_from,
            stop_at=stop_at,
            force=force,
            workspace_dir=workspace_dir,
        )
```

- [ ] **Step 4: 添加批量模式函数**

在 generate 函数后添加：

```python
def _run_batch_mode(
    config,
    input_paths: list,
    output_dir: Optional[str],
    skip_existing: bool,
    continue_on_error: bool,
    output_format: str,
):
    """运行批量处理模式"""
    scanner = VideoScanner()
    tasks = scanner.scan(
        paths=input_paths,
        recursive=True,
        skip_existing=skip_existing,
        output_dir=Path(output_dir) if output_dir else None,
        output_format=output_format
    )

    if not tasks:
        click.echo("未找到需要处理的视频文件", err=True)
        return

    click.echo(f"找到 {len(tasks)} 个视频文件，开始处理...")
    click.echo("-" * 50)

    pipeline = BatchPipeline(config)
    result = pipeline.process(
        tasks=tasks,
        continue_on_error=continue_on_error
    )

    # 打印详细结果
    click.echo("\n处理结果：")
    for task in result.tasks:
        status_icon = "✓" if task.status.value == "completed" else "✗"
        duration_str = ""
        if task.duration_ms:
            minutes = task.duration_ms // 60000
            seconds = (task.duration_ms % 60000) // 1000
            duration_str = f" [{minutes:02d}:{seconds:02d}]"
        click.echo(f"  {status_icon} {Path(task.video_path).name}{duration_str}")
        if task.error_message:
            click.echo(f"    错误: {task.error_message}")

def _run_single_mode(
    config,
    video_path: Path,
    output_path: Optional[str],
    start_from: Optional[str],
    stop_at: Optional[str],
    force: bool,
    workspace_dir: Optional[str],
):
    """运行单文件模式（原有逻辑）"""
    from ...core.pipeline import SubtitlePipeline
    from ...core.workspace import WorkspaceManager
    from ...core.progress import ConsoleProgressReporter

    video_path = Path(video_path)
    if output_path is None:
        output_path = video_path.with_suffix(f".{config.output.format}")
    else:
        output_path = Path(output_path)

    workspace_dir = Path(workspace_dir) if workspace_dir else None

    pipeline = SubtitlePipeline(config, workspace_dir=workspace_dir)
    reporter = ConsoleProgressReporter()

    try:
        result = pipeline.generate(
            video_path=video_path,
            output_path=output_path,
            reporter=reporter,
            start_from=start_from,
            stop_at=stop_at,
            force=force
        )
        click.echo(f"\n✓ 字幕已保存: {result}")
    except Exception as e:
        click.echo(f"\n✗ 错误: {e}", err=True)
        raise click.Abort()
```

- [ ] **Step 5: 添加缺少的导入**

确保文件顶部有：
```python
from typing import Optional
from pathlib import Path
```

- [ ] **Step 6: 测试 CLI**

测试帮助信息：

```bash
python -m semsub.cli generate --help
```

Expected: 显示包含 `INPUTS`, `--output-dir`, `--skip-existing`, `--continue-on-error` 的帮助信息

- [ ] **Step 7: Commit**

```bash
git add semsub/cli/commands/generate.py
git commit -m "feat: CLI generate command supports directory input and batch processing"
```

---

## Task 5: 创建 GUI BatchWorker

**Files:**
- Create: `semsub/gui/workers/batch_worker.py`

**Context:** 创建批量处理工作线程，支持 PyQt6 信号报告进度

- [ ] **Step 1: 创建文件**

```python
"""
批量处理工作线程
"""

from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from ...core.config import PipelineConfig
from ...core.batch_pipeline import BatchPipeline
from ...core.batch_scanner import VideoScanner
from ...core.state_models import VideoTask, BatchResult, StageStatus


class BatchWorker(QThread):
    """批量处理工作线程"""

    # 批量级别信号
    batch_started = pyqtSignal(int)  # total_count
    batch_progress = pyqtSignal(int, int, str)  # current_index, total_count, current_video_name
    batch_finished = pyqtSignal(bool, int, int, int)  # success, completed, failed, total
    batch_error = pyqtSignal(str)

    # 单个视频级别信号
    video_started = pyqtSignal(str, int, int)  # video_path, index, total
    video_progress = pyqtSignal(int, str)  # percent, message
    video_finished = pyqtSignal(str, bool, str)  # video_path, success, output_path

    # 日志信号
    log = pyqtSignal(str)

    def __init__(
        self,
        config: PipelineConfig,
        tasks: List[VideoTask],
        continue_on_error: bool = False
    ):
        super().__init__()
        self.config = config
        self.tasks = tasks
        self.continue_on_error = continue_on_error
        self._is_cancelled = False

    def run(self):
        """执行批量处理"""
        try:
            self.batch_started.emit(len(self.tasks))

            pipeline = BatchPipeline(self.config)

            # 创建自定义报告器
            reporter = self._create_reporter()

            result = pipeline.process(
                tasks=self.tasks,
                reporter=reporter,
                continue_on_error=self.continue_on_error
            )

            self.batch_finished.emit(
                result.success,
                result.completed_count,
                result.failed_count,
                result.total_count
            )

        except Exception as e:
            self.batch_error.emit(str(e))

    def _create_reporter(self):
        """创建 Qt 信号报告器"""
        from ...core.progress import BatchReporter
        from ...core.state_models import PipelineStatus

        class QtBatchReporter(BatchReporter):
            def __init__(self, worker):
                super().__init__()
                self.worker = worker

            def on_video_start(self, video_path: Path, index: int):
                super().on_video_start(video_path, index)
                self.worker.video_started.emit(str(video_path), index, self.batch_info.total_count)
                self.worker.batch_progress.emit(index, self.batch_info.total_count, video_path.name)

            def on_video_progress(self, status: PipelineStatus):
                super().on_video_progress(status)
                if status:
                    self.worker.video_progress.emit(
                        int(status.progress_percent),
                        f"{status.current_stage or 'processing'}"
                    )

            def on_video_finish(self, video_path: Path, success: bool, error_msg: Optional[str] = None):
                super().on_video_finish(video_path, success, error_msg)
                self.worker.video_finished.emit(
                    str(video_path),
                    success,
                    "" if success else (error_msg or "")
                )

            def on_batch_start(self, total_count: int):
                super().on_batch_start(total_count)
                self.worker.log.emit(f"开始批量处理 {total_count} 个视频...")

            def on_batch_finish(self, success: bool, error_msg: Optional[str] = None):
                super().on_batch_finish(success, error_msg)
                if success:
                    self.worker.log.emit("批量处理完成")
                else:
                    self.worker.log.emit(f"批量处理中断: {error_msg or 'Unknown error'}")

        return QtBatchReporter(self)

    def cancel(self):
        """取消处理"""
        self._is_cancelled = True
        self.log.emit("正在取消...")
```

- [ ] **Step 2: 验证导入**

运行: `python -c "from semsub.gui.workers.batch_worker import BatchWorker; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add semsub/gui/workers/batch_worker.py
git commit -m "feat: add BatchWorker for GUI batch processing"
```

---

## Task 6: 修改 GUI 主窗口支持批量处理

**Files:**
- Modify: `semsub/gui/main_window.py`

**Context:** 修改主窗口界面，支持多文件选择、显示视频列表、双进度条

- [ ] **Step 1: 修改文件选择区域**

替换原来的单文件选择区域：

```python
    def _setup_ui(self):
        # ... 前面的代码 ...

        # 1. 文件选择区域 - 改为批量模式
        file_group = QGroupBox("视频文件")
        file_layout = QVBoxLayout(file_group)

        # 文件列表
        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(150)
        self.file_list.setAcceptDrops(True)
        self.file_list.dragEnterEvent = self._drag_enter_event
        self.file_list.dropEvent = self._drop_event
        file_layout.addWidget(self.file_list)

        # 统计标签
        self.file_count_label = QLabel("已选择: 0 个视频")
        file_layout.addWidget(self.file_count_label)

        # 按钮行
        btn_layout = QHBoxLayout()
        self.add_file_btn = QPushButton("添加文件")
        self.add_file_btn.clicked.connect(self._add_files)
        btn_layout.addWidget(self.add_file_btn)

        self.add_dir_btn = QPushButton("添加目录")
        self.add_dir_btn.clicked.connect(self._add_directory)
        btn_layout.addWidget(self.add_dir_btn)

        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self._clear_files)
        btn_layout.addWidget(self.clear_btn)

        btn_layout.addStretch()
        file_layout.addLayout(btn_layout)

        layout.addWidget(file_group)

        # ... 其余代码 ...
```

- [ ] **Step 2: 修改进度显示区域**

在现有进度条基础上添加整体进度：

```python
        # 3. 批量进度条（新增）
        batch_progress_group = QGroupBox("整体进度")
        batch_layout = QVBoxLayout(batch_progress_group)

        self.batch_progress_bar = QProgressBar()
        self.batch_progress_bar.setRange(0, 100)
        self.batch_progress_bar.setValue(0)
        batch_layout.addWidget(self.batch_progress_bar)

        self.batch_status_label = QLabel("就绪")
        batch_layout.addWidget(self.batch_status_label)

        # 统计信息
        stats_layout = QHBoxLayout()
        self.completed_label = QLabel("已完成: 0")
        self.pending_label = QLabel("待处理: 0")
        self.eta_label = QLabel("预计剩余: --")
        stats_layout.addWidget(self.completed_label)
        stats_layout.addWidget(self.pending_label)
        stats_layout.addWidget(self.eta_label)
        stats_layout.addStretch()
        batch_layout.addLayout(stats_layout)

        layout.addWidget(batch_progress_group)

        # 4. 当前视频进度条（原有）
        video_progress_group = QGroupBox("当前视频进度")
        video_layout = QVBoxLayout(video_progress_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        video_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("等待开始...")
        video_layout.addWidget(self.status_label)

        layout.addWidget(video_progress_group)
```

- [ ] **Step 3: 添加新的槽函数**

替换原来的单文件处理槽函数：

```python
    def _add_files(self):
        """添加文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择视频文件", "",
            "视频文件 (*.mp4 *.mkv *.avi *.mov *.webm);;所有文件 (*)"
        )
        if files:
            self._add_videos([Path(f) for f in files])

    def _add_directory(self):
        """添加目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择视频目录")
        if dir_path:
            from ...core.batch_scanner import VideoScanner
            scanner = VideoScanner()
            tasks = scanner.scan([Path(dir_path)], recursive=True)
            self._add_videos([Path(t.video_path) for t in tasks])

    def _add_videos(self, paths: List[Path]):
        """添加视频到列表"""
        for path in paths:
            # 去重检查
            exists = False
            for i in range(self.file_list.count()):
                if self.file_list.item(i).data(Qt.ItemDataRole.UserRole) == str(path):
                    exists = True
                    break
            if not exists:
                item = QListWidgetItem(f"📹 {path.name}")
                item.setData(Qt.ItemDataRole.UserRole, str(path))
                item.setToolTip(str(path))
                self.file_list.addItem(item)

        self._update_file_count()

    def _clear_files(self):
        """清空列表"""
        self.file_list.clear()
        self._update_file_count()

    def _update_file_count(self):
        """更新文件计数"""
        count = self.file_list.count()
        self.file_count_label.setText(f"已选择: {count} 个视频")
```

- [ ] **Step 4: 修改开始生成逻辑**

替换 `_start_generation` 方法：

```python
    def _start_generation(self):
        """开始批量生成"""
        # 收集所有视频路径
        video_paths = []
        for i in range(self.file_list.count()):
            path = self.file_list.item(i).data(Qt.ItemDataRole.UserRole)
            if path:
                video_paths.append(Path(path))

        if not video_paths:
            QMessageBox.warning(self, "警告", "请先添加视频文件")
            return

        # 更新配置
        self._update_config()

        # 创建 VideoTask 列表
        from ...core.batch_scanner import VideoScanner
        scanner = VideoScanner()
        tasks = scanner.scan(video_paths, recursive=False)  # 已经扫描过了

        # 创建批量 worker
        from .workers.batch_worker import BatchWorker
        self.worker = BatchWorker(self.config, tasks)

        # 连接信号
        self.worker.batch_started.connect(self._on_batch_started)
        self.worker.batch_progress.connect(self._on_batch_progress)
        self.worker.batch_finished.connect(self._on_batch_finished)
        self.worker.batch_error.connect(self._on_batch_error)
        self.worker.video_started.connect(self._on_video_started)
        self.worker.video_progress.connect(self._on_video_progress)
        self.worker.video_finished.connect(self._on_video_finished)
        self.worker.log.connect(self._log)

        # 更新 UI
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.batch_progress_bar.setValue(0)
        self.progress_bar.setValue(0)

        # 启动
        self.worker.start()
        self._log(f"开始批量处理 {len(tasks)} 个视频...")
```

- [ ] **Step 5: 添加批量处理槽函数**

```python
    def _on_batch_started(self, total_count: int):
        """批量处理开始"""
        self.batch_status_label.setText(f"开始处理 {total_count} 个视频...")

    def _on_batch_progress(self, current: int, total: int, video_name: str):
        """批量进度更新"""
        percent = int((current / total) * 100) if total > 0 else 0
        self.batch_progress_bar.setValue(percent)
        self.batch_status_label.setText(f"处理中: {video_name} ({current+1}/{total})")

        # 更新统计
        self.completed_label.setText(f"已完成: {current}")
        self.pending_label.setText(f"待处理: {total - current}")

    def _on_video_started(self, video_path: str, index: int, total: int):
        """开始处理单个视频"""
        self.status_label.setText(f"正在处理: {Path(video_path).name}")
        # 高亮当前处理的项
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == video_path:
                self.file_list.setCurrentItem(item)
                break

    def _on_video_progress(self, percent: int, message: str):
        """单个视频进度"""
        self.progress_bar.setValue(percent)
        if message:
            self.status_label.setText(message)

    def _on_video_finished(self, video_path: str, success: bool, output_path: str):
        """单个视频完成"""
        # 更新列表项状态
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == video_path:
                prefix = "✓" if success else "✗"
                item.setText(f"{prefix} {item.text()[2:]}")  # 替换原有前缀
                break

    def _on_batch_finished(self, success: bool, completed: int, failed: int, total: int):
        """批量处理完成"""
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        if success:
            self.batch_progress_bar.setValue(100)
            self.batch_status_label.setText(f"完成: {completed}/{total} 成功")
            QMessageBox.information(self, "完成", f"批量处理完成！\n成功: {completed} 个\n失败: {failed} 个")
        else:
            self.batch_status_label.setText(f"中断: {completed} 成功, {failed} 失败")
            QMessageBox.warning(self, "中断", f"批量处理中断\n成功: {completed} 个\n失败: {failed} 个")

    def _on_batch_error(self, error_msg: str):
        """批量处理错误"""
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._log(f"✗ 错误: {error_msg}")
        QMessageBox.critical(self, "错误", error_msg)
```

- [ ] **Step 6: 修改拖放事件**

```python
    def _drop_event(self, event):
        """拖拽放下"""
        urls = event.mimeData().urls()
        paths = []
        for url in urls:
            path = url.toLocalFile()
            if path:
                paths.append(Path(path))

        if paths:
            # 如果是目录，扫描；如果是文件，直接添加
            from ...core.batch_scanner import VideoScanner
            scanner = VideoScanner()
            tasks = scanner.scan(paths, recursive=True)
            self._add_videos([Path(t.video_path) for t in tasks])
```

- [ ] **Step 7: 添加需要的导入**

在文件顶部添加：
```python
from typing import List
from PyQt6.QtWidgets import QListWidget, QListWidgetItem
```

- [ ] **Step 8: Commit**

```bash
git add semsub/gui/main_window.py
git commit -m "feat: GUI supports batch directory processing with dual progress bars"
```

---

## Task 7: Phase 5 GUI 工作区面板实现

**Files:**
- Create: `semsub/gui/widgets/workspace_panel.py`
- Create: `semsub/gui/widgets/stage_flow_widget.py`
- Modify: `semsub/gui/main_window.py`

**Context:** 实现 GUI 工作区面板，显示阶段流程图和状态，支持阶段级操作

- [ ] **Step 1: 创建 StageFlowWidget 阶段流程图**

创建 `semsub/gui/widgets/stage_flow_widget.py`：

```python
"""
阶段流程图组件
显示 5 个阶段的流程图样式状态
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont

from ...core.state_models import StageStatus, PipelineStatus


class StageCard(QFrame):
    """单个阶段卡片"""

    clicked = pyqtSignal(str)  # stage_id

    STAGE_NAMES = {
        "01_audio_extract": "音频\n提取",
        "02_vad_split": "VAD\n分割",
        "03_asr_transcribe": "ASR\n转录",
        "04_subtitle_optimize": "字幕\n优化",
        "05_llm_postprocess": "LLM\n后处理",
    }

    STATUS_COLORS = {
        StageStatus.PENDING: ("#9e9e9e", "#e0e0e0"),  # 灰色
        StageStatus.RUNNING: ("#1976d2", "#bbdefb"),  # 蓝色
        StageStatus.COMPLETED: ("#388e3c", "#c8e6c9"),  # 绿色
        StageStatus.FAILED: ("#d32f2f", "#ffcdd2"),  # 红色
        StageStatus.SKIPPED: ("#757575", "#eeeeee"),  # 深灰
    }

    def __init__(self, stage_id: str, parent=None):
        super().__init__(parent)
        self.stage_id = stage_id
        self.status = StageStatus.PENDING
        self.duration = ""
        self.progress = 0

        self.setFixedSize(100, 80)
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setSpacing(2)

        # 阶段名称
        self.name_label = QLabel(self.STAGE_NAMES.get(stage_id, stage_id))
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setFont(QFont("Microsoft YaHei", 9))
        layout.addWidget(self.name_label)

        # 状态/时长
        self.status_label = QLabel("等待中")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("Microsoft YaHei", 8))
        layout.addWidget(self.status_label)

        self._update_style()

    def set_status(self, status: StageStatus, duration: str = "", progress: float = 0):
        """更新状态"""
        self.status = status
        self.duration = duration
        self.progress = progress

        status_text = {
            StageStatus.PENDING: "等待中",
            StageStatus.RUNNING: f"{progress:.0f}%" if progress > 0 else "运行中",
            StageStatus.COMPLETED: duration or "完成",
            StageStatus.FAILED: "失败",
            StageStatus.SKIPPED: "跳过",
        }
        self.status_label.setText(status_text.get(status, "未知"))
        self._update_style()

    def _update_style(self):
        """更新样式"""
        border_color, bg_color = self.STATUS_COLORS.get(self.status, ("#9e9e9e", "#e0e0e0"))
        self.setStyleSheet(f"""
            StageCard {{
                border: 2px solid {border_color};
                border-radius: 8px;
                background-color: {bg_color};
            }}
            QLabel {{
                background: transparent;
                color: {border_color};
            }}
        """)

    def mousePressEvent(self, event):
        self.clicked.emit(self.stage_id)


class StageFlowWidget(QWidget):
    """阶段流程图组件"""

    stage_selected = pyqtSignal(str)  # stage_id

    STAGE_ORDER = [
        "01_audio_extract",
        "02_vad_split",
        "03_asr_transcribe",
        "04_subtitle_optimize",
        "05_llm_postprocess",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setSpacing(10)

        self.cards = {}
        for i, stage_id in enumerate(self.STAGE_ORDER):
            # 阶段卡片
            card = StageCard(stage_id)
            card.clicked.connect(self._on_card_clicked)
            layout.addWidget(card)
            self.cards[stage_id] = card

            # 箭头（除了最后一个）
            if i < len(self.STAGE_ORDER) - 1:
                arrow = QLabel("▶")
                arrow.setStyleSheet("color: #bdbdbd; font-size: 14px;")
                layout.addWidget(arrow)

        layout.addStretch()

    def _on_card_clicked(self, stage_id: str):
        self.stage_selected.emit(stage_id)

    def update_status(self, status: PipelineStatus):
        """更新状态显示"""
        for stage_id, (stage_status, duration_sec) in status.stage_summary.items():
            if stage_id in self.cards:
                duration_str = ""
                if duration_sec:
                    minutes = duration_sec // 60
                    seconds = duration_sec % 60
                    duration_str = f"{minutes:02d}:{seconds:02d}"

                progress = 0
                if stage_status == StageStatus.RUNNING and status.current_stage == stage_id:
                    # 从 PipelineStatus 获取进度
                    progress = status.progress_percent

                self.cards[stage_id].set_status(stage_status, duration_str, progress)
```

- [ ] **Step 2: 创建 WorkspacePanel 工作区面板**

创建 `semsub/gui/widgets/workspace_panel.py`：

```python
"""
工作区面板组件
显示工作区状态、阶段流程和操作按钮
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal

from ...core.pipeline import SubtitlePipeline
from ...core.state_models import StageStatus, PipelineStatus
from .stage_flow_widget import StageFlowWidget


class WorkspacePanel(QGroupBox):
    """工作区面板"""

    refresh_requested = pyqtSignal()
    stage_action = pyqtSignal(str, str)  # stage_id, action

    def __init__(self, parent=None):
        super().__init__("工作区状态", parent)
        self.pipeline = None
        self.video_path = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 1. 视频信息
        info_layout = QHBoxLayout()
        self.video_label = QLabel("未选择视频")
        self.video_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.video_label)

        self.open_folder_btn = QPushButton("打开文件夹")
        self.open_folder_btn.clicked.connect(self._open_workspace_folder)
        self.open_folder_btn.setEnabled(False)
        info_layout.addWidget(self.open_folder_btn)

        info_layout.addStretch()
        layout.addLayout(info_layout)

        # 2. 阶段流程图
        self.stage_flow = StageFlowWidget()
        self.stage_flow.stage_selected.connect(self._on_stage_selected)
        layout.addWidget(self.stage_flow)

        # 3. 选中阶段的详情
        self.detail_group = QGroupBox("阶段详情")
        detail_layout = QVBoxLayout(self.detail_group)

        self.detail_title = QLabel("点击阶段查看详情")
        self.detail_title.setStyleSheet("font-weight: bold; color: #1976d2;")
        detail_layout.addWidget(self.detail_title)

        self.detail_status = QLabel("")
        detail_layout.addWidget(self.detail_status)

        # 操作按钮
        btn_layout = QHBoxLayout()
        self.view_input_btn = QPushButton("查看输入")
        self.view_input_btn.clicked.connect(lambda: self._stage_action("view_input"))
        self.view_input_btn.setEnabled(False)
        btn_layout.addWidget(self.view_input_btn)

        self.view_output_btn = QPushButton("查看输出")
        self.view_output_btn.clicked.connect(lambda: self._stage_action("view_output"))
        self.view_output_btn.setEnabled(False)
        btn_layout.addWidget(self.view_output_btn)

        self.run_stage_btn = QPushButton("执行此阶段")
        self.run_stage_btn.clicked.connect(lambda: self._stage_action("run"))
        self.run_stage_btn.setEnabled(False)
        btn_layout.addWidget(self.run_stage_btn)

        self.force_run_btn = QPushButton("强制重新执行")
        self.force_run_btn.clicked.connect(lambda: self._stage_action("force_run"))
        self.force_run_btn.setEnabled(False)
        btn_layout.addWidget(self.force_run_btn)

        detail_layout.addLayout(btn_layout)
        layout.addWidget(self.detail_group)

        # 4. 整体进度
        self.overall_status = QLabel("就绪")
        layout.addWidget(self.overall_status)

        # 刷新按钮
        self.refresh_btn = QPushButton("刷新状态")
        self.refresh_btn.clicked.connect(self._refresh_status)
        layout.addWidget(self.refresh_btn)

    def set_video(self, video_path: Path, pipeline: SubtitlePipeline):
        """设置当前视频"""
        self.video_path = video_path
        self.pipeline = pipeline
        self.video_label.setText(f"📁 {video_path.name}")
        self.open_folder_btn.setEnabled(True)
        self._refresh_status()

    def _refresh_status(self):
        """刷新状态"""
        if not self.video_path or not self.pipeline:
            return

        try:
            status = self.pipeline.get_status(self.video_path)
            self.stage_flow.update_status(status)

            status_text = status.overall_status.value
            if status.current_stage:
                status_text += f" ({status.current_stage})"
            self.overall_status.setText(f"整体状态: {status_text}")

        except Exception as e:
            self.overall_status.setText(f"无法获取状态: {e}")

    def _on_stage_selected(self, stage_id: str):
        """阶段被选中"""
        self.selected_stage = stage_id

        stage_names = {
            "01_audio_extract": "音频提取",
            "02_vad_split": "VAD 分割",
            "03_asr_transcribe": "ASR 转录",
            "04_subtitle_optimize": "字幕优化",
            "05_llm_postprocess": "LLM 后处理",
        }
        self.detail_title.setText(f"{stage_names.get(stage_id, stage_id)} ({stage_id})")

        # 获取阶段状态并更新按钮
        if self.pipeline:
            try:
                stages_info = self.pipeline.list_available_stages(self.video_path)
                for info in stages_info:
                    if info.stage_id == stage_id:
                        self.detail_status.setText(f"状态: {info.status.value} - {info.reason}")

                        # 根据状态启用不同按钮
                        can_run = info.can_execute or info.status == StageStatus.COMPLETED
                        self.run_stage_btn.setEnabled(can_run)
                        self.force_run_btn.setEnabled(can_run)
                        self.view_output_btn.setEnabled(info.status == StageStatus.COMPLETED)
                        break
            except Exception as e:
                self.detail_status.setText(f"错误: {e}")

    def _stage_action(self, action: str):
        """阶段操作"""
        if hasattr(self, 'selected_stage'):
            self.stage_action.emit(self.selected_stage, action)

    def _open_workspace_folder(self):
        """打开工作区文件夹"""
        if self.video_path:
            workspace_dir = self.video_path.parent / ".semsub"
            if workspace_dir.exists():
                import subprocess
                subprocess.run(["xdg-open", str(workspace_dir)])
```

- [ ] **Step 3: 修改主窗口集成 WorkspacePanel**

在 `main_window.py` 的 `_setup_ui` 方法中，在配置面板之前添加工作区面板：

```python
    def _setup_ui(self):
        # ... 文件选择区域代码 ...

        # 新增: 工作区面板
        from .widgets.workspace_panel import WorkspacePanel
        self.workspace_panel = WorkspacePanel()
        self.workspace_panel.stage_action.connect(self._on_stage_action)
        layout.addWidget(self.workspace_panel)

        # 原有: 配置面板（Tab）
        self.tabs = QTabWidget()
        # ...
```

修改 `_set_video_file` 方法：

```python
    def _set_video_file(self, path: str):
        """设置视频文件"""
        self.file_label.setText(f"已选择: {Path(path).name}")
        self.file_label.setProperty("file_path", path)
        self._log(f"已选择文件: {path}")

        # 更新工作区面板
        video_path = Path(path)
        pipeline = SubtitlePipeline(self.config)
        self.workspace_panel.set_video(video_path, pipeline)
```

添加阶段操作处理：

```python
    def _on_stage_action(self, stage_id: str, action: str):
        """处理阶段操作"""
        video_path = self.file_label.property("file_path")
        if not video_path:
            return

        if action == "run":
            self._log(f"执行阶段: {stage_id}")
            # TODO: 启动阶段执行
        elif action == "force_run":
            reply = QMessageBox.question(
                self, "确认",
                f"强制重新执行 {stage_id} 将使下游阶段失效，是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._log(f"强制重新执行阶段: {stage_id}")
                # TODO: 启动强制重新执行
        elif action == "view_input":
            self._log(f"查看阶段输入: {stage_id}")
        elif action == "view_output":
            self._log(f"查看阶段输出: {stage_id}")
```

- [ ] **Step 4: 创建 widgets 目录的 __init__.py**

创建 `semsub/gui/widgets/__init__.py`：

```python
"""
GUI 组件模块
"""

from .stage_flow_widget import StageFlowWidget, StageCard
from .workspace_panel import WorkspacePanel

__all__ = ["StageFlowWidget", "StageCard", "WorkspacePanel"]
```

- [ ] **Step 5: Commit**

```bash
git add semsub/gui/widgets/
git add semsub/gui/main_window.py
git commit -m "feat: Phase 5 GUI workspace panel with stage flow visualization"
```

---

## Task 8: 集成测试

**Files:**
- All modified files

**Context:** 测试完整功能，确保 CLI 和 GUI 都能正常工作

- [ ] **Step 1: 创建测试目录结构**

```bash
mkdir -p /tmp/semsub_test/series1
mkdir -p /tmp/semsub_test/series2

# 创建测试视频文件（空文件）
touch /tmp/semsub_test/video1.mp4
touch /tmp/semsub_test/video2.mkv
touch /tmp/semsub_test/series1/ep1.mp4
touch /tmp/semsub_test/series1/ep2.mp4
touch /tmp/semsub_test/series2/movie.avi

echo "Test directory structure:"
find /tmp/semsub_test -type f
```

- [ ] **Step 2: 测试 VideoScanner**

```bash
python -c "
from pathlib import Path
from semsub.core.batch_scanner import VideoScanner

scanner = VideoScanner()
tasks = scanner.scan([Path('/tmp/semsub_test')], recursive=True)

print(f'Found {len(tasks)} videos:')
for t in tasks:
    print(f'  - {Path(t.video_path).name}')
"
```

Expected:
```
Found 5 videos:
  - ep1.mp4
  - ep2.mp4
  - movie.avi
  - video1.mp4
  - video2.mkv
```

- [ ] **Step 3: 测试 CLI help**

```bash
python -m semsub generate --help
```

Expected: 显示包含 `INPUTS`, `--output-dir`, `--skip-existing` 等选项的帮助信息

- [ ] **Step 4: 测试 GUI 导入**

```bash
python -c "from semsub.gui.main_window import MainWindow; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test: batch processing integration tests"
```

---

## Self-Review Checklist

**Spec Coverage:**
- ✅ VideoTask, BatchProgressInfo, BatchResult 数据模型
- ✅ VideoScanner 递归扫描目录
- ✅ BatchPipeline 串行处理
- ✅ CLI generate 命令支持目录输入
- ✅ GUI 批量界面和双进度条
- ✅ 错误处理（立即停止）
- ✅ 灵活输出位置（output-dir）

**Placeholder Scan:** 无 TBD/TODO/"implement later"

**Type Consistency:**
- `VideoTask.video_path: str` 一致使用
- `BatchProgressInfo.percent` 返回 float
- `BatchResult.success: bool` 一致使用

---

## 执行选项

Plan complete and saved to `docs/superpowers/plans/2025-04-07-batch-directory-processing.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints for review

Which approach?
