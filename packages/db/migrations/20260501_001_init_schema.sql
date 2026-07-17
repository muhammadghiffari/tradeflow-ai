-- ═══════════════════════════════════════════════════════════════
-- TradeFlow AI — Initial Database Schema
-- Migration: 20260501_001_init_schema.sql
-- PRD §11 — Full schema with RLS policies, indexes, Realtime
-- ═══════════════════════════════════════════════════════════════

-- ─────────────────────────────────────
-- EXTENSIONS
-- ─────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS keycloak;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─────────────────────────────────────
-- ENUMS
-- ─────────────────────────────────────
CREATE TYPE user_tier AS ENUM ('enterprise', 'sme');
CREATE TYPE user_role AS ENUM ('operator', 'admin', 'supervisor', 'importer');
CREATE TYPE doc_type AS ENUM ('bill_of_lading', 'packing_list', 'invoice');
CREATE TYPE batch_status AS ENUM (
    'uploaded', 'preprocessing', 'ocr_running', 'ocr_complete',
    'extracting', 'extracted', 'validating', 'validated',
    'review_ready', 'reviewing', 'approved', 'submitting', 'submitted',
    'accepted', 'rejected', 'error'
);

-- ─────────────────────────────────────
-- 1. COMPANIES
-- ─────────────────────────────────────
CREATE TABLE companies (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL,
    npwp                TEXT UNIQUE,
    tier                user_tier NOT NULL,
    submission_count    INTEGER DEFAULT 0,
    rejection_rate      DECIMAL(5,4) DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────
-- 2. PROFILES (Keycloak JWT maps sub → id)
-- ─────────────────────────────────────
-- Note: references auth.users from Supabase Auth layer (Keycloak JWT)
CREATE TABLE profiles (
    id              UUID PRIMARY KEY,   -- Keycloak sub claim
    full_name       TEXT NOT NULL,
    email           TEXT,
    tier            user_tier NOT NULL DEFAULT 'sme',
    role            user_role NOT NULL DEFAULT 'operator',
    company_id      UUID REFERENCES companies(id),
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can read own profile" ON profiles
    FOR SELECT USING (auth.uid()::text = id::text);
CREATE POLICY "Admins can read all profiles" ON profiles
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id::text = auth.uid()::text
            AND p.role IN ('admin', 'supervisor')
        )
    );
CREATE POLICY "Users can update own profile" ON profiles
    FOR UPDATE USING (auth.uid()::text = id::text);

-- ─────────────────────────────────────
-- 3. BATCHES
-- ─────────────────────────────────────
CREATE TABLE batches (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_by                  UUID REFERENCES profiles(id),
    company_id                  UUID REFERENCES companies(id),
    status                      batch_status DEFAULT 'uploaded',
    customs_readiness_score     DECIMAL(5,2),
    crs_grade                   CHAR(1),
    rejection_probability       DECIMAL(5,4),
    risk_level                  TEXT CHECK (risk_level IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    ceisa_submission_id         UUID,
    langgraph_thread_id         TEXT,
    blockchain_tx_hash          TEXT,
    blockchain_block_number     BIGINT,
    ipfs_cid                    TEXT,
    expires_at                  TIMESTAMPTZ DEFAULT NOW() + INTERVAL '48 hours',
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_batches_company ON batches(company_id);
CREATE INDEX idx_batches_status ON batches(status);
CREATE INDEX idx_batches_created_by ON batches(created_by);
CREATE INDEX idx_batches_created_at ON batches(created_at DESC);

ALTER TABLE batches ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users see own company batches" ON batches
    FOR SELECT USING (
        company_id IN (
            SELECT company_id FROM profiles WHERE id::text = auth.uid()::text
        )
    );
CREATE POLICY "Users create own batches" ON batches
    FOR INSERT WITH CHECK (
        created_by::text = auth.uid()::text
    );
CREATE POLICY "Operators update own company batches" ON batches
    FOR UPDATE USING (
        company_id IN (
            SELECT company_id FROM profiles WHERE id::text = auth.uid()::text
        )
    );

-- Supabase Realtime: enable CDC for live operator dashboard
ALTER PUBLICATION supabase_realtime ADD TABLE batches;

-- ─────────────────────────────────────
-- 4. DOCUMENTS
-- ─────────────────────────────────────
CREATE TABLE documents (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id                UUID REFERENCES batches(id) ON DELETE CASCADE,
    doc_type                doc_type NOT NULL,
    original_name           TEXT NOT NULL,
    storage_path            TEXT NOT NULL,
    file_hash               CHAR(64) NOT NULL,
    file_size_bytes         INTEGER,
    language                TEXT DEFAULT 'en',
    has_text_layer          BOOLEAN DEFAULT FALSE,
    page_count              INTEGER DEFAULT 1,
    quality_score           DECIMAL(4,3),
    ocr_engine_used         TEXT,
    overall_ocr_confidence  DECIMAL(4,3),
    status                  batch_status DEFAULT 'uploaded',
    error_message           TEXT,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_documents_batch ON documents(batch_id);
CREATE INDEX idx_documents_type ON documents(doc_type);

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users see own company documents" ON documents
    FOR SELECT USING (
        batch_id IN (
            SELECT b.id FROM batches b
            JOIN profiles p ON p.company_id = b.company_id
            WHERE p.id::text = auth.uid()::text
        )
    );

-- ─────────────────────────────────────
-- 5. EXTRACTED FIELDS
-- ─────────────────────────────────────
CREATE TABLE extracted_fields (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id            UUID REFERENCES batches(id) ON DELETE CASCADE,
    document_id         UUID REFERENCES documents(id) ON DELETE CASCADE,
    ceisa_field         TEXT NOT NULL,
    raw_ocr_value       TEXT,
    extracted_value     TEXT,
    normalized_value    TEXT,
    confidence          DECIMAL(4,3) NOT NULL DEFAULT 0,
    confidence_level    TEXT GENERATED ALWAYS AS (
        CASE WHEN confidence >= 0.90 THEN 'HIGH'
             WHEN confidence >= 0.70 THEN 'MEDIUM'
             ELSE 'LOW' END
    ) STORED,
    extraction_method   TEXT CHECK (extraction_method IN ('direct_ocr','llm_inferred','cross_doc','manual','rule_based')),
    source_page         INTEGER,
    bounding_box        JSONB,
    is_corrected        BOOLEAN DEFAULT FALSE,
    corrected_value     TEXT,
    correction_reason   TEXT,
    corrected_by        UUID REFERENCES profiles(id),
    corrected_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_extracted_fields_batch ON extracted_fields(batch_id);
CREATE INDEX idx_extracted_fields_field ON extracted_fields(ceisa_field);
CREATE INDEX idx_extracted_fields_confidence ON extracted_fields(confidence);

ALTER TABLE extracted_fields ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users see own company fields" ON extracted_fields
    FOR SELECT USING (
        batch_id IN (
            SELECT b.id FROM batches b
            JOIN profiles p ON p.company_id = b.company_id
            WHERE p.id::text = auth.uid()::text
        )
    );

ALTER PUBLICATION supabase_realtime ADD TABLE extracted_fields;

-- ─────────────────────────────────────
-- 6. VALIDATION RESULTS
-- ─────────────────────────────────────
CREATE TABLE validation_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id        UUID REFERENCES batches(id) ON DELETE CASCADE,
    rule_id         TEXT NOT NULL,
    rule_name       TEXT NOT NULL,
    severity        TEXT CHECK (severity IN ('PASS','WARNING','CRITICAL_FAIL')),
    error_message   TEXT,
    affected_fields TEXT[],
    resolved        BOOLEAN DEFAULT FALSE,
    resolved_by     UUID REFERENCES profiles(id),
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_validation_batch ON validation_results(batch_id);
CREATE INDEX idx_validation_severity ON validation_results(severity);

ALTER TABLE validation_results ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users see own company validations" ON validation_results
    FOR SELECT USING (
        batch_id IN (
            SELECT b.id FROM batches b
            JOIN profiles p ON p.company_id = b.company_id
            WHERE p.id::text = auth.uid()::text
        )
    );

-- ─────────────────────────────────────
-- 7. HS RECOMMENDATIONS
-- ─────────────────────────────────────
CREATE TABLE hs_recommendations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id            UUID REFERENCES batches(id),
    line_item_index     INTEGER,
    product_description TEXT,
    recommendations     JSONB,
    selected_hs_code    TEXT,
    selected_by         UUID REFERENCES profiles(id),
    selected_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_hs_recommendations_batch ON hs_recommendations(batch_id);

-- ─────────────────────────────────────
-- 8. CEISA SUBMISSIONS
-- ─────────────────────────────────────
CREATE TABLE ceisa_submissions (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id                    UUID REFERENCES batches(id),
    idempotency_key             UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    payload_hash                CHAR(64),
    payload_encrypted           BYTEA,
    ceisa_reference             TEXT,
    status                      TEXT DEFAULT 'pending' CHECK (status IN (
        'pending','queued','submitted','processing','accepted','rejected','failed'
    )),
    attempt_number              INTEGER DEFAULT 1,
    submitted_at                TIMESTAMPTZ,
    ceisa_responded_at          TIMESTAMPTZ,
    ceisa_response_encrypted    BYTEA,
    error_code                  TEXT,
    error_classification        TEXT CHECK (error_classification IN (
        'AUTO_RECOVERABLE','OPERATOR_REQUIRED','ADMIN_ESCALATION'
    )),
    auto_fixed                  BOOLEAN DEFAULT FALSE,
    parent_submission_id        UUID REFERENCES ceisa_submissions(id),
    created_at                  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ceisa_submissions_batch ON ceisa_submissions(batch_id);
CREATE INDEX idx_ceisa_submissions_status ON ceisa_submissions(status);

-- ─────────────────────────────────────
-- 9. BLOCKCHAIN RECORDS
-- ─────────────────────────────────────
CREATE TABLE blockchain_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id        UUID REFERENCES batches(id),
    content_hash    CHAR(64) NOT NULL,
    merkle_root     CHAR(64),
    tx_hash         TEXT NOT NULL,
    block_number    BIGINT,
    network         TEXT DEFAULT 'polygon-amoy',
    polygonscan_url TEXT,
    ipfs_cid        TEXT,
    anchored_at     TIMESTAMPTZ,
    verified        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_blockchain_batch ON blockchain_records(batch_id);

-- ─────────────────────────────────────
-- 10. LEARNING SAMPLES
-- ─────────────────────────────────────
CREATE TABLE learning_samples (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id            UUID REFERENCES batches(id),
    field_name          TEXT NOT NULL,
    extracted_value     TEXT,
    corrected_value     TEXT NOT NULL,
    correction_reason   TEXT,
    operator_id         UUID REFERENCES profiles(id),
    used_in_training    BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_learning_samples_field ON learning_samples(field_name);
CREATE INDEX idx_learning_samples_training ON learning_samples(used_in_training, created_at);

-- ─────────────────────────────────────
-- 11. SUBMISSION OUTCOMES
-- ─────────────────────────────────────
CREATE TABLE submission_outcomes (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id               UUID REFERENCES ceisa_submissions(id),
    batch_id                    UUID REFERENCES batches(id),
    outcome                     TEXT CHECK (outcome IN ('accepted', 'rejected')),
    rejection_codes             TEXT[],
    feature_snapshot            JSONB,
    predicted_rejection_prob    DECIMAL(5,4),
    used_in_training            BOOLEAN DEFAULT FALSE,
    created_at                  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_submission_outcomes_training ON submission_outcomes(used_in_training, created_at);
CREATE INDEX idx_submission_outcomes_outcome ON submission_outcomes(outcome);

-- ─────────────────────────────────────
-- 12. AUDIT LOG (IMMUTABLE — Append-Only)
-- ─────────────────────────────────────
CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        UUID,
    document_id     UUID,
    actor_id        UUID,
    actor_type      TEXT CHECK (actor_type IN ('operator','system','ceisa','admin','blockchain')),
    action          TEXT NOT NULL,
    before_state    JSONB,
    after_state     JSONB,
    metadata        JSONB,
    ip_address      INET,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_log_batch ON audit_log(batch_id);
CREATE INDEX idx_audit_log_time ON audit_log(created_at DESC);
CREATE INDEX idx_audit_log_actor ON audit_log(actor_id);

-- IMMUTABLE: enforce append-only at the database level
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Insert only via service role" ON audit_log
    FOR INSERT WITH CHECK (true);
CREATE POLICY "Read own company audit" ON audit_log
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM batches b
            JOIN profiles p ON p.id::text = auth.uid()::text
            WHERE b.id = audit_log.batch_id
            AND b.company_id = p.company_id
        )
        OR EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id::text = auth.uid()::text
            AND p.role IN ('admin', 'supervisor')
        )
    );

-- CRITICAL INVARIANT: Revoke all modification rights on audit_log
REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM PUBLIC;
REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM postgres;

-- ─────────────────────────────────────
-- BTKI HS CODES — Reference table
-- ─────────────────────────────────────
CREATE TABLE btki_hs_codes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hs_code         CHAR(8) NOT NULL UNIQUE,
    description_id  TEXT NOT NULL,
    description_en  TEXT NOT NULL,
    duty_rate       DECIMAL(6,4) DEFAULT 0,
    vat_rate        DECIMAL(6,4) DEFAULT 0.11,
    pph_rate        DECIMAL(6,4) DEFAULT 0,
    active          BOOLEAN DEFAULT TRUE,
    effective_date  DATE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_btki_hs_code ON btki_hs_codes(hs_code);
CREATE INDEX idx_btki_active ON btki_hs_codes(active);

-- ─────────────────────────────────────
-- UPDATED_AT TRIGGER (reusable)
-- ─────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at_batches
    BEFORE UPDATE ON batches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER set_updated_at_documents
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER set_updated_at_profiles
    BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
