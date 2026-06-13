-- ═══════════════════════════════════════════════════════════════
-- TradeFlow AI — Migration: Add Maritime Tables (v5.2)
-- Migration: 20260522_004_add_maritime_tables.sql
-- SDD §3 — Maritime data for VesselValidationAgent
-- ═══════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────
-- AIS Vessel Positions
-- Source: AIS_Data_Sample.csv (deleted) → seeded via seed_maritime.py
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ais_vessel_positions (
    id              BIGSERIAL PRIMARY KEY,
    vessel_name     TEXT,
    imo             TEXT NOT NULL,
    mmsi            TEXT,
    latitude        DECIMAL(10,6),
    longitude       DECIMAL(10,6),
    speed_knots     DECIMAL(5,2),
    heading         INTEGER CHECK (heading BETWEEN 0 AND 359),
    destination     TEXT,
    eta             TIMESTAMPTZ,
    nav_status      INTEGER,
    timestamp       TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ais_imo_timestamp
    ON ais_vessel_positions(imo, timestamp);
CREATE INDEX IF NOT EXISTS idx_ais_imo ON ais_vessel_positions(imo);
CREATE INDEX IF NOT EXISTS idx_ais_name ON ais_vessel_positions(LOWER(vessel_name));
CREATE INDEX IF NOT EXISTS idx_ais_timestamp ON ais_vessel_positions(timestamp DESC);

-- ─────────────────────────────────────────────────────────────
-- Vessel Characteristics
-- Source: Website_Vessel_Characteristics_Sample.xlsx (deleted)
-- → seeded via seed_maritime.py
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vessel_characteristics (
    id                  BIGSERIAL PRIMARY KEY,
    imo_number          TEXT UNIQUE NOT NULL,
    vessel_name         TEXT NOT NULL,
    call_sign           TEXT,
    vessel_type_code    TEXT,
    subtype_code        TEXT,
    flag_code           CHAR(2),
    built_year          INTEGER,
    dead_year           INTEGER,          -- NULL if still active
    trading_status      TEXT,             -- 'Trdg' = trading, etc.
    gross_tonnage       INTEGER,
    deadweight_tonnage  INTEGER,
    registered_owner    TEXT,
    raw_data            JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vc_imo ON vessel_characteristics(imo_number);
CREATE INDEX IF NOT EXISTS idx_vc_name ON vessel_characteristics(LOWER(vessel_name));
CREATE INDEX IF NOT EXISTS idx_vc_status ON vessel_characteristics(trading_status);

-- ─────────────────────────────────────────────────────────────
-- Vessel Ownership
-- Source: Ownership_-_Website_Data_Sample.xlsx (deleted)
-- → seeded via seed_maritime.py
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vessel_ownership (
    id                          BIGSERIAL PRIMARY KEY,
    imo_number                  TEXT NOT NULL,
    commercial_owner            TEXT,
    commercial_owner_country    TEXT,
    effective_control           TEXT,
    technical_manager           TEXT,
    financial_owner             TEXT,
    flag                        TEXT,
    effective_date              DATE,
    created_at                  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vo_imo ON vessel_ownership(imo_number);

-- ─────────────────────────────────────────────────────────────
-- Port Lineup
-- Source: Lineup_Data_Sample.csv (deleted) → seeded via seed_maritime.py
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS port_lineup (
    id              BIGSERIAL PRIMARY KEY,
    imo             TEXT NOT NULL,
    vessel_name     TEXT,
    port_locode     TEXT NOT NULL,
    port_name       TEXT,
    country         TEXT,
    eta             TIMESTAMPTZ,
    etd             TIMESTAMPTZ,
    voyage_number   TEXT,
    service_name    TEXT,
    cargo_type      TEXT,
    cargo_quantity  DECIMAL,
    cargo_uom       TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lineup_imo ON port_lineup(imo);
CREATE INDEX IF NOT EXISTS idx_lineup_locode ON port_lineup(port_locode);
CREATE INDEX IF NOT EXISTS idx_lineup_eta ON port_lineup(eta);

-- ─────────────────────────────────────────────────────────────
-- Update batches table with v5.2 fields
-- ─────────────────────────────────────────────────────────────
ALTER TABLE batches
    ADD COLUMN IF NOT EXISTS ceisa_aju_number        TEXT UNIQUE,
    ADD COLUMN IF NOT EXISTS ceisa_reference         TEXT,
    ADD COLUMN IF NOT EXISTS crs_components          JSONB,
    ADD COLUMN IF NOT EXISTS ocr_model_version       TEXT DEFAULT 'olm-ocr-cipl-v1',
    ADD COLUMN IF NOT EXISTS agent_agreement_rate    DECIMAL(4,3),
    ADD COLUMN IF NOT EXISTS vessel_validation_status TEXT CHECK (
        vessel_validation_status IN ('passed','warning','info','critical')
    ),
    ADD COLUMN IF NOT EXISTS vessel_validation_details JSONB,
    ADD COLUMN IF NOT EXISTS insw_status             TEXT;

-- Add composite indexes for query performance
CREATE INDEX IF NOT EXISTS idx_batches_company_status
    ON batches(company_id, status);
CREATE INDEX IF NOT EXISTS idx_batches_created_desc
    ON batches(created_at DESC);

-- Add carrier_scac to documents for carrier profile routing (FR-119)
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS carrier_scac        TEXT,
    ADD COLUMN IF NOT EXISTS processing_route    TEXT CHECK (
        processing_route IN ('FAST_PATH','STANDARD','DEGRADED')
    );

ALTER PUBLICATION supabase_realtime ADD TABLE validation_results;
ALTER PUBLICATION supabase_realtime ADD TABLE ceisa_submissions;
