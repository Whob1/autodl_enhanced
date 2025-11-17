"""Download manager for the Enhanced AutoDL Telegram Bot.

This module is responsible for pulling tasks from the queue and
downloading them using yt‑dlp. It supports concurrent downloads,
respects global pause/resume commands, implements retry logic with
exponential backoff and keeps track of progress for real‑time status
reporting.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from typing import Dict, Optional
from urllib.parse import urlparse

import requests
from yt_dlp import YoutubeDL

from .aria2_manager import Aria2Manager
from .queue_manager import QueueManager, DownloadTask
from .utils import disk_monitor
from .utils.disk_monitor import ConcurrencyGovernor
from .utils.logger import get_logger
from .utils.validators import sanitize_url


def is_playlist_url(url: str) -> bool:
    """Check if URL is a playlist."""
    playlist_keywords = [
        'playlist', 'list=', 'playlist?list=', '/playlist/',
        'album', 'channel', 'user'
    ]
    url_lower = url.lower()
    return any(keyword in url_lower for keyword in playlist_keywords)


async def extract_playlist_urls(url: str, max_videos: int = None) -> list[str]:
    """Extract individual video URLs from a playlist URL."""
    url = sanitize_url(url)
    try:
        # Use yt-dlp to extract playlist info without downloading
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,  # Don't download, just extract URLs
            "age_limit": 99,  # Allow adult content
            "ignoreerrors": True,  # Continue on errors
            "playlistend": max_videos or 10,  # Always limit playlists
            "max_downloads": max_videos or 10,  # Additional limit
        }

        from yt_dlp import YoutubeDL
        with YoutubeDL(ydl_opts) as ydl:
            print(f"DEBUG: Extracting playlist info for {url} with max_videos={max_videos}")
            info = ydl.extract_info(url, download=False)

            if not info:
                print("DEBUG: No info returned from yt-dlp")
                return []

            # Handle different playlist structures
            if 'entries' in info:
                # Standard playlist
                entries = info['entries']
                print(f"DEBUG: Found {len(entries)} entries in playlist")
            elif isinstance(info, list):
                # Some extractors return list directly
                entries = info
                print(f"DEBUG: Info is list with {len(entries)} items")
            else:
                print(f"DEBUG: Unexpected info structure: {type(info)}")
                return []

            # Extract URLs from entries
            video_urls = []
            for i, entry in enumerate(entries):
                if isinstance(entry, dict):
                    video_url = entry.get('url') or entry.get('webpage_url')
                    if video_url:
                        video_urls.append(video_url)
                        print(f"DEBUG: Extracted URL {i+1}: {video_url[:60]}...")
                    else:
                        print(f"DEBUG: No URL found in entry {i+1}")
                elif isinstance(entry, str):
                    video_urls.append(entry)
                    print(f"DEBUG: String URL {i+1}: {entry[:60]}...")
                else:
                    print(f"DEBUG: Unexpected entry type {i+1}: {type(entry)}")

            limited_urls = video_urls[:max_videos] if max_videos else video_urls
            print(f"DEBUG: Returning {len(limited_urls)} URLs (limited from {len(video_urls)})")
            return limited_urls

    except Exception as e:
        print(f"Error extracting playlist URLs: {e}")
        return []


class DownloadManager:
    """Coordinate downloads for queued tasks.

    Parameters
    ----------
    queue_manager: QueueManager
        The queue manager responsible for persisting tasks.
    config: Config
        Loaded configuration with download directory, concurrency limit,
        cookie file, etc.
    """

    def __init__(
        self,
        queue_manager: QueueManager,
        config: Config,
        aria2_manager: Optional[Aria2Manager] = None,
        concurrency_governor: Optional[ConcurrencyGovernor] = None,
    ):
        self.queue_manager = queue_manager
        self.config = config
        self.logger = get_logger(self.__class__.__name__)
        self.active_tasks: Dict[int, Dict[str, str]] = {}
        self.paused: bool = False
        self._workers: list[asyncio.Task] = []
        self._stop_event = asyncio.Event()
        self._slot_lock = asyncio.Lock()
        self._active_downloads = 0
        self._target_worker_limit = config.max_concurrent
        self._governor_sync_task: Optional[asyncio.Task] = None
        self.aria2_manager = aria2_manager
        self.governor = concurrency_governor

    async def start(self) -> None:
        """Start worker tasks up to the configured concurrency limit."""
        # Reset stop flag
        self._stop_event.clear()
        if self.governor:
            self._target_worker_limit = self.governor.target_workers
        else:
            self._target_worker_limit = self.config.max_concurrent
        self.logger.info(
            "Starting download manager (worker limit: %d)", self._target_worker_limit
        )
        for _ in range(self.config.max_concurrent):
            task = asyncio.create_task(self._worker_loop())
            self._workers.append(task)
        if self.governor:
            await self.governor.start()
            self._governor_sync_task = asyncio.create_task(self._sync_with_governor())

    async def stop(self) -> None:
        """Signal all workers to stop and wait for them to finish."""
        self._stop_event.set()
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        if self._governor_sync_task:
            self._governor_sync_task.cancel()
            await asyncio.gather(self._governor_sync_task, return_exceptions=True)
            self._governor_sync_task = None
        if self.governor:
            await self.governor.stop()

    async def _worker_loop(self) -> None:
        """Continuously fetch and process tasks until stopped."""
        while not self._stop_event.is_set():
            if self.paused:
                await asyncio.sleep(2)
                continue
            if disk_monitor.is_low_disk(self.config.download_dir, self.config.min_disk_space_gb):
                self.logger.warning("Low disk space detected. Pausing downloads until space is freed.")
                self.paused = True
                await asyncio.sleep(2)
                continue
            slot_acquired = await self._wait_for_slot()
            if not slot_acquired:
                break
            task = await self.queue_manager.fetch_next_task()
            if task is None:
                await self._release_slot()
                await asyncio.sleep(2)
                continue
            self.logger.info(f"Worker starting task {task.id}: {task.url}")
            try:
                await self._process_task(task)
            finally:
                await self._release_slot()

    async def _wait_for_slot(self) -> bool:
        """Wait until a download slot is available based on governor/limits."""
        while not self._stop_event.is_set():
            async with self._slot_lock:
                if self._active_downloads < max(1, self._target_worker_limit):
                    self._active_downloads += 1
                    return True
            await asyncio.sleep(0.5)
        return False

    async def _release_slot(self) -> None:
        """Release a previously acquired download slot."""
        async with self._slot_lock:
            self._active_downloads = max(0, self._active_downloads - 1)

    async def _sync_with_governor(self) -> None:
        """Sync target worker limit with the governor's recommendation."""
        if not self.governor:
            return
        while not self._stop_event.is_set():
            target = self.governor.target_workers
            async with self._slot_lock:
                self._target_worker_limit = max(1, target)
            await asyncio.sleep(1)

    async def _process_task(self, task: DownloadTask) -> None:
        """Handle downloading a single task with retry/backoff logic."""
        task_id = task.id
        url = sanitize_url(task.url)

        self.active_tasks[task_id] = {
            "status": "starting",
            "progress": "0%",
            "speed": "0 B/s",
            "eta": "?",
            "url": url
        }

        self.logger.info(f"Starting download: task_id={task_id}, url={url}")
        try:
            file_path = await self._download(task)
            if not file_path or file_path == "":
                self.logger.warning(f"No file path returned for task {task_id}, checking filesystem...")
                # Try to find the downloaded file
                try:
                    import glob
                    files = glob.glob(os.path.join(self.config.download_dir, "*"))
                    if files:
                        # Filter out aria2 control files and fragments
                        files = [f for f in files if not any(ext in f for ext in ['.aria2', '-Frag', '__temp'])]
                        # Get files modified in the last 5 minutes
                        recent_files = [f for f in files if (time.time() - os.path.getmtime(f)) < 300]
                        if recent_files:
                            file_path = max(recent_files, key=os.path.getmtime)
                            self.logger.info(f"Found recent file for task {task_id}: {file_path}")
                        else:
                            raise RuntimeError("No recent files found (after filtering fragments)")
                    else:
                        raise RuntimeError("No files in download directory")
                except Exception as e:
                    self.logger.error(f"Could not find downloaded file for task {task_id}: {e}")
                    raise RuntimeError(f"Download completed but file not found: {e}")

            # Mark as completed
            self.active_tasks[task_id] = {
                "status": "completed",
                "progress": "100%",
                "speed": "Done",
                "eta": "0",
                "url": url
            }

            await self.queue_manager.mark_completed(task_id, file_path)
            self.logger.info(f"Download completed: task_id={task_id}, file={file_path}")
        except Exception as exc:
            self.logger.error(f"Download failed for task_id={task_id}: {exc}")

            # Mark as failed
            self.active_tasks[task_id] = {
                "status": "failed",
                "progress": "0%",
                "speed": "Failed",
                "eta": "N/A",
                "url": url,
                "error": str(exc)
            }

            # Determine whether to retry
            if task.attempts + 1 >= self.queue_manager.max_retries:
                await self.queue_manager.mark_failed(task_id, str(exc))
                self.logger.warning(f"Task {task_id} marked as permanently failed")
            else:
                # Reschedule with exponential backoff
                await self.queue_manager.reschedule_task(task_id, task.attempts + 1)
                self.logger.info(
                    f"Rescheduled task {task_id} (attempt {task.attempts + 1}/{self.queue_manager.max_retries})"
                )
        finally:
            # Keep in active tasks for a short time so status can be seen
            await asyncio.sleep(2)
            self.active_tasks.pop(task_id, None)

    async def _download(self, task: DownloadTask) -> Optional[str]:
        """Dispatch downloads based on URL schemes or explicit hints."""
        url = sanitize_url(task.url)
        if not url:
            raise RuntimeError("URL could not be sanitized")
        parsed = urlparse(url)
        self.logger.info(f"_download called for task {task.id}: {url} (method={task.download_method})")

        if parsed.scheme == "magnet":
            return await self._download_magnet(task, url)
        if task.download_method == "file":
            return await self._download_file_url(url)
        return await self._download_with_ytdlp(task, url)

    async def _download_with_ytdlp(self, task: DownloadTask, url: str) -> Optional[str]:
        """Download a URL with yt-dlp in an executor."""
        self.logger.debug("Starting yt-dlp download for task %d", task.id)
        result = {"filepath": None}

        def progress_hook(info: dict) -> None:
            status = info.get("status")
            self.logger.debug("Progress hook for task %d: %s", task.id, status)
            if status == "downloading":
                percent_str = info.get("_percent_str", "0%")
                speed_str = info.get("_speed_str", "0 B/s")
                eta_str = info.get("_eta_str", "?")
                self.active_tasks[task.id] = {
                    "status": "downloading",
                    "progress": percent_str,
                    "speed": speed_str,
                    "eta": eta_str,
                    "url": url
                }
            elif status == "finished":
                filename = info.get("filename") or info.get("_filename") or ""
                if filename:
                    result["filepath"] = filename

        def run_download() -> None:
            ydl_opts = {
                "outtmpl": os.path.join(self.config.download_dir, "%(title)s.%(ext)s"),
                "progress_hooks": [progress_hook],
                "format": "bestvideo+bestaudio/best",
                "ignoreerrors": True,
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "socket_timeout": self.config.socket_timeout,
                "merge_output_format": self.config.preferred_format,
                "writethumbnail": True,
                "writedescription": True,
                "writesubtitles": True,
                "cachedir": False,
                "concurrent_fragment_downloads": 16,
                "external_downloader_args": [
                    "--continue=true",
                    "--max-tries=5",
                ],
            }
            if self.config.use_aria2c and self.config.aria2_rpc_url:
                ydl_opts["external_downloader"] = "aria2c"
                ydl_opts["external_downloader_args"].extend([
                    "--file-allocation=none",
                    "--allow-overwrite=true",
                ])
            if self.config.cookies_file:
                ydl_opts["cookiefile"] = self.config.cookies_file

            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, run_download)
        return result.get("filepath")

    async def _download_file_url(self, url: str) -> Optional[str]:
        """Download a plain HTTP(S) file via requests streaming."""
        self.logger.debug("Starting file download for %s", url)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._download_file_blocking, url)

    def _download_file_blocking(self, url: str) -> str:
        try:
            with requests.get(url, stream=True, timeout=self.config.socket_timeout) as response:
                response.raise_for_status()
                filename = self._derive_filename(url, response.headers)
                os.makedirs(self.config.download_dir, exist_ok=True)
                dest_path = os.path.join(self.config.download_dir, filename)
                with open(dest_path, "wb") as dest:
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        if chunk:
                            dest.write(chunk)
                return dest_path
        except requests.RequestException as exc:
            self.logger.error("HTTP file download failed for %s: %s", url, exc)
            raise RuntimeError(f"HTTP download failed: {exc}") from exc

    async def _download_magnet(self, task: DownloadTask, url: str) -> Optional[str]:
        if not self.aria2_manager:
            raise RuntimeError("aria2 RPC is not configured for magnet downloads")
        loop = asyncio.get_running_loop()
        gid = await loop.run_in_executor(None, self.aria2_manager.add_magnet, url)
        self.active_tasks[task.id].update(
            {"status": "queued", "progress": "0%", "speed": "aria2", "eta": "?"}
        )
        identifier = gid or "submitted"
        return f"aria2:{identifier}"

    def _derive_filename(self, url: str, headers: dict) -> str:
        disposition = headers.get("content-disposition", "")
        if disposition:
            filename = self._extract_filename_from_disposition(disposition)
            if filename:
                return filename
        parsed = urlparse(url)
        basename = os.path.basename(parsed.path)
        if basename:
            return basename
        return f"file_{int(time.time())}"

    def _extract_filename_from_disposition(self, disposition: str) -> Optional[str]:
        match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', disposition)
        if match:
            return match.group(1)
        return None

    def get_active_status(self) -> Dict[int, Dict[str, str]]:
        """Return a snapshot of current active download statuses."""
        return dict(self.active_tasks)
