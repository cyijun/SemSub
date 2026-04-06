"""
CLI 入口
"""

import click
from pathlib import Path

from .commands.generate import generate
from .commands.config import config
from .commands.status import status
from .commands.run_stage import run_stage
from .commands.init import init
from .commands.clean import clean


@click.group()
@click.version_option(version="1.0.0", prog_name="semsub")
@click.option("--config-file", "-c", type=click.Path(), help="配置文件路径")
@click.pass_context
def cli(ctx, config_file):
    """SemSub - 智能字幕生成器"""
    ctx.ensure_object(dict)
    ctx.obj["config_file"] = config_file


cli.add_command(generate)
cli.add_command(config)
cli.add_command(status)
cli.add_command(run_stage)
cli.add_command(init)
cli.add_command(clean)


if __name__ == "__main__":
    cli()
