-- Tiered batch: quant vs full rows, escalation audit trail
ALTER TABLE "weekly_signals" ADD COLUMN "tier" TEXT NOT NULL DEFAULT 'full';
ALTER TABLE "weekly_signals" ADD COLUMN "escalationScore" DOUBLE PRECISION;
ALTER TABLE "weekly_signals" ADD COLUMN "escalationReasons" JSONB;
ALTER TABLE "weekly_signals" ADD COLUMN "quantSignals" JSONB;

CREATE INDEX "weekly_signals_tier_idx" ON "weekly_signals"("tier");
