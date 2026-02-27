-- Migration: add deployment_metrics_cache
-- Adds the per-user, per-ticker snapshot cache for the Structural Deployment Update feature.
-- Snapshot-bucket design: unique key (user_id, snapshot_bucket, ticker).
-- Safe to run on a DB that does NOT yet have this table (idempotent via IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS "deployment_metrics_cache" (
    "id"                TEXT             NOT NULL,
    "user_id"           TEXT             NOT NULL,

    -- Snapshot identity (same values for all tickers in a given snapshot)
    "snapshot_id"       TEXT             NOT NULL,
    "snapshot_bucket"   TIMESTAMP(3)     NOT NULL,   -- UTC midnight of the generation day
    "universe_hash"     TEXT             NOT NULL,   -- SHA-256[:16] of sorted ticker set
    "model_version"     TEXT             NOT NULL    DEFAULT '1.1.0',
    "ruleset_version"   TEXT             NOT NULL    DEFAULT '1.0.0',

    -- Snapshot-level aggregates (denormalized for fast response building)
    "universe_size"     INTEGER          NOT NULL    DEFAULT 0,
    "eligible_count"    INTEGER          NOT NULL    DEFAULT 0,
    "capital_posture"   TEXT             NOT NULL    DEFAULT 'Low',
    "exposure_ceiling"  DOUBLE PRECISION NOT NULL    DEFAULT 50,

    -- Snapshot timestamps
    "generated_at"      TIMESTAMP(3)     NOT NULL    DEFAULT CURRENT_TIMESTAMP,
    "ttl_expires_at"    TIMESTAMP(3)     NOT NULL,

    -- Per-ticker metrics
    "ticker"                TEXT             NOT NULL,
    "sector"                TEXT             NOT NULL    DEFAULT 'Unknown',
    "allocation_current"    DOUBLE PRECISION NOT NULL    DEFAULT 0,
    "allocation_delta_30d"  DOUBLE PRECISION,
    "confirmation_score"    INTEGER          NOT NULL    DEFAULT 0,
    "ev_ratio"              DOUBLE PRECISION,
    "vol_adj_ev_score"      DOUBLE PRECISION,
    "stop_probability"      DOUBLE PRECISION NOT NULL    DEFAULT 50,
    "regime_stable"         BOOLEAN          NOT NULL    DEFAULT true,
    "source_run_id"         TEXT             NOT NULL,

    CONSTRAINT "deployment_metrics_cache_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "deployment_metrics_cache_user_id_snapshot_bucket_ticker_key"
    ON "deployment_metrics_cache" ("user_id", "snapshot_bucket", "ticker");

CREATE INDEX IF NOT EXISTS "deployment_metrics_cache_user_id_universe_hash_model_version_snapshot_bucket_idx"
    ON "deployment_metrics_cache" ("user_id", "universe_hash", "model_version", "snapshot_bucket");

CREATE INDEX IF NOT EXISTS "deployment_metrics_cache_user_id_generated_at_idx"
    ON "deployment_metrics_cache" ("user_id", "generated_at");
