"""
初始化工作区命令
"""

import click
from pathlib import Path
from rich.console import Console

from ...core.config_manager import get_config_manager
from ...core.workspace import WorkspaceManager

console = Console()


@click.command()
@click.argument("video", type=click.Path(exists=True))
@click.option("--force", is_flag=True, help="强制重新初始化（删除现有工作区）")
@click.option("--workspace-dir", help="自定义工作区目录")
def init(video, force, workspace_dir):
    """初始化工作区（不执行任何阶段）"""
    video_path = Path(video)

    config = get_config_manager().load()
    manager = WorkspaceManager(video_path, Path(workspace_dir) if workspace_dir else None)

    if manager.exists() and not force:
        console.print(f"[yellow]工作区已存在: {manager.workspace_dir}[/yellow]")
        console.print("使用 --force 重新初始化")
        return

    try:
        workspace = manager.initialize(config, force=force)
        console.print(f"[bold green]✓ 工作区已初始化:[/bold green] {workspace.workspace_dir}")
        console.print(f"  视频: {video_path.name}")
        console.print(f"  哈希: {workspace.state.video_hash}")
        console.print("\n使用 'semsub generate' 或 'semsub run-stage' 开始处理")
    except Exception as e:
        console.print(f"[bold red]✗ 初始化失败: {e}[/bold red]")
        raise click.Abort()
