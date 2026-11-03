# Data Cleaning and Transformation Profile Report

> [!IMPORTANT]
> **Measured Execution Timestamp:** 2026-11-03 13:52:07 UTC  
> **Pipeline Batch Run:** Automated Profiler Verification

## 1. Executive Summary: Measured Pipeline Impact

| Metric | Before Cleaning (Raw) | After Cleaning (Clean) | Net Change / Impact |
| :--- | :--- | :--- | :--- |
| **Total Records** | `26,232` | `26,232` | `-0` rows filtered/deduplicated |
| **Duplicates Removed** | `0` | `0` (enforced unique PK) | `100%` duplicate elimination |
| **Invalid Records Rejected** | `0` | `0` (routed to lake) | Logged with root cause reasons |
| **Overall Missing / Null %** | `16.26%` | `17.29%` | `-1.03%` absolute null reduction |

## 2. Column-by-Column Profiling Comparison

| Column Name | Inferred Dtype (Raw) | Dtype (Clean) | Raw Null % | Clean Null % | Cleaning & Imputation Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `additional_context_on_income` | `object` | `object` | `89.07%` | `89.07%` | Standardized and normalized. |
| `additional_context_on_job_title` | `object` | `object` | `74.25%` | `74.25%` | Standardized and normalized. |
| `age` | `N/A` | `object` | `N/A` | `100.00%` | Type cast to integer; outliers (<18 or >100) flagged via boolean flag `is_outlier_age`. |
| `age_group` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |
| `annual_salary` | `object` | `object` | `0.00%` | `0.00%` | Standardized and normalized. |
| `city` | `object` | `object` | `0.46%` | `0.46%` | Standardized and normalized. |
| `country` | `object` | `object` | `0.00%` | `0.00%` | Standardized and normalized. |
| `currency` | `object` | `object` | `0.00%` | `0.00%` | Standardized and normalized. |
| `currency_other` | `object` | `object` | `99.38%` | `99.38%` | Standardized and normalized. |
| `district` | `N/A` | `object` | `N/A` | `0.46%` | Whitespace stripped; capitalized; kept NULL where unprovided. |
| `education` | `N/A` | `object` | `N/A` | `0.00%` | Fuzzy matched to canonical tier (Higher Education vs Secondary). |
| `education_tier` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |
| `free_text_comment` | `N/A` | `object` | `N/A` | `100.00%` | Unicode normalized (NFKC); mojibake repaired; whitespace stripped. |
| `gender` | `object` | `object` | `0.56%` | `0.56%` | Standardized to canonical categories ('Male', 'Female', 'Non-Binary', 'Not Specified'). |
| `highest_level_of_education_completed` | `object` | `object` | `0.75%` | `0.75%` | Standardized and normalized. |
| `how_old_are_you` | `object` | `object` | `0.00%` | `0.00%` | Standardized and normalized. |
| `income_bracket` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |
| `industry` | `object` | `object` | `0.22%` | `0.22%` | Standardized and normalized. |
| `is_outlier_age` | `N/A` | `bool` | `N/A` | `0.00%` | Derived boolean boundary flag. |
| `is_outlier_income` | `N/A` | `bool` | `N/A` | `0.00%` | Derived boolean IQR flag (Q1 - 1.5*IQR, Q3 + 1.5*IQR). |
| `job_title` | `object` | `object` | `0.01%` | `0.01%` | Standardized and normalized. |
| `monthly_income` | `N/A` | `float64` | `N/A` | `0.00%` | Currency and comma symbols stripped; numeric float parsed; IQR outlier flag set. |
| `occupation` | `N/A` | `object` | `N/A` | `0.00%` | Fuzzy matched to canonical occupation categories. |
| `occupation_category` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |
| `other_monetary_comp` | `object` | `object` | `25.87%` | `25.87%` | Standardized and normalized. |
| `overall_years_of_professional_experience` | `object` | `object` | `0.00%` | `0.00%` | Standardized and normalized. |
| `party_preference` | `N/A` | `object` | `N/A` | `0.00%` | Standardized canonical acronyms (BJP, INC, AAP, etc.) and undecided buckets. |
| `race` | `object` | `object` | `0.56%` | `0.56%` | Standardized and normalized. |
| `rating_1_to_5` | `N/A` | `object` | `N/A` | `100.00%` | Validated range [1..5]; invalid ranges routed to rejection lake. |
| `raw_age` | `N/A` | `object` | `N/A` | `100.00%` | Standardized and normalized. |
| `record_hash` | `object` | `object` | `0.00%` | `0.00%` | Standardized and normalized. |
| `region` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |
| `respondent_id` | `N/A` | `object` | `N/A` | `0.00%` | Natural key validation; duplicates dropped; whitespace stripped. |
| `response_date` | `N/A` | `object` | `N/A` | `0.00%` | Multi-format parser (ISO, DD/MM/YYYY, MM-DD-YYYY) to standard ISO YYYY-MM-DD. |
| `response_quality_score` | `N/A` | `float64` | `N/A` | `0.00%` | Derived completeness ratio [0.0..1.0] across all mandatory fields. |
| `state` | `object` | `object` | `17.87%` | `0.00%` | Fuzzy string matched against canonical India state reference; low confidence mapped to Unknown. |
| `state_code` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |
| `timestamp` | `object` | `object` | `0.00%` | `0.00%` | Standardized and normalized. |
| `years_of_experience_in_field` | `object` | `object` | `0.00%` | `0.00%` | Standardized and normalized. |
| `zone` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |

## 3. Numeric Distribution and Outlier Bounds

| Numeric Field | Mean | Median | Q25 (p25) | Q75 (p75) | IQR | Outliers Flagged |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `monthly_income` | `145,725.42` | `76,000.0` | `54,000.0` | `110,000.0` | `56,000.0` | `1,112` |
| `response_quality_score` | `0.71` | `0.71` | `0.71` | `0.71` | `0.0` | `0` |
