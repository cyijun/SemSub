"""
主窗口 - 侧边栏导航布局
"""

from pathlib import Path
from typing import List, Optional
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox,
    QStackedWidget
)
from PyQt6.QtCore import Qt

from ..core.config import PipelineConfig
from ..core.config_manager import get_config_manager
from .widgets import NavigationSidebar


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SemSub - 智能字幕生成器")
        self.setMinimumSize(1200, 800)

        self.config_manager = get_config_manager()
        self.config = self.config_manager.load()

        self._setup_ui()

    def _setup_ui(self):
        """设置 UI - 侧边栏导航布局"""
        central = QWidget()
        self.setCentralWidget(central)
        
        # 主布局：水平排列
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 1. 左侧导航栏
        self.sidebar = NavigationSidebar()
        self.sidebar.module_changed.connect(self._on_module_changed)
        main_layout.addWidget(self.sidebar)

        # 2. 右侧内容区 - 使用 QStackedWidget 切换模块
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("""
            QStackedWidget {
                background-color: #2d2d2d;
            }
        """)
        main_layout.addWidget(self.content_stack, 1)  # 占据剩余空间

        # 初始化各模块（先创建占位）
        self._init_modules()

    def _init_modules(self):
        """初始化各功能模块"""
        from .modules.generate_module import GenerateModule
        from .modules.process_srt_module import ProcessSRTModule
        from .modules.status_module import StatusModule

        # 字幕生成模块
        self.generate_module = GenerateModule()
        self.content_stack.addWidget(self.generate_module)

        # 字幕处理模块
        self.process_srt_module = ProcessSRTModule()
        self.content_stack.addWidget(self.process_srt_module)

        # 工作区状态模块
        self.status_module = StatusModule()
        self.content_stack.addWidget(self.status_module)

        # 阶段执行模块
        from .modules.execution_module import ExecutionModule
        self.execution_module = ExecutionModule()
        self.content_stack.addWidget(self.execution_module)

        # 配置管理模块
        from .modules.config_module import ConfigModule
        self.config_module = ConfigModule()
        self.content_stack.addWidget(self.config_module)

    def _on_module_changed(self, module_id: str):
        """切换模块"""
        index = ["generate", "process_srt", "status", "execution", "config"].index(module_id)
        self.content_stack.setCurrentIndex(index)
