"""The Disability & Accessibility portal's operations (GUI and CLI).

Every function takes the signed-in ``actor`` first (see :mod:`.access`),
checks it, and raises ``PermissionError`` / ``ValueError`` with a message
the screen can show as it is. A student acts on their own student number
(never the account id); staff work the whole queue.

Decisions and staff replies land in the student's Notifications Hub inbox
(``messages``) with the change that caused them. Staff opening a request
is a view of special-category data, so it is written to the audit log first
and refused if that fails (as the health portal does).
"""

from __future__ import annotations

from datetime import datetime

from education_system.systems.university.domains.student_support.domain.disability import access
from education_system.systems.university.domains.student_support.domain.disability.accessibility_service import (
    AccessibilityService,
)
from education_system.systems.university.infrastructure.database.db import get_connection

ACCOMMODATION_TYPES = tuple(AccessibilityService.ACCOMMODATION_TYPES)
OPEN_STATUSES = (AccessibilityService.STATUS_SUBMITTED, AccessibilityService.STATUS_UNDER_REVIEW,
                 "pending")
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024

_service: AccessibilityService | None = None


def service() -> AccessibilityService:
    """One service per process (its constructor runs the table DDL)."""
    global _service
    if _service is None:
        _service = AccessibilityService()
    return _service


def _me(actor) -> str:
    sid = access.own_student_id(actor)
    if not sid:
        raise PermissionError("These pages are for students; your account has no student record.")
    return sid


def _request(request_id) -> dict:
    req = service().get_request_details(int(request_id))
    if not req:
        raise ValueError(f"Request #{request_id} was not found.")
    return req


def _notify(student_id, subject, body) -> None:
    """An unread inbox message for the student (never breaks the caller)."""
    from education_system.systems.university.infrastructure.email.messages_inbox import (
        deliver_inbox_message,
    )
    deliver_inbox_message(str(student_id), subject, body)


def _record_view(actor, student_id, request_id) -> None:
    from education_system.systems.university.domains.health.application.health import (
        access as health_access,
    )
    person = access.who(actor)
    if person is None:
        raise PermissionError("Sign in to use disability and accessibility services.")
    health_access.record_view(person, "accommodation_request", student_id=student_id,
                              record_id=request_id)


# ------------------------------------------------------------------ students

def my_student_id(actor) -> str:
    return _me(actor)


def my_contact(actor) -> tuple[str, str]:
    """``(name, email)`` from the student's record, for the request form."""
    sid = _me(actor)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')), "
            "email_address FROM students WHERE student_id = ?", (sid,)).fetchone()
    return (row[0] or "", row[1] or "") if row else ("", "")


def submit_request(actor, accommodation_type, description, *, contact_name=None,
                   contact_email=None) -> int:
    """A new request from the signed-in student. The contact name/e-mail
    default to their record."""
    sid = _me(actor)
    description = (description or "").strip()
    if accommodation_type not in ACCOMMODATION_TYPES:
        raise ValueError("Choose a type of adjustment.")
    if len(description) < 10:
        raise ValueError("Describe what you need (at least a sentence).")
    name, email = my_contact(actor)
    name = (contact_name or "").strip() or name or access.username(actor)
    email = (contact_email or "").strip() or email
    if email and "@" not in email:
        raise ValueError("That e-mail address doesn't look right.")
    return service().submit_accommodation_request(sid, name, email or "", accommodation_type,
                                                  description)


def my_requests(actor) -> list[dict]:
    return service().get_student_requests(_me(actor))


def my_accommodations(actor) -> list[dict]:
    return service().get_active_accommodations(_me(actor))


def my_expiring(actor, days=30) -> list[dict]:
    return service().get_expiring_accommodations(_me(actor), days_threshold=days)


def my_renewals(actor) -> list[dict]:
    return service().get_renewal_requests(_me(actor))


def my_faculty_notifications(actor) -> list[dict]:
    return service().get_faculty_notifications(_me(actor))


def upload_document(actor, request_id, filename, content: bytes,
                    document_type="Medical Documentation") -> int:
    req = _request(request_id)
    access.require_student(actor, req["student_id"])
    if not content:
        raise ValueError("That file is empty.")
    if len(content) > MAX_DOCUMENT_BYTES:
        raise ValueError("Files must be 10 MB or smaller.")
    return service().upload_documentation(int(request_id), str(req["student_id"]), filename,
                                          content, document_type)


def request_renewal(actor, accommodation_id, notes=None) -> int:
    sid = _me(actor)
    acc = service().get_accommodation(int(accommodation_id))
    if not acc or str(acc.get("student_id")) != sid:
        raise PermissionError("That accommodation belongs to another student.")
    if str(acc.get("status") or "").lower() != "active":
        raise ValueError("Only an active accommodation can be renewed.")
    if any(r["accommodation_id"] == acc["id"] and r["status"] == "Pending"
           for r in service().get_renewal_requests(sid)):
        raise ValueError("A renewal for this accommodation is already waiting.")
    return service().request_renewal(int(accommodation_id), sid, (notes or "").strip() or None)


# ------------------------------------------------------------- both sides

def messages(actor, request_id) -> list[dict]:
    """The request's conversation. Opening it marks the other side's
    messages read."""
    req = _request(request_id)
    access.require_student(actor, req["student_id"])
    staff = access.scope(actor) is None
    if staff:
        _record_view(actor, req["student_id"], req["request_id"])
    rows = service().get_messages(int(request_id))
    unread_from = "student" if staff else "staff"
    for m in rows:
        if m.get("sender_type") == unread_from and not m.get("is_read"):
            service().mark_message_as_read(m["message_id"])
    return rows


def send_message(actor, request_id, text) -> int:
    req = _request(request_id)
    access.require_student(actor, req["student_id"])
    text = (text or "").strip()
    if not text:
        raise ValueError("Write a message first.")
    staff = access.scope(actor) is None
    mid = service().send_message(int(request_id), access.username(actor),
                                 "staff" if staff else "student", text)
    if staff:
        _notify(req["student_id"], f"Disability services replied about request #{request_id}",
                f"{text}\n\nReply from Disability & Accessibility Services → Messages.")
    return mid


# -------------------------------------------------------------------- staff

def queue(actor, *, include_closed=False) -> list[dict]:
    access.require_staff(actor)
    return service().list_requests(None if include_closed else list(OPEN_STATUSES))


def request_detail(actor, request_id) -> dict:
    """The full request and its documents (an audited view)."""
    access.require_staff(actor)
    req = _request(request_id)
    _record_view(actor, req["student_id"], req["request_id"])
    req["documents"] = service().get_documentation(int(request_id))
    return req


def document_path(actor, request_id, doc_id) -> str:
    access.require_staff(actor)
    for doc in service().get_documentation(int(request_id)):
        if int(doc["doc_id"]) == int(doc_id):
            return doc["file_path"]
    raise ValueError("That document is not on this request.")


def _require_open(req) -> None:
    if req["status"] not in OPEN_STATUSES:
        raise ValueError(f"Request #{req['request_id']} is already {req['status']}.")


def mark_under_review(actor, request_id) -> None:
    access.require_decider(actor)
    req = _request(request_id)
    _require_open(req)
    service().update_request_status(int(request_id), AccessibilityService.STATUS_UNDER_REVIEW,
                                    access.username(actor), req.get("reviewer_notes"))
    _notify(req["student_id"], f"Your request #{request_id} is being reviewed",
            f"Disability services are reviewing your {req['accommodation_type']} request.")


def approve(actor, request_id, *, start_date=None, months=12, notes=None) -> int:
    access.require_decider(actor)
    req = _request(request_id)
    _require_open(req)
    if start_date:
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Use YYYY-MM-DD for the start date.") from None
    months = int(months)
    if not 1 <= months <= 60:
        raise ValueError("The adjustment lasts between 1 and 60 months.")
    acc_id = service().approve_and_activate_accommodation(
        int(request_id), access.username(actor), start_date=start_date, duration_months=months)
    if notes:
        with get_connection() as conn:
            conn.execute("UPDATE accommodation_requests SET reviewer_notes = ? "
                         "WHERE request_id = ?", (notes.strip(), int(request_id)))
            conn.commit()
    acc = service().get_accommodation(acc_id) or {}
    _notify(req["student_id"], f"Your {req['accommodation_type']} adjustment was approved",
            f"Request #{request_id} was approved and is active from {acc.get('start_date')} "
            f"until {acc.get('end_date')}." + (f"\n\n{notes.strip()}" if notes else ""))
    return acc_id


def deny(actor, request_id, reason) -> None:
    access.require_decider(actor)
    req = _request(request_id)
    _require_open(req)
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValueError("Give the student a reason.")
    service().update_request_status(int(request_id), AccessibilityService.STATUS_DENIED,
                                    access.username(actor), reason)
    _notify(req["student_id"], f"Your {req['accommodation_type']} request was not approved",
            f"Request #{request_id} was not approved.\n\nReason: {reason}\n\n"
            "You can reply from Disability & Accessibility Services → Messages.")


def pending_renewals(actor) -> list[dict]:
    access.require_staff(actor)
    return service().get_pending_renewals()


def decide_renewal(actor, renewal_id, approve_it: bool, notes=None, months=12) -> None:
    access.require_decider(actor)
    ren = service().get_renewal(int(renewal_id))
    if not ren:
        raise ValueError(f"Renewal #{renewal_id} was not found.")
    if ren["status"] != "Pending":
        raise ValueError(f"Renewal #{renewal_id} is already {ren['status']}.")
    notes = (notes or "").strip() or None
    if not approve_it and not notes:
        raise ValueError("Give the student a reason.")
    service().process_renewal(int(renewal_id), "Approved" if approve_it else "Denied",
                              access.username(actor), notes, extend_months=int(months))
    acc = service().get_accommodation(ren["accommodation_id"]) or {}
    if approve_it:
        _notify(ren["student_id"], "Your adjustment was renewed",
                f"Your {acc.get('accommodation_type')} adjustment now runs until "
                f"{acc.get('end_date')}." + (f"\n\n{notes}" if notes else ""))
    else:
        _notify(ren["student_id"], "Your renewal was not approved",
                f"The renewal of your {acc.get('accommodation_type')} adjustment was not "
                f"approved.\n\nReason: {notes}")


def statistics(actor) -> dict:
    access.require_staff(actor)
    return service().get_statistics()


# ------------------------------------------------------------- disabilities

#: The categories a disability is recorded under (UK, HESA-style), key → label.
DISABILITY_CATEGORIES = {
    "learning": "Learning difference (e.g. dyslexia, dyspraxia, ADHD)",
    "social_communication": "Social or communication condition (e.g. autism)",
    "long_term_illness": "Long-term illness or health condition",
    "mental_health": "Mental health condition",
    "physical": "Physical impairment or mobility issue",
    "hearing": "Deaf or serious hearing impairment",
    "visual": "Blind or serious visual impairment",
    "development": "Development condition (e.g. speech and language)",
    "other": "Another disability or condition",
}
MAX_DETAILS = 2000


def clean_disabilities(items) -> list[dict]:
    """Check what was entered — ``[{'category', 'details', 'adjustment_type'}]``
    — and return it tidied. Raises ValueError naming the first problem."""
    cleaned = []
    for n, item in enumerate(items or [], 1):
        category = str(item.get("category") or "")
        if category not in DISABILITY_CATEGORIES:
            raise ValueError(f"Disability {n}: choose a category.")
        details = str(item.get("details") or "").strip()
        if len(details) > MAX_DETAILS:
            raise ValueError(f"Disability {n}: keep the details under {MAX_DETAILS} characters.")
        adjustment = str(item.get("adjustment_type") or "").strip() or None
        if adjustment and adjustment not in ACCOMMODATION_TYPES:
            raise ValueError(f"Disability {n}: choose an adjustment from the list.")
        if adjustment and len(details) < 10:
            raise ValueError(f"Disability {n}: describe what is needed so disability services "
                             "can consider the adjustment.")
        cleaned.append({"category": category, "details": details,
                        "adjustment_type": adjustment})
    return cleaned


def _may_record_at_enrolment(actor) -> bool:
    return access.scope(actor) is None or access.has_permission(actor, "create_student")


def _add_rows(actor, student_id, items, source) -> dict:
    """Insert the disabilities; raise a request for each adjustment asked for."""
    from education_system.systems.university.domains.health.application.health import (
        sealed_fields,
    )
    service()   # tables exist
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        row = conn.execute(
            "SELECT TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')), "
            "email_address FROM students WHERE student_id = ?", (str(student_id),)).fetchone()
    if not row:
        raise ValueError(f"There is no student {student_id}.")
    name, email = row[0] or str(student_id), row[1] or ""
    # Seal everything first: if the key can't be used, nothing is written
    # (no adjustment request left without its disability record).
    sealed = [sealed_fields.seal_value("student_disabilities", "details", item["details"])
              for item in items]
    ids, requests = [], []
    for item, details in zip(items, sealed):
        request_id = None
        if item["adjustment_type"]:
            request_id = service().submit_accommodation_request(
                str(student_id), name, email, item["adjustment_type"],
                f"{DISABILITY_CATEGORIES[item['category']]}: {item['details']}")
            requests.append(request_id)
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO student_disabilities (student_id, category, details, "
                "adjustment_type, adjustment_request_id, source, status, declared_by, "
                "declared_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)",
                (str(student_id), item["category"], details, item["adjustment_type"], request_id, source, access.username(actor), now, now))
            ids.append(cur.lastrowid)
            conn.commit()
    return {"disabilities": ids, "requests": requests}


def record_at_enrolment(actor, student_id, items) -> dict:
    """The disabilities entered on Create Student, for the student just
    created. Anyone who may create students may record them; an adjustment
    asked for becomes a request in disability services' queue (Submitted),
    not an approved adjustment. Returns ``{'disabilities', 'requests'}``."""
    if not _may_record_at_enrolment(actor):
        raise PermissionError("Only staff who create students or disability services can "
                              "record a student's disabilities.")
    return _add_rows(actor, student_id, clean_disabilities(items), "enrolment")


def add_disabilities(actor, student_id, items) -> dict:
    """Disability services adding to any student's record, or a student
    telling us about their own."""
    access.require_student(actor, student_id)
    source = "staff" if access.scope(actor) is None else "student"
    return _add_rows(actor, student_id, clean_disabilities(items), source)


def list_disabilities(actor, student_id) -> list[dict]:
    """A student's disabilities (active), details unsealed. Staff looking at
    a student's record is audited first (fails closed)."""
    from education_system.systems.university.domains.health.application.health import (
        sealed_fields,
    )
    access.require_student(actor, student_id)
    service()
    if access.scope(actor) is None:
        _record_view(actor, student_id, None)
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT id, student_id, category, details, adjustment_type, adjustment_request_id, "
            "source, declared_by, declared_at FROM student_disabilities "
            "WHERE student_id = ? AND status = 'active' ORDER BY declared_at, id",
            (str(student_id),))
        cols = [d[0] for d in cursor.description]
        rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
    for r in rows:
        r["details"] = sealed_fields.reveal(r["details"])
        r["category_label"] = DISABILITY_CATEGORIES.get(r["category"], r["category"])
    return rows


def my_disabilities(actor) -> list[dict]:
    return list_disabilities(actor, _me(actor))


def remove_disability(actor, disability_id, reason) -> None:
    """Disability services only; the row is kept, marked removed."""
    access.require_staff(actor)
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValueError("Say why it is being removed.")
    with get_connection() as conn:
        n = conn.execute(
            "UPDATE student_disabilities SET status = 'removed', updated_at = ? "
            "WHERE id = ? AND status = 'active'",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), int(disability_id))).rowcount
        conn.commit()
    if not n:
        raise ValueError("That disability is not on the student's record.")
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    log_activity("delete", "student_disability", disability_id=int(disability_id),
                 details={"reason": reason, "by": access.username(actor)})
