-- ==============================================================================
-- 04_analytics_views.sql
-- Curated analytics views with window functions and statistical percentiles
-- ==============================================================================

-- 1. Response Volume & Sentiment by Macro-Region and State
CREATE OR REPLACE VIEW analytics.v_response_counts_by_geography AS
SELECT 
    g.region,
    g.state_name,
    COUNT(f.response_id) AS total_responses,
    COUNT(DISTINCT f.respondent_key) AS unique_respondents,
    ROUND(AVG(f.rating_1_to_5)::numeric, 2) AS avg_rating,
    ROUND(AVG(f.response_quality_score)::numeric, 4) AS avg_quality_score,
    ROUND(AVG(f.monthly_income) FILTER (WHERE f.is_outlier_income = FALSE)::numeric, 2) AS avg_monthly_income
FROM warehouse.fact_responses f
JOIN warehouse.dim_geography g ON f.geography_key = g.geography_key
GROUP BY g.region, g.state_name
ORDER BY g.region, total_responses DESC;

-- 2. Average Rating and Quality by Demographic Group (Age Group & Gender)
CREATE OR REPLACE VIEW analytics.v_demographic_sentiment AS
SELECT 
    COALESCE(r.age_group, 'Unknown') AS age_group,
    COALESCE(r.gender, 'Not Specified') AS gender,
    COUNT(f.response_id) AS response_count,
    ROUND(AVG(f.rating_1_to_5)::numeric, 2) AS avg_rating,
    ROUND(STDDEV_SAMP(f.rating_1_to_5)::numeric, 2) AS rating_stddev,
    ROUND(AVG(f.response_quality_score)::numeric, 4) AS avg_quality_score
FROM warehouse.fact_responses f
JOIN warehouse.dim_respondent r ON f.respondent_key = r.respondent_key
GROUP BY r.age_group, r.gender
ORDER BY r.age_group, response_count DESC;

-- 3. Income Distribution by Education Level (Continuous Percentiles p25, p50/Median, p75)
CREATE OR REPLACE VIEW analytics.v_income_distribution_by_education AS
SELECT 
    e.education_level,
    e.education_tier,
    COUNT(f.response_id) AS sample_size,
    ROUND(AVG(f.monthly_income)::numeric, 2) AS mean_income,
    ROUND(percentile_cont(0.25) WITHIN GROUP (ORDER BY f.monthly_income)::numeric, 2) AS p25_income,
    ROUND(percentile_cont(0.50) WITHIN GROUP (ORDER BY f.monthly_income)::numeric, 2) AS median_income,
    ROUND(percentile_cont(0.75) WITHIN GROUP (ORDER BY f.monthly_income)::numeric, 2) AS p75_income,
    ROUND((percentile_cont(0.75) WITHIN GROUP (ORDER BY f.monthly_income) - 
           percentile_cont(0.25) WITHIN GROUP (ORDER BY f.monthly_income))::numeric, 2) AS iqr_income
FROM warehouse.fact_responses f
JOIN warehouse.dim_education e ON f.education_key = e.education_key
WHERE f.is_outlier_income = FALSE AND f.monthly_income IS NOT NULL
GROUP BY e.education_level, e.education_tier
ORDER BY median_income DESC;

-- 4. Top Choices from Exploded Multi-Select Answers (Skills / Issues)
CREATE OR REPLACE VIEW analytics.v_top_multiselect_choices AS
WITH total_respondents AS (
    SELECT COUNT(DISTINCT response_id) AS total_count FROM warehouse.fact_responses
)
SELECT 
    c.choice_category,
    c.choice_value,
    COUNT(c.response_id) AS selection_count,
    ROUND(
        (COUNT(c.response_id)::numeric / NULLIF((SELECT total_count FROM total_respondents), 0) * 100), 
        2
    ) AS pct_of_all_respondents,
    ROUND(AVG(f.rating_1_to_5)::numeric, 2) AS avg_rating_of_selectors
FROM warehouse.fact_response_choices c
JOIN warehouse.fact_responses f ON c.response_id = f.response_id
GROUP BY c.choice_category, c.choice_value
ORDER BY selection_count DESC;

-- 5. Response Quality and Outlier Summary by Source and Batch
CREATE OR REPLACE VIEW analytics.v_response_quality_by_batch AS
SELECT 
    f.batch_id,
    f.source_file,
    COUNT(f.response_id) AS clean_records_loaded,
    ROUND(AVG(f.response_quality_score)::numeric, 4) AS mean_quality_score,
    ROUND(MIN(f.response_quality_score)::numeric, 4) AS min_quality_score,
    COUNT(CASE WHEN f.is_outlier_income THEN 1 END) AS income_outlier_count,
    COUNT(CASE WHEN f.is_outlier_age THEN 1 END) AS age_outlier_count,
    COUNT(CASE WHEN f.free_text_comment IS NOT NULL AND f.free_text_comment <> '' THEN 1 END) AS responses_with_comments
FROM warehouse.fact_responses f
GROUP BY f.batch_id, f.source_file
ORDER BY f.batch_id DESC;

-- 6. State-Wise Sentiment Ranking using Window Functions (RANK and NTILE)
CREATE OR REPLACE VIEW analytics.v_state_ranking_window AS
WITH state_aggregates AS (
    SELECT 
        g.region,
        g.state_name,
        COUNT(f.response_id) AS response_count,
        ROUND(AVG(f.rating_1_to_5)::numeric, 2) AS avg_rating,
        ROUND(AVG(f.response_quality_score)::numeric, 4) AS avg_quality_score
    FROM warehouse.fact_responses f
    JOIN warehouse.dim_geography g ON f.geography_key = g.geography_key
    WHERE f.rating_1_to_5 IS NOT NULL
    GROUP BY g.region, g.state_name
    HAVING COUNT(f.response_id) >= 5 -- suppress low-sample noise
)
SELECT 
    region,
    state_name,
    response_count,
    avg_rating,
    avg_quality_score,
    RANK() OVER (PARTITION BY region ORDER BY avg_rating DESC) AS regional_sentiment_rank,
    RANK() OVER (ORDER BY avg_rating DESC) AS national_sentiment_rank,
    NTILE(4) OVER (ORDER BY avg_rating DESC) AS sentiment_quartile -- 1 = Top 25%, 4 = Bottom 25%
FROM state_aggregates
ORDER BY national_sentiment_rank ASC;
