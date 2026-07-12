"""Fixed-window in-memory rate limiter, keyed per identity.

Single-process only: replicas each get their own window. Good enough until
the Redis-backed limiter arrives with the job queue (Phase 6).
"""

import threading
import time


class FixedWindowLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[int, int]] = {}

    def allow(self, identity: str, limit: int, window_seconds: int = 60) -> bool:
        current = int(time.time()) // window_seconds
        with self._lock:
            window, count = self._windows.get(identity, (current, 0))
            if window != current:
                window, count = current, 0
            if count >= limit:
                self._windows[identity] = (window, count)
                return False
            self._windows[identity] = (window, count + 1)
            return True


limiter = FixedWindowLimiter()
