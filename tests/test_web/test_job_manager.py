import pytest
from semsub.web.job_manager import JobManager, JobState, JobType, JobStatus


class TestJobManager:
    def test_create_job_returns_id(self):
        manager = JobManager()
        job_id = manager.create_job(JobType.GENERATE, {"video_path": "/tmp/test.mp4"})
        assert job_id.startswith("job-")
        assert len(job_id) == 12

    def test_get_job(self):
        manager = JobManager()
        job_id = manager.create_job(JobType.GENERATE, {"video_path": "/tmp/test.mp4"})
        job = manager.get_job(job_id)
        assert job is not None
        assert job.type == JobType.GENERATE
        assert job.status == JobStatus.PENDING

    def test_update_progress(self):
        manager = JobManager()
        job_id = manager.create_job(JobType.GENERATE, {})
        manager.update_progress(job_id, 50.0, "03_asr", "processing")
        job = manager.get_job(job_id)
        assert job.progress_percent == 50.0
        assert job.current_stage == "03_asr"
        assert job.message == "processing"

    def test_append_log(self):
        manager = JobManager()
        job_id = manager.create_job(JobType.GENERATE, {})
        manager.append_log(job_id, "log line 1")
        manager.append_log(job_id, "log line 2")
        job = manager.get_job(job_id)
        assert len(job.logs) == 2
        assert job.logs[0] == "log line 1"

    def test_cancel_job(self):
        manager = JobManager()
        job_id = manager.create_job(JobType.GENERATE, {})
        assert manager.cancel_job(job_id) is True
        assert manager.is_cancelled(job_id) is True
        job = manager.get_job(job_id)
        assert job.status == JobStatus.CANCELLED

    def test_set_status_completed(self):
        manager = JobManager()
        job_id = manager.create_job(JobType.GENERATE, {})
        manager.set_status(job_id, JobStatus.COMPLETED, result={"path": "/out.srt"})
        job = manager.get_job(job_id)
        assert job.status == JobStatus.COMPLETED
        assert job.result == {"path": "/out.srt"}
        assert job.completed_at is not None

    def test_list_jobs(self):
        manager = JobManager()
        manager.create_job(JobType.GENERATE, {})
        manager.create_job(JobType.BATCH, {})
        jobs = manager.list_jobs()
        assert len(jobs) == 2

    def test_cleanup_old_jobs(self):
        import time
        manager = JobManager()
        job_id = manager.create_job(JobType.GENERATE, {})
        manager.set_status(job_id, JobStatus.COMPLETED)
        # Manually set completed_at to old time
        from datetime import datetime, timedelta
        manager._jobs[job_id].completed_at = datetime.now() - timedelta(hours=25)
        manager.cleanup_old_jobs(max_age_hours=24)
        assert manager.get_job(job_id) is None
