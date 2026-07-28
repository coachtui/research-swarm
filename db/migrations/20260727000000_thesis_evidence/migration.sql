-- db/migrations/20260727000000_thesis_evidence/migration.sql
ALTER TABLE "ThemeBasket" ADD COLUMN "stage" TEXT;

CREATE TABLE "ThesisEvidence" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "kind" TEXT NOT NULL,
    "themeSlug" TEXT,
    "hypothesisKey" TEXT,
    "week" TEXT NOT NULL,
    "stage" TEXT,
    "body" JSONB NOT NULL,
    CONSTRAINT "ThesisEvidence_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "ThesisEvidence_themeSlug_createdAt_idx"
    ON "ThesisEvidence"("themeSlug", "createdAt");
CREATE INDEX "ThesisEvidence_kind_createdAt_idx"
    ON "ThesisEvidence"("kind", "createdAt");
