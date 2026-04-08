"""
首页 - 快速开始页面

提供简单的文件上传和字幕生成功能
"""

import os
import time
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, Generator

import gradio as gr

from ...core.pipeline import SubtitlePipeline
from ...core.config import PipelineConfig
from ..state import state_manager, JobStatus, ProgressReporter
from ..utils import (
    load_config, save_config, apply_preset_to_config,
    get_preset_choices, get_preset_description, get_language_choices,
    get_format_choices, get_llm_mode_choices, get_output_path,
    create_progress_html, create_stage_status_html, get_stage_name,
    format_duration, check_subtitle_exists,
)


def create_home_page() -> gr.Tab:
    """创建首页"""

    with gr.Tab("🏠 快速开始") as tab:
        gr.Markdown("""
        # 🎬 SemSub 智能字幕生成器
        上传视频，一键生成高质量字幕
        """)

        with gr.Row():
            # 左侧：文件路径输入和选项
            with gr.Column(scale=1):
                # 文件路径输入（支持多行，每行一个路径）
                file_path_input = gr.Textbox(
                    label="📁 视频文件路径（每行一个，支持批量）",
                    placeholder="/path/to/movie.mp4\n/path/to/another.mkv",
                    lines=3,
                    max_lines=5,
                )

                # 浏览按钮和添加按钮
                with gr.Row():
                    refresh_btn = gr.Button("🔄 刷新列表", size="sm")
                    clear_btn = gr.Button("🗑️ 清空", size="sm")

                # 文件列表显示
                file_list = gr.Dataframe(
                    headers=["文件名", "路径", "大小", "状态"],
                    label="已选择的文件",
                    visible=True,
                    interactive=False,
                    value=[],
                )

                # 路径提示
                gr.Markdown("""
                💡 **提示**：直接输入文件路径，无需上传。支持相对路径和绝对路径。
                """)

                with gr.Accordion("⚙️ 高级选项", open=False):
                    # 场景预设
                    preset_dropdown = gr.Dropdown(
                        choices=get_preset_choices(),
                        value="movie",
                        label="场景预设",
                    )
                    preset_desc = gr.Markdown(get_preset_description("movie"))

                    with gr.Row():
                        # 输出格式
                        format_dropdown = gr.Dropdown(
                            choices=get_format_choices(),
                            value="srt",
                            label="输出格式",
                        )
                        # 语言
                        language_dropdown = gr.Dropdown(
                            choices=get_language_choices(),
                            value=None,
                            label="语言（自动检测）",
                        )

                    # LLM 选项
                    enable_llm = gr.Checkbox(
                        label="启用 LLM 后处理",
                        value=False,
                    )

                    with gr.Column(visible=False) as llm_options:
                        llm_mode = gr.Radio(
                            choices=get_llm_mode_choices(),
                            value="correct",
                            label="处理模式",
                        )
                        llm_target_lang = gr.Dropdown(
                            choices=[
                                ("English", "en"),
                                ("中文", "zh"),
                                ("日本語", "ja"),
                                ("한국어", "ko"),
                            ],
                            value="en",
                            label="目标语言（翻译模式）",
                            visible=False,
                        )

            # 右侧：进度和结果
            with gr.Column(scale=1):
                # 开始按钮
                start_btn = gr.Button(
                    "🚀 开始生成字幕",
                    variant="primary",
                    size="lg",
                    interactive=False,
                )

                # 进度区域
                with gr.Column(visible=False) as progress_area:
                    gr.Markdown("### 📊 处理进度")

                    # 当前视频信息
                    current_video = gr.Textbox(
                        label="当前处理",
                        interactive=False,
                    )

                    # 整体进度条
                    overall_progress = gr.Slider(
                        minimum=0,
                        maximum=100,
                        value=0,
                        label="总体进度",
                        interactive=False,
                    )

                    # 阶段状态显示
                    stage_status = gr.HTML(label="阶段状态")

                    # 日志输出
                    log_output = gr.Textbox(
                        label="处理日志",
                        lines=5,
                        max_lines=10,
                        interactive=False,
                    )

                # 结果区域
                with gr.Column(visible=False) as result_area:
                    gr.Markdown("### ✅ 处理完成")
                    result_info = gr.JSON(label="结果详情")
                    download_btn = gr.File(label="下载字幕文件")

                # 错误区域
                with gr.Column(visible=False) as error_area:
                    gr.Markdown("### ❌ 处理失败")
                    error_message = gr.Textbox(
                        label="错误信息",
                        interactive=False,
                    )

        # 事件处理

        def update_preset_desc(preset: str) -> str:
            """更新预设描述"""
            return get_preset_description(preset)

        preset_dropdown.change(
            fn=update_preset_desc,
            inputs=preset_dropdown,
            outputs=preset_desc,
        )

        def toggle_llm_options(enabled: bool) -> gr.Column:
            """切换 LLM 选项显示"""
            return gr.Column(visible=enabled)

        enable_llm.change(
            fn=toggle_llm_options,
            inputs=enable_llm,
            outputs=llm_options,
        )

        def toggle_target_lang(mode: str) -> gr.Dropdown:
            """切换目标语言显示"""
            return gr.Dropdown(visible=(mode == "translate"))

        llm_mode.change(
            fn=toggle_target_lang,
            inputs=llm_mode,
            outputs=llm_target_lang,
        )

        def parse_file_paths(path_text: str) -> List[Path]:
            """解析文件路径文本，返回有效的视频文件路径列表"""
            if not path_text or not path_text.strip():
                return []

            paths = []
            video_extensions = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".flv"}

            for line in path_text.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue

                path = Path(line).expanduser().resolve()
                if path.exists() and path.suffix.lower() in video_extensions:
                    paths.append(path)

            return paths

        def update_file_list(path_text: str) -> Tuple[gr.Dataframe, gr.Button]:
            """更新文件列表并返回"""
            paths = parse_file_paths(path_text)

            if not paths:
                return gr.Dataframe(value=[]), gr.Button(interactive=False)

            rows = []
            for p in paths:
                size_mb = p.stat().st_size / (1024 * 1024)
                size_str = f"{size_mb:.1f} MB" if size_mb < 1024 else f"{size_mb/1024:.2f} GB"
                rows.append([p.name, str(p.parent), size_str, "就绪"])

            return gr.Dataframe(value=rows), gr.Button(interactive=True)

        def clear_paths() -> Tuple[gr.Textbox, gr.Dataframe, gr.Button]:
            """清空路径"""
            return gr.Textbox(value=""), gr.Dataframe(value=[]), gr.Button(interactive=False)

        file_path_input.change(
            fn=update_file_list,
            inputs=file_path_input,
            outputs=[file_list, start_btn],
        )

        refresh_btn.click(
            fn=update_file_list,
            inputs=file_path_input,
            outputs=[file_list, start_btn],
        )

        clear_btn.click(
            fn=clear_paths,
            outputs=[file_path_input, file_list, start_btn],
        )

        def process_videos(
            path_text: str,
            preset: str,
            output_format: str,
            language: Optional[str],
            enable_llm_flag: bool,
            llm_mode_val: str,
            llm_target: str,
        ) -> Generator[Tuple[Any, ...], None, None]:
            """处理视频 - 生成器函数用于流式更新"""

            file_paths = parse_file_paths(path_text)

            if not file_paths:
                yield {
                    progress_area: gr.Column(visible=False),
                    result_area: gr.Column(visible=False),
                    error_area: gr.Column(visible=True),
                    error_message: "请输入有效的视频文件路径",
                }
                return

            # 加载配置
            config = load_config()

            # 应用预设
            config = apply_preset_to_config(config, preset)

            # 应用其他选项
            if language:
                config.asr.language = language
            config.output.format = output_format

            # 配置 LLM
            config.llm.enabled = enable_llm_flag
            if enable_llm_flag:
                config.llm.output_mode = llm_mode_val
                config.llm.target_language = llm_target

            # 显示进度区域
            yield {
                progress_area: gr.Column(visible=True),
                result_area: gr.Column(visible=False),
                error_area: gr.Column(visible=False),
                current_video: f"准备处理 {len(file_paths)} 个视频...",
                log_output: "",
            }

            # 处理每个文件
            results = []
            pipeline = SubtitlePipeline(config)

            for idx, file_path in enumerate(file_paths):

                video_name = file_path.name

                # 创建任务
                job = state_manager.create_job(file_path)

                yield {
                    current_video: f"[{idx + 1}/{len(file_paths)}] {video_name}",
                    log_output: f"开始处理: {video_name}\n",
                }

                try:
                    state_manager.update_job(job.id, status=JobStatus.RUNNING)

                    # 进度报告器
                    reporter = ProgressReporter(job.id)

                    # 初始化阶段
                    stages = [
                        {"stage_id": s, "name": get_stage_name(s), "status": "pending", "message": ""}
                        for s in ["01_audio_extract", "02_vad_split", "03_asr_transcribe",
                                 "04_subtitle_optimize", "05_llm_postprocess"]
                    ]

                    # 开始处理
                    output_path = get_output_path(file_path, output_format)

                    # 执行生成
                    result = pipeline.generate(
                        video_path=file_path,
                        output_path=output_path,
                        reporter=reporter,
                    )

                    # 更新状态
                    state_manager.update_job(
                        job.id,
                        status=JobStatus.COMPLETED,
                        progress=100.0,
                        message=f"完成: {result}",
                        result=result,
                    )

                    results.append({
                        "video": video_name,
                        "status": "success",
                        "output": str(result),
                    })

                    yield {
                        overall_progress: ((idx + 1) / len(file_paths)) * 100,
                        log_output: f"✅ 完成: {video_name} -> {result}\n",
                        stage_status: create_stage_status_html([
                            {**s, "status": "completed"} for s in stages
                        ]),
                    }

                except Exception as e:
                    error_msg = str(e)
                    state_manager.update_job(
                        job.id,
                        status=JobStatus.FAILED,
                        error=error_msg,
                    )

                    results.append({
                        "video": video_name,
                        "status": "failed",
                        "error": error_msg,
                    })

                    yield {
                        log_output: f"❌ 失败: {video_name} - {error_msg}\n",
                    }

            # 显示结果
            success_count = sum(1 for r in results if r["status"] == "success")

            yield {
                progress_area: gr.Column(visible=False),
                result_area: gr.Column(visible=True),
                error_area: gr.Column(visible=False),
                result_info: {
                    "总视频数": len(file_paths),
                    "成功": success_count,
                    "失败": len(file_paths) - success_count,
                    "详细结果": results,
                },
            }

        start_btn.click(
            fn=process_videos,
            inputs=[
                file_path_input,
                preset_dropdown,
                format_dropdown,
                language_dropdown,
                enable_llm,
                llm_mode,
                llm_target_lang,
            ],
            outputs=[
                progress_area,
                result_area,
                error_area,
                current_video,
                overall_progress,
                log_output,
                stage_status,
                result_info,
            ],
        )

    return tab
