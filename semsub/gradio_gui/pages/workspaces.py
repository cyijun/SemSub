"""
工作区管理页面

管理所有活跃的工作区
"""

from pathlib import Path
from typing import List, Optional, Dict, Any

import gradio as gr

from ...core.pipeline import SubtitlePipeline
from ...core.config import PipelineConfig
from ..state import state_manager, JobStatus
from ..utils import (
    load_config, get_stage_icon, get_stage_name,
    format_duration, create_progress_html,
)


def create_workspaces_page() -> gr.Tab:
    """创建工作区管理页面"""

    with gr.Tab("🗂️ 工作区") as tab:
        gr.Markdown("""
        # 🗂️ 工作区管理
        查看和管理所有活跃的字幕生成工作区
        """)

        # 刷新按钮
        refresh_btn = gr.Button("🔄 刷新列表", size="sm")

        # 工作区列表
        workspaces_list = gr.HTML(label="工作区列表")

        # 工作区详情弹窗
        with gr.Column(visible=False) as workspace_detail:
            gr.Markdown("### 工作区详情")

            detail_video_path = gr.Textbox(label="视频路径", interactive=False)
            detail_status = gr.Textbox(label="当前状态", interactive=False)
            detail_progress = gr.Slider(label="进度", minimum=0, maximum=100, interactive=False)

            # 阶段状态
            detail_stages = gr.HTML(label="各阶段状态")

            # 操作按钮
            with gr.Row():
                continue_btn = gr.Button("▶️ 继续处理", variant="primary")
                restart_btn = gr.Button("🔄 重新处理")
                clean_btn = gr.Button("🗑️ 清理工作区", variant="stop")

            close_detail_btn = gr.Button("关闭")

    return tab

    # 事件处理

    def scan_workspaces() -> str:
        """扫描所有工作区"""
        # 从状态管理器获取任务
        jobs = state_manager.list_jobs()

        if not jobs:
            return """
            <div style="text-align: center; color: #999; padding: 40px;">
                <div style="font-size: 48px; margin-bottom: 20px;">📂</div>
                <div>暂无活跃工作区</div>
                <div style="font-size: 14px; margin-top: 10px;">
                    开始处理视频后将自动创建工作区
                </div>
            </div>
            """

        html = '<div style="display: flex; flex-direction: column; gap: 15px;">'

        for job in jobs:
            status_color = {
                "pending": "#ffc107",
                "running": "#4a90d9",
                "completed": "#28a745",
                "failed": "#dc3545",
                "cancelled": "#6c757d",
            }.get(job.status.value, "#6c757d")

            status_text = {
                "pending": "⏳ 等待中",
                "running": "🔄 处理中",
                "completed": "✅ 已完成",
                "failed": "❌ 失败",
                "cancelled": "🚫 已取消",
            }.get(job.status.value, "未知")

            # 阶段状态
            stage_html = ""
            if job.stages:
                stage_html = '<div style="display: flex; gap: 5px; margin-top: 10px;">'
                for stage in job.stages:
                    icon = get_stage_icon(stage.stage_id)
                    bg_color = {
                        "pending": "#f8f9fa",
                        "running": "#e3f2fd",
                        "completed": "#e8f5e9",
                        "failed": "#ffebee",
                    }.get(stage.status, "#f8f9fa")

                    stage_html += f"""
                    <div style="background: {bg_color}; padding: 5px 10px;
                                border-radius: 4px; font-size: 12px;
                                border: 1px solid #ddd;">
                        {icon} {stage.name}
                    </div>
                    """
                stage_html += '</div>'

            # 进度条
            progress_html = ""
            if job.status == JobStatus.RUNNING:
                progress_html = f"""
                <div style="margin-top: 10px;">
                    <div style="background: #f0f0f0; border-radius: 10px; overflow: hidden;">
                        <div style="width: {job.progress}%; background: linear-gradient(90deg, #4a90d9, #357abd);
                                    height: 8px; border-radius: 10px;">
                        </div>
                    </div>
                    <div style="font-size: 12px; color: #666; margin-top: 5px;">
                        {job.progress:.1f}% - {job.message}
                    </div>
                </div>
                """

            html += f"""
            <div style="border: 1px solid #ddd; border-radius: 8px; padding: 15px;
                        background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="flex: 1;">
                        <div style="font-weight: 500; font-size: 16px; margin-bottom: 5px;">
                            📹 {job.video_path.name}
                        </div>
                        <div style="font-size: 12px; color: #666;">
                            {job.video_path.parent}
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <div style="color: {status_color}; font-weight: 500;">
                            {status_text}
                        </div>
                        <div style="font-size: 12px; color: #999; margin-top: 5px;">
                            {job.created_at.strftime("%Y-%m-%d %H:%M")}
                        </div>
                    </div>
                </div>
                {progress_html}
                {stage_html}
                <div style="margin-top: 15px; display: flex; gap: 10px;">
                    <button onclick="showDetail('{job.id}')"
                            style="padding: 5px 15px; background: #4a90d9; color: white;
                                   border: none; border-radius: 4px; cursor: pointer;">
                        查看详情
                    </button>
                </div>
            </div>
            """

        html += '</div>'
        return html

    refresh_btn.click(
        fn=scan_workspaces,
        outputs=workspaces_list,
    )

    # 初始加载
    tab.select(fn=scan_workspaces, outputs=workspaces_list)

    return tab
