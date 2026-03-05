"""
Neon PostgreSQL-backed data cache for the DVRG analysis pipeline.

Provides transparent, TTL-gated caching for all external data fetches in
data_provider_hybrid.py. Falls back silently on any DB error so analysis
always proceeds even if the cache is unavailable.

TTL Tiers (defaults, overridable via the cache_control table):
  Tier 1  — 90 days  : company_profile, financial_statements
  Tier 2  — 7 days   : earnings_calendar, analyst_data
  Tier 2B — 24h      : short_interest
  Tier 2C — 48h      : institutional_ownership, insider_transactions
  Tier 3  — 15 min   : price_snapshot

DataFrame serialization:
  pandas DataFrames are tagged with {"__df__": "<split-json>"} so they can be
  transparently restored to DataFrame on read. Nested DataFrames inside dicts
  are handled recursively.
"""
import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Default TTLs in hours; overridden at runtime by cache_control table
_DEFAULT_TTL: Dict[str, float] = {
    "cache_company_profile":        90 * 24,   # 90 days
    "cache_financial_statements":   90 * 24,   # 90 days
    "cache_earnings_calendar":       7 * 24,   # 7 days
    "cache_analyst_data":            7 * 24,   # 7 days
    "cache_institutional_ownership": 48.0,     # 48h
    "cache_insider_transactions":    48.0,     # 48h
    "cache_openinsider":             48.0,     # 48h
    "cache_short_interest":          24.0,     # 24h
    "cache_dark_pool":               24.0,     # 24h
    "cache_8k_filings":              24.0,     # 24h
    "cache_price_snapshot":           0.25,    # 15 min
}


# ── Serialization helpers ──────────────────────────────────────────────────────

def _serialize(obj: Any) -> Any:
    """
    Recursively serialize an object for JSONB storage.

    pandas DataFrames → {"__df__": "<split-json-string>"}
    pandas Series    → {"__series__": "<split-json-string>"}
    Dicts/lists      → recursed
    Everything else  → returned as-is (json.dumps default=str handles remaining types)
    """
    if obj is None:
        return None
    try:
        import pandas as pd
        if isinstance(obj, pd.DataFrame):
            try:
                return {"__df__": obj.to_json(orient="split")}
            except Exception:
                return None
        if isinstance(obj, pd.Series):
            try:
                return {"__series__": obj.to_json(orient="split")}
            except Exception:
                return None
    except ImportError:
        pass
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(item) for item in obj]
    return obj


def _deserialize(obj: Any) -> Any:
    """
    Recursively restore DataFrames from tagged JSONB storage.

    {"__df__": "..."}     → pd.DataFrame
    {"__series__": "..."} → pd.Series
    Dicts/lists           → recursed
    Everything else       → returned as-is
    """
    if obj is None:
        return None
    if isinstance(obj, dict):
        if "__df__" in obj:
            try:
                import pandas as pd
                from io import StringIO
                return pd.read_json(StringIO(obj["__df__"]), orient="split")
            except Exception:
                return None
        if "__series__" in obj:
            try:
                import pandas as pd
                from io import StringIO
                return pd.read_json(StringIO(obj["__series__"]), typ="series", orient="split")
            except Exception:
                return None
        return {k: _deserialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deserialize(item) for item in obj]
    return obj


# ── Cache service ──────────────────────────────────────────────────────────────

class DataCacheService:
    """
    Synchronous PostgreSQL cache for the DVRG data pipeline.

    Uses psycopg2 directly (not Prisma) to be compatible with the synchronous
    data_provider_hybrid.py. Each public method corresponds to one cache table.
    """

    def __init__(self, db_url: Optional[str] = None):
        self._db_url = db_url or os.environ.get("DATABASE_URL")
        if not self._db_url:
            logger.warning("[DataCache] DATABASE_URL not set — cache disabled")
        self._enabled = bool(self._db_url)
        self._ttl: Dict[str, float] = dict(_DEFAULT_TTL)
        self._ttl_loaded = False

    # ── Connection ─────────────────────────────────────────────────────────────

    def _connect(self):
        try:
            import psycopg2
            return psycopg2.connect(self._db_url)
        except ImportError:
            logger.warning("[DataCache] psycopg2 not installed — cache disabled")
            self._enabled = False
            return None
        except Exception as e:
            logger.warning(f"[DataCache] DB connect failed: {e}")
            return None

    # ── TTL overrides ──────────────────────────────────────────────────────────

    def _load_ttl_overrides(self) -> None:
        """Load TTL overrides from cache_control table (once per process)."""
        if self._ttl_loaded or not self._enabled:
            return
        try:
            import psycopg2.extras
            conn = self._connect()
            if conn is None:
                self._ttl_loaded = True
                return
            with conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        "SELECT table_name, ttl_hours, is_enabled FROM cache_control"
                    )
                    for row in cur.fetchall():
                        name = row["table_name"]
                        if not row["is_enabled"]:
                            self._ttl[name] = 0.0
                        else:
                            self._ttl[name] = float(row["ttl_hours"])
        except Exception as e:
            logger.debug(f"[DataCache] TTL load failed (using defaults): {e}")
        finally:
            self._ttl_loaded = True

    # ── Core get / set ─────────────────────────────────────────────────────────

    def _get(self, table: str, ticker: str) -> Optional[Any]:
        if not self._enabled:
            return None
        try:
            import psycopg2.extras
            conn = self._connect()
            if conn is None:
                return None
            with conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        f"SELECT data FROM {table} WHERE ticker = %s AND expires_at > NOW()",
                        (ticker.upper(),),
                    )
                    row = cur.fetchone()
            if row:
                logger.debug(f"[DataCache] HIT  {table}:{ticker}")
                return _deserialize(row["data"])
            logger.debug(f"[DataCache] MISS {table}:{ticker}")
        except Exception as e:
            logger.warning(f"[DataCache] get error [{table}:{ticker}]: {e}")
        return None

    def _set(self, table: str, ticker: str, data: Any) -> None:
        if not self._enabled:
            return
        self._load_ttl_overrides()
        ttl_hours = self._ttl.get(table, 24.0)
        if ttl_hours <= 0:
            return  # Table disabled
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        try:
            serialized = _serialize(data)
            payload = json.dumps(serialized, default=str)
            conn = self._connect()
            if conn is None:
                return
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        INSERT INTO {table} (ticker, data, fetched_at, expires_at)
                        VALUES (%s, %s::jsonb, NOW(), %s)
                        ON CONFLICT (ticker) DO UPDATE
                            SET data       = EXCLUDED.data,
                                fetched_at = EXCLUDED.fetched_at,
                                expires_at = EXCLUDED.expires_at
                        """,
                        (ticker.upper(), payload, expires_at),
                    )
            logger.debug(
                f"[DataCache] SET  {table}:{ticker} "
                f"(expires {expires_at.strftime('%Y-%m-%d %H:%M')} UTC)"
            )
        except Exception as e:
            logger.warning(f"[DataCache] set error [{table}:{ticker}]: {e}")

    # ── Tier 1: Company Profile (90 days) ──────────────────────────────────────

    def get_company_profile(self, ticker: str) -> Optional[Dict]:
        return self._get("cache_company_profile", ticker)

    def set_company_profile(self, ticker: str, company_info: Dict) -> None:
        self._set("cache_company_profile", ticker, company_info)

    # ── Tier 1: Financial Statements (90 days) ─────────────────────────────────
    # Stores quarterly_financials (yfinance) + filings_raw (SEC Edgar) together.
    # Written once per analysis run after both sources have been fetched.

    def get_financial_statements(self, ticker: str) -> Optional[Dict]:
        return self._get("cache_financial_statements", ticker)

    def set_financial_statements(
        self,
        ticker: str,
        quarterly_financials: Any,
        filings_raw: Any,
    ) -> None:
        payload = {
            "quarterly_financials": quarterly_financials,
            "filings_raw": filings_raw,
        }
        self._set("cache_financial_statements", ticker, payload)

    # ── Tier 2: Earnings Calendar (7 days) ────────────────────────────────────
    # Stores earnings_history + earnings_dates.

    def get_earnings_calendar(self, ticker: str) -> Optional[Dict]:
        return self._get("cache_earnings_calendar", ticker)

    def set_earnings_calendar(self, ticker: str, earnings_data: Dict) -> None:
        self._set("cache_earnings_calendar", ticker, earnings_data)

    # ── Tier 2: Analyst Data (7 days) ──────────────────────────────────────────
    # Stores recommendations + price_target + analyst_estimates.

    def get_analyst_data(self, ticker: str) -> Optional[Dict]:
        return self._get("cache_analyst_data", ticker)

    def set_analyst_data(
        self,
        ticker: str,
        recommendations: Any,
        price_target: Any,
        analyst_estimates: Any,
        upgrades_downgrades: Any = None,
    ) -> None:
        payload = {
            "recommendations": recommendations,
            "price_target": price_target,
            "analyst_estimates": analyst_estimates,
            "upgrades_downgrades": upgrades_downgrades,
        }
        self._set("cache_analyst_data", ticker, payload)

    # ── Tier 2C: Institutional Ownership (48h) ─────────────────────────────────

    def get_institutional_ownership(self, ticker: str) -> Optional[Any]:
        return self._get("cache_institutional_ownership", ticker)

    def set_institutional_ownership(
        self, ticker: str, institutional_holders: Any
    ) -> None:
        self._set("cache_institutional_ownership", ticker, institutional_holders)

    # ── Tier 2C: Insider Transactions (48h) ────────────────────────────────────

    def get_insider_transactions(self, ticker: str) -> Optional[Any]:
        return self._get("cache_insider_transactions", ticker)

    def set_insider_transactions(
        self, ticker: str, insider_transactions: Any
    ) -> None:
        self._set("cache_insider_transactions", ticker, insider_transactions)

    # ── Tier 2B: Short Interest (24h) ─────────────────────────────────────────

    def get_short_interest(self, ticker: str) -> Optional[Any]:
        return self._get("cache_short_interest", ticker)

    def set_short_interest(self, ticker: str, short_interest: Any) -> None:
        self._set("cache_short_interest", ticker, short_interest)

    # ── Tier 2B: Dark Pool / FINRA ATS (24h) ──────────────────────────────────

    def get_dark_pool(self, ticker: str) -> Optional[Any]:
        return self._get("cache_dark_pool", ticker)

    def set_dark_pool(self, ticker: str, dark_pool_data: Any) -> None:
        self._set("cache_dark_pool", ticker, dark_pool_data)

    # ── Tier 2C: OpenInsider transactions (48h) ────────────────────────────────

    def get_openinsider(self, ticker: str) -> Optional[Any]:
        return self._get("cache_openinsider", ticker)

    def set_openinsider(self, ticker: str, transactions: Any) -> None:
        self._set("cache_openinsider", ticker, transactions)

    # ── Tier 2B: SEC 8-K filings (24h) ────────────────────────────────────────

    def get_8k_filings(self, ticker: str) -> Optional[Any]:
        return self._get("cache_8k_filings", ticker)

    def set_8k_filings(self, ticker: str, filings_data: Any) -> None:
        self._set("cache_8k_filings", ticker, filings_data)

    # ── Tier 3: Price Snapshot (15 min) ────────────────────────────────────────
    # Stores valuation_metrics (dict) + historical_data (DataFrame).
    # historical_data is stored as a tagged {"__df__": ...} and restored transparently.

    def get_price_snapshot(self, ticker: str) -> Optional[Dict]:
        return self._get("cache_price_snapshot", ticker)

    def set_price_snapshot(
        self,
        ticker: str,
        valuation_metrics: Optional[Dict],
        historical_data: Any,
    ) -> None:
        payload = {
            "valuation_metrics": valuation_metrics,
            "historical_data": historical_data,  # _serialize handles DataFrame tagging
        }
        self._set("cache_price_snapshot", ticker, payload)

    # ── Maintenance ────────────────────────────────────────────────────────────

    def purge_expired(self) -> Dict[str, int]:
        """Delete expired rows from all cache tables. Safe to call on a schedule."""
        counts: Dict[str, int] = {}
        if not self._enabled:
            return counts
        tables = list(_DEFAULT_TTL.keys())
        try:
            conn = self._connect()
            if conn is None:
                return counts
            with conn:
                with conn.cursor() as cur:
                    for table in tables:
                        cur.execute(f"DELETE FROM {table} WHERE expires_at <= NOW()")
                        counts[table] = cur.rowcount
                    cur.execute(
                        "UPDATE cache_control SET last_purge_at = NOW() "
                        "WHERE table_name = ANY(%s)",
                        (tables,),
                    )
        except Exception as e:
            logger.warning(f"[DataCache] purge_expired error: {e}")
        return counts

    def stats(self) -> Dict[str, Dict[str, int]]:
        """Return {table: {total, valid, expired}} counts for monitoring."""
        result: Dict[str, Dict[str, int]] = {}
        if not self._enabled:
            return result
        try:
            import psycopg2.extras
            conn = self._connect()
            if conn is None:
                return result
            with conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    for table in _DEFAULT_TTL:
                        cur.execute(
                            f"SELECT COUNT(*) AS total, "
                            f"SUM(CASE WHEN expires_at > NOW() THEN 1 ELSE 0 END) AS valid "
                            f"FROM {table}"
                        )
                        row = cur.fetchone()
                        total = int(row["total"] or 0)
                        valid = int(row["valid"] or 0)
                        result[table] = {
                            "total": total,
                            "valid": valid,
                            "expired": total - valid,
                        }
        except Exception as e:
            logger.warning(f"[DataCache] stats error: {e}")
        return result


# ── Global singleton ───────────────────────────────────────────────────────────
data_cache = DataCacheService()
