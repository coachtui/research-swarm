-- Filing extraction cache (Phase B)
--
-- Structured LLM extractions of individual SEC filings, keyed by SEC
-- accession number. A filing never changes after it is filed, so an
-- extraction is computed once per filing EVER and shared by every
-- subsequent analysis of that ticker, by any user.
--
-- The key column is named `ticker` for compatibility with the generic
-- DataCacheService get/set path; it holds the accession number
-- (e.g. "0000320193-25-000073").

CREATE TABLE IF NOT EXISTS cache_filing_extraction (
    ticker      TEXT PRIMARY KEY,
    data        JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cache_filing_extraction_expires
    ON cache_filing_extraction (expires_at);
