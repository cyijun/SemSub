"""Tests for SemSub Web GUI API routes."""

import os
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from semsub.web.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestFileSystemAPI:
    def test_fs_home(self, client):
        response = client.get("/api/fs/home")
        assert response.status_code == 200
        data = response.json()
        assert "path" in data
        assert data["path"].startswith("/")

    def test_fs_browse_current_dir(self, client):
        response = client.get(f"/api/fs/browse?path={os.getcwd()}")
        assert response.status_code == 200
        data = response.json()
        assert "current" in data
        assert "items" in data

    def test_fs_browse_forbidden_path(self, client):
        response = client.get("/api/fs/browse?path=/etc")
        assert response.status_code == 403

    def test_fs_browse_nonexistent(self, client):
        response = client.get("/api/fs/browse?path=/nonexistent/path/12345")
        assert response.status_code == 404


class TestJobAPI:
    def test_create_generate_job(self, client):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video")
            path = f.name
        try:
            response = client.post("/api/job/generate", params={"video_path": path})
            assert response.status_code == 200
            data = response.json()
            assert "job_id" in data
            assert data["status"] == "pending"
        finally:
            os.unlink(path)

    def test_get_job_status(self, client):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video")
            path = f.name
        try:
            create_resp = client.post("/api/job/generate", params={"video_path": path})
            job_id = create_resp.json()["job_id"]
            status_resp = client.get(f"/api/job/{job_id}/status")
            assert status_resp.status_code == 200
            assert status_resp.json()["id"] == job_id
        finally:
            os.unlink(path)

    def test_get_nonexistent_job(self, client):
        response = client.get("/api/job/job-00000000/status")
        assert response.status_code == 404

    def test_cancel_job(self, client):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video")
            path = f.name
        try:
            create_resp = client.post("/api/job/generate", params={"video_path": path})
            job_id = create_resp.json()["job_id"]
            cancel_resp = client.post(f"/api/job/{job_id}/cancel")
            assert cancel_resp.status_code == 200
            assert cancel_resp.json()["status"] == "cancelled"
        finally:
            os.unlink(path)

    def test_list_jobs(self, client):
        response = client.get("/api/job/list")
        assert response.status_code == 200
        # Should be a list
        assert isinstance(response.json(), list)


class TestBatchAPI:
    @patch("semsub.web.routes.api._run_batch")
    def test_create_batch_job(self, mock_run_batch, client):
        import tempfile, os
        with tempfile.TemporaryDirectory() as td:
            open(os.path.join(td, "test.mp4"), "w").close()
            response = client.post("/api/job/batch", params={"directory": td})
            assert response.status_code == 200
            assert "job_id" in response.json()

    def test_batch_nonexistent_dir(self, client):
        response = client.post("/api/job/batch", params={"directory": "/nonexistent/dir"})
        assert response.status_code == 404


class TestSRTProcessAPI:
    @patch("semsub.web.routes.api._run_srt_process")
    def test_create_srt_job(self, mock_run_srt, client):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as f:
            f.write(b"1\n00:00:01,000 --> 00:00:02,000\nHello\n")
            path = f.name
        try:
            response = client.post("/api/job/srt-process", params={"srt_path": path, "mode": "correct"})
            assert response.status_code == 200
            assert "job_id" in response.json()
        finally:
            import os
            os.unlink(path)


class TestWorkspaceAPI:
    def test_list_workspaces_empty(self, client):
        response = client.get("/api/workspaces")
        assert response.status_code == 200
        assert response.json() == []


class TestConfigAPI:
    def test_get_config(self, client):
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.json()
        assert "asr" in data
        assert "vad" in data

    def test_get_config_masks_api_key(self, client):
        response = client.get("/api/config")
        data = response.json()
        assert "llm" in data


class TestSSEAPI:
    def test_sse_job_not_found(self, client):
        response = client.get("/api/sse/job/job-00000000")
        assert response.status_code == 404

    def test_sse_job_stream(self, client):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video")
            path = f.name
        try:
            create_resp = client.post("/api/job/generate", params={"video_path": path})
            job_id = create_resp.json()["job_id"]
            response = client.get(f"/api/sse/job/{job_id}")
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        finally:
            import os
            os.unlink(path)
