"""The audit log: who changed what, and what it said before.

Exposes: menu, browse.

Administrators only — the log records every user's actions. An edit
shows as ``field: before → after``; an entry with no field changes
records an event (an upload, an export, a signature) and shows its
detail line instead.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import partial

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.records.audit import AuditRecord
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.application.compliance import compliance_service
from education_system.systems.apprenticeships.application.security.access import Actor

logger = logging.getLogger(__name__)

_COLUMNS = (
    ("#", -6), ("When", 19), ("Who", 12), ("Action", 8), ("Entity", 16), ("Record", 8),
    ("What changed", 48),
)


def menu(actor: Actor) -> None:
    if not actor.is_admin:
        prompts.fail("The audit log is for administrators only.")
        prompts.pause()
        return
    entries: list[tuple[str, Callable[[], None]]] = [
        ("Search the audit log", partial(browse, actor)),
        ("One record's history", partial(_record_history, actor)),
        ("Recent edits (with before and after)", partial(_recent_edits, actor)),
    ]
    prompts.run_menu("Audit Log", entries)


def browse(actor: Actor) -> None:
    """Filter the log, list what matches, and expand any entry's changes."""
    prompts.title("Audit log")
    prompts.note(
        "Leave any filter blank to skip it. Dates are YYYY-MM-DD and include the whole day."
    )
    options = compliance_service.audit_filter_options(actor)
    entity = prompts.choose("Entity", options["entities"], allow_blank=True)
    who = prompts.choose("Who", options["actors"], allow_blank=True)
    action = prompts.choose("Action", config.AUDIT_ACTIONS, allow_blank=True)
    record_id = prompts.ask("Record id")
    since = prompts.ask("From (YYYY-MM-DD)")
    until = prompts.ask("To (YYYY-MM-DD)")
    limit = prompts.ask_int("How many entries at most", default=200)

    rows = compliance_service.audit_trail(
        actor, entity=entity, actor_username=who, action=action,
        entity_id=record_id or None, since=since or None, until=until or None,
        limit=limit or 200,
    )
    _show(rows)


def _record_history(actor: Actor) -> None:
    prompts.title("One record's history")
    options = compliance_service.audit_filter_options(actor)
    entity = prompts.choose("Entity", options["entities"])
    record_id = prompts.ask("Record id", required=True)
    _show(compliance_service.audit_trail(actor, entity=entity, entity_id=record_id, limit=1000))


def _recent_edits(actor: Actor) -> None:
    prompts.title("Recent edits")
    _show(compliance_service.audit_trail(actor, changes_only=True, limit=100))


def _show(rows: list) -> None:
    prompts.table(
        _COLUMNS,
        rows,
        lambda e: (e.audit_id, e.ts, e.actor, e.action, e.entity, e.entity_id,
                   _summary(e)),
        noun="entry",
        empty="no entries match",
    )
    by_id = {e.audit_id: e for e in rows}
    while by_id:
        chosen = prompts.ask_int("Entry # to see in full (blank to finish)")
        if chosen is None:
            return
        entry = by_id.get(chosen)
        if entry is None:
            prompts.note("That entry is not in the list above.")
            continue
        _expand(entry)
    prompts.pause()


def _summary(entry: object) -> str:
    if isinstance(entry, AuditRecord) and entry.changes:
        return entry.changes_text
    return getattr(entry, "detail", "") or ""


def _expand(entry: AuditRecord) -> None:
    prompts.details([
        ("When", entry.ts),
        ("Who", f"{entry.actor} ({config.ROLE_LABELS.get(entry.actor_role or '', entry.actor_role)})"),
        ("Action", entry.action),
        ("Record", f"{entry.entity} {entry.entity_id or ''}"),
        ("Detail", entry.detail),
    ])
    if not entry.changes:
        prompts.note("  (an event, not an edit to fields)")
        return
    prompts.note("")
    for change in entry.changes:
        prompts.note(f"  {change.label}")
