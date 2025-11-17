import os
from dotenv import load_dotenv
from typing import List

env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=os.path.abspath(env_path), override=True)


class ConfigurationError(Exception):
    """Raised when configuration is missing or invalid."""
    pass


class Config:
    """Configuration object for the AutoDL bot."""

    def __init__(self, base_dir: str):
        """Initialize configuration from environment variables."""
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token or not token.strip():
            raise ConfigurationError("TELEGRAM_BOT_TOKEN must be set in .env and cannot be empty")
        self.token = token.strip()

        self.admin_ids: List[str] = []
        admin_ids_str = os.getenv("TELEGRAM_ADMIN_IDS", "")
        if admin_ids_str and admin_ids_str.strip():
            self.admin_ids = [aid.strip() for aid in admin_ids_str.split(",") if aid.strip()]

        download_dir = os.getenv("DOWNLOAD_DIR", "/mnt/sda/videos")
        if not download_dir or not download_dir.strip():
            raise ConfigurationError("DOWNLOAD_DIR must be set and cannot be empty")
        self.download_dir = download_dir.strip()

        log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigurationError(f"LOG_LEVEL must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL (got: {log_level})")
        self.log_level = log_level

        try:
            self.max_concurrent = int(os.getenv("MAX_CONCURRENT", "8"))
            if self.max_concurrent < 1 or self.max_concurrent > 100:
                raise ValueError("MAX_CONCURRENT must be between 1 and 100")
        except ValueError as e:
            raise ConfigurationError(f"Invalid MAX_CONCURRENT value: {e}")

        try:
            self.min_concurrent = int(os.getenv("MIN_CONCURRENT", "2"))
            if self.min_concurrent < 1 or self.min_concurrent > self.max_concurrent:
                raise ValueError("MIN_CONCURRENT must be between 1 and MAX_CONCURRENT")
        except ValueError as e:
            raise ConfigurationError(f"Invalid MIN_CONCURRENT value: {e}")

        try:
            self.concurrency_cpu_threshold = float(os.getenv("CONCURRENCY_CPU_THRESHOLD", "85.0"))
            if self.concurrency_cpu_threshold <= 0 or self.concurrency_cpu_threshold > 100:
                raise ValueError("CONCURRENCY_CPU_THRESHOLD must be between 0 and 100")
        except ValueError as e:
            raise ConfigurationError(f"Invalid CONCURRENCY_CPU_THRESHOLD value: {e}")

        try:
            self.concurrency_disk_threshold = float(os.getenv("CONCURRENCY_DISK_THRESHOLD", "90.0"))
            if self.concurrency_disk_threshold <= 0 or self.concurrency_disk_threshold > 100:
                raise ValueError("CONCURRENCY_DISK_THRESHOLD must be between 0 and 100")
        except ValueError as e:
            raise ConfigurationError(f"Invalid CONCURRENCY_DISK_THRESHOLD value: {e}")

        cookies_file_env = os.getenv("COOKIES_FILE")
        self.cookies_file = cookies_file_env.strip() if cookies_file_env and cookies_file_env.strip() else os.path.join(base_dir, "data", "cookies", "cookies.txt")

        self.use_aria2c = os.getenv("USE_ARIA2C", "true").lower() == "true"
        self.aria2_rpc_url = os.getenv("ARIA2_RPC_URL", "").strip()
        self.aria2_rpc_secret = os.getenv("ARIA2_RPC_SECRET", "").strip()
        try:
            self.aria2_rpc_timeout = float(os.getenv("ARIA2_RPC_TIMEOUT", "30"))
            if self.aria2_rpc_timeout <= 0:
                raise ValueError("ARIA2_RPC_TIMEOUT must be positive")
        except ValueError as e:
            raise ConfigurationError(f"Invalid ARIA2_RPC_TIMEOUT value: {e}")

        try:
            self.min_disk_space_gb = float(os.getenv("MIN_DISK_SPACE_GB", "50.0"))
            if self.min_disk_space_gb < 0:
                raise ValueError("MIN_DISK_SPACE_GB cannot be negative")
        except ValueError as e:
            raise ConfigurationError(f"Invalid MIN_DISK_SPACE_GB value: {e}")

        try:
            self.socket_timeout = int(os.getenv("SOCKET_TIMEOUT", "30"))
            if self.socket_timeout < 1:
                raise ValueError("SOCKET_TIMEOUT must be at least 1")
        except ValueError as e:
            raise ConfigurationError(f"Invalid SOCKET_TIMEOUT value: {e}")

        try:
            self.max_retries = int(os.getenv("MAX_RETRIES", "5"))
            if self.max_retries < 0:
                raise ValueError("MAX_RETRIES cannot be negative")
        except ValueError as e:
            raise ConfigurationError(f"Invalid MAX_RETRIES value: {e}")

        try:
            self.retry_sleep = int(os.getenv("RETRY_SLEEP", "1"))
            if self.retry_sleep < 0:
                raise ValueError("RETRY_SLEEP cannot be negative")
        except ValueError as e:
            raise ConfigurationError(f"Invalid RETRY_SLEEP value: {e}")

        max_video_quality = os.getenv("MAX_VIDEO_QUALITY", "1080p").strip()
        if not max_video_quality.endswith('p') or not max_video_quality[:-1].isdigit():
            raise ConfigurationError(f"MAX_VIDEO_QUALITY must be in format XXXp (e.g., 1080p), got: {max_video_quality}")
        self.max_video_quality = max_video_quality

        preferred_format = os.getenv("PREFERRED_FORMAT", "mp4").strip().lower()
        if preferred_format not in {"mp4", "webm", "mkv", "flv", "avi"}:
            raise ConfigurationError(f"PREFERRED_FORMAT must be one of mp4, webm, mkv, flv, avi (got: {preferred_format})")
        self.preferred_format = preferred_format

        self.skip_hls = os.getenv("SKIP_HLS", "true").lower() == "true"
        self.skip_dash = os.getenv("SKIP_DASH", "true").lower() == "true"

        try:
            self.max_playlist_videos = int(os.getenv("MAX_PLAYLIST_VIDEOS", "10"))
            if self.max_playlist_videos < 1:
                raise ValueError("MAX_PLAYLIST_VIDEOS must be at least 1")
        except ValueError as e:
            raise ConfigurationError(f"Invalid MAX_PLAYLIST_VIDEOS value: {e}")

        try:
            self.feed_poll_interval = int(os.getenv("FEED_POLL_INTERVAL", "300"))
            if self.feed_poll_interval < 60:
                raise ValueError("FEED_POLL_INTERVAL must be at least 60 seconds")
        except ValueError as e:
            raise ConfigurationError(f"Invalid FEED_POLL_INTERVAL value: {e}")

        try:
            self.feed_max_items_per_poll = int(os.getenv("FEED_MAX_ITEMS_PER_POLL", "5"))
            if self.feed_max_items_per_poll < 1:
                raise ValueError("FEED_MAX_ITEMS_PER_POLL must be at least 1")
        except ValueError as e:
            raise ConfigurationError(f"Invalid FEED_MAX_ITEMS_PER_POLL value: {e}")

        try:
            self.feed_fetch_timeout = float(os.getenv("FEED_FETCH_TIMEOUT", "20.0"))
            if self.feed_fetch_timeout <= 0:
                raise ValueError("FEED_FETCH_TIMEOUT must be positive")
        except ValueError as e:
            raise ConfigurationError(f"Invalid FEED_FETCH_TIMEOUT value: {e}")

        self.db_path = os.path.join(base_dir, "data", "queue", "autodl.db")


def load_config(base_dir: str):
    """Load configuration from environment variables."""
    return Config(base_dir)
