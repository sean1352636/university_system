"""Mock-exam data layer for the Secondary School System.

Three tables:

* ``mock_series``  — named mock window (e.g. "Year 11 Nov Mocks 2025").
                      Has a status workflow Planned → InProgress → Complete
                      → Archived.
* ``mock_papers``  — one row per paper sat inside a series (subject +
                      paper name + date + max_marks + tier).
* ``mock_results`` — one row per pupil per paper (marks + grade).
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

SERIES_STATUSES: tuple[str, ...] = (
    "Planned", "InProgress", "Complete", "Archived")
DEFAULT_SERIES_STATUS: str = "Planned"

PAPER_TIERS: tuple[str, ...] = ("Foundation", "Higher", "Combined", "N/A")
DEFAULT_TIER: str = "N/A"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_GRADE_RE = re.compile(r"^[A-Za-z0-9*+\-]{1,3}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS mock_series (
    series_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL UNIQUE,
    year_group       TEXT NOT NULL,
    start_date       TEXT NOT NULL,
    end_date         TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'Planned',
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS mock_papers (
    paper_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id        INTEGER NOT NULL,
    subject_id       INTEGER NOT NULL,
    paper_name       TEXT NOT NULL,
    paper_date       TEXT NOT NULL,
    max_marks        REAL NOT NULL,
    tier             TEXT NOT NULL DEFAULT 'N/A',
    grade_boundaries TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    UNIQUE (series_id, subject_id, paper_name),
    FOREIGN KEY (series_id) REFERENCES mock_series(series_id)
        ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
);

CREATE TABLE IF NOT EXISTS mock_results (
    result_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id         INTEGER NOT NULL,
    pupil_id         TEXT NOT NULL,
    marks_awarded    REAL,
    mark_pct         REAL,
    grade            TEXT,
    absent           INTEGER NOT NULL DEFAULT 0,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    UNIQUE (paper_id, pupil_id),
    FOREIGN KEY (paper_id) REFERENCES mock_papers(paper_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mock_papers_series
    ON mock_papers(series_id);
CREATE INDEX IF NOT EXISTS idx_mock_results_pupil
    ON mock_results(pupil_id);
"""


@dataclass
class MockSeries:
    series_id: int
    name: str
    year_group: str
    start_date: str
    end_date: str
    status: str
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class MockPaper:
    paper_id: int
    series_id: int
    subject_id: int
    paper_name: str
    paper_date: str
    max_marks: float
    tier: str
    grade_boundaries: str | None
    notes: str | None
    subject_code: str | None = None
    subject_name: str | None = None
    series_name: str | None = None
    series_year: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class MockResult:
    result_id: int
    paper_id: int
    pupil_id: str
    marks_awarded: float | None
    mark_pct: float | None
    grade: str | None
    absent: bool
    notes: str | None
    paper_name: str | None = None
    paper_max: float | None = None
    subject_code: str | None = None
    pupil_name: str | None = None
    pupil_year: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.secondary.domain.academics.subjects import (
        subjects as subjects_data,
    )
    subjects_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise mock_exams tables")
        raise
    logger.info("Secondary mock_exams tables ready")
    _DB_READY = True


def _row_series(r: sqlite3.Row) -> MockSeries:
    return MockSeries(
        series_id=r["series_id"], name=r["name"],
        year_group=r["year_group"], start_date=r["start_date"],
        end_date=r["end_date"], status=r["status"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_paper(r: sqlite3.Row) -> MockPaper:
    keys = r.keys()
    return MockPaper(
        paper_id=r["paper_id"], series_id=r["series_id"],
        subject_id=r["subject_id"],
        paper_name=r["paper_name"], paper_date=r["paper_date"],
        max_marks=r["max_marks"], tier=r["tier"],
        grade_boundaries=r["grade_boundaries"], notes=r["notes"],
        subject_code=r["subject_code"] if "subject_code" in keys else None,
        subject_name=r["subject_name"] if "subject_name" in keys else None,
        series_name=r["series_name"] if "series_name" in keys else None,
        series_year=r["series_year"] if "series_year" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_result(r: sqlite3.Row) -> MockResult:
    keys = r.keys()
    return MockResult(
        result_id=r["result_id"], paper_id=r["paper_id"],
        pupil_id=r["pupil_id"],
        marks_awarded=r["marks_awarded"], mark_pct=r["mark_pct"],
        grade=r["grade"], absent=bool(r["absent"]),
        notes=r["notes"],
        paper_name=r["paper_name"] if "paper_name" in keys else None,
        paper_max=r["paper_max"] if "paper_max" in keys else None,
        subject_code=r["subject_code"] if "subject_code" in keys else None,
        pupil_name=r["pupil_name"] if "pupil_name" in keys else None,
        pupil_year=r["pupil_year"] if "pupil_year" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_date(value: Any, label: str) -> str:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _opt_float(value, label, *, mn, mx):
    if value in (None, "") or (isinstance(value, str)
                                and not value.strip()):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number") from None
    if v < mn or v > mx:
        raise ValidationError(
            f"{label} must be between {mn} and {mx}")
    return v


# ── Series CRUD ──────────────────────────────────────────────────

def _validate_series(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    name = (data.get("name") or "").strip()
    if not name:
        raise ValidationError("Series name is required")
    if len(name) > 80:
        raise ValidationError("Series name must be 80 characters or fewer")
    out["name"] = name
    yg = (data.get("year_group") or "").strip()
    if not yg:
        raise ValidationError("Year group is required")
    if yg not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of {', '.join(YEAR_GROUPS)}")
    out["year_group"] = yg
    out["start_date"] = _validate_date(data.get("start_date"),
                                         "Start date")
    out["end_date"]   = _validate_date(data.get("end_date"), "End date")
    if out["end_date"] < out["start_date"]:
        raise ValidationError("End date cannot be before start date")
    status = (data.get("status") or DEFAULT_SERIES_STATUS).strip()
    if status not in SERIES_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(SERIES_STATUSES)}")
    out["status"] = status
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def create_series(data: dict[str, Any]) -> MockSeries:
    init_db()
    payload = _validate_series(data)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT series_id FROM mock_series WHERE name = ?",
                (payload["name"],),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"A mock series named {payload['name']!r} "
                    f"already exists")
            cur = conn.execute(
                """INSERT INTO mock_series
                       (name, year_group, start_date, end_date,
                        status, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (payload["name"], payload["year_group"],
                 payload["start_date"], payload["end_date"],
                 payload["status"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create mock series")
        raise
    rec = get_series(new_id)
    assert rec is not None
    logger.info("Created mock series #%d %r (Yr%s, %s..%s)",
                rec.series_id, rec.name, rec.year_group,
                rec.start_date, rec.end_date)
    return rec


def get_series(series_id: int) -> MockSeries | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM mock_series WHERE series_id = ?",
                (series_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_series(%s) failed", series_id)
        raise
    return _row_series(r) if r else None


def list_series(*, year_group: str | None = None,
                status: str | None = None) -> list[MockSeries]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("year_group = ?")
        params.append(year_group)
    if status:
        if status not in SERIES_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(SERIES_STATUSES)}")
        where.append("status = ?")
        params.append(status)
    sql = "SELECT * FROM mock_series"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY start_date DESC, series_id DESC"
    try:
        with _connect() as conn:
            return [_row_series(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_series failed")
        raise


def update_series(series_id: int, data: dict[str, Any]) -> MockSeries:
    init_db()
    existing = get_series(series_id)
    if existing is None:
        raise ValidationError(f"No mock series #{series_id}")
    merged = {
        "name":       data.get("name", existing.name),
        "year_group": data.get("year_group", existing.year_group),
        "start_date": data.get("start_date", existing.start_date),
        "end_date":   data.get("end_date", existing.end_date),
        "status":     data.get("status", existing.status),
        "notes":      data.get("notes", existing.notes),
    }
    payload = _validate_series(merged)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT series_id FROM mock_series "
                "WHERE name = ? AND series_id <> ?",
                (payload["name"], series_id),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"A mock series named {payload['name']!r} "
                    f"already exists")
            conn.execute(
                """UPDATE mock_series SET
                       name = ?, year_group = ?, start_date = ?,
                       end_date = ?, status = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE series_id = ?""",
                (payload["name"], payload["year_group"],
                 payload["start_date"], payload["end_date"],
                 payload["status"], payload["notes"], series_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update mock series #%d", series_id)
        raise
    rec = get_series(series_id)
    assert rec is not None
    logger.info("Updated mock series #%d (status %s)",
                rec.series_id, rec.status)
    return rec


def set_series_status(series_id: int, status: str) -> MockSeries:
    return update_series(series_id, {"status": status})


def delete_series(series_id: int) -> bool:
    init_db()
    existing = get_series(series_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            cur = conn.execute(
                "DELETE FROM mock_series WHERE series_id = ?",
                (series_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete mock series #%d", series_id)
        raise
    if deleted:
        logger.info("Deleted mock series #%d %r "
                    "(cascade: papers + results)",
                    series_id, existing.name)
    return deleted


# ── Papers ───────────────────────────────────────────────────────

def _validate_paper(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    sid_raw = data.get("series_id")
    if sid_raw in (None, ""):
        raise ValidationError("Series is required")
    try:
        out["series_id"] = int(sid_raw)
    except (TypeError, ValueError):
        raise ValidationError("Series ID must be a number") from None
    if get_series(out["series_id"]) is None:
        raise ValidationError(f"No mock series #{out['series_id']}")

    subj_raw = data.get("subject_id")
    if subj_raw in (None, ""):
        raise ValidationError("Subject is required")
    try:
        out["subject_id"] = int(subj_raw)
    except (TypeError, ValueError):
        raise ValidationError("Subject ID must be a number") from None
    from education_system.systems.secondary.domain.academics.subjects import (
        subjects as subjects_data,
    )
    if subjects_data.get(out["subject_id"]) is None:
        raise ValidationError(f"No subject #{out['subject_id']}")

    name = (data.get("paper_name") or "").strip()
    if not name:
        raise ValidationError("Paper name is required")
    if len(name) > 64:
        raise ValidationError("Paper name must be 64 characters or fewer")
    out["paper_name"] = name

    out["paper_date"] = _validate_date(data.get("paper_date"),
                                         "Paper date")

    max_marks = _opt_float(data.get("max_marks"),
                            "Max marks", mn=0.001, mx=10000)
    if max_marks is None:
        raise ValidationError("Max marks is required")
    out["max_marks"] = max_marks

    tier = (data.get("tier") or DEFAULT_TIER).strip()
    if tier not in PAPER_TIERS:
        raise ValidationError(
            f"Tier must be one of {', '.join(PAPER_TIERS)}")
    out["tier"] = tier
    out["grade_boundaries"] = (data.get("grade_boundaries") or "").strip() or None
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def create_paper(data: dict[str, Any]) -> MockPaper:
    init_db()
    payload = _validate_paper(data)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT paper_id FROM mock_papers "
                "WHERE series_id = ? AND subject_id = ? "
                "  AND paper_name = ?",
                (payload["series_id"], payload["subject_id"],
                 payload["paper_name"]),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"A paper {payload['paper_name']!r} for that "
                    f"subject in that series already exists")
            cur = conn.execute(
                """INSERT INTO mock_papers
                       (series_id, subject_id, paper_name, paper_date,
                        max_marks, tier, grade_boundaries, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["series_id"], payload["subject_id"],
                 payload["paper_name"], payload["paper_date"],
                 payload["max_marks"], payload["tier"],
                 payload["grade_boundaries"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create mock paper")
        raise
    rec = get_paper(new_id)
    assert rec is not None
    logger.info("Created mock paper #%d series=#%d subject=#%d %r "
                "(date %s, max %s)",
                rec.paper_id, rec.series_id, rec.subject_id,
                rec.paper_name, rec.paper_date, rec.max_marks)
    return rec


def get_paper(paper_id: int) -> MockPaper | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT p.*, s.code AS subject_code,
                          s.name AS subject_name,
                          ms.name AS series_name,
                          ms.year_group AS series_year
                   FROM mock_papers p
                   LEFT JOIN subjects s ON s.subject_id = p.subject_id
                   LEFT JOIN mock_series ms ON ms.series_id = p.series_id
                   WHERE p.paper_id = ?""",
                (paper_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_paper(%s) failed", paper_id)
        raise
    return _row_paper(r) if r else None


def list_papers(series_id: int) -> list[MockPaper]:
    init_db()
    try:
        with _connect() as conn:
            return [_row_paper(r) for r in conn.execute(
                """SELECT p.*, s.code AS subject_code,
                          s.name AS subject_name,
                          ms.name AS series_name,
                          ms.year_group AS series_year
                   FROM mock_papers p
                   LEFT JOIN subjects s ON s.subject_id = p.subject_id
                   LEFT JOIN mock_series ms ON ms.series_id = p.series_id
                   WHERE p.series_id = ?
                   ORDER BY p.paper_date, s.name, p.paper_name""",
                (series_id,),
            ).fetchall()]
    except sqlite3.Error:
        logger.exception("list_papers(%s) failed", series_id)
        raise


def update_paper(paper_id: int, data: dict[str, Any]) -> MockPaper:
    init_db()
    existing = get_paper(paper_id)
    if existing is None:
        raise ValidationError(f"No mock paper #{paper_id}")
    merged = {
        "series_id":        existing.series_id,
        "subject_id":       data.get("subject_id", existing.subject_id),
        "paper_name":       data.get("paper_name", existing.paper_name),
        "paper_date":       data.get("paper_date", existing.paper_date),
        "max_marks":        data.get("max_marks", existing.max_marks),
        "tier":             data.get("tier", existing.tier),
        "grade_boundaries": data.get("grade_boundaries",
                                       existing.grade_boundaries),
        "notes":            data.get("notes", existing.notes),
    }
    payload = _validate_paper(merged)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT paper_id FROM mock_papers "
                "WHERE series_id = ? AND subject_id = ? "
                "  AND paper_name = ? AND paper_id <> ?",
                (payload["series_id"], payload["subject_id"],
                 payload["paper_name"], paper_id),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"Another paper {payload['paper_name']!r} for that "
                    f"subject in that series already exists")
            conn.execute(
                """UPDATE mock_papers SET
                       subject_id = ?, paper_name = ?, paper_date = ?,
                       max_marks = ?, tier = ?,
                       grade_boundaries = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE paper_id = ?""",
                (payload["subject_id"], payload["paper_name"],
                 payload["paper_date"], payload["max_marks"],
                 payload["tier"], payload["grade_boundaries"],
                 payload["notes"], paper_id),
            )
            # If max_marks changed, recompute mark_pct on results.
            if payload["max_marks"] != existing.max_marks:
                conn.execute(
                    "UPDATE mock_results SET "
                    "mark_pct = CASE "
                    "  WHEN marks_awarded IS NULL THEN NULL "
                    "  ELSE ROUND(100.0 * marks_awarded / ?, 2) "
                    "END WHERE paper_id = ?",
                    (payload["max_marks"], paper_id),
                )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update mock paper #%d", paper_id)
        raise
    rec = get_paper(paper_id)
    assert rec is not None
    logger.info("Updated mock paper #%d", rec.paper_id)
    return rec


def delete_paper(paper_id: int) -> bool:
    init_db()
    existing = get_paper(paper_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            cur = conn.execute(
                "DELETE FROM mock_papers WHERE paper_id = ?",
                (paper_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete mock paper #%d", paper_id)
        raise
    if deleted:
        logger.info("Deleted mock paper #%d (cascade: results)",
                    paper_id)
    return deleted


# ── Results ──────────────────────────────────────────────────────

def _validate_result(data: dict[str, Any], paper: MockPaper
                      ) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid = (data.get("pupil_id") or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    from education_system.systems.secondary.domain.learners.pupils import (
        pupils as pupils_data,
    )
    if pupils_data.get_pupil(pid) is None:
        raise ValidationError(f"No pupil with id {pid}")
    out["pupil_id"] = pid

    absent = bool(data.get("absent"))
    out["absent"] = absent

    if absent:
        out["marks_awarded"] = None
        out["mark_pct"] = None
    else:
        marks = _opt_float(data.get("marks_awarded"),
                            "Marks awarded", mn=0,
                            mx=paper.max_marks)
        out["marks_awarded"] = marks
        out["mark_pct"] = (round(100.0 * marks / paper.max_marks, 2)
                            if marks is not None else None)

    grade = (data.get("grade") or "").strip()
    if grade:
        if not _GRADE_RE.match(grade):
            raise ValidationError(
                "Grade must be 1–3 chars (letters/digits/* + -)")
        out["grade"] = grade
    else:
        out["grade"] = None

    out["notes"] = (data.get("notes") or "").strip() or None
    if (not absent and out["marks_awarded"] is None
            and out["grade"] is None):
        raise ValidationError(
            "Either marks_awarded or grade is required when not absent")
    return out


def upsert_result(paper_id: int,
                   data: dict[str, Any]) -> MockResult:
    init_db()
    paper = get_paper(paper_id)
    if paper is None:
        raise ValidationError(f"No mock paper #{paper_id}")
    payload = _validate_result(data, paper)
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT result_id FROM mock_results "
                "WHERE paper_id = ? AND pupil_id = ?",
                (paper_id, payload["pupil_id"]),
            ).fetchone()
            if row:
                conn.execute(
                    """UPDATE mock_results SET
                           marks_awarded = ?, mark_pct = ?,
                           grade = ?, absent = ?, notes = ?,
                           updated_at = datetime('now')
                       WHERE result_id = ?""",
                    (payload["marks_awarded"], payload["mark_pct"],
                     payload["grade"],
                     1 if payload["absent"] else 0,
                     payload["notes"], row["result_id"]),
                )
                rid = row["result_id"]
                action = "updated"
            else:
                cur = conn.execute(
                    """INSERT INTO mock_results
                           (paper_id, pupil_id, marks_awarded,
                            mark_pct, grade, absent, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (paper_id, payload["pupil_id"],
                     payload["marks_awarded"], payload["mark_pct"],
                     payload["grade"],
                     1 if payload["absent"] else 0,
                     payload["notes"]),
                )
                rid = cur.lastrowid
                action = "inserted"
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to upsert mock result for paper %d pupil %s",
            paper_id, payload["pupil_id"])
        raise
    logger.info(
        "Mock result %s: paper=#%d pupil=%s marks=%s grade=%s absent=%s",
        action, paper_id, payload["pupil_id"],
        payload["marks_awarded"], payload["grade"], payload["absent"])
    rec = get_result(rid)
    assert rec is not None
    return rec


def get_result(result_id: int) -> MockResult | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT mr.*, p.paper_name AS paper_name,
                          p.max_marks AS paper_max,
                          s.code AS subject_code,
                          (pu.first_name || ' ' || pu.last_name) AS pupil_name,
                          pu.year_group AS pupil_year
                   FROM mock_results mr
                   LEFT JOIN mock_papers p ON p.paper_id = mr.paper_id
                   LEFT JOIN subjects s ON s.subject_id = p.subject_id
                   LEFT JOIN pupils pu ON pu.pupil_id = mr.pupil_id
                   WHERE mr.result_id = ?""",
                (result_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_result(%s) failed", result_id)
        raise
    return _row_result(r) if r else None


def list_results(paper_id: int) -> list[MockResult]:
    init_db()
    try:
        with _connect() as conn:
            return [_row_result(r) for r in conn.execute(
                """SELECT mr.*, p.paper_name AS paper_name,
                          p.max_marks AS paper_max,
                          s.code AS subject_code,
                          (pu.first_name || ' ' || pu.last_name) AS pupil_name,
                          pu.year_group AS pupil_year
                   FROM mock_results mr
                   LEFT JOIN mock_papers p ON p.paper_id = mr.paper_id
                   LEFT JOIN subjects s ON s.subject_id = p.subject_id
                   LEFT JOIN pupils pu ON pu.pupil_id = mr.pupil_id
                   WHERE mr.paper_id = ?
                   ORDER BY mr.pupil_id""",
                (paper_id,),
            ).fetchall()]
    except sqlite3.Error:
        logger.exception("list_results(%s) failed", paper_id)
        raise


def results_for_pupil(pupil_id: str) -> list[MockResult]:
    init_db()
    pid = (pupil_id or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    try:
        with _connect() as conn:
            return [_row_result(r) for r in conn.execute(
                """SELECT mr.*, p.paper_name AS paper_name,
                          p.max_marks AS paper_max,
                          s.code AS subject_code,
                          (pu.first_name || ' ' || pu.last_name) AS pupil_name,
                          pu.year_group AS pupil_year
                   FROM mock_results mr
                   LEFT JOIN mock_papers p ON p.paper_id = mr.paper_id
                   LEFT JOIN subjects s ON s.subject_id = p.subject_id
                   LEFT JOIN pupils pu ON pu.pupil_id = mr.pupil_id
                   WHERE mr.pupil_id = ?
                   ORDER BY p.paper_date DESC""",
                (pid,),
            ).fetchall()]
    except sqlite3.Error:
        logger.exception("results_for_pupil(%s) failed", pupil_id)
        raise


def delete_result(result_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM mock_results WHERE result_id = ?",
                (result_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete mock result #%d", result_id)
        raise
    if deleted:
        logger.info("Deleted mock result #%d", result_id)
    return deleted


def paper_summary(paper_id: int) -> dict[str, Any]:
    init_db()
    paper = get_paper(paper_id)
    if paper is None:
        raise ValidationError(f"No mock paper #{paper_id}")
    results = list_results(paper_id)
    pcts = [r.mark_pct for r in results
            if r.mark_pct is not None and not r.absent]
    grades = Counter(r.grade for r in results if r.grade)
    absent = sum(1 for r in results if r.absent)
    return {
        "paper":    paper,
        "count":    len(results),
        "absent":   absent,
        "avg_pct":  round(sum(pcts) / len(pcts), 2) if pcts else None,
        "min_pct":  min(pcts) if pcts else None,
        "max_pct":  max(pcts) if pcts else None,
        "grades":   dict(grades),
        "results":  results,
    }
