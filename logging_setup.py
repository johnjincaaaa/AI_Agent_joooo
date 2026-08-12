"""
Logging configuration for Jingent AI.

Provides structured, file-based logging with rotation.
Usage: call `setup_logging()` once at app startup (main.py).
"""
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from datetime import datetime


DEFAULT_LOG_DIR = Path("logs")


def setup_logging(
    log_dir: Path | str | None = None,
    level: int = logging.INFO,
    enable_console: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB per file
    backup_count: int = 5,
) -> Path:
    """
    Configure logging globally.

    - Rotating file handlers for INFO and ERROR separately.
    - Structured format with timestamp, logger name, level, and message.
    - Console handler for development convenience.

    Returns the log directory path.
    """
    log_dir = Path(log_dir or DEFAULT_LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid double-registering handlers on hot-reload
    if root_logger.handlers:
        root_logger.handlers.clear()

    # ── Format ──────────────────────────────────────────────
    # Example: 2026-08-08 15:30:22,456 | INFO    | uvicorn.info | server started
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── Combined (INFO+) file ───────────────────────────────
    info_file = log_dir / "app.log"
    info_handler = logging.handlers.RotatingFileHandler(
        info_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(fmt)
    root_logger.addHandler(info_handler)

    # ── Error-only file ─────────────────────────────────────
    error_file = log_dir / "error.log"
    error_handler = logging.handlers.RotatingFileHandler(
        error_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(fmt)
    root_logger.addHandler(error_handler)

    # ── Console ─────────────────────────────────────────────
    if enable_console:
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(level)
        console.setFormatter(fmt)
        root_logger.addHandler(console)

    # Silence noisy libraries
    for noisy in ("httpx", "urllib3", "selenium", "playwright"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Startup banner in log
    logging.info("=" * 60)
    logging.info(f"[Startup] Jingent AI launched at {datetime.now().isoformat(timespec='seconds')}")
    logging.info(f"[Startup] Log directory: {log_dir.resolve()}")
    logging.info("=" * 60)

    return log_dir
