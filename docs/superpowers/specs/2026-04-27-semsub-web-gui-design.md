# SemSub Web GUI 设计文档

## 概述

为 SemSub 字幕生成工具设计一个基于 FastAPI + HTMX 的网页 GUI，部署在 tailnet 内网，通过浏览器远程管理字幕生成任务。

## 设计目标

- **远程管理**：通过 tailnet 从任意设备访问服务器上的 SemSub
- **服务器文件选择**：直接浏览服务器文件系统选择视频/SRT 文件，而非上传
- **实时进度**：SSE 推送处理进度、日志流
- **轻量维护**：原生 HTML/JS + HTMX，零构建步骤，维护成本最低

## 技术栈

| 层级 | 技术 | 理由 |
|------|------|------|
| 后端框架 | FastAPI | 高性能、自动 API 文档、原生 SSE 支持 |
| 前端交互 | HTMX | 无 JS 框架依赖，HTML 属性驱动动态加载 |
| 实时通信 | SSE (Server-Sent Events) | 单向服务器推送，比 WebSocket 更简单 |
| 样式 | 原生 CSS + CSS 变量 | 无 CSS 框架依赖，完全自定义主题 |
| 文件浏览 | 后端 API 返回目录列表 | HTMX 渲染文件树 |

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                         Browser                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │ Generate│  │  Batch  │  │ SRT Proc│  │Workspace│  ...  │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘       │
│       │            │            │            │              │
│       └────────────┴────────────┴────────────┘              │
│                    HTMX + SSE                                │
└─────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │    FastAPI App     │
                    │  ┌─────────────┐   │
                    │  │  API Routes │   │
                    │  │  - /api/fs  │   │
                    │  │  - /api/job │   │
                    │  │  - /api/sse │   │
                    │  └─────────────┘   │
                    │  ┌─────────────┐   │
                    │  │ Job Manager │   │
                    │  │ (in-memory) │   │
                    │  └─────────────┘   │
                    └─────────┬─────────┘
                              │
                    ┌─────────┴─────────┐
                    │   SemSub Core      │
                    │  SubtitlePipeline  │
                    │  ProgressReporter  │
                    └───────────────────┘
```

## 目录结构

```
semsub/
└── web/                          # Web GUI 模块
    ├── __init__.py
    ├── main.py                   # FastAPI app 入口
    ├── routes/
    │   ├── __init__.py
    │   ├── pages.py              # HTML 页面路由
    │   ├── api.py                # REST API
    │   └── sse.py                # SSE 进度推送
    ├── static/
    │   ├── css/
    │   │   └── style.css         # 主题样式
    │   └── js/
    │       └── app.js            # 少量原生 JS (SSE 连接等)
    └── templates/
        ├── base.html             # 基础布局（侧边栏 + 主内容区）
        ├── generate.html         # 生成字幕页面
        ├── batch.html            # 批量处理页面
        ├── srt_process.html      # SRT 处理页面
        ├── workspaces.html       # 工作区管理页面
        ├── config.html           # 配置管理页面
        ├── file_picker.html      # 文件选择器组件
        └── progress_panel.html   # 进度面板组件
```

## 主题设计

**Cine-Industrial 电影工业风**

- 主色调：胶片琥珀色 `#f5a623` 作为强调色
- 背景色：深黑 `#0a0a0f`，卡片 `#111118`
- 字体：JetBrains Mono（等宽，代码/日志）+ Noto Sans SC（中文正文）
- 纹理：细微的胶片颗粒噪点 overlay
- 进度条：琥珀色渐变，配合脉冲动画

## 页面设计

### 基础布局 (base.html)

- **侧边栏**（固定 200px）：Logo + 5 个导航项 + GPU 状态
- **主内容区**：HTMX 根据导航动态加载对应页面片段
- **全局 SSE 连接**：连接 `/api/sse`，接收所有任务进度

### 1. 生成字幕 (generate.html)

| 元素 | 说明 |
|------|------|
| 文件选择器 | 输入框 + "浏览"按钮，点击弹出文件选择模态框 |
| 配置表单 | 预设、语言、输出格式、输出路径（2x2 网格）|
| 高级选项 | `<details>` 折叠：最大字符数、最大时长、LLM 开关、跳过已有 |
| 开始按钮 | 主操作按钮，触发 POST `/api/job/generate` |
| 进度面板 | SSE 驱动：阶段名称、百分比、进度条、日志流 |

### 2. 批量处理 (batch.html)

| 元素 | 说明 |
|------|------|
| 目录选择器 | 输入框 + "浏览" + "扫描"按钮 |
| 文件列表 | 表格：复选框、文件名、大小、状态徽章 |
| 批量配置 | 预设、输出目录、选项复选框 |
| 批量进度 | 总体进度条 + 每个文件的状态列表 |

### 3. SRT 处理 (srt_process.html)

| 元素 | 说明 |
|------|------|
| SRT 文件选择器 | 输入框 + "浏览"按钮 |
| LLM 配置 | 处理模式、提供商、响应格式、目标语言 |
| 输出路径 | 可选，默认在原文件名加 `_processed` |
| 进度面板 | LLM 分批处理进度 |

### 4. 工作区 (workspaces.html)

| 元素 | 说明 |
|------|------|
| 工作区卡片列表 | 每个视频一个卡片 |
| 阶段流程图 | 5 个圆形节点 (01-05) + 连接线，颜色表示状态 |
| 操作按钮组 | 继续、重跑某阶段、从某阶段开始、下载字幕、清理、查看日志 |

### 5. 配置 (config.html)

| 分组 | 字段 |
|------|------|
| ASR 模型 | 模型路径、对齐器路径、batch size、device |
| VAD 配置 | 阈值、最小语音/静音时长 |
| 字幕参数 | 最大字符数（中/英）、最大/最小时长、gap 阈值 |
| LLM 配置 | 启用、提供商、base_url、模型、api_key |
| 操作按钮 | 保存、重置默认值、导出配置 |

## API 设计

### 文件系统 API

```
GET  /api/fs/browse?path=/mnt/g/movies        # 列出目录内容
GET  /api/fs/home                             # 获取用户主目录
```

响应：
```json
{
  "current": "/mnt/g/movies",
  "parent": "/mnt/g",
  "items": [
    {"name": "inception.mkv", "type": "file", "size": 2147483648, "ext": ".mkv"},
    {"name": "season1", "type": "dir"},
    {"name": "interstellar.srt", "type": "file", "size": 524288, "ext": ".srt"}
  ]
}
```

### 任务 API

```
POST /api/job/generate          # 创建单视频生成任务
POST /api/job/batch             # 创建批量处理任务
POST /api/job/srt-process       # 创建 SRT 处理任务
POST /api/job/{id}/cancel       # 取消任务
GET  /api/job/{id}/status       # 获取任务状态
GET  /api/job/list              # 列出所有任务
```

### 工作区 API

```
GET  /api/workspaces            # 列出所有工作区
GET  /api/workspace/{path}/status   # 获取工作区状态
POST /api/workspace/{path}/run-stage?stage=03&force=true
POST /api/workspace/{path}/clean
GET  /api/workspace/{path}/log  # 获取阶段日志
GET  /api/workspace/{path}/download  # 下载字幕文件
```

### 配置 API

```
GET  /api/config                # 获取当前配置
POST /api/config                # 保存配置
POST /api/config/reset          # 重置为默认
GET  /api/config/export         # 导出为 YAML
```

### SSE 进度推送

```
GET /api/sse?client_id=xxx      # SSE 连接，接收所有任务进度事件
```

事件格式：
```json
{
  "type": "progress",
  "job_id": "job-123",
  "stage": "03_asr_transcribe",
  "current": 12,
  "total": 18,
  "percent": 67,
  "message": "处理第 12/18 段",
  "log": "[14:33:12] 处理第 12/18 段..."
}
```

## 数据流

### 单视频生成流程

```
用户选择文件 → 填写配置 → 点击"开始"
  ↓
POST /api/job/generate → 创建 Job，启动后台线程
  ↓
后台线程调用 SubtitlePipeline.generate(video_path, config)
  ↓
自定义 ProgressReporter 捕获进度
  ↓
ProgressReporter → 写入 JobManager 的内存状态
  ↓
SSE endpoint 轮询 JobManager → 推送到浏览器
  ↓
浏览器 HTMX 更新进度面板
```

### 批量处理流程

```
用户选择目录 → 扫描 → 选择文件 → 填写配置 → 点击"批量开始"
  ↓
POST /api/job/batch → 创建 BatchJob，启动后台线程
  ↓
后台线程循环处理每个视频（串行）
  ↓
每个视频完成后更新 BatchJob 状态
  ↓
SSE 推送每个视频的进度 + 总体进度
```

## 任务管理 (JobManager)

```python
class JobManager:
    """内存中的任务管理器"""

    def create_job(type, params) -> str:
        """创建任务，返回 job_id"""

    def get_job(job_id) -> JobState:
        """获取任务状态"""

    def cancel_job(job_id):
        """取消任务（通过 ProgressReporter.cancel()）"""

    def list_jobs() -> List[JobState]:
        """列出所有任务"""

    def cleanup_old_jobs(max_age_hours=24):
        """清理过期任务"""
```

## 进度报告 (WebProgressReporter)

```python
class WebProgressReporter(ProgressReporter):
    """将进度写入 JobManager，供 SSE 推送"""

    def __init__(self, job_id: str, job_manager: JobManager):
        self.job_id = job_id
        self.job_manager = job_manager

    def on_progress(self, progress: StageProgress):
        self.job_manager.update_progress(self.job_id, progress)

    def on_log(self, message: str, level: str = "info"):
        self.job_manager.append_log(self.job_id, message, level)

    def check_cancelled(self):
        if self.job_manager.is_cancelled(self.job_id):
            raise CancellationError("操作已取消")
```

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| 文件不存在 | API 返回 404，前端显示错误提示 |
| GPU 内存不足 | ProgressReporter.on_error() → SSE 推送错误 → 前端显示红色错误卡片 |
| 任务取消 | ProgressReporter.check_cancelled() 抛出 CancellationError，前端显示"已取消" |
| 配置无效 | FastAPI 校验错误，前端显示字段级错误提示 |
| SSE 断开 | 前端自动重连（指数退避）|

## 安全考量

- **文件访问限制**：文件浏览 API 限制在配置的白名单目录内（默认用户主目录），禁止访问 `/etc`、`/root` 等敏感路径
- **API Key 隐藏**：配置页面中 API key 以 password 类型输入框显示，后端返回时脱敏（`sk-****`）
- **CSRF 防护**：FastAPI 的 SessionMiddleware + SameSite cookie
- **无认证**：tailnet 内网环境，依赖网络层隔离

## 部署

```bash
# 启动 Web GUI
python -m semsub.web

# 或指定端口
python -m semsub.web --port 8080 --host 0.0.0.0
```

入口点 (`semsub/web/__main__.py`)：
```python
import uvicorn
from .main import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

## 扩展性

- **多用户**：当前为单用户设计。如需多用户，可添加简单的 HTTP Basic Auth
- **任务持久化**：当前任务存在内存中。如需持久化，可添加 SQLite 存储 JobState
- **队列**：当前后台线程直接运行。如需并发限制，可添加 asyncio 队列

## 依赖

```
fastapi
uvicorn
jinja2          # FastAPI 模板渲染
python-multipart # 文件上传（备用）
```

无需额外前端依赖（HTMX 通过 CDN 引入）。
