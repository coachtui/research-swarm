-- TickerFinancials cache: quarterly/annual financials per ticker.
-- Avoids re-fetching the same earnings data on every analysis run.
-- Source preference: edgar > yfinance (more authoritative for US companies).

CREATE TABLE "ticker_financials" (
    "id"                  TEXT NOT NULL,
    "ticker"              TEXT NOT NULL,
    "period"              TEXT NOT NULL,       -- "2024-Q4" | "2024-FY"
    "period_end"          TIMESTAMP(3) NOT NULL,
    "source"              TEXT NOT NULL,       -- "yfinance" | "edgar"

    -- Income statement
    "revenue"             DOUBLE PRECISION,
    "operating_income"    DOUBLE PRECISION,
    "operating_margin"    DOUBLE PRECISION,   -- operating_income / revenue
    "gross_profit"        DOUBLE PRECISION,
    "net_income"          DOUBLE PRECISION,
    "ebitda"              DOUBLE PRECISION,

    -- Cash flow statement
    "operating_cash_flow" DOUBLE PRECISION,
    "capex"               DOUBLE PRECISION,
    "free_cash_flow"      DOUBLE PRECISION,   -- operating_cf - capex

    -- Balance sheet snapshots
    "total_debt"          DOUBLE PRECISION,
    "cash"                DOUBLE PRECISION,

    -- Fetch metadata
    "fetched_at"          TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ticker_financials_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "ticker_financials_ticker_period_source_key"
    ON "ticker_financials"("ticker", "period", "source");

CREATE INDEX "ticker_financials_ticker_period_end_idx"
    ON "ticker_financials"("ticker", "period_end" DESC);
