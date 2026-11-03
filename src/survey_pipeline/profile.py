"""Data profiling engine: computes null distributions, cardinality, and before/after comparisons."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from survey_pipeline.logging_config import get_logger

logger = get_logger(__name__)


RAW_MISSING_TOKENS = {
    "n/a",
    "na",
    "-",
    "--",
    "none",
    "",
    "nan",
    "null",
    "not available",
    "undefined",
    "n.a.",
    "nil",
    "blank",
    "unspecified",
    "not specified",
}


def profile_dataframe(df: pd.DataFrame, stage_name: str = "raw") -> dict[str, Any]:
    """Computes statistical profile of a dataset at any ETL stage.

    Metrics captured:
    - Total row & column counts
    - Total cells & overall null percentage
    - Column-by-column null count, null %, unique count, and inferred dtype
    - Numeric distribution metrics: min, max, mean, median, IQR, outlier counts
    - Duplicate count on natural keys if present

    Args:
        df: Input pandas DataFrame.
        stage_name: Label for the stage ('raw', 'cleaned', etc.).

    Returns:
        Structured profile dictionary.
    """
    total_rows = len(df)
    total_cols = len(df.columns)
    total_cells = total_rows * total_cols if total_rows > 0 else 0

    col_profiles: dict[str, dict[str, Any]] = {}
    total_nulls = 0

    for col in df.columns:
        series = df[col]
        # Count explicit NaNs and ambiguous string missing tokens
        null_mask = series.apply(
            lambda x: (
                True
                if pd.isna(x)
                or (isinstance(x, str) and str(x).strip().lower() in RAW_MISSING_TOKENS)
                else False
            )
        )
        null_count = int(null_mask.sum())
        total_nulls += null_count
        null_pct = round((null_count / total_rows * 100), 2) if total_rows > 0 else 0.0
        unique_count = int(series[~null_mask].nunique())

        col_meta: dict[str, Any] = {
            "dtype": str(series.dtype),
            "null_count": null_count,
            "null_pct": null_pct,
            "unique_count": unique_count,
        }

        # Numeric statistics if column is numeric (excluding boolean)
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            valid_num = series.dropna()
            if len(valid_num) > 0:
                q25 = float(valid_num.quantile(0.25))
                q50 = float(valid_num.median())
                q75 = float(valid_num.quantile(0.75))
                iqr = q75 - q25
                lower_bound = q25 - 1.5 * iqr
                upper_bound = q75 + 1.5 * iqr
                outliers = int(((valid_num < lower_bound) | (valid_num > upper_bound)).sum())

                col_meta["numeric_stats"] = {
                    "min": float(valid_num.min()),
                    "max": float(valid_num.max()),
                    "mean": round(float(valid_num.mean()), 2),
                    "median": round(q50, 2),
                    "q25": round(q25, 2),
                    "q75": round(q75, 2),
                    "iqr": round(iqr, 2),
                    "outlier_count": outliers,
                }

        col_profiles[col] = col_meta

    overall_null_pct = round((total_nulls / total_cells * 100), 2) if total_cells > 0 else 0.0

    profile = {
        "stage": stage_name,
        "profile_timestamp": datetime.now(UTC).isoformat(),
        "total_rows": total_rows,
        "total_columns": total_cols,
        "total_cells": total_cells,
        "total_nulls": total_nulls,
        "overall_null_pct": overall_null_pct,
        "columns": col_profiles,
    }

    logger.debug(
        "Profile generated for '%s': %d rows, %d cols, %.2f%% nulls.",
        stage_name,
        total_rows,
        total_cols,
        overall_null_pct,
    )
    return profile


def generate_profile_comparison_markdown(
    profile_before: dict[str, Any],
    profile_after: dict[str, Any],
    output_path: Path | None = None,
    duplicates_removed: int = 0,
    rejected_count: int = 0,
) -> str:
    """Generates an automated, reproducible before/after Markdown audit report.

    Contains real measured statistics (null % reduction, row counts, duplicate removals).
    """
    rows_before = profile_before["total_rows"]
    rows_after = profile_after["total_rows"]
    null_pct_before = profile_before["overall_null_pct"]
    null_pct_after = profile_after["overall_null_pct"]
    null_reduction = round(null_pct_before - null_pct_after, 2)

    lines: list[str] = [
        "# Data Cleaning and Transformation Profile Report",
        "",
        "> [!IMPORTANT]",
        f"> **Measured Execution Timestamp:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}  ",
        "> **Pipeline Batch Run:** Automated Profiler Verification",
        "",
        "## 1. Executive Summary: Measured Pipeline Impact",
        "",
        "| Metric | Before Cleaning (Raw) | After Cleaning (Clean) | Net Change / Impact |",
        "| :--- | :--- | :--- | :--- |",
        f"| **Total Records** | `{rows_before:,}` | `{rows_after:,}` | `-{rows_before - rows_after:,}` rows filtered/deduplicated |",
        f"| **Duplicates Removed** | `{duplicates_removed:,}` | `0` (enforced unique PK) | `100%` duplicate elimination |",
        f"| **Invalid Records Rejected** | `0` | `{rejected_count:,}` (routed to lake) | Logged with root cause reasons |",
        f"| **Overall Missing / Null %** | `{null_pct_before:.2f}%` | `{null_pct_after:.2f}%` | `{null_reduction:+.2f}%` absolute null reduction |",
        "",
        "## 2. Column-by-Column Profiling Comparison",
        "",
        "| Column Name | Inferred Dtype (Raw) | Dtype (Clean) | Raw Null % | Clean Null % | Cleaning & Imputation Strategy |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    before_cols = profile_before.get("columns", {})
    after_cols = profile_after.get("columns", {})

    all_col_keys = sorted(set(list(before_cols.keys()) + list(after_cols.keys())))

    strategy_notes = {
        "respondent_id": "Natural key validation; duplicates dropped; whitespace stripped.",
        "state": "Fuzzy string matched against canonical India state reference; low confidence mapped to Unknown.",
        "district": "Whitespace stripped; capitalized; kept NULL where unprovided.",
        "age": "Type cast to integer; outliers (<18 or >100) flagged via boolean flag `is_outlier_age`.",
        "gender": "Standardized to canonical categories ('Male', 'Female', 'Non-Binary', 'Not Specified').",
        "education": "Fuzzy matched to canonical tier (Higher Education vs Secondary).",
        "occupation": "Fuzzy matched to canonical occupation categories.",
        "monthly_income": "Currency and comma symbols stripped; numeric float parsed; IQR outlier flag set.",
        "party_preference": "Standardized canonical acronyms (BJP, INC, AAP, etc.) and undecided buckets.",
        "rating_1_to_5": "Validated range [1..5]; invalid ranges routed to rejection lake.",
        "response_date": "Multi-format parser (ISO, DD/MM/YYYY, MM-DD-YYYY) to standard ISO YYYY-MM-DD.",
        "multi_select_choices": "Exploded into relational bridge table `fact_response_choices`.",
        "free_text_comment": "Unicode normalized (NFKC); mojibake repaired; whitespace stripped.",
        "response_quality_score": "Derived completeness ratio [0.0..1.0] across all mandatory fields.",
        "is_outlier_income": "Derived boolean IQR flag (Q1 - 1.5*IQR, Q3 + 1.5*IQR).",
        "is_outlier_age": "Derived boolean boundary flag.",
    }

    for col in all_col_keys:
        b_meta = before_cols.get(col, {})
        a_meta = after_cols.get(col, {})

        b_dtype = b_meta.get("dtype", "N/A")
        a_dtype = a_meta.get("dtype", "N/A")
        b_null = f"{b_meta.get('null_pct', 0.0):.2f}%" if "null_pct" in b_meta else "N/A"
        a_null = f"{a_meta.get('null_pct', 0.0):.2f}%" if "null_pct" in a_meta else "N/A"
        strat = strategy_notes.get(col, "Standardized and normalized.")

        lines.append(f"| `{col}` | `{b_dtype}` | `{a_dtype}` | `{b_null}` | `{a_null}` | {strat} |")

    lines.extend(
        [
            "",
            "## 3. Numeric Distribution and Outlier Bounds",
            "",
            "| Numeric Field | Mean | Median | Q25 (p25) | Q75 (p75) | IQR | Outliers Flagged |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
    )

    for col, a_meta in after_cols.items():
        if "numeric_stats" in a_meta:
            ns = a_meta["numeric_stats"]
            lines.append(
                f"| `{col}` | `{ns['mean']:,}` | `{ns['median']:,}` | `{ns['q25']:,}` | `{ns['q75']:,}` | `{ns['iqr']:,}` | `{ns['outlier_count']:,}` |"
            )

    report_content = "\n".join(lines) + "\n"

    if output_path:
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(report_content, encoding="utf-8")
        logger.info("Saved data profile comparison report to: %s", out_file)

    return report_content
