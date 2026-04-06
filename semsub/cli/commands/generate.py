"""
生成字幕命令
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
@click.argument("video", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="输出字幕路径")
@click.option("--preset", type=click.Choice(["movie", "documentary", "animation"]), help="使用预设配置")
@click.option("--language", "-l", help="语言代码 (Chinese/English/None)")
@click.option("--format", "-f", type=click.Choice(["srt", "vtt", "json"]), default="srt", help="输出格式")
@click.option("--llm", is_flag=True, help="启用 LLM 后处理")
@click.option("--llm-prompt", default="correct.zh", help="LLM 提示词模板")
@click.option("--llm-mode", type=click.Choice(["correct", "translate", "bilingual"]), default="correct", help="LLM 输出模式")
@click.option("--from", "start_from", help="从指定阶段开始执行")
@click.option("--to", "stop_at", help="执行到指定阶段停止")
@click.option("--force", is_flag=True, help="强制重新执行（使下游阶段失效）")
@click.option("--workspace-dir", help="自定义工作区目录")
@click.pass_context
def generate(ctx, video, output, preset, language, format, llm, llm_prompt, llm_mode, start_from, stop_at, force, workspace_dir):
    """生成字幕"""
    video_path = Path(video)

    # 使用 ConfigManager 加载配置
    manager = get_config_manager()

    # 构建 CLI 覆盖
    cli_overrides = {}
    if language:
        cli_overrides["asr.language"] = language
    if format:
        cli_overrides["output.format"] = format
    if llm:
        cli_overrides["llm.enabled"] = "true"
        cli_overrides["llm.prompt_template"] = llm_prompt
        cli_overrides["llm.output_mode"] = llm_mode

    # 加载配置（自动合并预设、用户配置、项目配置、CLI 覆盖）
    config = manager.load(preset=preset, cli_overrides=cli_overrides)

    # 执行管道
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        reporter = RichProgressReporter(progress, None)
        pipeline = SubtitlePipeline(config, workspace_dir=Path(workspace_dir) if workspace_dir else None)

        try:
            output_path = pipeline.generate(
                video_path,
                Path(output) if output else None,
                reporter,
                start_from=start_from,
                stop_at=stop_at,
                force=force
            )
            console.print(f"\n[bold green]完成！输出文件: {output_path}[/bold green]")
        except Exception as e:
            console.print(f"[bold red]错误: {e}[/bold red]")
            raise click.Abort()
