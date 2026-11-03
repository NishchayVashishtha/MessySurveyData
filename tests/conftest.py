"""Pytest configuration and shared test fixtures."""

from pathlib import Path

import pandas as pd
import pytest

from survey_pipeline.standardize import Standardizer

TEST_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TEST_DIR.parent


@pytest.fixture(scope="session")
def standardizer() -> Standardizer:
    """Session-scoped Standardizer instance using reference CSVs."""
    ref_dir = PROJECT_ROOT / "data" / "reference"
    return Standardizer(ref_dir=ref_dir)


@pytest.fixture
def dirty_sample_df() -> pd.DataFrame:
    """Provides a sample dirty DataFrame containing typical survey noise."""
    return pd.DataFrame(
        [
            {
                "respondent_id": "RESP_001",
                "state": "UP",
                "district": "Lucknow",
                "age": "28",
                "gender": "male",
                "education": "B.Tech Computer Science",
                "occupation": "Software Engineer",
                "monthly_income": "₹75,000",
                "party_preference": "BJP",
                "rating_1_to_5": "4",
                "response_date": "2024-03-15",
                "free_text_comment": "Good governance  ",
            },
            {
                "respondent_id": "RESP_002",
                "state": "Maharastra",  # slight typo for fuzzy test
                "district": "Pune",
                "age": "-5",  # Invalid age
                "gender": "Female",
                "education": "M.B.A.",
                "occupation": "Data Analyst",
                "monthly_income": "50,000",
                "party_preference": "INC",
                "rating_1_to_5": "5",
                "response_date": "15/03/2024",  # Mixed date format
                "free_text_comment": "N/A",
            },
            {
                "respondent_id": "RESP_001",  # Duplicate respondent_id
                "state": "UP",
                "district": "Lucknow",
                "age": "28",
                "gender": "male",
                "education": "B.Tech Computer Science",
                "occupation": "Software Engineer",
                "monthly_income": "₹75,000",
                "party_preference": "BJP",
                "rating_1_to_5": "4",
                "response_date": "2024-03-15",
                "free_text_comment": "Good governance",
            },
            {
                "respondent_id": "RESP_003",
                "state": "Tamil Nadu",
                "district": "Chennai",
                "age": "45",
                "gender": "F",
                "education": "High School",
                "occupation": "Teacher",
                "monthly_income": "-",  # Missing representation
                "party_preference": "DMK",
                "rating_1_to_5": "3",
                "response_date": "2024-01-10",
                "free_text_comment": "No issues",
            },
        ]
    )
