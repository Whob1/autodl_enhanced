"""Unit tests for the DownloadManager.

These tests simulate the behaviour of the download manager when
downloads succeed or fail without actually fetching any data. We use
monkeypatching to override the internal _download method.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from autodl_enhanced.src.queue_manager import QueueManager, DownloadTask
from autodl_enhanced.src.download_manager import DownloadManager
from autodl_enhanced.src.config_manager import Config


def create_config(tmp_dir: str) -> Config:
    """Helper to construct a Config object for tests."""
    os.environ["TELEGRAM_BOT_TOKEN"] = "dummy-token"
    os.environ["DOWNLOAD_DIR"] = tmp_dir
    os.environ["MIN_CONCURRENT"] = "1"
    os.environ["MAX_CONCURRENT"] = "1"
    os.environ["CONCURRENCY_CPU_THRESHOLD"] = "90"
    os.environ["CONCURRENCY_DISK_THRESHOLD"] = "90"
    os.environ["FEED_POLL_INTERVAL"] = "60"
    os.environ["FEED_MAX_ITEMS_PER_POLL"] = "1"
    os.environ["FEED_FETCH_TIMEOUT"] = "5"
    config = Config(tmp_dir)
    os.makedirs(os.path.dirname(config.db_path), exist_ok=True)
    os.makedirs(config.download_dir, exist_ok=True)
    return config


@pytest.mark.asyncio
async def test_process_task_success(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        config = create_config(tmpdir)
        # Create queue manager
        qm = QueueManager(config.db_path, max_retries=1)
        await qm.initialize()
        await qm.add_task("https://example.com/video3")
        task = await qm.fetch_next_task()
        # Create download manager
        dm = DownloadManager(qm, config)
        # Monkeypatch _download to always succeed
        async def fake_download(task: DownloadTask) -> str:
            return os.path.join(config.download_dir, "dummy.mp4")
        monkeypatch.setattr(dm, "_download", fake_download)
        # Record completed calls
        recorded = {}
        async def fake_mark_completed(task_id: int, file_path: str) -> None:
            recorded['called'] = (task_id, file_path)
        monkeypatch.setattr(qm, "mark_completed", fake_mark_completed)
        await dm._process_task(task)
        # Ensure mark_completed was called with the task id
        assert recorded.get('called') == (task.id, os.path.join(config.download_dir, "dummy.mp4"))


@pytest.mark.asyncio
async def test_process_task_failure(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        config = create_config(tmpdir)
        qm = QueueManager(config.db_path, max_retries=1)
        await qm.initialize()
        await qm.add_task("https://example.com/video4")
        task = await qm.fetch_next_task()
        dm = DownloadManager(qm, config)
        # Monkeypatch _download to raise
        async def fake_download(task: DownloadTask) -> str:
            raise RuntimeError("Simulated download failure")
        monkeypatch.setattr(dm, "_download", fake_download)
        recorded = {}
        async def fake_mark_failed(task_id: int, error_message: str) -> None:
            recorded['failed'] = (task_id, error_message)
        monkeypatch.setattr(qm, "mark_failed", fake_mark_failed)
        # Also monkeypatch reschedule_task so we know if it's called (should not be because max_retries=1)
        async def fake_reschedule_task(task_id: int, attempts: int) -> None:
            recorded['rescheduled'] = task_id
        monkeypatch.setattr(qm, "reschedule_task", fake_reschedule_task)
        await dm._process_task(task)
        # Since max_retries=1 and attempts start at 0, the first failure should mark the task as failed
        assert 'failed' in recorded
        assert recorded['failed'][0] == task.id
        assert 'rescheduled' not in recorded
