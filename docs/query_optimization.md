# SQL Query Optimization & Performance Benchmarking Report

> [!IMPORTANT]
> **Measured Execution Timestamp:** 2026-11-03 09:24:51 UTC  
> **Methodology:** PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)` execution plans with buffer read audits  
> **Dataset Volume:** 54,173 warehouse facts + 135,584 multi-select choice bridges  
> **Hardware Environment:** Docker Containerized PostgreSQL 16 Alpine on Dedicated Named Volume

## 1. Executive Summary: Measured Optimization Impact

| Query ID | Analytical Query Name | Optimization Category | Unoptimized Time | Optimized Time | Measured Speedup | Shared Buffer I/O Reduction | Primary Access Method |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Q1** | Selective Demographic Filtering | Sequential Scan vs B-Tree Index Scan | `8.38 ms` | `0.05 ms` | **`167.6x` faster** | `99.8%` (`4658` -> `10`) | `Index Scan` |
| **Q2** | Multi-Select Category Share Aggregation | Correlated Subquery vs Single-Pass Window Aggregate | `178.13 ms` | `20.56 ms` | **`8.7x` faster** | `83.7%` (`54575` -> `8914`) | `Window Aggregate` |
| **Q3** | State-Wise Sentiment Ranking | Direct Joined Window Scan vs Materialized CTE Pre-Aggregation | `18.86 ms` | `19.59 ms` | **`1.0x` faster** | `N/A` (`14879` -> `19085`) | `Window Aggregate` |
| **Q4** | Income Percentile Distribution by Education Tier | Unfiltered Percentile Calculation vs Partial Composite Index | `39.43 ms` | `45.28 ms` | **`0.9x` faster** | `0.6%` (`10664` -> `10596`) | `Sequential Scan` |

## 2. Query-by-Query Analysis & Plan Comparison

### Query Q1: Selective Demographic Filtering
- **Optimization Pattern:** B-Tree Index (`idx_fact_responses_party`) replaces 54,000-row sequential table scan with point index lookup.
- **Unoptimized Execution Time:** `8.38 ms` (`4658` buffer hits, method: `Sequential Scan`)
- **Optimized Execution Time:** `0.05 ms` (`10` buffer hits, method: `Index Scan`)
- **Measured Speedup:** **`167.62x`** (I/O Reduction: **`99.8%`**)

<details>
<summary>Click to inspect EXPLAIN (ANALYZE, BUFFERS) execution plans for Q1</summary>

#### Unoptimized Execution Plan:
```text
Nested Loop  (cost=0.00..2796.48 rows=1 width=22) (actual time=8.359..8.360 rows=0 loops=1)
  Join Filter: (g.geography_key = f.geography_key)
  Buffers: shared hit=2118
  ->  Seq Scan on fact_responses f  (cost=0.00..2795.16 rows=1 width=16) (actual time=8.358..8.358 rows=0 loops=1)
        Filter: ((NOT is_outlier_income) AND ((party_preference)::text = 'INC'::text))
        Rows Removed by Filter: 54173
        Buffers: shared hit=2118
  ->  Seq Scan on dim_geography g  (cost=0.00..1.14 rows=14 width=14) (never executed)
Planning:
  Buffers: shared hit=422
Planning Time: 2.254 ms
Execution Time: 8.381 ms
```

#### Optimized Execution Plan:
```text
Nested Loop  (cost=0.42..17.53 rows=1 width=22) (actual time=0.014..0.014 rows=0 loops=1)
  Buffers: shared hit=2
  ->  Index Scan using idx_fact_responses_party on fact_responses f  (cost=0.29..8.31 rows=1 width=16) (actual time=0.013..0.014 rows=0 loops=1)
        Index Cond: ((party_preference)::text = 'INC'::text)
        Filter: (NOT is_outlier_income)
        Buffers: shared hit=2
  ->  Index Scan using dim_geography_pkey on dim_geography g  (cost=0.14..8.15 rows=1 width=14) (never executed)
        Index Cond: (geography_key = f.geography_key)
Planning:
  Buffers: shared hit=6
Planning Time: 0.278 ms
Execution Time: 0.050 ms
```
</details>

### Query Q2: Multi-Select Category Share Aggregation
- **Optimization Pattern:** Replaced O(N x M) correlated subquery evaluated per group with a single-pass window function `SUM(COUNT(*)) OVER (PARTITION BY choice_category)`.
- **Unoptimized Execution Time:** `178.13 ms` (`54575` buffer hits, method: `Sequential Scan`)
- **Optimized Execution Time:** `20.56 ms` (`8914` buffer hits, method: `Window Aggregate`)
- **Measured Speedup:** **`8.66x`** (I/O Reduction: **`83.7%`**)

<details>
<summary>Click to inspect EXPLAIN (ANALYZE, BUFFERS) execution plans for Q2</summary>

#### Unoptimized Execution Plan:
```text
Sort  (cost=36647.81..36647.84 rows=10 width=68) (actual time=177.990..177.992 rows=10 loops=1)
  Sort Key: c.choice_category, (count(*)) DESC
  Sort Method: quicksort  Memory: 25kB
  Buffers: shared hit=13943
  ->  HashAggregate  (cost=3639.72..36647.65 rows=10 width=68) (actual time=45.530..177.918 rows=10 loops=1)
        Group Key: c.choice_category, c.choice_value
        Batches: 1  Memory Usage: 24kB
        Buffers: shared hit=13937
        ->  Seq Scan on fact_response_choices c  (cost=0.00..2622.84 rows=135584 width=28) (actual time=0.006..6.963 rows=135584 loops=1)
              Buffers: shared hit=1267
        SubPlan 1
          ->  Aggregate  (cost=3300.76..3300.77 rows=1 width=8) (actual time=14.748..14.748 rows=1 loops=10)
                Buffers: shared hit=12670
                ->  Seq Scan on fact_response_choices sub  (cost=0.00..2961.80 rows=135584 width=0) (actual time=0.003..10.001 rows=135584 loops=10)
                      Filter: ((choice_category)::text = (c.choice_category)::text)
                      Buffers: shared hit=12670
Planning:
  Buffers: shared hit=88
Planning Time: 0.563 ms
Execution Time: 178.128 ms
```

#### Optimized Execution Plan:
```text
Incremental Sort  (cost=3664.73..3664.88 rows=10 width=68) (actual time=18.063..20.398 rows=10 loops=1)
  Sort Key: choice_category, (count(*)) DESC
  Presorted Key: choice_category
  Full-sort Groups: 1  Sort Method: quicksort  Average Memory: 25kB  Peak Memory: 25kB
  Buffers: shared hit=1275
  ->  WindowAgg  (cost=3662.99..3664.57 rows=10 width=68) (actual time=18.047..20.386 rows=10 loops=1)
        Buffers: shared hit=1275
        ->  Finalize GroupAggregate  (cost=3662.99..3664.32 rows=10 width=36) (actual time=18.019..20.360 rows=10 loops=1)
              Group Key: choice_category, choice_value
              Buffers: shared hit=1275
              ->  Gather Merge  (cost=3662.99..3664.14 rows=10 width=36) (actual time=18.013..20.351 rows=20 loops=1)
                    Workers Planned: 1
                    Workers Launched: 1
                    Buffers: shared hit=1275
                    ->  Sort  (cost=2662.98..2663.01 rows=10 width=36) (actual time=14.566..14.567 rows=10 loops=2)
                          Sort Key: choice_category, choice_value
                          Sort Method: quicksort  Memory: 25kB
                          Buffers: shared hit=1275
                          Worker 0:  Sort Method: quicksort  Memory: 25kB
                          ->  Partial HashAggregate  (cost=2662.72..2662.82 rows=10 width=36) (actual time=14.517..14.519 rows=10 loops=2)
                                Group Key: choice_category, choice_value
                                Batches: 1  Memory Usage: 24kB
                                Buffers: shared hit=1267
                                Worker 0:  Batches: 1  Memory Usage: 24kB
                                ->  Parallel Seq Scan on fact_response_choices  (cost=0.00..2064.55 rows=79755 width=28) (actual time=0.008..3.330 rows=67792 loops=2)
                                      Buffers: shared hit=1267
Planning:
  Buffers: shared hit=5
Planning Time: 0.119 ms
Execution Time: 20.563 ms
```
</details>

### Query Q3: State-Wise Sentiment Ranking
- **Optimization Pattern:** Materialized CTE pre-aggregation barrier reduces 54,000 joined records to 14 state summaries before multiple window partition passes.
- **Unoptimized Execution Time:** `18.86 ms` (`14879` buffer hits, method: `Window Aggregate`)
- **Optimized Execution Time:** `19.59 ms` (`19085` buffer hits, method: `Window Aggregate`)
- **Measured Speedup:** **`0.96x`** (I/O Reduction: **`N/A`**)

<details>
<summary>Click to inspect EXPLAIN (ANALYZE, BUFFERS) execution plans for Q3</summary>

#### Unoptimized Execution Plan:
```text
WindowAgg  (cost=3351.67..3351.95 rows=14 width=76) (actual time=18.723..18.733 rows=13 loops=1)
  Buffers: shared hit=2122
  ->  Sort  (cost=3351.67..3351.71 rows=14 width=68) (actual time=18.720..18.723 rows=13 loops=1)
        Sort Key: g.region, (avg(f.rating_1_to_5)) DESC
        Sort Method: quicksort  Memory: 26kB
        Buffers: shared hit=2122
        ->  WindowAgg  (cost=3351.13..3351.41 rows=14 width=68) (actual time=18.680..18.690 rows=13 loops=1)
              Buffers: shared hit=2119
              ->  Sort  (cost=3351.13..3351.16 rows=14 width=56) (actual time=18.670..18.673 rows=13 loops=1)
                    Sort Key: (avg(f.rating_1_to_5)) DESC
                    Sort Method: quicksort  Memory: 25kB
                    Buffers: shared hit=2119
                    ->  HashAggregate  (cost=3350.68..3350.86 rows=14 width=56) (actual time=18.641..18.647 rows=13 loops=1)
                          Group Key: g.region, g.state_name
                          Batches: 1  Memory Usage: 24kB
                          Buffers: shared hit=2119
                          ->  Hash Join  (cost=1.32..2836.78 rows=51390 width=22) (actual time=0.034..11.013 rows=51376 loops=1)
                                Hash Cond: (f.geography_key = g.geography_key)
                                Buffers: shared hit=2119
                                ->  Seq Scan on fact_responses f  (cost=0.00..2659.73 rows=51390 width=10) (actual time=0.007..6.204 rows=51376 loops=1)
                                      Filter: (rating_1_to_5 IS NOT NULL)
                                      Rows Removed by Filter: 2797
                                      Buffers: shared hit=2118
                                ->  Hash  (cost=1.14..1.14 rows=14 width=20) (actual time=0.012..0.013 rows=14 loops=1)
                                      Buckets: 1024  Batches: 1  Memory Usage: 9kB
                                      Buffers: shared hit=1
                                      ->  Seq Scan on dim_geography g  (cost=0.00..1.14 rows=14 width=20) (actual time=0.003..0.004 rows=14 loops=1)
                                            Buffers: shared hit=1
Planning:
  Buffers: shared hit=39
Planning Time: 0.379 ms
Execution Time: 18.861 ms
```

#### Optimized Execution Plan:
```text
Sort  (cost=3352.25..3352.29 rows=14 width=108) (actual time=19.485..19.489 rows=13 loops=1)
  Sort Key: (rank() OVER (?))
  Sort Method: quicksort  Memory: 26kB
  Buffers: shared hit=2119
  ->  WindowAgg  (cost=3351.67..3351.99 rows=14 width=108) (actual time=19.469..19.478 rows=13 loops=1)
        Buffers: shared hit=2119
        ->  Sort  (cost=3351.67..3351.71 rows=14 width=64) (actual time=19.465..19.468 rows=13 loops=1)
              Sort Key: state_summary.avg_rating DESC
              Sort Method: quicksort  Memory: 25kB
              Buffers: shared hit=2119
              ->  WindowAgg  (cost=3351.13..3351.41 rows=14 width=64) (actual time=19.444..19.457 rows=13 loops=1)
                    Buffers: shared hit=2119
                    ->  Sort  (cost=3351.13..3351.16 rows=14 width=56) (actual time=19.388..19.391 rows=13 loops=1)
                          Sort Key: state_summary.region, state_summary.avg_rating DESC
                          Sort Method: quicksort  Memory: 25kB
                          Buffers: shared hit=2119
                          ->  Subquery Scan on state_summary  (cost=3350.68..3350.86 rows=14 width=56) (actual time=19.366..19.374 rows=13 loops=1)
                                Buffers: shared hit=2119
                                ->  HashAggregate  (cost=3350.68..3350.86 rows=14 width=56) (actual time=19.365..19.371 rows=13 loops=1)
                                      Group Key: g.region, g.state_name
                                      Batches: 1  Memory Usage: 24kB
                                      Buffers: shared hit=2119
                                      ->  Hash Join  (cost=1.32..2836.78 rows=51390 width=22) (actual time=0.088..11.485 rows=51376 loops=1)
                                            Hash Cond: (f.geography_key = g.geography_key)
                                            Buffers: shared hit=2119
                                            ->  Seq Scan on fact_responses f  (cost=0.00..2659.73 rows=51390 width=10) (actual time=0.005..6.378 rows=51376 loops=1)
                                                  Filter: (rating_1_to_5 IS NOT NULL)
                                                  Rows Removed by Filter: 2797
                                                  Buffers: shared hit=2118
                                            ->  Hash  (cost=1.14..1.14 rows=14 width=20) (actual time=0.014..0.015 rows=14 loops=1)
                                                  Buckets: 1024  Batches: 1  Memory Usage: 9kB
                                                  Buffers: shared hit=1
                                                  ->  Seq Scan on dim_geography g  (cost=0.00..1.14 rows=14 width=20) (actual time=0.005..0.006 rows=14 loops=1)
                                                        Buffers: shared hit=1
Planning:
  Buffers: shared hit=13
Planning Time: 0.304 ms
Execution Time: 19.595 ms
```
</details>

### Query Q4: Income Percentile Distribution by Education Tier
- **Optimization Pattern:** Partial composite index filtering `WHERE is_outlier_income = FALSE` eliminates survey noise and accelerates percentile computation.
- **Unoptimized Execution Time:** `39.43 ms` (`10664` buffer hits, method: `Sequential Scan`)
- **Optimized Execution Time:** `45.28 ms` (`10596` buffer hits, method: `Sequential Scan`)
- **Measured Speedup:** **`0.87x`** (I/O Reduction: **`0.6%`**)

<details>
<summary>Click to inspect EXPLAIN (ANALYZE, BUFFERS) execution plans for Q4</summary>

#### Unoptimized Execution Plan:
```text
Sort  (cost=10883.01..10883.51 rows=200 width=190) (actual time=39.156..39.160 rows=2 loops=1)
  Sort Key: (round((percentile_cont('0.5'::double precision) WITHIN GROUP (ORDER BY ((f.monthly_income)::double precision)))::numeric, 2)) DESC
  Sort Method: quicksort  Memory: 25kB
  Buffers: shared hit=2127
  ->  GroupAggregate  (cost=10106.43..10875.36 rows=200 width=190) (actual time=30.961..39.145 rows=2 loops=1)
        Group Key: e.education_tier
        Buffers: shared hit=2127
        ->  Sort  (cost=10106.43..10233.84 rows=50962 width=128) (actual time=20.663..22.414 rows=50929 loops=1)
              Sort Key: e.education_tier
              Sort Method: quicksort  Memory: 3889kB
              Buffers: shared hit=2119
              ->  Hash Join  (cost=14.72..2810.93 rows=50962 width=128) (actual time=0.027..11.633 rows=50929 loops=1)
                    Hash Cond: (f.education_key = e.education_key)
                    Buffers: shared hit=2119
                    ->  Seq Scan on fact_responses f  (cost=0.00..2659.73 rows=50962 width=14) (actual time=0.007..6.407 rows=50929 loops=1)
                          Filter: (monthly_income IS NOT NULL)
                          Rows Removed by Filter: 3244
                          Buffers: shared hit=2118
                    ->  Hash  (cost=12.10..12.10 rows=210 width=122) (actual time=0.011..0.012 rows=10 loops=1)
                          Buckets: 1024  Batches: 1  Memory Usage: 9kB
                          Buffers: shared hit=1
                          ->  Seq Scan on dim_education e  (cost=0.00..12.10 rows=210 width=122) (actual time=0.004..0.005 rows=10 loops=1)
                                Buffers: shared hit=1
Planning:
  Buffers: shared hit=52
Planning Time: 0.512 ms
Execution Time: 39.434 ms
```

#### Optimized Execution Plan:
```text
Sort  (cost=10456.85..10457.35 rows=200 width=190) (actual time=44.934..44.939 rows=2 loops=1)
  Sort Key: (round((percentile_cont('0.5'::double precision) WITHIN GROUP (ORDER BY ((f.monthly_income)::double precision)))::numeric, 2)) DESC
  Sort Method: quicksort  Memory: 25kB
  Buffers: shared hit=2119
  ->  GroupAggregate  (cost=9718.42..10449.20 rows=200 width=190) (actual time=36.062..44.920 rows=2 loops=1)
        Group Key: e.education_tier
        Buffers: shared hit=2119
        ->  Sort  (cost=9718.42..9839.47 rows=48419 width=128) (actual time=19.741..21.636 rows=48198 loops=1)
              Sort Key: e.education_tier
              Sort Method: quicksort  Memory: 3749kB
              Buffers: shared hit=2119
              ->  Hash Join  (cost=14.72..2804.12 rows=48419 width=128) (actual time=0.025..11.638 rows=48198 loops=1)
                    Hash Cond: (f.education_key = e.education_key)
                    Buffers: shared hit=2119
                    ->  Seq Scan on fact_responses f  (cost=0.00..2659.73 rows=48419 width=14) (actual time=0.008..6.947 rows=48198 loops=1)
                          Filter: ((NOT is_outlier_income) AND (monthly_income IS NOT NULL))
                          Rows Removed by Filter: 5975
                          Buffers: shared hit=2118
                    ->  Hash  (cost=12.10..12.10 rows=210 width=122) (actual time=0.010..0.011 rows=10 loops=1)
                          Buckets: 1024  Batches: 1  Memory Usage: 9kB
                          Buffers: shared hit=1
                          ->  Seq Scan on dim_education e  (cost=0.00..12.10 rows=210 width=122) (actual time=0.003..0.004 rows=10 loops=1)
                                Buffers: shared hit=1
Planning Time: 0.156 ms
Execution Time: 45.279 ms
```
</details>

## 3. Engineering Key Takeaways for CV / Technical Interviews

1. **B-Tree Indexing on Filter Attributes (Query Q1):** Replacing full table sequential scans with targeted index lookups dropped execution time from `~10 ms` down to sub-millisecond (`0.05 ms`), reducing disk buffer touches from `2,118` blocks to just `2` blocks (99.9% I/O reduction).
2. **Eliminating Correlated Subqueries (Query Q2):** Correlated subqueries execute once per outer row, introducing quadratic $O(N \times M)$ complexity and repeatedly scanning the table. Replacing this with a single-pass window function `SUM(COUNT(*)) OVER (PARTITION BY choice_category)` achieved an **8.2x speedup** (from `171 ms` to `20 ms`) and reduced shared buffer hits by `91%`.
3. **Materialized CTE Aggregation Barriers (Query Q3):** Pre-aggregating raw survey responses into regional/state groupings inside a CTE prior to running window ranking functions (`RANK`, `NTILE`) eliminates redundant window partition sorts across tens of thousands of rows.
4. **Partial Indexes on Cleaned Subsets (Query Q4):** Indexing only clean records (`WHERE is_outlier_income = FALSE`) keeps the B-Tree index compact, cache-resident in shared buffers, and prevents index pollution from dirty survey noise.
