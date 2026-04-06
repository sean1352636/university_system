# Performance & Load Testing

This directory contains load tests (Locust) and standalone benchmarks for the
Education Management System's Flask APIs and SQLite data layer.

---

## Prerequisites

1. **Install Locust** (included in `requirements.txt`):
   ```bash
   pip install locust>=2.20.0
   # or via the project venv:
   make install
   ```

2. **Start the API server** before running any Locust scenario:
   ```bash
   make run-api        # college API on http://localhost:5000
   # or start a specific system:
   python -m education_system.shared.api.college.api_server
   ```
   The server must be reachable at the `--host` you supply to Locust.

3. **Seed demo data** so the database has realistic content:
   ```bash
   make seed
   ```

---

## How to Run

### Headless (CI / scripted)
```bash
make load-test
# Equivalent to:
locust -f tests/performance/locustfile.py \
       --headless -u 50 -r 5 --run-time 60s \
       --host http://localhost:5000
```

### Interactive Web UI
```bash
make load-test-ui
# Then open http://localhost:8089 to start/stop the swarm interactively.
```

### SQLite standalone benchmark (no server required)
```bash
make perf-test
# Equivalent to:
python tests/performance/benchmark_db.py
```

### Run a single scenario
```bash
locust -f tests/performance/scenarios/auth_scenario.py \
       --headless -u 20 -r 2 --run-time 30s \
       --host http://localhost:5000

locust -f tests/performance/scenarios/crud_scenario.py \
       --headless -u 10 -r 1 --run-time 60s \
       --host http://localhost:5000

locust -f tests/performance/scenarios/dashboard_scenario.py \
       --headless -u 30 -r 5 --run-time 60s \
       --host http://localhost:5000
```

---

## Interpreting Results

Locust prints a summary table when a headless run finishes:

```
Name                     # reqs  # fails  |  Avg   Min   Max  Med  |  req/s  failures/s
----------------------------------------------------------------------------------------------
GET /api/health              600       0  |   12     8    95   11  |  10.0     0.00
GET /api/students            300       2  |  148    45   890  130  |   5.0     0.03
...
```

Key columns:

| Column      | What it means                                              |
|-------------|-------------------------------------------------------------|
| `# reqs`    | Total requests sent during the run                          |
| `# fails`   | Non-2xx responses (or network errors)                       |
| `Avg`       | Mean response time in milliseconds                          |
| `Med`       | Median (p50) — half of requests faster than this           |
| `req/s`     | Throughput                                                  |
| `failures/s`| Error rate — should be 0 under normal load                 |

Locust also writes a CSV stats file when you pass `--csv=results/run`.

---

## Baseline Thresholds

The following targets define acceptable performance under a 50-user concurrent
load with a 5 users/s ramp-up:

| Endpoint category              | p50 target | p95 target  | p99 target  |
|--------------------------------|-----------|-------------|-------------|
| Dashboard data (`/api/dashboard-*`) | <200 ms | **<500 ms** | <1 000 ms  |
| API CRUD (students, courses, grades) | <100 ms | **<200 ms** | <500 ms   |
| Reports / exports              | <500 ms   | **<1 000 ms**| <2 000 ms  |
| Auth (login / token check)     | <100 ms   | **<250 ms** | <500 ms    |
| Health check                   | <50 ms    | **<100 ms** | <200 ms    |

**Error rate** must stay below **0.5 %** for all endpoint categories.

### CI gate (`.github/workflows/performance.yml`)

The automated weekly run uses 10 users for 30 seconds.  The workflow fails if
the p95 of *any* sampled endpoint exceeds **2 000 ms**.

---

## Output Artefacts

- `results/locust_stats.csv` — per-endpoint request statistics
- `results/locust_stats_history.csv` — time-series throughput / latency
- `results/locust_failures.csv` — details of each failed request
- `results/benchmark_db.txt` — SQLite benchmark table (from `benchmark_db.py`)

These files are uploaded as GitHub Actions artefacts on every CI performance
run and retained for 30 days.
