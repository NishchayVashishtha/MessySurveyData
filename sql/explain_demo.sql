-- ==============================================================================
-- explain_demo.sql
-- Demonstration of SQL Optimization & EXPLAIN (ANALYZE, BUFFERS) Benchmarking
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- QUERY 1: Selective Party Filtering (Sequential Scan vs B-Tree Index Scan)
-- ------------------------------------------------------------------------------

-- [UNOPTIMIZED] Full Sequential Scan across entire warehouse.fact_responses table
EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    f.response_id, 
    f.monthly_income, 
    f.rating_1_to_5, 
    g.state_name
FROM warehouse.fact_responses f
JOIN warehouse.dim_geography g ON f.geography_key = g.geography_key
WHERE f.party_preference = 'INC' AND f.is_outlier_income = FALSE;

-- [OPTIMIZED] Utilizes B-Tree Index (idx_fact_responses_party) + Primary Key Index Scan
EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    f.response_id, 
    f.monthly_income, 
    f.rating_1_to_5, 
    g.state_name
FROM warehouse.fact_responses f
JOIN warehouse.dim_geography g ON f.geography_key = g.geography_key
WHERE f.party_preference = 'INC' AND f.is_outlier_income = FALSE;


-- ------------------------------------------------------------------------------
-- QUERY 2: Multi-Select Category Share (Correlated Subquery vs Single-Pass Window)
-- ------------------------------------------------------------------------------

-- [UNOPTIMIZED] Correlated Subquery in SELECT clause (re-scans table for every category group)
EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    c.choice_category,
    c.choice_value,
    COUNT(*) AS choice_count,
    ROUND((COUNT(*)::numeric / (
        SELECT COUNT(*) 
        FROM warehouse.fact_response_choices sub 
        WHERE sub.choice_category = c.choice_category
    ) * 100), 2) AS category_pct
FROM warehouse.fact_response_choices c
GROUP BY c.choice_category, c.choice_value
ORDER BY c.choice_category, choice_count DESC;

-- [OPTIMIZED] Single-Pass Window Function Aggregate (avoids redundant full-table scans)
EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    choice_category,
    choice_value,
    COUNT(*) AS choice_count,
    ROUND((COUNT(*)::numeric / SUM(COUNT(*)) OVER (PARTITION BY choice_category) * 100), 2) AS category_pct
FROM warehouse.fact_response_choices
GROUP BY choice_category, choice_value
ORDER BY choice_category, choice_count DESC;


-- ------------------------------------------------------------------------------
-- QUERY 3: State-Wise Sentiment Ranking (Pre-Aggregated CTE vs Direct Window Scan)
-- ------------------------------------------------------------------------------

-- [UNOPTIMIZED] Direct window function over full join with repeated sorting passes
EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    g.region,
    g.state_name,
    COUNT(f.response_id) AS response_count,
    AVG(f.rating_1_to_5) AS avg_rating,
    RANK() OVER (PARTITION BY g.region ORDER BY AVG(f.rating_1_to_5) DESC) AS regional_rank,
    RANK() OVER (ORDER BY AVG(f.rating_1_to_5) DESC) AS national_rank,
    NTILE(4) OVER (ORDER BY AVG(f.rating_1_to_5) DESC) AS sentiment_quartile
FROM warehouse.fact_responses f
JOIN warehouse.dim_geography g ON f.geography_key = g.geography_key
WHERE f.rating_1_to_5 IS NOT NULL
GROUP BY g.region, g.state_name;

-- [OPTIMIZED] Materialized Aggregation Barrier in CTE prior to Window Evaluation
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
-- QUERY 4: Income Percentile Distribution by Education Tier (Outlier Filtered Scan)
-- ------------------------------------------------------------------------------

-- [UNOPTIMIZED] Unfiltered percentile calculation across all noisy records
EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    e.education_tier,
    COUNT(f.response_id) AS sample_size,
    ROUND(percentile_cont(0.50) WITHIN GROUP (ORDER BY f.monthly_income)::numeric, 2) AS median_income,
    ROUND(AVG(f.monthly_income)::numeric, 2) AS mean_income
FROM warehouse.fact_responses f
JOIN warehouse.dim_education e ON f.education_key = e.education_key
WHERE f.monthly_income IS NOT NULL
GROUP BY e.education_tier
ORDER BY median_income DESC;

-- [OPTIMIZED] Filtered Clean Sample with Composite Index Execution
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
