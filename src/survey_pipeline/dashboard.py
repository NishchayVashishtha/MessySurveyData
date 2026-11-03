"""Interactive Streamlit Portfolio & Analytics Dashboard for survey-data-pipeline."""

from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import text

from survey_pipeline.config import PipelineSettings
from survey_pipeline.mongo_db import get_database
from survey_pipeline.pg_db import get_pg_engine

# -----------------------------------------------------------------------------
# Page Configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Survey Data Pipeline | Analytics & Metastore",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling for Dark Theme & Glassmorphism Aesthetics
st.markdown(
    """
    <style>
    .metric-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7), rgba(15, 23, 42, 0.8));
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #38bdf8;
    }
    .metric-label {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94a3b8;
    }
    .badge-pass {
        background-color: #065f46;
        color: #34d399;
        padding: 2px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_db_connections():
    """Initializes and caches database connection engines."""
    settings = PipelineSettings()
    pg_engine = get_pg_engine(settings.postgres.url)
    mongo_db = get_database(settings.mongo.uri, settings.mongo.db)
    return pg_engine, mongo_db, settings


pg_engine, mongo_db, settings = get_db_connections()


# -----------------------------------------------------------------------------
# Data Loaders (Cached with TTL)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=15)
def load_kpis():
    """Queries core volume and audit KPIs from PostgreSQL and MongoDB."""
    with pg_engine.connect() as conn:
        fact_count = (
            conn.execute(text("SELECT count(*) FROM warehouse.fact_responses")).scalar() or 0
        )
        choice_count = (
            conn.execute(text("SELECT count(*) FROM warehouse.fact_response_choices")).scalar() or 0
        )
        respondent_count = (
            conn.execute(text("SELECT count(*) FROM warehouse.dim_respondent")).scalar() or 0
        )
        reject_count = conn.execute(text("SELECT count(*) FROM audit.rejected_rows")).scalar() or 0
        dq_results = conn.execute(
            text(
                "SELECT count(*) as total, count(*) FILTER (WHERE status = 'PASS') as passed FROM audit.data_quality_results"
            )
        ).fetchone()

    total_dq = dq_results.total if dq_results else 0
    passed_dq = dq_results.passed if dq_results else 0
    dq_rate = (passed_dq / total_dq * 100) if total_dq > 0 else 100.0

    try:
        mongo_raw_count = mongo_db.raw_responses.count_documents({})
        mongo_rej_count = mongo_db.rejected_responses.count_documents({})
    except Exception:
        mongo_raw_count = 0
        mongo_rej_count = 0

    return {
        "fact_count": fact_count,
        "choice_count": choice_count,
        "respondent_count": respondent_count,
        "reject_count": reject_count,
        "mongo_raw_count": mongo_raw_count,
        "mongo_rej_count": mongo_rej_count,
        "dq_rate": dq_rate,
        "total_dq": total_dq,
        "passed_dq": passed_dq,
    }


@st.cache_data(ttl=30)
def load_state_sentiment():
    """Loads state sentiment ranking analytical view."""
    query = """
    SELECT state, respondent_count, average_rating, top_party, sentiment_tier, state_sentiment_rank
    FROM analytics.v_state_sentiment_ranking
    ORDER BY state_sentiment_rank ASC
    """
    with pg_engine.connect() as conn:
        return pd.read_sql(text(query), conn)


@st.cache_data(ttl=30)
def load_demographic_sentiment():
    """Loads demographic sentiment cross-tabulation view."""
    query = """
    SELECT age_group, gender, party_preference, respondent_count, average_rating, satisfaction_rate_pct
    FROM analytics.v_demographic_sentiment
    ORDER BY respondent_count DESC
    """
    with pg_engine.connect() as conn:
        return pd.read_sql(text(query), conn)


@st.cache_data(ttl=30)
def load_income_distribution():
    """Loads income percentile distribution by education tier."""
    query = """
    SELECT education_tier, valid_income_count, p25_income, median_income, p75_income, p90_income, iqr_spread
    FROM analytics.v_income_distribution
    ORDER BY median_income DESC
    """
    with pg_engine.connect() as conn:
        return pd.read_sql(text(query), conn)


@st.cache_data(ttl=30)
def load_top_choices():
    """Loads top exploded survey choices view."""
    query = """
    SELECT choice_category, choice_value, selection_count, overall_popularity_rank, category_popularity_rank, category_share_pct
    FROM analytics.v_top_choice_popularity
    ORDER BY selection_count DESC
    LIMIT 30
    """
    with pg_engine.connect() as conn:
        return pd.read_sql(text(query), conn)


@st.cache_data(ttl=15)
def load_audit_runs():
    """Loads pipeline batch runs audit log."""
    query = """
    SELECT batch_id, status, source_name, raw_extracted_count, clean_loaded_count,
           rejected_count, dropped_duplicates_count, execution_duration_sec, start_timestamp
    FROM audit.pipeline_runs
    ORDER BY start_timestamp DESC
    LIMIT 10
    """
    with pg_engine.connect() as conn:
        return pd.read_sql(text(query), conn)


@st.cache_data(ttl=15)
def load_dq_assertions():
    """Loads individual DQ assertion evaluations."""
    query = """
    SELECT batch_id, rule_name, rule_category, status, severity,
           records_evaluated, records_failed, failure_rate_pct, assertion_timestamp
    FROM audit.data_quality_results
    ORDER BY assertion_timestamp DESC
    LIMIT 35
    """
    with pg_engine.connect() as conn:
        return pd.read_sql(text(query), conn)


@st.cache_data(ttl=15)
def load_rejections_summary():
    """Loads summary of rejection reasons from dead-letter audit table."""
    query = """
    SELECT rejection_reason, count(*) as rejection_count
    FROM audit.rejected_rows
    GROUP BY rejection_reason
    ORDER BY rejection_count DESC
    """
    with pg_engine.connect() as conn:
        return pd.read_sql(text(query), conn)


# -----------------------------------------------------------------------------
# Sidebar
# -----------------------------------------------------------------------------
with st.sidebar:
    st.image(
        "https://img.shields.io/badge/Status-Production%20Active-brightgreen",
        use_container_width=True,
    )
    st.title("Survey Data Pipeline")
    st.markdown("**Dual-Store Lakehouse:** MongoDB 7.0 + PostgreSQL 16")
    st.markdown("---")

    st.subheader("System Infrastructure")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.caption("PostgreSQL Warehouse")
        st.markdown(f"`{settings.postgres.host}:{settings.postgres.port}`")
    with col_s2:
        st.caption("MongoDB Raw Lake")
        st.markdown(f"`{settings.mongo.host}:{settings.mongo.port}`")

    st.markdown("---")
    st.markdown("### Quick Navigation")
    st.markdown("""
        - [Architectural Overview](docs/architecture.md)
        - [Data Dictionary](docs/data_dictionary.md)
        - [Entity-Relationship Diagram](docs/erd.md)
        - [Query Optimization Report](docs/query_optimization.md)
        """)
    if st.button("🔄 Refresh Data Cache"):
        st.cache_data.clear()
        st.rerun()


# -----------------------------------------------------------------------------
# Main Dashboard Header & Metrics
# -----------------------------------------------------------------------------
st.title("⚡ Survey Data Engineering Lakehouse & Analytics")
st.markdown(
    "*Production ELT pipeline ingesting raw survey submissions into MongoDB, executing Pandas/RapidFuzz cleaning & DQ validation, and idempotently upserting into PostgreSQL Dimensional Star Schema.*"
)

kpis = load_kpis()

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric(
        label="PostgreSQL Warehouse Facts",
        value=f"{kpis['fact_count']:,}",
        delta=f"{kpis['respondent_count']:,} respondents",
    )
with c2:
    st.metric(
        label="MongoDB Raw Documents",
        value=f"{kpis['mongo_raw_count']:,}",
        delta="100% SHA-256 fingerprinted",
    )
with c3:
    st.metric(
        label="Multi-Select Choices",
        value=f"{kpis['choice_count']:,}",
        delta="Exploded bridge rows",
    )
with c4:
    st.metric(
        label="Data Quality SLA",
        value=f"{kpis['dq_rate']:.1f}%",
        delta=f"{kpis['passed_dq']}/{kpis['total_dq']} checks passed",
    )
with c5:
    st.metric(
        label="Audit Rejections",
        value=f"{kpis['reject_count']:,}",
        delta="Dead-letter routed",
        delta_color="inverse",
    )

st.markdown("---")

# -----------------------------------------------------------------------------
# Tabs Layout
# -----------------------------------------------------------------------------
tab_analytics, tab_perf, tab_dq, tab_runs, tab_trigger = st.tabs(
    [
        "📊 Warehouse Analytics",
        "⚡ SQL Optimization Benchmarks",
        "🛡️ Data Quality & Audit Center",
        "📋 Pipeline Runs Metastore",
        "🚀 Run Pipeline Ingestion",
    ]
)

# -----------------------------------------------------------------------------
# TAB 1: Warehouse Analytics
# -----------------------------------------------------------------------------
with tab_analytics:
    st.subheader("Public Opinion & Demographic Analytics Views")
    st.caption(
        "Live queries against curated PostgreSQL views (`analytics.v_*`) supporting high-concurrency decision making."
    )

    sub_t1, sub_t2, sub_t3 = st.tabs(
        ["State Sentiment Ranking", "Income Distribution by Education", "Top Multi-Select Choices"]
    )

    with sub_t1:
        df_state = load_state_sentiment()
        if not df_state.empty:
            c_left, c_right = st.columns([3, 2])
            with c_left:
                fig_state = px.bar(
                    df_state.head(20),
                    x="state",
                    y="average_rating",
                    color="sentiment_tier",
                    text="average_rating",
                    title="Average Public Sentiment by State (Top 20)",
                    labels={"average_rating": "Average Rating (1-5)", "state": "State / Territory"},
                    color_discrete_map={
                        "High Satisfaction": "#10b981",
                        "Moderate Satisfaction": "#3b82f6",
                        "Low Satisfaction": "#f59e0b",
                    },
                )
                fig_state.update_traces(texttemplate="%{text:.2f}", textposition="outside")
                fig_state.update_layout(xaxis_tickangle=-45, height=420)
                st.plotly_chart(fig_state, use_container_width=True)

            with c_right:
                st.markdown("#### Ranked State Data View")
                st.dataframe(
                    df_state[
                        [
                            "state_sentiment_rank",
                            "state",
                            "respondent_count",
                            "average_rating",
                            "top_party",
                            "sentiment_tier",
                        ]
                    ],
                    hide_index=True,
                    height=380,
                    use_container_width=True,
                )
        else:
            st.info("No data available in `analytics.v_state_sentiment_ranking` yet.")

    with sub_t2:
        df_income = load_income_distribution()
        if not df_income.empty:
            fig_income = go.Figure()
            for _, row in df_income.iterrows():
                fig_income.add_trace(
                    go.Box(
                        y=[
                            row["p25_income"],
                            row["median_income"],
                            row["p75_income"],
                            row["p90_income"],
                        ],
                        name=str(row["education_tier"]),
                        boxpoints=False,
                    )
                )
            fig_income.update_layout(
                title="Income Distribution Spread by Standardized Education Tier (INR / Monthly)",
                yaxis_title="Monthly Income (₹)",
                xaxis_title="Educational Attainment",
                height=450,
            )
            st.plotly_chart(fig_income, use_container_width=True)
            st.dataframe(df_income, hide_index=True, use_container_width=True)
        else:
            st.info("No data available in `analytics.v_income_distribution`.")

    with sub_t3:
        df_choices = load_top_choices()
        if not df_choices.empty:
            fig_choices = px.bar(
                df_choices.head(15),
                x="selection_count",
                y="choice_value",
                color="choice_category",
                orientation="h",
                title="Top Multi-Select Answers Across All Survey Waves",
                labels={"selection_count": "Total Selections", "choice_value": "Answer Option"},
            )
            fig_choices.update_layout(yaxis={"categoryorder": "total ascending"}, height=450)
            st.plotly_chart(fig_choices, use_container_width=True)
            st.dataframe(df_choices, hide_index=True, use_container_width=True)
        else:
            st.info("No multi-select choices extracted yet.")


# -----------------------------------------------------------------------------
# TAB 2: SQL Optimization Benchmarks
# -----------------------------------------------------------------------------
with tab_perf:
    st.subheader("Measured PostgreSQL Query Optimization Impact")
    st.markdown("""
        Performance comparison audited with **`EXPLAIN (ANALYZE, BUFFERS)`** across **80,591 facts** and **136,062 choice bridges**.
        """)

    perf_data = [
        {
            "Query ID": "Q1",
            "Analytical Workload": "Selective Demographic Filtering",
            "Optimization Technique": "B-Tree Index Scan (`idx_fact_responses_party`)",
            "Unoptimized Time": "163.05 ms",
            "Optimized Time": "0.64 ms",
            "Speedup": "254.4x faster",
            "Buffer I/O Reduction": "99.8% (6,412 -> 10 bufs)",
        },
        {
            "Query ID": "Q2",
            "Analytical Workload": "Multi-Select Category Share Aggregation",
            "Optimization Technique": "Single-Pass Window Aggregate (`OVER (PARTITION BY)`)",
            "Unoptimized Time": "1,006.72 ms",
            "Optimized Time": "43.85 ms",
            "Speedup": "23.0x faster",
            "Buffer I/O Reduction": "83.7% (54,747 -> 8,942 bufs)",
        },
        {
            "Query ID": "Q3",
            "Analytical Workload": "State-Wise Sentiment Ranking",
            "Optimization Technique": "Direct Window Aggregate Scan",
            "Unoptimized Time": "36.82 ms",
            "Optimized Time": "56.05 ms",
            "Speedup": "0.7x (In-memory sort)",
            "Buffer I/O Reduction": "In-memory sort",
        },
        {
            "Query ID": "Q4",
            "Analytical Workload": "Income Percentiles by Education Tier",
            "Optimization Technique": "Outlier-Filtered Scan (`is_outlier_income = FALSE`)",
            "Unoptimized Time": "205.26 ms",
            "Optimized Time": "94.24 ms",
            "Speedup": "2.2x faster",
            "Buffer I/O Reduction": "0.5% (15,049 -> 14,981 bufs)",
        },
    ]

    st.dataframe(pd.DataFrame(perf_data), hide_index=True, use_container_width=True)

    st.markdown("---")
    st.subheader("Live Dynamic Query Benchmark Runner")
    st.caption(
        "Execute Query Q1 live against the containerized database and inspect the real-time execution plan."
    )

    col_q1, col_q2 = st.columns([1, 1])
    with col_q1:
        if st.button("⚡ Run Live Optimized Q1 (With B-Tree Index)"):
            with pg_engine.connect() as conn:
                start_t = datetime.now()
                plan_rows = conn.execute(text("""
                        EXPLAIN (ANALYZE, BUFFERS)
                        SELECT f.fact_id, f.respondent_id, g.state, f.survey_rating
                        FROM warehouse.fact_responses f
                        JOIN warehouse.dim_geography g ON f.geography_key = g.geography_key
                        WHERE f.party_preference = 'INC'
                          AND f.is_outlier_income = FALSE;
                        """)).fetchall()
                exec_ms = (datetime.now() - start_t).total_seconds() * 1000
                st.success(f"Execution Completed in **{exec_ms:.2f} ms**")
                plan_text = "\n".join([r[0] for r in plan_rows])
                st.code(plan_text, language="text")

    with col_q2:
        st.markdown(
            "> **Why Q1 Achieves 254.4x Speedup:**\n\n"
            "> Without an index, PostgreSQL must sequentially scan all **80,591 table rows** and test each row against the `party_preference` filter, touching over **6,400 shared buffer pages**.\n\n"
            "> The B-Tree index converts this into a **single point index lookup** touching only **10 shared buffer pages**."
        )


# -----------------------------------------------------------------------------
# TAB 3: Data Quality & Audit Center
# -----------------------------------------------------------------------------
with tab_dq:
    st.subheader("Data Quality Gate & Dead-Letter Audit Logs")
    st.caption(
        "Enforcing mathematical assertions and exact row reconciliation before warehouse insertion."
    )

    c_dq1, c_dq2 = st.columns([3, 2])
    with c_dq1:
        df_dq = load_dq_assertions()
        if not df_dq.empty:
            st.markdown("#### Recent Data Quality Assertion Evaluations")
            st.dataframe(df_dq, hide_index=True, use_container_width=True, height=360)
        else:
            st.info("No DQ results logged yet.")

    with c_dq2:
        df_rej = load_rejections_summary()
        if not df_rej.empty:
            st.markdown("#### Dead-Letter Rejections by Root Cause")
            fig_rej = px.pie(
                df_rej,
                names="rejection_reason",
                values="rejection_count",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig_rej.update_layout(height=360)
            st.plotly_chart(fig_rej, use_container_width=True)
        else:
            st.info("No rejected records.")


# -----------------------------------------------------------------------------
# TAB 4: Pipeline Runs Metastore
# -----------------------------------------------------------------------------
with tab_runs:
    st.subheader("Pipeline Batch Runs Metastore (`audit.pipeline_runs`)")
    st.caption("Tracks end-to-end lineage, duration, input volume, and row-level reconciliation.")

    df_runs = load_audit_runs()
    if not df_runs.empty:
        st.dataframe(df_runs, hide_index=True, use_container_width=True)
    else:
        st.info("No pipeline runs logged in metastore.")


# -----------------------------------------------------------------------------
# TAB 5: Live Pipeline Ingestion Trigger
# -----------------------------------------------------------------------------
with tab_trigger:
    st.subheader("Trigger Live On-Demand Pipeline Execution")
    st.markdown(
        "Submit a live ingestion batch to test data extraction, MongoDB landing, cleaning, and PostgreSQL loading."
    )

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        source_choice = st.selectbox(
            "Select Data Source",
            ["synthetic (Messy Survey Generator)", "real (Ask-A-Manager / TidyTuesday Survey)"],
            index=0,
        )
        batch_size = st.slider(
            "Record Volume (Synthetic only)", min_value=1000, max_value=25000, value=5000, step=1000
        )

    with col_t2:
        custom_batch_id = st.text_input(
            "Custom Batch ID", value=f"BATCH_UI_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        st.caption(
            "Execution is fully idempotent: re-submitting an identical batch creates zero duplicate warehouse facts."
        )

    if st.button("🚀 Execute Ingestion Pipeline Now"):
        with st.spinner("Executing pipeline batch in background..."):
            import subprocess

            src_arg = "synthetic" if "synthetic" in source_choice else "real"
            cmd = [
                "python",
                "-m",
                "survey_pipeline.run",
                "--source",
                src_arg,
                "--batch-id",
                custom_batch_id,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                st.success(f"Batch **{custom_batch_id}** Executed Successfully!")
                st.cache_data.clear()
            else:
                st.error("Pipeline Execution Failed:")
                st.code(res.stderr or res.stdout)
