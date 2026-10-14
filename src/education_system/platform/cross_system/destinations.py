"""Where learners went after they left: destinations and outcomes.

The sixth form tracks leavers locally, at the point of leaving and at +6
and +12 months, and nothing else on the platform tracked them at all. A
secondary leaver who went into an apprenticeship, or a university drop-out
who went into work, simply fell off the end of the journey. Transitions to
employment, training or a gap year were opened and then sat at
``expected`` for ever.

This module keeps one platform-wide ``learner_destination`` table in
auth.db, keyed on the canonical ``journey_id``, so any system can record a
destination and analytics can count them across the whole platform:

    record_destination(journey_id, destination="employment",
                       checkpoint="leaving", source_system="sixth_form",
                       detail="Acme Engineering Ltd")

Completing a transition to a non-phase destination (employment, training,
gap year, NEET) records its leaving destination automatically. See
``transitions.complete``.

One row per (journey, source system, checkpoint). Recording the same
checkpoint again corrects it rather than adding a second answer to "where
were they at +6 months?".
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import date
from typing import Any

from education_system.platform.cross_system.enrolment_schema import (
    ensure_enrolment_schema,
)
from education_system.platform.identity.auth.db import connect
from education_system.platform.integrations.external import cross_system_bus

logger = logging.getLogger(__name__)

_SOURCE_MODULE = "platform.cross_system.destinations"

#: The destination vocabulary. These are DfE destination-measure categories,
#: flattened so a count needs no lookup table.
DESTINATION_KINDS: tuple[str, ...] = (
    "employment",
    "apprenticeship",
    "higher_education",
    "further_education",
    "training",
    "gap_year",
    "neet",
    "unknown",
)

#: When the destination was true: on leaving, and at the two follow-ups.
CHECKPOINTS: tuple[str, ...] = ("leaving", "6_months", "12_months")

# Spellings used elsewhere, folded onto the vocabulary above. The sixth
# form's own labels ("Higher Education", "PLUS_6") are listed so its local
# records can be mirrored without a translation table of their own.
_DESTINATION_ALIASES: dict[str, str] = {
    "higher education": "higher_education",
    "he": "higher_education",
    "university": "higher_education",
    "further education": "further_education",
    "fe": "further_education",
    "fe_college": "further_education",
    "sixth_form": "further_education",
    "apprenticeships": "apprenticeship",
    "gap year": "gap_year",
    "not in education, employment or training": "neet",
}

_CHECKPOINT_ALIASES: dict[str, str] = {
    "at leaving": "leaving",
    "on leaving": "leaving",
    "+6": "6_months",
    "+6 months": "6_months",
    "plus_6": "6_months",
    "6m": "6_months",
    "six_months": "6_months",
    "+12": "12_months",
    "+12 months": "12_months",
    "plus_12": "12_months",
    "12m": "12_months",
    "twelve_months": "12_months",
}

# Transition destination (a system key or a non-phase label) to the
# destination kind it implies. Only the non-phase destinations are recorded
# automatically on completion. The system keys are here so a caller that
# wants a phase move counted (sixth form into university, say) can
# translate it the same way.
_SYSTEM_TO_KIND: dict[str, str] = {
    "employment": "employment",
    "training": "training",
    "gap_year": "gap_year",
    "neet": "neet",
    "apprenticeships": "apprenticeship",
    "university": "higher_education",
    "fe_college": "further_education",
    "sixth_form": "further_education",
}


class DestinationError(ValueError):
    """An unknown destination or checkpoint."""


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS learner_destination (
    destination_id  TEXT    PRIMARY KEY,
    journey_id      TEXT    NOT NULL REFERENCES student_journey(journey_id),
    destination     TEXT    NOT NULL,
    checkpoint      TEXT    NOT NULL,
    -- The employer or institution, e.g. "Acme Ltd" or "University of Leeds".
    detail          TEXT,
    source_system   TEXT    NOT NULL,
    recorded_on     TEXT    NOT NULL DEFAULT (date('now')),
    recorded_by     TEXT,
    notes           TEXT,
    -- The transition that produced it, when it came from one.
    transition_id   TEXT    REFERENCES learner_transition(transition_id),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_destination_checkpoint
    ON learner_destination(journey_id, source_system, checkpoint);
CREATE INDEX IF NOT EXISTS idx_destination_recorded
    ON learner_destination(recorded_on, destination);
"""

_initialised: set[str] = set()


def ensure_destination_schema(db_path: str | None = None) -> None:
    """Create ``learner_destination`` if absent. Idempotent and cheap."""
    key = db_path or "<default>"
    if key in _initialised:
        return
    # Both foreign-key targets (student_journey, learner_transition) are
    # created there, and FK enforcement is on everywhere.
    ensure_enrolment_schema(db_path)
    conn = connect(db_path)
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
    _initialised.add(key)


def reset_schema_cache_for_test() -> None:
    """Test-only: forget which db_paths have been initialised."""
    _initialised.clear()


def normalise_destination(value: str) -> str:
    """Fold a destination label onto :data:`DESTINATION_KINDS`."""
    raw = (value or "").strip().lower()
    kind = _DESTINATION_ALIASES.get(raw, raw.replace(" ", "_"))
    if kind not in DESTINATION_KINDS:
        raise DestinationError(
            f"Unknown destination {value!r}; expected one of "
            f"{', '.join(DESTINATION_KINDS)}")
    return kind


def normalise_checkpoint(value: str) -> str:
    """Fold a checkpoint label onto :data:`CHECKPOINTS`."""
    raw = (value or "").strip().lower()
    cp = _CHECKPOINT_ALIASES.get(raw, raw.replace(" ", "_"))
    if cp not in CHECKPOINTS:
        raise DestinationError(
            f"Unknown checkpoint {value!r}; expected one of "
            f"{', '.join(CHECKPOINTS)}")
    return cp


def destination_kind_for_system(system: str | None) -> str | None:
    """The destination kind a transition to ``system`` implies, or None."""
    if not system:
        return None
    return _SYSTEM_TO_KIND.get(system.strip().lower())


def _row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(r) if r is not None else None


def record_destination(
    journey_id: str,
    *,
    destination: str,
    checkpoint: str,
    source_system: str,
    detail: str | None = None,
    recorded_by: str | None = None,
    recorded_on: str | None = None,
    notes: str | None = None,
    transition_id: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Record (or correct) where a learner was at one checkpoint.

    Publishes ``destination.recorded`` with the kind and checkpoint only.
    The employer or institution name stays in the table, so bus rows carry
    nothing identifying beyond the journey id they already carry.
    """
    if not journey_id:
        raise DestinationError("journey_id is required")
    if not source_system:
        raise DestinationError("source_system is required")
    kind = normalise_destination(destination)
    cp = normalise_checkpoint(checkpoint)
    on = date.fromisoformat(recorded_on[:10]).isoformat() if recorded_on \
        else date.today().isoformat()
    ensure_destination_schema(db_path)

    conn = connect(db_path)
    try:
        conn.execute(
            """INSERT INTO learner_destination
                 (destination_id, journey_id, destination, checkpoint, detail,
                  source_system, recorded_on, recorded_by, notes,
                  transition_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(journey_id, source_system, checkpoint) DO UPDATE
                  SET destination   = excluded.destination,
                      detail        = excluded.detail,
                      recorded_on   = excluded.recorded_on,
                      recorded_by   = excluded.recorded_by,
                      notes         = COALESCE(excluded.notes,
                                               learner_destination.notes),
                      transition_id = COALESCE(excluded.transition_id,
                                               learner_destination.transition_id),
                      updated_at    = datetime('now')""",
            (str(uuid.uuid4()), journey_id, kind, cp, detail, source_system,
             on, recorded_by, notes, transition_id))
        conn.commit()
        row = _row(conn.execute(
            "SELECT * FROM learner_destination WHERE journey_id = ? "
            "AND source_system = ? AND checkpoint = ?",
            (journey_id, source_system, cp)).fetchone())
    finally:
        conn.close()
    assert row is not None

    try:
        # Broadcast: destinations feed platform analytics, which is not any
        # one system's, and the payload is the category alone.
        cross_system_bus.publish_cross_system(
            cross_system_bus.EVENT_DESTINATION_RECORDED,
            source_system=source_system, source_module=_SOURCE_MODULE,
            journey_id=journey_id, target_system=None, db_path=db_path,
            idempotency_key=(f"destination.recorded:{row['destination_id']}:"
                             f"{kind}:{on}"),
            destination_id=row["destination_id"], destination=kind,
            checkpoint=cp, recorded_on=on, transition_id=transition_id)
    except Exception:
        logger.exception("Destination %s recorded but not published",
                         row["destination_id"])
    logger.info("Recorded %s destination %s for journey %s (%s)", cp, kind,
                journey_id, source_system)
    return row


def destinations_for(journey_id: str, *,
                     db_path: str | None = None) -> list[dict[str, Any]]:
    """Every recorded destination for a journey, in checkpoint order."""
    ensure_destination_schema(db_path)
    conn = connect(db_path)
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM learner_destination WHERE journey_id = ? "
            "ORDER BY recorded_on, created_at", (journey_id,)).fetchall()]
    finally:
        conn.close()
    order = {cp: i for i, cp in enumerate(CHECKPOINTS)}
    rows.sort(key=lambda r: (order.get(r["checkpoint"], 99),
                             r["recorded_on"], r["created_at"]))
    return rows


def outcome_summary(*, since: str | None = None,
                    source_system: str | None = None,
                    db_path: str | None = None) -> dict[str, Any]:
    """Destination counts for analytics, zero-filled so charts line up.

    ``since`` filters on ``recorded_on`` (an ISO date, inclusive).
    ``by_checkpoint_destination`` is the checkpoint-by-destination grid,
    the shape a destination-measures report is laid out in.
    """
    ensure_destination_schema(db_path)
    sql = ["SELECT checkpoint, destination, COUNT(*) AS n, "
           "COUNT(DISTINCT journey_id) AS learners "
           "FROM learner_destination WHERE 1 = 1"]
    args: list[Any] = []
    if since:
        sql.append("AND recorded_on >= ?")
        args.append(date.fromisoformat(since[:10]).isoformat())
    if source_system:
        sql.append("AND source_system = ?")
        args.append(source_system)
    sql.append("GROUP BY checkpoint, destination")
    conn = connect(db_path)
    try:
        rows = conn.execute(" ".join(sql), args).fetchall()
        where = " ".join(sql[1:-1])
        learners = conn.execute(
            f"SELECT COUNT(DISTINCT journey_id) FROM learner_destination "  # nosec B608
            f"WHERE 1 = 1 {where}", args).fetchone()[0]
    finally:
        conn.close()

    by_destination = dict.fromkeys(DESTINATION_KINDS, 0)
    by_checkpoint = dict.fromkeys(CHECKPOINTS, 0)
    grid = {cp: dict.fromkeys(DESTINATION_KINDS, 0) for cp in CHECKPOINTS}
    total = 0
    for r in rows:
        cp, kind, n = r["checkpoint"], r["destination"], int(r["n"])
        total += n
        # Rows outside the vocabulary cannot be written through this module,
        # but a hand-edited row should be counted rather than lost.
        by_destination[kind] = by_destination.get(kind, 0) + n
        by_checkpoint[cp] = by_checkpoint.get(cp, 0) + n
        grid.setdefault(cp, dict.fromkeys(DESTINATION_KINDS, 0))
        grid[cp][kind] = grid[cp].get(kind, 0) + n
    return {
        "since": since,
        "source_system": source_system,
        "total": total,
        "learners": int(learners or 0),
        "by_destination": by_destination,
        "by_checkpoint": by_checkpoint,
        "by_checkpoint_destination": grid,
    }


__all__ = [
    "DESTINATION_KINDS",
    "CHECKPOINTS",
    "DestinationError",
    "ensure_destination_schema",
    "reset_schema_cache_for_test",
    "normalise_destination",
    "normalise_checkpoint",
    "destination_kind_for_system",
    "record_destination",
    "destinations_for",
    "outcome_summary",
]
