"""PostgreSQL warehouse client and idempotent upsert helpers."""

from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
from sqlalchemy import create_engine, Engine, text
from sqlalchemy.pool import QueuePool

from survey_pipeline.config import settings
from survey_pipeline.logging_config import get_logger

logger = get_logger(__name__)


def get_pg_engine(url: Optional[str] = None) -> Engine:
    """Creates an enterprise-grade SQLAlchemy Engine with connection pooling and health checks.

    Args:
        url: Optional PostgreSQL connection URL. Defaults to settings.postgres.url.

    Returns:
        SQLAlchemy Engine instance.
    """
    connection_url = url or settings.postgres.url
    logger.debug("Connecting to PostgreSQL at %s:%s", settings.postgres.host, settings.postgres.port)

    engine = create_engine(
        connection_url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=True,
    )
    return engine


def init_database_schema(engine: Engine, sql_dir: Optional[Path] = None) -> None:
    """Executes the DDL schema scripts in sequential order.

    Idempotent operation: creates schemas, tables, constraints, indexes, and views if not exists.
    """
    target_sql_dir = sql_dir or settings.sql_dir
    sql_files = [
        "01_init_schemas.sql",
        "02_warehouse_tables.sql",
        "03_indexes.sql",
        "04_analytics_views.sql",
    ]

    logger.info("Initializing PostgreSQL database schemas from %s...", target_sql_dir)
    with engine.begin() as conn:
        for fname in sql_files:
            file_path = target_sql_dir / fname
            if not file_path.exists():
                logger.warning("SQL file not found: %s", file_path)
                continue
            logger.info("Executing DDL: %s", fname)
            content = file_path.read_text(encoding="utf-8")
            # Execute statement
            conn.execute(text(content))

    logger.info("Database schemas and views successfully initialized.")


def upsert_dim_geography(df: pd.DataFrame, engine: Engine) -> Dict[str, int]:
    """Idempotently populates warehouse.dim_geography and returns {state_name: geography_key}."""
    logger.debug("Upserting geography dimension...")
    insert_sql = text("""
        INSERT INTO warehouse.dim_geography (state_name, state_code, region, zone)
        VALUES (:state_name, :state_code, :region, :zone)
        ON CONFLICT (state_name) 
        DO UPDATE SET 
            region = EXCLUDED.region,
            zone = EXCLUDED.zone;
    """)

    # Always ensure Unknown fallback exists
    with engine.begin() as conn:
        conn.execute(
            insert_sql,
            {"state_name": "Unknown / Not Provided", "state_code": "UNK", "region": "Unknown", "zone": "Unknown"}
        )

        # Extract unique state records
        geo_df = df[["state", "region"]].dropna(subset=["state"]).drop_duplicates(subset=["state"])
        for _, row in geo_df.iterrows():
            conn.execute(
                insert_sql,
                {
                    "state_name": str(row["state"]),
                    "state_code": str(row["state"])[:3].upper(),
                    "region": str(row["region"]) if pd.notna(row["region"]) else "Other",
                    "zone": None,
                },
            )

        # Retrieve mapped surrogate keys
        res = conn.execute(text("SELECT state_name, geography_key FROM warehouse.dim_geography;"))
        mapping = {row[0]: row[1] for row in res.fetchall()}

    return mapping


def upsert_dim_occupation(df: pd.DataFrame, engine: Engine) -> Dict[str, int]:
    """Idempotently populates warehouse.dim_occupation and returns {occupation_title: occupation_key}."""
    logger.debug("Upserting occupation dimension...")
    insert_sql = text("""
        INSERT INTO warehouse.dim_occupation (occupation_title, occupation_category)
        VALUES (:occupation_title, :occupation_category)
        ON CONFLICT (occupation_title)
        DO NOTHING;
    """)

    with engine.begin() as conn:
        conn.execute(insert_sql, {"occupation_title": "Unknown / Not Provided", "occupation_category": "Unknown"})

        occ_df = df[["occupation"]].dropna().drop_duplicates()
        for _, row in occ_df.iterrows():
            title = str(row["occupation"]).strip()
            conn.execute(
                insert_sql,
                {"occupation_title": title, "occupation_category": "General"},
            )

        res = conn.execute(text("SELECT occupation_title, occupation_key FROM warehouse.dim_occupation;"))
        mapping = {row[0]: row[1] for row in res.fetchall()}

    return mapping


def upsert_dim_education(df: pd.DataFrame, engine: Engine) -> Dict[str, int]:
    """Idempotently populates warehouse.dim_education and returns {education_level: education_key}."""
    logger.debug("Upserting education dimension...")
    insert_sql = text("""
        INSERT INTO warehouse.dim_education (education_level, education_tier)
        VALUES (:education_level, :education_tier)
        ON CONFLICT (education_level)
        DO NOTHING;
    """)

    with engine.begin() as conn:
        conn.execute(insert_sql, {"education_level": "Unknown / Not Provided", "education_tier": "Unknown"})

        edu_df = df[["education"]].dropna().drop_duplicates()
        for _, row in edu_df.iterrows():
            level = str(row["education"]).strip()
            tier = "Higher Education" if any(w in level.lower() for w in ["bachelor", "master", "phd", "doctorate"]) else "Secondary"
            conn.execute(
                insert_sql,
                {"education_level": level, "education_tier": tier},
            )

        res = conn.execute(text("SELECT education_level, education_key FROM warehouse.dim_education;"))
        mapping = {row[0]: row[1] for row in res.fetchall()}

    return mapping


def upsert_dim_respondent(df: pd.DataFrame, engine: Engine, batch_id: str) -> Dict[str, int]:
    """Idempotently upserts warehouse.dim_respondent by natural respondent_id."""
    logger.debug("Upserting respondent dimension...")
    insert_sql = text("""
        INSERT INTO warehouse.dim_respondent (
            natural_respondent_id, gender, age, age_group, district, first_seen_batch_id, updated_at
        ) VALUES (
            :natural_respondent_id, :gender, :age, :age_group, :district, :first_seen_batch_id, CURRENT_TIMESTAMP
        )
        ON CONFLICT (natural_respondent_id)
        DO UPDATE SET
            gender = EXCLUDED.gender,
            age = EXCLUDED.age,
            age_group = EXCLUDED.age_group,
            district = EXCLUDED.district,
            updated_at = CURRENT_TIMESTAMP;
    """)

    resp_df = df[["respondent_id", "gender", "age", "age_group", "district"]].drop_duplicates(subset=["respondent_id"])
    with engine.begin() as conn:
        for _, row in resp_df.iterrows():
            conn.execute(
                insert_sql,
                {
                    "natural_respondent_id": str(row["respondent_id"]),
                    "gender": str(row["gender"]) if pd.notna(row["gender"]) else None,
                    "age": int(row["age"]) if pd.notna(row["age"]) else None,
                    "age_group": str(row["age_group"]) if pd.notna(row["age_group"]) else None,
                    "district": str(row["district"]) if pd.notna(row["district"]) else None,
                    "first_seen_batch_id": batch_id,
                },
            )

        res = conn.execute(text("SELECT natural_respondent_id, respondent_key FROM warehouse.dim_respondent;"))
        mapping = {row[0]: row[1] for row in res.fetchall()}

    return mapping


def upsert_fact_responses(
    df: pd.DataFrame,
    engine: Engine,
    geo_map: Dict[str, int],
    occ_map: Dict[str, int],
    edu_map: Dict[str, int],
    resp_map: Dict[str, int],
    batch_id: str,
    source_file: str,
) -> int:
    """Idempotently upserts clean survey facts into warehouse.fact_responses.

    Upsert logic: ON CONFLICT (natural_response_id) DO UPDATE
    Ensures running the pipeline multiple times never creates duplicate facts.
    """
    logger.info("Upserting %d fact responses into warehouse.fact_responses...", len(df))

    default_geo_key = geo_map.get("Unknown / Not Provided", next(iter(geo_map.values())) if geo_map else 1)
    default_occ_key = occ_map.get("Unknown / Not Provided", next(iter(occ_map.values())) if occ_map else 1)
    default_edu_key = edu_map.get("Unknown / Not Provided", next(iter(edu_map.values())) if edu_map else 1)
    default_resp_key = next(iter(resp_map.values())) if resp_map else 1

    upsert_sql = text("""
        INSERT INTO warehouse.fact_responses (
            natural_response_id, respondent_key, geography_key, occupation_key, education_key,
            batch_id, source_file, response_date, party_preference, monthly_income, income_bracket,
            rating_1_to_5, response_quality_score, is_outlier_income, is_outlier_age,
            free_text_comment, raw_record_hash, updated_at
        ) VALUES (
            :natural_response_id, :respondent_key, :geography_key, :occupation_key, :education_key,
            :batch_id, :source_file, :response_date, :party_preference, :monthly_income, :income_bracket,
            :rating_1_to_5, :response_quality_score, :is_outlier_income, :is_outlier_age,
            :free_text_comment, :raw_record_hash, CURRENT_TIMESTAMP
        )
        ON CONFLICT (natural_response_id)
        DO UPDATE SET
            respondent_key = EXCLUDED.respondent_key,
            geography_key = EXCLUDED.geography_key,
            occupation_key = EXCLUDED.occupation_key,
            education_key = EXCLUDED.education_key,
            batch_id = EXCLUDED.batch_id,
            response_date = EXCLUDED.response_date,
            party_preference = EXCLUDED.party_preference,
            monthly_income = EXCLUDED.monthly_income,
            income_bracket = EXCLUDED.income_bracket,
            rating_1_to_5 = EXCLUDED.rating_1_to_5,
            response_quality_score = EXCLUDED.response_quality_score,
            is_outlier_income = EXCLUDED.is_outlier_income,
            is_outlier_age = EXCLUDED.is_outlier_age,
            free_text_comment = EXCLUDED.free_text_comment,
            updated_at = CURRENT_TIMESTAMP;
    """)

    records_to_insert = []
    for _, row in df.iterrows():
        resp_id = str(row["respondent_id"])
        state = str(row["state"]) if pd.notna(row.get("state")) else ""
        occ = str(row["occupation"]) if pd.notna(row.get("occupation")) else ""
        edu = str(row["education"]) if pd.notna(row.get("education")) else ""

        records_to_insert.append({
            "natural_response_id": f"{resp_id}_{batch_id}",
            "respondent_key": resp_map.get(resp_id, default_resp_key),
            "geography_key": geo_map.get(state, default_geo_key),
            "occupation_key": occ_map.get(occ, default_occ_key),
            "education_key": edu_map.get(edu, default_edu_key),
            "batch_id": batch_id,
            "source_file": source_file,
            "response_date": row["response_date"] if pd.notna(row.get("response_date")) else "2024-01-01",
            "party_preference": str(row["party_preference"]) if pd.notna(row.get("party_preference")) else None,
            "monthly_income": float(row["monthly_income"]) if pd.notna(row.get("monthly_income")) else None,
            "income_bracket": str(row["income_bracket"]) if pd.notna(row.get("income_bracket")) else None,
            "rating_1_to_5": int(row["rating_1_to_5"]) if pd.notna(row.get("rating_1_to_5")) else None,
            "response_quality_score": float(row.get("response_quality_score", 1.0)),
            "is_outlier_income": bool(row.get("is_outlier_income", False)),
            "is_outlier_age": bool(row.get("is_outlier_age", False)),
            "free_text_comment": str(row["free_text_comment"]) if pd.notna(row.get("free_text_comment")) else None,
            "raw_record_hash": str(row["record_hash"]),
        })

    # Bulk execute in chunks
    chunk_size = 1000
    with engine.begin() as conn:
        for i in range(0, len(records_to_insert), chunk_size):
            chunk = records_to_insert[i : i + chunk_size]
            conn.execute(upsert_sql, chunk)

    logger.info("Successfully loaded %d facts into PostgreSQL.", len(records_to_insert))
    return len(records_to_insert)


def upsert_fact_choices(
    choices: List[Dict[str, Any]],
    engine: Engine,
    batch_id: Optional[str] = None,
) -> int:
    """Loads exploded multi-select choices into warehouse.fact_response_choices with high throughput."""
    if not choices:
        return 0

    logger.debug("Loading %d multi-select choices...", len(choices))

    # Pre-fetch response_id map for batch to achieve sub-second bulk insert
    with engine.connect() as conn:
        if batch_id:
            res = conn.execute(
                text("SELECT natural_response_id, response_id FROM warehouse.fact_responses WHERE batch_id = :b;"),
                {"b": batch_id},
            )
        else:
            res = conn.execute(text("SELECT natural_response_id, response_id FROM warehouse.fact_responses;"))
        id_map = {row[0]: row[1] for row in res.fetchall()}

    insert_sql = text("""
        INSERT INTO warehouse.fact_response_choices (response_id, choice_category, choice_value)
        VALUES (:response_id, :choice_category, :choice_value)
        ON CONFLICT (response_id, choice_category, choice_value) DO NOTHING;
    """)

    records = []
    for c in choices:
        nat_id = c["natural_response_id"]
        if nat_id in id_map:
            records.append({
                "response_id": id_map[nat_id],
                "choice_category": c["choice_category"],
                "choice_value": c["choice_value"],
            })

    chunk_size = 5000
    with engine.begin() as conn:
        for i in range(0, len(records), chunk_size):
            chunk = records[i : i + chunk_size]
            conn.execute(insert_sql, chunk)

    logger.info("Successfully loaded %d multi-select choices into bridge table.", len(records))
    return len(records)


def record_audit_pipeline_run(engine: Engine, metrics: Dict[str, Any]) -> None:
    """Logs or updates pipeline execution metrics into audit.pipeline_runs."""
    sql = text("""
        INSERT INTO audit.pipeline_runs (
            batch_id, source_name, source_file, status, records_extracted, records_loaded_mongo,
            records_cleaned, records_rejected, records_loaded_pg, duplicates_dropped,
            null_pct_before, null_pct_after, execution_time_seconds, error_message,
            started_at, completed_at
        ) VALUES (
            :batch_id, :source_name, :source_file, :status, :records_extracted, :records_loaded_mongo,
            :records_cleaned, :records_rejected, :records_loaded_pg, :duplicates_dropped,
            :null_pct_before, :null_pct_after, :execution_time_seconds, :error_message,
            :started_at, :completed_at
        )
        ON CONFLICT (batch_id)
        DO UPDATE SET
            status = EXCLUDED.status,
            records_extracted = EXCLUDED.records_extracted,
            records_loaded_mongo = EXCLUDED.records_loaded_mongo,
            records_cleaned = EXCLUDED.records_cleaned,
            records_rejected = EXCLUDED.records_rejected,
            records_loaded_pg = EXCLUDED.records_loaded_pg,
            duplicates_dropped = EXCLUDED.duplicates_dropped,
            null_pct_before = EXCLUDED.null_pct_before,
            null_pct_after = EXCLUDED.null_pct_after,
            execution_time_seconds = EXCLUDED.execution_time_seconds,
            error_message = EXCLUDED.error_message,
            completed_at = EXCLUDED.completed_at;
    """)

    with engine.begin() as conn:
        conn.execute(sql, metrics)


def record_rejected_rows_pg(engine: Engine, rejected_rows: List[Dict[str, Any]]) -> int:
    """Inserts rejected records into audit.rejected_rows."""
    if not rejected_rows:
        return 0

    import json

    sql = text("""
        INSERT INTO audit.rejected_rows (
            batch_id, natural_respondent_id, rule_failed, severity, failed_column,
            invalid_value, error_reason, raw_payload
        ) VALUES (
            :batch_id, :natural_respondent_id, :rule_failed, :severity, :failed_column,
            :invalid_value, :error_reason, CAST(:raw_payload AS jsonb)
        );
    """)

    formatted_rows = []
    for r in rejected_rows:
        payload = r.get("raw_payload")
        if isinstance(payload, dict):
            # Clean np.nan / float('nan') into None so it serializes to valid JSON null
            cleaned_dict = {k: (None if pd.isna(v) else v) for k, v in payload.items()}
            payload_str = json.dumps(cleaned_dict, default=str)
        else:
            payload_str = str(payload) if payload else "{}"

        formatted_rows.append({
            "batch_id": r["batch_id"],
            "natural_respondent_id": r.get("natural_respondent_id"),
            "rule_failed": r["rule_failed"],
            "severity": r.get("severity", "ERROR"),
            "failed_column": r.get("failed_column"),
            "invalid_value": str(r.get("invalid_value", "")),
            "error_reason": r["error_reason"],
            "raw_payload": payload_str,
        })

    with engine.begin() as conn:
        conn.execute(sql, formatted_rows)

    return len(formatted_rows)


def record_data_quality_results_pg(engine: Engine, dq_results: List[Dict[str, Any]]) -> int:
    """Inserts data quality check results into audit.data_quality_results."""
    if not dq_results:
        return 0

    sql = text("""
        INSERT INTO audit.data_quality_results (
            batch_id, check_name, target_table, target_column, severity,
            passed, expected_condition, actual_value, failed_records_count
        ) VALUES (
            :batch_id, :check_name, :target_table, :target_column, :severity,
            :passed, :expected_condition, :actual_value, :failed_records_count
        );
    """)

    with engine.begin() as conn:
        conn.execute(sql, dq_results)

    return len(dq_results)
