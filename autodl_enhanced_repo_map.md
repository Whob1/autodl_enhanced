# Repository Map

```markdown
/ (autodl_enhanced)
├── .claude/
    └── settings.local.json (JSON)
├── __pycache__/
├── config/
├── data/
    ├── cookies/
    │   └── cookies.txt (Text)
    ├── logs/
    │   ├── autodl-bot.log.1 (None)
    │   ├── autodl-bot.log.2 (None)
    │   ├── autodl-bot.log.3 (None)
    │   ├── autodl-bot.log.4 (None)
    │   └── autodl-bot.log.5 (None)
    └── queue/
├── scripts/
    └── install.sh (Shell)
├── src/
    ├── __pycache__/
    ├── handlers/
    │   ├── __pycache__/
    │   ├── __init__.py (Python)
    │   │   └── Description: Package for Telegram handlers.
    │   ├── command_handler.py (Python)
    │   │   ├── Description: Handles Telegram bot commands like /start, /queue, /status, /pause, /resume, and /clear using bot_data objects.
    │   │   ├── Developer Consideration: "Relies on application.bot_data for queue_manager and download_manager; handlers must ensure these are properly initialized before command execution."
    │   │   ├── Maintenance Flag: Stable
    │   │   ├── Architectural Role: Service Layer
    │   │   ├── Code Quality Score: 8/10
    │   │   ├── Refactoring Suggestions: "Consider implementing a command registry pattern to dynamically load handlers and reduce repetitive boilerplate code."
    │   │   ├── Security Assessment: "Ensure that command handlers validate user permissions before executing privileged operations like /pause or /resume."
    │   │   ├── Critical Dependencies:
    │   │   ├──   - telegram: Provides core Telegram bot functionality and update handling.
    │   │   ├──   - utils.performance: Used for retrieving system performance metrics in /status command.
    │   │   └──   - utils.cookie_manager.CookieManager: Required for cookie management in download operations.
    │   └── message_handler.py (Python)
    │       ├── Description: Handles Telegram message events, extracting URLs from text and .txt document uploads for queue processing.
    │       ├── Developer Consideration: "Text files are processed line-by-line, but only the first 1000 lines are considered to prevent memory exhaustion from large files."
    │       ├── Maintenance Flag: Volatile
    │       ├── Architectural Role: Service Layer
    │       ├── Code Quality Score: 7/10
    │       ├── Refactoring Suggestions: "Add input validation for file sizes and line counts to prevent potential DoS attacks through malformed or excessively large text files."
    │       ├── Security Assessment: "Ensure that uploaded .txt files are sanitized and that URL extraction doesn't inadvertently expose sensitive information or allow command injection."
    │       ├── Critical Dependencies:
    │       ├──   - telegram: Provides core Telegram bot functionality including Update and Context objects.
    │       └──   - download_manager: Required for playlist URL detection and extraction capabilities.
    ├── utils/
    │   ├── __pycache__/
    │   ├── __init__.py (Python)
    │   │   └── Description: Utility functions used throughout the project.
    │   ├── cookie_manager.py (Python)
    │   │   ├── Description: Cookie management utilities for yt-dlp. Handles reading, merging, and appending cookies in Netscape format.
    │   │   ├── Developer Consideration: "Cookie files are parsed line-by-line without validation; malformed entries may cause yt-dlp to fail silently during downloads."
    │   │   ├── Maintenance Flag: Stable
    │   │   ├── Architectural Role: Utility
    │   │   ├── Code Quality Score: 7/10
    │   │   ├── Refactoring Suggestions: "Add input validation for cookie file formats and implement a try-except block around file operations to gracefully handle permission errors or corrupted files."
    │   │   ├── Security Assessment: "Cookie files contain authentication tokens; ensure they are stored with appropriate file permissions (600) and never logged or exposed in error messages."
    │   │   ├── Critical Dependencies:
    │   │   ├──   - os: Required for file system operations like checking if cookie files exist and reading their contents.
    │   │   └──   - pathlib.Path: Used for robust path manipulation and file location handling across different operating systems.
    │   ├── deduplication.py (Python)
    │   │   ├── Description: Provides URL normalization and duplicate detection utilities to prevent downloading the same video multiple times.
    │   │   ├── Developer Consideration: "URL normalization handles query parameter reordering but may not resolve all canonical URL variations; consider platform-specific URL schemes for better deduplication."
    │   │   ├── Maintenance Flag: Stable
    │   │   ├── Architectural Role: Utility
    │   │   ├── Code Quality Score: 8/10
    │   │   ├── Refactoring Suggestions: "Consider adding a cache layer for computed URL hashes to improve performance during frequent duplicate checks."
    │   │   ├── Security Assessment: "None"
    │   │   ├── Critical Dependencies:
    │   │   └──   - hashlib: Used for generating consistent hashes of URLs and filenames to identify duplicates.
    │   ├── disk_monitor.py (Python)
    │   │   ├── Description: Provides disk monitoring utilities to check available space and detect low disk conditions in the download directory.
    │   │   ├── Developer Consideration: "The disk space check uses psutil which may fail silently on systems with restricted filesystem access; implement fallback mechanisms for production deployments."
    │   │   ├── Maintenance Flag: Stable
    │   │   ├── Architectural Role: Utility
    │   │   ├── Code Quality Score: 8/10
    │   │   ├── Refactoring Suggestions: "Add unit tests for edge cases like negative disk space values or invalid paths to improve reliability."
    │   │   ├── Security Assessment: "None"
    │   │   ├── Critical Dependencies:
    │   │   └──   - psutil: Provides cross-platform disk space monitoring capabilities essential for the low disk detection logic.
    │   ├── logger.py (Python)
    │   │   ├── Description: Provides unified logging configuration with console and file handlers for the Telegram bot application.
    │   │   ├── Developer Consideration: "The logger setup depends on environment-based LOG_LEVEL; ensure config_manager properly loads this before calling setup_logging to avoid defaulting to WARNING level."
    │   │   ├── Maintenance Flag: Stable
    │   │   ├── Architectural Role: Utility
    │   │   ├── Code Quality Score: 8/10
    │   │   ├── Refactoring Suggestions: "Consider adding log level validation to prevent invalid LOG_LEVEL values from causing unexpected behavior during setup."
    │   │   ├── Security Assessment: "None"
    │   │   ├── Critical Dependencies:
    │   │   ├──   - logging: Core Python module for all logging functionality and handler management.
    │   │   └──   - logging.handlers.RotatingFileHandler: Enables log rotation to prevent excessive disk usage.
    │   ├── performance.py (Python)
    │   │   ├── Description: System performance monitoring utilities exposing CPU, memory, and disk usage metrics for Telegram bot status reporting.
    │   │   ├── Developer Consideration: "psutil may raise RuntimeError on some systems with restricted process access; implement graceful fallbacks or error handling in production deployments."
    │   │   ├── Maintenance Flag: Stable
    │   │   ├── Architectural Role: Utility
    │   │   ├── Code Quality Score: 8/10
    │   │   ├── Refactoring Suggestions: "Add type hints to function parameters and return values for better IDE support and documentation clarity."
    │   │   ├── Security Assessment: "None"
    │   │   ├── Critical Dependencies:
    │   │   └──   - psutil: Provides cross-platform system information including CPU, memory, and disk usage metrics essential for performance monitoring.
    │   └── validators.py (Python)
    │       ├── Description: Validation utilities for the Enhanced AutoDL Telegram Bot, providing URL validation and extraction functionality.
    │       ├── Developer Consideration: "The is_valid_url function uses a basic regex pattern that may not catch all edge cases; consider strengthening validation for production use to prevent malformed URLs from entering the download queue."
    │       ├── Maintenance Flag: Stable
    │       ├── Architectural Role: Utility
    │       ├── Code Quality Score: 7/10
    │       ├── Refactoring Suggestions: "Add comprehensive test cases for various URL formats including edge cases like malformed URLs, international domain names, and URLs with special characters to ensure robust validation."
    │       ├── Security Assessment: "Input validation is crucial for preventing injection attacks; ensure extracted URLs are properly sanitized before being passed to yt-dlp to avoid command injection vulnerabilities."
    │       ├── Critical Dependencies:
    │       ├──   - re: Provides regular expression matching for URL validation patterns.
    │       └──   - urllib.parse: Handles URL parsing and validation of URL components like scheme and netloc.
    ├── __init__.py (Python)
    │   └── Description: Enhanced AutoDL Telegram Bot source package.
    ├── autodl_bot.py (Python)
    │   ├── Description: Entry point for the Enhanced AutoDL Telegram Bot, orchestrating config loading, logging, queue management, and Telegram bot initialization.
    │   ├── Developer Consideration: "The application's startup sequence is tightly coupled to environment variables and config file parsing; any misconfiguration here will prevent the bot from running entirely."
    │   ├── Maintenance Flag: Stable
    │   ├── Architectural Role: Entrypoint
    │   ├── Code Quality Score: 8/10
    │   ├── Refactoring Suggestions: "Consider separating the bot initialization logic into a dedicated factory function to improve testability and reduce the main function's cognitive load."
    │   ├── Security Assessment: "The bot relies on environment variables for sensitive data like Telegram tokens; ensure these are properly secured and not exposed in logs or error messages."
    │   ├── Critical Dependencies:
    │   ├──   - telegram.ext.Application: Core Telegram bot framework for handling updates and dispatching events.
    │   ├──   - config_manager.load_config: Initializes application configuration from environment and file sources.
    │   ├──   - queue_manager.QueueManager: Manages persistent task queue state and operations.
    │   └──   - download_manager.DownloadManager: Handles concurrent downloads and retry logic for queued items.
    ├── config_manager.py (Python)
    │   ├── Description: Loads and validates environment variables for the Enhanced AutoDL Telegram Bot configuration.
    │   ├── Developer Consideration: "Relies on python-dotenv for .env file loading; ensure the .env file exists in the project root or defaults will be used without warning."
    │   ├── Maintenance Flag: Stable
    │   ├── Architectural Role: Configuration
    │   ├── Code Quality Score: 7/10
    │   ├── Refactoring Suggestions: "Add explicit validation for required environment variables and raise ConfigurationError with descriptive messages for missing or invalid values."
    │   ├── Security Assessment: "Environment variables containing sensitive data like Telegram tokens should be validated and sanitized to prevent injection attacks; consider implementing a secure loading mechanism."
    │   ├── Critical Dependencies:
    │   └──   - python-dotenv: Enables loading environment variables from .env files, which is essential for configuration management.
    ├── download_manager.py (Python)
    │   ├── Description: Manages concurrent yt-dlp downloads with pause/resume, retry logic, and real-time progress tracking.
    │   ├── Developer Consideration: "The download manager relies on yt-dlp's internal state management; concurrent downloads may cause race conditions if not properly synchronized with the queue manager's task states."
    │   ├── Maintenance Flag: Volatile
    │   ├── Architectural Role: Service Layer
    │   ├── Code Quality Score: 7/10
    │   ├── Refactoring Suggestions: "Extract the yt-dlp options configuration into a dedicated function or class to improve testability and allow for easier configuration updates without modifying the core download logic."
    │   ├── Security Assessment: "Input validation should be strengthened to prevent command injection via malicious URLs; ensure all URLs are properly sanitized before being passed to yt-dlp."
    │   ├── Critical Dependencies:
    │   ├──   - yt-dlp: Core dependency for all download operations; handles URL extraction, format selection, and actual file downloading.
    │   └──   - queue_manager.QueueManager: Essential for retrieving download tasks and updating their status; ensures consistent task lifecycle management.
    └── queue_manager.py (Python)
        ├── Description: SQLite-backed queue manager for the Enhanced AutoDL Telegram Bot, handling persistent task storage with retry logic.
        ├── Developer Consideration: "Uses aiosqlite for async database operations; ensure proper connection handling to prevent database locks during concurrent access."
        ├── Maintenance Flag: Stable
        ├── Architectural Role: Data Model
        ├── Code Quality Score: 8/10
        ├── Refactoring Suggestions: "Consider adding database schema versioning to handle future migration needs when the queue structure evolves."
        ├── Security Assessment: "Input validation is minimal; ensure all URLs are properly sanitized before insertion to prevent SQL injection in future extensions."
        ├── Critical Dependencies:
        └──   - aiosqlite: Enables asynchronous SQLite database operations required for non-blocking queue management.
├── tests/
    ├── __pycache__/
    ├── __init__.py (Python)
    │   └── Description: Test package for the Enhanced AutoDL Telegram Bot.
    ├── test_download_manager.py (Python)
    │   ├── Description: Unit tests for the DownloadManager simulating download success/failure scenarios without actual data fetching.
    │   ├── Developer Consideration: "Relies on monkeypatching to override _download method; test coverage depends entirely on mocked yt-dlp behavior rather than real downloads."
    │   ├── Maintenance Flag: Volatile
    │   ├── Architectural Role: Test Suite
    │   ├── Code Quality Score: 7/10
    │   ├── Refactoring Suggestions: "Add parameterized tests for different download failure scenarios to improve coverage of error handling paths in DownloadManager."
    │   ├── Security Assessment: "None - tests only simulate download behavior and do not process external inputs or interact with real systems."
    │   ├── Critical Dependencies:
    │   ├──   - pytest: Provides the testing framework and assertion capabilities for unit testing.
    │   └──   - aiosqlite: Required for database operations in the QueueManager under test.
    └── test_queue_manager.py (Python)
        ├── Description: Unit tests for the QueueManager, verifying SQLite-backed queue operations with temporary database files.
        ├── Developer Consideration: "Uses temporary database files to prevent data clobbering; tests must properly clean up these temp files to avoid disk space accumulation."
        ├── Maintenance Flag: Stable
        ├── Architectural Role: Test Suite
        ├── Code Quality Score: 8/10
        ├── Refactoring Suggestions: "Consider parameterizing test cases with different queue states and operations to improve coverage without duplicating test logic."
        ├── Security Assessment: "None - tests operate on temporary files and don't handle sensitive data; however, ensure temp file permissions are secure to prevent unauthorized access."
        ├── Critical Dependencies:
        └──   - aiosqlite: Enables async SQLite operations for queue persistence; essential for test isolation and database interaction.
├── venv/
├── ARCHITECTURE.md (Markdown)
├── COMPONENTS.md (Markdown)
├── README.md (Markdown)
├── autodl_enhanced.zip (None)
├── autodl_enhanced_20251020_075150.zip (None)
├── debug_queue.py (Python)
│   ├── Description: Debug script to inspect and display the current state and contents of the SQLite download queue database.
│   ├── Developer Consideration: "Direct database access bypasses normal queue manager operations; changes made directly to the database may cause inconsistencies with the application's internal state tracking."
│   ├── Maintenance Flag: Stable
│   ├── Architectural Role: Utility Script
│   ├── Code Quality Score: 6/10
│   ├── Refactoring Suggestions: "Add proper error handling for database connection failures and implement a more robust display format for queue entries that includes task metadata and status information."
│   ├── Security Assessment: "None"
│   ├── Critical Dependencies:
│   └──   - config_manager: Provides database path configuration needed to locate and access the SQLite queue database file.
├── requirements.txt (Text)
├── test_download.py (Python)
│   ├── Description: Test script to add a URL to the download queue for manual verification of queue functionality.
│   ├── Developer Consideration: "Directly manipulates the queue database without going through the normal bot command flow; changes are immediately visible in the queue but bypass standard validation and deduplication logic."
│   ├── Maintenance Flag: Volatile
│   ├── Architectural Role: Test Utility
│   ├── Code Quality Score: 6/10
│   ├── Refactoring Suggestions: "Add input validation and URL normalization before queue insertion to match production behavior and improve test reliability."
│   ├── Security Assessment: "None - this is a test script that directly accesses the queue database and does not process external inputs or handle sensitive data."
│   ├── Critical Dependencies:
│   ├──   - src.config_manager: Loads configuration needed for database path and queue settings.
│   └──   - src.queue_manager: Provides the queue management interface for adding items to the download queue.
├── test_playlist.py (Python)
│   ├── Description: Test script to add a playlist URL to the download queue for manual verification of playlist processing functionality.
│   ├── Developer Consideration: "Bypasses normal bot command validation and deduplication logic; directly manipulates the queue database which may cause state inconsistencies if not properly synchronized with the application's internal queue manager."
│   ├── Maintenance Flag: Volatile
│   ├── Architectural Role: Test Script
│   ├── Code Quality Score: 6/10
│   ├── Refactoring Suggestions: "Convert to proper unit test using pytest fixtures to mock queue manager dependencies and ensure test isolation without direct database manipulation."
│   ├── Security Assessment: "Direct database access could expose the application to data integrity issues; ensure proper transaction handling and validation before inserting test data."
│   ├── Critical Dependencies:
│   └──   - src.download_manager: Provides playlist URL detection and extraction utilities essential for test functionality.
├── test_playlist_extraction.py (Python)
│   ├── Description: Test script for debugging playlist extraction functionality with yt-dlp.
│   ├── Developer Consideration: "Directly imports and uses yt-dlp's extract_info method without the application's queue or validation layers; may not reflect real-world behavior accurately."
│   ├── Maintenance Flag: Volatile
│   ├── Architectural Role: Test Utility
│   ├── Code Quality Score: 4/10
│   ├── Refactoring Suggestions: "Add proper error handling and logging around yt-dlp calls to make debugging more effective; consider parameterizing the test URL for easier reuse."
│   ├── Security Assessment: "Script directly executes yt-dlp on provided URLs without validation; could be exploited if run with untrusted input to execute arbitrary commands or access unauthorized resources."
│   ├── Critical Dependencies:
│   └──   - yt_dlp: Provides core playlist extraction and URL information parsing capabilities essential for this test script's functionality.
└── test_playlist_simple.py (Python)
    ├── Description: Simple test script for detecting and extracting playlist URLs using yt-dlp's extraction capabilities.
    ├── Developer Consideration: "Bypasses application validation and deduplication layers; direct yt-dlp integration may expose underlying library limitations or unexpected behavior in edge cases."
    ├── Maintenance Flag: Volatile
    ├── Architectural Role: Test Utility
    ├── Code Quality Score: 6/10
    ├── Refactoring Suggestions: "Add input validation and error handling for yt-dlp extraction to make the script more robust against malformed URLs or network issues."
    ├── Security Assessment: "Direct yt-dlp usage without application-level validation may process untrusted URLs; ensure proper sandboxing or input sanitization if used in production contexts."
    ├── Critical Dependencies:
    └──   - yt_dlp: Primary dependency for URL playlist detection and metadata extraction; directly impacts test accuracy and reliability.
└────────────── 
```
