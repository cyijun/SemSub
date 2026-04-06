"""
主窗口
"""

from pathlib import Path
from typing import List
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QProgressBar,
    QTextEdit, QComboBox, QTabWidget, QSpinBox,
    QDoubleSpinBox, QCheckBox, QLineEdit, QMessageBox,
    QGroupBox, QFormLayout, QListWidget, QListWidgetItem
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

        # 1. 文件选择区域 - 改为批量模式
        file_group = QGroupBox("视频文件")
        file_layout = QVBoxLayout(file_group)

        # 文件列表
        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(150)
        self.file_list.setAcceptDrops(True)
        self.file_list.dragEnterEvent = self._drag_enter_event
        self.file_list.dropEvent = self._drop_event
        file_layout.addWidget(self.file_list)

        # 统计标签
        self.file_count_label = QLabel("已选择: 0 个视频")
        file_layout.addWidget(self.file_count_label)

        # 按钮行
        btn_layout = QHBoxLayout()
        self.add_file_btn = QPushButton("添加文件")
        self.add_file_btn.clicked.connect(self._add_files)
        btn_layout.addWidget(self.add_file_btn)

        self.add_dir_btn = QPushButton("添加目录")
        self.add_dir_btn.clicked.connect(self._add_directory)
        btn_layout.addWidget(self.add_dir_btn)

        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self._clear_files)
        btn_layout.addWidget(self.clear_btn)

        btn_layout.addStretch()
        file_layout.addLayout(btn_layout)

        layout.addWidget(file_group)

        # 2. 配置面板（Tab）
        self.tabs = QTabWidget()
        self._setup_basic_tab()
        self._setup_vad_tab()
        self._setup_subtitle_tab()
        self._setup_llm_tab()
        layout.addWidget(self.tabs)

        # 3. 批量进度条（新增）
        batch_progress_group = QGroupBox("整体进度")
        batch_layout = QVBoxLayout(batch_progress_group)

        self.batch_progress_bar = QProgressBar()
        self.batch_progress_bar.setRange(0, 100)
        self.batch_progress_bar.setValue(0)
        batch_layout.addWidget(self.batch_progress_bar)

        self.batch_status_label = QLabel("就绪")
        batch_layout.addWidget(self.batch_status_label)

        # 统计信息
        stats_layout = QHBoxLayout()
        self.completed_label = QLabel("已完成: 0")
        self.pending_label = QLabel("待处理: 0")
        self.eta_label = QLabel("预计剩余: --")
        stats_layout.addWidget(self.completed_label)
        stats_layout.addWidget(self.pending_label)
        stats_layout.addWidget(self.eta_label)
        stats_layout.addStretch()
        batch_layout.addLayout(stats_layout)

        layout.addWidget(batch_progress_group)

        # 4. 当前视频进度条（原有）
        video_progress_group = QGroupBox("当前视频进度")
        video_layout = QVBoxLayout(video_progress_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        video_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("等待开始...")
        video_layout.addWidget(self.status_label)

        layout.addWidget(video_progress_group)

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
        paths = []
        for url in urls:
            path = url.toLocalFile()
            if path:
                paths.append(Path(path))

        if paths:
            # 如果是目录，扫描；如果是文件，直接添加
            from ...core.batch_scanner import VideoScanner
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
            from ...core.batch_scanner import VideoScanner
            scanner = VideoScanner()
            tasks = scanner.scan([Path(dir_path)], recursive=True)
            self._add_videos([Path(t.video_path) for t in tasks])

    def _add_videos(self, paths: List[Path]):
        """添加视频到列表"""
        for path in paths:
            # 去重检查
            exists = False
            for i in range(self.file_list.count()):
                if self.file_list.item(i).data(Qt.ItemDataRole.UserRole) == str(path):
                    exists = True
                    break
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

    def _on_preset_changed(self, preset: str):
        """预设改变"""
        if preset == "电影":
            self.min_silence_ms.setValue(300)
        elif preset == "纪录片":
            self.min_silence_ms.setValue(800)
        elif preset == "动画":
            self.min_silence_ms.setValue(200)

    def _start_generation(self):
        """开始批量生成"""
        # 收集所有视频路径
        video_paths = []
        for i in range(self.file_list.count()):
            path = self.file_list.item(i).data(Qt.ItemDataRole.UserRole)
            if path:
                video_paths.append(Path(path))

        if not video_paths:
            QMessageBox.warning(self, "警告", "请先添加视频文件")
            return

        # 更新配置
        self._update_config()

        # 创建 VideoTask 列表
        from ...core.batch_scanner import VideoScanner
        scanner = VideoScanner()
        tasks = scanner.scan(video_paths, recursive=False)  # 已经扫描过了

        # 创建批量 worker
        from .workers.batch_worker import BatchWorker
        self.worker = BatchWorker(self.config, tasks)

        # 连接信号
        self.worker.batch_started.connect(self._on_batch_started)
        self.worker.batch_progress.connect(self._on_batch_progress)
        self.worker.batch_finished.connect(self._on_batch_finished)
        self.worker.batch_error.connect(self._on_batch_error)
        self.worker.video_started.connect(self._on_video_started)
        self.worker.video_progress.connect(self._on_video_progress)
        self.worker.video_finished.connect(self._on_video_finished)
        self.worker.log.connect(self._log)

        # 更新 UI
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.batch_progress_bar.setValue(0)
        self.progress_bar.setValue(0)

        # 启动
        self.worker.start()
        self._log(f"开始批量处理 {len(tasks)} 个视频...")

    def _cancel_generation(self):
        """取消生成"""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self._log("正在取消...")
            # 立即禁用取消按钮，防止重复点击
            self.cancel_btn.setEnabled(False)
            self.status_label.setText("正在取消...")

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

    def _on_save_config_clicked(self):
        """保存配置按钮点击"""
        self._save_config()
        self._log(f"✓ 配置已保存到: {self.config_manager.user_config_file}")
        QMessageBox.information(self, "保存成功", "配置已保存为用户默认配置")

    def _on_batch_started(self, total_count: int):
        """批量处理开始"""
        self.batch_status_label.setText(f"开始处理 {total_count} 个视频...")

    def _on_batch_progress(self, current: int, total: int, video_name: str):
        """批量进度更新"""
        percent = int((current / total) * 100) if total > 0 else 0
        self.batch_progress_bar.setValue(percent)
        self.batch_status_label.setText(f"处理中: {video_name} ({current+1}/{total})")

        # 更新统计
        self.completed_label.setText(f"已完成: {current}")
        self.pending_label.setText(f"待处理: {total - current}")

    def _on_video_started(self, video_path: str, index: int, total: int):
        """开始处理单个视频"""
        self.status_label.setText(f"正在处理: {Path(video_path).name}")
        # 高亮当前处理的项
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == video_path:
                self.file_list.setCurrentItem(item)
                break

    def _on_video_progress(self, percent: int, message: str):
        """单个视频进度"""
        self.progress_bar.setValue(percent)
        if message:
            self.status_label.setText(message)

    def _on_video_finished(self, video_path: str, success: bool, output_path: str):
        """单个视频完成"""
        # 更新列表项状态
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == video_path:
                prefix = "✓" if success else "✗"
                item.setText(f"{prefix} {item.text()[2:]}")  # 替换原有前缀
                break

    def _on_batch_finished(self, success: bool, completed: int, failed: int, total: int):
        """批量处理完成"""
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        if success:
            self.batch_progress_bar.setValue(100)
            self.batch_status_label.setText(f"完成: {completed}/{total} 成功")
            QMessageBox.information(self, "完成", f"批量处理完成！\n成功: {completed} 个\n失败: {failed} 个")
        else:
            self.batch_status_label.setText(f"中断: {completed} 成功, {failed} 失败")
            QMessageBox.warning(self, "中断", f"批量处理中断\n成功: {completed} 个\n失败: {failed} 个")

    def _on_batch_error(self, error_msg: str):
        """批量处理错误"""
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._log(f"✗ 错误: {error_msg}")
        QMessageBox.critical(self, "错误", error_msg)

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
