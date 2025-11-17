"""Disk monitoring utilities for the Enhanced AutoDL Telegram Bot.

This module exposes functions to monitor available disk space in the
download directory. When free space drops below a configurable
threshold (10 GB by default), downloads should be paused and the
administrator notified.
"""

from __future__ import annotations

import asyncio
import psutil
from typing import Optional

from .logger import get_logger


def get_free_space_bytes(path: str) -> int:
    """Return the free space in bytes for the filesystem containing ``path``.

    Parameters
    ----------
    path: str
        The path on the filesystem to inspect.

    Returns
    -------
    int
        The number of free bytes available to the current user.
    """
    usage = psutil.disk_usage(path)
    return usage.free


def is_low_disk(path: str, threshold_gb: float = 10.0) -> bool:
    """Determine whether the available disk space is below a threshold.

    Parameters
    ----------
    path: str
        The directory to check.
    threshold_gb: float, optional
        The minimum free space (in gigabytes) required. Defaults to 10 GB.

    Returns
    -------
    bool
        True if free space is less than the threshold, otherwise False.
    """
    free_bytes = get_free_space_bytes(path)
    free_gb = free_bytes / (1024 ** 3)
    return free_gb < threshold_gb


class ConcurrencyGovernor:
    """Dynamically adjust concurrency based on system utilization."""

    def __init__(
        self,
        download_path: str,
        min_workers: int,
        max_workers: int,
        cpu_threshold: float,
        disk_threshold: float,
        interval: float = 5.0,
    ):
        self.download_path = download_path
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.cpu_threshold = cpu_threshold
        self.disk_threshold = disk_threshold
        self.interval = interval
        self._target_workers = min_workers
        self._stop_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self.logger = get_logger(self.__class__.__name__)

    @property
    def target_workers(self) -> int:
        """Return the current recommended number of workers."""
        return self._target_workers

    async def start(self) -> None:
        """Start the governor loop."""
        if self._task:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._monitor_loop())

    async def stop(self) -> None:
        """Stop the governor loop."""
        self._stop_event.set()
        if self._task:
            await self._task
            self._task = None

    def update_limits(
        self,
        min_workers: int,
        max_workers: int,
        cpu_threshold: float,
        disk_threshold: float,
    ) -> None:
        if min_workers < 1 or max_workers < min_workers:
            raise ValueError("min_workers must be >= 1 and <= max_workers")
        if not (0 < cpu_threshold <= 100) or not (0 < disk_threshold <= 100):
            raise ValueError("Thresholds must be between 0 and 100")
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.cpu_threshold = cpu_threshold
        self.disk_threshold = disk_threshold
        self._target_workers = max(min(self._target_workers, max_workers), min_workers)

    async def _monitor_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                cpu = psutil.cpu_percent(interval=None)
                disk = psutil.disk_usage(self.download_path).percent
                self._adjust_target(cpu, disk)
            except Exception as exc:
                self.logger.warning("Concurrency governor sample failed: %s", exc)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                continue

    def _adjust_target(self, cpu: float, disk: float) -> None:
        pressure = max(cpu / max(1.0, self.cpu_threshold), disk / max(1.0, self.disk_threshold))
        if pressure >= 1.0 and self._target_workers > self.min_workers:
            self._target_workers -= 1
        elif pressure < 0.85 and self._target_workers < self.max_workers:
            self._target_workers += 1
        self._target_workers = max(self.min_workers, min(self.max_workers, self._target_workers))
