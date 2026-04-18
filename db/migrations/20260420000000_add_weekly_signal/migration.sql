-- WeeklySignal table — stores one row per ticker per weekly batch run.
-- All downstream surfaces (leaderboard, alerts, portfolio scan, public teasers)
-- query this table instead of re-running expensive LLM analysis.

CREATE TABLE IF NOT EXISTS "weekly_signals" (
    "id"                  TEXT        NOT NULL,
    "ticker"              TEXT        NOT NULL,
    "runDate"             TIMESTAMP(3) NOT NULL,

    -- Core verdict
    "verdict"             TEXT,
    "currentPrice"        DOUBLE PRECISION,
    "fairValue"           DOUBLE PRECISION,
    "fairValueGapPct"     DOUBLE PRECISION,

    -- Probabilistic signals
    "evProbability"       DOUBLE PRECISION,
    "stopLossProbability" DOUBLE PRECISION,

    -- Activity signals
    "insiderScore"        DOUBLE PRECISION,
    "darkPoolScore"       DOUBLE PRECISION,
    "sentimentScore"      DOUBLE PRECISION,

    -- Text
    "synthesisSummary"    TEXT,
    "catalystSummary"     TEXT,

    -- Position
    "positionSizeRec"     TEXT,

    -- Market context (week-over-week %)
    "esChangePct"         DOUBLE PRECISION,
    "nqChangePct"         DOUBLE PRECISION,
    "dowChangePct"        DOUBLE PRECISION,

    -- Alert diffing — prior week values
    "priorVerdict"        TEXT,
    "priorEvProbability"  DOUBLE PRECISION,

    -- Screener metadata
    "screenerScore"       DOUBLE PRECISION,

    "createdAt"           TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt"           TIMESTAMP(3) NOT NULL,

    CONSTRAINT "weekly_signals_pkey" PRIMARY KEY ("id")
);

CREATE INDEX IF NOT EXISTS "weekly_signals_runDate_idx" ON "weekly_signals"("runDate");
CREATE INDEX IF NOT EXISTS "weekly_signals_ticker_idx" ON "weekly_signals"("ticker");
CREATE UNIQUE INDEX IF NOT EXISTS "weekly_signals_ticker_runDate_key" ON "weekly_signals"("ticker", "runDate");
