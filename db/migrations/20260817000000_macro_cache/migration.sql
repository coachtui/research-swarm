-- Macro cache (market state + interpreted brief)
--
-- Both rows describe the world, not a company, so a single row is shared by
-- every analysis that runs while it is fresh. cache_macro_snapshot holds the
-- deterministic instrument scan (indices, volatility, rates, FX, commodities,
-- sector and regional rotation). cache_macro_brief holds the interpreted
-- geopolitical/macro themes — one LLM call amortized across every report in
-- the TTL window.
--
-- The key column is named `ticker` for compatibility with the generic
-- DataCacheService get/set path; it holds a scope string (e.g. "global").

CREATE TABLE IF NOT EXISTS cache_macro_snapshot (
    ticker      TEXT PRIMARY KEY,
    data        JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cache_macro_snapshot_expires
    ON cache_macro_snapshot (expires_at);

CREATE TABLE IF NOT EXISTS cache_macro_brief (
    ticker      TEXT PRIMARY KEY,
    data        JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cache_macro_brief_expires
    ON cache_macro_brief (expires_at);
