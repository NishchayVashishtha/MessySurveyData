# Pipeline Architecture & Data Flow Design

## 1. System Architecture Overview

The `survey-data-pipeline` is a production-grade, containerized ELT/ETL pipeline designed for survey analytics and political research intelligence. It ingests messy, heterogeneous survey submissions, archives the untouched payloads in a schema-flexible MongoDB Data Lake, executes automated cleaning and fuzzy standardization via Python/Pandas, validates structural integrity through a rule-based Data Quality Suite, and idempotently loads a dimensional Star Schema into PostgreSQL for high-speed analytical querying.

```mermaid
flowchart TD
    subgraph SOURCING ["1. Data Ingestion & Fingerprinting"]
        RAW_CSV["Raw Survey CSV File<br/>(Real / Synthetic Dirty Stream)"] --> HASH["Compute SHA-256 File Checksum<br/>& Deterministic Record Hash"]
    end

    subgraph LAKE ["2. MongoDB Raw Landing Lake (survey_lake)"]
        HASH --> MONGO_RAW[("raw_responses<br/>(Untouched Verbatim JSONB Payload<br/>+ batch_id + ingest_ts + record_hash)")]
        MONGO_REJ[("rejected_responses<br/>(Validation Rejections + Error Details)")]
        MONGO_RUNS[("pipeline_runs<br/>(Execution Metastore)")]
    end

    subgraph ENGINE ["3. Cleaning, Standardization & Feature Engineering"]
        MONGO_RAW --> CLEAN_NORM["Snake_case Normalization<br/>& Unicode NFKC Repair"]
        CLEAN_NORM --> CLEAN_MISS["Missing Value Unification<br/>(N/A, NA, -, Null -> pd.NA)"]
        CLEAN_MISS --> CLEAN_DEDUP["Deterministic Deduplication<br/>(Natural Key: respondent_id)"]
        CLEAN_DEDUP --> CLEAN_CAST["Safe Numeric & Date Parsing<br/>(Currency symbols, multi-format dates)"]
        CLEAN_CAST --> FUZZY["RapidFuzz Standardization<br/>(States, Parties, Education, Occupations)"]
        FUZZY --> OUTLIER["Outlier Detection<br/>(IQR Multiplier 1.5, Age Bounds)"]
        OUTLIER --> DERIVE["Derived Analytics Features<br/>(age_group, income_bracket, quality_score)"]
        DERIVE --> ROUTER{"Validation<br/>Quality Filter"}
        ROUTER -- "Severe Violations" --> MONGO_REJ
        ROUTER -- "Severe Violations" --> PG_REJ["audit.rejected_rows<br/>(PostgreSQL)"]
        ROUTER -- "Clean Records" --> DQ_SUITE["Data Quality Suite"]
    end

    subgraph AUDIT ["4. Data Quality & Audit Framework"]
        DQ_SUITE --> DQ_ASSERT{"Assert Critical<br/>Rules (ERROR)"}
        DQ_ASSERT -- "Critical Failure" --> STOP["Halt Pipeline Load"]
        DQ_ASSERT -- "Passed (100%)" --> PG_DQ["audit.data_quality_results<br/>(PostgreSQL)"]
        PG_DQ --> DQ_REP["docs/data_quality_report.md"]
        DERIVE --> CLEAN_REP["docs/cleaning_report.md"]
    end

    subgraph WAREHOUSE ["5. PostgreSQL Star Schema (survey_dw)"]
        DQ_ASSERT --> PG_LOAD["Idempotent Warehouse Loader<br/>(INSERT ... ON CONFLICT DO UPDATE)"]
        PG_LOAD --> DIM_RESP[("dim_respondent<br/>(Demographics & Natural Key)")]
        PG_LOAD --> DIM_GEO[("dim_geography<br/>(State, Region, Zone)")]
        PG_LOAD --> DIM_EDU[("dim_education<br/>(Level, Education Tier)")]
        PG_LOAD --> DIM_OCC[("dim_occupation<br/>(Title, Category)")]
        PG_LOAD --> FACT_RESP[("fact_responses<br/>(Surrogate FKs, Income, Rating,<br/>Quality Score, Outlier Flags)")]
        PG_LOAD --> FACT_CHOICES[("fact_response_choices<br/>(Bridge Table for Multi-Selects)")]
        PG_LOAD --> AUDIT_RUNS[("audit.pipeline_runs")]
    end

    subgraph ANALYTICS ["6. Analytics & Performance Optimization"]
        FACT_RESP --> V_GEO["v_response_counts_by_geography"]
        FACT_RESP --> V_DEMO["v_demographic_sentiment"]
        FACT_RESP --> V_RANK["v_state_sentiment_ranking (Window RANK/NTILE)"]
        FACT_RESP --> V_INCOME["v_income_distribution_by_education"]
        FACT_CHOICES --> V_CHOICES["v_top_choice_popularity"]
        FACT_RESP --> V_QUALITY["v_response_quality_audit"]
    end

    classDef primary fill:#e3f2fd,stroke:#1565c0,stroke-width:2px;
    classDef lake fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px;
    classDef warehouse fill:#fff3e0,stroke:#e65100,stroke-width:2px;
    classDef audit fill:#fce4ec,stroke:#c2185b,stroke-width:2px;

    class RAW_CSV,HASH,CLEAN_NORM,CLEAN_MISS,CLEAN_DEDUP,CLEAN_CAST,FUZZY,OUTLIER,DERIVE primary;
    class MONGO_RAW,MONGO_REJ,MONGO_RUNS lake;
    class DIM_RESP,DIM_GEO,DIM_EDU,DIM_OCC,FACT_RESP,FACT_CHOICES warehouse;
    class DQ_SUITE,DQ_ASSERT,PG_DQ,PG_REJ,AUDIT_RUNS,DQ_REP,CLEAN_REP audit;
```

---

## 2. Storage Strategy: Dual-Store Hybrid Lakehouse Pattern

A fundamental design decision in this architecture is the deliberate division of labor between **MongoDB** and **PostgreSQL**:

| Architectural Dimension | MongoDB Raw Landing Zone (`survey_lake`) | PostgreSQL Dimensional Warehouse (`survey_dw`) |
| :--- | :--- | :--- |
| **Primary Responsibility** | Verbatim raw data lake / audit landing zone | Highly structured analytical warehouse |
| **Schema Paradigm** | Schema-flexible JSON documents | Strictly typed relational Star Schema (3NF Dims) |
| **Handling Question Drift** | Seamlessly captures newly added questions without DDL migrations | Strict DDL with Surrogate Keys, PK/FK constraints, and CHECK rules |
| **Query Workload** | Key-value point audits and document inspection | Multi-dimensional analytical joins, window ranking, percentiles |
| **Data Preservation** | 100% loss-free capture of original noise and raw headers | Cleaned, standardized, outlier-flagged, analysis-ready records |
| **Idempotency Primitive** | `ReplaceOne({"record_hash": h}, doc, upsert=True)` | `INSERT INTO ... ON CONFLICT (natural_id) DO UPDATE` |

---

## 3. Data Transformation & Cleaning Engine

The cleaning engine (`survey_pipeline.clean` and `survey_pipeline.standardize`) adheres to functional, idempotent principles:

1. **Deterministic Hashing:** Before transformation, every incoming raw record receives a deterministic SHA-256 cryptographic digest computed across its canonical representation.
2. **Missing Token Normalization:** Survey instruments frequently represent missing data via `"N/A"`, `"na"`, `"-"`, `"--"`, `"None"`, `"null"`, `"nil"`, or empty strings. These are unified into native `pd.NA` / `numpy.nan` prior to type casting.
3. **Safe Type Casting:** Numeric values with currency symbols (`₹`, `$`, `€`), commas (`50,000`), or trailing spaces are extracted safely. Dates in disparate formats (`YYYY-MM-DD`, `DD/MM/YYYY`, `MM-DD-YYYY`) are normalized to ISO-8601 strings.
4. **Fuzzy String Matching (RapidFuzz):** Using token sort ratio algorithms with strict confidence thresholds (85.0%), state abbreviations (`"UP"` -> `"Uttar Pradesh"`), typos (`"Maharastra"` -> `"Maharashtra"`), and political parties (`"Bhartiya Janta Party"` -> `"Bharatiya Janata Party"`) are canonically mapped. Low-confidence anomalies default to designated `"Unknown / Other"` dimensional buckets.
5. **Multi-Select Array Normalization:** Semicolon-delimited responses (`"Healthcare; Education; Jobs"`) are extracted and exploded into a normalized relational bridge table (`fact_response_choices`), enabling index-backed analytical aggregation.

---

## 4. Zero-Defect Data Quality Framework

The pipeline implements an in-memory Data Quality Suite (`survey_pipeline.validate`) executing assertions prior to warehouse loading:

1. **Schema Integrity:** Verifies all required analytical fields exist. Missing critical columns abort execution immediately (`severity="ERROR"`).
2. **Natural Key Uniqueness:** Enforces 100% uniqueness of respondent identifiers.
3. **Not-Null Primary Keys:** Asserts zero null values in natural keys and batch identifiers.
4. **Plausible Numerical Bounds:** Enforces domain constraints (e.g., survey ratings strictly between 1 and 5; plausible age between 10 and 120 years). Out-of-bounds records are routed to the rejection lake.
5. **ETL Conservation Law:** Evaluates exact mathematical reconciliation:
   $$\text{Raw Records} = \text{Clean Loaded} + \text{Rejected Records} + \text{Dropped Duplicates}$$
   Any discrepancy halts the pipeline and logs an audit failure.
