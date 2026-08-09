"""EYFS Profile data layer.

Reception teachers complete the EYFS Profile at the end of the
Reception year. The Profile is made up of 17 Early Learning Goals
across 7 areas of learning. Each ELG is graded:

    Emerging — the child has not yet reached the expected level
    Expected — the child is meeting the expected level

(Exceeding was removed in the 2021 reform.)

A child is judged to have a "Good Level of Development" (GLD) if they
are graded ``Expected`` in the 12 ELGs that fall in the *prime* areas
(Communication & Language, PSED, Physical Development) and in the two
specific areas of Literacy and Mathematics. UW and EAD do not feed
into GLD.

One row per (pupil, academic_year, elg_code).
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.primary.domain.learners.pupils import (
    pupils as pupils_data,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
    Pupil, ValidationError, YEAR_GROUPS,
    _connect as _pupils_connect, _DOB_RE,
)

logger = logging.getLogger(__name__)

STATUSES: tuple[str, ...] = ("Emerging", "Expected")

# (area, elg_code, label, contributes_to_GLD)
_ELG_TABLE: tuple[tuple[str, str, str, bool], ...] = (
    ("Communication & Language", "CL01", "Listening, Attention and Understanding", True),
    ("Communication & Language", "CL02", "Speaking",                                  True),
    ("Personal, Social & Emotional Development", "PSED01", "Self-Regulation",         True),
    ("Personal, Social & Emotional Development", "PSED02", "Managing Self",           True),
    ("Personal, Social & Emotional Development", "PSED03", "Building Relationships",  True),
    ("Physical Development", "PD01", "Gross Motor Skills",                            True),
    ("Physical Development", "PD02", "Fine Motor Skills",                             True),
    ("Literacy",       "LIT01", "Comprehension",                                      True),
    ("Literacy",       "LIT02", "Word Reading",                                       True),
    ("Literacy",       "LIT03", "Writing",                                            True),
    ("Mathematics",    "MAT01", "Number",                                             True),
    ("Mathematics",    "MAT02", "Numerical Patterns",                                 True),
    ("Understanding the World", "UW01", "Past and Present",                           False),
    ("Understanding the World", "UW02", "People, Culture and Communities",            False),
    ("Understanding the World", "UW03", "The Natural World",                          False),
    ("Expressive Arts & Design", "EAD01", "Creating with Materials",                  False),
    ("Expressive Arts & Design", "EAD02", "Being Imaginative and Expressive",         False),
)

ELG_CODES: tuple[str, ...] = tuple(e[1] for e in _ELG_TABLE)
ELG_LABELS: dict[str, str] = {code: label for _a, code, label, _g in _ELG_TABLE}
ELG_AREAS: dict[str, str] = {code: area for area, code, _l, _g in _ELG_TABLE}
ELG_GLD: dict[str, bool] = {code: gld for _a, code, _l, gld in _ELG_TABLE}
GLD_CODES: tuple[str, ...] = tuple(c for c in ELG_CODES if ELG_GLD[c])

AREAS: tuple[str, ...] = tuple(dict.fromkeys(a for a, _c, _l, _g in _ELG_TABLE))

_ACADEMIC_YEAR_RE = re.compile(r"^\d{4}(-\d{2}|-\d{4})?$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS eyfs_profile_results (
    result_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id        TEXT NOT NULL,
    academic_year   TEXT NOT NULL,
    elg_code        TEXT NOT NULL,
    status          TEXT NOT NULL,
    assessed_on     TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(pupil_id, academic_year, elg_code),
    FOREIGN KEY(pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_eyfs_pupil ON eyfs_profile_results(pupil_id);
CREATE INDEX IF NOT EXISTS idx_eyfs_year  ON eyfs_profile_results(academic_year);
"""


@dataclass
class ELGResult:
    result_id: int
    pupil_id: str
    academic_year: str
    elg_code: str
    status: str
    assessed_on: str | None
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def area(self) -> str:
        return ELG_AREAS.get(self.elg_code, "?")

    @property
    def label(self) -> str:
        return ELG_LABELS.get(self.elg_code, self.elg_code)

    @property
    def contributes_to_gld(self) -> bool:
        return ELG_GLD.get(self.elg_code, False)


@dataclass
class PupilProfile:
    """Aggregated EYFS profile for one (pupil, year)."""
    pupil_id: str
    academic_year: str
    by_code: dict[str, ELGResult]

    @property
    def elgs_recorded(self) -> int:
        return len(self.by_code)

    @property
    def elgs_total(self) -> int:
        return len(ELG_CODES)

    @property
    def expected_count(self) -> int:
        return sum(1 for r in self.by_code.values() if r.status == "Expected")

    @property
    def has_gld(self) -> bool:
        for code in GLD_CODES:
            rec = self.by_code.get(code)
            if rec is None or rec.status != "Expected":
                return False
        return True

    @property
    def gld_missing(self) -> list[str]:
        out: list[str] = []
        for code in GLD_CODES:
            rec = self.by_code.get(code)
            if rec is None or rec.status != "Expected":
                out.append(code)
        return out


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    pupils_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise eyfs_profile_results table")
        raise
    logger.info("Primary eyfs_profile_results table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> ELGResult:
    return ELGResult(
        result_id=r["result_id"],
        pupil_id=r["pupil_id"],
        academic_year=r["academic_year"],
        elg_code=r["elg_code"],
        status=r["status"],
        assessed_on=r["assessed_on"],
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid = (data.get("pupil_id") or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    out["pupil_id"] = pid
    ay = (data.get("academic_year") or "").strip()
    if not ay:
        raise ValidationError("Academic year is required (e.g. 2025-26)")
    if not _ACADEMIC_YEAR_RE.match(ay):
        raise ValidationError("Academic year must look like 2025 or 2025-26")
    out["academic_year"] = ay
    code = (data.get("elg_code") or "").strip().upper()
    if not code:
        raise ValidationError("ELG code is required")
    if code not in ELG_LABELS:
        raise ValidationError(
            f"ELG code must be one of: {', '.join(ELG_CODES)}")
    out["elg_code"] = code
    status = (data.get("status") or "").strip().title()
    if not status:
        raise ValidationError("Status is required")
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status
    assessed_on = (data.get("assessed_on") or "").strip()
    if assessed_on and not _DOB_RE.match(assessed_on):
        raise ValidationError("Assessed-on date must be YYYY-MM-DD")
    out["assessed_on"] = assessed_on or None
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def set_elg(pupil_id: str, academic_year: str, elg_code: str,
            status: str, *, assessed_on: str | None = None,
            notes: str | None = None) -> ELGResult:
    """Upsert a single ELG entry for the pupil/year."""
    init_db()
    payload = _validate({
        "pupil_id": pupil_id, "academic_year": academic_year,
        "elg_code": elg_code, "status": status,
        "assessed_on": assessed_on, "notes": notes,
    })
    if pupils_data.get_pupil(payload["pupil_id"]) is None:
        raise ValidationError(f"No pupil with id {payload['pupil_id']}")
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT result_id FROM eyfs_profile_results "
                "WHERE pupil_id = ? AND academic_year = ? AND elg_code = ?",
                (payload["pupil_id"], payload["academic_year"],
                 payload["elg_code"]),
            ).fetchone()
            if r is None:
                cur = conn.execute(
                    """INSERT INTO eyfs_profile_results
                           (pupil_id, academic_year, elg_code, status,
                            assessed_on, notes)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (payload["pupil_id"], payload["academic_year"],
                     payload["elg_code"], payload["status"],
                     payload["assessed_on"], payload["notes"]),
                )
                new_id = cur.lastrowid
            else:
                conn.execute(
                    """UPDATE eyfs_profile_results SET
                           status = ?, assessed_on = ?, notes = ?,
                           updated_at = datetime('now')
                       WHERE result_id = ?""",
                    (payload["status"], payload["assessed_on"],
                     payload["notes"], r["result_id"]),
                )
                new_id = r["result_id"]
            conn.commit()
    except sqlite3.Error:
        logger.exception("set_elg failed for %s/%s/%s",
                         payload["pupil_id"], payload["academic_year"],
                         payload["elg_code"])
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info("EYFS: %s %s %s -> %s",
                rec.pupil_id, rec.academic_year, rec.elg_code, rec.status)
    return rec


def get(result_id: int) -> ELGResult | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM eyfs_profile_results WHERE result_id = ?",
                (result_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get eyfs(%s) failed", result_id)
        raise
    return _row(r) if r else None


def delete(result_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM eyfs_profile_results WHERE result_id = ?",
                (result_id,),
            )
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete eyfs #%d", result_id)
        raise
    if deleted:
        logger.info("Deleted eyfs result #%d", result_id)
    return deleted


def clear_pupil_year(pupil_id: str, academic_year: str) -> int:
    """Remove every ELG entry for a pupil in a given year."""
    init_db()
    if pupils_data.get_pupil(pupil_id) is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM eyfs_profile_results "
                "WHERE pupil_id = ? AND academic_year = ?",
                (pupil_id, academic_year),
            )
            conn.commit()
            removed = cur.rowcount
    except sqlite3.Error:
        logger.exception("clear_pupil_year(%s, %s) failed",
                         pupil_id, academic_year)
        raise
    logger.info("Cleared %d EYFS entry(ies) for pupil %s in %s",
                removed, pupil_id, academic_year)
    return removed


def get_profile(pupil_id: str, academic_year: str) -> PupilProfile:
    init_db()
    if pupils_data.get_pupil(pupil_id) is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM eyfs_profile_results "
                "WHERE pupil_id = ? AND academic_year = ?",
                (pupil_id, academic_year),
            ).fetchall()
    except sqlite3.Error:
        logger.exception("get_profile(%s, %s) failed",
                         pupil_id, academic_year)
        raise
    by_code = {r["elg_code"]: _row(r) for r in rows}
    return PupilProfile(pupil_id=pupil_id, academic_year=academic_year,
                        by_code=by_code)


def list_pupils_with_profiles(
    academic_year: str, *, year_group: str | None = None,
) -> list[tuple[Pupil, PupilProfile]]:
    """Return every pupil who has at least one ELG row for ``academic_year``."""
    init_db()
    if year_group and year_group not in YEAR_GROUPS:
        raise ValidationError(
            f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM eyfs_profile_results WHERE academic_year = ?",
                (academic_year,),
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_pupils_with_profiles(%s) failed", academic_year)
        raise
    by_pupil: dict[str, dict[str, ELGResult]] = {}
    for r in rows:
        by_pupil.setdefault(r["pupil_id"], {})[r["elg_code"]] = _row(r)
    out: list[tuple[Pupil, PupilProfile]] = []
    for pid, by_code in by_pupil.items():
        p = pupils_data.get_pupil(pid)
        if p is None:
            logger.warning("EYFS rows for missing pupil %s", pid)
            continue
        if year_group and p.year_group != year_group:
            continue
        out.append((p, PupilProfile(pupil_id=pid,
                                    academic_year=academic_year,
                                    by_code=by_code)))
    out.sort(key=lambda t: (t[0].last_name, t[0].first_name))
    return out


def cohort_summary(academic_year: str,
                   *, year_group: str | None = None) -> dict[str, Any]:
    init_db()
    profiles = list_pupils_with_profiles(academic_year, year_group=year_group)
    total = len(profiles)
    complete = sum(1 for _p, pr in profiles if pr.elgs_recorded == pr.elgs_total)
    gld = sum(1 for _p, pr in profiles if pr.has_gld)
    return {
        "academic_year": academic_year,
        "pupils": total,
        "complete_profiles": complete,
        "gld_count": gld,
        "gld_pct": (gld / total * 100.0) if total else 0.0,
    }


def known_years() -> list[str]:
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT academic_year FROM eyfs_profile_results "
                "ORDER BY academic_year DESC"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("known_years failed")
        raise
    return [r["academic_year"] for r in rows]
