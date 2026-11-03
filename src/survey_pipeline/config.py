"""Configuration management using Pydantic Settings and environment variables."""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ensure .env is loaded if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class MongoSettings(BaseSettings):
    """MongoDB connection configuration."""

    model_config = SettingsConfigDict(env_prefix="MONGO_", extra="ignore")

    host: str = Field(default="localhost")
    port: int = Field(default=27017)
    user: Optional[str] = Field(default="survey_admin")
    password: Optional[str] = Field(default="survey_secret_pass")
    db: str = Field(default="survey_raw_lake")
    auth_source: str = Field(default="admin")

    @property
    def resolved_host(self) -> str:
        """Resolves host, falling back to WSL IP if localhost authentication proxy is blocked."""
        h = self.host
        if h in ("localhost", "127.0.0.1") and os.name == "nt":
            # Check if WSL host is accessible
            wsl_ip = os.environ.get("WSL_HOST_IP")
            if wsl_ip:
                return wsl_ip
        return h

    @property
    def uri(self) -> str:
        """Construct standard MongoDB connection URI."""
        h = self.resolved_host
        if self.user and self.password:
            return f"mongodb://{self.user}:{self.password}@{h}:{self.port}/{self.db}?authSource={self.auth_source}&authMechanism=SCRAM-SHA-256"
        return f"mongodb://{h}:{self.port}/{self.db}"


class PostgresSettings(BaseSettings):
    """PostgreSQL data warehouse connection configuration."""

    model_config = SettingsConfigDict(env_prefix="POSTGRES_", extra="ignore")

    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    user: str = Field(default="survey_engineer")
    password: str = Field(default="survey_pg_pass")
    db: str = Field(default="survey_dw")

    @property
    def resolved_host(self) -> str:
        """Resolves host, falling back to WSL IP if on Windows and WSL host IP is set."""
        h = self.host
        if h in ("localhost", "127.0.0.1") and os.name == "nt":
            wsl_ip = os.environ.get("WSL_HOST_IP")
            if wsl_ip:
                return wsl_ip
        return h

    @property
    def url(self) -> str:
        """Construct SQLAlchemy-compatible PostgreSQL connection string."""
        h = self.resolved_host
        return f"postgresql+psycopg2://{self.user}:{self.password}@{h}:{self.port}/{self.db}"


class PipelineSettings(BaseSettings):
    """Overall pipeline parameters and execution thresholds."""

    model_config = SettingsConfigDict(extra="ignore")

    pipeline_env: str = Field(default="development", alias="PIPELINE_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    batch_id: str = Field(default="auto", alias="BATCH_ID")
    data_dir: Path = Field(default=BASE_DIR / "data", alias="DATA_DIR")
    fuzzy_match_threshold: float = Field(default=85.0, alias="FUZZY_MATCH_THRESHOLD")
    outlier_iqr_factor: float = Field(default=1.5, alias="OUTLIER_IQR_FACTOR")

    # Nested configurations
    mongo: MongoSettings = Field(default_factory=MongoSettings)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)

    @property
    def raw_data_dir(self) -> Path:
        return Path(self.data_dir) / "raw"

    @property
    def sample_data_dir(self) -> Path:
        return Path(self.data_dir) / "sample"

    @property
    def reference_data_dir(self) -> Path:
        return Path(self.data_dir) / "reference"

    @property
    def docs_dir(self) -> Path:
        return BASE_DIR / "docs"

    @property
    def sql_dir(self) -> Path:
        return BASE_DIR / "sql"


# Global singleton instance
settings = PipelineSettings()
