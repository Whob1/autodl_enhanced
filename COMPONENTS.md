# autodl_enhanced Component Reference

Detailed documentation of all modules, classes, and functions in the autodl_enhanced project.

**Table of Contents**
1. [Entry Point](#entry-point-autodl_botpy)
2. [Configuration](#configuration-config_managerpy)
3. [Queue Manager](#queue-manager-queue_managerpy)
4. [Download Manager](#download-manager-download_managerpy)
5. [Handlers](#handlers)
6. [Utilities](#utilities)

---

## Entry Point: `autodl_bot.py`

**File Path**: `/path/to/project/src/autodl_bot.py`
**Lines**: ~101
**Purpose**: Initialize Telegram bot, register handlers, manage async application lifecycle

### Class: `AutoDLBot`

Main bot class responsible for application initialization and management.

#### `__init__(config: Config)`

**Parameters**:
- `config: Config` - Configuration object containing all bot settings

**Initialization**:
```python
def __init__(self, config: Config):
    self.config = config
    self.logger = get_logger(__name__)

    # Initialize managers
    self.queue_manager = QueueManager(config)
    self.download_manager = DownloadManager(config, self.queue_manager)

    # Initialize Telegram application
    self.application = Application.builder() \
        .token(config.telegram_bot_token) \
        .build()

    self._register_handlers()
```

**Attributes**:
- `config: Config` - Bot configuration
- `logger: logging.Logger` - Application logger
- `queue_manager: QueueManager` - Persistent queue manager
- `download_manager: DownloadManager` - Download orchestrator
- `application: Application` - Telegram bot application

#### `_register_handlers()`

**Purpose**: Register all Telegram message and command handlers

**Handler Registration**:
```python
def _register_handlers(self):
    # Command handlers
    self.application.add_handler(
        CommandHandler("start", command_handler.cmd_start)
    )
    self.application.add_handler(
        CommandHandler("queue", command_handler.cmd_queue)
    )
    self.application.add_handler(
        CommandHandler("status", command_handler.cmd_status)
    )
    self.application.add_handler(
        CommandHandler("pause", command_handler.cmd_pause)
    )
    self.application.add_handler(
        CommandHandler("resume", command_handler.cmd_resume)
    )
    self.application.add_handler(
        CommandHandler("retry", command_handler.cmd_retry)
    )
    self.application.add_handler(
        CommandHandler("clear", command_handler.cmd_clear)
    )

    # Message handlers
    self.application.add_handler(
        MessageHandler(filters.TEXT, message_handler.handle_text_message)
    )
    self.application.add_handler(
        MessageHandler(
            filters.Document.FileExtension("txt"),
            message_handler.handle_text_file
        )
    )
```

**Handler Order**: Command handlers processed before message handlers (priority matters).

#### `async start_application()`

**Purpose**: Start the bot application with background managers

**Flow**:
```python
async def start_application(self):
    self.logger.info("Starting AutoDL Bot...")

    # Create background tasks
    download_task = asyncio.create_task(self.download_manager.run())
    queue_task = asyncio.create_task(self.queue_manager.run())

    try:
        # Start Telegram polling
        await self.application.run_polling(allowed_updates=Update.ALL_TYPES)
    finally:
        # Cleanup on shutdown
        download_task.cancel()
        queue_task.cancel()
        self.logger.info("Bot stopped")
```

**Concurrent Tasks**:
1. `self.download_manager.run()` - Download worker pool
2. `self.queue_manager.run()` - Queue management and retry scheduling
3. `self.application.run_polling()` - Telegram message polling

#### `async stop_application()`

**Purpose**: Gracefully shutdown all services

**Cleanup**:
```python
async def stop_application(self):
    self.logger.info("Stopping AutoDL Bot...")
    await self.download_manager.pause_downloads()
    await self.application.stop()
```

### Module-Level Functions

#### `async main()`

**Purpose**: Entry point for bot execution

**Implementation**:
```python
async def main():
    config = Config.from_env()  # Load configuration from .env
    bot = AutoDLBot(config)
    await bot.start_application()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Configuration: `config_manager.py`

**File Path**: `/path/to/project/src/config_manager.py`
**Lines**: ~49
**Purpose**: Load environment variables, validate configuration, provide defaults

### Class: `Config`

**Type**: `@dataclass`

**Purpose**: Immutable configuration container

#### Attributes

**Telegram Settings**:
```python
telegram_bot_token: str              # Required: Bot token from BotFather
telegram_admin_ids: List[int]        # Admin user IDs for authorization
```

**Download Settings**:
```python
download_dir: Path                   # Directory to save downloads
max_concurrent: int                  # Max parallel downloads (default: 8)
max_retries: int                     # Max retry attempts (default: 5)
retry_sleep: float                   # Base retry delay in seconds (default: 1)
socket_timeout: int                  # Network timeout in seconds (default: 30)
max_video_quality: str               # Max quality (default: "1080p")
preferred_format: str                # Format preference (default: "mp4")
skip_hls: bool                       # Skip HLS streams (default: True)
skip_dash: bool                      # Skip DASH streams (default: True)
use_aria2c: bool                     # Use aria2c downloader (default: True)
cookies_file: Optional[Path]         # Path to cookies file for auth
```

**System Settings**:
```python
min_disk_space_gb: float             # Min disk space before pause (default: 50)
max_playlist_videos: int             # Max videos per playlist (default: 300)
log_level: str                       # Logging level (default: "INFO")
```

**Database**:
```python
db_path: Path                        # SQLite database path
```

#### `@classmethod from_env() -> Config`

**Purpose**: Load configuration from environment variables and .env file

**Loading Order**:
1. Load `.env` file using `python-dotenv`
2. Read environment variables with defaults
3. Validate required fields
4. Convert types (strings to int, Path, etc.)
5. Return Config instance

**Implementation**:
```python
@classmethod
def from_env(cls) -> "Config":
    load_dotenv()  # Load from .env file

    # Required fields
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")

    admin_ids_str = os.getenv("TELEGRAM_ADMIN_IDS", "")
    admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]

    # Optional fields with defaults
    return cls(
        telegram_bot_token=bot_token,
        telegram_admin_ids=admin_ids,
        download_dir=Path(os.getenv("DOWNLOAD_DIR", "/path/to/downloads")),
        max_concurrent=int(os.getenv("MAX_CONCURRENT", "8")),
        max_retries=int(os.getenv("MAX_RETRIES", "5")),
        # ... etc
    )
```

#### Example `.env` File

```env
# Required
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN_HERE
TELEGRAM_ADMIN_IDS=1234567890

# Download Settings
DOWNLOAD_DIR=/path/to/downloads
MAX_CONCURRENT=8
USE_ARIA2C=true
MAX_VIDEO_QUALITY=1080p
PREFERRED_FORMAT=mp4
SKIP_HLS=true
SKIP_DASH=true

# System Settings
MIN_DISK_SPACE_GB=50.0
MAX_PLAYLIST_VIDEOS=300
LOG_LEVEL=INFO

# Advanced
SOCKET_TIMEOUT=30
MAX_RETRIES=5
RETRY_SLEEP=1
COOKIES_FILE=/path/to/project/data/cookies/cookies.txt
```

---

## Queue Manager: `queue_manager.py`

**File Path**: `/path/to/project/src/queue_manager.py`
**Lines**: ~351
**Purpose**: Manage persistent SQLite queue with deduplication and retry logic

### Class: `DownloadTask`

**Type**: `@dataclass`

**Purpose**: Represent a download task in the queue

#### Attributes

```python
@dataclass
class DownloadTask:
    id: int                              # Unique task ID
    url: str                             # Download URL
    status: str                          # pending, processing, completed, failed
    attempts: int                        # Number of attempts made
    added_at: float                      # Unix timestamp when added
    updated_at: float                    # Unix timestamp of last update
    next_attempt_at: Optional[float]     # Unix timestamp for next retry
    file_path: Optional[str]             # Path to downloaded file
    error_message: Optional[str]         # Error message if failed
    url_hash: Optional[str] = None       # SHA256 hash of normalized URL
    video_id: Optional[str] = None       # Platform-specific video ID
```

**Status Values**:
- `pending`: Waiting to be processed
- `processing`: Currently downloading
- `completed`: Successfully downloaded
- `failed`: Max retries exceeded

### Class: `QueueManager`

**Purpose**: Async SQLite queue management

#### `__init__(config: Config)`

**Parameters**:
- `config: Config` - Configuration object

**Initialization**:
```python
def __init__(self, config: Config):
    self.config = config
    self.db_path = config.db_path
    self.logger = get_logger(__name__)
    self._lock = asyncio.Lock()  # For atomic operations
```

**Attributes**:
- `config: Config` - Bot configuration
- `db_path: Path` - SQLite database path
- `logger: logging.Logger` - Logger instance
- `_lock: asyncio.Lock` - Lock for thread-safe operations

#### `async initialize()`

**Purpose**: Create database schema if not exists

**Operations**:
```python
async def initialize(self):
    async with aiosqlite.connect(self.db_path) as db:
        await db.execute("""
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
                video_id TEXT
            )
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_url_hash ON tasks(url_hash)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_video_id ON tasks(video_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_status ON tasks(status)
        """)

        await db.commit()
```

#### `async add_task(url: str, video_id: Optional[str] = None, url_hash: Optional[str] = None) -> DownloadTask`

**Purpose**: Add a URL to the download queue

**Parameters**:
- `url: str` - Download URL
- `video_id: Optional[str]` - Platform-specific video ID (for dedup)
- `url_hash: Optional[str]` - SHA256 hash of normalized URL (for dedup)

**Returns**: `DownloadTask` - The created task

**Implementation**:
```python
async def add_task(self, url: str, video_id: Optional[str] = None,
                   url_hash: Optional[str] = None) -> DownloadTask:
    current_time = time.time()

    async with aiosqlite.connect(self.db_path) as db:
        cursor = await db.execute("""
            INSERT INTO tasks (
                url, status, attempts, added_at, updated_at, url_hash, video_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (url, 'pending', 0, current_time, current_time, url_hash, video_id))

        await db.commit()

        task_id = cursor.lastrowid
        return DownloadTask(
            id=task_id,
            url=url,
            status='pending',
            attempts=0,
            added_at=current_time,
            updated_at=current_time,
            next_attempt_at=None,
            file_path=None,
            error_message=None,
            url_hash=url_hash,
            video_id=video_id
        )
```

#### `async fetch_pending_task() -> Optional[DownloadTask]`

**Purpose**: Atomically fetch next pending task ready for download

**Returns**: `Optional[DownloadTask]` - Next task or None if no pending

**Key Feature**: Uses atomic update-then-select to prevent multiple workers getting same task

**Implementation**:
```python
async def fetch_pending_task(self) -> Optional[DownloadTask]:
    async with self._lock:
        async with aiosqlite.connect(self.db_path) as db:
            current_time = time.time()

            # Atomically find and update pending task
            cursor = await db.execute("""
                SELECT * FROM tasks
                WHERE status='pending'
                AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
                ORDER BY added_at ASC
                LIMIT 1
            """, (current_time,))

            row = await cursor.fetchone()
            if not row:
                return None

            task_id = row[0]

            # Mark as processing (atomic)
            await db.execute("""
                UPDATE tasks SET status='processing', updated_at=? WHERE id=?
            """, (time.time(), task_id))

            await db.commit()

            return DownloadTask(*row)
```

#### `async mark_processing(task_id: int)`

**Purpose**: Mark task as currently downloading

**Parameters**:
- `task_id: int` - Task ID to update

**Implementation**:
```python
async def mark_processing(self, task_id: int):
    async with aiosqlite.connect(self.db_path) as db:
        await db.execute("""
            UPDATE tasks SET status='processing', updated_at=? WHERE id=?
        """, (time.time(), task_id))
        await db.commit()
```

#### `async mark_completed(task_id: int, file_path: str)`

**Purpose**: Mark task as successfully downloaded

**Parameters**:
- `task_id: int` - Task ID to update
- `file_path: str` - Path to downloaded file

**Implementation**:
```python
async def mark_completed(self, task_id: int, file_path: str):
    async with aiosqlite.connect(self.db_path) as db:
        await db.execute("""
            UPDATE tasks
            SET status='completed', file_path=?, updated_at=?
            WHERE id=?
        """, (file_path, time.time(), task_id))
        await db.commit()

        self.logger.info(f"Task {task_id} completed: {file_path}")
```

#### `async reschedule_task(task_id: int, error_message: str)`

**Purpose**: Reschedule failed task with exponential backoff

**Parameters**:
- `task_id: int` - Task ID to reschedule
- `error_message: str` - Error message from failure

**Exponential Backoff**:
```python
next_delay = 2 ** task.attempts * self.config.retry_sleep
# Attempt 1: 2^0 * 1 = 1 second
# Attempt 2: 2^1 * 1 = 2 seconds
# Attempt 3: 2^2 * 1 = 4 seconds
# etc.
```

**Implementation**:
```python
async def reschedule_task(self, task_id: int, error_message: str):
    async with aiosqlite.connect(self.db_path) as db:
        cursor = await db.execute("""
            SELECT attempts FROM tasks WHERE id=?
        """, (task_id,))

        row = await cursor.fetchone()
        if not row:
            return

        attempts = row[0]

        if attempts >= self.config.max_retries:
            # Mark as failed
            await db.execute("""
                UPDATE tasks
                SET status='failed', error_message=?, updated_at=?
                WHERE id=?
            """, (error_message, time.time(), task_id))

            self.logger.error(f"Task {task_id} failed (max retries): {error_message}")
        else:
            # Schedule retry with exponential backoff
            next_delay = 2 ** attempts * self.config.retry_sleep
            next_attempt = time.time() + next_delay

            await db.execute("""
                UPDATE tasks
                SET status='pending', next_attempt_at=?, attempts=?,
                    error_message=?, updated_at=?
                WHERE id=?
            """, (next_attempt, attempts + 1, error_message, time.time(), task_id))

            self.logger.warning(
                f"Task {task_id} will retry in {next_delay:.0f}s "
                f"(attempt {attempts + 1}/{self.config.max_retries})"
            )

        await db.commit()
```

#### `async check_duplicate(url_hash: Optional[str], video_id: Optional[str]) -> bool`

**Purpose**: Check if URL already in queue (any status)

**Parameters**:
- `url_hash: Optional[str]` - SHA256 hash of normalized URL
- `video_id: Optional[str]` - Platform-specific video ID

**Returns**: `bool` - True if duplicate found

**Implementation**:
```python
async def check_duplicate(self, url_hash: Optional[str],
                          video_id: Optional[str]) -> bool:
    async with aiosqlite.connect(self.db_path) as db:
        # Check by URL hash
        if url_hash:
            cursor = await db.execute("""
                SELECT id FROM tasks WHERE url_hash=? LIMIT 1
            """, (url_hash,))

            if await cursor.fetchone():
                return True

        # Check by video ID
        if video_id:
            cursor = await db.execute("""
                SELECT id FROM tasks WHERE video_id=? LIMIT 1
            """, (video_id,))

            if await cursor.fetchone():
                return True

        return False
```

#### `async get_status_summary() -> Dict[str, int]`

**Purpose**: Get queue statistics (pending, processing, completed, failed)

**Returns**: `Dict[str, int]` - Status counts

**Implementation**:
```python
async def get_status_summary(self) -> Dict[str, int]:
    async with aiosqlite.connect(self.db_path) as db:
        cursor = await db.execute("""
            SELECT status, COUNT(*) FROM tasks GROUP BY status
        """)

        rows = await cursor.fetchall()
        result = {
            'pending': 0,
            'processing': 0,
            'completed': 0,
            'failed': 0
        }

        for status, count in rows:
            result[status] = count

        return result
```

#### `async clear_completed_tasks()`

**Purpose**: Remove all completed and failed tasks from queue

**Implementation**:
```python
async def clear_completed_tasks(self):
    async with aiosqlite.connect(self.db_path) as db:
        cursor = await db.execute("""
            DELETE FROM tasks WHERE status IN ('completed', 'failed')
        """)

        deleted = cursor.rowcount

        await db.commit()
        self.logger.info(f"Cleared {deleted} completed/failed tasks")
```

#### `async run()`

**Purpose**: Background task for queue management and retry scheduling

**Periodic Tasks**:
```python
async def run(self):
    self.logger.info("Queue manager started")

    while True:
        try:
            # Reschedule failed tasks whose retry time has arrived
            await self.reschedule_failed_tasks()

            # Wait before next check
            await asyncio.sleep(5)  # Check every 5 seconds

        except Exception as e:
            self.logger.error(f"Queue manager error: {e}")
            await asyncio.sleep(5)
```

---

## Download Manager: `download_manager.py`

**File Path**: `/path/to/project/src/download_manager.py`
**Lines**: ~400+
**Purpose**: Orchestrate downloads, manage worker pool, track progress

### Class: `DownloadManager`

**Purpose**: Async download orchestration with worker pool

#### `__init__(config: Config, queue_manager: QueueManager)`

**Parameters**:
- `config: Config` - Configuration object
- `queue_manager: QueueManager` - Queue manager instance

**Initialization**:
```python
def __init__(self, config: Config, queue_manager: QueueManager):
    self.config = config
    self.queue_manager = queue_manager
    self.logger = get_logger(__name__)

    self._pause_event = asyncio.Event()  # Not set = paused
    self._pause_event.set()              # Start unpaused

    self._active_downloads = {}  # {task_id: DownloadTask}
    self._lock = asyncio.Lock()
```

**Attributes**:
- `config: Config` - Bot configuration
- `queue_manager: QueueManager` - Queue manager reference
- `logger: logging.Logger` - Logger instance
- `_pause_event: asyncio.Event` - Pause/resume control
- `_active_downloads: Dict` - Tracking active downloads
- `_lock: asyncio.Lock` - Lock for shared state

#### `async run()`

**Purpose**: Main event loop spawning worker coroutines

**Worker Pool Pattern**:
```python
async def run(self):
    self.logger.info(f"Download manager started (max {self.config.max_concurrent} workers)")

    # Create worker tasks
    workers = [
        asyncio.create_task(self._worker())
        for _ in range(self.config.max_concurrent)
    ]

    try:
        # Wait for all workers (they run forever)
        await asyncio.gather(*workers)
    except asyncio.CancelledError:
        self.logger.info("Download manager cancelled")
        for worker in workers:
            worker.cancel()
        raise
```

**Creates**: `max_concurrent` (default 8) concurrent worker coroutines

#### `async _worker()`

**Purpose**: Individual worker loop - fetch task, download, update queue

**Worker Lifecycle**:
```python
async def _worker(self):
    while True:
        try:
            # Check pause flag
            if not self._pause_event.is_set():
                await asyncio.sleep(1)
                continue

            # Fetch next pending task
            task = await self.queue_manager.fetch_pending_task()
            if not task:
                await asyncio.sleep(2)  # No tasks, wait
                continue

            # Add to active downloads tracking
            async with self._lock:
                self._active_downloads[task.id] = task

            # Perform download
            success, file_path, error = await self._download(task)

            # Update queue based on result
            if success:
                await self.queue_manager.mark_completed(task.id, file_path)
                self.logger.info(f"Task {task.id} completed: {file_path}")
            else:
                await self.queue_manager.reschedule_task(task.id, error)
                self.logger.warning(f"Task {task.id} failed: {error}")

            # Remove from active downloads
            async with self._lock:
                self._active_downloads.pop(task.id, None)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.error(f"Worker error: {e}")
            await asyncio.sleep(1)
```

#### `async _download(task: DownloadTask) -> tuple`

**Purpose**: Execute yt-dlp download for a task

**Parameters**:
- `task: DownloadTask` - Task to download

**Returns**: `(success: bool, file_path: Optional[str], error: Optional[str])`

**Flow**:
```python
async def _download(self, task: DownloadTask) -> tuple:
    try:
        # Check disk space
        free_gb = await disk_monitor.get_free_space(self.config.download_dir)
        if free_gb < self.config.min_disk_space_gb:
            await self.pause_downloads()
            return (False, None, f"Low disk space: {free_gb:.1f}GB")

        # Prepare yt-dlp options
        ydl_opts = {
            'format': self._build_format_string(),
            'outtmpl': os.path.join(
                self.config.download_dir,
                '%(title)s.%(ext)s'
            ),
            'socket_timeout': self.config.socket_timeout,
            'quiet': False,
            'no_warnings': False,
            'no_color': True,
        }

        # Add aria2c if configured
        if self.config.use_aria2c:
            ydl_opts['external_downloader'] = 'aria2c'
            ydl_opts['external_downloader_args'] = '-x 16 -k 1M'

        # Add cookies if available
        if self.config.cookies_file and self.config.cookies_file.exists():
            ydl_opts['cookiefile'] = str(self.config.cookies_file)

        # Skip streams if configured
        if self.config.skip_hls:
            ydl_opts['skip_unavailable_fragments'] = True
        if self.config.skip_dash:
            ydl_opts['skip_unavailable_fragments'] = True

        # Run yt-dlp in executor (non-blocking)
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(
                None,
                ydl.extract_info,
                task.url,
                False
            )

            if info:
                file_path = ydl.prepare_filename(info)
                return (True, file_path, None)
            else:
                return (False, None, "No extractable format found")

    except yt_dlp.utils.DownloadError as e:
        # Permanent errors - don't retry
        error_str = str(e)
        if any(x in error_str.lower() for x in ['removed', 'deleted', 'private']):
            return (False, None, f"Permanent error: {error_str}")
        else:
            # Transient error - will retry
            return (False, None, error_str)

    except Exception as e:
        return (False, None, f"Download error: {str(e)}")
```

#### `_build_format_string() -> str`

**Purpose**: Build yt-dlp format string based on quality config

**Returns**: `str` - Format string for yt-dlp

**Quality Map**:
```python
def _build_format_string(self) -> str:
    quality_map = {
        '4K': '2160',
        '1440p': '1440',
        '1080p': '1080',
        '720p': '720',
        '480p': '480',
        'best': 'best',
    }

    max_height = quality_map.get(
        self.config.max_video_quality,
        quality_map['1080p']
    )

    if max_height == 'best':
        return 'best'
    else:
        return f"best[height<={max_height}]/best"
```

**Examples**:
- `max_video_quality='1080p'` → `"best[height<=1080]/best"`
- `max_video_quality='720p'` → `"best[height<=720]/best"`
- `max_video_quality='4K'` → `"best[height<=2160]/best"`

#### `async pause_downloads()`

**Purpose**: Pause all active downloads

**Implementation**:
```python
async def pause_downloads(self):
    self._pause_event.clear()
    self.logger.info("Downloads paused")
```

#### `async resume_downloads()`

**Purpose**: Resume paused downloads

**Implementation**:
```python
async def resume_downloads(self):
    self._pause_event.set()
    self.logger.info("Downloads resumed")
```

#### `async get_active_downloads() -> Dict[int, DownloadTask]`

**Purpose**: Get list of currently downloading tasks

**Returns**: `Dict[int, DownloadTask]` - Active download tasks

**Implementation**:
```python
async def get_active_downloads(self) -> Dict[int, DownloadTask]:
    async with self._lock:
        return dict(self._active_downloads)
```

---

## Handlers

### Command Handler: `handlers/command_handler.py`

**File Path**: `/path/to/project/src/handlers/command_handler.py`
**Purpose**: Handle Telegram bot commands with admin authentication

#### Decorator: `@admin_only`

**Purpose**: Verify user is admin before executing command

**Implementation**:
```python
def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in context.bot_data['config'].telegram_admin_ids:
            await update.message.reply_text("⛔ You are not authorized to use this bot.")
            return

        return await func(update, context)

    return wrapper
```

#### `async cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE)`

**Purpose**: Welcome message and command list

**Response**:
```
🤖 Welcome to AutoDL Bot!

I can download media from YouTube, Twitch, Instagram, and 100+ other platforms.

📝 How to use:
1. Send a URL directly for single downloads
2. Upload a .txt file with multiple URLs (one per line)
3. Send a playlist URL to expand all videos

📋 Available Commands:
/queue - Show current queue
/status - System and queue status
/pause - Pause downloads
/resume - Resume downloads
/retry - Retry failed downloads
/clear - Clear completed tasks
```

#### `async cmd_queue(update: Update, context: ContextTypes.DEFAULT_TYPE)`

**Purpose**: Display current download queue

**Query**: Fetches all tasks with status in (pending, processing, completed, failed)

**Response Format**:
```
📥 Download Queue

⏳ Pending (5):
• video1.mp4
• video2.mp4
[... up to 5 shown ...]

▶️ Processing (2):
• video3.mp4 (45% complete)
• video4.mp4 (12% complete)

✅ Completed (156)
❌ Failed (3)
```

**Implementation**:
```python
@admin_only
async def cmd_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    queue_mgr = context.bot_data['queue_manager']

    # Fetch pending tasks
    pending = await queue_mgr.get_tasks_by_status('pending', limit=5)

    # Fetch processing tasks
    processing = await queue_mgr.get_tasks_by_status('processing')

    # Build response
    msg = "📥 *Download Queue*\n\n"

    msg += f"⏳ *Pending* ({len(pending)}):\n"
    for task in pending:
        msg += f"• {task.url[:50]}...\n"

    msg += f"\n▶️ *Processing* ({len(processing)}):\n"
    for task in processing:
        msg += f"• {task.url[:50]}...\n"

    await update.message.reply_text(msg, parse_mode='Markdown')
```

#### `async cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE)`

**Purpose**: Display system metrics and queue summary

**Metrics**:
- CPU usage percentage
- Memory usage percentage
- Disk usage percentage
- Queue statistics (pending, processing, completed, failed)

**Response Format**:
```
📊 *System Status*

🖥️ *System Metrics*
CPU: 45.2% | RAM: 62.1% | Disk: 78.3%

📥 *Queue Summary*
Pending: 12 | Processing: 4 | Completed: 156 | Failed: 3

⏳ *Active Downloads* (Top 5):
1. video1.mp4 - 45%
2. video2.mp4 - 78%
3. video3.mp4 - 12%
```

#### `async cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE)`

**Purpose**: Pause all downloads

**Response**: `⏸️ Downloads paused`

**Implementation**:
```python
@admin_only
async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    download_mgr = context.bot_data['download_manager']
    await download_mgr.pause_downloads()
    await update.message.reply_text("⏸️ Downloads paused")
```

#### `async cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE)`

**Purpose**: Resume paused downloads

**Response**: `▶️ Downloads resumed`

#### `async cmd_retry(update: Update, context: ContextTypes.DEFAULT_TYPE)`

**Purpose**: Retry all failed downloads

**Implementation**:
```python
@admin_only
async def cmd_retry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    queue_mgr = context.bot_data['queue_manager']

    # Fetch all failed tasks
    failed = await queue_mgr.get_tasks_by_status('failed')

    # Reset to pending
    for task in failed:
        await queue_mgr.reschedule_task(task.id, "User retry")

    await update.message.reply_text(f"🔄 Retrying {len(failed)} failed downloads")
```

#### `async cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE)`

**Purpose**: Clear completed and failed tasks from queue

**Response**: `🗑️ Cleared 156 completed and 3 failed tasks`

---

### Message Handler: `handlers/message_handler.py`

**File Path**: `/path/to/project/src/handlers/message_handler.py`
**Purpose**: Handle text messages and file uploads

#### `async handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE)`

**Purpose**: Process URLs sent directly as text

**Flow**:
1. Extract text from message
2. Validate URL format
3. Check for duplicate
4. Extract video ID and URL hash
5. Add to queue
6. Confirm to user

**Implementation**:
```python
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    queue_mgr = context.bot_data['queue_manager']

    # Validate URL
    if not validators.is_valid_url(url):
        await update.message.reply_text("❌ Invalid URL format")
        return

    # Check duplicate
    video_id = deduplication.extract_video_id(url)
    url_hash = deduplication.hash_url(url)

    if await queue_mgr.check_duplicate(url_hash, video_id):
        await update.message.reply_text("⚠️ This URL is already queued or completed")
        return

    # Add to queue
    task = await queue_mgr.add_task(url, video_id, url_hash)

    await update.message.reply_text(
        f"✅ Added to queue (ID: {task.id})\n"
        f"📝 URL: {url[:50]}..."
    )
```

#### `async handle_text_file(update: Update, context: ContextTypes.DEFAULT_TYPE)`

**Purpose**: Process .txt file uploads with multiple URLs

**Flow**:
1. Download file from Telegram
2. Extract URLs from text
3. Detect playlists
4. Expand playlists if detected
5. Deduplicate each URL
6. Add all to queue
7. Confirm count to user

**Implementation**:
```python
async def handle_text_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    queue_mgr = context.bot_data['queue_manager']

    # Download file
    file = await context.bot.get_file(update.message.document.file_id)
    content = await file.download_as_bytearray()
    text = content.decode('utf-8')

    # Extract URLs
    urls = validators.extract_urls_from_text(text)
    total_added = 0

    for url in urls:
        # Check if playlist
        if validators.is_playlist_url(url):
            # Expand playlist
            playlist_urls = await _extract_playlist_urls(url)
            urls.extend(playlist_urls)
            continue

        # Check duplicate
        video_id = deduplication.extract_video_id(url)
        url_hash = deduplication.hash_url(url)

        if not await queue_mgr.check_duplicate(url_hash, video_id):
            await queue_mgr.add_task(url, video_id, url_hash)
            total_added += 1

    await update.message.reply_text(
        f"✅ Added {total_added} URLs to queue"
    )
```

#### `async _extract_playlist_urls(url: str) -> List[str]`

**Purpose**: Extract individual video URLs from playlist

**Uses**: yt-dlp `extract_info()` with `process_info=False`

**Implementation**:
```python
async def _extract_playlist_urls(url: str) -> List[str]:
    loop = asyncio.get_event_loop()

    def extract():
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, process=False)
            if 'entries' in info:
                # Limit to configured max
                entries = info['entries'][:config.max_playlist_videos]
                return [entry['url'] for entry in entries if 'url' in entry]
        return []

    return await loop.run_in_executor(None, extract)
```

---

## Utilities

### Validators: `utils/validators.py`

**File Path**: `/path/to/project/src/utils/validators.py`
**Purpose**: URL validation and extraction

#### `def is_valid_url(url: str) -> bool`

**Purpose**: Validate URL format

**Pattern**: `^https?://[^\s]+`

**Returns**: `bool` - True if valid URL

```python
def is_valid_url(url: str) -> bool:
    pattern = r'^https?://[^\s]+'
    return bool(re.match(pattern, url))
```

#### `def extract_urls_from_text(text: str) -> List[str]`

**Purpose**: Extract all URLs from multi-line text

**Returns**: `List[str]` - Found URLs

```python
def extract_urls_from_text(text: str) -> List[str]:
    pattern = r'https?://[^\s]+'
    return re.findall(pattern, text)
```

#### `def is_playlist_url(url: str) -> bool`

**Purpose**: Detect if URL is a playlist

**Heuristics**: Contains 'playlist' or 'series' in URL

```python
def is_playlist_url(url: str) -> bool:
    url_lower = url.lower()
    return 'playlist' in url_lower or 'series' in url_lower or 'list=' in url_lower
```

---

### Deduplication: `utils/deduplication.py`

**File Path**: `/path/to/project/src/utils/deduplication.py`
**Purpose**: URL normalization and duplicate detection

#### `def normalize_url(url: str) -> str`

**Purpose**: Normalize URL for hashing (remove tracking parameters)

**Removes**: `utm_*`, `fbclid`, `gclid`, `msclkid`, etc.

```python
def normalize_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)

    # Remove tracking parameters
    tracking_prefixes = ['utm_', 'fbclid', 'gclid', 'msclkid']
    clean_params = {
        k: v for k, v in params.items()
        if not any(k.startswith(p) for p in tracking_prefixes)
    }

    clean_query = urllib.parse.urlencode(clean_params, doseq=True)
    return urllib.parse.urlunparse((
        parsed.scheme, parsed.netloc, parsed.path,
        parsed.params, clean_query, parsed.fragment
    ))
```

#### `def hash_url(url: str) -> str`

**Purpose**: Create SHA256 hash of normalized URL

**Returns**: `str` - Hex digest of hash

```python
def hash_url(url: str) -> str:
    normalized = normalize_url(url)
    return hashlib.sha256(normalized.encode()).hexdigest()
```

#### `def extract_video_id(url: str) -> Optional[str]`

**Purpose**: Extract platform-specific video ID

**Supported Platforms**:
- YouTube: `v=` parameter or `/shorts/` path
- Pornhub: `viewkey=` parameter
- Xvideos: numeric path parameter
- Twitter/X: status ID from path
- Reddit: post ID from path
- Twitch: channel/video ID

**Returns**: `Optional[str]` - Extracted ID or None

```python
def extract_video_id(url: str) -> Optional[str]:
    # YouTube
    if 'youtube.com' in url or 'youtu.be' in url:
        match = re.search(r'v=([^&]+)', url)
        if match:
            return match.group(1)
        match = re.search(r'/shorts/([^/?]+)', url)
        if match:
            return match.group(1)

    # Pornhub
    if 'pornhub.com' in url:
        match = re.search(r'viewkey=([^&]+)', url)
        if match:
            return match.group(1)

    # Twitter/X
    if 'twitter.com' in url or 'x.com' in url:
        match = re.search(r'/status/(\d+)', url)
        if match:
            return match.group(1)

    # Reddit
    if 'reddit.com' in url:
        match = re.search(r'/r/[^/]+/comments/([^/?]+)', url)
        if match:
            return match.group(1)

    # Fallback: none
    return None
```

---

### Logger: `utils/logger.py`

**File Path**: `/path/to/project/src/utils/logger.py`
**Purpose**: Unified logging setup

#### `def get_logger(name: str) -> logging.Logger`

**Purpose**: Get or create logger with file and console handlers

**Parameters**:
- `name: str` - Logger name (usually `__name__`)

**Returns**: `logging.Logger` - Configured logger

**Features**:
- Rotating file handler (10 MB, 5 backups)
- Console handler
- Configurable log level
- Formatted timestamps

```python
def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, config.log_level))

    if logger.handlers:
        return logger  # Already configured

    # File handler with rotation
    log_dir = config.db_path.parent.parent / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_dir / 'autodl-bot.log',
        maxBytes=10_000_000,  # 10 MB
        backupCount=5
    )

    # Console handler
    console_handler = logging.StreamHandler()

    # Format
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
```

---

### Disk Monitor: `utils/disk_monitor.py`

**File Path**: `/path/to/project/src/utils/disk_monitor.py`
**Purpose**: Monitor disk space

#### `async def get_free_space(path: Path) -> float`

**Purpose**: Get free disk space in GB

**Parameters**:
- `path: Path` - Directory to check

**Returns**: `float` - Free space in GB

```python
async def get_free_space(path: Path) -> float:
    stat = os.statvfs(path)
    free_space_bytes = stat.f_bavail * stat.f_frsize
    return free_space_bytes / (1024 ** 3)
```

---

### Performance Monitor: `utils/performance.py`

**File Path**: `/path/to/project/src/utils/performance.py`
**Purpose**: Monitor system resources

#### `def get_system_metrics() -> Dict[str, float]`

**Purpose**: Get CPU, memory, and disk usage

**Returns**: `Dict[str, float]` - Usage percentages

```python
def get_system_metrics() -> Dict[str, float]:
    return {
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_percent': psutil.disk_usage('/').percent,
    }
```

**Metrics**:
- `cpu_percent`: CPU usage 0-100%
- `memory_percent`: Memory usage 0-100%
- `disk_percent`: Disk usage 0-100%

---

## Summary

This completes the detailed component reference for **autodl_enhanced**. Each module has clear responsibilities:

- **autodl_bot.py**: Entry point and orchestration
- **config_manager.py**: Configuration loading and validation
- **queue_manager.py**: Persistent task queue and deduplication
- **download_manager.py**: Download orchestration with worker pool
- **handlers/**: Telegram command and message processing
- **utils/**: Validators, deduplication, logging, monitoring

All components work together asynchronously to provide a robust, scalable download bot.
