"""Pipeline performance and data metrics tracking engine."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any, Dict, Optional

from survey_pipeline.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PipelineMetrics:
    """Stores measured pipeline performance and data processing metrics."""

    batch_id: str
    source_name: str
    source_file: str
    status: str = "STARTED"
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    execution_time_seconds: float = 0.0

    # Data volume metrics
    records_extracted: int = 0
    records_loaded_mongo: int = 0
    records_cleaned: int = 0
    records_rejected: int = 0
    records_loaded_pg: int = 0
    duplicates_dropped: int = 0

    # Quality and profiling metrics
    null_pct_before: float = 0.0
    null_pct_after: float = 0.0
    total_quality_checks: int = 0
    passed_quality_checks: int = 0
    error_message: Optional[str] = None

    def complete(self, status: str = "COMPLETED", error_message: Optional[str] = None) -> None:
        """Marks the execution as finished and computes final runtime."""
        self.end_time = time.time()
        self.execution_time_seconds = round(self.end_time - self.start_time, 3)
        self.status = status
        self.error_message = error_message
        logger.info(
            "Pipeline batch '%s' finished in %.3f seconds with status '%s'.",
            self.batch_id,
            self.execution_time_seconds,
            self.status,
        )

    @property
    def null_reduction_pct(self) -> float:
        return round(self.null_pct_before - self.null_pct_after, 2)

    def to_dict(self) -> Dict[str, Any]:
        """Converts metrics to a serializable dictionary for audit tables."""
        return {
            "batch_id": self.batch_id,
            "source_name": self.source_name,
            "source_file": self.source_file,
            "status": self.status,
            "records_extracted": self.records_extracted,
            "records_loaded_mongo": self.records_loaded_mongo,
            "records_cleaned": self.records_cleaned,
            "records_rejected": self.records_rejected,
            "records_loaded_pg": self.records_loaded_pg,
            "duplicates_dropped": self.duplicates_dropped,
            "null_pct_before": self.null_pct_before,
            "null_pct_after": self.null_pct_after,
            "execution_time_seconds": self.execution_time_seconds,
            "error_message": self.error_message,
            "started_at": datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat(),
            "completed_at": datetime.fromtimestamp(self.end_time, tz=timezone.utc).isoformat() if self.end_time else None,
        }

    def save_json(self, output_path: Path) -> None:
        """Saves metrics dictionary to a JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
