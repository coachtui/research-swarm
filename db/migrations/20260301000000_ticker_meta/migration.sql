-- Migration: 20260301000000_ticker_meta
--
-- 1. Add sector/industry classification columns to stock_results
--    (snapshot of TickerMeta at the time the report was generated)
-- 2. Create the ticker_meta cache table (PK = uppercase ticker)

-- ─── stock_results additions ─────────────────────────────────────────────────

ALTER TABLE stock_results
  ADD COLUMN IF NOT EXISTS sector          VARCHAR(255),
  ADD COLUMN IF NOT EXISTS industry        VARCHAR(255),
  ADD COLUMN IF NOT EXISTS sub_industry    VARCHAR(255),
  ADD COLUMN IF NOT EXISTS exchange        VARCHAR(50),
  ADD COLUMN IF NOT EXISTS country         VARCHAR(100),
  ADD COLUMN IF NOT EXISTS currency        VARCHAR(10),
  ADD COLUMN IF NOT EXISTS meta_source     VARCHAR(50),
  ADD COLUMN IF NOT EXISTS meta_updated_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS stock_results_sector_idx ON stock_results (sector);

-- ─── ticker_meta (sector/industry cache) ─────────────────────────────────────

CREATE TABLE IF NOT EXISTS ticker_meta (
  ticker        VARCHAR(20)  PRIMARY KEY,
  sector        VARCHAR(255),
  industry      VARCHAR(255),
  sub_industry  VARCHAR(255),
  exchange      VARCHAR(50),
  country       VARCHAR(100),
  currency      VARCHAR(10),
  source        VARCHAR(50)  NOT NULL DEFAULT 'yfinance',
  raw           JSONB,
  updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ticker_meta_updated_at_idx ON ticker_meta (updated_at);
