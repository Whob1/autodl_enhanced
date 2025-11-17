# autodl_enhanced Architecture

Comprehensive technical architecture documentation for the autodl_enhanced Telegram download bot.

## Table of Contents
1. [System Overview](#system-overview)
2. [Component Architecture](#component-architecture)
3. [Data Flow](#data-flow)
4. [Async Model](#async-model)
5. [Database Design](#database-design)
6. [Retry and Backoff Strategy](#retry-and-backoff-strategy)
7. [Deduplication System](#deduplication-system)
8. [Error Handling](#error-handling)
9. [Performance Optimization](#performance-optimization)
10. [Security Architecture](#security-architecture)

## System Overview

**autodl_enhanced** is built on a modular asynchronous architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TELEGRAM USER LAYER                             │
│                    (Users send URLs and commands)                        │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                    ┌────────────▼───────────────┐
                    │   MESSAGE HANDLERS LAYER   │
                    │  (command & message parse) │
                    └────────────┬───────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
    ┌────▼──────┐        ┌─────▼──────┐        ┌────────▼────┐
    │  COMMAND  │        │  MESSAGE   │        │  PLAYLIST   │
    │ HANDLER   │        │  HANDLER   │        │ EXTRACTION  │
    └────┬──────┘        └─────┬──────┘        └────────┬────┘
         │                     │                        │
         └─────────────────────┼────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  VALIDATION LAYER   │
                    │ (URL regex checks)  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ DEDUPLICATION LAYER │
                    │  (URL hash, ID)     │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────────────┐
                    │   QUEUE MANAGER LAYER       │
                    │ (SQLite persistence)        │
                    │ - Add tasks                 │
                    │ - Fetch pending tasks       │
                    │ - Manage retry scheduling   │
                    └──────────┬──────────────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
         ┌────▼──────────┐          ┌──────────▼────┐
         │ DOWNLOAD MGR  │          │ SYSTEM MONITOR│
         │ (worker pool) │          │ (disk, CPU)   │
         └────┬──────────┘          └──────────────┘
              │
    ┌─────────┴──────────┐
    │                    │
┌───▼──────┐        ┌───▼──────┐
│ YT-DLP   │        │  ARIA2C  │
│(native)  │        │(optional)│
└───┬──────┘        └───┬──────┘
    └────────┬──────────┘
             │
    ┌────────▼────────────┐
    │  DOWNLOADED MEDIA   │
    │  /path/to/downloads │
    └─────────────────────┘
```

## Component Architecture

### 1. Entry Point: `autodl_bot.py`

**Responsibility**: Bot initialization, handler registration, event loop management

**Key Functions**:
- `__init__()`: Initialize Telegram Application, register handlers
- `start_application()`: Start bot polling and async managers
- `stop_application()`: Graceful shutdown of services

**Handler Registration**:
```python
# Message handlers
application.add_handler(MessageHandler(filters.TEXT, message_handler.handle_text_message))
application.add_handler(MessageHandler(filters.Document.FileExtension("txt"), message_handler.handle_text_file))

# Command handlers
application.add_handler(CommandHandler("start", command_handler.cmd_start))
application.add_handler(CommandHandler("queue", command_handler.cmd_queue))
application.add_handler(CommandHandler("status", command_handler.cmd_status))
application.add_handler(CommandHandler("pause", command_handler.cmd_pause))
application.add_handler(CommandHandler("resume", command_handler.cmd_resume))
application.add_handler(CommandHandler("retry", command_handler.cmd_retry))
application.add_handler(CommandHandler("clear", command_handler.cmd_clear))
```

**Async Managers**:
- Starts `QueueManager.run()` in background task
- Starts `DownloadManager.run()` in background task
- Runs both concurrently with Telegram polling

---

### 2. Configuration: `config_manager.py`

**Responsibility**: Environment variable loading, configuration validation, default values

**Key Components**:

```python
@dataclass
class Config:
    # Telegram
    telegram_bot_token: str
    telegram_admin_ids: List[int]

    # Downloads
    download_dir: Path
    max_concurrent: int
    max_retries: int
    retry_sleep: float
    socket_timeout: int
    max_video_quality: str
    preferred_format: str
    skip_hls: bool
    skip_dash: bool
    use_aria2c: bool
    cookies_file: Optional[Path]

    # System
    min_disk_space_gb: float
    max_playlist_videos: int
    log_level: str

    # Database
    db_path: Path
```

**Loading Logic**:
1. Load from `.env` file using `python-dotenv`
2. Validate required fields (TELEGRAM_BOT_TOKEN)
3. Apply type conversions (strings to int, Path, etc.)
4. Apply sensible defaults for optional fields
5. Return Config dataclass instance

---

### 3. Queue Manager: `queue_manager.py`

**Responsibility**: Persistent task queue management, SQLite operations, retry scheduling

**Architecture**:

```python
@dataclass
class DownloadTask:
    id: int
    url: str
    status: str  # pending, processing, completed, failed
    attempts: int
    added_at: float  # Unix timestamp
    updated_at: float
    next_attempt_at: Optional[float]
    file_path: Optional[str]
    error_message: Optional[str]
    url_hash: Optional[str]
    video_id: Optional[str]
```

**Core Operations**:

| Method | Purpose | Usage |
|--------|---------|-------|
| `add_task(url, video_id, url_hash)` | Add URL to queue | After deduplication validation |
| `fetch_pending_tasks(limit)` | Get tasks ready to download | Download manager worker loop |
| `mark_processing(task_id)` | Mark task as downloading | When download starts |
| `mark_completed(task_id, file_path)` | Mark task successful | On download completion |
| `mark_failed(task_id, error_msg)` | Mark task failed | On download error |
| `get_status_summary()` | Queue statistics | `/status` command |
| `check_duplicate(url, video_id)` | Check if already queued | Deduplication |
| `reschedule_failed_tasks()` | Retry failed tasks | Periodic background task |
| `clear_completed_tasks()` | Remove done/failed tasks | `/clear` command |

**Database Indices**:
```sql
CREATE INDEX idx_url_hash ON tasks(url_hash);
CREATE INDEX idx_video_id ON tasks(video_id);
CREATE INDEX idx_status ON tasks(status);
```

**Async Operations**:
- Uses `aiosqlite` for non-blocking SQLite access
- `asyncio.Lock()` for thread-safe database operations
- All DB operations are `async def`

---

### 4. Download Manager: `download_manager.py`

**Responsibility**: Download orchestration, worker pool management, progress tracking, retry logic

**Architecture**:

```
Worker Pool Pattern:
┌─────────────────────────────────────────────────────────────┐
│                   Download Manager                          │
│  max_concurrent=8 (configurable)                            │
├─────────────────────────────────────────────────────────────┤
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│ │ Worker 1 │ │ Worker 2 │ │ Worker 3 │ │ Worker 4 │  ...   │
│ │ (async)  │ │ (async)  │ │ (async)  │ │ (async)  │        │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
└─────────────────────────────────────────────────────────────┘
```

**Key Methods**:

| Method | Purpose |
|--------|---------|
| `run()` | Main event loop, spawns workers |
| `_worker()` | Individual worker coroutine (fetch, download, handle errors) |
| `_download(task)` | yt-dlp execution wrapper |
| `pause_downloads()` | Set pause flag, pause workers gracefully |
| `resume_downloads()` | Clear pause flag, resume workers |
| `get_active_downloads()` | Get in-progress task list |

**Worker Lifecycle**:

```python
async def _worker(self):
    while True:
        # Check pause flag
        if self._pause_event.is_set():
            await asyncio.sleep(1)
            continue

        # Fetch task from queue
        task = await self.queue_manager.fetch_pending_task()
        if not task:
            await asyncio.sleep(2)
            continue

        # Mark as processing
        await self.queue_manager.mark_processing(task.id)

        # Download
        success, file_path, error = await self._download(task)

        # Update queue based on result
        if success:
            await self.queue_manager.mark_completed(task.id, file_path)
        else:
            # Exponential backoff retry
            next_attempt = time.time() + (2 ** task.attempts * self.config.retry_sleep)
            await self.queue_manager.reschedule_task(task.id, next_attempt, error)
```

**Download Execution**:

```python
async def _download(self, task: DownloadTask) -> tuple:
    """
    Execute yt-dlp download asynchronously
    Returns: (success: bool, file_path: Optional[str], error: Optional[str])
    """
    try:
        # Disk space check
        if free_space < min_required:
            return (False, None, "Insufficient disk space")

        # yt-dlp arguments
        ydl_opts = {
            'format': self._build_format_string(),
            'outtmpl': os.path.join(self.config.download_dir, '%(title)s.%(ext)s'),
            'socket_timeout': self.config.socket_timeout,
            'max_downloads': 1,
            'quiet': False,
            'no_warnings': False,
        }

        # Optional aria2c
        if self.config.use_aria2c:
            ydl_opts['external_downloader'] = 'aria2c'

        # Run yt-dlp in executor (non-blocking)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.get_event_loop().run_in_executor(
                None,
                ydl.extract_info,
                task.url,
                False
            )
            file_path = ydl.prepare_filename(info)
            return (True, file_path, None)

    except Exception as e:
        return (False, None, str(e))
```

**Quality Selection**:

```python
def _build_format_string(self) -> str:
    """
    Build yt-dlp format string based on configuration
    Example output: "best[height<=1080]/best"
    """
    quality_map = {
        '4K': '2160',
        '1440p': '1440',
        '1080p': '1080',
        '720p': '720',
        '480p': '480',
    }
    max_height = quality_map.get(self.config.max_video_quality, '1080')
    return f"best[height<={max_height}]/best"
```

---

### 5. Handlers Layer

#### Message Handler: `handlers/message_handler.py`

**Responsibility**: Parse incoming text and file messages, extract URLs

**Key Functions**:

```python
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle direct URL messages"""
    url = context.user_data.get('text', '')
    if is_valid_url(url):
        await queue_manager.add_task(url)
        await update.message.reply_text(f"Queued: {url}")

async def handle_text_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle .txt file uploads with URLs"""
    file = await context.bot.get_file(update.message.document.file_id)
    content = await file.download_as_bytearray()
    urls = extract_urls_from_text(content.decode('utf-8'))

    for url in urls:
        await queue_manager.add_task(url)

    await update.message.reply_text(f"Queued {len(urls)} URLs")
```

**URL Extraction**:
- Uses regex patterns to find URLs in text
- Validates http/https schemes only
- Splits newlines for file-based URLs

#### Command Handler: `handlers/command_handler.py`

**Responsibility**: Handle Telegram bot commands with admin authentication

**Commands Implemented**:

| Command | Purpose | Auth |
|---------|---------|------|
| `/start` | Welcome message, list commands | Admin |
| `/queue` | Show pending/processing tasks | Admin |
| `/status` | System metrics and queue summary | Admin |
| `/pause` | Pause all downloads | Admin |
| `/resume` | Resume paused downloads | Admin |
| `/retry` | Re-attempt failed tasks | Admin |
| `/clear` | Remove completed/failed tasks | Admin |

**Admin Check Pattern**:
```python
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.telegram_admin_ids:
        await update.message.reply_text("⛔ Unauthorized")
        return

    # ... execute command
```

**Status Command Output**:
```
📊 System Status
CPU: 42.5% | RAM: 58.3% | Disk: 71.2%

📥 Queue Summary
Pending: 8 | Processing: 3 | Completed: 124 | Failed: 2

⏳ Active Downloads
1. media_file_1.mp4 - 45% (5m 30s remaining)
2. media_file_2.mp4 - 78% (2m 15s remaining)
```

---

### 6. Utilities Layer

#### URL Validators: `utils/validators.py`

**Responsibility**: URL validation and extraction

**Key Functions**:

```python
def is_valid_url(url: str) -> bool:
    """Validate URL format"""
    pattern = r'^https?://[^\s]+'
    return bool(re.match(pattern, url))

def extract_urls_from_text(text: str) -> List[str]:
    """Extract all URLs from multi-line text"""
    pattern = r'https?://[^\s]+'
    return re.findall(pattern, text)

def is_playlist_url(url: str) -> bool:
    """Detect if URL is a playlist"""
    return 'playlist' in url.lower() or 'series' in url.lower()
```

#### Deduplication: `utils/deduplication.py`

**Responsibility**: Multi-level duplicate detection

**Strategy**:

```python
async def check_duplicate(url: str) -> bool:
    """Check if URL already in queue (any status)"""

    # Level 1: Normalize URL and compute hash
    normalized = normalize_url(url)
    url_hash = hashlib.sha256(normalized.encode()).hexdigest()

    # Level 2: Extract video ID
    video_id = extract_video_id(url)

    # Level 3: Query database
    existing = await queue_manager.check_duplicate(url_hash, video_id)
    return existing is not None

def normalize_url(url: str) -> str:
    """Remove tracking parameters and normalize"""
    # Remove utm_*, fbclid, gclid, etc.
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)

    # Keep only essential parameters
    clean_params = {k: v for k, v in params.items()
                   if not is_tracking_param(k)}

    clean_query = urllib.parse.urlencode(clean_params, doseq=True)
    return urllib.parse.urlunparse((
        parsed.scheme, parsed.netloc, parsed.path,
        parsed.params, clean_query, parsed.fragment
    ))

def extract_video_id(url: str) -> Optional[str]:
    """Extract platform-specific video ID"""
    # YouTube: v= parameter or shorts/
    # Pornhub: viewkey parameter
    # Twitter: /status/ID
    # etc.
```

**Supported Platforms for Video ID Extraction**:
- YouTube (v=, youtube.com/shorts/)
- Pornhub (viewkey)
- Xvideos, Xhamster, Redtube (numeric ID)
- Twitter/X (status ID)
- Reddit (post ID)
- Spankbang, OnlyFans

#### Logger: `utils/logger.py`

**Responsibility**: Unified logging setup

**Configuration**:

```python
def setup_logger(log_level: str, log_file: Path) -> logging.Logger:
    logger = logging.getLogger(__name__)
    logger.setLevel(getattr(logging, log_level))

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
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

**Log Rotation**:
- Max 10 MB per file
- Keep 5 backup files
- Automatic rollover on size limit

#### Disk Monitor: `utils/disk_monitor.py`

**Responsibility**: Monitor disk space, trigger pause on low space

**Logic**:

```python
async def check_disk_space(download_dir: Path, min_space_gb: float) -> bool:
    """Check if sufficient disk space available"""
    stat = os.statvfs(download_dir)
    free_space_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)

    if free_space_gb < min_space_gb:
        logger.warning(f"Low disk space: {free_space_gb:.1f}GB < {min_space_gb}GB")
        return False
    return True
```

**Integration**:
- Checked before each download start
- Pauses downloads if threshold breached
- Resumes when space available again

#### Performance Monitor: `utils/performance.py`

**Responsibility**: System resource monitoring

**Metrics**:

```python
def get_system_metrics() -> Dict[str, float]:
    """Get CPU, memory, and disk usage percentages"""
    return {
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_percent': psutil.disk_usage('/').percent,
    }
```

**Display in `/status` command**:
```
CPU: 42.5% | RAM: 58.3% | Disk: 71.2%
```

---

## Data Flow

### Complete Download Flow

```
1. User sends URL
   └─> message_handler.handle_text_message()

2. Validate URL
   └─> validators.is_valid_url(url)

3. Check for duplicates
   └─> deduplication.extract_video_id(url)
   └─> deduplication.normalize_url(url)
   └─> queue_manager.check_duplicate(url_hash, video_id)

4. Add to queue
   └─> queue_manager.add_task(url, video_id, url_hash)
   └─> INSERT INTO tasks VALUES (...)

5. Download manager picks up task
   └─> download_manager._worker()
   └─> queue_manager.fetch_pending_task()
   └─> queue_manager.mark_processing(task.id)

6. Download execution
   └─> download_manager._download(task)
   └─> disk_monitor.check_disk_space()
   └─> yt_dlp.YoutubeDL(ydl_opts).extract_info(url)
   └─> Run in executor (non-blocking)

7. Handle result
   IF success:
      └─> queue_manager.mark_completed(task.id, file_path)
      └─> UPDATE tasks SET status='completed'

   IF failure:
      └─> queue_manager.reschedule_task(task.id, next_attempt, error)
      └─> UPDATE tasks SET status='pending', next_attempt_at=...
      └─> (retry with exponential backoff)
```

### Playlist Expansion Flow

```
User sends: /watch?list=PLxxxxx
   │
   └─> message_handler detects playlist
   │
   └─> handlers/message_handler.extract_playlist_urls()
   │
   └─> yt-dlp extracts playlist entries
   │   (up to MAX_PLAYLIST_VIDEOS=300)
   │
   └─> For each video URL:
       ├─> Deduplication check
       └─> Add to queue
   │
   └─> User notified: "Queued 47 videos from playlist"
```

---

## Async Model

### Event Loop Architecture

```
Main Event Loop (asyncio)
├─ Telegram Application polling
│  └─ Handlers dispatch (command, message)
│
├─ QueueManager.run()
│  └─ Periodic status updates
│  └─ Retry scheduling
│
└─ DownloadManager.run()
   ├─ Worker pool (8 concurrent)
   │  ├─ Worker 1: fetch_task → download → update_queue
   │  ├─ Worker 2: fetch_task → download → update_queue
   │  ├─ ... (up to MAX_CONCURRENT)
   │
   ├─ Pause/Resume control
   └─ System monitoring
```

### Concurrency Patterns

**Pattern 1: Worker Pool**
```python
# Multiple workers running in parallel
async def _worker(self):
    while True:
        task = await self.queue_manager.fetch_pending_task()
        # Only one worker gets each task (atomic fetch)
        await self._download(task)
```

**Pattern 2: Atomic Task Fetch**
```python
async def fetch_pending_task(self) -> Optional[DownloadTask]:
    async with self._lock:  # asyncio.Lock()
        # Update status within lock (atomic)
        await cursor.execute(
            "UPDATE tasks SET status='processing' WHERE status='pending'"
        )
        # Fetch the updated task
        result = await cursor.fetchone()
```

**Pattern 3: Pause/Resume with Events**
```python
self._pause_event = asyncio.Event()  # Not set = paused

# Pause
self._pause_event.clear()

# Resume
self._pause_event.set()

# In worker
if not self._pause_event.is_set():
    await asyncio.sleep(1)
    continue
```

---

## Database Design

### Schema

```sql
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
);

CREATE INDEX IF NOT EXISTS idx_url_hash ON tasks(url_hash);
CREATE INDEX IF NOT EXISTS idx_video_id ON tasks(video_id);
CREATE INDEX IF NOT EXISTS idx_status ON tasks(status);
```

### Task Status Flow

```
pending
   │
   ├─ (download starts) → processing
   │                       ├─ (success) → completed ✓
   │                       └─ (error) → pending (reschedule)
   │
   └─ (reached max attempts) → failed ✗
```

### Database Operations

**Query: Fetch Pending Task**
```sql
SELECT * FROM tasks
WHERE status='pending' AND next_attempt_at <= strftime('%s', 'now')
ORDER BY added_at ASC
LIMIT 1;
```

**Query: Check Duplicate**
```sql
SELECT * FROM tasks
WHERE (url_hash=? OR video_id=?)
AND status IN ('pending', 'processing', 'completed');
```

**Query: Get Status Summary**
```sql
SELECT status, COUNT(*) as count FROM tasks GROUP BY status;
```

**Query: Reschedule Failed**
```sql
UPDATE tasks
SET status='pending', next_attempt_at=?, attempts=attempts+1, updated_at=?
WHERE status='failed' AND attempts < max_retries;
```

---

## Retry and Backoff Strategy

### Exponential Backoff Formula

```
next_retry_time = current_time + (2^attempts * retry_sleep_base)

Example (retry_sleep_base=1s):
Attempt 1: immediate
Attempt 2: 2^1 * 1 = 2 seconds
Attempt 3: 2^2 * 1 = 4 seconds
Attempt 4: 2^3 * 1 = 8 seconds
Attempt 5: 2^4 * 1 = 16 seconds
After 5: marked as FAILED
```

### Implementation

```python
async def reschedule_task(self, task_id: int, error_msg: str):
    """Reschedule failed task with exponential backoff"""
    async with self._lock:
        task = await self.get_task(task_id)

        if task.attempts >= self.config.max_retries:
            # Max retries exceeded
            await cursor.execute(
                "UPDATE tasks SET status='failed', error_message=? WHERE id=?",
                (error_msg, task_id)
            )
        else:
            # Schedule next retry
            next_delay = 2 ** task.attempts * self.config.retry_sleep
            next_attempt = time.time() + next_delay

            await cursor.execute(
                "UPDATE tasks SET status='pending', next_attempt_at=?, "
                "attempts=?, error_message=?, updated_at=? WHERE id=?",
                (next_attempt, task.attempts + 1, error_msg, time.time(), task_id)
            )
```

### Why Exponential Backoff?

1. **Reduce Server Load**: Don't hammer failing URLs immediately
2. **Handle Transient Errors**: Give servers time to recover (rate limits, temporary outages)
3. **Efficient Resource Usage**: Don't waste bandwidth retrying quickly
4. **Avoid IP Bans**: Staggered retries look more like organic traffic

---

## Deduplication System

### Multi-Level Detection

**Level 1: URL Hashing**
```python
normalized = normalize_url(url)  # Remove utm_*, fbclid, etc.
url_hash = hashlib.sha256(normalized.encode()).hexdigest()
# Query: WHERE url_hash = ?
```

**Level 2: Video ID Extraction**
```python
video_id = extract_video_id(url)
# YouTube: extract 'v=' parameter
# Pornhub: extract 'viewkey=' parameter
# Twitter: extract status ID from URL path
# etc.
# Query: WHERE video_id = ?
```

**Level 3: Database Lookup**
```sql
SELECT * FROM tasks
WHERE (url_hash = ? OR video_id = ?)
AND status IN ('pending', 'processing', 'completed');
```

### Supported Platforms

| Platform | ID Extraction | Hash Fallback |
|----------|---------------|---------------|
| YouTube | v= parameter, /shorts/ path | URL hash |
| Pornhub | viewkey parameter | URL hash |
| Xvideos | numeric path parameter | URL hash |
| Twitter/X | status ID from path | URL hash |
| Reddit | post ID from path | URL hash |
| Twitch | channel/video path | URL hash |
| Generic | N/A | URL hash |

### Why Multi-Level?

1. **URL Hash**: Detects exact duplicates and parameter reordering
2. **Video ID**: Detects same content shared via different URLs
3. **Database Lookup**: Handles edge cases and ensures no duplicates

---

## Error Handling

### Error Categories

**Network Errors**:
- Connection timeout
- Connection refused
- DNS resolution failed
- **Action**: Retry with backoff

**Media Availability Errors**:
- Video removed/deleted
- Video private/restricted
- Geoblocked
- **Action**: Mark as failed (don't retry)

**Format/Extraction Errors**:
- No downloadable formats
- Unsupported platform
- **Action**: Mark as failed

**System Errors**:
- Disk full
- Permission denied
- Out of memory
- **Action**: Pause downloads, resume when resolved

### Error Handling in Download Manager

```python
async def _download(self, task: DownloadTask):
    try:
        # Disk space check
        if not await disk_monitor.check_disk_space(...):
            # Pause all downloads
            await self.pause_downloads()
            return (False, None, "Insufficient disk space")

        # yt-dlp execution
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(task.url, False)
            file_path = ydl.prepare_filename(info)
            return (True, file_path, None)

    except yt_dlp.utils.DownloadError as e:
        # Permanent error (video removed, etc)
        if "not available" in str(e) or "removed" in str(e):
            return (False, None, f"Permanent: {str(e)}")
        else:
            # Transient error, retry
            return (False, None, str(e))

    except Exception as e:
        # Unexpected error, retry
        logger.error(f"Download failed for {task.url}: {e}")
        return (False, None, str(e))
```

### Graceful Degradation

- **Single download fails**: Task rescheduled, other downloads continue
- **Disk space low**: All downloads paused, system remains responsive
- **Database unavailable**: Bot can't queue, but existing tasks continue
- **Telegram API down**: Downloads continue, status updates delayed

---

## Performance Optimization

### Concurrency Optimization

**Worker Pool**: Configurable concurrency (default 8)
```env
MAX_CONCURRENT=8  # Adjust based on system capacity
```

**Optimal Range**:
- **Low-end systems** (1-2 GB RAM): 2-4 workers
- **Mid-range systems** (4-8 GB RAM): 4-8 workers
- **High-end systems** (16+ GB RAM): 8-16 workers

### Network Optimization

**Aria2c Integration**:
```python
if config.use_aria2c:
    ydl_opts['external_downloader'] = 'aria2c'
    ydl_opts['external_downloader_args'] = '-x 16 -k 1M'  # 16 connections
```

**Socket Timeout**:
```env
SOCKET_TIMEOUT=30  # Seconds before connection times out
```

### Database Optimization

**Indexing**:
```sql
CREATE INDEX idx_url_hash ON tasks(url_hash);  -- Fast dedup lookup
CREATE INDEX idx_video_id ON tasks(video_id);  -- Platform ID lookup
CREATE INDEX idx_status ON tasks(status);      -- Fast status filtering
```

**Async Operations**:
- All DB operations use `aiosqlite` (non-blocking)
- No synchronous database calls in async functions

### Format Selection Optimization

```python
# Build efficient format string
format = "best[height<=1080]/best"
# This tells yt-dlp:
# 1. Try best video/audio combo at ≤1080p
# 2. Fall back to best available
```

**Skip Unnecessary Codecs**:
```env
SKIP_HLS=true      # Skip HLS adaptive streams
SKIP_DASH=true     # Skip DASH adaptive streams
```
These consume bandwidth extracting manifests without being used.

### Disk I/O Optimization

**Efficient Download Template**:
```python
'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s')
```

**Atomic Move** (if needed):
- yt-dlp handles atomic downloads within target directory

---

## Security Architecture

### Authentication & Authorization

**Telegram Admin Check**:
```python
@admin_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.telegram_admin_ids:
        await update.message.reply_text("⛔ Unauthorized")
        return
```

**Configuration**:
```env
TELEGRAM_ADMIN_IDS=1234567890,9876543210  # Comma-separated user IDs (examples)
```

### Input Validation

**URL Validation**:
```python
# Only http/https schemes allowed
pattern = r'^https?://[^\s]+'

# Prevent command injection
url = url.strip()
```

**File Upload Restrictions**:
```python
# Only .txt files allowed
MessageHandler(filters.Document.FileExtension("txt"), ...)
```

### Sensitive Data Protection

**Bot Token**:
- Stored in `.env` (should never be committed)
- Recommend: `chmod 600 .env`
- Better: Use environment variable at runtime

**Cookies File**:
```
/path/to/project/data/cookies/cookies.txt
```
- Contains website authentication credentials
- Should have restricted permissions
- Path configurable via `COOKIES_FILE` environment variable

**Error Messages**:
- Exceptions not exposed to users
- Generic "Download failed" message shown
- Details logged for debugging

### Database Security

**No SQL Injection**:
- All queries use parameterized statements
- `await cursor.execute("... WHERE id=?", (task_id,))`

**Database File Permissions**:
```
/path/to/project/data/queue/autodl.db
```
- Should be readable/writable by bot user only
- Recommend: `chmod 600 autodl.db`

### Network Security

**TLS/HTTPS**:
- All Telegram API communication via HTTPS
- yt-dlp respects certificates

**Socket Timeout**:
```env
SOCKET_TIMEOUT=30  # Prevent hanging connections
```

---

## Deployment Architecture

### Systemd Integration

**Service File** (`/etc/systemd/system/autodl-bot.service`):
```ini
[Unit]
Description=autodl_enhanced Telegram Download Bot
After=network.target

[Service]
Type=simple
User=autodl
WorkingDirectory=/opt/autodl_enhanced
ExecStart=/opt/autodl_enhanced/venv/bin/python -m src.autodl_bot
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Service Management**:
```bash
sudo systemctl start autodl-bot      # Start service
sudo systemctl stop autodl-bot       # Stop service
sudo systemctl status autodl-bot     # Check status
sudo systemctl enable autodl-bot     # Auto-start on boot
sudo journalctl -u autodl-bot -f     # View live logs
```

### Environment Isolation

**Virtual Environment**:
```bash
/path/to/project/venv/
```

**Benefits**:
- Isolated Python dependencies
- No conflicts with system Python
- Easy version management

---

## Summary

**autodl_enhanced** implements a clean, production-ready architecture with:

1. **Modular Design**: Clear separation of concerns (handlers, managers, utilities)
2. **Async Throughout**: Leverages Python asyncio for efficient concurrency
3. **Persistent Queue**: SQLite-based with atomic operations and proper indexing
4. **Intelligent Retry**: Exponential backoff prevents server overload
5. **Smart Deduplication**: Multi-level detection across 15+ platforms
6. **Resource Monitoring**: Disk space, CPU, memory tracking
7. **Security**: Admin-only access, input validation, sensitive data protection
8. **Production Ready**: Systemd integration, rotating logs, error handling
9. **Extensible**: Clean interfaces for adding new features

This architecture scales from low-end systems (2 workers) to high-end servers (16+ workers) without code changes.
