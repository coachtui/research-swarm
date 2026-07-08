-- CreateTable
CREATE TABLE "MarketOutlook" (
    "id" TEXT NOT NULL,
    "runDate" TIMESTAMP(3) NOT NULL,
    "regime" TEXT NOT NULL,
    "regimeMechanical" TEXT NOT NULL,
    "strategistOverride" BOOLEAN NOT NULL DEFAULT false,
    "strategistStatus" TEXT NOT NULL DEFAULT 'ok',
    "conviction" DOUBLE PRECISION,
    "sectorRankings" JSONB NOT NULL,
    "rotationFlags" JSONB NOT NULL,
    "breadth" JSONB NOT NULL,
    "reasoning" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "MarketOutlook_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "MarketOutlook_runDate_idx" ON "MarketOutlook"("runDate");
