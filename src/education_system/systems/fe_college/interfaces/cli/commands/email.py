"""Email centre commands — the correspondence log, compose, send, templates."""

from __future__ import annotations

from education_system.systems.fe_college.config import (
    MESSAGE_CATEGORIES,
    MESSAGE_CHANNELS,
    MESSAGE_PRIORITIES,
)
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.interfaces.cli import shell as sh
from education_system.systems.fe_college.services import email_service, email_templates


def _table(messages) -> None:
    sh.table(
        [("id", "Ref"), ("when", "When"), ("dir", "Dir"),
         ("to", "To"), ("subject", "Subject"),
         ("category", "Category"), ("status", "Status")],
        [
            {
                "id": m.message_id,
                "when": (m.sent_at or m.created_at or "")[:16],
                "dir": "in" if m.direction == "Incoming" else "out",
                "to": m.recipient if m.direction == "Outgoing"
                      else (m.from_address or m.from_name or "—"),
                "subject": m.subject,
                "category": m.category,
                "status": m.status,
            }
            for m in messages
        ],
        empty="No messages match.",
    )


def log(ctl) -> None:
    """The whole correspondence log, filterable."""
    counts = email_service.outbox()
    sh.header(
        "Email centre",
        f"{counts.total} logged — {counts.drafts} draft, {counts.sent} sent, "
        f"{counts.incoming} incoming"
        + (f", {counts.failed} failed" if counts.failed else ""),
    )
    category = sh.choose("Category", ["any", *MESSAGE_CATEGORIES])
    if category is sh.CANCEL:
        return
    status = sh.choose("Status", ["any", "Draft", "Sent", "Received", "Failed"])
    if status is sh.CANCEL:
        return
    query = sh.prompt("Search subject, body or address (blank for all)")
    if query is sh.CANCEL:
        return

    _table(email_service.search(
        category=None if category == "any" else category,
        status=None if status == "any" else status,
        query=query or None,
    ))


def drafts(ctl) -> None:
    """Everything written but not yet sent."""
    sh.header("Drafts", "Composed but not sent. Send or edit from here.")
    _table(email_service.drafts())


def inbox(ctl) -> None:
    """Messages logged as coming in."""
    sh.header("Inbox", "Enquiries and replies logged against the college.")
    _table(email_service.inbox())


def view(ctl) -> None:
    """One message in full."""
    ref = sh.prompt("Message reference (e.g. FEM-0001)")
    if ref is sh.CANCEL or not ref:
        return
    message = email_service.get(ref.strip().upper())
    if message is None:
        sh.error(f"No message with reference {ref}.")
        return

    sh.header(message.subject, f"{message.message_id} — {message.status}")
    sh.key_values([
        ("Direction", message.direction),
        ("Channel", message.channel),
        ("Category", message.category),
        ("Priority", message.priority),
        ("From", f"{message.from_name} <{message.from_address}>".strip()),
        ("To", message.recipient),
        ("Learner", message.student_name or message.student_id or "—"),
        ("Staff", message.staff_name or message.staff_id or "—"),
        ("Created", message.created_at),
        ("Sent", message.sent_at or "—"),
        ("Tags", message.tags or "—"),
    ])
    sh.section("Message")
    print(message.body or "(no body)")


def compose(ctl) -> None:
    """Write a new message, to a learner, a staff member or any address."""
    sh.header("Compose", "Saved as a draft unless you choose to send it now.")

    to_name, to_address, student_id, staff_id = "", "", "", ""
    if sh.ask_bool("Pick the recipient from the college directory?", True):
        directory = email_service.recipients()
        chosen = sh.choose_object("Recipient", directory, lambda r: r["label"])
        if chosen is sh.CANCEL:
            return
        to_name = chosen["to_name"]
        to_address = chosen["to_address"]
        student_id = chosen["student_id"]
        staff_id = chosen["staff_id"]
        if not to_address:
            sh.warn("That person has no email address on file — enter one below.")

    values = sh.form("Message", [
        ("to_name", "To (name)", "text"),
        ("to_address", "To (email)", "text"),
        ("subject", "Subject", "text"),
        ("body", "Body", "text"),
        ("category", "Category", "choice", MESSAGE_CATEGORIES),
        ("priority", "Priority", "choice", MESSAGE_PRIORITIES),
        ("channel", "Channel", "choice", MESSAGE_CHANNELS),
    ], initial={"to_name": to_name, "to_address": to_address})
    if values is sh.CANCEL:
        return

    send_now = sh.ask_bool("Send it now?", False)
    if send_now is sh.CANCEL:
        return

    try:
        result = email_service.compose(
            subject=values.get("subject", ""),
            body=values.get("body", ""),
            to_name=values.get("to_name") or to_name,
            to_address=values.get("to_address") or to_address,
            category=values.get("category") or "General",
            priority=values.get("priority") or "Normal",
            channel=values.get("channel") or "Email",
            student_id=student_id,
            staff_id=staff_id,
            send_now=bool(send_now),
        )
    except ValidationError as exc:
        sh.error(str(exc))
        return
    _report(result)


def send(ctl) -> None:
    """Send a draft."""
    pending = email_service.drafts()
    if not pending:
        sh.note("There are no drafts waiting to be sent.")
        return
    chosen = sh.choose_object(
        "Draft to send", pending,
        lambda m: f"{m.message_id}  {m.subject}  → {m.recipient}")
    if chosen is sh.CANCEL:
        return
    try:
        _report(email_service.send(chosen.message_id))
    except ValidationError as exc:
        sh.error(str(exc))


def discard(ctl) -> None:
    """Delete a draft. Sent correspondence is never deletable."""
    pending = email_service.drafts()
    if not pending:
        sh.note("There are no drafts to discard.")
        return
    chosen = sh.choose_object(
        "Draft to discard", pending,
        lambda m: f"{m.message_id}  {m.subject}  → {m.recipient}")
    if chosen is sh.CANCEL:
        return
    if not sh.confirm(f"Discard {chosen.message_id}?"):
        return
    try:
        if email_service.delete(chosen.message_id):
            sh.success(f"Discarded {chosen.message_id}.")
    except ValidationError as exc:
        sh.error(str(exc))


def from_template(ctl) -> None:
    """Compose from one of the college's standard letters."""
    names = email_templates.list_templates()
    if not names:
        sh.note("No templates are installed.")
        return
    sh.header("Send a standard letter",
              "Templates ship with the system; fill in the blanks below.")
    name = sh.choose("Template", names)
    if name is sh.CANCEL:
        return

    directory = email_service.recipients()
    chosen = sh.choose_object("Recipient", directory, lambda r: r["label"])
    if chosen is sh.CANCEL:
        return

    # Prompt only for what this template actually uses, pre-filling what the
    # college already knows about the recipient.
    known = {
        "college_name": ctl.college_name,
        "first_name": chosen["to_name"].split(" ")[0] if chosen["to_name"] else "",
        "last_name": " ".join(chosen["to_name"].split(" ")[1:]),
        "student_id": chosen["student_id"],
        "recipient_name": chosen["to_name"],
    }
    context = dict(known)
    for token in email_templates.placeholders(name):
        if context.get(token):
            continue
        value = sh.prompt(f"{token.replace('_', ' ').capitalize()}")
        if value is sh.CANCEL:
            return
        context[token] = value

    subject, body = email_templates.preview(name, context)
    sh.section("Preview")
    sh.key_values([("Subject", subject)])
    print(body)
    sh.blank()

    send_now = sh.ask_bool("Send it now? (no = save as draft)", False)
    if send_now is sh.CANCEL:
        return
    try:
        result = email_templates.compose_from_template(
            name, context,
            to_name=chosen["to_name"], to_address=chosen["to_address"],
            student_id=chosen["student_id"], staff_id=chosen["staff_id"],
            send_now=bool(send_now),
        )
    except (ValidationError, email_templates.TemplateError) as exc:
        sh.error(str(exc))
        return
    _report(result)


def for_learner(ctl) -> None:
    """Everything the college has sent or received about one learner."""
    ref = sh.prompt("Learner reference (e.g. FE26-0001)")
    if ref is sh.CANCEL or not ref:
        return
    learner_id = ref.strip().upper()
    learner = ctl.students.get(learner_id)
    if learner is None:
        sh.error(f"No learner with reference {learner_id}.")
        return
    sh.header(f"Correspondence — {learner.full_name}",
              f"Everything logged against {learner_id}.")
    _table(email_service.for_learner(learner_id))


def _report(result) -> None:
    """Confirm what happened, separating the log from actual delivery."""
    message = result.message
    if message.status == "Failed":
        sh.warn(
            f"{message.message_id} is logged, but delivery was refused: "
            f"{result.detail}")
        sh.note("It stays in the log marked Failed so it is not lost.")
        return
    if message.is_draft:
        sh.success(f"Saved {message.message_id} as a draft.")
        return
    sh.success(f"{message.message_id} sent to {message.recipient}.")
    if not result.delivered:
        sh.note("No mail server is configured, so it is recorded rather than "
                "delivered. Configure SMTP in the platform email settings to "
                "send for real.")
