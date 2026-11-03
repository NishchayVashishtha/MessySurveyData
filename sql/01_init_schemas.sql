-- ==============================================================================
-- 01_init_schemas.sql
-- Sets up core logical schemas and database extensions for survey-data-pipeline
-- ==============================================================================

-- Enable standard extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 1. Staging Schema: transient landing zone for bulk ingestion
CREATE SCHEMA IF NOT EXISTS staging;

-- 2. Warehouse Schema: dimensional model (Star Schema: facts, dims, bridge)
CREATE SCHEMA IF NOT EXISTS warehouse;

-- 3. Analytics Schema: consumer-facing optimized views & reporting queries
CREATE SCHEMA IF NOT EXISTS analytics;

-- 4. Audit Schema: data quality checks, pipeline run logs, and rejected rows
CREATE SCHEMA IF NOT EXISTS audit;

-- Set search path default
SET search_path TO warehouse, staging, analytics, audit, public;
