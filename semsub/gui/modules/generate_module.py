"""
字幕生成模块
"""

from pathlib import Path
from typing import List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem,
    QProgressBar, QTextEdit, QGroupBox, QFormLayout,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QLineEdit, QTabWidget
)
from PyQt6.QtCore import Qt

from ...core.config import PipelineConfig
from ...core.config_manager import get_config_manager
from ...core.batch_scanner import VideoScanner


class GenerateModule(QWidget):
    """字幕生成模块"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = get_config_manager()
        self.config = self.config_manager.load()
        self.worker = None
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 1. 文件选择区域
        file_group = QGroupBox("视频文件")
        file_layout = QVBoxLayout(file_group)

        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(150)
        self.file_list.setAcceptDrops(True)
        self.file_list.dragEnterEvent = self._drag_enter
        self.file_list.dropEvent = self._drop
        file_layout.addWidget(self.file_list)

        self.file_count_label = QLabel("已选择: 0 个视频")
        file_layout.addWidget(self.file_count_label)

        btn_layout = QHBoxLayout()
        self.add_file_btn = QPushButton("➕ 添加文件")
        self.add_file_btn.clicked.connect(self._add_files)
        btn_layout.addWidget(self.add_file_btn)

        self.add_dir_btn = QPushButton("📁 添加目录")
        self.add_dir_btn.clicked.connect(self._add_directory)
        btn_layout.addWidget(self.add_dir_btn)

        self.clear_btn = QPushButton("🗑️ 清空")
        self.clear_btn.clicked.connect(self._clear_files)
        btn_layout.addWidget(self.clear_btn)

        btn_layout.addStretch()
        file_layout.addLayout(btn_layout)
        layout.addWidget(file_group)

        # 2. 配置面板
        self._setup_config_panel()
        layout.addWidget(self.config_tabs)

        # 3. 批量进度
        progress_group = QGroupBox("整体进度")
        progress_layout = QVBoxLayout(progress_group)

        self.batch_progress = QProgressBar()
        self.batch_progress.setRange(0, 100)
        progress_layout.addWidget(self.batch_progress)

        self.batch_status = QLabel("就绪")
        progress_layout.addWidget(self.batch_status)

        stats_layout = QHBoxLayout()
        self.completed_label = QLabel("已完成: 0")
        self.pending_label = QLabel("待处理: 0")
        stats_layout.addWidget(self.completed_label)
        stats_layout.addWidget(self.pending_label)
        stats_layout.addStretch()
        progress_layout.addLayout(stats_layout)
        layout.addWidget(progress_group)

        # 4. 当前视频进度
        video_progress_group = QGroupBox("当前视频进度")
        video_progress_layout = QVBoxLayout(video_progress_group)

        self.video_progress = QProgressBar()
        self.video_progress.setRange(0, 100)
        video_progress_layout.addWidget(self.video_progress)

        self.video_status = QLabel("等待开始...")
        video_progress_layout.addWidget(self.video_status)
        layout.addWidget(video_progress_group)

        # 5. 日志区域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        layout.addWidget(self.log_text)

        # 6. 操作按钮
        action_layout = QHBoxLayout()

        self.start_btn = QPushButton("▶️ 开始生成")
        self.start_btn.clicked.connect(self._start_generation)
        action_layout.addWidget(self.start_btn)

        self.cancel_btn = QPushButton("⏹️ 取消")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_generation)
        action_layout.addWidget(self.cancel_btn)

        self.save_config_btn = QPushButton("💾 保存配置")
        self.save_config_btn.clicked.connect(self._save_config)
        action_layout.addWidget(self.save_config_btn)

        action_layout.addStretch()
        layout.addLayout(action_layout)

    def _setup_config_panel(self):
        """设置配置面板"""
        self.config_tabs = QTabWidget()

        # 快速选项 Tab
        quick_tab = QWidget()
        quick_layout = QFormLayout(quick_tab)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["默认", "电影", "纪录片", "动画"])
        quick_layout.addRow("预设场景:", self.preset_combo)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["SRT", "VTT", "JSON"])
        quick_layout.addRow("输出格式:", self.format_combo)

        self.language_combo = QComboBox()
        self.language_combo.addItems(["自动检测", "中文", "English", "日本語"])
        quick_layout.addRow("语言:", self.language_combo)

        # 阶段范围
        range_layout = QHBoxLayout()
        self.from_stage = QComboBox()
        self.from_stage.addItems(["开始", "01_音频提取", "02_VAD分割", "03_ASR转录", "04_字幕优化", "05_LLM后处理"])
        self.to_stage = QComboBox()
        self.to_stage.addItems(["结束", "01_音频提取", "02_VAD分割", "03_ASR转录", "04_字幕优化", "05_LLM后处理"])
        range_layout.addWidget(QLabel("从:"))
        range_layout.addWidget(self.from_stage)
        range_layout.addWidget(QLabel("到:"))
        range_layout.addWidget(self.to_stage)
        range_layout.addStretch()
        quick_layout.addRow("阶段范围:", range_layout)

        # 处理选项
        self.skip_existing_cb = QCheckBox("跳过已存在字幕的视频 (--skip-existing)")
        quick_layout.addRow(self.skip_existing_cb)

        self.continue_on_error_cb = QCheckBox("遇到错误继续处理 (--continue-on-error)")
        quick_layout.addRow(self.continue_on_error_cb)

        self.force_cb = QCheckBox("强制重新执行 (--force)")
        quick_layout.addRow(self.force_cb)

        self.config_tabs.addTab(quick_tab, "⚡ 快速选项")

        # VAD Tab
        vad_tab = QWidget()
        vad_layout = QFormLayout(vad_tab)

        self.vad_threshold = QDoubleSpinBox()
        self.vad_threshold.setRange(0.1, 0.9)
        self.vad_threshold.setValue(0.5)
        self.vad_threshold.setSingleStep(0.1)
        vad_layout.addRow("阈值:", self.vad_threshold)

        self.min_speech_ms = QSpinBox()
        self.min_speech_ms.setRange(50, 1000)
        self.min_speech_ms.setValue(250)
        self.min_speech_ms.setSuffix(" ms")
        vad_layout.addRow("最小语音时长:", self.min_speech_ms)

        self.min_silence_ms = QSpinBox()
        self.min_silence_ms.setRange(100, 2000)
        self.min_silence_ms.setValue(500)
        self.min_silence_ms.setSuffix(" ms")
        vad_layout.addRow("最小静音时长:", self.min_silence_ms)

        self.config_tabs.addTab(vad_tab, "🔊 VAD")

        # 字幕 Tab
        subtitle_tab = QWidget()
        subtitle_layout = QFormLayout(subtitle_tab)

        self.max_chars = QSpinBox()
        self.max_chars.setRange(20, 100)
        self.max_chars.setValue(40)
        subtitle_layout.addRow("中文每行最大字符:", self.max_chars)

        self.max_duration = QDoubleSpinBox()
        self.max_duration.setRange(2.0, 10.0)
        self.max_duration.setValue(6.0)
        self.max_duration.setSuffix(" 秒")
        subtitle_layout.addRow("最大显示时长:", self.max_duration)

        self.config_tabs.addTab(subtitle_tab, "📝 字幕")

        # LLM Tab
        llm_tab = QWidget()
        llm_layout = QFormLayout(llm_tab)

        self.llm_enabled = QCheckBox("启用大模型后处理")
        llm_layout.addRow(self.llm_enabled)

        self.llm_base_url = QLineEdit()
        self.llm_base_url.setPlaceholderText("https://api.deepseek.com/v1")
        llm_layout.addRow("Base URL:", self.llm_base_url)

        self.llm_api_key = QLineEdit()
        self.llm_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        llm_layout.addRow("API Key:", self.llm_api_key)

        self.llm_model = QComboBox()
        self.llm_model.addItems(["deepseek-chat", "moonshot-v1-8k", "qwen-turbo"])
        self.llm_model.setEditable(True)
        llm_layout.addRow("模型:", self.llm_model)

        self.llm_mode = QComboBox()
        self.llm_mode.addItems(["仅纠错", "翻译", "双语"])
        llm_layout.addRow("输出模式:", self.llm_mode)

        self.config_tabs.addTab(llm_tab, "🤖 LLM")

    def _load_config(self):
        """加载配置到 UI"""
        self.vad_threshold.setValue(self.config.vad.threshold)
        self.min_speech_ms.setValue(self.config.vad.min_speech_duration_ms)
        self.min_silence_ms.setValue(self.config.vad.min_silence_duration_ms)
        self.max_chars.setValue(self.config.subtitle.max_chars)
        self.max_duration.setValue(self.config.subtitle.max_duration)
        self.llm_enabled.setChecked(self.config.llm.enabled)
        self.llm_base_url.setText(self.config.llm.base_url or "")
        self.llm_api_key.setText(self.config.llm.api_key or "")
        if self.config.llm.model:
            self.llm_model.setCurrentText(self.config.llm.model)

    def _update_config(self):
        """从 UI 更新配置"""
        self.config.vad.threshold = self.vad_threshold.value()
        self.config.vad.min_speech_duration_ms = self.min_speech_ms.value()
        self.config.vad.min_silence_duration_ms = self.min_silence_ms.value()
        self.config.subtitle.max_chars = self.max_chars.value()
        self.config.subtitle.max_duration = self.max_duration.value()
        self.config.llm.enabled = self.llm_enabled.isChecked()
        self.config.llm.base_url = self.llm_base_url.text() or None
        self.config.llm.api_key = self.llm_api_key.text() or None
        self.config.llm.model = self.llm_model.currentText() or None

        mode_map = {"仅纠错": "correct", "翻译": "translate", "双语": "bilingual"}
        self.config.llm.output_mode = mode_map.get(self.llm_mode.currentText(), "correct")

        lang_map = {"自动检测": None, "中文": "Chinese", "English": "English", "日本語": "Japanese"}
        self.config.asr.language = lang_map.get(self.language_combo.currentText())

        self.config.output.format = self.format_combo.currentText().lower()

    def _save_config(self):
        """保存配置"""
        self._update_config()
        self.config_manager.save_user_config(self.config)
        self._log("✓ 配置已保存")

    def _drag_enter(self, event):
        """拖拽进入"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def _drop(self, event):
        """拖拽放下"""
        urls = event.mimeData().urls()
        paths = [Path(url.toLocalFile()) for url in urls if url.toLocalFile()]
        if paths:
            scanner = VideoScanner()
            tasks = scanner.scan(paths, recursive=True)
            self._add_videos([Path(t.video_path) for t in tasks])

    def _add_files(self):
        """添加文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择视频文件", "",
            "视频文件 (*.mp4 *.mkv *.avi *.mov *.webm);;所有文件 (*)"
        )
        if files:
            self._add_videos([Path(f) for f in files])

    def _add_directory(self):
        """添加目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择视频目录")
        if dir_path:
            scanner = VideoScanner()
            tasks = scanner.scan([Path(dir_path)], recursive=True)
            self._add_videos([Path(t.video_path) for t in tasks])

    def _add_videos(self, paths: List[Path]):
        """添加视频到列表"""
        for path in paths:
            exists = any(
                self.file_list.item(i).data(Qt.ItemDataRole.UserRole) == str(path)
                for i in range(self.file_list.count())
            )
            if not exists:
                item = QListWidgetItem(f"📹 {path.name}")
                item.setData(Qt.ItemDataRole.UserRole, str(path))
                item.setToolTip(str(path))
                self.file_list.addItem(item)
        self._update_file_count()

    def _clear_files(self):
        """清空列表"""
        self.file_list.clear()
        self._update_file_count()

    def _update_file_count(self):
        """更新文件计数"""
        count = self.file_list.count()
        self.file_count_label.setText(f"已选择: {count} 个视频")

    def _start_generation(self):
        """开始生成"""
        video_paths = [
            Path(self.file_list.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(self.file_list.count())
        ]

        if not video_paths:
            QMessageBox.warning(self, "警告", "请先添加视频文件")
            return

        self._update_config()

        # 创建 tasks
        scanner = VideoScanner()
        tasks = scanner.scan(video_paths, recursive=False)

        # 创建 worker
        from ..workers.batch_worker import BatchWorker
        self.worker = BatchWorker(
            self.config,
            tasks,
            continue_on_error=self.continue_on_error_cb.isChecked()
        )

        # 连接信号
        self.worker.batch_started.connect(self._on_batch_started)
        self.worker.batch_progress.connect(self._on_batch_progress)
        self.worker.batch_finished.connect(self._on_batch_finished)
        self.worker.batch_error.connect(self._on_batch_error)
        self.worker.video_started.connect(self._on_video_started)
        self.worker.video_progress.connect(self._on_video_progress)
        self.worker.video_finished.connect(self._on_video_finished)
        self.worker.log.connect(self._log)

        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.worker.start()

    def _cancel_generation(self):
        """取消生成"""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self._log("正在取消...")
            self.cancel_btn.setEnabled(False)

    def _on_batch_started(self, total: int):
        self.batch_status.setText(f"开始处理 {total} 个视频...")

    def _on_batch_progress(self, current: int, total: int, name: str):
        percent = int((current / total) * 100) if total > 0 else 0
        self.batch_progress.setValue(percent)
        self.batch_status.setText(f"处理中: {name} ({current+1}/{total})")
        self.completed_label.setText(f"已完成: {current}")
        self.pending_label.setText(f"待处理: {total - current}")

    def _on_batch_finished(self, success: bool, completed: int, failed: int, total: int):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        if success:
            QMessageBox.information(self, "完成", f"批量处理完成！\n成功: {completed} 个\n失败: {failed} 个")
        else:
            QMessageBox.warning(self, "中断", f"批量处理中断\n成功: {completed} 个\n失败: {failed} 个")

    def _on_batch_error(self, error: str):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        QMessageBox.critical(self, "错误", error)

    def _on_video_started(self, path: str, index: int, total: int):
        self.video_status.setText(f"正在处理: {Path(path).name}")

    def _on_video_progress(self, percent: int, message: str):
        self.video_progress.setValue(percent)
        if message:
            self.video_status.setText(message)

    def _on_video_finished(self, path: str, success: bool, output: str):
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == path:
                prefix = "✅" if success else "❌"
                item.setText(f"{prefix} {item.text()[2:]}")
                break

    def _log(self, message: str):
        """添加日志"""
        self.log_text.append(message)
