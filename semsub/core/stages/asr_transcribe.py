"""
ASR 转录阶段 - 使用 Qwen3-ASR
支持 Workspace 和检查点续传
"""

from pathlib import Path
from typing import Optional, List, Dict
import shutil

import torch
import torchaudio

try:
    from qwen_asr import Qwen3ASRModel
except ImportError:
    Qwen3ASRModel = None

from .base import WorkspacePipelineStage
from ..progress import ProgressReporter, PipelineStage, StageProgress, CancellationError
from ..workspace import StageContext
from ..state_models import ArtifactInfo
from ..config import ASRConfig
from ..models import WordItem, TranscriptSegment


class ASRTranscribeStage(WorkspacePipelineStage):
    """ASR 转录阶段"""

    name = "ASR 转录"
    stage_id = "03_asr_transcribe"

    def __init__(self, config: ASRConfig):
        self.config = config
        self.model = None

    def get_input_spec(self):
        return {
            "dependencies": ["02_vad_split"],
            "artifacts": {
                "segments": {"type": "json", "from_stage": "02_vad_split"},
                "audio_tensor": {"type": "pt", "from_stage": "02_vad_split"}
            },
            "parameters": {
                "batch_size": int,
                "language": Optional[str],
                "model_path": str,
                "aligner_path": str
            }
        }

    def get_output_spec(self):
        return {
            "artifacts": {
                "transcripts": {"type": "json", "description": "转录结果"}
            }
        }

    def _load_model(self):
        """加载 ASR 模型"""
        if self.model is not None:
            return

        if Qwen3ASRModel is None:
            raise RuntimeError("qwen_asr 模块未安装")

        self.model = Qwen3ASRModel.from_pretrained(
            self.config.model_path,
            dtype=torch.bfloat16,
            device_map=self.config.device,
            forced_aligner=self.config.aligner_path,
            forced_aligner_kwargs=dict(
                dtype=torch.bfloat16,
                device_map=self.config.device,
            ),
        )

    def can_resume(self, checkpoint: Dict) -> bool:
        """检查是否可以恢复"""
        return (
            "processed_count" in checkpoint
            and "transcript_segments" in checkpoint
            and "batch_size" in checkpoint
        )

    def execute(
        self,
        ctx: StageContext,
        reporter: Optional[ProgressReporter] = None
    ) -> dict:
        """
        转录音频片段

        Args:
            ctx: 阶段上下文
            reporter: 进度报告器

        Returns:
            {"artifacts": {"transcripts": [...]}, "statistics": {...}}
        """
        # 加载检查点（如果存在）
        checkpoint = ctx.load_checkpoint()

        if checkpoint and self.can_resume(checkpoint):
            return self.resume(ctx, checkpoint, reporter)

        # 加载输入
        segments = ctx.load_artifact("segments", from_input=True)
        if segments is None:
            raise FileNotFoundError("找不到输入 segments 文件")

        # 加载音频张量
        audio_tensor_path = ctx.resolve_input_artifact("audio_tensor")
        if audio_tensor_path is None:
            raise FileNotFoundError("找不到输入音频张量")
        wav = torch.load(audio_tensor_path)

        sample_rate = 16000

        self._load_model()

        if reporter:
            reporter.on_stage_start(PipelineStage.ASR_TRANSCRIBE, len(segments))
            reporter.on_log(f"开始转录 {len(segments)} 个片段")

        transcript_segments = []
        temp_dir = ctx.stage_dir / "temp_segments"
        temp_dir.mkdir(exist_ok=True)

        try:
            # 分批处理
            batch_size = self.config.batch_size
            total_segments = len(segments)

            for batch_start in range(0, total_segments, batch_size):
                # 检查是否已取消
                if reporter:
                    reporter.check_cancelled()

                batch_end = min(batch_start + batch_size, total_segments)
                batch_segments = segments[batch_start:batch_end]
                batch_num = batch_start // batch_size + 1
                total_batches = (total_segments - 1) // batch_size + 1

                if reporter:
                    reporter.on_progress(StageProgress.create(
                        PipelineStage.ASR_TRANSCRIBE,
                        batch_start,
                        total_segments,
                        f"处理批次 {batch_num}/{total_batches}"
                    ))

                # 准备音频文件
                batch_files = []
                for seg in batch_segments:
                    start_sample = int(seg['start'] * sample_rate)
                    end_sample = int(seg['end'] * sample_rate)
                    seg_wav = wav[start_sample:end_sample]
                    seg_file = temp_dir / f"seg_{seg['index']:04d}.wav"
                    torchaudio.save(str(seg_file), seg_wav.unsqueeze(0).cpu(), sample_rate)
                    batch_files.append((seg_file, seg))

                # 批量 ASR
                language = self.config.language
                results = self.model.transcribe(
                    audio=[str(f[0]) for f in batch_files],
                    language=[language] * len(batch_files) if language else [None] * len(batch_files),
                    return_time_stamps=True,
                )

                # 处理结果，保留完整文本和字级时间戳（含标点）
                for (seg_file, seg), result in zip(batch_files, results):
                    words = self._process_asr_result(result, seg)

                    # 保存完整文本（含标点）和字级时间戳
                    full_text = result.text if hasattr(result, 'text') and result.text else "".join(w.text for w in words)
                    transcript_segments.append(TranscriptSegment(
                        start=seg['start'],
                        end=seg['end'],
                        text=full_text,
                        words=words,
                    ))

                # 保存检查点
                ctx.save_checkpoint({
                    "processed_count": len(transcript_segments),
                    "transcript_segments": [self._segment_to_dict(s) for s in transcript_segments],
                    "batch_size": batch_size,
                    "last_processed_index": batch_end - 1,
                })

        except CancellationError:
            raise

        finally:
            # 清理临时文件
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

        # 按时间排序
        transcript_segments.sort(key=lambda s: s.start)

        total_words = sum(len(s.words) for s in transcript_segments)

        # 保存最终结果
        transcripts_data = [self._segment_to_dict(s) for s in transcript_segments]
        ctx.save_artifact("transcripts", transcripts_data, "json")

        # 清除检查点（成功完成）
        ctx.clear_checkpoint()

        if reporter:
            reporter.on_progress(StageProgress.create(
                PipelineStage.ASR_TRANSCRIBE,
                len(segments),
                len(segments),
                f"转录完成，共 {len(transcript_segments)} 个片段，{total_words} 个字"
            ))

        return {
            "artifacts": {
                "transcripts": ArtifactInfo(
                    path="transcripts.json",
                    type="json"
                )
            },
            "statistics": {
                "total_segments": len(transcript_segments),
                "total_words": total_words,
                "avg_words_per_segment": round(total_words / len(transcript_segments), 1) if transcript_segments else 0
            }
        }

    def resume(
        self,
        ctx: StageContext,
        checkpoint: Dict,
        reporter: Optional[ProgressReporter] = None
    ) -> dict:
        """从检查点恢复执行"""
        if reporter:
            reporter.on_log(f"从检查点恢复，已处理 {checkpoint['processed_count']} 个片段")

        # 恢复已处理的数据
        processed_count = checkpoint['processed_count']
        transcript_segments = [self._dict_to_segment(d) for d in checkpoint['transcript_segments']]
        batch_size = checkpoint.get('batch_size', self.config.batch_size)
        last_processed = checkpoint.get('last_processed_index', -1)

        # 加载输入
        segments = ctx.load_artifact("segments", from_input=True)
        audio_tensor_path = ctx.resolve_input_artifact("audio_tensor")
        wav = torch.load(audio_tensor_path)
        sample_rate = 16000

        self._load_model()

        temp_dir = ctx.stage_dir / "temp_segments"
        temp_dir.mkdir(exist_ok=True)

        try:
            # 从断点继续处理
            start_index = last_processed + 1
            total_segments = len(segments)

            for batch_start in range(start_index, total_segments, batch_size):
                if reporter:
                    reporter.check_cancelled()

                batch_end = min(batch_start + batch_size, total_segments)
                batch_segments = segments[batch_start:batch_end]

                if reporter:
                    reporter.on_progress(StageProgress.create(
                        PipelineStage.ASR_TRANSCRIBE,
                        batch_start,
                        total_segments,
                        f"恢复处理: 批次 {batch_start // batch_size + 1}/{(total_segments - 1) // batch_size + 1}"
                    ))

                # 准备音频文件
                batch_files = []
                for seg in batch_segments:
                    start_sample = int(seg['start'] * sample_rate)
                    end_sample = int(seg['end'] * sample_rate)
                    seg_wav = wav[start_sample:end_sample]
                    seg_file = temp_dir / f"seg_{seg['index']:04d}.wav"
                    torchaudio.save(str(seg_file), seg_wav.unsqueeze(0).cpu(), sample_rate)
                    batch_files.append((seg_file, seg))

                # 批量 ASR
                language = self.config.language
                results = self.model.transcribe(
                    audio=[str(f[0]) for f in batch_files],
                    language=[language] * len(batch_files) if language else [None] * len(batch_files),
                    return_time_stamps=True,
                )

                # 处理结果
                for (seg_file, seg), result in zip(batch_files, results):
                    words = self._process_asr_result(result, seg)
                    full_text = result.text if hasattr(result, 'text') and result.text else "".join(w.text for w in words)
                    transcript_segments.append(TranscriptSegment(
                        start=seg['start'],
                        end=seg['end'],
                        text=full_text,
                        words=words,
                    ))

                # 更新检查点
                ctx.save_checkpoint({
                    "processed_count": len(transcript_segments),
                    "transcript_segments": [self._segment_to_dict(s) for s in transcript_segments],
                    "batch_size": batch_size,
                    "last_processed_index": batch_end - 1,
                })

        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

        # 按时间排序
        transcript_segments.sort(key=lambda s: s.start)
        total_words = sum(len(s.words) for s in transcript_segments)

        # 保存最终结果
        transcripts_data = [self._segment_to_dict(s) for s in transcript_segments]
        ctx.save_artifact("transcripts", transcripts_data, "json")

        # 清除检查点
        ctx.clear_checkpoint()

        if reporter:
            reporter.on_progress(StageProgress.create(
                PipelineStage.ASR_TRANSCRIBE,
                total_segments,
                total_segments,
                f"转录完成（恢复），共 {len(transcript_segments)} 个片段"
            ))

        return {
            "artifacts": {
                "transcripts": ArtifactInfo(
                    path="transcripts.json",
                    type="json"
                )
            },
            "statistics": {
                "total_segments": len(transcript_segments),
                "total_words": total_words
            }
        }

    def _process_asr_result(self, result, seg: dict) -> List[WordItem]:
        """处理 ASR 结果，保留标点"""
        words = []

        if result.time_stamps and result.time_stamps.items and hasattr(result, 'text') and result.text:
            align_items = result.time_stamps.items
            full_text = result.text

            item_idx = 0
            for char_idx, char in enumerate(full_text):
                if char.isspace():
                    continue

                punctuation = '，。！？；：、""''（）【】《》,.!?;:()[]{} '
                if char in punctuation:
                    if item_idx > 0:
                        prev_end = align_items[item_idx - 1].end_time
                        words.append(WordItem(
                            text=char,
                            start=prev_end + seg['start'],
                            end=prev_end + seg['start'] + 0.01,
                        ))
                    elif align_items:
                        first_start = align_items[0].start_time
                        words.append(WordItem(
                            text=char,
                            start=first_start + seg['start'],
                            end=first_start + seg['start'] + 0.01,
                        ))
                else:
                    if item_idx < len(align_items):
                        item = align_items[item_idx]
                        words.append(WordItem(
                            text=char,
                            start=item.start_time + seg['start'],
                            end=item.end_time + seg['start'],
                        ))
                        item_idx += 1
                    else:
                        if words:
                            last_end = words[-1].end - seg['start']
                            words.append(WordItem(
                                text=char,
                                start=last_end + seg['start'],
                                end=last_end + seg['start'] + 0.1,
                            ))
        elif result.time_stamps and result.time_stamps.items:
            for item in result.time_stamps.items:
                words.append(WordItem(
                    text=item.text,
                    start=item.start_time + seg['start'],
                    end=item.end_time + seg['start'],
                ))

        return words

    def _segment_to_dict(self, seg: TranscriptSegment) -> dict:
        """转换 TranscriptSegment 为字典"""
        return {
            "start": seg.start,
            "end": seg.end,
            "text": seg.text,
            "words": [{"text": w.text, "start": w.start, "end": w.end} for w in seg.words]
        }

    def _dict_to_segment(self, data: dict) -> TranscriptSegment:
        """从字典恢复 TranscriptSegment"""
        words = [WordItem(**w) for w in data.get("words", [])]
        return TranscriptSegment(
            start=data["start"],
            end=data["end"],
            text=data["text"],
            words=words
        )

    def cleanup(self):
        """清理模型"""
        if self.model is not None:
            del self.model
            self.model = None
        torch.cuda.empty_cache()
