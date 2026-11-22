"""Gatsby benchmark coverage per student, with the evidence behind it.

``careers.py`` lets a session be tagged to one of the eight Gatsby
benchmarks, which answers "what does the careers programme offer". It
could not answer the question the benchmarks actually ask of a college —
*has each learner had* an employer encounter, a workplace experience, an
encounter with further and higher education, a personal guidance
interview with a qualified adviser — because nothing tied the evidence
to the learner and nothing said whether it was enough.

This module does, drawing on four sources so nothing is typed twice:

* **careers sessions** (``career_sessions``) that are Completed and tagged
  to a benchmark — now optionally linked to an **employer** (Benchmark 5),
  an FE/HE **provider** (Benchmark 7), and flagged as delivered by a
  **level 6 qualified adviser** (Benchmark 8 counts only those);
* **work-experience placements** (``we_placements``) in progress or
  completed — Benchmark 6, linked to their employer;
* **university visits** attended (``university_visit_attendees``) —
  Benchmark 7;
* **manual evidence** (``gatsby_evidence``) for anything else: an
  assembly talk by an employer, a college fair, a guidance meeting
  recorded elsewhere.

The **employer directory** is the work-experience one (``we_employers``):
one list of employers the college works with, whether they host a
placement, give a talk or run a mock interview. Encounters link to it.

Cascade: deleting a student removes their evidence rows; deleting an
employer clears the link on encounters rather than deleting them.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from education_system.systems.sixth_form.infrastructure import database as _sql
from dataclasses import dataclass, field
from typing import Any

from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_CAREERS_DB

#: Evidence needed for a learner to count as having met each benchmark.
#: Benchmarks 5–8 follow the Gatsby/Careers & Enterprise Company 16-18
#: expectations as published (an employer encounter each year, a
#: workplace experience, two encounters with FE/HE providers for those
#: considering it, a personal guidance interview with a level 6 adviser).
#: Benchmarks 1–4 are mainly about the programme, so one piece of tagged
#: evidence counts. CHECK AGAINST THE CURRENT GATSBY GUIDANCE (the
#: benchmarks were refreshed in 2025) and adjust here.
THRESHOLDS: dict[int, int] = {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 2, 8: 1}

EVIDENCE_KINDS: tuple[str, ...] = (
    "Employer encounter", "Workplace experience", "FE/HE encounter",
    "Personal guidance", "Labour market information", "Curriculum link",
    "Programme activity", "Other",
)
#: The benchmark each kind of evidence normally supports (pre-fills the form).
KIND_BENCHMARK: dict[str, int] = {
    "Employer encounter": 5, "Workplace experience": 6, "FE/HE encounter": 7,
    "Personal guidance": 8, "Labour market information": 2,
    "Curriculum link": 4, "Programme activity": 1,
}

COHORTS: tuple[str, ...] = ("Year 12", "Year 13", "All active")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SESSION_COLUMNS: tuple[tuple[str, str], ...] = (
    ("employer_id", "INTEGER REFERENCES we_employers(employer_id) ON DELETE SET NULL"),
    ("provider", "TEXT"),
    ("adviser_level6", "INTEGER NOT NULL DEFAULT 0"),
    ("evidence", "TEXT"),
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gatsby_evidence (
    evidence_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     TEXT NOT NULL,
    benchmark      INTEGER NOT NULL CHECK (benchmark BETWEEN 1 AND 8),
    kind           TEXT NOT NULL,
    evidence_date  TEXT NOT NULL,
    description    TEXT NOT NULL,
    employer_id    INTEGER,
    provider       TEXT,
    adviser_level6 INTEGER NOT NULL DEFAULT 0,
    recorded_by    TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (employer_id) REFERENCES we_employers(employer_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_gatsby_ev_student ON gatsby_evidence(student_id, benchmark);
CREATE INDEX IF NOT EXISTS idx_gatsby_ev_employer ON gatsby_evidence(employer_id);
"""


class ValidationError(ValueError):
    """Raised for invalid Gatsby evidence input."""


def _connect() -> _sql.Connection:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.progression.careers import careers as _careers
    from education_system.systems.sixth_form.domain.progression.work_experience import (
        work_experience as _we,
    )
    _careers.init_db()
    _we.init_db()          # we_employers must exist before anything references it
    with _connect() as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(career_sessions)")}
        for col, ddl in _SESSION_COLUMNS:
            if col not in cols:
                conn.execute(f"ALTER TABLE career_sessions ADD COLUMN {col} {ddl}")
        conn.executescript(_SCHEMA)
        conn.commit()
    _DB_READY = True
    logger.debug("Gatsby coverage schema ready at %s", DB_PATH)


def _table_exists(conn: _sql.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (name,)).fetchone() is not None


def _date(value: Any, label: str, *, required: bool = False) -> str | None:
    s = (str(value).strip() if value is not None else "")
    if not s:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _employer_id(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        emp = int(value)
    except (TypeError, ValueError):
        raise ValidationError("Employer id must be a number") from None
    from education_system.systems.sixth_form.domain.progression.work_experience import (
        work_experience as _we,
    )
    if _we.get_employer(emp) is None:
        raise ValidationError(f"No employer with id {emp}")
    return emp


def _bool(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    return 1 if str(value or "").strip().lower() in ("1", "y", "yes", "true", "t") else 0


def current_academic_year(today: _dt.date | None = None) -> tuple[str, str]:
    """``(from, to)`` ISO dates of the academic year containing *today*."""
    today = today or _dt.date.today()
    start = today.year if today.month >= 9 else today.year - 1
    return f"{start}-09-01", f"{start + 1}-08-31"


# ── Session links ───────────────────────────────────────────────────

def get_session_links(session_id: int) -> dict[str, Any]:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT employer_id, provider, adviser_level6, evidence FROM career_sessions "
            "WHERE session_id=?", (session_id,)).fetchone()
    if r is None:
        raise ValidationError(f"No session with id {session_id}")
    return dict(r)


def session_links_map(student_id: str | None = None) -> dict[int, dict[str, Any]]:
    """``session_id -> links`` (with ``employer_name``) in one query."""
    init_db()
    sql = ("SELECT s.session_id, s.employer_id, s.provider, s.adviser_level6, "
           "s.evidence, e.name AS employer_name FROM career_sessions s "
           "LEFT JOIN we_employers e ON e.employer_id = s.employer_id")
    args: tuple = ()
    if student_id:
        sql += " WHERE s.student_id = ?"
        args = (student_id,)
    with _connect() as conn:
        return {r["session_id"]: dict(r) for r in conn.execute(sql, args)}


def set_session_links(session_id: int, *, employer_id: Any = None,
                      provider: str | None = None, adviser_level6: Any = False,
                      evidence: str | None = None) -> dict[str, Any]:
    """Link a careers session to its employer / provider, and record
    whether a level 6 adviser delivered it and what evidence exists."""
    init_db()
    get_session_links(session_id)
    with _connect() as conn:
        conn.execute(
            "UPDATE career_sessions SET employer_id=?, provider=?, adviser_level6=?, "
            "evidence=?, updated_at=datetime('now') WHERE session_id=?",
            (_employer_id(employer_id), (provider or "").strip() or None,
             _bool(adviser_level6), (evidence or "").strip() or None, session_id))
        conn.commit()
    return get_session_links(session_id)


# ── Manual evidence ─────────────────────────────────────────────────

def add_evidence(data: dict[str, Any], *, recorded_by: str | None = None) -> dict[str, Any]:
    init_db()
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    sid = (data.get("student_id") or "").strip()
    if not sid or _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    kind = (data.get("kind") or "").strip()
    if kind not in EVIDENCE_KINDS:
        raise ValidationError(f"Kind must be one of: {', '.join(EVIDENCE_KINDS)}")
    bm_raw = data.get("benchmark") or KIND_BENCHMARK.get(kind)
    try:
        bm = int(str(bm_raw).split()[0])
    except (TypeError, ValueError, IndexError):
        raise ValidationError("Benchmark must be 1-8") from None
    if not 1 <= bm <= 8:
        raise ValidationError("Benchmark must be 1-8")
    desc = (data.get("description") or "").strip()
    if not desc:
        raise ValidationError("Describe the evidence")
    level6 = _bool(data.get("adviser_level6"))
    if bm == 8 and not level6:
        raise ValidationError(
            "Benchmark 8 evidence must be a guidance interview with a level 6 "
            "qualified careers adviser — tick that box, or record it against "
            "another benchmark.")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO gatsby_evidence
                   (student_id, benchmark, kind, evidence_date, description,
                    employer_id, provider, adviser_level6, recorded_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sid, bm, kind,
             _date(data.get("evidence_date"), "Date", required=True),
             desc, _employer_id(data.get("employer_id")),
             (data.get("provider") or "").strip() or None, level6, recorded_by))
        conn.commit()
        return dict(conn.execute("SELECT * FROM gatsby_evidence WHERE evidence_id=?",
                                 (cur.lastrowid,)).fetchone())


def list_evidence(*, student_id: str | None = None, benchmark: int | None = None,
                  employer_id: int | None = None) -> list[dict[str, Any]]:
    init_db()
    clauses, args = [], []
    for col, val in (("g.student_id", student_id), ("g.benchmark", benchmark),
                     ("g.employer_id", employer_id)):
        if val not in (None, ""):
            clauses.append(f"{col} = ?"); args.append(val)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [dict(r) for r in conn.execute(
            f"""SELECT g.*, e.name AS employer_name,
                       s.first_name || ' ' || s.last_name AS student_name
                  FROM gatsby_evidence g
                  LEFT JOIN we_employers e ON e.employer_id = g.employer_id
                  LEFT JOIN students s ON s.student_id = g.student_id
                  {where}
                 ORDER BY g.evidence_date DESC, g.evidence_id DESC""", args)]


def delete_evidence(evidence_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM gatsby_evidence WHERE evidence_id=?", (evidence_id,))
        conn.commit()
    return bool(cur.rowcount)


# ── Coverage ────────────────────────────────────────────────────────

@dataclass
class BenchmarkCoverage:
    benchmark: int
    needed: int
    items: list[str] = field(default_factory=list)
    #: Items that look relevant but do not count (e.g. guidance by an
    #: adviser not flagged level 6) — shown so they can be fixed.
    not_counted: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.items)

    @property
    def met(self) -> bool:
        return self.count >= self.needed


@dataclass
class StudentCoverage:
    student_id: str
    student_name: str
    benchmarks: dict[int, BenchmarkCoverage]

    @property
    def met(self) -> list[int]:
        return [b for b, c in self.benchmarks.items() if c.met]

    def as_row(self) -> dict[str, Any]:
        row: dict[str, Any] = {"student_id": self.student_id,
                               "student_name": self.student_name,
                               "met": f"{len(self.met)}/8"}
        for b, c in self.benchmarks.items():
            row[f"bm{b}"] = "✓" if c.met else (f"{c.count}/{c.needed}" if c.count else "—")
        return row


def _in_window(d: str | None, lo: str | None, hi: str | None) -> bool:
    if not d:
        return False
    d = d[:10]
    return (lo is None or d >= lo) and (hi is None or d <= hi)


def _collect(student_ids: list[str], lo: str | None, hi: str | None
             ) -> dict[str, dict[int, BenchmarkCoverage]]:
    out = {sid: {b: BenchmarkCoverage(b, THRESHOLDS[b]) for b in range(1, 9)}
           for sid in student_ids}
    if not student_ids:
        return out
    wanted = set(student_ids)
    with _connect() as conn:
        for r in conn.execute(
                """SELECT s.*, e.name AS employer_name FROM career_sessions s
                   LEFT JOIN we_employers e ON e.employer_id = s.employer_id
                   WHERE s.status = 'Completed'"""):
            if r["student_id"] not in wanted or not _in_window(r["session_date"], lo, hi):
                continue
            bm = r["gatsby_benchmark"]
            if bm is None:
                if r["session_type"] == "Employer Encounter":
                    bm = 5
                elif r["session_type"] == "University Visit":
                    bm = 7
                else:
                    continue
            label = f"{r['session_date']} {r['session_type']}"
            if r["employer_name"]:
                label += f" — {r['employer_name']}"
            if r["provider"]:
                label += f" — {r['provider']}"
            cov = out[r["student_id"]][int(bm)]
            if int(bm) == 8 and not r["adviser_level6"]:
                cov.not_counted.append(label + " (adviser not flagged level 6)")
            else:
                cov.items.append(label)
        for r in conn.execute("SELECT g.*, e.name AS employer_name FROM gatsby_evidence g "
                              "LEFT JOIN we_employers e ON e.employer_id = g.employer_id"):
            if r["student_id"] in wanted and _in_window(r["evidence_date"], lo, hi):
                label = f"{r['evidence_date']} {r['kind']}: {r['description']}"
                if r["employer_name"]:
                    label += f" — {r['employer_name']}"
                out[r["student_id"]][r["benchmark"]].items.append(label)
        if _table_exists(conn, "we_placements"):
            for r in conn.execute(
                    """SELECT p.*, e.name AS employer_name FROM we_placements p
                       JOIN we_employers e ON e.employer_id = p.employer_id
                       WHERE p.status IN ('In Progress', 'Completed')"""):
                if r["student_id"] in wanted and _in_window(r["start_date"], lo, hi):
                    out[r["student_id"]][6].items.append(
                        f"{r['start_date']} placement — {r['employer_name']} ({r['status']})")
        if _table_exists(conn, "university_visit_attendees"):
            for r in conn.execute(
                    """SELECT a.student_id, v.visit_date, v.university_name, v.visit_type
                         FROM university_visit_attendees a
                         JOIN university_visits v ON v.visit_id = a.visit_id
                        WHERE a.attended = 1 AND v.status != 'Cancelled'"""):
                if r["student_id"] in wanted and _in_window(r["visit_date"], lo, hi):
                    out[r["student_id"]][7].items.append(
                        f"{r['visit_date']} {r['visit_type']} — {r['university_name']}")
    return out


def student_coverage(student_id: str, *, date_from: str | None = None,
                     date_to: str | None = None) -> StudentCoverage:
    init_db()
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    st = _students.get_student(student_id)
    if st is None:
        raise ValidationError(f"No student with id {student_id}")
    lo, hi = _date(date_from, "From"), _date(date_to, "To")
    return StudentCoverage(st.student_id, st.full_name, _collect([st.student_id], lo, hi)[st.student_id])


def cohort_students(cohort: str) -> list[tuple[str, str]]:
    """``(student_id, name)`` for a cohort: Year 12 / Year 13 from each
    learner's live (Enrolled, not archived) enrolment in the current
    academic year, or every active student."""
    if cohort not in COHORTS:
        raise ValidationError(f"Cohort must be one of: {', '.join(COHORTS)}")
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    active = [s for s in _students.list_students() if (s.status or "Active") == "Active"]
    if cohort == "All active":
        return [(s.student_id, s.full_name) for s in active]
    year = 12 if cohort == "Year 12" else 13
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolments as _enrolments,
    )
    latest: dict[str, int] = {}
    with _connect() as conn:
        if _table_exists(conn, "enrolments"):
            for r in conn.execute(
                    "SELECT student_id, year_group FROM enrolments "
                    "WHERE status = 'Enrolled' AND archived_at IS NULL "
                    "AND academic_year = ?",
                    (_enrolments.current_academic_year(),)):
                latest[r["student_id"]] = r["year_group"]
    return [(s.student_id, s.full_name) for s in active if latest.get(s.student_id) == year]


@dataclass
class CohortReport:
    cohort: str
    date_from: str | None
    date_to: str | None
    students: list[StudentCoverage]

    def benchmark_rates(self) -> dict[int, tuple[int, int]]:
        """``benchmark -> (students met, cohort size)``."""
        n = len(self.students)
        return {b: (sum(1 for s in self.students if s.benchmarks[b].met), n)
                for b in range(1, 9)}

    def text(self) -> str:
        from education_system.systems.sixth_form.domain.progression.careers.careers import (
            GATSBY_BENCHMARKS,
        )
        lines = [f"Gatsby coverage — {self.cohort}"
                 f" ({self.date_from or 'start'} to {self.date_to or 'today'})",
                 f"{len(self.students)} learner(s)", ""]
        for b, (met, n) in self.benchmark_rates().items():
            pct = round(100 * met / n) if n else 0
            lines.append(f"  BM{b} {GATSBY_BENCHMARKS[b][:46]:<46} {met:>4}/{n:<4} {pct:>3}%"
                         f"   (needs {THRESHOLDS[b]})")
        missing = [s for s in self.students if any(not s.benchmarks[b].met for b in (5, 6, 7, 8))]
        lines += ["", f"Learners missing any of BM5-8: {len(missing)}"]
        for s in missing:
            gaps = [f"BM{b}" for b in (5, 6, 7, 8) if not s.benchmarks[b].met]
            lines.append(f"  {s.student_id:<10} {s.student_name[:28]:<28} {', '.join(gaps)}")
        return "\n".join(lines)


def cohort_coverage(cohort: str = "All active", *, date_from: str | None = None,
                    date_to: str | None = None) -> CohortReport:
    init_db()
    lo, hi = _date(date_from, "From"), _date(date_to, "To")
    members = cohort_students(cohort)
    collected = _collect([sid for sid, _n in members], lo, hi)
    return CohortReport(cohort, lo, hi,
                        [StudentCoverage(sid, name, collected[sid]) for sid, name in members])


# ── Employer directory ──────────────────────────────────────────────

def employer_directory(*, name_like: str | None = None) -> list[dict[str, Any]]:
    """Every employer with how often learners have encountered them."""
    init_db()
    args: list[Any] = []
    where = ""
    if name_like:
        where = "WHERE e.name LIKE ?"
        args.append(f"%{name_like.strip()}%")
    with _connect() as conn:
        return [dict(r) for r in conn.execute(
            f"""SELECT e.*,
                       (SELECT COUNT(*) FROM career_sessions s
                         WHERE s.employer_id = e.employer_id) AS sessions,
                       (SELECT COUNT(*) FROM gatsby_evidence g
                         WHERE g.employer_id = e.employer_id) AS evidence,
                       (SELECT COUNT(*) FROM we_placements p
                         WHERE p.employer_id = e.employer_id) AS placements
                  FROM we_employers e {where}
                 ORDER BY e.name COLLATE NOCASE""", args)]


def encounters_for_employer(employer_id: int) -> list[dict[str, Any]]:
    """Every session, evidence row and placement linked to an employer."""
    init_db()
    out: list[dict[str, Any]] = []
    with _connect() as conn:
        for r in conn.execute(
                "SELECT session_id, student_id, session_date, session_type, status "
                "FROM career_sessions WHERE employer_id=?", (employer_id,)):
            out.append({"id": f"S{r['session_id']}", "date": r["session_date"],
                        "student_id": r["student_id"], "what": r["session_type"],
                        "detail": r["status"]})
        for r in conn.execute(
                "SELECT evidence_id, student_id, evidence_date, kind, description "
                "FROM gatsby_evidence WHERE employer_id=?", (employer_id,)):
            out.append({"id": f"E{r['evidence_id']}", "date": r["evidence_date"],
                        "student_id": r["student_id"], "what": r["kind"],
                        "detail": r["description"]})
        for r in conn.execute(
                "SELECT placement_id, student_id, start_date, status, role "
                "FROM we_placements WHERE employer_id=?", (employer_id,)):
            out.append({"id": f"P{r['placement_id']}", "date": r["start_date"],
                        "student_id": r["student_id"], "what": "Placement",
                        "detail": f"{r['role'] or ''} ({r['status']})".strip()})
    out.sort(key=lambda r: r["date"] or "", reverse=True)
    return out


__all__ = [
    "THRESHOLDS", "EVIDENCE_KINDS", "KIND_BENCHMARK", "COHORTS", "ValidationError",
    "BenchmarkCoverage", "StudentCoverage", "CohortReport", "current_academic_year",
    "get_session_links", "session_links_map", "set_session_links", "add_evidence", "list_evidence",
    "delete_evidence", "student_coverage", "cohort_students", "cohort_coverage",
    "employer_directory", "encounters_for_employer",
]
