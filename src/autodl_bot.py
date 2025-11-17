"""Entry point for the Enhanced AutoDL Telegram Bot.

This script ties together configuration loading, logging setup, queue
initialisation, download management and Telegram bot registration.
Execute this file to run the bot.
"""

from __future__ import annotations

import asyncio
import os
import sys

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from .aria2_manager import Aria2Manager
from .config_manager import load_config
from .feed_manager import FeedManager
from .utils.disk_monitor import ConcurrencyGovernor
from .utils.logger import setup_logging, get_logger
from .queue_manager import QueueManager
from .download_manager import DownloadManager
from .handlers import command_handler, message_handler


def main() -> None:
    """Main entrypoint for the bot."""
    # Determine base directory relative to this file
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Load configuration
    try:
        config = load_config(base_dir)
    except Exception as exc:
        print(f"Failed to load configuration: {exc}")
        sys.exit(1)

    # Set up logging
    log_file = os.path.join(base_dir, 'data', 'logs', 'autodl-bot.log')
    setup_logging(config.log_level, log_file)
    logger = get_logger("AutoDLBot")
    logger.info("Configuration loaded successfully")

    async def post_init(app):
        """Initialize async components after the application starts."""
        # Initialise queue manager
        await queue_manager.initialize()
        logger.info("Queue manager initialised")

        # Initialise feed manager
        await feed_manager.initialize()
        logger.info("Feed manager initialised")
        await feed_manager.start(queue_manager)
        logger.info("Feed manager polling started")

        # Initialise download manager
        await download_manager.start()
        logger.info("Download manager started")

    # Build the Telegram application
    application = Application.builder().token(config.token).concurrent_updates(True).post_init(post_init).build()

    # Store config for handlers
    application.bot_data["config"] = config

    # Initialise queue manager (will be initialized in post_init)
    queue_manager = QueueManager(config.db_path)
    application.bot_data["queue_manager"] = queue_manager

    # Prepare feed manager
    feed_manager = FeedManager(
        config.db_path,
        poll_interval=config.feed_poll_interval,
        max_items_per_poll=config.feed_max_items_per_poll,
        timeout=config.feed_fetch_timeout,
    )
    application.bot_data["feed_manager"] = feed_manager

    # Initialise aria2 manager (optional)
    aria2_manager = None
    if config.use_aria2c and config.aria2_rpc_url:
        aria2_manager = Aria2Manager(
            config.aria2_rpc_url,
            config.aria2_rpc_secret,
            config.aria2_rpc_timeout,
            config.download_dir,
        )

    # Concurrency governor
    governor = ConcurrencyGovernor(
        download_path=config.download_dir,
        min_workers=config.min_concurrent,
        max_workers=config.max_concurrent,
        cpu_threshold=config.concurrency_cpu_threshold,
        disk_threshold=config.concurrency_disk_threshold,
    )
    application.bot_data["concurrency_governor"] = governor

    # Initialise download manager (will be started in post_init)
    download_manager = DownloadManager(
        queue_manager,
        config,
        aria2_manager=aria2_manager,
        concurrency_governor=governor,
    )
    application.bot_data["download_manager"] = download_manager

    # Register command handlers
    application.add_handler(CommandHandler("start", command_handler.start))
    application.add_handler(CommandHandler("queue", command_handler.queue))
    application.add_handler(CommandHandler("status", command_handler.status))
    application.add_handler(CommandHandler("pause", command_handler.pause))
    application.add_handler(CommandHandler("resume", command_handler.resume))
    application.add_handler(CommandHandler("clear", command_handler.clear))
    application.add_handler(CommandHandler("retry", command_handler.retry))
    application.add_handler(CommandHandler("addcookies", command_handler.addcookies))
    application.add_handler(CommandHandler("cookies", command_handler.cookies))
    application.add_handler(CommandHandler("add_feed", command_handler.add_feed))
    application.add_handler(CommandHandler("add_magnet", command_handler.add_magnet))
    application.add_handler(CommandHandler("add_file_url", command_handler.add_file_url))
    application.add_handler(CommandHandler("set_concurrency_limits", command_handler.set_concurrency_limits))

    # Register message handlers: documents and text
    # Handle .txt documents
    application.add_handler(
        MessageHandler(filters.Document.FileExtension("txt"), message_handler.handle_document)
    )
    # Handle plain text messages containing URLs
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler.handle_text)
    )

    # Error handling is provided by the logging module; use a simple error handler
    async def error_handler(update, context) -> None:
        logger.exception("Exception while handling update")
        if update and update.effective_message:
            await update.effective_message.reply_text("An unexpected error occurred.")
    application.add_error_handler(error_handler)

    logger.info("Bot configured, starting polling...")

    # Start the bot in polling mode - this handles the event loop internally
    application.run_polling(stop_signals=None)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        pass
