"""Categorical standardization and fuzzy string matching using RapidFuzz."""

from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Tuple
import pandas as pd
from rapidfuzz import process, fuzz

from survey_pipeline.config import settings
from survey_pipeline.logging_config import get_logger

logger = get_logger(__name__)


class Standardizer:
    """Enterprise-grade fuzzy categorical standardizer with confidence thresholds."""

    def __init__(self, ref_dir: Optional[Path] = None, threshold: float = 85.0):
        self.ref_dir = ref_dir or settings.reference_data_dir
        self.threshold = threshold
        self._load_reference_tables()

    def _load_reference_tables(self) -> None:
        """Loads canonical mapping dictionaries from CSVs."""
        logger.debug("Loading reference mappings from %s...", self.ref_dir)

        # 1. State Mapping: pattern -> (canonical_name, state_code, region, zone)
        state_file = self.ref_dir / "state_mapping.csv"
        self.state_lookup: Dict[str, Tuple[str, str, str, str]] = {}
        if state_file.exists():
            df_state = pd.read_csv(state_file)
            for _, r in df_state.iterrows():
                key = str(r["raw_pattern"]).strip().lower()
                self.state_lookup[key] = (
                    str(r["canonical_name"]),
                    str(r["state_code"]),
                    str(r["region"]),
                    str(r["zone"]),
                )
        self.state_patterns = list(self.state_lookup.keys())

        # 2. Party Mapping: pattern -> (canonical_name, party_code)
        party_file = self.ref_dir / "party_mapping.csv"
        self.party_lookup: Dict[str, Tuple[str, str]] = {}
        if party_file.exists():
            df_party = pd.read_csv(party_file)
            for _, r in df_party.iterrows():
                key = str(r["raw_pattern"]).strip().lower()
                self.party_lookup[key] = (str(r["canonical_name"]), str(r["party_code"]))
        self.party_patterns = list(self.party_lookup.keys())

        # 3. Education Mapping: pattern -> (canonical_name, education_tier)
        edu_file = self.ref_dir / "education_mapping.csv"
        self.edu_lookup: Dict[str, Tuple[str, str]] = {}
        if edu_file.exists():
            df_edu = pd.read_csv(edu_file)
            for _, r in df_edu.iterrows():
                key = str(r["raw_pattern"]).strip().lower()
                self.edu_lookup[key] = (str(r["canonical_name"]), str(r["education_tier"]))
        self.edu_patterns = list(self.edu_lookup.keys())

        # 4. Occupation Mapping: pattern -> (canonical_name, occupation_category)
        occ_file = self.ref_dir / "occupation_mapping.csv"
        self.occ_lookup: Dict[str, Tuple[str, str]] = {}
        if occ_file.exists():
            df_occ = pd.read_csv(occ_file)
            for _, r in df_occ.iterrows():
                key = str(r["raw_pattern"]).strip().lower()
                self.occ_lookup[key] = (str(r["canonical_name"]), str(r["occupation_category"]))
        self.occ_patterns = list(self.occ_lookup.keys())

    @lru_cache(maxsize=4096)
    def match_state(self, raw_val: Optional[str]) -> Tuple[str, str, str, str]:
        """Maps raw state to (canonical_name, state_code, region, zone)."""
        if not raw_val or pd.isna(raw_val):
            return ("Unknown / Not Provided", "UNK", "Other", "Unknown")

        cleaned = str(raw_val).strip().lower().replace(".", "").replace("-", " ")
        if cleaned in self.state_lookup:
            return self.state_lookup[cleaned]

        # Fuzzy match with RapidFuzz
        if self.state_patterns:
            match = process.extractOne(cleaned, self.state_patterns, scorer=fuzz.token_sort_ratio)
            if match and match[1] >= self.threshold:
                return self.state_lookup[match[0]]

        return (str(raw_val).title().strip(), "OTH", "Other", "Unknown")

    @lru_cache(maxsize=4096)
    def match_party(self, raw_val: Optional[str]) -> Tuple[str, str]:
        """Maps raw party string to (canonical_name, party_code)."""
        if not raw_val or pd.isna(raw_val):
            return ("None / Undecided", "UNDECIDED")

        cleaned = str(raw_val).strip().lower().replace(".", "")
        if cleaned in self.party_lookup:
            return self.party_lookup[cleaned]

        if self.party_patterns:
            match = process.extractOne(cleaned, self.party_patterns, scorer=fuzz.token_sort_ratio)
            if match and match[1] >= self.threshold:
                return self.party_lookup[match[0]]

        return (str(raw_val).strip(), "OTHER")

    @lru_cache(maxsize=4096)
    def match_education(self, raw_val: Optional[str]) -> Tuple[str, str]:
        """Maps raw education to (canonical_name, education_tier)."""
        if not raw_val or pd.isna(raw_val):
            return ("Unknown / Not Specified", "Unknown")

        cleaned = str(raw_val).strip().lower().replace(".", "")
        if cleaned in self.edu_lookup:
            return self.edu_lookup[cleaned]

        if self.edu_patterns:
            match = process.extractOne(cleaned, self.edu_patterns, scorer=fuzz.token_sort_ratio)
            if match and match[1] >= self.threshold:
                return self.edu_lookup[match[0]]

        return (str(raw_val).title().strip(), "Secondary")

    @lru_cache(maxsize=4096)
    def match_occupation(self, raw_val: Optional[str]) -> Tuple[str, str]:
        """Maps raw occupation to (canonical_name, occupation_category)."""
        if not raw_val or pd.isna(raw_val):
            return ("Unknown / Not Provided", "Other")

        cleaned = str(raw_val).strip().lower().replace(".", "")
        if cleaned in self.occ_lookup:
            return self.occ_lookup[cleaned]

        if self.occ_patterns:
            match = process.extractOne(cleaned, self.occ_patterns, scorer=fuzz.token_sort_ratio)
            if match and match[1] >= self.threshold:
                return self.occ_lookup[match[0]]

        return (str(raw_val).title().strip(), "General")

    @staticmethod
    def standardize_gender(raw_val: Optional[str]) -> str:
        """Maps raw gender string to canonical domain categories."""
        if not raw_val or pd.isna(raw_val):
            return "Not Specified"

        val = str(raw_val).strip().lower()
        if val in ("m", "male", "man", "he"):
            return "Male"
        elif val in ("f", "female", "woman", "she"):
            return "Female"
        elif any(w in val for w in ["non-binary", "nonbinary", "queer", "other"]):
            return "Non-Binary"
        elif any(w in val for w in ["prefer not", "skip", "none"]):
            return "Prefer not to say"

        return "Not Specified"


# Default singleton standardizer
default_standardizer = Standardizer()
