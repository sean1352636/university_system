"""Mock exams: series, papers, tier entries, marks, grades and analysis.

Series
    A named mock window for one year group ("Year 11 November mocks"), with
    the old status flow Planned -> InProgress -> Complete -> Archived (and
    back a step while not archived). Papers are set up while Planned or
    InProgress, marks entered while InProgress or Complete, and an Archived
    series is read-only. Results are *released* (to pupils and parents) once
    the series is Complete.

Papers
    Subject, paper name, date, start time, length, room, maximum marks, tier
    (Foundation / Higher / Combined / N/A) and **grade boundaries** as the
    lowest mark for each grade ("9=72, 8=64, ..."). A tier only uses its
    grades: Foundation 5-1, Higher 9-4 (3 allowed), Combined science the
    double grades 9-9 ... 1-1, otherwise 9-1. Marks are graded from the
    boundaries automatically unless a grade is typed in; changing the
    boundaries regrades the automatic ones.

Subject grade
    A pupil's subject grade in a series comes from their total marks over
    the subject's papers in their tier, against the summed paper boundaries
    (how exam boards build a qualification boundary from its components).
    It needs every paper sat and every paper's boundary for that grade.

Who sits what
    The candidates for a paper are the year group's pupils in a teaching
    group for the subject this year (the whole year group if the subject has
    no groups), narrowed to the tier they are entered for when tier entries
    are recorded for that subject. The timetable flags clashes (a pupil with
    overlapping papers) and lists each candidate's exam access arrangements
    from their SEN details.

Who may change things
    The exams officer (:data:`MOCK_EXAM_EDITORS`) runs everything; a teacher
    enters marks and tiers for the pupils they teach in that subject. Every
    change is audited.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import re
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import MOCK_EXAM_EDITORS, Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

MENU_LABEL = "Mock Exams"
SERIES_STATUSES: tuple[str, ...] = ("Planned", "InProgress", "Complete", "Archived")
DEFAULT_SERIES_STATUS = "Planned"
STATUS_LABELS = {"Planned": "Planned", "InProgress": "In progress", "Complete": "Complete",
                 "Archived": "Archived"}
PAPER_TIERS: tuple[str, ...] = ("Foundation", "Higher", "Combined", "N/A")
DEFAULT_TIER = "N/A"
ENTRY_TIERS: tuple[str, ...] = ("Foundation", "Higher")
#: Paper changes allowed while; marks allowed while.
SETUP_STATUSES = frozenset({"Planned", "InProgress"})
MARKING_STATUSES = frozenset({"InProgress", "Complete"})

_SINGLE = ("9", "8", "7", "6", "5", "4", "3", "2", "1")
_COMBINED = tuple(f"{a}-{b}" for a in range(9, 0, -1) for b in (a, a - 1) if b >= 1)
#: Grades a tier can award (best first), without U.
TIER_GRADES: dict[str, tuple[str, ...]] = {
    "N/A": _SINGLE,
    "Higher": ("9", "8", "7", "6", "5", "4", "3"),
    "Foundation": ("5", "4", "3", "2", "1"),
    "Combined": _COMBINED,
}
ABSENCE_REASONS: tuple[str, ...] = ("Absent", "Ill", "Authorised", "Not entered", "Other")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS mock_series (
    series_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL UNIQUE COLLATE NOCASE,
    year_group     INTEGER NOT NULL,
    start_date     TEXT NOT NULL,
    end_date       TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'Planned',
    released_on    TEXT,
    notes          TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    created_by     TEXT,
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS mock_papers (
    paper_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id        INTEGER NOT NULL REFERENCES mock_series (series_id) ON DELETE CASCADE,
    subject_id       INTEGER NOT NULL REFERENCES subjects (subject_id),
    paper_name       TEXT NOT NULL,
    paper_date       TEXT NOT NULL,
    start_time       TEXT,
    duration_mins    INTEGER,
    room             TEXT,
    max_marks        REAL NOT NULL,
    tier             TEXT NOT NULL DEFAULT 'N/A',
    grade_boundaries TEXT,
    notes            TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (series_id, subject_id, paper_name, tier)
);
CREATE INDEX IF NOT EXISTS ix_mock_papers_series ON mock_papers (series_id);
CREATE TABLE IF NOT EXISTS mock_results (
    result_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id       INTEGER NOT NULL REFERENCES mock_papers (paper_id) ON DELETE CASCADE,
    pupil_id       INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    marks_awarded  REAL,
    mark_pct       REAL,
    grade          TEXT,
    grade_source   TEXT NOT NULL DEFAULT 'auto' CHECK (grade_source IN ('auto', 'manual')),
    absent         INTEGER NOT NULL DEFAULT 0,
    absence_reason TEXT,
    notes          TEXT,
    entered_by     TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (paper_id, pupil_id)
);
CREATE INDEX IF NOT EXISTS ix_mock_results_pupil ON mock_results (pupil_id);
CREATE TABLE IF NOT EXISTS mock_entries (
    series_id   INTEGER NOT NULL REFERENCES mock_series (series_id) ON DELETE CASCADE,
    subject_id  INTEGER NOT NULL REFERENCES subjects (subject_id),
    pupil_id    INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    tier        TEXT NOT NULL CHECK (tier IN ('Foundation', 'Higher')),
    set_by      TEXT,
    set_at      TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (series_id, subject_id, pupil_id)
);
CREATE TABLE IF NOT EXISTS mock_audit (
    audit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id  INTEGER,
    pupil_id   INTEGER,
    action     TEXT NOT NULL,
    detail     TEXT,
    actor      TEXT NOT NULL,
    at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_mock_audit_series ON mock_audit (series_id);
"""

database.register_schema("mock_exams", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


# ── Records ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MockSeries:
    series_id: int
    name: str
    year_group: int
    start_date: str
    end_date: str
    status: str
    released_on: str | None
    notes: str | None
    created_at: str
    created_by: str | None
    updated_at: str

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, self.status)

    @property
    def academic_year(self) -> str:
        return TG.current_year(_dt.date.fromisoformat(self.start_date))

    @property
    def released(self) -> bool:
        return bool(self.released_on)


@dataclass(frozen=True)
class MockPaper:
    paper_id: int
    series_id: int
    subject_id: int
    paper_name: str
    paper_date: str
    start_time: str | None
    duration_mins: int | None
    room: str | None
    max_marks: float
    tier: str
    grade_boundaries: str | None
    notes: str | None
    created_at: str
    updated_at: str
    subject_code: str = ""
    subject_name: str = ""

    @property
    def boundaries(self) -> dict[str, float]:
        return json.loads(self.grade_boundaries) if self.grade_boundaries else {}

    @property
    def boundaries_text(self) -> str:
        return ", ".join(f"{g}={_num(m)}" for g, m in self.boundaries.items())

    @property
    def label(self) -> str:
        tier = "" if self.tier == "N/A" else f" ({self.tier})"
        return f"{self.subject_code} {self.paper_name}{tier}"

    def window(self) -> tuple[_dt.datetime, _dt.datetime] | None:
        if not self.start_time:
            return None
        start = _dt.datetime.fromisoformat(f"{self.paper_date}T{self.start_time}")
        return start, start + _dt.timedelta(minutes=self.duration_mins or 60)


@dataclass(frozen=True)
class MockResult:
    result_id: int
    paper_id: int
    pupil_id: int
    marks_awarded: float | None
    mark_pct: float | None
    grade: str | None
    grade_source: str
    absent: bool
    absence_reason: str | None
    notes: str | None
    entered_by: str | None
    created_at: str
    updated_at: str
    pupil_name: str = ""
    admission_no: str = ""


def _num(v: float | None) -> str:
    if v is None:
        return ""
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


_SERIES_SELECT = "SELECT * FROM mock_series"
_PAPER_SELECT = ("SELECT p.*, s.code AS subject_code, s.name AS subject_name FROM mock_papers p "
                 "JOIN subjects s USING (subject_id)")
_RESULT_SELECT = ("SELECT r.*, pu.legal_last_name, pu.legal_first_name, pu.preferred_name, "
                  "pu.admission_no FROM mock_results r JOIN pupils pu USING (pupil_id)")


def _series_row(r) -> MockSeries:
    return MockSeries(**{k: r[k] for k in MockSeries.__dataclass_fields__})


def _paper_row(r) -> MockPaper:
    return MockPaper(**{k: r[k] for k in MockPaper.__dataclass_fields__})


def _result_row(r) -> MockResult:
    base = {k: r[k] for k in MockResult.__dataclass_fields__
            if k not in ("pupil_name", "admission_no")}
    base["absent"] = bool(base["absent"])
    return MockResult(**base, admission_no=r["admission_no"],
                      pupil_name=f"{r['legal_last_name']}, "
                                 f"{r['preferred_name'] or r['legal_first_name']}")


# ── Access ───────────────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in MOCK_EXAM_EDITORS


def _same(a: str | None, b: str | None) -> bool:
    return bool(a) and bool(b) and a.strip().lower() == b.strip().lower()  # type: ignore[union-attr]


def teaches(actor: Principal, pupil_id: int, subject_id: int, academic_year: str) -> bool:
    return any(i.group.subject_id == subject_id and _same(i.group.teacher_username,
                                                          actor.username)
               for i in TG.groups_for_pupil(pupil_id, academic_year))


def _require(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Only the exams officer can do that.")


def _audit(conn, series_id: int | None, action: str, actor: Principal, detail: dict,
           pupil_id: int | None = None) -> None:
    conn.execute("INSERT INTO mock_audit (series_id, pupil_id, action, detail, actor) VALUES "
                 "(?, ?, ?, ?, ?)", (series_id, pupil_id, action,
                                     json.dumps(detail, sort_keys=True, default=str),
                                     actor.username or "unknown"))


def history(series_id: int) -> list[dict[str, Any]]:
    with database.connect() as conn:
        return [{"at": r["at"], "actor": r["actor"], "action": r["action"],
                 "pupil_id": r["pupil_id"], "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute("SELECT * FROM mock_audit WHERE series_id = ? "
                                      "ORDER BY audit_id DESC", (int(series_id),))]


# ── Grades ───────────────────────────────────────────────────────────

def grades_for(tier: str) -> tuple[str, ...]:
    """Grades a paper of *tier* can award, best first, then U."""
    return TIER_GRADES.get(tier, _SINGLE) + ("U",)


def grade_value(grade: str | None) -> float | None:
    """9-1 as a number; a combined grade is the mean of its two; U is 0."""
    if not grade:
        return None
    g = grade.strip().upper()
    if g == "U":
        return 0.0
    if g.isdigit():
        return float(g)
    if re.fullmatch(r"\d-\d", g):
        a, b = g.split("-")
        return (int(a) + int(b)) / 2
    return None


def parse_boundaries(text: str | dict | None, tier: str, max_marks: float
                     ) -> dict[str, float]:
    """``"9=72, 8=64"`` (or ``:``) -> {"9": 72.0, ...}, best grade first.
    Raises ValidationError for unknown grades, marks outside 0..max, or
    marks that don't fall as the grade falls."""
    if isinstance(text, dict):
        pairs = list(text.items())
    else:
        pairs = []
        for part in re.split(r"[,;\n]+", text or ""):
            part = part.strip()
            if not part:
                continue
            m = re.fullmatch(r"([0-9]-?[0-9]?)\s*[=:]\s*(\d+(?:\.\d+)?)", part)
            if not m:
                raise ValidationError([f"Grade boundary '{part}' should look like 7=56"])
            pairs.append((m.group(1), m.group(2)))
    allowed = TIER_GRADES.get(tier, _SINGLE)
    problems, out = [], {}
    for g, mark in pairs:
        g = str(g).strip()
        if g not in allowed:
            problems.append(f"Grade {g} isn't awarded on a {tier} paper "
                            f"(grades {allowed[-1]}-{allowed[0]})" if tier != "N/A"
                            else f"Grade {g} isn't a 9-1 grade")
            continue
        try:
            val = float(mark)
        except (TypeError, ValueError):
            problems.append(f"The boundary for {g} must be a number")
            continue
        if not 0 <= val <= max_marks:
            problems.append(f"The boundary for {g} must be between 0 and {_num(max_marks)}")
            continue
        if g in out:
            problems.append(f"Grade {g} has two boundaries")
        out[g] = val
    ordered = {g: out[g] for g in allowed if g in out}
    marks = list(ordered.values())
    if any(a <= b for a, b in zip(marks, marks[1:])):
        problems.append("Each grade's boundary must be below the grade above it")
    if problems:
        raise ValidationError(problems)
    return ordered


def grade_from(marks: float | None, boundaries: dict[str, float]) -> str | None:
    """The best grade whose boundary *marks* reaches; U below the lowest;
    None with no boundaries or no marks."""
    if marks is None or not boundaries:
        return None
    for g, low in boundaries.items():
        if marks >= low:
            return g
    return "U"


# ── Series ───────────────────────────────────────────────────────────

def get_series(series_id: int) -> MockSeries:
    with database.connect() as conn:
        r = conn.execute(_SERIES_SELECT + " WHERE series_id = ?", (int(series_id),)).fetchone()
    if r is None:
        raise NotFound(f"No mock series #{series_id}")
    return _series_row(r)


def list_series(*, year_group: int | str | None = None, status: str | None = None
                ) -> list[MockSeries]:
    sql, params = _SERIES_SELECT + " WHERE 1=1", []
    if year_group not in (None, ""):
        sql += " AND year_group = ?"
        params.append(int(year_group))  # type: ignore[arg-type]
    if status:
        sql += " AND status = ?"
        params.append(status)
    with database.connect() as conn:
        return [_series_row(r) for r in conn.execute(
            sql + " ORDER BY start_date DESC, name COLLATE NOCASE", params)]


def _date(value: Any, label: str, problems: list[str]) -> str | None:
    v = str(value or "").strip()
    if not v:
        problems.append(f"{label} is required")
        return None
    try:
        return _dt.date.fromisoformat(v).isoformat()
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None


def _clean_series(data: dict[str, Any], current: MockSeries | None) -> dict[str, Any]:
    merged = {k: getattr(current, k) for k in ("name", "year_group", "start_date",
                                               "end_date", "notes")} if current else {}
    merged.update({k: v for k, v in data.items() if v is not None})
    problems: list[str] = []
    name = P._clean_text(merged.get("name"), 80)
    if not name:
        problems.append("Give the series a name")
    try:
        yg = int(str(merged.get("year_group") or "").strip())
    except ValueError:
        yg = 0
    if yg not in P.YEAR_GROUPS:
        problems.append(f"Year group must be one of {', '.join(map(str, P.YEAR_GROUPS))}")
    start = _date(merged.get("start_date"), "Start date", problems)
    end = _date(merged.get("end_date"), "End date", problems)
    if start and end and end < start:
        problems.append("End date cannot be before start date")
    if start and end and (_dt.date.fromisoformat(end) - _dt.date.fromisoformat(start)).days > 60:
        problems.append("A mock series can't run for more than 60 days")
    if problems:
        raise ValidationError(problems)
    return {"name": name, "year_group": yg, "start_date": start, "end_date": end,
            "notes": P._clean_text(merged.get("notes"), 2000)}


def _name_taken(conn, name: str, exclude: int | None = None) -> bool:
    return conn.execute("SELECT 1 FROM mock_series WHERE name = ? COLLATE NOCASE AND "
                        "series_id IS NOT ?", (name, exclude)).fetchone() is not None


def create_series(data: dict[str, Any], *, actor: Principal) -> MockSeries:
    _require(actor, "mock.series.create")
    clean = _clean_series(data, None)
    status = data.get("status") or DEFAULT_SERIES_STATUS
    if status not in ("Planned", "InProgress"):
        raise ValidationError(["A new series starts as Planned or InProgress"])
    with database.connect() as conn:
        if _name_taken(conn, clean["name"]):
            raise ValidationError([f"There is already a series called {clean['name']}"])
        cur = conn.execute(
            "INSERT INTO mock_series (name, year_group, start_date, end_date, status, notes, "
            "created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (clean["name"], clean["year_group"], clean["start_date"], clean["end_date"],
             status, clean["notes"], actor.username))
        sid = cur.lastrowid
        _audit(conn, sid, "series.create", actor, {"name": clean["name"]})
    activity_log.record("mock.series.create", target=f"series:{sid}", principal=actor)
    return get_series(sid)  # type: ignore[arg-type]


def update_series(series_id: int, data: dict[str, Any], *, actor: Principal) -> MockSeries:
    s = get_series(series_id)
    _require(actor, "mock.series.update", f"series:{s.series_id}")
    if s.status == "Archived":
        raise ValidationError(["The series is archived - restore it to Complete first"])
    if "status" in data and data["status"] not in (None, s.status):
        raise ValidationError(["Change the status with Set status"])
    clean = _clean_series(data, s)
    problems = []
    with database.connect() as conn:
        if _name_taken(conn, clean["name"], s.series_id):
            problems.append(f"There is already a series called {clean['name']}")
        n = conn.execute("SELECT count(*) FROM mock_papers WHERE series_id = ?",
                         (s.series_id,)).fetchone()[0]
        if n and clean["year_group"] != s.year_group:
            problems.append("The year group can't change once papers are set up")
        outside = conn.execute(
            "SELECT count(*) FROM mock_papers WHERE series_id = ? AND (paper_date < ? OR "
            "paper_date > ?)", (s.series_id, clean["start_date"], clean["end_date"])
        ).fetchone()[0]
        if outside:
            problems.append(f"{outside} paper(s) would fall outside the new dates")
        if problems:
            raise ValidationError(problems)
        changed = {k: v for k, v in clean.items() if getattr(s, k) != v}
        if not changed:
            return s
        conn.execute(
            "UPDATE mock_series SET name = ?, year_group = ?, start_date = ?, end_date = ?, "
            "notes = ?, updated_at = datetime('now') WHERE series_id = ?",
            (clean["name"], clean["year_group"], clean["start_date"], clean["end_date"],
             clean["notes"], s.series_id))
        _audit(conn, s.series_id, "series.update", actor, {"fields": sorted(changed)})
    activity_log.record("mock.series.update", target=f"series:{s.series_id}", principal=actor)
    return get_series(s.series_id)


_MOVES = {("Planned", "InProgress"), ("InProgress", "Planned"), ("InProgress", "Complete"),
          ("Complete", "InProgress"), ("Complete", "Archived"), ("Archived", "Complete")}


def set_series_status(series_id: int, status: str, *, actor: Principal) -> MockSeries:
    s = get_series(series_id)
    _require(actor, "mock.series.status", f"series:{s.series_id}")
    if status == s.status:
        return s
    if status not in SERIES_STATUSES:
        raise ValidationError([f"Status must be one of {', '.join(SERIES_STATUSES)}"])
    if (s.status, status) not in _MOVES:
        nxt = sorted(b for a, b in _MOVES if a == s.status)
        raise ValidationError([f"A {s.status_label.lower()} series can move to "
                               + " or ".join(STATUS_LABELS[n] for n in nxt)])
    problems = []
    if status == "Planned" and results_count(s.series_id):
        problems.append("Marks have been entered - it can't go back to Planned")
    if status == "Complete" and not papers(s.series_id):
        problems.append("Add the papers first")
    if status == "InProgress" and s.released:
        problems.append("Results have been released - withdraw the release first")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("UPDATE mock_series SET status = ?, updated_at = datetime('now') WHERE "
                     "series_id = ?", (status, s.series_id))
        _audit(conn, s.series_id, "series.status", actor, {"from": s.status, "to": status})
    activity_log.record("mock.series.status", target=f"series:{s.series_id}", principal=actor,
                        status=status)
    return get_series(s.series_id)


def release_results(series_id: int, *, actor: Principal, release: bool = True) -> MockSeries:
    """Release (or withdraw) the results to pupils and parents."""
    s = get_series(series_id)
    _require(actor, "mock.release", f"series:{s.series_id}")
    if release and s.status not in ("Complete", "Archived"):
        raise ValidationError(["Mark the series Complete before releasing results"])
    if release and not s.released:
        missing = sum(len(m) for _p, m in missing_marks(s.series_id))
        if missing:
            raise ValidationError([f"{missing} mark(s) are still missing - enter them or "
                                   "mark the pupils absent"])
    if release == s.released:
        return s
    when = _today().isoformat() if release else None
    with database.connect() as conn:
        conn.execute("UPDATE mock_series SET released_on = ?, updated_at = datetime('now') "
                     "WHERE series_id = ?", (when, s.series_id))
        _audit(conn, s.series_id, "series.release" if release else "series.unrelease", actor,
               {})
    activity_log.record("mock.release", target=f"series:{s.series_id}", principal=actor,
                        released=release)
    return get_series(s.series_id)


def delete_series(series_id: int, *, actor: Principal) -> bool:
    s = get_series(series_id)
    _require(actor, "mock.series.delete", f"series:{s.series_id}")
    if s.released:
        raise ValidationError(["Released results can't be deleted - archive the series"])
    with database.connect() as conn:
        n = conn.execute("SELECT count(*) FROM mock_results r JOIN mock_papers p USING "
                         "(paper_id) WHERE p.series_id = ?", (s.series_id,)).fetchone()[0]
        conn.execute("DELETE FROM mock_series WHERE series_id = ?", (s.series_id,))
        _audit(conn, s.series_id, "series.delete", actor, {"name": s.name, "results": n})
    activity_log.record("mock.series.delete", target=f"series:{s.series_id}", principal=actor)
    return True


def results_count(series_id: int) -> int:
    with database.connect() as conn:
        return conn.execute("SELECT count(*) FROM mock_results r JOIN mock_papers p USING "
                            "(paper_id) WHERE p.series_id = ?", (int(series_id),)).fetchone()[0]


# ── Papers ───────────────────────────────────────────────────────────

def get_paper(paper_id: int) -> MockPaper:
    with database.connect() as conn:
        r = conn.execute(_PAPER_SELECT + " WHERE p.paper_id = ?", (int(paper_id),)).fetchone()
    if r is None:
        raise NotFound(f"No mock paper #{paper_id}")
    return _paper_row(r)


def papers(series_id: int, *, subject_id: int | None = None) -> list[MockPaper]:
    sql, params = _PAPER_SELECT + " WHERE p.series_id = ?", [int(series_id)]
    if subject_id is not None:
        sql += " AND p.subject_id = ?"
        params.append(int(subject_id))
    with database.connect() as conn:
        return [_paper_row(r) for r in conn.execute(
            sql + " ORDER BY p.paper_date, coalesce(p.start_time, '99'), s.name COLLATE "
                  "NOCASE, p.paper_name", params)]


list_papers = papers


def _subject(ref: Any) -> S.Subject | None:
    v = str(ref or "").strip()
    if not v:
        return None
    if v.isdigit():
        try:
            return S.get(int(v))
        except NotFound:
            return None
    return S.get_by_code(v) or next((x for x in S.list_subjects(active_only=False)
                                     if x.name.lower() == v.lower()), None)


def _clean_paper(data: dict[str, Any], series: MockSeries, current: MockPaper | None
                 ) -> dict[str, Any]:
    keys = ("subject_id", "paper_name", "paper_date", "start_time", "duration_mins", "room",
            "max_marks", "tier", "grade_boundaries", "notes")
    merged: dict[str, Any] = {k: getattr(current, k) for k in keys} if current else {}
    if current:
        merged["grade_boundaries"] = current.boundaries
    merged.update({k: v for k, v in data.items() if v is not None})
    problems: list[str] = []
    subj = _subject(merged.get("subject_id") or merged.get("subject"))
    if subj is None:
        problems.append("Choose the subject")
    name = P._clean_text(merged.get("paper_name"), 64)
    if not name:
        problems.append("Give the paper a name (e.g. Paper 1)")
    day = _date(merged.get("paper_date"), "Paper date", problems)
    if day and not series.start_date <= day <= series.end_date:
        problems.append(f"The paper date must be within the series "
                        f"({series.start_date} to {series.end_date})")
    start = P._clean_text(merged.get("start_time"), 5)
    if start and not _TIME_RE.match(start):
        problems.append("Start time must be HH:MM (24-hour)")
    dur_raw = merged.get("duration_mins")
    dur = None
    if dur_raw not in (None, ""):
        try:
            dur = int(str(dur_raw).strip())
            if not 10 <= dur <= 300:
                raise ValueError
        except ValueError:
            problems.append("Length must be 10-300 minutes")
    try:
        mx = float(str(merged.get("max_marks") or "").strip())
        if not 0 < mx <= 1000:
            raise ValueError
    except ValueError:
        mx = 0.0
        problems.append("Max marks must be a number from 1 to 1000")
    tier = P._clean_text(merged.get("tier"), 12) or DEFAULT_TIER
    tier = next((t for t in PAPER_TIERS if t.lower() == tier.lower()), tier)
    if tier not in PAPER_TIERS:
        problems.append(f"Tier must be one of {', '.join(PAPER_TIERS)}")
    bounds: dict[str, float] = {}
    if mx and tier in PAPER_TIERS:
        try:
            bounds = parse_boundaries(merged.get("grade_boundaries"), tier, mx)
        except ValidationError as e:
            problems.extend(e.problems)
    if problems:
        raise ValidationError(problems)
    return {"subject_id": subj.subject_id, "paper_name": name, "paper_date": day,  # type: ignore[union-attr]
            "start_time": start or None, "duration_mins": dur,
            "room": P._clean_text(merged.get("room"), 30), "max_marks": mx, "tier": tier,
            "grade_boundaries": json.dumps(bounds) if bounds else None,
            "notes": P._clean_text(merged.get("notes"), 1000)}


def _setup_open(series: MockSeries) -> None:
    if series.status not in SETUP_STATUSES:
        raise ValidationError([f"Papers can't change while the series is "
                               f"{series.status_label.lower()}"])


def create_paper(data: dict[str, Any], *, actor: Principal) -> MockPaper:
    s = get_series(int(data.get("series_id") or 0))
    _require(actor, "mock.paper.create", f"series:{s.series_id}")
    _setup_open(s)
    clean = _clean_paper(data, s, None)
    with database.connect() as conn:
        if conn.execute("SELECT 1 FROM mock_papers WHERE series_id = ? AND subject_id = ? AND "
                        "paper_name = ? COLLATE NOCASE AND tier = ?",
                        (s.series_id, clean["subject_id"], clean["paper_name"], clean["tier"])
                        ).fetchone():
            raise ValidationError([f"That subject already has {clean['paper_name']} "
                                   f"({clean['tier']}) in this series"])
        cur = conn.execute(
            "INSERT INTO mock_papers (series_id, subject_id, paper_name, paper_date, start_time, "
            "duration_mins, room, max_marks, tier, grade_boundaries, notes) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (s.series_id, clean["subject_id"], clean["paper_name"], clean["paper_date"],
             clean["start_time"], clean["duration_mins"], clean["room"], clean["max_marks"],
             clean["tier"], clean["grade_boundaries"], clean["notes"]))
        pid = cur.lastrowid
        _audit(conn, s.series_id, "paper.create", actor,
               {"paper_id": pid, "subject_id": clean["subject_id"],
                "paper": clean["paper_name"]})
    activity_log.record("mock.paper.create", target=f"paper:{pid}", principal=actor)
    return get_paper(pid)  # type: ignore[arg-type]


def update_paper(paper_id: int, data: dict[str, Any], *, actor: Principal) -> MockPaper:
    """Change a paper. Max marks can't go below a mark already entered; the
    subject and tier are fixed once marks exist; new boundaries regrade the
    automatically graded results."""
    p = get_paper(paper_id)
    s = get_series(p.series_id)
    _require(actor, "mock.paper.update", f"paper:{p.paper_id}")
    if s.status == "Archived":
        raise ValidationError(["The series is archived"])
    clean = _clean_paper(data, s, p)
    marks_only = s.status not in SETUP_STATUSES
    with database.connect() as conn:
        top = conn.execute("SELECT max(marks_awarded), count(*) FROM mock_results WHERE "
                           "paper_id = ?", (p.paper_id,)).fetchone()
        problems = []
        if top[1] and (clean["subject_id"] != p.subject_id or clean["tier"] != p.tier):
            problems.append("The subject and tier can't change once marks are entered")
        if top[0] is not None and clean["max_marks"] < top[0]:
            problems.append(f"A pupil already has {_num(top[0])} marks - max marks can't be "
                            "lower")
        if marks_only and any(clean[k] != getattr(p, k) for k in (
                "subject_id", "paper_name", "paper_date", "start_time", "duration_mins",
                "room", "max_marks", "tier")):
            problems.append(f"Only the grade boundaries and notes can change while the series "
                            f"is {s.status_label.lower()}")
        if s.released and (clean["grade_boundaries"] != p.grade_boundaries
                           or clean["max_marks"] != p.max_marks):
            problems.append("Results have been released - withdraw the release before "
                            "changing the grade boundaries")
        if problems:
            raise ValidationError(problems)
        changed = sorted(k for k in clean if clean[k] != (
            p.grade_boundaries if k == "grade_boundaries" else getattr(p, k)))
        if not changed:
            return p
        conn.execute(
            "UPDATE mock_papers SET subject_id = ?, paper_name = ?, paper_date = ?, "
            "start_time = ?, duration_mins = ?, room = ?, max_marks = ?, tier = ?, "
            "grade_boundaries = ?, notes = ?, updated_at = datetime('now') WHERE paper_id = ?",
            (clean["subject_id"], clean["paper_name"], clean["paper_date"], clean["start_time"],
             clean["duration_mins"], clean["room"], clean["max_marks"], clean["tier"],
             clean["grade_boundaries"], clean["notes"], p.paper_id))
        regraded = 0
        if {"grade_boundaries", "max_marks"} & set(changed):
            bounds = json.loads(clean["grade_boundaries"]) if clean["grade_boundaries"] else {}
            for r in conn.execute("SELECT result_id, marks_awarded, grade FROM mock_results "
                                  "WHERE paper_id = ? AND grade_source = 'auto' AND absent = 0",
                                  (p.paper_id,)).fetchall():
                g = grade_from(r["marks_awarded"], bounds)
                pct = (round(100 * r["marks_awarded"] / clean["max_marks"], 1)
                       if r["marks_awarded"] is not None else None)
                conn.execute("UPDATE mock_results SET grade = ?, mark_pct = ? WHERE "
                             "result_id = ?", (g, pct, r["result_id"]))
                regraded += g != r["grade"]
        _audit(conn, s.series_id, "paper.update", actor,
               {"paper_id": p.paper_id, "fields": changed, "regraded": regraded})
    activity_log.record("mock.paper.update", target=f"paper:{p.paper_id}", principal=actor)
    return get_paper(p.paper_id)


def delete_paper(paper_id: int, *, actor: Principal) -> bool:
    p = get_paper(paper_id)
    s = get_series(p.series_id)
    _require(actor, "mock.paper.delete", f"paper:{p.paper_id}")
    _setup_open(s)
    with database.connect() as conn:
        n = conn.execute("SELECT count(*) FROM mock_results WHERE paper_id = ?",
                         (p.paper_id,)).fetchone()[0]
        conn.execute("DELETE FROM mock_papers WHERE paper_id = ?", (p.paper_id,))
        _audit(conn, s.series_id, "paper.delete", actor,
               {"paper_id": p.paper_id, "paper": p.label, "results": n})
    activity_log.record("mock.paper.delete", target=f"paper:{p.paper_id}", principal=actor)
    return True


# ── Tier entries and candidates ──────────────────────────────────────

def entries(series_id: int, subject_id: int) -> dict[int, str]:
    with database.connect() as conn:
        return {r[0]: r[1] for r in conn.execute(
            "SELECT pupil_id, tier FROM mock_entries WHERE series_id = ? AND subject_id = ?",
            (int(series_id), int(subject_id)))}


def subject_pupils(series: MockSeries, subject_id: int) -> list[P.Pupil]:
    """Year-group pupils taking the subject (in a teaching group for it this
    year), or the whole year group if the subject has no groups."""
    pupils = P.list_pupils(year_group=series.year_group)
    groups = TG.list_groups(academic_year=series.academic_year, year_group=series.year_group,
                            subject_id=subject_id)
    if not groups:
        return pupils
    ids = {p.pupil_id for g in groups for p in TG.members(g.group_id)}
    return [p for p in pupils if p.pupil_id in ids]


def candidates(paper_id: int) -> list[P.Pupil]:
    """Who sits this paper (see the module notes)."""
    p = get_paper(paper_id)
    s = get_series(p.series_id)
    pupils = subject_pupils(s, p.subject_id)
    if p.tier in ENTRY_TIERS:
        tiers = entries(s.series_id, p.subject_id)
        if tiers:
            pupils = [x for x in pupils if tiers.get(x.pupil_id) == p.tier]
    return pupils


def set_tiers(series_id: int, subject_id: int, tiers: dict[int, str | None], *,
              actor: Principal) -> int:
    """Enter pupils for Foundation or Higher (None clears). A teacher may set
    tiers for the pupils they teach. All or nothing; returns rows changed."""
    s = get_series(series_id)
    if s.status == "Archived":
        raise ValidationError(["The series is archived"])
    subj = S.get(int(subject_id))
    current = entries(s.series_id, subj.subject_id)
    problems = []
    with database.connect() as conn:
        tiered_results = {r[0]: r[1] for r in conn.execute(
            "SELECT r.pupil_id, p.tier FROM mock_results r JOIN mock_papers p USING (paper_id) "
            "WHERE p.series_id = ? AND p.subject_id = ? AND p.tier IN ('Foundation', 'Higher')",
            (s.series_id, subj.subject_id))}
    for pid, tier in tiers.items():
        pid = int(pid)
        if tier not in (None, "", *ENTRY_TIERS):
            problems.append(f"Tier must be Foundation or Higher (pupil {pid})")
            continue
        if not is_editor(actor) and not teaches(actor, pid, subj.subject_id, s.academic_year):
            activity_log.record("mock.tiers", target=f"series:{s.series_id}", outcome="denied",
                                principal=actor)
            raise PermissionDenied("You can only set tiers for pupils you teach.")
        if tier and pid in tiered_results and tiered_results[pid] != tier:
            p = P.get_pupil(pid)
            problems.append(f"{p.display_name if p else pid} has {tiered_results[pid]} marks "
                            "already - delete them before changing tier")
    if problems:
        raise ValidationError(problems)
    n = 0
    with database.connect() as conn:
        for pid, tier in tiers.items():
            pid = int(pid)
            if (tier or None) == current.get(pid):
                continue
            if tier:
                conn.execute("INSERT INTO mock_entries (series_id, subject_id, pupil_id, tier, "
                             "set_by) VALUES (?, ?, ?, ?, ?) ON CONFLICT DO UPDATE SET "
                             "tier = excluded.tier, set_by = excluded.set_by, set_at = "
                             "datetime('now')", (s.series_id, subj.subject_id, pid, tier,
                                                 actor.username))
            else:
                conn.execute("DELETE FROM mock_entries WHERE series_id = ? AND subject_id = ? "
                             "AND pupil_id = ?", (s.series_id, subj.subject_id, pid))
            _audit(conn, s.series_id, "tier", actor, {"subject_id": subj.subject_id,
                                                      "from": current.get(pid), "to": tier},
                   pupil_id=pid)
            n += 1
    activity_log.record("mock.tiers", target=f"series:{s.series_id}", principal=actor, rows=n)
    return n


# ── Results ──────────────────────────────────────────────────────────

def get_result(result_id: int) -> MockResult:
    with database.connect() as conn:
        r = conn.execute(_RESULT_SELECT + " WHERE r.result_id = ?", (int(result_id),)).fetchone()
    if r is None:
        raise NotFound(f"No mock result #{result_id}")
    return _result_row(r)


def list_results(paper_id: int) -> list[MockResult]:
    with database.connect() as conn:
        return [_result_row(r) for r in conn.execute(
            _RESULT_SELECT + " WHERE r.paper_id = ? ORDER BY pu.legal_last_name COLLATE "
            "NOCASE, pu.legal_first_name COLLATE NOCASE", (int(paper_id),))]


def results_for_pupil(pupil_id: int, *, released_only: bool = False
                      ) -> list[tuple[MockSeries, MockPaper, MockResult]]:
    """Every mock result for the pupil, newest series first."""
    sql = (_RESULT_SELECT + " WHERE r.pupil_id = ?")
    with database.connect() as conn:
        rows = [_result_row(r) for r in conn.execute(sql, (int(pupil_id),))]
    out = []
    cache_p: dict[int, MockPaper] = {}
    cache_s: dict[int, MockSeries] = {}
    for r in rows:
        if r.paper_id not in cache_p:
            cache_p[r.paper_id] = get_paper(r.paper_id)
        p = cache_p[r.paper_id]
        if p.series_id not in cache_s:
            cache_s[p.series_id] = get_series(p.series_id)
        s = cache_s[p.series_id]
        if released_only and not s.released:
            continue
        out.append((s, p, r))
    out.sort(key=lambda t: (t[0].start_date, t[1].paper_date, t[1].subject_name), reverse=True)
    return out


def can_mark(actor: Principal, paper: MockPaper, series: MockSeries, pupil_id: int) -> bool:
    return is_editor(actor) or (actor.is_staff and teaches(actor, pupil_id, paper.subject_id,
                                                           series.academic_year))


def _clean_result(data: dict[str, Any], paper: MockPaper, label: str,
                  problems: list[str]) -> dict[str, Any] | None:
    n = len(problems)
    absent = str(data.get("absent") or "").strip().lower() in ("1", "true", "yes", "y", "a",
                                                                "absent")
    if data.get("absent") is True:
        absent = True
    reason = P._clean_text(data.get("absence_reason"), 20)
    if reason:
        reason = next((x for x in ABSENCE_REASONS if x.lower() == reason.lower()), reason)
        if reason not in ABSENCE_REASONS:
            problems.append(f"{label}absence reason must be one of {', '.join(ABSENCE_REASONS)}")
    marks = None
    raw = data.get("marks_awarded", data.get("marks"))
    if raw not in (None, "") and not absent:
        try:
            marks = float(str(raw).strip())
            if not 0 <= marks <= paper.max_marks:
                problems.append(f"{label}marks must be between 0 and {_num(paper.max_marks)}")
        except ValueError:
            problems.append(f"{label}marks must be a number")
    if absent and raw not in (None, ""):
        problems.append(f"{label}an absent pupil has no marks")
    grade = (P._clean_text(data.get("grade"), 4) or "").upper()
    if grade and grade not in grades_for(paper.tier):
        problems.append(f"{label}grade {grade} isn't awarded on this paper "
                        f"({', '.join(grades_for(paper.tier))})")
    if absent and grade:
        problems.append(f"{label}an absent pupil has no grade")
    if not absent and marks is None and not grade:
        problems.append(f"{label}enter the marks, a grade, or mark them absent")
    if len(problems) != n:
        return None
    auto = grade_from(marks, paper.boundaries)
    return {"marks_awarded": marks,
            "mark_pct": round(100 * marks / paper.max_marks, 1) if marks is not None else None,
            "grade": grade or auto, "grade_source": "manual" if grade and grade != auto
            else "auto", "absent": 1 if absent else 0,
            "absence_reason": (reason or "Absent") if absent else None,
            "notes": P._clean_text(data.get("notes"), 500)}


_RESULT_KEYS = ("marks_awarded", "mark_pct", "grade", "grade_source", "absent",
                "absence_reason", "notes")


def _write_result(conn, paper: MockPaper, pupil_id: int, c: dict[str, Any], actor: Principal,
                  ) -> str:
    old = conn.execute("SELECT * FROM mock_results WHERE paper_id = ? AND pupil_id = ?",
                       (paper.paper_id, pupil_id)).fetchone()
    if old is not None and all(old[k] == c[k] for k in _RESULT_KEYS):
        return ""
    conn.execute(
        "INSERT INTO mock_results (paper_id, pupil_id, marks_awarded, mark_pct, grade, "
        "grade_source, absent, absence_reason, notes, entered_by) VALUES "
        "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (paper_id, pupil_id) DO UPDATE SET "
        "marks_awarded = excluded.marks_awarded, mark_pct = excluded.mark_pct, grade = "
        "excluded.grade, grade_source = excluded.grade_source, absent = excluded.absent, "
        "absence_reason = excluded.absence_reason, notes = excluded.notes, entered_by = "
        "excluded.entered_by, updated_at = datetime('now')",
        (paper.paper_id, pupil_id, c["marks_awarded"], c["mark_pct"], c["grade"],
         c["grade_source"], c["absent"], c["absence_reason"], c["notes"], actor.username))
    kind = "result.record" if old is None else "result.change"
    _audit(conn, paper.series_id, kind, actor,
           {"paper_id": paper.paper_id,
            "from": None if old is None else ("absent" if old["absent"] else
                                              f"{_num(old['marks_awarded'])} {old['grade'] or ''}"
                                              .strip()),
            "to": "absent" if c["absent"] else f"{_num(c['marks_awarded'])} {c['grade'] or ''}"
            .strip()}, pupil_id=pupil_id)
    return "record" if old is None else "change"


def _marking_checks(paper: MockPaper, series: MockSeries, pupil_ids: list[int],
                    actor: Principal, action: str) -> None:
    if series.status not in MARKING_STATUSES:
        raise ValidationError([f"Marks can only be entered while the series is In progress "
                               f"or Complete (it is {series.status_label})"])
    if series.released and not is_editor(actor):
        raise PermissionDenied("Results have been released - ask the exams officer to change "
                               "them.")
    if not is_editor(actor):
        for pid in pupil_ids:
            if not can_mark(actor, paper, series, pid):
                activity_log.record(action, target=f"paper:{paper.paper_id}", outcome="denied",
                                    principal=actor)
                raise PermissionDenied("You can only enter marks for pupils you teach in "
                                       f"{paper.subject_name}.")


def upsert_result(paper_id: int, data: dict[str, Any], *, actor: Principal) -> MockResult:
    """Record or update one pupil's result: pupil (id / admission no),
    marks_awarded, grade (blank = from the boundaries), absent,
    absence_reason, notes."""
    paper = get_paper(paper_id)
    series = get_series(paper.series_id)
    ref = data.get("pupil_id") or data.get("pupil")
    pupil = (P.get_pupil(int(ref)) if str(ref or "").strip().isdigit() else None) or \
        P.find_by_reference(str(ref or "").strip())
    if pupil is None:
        raise ValidationError([f"No pupil {ref}" if ref else "Choose the pupil"])
    _marking_checks(paper, series, [pupil.pupil_id], actor, "mock.result")
    problems: list[str] = []
    if pupil.pupil_id not in {p.pupil_id for p in candidates(paper.paper_id)}:
        problems.append(f"{pupil.display_name} isn't a candidate for {paper.label}")
    c = _clean_result(data, paper, "", problems)
    if problems:
        raise ValidationError([x[:1].upper() + x[1:] for x in problems])
    with database.connect() as conn:
        _write_result(conn, paper, pupil.pupil_id, c, actor)  # type: ignore[arg-type]
        rid = conn.execute("SELECT result_id FROM mock_results WHERE paper_id = ? AND "
                           "pupil_id = ?", (paper.paper_id, pupil.pupil_id)).fetchone()[0]
    activity_log.record("mock.result", target=f"paper:{paper.paper_id}", principal=actor)
    return get_result(rid)


def save_sheet(paper_id: int, rows: dict[int, dict[str, Any]], *, actor: Principal) -> int:
    """Whole-paper mark entry: {pupil_id: {marks_awarded, grade, absent,
    absence_reason, notes}}. A row with nothing in it clears the result.
    All or nothing; returns rows changed."""
    paper = get_paper(paper_id)
    series = get_series(paper.series_id)
    ids = [int(k) for k in rows]
    _marking_checks(paper, series, ids, actor, "mock.sheet")
    allowed = {p.pupil_id: p for p in candidates(paper.paper_id)}
    problems: list[str] = []
    todo: list[tuple[int, dict | None]] = []
    for pid, data in rows.items():
        pid = int(pid)
        p = allowed.get(pid)
        label = f"{p.display_name}: " if p else f"Pupil {pid}: "
        if p is None:
            problems.append(f"{label}not a candidate for this paper")
            continue
        blank = not any(str(data.get(k) or "").strip() for k in
                        ("marks_awarded", "marks", "grade", "absent", "notes"))
        if blank:
            todo.append((pid, None))
            continue
        c = _clean_result(data, paper, label, problems)
        if c is not None:
            todo.append((pid, c))
    if problems:
        raise ValidationError(problems)
    n = 0
    with database.connect() as conn:
        for pid, c in todo:
            if c is None:
                cur = conn.execute("DELETE FROM mock_results WHERE paper_id = ? AND pupil_id = ?",
                                   (paper.paper_id, pid))
                if cur.rowcount:
                    _audit(conn, series.series_id, "result.delete", actor,
                           {"paper_id": paper.paper_id}, pupil_id=pid)
                    n += 1
            elif _write_result(conn, paper, pid, c, actor):
                n += 1
    activity_log.record("mock.sheet", target=f"paper:{paper.paper_id}", principal=actor, rows=n)
    return n


def mark_sheet(paper_id: int) -> list[tuple[P.Pupil, MockResult | None, str | None]]:
    """Candidates with their result and exam access arrangements."""
    results = {r.pupil_id: r for r in list_results(paper_id)}
    access = access_arrangements(paper_id)
    return [(p, results.get(p.pupil_id), access.get(p.pupil_id))
            for p in candidates(paper_id)]


def delete_result(result_id: int, *, actor: Principal) -> bool:
    r = get_result(result_id)
    paper = get_paper(r.paper_id)
    series = get_series(paper.series_id)
    _marking_checks(paper, series, [r.pupil_id], actor, "mock.result.delete")
    with database.connect() as conn:
        conn.execute("DELETE FROM mock_results WHERE result_id = ?", (r.result_id,))
        _audit(conn, series.series_id, "result.delete", actor, {"paper_id": paper.paper_id},
               pupil_id=r.pupil_id)
    activity_log.record("mock.result.delete", target=f"paper:{paper.paper_id}", principal=actor)
    return True


# ── Subject grades ───────────────────────────────────────────────────

def _subject_grade(ps: list[MockPaper], res: dict[int, MockResult]) -> dict[str, Any]:
    """Total over *ps* (one subject + tier) for one pupil."""
    sat = [res[p.paper_id] for p in ps if p.paper_id in res]
    out: dict[str, Any] = {"papers": len(ps), "sat": sum(1 for r in sat if not r.absent),
                           "absent": sum(1 for r in sat if r.absent), "marks": None,
                           "max": sum(p.max_marks for p in ps), "pct": None, "grade": None,
                           "note": ""}
    missing = [p.paper_name for p in ps if p.paper_id not in res]
    if out["absent"]:
        out["note"] = "absent from " + ", ".join(p.paper_name for p in ps
                                                 if p.paper_id in res and res[p.paper_id].absent)
        return out
    if missing:
        out["note"] = "missing " + ", ".join(missing)
        return out
    if any(r.marks_awarded is None for r in sat):
        if len(sat) == 1:
            out["grade"] = sat[0].grade
        out["note"] = "grade only"
        return out
    total = sum(r.marks_awarded for r in sat)  # type: ignore[misc]
    out["marks"] = total
    out["pct"] = round(100 * total / out["max"], 1) if out["max"] else None
    if len(ps) == 1:
        out["grade"] = sat[0].grade
        return out
    common = set.intersection(*(set(p.boundaries) for p in ps)) if ps else set()
    tier = ps[0].tier
    summed = {g: sum(p.boundaries[g] for p in ps) for g in TIER_GRADES.get(tier, _SINGLE)
              if g in common}
    out["grade"] = grade_from(total, summed)
    if out["grade"] is None:
        out["note"] = "no boundaries"
    return out


def subject_results(series_id: int, *, subject_id: int | None = None,
                    pupil_id: int | None = None) -> list[dict[str, Any]]:
    """One row per pupil per subject (and tier) in the series: totals,
    percentage, subject grade, target and how they compare."""
    from education_system.systems.secondary.modules.assessment.domain import target_grades as TGR
    s = get_series(series_id)
    by_key: dict[tuple[int, str], list[MockPaper]] = {}
    for p in papers(s.series_id, subject_id=subject_id):
        by_key.setdefault((p.subject_id, p.tier), []).append(p)
    out = []
    for (sid, tier), ps in sorted(by_key.items(), key=lambda kv: (kv[1][0].subject_name,
                                                                  kv[0][1])):
        res: dict[int, dict[int, MockResult]] = {}
        for p in ps:
            for r in list_results(p.paper_id):
                if pupil_id is None or r.pupil_id == pupil_id:
                    res.setdefault(r.pupil_id, {})[p.paper_id] = r
        cands = {c.pupil_id: c for p in ps for c in candidates(p.paper_id)}
        for pid in sorted(set(res) | set(cands)):
            if pupil_id is not None and pid != pupil_id:
                continue
            pupil = cands.get(pid) or P.get_pupil(pid)
            if pupil is None:
                continue
            g = _subject_grade(ps, res.get(pid, {}))
            target = TGR.get_for(pid, sid)
            out.append({"pupil": pupil, "subject_id": sid, "subject_code": ps[0].subject_code,
                        "subject_name": ps[0].subject_name, "tier": tier, **g,
                        "target": target.target_grade if target else None,
                        "vs_target": compare(g["grade"], target.target_grade if target
                                             else None)})
    return out


def compare(grade: str | None, target: str | None) -> str:
    """Above / On track / Below / Well below against a target, or No data."""
    a, b = grade_value(grade), grade_value(target)
    if a is None or b is None:
        return "No data"
    gap = a - b
    return "Above" if gap > 0 else "On track" if gap == 0 else \
        "Below" if gap >= -1 else "Well below"


def latest_grades(pupil_id: int | None = None) -> dict[tuple[int, int], tuple[str, str, str]]:
    """(pupil, subject) -> (grade, series name, series end date) from the
    newest Complete / Archived series - used by Target Grades progress."""
    out: dict[tuple[int, int], tuple[str, str, str]] = {}
    for s in sorted(list_series(), key=lambda x: x.end_date):
        if s.status not in ("Complete", "Archived"):
            continue
        for row in subject_results(s.series_id, pupil_id=pupil_id):
            if row["grade"]:
                out[(row["pupil"].pupil_id, row["subject_id"])] = (row["grade"], s.name,
                                                                   s.end_date)
    return out


# ── Analysis ─────────────────────────────────────────────────────────

def paper_summary(paper_id: int) -> dict[str, Any]:
    """The old summary (count, absent, avg/min/max %, grades, results) plus
    median, candidates, missing and grade 4+ / 5+ counts."""
    paper = get_paper(paper_id)
    results = list_results(paper_id)
    pcts = [r.mark_pct for r in results if r.mark_pct is not None and not r.absent]
    grades = Counter(r.grade for r in results if r.grade)
    cands = candidates(paper_id)
    have = {r.pupil_id for r in results}
    vals = [grade_value(r.grade) for r in results if r.grade and not r.absent]
    return {
        "paper": paper, "count": len(results),
        "absent": sum(1 for r in results if r.absent),
        "avg_pct": round(sum(pcts) / len(pcts), 2) if pcts else None,
        "median_pct": round(statistics.median(pcts), 2) if pcts else None,
        "min_pct": min(pcts) if pcts else None, "max_pct": max(pcts) if pcts else None,
        "grades": dict(grades), "results": results, "candidates": len(cands),
        "missing": [p for p in cands if p.pupil_id not in have],
        "grade4": sum(1 for v in vals if v is not None and v >= 4),
        "grade5": sum(1 for v in vals if v is not None and v >= 5),
    }


def subject_summary(series_id: int) -> list[dict[str, Any]]:
    """Per subject: pupils, with a grade, average %, % 4+ / 5+ / 7+,
    grade distribution and how many are below target."""
    rows = subject_results(series_id)
    out = []
    by_sub: dict[int, list[dict]] = {}
    for r in rows:
        by_sub.setdefault(r["subject_id"], []).append(r)
    for sid, rs in by_sub.items():
        graded = [r for r in rs if r["grade"]]
        vals = [grade_value(r["grade"]) or 0 for r in graded]
        pcts = [r["pct"] for r in rs if r["pct"] is not None]

        def share(n: float) -> float | None:
            return round(100 * sum(1 for v in vals if v >= n) / len(vals), 1) if vals else None
        out.append({"subject_id": sid, "subject_code": rs[0]["subject_code"],
                    "subject_name": rs[0]["subject_name"], "pupils": len(rs),
                    "graded": len(graded), "avg_pct": round(sum(pcts) / len(pcts), 1)
                    if pcts else None, "pct4": share(4), "pct5": share(5), "pct7": share(7),
                    "distribution": dict(Counter(r["grade"] for r in graded)),
                    "below_target": sum(1 for r in rs if r["vs_target"] in ("Below",
                                                                            "Well below"))})
    return sorted(out, key=lambda x: x["subject_name"].lower())


def below_target(series_id: int, *, well_below_only: bool = False) -> list[dict[str, Any]]:
    want = {"Well below"} if well_below_only else {"Below", "Well below"}
    return [r for r in subject_results(series_id) if r["vs_target"] in want]


def compare_series(series_id: int, earlier_id: int) -> list[dict[str, Any]]:
    """Each pupil-subject graded in both: earlier grade, now, change."""
    before = {(r["pupil"].pupil_id, r["subject_id"]): r for r in subject_results(earlier_id)
              if r["grade"]}
    out = []
    for r in subject_results(series_id):
        b = before.get((r["pupil"].pupil_id, r["subject_id"]))
        if not (b and r["grade"]):
            continue
        change = (grade_value(r["grade"]) or 0) - (grade_value(b["grade"]) or 0)
        out.append({**r, "earlier": b["grade"], "change": change})
    return out


def missing_marks(series_id: int) -> list[tuple[MockPaper, list[P.Pupil]]]:
    """Papers with candidates who have no result (to chase)."""
    out = []
    for p in papers(series_id):
        have = {r.pupil_id for r in list_results(p.paper_id)}
        miss = [c for c in candidates(p.paper_id) if c.pupil_id not in have]
        if miss:
            out.append((p, miss))
    return out


def pupil_report(series_id: int, pupil_id: int) -> dict[str, Any]:
    """One pupil's series: each subject's grade against target, and the
    papers behind it."""
    s = get_series(series_id)
    pupil = P.get_pupil(int(pupil_id))
    if pupil is None:
        raise NotFound(f"No pupil with id {pupil_id}")
    subjects = subject_results(s.series_id, pupil_id=pupil.pupil_id)
    res = {r.paper_id: r for _s, _p, r in results_for_pupil(pupil.pupil_id)
           if _s.series_id == s.series_id}
    return {"series": s, "pupil": pupil, "subjects": subjects,
            "papers": [(p, res.get(p.paper_id)) for p in papers(s.series_id)
                       if p.paper_id in res]}


# ── Timetable ────────────────────────────────────────────────────────

def access_arrangements(paper_id: int) -> dict[int, str]:
    """Candidates with exam access arrangements (from SEN details)."""
    from education_system.systems.secondary.modules.pupils.domain import sen_details as SEN
    out = {}
    for c in candidates(paper_id):
        d = SEN.get(c.pupil_id)
        if d and d.exam_access:
            out[c.pupil_id] = d.exam_access
    return out


def timetable(series_id: int) -> list[dict[str, Any]]:
    """Papers in date/time order with candidate numbers, access
    arrangements and clashes."""
    ps = papers(series_id)
    cands = {p.paper_id: {c.pupil_id for c in candidates(p.paper_id)} for p in ps}
    out = []
    for p in ps:
        clashes = []
        w = p.window()
        for q in ps:
            if q.paper_id == p.paper_id or q.paper_date != p.paper_date:
                continue
            v = q.window()
            same = cands[p.paper_id] & cands[q.paper_id]
            if same and w and v and w[0] < v[1] and v[0] < w[1]:
                clashes.append((q, len(same)))
        out.append({"paper": p, "candidates": len(cands[p.paper_id]),
                    "access": len(access_arrangements(p.paper_id)), "clashes": clashes})
    return out


def clashes(series_id: int) -> list[tuple[MockPaper, MockPaper, list[P.Pupil]]]:
    """Pairs of overlapping papers and the pupils down for both."""
    ps = papers(series_id)
    cands = {p.paper_id: {c.pupil_id: c for c in candidates(p.paper_id)} for p in ps}
    out = []
    for i, p in enumerate(ps):
        for q in ps[i + 1:]:
            w, v = p.window(), q.window()
            if p.paper_date != q.paper_date or not (w and v and w[0] < v[1] and v[0] < w[1]):
                continue
            both = [cands[p.paper_id][k] for k in cands[p.paper_id] if k in cands[q.paper_id]]
            if both:
                out.append((p, q, both))
    return out


# ── CSV ──────────────────────────────────────────────────────────────

def import_marks(paper_id: int, path: str | Path, *, actor: Principal) -> int:
    """Marks for one paper: Admission no, Marks, and optionally Grade,
    Absent (Y), Absence reason, Notes. All or nothing (see save_sheet); every
    problem is reported by row, and a row with no mark, grade or absence is
    skipped rather than clearing the pupil's result."""
    paper = get_paper(paper_id)
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        heads = {h.strip().lower(): h for h in (reader.fieldnames or [])}
        if "admission no" not in heads or not ({"marks", "grade", "absent"} & set(heads)):
            raise ValidationError(["The file needs 'Admission no' and 'Marks' (or 'Grade' / "
                                   "'Absent') columns"])
        lines = list(reader)
    keys = {"marks": "marks_awarded", "grade": "grade", "absent": "absent",
            "absence reason": "absence_reason", "notes": "notes"}
    rows: dict[int, dict] = {}
    problems = []
    for i, r in enumerate(lines, 2):
        ref = (r.get(heads["admission no"]) or "").strip()
        if not ref:
            continue
        p = P.find_by_reference(ref)
        if p is None:
            problems.append(f"Row {i}: no pupil {ref}")
            continue
        if p.pupil_id in rows:
            problems.append(f"Row {i}: {ref} appears twice")
            continue
        data = {k: (r.get(heads[h]) or "").strip() for h, k in keys.items() if h in heads}
        if not any(data.get(k) for k in ("marks_awarded", "grade", "absent")):
            continue  # a row left blank on the sheet keeps what is there
        _clean_result(data, paper, f"Row {i} ({ref}): ", problems)
        rows[p.pupil_id] = data
    if problems:
        raise ValidationError(problems)
    n = save_sheet(paper.paper_id, rows, actor=actor)
    activity_log.record("mock.import", target=f"paper:{paper.paper_id}", principal=actor, rows=n)
    return n


def export_results(series_id: int, path: str | Path, *, actor: Principal) -> int:
    """Subject grades for the series, one row per pupil per subject."""
    if not actor.is_staff:
        raise PermissionDenied("Only school staff can export results.")
    s = get_series(series_id)
    rows = subject_results(s.series_id)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Admission no", "Pupil", "Subject", "Tier", "Marks", "Out of", "%",
                    "Grade", "Target", "Against target", "Note"])
        for r in rows:
            w.writerow([_safe(v) for v in (
                r["pupil"].admission_no, r["pupil"].display_name, r["subject_code"], r["tier"],
                _num(r["marks"]), _num(r["max"]), r["pct"], r["grade"], r["target"],
                r["vs_target"], r["note"])])
    activity_log.record("mock.export", target=f"series:{s.series_id}", principal=actor,
                        rows=len(rows))
    return len(rows)


def export_sheet_template(paper_id: int, path: str | Path, *, actor: Principal) -> int:
    """A mark-entry CSV for the paper's candidates, to fill in and import."""
    if not actor.is_staff:
        raise PermissionDenied("Only school staff can export mark sheets.")
    sheet = mark_sheet(paper_id)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Admission no", "Pupil", "Marks", "Grade", "Absent", "Absence reason",
                    "Notes"])
        for p, r, _a in sheet:
            w.writerow([_safe(v) for v in (
                p.admission_no, p.display_name, _num(r.marks_awarded) if r else "",
                (r.grade if r and r.grade_source == "manual" else ""),
                "Y" if r and r.absent else "", r.absence_reason if r else "",
                r.notes if r else "")])
    return len(sheet)


S.register_usage("mock_papers", "subject_id", "mock exam paper(s)")
