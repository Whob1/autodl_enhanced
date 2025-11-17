"""Telegram command handlers for the Enhanced AutoDL Telegram Bot.

This module defines asynchronous handler functions for bot commands such
as /start, /queue, /status, /pause, /resume and /clear. Handlers rely on
objects stored in ``application.bot_data`` (queue_manager and
download_manager).
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from telegram import Update
from telegram.ext import ContextTypes

from ..utils import performance, validators
from ..utils.cookie_manager import CookieManager


def _is_authorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the user is authorized to execute privileged commands."""
    if not update.effective_user:
        return False
    config = context.bot_data.get("config")
    if not config:
        return False
    user_id = str(update.effective_user.id)
    if not config.admin_ids or not config.admin_ids[0]:
        return True
    return user_id in config.admin_ids


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the user invokes /start."""
    message = (
        "👋 *Welcome to the Enhanced AutoDL Bot!*\n\n"
        "Send me a YouTube or other supported media link and I'll add it to the queue.\n"
        "You can also send a `.txt` file containing one URL per line.\n\n"
        "Commands:\n"
        "/queue – Show pending tasks\n"
        "/status – Show active downloads and system resource usage\n"
        "/pause – Pause all downloads\n"
        "/resume – Resume downloads if paused\n"
        "/retry – Retry all failed downloads\n"
        "/clear – Clear permanently failed tasks\n"
        "/addcookies – Add cookies from a file (appends to existing cookies)\n"
        "/cookies – Show cookie statistics"
        "\n/add_feed <url> – Register an RSS/Atom feed for auto-enqueueing\n"
        "/add_magnet <link> – Queue a magnet link via aria2\n"
        "/add_file_url <url> – Download a plain HTTP(S) file\n"
        "/set_concurrency_limits <min> <max> <cpu%> <disk%> – Tune worker limits"
    )
    await update.message.reply_markdown(message)


async def queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List pending tasks in the queue."""
    queue_manager = context.bot_data.get("queue_manager")
    if queue_manager is None:
        await update.message.reply_text("Queue manager not available.")
        return
    pending_tasks = await queue_manager.get_pending_tasks()
    if not pending_tasks:
        await update.message.reply_text("✅ The queue is empty.")
        return
    lines = [f"• Task {t.id}: {t.url} (attempts: {t.attempts})" for t in pending_tasks[:10]]
    more = "" if len(pending_tasks) <= 10 else f"\n…and {len(pending_tasks) - 10} more tasks"
    await update.message.reply_text(
        "📋 Pending tasks (showing up to 10):\n" + "\n".join(lines) + more
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provide information about active downloads and system resources."""
    download_manager = context.bot_data.get("download_manager")
    queue_manager = context.bot_data.get("queue_manager")
    if download_manager is None or queue_manager is None:
        await update.message.reply_text("Status information unavailable.")
        return
    active = download_manager.get_active_status()
    processing_tasks = await queue_manager.get_processing_tasks()

    # Get recent failed tasks (from last 10 minutes) - simplified approach
    recent_failed = []
    try:
        # Query failed tasks directly from database
        import sqlite3
        import time
        db_path = queue_manager.db_path
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        current_time = time.time()

        cursor.execute("""
            SELECT id, url, status, attempts, added_at, updated_at, next_attempt_at, file_path, error_message
            FROM tasks
            WHERE status='failed' AND updated_at > ?
            ORDER BY updated_at DESC
            LIMIT 5
        """, (current_time - 600,))  # Last 10 minutes

        for row in cursor.fetchall():
            task_id, url, status, attempts, added_at, updated_at, next_attempt_at, file_path, error_message = row
            # Create a simple object to hold the task info
            class SimpleTask:
                def __init__(self, id, url, error_message):
                    self.id = id
                    self.url = url
                    self.error_message = error_message
            recent_failed.append(SimpleTask(task_id, url, error_message))

        conn.close()
    except:
        pass  # Ignore if we can't get recent failed tasks

    lines = []

    if active:
        lines.append("📥 *Active downloads:*\n")
        for task_id, info in active.items():
            status = info.get('status', 'unknown')
            progress = info.get('progress', '0%')
            speed = info.get('speed', '?')
            eta = info.get('eta', '?')

            # Format URL to be shorter for display
            url = info.get('url', '')
            if len(url) > 50:
                url = url[:47] + "..."

            if status == 'failed':
                error_msg = info.get('error', '')
                if error_msg:
                    error_msg = f" - {error_msg[:30]}..."
                line = f"• Task {task_id}: ❌ FAILED{error_msg} - {url}"
            elif status == 'completed':
                line = f"• Task {task_id}: ✅ COMPLETED - {url}"
            elif status == 'starting':
                line = f"• Task {task_id}: 🔄 STARTING - {url}"
            elif status == 'postprocessing':
                line = f"• Task {task_id}: 🔄 POST-PROCESSING - {url}"
            else:
                line = f"• Task {task_id}: {progress} at {speed} (ETA: {eta})"

            lines.append(line)
    else:
        lines.append("📥 No active downloads.")

    # Show recent failed tasks
    if recent_failed:
        lines.append(f"\n❌ *Recent failures ({len(recent_failed)}):*")
        for task in recent_failed[:5]:  # Show up to 5 recent failures
            url_short = task.url[:40] + "..." if len(task.url) > 40 else task.url
            error_short = task.error_message[:30] + "..." if task.error_message and len(task.error_message) > 30 else (task.error_message or "Unknown error")
            lines.append(f"• Task {task.id}: {url_short} - {error_short}")

    # Show processing tasks count
    processing_count = len(processing_tasks) if processing_tasks else 0
    if processing_count > 0:
        lines.append(f"\n⚙️ {processing_count} tasks being processed")
    # System performance
    cpu = performance.get_cpu_usage()
    mem = performance.get_memory_usage()
    disk = performance.get_disk_usage(download_manager.config.download_dir)
    sys_info = (
        f"\n*System resources*:\n"
        f"• CPU usage: {cpu:.1f}%\n"
        f"• Memory usage: {mem:.1f}%\n"
        f"• Disk usage: {disk:.1f}%"
    )
    await update.message.reply_markdown("\n".join(lines) + sys_info)


async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pause all downloads and stop new tasks from starting."""
    if not _is_authorized(update, context):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    download_manager = context.bot_data.get("download_manager")
    if download_manager is None:
        await update.message.reply_text("Download manager unavailable.")
        return
    download_manager.paused = True
    await update.message.reply_text("⏸️ Downloads have been paused.")


async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resume downloads if they are paused."""
    if not _is_authorized(update, context):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    download_manager = context.bot_data.get("download_manager")
    if download_manager is None:
        await update.message.reply_text("Download manager unavailable.")
        return
    if not download_manager.paused:
        await update.message.reply_text("▶️ Downloads are already running.")
    else:
        download_manager.paused = False
        await update.message.reply_text("▶️ Downloads resumed.")


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear permanently failed tasks from the queue."""
    if not _is_authorized(update, context):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    queue_manager = context.bot_data.get("queue_manager")
    if queue_manager is None:
        await update.message.reply_text("Queue manager unavailable.")
        return
    await queue_manager.clear_failed_tasks()
    await update.message.reply_text("🗑️ Cleared all failed tasks from the queue.")


async def retry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Retry all failed tasks."""
    queue_manager = context.bot_data.get("queue_manager")
    if queue_manager is None:
        await update.message.reply_text("Queue manager unavailable.")
        return

    retried_count = await queue_manager.retry_failed_tasks()

    if retried_count == 0:
        await update.message.reply_text("ℹ️ No failed tasks to retry.")
    else:
        await update.message.reply_text(f"🔄 Retrying {retried_count} failed task(s).")


async def addcookies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Prompt user to send a cookie file.
    Sets state so message handler knows to process next file as cookies.
    """
    context.user_data["awaiting_cookie_file"] = True
    message = (
        "🍪 *Add Cookies*\n\n"
        "Please send a `.txt` file containing cookies in Netscape format.\n"
        "These cookies will be appended to the existing cookies file (not replaced).\n\n"
        "Format: Each line should follow the Netscape cookie format:\n"
        "`domain flag path secure expiration name value`"
    )
    await update.message.reply_markdown(message)


async def cookies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show statistics about current cookies."""
    config = context.bot_data.get("config")
    if config is None or not config.cookies_file:
        await update.message.reply_text("Cookie file not configured.")
        return

    from pathlib import Path
    cookies_path = Path(config.cookies_file)

    summary = CookieManager.get_cookies_summary(cookies_path)

    if summary["total"] == 0:
        await update.message.reply_text("📊 No cookies found in the cookies file.")
        return

    lines = [f"📊 *Cookie Statistics*\n"]
    lines.append(f"Total cookies: {summary['total']}\n")
    lines.append("Cookies by domain:")

    for domain, count in summary["domains"]:
        lines.append(f"  • {domain}: {count}")

    await update.message.reply_markdown("\n".join(lines))


async def add_feed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Register a new RSS/Atom feed URL for automatic enqueuing."""
    if not _is_authorized(update, context):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    feed_manager = context.bot_data.get("feed_manager")
    if feed_manager is None:
        await update.message.reply_text("Feed manager unavailable.")
        return
    query = " ".join(context.args or [])
    if not query:
        await update.message.reply_text("Usage: /add_feed <feed_url>")
        return
    url = validators.sanitize_url(query)
    if not validators.is_valid_url(url):
        await update.message.reply_text("❌ Please provide a valid HTTP or HTTPS feed URL.")
        return
    try:
        feed_id, created = await feed_manager.add_feed(url)
        if created:
            await update.message.reply_text(f"✅ Feed registered (id {feed_id}). New items will be queued automatically.")
        else:
            await update.message.reply_text(f"ℹ️ Feed already exists (id {feed_id}).")
    except ValueError as exc:
        await update.message.reply_text(f"❌ {str(exc)}")
    except Exception as exc:
        await update.message.reply_text(f"❌ Failed to register feed: {str(exc)}")


async def add_magnet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a magnet link directly to the download queue."""
    if not _is_authorized(update, context):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    queue_manager = context.bot_data.get("queue_manager")
    if queue_manager is None:
        await update.message.reply_text("Queue manager unavailable.")
        return
    query = " ".join(context.args or [])
    if not query:
        await update.message.reply_text("Usage: /add_magnet <magnet_link>")
        return
    url = validators.sanitize_url(query)
    if not validators.is_valid_url(url):
        await update.message.reply_text("❌ Please provide a valid magnet link.")
        return
    task_id, is_new = await queue_manager.add_task(url)
    if is_new:
        await update.message.reply_text(f"📥 Magnet queued (task {task_id}).")
    else:
        await update.message.reply_text(f"♻️ Magnet already queued (existing task {task_id}).")


async def add_file_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Queue a plain HTTP(S) file URL to download via streaming requests."""
    if not _is_authorized(update, context):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    queue_manager = context.bot_data.get("queue_manager")
    if queue_manager is None:
        await update.message.reply_text("Queue manager unavailable.")
        return
    query = " ".join(context.args or [])
    if not query:
        await update.message.reply_text("Usage: /add_file_url <file_url>")
        return
    url = validators.sanitize_url(query)
    if not validators.is_valid_url(url):
        await update.message.reply_text("❌ Please provide a valid HTTP or HTTPS URL.")
        return
    task_id, is_new = await queue_manager.add_task(url, download_method="file")
    if is_new:
        await update.message.reply_text(f"📥 File download queued (task {task_id}).")
    else:
        await update.message.reply_text(f"♻️ File URL already queued (existing task {task_id}).")


async def set_concurrency_limits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Adjust runtime concurrency limits and thresholds."""
    if not _is_authorized(update, context):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    if len(context.args) != 4:
        await update.message.reply_text("Usage: /set_concurrency_limits <min> <max> <cpu%> <disk%>")
        return
    try:
        min_workers = int(context.args[0])
        max_workers = int(context.args[1])
        cpu_threshold = float(context.args[2])
        disk_threshold = float(context.args[3])
    except ValueError:
        await update.message.reply_text("❌ All values must be numeric.")
        return
    governor = context.bot_data.get("concurrency_governor")
    download_manager = context.bot_data.get("download_manager")
    config = context.bot_data.get("config")
    if governor is None or download_manager is None:
        await update.message.reply_text("Concurrency governor is not configured.")
        return
    try:
        governor.update_limits(min_workers, max_workers, cpu_threshold, disk_threshold)
    except ValueError as exc:
        await update.message.reply_text(f"❌ {str(exc)}")
        return
    if config:
        config.min_concurrent = min_workers
        config.max_concurrent = max_workers
        config.concurrency_cpu_threshold = cpu_threshold
        config.concurrency_disk_threshold = disk_threshold
    async with download_manager._slot_lock:
        download_manager._target_worker_limit = max(1, governor.target_workers)
    await update.message.reply_text(
        f"✅ Concurrency range set to {min_workers}-{max_workers} with CPU {cpu_threshold}% and disk {disk_threshold}% thresholds."
    )
