"""
Gradio GUI 页面模块
"""

from .home import create_home_page
from .batch import create_batch_page
from .srt_process import create_srt_page
from .workspaces import create_workspaces_page
from .settings import create_settings_page

__all__ = [
    "create_home_page",
    "create_batch_page",
    "create_srt_page",
    "create_workspaces_page",
    "create_settings_page",
]
