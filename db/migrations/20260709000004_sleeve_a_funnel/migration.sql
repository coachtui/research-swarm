-- db/migrations/20260709000004_sleeve_a_funnel/migration.sql
-- Phase 3C: Sleeve A funnel columns (all nullable / defaulted — no backfill).
ALTER TABLE "EnginePosition"
  ADD COLUMN "convictionScore" DOUBLE PRECISION,
  ADD COLUMN "stopPrice" DOUBLE PRECISION,
  ADD COLUMN "highWaterClose" DOUBLE PRECISION,
  ADD COLUMN "sourceTags" JSONB,
  ADD COLUMN "reportRef" TEXT;

ALTER TABLE "EngineTrade"
  ADD COLUMN "limitPrice" DOUBLE PRECISION,
  ADD COLUMN "expiresAt" TIMESTAMP(3);

ALTER TABLE "SleeveState"
  ADD COLUMN "mode" TEXT NOT NULL DEFAULT 'live';
