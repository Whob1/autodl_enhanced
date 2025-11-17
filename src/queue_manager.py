"""SQLite-backed queue manager for the Enhanced AutoDL Telegram Bot.

This module implements a persistent task queue on top of SQLite. Each
task corresponds to a URL to be downloaded. The queue persists across
restarts and supports retrying failed tasks with exponential backoff.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Optional, List, Tuple

import aiosqlite

from .utils.logger import get_logger
from .utils.deduplication import normalize_url, compute_url_hash, extract_video_id


@dataclass
class DownloadTask:
    """Represents a single download task stored in the SQLite queue."""

    id: int
    url: str
    status: str
    attempts: int
    added_at: float
    updated_at: float
    next_attempt_at: Optional[float]
    file_path: Optional[str]
    error_message: Optional[str]
    url_hash: Optional[str] = None
    video_id: Optional[str] = None
    download_method: str = "auto"


class QueueManager:
    """Manage persistent download tasks using SQLite.

    Parameters
    ----------
    db_path: str
        Path to the SQLite database file.
    max_retries: int, optional
        Maximum number of retry attempts before marking a task as failed.
    base_delay: int, optional
        Base delay in seconds used for exponential backoff when
        calculating the next attempt time (e.g., 2**attempts * base_delay).
    """

    def __init__(self, db_path: str, max_retries: int = 3, base_delay: int = 60):
        self.db_path = db_path
        self.max_retries = max_retries
        self.base_delay = base_delay
        # Lock to prevent concurrent selection of the same task by multiple workers
        self._lock = asyncio.Lock()
        self.logger = get_logger(self.__class__.__name__)

    async def initialize(self) -> None:
        """Initialize the database and reset tasks stuck in processing state."""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    added_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    next_attempt_at REAL,
                    file_path TEXT,
                    error_message TEXT,
                    url_hash TEXT,
                    video_id TEXT,
                    download_method TEXT NOT NULL DEFAULT 'auto'
                )
                """
            )
            await conn.commit()

            # Add new columns if they don't exist (for existing databases)
            try:
                await conn.execute("ALTER TABLE tasks ADD COLUMN url_hash TEXT")
                await conn.commit()
            except:
                pass  # Column already exists

            try:
                await conn.execute("ALTER TABLE tasks ADD COLUMN video_id TEXT")
                await conn.commit()
            except:
                pass  # Column already exists

            try:
                await conn.execute("ALTER TABLE tasks ADD COLUMN download_method TEXT NOT NULL DEFAULT 'auto'")
                await conn.commit()
            except:
                pass  # Column already exists

            # Create indices for fast duplicate detection
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_url_hash ON tasks(url_hash)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_video_id ON tasks(video_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON tasks(status)")
            await conn.commit()

            # Reset tasks that were in processing state when the bot crashed
            await conn.execute(
                "UPDATE tasks SET status='pending' WHERE status='processing'"
            )
            await conn.commit()

    async def check_duplicate(self, url: str) -> Tuple[bool, Optional[DownloadTask]]:
        """Check if a URL is a duplicate of an existing task.

        Parameters
        ----------
        url : str
            The URL to check

        Returns
        -------
        Tuple[bool, Optional[DownloadTask]]
            (is_duplicate, existing_task) - existing_task is None if not duplicate
        """
        url_hash = compute_url_hash(url)
        video_id = extract_video_id(url)

        async with aiosqlite.connect(self.db_path) as conn:
            # Check by URL hash first (most reliable)
            cursor = await conn.execute(
                """
                SELECT id, url, status, attempts, added_at, updated_at, next_attempt_at, file_path, error_message, url_hash, video_id, download_method
                FROM tasks
                WHERE url_hash = ? AND status IN ('pending', 'processing', 'completed')
                ORDER BY id DESC
                LIMIT 1
                """,
                (url_hash,)
            )
            row = await cursor.fetchone()
            if row:
                task = DownloadTask(*row)
                self.logger.info(f"Duplicate detected by URL hash: {url[:50]}... matches task {task.id}")
                return True, task

            # Check by video ID if available
            if video_id:
                cursor = await conn.execute(
                    """
                SELECT id, url, status, attempts, added_at, updated_at, next_attempt_at, file_path, error_message, url_hash, video_id, download_method
                    FROM tasks
                WHERE video_id = ? AND status IN ('pending', 'processing', 'completed')
                ORDER BY id DESC
                LIMIT 1
                """,
                (video_id,)
            )
                row = await cursor.fetchone()
                if row:
                    task = DownloadTask(*row)
                    self.logger.info(f"Duplicate detected by video ID {video_id}: {url[:50]}... matches task {task.id}")
                    return True, task

            return False, None

    async def add_task(self, url: str, skip_duplicate_check: bool = False, download_method: str = "auto") -> Tuple[int, bool]:
        """Add a new task to the queue.

        Parameters
        ----------
        url: str
            The URL to download.
        skip_duplicate_check: bool
            If True, skip the duplicate check (default False)

        Returns
        -------
        Tuple[int, bool]
            (task_id, is_new) - is_new is False if it was a duplicate
        """
        download_method = download_method if download_method else "auto"
        # Check for duplicates first
        if not skip_duplicate_check:
            is_dup, existing_task = await self.check_duplicate(url)
            if is_dup:
                self.logger.info(f"Skipping duplicate URL: {url[:50]}... (existing task: {existing_task.id})")
                return existing_task.id, False

        # Compute hash and video ID for new task
        url_hash = compute_url_hash(url)
        video_id = extract_video_id(url)

        now = time.time()
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                """
                INSERT INTO tasks (url, status, attempts, added_at, updated_at, url_hash, video_id, download_method)
                VALUES (?, 'pending', 0, ?, ?, ?, ?, ?)
                """,
                (url, now, now, url_hash, video_id, download_method),
            )
            await conn.commit()
            task_id = cursor.lastrowid
            self.logger.info(f"Added new task {task_id}: {url[:50]}... (hash: {url_hash[:8]}, video_id: {video_id})")
            return task_id, True

    async def _fetch_next_row(self, conn) -> Optional[DownloadTask]:
        """Select the next eligible task and mark it as processing.

        This helper must be called with the queue manager's lock held.
        """
        now = time.time()
        # Find the next task that is pending and ready for another attempt
        cursor = await conn.execute(
                """
                SELECT id, url, status, attempts, added_at, updated_at, next_attempt_at, file_path, error_message, url_hash, video_id, download_method
                FROM tasks
                WHERE status='pending'
                  AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
                ORDER BY id ASC
                LIMIT 1
                """,
                (now,),
            )
        row = await cursor.fetchone()
        if row is None:
            return None
        task = DownloadTask(*row)
        # Immediately mark as processing
        await conn.execute(
            "UPDATE tasks SET status='processing', updated_at=? WHERE id=?",
            (now, task.id),
        )
        await conn.commit()
        task.status = 'processing'
        task.updated_at = now
        return task

    async def fetch_next_task(self) -> Optional[DownloadTask]:
        """Fetch the next pending task and mark it as processing.

        Returns ``None`` if there are no pending tasks ready for processing.
        """
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                task = await self._fetch_next_row(conn)
                if task:
                    self.logger.debug(f"Fetched task {task.id}: {task.url} (status: {task.status})")
                return task

    async def mark_completed(self, task_id: int, file_path: str) -> None:
        """Mark a task as completed and record the output file path."""
        now = time.time()
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "UPDATE tasks SET status='completed', file_path=?, updated_at=? WHERE id=?",
                (file_path, now, task_id),
            )
            await conn.commit()

    async def mark_failed(self, task_id: int, error_message: str) -> None:
        """Mark a task as failed (no more retries)."""
        now = time.time()
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "UPDATE tasks SET status='failed', error_message=?, updated_at=? WHERE id=?",
                (error_message, now, task_id),
            )
            await conn.commit()

    async def reschedule_task(self, task_id: int, attempts: int) -> None:
        """Increment attempts and reschedule the task with exponential backoff."""
        # Compute next attempt time using exponential backoff (attempts start at 0)
        delay = (2 ** attempts) * self.base_delay
        next_time = time.time() + delay
        now = time.time()
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                UPDATE tasks
                SET attempts = attempts + 1,
                    status = 'pending',
                    next_attempt_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (next_time, now, task_id),
            )
            await conn.commit()

    async def get_pending_tasks(self) -> List[DownloadTask]:
        """Return a list of tasks currently in the pending state."""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                """SELECT id, url, status, attempts, added_at, updated_at, next_attempt_at, file_path, error_message, url_hash, video_id, download_method FROM tasks WHERE status='pending' ORDER BY id"""
            )
            rows = await cursor.fetchall()
            return [DownloadTask(*row) for row in rows]

    async def get_processing_tasks(self) -> List[DownloadTask]:
        """Return a list of tasks currently in the processing state."""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                """SELECT id, url, status, attempts, added_at, updated_at, next_attempt_at, file_path, error_message, url_hash, video_id, download_method FROM tasks WHERE status='processing' ORDER BY id"""
            )
            rows = await cursor.fetchall()
            return [DownloadTask(*row) for row in rows]

    async def clear_failed_tasks(self) -> None:
        """Remove tasks that have permanently failed from the database."""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("DELETE FROM tasks WHERE status='failed'")
            await conn.commit()

    async def retry_failed_tasks(self) -> int:
        """Reset failed tasks to pending state for retry.

        Returns
        -------
        int
            Number of tasks reset
        """
        now = time.time()
        async with aiosqlite.connect(self.db_path) as conn:
            # Count failed tasks
            cursor = await conn.execute("SELECT COUNT(*) FROM tasks WHERE status='failed'")
            result = await cursor.fetchone()
            count = result[0] if result else 0

            if count > 0:
                # Reset failed tasks to pending with attempts reset
                await conn.execute(
                    """
                    UPDATE tasks
                    SET status='pending',
                        attempts=0,
                        next_attempt_at=NULL,
                        error_message=NULL,
                        updated_at=?
                    WHERE status='failed'
                    """,
                    (now,)
                )
                await conn.commit()
                self.logger.info(f"Reset {count} failed tasks to pending for retry")

            return count

    async def count_by_status(self, status: str) -> int:
        """Return the number of tasks with the given status."""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status=?", (status,)
            )
            result = await cursor.fetchone()
            return result[0] if result else 0
