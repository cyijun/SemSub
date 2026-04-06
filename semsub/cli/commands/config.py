"""
配置管理命令
"""

import click
from pathlib import Path
from rich.console import Console
from rich.table import Table

from ...core.config import PipelineConfig
from ...core.config_manager import get_config_manager

console = Console()


@click.group()
def config():
    """配置管理"""
    pass


@config.command()
@click.option("--preset", "-p", help="使用预设")
def show(preset):
    """显示当前配置（合并后的配置）"""
    manager = get_config_manager()
    cfg = manager.load(preset=preset)

    table = Table(title="当前配置")
    table.add_column("模块", style="cyan")
    table.add_column("设置", style="magenta")
    table.add_column("值", style="green")

    # VAD 配置
    table.add_row("VAD", "threshold", str(cfg.vad.threshold))
    table.add_row("VAD", "min_speech_duration_ms", str(cfg.vad.min_speech_duration_ms))
    table.add_row("VAD", "min_silence_duration_ms", str(cfg.vad.min_silence_duration_ms))

    # 字幕配置
    table.add_row("字幕", "max_chars", str(cfg.subtitle.max_chars))
    table.add_row("字幕", "min_chars", str(cfg.subtitle.min_chars))
    table.add_row("字幕", "max_duration", str(cfg.subtitle.max_duration))
    table.add_row("字幕", "min_line_duration", str(cfg.subtitle.min_line_duration))
    table.add_row("字幕", "prefer_longer_lines", str(cfg.subtitle.prefer_longer_lines))

    # ASR 配置
    table.add_row("ASR", "model_path", cfg.asr.model_path)
    table.add_row("ASR", "device", cfg.asr.device)

    # LLM 配置
    table.add_row("LLM", "enabled", str(cfg.llm.enabled))
    table.add_row("LLM", "model", cfg.llm.model)
    table.add_row("LLM", "base_url", cfg.llm.base_url)
    # API Key 部分隐藏
    api_key_display = "未设置"
    if cfg.llm.api_key:
        api_key_display = cfg.llm.api_key[:8] + "..." if len(cfg.llm.api_key) > 8 else "***"
    table.add_row("LLM", "api_key", api_key_display)

    # 输出配置
    table.add_row("输出", "format", cfg.output.format)

    console.print(table)


@config.command()
@click.argument("key")
@click.argument("value")
@click.option("--user", "-u", is_flag=True, help="保存到用户配置")
@click.option("--project", "-p", is_flag=True, help="保存到项目配置")
def set(key, value, user, project):
    """设置配置项"""
    manager = get_config_manager()

    # 加载现有配置
    cfg = manager.load()

    # 设置值
    if manager.set_config_value(cfg, key, value):
        # 保存配置
        if project:
            manager.save_project_config(cfg)
            console.print(f"[green]设置 {key} = {value} (已保存到项目配置)[/green]")
        else:
            manager.save_user_config(cfg)
            console.print(f"[green]设置 {key} = {value} (已保存到用户配置)[/green]")
    else:
        console.print(f"[red]配置项不存在: {key}[/red]")


@config.command()
@click.argument("key")
@click.option("--preset", "-p", help="使用预设")
def get(key, preset):
    """获取配置项"""
    manager = get_config_manager()
    cfg = manager.load(preset=preset)

    value = manager.get_config_value(cfg, key)
    if value is not None:
        # 对 API Key 进行部分隐藏
        if "api_key" in key and isinstance(value, str) and value:
            value = value[:8] + "..." if len(value) > 8 else "***"
        console.print(f"{key} = {value}")
    else:
        console.print(f"[red]配置项不存在: {key}[/red]")


@config.command("list-presets")
def list_presets():
    """列出所有预设"""
    manager = get_config_manager()
    presets = manager.list_presets()

    if not presets:
        console.print("[yellow]没有可用的预设[/yellow]")
        return

    table = Table(title="可用预设")
    table.add_column("名称", style="cyan")
    table.add_column("描述", style="green")

    for name, description in presets.items():
        table.add_row(name, description)

    console.print(table)


@config.command()
@click.argument("path", type=click.Path())
def export(path):
    """导出配置到文件"""
    manager = get_config_manager()
    cfg = manager.load()

    output_path = Path(path)
    manager._save_yaml(cfg, output_path)
    console.print(f"[green]配置已导出到: {output_path}[/green]")


@config.command("import")
@click.argument("path", type=click.Path(exists=True))
@click.option("--user", "-u", is_flag=True, help="导入为用户配置")
@click.option("--project", "-p", is_flag=True, help="导入为项目配置")
def import_(path, user, project):
    """从文件导入配置"""
    manager = get_config_manager()

    # 从文件加载
    override = manager._load_yaml(Path(path))

    # 加载当前配置并合并
    cfg = manager.load()
    cfg = manager._merge_config(cfg, override)

    # 保存
    if project:
        manager.save_project_config(cfg)
        console.print(f"[green]配置已从 {path} 导入并保存为项目配置[/green]")
    else:
        manager.save_user_config(cfg)
        console.print(f"[green]配置已从 {path} 导入并保存为用户配置[/green]")


@config.command()
def wizard():
    """交互式配置向导"""
    console.print("[bold cyan]SemSub 配置向导[/bold cyan]")
    console.print("本向导会帮助你配置常用设置，所有配置将保存到用户目录，后续无需重复填写。")
    console.print()

    manager = get_config_manager()
    cfg = manager.load()

    # === LLM 配置 ===
    console.print("[cyan]1. LLM 后处理配置[/cyan]")
    console.print("LLM 可以用于翻译、纠错或生成双语字幕。")
    cfg.llm.enabled = click.confirm("启用 LLM 后处理?", default=cfg.llm.enabled)

    if cfg.llm.enabled:
        # 提供常用提供商选项
        console.print("\n选择 LLM 提供商:")
        console.print("  1) DeepSeek (api.deepseek.com)")
        console.print("  2) Moonshot/Kimi (api.moonshot.cn)")
        console.print("  3) 通义千问 (dashscope.aliyuncs.com)")
        console.print("  4) 自定义")
        provider_choice = click.prompt("选择", type=int, default=1)

        providers = {
            1: ("https://api.deepseek.com/v1", "deepseek-chat"),
            2: ("https://api.moonshot.cn/v1", "moonshot-v1-8k"),
            3: ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-turbo"),
        }

        if provider_choice in providers:
            cfg.llm.base_url, default_model = providers[provider_choice]
            cfg.llm.model = default_model
        else:
            cfg.llm.base_url = click.prompt("Base URL", default=cfg.llm.base_url or "https://api.openai.com/v1")
            cfg.llm.model = click.prompt("模型", default=cfg.llm.model or "gpt-3.5-turbo")

        # API Key 输入
        current_key = cfg.llm.api_key
        key_display = current_key[:8] + "..." if current_key and len(current_key) > 8 else ("已设置" if current_key else "未设置")
        console.print(f"当前 API Key: {key_display}")
        new_key = click.prompt("输入 API Key (留空保持当前)", default="", hide_input=True, show_default=False)
        if new_key:
            cfg.llm.api_key = new_key

        # 输出模式
        console.print("\nLLM 输出模式:")
        console.print("  correct    - 仅纠错，保持原文语言")
        console.print("  translate  - 翻译为目标语言")
        console.print("  bilingual  - 双语输出（原文+译文）")
        cfg.llm.output_mode = click.prompt("输出模式", type=click.Choice(["correct", "translate", "bilingual"]), default=cfg.llm.output_mode)

        if cfg.llm.output_mode == "translate":
            cfg.llm.target_language = click.prompt("目标语言", default=cfg.llm.target_language or "English")

        console.print()

    # === 字幕配置 ===
    console.print("[cyan]2. 字幕显示配置[/cyan]")
    console.print("这些设置影响字幕的切换频率和长度。")

    # 使用场景预设
    console.print("\n选择使用场景:")
    console.print("  1) 讲课/纪录片 - 较少切换，每行显示更长 (min_chars=15, min_line_duration=3s)")
    console.print("  2) 电影/对话  - 正常切换 (min_chars=10, min_line_duration=2s)")
    console.print("  3) 快速对话   - 稍快切换 (min_chars=8, min_line_duration=1.5s)")
    console.print("  4) 自定义")

    scene_choice = click.prompt("选择", type=int, default=2)
    scene_presets = {
        1: (15, 3.0),
        2: (10, 2.0),
        3: (8, 1.5),
    }

    if scene_choice in scene_presets:
        cfg.subtitle.min_chars, cfg.subtitle.min_line_duration = scene_presets[scene_choice]
        cfg.subtitle.prefer_longer_lines = True
    else:
        cfg.subtitle.min_chars = click.prompt("每行最少字符数", type=int, default=cfg.subtitle.min_chars)
        cfg.subtitle.min_line_duration = click.prompt("每行最少显示时长(秒)", type=float, default=cfg.subtitle.min_line_duration)
        cfg.subtitle.prefer_longer_lines = click.confirm("优先合并成更长的行?", default=True)

    cfg.subtitle.max_chars = click.prompt("每行最多字符数", type=int, default=cfg.subtitle.max_chars)
    cfg.subtitle.max_duration = click.prompt("每行最大显示时长(秒)", type=float, default=cfg.subtitle.max_duration)
    console.print()

    # === ASR 配置 ===
    console.print("[cyan]3. ASR 模型配置[/cyan]")
    if click.confirm("修改 ASR 模型路径?", default=False):
        cfg.asr.model_path = click.prompt("ASR 模型路径", default=cfg.asr.model_path)
        cfg.asr.aligner_path = click.prompt("对齐模型路径", default=cfg.asr.aligner_path)
        cfg.asr.device = click.prompt("设备", default=cfg.asr.device)
    console.print()

    # === 保存配置 ===
    console.print("[cyan]4. 保存配置[/cyan]")
    save_to = click.prompt(
        "保存到",
        type=click.Choice(["user", "project"]),
        default="user"
    )

    if save_to == "user":
        manager.save_user_config(cfg)
        console.print(f"[green]配置已保存到用户目录: {manager.user_config_file}[/green]")
    else:
        manager.save_project_config(cfg)
        console.print(f"[green]配置已保存到项目目录: {manager.project_config_file}[/green]")

    console.print()
    console.print("[bold green]配置完成! 以后运行命令时将自动使用这些设置。[/bold green]")
    console.print("提示: 使用 'semsub config show' 查看当前配置")
