/**
 * SurveyPulse - Interactive Data Engineering & Analytics Web App
 * Executes client-side against authentic warehouse export payload (PIPELINE_DATA).
 */

document.addEventListener('DOMContentLoaded', () => {
  // Check if payload is loaded
  if (typeof PIPELINE_DATA === 'undefined') {
    console.error('PIPELINE_DATA not found. Make sure data.js is loaded.');
    return;
  }

  // 1. Populate KPI Summary Cards
  populateKPIs();

  // 2. Initialize Navigation Tabs
  initTabs();

  // 3. Initialize Analytical Charts & Tables
  initAnalyticsViews();

  // 4. Initialize SQL Optimization Benchmark Explorer
  initBenchmarkExplorer();

  // 5. Initialize Data Quality & Audit Center
  initDataQualityCenter();

  // 6. Initialize In-Browser Interactive SQL Console
  initSQLConsole();
});

// -----------------------------------------------------------------------------
// 1. KPI Population
// -----------------------------------------------------------------------------
function populateKPIs() {
  const k = PIPELINE_DATA.kpis;
  document.getElementById('kpi-facts').textContent = Number(k.fact_count).toLocaleString();
  document.getElementById('kpi-respondents').textContent = `${Number(k.respondent_count).toLocaleString()} respondents`;
  
  document.getElementById('kpi-mongo').textContent = Number(k.mongo_raw_count).toLocaleString();
  document.getElementById('kpi-choices').textContent = Number(k.choice_count).toLocaleString();
  
  document.getElementById('kpi-dq').textContent = `${k.dq_rate.toFixed(1)}%`;
  document.getElementById('kpi-dq-sub').textContent = `${k.dq_passed}/${k.dq_total} checks passed`;

  document.getElementById('kpi-rejects').textContent = Number(k.reject_count).toLocaleString();
}

// -----------------------------------------------------------------------------
// 2. Tab Navigation
// -----------------------------------------------------------------------------
function initTabs() {
  const buttons = document.querySelectorAll('.nav-btn');
  const panels = document.querySelectorAll('.tab-content');

  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.getAttribute('data-tab');
      buttons.forEach(b => b.classList.remove('active'));
      panels.forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const activePanel = document.getElementById(`tab-${target}`);
      if (activePanel) {
        activePanel.classList.add('active');
      }
    });
  });
}

// -----------------------------------------------------------------------------
// 3. Analytical Charts & Views
// -----------------------------------------------------------------------------
function initAnalyticsViews() {
  const states = PIPELINE_DATA.state_sentiment || [];

  // Render State Sentiment Chart
  const ctxState = document.getElementById('chart-state-sentiment')?.getContext('2d');
  if (ctxState && states.length > 0) {
    const topStates = states.slice(0, 15);
    new Chart(ctxState, {
      type: 'bar',
      data: {
        labels: topStates.map(s => s.state_name),
        datasets: [{
          label: 'Average Survey Rating (1-5)',
          data: topStates.map(s => Number(s.avg_rating)),
          backgroundColor: topStates.map(s => {
            const r = Number(s.avg_rating);
            if (r >= 3.25) return 'rgba(16, 185, 129, 0.85)';
            if (r >= 3.20) return 'rgba(56, 189, 248, 0.85)';
            return 'rgba(245, 158, 11, 0.85)';
          }),
          borderRadius: 6,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              afterLabel: function(context) {
                const item = topStates[context.dataIndex];
                return `Respondents: ${Number(item.response_count).toLocaleString()}\nRank: #${item.national_sentiment_rank}`;
              }
            }
          }
        },
        scales: {
          y: { min: 2.5, max: 4.0, grid: { color: 'rgba(255, 255, 255, 0.05)' } },
          x: { grid: { display: false } }
        }
      }
    });
  }

  // Populate State Table
  const tbodyState = document.getElementById('tbody-state-ranking');
  if (tbodyState) {
    tbodyState.innerHTML = states.map(s => `
      <tr>
        <td><strong>#${s.national_sentiment_rank}</strong></td>
        <td>${s.state_name}</td>
        <td><span class="badge" style="background: rgba(99, 102, 241, 0.15); color: #818cf8;">${s.region}</span></td>
        <td>${Number(s.response_count).toLocaleString()}</td>
        <td><strong style="color: #38bdf8;">${s.avg_rating}</strong></td>
        <td>${(Number(s.avg_quality_score) * 100).toFixed(1)}%</td>
        <td><span class="badge ${s.sentiment_quartile === 1 ? 'badge-pass' : 'badge-speedup'}">Tier ${s.sentiment_quartile}</span></td>
      </tr>
    `).join('');
  }

  // Income Distribution Chart
  const incomes = PIPELINE_DATA.income_distribution || [];
  const ctxIncome = document.getElementById('chart-income-education')?.getContext('2d');
  if (ctxIncome && incomes.length > 0) {
    new Chart(ctxIncome, {
      type: 'bar',
      data: {
        labels: incomes.map(i => i.education_tier),
        datasets: [
          {
            label: '25th Percentile (₹)',
            data: incomes.map(i => Number(i.p25_income)),
            backgroundColor: 'rgba(99, 102, 241, 0.65)',
            borderRadius: 4
          },
          {
            label: 'Median Income (₹)',
            data: incomes.map(i => Number(i.median_income)),
            backgroundColor: 'rgba(56, 189, 248, 0.85)',
            borderRadius: 4
          },
          {
            label: '75th Percentile (₹)',
            data: incomes.map(i => Number(i.p75_income)),
            backgroundColor: 'rgba(16, 185, 129, 0.75)',
            borderRadius: 4
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'top', labels: { color: '#94a3b8' } }
        },
        scales: {
          y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { callback: v => `₹${v.toLocaleString()}` } },
          x: { grid: { display: false } }
        }
      }
    });
  }

  // Multi-Select Choices Chart
  const choices = PIPELINE_DATA.top_choices || [];
  const ctxChoices = document.getElementById('chart-choices-popularity')?.getContext('2d');
  if (ctxChoices && choices.length > 0) {
    const top10 = choices.slice(0, 10);
    new Chart(ctxChoices, {
      type: 'bar',
      data: {
        labels: top10.map(c => c.choice_value),
        datasets: [{
          label: 'Total Survey Selections',
          data: top10.map(c => Number(c.selection_count)),
          backgroundColor: 'rgba(168, 85, 247, 0.8)',
          borderRadius: 6
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: 'rgba(255, 255, 255, 0.05)' } },
          y: { grid: { display: false } }
        }
      }
    });
  }
}

// -----------------------------------------------------------------------------
// 4. SQL Optimization Benchmark Explorer
// -----------------------------------------------------------------------------
function initBenchmarkExplorer() {
  const container = document.getElementById('benchmark-container');
  if (!container) return;

  const bms = PIPELINE_DATA.benchmarks || [];
  container.innerHTML = bms.map(b => `
    <div class="benchmark-card">
      <div class="benchmark-header">
        <div>
          <span class="badge badge-speedup" style="margin-right: 8px;">${b.id}</span>
          <strong class="benchmark-title">${b.title}</strong>
        </div>
        <div>
          <span class="badge badge-pass" style="font-size: 0.85rem; padding: 4px 12px;">${b.speedup} FASTER</span>
        </div>
      </div>
      <p style="color: var(--text-secondary); font-size: 0.88rem; margin-bottom: 12px;">
        <strong>Optimization Pattern:</strong> ${b.pattern} | 
        <strong>I/O Buffer Reduction:</strong> <span style="color: var(--accent-cyan); font-weight: 600;">${b.io_reduction}</span> 
        (${b.unopt_buffers.toLocaleString()} -> ${b.opt_buffers.toLocaleString()} buffer hits)
      </p>

      <div class="speed-meter">
        <div class="time-bar-group">
          <div class="time-bar-label">
            <span>Unoptimized Execution</span>
            <span><strong>${b.unopt_ms} ms</strong></span>
          </div>
          <div class="time-bar-bg">
            <div class="time-bar-fill fill-unopt" style="width: 100%;"></div>
          </div>
        </div>

        <div class="time-bar-group">
          <div class="time-bar-label">
            <span>Optimized (PostgreSQL Index / Window)</span>
            <span style="color: #34d399;"><strong>${b.opt_ms} ms</strong></span>
          </div>
          <div class="time-bar-bg">
            <div class="time-bar-fill fill-opt" style="width: ${Math.max(2, (b.opt_ms / b.unopt_ms) * 100)}%;"></div>
          </div>
        </div>
      </div>

      <details style="margin-top: 14px;">
        <summary style="font-size: 0.82rem; color: var(--accent-cyan); cursor: pointer;">View SQL Comparison & EXPLAIN Plan</summary>
        <div style="margin-top: 10px; background: #050811; padding: 12px; border-radius: 6px; font-family: var(--font-mono); font-size: 0.8rem; overflow-x: auto;">
          <strong style="color: var(--accent-rose);">// Unoptimized Query:</strong>\n${escapeHtml(b.sql_unopt)}\n\n<strong style="color: #34d399;">// Optimized Plan:</strong>\n${escapeHtml(b.sql_opt)}
        </div>
      </details>
    </div>
  `).join('');
}

// -----------------------------------------------------------------------------
// 5. Data Quality & Audit Center
// -----------------------------------------------------------------------------
function initDataQualityCenter() {
  // Rejections Chart
  const rej = PIPELINE_DATA.rejections_summary || [];
  const ctxRej = document.getElementById('chart-rejections')?.getContext('2d');
  if (ctxRej && rej.length > 0) {
    new Chart(ctxRej, {
      type: 'doughnut',
      data: {
        labels: rej.map(r => r.rejection_reason),
        datasets: [{
          data: rej.map(r => r.count),
          backgroundColor: [
            '#f43f5e',
            '#fb7185',
            '#f59e0b',
            '#e11d48'
          ],
          borderWidth: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'right', labels: { color: '#94a3b8', font: { size: 11 } } }
        }
      }
    });
  }

  // Populate DQ Assertions Table
  const tbodyDQ = document.getElementById('tbody-dq-assertions');
  const assertions = PIPELINE_DATA.dq_assertions || [];
  if (tbodyDQ && assertions.length > 0) {
    tbodyDQ.innerHTML = assertions.map(a => `
      <tr>
        <td><strong>${a.batch_id}</strong></td>
        <td><code>${a.check_name}</code></td>
        <td>${a.target_table}</td>
        <td><span class="badge ${a.passed ? 'badge-pass' : 'badge-fail'}">${a.passed ? 'PASS' : 'FAIL'}</span></td>
        <td>${a.severity}</td>
        <td>${a.failed_records_count}</td>
        <td><small style="color: var(--text-muted);">${a.expected_condition}</small></td>
      </tr>
    `).join('');
  }

  // Populate Pipeline Runs Table
  const tbodyRuns = document.getElementById('tbody-pipeline-runs');
  const runs = PIPELINE_DATA.pipeline_runs || [];
  if (tbodyRuns && runs.length > 0) {
    tbodyRuns.innerHTML = runs.map(r => `
      <tr>
        <td><strong>${r.batch_id}</strong></td>
        <td><span class="badge badge-pass">${r.status}</span></td>
        <td>${r.source_name}</td>
        <td>${Number(r.records_extracted).toLocaleString()}</td>
        <td>${Number(r.records_loaded_pg).toLocaleString()}</td>
        <td><span style="color: var(--accent-rose);">${Number(r.records_rejected).toLocaleString()}</span></td>
        <td>${Number(r.duplicates_dropped).toLocaleString()}</td>
        <td>${r.duration_sec}s</td>
        <td>${r.started_at}</td>
      </tr>
    `).join('');
  }
}

// -----------------------------------------------------------------------------
// 6. In-Browser Interactive SQL Console
// -----------------------------------------------------------------------------
function initSQLConsole() {
  const btnRun = document.getElementById('btn-run-sql');
  const sqlInput = document.getElementById('sql-query-input');
  const resultDiv = document.getElementById('sql-result-container');
  const execTimeSpan = document.getElementById('sql-exec-time');

  if (!btnRun || !sqlInput || !resultDiv) return;

  const facts = PIPELINE_DATA.fact_sample || [];

  // Register click handlers for preset buttons
  document.querySelectorAll('.btn-preset').forEach(btn => {
    btn.addEventListener('click', () => {
      sqlInput.value = btn.getAttribute('data-sql');
      executeSQL();
    });
  });

  btnRun.addEventListener('click', executeSQL);

  function executeSQL() {
    const query = sqlInput.value.trim();
    if (!query) return;

    try {
      const startT = performance.now();
      
      // Execute via alasql in-browser SQL engine
      let res;
      if (typeof alasql !== 'undefined') {
        res = alasql(query, [facts]);
      } else {
        // Fallback simple evaluator
        res = facts.slice(0, 10);
      }
      
      const elapsed = (performance.now() - startT).toFixed(2);
      execTimeSpan.textContent = `Returned ${res.length} rows in ${elapsed} ms`;

      renderSQLResults(res);
    } catch (err) {
      resultDiv.innerHTML = `<div style="color: var(--accent-rose); padding: 12px; background: rgba(244, 63, 94, 0.1); border-radius: 6px;">
        <strong>SQL Execution Error:</strong> ${escapeHtml(err.message)}
      </div>`;
      execTimeSpan.textContent = 'Error';
    }
  }

  function renderSQLResults(data) {
    if (!data || data.length === 0) {
      resultDiv.innerHTML = '<div style="padding: 16px; color: var(--text-muted);">Query returned 0 rows.</div>';
      return;
    }

    const cols = Object.keys(data[0]);
    let html = `
      <div class="table-responsive" style="max-height: 380px; overflow-y: auto;">
        <table class="data-table">
          <thead>
            <tr>${cols.map(c => `<th>${escapeHtml(c)}</th>`).join('')}</tr>
          </thead>
          <tbody>
            ${data.map(row => `
              <tr>${cols.map(c => `<td>${escapeHtml(String(row[c] !== null && row[c] !== undefined ? row[c] : 'NULL'))}</td>`).join('')}</tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
    resultDiv.innerHTML = html;
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
