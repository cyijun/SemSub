"""
处理 SRT 文件命令 - 使用 LLM 对已有 SRT 文件进行后处理
"""

from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ...core.config import LLMProcessConfig
from ...core.config_manager import get_config_manager
from ...core.progress import ProgressReporter, PipelineStage, StageProgress
from ...core.srt_llm_processor import SRTLLMProcessor

console = Console()


class RichProgressReporter(ProgressReporter):
    """Rich 进度报告器"""

    def __init__(self, progress: Progress, task_id):
        super().__init__()
        self.progress = progress
        self.task_id = task_id
        self.stage_task = None

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

    def on_error(self, stage: PipelineStage, error: Exception):
        console.print(f"[bold red]✗ {stage} 错误: {error}[/bold red]")

    def on_log(self, message: str, level: str = "info"):
        style = {
            "info": "blue",
            "warning": "yellow",
            "error": "red",
            "success": "green"
        }.get(level, "white")
        console.print(f"[{style}]{message}[/]")


@click.command(name="process-srt")
@click.argument("input_srt", type=click.Path(exists=True, dir_okay=False))
@click.option("--output", "-o", type=click.Path(), help="输出 SRT 文件路径")
@click.option("--preset", type=click.Choice(["movie", "documentary", "animation"]), help="使用预设配置")
@click.option("--template", help="LLM 提示词模板名称")
@click.option("--mode", "output_mode", type=click.Choice(["correct", "translate", "bilingual"]),
              help="LLM 输出模式: correct=纠错, translate=翻译, bilingual=双语")
@click.option("--config-file", "-c", type=click.Path(exists=True), help="配置文件路径")
@click.pass_context
def process_srt(
    ctx,
    input_srt,
    output,
    preset,
    template,
    output_mode,
    config_file
):
    """
    使用 LLM 处理 SRT 字幕文件

    支持纠错、翻译、双语三种模式，直接处理已有的 SRT 文件，无需视频文件。

    \b
    示例：
        semsub process-srt input.srt
        semsub process-srt input.srt -o output.srt --mode correct
        semsub process-srt input.srt --mode translate --template translate.zh
        semsub process-srt input.srt --mode bilingual -o bilingual.srt
    """
    input_path = Path(input_srt)

    # 确定输出路径
    if output:
        output_path = Path(output)
    else:
        # 默认在输入文件名后添加 _processed
        output_path = input_path.with_stem(f"{input_path.stem}_processed")

    # 加载配置
    manager = get_config_manager()
    cli_overrides = {}
    if template:
        cli_overrides["llm.prompt_template"] = template
    if output_mode:
        cli_overrides["llm.output_mode"] = output_mode

    config_file_path = Path(config_file) if config_file else None
    pipeline_config = manager.load(
        preset=preset,
        config_file=config_file_path,
        cli_overrides=cli_overrides
    )

    # 确保 LLM 处理已启用
    llm_config = pipeline_config.llm
    llm_config.enabled = True

    # 检查 LLM 配置
    if not llm_config.api_key or not llm_config.base_url:
        console.print("[bold red]错误: LLM 未配置 API Key 或 Base URL[/bold red]")
        console.print("请通过以下方式之一配置:")
        console.print("  1. 配置文件 (~/.config/semsub/config.yaml 或 ./semsub.yaml)")
        console.print("  2. 环境变量 (SEMSUB_LLM_API_KEY, SEMSUB_LLM_BASE_URL)")
        raise click.Abort()

    # 创建处理器
    processor = SRTLLMProcessor(llm_config)

    # 显示配置信息
    console.print(f"[bold]输入文件:[/bold] {input_path}")
    console.print(f"[bold]输出文件:[/bold] {output_path}")
    console.print(f"[bold]处理模式:[/bold] {llm_config.output_mode}")
    console.print(f"[bold]提示词模板:[/bold] {llm_config.prompt_template}")
    console.print(f"[bold]模型:[/bold] {llm_config.model}")
    console.print()

    # 执行处理
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        reporter = RichProgressReporter(progress, None)

        try:
            result = processor.process_file(input_path, output_path, reporter)
        except Exception as e:
            console.print(f"[bold red]处理失败: {e}[/bold red]")
            raise click.Abort()

    # 显示结果统计
    console.print()
    console.print("[bold green]✓ 处理完成[/bold green]")
    console.print()

    # 创建统计表格
    table = Table(title="处理统计")
    table.add_column("项目", style="cyan")
    table.add_column("数值", style="green")

    table.add_row("输入文件", str(result.get("input_path", input_path)))
    table.add_row("输出文件", str(result.get("output_path", output_path)))
    table.add_row("总字幕行数", str(result.get("total_lines", 0)))

    if result.get("enabled"):
        table.add_row("修改行数", str(result.get("changed_lines", 0)))
        table.add_row("修改比例", f"{result.get('change_ratio', 0)}%")
        if result.get("failed_lines", 0) > 0:
            table.add_row("失败行数", str(result.get("failed_lines", 0)))
    else:
        table.add_row("处理状态", "已跳过 (LLM 未启用)")

    console.print(table)
