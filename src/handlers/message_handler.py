"""Telegram message handlers for the Enhanced AutoDL Telegram Bot.

This module defines handlers for plain text and document messages. It
extracts URLs from user input and enqueues them into the persistent
download queue. When a `.txt` file is uploaded, each line is treated
as a potential URL.
"""

from __future__ import annotations

from typing import List

from telegram import Update, Document
from telegram.ext import ContextTypes

from ..utils import validators
from ..download_manager import is_playlist_url, extract_playlist_urls
from ..utils.cookie_manager import CookieManager
from pathlib import Path
import tempfile
import logging

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_MB = 10
MAX_LINE_COUNT = 10000


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages containing one or more URLs."""
    message = update.message
    if message is None or not message.text:
        return
    queue_manager = context.bot_data.get("queue_manager")
    if queue_manager is None:
        await update.message.reply_text("Queue manager unavailable.")
        return
    urls = validators.extract_urls(message.text)
    if not urls:
        await update.message.reply_text("Please send a valid URL or a .txt file containing URLs.")
        return
    urls = [validators.sanitize_url(url) for url in urls]
    added_ids: List[int] = []
    duplicate_ids: List[int] = []
    total_videos = 0
    total_duplicates = 0

    for url in urls:
        if not validators.is_valid_url(url):
            continue

        # Check if this is a playlist URL
        if is_playlist_url(url):
            config = context.bot_data.get("config", None)
            max_videos = config.max_playlist_videos if config else 10
            await update.message.reply_text(f"🎵 Detected playlist URL, extracting videos from: {url[:50]}...")
            try:
                video_urls = await extract_playlist_urls(url, max_videos=max_videos)
                if video_urls:
                    await update.message.reply_text(f"📋 Found {len(video_urls)} videos in playlist")
                    for video_url in video_urls:
                        if validators.is_valid_url(video_url):
                            task_id, is_new = await queue_manager.add_task(video_url)
                            if is_new:
                                added_ids.append(task_id)
                                total_videos += 1
                            else:
                                duplicate_ids.append(task_id)
                                total_duplicates += 1
                else:
                    await update.message.reply_text(f"❌ Could not extract videos from playlist: {url[:50]}...")
            except Exception as e:
                await update.message.reply_text(f"❌ Error processing playlist {url[:50]}...: {str(e)}")
        else:
            # Regular video URL
            task_id, is_new = await queue_manager.add_task(url)
            if is_new:
                added_ids.append(task_id)
                total_videos += 1
            else:
                duplicate_ids.append(task_id)
                total_duplicates += 1

    # Build response message
    response_parts = []
    if added_ids:
        if total_videos > len(urls):
            response_parts.append(f"📥 Added {total_videos} new video(s) (expanded from {len(urls)} URL(s))")
        else:
            response_parts.append(f"📥 Added {len(added_ids)} new task(s)")

    if duplicate_ids:
        response_parts.append(f"♻️ Skipped {total_duplicates} duplicate(s)")

    if response_parts:
        await update.message.reply_text(" • ".join(response_parts))
    else:
        await update.message.reply_text("No valid URLs found in your message.")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle uploaded documents (.txt files) containing a list of URLs or cookies."""
    message = update.message
    if message is None or message.document is None:
        return
    document: Document = message.document
    if not document.file_name.lower().endswith('.txt'):
        await update.message.reply_text("Unsupported file type. Please send a .txt file.")
        return

    if document.file_size and document.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        await update.message.reply_text(f"❌ File too large. Maximum size is {MAX_FILE_SIZE_MB}MB.")
        logger.warning(f"User attempted to upload file larger than {MAX_FILE_SIZE_MB}MB: {document.file_size} bytes")
        return

    # Check if user is awaiting a cookie file
    is_cookie_upload = context.user_data.get("awaiting_cookie_file", False)
    context.user_data["awaiting_cookie_file"] = False  # Reset state

    queue_manager = context.bot_data.get("queue_manager")
    config = context.bot_data.get("config")

    if is_cookie_upload:
        # Process as cookie file
        if config is None or not config.cookies_file:
            await update.message.reply_text("❌ Cookie file path not configured.")
            return

        try:
            file = await document.get_file()
            data: bytearray = await file.download_as_bytearray()

            # Save to temporary file first
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name

            # Append cookies from temp file to main cookies file
            success, message_text = CookieManager.append_cookies(
                Path(config.cookies_file),
                Path(tmp_path)
            )

            # Clean up temp file
            import os
            try:
                os.unlink(tmp_path)
            except:
                pass

            if success:
                await update.message.reply_text(f"✅ {message_text}")
                logger.info(f"Cookies appended from user file: {message_text}")
            else:
                await update.message.reply_text(f"❌ Failed to append cookies: {message_text}")
                logger.error(f"Failed to append cookies: {message_text}")
        except Exception as e:
            await update.message.reply_text(f"❌ Error processing cookie file: {str(e)}")
            logger.error(f"Error processing cookie file: {e}")
        return

    # Not a cookie upload, process as URL list
    if queue_manager is None:
        await update.message.reply_text("Queue manager unavailable.")
        return
    # Download the file contents into memory
    try:
        file = await document.get_file()
        data: bytearray = await file.download_as_bytearray()
        content = data.decode('utf-8', errors='ignore')
    except Exception:
        await update.message.reply_text("Failed to download the file. Please try again.")
        return
    lines = [line.strip() for line in content.splitlines()]
    
    if len(lines) > MAX_LINE_COUNT:
        await update.message.reply_text(f"❌ File has too many lines. Maximum is {MAX_LINE_COUNT} lines.")
        logger.warning(f"User attempted to upload file with {len(lines)} lines (max: {MAX_LINE_COUNT})")
        return
    
    lines = [validators.sanitize_url(line) for line in lines]
    added = 0
    duplicates = 0
    total_videos = 0

    for line in lines:
        if not validators.is_valid_url(line):
            continue

        # Check if this is a playlist URL
        if is_playlist_url(line):
            config = context.bot_data.get("config", None)
            max_videos = config.max_playlist_videos if config else 10
            await update.message.reply_text(f"🎵 Processing playlist from file: {line[:50]}...")
            try:
                video_urls = await extract_playlist_urls(line, max_videos=max_videos)
                if video_urls:
                    await update.message.reply_text(f"📋 Found {len(video_urls)} videos in playlist")
                    for video_url in video_urls:
                        if validators.is_valid_url(video_url):
                            _, is_new = await queue_manager.add_task(video_url)
                            if is_new:
                                added += 1
                                total_videos += 1
                            else:
                                duplicates += 1
                else:
                    await update.message.reply_text(f"❌ Could not extract videos from playlist: {line[:50]}...")
            except Exception as e:
                await update.message.reply_text(f"❌ Error processing playlist {line[:50]}...: {str(e)}")
        else:
            # Regular video URL
            _, is_new = await queue_manager.add_task(line)
            if is_new:
                added += 1
                total_videos += 1
            else:
                duplicates += 1

    # Build response message
    response_parts = []
    if added:
        if total_videos > len([l for l in lines if l.strip()]):
            response_parts.append(f"📥 Added {total_videos} new video(s) (expanded from file)")
        else:
            response_parts.append(f"📥 Added {added} new task(s) from file")

    if duplicates:
        response_parts.append(f"♻️ Skipped {duplicates} duplicate(s)")

    if response_parts:
        await update.message.reply_text(" • ".join(response_parts))
    else:
        await update.message.reply_text("No valid URLs found in the uploaded file.")