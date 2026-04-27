import pytest
from semsub.web.job_manager import JobManager, JobType, JobStatus
from semsub.web.progress_reporter import WebProgressReporter
from semsub.core.progress import PipelineStage, StageProgress


class TestWebProgressReporter:
    def test_on_pipeline_start_sets_running(self):
        manager = JobManager()
        job_id = manager.create_job(JobType.GENERATE, {})
        reporter = WebProgressReporter(job_id, manager)
        reporter.on_pipeline_start([PipelineStage.AUDIO_EXTRACT])
        job = manager.get_job(job_id)
        assert job.status == JobStatus.RUNNING

    def test_on_progress_updates_percent(self):
        manager = JobManager()
        job_id = manager.create_job(JobType.GENERATE, {})
        reporter = WebProgressReporter(job_id, manager)
        progress = StageProgress(
            stage=PipelineStage.ASR_TRANSCRIBE,
            current=5, total=10, message="halfway", percent=50.0
        )
        reporter.on_progress(progress)
        job = manager.get_job(job_id)
        assert job.progress_percent == 50.0
        assert job.current_stage == "ASR 转录"

    def test_on_log_appends_message(self):
        manager = JobManager()
        job_id = manager.create_job(JobType.GENERATE, {})
        reporter = WebProgressReporter(job_id, manager)
        reporter.on_log("test message", "info")
        job = manager.get_job(job_id)
        assert any("test message" in log for log in job.logs)

    def test_check_cancelled_raises(self):
        manager = JobManager()
        job_id = manager.create_job(JobType.GENERATE, {})
        reporter = WebProgressReporter(job_id, manager)
        manager.cancel_job(job_id)
        from semsub.core.progress import CancellationError
        with pytest.raises(CancellationError):
            reporter.check_cancelled()

    def test_on_pipeline_complete_sets_completed(self):
        manager = JobManager()
        job_id = manager.create_job(JobType.GENERATE, {})
        reporter = WebProgressReporter(job_id, manager)
        reporter.on_pipeline_complete("/out.srt")
        job = manager.get_job(job_id)
        assert job.status == JobStatus.COMPLETED
        assert job.result["output_path"] == "/out.srt"

    def test_on_error_sets_failed(self):
        manager = JobManager()
        job_id = manager.create_job(JobType.GENERATE, {})
        reporter = WebProgressReporter(job_id, manager)
        reporter.on_error(PipelineStage.ASR_TRANSCRIBE, RuntimeError("gpu oom"))
        job = manager.get_job(job_id)
        assert job.status == JobStatus.FAILED
        assert "gpu oom" in job.error
