-- CreateTable: portfolios
CREATE TABLE "portfolios" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "name" TEXT NOT NULL DEFAULT 'Core',
    "mandate" TEXT NOT NULL DEFAULT 'compounder',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "portfolios_pkey" PRIMARY KEY ("id")
);

-- CreateTable: positions
CREATE TABLE "positions" (
    "id" TEXT NOT NULL,
    "portfolio_id" TEXT NOT NULL,
    "ticker" TEXT NOT NULL,
    "current_weight" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "cost_basis" DOUBLE PRECISION,
    "shares" DOUBLE PRECISION,
    "tier_state" TEXT NOT NULL DEFAULT 'none',
    "thesis_state" TEXT NOT NULL DEFAULT 'intact',
    "eligibility_state" TEXT NOT NULL DEFAULT 'pending',
    "ownership_status" TEXT NOT NULL DEFAULT 'watch',
    "entry_date" TIMESTAMP(3),
    "quarters_held" INTEGER NOT NULL DEFAULT 0,
    "compounder_score" DOUBLE PRECISION,
    "last_drawdown" DOUBLE PRECISION,
    "add_tiers_applied" JSONB NOT NULL DEFAULT '[]',
    "latest_run_id" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "positions_pkey" PRIMARY KEY ("id")
);

-- CreateTable: portfolio_actions
CREATE TABLE "portfolio_actions" (
    "id" TEXT NOT NULL,
    "portfolio_id" TEXT NOT NULL,
    "ticker" TEXT NOT NULL,
    "action_type" TEXT NOT NULL,
    "weight_delta" DOUBLE PRECISION NOT NULL,
    "reason_codes" TEXT[],
    "reason_text" TEXT,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "signal_snapshot" JSONB,
    "trigger_cycle" TEXT,
    "engine_version" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "executed_at" TIMESTAMP(3),
    "expires_at" TIMESTAMP(3),

    CONSTRAINT "portfolio_actions_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "portfolios_user_id_idx" ON "portfolios"("user_id");

-- CreateIndex
CREATE UNIQUE INDEX "portfolios_user_id_name_key" ON "portfolios"("user_id", "name");

-- CreateIndex
CREATE INDEX "positions_portfolio_id_idx" ON "positions"("portfolio_id");

-- CreateIndex
CREATE INDEX "positions_ticker_idx" ON "positions"("ticker");

-- CreateIndex
CREATE UNIQUE INDEX "positions_portfolio_id_ticker_key" ON "positions"("portfolio_id", "ticker");

-- CreateIndex
CREATE INDEX "portfolio_actions_portfolio_id_created_at_idx" ON "portfolio_actions"("portfolio_id", "created_at" DESC);

-- CreateIndex
CREATE INDEX "portfolio_actions_portfolio_id_status_idx" ON "portfolio_actions"("portfolio_id", "status");

-- CreateIndex
CREATE INDEX "portfolio_actions_ticker_idx" ON "portfolio_actions"("ticker");

-- AddForeignKey
ALTER TABLE "portfolios" ADD CONSTRAINT "portfolios_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "positions" ADD CONSTRAINT "positions_portfolio_id_fkey" FOREIGN KEY ("portfolio_id") REFERENCES "portfolios"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "portfolio_actions" ADD CONSTRAINT "portfolio_actions_portfolio_id_fkey" FOREIGN KEY ("portfolio_id") REFERENCES "portfolios"("id") ON DELETE CASCADE ON UPDATE CASCADE;
