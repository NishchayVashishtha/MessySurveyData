# ==============================================================================
# Dockerfile for survey-data-pipeline
# Python 3.11 lightweight production container
# ==============================================================================
FROM python:3.11-slim

# Prevent Python from writing pyc files and enable unbuffered streaming
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Install system dependencies for psycopg2 and health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

# Copy source code, schemas, scripts, references, and tests
COPY pyproject.toml ./
COPY src/ ./src/
COPY sql/ ./sql/
COPY scripts/ ./scripts/
COPY data/reference/ ./data/reference/
COPY tests/ ./tests/

# Create raw and sample data directories
RUN mkdir -p /app/data/raw /app/data/sample /app/docs

# Default entrypoint runs the pipeline CLI
ENTRYPOINT ["python", "-m", "survey_pipeline.run"]
CMD ["--source", "synthetic", "--batch-id", "auto"]
