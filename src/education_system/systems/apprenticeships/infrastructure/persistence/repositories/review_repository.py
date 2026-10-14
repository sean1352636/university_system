"""Progress reviews, their targets (the action plan), signatures and employer feedback."""

from __future__ import annotations

from typing import Any

from education_system.systems.apprenticeships.domain.reviews.action_plans import (
    CARRIED_FORWARD,
    ActionNote,
    carry_payload,
)
from education_system.systems.apprenticeships.domain.reviews.progress_reviews import (
    EmployerFeedback,
    Review,
    ReviewSignature,
    ReviewTarget,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    QueryBuilder,
    col,
    connect,
    init_db,
    to_bool,
    to_int,
)

_REVIEW_FIELDS = (
    "apprentice_id", "scheduled_date", "held_date", "status", "conducted_by",
    "progress_rating", "otj_on_track", "summary", "apprentice_comments",
    "employer_comments", "next_review_date",
)

_TARGET_FIELDS = (
    "review_id", "description", "due_date", "ksb_codes", "status", "outcome_note",
    "owner", "priority", "completed_at", "carried_from", "carry_count",
)

_REVIEW_SELECT = """
    SELECT r.*,
           (a.given_name || ' ' || a.family_name) AS apprentice_name,
           s.full_name AS conductor_name
      FROM reviews r
      JOIN apprentices a ON a.apprentice_id = r.apprentice_id
      LEFT JOIN staff  s ON s.staff_id      = r.conducted_by
"""

# Targets always come with the apprentice and review they belong to:
# the action-plan screens list actions across reviews, and the service
# checks ownership and scope against the apprentice.
_TARGET_SELECT = """
    SELECT t.*,
           r.apprentice_id AS apprentice_id,
           (a.given_name || ' ' || a.family_name) AS apprentice_name,
           a.employer_id AS employer_id,
           a.tutor_id    AS tutor_id,
           COALESCE(r.held_date, r.scheduled_date) AS review_date,
           r.status      AS review_status
      FROM review_targets t
      JOIN reviews     r ON r.review_id     = t.review_id
      JOIN apprentices a ON a.apprentice_id = r.apprentice_id
"""

_TARGET_ORDER = "ORDER BY COALESCE(t.due_date, '9999'), t.target_id"

# Where a review falls in an apprentice's sequence: the day it happened,
# or the day it is booked for if it has not yet, with the id breaking a
# tie between two on the same day.
_REVIEW_KEY = "COALESCE(r.held_date, r.scheduled_date)"


def _map(row: Any) -> Review:
    otj = col(row, "otj_on_track")
    return Review(
        review_id=row["review_id"],
        apprentice_id=row["apprentice_id"],
        scheduled_date=row["scheduled_date"],
        held_date=col(row, "held_date"),
        status=col(row, "status", "Scheduled"),
        conducted_by=col(row, "conducted_by"),
        progress_rating=col(row, "progress_rating"),
        # Tri-state on purpose: NULL means "not yet judged", which reads
        # differently from "judged, and they are behind".
        otj_on_track=None if otj is None else to_bool(otj),
        summary=col(row, "summary"),
        apprentice_comments=col(row, "apprentice_comments"),
        employer_comments=col(row, "employer_comments"),
        next_review_date=col(row, "next_review_date"),
        created_at=col(row, "created_at", ""),
        updated_at=col(row, "updated_at", ""),
        apprentice_name=col(row, "apprentice_name", ""),
        conductor_name=col(row, "conductor_name"),
    )


def _map_target(row: Any) -> ReviewTarget:
    return ReviewTarget(
        target_id=row["target_id"],
        review_id=row["review_id"],
        description=row["description"],
        due_date=col(row, "due_date"),
        ksb_codes=col(row, "ksb_codes"),
        status=col(row, "status", "Open"),
        outcome_note=col(row, "outcome_note"),
        owner=col(row, "owner") or "Apprentice",
        priority=col(row, "priority") or "Normal",
        completed_at=col(row, "completed_at"),
        carried_from=col(row, "carried_from"),
        carry_count=to_int(col(row, "carry_count")),
        created_at=col(row, "created_at", ""),
        updated_at=col(row, "updated_at", ""),
        apprentice_id=col(row, "apprentice_id"),
        apprentice_name=col(row, "apprentice_name", "") or "",
        employer_id=col(row, "employer_id"),
        tutor_id=col(row, "tutor_id"),
        review_date=col(row, "review_date"),
        review_status=col(row, "review_status"),
    )


def _map_signature(row: Any) -> ReviewSignature:
    return ReviewSignature(
        signature_id=row["signature_id"],
        review_id=row["review_id"],
        signatory=row["signatory"],
        signed_by=row["signed_by"],
        signed_at=row["signed_at"],
    )


def _map_note(row: Any) -> ActionNote:
    return ActionNote(
        note_id=row["note_id"],
        target_id=row["target_id"],
        author=row["author"],
        author_role=row["author_role"],
        body=row["body"],
        from_status=col(row, "from_status"),
        to_status=col(row, "to_status"),
        created_at=col(row, "created_at", ""),
    )


def _map_feedback(row: Any) -> EmployerFeedback:
    return EmployerFeedback(
        feedback_id=row["feedback_id"],
        employer_id=row["employer_id"],
        satisfaction=row["satisfaction"],
        apprentice_id=col(row, "apprentice_id"),
        review_id=col(row, "review_id"),
        comments=col(row, "comments"),
        submitted_by=col(row, "submitted_by"),
        submitted_at=col(row, "submitted_at", ""),
    )


# ── Reviews ─────────────────────────────────────────────────────────

def get(review_id: int, *, with_children: bool = True) -> Review | None:
    init_db()
    with connect() as conn:
        row = conn.execute(f"{_REVIEW_SELECT} WHERE r.review_id = ?", (review_id,)).fetchone()
        if row is None:
            return None
        review = _map(row)
        if with_children:
            review.targets = [
                _map_target(r)
                for r in conn.execute(
                    f"{_TARGET_SELECT} WHERE t.review_id = ? {_TARGET_ORDER}",
                    (review_id,),
                ).fetchall()
            ]
            review.signatures = [
                _map_signature(r)
                for r in conn.execute(
                    "SELECT * FROM review_signatures WHERE review_id = ?", (review_id,)
                ).fetchall()
            ]
    return review


def list_reviews(
    *,
    apprentice_id: int | None = None,
    status: str | None = None,
    statuses: list[str] | None = None,
    conducted_by: int | None = None,
    tutor_id: int | None = None,
    employer_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    overdue_only: bool = False,
    with_children: bool = False,
    limit: int | None = None,
) -> list[Review]:
    """Reviews matching the filters, soonest first.

    ``with_children`` costs two extra queries for the whole page rather
    than two per row — the targets and signatures for every matched
    review are fetched in one ``IN`` each and stitched on in Python.
    """
    init_db()
    qb = QueryBuilder()
    qb.add_if(apprentice_id, "r.apprentice_id = ?", apprentice_id)
    qb.add_if(status, "r.status = ?", status)
    qb.add_in("r.status", statuses)
    qb.add_if(conducted_by, "r.conducted_by = ?", conducted_by)
    qb.add_if(tutor_id, "a.tutor_id = ?", tutor_id)
    qb.add_if(employer_id, "a.employer_id = ?", employer_id)
    qb.add_if(date_from, "r.scheduled_date >= ?", date_from)
    qb.add_if(date_to, "r.scheduled_date <= ?", date_to)
    if overdue_only:
        qb.add(
            "r.status IN ('Scheduled', 'In Progress') AND r.scheduled_date < date('now')"
        )
    sql = f"{_REVIEW_SELECT} {qb.where} ORDER BY r.scheduled_date DESC, r.review_id DESC"
    args = qb.args
    if limit:
        sql += " LIMIT ?"
        args = [*args, int(limit)]

    with connect() as conn:
        reviews = [_map(r) for r in conn.execute(sql, args).fetchall()]
        if with_children and reviews:
            ids = [r.review_id for r in reviews]
            placeholders = ", ".join("?" for _ in ids)
            by_id = {r.review_id: r for r in reviews}
            for row in conn.execute(
                f"{_TARGET_SELECT} WHERE t.review_id IN ({placeholders}) {_TARGET_ORDER}", ids
            ).fetchall():
                by_id[row["review_id"]].targets.append(_map_target(row))
            for row in conn.execute(
                f"SELECT * FROM review_signatures WHERE review_id IN ({placeholders})", ids
            ).fetchall():
                by_id[row["review_id"]].signatures.append(_map_signature(row))
    return reviews


def create(payload: dict[str, Any]) -> int:
    init_db()
    columns = [f for f in _REVIEW_FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO reviews ({', '.join(columns)}) VALUES ({placeholders})",
            [payload[c] for c in columns],
        )
        return int(cur.lastrowid)


def update(review_id: int, payload: dict[str, Any]) -> None:
    init_db()
    columns = [f for f in _REVIEW_FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    with connect() as conn:
        conn.execute(
            f"UPDATE reviews SET {assignments}, updated_at = datetime('now') "
            "WHERE review_id = ?",
            [*[payload[c] for c in columns], review_id],
        )


def delete(review_id: int) -> None:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM reviews WHERE review_id = ?", (review_id,))


def next_review_after(review_id: int) -> Review | None:
    """The apprentice's next review still to be held or signed, after this one.

    Complete and missed reviews are skipped: an action cannot be carried
    onto a meeting that is over or did not happen.
    """
    init_db()
    with connect() as conn:
        anchor = conn.execute(
            f"SELECT r.apprentice_id, {_REVIEW_KEY} AS k FROM reviews r WHERE r.review_id = ?",
            (review_id,),
        ).fetchone()
        if anchor is None:
            return None
        row = conn.execute(
            f"""{_REVIEW_SELECT}
                 WHERE r.apprentice_id = ? AND r.review_id != ?
                   AND r.status NOT IN ('Complete', 'Missed')
                   AND ({_REVIEW_KEY} > ? OR ({_REVIEW_KEY} = ? AND r.review_id > ?))
                 ORDER BY {_REVIEW_KEY}, r.review_id
                 LIMIT 1""",
            (anchor["apprentice_id"], review_id, anchor["k"], anchor["k"], review_id),
        ).fetchone()
    return _map(row) if row else None


def count_overdue(*, tutor_id: int | None = None, employer_id: int | None = None) -> int:
    init_db()
    qb = QueryBuilder()
    qb.add("r.status IN ('Scheduled', 'In Progress')")
    qb.add("r.scheduled_date < date('now')")
    qb.add_if(tutor_id, "a.tutor_id = ?", tutor_id)
    qb.add_if(employer_id, "a.employer_id = ?", employer_id)
    with connect() as conn:
        row = conn.execute(
            f"""SELECT COUNT(*) AS n FROM reviews r
                  JOIN apprentices a ON a.apprentice_id = r.apprentice_id
                  {qb.where}""",
            qb.args,
        ).fetchone()
    return int(row["n"])


def count_awaiting_signature(
    *, tutor_id: int | None = None, employer_id: int | None = None
) -> int:
    init_db()
    qb = QueryBuilder()
    qb.add("r.status = 'Awaiting Signatures'")
    qb.add_if(tutor_id, "a.tutor_id = ?", tutor_id)
    qb.add_if(employer_id, "a.employer_id = ?", employer_id)
    with connect() as conn:
        row = conn.execute(
            f"""SELECT COUNT(*) AS n FROM reviews r
                  JOIN apprentices a ON a.apprentice_id = r.apprentice_id
                  {qb.where}""",
            qb.args,
        ).fetchone()
    return int(row["n"])


def unsigned_review_count(apprentice_id: int) -> int:
    """Held reviews that are not fully signed — a gateway blocker."""
    init_db()
    with connect() as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS n FROM reviews r
                WHERE r.apprentice_id = ?
                  AND r.status NOT IN ('Complete', 'Missed', 'Scheduled')""",
            (apprentice_id,),
        ).fetchone()
    return int(row["n"])


def held_review_count(apprentice_id: int) -> int:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM reviews WHERE apprentice_id = ? AND status = 'Complete'",
            (apprentice_id,),
        ).fetchone()
    return int(row["n"])


# ── Targets (the action plan) ───────────────────────────────────────

def _target_filters(
    *,
    review_id: int | None = None,
    apprentice_id: int | None = None,
    employer_id: int | None = None,
    tutor_id: int | None = None,
    status: str | None = None,
    statuses: list[str] | None = None,
    owner: str | None = None,
    priority: str | None = None,
    open_only: bool = False,
    overdue_on: str | None = None,
    due_from: str | None = None,
    due_before: str | None = None,
) -> QueryBuilder:
    qb = QueryBuilder()
    qb.add_if(review_id, "t.review_id = ?", review_id)
    qb.add_if(apprentice_id, "r.apprentice_id = ?", apprentice_id)
    qb.add_if(employer_id, "a.employer_id = ?", employer_id)
    qb.add_if(tutor_id, "a.tutor_id = ?", tutor_id)
    qb.add_if(status, "t.status = ?", status)
    qb.add_in("t.status", statuses)
    qb.add_if(owner, "t.owner = ?", owner)
    qb.add_if(priority, "t.priority = ?", priority)
    qb.add_if(open_only, "t.status = 'Open'")
    # Overdue is judged against a date the caller passes rather than
    # SQLite's date('now'), which is UTC: the domain's is_overdue uses the
    # local date, and the list and the row colour must agree at midnight.
    qb.add_if(
        overdue_on,
        "t.status = 'Open' AND t.due_date IS NOT NULL AND t.due_date < ?",
        overdue_on,
    )
    qb.add_if(due_from, "t.due_date >= ?", due_from)
    qb.add_if(due_before, "t.due_date <= ?", due_before)
    return qb


def list_targets(
    review_id: int | None = None,
    *,
    apprentice_id: int | None = None,
    employer_id: int | None = None,
    tutor_id: int | None = None,
    status: str | None = None,
    statuses: list[str] | None = None,
    owner: str | None = None,
    priority: str | None = None,
    open_only: bool = False,
    overdue_on: str | None = None,
    due_from: str | None = None,
    due_before: str | None = None,
    limit: int | None = None,
) -> list[ReviewTarget]:
    """Targets matching the filters, soonest due first.

    ``apprentice_id`` / ``employer_id`` / ``tutor_id`` are the scope
    filters ``access.apprentice_filters()`` yields, so "what is due or
    overdue in my scope" is one call: ``open_only=True`` plus
    ``due_before`` (due by then) or ``overdue_on`` (past due as of then).
    """
    init_db()
    qb = _target_filters(
        review_id=review_id, apprentice_id=apprentice_id, employer_id=employer_id,
        tutor_id=tutor_id, status=status, statuses=statuses, owner=owner,
        priority=priority, open_only=open_only, overdue_on=overdue_on,
        due_from=due_from, due_before=due_before,
    )
    sql = f"{_TARGET_SELECT} {qb.where} {_TARGET_ORDER}"
    args = qb.args
    if limit:
        sql += " LIMIT ?"
        args = [*args, int(limit)]
    with connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [_map_target(r) for r in rows]


def count_targets(**filters: Any) -> int:
    """How many targets match — the same filters as :func:`list_targets`.

    For dashboard tiles, which want the number without the rows.
    """
    init_db()
    qb = _target_filters(**filters)
    with connect() as conn:
        row = conn.execute(
            f"""SELECT COUNT(*) AS n
                  FROM review_targets t
                  JOIN reviews     r ON r.review_id     = t.review_id
                  JOIN apprentices a ON a.apprentice_id = r.apprentice_id
                  {qb.where}""",
            qb.args,
        ).fetchone()
    return to_int(col(row, "n"))


def get_target(target_id: int) -> ReviewTarget | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            f"{_TARGET_SELECT} WHERE t.target_id = ?", (target_id,)
        ).fetchone()
    return _map_target(row) if row else None


def create_target(payload: dict[str, Any]) -> int:
    init_db()
    columns = [f for f in _TARGET_FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO review_targets ({', '.join(columns)}) VALUES ({placeholders})",
            [payload[c] for c in columns],
        )
        return int(cur.lastrowid)


def update_target(target_id: int, payload: dict[str, Any]) -> None:
    init_db()
    columns = [f for f in _TARGET_FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    with connect() as conn:
        conn.execute(
            f"UPDATE review_targets SET {assignments}, updated_at = datetime('now') "
            "WHERE target_id = ?",
            [*[payload[c] for c in columns], target_id],
        )


def delete_target(target_id: int) -> None:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM review_targets WHERE target_id = ?", (target_id,))


def record_status(
    target_id: int,
    *,
    status: str,
    completed_at: str | None,
    from_status: str,
    author: str,
    author_role: str,
    body: str,
) -> int:
    """Move an action's status and log the move in its history, together.

    One transaction, so the action's status and the note explaining how
    it got there cannot disagree.
    """
    init_db()
    with connect() as conn:
        conn.execute(
            """UPDATE review_targets
                  SET status = ?, completed_at = ?, updated_at = datetime('now')
                WHERE target_id = ?""",
            (status, completed_at, target_id),
        )
        cur = conn.execute(
            """INSERT INTO action_notes
                   (target_id, author, author_role, body, from_status, to_status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (target_id, author, author_role, body, from_status, status),
        )
        return int(cur.lastrowid)


def add_note(target_id: int, *, author: str, author_role: str, body: str) -> int:
    init_db()
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO action_notes (target_id, author, author_role, body)
               VALUES (?, ?, ?, ?)""",
            (target_id, author, author_role, body),
        )
        return int(cur.lastrowid)


def list_notes(target_ids: list[int]) -> list[ActionNote]:
    """The history of one or more actions, newest first."""
    if not target_ids:
        return []
    init_db()
    placeholders = ", ".join("?" for _ in target_ids)
    with connect() as conn:
        rows = conn.execute(
            f"""SELECT * FROM action_notes WHERE target_id IN ({placeholders})
                 ORDER BY created_at DESC, note_id DESC""",
            list(target_ids),
        ).fetchall()
    return [_map_note(r) for r in rows]


def carry_chain(target_id: int) -> list[int]:
    """This action's id and every earlier copy it was carried from, newest first."""
    init_db()
    chain: list[int] = []
    current: int | None = target_id
    with connect() as conn:
        # Bounded by the table size: a cycle is impossible (each copy
        # points at an older row) but a guard costs nothing.
        while current is not None and current not in chain:
            chain.append(current)
            row = conn.execute(
                "SELECT carried_from FROM review_targets WHERE target_id = ?", (current,)
            ).fetchone()
            current = row["carried_from"] if row else None
    return chain


def _carry(conn: Any, target: ReviewTarget, to_review_id: int, note: str) -> int:
    """Copy one open target onto a later review and close the original.

    Runs inside the caller's transaction so a batch carries completely
    or not at all.
    """
    data = carry_payload(target, to_review_id)
    columns = [f for f in _TARGET_FIELDS if f in data]
    cur = conn.execute(
        f"INSERT INTO review_targets ({', '.join(columns)}) "
        f"VALUES ({', '.join('?' for _ in columns)})",
        [data[c] for c in columns],
    )
    conn.execute(
        """UPDATE review_targets
              SET status = ?, outcome_note = ?, completed_at = NULL,
                  updated_at = datetime('now')
            WHERE target_id = ?""",
        (CARRIED_FORWARD, note, target.target_id),
    )
    return int(cur.lastrowid)


def carry_target(target_id: int, to_review_id: int, *, note: str) -> int | None:
    """Carry one target onto *to_review_id*. Returns the new copy's id,
    or None if the target is no longer open (somebody got there first)."""
    init_db()
    with connect() as conn:
        row = conn.execute(f"{_TARGET_SELECT} WHERE t.target_id = ?", (target_id,)).fetchone()
        if row is None or row["status"] != "Open":
            return None
        return _carry(conn, _map_target(row), to_review_id, note)


def carry_forward_into(review_id: int, *, note: str) -> list[tuple[int, int]]:
    """Carry every open target from the apprentice's earlier reviews onto this one.

    "Earlier" is by the date each review happened (or is booked for),
    so targets on a later review are never pulled backwards. Returns
    ``(old_id, new_id)`` pairs. Idempotent: a carried target is no longer
    open, so running this twice carries nothing the second time.
    """
    init_db()
    with connect() as conn:
        anchor = conn.execute(
            f"SELECT r.apprentice_id, {_REVIEW_KEY} AS k FROM reviews r WHERE r.review_id = ?",
            (review_id,),
        ).fetchone()
        if anchor is None:
            return []
        rows = conn.execute(
            f"""{_TARGET_SELECT}
                 WHERE r.apprentice_id = ? AND t.review_id != ? AND t.status = 'Open'
                   AND ({_REVIEW_KEY} < ? OR ({_REVIEW_KEY} = ? AND r.review_id < ?))
                 ORDER BY t.target_id""",
            (anchor["apprentice_id"], review_id, anchor["k"], anchor["k"], review_id),
        ).fetchall()
        return [
            (target.target_id, _carry(conn, target, review_id, note))
            for target in (_map_target(r) for r in rows)
        ]


# ── Signatures ──────────────────────────────────────────────────────

def list_signatures(review_id: int) -> list[ReviewSignature]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM review_signatures WHERE review_id = ?", (review_id,)
        ).fetchall()
    return [_map_signature(r) for r in rows]


def add_signature(review_id: int, signatory: str, signed_by: str) -> int:
    """Record a signature.

    ``INSERT OR IGNORE`` against the UNIQUE(review_id, signatory) index:
    a double-click on Sign must not create a second signature, and the
    service has already checked whether signing is allowed.
    """
    init_db()
    with connect() as conn:
        cur = conn.execute(
            """INSERT OR IGNORE INTO review_signatures (review_id, signatory, signed_by)
               VALUES (?, ?, ?)""",
            (review_id, signatory, signed_by),
        )
        return int(cur.lastrowid or 0)


def remove_signature(review_id: int, signatory: str) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            "DELETE FROM review_signatures WHERE review_id = ? AND signatory = ?",
            (review_id, signatory),
        )


# ── Employer feedback ───────────────────────────────────────────────

def add_feedback(payload: dict[str, Any]) -> int:
    init_db()
    fields = ("employer_id", "apprentice_id", "review_id", "satisfaction",
              "comments", "submitted_by")
    columns = [f for f in fields if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO employer_feedback ({', '.join(columns)}) VALUES ({placeholders})",
            [payload[c] for c in columns],
        )
        return int(cur.lastrowid)


def list_feedback(
    *, employer_id: int | None = None, apprentice_id: int | None = None,
    limit: int | None = None,
) -> list[EmployerFeedback]:
    init_db()
    qb = QueryBuilder()
    qb.add_if(employer_id, "employer_id = ?", employer_id)
    qb.add_if(apprentice_id, "apprentice_id = ?", apprentice_id)
    sql = f"SELECT * FROM employer_feedback {qb.where} ORDER BY submitted_at DESC"
    args = qb.args
    if limit:
        sql += " LIMIT ?"
        args = [*args, int(limit)]
    with connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [_map_feedback(r) for r in rows]


def average_satisfaction(*, employer_id: int | None = None) -> float | None:
    """Mean satisfaction score, or None when nobody has rated anything."""
    init_db()
    rows = list_feedback(employer_id=employer_id)
    scored = [f.score for f in rows if f.score]
    if not scored:
        return None
    return round(sum(scored) / len(scored), 2)
