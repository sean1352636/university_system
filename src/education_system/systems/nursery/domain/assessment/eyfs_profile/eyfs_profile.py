"""Domain layer for EYFS Profile (Nursery System).

Owns the ``eyfs_profiles`` table — per-child attainment snapshots across the
7 EYFS prime and specific areas of learning. Each row records one assessment
point (term/date) together with the assessor and an overall status so the
setting can track progress from Draft to Finalised.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``eyfs_profile_cli.py``, Tk GUI in ``eyfs_profile_views.py``.
"""

from __future__ import annotations

import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.nursery.infrastructure.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "EYFS Profile"
CATEGORY = "EYFS Learning & Development"

ID_PREFIX = "NEP"
ID_DIGITS = 3

BANDS = ("Emerging", "Expected", "Exceeding")
STATUSES = ("draft", "finalised")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

AREA_FIELDS = (
    "communication_language",
    "physical_development",
    "pse_development",
    "literacy",
    "mathematics",
    "understanding_world",
    "expressive_arts",
)

AREA_LABELS = {
    "communication_language": "Communication & Language",
    "physical_development": "Physical Development",
    "pse_development": "PSE Development",
    "literacy": "Literacy",
    "mathematics": "Mathematics",
    "understanding_world": "Understanding the World",
    "expressive_arts": "Expressive Arts & Design",
}


class ValidationError(ValueError):
    """Raised for invalid EYFS profile input."""


@dataclass
class EyfsProfile:
    profile_id: str
    pupil_id: str
    assessment_date: str | None
    term: str | None
    communication_language: str | None
    physical_development: str | None
    pse_development: str | None
    literacy: str | None
    mathematics: str | None
    understanding_world: str | None
    expressive_arts: str | None
    summary: str | None
    assessor: str | None
    status: str | None
    created_at: str | None
    child_name: str | None = None
    room: str | None = None
    assessor_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for EYFS profiles")
        raise


_SELECT = """
SELECT ep.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room AS room,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, ''))
           AS assessor_name
FROM eyfs_profiles ep
LEFT JOIN pupils p ON p.pupil_id = ep.pupil_id
LEFT JOIN staff s ON s.staff_id = ep.assessor
"""


def _row(r: sqlite3.Row) -> EyfsProfile:
    keys = r.keys()
    return EyfsProfile(
        profile_id=r["profile_id"],
        pupil_id=r["pupil_id"],
        assessment_date=r["assessment_date"],
        term=r["term"],
        communication_language=r["communication_language"],
        physical_development=r["physical_development"],
        pse_development=r["pse_development"],
        literacy=r["literacy"],
        mathematics=r["mathematics"],
        understanding_world=r["understanding_world"],
        expressive_arts=r["expressive_arts"],
        summary=r["summary"],
        assessor=r["assessor"],
        status=r["status"],
        created_at=r["created_at"],
        child_name=r["child_name"] if "child_name" in keys else None,
        room=r["room"] if "room" in keys else None,
        assessor_name=(r["assessor_name"] or None) if "assessor_name" in keys else None,
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _opt_date(value: str | None, label: str) -> str | None:
    v = (value or "").strip()
    if v and not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return v or None


def _validate(data: dict[str, Any], *, require_pupil: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if require_pupil:
        pid = (data.get("pupil_id") or "").strip()
        if not pid:
            raise ValidationError("Child (pupil ID) is required")
        out["pupil_id"] = pid

    out["assessment_date"] = _opt_date(data.get("assessment_date"), "Assessment date")
    out["term"] = _opt(data.get("term"))

    for field in AREA_FIELDS:
        band = (data.get(field) or "").strip()
        if band and band not in BANDS:
            raise ValidationError(
                f"{AREA_LABELS[field]} must be one of: " + ", ".join(BANDS))
        out[field] = band or None

    out["summary"] = _opt(data.get("summary"))
    out["assessor"] = _opt(data.get("assessor"))

    status = (data.get("status") or "").strip()
    if status and status not in STATUSES:
        raise ValidationError("Status must be one of: " + ", ".join(STATUSES))
    out["status"] = status or "draft"

    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_profile_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT profile_id FROM eyfs_profiles").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing EYFS profile ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        pid = f"{ID_PREFIX}{n}"
        if pid not in existing:
            return pid
    raise RuntimeError("Could not allocate a unique EYFS profile id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_profiles(*, pupil_id: str | None = None) -> list[EyfsProfile]:
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if pupil_id:
        sql += " WHERE ep.pupil_id = ?"
        params.append(pupil_id)
    sql += " ORDER BY ep.assessment_date DESC, ep.profile_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_profiles failed")
        raise
    return [_row(r) for r in rows]


def get_profile(profile_id: str) -> EyfsProfile | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE ep.profile_id = ?", (profile_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_profile(%s) failed", profile_id)
        raise
    return _row(row) if row else None


def list_pupil_choices() -> list[tuple[str, str]]:
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT pupil_id, first_name, last_name, room FROM pupils "
                "WHERE status = 'active' ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_pupil_choices failed")
        raise
    out = []
    for r in rows:
        room = f" — {r['room']}" if r["room"] else ""
        out.append((r["pupil_id"],
                    f"{r['first_name']} {r['last_name']} ({r['pupil_id']}){room}"))
    return out


def list_staff_choices() -> list[tuple[str, str]]:
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, first_name, last_name FROM staff "
                "ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_staff_choices failed")
        raise
    return [(r["staff_id"], f"{r['first_name']} {r['last_name']} ({r['staff_id']})")
            for r in rows]


# ── Writes ───────────────────────────────────────────────────────────────────

def create_profile(data: dict[str, Any]) -> EyfsProfile:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    pid = generate_profile_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO eyfs_profiles (
                    profile_id, pupil_id, assessment_date, term,
                    communication_language, physical_development, pse_development,
                    literacy, mathematics, understanding_world, expressive_arts,
                    summary, assessor, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (pid, payload["pupil_id"], payload["assessment_date"], payload["term"],
                 payload["communication_language"], payload["physical_development"],
                 payload["pse_development"], payload["literacy"],
                 payload["mathematics"], payload["understanding_world"],
                 payload["expressive_arts"], payload["summary"],
                 payload["assessor"], payload["status"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for EYFS profile id=%s", pid)
        raise ValidationError(f"Could not create profile — {e}") from e
    p = get_profile(pid)
    assert p is not None
    logger.info("Created EYFS profile %s for pupil %s", pid, payload["pupil_id"])
    return p


def update_profile(profile_id: str, data: dict[str, Any]) -> EyfsProfile:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    existing = get_profile(profile_id)
    if existing is None:
        raise ValidationError(f"No EYFS profile with id {profile_id}")
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE eyfs_profiles SET
                    assessment_date = ?, term = ?,
                    communication_language = ?, physical_development = ?,
                    pse_development = ?, literacy = ?, mathematics = ?,
                    understanding_world = ?, expressive_arts = ?,
                    summary = ?, assessor = ?, status = ?
                WHERE profile_id = ?
                """,
                (payload["assessment_date"], payload["term"],
                 payload["communication_language"], payload["physical_development"],
                 payload["pse_development"], payload["literacy"],
                 payload["mathematics"], payload["understanding_world"],
                 payload["expressive_arts"], payload["summary"],
                 payload["assessor"], payload["status"], profile_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No EYFS profile with id {profile_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for EYFS profile id=%s", profile_id)
        raise ValidationError(f"Could not update profile — {e}") from e
    p = get_profile(profile_id)
    assert p is not None
    logger.info("Updated EYFS profile %s", profile_id)
    return p


def delete_profile(profile_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM eyfs_profiles WHERE profile_id = ?", (profile_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting EYFS profile id=%s", profile_id)
        raise
    if deleted:
        logger.info("Deleted EYFS profile %s", profile_id)
    return deleted
