"""
SemSub Gradio GUI 模块

提供基于 Web 的字幕生成界面
"""

__version__ = "1.0.0"

from .app import create_app

__all__ = ["create_app"]
