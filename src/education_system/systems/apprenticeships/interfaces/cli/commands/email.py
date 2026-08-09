"""Correspondence: the message log, compose, send and standard letters.

Everything here is scoped by the service, so an employer running the
same commands sees only messages about their own apprentices.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import partial
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import (
    ValidationError,
)
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.services import (
    email_service,
    email_templates,
)
from education_system.systems.apprenticeships.services.access import Actor

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════
# Menu
# ═════════════════════════════════════════════════════════════════════

def menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("Message log", partial(_log, actor)),
        ("Read a message", partial(_view, actor)),
        ("Inbox", partial(_inbox, actor)),
    ]
    if actor.can("email.send"):
        entries += [
            ("Compose a message", partial(_compose, actor)),
            ("Send a standard letter", partial(_from_template, actor)),
            ("Drafts", partial(_drafts, actor)),
            ("Send a draft", partial(_send, actor)),
            ("Discard a draft", partial(_discard, actor)),
            ("Log an incoming message", partial(_log_incoming, actor)),
        ]
    prompts.run_menu("Correspondence", entries)


# ═════════════════════════════════════════════════════════════════════
# Shared rendering
# ═════════════════════════════════════════════════════════════════════

def _recipient(message: dict[str, Any]) -> str:
    if message.get("direction") == "Incoming":
        return message.get("from_address") or message.get("from_name") or "—"
    name = message.get("to_name") or ""
    address = message.get("to_address") or ""
    if name and address:
        return f"{name} <{address}>"
    return name or address or "—"


def _table(messages: list[dict[str, Any]]) -> None:
    prompts.table(
        (("Ref", 10), ("When", 17), ("Dir", 4), ("To / From", 26),
         ("Subject", 30), ("Category", 15), ("Status", 9)),
        messages,
        lambda m: (
            m.get("message_id"),
            (m.get("sent_at") or m.get("created_at") or "")[:16],
            "in" if m.get("direction") == "Incoming" else "out",
            _recipient(m),
            m.get("subject"),
            m.get("category"),
            m.get("status"),
        ),
        noun="message",
    )


def _show(message: dict[str, Any]) -> None:
    prompts.title(f"{message.get('message_id')} — {message.get('subject')}")
    prompts.details([
        ("Status", message.get("status")),
        ("Direction", message.get("direction")),
        ("Channel", message.get("channel")),
        ("Category", message.get("category")),
        ("Priority", message.get("priority")),
        ("From", f"{message.get('from_name') or ''} "
                 f"{message.get('from_address') or ''}".strip() or "—"),
        ("To", _recipient(message)),
        ("Apprentice", message.get("apprentice_name")
                       or message.get("apprentice_id") or "—"),
        ("Employer", message.get("employer_name")
                     or message.get("employer_id") or "—"),
        ("Sent by", message.get("sent_by")),
        ("Created", message.get("created_at")),
        ("Sent", message.get("sent_at") or "—"),
        ("Tags", message.get("tags") or "—"),
    ])
    prompts.rule()
    print(message.get("body") or "(no body)")
    print()


def _pick(actor: Actor, heading: str,
          messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not messages:
        prompts.note("There is nothing here.")
        prompts.pause()
        return None
    return prompts.choose(
        heading, messages,
        render=lambda m: f"{m.get('message_id')}  {m.get('subject')}  "
                         f"→ {_recipient(m)}")


# ═════════════════════════════════════════════════════════════════════
# Commands
# ═════════════════════════════════════════════════════════════════════

def _log(actor: Actor) -> None:
    totals = email_service.counts(actor)
    prompts.title("Correspondence")
    prompts.note(
        f"{totals['total']} logged — {totals['drafts']} draft, "
        f"{totals['sent']} sent, {totals['incoming']} incoming"
        + (f", {totals['failed']} FAILED" if totals["failed"] else ""))

    category = prompts.choose("Category filter", config.MESSAGE_CATEGORIES,
                              allow_blank=True)
    status = prompts.choose("Status filter", config.MESSAGE_STATUSES,
                            allow_blank=True)
    query = prompts.ask("Search subject, body or address")

    _table(email_service.search(
        actor, category=category, status=status, query=query or None))
    prompts.pause()


def _drafts(actor: Actor) -> None:
    prompts.title("Drafts")
    _table(email_service.drafts(actor))
    prompts.pause()


def _inbox(actor: Actor) -> None:
    prompts.title("Inbox")
    _table(email_service.inbox(actor))
    prompts.pause()


def _view(actor: Actor) -> None:
    message = _pick(actor, "Message", email_service.search(actor))
    if message is None:
        return
    _show(message)
    prompts.pause()


def _compose(actor: Actor) -> None:
    prompts.title("Compose")
    picked = _pick_recipient(actor)
    if picked is None:
        return

    to_name = prompts.ask("To (name)", default=picked["to_name"])
    to_address = prompts.ask("To (email)", default=picked["to_address"],
                             required=True)
    subject = prompts.ask("Subject", required=True)
    body = prompts.ask("Body")
    category = prompts.choose_value("Category", config.MESSAGE_CATEGORIES,
                                    default="General")
    priority = prompts.choose_value("Priority", config.MESSAGE_PRIORITIES,
                                    default="Normal")
    channel = prompts.choose_value("Channel", config.MESSAGE_CHANNELS,
                                   default="Email")
    send_now = prompts.ask_yes_no("Send it now?")

    try:
        result = email_service.compose(
            actor, subject=subject, body=body, to_name=to_name,
            to_address=to_address, category=category, priority=priority,
            channel=channel, apprentice_id=picked["apprentice_id"],
            employer_id=picked["employer_id"], send_now=send_now,
        )
    except ValidationError as exc:
        prompts.fail(str(exc))
        prompts.pause()
        return
    _report(result)
    prompts.pause()


def _from_template(actor: Actor) -> None:
    names = email_templates.list_templates()
    if not names:
        prompts.note("No templates are installed.")
        prompts.pause()
        return

    prompts.title("Send a standard letter")
    name = prompts.choose_value("Template", tuple(names))
    picked = _pick_recipient(actor)
    if picked is None:
        return

    known = {
        "provider_name": email_service.PROVIDER_NAME,
        "recipient_name": picked["to_name"],
        "first_name": (picked["to_name"] or "").split(" ")[0],
        "apprentice_name": picked["to_name"] if picked["apprentice_id"] else "",
        "sender_name": actor.name,
        "tutor_name": actor.name,
    }
    context = dict(known)
    for token in email_templates.placeholders(name):
        if context.get(token):
            continue
        context[token] = prompts.ask(token.replace("_", " ").capitalize())

    subject, body = email_templates.preview(name, context)
    prompts.rule()
    prompts.note(f"Subject: {subject}")
    print(body)
    prompts.rule()

    send_now = prompts.ask_yes_no("Send it now? (no saves it as a draft)")
    try:
        result = email_templates.compose_from_template(
            actor, name, context,
            to_name=picked["to_name"], to_address=picked["to_address"],
            apprentice_id=picked["apprentice_id"],
            employer_id=picked["employer_id"], send_now=send_now,
        )
    except (ValidationError, email_templates.TemplateError) as exc:
        prompts.fail(str(exc))
        prompts.pause()
        return
    _report(result)
    prompts.pause()


def _send(actor: Actor) -> None:
    message = _pick(actor, "Draft to send", email_service.drafts(actor))
    if message is None:
        return
    try:
        _report(email_service.send(actor, message["message_id"]))
    except ValidationError as exc:
        prompts.fail(str(exc))
    prompts.pause()


def _discard(actor: Actor) -> None:
    message = _pick(actor, "Draft to discard", email_service.drafts(actor))
    if message is None:
        return
    if not prompts.ask_yes_no(f"Discard {message['message_id']}?"):
        return
    try:
        if email_service.delete(actor, message["message_id"]):
            prompts.ok(f"Discarded {message['message_id']}.")
    except ValidationError as exc:
        prompts.fail(str(exc))
    prompts.pause()


def _log_incoming(actor: Actor) -> None:
    prompts.title("Log an incoming message")
    prompts.note("For something that arrived by another route — a reply, a "
                 "phone call worth recording, a letter.")
    from_name = prompts.ask("From (name)")
    from_address = prompts.ask("From (email)")
    subject = prompts.ask("Subject", required=True)
    body = prompts.ask("Message")
    category = prompts.choose_value("Category", config.MESSAGE_CATEGORIES,
                                    default="General")
    try:
        message = email_service.log_incoming(
            actor, subject=subject, body=body, from_name=from_name,
            from_address=from_address, category=category)
    except ValidationError as exc:
        prompts.fail(str(exc))
        prompts.pause()
        return
    prompts.ok(f"Logged {message['message_id']}.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _pick_recipient(actor: Actor) -> dict[str, Any] | None:
    """Choose from the directory, or address the message by hand.

    Returns a blank entry when addressing by hand, ``None`` on cancel.
    """
    blank = {"to_name": "", "to_address": "",
             "apprentice_id": None, "employer_id": None}
    directory = email_service.recipients(actor)
    if not directory:
        return blank
    if not prompts.ask_yes_no("Pick the recipient from the directory?",
                              default=True):
        return blank
    chosen = prompts.choose(
        "Recipient", directory,
        render=lambda r: f"[{r['kind']}] {r['label']}")
    if chosen is None:
        return blank
    if not chosen["to_address"]:
        prompts.note("No email address on file — enter one at the prompt.")
    return chosen


def _report(result: email_service.SendResult) -> None:
    """Confirm what happened, keeping the log distinct from delivery."""
    if result.status == "Failed":
        prompts.fail(f"{result.message_id} is logged, but delivery was "
                     f"refused: {result.detail}")
        prompts.note("It stays in the log marked Failed so it is not lost.")
        return
    if result.status == "Draft":
        prompts.ok(f"Saved {result.message_id} as a draft.")
        return
    prompts.ok(f"{result.message_id} sent to {result.recipient}.")
    if not result.delivered:
        prompts.note("No mail server is configured, so it is recorded rather "
                     "than delivered. Set SMTP up in the platform email "
                     "settings to send for real.")
