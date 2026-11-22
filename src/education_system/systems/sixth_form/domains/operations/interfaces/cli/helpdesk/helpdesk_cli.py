"""CLI flows for the Sixth Form site & IT helpdesk."""

from __future__ import annotations

import logging
from typing import Callable

from education_system.systems.sixth_form.domains.operations.domain.helpdesk import (
    helpdesk as data,
)
from education_system.systems.sixth_form.interfaces.cli.operations._ops_cli import (
    ask,
    choose,
    pause,
    pick_staff,
    run_menu,
    table,
    yes_no,
)

logger = logging.getLogger(__name__)


def _show(rows) -> None:
    table(["Ref", "Type", "Category", "Summary", "Location", "Priority",
           "Status", "Assigned", "SLA due"],
          [(t.reference, t.kind, t.category, t.title, t.location,
            t.priority, t.status + (" !" if t.is_overdue() else ""),
            t.assignee_name,
            "" if not t.is_open else t.sla_due_at.replace("T", " ")[:16])
           for t in rows])


def _pick(rows=None) -> int:
    rows = rows if rows is not None else data.list_tickets(open_only=True)
    raw = ask("Ticket ref or number (blank = choose)")
    if raw:
        digits = raw.upper().removeprefix("HD").lstrip("0") or "0"
        if not digits.isdigit():
            raise ValueError(f"'{raw}' is not a ticket reference")
        return int(digits)
    label = choose("Ticket", [f"{t.reference} — {t.title} ({t.status})"
                              for t in rows])
    if label is None:
        raise ValueError("No tickets to choose from")
    return int(label.split(" — ")[0].removeprefix("HD"))


def _pick_from_options(prompt: str, options) -> str | None:
    labels = [f"{k} — {v}" for k, v in options]
    if not labels:
        return None
    label = choose(prompt, labels, allow_blank=True)
    return label.split(" — ")[0] if label else None


def raise_flow() -> None:
    kind = choose("Type", data.KINDS, default=data.SITE)
    category = choose("Category", data.CATEGORIES[kind], default="Other")
    title = ask("Summary", required=True)
    description = ask("What is wrong")
    print("  Room (blank to skip):")
    room = _pick_from_options("Room", data.room_options())
    location = ask("Location (if not a room above)")
    asset = None
    if yes_no("Is it a specific asset (projector, PC, …)?"):
        asset = _pick_from_options("Asset", data.asset_options())
    t = data.raise_ticket({
        "kind": kind, "category": category, "title": title,
        "description": description, "resource_id": room,
        "location": location, "asset_id": asset,
        "priority": choose("Priority", data.PRIORITIES,
                           default=data.DEFAULT_PRIORITY),
        "contact": ask("Best way to reach you")})
    print(f"\n  ✓ Raised {t.reference}; target "
          f"{t.sla_due_at.replace('T', ' ')[:16]}")
    pause()


def my_tickets() -> None:
    _show(data.list_tickets(mine=True))
    pause()


def view_flow() -> None:
    t = data.get_ticket(_pick(data.list_tickets()))
    print(f"\n  {t.reference}  {t.kind} / {t.category}  — {t.priority}, "
          f"{t.status}")
    print(f"  {t.title}")
    if t.description:
        print(f"  {t.description}")
    print(f"  Where: {t.location or '—'}"
          + (f"   Asset: {t.asset_tag}" if t.asset_tag else ""))
    print(f"  Raised by {t.raised_by_name or t.raised_by} "
          f"{t.raised_at.replace('T', ' ')[:16]}; assigned to "
          f"{t.assignee_name or 'nobody'}")
    if t.resolution:
        print(f"  Resolution: {t.resolution}")
    print("\n  History:")
    for u in data.list_updates(t.ticket_id):
        print(f"    {u.at.replace('T', ' ')[:16]} {u.author or ''} "
              f"[{u.kind}] {u.body}")
    pause()


def comment_flow() -> None:
    tid = _pick(data.list_tickets())
    internal = data.can_manage() and yes_no("Internal note (team only)?")
    data.add_comment(tid, ask("Comment", required=True), internal=internal)
    print("\n  ✓ Added")
    pause()


def confirm_flow() -> None:
    tid = _pick([t for t in data.list_tickets(mine=True)
                 if t.status == data.RESOLVED])
    t = data.close(tid)
    print(f"\n  ✓ {t.reference} closed")
    pause()


def reopen_flow() -> None:
    tid = _pick([t for t in data.list_tickets() if not t.is_open])
    t = data.reopen(tid, ask("What is still wrong", required=True))
    print(f"\n  ✓ {t.reference} reopened ({t.status})")
    pause()


# ── Team ────────────────────────────────────────────────────────────

def queue_flow() -> None:
    kind = choose("Type (blank = both)", data.KINDS, allow_blank=True)
    _show(data.list_tickets(kind=kind, open_only=True))
    pause()


def unassigned_flow() -> None:
    _show(data.list_tickets(unassigned_only=True))
    pause()


def assign_flow() -> None:
    tid = _pick()
    who = pick_staff() if yes_no("Assign to someone (n = unassign)?",
                                 default=True) else None
    t = data.assign(tid, who)
    print(f"\n  ✓ {t.reference}: {t.status}, {t.assignee_name or 'unassigned'}")
    pause()


def status_flow() -> None:
    tid = _pick()
    status = choose("New status", data.OPEN_STATUSES)
    note = ask("Note (required for On hold)")
    t = data.set_status(tid, status, note=note)
    print(f"\n  ✓ {t.reference} now {t.status}")
    pause()


def priority_flow() -> None:
    tid = _pick()
    t = data.set_priority(tid, choose("Priority", data.PRIORITIES))
    print(f"\n  ✓ {t.reference} {t.priority}; target "
          f"{t.sla_due_at.replace('T', ' ')[:16]}")
    pause()


def resolve_flow() -> None:
    tid = _pick()
    t = data.get_ticket(tid)
    resolution = ask("What was done", required=True)
    log, cost = False, None
    if t.asset_id and yes_no(f"Log repair on asset {t.asset_tag}?",
                             default=True):
        log = True
        raw = ask("Repair cost £ (blank = none)")
        try:
            cost = float(raw) if raw else None
        except ValueError:
            raise ValueError("Repair cost must be a number") from None
    t = data.resolve(tid, resolution, log_asset_repair=log, repair_cost=cost)
    print(f"\n  ✓ {t.reference} resolved "
          f"({'within' if t.met_sla else 'outside'} target)")
    pause()


def close_flow() -> None:
    tid = _pick(data.list_tickets())
    t = data.close(tid, resolution=ask("Reason (needed if not resolved)"))
    print(f"\n  ✓ {t.reference} closed")
    pause()


def overdue_flow() -> None:
    _show(data.overdue())
    pause()


def by_category_flow() -> None:
    table(["Type", "Category", "Open", "Overdue"], data.open_by_category())
    pause()


def sla_flow() -> None:
    dfrom = ask("Resolved from (YYYY-MM-DD, blank = all)") or None
    dto = ask("Resolved to (YYYY-MM-DD, blank = today)") or None
    table(["Priority", "Target h", "Resolved", "In target", "Avg hours"],
          [(p, data.SLA_HOURS[p], n, met, avg)
           for p, n, met, avg in data.sla_performance(date_from=dfrom,
                                                      date_to=dto)])
    pause()


def summary_flow() -> None:
    s = data.summary()
    print("\n═══ Helpdesk ═══")
    print(f"  Open:        {s.open_tickets}")
    print(f"  Overdue:     {s.overdue}")
    print(f"  On hold:     {s.on_hold}")
    print(f"  Unassigned:  {s.unassigned}")
    print(f"  Resolved (30 days): {s.resolved_in_period} "
          f"({s.sla_met_in_period} within target)")
    for k, v in s.open_by_assignee.items():
        print(f"    {k:<28} {v}")
    pause()


_STAFF_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Report a problem",        raise_flow),
    ("My tickets",              my_tickets),
    ("View ticket",             view_flow),
    ("Add comment",             comment_flow),
    ("Confirm fixed (close)",   confirm_flow),
    ("Reopen ticket",           reopen_flow),
]

_TEAM_MENU: list[tuple[str, Callable[[], None]]] = [
    ("─" * 6,                   lambda: None),
    ("Open queue",              queue_flow),
    ("Unassigned",              unassigned_flow),
    ("Assign",                  assign_flow),
    ("Change status / hold",    status_flow),
    ("Change priority",         priority_flow),
    ("Resolve",                 resolve_flow),
    ("Close",                   close_flow),
    ("─" * 6,                   lambda: None),
    ("Overdue tickets",         overdue_flow),
    ("Open by category",        by_category_flow),
    ("Target (SLA) performance", sla_flow),
    ("Summary",                 summary_flow),
]


def run() -> None:
    data.init_db()
    menu = _STAFF_MENU + (_TEAM_MENU if data.can_manage() else [])
    run_menu("Site & IT Helpdesk", menu)


def helpdesk_menu() -> None:
    """Entry point for the main CLI menu."""
    run()


def dispatch(label: str) -> bool:
    if label not in ("Helpdesk", "Site & IT Helpdesk"):
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Helpdesk CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        pause()
    return True
