"""
生成字幕命令
"""

from typing import Optional

import click
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ...core.config import PipelineConfig
from ...core.config_manager import get_config_manager
from ...core.pipeline import SubtitlePipeline
from ...core.progress import ProgressReporter, PipelineStage, StageProgress

console = Console()


class RichProgressReporter(ProgressReporter):
    """Rich 进度报告器"""

    def __init__(self, progress: Progress, task_id):
        super().__init__()
        self.progress = progress
        self.task_id = task_id
        self.stage_task = None

    def on_pipeline_start(self, stages):
        console.print(f"[bold green]开始处理，共 {len(stages)} 个阶段[/bold green]")

    def on_stage_start(self, stage: PipelineStage, total: int):
        self.stage_task = self.progress.add_task(f"[cyan]{stage}...", total=total)

    def on_progress(self, progress: StageProgress):
        if self.stage_task:
            self.progress.update(self.stage_task, completed=progress.current, description=f"[cyan]{progress.stage}: {progress.message}")

    def on_stage_complete(self, stage: PipelineStage, result):
        if self.stage_task:
            self.progress.update(self.stage_task, completed=100)

    def on_pipeline_complete(self, output_path: str):
        console.print(f"[bold green]✓ 字幕已保存: {output_path}[/bold green]")

    def on_error(self, stage: PipelineStage, error: Exception):
        console.print(f"[bold red]✗ {stage} 错误: {error}[/bold red]")

    def on_log(self, message: str, level: str = "info"):
        console.print(f"[{level}]{message}[/]")


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
    from ...core.batch_scanner import VideoScanner
    from ...core.batch_pipeline import BatchPipeline

    # 转换为 Path 列表
    input_paths = [Path(p) for p in inputs]

    # 判断是否是批量模式（输入包含目录，或输入多于1个文件）
    has_directory = any(p.is_dir() for p in input_paths)
    is_batch_mode = has_directory or len(input_paths) > 1

    # 使用 ConfigManager 加载配置
    manager = get_config_manager()

    # 构建 CLI 覆盖
    cli_overrides = {}
    if language:
        cli_overrides["asr.language"] = language
    if output_format:
        cli_overrides["output.format"] = output_format
    if llm:
        cli_overrides["llm.enabled"] = "true"
        cli_overrides["llm.prompt_template"] = llm_prompt
        cli_overrides["llm.output_mode"] = llm_mode

    # 加载配置（自动合并预设、用户配置、项目配置、CLI 覆盖）
    config = manager.load(preset=preset, cli_overrides=cli_overrides)

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
    video_path = Path(video_path)
    if output_path is None:
        output_path = video_path.with_suffix(f".{config.output.format}")
    else:
        output_path = Path(output_path)

    workspace_dir = Path(workspace_dir) if workspace_dir else None

    pipeline = SubtitlePipeline(config, workspace_dir=workspace_dir)

    # 执行管道
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        reporter = RichProgressReporter(progress, None)

        try:
            result = pipeline.generate(
                video_path=video_path,
                output_path=output_path,
                reporter=reporter,
                start_from=start_from,
                stop_at=stop_at,
                force=force
            )
            console.print(f"\n[bold green]完成！输出文件: {result}[/bold green]")
        except Exception as e:
            console.print(f"[bold red]错误: {e}[/bold red]")
            raise click.Abort()
