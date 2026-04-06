"""
主窗口
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QProgressBar,
    QTextEdit, QComboBox, QTabWidget, QSpinBox,
    QDoubleSpinBox, QCheckBox, QLineEdit, QMessageBox,
    QGroupBox, QFormLayout
)
from PyQt6.QtCore import Qt, QThread

from ..core.config import PipelineConfig
from ..core.pipeline import SubtitlePipeline
from ..core.config_manager import get_config_manager
from .workers.pipeline_worker import PipelineWorker


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SemSub - 智能字幕生成器")
        self.setMinimumSize(800, 600)

        self.config_manager = get_config_manager()
        self.config = self.config_manager.load()  # 加载保存的配置
        self.worker = None

        self._setup_ui()
        self._load_config_to_ui()  # 将配置加载到 UI

    def _setup_ui(self):
        """设置 UI"""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(15)

        # 1. 文件选择
        file_group = QGroupBox("视频文件")
        file_layout = QHBoxLayout(file_group)
        self.file_label = QLabel("请拖拽视频文件到这里，或点击选择")
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_label.setStyleSheet("padding: 30px; border: 2px dashed #aaa;")
        self.file_label.setAcceptDrops(True)
        self.file_label.dragEnterEvent = self._drag_enter_event
        self.file_label.dropEvent = self._drop_event
        file_layout.addWidget(self.file_label)

        self.select_btn = QPushButton("选择文件")
        self.select_btn.clicked.connect(self._select_file)
        file_layout.addWidget(self.select_btn)

        layout.addWidget(file_group)

        # 2. 配置面板（Tab）
        self.tabs = QTabWidget()
        self._setup_basic_tab()
        self._setup_vad_tab()
        self._setup_subtitle_tab()
        self._setup_llm_tab()
        layout.addWidget(self.tabs)

        # 3. 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)

        # 4. 日志区域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        layout.addWidget(self.log_text)

        # 5. 按钮
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始生成")
        self.start_btn.clicked.connect(self._start_generation)
        btn_layout.addWidget(self.start_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_generation)
        btn_layout.addWidget(self.cancel_btn)

        self.save_config_btn = QPushButton("保存配置")
        self.save_config_btn.setToolTip("保存当前设置为默认配置")
        self.save_config_btn.clicked.connect(self._on_save_config_clicked)
        btn_layout.addWidget(self.save_config_btn)

        layout.addLayout(btn_layout)

    def _setup_basic_tab(self):
        """基本设置 Tab"""
        tab = QWidget()
        layout = QFormLayout(tab)

        # 预设场景
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["默认", "电影", "纪录片", "动画"])
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        layout.addRow("预设场景:", self.preset_combo)

        # 输出格式
        self.format_combo = QComboBox()
        self.format_combo.addItems(["SRT", "VTT", "JSON"])
        layout.addRow("输出格式:", self.format_combo)

        # 语言
        self.language_combo = QComboBox()
        self.language_combo.addItems(["自动检测", "中文", "English", "日本語"])
        layout.addRow("语言:", self.language_combo)

        self.tabs.addTab(tab, "基本")

    def _setup_vad_tab(self):
        """VAD 设置 Tab"""
        tab = QWidget()
        layout = QFormLayout(tab)

        # 阈值
        self.vad_threshold = QDoubleSpinBox()
        self.vad_threshold.setRange(0.1, 0.9)
        self.vad_threshold.setSingleStep(0.1)
        self.vad_threshold.setValue(0.5)
        layout.addRow("阈值:", self.vad_threshold)

        # 最小语音时长
        self.min_speech_ms = QSpinBox()
        self.min_speech_ms.setRange(50, 1000)
        self.min_speech_ms.setSingleStep(50)
        self.min_speech_ms.setValue(250)
        self.min_speech_ms.setSuffix(" ms")
        layout.addRow("最小语音时长:", self.min_speech_ms)

        # 最小静音时长
        self.min_silence_ms = QSpinBox()
        self.min_silence_ms.setRange(100, 2000)
        self.min_silence_ms.setSingleStep(100)
        self.min_silence_ms.setValue(500)
        self.min_silence_ms.setSuffix(" ms")
        layout.addRow("最小静音时长:", self.min_silence_ms)

        self.tabs.addTab(tab, "VAD")

    def _setup_subtitle_tab(self):
        """字幕设置 Tab"""
        tab = QWidget()
        layout = QFormLayout(tab)

        # 最大字符数
        self.max_chars = QSpinBox()
        self.max_chars.setRange(20, 100)
        self.max_chars.setValue(40)
        layout.addRow("中文每行最大字符:", self.max_chars)

        # 最大时长
        self.max_duration = QDoubleSpinBox()
        self.max_duration.setRange(2.0, 10.0)
        self.max_duration.setSingleStep(0.5)
        self.max_duration.setValue(6.0)
        self.max_duration.setSuffix(" 秒")
        layout.addRow("最大显示时长:", self.max_duration)

        self.tabs.addTab(tab, "字幕")

    def _setup_llm_tab(self):
        """LLM 设置 Tab"""
        tab = QWidget()
        layout = QFormLayout(tab)

        # 启用 LLM
        self.llm_enabled = QCheckBox("启用大模型后处理")
        layout.addRow(self.llm_enabled)

        # Base URL
        self.llm_base_url = QLineEdit()
        self.llm_base_url.setPlaceholderText("https://api.deepseek.com/v1")
        layout.addRow("Base URL:", self.llm_base_url)

        # API Key
        self.llm_api_key = QLineEdit()
        self.llm_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("API Key:", self.llm_api_key)

        # 模型
        self.llm_model = QComboBox()
        self.llm_model.addItems(["deepseek-chat", "moonshot-v1-8k", "qwen-turbo"])
        self.llm_model.setEditable(True)
        layout.addRow("模型:", self.llm_model)

        # 输出模式
        self.llm_mode = QComboBox()
        self.llm_mode.addItems(["仅纠错", "翻译", "双语"])
        layout.addRow("输出模式:", self.llm_mode)

        self.tabs.addTab(tab, "LLM")

    def _load_config_to_ui(self):
        """将配置加载到 UI"""
        # VAD
        self.vad_threshold.setValue(self.config.vad.threshold)
        self.min_speech_ms.setValue(self.config.vad.min_speech_duration_ms)
        self.min_silence_ms.setValue(self.config.vad.min_silence_duration_ms)

        # 字幕
        self.max_chars.setValue(self.config.subtitle.max_chars)
        self.max_duration.setValue(self.config.subtitle.max_duration)

        # LLM
        self.llm_enabled.setChecked(self.config.llm.enabled)
        self.llm_base_url.setText(self.config.llm.base_url)
        self.llm_api_key.setText(self.config.llm.api_key)
        if self.config.llm.model:
            index = self.llm_model.findText(self.config.llm.model)
            if index >= 0:
                self.llm_model.setCurrentIndex(index)
            else:
                self.llm_model.setCurrentText(self.config.llm.model)

        mode_map = {"correct": "仅纠错", "translate": "翻译", "bilingual": "双语"}
        self.llm_mode.setCurrentText(mode_map.get(self.config.llm.output_mode, "仅纠错"))

        # 输出格式
        format_text = self.config.output.format.upper()
        index = self.format_combo.findText(format_text)
        if index >= 0:
            self.format_combo.setCurrentIndex(index)

        # 语言
        lang_map = {None: "自动检测", "Chinese": "中文", "English": "English", "Japanese": "日本語"}
        self.language_combo.setCurrentText(lang_map.get(self.config.asr.language, "自动检测"))

    def _save_config(self):
        """保存配置"""
        self._update_config()
        self.config_manager.save_user_config(self.config)

    def _drag_enter_event(self, event):
        """拖拽进入"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def _drop_event(self, event):
        """拖拽放下"""
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm')):
                self._set_video_file(file_path)

    def _select_file(self):
        """选择文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择视频文件", "",
            "视频文件 (*.mp4 *.mkv *.avi *.mov *.webm);;所有文件 (*)"
        )
        if file_path:
            self._set_video_file(file_path)

    def _set_video_file(self, path: str):
        """设置视频文件"""
        self.file_label.setText(f"已选择: {Path(path).name}")
        self.file_label.setProperty("file_path", path)
        self._log(f"已选择文件: {path}")

    def _on_preset_changed(self, preset: str):
        """预设改变"""
        if preset == "电影":
            self.min_silence_ms.setValue(300)
        elif preset == "纪录片":
            self.min_silence_ms.setValue(800)
        elif preset == "动画":
            self.min_silence_ms.setValue(200)

    def _start_generation(self):
        """开始生成"""
        file_path = self.file_label.property("file_path")
        if not file_path:
            QMessageBox.warning(self, "警告", "请先选择视频文件")
            return

        # 更新配置
        self._update_config()

        # 创建 worker
        self.worker = PipelineWorker(self.config, Path(file_path))
        self.worker.progress.connect(self._on_progress)
        self.worker.log.connect(self._log)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.cancelled.connect(self._on_cancelled)

        # 更新 UI
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)

        # 启动
        self.worker.start()
        self._log("开始生成字幕...")

    def _cancel_generation(self):
        """取消生成"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self._log("正在取消...")
            # 立即禁用取消按钮，防止重复点击
            self.cancel_btn.setEnabled(False)
            self.status_label.setText("正在取消...")

    def _on_cancelled(self):
        """取消完成"""
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("已取消")
        self._log("✓ 已取消")

    def _update_config(self):
        """更新配置"""
        # VAD
        self.config.vad.threshold = self.vad_threshold.value()
        self.config.vad.min_speech_duration_ms = self.min_speech_ms.value()
        self.config.vad.min_silence_duration_ms = self.min_silence_ms.value()

        # 字幕
        self.config.subtitle.max_chars = self.max_chars.value()
        self.config.subtitle.max_duration = self.max_duration.value()

        # 输出
        self.config.output.format = self.format_combo.currentText().lower()

        # 语言
        lang_map = {"自动检测": None, "中文": "Chinese", "English": "English", "日本語": "Japanese"}
        self.config.asr.language = lang_map.get(self.language_combo.currentText())

        # LLM
        self.config.llm.enabled = self.llm_enabled.isChecked()
        self.config.llm.base_url = self.llm_base_url.text()
        self.config.llm.api_key = self.llm_api_key.text()
        self.config.llm.model = self.llm_model.currentText()
        mode_map = {"仅纠错": "correct", "翻译": "translate", "双语": "bilingual"}
        self.config.llm.output_mode = mode_map.get(self.llm_mode.currentText(), "correct")

    def _on_progress(self, percent: int, message: str):
        """进度更新"""
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)

    def _on_finished(self, output_path: str):
        """完成"""
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setValue(100)
        self._log(f"✓ 完成！输出: {output_path}")
        QMessageBox.information(self, "完成", f"字幕已生成:\n{output_path}")

    def _on_error(self, error_msg: str):
        """错误"""
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._log(f"✗ 错误: {error_msg}")
        QMessageBox.critical(self, "错误", error_msg)

    def _on_save_config_clicked(self):
        """保存配置按钮点击"""
        self._save_config()
        self._log(f"✓ 配置已保存到: {self.config_manager.user_config_file}")
        QMessageBox.information(self, "保存成功", "配置已保存为用户默认配置")

    def closeEvent(self, event):
        """关闭窗口时保存配置"""
        try:
            self._save_config()
        except Exception:
            pass  # 忽略保存错误
        event.accept()

    def _log(self, message: str):
        """添加日志"""
        self.log_text.append(message)
