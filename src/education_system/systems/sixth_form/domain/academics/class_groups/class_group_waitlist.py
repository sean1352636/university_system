"""Waiting lists for full Sixth Form class groups.

``add_member`` refuses once a group is at capacity, which leaves the
office with nowhere to put the request except a note in the group's
``notes`` field. This module gives that queue a table, so "who is next
for 12M-1?" has an answer that survives a staff change.

**Position is derived, never stored.** A stored position column has to
be renumbered on every insertion, removal and promotion, and one missed
renumber leaves two students sharing a place with no way to tell which
came first. Here the order is ``(priority DESC, added_at, entry_id)``
and the position is computed on read — it cannot drift, and a promotion
is a status change rather than a shuffle of everybody below it.

``priority`` exists because queues in a school are not purely FIFO: a
timetable clash or an EHCP-driven placement legitimately jumps the
queue. It defaults to 0, and anything non-zero is logged with its reason
so the jump is visible later.

Entries are never deleted by the normal flow — they move to
``promoted`` or ``withdrawn`` and stay. The live queue is the rows still
marked ``waiting``.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_group_capacity as capacity,
)
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_group_logging as cg_log,
)
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_group_membership as membership,
)
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_groups as core,
)

logger = cg_log.get_logger(__name__)

DB_PATH = paths.SIXTH_FORM_CLASS_GROUPS_DB

ValidationError = core.ValidationError
BulkResult = membership.BulkResult

#: Live queue vs. closed entries. Closed rows are kept for the trail.
STATUSES: tuple[str, ...] = ("waiting", "promoted", "withdrawn")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS class_group_waitlist (
    entry_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id    INTEGER NOT NULL,
    student_id  TEXT    NOT NULL,
    priority    INTEGER NOT NULL DEFAULT 0,
    status      TEXT    NOT NULL DEFAULT 'waiting',
    reason      TEXT,
    added_by    TEXT,
    added_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    closed_at   TEXT,
    closed_by   TEXT,
    FOREIGN KEY (group_id)   REFERENCES class_groups(group_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)   ON DELETE CASCADE
);

-- At most one live entry per student per group. A partial index is the
-- only way to say that while still allowing repeat entries after a
-- withdrawal.
CREATE UNIQUE INDEX IF NOT EXISTS idx_cgw_live_unique
    ON class_group_waitlist(group_id, student_id)
    WHERE status = 'waiting';
CREATE INDEX IF NOT EXISTS idx_cgw_group
    ON class_group_waitlist(group_id, status);
CREATE INDEX IF NOT EXISTS idx_cgw_student
    ON class_group_waitlist(student_id, status);
"""

#: The queue order, in one place so reads and promotions cannot disagree.
_ORDER = "priority DESC, added_at, entry_id"

_DB_READY: bool = False


@dataclass
class WaitlistEntry:
    entry_id: int
    group_id: int
    student_id: str
    priority: int
    status: str
    reason: str | None
    added_by: str | None
    added_at: str
    closed_at: str | None
    closed_by: str | None
    #: 1-based place in the live queue; None for a closed entry.
    position: int | None = None

    @property
    def is_waiting(self) -> bool:
        return self.status == "waiting"


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    core.init_db()
    with membership._txn() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Class-group waitlist schema ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row, position: int | None = None) -> WaitlistEntry:
    return WaitlistEntry(
        entry_id=r["entry_id"], group_id=r["group_id"],
        student_id=r["student_id"], priority=int(r["priority"]),
        status=r["status"], reason=r["reason"], added_by=r["added_by"],
        added_at=r["added_at"], closed_at=r["closed_at"],
        closed_by=r["closed_by"], position=position,
    )


def _live_rows(conn: sqlite3.Connection, group_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM class_group_waitlist "
        f"WHERE group_id = ? AND status = 'waiting' ORDER BY {_ORDER}",
        (group_id,),
    ).fetchall()


# ── 16. Join the queue ──────────────────────────────────────────────

def add_to_waitlist(group_id: int,
                    student_id: str,
                    *,
                    priority: int = 0,
                    reason: str | None = None,
                    actor: str | None = None,
                    allow_when_space: bool = False) -> int:
    """Put a student on a group's waiting list. Returns their position.

    Refuses when the group still has free places — the answer there is
    ``add_member``, and a queue in front of an empty seat is a bug
    somebody will spend an afternoon on. Pass ``allow_when_space=True``
    to queue anyway (holding a place for an expected transfer).

    Position is 1-based and reflects ``priority`` first, then join
    order.
    """
    init_db()
    sid = core._require(student_id, "Student ID")
    gc = capacity.capacity_of(group_id)
    gid = gc.group_id

    try:
        prio = int(priority)
    except (TypeError, ValueError):
        raise ValidationError("Priority must be a whole number") from None

    if not gc.is_full and not allow_when_space:
        cg_log.rejected(
            logger,
            "Waitlist refused for %s: class group #%d (%s) has %s free place(s)",
            sid, gid, gc.group.group_name, gc.remaining,
            student_id=sid, group_id=gid, actor=actor,
        )
        raise ValidationError(
            f"'{gc.group.group_name}' has {gc.remaining} free place(s); "
            f"add {sid} directly rather than waitlisting them "
            f"(or pass allow_when_space=True)")

    with membership._txn() as conn:
        if not membership._existing_students(conn, [sid]):
            cg_log.rejected(logger, "Waitlist: unknown student %s", sid,
                            student_id=sid, group_id=gid, actor=actor)
            raise ValidationError(f"No student with id {sid}")
        if sid in membership._members_of(conn, gid):
            raise ValidationError(
                f"{sid} is already a member of '{gc.group.group_name}'")
        try:
            conn.execute(
                """INSERT INTO class_group_waitlist
                       (group_id, student_id, priority, reason, added_by)
                   VALUES (?, ?, ?, ?, ?)""",
                (gid, sid, prio, reason, actor),
            )
        except sqlite3.IntegrityError as e:
            if "idx_cgw_live_unique" in str(e) or "UNIQUE" in str(e):
                raise ValidationError(
                    f"{sid} is already on the waiting list for "
                    f"'{gc.group.group_name}'") from e
            raise ValidationError(f"Database error: {e}") from e
        order = [r["student_id"] for r in _live_rows(conn, gid)]

    position = order.index(sid) + 1
    cg_log.student_event(
        logger,
        "Waitlisted %s for class group #%d (%s) at position %d of %d"
        + (" (priority %d)" % prio if prio else ""),
        sid, gid, gc.group.group_name, position, len(order),
        student_id=sid, group_id=gid, actor=actor,
    )
    return position


# ── 17. Promote off the queue ───────────────────────────────────────

def promote_from_waitlist(group_id: int,
                          count: int = 1,
                          *,
                          actor: str | None = None,
                          reason: str | None = None) -> BulkResult:
    """Move the front of the queue into the group.

    Takes the smaller of ``count`` and the group's free places, so this
    is safe to call speculatively after a removal — it promotes nobody
    when the group is still full rather than breaching the cap.

    The actual insert goes through
    :func:`class_group_membership.add_members_bulk`, so promotions land
    in the membership trail like any other join. An entry whose student
    has since become invalid (left the college, already added by hand)
    is closed as ``withdrawn`` rather than left to block the queue
    forever.
    """
    init_db()
    gc = capacity.capacity_of(group_id)
    gid = gc.group_id
    result = BulkResult(group_id=gid, action="join")

    try:
        want = int(count)
    except (TypeError, ValueError):
        raise ValidationError("Count must be a whole number") from None
    if want < 1:
        raise ValidationError("Count must be at least 1")

    room = gc.remaining  # None == uncapped
    take = want if room is None else min(want, room)
    if take < 1:
        cg_log.group_event(
            logger,
            "No promotion from class group #%d (%s) waitlist: %d/%s full",
            gid, gc.group.group_name, gc.members, gc.cap,
            group_id=gid, actor=actor, level=10,
        )
        return result

    with membership._txn() as conn:
        rows = _live_rows(conn, gid)
    if not rows:
        return result

    candidates = rows[:take]
    ids = [r["student_id"] for r in candidates]

    result = membership.add_members_bulk(
        gid, ids, actor=actor,
        reason=reason or f"promoted from the waitlist for group #{gid}",
    )

    promoted = set(result.succeeded)
    # A skip means the entry can never succeed as it stands, so close it
    # rather than leave a dead row at the head of the queue.
    skipped_reasons = {s.student_id: s.reason for s in result.skipped}
    with membership._txn() as conn:
        for r in candidates:
            sid = r["student_id"]
            if sid in promoted:
                conn.execute(
                    "UPDATE class_group_waitlist SET status = 'promoted', "
                    "closed_at = datetime('now'), closed_by = ? "
                    "WHERE entry_id = ?", (actor, r["entry_id"]),
                )
            elif sid in skipped_reasons:
                conn.execute(
                    "UPDATE class_group_waitlist SET status = 'withdrawn', "
                    "closed_at = datetime('now'), closed_by = ?, "
                    "reason = COALESCE(reason || ' | ', '') || ? "
                    "WHERE entry_id = ?",
                    (actor, f"auto-closed: {skipped_reasons[sid]}",
                     r["entry_id"]),
                )
                cg_log.rejected(
                    logger,
                    "Closed waitlist entry for %s on class group #%d: %s",
                    sid, gid, skipped_reasons[sid],
                    student_id=sid, group_id=gid, actor=actor,
                )

    cg_log.group_event(
        logger, "Promoted %d student(s) from the class group #%d (%s) waitlist",
        result.count, gid, gc.group.group_name,
        group_id=gid, actor=actor,
    )
    return result


# ── Supporting queue operations ─────────────────────────────────────

def list_waitlist(group_id: int,
                  *,
                  status: str = "waiting") -> list[WaitlistEntry]:
    """The queue for one group, in position order.

    ``status='waiting'`` (the default) is the live queue with positions
    filled in; any other status returns closed entries, whose
    ``position`` is None because they no longer hold one.
    """
    init_db()
    if status not in STATUSES:
        raise ValidationError(
            f"Unknown status {status!r}; expected one of {', '.join(STATUSES)}")
    gid = int(group_id)
    with membership._txn() as conn:
        rows = conn.execute(
            "SELECT * FROM class_group_waitlist "
            f"WHERE group_id = ? AND status = ? ORDER BY {_ORDER}",
            (gid, status),
        ).fetchall()
    if status != "waiting":
        return [_row(r) for r in rows]
    return [_row(r, position=i) for i, r in enumerate(rows, start=1)]


def waitlist_position(group_id: int, student_id: str) -> int | None:
    """This student's 1-based place in the queue, or None if not queued."""
    for entry in list_waitlist(group_id):
        if entry.student_id == student_id:
            return entry.position
    return None


def remove_from_waitlist(group_id: int,
                         student_id: str,
                         *,
                         actor: str | None = None,
                         reason: str | None = None) -> bool:
    """Withdraw a live waitlist entry. Returns False if there wasn't one.

    Closes the row rather than deleting it — everybody below moves up by
    one automatically, because positions are derived.
    """
    init_db()
    gid = int(group_id)
    sid = str(student_id or "").strip()
    if not sid:
        return False
    with membership._txn() as conn:
        cur = conn.execute(
            "UPDATE class_group_waitlist SET status = 'withdrawn', "
            "closed_at = datetime('now'), closed_by = ?, "
            "reason = COALESCE(reason || ' | ', '') || ? "
            "WHERE group_id = ? AND student_id = ? AND status = 'waiting'",
            (actor, reason or "withdrawn", gid, sid),
        )
        changed = cur.rowcount or 0
    if changed:
        cg_log.student_event(
            logger, "Withdrew %s from the class group #%d waitlist", sid, gid,
            student_id=sid, group_id=gid, actor=actor,
        )
        return True
    return False


def waitlist_for_student(student_id: str) -> list[WaitlistEntry]:
    """Every live queue this student is sitting in, across all groups."""
    init_db()
    sid = core._require(student_id, "Student ID")
    with membership._txn() as conn:
        rows = conn.execute(
            "SELECT * FROM class_group_waitlist "
            f"WHERE student_id = ? AND status = 'waiting' ORDER BY {_ORDER}",
            (sid,),
        ).fetchall()
    out: list[WaitlistEntry] = []
    for r in rows:
        out.append(_row(r, position=waitlist_position(r["group_id"], sid)))
    return out


def promote_where_possible(course_id: int,
                           *,
                           actor: str | None = None) -> dict[int, BulkResult]:
    """Run :func:`promote_from_waitlist` across every group on a course.

    The housekeeping pass to run after a round of removals: each group
    fills whatever places it now has, and groups with none are skipped
    without a write. Returns only the groups where somebody moved.
    """
    init_db()
    out: dict[int, BulkResult] = {}
    for gc in capacity.capacity_report(course_id=course_id):
        room = gc.remaining
        if room is not None and room < 1:
            continue
        result = promote_from_waitlist(
            gc.group_id, room if room is not None else 50,
            actor=actor, reason="bulk waitlist sweep")
        if result.count:
            out[gc.group_id] = result
    return out
