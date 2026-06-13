"""Library notifications (items 15-20).

Each notification is rendered from an email template and dropped into the
messages log via :func:`email_templates.send_from_template` (the
system's standard, simulated email path). Every send is recorded in
``library_notifications`` with a ``dedupe_key`` so the same reminder
isn't sent twice — the unique index on that column enforces it.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3

from education_system.sixthform_system.modules.domain.academics.library import (
    library as _lib,
    library_settings as _settings,
)

logger = logging.getLogger(__name__)

DIGEST_INBOX = "library@sixthform.ac.uk"


def _system_name() -> str:
    try:
        from education_system.sixthform_system import SYSTEM_NAME
        return SYSTEM_NAME
    except Exception:
        return "Sixth Form"


def _send(template: str, context: dict, *, to_name=None,
          to_address=None, student_id=None):
    from education_system.sixthform_system.modules.domain.staff_comms.messages import (
        email_templates,
    )
    context.setdefault("system_name", _system_name())
    return email_templates.send_from_template(
        template, context, to_name=to_name, to_address=to_address,
        student_id=student_id)


def _claim(kind: str, dedupe_key: str, *, loan_id=None,
           reservation_id=None, fine_id=None, student_id=None) -> bool:
    """Reserve a dedupe key. Returns False if already claimed."""
    _lib.init_db()
    with _lib._connect() as conn:
        try:
            conn.execute(
                "INSERT INTO library_notifications "
                "(kind, loan_id, reservation_id, fine_id, student_id, "
                " dedupe_key, sent_at) "
                "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
                (kind, loan_id, reservation_id, fine_id, student_id,
                 dedupe_key))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def _unclaim(dedupe_key: str) -> None:
    with _lib._connect() as conn:
        conn.execute(
            "DELETE FROM library_notifications WHERE dedupe_key = ?",
            (dedupe_key,))
        conn.commit()


def _student(sid: str):
    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    return _students.get_student(sid)


def _book_title(book_id: int) -> str:
    b = _lib.get_book(book_id)
    return b.title if b else f"#{book_id}"


def _deliver(template, context, *, dedupe_key, kind, student, **ids):
    """Claim-then-send to a student; roll back the claim if send fails."""
    if student is None:
        return None
    return _deliver_to(template, context, to_name=student.full_name,
                       to_address=student.email,
                       student_id=student.student_id,
                       dedupe_key=dedupe_key, kind=kind, **ids)


def _deliver_to(template, context, *, to_name, to_address,
                dedupe_key, kind, student_id=None, **ids):
    """Generic claim-then-send for any recipient (student or free-text
    staff name). A ``dedupe_key`` of ``None`` always sends (still logged
    for audit) — use it for transactional receipts that may recur."""
    if not _claim(kind, dedupe_key, student_id=student_id, **ids):
        return None
    try:
        return _send(template, context, to_name=to_name,
                     to_address=to_address, student_id=student_id)
    except Exception:
        logger.exception("Library notification '%s' failed to send",
                         template)
        if dedupe_key is not None:
            _unclaim(dedupe_key)
        return None


# ── Individual notifications ──────────────────────────────────────

def notify_due_soon(loan):
    student = _student(loan.student_id)
    return _deliver(
        "library_due_soon",
        {"first_name": getattr(student, "first_name", ""),
         "book_title": _book_title(loan.book_id),
         "due_date": loan.due_on},
        dedupe_key=f"due_soon:loan={loan.loan_id}:due={loan.due_on}",
        kind="due_soon", student=student, loan_id=loan.loan_id)


_OVERDUE_STAGES = (
    (1, "First reminder"),
    (8, "Second reminder"),
    (15, "Final notice"),
)


def _overdue_stage(days_overdue: int) -> tuple[int, str]:
    stage, label = 1, _OVERDUE_STAGES[0][1]
    for i, (threshold, lbl) in enumerate(_OVERDUE_STAGES, 1):
        if days_overdue >= threshold:
            stage, label = i, lbl
    return stage, label


def notify_overdue(loan):
    days = loan.days_overdue
    if days <= 0:
        return None
    stage, label = _overdue_stage(days)
    rate = float(_settings.get_setting("fine_daily_rate"))
    cap = float(_settings.get_setting("fine_max_per_loan"))
    fine_so_far = min(days * rate, cap)
    student = _student(loan.student_id)
    return _deliver(
        "library_overdue",
        {"first_name": getattr(student, "first_name", ""),
         "book_title": _book_title(loan.book_id),
         "due_date": loan.due_on, "days_overdue": days,
         "stage_label": label,
         "fine_so_far": f"{fine_so_far:.2f}"},
        dedupe_key=f"overdue:loan={loan.loan_id}:stage={stage}",
        kind="overdue", student=student, loan_id=loan.loan_id)


def notify_reservation_ready(reservation):
    student = _student(reservation.student_id)
    return _deliver(
        "library_reservation_ready",
        {"first_name": getattr(student, "first_name", ""),
         "book_title": _book_title(reservation.book_id),
         "expires_on": reservation.expires_on or "soon"},
        dedupe_key=f"ready:res={reservation.reservation_id}",
        kind="reservation_ready", student=student,
        reservation_id=reservation.reservation_id)


def notify_fine_issued(fine):
    from education_system.sixthform_system.modules.domain.academics.library import (
        library_fines as _fines,
    )
    student = _student(fine.student_id)
    title = "—"
    if fine.loan_id:
        loan = _lib.get_loan(fine.loan_id)
        if loan:
            title = _book_title(loan.book_id)
    balance = _fines.student_balance(fine.student_id)
    return _deliver(
        "library_fine_issued",
        {"first_name": getattr(student, "first_name", ""),
         "reason": fine.reason, "amount": f"{fine.amount:.2f}",
         "book_title": title, "note": fine.note or "—",
         "balance": f"{balance:.2f}"},
        dedupe_key=f"fine:{fine.fine_id}",
        kind="fine_issued", student=student, fine_id=fine.fine_id)


def notify_recall(loan):
    student = _student(loan.student_id)
    return _deliver(
        "library_recall",
        {"first_name": getattr(student, "first_name", ""),
         "book_title": _book_title(loan.book_id),
         "new_due": loan.due_on},
        dedupe_key=f"recall:loan={loan.loan_id}:due={loan.due_on}",
        kind="recall", student=student, loan_id=loan.loan_id)


# ── Transactional receipts & status updates ───────────────────────

def notify_loan_receipt(loan):
    student = _student(loan.student_id)
    return _deliver(
        "library_loan_receipt",
        {"first_name": getattr(student, "first_name", ""),
         "book_title": _book_title(loan.book_id),
         "loaned_on": loan.loaned_on, "due_date": loan.due_on},
        dedupe_key=f"loan_receipt:loan={loan.loan_id}",
        kind="loan_receipt", student=student, loan_id=loan.loan_id)


def notify_renewal(loan):
    student = _student(loan.student_id)
    book = _lib.get_book(loan.book_id)
    cap = (_settings.get_policy(book.item_type).max_renewals
           if book else "")
    return _deliver(
        "library_renewal_confirmation",
        {"first_name": getattr(student, "first_name", ""),
         "book_title": _book_title(loan.book_id),
         "new_due": loan.due_on,
         "renewals_count": loan.renewals_count, "max_renewals": cap},
        dedupe_key=f"renewal:loan={loan.loan_id}:due={loan.due_on}",
        kind="renewal", student=student, loan_id=loan.loan_id)


def notify_return_receipt(loan, *, fine_raised: float | None = None):
    from education_system.sixthform_system.modules.domain.academics.library import (
        library_fines as _fines,
    )
    student = _student(loan.student_id)
    balance = _fines.student_balance(loan.student_id)
    if fine_raised:
        fine_note = f"A charge of {fine_raised:.2f} was raised."
    else:
        fine_note = "No charges were raised."
    return _deliver(
        "library_return_receipt",
        {"first_name": getattr(student, "first_name", ""),
         "book_title": _book_title(loan.book_id),
         "returned_on": loan.returned_on or "",
         "fine_note": fine_note, "balance": f"{balance:.2f}"},
        dedupe_key=f"return_receipt:loan={loan.loan_id}",
        kind="return_receipt", student=student, loan_id=loan.loan_id)


def notify_reservation_placed(reservation):
    if reservation.status != "Waiting":
        return None
    from education_system.sixthform_system.modules.domain.academics.library import (
        library_reservations as _holds,
    )
    student = _student(reservation.student_id)
    pos = _holds.waitlist_position(reservation.reservation_id)
    return _deliver(
        "library_reservation_placed",
        {"first_name": getattr(student, "first_name", ""),
         "book_title": _book_title(reservation.book_id),
         "queue_position": pos},
        dedupe_key=f"placed:res={reservation.reservation_id}",
        kind="reservation_placed", student=student,
        reservation_id=reservation.reservation_id)


def notify_hold_expired(reservation):
    student = _student(reservation.student_id)
    return _deliver(
        "library_hold_expired",
        {"first_name": getattr(student, "first_name", ""),
         "book_title": _book_title(reservation.book_id),
         "expired_on": reservation.expires_on or ""},
        dedupe_key=f"hold_expired:res={reservation.reservation_id}",
        kind="hold_expired", student=student,
        reservation_id=reservation.reservation_id)


def notify_fine_settled(fine):
    from education_system.sixthform_system.modules.domain.academics.library import (
        library_fines as _fines,
    )
    student = _student(fine.student_id)
    balance = _fines.student_balance(fine.student_id)
    return _deliver(
        "library_fine_settled",
        {"first_name": getattr(student, "first_name", ""),
         "reason": fine.reason,
         "amount_paid": f"{fine.amount_paid:.2f}",
         "amount_waived": f"{fine.amount_waived:.2f}",
         "status": fine.status, "balance": f"{balance:.2f}"},
        dedupe_key=None,  # settlement can happen in several steps
        kind="fine_settled", student=student, fine_id=fine.fine_id)


def notify_class_set_ready(class_set):
    """To the requesting teacher (free-text name; logged as an internal
    message since we don't hold a staff email)."""
    name = class_set.requested_by or "Teacher"
    return _deliver_to(
        "library_class_set_ready",
        {"requested_by": name, "book_title": class_set.book_title,
         "copies_needed": class_set.copies_needed,
         "needed_by": class_set.needed_by or "—",
         "status": class_set.status},
        to_name=name, to_address=None,
        dedupe_key=f"classset:{class_set.set_id}:{class_set.status}",
        kind="class_set")


def notify_acquisition_update(acq):
    name = acq.requested_by or "Requester"
    supplier = "—"
    if acq.supplier_id:
        from education_system.sixthform_system.modules.domain.academics.library import (
            library_acquisitions as _acq,
        )
        s = _acq.get_supplier(acq.supplier_id)
        if s:
            supplier = s.name
    return _deliver_to(
        "library_acquisition_update",
        {"requested_by": name, "title": acq.title,
         "quantity": acq.quantity, "supplier": supplier,
         "status": acq.status},
        to_name=name, to_address=None,
        dedupe_key=f"acq:{acq.acq_id}:{acq.status}",
        kind="acquisition")


def notify_reading_list_shared(reading_list) -> int:
    """Fan out to every student studying the list's subject. Returns the
    number of students notified."""
    subject = reading_list.subject
    if not subject:
        return 0
    from education_system.sixthform_system.modules.domain.academics.library import (
        library_reading_lists as _reading,
    )
    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    items = _reading.list_items(reading_list.list_id)
    required = sum(1 for i in items if i.requirement == "Required")
    recommended = len(items) - required
    sent = 0
    for s in _students.list_students():
        if subject not in (s.subjects or []):
            continue
        res = _deliver(
            "library_reading_list_shared",
            {"first_name": s.first_name,
             "list_title": reading_list.title, "subject": subject,
             "required_count": required,
             "recommended_count": recommended},
            dedupe_key=(f"readinglist:{reading_list.list_id}:"
                        f"student={s.student_id}"),
            kind="reading_list", student=s)
        if res is not None:
            sent += 1
    return sent


def notify_study_booking(booking):
    if not booking.student_id:
        return None
    student = _student(booking.student_id)
    return _deliver(
        "library_study_booking_confirmation",
        {"first_name": getattr(student, "first_name", ""),
         "space": booking.space, "date": booking.date,
         "start_time": booking.start_time, "end_time": booking.end_time,
         "purpose": booking.purpose or "—"},
        dedupe_key=f"studybooking:{booking.booking_id}",
        kind="study_booking", student=student)


# ── Sweeps & digest ───────────────────────────────────────────────

def run_due_soon_sweep(*, as_of: str | None = None) -> int:
    """Send due-soon reminders for loans due within the window."""
    today = _dt.date.fromisoformat(as_of) if as_of else _dt.date.today()
    window = int(_settings.get_setting("due_soon_days"))
    horizon = (today + _dt.timedelta(days=window)).isoformat()
    sent = 0
    for loan in _lib.list_loans(active_only=True):
        if today.isoformat() <= loan.due_on <= horizon:
            if notify_due_soon(loan) is not None:
                sent += 1
    return sent


def run_overdue_sweep() -> int:
    """Send overdue notices for all currently-overdue active loans."""
    sent = 0
    for loan in _lib.list_loans(overdue_only=True):
        if notify_overdue(loan) is not None:
            sent += 1
    return sent


def daily_digest(*, to_address: str | None = None,
                 as_of: str | None = None):
    """Build and send the librarian daily digest (item 19)."""
    from education_system.sixthform_system.modules.domain.academics.library import (
        library_fines as _fines,
        library_reservations as _holds,
    )
    today = as_of or _dt.date.today().isoformat()
    window = int(_settings.get_setting("due_soon_days"))
    horizon = (_dt.date.fromisoformat(today)
               + _dt.timedelta(days=window)).isoformat()
    active = _lib.list_loans(active_only=True)
    due_soon = sum(1 for l in active if today <= l.due_on <= horizon)
    overdue = sum(1 for l in active if l.due_on < today)
    ready = _holds.list_reservations(status="Ready")
    expiring = sum(1 for r in ready
                   if r.expires_on and r.expires_on <= today)
    outstanding = round(sum(
        f.outstanding for f in _fines.list_fines(open_only=True)), 2)

    context = {
        "generated_on": today, "due_soon_days": window,
        "due_soon_count": due_soon, "overdue_count": overdue,
        "ready_count": len(ready), "expiring_count": expiring,
        "outstanding_total": f"{outstanding:.2f}",
    }
    return _send("library_daily_digest", context,
                 to_name="Library Desk",
                 to_address=to_address or DIGEST_INBOX)
