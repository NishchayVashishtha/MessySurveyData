"""Integration test verifying end-to-end pipeline execution and strict idempotency."""

from pathlib import Path

import pytest
from sqlalchemy import text

from survey_pipeline.clean import clean_survey_dataset
from survey_pipeline.extract import extract_survey_data
from survey_pipeline.load import load_clean_to_postgres, load_raw_to_mongodb
from survey_pipeline.mongo_db import get_mongo_db, setup_mongo_indexes
from survey_pipeline.pg_db import get_pg_engine, init_database_schema
from survey_pipeline.standardize import Standardizer


@pytest.fixture(scope="module")
def synthetic_test_csv(tmp_path_factory) -> Path:
    """Generates a small test survey CSV file with duplicates and invalid values."""
    from scripts.generate_dirty_survey import generate_dirty_survey

    tmp_dir = tmp_path_factory.mktemp("data")
    file_path = tmp_dir / "dirty_test_survey.csv"
    df = generate_dirty_survey(num_rows=200, seed=123)
    df.to_csv(file_path, index=False)
    return file_path


def test_end_to_end_pipeline_and_idempotency(synthetic_test_csv: Path, standardizer: Standardizer):
    """Verifies that running the pipeline twice with identical batch ID produces zero duplicate rows."""
    engine = get_pg_engine()
    mongo_db = get_mongo_db()
    batch_id = "BATCH_TEST_IDEMPOTENCY"

    # Setup schemas
    init_database_schema(engine)
    setup_mongo_indexes(mongo_db)

    def run_iteration():
        # 1. Extract
        df_raw, source_file, checksum = extract_survey_data(
            source="synthetic", custom_file=synthetic_test_csv
        )
        # 2. Raw Mongo Landing
        load_raw_to_mongodb(db=mongo_db, df_raw=df_raw, batch_id=batch_id, source_file=source_file)
        # 3. Clean
        clean_res = clean_survey_dataset(
            df_raw=df_raw,
            batch_id=batch_id,
            source_file=source_file,
            standardizer=standardizer,
        )
        # 4. Postgres Loading
        facts_loaded = load_clean_to_postgres(
            engine=engine,
            clean_result=clean_res,
            batch_id=batch_id,
            source_file=source_file,
        )
        return facts_loaded, clean_res

    # --- FIRST RUN ---
    facts_run_1, clean_res_1 = run_iteration()
    assert facts_run_1 > 0
    assert clean_res_1.duplicates_removed > 0

    # Query counts after Run 1
    with engine.connect() as conn:
        res = conn.execute(
            text("SELECT COUNT(*) FROM warehouse.fact_responses WHERE batch_id = :b;"),
            {"b": batch_id},
        )
        facts_count_1 = res.scalar()

        res_choices = conn.execute(
            text("""
                SELECT COUNT(*) FROM warehouse.fact_response_choices c
                JOIN warehouse.fact_responses f ON c.response_id = f.response_id
                WHERE f.batch_id = :b;
            """),
            {"b": batch_id},
        )
        choices_count_1 = res_choices.scalar()

    mongo_raw_count_1 = mongo_db["raw_responses"].count_documents({"batch_id": batch_id})

    # --- SECOND RUN (IDEMPOTENCY CHECK) ---
    facts_run_2, clean_res_2 = run_iteration()
    assert facts_run_2 == facts_run_1

    # Query counts after Run 2
    with engine.connect() as conn:
        res = conn.execute(
            text("SELECT COUNT(*) FROM warehouse.fact_responses WHERE batch_id = :b;"),
            {"b": batch_id},
        )
        facts_count_2 = res.scalar()

        res_choices = conn.execute(
            text("""
                SELECT COUNT(*) FROM warehouse.fact_response_choices c
                JOIN warehouse.fact_responses f ON c.response_id = f.response_id
                WHERE f.batch_id = :b;
            """),
            {"b": batch_id},
        )
        choices_count_2 = res_choices.scalar()

    mongo_raw_count_2 = mongo_db["raw_responses"].count_documents({"batch_id": batch_id})

    # Assert zero row duplication
    assert (
        facts_count_2 == facts_count_1
    ), "Fact table row count changed on re-run (idempotency violation)!"
    assert (
        choices_count_2 == choices_count_1
    ), "Choices bridge count changed on re-run (idempotency violation)!"
    assert (
        mongo_raw_count_2 == mongo_raw_count_1
    ), "MongoDB raw doc count changed on re-run (idempotency violation)!"
