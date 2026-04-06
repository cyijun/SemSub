"""
GUI 应用入口
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QFontDatabase
from .main_window import MainWindow


def setup_fonts():
    """设置中文字体"""
    # 尝试加载系统中文字体（按优先级）
    chinese_fonts = [
        "Microsoft YaHei UI",  # Windows 微软雅黑
        "Microsoft YaHei",
        "SimHei",              # Windows 黑体
        "PingFang SC",         # macOS 苹方
        "Heiti SC",            # macOS 黑体
        "Noto Sans CJK SC",    # Linux Noto
        "WenQuanYi Micro Hei", # Linux 文泉驿
        "WenQuanYi Zen Hei",
        "Source Han Sans SC",  # 思源黑体
        "DejaVu Sans",         # 通用备用
    ]

    # 使用 QFontDatabase 的静态方法获取可用字体
    available_families = QFontDatabase.families()

    # 查找可用的中文字体
    selected_font = None
    for font_name in chinese_fonts:
        if font_name in available_families:
            selected_font = font_name
            print(f"使用字体: {font_name}")
            break

    if selected_font:
        font = QFont(selected_font, 10)
        QApplication.setFont(font)
    else:
        print("警告: 未找到合适的中文字体，使用系统默认字体")
        # 尝试设置通用字体并启用字体回退
        font = QFont("Sans Serif", 10)
        QApplication.setFont(font)


def main():
    """启动 GUI 应用"""
    app = QApplication(sys.argv)
    app.setApplicationName("SemSub")
    app.setApplicationVersion("1.0.0")

    # 设置中文字体
    setup_fonts()

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
