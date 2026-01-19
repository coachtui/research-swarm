"""
SQLite-based caching for API responses.
Reduces API calls and stays under budget.
"""
import sqlite3
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any
from research_swarm.config import settings
from research_swarm.logger import logger

class Cache:
    """Simple key-value cache with TTL support."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.cache_dir / "api_cache.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Create cache table if not exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at
                ON cache(expires_at)
            """)
            logger.debug(f"Cache initialized at {self.db_path}")

    def _make_key(self, namespace: str, key: str) -> str:
        """Generate cache key with namespace."""
        combined = f"{namespace}:{key}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def get(self, namespace: str, key: str) -> Optional[Any]:
        """
        Retrieve cached value if not expired.

        Args:
            namespace: Cache namespace (e.g., 'sec', 'news')
            key: Cache key (e.g., 'AAPL_10K_2023')

        Returns:
            Cached value or None if expired/missing
        """
        cache_key = self._make_key(namespace, key)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?",
                (cache_key,)
            )
            row = cursor.fetchone()

            if not row:
                logger.debug(f"Cache miss: {namespace}:{key}")
                return None

            value_json, expires_at = row
            expires_at = datetime.fromisoformat(expires_at)

            if datetime.now() > expires_at:
                logger.debug(f"Cache expired: {namespace}:{key}")
                # Delete expired entry
                conn.execute("DELETE FROM cache WHERE key = ?", (cache_key,))
                return None

            logger.debug(f"Cache hit: {namespace}:{key}")
            return json.loads(value_json)

    def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        ttl_days: int = 7
    ):
        """
        Store value in cache with TTL.

        Args:
            namespace: Cache namespace
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl_days: Time-to-live in days
        """
        cache_key = self._make_key(namespace, key)
        created_at = datetime.now()
        expires_at = created_at + timedelta(days=ttl_days)
        value_json = json.dumps(value)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO cache (key, value, created_at, expires_at)
                VALUES (?, ?, ?, ?)
            """, (
                cache_key,
                value_json,
                created_at.isoformat(),
                expires_at.isoformat()
            ))
            logger.debug(f"Cached: {namespace}:{key} (TTL: {ttl_days} days)")

    def clear_expired(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of entries deleted.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM cache WHERE expires_at < ?",
                (datetime.now().isoformat(),)
            )
            return cursor.rowcount

    def stats(self) -> dict:
        """Get cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM cache")
            total = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT COUNT(*) FROM cache WHERE expires_at > ?",
                (datetime.now().isoformat(),)
            )
            valid = cursor.fetchone()[0]

            return {
                "total_entries": total,
                "valid_entries": valid,
                "expired_entries": total - valid
            }

# Global cache instance
cache = Cache()
