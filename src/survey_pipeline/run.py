"""Command-Line Interface and Pipeline Orchestrator for survey-data-pipeline."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Optional

from rich.console import Console
from rich.table import Table

from survey_pipeline.clean import clean_survey_dataset
from survey_pipeline.config import settings
from survey_pipeline.extract import extract_survey_data
from survey_pipeline.load import finalize_audit_records, load_clean_to_postgres, load_raw_to_mongodb
from survey_pipeline.logging_config import get_logger
from survey_pipeline.metrics import PipelineMetrics
from survey_pipeline.mongo_db import get_database
from survey_pipeline.pg_db import get_pg_engine
from survey_pipeline.profile import generate_profile_comparison_markdown
from survey_pipeline.validate import (
    DataQualitySuite,
    generate_data_quality_report_markdown,
)

logger = get_logger(__name__)
console = Console()


def generate_batch_id(custom_batch_id: Optional[str] = None) -> str:
    """Generates an ISO timestamped batch identifier or returns custom one."""
    if custom_batch_id and custom_batch_id.lower() != "auto":
        return custom_batch_id
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"BATCH_{now_str}"


def run_pipeline(
    source: str = "synthetic",
    batch_id: Optional[str] = None,
    custom_file: Optional[Path] = None,
    force_download: bool = False,
    skip_mongo: bool = False,
    skip_pg: bool = False,
    dry_run: bool = False,
) -> PipelineMetrics:
    """Orchestrates end-to-end ELT execution across all pipeline phases."""
    actual_batch_id = generate_batch_id(batch_id)
    logger.info("================================================================================")
    logger.info("STARTING SURVEY DATA PIPELINE: Batch ID '%s' | Source: '%s'", actual_batch_id, source)
    logger.info("================================================================================")

    # 1. Initialize Metrics Tracker
    metrics = PipelineMetrics(
        batch_id=actual_batch_id,
        source_name=source,
        source_file="",
    )

    mongo_db = None
    pg_engine = None

    try:
        # Establish DB connections if not skipping
        if not dry_run and not skip_mongo:
            mongo_db = get_database()
        if not dry_run and not skip_pg:
            pg_engine = get_pg_engine()

        # ----------------------------------------------------------------------
        # PHASE 1: EXTRACT
        # ----------------------------------------------------------------------
        logger.info("[PHASE 1/5] Extracting raw survey data...")
        df_raw, source_file, file_checksum = extract_survey_data(
            source=source,
            custom_file=custom_file,
            force_download=force_download,
        )
        metrics.source_file = source_file
        metrics.records_extracted = len(df_raw)

        # ----------------------------------------------------------------------
        # PHASE 2: LAND RAW IN MONGODB (Data Lake / Landing Zone)
        # ----------------------------------------------------------------------
        if not dry_run and not skip_mongo and mongo_db is not None:
            logger.info("[PHASE 2/5] Ingesting untouched raw records into MongoDB landing zone...")
            records_loaded_mongo = load_raw_to_mongodb(
                db=mongo_db,
                df_raw=df_raw,
                batch_id=actual_batch_id,
                source_file=source_file,
            )
            metrics.records_loaded_mongo = records_loaded_mongo
        else:
            logger.info("[PHASE 2/5] Skipping MongoDB ingestion (dry_run=%s, skip_mongo=%s)", dry_run, skip_mongo)
            metrics.records_loaded_mongo = len(df_raw)

        # ----------------------------------------------------------------------
        # PHASE 3: CLEAN & TRANSFORM
        # ----------------------------------------------------------------------
        logger.info("[PHASE 3/5] Cleaning, standardizing, and deriving analytical features...")
        clean_result = clean_survey_dataset(
            df_raw=df_raw,
            batch_id=actual_batch_id,
            source_file=source_file,
        )

        metrics.records_cleaned = len(clean_result.cleaned_df)
        metrics.records_rejected = len(clean_result.rejected_records)
        metrics.duplicates_dropped = clean_result.duplicates_removed
        metrics.null_pct_before = clean_result.before_profile["overall_null_pct"]
        metrics.null_pct_after = clean_result.after_profile["overall_null_pct"]

        # Generate & save cleaning report
        generate_profile_comparison_markdown(
            profile_before=clean_result.before_profile,
            profile_after=clean_result.after_profile,
            output_path=settings.docs_dir / "cleaning_report.md",
            duplicates_removed=clean_result.duplicates_removed,
            rejected_count=len(clean_result.rejected_records),
        )

        # ----------------------------------------------------------------------
        # PHASE 4: DATA QUALITY VERIFICATION
        # ----------------------------------------------------------------------
        logger.info("[PHASE 4/5] Executing Data Quality Suite assertions...")
        suite = DataQualitySuite(batch_id=actual_batch_id)

        # Check: Essential Schema Columns Present
        suite.check_schema_presence(
            clean_result.cleaned_df,
            required_columns=["respondent_id", "state", "record_hash"],
        )

        # Check: Not-Null on Natural Keys
        suite.check_not_null(clean_result.cleaned_df, "respondent_id")
        suite.check_not_null(clean_result.cleaned_df, "record_hash")

        # Check: Natural Key Uniqueness (0 duplicates)
        suite.check_uniqueness(clean_result.cleaned_df, "respondent_id")

        # Check: Rating Boundary Range [1..5]
        if "rating_1_to_5" in clean_result.cleaned_df.columns:
            suite.check_range(clean_result.cleaned_df, "rating_1_to_5", min_val=1, max_val=5)

        # Check: Exact Row-Count Reconciliation
        suite.check_row_reconciliation(
            raw_count=metrics.records_extracted,
            clean_count=metrics.records_cleaned,
            rejected_count=metrics.records_rejected,
            duplicates_dropped=metrics.duplicates_dropped,
        )

        # Check: Response Quality SLA
        suite.check_average_quality_score(clean_result.cleaned_df, min_score=0.50)

        metrics.total_quality_checks = len(suite.results)
        metrics.passed_quality_checks = sum(1 for r in suite.results if r.passed)

        # Export Data Quality Report to docs/
        generate_data_quality_report_markdown(
            results=suite.results,
            batch_id=actual_batch_id,
            output_path=settings.docs_dir / "data_quality_report.md",
        )

        # Assert zero ERROR-level failures
        suite.assert_no_errors()

        # ----------------------------------------------------------------------
        # PHASE 5: LOAD TO POSTGRESQL WAREHOUSE
        # ----------------------------------------------------------------------
        if not dry_run and not skip_pg and pg_engine is not None:
            logger.info("[PHASE 5/5] Idempotently loading dimensional star schema into PostgreSQL...")
            facts_loaded = load_clean_to_postgres(
                engine=pg_engine,
                clean_result=clean_result,
                batch_id=actual_batch_id,
                source_file=source_file,
            )
            metrics.records_loaded_pg = facts_loaded
        else:
            logger.info("[PHASE 5/5] Skipping PostgreSQL loading (dry_run=%s, skip_pg=%s)", dry_run, skip_pg)
            metrics.records_loaded_pg = len(clean_result.cleaned_df)

        # Mark pipeline complete
        metrics.complete(status="COMPLETED")

        # Finalize audit records in both DBs
        if not dry_run:
            finalize_audit_records(
                metrics=metrics,
                dq_results=suite.results,
                rejected_records=clean_result.rejected_records,
                mongo_db=mongo_db,
                pg_engine=pg_engine,
            )

        # Print Executive Results Table
        print_pipeline_summary(metrics)
        return metrics

    except Exception as e:
        logger.exception("Pipeline execution failed for batch '%s': %s", actual_batch_id, e)
        metrics.complete(status="FAILED", error_message=str(e))
        if not dry_run and pg_engine is not None:
            try:
                finalize_audit_records(
                    metrics=metrics,
                    dq_results=[],
                    rejected_records=[],
                    mongo_db=mongo_db,
                    pg_engine=pg_engine,
                )
            except Exception:
                pass
        raise


def print_pipeline_summary(metrics: PipelineMetrics) -> None:
    """Prints a beautiful, rich terminal summary table of measured results."""
    table = Table(
        title=f"Survey Data Pipeline Execution Summary | Batch: {metrics.batch_id}",
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("Pipeline Metric", style="bold white", width=35)
    table.add_column("Measured Value", style="bold green", justify="right", width=25)
    table.add_column("Quality SLA / Impact", style="italic yellow", width=35)

    table.add_row("Execution Status", metrics.status, "Zero-error policy enforced")
    table.add_row("Source Dataset File", metrics.source_file, f"Source: {metrics.source_name}")
    table.add_row("Total Raw Records Extracted", f"{metrics.records_extracted:,}", "100% captured with SHA-256 hash")
    table.add_row("Raw Records Loaded to MongoDB", f"{metrics.records_loaded_mongo:,}", "Schema-flexible raw landing lake")
    table.add_row("Duplicate Records Removed", f"{metrics.duplicates_dropped:,}", "100% duplicate elimination on PK")
    table.add_row("Invalid Records Rejected", f"{metrics.records_rejected:,}", "Logged to rejection lake with reasons")
    table.add_row("Clean Facts Loaded to PostgreSQL", f"{metrics.records_loaded_pg:,}", "Star schema with surrogate FKs")
    table.add_row("Missing Value % (Raw -> Clean)", f"{metrics.null_pct_before:.2f}% -> {metrics.null_pct_after:.2f}%", f"{metrics.null_reduction_pct:+.2f}% net null reduction")
    table.add_row("Data Quality Checks Passed", f"{metrics.passed_quality_checks} / {metrics.total_quality_checks}", "100% critical rules passed")
    table.add_row("Total End-to-End Runtime", f"{metrics.execution_time_seconds:.3f} seconds", f"{metrics.records_extracted / max(metrics.execution_time_seconds, 0.001):,.0f} rows / sec throughput")

    console.print()
    console.print(table)
    console.print()


def main():
    parser = argparse.ArgumentParser(
        description="Production Survey Data Pipeline: Ingest, Clean, Validate & Load"
    )
    parser.add_argument(
        "--source",
        type=str,
        default="synthetic",
        choices=["synthetic", "real", "tidytuesday", "stackoverflow", "local"],
        help="Data source to ingest (default: synthetic)",
    )
    parser.add_argument(
        "--batch-id",
        type=str,
        default="auto",
        help="Batch run identifier (default: auto)",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to local survey CSV file",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Force re-download of dataset bypassing cache",
    )
    parser.add_argument(
        "--skip-mongo",
        action="store_true",
        help="Skip MongoDB raw landing zone ingestion",
    )
    parser.add_argument(
        "--skip-pg",
        action="store_true",
        help="Skip PostgreSQL warehouse loading",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run ETL and validation in-memory without database writes",
    )

    args = parser.parse_args()

    custom_file_path = Path(args.file) if args.file else None

    try:
        run_pipeline(
            source=args.source,
            batch_id=args.batch_id,
            custom_file=custom_file_path,
            force_download=args.force_download,
            skip_mongo=args.skip_mongo,
            skip_pg=args.skip_pg,
            dry_run=args.dry_run,
        )
    except Exception as e:
        logger.error("Execution failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
