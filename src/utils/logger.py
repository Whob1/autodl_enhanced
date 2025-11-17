"""Unified logging configuration for the Enhanced AutoDL Telegram Bot.

This module defines a helper function to configure Python's logging module
for both console and file handlers. All components should call
``setup_logging()`` once at startup and then retrieve named loggers via
``logging.getLogger(name)``.

The logging configuration is driven by the LOG_LEVEL value provided in
the environment (loaded via config_manager). Logs are written to a
specified file as well as the console.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(log_level: str, log_file_path: str) -> None:
    """Configure the root logger.

    Parameters
    ----------
    log_level: str
        The minimum severity level to emit (e.g. "DEBUG", "INFO").
    log_file_path: str
        Absolute path to the file where logs should be written.

    Notes
    -----
    This function should be called exactly once, at the very beginning of
    the application lifecycle. Subsequent calls will have no effect.
    """
    # Convert log level string into logging constant; default to INFO
    level = getattr(logging, log_level.upper(), logging.INFO)

    # If the root logger already has handlers configured, skip reconfiguration
    if logging.getLogger().handlers:
        return

    # Ensure parent directories exist
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    # Create formatters
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Set up rotating file handler (max 10MB with 5 backups)
    file_handler = RotatingFileHandler(log_file_path, maxBytes=10 * 1024 * 1024, backupCount=5)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    # Configure root logger
    logging.basicConfig(level=level, handlers=[file_handler, console_handler])


def get_logger(name: str) -> logging.Logger:
    """Retrieve a named logger.

    Components should call this instead of creating their own loggers
    directly. The root logger must have been configured beforehand via
    ``setup_logging()``.
    """
    return logging.getLogger(name)