"""Audit trail, permissions and visibility for the Sixth Form Calendar.

Sibling to :mod:`calendar`. Three jobs:

**The amendment trail.** Anyone who can open the calendar window can
move a parents' evening, and until now nothing recorded that they did.
:func:`log_changes` diffs an event before and after a write and stores
one entry per field that moved, so the trail reads as facts ("location:
Hall → Gym, by jsmith") rather than row dumps. The ``audited_*``
wrappers bundle a core write with its trail entry; interfaces should
call those rather than the core functions directly.

**Permissions.** Domain code cannot know who is logged in — the
interface does, and passes the launcher's ``system_role`` down. The
policy table here says what each role may do to the calendar, and
:func:`require` turns "may not" into a :class:`ValidationError` the
views already know how to show. It is deliberately a table, not code:
the argument about whether teachers may delete events should be a
one-line change.

**Visibility.** ``visibility`` on an event says who may *see* it
(:data:`calendar.VISIBILITIES`); this module is where that rule is
actually applied. :func:`visible_events` is the read every
student/parent-facing surface should go through — the portal, the
API's public feed, the student view. Staff surfaces can keep using
:func:`calendar.list_events` directly.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as core,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_CALENDAR_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

ACTIONS: tuple[str, ...] = (
    "create", "edit", "status", "archive", "restore", "purge",
)

# Event fields worth a trail entry when they move. `updated_at` and
# `updated_by` change on every write and would drown the signal.
TRACKED_FIELDS: tuple[str, ...] = (
    "title", "event_type", "description", "start_date", "end_date",
    "start_time", "end_time", "all_day", "location", "organiser",
    "audience", "status", "capacity", "rsvp_required", "cost",
    "notes", "department", "visibility",
)

# The launcher's system_role vocabulary, plus the two portal-side
# viewers that never get write access.
ROLES: tuple[str, ...] = (
    "admin", "staff", "teacher", "student", "parent",
)

# What each role may do. `manage` covers the vocabulary screens —
# departments, colours, series — where a stray edit changes hundreds
# of events at once.
_POLICY: dict[str, frozenset[str]] = {
    "admin":   frozenset({"view", "create", "edit", "status",
                          "archive", "restore", "purge", "manage"}),
    "staff":   frozenset({"view", "create", "edit", "status",
                          "archive", "restore"}),
    "teacher": frozenset({"view", "create", "edit", "status"}),
    "student": frozenset({"view"}),
    "parent":  frozenset({"view"}),
}

# Which visibilities each kind of viewer may see. Staff see the lot;
# students see the college's day-to-day calendar; parents and the
# outside world see only what was deliberately published.
_STAFF_ROLES: frozenset[str] = frozenset({"admin", "staff", "teacher"})
_VIEWER_VISIBILITIES: dict[str, tuple[str, ...]] = {
    "admin":   core.VISIBILITIES,
    "staff":   core.VISIBILITIES,
    "teacher": core.VISIBILITIES,
    "student": (core.INTERNAL, core.PUBLIC),
    "parent":  (core.PUBLIC,),
    "public":  (core.PUBLIC,),
}


_SCHEMA = """
CREATE TABLE IF NOT EXISTS calendar_amendments (
    amendment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id     INTEGER NOT NULL,
    action       TEXT NOT NULL,
    field        TEXT,
    old_value    TEXT,
    new_value    TEXT,
    reason       TEXT,
    amended_by   TEXT,
    amended_at   TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cal_amend_event
    ON calendar_amendments(event_id);
CREATE INDEX IF NOT EXISTS idx_cal_amend_when
    ON calendar_amendments(amended_at);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Amendment:
    """One recorded change to one calendar event."""

    amendment_id: int
    event_id: int
    action: str
    field: str | None
    old_value: str | None
    new_value: str | None
    reason: str | None
    amended_by: str | None
    amended_at: str | None

    @property
    def summary(self) -> str:
        who = self.amended_by or "unknown"
        if self.field:
            return (f"{self.field}: {self.old_value or '—'} → "
                    f"{self.new_value or '—'} (by {who})")
        return f"{self.action} (by {who})"


# ── DB plumbing ─────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    core.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Calendar governance schema ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row) -> Amendment:
    return Amendment(
        amendment_id=r["amendment_id"], event_id=r["event_id"],
        action=r["action"], field=r["field"],
        old_value=r["old_value"], new_value=r["new_value"],
        reason=r["reason"], amended_by=r["amended_by"],
        amended_at=r["amended_at"])


# ── Permissions ─────────────────────────────────────────────────────

def can(role: str | None, action: str) -> bool:
    """May this role do this? Unknown roles may do nothing — a typo'd
    role failing closed is a nuisance; failing open is an incident."""
    return action in _POLICY.get((role or "").strip().lower(),
                                 frozenset())


def require(role: str | None, action: str) -> None:
    if not can(role, action):
        raise ValidationError(
            f"Role {role or 'unknown'!r} may not {action} "
            "calendar events")


# ── The trail ───────────────────────────────────────────────────────

def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def record_action(event_id: int, action: str, *,
                  actor: str | None = None,
                  reason: str | None = None,
                  field: str | None = None,
                  old_value: Any = None,
                  new_value: Any = None) -> None:
    """Append one entry. Never raises past logging — a full audit
    table must not be the reason an event could not be saved."""
    if action not in ACTIONS:
        raise ValidationError(
            f"Action must be one of: {', '.join(ACTIONS)}")
    init_db()
    try:
        with _connect() as conn:
            conn.execute(
                """INSERT INTO calendar_amendments
                       (event_id, action, field, old_value, new_value,
                        reason, amended_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (event_id, action, field, _stringify(old_value),
                 _stringify(new_value), (reason or "").strip() or None,
                 (actor or "").strip() or None))
            conn.commit()
    except sqlite3.Error:                   # pragma: no cover - defensive
        logger.exception("Could not write calendar amendment for "
                         "event #%d", event_id)


def log_changes(before: core.Event, after: core.Event, *,
                actor: str | None = None,
                reason: str | None = None) -> int:
    """Diff two versions of an event; one entry per field that moved."""
    written = 0
    for field_name in TRACKED_FIELDS:
        old = getattr(before, field_name, None)
        new = getattr(after, field_name, None)
        if old == new:
            continue
        action = "status" if field_name == "status" else "edit"
        record_action(after.event_id, action, actor=actor,
                      reason=reason, field=field_name,
                      old_value=old, new_value=new)
        written += 1
    return written


def trail(event_id: int, *, limit: int = 200) -> list[Amendment]:
    """Everything that ever happened to one event, newest first."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM calendar_amendments WHERE event_id = ? "
            "ORDER BY amended_at DESC, amendment_id DESC LIMIT ?",
            (event_id, max(1, int(limit)))).fetchall()
    return [_row(r) for r in rows]


def recent_activity(*, limit: int = 100,
                    actor: str | None = None) -> list[Amendment]:
    """The latest changes across the whole calendar — the governor's
    "who has been fiddling with this?" view."""
    init_db()
    clauses, args = [], []
    if actor:
        clauses.append("amended_by = ?")
        args.append(actor.strip())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM calendar_amendments {where} "
            "ORDER BY amended_at DESC, amendment_id DESC LIMIT ?",
            args).fetchall()
    return [_row(r) for r in rows]


# ── Audited writes ──────────────────────────────────────────────────

def audited_create(payload: dict[str, Any], *, actor: str | None = None,
                   role: str | None = None) -> core.Event:
    if role is not None:
        require(role, "create")
    event = core.create_event(payload, actor=actor)
    record_action(event.event_id, "create", actor=actor,
                  new_value=event.title)
    return event


def audited_update(event_id: int, payload: dict[str, Any], *,
                   actor: str | None = None,
                   role: str | None = None,
                   reason: str | None = None) -> core.Event:
    if role is not None:
        require(role, "edit")
    before = core.get_event(event_id)
    if before is None:
        raise ValidationError(f"No event #{event_id}")
    after = core.update_event(event_id, payload, actor=actor)
    log_changes(before, after, actor=actor, reason=reason)
    return after


def audited_set_status(event_id: int, status: str, *,
                       actor: str | None = None,
                       role: str | None = None,
                       reason: str | None = None) -> core.Event:
    if role is not None:
        require(role, "status")
    before = core.get_event(event_id)
    if before is None:
        raise ValidationError(f"No event #{event_id}")
    after = core.set_status(event_id, status, actor=actor)
    if before.status != after.status:
        record_action(event_id, "status", actor=actor, reason=reason,
                      field="status", old_value=before.status,
                      new_value=after.status)
    return after


def audited_archive(event_id: int, *, actor: str | None = None,
                    role: str | None = None,
                    reason: str | None = None) -> bool:
    if role is not None:
        require(role, "archive")
    done = core.delete_event(event_id, actor=actor)
    if done:
        record_action(event_id, "archive", actor=actor, reason=reason)
    return done


def audited_restore(event_id: int, *, actor: str | None = None,
                    role: str | None = None) -> bool:
    if role is not None:
        require(role, "restore")
    done = core.restore_event(event_id, actor=actor)
    if done:
        record_action(event_id, "restore", actor=actor)
    return done


def audited_purge(event_id: int, *, actor: str | None = None,
                  role: str | None = None,
                  reason: str | None = None) -> bool:
    """The one true delete. The trail entry is written first — after
    the purge there is no row left to hang it on, but the trail keeps
    the event_id, which is the point."""
    if role is not None:
        require(role, "purge")
    existing = core.get_event(event_id)
    if existing is None:
        return False
    record_action(event_id, "purge", actor=actor, reason=reason,
                  old_value=existing.title)
    return core.purge_event(event_id)


# ── Archive views ───────────────────────────────────────────────────

def list_archived(**filters: Any) -> list[core.Event]:
    """Just the archived events — the bin, ready for restore/purge."""
    rows = core.list_events(include_deleted=True, **filters)
    return [e for e in rows if e.is_deleted]


# ── Visibility ──────────────────────────────────────────────────────

def allowed_visibilities(viewer: str | None) -> tuple[str, ...]:
    """Which visibility levels this kind of viewer may see. Unknown
    viewers are treated as the public."""
    return _VIEWER_VISIBILITIES.get(
        (viewer or "public").strip().lower(),
        _VIEWER_VISIBILITIES["public"])


def visible_events(viewer: str | None, **filters: Any) -> list[core.Event]:
    """:func:`calendar.list_events`, filtered to what this viewer may
    see. The read behind every non-staff surface."""
    allowed = allowed_visibilities(viewer)
    rows = core.list_events(**filters)
    return [e for e in rows if e.visibility in allowed]


def visible_on(viewer: str | None, date_iso: str) -> list[core.Event]:
    allowed = allowed_visibilities(viewer)
    return [e for e in core.events_on(date_iso)
            if e.visibility in allowed]
