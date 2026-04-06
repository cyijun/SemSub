"""
管道阶段抽象基类 - 支持 Workspace
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar, Optional, Dict, List

from ..progress import ProgressReporter
from ..workspace import StageContext


T = TypeVar('T')
U = TypeVar('U')


class PipelineStageBase(ABC, Generic[T, U]):
    """管道阶段抽象基类（传统接口，向后兼容）"""

    name: str = ""

    @abstractmethod
    def execute(self, input_data: T, reporter: Optional[ProgressReporter] = None) -> U:
        """
        执行阶段

        Args:
            input_data: 输入数据
            reporter: 进度报告器（可选）

        Returns:
            输出数据
        """
        pass

    def cleanup(self):
        """清理资源（可选重写）"""
        pass


class WorkspacePipelineStage(ABC):
    """支持 Workspace 的管道阶段基类（新接口）"""

    name: str = ""
    stage_id: str = ""  # 如 "01_audio_extract"

    def get_input_spec(self) -> Dict[str, Any]:
        """
        定义输入契约

        Returns:
            {
                "dependencies": ["stage_id"],  # 依赖的阶段
                "artifacts": {  # 输入 artifacts
                    "audio": {"type": "wav"},
                    "segments": {"type": "json"}
                },
                "parameters": {  # 参数定义
                    "batch_size": int,
                    "language": Optional[str]
                }
            }
        """
        return {
            "dependencies": [],
            "artifacts": {},
            "parameters": {}
        }

    def get_output_spec(self) -> Dict[str, Any]:
        """
        定义输出契约

        Returns:
            {
                "artifacts": {  # 输出 artifacts
                    "transcripts": {"type": "json"},
                    "audio": {"type": "wav"}
                }
            }
        """
        return {
            "artifacts": {}
        }

    @abstractmethod
    def execute(
        self,
        ctx: StageContext,
        reporter: Optional[ProgressReporter] = None
    ) -> Dict[str, Any]:
        """
        执行阶段（使用 Workspace 上下文）

        Args:
            ctx: 阶段上下文，提供输入/输出/检查点管理
            reporter: 进度报告器

        Returns:
            输出 artifacts 字典，如 {"transcripts": data, "statistics": {...}}
        """
        pass

    def resume(
        self,
        ctx: StageContext,
        checkpoint: Dict[str, Any],
        reporter: Optional[ProgressReporter] = None
    ) -> Dict[str, Any]:
        """
        从检查点恢复（可选实现）

        默认实现：清空状态重新执行

        Args:
            ctx: 阶段上下文
            checkpoint: 检查点数据
            reporter: 进度报告器

        Returns:
            输出 artifacts 字典
        """
        # 默认实现：重新执行
        return self.execute(ctx, reporter)

    def can_resume(self, checkpoint: Dict[str, Any]) -> bool:
        """
        检查是否可以从给定检查点恢复

        Args:
            checkpoint: 检查点数据

        Returns:
            是否可以恢复
        """
        return False

    def cleanup(self):
        """清理资源（可选重写）"""
        pass


# 别名，方便导入
PipelineStage = WorkspacePipelineStage
