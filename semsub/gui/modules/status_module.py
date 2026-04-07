"""
工作区状态模块
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog
)
from PyQt6.QtCore import Qt

from ...core.workspace import WorkspaceManager
from ...core.config_manager import get_config_manager
from ..widgets import WorkspacePanel


class StatusModule(QWidget):
    """工作区状态模块"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = get_config_manager().load()
        self._setup_ui()

    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 1. 视频选择
        select_layout = QHBoxLayout()

        select_layout.addWidget(QLabel("选择视频:"))

        self.select_btn = QPushButton("📁 选择视频文件")
        self.select_btn.clicked.connect(self._select_video)
        select_layout.addWidget(self.select_btn)

        self.selected_label = QLabel("未选择")
        self.selected_label.setStyleSheet("color: #888;")
        select_layout.addWidget(self.selected_label)

        select_layout.addStretch()
        layout.addLayout(select_layout)

        # 2. 工作区面板
        self.workspace_panel = WorkspacePanel()
        layout.addWidget(self.workspace_panel)

        # 3. 快捷操作
        actions_group = QWidget()
        actions_layout = QHBoxLayout(actions_group)
        actions_layout.setContentsMargins(0, 0, 0, 0)

        self.clean_btn = QPushButton("🗑️ 清理工作区")
        self.clean_btn.clicked.connect(self._clean_workspace)
        self.clean_btn.setToolTip("删除工作区临时文件，保留最终字幕")
        actions_layout.addWidget(self.clean_btn)

        self.clean_all_btn = QPushButton("🗑️💥 完全清理")
        self.clean_all_btn.clicked.connect(self._clean_all)
        self.clean_all_btn.setToolTip("删除工作区和所有输出文件")
        actions_layout.addWidget(self.clean_all_btn)

        actions_layout.addStretch()
        layout.addWidget(actions_group)

    def _select_video(self):
        """选择视频文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择视频文件", "",
            "视频文件 (*.mp4 *.mkv *.avi *.mov *.webm);;所有文件 (*)"
        )
        if file_path:
            video_path = Path(file_path)
            self.selected_label.setText(video_path.name)
            self.workspace_panel.set_video(video_path, self.config)

    def _clean_workspace(self):
        """清理工作区（保留输出）"""
        if not self.workspace_panel.workspace:
            return

        from PyQt6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self, "确认清理",
            "确定要清理工作区吗？\n这将删除临时文件，但保留最终字幕输出。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.workspace_panel.workspace.clean(keep_output=True)
                QMessageBox.information(self, "完成", "工作区已清理")
                self.workspace_panel.refresh_status()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"清理失败: {e}")

    def _clean_all(self):
        """完全清理"""
        if not self.workspace_panel.workspace:
            return

        from PyQt6.QtWidgets import QMessageBox

        reply = QMessageBox.warning(
            self, "⚠️ 危险操作",
            "确定要完全清理吗？\n这将删除工作区和所有输出文件（包括字幕），不可恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.workspace_panel.workspace.clean(keep_output=False)
                QMessageBox.information(self, "完成", "工作区和输出文件已删除")
                self.workspace_panel.refresh_status()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"清理失败: {e}")
