"""
SemSub Gradio GUI 端到端测试 - 使用样例视频测试各个功能

使用方法:
    pytest tests/test_gradio_e2e.py -v -s
    pytest tests/test_gradio_e2e.py::TestHomePageE2E -v -s

前置条件:
    - GUI 服务运行在 http://localhost:7860
    - cutted_demo.mp4 存在于项目根目录

注意:
    实际视频处理需要很长时间，此测试主要验证 UI 交互流程
"""

import time
from pathlib import Path
from playwright.sync_api import Page, expect, Browser
import pytest

BASE_URL = "http://localhost:7860"
VIDEO_PATH = Path("/mnt/d/temp/SemSub/cutted_demo.mp4")


@pytest.fixture(scope="session")
def browser_context():
    """启动浏览器上下文"""
    from playwright.sync_api import sync_playwright

    p = sync_playwright().start()
    browser = p.chromium.launch(
        executable_path="/tmp/playwright-chrome/chrome-linux/chrome",
        headless=True,
    )
    yield browser
    browser.close()
    p.stop()


@pytest.fixture
def page(browser_context: Browser):
    """创建新页面实例"""
    page = browser_context.new_page()
    page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)
    yield page
    page.close()


@pytest.fixture
def video_file():
    """确认视频文件存在"""
    assert VIDEO_PATH.exists(), f"视频文件不存在: {VIDEO_PATH}"
    assert VIDEO_PATH.stat().st_size > 0, f"视频文件为空: {VIDEO_PATH}"
    return VIDEO_PATH


class TestHomePageE2E:
    """首页端到端测试 - 使用真实视频"""

    def test_upload_video_and_start_processing(self, page: Page, video_file: Path):
        """测试上传视频并开始处理流程"""
        print(f"\n📹 测试视频: {video_file.name} ({video_file.stat().st_size / 1024 / 1024:.1f} MB)")

        # 1. 上传视频文件
        file_input = page.locator('input[type="file"]').first
        file_input.set_input_files(str(video_file))
        print("✅ 视频文件已上传")

        # 等待文件上传完成
        page.wait_for_timeout(2000)

        # 2. 展开高级选项
        accordion = page.locator("text=高级选项").first
        accordion.click()
        page.wait_for_timeout(500)
        print("✅ 展开高级选项")

        # 3. 选择场景预设
        # Gradio Dropdown 使用自定义渲染，点击展开选项
        preset_dropdown = page.locator('label:has-text("场景预设") + div, [data-testid="dropdown"]').first
        if preset_dropdown.count() > 0:
            preset_dropdown.click()
            page.wait_for_timeout(300)
            # 选择"电影"预设
            movie_option = page.locator('text=电影').filter(has_text="电影").first
            if movie_option.count() > 0:
                movie_option.click()
                print("✅ 选择电影预设")

        # 4. 检查输出格式
        format_dropdown = page.locator('label:has-text("输出格式") + div').first
        if format_dropdown.count() > 0:
            print("✅ 输出格式选项存在")

        # 5. 截图记录状态
        page.screenshot(path="/tmp/e2e_home_ready.png")
        print("📸 截图已保存: /tmp/e2e_home_ready.png")

        # 6. 点击开始生成按钮（不实际执行，因为处理时间太长）
        start_btn = page.locator('button:has-text("开始生成字幕")')
        expect(start_btn).to_be_visible()
        expect(start_btn).to_be_enabled()
        print("✅ 开始生成按钮可用")

        # 注：不实际点击开始，因为视频处理需要很长时间
        # 在真实场景中，点击后会显示进度区域

    def test_advanced_options_interaction(self, page: Page, video_file: Path):
        """测试高级选项交互"""
        # 上传视频
        file_input = page.locator('input[type="file"]').first
        file_input.set_input_files(str(video_file))
        page.wait_for_timeout(1000)

        # 展开高级选项
        accordion = page.locator("text=高级选项").first
        accordion.click()
        page.wait_for_timeout(500)

        # 测试 LLM 选项
        llm_checkbox = page.locator('input[type="checkbox"]').filter(
            has=page.locator('xpath=..').filter(has_text="LLM")
        ).first

        # 检查 LLM 相关选项
        llm_text = page.locator("text=启用 LLM 后处理")
        if llm_text.count() > 0:
            print("✅ LLM 后处理选项存在")

            # 点击启用 LLM
            llm_text.click()
            page.wait_for_timeout(300)

            # 检查 LLM 配置是否显示
            llm_config = page.locator("text=LLM 提供商")
            if llm_config.count() > 0:
                print("✅ LLM 配置区域已显示")

        # 截图
        page.screenshot(path="/tmp/e2e_advanced_options.png")
        print("📸 截图已保存: /tmp/e2e_advanced_options.png")


class TestBatchPageE2E:
    """批量处理页端到端测试"""

    def test_add_multiple_files(self, page: Page, video_file: Path):
        """测试添加多个文件到批量队列"""
        # 切换到批量处理 Tab
        batch_tab = page.locator('[role="tab"]:has-text("批量处理")')
        batch_tab.click()
        page.wait_for_timeout(1000)
        print("\n📁 进入批量处理页")

        # 添加视频文件
        file_input = page.locator('input[type="file"]').first
        file_input.set_input_files(str(video_file))
        page.wait_for_timeout(1500)
        print(f"✅ 添加文件: {video_file.name}")

        # 检查文件是否显示在列表中
        file_name_display = page.locator(f"text={video_file.name}")
        if file_name_display.count() > 0:
            print("✅ 文件显示在列表中")

        # 检查统计信息更新
        stats = page.locator("text=总文件数").first
        if stats.count() > 0:
            print("✅ 统计信息显示")

        # 截图
        page.screenshot(path="/tmp/e2e_batch_files.png")
        print("📸 截图已保存: /tmp/e2e_batch_files.png")

    def test_batch_settings(self, page: Page, video_file: Path):
        """测试批量设置选项"""
        # 进入批量处理页
        batch_tab = page.locator('[role="tab"]:has-text("批量处理")')
        batch_tab.click()
        page.wait_for_timeout(500)

        # 添加文件
        file_input = page.locator('input[type="file"]').first
        file_input.set_input_files(str(video_file))
        page.wait_for_timeout(1000)

        # 检查批量设置选项
        settings_checks = [
            ("跳过已有字幕", "跳过已有字幕的视频"),
            ("出错时继续", "出错时继续处理其他"),
            ("LLM 后处理", "启用 LLM 后处理"),
        ]

        for name, text in settings_checks:
            elem = page.locator(f"text={text}").first
            if elem.count() > 0:
                print(f"✅ {name} 选项存在")

        # 检查开始批量处理按钮
        start_btn = page.locator('button:has-text("开始批量处理")')
        expect(start_btn).to_be_visible()
        print("✅ 开始批量处理按钮可用")

        page.screenshot(path="/tmp/e2e_batch_settings.png")
        print("📸 截图已保存: /tmp/e2e_batch_settings.png")


class TestSRTPageE2E:
    """SRT 处理页端到端测试"""

    def test_srt_upload_interface(self, page: Page):
        """测试 SRT 上传界面"""
        # 切换到 SRT 处理 Tab
        srt_tab = page.locator('[role="tab"]:has-text("SRT")')
        srt_tab.click()
        page.wait_for_timeout(1000)
        print("\n📝 进入 SRT 处理页")

        # 检查 SRT 文件上传
        expect(page.locator("text=SRT 字幕处理")).to_be_visible()
        expect(page.locator("text=选择 SRT 字幕文件")).to_be_visible()
        print("✅ SRT 上传界面正常")

        # 检查处理模式选项
        modes = ["纠错优化", "翻译成其他语言", "双语字幕"]
        for mode in modes:
            elem = page.locator(f"text={mode}").first
            if elem.count() > 0:
                print(f"✅ 处理模式 '{mode}' 存在")

        page.screenshot(path="/tmp/e2e_srt_page.png")
        print("📸 截图已保存: /tmp/e2e_srt_page.png")

    def test_srt_llm_config(self, page: Page):
        """测试 SRT 处理页的 LLM 配置"""
        # 进入 SRT 页
        srt_tab = page.locator('[role="tab"]:has-text("SRT")')
        srt_tab.click()
        page.wait_for_timeout(500)

        # 展开 LLM 配置
        llm_accordion = page.locator("text=LLM 配置").first
        llm_accordion.click()
        page.wait_for_timeout(800)
        print("✅ 展开 LLM 配置")

        # 检查 LLM 配置字段
        config_fields = ["Base URL", "API Key", "模型", "批次大小", "Temperature"]
        for field in config_fields:
            elem = page.locator(f"text={field}").first
            if elem.count() > 0:
                print(f"✅ LLM 配置字段 '{field}' 存在")

        # 检查模型选择下拉框
        model_dropdown = page.locator('label:has-text("模型") + div').first
        if model_dropdown.count() > 0:
            print("✅ 模型选择下拉框存在")

        page.screenshot(path="/tmp/e2e_srt_llm_config.png")
        print("📸 截图已保存: /tmp/e2e_srt_llm_config.png")


class TestSettingsPageE2E:
    """设置页端到端测试"""

    def test_settings_navigation(self, page: Page):
        """测试设置页导航"""
        # 切换到设置 Tab
        settings_tab = page.locator('[role="tab"]:has-text("设置")')
        settings_tab.click()
        page.wait_for_timeout(1000)
        print("\n⚙️ 进入设置页")

        # 检查所有设置标签
        setting_tabs = ["ASR 模型", "VAD 参数", "字幕优化", "LLM 配置"]
        for tab_name in setting_tabs:
            tab = page.get_by_role("tab", name=tab_name)
            if tab.count() > 0:
                print(f"✅ 设置标签 '{tab_name}' 存在")

        page.screenshot(path="/tmp/e2e_settings.png")
        print("📸 截图已保存: /tmp/e2e_settings.png")

    def test_asr_settings(self, page: Page):
        """测试 ASR 模型设置"""
        # 进入设置页
        settings_tab = page.locator('[role="tab"]:has-text("设置")')
        settings_tab.click()
        page.wait_for_timeout(500)

        # 切换到 ASR 模型标签
        asr_tab = page.get_by_role("tab", name="ASR 模型")
        asr_tab.click()
        page.wait_for_timeout(500)
        print("✅ 切换到 ASR 模型设置")

        # 检查 ASR 配置字段
        asr_fields = ["ASR 模型路径", "对齐模型路径", "设备", "批次大小"]
        for field in asr_fields:
            elem = page.locator(f"text={field}").first
            if elem.count() > 0:
                print(f"✅ ASR 配置字段 '{field}' 存在")

        # 检查输入框
        inputs = page.locator('input').all()
        print(f"✅ ASR 页有 {len(inputs)} 个输入框")

        page.screenshot(path="/tmp/e2e_settings_asr.png")
        print("📸 截图已保存: /tmp/e2e_settings_asr.png")

    def test_vad_settings(self, page: Page):
        """测试 VAD 参数设置"""
        # 进入设置页
        settings_tab = page.locator('[role="tab"]:has-text("设置")')
        settings_tab.click()
        page.wait_for_timeout(500)

        # 切换到 VAD 参数标签
        vad_tab = page.get_by_role("tab", name="VAD 参数")
        vad_tab.click()
        page.wait_for_timeout(500)
        print("✅ 切换到 VAD 参数设置")

        # 检查 VAD 配置字段
        vad_fields = ["阈值", "最小语音时长", "最小静音时长"]
        for field in vad_fields:
            elem = page.locator(f"text={field}").first
            if elem.count() > 0:
                print(f"✅ VAD 配置字段 '{field}' 存在")

        # 检查滑块
        sliders = page.locator('input[type="range"]').all()
        print(f"✅ VAD 页有 {len(sliders)} 个滑块")

        page.screenshot(path="/tmp/e2e_settings_vad.png")
        print("📸 截图已保存: /tmp/e2e_settings_vad.png")

    def test_save_and_reset_buttons(self, page: Page):
        """测试保存和重置按钮"""
        # 进入设置页
        settings_tab = page.locator('[role="tab"]:has-text("设置")')
        settings_tab.click()
        page.wait_for_timeout(500)

        # 检查按钮
        save_btn = page.locator('button:has-text("保存配置")')
        reset_btn = page.locator('button:has-text("重置为默认")')
        export_btn = page.locator('button:has-text("导出配置")')

        expect(save_btn).to_be_visible()
        print("✅ 保存配置按钮存在")

        if reset_btn.count() > 0:
            print("✅ 重置为默认按钮存在")

        if export_btn.count() > 0:
            print("✅ 导出配置按钮存在")


class TestWorkspacesPageE2E:
    """工作区页端到端测试"""

    def test_workspaces_list(self, page: Page):
        """测试工作区列表显示"""
        # 切换到工作区 Tab
        ws_tab = page.locator('[role="tab"]:has-text("工作区")')
        ws_tab.click()
        page.wait_for_timeout(1000)
        print("\n🗂️ 进入工作区管理页")

        # 检查页面元素
        expect(page.locator("text=工作区管理")).to_be_visible()
        print("✅ 工作区管理标题存在")

        # 检查刷新按钮
        refresh_btn = page.locator("text=刷新列表")
        expect(refresh_btn).to_be_visible()
        print("✅ 刷新列表按钮存在")

        # 点击刷新
        refresh_btn.click()
        page.wait_for_timeout(1000)
        print("✅ 刷新按钮可点击")

        page.screenshot(path="/tmp/e2e_workspaces.png")
        print("📸 截图已保存: /tmp/e2e_workspaces.png")


class TestFullWorkflow:
    """完整工作流程测试"""

    def test_complete_user_journey(self, page: Page, video_file: Path):
        """测试完整用户旅程：上传 -> 配置 -> 预览各页面"""
        print(f"\n🚀 开始完整用户旅程测试")
        print(f"📹 使用视频: {video_file.name}")

        # Step 1: 首页上传视频
        print("\n📍 Step 1: 首页")
        file_input = page.locator('input[type="file"]').first
        file_input.set_input_files(str(video_file))
        page.wait_for_timeout(1500)
        print("✅ 视频已上传到首页")

        # 展开高级选项并配置
        accordion = page.locator("text=高级选项").first
        accordion.click()
        page.wait_for_timeout(500)

        # Step 2: 批量处理页
        print("\n📍 Step 2: 批量处理页")
        batch_tab = page.locator('[role="tab"]:has-text("批量处理")')
        batch_tab.click()
        page.wait_for_timeout(1000)

        # 在批量页添加文件
        batch_file_input = page.locator('input[type="file"]').first
        batch_file_input.set_input_files(str(video_file))
        page.wait_for_timeout(1500)
        print("✅ 文件添加到批量队列")

        # Step 3: SRT 处理页
        print("\n📍 Step 3: SRT 处理页")
        srt_tab = page.locator('[role="tab"]:has-text("SRT")')
        srt_tab.click()
        page.wait_for_timeout(1000)
        print("✅ 浏览 SRT 处理页")

        # Step 4: 工作区页
        print("\n📍 Step 4: 工作区页")
        ws_tab = page.locator('[role="tab"]:has-text("工作区")')
        ws_tab.click()
        page.wait_for_timeout(1000)

        # 刷新工作区列表
        refresh_btn = page.locator("text=刷新列表")
        refresh_btn.click()
        page.wait_for_timeout(1000)
        print("✅ 刷新工作区列表")

        # Step 5: 设置页
        print("\n📍 Step 5: 设置页")
        settings_tab = page.locator('[role="tab"]:has-text("设置")')
        settings_tab.click()
        page.wait_for_timeout(1000)

        # 浏览各个设置标签
        for tab_name in ["VAD 参数", "字幕优化", "LLM 配置"]:
            tab = page.get_by_role("tab", name=tab_name)
            if tab.count() > 0:
                tab.click()
                page.wait_for_timeout(500)
                print(f"✅ 浏览 {tab_name} 设置")

        # 回到 ASR 标签
        asr_tab = page.get_by_role("tab", name="ASR 模型")
        asr_tab.click()
        page.wait_for_timeout(500)

        # 最终截图
        page.screenshot(path="/tmp/e2e_complete_journey.png", full_page=True)
        print("\n📸 完整旅程截图已保存: /tmp/e2e_complete_journey.png")

        print("\n✅ 完整用户旅程测试完成!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
