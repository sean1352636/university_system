"""Tkinter window for the Sixth Form site & IT helpdesk.

Every member of staff gets "My tickets" (raise, follow, comment, confirm
the fix, reopen). Site / IT staff (``OPERATIONS``) also get the Queue,
Overdue and Reports tabs.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from education_system.platform.delivery.gui import window_sizing
from education_system.systems.sixth_form.domains.operations.domain.helpdesk import (
    helpdesk as data,
)
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable
from education_system.systems.sixth_form.interfaces.gui.operations._ops_ui import (
    make_window,
)
from education_system.systems.sixth_form.interfaces.gui.progression import (
    _record_tabs as rt,
)

logger = logging.getLogger(__name__)

_COLUMNS = [("ref", "Ref", 80), ("kind", "Type", 50),
            ("category", "Category", 150), ("title", "Summary", 260),
            ("location", "Location", 170), ("priority", "Priority", 70),
            ("status", "Status", 90), ("assignee", "Assigned to", 130),
            ("raised", "Raised", 120), ("due", "SLA due", 120)]


def _row(t: data.Ticket) -> dict:
    return {"id": t.ticket_id, "ref": t.reference, "kind": t.kind,
            "category": t.category, "title": t.title,
            "location": t.location or "", "priority": t.priority,
            "status": t.status, "assignee": t.assignee_name or "",
            "raised": t.raised_at.replace("T", " ")[:16],
            "due": ("" if not t.is_open
                    else "on hold" if t.status == data.ON_HOLD
                    else t.sla_due_at.replace("T", " ")[:16]),
            "raiser": t.raised_by_name or t.raised_by,
            "_overdue": t.is_overdue()}


def _tag(row: dict) -> str | None:
    if row["_overdue"]:
        return "bad"
    if row["status"] in (data.RESOLVED, data.CLOSED):
        return "muted"
    if row["priority"] == data.URGENT or row["status"] == data.ON_HOLD:
        return "warn"
    return None


def _all_categories() -> list[str]:
    seen: list[str] = []
    for cats in data.CATEGORIES.values():
        seen += [c for c in cats if c not in seen]
    return seen


def _room_choices() -> list[str]:
    try:
        return [f"{rid} — {label}" for rid, label in data.room_options()]
    except Exception:
        logger.exception("Could not list rooms")
        return []


def _asset_choices() -> list[str]:
    try:
        return [f"{aid} — {label}" for aid, label in data.asset_options()]
    except Exception:
        logger.exception("Could not list assets")
        return []


def _key(label: str) -> str | None:
    return (label or "").split(" — ")[0].strip() or None


def _staff_choices() -> list[str]:
    from education_system.systems.sixth_form.domain.staff import (
        staff as _staff,
    )
    return [f"{s.staff_id} — {s.full_name} ({s.role})"
            for s in _staff.list_staff(active_only=True)]


def _refuse(parent, title: str, message: str) -> None:
    from education_system.platform.delivery.gui.parented_dialogs import messagebox
    messagebox.showwarning(title, message,
                           parent=getattr(parent, "root", parent))


def open_helpdesk_window(parent=None) -> None:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    p = access.current()
    if not (p.is_staff or p.can(access.OPERATIONS)):
        _refuse(parent, "Site & IT Helpdesk", "The helpdesk is for staff.")
        return
    data.init_db()
    win, nb = make_window(parent, "Site & IT Helpdesk")
    tables: list[rt.RecordTable] = []

    def refresh_all() -> None:
        for t in tables:
            t.refresh()

    def raise_ticket(table: rt.RecordTable) -> None:
        cats = _all_categories()
        rt.form_dialog(
            table.parent, "Report a problem",
            (("kind", "Type", "choice", data.KINDS),
             ("category", "Category", "choice", cats),
             ("title", "Summary", "text"),
             ("description", "What is wrong", "multiline"),
             ("room", "Room (bookable rooms)", "choice",
              [""] + _room_choices()),
             ("location", "Location (if not a room above)", "text"),
             ("asset", "Asset (asset register)", "choice",
              [""] + _asset_choices()),
             ("priority", "Priority", "choice", data.PRIORITIES),
             ("contact", "Best way to reach you", "text")),
            {"kind": data.SITE, "priority": data.DEFAULT_PRIORITY,
             "category": "Other"},
            lambda v: data.raise_ticket({
                **v, "resource_id": _key(v.pop("room")),
                "asset_id": _key(v.pop("asset"))}),
            refresh_all,
            intro="Site: buildings, heating, plumbing, furniture, cleaning. "
                  "IT: devices, accounts, network, printing, AV. Urgent = "
                  "unsafe or stopping teaching now.")

    def view(table: rt.RecordTable) -> None:
        _ticket_detail(win, int(table.require()["id"]), refresh_all)

    def edit(table: rt.RecordTable) -> None:
        t = data.get_ticket(int(table.require()["id"]))
        rt.form_dialog(
            table.parent, f"Edit {t.reference}",
            (("kind", "Type", "choice", data.KINDS),
             ("category", "Category", "choice", _all_categories()),
             ("title", "Summary", "text"),
             ("description", "What is wrong", "multiline"),
             ("room", "Room", "choice", [""] + _room_choices()),
             ("location", "Location", "text"),
             ("asset", "Asset", "choice", [""] + _asset_choices()),
             ("priority", "Priority", "choice", data.PRIORITIES),
             ("contact", "Contact", "text")),
            {**vars(t),
             "room": next((c for c in _room_choices()
                           if _key(c) == str(t.resource_id)), ""),
             "asset": next((c for c in _asset_choices()
                            if _key(c) == str(t.asset_id)), "")},
            lambda v: data.update_details(t.ticket_id, {
                **v, "resource_id": _key(v.pop("room")),
                "asset_id": _key(v.pop("asset"))}),
            refresh_all)

    def confirm_fixed(table: rt.RecordTable) -> None:
        t = data.get_ticket(int(table.require()["id"]))
        if t.status != data.RESOLVED:
            raise ValueError("You can confirm a ticket once it is Resolved")
        if rt.confirm(table.parent, "Confirm fix",
                      f"Close {t.reference} as fixed?"):
            data.close(t.ticket_id)
            refresh_all()

    def reopen(table: rt.RecordTable) -> None:
        t = data.get_ticket(int(table.require()["id"]))
        rt.form_dialog(table.parent, f"Reopen {t.reference}",
                       (("reason", "What is still wrong", "multiline"),),
                       {}, lambda v: data.reopen(t.ticket_id, v["reason"]),
                       refresh_all)

    # ── My tickets ──
    def my_tab(parent: ttk.Frame) -> None:
        tables.append(rt.RecordTable(
            parent, _COLUMNS,
            lambda f: [_row(t) for t in data.list_tickets(
                mine=True, status=f.get("status") or None,
                open_only=f.get("open") == "Yes")],
            key="id",
            filters=(("status", "Status", "choice", data.STATUSES),
                     ("open", "Open only", "choice", ("Yes",))),
            actions=(("Report a problem", raise_ticket),
                     ("View / comment", view), ("Edit", edit),
                     ("Confirm fixed", confirm_fixed), ("Reopen", reopen)),
            note="Tickets you raised or are assigned to. Red = past its "
                 "target time.",
            tags=_tag, on_open=view))

    rt.notebook_tab(nb, "My tickets", my_tab)
    if not data.can_manage():
        return

    # ── Team-only actions ──
    def assign(table: rt.RecordTable) -> None:
        t = data.get_ticket(int(table.require()["id"]))
        rt.form_dialog(table.parent, f"Assign {t.reference}",
                       (("who", "Assign to (blank = unassign)", "choice",
                         [""] + _staff_choices()),),
                       {}, lambda v: data.assign(t.ticket_id, _key(v["who"])),
                       refresh_all)

    def set_status(table: rt.RecordTable) -> None:
        t = data.get_ticket(int(table.require()["id"]))
        rt.form_dialog(table.parent, f"Status — {t.reference}",
                       (("status", "New status", "choice",
                         data.OPEN_STATUSES),
                        ("note", "Note (required for On hold)", "text")),
                       {"status": t.status},
                       lambda v: data.set_status(t.ticket_id, v["status"],
                                                 note=v["note"]),
                       refresh_all)

    def priority(table: rt.RecordTable) -> None:
        t = data.get_ticket(int(table.require()["id"]))
        rt.form_dialog(table.parent, f"Priority — {t.reference}",
                       (("priority", "Priority", "choice", data.PRIORITIES),),
                       {"priority": t.priority},
                       lambda v: data.set_priority(t.ticket_id,
                                                   v["priority"]),
                       refresh_all)

    def resolve(table: rt.RecordTable) -> None:
        t = data.get_ticket(int(table.require()["id"]))
        fields = [("resolution", "What was done", "multiline")]
        if t.asset_id:
            fields += [("log", f"Log repair on asset {t.asset_tag}", "bool"),
                       ("cost", "Repair cost (£)", "number")]

        def save(v):
            cost = v.get("cost") or None
            if cost is not None:
                try:
                    cost = float(cost)
                except ValueError:
                    raise ValueError("Repair cost must be a number") from None
            data.resolve(t.ticket_id, v["resolution"],
                         log_asset_repair=bool(v.get("log")),
                         repair_cost=cost)
        rt.form_dialog(table.parent, f"Resolve {t.reference}", fields,
                       {"log": bool(t.asset_id)}, save, refresh_all)

    def close(table: rt.RecordTable) -> None:
        t = data.get_ticket(int(table.require()["id"]))
        rt.form_dialog(table.parent, f"Close {t.reference}",
                       (("resolution", "Reason (needed if not resolved)",
                         "multiline"),),
                       {}, lambda v: data.close(t.ticket_id,
                                                resolution=v["resolution"]),
                       refresh_all)

    queue_actions = (("Report a problem", raise_ticket),
                     ("View / comment", view), ("Assign", assign),
                     ("Status / hold", set_status), ("Priority", priority),
                     ("Resolve", resolve), ("Close", close),
                     ("Reopen", reopen), ("Edit", edit))

    def queue_tab(parent: ttk.Frame) -> None:
        tables.append(rt.RecordTable(
            parent, _COLUMNS + [("raiser", "Raised by", 130)],
            lambda f: [_row(t) for t in data.list_tickets(
                kind=f.get("kind") or None,
                category=f.get("category") or None,
                status=f.get("status") or None,
                priority=f.get("priority") or None,
                open_only=f.get("open") == "Yes",
                unassigned_only=f.get("open") == "Unassigned",
                search=f.get("search") or None)],
            key="id",
            filters=(("kind", "Type", "choice", data.KINDS),
                     ("category", "Category", "choice", _all_categories),
                     ("status", "Status", "choice", data.STATUSES),
                     ("priority", "Priority", "choice", data.PRIORITIES),
                     ("open", "Show", "choice", ("Yes", "Unassigned"), "Yes"),
                     ("search", "Search", "text")),
            actions=queue_actions, tags=_tag, on_open=view))

    def overdue_tab(parent: ttk.Frame) -> None:
        tables.append(rt.RecordTable(
            parent, _COLUMNS + [("raiser", "Raised by", 130)],
            lambda f: [_row(t) for t in data.overdue(
                kind=f.get("kind") or None)],
            key="id", filters=(("kind", "Type", "choice", data.KINDS),),
            actions=queue_actions, tags=_tag, on_open=view,
            note="Open tickets past their target time (tickets on hold "
                 "are excluded — the clock stops while waiting)."))

    def reports_tab(parent: ttk.Frame) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Resolved from:").pack(side="left")
        dfrom = tk.StringVar()
        ttk.Entry(bar, textvariable=dfrom, width=12).pack(side="left",
                                                          padx=(4, 8))
        ttk.Label(bar, text="to:").pack(side="left")
        dto = tk.StringVar()
        ttk.Entry(bar, textvariable=dto, width=12).pack(side="left",
                                                        padx=(4, 8))
        box = tk.Text(parent, wrap="none", font=("TkFixedFont", 10))

        def render() -> None:
            try:
                lines = _report_lines(dfrom.get().strip() or None,
                                      dto.get().strip() or None)
            except ValueError as exc:
                rt.warn(parent, "Helpdesk reports", str(exc))
                return
            box.configure(state="normal")
            box.delete("1.0", "end")
            box.insert("1.0", "\n".join(lines))
            box.configure(state="disabled")

        ttk.Button(bar, text="Refresh", command=render).pack(side="left")
        box.pack(fill="both", expand=True)
        render()

    rt.notebook_tab(nb, "Queue", queue_tab)
    rt.notebook_tab(nb, "Overdue", overdue_tab)
    rt.notebook_tab(nb, "Reports", reports_tab)
    nb.select(1)


def _report_lines(date_from: str | None, date_to: str | None) -> list[str]:
    s = data.summary()
    lines = ["Helpdesk queue", "",
             f"  Open tickets:       {s.open_tickets}",
             f"  Overdue:            {s.overdue}",
             f"  On hold:            {s.on_hold}",
             f"  Unassigned:         {s.unassigned}",
             f"  Resolved (30 days): {s.resolved_in_period} "
             f"({s.sla_met_in_period} within target)",
             f"  Average time to resolve: "
             f"{s.avg_resolution_hours if s.avg_resolution_hours is not None else '—'} h",
             "", "Open by category (open / overdue)"]
    rows = data.open_by_category()
    lines += [f"  {k:<5} {c:<28} {n:>4} {o:>4}" for k, c, n, o in rows] \
        or ["  (none)"]
    lines += ["", "Open by assignee"]
    lines += [f"  {k:<30} {v:>4}" for k, v in
              sorted(s.open_by_assignee.items(), key=lambda kv: -kv[1])] \
        or ["  (none)"]
    lines += ["", "Open by priority"]
    lines += [f"  {p:<10} {s.open_by_priority.get(p, 0):>4}"
              for p in data.PRIORITIES]
    period = (f" {date_from or 'start'} to {date_to or 'today'}"
              if date_from or date_to else " (all time)")
    lines += ["", f"Target performance{period}",
              "  Priority   Target  Resolved  In target  Avg hours"]
    for pr, n, met, avg in data.sla_performance(date_from=date_from,
                                                date_to=date_to):
        pct = f"{round(100 * met / n)}%" if n else "—"
        lines.append(f"  {pr:<10} {data.SLA_HOURS[pr]:>4}h  {n:>8}  "
                     f"{met:>5} {pct:>4}  {avg if avg is not None else '—':>9}")
    return lines


def _ticket_detail(parent: tk.Misc, ticket_id: int, after) -> None:
    """History and comments for one ticket."""
    t = data.get_ticket(ticket_id)
    top = tk.Toplevel(parent.winfo_toplevel())
    top.title(f"{t.reference} — {t.title}")
    window_sizing.fit(top, "860x640", (560, 420))
    top.transient(parent.winfo_toplevel())

    head = ttk.Frame(top, padding=10)
    head.pack(fill="x")
    info = ttk.Label(head, justify="left", wraplength=800)
    info.pack(anchor="w")

    # Comment bar first so it stays on screen.
    bottom = ttk.Frame(top, padding=10)
    bottom.pack(side="bottom", fill="x")
    entry = tk.Text(bottom, height=3, wrap="word")
    entry.pack(side="left", fill="x", expand=True)
    internal = tk.BooleanVar(value=False)
    side = ttk.Frame(bottom)
    side.pack(side="right", padx=(8, 0))
    if data.can_manage():
        ttk.Checkbutton(side, text="Internal note",
                        variable=internal).pack(anchor="w")

    body = ttk.Frame(top, padding=(10, 0))
    body.pack(fill="both", expand=True)
    hist = tk.Text(body, wrap="word", state="disabled")
    sb = ttk.Scrollbar(body, orient="vertical", command=hist.yview)
    hist.configure(yscrollcommand=sb.set)
    hist.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    def load() -> None:
        tk_ = data.get_ticket(ticket_id)
        info.configure(text=(
            f"{tk_.reference}  {tk_.kind} / {tk_.category}  —  "
            f"{tk_.priority}, {tk_.status}\n"
            f"Where: {tk_.location or '—'}"
            + (f"   Asset: {tk_.asset_tag}" if tk_.asset_tag else "")
            + f"\nRaised by {tk_.raised_by_name or tk_.raised_by} at "
            f"{tk_.raised_at.replace('T', ' ')[:16]}; assigned to "
            f"{tk_.assignee_name or 'nobody yet'}; target "
            f"{tk_.sla_due_at.replace('T', ' ')[:16]}"
            + (f"\nOn hold: {tk_.hold_reason}" if tk_.hold_reason else "")
            + (f"\nResolution: {tk_.resolution}" if tk_.resolution else "")
            + (f"\n\n{tk_.description}" if tk_.description else "")))
        hist.configure(state="normal")
        hist.delete("1.0", "end")
        for u in data.list_updates(ticket_id):
            hist.insert("end", f"{u.at.replace('T', ' ')[:16]}  "
                               f"{u.author or ''}  [{u.kind}]\n  {u.body}\n\n")
        hist.configure(state="disabled")
        hist.see("end")

    def add() -> None:
        text = entry.get("1.0", "end-1c").strip()
        try:
            data.add_comment(ticket_id, text, internal=internal.get())
        except ValueError as exc:
            rt.warn(top, "Comment", str(exc))
            return
        except PermissionError as exc:
            rt.warn(top, "Comment", str(exc))
            return
        entry.delete("1.0", "end")
        load()
        if after:
            after()

    ttk.Button(side, text="Add comment", command=add).pack(fill="x")
    ttk.Button(side, text="Close window", command=top.destroy).pack(
        fill="x", pady=(4, 0))
    load()
    grab_when_viewable(top)
