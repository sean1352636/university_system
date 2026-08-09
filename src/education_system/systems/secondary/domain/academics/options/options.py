"""GCSE options process for the Secondary School System.

Three related tables:

* ``option_rounds``          — one row per options exercise (e.g.
                                "Year 9 → 10 GCSE 2025/26"). Each round
                                has a status (Draft / Open / Closed),
                                opens/closes dates, the number of
                                choices and reserves required.
* ``option_round_subjects``  — which subjects are available for the
                                round (subset of the active subjects
                                catalogue).
* ``pupil_options``          — each pupil's submitted choices. A row
                                represents one pick at a given rank
                                (1 = first choice, … N = primary
                                choices; N+1, N+2 = reserves).
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.domain.academics.subjects import (
    subjects as subjects_data,
)
from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

ROUND_STATUSES: tuple[str, ...] = ("Draft", "Open", "Closed")
DEFAULT_ROUND_STATUS: str = "Draft"

import re as _re
_DATE_RE = _re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS option_rounds (
    round_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name               TEXT NOT NULL UNIQUE,
    year_group         TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'Draft',
    opens_on           TEXT,
    closes_on          TEXT,
    choices_required   INTEGER NOT NULL DEFAULT 4,
    reserves_required  INTEGER NOT NULL DEFAULT 1,
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS option_round_subjects (
    round_id    INTEGER NOT NULL,
    subject_id  INTEGER NOT NULL,
    PRIMARY KEY (round_id, subject_id),
    FOREIGN KEY (round_id) REFERENCES option_rounds(round_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pupil_options (
    option_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id    INTEGER NOT NULL,
    pupil_id    TEXT NOT NULL,
    subject_id  INTEGER NOT NULL,
    rank        INTEGER NOT NULL,
    is_reserve  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now')),
    UNIQUE (round_id, pupil_id, rank),
    FOREIGN KEY (round_id) REFERENCES option_rounds(round_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pupil_options_pupil
    ON pupil_options(round_id, pupil_id);
CREATE INDEX IF NOT EXISTS idx_pupil_options_subject
    ON pupil_options(round_id, subject_id);
"""


@dataclass
class OptionRound:
    round_id: int
    name: str
    year_group: str
    status: str
    opens_on: str | None
    closes_on: str | None
    choices_required: int
    reserves_required: int
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class PupilChoice:
    option_id: int
    round_id: int
    pupil_id: str
    subject_id: int
    rank: int
    is_reserve: bool


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
        logger.exception("Failed to initialise options tables")
        raise
    logger.info("Secondary options tables ready")
    _DB_READY = True


def _row_round(r: sqlite3.Row) -> OptionRound:
    return OptionRound(
        round_id=r["round_id"], name=r["name"],
        year_group=r["year_group"], status=r["status"],
        opens_on=r["opens_on"], closes_on=r["closes_on"],
        choices_required=r["choices_required"],
        reserves_required=r["reserves_required"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_choice(r: sqlite3.Row) -> PupilChoice:
    return PupilChoice(
        option_id=r["option_id"], round_id=r["round_id"],
        pupil_id=r["pupil_id"], subject_id=r["subject_id"],
        rank=r["rank"], is_reserve=bool(r["is_reserve"]),
    )


def _validate_date(value: Any, label: str) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_int(value: Any, label: str, *,
                  minimum: int = 0, maximum: int = 20) -> int:
    if value in (None, ""):
        raise ValidationError(f"{label} is required")
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a whole number") from None
    if n < minimum or n > maximum:
        raise ValidationError(
            f"{label} must be between {minimum} and {maximum}")
    return n


def _validate_round(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    name = (data.get("name") or "").strip()
    if not name:
        raise ValidationError("Round name is required")
    if len(name) > 64:
        raise ValidationError("Round name must be 64 characters or fewer")
    out["name"] = name
    yg = (data.get("year_group") or "").strip()
    if not yg:
        raise ValidationError("Year group is required")
    if yg not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of {', '.join(YEAR_GROUPS)}")
    out["year_group"] = yg
    status = (data.get("status") or DEFAULT_ROUND_STATUS).strip()
    if status not in ROUND_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(ROUND_STATUSES)}")
    out["status"] = status
    out["opens_on"] = _validate_date(data.get("opens_on"), "Opens on")
    out["closes_on"] = _validate_date(data.get("closes_on"), "Closes on")
    if (out["opens_on"] and out["closes_on"]
            and out["closes_on"] < out["opens_on"]):
        raise ValidationError("Closes-on date cannot be before opens-on")
    out["choices_required"] = _validate_int(
        data.get("choices_required", 4), "Choices required",
        minimum=1, maximum=20)
    out["reserves_required"] = _validate_int(
        data.get("reserves_required", 1), "Reserves required",
        minimum=0, maximum=10)
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


# ── Rounds CRUD ────────────────────────────────────────────────────

def create_round(data: dict[str, Any]) -> OptionRound:
    init_db()
    payload = _validate_round(data)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT round_id FROM option_rounds WHERE name = ?",
                (payload["name"],),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"A round named {payload['name']!r} already exists")
            cur = conn.execute(
                """INSERT INTO option_rounds
                       (name, year_group, status, opens_on, closes_on,
                        choices_required, reserves_required, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["name"], payload["year_group"], payload["status"],
                 payload["opens_on"], payload["closes_on"],
                 payload["choices_required"], payload["reserves_required"],
                 payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create options round %s",
                         payload["name"])
        raise
    rec = get_round(new_id)
    assert rec is not None
    logger.info("Created options round #%d %r (year %s, status %s)",
                rec.round_id, rec.name, rec.year_group, rec.status)
    return rec


def get_round(round_id: int) -> OptionRound | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM option_rounds WHERE round_id = ?",
                (round_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_round(%s) failed", round_id)
        raise
    return _row_round(r) if r else None


def list_rounds(*, status: str | None = None,
                year_group: str | None = None) -> list[OptionRound]:
    init_db()
    where, params = [], []
    if status:
        if status not in ROUND_STATUSES:
            raise ValidationError(
                f"Status filter must be one of {', '.join(ROUND_STATUSES)}")
        where.append("status = ?")
        params.append(status)
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("year_group = ?")
        params.append(year_group)
    sql = "SELECT * FROM option_rounds"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY round_id DESC"
    try:
        with _connect() as conn:
            return [_row_round(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_rounds failed")
        raise


def update_round(round_id: int, data: dict[str, Any]) -> OptionRound:
    init_db()
    existing = get_round(round_id)
    if existing is None:
        raise ValidationError(f"No options round #{round_id}")
    merged = {
        "name":               data.get("name", existing.name),
        "year_group":         data.get("year_group", existing.year_group),
        "status":             data.get("status", existing.status),
        "opens_on":           data.get("opens_on", existing.opens_on),
        "closes_on":          data.get("closes_on", existing.closes_on),
        "choices_required":   data.get("choices_required",
                                       existing.choices_required),
        "reserves_required":  data.get("reserves_required",
                                       existing.reserves_required),
        "notes":              data.get("notes", existing.notes),
    }
    payload = _validate_round(merged)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT round_id FROM option_rounds "
                "WHERE name = ? AND round_id <> ?",
                (payload["name"], round_id),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"A round named {payload['name']!r} already exists")
            conn.execute(
                """UPDATE option_rounds SET
                       name = ?, year_group = ?, status = ?,
                       opens_on = ?, closes_on = ?,
                       choices_required = ?, reserves_required = ?,
                       notes = ?, updated_at = datetime('now')
                   WHERE round_id = ?""",
                (payload["name"], payload["year_group"], payload["status"],
                 payload["opens_on"], payload["closes_on"],
                 payload["choices_required"], payload["reserves_required"],
                 payload["notes"], round_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update options round #%d", round_id)
        raise
    rec = get_round(round_id)
    assert rec is not None
    logger.info("Updated options round #%d %r (status %s)",
                rec.round_id, rec.name, rec.status)
    return rec


def set_round_status(round_id: int, status: str) -> OptionRound:
    if status not in ROUND_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(ROUND_STATUSES)}")
    return update_round(round_id, {"status": status})


def delete_round(round_id: int) -> bool:
    init_db()
    existing = get_round(round_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            cur = conn.execute(
                "DELETE FROM option_rounds WHERE round_id = ?",
                (round_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete options round #%d", round_id)
        raise
    if deleted:
        logger.info("Deleted options round #%d %r "
                    "(cascade: subjects+choices)",
                    round_id, existing.name)
    return deleted


# ── Round subjects ────────────────────────────────────────────────

def add_round_subject(round_id: int, subject_id: int) -> None:
    init_db()
    if get_round(round_id) is None:
        raise ValidationError(f"No options round #{round_id}")
    subj = subjects_data.get(subject_id)
    if subj is None:
        raise ValidationError(f"No subject #{subject_id}")
    if not subj.is_active:
        raise ValidationError(
            f"Subject {subj.code} is inactive — activate it first")
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO option_round_subjects "
                "(round_id, subject_id) VALUES (?, ?)",
                (round_id, subject_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to add subject %d to round %d",
                         subject_id, round_id)
        raise
    logger.info("Round #%d: added subject #%d (%s)",
                round_id, subject_id, subj.code)


def remove_round_subject(round_id: int, subject_id: int) -> None:
    init_db()
    with _connect() as conn:
        used = conn.execute(
            "SELECT COUNT(*) FROM pupil_options "
            "WHERE round_id = ? AND subject_id = ?",
            (round_id, subject_id),
        ).fetchone()[0]
    if used:
        raise ValidationError(
            f"Subject is chosen by {used} pupil(s) in this round — "
            f"cannot remove until choices are cleared")
    try:
        with _connect() as conn:
            conn.execute(
                "DELETE FROM option_round_subjects "
                "WHERE round_id = ? AND subject_id = ?",
                (round_id, subject_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to remove subject %d from round %d",
                         subject_id, round_id)
        raise
    logger.info("Round #%d: removed subject #%d", round_id, subject_id)


def list_round_subjects(round_id: int):
    """Return subjects available for ``round_id`` as ``Subject`` objects."""
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                """SELECT s.* FROM option_round_subjects rs
                   JOIN subjects s ON s.subject_id = rs.subject_id
                   WHERE rs.round_id = ?
                   ORDER BY s.name COLLATE NOCASE""",
                (round_id,),
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_round_subjects(%d) failed", round_id)
        raise
    return [subjects_data._row(r) for r in rows]


# ── Pupil choices ─────────────────────────────────────────────────

def submit_pupil_choices(round_id: int, pupil_id: str,
                         choices: list[int],
                         reserves: list[int] | None = None) -> list[PupilChoice]:
    """Replace a pupil's choices for a round.

    ``choices``: ordered list of subject_ids (rank 1..N).
    ``reserves``: ordered list of subject_ids (rank N+1..N+M).
    """
    init_db()
    rnd = get_round(round_id)
    if rnd is None:
        raise ValidationError(f"No options round #{round_id}")
    if rnd.status != "Open":
        raise ValidationError(
            f"Round '{rnd.name}' is {rnd.status} — choices can only be "
            f"submitted while the round is Open")
    pupil_id = (pupil_id or "").strip()
    if not pupil_id:
        raise ValidationError("Pupil ID is required")

    choices = list(choices or [])
    reserves = list(reserves or [])
    if len(choices) != rnd.choices_required:
        raise ValidationError(
            f"Exactly {rnd.choices_required} primary choices required "
            f"(got {len(choices)})")
    if len(reserves) != rnd.reserves_required:
        raise ValidationError(
            f"Exactly {rnd.reserves_required} reserve(s) required "
            f"(got {len(reserves)})")
    all_picks = choices + reserves
    if len(set(all_picks)) != len(all_picks):
        raise ValidationError("Each subject can only be picked once per pupil")

    allowed = {s.subject_id for s in list_round_subjects(round_id)}
    if not allowed:
        raise ValidationError(
            "Round has no subjects configured — add subjects first")
    invalid = [s for s in all_picks if s not in allowed]
    if invalid:
        raise ValidationError(
            f"Subject(s) {invalid} are not available in this round")

    try:
        with _connect() as conn:
            conn.execute(
                "DELETE FROM pupil_options "
                "WHERE round_id = ? AND pupil_id = ?",
                (round_id, pupil_id),
            )
            for i, sid in enumerate(choices, start=1):
                conn.execute(
                    "INSERT INTO pupil_options "
                    "(round_id, pupil_id, subject_id, rank, is_reserve) "
                    "VALUES (?, ?, ?, ?, 0)",
                    (round_id, pupil_id, sid, i),
                )
            for j, sid in enumerate(reserves, start=1):
                conn.execute(
                    "INSERT INTO pupil_options "
                    "(round_id, pupil_id, subject_id, rank, is_reserve) "
                    "VALUES (?, ?, ?, ?, 1)",
                    (round_id, pupil_id, sid, len(choices) + j),
                )
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to submit choices for pupil %s in round #%d",
            pupil_id, round_id)
        raise
    logger.info("Submitted %d+%d choices for pupil %s in round #%d",
                len(choices), len(reserves), pupil_id, round_id)
    return get_pupil_choices(round_id, pupil_id)


def get_pupil_choices(round_id: int, pupil_id: str) -> list[PupilChoice]:
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM pupil_options "
                "WHERE round_id = ? AND pupil_id = ? "
                "ORDER BY rank",
                (round_id, (pupil_id or "").strip()),
            ).fetchall()
    except sqlite3.Error:
        logger.exception(
            "get_pupil_choices(%d,%s) failed", round_id, pupil_id)
        raise
    return [_row_choice(r) for r in rows]


def clear_pupil_choices(round_id: int, pupil_id: str) -> int:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM pupil_options "
                "WHERE round_id = ? AND pupil_id = ?",
                (round_id, (pupil_id or "").strip()),
            )
            conn.commit()
            removed = cur.rowcount
    except sqlite3.Error:
        logger.exception(
            "clear_pupil_choices(%d,%s) failed", round_id, pupil_id)
        raise
    if removed:
        logger.info("Cleared %d choice(s) for pupil %s in round #%d",
                    removed, pupil_id, round_id)
    return removed


def submission_summary(round_id: int) -> dict[str, Any]:
    """Return per-pupil submission stats + per-subject pick counts."""
    init_db()
    rnd = get_round(round_id)
    if rnd is None:
        raise ValidationError(f"No options round #{round_id}")
    try:
        with _connect() as conn:
            pupil_rows = conn.execute(
                "SELECT pupil_id, COUNT(*) AS n FROM pupil_options "
                "WHERE round_id = ? GROUP BY pupil_id",
                (round_id,),
            ).fetchall()
            subj_rows = conn.execute(
                """SELECT s.subject_id, s.code, s.name,
                          SUM(CASE WHEN po.is_reserve = 0 THEN 1 ELSE 0 END)
                              AS primary_n,
                          SUM(CASE WHEN po.is_reserve = 1 THEN 1 ELSE 0 END)
                              AS reserve_n
                   FROM option_round_subjects rs
                   JOIN subjects s ON s.subject_id = rs.subject_id
                   LEFT JOIN pupil_options po
                     ON po.subject_id = rs.subject_id
                    AND po.round_id = rs.round_id
                   WHERE rs.round_id = ?
                   GROUP BY s.subject_id
                   ORDER BY s.name COLLATE NOCASE""",
                (round_id,),
            ).fetchall()
    except sqlite3.Error:
        logger.exception("submission_summary(%d) failed", round_id)
        raise
    expected = rnd.choices_required + rnd.reserves_required
    complete = sum(1 for r in pupil_rows if r["n"] == expected)
    partial = sum(1 for r in pupil_rows if r["n"] != expected)
    return {
        "round":             rnd,
        "pupils_submitted":  len(pupil_rows),
        "pupils_complete":   complete,
        "pupils_partial":    partial,
        "subject_picks":     [
            {"subject_id": r["subject_id"], "code": r["code"],
             "name": r["name"],
             "primary": int(r["primary_n"] or 0),
             "reserve": int(r["reserve_n"] or 0)}
            for r in subj_rows
        ],
    }
