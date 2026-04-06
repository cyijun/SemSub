"""
电影字幕生成器 - 完整流程

整合 VAD、ASR、ForcedAligner 和字幕优化
"""

import json
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass

import torch
import torchaudio

try:
    from qwen_asr import Qwen3ASRModel
except ImportError:
    Qwen3ASRModel = None
    print("警告: qwen_asr 模块未安装")

from subtitle_merger import SubtitleMerger, SubtitleLine, WordItem, save_subtitles


@dataclass
class SubtitleConfig:
    """字幕生成配置"""
    # 模型路径
    asr_model_path: str = '/mnt/g/models/Qwen3-ASR-1.7B'
    aligner_path: str = '/mnt/g/models/Qwen3-ForcedAligner-0.6B'
    
    # 语言设置
    language: Optional[str] = None  # None=自动检测, "Chinese", "English"
    
    # VAD 参数
    vad_threshold: float = 0.5
    vad_min_speech_duration_ms: int = 250
    vad_min_silence_duration_ms: int = 500
    
    # 字幕优化参数
    max_chars: int = 40           # 中文每行最大字符
    max_chars_en: int = 80        # 英文每行最大字符
    max_duration: float = 6.0     # 每行最大显示时长
    min_duration: float = 1.0     # 每行最小显示时长
    gap_threshold: float = 0.3    # VAD 片段合并阈值
    
    # 批处理参数
    batch_size: int = 8
    device: str = "cuda:0"


class MovieSubtitleGenerator:
    """电影字幕生成器"""
    
    def __init__(self, config: Optional[SubtitleConfig] = None):
        self.config = config or SubtitleConfig()
        self.asr_model = None
        self.vad_model = None
        self.vad_utils = None
        
        # 初始化字幕合并器
        self.merger = SubtitleMerger(
            max_chars=self.config.max_chars,
            max_chars_en=self.config.max_chars_en,
            max_duration=self.config.max_duration,
            min_duration=self.config.min_duration,
            gap_threshold=self.config.gap_threshold,
        )
    
    def _load_asr_model(self):
        """加载 ASR 模型"""
        if self.asr_model is not None:
            return
        
        if Qwen3ASRModel is None:
            raise RuntimeError("qwen_asr 模块未安装，无法加载 ASR 模型")
        
        print("正在加载 ASR 模型...")
        self.asr_model = Qwen3ASRModel.from_pretrained(
            self.config.asr_model_path,
            dtype=torch.bfloat16,
            device_map=self.config.device,
            forced_aligner=self.config.aligner_path,
            forced_aligner_kwargs=dict(
                dtype=torch.bfloat16,
                device_map=self.config.device,
            ),
        )
        print("ASR 模型加载完成")
    
    def _load_vad_model(self):
        """加载 VAD 模型"""
        if self.vad_model is not None:
            return
        
        print("正在加载 VAD 模型...")
        self.vad_model, self.vad_utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
        )
        self.vad_model = self.vad_model.to(self.config.device)
        print("VAD 模型加载完成")
    
    def extract_audio(self, video_path: str, output_wav: Optional[str] = None, 
                      sample_rate: int = 16000) -> Path:
        """从视频提取音频"""
        video_path = Path(video_path)
        
        if not video_path.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        
        if output_wav is None:
            output_wav = video_path.with_suffix('.wav')
        else:
            output_wav = Path(output_wav)
        
        cmd = [
            'ffmpeg', '-y', '-i', str(video_path),
            '-vn',                    # 无视频
            '-acodec', 'pcm_s16le',   # 16位 PCM
            '-ac', '1',               # 单声道
            '-ar', str(sample_rate),  # 采样率
            str(output_wav)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"FFmpeg 错误: {result.stderr}")
            raise subprocess.CalledProcessError(result.returncode, cmd)
        
        print(f"音频已提取: {output_wav}")
        return output_wav
    
    def vad_split(self, wav_path: str, sample_rate: int = 16000) -> tuple:
        """
        VAD 语音分割
        
        Returns:
            (segments, wav_tensor)
        """
        self._load_vad_model()
        
        get_speech_timestamps = self.vad_utils[0]
        read_audio = self.vad_utils[2]
        
        # 读取音频
        wav = read_audio(str(wav_path), sampling_rate=sample_rate)
        if isinstance(wav, torch.Tensor):
            wav = wav.to(self.config.device)
        
        total_duration = len(wav) / sample_rate
        print(f"音频总时长: {total_duration:.2f}秒")
        
        # 获取语音时间戳
        speech_timestamps = get_speech_timestamps(
            wav,
            self.vad_model,
            sampling_rate=sample_rate,
            threshold=self.config.vad_threshold,
            min_speech_duration_ms=self.config.vad_min_speech_duration_ms,
            min_silence_duration_ms=self.config.vad_min_silence_duration_ms,
        )
        
        # 转换为秒
        segments = [
            {
                'index': i,
                'start': ts['start'] / sample_rate,
                'end': ts['end'] / sample_rate,
                'duration': (ts['end'] - ts['start']) / sample_rate,
            }
            for i, ts in enumerate(speech_timestamps)
        ]
        
        print(f"检测到 {len(segments)} 个语音片段")
        return segments, wav
    
    def _extract_segment(self, wav: torch.Tensor, seg: Dict, 
                         sample_rate: int = 16000) -> torch.Tensor:
        """从音频中提取片段"""
        start_sample = int(seg['start'] * sample_rate)
        end_sample = int(seg['end'] * sample_rate)
        return wav[start_sample:end_sample]
    
    def transcribe_segments(self, segments: List[Dict], wav: torch.Tensor,
                           sample_rate: int = 16000) -> List[WordItem]:
        """
        批量转录语音片段，返回词级时间戳
        """
        self._load_asr_model()
        
        all_words = []
        temp_dir = Path("temp_segments")
        temp_dir.mkdir(exist_ok=True)
        
        try:
            # 分批处理
            for batch_start in range(0, len(segments), self.config.batch_size):
                batch_end = min(batch_start + self.config.batch_size, len(segments))
                batch_segments = segments[batch_start:batch_end]
                
                print(f"处理批次 {batch_start//self.config.batch_size + 1}/"
                      f"{(len(segments)-1)//self.config.batch_size + 1} "
                      f"({batch_start}-{batch_end-1})")
                
                # 准备音频文件
                batch_files = []
                for seg in batch_segments:
                    seg_wav = self._extract_segment(wav, seg, sample_rate)
                    seg_file = temp_dir / f"seg_{seg['index']:04d}.wav"
                    torchaudio.save(str(seg_file), seg_wav.unsqueeze(0).cpu(), sample_rate)
                    batch_files.append((seg_file, seg))
                
                # 批量 ASR
                results = self.asr_model.transcribe(
                    audio=[str(f[0]) for f in batch_files],
                    language=[self.config.language] * len(batch_files),
                    return_time_stamps=True,
                )
                
                # 处理结果，调整时间戳
                for (seg_file, seg), result in zip(batch_files, results):
                    if result.time_stamps and result.time_stamps.items:
                        for item in result.time_stamps.items:
                            # 调整时间戳（加上片段偏移）
                            all_words.append(WordItem(
                                text=item.text,
                                start=item.start_time + seg['start'],
                                end=item.end_time + seg['start'],
                            ))
        finally:
            # 清理临时文件
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        
        # 按时间排序
        all_words.sort(key=lambda w: w.start)
        print(f"转录完成，共 {len(all_words)} 个词")
        
        return all_words
    
    def generate(self, video_path: str, output_srt: Optional[str] = None,
                 save_intermediate: bool = False) -> Path:
        """
        生成字幕的完整流程
        
        Args:
            video_path: 视频文件路径
            output_srt: 输出字幕路径（默认与视频同名）
            save_intermediate: 是否保存中间结果
        
        Returns:
            字幕文件路径
        """
        video_path = Path(video_path)
        if output_srt is None:
            output_srt = video_path.with_suffix('.srt')
        else:
            output_srt = Path(output_srt)
        
        # 1. 提取音频
        print("="*50)
        print("步骤 1/5: 提取音频")
        print("="*50)
        wav_path = self.extract_audio(video_path)
        
        # 2. VAD 分割
        print("\n" + "="*50)
        print("步骤 2/5: VAD 语音分割")
        print("="*50)
        segments, wav = self.vad_split(wav_path)
        
        if save_intermediate:
            # 保存分割结果
            segments_json = wav_path.parent / f"{video_path.stem}_segments.json"
            with open(segments_json, 'w', encoding='utf-8') as f:
                json.dump(segments, f, ensure_ascii=False, indent=2)
            print(f"分割结果已保存: {segments_json}")
        
        # 3. ASR + ForcedAlign
        print("\n" + "="*50)
        print("步骤 3/5: 语音识别与对齐")
        print("="*50)
        words = self.transcribe_segments(segments, wav)
        
        if save_intermediate:
            # 保存词级对齐结果
            words_json = wav_path.parent / f"{video_path.stem}_words.json"
            with open(words_json, 'w', encoding='utf-8') as f:
                json.dump([
                    {'text': w.text, 'start': w.start, 'end': w.end}
                    for w in words
                ], f, ensure_ascii=False, indent=2)
            print(f"对齐结果已保存: {words_json}")
        
        # 4. 字幕优化
        print("\n" + "="*50)
        print("步骤 4/5: 优化字幕")
        print("="*50)
        subtitle_lines = self.merger.process(segments, words)
        
        # 5. 保存字幕
        print("\n" + "="*50)
        print("步骤 5/5: 保存字幕")
        print("="*50)
        save_subtitles(subtitle_lines, output_srt)
        
        # 打印统计信息
        self._print_stats(subtitle_lines, segments)
        
        return output_srt
    
    def _print_stats(self, lines: List[SubtitleLine], segments: List[Dict]):
        """打印统计信息"""
        if not lines:
            print("没有生成字幕")
            return
        
        total_duration = sum(line.duration for line in lines)
        avg_duration = total_duration / len(lines)
        avg_chars = sum(line.char_count for line in lines) / len(lines)
        avg_speed = sum(line.reading_speed for line in lines) / len(lines)
        
        print("\n" + "="*50)
        print("生成统计")
        print("="*50)
        print(f"原始语音片段: {len(segments)} 个")
        print(f"生成字幕行: {len(lines)} 行")
        print(f"平均每行时长: {avg_duration:.2f}秒")
        print(f"平均每行字符: {avg_chars:.1f}个")
        print(f"平均阅读速度: {avg_speed:.1f} 字/秒")
        print(f"总字幕时长: {total_duration:.2f}秒")
        
        # 显示前3行示例
        print("\n字幕示例（前3行）:")
        for line in lines[:3]:
            print(f"  [{line.index}] {line.start:.2f}s - {line.end:.2f}s: {line.text[:50]}{'...' if len(line.text) > 50 else ''}")


def quick_generate(video_path: str, 
                   asr_model_path: str = '/mnt/g/models/Qwen3-ASR-1.7B',
                   aligner_path: str = '/mnt/g/models/Qwen3-ForcedAligner-0.6B',
                   language: Optional[str] = None,
                   output_srt: Optional[str] = None) -> Path:
    """
    快速生成字幕的便捷函数
    
    Args:
        video_path: 视频文件路径
        asr_model_path: ASR 模型路径
        aligner_path: ForcedAligner 模型路径
        language: 语言代码（None=自动检测）
        output_srt: 输出字幕路径
    
    Returns:
        字幕文件路径
    """
    config = SubtitleConfig(
        asr_model_path=asr_model_path,
        aligner_path=aligner_path,
        language=language,
    )
    
    generator = MovieSubtitleGenerator(config)
    return generator.generate(video_path, output_srt)


# 命令行入口
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="电影字幕生成器")
    parser.add_argument("video", help="视频文件路径")
    parser.add_argument("-o", "--output", help="输出字幕路径")
    parser.add_argument("-l", "--language", help="语言代码 (Chinese/English/None)")
    parser.add_argument("--asr-model", default='/mnt/g/models/Qwen3-ASR-1.7B', 
                       help="ASR 模型路径")
    parser.add_argument("--aligner", default='/mnt/g/models/Qwen3-ForcedAligner-0.6B',
                       help="ForcedAligner 模型路径")
    parser.add_argument("--save-intermediate", action="store_true",
                       help="保存中间结果")
    parser.add_argument("--max-chars", type=int, default=40,
                       help="每行最大字符数")
    
    args = parser.parse_args()
    
    language = args.language
    if language == "None":
        language = None
    
    config = SubtitleConfig(
        asr_model_path=args.asr_model,
        aligner_path=args.aligner,
        language=language,
        max_chars=args.max_chars,
    )
    
    generator = MovieSubtitleGenerator(config)
    generator.generate(args.video, args.output, args.save_intermediate)
