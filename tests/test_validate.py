"""Unit tests for survey_pipeline.validate module."""

import pandas as pd
import pytest

from survey_pipeline.validate import DataQualityError, DataQualitySuite


def test_validate_required_columns_pass():
    df = pd.DataFrame(columns=["respondent_id", "state", "age", "gender"])
    suite = DataQualitySuite(batch_id="TEST_BATCH")
    suite.check_schema_presence(df, ["respondent_id", "state", "age"])
    assert len(suite.results) == 1
    assert suite.results[0].passed
    suite.assert_no_errors()


def test_validate_required_columns_fail():
    df = pd.DataFrame(columns=["respondent_id", "gender"])
    suite = DataQualitySuite(batch_id="TEST_BATCH")
    suite.check_schema_presence(df, ["respondent_id", "state", "age"])
    assert len(suite.results) == 1
    assert not suite.results[0].passed
    assert suite.results[0].severity == "ERROR"
    with pytest.raises(DataQualityError):
        suite.assert_no_errors()


def test_validate_not_null_check():
    df_clean = pd.DataFrame({"id": ["R1", "R2", "R3"]})
    suite = DataQualitySuite(batch_id="TEST_BATCH")
    suite.check_not_null(df_clean, "id")
    assert suite.results[0].passed

    df_dirty = pd.DataFrame({"id": ["R1", None, "R3"]})
    suite_dirty = DataQualitySuite(batch_id="TEST_BATCH")
    suite_dirty.check_not_null(df_dirty, "id")
    assert not suite_dirty.results[0].passed
    assert suite_dirty.results[0].failed_records_count == 1


def test_validate_uniqueness():
    df_unique = pd.DataFrame({"resp_id": ["A", "B", "C"]})
    suite = DataQualitySuite(batch_id="TEST_BATCH")
    suite.check_uniqueness(df_unique, "resp_id")
    assert suite.results[0].passed

    df_dup = pd.DataFrame({"resp_id": ["A", "B", "A"]})
    suite_dup = DataQualitySuite(batch_id="TEST_BATCH")
    suite_dup.check_uniqueness(df_dup, "resp_id")
    assert not suite_dup.results[0].passed
    assert suite_dup.results[0].failed_records_count == 1


def test_validate_range():
    df_valid = pd.DataFrame({"rating": [1, 3, 5, 4]})
    suite = DataQualitySuite(batch_id="TEST_BATCH")
    suite.check_range(df_valid, "rating", min_val=1, max_val=5)
    assert suite.results[0].passed

    df_invalid = pd.DataFrame({"rating": [1, 6, -2, 5]})
    suite_inv = DataQualitySuite(batch_id="TEST_BATCH")
    suite_inv.check_range(df_invalid, "rating", min_val=1, max_val=5)
    assert not suite_inv.results[0].passed
    assert suite_inv.results[0].failed_records_count == 2


def test_validate_row_count_reconciliation():
    suite = DataQualitySuite(batch_id="TEST_BATCH")
    # Equation: raw (100) == clean (80) + rejected (15) + dropped_dups (5)
    suite.check_row_reconciliation(
        raw_count=100,
        clean_count=80,
        rejected_count=15,
        duplicates_dropped=5,
    )
    assert suite.results[0].passed

    # Equation mismatch: raw (100) != clean (70) + rejected (15) + dropped_dups (5)
    suite_mismatch = DataQualitySuite(batch_id="TEST_BATCH")
    suite_mismatch.check_row_reconciliation(
        raw_count=100,
        clean_count=70,
        rejected_count=15,
        duplicates_dropped=5,
    )
    assert not suite_mismatch.results[0].passed
