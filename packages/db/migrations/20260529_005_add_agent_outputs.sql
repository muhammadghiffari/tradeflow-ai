-- ═══════════════════════════════════════════════════════════════
-- TradeFlow AI — Migration: Add Multi-Agent OCR Fields (v5.2)
-- Migration: 20260529_005_add_agent_outputs.sql
-- SDD §3 — Multi-agent ensemble per-field storage
-- ═══════════════════════════════════════════════════════════════

-- Add agent_outputs and disagreement tracking to extracted_fields (FR-023)
ALTER TABLE extracted_fields
    ADD COLUMN IF NOT EXISTS agent_outputs     JSONB,
    ADD COLUMN IF NOT EXISTS agent_disagreement BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS all_agent_values  JSONB;

-- Update confidence_level generated column to include DISAGREEMENT level
-- (Drop and recreate since PostgreSQL doesn't support ALTER on generated columns)
ALTER TABLE extracted_fields
    DROP COLUMN IF EXISTS confidence_level;

ALTER TABLE extracted_fields
    ADD COLUMN confidence_level TEXT GENERATED ALWAYS AS (
        CASE
            WHEN agent_disagreement = TRUE         THEN 'DISAGREEMENT'
            WHEN confidence >= 0.90                THEN 'HIGH'
            WHEN confidence >= 0.70                THEN 'MEDIUM'
            WHEN confidence >  0.0                 THEN 'LOW'
            ELSE 'MISSING'
        END
    ) STORED;

-- Add index for disagreement lookups (for operator review filter)
CREATE INDEX IF NOT EXISTS idx_fields_disagreement
    ON extracted_fields(batch_id, agent_disagreement)
    WHERE agent_disagreement = TRUE;

CREATE INDEX IF NOT EXISTS idx_fields_batch_field
    ON extracted_fields(batch_id, ceisa_field);

-- Learning outcomes table (FR-084)
CREATE TABLE IF NOT EXISTS learning_outcomes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id        UUID REFERENCES batches(id),
    features        JSONB NOT NULL,     -- 32 XGBoost features snapshot at submission time
    label           BOOLEAN,            -- true=accepted, false=rejected
    ceisa_error_codes TEXT[],
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_learning_outcomes_label
    ON learning_outcomes(label, created_at DESC);

-- Model drift alerts table (FR-086)
CREATE TABLE IF NOT EXISTS model_drift_alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    field_name      TEXT NOT NULL,
    correction_count INTEGER NOT NULL,
    window_days     INTEGER DEFAULT 30,
    alert_sent      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Vessel validation issues (detailed, for review UI widget)
CREATE TABLE IF NOT EXISTS vessel_validation_issues (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id    UUID REFERENCES batches(id) ON DELETE CASCADE,
    severity    TEXT NOT NULL CHECK (severity IN ('CRITICAL','WARNING','INFO')),
    code        TEXT NOT NULL,   -- V001, V002, V003, V004
    message     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vvi_batch ON vessel_validation_issues(batch_id);
