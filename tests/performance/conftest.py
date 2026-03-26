"""
Pytest fixtures for performance / integration tests.

Provides:
  - ``perf_db``   — a seeded SQLite database with 10 000 students,
                    500 courses, and ~100 000 grades, scoped to the
                    test session for reuse across multiple tests.
  - ``api_client`` — a requests.Session with a valid auth token,
                    pointed at ``PERF_API_URL`` (default localhost:5000).

Environment variables:
  PERF_API_URL   — base URL of the running API (default http://localhost:5000)
  PERF_USERNAME  — username for API authentication (default Admin@College)
  PERF_PASSWORD  — password for API authentication (default Admin@College123)
"""

import os
import random
import sqlite3
import tempfile

import pytest


# ---------------------------------------------------------------------------
# perf_db fixture
# ---------------------------------------------------------------------------

def _build_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        PRAGMA cache_size=-65536;   -- 64 MB page cache

        CREATE TABLE IF NOT EXISTS students (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_ref TEXT    NOT NULL UNIQUE,
            first_name  TEXT    NOT NULL,
            last_name   TEXT    NOT NULL,
            email       TEXT,
            phone       TEXT,
            date_of_birth TEXT,
            year_group  TEXT,
            form_group  TEXT,
            status      TEXT    DEFAULT 'active',
            created_at  TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS courses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT    NOT NULL UNIQUE,
            title       TEXT    NOT NULL,
            department  TEXT,
            credits     INTEGER DEFAULT 10,
            level       TEXT    DEFAULT 'Level 3'
        );

        CREATE TABLE IF NOT EXISTS grades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            course_id   INTEGER NOT NULL REFERENCES courses(id)  ON DELETE CASCADE,
            grade       TEXT,
            percentage  REAL,
            assessment_type TEXT DEFAULT 'exam',
            recorded_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            course_id   INTEGER REFERENCES courses(id),
            date        TEXT    NOT NULL,
            status      TEXT    DEFAULT 'present',
            notes       TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_students_ref    ON students(student_ref);
        CREATE INDEX IF NOT EXISTS idx_students_status ON students(status);
        CREATE INDEX IF NOT EXISTS idx_grades_student  ON grades(student_id);
        CREATE INDEX IF NOT EXISTS idx_grades_course   ON grades(course_id);
        CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date);
    """)
    conn.commit()


def _seed(conn: sqlite3.Connection, n_students: int, n_courses: int, n_grades: int) -> None:
    """Insert seeded data in batches for speed."""
    GRADES_SCALE = ["A*", "A", "B", "C", "D", "E", "U"]
    YEAR_GROUPS = ["Year 12", "Year 13"]
    DEPARTMENTS = ["Science", "Humanities", "Arts", "Technology", "Maths", "Languages"]
    FORM_GROUPS = [f"{y}{c}" for y in ["12", "13"] for c in "ABCDEF"]
    STATUSES = ["active"] * 9 + ["inactive"]
    ATTENDANCE_STATUSES = ["present"] * 8 + ["absent", "late"]

    # Students
    batch_size = 500
    for batch_start in range(1, n_students + 1, batch_size):
        batch_end = min(batch_start + batch_size, n_students + 1)
        conn.executemany(
            """
            INSERT OR IGNORE INTO students
                (student_ref, first_name, last_name, email, phone,
                 date_of_birth, year_group, form_group, status)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    f"STU{i:07d}",
                    f"First{i % 500 + 1}",
                    f"Last{i % 1000 + 1}",
                    f"stu{i}@perf.edu",
                    f"07{i % 900000000 + 100000000}",
                    f"{1998 + (i % 8)}-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
                    YEAR_GROUPS[i % len(YEAR_GROUPS)],
                    FORM_GROUPS[i % len(FORM_GROUPS)],
                    STATUSES[i % len(STATUSES)],
                )
                for i in range(batch_start, batch_end)
            ],
        )
        conn.commit()

    # Courses
    conn.executemany(
        "INSERT OR IGNORE INTO courses (code, title, department, credits, level) VALUES (?,?,?,?,?)",
        [
            (
                f"CRS{j:04d}",
                f"Course {j}: {DEPARTMENTS[j % len(DEPARTMENTS)]} Module {j}",
                DEPARTMENTS[j % len(DEPARTMENTS)],
                (j % 4 + 1) * 10,
                f"Level {(j % 3) + 2}",
            )
            for j in range(1, n_courses + 1)
        ],
    )
    conn.commit()

    # Grades — distribute evenly
    grades_per_student = max(1, n_grades // n_students)
    grade_rows = []
    for i in range(1, n_students + 1):
        for k in range(grades_per_student):
            course_id = ((i + k) % n_courses) + 1
            grade_rows.append((
                i,
                course_id,
                GRADES_SCALE[i % len(GRADES_SCALE)],
                round(40.0 + (i % 60) + random.uniform(0, 0.99), 2),
                ["exam", "coursework", "mock"][k % 3],
            ))
        if len(grade_rows) >= batch_size:
            conn.executemany(
                "INSERT INTO grades (student_id, course_id, grade, percentage, assessment_type) "
                "VALUES (?,?,?,?,?)",
                grade_rows,
            )
            conn.commit()
            grade_rows = []

    if grade_rows:
        conn.executemany(
            "INSERT INTO grades (student_id, course_id, grade, percentage, assessment_type) "
            "VALUES (?,?,?,?,?)",
            grade_rows,
        )
        conn.commit()

    # Attendance — one entry per student per week-day in the last month
    import datetime
    today = datetime.date.today()
    dates = [
        (today - datetime.timedelta(days=d)).isoformat()
        for d in range(30)
        if (today - datetime.timedelta(days=d)).weekday() < 5
    ]
    attendance_rows = []
    for i in range(1, min(n_students + 1, 500)):  # cap to keep DB size sane
        for dt in dates:
            attendance_rows.append((
                i,
                ((i + len(dt)) % n_courses) + 1,
                dt,
                ATTENDANCE_STATUSES[i % len(ATTENDANCE_STATUSES)],
            ))
        if len(attendance_rows) >= batch_size:
            conn.executemany(
                "INSERT INTO attendance (student_id, course_id, date, status) VALUES (?,?,?,?)",
                attendance_rows,
            )
            conn.commit()
            attendance_rows = []

    if attendance_rows:
        conn.executemany(
            "INSERT INTO attendance (student_id, course_id, date, status) VALUES (?,?,?,?)",
            attendance_rows,
        )
        conn.commit()


@pytest.fixture(scope="session")
def perf_db():
    """
    Session-scoped SQLite database seeded with:
      - 10 000 students
      - 500 courses
      - ~100 000 grades  (10 grades per student)

    Returns the file path so tests can open their own connections.
    The database file is removed after the test session.
    """
    fd, path = tempfile.mkstemp(suffix=".db", prefix="perf_test_")
    os.close(fd)

    conn = sqlite3.connect(path)
    _build_schema(conn)
    _seed(conn, n_students=10_000, n_courses=500, n_grades=100_000)
    conn.close()

    yield path

    try:
        os.unlink(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# api_client fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def api_client():
    """
    Session-scoped requests.Session pre-authenticated against the API.

    Skips automatically if the server is not reachable so that performance
    tests do not block the normal unit-test suite.

    Usage::

        def test_list_students(api_client):
            resp = api_client.get("/api/students")
            assert resp.status_code == 200
    """
    try:
        import requests
    except ImportError:
        pytest.skip("requests not installed")

    base_url = os.environ.get("PERF_API_URL", "http://localhost:5000")
    username = os.environ.get("PERF_USERNAME", "Admin@College")
    password = os.environ.get("PERF_PASSWORD", "Admin@College123")

    # Check server reachability before attempting login
    try:
        resp = requests.get(f"{base_url}/api/health", timeout=3)
    except Exception:
        pytest.skip(f"API server not reachable at {base_url} — skipping performance tests")

    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
    })

    # Login
    try:
        login_resp = session.post(
            f"{base_url}/api/auth/login",
            json={"username": username, "password": password},
            timeout=10,
        )
        if login_resp.status_code == 200:
            data = login_resp.json()
            token = data.get("access_token") or data.get("token", "")
            if token:
                session.headers["Authorization"] = f"Bearer {token}"
    except Exception as exc:
        pytest.skip(f"Could not authenticate against {base_url}: {exc}")

    # Attach base_url to the session for convenience
    session.base_url = base_url  # type: ignore[attr-defined]

    # Wrap get/post/put/delete to prepend base_url if path starts with /
    _orig_request = session.request

    def _request(method, url, **kwargs):
        if url.startswith("/"):
            url = base_url + url
        return _orig_request(method, url, **kwargs)

    session.request = _request  # type: ignore[method-assign]

    yield session
    session.close()
