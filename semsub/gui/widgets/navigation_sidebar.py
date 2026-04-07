"""
侧边栏导航组件
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QFrame,
    QLabel, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont


class NavButton(QPushButton):
    """导航按钮"""
    
    def __init__(self, text: str, icon: str = "", parent=None):
        super().__init__(f"{icon} {text}" if icon else text, parent)
        self.setCheckable(True)
        self.setMinimumHeight(45)
        self.setFont(QFont("Microsoft YaHei", 11))
        self.setStyleSheet("""
            NavButton {
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                text-align: left;
                background-color: transparent;
                color: #e0e0e0;
            }
            NavButton:hover {
                background-color: #2d2d2d;
            }
            NavButton:checked {
                background-color: #1976d2;
                color: white;
            }
        """)

class NavigationSidebar(QFrame):
    """侧边栏导航"""
    
    module_changed = pyqtSignal(str)  # module_id
    
    MODULES = [
        ("generate", "🎬", "字幕生成"),
        ("process_srt", "📝", "字幕处理"),
        ("status", "📊", "工作区状态"),
        ("execution", "⚙️", "阶段执行"),
        ("config", "🔧", "配置管理"),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(180)
        self.setStyleSheet("""
            NavigationSidebar {
                background-color: #1e1e1e;
                border-right: 1px solid #333;
            }
        """)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 20, 10, 20)
        
        # 标题
        title = QLabel("SemSub")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #1976d2; padding: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        subtitle = QLabel("智能字幕生成器")
        subtitle.setFont(QFont("Microsoft YaHei", 9))
        subtitle.setStyleSheet("color: #888; padding-bottom: 20px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        
        layout.addSpacing(20)
        
        # 导航按钮
        self.buttons = {}
        for module_id, icon, text in self.MODULES:
            btn = NavButton(text, icon)
            btn.clicked.connect(lambda checked, mid=module_id: self._on_button_clicked(mid))
            layout.addWidget(btn)
            self.buttons[module_id] = btn
        
        layout.addStretch()
        
        # 默认选中第一个
        self.set_active_module("generate")
    
    def _on_button_clicked(self, module_id: str):
        self.set_active_module(module_id)
        self.module_changed.emit(module_id)
    
    def set_active_module(self, module_id: str):
        """设置活动模块"""
        for mid, btn in self.buttons.items():
            btn.setChecked(mid == module_id)
