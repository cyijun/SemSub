"""
阶段流程图组件
显示 5 个阶段的流程图样式状态
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont

from ...core.state_models import StageStatus, PipelineStatus


class StageCard(QFrame):
    """单个阶段卡片"""

    clicked = pyqtSignal(str)  # stage_id

    STAGE_NAMES = {
        "01_audio_extract": "音频\n提取",
        "02_vad_split": "VAD\n分割",
        "03_asr_transcribe": "ASR\n转录",
        "04_subtitle_optimize": "字幕\n优化",
        "05_llm_postprocess": "LLM\n后处理",
    }

    STATUS_COLORS = {
        StageStatus.PENDING: ("#9e9e9e", "#e0e0e0"),  # 灰色
        StageStatus.RUNNING: ("#1976d2", "#bbdefb"),  # 蓝色
        StageStatus.COMPLETED: ("#388e3c", "#c8e6c9"),  # 绿色
        StageStatus.FAILED: ("#d32f2f", "#ffcdd2"),  # 红色
        StageStatus.SKIPPED: ("#757575", "#eeeeee"),  # 深灰
    }

    def __init__(self, stage_id: str, parent=None):
        super().__init__(parent)
        self.stage_id = stage_id
        self.status = StageStatus.PENDING
        self.duration = ""
        self.progress = 0

        self.setFixedSize(100, 80)
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setSpacing(2)

        # 阶段名称
        self.name_label = QLabel(self.STAGE_NAMES.get(stage_id, stage_id))
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setFont(QFont("Microsoft YaHei", 9))
        layout.addWidget(self.name_label)

        # 状态/时长
        self.status_label = QLabel("等待中")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("Microsoft YaHei", 8))
        layout.addWidget(self.status_label)

        self._update_style()

    def set_status(self, status: StageStatus, duration: str = "", progress: float = 0):
        """更新状态"""
        self.status = status
        self.duration = duration
        self.progress = progress

        status_text = {
            StageStatus.PENDING: "等待中",
            StageStatus.RUNNING: f"{progress:.0f}%" if progress > 0 else "运行中",
            StageStatus.COMPLETED: duration or "完成",
            StageStatus.FAILED: "失败",
            StageStatus.SKIPPED: "跳过",
        }
        self.status_label.setText(status_text.get(status, "未知"))
        self._update_style()

    def _update_style(self):
        """更新样式"""
        border_color, bg_color = self.STATUS_COLORS.get(self.status, ("#9e9e9e", "#e0e0e0"))
        self.setStyleSheet(f"""
            StageCard {{
                border: 2px solid {border_color};
                border-radius: 8px;
                background-color: {bg_color};
            }}
            QLabel {{
                background: transparent;
                color: {border_color};
            }}
        """)

    def mousePressEvent(self, event):
        self.clicked.emit(self.stage_id)


class StageFlowWidget(QWidget):
    """阶段流程图组件"""

    stage_selected = pyqtSignal(str)  # stage_id

    STAGE_ORDER = [
        "01_audio_extract",
        "02_vad_split",
        "03_asr_transcribe",
        "04_subtitle_optimize",
        "05_llm_postprocess",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setSpacing(10)

        self.cards = {}
        for i, stage_id in enumerate(self.STAGE_ORDER):
            # 阶段卡片
            card = StageCard(stage_id)
            card.clicked.connect(self._on_card_clicked)
            layout.addWidget(card)
            self.cards[stage_id] = card

            # 箭头（除了最后一个）
            if i < len(self.STAGE_ORDER) - 1:
                arrow = QLabel("▶")
                arrow.setStyleSheet("color: #bdbdbd; font-size: 14px;")
                layout.addWidget(arrow)

        layout.addStretch()

    def _on_card_clicked(self, stage_id: str):
        self.stage_selected.emit(stage_id)

    def update_status(self, status: PipelineStatus):
        """更新状态显示"""
        for stage_id, (stage_status, duration_sec) in status.stage_summary.items():
            if stage_id in self.cards:
                duration_str = ""
                if duration_sec:
                    minutes = duration_sec // 60
                    seconds = duration_sec % 60
                    duration_str = f"{minutes:02d}:{seconds:02d}"

                progress = 0
                if stage_status == StageStatus.RUNNING and status.current_stage == stage_id:
                    # 从 PipelineStatus 获取进度
                    progress = status.progress_percent

                self.cards[stage_id].set_status(stage_status, duration_str, progress)
