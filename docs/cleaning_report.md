# Data Cleaning and Transformation Profile Report

> [!IMPORTANT]
> **Measured Execution Timestamp:** 2026-11-03 09:13:30 UTC  
> **Pipeline Batch Run:** Automated Profiler Verification

## 1. Executive Summary: Measured Pipeline Impact

| Metric | Before Cleaning (Raw) | After Cleaning (Clean) | Net Change / Impact |
| :--- | :--- | :--- | :--- |
| **Total Records** | `10,000` | `9,026` | `-974` rows filtered/deduplicated |
| **Duplicates Removed** | `500` | `0` (enforced unique PK) | `100%` duplicate elimination |
| **Invalid Records Rejected** | `0` | `474` (routed to lake) | Logged with root cause reasons |
| **Overall Missing / Null %** | `2.99%` | `1.64%` | `+1.35%` absolute null reduction |

## 2. Column-by-Column Profiling Comparison

| Column Name | Inferred Dtype (Raw) | Dtype (Clean) | Raw Null % | Clean Null % | Cleaning & Imputation Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `age` | `object` | `float64` | `3.86%` | `4.02%` | Type cast to integer; outliers (<18 or >100) flagged via boolean flag `is_outlier_age`. |
| `age_group` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |
| `data_classification` | `object` | `object` | `0.00%` | `0.00%` | Standardized and normalized. |
| `district` | `object` | `object` | `0.00%` | `0.00%` | Whitespace stripped; capitalized; kept NULL where unprovided. |
| `education` | `object` | `object` | `4.03%` | `0.00%` | Fuzzy matched to canonical tier (Higher Education vs Secondary). |
| `education_tier` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |
| `free_text_comment` | `object` | `object` | `10.16%` | `10.13%` | Unicode normalized (NFKC); mojibake repaired; whitespace stripped. |
| `gender` | `object` | `object` | `2.42%` | `2.35%` | Standardized to canonical categories ('Male', 'Female', 'Non-Binary', 'Not Specified'). |
| `income_bracket` | `N/A` | `object` | `N/A` | `5.97%` | Standardized and normalized. |
| `is_outlier_age` | `N/A` | `bool` | `N/A` | `0.00%` | Derived boolean boundary flag. |
| `is_outlier_income` | `N/A` | `bool` | `N/A` | `0.00%` | Derived boolean IQR flag (Q1 - 1.5*IQR, Q3 + 1.5*IQR). |
| `monthly_income` | `object` | `float64` | `5.80%` | `5.97%` | Currency and comma symbols stripped; numeric float parsed; IQR outlier flag set. |
| `multi_select_choices` | `object` | `object` | `0.00%` | `0.00%` | Exploded into relational bridge table `fact_response_choices`. |
| `occupation` | `object` | `object` | `4.14%` | `0.00%` | Fuzzy matched to canonical occupation categories. |
| `occupation_category` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |
| `party_preference` | `object` | `object` | `4.39%` | `0.00%` | Standardized canonical acronyms (BJP, INC, AAP, etc.) and undecided buckets. |
| `rating_1_to_5` | `object` | `float64` | `5.07%` | `5.20%` | Validated range [1..5]; invalid ranges routed to rejection lake. |
| `raw_age` | `N/A` | `object` | `N/A` | `4.02%` | Standardized and normalized. |
| `record_hash` | `object` | `object` | `0.00%` | `0.00%` | Standardized and normalized. |
| `region` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |
| `respondent_id` | `object` | `object` | `0.00%` | `0.00%` | Natural key validation; duplicates dropped; whitespace stripped. |
| `response_date` | `object` | `object` | `4.96%` | `5.04%` | Multi-format parser (ISO, DD/MM/YYYY, MM-DD-YYYY) to standard ISO YYYY-MM-DD. |
| `response_quality_score` | `N/A` | `float64` | `N/A` | `0.00%` | Derived completeness ratio [0.0..1.0] across all mandatory fields. |
| `state` | `object` | `object` | `0.00%` | `0.00%` | Fuzzy string matched against canonical India state reference; low confidence mapped to Unknown. |
| `state_code` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |
| `zone` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |

## 3. Numeric Distribution and Outlier Bounds

| Numeric Field | Mean | Median | Q25 (p25) | Q75 (p75) | IQR | Outliers Flagged |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `age` | `38.02` | `38.0` | `28.0` | `47.0` | `19.0` | `27` |
| `monthly_income` | `886,321.66` | `30,689.0` | `18,623.0` | `48,165.0` | `29,542.0` | `460` |
| `rating_1_to_5` | `3.23` | `3.0` | `2.0` | `4.0` | `2.0` | `0` |
| `response_quality_score` | `0.99` | `1.0` | `1.0` | `1.0` | `0.0` | `811` |
