"""Sixth Form bulk operations — communications (messages, SMS, letters,
invites, reminders, password-reset e-mails, scheduled messages).

Split out of ``bulk_operations.py``, which re-exports every name defined here."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.learners.bulk_operations.base import (
    BulkResult,
    ValidationError,
    _log_job,
    _validate_targets,
)

def _send_email_logged(payload: dict) -> None:
    """Log an outgoing e-mail and hand it to the outbox.

    The row is created Queued and sent through ``send_message``, so it
    reads Sent only when a provider accepted it (the platform delivery
    mode decides whether anything leaves). Raises when the row cannot
    be created; a delivery that is held or retried is not an error.
    """
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as _msg,
    )
    msg = _msg.create_message({**payload, "status": "Queued"})
    _msg.send_message(msg.message_id)


# ── Operation: bulk message ───────────────────────────────────────

def bulk_message(
    student_ids: list[str],
    *,
    subject: str,
    body: str,
    channel: str = "Email",
    category: str = "General",
    priority: str = "Normal",
    status: str = "Sent",
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as _msg,
    )
    result = BulkResult(operation="message",
                          target_count=len(targets))
    if dry_run:
        return result
    try:
        sent = _msg.bulk_send(
            subject=subject, body=body,
            student_ids=targets,
            channel=channel, category=category,
            priority=priority, status=status,
        )
        for m in sent.created:
            sid = getattr(m, "student_id", None)
            if sid:
                result.success_ids.append(sid)
        for label, reason in sent.failed:
            result.failures.append((label, reason))
    except Exception as e:
        # Total failure (e.g. messages module rejected payload). Mark
        # all targets as failed so the job log is honest.
        for sid in targets:
            result.failures.append((sid, str(e)))
    summary = (f"Sent {subject!r} to "
               f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="message", summary=summary,
        params={"subject": subject, "channel": channel,
                "category": category, "priority": priority,
                "status": status},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk SMS (messages with channel=SMS) ───────────────

def bulk_send_sms(
    student_ids: list[str],
    *,
    body: str,
    subject: str = "SMS",
    sender_staff_id: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as _msg,
    )
    result = BulkResult(operation="send_sms", target_count=len(targets))
    if dry_run:
        return result
    try:
        sent = _msg.bulk_send(
            subject=subject, body=body,
            student_ids=targets, channel="SMS",
            category="General", priority="Normal", status="Sent",
            sender_staff_id=sender_staff_id,
        )
        for m in sent.created:
            sid = getattr(m, "student_id", None)
            if sid:
                result.success_ids.append(sid)
        for label, reason in sent.failed:
            result.failures.append((label, reason))
    except Exception as e:
        for sid in targets:
            result.failures.append((sid, str(e)))
    summary_text = (f"SMS sent to "
                    f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="send_sms", summary=summary_text,
        params={"subject": subject, "body_preview": body[:80]},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk send templated letters ────────────────────────

def bulk_send_letters(
    student_ids: list[str],
    *,
    template_id: int,
    extra_context: dict[str, str] | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Render a letter template per student and store one Message row
    each (channel='Letter'). Per-student placeholders (student_id,
    full_name) are merged into ``extra_context``."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domains.communications.domain.letter_templates import (
        letter_templates as _lt,
    )
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as _msg,
    )
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    tmpl = _lt.get_template(template_id)
    if tmpl is None:
        raise ValidationError(f"No template with id {template_id}")
    result = BulkResult(operation="send_letters",
                         target_count=len(targets))
    if dry_run:
        return result
    base_ctx = dict(extra_context or {})
    for sid in targets:
        try:
            st = _students.get_student(sid)
            ctx = {**base_ctx,
                   "student_id": sid,
                   "full_name": getattr(st, "full_name", sid) if st else sid,
                   "first_name": getattr(st, "first_name", "") if st else "",
                   "last_name": getattr(st, "last_name", "") if st else ""}
            rendered = _lt.render(tmpl, ctx, track_use=False)
            _msg.create_message({
                "direction":  "Outgoing",
                "channel":    "Letter",
                "category":   "General",
                "priority":   "Normal",
                "status":     "Sent",
                "subject":    rendered.subject or f"Letter ({tmpl.name})",
                "body":       rendered.body,
                "student_id": sid,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Sent template-#{template_id} letter to "
                    f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="send_letters", summary=summary_text,
        params={"template_id": template_id,
                "extra_context": extra_context or {}},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk parents-evening meeting invites ───────────────

def bulk_meeting_invites(
    student_ids: list[str],
    *,
    event_id: int,
    booking_link: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Send a parents-evening invite email to each student's primary
    parent contact. ``booking_link`` is embedded in the body if given."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domains.communications.domain.parents_evenings import (
        parents_evenings as _pe,
    )
    from education_system.systems.sixth_form.domains.communications.domain.parent_contacts import (
        parent_contacts as _pc,
    )
    event = _pe.get_event(event_id)
    if event is None:
        raise ValidationError(f"No parents-evening event #{event_id}")
    result = BulkResult(operation="meeting_invites",
                         target_count=len(targets))
    if dry_run:
        return result
    subject = f"Parents' evening invitation — {event.title}"
    base_body = (
        f"Date: {event.event_date}\n"
        f"Location: {getattr(event, 'location', '') or '—'}\n\n"
        "Please book a slot at your earliest convenience.\n"
    )
    if booking_link:
        base_body += f"\nBooking link: {booking_link}\n"
    for sid in targets:
        try:
            contact = _pc.primary_for_student(sid)
            if contact is None:
                raise ValidationError("No primary parent contact")
            _send_email_logged({
                "direction":  "Outgoing",
                "channel":    "Email",
                "category":   "General",
                "priority":   "Normal",
                "subject":    subject,
                "body":       base_body,
                "to_name":    getattr(contact, "full_name", None),
                "to_address": getattr(contact, "email", None),
                "student_id": sid,
                "parent_contact_id": contact.contact_id,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Sent parents-evening invites for event #{event_id} "
                    f"to {result.success_count}/{result.target_count} "
                    f"families")
    result.job_id = _log_job(
        operation="meeting_invites", summary=summary_text,
        params={"event_id": event_id, "booking_link": booking_link},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk UCAS reference reminders ──────────────────────

def bulk_ucas_reference_reminders(
    student_ids: list[str],
    *,
    referee_email: str | None = None,
    deadline: str | None = None,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Send a reminder email per student to the configured referee
    asking them to complete the UCAS reference."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    result = BulkResult(operation="ucas_reference_reminders",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            st = _students.get_student(sid)
            name = getattr(st, "full_name", sid) if st else sid
            app = _ucas.get_application_for_student(sid) \
                if hasattr(_ucas, "get_application_for_student") else None
            referee = referee_email
            if not referee and app is not None:
                referee = getattr(app, "reference_email", None)
            if not referee:
                raise ValidationError("No referee email available")
            body = (
                f"This is a reminder to complete the UCAS reference "
                f"for {name} ({sid}).\n"
            )
            if deadline:
                body += f"Deadline: {deadline}\n"
            _send_email_logged({
                "direction":  "Outgoing",
                "channel":    "Email",
                "category":   "UCAS",
                "priority":   "High",
                "subject":    f"UCAS reference reminder — {name}",
                "body":       body,
                "to_address": referee,
                "student_id": sid,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Sent UCAS reference reminders for "
                    f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="ucas_reference_reminders", summary=summary_text,
        params={"deadline": deadline,
                "referee_email": referee_email},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk password-reset emails ─────────────────────────

def bulk_password_reset_emails(
    student_ids: list[str],
    *,
    reset_url: str | None = None,
    mfa_enrolment: bool = False,
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Send a password-reset (or MFA enrolment) email to each student."""
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    flow = "MFA enrolment" if mfa_enrolment else "Password reset"
    result = BulkResult(operation="password_reset_emails",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            st = _students.get_student(sid)
            email = getattr(st, "email", None) if st else None
            if not email:
                raise ValidationError("No email on file")
            body = (
                f"Hello,\n\n"
                f"A {flow.lower()} has been initiated for your account.\n"
            )
            if reset_url:
                body += f"\nFollow this link to continue: {reset_url}\n"
            else:
                body += ("\nPlease contact the IT office for the next "
                         "steps.\n")
            _send_email_logged({
                "direction":  "Outgoing",
                "channel":    "Email",
                "category":   "General",
                "priority":   "High",
                "subject":    f"{flow} — action required",
                "body":       body,
                "to_address": email,
                "student_id": sid,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Sent {flow} emails to "
                    f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="password_reset_emails", summary=summary_text,
        params={"reset_url": reset_url, "mfa_enrolment": mfa_enrolment},
        result=result, ran_by=ran_by,
    )
    return result


# ── Operation: bulk schedule message (future send) ────────────────

def bulk_schedule_message(
    student_ids: list[str],
    *,
    subject: str,
    body: str,
    send_at: str,
    channel: str = "Email",
    category: str = "General",
    priority: str = "Normal",
    ran_by: str | None = None,
    dry_run: bool = False,
) -> BulkResult:
    """Queue a message per student to go out at ``send_at``.

    Each row is ``status = 'Queued'`` with ``scheduled_for = send_at``
    and the student's e-mail (or mobile, for SMS) as the address. The
    scheduler's "Send scheduled messages" job hands each one to the
    outbox at or after that time
    (:func:`messages.send_due_scheduled`); until then nothing is sent
    and ``sent_at`` stays empty.
    """
    targets = _validate_targets(student_ids)
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as _msg,
    )
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    when = _msg._validate_datetime(send_at, "Send at")
    if not when:
        raise ValidationError("Send at is required (YYYY-MM-DD HH:MM)")
    result = BulkResult(operation="schedule_message",
                         target_count=len(targets))
    if dry_run:
        return result
    for sid in targets:
        try:
            st = _students.get_student(sid)
            if st is None:
                raise ValidationError("no such student")
            address = (st.phone or "") if channel == "SMS" else st.email
            if channel in ("Email", "SMS") and not address:
                raise ValidationError(
                    "no mobile number on file" if channel == "SMS"
                    else "no e-mail address on file")
            _msg.create_message({
                "direction":  "Outgoing",
                "channel":    channel,
                "category":   category,
                "priority":   priority,
                "status":     "Queued",
                "subject":    subject,
                "body":       body,
                "student_id": sid,
                "to_name":    st.full_name,
                "to_address": address,
                "scheduled_for": when,
            })
            result.success_ids.append(sid)
        except Exception as e:
            result.failures.append((sid, str(e)))
    summary_text = (f"Scheduled {subject!r} for {when} → "
                    f"{result.success_count}/{result.target_count} students")
    result.job_id = _log_job(
        operation="schedule_message", summary=summary_text,
        params={"subject": subject, "send_at": when,
                "channel": channel, "category": category,
                "priority": priority},
        result=result, ran_by=ran_by,
    )
    return result
