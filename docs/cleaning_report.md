# Data Cleaning and Transformation Profile Report

> [!IMPORTANT]
> **Measured Execution Timestamp:** 2026-11-03 08:52:49 UTC  
> **Pipeline Batch Run:** Automated Profiler Verification

## 1. Executive Summary: Measured Pipeline Impact

| Metric | Before Cleaning (Raw) | After Cleaning (Clean) | Net Change / Impact |
| :--- | :--- | :--- | :--- |
| **Total Records** | `10,000` | `9,065` | `-935` rows filtered/deduplicated |
| **Duplicates Removed** | `500` | `0` (enforced unique PK) | `100%` duplicate elimination |
| **Invalid Records Rejected** | `0` | `435` (routed to lake) | Logged with root cause reasons |
| **Overall Missing / Null %** | `0.00%` | `1.32%` | `-1.32%` absolute null reduction |

## 2. Column-by-Column Profiling Comparison

| Column Name | Inferred Dtype (Raw) | Dtype (Clean) | Raw Null % | Clean Null % | Cleaning & Imputation Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `age` | `object` | `float64` | `0.00%` | `4.00%` | Type cast to integer; outliers (<18 or >100) flagged via boolean flag `is_outlier_age`. |
| `age_group` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |
| `data_classification` | `object` | `object` | `0.00%` | `0.00%` | Standardized and normalized. |
| `district` | `object` | `object` | `0.00%` | `0.00%` | Whitespace stripped; capitalized; kept NULL where unprovided. |
| `education` | `object` | `object` | `0.00%` | `0.00%` | Fuzzy matched to canonical tier (Higher Education vs Secondary). |
| `education_tier` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |
| `free_text_comment` | `object` | `object` | `0.00%` | `10.13%` | Unicode normalized (NFKC); mojibake repaired; whitespace stripped. |
| `gender` | `object` | `object` | `0.00%` | `0.00%` | Standardized to canonical categories ('Male', 'Female', 'Non-Binary', 'Not Specified'). |
| `income_bracket` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |
| `is_outlier_age` | `N/A` | `bool` | `N/A` | `0.00%` | Derived boolean boundary flag. |
| `is_outlier_income` | `N/A` | `bool` | `N/A` | `0.00%` | Derived boolean IQR flag (Q1 - 1.5*IQR, Q3 + 1.5*IQR). |
| `monthly_income` | `object` | `float64` | `0.00%` | `5.95%` | Currency and comma symbols stripped; numeric float parsed; IQR outlier flag set. |
| `multi_select_choices` | `object` | `object` | `0.00%` | `0.00%` | Exploded into relational bridge table `fact_response_choices`. |
| `occupation` | `object` | `object` | `0.00%` | `0.00%` | Fuzzy matched to canonical occupation categories. |
| `occupation_category` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |
| `party_preference` | `object` | `object` | `0.00%` | `0.00%` | Standardized canonical acronyms (BJP, INC, AAP, etc.) and undecided buckets. |
| `rating_1_to_5` | `object` | `float64` | `0.00%` | `5.20%` | Validated range [1..5]; invalid ranges routed to rejection lake. |
| `raw_age` | `N/A` | `object` | `N/A` | `4.00%` | Standardized and normalized. |
| `record_hash` | `object` | `object` | `0.00%` | `0.00%` | Standardized and normalized. |
| `region` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |
| `respondent_id` | `object` | `object` | `0.00%` | `0.00%` | Natural key validation; duplicates dropped; whitespace stripped. |
| `response_date` | `object` | `object` | `0.00%` | `5.02%` | Multi-format parser (ISO, DD/MM/YYYY, MM-DD-YYYY) to standard ISO YYYY-MM-DD. |
| `response_quality_score` | `N/A` | `float64` | `N/A` | `0.00%` | Derived completeness ratio [0.0..1.0] across all mandatory fields. |
| `state` | `object` | `object` | `0.00%` | `0.00%` | Fuzzy string matched against canonical India state reference; low confidence mapped to Unknown. |
| `state_code` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |
| `zone` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |

## 3. Numeric Distribution and Outlier Bounds

| Numeric Field | Mean | Median | Q25 (p25) | Q75 (p75) | IQR | Outliers Flagged |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `age` | `37.85` | `37.5` | `28.0` | `47.0` | `19.0` | `27` |
| `monthly_income` | `882,421.22` | `30,695.0` | `18,622.5` | `48,177.0` | `29,554.5` | `459` |
| `rating_1_to_5` | `3.23` | `3.0` | `2.0` | `4.0` | `2.0` | `0` |
| `response_quality_score` | `0.99` | `1.0` | `1.0` | `1.0` | `0.0` | `813` |
