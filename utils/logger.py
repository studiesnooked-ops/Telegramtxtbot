"""Centralized logging setup."""

import logging
import logging.handlers
import os
import sys
from pathlib import Path


def setup_logger(name: str, log_file: str = None, level: int = logging.INFO) -> logging.Logger:
    """Configure and return a logger with console + rotating file handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger   # already configured

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # File handler (rotating, 5 MB × 3 backups)
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    # Silence noisy third-party loggers
    for noisy in ("httpx", "telegram.ext", "aiohttp"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return logger
