"""Unit tests for survey_pipeline.standardize module."""

from survey_pipeline.standardize import Standardizer


def test_standardize_state_exact(standardizer: Standardizer):
    canonical, code, region, zone = standardizer.match_state("Maharashtra")
    assert canonical == "Maharashtra"
    assert code == "MH"
    assert region == "West"


def test_standardize_state_alias(standardizer: Standardizer):
    canonical_up, code_up, region_up, zone_up = standardizer.match_state("UP")
    assert canonical_up == "Uttar Pradesh"
    assert code_up == "UP"
    assert region_up == "North"

    canonical_mh, code_mh, _, _ = standardizer.match_state("MH")
    assert canonical_mh == "Maharashtra"
    assert code_mh == "MH"


def test_standardize_state_fuzzy(standardizer: Standardizer):
    # Typo: 'Maharastra' missing 'h'
    canonical, code, region, _ = standardizer.match_state("Maharastra")
    assert canonical == "Maharashtra"
    assert code == "MH"

    # Typo: 'Karnatka'
    canonical_k, code_k, _, _ = standardizer.match_state("Karnatka")
    assert canonical_k == "Karnataka"
    assert code_k == "KA"


def test_standardize_state_unmatched_fallback(standardizer: Standardizer):
    canonical, code, region, _ = standardizer.match_state("XYZ_Unrecognized_State_123")
    assert code == "OTH"
    assert region == "Other"


def test_standardize_party_exact_and_alias(standardizer: Standardizer):
    canonical_bjp, code_bjp = standardizer.match_party("BJP")
    assert canonical_bjp == "Bharatiya Janata Party"
    assert code_bjp == "BJP"

    canonical_inc, code_inc = standardizer.match_party("Congress")
    assert canonical_inc == "Indian National Congress"
    assert code_inc == "INC"


def test_standardize_party_fuzzy(standardizer: Standardizer):
    canonical, code = standardizer.match_party("Bhartiya Janta Party")
    assert canonical == "Bharatiya Janata Party"
    assert code == "BJP"


def test_standardize_education_mapping(standardizer: Standardizer):
    canonical, tier = standardizer.match_education("B.Tech")
    assert "Bachelor" in canonical
    assert tier == "Higher Education"


def test_standardize_occupation_mapping(standardizer: Standardizer):
    canonical, category = standardizer.match_occupation("Software Engineer")
    assert "Software" in canonical
    assert category == "Technology"


def test_standardize_gender():
    assert Standardizer.standardize_gender("m") == "Male"
    assert Standardizer.standardize_gender("FEMALE") == "Female"
    assert Standardizer.standardize_gender("nonbinary") == "Non-Binary"
    assert Standardizer.standardize_gender("prefer not to say") == "Prefer not to say"
    assert Standardizer.standardize_gender(None) == "Not Specified"
