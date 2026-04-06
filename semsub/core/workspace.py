"""
工作区管理模块
提供 WorkspaceManager、Workspace、StageContext 类
"""

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar, Union
import fcntl
import os
import tempfile

from .state_models import (
    WorkspaceState,
    StageState,
    StageStatus,
    StageInput,
    StageOutput,
    StageDependency,
    ArtifactInfo,
    StageProgressInfo,
)
from .config import PipelineConfig


T = TypeVar("T")


class AtomicFileWriter:
    """原子文件写入器"""

    def __init__(self, target_path: Path):
        self.target_path = Path(target_path)
        self.temp_file = None

    def __enter__(self):
        # 在同一目录创建临时文件，确保原子重命名
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".tmp",
            prefix=f".tmp_{self.target_path.name}_",
            dir=str(self.target_path.parent),
            delete=False,
        )
        return self.temp_file

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temp_file:
            self.temp_file.close()
            if exc_type is None:
                # 成功：原子重命名
                os.rename(self.temp_file.name, self.target_path)
            else:
                # 失败：删除临时文件
                os.unlink(self.temp_file.name)


class FileLock:
    """文件锁（用于防止并发执行）"""

    def __init__(self, lock_path: Path, timeout: float = 0):
        self.lock_path = Path(lock_path)
        self.timeout = timeout
        self.fd = None

    def __enter__(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = open(self.lock_path, "w")

        if self.timeout > 0:
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError(f"无法获取文件锁: {self.lock_path}")

            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(self.timeout))

        try:
            fcntl.flock(self.fd.fileno(), fcntl.LOCK_EX)
        finally:
            if self.timeout > 0:
                signal.alarm(0)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.fd:
            fcntl.flock(self.fd.fileno(), fcntl.LOCK_UN)
            self.fd.close()


def compute_file_hash(path: Path, algorithm: str = "sha256", chunk_size: int = 8192) -> str:
    """计算文件哈希"""
    hasher = hashlib.new(algorithm)
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return f"{algorithm}:{hasher.hexdigest()}"


def safe_write_json(path: Path, data: Any):
    """安全地写入 JSON 文件（原子写入）"""
    with AtomicFileWriter(path) as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        f.write("\n")


def safe_read_json(path: Path, default: T = None) -> Union[Any, T]:
    """安全地读取 JSON 文件"""
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def copy_with_hardlink(src: Path, dst: Path, use_hardlink: bool = True) -> Path:
    """复制文件，优先使用硬链接"""
    dst.parent.mkdir(parents=True, exist_ok=True)

    if use_hardlink:
        try:
            os.link(src, dst)
            return dst
        except (OSError, FileExistsError):
            pass

    shutil.copy2(src, dst)
    return dst


class StageContext:
    """单个阶段的执行上下文"""

    def __init__(self, stage_dir: Path, stage_state: StageState, workspace: "Workspace"):
        self.stage_dir = Path(stage_dir)
        self.state = stage_state
        self.workspace = workspace
        self._input_cache: Optional[StageInput] = None
        self._output_cache: Optional[StageOutput] = None

    @property
    def stage_id(self) -> str:
        return self.state.stage_id

    @property
    def input_path(self) -> Path:
        return self.stage_dir / self.state.input_path

    @property
    def output_path(self) -> Path:
        return self.stage_dir / self.state.output_path

    @property
    def checkpoint_path(self) -> Optional[Path]:
        if self.state.checkpoint_path:
            return self.stage_dir / self.state.checkpoint_path
        return None

    def ensure_dir(self):
        """确保阶段目录存在"""
        self.stage_dir.mkdir(parents=True, exist_ok=True)

    def load_input(self) -> Optional[StageInput]:
        """加载输入描述"""
        if self._input_cache is None and self.input_path.exists():
            data = safe_read_json(self.input_path)
            if data:
                self._input_cache = StageInput.model_validate(data)
        return self._input_cache

    def load_output(self) -> Optional[StageOutput]:
        """加载输出描述（如果已完成）"""
        if self._output_cache is None and self.output_path.exists():
            data = safe_read_json(self.output_path)
            if data:
                self._output_cache = StageOutput.model_validate(data)
        return self._output_cache

    def save_input(self, dependencies: Dict[str, StageDependency], parameters: Dict[str, Any]):
        """保存输入描述"""
        self.ensure_dir()
        input_def = StageInput(
            stage_id=self.stage_id,
            dependencies=dependencies,
            parameters=parameters,
        )
        safe_write_json(self.input_path, input_def.model_dump())
        self._input_cache = input_def

    def save_output(self, artifacts: Dict[str, ArtifactInfo], statistics: Dict[str, Any]):
        """保存阶段输出"""
        self.ensure_dir()
        output_def = StageOutput(
            stage_id=self.stage_id,
            status=self.state.status,
            artifacts=artifacts,
            statistics=statistics,
            started_at=self.state.started_at,
            completed_at=self.state.completed_at,
            duration_ms=self.state.duration_ms,
        )
        safe_write_json(self.output_path, output_def.model_dump())
        self._output_cache = output_def

    def resolve_input_artifact(self, artifact_name: str) -> Optional[Path]:
        """解析输入 artifact 的实际路径"""
        input_def = self.load_input()
        if input_def is None or artifact_name not in input_def.dependencies:
            return None

        dep = input_def.dependencies[artifact_name]
        # 路径可能是相对路径，需要解析
        if dep.path.startswith("../"):
            # 相对当前阶段目录
            return (self.stage_dir / dep.path).resolve()
        elif dep.path.startswith("/"):
            # 绝对路径
            return Path(dep.path)
        else:
            # 相对工作区根目录
            return (self.workspace.workspace_dir / dep.path).resolve()

    def load_artifact(self, name: str, from_input: bool = False) -> Any:
        """加载 artifact 数据

        Args:
            name: artifact 名称
            from_input: 是否从输入加载（否则从输出加载）
        """
        if from_input:
            path = self.resolve_input_artifact(name)
        else:
            output_def = self.load_output()
            if output_def is None or name not in output_def.artifacts:
                return None
            path = self.stage_dir / output_def.artifacts[name].path

        if path is None or not path.exists():
            return None

        # 根据后缀自动解析
        suffix = path.suffix.lower()
        if suffix == ".json":
            return safe_read_json(path)
        elif suffix in (".wav", ".mp3", ".flac"):
            return path  # 返回路径，由调用者处理
        elif suffix in (".txt", ".srt", ".vtt", ".yaml", ".yml"):
            return path.read_text(encoding="utf-8")
        else:
            return path

    def save_artifact(self, name: str, data: Any, artifact_type: str = "json") -> Path:
        """保存 artifact 数据"""
        self.ensure_dir()

        # 确定文件路径
        if artifact_type == "json":
            path = self.stage_dir / f"{name}.json"
            safe_write_json(path, data)
        elif artifact_type in ("wav", "mp3", "flac"):
            path = self.stage_dir / f"{name}.{artifact_type}"
            if isinstance(data, Path):
                copy_with_hardlink(data, path)
            elif isinstance(data, bytes):
                path.write_bytes(data)
        elif artifact_type in ("txt", "srt", "vtt", "yaml"):
            path = self.stage_dir / f"{name}.{artifact_type}"
            if isinstance(data, str):
                path.write_text(data, encoding="utf-8")
            elif isinstance(data, Path):
                shutil.copy2(data, path)
        else:
            raise ValueError(f"不支持的 artifact 类型: {artifact_type}")

        return path

    def load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """加载检查点数据"""
        if self.checkpoint_path and self.checkpoint_path.exists():
            return safe_read_json(self.checkpoint_path)
        return self.state.checkpoint_data or None

    def save_checkpoint(self, data: Dict[str, Any]):
        """保存检查点数据"""
        self.ensure_dir()
        checkpoint_path = self.stage_dir / "checkpoint.json"
        safe_write_json(checkpoint_path, data)
        self.state.checkpoint_path = "checkpoint.json"
        self.state.checkpoint_data = data

    def clear_checkpoint(self):
        """清除检查点"""
        if self.checkpoint_path and self.checkpoint_path.exists():
            self.checkpoint_path.unlink()
        self.state.checkpoint_path = None
        self.state.checkpoint_data = {}


class Workspace:
    """表示一个具体的工作区"""

    STAGE_ORDER = [
        "01_audio_extract",
        "02_vad_split",
        "03_asr_transcribe",
        "04_subtitle_optimize",
        "05_llm_postprocess",
    ]

    STAGE_DEPENDENCIES = {
        "01_audio_extract": [],
        "02_vad_split": ["01_audio_extract"],
        "03_asr_transcribe": ["02_vad_split"],
        "04_subtitle_optimize": ["02_vad_split", "03_asr_transcribe"],
        "05_llm_postprocess": ["04_subtitle_optimize"],
    }

    def __init__(self, workspace_dir: Path, state: WorkspaceState):
        self.workspace_dir = Path(workspace_dir)
        self.state = state
        self._stage_cache: Dict[str, StageContext] = {}
        self._lock: Optional[FileLock] = None

    @property
    def video_path(self) -> Path:
        return Path(self.state.video_path)

    def acquire_lock(self, timeout: float = 0) -> FileLock:
        """获取工作区锁"""
        lock_path = self.workspace_dir / ".lock"
        self._lock = FileLock(lock_path, timeout=timeout)
        return self._lock.__enter__()

    def release_lock(self):
        """释放工作区锁"""
        if self._lock:
            self._lock.__exit__(None, None, None)
            self._lock = None

    def save_state(self):
        """保存状态到文件"""
        self.state.updated_at = datetime.now()
        state_path = self.workspace_dir / "state.json"
        safe_write_json(state_path, self.state.model_dump())

    def get_stage(self, stage_id: str) -> StageContext:
        """获取指定阶段的上下文"""
        if stage_id not in self._stage_cache:
            stage_dir = self.workspace_dir / stage_id
            stage_state = self.state.stages.get(stage_id)
            if stage_state is None:
                stage_state = StageState(stage_id=stage_id, created_at=datetime.now())
                self.state.stages[stage_id] = stage_state
            self._stage_cache[stage_id] = StageContext(stage_dir, stage_state, self)
        return self._stage_cache[stage_id]

    def list_stages(self) -> List[str]:
        """列出所有阶段"""
        return self.STAGE_ORDER.copy()

    def get_stage_dependencies(self, stage_id: str) -> List[str]:
        """获取阶段的依赖列表"""
        return self.STAGE_DEPENDENCIES.get(stage_id, [])

    def check_dependencies_satisfied(self, stage_id: str) -> tuple[bool, str]:
        """检查阶段的依赖是否已满足

        Returns:
            (是否满足, 原因)
        """
        dependencies = self.get_stage_dependencies(stage_id)
        for dep_id in dependencies:
            dep_stage = self.get_stage(dep_id)
            if dep_stage.state.status != StageStatus.COMPLETED:
                if dep_stage.state.status == StageStatus.FAILED:
                    return False, f"依赖阶段 {dep_id} 执行失败"
                elif dep_stage.state.status == StageStatus.SKIPPED:
                    return False, f"依赖阶段 {dep_id} 被跳过"
                else:
                    return False, f"依赖阶段 {dep_id} 尚未完成"
        return True, ""

    def get_next_pending_stage(self) -> Optional[str]:
        """获取下一个待执行的阶段"""
        for stage_id in self.STAGE_ORDER:
            stage = self.get_stage(stage_id)
            if stage.state.status == StageStatus.PENDING:
                satisfied, _ = self.check_dependencies_satisfied(stage_id)
                if satisfied:
                    return stage_id
        return None

    def update_stage_status(
        self,
        stage_id: str,
        status: StageStatus,
        message: str = "",
        error_message: str = "",
        error_traceback: str = "",
    ):
        """更新阶段状态"""
        stage = self.get_stage(stage_id)
        stage.state.status = status
        stage.state.status_message = message

        now = datetime.now()

        if status == StageStatus.RUNNING:
            stage.state.started_at = now
            self.state.current_stage = stage_id
            self.state.overall_status = StageStatus.RUNNING
        elif status in (StageStatus.COMPLETED, StageStatus.FAILED, StageStatus.SKIPPED):
            stage.state.completed_at = now
            if stage.state.started_at:
                stage.state.duration_ms = int(
                    (now - stage.state.started_at).total_seconds() * 1000
                )

            if status == StageStatus.FAILED:
                stage.state.error_message = error_message
                stage.state.error_traceback = error_traceback
                self.state.overall_status = StageStatus.FAILED
            else:
                # 检查是否全部完成
                if all(
                    s.status in (StageStatus.COMPLETED, StageStatus.SKIPPED)
                    for s in self.state.stages.values()
                ):
                    self.state.overall_status = StageStatus.COMPLETED

        self.save_state()

    def update_stage_progress(self, stage_id: str, current: int, total: int, message: str = ""):
        """更新阶段进度"""
        stage = self.get_stage(stage_id)
        stage.state.progress = StageProgressInfo(
            current=current,
            total=total,
            message=message,
            percent=round(current / total * 100, 1) if total > 0 else 0.0,
        )
        self.save_state()

    def invalidate_downstream_stages(self, stage_id: str):
        """使下游阶段失效（当某个阶段重新执行时）"""
        found = False
        for sid in self.STAGE_ORDER:
            if sid == stage_id:
                found = True
                continue
            if found:
                stage = self.get_stage(sid)
                if stage.state.status in (StageStatus.COMPLETED, StageStatus.FAILED):
                    stage.state.status = StageStatus.PENDING
                    stage.state.status_message = "上游阶段已变更，需要重新执行"
                    # 清除输出文件
                    if stage.output_path.exists():
                        stage.output_path.unlink()
        self.save_state()

    def get_stage_order_index(self, stage_id: str) -> int:
        """获取阶段的执行顺序索引"""
        try:
            return self.STAGE_ORDER.index(stage_id)
        except ValueError:
            return -1


class WorkspaceManager:
    """管理工作区生命周期"""

    def __init__(
        self,
        video_path: Union[str, Path],
        workspace_dir: Optional[Union[str, Path]] = None,
    ):
        self.video_path = Path(video_path)
        if workspace_dir:
            self.workspace_dir = Path(workspace_dir)
        else:
            self.workspace_dir = self._get_default_workspace_dir()

    def _get_default_workspace_dir(self) -> Path:
        """获取默认工作区目录"""
        # 默认在视频目录下创建 .semsub
        return self.video_path.parent / ".semsub"

    def _compute_video_hash(self) -> str:
        """计算视频文件哈希（前1MB + 文件大小 + 修改时间）"""
        stat = self.video_path.stat()
        size = stat.st_size
        mtime = stat.st_mtime

        # 读取前1MB
        hasher = hashlib.sha256()
        hasher.update(f"{size}:{mtime}:".encode())

        with open(self.video_path, "rb") as f:
            chunk = f.read(1024 * 1024)  # 1MB
            hasher.update(chunk)

        return f"sha256:{hasher.hexdigest()}"

    def exists(self) -> bool:
        """检查工作区是否存在"""
        state_path = self.workspace_dir / "state.json"
        return state_path.exists()

    def initialize(self, config: PipelineConfig, force: bool = False) -> Workspace:
        """初始化新工作区"""
        if self.exists() and not force:
            raise FileExistsError(f"工作区已存在: {self.workspace_dir}")

        # 删除旧工作区（如果强制初始化）
        if self.exists() and force:
            self.delete()

        # 创建目录结构
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        # 写入配置快照
        config_path = self.workspace_dir / "config.yaml"
        config_path.write_text(config.to_yaml(), encoding="utf-8")

        # 创建状态
        stat = self.video_path.stat()
        state = WorkspaceState(
            video_path=str(self.video_path),
            video_hash=self._compute_video_hash(),
            video_size=stat.st_size,
            video_mtime=datetime.fromtimestamp(stat.st_mtime),
        )

        # 初始化各阶段状态
        for stage_id in Workspace.STAGE_ORDER:
            state.stages[stage_id] = StageState(
                stage_id=stage_id,
                status=StageStatus.PENDING,
                created_at=datetime.now(),
            )

        # 保存状态
        workspace = Workspace(self.workspace_dir, state)
        workspace.save_state()

        return workspace

    def open(self, check_hash: bool = True) -> Optional[Workspace]:
        """打开已有工作区

        Args:
            check_hash: 是否检查视频文件哈希（检测视频是否变更）
        """
        if not self.exists():
            return None

        # 加载状态
        state_path = self.workspace_dir / "state.json"
        try:
            data = safe_read_json(state_path)
            state = WorkspaceState.model_validate(data)
        except Exception as e:
            raise RuntimeError(f"无法加载工作区状态: {e}")

        workspace = Workspace(self.workspace_dir, state)

        # 验证视频文件
        if not self.video_path.exists():
            raise FileNotFoundError(f"视频文件不存在: {self.video_path}")

        if check_hash:
            current_hash = self._compute_video_hash()
            if current_hash != state.video_hash:
                raise ValueError(
                    f"视频文件已变更（哈希不匹配）。\n"
                    f"  原哈希: {state.video_hash}\n"
                    f"  新哈希: {current_hash}\n"
                    f"  建议: 删除工作区重新初始化，或使用 --ignore-hash 忽略"
                )

        return workspace

    def open_or_initialize(self, config: PipelineConfig) -> Workspace:
        """打开或初始化工作区"""
        workspace = self.open()
        if workspace is None:
            workspace = self.initialize(config)
        return workspace

    def delete(self, keep_output: bool = False):
        """删除工作区

        Args:
            keep_output: 是否保留最终输出文件（如 .srt）
        """
        if not self.exists():
            return

        if keep_output:
            # 只保留最终字幕文件
            for ext in (".srt", ".vtt", ".json"):
                output_file = self.video_path.with_suffix(ext)
                if output_file.exists():
                    # 临时移动出去
                    temp_dir = tempfile.mkdtemp()
                    shutil.move(str(output_file), temp_dir)

            shutil.rmtree(self.workspace_dir, ignore_errors=True)

            # 移回来
            # TODO: 实现这个逻辑
        else:
            shutil.rmtree(self.workspace_dir, ignore_errors=True)

    @staticmethod
    def list_centralized_workspaces(base_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
        """列出集中式存储的所有工作区"""
        if base_dir is None:
            base_dir = Path.home() / ".semsub" / "workspaces"

        workspaces = []
        if not base_dir.exists():
            return workspaces

        for ws_dir in base_dir.iterdir():
            if not ws_dir.is_dir():
                continue
            state_path = ws_dir / "state.json"
            if state_path.exists():
                try:
                    data = safe_read_json(state_path)
                    workspaces.append({
                        "path": ws_dir,
                        "video_path": data.get("video_path", "unknown"),
                        "status": data.get("overall_status", "unknown"),
                        "updated_at": data.get("updated_at"),
                    })
                except Exception:
                    pass

        return workspaces
