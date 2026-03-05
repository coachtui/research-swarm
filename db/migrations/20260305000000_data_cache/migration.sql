-- DVRG Data Cache Layer
-- Neon PostgreSQL-backed TTL cache for all external data fetches in data_provider_hybrid.py.
--
-- Tier 1 (90d)   : cache_company_profile, cache_financial_statements
-- Tier 2 (7d)    : cache_earnings_calendar, cache_analyst_data
-- Tier 2B (24h)  : cache_short_interest
-- Tier 2C (48h)  : cache_institutional_ownership, cache_insider_transactions
-- Tier 3 (15min) : cache_price_snapshot
-- Admin           : cache_control (TTL overrides, enable/disable per table)

-- Tier 1: Company profile — sector, industry, country, company description
CREATE TABLE IF NOT EXISTS cache_company_profile (
    ticker      TEXT PRIMARY KEY,
    data        JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cache_company_profile_expires
    ON cache_company_profile (expires_at);

-- Tier 1: Financial statements — quarterly_financials (yfinance) + filings_raw (SEC Edgar)
CREATE TABLE IF NOT EXISTS cache_financial_statements (
    ticker      TEXT PRIMARY KEY,
    data        JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cache_financial_statements_expires
    ON cache_financial_statements (expires_at);

-- Tier 2: Earnings calendar — earnings_dates, earnings_history
CREATE TABLE IF NOT EXISTS cache_earnings_calendar (
    ticker      TEXT PRIMARY KEY,
    data        JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cache_earnings_calendar_expires
    ON cache_earnings_calendar (expires_at);

-- Tier 2: Analyst data — recommendations, price_target, analyst_estimates
CREATE TABLE IF NOT EXISTS cache_analyst_data (
    ticker      TEXT PRIMARY KEY,
    data        JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cache_analyst_data_expires
    ON cache_analyst_data (expires_at);

-- Tier 2C: Institutional ownership — 13F institutional holders
CREATE TABLE IF NOT EXISTS cache_institutional_ownership (
    ticker      TEXT PRIMARY KEY,
    data        JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cache_institutional_ownership_expires
    ON cache_institutional_ownership (expires_at);

-- Tier 2C: Insider transactions — SEC Form 4 insider buys/sells
CREATE TABLE IF NOT EXISTS cache_insider_transactions (
    ticker      TEXT PRIMARY KEY,
    data        JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cache_insider_transactions_expires
    ON cache_insider_transactions (expires_at);

-- Tier 2B: Short interest — FINRA/dark pool short data (daily refresh)
CREATE TABLE IF NOT EXISTS cache_short_interest (
    ticker      TEXT PRIMARY KEY,
    data        JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cache_short_interest_expires
    ON cache_short_interest (expires_at);

-- Tier 3: Price snapshot — valuation_metrics + historical OHLCV (15-min window)
CREATE TABLE IF NOT EXISTS cache_price_snapshot (
    ticker      TEXT PRIMARY KEY,
    data        JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cache_price_snapshot_expires
    ON cache_price_snapshot (expires_at);

-- Admin: TTL overrides and enable/disable per table
-- Edit rows here to tune TTLs without code changes.
CREATE TABLE IF NOT EXISTS cache_control (
    table_name    TEXT PRIMARY KEY,
    ttl_hours     FLOAT    NOT NULL,
    is_enabled    BOOLEAN  NOT NULL DEFAULT TRUE,
    last_purge_at TIMESTAMPTZ,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed default TTLs (idempotent — skips if row already exists)
INSERT INTO cache_control (table_name, ttl_hours, is_enabled)
VALUES
    ('cache_company_profile',        2160.0, TRUE),  -- 90 days
    ('cache_financial_statements',   2160.0, TRUE),  -- 90 days
    ('cache_earnings_calendar',       168.0, TRUE),  -- 7 days
    ('cache_analyst_data',            168.0, TRUE),  -- 7 days
    ('cache_institutional_ownership',  48.0, TRUE),  -- 48h
    ('cache_insider_transactions',     48.0, TRUE),  -- 48h
    ('cache_short_interest',           24.0, TRUE),  -- 24h
    ('cache_price_snapshot',            0.25, TRUE)  -- 15 min
ON CONFLICT (table_name) DO NOTHING;
