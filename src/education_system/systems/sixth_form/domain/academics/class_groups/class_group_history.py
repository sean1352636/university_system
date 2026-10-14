"""Append-only membership trail for Sixth Form class groups.

``class_group_students`` records who is in a group *now*. It cannot
answer who used to be — a removal deletes the row, and deleting a group
cascades every one of its memberships away with it. That makes the live
table useless for the question people actually ask ("this student says
they were in 12M-1 last term; were they?").

This module adds ``class_group_membership_log``: one row per join,
leave, move or merge, written by the membership operations in
:mod:`class_group_membership` and never updated afterwards.

Two deliberate choices:

* **No foreign key on ``group_id``.** The whole point is to outlive the
  group. An FK with ``ON DELETE CASCADE`` would delete the history along
  with the group; an FK without one would block the delete entirely.
  Neither is what we want, so the column is a plain integer.
* **Denormalised ``group_name`` and ``course_id``.** Once the group is
  gone there is nothing left to join to, so the trail carries enough
  copied context to stay readable on its own.

Retention is not automatic. :func:`purge_before` exists so a policy can
be applied on a schedule; nothing here expires a row by itself.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Iterable

from education_system import paths
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_group_logging as cg_log,
)
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_groups as core,
)

logger = cg_log.get_logger(__name__)

DB_PATH = paths.SIXTH_FORM_CLASS_GROUPS_DB

ValidationError = core.ValidationError


# ── Vocabulary ──────────────────────────────────────────────────────

#: What a trail entry describes. Kept coarse on purpose — the detail
#: lives in ``related_group_id`` and ``reason``, not in an ever-growing
#: list of action names.
ACTIONS: tuple[str, ...] = (
    "join",          # added to the group
    "leave",         # removed from the group
    "transfer_in",   # arrived via move_student / transfer_all_members
    "transfer_out",  # departed via move_student / transfer_all_members
    "swap_in",       # arrived via swap_students
    "swap_out",      # departed via swap_students
    "clear",         # removed by clear_members
    "intake",        # added by a cohort intake run
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS class_group_membership_log (
    event_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id         INTEGER NOT NULL,
    course_id        INTEGER,
    group_name       TEXT,
    student_id       TEXT NOT NULL,
    action           TEXT NOT NULL,
    actor            TEXT,
    reason           TEXT,
    related_group_id INTEGER,
    occurred_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cgml_student
    ON class_group_membership_log(student_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_cgml_group
    ON class_group_membership_log(group_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_cgml_action
    ON class_group_membership_log(action);
"""

_DB_READY: bool = False


@dataclass
class MembershipEvent:
    event_id: int
    group_id: int
    course_id: int | None
    group_name: str | None
    student_id: str
    action: str
    actor: str | None
    reason: str | None
    related_group_id: int | None
    occurred_at: str

    @property
    def is_arrival(self) -> bool:
        return self.action in ("join", "transfer_in", "swap_in", "intake")

    @property
    def is_departure(self) -> bool:
        return self.action in ("leave", "transfer_out", "swap_out", "clear")


def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    core.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Class-group membership log ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row) -> MembershipEvent:
    return MembershipEvent(
        event_id=r["event_id"],
        group_id=r["group_id"],
        course_id=r["course_id"],
        group_name=r["group_name"],
        student_id=r["student_id"],
        action=r["action"],
        actor=r["actor"],
        reason=r["reason"],
        related_group_id=r["related_group_id"],
        occurred_at=r["occurred_at"],
    )


# ── Writing ─────────────────────────────────────────────────────────

def _context_for(conn: sqlite3.Connection,
                 group_id: int) -> tuple[int | None, str | None]:
    """Look up the course/name to copy into the trail entry.

    Best-effort: a group that has already been deleted still deserves a
    trail row, just without the extra context.
    """
    try:
        row = conn.execute(
            "SELECT course_id, group_name FROM class_groups "
            "WHERE group_id = ?", (group_id,),
        ).fetchone()
    except sqlite3.DatabaseError:
        return (None, None)
    if row is None:
        return (None, None)
    return (row["course_id"], row["group_name"])


def record(group_id: int,
           student_id: str,
           action: str,
           *,
           actor: str | None = None,
           reason: str | None = None,
           related_group_id: int | None = None,
           conn: sqlite3.Connection | None = None) -> None:
    """Append one event to the trail.

    Pass ``conn`` to enlist in a caller's open transaction — the
    membership operations do this so the trail entry commits or rolls
    back with the change it describes.

    Never raises. A failure to write history is logged loudly but must
    not undo a membership change that already succeeded, and must not
    abort a bulk run partway through.
    """
    if action not in ACTIONS:
        # Not fatal — an unknown action is still better recorded than
        # dropped — but it means somebody added an operation without
        # extending ACTIONS, and the GUI filters will not know about it.
        logger.warning(
            "record: unknown membership action %r (recording anyway)",
            action,
        )
    own_conn = conn is None
    try:
        init_db()
        c = conn or _connect()
        try:
            course_id, group_name = _context_for(c, group_id)
            c.execute(
                """INSERT INTO class_group_membership_log
                       (group_id, course_id, group_name, student_id,
                        action, actor, reason, related_group_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (group_id, course_id, group_name, student_id, action,
                 actor, reason, related_group_id),
            )
            if own_conn:
                c.commit()
        finally:
            if own_conn:
                c.close()
    except Exception:
        cg_log.rejected(
            logger,
            "Failed to write membership trail entry (%s %s -> group #%s)",
            action, student_id, group_id,
            student_id=student_id, group_id=group_id, actor=actor,
        )
        logger.debug("record traceback", exc_info=True)


def record_many(group_id: int,
                student_ids: Iterable[str],
                action: str,
                *,
                actor: str | None = None,
                reason: str | None = None,
                related_group_id: int | None = None,
                conn: sqlite3.Connection | None = None) -> int:
    """Append one event per student. Returns the number written.

    One INSERT per row would be N round trips inside a bulk operation
    that is already holding a write lock, so this batches them.
    """
    ids = [str(s) for s in student_ids if s]
    if not ids:
        return 0
    own_conn = conn is None
    try:
        init_db()
        c = conn or _connect()
        try:
            course_id, group_name = _context_for(c, group_id)
            c.executemany(
                """INSERT INTO class_group_membership_log
                       (group_id, course_id, group_name, student_id,
                        action, actor, reason, related_group_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [(group_id, course_id, group_name, sid, action,
                  actor, reason, related_group_id) for sid in ids],
            )
            if own_conn:
                c.commit()
        finally:
            if own_conn:
                c.close()
        return len(ids)
    except Exception:
        cg_log.rejected(
            logger,
            "Failed to write %d membership trail entries (%s, group #%s)",
            len(ids), action, group_id,
            group_id=group_id, actor=actor,
        )
        logger.debug("record_many traceback", exc_info=True)
        return 0


# ── Reading ─────────────────────────────────────────────────────────

def membership_history(student_id: str,
                       *,
                       course_id: int | None = None,
                       action: str | None = None,
                       since: str | None = None,
                       until: str | None = None,
                       limit: int = 200) -> list[MembershipEvent]:
    """Feature 9 — every group this student has moved through.

    Most recent first. Includes groups that no longer exist, which is
    the reason this table is separate from ``class_group_students``.
    """
    init_db()
    sid = core._require(student_id, "Student ID")
    clauses = ["student_id = ?"]
    args: list[Any] = [sid]
    if course_id is not None:
        clauses.append("course_id = ?")
        args.append(int(course_id))
    if action:
        clauses.append("action = ?")
        args.append(str(action))
    if since:
        clauses.append("occurred_at >= ?")
        args.append(since)
    if until:
        clauses.append("occurred_at <= ?")
        args.append(until)
    args.append(max(1, int(limit)))
    sql = ("SELECT * FROM class_group_membership_log "
           f"WHERE {' AND '.join(clauses)} "
           "ORDER BY occurred_at DESC, event_id DESC LIMIT ?")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def group_history(group_id: int,
                  *,
                  action: str | None = None,
                  since: str | None = None,
                  limit: int = 200) -> list[MembershipEvent]:
    """Everything that has happened to one group's roster."""
    init_db()
    clauses = ["group_id = ?"]
    args: list[Any] = [int(group_id)]
    if action:
        clauses.append("action = ?")
        args.append(str(action))
    if since:
        clauses.append("occurred_at >= ?")
        args.append(since)
    args.append(max(1, int(limit)))
    sql = ("SELECT * FROM class_group_membership_log "
           f"WHERE {' AND '.join(clauses)} "
           "ORDER BY occurred_at DESC, event_id DESC LIMIT ?")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def was_ever_member(group_id: int, student_id: str) -> bool:
    """Whether this student has ever been in this group, past or present."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM class_group_membership_log "
            "WHERE group_id = ? AND student_id = ? LIMIT 1",
            (int(group_id), str(student_id)),
        ).fetchone()
    return row is not None


def churn_summary(group_id: int,
                  *, since: str | None = None) -> dict[str, int]:
    """Arrivals/departures per action for one group.

    A group with a high churn count and a stable headcount is a group
    somebody keeps reshuffling — worth surfacing in the directory view.
    """
    init_db()
    clauses = ["group_id = ?"]
    args: list[Any] = [int(group_id)]
    if since:
        clauses.append("occurred_at >= ?")
        args.append(since)
    sql = ("SELECT action, COUNT(*) AS n FROM class_group_membership_log "
           f"WHERE {' AND '.join(clauses)} GROUP BY action")
    with _connect() as conn:
        counts = {r["action"]: int(r["n"])
                  for r in conn.execute(sql, args).fetchall()}
    counts["arrivals"] = sum(
        n for a, n in counts.items()
        if a in ("join", "transfer_in", "swap_in", "intake"))
    counts["departures"] = sum(
        n for a, n in counts.items()
        if a in ("leave", "transfer_out", "swap_out", "clear"))
    return counts


def purge_before(ts: str) -> int:
    """Delete trail entries older than ``ts`` (YYYY-MM-DD or timestamp).

    Retention housekeeping only. The table is otherwise append-only and
    nothing else in this package removes a row.
    """
    init_db()
    if not ts or not str(ts).strip():
        raise ValidationError("A cut-off timestamp is required")
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM class_group_membership_log WHERE occurred_at < ?",
            (str(ts).strip(),),
        )
        conn.commit()
        removed = cur.rowcount or 0
    cg_log.group_event(
        logger, "Purged %d membership trail entries older than %s",
        removed, ts,
    )
    return removed
