from pathlib import Path
from semsub.core.config import PipelineConfig
from semsub.core.pipeline import SubtitlePipeline
from semsub.core.progress import ProgressReporter, PipelineStage

class SimpleReporter(ProgressReporter):
    def on_log(self, msg, level='info'):
        print(f'[{level}] {msg}')
    def on_stage_start(self, stage, total):
        print(f'开始: {stage}')
    def on_progress(self, p):
        print(f'  {p.message}')
    def on_stage_complete(self, stage, result):
        print(f'完成: {stage}')
    def check_cancelled(self):
        pass
    def on_error(self, stage, error):
        print(f'错误: {stage} - {error}')
    def on_pipeline_complete(self, path):
        print(f'完成: {path}')
    def on_pipeline_start(self, stages):
        print(f'开始处理，阶段: {len(stages)}')

config = PipelineConfig()
config.llm.enabled = False  # 禁用 LLM
pipeline = SubtitlePipeline(config)
reporter = SimpleReporter()
output = pipeline.generate(Path('cutted_demo.mp4'), Path('cutted_demo_v5.srt'), reporter)
print(f'输出: {output}')
