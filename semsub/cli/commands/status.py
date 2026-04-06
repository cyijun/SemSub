"""
查看工作区状态命令
"""

import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from ...core.pipeline import SubtitlePipeline
from ...core.config import PipelineConfig
from ...core.config_manager import get_config_manager
from ...core.state_models import StageStatus

console = Console()


STAGE_NAMES = {
    "01_audio_extract": "音频提取",
    "02_vad_split": "VAD 分割",
    "03_asr_transcribe": "ASR 转录",
    "04_subtitle_optimize": "字幕优化",
    "05_llm_postprocess": "LLM 后处理",
}

STATUS_ICONS = {
    StageStatus.PENDING: "⏸",
    StageStatus.RUNNING: "▶",
    StageStatus.COMPLETED: "✓",
    StageStatus.FAILED: "✗",
    StageStatus.SKIPPED: "⏭",
}

STATUS_COLORS = {
    StageStatus.PENDING: "dim",
    StageStatus.RUNNING: "cyan",
    StageStatus.COMPLETED: "green",
    StageStatus.FAILED: "red",
    StageStatus.SKIPPED: "yellow",
}


@click.command()
@click.argument("video", type=click.Path(exists=True))
@click.option("--verbose", "-v", is_flag=True, help="显示详细信息")
@click.option("--artifacts", is_flag=True, help="显示 artifacts 信息")
@click.option("--workspace-dir", help="自定义工作区目录")
def status(video, verbose, artifacts, workspace_dir):
    """查看工作区状态"""
    video_path = Path(video)
    config = get_config_manager().load()
    pipeline = SubtitlePipeline(config, workspace_dir=Path(workspace_dir) if workspace_dir else None)

    status_info = pipeline.get_status(video_path)

    if status_info is None:
        console.print(f"[yellow]工作区不存在: {video_path.parent / '.semsub'}[/yellow]")
        console.print("使用 'semsub init' 初始化工作区，或直接运行 'semsub generate'")
        return

    # 基本信息
    console.print(Panel.fit(
        f"[bold]视频:[/bold] {status_info.video_path}\n"
        f"[bold]工作区:[/bold] {status_info.workspace_path}\n"
        f"[bold]状态:[/bold] [{STATUS_COLORS.get(status_info.overall_status, 'white')}]{status_info.overall_status.value}[/]\n"
        f"[bold]进度:[/bold] {status_info.progress_percent:.1f}%\n"
        f"[bold]总耗时:[/bold] {status_info.total_duration_ms // 1000 // 60}分{status_info.total_duration_ms // 1000 % 60}秒"
        if status_info.total_duration_ms else "[bold]总耗时:[/bold] --",
        title="工作区概览",
        border_style="blue"
    ))

    # 阶段状态表格
    table = Table(title="阶段状态", box=box.ROUNDED)
    table.add_column("阶段", style="cyan")
    table.add_column("名称", style="cyan")
    table.add_column("状态", justify="center")
    table.add_column("耗时", justify="right")

    for stage_id, (stage_status, duration_sec) in status_info.stage_summary.items():
        icon = STATUS_ICONS.get(stage_status, "?")
        color = STATUS_COLORS.get(stage_status, "white")
        name = STAGE_NAMES.get(stage_id, stage_id)
        duration_str = f"{duration_sec}s" if duration_sec else "--"

        table.add_row(
            stage_id,
            name,
            f"[{color}]{icon} {stage_status.value}[/{color}]",
            duration_str
        )

    console.print(table)

    # 详细信息
    if verbose or artifacts:
        _show_artifacts(status_info.workspace_path, artifacts)


def _show_artifacts(workspace_path: str, show_artifacts: bool):
    """显示 artifacts 详细信息"""
    from ...core.workspace import safe_read_json
    import json

    workspace_dir = Path(workspace_path)

    for stage_id in ["01_audio_extract", "02_vad_split", "03_asr_transcribe", "04_subtitle_optimize", "05_llm_postprocess"]:
        stage_dir = workspace_dir / stage_id
        if not stage_dir.exists():
            continue

        output_path = stage_dir / "output.json"
        if output_path.exists():
            output_data = safe_read_json(output_path)
            if output_data:
                console.print(f"\n[bold]{stage_id}[/bold] artifacts:")
                for name, info in output_data.get("artifacts", {}).items():
                    size = info.get("size_bytes", 0)
                    size_str = f"({size / 1024 / 1024:.1f} MB)" if size > 1024 * 1024 else f"({size / 1024:.1f} KB)" if size > 1024 else f"({size} B)"
                    console.print(f"  • {name}: {info.get('path')} {size_str}")

                if show_artifacts and "statistics" in output_data:
                    console.print(f"  统计:")
                    for key, value in output_data["statistics"].items():
                        console.print(f"    - {key}: {value}")
