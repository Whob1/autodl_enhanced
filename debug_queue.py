#!/usr/bin/env python3
"""Debug script to check queue status and database contents."""

import asyncio
import os
import sys
import sqlite3
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config_manager import load_config

async def check_queue():
    """Check the current state of the download queue."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config = load_config(base_dir)

    db_path = config.db_path
    print(f"Database path: {db_path}")
    print(f"Download directory: {config.download_dir}")
    print()

    if not os.path.exists(db_path):
        print("❌ Database file does not exist!")
        return

    # Check database contents
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all tasks
    cursor.execute("SELECT id, url, status, attempts, added_at, updated_at, next_attempt_at, file_path, error_message FROM tasks ORDER BY id")
    tasks = cursor.fetchall()

    print(f"📊 Total tasks in database: {len(tasks)}")
    print()

    # Group by status
    status_counts = {}
    for task in tasks:
        status = task[2]
        status_counts[status] = status_counts.get(status, 0) + 1

    print("📈 Tasks by status:")
    for status, count in status_counts.items():
        print(f"  {status}: {count}")
    print()

    # Show recent tasks
    print("📋 Recent tasks (last 10):")
    for task in tasks[-10:]:
        task_id, url, status, attempts, added_at, updated_at, next_attempt_at, file_path, error_message = task
        added_time = datetime.fromtimestamp(added_at).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  ID {task_id}: {status} - {url[:50]}{'...' if len(url) > 50 else ''}")
        print(f"    Added: {added_time}, Attempts: {attempts}")
        if error_message:
            print(f"    Error: {error_message}")
        if file_path:
            print(f"    File: {file_path}")
        print()

    # Check if download directory exists and has space
    download_dir = config.download_dir
    if os.path.exists(download_dir):
        stat = os.statvfs(download_dir)
        free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
        print(f"💾 Download directory: {download_dir}")
        print(f"Free space: {free_gb:.2f} GB")
    else:
        print(f"❌ Download directory does not exist: {download_dir}")

    # Check for any running yt-dlp processes
    import subprocess
    try:
        result = subprocess.run(['pgrep', '-f', 'yt-dlp'], capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            print(f"🎬 Running yt-dlp processes: {len(pids)}")
            for pid in pids[:5]:  # Show first 5
                print(f"  PID: {pid}")
        else:
            print("🎬 No running yt-dlp processes")
    except:
        print("⚠️ Could not check for running yt-dlp processes")

    # Option to clear failed tasks
    if len([t for t in tasks if t[2] == 'failed']) > 0:
        print()
        print("💡 To clear failed tasks, you can run:")
        print("python3 -c \"import asyncio; from debug_queue import clear_failed_tasks; asyncio.run(clear_failed_tasks())\"")

    conn.close()

async def clear_failed_tasks():
    """Clear all failed tasks from the database."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config = load_config(base_dir)

    db_path = config.db_path
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Count failed tasks before deletion
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE status='failed'")
    count_before = cursor.fetchone()[0]

    # Delete failed tasks
    cursor.execute("DELETE FROM tasks WHERE status='failed'")
    conn.commit()

    print(f"🗑️ Cleared {count_before} failed tasks from the database")

    conn.close()

if __name__ == "__main__":
    asyncio.run(check_queue())
