"""Unit tests for the QueueManager.

These tests verify that the SQLite-backed queue behaves as expected. We
use a temporary database file in a temporary directory to avoid
clobbering any real data.
"""

from __future__ import annotations

import asyncio
import os
import tempfile

import pytest

from autodl_enhanced.src.queue_manager import QueueManager


@pytest.mark.asyncio
async def test_add_and_fetch_task():
    # Create a temporary database file
    with tempfile.NamedTemporaryFile(delete=True) as tmp:
        qm = QueueManager(tmp.name)
        await qm.initialize()
        # Add a task
        task_id, is_new = await qm.add_task("https://example.com/video1")
        assert task_id == 1
        assert is_new
        # Fetch the task and ensure it's marked processing
        task = await qm.fetch_next_task()
        assert task is not None
        assert task.id == 1
        assert task.status == 'processing'
        # After fetch, there should be no pending tasks left
        none_task = await qm.fetch_next_task()
        assert none_task is None


@pytest.mark.asyncio
async def test_task_lifecycle():
    with tempfile.NamedTemporaryFile(delete=True) as tmp:
        qm = QueueManager(tmp.name, max_retries=2, base_delay=0)
        await qm.initialize()
        # Add and fetch a task
        await qm.add_task("https://example.com/video2")
        task = await qm.fetch_next_task()
        # Mark as failed (first attempt)
        await qm.reschedule_task(task.id, attempts=1)
        # Should be pending again
        pending = await qm.get_pending_tasks()
        assert pending and pending[0].id == task.id
        # Fetch again
        task2 = await qm.fetch_next_task()
        assert task2 is not None
        # On second failure, should mark permanently failed
        await qm.mark_failed(task2.id, "error")
        count_failed = await qm.count_by_status('failed')
        assert count_failed == 1
        # Clearing failed tasks removes them
        await qm.clear_failed_tasks()
        count_failed_after = await qm.count_by_status('failed')
        assert count_failed_after == 0
