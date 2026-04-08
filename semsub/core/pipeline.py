"""
字幕生成管道主类
整合所有处理阶段，支持 Workspace 和分段执行
"""

from pathlib import Path
from typing import Optional, List, Dict, Any

from .config import PipelineConfig
from .models import SubtitleLine
from .progress import ProgressReporter, SilentProgressReporter, PipelineStage
from .workspace import WorkspaceManager, Workspace, StageContext
from .state_models import StageStatus, StageDependency, PipelineStatus, StageInfo
from .stages import (
    AudioExtractStage,
    VADSplitStage,
    ASRTranscribeStage,
    SubtitleOptimizeStage,
    LLMPostprocessStage,
    STAGE_ORDER,
    STAGE_DEPENDENCIES,
    STAGE_NAMES,
    STAGE_TO_ENUM_MAP,
)
from .merger import save_subtitles
from .resource_checker import ResourceChecker


def _stage_id_to_enum(stage_id: str) -> PipelineStage:
    """将阶段 ID 转换为 PipelineStage 枚举值"""
    enum_name = STAGE_TO_ENUM_MAP.get(stage_id, "SUBTITLE_OPTIMIZE")
    return getattr(PipelineStage, enum_name, PipelineStage.SUBTITLE_OPTIMIZE)


class StageExecutor:
    """阶段执行器 - 处理单个阶段的执行和状态流转"""

    STAGE_MAP = {
        "01_audio_extract": AudioExtractStage,
        "02_vad_split": VADSplitStage,
        "03_asr_transcribe": ASRTranscribeStage,
        "04_subtitle_optimize": SubtitleOptimizeStage,
        "05_llm_postprocess": LLMPostprocessStage,
    }

    def __init__(self, workspace: Workspace, stage_id: str, config: PipelineConfig):
        self.workspace = workspace
        self.stage_id = stage_id
        self.config = config
        self.stage_impl = self._create_stage_impl()

    def _create_stage_impl(self):
        """创建阶段实现实例"""
        stage_class = self.STAGE_MAP.get(self.stage_id)
        if stage_class is None:
            raise ValueError(f"未知的阶段 ID: {self.stage_id}")

        # 根据阶段类型传递配置
        if self.stage_id == "01_audio_extract":
            return stage_class()
        elif self.stage_id == "02_vad_split":
            return stage_class(self.config.vad)
        elif self.stage_id == "03_asr_transcribe":
            return stage_class(self.config.asr)
        elif self.stage_id == "04_subtitle_optimize":
            return stage_class(self.config.subtitle)
        elif self.stage_id == "05_llm_postprocess":
            return stage_class(self.config.llm)

    def can_execute(self) -> tuple[bool, str]:
        """检查是否可以执行

        Returns:
            (是否可以执行, 原因)
        """
        stage = self.workspace.get_stage(self.stage_id)

        # 检查当前状态
        if stage.state.status == StageStatus.RUNNING:
            return False, "阶段正在执行中"

        # 检查依赖
        satisfied, reason = self.workspace.check_dependencies_satisfied(self.stage_id)
        if not satisfied:
            return False, reason

        return True, ""

    def prepare_input(self) -> Dict[str, StageDependency]:
        """准备输入依赖定义"""
        deps = {}
        stage_deps = self.workspace.get_stage_dependencies(self.stage_id)

        for dep_stage_id in stage_deps:
            dep_stage = self.workspace.get_stage(dep_stage_id)
            output_def = dep_stage.load_output()

            if output_def:
                for artifact_name in output_def.artifacts.keys():
                    deps[artifact_name] = StageDependency(
                        stage_id=dep_stage_id,
                        artifact=artifact_name,
                        path=f"../{dep_stage_id}/{output_def.artifacts[artifact_name].path}"
                    )

        return deps

    def execute(self, reporter: Optional[ProgressReporter] = None, resume: bool = False) -> Any:
        """执行阶段"""
        stage = self.workspace.get_stage(self.stage_id)
        ctx = stage

        # 检查是否可以执行
        can_exec, reason = self.can_execute()
        if not can_exec:
            raise RuntimeError(f"无法执行阶段 {self.stage_id}: {reason}")

        # 准备输入
        deps = self.prepare_input()

        # 获取阶段配置参数
        params = self._get_stage_params()

        # 保存输入定义
        ctx.save_input(deps, params)

        # 更新状态为 running
        self.workspace.update_stage_status(
            self.stage_id,
            StageStatus.RUNNING,
            message="正在执行..."
        )

        try:
            # 检查检查点
            checkpoint = ctx.load_checkpoint() if resume else None

            if resume and checkpoint and self.stage_impl.can_resume(checkpoint):
                result = self.stage_impl.resume(ctx, checkpoint, reporter)
            else:
                result = self.stage_impl.execute(ctx, reporter)

            # 更新状态为 completed（这会更新 ctx.state）
            self.workspace.update_stage_status(
                self.stage_id,
                StageStatus.COMPLETED,
                message="执行完成"
            )

            # 保存输出（使用更新后的状态）
            ctx.save_output(result.get("artifacts", {}), result.get("statistics", {}))

            return result

        except Exception as e:
            # 更新状态为 failed
            import traceback
            self.workspace.update_stage_status(
                self.stage_id,
                StageStatus.FAILED,
                message=f"执行失败: {str(e)}",
                error_message=str(e),
                error_traceback=traceback.format_exc()
            )
            raise

        finally:
            # 确保清理资源，防止 GPU 内存泄漏
            self.stage_impl.cleanup()

    def _get_stage_params(self) -> Dict[str, Any]:
        """获取阶段的配置参数"""
        if self.stage_id == "01_audio_extract":
            return {"sample_rate": 16000}
        elif self.stage_id == "02_vad_split":
            return {
                "threshold": self.config.vad.threshold,
                "min_speech_duration_ms": self.config.vad.min_speech_duration_ms,
                "min_silence_duration_ms": self.config.vad.min_silence_duration_ms,
                "sample_rate": 16000
            }
        elif self.stage_id == "03_asr_transcribe":
            return {
                "batch_size": self.config.asr.batch_size,
                "language": self.config.asr.language,
                "model_path": self.config.asr.model_path,
                "aligner_path": self.config.asr.aligner_path
            }
        elif self.stage_id == "04_subtitle_optimize":
            return {
                "max_chars": self.config.subtitle.max_chars,
                "max_duration": self.config.subtitle.max_duration,
                "min_duration": self.config.subtitle.min_duration,
                "gap_threshold": self.config.subtitle.gap_threshold
            }
        elif self.stage_id == "05_llm_postprocess":
            return {
                "enabled": self.config.llm.enabled,
                "provider": self.config.llm.provider,
                "model": self.config.llm.model,
                "batch_size": self.config.llm.batch_size,
                "output_mode": self.config.llm.output_mode
            }
        return {}


class SubtitlePipeline:
    """支持 Workspace 和分段执行的字幕生成管道"""

    STAGE_ORDER = STAGE_ORDER

    def __init__(
        self,
        config: PipelineConfig,
        workspace: Optional[Workspace] = None,
        workspace_dir: Optional[Path] = None
    ):
        self.config = config
        self.workspace = workspace
        self.workspace_dir = workspace_dir

    def _get_workspace(self, video_path: Path) -> Workspace:
        """获取或创建工作区"""
        if self.workspace is not None:
            return self.workspace

        manager = WorkspaceManager(video_path, self.workspace_dir)

        if manager.exists():
            return manager.open()
        else:
            return manager.initialize(self.config)

    def generate(
        self,
        video_path: Path,
        output_path: Optional[Path] = None,
        reporter: Optional[ProgressReporter] = None,
        start_from: Optional[str] = None,  # 从指定阶段开始
        stop_at: Optional[str] = None,      # 执行到指定阶段停止
        force: bool = False,                # 强制重新执行
    ) -> Path:
        """
        执行管道（支持分段）

        Args:
            video_path: 输入视频路径
            output_path: 输出字幕路径（默认与视频同名）
            reporter: 进度报告器（可选）
            start_from: 从指定阶段开始执行
            stop_at: 执行到指定阶段停止
            force: 强制重新执行（使下游阶段失效）

        Returns:
            输出字幕文件路径
        """
        if reporter is None:
            reporter = SilentProgressReporter()

        video_path = Path(video_path)
        if output_path is None:
            output_path = video_path.with_suffix(f".{self.config.output.format}")
        else:
            output_path = Path(output_path)

        # 资源预检查
        reporter.on_log("检查系统资源...")
        resource_check = ResourceChecker.preflight_check(video_path, output_path.parent)
        if not resource_check.passed:
            raise RuntimeError(f"资源检查失败: {resource_check.message}")
        reporter.on_log(resource_check.message)

        # 获取工作区
        workspace = self._get_workspace(video_path)

        # 获取执行范围
        start_idx = 0
        stop_idx = len(self.STAGE_ORDER)

        if start_from:
            try:
                start_idx = self.STAGE_ORDER.index(start_from)
            except ValueError:
                raise ValueError(f"无效的起始阶段: {start_from}")

            # 如果强制重新执行，使下游阶段失效
            if force:
                workspace.invalidate_downstream_stages(start_from)

        if stop_at:
            try:
                stop_idx = self.STAGE_ORDER.index(stop_at) + 1
            except ValueError:
                raise ValueError(f"无效的停止阶段: {stop_at}")

        # 获取要执行的阶段列表
        stages_to_run = self.STAGE_ORDER[start_idx:stop_idx]

        current_stage_id = None
        try:
            # 获取工作区锁
            with workspace.acquire_lock(timeout=5):
                # 执行各阶段
                for stage_id in stages_to_run:
                    current_stage_id = stage_id
                    executor = StageExecutor(workspace, stage_id, self.config)

                    # 检查是否可以执行
                    can_exec, reason = executor.can_execute()
                    if not can_exec:
                        if force and workspace.get_stage(stage_id).state.status == StageStatus.COMPLETED:
                            # 强制重新执行
                            pass
                        else:
                            raise RuntimeError(f"无法执行阶段 {stage_id}: {reason}")

                    # 执行阶段
                    reporter.on_log(f"开始执行阶段: {stage_id}")
                    executor.execute(reporter)

                # 生成最终字幕文件
                if stop_at is None or stop_at == "05_llm_postprocess":
                    self._export_subtitles(workspace, output_path, reporter)

                reporter.on_pipeline_complete(str(output_path))
                return output_path

        except Exception as e:
            reporter.on_error(_stage_id_to_enum(current_stage_id), e)
            raise

    def run_stage(
        self,
        video_path: Path,
        stage_id: str,
        reporter: Optional[ProgressReporter] = None,
        force: bool = False,
        resume: bool = False,
    ) -> Any:
        """
        单独执行一个阶段

        Args:
            video_path: 视频路径
            stage_id: 阶段 ID
            reporter: 进度报告器
            force: 强制重新执行
            resume: 从检查点恢复

        Returns:
            阶段执行结果
        """
        if reporter is None:
            reporter = SilentProgressReporter()

        video_path = Path(video_path)
        workspace = self._get_workspace(video_path)

        executor = StageExecutor(workspace, stage_id, self.config)

        # 检查是否可以执行
        can_exec, reason = executor.can_execute()
        if not can_exec and not force:
            raise RuntimeError(f"无法执行阶段 {stage_id}: {reason}")

        # 强制重新执行
        if force:
            # 更新状态为 pending
            workspace.update_stage_status(stage_id, StageStatus.PENDING)
            # 使下游阶段失效
            workspace.invalidate_downstream_stages(stage_id)

        # 获取工作区锁
        with workspace.acquire_lock(timeout=5):
            return executor.execute(reporter, resume=resume)

    def get_status(self, video_path: Path) -> Optional[PipelineStatus]:
        """获取管道状态"""
        video_path = Path(video_path)
        manager = WorkspaceManager(video_path, self.workspace_dir)

        if not manager.exists():
            return None

        workspace = manager.open()

        stage_summary = {}
        for stage_id in self.STAGE_ORDER:
            stage = workspace.get_stage(stage_id)
            duration_sec = None
            if stage.state.duration_ms:
                duration_sec = stage.state.duration_ms // 1000
            stage_summary[stage_id] = (stage.state.status, duration_sec)

        total_duration = sum(
            (d or 0) for _, d in stage_summary.values()
        )

        # 计算进度百分比
        completed = sum(
            1 for status, _ in stage_summary.values()
            if status in (StageStatus.COMPLETED, StageStatus.SKIPPED)
        )
        progress = completed / len(self.STAGE_ORDER) * 100

        return PipelineStatus(
            video_path=str(video_path),
            workspace_path=str(workspace.workspace_dir),
            overall_status=workspace.state.overall_status,
            current_stage=workspace.state.current_stage,
            stage_summary=stage_summary,
            total_duration_ms=total_duration * 1000,
            progress_percent=progress
        )

    def list_available_stages(self, video_path: Path) -> List[StageInfo]:
        """列出可执行的阶段及其依赖状态"""
        video_path = Path(video_path)
        manager = WorkspaceManager(video_path, self.workspace_dir)

        if not manager.exists():
            # 返回所有阶段为 pending
            return [
                StageInfo(
                    stage_id=stage_id,
                    name=self._get_stage_name(stage_id),
                    status=StageStatus.PENDING,
                    can_execute=stage_id == "01_audio_extract",
                    reason="需要先执行前面阶段" if stage_id != "01_audio_extract" else "",
                    dependencies=self._get_stage_dependencies(stage_id)
                )
                for stage_id in self.STAGE_ORDER
            ]

        workspace = manager.open()
        result = []

        for stage_id in self.STAGE_ORDER:
            stage = workspace.get_stage(stage_id)
            can_exec, reason = workspace.check_dependencies_satisfied(stage_id)

            # 如果已完成，也可以重新执行
            if stage.state.status == StageStatus.COMPLETED:
                can_exec = True
                reason = "可以重新执行 (--force)"

            result.append(StageInfo(
                stage_id=stage_id,
                name=self._get_stage_name(stage_id),
                status=stage.state.status,
                can_execute=can_exec,
                reason=reason,
                dependencies=self._get_stage_dependencies(stage_id)
            ))

        return result

    def _export_subtitles(self, workspace: Workspace, output_path: Path, reporter: Optional[ProgressReporter]):
        """导出最终字幕文件"""
        # 确定从哪个阶段获取字幕
        stage_id = "05_llm_postprocess"
        stage = workspace.get_stage(stage_id)

        if stage.state.status != StageStatus.COMPLETED or not self.config.llm.enabled:
            # 使用字幕优化阶段的结果
            stage_id = "04_subtitle_optimize"
            stage = workspace.get_stage(stage_id)

        # 加载字幕数据
        subtitles_data = stage.load_artifact("subtitles")
        if subtitles_data is None:
            raise RuntimeError(f"找不到字幕数据: {stage_id}")

        # 转换为 SubtitleLine 对象
        lines = [SubtitleLine.from_dict(d) for d in subtitles_data]

        # 重新编号
        for i, line in enumerate(lines, 1):
            line.index = i

        # 保存字幕文件
        save_subtitles(lines, output_path, self.config.output.format)

        if reporter:
            reporter.on_log(f"字幕已保存: {output_path}")

    def _get_stage_name(self, stage_id: str) -> str:
        """获取阶段名称"""
        return STAGE_NAMES.get(stage_id, stage_id)

    def _get_stage_dependencies(self, stage_id: str) -> List[str]:
        """获取阶段依赖"""
        return STAGE_DEPENDENCIES.get(stage_id, [])

    def clean_workspace(self, video_path: Path, keep_output: bool = False):
        """清理工作区"""
        video_path = Path(video_path)
        manager = WorkspaceManager(video_path, self.workspace_dir)

        if manager.exists():
            manager.delete(keep_output=keep_output)
