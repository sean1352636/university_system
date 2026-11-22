"""The sixth form's side of the university UCAS link, on the bus.

The university no longer writes this system's ``ucas_choices`` rows. It
records a decision or an enrolment in its own tables and publishes an
event; the handlers here apply it to the sixth form's own row:

``ucas.decision.recorded``
    The decision, offer summary, structured conditions and reply-by date
    land on the choice, with who decided and when. The learner and their
    tutor are told through the sixth form's own messaging.

``university.student.enrolled``
    The choice is marked *Placed* (never deleted), so the record of where
    the learner went survives and the university's applicant list stops
    showing them.

Both handlers are idempotent — the bus may redeliver — and neither raises
for a learner or choice this system does not hold.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.platform.integrations.external import cross_system_bus
from education_system.systems.sixth_form.domain.progression.university import (
    ucas as _ucas,
)

logger = logging.getLogger(__name__)

EVENT_DECISION_RECORDED = "ucas.decision.recorded"
EVENT_STUDENT_ENROLLED = "university.student.enrolled"

DECISION_HANDLER = "sixth_form.ucas.apply_university_decision"
ENROLLED_HANDLER = "sixth_form.ucas.mark_choice_placed"

#: Decisions a learner hears about. A withdrawal is normally the learner's
#: own doing, so it is applied silently.
_NOTIFY = ("Conditional Offer", "Unconditional Offer", "Rejected")


def _payload(envelope: dict) -> dict[str, Any]:
    payload = envelope.get("payload") if isinstance(envelope, dict) else None
    return payload if isinstance(payload, dict) else {}


# ── Decisions ──────────────────────────────────────────────────────

def handle_decision_recorded(envelope: dict) -> None:
    """Apply a university decision to our choice row, then notify."""
    payload = _payload(envelope)
    choice, changed = _ucas.apply_university_decision(payload)
    if choice is None or not changed:
        return
    # A declined Firm (or a changed Insurance) can move where an already
    # handed-over learner is going; a no-op for anyone not yet handed over.
    _reroute(choice.application_id)
    if choice.decision_status not in _NOTIFY:
        return
    try:
        _notify_decision(choice, payload)
    except Exception:
        # The decision is on the row; a messaging failure must not make
        # the bus retry (and re-apply) it.
        logger.exception("Could not notify about the decision on UCAS "
                         "choice #%d", choice.choice_id)


def _decision_text(choice, payload: dict[str, Any]) -> tuple[str, str]:
    status = choice.decision_status
    lines = [f"{choice.university} has recorded a decision on your UCAS "
             f"choice {choice.course_name}"
             + (f" ({choice.course_code})" if choice.course_code else "")
             + f": {status}."]
    if choice.offer_terms:
        lines.append(f"Offer: {choice.offer_terms}")
    conditions = payload.get("conditions")
    if isinstance(conditions, list) and conditions:
        lines.append("Conditions:")
        for c in conditions:
            if isinstance(c, dict) and c.get("kind"):
                from education_system.platform.cross_system import (
                    offer_conditions as _oc,
                )
                text = _oc.describe(c)
            elif isinstance(c, dict):
                text = (c.get("description") or c.get("text")
                        or ", ".join(f"{k}: {v}" for k, v in c.items()))
            else:
                text = str(c)
            lines.append(f"  - {text}")
    if choice.reply_by:
        lines.append(f"Reply by: {choice.reply_by}")
    if status in ("Conditional Offer", "Unconditional Offer"):
        lines.append("Talk to your tutor about your reply (Firm / "
                     "Insurance / Decline).")
    subject = f"UCAS: {status} from {choice.university}"
    return subject, "\n".join(lines)


def _notify_decision(choice, payload: dict[str, Any]) -> None:
    application = _ucas.get_application(choice.application_id)
    if application is None:
        return
    subject, body = _decision_text(choice, payload)
    # In the learner's portal rather than by e-mail: the university's own
    # offer / rejection e-mail already reaches them, and two e-mails about
    # one decision read as two decisions.
    notify_learner(application.student_id, subject=subject, body=body,
                   sender=choice.university, channel="Portal")
    notify_tutor(application.student_id, subject=subject,
                 body=f"For your tutee {application.student_id}:\n\n{body}")


# ── Enrolments ─────────────────────────────────────────────────────

def handle_student_enrolled(envelope: dict) -> None:
    """Mark the choice the university enrolled the learner on as Placed."""
    payload = _payload(envelope)
    choice_id = payload.get("sf_choice_id")
    if choice_id in (None, ""):
        return
    try:
        choice_id = int(choice_id)
    except (TypeError, ValueError):
        logger.warning("Enrolment event with unusable sf_choice_id %r",
                       payload.get("sf_choice_id"))
        return
    choice, _changed = _ucas.mark_placed(
        choice_id,
        university_student_id=payload.get("university_student_id"),
        placed_at=payload.get("enrolled_on"))
    if choice is None:
        logger.info("Enrolment event for unknown UCAS choice #%d skipped",
                    choice_id)


# ── Messaging ──────────────────────────────────────────────────────

def _reroute(application_id: int) -> None:
    """Best-effort handover reroute; never fails the bus delivery."""
    try:
        from education_system.systems.sixth_form.domain.progression import (
            university_handover,
        )
        university_handover.reroute_for_ucas_application(application_id)
    except Exception:
        logger.exception("Could not re-check the university handover for "
                         "application #%s", application_id)


def notify_learner(student_id: str, *, subject: str, body: str,
                   sender: str | None = None, channel: str = "Email") -> bool:
    """Message a learner through the sixth form's outbox. False if unknown."""
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as _messages,
    )
    if not student_id or _students.get_student(str(student_id)) is None:
        return False
    result = _messages.bulk_send(
        subject=subject[:200], body=body, student_ids=[str(student_id)],
        channel=channel, category="UCAS", from_name=sender or None,
        tags="ucas")
    return bool(result.created)


def _tutor_staff_id(student_id: str) -> str | None:
    """The learner's tutor as a staff id. The tutor-group field holds a
    staff id or a name; a name resolves only when exactly one member of
    staff carries it."""
    try:
        from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
            tutor_groups as _tg,
        )
        from education_system.systems.sixth_form.domain.staff import (
            staff as _staff,
        )
    except Exception:
        return None
    group = _tg.group_for_student(student_id)
    tutor = (group.tutor or "").strip() if group else ""
    if not tutor:
        return None
    if _staff.get_staff(tutor) is not None:
        return tutor
    matches = [s for s in _staff.search_staff(tutor)
               if s.full_name.strip().lower() == tutor.lower()]
    return matches[0].staff_id if len(matches) == 1 else None


def notify_tutor(student_id: str, *, subject: str, body: str) -> bool:
    """Message the learner's tutor, when one can be identified."""
    staff_id = _tutor_staff_id(str(student_id))
    if not staff_id:
        logger.info("No tutor on record for %s; UCAS notice not copied",
                    student_id)
        return False
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as _messages,
    )
    result = _messages.bulk_send(
        subject=subject[:200], body=body, staff_ids=[staff_id],
        channel="Email", category="UCAS", tags="ucas,tutor")
    return bool(result.created)


# ── Registration ───────────────────────────────────────────────────

_registered = False


def register_consumers() -> None:
    """Subscribe both handlers. Idempotent; called by the bus bootstrap."""
    global _registered
    if _registered:
        return
    cross_system_bus.subscribe(EVENT_DECISION_RECORDED,
                               handle_decision_recorded,
                               handler_name=DECISION_HANDLER)
    cross_system_bus.subscribe(EVENT_STUDENT_ENROLLED,
                               handle_student_enrolled,
                               handler_name=ENROLLED_HANDLER)
    _registered = True


__all__ = [
    "EVENT_DECISION_RECORDED",
    "EVENT_STUDENT_ENROLLED",
    "handle_decision_recorded",
    "handle_student_enrolled",
    "notify_learner",
    "notify_tutor",
    "register_consumers",
]
