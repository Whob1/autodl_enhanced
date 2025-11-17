# autodl_enhanced

A feature-rich Telegram bot for automatically downloading media from various platforms including YouTube, streaming services, and social media. Built with Python 3.10+ and leveraging yt-dlp for media extraction.

## Quick Overview

**autodl_enhanced** is an asynchronous Telegram bot that:
- Downloads media from 100+ platforms (YouTube, Twitch, Instagram, TikTok, etc.)
- Manages downloads using a persistent SQLite queue with automatic retry logic
- Handles concurrent downloads with configurable worker pools
- Monitors system resources (disk space, CPU, memory) and intelligently pauses/resumes
- Detects and prevents duplicate downloads using multi-level deduplication
- Expands playlists up to 300 videos per request
- Provides real-time status updates via Telegram commands

## Key Features

### Core Capabilities
- **Multi-Platform Support**: YouTube, Twitch, Instagram, TikTok, Reddit, Twitter, adult content sites, and 100+ more
- **Persistent Queue**: Tasks survive application restarts via SQLite database
- **Intelligent Retry**: Exponential backoff for failed downloads (max 5 attempts by default)
- **Duplicate Detection**: Multi-level detection using URL hashing and video IDs
- **Concurrent Downloads**: Up to 8 parallel downloads (configurable)
- **Playlist Expansion**: Automatically extracts up to 300 videos from playlists
- **Quality Control**: Configurable quality settings (max 1080p default), format preferences (MP4)

### System Intelligence
- **Disk Space Monitoring**: Automatically pauses downloads if free space drops below threshold (50 GB default)
- **System Resource Tracking**: Real-time CPU, memory, and disk usage reporting
- **Performance Metrics**: Download speed, ETA, active task monitoring
- **Smart Aria2c Integration**: Optional high-speed downloader support for enhanced performance

### User Control
- **Telegram Commands**: /start, /queue, /status, /pause, /resume, /retry, /clear
- **Batch Downloads**: Upload .txt files with multiple URLs
- **Playlist Handling**: Automatic playlist URL detection and expansion
- **Admin Controls**: Admin-only access with configurable admin IDs

## Project Structure

```
autodl_enhanced/
├── src/
│   ├── autodl_bot.py           # Entry point and bot initialization
│   ├── config_manager.py       # Configuration loader
│   ├── queue_manager.py        # Persistent task queue (SQLite)
│   ├── download_manager.py     # Download orchestration and worker pool
│   ├── handlers/               # Telegram event handlers
│   │   ├── command_handler.py  # /start, /queue, /status, etc.
│   │   └── message_handler.py  # URL and file message handling
│   └── utils/
│       ├── logger.py           # Logging configuration
│       ├── validators.py       # URL validation and extraction
│       ├── deduplication.py    # URL normalization and duplicate detection
│       ├── disk_monitor.py     # Disk space monitoring
│       └── performance.py      # System resource monitoring
├── config/
│   └── .env                    # Configuration template
├── data/
│   ├── cookies/                # Website authentication cookies
│   ├── logs/                   # Application logs
│   └── queue/                  # SQLite database
├── tests/                      # Unit tests (pytest)
├── scripts/
│   └── install.sh              # Setup and systemd installation
├── requirements.txt            # Python dependencies
└── .env                        # Active configuration
```

## Installation

### Prerequisites
- Python 3.10+
- Linux system (systemd)
- ffmpeg (for media processing)
- aria2 (optional, for faster downloads)

### Quick Setup

1. **Clone and enter directory**:
   ```bash
   cd autodl_enhanced
   ```

2. **Run installation script**:
   ```bash
   bash scripts/install.sh
   ```

   This will:
   - Install system dependencies (python3-venv, aria2, ffmpeg)
   - Create Python virtual environment
   - Install Python packages (requirements.txt)
   - Configure systemd service
   - Start the bot service

3. **Configure bot**:
   ```bash
   cp config/.env .env
   nano .env
   ```

   Set these required values:
   - `TELEGRAM_BOT_TOKEN`: Get from BotFather on Telegram
   - `TELEGRAM_ADMIN_IDS`: Your Telegram user ID
   - `DOWNLOAD_DIR`: Where to save downloaded media

4. **Start the bot**:
   ```bash
   sudo systemctl start autodl-bot
   sudo systemctl enable autodl-bot  # Auto-start on boot
   ```

5. **Check status**:
   ```bash
   sudo systemctl status autodl-bot
   sudo journalctl -u autodl-bot -f  # View live logs
   ```

## Configuration

All configuration is managed via `.env` file. Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| TELEGRAM_BOT_TOKEN | - | **Required**: Bot token from BotFather |
| TELEGRAM_ADMIN_IDS | - | Comma-separated admin user IDs |
| DOWNLOAD_DIR | /path/to/downloads | Download destination directory |
| MAX_CONCURRENT | 8 | Parallel downloads |
| USE_ARIA2C | true | Use aria2c for faster downloads |
| MIN_DISK_SPACE_GB | 50 | Pause if free space drops below (GB) |
| MAX_PLAYLIST_VIDEOS | 300 | Max videos per playlist expansion |
| LOG_LEVEL | INFO | Logging verbosity (DEBUG/INFO/WARNING/ERROR) |
| MAX_RETRIES | 5 | Max download retry attempts |
| MAX_VIDEO_QUALITY | 1080p | Maximum quality to download |
| PREFERRED_FORMAT | mp4 | Format preference (mp4, mkv, etc.) |
| COOKIES_FILE | data/cookies/cookies.txt | Cookie file for authentication |
| SOCKET_TIMEOUT | 30 | Network timeout (seconds) |
| SKIP_HLS | true | Skip HLS streams |
| SKIP_DASH | true | Skip DASH streams |

## Usage

### Telegram Commands

**Starting the bot**:
```
/start
```
Displays welcome message and available commands.

**Checking download queue**:
```
/queue
```
Shows all pending, processing, and recently completed tasks.

**Getting status**:
```
/status
```
Displays:
- Current system metrics (CPU, memory, disk usage)
- Queue statistics (pending, processing, completed, failed)
- Top 5 active downloads with progress

**Pausing downloads**:
```
/pause
```
Pauses all active downloads.

**Resuming downloads**:
```
/resume
```
Resumes paused downloads.

**Retrying failed tasks**:
```
/retry
```
Attempts to re-download all failed tasks.

**Clearing queue**:
```
/clear
```
Removes all completed and failed tasks from queue.

### Sending URLs

**Single URL**:
Send any URL directly to the bot:
```
https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

**Multiple URLs**:
Upload a `.txt` file with one URL per line:
```
https://www.youtube.com/watch?v=...
https://www.youtube.com/watch?v=...
https://www.youtube.com/playlist?list=...
```

**Playlist URLs**:
Send a playlist URL, and the bot automatically expands it:
```
https://www.youtube.com/playlist?list=PLxxx
```
Extracts up to 300 videos and queues them.

## How It Works

### Data Flow

1. **User sends URL** → Message handler validates and extracts URL
2. **Duplicate detection** → Checks if already queued/completed via URL hash and video ID
3. **Queue manager** → Adds task to SQLite database with `pending` status
4. **Download manager** → Worker pool picks up pending tasks
5. **Extraction** → yt-dlp extracts media info and begins download
6. **Monitoring** → System monitors disk space, retries on failure with backoff
7. **Completion** → File saved, task marked `completed`, user notified

### Deduplication Strategy

Multi-level duplicate detection:
- **URL Hash**: SHA256 of normalized URL (removes query parameters)
- **Video ID**: Platform-specific extraction (YouTube ID, pornhub viewkey, etc.)
- **Normalized URL**: Query parameter removal (utm_*, fbclid, gclid)

### Retry Logic

Failed downloads automatically retry with exponential backoff:
- Attempt 1: immediate retry
- Attempt 2: 2^1 * 1s = 2 seconds
- Attempt 3: 2^2 * 1s = 4 seconds
- Attempt 4: 2^3 * 1s = 8 seconds
- Attempt 5: 2^4 * 1s = 16 seconds
- After max retries: marked as `failed`

## Database Schema

SQLite database stores all download tasks:

```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    added_at REAL NOT NULL,              -- Unix timestamp
    updated_at REAL NOT NULL,
    next_attempt_at REAL,                -- Unix timestamp for retry scheduling
    file_path TEXT,                      -- Path to downloaded file
    error_message TEXT,                  -- Last error details
    url_hash TEXT,                       -- SHA256 hash of normalized URL
    video_id TEXT                        -- Platform-specific video ID
);
```

**Task Statuses**:
- `pending`: Waiting to be processed
- `processing`: Currently downloading
- `completed`: Successfully downloaded
- `failed`: Max retries exceeded

## Logging

Logs are stored in `data/logs/` with rotation:
- Current log: `autodl-bot.log`
- Backup logs: `autodl-bot.log.1` through `autodl-bot.log.4`
- Max file size: 10 MB per file
- Max backups: 5 files

View live logs:
```bash
sudo journalctl -u autodl-bot -f
tail -f data/logs/autodl-bot.log
```

Configure log level in `.env` with `LOG_LEVEL` (DEBUG/INFO/WARNING/ERROR).

## Testing

Run unit tests:
```bash
pytest tests/
pytest tests/test_queue_manager.py -v
pytest tests/test_download_manager.py -v
```

## Troubleshooting

### Bot Not Responding to Messages

1. Check bot is running:
   ```bash
   sudo systemctl status autodl-bot
   ```

2. Check logs for errors:
   ```bash
   sudo journalctl -u autodl-bot -f
   ```

3. Verify TELEGRAM_BOT_TOKEN is correct:
   ```bash
   grep TELEGRAM_BOT_TOKEN .env
   ```

4. Ensure admin ID is correct:
   ```bash
   grep TELEGRAM_ADMIN_IDS .env
   ```

### Downloads Not Starting

1. Check download directory exists and is writable:
   ```bash
   ls -la $(grep DOWNLOAD_DIR .env | cut -d'=' -f2)
   ```

2. Check disk space:
   ```bash
   df -h
   ```

3. Verify yt-dlp is installed:
   ```bash
   source venv/bin/activate && python -m yt_dlp --version
   ```

### High Memory Usage

- Reduce `MAX_CONCURRENT` in `.env` to lower parallel downloads
- Check queue size: `/queue` command
- Clear completed tasks: `/clear` command

### Download Failures

1. Check error message in `/queue`
2. Verify URL is supported by yt-dlp: `yt-dlp --list-extractors`
3. Check cookies file if downloading from authenticated sites
4. Review logs for specific error details

## Performance Tuning

### For High Throughput
```env
MAX_CONCURRENT=16
USE_ARIA2C=true
SOCKET_TIMEOUT=45
```

### For Low Resource Systems
```env
MAX_CONCURRENT=2
SKIP_HLS=true
SKIP_DASH=true
MIN_DISK_SPACE_GB=10
```

### For Stable Operations
```env
MAX_CONCURRENT=4
MAX_RETRIES=3
MIN_DISK_SPACE_GB=100
```

## Architecture Highlights

**Async Architecture**:
- Python asyncio for non-blocking operations
- Concurrent downloads with worker pool pattern
- Async SQLite operations via aiosqlite

**Error Handling**:
- Graceful degradation on yt-dlp errors
- Database consistency with transaction management
- Telegram API error recovery

**System Integration**:
- Systemd service for automatic startup
- Rotating logs for manageable disk usage
- Resource monitoring to prevent system overload

## Security Considerations

**Sensitive Data**:
- Keep `.env` file private (contains bot token)
- Restrict file permissions: `chmod 600 .env`
- Consider using environment variables instead of file on production systems

**Input Validation**:
- All URLs validated against whitelist patterns
- File uploads restricted to .txt files only
- URL schemes limited to http/https

**Authentication**:
- Bot access limited to configured admin IDs
- All commands require admin authentication

## Dependencies

| Package | Purpose | Version |
|---------|---------|---------|
| python-telegram-bot | Telegram bot API | 21.5 |
| yt-dlp | Media downloader | >= 2024.10.7 |
| aiosqlite | Async SQLite | >= 0.20.0 |
| psutil | System monitoring | >= 5.9.6 |
| aiofiles | Async file I/O | >= 23.2.1 |
| python-dotenv | Environment config | >= 1.0.1 |

## Development

### Code Quality
- Type hints throughout codebase
- Comprehensive docstrings (NumPy style)
- Modular design with separation of concerns
- 22 Python files, ~4,500 LOC

### Testing
- Unit tests with pytest-asyncio
- Mock/monkeypatch for external dependencies
- Async test fixtures for queue/download managers

### Contributing
Ensure code follows existing patterns:
- Use async/await for I/O operations
- Add type hints to all functions
- Include docstrings for public methods
- Run tests before submitting changes

## License

[Specify your license here]

## Support

For issues, bug reports, or feature requests, please check the logs and provide:
1. Error message from logs
2. `.env` settings (excluding bot token)
3. Steps to reproduce
4. Expected vs. actual behavior

## Future Enhancements

- Web dashboard for queue visualization
- Webhook support for faster Telegram updates
- Download scheduling (at specific times)
- Quality-based post-processing (encoding, transcoding)
- Metadata extraction and organization
- Multi-language support
