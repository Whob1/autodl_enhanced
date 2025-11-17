"""RSS/Atom feed polling service for the Enhanced AutoDL bot."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import List, Optional

import aiohttp
import aiosqlite
import feedparser

from .queue_manager import QueueManager
from .utils import validators
from .utils.logger import get_logger


@dataclass
class Feed:
    id: int
    url: str
    added_at: float
    last_polled: Optional[float]
    last_entry_id: Optional[str]


class FeedManager:
    """Poll RSS/Atom feeds and enqueue new entries."""

    def __init__(
        self,
        db_path: str,
        poll_interval: int = 300,
        max_items_per_poll: int = 5,
        timeout: float = 20.0,
    ):
        self.db_path = db_path
        self.poll_interval = poll_interval
        self.max_items_per_poll = max_items_per_poll
        self.timeout = timeout
        self.logger = get_logger(self.__class__.__name__)
        self._session: Optional[aiohttp.ClientSession] = None
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    async def initialize(self) -> None:
        """Prepare storage and HTTP client."""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS feeds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL UNIQUE,
                    added_at REAL NOT NULL,
                    last_polled REAL,
                    last_entry_id TEXT
                )
                """
            )
            await conn.commit()
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)

    async def add_feed(self, url: str) -> tuple[int, bool]:
        """Add a new feed to the database."""
        normalized = validators.sanitize_url(url)
        if not normalized:
            raise ValueError("Invalid feed URL")
        now = time.time()
        async with aiosqlite.connect(self.db_path) as conn:
            try:
                cursor = await conn.execute(
                    """
                    INSERT INTO feeds (url, added_at)
                    VALUES (?, ?)
                    """,
                    (normalized, now),
                )
                await conn.commit()
                feed_id = cursor.lastrowid
                self.logger.info("Added feed %s (id=%d)", normalized, feed_id)
                return feed_id, True
            except aiosqlite.IntegrityError:
                cursor = await conn.execute(
                    "SELECT id FROM feeds WHERE url = ?",
                    (normalized,),
                )
                row = await cursor.fetchone()
                feed_id = row[0] if row else 0
                self.logger.info("Feed already registered: %s (id=%s)", normalized, feed_id)
                return feed_id, False

    async def list_feeds(self) -> List[Feed]:
        """Return all configured feeds."""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT id, url, added_at, last_polled, last_entry_id FROM feeds ORDER BY id"
            )
            rows = await cursor.fetchall()
        return [Feed(*row) for row in rows]

    async def start(self, queue_manager: QueueManager) -> None:
        """Start the polling loop."""
        if self._task:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._poll_loop(queue_manager))

    async def stop(self) -> None:
        """Stop the polling loop and close HTTP session."""
        self._stop_event.set()
        if self._task:
            await self._task
            self._task = None
        if self._session:
            await self._session.close()
            self._session = None

    async def _poll_loop(self, queue_manager: QueueManager) -> None:
        """Periodic polling loop."""
        while not self._stop_event.is_set():
            try:
                await self._poll_once(queue_manager)
            except Exception as exc:
                self.logger.exception("Feed polling failed: %s", exc)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval)
            except asyncio.TimeoutError:
                continue

    async def _poll_once(self, queue_manager: QueueManager) -> None:
        feeds = await self.list_feeds()
        if not feeds:
            return
        for feed in feeds:
            if self._stop_event.is_set():
                break
            await self._process_feed(feed, queue_manager)

    async def _process_feed(self, feed: Feed, queue_manager: QueueManager) -> None:
        if not self._session:
            raise RuntimeError("FeedManager session not initialized")
        try:
            async with self._session.get(feed.url) as response:
                if response.status != 200:
                    self.logger.warning("Feed %s returned HTTP %s", feed.url, response.status)
                    await self._update_feed(feed.id, feed.last_entry_id)
                    return
                raw = await response.read()
        except Exception as exc:
            self.logger.error("Failed to fetch feed %s: %s", feed.url, exc)
            return

        parsed = feedparser.parse(raw)
        entries = parsed.entries or []
        if not entries:
            await self._update_feed(feed.id, feed.last_entry_id)
            return

        new_entries = []
        for entry in entries:
            key = self._entry_key(entry)
            if not key:
                continue
            if feed.last_entry_id and key == feed.last_entry_id:
                break
            new_entries.append(entry)

        latest_key = self._entry_key(entries[0])
        limited = new_entries[: self.max_items_per_poll]
        if not limited:
            await self._update_feed(feed.id, latest_key)
            return

        enqueued = 0
        for entry in reversed(limited):
            url = self._entry_link(entry)
            sanitized = validators.sanitize_url(url)
            if not sanitized:
                continue
            task_id, is_new = await queue_manager.add_task(sanitized)
            if is_new:
                enqueued += 1
        self.logger.info("Feed %s added %d new entries", feed.url, enqueued)
        await self._update_feed(feed.id, latest_key)

    async def _update_feed(self, feed_id: int, last_entry_id: Optional[str]) -> None:
        now = time.time()
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                UPDATE feeds
                SET last_polled = ?, last_entry_id = ?
                WHERE id = ?
                """,
                (now, last_entry_id, feed_id),
            )
            await conn.commit()

    def _entry_key(self, entry: dict) -> Optional[str]:
        return entry.get("id") or entry.get("link") or entry.get("title")

    def _entry_link(self, entry: dict) -> str:
        return entry.get("link") or entry.get("id") or ""
