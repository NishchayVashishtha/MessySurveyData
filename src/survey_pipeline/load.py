"""Warehouse loading coordinator: manages dual-store ingestion into MongoDB and PostgreSQL."""

from typing import Any

import pandas as pd
from pymongo.database import Database
from sqlalchemy import Engine

from survey_pipeline.clean import CleanResult
from survey_pipeline.logging_config import get_logger
from survey_pipeline.metrics import PipelineMetrics
from survey_pipeline.mongo_db import (
    insert_rejected_responses,
    log_pipeline_run_mongo,
    setup_mongo_indexes,
    upsert_raw_responses,
)
from survey_pipeline.pg_db import (
    init_database_schema,
    record_audit_pipeline_run,
    record_data_quality_results_pg,
    record_rejected_rows_pg,
    upsert_dim_education,
    upsert_dim_geography,
    upsert_dim_occupation,
    upsert_dim_respondent,
    upsert_fact_choices,
    upsert_fact_responses,
)
from survey_pipeline.validate import CheckResult

logger = get_logger(__name__)


def load_raw_to_mongodb(
    db: Database,
    df_raw: pd.DataFrame,
    batch_id: str,
    source_file: str,
) -> int:
    """Loads verbatim raw survey responses into MongoDB landing zone.

    Idempotent: updates existing records by record_hash.
    """
    setup_mongo_indexes(db)
    raw_dicts = df_raw.to_dict(orient="records")
    loaded = upsert_raw_responses(db, raw_dicts, batch_id=batch_id, source_file=source_file)
    return loaded


def load_clean_to_postgres(
    engine: Engine,
    clean_result: CleanResult,
    batch_id: str,
    source_file: str,
) -> int:
    """Loads cleaned, standardized, validated data into PostgreSQL dimensional warehouse.

    Idempotent: dimension and fact tables use INSERT ... ON CONFLICT (...) DO UPDATE.
    """
    logger.info("Initializing warehouse relational schema if needed...")
    init_database_schema(engine)

    df_clean = clean_result.cleaned_df

    # 1. Upsert Dimensions
    geo_map = upsert_dim_geography(df_clean, engine)
    occ_map = upsert_dim_occupation(df_clean, engine)
    edu_map = upsert_dim_education(df_clean, engine)
    resp_map = upsert_dim_respondent(df_clean, engine, batch_id=batch_id)

    # 2. Upsert Facts
    facts_loaded = upsert_fact_responses(
        df=df_clean,
        engine=engine,
        geo_map=geo_map,
        occ_map=occ_map,
        edu_map=edu_map,
        resp_map=resp_map,
        batch_id=batch_id,
        source_file=source_file,
    )

    # 3. Upsert Multi-Select Choices Bridge Table
    if clean_result.choices_records:
        upsert_fact_choices(clean_result.choices_records, engine, batch_id=batch_id)

    # 4. Record Rejected Rows in Audit Schema
    if clean_result.rejected_records:
        record_rejected_rows_pg(engine, clean_result.rejected_records)

    return facts_loaded


def finalize_audit_records(
    metrics: PipelineMetrics,
    dq_results: list[CheckResult],
    rejected_records: list[dict[str, Any]],
    mongo_db: Database | None = None,
    pg_engine: Engine | None = None,
) -> None:
    """Records audit logs, run metrics, and DQ check evaluations across both stores."""
    metrics_dict = metrics.to_dict()

    # Log to MongoDB
    if mongo_db is not None:
        try:
            log_pipeline_run_mongo(mongo_db, metrics_dict)
            if rejected_records:
                insert_rejected_responses(mongo_db, rejected_records)
        except Exception as e:
            logger.warning("Failed to record audit logs to MongoDB: %s", e)

    # Log to PostgreSQL
    if pg_engine is not None:
        try:
            record_audit_pipeline_run(pg_engine, metrics_dict)
            if dq_results:
                dq_dicts = [r.to_dict(batch_id=metrics.batch_id) for r in dq_results]
                record_data_quality_results_pg(pg_engine, dq_dicts)
        except Exception as e:
            logger.warning("Failed to record audit logs to PostgreSQL: %s", e)
