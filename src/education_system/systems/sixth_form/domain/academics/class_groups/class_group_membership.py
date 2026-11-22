"""Bulk and cross-group roster operations for Sixth Form class groups.

:mod:`class_groups` handles one student at a time: ``add_member``,
``remove_member``. That is the right shape for the profile screen and
the wrong shape for everything else a head of department actually does
— splitting a set, moving a learner between sets after a re-assessment,
emptying a group before it is retired, pasting in thirty ids from a
spreadsheet.

Doing those by looping over ``add_member`` is wrong twice over. It is a
fresh connection and a fresh set of validation queries per student, and
it is not atomic: a loop that fails on student twenty leaves nineteen
committed and no record of intent. Everything here runs in one
transaction over one connection.

**Partial success is the default.** A bulk add of thirty ids where two
are typos should enrol twenty-eight and tell you about the two, not
refuse the lot. Callers who need all-or-nothing pass ``atomic=True``.
Either way the skipped rows come back in the :class:`BulkResult` *and*
go to the durable log, because a return value the GUI forgets to render
is not a record.

The cross-group operations (:func:`move_student`, :func:`swap_students`,
:func:`transfer_all_members`) are always atomic regardless — a move that
half-happens loses a student.

Every change here is mirrored into the append-only trail in
:mod:`class_group_history`, inside the same transaction.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator, Sequence

from education_system import paths
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_group_history as history,
)
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_group_logging as cg_log,
)
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_groups as core,
)

logger = cg_log.get_logger(__name__)

DB_PATH = paths.SIXTH_FORM_CLASS_GROUPS_DB

ValidationError = core.ValidationError
ClassGroup = core.ClassGroup
ClassGroupMember = core.ClassGroupMember

#: Who may change class lists: teaching staff (the Class Groups menu),
#: plus whoever manages students or enrolments (intake from a course).
WRITE_CAPABILITIES = ("teaching", "students.manage", "admissions")


def _require_writer(action: str) -> None:
    """Roster writes need one of :data:`WRITE_CAPABILITIES`; reads are
    open. Nobody signed in and no ``_guard.system_actor`` is refused."""
    from education_system.systems.sixth_form.domain.admissions import _guard
    _guard.require_any(WRITE_CAPABILITIES, action)


#: Guard against a paste of the entire student body into a bulk call.
#: Large enough for any real class list, small enough that a mistake
#: fails fast instead of locking the DB for a minute.
MAX_BULK = 500


# ── Result types ────────────────────────────────────────────────────

@dataclass
class Skip:
    """One student a bulk operation declined to act on, and why."""
    student_id: str
    reason: str


@dataclass
class BulkResult:
    """Outcome of a bulk membership operation.

    ``succeeded`` and ``skipped`` together account for every id the
    caller passed, minus duplicates within the input itself (which are
    collapsed before anything is attempted).
    """
    group_id: int
    action: str
    succeeded: list[str] = field(default_factory=list)
    skipped: list[Skip] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.succeeded)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)

    @property
    def ok(self) -> bool:
        """True when nothing was skipped."""
        return not self.skipped

    def reasons(self) -> dict[str, list[str]]:
        """Skipped ids grouped by reason — the shape a summary dialog wants."""
        out: dict[str, list[str]] = {}
        for s in self.skipped:
            out.setdefault(s.reason, []).append(s.student_id)
        return out

    def __str__(self) -> str:
        if self.ok:
            return f"{self.action}: {self.count} student(s)"
        return (f"{self.action}: {self.count} student(s), "
                f"{self.skipped_count} skipped")


@dataclass
class MemberDetail:
    """A group member with the student fields a register needs.

    Deliberately not a ``Student`` — this is the join of a membership
    and a learner, and ``joined_at`` belongs to the membership.
    """
    group_id: int
    student_id: str
    first_name: str
    last_name: str
    full_name: str
    email: str
    status: str
    phone: str | None
    joined_at: str

    @property
    def is_active(self) -> bool:
        return (self.status or "").strip().lower() == "active"


# ── Transaction plumbing ────────────────────────────────────────────

@contextmanager
def _txn() -> Iterator[sqlite3.Connection]:
    """One connection, one transaction, always closed.

    ``class_groups`` uses ``with sqlite3.connect(...) as conn``, which
    commits on success but does *not* close the connection. That is
    tolerable for a single statement and not for the multi-statement
    operations here, which would otherwise leave a write lock dangling
    until the GC got round to it.
    """
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except sqlite3.DatabaseError:  # pragma: no cover
            pass
        raise
    finally:
        conn.close()


def _init() -> None:
    """Bring both the core schema and the trail table up."""
    core.init_db()
    history.init_db()


def _clean_ids(student_ids: Iterable[str]) -> list[str]:
    """Normalise, drop blanks, de-duplicate, preserve caller order."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in student_ids or ():
        sid = str(raw or "").strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        out.append(sid)
    if len(out) > MAX_BULK:
        raise ValidationError(
            f"Too many students in one operation "
            f"({len(out)}; the limit is {MAX_BULK})")
    return out


def _require_group(group_id: int, label: str = "class group") -> ClassGroup:
    try:
        gid = int(group_id)
    except (TypeError, ValueError):
        raise ValidationError(
            f"{label.capitalize()} ID must be a whole number") from None
    group = core.get_group(gid)
    if group is None:
        cg_log.rejected(logger, "Unknown %s #%s", label, gid, group_id=gid)
        raise ValidationError(f"No {label} with id {gid}")
    return group


def _existing_students(conn: sqlite3.Connection,
                       ids: Sequence[str]) -> set[str]:
    """Which of ``ids`` are real students — one query, not N."""
    if not ids:
        return set()
    marks = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT student_id FROM students WHERE student_id IN ({marks})",
        list(ids),
    ).fetchall()
    return {r["student_id"] for r in rows}


def _members_of(conn: sqlite3.Connection, group_id: int) -> set[str]:
    rows = conn.execute(
        "SELECT student_id FROM class_group_students WHERE group_id = ?",
        (group_id,),
    ).fetchall()
    return {r["student_id"] for r in rows}


def _headroom(conn: sqlite3.Connection, group: ClassGroup) -> int | None:
    """Places left in ``group``, or None when it is uncapped."""
    cap = core.effective_cap(group)
    if cap is None:
        return None
    (n,) = conn.execute(
        "SELECT COUNT(*) FROM class_group_students WHERE group_id = ?",
        (group.group_id,),
    ).fetchone()
    return max(0, cap - int(n))


# ── 1. Bulk add ─────────────────────────────────────────────────────

def add_members_bulk(group_id: int,
                     student_ids: Iterable[str],
                     *,
                     actor: str | None = None,
                     reason: str | None = None,
                     atomic: bool = False,
                     action: str = "join") -> BulkResult:
    """Add many students to one group in a single transaction.

    Skips, rather than fails on, ids that are unknown, already in the
    group, or that would breach the group's effective cap — unless
    ``atomic`` is set, in which case any skip aborts the whole run and
    raises :class:`ValidationError` with nothing written.

    Capacity is filled in the order given, so the caller controls who
    gets the last place.
    """
    _require_writer("adding learners to class groups")
    _init()
    group = _require_group(group_id)
    ids = _clean_ids(student_ids)
    result = BulkResult(group_id=group.group_id, action=action)
    if not ids:
        return result

    with cg_log.operation(logger, "add_members_bulk",
                          group_id=group.group_id, actor=actor) as op:
        with _txn() as conn:
            known = _existing_students(conn, ids)
            current = _members_of(conn, group.group_id)
            headroom = _headroom(conn, group)

            to_add: list[str] = []
            for sid in ids:
                if sid not in known:
                    result.skipped.append(Skip(sid, "no such student"))
                elif sid in current:
                    result.skipped.append(Skip(sid, "already a member"))
                elif headroom is not None and len(to_add) >= headroom:
                    result.skipped.append(Skip(sid, "group is full"))
                else:
                    to_add.append(sid)

            if atomic and result.skipped:
                raise ValidationError(
                    f"Cannot add all {len(ids)} students to "
                    f"'{group.group_name}': "
                    + "; ".join(f"{s.student_id} ({s.reason})"
                                for s in result.skipped[:5])
                    + ("; ..." if len(result.skipped) > 5 else ""))

            if to_add:
                conn.executemany(
                    "INSERT INTO class_group_students (group_id, student_id) "
                    "VALUES (?, ?)",
                    [(group.group_id, sid) for sid in to_add],
                )
                history.record_many(
                    group.group_id, to_add, action,
                    actor=actor, reason=reason, conn=conn,
                )
                result.succeeded = to_add

        op["added"] = len(result.succeeded)
        op["skipped"] = len(result.skipped)

    for sid in result.succeeded:
        cg_log.student_event(
            logger, "Added %s to class group #%d (%s)",
            sid, group.group_id, group.group_name,
            student_id=sid, group_id=group.group_id, actor=actor,
        )
    for skip in result.skipped:
        cg_log.rejected(
            logger, "Not added to class group #%d (%s): %s — %s",
            group.group_id, group.group_name, skip.student_id, skip.reason,
            student_id=skip.student_id, group_id=group.group_id, actor=actor,
        )
    return result


# ── 2. Bulk remove ──────────────────────────────────────────────────

def remove_members_bulk(group_id: int,
                        student_ids: Iterable[str],
                        *,
                        actor: str | None = None,
                        reason: str | None = None,
                        action: str = "leave") -> BulkResult:
    """Remove many students from one group in a single transaction.

    Ids that were not members are reported as skips rather than errors —
    removing somebody who is already gone is not a failure.
    """
    _require_writer("removing learners from class groups")
    _init()
    group = _require_group(group_id)
    ids = _clean_ids(student_ids)
    result = BulkResult(group_id=group.group_id, action=action)
    if not ids:
        return result

    with cg_log.operation(logger, "remove_members_bulk",
                          group_id=group.group_id, actor=actor) as op:
        with _txn() as conn:
            current = _members_of(conn, group.group_id)
            to_remove = [s for s in ids if s in current]
            result.skipped = [Skip(s, "not a member")
                              for s in ids if s not in current]
            if to_remove:
                conn.executemany(
                    "DELETE FROM class_group_students "
                    "WHERE group_id = ? AND student_id = ?",
                    [(group.group_id, sid) for sid in to_remove],
                )
                history.record_many(
                    group.group_id, to_remove, action,
                    actor=actor, reason=reason, conn=conn,
                )
                result.succeeded = to_remove
        op["removed"] = len(result.succeeded)
        op["skipped"] = len(result.skipped)

    for sid in result.succeeded:
        cg_log.student_event(
            logger, "Removed %s from class group #%d (%s)",
            sid, group.group_id, group.group_name,
            student_id=sid, group_id=group.group_id, actor=actor,
        )
    return result


# ── 3. Move one student ─────────────────────────────────────────────

def move_student(from_group_id: int,
                 to_group_id: int,
                 student_id: str,
                 *,
                 actor: str | None = None,
                 reason: str | None = None) -> ClassGroupMember:
    """Move one student between groups atomically, respecting the cap.

    Always all-or-nothing: the delete and the insert share a
    transaction, so a full destination leaves the student exactly where
    they started rather than nowhere.
    """
    _require_writer("moving learners between class groups")
    _init()
    sid = core._require(student_id, "Student ID")
    src = _require_group(from_group_id, "source class group")
    dst = _require_group(to_group_id, "destination class group")
    if src.group_id == dst.group_id:
        raise ValidationError(
            "Source and destination are the same class group")

    with cg_log.operation(logger, "move_student",
                          group_id=dst.group_id, actor=actor) as op:
        with _txn() as conn:
            if sid not in _members_of(conn, src.group_id):
                raise ValidationError(
                    f"{sid} is not a member of '{src.group_name}'")
            if sid in _members_of(conn, dst.group_id):
                raise ValidationError(
                    f"{sid} is already a member of '{dst.group_name}'")
            headroom = _headroom(conn, dst)
            if headroom is not None and headroom < 1:
                cap = core.effective_cap(dst)
                raise ValidationError(
                    f"'{dst.group_name}' is at capacity ({cap}); "
                    f"cannot move {sid} into it")

            conn.execute(
                "DELETE FROM class_group_students "
                "WHERE group_id = ? AND student_id = ?",
                (src.group_id, sid),
            )
            conn.execute(
                "INSERT INTO class_group_students (group_id, student_id) "
                "VALUES (?, ?)",
                (dst.group_id, sid),
            )
            history.record(src.group_id, sid, "transfer_out", actor=actor,
                           reason=reason, related_group_id=dst.group_id,
                           conn=conn)
            history.record(dst.group_id, sid, "transfer_in", actor=actor,
                           reason=reason, related_group_id=src.group_id,
                           conn=conn)
            row = conn.execute(
                "SELECT * FROM class_group_students "
                "WHERE group_id = ? AND student_id = ?",
                (dst.group_id, sid),
            ).fetchone()
        op["student"] = sid

    cg_log.student_event(
        logger, "Moved %s from class group #%d (%s) to #%d (%s)",
        sid, src.group_id, src.group_name, dst.group_id, dst.group_name,
        student_id=sid, group_id=dst.group_id, actor=actor,
    )
    return ClassGroupMember(group_id=row["group_id"],
                            student_id=row["student_id"],
                            joined_at=row["joined_at"])


# ── 4. Swap two students ────────────────────────────────────────────

def swap_students(group_a: int,
                  student_a: str,
                  group_b: int,
                  student_b: str,
                  *,
                  actor: str | None = None,
                  reason: str | None = None
                  ) -> tuple[ClassGroupMember, ClassGroupMember]:
    """Exchange one student in each of two groups, atomically.

    Net headcount is unchanged in both groups, so a swap is legal even
    when both are full — which is exactly why it exists rather than
    being two :func:`move_student` calls.

    Returns the two new memberships as ``(a_now_in_b, b_now_in_a)``.
    """
    _require_writer("swapping learners between class groups")
    _init()
    sid_a = core._require(student_a, "First student ID")
    sid_b = core._require(student_b, "Second student ID")
    ga = _require_group(group_a, "first class group")
    gb = _require_group(group_b, "second class group")
    if ga.group_id == gb.group_id:
        raise ValidationError("Cannot swap two students within one group")
    if sid_a == sid_b:
        raise ValidationError("Cannot swap a student with themselves")

    with cg_log.operation(logger, "swap_students",
                          group_id=ga.group_id, actor=actor) as op:
        with _txn() as conn:
            members_a = _members_of(conn, ga.group_id)
            members_b = _members_of(conn, gb.group_id)
            if sid_a not in members_a:
                raise ValidationError(
                    f"{sid_a} is not a member of '{ga.group_name}'")
            if sid_b not in members_b:
                raise ValidationError(
                    f"{sid_b} is not a member of '{gb.group_name}'")
            # Each student must be absent from their destination, or the
            # swap would silently drop one of them.
            if sid_a in members_b:
                raise ValidationError(
                    f"{sid_a} is already a member of '{gb.group_name}'")
            if sid_b in members_a:
                raise ValidationError(
                    f"{sid_b} is already a member of '{ga.group_name}'")

            conn.executemany(
                "DELETE FROM class_group_students "
                "WHERE group_id = ? AND student_id = ?",
                [(ga.group_id, sid_a), (gb.group_id, sid_b)],
            )
            conn.executemany(
                "INSERT INTO class_group_students (group_id, student_id) "
                "VALUES (?, ?)",
                [(gb.group_id, sid_a), (ga.group_id, sid_b)],
            )
            history.record(ga.group_id, sid_a, "swap_out", actor=actor,
                           reason=reason, related_group_id=gb.group_id,
                           conn=conn)
            history.record(gb.group_id, sid_a, "swap_in", actor=actor,
                           reason=reason, related_group_id=ga.group_id,
                           conn=conn)
            history.record(gb.group_id, sid_b, "swap_out", actor=actor,
                           reason=reason, related_group_id=ga.group_id,
                           conn=conn)
            history.record(ga.group_id, sid_b, "swap_in", actor=actor,
                           reason=reason, related_group_id=gb.group_id,
                           conn=conn)
            rows = conn.execute(
                "SELECT * FROM class_group_students "
                "WHERE (group_id = ? AND student_id = ?) "
                "   OR (group_id = ? AND student_id = ?)",
                (gb.group_id, sid_a, ga.group_id, sid_b),
            ).fetchall()
        op["swapped"] = f"{sid_a} <-> {sid_b}"

    by_key = {(r["group_id"], r["student_id"]): r for r in rows}
    a_row = by_key[(gb.group_id, sid_a)]
    b_row = by_key[(ga.group_id, sid_b)]

    for sid, src, dst in ((sid_a, ga, gb), (sid_b, gb, ga)):
        cg_log.student_event(
            logger, "Swapped %s out of class group #%d (%s) into #%d (%s)",
            sid, src.group_id, src.group_name, dst.group_id, dst.group_name,
            student_id=sid, group_id=dst.group_id, actor=actor,
        )
    return (
        ClassGroupMember(a_row["group_id"], a_row["student_id"],
                         a_row["joined_at"]),
        ClassGroupMember(b_row["group_id"], b_row["student_id"],
                         b_row["joined_at"]),
    )


# ── 5. Transfer a whole roster ──────────────────────────────────────

def transfer_all_members(from_group_id: int,
                         to_group_id: int,
                         *,
                         actor: str | None = None,
                         reason: str | None = None,
                         partial: bool = False) -> BulkResult:
    """Move every member of one group into another (merging two sets).

    Students already in the destination are removed from the source
    without being double-inserted, and reported as ``already there``.

    If the destination cannot hold everyone, this raises and moves
    nobody — a half-merge is worse than none, because the caller cannot
    tell from the group list which half moved. Pass ``partial=True`` to
    accept filling the destination and leaving the remainder behind.
    """
    _require_writer("moving a class list")
    _init()
    src = _require_group(from_group_id, "source class group")
    dst = _require_group(to_group_id, "destination class group")
    if src.group_id == dst.group_id:
        raise ValidationError(
            "Source and destination are the same class group")

    result = BulkResult(group_id=dst.group_id, action="transfer_in")
    with cg_log.operation(logger, "transfer_all_members",
                          group_id=dst.group_id, actor=actor) as op:
        with _txn() as conn:
            # Join order, so "first in, first placed" survives the merge.
            movers = [r["student_id"] for r in conn.execute(
                "SELECT student_id FROM class_group_students "
                "WHERE group_id = ? ORDER BY joined_at, student_id",
                (src.group_id,),
            ).fetchall()]
            if not movers:
                op["moved"] = 0
                return result

            already = _members_of(conn, dst.group_id)
            incoming = [s for s in movers if s not in already]
            duplicates = [s for s in movers if s in already]

            headroom = _headroom(conn, dst)
            if headroom is not None and len(incoming) > headroom:
                if not partial:
                    cap = core.effective_cap(dst)
                    raise ValidationError(
                        f"'{dst.group_name}' has room for {headroom} more "
                        f"student(s) (cap {cap}) but {len(incoming)} would "
                        f"move from '{src.group_name}'; nothing was moved")
                left_behind = incoming[headroom:]
                incoming = incoming[:headroom]
                result.skipped.extend(
                    Skip(s, "destination full") for s in left_behind)

            moved_out = incoming + duplicates
            conn.executemany(
                "DELETE FROM class_group_students "
                "WHERE group_id = ? AND student_id = ?",
                [(src.group_id, sid) for sid in moved_out],
            )
            if incoming:
                conn.executemany(
                    "INSERT INTO class_group_students "
                    "(group_id, student_id) VALUES (?, ?)",
                    [(dst.group_id, sid) for sid in incoming],
                )
            history.record_many(src.group_id, moved_out, "transfer_out",
                                actor=actor, reason=reason,
                                related_group_id=dst.group_id, conn=conn)
            history.record_many(dst.group_id, incoming, "transfer_in",
                                actor=actor, reason=reason,
                                related_group_id=src.group_id, conn=conn)
            result.succeeded = incoming
            result.skipped.extend(
                Skip(s, "already in destination") for s in duplicates)

        op["moved"] = len(result.succeeded)
        op["skipped"] = len(result.skipped)

    cg_log.group_event(
        logger, "Transferred %d student(s) from class group #%d (%s) "
                "to #%d (%s); %d skipped",
        len(result.succeeded), src.group_id, src.group_name,
        dst.group_id, dst.group_name, len(result.skipped),
        group_id=dst.group_id, actor=actor,
    )
    return result


# ── 6. Membership test ──────────────────────────────────────────────

def is_member(group_id: int, student_id: str) -> bool:
    """Whether this student is currently in this group.

    Cheap enough to call in a loop — a single indexed primary-key
    lookup, no group or student validation. An unknown group or student
    is simply not a member.
    """
    core.init_db()
    sid = str(student_id or "").strip()
    if not sid:
        return False
    try:
        gid = int(group_id)
    except (TypeError, ValueError):
        return False
    with _txn() as conn:
        row = conn.execute(
            "SELECT 1 FROM class_group_students "
            "WHERE group_id = ? AND student_id = ? LIMIT 1",
            (gid, sid),
        ).fetchone()
    return row is not None


# ── 7. Empty a group ────────────────────────────────────────────────

def clear_members(group_id: int,
                  *,
                  actor: str | None = None,
                  reason: str | None = None) -> int:
    """Remove every student from a group. Returns how many were removed.

    The group itself survives — this is the step before retiring or
    re-populating a set, and is the non-destructive alternative to
    ``delete_group``, which takes the group and its history context with
    it.
    """
    _require_writer("emptying class groups")
    _init()
    group = _require_group(group_id)
    with cg_log.operation(logger, "clear_members",
                          group_id=group.group_id, actor=actor) as op:
        with _txn() as conn:
            members = sorted(_members_of(conn, group.group_id))
            if not members:
                op["removed"] = 0
                return 0
            conn.execute(
                "DELETE FROM class_group_students WHERE group_id = ?",
                (group.group_id,),
            )
            history.record_many(group.group_id, members, "clear",
                                actor=actor, reason=reason, conn=conn)
        op["removed"] = len(members)

    cg_log.group_event(
        logger, "Cleared %d student(s) from class group #%d (%s)",
        len(members), group.group_id, group.group_name,
        group_id=group.group_id, actor=actor,
    )
    return len(members)


# ── 8. Roster with student detail ───────────────────────────────────

def list_member_details(group_id: int,
                        *,
                        include_inactive: bool = True,
                        order_by: str = "name") -> list[MemberDetail]:
    """The group roster as printable rows, not bare ids.

    ``core.list_members`` returns ids, which means every caller that
    wants a register does its own N-query name lookup. This is the same
    information in one join.

    ``order_by`` is one of ``name`` (surname then forename, what a
    register wants) or ``joined`` (join order, what the audit trail
    wants). Anything else raises rather than silently falling back to an
    arbitrary order.
    """
    _init()
    group = _require_group(group_id)
    orders = {
        "name": "s.last_name COLLATE NOCASE, s.first_name COLLATE NOCASE",
        "joined": "cgs.joined_at, cgs.student_id",
    }
    if order_by not in orders:
        raise ValidationError(
            f"Unknown sort order {order_by!r}; expected one of "
            + ", ".join(sorted(orders)))

    sql = f"""
        SELECT cgs.group_id, cgs.student_id, cgs.joined_at,
               s.first_name, s.middle_name, s.last_name,
               s.email, s.phone, s.status
          FROM class_group_students cgs
          JOIN students s ON s.student_id = cgs.student_id
         WHERE cgs.group_id = ?
         ORDER BY {orders[order_by]}
    """
    with _txn() as conn:
        rows = conn.execute(sql, (group.group_id,)).fetchall()
        # An id in the membership table with no matching student row is
        # impossible while the FK holds, but the FK was added after some
        # of this data existed. Count the orphans so they are visible.
        (total,) = conn.execute(
            "SELECT COUNT(*) FROM class_group_students WHERE group_id = ?",
            (group.group_id,),
        ).fetchone()
    if len(rows) != total:
        cg_log.rejected(
            logger,
            "Class group #%d (%s) has %d membership row(s) with no matching "
            "student record; they are omitted from the roster",
            group.group_id, group.group_name, total - len(rows),
            group_id=group.group_id,
        )

    out: list[MemberDetail] = []
    for r in rows:
        parts = [r["first_name"], r["middle_name"] or "", r["last_name"]]
        detail = MemberDetail(
            group_id=r["group_id"],
            student_id=r["student_id"],
            first_name=r["first_name"],
            last_name=r["last_name"],
            full_name=" ".join(p for p in parts if p).strip(),
            email=r["email"],
            status=r["status"],
            phone=r["phone"],
            joined_at=r["joined_at"],
        )
        if include_inactive or detail.is_active:
            out.append(detail)
    return out
