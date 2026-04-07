"""
工作区面板组件
显示工作区状态、阶段流程和操作按钮
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QMessageBox, QFileDialog,
    QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal

from ...core.workspace import WorkspaceManager
from ...core.state_models import StageStatus
from ..workers.stage_worker import StageWorker
from .stage_flow_widget import StageFlowWidget


class WorkspacePanel(QGroupBox):
    """工作区面板"""

    stage_action = pyqtSignal(str, str)  # stage_id, action

    STAGE_NAMES = {
        "01_audio_extract": "音频提取",
        "02_vad_split": "VAD 分割",
        "03_asr_transcribe": "ASR 转录",
        "04_subtitle_optimize": "字幕优化",
        "05_llm_postprocess": "LLM 后处理",
    }

    def __init__(self, parent=None):
        super().__init__("工作区状态", parent)
        self.workspace = None
        self.video_path = None
        self.config = None
        self.selected_stage = None
        self.stage_worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 1. 视频信息
        info_layout = QHBoxLayout()
        self.video_label = QLabel("未选择视频")
        self.video_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        info_layout.addWidget(self.video_label)

        self.open_folder_btn = QPushButton("📁 打开文件夹")
        self.open_folder_btn.clicked.connect(self._open_workspace_folder)
        self.open_folder_btn.setEnabled(False)
        info_layout.addWidget(self.open_folder_btn)

        info_layout.addStretch()
        layout.addLayout(info_layout)

        # 2. 双区域布局
        content_layout = QHBoxLayout()

        # 左侧：阶段流程图
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.stage_flow = StageFlowWidget()
        self.stage_flow.stage_selected.connect(self._on_stage_selected)
        left_layout.addWidget(self.stage_flow)

        # 整体状态
        self.overall_status = QLabel("就绪")
        self.overall_status.setStyleSheet("color: #888; padding: 10px;")
        left_layout.addWidget(self.overall_status)

        left_layout.addStretch()
        content_layout.addWidget(left_widget, 1)

        # 右侧：阶段详情
        right_widget = QGroupBox("阶段详情")
        right_layout = QVBoxLayout(right_widget)

        self.detail_title = QLabel("点击阶段查看详情")
        self.detail_title.setStyleSheet("font-weight: bold; color: #1976d2; font-size: 13px;")
        right_layout.addWidget(self.detail_title)

        self.detail_status = QLabel("状态: -")
        right_layout.addWidget(self.detail_status)

        self.detail_time = QLabel("耗时: -")
        right_layout.addWidget(self.detail_time)

        # Artifacts 树
        right_layout.addWidget(QLabel("输出文件:"))
        self.artifacts_tree = QTreeWidget()
        self.artifacts_tree.setHeaderLabels(["文件名", "大小", "说明"])
        self.artifacts_tree.setMaximumHeight(120)
        right_layout.addWidget(self.artifacts_tree)

        # 操作按钮
        btn_layout = QHBoxLayout()

        self.view_input_btn = QPushButton("📥 查看输入")
        self.view_input_btn.clicked.connect(lambda: self._stage_action("view_input"))
        self.view_input_btn.setEnabled(False)
        btn_layout.addWidget(self.view_input_btn)

        self.view_output_btn = QPushButton("📤 查看输出")
        self.view_output_btn.clicked.connect(lambda: self._stage_action("view_output"))
        self.view_output_btn.setEnabled(False)
        btn_layout.addWidget(self.view_output_btn)

        right_layout.addLayout(btn_layout)

        action_layout = QHBoxLayout()

        self.run_stage_btn = QPushButton("▶️ 执行此阶段")
        self.run_stage_btn.clicked.connect(self._execute_stage)
        self.run_stage_btn.setEnabled(False)
        action_layout.addWidget(self.run_stage_btn)

        self.force_run_btn = QPushButton("🔄 强制重新执行")
        self.force_run_btn.clicked.connect(self._force_execute_stage)
        self.force_run_btn.setEnabled(False)
        action_layout.addWidget(self.force_run_btn)

        right_layout.addLayout(action_layout)

        content_layout.addWidget(right_widget, 1)
        layout.addLayout(content_layout)

        # 3. 底部按钮
        bottom_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("🔄 刷新状态")
        self.refresh_btn.clicked.connect(self.refresh_status)
        bottom_layout.addWidget(self.refresh_btn)

        bottom_layout.addStretch()
        layout.addLayout(bottom_layout)

    def set_video(self, video_path: Path, config):
        """设置当前视频"""
        self.video_path = video_path
        self.config = config
        self.video_label.setText(f"📹 {video_path.name}")
        self.open_folder_btn.setEnabled(True)

        # 创建工作区
        manager = WorkspaceManager(video_path)
        self.workspace = manager.open_or_initialize(config)

        self.refresh_status()

    def refresh_status(self):
        """刷新状态"""
        if not self.workspace:
            return

        try:
            state = self.workspace.get_global_state()

            # 更新阶段流程图
            self.stage_flow.update_status(state)

            # 更新整体状态
            status_text = f"整体状态: {state.overall_status.value}"
            if state.current_stage:
                status_text += f" ({state.current_stage})"
            self.overall_status.setText(status_text)

            # 如果当前有选中阶段，刷新详情
            if self.selected_stage:
                self._on_stage_selected(self.selected_stage)

        except Exception as e:
            self.overall_status.setText(f"无法获取状态: {e}")

    def _on_stage_selected(self, stage_id: str):
        """阶段被选中"""
        self.selected_stage = stage_id

        stage_name = self.STAGE_NAMES.get(stage_id, stage_id)
        self.detail_title.setText(f"{stage_name} ({stage_id})")

        # 获取阶段状态
        if self.workspace:
            try:
                stage_context = self.workspace.get_stage(stage_id)
                stage_state = stage_context.get_state()

                self.detail_status.setText(f"状态: {stage_state.status.value}")

                if stage_state.started_at and stage_state.completed_at:
                    duration = stage_state.completed_at - stage_state.started_at
                    self.detail_time.setText(f"耗时: {duration.total_seconds():.1f} 秒")
                else:
                    self.detail_time.setText("耗时: -")

                # 更新按钮状态
                is_completed = stage_state.status == StageStatus.COMPLETED
                self.view_output_btn.setEnabled(is_completed)
                self.view_input_btn.setEnabled(True)
                self.run_stage_btn.setEnabled(True)
                self.force_run_btn.setEnabled(True)

                # 加载 artifacts
                self._load_artifacts(stage_context)

            except Exception as e:
                self.detail_status.setText(f"错误: {e}")

    def _load_artifacts(self, stage_context):
        """加载 artifacts 信息"""
        self.artifacts_tree.clear()

        try:
            output = stage_context.load_output()
            if output and "artifacts" in output:
                for name, info in output["artifacts"].items():
                    item = QTreeWidgetItem([
                        name,
                        info.get("size", "-"),
                        info.get("description", "")
                    ])
                    self.artifacts_tree.addTopLevelItem(item)
        except Exception:
            pass

    def _execute_stage(self):
        """执行选中的阶段"""
        if not self.selected_stage or not self.video_path:
            return

        # 检查依赖
        deps_ok, missing = self._check_dependencies(self.selected_stage)
        if not deps_ok:
            reply = QMessageBox.question(
                self, "依赖未满足",
                f"以下依赖未完成:\n{', '.join(missing)}\n\n是否强制执行?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._run_stage(self.selected_stage, force=False)

    def _force_execute_stage(self):
        """强制重新执行阶段"""
        if not self.selected_stage or not self.video_path:
            return

        reply = QMessageBox.question(
            self, "确认",
            f"强制重新执行 {self.selected_stage} 将使下游阶段失效，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_stage(self.selected_stage, force=True)

    def _run_stage(self, stage_id: str, force: bool = False):
        """运行阶段"""
        # 停止之前的 worker
        if self.stage_worker and self.stage_worker.isRunning():
            self.stage_worker.cancel()
            self.stage_worker.wait()

        # 创建新 worker
        self.stage_worker = StageWorker(
            self.video_path,
            stage_id,
            self.config,
            force=force
        )

        # 连接信号
        self.stage_worker.started_signal.connect(lambda: self._on_stage_started(stage_id))
        self.stage_worker.progress_signal.connect(self._on_stage_progress)
        self.stage_worker.finished_signal.connect(self._on_stage_finished)
        self.stage_worker.error_signal.connect(self._on_stage_error)
        self.stage_worker.log_signal.connect(self._on_stage_log)

        # 禁用按钮
        self.run_stage_btn.setEnabled(False)
        self.force_run_btn.setEnabled(False)

        # 启动
        self.stage_worker.start()

    def _on_stage_started(self, stage_id: str):
        """阶段开始"""
        self.detail_status.setText("状态: 运行中...")

    def _on_stage_progress(self, percent: int, message: str):
        """阶段进度"""
        self.detail_status.setText(f"状态: 运行中 ({percent}%)")

    def _on_stage_finished(self, success: bool, message: str):
        """阶段完成"""
        self.run_stage_btn.setEnabled(True)
        self.force_run_btn.setEnabled(True)

        if success:
            QMessageBox.information(self, "完成", message)
        else:
            QMessageBox.warning(self, "失败", message)

        # 刷新状态
        self.refresh_status()

    def _on_stage_error(self, error: str):
        """阶段错误"""
        QMessageBox.critical(self, "错误", error)

    def _on_stage_log(self, message: str):
        """阶段日志"""
        # 可以发送到主日志区域
        pass

    def _check_dependencies(self, stage_id: str) -> tuple[bool, list]:
        """检查依赖"""
        deps_map = {
            "01_audio_extract": [],
            "02_vad_split": ["01_audio_extract"],
            "03_asr_transcribe": ["02_vad_split"],
            "04_subtitle_optimize": ["02_vad_split", "03_asr_transcribe"],
            "05_llm_postprocess": ["04_subtitle_optimize"],
        }

        missing = []
        for dep_id in deps_map.get(stage_id, []):
            stage_context = self.workspace.get_stage(dep_id)
            if stage_context.get_state().status != StageStatus.COMPLETED:
                missing.append(self.STAGE_NAMES.get(dep_id, dep_id))

        return len(missing) == 0, missing

    def _stage_action(self, action: str):
        """阶段操作"""
        if self.selected_stage:
            self.stage_action.emit(self.selected_stage, action)

    def _open_workspace_folder(self):
        """打开工作区文件夹"""
        if self.video_path:
            import subprocess
            import sys

            workspace_dir = self.video_path.parent / ".semsub"
            if workspace_dir.exists():
                if sys.platform == "darwin":
                    subprocess.run(["open", str(workspace_dir)])
                elif sys.platform == "win32":
                    subprocess.run(["explorer", str(workspace_dir)])
                else:
                    subprocess.run(["xdg-open", str(workspace_dir)])
