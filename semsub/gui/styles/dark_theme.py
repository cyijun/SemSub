"""
深色主题样式
"""

DARK_THEME_STYLESHEET = """
QMainWindow {
    background-color: #1e1e1e;
}

QWidget {
    background-color: #2d2d2d;
    color: #e0e0e0;
    font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
}

QGroupBox {
    border: 1px solid #444;
    border-radius: 6px;
    margin-top: 12px;
    font-weight: bold;
    color: #1976d2;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}

QPushButton {
    background-color: #1976d2;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #1565c0;
}

QPushButton:pressed {
    background-color: #0d47a1;
}

QPushButton:disabled {
    background-color: #555;
    color: #888;
}

QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #1e1e1e;
    border: 1px solid #444;
    border-radius: 4px;
    padding: 6px;
    color: #e0e0e0;
}

QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border-color: #1976d2;
}

QListWidget {
    background-color: #1e1e1e;
    border: 1px solid #444;
    border-radius: 4px;
    padding: 5px;
}

QListWidget::item {
    padding: 5px;
    border-radius: 3px;
}

QListWidget::item:selected {
    background-color: #1976d2;
}

QProgressBar {
    border: 1px solid #444;
    border-radius: 4px;
    text-align: center;
    background-color: #1e1e1e;
}

QProgressBar::chunk {
    background-color: #1976d2;
    border-radius: 3px;
}

QTabWidget::pane {
    border: 1px solid #444;
    border-radius: 4px;
    background-color: #2d2d2d;
}

QTabBar::tab {
    background-color: #333;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background-color: #1976d2;
}

QTabBar::tab:hover:!selected {
    background-color: #444;
}

QTreeWidget {
    background-color: #1e1e1e;
    border: 1px solid #444;
    border-radius: 4px;
}

QTreeWidget::item {
    padding: 5px;
}

QTreeWidget::item:selected {
    background-color: #1976d2;
}

QCheckBox {
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #444;
    border-radius: 3px;
    background-color: #1e1e1e;
}

QCheckBox::indicator:checked {
    background-color: #1976d2;
    border-color: #1976d2;
}

QLabel {
    color: #e0e0e0;
}

QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 12px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background-color: #444;
    border-radius: 6px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #555;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QWizard {
    background-color: #2d2d2d;
}

QWizardPage {
    background-color: #2d2d2d;
}
"""


def apply_dark_theme(app):
    """应用深色主题"""
    app.setStyleSheet(DARK_THEME_STYLESHEET)
