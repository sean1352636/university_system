"""Progress reviews, their targets, signatures and employer feedback."""

from __future__ import annotations

from typing import Any

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
)

_REVIEW_FIELDS = (
    "apprentice_id", "scheduled_date", "held_date", "status", "conducted_by",
    "progress_rating", "otj_on_track", "summary", "apprentice_comments",
    "employer_comments", "next_review_date",
)

_TARGET_FIELDS = (
    "review_id", "description", "due_date", "ksb_codes", "status", "outcome_note",
)

_REVIEW_SELECT = """
    SELECT r.*,
           (a.given_name || ' ' || a.family_name) AS apprentice_name,
           s.full_name AS conductor_name
      FROM reviews r
      JOIN apprentices a ON a.apprentice_id = r.apprentice_id
      LEFT JOIN staff  s ON s.staff_id      = r.conducted_by
"""


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
        created_at=col(row, "created_at", ""),
        updated_at=col(row, "updated_at", ""),
    )


def _map_signature(row: Any) -> ReviewSignature:
    return ReviewSignature(
        signature_id=row["signature_id"],
        review_id=row["review_id"],
        signatory=row["signatory"],
        signed_by=row["signed_by"],
        signed_at=row["signed_at"],
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
                    "SELECT * FROM review_targets WHERE review_id = ? "
                    "ORDER BY COALESCE(due_date, '9999'), target_id",
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
                f"SELECT * FROM review_targets WHERE review_id IN ({placeholders})", ids
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


# ── Targets ─────────────────────────────────────────────────────────

def list_targets(
    review_id: int | None = None, *, apprentice_id: int | None = None,
    open_only: bool = False,
) -> list[ReviewTarget]:
    init_db()
    qb = QueryBuilder()
    qb.add_if(review_id, "t.review_id = ?", review_id)
    qb.add_if(apprentice_id, "r.apprentice_id = ?", apprentice_id)
    qb.add_if(open_only, "t.status = 'Open'")
    with connect() as conn:
        rows = conn.execute(
            f"""SELECT t.* FROM review_targets t
                  JOIN reviews r ON r.review_id = t.review_id
                  {qb.where}
                 ORDER BY COALESCE(t.due_date, '9999'), t.target_id""",
            qb.args,
        ).fetchall()
    return [_map_target(r) for r in rows]


def get_target(target_id: int) -> ReviewTarget | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM review_targets WHERE target_id = ?", (target_id,)
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
