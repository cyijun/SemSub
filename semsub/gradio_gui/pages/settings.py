"""
设置页面

配置所有 SemSub 参数
"""

from pathlib import Path
from typing import Dict, Any, Tuple

import gradio as gr

from ...core.config import PipelineConfig
from ...core.config_manager import get_config_manager
from ..utils import load_config, save_config, get_preset_choices


def create_settings_page() -> gr.Tab:
    """创建设置页面"""

    with gr.Tab("⚙️ 设置") as tab:
        gr.Markdown("""
        # ⚙️ 系统设置
        配置 SemSub 的各项参数
        """)

        with gr.Tabs():
            # ASR 设置
            with gr.TabItem("🎙️ ASR 模型"):
                gr.Markdown("### 语音识别模型配置")

                asr_model_path = gr.Textbox(
                    label="ASR 模型路径",
                    placeholder="/mnt/g/models/Qwen3-ASR-1.7B",
                )

                aligner_model_path = gr.Textbox(
                    label="对齐模型路径",
                    placeholder="/mnt/g/models/Qwen3-ForcedAligner-0.6B",
                )

                with gr.Row():
                    asr_batch_size = gr.Slider(
                        minimum=1,
                        maximum=32,
                        value=8,
                        step=1,
                        label="批次大小",
                    )

                    asr_device = gr.Dropdown(
                        choices=[
                            ("CUDA:0", "cuda:0"),
                            ("CUDA:1", "cuda:1"),
                            ("CPU", "cpu"),
                        ],
                        value="cuda:0",
                        label="设备",
                    )

            # VAD 设置
            with gr.TabItem("🔊 VAD 参数"):
                gr.Markdown("### 语音活动检测配置")

                vad_threshold = gr.Slider(
                    minimum=0.1,
                    maximum=0.9,
                    value=0.5,
                    step=0.05,
                    label="检测阈值",
                )

                with gr.Row():
                    vad_min_speech = gr.Slider(
                        minimum=50,
                        maximum=1000,
                        value=250,
                        step=50,
                        label="最小语音时长 (ms)",
                    )

                    vad_min_silence = gr.Slider(
                        minimum=100,
                        maximum=2000,
                        value=500,
                        step=100,
                        label="最小静音时长 (ms)",
                    )

            # 字幕设置
            with gr.TabItem("📝 字幕优化"):
                gr.Markdown("### 字幕优化参数")

                with gr.Row():
                    sub_max_chars = gr.Slider(
                        minimum=20,
                        maximum=100,
                        value=40,
                        step=5,
                        label="中文每行最大字符",
                    )

                    sub_max_chars_en = gr.Slider(
                        minimum=40,
                        maximum=160,
                        value=80,
                        step=10,
                        label="英文每行最大字符",
                    )

                with gr.Row():
                    sub_max_duration = gr.Slider(
                        minimum=2.0,
                        maximum=10.0,
                        value=6.0,
                        step=0.5,
                        label="最大显示时长 (秒)",
                    )

                    sub_min_duration = gr.Slider(
                        minimum=0.5,
                        maximum=3.0,
                        value=1.0,
                        step=0.5,
                        label="最小显示时长 (秒)",
                    )

                sub_gap_threshold = gr.Slider(
                    minimum=0.1,
                    maximum=1.0,
                    value=0.3,
                    step=0.1,
                    label="片段合并阈值 (秒)",
                )

            # LLM 设置
            with gr.TabItem("🤖 LLM 配置"):
                gr.Markdown("### 大模型配置")

                llm_enabled_default = gr.Checkbox(
                    label="默认启用 LLM 后处理",
                    value=False,
                )

                llm_default_provider = gr.Dropdown(
                    choices=[
                        ("OpenAI 兼容", "openai_compatible"),
                        ("Ollama", "ollama"),
                    ],
                    value="openai_compatible",
                    label="默认提供商",
                )

                llm_default_base_url = gr.Textbox(
                    label="默认 Base URL",
                    placeholder="https://api.deepseek.com/v1",
                )

                llm_default_model = gr.Textbox(
                    label="默认模型",
                    placeholder="deepseek-chat",
                )

                with gr.Row():
                    llm_batch_size = gr.Slider(
                        minimum=1,
                        maximum=50,
                        value=10,
                        step=1,
                        label="默认批次大小",
                    )

                    llm_temperature = gr.Slider(
                        minimum=0.0,
                        maximum=1.0,
                        value=0.3,
                        step=0.1,
                        label="默认 Temperature",
                    )

        # 保存和重置按钮
        with gr.Row():
            save_btn = gr.Button("💾 保存配置", variant="primary", size="lg")
            reset_btn = gr.Button("🔄 重置为默认", size="lg")
            export_btn = gr.Button("📤 导出配置", size="lg")

        # 保存位置选择
        save_location = gr.Radio(
            choices=[
                ("保存到用户配置 (~/.config/semsub/)", "user"),
                ("保存到项目配置 (./semsub.yaml)", "project"),
            ],
            value="user",
            label="保存位置",
        )

        # 状态显示
        save_status = gr.Textbox(
            label="状态",
            interactive=False,
            visible=False,
        )

        # 事件处理

        def load_settings() -> Tuple[Any, ...]:
            """加载当前设置"""
            config = load_config()

            return (
                # ASR
                config.asr.model_path or "",
                config.asr.aligner_path or "",
                config.asr.batch_size,
                config.asr.device,
                # VAD
                config.vad.threshold,
                config.vad.min_speech_duration_ms,
                config.vad.min_silence_duration_ms,
                # Subtitle
                config.subtitle.max_chars,
                config.subtitle.max_chars_en,
                config.subtitle.max_duration,
                config.subtitle.min_duration,
                config.subtitle.gap_threshold,
                # LLM
                config.llm.enabled,
                config.llm.provider,
                config.llm.base_url or "",
                config.llm.model or "",
                config.llm.batch_size,
                config.llm.temperature,
            )

        def save_settings(
            # ASR
            asr_model: str,
            aligner_model: str,
            batch_size: int,
            device: str,
            # VAD
            vad_thresh: float,
            vad_min_sp: int,
            vad_min_sl: int,
            # Subtitle
            sub_max_ch: int,
            sub_max_ch_en: int,
            sub_max_dur: float,
            sub_min_dur: float,
            sub_gap: float,
            # LLM
            llm_en: bool,
            llm_prov: str,
            llm_url: str,
            llm_mod: str,
            llm_batch: int,
            llm_temp: float,
            # Save location
            location: str,
        ) -> Tuple[str, bool]:
            """保存设置"""
            try:
                config = PipelineConfig(
                    asr=config.asr.__class__(
                        model_path=asr_model or None,
                        aligner_path=aligner_model or None,
                        batch_size=batch_size,
                        device=device,
                    ),
                    vad=config.vad.__class__(
                        threshold=vad_thresh,
                        min_speech_duration_ms=vad_min_sp,
                        min_silence_duration_ms=vad_min_sl,
                    ),
                    subtitle=config.subtitle.__class__(
                        max_chars=sub_max_ch,
                        max_chars_en=sub_max_ch_en,
                        max_duration=sub_max_dur,
                        min_duration=sub_min_dur,
                        gap_threshold=sub_gap,
                    ),
                    llm=config.llm.__class__(
                        enabled=llm_en,
                        provider=llm_prov,
                        base_url=llm_url or None,
                        model=llm_mod or None,
                        batch_size=llm_batch,
                        temperature=llm_temp,
                    ),
                )

                if save_config(config, location):
                    return "✅ 配置已保存", True
                else:
                    return "❌ 保存失败", True

            except Exception as e:
                return f"❌ 保存失败: {str(e)}", True

        def reset_settings() -> Tuple[Any, ...]:
            """重置为默认设置"""
            default_config = PipelineConfig()

            return (
                # ASR
                default_config.asr.model_path or "",
                default_config.asr.aligner_path or "",
                default_config.asr.batch_size,
                default_config.asr.device,
                # VAD
                default_config.vad.threshold,
                default_config.vad.min_speech_duration_ms,
                default_config.vad.min_silence_duration_ms,
                # Subtitle
                default_config.subtitle.max_chars,
                default_config.subtitle.max_chars_en,
                default_config.subtitle.max_duration,
                default_config.subtitle.min_duration,
                default_config.subtitle.gap_threshold,
                # LLM
                default_config.llm.enabled,
                default_config.llm.provider,
                default_config.llm.base_url or "",
                default_config.llm.model or "",
                default_config.llm.batch_size,
                default_config.llm.temperature,
                # Status
                "配置已重置为默认值，请点击保存",
                True,
            )

        # 页面加载时自动加载设置
        tab.select(
            fn=load_settings,
            outputs=[
                asr_model_path,
                aligner_model_path,
                asr_batch_size,
                asr_device,
                vad_threshold,
                vad_min_speech,
                vad_min_silence,
                sub_max_chars,
                sub_max_chars_en,
                sub_max_duration,
                sub_min_duration,
                sub_gap_threshold,
                llm_enabled_default,
                llm_default_provider,
                llm_default_base_url,
                llm_default_model,
                llm_batch_size,
                llm_temperature,
            ],
        )

        save_btn.click(
            fn=save_settings,
            inputs=[
                asr_model_path,
                aligner_model_path,
                asr_batch_size,
                asr_device,
                vad_threshold,
                vad_min_speech,
                vad_min_silence,
                sub_max_chars,
                sub_max_chars_en,
                sub_max_duration,
                sub_min_duration,
                sub_gap_threshold,
                llm_enabled_default,
                llm_default_provider,
                llm_default_base_url,
                llm_default_model,
                llm_batch_size,
                llm_temperature,
                save_location,
            ],
            outputs=[save_status, save_status],
        )

        reset_btn.click(
            fn=reset_settings,
            outputs=[
                asr_model_path,
                aligner_model_path,
                asr_batch_size,
                asr_device,
                vad_threshold,
                vad_min_speech,
                vad_min_silence,
                sub_max_chars,
                sub_max_chars_en,
                sub_max_duration,
                sub_min_duration,
                sub_gap_threshold,
                llm_enabled_default,
                llm_default_provider,
                llm_default_base_url,
                llm_default_model,
                llm_batch_size,
                llm_temperature,
                save_status,
                save_status,
            ],
        )

    return tab
