"""Ports student wellbeing casework uses to reach other university domains.

Counselling, DSA, PEEPs, Support to Study and trusted contacts live in the
Student Support slice, which may not import another domain directly (the
slice boundary ratchet). What they need from elsewhere goes through here:

* **health access** (``health.application.health.access``, frozen API):
  :func:`health_user`, :func:`counselling_scope` (``scope_area`` for the
  counselling practitioners) and :func:`record_view` (the immutable audit
  log; raises ``PermissionError`` when the entry cannot be written, so an
  unrecorded look never happens);
* **sealing** of free-text clinical notes (:func:`seal` / :func:`unseal_rows`,
  ``health.application.health.sealed_fields``);
* **the crisis pathway**: :func:`raise_crisis_concern` — a CRITICAL concern in
  the safeguarding register, the same call a crisis support ticket makes
  (``support_referrals_bus.raise_safeguarding_concern``);
* **the student lifecycle**: :func:`interrupt_studies` —
  ``learners.domain.student_lifecycle.change_status(..., 'interrupt')``, the
  one way a student's status changes (history row, module moves, the
  ``enrolment.changed`` event to finance / visa / library);
* **reasonable adjustments → exams**: :func:`add_adjustment` /
  :func:`withdraw_adjustment` (``accommodation_bus``), which write the
  ``accommodations`` row and let ``reconcile`` carry it to exam
  accommodations, the register and extensions.

Each call opens its own connection and commits there: callers must not hold
a write transaction on the university database while calling (except where
a ``conn`` argument is taken).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── health access (read-only use of the frozen API) ─────────────────────

def _health_access():
    from education_system.systems.university.domains.health.application.health import access
    return access


def health_user(current_user: Optional[dict]):
    """``HealthUser`` for a ``current_user`` dict (``None`` if not signed in)."""
    return _health_access().from_user(current_user)


def counselling_scope(who) -> Optional[str]:
    """``None`` = the whole counselling caseload (counsellors, clinicians,
    administrators); a student number = only that student; raises
    ``PermissionError`` for anyone else."""
    return _health_access().scope_area(who, "counselling")


def counselling_roles() -> tuple:
    return tuple(_health_access().AREA_ROLES.get("counselling", ()))


def wellbeing_roles() -> tuple:
    return tuple(_health_access().AREA_ROLES.get("wellbeing", ()))


def clinical_roles() -> tuple:
    access = _health_access()
    return tuple(access.CLINICAL_ROLES) + tuple(access.ADMIN_ROLES)


def admin_roles() -> tuple:
    return tuple(_health_access().ADMIN_ROLES)


def record_view(who, area: str, *, student_id=None, record_id=None,
                reason: Optional[str] = None) -> None:
    """Write a view of special-category data to the immutable audit log, or
    raise ``PermissionError`` (fail closed)."""
    _health_access().record_view(who, area, student_id=student_id, record_id=record_id,
                                 reason=reason)


# ── sealing ─────────────────────────────────────────────────────────────

def seal(table: str, column: str, value):
    """Seal a free-text value at rest (``table`` / ``column`` must be listed in
    ``sealed_fields.SEALED``; anything else passes through unchanged)."""
    from education_system.systems.university.domains.health.application.health import (
        sealed_fields,
    )
    return sealed_fields.seal_value(table, column, value)


def seal_text(value):
    """Seal a value regardless of the table it goes to (confidential notes
    in tables ``sealed_fields`` does not list)."""
    from education_system.systems.university.domains.health.application.health import (
        sealed_fields,
    )
    return sealed_fields.seal_value("health_records", "description", value, confidential=True)


def reveal(value):
    from education_system.systems.university.domains.health.application.health import (
        sealed_fields,
    )
    return sealed_fields.reveal(value)


def unseal_rows(rows) -> list[dict]:
    from education_system.systems.university.domains.health.application.health import (
        sealed_fields,
    )
    return sealed_fields.unseal_rows(rows)


# ── crisis pathway ──────────────────────────────────────────────────────

def safeguarding_lead_roles() -> frozenset:
    from education_system.systems.university.services.bus import support_referrals_bus
    return support_referrals_bus.safeguarding_lead_roles()


def raise_crisis_concern(subject: dict, content: str, *, snippet: str = "",
                         reporter_username: Optional[str] = None) -> int:
    """A CRITICAL self-harm / mental-health concern about ``subject``
    (``{'username', 'full_name', 'role'}``) in the safeguarding register;
    returns its id."""
    from education_system.systems.university.services.bus import support_referrals_bus
    return support_referrals_bus.raise_safeguarding_concern(
        subject, content, snippet=snippet, reporter_username=reporter_username)


# ── student lifecycle ───────────────────────────────────────────────────

def student_status(student_id: str) -> Optional[str]:
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection(row_factory=False)
    try:
        row = conn.execute("SELECT status FROM students WHERE student_id = ?",
                           (str(student_id),)).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def interrupt_studies(student_id: str, *, actor_id: str, reason: str,
                      effective_date: Optional[str] = None,
                      expected_return_date: Optional[str] = None) -> int:
    """Interrupt a student's studies through the lifecycle (never by writing
    ``students.status``); returns the lifecycle history id. Raises the
    lifecycle's ``EnrolmentBoundaryError`` (a ``ValueError``-like domain
    error) when the student cannot be interrupted from their status."""
    from education_system.systems.university.domains.learners.domain import student_lifecycle
    return int(student_lifecycle.change_status(
        str(student_id), "interrupt", actor_id=actor_id, reason=reason,
        effective_date=effective_date, expected_return_date=expected_return_date))


# ── reasonable adjustments / exam access arrangements ───────────────────

def add_adjustment(student_id: str, accommodation_type: str, description: str, *,
                   approved_by: str, start_date: Optional[str] = None,
                   end_date: Optional[str] = None, notes: Optional[str] = None) -> int:
    """An approved adjustment, carried to exams/register/extensions."""
    from education_system.systems.university.services.bus import accommodation_bus
    return accommodation_bus.add_approved(
        student_id, accommodation_type, description, approved_by=approved_by,
        start_date=start_date, end_date=end_date, notes=notes)


def withdraw_adjustment(accommodation_id: int, *, reason: str, by: str) -> bool:
    from education_system.systems.university.services.bus import accommodation_bus
    return accommodation_bus.withdraw(accommodation_id, reason=reason, by=by)


def describe_exam_arrangements(*, extra_percent: int = 0, separate_room: bool = False,
                               reader: bool = False, scribe: bool = False,
                               assistive_technology: str = "", rest_breaks: bool = False,
                               other: str = "") -> str:
    from education_system.systems.university.services.bus import accommodation_bus
    return accommodation_bus.exam_arrangement_text(
        extra_percent=extra_percent, separate_room=separate_room, reader=reader,
        scribe=scribe, assistive_technology=assistive_technology, rest_breaks=rest_breaks,
        other=other)


def student_adjustments(student_id: str) -> list[dict]:
    """Every ``accommodations`` row for the student (newest first)."""
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT id, accommodation_type, description, start_date, end_date, status, "
            "approved_by FROM accommodations WHERE student_id = ? ORDER BY id DESC",
            (str(student_id),))]
    except Exception:
        logger.debug("accommodations not readable", exc_info=True)
        return []
    finally:
        conn.close()


# ── notices ─────────────────────────────────────────────────────────────

def notify_inbox(recipient_ref, subject: str, body: str) -> None:
    """An unread Notifications Hub message (never breaks the caller)."""
    try:
        from education_system.systems.university.infrastructure.email.messages_inbox import (
            deliver_inbox_message,
        )
        deliver_inbox_message(str(recipient_ref), subject, body)
    except Exception:
        logger.debug("inbox notice failed", exc_info=True)


def send_email(address: str, subject: str, body: str) -> None:
    """Through the university outbox (never breaks the caller)."""
    if not address:
        return
    try:
        from education_system.systems.university.infrastructure.email.email_service.core import (
            send_email as _send,
        )
        _send(address, subject, body)
    except Exception:
        logger.debug("outbox e-mail to %s failed", address, exc_info=True)


__all__: list[Any] = [
    "health_user", "counselling_scope", "counselling_roles", "wellbeing_roles",
    "clinical_roles", "admin_roles", "record_view", "seal", "seal_text", "reveal",
    "unseal_rows", "safeguarding_lead_roles", "raise_crisis_concern", "student_status",
    "interrupt_studies", "add_adjustment", "withdraw_adjustment",
    "describe_exam_arrangements", "student_adjustments", "notify_inbox", "send_email",
]
