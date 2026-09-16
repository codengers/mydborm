# =============================================================================
# File        : cache.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Description : Simple in-memory query-result cache. Table-level
#               invalidation (conservative — correct over precise), TTL
#               expiry. Used by QueryBuilder.cache()/AsyncQueryBuilder.cache().
# =============================================================================

import threading
import time


class QueryCache:
    """
    In-memory cache for query results, keyed by (dialect, table, sql,
    params). Invalidation is table-level: any write to a table clears
    every cached entry for that table, rather than trying to track which
    specific cached queries a given write actually affects.
    """

    def __init__(self):
        self._store = {}          # key -> (value, expires_at)
        self._by_table = {}       # table -> set of keys
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None, False
            value, expires_at = entry
            if time.time() > expires_at:
                del self._store[key]
                return None, False
            return value, True

    def set(self, key, table: str, value, ttl: int):
        with self._lock:
            self._store[key] = (value, time.time() + ttl)
            self._by_table.setdefault(table, set()).add(key)

    def invalidate_table(self, table: str):
        with self._lock:
            keys = self._by_table.pop(table, None)
            if not keys:
                return
            for key in keys:
                self._store.pop(key, None)

    def clear(self):
        with self._lock:
            self._store.clear()
            self._by_table.clear()


# Global singleton — shared across all models/dialects, keys are already
# scoped by (dialect, table, sql, params) so no cross-contamination.
query_cache = QueryCache()
