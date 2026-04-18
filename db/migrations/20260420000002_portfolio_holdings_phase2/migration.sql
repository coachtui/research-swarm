-- Phase 2a: Portfolio Holdings Rework (additive only)
-- Adds cash tracking to Portfolio, price/weight fields to Position,
-- and conditional action chain fields to PortfolioAction.

-- Portfolio: add cash balance
ALTER TABLE "portfolios" ADD COLUMN "cash_balance" DOUBLE PRECISION NOT NULL DEFAULT 0;
ALTER TABLE "portfolios" ADD COLUMN "cash_updated_at" TIMESTAMP(3);

-- Position: add price tracking and target weight fields
ALTER TABLE "positions" ADD COLUMN "last_known_price" DOUBLE PRECISION;
ALTER TABLE "positions" ADD COLUMN "last_price_at" TIMESTAMP(3);
ALTER TABLE "positions" ADD COLUMN "target_weight" DOUBLE PRECISION NOT NULL DEFAULT 0;
ALTER TABLE "positions" ADD COLUMN "engine_suggested_weight" DOUBLE PRECISION;

-- PortfolioAction: add conditional action chain fields
ALTER TABLE "portfolio_actions" ADD COLUMN "trigger_price" DOUBLE PRECISION;
ALTER TABLE "portfolio_actions" ADD COLUMN "trigger_condition" TEXT;
ALTER TABLE "portfolio_actions" ADD COLUMN "parent_action_id" TEXT;

-- Self-referential FK for action chains (parent -> children)
ALTER TABLE "portfolio_actions" ADD CONSTRAINT "portfolio_actions_parent_action_id_fkey"
    FOREIGN KEY ("parent_action_id") REFERENCES "portfolio_actions"("id")
    ON DELETE SET NULL ON UPDATE CASCADE;

-- Index for looking up children by parent
CREATE INDEX "portfolio_actions_parent_action_id_idx" ON "portfolio_actions"("parent_action_id");
