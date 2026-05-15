"""Baseline-assessment data layer for the Secondary School System.

Two tables:

* ``baseline_tests``    — one row per baseline test the school has set
                           (e.g. "Year 7 Sept Maths"). Has a subject,
                           year group, date, max_marks, type
                           (CAT4/MidYIS/YELLIS/School/Other).
* ``baseline_results``  — one row per pupil per test. Records the raw
                           marks, derived mark %, an optional
                           standardised_score (for CAT4-style tests),
                           and a baseline_grade string.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

TEST_TYPES: tuple[str, ...] = (
    "CAT4", "MidYIS", "YELLIS", "KS2", "School", "Other")
DEFAULT_TEST_TYPE: str = "School"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_GRADE_RE = re.compile(r"^[A-Za-z0-9*+\-]{1,3}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS baseline_tests (
    test_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL,
    subject_id       INTEGER,
    year_group       TEXT NOT NULL,
    test_type        TEXT NOT NULL DEFAULT 'School',
    test_date        TEXT NOT NULL DEFAULT (date('now')),
    max_marks        REAL,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    UNIQUE (name, year_group, test_date),
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
);

CREATE TABLE IF NOT EXISTS baseline_results (
    result_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id              INTEGER NOT NULL,
    pupil_id             TEXT NOT NULL,
    marks_awarded        REAL,
    mark_pct             REAL,
    standardised_score   REAL,
    baseline_grade       TEXT,
    notes                TEXT,
    created_at           TEXT DEFAULT (datetime('now')),
    updated_at           TEXT DEFAULT (datetime('now')),
    UNIQUE (test_id, pupil_id),
    FOREIGN KEY (test_id) REFERENCES baseline_tests(test_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_blt_year ON baseline_tests(year_group);
CREATE INDEX IF NOT EXISTS idx_blr_pupil ON baseline_results(pupil_id);
"""


@dataclass
class BaselineTest:
    test_id: int
    name: str
    subject_id: int | None
    year_group: str
    test_type: str
    test_date: str
    max_marks: float | None
    notes: str | None
    subject_code: str | None = None
    subject_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class BaselineResult:
    result_id: int
    test_id: int
    pupil_id: str
    marks_awarded: float | None
    mark_pct: float | None
    standardised_score: float | None
    baseline_grade: str | None
    notes: str | None
    test_name: str | None = None
    test_max: float | None = None
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
    from education_system.secondarysch_system.modules.domain.academics.subjects import (
        subjects as subjects_data,
    )
    subjects_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise baseline_assessment tables")
        raise
    logger.info("Secondary baseline_assessment tables ready")
    _DB_READY = True


def _row_test(r: sqlite3.Row) -> BaselineTest:
    keys = r.keys()
    return BaselineTest(
        test_id=r["test_id"], name=r["name"],
        subject_id=r["subject_id"], year_group=r["year_group"],
        test_type=r["test_type"], test_date=r["test_date"],
        max_marks=r["max_marks"], notes=r["notes"],
        subject_code=r["subject_code"] if "subject_code" in keys else None,
        subject_name=r["subject_name"] if "subject_name" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_result(r: sqlite3.Row) -> BaselineResult:
    keys = r.keys()
    return BaselineResult(
        result_id=r["result_id"], test_id=r["test_id"],
        pupil_id=r["pupil_id"],
        marks_awarded=r["marks_awarded"],
        mark_pct=r["mark_pct"],
        standardised_score=r["standardised_score"],
        baseline_grade=r["baseline_grade"], notes=r["notes"],
        test_name=r["test_name"] if "test_name" in keys else None,
        test_max=r["test_max"] if "test_max" in keys else None,
        pupil_name=r["pupil_name"] if "pupil_name" in keys else None,
        pupil_year=r["pupil_year"] if "pupil_year" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_date(value: Any, label: str) -> str:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return _dt.date.today().isoformat()
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


def _validate_test(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    name = (data.get("name") or "").strip()
    if not name:
        raise ValidationError("Test name is required")
    if len(name) > 80:
        raise ValidationError("Test name must be 80 characters or fewer")
    out["name"] = name

    sid_raw = data.get("subject_id")
    if sid_raw in (None, "") or (isinstance(sid_raw, str)
                                  and not sid_raw.strip()):
        out["subject_id"] = None
    else:
        try:
            sid = int(sid_raw)
        except (TypeError, ValueError):
            raise ValidationError(
                "Subject ID must be a number") from None
        from education_system.secondarysch_system.modules.domain.academics.subjects import (
            subjects as subjects_data,
        )
        if subjects_data.get(sid) is None:
            raise ValidationError(f"No subject #{sid}")
        out["subject_id"] = sid

    yg = (data.get("year_group") or "").strip()
    if not yg:
        raise ValidationError("Year group is required")
    if yg not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of {', '.join(YEAR_GROUPS)}")
    out["year_group"] = yg

    ttype = (data.get("test_type") or DEFAULT_TEST_TYPE).strip()
    if ttype not in TEST_TYPES:
        raise ValidationError(
            f"Test type must be one of {', '.join(TEST_TYPES)}")
    out["test_type"] = ttype

    out["test_date"] = _validate_date(data.get("test_date"), "Test date")
    out["max_marks"] = _opt_float(data.get("max_marks"),
                                    "Max marks", mn=0, mx=10000)
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def _validate_result(data: dict[str, Any],
                      max_marks: float | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid = (data.get("pupil_id") or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    from education_system.secondarysch_system.modules.domain.pupils.pupils import (
        pupils as pupils_data,
    )
    if pupils_data.get_pupil(pid) is None:
        raise ValidationError(f"No pupil with id {pid}")
    out["pupil_id"] = pid

    marks = _opt_float(data.get("marks_awarded"),
                        "Marks awarded", mn=0, mx=10000)
    if marks is not None and max_marks is not None and marks > max_marks:
        raise ValidationError(
            f"Marks awarded ({marks}) exceeds max marks ({max_marks})")
    out["marks_awarded"] = marks
    out["mark_pct"] = (round(100.0 * marks / max_marks, 2)
                       if marks is not None and max_marks else None)

    out["standardised_score"] = _opt_float(
        data.get("standardised_score"),
        "Standardised score", mn=40, mx=160)

    grade = (data.get("baseline_grade") or "").strip()
    if grade:
        if not _GRADE_RE.match(grade):
            raise ValidationError(
                "Baseline grade must be 1–3 chars (letters/digits/* + -)")
        out["baseline_grade"] = grade
    else:
        out["baseline_grade"] = None

    out["notes"] = (data.get("notes") or "").strip() or None
    if (out["marks_awarded"] is None
            and out["standardised_score"] is None
            and out["baseline_grade"] is None):
        raise ValidationError(
            "At least one of marks_awarded, standardised_score, "
            "or baseline_grade must be set")
    return out


# ── Test CRUD ────────────────────────────────────────────────────

def create_test(data: dict[str, Any]) -> BaselineTest:
    init_db()
    payload = _validate_test(data)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT test_id FROM baseline_tests "
                "WHERE name = ? AND year_group = ? AND test_date = ?",
                (payload["name"], payload["year_group"],
                 payload["test_date"]),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"A test named {payload['name']!r} for Year "
                    f"{payload['year_group']} on {payload['test_date']} "
                    f"already exists")
            cur = conn.execute(
                """INSERT INTO baseline_tests
                       (name, subject_id, year_group, test_type,
                        test_date, max_marks, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (payload["name"], payload["subject_id"],
                 payload["year_group"], payload["test_type"],
                 payload["test_date"], payload["max_marks"],
                 payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create baseline test")
        raise
    rec = get_test(new_id)
    assert rec is not None
    logger.info(
        "Created baseline test #%d %r (Yr%s, %s, date %s, max=%s)",
        rec.test_id, rec.name, rec.year_group, rec.test_type,
        rec.test_date, rec.max_marks)
    return rec


def get_test(test_id: int) -> BaselineTest | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT t.*, s.code AS subject_code,
                          s.name AS subject_name
                   FROM baseline_tests t
                   LEFT JOIN subjects s ON s.subject_id = t.subject_id
                   WHERE t.test_id = ?""",
                (test_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_test(%s) failed", test_id)
        raise
    return _row_test(r) if r else None


def list_tests(*, year_group: str | None = None,
               test_type: str | None = None,
               subject_id: int | None = None) -> list[BaselineTest]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("t.year_group = ?")
        params.append(year_group)
    if test_type:
        if test_type not in TEST_TYPES:
            raise ValidationError(
                f"Type filter must be one of {', '.join(TEST_TYPES)}")
        where.append("t.test_type = ?")
        params.append(test_type)
    if subject_id is not None:
        where.append("t.subject_id = ?")
        params.append(int(subject_id))
    sql = ("""SELECT t.*, s.code AS subject_code,
                     s.name AS subject_name
              FROM baseline_tests t
              LEFT JOIN subjects s ON s.subject_id = t.subject_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY t.test_date DESC, t.test_id DESC"
    try:
        with _connect() as conn:
            return [_row_test(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_tests failed")
        raise


def update_test(test_id: int, data: dict[str, Any]) -> BaselineTest:
    init_db()
    existing = get_test(test_id)
    if existing is None:
        raise ValidationError(f"No baseline test #{test_id}")
    merged = {
        "name":       data.get("name", existing.name),
        "subject_id": data.get("subject_id", existing.subject_id),
        "year_group": data.get("year_group", existing.year_group),
        "test_type":  data.get("test_type", existing.test_type),
        "test_date":  data.get("test_date", existing.test_date),
        "max_marks":  data.get("max_marks", existing.max_marks),
        "notes":      data.get("notes", existing.notes),
    }
    payload = _validate_test(merged)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT test_id FROM baseline_tests "
                "WHERE name = ? AND year_group = ? AND test_date = ? "
                "  AND test_id <> ?",
                (payload["name"], payload["year_group"],
                 payload["test_date"], test_id),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"Another test named {payload['name']!r} for Year "
                    f"{payload['year_group']} on "
                    f"{payload['test_date']} already exists")
            conn.execute(
                """UPDATE baseline_tests SET
                       name = ?, subject_id = ?, year_group = ?,
                       test_type = ?, test_date = ?, max_marks = ?,
                       notes = ?, updated_at = datetime('now')
                   WHERE test_id = ?""",
                (payload["name"], payload["subject_id"],
                 payload["year_group"], payload["test_type"],
                 payload["test_date"], payload["max_marks"],
                 payload["notes"], test_id),
            )
            # If max_marks changed, recompute mark_pct on results.
            if payload["max_marks"] != existing.max_marks:
                if payload["max_marks"]:
                    conn.execute(
                        "UPDATE baseline_results SET "
                        "mark_pct = ROUND(100.0 * marks_awarded / ?, 2) "
                        "WHERE test_id = ? AND marks_awarded IS NOT NULL",
                        (payload["max_marks"], test_id),
                    )
                else:
                    conn.execute(
                        "UPDATE baseline_results SET mark_pct = NULL "
                        "WHERE test_id = ?", (test_id,),
                    )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update baseline test #%d", test_id)
        raise
    rec = get_test(test_id)
    assert rec is not None
    logger.info("Updated baseline test #%d", rec.test_id)
    return rec


def delete_test(test_id: int) -> bool:
    init_db()
    existing = get_test(test_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            cur = conn.execute(
                "DELETE FROM baseline_tests WHERE test_id = ?",
                (test_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete baseline test #%d", test_id)
        raise
    if deleted:
        logger.info("Deleted baseline test #%d %r (cascade: results)",
                    test_id, existing.name)
    return deleted


# ── Result handling ──────────────────────────────────────────────

def upsert_result(test_id: int,
                  data: dict[str, Any]) -> BaselineResult:
    init_db()
    test = get_test(test_id)
    if test is None:
        raise ValidationError(f"No baseline test #{test_id}")
    payload = _validate_result(data, test.max_marks)
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT result_id FROM baseline_results "
                "WHERE test_id = ? AND pupil_id = ?",
                (test_id, payload["pupil_id"]),
            ).fetchone()
            if row:
                conn.execute(
                    """UPDATE baseline_results SET
                           marks_awarded = ?, mark_pct = ?,
                           standardised_score = ?, baseline_grade = ?,
                           notes = ?, updated_at = datetime('now')
                       WHERE result_id = ?""",
                    (payload["marks_awarded"], payload["mark_pct"],
                     payload["standardised_score"],
                     payload["baseline_grade"], payload["notes"],
                     row["result_id"]),
                )
                rid = row["result_id"]
                action = "updated"
            else:
                cur = conn.execute(
                    """INSERT INTO baseline_results
                           (test_id, pupil_id, marks_awarded,
                            mark_pct, standardised_score,
                            baseline_grade, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (test_id, payload["pupil_id"],
                     payload["marks_awarded"], payload["mark_pct"],
                     payload["standardised_score"],
                     payload["baseline_grade"], payload["notes"]),
                )
                rid = cur.lastrowid
                action = "inserted"
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to upsert baseline result for test %d pupil %s",
            test_id, payload["pupil_id"])
        raise
    logger.info(
        "Baseline result %s: test=#%d pupil=%s marks=%s ss=%s grade=%s",
        action, test_id, payload["pupil_id"],
        payload["marks_awarded"], payload["standardised_score"],
        payload["baseline_grade"])
    rec = get_result(rid)
    assert rec is not None
    return rec


def get_result(result_id: int) -> BaselineResult | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT br.*, bt.name AS test_name,
                          bt.max_marks AS test_max,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM baseline_results br
                   LEFT JOIN baseline_tests bt ON bt.test_id = br.test_id
                   LEFT JOIN pupils p ON p.pupil_id = br.pupil_id
                   WHERE br.result_id = ?""",
                (result_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_result(%s) failed", result_id)
        raise
    return _row_result(r) if r else None


def list_results(test_id: int) -> list[BaselineResult]:
    init_db()
    try:
        with _connect() as conn:
            return [_row_result(r) for r in conn.execute(
                """SELECT br.*, bt.name AS test_name,
                          bt.max_marks AS test_max,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM baseline_results br
                   LEFT JOIN baseline_tests bt ON bt.test_id = br.test_id
                   LEFT JOIN pupils p ON p.pupil_id = br.pupil_id
                   WHERE br.test_id = ?
                   ORDER BY br.pupil_id""",
                (test_id,),
            ).fetchall()]
    except sqlite3.Error:
        logger.exception("list_results(%s) failed", test_id)
        raise


def results_for_pupil(pupil_id: str) -> list[BaselineResult]:
    init_db()
    pid = (pupil_id or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    try:
        with _connect() as conn:
            return [_row_result(r) for r in conn.execute(
                """SELECT br.*, bt.name AS test_name,
                          bt.max_marks AS test_max,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM baseline_results br
                   LEFT JOIN baseline_tests bt ON bt.test_id = br.test_id
                   LEFT JOIN pupils p ON p.pupil_id = br.pupil_id
                   WHERE br.pupil_id = ?
                   ORDER BY bt.test_date DESC""",
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
                "DELETE FROM baseline_results WHERE result_id = ?",
                (result_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete baseline result #%d",
                         result_id)
        raise
    if deleted:
        logger.info("Deleted baseline result #%d", result_id)
    return deleted


def test_summary(test_id: int) -> dict[str, Any]:
    init_db()
    test = get_test(test_id)
    if test is None:
        raise ValidationError(f"No baseline test #{test_id}")
    results = list_results(test_id)
    pcts = [r.mark_pct for r in results if r.mark_pct is not None]
    sss  = [r.standardised_score for r in results
            if r.standardised_score is not None]
    grade_dist = Counter(r.baseline_grade for r in results
                          if r.baseline_grade)
    return {
        "test":           test,
        "count":          len(results),
        "avg_pct":        round(sum(pcts) / len(pcts), 2) if pcts else None,
        "min_pct":        min(pcts) if pcts else None,
        "max_pct":        max(pcts) if pcts else None,
        "avg_standardised": round(sum(sss) / len(sss), 1) if sss else None,
        "grades":         dict(grade_dist),
        "results":        results,
    }
