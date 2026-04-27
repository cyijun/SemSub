"""Tests for web page routes."""

import pytest
from fastapi.testclient import TestClient

from semsub.web.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestPages:
    def test_home_page(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "SemSub" in response.text

    def test_generate_page(self, client):
        response = client.get("/generate")
        assert response.status_code == 200
        assert "生成字幕" in response.text

    def test_batch_page(self, client):
        response = client.get("/batch")
        assert response.status_code == 200
        assert "批量处理" in response.text

    def test_srt_process_page(self, client):
        response = client.get("/srt-process")
        assert response.status_code == 200
        assert "SRT" in response.text

    def test_workspaces_page(self, client):
        response = client.get("/workspaces")
        assert response.status_code == 200
        assert "工作区" in response.text

    def test_config_page(self, client):
        response = client.get("/config")
        assert response.status_code == 200
        assert "设置" in response.text
