"""Data cleaning, normalization, outlier detection, and feature derivation."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from survey_pipeline.logging_config import get_logger
from survey_pipeline.profile import profile_dataframe
from survey_pipeline.standardize import Standardizer, default_standardizer

logger = get_logger(__name__)

# Standard set of missing value representations across survey instruments
DEFAULT_MISSING_TOKENS = {
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

# Known mojibake character mappings for UTF-8 misinterpretations
MOJIBAKE_MAP = {
    "Ã©": "é",
    "Ã¼": "ü",
    "Ã¯": "ï",
    "Ã§": "ç",
    "Ã": "à",
    "â€™": "'",
    "â€œ": '"',
    "â€": '"',
    "â€“": "-",
    "â€”": "-",
}


@dataclass
class CleanResult:
    """Encapsulates the complete result of cleaning and transformation."""

    cleaned_df: pd.DataFrame
    rejected_records: list[dict[str, Any]]
    choices_records: list[dict[str, Any]]
    duplicates_removed: int
    before_profile: dict[str, Any]
    after_profile: dict[str, Any]


def normalize_column_name(col: str) -> str:
    """Converts a column name to standardized snake_case."""
    s = unicodedata.normalize("NFKC", str(col)).strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s-]+", "_", s)
    return s.lower()


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Returns a copy of the dataframe with normalized snake_case column names."""
    df_out = df.copy()
    df_out.columns = [normalize_column_name(c) for c in df_out.columns]
    return df_out


def repair_mojibake_and_unicode(text_val: str | None) -> str | None:
    """Normalizes Unicode (NFKC), repairs common mojibake sequences, and strips whitespace."""
    if text_val is None or pd.isna(text_val):
        return None

    s = str(text_val)
    # Mojibake string replacements
    for bad, good in MOJIBAKE_MAP.items():
        if bad in s:
            s = s.replace(bad, good)

    # Unicode NFKC normalization
    s = unicodedata.normalize("NFKC", s).strip()
    return s if s else None


def unify_missing_values(df: pd.DataFrame, missing_tokens: set | None = None) -> pd.DataFrame:
    """Replaces all ambiguous string missing tokens with np.nan."""
    tokens = missing_tokens or DEFAULT_MISSING_TOKENS
    df_out = df.copy()

    for col in df_out.columns:
        if df_out[col].dtype == object or pd.api.types.is_string_dtype(df_out[col]):
            mask = df_out[col].apply(
                lambda x: True if pd.isna(x) or str(x).strip().lower() in tokens else False
            )
            df_out.loc[mask, col] = np.nan

    return df_out


def parse_numeric_safe(val: Any) -> float | None:
    """Safely parses raw text with currency symbols, commas, or spaces into float."""
    if val is None or pd.isna(val):
        return None

    s = str(val).strip()
    if s.lower() in DEFAULT_MISSING_TOKENS:
        return None

    # Remove currency symbols (₹, $, €, £), commas, percentage signs
    cleaned = re.sub(r"[₹$€£,%\s]", "", s)
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def parse_date_safe(val: Any) -> str | None:
    """Parses diverse date formats safely into standard ISO format (YYYY-MM-DD).

    Supports:
    - YYYY-MM-DD
    - DD/MM/YYYY
    - MM-DD-YYYY or MM/DD/YYYY
    - YYYY/MM/DD
    - ISO timestamps
    """
    if val is None or pd.isna(val):
        return None

    s = str(val).strip()
    if s.lower() in DEFAULT_MISSING_TOKENS:
        return None

    # Try common formats explicitly
    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m-%d-%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
    ]

    for fmt in formats:
        try:
            dt = pd.to_datetime(s, format=fmt, errors="raise")
            return dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue

    # Fallback to flexible pandas parser
    try:
        dt = pd.to_datetime(s, errors="coerce")
        if pd.notna(dt):
            return dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    return None


def detect_outliers_iqr(series: pd.Series, factor: float = 1.5) -> pd.Series:
    """Flags numeric outliers using the Interquartile Range (IQR) method.

    Returns:
        Boolean Series where True indicates an outlier.
    """
    valid = series.dropna()
    if len(valid) < 4:
        return pd.Series(False, index=series.index)

    q25 = valid.quantile(0.25)
    q75 = valid.quantile(0.75)
    iqr = q75 - q25
    lower_bound = q25 - factor * iqr
    upper_bound = q75 + factor * iqr

    return series.apply(
        lambda x: bool(x < lower_bound or x > upper_bound) if pd.notna(x) else False
    )


def deduplicate_records(
    df: pd.DataFrame,
    key_column: str = "respondent_id",
) -> tuple[pd.DataFrame, int]:
    """Drops duplicate records on the natural key, keeping first occurrence.

    Returns:
        Tuple of (deduplicated DataFrame, count of dropped duplicates).
    """
    if key_column not in df.columns:
        return df, 0

    initial_count = len(df)
    df_dedup = df.drop_duplicates(subset=[key_column], keep="first")
    dropped_count = initial_count - len(df_dedup)
    logger.info("Deduplication on '%s': %d duplicates dropped.", key_column, dropped_count)
    return df_dedup, dropped_count


def derive_age_group(age: float | None) -> str:
    """Categorizes numerical age into demographic age brackets."""
    if age is None or pd.isna(age):
        return "Unknown"
    a = int(age)
    if a < 18:
        return "<18"
    elif a <= 25:
        return "18-25"
    elif a <= 35:
        return "26-35"
    elif a <= 50:
        return "36-50"
    elif a <= 65:
        return "51-65"
    else:
        return "65+"


def derive_income_bracket(income: float | None) -> str:
    """Categorizes monthly income (INR) into standardized income tiers."""
    if income is None or pd.isna(income):
        return "Not Specified"
    inc = float(income)
    if inc < 25000:
        return "< ₹25k"
    elif inc < 50000:
        return "₹25k-₹50k"
    elif inc < 100000:
        return "₹50k-₹100k"
    elif inc < 200000:
        return "₹100k-₹200k"
    else:
        return "₹200k+"


def compute_response_quality_score(row: pd.Series, check_cols: list[str]) -> float:
    """Calculates completeness ratio (non-null answers over evaluated questions)."""
    valid_count = sum(
        1 for c in check_cols if pd.notna(row.get(c)) and str(row.get(c)).strip() != ""
    )
    return round(valid_count / len(check_cols), 4) if check_cols else 1.0


def explode_multiselect_choices(
    df: pd.DataFrame,
    col_name: str = "multi_select_choices",
    category: str = "issue_or_skill",
    batch_id: str = "auto",
) -> list[dict[str, Any]]:
    """Explodes semicolon-separated multi-select fields into bridge records."""
    choices_records = []
    if col_name not in df.columns:
        return choices_records

    for _, row in df.iterrows():
        resp_id = str(row["respondent_id"])
        natural_response_id = f"{resp_id}_{batch_id}"
        val = row.get(col_name)
        if pd.isna(val) or not val:
            continue

        parts = [p.strip() for p in str(val).split(";") if p.strip()]
        for choice in set(parts):  # deduplicate within individual respondent
            choices_records.append(
                {
                    "natural_response_id": natural_response_id,
                    "choice_category": category,
                    "choice_value": choice,
                }
            )

    return choices_records


def clean_survey_dataset(
    df_raw: pd.DataFrame,
    batch_id: str,
    source_file: str,
    standardizer: Standardizer | None = None,
) -> CleanResult:
    """Master cleaning pipeline. Executes all composable cleaning and validation steps.

    Workflow:
    1. Computes raw baseline profile.
    2. Column name normalization (snake_case).
    3. Unicode & text repair (NFKC, mojibake).
    4. Missing value unification.
    5. Deduplication on natural key (respondent_id).
    6. Safe type casting (age, income, dates, rating).
    7. Fuzzy categorical standardization (state, party, education, occupation, gender).
    8. Outlier detection (IQR income, age boundaries).
    9. Rejection routing for severe validation violations.
    10. Feature derivation (age_group, income_bracket, quality_score).
    11. Explodes multi-select choices.
    12. Computes clean post-transformation profile.
    """
    logger.info("Starting survey data cleaning pipeline for batch '%s'...", batch_id)
    std = standardizer or default_standardizer

    # 1. Profile Raw Baseline
    before_profile = profile_dataframe(df_raw, stage_name="raw")

    # 2. Column Normalization
    df = normalize_column_names(df_raw)

    # 3. Text & Unicode Normalization
    for col in df.columns:
        if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
            df[col] = df[col].apply(repair_mojibake_and_unicode)

    # 4. Unify Missing Values
    df = unify_missing_values(df)

    # 5. Deduplication
    if "respondent_id" not in df.columns:
        df["respondent_id"] = [f"GEN_{i+1:06d}" for i in range(len(df))]
    df, duplicates_removed = deduplicate_records(df, key_column="respondent_id")

    # 6. Safe Type Parsing
    # Parse Age
    if "age" in df.columns:
        df["raw_age"] = df["age"]
        df["age"] = df["age"].apply(parse_numeric_safe)

    # Parse Monthly Income
    if "monthly_income" in df.columns:
        df["monthly_income"] = df["monthly_income"].apply(parse_numeric_safe)

    # Parse Response Date
    if "response_date" in df.columns:
        df["response_date"] = df["response_date"].apply(parse_date_safe)

    # Parse Rating (1 to 5)
    if "rating_1_to_5" in df.columns:
        df["rating_1_to_5"] = df["rating_1_to_5"].apply(parse_numeric_safe)

    # 7. Fuzzy Standardization
    if "state" in df.columns:
        state_results = [std.match_state(s) for s in df["state"]]
        df["state"] = [res[0] for res in state_results]
        df["state_code"] = [res[1] for res in state_results]
        df["region"] = [res[2] for res in state_results]
        df["zone"] = [res[3] for res in state_results]

    if "party_preference" in df.columns:
        party_results = [std.match_party(p) for p in df["party_preference"]]
        df["party_preference"] = [res[0] for res in party_results]

    if "education" in df.columns:
        edu_results = [std.match_education(e) for e in df["education"]]
        df["education"] = [res[0] for res in edu_results]
        df["education_tier"] = [res[1] for res in edu_results]

    if "occupation" in df.columns:
        occ_results = [std.match_occupation(o) for o in df["occupation"]]
        df["occupation"] = [res[0] for res in occ_results]
        df["occupation_category"] = [res[1] for res in occ_results]

    if "gender" in df.columns:
        df["gender"] = df["gender"].apply(std.standardize_gender)

    # 8. Outlier Detection
    if "monthly_income" in df.columns:
        df["is_outlier_income"] = detect_outliers_iqr(df["monthly_income"], factor=1.5)
    else:
        df["is_outlier_income"] = False

    if "age" in df.columns:
        df["is_outlier_age"] = df["age"].apply(
            lambda a: bool(a < 18 or a > 100) if pd.notna(a) else False
        )
    else:
        df["is_outlier_age"] = False

    # 9. Validation & Rejection Routing
    rejected_records: list[dict[str, Any]] = []
    valid_indices = []

    for idx, row in df.iterrows():
        resp_id = str(row["respondent_id"])
        rejection_reason = None
        rule_name = None
        failed_col = None

        # Check: Rating outside valid range [1..5]
        if pd.notna(row.get("rating_1_to_5")):
            r = row["rating_1_to_5"]
            if r < 1 or r > 5:
                rule_name = "VALID_RATING_RANGE"
                rejection_reason = f"Rating {r} is outside allowed range [1, 5]."
                failed_col = "rating_1_to_5"

        # Check: Severe Age boundary violations (< 10 or > 120)
        if not rule_name and pd.notna(row.get("age")):
            a = row["age"]
            if a < 10 or a > 120:
                rule_name = "PLAUSIBLE_AGE_LIMIT"
                rejection_reason = (
                    f"Age {a} is physically implausible for survey respondent (<10 or >120)."
                )
                failed_col = "age"

        if rule_name:
            rejected_records.append(
                {
                    "batch_id": batch_id,
                    "natural_respondent_id": resp_id,
                    "rule_failed": rule_name,
                    "severity": "ERROR",
                    "failed_column": failed_col,
                    "invalid_value": str(row.get(failed_col)),
                    "error_reason": rejection_reason,
                    "raw_payload": row.to_dict(),
                }
            )
        else:
            valid_indices.append(idx)

    # Filter to clean rows only
    clean_df = df.loc[valid_indices].copy()
    logger.info(
        "Validation complete: %d valid records retained, %d invalid records rejected.",
        len(clean_df),
        len(rejected_records),
    )

    # 10. Derived Features
    clean_df["age_group"] = (
        clean_df["age"].apply(derive_age_group) if "age" in clean_df.columns else "Unknown"
    )
    clean_df["income_bracket"] = (
        clean_df["monthly_income"].apply(derive_income_bracket)
        if "monthly_income" in clean_df.columns
        else "Not Specified"
    )

    core_cols = [
        c
        for c in [
            "state",
            "age",
            "gender",
            "education",
            "occupation",
            "party_preference",
            "rating_1_to_5",
        ]
        if c in clean_df.columns
    ]
    clean_df["response_quality_score"] = clean_df.apply(
        lambda r: compute_response_quality_score(r, core_cols), axis=1
    )

    # 11. Explode Multi-select Choices
    choices_records = explode_multiselect_choices(
        clean_df,
        col_name="multi_select_choices",
        category="survey_issue",
        batch_id=batch_id,
    )

    # 12. Profile Post-transformation
    after_profile = profile_dataframe(clean_df, stage_name="cleaned")

    return CleanResult(
        cleaned_df=clean_df,
        rejected_records=rejected_records,
        choices_records=choices_records,
        duplicates_removed=duplicates_removed,
        before_profile=before_profile,
        after_profile=after_profile,
    )
