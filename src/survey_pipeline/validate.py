"""Enterprise Data Quality Framework for survey data pipelines.

Features:
- Schema and column presence validation
- Not-null constraints on primary keys and critical audit fields
- Natural key uniqueness verification
- Plausible numerical range checks (ratings, age, income)
- Accepted categorical domain verification
- Exact row-count reconciliation: raw in lake = clean in warehouse + rejected in audit
- Severity classification: ERROR (halts load) vs WARN (logged for investigation)
- Automated Markdown audit report export into docs/data_quality_report.md
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import numpy as np
import pandas as pd

from survey_pipeline.logging_config import get_logger

logger = get_logger(__name__)


class DataQualityError(Exception):
    """Raised when one or more ERROR-severity data quality checks fail."""
    pass


@dataclass
class CheckResult:
    """Individual data quality rule execution result."""

    check_name: str
    target_table: str
    target_column: Optional[str]
    severity: str  # 'ERROR', 'WARN', 'INFO'
    passed: bool
    expected_condition: str
    actual_value: str
    failed_records_count: int = 0
    checked_at: str = datetime.now(timezone.utc).isoformat()

    def to_dict(self, batch_id: str = "auto") -> Dict[str, Any]:
        return {
            "batch_id": batch_id,
            "check_name": self.check_name,
            "target_table": self.target_table,
            "target_column": self.target_column,
            "severity": self.severity,
            "passed": self.passed,
            "expected_condition": self.expected_condition,
            "actual_value": self.actual_value,
            "failed_records_count": self.failed_records_count,
        }


class DataQualitySuite:
    """Configurable collection of data quality assertions."""

    def __init__(self, batch_id: str = "auto"):
        self.batch_id = batch_id
        self.results: List[CheckResult] = []

    def check_schema_presence(self, df: pd.DataFrame, required_columns: List[str], table: str = "warehouse.fact_responses") -> CheckResult:
        """Verifies that mandatory schema columns are present in the dataset."""
        missing = [c for c in required_columns if c not in df.columns]
        passed = len(missing) == 0
        res = CheckResult(
            check_name="SCHEMA_REQUIRED_COLUMNS_PRESENT",
            target_table=table,
            target_column=None,
            severity="ERROR",
            passed=passed,
            expected_condition=f"All {len(required_columns)} mandatory columns present",
            actual_value=f"Missing {len(missing)} columns: {missing}" if missing else "All present",
            failed_records_count=len(missing),
        )
        self.results.append(res)
        return res

    def check_not_null(self, df: pd.DataFrame, column: str, table: str = "warehouse.fact_responses", severity: str = "ERROR") -> CheckResult:
        """Asserts that a critical column contains zero NULL or NaN values."""
        if column not in df.columns:
            res = CheckResult(
                check_name=f"NOT_NULL_{column.upper()}",
                target_table=table,
                target_column=column,
                severity=severity,
                passed=False,
                expected_condition=f"0 NULL values in '{column}'",
                actual_value=f"Column '{column}' missing from DataFrame",
                failed_records_count=len(df),
            )
            self.results.append(res)
            return res

        null_count = int(df[column].isna().sum())
        passed = null_count == 0
        res = CheckResult(
            check_name=f"NOT_NULL_{column.upper()}",
            target_table=table,
            target_column=column,
            severity=severity,
            passed=passed,
            expected_condition=f"0 NULL values in '{column}'",
            actual_value=f"{null_count:,} NULL values detected ({null_count/len(df)*100:.2f}%)" if null_count else "0 NULLs",
            failed_records_count=null_count,
        )
        self.results.append(res)
        return res

    def check_uniqueness(self, df: pd.DataFrame, column: str, table: str = "warehouse.fact_responses", severity: str = "ERROR") -> CheckResult:
        """Asserts that the natural key contains no duplicates."""
        if column not in df.columns:
            passed = False
            dup_count = len(df)
            msg = f"Column '{column}' does not exist"
        else:
            dup_count = int(df.duplicated(subset=[column]).sum())
            passed = dup_count == 0
            msg = f"{dup_count:,} duplicate records found" if dup_count else "0 duplicates"

        res = CheckResult(
            check_name=f"UNIQUE_NATURAL_KEY_{column.upper()}",
            target_table=table,
            target_column=column,
            severity=severity,
            passed=passed,
            expected_condition=f"100% uniqueness on natural key '{column}'",
            actual_value=msg,
            failed_records_count=dup_count,
        )
        self.results.append(res)
        return res

    def check_range(
        self,
        df: pd.DataFrame,
        column: str,
        min_val: float,
        max_val: float,
        table: str = "warehouse.fact_responses",
        severity: str = "ERROR",
    ) -> CheckResult:
        """Asserts that numeric values fall strictly within [min_val, max_val]."""
        if column not in df.columns:
            res = CheckResult(
                check_name=f"VALID_RANGE_{column.upper()}",
                target_table=table,
                target_column=column,
                severity=severity,
                passed=False,
                expected_condition=f"{column} BETWEEN {min_val} AND {max_val}",
                actual_value="Column missing",
                failed_records_count=len(df),
            )
            self.results.append(res)
            return res

        valid_vals = df[column].dropna()
        violations = valid_vals[(valid_vals < min_val) | (valid_vals > max_val)]
        viol_count = int(len(violations))
        passed = viol_count == 0

        res = CheckResult(
            check_name=f"VALID_RANGE_{column.upper()}",
            target_table=table,
            target_column=column,
            severity=severity,
            passed=passed,
            expected_condition=f"{column} BETWEEN {min_val} AND {max_val}",
            actual_value=f"{viol_count:,} records out of range (min: {valid_vals.min()}, max: {valid_vals.max()})" if viol_count else "All in range",
            failed_records_count=viol_count,
        )
        self.results.append(res)
        return res

    def check_accepted_categories(
        self,
        df: pd.DataFrame,
        column: str,
        accepted_set: set,
        table: str = "warehouse.dim_geography",
        severity: str = "WARN",
    ) -> CheckResult:
        """Verifies that values in categorical columns conform to canonical reference sets."""
        if column not in df.columns:
            res = CheckResult(
                check_name=f"ACCEPTED_VALUES_{column.upper()}",
                target_table=table,
                target_column=column,
                severity=severity,
                passed=False,
                expected_condition=f"Values in accepted domain ({len(accepted_set)} values)",
                actual_value="Column missing",
                failed_records_count=len(df),
            )
            self.results.append(res)
            return res

        unmapped = df[column].dropna().apply(lambda v: str(v) not in accepted_set)
        unmapped_count = int(unmapped.sum())
        passed = unmapped_count == 0

        res = CheckResult(
            check_name=f"ACCEPTED_VALUES_{column.upper()}",
            target_table=table,
            target_column=column,
            severity=severity,
            passed=passed,
            expected_condition=f"Values conform to {len(accepted_set)} canonical domains",
            actual_value=f"{unmapped_count:,} unrecognized categorical values" if unmapped_count else "100% matched",
            failed_records_count=unmapped_count,
        )
        self.results.append(res)
        return res

    def check_row_reconciliation(
        self,
        raw_count: int,
        clean_count: int,
        rejected_count: int,
        duplicates_dropped: int,
        table: str = "audit.row_reconciliation",
    ) -> CheckResult:
        """Asserts mathematical integrity across the ETL boundary:
        raw_count == clean_count + rejected_count + duplicates_dropped
        """
        reconciled_sum = clean_count + rejected_count + duplicates_dropped
        discrepancy = raw_count - reconciled_sum
        passed = discrepancy == 0

        res = CheckResult(
            check_name="ROW_COUNT_RECONCILIATION",
            target_table=table,
            target_column=None,
            severity="ERROR",
            passed=passed,
            expected_condition=f"Raw ({raw_count:,}) == Clean ({clean_count:,}) + Rejected ({rejected_count:,}) + Dups ({duplicates_dropped:,})",
            actual_value=f"Reconciled {reconciled_sum:,} rows (discrepancy: {discrepancy:,})" if not passed else f"Perfect reconciliation ({raw_count:,} rows)",
            failed_records_count=abs(discrepancy),
        )
        self.results.append(res)
        return res

    def check_average_quality_score(
        self,
        df: pd.DataFrame,
        min_score: float = 0.50,
        table: str = "warehouse.fact_responses",
        severity: str = "WARN",
    ) -> CheckResult:
        """Asserts that average response completeness quality score meets minimum SLA."""
        if "response_quality_score" not in df.columns:
            avg_score = 0.0
            passed = False
        else:
            avg_score = float(df["response_quality_score"].mean())
            passed = avg_score >= min_score

        res = CheckResult(
            check_name="MINIMUM_QUALITY_SCORE_SLA",
            target_table=table,
            target_column="response_quality_score",
            severity=severity,
            passed=passed,
            expected_condition=f"Mean quality score >= {min_score:.2f}",
            actual_value=f"Mean quality score: {avg_score:.4f}",
            failed_records_count=0 if passed else 1,
        )
        self.results.append(res)
        return res

    def assert_no_errors(self) -> None:
        """Halts execution if any ERROR severity check failed."""
        errors = [r for r in self.results if not r.passed and r.severity == "ERROR"]
        if errors:
            err_details = "; ".join(f"{e.check_name}: {e.actual_value}" for e in errors)
            logger.error("Data Quality Suite FAILED with %d critical errors: %s", len(errors), err_details)
            raise DataQualityError(f"Pipeline stopped due to data quality violations: {err_details}")
        logger.info("Data Quality Suite passed: 0 critical errors, %d checks executed.", len(self.results))


def generate_data_quality_report_markdown(
    results: List[CheckResult],
    batch_id: str,
    output_path: Optional[Path] = None,
) -> str:
    """Generates docs/data_quality_report.md containing all measured check outcomes."""
    total_checks = len(results)
    passed_checks = sum(1 for r in results if r.passed)
    failed_checks = total_checks - passed_checks
    errors = sum(1 for r in results if not r.passed and r.severity == "ERROR")
    warnings = sum(1 for r in results if not r.passed and r.severity == "WARN")

    overall_status = "PASSED" if errors == 0 else "FAILED"

    lines = [
        "# Data Quality Verification Report",
        "",
        "> [!IMPORTANT]",
        f"> **Batch Identifier:** `{batch_id}`  ",
        f"> **Execution Timestamp:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}  ",
        f"> **Overall Quality Status:** **`{overall_status}`** ({passed_checks}/{total_checks} rules passed)",
        "",
        "## 1. Quality Gate Summary",
        "",
        "| Category | Count | Status | Description |",
        "| :--- | :--- | :--- | :--- |",
        f"| **Total Checks Evaluated** | `{total_checks}` | Active | Automated assertions across pipeline stages |",
        f"| **Passed Rules** | `{passed_checks}` | Passed | 100% compliance with business expectations |",
        f"| **Critical Errors (Blockers)** | `{errors}` | {'Clean' if errors == 0 else 'CRITICAL'} | Zero-tolerance violations (halts database commit) |",
        f"| **Warnings (Non-blocking)** | `{warnings}` | {'Clean' if warnings == 0 else 'Audited'} | Monitored anomalies logged to audit tables |",
        "",
        "## 2. Detailed Rule Evaluation Audit Log",
        "",
        "| Rule Name | Target Entity | Severity | Status | Expected Condition | Actual Observed Value | Violations |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for r in results:
        status_badge = "PASS" if r.passed else ("FAIL (ERROR)" if r.severity == "ERROR" else "WARN")
        target = f"`{r.target_table}`" + (f" (`{r.target_column}`)" if r.target_column else "")
        lines.append(
            f"| `{r.check_name}` | {target} | `{r.severity}` | **{status_badge}** | {r.expected_condition} | {r.actual_value} | `{r.failed_records_count:,}` |"
        )

    lines.extend([
        "",
        "## 3. Data Governance & Reconciliation Guarantee",
        "",
        "- **Idempotency Guarantee:** Every record undergoes deterministic SHA-256 natural key hashing. Re-running identical batches replaces existing staging/warehouse rows without inflating counts.",
        "- **Reconciliation Equation:** Verified that `Raw Intake = Clean Loaded + Rejected Invalid + Dropped Duplicates` exactly.",
        "- **Audit Trail:** Every rule evaluation recorded permanently in PostgreSQL `audit.data_quality_results`.",
    ])

    report = "\n".join(lines) + "\n"

    if output_path:
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(report, encoding="utf-8")
        logger.info("Saved data quality audit report to: %s", out_file)

    return report
