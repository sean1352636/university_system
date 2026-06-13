"""Attainment 8 data layer for the Secondary School System.

A pupil's Attainment 8 is the sum of grade points across 10 weighted
slots, divided by 10:

* English (best of language + literature) — counted twice
* Maths — counted twice
* Three EBacc slots (Sciences / Computer Science / Humanities / Lang.)
* Three Open slots (any remaining qualifying subjects)

GCSE 9–1 grades convert 1:1 to points (grade "9" = 9.0, "U" = 0.0).
Each pupil has at most one Attainment 8 record per academic year.
``record_source`` lets you keep both an "Estimated" mid-year row and
the final "Actual" row by re-using a different academic_year tag if
you want to preserve history — or just overwrite.
"""

from __future__ import annotations

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

SOURCES: tuple[str, ...] = ("Estimated", "Predicted", "Actual")
DEFAULT_SOURCE: str = "Estimated"

# Grade → point mapping (GCSE 9–1).
GRADE_POINTS: dict[str, float] = {
    "9": 9.0, "8": 8.0, "7": 7.0, "6": 6.0, "5": 5.0,
    "4": 4.0, "3": 3.0, "2": 2.0, "1": 1.0, "U": 0.0,
}

# Slot labels (10 total: English ×2, Maths ×2, 3 EBacc, 3 Open).
SLOT_LABELS: tuple[str, ...] = (
    "english_grade", "maths_grade",
    "ebacc1_grade", "ebacc2_grade", "ebacc3_grade",
    "open1_grade", "open2_grade", "open3_grade",
)

_ACADEMIC_YEAR_RE = re.compile(r"^\d{4}/\d{2}$")
_GRADE_RE = re.compile(r"^[A-Za-z0-9*+\-]{1,3}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attainment_8 (
    record_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id         TEXT NOT NULL,
    academic_year    TEXT NOT NULL,
    record_source    TEXT NOT NULL DEFAULT 'Estimated',
    english_grade    TEXT,
    maths_grade      TEXT,
    ebacc1_grade     TEXT,
    ebacc2_grade     TEXT,
    ebacc3_grade     TEXT,
    open1_grade      TEXT,
    open2_grade      TEXT,
    open3_grade      TEXT,
    total_points     REAL,
    attainment_8     REAL,
    recorded_by      TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    UNIQUE (pupil_id, academic_year, record_source)
);

CREATE INDEX IF NOT EXISTS idx_a8_pupil ON attainment_8(pupil_id);
CREATE INDEX IF NOT EXISTS idx_a8_year ON attainment_8(academic_year);
"""


@dataclass
class Attainment8Record:
    record_id: int
    pupil_id: str
    academic_year: str
    record_source: str
    english_grade: str | None
    maths_grade: str | None
    ebacc1_grade: str | None
    ebacc2_grade: str | None
    ebacc3_grade: str | None
    open1_grade: str | None
    open2_grade: str | None
    open3_grade: str | None
    total_points: float | None
    attainment_8: float | None
    recorded_by: str | None
    notes: str | None
    pupil_name: str | None = None
    pupil_year: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def slots_filled(self) -> int:
        return sum(1 for k in SLOT_LABELS
                   if getattr(self, k) not in (None, ""))


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise attainment_8 table")
        raise
    logger.info("Secondary attainment_8 table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> Attainment8Record:
    keys = r.keys()
    return Attainment8Record(
        record_id=r["record_id"], pupil_id=r["pupil_id"],
        academic_year=r["academic_year"],
        record_source=r["record_source"],
        english_grade=r["english_grade"],
        maths_grade=r["maths_grade"],
        ebacc1_grade=r["ebacc1_grade"],
        ebacc2_grade=r["ebacc2_grade"],
        ebacc3_grade=r["ebacc3_grade"],
        open1_grade=r["open1_grade"],
        open2_grade=r["open2_grade"],
        open3_grade=r["open3_grade"],
        total_points=r["total_points"],
        attainment_8=r["attainment_8"],
        recorded_by=r["recorded_by"], notes=r["notes"],
        pupil_name=r["pupil_name"] if "pupil_name" in keys else None,
        pupil_year=r["pupil_year"] if "pupil_year" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def grade_to_points(grade: str | None) -> float | None:
    """Look up GCSE 9–1 grade points; returns None for unrecognised."""
    if grade is None:
        return None
    g = grade.strip().upper()
    if not g:
        return None
    return GRADE_POINTS.get(g)


def compute_total(grades: dict[str, str | None]) -> tuple[float | None,
                                                            float | None]:
    """Return ``(total_points, attainment_8)``.

    ``total_points`` is the weighted sum (English ×2, Maths ×2, plus the
    six other slots). ``attainment_8`` is ``total_points / 10``.

    If any of the slots has a grade that doesn't map to a numeric point
    value (e.g. it's blank, or a non-9–1 grade like "WT"), returns
    ``(None, None)`` so the user can decide how to handle it.
    """
    points: list[float] = []
    for label in SLOT_LABELS:
        grade = grades.get(label)
        if grade in (None, ""):
            return None, None
        pts = grade_to_points(grade)
        if pts is None:
            return None, None
        if label in ("english_grade", "maths_grade"):
            points.extend([pts, pts])
        else:
            points.append(pts)
    if len(points) != 10:
        return None, None
    total = round(sum(points), 2)
    return total, round(total / 10.0, 2)


def _validate(data: dict[str, Any]) -> dict[str, Any]:
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

    ay = (data.get("academic_year") or "").strip()
    if not ay:
        raise ValidationError("Academic year is required (e.g. 2025/26)")
    if not _ACADEMIC_YEAR_RE.match(ay):
        raise ValidationError(
            "Academic year must be in form YYYY/YY (e.g. 2025/26)")
    out["academic_year"] = ay

    src = (data.get("record_source") or DEFAULT_SOURCE).strip()
    if src not in SOURCES:
        raise ValidationError(
            f"Record source must be one of {', '.join(SOURCES)}")
    out["record_source"] = src

    for label in SLOT_LABELS:
        raw = (data.get(label) or "").strip()
        if not raw:
            out[label] = None
            continue
        if not _GRADE_RE.match(raw):
            raise ValidationError(
                f"{label.replace('_', ' ')} must be 1–3 chars "
                f"(letters/digits/* + -)")
        out[label] = raw.upper()

    out["recorded_by"] = (data.get("recorded_by") or "").strip() or None
    out["notes"]       = (data.get("notes") or "").strip() or None
    # Derived metrics
    total, a8 = compute_total({k: out[k] for k in SLOT_LABELS})
    out["total_points"] = total
    out["attainment_8"] = a8
    return out


def upsert(data: dict[str, Any]) -> Attainment8Record:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT record_id FROM attainment_8 "
                "WHERE pupil_id = ? AND academic_year = ? "
                "  AND record_source = ?",
                (payload["pupil_id"], payload["academic_year"],
                 payload["record_source"]),
            ).fetchone()
            cols = ("english_grade", "maths_grade",
                    "ebacc1_grade", "ebacc2_grade", "ebacc3_grade",
                    "open1_grade", "open2_grade", "open3_grade",
                    "total_points", "attainment_8",
                    "recorded_by", "notes")
            if row:
                conn.execute(
                    "UPDATE attainment_8 SET "
                    + ", ".join(f"{c} = ?" for c in cols)
                    + ", updated_at = datetime('now') "
                    "WHERE record_id = ?",
                    (*(payload[c] for c in cols), row["record_id"]),
                )
                rid = row["record_id"]
                action = "updated"
            else:
                cur = conn.execute(
                    "INSERT INTO attainment_8 "
                    "(pupil_id, academic_year, record_source, "
                    + ", ".join(cols) + ") VALUES ("
                    + ", ".join(["?"] * (3 + len(cols))) + ")",
                    (payload["pupil_id"], payload["academic_year"],
                     payload["record_source"],
                     *(payload[c] for c in cols)),
                )
                rid = cur.lastrowid
                action = "inserted"
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to upsert attainment_8 for pupil %s year %s source %s",
            payload["pupil_id"], payload["academic_year"],
            payload["record_source"])
        raise
    logger.info(
        "Attainment 8 %s: pupil=%s year=%s source=%s total=%s a8=%s",
        action, payload["pupil_id"], payload["academic_year"],
        payload["record_source"], payload["total_points"],
        payload["attainment_8"])
    rec = get(rid)
    assert rec is not None
    return rec


def get(record_id: int) -> Attainment8Record | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT a.*,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM attainment_8 a
                   LEFT JOIN pupils p ON p.pupil_id = a.pupil_id
                   WHERE a.record_id = ?""",
                (record_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", record_id)
        raise
    return _row(r) if r else None


def get_for(pupil_id: str, academic_year: str,
            record_source: str = DEFAULT_SOURCE
            ) -> Attainment8Record | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT a.*,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM attainment_8 a
                   LEFT JOIN pupils p ON p.pupil_id = a.pupil_id
                   WHERE a.pupil_id = ? AND a.academic_year = ?
                     AND a.record_source = ?""",
                ((pupil_id or "").strip(), (academic_year or "").strip(),
                 record_source),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_for(%s, %s, %s) failed",
                         pupil_id, academic_year, record_source)
        raise
    return _row(r) if r else None


def list_records(*, year_group: str | None = None,
                 academic_year: str | None = None,
                 record_source: str | None = None,
                 pupil_id: str | None = None
                 ) -> list[Attainment8Record]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("p.year_group = ?")
        params.append(year_group)
    if academic_year:
        where.append("a.academic_year = ?")
        params.append(academic_year.strip())
    if record_source:
        if record_source not in SOURCES:
            raise ValidationError(
                f"Source filter must be one of {', '.join(SOURCES)}")
        where.append("a.record_source = ?")
        params.append(record_source)
    if pupil_id:
        where.append("a.pupil_id = ?")
        params.append(pupil_id.strip())
    sql = ("""SELECT a.*,
                     (p.first_name || ' ' || p.last_name) AS pupil_name,
                     p.year_group AS pupil_year
              FROM attainment_8 a
              LEFT JOIN pupils p ON p.pupil_id = a.pupil_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (" ORDER BY a.academic_year DESC, p.year_group, "
            "p.last_name, p.first_name")
    try:
        with _connect() as conn:
            return [_row(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise


def delete(record_id: int) -> bool:
    init_db()
    existing = get(record_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM attainment_8 WHERE record_id = ?",
                (record_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete attainment_8 #%d",
                         record_id)
        raise
    if deleted:
        logger.info("Deleted attainment_8 #%d (pupil %s year %s)",
                    record_id, existing.pupil_id,
                    existing.academic_year)
    return deleted


def cohort_summary(*, year_group: str | None = None,
                   academic_year: str | None = None,
                   record_source: str | None = None) -> dict[str, Any]:
    """Mean / spread for the filtered cohort (only complete records
    count toward the averages — incomplete rows are reported separately)."""
    rows = list_records(year_group=year_group,
                          academic_year=academic_year,
                          record_source=record_source)
    a8s = [r.attainment_8 for r in rows if r.attainment_8 is not None]
    incomplete = sum(1 for r in rows if r.attainment_8 is None)
    avg = round(sum(a8s) / len(a8s), 2) if a8s else None
    bands: Counter = Counter()
    for v in a8s:
        if v >= 8:
            bands["8.0+"] += 1
        elif v >= 7:
            bands["7.0–7.9"] += 1
        elif v >= 6:
            bands["6.0–6.9"] += 1
        elif v >= 5:
            bands["5.0–5.9"] += 1
        elif v >= 4:
            bands["4.0–4.9"] += 1
        elif v >= 3:
            bands["3.0–3.9"] += 1
        else:
            bands["<3.0"] += 1
    return {
        "count":      len(rows),
        "complete":   len(a8s),
        "incomplete": incomplete,
        "avg_a8":     avg,
        "min_a8":     min(a8s) if a8s else None,
        "max_a8":     max(a8s) if a8s else None,
        "bands":      dict(bands),
    }
