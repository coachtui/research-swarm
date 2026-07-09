-- CreateTable
CREATE TABLE "LinkedBrokerAccount" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "provider" TEXT NOT NULL DEFAULT 'alpaca',
    "mode" TEXT NOT NULL DEFAULT 'paper',
    "apiKeyEncrypted" TEXT NOT NULL,
    "apiSecretEncrypted" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'active',
    "lastVerifiedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "LinkedBrokerAccount_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "EngineTrade" (
    "id" TEXT NOT NULL,
    "sleeve" TEXT NOT NULL,
    "symbol" TEXT NOT NULL,
    "side" TEXT NOT NULL,
    "qty" DOUBLE PRECISION NOT NULL,
    "notional" DOUBLE PRECISION,
    "fillPrice" DOUBLE PRECISION,
    "brokerOrderId" TEXT,
    "status" TEXT NOT NULL,
    "journal" JSONB NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "EngineTrade_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "EnginePosition" (
    "id" TEXT NOT NULL,
    "sleeve" TEXT NOT NULL,
    "symbol" TEXT NOT NULL,
    "qty" DOUBLE PRECISION NOT NULL,
    "avgEntryPrice" DOUBLE PRECISION NOT NULL,
    "thesis" JSONB NOT NULL,
    "openedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "EnginePosition_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "SleeveSnapshot" (
    "id" TEXT NOT NULL,
    "snapshotDate" TIMESTAMP(3) NOT NULL,
    "sleeve" TEXT NOT NULL,
    "equity" DOUBLE PRECISION NOT NULL,
    "cash" DOUBLE PRECISION NOT NULL,
    "positionsValue" DOUBLE PRECISION NOT NULL,
    "spyClose" DOUBLE PRECISION NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "SleeveSnapshot_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "SleeveState" (
    "id" TEXT NOT NULL,
    "sleeve" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'active',
    "statusReason" TEXT,
    "cashBalance" DOUBLE PRECISION NOT NULL,
    "inceptionDate" TIMESTAMP(3) NOT NULL,
    "inceptionEquity" DOUBLE PRECISION NOT NULL,
    "inceptionSpyClose" DOUBLE PRECISION NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "SleeveState_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "LinkedBrokerAccount_userId_provider_mode_key" ON "LinkedBrokerAccount"("userId", "provider", "mode");

-- CreateIndex
CREATE INDEX "EngineTrade_sleeve_createdAt_idx" ON "EngineTrade"("sleeve", "createdAt");

-- CreateIndex
CREATE UNIQUE INDEX "EnginePosition_sleeve_symbol_key" ON "EnginePosition"("sleeve", "symbol");

-- CreateIndex
CREATE UNIQUE INDEX "SleeveSnapshot_snapshotDate_sleeve_key" ON "SleeveSnapshot"("snapshotDate", "sleeve");

-- CreateIndex
CREATE UNIQUE INDEX "SleeveState_sleeve_key" ON "SleeveState"("sleeve");

-- AddForeignKey
ALTER TABLE "LinkedBrokerAccount" ADD CONSTRAINT "LinkedBrokerAccount_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
