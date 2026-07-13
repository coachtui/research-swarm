-- CreateTable
CREATE TABLE "WeeklyBatchRun" (
    "id" TEXT NOT NULL,
    "runDate" TIMESTAMP(3) NOT NULL,
    "status" TEXT NOT NULL,
    "abortReason" TEXT,
    "universeSize" INTEGER,
    "advancedCount" INTEGER,
    "watchlistExtras" INTEGER,
    "quantStored" INTEGER,
    "quantFailed" INTEGER,
    "escalationSwarm" INTEGER,
    "escalationReuse" INTEGER,
    "escalationHold" INTEGER,
    "swarmCap" INTEGER,
    "outcomes" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "WeeklyBatchRun_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "WeeklyBatchRun_runDate_idx" ON "WeeklyBatchRun"("runDate");
