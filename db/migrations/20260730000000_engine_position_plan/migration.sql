-- Phase C (audit surface): persist the memo's position plan on the position.
-- The plan (ladder rungs, thesis_break, exit posture) has been validated and
-- dropped since PR #27; from this migration on it lands at fill time and the
-- crowded-winner review's "what was our plan entering?" has something to read.
ALTER TABLE "EnginePosition" ADD COLUMN "positionPlan" JSONB;
