-- ==============================================================================
-- 02_warehouse_tables.sql
-- Star Schema dimensional model, staging, and audit tables for survey responses
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. STAGING TABLE
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS staging.stg_survey_responses (
    stg_id SERIAL PRIMARY KEY,
    batch_id VARCHAR(100) NOT NULL,
    source_file VARCHAR(255) NOT NULL,
    respondent_id VARCHAR(100) NOT NULL,
    state VARCHAR(100),
    district VARCHAR(100),
    age INT,
    gender VARCHAR(50),
    education VARCHAR(100),
    occupation VARCHAR(100),
    monthly_income NUMERIC(12, 2),
    party_preference VARCHAR(100),
    rating_1_to_5 SMALLINT,
    response_date DATE,
    multi_select_choices TEXT, -- semicolon-separated
    free_text_comment TEXT,
    age_group VARCHAR(50),
    income_bracket VARCHAR(50),
    region VARCHAR(50),
    response_quality_score NUMERIC(5, 4),
    is_outlier_income BOOLEAN DEFAULT FALSE,
    is_outlier_age BOOLEAN DEFAULT FALSE,
    raw_record_hash VARCHAR(64) NOT NULL,
    loaded_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 2. WAREHOUSE DIMENSION TABLES
-- ------------------------------------------------------------------------------

-- Geography Dimension (canonical state and macro-region)
CREATE TABLE IF NOT EXISTS warehouse.dim_geography (
    geography_key SERIAL PRIMARY KEY,
    state_code VARCHAR(10),
    state_name VARCHAR(100) NOT NULL UNIQUE,
    region VARCHAR(50) NOT NULL,
    zone VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Occupation Dimension
CREATE TABLE IF NOT EXISTS warehouse.dim_occupation (
    occupation_key SERIAL PRIMARY KEY,
    occupation_title VARCHAR(100) NOT NULL UNIQUE,
    occupation_category VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Education Dimension
CREATE TABLE IF NOT EXISTS warehouse.dim_education (
    education_key SERIAL PRIMARY KEY,
    education_level VARCHAR(100) NOT NULL UNIQUE,
    education_tier VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Respondent Demographics Dimension (SCD Type 1 with natural key)
CREATE TABLE IF NOT EXISTS warehouse.dim_respondent (
    respondent_key SERIAL PRIMARY KEY,
    natural_respondent_id VARCHAR(100) NOT NULL UNIQUE,
    gender VARCHAR(50),
    age INT CHECK (age IS NULL OR (age >= 10 AND age <= 120)),
    age_group VARCHAR(50),
    district VARCHAR(100),
    first_seen_batch_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 3. WAREHOUSE FACT TABLES
-- ------------------------------------------------------------------------------

-- Primary Survey Response Fact Table
CREATE TABLE IF NOT EXISTS warehouse.fact_responses (
    response_id SERIAL PRIMARY KEY,
    natural_response_id VARCHAR(100) NOT NULL UNIQUE,
    respondent_key INT NOT NULL REFERENCES warehouse.dim_respondent(respondent_key),
    geography_key INT NOT NULL REFERENCES warehouse.dim_geography(geography_key),
    occupation_key INT NOT NULL REFERENCES warehouse.dim_occupation(occupation_key),
    education_key INT NOT NULL REFERENCES warehouse.dim_education(education_key),
    batch_id VARCHAR(100) NOT NULL,
    source_file VARCHAR(255) NOT NULL,
    response_date DATE NOT NULL,
    party_preference VARCHAR(100),
    monthly_income NUMERIC(12, 2),
    income_bracket VARCHAR(50),
    rating_1_to_5 SMALLINT CHECK (rating_1_to_5 IS NULL OR (rating_1_to_5 >= 1 AND rating_1_to_5 <= 5)),
    response_quality_score NUMERIC(5, 4) CHECK (response_quality_score BETWEEN 0.0 AND 1.0),
    is_outlier_income BOOLEAN DEFAULT FALSE,
    is_outlier_age BOOLEAN DEFAULT FALSE,
    free_text_comment TEXT,
    raw_record_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Child / Bridge Table for Multi-select Responses (e.g., Skills, Preferred Issues)
CREATE TABLE IF NOT EXISTS warehouse.fact_response_choices (
    choice_id SERIAL PRIMARY KEY,
    response_id INT NOT NULL REFERENCES warehouse.fact_responses(response_id) ON DELETE CASCADE,
    choice_category VARCHAR(50) NOT NULL DEFAULT 'multi_select',
    choice_value VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_response_choice UNIQUE (response_id, choice_category, choice_value)
);

-- ------------------------------------------------------------------------------
-- 4. AUDIT & QUALITY TABLES
-- ------------------------------------------------------------------------------

-- Pipeline Run Execution Log
CREATE TABLE IF NOT EXISTS audit.pipeline_runs (
    run_id SERIAL PRIMARY KEY,
    batch_id VARCHAR(100) NOT NULL UNIQUE,
    source_name VARCHAR(100) NOT NULL,
    source_file VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL, -- STARTED, EXTRACTED, CLEANED, VALIDATED, LOADED, FAILED
    records_extracted INT DEFAULT 0,
    records_loaded_mongo INT DEFAULT 0,
    records_cleaned INT DEFAULT 0,
    records_rejected INT DEFAULT 0,
    records_loaded_pg INT DEFAULT 0,
    duplicates_dropped INT DEFAULT 0,
    null_pct_before NUMERIC(5, 2),
    null_pct_after NUMERIC(5, 2),
    execution_time_seconds NUMERIC(10, 3),
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ
);

-- Rejected / Invalid Records with Rule Failure Trace
CREATE TABLE IF NOT EXISTS audit.rejected_rows (
    reject_id SERIAL PRIMARY KEY,
    batch_id VARCHAR(100) NOT NULL,
    natural_respondent_id VARCHAR(100),
    rule_failed VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL, -- ERROR, WARN
    failed_column VARCHAR(100),
    invalid_value TEXT,
    error_reason TEXT NOT NULL,
    raw_payload JSONB,
    rejected_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Data Quality Verification Checks Log
CREATE TABLE IF NOT EXISTS audit.data_quality_results (
    check_id SERIAL PRIMARY KEY,
    batch_id VARCHAR(100) NOT NULL,
    check_name VARCHAR(150) NOT NULL,
    target_table VARCHAR(100) NOT NULL,
    target_column VARCHAR(100),
    severity VARCHAR(20) NOT NULL, -- ERROR, WARN, INFO
    passed BOOLEAN NOT NULL,
    expected_condition TEXT,
    actual_value TEXT,
    failed_records_count INT DEFAULT 0,
    checked_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
