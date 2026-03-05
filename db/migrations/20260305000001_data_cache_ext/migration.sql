-- DVRG Data Cache Extension — Phase 2
-- Adds three new Neon-backed cache tables:
--   cache_8k_filings  (24h) — SEC 8-K material events (was process-restart-volatile SQLite)
--   cache_openinsider (48h) — OpenInsider HTML scrape results
--   cache_dark_pool   (24h) — FINRA ATS dark pool data (was process-restart-volatile SQLite)

-- SEC 8-K filings — material events between quarterly reports
CREATE TABLE IF NOT EXISTS cache_8k_filings (
    ticker      TEXT PRIMARY KEY,
    data        JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cache_8k_filings_expires
    ON cache_8k_filings (expires_at);

-- OpenInsider Form 4 transactions — HTML scrape, 1-year lookback
CREATE TABLE IF NOT EXISTS cache_openinsider (
    ticker      TEXT PRIMARY KEY,
    data        JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cache_openinsider_expires
    ON cache_openinsider (expires_at);

-- FINRA ATS dark pool — weekly ATS aggregate data, 13-week lookback
CREATE TABLE IF NOT EXISTS cache_dark_pool (
    ticker      TEXT PRIMARY KEY,
    data        JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cache_dark_pool_expires
    ON cache_dark_pool (expires_at);

-- Seed TTL defaults in cache_control (idempotent)
INSERT INTO cache_control (table_name, ttl_hours, is_enabled)
VALUES
    ('cache_8k_filings',   24.0, TRUE),
    ('cache_openinsider',  48.0, TRUE),
    ('cache_dark_pool',    24.0, TRUE)
ON CONFLICT (table_name) DO NOTHING;
