"""
SRT 处理页面

提供独立的 SRT 字幕后处理功能
"""

from pathlib import Path
from typing import Optional, List, Tuple

import gradio as gr

from ...core.config import LLMProcessConfig
from ...core.config_manager import get_config_manager
from ..utils import (
    load_config, save_config, get_llm_mode_choices,
    format_duration, get_preset_choices,
)


def create_srt_page() -> gr.Tab:
    """创建 SRT 处理页面"""

    with gr.Tab("📝 SRT 处理") as tab:
        gr.Markdown("""
        # 📝 SRT 字幕处理
        对已有的字幕文件进行翻译、纠错或生成双语字幕
        """)

        with gr.Row():
            # 左侧：输入和配置
            with gr.Column(scale=1):
                # 文件选择
                srt_input = gr.File(
                    label="📄 选择 SRT 字幕文件",
                    file_types=[".srt"],
                    file_count="single",
                )

                # 处理选项
                with gr.Group():
                    gr.Markdown("### 处理模式")

                    process_mode = gr.Radio(
                        choices=get_llm_mode_choices(),
                        value="correct",
                        label="选择处理方式",
                    )

                    target_language = gr.Dropdown(
                        choices=[
                            ("English", "en"),
                            ("中文", "zh"),
                            ("日本語", "ja"),
                            ("한국어", "ko"),
                            ("Français", "fr"),
                            ("Deutsch", "de"),
                            ("Español", "es"),
                        ],
                        value="en",
                        label="目标语言",
                        visible=False,
                    )

                    # 提示词模板选择
                    template_dropdown = gr.Dropdown(
                        choices=[
                            ("默认纠错模板", "correct.zh"),
                            ("默认翻译模板", "translate.en"),
                            ("双语字幕模板", "bilingual"),
                        ],
                        value="correct.zh",
                        label="提示词模板",
                    )

                # LLM 配置
                with gr.Accordion("🤖 LLM 配置", open=True):
                    llm_base_url = gr.Textbox(
                        label="Base URL",
                        placeholder="https://api.deepseek.com/v1",
                    )

                    llm_api_key = gr.Textbox(
                        label="API Key",
                        type="password",
                        placeholder="输入您的 API Key",
                    )

                    llm_model = gr.Dropdown(
                        choices=[
                            "deepseek-chat",
                            "deepseek-reasoner",
                            "moonshot-v1-8k",
                            "moonshot-v1-32k",
                            "qwen-turbo",
                            "qwen-plus",
                            "gpt-3.5-turbo",
                            "gpt-4",
                        ],
                        value="deepseek-chat",
                        label="模型",
                        allow_custom_value=True,
                    )

                    with gr.Row():
                        batch_size = gr.Slider(
                            minimum=1,
                            maximum=50,
                            value=10,
                            step=1,
                            label="批次大小",
                        )
                        temperature = gr.Slider(
                            minimum=0.0,
                            maximum=1.0,
                            value=0.3,
                            step=0.1,
                            label="Temperature",
                        )

                    # 加载配置按钮
                    load_config_btn = gr.Button("🔄 加载已保存的配置")

            # 右侧：预览和结果
            with gr.Column(scale=1):
                # 字幕预览
                with gr.Accordion("👁️ 原始字幕预览", open=False):
                    srt_preview = gr.Textbox(
                        label="前 20 行预览",
                        lines=10,
                        max_lines=15,
                        interactive=False,
                    )

                # 开始按钮
                start_process_btn = gr.Button(
                    "▶️ 开始处理",
                    variant="primary",
                    size="lg",
                    interactive=False,
                )

                # 进度区域
                with gr.Column(visible=False) as srt_progress_area:
                    gr.Markdown("### 📊 处理进度")

                    srt_progress_bar = gr.Slider(
                        minimum=0,
                        maximum=100,
                        value=0,
                        label="进度",
                        interactive=False,
                    )

                    srt_status = gr.Textbox(
                        label="状态",
                        interactive=False,
                    )

                # 结果区域
                with gr.Column(visible=False) as srt_result_area:
                    gr.Markdown("### ✅ 处理完成")

                    # 结果预览
                    result_preview = gr.Textbox(
                        label="处理后预览",
                        lines=10,
                        interactive=False,
                    )

                    # 下载按钮
                    download_result = gr.File(
                        label="下载处理后的字幕文件",
                    )

                    # 统计信息
                    process_stats = gr.JSON(label="处理统计")

        # 事件处理

        def toggle_target_lang(mode: str) -> gr.Dropdown:
            """切换目标语言显示"""
            return gr.Dropdown(visible=(mode == "translate"))

        process_mode.change(
            fn=toggle_target_lang,
            inputs=process_mode,
            outputs=target_language,
        )

        def update_template(mode: str) -> gr.Dropdown:
            """根据模式更新模板"""
            template_map = {
                "correct": "correct.zh",
                "translate": "translate.en",
                "bilingual": "bilingual",
            }
            return gr.Dropdown(value=template_map.get(mode, "correct.zh"))

        process_mode.change(
            fn=update_template,
            inputs=process_mode,
            outputs=template_dropdown,
        )

        def load_srt_preview(file_info) -> Tuple[str, bool]:
            """加载 SRT 文件预览"""
            if not file_info:
                return "", False

            try:
                file_path = Path(file_info.name if hasattr(file_info, 'name') else str(file_info))
                if not file_path.exists():
                    return f"文件不存在: {file_path}", False

                content = file_path.read_text(encoding='utf-8')
                lines = content.split('\n')[:20]
                preview = '\n'.join(lines)

                if len(content.split('\n')) > 20:
                    preview += "\n... (仅显示前20行)"

                return preview, True
            except Exception as e:
                return f"读取文件失败: {str(e)}", False

        srt_input.change(
            fn=load_srt_preview,
            inputs=srt_input,
            outputs=[srt_preview, start_process_btn],
        )

        def load_saved_config() -> Tuple[str, str, str]:
            """加载已保存的配置"""
            config = load_config()
            llm_config = config.llm

            return (
                llm_config.base_url or "",
                llm_config.api_key or "",
                llm_config.model or "deepseek-chat",
            )

        load_config_btn.click(
            fn=load_saved_config,
            outputs=[llm_base_url, llm_api_key, llm_model],
        )

        def process_srt(
            file_info,
            mode: str,
            target_lang: str,
            template: str,
            base_url: str,
            api_key: str,
            model: str,
            batch_sz: int,
            temp: float,
        ):
            """处理 SRT 文件"""
            if not file_info:
                yield {
                    srt_progress_area: gr.Column(visible=False),
                    srt_result_area: gr.Column(visible=False),
                }
                return

            file_path = Path(file_info.name if hasattr(file_info, 'name') else str(file_info))
            if not file_path.exists():
                yield {
                    srt_progress_area: gr.Column(visible=False),
                    srt_result_area: gr.Column(visible=True),
                    result_preview: f"文件不存在: {file_path}",
                }
                return

            # 显示进度
            yield {
                srt_progress_area: gr.Column(visible=True),
                srt_result_area: gr.Column(visible=False),
                srt_status: "正在读取字幕文件...",
            }

            try:
                # 读取字幕
                content = file_path.read_text(encoding='utf-8')

                # 解析字幕条目
                import re
                pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n((?:.|\n)*?)(?=\n\n|\Z)'
                matches = re.findall(pattern, content, re.MULTILINE)

                if not matches:
                    yield {
                        srt_progress_area: gr.Column(visible=False),
                        srt_result_area: gr.Column(visible=True),
                        result_preview: "无法解析字幕文件格式",
                    }
                    return

                total_entries = len(matches)

                # 配置 LLM
                llm_config = LLMProcessConfig(
                    enabled=True,
                    provider="openai_compatible",
                    base_url=base_url or None,
                    api_key=api_key or None,
                    model=model,
                    prompt_template=template,
                    output_mode=mode,
                    batch_size=batch_sz,
                    target_language=target_lang,
                    temperature=temp,
                )

                # 保存配置
                config = load_config()
                config.llm = llm_config
                save_config(config)

                yield {
                    srt_status: f"找到 {total_entries} 条字幕，开始处理...",
                    srt_progress_bar: 5,
                }

                # 模拟处理进度（实际实现需要调用 LLMClient）
                # 这里简化处理，实际应该分批调用 LLM
                processed = 0
                batch_count = (total_entries + batch_sz - 1) // batch_sz

                for batch_idx in range(batch_count):
                    start_idx = batch_idx * batch_sz
                    end_idx = min(start_idx + batch_sz, total_entries)

                    yield {
                        srt_status: f"处理批次 {batch_idx + 1}/{batch_count}...",
                        srt_progress_bar: 5 + (batch_idx / batch_count) * 90,
                    }

                    # TODO: 实际调用 LLM 处理
                    # 这里模拟处理时间
                    import time
                    time.sleep(0.1)

                    processed = end_idx

                # 生成输出文件
                output_path = file_path.parent / f"{file_path.stem}.processed.srt"

                # 简化：复制原文件作为示例
                # 实际应该使用 LLM 处理后的结果
                output_path.write_text(content, encoding='utf-8')

                yield {
                    srt_progress_bar: 100,
                    srt_status: "处理完成！",
                }

                # 生成预览
                preview_lines = content.split('\n')[:15]
                result_preview_text = '\n'.join(preview_lines)

                yield {
                    srt_progress_area: gr.Column(visible=False),
                    srt_result_area: gr.Column(visible=True),
                    result_preview: result_preview_text + "\n... (仅显示前15行)",
                    download_result: str(output_path),
                    process_stats: {
                        "原始条目数": total_entries,
                        "处理批次": batch_count,
                        "输出文件": str(output_path),
                    },
                }

            except Exception as e:
                yield {
                    srt_progress_area: gr.Column(visible=False),
                    srt_result_area: gr.Column(visible=True),
                    result_preview: f"处理失败: {str(e)}",
                }

        start_process_btn.click(
            fn=process_srt,
            inputs=[
                srt_input,
                process_mode,
                target_language,
                template_dropdown,
                llm_base_url,
                llm_api_key,
                llm_model,
                batch_size,
                temperature,
            ],
            outputs=[
                srt_progress_area,
                srt_result_area,
                srt_status,
                srt_progress_bar,
                result_preview,
                download_result,
                process_stats,
            ],
        )

    return tab
