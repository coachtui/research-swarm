-- Migration: sector_snapshot_history
-- Stores per-sector aggregates per snapshot bucket to enable Δ Opp / Δ Structural / Δ Tier2 trending.

CREATE TABLE IF NOT EXISTS "sector_snapshot_history" (
    "id"                    TEXT NOT NULL,
    "user_id"               TEXT NOT NULL,
    "snapshot_id"           TEXT NOT NULL,
    "snapshot_bucket"       TIMESTAMP(3) NOT NULL,
    "sector"                TEXT NOT NULL,
    "total_tracked"         INTEGER NOT NULL,
    "confirmed_count"       INTEGER NOT NULL,
    "confirmed_pct"         DOUBLE PRECISION NOT NULL,
    "structural_score"      DOUBLE PRECISION NOT NULL,
    "opp_score"             DOUBLE PRECISION NOT NULL,
    "rotation_score"        DOUBLE PRECISION NOT NULL,
    "tier2_count"           INTEGER NOT NULL,
    "avg_risk_adj_edge_pct" DOUBLE PRECISION NOT NULL,
    "positive_edge_ratio"   DOUBLE PRECISION NOT NULL,
    "median_stop_pct"       DOUBLE PRECISION NOT NULL,
    "coverage_pct"          DOUBLE PRECISION NOT NULL,
    "universe_size"         INTEGER NOT NULL,
    "created_at"            TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "sector_snapshot_history_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "sector_snapshot_history_user_id_snapshot_bucket_sector_key"
    ON "sector_snapshot_history"("user_id", "snapshot_bucket", "sector");

CREATE INDEX IF NOT EXISTS "sector_snapshot_history_user_id_snapshot_bucket_idx"
    ON "sector_snapshot_history"("user_id", "snapshot_bucket");
