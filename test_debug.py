from pathlib import Path
from semsub.core.config import PipelineConfig
from semsub.core.pipeline import SubtitlePipeline
from semsub.core.progress import ProgressReporter, PipelineStage
import json

class SimpleReporter(ProgressReporter):
    def on_log(self, msg, level='info'):
        print(f'[{level}] {msg}')
    def on_stage_start(self, stage, total):
        print(f'开始: {stage}')
    def on_progress(self, p):
        print(f'  {p.message}')
    def on_stage_complete(self, stage, result):
        print(f'完成: {stage}')
        # 保存 ASR 结果
        if stage == PipelineStage.ASR_TRANSCRIBE:
            with open('debug_transcription.json', 'w', encoding='utf-8') as f:
                json.dump([{'text': s.text, 'words': [{'text': w.text, 'start': w.start, 'end': w.end} for w in s.words]} for s in result], f, ensure_ascii=False, indent=2)
            print('已保存 debug_transcription.json')
    def check_cancelled(self):
        pass
    def on_error(self, stage, error):
        print(f'错误: {stage} - {error}')
    def on_pipeline_complete(self, path):
        print(f'完成: {path}')
    def on_pipeline_start(self, stages):
        print(f'开始处理，阶段: {len(stages)}')

config = PipelineConfig()
config.llm.enabled = False
config.output.save_intermediate = True
pipeline = SubtitlePipeline(config)
reporter = SimpleReporter()
output = pipeline.generate(Path('cutted_demo.mp4'), Path('cutted_demo_v6.srt'), reporter)
print(f'输出: {output}')
