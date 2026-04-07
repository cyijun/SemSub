"""
配置管理模块
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTabWidget, QWidget as TabWidget,
    QFormLayout, QComboBox, QLineEdit, QCheckBox,
    QSpinBox, QDoubleSpinBox, QTextEdit, QFileDialog,
    QMessageBox, QGroupBox, QTreeWidget, QTreeWidgetItem,
    QWizard, QWizardPage
)
from PyQt6.QtCore import Qt

from ...core.config_manager import get_config_manager
from ...core.config import PipelineConfig


class ConfigWizard(QWizard):
    """配置向导"""

    def __init__(self, config: PipelineConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("配置向导")
        self.setMinimumSize(600, 500)

        # 添加页面
        self.addPage(self._create_llm_page())
        self.addPage(self._create_subtitle_page())
        self.addPage(self._create_asr_page())
        self.addPage(self._create_save_page())

    def _create_llm_page(self) -> QWizardPage:
        """LLM 配置页"""
        page = QWizardPage()
        page.setTitle("步骤 1/4: LLM 配置")
        page.setSubTitle("配置大模型后处理选项（可选）")

        layout = QFormLayout(page)

        self.wizard_llm_enabled = QCheckBox("启用大模型后处理")
        self.wizard_llm_enabled.setChecked(self.config.llm.enabled)
        layout.addRow(self.wizard_llm_enabled)

        self.wizard_llm_base_url = QLineEdit(self.config.llm.base_url or "")
        self.wizard_llm_base_url.setPlaceholderText("https://api.deepseek.com/v1")
        layout.addRow("Base URL:", self.wizard_llm_base_url)

        self.wizard_llm_api_key = QLineEdit(self.config.llm.api_key or "")
        self.wizard_llm_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("API Key:", self.wizard_llm_api_key)

        self.wizard_llm_model = QLineEdit(self.config.llm.model or "deepseek-chat")
        layout.addRow("模型:", self.wizard_llm_model)

        return page

    def _create_subtitle_page(self) -> QWizardPage:
        """字幕配置页"""
        page = QWizardPage()
        page.setTitle("步骤 2/4: 字幕配置")
        page.setSubTitle("配置字幕优化参数")

        layout = QFormLayout(page)

        self.wizard_max_chars = QSpinBox()
        self.wizard_max_chars.setRange(20, 100)
        self.wizard_max_chars.setValue(self.config.subtitle.max_chars)
        layout.addRow("中文每行最大字符:", self.wizard_max_chars)

        self.wizard_max_duration = QDoubleSpinBox()
        self.wizard_max_duration.setRange(2.0, 10.0)
        self.wizard_max_duration.setValue(self.config.subtitle.max_duration)
        self.wizard_max_duration.setSuffix(" 秒")
        layout.addRow("最大显示时长:", self.wizard_max_duration)

        # 预设快速选择
        presets = QGroupBox("快速选择预设")
        presets_layout = QHBoxLayout(presets)

        for preset_name in ["电影", "纪录片", "动画"]:
            btn = QPushButton(preset_name)
            btn.clicked.connect(lambda checked, pn=preset_name: self._apply_preset(pn))
            presets_layout.addWidget(btn)

        layout.addRow(presets)

        return page

    def _apply_preset(self, preset_name: str):
        """应用预设"""
        presets = {
            "电影": {"max_chars": 40, "max_duration": 6.0},
            "纪录片": {"max_chars": 35, "max_duration": 7.0},
            "动画": {"max_chars": 30, "max_duration": 4.0},
        }
        settings = presets.get(preset_name, {})
        self.wizard_max_chars.setValue(settings.get("max_chars", 40))
        self.wizard_max_duration.setValue(settings.get("max_duration", 6.0))

    def _create_asr_page(self) -> QWizardPage:
        """ASR 配置页"""
        page = QWizardPage()
        page.setTitle("步骤 3/4: ASR 配置")
        page.setSubTitle("配置语音识别参数")

        layout = QFormLayout(page)

        self.wizard_batch_size = QSpinBox()
        self.wizard_batch_size.setRange(1, 32)
        self.wizard_batch_size.setValue(self.config.asr.batch_size)
        layout.addRow("批次大小:", self.wizard_batch_size)

        self.wizard_language = QComboBox()
        self.wizard_language.addItems(["自动检测", "中文", "English", "日本語"])
        layout.addRow("语言:", self.wizard_language)

        return page

    def _create_save_page(self) -> QWizardPage:
        """保存配置页"""
        page = QWizardPage()
        page.setTitle("步骤 4/4: 保存配置")
        page.setSubTitle("选择保存位置")

        layout = QFormLayout(page)

        self.save_location = QComboBox()
        self.save_location.addItems(["用户配置 (~/.config/semsub/)", "项目配置 (./semsub.yaml)"])
        layout.addRow("保存位置:", self.save_location)

        # 配置预览
        layout.addRow(QLabel("配置预览:"))
        self.config_preview = QTextEdit()
        self.config_preview.setReadOnly(True)
        self.config_preview.setMaximumHeight(150)
        layout.addRow(self.config_preview)

        return page

    def get_config(self) -> tuple[PipelineConfig, str]:
        """获取配置和保存位置"""
        config = PipelineConfig()

        # LLM
        config.llm.enabled = self.wizard_llm_enabled.isChecked()
        config.llm.base_url = self.wizard_llm_base_url.text() or None
        config.llm.api_key = self.wizard_llm_api_key.text() or None
        config.llm.model = self.wizard_llm_model.text() or None

        # Subtitle
        config.subtitle.max_chars = self.wizard_max_chars.value()
        config.subtitle.max_duration = self.wizard_max_duration.value()

        # ASR
        config.asr.batch_size = self.wizard_batch_size.value()

        location = "user" if self.save_location.currentIndex() == 0 else "project"

        return config, location


class ConfigModule(QWidget):
    """配置管理模块"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = get_config_manager()
        self.config = self.config_manager.load()
        self._setup_ui()

    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Tab 切换
        self.tabs = QTabWidget()

        # Tab 1: 配置向导
        self.tabs.addTab(self._create_wizard_tab(), "🧙 配置向导")

        # Tab 2: 当前配置
        self.tabs.addTab(self._create_current_tab(), "📋 当前配置")

        # Tab 3: 预设管理
        self.tabs.addTab(self._create_presets_tab(), "🎨 预设管理")

        # Tab 4: 导入导出
        self.tabs.addTab(self._create_io_tab(), "💾 导入导出")

        layout.addWidget(self.tabs)

    def _create_wizard_tab(self) -> QWidget:
        """配置向导标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info = QLabel("配置向导将引导你完成 SemSub 的配置。")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        start_btn = QPushButton("🚀 启动配置向导")
        start_btn.setMinimumHeight(50)
        start_btn.clicked.connect(self._start_wizard)
        layout.addWidget(start_btn)

        layout.addStretch()
        return widget

    def _create_current_tab(self) -> QWidget:
        """当前配置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 配置树
        self.config_tree = QTreeWidget()
        self.config_tree.setHeaderLabels(["配置项", "值"])
        self.config_tree.setColumnWidth(0, 200)
        layout.addWidget(self.config_tree)

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._refresh_config_tree)
        layout.addWidget(refresh_btn)

        self._refresh_config_tree()
        return widget

    def _create_presets_tab(self) -> QWidget:
        """预设管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 预设列表
        layout.addWidget(QLabel("可用预设:"))
        self.preset_list = QComboBox()
        self.preset_list.addItems(["movie", "documentary", "animation"])
        self.preset_list.currentTextChanged.connect(self._on_preset_selected)
        layout.addWidget(self.preset_list)

        # 预设详情
        layout.addWidget(QLabel("预设详情:"))
        self.preset_details = QTextEdit()
        self.preset_details.setReadOnly(True)
        self.preset_details.setMaximumHeight(200)
        layout.addWidget(self.preset_details)

        # 应用按钮
        apply_btn = QPushButton("✅ 应用此预设")
        apply_btn.clicked.connect(self._apply_preset)
        layout.addWidget(apply_btn)

        self._on_preset_selected("movie")
        layout.addStretch()
        return widget

    def _create_io_tab(self) -> QWidget:
        """导入导出标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 导出
        export_group = QGroupBox("导出配置")
        export_layout = QVBoxLayout(export_group)

        export_btn = QPushButton("📤 导出到文件")
        export_btn.clicked.connect(self._export_config)
        export_layout.addWidget(export_btn)

        layout.addWidget(export_group)

        # 导入
        import_group = QGroupBox("导入配置")
        import_layout = QVBoxLayout(import_group)

        import_user_btn = QPushButton("📥 导入为用户配置")
        import_user_btn.clicked.connect(lambda: self._import_config("user"))
        import_layout.addWidget(import_user_btn)

        import_project_btn = QPushButton("📥 导入为项目配置")
        import_project_btn.clicked.connect(lambda: self._import_config("project"))
        import_layout.addWidget(import_project_btn)

        layout.addWidget(import_group)
        layout.addStretch()
        return widget

    def _start_wizard(self):
        """启动配置向导"""
        wizard = ConfigWizard(self.config, self)
        if wizard.exec() == QWizard.DialogCode.Accepted:
            new_config, location = wizard.get_config()

            # 保存配置
            if location == "user":
                self.config_manager.save_user_config(new_config)
            else:
                self.config_manager.save_project_config(new_config)

            # 重新加载
            self.config = self.config_manager.load()
            self._refresh_config_tree()

            QMessageBox.information(self, "完成", "配置已保存！")

    def _refresh_config_tree(self):
        """刷新配置树"""
        self.config_tree.clear()

        config = self.config_manager.load()

        # VAD
        vad_item = QTreeWidgetItem(["vad", ""])
        vad_item.addChild(QTreeWidgetItem(["threshold", str(config.vad.threshold)]))
        vad_item.addChild(QTreeWidgetItem(["min_speech_duration_ms", str(config.vad.min_speech_duration_ms)]))
        vad_item.addChild(QTreeWidgetItem(["min_silence_duration_ms", str(config.vad.min_silence_duration_ms)]))
        self.config_tree.addTopLevelItem(vad_item)
        vad_item.setExpanded(True)

        # Subtitle
        sub_item = QTreeWidgetItem(["subtitle", ""])
        sub_item.addChild(QTreeWidgetItem(["max_chars", str(config.subtitle.max_chars)]))
        sub_item.addChild(QTreeWidgetItem(["max_duration", str(config.subtitle.max_duration)]))
        self.config_tree.addTopLevelItem(sub_item)
        sub_item.setExpanded(True)

        # ASR
        asr_item = QTreeWidgetItem(["asr", ""])
        asr_item.addChild(QTreeWidgetItem(["batch_size", str(config.asr.batch_size)]))
        asr_item.addChild(QTreeWidgetItem(["language", str(config.asr.language)]))
        self.config_tree.addTopLevelItem(asr_item)
        asr_item.setExpanded(True)

        # LLM
        llm_item = QTreeWidgetItem(["llm", ""])
        llm_item.addChild(QTreeWidgetItem(["enabled", str(config.llm.enabled)]))
        llm_item.addChild(QTreeWidgetItem(["model", str(config.llm.model)]))
        self.config_tree.addTopLevelItem(llm_item)
        llm_item.setExpanded(True)

    def _on_preset_selected(self, preset_name: str):
        """预设选择改变"""
        presets = self.config_manager.list_presets()
        if preset_name in presets:
            preset = presets[preset_name]
            details = f"""
名称: {preset_name}

VAD:
  - 阈值: {preset.vad.threshold}
  - 最小语音时长: {preset.vad.min_speech_duration_ms}ms
  - 最小静音时长: {preset.vad.min_silence_duration_ms}ms

字幕:
  - 最大字符数: {preset.subtitle.max_chars}
  - 最大时长: {preset.subtitle.max_duration}s

ASR:
  - 批次大小: {preset.asr.batch_size}
            """
            self.preset_details.setText(details.strip())

    def _apply_preset(self):
        """应用选中的预设"""
        preset_name = self.preset_list.currentText()
        preset = self.config_manager.load_preset(preset_name)
        if preset:
            # 应用预设到当前配置
            self.config_manager.save_user_config(preset)
            self.config = preset
            self._refresh_config_tree()
            QMessageBox.information(self, "完成", f"已应用预设: {preset_name}")

    def _export_config(self):
        """导出配置"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出配置", "semsub_config.yaml",
            "YAML files (*.yaml);;All files (*)"
        )
        if file_path:
            try:
                self.config_manager.export_config(Path(file_path))
                QMessageBox.information(self, "完成", f"配置已导出到:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {e}")

    def _import_config(self, target: str):
        """导入配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入配置", "",
            "YAML files (*.yaml);;All files (*)"
        )
        if file_path:
            try:
                self.config_manager.import_config(
                    Path(file_path),
                    target=target  # type: ignore
                )
                self.config = self.config_manager.load()
                self._refresh_config_tree()
                QMessageBox.information(self, "完成", "配置已导入！")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导入失败: {e}")
