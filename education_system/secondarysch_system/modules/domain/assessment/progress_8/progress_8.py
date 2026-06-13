"""Progress 8 data layer for the Secondary School System.

Progress 8 is the DfE "value-added" measure: the difference between
a pupil's Attainment 8 and the average Attainment 8 of pupils with the
same KS2 prior attainment. Concretely:

    progress_8 = attainment_8 − expected_attainment_8

This module stores one row per (pupil, academic_year) recording the
pupil's KS2 prior attainment, an expected A8 (either provided or
estimated from the cohort's mean), and the resulting Progress 8 score.

If the row doesn't carry an explicit ``attainment_8``, the Progress 8
record looks up the latest matching row in the ``attainment_8`` table
(preferring ``record_source = 'Actual'`` over ``Predicted``/
``Estimated``).
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

_ACADEMIC_YEAR_RE = re.compile(r"^\d{4}/\d{2}$")

# A simple "expected A8 from KS2 average fine-grade" approximation. This
# is a rough mapping rather than the live DfE tables — the school can
# override by passing ``expected_a8`` explicitly.
_KS2_DEFAULT_EXPECTED: tuple[tuple[float, float], ...] = (
    (5.5, 7.5), (5.0, 6.5), (4.5, 5.5),
    (4.0, 4.7), (3.5, 4.0), (3.0, 3.2),
    (2.5, 2.5), (2.0, 2.0),
)


def estimate_expected_a8(ks2: float) -> float:
    """Map a KS2 prior attainment value to a rough expected A8."""
    for threshold, value in _KS2_DEFAULT_EXPECTED:
        if ks2 >= threshold:
            return value
    return 1.5


_SCHEMA = """
CREATE TABLE IF NOT EXISTS progress_8 (
    record_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id         TEXT NOT NULL,
    academic_year    TEXT NOT NULL,
    ks2_prior        REAL NOT NULL,
    expected_a8      REAL NOT NULL,
    attainment_8     REAL,
    progress_8       REAL,
    a8_source        TEXT,
    notes            TEXT,
    recorded_by      TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    UNIQUE (pupil_id, academic_year)
);

CREATE INDEX IF NOT EXISTS idx_p8_pupil ON progress_8(pupil_id);
CREATE INDEX IF NOT EXISTS idx_p8_year ON progress_8(academic_year);
"""


@dataclass
class Progress8Record:
    record_id: int
    pupil_id: str
    academic_year: str
    ks2_prior: float
    expected_a8: float
    attainment_8: float | None
    progress_8: float | None
    a8_source: str | None
    notes: str | None
    recorded_by: str | None
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
    from education_system.secondarysch_system.modules.domain.assessment.attainment_8 import (
        attainment_8 as a8_data,
    )
    a8_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise progress_8 table")
        raise
    logger.info("Secondary progress_8 table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> Progress8Record:
    keys = r.keys()
    return Progress8Record(
        record_id=r["record_id"], pupil_id=r["pupil_id"],
        academic_year=r["academic_year"],
        ks2_prior=r["ks2_prior"], expected_a8=r["expected_a8"],
        attainment_8=r["attainment_8"], progress_8=r["progress_8"],
        a8_source=r["a8_source"], notes=r["notes"],
        recorded_by=r["recorded_by"],
        pupil_name=r["pupil_name"] if "pupil_name" in keys else None,
        pupil_year=r["pupil_year"] if "pupil_year" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _lookup_a8(pupil_id: str,
                academic_year: str) -> tuple[float | None, str | None]:
    """Find the best-matching attainment_8 row for this pupil/year."""
    from education_system.secondarysch_system.modules.domain.assessment.attainment_8 import (
        attainment_8 as a8_data,
    )
    for src in ("Actual", "Predicted", "Estimated"):
        rec = a8_data.get_for(pupil_id, academic_year, src)
        if rec is not None and rec.attainment_8 is not None:
            return rec.attainment_8, src
    return None, None


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

    def _float(value, label, *, mn, mx):
        if value in (None, "") or (isinstance(value, str)
                                    and not value.strip()):
            raise ValidationError(f"{label} is required")
        try:
            v = float(value)
        except (TypeError, ValueError):
            raise ValidationError(f"{label} must be a number") from None
        if v < mn or v > mx:
            raise ValidationError(f"{label} must be between {mn} and {mx}")
        return v

    out["ks2_prior"] = _float(data.get("ks2_prior"),
                                "KS2 prior attainment", mn=0, mx=6)

    expected_raw = data.get("expected_a8")
    if expected_raw in (None, "") or (isinstance(expected_raw, str)
                                        and not expected_raw.strip()):
        out["expected_a8"] = round(estimate_expected_a8(out["ks2_prior"]),
                                     2)
    else:
        out["expected_a8"] = _float(expected_raw,
                                       "Expected A8", mn=0, mx=9)

    a8_raw = data.get("attainment_8")
    if a8_raw in (None, "") or (isinstance(a8_raw, str)
                                  and not a8_raw.strip()):
        looked_up, src = _lookup_a8(out["pupil_id"], out["academic_year"])
        out["attainment_8"] = looked_up
        out["a8_source"] = (data.get("a8_source") or src or
                              "(no A8 record)")
    else:
        try:
            out["attainment_8"] = float(a8_raw)
        except (TypeError, ValueError):
            raise ValidationError(
                "Attainment 8 must be a number") from None
        if out["attainment_8"] < 0 or out["attainment_8"] > 9:
            raise ValidationError(
                "Attainment 8 must be between 0 and 9")
        out["a8_source"] = (data.get("a8_source") or "Manual").strip()

    if out["attainment_8"] is not None:
        out["progress_8"] = round(
            out["attainment_8"] - out["expected_a8"], 2)
    else:
        out["progress_8"] = None

    out["recorded_by"] = (data.get("recorded_by") or "").strip() or None
    out["notes"]       = (data.get("notes") or "").strip() or None
    return out


def upsert(data: dict[str, Any]) -> Progress8Record:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT record_id FROM progress_8 "
                "WHERE pupil_id = ? AND academic_year = ?",
                (payload["pupil_id"], payload["academic_year"]),
            ).fetchone()
            if row:
                conn.execute(
                    """UPDATE progress_8 SET
                           ks2_prior = ?, expected_a8 = ?,
                           attainment_8 = ?, progress_8 = ?,
                           a8_source = ?, recorded_by = ?, notes = ?,
                           updated_at = datetime('now')
                       WHERE record_id = ?""",
                    (payload["ks2_prior"], payload["expected_a8"],
                     payload["attainment_8"], payload["progress_8"],
                     payload["a8_source"], payload["recorded_by"],
                     payload["notes"], row["record_id"]),
                )
                rid = row["record_id"]
                action = "updated"
            else:
                cur = conn.execute(
                    """INSERT INTO progress_8
                           (pupil_id, academic_year, ks2_prior,
                            expected_a8, attainment_8, progress_8,
                            a8_source, recorded_by, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (payload["pupil_id"], payload["academic_year"],
                     payload["ks2_prior"], payload["expected_a8"],
                     payload["attainment_8"], payload["progress_8"],
                     payload["a8_source"], payload["recorded_by"],
                     payload["notes"]),
                )
                rid = cur.lastrowid
                action = "inserted"
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to upsert progress_8 for pupil %s year %s",
            payload["pupil_id"], payload["academic_year"])
        raise
    logger.info(
        "Progress 8 %s: pupil=%s year=%s ks2=%s expected=%s a8=%s p8=%s",
        action, payload["pupil_id"], payload["academic_year"],
        payload["ks2_prior"], payload["expected_a8"],
        payload["attainment_8"], payload["progress_8"])
    rec = get(rid)
    assert rec is not None
    return rec


def refresh_progress_8(record_id: int) -> Progress8Record:
    """Re-pull the latest Attainment 8 from the a8 table and recompute."""
    init_db()
    existing = get(record_id)
    if existing is None:
        raise ValidationError(f"No progress_8 record #{record_id}")
    return upsert({
        "pupil_id":      existing.pupil_id,
        "academic_year": existing.academic_year,
        "ks2_prior":     existing.ks2_prior,
        "expected_a8":   existing.expected_a8,
        "recorded_by":   existing.recorded_by,
        "notes":         existing.notes,
    })


def get(record_id: int) -> Progress8Record | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT p8.*,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM progress_8 p8
                   LEFT JOIN pupils p ON p.pupil_id = p8.pupil_id
                   WHERE p8.record_id = ?""",
                (record_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", record_id)
        raise
    return _row(r) if r else None


def get_for(pupil_id: str,
            academic_year: str) -> Progress8Record | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT p8.*,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM progress_8 p8
                   LEFT JOIN pupils p ON p.pupil_id = p8.pupil_id
                   WHERE p8.pupil_id = ? AND p8.academic_year = ?""",
                ((pupil_id or "").strip(),
                 (academic_year or "").strip()),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_for(%s, %s) failed",
                         pupil_id, academic_year)
        raise
    return _row(r) if r else None


def list_records(*, year_group: str | None = None,
                 academic_year: str | None = None,
                 pupil_id: str | None = None
                 ) -> list[Progress8Record]:
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
        where.append("p8.academic_year = ?")
        params.append(academic_year.strip())
    if pupil_id:
        where.append("p8.pupil_id = ?")
        params.append(pupil_id.strip())
    sql = ("""SELECT p8.*,
                     (p.first_name || ' ' || p.last_name) AS pupil_name,
                     p.year_group AS pupil_year
              FROM progress_8 p8
              LEFT JOIN pupils p ON p.pupil_id = p8.pupil_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (" ORDER BY p8.academic_year DESC, p.year_group, "
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
                "DELETE FROM progress_8 WHERE record_id = ?",
                (record_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete progress_8 #%d", record_id)
        raise
    if deleted:
        logger.info("Deleted progress_8 #%d (pupil %s year %s)",
                    record_id, existing.pupil_id,
                    existing.academic_year)
    return deleted


def cohort_summary(*, year_group: str | None = None,
                   academic_year: str | None = None) -> dict[str, Any]:
    rows = list_records(year_group=year_group,
                          academic_year=academic_year)
    p8s = [r.progress_8 for r in rows if r.progress_8 is not None]
    avg = round(sum(p8s) / len(p8s), 2) if p8s else None
    bands: Counter = Counter()
    for v in p8s:
        if v >= 1:
            bands["+1.0 or more"] += 1
        elif v >= 0.5:
            bands["+0.5 to +0.99"] += 1
        elif v >= 0:
            bands["0 to +0.49"] += 1
        elif v >= -0.5:
            bands["-0.5 to -0.01"] += 1
        elif v >= -1:
            bands["-1.0 to -0.51"] += 1
        else:
            bands["worse than -1.0"] += 1
    return {
        "count":      len(rows),
        "with_p8":    len(p8s),
        "without_p8": len(rows) - len(p8s),
        "avg_p8":     avg,
        "min_p8":     min(p8s) if p8s else None,
        "max_p8":     max(p8s) if p8s else None,
        "bands":      dict(bands),
    }
