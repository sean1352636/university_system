"""Admissions e-mail: letters and notices actually sent through the outbox.

Everything here goes through the sixth form messages log
(``domains/communications/domain/messages``): a message row is created
and handed to :func:`messages.send_message`, which delivers it through
the outbox and obeys the platform e-mail delivery mode
(``inbox_only`` / ``sandbox`` / ``live``). Nothing is "previewed and
forgotten" — what was queued, to whom, and what the outbox did with it
is returned so a screen can say honestly "Queued (held by delivery
mode)" rather than "Sent".

* Applicant mail needs the ``admissions`` capability only — it is part of
  running admissions, not a general mail-out.
* Parents/carers who receive correspondence
  (:func:`applicant_details.correspondence_contacts`) get their own copy
  when ``include_parents`` is set.
* Every send goes on the applicant timeline (who sent what to whom, and
  the delivery state) and into ``admissions_messages`` — the link from
  an applicant to the message ids, read by :func:`communications_log`.
* A recipient without an e-mail address is refused with a clear
  :class:`ValidationError`; nothing is queued for nobody.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.domain.admissions import _guard
from education_system.systems.sixth_form.domain.admissions import (
    admissions as _adm,
)

logger = logging.getLogger(__name__)

ValidationError = _adm.ValidationError

#: Message category in the messages log.
CATEGORY: str = "Admissions"

#: What kind of admissions message each link row records.
KINDS: tuple[str, ...] = (
    "custom", "status", "offer-letter", "offer-expiry", "interview-invite",
    "application-received", "reference-request", "reference-chase",
    "portal-code", "contact-change",
)

#: Recipient roles on a link row.
ROLES: tuple[str, ...] = ("applicant", "parent", "referee")

#: How long after an expiry warning before another is sent for the same
#: offer by :func:`send_expiry_warnings`.
EXPIRY_WARNING_GAP_DAYS: int = 3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS admissions_messages (
    link_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id   TEXT NOT NULL,
    message_id     INTEGER NOT NULL,
    kind           TEXT NOT NULL,
    recipient_role TEXT NOT NULL DEFAULT 'applicant',
    to_address     TEXT,
    to_name        TEXT,
    reference_id   INTEGER,
    sent_by        TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (applicant_id) REFERENCES admissions_applicants(applicant_id)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_adm_msg_aid ON admissions_messages(applicant_id);
CREATE INDEX IF NOT EXISTS idx_adm_msg_mid ON admissions_messages(message_id);
"""


@dataclass
class QueuedMessage:
    """One message handed to the outbox."""
    message_id: int
    kind: str
    recipient_role: str
    to_name: str | None
    to_address: str
    subject: str
    message_status: str          # messages-log status (Queued / Sent / Failed)
    delivery_state: str | None   # outbox state (Held / Sandbox / Sent / …)
    delivery_detail: str | None

    @property
    def label(self) -> str:
        """Honest one-line status for a screen."""
        state = self.delivery_state
        if state == "Held":
            return "Queued (held by delivery mode)"
        if state == "Sandbox":
            return "Written to the e-mail sandbox (not sent)"
        if state == "Retrying":
            return "Queued (retrying after a failed attempt)"
        if state == "Sent" or self.message_status == "Sent":
            return "Sent"
        if state == "Failed" or self.message_status == "Failed":
            return "Failed" + (f": {self.delivery_detail}"
                               if self.delivery_detail else "")
        return state or self.message_status


# ── Plumbing ───────────────────────────────────────────────────────

def _messages():
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages,
    )
    return messages


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    _adm.init_db()
    with _adm._connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _DB_READY = True


def _applicant(applicant_id: str) -> _adm.Applicant:
    a = _adm.get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    if a.is_archived:
        raise ValidationError(
            f"{applicant_id} is archived; restore it before writing to it.")
    return a


def _clean_address(address: str | None, who: str) -> str:
    addr = (address or "").strip()
    if not addr:
        raise ValidationError(f"{who} has no e-mail address — nothing was "
                              "sent. Add one first.")
    try:
        return _adm._validate_email(addr) or ""
    except ValidationError:
        raise ValidationError(
            f"{who}'s e-mail address is not valid: {addr}") from None


def _deliver(applicant_id: str, *, to_address: str, to_name: str | None,
             subject: str, body: str, kind: str, role: str,
             attachments_note: str | None = None,
             reference_id: int | None = None,
             log_detail: str | None = None) -> QueuedMessage:
    """Create the message, hand it to the outbox, link it and log it."""
    if kind not in KINDS:
        raise ValidationError(f"Unknown message kind {kind!r}")
    msgs = _messages()
    try:
        m = msgs.create_message({
            "direction": "Outgoing", "channel": "Email",
            "category": CATEGORY, "status": "Queued",
            "subject": subject, "body": body,
            "to_address": to_address, "to_name": to_name,
            "from_name": "Admissions Team",
            "attachments_note": attachments_note,
            "tags": f"admissions,{kind}",
            "notes": f"Applicant {applicant_id} ({role})",
        })
        m = msgs.send_message(m.message_id)
    except msgs.ValidationError as e:
        raise ValidationError(str(e)) from e
    d = msgs.delivery_status(m.message_id)
    out = QueuedMessage(
        message_id=m.message_id, kind=kind, recipient_role=role,
        to_name=to_name, to_address=to_address, subject=subject,
        message_status=m.status,
        delivery_state=d.state if d else None,
        delivery_detail=(d.last_error or d.detail) if d else None)
    init_db()
    with _adm._connect() as conn:
        conn.execute(
            "INSERT INTO admissions_messages (applicant_id, message_id, kind, "
            "recipient_role, to_address, to_name, reference_id, sent_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (applicant_id, m.message_id, kind, role, to_address, to_name,
             reference_id, _guard.actor()))
        who = f"{to_name} <{to_address}>" if to_name else to_address
        _adm._log_event(
            conn, applicant_id,
            f"E-mail ({role}) {log_detail or subject!r} → {who}: "
            f"{out.label} [message #{m.message_id}]", kind="comms")
        conn.commit()
    logger.info("Admissions %s e-mail for %s → message #%d (%s)", kind,
                applicant_id, m.message_id, out.label)
    return out


def _to_applicant_and_parents(a: _adm.Applicant, subject: str, body: str, *,
                              kind: str, include_parents: bool,
                              attachments_note: str | None = None,
                              log_detail: str | None = None
                              ) -> list[QueuedMessage]:
    addr = _clean_address(a.email, a.full_name or a.applicant_id)
    parents = []
    if include_parents:
        from education_system.systems.sixth_form.domain.admissions import (
            applicant_details,
        )
        parents = [c for c in applicant_details.correspondence_contacts(
            a.applicant_id) if (c.email or "").strip().lower() != addr]
    out = [_deliver(a.applicant_id, to_address=addr, to_name=a.full_name,
                    subject=subject, body=body, kind=kind, role="applicant",
                    attachments_note=attachments_note,
                    log_detail=log_detail)]
    seen = {addr}
    for c in parents:
        caddr = _clean_address(c.email, c.name)
        if caddr in seen:
            continue
        seen.add(caddr)
        greeting = f"Dear {c.name},\n\nA copy of a letter we have sent to " \
                   f"{a.full_name} about their sixth form application:\n\n"
        out.append(_deliver(a.applicant_id, to_address=caddr, to_name=c.name,
                            subject=f"Copy: {subject}",
                            body=greeting + body, kind=kind, role="parent",
                            attachments_note=attachments_note,
                            log_detail=log_detail))
    return out


# ── Applicant mail ─────────────────────────────────────────────────

def send_to_applicant(applicant_id: str, subject: str, body: str, *,
                      include_parents: bool = False,
                      kind: str = "custom") -> list[QueuedMessage]:
    """Send a free-text e-mail to the applicant (and parents/carers who
    receive correspondence when ``include_parents``)."""
    _guard.require("e-mailing applicants")
    subject = (subject or "").strip()
    body = (body or "").strip()
    if not subject or not body:
        raise ValidationError("A subject and a message are required")
    a = _applicant(applicant_id)
    return _to_applicant_and_parents(a, subject, body, kind=kind,
                                     include_parents=include_parents)


def send_status_email(applicant_id: str, *,
                      include_parents: bool = False) -> list[QueuedMessage]:
    """The status/decision e-mail for where the application is now."""
    _guard.require("e-mailing applicants")
    from education_system.systems.sixth_form.domain.admissions import (
        applicant_reports,
    )
    a = _applicant(applicant_id)
    subject, body = applicant_reports.render_status_email(applicant_id)
    return _to_applicant_and_parents(a, subject, body, kind="status",
                                     include_parents=include_parents)


def send_offer_letter(applicant_id: str, *,
                      include_parents: bool = False) -> list[QueuedMessage]:
    """E-mail the offer letter (needs an offer on the record)."""
    _guard.require("e-mailing applicants")
    from education_system.systems.sixth_form.domain.admissions import (
        applicant_reports,
    )
    a = _applicant(applicant_id)
    if a.status not in ("Offer Made", "Offer Accepted", "Deferred"):
        raise ValidationError(
            f"{applicant_id} has no offer to send (status: {a.status})")
    body = applicant_reports.render_offer_letter(applicant_id)
    return _to_applicant_and_parents(
        a, "Your offer of a place in our Sixth Form", body,
        kind="offer-letter", include_parents=include_parents,
        log_detail="Offer letter")


def send_offer_expiry_warning(applicant_id: str, *,
                              include_parents: bool = False
                              ) -> list[QueuedMessage]:
    """Remind the applicant their offer expires soon."""
    _guard.require("e-mailing applicants")
    a = _applicant(applicant_id)
    if a.status != "Offer Made" or not a.offer_expiry:
        raise ValidationError(
            f"{applicant_id} has no open offer with an expiry date")
    days = (_dt.date.fromisoformat(a.offer_expiry[:10])
            - _dt.date.today()).days
    when = ("today" if days == 0 else
            "has passed" if days < 0 else
            f"in {days} day{'s' if days != 1 else ''}")
    body = (f"Dear {a.first_name},\n\n"
            f"This is a reminder that your offer of a place in our Sixth "
            f"Form must be accepted by {a.offer_expiry} ({when}).\n\n"
            "Please accept or decline your offer — you can do this in the "
            "applicant portal using your reference number and date of "
            "birth, or by replying to this e-mail.\n\n"
            f"Our ref: {a.applicant_id}\n\nKind regards,\nAdmissions Team")
    return _to_applicant_and_parents(
        a, f"Reminder: please respond to your offer by {a.offer_expiry}",
        body, kind="offer-expiry", include_parents=include_parents,
        log_detail="Offer expiry reminder")


def send_expiry_warnings(*, within_days: int = 7) -> dict[str, Any]:
    """Send :func:`send_offer_expiry_warning` to every open offer expiring
    within *within_days* that has not had one in the last
    :data:`EXPIRY_WARNING_GAP_DAYS` days. Applicants with no e-mail are
    reported, not failed."""
    _guard.require("e-mailing applicants")
    init_db()
    since = (_dt.datetime.now() - _dt.timedelta(days=EXPIRY_WARNING_GAP_DAYS)
             ).strftime("%Y-%m-%d %H:%M:%S")
    sent, skipped, errors = [], [], []
    for a in _adm.list_expiring_offers(within_days=within_days):
        with _adm._connect() as conn:
            recent = conn.execute(
                "SELECT 1 FROM admissions_messages WHERE applicant_id = ? "
                "AND kind = 'offer-expiry' AND created_at >= ? LIMIT 1",
                (a.applicant_id, since)).fetchone()
        if recent:
            skipped.append(a.applicant_id)
            continue
        try:
            send_offer_expiry_warning(a.applicant_id)
            sent.append(a.applicant_id)
        except ValidationError as e:
            errors.append(f"{a.applicant_id}: {e}")
    return {"sent": sent, "skipped": skipped, "errors": errors}


def send_interview_invite(applicant_id: str, *,
                          include_parents: bool = False
                          ) -> list[QueuedMessage]:
    """E-mail the interview invitation with the calendar entry (the
    messages log has no binary attachments, so the .ics text is included
    at the end of the e-mail and named in the attachments note)."""
    _guard.require("e-mailing applicants")
    a = _applicant(applicant_id)
    if not a.interview_date:
        raise ValidationError(f"{applicant_id} has no interview scheduled")
    ics = _adm.interview_to_ics(applicant_id)
    body = (f"Dear {a.first_name},\n\n"
            f"Thank you for applying to our Sixth Form. We would like to "
            f"invite you to an interview on {a.interview_date}"
            + (f" with {a.interviewer}" if a.interviewer else "") + ".\n\n"
            "Please bring your most recent school report. If you cannot "
            "come on this date, reply to this e-mail and we will arrange "
            "another.\n\n"
            f"Our ref: {a.applicant_id}\n\nKind regards,\nAdmissions Team\n\n"
            "-- Calendar entry (save as interview.ics to add it to your "
            "calendar) --\n" + ics)
    return _to_applicant_and_parents(
        a, f"Invitation to interview — {a.interview_date}", body,
        kind="interview-invite", include_parents=include_parents,
        attachments_note="interview.ics (calendar entry included in the "
                         "message text)",
        log_detail=f"Interview invitation ({a.interview_date})")


def send_application_received(applicant_id: str, *,
                              reference_no: str | None = None
                              ) -> list[QueuedMessage]:
    """Confirmation that an application arrived, with the reference the
    applicant uses in the applicant portal."""
    _guard.require("e-mailing applicants")
    a = _applicant(applicant_id)
    ref = reference_no or a.applicant_id
    body = (f"Dear {a.first_name},\n\n"
            "Thank you for applying to our Sixth Form. We have received "
            "your application.\n\n"
            f"Your reference number is: {ref}\n\n"
            "Please keep it safe. With your reference number and date of "
            "birth you can check your application in the applicant portal; "
            "we will e-mail a one-time code to this address each time you "
            "sign in.\n\n"
            "Our admissions team will check your application and be in "
            "touch about the next steps.\n\n"
            "If you did not apply, please reply to this e-mail so we can "
            "remove the application.\n\nKind regards,\nAdmissions Team")
    return _to_applicant_and_parents(
        a, f"Application received — reference {ref}", body,
        kind="application-received", include_parents=False,
        log_detail=f"Application received ({ref})")


def send_portal_code(applicant_id: str, code: str, *,
                     valid_minutes: int) -> QueuedMessage:
    """The one-time applicant-portal sign-in code (applicant only; the
    timeline records that a code was sent, never the code)."""
    _guard.require("e-mailing applicants")
    a = _applicant(applicant_id)
    addr = _clean_address(a.email, a.full_name or a.applicant_id)
    body = (f"Dear {a.first_name},\n\n"
            f"Your applicant portal code is: {code}\n\n"
            f"It can be used once and expires in {valid_minutes} minutes. "
            "If you did not ask for it, you can ignore this e-mail — "
            "nobody can sign in without the code.\n\nAdmissions Team")
    return _deliver(applicant_id, to_address=addr, to_name=a.full_name,
                    subject="Your applicant portal code", body=body,
                    kind="portal-code", role="applicant",
                    log_detail="Applicant portal sign-in code")


def send_contact_change_notice(applicant_id: str, old_email: str,
                               changes: list[str]) -> QueuedMessage:
    """Tell the *previous* address that contact details were changed in
    the applicant portal (so a hijacked change is noticed)."""
    _guard.require("e-mailing applicants")
    a = _applicant(applicant_id)
    addr = _clean_address(old_email, a.full_name or a.applicant_id)
    body = (f"Dear {a.first_name},\n\n"
            "The contact details on your sixth form application were "
            "changed in the applicant portal:\n  - "
            + "\n  - ".join(changes) +
            "\n\nIf you did not make this change, please contact the "
            "admissions team straight away.\n\nAdmissions Team")
    return _deliver(applicant_id, to_address=addr, to_name=a.full_name,
                    subject="Your application contact details were changed",
                    body=body, kind="contact-change", role="applicant",
                    log_detail="Contact details changed notice")


# ── Referees ───────────────────────────────────────────────────────

def _reference(reference_id: int):
    from education_system.systems.sixth_form.domain.admissions import (
        references,
    )
    ref = references.get_reference(reference_id)
    if ref is None:
        raise ValidationError(f"No reference #{reference_id}")
    return references, ref


def send_reference_request(reference_id: int) -> QueuedMessage:
    """E-mail the reference request to the referee and record it as sent
    (status Sent, due date set)."""
    _guard.require("e-mailing referees")
    references, ref = _reference(reference_id)
    if ref.status not in ("Requested", "Sent"):
        raise ValidationError(
            f"Reference is {ref.status} — the request cannot be sent")
    _applicant(ref.applicant_id)
    addr = _clean_address(ref.referee_email, f"Referee {ref.referee_name}")
    if ref.status == "Requested":
        # Set the due date first so the letter quotes the real one.
        references.mark_sent(reference_id)
    subject, body = references.render_request(reference_id)
    return _deliver(ref.applicant_id, to_address=addr,
                    to_name=ref.referee_name, subject=subject, body=body,
                    kind="reference-request", role="referee",
                    reference_id=reference_id,
                    log_detail=f"Reference request #{reference_id}")


def send_reference_chase(reference_id: int) -> QueuedMessage:
    """E-mail a reminder to the referee and record the chase (count and
    date) through :func:`references.chase`."""
    _guard.require("e-mailing referees")
    references, ref = _reference(reference_id)
    if not ref.is_open:
        raise ValidationError(f"Reference is {ref.status} — nothing to chase")
    _applicant(ref.applicant_id)
    addr = _clean_address(ref.referee_email, f"Referee {ref.referee_name}")
    subject, body = references.render_chase(reference_id)
    out = _deliver(ref.applicant_id, to_address=addr,
                   to_name=ref.referee_name, subject=subject, body=body,
                   kind="reference-chase", role="referee",
                   reference_id=reference_id,
                   log_detail=f"Reference reminder #{reference_id}")
    references.chase(reference_id)
    return out


# ── Log ────────────────────────────────────────────────────────────

def communications_log(applicant_id: str) -> list[dict[str, Any]]:
    """Admissions messages sent for an applicant, newest first, with the
    current messages-log status and outbox state of each."""
    _guard.require("applicant correspondence")
    init_db()
    with _adm._connect() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM admissions_messages WHERE applicant_id = ? "
            "ORDER BY created_at DESC, link_id DESC",
            (applicant_id,)).fetchall()]
    msgs = _messages()
    for r in rows:
        m = msgs.get_message(r["message_id"])
        d = msgs.delivery_status(r["message_id"]) if m else None
        r["subject"] = m.subject if m else "(message deleted)"
        r["message_status"] = m.status if m else None
        r["delivery_state"] = d.state if d else None
        r["delivery_detail"] = (d.last_error or d.detail) if d else None
        r["label"] = QueuedMessage(
            message_id=r["message_id"], kind=r["kind"],
            recipient_role=r["recipient_role"], to_name=r["to_name"],
            to_address=r["to_address"] or "", subject=r["subject"],
            message_status=r["message_status"] or "Deleted",
            delivery_state=r["delivery_state"],
            delivery_detail=r["delivery_detail"]).label
    return rows
