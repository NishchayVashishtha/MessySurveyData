#!/usr/bin/env bash
# ==============================================================================
# run_pipeline.sh
# Production Automation Shell Script for survey-data-pipeline
# Supports CLI flags, structured logging, trap signals, and execution error codes
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="${PROJECT_ROOT}/logs"
TIMESTAMP="$(date +'%Y%m%d_%H%M%S')"
RUN_LOG="${LOG_DIR}/pipeline_run_${TIMESTAMP}.log"

mkdir -p "${LOG_DIR}"

# Default parameters
SOURCE="synthetic"
BATCH_ID="auto"
FORCE_DOWNLOAD="false"
SKIP_MONGO="false"
SKIP_PG="false"

# ANSI Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    local level="$1"
    local msg="$2"
    local ts
    ts="$(date +'%Y-%m-%d %H:%M:%S')"
    echo -e "${CYAN}${ts}${NC} | ${level} | ${msg}" | tee -a "${RUN_LOG}"
}

error_handler() {
    local exit_code="$?"
    local line_no="$1"
    log "${RED}ERROR${NC}" "Pipeline failed at line ${line_no} with exit code ${exit_code}."
    exit "${exit_code}"
}

trap 'error_handler $LINENO' ERR
trap 'log "${YELLOW}WARN${NC}" "Interruption signal received. Terminating gracefully..."; exit 130' INT TERM

usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
    -s, --source SOURCE        Data source to ingest (synthetic, real, tidytuesday, stackoverflow) [default: synthetic]
    -b, --batch-id BATCH_ID    Execution batch ID [default: auto]
    -f, --force                Force re-download of raw datasets
    --skip-mongo               Skip MongoDB landing zone ingestion
    --skip-pg                  Skip PostgreSQL warehouse loading
    -h, --help                 Display this help message and exit

Examples:
    $0 --source synthetic --batch-id BATCH_001
    $0 --source real --force
EOF
}

# Parse Command Line Arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -s|--source)
            SOURCE="$2"
            shift 2
            ;;
        -b|--batch-id)
            BATCH_ID="$2"
            shift 2
            ;;
        -f|--force)
            FORCE_DOWNLOAD="true"
            shift
            ;;
        --skip-mongo)
            SKIP_MONGO="true"
            shift
            ;;
        --skip-pg)
            SKIP_PG="true"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown argument: $1${NC}"
            usage
            exit 1
            ;;
    esac
done

log "${GREEN}INFO${NC}" "Starting automated survey data pipeline run..."
log "${GREEN}INFO${NC}" "Project Root: ${PROJECT_ROOT}"
log "${GREEN}INFO${NC}" "Source: ${SOURCE} | Batch: ${BATCH_ID}"

# Prepare Python execution command
CMD=(python -m survey_pipeline.run --source "${SOURCE}" --batch-id "${BATCH_ID}")

if [[ "${FORCE_DOWNLOAD}" == "true" ]]; then
    CMD+=(--force-download)
fi
if [[ "${SKIP_MONGO}" == "true" ]]; then
    CMD+=(--skip-mongo)
fi
if [[ "${SKIP_PG}" == "true" ]]; then
    CMD+=(--skip-pg)
fi

START_SEC=$SECONDS
log "${GREEN}INFO${NC}" "Executing: ${CMD[*]}"

cd "${PROJECT_ROOT}"
"${CMD[@]}" 2>&1 | tee -a "${RUN_LOG}"

DURATION=$(( SECONDS - START_SEC ))
log "${GREEN}SUCCESS${NC}" "Pipeline completed successfully in ${DURATION}s. Detailed run log saved to: ${RUN_LOG}"
exit 0
