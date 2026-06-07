"""
Configuration management — reads from environment variables.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    # ── Telegram ──────────────────────────────────────────────────────────────
    BOT_TOKEN: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))

    # ── Render / Webhook ──────────────────────────────────────────────────────
    USE_WEBHOOK: bool = field(
        default_factory=lambda: os.getenv("USE_WEBHOOK", "true").lower() == "true"
    )
    RENDER_EXTERNAL_URL: Optional[str] = field(
        default_factory=lambda: os.getenv("RENDER_EXTERNAL_URL")
    )
    WEBHOOK_SECRET: str = field(
        default_factory=lambda: os.getenv("WEBHOOK_SECRET", "supersecrettoken123")
    )
    PORT: int = field(default_factory=lambda: int(os.getenv("PORT", "8080")))

    # ── Processing ────────────────────────────────────────────────────────────
    MAX_FILE_SIZE_MB: int = field(
        default_factory=lambda: int(os.getenv("MAX_FILE_SIZE_MB", "20"))
    )
    MAX_WORKERS: int = field(
        default_factory=lambda: int(os.getenv("MAX_WORKERS", "4"))
    )
    MAX_URLS_PER_FILE: int = field(
        default_factory=lambda: int(os.getenv("MAX_URLS_PER_FILE", "500"))
    )
    BATCH_SEND_DELAY: float = field(
        default_factory=lambda: float(os.getenv("BATCH_SEND_DELAY", "0.5"))
    )

    # ── Directories ───────────────────────────────────────────────────────────
    UPLOAD_DIR: str = field(default_factory=lambda: os.getenv("UPLOAD_DIR", "uploads"))
    DOWNLOAD_DIR: str = field(
        default_factory=lambda: os.getenv("DOWNLOAD_DIR", "downloads")
    )
    LOG_DIR: str = field(default_factory=lambda: os.getenv("LOG_DIR", "logs"))

    # ── Admin ─────────────────────────────────────────────────────────────────
    ADMIN_IDS: list = field(
        default_factory=lambda: [
            int(x)
            for x in os.getenv("ADMIN_IDS", "").split(",")
            if x.strip().isdigit()
        ]
    )

    def validate(self):
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN environment variable is required!")
        if self.USE_WEBHOOK and not self.RENDER_EXTERNAL_URL:
            raise ValueError(
                "RENDER_EXTERNAL_URL is required when USE_WEBHOOK=true. "
                "Set it to your Render service URL."
            )
        for d in [self.UPLOAD_DIR, self.DOWNLOAD_DIR, self.LOG_DIR]:
            os.makedirs(d, exist_ok=True)

    @property
    def webhook_url(self) -> str:
        base = self.RENDER_EXTERNAL_URL.rstrip("/")
        return f"{base}/webhook/{self.WEBHOOK_SECRET}"

    @property
    def max_file_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024
