"""
清理工作区命令
"""

import click
from pathlib import Path
from rich.console import Console
from rich.prompt import Confirm

from ...core.workspace import WorkspaceManager

console = Console()


@click.command()
@click.argument("video", type=click.Path(exists=True))
@click.option("--keep-output", is_flag=True, help="保留最终输出文件(.srt等)")
@click.option("--yes", "-y", is_flag=True, help="跳过确认")
@click.option("--workspace-dir", help="自定义工作区目录")
def clean(video, keep_output, yes, workspace_dir):
    """清理工作区"""
    video_path = Path(video)
    manager = WorkspaceManager(video_path, Path(workspace_dir) if workspace_dir else None)

    if not manager.exists():
        console.print(f"[yellow]工作区不存在: {manager.workspace_dir}[/yellow]")
        return

    if not yes:
        action = "保留输出文件" if keep_output else "删除所有文件"
        if not Confirm.ask(f"确定要清理工作区吗？({action})"):
            console.print("已取消")
            return

    try:
        manager.delete(keep_output=keep_output)
        msg = "（保留输出文件）" if keep_output else ""
        console.print(f"[bold green]✓ 工作区已清理 {msg}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]✗ 清理失败: {e}[/bold red]")
        raise click.Abort()
