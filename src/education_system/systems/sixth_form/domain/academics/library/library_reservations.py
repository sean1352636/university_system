"""Library reservations / holds.

Lifecycle: ``Waiting`` (in the queue) -> ``Ready`` (a copy is on the
hold shelf for the student) -> ``Collected`` (turned into a loan), or
``Cancelled`` / ``Expired``.

Copies accounting: when a reservation is promoted to ``Ready`` a copy is
taken off the shelf (``copies_available`` is decremented) so a walk-in
can't borrow the held copy. Collecting turns it into a loan; cancelling
or expiring a ``Ready`` hold puts the copy back and promotes the next
person in the queue.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass

from education_system.systems.sixth_form.domain.academics.library import (
    library as _lib,
    library_settings as _settings,
)

logger = logging.getLogger(__name__)

ValidationError = _lib.ValidationError

RESERVATION_STATUSES: tuple[str, ...] = (
    "Waiting", "Ready", "Collected", "Cancelled", "Expired",
)
OPEN_STATUSES: tuple[str, ...] = ("Waiting", "Ready")


@dataclass
class Reservation:
    reservation_id: int
    book_id: int
    student_id: str
    status: str
    reserved_on: str
    ready_on: str | None
    expires_on: str | None
    notes: str | None
    created_at: str
    updated_at: str


def _row(r) -> Reservation:
    return Reservation(
        reservation_id=r["reservation_id"], book_id=r["book_id"],
        student_id=r["student_id"], status=r["status"],
        reserved_on=r["reserved_on"], ready_on=r["ready_on"],
        expires_on=r["expires_on"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"])


def _today(offset: int = 0) -> str:
    return (_dt.date.today() + _dt.timedelta(days=offset)).isoformat()


def get_reservation(reservation_id: int) -> Reservation | None:
    _lib.init_db()
    with _lib._connect() as conn:
        r = conn.execute(
            "SELECT * FROM library_reservations "
            "WHERE reservation_id = ?", (reservation_id,)).fetchone()
    return _row(r) if r else None


def list_reservations(*, book_id: int | None = None,
                      student_id: str | None = None,
                      status: str | None = None,
                      open_only: bool = False) -> list[Reservation]:
    _lib.init_db()
    clauses, args = [], []
    if book_id is not None:
        clauses.append("book_id = ?")
        args.append(int(book_id))
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if status:
        if status not in RESERVATION_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(RESERVATION_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if open_only:
        clauses.append("status IN ('Waiting', 'Ready')")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _lib._connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM library_reservations {where} "
            "ORDER BY reserved_on ASC, reservation_id ASC",
            args).fetchall()
    return [_row(r) for r in rows]


def has_waiting(book_id: int) -> bool:
    _lib.init_db()
    with _lib._connect() as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM library_reservations "
            "WHERE book_id = ? AND status = 'Waiting'",
            (int(book_id),)).fetchone()[0]
    return n > 0


def reserve(book_id: int, student_id: str, *,
            notes: str | None = None) -> Reservation:
    _lib.init_db()
    book = _lib.get_book(book_id)
    if book is None:
        raise ValidationError(f"No book #{book_id}")
    sid = (student_id or "").strip()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    # One open hold per student per title.
    dupes = list_reservations(book_id=book_id, student_id=sid,
                              open_only=True)
    if dupes:
        raise ValidationError(
            "Student already has an open reservation for this title")
    with _lib._connect() as conn:
        cur = conn.execute(
            "INSERT INTO library_reservations "
            "(book_id, student_id, status, reserved_on, notes, "
            " created_at, updated_at) "
            "VALUES (?, ?, 'Waiting', ?, ?, "
            "        datetime('now'), datetime('now'))",
            (int(book_id), sid, _today(),
             (notes or "").strip() or None))
        conn.commit()
        rid = cur.lastrowid
    logger.info("Reservation #%d placed for student %s on book #%d",
                rid, sid, book_id)
    # If a copy is free right now, promote straight to Ready.
    promote_next(book_id)
    out = get_reservation(rid)
    assert out is not None
    if out.status == "Waiting":
        _notify_placed(out)
    return out


def waitlist_position(reservation_id: int) -> int:
    """1-based position among ``Waiting`` holds for the same title.

    Returns 0 for a hold that is already ``Ready`` (or not waiting)."""
    res = get_reservation(reservation_id)
    if res is None:
        raise ValidationError(f"No reservation #{reservation_id}")
    if res.status != "Waiting":
        return 0
    waiting = [r for r in list_reservations(book_id=res.book_id,
                                            status="Waiting")]
    for i, r in enumerate(waiting, 1):
        if r.reservation_id == reservation_id:
            return i
    return 0


def _set_status(reservation_id: int, status: str, **cols) -> None:
    sets = ["status = ?", "updated_at = datetime('now')"]
    args: list = [status]
    for k, v in cols.items():
        sets.append(f"{k} = ?")
        args.append(v)
    args.append(reservation_id)
    with _lib._connect() as conn:
        conn.execute(
            f"UPDATE library_reservations SET {', '.join(sets)} "
            "WHERE reservation_id = ?", args)
        conn.commit()


def promote_next(book_id: int) -> Reservation | None:
    """Promote the oldest ``Waiting`` hold to ``Ready`` for each free
    copy. Returns the most recently promoted reservation, if any."""
    _lib.init_db()
    promoted: Reservation | None = None
    hold_days = int(_settings.get_setting("hold_shelf_days"))
    while True:
        book = _lib.get_book(book_id)
        if book is None or book.copies_available <= 0:
            break
        waiting = list_reservations(book_id=book_id, status="Waiting")
        if not waiting:
            break
        nxt = waiting[0]
        _set_status(nxt.reservation_id, "Ready",
                    ready_on=_today(),
                    expires_on=_today(hold_days))
        _lib._adjust_available(book_id, -1)  # onto the hold shelf
        promoted = get_reservation(nxt.reservation_id)
        logger.info("Reservation #%d ready for collection (book #%d)",
                    nxt.reservation_id, book_id)
        _notify_ready(promoted)
    return promoted


def cancel_reservation(reservation_id: int) -> Reservation:
    res = get_reservation(reservation_id)
    if res is None:
        raise ValidationError(f"No reservation #{reservation_id}")
    if res.status not in OPEN_STATUSES:
        raise ValidationError(
            f"Reservation is already {res.status}")
    _set_status(reservation_id, "Cancelled")
    if res.status == "Ready":
        # Copy comes off the hold shelf, back into circulation.
        _lib._adjust_available(res.book_id, +1)
        promote_next(res.book_id)
    logger.info("Reservation #%d cancelled", reservation_id)
    out = get_reservation(reservation_id)
    assert out is not None
    return out


def collect_reservation(reservation_id: int, *,
                        issued_by: str | None = None) -> "tuple":
    """Turn a ``Ready`` hold into an actual loan. Returns
    ``(reservation, loan)``."""
    res = get_reservation(reservation_id)
    if res is None:
        raise ValidationError(f"No reservation #{reservation_id}")
    if res.status != "Ready":
        raise ValidationError(
            f"Reservation #{reservation_id} is not Ready "
            f"(status={res.status})")
    # The held copy is on the hold shelf (available was decremented at
    # promotion); put it back so issue() can take it cleanly.
    _lib._adjust_available(res.book_id, +1)
    try:
        loan = _lib.issue(res.book_id, res.student_id,
                          issued_by=issued_by,
                          notes=f"Collected hold #{reservation_id}",
                          override_blocks=True)
    except ValidationError:
        _lib._adjust_available(res.book_id, -1)  # restore hold shelf
        raise
    _set_status(reservation_id, "Collected")
    logger.info("Reservation #%d collected as loan #%d",
                reservation_id, loan.loan_id)
    return get_reservation(reservation_id), loan


def expire_holds(*, as_of: str | None = None) -> int:
    """Expire ``Ready`` holds past their hold-shelf date (item 13).

    Returns the number expired. Each expiry returns its copy to the
    shelf and promotes the next waiting hold."""
    _lib.init_db()
    today = as_of or _today()
    with _lib._connect() as conn:
        rows = conn.execute(
            "SELECT reservation_id, book_id FROM library_reservations "
            "WHERE status = 'Ready' AND expires_on IS NOT NULL "
            "AND expires_on < ?", (today,)).fetchall()
    count = 0
    for r in rows:
        _set_status(r["reservation_id"], "Expired")
        expired = get_reservation(r["reservation_id"])
        _lib._adjust_available(r["book_id"], +1)
        promote_next(r["book_id"])
        _notify_expired(expired)
        count += 1
    if count:
        logger.info("Expired %d hold(s) as of %s", count, today)
    return count


def recall(loan_id: int, *, grace_days: int = 0,
           notify: bool = True) -> "object":
    """Recall an active loan (item 14): shorten its due date so the
    item comes back for someone waiting on it."""
    loan = _lib.get_loan(loan_id)
    if loan is None:
        raise ValidationError(f"No loan #{loan_id}")
    if not loan.is_active:
        raise ValidationError("Can only recall an active loan")
    new_due = _today(grace_days)
    note = (loan.notes + " | Recalled") if loan.notes else "Recalled"
    out = _lib.update_loan(loan_id, {"due_on": new_due, "notes": note})
    logger.info("Loan #%d recalled — due now %s", loan_id, new_due)
    if notify:
        _notify_recall(out)
    return out


def _notify_ready(res: Reservation | None) -> None:
    if res is None:
        return
    try:
        from education_system.systems.sixth_form.domain.academics.library import (
            library_notifications as _notifs,
        )
        _notifs.notify_reservation_ready(res)
    except Exception:
        logger.debug("Ready notification skipped for hold #%d",
                     res.reservation_id, exc_info=True)


def _notify_recall(loan) -> None:
    try:
        from education_system.systems.sixth_form.domain.academics.library import (
            library_notifications as _notifs,
        )
        _notifs.notify_recall(loan)
    except Exception:
        logger.debug("Recall notification skipped for loan #%d",
                     loan.loan_id, exc_info=True)


def _notify_placed(reservation) -> None:
    try:
        from education_system.systems.sixth_form.domain.academics.library import (
            library_notifications as _notifs,
        )
        _notifs.notify_reservation_placed(reservation)
    except Exception:
        logger.debug("Placed notification skipped for hold #%s",
                     getattr(reservation, "reservation_id", "?"),
                     exc_info=True)


def _notify_expired(reservation) -> None:
    if reservation is None:
        return
    try:
        from education_system.systems.sixth_form.domain.academics.library import (
            library_notifications as _notifs,
        )
        _notifs.notify_hold_expired(reservation)
    except Exception:
        logger.debug("Expiry notification skipped for hold #%s",
                     getattr(reservation, "reservation_id", "?"),
                     exc_info=True)
