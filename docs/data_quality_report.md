# Data Quality Verification Report

> [!IMPORTANT]
> **Batch Identifier:** `BATCH_DQ_TEST`  
> **Execution Timestamp:** 2026-11-03 08:55:39 UTC  
> **Overall Quality Status:** **`PASSED`** (7/7 rules passed)

## 1. Quality Gate Summary

| Category | Count | Status | Description |
| :--- | :--- | :--- | :--- |
| **Total Checks Evaluated** | `7` | Active | Automated assertions across pipeline stages |
| **Passed Rules** | `7` | Passed | 100% compliance with business expectations |
| **Critical Errors (Blockers)** | `0` | Clean | Zero-tolerance violations (halts database commit) |
| **Warnings (Non-blocking)** | `0` | Clean | Monitored anomalies logged to audit tables |

## 2. Detailed Rule Evaluation Audit Log

| Rule Name | Target Entity | Severity | Status | Expected Condition | Actual Observed Value | Violations |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `SCHEMA_REQUIRED_COLUMNS_PRESENT` | `warehouse.fact_responses` | `ERROR` | **PASS** | All 6 mandatory columns present | All present | `0` |
| `NOT_NULL_RESPONDENT_ID` | `warehouse.fact_responses` (`respondent_id`) | `ERROR` | **PASS** | 0 NULL values in 'respondent_id' | 0 NULLs | `0` |
| `NOT_NULL_RECORD_HASH` | `warehouse.fact_responses` (`record_hash`) | `ERROR` | **PASS** | 0 NULL values in 'record_hash' | 0 NULLs | `0` |
| `UNIQUE_NATURAL_KEY_RESPONDENT_ID` | `warehouse.fact_responses` (`respondent_id`) | `ERROR` | **PASS** | 100% uniqueness on natural key 'respondent_id' | 0 duplicates | `0` |
| `VALID_RANGE_RATING_1_TO_5` | `warehouse.fact_responses` (`rating_1_to_5`) | `ERROR` | **PASS** | rating_1_to_5 BETWEEN 1 AND 5 | All in range | `0` |
| `ROW_COUNT_RECONCILIATION` | `audit.row_reconciliation` | `ERROR` | **PASS** | Raw (10,000) == Clean (9,065) + Rejected (435) + Dups (500) | Perfect reconciliation (10,000 rows) | `0` |
| `MINIMUM_QUALITY_SCORE_SLA` | `warehouse.fact_responses` (`response_quality_score`) | `WARN` | **PASS** | Mean quality score >= 0.60 | Mean quality score: 0.9869 | `0` |

## 3. Data Governance & Reconciliation Guarantee

- **Idempotency Guarantee:** Every record undergoes deterministic SHA-256 natural key hashing. Re-running identical batches replaces existing staging/warehouse rows without inflating counts.
- **Reconciliation Equation:** Verified that `Raw Intake = Clean Loaded + Rejected Invalid + Dropped Duplicates` exactly.
- **Audit Trail:** Every rule evaluation recorded permanently in PostgreSQL `audit.data_quality_results`.
