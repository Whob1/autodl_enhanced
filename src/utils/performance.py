"""System performance monitoring utilities.

This module exposes helpers to inspect CPU usage, memory usage and disk
usage. These functions are used to provide more detailed status
information through the Telegram bot.
"""

from __future__ import annotations

import psutil


def get_cpu_usage() -> float:
    """Return the current system-wide CPU utilization as a percentage.

    The value returned is averaged over a short period of time.
    """
    return psutil.cpu_percent(interval=0.5)


def get_memory_usage() -> float:
    """Return the current memory usage as a percentage of total available memory."""
    return psutil.virtual_memory().percent


def get_disk_usage(path: str) -> float:
    """Return the disk utilization for the filesystem containing ``path``.

    Parameters
    ----------
    path: str
        The directory whose filesystem's usage is to be inspected.

    Returns
    -------
    float
        Percentage of the filesystem used (0 – 100).
    """
    return psutil.disk_usage(path).percent