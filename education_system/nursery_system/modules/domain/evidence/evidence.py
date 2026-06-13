"""Domain layer for Photos & Evidence (Nursery System).

Owns the ``evidence`` table — the EYFS evidence library: photos, videos, work
samples and notes attached to individual children. Each row records the type of
evidence, the EYFS area it covers, an optional file reference, a description and
whether the evidence has been shared with the child's parent / carer.

Follows the 4-layer pattern used across the other systems: validation +
SQLite access here, CLI in ``evidence_cli.py``, Tk GUI in ``evidence_views.py``.
"""

from __future__ import annotations

import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.nursery_system.core.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Photos & Evidence"
CATEGORY = "EYFS Learning & Development"

ID_PREFIX = "NEV"
ID_DIGITS = 3

EVIDENCE_TYPES = ("Photo", "Video", "Work sample", "Note")

AREAS = (
    "Communication and Language",
    "Physical Development",
    "Personal, Social and Emotional Development",
    "Literacy",
    "Mathematics",
    "Understanding the World",
    "Expressive Arts and Design",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid evidence input."""


@dataclass
class Evidence:
    evidence_id: str
    pupil_id: str
    capture_date: str | None
    title: str
    evidence_type: str | None
    area: str | None
    file_ref: str | None
    description: str | None
    shared_with_parent: bool
    staff_id: str | None
    created_at: str | None
    child_name: str | None = None
    room: str | None = None
    staff_name: str | None = None


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for evidence")
        raise


_SELECT = """
SELECT ev.*,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room AS room,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, ''))
           AS staff_name
FROM evidence ev
LEFT JOIN pupils p ON p.pupil_id = ev.pupil_id
LEFT JOIN staff s ON s.staff_id = ev.staff_id
"""


def _row(r: sqlite3.Row) -> Evidence:
    keys = r.keys()
    return Evidence(
        evidence_id=r["evidence_id"],
        pupil_id=r["pupil_id"],
        capture_date=r["capture_date"],
        title=r["title"],
        evidence_type=r["evidence_type"],
        area=r["area"],
        file_ref=r["file_ref"],
        description=r["description"],
        shared_with_parent=bool(r["shared_with_parent"]),
        staff_id=r["staff_id"],
        created_at=r["created_at"],
        child_name=r["child_name"] if "child_name" in keys else None,
        room=r["room"] if "room" in keys else None,
        staff_name=(r["staff_name"] or None) if "staff_name" in keys else None,
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _as_bool(value: Any) -> int:
    if isinstance(value, str):
        return 1 if value.strip().lower() in ("1", "y", "yes", "true", "on") else 0
    return 1 if value else 0


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

    title = (data.get("title") or "").strip()
    if not title:
        raise ValidationError("Title is required")
    out["title"] = title

    out["capture_date"] = _opt_date(data.get("capture_date"), "Capture date")

    etype = (data.get("evidence_type") or "").strip()
    if etype and etype not in EVIDENCE_TYPES:
        raise ValidationError(
            "Evidence type must be one of: " + ", ".join(EVIDENCE_TYPES))
    out["evidence_type"] = etype or None

    area = (data.get("area") or "").strip()
    if area and area not in AREAS:
        raise ValidationError("Area must be one of: " + ", ".join(AREAS))
    out["area"] = area or None

    out["file_ref"] = _opt(data.get("file_ref"))
    out["description"] = _opt(data.get("description"))
    out["shared_with_parent"] = _as_bool(data.get("shared_with_parent"))
    out["staff_id"] = _opt(data.get("staff_id"))
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_evidence_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT evidence_id FROM evidence").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing evidence ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        eid = f"{ID_PREFIX}{n}"
        if eid not in existing:
            return eid
    raise RuntimeError("Could not allocate a unique evidence id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_evidence(*, pupil_id: str | None = None) -> list[Evidence]:
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if pupil_id:
        sql += " WHERE ev.pupil_id = ?"
        params.append(pupil_id)
    sql += " ORDER BY ev.capture_date DESC, ev.evidence_id DESC"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_evidence failed")
        raise
    return [_row(r) for r in rows]


def get_evidence(evidence_id: str) -> Evidence | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE ev.evidence_id = ?", (evidence_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_evidence(%s) failed", evidence_id)
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

def create_evidence(data: dict[str, Any]) -> Evidence:
    _ensure_schema()
    payload = _validate(data, require_pupil=True)
    eid = generate_evidence_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM pupils WHERE pupil_id = ?",
                                (payload["pupil_id"],)).fetchone():
                raise ValidationError(
                    f"No child on roll with id {payload['pupil_id']}")
            conn.execute(
                """
                INSERT INTO evidence (
                    evidence_id, pupil_id, capture_date, title,
                    evidence_type, area, file_ref, description,
                    shared_with_parent, staff_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (eid, payload["pupil_id"], payload["capture_date"], payload["title"],
                 payload["evidence_type"], payload["area"], payload["file_ref"],
                 payload["description"], payload["shared_with_parent"],
                 payload["staff_id"]),
            )
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("INSERT failed for evidence id=%s", eid)
        raise ValidationError(f"Could not create evidence — {e}") from e
    ev = get_evidence(eid)
    assert ev is not None
    logger.info("Created evidence %s for pupil %s", eid, payload["pupil_id"])
    return ev


def update_evidence(evidence_id: str, data: dict[str, Any]) -> Evidence:
    _ensure_schema()
    payload = _validate(data, require_pupil=False)
    existing = get_evidence(evidence_id)
    if existing is None:
        raise ValidationError(f"No evidence with id {evidence_id}")
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE evidence SET
                    capture_date = ?, title = ?, evidence_type = ?, area = ?,
                    file_ref = ?, description = ?, shared_with_parent = ?,
                    staff_id = ?
                WHERE evidence_id = ?
                """,
                (payload["capture_date"], payload["title"], payload["evidence_type"],
                 payload["area"], payload["file_ref"], payload["description"],
                 payload["shared_with_parent"], payload["staff_id"],
                 evidence_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No evidence with id {evidence_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("UPDATE failed for evidence id=%s", evidence_id)
        raise ValidationError(f"Could not update evidence — {e}") from e
    ev = get_evidence(evidence_id)
    assert ev is not None
    logger.info("Updated evidence %s", evidence_id)
    return ev


def delete_evidence(evidence_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM evidence WHERE evidence_id = ?", (evidence_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting evidence id=%s", evidence_id)
        raise
    if deleted:
        logger.info("Deleted evidence %s", evidence_id)
    return deleted
