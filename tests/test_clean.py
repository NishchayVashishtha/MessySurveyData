"""Unit tests for survey_pipeline.clean module."""

import numpy as np
import pandas as pd

from survey_pipeline.clean import (
    clean_survey_dataset,
    compute_response_quality_score,
    deduplicate_records,
    derive_age_group,
    derive_income_bracket,
    detect_outliers_iqr,
    normalize_column_names,
    parse_date_safe,
    parse_numeric_safe,
    repair_mojibake_and_unicode,
    unify_missing_values,
)


def test_normalize_column_names():
    df = pd.DataFrame(columns=["Respondent ID", "Monthly Income (INR)", "State/UT", "Rating [1-5]"])
    normalized = normalize_column_names(df)
    assert list(normalized.columns) == [
        "respondent_id",
        "monthly_income_inr",
        "stateut",
        "rating_1_5",
    ]


def test_unify_missing_values():
    df = pd.DataFrame(
        {
            "col_a": ["Valid", "N/A", "na", "-", "None", "", "nan", "  null  "],
            "col_b": [1, 2, 3, 4, 5, 6, 7, 8],
        }
    )
    cleaned = unify_missing_values(df)
    assert cleaned["col_a"].iloc[0] == "Valid"
    for i in range(1, 8):
        assert pd.isna(cleaned["col_a"].iloc[i])


def test_repair_mojibake_and_unicode():
    assert repair_mojibake_and_unicode("Café") == "Café"
    assert repair_mojibake_and_unicode("Hello\xa0World") == "Hello World"
    assert repair_mojibake_and_unicode("  Trim Me  ") == "Trim Me"
    assert repair_mojibake_and_unicode("CafÃ©") == "Café"
    assert repair_mojibake_and_unicode(None) is None


def test_parse_date_safe():
    assert parse_date_safe("2024-03-15") == "2024-03-15"
    assert parse_date_safe("15/03/2024") == "2024-03-15"
    assert parse_date_safe("invalid_date") is None
    assert parse_date_safe(None) is None
    assert parse_date_safe("N/A") is None


def test_parse_numeric_safe():
    assert parse_numeric_safe("₹75,000") == 75000.0
    assert parse_numeric_safe("$1,200.50") == 1200.50
    assert parse_numeric_safe("  50000  ") == 50000.0
    assert parse_numeric_safe("N/A") is None
    assert parse_numeric_safe("-") is None
    assert parse_numeric_safe(None) is None


def test_detect_outliers_iqr():
    values = [50000 + i * 500 for i in range(20)] + [1000000]
    series = pd.Series(values)
    flags = detect_outliers_iqr(series, factor=1.5)
    assert not flags.iloc[0]
    assert flags.iloc[-1]  # Extreme outlier flagged as True


def test_derive_age_group():
    assert derive_age_group(15) == "<18"
    assert derive_age_group(22) == "18-25"
    assert derive_age_group(30) == "26-35"
    assert derive_age_group(45) == "36-50"
    assert derive_age_group(58) == "51-65"
    assert derive_age_group(72) == "65+"
    assert derive_age_group(None) == "Unknown"
    assert derive_age_group(np.nan) == "Unknown"


def test_derive_income_bracket():
    assert derive_income_bracket(15000) == "< ₹25k"
    assert derive_income_bracket(35000) == "₹25k-₹50k"
    assert derive_income_bracket(75000) == "₹50k-₹100k"
    assert derive_income_bracket(150000) == "₹100k-₹200k"
    assert derive_income_bracket(300000) == "₹200k+"
    assert derive_income_bracket(None) == "Not Specified"


def test_compute_response_quality_score():
    row_full = pd.Series({"a": 1, "b": "val", "c": 3})
    assert compute_response_quality_score(row_full, ["a", "b", "c"]) == 1.0

    row_partial = pd.Series({"a": 1, "b": None, "c": 3})
    assert round(compute_response_quality_score(row_partial, ["a", "b", "c"]), 2) == 0.67

    row_empty = pd.Series({"a": None, "b": "", "c": np.nan})
    assert compute_response_quality_score(row_empty, ["a", "b", "c"]) == 0.0


def test_deduplicate_records():
    df = pd.DataFrame(
        {
            "respondent_id": ["R1", "R2", "R1", "R3"],
            "val": [10, 20, 10, 30],
        }
    )
    deduped, removed = deduplicate_records(df, key_column="respondent_id")
    assert removed == 1
    assert len(deduped) == 3
    assert list(deduped["respondent_id"]) == ["R1", "R2", "R3"]


def test_clean_survey_dataset_end_to_end(dirty_sample_df, standardizer):
    res = clean_survey_dataset(
        df_raw=dirty_sample_df,
        batch_id="TEST_BATCH",
        source_file="test_dirty.csv",
        standardizer=standardizer,
    )

    # 4 rows input: 1 duplicate dropped -> 3 rows evaluated -> 1 row with age -5 rejected -> 2 clean rows
    assert res.duplicates_removed == 1
    assert len(res.cleaned_df) == 2
    assert len(res.rejected_records) == 1
    assert res.rejected_records[0]["rule_failed"] == "PLAUSIBLE_AGE_LIMIT"

    # Verify derived columns
    assert "age_group" in res.cleaned_df.columns
    assert "income_bracket" in res.cleaned_df.columns
    assert "response_quality_score" in res.cleaned_df.columns
    assert "is_outlier_income" in res.cleaned_df.columns
