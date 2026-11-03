-- ==============================================================================
-- explain_demo.sql
-- Demonstration of SQL Optimization & EXPLAIN (ANALYZE, BUFFERS) Benchmarking
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- QUERY 1: Regional Demographic Sentiment Aggregation
-- ------------------------------------------------------------------------------

-- [UNOPTIMIZED] Forces Sequential Scan across fact_responses + SELECT * + unindexed joins
EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    g.region,
    g.state_name,
    AVG(f.rating_1_to_5) AS avg_rating,
    COUNT(*) AS count_ratings
FROM warehouse.fact_responses f
JOIN warehouse.dim_geography g ON f.geography_key = g.geography_key
WHERE f.response_date >= '2024-01-01'
GROUP BY g.region, g.state_name;

-- [OPTIMIZED] Uses Covering Index (idx_fact_geo_date_covering) for Index-Only Scan
EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    g.region,
    g.state_name,
    ROUND(AVG(f.rating_1_to_5)::numeric, 2) AS avg_rating,
    COUNT(f.response_id) AS count_ratings
FROM warehouse.dim_geography g
JOIN warehouse.fact_responses f ON f.geography_key = g.geography_key
WHERE f.response_date >= '2024-01-01'
GROUP BY g.region, g.state_name;

-- ------------------------------------------------------------------------------
-- QUERY 2: Multi-Select Skill Popularity Ranking (Correlated Subquery vs CTE Join)
-- ------------------------------------------------------------------------------

-- [UNOPTIMIZED] Uses Correlated Subquery for calculating percentage of total
EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    c.choice_value,
    COUNT(*) AS cnt,
    (COUNT(*)::float / (SELECT COUNT(*) FROM warehouse.fact_responses) * 100) AS pct
FROM warehouse.fact_response_choices c
GROUP BY c.choice_value
ORDER BY cnt DESC;

-- [OPTIMIZED] Uses Single Shared CTE with Cross Join & Indexed Lookup
EXPLAIN (ANALYZE, BUFFERS)
WITH total_universe AS (
    SELECT COUNT(DISTINCT response_id) AS total_respondents 
    FROM warehouse.fact_responses
)
SELECT 
    c.choice_value,
    COUNT(c.response_id) AS selection_count,
    ROUND((COUNT(c.response_id)::numeric / u.total_respondents * 100), 2) AS selection_pct
FROM warehouse.fact_response_choices c
CROSS JOIN total_universe u
GROUP BY c.choice_value, u.total_respondents
ORDER BY selection_count DESC;

-- ------------------------------------------------------------------------------
-- QUERY 3: State-Wise Sentiment Ranking using Window Functions
-- ------------------------------------------------------------------------------

-- [OPTIMIZED] Window Partitioning with Covering Index on Geography & Rating
EXPLAIN (ANALYZE, BUFFERS)
WITH state_summary AS (
    SELECT 
        g.region,
        g.state_name,
        COUNT(f.response_id) AS response_count,
        AVG(f.rating_1_to_5) AS avg_rating
    FROM warehouse.fact_responses f
    JOIN warehouse.dim_geography g ON f.geography_key = g.geography_key
    WHERE f.rating_1_to_5 IS NOT NULL
    GROUP BY g.region, g.state_name
)
SELECT 
    region,
    state_name,
    response_count,
    ROUND(avg_rating::numeric, 2) AS avg_rating,
    RANK() OVER (PARTITION BY region ORDER BY avg_rating DESC) AS regional_rank,
    RANK() OVER (ORDER BY avg_rating DESC) AS national_rank,
    NTILE(4) OVER (ORDER BY avg_rating DESC) AS sentiment_quartile
FROM state_summary
ORDER BY national_rank ASC;

-- ------------------------------------------------------------------------------
-- QUERY 4: Income Percentile Distribution by Education Tier
-- ------------------------------------------------------------------------------

-- [OPTIMIZED] Utilizes Composite Partial Index (idx_fact_edu_income WHERE is_outlier_income = FALSE)
EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    e.education_tier,
    COUNT(f.response_id) AS clean_sample,
    ROUND(percentile_cont(0.50) WITHIN GROUP (ORDER BY f.monthly_income)::numeric, 2) AS median_income,
    ROUND(AVG(f.monthly_income)::numeric, 2) AS mean_income
FROM warehouse.fact_responses f
JOIN warehouse.dim_education e ON f.education_key = e.education_key
WHERE f.is_outlier_income = FALSE AND f.monthly_income IS NOT NULL
GROUP BY e.education_tier
ORDER BY median_income DESC;
