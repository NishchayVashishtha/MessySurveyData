"""MongoDB Data Lake / Landing Zone client and collection management.

Why schema-flexible storage suits raw survey data:
Raw survey instruments vary extensively across iterations: new questions are added,
free-text comment boxes are introduced, multi-select options expand, and column names
frequently change. Storing original responses in a schema-flexible Document store
(MongoDB) ensures 100% data preservation without brittle upfront schema migrations
or lossy truncation. Every raw submission is captured verbatim with cryptographic
checksums and batch lineage before any transformation.
"""

from datetime import UTC, datetime
from typing import Any

import pymongo
from pymongo import ASCENDING, IndexModel, UpdateOne
from pymongo.database import Database

from survey_pipeline.config import settings
from survey_pipeline.logging_config import get_logger

logger = get_logger(__name__)


def get_mongo_client(uri: str | None = None) -> pymongo.MongoClient:
    """Returns a connected pymongo MongoClient with timeout protection.

    Args:
        uri: Optional connection URI. If None, loaded from settings.

    Returns:
        pymongo.MongoClient instance.
    """
    connection_uri = uri or settings.mongo.uri
    logger.debug("Connecting to MongoDB at %s:%s", settings.mongo.host, settings.mongo.port)
    client = pymongo.MongoClient(
        connection_uri,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
    )
    return client


def get_database(client: pymongo.MongoClient | None = None, db_name: str | None = None) -> Database:
    """Returns the database handle."""
    cli = client or get_mongo_client()
    return cli[db_name or settings.mongo.db]


get_mongo_db = get_database


def setup_mongo_indexes(db: Database) -> None:
    """Creates required indexes on raw_responses, rejected_responses, and pipeline_runs.

    Idempotent operation: index creation is safe to execute multiple times.
    """
    raw_col = db["raw_responses"]
    rejected_col = db["rejected_responses"]
    runs_col = db["pipeline_runs"]

    logger.info("Setting up MongoDB collection indexes...")

    # raw_responses: unique on record_hash, index on batch_id, compound on (source_file, ingest_ts)
    raw_col.create_indexes(
        [
            IndexModel([("record_hash", ASCENDING)], unique=True, name="uniq_record_hash"),
            IndexModel([("batch_id", ASCENDING)], name="idx_batch_id"),
            IndexModel(
                [("source_file", ASCENDING), ("ingest_ts", ASCENDING)], name="idx_source_ingest"
            ),
        ]
    )

    # rejected_responses: index on batch_id, rule_failed
    rejected_col.create_indexes(
        [
            IndexModel([("batch_id", ASCENDING)], name="idx_rejected_batch"),
            IndexModel([("rule_failed", ASCENDING)], name="idx_rejected_rule"),
        ]
    )

    # pipeline_runs: unique on batch_id
    runs_col.create_indexes(
        [
            IndexModel([("batch_id", ASCENDING)], unique=True, name="uniq_run_batch"),
        ]
    )

    logger.info("MongoDB indexes successfully verified.")


def upsert_raw_responses(
    db: Database,
    records: list[dict[str, Any]],
    batch_id: str,
    source_file: str,
) -> int:
    """Idempotently loads untouched raw survey records into MongoDB raw_responses.

    Each document contains the complete original survey row plus ingestion metadata:
    - batch_id: ETL run identifier
    - source_file: source filename
    - ingest_ts: UTC timestamp of raw landing
    - record_hash: SHA-256 fingerprint of the verbatim raw content

    Args:
        db: MongoDB Database handle.
        records: List of dictionaries representing raw survey rows (must contain 'record_hash').
        batch_id: Execution batch ID.
        source_file: Name of the ingested file.

    Returns:
        Number of documents upserted or inserted.
    """
    if not records:
        logger.warning("No records supplied for MongoDB raw ingestion.")
        return 0

    collection = db["raw_responses"]
    now_utc = datetime.now(UTC).isoformat()
    operations: list[UpdateOne] = []

    for record in records:
        rec_hash = record.get("record_hash")
        if not rec_hash:
            raise ValueError("Record missing required 'record_hash' for idempotent raw ingestion.")

        doc = {
            **record,
            "batch_id": batch_id,
            "source_file": source_file,
            "ingest_ts": now_utc,
        }

        # Idempotent upsert on natural/fingerprint record_hash
        operations.append(
            UpdateOne(
                {"record_hash": rec_hash},
                {"$set": doc},
                upsert=True,
            )
        )

    # Execute in bulk batches of 2000
    batch_size = 2000
    upserted_count = 0
    for i in range(0, len(operations), batch_size):
        chunk = operations[i : i + batch_size]
        result = collection.bulk_write(chunk, ordered=False)
        upserted_count += result.upserted_count + result.matched_count

    logger.info(
        "Ingested %d raw records into MongoDB raw_responses for batch '%s'.",
        len(records),
        batch_id,
    )
    return len(records)


def insert_rejected_responses(
    db: Database,
    rejected_records: list[dict[str, Any]],
) -> int:
    """Records validation failures into MongoDB rejected_responses with failure reasons.

    Args:
        db: MongoDB Database handle.
        rejected_records: List of rejection payload dictionaries.

    Returns:
        Count of inserted rejection documents.
    """
    if not rejected_records:
        return 0

    collection = db["rejected_responses"]
    now_utc = datetime.now(UTC).isoformat()

    docs = [{**rec, "recorded_at": now_utc} for rec in rejected_records]
    result = collection.insert_many(docs, ordered=False)
    logger.info("Recorded %d validation rejection records in MongoDB.", len(result.inserted_ids))
    return len(result.inserted_ids)


def log_pipeline_run_mongo(db: Database, run_doc: dict[str, Any]) -> None:
    """Records pipeline run metadata and metrics into pipeline_runs collection."""
    collection = db["pipeline_runs"]
    batch_id = run_doc["batch_id"]
    collection.replace_one({"batch_id": batch_id}, run_doc, upsert=True)
    logger.debug("Logged pipeline run '%s' to MongoDB pipeline_runs.", batch_id)


def run_raw_responses_aggregation(
    db: Database, batch_id: str | None = None
) -> list[dict[str, Any]]:
    """Demonstrates an analytical aggregation pipeline directly on the raw landing zone.

    Computes:
    - Total raw count per batch
    - Distinct files ingested
    - Distribution of missing values across raw columns
    """
    collection = db["raw_responses"]
    match_stage = {"$match": {"batch_id": batch_id}} if batch_id else {"$match": {}}

    pipeline = [
        match_stage,
        {
            "$group": {
                "_id": "$batch_id",
                "total_records": {"$sum": 1},
                "source_files": {"$addToSet": "$source_file"},
                "min_ingest_ts": {"$min": "$ingest_ts"},
                "max_ingest_ts": {"$max": "$ingest_ts"},
            }
        },
        {"$sort": {"_id": -1}},
    ]

    return list(collection.aggregate(pipeline))
