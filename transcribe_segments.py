"""
批量转录音频片段并输出为 TXT

对 segments 目录下的所有 wav 文件进行 ASR 识别，保存为文本格式
"""

import json
import torch
import torchaudio
from pathlib import Path
from typing import List, Dict, Optional
from datetime import timedelta

try:
    from qwen_asr import Qwen3ASRModel
except ImportError:
    Qwen3ASRModel = None
    print("警告: qwen_asr 模块未安装")


class SegmentTranscriber:
    """片段转录器"""
    
    def __init__(
        self,
        asr_model_path: str = '/mnt/g/models/Qwen3-ASR-1.7B',
        device: str = "cuda:0",
        batch_size: int = 8,
        language: Optional[str] = None,
    ):
        self.asr_model_path = asr_model_path
        self.device = device
        self.batch_size = batch_size
        self.language = language
        self.model = None
    
    def _load_model(self):
        """加载 ASR 模型"""
        if self.model is not None:
            return
        
        if Qwen3ASRModel is None:
            raise RuntimeError("qwen_asr 模块未安装")
        
        print(f"正在加载 ASR 模型: {self.asr_model_path}")
        self.model = Qwen3ASRModel.from_pretrained(
            self.asr_model_path,
            dtype=torch.bfloat16,
            device_map=self.device,
            max_inference_batch_size=self.batch_size,
            max_new_tokens=256,
        )
        print("模型加载完成")
    
    def load_segments_info(self, json_path: str = "segments/segments.json") -> List[Dict]:
        """加载片段信息"""
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def format_time(self, seconds: float) -> str:
        """格式化时间为 HH:MM:SS.mmm"""
        td = timedelta(seconds=seconds)
        hours, remainder = divmod(td.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        milliseconds = int(td.microseconds / 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
    
    def transcribe_batch(self, audio_files: List[str]) -> List:
        """批量转录音频"""
        self._load_model()
        
        results = self.model.transcribe(
            audio=audio_files,
            language=[self.language] * len(audio_files),
        )
        return results
    
    def transcribe_all(
        self,
        segments_dir: str = "segments",
        output_txt: str = "transcription.txt",
        output_json: Optional[str] = "transcription.json",
        resume: bool = True,  # 支持断点续传
    ):
        """
        转录所有片段并保存
        
        Args:
            segments_dir: 片段目录
            output_txt: 输出 TXT 文件路径
            output_json: 输出 JSON 文件路径（可选）
        """
        segments_dir = Path(segments_dir)
        
        # 加载片段信息
        segments_json = segments_dir / "segments.json"
        if segments_json.exists():
            segments = self.load_segments_info(str(segments_json))
        else:
            # 如果没有 JSON，扫描目录中的 wav 文件
            wav_files = sorted(segments_dir.glob("segment_*.wav"))
            segments = [
                {
                    'index': i,
                    'file': f.name,
                    'start': 0,  # 未知
                    'end': 0,
                }
                for i, f in enumerate(wav_files)
            ]
        
        total = len(segments)
        print(f"共 {total} 个片段需要转录")
        
        # 检查是否有之前的进度
        checkpoint_file = Path(output_txt).with_suffix('.checkpoint.json')
        processed_indices = set()
        if resume and checkpoint_file.exists():
            try:
                with open(checkpoint_file, 'r', encoding='utf-8') as f:
                    checkpoint_data = json.load(f)
                    processed_indices = set(checkpoint_data.get('processed', []))
                    print(f"发现检查点，已处理 {len(processed_indices)} 个片段，继续...")
            except:
                pass
        
        # 准备批处理
        all_results = []
        
        for batch_start in range(0, total, self.batch_size):
            batch_end = min(batch_start + self.batch_size, total)
            batch_segments = segments[batch_start:batch_end]
            
            # 检查是否全部已处理
            batch_indices = {seg.get('index', 0) for seg in batch_segments}
            if batch_indices <= processed_indices:
                print(f"批次 {batch_start//self.batch_size + 1} 已处理，跳过")
                continue
            
            print(f"\n处理批次 {batch_start//self.batch_size + 1}/{(total-1)//self.batch_size + 1} "
                  f"({batch_start}-{batch_end-1})")
            
            # 准备音频文件路径
            audio_files = [
                str(segments_dir / seg['file'])
                for seg in batch_segments
            ]
            
            # 检查文件是否存在
            existing_files = []
            valid_segments = []
            for seg, audio_file in zip(batch_segments, audio_files):
                if Path(audio_file).exists():
                    existing_files.append(audio_file)
                    valid_segments.append(seg)
                else:
                    print(f"  警告: 文件不存在 {audio_file}")
                    all_results.append({
                        **seg,
                        'text': '[FILE_NOT_FOUND]',
                        'language': 'unknown',
                    })
            
            if not existing_files:
                continue
            
            # 批量转录
            try:
                batch_results = self.transcribe_batch(existing_files)
                
                for seg, result in zip(valid_segments, batch_results):
                    all_results.append({
                        **seg,
                        'text': result.text.strip() if result.text else '',
                        'language': result.language if hasattr(result, 'language') else 'unknown',
                    })
                    
                    # 打印进度
                    progress = (len(all_results) / total) * 100
                    print(f"  [{seg.get('index', '?'):04d}] [{progress:5.1f}%] {result.text[:60]}{'...' if len(result.text) > 60 else ''}")
                    
            except Exception as e:
                print(f"  错误: {e}")
                for seg in valid_segments:
                    all_results.append({
                        **seg,
                        'text': f'[ERROR: {str(e)[:50]}]',
                        'language': 'error',
                    })
            
            # 保存检查点
            if resume:
                processed_indices.update(seg.get('index', 0) for seg in batch_segments)
                with open(checkpoint_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'processed': list(processed_indices),
                        'last_batch': batch_start // self.batch_size + 1,
                    }, f)
        
        # 完成后删除检查点
        if checkpoint_file.exists():
            checkpoint_file.unlink()
        
        # 按索引排序
        all_results.sort(key=lambda x: x.get('index', 0))
        
        # 保存为 TXT
        self._save_txt(all_results, output_txt)
        
        # 保存为 JSON（可选）
        if output_json:
            self._save_json(all_results, output_json)
        
        return all_results
    
    def _save_txt(self, results: List[Dict], output_path: str):
        """保存为 TXT 格式"""
        output_path = Path(output_path)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("音频片段转录结果\n")
            f.write("=" * 80 + "\n\n")
            
            for r in results:
                idx = r.get('index', 0)
                start = r.get('start', 0)
                end = r.get('end', 0)
                text = r.get('text', '')
                lang = r.get('language', 'unknown')
                
                # 格式化时间
                if start and end:
                    time_str = f"{self.format_time(start)} --> {self.format_time(end)}"
                    duration = end - start
                    time_info = f"[{time_str}] (时长: {duration:.2f}s)"
                else:
                    time_info = "[时间未知]"
                
                f.write(f"[{idx:04d}] {time_info}\n")
                f.write(f"语言: {lang}\n")
                f.write(f"文本: {text}\n")
                f.write("-" * 80 + "\n\n")
            
            # 统计信息
            total = len(results)
            has_text = sum(1 for r in results if r.get('text') and not r.get('text', '').startswith('['))
            f.write("=" * 80 + "\n")
            f.write(f"总计: {total} 个片段\n")
            f.write(f"成功识别: {has_text} 个\n")
            f.write("=" * 80 + "\n")
        
        print(f"\nTXT 文件已保存: {output_path}")
    
    def _save_json(self, results: List[Dict], output_path: str):
        """保存为 JSON 格式"""
        output_path = Path(output_path)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"JSON 文件已保存: {output_path}")


def quick_transcribe(
    segments_dir: str = "segments",
    output_txt: str = "transcription.txt",
    asr_model_path: str = '/mnt/g/models/Qwen3-ASR-1.7B',
    language: Optional[str] = None,
    batch_size: int = 8,
):
    """
    快速转录函数
    
    Args:
        segments_dir: 片段目录
        output_txt: 输出 TXT 路径
        asr_model_path: ASR 模型路径
        language: 语言代码（None=自动检测）
        batch_size: 批处理大小
    """
    transcriber = SegmentTranscriber(
        asr_model_path=asr_model_path,
        language=language,
        batch_size=batch_size,
    )
    
    return transcriber.transcribe_all(
        segments_dir=segments_dir,
        output_txt=output_txt,
        output_json=output_txt.replace('.txt', '.json'),
    )


# 命令行入口
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="批量转录音频片段")
    parser.add_argument("-i", "--input", default="segments", help="片段目录")
    parser.add_argument("-o", "--output", default="transcription.txt", help="输出 TXT 文件")
    parser.add_argument("-l", "--language", help="语言代码 (Chinese/English/None)")
    parser.add_argument("--asr-model", default='/mnt/g/models/Qwen3-ASR-1.7B', help="ASR 模型路径")
    parser.add_argument("-b", "--batch-size", type=int, default=8, help="批处理大小")
    
    args = parser.parse_args()
    
    language = args.language
    if language == "None":
        language = None
    
    quick_transcribe(
        segments_dir=args.input,
        output_txt=args.output,
        asr_model_path=args.asr_model,
        language=language,
        batch_size=args.batch_size,
    )
