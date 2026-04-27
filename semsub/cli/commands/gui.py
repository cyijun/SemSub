"""
GUI 命令 - 启动 Web 界面
"""

import click


@click.command(name="gui")
@click.option("--host", default="0.0.0.0", help="服务器地址")
@click.option("--port", default=7860, help="服务器端口", type=int)
@click.option("--debug", is_flag=True, help="启用调试模式")
def gui(host, port, debug):
    """启动 SemSub Web GUI"""
    click.echo("🚀 启动 SemSub Web GUI...")
    click.echo(f"📡 服务器地址: http://{host}:{port}")

    import uvicorn
    from semsub.web.main import create_app

    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="debug" if debug else "info")
