"""Email centre — the college's correspondence log, and how it is written.

One screen for everything the college sends and receives: compose to a
learner, a staff member or any address, send standard letters from a
template, and read back what went out and when.

The log is the point. Delivery is best-effort on top of it — see
``email_service`` — so a message always ends up recorded even when no
mail server is configured, and a refused delivery shows as Failed rather
than disappearing.
"""

from __future__ import annotations

import logging

from education_system.systems.fe_college.config import (
    MESSAGE_CATEGORIES,
    MESSAGE_CHANNELS,
    MESSAGE_PRIORITIES,
    MESSAGE_STATUSES,
)
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.interfaces.gui import widgets as w
from education_system.systems.fe_college.services import email_service, email_templates

logger = logging.getLogger(__name__)

TITLE = "Email centre"

_COMPOSE_FIELDS = (
    ("to_name", "To (name)", "text"),
    ("to_address", "To (email)", "text"),
    ("subject", "Subject", "text"),
    ("body", "Message", "text"),
    ("category", "Category", "choice", MESSAGE_CATEGORIES),
    ("priority", "Priority", "choice", MESSAGE_PRIORITIES),
    ("channel", "Channel", "choice", MESSAGE_CHANNELS),
    ("send_now", "Send immediately", "bool"),
)


def open_window(host) -> None:
    Screen(host)


class Screen:
    def __init__(self, host):
        self.host = host
        self.ctl = host.ctl
        host.clear_content()
        parent = host.content_frame

        w.page_header(
            parent, TITLE,
            "Everything the college has sent or received, and where new "
            "messages are written.",
            actions=[
                ("+ Compose", self.compose),
                ("Standard letter", self.from_template),
                ("↻ Refresh", self.refresh),
            ],
        )

        self.filters = w.FilterBar(
            parent, self.refresh,
            search_label="Subject / body / address",
            filters=[
                ("status", "Status", MESSAGE_STATUSES),
                ("category", "Category", MESSAGE_CATEGORIES),
                ("direction", "Direction", ("Outgoing", "Incoming")),
            ],
        )

        self.table = w.DataTable(parent, [
            ("id", "Ref", 90),
            ("when", "When", 130),
            ("direction", "Dir", 50),
            ("to", "To / From", 220),
            ("subject", "Subject", 260),
            ("category", "Category", 110),
            ("status", "Status", 90),
        ], on_double_click=lambda _m: self.view())

        w.button_bar(parent, [
            ("Read", self.view),
            ("Send", self.send),
            ("Edit draft", self.edit),
            ("Discard draft", self.discard),
            ("Log incoming", self.log_incoming),
        ])
        self.refresh()

    # ── Data ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        try:
            messages = email_service.search(
                query=self.filters.query, **self.filters.values()
            )
            counts = email_service.outbox()
        except Exception as exc:
            logger.exception("Could not load the FE College message log")
            w.error(self.host, TITLE, f"Could not load messages: {exc}")
            return

        rows = []
        for m in messages:
            rows.append({
                "id": m.message_id,
                "when": (m.sent_at or m.created_at or "—")[:16],
                "direction": "in" if m.direction == "Incoming" else "out",
                "to": m.recipient if m.direction == "Outgoing"
                      else (m.from_address or m.from_name or "—"),
                "subject": m.subject,
                "category": m.category,
                "status": m.status,
                # Failed is the one state somebody has to act on, so it is
                # the one the table colours.
                "_tone": "bad" if m.status == "Failed" else (
                    "warn" if m.is_draft else "plain"),
                "_obj": m,
            })
        self.table.set_rows(rows)
        self.filters.set_count(len(rows), "message")
        # Whole-log totals in the status bar; the filter bar's count is
        # what the current filters matched, which is a different number.
        status = (f"{counts.total} logged — {counts.drafts} draft, "
                  f"{counts.sent} sent, {counts.incoming} incoming")
        if counts.failed:
            status += f", {counts.failed} FAILED"
        self.host.set_status(status)

    # ── Actions ────────────────────────────────────────────────────────────

    def view(self) -> None:
        message = self.table.require_selection("a message")
        if message is None:
            return
        fresh = email_service.get(message.message_id)
        if fresh is None:
            w.error(self.host, TITLE, "That message no longer exists.")
            self.refresh()
            return
        w.show_text(self.host, f"{fresh.message_id} — {fresh.subject}",
                    _message_text(fresh))

    def compose(self) -> None:
        picked = self._pick_recipient()
        if picked is None:
            return
        result = w.ask(
            self.host, "Compose", _COMPOSE_FIELDS,
            initial={
                "to_name": picked["to_name"],
                "to_address": picked["to_address"],
                "category": "General",
                "priority": "Normal",
                "channel": "Email",
                "send_now": False,
            },
        )
        if result is None:
            return
        try:
            outcome = email_service.compose(
                subject=result.get("subject", ""),
                body=result.get("body", ""),
                to_name=result.get("to_name", ""),
                to_address=result.get("to_address", ""),
                category=result.get("category") or "General",
                priority=result.get("priority") or "Normal",
                channel=result.get("channel") or "Email",
                student_id=picked["student_id"],
                staff_id=picked["staff_id"],
                send_now=bool(result.get("send_now")),
            )
        except ValidationError as exc:
            w.error(self.host, TITLE, str(exc))
            return
        self._report(outcome)
        self.refresh()

    def from_template(self) -> None:
        names = email_templates.list_templates()
        if not names:
            w.info(self.host, TITLE, "No templates are installed.")
            return
        picked = self._pick_recipient()
        if picked is None:
            return

        chosen = w.ask(self.host, "Standard letter",
                       [("template", "Template", "choice", names)])
        if chosen is None or not chosen.get("template"):
            return
        name = chosen["template"]

        # Ask only for the blanks the college cannot already fill in.
        known = {
            "college_name": self.ctl.college_name,
            "first_name": (picked["to_name"] or "").split(" ")[0],
            "last_name": " ".join((picked["to_name"] or "").split(" ")[1:]),
            "student_id": picked["student_id"],
            "recipient_name": picked["to_name"],
        }
        wanted = [t for t in email_templates.placeholders(name) if not known.get(t)]
        context = dict(known)
        if wanted:
            filled = w.ask(
                self.host, f"{name} — details",
                [(t, t.replace("_", " ").capitalize(), "text") for t in wanted],
            )
            if filled is None:
                return
            context.update(filled)

        subject, body = email_templates.preview(name, context)
        if not w.confirm(self.host, "Send this?",
                         f"Subject: {subject}\n\n{body[:600]}"):
            return
        try:
            outcome = email_templates.compose_from_template(
                name, context,
                to_name=picked["to_name"], to_address=picked["to_address"],
                student_id=picked["student_id"], staff_id=picked["staff_id"],
                send_now=True,
            )
        except (ValidationError, email_templates.TemplateError) as exc:
            w.error(self.host, TITLE, str(exc))
            return
        self._report(outcome)
        self.refresh()

    def send(self) -> None:
        message = self.table.require_selection("a draft")
        if message is None:
            return
        try:
            self._report(email_service.send(message.message_id))
        except ValidationError as exc:
            w.error(self.host, TITLE, str(exc))
            return
        self.refresh()

    def edit(self) -> None:
        message = self.table.require_selection("a draft")
        if message is None:
            return
        if not message.is_draft:
            w.warn(self.host, TITLE,
                   "Only a draft can be edited — a sent message is the record "
                   "of what went out.")
            return
        result = w.ask(
            self.host, f"Edit {message.message_id}", _COMPOSE_FIELDS[:-1],
            initial={
                "to_name": message.to_name,
                "to_address": message.to_address,
                "subject": message.subject,
                "body": message.body,
                "category": message.category,
                "priority": message.priority,
                "channel": message.channel,
            },
        )
        if result is None:
            return
        try:
            email_service.update_draft(message.message_id, **result)
        except ValidationError as exc:
            w.error(self.host, TITLE, str(exc))
            return
        self.refresh()

    def discard(self) -> None:
        message = self.table.require_selection("a draft")
        if message is None:
            return
        if not w.confirm(self.host, "Discard draft",
                         f"Discard {message.message_id}? This cannot be undone."):
            return
        try:
            email_service.delete(message.message_id)
        except ValidationError as exc:
            w.error(self.host, TITLE, str(exc))
            return
        self.refresh()

    def log_incoming(self) -> None:
        """Record something that arrived — an enquiry, an employer reply."""
        result = w.ask(self.host, "Log an incoming message", [
            ("from_name", "From (name)", "text"),
            ("from_address", "From (email)", "text"),
            ("subject", "Subject", "text"),
            ("body", "Message", "text"),
            ("category", "Category", "choice", MESSAGE_CATEGORIES),
        ])
        if result is None:
            return
        try:
            email_service.log_incoming(
                subject=result.get("subject", ""),
                body=result.get("body", ""),
                from_name=result.get("from_name", ""),
                from_address=result.get("from_address", ""),
                category=result.get("category") or "General",
            )
        except ValidationError as exc:
            w.error(self.host, TITLE, str(exc))
            return
        self.refresh()

    # ── Helpers ────────────────────────────────────────────────────────────

    def _pick_recipient(self) -> dict | None:
        """Choose from the college directory, or type an address by hand.

        Returns a blank entry (not None) when the user chooses to address
        it manually; None only when they cancel.
        """
        blank = {"to_name": "", "to_address": "", "student_id": "", "staff_id": ""}
        try:
            directory = email_service.recipients()
        except Exception:
            logger.exception("Could not load the recipient directory")
            return blank
        if not directory:
            return blank

        labels = ["(type an address by hand)"] + [r["label"] for r in directory]
        chosen = w.ask(self.host, "Recipient",
                       [("who", "Send to", "choice", labels)])
        if chosen is None:
            return None
        who = chosen.get("who")
        if not who or who == labels[0]:
            return blank
        match = next((r for r in directory if r["label"] == who), None)
        return match or blank

    def _report(self, result) -> None:
        message = result.message
        if message.status == "Failed":
            w.warn(self.host, "Logged, but not delivered",
                   f"{message.message_id} is in the log, but the mail server "
                   f"refused it:\n\n{result.detail}\n\n"
                   f"It is marked Failed rather than lost.")
            return
        if message.is_draft:
            w.info(self.host, TITLE, f"Saved {message.message_id} as a draft.")
            return
        note = ""
        if not result.delivered:
            note = ("\n\nNo mail server is configured, so it has been recorded "
                    "rather than delivered. Configure SMTP in the platform "
                    "email settings to send for real.")
        w.info(self.host, TITLE,
               f"{message.message_id} sent to {message.recipient}.{note}")


def _message_text(message) -> str:
    """One message rendered for the read-only viewer."""
    lines = [
        f"Reference   {message.message_id}",
        f"Status      {message.status}",
        f"Direction   {message.direction}   ({message.channel})",
        f"Category    {message.category}   Priority {message.priority}",
        f"From        {message.from_name} <{message.from_address}>".rstrip(" <>"),
        f"To          {message.recipient}",
        f"Learner     {message.student_name or message.student_id or '—'}",
        f"Staff       {message.staff_name or message.staff_id or '—'}",
        f"Created     {message.created_at or '—'}",
        f"Sent        {message.sent_at or '—'}",
        f"Tags        {message.tags or '—'}",
        "",
        f"Subject: {message.subject}",
        "",
        message.body or "(no body)",
    ]
    return "\n".join(lines)
