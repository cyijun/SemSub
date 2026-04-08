"""
批量处理页面

提供多视频批量处理功能
"""

import os
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

import gradio as gr

from ...core.pipeline import SubtitlePipeline
from ...core.batch_pipeline import BatchPipeline
from ...core.config import PipelineConfig
from ...core.batch_scanner import VideoScanner
from ...core.state_models import VideoTask
from ..state import state_manager, JobStatus
from ..utils import (
    load_config, apply_preset_to_config, get_preset_choices,
    get_format_choices, get_language_choices, format_duration,
    format_file_size, create_progress_html, check_subtitle_exists,
)


def create_batch_page() -> gr.Tab:
    """创建批量处理页面"""

    with gr.Tab("📁 批量处理") as tab:
        gr.Markdown("""
        # 📁 批量字幕生成
        同时处理多个视频文件
        """)

        # 存储批量任务状态
        batch_files_state = gr.State([])

        with gr.Row():
            # 左侧：文件管理
            with gr.Column(scale=1):
                # 添加文件路径
                gr.Markdown("### 添加视频文件路径")
                batch_path_input = gr.Textbox(
                    label="输入视频文件路径（每行一个）",
                    placeholder="/path/to/movie1.mp4\n/path/to/movie2.mkv",
                    lines=3,
                    max_lines=5,
                )

                with gr.Row():
                    add_paths_btn = gr.Button("➕ 添加到列表", variant="secondary")
                    clear_all_btn = gr.Button("🗑️ 清空列表")

                # 文件列表
                gr.Markdown("### 待处理文件列表")
                file_list_html = gr.HTML()

                # 全局设置
                with gr.Accordion("📋 批量设置", open=True):
                    batch_preset = gr.Dropdown(
                        choices=get_preset_choices(),
                        value="movie",
                        label="场景预设",
                    )

                    with gr.Row():
                        batch_format = gr.Dropdown(
                            choices=get_format_choices(),
                            value="srt",
                            label="输出格式",
                        )
                        batch_language = gr.Dropdown(
                            choices=get_language_choices(),
                            value=None,
                            label="语言",
                        )

                    with gr.Row():
                        skip_existing = gr.Checkbox(
                            label="跳过已有字幕的视频",
                            value=True,
                        )
                        continue_on_error = gr.Checkbox(
                            label="出错时继续处理其他",
                            value=True,
                        )

                    batch_enable_llm = gr.Checkbox(
                        label="启用 LLM 后处理",
                        value=False,
                    )

            # 右侧：处理和进度
            with gr.Column(scale=1):
                # 统计信息
                with gr.Row():
                    total_count = gr.Number(
                        value=0,
                        label="总文件数",
                        interactive=False,
                    )
                    ready_count = gr.Number(
                        value=0,
                        label="待处理",
                        interactive=False,
                    )
                    exist_count = gr.Number(
                        value=0,
                        label="已有字幕",
                        interactive=False,
                    )

                # 开始按钮
                start_batch_btn = gr.Button(
                    "▶️ 开始批量处理",
                    variant="primary",
                    size="lg",
                    interactive=False,
                )

                # 进度区域
                with gr.Column(visible=False) as batch_progress_area:
                    gr.Markdown("### 📊 处理进度")

                    batch_overall_progress = gr.Slider(
                        minimum=0,
                        maximum=100,
                        value=0,
                        label="整体进度",
                        interactive=False,
                    )

                    current_batch_file = gr.Textbox(
                        label="当前处理",
                        interactive=False,
                    )

                    batch_stats = gr.JSON(label="处理统计")

                    # 每个文件的状态
                    batch_file_status = gr.HTML(label="文件状态")

                # 结果区域
                with gr.Column(visible=False) as batch_result_area:
                    gr.Markdown("### ✅ 批量处理完成")
                    batch_result_summary = gr.JSON(label="结果汇总")
                    download_all_btn = gr.Button("📥 下载所有字幕文件")

        # 事件处理

        def parse_video_paths(path_text: str) -> List[Path]:
            """解析视频文件路径"""
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

        def add_files_to_list(
            path_text: str,
            current_files: List[Dict],
        ) -> Tuple[List[Dict], str, int, int, int, bool]:
            """添加文件到列表"""
            new_paths = parse_video_paths(path_text)
            if not new_paths:
                total = len(current_files)
                has_subtitle = sum(1 for f in current_files if f["has_subtitle"])
                ready = total - has_subtitle
                return current_files, _render_file_list(current_files), total, ready, has_subtitle, ready > 0

            for file_path in new_paths:
                # 检查是否已存在
                exists = any(f["path"] == str(file_path) for f in current_files)
                if not exists:
                    current_files.append({
                        "name": file_path.name,
                        "path": str(file_path),
                        "size": format_file_size(file_path.stat().st_size) if file_path.exists() else "未知",
                        "status": "pending",
                        "has_subtitle": False,
                    })

            # 更新统计
            total = len(current_files)
            has_subtitle = sum(1 for f in current_files if f["has_subtitle"])
            ready = total - has_subtitle

            html = _render_file_list(current_files)
            has_files = ready > 0

            # 更新统计
            total = len(current_files)
            has_subtitle = sum(1 for f in current_files if f["has_subtitle"])
            ready = total - has_subtitle

            html = _render_file_list(current_files)
            has_files = ready > 0

            # 返回时清空输入框
            return current_files, html, total, ready, has_subtitle, has_files

        def _render_file_list(files: List[Dict]) -> str:
            """渲染文件列表 HTML"""
            if not files:
                return "<div style='text-align: center; color: #999; padding: 20px;'>暂无文件</div>"

            html = '<div style="max-height: 300px; overflow-y: auto;">'

            for idx, f in enumerate(files):
                status_color = {
                    "pending": "#666",
                    "running": "#4a90d9",
                    "completed": "#28a745",
                    "failed": "#dc3545",
                    "skipped": "#ffc107",
                }.get(f["status"], "#666")

                status_icon = {
                    "pending": "⭕",
                    "running": "🔄",
                    "completed": "✅",
                    "failed": "❌",
                    "skipped": "⏭️",
                }.get(f["status"], "⭕")

                subtitle_badge = "<span style='background: #28a745; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin-left: 8px;'>已有字幕</span>" if f.get("has_subtitle") else ""

                html += f"""
                <div style="padding: 10px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center;">
                    <div style="flex: 1;">
                        <div style="font-weight: 500;">{f['name']}{subtitle_badge}</div>
                        <div style="font-size: 12px; color: #666;">{f['size']}</div>
                    </div>
                    <div style="color: {status_color}; font-size: 14px;">
                        {status_icon} {f.get('message', '')}
                    </div>
                </div>
                """

            html += '</div>'
            return html

        add_paths_btn.click(
            fn=add_files_to_list,
            inputs=[batch_path_input, batch_files_state],
            outputs=[
                batch_files_state,
                file_list_html,
                total_count,
                ready_count,
                exist_count,
                start_batch_btn,
            ],
        )

        def clear_all_files() -> Tuple[List, str, int, int, int, bool]:
            """清空所有文件"""
            return [], "<div style='text-align: center; color: #999; padding: 20px;'>暂无文件</div>", 0, 0, 0, False

        clear_all_btn.click(
            fn=clear_all_files,
            outputs=[
                batch_files_state,
                file_list_html,
                total_count,
                ready_count,
                exist_count,
                start_batch_btn,
            ],
        )

        def process_batch(
            files: List[Dict],
            preset: str,
            output_format: str,
            language: Optional[str],
            skip_exist: bool,
            continue_error: bool,
            enable_llm: bool,
        ):
            """批量处理"""
            if not files:
                yield {
                    batch_progress_area: gr.Column(visible=False),
                    batch_result_area: gr.Column(visible=False),
                }
                return

            # 加载配置
            config = load_config()
            config = apply_preset_to_config(config, preset)

            if language:
                config.asr.language = language
            config.output.format = output_format
            config.llm.enabled = enable_llm

            # 创建任务
            tasks = []
            for f in files:
                file_path = Path(f["path"])
                output_path = file_path.with_suffix(f".{output_format}")

                # 检查是否需要跳过
                if skip_exist and check_subtitle_exists(file_path, output_format):
                    f["status"] = "skipped"
                    f["message"] = "已跳过"
                    continue

                tasks.append(VideoTask(
                    video_path=str(file_path),
                    output_path=str(output_path),
                ))

            # 更新文件列表显示
            yield {
                batch_progress_area: gr.Column(visible=True),
                batch_result_area: gr.Column(visible=False),
                file_list_html: _render_file_list(files),
            }

            if not tasks:
                yield {
                    batch_progress_area: gr.Column(visible=False),
                    batch_result_area: gr.Column(visible=True),
                    batch_result_summary: {"状态": "所有文件都已处理或跳过"},
                }
                return

            # 执行批量处理
            batch_pipeline = BatchPipeline(config)

            # 进度追踪
            completed = 0
            failed = 0
            results = []

            for idx, task in enumerate(tasks):
                video_path = Path(task.video_path)
                video_name = video_path.name

                # 更新当前文件状态
                for f in files:
                    if f["path"] == str(video_path):
                        f["status"] = "running"
                        f["message"] = "处理中..."
                        break

                yield {
                    current_batch_file: f"[{idx + 1}/{len(tasks)}] {video_name}",
                    batch_overall_progress: (idx / len(tasks)) * 100,
                    file_list_html: _render_file_list(files),
                }

                try:
                    # 处理单个视频
                    pipeline = SubtitlePipeline(config)
                    result = pipeline.generate(
                        video_path=video_path,
                        output_path=task.output_path,
                    )

                    # 更新状态
                    for f in files:
                        if f["path"] == str(video_path):
                            f["status"] = "completed"
                            f["message"] = "完成"
                            break

                    completed += 1
                    results.append({
                        "video": video_name,
                        "status": "success",
                        "output": str(result),
                    })

                except Exception as e:
                    # 更新状态
                    for f in files:
                        if f["path"] == str(video_path):
                            f["status"] = "failed"
                            f["message"] = str(e)[:30]
                            break

                    failed += 1
                    results.append({
                        "video": video_name,
                        "status": "failed",
                        "error": str(e),
                    })

                    if not continue_error:
                        break

                yield {
                    batch_overall_progress: ((idx + 1) / len(tasks)) * 100,
                    batch_stats: {
                        "已完成": completed,
                        "失败": failed,
                        "剩余": len(tasks) - completed - failed,
                    },
                    file_list_html: _render_file_list(files),
                }

            # 显示结果
            yield {
                batch_progress_area: gr.Column(visible=False),
                batch_result_area: gr.Column(visible=True),
                batch_result_summary: {
                    "总任务数": len(files),
                    "已完成": completed,
                    "失败": failed,
                    "跳过": len(files) - len(tasks),
                    "详细结果": results,
                },
            }

        start_batch_btn.click(
            fn=process_batch,
            inputs=[
                batch_files_state,
                batch_preset,
                batch_format,
                batch_language,
                skip_existing,
                continue_on_error,
                batch_enable_llm,
            ],
            outputs=[
                batch_progress_area,
                batch_result_area,
                file_list_html,
                current_batch_file,
                batch_overall_progress,
                batch_stats,
                batch_result_summary,
            ],
        )

    return tab
