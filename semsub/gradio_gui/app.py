"""
Gradio GUI 主应用

整合所有页面的主应用入口
"""

import argparse
from typing import Optional

import gradio as gr

from .pages import (
    create_home_page,
    create_batch_page,
    create_srt_page,
    create_workspaces_page,
    create_settings_page,
)


def create_app(theme: Optional[gr.Theme] = None) -> gr.Blocks:
    """创建 Gradio 应用

    Args:
        theme: 可选的主题

    Returns:
        Gradio Blocks 应用
    """

    # 默认主题
    if theme is None:
        theme = gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="slate",
            neutral_hue="slate",
        )

    # 创建应用
    app = gr.Blocks(
        theme=theme,
        title="SemSub - 智能字幕生成器",
        css="""
        .upload-area {
            min-height: 150px !important;
            border: 2px dashed #ccc !important;
            border-radius: 10px !important;
            transition: all 0.3s ease;
        }
        .upload-area:hover {
            border-color: #4a90d9 !important;
            background-color: #f8f9fa !important;
        }
        .primary-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        }
        .gradio-container {
            max-width: 1400px !important;
        }
        """,
    )

    with app:
        # 页面标题
        gr.Markdown("""
        <div style="text-align: center; padding: 20px 0;">
            <h1 style="margin: 0; font-size: 2.5em; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                       -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                🎬 SemSub
            </h1>
            <p style="margin: 10px 0 0 0; color: #666; font-size: 1.1em;">
                智能字幕生成器 - 基于 Qwen3-ASR 的高质量字幕制作工具
            </p>
        </div>
        """)

        # 创建所有页面
        with gr.Tabs():
            create_home_page()
            create_batch_page()
            create_srt_page()
            create_workspaces_page()
            create_settings_page()

        # 页脚
        gr.Markdown("""
        <div style="text-align: center; padding: 20px 0; margin-top: 30px;
                    border-top: 1px solid #eee; color: #999; font-size: 0.9em;">
            <p>
                SemSub v1.0.0 |
                <a href="https://github.com/cyijun/SemSub" target="_blank">GitHub</a> |
                使用 Qwen3-ASR 和 Silero VAD 技术
            </p>
        </div>
        """)

    return app


def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(description="SemSub Gradio GUI")
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="服务器地址 (默认: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="服务器端口 (默认: 7860)",
    )
    parser.add_argument(
        "--share",
        action="store_true",
        help="创建公开分享链接",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试模式",
    )
    parser.add_argument(
        "--auth",
        type=str,
        help="基本认证，格式: username:password",
    )

    args = parser.parse_args()

    # 创建应用
    app = create_app()

    # 认证配置
    auth = None
    if args.auth:
        try:
            username, password = args.auth.split(":", 1)
            auth = (username, password)
        except ValueError:
            print("错误: 认证格式应为 username:password")
            return

    # 启动应用
    print(f"🚀 启动 SemSub Gradio GUI...")
    print(f"📡 服务器地址: http://{args.host}:{args.port}")
    if args.share:
        print("🌐 正在创建公开分享链接...")

    app.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        debug=args.debug,
        auth=auth,
        show_error=True,
        quiet=False,
    )


if __name__ == "__main__":
    main()
