#!/usr/bin/env python3
"""
SQLite performance benchmark for the Education Management System.

Runs a suite of micro-benchmarks covering:
  - Concurrent reads (multiple threads reading simultaneously)
  - Concurrent writes (multiple threads inserting simultaneously)
  - WAL-mode vs default journal performance
  - Large result-set queries
  - Index effectiveness (sequential scan vs indexed lookup)

No external dependencies required beyond the Python standard library.

Usage:
    /home/seancatchpole989/venv/bin/python tests/performance/benchmark_db.py
    # or via Makefile:
    make perf-test
"""

import sqlite3
import threading
import time
import tempfile
import os
import statistics
from typing import Callable


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------

COL_WIDTHS = (38, 12, 12, 12, 14, 10)
HEADERS = ("Benchmark", "Min (ms)", "Avg (ms)", "Max (ms)", "p95 (ms)", "Status")


def _sep(char: str = "-") -> str:
    return "+-" + "-+-".join(char * w for w in COL_WIDTHS) + "-+"


def _row(*cols) -> str:
    return "| " + " | ".join(str(c).ljust(w) for c, w in zip(cols, COL_WIDTHS)) + " |"


def _print_table(rows: list[tuple]) -> None:
    print(_sep())
    print(_row(*HEADERS))
    print(_sep("="))
    for row in rows:
        print(_row(*row))
    print(_sep())


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def _timeit(fn: Callable, iterations: int = 50) -> dict:
    """Run *fn* *iterations* times and return latency statistics (ms)."""
    samples: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)

    samples.sort()
    p95_idx = max(0, int(len(samples) * 0.95) - 1)
    return {
        "min": samples[0],
        "avg": statistics.mean(samples),
        "max": samples[-1],
        "p95": samples[p95_idx],
    }


def _fmt(val: float) -> str:
    return f"{val:.2f}"


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_ref TEXT    NOT NULL UNIQUE,
            first_name  TEXT    NOT NULL,
            last_name   TEXT    NOT NULL,
            email       TEXT,
            year_group  TEXT,
            status      TEXT    DEFAULT 'active',
            created_at  TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS courses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT    NOT NULL UNIQUE,
            title       TEXT    NOT NULL,
            credits     INTEGER DEFAULT 10
        );

        CREATE TABLE IF NOT EXISTS grades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  INTEGER NOT NULL REFERENCES students(id),
            course_id   INTEGER NOT NULL REFERENCES courses(id),
            grade       TEXT,
            percentage  REAL,
            created_at  TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()


def _seed_data(conn: sqlite3.Connection, n_students: int = 1000) -> None:
    """Insert *n_students* rows and proportional courses + grades."""
    n_courses = max(20, n_students // 10)

    conn.executemany(
        "INSERT OR IGNORE INTO students (student_ref, first_name, last_name, email, year_group, status) "
        "VALUES (?,?,?,?,?,?)",
        [
            (
                f"STU{i:06d}",
                f"First{i}",
                f"Last{i}",
                f"student{i}@example.edu",
                f"Year {(i % 2) + 12}",
                "active" if i % 10 != 0 else "inactive",
            )
            for i in range(1, n_students + 1)
        ],
    )

    conn.executemany(
        "INSERT OR IGNORE INTO courses (code, title, credits) VALUES (?,?,?)",
        [(f"CRS{j:04d}", f"Course Title {j}", (j % 3 + 1) * 10) for j in range(1, n_courses + 1)],
    )

    grades_data = []
    for i in range(1, n_students + 1):
        for j in range(1, min(6, n_courses + 1)):  # each student takes up to 5 courses
            grades_data.append((i, j, ["A*", "A", "B", "C", "D"][i % 5], 55.0 + (i % 45)))

    conn.executemany(
        "INSERT INTO grades (student_id, course_id, grade, percentage) VALUES (?,?,?,?)",
        grades_data,
    )
    conn.commit()


def _make_db(wal: bool = False, n_students: int = 1000) -> str:
    """Create a temp SQLite database and return its path."""
    fd, path = tempfile.mkstemp(suffix=".db", prefix="bench_")
    os.close(fd)

    conn = sqlite3.connect(path)
    if wal:
        conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    _create_schema(conn)
    _seed_data(conn, n_students)
    conn.close()
    return path


# ---------------------------------------------------------------------------
# Individual benchmarks
# ---------------------------------------------------------------------------

def bench_single_read(db_path: str) -> dict:
    """Single-threaded sequential SELECT by primary key."""
    def _run():
        conn = sqlite3.connect(db_path)
        conn.execute("SELECT * FROM students WHERE id = ?", (1,)).fetchone()
        conn.close()

    return _timeit(_run, iterations=200)


def bench_large_result_set(db_path: str) -> dict:
    """SELECT all students — tests result materialisation overhead."""
    def _run():
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT * FROM students ORDER BY last_name").fetchall()
        conn.close()
        return rows

    return _timeit(_run, iterations=50)


def bench_index_lookup(db_path: str) -> dict:
    """SELECT using an indexed column (student_ref UNIQUE index)."""
    # Ensure index exists
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_students_ref ON students(student_ref)")
    conn.commit()
    conn.close()

    def _run():
        conn = sqlite3.connect(db_path)
        conn.execute("SELECT * FROM students WHERE student_ref = ?", ("STU000100",)).fetchone()
        conn.close()

    return _timeit(_run, iterations=200)


def bench_sequential_scan(db_path: str) -> dict:
    """SELECT using a non-indexed column to force a full table scan."""
    def _run():
        conn = sqlite3.connect(db_path)
        conn.execute(
            "SELECT * FROM students WHERE email = ?", ("student100@example.edu",)
        ).fetchone()
        conn.close()

    return _timeit(_run, iterations=100)


def bench_aggregate_query(db_path: str) -> dict:
    """GROUP BY aggregation — typical dashboard/report query."""
    def _run():
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            SELECT s.year_group, COUNT(g.id) AS total_grades, AVG(g.percentage) AS avg_pct
            FROM students s
            JOIN grades g ON g.student_id = s.id
            GROUP BY s.year_group
            """
        ).fetchall()
        conn.close()

    return _timeit(_run, iterations=100)


def bench_concurrent_reads(db_path: str, n_threads: int = 8) -> dict:
    """N threads all reading simultaneously — tests SQLite read concurrency."""
    results: list[float] = []
    lock = threading.Lock()

    def _worker():
        for _ in range(25):
            t0 = time.perf_counter()
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.execute("SELECT * FROM students LIMIT 50").fetchall()
            conn.close()
            elapsed = (time.perf_counter() - t0) * 1000
            with lock:
                results.append(elapsed)

    threads = [threading.Thread(target=_worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    results.sort()
    p95_idx = max(0, int(len(results) * 0.95) - 1)
    return {
        "min": min(results),
        "avg": statistics.mean(results),
        "max": max(results),
        "p95": results[p95_idx],
    }


def bench_concurrent_writes(db_path: str, n_threads: int = 4) -> dict:
    """N threads writing concurrently — tests WAL/lock contention."""
    results: list[float] = []
    lock = threading.Lock()
    counter = [0]

    def _worker():
        for _ in range(20):
            t0 = time.perf_counter()
            conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10)
            with lock:
                counter[0] += 1
                idx = counter[0]
            try:
                conn.execute(
                    "INSERT INTO students (student_ref, first_name, last_name) VALUES (?,?,?)",
                    (f"TMP{idx:08d}", f"TFirst{idx}", f"TLast{idx}"),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                pass
            finally:
                conn.close()
            elapsed = (time.perf_counter() - t0) * 1000
            with lock:
                results.append(elapsed)

    threads = [threading.Thread(target=_worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    results.sort()
    p95_idx = max(0, int(len(results) * 0.95) - 1)
    return {
        "min": min(results),
        "avg": statistics.mean(results),
        "max": max(results),
        "p95": results[p95_idx],
    }


def bench_wal_vs_default_write(wal: bool) -> dict:
    """Compare WAL-mode vs default (DELETE) journal for sequential writes."""
    db_path = _make_db(wal=wal, n_students=200)

    def _run():
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO students (student_ref, first_name, last_name) VALUES (?,?,?)",
            (f"W{time.time_ns()}", "WFirst", "WLast"),
        )
        conn.commit()
        conn.close()

    result = _timeit(_run, iterations=100)
    os.unlink(db_path)
    return result


# ---------------------------------------------------------------------------
# Thresholds — warn if exceeded
# ---------------------------------------------------------------------------

THRESHOLDS_P95_MS = {
    "Single read (pk lookup)":         5.0,
    "Index lookup (student_ref)":      5.0,
    "Sequential scan (full table)":   50.0,
    "Large result set (all students)":100.0,
    "Aggregate / GROUP BY query":      50.0,
    "Concurrent reads (8 threads)":    20.0,
    "Concurrent writes (4 threads)":  200.0,
    "WAL write (sequential)":          10.0,
    "Default journal write (seq.)":    20.0,
}


def _status(name: str, p95: float) -> str:
    threshold = THRESHOLDS_P95_MS.get(name)
    if threshold is None:
        return "N/A"
    return "PASS" if p95 <= threshold else f"SLOW>{threshold:.0f}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print()
    print("Education System — SQLite Performance Benchmark")
    print(f"Python sqlite3 version: {sqlite3.sqlite_version}")
    print()

    print("Building benchmark database (1 000 students)…")
    db_default = _make_db(wal=False, n_students=1000)
    db_wal = _make_db(wal=True, n_students=1000)
    print("Done.\n")

    benchmarks: list[tuple[str, dict]] = [
        ("Single read (pk lookup)",        bench_single_read(db_default)),
        ("Index lookup (student_ref)",     bench_index_lookup(db_default)),
        ("Sequential scan (full table)",   bench_sequential_scan(db_default)),
        ("Large result set (all students)",bench_large_result_set(db_default)),
        ("Aggregate / GROUP BY query",     bench_aggregate_query(db_default)),
        ("Concurrent reads (8 threads)",   bench_concurrent_reads(db_default, n_threads=8)),
        ("Concurrent writes (4 threads)",  bench_concurrent_writes(db_wal, n_threads=4)),
        ("WAL write (sequential)",         bench_wal_vs_default_write(wal=True)),
        ("Default journal write (seq.)",   bench_wal_vs_default_write(wal=False)),
    ]

    rows = []
    any_slow = False
    for name, stats in benchmarks:
        p95 = stats["p95"]
        status = _status(name, p95)
        if "SLOW" in status:
            any_slow = True
        rows.append((
            name,
            _fmt(stats["min"]),
            _fmt(stats["avg"]),
            _fmt(stats["max"]),
            _fmt(p95),
            status,
        ))

    _print_table(rows)
    print()

    if any_slow:
        print("WARNING: one or more benchmarks exceeded their p95 threshold.")
        print("Consider adding indexes, enabling WAL mode, or reviewing query plans.")
    else:
        print("All benchmarks within expected thresholds.")

    # Cleanup temp files
    try:
        os.unlink(db_default)
        os.unlink(db_wal)
    except OSError:
        pass

    return 1 if any_slow else 0


if __name__ == "__main__":
    raise SystemExit(main())
