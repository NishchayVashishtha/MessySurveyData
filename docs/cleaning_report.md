# Data Cleaning and Transformation Profile Report

> [!IMPORTANT]
> **Measured Execution Timestamp:** 2026-11-03 09:19:46 UTC  
> **Pipeline Batch Run:** Automated Profiler Verification

## 1. Executive Summary: Measured Pipeline Impact

| Metric | Before Cleaning (Raw) | After Cleaning (Clean) | Net Change / Impact |
| :--- | :--- | :--- | :--- |
| **Total Records** | `50,000` | `45,147` | `-4,853` rows filtered/deduplicated |
| **Duplicates Removed** | `2,500` | `0` (enforced unique PK) | `100%` duplicate elimination |
| **Invalid Records Rejected** | `0` | `2,353` (routed to lake) | Logged with root cause reasons |
| **Overall Missing / Null %** | `2.97%` | `1.63%` | `+1.34%` absolute null reduction |

## 2. Column-by-Column Profiling Comparison

| Column Name | Inferred Dtype (Raw) | Dtype (Clean) | Raw Null % | Clean Null % | Cleaning & Imputation Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `age` | `object` | `float64` | `3.93%` | `4.04%` | Type cast to integer; outliers (<18 or >100) flagged via boolean flag `is_outlier_age`. |
| `age_group` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |
| `data_classification` | `object` | `object` | `0.00%` | `0.00%` | Standardized and normalized. |
| `district` | `object` | `object` | `0.00%` | `0.00%` | Whitespace stripped; capitalized; kept NULL where unprovided. |
| `education` | `object` | `object` | `3.97%` | `0.00%` | Fuzzy matched to canonical tier (Higher Education vs Secondary). |
| `education_tier` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |
| `free_text_comment` | `object` | `object` | `10.11%` | `10.08%` | Unicode normalized (NFKC); mojibake repaired; whitespace stripped. |
| `gender` | `object` | `object` | `2.22%` | `2.18%` | Standardized to canonical categories ('Male', 'Female', 'Non-Binary', 'Not Specified'). |
| `income_bracket` | `N/A` | `object` | `N/A` | `5.99%` | Standardized and normalized. |
| `is_outlier_age` | `N/A` | `bool` | `N/A` | `0.00%` | Derived boolean boundary flag. |
| `is_outlier_income` | `N/A` | `bool` | `N/A` | `0.00%` | Derived boolean IQR flag (Q1 - 1.5*IQR, Q3 + 1.5*IQR). |
| `monthly_income` | `object` | `float64` | `5.95%` | `5.99%` | Currency and comma symbols stripped; numeric float parsed; IQR outlier flag set. |
| `multi_select_choices` | `object` | `object` | `0.00%` | `0.00%` | Exploded into relational bridge table `fact_response_choices`. |
| `occupation` | `object` | `object` | `4.01%` | `0.00%` | Fuzzy matched to canonical occupation categories. |
| `occupation_category` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |
| `party_preference` | `object` | `object` | `4.44%` | `0.00%` | Standardized canonical acronyms (BJP, INC, AAP, etc.) and undecided buckets. |
| `rating_1_to_5` | `object` | `float64` | `5.01%` | `5.16%` | Validated range [1..5]; invalid ranges routed to rejection lake. |
| `raw_age` | `N/A` | `object` | `N/A` | `4.04%` | Standardized and normalized. |
| `record_hash` | `object` | `object` | `0.00%` | `0.00%` | Standardized and normalized. |
| `region` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |
| `respondent_id` | `object` | `object` | `0.00%` | `0.00%` | Natural key validation; duplicates dropped; whitespace stripped. |
| `response_date` | `object` | `object` | `4.84%` | `4.87%` | Multi-format parser (ISO, DD/MM/YYYY, MM-DD-YYYY) to standard ISO YYYY-MM-DD. |
| `response_quality_score` | `N/A` | `float64` | `N/A` | `0.00%` | Derived completeness ratio [0.0..1.0] across all mandatory fields. |
| `state` | `object` | `object` | `0.00%` | `0.00%` | Fuzzy string matched against canonical India state reference; low confidence mapped to Unknown. |
| `state_code` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |
| `zone` | `N/A` | `object` | `N/A` | `0.00%` | Standardized and normalized. |

## 3. Numeric Distribution and Outlier Bounds

| Numeric Field | Mean | Median | Q25 (p25) | Q75 (p75) | IQR | Outliers Flagged |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `age` | `38.0` | `38.0` | `28.0` | `47.0` | `19.0` | `133` |
| `monthly_income` | `918,283.91` | `30,432.0` | `18,367.5` | `47,827.0` | `29,459.5` | `2,275` |
| `rating_1_to_5` | `3.24` | `3.0` | `2.0` | `4.0` | `2.0` | `0` |
| `response_quality_score` | `0.99` | `1.0` | `1.0` | `1.0` | `0.0` | `4,051` |
