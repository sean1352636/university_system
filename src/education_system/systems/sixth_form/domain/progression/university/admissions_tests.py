"""University admissions tests — UCAT, LNAT, TMUA, MAT, PAT, ESAT and the rest.

Many competitive courses require a separate admissions test, each with
its own registration window, test date and score, and nothing in the
UCAS package recorded any of it: a learner applying for medicine could
reach the October deadline with no UCAT booked and nobody would know.

Two tables:

* ``ucas_admissions_test_types`` — the **configurable list** of tests.
  Seeded on first use with the tests in current use, but staff add,
  rename or retire tests here rather than in code, because the line-up
  changes: BMAT was withdrawn after the 2024 cycle and its courses moved
  to UCAT, ESAT and TARA, and Oxford changed its own tests at the same
  time. Each type carries course/university keywords used to *suggest*
  it for an application.
* ``ucas_admissions_tests`` — one row per learner per test per cycle:
  registration deadline, whether and when booked, booking reference,
  test date and centre, score and when it arrived, and reasonable
  adjustments (what was requested and whether it was approved).

Cascade: deleting a student removes their test entries.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from education_system.systems.sixth_form.infrastructure import database as _sql
from dataclasses import dataclass
from typing import Any

from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_UCAS_DB

#: Seed rows: (code, name, course keywords, university keywords, notes).
#: Keywords are comma-separated, matched case-insensitively against a
#: choice's course name / university. Editable once seeded; the dates and
#: the universities using each test change every cycle.
DEFAULT_TEST_TYPES: tuple[tuple[str, str, str, str, str], ...] = (
    ("UCAT", "University Clinical Aptitude Test",
     "medicine,dentistry,graduate medicine", "",
     "Most UK medical and dental schools. Register in early summer of Year 12; "
     "test window July–September. Bursaries available for eligible students."),
    ("LNAT", "National Admissions Test for Law", "law,jurisprudence",
     "oxford,cambridge,durham,bristol,king's college,london school of economics,"
     "nottingham,university college london,glasgow,soas",
     "Book early: Oxford/Cambridge applicants must test before mid-October."),
    ("TMUA", "Test of Mathematics for University Admission",
     "mathematics,computer science,economics", "cambridge,imperial,lse,warwick,durham,"
     "london school of economics,bath,lancaster,nottingham,southampton,surrey",
     "Run by UAT-UK; two sittings (October and January)."),
    ("MAT", "Mathematics Admissions Test", "mathematics,computer science",
     "oxford,imperial,warwick", "Oxford maths and computer science courses."),
    ("PAT", "Physics Aptitude Test", "physics,engineering,materials science",
     "oxford", "Oxford physics, engineering and materials."),
    ("ESAT", "Engineering and Science Admissions Test",
     "engineering,natural sciences,chemistry,physics,veterinary medicine,chemical engineering",
     "cambridge,imperial,university college london",
     "Successor to BMAT/NSAA/ENGAA for science and engineering. Two sittings."),
    ("TARA", "Test of Academic Reasoning for Admissions",
     "economics,european social and political studies,psychology,biochemical engineering",
     "university college london,cambridge",
     "Run by UAT-UK alongside ESAT and TMUA."),
    ("TSA", "Thinking Skills Assessment",
     "politics and economics,economics and management,"
     "experimental psychology,human sciences,land economy",
     "oxford,cambridge,university college london",
     "Check which courses still require it this cycle."),
    ("STEP", "Sixth Term Examination Paper", "mathematics",
     "cambridge,warwick,imperial",
     "Taken in June after offers; usually part of the offer conditions."),
)

ENTRY_STATUSES: tuple[str, ...] = (
    "Not registered", "Registered", "Booked", "Sat", "Result received",
    "Withdrawn",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ucas_admissions_test_types (
    code                 TEXT PRIMARY KEY,
    name                 TEXT NOT NULL,
    course_keywords      TEXT,
    university_keywords  TEXT,
    notes                TEXT,
    active               INTEGER NOT NULL DEFAULT 1,
    updated_at           TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ucas_admissions_tests (
    entry_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id               TEXT NOT NULL,
    cycle_year               INTEGER NOT NULL,
    test_code                TEXT NOT NULL,
    registration_deadline    TEXT,
    registered_on            TEXT,
    booked                   INTEGER NOT NULL DEFAULT 0,
    booking_ref              TEXT,
    test_date                TEXT,
    test_centre              TEXT,
    score                    TEXT,
    result_date              TEXT,
    adjustments_requested    TEXT,
    adjustments_approved     INTEGER NOT NULL DEFAULT 0,
    bursary_or_fee_waiver    INTEGER NOT NULL DEFAULT 0,
    status                   TEXT NOT NULL DEFAULT 'Not registered',
    notes                    TEXT,
    created_at               TEXT DEFAULT (datetime('now')),
    updated_at               TEXT DEFAULT (datetime('now')),
    UNIQUE (student_id, cycle_year, test_code),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (test_code) REFERENCES ucas_admissions_test_types(code)
        ON UPDATE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_adm_tests_student ON ucas_admissions_tests(student_id);
CREATE INDEX IF NOT EXISTS idx_adm_tests_dates   ON ucas_admissions_tests(registration_deadline, test_date);
"""


class ValidationError(ValueError):
    """Raised for invalid admissions-test input."""


def _connect() -> _sql.Connection:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY = False


def init_db() -> None:
    """Create the tables and seed the default test list (once, ever: a
    seeded code that staff later delete stays deleted because the seed
    only inserts into an empty table)."""
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM ucas_admissions_test_types").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO ucas_admissions_test_types "
                "(code, name, course_keywords, university_keywords, notes) "
                "VALUES (?, ?, ?, ?, ?)", DEFAULT_TEST_TYPES)
        conn.commit()
    _DB_READY = True
    logger.debug("Admissions-tests schema ready at %s", DB_PATH)


def _date(value: Any, label: str) -> str | None:
    s = (str(value).strip() if value is not None else "")
    if not s:
        return None
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _text(value: Any) -> str | None:
    return (str(value).strip() if value is not None else "") or None


def _bool(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    return 1 if str(value or "").strip().lower() in ("1", "y", "yes", "true", "t") else 0


# ── Test types (the configurable list) ──────────────────────────────

def list_test_types(*, include_inactive: bool = False) -> list[dict[str, Any]]:
    init_db()
    where = "" if include_inactive else "WHERE active = 1"
    with _connect() as conn:
        return [dict(r) for r in conn.execute(
            f"SELECT * FROM ucas_admissions_test_types {where} ORDER BY code")]


def test_codes() -> list[str]:
    return [t["code"] for t in list_test_types()]


def save_test_type(data: dict[str, Any]) -> dict[str, Any]:
    """Add or update a test type, keyed on its code."""
    init_db()
    code = (_text(data.get("code")) or "").upper()
    name = _text(data.get("name"))
    if not code or not re.match(r"^[A-Z0-9][A-Z0-9_-]{0,15}$", code):
        raise ValidationError("Code must be 1-16 letters/digits (e.g. UCAT)")
    if not name:
        raise ValidationError("Name is required")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO ucas_admissions_test_types
                   (code, name, course_keywords, university_keywords, notes, active, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(code) DO UPDATE SET name=excluded.name,
                   course_keywords=excluded.course_keywords,
                   university_keywords=excluded.university_keywords,
                   notes=excluded.notes, active=excluded.active,
                   updated_at=datetime('now')""",
            (code, name, _text(data.get("course_keywords")),
             _text(data.get("university_keywords")), _text(data.get("notes")),
             _bool(data.get("active", True))))
        conn.commit()
        return dict(conn.execute("SELECT * FROM ucas_admissions_test_types WHERE code=?",
                                 (code,)).fetchone())


def retire_test_type(code: str) -> None:
    """Hide a test from new entries; existing entries keep their history."""
    init_db()
    with _connect() as conn:
        conn.execute("UPDATE ucas_admissions_test_types SET active=0, "
                     "updated_at=datetime('now') WHERE code=?", (code,))
        conn.commit()


# ── Entries ─────────────────────────────────────────────────────────

def _derive_status(p: dict[str, Any], today: _dt.date) -> str:
    if p.get("status") == "Withdrawn":
        return "Withdrawn"
    if p.get("score"):
        return "Result received"
    if p.get("test_date") and p["test_date"] < today.isoformat() and p.get("booked"):
        return "Sat"
    if p.get("booked"):
        return "Booked"
    if p.get("registered_on"):
        return "Registered"
    return "Not registered"


def _validate_entry(data: dict[str, Any]) -> dict[str, Any]:
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    sid = _text(data.get("student_id"))
    if not sid or _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    code = (_text(data.get("test_code")) or "").upper()
    known = {t["code"] for t in list_test_types(include_inactive=True)}
    if code not in known:
        raise ValidationError(f"Unknown test '{code}' — add it to the test list first")
    try:
        cycle = int(data.get("cycle_year"))
    except (TypeError, ValueError):
        raise ValidationError("Cycle year is required") from None
    p = {
        "student_id": sid, "test_code": code, "cycle_year": cycle,
        "registration_deadline": _date(data.get("registration_deadline"), "Registration deadline"),
        "registered_on": _date(data.get("registered_on"), "Registered on"),
        "booked": _bool(data.get("booked")),
        "booking_ref": _text(data.get("booking_ref")),
        "test_date": _date(data.get("test_date"), "Test date"),
        "test_centre": _text(data.get("test_centre")),
        "score": _text(data.get("score")),
        "result_date": _date(data.get("result_date"), "Result date"),
        "adjustments_requested": _text(data.get("adjustments_requested")),
        "adjustments_approved": _bool(data.get("adjustments_approved")),
        "bursary_or_fee_waiver": _bool(data.get("bursary_or_fee_waiver")),
        "notes": _text(data.get("notes")),
        "status": _text(data.get("status")),
    }
    if p["booked"] and not p["test_date"]:
        raise ValidationError("A booked test needs its test date")
    if p["adjustments_approved"] and not p["adjustments_requested"]:
        raise ValidationError("Say which reasonable adjustments were approved")
    if p["status"] and p["status"] not in ENTRY_STATUSES:
        raise ValidationError(f"Status must be one of: {', '.join(ENTRY_STATUSES)}")
    p["status"] = _derive_status(p, _dt.date.today())
    return p


_COLS = ("registration_deadline", "registered_on", "booked", "booking_ref",
         "test_date", "test_centre", "score", "result_date",
         "adjustments_requested", "adjustments_approved",
         "bursary_or_fee_waiver", "status", "notes")


def get_entry(entry_id: int) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM ucas_admissions_tests WHERE entry_id=?",
                         (entry_id,)).fetchone()
    return dict(r) if r else None


def create_entry(data: dict[str, Any]) -> dict[str, Any]:
    init_db()
    p = _validate_entry(data)
    try:
        with _connect() as conn:
            cur = conn.execute(
                f"""INSERT INTO ucas_admissions_tests
                        (student_id, cycle_year, test_code, {', '.join(_COLS)})
                    VALUES (?, ?, ?, {', '.join('?' for _ in _COLS)})""",
                (p["student_id"], p["cycle_year"], p["test_code"],
                 *[p[c] for c in _COLS]))
            conn.commit()
            new_id = cur.lastrowid
    except _sql.IntegrityError as e:
        if "UNIQUE" in str(e):
            raise ValidationError(
                f"{p['student_id']} already has a {p['test_code']} entry for "
                f"cycle {p['cycle_year']}") from None
        raise
    logger.info("Admissions test %s recorded for %s (cycle %d)",
                p["test_code"], p["student_id"], p["cycle_year"])
    out = get_entry(new_id)
    assert out is not None
    return out


def update_entry(entry_id: int, data: dict[str, Any]) -> dict[str, Any]:
    init_db()
    existing = get_entry(entry_id)
    if existing is None:
        raise ValidationError(f"No test entry with id {entry_id}")
    merged = {**existing, **{k: v for k, v in data.items() if k in _COLS + ("test_code",)}}
    p = _validate_entry(merged)
    with _connect() as conn:
        conn.execute(
            f"""UPDATE ucas_admissions_tests SET test_code=?,
                    {', '.join(f'{c}=?' for c in _COLS)}, updated_at=datetime('now')
                WHERE entry_id=?""",
            (p["test_code"], *[p[c] for c in _COLS], entry_id))
        conn.commit()
    out = get_entry(entry_id)
    assert out is not None
    return out


def delete_entry(entry_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM ucas_admissions_tests WHERE entry_id=?", (entry_id,))
        conn.commit()
    return bool(cur.rowcount)


def list_entries(*, student_id: str | None = None, cycle_year: int | None = None,
                 test_code: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    init_db()
    clauses, args = [], []
    for col, val in (("t.student_id", student_id), ("t.cycle_year", cycle_year),
                     ("t.test_code", test_code), ("t.status", status)):
        if val not in (None, ""):
            clauses.append(f"{col} = ?"); args.append(val)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [dict(r) for r in conn.execute(
            f"""SELECT t.*, s.first_name || ' ' || s.last_name AS student_name
                  FROM ucas_admissions_tests t
                  LEFT JOIN students s ON s.student_id = t.student_id
                  {where}
                 ORDER BY COALESCE(t.test_date, t.registration_deadline, '9999'),
                          s.last_name""", args)]


# ── Alerts and suggestions ──────────────────────────────────────────

def registration_alerts(*, cycle_year: int | None = None, within_days: int = 21,
                        today: _dt.date | None = None) -> list[dict[str, Any]]:
    """Entries not yet booked whose registration deadline is within
    *within_days* or already gone — the ones that need chasing."""
    today = today or _dt.date.today()
    cutoff = (today + _dt.timedelta(days=within_days)).isoformat()
    out = []
    for e in list_entries(cycle_year=cycle_year):
        if e["booked"] or e["status"] == "Withdrawn" or not e["registration_deadline"]:
            continue
        if e["registration_deadline"] <= cutoff:
            e["alert"] = ("Registration deadline passed"
                          if e["registration_deadline"] < today.isoformat()
                          else "Registration closes soon")
            out.append(e)
    return out


def upcoming_tests(*, within_days: int = 30,
                   today: _dt.date | None = None) -> list[dict[str, Any]]:
    today = today or _dt.date.today()
    lo, hi = today.isoformat(), (today + _dt.timedelta(days=within_days)).isoformat()
    return [e for e in list_entries() if e["booked"] and e["test_date"]
            and lo <= e["test_date"] <= hi and not e["score"]]


def _split(keywords: str | None) -> list[str]:
    return [k.strip().lower() for k in (keywords or "").split(",") if k.strip()]


def suggested_tests(application_id: int) -> list[dict[str, Any]]:
    """Tests the application's choices point at that the learner has no
    entry for. A prompt for staff, not a rule: the keyword lists are the
    configurable test types' and universities change requirements."""
    init_db()
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    app = _ucas.get_application(application_id)
    if app is None:
        raise ValidationError(f"No application with id {application_id}")
    have = {e["test_code"] for e in list_entries(student_id=app.student_id,
                                                cycle_year=app.cycle_year)}
    out = []
    for t in list_test_types():
        if t["code"] in have:
            continue
        courses, unis = _split(t["course_keywords"]), _split(t["university_keywords"])
        for c in _ucas.list_choices(application_id):
            course = (c.course_name or "").lower()
            uni = (c.university or "").lower()
            if any(k in course for k in courses) and (not unis or any(u in uni for u in unis)):
                out.append({"test_code": t["code"], "name": t["name"],
                            "because": f"choice {c.choice_order}: {c.university} — {c.course_name}"})
                break
    return out


__all__ = [
    "DEFAULT_TEST_TYPES", "ENTRY_STATUSES", "ValidationError",
    "list_test_types", "test_codes", "save_test_type", "retire_test_type",
    "get_entry", "create_entry", "update_entry", "delete_entry", "list_entries",
    "registration_alerts", "upcoming_tests", "suggested_tests",
]
