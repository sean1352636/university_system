"""Canonical cross-system student identity (the ``student_journey`` registry).

One ``student_journey`` row per real person, identified by a stable
``journey_id``. Each system links its local student id into its own slot
(``school_*`` / ``college_*`` / ``university_*`` / ``primary_*`` ...) rather
than every system duplicating and re-keying demographics on transfer.

The sixth-form system is the ``college`` slot; the university system is
the ``university`` slot (matching the launcher's auth seed keys).

Resolution
----------
:func:`get_or_create_journey` decides whether a newly seen local record is
a person the registry already knows. In order:

1. the calling system's local id is already linked — idempotent re-register;
2. an NHS number or UPN matches — strong identifiers win over names;
3. the normalised legal name and date of birth match, **unless** the
   candidate carries a different NHS number/UPN, or already holds a
   *different, still-open* record in the same system — and only when
   exactly one journey survives those exclusions. Two equally good
   matches link to neither.

Case 3's exclusions are what stop two different people who share a name
and birthday being folded into one journey. The cost of being cautious is
a possible duplicate journey, which :func:`find_duplicate_candidates`
surfaces with its reasons and :func:`merge_journeys` resolves; the cost of
the old behaviour was one child's record appearing under another's.

This is the service the schema comment in ``platform/identity/auth/schema.py``
refers to; the tables exist there and are created by ``initialise_auth_db``.
"""

from __future__ import annotations

import difflib
import json
import logging
import re
import sqlite3
import unicodedata
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from education_system.platform.identity.auth.db import connect
from education_system.platform.identity.auth.schema import initialise_auth_db

logger = logging.getLogger(__name__)

# system key -> (pk_column, student_id_column) in student_journey
SYSTEM_SLOTS: dict[str, tuple[str, str]] = {
    "nursery":    ("nursery_pk", "nursery_student_id"),
    "primary":    ("primary_pk", "primary_student_id"),
    "secondary":     ("school_pk", "school_student_id"),
    "sixth_form":    ("college_pk", "college_student_id"),
    "fe_college": ("fe_college_pk", "fe_college_student_id"),
    "apprenticeships": ("apprenticeships_pk", "apprenticeships_learner_id"),
    "university": ("university_pk", "university_student_id"),
    # A PRU / AP placement. Not a phase: pupils come from primary or
    # secondary and usually go back (see platform.cross_system.ap_referrals).
    "alternative_provision": ("alternative_provision_pk",
                              "alternative_provision_pupil_id"),
    # The SEND service's case (register, EHCP). Not a phase either: the
    # pupil stays at their school (see platform.cross_system.send_referrals).
    "special_education": ("special_education_pk", "special_education_learner_id"),
    # Adult community learning. Adults move to and from FE College and go on
    # to university (see platform.cross_system.adult_education_applications).
    "adult_education": ("adult_education_pk", "adult_education_learner_id"),
    # Short courses and certificates. Apprenticeship providers and FE colleges
    # send learners for training; learners go on to an apprenticeship or FE
    # (see platform.cross_system.training_provider_requests).
    "training_provider": ("training_provider_pk", "training_provider_learner_id"),
    # The local authority's record of a child (admissions, attendance and
    # welfare, exclusions, SEND). Not a phase: it runs alongside the school
    # place (see platform.cross_system.local_authority_links).
    "local_authority": ("local_authority_pk", "local_authority_child_id"),
}

# The post-16 systems a learner may hold *concurrently* with another. A
# degree apprentice is enrolled with the university and the training
# provider at once, and an FE learner may convert to an apprenticeship
# mid-programme while the FE enrolment stays open. Callers that assume one
# live system per learner should consult this before closing the other.
CONCURRENT_SYSTEMS: frozenset[str] = frozenset({
    "apprenticeships", "fe_college", "university", "sixth_form",
    # Dual registration: the pupil stays on the home school's roll while
    # attending alternative provision.
    "alternative_provision",
    # A SEND service case runs alongside the school place.
    "special_education",
    # An adult course is usually part-time, alongside FE or other study.
    "adult_education",
    # A short course runs alongside an apprenticeship or an FE programme.
    "training_provider",
    # The local authority's casework runs alongside the school place.
    "local_authority",
})

#: ``student_journey.status`` of a journey folded into another. The row is
#: kept (it is the target of ``merged_into`` and of the merge log) but is
#: never returned by identity lookups.
MERGED_STATUS = "merged"

_SOURCE_MODULE = "platform.cross_system.identity_service"

# Tables in auth.db that key rows on journey_id and must follow a merge.
# Each is checked for existence first, so a table another module creates
# lazily (enrolments, qualifications) is simply skipped when absent.
_JOURNEY_KEYED_TABLES: tuple[str, ...] = (
    "learner_enrolment",
    "learner_transition",
    "student_journey_transitions",
    "safeguarding_alerts",
    "cross_system_event_outbox",
    "learner_qualification",
    "enrolment_year_history",
    "learner_destination",
    "users",
)

_initialised: set[str] = set()


class MergeError(ValueError):
    """A merge was refused (unknown/merged journey, conflicting identifiers)."""


def _ensure(db_path: str | None) -> None:
    key = db_path or "<default>"
    if key in _initialised:
        return
    try:
        initialise_auth_db(db_path)
    except Exception:
        logger.debug("identity_service: auth schema init skipped",
                     exc_info=True)
    _initialised.add(key)


def _slots(system: str) -> tuple[str, str]:
    if system not in SYSTEM_SLOTS:
        raise ValueError(
            f"Unknown system {system!r}; expected one of "
            f"{', '.join(SYSTEM_SLOTS)}")
    return SYSTEM_SLOTS[system]


def _row_to_dict(row) -> dict | None:
    return dict(row) if row is not None else None


def _is_merged(row: dict | None) -> bool:
    return bool(row) and (row.get("status") == MERGED_STATUS)


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def normalise_name(value: Any) -> str:
    """Casefold, strip accents, and collapse whitespace and punctuation.

    ``"  O'Brien-Smith "`` and ``"o brien smith"`` compare equal, which is
    what two admissions clerks typing the same name actually produce.
    """
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w\s]", " ", text.casefold())
    return " ".join(text.split())


def normalise_nhs_number(value: Any) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits or None


def normalise_upn(value: Any) -> str | None:
    text = re.sub(r"[^0-9A-Za-z]", "", str(value or "")).upper()
    return text or None


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def get(journey_id: str, *, db_path: str | None = None) -> dict | None:
    """The raw registry row, including a tombstoned (merged) one."""
    _ensure(db_path)
    conn = connect(db_path)
    try:
        r = conn.execute(
            "SELECT * FROM student_journey WHERE journey_id = ?",
            (journey_id,)).fetchone()
    finally:
        conn.close()
    return _row_to_dict(r)


def resolve_journey_id(journey_id: str | None, *,
                       db_path: str | None = None) -> str | None:
    """Follow ``merged_into`` to the surviving journey.

    A local row stamped before a merge (or whose re-stamp failed) still
    carries the duplicate's id; resolving it here means that stale id keeps
    working rather than pointing at a tombstone. Returns None if unknown.
    """
    if not journey_id:
        return None
    seen: set[str] = set()
    current = journey_id
    while current and current not in seen:
        seen.add(current)
        row = get(current, db_path=db_path)
        if row is None:
            return None
        if not _is_merged(row) or not row.get("merged_into"):
            return current
        current = row["merged_into"]
    return None


def _live_rows_for_dob(conn, date_of_birth: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM student_journey WHERE date_of_birth = ? "
        "AND COALESCE(status, '') != ? ORDER BY created_at, journey_id",
        (date_of_birth, MERGED_STATUS)).fetchall()]


def find_identity_candidates(first_name: str, last_name: str,
                             date_of_birth: str, *,
                             db_path: str | None = None) -> list[dict]:
    """Every live journey with this normalised name and date of birth.

    More than one is possible now that the name+DOB index is not unique.
    """
    _ensure(db_path)
    first, last = normalise_name(first_name), normalise_name(last_name)
    conn = connect(db_path)
    try:
        rows = _live_rows_for_dob(conn, date_of_birth)
    finally:
        conn.close()
    return [r for r in rows
            if normalise_name(r.get("legal_first_name")) == first
            and normalise_name(r.get("legal_last_name")) == last]


def find_by_identity(first_name: str, last_name: str,
                     date_of_birth: str, *,
                     db_path: str | None = None) -> dict | None:
    """The oldest live journey matching the normalised name and DOB.

    Case- and whitespace-insensitive. Callers that need to know about
    ambiguity should use :func:`find_identity_candidates`.
    """
    matches = find_identity_candidates(first_name, last_name, date_of_birth,
                                       db_path=db_path)
    return matches[0] if matches else None


def find_by_strong_id(*, nhs_number: str | None = None,
                      upn: str | None = None,
                      db_path: str | None = None) -> dict | None:
    """The oldest live journey carrying this NHS number or UPN."""
    nhs, pupil = normalise_nhs_number(nhs_number), normalise_upn(upn)
    if not (nhs or pupil):
        return None
    _ensure(db_path)
    conn = connect(db_path)
    try:
        if nhs:
            row = conn.execute(
                "SELECT * FROM student_journey "
                "WHERE REPLACE(REPLACE(nhs_number, ' ', ''), '-', '') = ? "
                "AND COALESCE(status, '') != ? ORDER BY created_at LIMIT 1",
                (nhs, MERGED_STATUS)).fetchone()
            if row is not None:
                return dict(row)
        if pupil:
            row = conn.execute(
                "SELECT * FROM student_journey "
                "WHERE UPPER(REPLACE(REPLACE(upn, ' ', ''), '-', '')) = ? "
                "AND COALESCE(status, '') != ? ORDER BY created_at LIMIT 1",
                (pupil, MERGED_STATUS)).fetchone()
            if row is not None:
                return dict(row)
    finally:
        conn.close()
    return None


def find_by_student(system: str, student_id: str, *,
                    db_path: str | None = None) -> dict | None:
    """The live journey a system's local id belongs to.

    Falls back to the enrolment history when no slot holds the id: a slot
    keeps only the latest local id per phase, so a learner's earlier spell
    (or a duplicate's id kept after a merge) is only findable there.
    """
    _ensure(db_path)
    _pk, id_col = _slots(system)
    conn = connect(db_path)
    try:
        r = conn.execute(
            f"SELECT * FROM student_journey WHERE {id_col} = ? "  # nosec B608 - column from SYSTEM_SLOTS
            "ORDER BY (COALESCE(status, '') = ?), created_at LIMIT 1",
            (student_id, MERGED_STATUS)).fetchone()
        via_enrolment = None
        if r is None:
            try:
                via_enrolment = conn.execute(
                    "SELECT journey_id FROM learner_enrolment "
                    "WHERE system = ? AND local_student_id = ? "
                    "ORDER BY created_at DESC LIMIT 1",
                    (system, str(student_id))).fetchone()
            except sqlite3.Error:
                via_enrolment = None
    finally:
        conn.close()
    row = _row_to_dict(r)
    if row is None and via_enrolment is not None:
        row = get(via_enrolment["journey_id"], db_path=db_path)
    if _is_merged(row):
        survivor = resolve_journey_id(row["journey_id"], db_path=db_path)
        row = get(survivor, db_path=db_path) if survivor else None
    return row


def find_by_students(system: str, student_ids,
                     *, db_path: str | None = None) -> dict[str, dict]:
    """``{student_id: journey}`` for many of one system's ids, in one query.

    :func:`find_by_student` opens a fresh connection per call, which is
    fine for the one-off lookups it was written for and quadratic-feeling
    the moment a screen asks about a whole cohort. Ids with no journey are
    absent from the result rather than mapped to ``None``, so a caller can
    use plain ``.get()``.
    """
    ids = [str(s) for s in student_ids if s]
    if not ids:
        return {}
    _ensure(db_path)
    _pk, id_col = _slots(system)
    out: dict[str, dict] = {}
    conn = connect(db_path)
    try:
        # Chunked to stay clear of SQLITE_MAX_VARIABLE_NUMBER, which is 999
        # on older builds — a sixth form with a thousand leavers is not a
        # stretch, and the failure would be an OperationalError at exactly
        # the busiest time of year.
        for start in range(0, len(ids), 500):
            chunk = ids[start:start + 500]
            placeholders = ",".join("?" * len(chunk))
            rows = conn.execute(
                f"SELECT * FROM student_journey "  # nosec B608 - column name
                f"WHERE {id_col} IN ({placeholders}) "  # from SYSTEM_SLOTS
                "AND COALESCE(status, '') != ?",
                [*chunk, MERGED_STATUS]).fetchall()
            for row in rows:
                journey = dict(row)
                out[str(journey[id_col])] = journey
    finally:
        conn.close()
    return out


# ---------------------------------------------------------------------------
# Bus publishing (best-effort)
# ---------------------------------------------------------------------------

def _publish(event_name: str, *, journey_id: str | None,
             idempotency_key: str, source_system: str = "platform",
             source_module: str = _SOURCE_MODULE,
             target_system: str | None = None,
             actor_user_id: int | None = None,
             db_path: str | None = None, **payload: Any) -> str | None:
    """Publish to the durable bus; never raises.

    Every caller has already committed the state the event describes, so a
    bus failure is logged rather than allowed to undo it.
    """
    try:
        from education_system.platform.integrations.external import (
            cross_system_bus,
        )
        return cross_system_bus.publish_cross_system(
            event_name, source_system=source_system,
            source_module=source_module, journey_id=journey_id,
            target_system=target_system, actor_user_id=actor_user_id,
            idempotency_key=idempotency_key, db_path=db_path, **payload)
    except Exception:
        logger.exception("Failed to publish %s for journey %s",
                         event_name, journey_id)
        return None


def registration_key(journey_id: str, system: str,
                     student_id: str | None) -> str:
    """Idempotency key for "this local record joined this journey".

    Shared by the mint path here and the systems' own create paths, so a
    brand-new learner produces one ``journey.registered`` event, not two.
    """
    return f"journey.registered:{journey_id}:{system}:{student_id or '-'}"


def publish_registered(journey_id: str, system: str,
                       student_id: str | None, *, minted: bool = False,
                       source_module: str | None = None,
                       db_path: str | None = None) -> str | None:
    """Announce that a local learner record is registered to a journey."""
    from education_system.platform.integrations.external import (
        cross_system_bus,
    )
    return _publish(
        cross_system_bus.EVENT_JOURNEY_REGISTERED, journey_id=journey_id,
        idempotency_key=registration_key(journey_id, system, student_id),
        source_system=system if system in SYSTEM_SLOTS else "platform",
        source_module=source_module or _SOURCE_MODULE, db_path=db_path,
        system=system, local_student_id=student_id, minted=minted)


# ---------------------------------------------------------------------------
# Link / register
# ---------------------------------------------------------------------------

def link_system(journey_id: str, system: str, *,
                student_id: str | None = None, pk: int | None = None,
                set_current: bool = False,
                db_path: str | None = None) -> dict:
    """Point a system's slot at this journey. Idempotent.

    A merged journey id is followed to its survivor, so a caller holding a
    stale id cannot re-populate a tombstone.
    """
    _ensure(db_path)
    pk_col, id_col = _slots(system)
    journey_id = resolve_journey_id(journey_id, db_path=db_path) or journey_id
    sets, args = [], []
    if student_id is not None:
        sets.append(f"{id_col} = ?")
        args.append(student_id)
    if pk is not None:
        sets.append(f"{pk_col} = ?")
        args.append(pk)
    if set_current:
        sets.append("current_system = ?")
        args.append(system)
    sets.append("updated_at = datetime('now')")
    args.append(journey_id)
    conn = connect(db_path)
    try:
        conn.execute(
            f"UPDATE student_journey SET {', '.join(sets)} "
            "WHERE journey_id = ?", args)
        conn.commit()
    finally:
        conn.close()
    out = get(journey_id, db_path=db_path)
    if out is None:
        raise ValueError(f"No journey {journey_id}")
    _mirror_enrolment(journey_id, system, student_id, db_path=db_path)
    return out


def _mirror_enrolment(journey_id: str, system: str,
                      student_id: str | None, *,
                      db_path: str | None = None) -> None:
    """Dual-write the slot link into ``learner_enrolment``.

    Slots record only the latest local id per phase; enrolments record
    every spell. Writing both keeps existing slot readers correct while
    the enrolment history becomes the authoritative one — see
    ``enrolment_schema`` for why the slots alone are not enough.

    Best-effort by design: this is a mirror of a write that has already
    committed, so a failure here must not fail the caller's link.
    """
    if not student_id:
        return
    try:
        from education_system.platform.cross_system import enrolments
        enrolments.link_local_enrolment(
            journey_id=journey_id, system=system,
            local_student_id=student_id, status="active",
            source_system=system, db_path=db_path)
    except Exception:
        logger.exception(
            "Enrolment mirror failed for journey %s / %s %s (slot link "
            "still applied)", journey_id, system, student_id)


def _held_record_is_open(conn, journey_id: str, system: str,
                         held_id: str) -> bool:
    """Whether ``held_id`` is (or may be) a live record of this journey.

    True when an open enrolment exists for it, and also when no enrolment
    row exists at all — without history we cannot prove the other record
    has ended, and assuming it has is how two people get merged.
    """
    from education_system.platform.cross_system.enrolment_schema import (
        OPEN_STATUSES,
    )
    try:
        rows = conn.execute(
            "SELECT status FROM learner_enrolment WHERE journey_id = ? "
            "AND system = ? AND local_student_id = ?",
            (journey_id, system, str(held_id))).fetchall()
    except sqlite3.Error:
        return True
    if not rows:
        return True
    return any(r["status"] in OPEN_STATUSES for r in rows)


def _strong_ids_conflict(candidate: dict, nhs: str | None,
                         pupil: str | None) -> list[str]:
    reasons = []
    theirs_nhs = normalise_nhs_number(candidate.get("nhs_number"))
    theirs_upn = normalise_upn(candidate.get("upn"))
    if nhs and theirs_nhs and nhs != theirs_nhs:
        reasons.append("NHS number differs")
    if pupil and theirs_upn and pupil != theirs_upn:
        reasons.append("UPN differs")
    return reasons


def _resolve_existing(*, system: str, student_id: str | None,
                      first_name: str, last_name: str, date_of_birth: str,
                      nhs_number: str | None, upn: str | None,
                      db_path: str | None) -> str | None:
    """Pick the journey an incoming local record belongs to, or None."""
    if student_id:
        linked = find_by_student(system, str(student_id), db_path=db_path)
        if linked is not None:
            return linked["journey_id"]

    strong = find_by_strong_id(nhs_number=nhs_number, upn=upn,
                               db_path=db_path)
    if strong is not None:
        if strong.get("date_of_birth") != date_of_birth:
            logger.warning(
                "Journey %s matched on NHS number/UPN but its DOB differs "
                "from the incoming %s record — linked on the strong "
                "identifier", strong["journey_id"], system)
        return strong["journey_id"]

    nhs, pupil = normalise_nhs_number(nhs_number), normalise_upn(upn)
    _pk, id_col = _slots(system)
    candidates = find_identity_candidates(first_name, last_name,
                                          date_of_birth, db_path=db_path)
    if not candidates:
        return None
    survivors: list[str] = []
    conn = connect(db_path)
    try:
        for cand in candidates:
            conflict = _strong_ids_conflict(cand, nhs, pupil)
            held = cand.get(id_col)
            if (not conflict and held and student_id
                    and str(held) != str(student_id)
                    and _held_record_is_open(conn, cand["journey_id"],
                                             system, held)):
                conflict.append(
                    f"already holds open {system} record {held}")
            if conflict:
                logger.info(
                    "Not linking %s record %s to journey %s despite a "
                    "name+DOB match: %s — a separate journey will be "
                    "created and flagged as a possible duplicate",
                    system, student_id or "-", cand["journey_id"],
                    "; ".join(conflict))
                continue
            survivors.append(cand["journey_id"])
    finally:
        conn.close()
    if len(survivors) == 1:
        if not (nhs or pupil):
            logger.info(
                "Linked %s record %s to journey %s on name + date of birth "
                "alone (no NHS number or UPN to confirm)", system,
                student_id or "-", survivors[0])
        return survivors[0]
    if len(survivors) > 1:
        # Two or more live journeys fit equally well. Picking the first is
        # a coin toss over whose record this learner joins; a separate
        # journey is the recoverable mistake — find_duplicate_candidates
        # surfaces it and merge_journeys resolves it.
        logger.warning(
            "Not linking %s record %s on name + date of birth: %d journeys "
            "match (%s). A separate journey will be created for review as a "
            "possible duplicate", system, student_id or "-", len(survivors),
            ", ".join(survivors))
    return None


def _fill_strong_ids(journey_id: str, nhs_number: str | None,
                     upn: str | None, *, db_path: str | None) -> None:
    """Record identifiers the registry lacked; never overwrite one."""
    if not (nhs_number or upn):
        return
    conn = connect(db_path)
    try:
        conn.execute(
            "UPDATE student_journey SET "
            "nhs_number = COALESCE(nhs_number, ?), upn = COALESCE(upn, ?), "
            "updated_at = datetime('now') WHERE journey_id = ?",
            (nhs_number or None, upn or None, journey_id))
        conn.commit()
    finally:
        conn.close()


def get_or_create_journey(*, first_name: str, last_name: str,
                          date_of_birth: str, system: str,
                          student_id: str | None = None,
                          pk: int | None = None,
                          nhs_number: str | None = None,
                          upn: str | None = None,
                          announce: bool = True,
                          db_path: str | None = None) -> str:
    """Return the canonical ``journey_id`` for a person, creating the
    registry row if this is the first system to see them. Links the
    calling system's slot to ``student_id`` and marks it current.

    See the module docstring for the resolution order. ``announce=False``
    suppresses the ``journey.registered`` event — the bulk backfill uses
    it so that registering historic records does not flood the bus.
    """
    _ensure(db_path)
    if not (first_name and last_name and date_of_birth):
        raise ValueError(
            "first_name, last_name and date_of_birth are required "
            "to register a journey")
    pk_col, id_col = _slots(system)
    existing = _resolve_existing(
        system=system, student_id=student_id, first_name=first_name,
        last_name=last_name, date_of_birth=date_of_birth,
        nhs_number=nhs_number, upn=upn, db_path=db_path)
    if existing is not None:
        link_system(existing, system, student_id=student_id, pk=pk,
                    set_current=True, db_path=db_path)
        _fill_strong_ids(existing, nhs_number, upn, db_path=db_path)
        return existing

    jid = str(uuid.uuid4())
    conn = connect(db_path)
    try:
        conn.execute(
            f"""INSERT INTO student_journey
                 (journey_id, legal_first_name, legal_last_name,
                  date_of_birth, nhs_number, upn, current_system,
                  status, {id_col}, {pk_col})
                 VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)""",
            (jid, first_name, last_name, date_of_birth, nhs_number,
             upn, system, student_id, pk))
        conn.commit()
    finally:
        conn.close()
    logger.info("Created student_journey %s for a %s record (%s)",
                jid, system, student_id or "-")
    # This path INSERTs the slot directly rather than going through
    # link_system, so it has to mirror the enrolment itself.
    _mirror_enrolment(jid, system, student_id, db_path=db_path)
    if announce:
        publish_registered(jid, system, student_id, minted=True,
                           db_path=db_path)
    return jid


def record_transition(journey_id: str, *, to_system: str,
                      from_system: str | None = None,
                      reason: str | None = None,
                      actor_user_id: int | None = None,
                      notes: str | None = None,
                      db_path: str | None = None) -> None:
    """Append an audit row and update the journey's current system."""
    _ensure(db_path)
    conn = connect(db_path)
    try:
        conn.execute(
            """INSERT INTO student_journey_transitions
                 (journey_id, from_system, to_system, reason,
                  actor_user_id, notes)
                 VALUES (?, ?, ?, ?, ?, ?)""",
            (journey_id, from_system, to_system, reason,
             actor_user_id, notes))
        conn.execute(
            "UPDATE student_journey SET current_system = ?, "
            "updated_at = datetime('now') WHERE journey_id = ?",
            (to_system, journey_id))
        conn.commit()
    finally:
        conn.close()
    logger.info("Journey %s transitioned %s -> %s", journey_id,
                from_system or "?", to_system)


def record_transition_once(journey_id: str, *, to_system: str,
                           from_system: str | None = None,
                           reason: str | None = None,
                           actor_user_id: int | None = None,
                           notes: str | None = None,
                           db_path: str | None = None) -> bool:
    """:func:`record_transition`, but a no-op if that move is already logged.

    ``student_journey_transitions`` is append-only, so a retryable
    transfer flow that records its move on every attempt writes the same
    hop two or three times and the journey reads as though the learner
    bounced between systems. Matching is on the hop — ``(journey_id,
    from_system, to_system)`` — not on the reason text, because a second
    attempt phrases itself differently while describing the same event.

    Returns True if a row was written. ``current_system`` is still
    refreshed on the duplicate path: the hop is what is deduplicated, not
    the journey's idea of where the learner is now.
    """
    _ensure(db_path)
    conn = connect(db_path)
    try:
        existing = conn.execute(
            """SELECT 1 FROM student_journey_transitions
                WHERE journey_id = ? AND to_system = ?
                  AND (from_system IS ? OR from_system = ?)
                LIMIT 1""",
            (journey_id, to_system, from_system, from_system)).fetchone()
        if existing:
            conn.execute(
                "UPDATE student_journey SET current_system = ?, "
                "updated_at = datetime('now') WHERE journey_id = ?",
                (to_system, journey_id))
            conn.commit()
            logger.debug(
                "Journey %s already has a %s -> %s transition — not "
                "recording a second", journey_id, from_system or "?",
                to_system)
            return False
    finally:
        conn.close()
    record_transition(journey_id, to_system=to_system,
                      from_system=from_system, reason=reason,
                      actor_user_id=actor_user_id, notes=notes,
                      db_path=db_path)
    return True


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DuplicateCandidate:
    """Two live journeys that may be the same person.

    ``journey_id`` is the suggested survivor (more linked systems, then
    older); ``duplicate_id`` the suggested one to fold into it. ``score`` is
    0–100; ``reasons`` says why, in words an administrator can check.
    """

    journey_id: str
    duplicate_id: str
    score: int
    reasons: tuple[str, ...]
    journey: dict = field(default_factory=dict)
    duplicate: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "journey_id": self.journey_id,
            "duplicate_id": self.duplicate_id,
            "score": self.score,
            "reasons": list(self.reasons),
            "journey": dict(self.journey),
            "duplicate": dict(self.duplicate),
        }


# Pairwise comparison inside one blocking group is quadratic; a group this
# large is a data problem (thousands sharing one birthday) that a screen of
# near-name suggestions would not help with anyway.
_MAX_BLOCK = 400


def _last4(value: Any) -> str | None:
    text = re.sub(r"\s", "", str(value or ""))
    return f"…{text[-4:]}" if text else None


def _summary(row: dict) -> dict:
    systems = [s for s, (_pk, col) in SYSTEM_SLOTS.items() if row.get(col)]
    # Identifiers are masked: the duplicates screen needs to show whether
    # two records agree, not to republish every learner's NHS number.
    return {
        "journey_id": row["journey_id"],
        "name": f"{row.get('legal_first_name') or ''} "
                f"{row.get('legal_last_name') or ''}".strip(),
        "date_of_birth": row.get("date_of_birth"),
        "nhs_number": _last4(row.get("nhs_number")),
        "upn": _last4(row.get("upn")),
        "current_system": row.get("current_system"),
        "systems": systems,
        "created_at": row.get("created_at"),
    }


def _similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def _first_names_close(a: str, b: str) -> bool:
    if not a or not b or a == b:
        return False
    if _similar(a, b) >= 0.8:
        return True
    # "Alex" / "Alexander", "Sam" / "Samuel": a registered short form.
    short, long_ = sorted((a, b), key=len)
    if len(short) >= 3 and long_.startswith(short):
        return True
    # "J" / "James": an initial typed where the name should be.
    return len(short) == 1 and long_.startswith(short)


def _dob_near(a: str | None, b: str | None) -> str | None:
    if not a or not b or a == b:
        return None
    pa, pb = a.split("-"), b.split("-")
    if len(pa) != 3 or len(pb) != 3:
        return None
    if pa[0] == pb[0] and pa[1] == pb[2] and pa[2] == pb[1]:
        return "same name, day and month of birth transposed"
    if sum(x != y for x, y in zip(pa, pb)) == 1:
        return "same name, date of birth differs in one part"
    return None


def _distinct_pairs(conn) -> set[tuple[str, str]]:
    try:
        rows = conn.execute(
            "SELECT journey_a, journey_b FROM student_journey_distinct"
        ).fetchall()
    except sqlite3.Error:
        return set()
    return {tuple(sorted((r["journey_a"], r["journey_b"]))) for r in rows}


def find_duplicate_candidates(*, limit: int = 100, min_score: int = 50,
                              db_path: str | None = None
                              ) -> list[DuplicateCandidate]:
    """Pairs of live journeys that are probably the same person, best first.

    Signals, strongest first: same NHS number (100), same UPN (95), same
    normalised name + DOB (90), names swapped (80), same surname + DOB with
    a close first name (75), same first name + DOB with a close surname
    (70), same name with a transposed or single-part-different DOB (65/55).
    Each extra agreeing signal adds 5. Disagreeing NHS numbers or UPNs
    subtract 40/30 — two records with different NHS numbers are almost
    always two people. Pairs an administrator marked distinct
    (:func:`mark_not_duplicate`) are excluded.
    """
    _ensure(db_path)
    conn = connect(db_path)
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM student_journey WHERE COALESCE(status, '') != ?",
            (MERGED_STATUS,)).fetchall()]
        dismissed = _distinct_pairs(conn)
    finally:
        conn.close()

    info: dict[str, dict] = {}
    for r in rows:
        info[r["journey_id"]] = {
            "row": r,
            "first": normalise_name(r.get("legal_first_name")),
            "last": normalise_name(r.get("legal_last_name")),
            "dob": r.get("date_of_birth"),
            "nhs": normalise_nhs_number(r.get("nhs_number")),
            "upn": normalise_upn(r.get("upn")),
        }

    signals: dict[tuple[str, str], dict[str, int]] = {}

    def add(a: str, b: str, score: int, reason: str) -> None:
        if a == b:
            return
        key = tuple(sorted((a, b)))
        if key in dismissed:
            return
        bucket = signals.setdefault(key, {})
        bucket[reason] = max(score, bucket.get(reason, 0))

    def groups(keyfn) -> Iterable[list[str]]:
        buckets: dict[Any, list[str]] = {}
        for jid, i in info.items():
            k = keyfn(i)
            if k:
                buckets.setdefault(k, []).append(jid)
        return (ids for ids in buckets.values() if 1 < len(ids) <= _MAX_BLOCK)

    def pairs(ids: list[str]) -> Iterable[tuple[str, str]]:
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                yield a, b

    for ids in groups(lambda i: i["nhs"]):
        for a, b in pairs(ids):
            add(a, b, 100, "same NHS number")
    for ids in groups(lambda i: i["upn"]):
        for a, b in pairs(ids):
            add(a, b, 95, "same UPN")
    for ids in groups(lambda i: (i["dob"], i["first"], i["last"])
                      if i["first"] and i["last"] else None):
        for a, b in pairs(ids):
            ra, rb = info[a]["row"], info[b]["row"]
            exact = (ra.get("legal_first_name"), ra.get("legal_last_name")) \
                == (rb.get("legal_first_name"), rb.get("legal_last_name"))
            add(a, b, 90, "same name and date of birth" if exact else
                "same name and date of birth once case, accents and "
                "spacing are normalised")
    for ids in groups(lambda i: i["dob"]):
        for a, b in pairs(ids):
            ia, ib = info[a], info[b]
            if (ia["first"], ia["last"]) == (ib["first"], ib["last"]):
                continue
            if ia["first"] == ib["last"] and ia["last"] == ib["first"]:
                add(a, b, 80, "first and last names swapped, same DOB")
            elif ia["last"] == ib["last"] and _first_names_close(
                    ia["first"], ib["first"]):
                add(a, b, 75, "same surname and DOB, similar first name "
                    f"({ia['row'].get('legal_first_name')} / "
                    f"{ib['row'].get('legal_first_name')})")
            elif ia["first"] == ib["first"] and (
                    _similar(ia["last"], ib["last"]) >= 0.85
                    or (ia["last"] and ib["last"] and (
                        set(ia["last"].split()) & set(ib["last"].split())))):
                add(a, b, 70, "same first name and DOB, similar surname "
                    f"({ia['row'].get('legal_last_name')} / "
                    f"{ib['row'].get('legal_last_name')})")
    for ids in groups(lambda i: (i["first"], i["last"])
                      if i["first"] and i["last"] else None):
        for a, b in pairs(ids):
            reason = _dob_near(info[a]["dob"], info[b]["dob"])
            if reason:
                add(a, b, 65 if "transposed" in reason else 55, reason)

    out: list[DuplicateCandidate] = []
    for (a, b), bucket in signals.items():
        ia, ib = info[a], info[b]
        score = max(bucket.values()) + 5 * (len(bucket) - 1)
        reasons = sorted(bucket, key=lambda r: -bucket[r])
        if ia["nhs"] and ib["nhs"] and ia["nhs"] != ib["nhs"]:
            score -= 40
            reasons.append("NHS numbers differ")
        if ia["upn"] and ib["upn"] and ia["upn"] != ib["upn"]:
            score -= 30
            reasons.append("UPNs differ")
        score = max(0, min(100, score))
        if score < min_score:
            continue
        ra, rb = ia["row"], ib["row"]

        def weight(r: dict) -> tuple[int, str]:
            linked = sum(1 for _pk, col in SYSTEM_SLOTS.values() if r.get(col))
            # Negated so that sorting ascending puts more-linked first; ties
            # go to the older row.
            return (-linked, r.get("created_at") or "")

        survivor, dup = sorted((ra, rb), key=weight)
        out.append(DuplicateCandidate(
            journey_id=survivor["journey_id"],
            duplicate_id=dup["journey_id"],
            score=score, reasons=tuple(reasons),
            journey=_summary(survivor), duplicate=_summary(dup)))
    out.sort(key=lambda c: (-c.score, c.journey.get("created_at") or ""))
    return out[:max(0, int(limit))]


def mark_not_duplicate(journey_a: str, journey_b: str, *, actor: str,
                       reason: str | None = None,
                       db_path: str | None = None) -> None:
    """Record that two journeys are different people.

    Without this, a pair of twins or two unrelated Oliver Smiths born the
    same day would sit at the top of the duplicates screen for ever.
    """
    if not actor or not str(actor).strip():
        raise ValueError("actor is required")
    if journey_a == journey_b:
        raise ValueError("A journey cannot be distinct from itself")
    _ensure(db_path)
    a, b = sorted((journey_a, journey_b))
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO student_journey_distinct "
            "(journey_a, journey_b, actor, reason) VALUES (?, ?, ?, ?)",
            (a, b, actor, reason))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def _table_has_journey_id(conn, table: str) -> bool:
    return any(r[1] == "journey_id" for r in conn.execute(
        f"PRAGMA table_info({table})").fetchall())  # nosec B608 - fixed names


def _audit_merge(*, actor: str, survivor_id: str, duplicate_id: str,
                 details: dict, audit_db_path: str | None) -> None:
    """Write the IDENTITY_MERGE audit row; raises if it cannot be written.

    Called inside the merge transaction so that a merge which could not be
    audited is rolled back rather than left standing unrecorded.
    """
    from education_system.platform.governance.audit.logger import (
        AuditAction,
        AuditLogger,
    )
    AuditLogger("platform", db_path=audit_db_path).log(
        AuditAction.IDENTITY_MERGE, username=actor,
        target_type="student_journey", target_id=survivor_id,
        details={"duplicate_journey_id": duplicate_id, **details},
        severity="warning")


def merge_journeys(survivor_id: str, duplicate_id: str, *, actor: str,
                   reason: str | None = None, force: bool = False,
                   db_path: str | None = None,
                   audit_db_path: str | None = None,
                   system_db_paths: dict | None = None) -> dict:
    """Fold ``duplicate_id`` into ``survivor_id``.

    In one auth.db transaction: every row keyed on the duplicate's journey
    (enrolments, both transition tables, safeguarding alerts, outbox rows,
    qualifications, year history, linked logins) is repointed; slots the
    survivor lacks are copied across and the duplicate's are cleared; the
    duplicate is tombstoned (``status='merged'``, ``merged_into``) and the
    merge logged to ``student_journey_merges`` with a snapshot of the
    duplicate for reversal. The IDENTITY_MERGE audit entry is written
    before commit — an unaudited merge is rolled back.

    After commit, best-effort: each local record the duplicate knew is
    re-stamped with the survivor's id via ``person.link_local_record``, and
    ``journey.merged`` is published.

    Refuses (``MergeError``) when either journey is unknown or already
    merged, or when the two carry different NHS numbers/UPNs unless
    ``force=True``. ``system_db_paths`` overrides per-system DBs (tests).
    """
    if not actor or not str(actor).strip():
        raise MergeError("actor is required to merge journeys")
    if not survivor_id or not duplicate_id or survivor_id == duplicate_id:
        raise MergeError("Two different journeys are required to merge")
    _ensure(db_path)

    conn = connect(db_path)
    local_records: list[tuple[str, str]] = []
    try:
        conn.execute("BEGIN IMMEDIATE")
        survivor = _row_to_dict(conn.execute(
            "SELECT * FROM student_journey WHERE journey_id = ?",
            (survivor_id,)).fetchone())
        duplicate = _row_to_dict(conn.execute(
            "SELECT * FROM student_journey WHERE journey_id = ?",
            (duplicate_id,)).fetchone())
        if survivor is None or duplicate is None:
            raise MergeError("Both journeys must exist to merge")
        if _is_merged(survivor) or _is_merged(duplicate):
            raise MergeError("A merged journey cannot take part in a merge")
        conflicts = _strong_ids_conflict(
            survivor, normalise_nhs_number(duplicate.get("nhs_number")),
            normalise_upn(duplicate.get("upn")))
        if conflicts and not force:
            raise MergeError(
                "Refusing to merge: " + "; ".join(conflicts)
                + ". Pass force=True if the identifiers are known to be wrong.")

        # Local records the duplicate knows, gathered before repointing so
        # they can be re-stamped once the merge has committed.
        for system, (_pk, id_col) in SYSTEM_SLOTS.items():
            if duplicate.get(id_col):
                local_records.append((system, str(duplicate[id_col])))
        try:
            for r in conn.execute(
                    "SELECT DISTINCT system, local_student_id "
                    "FROM learner_enrolment WHERE journey_id = ? "
                    "AND local_student_id IS NOT NULL",
                    (duplicate_id,)).fetchall():
                pair = (r["system"], str(r["local_student_id"]))
                if pair not in local_records:
                    local_records.append(pair)
        except sqlite3.Error:
            pass

        # Slots: the survivor keeps its own; empty ones are filled.
        sets, args = [], []
        slots_moved, slots_conflicting = [], []
        for system, (pk_col, id_col) in SYSTEM_SLOTS.items():
            dv, sv = duplicate.get(id_col), survivor.get(id_col)
            if dv and not sv:
                sets += [f"{id_col} = ?", f"{pk_col} = ?"]
                args += [dv, duplicate.get(pk_col)]
                slots_moved.append(system)
            elif dv and sv and str(dv) != str(sv):
                # Both held a record here. The survivor's stays in the slot;
                # the duplicate's survives in its (repointed) enrolments.
                slots_conflicting.append(system)
        for col in ("nhs_number", "upn"):
            if duplicate.get(col) and not survivor.get(col):
                sets.append(f"{col} = ?")
                args.append(duplicate[col])
        sets.append("updated_at = datetime('now')")
        conn.execute(
            f"UPDATE student_journey SET {', '.join(sets)} "  # nosec B608 - fixed columns
            "WHERE journey_id = ?", [*args, survivor_id])

        moved: dict[str, int] = {}
        for table in _JOURNEY_KEYED_TABLES:
            if not _table_has_journey_id(conn, table):
                continue
            cur = conn.execute(
                f"UPDATE {table} SET journey_id = ? "  # nosec B608 - fixed names
                "WHERE journey_id = ?", (survivor_id, duplicate_id))
            moved[table] = cur.rowcount

        cleared = ", ".join(f"{c} = NULL" for pair in SYSTEM_SLOTS.values()
                            for c in pair)
        conn.execute(
            f"UPDATE student_journey SET {cleared}, status = ?, "  # nosec B608 - fixed columns
            "merged_into = ?, merged_at = datetime('now'), "
            "updated_at = datetime('now') WHERE journey_id = ?",
            (MERGED_STATUS, survivor_id, duplicate_id))
        # Anything previously folded into the duplicate now points straight
        # at the survivor, so resolution stays a single hop.
        conn.execute(
            "UPDATE student_journey SET merged_into = ? "
            "WHERE merged_into = ?", (survivor_id, duplicate_id))

        merge_id = str(uuid.uuid4())
        details = {
            "merge_id": merge_id, "reason": reason, "forced": bool(force
                                                                 and conflicts),
            "moved": moved, "slots_moved": slots_moved,
            "slots_conflicting": slots_conflicting,
        }
        conn.execute(
            "INSERT INTO student_journey_merges "
            "(merge_id, survivor_id, duplicate_id, actor, reason, "
            " moved_json, duplicate_snapshot_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (merge_id, survivor_id, duplicate_id, actor, reason,
             json.dumps(details, default=str),
             json.dumps(duplicate, default=str)))
        _audit_merge(actor=actor, survivor_id=survivor_id,
                     duplicate_id=duplicate_id, details=details,
                     audit_db_path=audit_db_path)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    logger.warning("Journey %s merged into %s by %s (%s)", duplicate_id,
                   survivor_id, actor, reason or "no reason given")

    restamped = 0
    try:
        from education_system.platform.cross_system import person
        for system, local_id in local_records:
            path = (system_db_paths or {}).get(system)
            if person.link_local_record(system, local_id, survivor_id,
                                        db_path=str(path) if path else None):
                restamped += 1
    except Exception:
        logger.exception("Re-stamping local records after merge %s failed",
                         merge_id)

    from education_system.platform.integrations.external import (
        cross_system_bus,
    )
    event_id = _publish(
        cross_system_bus.EVENT_JOURNEY_MERGED, journey_id=survivor_id,
        idempotency_key=f"journey.merged:{duplicate_id}", db_path=db_path,
        merge_id=merge_id, survivor_journey_id=survivor_id,
        duplicate_journey_id=duplicate_id, moved=moved,
        slots_moved=slots_moved, slots_conflicting=slots_conflicting,
        merged_by=actor)

    return {
        "merge_id": merge_id,
        "survivor_id": survivor_id,
        "duplicate_id": duplicate_id,
        "moved": moved,
        "slots_moved": slots_moved,
        "slots_conflicting": slots_conflicting,
        "local_records": [list(p) for p in local_records],
        "restamped": restamped,
        "event_id": event_id,
    }


def list_merges(journey_id: str | None = None, *,
                db_path: str | None = None) -> list[dict]:
    """The merge log, newest first; filtered to one survivor or duplicate."""
    _ensure(db_path)
    conn = connect(db_path)
    try:
        if journey_id:
            rows = conn.execute(
                "SELECT * FROM student_journey_merges WHERE survivor_id = ? "
                "OR duplicate_id = ? ORDER BY merged_at DESC",
                (journey_id, journey_id)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM student_journey_merges "
                "ORDER BY merged_at DESC").fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["moved"] = json.loads(d.pop("moved_json") or "{}")
        # The snapshot is for reversal by an operator, not for display.
        d.pop("duplicate_snapshot_json", None)
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Login <-> learner link
# ---------------------------------------------------------------------------

def link_user_account(user_id: int, journey_id: str, *, actor: str,
                      db_path: str | None = None) -> None:
    """Link a login (``users.id``) to the learner it belongs to.

    A merged journey is followed to its survivor. The change is recorded
    in ``security_audit_log`` in the same transaction; ``username`` there is
    the actor, ``user_id`` the account that was linked.
    """
    if not actor or not str(actor).strip():
        raise ValueError("actor is required")
    _ensure(db_path)
    target = resolve_journey_id(journey_id, db_path=db_path)
    if target is None:
        raise ValueError(f"No journey {journey_id}")
    conn = connect(db_path)
    try:
        user = conn.execute(
            "SELECT id, username, journey_id FROM users WHERE id = ?",
            (int(user_id),)).fetchone()
        if user is None:
            raise ValueError(f"No user {user_id}")
        conn.execute(
            "UPDATE users SET journey_id = ?, updated_at = datetime('now') "
            "WHERE id = ?", (target, int(user_id)))
        conn.execute(
            "INSERT INTO security_audit_log (event_type, username, user_id, "
            "detail) VALUES (?, ?, ?, ?)",
            ("identity.user_linked", actor, int(user_id), json.dumps({
                "account": user["username"],
                "previous_journey_id": user["journey_id"],
                "journey_id": target})))
        conn.commit()
    finally:
        conn.close()
    logger.info("User %s linked to journey %s by %s", user_id, target, actor)


def unlink_user_account(user_id: int, *, actor: str,
                        db_path: str | None = None) -> None:
    """Remove a login's learner link (audited like :func:`link_user_account`)."""
    if not actor or not str(actor).strip():
        raise ValueError("actor is required")
    _ensure(db_path)
    conn = connect(db_path)
    try:
        user = conn.execute(
            "SELECT id, username, journey_id FROM users WHERE id = ?",
            (int(user_id),)).fetchone()
        if user is None:
            raise ValueError(f"No user {user_id}")
        conn.execute(
            "UPDATE users SET journey_id = NULL, updated_at = datetime('now') "
            "WHERE id = ?", (int(user_id),))
        conn.execute(
            "INSERT INTO security_audit_log (event_type, username, user_id, "
            "detail) VALUES (?, ?, ?, ?)",
            ("identity.user_unlinked", actor, int(user_id), json.dumps({
                "account": user["username"],
                "previous_journey_id": user["journey_id"]})))
        conn.commit()
    finally:
        conn.close()


def journey_for_user(user_id: int, *, db_path: str | None = None) -> str | None:
    """The (resolved) journey a login is linked to, if any."""
    _ensure(db_path)
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT journey_id FROM users WHERE id = ?",
                           (int(user_id),)).fetchone()
    finally:
        conn.close()
    if row is None or not row["journey_id"]:
        return None
    return resolve_journey_id(row["journey_id"], db_path=db_path)


def users_for_journey(journey_id: str, *,
                      db_path: str | None = None) -> list[dict]:
    """Logins linked to a journey, each with its ``user_systems`` access."""
    _ensure(db_path)
    conn = connect(db_path)
    try:
        users = [dict(r) for r in conn.execute(
            "SELECT id, username, display_name, is_active, last_login "
            "FROM users WHERE journey_id = ? ORDER BY id",
            (journey_id,)).fetchall()]
        for u in users:
            u["systems"] = [dict(r) for r in conn.execute(
                "SELECT system_key, role FROM user_systems WHERE user_id = ? "
                "ORDER BY system_key", (u["id"],)).fetchall()]
    finally:
        conn.close()
    return users


__all__ = [
    "SYSTEM_SLOTS",
    "CONCURRENT_SYSTEMS",
    "MERGED_STATUS",
    "DuplicateCandidate",
    "MergeError",
    "normalise_name",
    "normalise_nhs_number",
    "normalise_upn",
    "get",
    "resolve_journey_id",
    "find_identity_candidates",
    "find_by_identity",
    "find_by_strong_id",
    "find_by_student",
    "find_by_students",
    "registration_key",
    "publish_registered",
    "link_system",
    "get_or_create_journey",
    "record_transition",
    "record_transition_once",
    "find_duplicate_candidates",
    "mark_not_duplicate",
    "merge_journeys",
    "list_merges",
    "link_user_account",
    "unlink_user_account",
    "journey_for_user",
    "users_for_journey",
]
