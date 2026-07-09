-- Phase 3A: industry ETF overlay + size/style regime inputs.
-- Additive and nullable — historical rows and degraded weeks stay valid.
ALTER TABLE "MarketOutlook" ADD COLUMN "industryRankings" JSONB;
ALTER TABLE "MarketOutlook" ADD COLUMN "sizeStyle" JSONB;
