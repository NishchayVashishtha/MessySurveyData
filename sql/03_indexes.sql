-- ==============================================================================
-- 03_indexes.sql
-- Performance optimization indexes: B-Tree, Composite, Covering, and GIN
-- ==============================================================================

-- 1. Foreign Key B-Tree Indexes on Fact Table
CREATE INDEX IF NOT EXISTS idx_fact_responses_respondent_key 
    ON warehouse.fact_responses (respondent_key);

CREATE INDEX IF NOT EXISTS idx_fact_responses_geography_key 
    ON warehouse.fact_responses (geography_key);

CREATE INDEX IF NOT EXISTS idx_fact_responses_occupation_key 
    ON warehouse.fact_responses (occupation_key);

CREATE INDEX IF NOT EXISTS idx_fact_responses_education_key 
    ON warehouse.fact_responses (education_key);

-- 2. Natural Key and Filtering Indexes
CREATE INDEX IF NOT EXISTS idx_fact_responses_batch_id 
    ON warehouse.fact_responses (batch_id);

CREATE INDEX IF NOT EXISTS idx_fact_responses_response_date 
    ON warehouse.fact_responses (response_date);

CREATE INDEX IF NOT EXISTS idx_fact_responses_party 
    ON warehouse.fact_responses (party_preference);

CREATE INDEX IF NOT EXISTS idx_fact_responses_rating 
    ON warehouse.fact_responses (rating_1_to_5);

CREATE INDEX IF NOT EXISTS idx_fact_responses_hash 
    ON warehouse.fact_responses (raw_record_hash);

-- 3. Composite & Covering Indexes for Analytic Aggregations
-- Covering index: enables index-only scans for geography-level sentiment queries
CREATE INDEX IF NOT EXISTS idx_fact_geo_date_covering 
    ON warehouse.fact_responses (geography_key, response_date) 
    INCLUDE (rating_1_to_5, monthly_income, response_quality_score);

-- Composite index for demographic income distribution
CREATE INDEX IF NOT EXISTS idx_fact_edu_income 
    ON warehouse.fact_responses (education_key, monthly_income)
    WHERE is_outlier_income = FALSE;

-- 4. Multi-Select Bridge Table Indexes
CREATE INDEX IF NOT EXISTS idx_choices_response_id 
    ON warehouse.fact_response_choices (response_id);

CREATE INDEX IF NOT EXISTS idx_choices_val 
    ON warehouse.fact_response_choices (choice_value);

-- 5. Full-Text Search GIN Index on Free-Text Survey Comments
CREATE INDEX IF NOT EXISTS idx_fact_comment_gin 
    ON warehouse.fact_responses USING gin (to_tsvector('english', COALESCE(free_text_comment, '')));

-- 6. Dimension Indexes for Filter Pushdown
CREATE INDEX IF NOT EXISTS idx_dim_geography_region 
    ON warehouse.dim_geography (region, state_name);

CREATE INDEX IF NOT EXISTS idx_dim_respondent_demographics 
    ON warehouse.dim_respondent (age_group, gender);

-- 7. Audit Schema Lookup Indexes
CREATE INDEX IF NOT EXISTS idx_audit_dq_batch 
    ON audit.data_quality_results (batch_id, passed);

CREATE INDEX IF NOT EXISTS idx_audit_rejected_batch 
    ON audit.rejected_rows (batch_id, rule_failed);
