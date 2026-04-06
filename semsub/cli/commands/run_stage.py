"""
执行单个阶段命令
"""

import click
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ...core.config import PipelineConfig
from ...core.config_manager import get_config_manager
from ...core.pipeline import SubtitlePipeline
from ...core.progress import ProgressReporter, PipelineStage, StageProgress

console = Console()


class StageProgressReporter(ProgressReporter):
    """阶段进度报告器"""

    def __init__(self, progress: Progress):
        super().__init__()
        self.progress = progress
        self.stage_task = None

    def on_pipeline_start(self, stages):
        pass

    def on_stage_start(self, stage: PipelineStage, total: int):
        self.stage_task = self.progress.add_task(f"[cyan]{stage}...", total=total)

    def on_progress(self, progress: StageProgress):
        if self.stage_task:
            self.progress.update(
                self.stage_task,
                completed=progress.current,
                description=f"[cyan]{progress.stage}: {progress.message}"
            )

    def on_stage_complete(self, stage: PipelineStage, result):
        if self.stage_task:
            self.progress.update(self.stage_task, completed=100)

    def on_pipeline_complete(self, output_path: str):
        pass

    def on_error(self, stage: PipelineStage, error: Exception):
        console.print(f"[bold red]✗ {stage} 错误: {error}[/bold red]")

    def on_log(self, message: str, level: str = "info"):
        console.print(f"  [{level}]{message}[/]")


@click.command()
@click.argument("video", type=click.Path(exists=True))
@click.argument("stage_id")
@click.option("--force", is_flag=True, help="强制重新执行")
@click.option("--resume", is_flag=True, help="从检查点恢复")
@click.option("--workspace-dir", help="自定义工作区目录")
def run_stage(video, stage_id, force, resume, workspace_dir):
    """执行单个阶段

    STAGE_ID 可以是:
    - 01_audio_extract: 音频提取
    - 02_vad_split: VAD 分割
    - 03_asr_transcribe: ASR 转录
    - 04_subtitle_optimize: 字幕优化
    - 05_llm_postprocess: LLM 后处理
    """
    video_path = Path(video)

    # 验证 stage_id
    valid_stages = ["01_audio_extract", "02_vad_split", "03_asr_transcribe",
                    "04_subtitle_optimize", "05_llm_postprocess"]
    if stage_id not in valid_stages:
        console.print(f"[red]无效的阶段 ID: {stage_id}[/red]")
        console.print(f"有效的阶段: {', '.join(valid_stages)}")
        raise click.Abort()

    # 加载配置
    config = get_config_manager().load()
    pipeline = SubtitlePipeline(config, workspace_dir=Path(workspace_dir) if workspace_dir else None)

    # 检查依赖
    if not force:
        stages_info = pipeline.list_available_stages(video_path)
        stage_info = next((s for s in stages_info if s.stage_id == stage_id), None)

        if stage_info and not stage_info.can_execute:
            console.print(f"[red]无法执行阶段 {stage_id}:[/red] {stage_info.reason}")
            console.print("使用 --force 强制重新执行（会重新执行该阶段及下游阶段）")
            raise click.Abort()

    # 执行阶段
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        reporter = StageProgressReporter(progress)

        try:
            result = pipeline.run_stage(video_path, stage_id, reporter, force=force, resume=resume)
            console.print(f"[bold green]✓ 阶段 {stage_id} 执行完成[/bold green]")

            # 显示统计信息
            if "statistics" in result:
                console.print("\n[bold]统计:[/bold]")
                for key, value in result["statistics"].items():
                    console.print(f"  {key}: {value}")

        except Exception as e:
            console.print(f"[bold red]✗ 阶段 {stage_id} 失败: {e}[/bold red]")
            raise click.Abort()
