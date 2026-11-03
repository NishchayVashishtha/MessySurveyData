"""Data extraction module with programmatic downloading, caching, and cryptographic hashing."""

import hashlib
import json
from pathlib import Path
from typing import Dict, Optional, Tuple
import pandas as pd
import requests

from survey_pipeline.config import settings
from survey_pipeline.logging_config import get_logger

logger = get_logger(__name__)

# Verified open dataset URLs with open licensing (Attribution / Public Domain)
PRIMARY_REAL_DATASET_URL = (
    "https://raw.githubusercontent.com/rfordatascience/tidytuesday/master/data/2021/2021-05-18/survey.csv"
)


def compute_file_sha256(file_path: Path) -> str:
    """Calculates SHA-256 hash of a file for data lineage and cache validation."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_record_hash(row_dict: Dict) -> str:
    """Computes a deterministic SHA-256 fingerprint of a single raw record.

    Used as natural key in MongoDB landing zone to guarantee idempotent ingestion.
    """
    # Sort keys and serialize to JSON for deterministic representation
    serialized = json.dumps(row_dict, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def download_dataset(
    url: str,
    target_path: Path,
    force: bool = False,
    timeout: int = 30,
) -> Path:
    """Programmatically downloads a dataset with local caching.

    Args:
        url: Direct download URL.
        target_path: Destination local path in data/raw/.
        force: If True, re-downloads even if target_path exists.
        timeout: HTTP request timeout in seconds.

    Returns:
        Path to downloaded file.
    """
    if target_path.exists() and not force:
        logger.info("Dataset found in cache at %s. Skipping download.", target_path)
        return target_path

    target_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading dataset from %s to %s...", url, target_path)

    response = requests.get(url, stream=True, timeout=timeout)
    response.raise_for_status()

    with open(target_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    checksum = compute_file_sha256(target_path)
    logger.info(
        "Successfully downloaded dataset (%d bytes, SHA-256: %s...)",
        target_path.stat().st_size,
        checksum[:12],
    )
    return target_path


def extract_survey_data(
    source: str = "synthetic",
    custom_file: Optional[Path] = None,
    force_download: bool = False,
) -> Tuple[pd.DataFrame, str, str]:
    """Main extraction entrypoint. Loads survey data and attaches record hashes.

    Args:
        source: 'synthetic', 'real', 'tidytuesday', or 'stackoverflow'.
        custom_file: Path to local file if provided.
        force_download: If True, bypasses local download cache.

    Returns:
        Tuple of (DataFrame with 'record_hash', source_file_name, file_checksum).
    """
    source_lower = source.lower()

    if custom_file and Path(custom_file).exists():
        file_path = Path(custom_file)
        logger.info("Extracting survey responses from custom file: %s", file_path)
    elif source_lower in ("synthetic", "sample", "local"):
        file_path = settings.sample_data_dir / "survey_sample_dirty.csv"
        if not file_path.exists():
            logger.info("Sample synthetic dataset not found. Generating fresh copy...")
            from scripts.generate_dirty_survey import generate_dirty_survey
            df_gen = generate_dirty_survey(num_rows=10000)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            df_gen.to_csv(file_path, index=False, encoding="utf-8")
    elif source_lower in ("real", "tidytuesday", "open_survey"):
        file_path = settings.raw_data_dir / "tidytuesday_survey_raw.csv"
        download_dataset(PRIMARY_REAL_DATASET_URL, file_path, force=force_download)
    elif source_lower == "stackoverflow":
        # Check if user already placed a Stack Overflow survey file in data/raw
        candidates = list(settings.raw_data_dir.glob("*stackoverflow*.csv")) + list(
            settings.raw_data_dir.glob("*survey_results_public*.csv")
        )
        if candidates:
            file_path = candidates[0]
            logger.info("Found Stack Overflow survey file: %s", file_path)
        else:
            logger.warning(
                "Stack Overflow CSV not found in data/raw/. Using verified real open survey dataset."
            )
            file_path = settings.raw_data_dir / "tidytuesday_survey_raw.csv"
            download_dataset(PRIMARY_REAL_DATASET_URL, file_path, force=force_download)
    else:
        raise ValueError(f"Unsupported survey data source: '{source}'. Choose 'synthetic' or 'real'.")

    file_checksum = compute_file_sha256(file_path)
    logger.info("Reading CSV from %s (Checksum: %s...)", file_path.name, file_checksum[:12])

    # Read raw CSV preserving all original string values verbatim
    df_raw = pd.read_csv(file_path, dtype=str, keep_default_na=False)

    # Compute deterministic record hash for each row
    logger.debug("Generating cryptographic record hashes for %d rows...", len(df_raw))
    hashes = [compute_record_hash(row) for row in df_raw.to_dict(orient="records")]
    df_raw["record_hash"] = hashes

    logger.info("Extraction complete: %d raw records loaded from %s.", len(df_raw), file_path.name)
    return df_raw, file_path.name, file_checksum
