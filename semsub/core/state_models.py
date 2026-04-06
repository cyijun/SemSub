"""
工作区状态数据模型
使用 Pydantic 进行类型验证
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Literal
from pathlib import Path

from pydantic import BaseModel, Field


class StageStatus(str, Enum):
    """阶段状态"""
    PENDING = "pending"      # 等待执行
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    SKIPPED = "skipped"      # 已跳过


class ArtifactSpec(BaseModel):
    """Artifact 规格定义"""
    type: Literal["json", "wav", "txt", "srt", "vtt", "yaml"]
    description: str = ""
    schema_version: str = "1.0"


class InputSpec(BaseModel):
    """输入规格"""
    dependencies: List[str] = Field(default_factory=list)  # 依赖的阶段 ID
    parameters: Dict[str, Any] = Field(default_factory=dict)  # 参数定义


class OutputSpec(BaseModel):
    """输出规格"""
    artifacts: Dict[str, ArtifactSpec] = Field(default_factory=dict)


class ArtifactInfo(BaseModel):
    """Artifact 信息"""
    path: str
    type: str
    size_bytes: Optional[int] = None
    checksum: Optional[str] = None  # 文件哈希，用于验证


class StageProgressInfo(BaseModel):
    """阶段进度信息"""
    current: int = 0
    total: int = 0
    message: str = ""
    percent: float = 0.0  # 0-100


class StageState(BaseModel):
    """单个阶段的状态"""
    stage_id: str
    status: StageStatus = StageStatus.PENDING
    status_message: str = ""  # 状态描述

    # 时间戳
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None  # 执行耗时

    # 进度（仅 running 状态）
    progress: Optional[StageProgressInfo] = None

    # 配置快照（用于检测变更）
    config_hash: Optional[str] = None
    config_snapshot: Dict[str, Any] = Field(default_factory=dict)

    # 输入输出引用
    input_path: str = "input.json"
    output_path: str = "output.json"

    # 检查点（用于断点续传）
    checkpoint_path: Optional[str] = None
    checkpoint_data: Dict[str, Any] = Field(default_factory=dict)

    # 错误信息（仅 failed 状态）
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WorkspaceState(BaseModel):
    """工作区全局状态"""
    version: str = "1.0"

    # 视频信息
    video_path: str
    video_hash: str  # 用于检测视频变更
    video_size: int = 0
    video_mtime: Optional[datetime] = None  # 视频文件修改时间

    # 工作区配置
    config_path: str = "config.yaml"

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # 整体状态
    overall_status: StageStatus = StageStatus.PENDING
    current_stage: Optional[str] = None

    # 各阶段状态
    stages: Dict[str, StageState] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class StageInput(BaseModel):
    """阶段输入定义"""
    stage_id: str
    dependencies: Dict[str, "StageDependency"] = Field(default_factory=dict)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class StageDependency(BaseModel):
    """阶段依赖定义"""
    stage_id: str  # 依赖的阶段
    artifact: str  # artifact 名称
    path: str      # 相对路径


class StageOutput(BaseModel):
    """阶段输出定义"""
    stage_id: str
    status: StageStatus

    # 生成的 artifacts
    artifacts: Dict[str, ArtifactInfo] = Field(default_factory=dict)

    # 执行统计
    statistics: Dict[str, Any] = Field(default_factory=dict)

    # 执行时间
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None


class WorkspaceConfig(BaseModel):
    """工作区配置"""
    location: Literal["video_dir", "centralized"] = "video_dir"
    centralized_path: str = "~/.semsub/workspaces"
    naming: Literal["hash", "basename_hash"] = "basename_hash"

    # 保留策略
    auto_clean: bool = False
    keep_days: int = 7


class PipelineStatus(BaseModel):
    """管道状态摘要"""
    video_path: str
    workspace_path: str
    overall_status: StageStatus
    current_stage: Optional[str]

    stage_summary: Dict[str, tuple[StageStatus, Optional[int]]]  # stage_id -> (status, duration_sec)

    total_duration_ms: Optional[int] = None
    progress_percent: float = 0.0


class StageInfo(BaseModel):
    """阶段信息（用于列出可执行阶段）"""
    stage_id: str
    name: str
    status: StageStatus
    can_execute: bool
    reason: str  # 如果不能执行，说明原因
    dependencies: List[str]


class VideoTask(BaseModel):
    """批量任务中的单个视频任务"""
    video_path: str
    output_path: str  # 目标字幕路径
    status: StageStatus = StageStatus.PENDING
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    workspace_path: Optional[str] = None  # 工作区路径（如果有）

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class BatchProgressInfo(BaseModel):
    """批量任务进度"""
    current_index: int = 0  # 当前处理的视频索引（从0开始）
    total_count: int = 0
    current_video: Optional[str] = None  # 当前处理的视频名
    current_video_status: Optional[PipelineStatus] = None  # 当前视频的详细进度

    completed_count: int = 0
    failed_count: int = 0

    @property
    def percent(self) -> float:
        """整体进度百分比"""
        if self.total_count == 0:
            return 0.0
        # 基础进度：已完成视频占比
        base_progress = self.completed_count / self.total_count
        # 当前视频贡献的进度
        current_progress = 0.0
        if self.current_video_status and self.total_count > 0:
            current_progress = (self.current_video_status.progress_percent / 100) / self.total_count
        return round((base_progress + current_progress) * 100, 1)

    @property
    def is_complete(self) -> bool:
        """是否全部完成"""
        return self.completed_count + self.failed_count >= self.total_count


class BatchResult(BaseModel):
    """批量处理结果"""
    success: bool
    total_count: int
    completed_count: int
    failed_count: int
    tasks: List[VideoTask] = Field(default_factory=list)
    total_duration_ms: int = 0
    error_message: Optional[str] = None  # 如果失败，错误信息


# 解决循环引用
StageInput.model_rebuild()
