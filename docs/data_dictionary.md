# Comprehensive Data Dictionary

## 1. Schema Overview

The relational warehouse (`survey_dw`) comprises four distinct PostgreSQL schemas designed with clear separation of concerns:
- **`warehouse`**: Dimensional Star Schema containing dimension tables, central fact responses, and exploded multi-select bridge tables.
- **`audit`**: Data governance, operational metastore, rejected records lake, and data quality check results.
- **`analytics`**: Curated analytical views with pre-joined business logic, window ranking, and percentiles.
- **`staging`**: Ephemeral landing zone for bulk database operations.

---

## 2. Dimensional Tables (`warehouse` Schema)

### 2.1 `warehouse.dim_respondent`
Demographic profile of survey participants identified by natural business keys.

| Column Name | Data Type | Nullable | Default | Constraints | Description & Business Rules |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `respondent_key` | `SERIAL` | **No** | Auto | `PRIMARY KEY` | Surrogate auto-increment integer key. |
| `natural_respondent_id` | `VARCHAR(100)` | **No** | None | `UNIQUE NOT NULL` | Natural business identifier from the survey instrument (e.g., `RESP_000123`). |
| `gender` | `VARCHAR(30)` | Yes | None | `CHECK (gender IN ('Male', 'Female', 'Non-Binary', 'Prefer not to say', 'Not Specified'))` | Standardized canonical gender identity. |
| `age` | `INTEGER` | Yes | None | `CHECK (age >= 10 AND age <= 120)` | Validated respondent age in completed years. Values outside `[10, 120]` are rejected. |
| `age_group` | `VARCHAR(20)` | Yes | None | None | Derived age bracket: `<18`, `18-25`, `26-35`, `36-50`, `51-65`, `65+`, or `Unknown`. |
| `district` | `VARCHAR(100)` | Yes | None | None | Cleaned administrative district / city of the respondent. |
| `first_seen_batch_id` | `VARCHAR(100)` | **No** | None | None | Lineage tracker recording the batch where this participant was first ingested. |
| `created_at` | `TIMESTAMP` | **No** | `CURRENT_TIMESTAMP` | None | Initial row creation timestamp in UTC. |
| `updated_at` | `TIMESTAMP` | **No** | `CURRENT_TIMESTAMP` | None | Most recent upsert/modification timestamp in UTC. |

---

### 2.2 `warehouse.dim_geography`
Canonical geographic reference data with regional hierarchy.

| Column Name | Data Type | Nullable | Default | Constraints | Description & Business Rules |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `geography_key` | `SERIAL` | **No** | Auto | `PRIMARY KEY` | Surrogate auto-increment integer key. |
| `state_name` | `VARCHAR(100)` | **No** | None | `UNIQUE NOT NULL` | Canonical state / Union Territory name (e.g., `Uttar Pradesh`, `Maharashtra`). |
| `state_code` | `VARCHAR(10)` | Yes | None | None | 2-letter standard ISO/postal abbreviation (e.g., `UP`, `MH`, `DL`). |
| `region` | `VARCHAR(50)` | Yes | None | None | Geographic region: `North`, `South`, `East`, `West`, `Central`, `Northeast`, or `Other`. |
| `zone` | `VARCHAR(50)` | Yes | None | None | Administrative Zonal Council grouping. |
| `created_at` | `TIMESTAMP` | **No** | `CURRENT_TIMESTAMP` | None | Row creation timestamp. |

---

### 2.3 `warehouse.dim_occupation`
Standardized occupational titles and industry sectors.

| Column Name | Data Type | Nullable | Default | Constraints | Description & Business Rules |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `occupation_key` | `SERIAL` | **No** | Auto | `PRIMARY KEY` | Surrogate auto-increment integer key. |
| `occupation_title` | `VARCHAR(150)` | **No** | None | `UNIQUE NOT NULL` | Canonical job title (e.g., `Software Engineer`, `Data Analyst`, `Farmer`). |
| `occupation_category` | `VARCHAR(100)` | Yes | None | None | Industry vertical: `Technology`, `Healthcare`, `Education`, `Agriculture`, `Business`, `Public Sector`, etc. |
| `created_at` | `TIMESTAMP` | **No** | `CURRENT_TIMESTAMP` | None | Row creation timestamp. |

---

### 2.4 `warehouse.dim_education`
Educational attainment hierarchy and qualification tiers.

| Column Name | Data Type | Nullable | Default | Constraints | Description & Business Rules |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `education_key` | `SERIAL` | **No** | Auto | `PRIMARY KEY` | Surrogate auto-increment integer key. |
| `education_level` | `VARCHAR(150)` | **No** | None | `UNIQUE NOT NULL` | Canonical educational qualification (e.g., `Bachelor's Degree`, `Master's Degree`, `Doctorate`). |
| `education_tier` | `VARCHAR(50)` | Yes | None | None | Normalized tier: `Higher Education`, `Secondary`, `Primary`, or `Unknown`. |
| `created_at` | `TIMESTAMP` | **No** | `CURRENT_TIMESTAMP` | None | Row creation timestamp. |

---

## 3. Fact Tables (`warehouse` Schema)

### 3.1 `warehouse.fact_responses`
Central fact table storing individual survey responses, numeric scores, and quality flags.

| Column Name | Data Type | Nullable | Default | Constraints | Description & Business Rules |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `response_id` | `SERIAL` | **No** | Auto | `PRIMARY KEY` | Surrogate primary key. |
| `natural_response_id` | `VARCHAR(150)` | **No** | None | `UNIQUE NOT NULL` | Natural compound key (`respondent_id + '_' + batch_id`) ensuring idempotent re-runs. |
| `respondent_key` | `INTEGER` | **No** | None | `REFERENCES warehouse.dim_respondent(respondent_key)` | Foreign key link to respondent demographics. |
| `geography_key` | `INTEGER` | **No** | None | `REFERENCES warehouse.dim_geography(geography_key)` | Foreign key link to geographic dimension. |
| `occupation_key` | `INTEGER` | **No** | None | `REFERENCES warehouse.dim_occupation(occupation_key)` | Foreign key link to occupation dimension. |
| `education_key` | `INTEGER` | **No** | None | `REFERENCES warehouse.dim_education(education_key)` | Foreign key link to education dimension. |
| `batch_id` | `VARCHAR(100)` | **No** | None | None | Execution batch identifier for data lineage. |
| `source_file` | `VARCHAR(255)` | **No** | None | None | Origin filename from which the response was extracted. |
| `response_date` | `DATE` | **No** | None | None | Normalized submission date (ISO format `YYYY-MM-DD`). |
| `party_preference` | `VARCHAR(100)` | Yes | None | None | Standardized political party preference (e.g., `BJP`, `INC`, `AAP`). |
| `monthly_income` | `NUMERIC(12,2)` | Yes | None | `CHECK (monthly_income >= 0)` | Cleaned numeric income per month in INR. Negative values are rejected. |
| `income_bracket` | `VARCHAR(50)` | Yes | None | None | Derived income tier: `< ₹25k`, `₹25k-₹50k`, `₹50k-₹100k`, `₹100k-₹200k`, `₹200k+`. |
| `rating_1_to_5` | `INTEGER` | Yes | None | `CHECK (rating_1_to_5 >= 1 AND rating_1_to_5 <= 5)` | Evaluated survey satisfaction score (1 = Lowest, 5 = Highest). |
| `response_quality_score`| `NUMERIC(4,3)` | **No** | 1.0 | `CHECK (response_quality_score >= 0.0 AND response_quality_score <= 1.0)` | Completeness metric: fraction of non-null answers across questions. |
| `is_outlier_income` | `BOOLEAN` | **No** | `FALSE` | None | IQR outlier flag (True if income > Q3 + 1.5*IQR). Retained for statistical audits. |
| `is_outlier_age` | `BOOLEAN` | **No** | `FALSE` | None | Flag indicating boundary age conditions. |
| `free_text_comment` | `TEXT` | Yes | None | None | Sanitized, Unicode-normalized qualitative text response. |
| `raw_record_hash` | `VARCHAR(64)` | **No** | None | None | SHA-256 fingerprint of the original raw document in MongoDB. |
| `created_at` | `TIMESTAMP` | **No** | `CURRENT_TIMESTAMP` | None | Ingestion timestamp. |
| `updated_at` | `TIMESTAMP` | **No** | `CURRENT_TIMESTAMP` | None | Idempotent upsert timestamp. |

---

### 3.2 `warehouse.fact_response_choices`
Bridge child table for exploded multi-select question responses (e.g., skills, public issues, platform choices).

| Column Name | Data Type | Nullable | Default | Constraints | Description & Business Rules |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `choice_id` | `SERIAL` | **No** | Auto | `PRIMARY KEY` | Surrogate primary key. |
| `response_id` | `INTEGER` | **No** | None | `REFERENCES warehouse.fact_responses(response_id) ON DELETE CASCADE` | Foreign key linking to parent survey fact. |
| `choice_category` | `VARCHAR(100)` | **No** | None | None | Category/Question name (e.g., `priority_issue`, `programming_language`). |
| `choice_value` | `VARCHAR(150)` | **No** | None | None | Individual selected choice option. |
| *Composite* | - | - | - | `UNIQUE (response_id, choice_category, choice_value)` | Enforces uniqueness of a choice per respondent to prevent double-counting. |

---

## 4. Audit & Operational Metastore Tables (`audit` Schema)

### 4.1 `audit.pipeline_runs`
Master operational log tracking every execution batch, data volume, and quality metrics.

| Column Name | Data Type | Nullable | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- |
| `batch_id` | `VARCHAR(100)` | **No** | `PRIMARY KEY` | Unique batch execution code. |
| `source_name` | `VARCHAR(100)` | **No** | None | Source instrument (`synthetic`, `local`, `stackoverflow`). |
| `source_file` | `VARCHAR(255)` | **No** | None | Source filename. |
| `status` | `VARCHAR(30)` | **No** | None | Execution outcome (`COMPLETED`, `FAILED`, `RUNNING`). |
| `records_extracted` | `INTEGER` | **No** | None | Total raw records loaded from CSV. |
| `records_loaded_mongo` | `INTEGER` | **No** | None | Raw records written to MongoDB data lake. |
| `records_cleaned` | `INTEGER` | **No** | None | Clean records meeting validation rules. |
| `records_rejected` | `INTEGER` | **No** | None | Dirty records routed to the rejection lake. |
| `records_loaded_pg` | `INTEGER` | **No** | None | Facts successfully loaded to PostgreSQL. |
| `duplicates_dropped` | `INTEGER` | **No** | None | Duplicate natural keys dropped. |
| `null_pct_before` | `NUMERIC(5,2)` | Yes | None | Overall null percentage in raw dataset. |
| `null_pct_after` | `NUMERIC(5,2)` | Yes | None | Overall null percentage in cleaned warehouse dataset. |
| `execution_time_seconds`| `NUMERIC(8,3)` | Yes | None | Wall-clock execution runtime. |
| `error_message` | `TEXT` | Yes | None | Error log trace if execution failed. |
| `started_at` | `TIMESTAMP` | **No** | None | Pipeline start timestamp. |
| `completed_at` | `TIMESTAMP` | Yes | None | Pipeline completion timestamp. |

---

### 4.2 `audit.rejected_rows`
Dead-letter audit table storing individual records that failed validation with full error context.

| Column Name | Data Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `rejection_id` | `SERIAL` | **No** | Surrogate primary key. |
| `batch_id` | `VARCHAR(100)` | **No** | Execution batch identifier. |
| `natural_respondent_id`| `VARCHAR(100)` | Yes | Natural respondent ID of the offending record (if extractable). |
| `rule_failed` | `VARCHAR(100)` | **No** | Specific Data Quality rule (e.g., `PLAUSIBLE_AGE_LIMIT`, `NON_NEGATIVE_INCOME`). |
| `severity` | `VARCHAR(20)` | **No** | Severity code (`ERROR`, `WARN`). |
| `failed_column` | `VARCHAR(100)` | Yes | Name of the column violating the constraint. |
| `invalid_value` | `TEXT` | Yes | The unparseable dirty value (e.g., `"-5"`, `"999999999"`). |
| `error_reason` | `TEXT` | **No** | Human-readable root cause explanation. |
| `raw_payload` | `JSONB` | **No** | Complete verbatim raw JSON document for debugging and reprojection. |
| `rejected_at` | `TIMESTAMP` | **No** | Timestamp when the rejection occurred. |

---

### 4.3 `audit.data_quality_results`
Assertion results from the Data Quality Suite.

| Column Name | Data Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `check_id` | `SERIAL` | **No** | Surrogate primary key. |
| `batch_id` | `VARCHAR(100)` | **No** | Execution batch identifier. |
| `check_name` | `VARCHAR(150)` | **No** | Name of the assertion rule (e.g., `ROW_COUNT_RECONCILIATION`). |
| `target_table` | `VARCHAR(100)` | **No** | Relational table evaluated. |
| `target_column` | `VARCHAR(100)` | Yes | Column evaluated (or NULL for table-wide rules). |
| `severity` | `VARCHAR(20)` | **No** | Classification (`ERROR`, `WARN`, `INFO`). |
| `passed` | `BOOLEAN` | **No** | True if check passed; False if violated. |
| `expected_condition` | `TEXT` | **No** | Contractual expectation string. |
| `actual_value` | `TEXT` | **No** | Measured outcome during execution. |
| `failed_records_count` | `INTEGER` | **No** | Number of rows failing the check. |
| `checked_at` | `TIMESTAMP` | **No** | Verification timestamp. |
