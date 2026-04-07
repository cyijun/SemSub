"""
阶段执行模块
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QFileDialog,
    QGroupBox, QCheckBox, QTextEdit, QMessageBox,
    QProgressBar
)
from PyQt6.QtCore import Qt

from ...core.config_manager import get_config_manager
from ...core.workspace import WorkspaceManager
from ...core.state_models import StageStatus
from ..workers.stage_worker import StageWorker


class ExecutionModule(QWidget):
    """阶段执行模块"""

    STAGES = [
        ("01_audio_extract", "01_音频提取"),
        ("02_vad_split", "02_VAD分割"),
        ("03_asr_transcribe", "03_ASR转录"),
        ("04_subtitle_optimize", "04_字幕优化"),
        ("05_llm_postprocess", "05_LLM后处理"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config_manager().load()
        self.workspace = None
        self.video_path = None
        self.stage_worker = None
        self._setup_ui()

    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 1. 视频选择
        video_layout = QHBoxLayout()
        video_layout.addWidget(QLabel("选择视频:"))

        self.select_btn = QPushButton("📁 选择视频文件")
        self.select_btn.clicked.connect(self._select_video)
        video_layout.addWidget(self.select_btn)

        self.selected_label = QLabel("未选择")
        self.selected_label.setStyleSheet("color: #888;")
        video_layout.addWidget(self.selected_label)

        video_layout.addStretch()
        layout.addLayout(video_layout)

        # 2. 目标阶段选择
        stage_group = QGroupBox("目标阶段")
        stage_layout = QVBoxLayout(stage_group)

        self.stage_combo = QComboBox()
        for stage_id, stage_name in self.STAGES:
            self.stage_combo.addItem(f"{stage_name} ({stage_id})", stage_id)
        self.stage_combo.currentIndexChanged.connect(self._on_stage_changed)
        stage_layout.addWidget(self.stage_combo)

        layout.addWidget(stage_group)

        # 3. 依赖关系显示
        self.deps_group = QGroupBox("依赖关系")
        deps_layout = QVBoxLayout(self.deps_group)

        self.deps_label = QLabel("选择阶段查看依赖")
        deps_layout.addWidget(self.deps_label)

        self.deps_list = QTextEdit()
        self.deps_list.setReadOnly(True)
        self.deps_list.setMaximumHeight(100)
        deps_layout.addWidget(self.deps_list)

        layout.addWidget(self.deps_group)

        # 4. 执行选项
        options_group = QGroupBox("执行选项")
        options_layout = QVBoxLayout(options_group)

        self.force_cb = QCheckBox("强制重新执行 (--force)")
        options_layout.addWidget(self.force_cb)

        self.resume_cb = QCheckBox("从检查点恢复 (--resume)")
        options_layout.addWidget(self.resume_cb)

        layout.addWidget(options_group)

        # 5. 执行按钮和进度
        exec_layout = QHBoxLayout()

        self.execute_btn = QPushButton("▶️ 执行阶段")
        self.execute_btn.clicked.connect(self._execute_stage)
        self.execute_btn.setEnabled(False)
        exec_layout.addWidget(self.execute_btn)

        self.cancel_btn = QPushButton("⏹️ 取消")
        self.cancel_btn.clicked.connect(self._cancel_execution)
        self.cancel_btn.setEnabled(False)
        exec_layout.addWidget(self.cancel_btn)

        exec_layout.addStretch()
        layout.addLayout(exec_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)

        # 6. 日志输出
        layout.addWidget(QLabel("执行日志:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        layout.addWidget(self.log_text)

        layout.addStretch()

    def _select_video(self):
        """选择视频文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择视频文件", "",
            "视频文件 (*.mp4 *.mkv *.avi *.mov *.webm);;所有文件 (*)"
        )
        if file_path:
            self.video_path = Path(file_path)
            self.selected_label.setText(self.video_path.name)

            # 创建工作区
            manager = WorkspaceManager(self.config)
            self.workspace = manager.get_workspace(self.video_path)

            self.execute_btn.setEnabled(True)
            self._on_stage_changed()

    def _on_stage_changed(self):
        """阶段选择改变"""
        stage_id = self.stage_combo.currentData()
        if not stage_id or not self.workspace:
            return

        # 更新依赖显示
        self._update_dependencies(stage_id)

    def _update_dependencies(self, stage_id: str):
        """更新依赖显示"""
        deps_map = {
            "01_audio_extract": [],
            "02_vad_split": ["01_audio_extract"],
            "03_asr_transcribe": ["02_vad_split"],
            "04_subtitle_optimize": ["02_vad_split", "03_asr_transcribe"],
            "05_llm_postprocess": ["04_subtitle_optimize"],
        }

        deps = deps_map.get(stage_id, [])
        if not deps:
            self.deps_label.setText("此阶段无依赖")
            self.deps_list.clear()
            return

        # 检查每个依赖的状态
        dep_statuses = []
        for dep_id in deps:
            stage_context = self.workspace.get_stage_context(dep_id)
            status = stage_context.get_state().status
            status_icon = {
                StageStatus.PENDING: "⏸️",
                StageStatus.RUNNING: "▶️",
                StageStatus.COMPLETED: "✅",
                StageStatus.FAILED: "❌",
            }.get(status, "❓")
            dep_name = dict(self.STAGES).get(dep_id, dep_id)
            dep_statuses.append(f"{status_icon} {dep_name} ({dep_id}) - {status.value}")

        self.deps_label.setText(f"前置依赖: {len(deps)} 个")
        self.deps_list.setText("\n".join(dep_statuses))

    def _execute_stage(self):
        """执行阶段"""
        if not self.video_path:
            return

        stage_id = self.stage_combo.currentData()
        force = self.force_cb.isChecked()

        # 检查依赖
        if not force:
            deps_map = {
                "01_audio_extract": [],
                "02_vad_split": ["01_audio_extract"],
                "03_asr_transcribe": ["02_vad_split"],
                "04_subtitle_optimize": ["02_vad_split", "03_asr_transcribe"],
                "05_llm_postprocess": ["04_subtitle_optimize"],
            }
            missing = []
            for dep_id in deps_map.get(stage_id, []):
                stage_context = self.workspace.get_stage_context(dep_id)
                if stage_context.get_state().status != StageStatus.COMPLETED:
                    missing.append(dict(self.STAGES).get(dep_id, dep_id))

            if missing:
                reply = QMessageBox.question(
                    self, "依赖未满足",
                    f"以下依赖未完成:\n{', '.join(missing)}\n\n是否强制执行?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

        # 停止之前的 worker
        if self.stage_worker and self.stage_worker.isRunning():
            self.stage_worker.cancel()
            self.stage_worker.wait()

        # 创建新 worker
        self.stage_worker = StageWorker(
            self.video_path,
            stage_id,
            self.config,
            force=force,
            resume=self.resume_cb.isChecked()
        )

        # 连接信号
        self.stage_worker.started_signal.connect(self._on_stage_started)
        self.stage_worker.progress_signal.connect(self._on_stage_progress)
        self.stage_worker.finished_signal.connect(self._on_stage_finished)
        self.stage_worker.error_signal.connect(self._on_stage_error)
        self.stage_worker.log_signal.connect(self._log)

        # 更新 UI
        self.execute_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.log_text.clear()

        # 启动
        self.stage_worker.start()

    def _cancel_execution(self):
        """取消执行"""
        if self.stage_worker and self.stage_worker.isRunning():
            self.stage_worker.cancel()
            self._log("正在取消...")

    def _on_stage_started(self, stage_id: str):
        """阶段开始"""
        stage_name = dict(self.STAGES).get(stage_id, stage_id)
        self.status_label.setText(f"正在执行: {stage_name}")
        self._log(f"开始执行阶段: {stage_id}")

    def _on_stage_progress(self, percent: int, message: str):
        """阶段进度"""
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)

    def _on_stage_finished(self, success: bool, message: str):
        """阶段完成"""
        self.execute_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        if success:
            QMessageBox.information(self, "完成", message)
        else:
            QMessageBox.warning(self, "失败", message)

        # 刷新依赖显示
        self._on_stage_changed()

    def _on_stage_error(self, error: str):
        """阶段错误"""
        QMessageBox.critical(self, "错误", error)
        self.execute_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def _log(self, message: str):
        """添加日志"""
        self.log_text.append(message)
