"""Onboarding data layer for the Primary School System.

Tracks per-pupil onboarding checklist progress. Each pupil has a single
``pupil_onboarding`` row; rows are created lazily the first time a step
is toggled or the record is fetched.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.primary.domain.learners.pupils import pupils as pupils_data
from education_system.systems.primary.domain.learners.pupils.pupils import (
    Pupil, ValidationError,
)

logger = logging.getLogger(__name__)

STEPS: list[tuple[str, str]] = [
    ("parent_contacts_done", "Parent contacts collected"),
    ("photo_on_file",        "Photo on file"),
    ("safeguarding_consent", "Safeguarding consent received"),
    ("medical_info",         "Medical info on file"),
    ("home_visit_done",      "Home visit completed"),
    ("induction_done",       "Induction session completed"),
]
STEP_KEYS: tuple[str, ...] = tuple(k for k, _ in STEPS)
STEP_LABELS: dict[str, str] = dict(STEPS)

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS pupil_onboarding (
    pupil_id              TEXT PRIMARY KEY,
    {", ".join(f"{k} INTEGER NOT NULL DEFAULT 0" for k in STEP_KEYS)},
    updated_at            TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);
"""


@dataclass
class OnboardingRecord:
    pupil_id: str
    steps: dict[str, bool]
    updated_at: str | None

    @property
    def complete(self) -> bool:
        return all(self.steps.values())

    @property
    def done_count(self) -> int:
        return sum(1 for v in self.steps.values() if v)

    @property
    def total(self) -> int:
        return len(self.steps)


_DB_READY = False


def _ensure_schema() -> None:
    global _DB_READY
    if _DB_READY:
        return
    pupils_data.init_db()
    try:
        with pupils_data._connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise primary onboarding table")
        raise
    logger.info("Primary onboarding table ready")
    _DB_READY = True


def _row_to_record(row: sqlite3.Row) -> OnboardingRecord:
    return OnboardingRecord(
        pupil_id=row["pupil_id"],
        steps={k: bool(row[k]) for k in STEP_KEYS},
        updated_at=row["updated_at"],
    )


def _blank_record(pupil_id: str) -> OnboardingRecord:
    return OnboardingRecord(
        pupil_id=pupil_id,
        steps={k: False for k in STEP_KEYS},
        updated_at=None,
    )


def get_record(pupil_id: str) -> OnboardingRecord:
    _ensure_schema()
    pupil = pupils_data.get_pupil(pupil_id)
    if pupil is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    try:
        with pupils_data._connect() as conn:
            row = conn.execute(
                "SELECT * FROM pupil_onboarding WHERE pupil_id = ?",
                (pupil_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_record(%s) failed", pupil_id)
        raise
    if row is None:
        logger.debug("get_record(%s) -> blank", pupil_id)
        return _blank_record(pupil_id)
    return _row_to_record(row)


def set_step(pupil_id: str, step: str, done: bool) -> OnboardingRecord:
    _ensure_schema()
    if step not in STEP_KEYS:
        raise ValidationError(
            f"Unknown onboarding step: {step!r}. "
            f"Allowed: {', '.join(STEP_KEYS)}"
        )
    pupil = pupils_data.get_pupil(pupil_id)
    if pupil is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    flag = 1 if done else 0
    try:
        with pupils_data._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO pupil_onboarding(pupil_id) VALUES (?)",
                (pupil_id,),
            )
            conn.execute(
                f"UPDATE pupil_onboarding "
                f"SET {step} = ?, updated_at = datetime('now') "
                f"WHERE pupil_id = ?",
                (flag, pupil_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("set_step(%s, %s, %s) failed", pupil_id, step, done)
        raise
    logger.info("Onboarding: pupil %s step %s -> %s",
                pupil_id, step, "done" if done else "pending")
    return get_record(pupil_id)


def mark_all(pupil_id: str, done: bool) -> OnboardingRecord:
    _ensure_schema()
    pupil = pupils_data.get_pupil(pupil_id)
    if pupil is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    flag = 1 if done else 0
    set_clause = ", ".join(f"{k} = ?" for k in STEP_KEYS)
    params: list[Any] = [flag] * len(STEP_KEYS)
    params.append(pupil_id)
    try:
        with pupils_data._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO pupil_onboarding(pupil_id) VALUES (?)",
                (pupil_id,),
            )
            conn.execute(
                f"UPDATE pupil_onboarding "
                f"SET {set_clause}, updated_at = datetime('now') "
                f"WHERE pupil_id = ?",
                params,
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("mark_all(%s, %s) failed", pupil_id, done)
        raise
    logger.info("Onboarding: pupil %s mark_all -> %s",
                pupil_id, "done" if done else "reset")
    return get_record(pupil_id)


def list_records(
    *, pending_only: bool = False, year_group: str | None = None,
) -> list[tuple[Pupil, OnboardingRecord]]:
    _ensure_schema()
    try:
        with pupils_data._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM pupil_onboarding"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise
    by_id: dict[str, OnboardingRecord] = {
        r["pupil_id"]: _row_to_record(r) for r in rows
    }
    out: list[tuple[Pupil, OnboardingRecord]] = []
    for p in pupils_data.list_pupils():
        if year_group and p.year_group != year_group:
            continue
        rec = by_id.get(p.pupil_id) or _blank_record(p.pupil_id)
        if pending_only and rec.complete:
            continue
        out.append((p, rec))
    logger.debug(
        "list_records(pending_only=%s, year_group=%s) -> %d row(s)",
        pending_only, year_group, len(out),
    )
    return out


def progress_summary() -> dict[str, int]:
    _ensure_schema()
    records = list_records()
    total = len(records)
    complete = sum(1 for _, r in records if r.complete)
    started = sum(1 for _, r in records if r.done_count > 0 and not r.complete)
    pending = total - complete - started
    summary = {
        "total": total,
        "complete": complete,
        "started": started,
        "pending": pending,
    }
    logger.debug("progress_summary -> %s", summary)
    return summary
