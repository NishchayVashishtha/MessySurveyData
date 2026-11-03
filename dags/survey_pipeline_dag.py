"""Apache Airflow DAG: survey_pipeline_orchestration (OPTIONAL ENHANCEMENT).

Demonstrates production scheduling of survey data ingestion, validation,
and warehouse loading using standard BashOperator and PythonOperator.
"""

from datetime import datetime, timedelta

try:
    from airflow import DAG
    from airflow.operators.bash import BashOperator
    from airflow.operators.python import PythonOperator
    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False


default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": True,
    "email": ["alerts@surveyanalytics.com"],
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

if AIRFLOW_AVAILABLE:
    with DAG(
        dag_id="survey_data_pipeline_daily",
        default_args=default_args,
        description="Daily ELT Survey Data Lake & Star Schema Warehouse Ingestion",
        schedule_interval="0 3 * * *",  # 03:00 UTC daily
        start_date=datetime(2025, 1, 1),
        catchup=False,
        tags=["survey", "etl", "mongodb", "postgres", "data-quality"],
    ) as dag:

        # 1. Health check databases
        task_health_check = BashOperator(
            task_id="check_database_health",
            bash_command="pg_isready -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB",
        )

        # 2. Extract & Land Raw Data in MongoDB
        task_extract_and_land = BashOperator(
            task_id="extract_raw_to_mongodb",
            bash_command="python -m survey_pipeline.run --source synthetic --skip-pg",
        )

        # 3. Clean, Validate & Load PostgreSQL
        task_transform_load_pg = BashOperator(
            task_id="transform_validate_load_pg",
            bash_command="python -m survey_pipeline.run --source synthetic --skip-mongo",
        )

        # Pipeline DAG dependencies
        task_health_check >> task_extract_and_land >> task_transform_load_pg
