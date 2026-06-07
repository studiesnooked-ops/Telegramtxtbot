"""
Simple async queue manager for tracking download jobs per user.
Provides concurrency control and per-user statistics.
"""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bot.queue")


@dataclass
class DownloadJob:
    job_id: str
    user_id: int
    urls: List[str]
    chat_id: int
    created_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    cancelled: bool = False


class QueueManager:
    """Tracks active/queued download jobs across users."""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._semaphore = asyncio.Semaphore(max_workers)
        self._active: Dict[str, DownloadJob] = {}
        self._queued: Dict[str, DownloadJob] = {}
        self._user_active: Dict[int, int] = defaultdict(int)
        self._user_queued: Dict[int, int] = defaultdict(int)
        self._completed_today: Dict[int, int] = defaultdict(int)
        self._last_reset_date = date.today()
        self._lock = asyncio.Lock()

    def _reset_daily_if_needed(self):
        today = date.today()
        if today != self._last_reset_date:
            self._completed_today.clear()
            self._last_reset_date = today

    async def acquire(self, job: DownloadJob) -> bool:
        """Returns True when the job can run (semaphore acquired)."""
        async with self._lock:
            self._queued[job.job_id] = job
            self._user_queued[job.user_id] += 1

        await self._semaphore.acquire()

        async with self._lock:
            self._queued.pop(job.job_id, None)
            self._user_queued[job.user_id] = max(0, self._user_queued[job.user_id] - 1)

            if job.cancelled:
                self._semaphore.release()
                return False

            self._active[job.job_id] = job
            self._user_active[job.user_id] += 1

        return True

    async def release(self, job: DownloadJob):
        async with self._lock:
            self._active.pop(job.job_id, None)
            self._user_active[job.user_id] = max(0, self._user_active[job.user_id] - 1)
            self._reset_daily_if_needed()
            self._completed_today[job.user_id] += 1
        self._semaphore.release()

    def cancel_user_jobs(self, user_id: int) -> int:
        count = 0
        for job in list(self._queued.values()):
            if job.user_id == user_id and not job.cancelled:
                job.cancelled = True
                count += 1
        for job in list(self._active.values()):
            if job.user_id == user_id and not job.cancelled:
                job.cancelled = True
                count += 1
        return count

    def get_stats(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        self._reset_daily_if_needed()
        return {
            "global_active":  len(self._active),
            "global_queued":  len(self._queued),
            "max_workers":    self.max_workers,
            "user_active":    self._user_active.get(user_id, 0) if user_id else 0,
            "user_queued":    self._user_queued.get(user_id, 0) if user_id else 0,
            "user_completed": self._completed_today.get(user_id, 0) if user_id else 0,
        }

    async def shutdown(self):
        logger.info("QueueManager shutting down. Cancelling %d queued job(s).", len(self._queued))
        for job in self._queued.values():
            job.cancelled = True
