"""Self-service kiosk data (item 50).

Read-only, student-facing helpers: search the catalogue and look up
your own loans, fines and reservations. There are no mutating
operations here — the CLI/GUI kiosk surfaces wrap these so a student at
a shared terminal can't change anything.
"""

from __future__ import annotations

from education_system.post_16.sixthform_system.modules.domain.academics.library import (
    library as _lib,
    library_fines as _fines,
    library_reservations as _holds,
)


def search(query: str | None = None, *,
           available_only: bool = False) -> list["_lib.Book"]:
    """Catalogue search for the kiosk."""
    return _lib.list_books(search=(query or None),
                           available_only=available_only)


def student_summary(student_id: str) -> dict:
    """A student's own active loans, open fines and reservations."""
    _lib.init_db()
    from education_system.post_16.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    student = _students.get_student(student_id)
    if student is None:
        raise _lib.ValidationError(f"No student with id {student_id}")

    titles = {b.book_id: b.title for b in _lib.list_books()}
    loans = []
    for l in _lib.list_loans(student_id=student_id, active_only=True):
        loans.append({"loan_id": l.loan_id,
                      "title": titles.get(l.book_id, f"#{l.book_id}"),
                      "due_on": l.due_on,
                      "overdue": l.is_overdue,
                      "renewals": l.renewals_count})
    open_fines = _fines.list_fines(student_id=student_id,
                                   open_only=True)
    reservations = []
    for r in _holds.list_reservations(student_id=student_id,
                                      open_only=True):
        pos = _holds.waitlist_position(r.reservation_id)
        reservations.append(
            {"reservation_id": r.reservation_id,
             "title": titles.get(r.book_id, f"#{r.book_id}"),
             "status": r.status, "queue_position": pos or None,
             "collect_by": r.expires_on})

    return {
        "student_id": student.student_id,
        "name": student.full_name,
        "loans": loans,
        "fines": [{"fine_id": f.fine_id, "reason": f.reason,
                   "outstanding": f.outstanding} for f in open_fines],
        "balance": round(sum(f.outstanding for f in open_fines), 2),
        "reservations": reservations,
    }
