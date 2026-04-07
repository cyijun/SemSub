"""
字幕处理模块 - 独立的 SRT 文件 LLM 后处理
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QProgressBar,
    QTextEdit, QGroupBox, QFormLayout,
    QComboBox, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt

from ...core.config import LLMProcessConfig
from ...core.config_manager import get_config_manager
from ...core.prompts import PromptManager


class ProcessSRTModule(QWidget):
    """SRT 字幕处理模块"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = get_config_manager()
        self.pipeline_config = self.config_manager.load()
        self.worker = None
        self.prompt_manager = PromptManager()
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 1. 文件选择区域
        file_group = QGroupBox("文件选择")
        file_layout = QFormLayout(file_group)

        # 输入文件
        input_layout = QHBoxLayout()
        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText("选择 SRT 字幕文件...")
        input_layout.addWidget(self.input_path)

        self.browse_input_btn = QPushButton("浏览...")
        self.browse_input_btn.clicked.connect(self._browse_input)
        input_layout.addWidget(self.browse_input_btn)
        file_layout.addRow("输入文件:", input_layout)

        # 输出文件
        output_layout = QHBoxLayout()
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("自动保存为 .processed.srt...")
        output_layout.addWidget(self.output_path)

        self.browse_output_btn = QPushButton("浏览...")
        self.browse_output_btn.clicked.connect(self._browse_output)
        output_layout.addWidget(self.browse_output_btn)
        file_layout.addRow("输出文件:", output_layout)

        layout.addWidget(file_group)

        # 2. 处理选项
        options_group = QGroupBox("处理选项")
        options_layout = QFormLayout(options_group)

        # 处理模式
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("纠错优化", "correct")
        self.mode_combo.addItem("翻译", "translate")
        self.mode_combo.addItem("双语字幕", "bilingual")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        options_layout.addRow("处理模式:", self.mode_combo)

        # 提示词模板
        self.template_combo = QComboBox()
        self._load_templates()
        options_layout.addRow("提示词模板:", self.template_combo)

        # 目标语言（仅翻译模式显示）
        self.target_lang_combo = QComboBox()
        self.target_lang_combo.addItems(["English", "中文", "日本語", "한국어", "Français", "Deutsch", "Español"])
        self.target_lang_label = QLabel("目标语言:")
        options_layout.addRow(self.target_lang_label, self.target_lang_combo)

        layout.addWidget(options_group)

        # 3. LLM 配置
        llm_group = QGroupBox("LLM 配置")
        llm_layout = QFormLayout(llm_group)

        self.llm_base_url = QLineEdit()
        self.llm_base_url.setPlaceholderText("https://api.deepseek.com/v1")
        llm_layout.addRow("Base URL:", self.llm_base_url)

        self.llm_api_key = QLineEdit()
        self.llm_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        llm_layout.addRow("API Key:", self.llm_api_key)

        self.llm_model = QComboBox()
        self.llm_model.addItems(["deepseek-chat", "moonshot-v1-8k", "qwen-turbo", "gpt-3.5-turbo", "gpt-4"])
        self.llm_model.setEditable(True)
        llm_layout.addRow("模型:", self.llm_model)

        batch_layout = QHBoxLayout()
        self.batch_size = QComboBox()
        self.batch_size.addItems(["5", "10", "15", "20", "30"])
        self.batch_size.setCurrentText("10")
        batch_layout.addWidget(self.batch_size)
        batch_layout.addStretch()
        llm_layout.addRow("批次大小:", batch_layout)

        layout.addWidget(llm_group)

        # 4. 进度区域
        progress_group = QGroupBox("处理进度")
        progress_layout = QVBoxLayout(progress_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        progress_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("就绪")
        progress_layout.addWidget(self.status_label)

        layout.addWidget(progress_group)

        # 5. 日志区域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        layout.addWidget(self.log_text)

        # 6. 操作按钮
        action_layout = QHBoxLayout()

        self.start_btn = QPushButton("▶️ 开始处理")
        self.start_btn.clicked.connect(self._start_processing)
        action_layout.addWidget(self.start_btn)

        self.cancel_btn = QPushButton("⏹️ 取消")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_processing)
        action_layout.addWidget(self.cancel_btn)

        self.save_config_btn = QPushButton("💾 保存配置")
        self.save_config_btn.clicked.connect(self._save_config)
        action_layout.addWidget(self.save_config_btn)

        action_layout.addStretch()
        layout.addLayout(action_layout)

    def _load_templates(self):
        """加载可用模板"""
        templates = self.prompt_manager.list_templates()
        self.template_combo.clear()

        # 添加内置模板
        template_map = {
            "correct.zh": ("中文纠错优化", "correct"),
            "translate.en": ("翻译成英文", "translate"),
            "bilingual": ("双语字幕", "bilingual"),
        }

        for name, description in templates.items():
            display = f"{description} ({name})"
            self.template_combo.addItem(display, name)

    def _on_mode_changed(self, index):
        """处理模式改变时更新模板建议"""
        mode = self.mode_combo.currentData()

        # 根据模式选择合适的默认模板
        if mode == "correct":
            self._set_template_by_name("correct.zh")
            self.target_lang_label.setVisible(False)
            self.target_lang_combo.setVisible(False)
        elif mode == "translate":
            self._set_template_by_name("translate.en")
            self.target_lang_label.setVisible(True)
            self.target_lang_combo.setVisible(True)
        elif mode == "bilingual":
            self._set_template_by_name("bilingual")
            self.target_lang_label.setVisible(False)
            self.target_lang_combo.setVisible(False)

    def _set_template_by_name(self, name: str):
        """根据名称设置模板"""
        for i in range(self.template_combo.count()):
            if self.template_combo.itemData(i) == name:
                self.template_combo.setCurrentIndex(i)
                break

    def _load_config(self):
        """加载配置到 UI"""
        llm_config = self.pipeline_config.llm
        self.llm_base_url.setText(llm_config.base_url or "")
        self.llm_api_key.setText(llm_config.api_key or "")
        if llm_config.model:
            self.llm_model.setCurrentText(llm_config.model)
        self.batch_size.setCurrentText(str(llm_config.batch_size))

        # 设置模板
        if llm_config.prompt_template:
            self._set_template_by_name(llm_config.prompt_template)

        # 设置模式
        mode_index = {"correct": 0, "translate": 1, "bilingual": 2}.get(
            llm_config.output_mode, 0
        )
        self.mode_combo.setCurrentIndex(mode_index)

    def _update_config(self) -> LLMProcessConfig:
        """从 UI 更新配置"""
        return LLMProcessConfig(
            enabled=True,
            provider="openai_compatible",
            api_key=self.llm_api_key.text(),
            base_url=self.llm_base_url.text(),
            model=self.llm_model.currentText(),
            prompt_template=self.template_combo.currentData(),
            output_mode=self.mode_combo.currentData(),
            batch_size=int(self.batch_size.currentText()),
            target_language=self.target_lang_combo.currentText(),
        )

    def _save_config(self):
        """保存配置"""
        self.pipeline_config.llm = self._update_config()
        self.config_manager.save_user_config(self.pipeline_config)
        self._log("✓ 配置已保存")

    def _browse_input(self):
        """浏览输入文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择 SRT 字幕文件", "",
            "字幕文件 (*.srt);;所有文件 (*)"
        )
        if file_path:
            self.input_path.setText(file_path)
            # 自动设置输出路径
            input_path = Path(file_path)
            auto_output = input_path.parent / f"{input_path.stem}.processed.srt"
            self.output_path.setText(str(auto_output))

    def _browse_output(self):
        """浏览输出文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存处理后字幕", "",
            "字幕文件 (*.srt);;所有文件 (*)"
        )
        if file_path:
            self.output_path.setText(file_path)

    def _start_processing(self):
        """开始处理"""
        input_path = Path(self.input_path.text()) if self.input_path.text() else None
        output_path = Path(self.output_path.text()) if self.output_path.text() else None

        if not input_path or not input_path.exists():
            QMessageBox.warning(self, "警告", "请选择有效的输入文件")
            return

        if not output_path:
            # 自动生成输出路径
            output_path = input_path.parent / f"{input_path.stem}.processed.srt"
            self.output_path.setText(str(output_path))

        # 检查 LLM 配置
        config = self._update_config()
        if not config.api_key or not config.base_url:
            QMessageBox.warning(self, "警告", "请配置 LLM 的 API Key 和 Base URL")
            return

        # 清空日志
        self.log_text.clear()
        self._log(f"输入: {input_path}")
        self._log(f"输出: {output_path}")
        self._log(f"模式: {self.mode_combo.currentText()}")
        self._log(f"模板: {self.template_combo.currentData()}")

        # 创建工作线程
        from ..workers.srt_process_worker import SRTProcessWorker
        self.worker = SRTProcessWorker(input_path, output_path, config)

        # 连接信号
        self.worker.started_signal.connect(self._on_started)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.error_signal.connect(self._on_error)
        self.worker.log_signal.connect(self._log)

        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.worker.start()

    def _cancel_processing(self):
        """取消处理"""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self._log("正在取消...")
            self.cancel_btn.setEnabled(False)

    def _on_started(self):
        """处理开始"""
        self.progress_bar.setValue(0)
        self.status_label.setText("处理中...")

    def _on_progress(self, percent: int, message: str):
        """进度更新"""
        self.progress_bar.setValue(percent)
        if message:
            self.status_label.setText(message)

    def _on_finished(self, success: bool, message: str):
        """处理完成"""
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        if success:
            self.status_label.setText("完成")
            QMessageBox.information(self, "完成", message)
        else:
            self.status_label.setText(f"失败: {message}")
            if message != "已取消":
                QMessageBox.warning(self, "处理失败", message)

    def _on_error(self, error: str):
        """错误处理"""
        self._log(f"错误: {error}")

    def _log(self, message: str):
        """添加日志"""
        self.log_text.append(message)
