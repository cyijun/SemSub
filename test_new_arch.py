"""
测试新的架构
"""

import sys
sys.path.insert(0, '/mnt/d/temp/SemSub')

# 测试导入
def test_imports():
    print("测试导入...")
    try:
        from semsub.core.config import PipelineConfig
        from semsub.core.models import WordItem, SubtitleLine
        from semsub.core.merger import SubtitleMerger
        from semsub.core.pipeline import SubtitlePipeline
        from semsub.core.progress import ProgressReporter
        print("✓ 核心模块导入成功")
        return True
    except Exception as e:
        print(f"✗ 导入失败: {e}")
        return False

# 测试配置
def test_config():
    print("\n测试配置...")
    try:
        from semsub.core.config import PipelineConfig
        config = PipelineConfig()
        print(f"✓ 配置创建成功")
        print(f"  - VAD threshold: {config.vad.threshold}")
        print(f"  - 字幕 max_chars: {config.subtitle.max_chars}")
        print(f"  - LLM enabled: {config.llm.enabled}")
        return True
    except Exception as e:
        print(f"✗ 配置测试失败: {e}")
        return False

# 测试字幕模型
def test_models():
    print("\n测试字幕模型...")
    try:
        from semsub.core.models import WordItem, SubtitleLine

        word = WordItem("Hello", 0.0, 0.5)
        line = SubtitleLine(
            index=1,
            start=0.0,
            end=1.0,
            text="Hello world",
            words=[word]
        )

        print(f"✓ 模型创建成功")
        print(f"  - 字幕行: {line.text}")
        print(f"  - 时长: {line.duration}s")
        print(f"  - SRT 格式:\n{line.to_srt()}")
        return True
    except Exception as e:
        print(f"✗ 模型测试失败: {e}")
        return False

# 测试 CLI 导入
def test_cli():
    print("\n测试 CLI...")
    try:
        from semsub.cli.main import cli
        print("✓ CLI 导入成功")
        return True
    except Exception as e:
        print(f"✗ CLI 导入失败: {e}")
        return False

# 测试 GUI 导入
def test_gui():
    print("\n测试 GUI...")
    try:
        # GUI 需要 Qt，可能无法在无头环境运行
        from semsub.gui.main_window import MainWindow
        print("✓ GUI 导入成功")
        return True
    except Exception as e:
        print(f"✗ GUI 导入失败: {e}")
        return False

# 测试 LLM 模块
def test_llm():
    print("\n测试 LLM 模块...")
    try:
        from semsub.core.llm import LLMConfig, LLMOutputMode
        from semsub.core.llm.openai_compatible import OpenAICompatibleProvider
        from semsub.core.prompts import PromptManager

        config = LLMConfig()
        print(f"✓ LLM 配置创建成功")

        manager = PromptManager()
        templates = manager.list_templates()
        print(f"✓ 提示词模板加载成功: {list(templates.keys())}")
        return True
    except Exception as e:
        print(f"✗ LLM 测试失败: {e}")
        return False

def test_config_manager():
    """测试配置管理器"""
    print("\n测试配置管理器...")
    try:
        from semsub.core.config_manager import ConfigManager, get_config_manager
        from semsub.core.config import PipelineConfig

        manager = ConfigManager()

        # 测试加载默认配置
        config = manager.load()
        assert isinstance(config, PipelineConfig)
        print(f"✓ 配置加载成功")

        # 测试获取配置值
        value = manager.get_config_value(config, "vad.threshold")
        assert value == 0.5
        print(f"✓ 获取配置值成功: vad.threshold = {value}")

        # 测试设置配置值
        manager.set_config_value(config, "vad.threshold", 0.8)
        assert config.vad.threshold == 0.8
        print(f"✓ 设置配置值成功")

        # 测试预设列表
        presets = manager.list_presets()
        print(f"✓ 预设列表: {list(presets.keys())}")

        return True
    except Exception as e:
        print(f"✗ 配置管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("SemSub 新架构测试")
    print("=" * 50)

    results = []
    results.append(("导入", test_imports()))
    results.append(("配置", test_config()))
    results.append(("模型", test_models()))
    results.append(("CLI", test_cli()))
    results.append(("GUI", test_gui()))
    results.append(("LLM", test_llm()))
    results.append(("配置管理器", test_config_manager()))

    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{name}: {status}")

    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"\n总计: {passed}/{total} 通过")
