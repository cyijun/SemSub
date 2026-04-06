"""
工作区面板组件
显示工作区状态、阶段流程和操作按钮
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal

from ...core.pipeline import SubtitlePipeline
from ...core.state_models import StageStatus, PipelineStatus
from .stage_flow_widget import StageFlowWidget


class WorkspacePanel(QGroupBox):
    """工作区面板"""

    refresh_requested = pyqtSignal()
    stage_action = pyqtSignal(str, str)  # stage_id, action

    def __init__(self, parent=None):
        super().__init__("工作区状态", parent)
        self.pipeline = None
        self.video_path = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 1. 视频信息
        info_layout = QHBoxLayout()
        self.video_label = QLabel("未选择视频")
        self.video_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.video_label)

        self.open_folder_btn = QPushButton("打开文件夹")
        self.open_folder_btn.clicked.connect(self._open_workspace_folder)
        self.open_folder_btn.setEnabled(False)
        info_layout.addWidget(self.open_folder_btn)

        info_layout.addStretch()
        layout.addLayout(info_layout)

        # 2. 阶段流程图
        self.stage_flow = StageFlowWidget()
        self.stage_flow.stage_selected.connect(self._on_stage_selected)
        layout.addWidget(self.stage_flow)

        # 3. 选中阶段的详情
        self.detail_group = QGroupBox("阶段详情")
        detail_layout = QVBoxLayout(self.detail_group)

        self.detail_title = QLabel("点击阶段查看详情")
        self.detail_title.setStyleSheet("font-weight: bold; color: #1976d2;")
        detail_layout.addWidget(self.detail_title)

        self.detail_status = QLabel("")
        detail_layout.addWidget(self.detail_status)

        # 操作按钮
        btn_layout = QHBoxLayout()
        self.view_input_btn = QPushButton("查看输入")
        self.view_input_btn.clicked.connect(lambda: self._stage_action("view_input"))
        self.view_input_btn.setEnabled(False)
        btn_layout.addWidget(self.view_input_btn)

        self.view_output_btn = QPushButton("查看输出")
        self.view_output_btn.clicked.connect(lambda: self._stage_action("view_output"))
        self.view_output_btn.setEnabled(False)
        btn_layout.addWidget(self.view_output_btn)

        self.run_stage_btn = QPushButton("执行此阶段")
        self.run_stage_btn.clicked.connect(lambda: self._stage_action("run"))
        self.run_stage_btn.setEnabled(False)
        btn_layout.addWidget(self.run_stage_btn)

        self.force_run_btn = QPushButton("强制重新执行")
        self.force_run_btn.clicked.connect(lambda: self._stage_action("force_run"))
        self.force_run_btn.setEnabled(False)
        btn_layout.addWidget(self.force_run_btn)

        detail_layout.addLayout(btn_layout)
        layout.addWidget(self.detail_group)

        # 4. 整体进度
        self.overall_status = QLabel("就绪")
        layout.addWidget(self.overall_status)

        # 刷新按钮
        self.refresh_btn = QPushButton("刷新状态")
        self.refresh_btn.clicked.connect(self._refresh_status)
        layout.addWidget(self.refresh_btn)

    def set_video(self, video_path: Path, pipeline: SubtitlePipeline):
        """设置当前视频"""
        self.video_path = video_path
        self.pipeline = pipeline
        self.video_label.setText(f"📁 {video_path.name}")
        self.open_folder_btn.setEnabled(True)
        self._refresh_status()

    def _refresh_status(self):
        """刷新状态"""
        if not self.video_path or not self.pipeline:
            return

        try:
            status = self.pipeline.get_status(self.video_path)
            self.stage_flow.update_status(status)

            status_text = status.overall_status.value
            if status.current_stage:
                status_text += f" ({status.current_stage})"
            self.overall_status.setText(f"整体状态: {status_text}")

        except Exception as e:
            self.overall_status.setText(f"无法获取状态: {e}")

    def _on_stage_selected(self, stage_id: str):
        """阶段被选中"""
        self.selected_stage = stage_id

        stage_names = {
            "01_audio_extract": "音频提取",
            "02_vad_split": "VAD 分割",
            "03_asr_transcribe": "ASR 转录",
            "04_subtitle_optimize": "字幕优化",
            "05_llm_postprocess": "LLM 后处理",
        }
        self.detail_title.setText(f"{stage_names.get(stage_id, stage_id)} ({stage_id})")

        # 获取阶段状态并更新按钮
        if self.pipeline:
            try:
                stages_info = self.pipeline.list_available_stages(self.video_path)
                for info in stages_info:
                    if info.stage_id == stage_id:
                        self.detail_status.setText(f"状态: {info.status.value} - {info.reason}")

                        # 根据状态启用不同按钮
                        can_run = info.can_execute or info.status == StageStatus.COMPLETED
                        self.run_stage_btn.setEnabled(can_run)
                        self.force_run_btn.setEnabled(can_run)
                        self.view_output_btn.setEnabled(info.status == StageStatus.COMPLETED)
                        break
            except Exception as e:
                self.detail_status.setText(f"错误: {e}")

    def _stage_action(self, action: str):
        """阶段操作"""
        if hasattr(self, 'selected_stage'):
            self.stage_action.emit(self.selected_stage, action)

    def _open_workspace_folder(self):
        """打开工作区文件夹"""
        if self.video_path:
            workspace_dir = self.video_path.parent / ".semsub"
            if workspace_dir.exists():
                import subprocess
                subprocess.run(["xdg-open", str(workspace_dir)])
