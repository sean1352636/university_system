"""Correspondence — the provider's message log, and how it is written.

With five parties round an apprentice, "who was told what, and when" is
asked constantly: a missed review, a funding query, a gateway delay all
turn into questions about correspondence. This is where the answer lives.

The log is scoped by the service, so an employer opening this screen sees
only messages about their own apprentices. Delivery is best-effort on top
— a message is always recorded, and a refused delivery is marked Failed
rather than lost.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import (
    email_service,
    email_templates,
)

logger = logging.getLogger(__name__)

_SUBTITLE = (
    "Everything sent to and received from apprentices, employers and EPAOs. "
    "Composing saves a draft; sending stamps the log and attempts delivery."
)

_COLUMNS = (
    ("id", "Ref", 90),
    ("when", "When", 130),
    ("direction", "Dir", 50),
    ("who", "To / From", 210),
    ("subject", "Subject", 240),
    ("category", "Category", 130),
    ("status", "Status", 90),
)


def _recipient(message: dict[str, Any]) -> str:
    if message.get("direction") == "Incoming":
        return message.get("from_address") or message.get("from_name") or "—"
    name = message.get("to_name") or ""
    address = message.get("to_address") or ""
    if name and address:
        return f"{name} <{address}>"
    return name or address or "—"


def render(gui) -> None:
    """The message log, with the actions that write to it."""
    frame = gui.clear()
    widgets.heading(frame, "Correspondence", subtitle=_SUBTITLE)

    filters = widgets.FilterBar(
        frame,
        (
            ("status", "Status", "combo", config.MESSAGE_STATUSES),
            ("category", "Category", "combo", config.MESSAGE_CATEGORIES),
            ("direction", "Direction", "combo", config.MESSAGE_DIRECTIONS),
            ("query", "Search", "entry"),
        ),
        lambda: reload(),
    )
    table = widgets.DataTable(
        frame, _COLUMNS,
        on_activate=lambda chosen: _read(gui, str(chosen)),
    )
    hint = widgets.empty_state(frame, "")

    def reload() -> None:
        ok, rows = widgets.guard(
            lambda: email_service.search(gui.actor, **filters.values()))
        rows = rows or []
        _, totals = widgets.guard(lambda: email_service.counts(gui.actor))
        totals = totals or {}
        table.populate(
            rows,
            lambda m: (
                m.get("message_id"),
                (m.get("sent_at") or m.get("created_at") or "—")[:16],
                "in" if m.get("direction") == "Incoming" else "out",
                _recipient(m),
                m.get("subject"),
                m.get("category"),
                m.get("status"),
            ),
            identity=lambda m: m.get("message_id"),
            # Failed is the one state somebody must act on.
            tag=lambda m: m.get("status"),
            noun="message",
        )
        if not rows:
            hint.config(text="No message matches these filters.")
        else:
            summary = (f"{totals.get('total', 0)} logged — "
                       f"{totals.get('drafts', 0)} draft, "
                       f"{totals.get('sent', 0)} sent, "
                       f"{totals.get('incoming', 0)} incoming")
            if totals.get("failed"):
                summary += f", {totals['failed']} FAILED"
            hint.config(text=summary)

    buttons: list[tuple[str, Any]] = [("Read", lambda: _read_selected(gui, table))]
    if gui.actor.can("email.send"):
        buttons += [
            ("Compose", lambda: _compose(gui, reload)),
            ("Standard Letter", lambda: _from_template(gui, reload)),
            ("Send", lambda: _send(gui, table, reload)),
            ("Discard Draft", lambda: _discard(gui, table, reload)),
            ("Log Incoming", lambda: _log_incoming(gui, reload)),
        ]
    widgets.button_bar(frame, buttons)

    reload()


# ═════════════════════════════════════════════════════════════════════
# Reading
# ═════════════════════════════════════════════════════════════════════

def _read_selected(gui, table: widgets.DataTable) -> None:
    chosen = table.require_selection("read a message")
    if chosen is not None:
        _read(gui, str(chosen))


def _read(gui, message_id: str) -> None:
    """One message in full, rendered over the log."""
    frame = gui.clear()
    ok, message = widgets.guard(lambda: email_service.get(gui.actor, message_id))
    if not ok or message is None:
        widgets.heading(frame, "Message")
        widgets.button_bar(frame, [("← Back", lambda: render(gui))])
        widgets.empty_state(frame, "That message could not be opened.")
        return

    widgets.heading(frame, message.get("subject") or "(no subject)",
                    subtitle=f"{message.get('message_id')} — "
                             f"{message.get('status')}")
    widgets.field_grid(frame, [
        ("Direction", message.get("direction")),
        ("Channel", message.get("channel")),
        ("Category", message.get("category")),
        ("Priority", message.get("priority")),
        ("From", f"{message.get('from_name') or ''} "
                 f"{message.get('from_address') or ''}".strip() or "—"),
        ("To", _recipient(message)),
        ("Apprentice", message.get("apprentice_name") or "—"),
        ("Employer", message.get("employer_name") or "—"),
        ("Sent by", message.get("sent_by") or "—"),
        ("Created", message.get("created_at") or "—"),
        ("Sent", message.get("sent_at") or "—"),
        ("Tags", message.get("tags") or "—"),
    ])
    body = widgets.section(frame, "Message")
    widgets.field_grid(body, [("", message.get("body") or "(no body)")],
                       columns=1)
    widgets.button_bar(frame, [("← Back", lambda: render(gui))])


# ═════════════════════════════════════════════════════════════════════
# Writing
# ═════════════════════════════════════════════════════════════════════

def _pick_recipient(gui) -> dict[str, Any] | None:
    """Choose from the directory, or address the message by hand.

    A blank entry means "typed by hand"; ``None`` means cancelled.
    """
    blank = {"to_name": "", "to_address": "",
             "apprentice_id": None, "employer_id": None}
    ok, directory = widgets.guard(lambda: email_service.recipients(gui.actor))
    if not ok or not directory:
        return blank

    labels = ["(type an address by hand)"] + [
        f"[{r['kind']}] {r['label']}" for r in directory]
    chosen: dict[str, Any] = {}

    def save(values: dict[str, Any]) -> None:
        chosen.update(values)

    dialog = widgets.FormDialog(
        gui.root, "Recipient",
        [{"key": "who", "label": "Send to", "kind": "combo",
          "options": labels, "value": labels[0]}],
        save,
        intro="Apprentices, employer contacts and EPAOs you may write to.",
        save_label="Next",
    )
    if not dialog.saved:
        return None
    who = chosen.get("who")
    if not who or who == labels[0]:
        return blank
    index = labels.index(who) - 1
    return directory[index]


def _compose(gui, after) -> None:
    picked = _pick_recipient(gui)
    if picked is None:
        return

    def save(values: dict[str, Any]) -> None:
        result = email_service.compose(
            gui.actor,
            subject=values.get("subject", ""),
            body=values.get("body", ""),
            to_name=values.get("to_name", ""),
            to_address=values.get("to_address", ""),
            category=values.get("category") or "General",
            priority=values.get("priority") or "Normal",
            channel=values.get("channel") or "Email",
            apprentice_id=picked["apprentice_id"],
            employer_id=picked["employer_id"],
            send_now=bool(values.get("send_now")),
        )
        _report(result)

    dialog = widgets.FormDialog(
        gui.root, "Compose",
        [
            {"key": "to_name", "label": "To (name)", "value": picked["to_name"]},
            {"key": "to_address", "label": "To (email)", "required": True,
             "value": picked["to_address"]},
            {"key": "subject", "label": "Subject", "required": True},
            {"key": "body", "label": "Message", "kind": "text"},
            {"key": "category", "label": "Category", "kind": "combo",
             "options": config.MESSAGE_CATEGORIES, "value": "General"},
            {"key": "priority", "label": "Priority", "kind": "combo",
             "options": config.MESSAGE_PRIORITIES, "value": "Normal"},
            {"key": "channel", "label": "Channel", "kind": "combo",
             "options": config.MESSAGE_CHANNELS, "value": "Email"},
            {"key": "send_now", "label": "Send immediately", "kind": "check"},
        ],
        save,
        save_label="Save",
    )
    if dialog.saved:
        after()


def _from_template(gui, after) -> None:
    names = email_templates.list_templates()
    if not names:
        widgets.inform("No templates are installed.", title="Standard letter")
        return
    picked = _pick_recipient(gui)
    if picked is None:
        return

    chosen: dict[str, Any] = {}
    picker = widgets.FormDialog(
        gui.root, "Standard letter",
        [{"key": "template", "label": "Template", "kind": "combo",
          "options": names, "value": names[0], "required": True}],
        lambda values: chosen.update(values),
        save_label="Next",
    )
    if not picker.saved or not chosen.get("template"):
        return
    name = chosen["template"]

    # Ask only for the blanks the provider cannot already fill in.
    known = {
        "provider_name": email_service.PROVIDER_NAME,
        "recipient_name": picked["to_name"],
        "first_name": (picked["to_name"] or "").split(" ")[0],
        "apprentice_name": picked["to_name"] if picked["apprentice_id"] else "",
        "sender_name": gui.actor.name,
        "tutor_name": gui.actor.name,
    }
    context = dict(known)
    wanted = [t for t in email_templates.placeholders(name) if not known.get(t)]

    def save(values: dict[str, Any]) -> None:
        context.update(values)
        result = email_templates.compose_from_template(
            gui.actor, name, context,
            to_name=picked["to_name"], to_address=picked["to_address"],
            apprentice_id=picked["apprentice_id"],
            employer_id=picked["employer_id"],
            send_now=bool(values.get("_send_now")),
        )
        _report(result)

    fields: list[dict[str, Any]] = [
        {"key": token, "label": token.replace("_", " ").capitalize()}
        for token in wanted
    ]
    fields.append({"key": "_send_now", "label": "Send immediately",
                   "kind": "check"})
    dialog = widgets.FormDialog(
        gui.root, f"{name.replace('_', ' ').capitalize()}", fields, save,
        intro="Fill in the blanks this letter needs. Leave Send immediately "
              "unticked to save it as a draft and read it back first.",
        save_label="Save",
    )
    if dialog.saved:
        after()


def _send(gui, table: widgets.DataTable, after) -> None:
    chosen = table.require_selection("send a draft")
    if chosen is None:
        return
    ok, result = widgets.guard(
        lambda: email_service.send(gui.actor, str(chosen)))
    if ok and result is not None:
        _report(result)
        after()


def _discard(gui, table: widgets.DataTable, after) -> None:
    chosen = table.require_selection("discard a draft")
    if chosen is None:
        return
    if not widgets.confirm(f"Discard {chosen}? This cannot be undone."):
        return
    ok, _ = widgets.guard(lambda: email_service.delete(gui.actor, str(chosen)))
    if ok:
        after()


def _log_incoming(gui, after) -> None:
    def save(values: dict[str, Any]) -> None:
        email_service.log_incoming(
            gui.actor,
            subject=values.get("subject", ""),
            body=values.get("body", ""),
            from_name=values.get("from_name", ""),
            from_address=values.get("from_address", ""),
            category=values.get("category") or "General",
        )

    dialog = widgets.FormDialog(
        gui.root, "Log an incoming message",
        [
            {"key": "from_name", "label": "From (name)"},
            {"key": "from_address", "label": "From (email)"},
            {"key": "subject", "label": "Subject", "required": True},
            {"key": "body", "label": "Message", "kind": "text"},
            {"key": "category", "label": "Category", "kind": "combo",
             "options": config.MESSAGE_CATEGORIES, "value": "General"},
        ],
        save,
        intro="For something that arrived by another route — a reply, a phone "
              "call worth recording, a letter.",
    )
    if dialog.saved:
        after()


def _report(result: email_service.SendResult) -> None:
    """Confirm the outcome, keeping the log distinct from delivery."""
    if result.status == "Failed":
        widgets.warn(
            f"{result.message_id} is in the log, but the mail server refused "
            f"it:\n\n{result.detail}\n\nIt is marked Failed rather than lost.",
            title="Logged, but not delivered")
        return
    if result.status == "Draft":
        widgets.inform(f"Saved {result.message_id} as a draft.")
        return
    note = ""
    if not result.delivered:
        note = ("\n\nNo mail server is configured, so it has been recorded "
                "rather than delivered. Set SMTP up in the platform email "
                "settings to send for real.")
    widgets.inform(f"{result.message_id} sent to {result.recipient}.{note}")
