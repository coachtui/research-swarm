-- Phase 3B: theme baskets + engine journal. Additive; themeRankings nullable.

CREATE TABLE "ThemeBasket" (
    "id" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'active',
    "origin" TEXT NOT NULL,
    "thesis" TEXT NOT NULL,
    "confidence" DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    "metadata" JSONB,
    "lastReasonedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "retiredAt" TIMESTAMP(3),
    CONSTRAINT "ThemeBasket_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "ThemeBasket_slug_key" ON "ThemeBasket"("slug");

CREATE TABLE "ThemeConstituent" (
    "id" TEXT NOT NULL,
    "themeId" TEXT NOT NULL,
    "ticker" TEXT NOT NULL,
    "exposure" TEXT NOT NULL,
    "confidence" DOUBLE PRECISION NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'active',
    "source" TEXT NOT NULL,
    "validation" JSONB,
    "addedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "removedAt" TIMESTAMP(3),
    CONSTRAINT "ThemeConstituent_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "ThemeConstituent_themeId_ticker_key" ON "ThemeConstituent"("themeId", "ticker");
ALTER TABLE "ThemeConstituent" ADD CONSTRAINT "ThemeConstituent_themeId_fkey"
    FOREIGN KEY ("themeId") REFERENCES "ThemeBasket"("id") ON DELETE CASCADE ON UPDATE CASCADE;

CREATE TABLE "EngineReport" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "type" TEXT NOT NULL,
    "severity" TEXT NOT NULL,
    "source" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "body" JSONB NOT NULL,
    CONSTRAINT "EngineReport_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "EngineReport_createdAt_idx" ON "EngineReport"("createdAt");
CREATE INDEX "EngineReport_type_idx" ON "EngineReport"("type");

ALTER TABLE "MarketOutlook" ADD COLUMN "themeRankings" JSONB;

-- Seed the six owner niches. origin='seed', no constituents — the first
-- monthly reasoning pass populates them. Seeds compete equally thereafter.
INSERT INTO "ThemeBasket" ("id", "slug", "name", "status", "origin", "thesis", "confidence") VALUES
('seed_photonics',    'photonics',    'Photonics & Optical Interconnect', 'active', 'seed', 'Seed hypothesis: networking/interconnect is a scaling bottleneck; optical I/O demand compounds with cluster size.', 0.5),
('seed_memory_hbm',   'memory-hbm',   'Memory & HBM',                     'active', 'seed', 'Seed hypothesis: HBM demand is the near-term binding constraint on accelerator output.', 0.5),
('seed_data_centers', 'data-centers', 'Data Center Buildout',             'active', 'seed', 'Seed hypothesis: datacenter construction/cooling/REITs re-rate as cluster capex scales ~0.5 OOM/yr.', 0.5),
('seed_dc_energy',    'dc-energy',    'Energy for Data Centers',          'active', 'seed', 'Seed hypothesis: power is the single biggest supply-side constraint; generation and grid beneficiaries re-rate.', 0.5),
('seed_space',        'space',        'Space',                            'active', 'seed', 'Seed hypothesis: launch-cost decline compounds into new space infrastructure demand.', 0.5),
('seed_chips',        'chips',        'Semiconductors & Fab Chain',       'active', 'seed', 'Seed hypothesis: AI chip demand exceeds leading-edge capacity by 2028; fab chain must expand at multiples of historical pace.', 0.5);
