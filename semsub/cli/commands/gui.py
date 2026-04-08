"""
GUI 命令 - 启动 Gradio 界面
"""

import click


@click.command(name="gui")
@click.option("--host", default="0.0.0.0", help="服务器地址")
@click.option("--port", default=7860, help="服务器端口")
@click.option("--share", is_flag=True, help="创建公开分享链接")
@click.option("--debug", is_flag=True, help="启用调试模式")
def gui(host, port, share, debug):
    """启动 Gradio Web 界面"""
    click.echo("🚀 启动 SemSub Gradio GUI...")
    click.echo(f"📡 服务器地址: http://{host}:{port}")

    if share:
        click.echo("🌐 正在创建公开分享链接...")

    # 启动 Gradio GUI
    from semsub.gradio_gui.app import create_app

    app = create_app()
    app.launch(
        server_name=host,
        server_port=port,
        share=share,
        debug=debug,
        show_error=True,
    )
