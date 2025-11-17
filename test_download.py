#!/usr/bin/env python3
"""Test script to add a URL to the download queue."""

import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config_manager import load_config
from queue_manager import QueueManager

async def test_add_url():
    """Add a test URL to the queue."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config = load_config(base_dir)

    # Initialize queue manager
    queue_manager = QueueManager(config.db_path)
    await queue_manager.initialize()

    # Add a test URL (single video, not playlist)
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rickroll - short and reliable

    print(f"Adding test URL to queue: {test_url}")
    task_id = await queue_manager.add_task(test_url)
    print(f"✅ Added task with ID: {task_id}")

    # Check queue status
    pending = await queue_manager.get_pending_tasks()
    print(f"📋 Pending tasks in queue: {len(pending)}")

    for task in pending[-3:]:  # Show last 3
        print(f"  Task {task.id}: {task.url}")

if __name__ == "__main__":
    asyncio.run(test_add_url())
