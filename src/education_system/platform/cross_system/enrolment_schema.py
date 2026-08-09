"""Enrolment-based learner journey schema (the flexible successor to slots).

``student_journey`` gives every learner one permanent ``journey_id`` and a
single ID slot per phase. That is exactly right for a linear
nursery → primary → secondary → sixth_form → university walk, and exactly
wrong for everything else: changing school mid-phase, attending two
nurseries, repeating a year, leaving and returning, transferring between
universities, skipping sixth form, or taking an apprenticeship first. A
slot can only ever hold the *most recent* local id, so every one of those
histories overwrites itself.

This module adds the two tables that carry the history the slots cannot::

    learner_enrolment    one row per (learner, institution, spell)
    learner_transition   one row per attempted move between enrolments

plus a ``learner_journey`` *view* over ``student_journey``. The view is
deliberately not a new table — the canonical identity, legal name and
matching keys already live in ``student_journey`` and duplicating them
would create two sources of truth for who somebody is. The view just
presents that row under the vocabulary the enrolment model uses
(``current_phase`` rather than ``current_system``).

Compatibility
-------------
The per-phase slot columns on ``student_journey`` stay populated and
authoritative-looking for existing readers. ``identity_service.link_system``
now dual-writes an enrolment alongside the slot, and
:func:`backfill_enrolments` derives enrolments from slots already in the
database, so enrolment rows are complete from day one rather than only
covering journeys that move after this lands.

Everything here targets the same auth DB as ``student_journey`` (see
``platform/identity/auth/schema.py``); the tables are created lazily by
:func:`ensure_enrolment_schema`, which is idempotent and safe to call on
every service entry point.
"""

from __future__ import annotations

import logging

from education_system.platform.identity.auth.db import connect
from education_system.platform.identity.auth.schema import initialise_auth_db

logger = logging.getLogger(__name__)


# ── Enrolment status vocabulary ─────────────────────────────────────
# An enrolment moves applicant → offered → accepted → active → (a terminal
# state). Not every enrolment starts at the top: a learner joining from an
# external institution mid-year is created directly as 'active'.
ENROLMENT_STATUSES: frozenset[str] = frozenset({
    "applicant",    # destination has a pending admission record
    "offered",      # a place has been offered
    "accepted",     # the offer was accepted, not yet admitted
    "active",       # currently enrolled and attending
    "deferred",     # accepted but start postponed
    "completed",    # finished this phase normally
    "transferred",  # left for another institution/system
    "withdrawn",    # left without completing
    "cancelled",    # applicant/offer that never became an enrolment
})

# Statuses that mean "this enrolment is still live" — a learner may hold
# more than one at once (dual enrolment, an applicant record at the next
# phase while still active at the current one).
OPEN_STATUSES: frozenset[str] = frozenset({
    "applicant", "offered", "accepted", "active", "deferred",
})

# Statuses that close an enrolment out. Note 'transferred' and 'completed'
# are distinct: the source enrolment is never deleted on progression, it is
# closed with the reason it ended.
CLOSED_STATUSES: frozenset[str] = ENROLMENT_STATUSES - OPEN_STATUSES


# ── Transition status vocabulary ────────────────────────────────────
# The seven steps of the common workflow, in order. See transitions.py for
# the state machine that walks them.
TRANSITION_STATUSES: tuple[str, ...] = (
    "expected",           # 1. source thinks this learner will move
    "applied",            # 2. an application exists at the destination
    "offered",            # 3. destination has offered a place
    "accepted",           # 4. offer accepted by learner/parent/admissions
    "handover_approved",  # 5. source approved the information transfer
    "admitted",           # 6. destination created its local learner id
    "completed",          # 7. journey updated, source enrolment closed
)

# Terminal failure state, reachable from any step.
TRANSITION_CANCELLED = "cancelled"

ALL_TRANSITION_STATUSES: frozenset[str] = frozenset(
    TRANSITION_STATUSES) | {TRANSITION_CANCELLED}


_SCHEMA_SQL = """
-- ── Enrolment history ───────────────────────────────────────────────
-- One row per spell at one institution. A learner has as many rows as
-- they have had places: two nurseries, a repeated Year 9, a university
-- transfer and an apprenticeship are five rows, not five overwritten
-- slots. ``system`` is a phase key (nursery/primary/secondary/
-- sixth_form/university) or one of the non-phase destinations
-- (external/apprenticeship/employment/home_education) so a journey that
-- leaves the platform is still recorded rather than simply stopping.
CREATE TABLE IF NOT EXISTS learner_enrolment (
    enrolment_id     TEXT    PRIMARY KEY,
    journey_id       TEXT    NOT NULL REFERENCES student_journey(journey_id),
    system           TEXT    NOT NULL,
    institution_id   TEXT,
    local_student_id TEXT,
    start_date       TEXT,
    end_date         TEXT,
    status           TEXT    NOT NULL DEFAULT 'applicant',
    year_group       TEXT,
    exit_reason      TEXT,
    notes            TEXT,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_enrolment_journey
    ON learner_enrolment(journey_id, status);
CREATE INDEX IF NOT EXISTS idx_enrolment_system_local
    ON learner_enrolment(system, local_student_id)
    WHERE local_student_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_enrolment_system_status
    ON learner_enrolment(system, status);

-- Deliberately NOT unique on (journey_id, system, local_student_id): a
-- learner who leaves and later returns to the same institution keeps their
-- old local id, and that second spell is a second row. Idempotency for
-- repeated dual-writes is handled in enrolments.link_local_enrolment,
-- which reuses an *open* enrolment and only creates when none is live.
CREATE INDEX IF NOT EXISTS idx_enrolment_journey_system
    ON learner_enrolment(journey_id, system);

-- ── Transition history ──────────────────────────────────────────────
-- One row per attempted move. Rows are kept when a move is cancelled or
-- abandoned — "applied and was rejected" is part of the journey.
CREATE TABLE IF NOT EXISTS learner_transition (
    transition_id            TEXT    PRIMARY KEY,
    journey_id               TEXT    NOT NULL REFERENCES student_journey(journey_id),
    source_enrolment_id      TEXT    REFERENCES learner_enrolment(enrolment_id),
    source_system            TEXT,
    destination_system       TEXT    NOT NULL,
    destination_enrolment_id TEXT    REFERENCES learner_enrolment(enrolment_id),
    status                   TEXT    NOT NULL DEFAULT 'expected',
    initiated_at             TEXT    NOT NULL DEFAULT (datetime('now')),
    completed_at             TEXT,
    reason                   TEXT,
    actor_user_id            INTEGER,
    handover_json            TEXT,
    handover_approved_at     TEXT,
    consent_reference        TEXT,
    cancelled_reason         TEXT,
    updated_at               TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_transition_journey
    ON learner_transition(journey_id, initiated_at);
CREATE INDEX IF NOT EXISTS idx_transition_status
    ON learner_transition(status, destination_system);
CREATE INDEX IF NOT EXISTS idx_transition_dest_enrolment
    ON learner_transition(destination_enrolment_id)
    WHERE destination_enrolment_id IS NOT NULL;

-- ── Canonical journey, in enrolment vocabulary ──────────────────────
-- A view, not a table: student_journey already owns legal identity and is
-- the row every existing reader and the DOB+name unique index point at.
-- Duplicating it would give the platform two answers to "who is this".
CREATE VIEW IF NOT EXISTS learner_journey AS
    SELECT journey_id,
           legal_first_name,
           legal_last_name,
           date_of_birth,
           nhs_number,
           upn,
           current_system AS current_phase,
           status,
           created_at,
           updated_at
      FROM student_journey;
"""


_initialised: set[str] = set()


def ensure_enrolment_schema(db_path: str | None = None) -> None:
    """Create the enrolment tables/view if absent. Idempotent and cheap.

    Also ensures the base auth schema, because ``learner_enrolment``
    carries a foreign key onto ``student_journey``.
    """
    key = db_path or "<default>"
    if key in _initialised:
        return
    try:
        initialise_auth_db(db_path)
    except Exception:
        logger.debug("enrolment_schema: auth schema init skipped",
                     exc_info=True)
    conn = connect(db_path)
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
    _initialised.add(key)


def reset_schema_cache_for_test() -> None:
    """Test-only: forget which db_paths have been initialised.

    Tests that build a fresh temp auth DB per case would otherwise be
    skipped by the ``_initialised`` short-circuit if a previous test used
    the same path string.
    """
    _initialised.clear()


# ---------------------------------------------------------------------------
# Backfill — derive enrolments from the legacy per-phase slots
# ---------------------------------------------------------------------------

# Ordered so a journey's history reads in phase order regardless of which
# slots happen to be populated.
from education_system.platform.cross_system.identity_service import (  # noqa: E402
    SYSTEM_SLOTS,
)

# Every system with a journey slot, in reading order. Must stay a superset
# of SYSTEM_SLOTS or the backfill silently skips a populated slot: an FE
# learner or an apprentice would end up with no enrolment row derived for
# them, which is exactly the gap this backfill exists to close.
_PHASE_ORDER: tuple[str, ...] = (
    "nursery", "primary", "secondary", "sixth_form", "fe_college",
    "apprenticeships", "university")


def backfill_enrolments(*, db_path: str | None = None) -> dict[str, int]:
    """Derive one ``learner_enrolment`` per populated legacy slot.

    A slot that matches the journey's ``current_system`` becomes an
    ``active`` enrolment; earlier phases become ``completed`` with an
    exit reason of ``progressed``. Existing enrolment rows are left
    untouched, so this is safe to re-run and safe to run after enrolments
    have already started being written live.

    Concurrency cannot be recovered here, only going forward. A degree
    apprentice holds a university and an apprenticeships enrolment at the
    same time, but the slots record one ``current_system`` between them,
    so the backfill closes the other. Live transitions record both,
    because they know ``close_source`` was False.

    Returns a summary dict of counts.
    """
    ensure_enrolment_schema(db_path)
    # Imported here to avoid a circular import at module load: enrolments
    # imports this module for ensure_enrolment_schema.
    from education_system.platform.cross_system import enrolments

    summary = {"journeys": 0, "created": 0, "existing": 0, "no_slots": 0}
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM student_journey").fetchall()
        existing = {
            (r["journey_id"], r["system"], r["local_student_id"])
            for r in conn.execute(
                "SELECT journey_id, system, local_student_id "
                "FROM learner_enrolment").fetchall()
        }
    finally:
        conn.close()

    for row in rows:
        summary["journeys"] += 1
        journey = dict(row)
        current = journey.get("current_system")
        populated = 0
        for phase in _PHASE_ORDER:
            _pk_col, id_col = SYSTEM_SLOTS[phase]
            local_id = journey.get(id_col)
            if not local_id:
                continue
            populated += 1
            if (journey["journey_id"], phase, local_id) in existing:
                summary["existing"] += 1
                continue
            is_current = (phase == current)
            try:
                enrolments.create_enrolment(
                    journey_id=journey["journey_id"],
                    system=phase,
                    local_student_id=local_id,
                    status="active" if is_current else "completed",
                    exit_reason=None if is_current else "progressed",
                    notes="backfilled from student_journey slot",
                    db_path=db_path,
                )
                summary["created"] += 1
            except Exception:
                logger.exception(
                    "Enrolment backfill failed for journey %s phase %s",
                    journey["journey_id"], phase)
        if populated == 0:
            summary["no_slots"] += 1

    logger.info(
        "Enrolment backfill: %d journeys, %d enrolments created, "
        "%d already present, %d journeys with no linked slot",
        summary["journeys"], summary["created"], summary["existing"],
        summary["no_slots"])
    return summary


__all__ = [
    "ENROLMENT_STATUSES",
    "OPEN_STATUSES",
    "CLOSED_STATUSES",
    "TRANSITION_STATUSES",
    "TRANSITION_CANCELLED",
    "ALL_TRANSITION_STATUSES",
    "ensure_enrolment_schema",
    "reset_schema_cache_for_test",
    "backfill_enrolments",
]
