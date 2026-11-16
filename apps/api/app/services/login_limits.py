"""Bounded local defence when the distributed authentication limiter is unavailable.

Limits are per process during a broker outage; readiness remains degraded so an
operator can repair Redis. Existing active limits are never evicted for new keys.
"""
from threading import Lock
from time import monotonic


class LocalLoginLimits:
    def __init__(self, max_keys=10000, clock=monotonic):
        self._max_keys = max_keys
        self._clock = clock
        self._entries = {}
        self._lock = Lock()

    def allow(self, key, limit, window):
        with self._lock:
            now = self._clock()
            entry = self._entries.get(key)
            if entry is None or entry[0] <= now:
                # Prune only expired entries; attackers cannot evict active keys.
                self._entries = {k: v for k, v in self._entries.items() if v[0] > now}
                if key not in self._entries and len(self._entries) >= self._max_keys:
                    return False
                entry = (now + window, 0)
            count = min(entry[1] + 1, limit + 1)
            self._entries[key] = (entry[0], count)
            return count <= limit

    def clear(self, key):
        with self._lock:
            self._entries.pop(key, None)


fallback_login_limits = LocalLoginLimits()
