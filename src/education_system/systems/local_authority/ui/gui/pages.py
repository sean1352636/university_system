"""The Local Authority Education pages that aren't a plain record list: the
children directory, child profile, chronology and the reports. Each is
``draw(parent, app)``, where *app* is the main window (for ``principal``,
``show_learner``, ``open_page``, ``status`` and ``state_for``)."""

from __future__ import annotations

import tkinter as tk
from collections import Counter
from datetime import date
from tkinter import ttk
from typing import TYPE_CHECKING

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.local_authority.app import routing
from education_system.systems.local_authority.core import dates
from education_system.systems.local_authority.core import records as r
from education_system.systems.local_authority.modules import (
    children,
    exclusions,
    reports,
    schools,
    send,
    transport,
    welfare,
)
from education_system.systems.local_authority.ui.gui import kit

if TYPE_CHECKING:
    from education_system.systems.local_authority.app.gui_main import LAMainGUI


# ── children ────────────────────────────────────────────────────────

def draw_directory(parent: ttk.Frame, app: "LAMainGUI") -> None:
    kit.draw_records(parent, children.CHILDREN, principal=app.principal,
                     state=app.state_for("learners"), on_status=app.status,
                     on_open=lambda row: app.show_learner(row["id"]),
                     subtitle="Children and young people known to the authority. Double-click "
                              "a child to open their profile.")


def draw_learner_picker(parent: ttk.Frame, app: "LAMainGUI") -> None:
    kit.heading(parent, "Child Profile", "Choose a child to see admissions, attendance, "
                                         "exclusions, SEND and transport in one place.")
    kit.draw_records(parent, children.CHILDREN, principal=app.principal,
                     state=app.state_for("learner_picker"), on_status=app.status,
                     on_open=lambda row: app.show_learner(row["id"]), show_heading=False)


def _alerts(row: dict, child_id: int) -> list[str]:
    out = []
    if children.compulsory_school_age(row) and row["education"] == "Not in education":
        out.append("Of compulsory school age and not in education")
    if row.get("social_care") not in (None, "None known"):
        out.append(row["social_care"])
    if row.get("sen_status") not in (None, "No SEN"):
        out.append(row["sen_status"])
    if r.list_records(welfare.CME, learner_id=child_id, equals={"status": "Open"}):
        out.append("Open CME case")
    if r.list_records(welfare.ATTENDANCE_CASES, learner_id=child_id,
                      equals={"status": "Open"}):
        out.append("Open attendance case")
    if any(x["kind"] == exclusions.KINDS[1] and x.get("outcome") != "Reinstated"
           for x in r.list_records(exclusions.EXCLUSIONS, learner_id=child_id)):
        out.append("Permanently excluded")
    if any(c.get("no_contact") for c in r.list_records(children.CONTACTS,
                                                       learner_id=child_id)):
        out.append("Contact restriction")
    return out


def draw_learner(parent: ttk.Frame, app: "LAMainGUI", learner_id: int) -> None:
    row = r.get(children.CHILDREN, learner_id)
    if row is None:
        kit.heading(parent, "Child not found", "They may have been deleted.")
        return
    top = ttk.Frame(parent)
    top.pack(fill="x")
    name = f"{row['first_name']} {row['last_name']}"
    if row.get("preferred_name"):
        name += f" ({row['preferred_name']})"
    dob = r.to_date(row.get("dob"))
    ttk.Label(top, text=name, font=("", 18, "bold")).pack(side="left")
    ttk.Label(top, text=f"  {row['child_ref']} · {children.year_group(dob)} · "
                        f"{row['status']}", foreground=kit.MUTED,
              font=("", 12)).pack(side="left")
    buttons = ttk.Frame(top)
    buttons.pack(side="right")

    def edit() -> None:
        kit.open_form(parent, children.CHILDREN, row, principal=app.principal,
                      on_saved=lambda _id: app.show_learner(learner_id))

    def toggle_archive() -> None:
        archived = row["status"] == "Archived"
        if not archived and not messagebox.askyesno(
                "Archive", f"Archive {name}? Their records are kept and can be restored.",
                parent=parent):
            return
        try:
            r.save(children.CHILDREN, {"status": "Resident" if archived else "Archived"},
                   record_id=learner_id, actor=app.principal.username)
        except r.ValidationError as exc:
            messagebox.showwarning("Can't change status", str(exc), parent=parent)
            return
        app.status(f"{name} {'restored' if archived else 'archived'}")
        app.show_learner(learner_id)

    if app.principal.can_edit("learners"):
        ttk.Button(buttons, text="Edit details", command=edit).pack(side="left", padx=4)
        ttk.Button(buttons, text="Restore" if row["status"] == "Archived" else "Archive",
                   command=toggle_archive).pack(side="left")

    alerts = _alerts(row, learner_id)
    if alerts:
        ttk.Label(parent, text="⚠ " + " · ".join(alerts), foreground=kit.OVERDUE_FG,
                  font=("", 10, "bold")).pack(anchor="w", pady=(4, 0))

    contact = children.main_contact(learner_id)
    plan = next(iter(r.list_records(send.EHC_PLANS, learner_id=learner_id,
                                    equals={"status": "Active"})), None)
    ride = next(iter(r.list_records(transport.TRANSPORT, learner_id=learner_id,
                                    equals={"status": "Agreed"})), None)
    facts = [
        ("Date of birth", f"{dates.uk(dob)} (age {dates.age_on(dob, date.today())})"
         if dob else ""),
        ("UPN", row.get("upn")),
        ("Education", row["education"]),
        ("School / setting", schools.school_name(row.get("school_id"))),
        ("SEN", row["sen_status"] + (f" (review {dates.uk(r.to_date(plan['next_review']))})"
                                     if plan and plan.get("next_review") else "")),
        ("Social care", row.get("social_care")),
        ("Main contact", f"{contact['name']} ({contact['relationship']}) "
                         f"{contact.get('phone') or contact.get('email') or ''}"
         if contact else "None recorded"),
        ("Transport", f"Route {(r.get(transport.ROUTES, ride['route_id']) or {}).get('code')}"
         if ride and ride.get("route_id") else "None"),
        ("Address", " ".join(x for x in (row.get("address_line1"), row.get("town"),
                                         row.get("postcode")) if x)),
        ("Free school meals / EAL", f"{'Yes' if row.get('free_school_meals') else 'No'} / "
                                   f"{'Yes' if row.get('eal') else 'No'}"),
    ]
    grid = ttk.Frame(parent)
    grid.pack(fill="x", pady=(6, 4))
    for i, (k, v) in enumerate(facts):
        ttk.Label(grid, text=f"{k}:", foreground=kit.MUTED).grid(
            row=i // 2, column=(i % 2) * 2, sticky="w", padx=(0, 6), pady=1)
        ttk.Label(grid, text=v or "—", wraplength=380, justify="left").grid(
            row=i // 2, column=(i % 2) * 2 + 1, sticky="w", padx=(0, 30), pady=1)
    if row.get("notes"):
        ttk.Label(parent, text=row["notes"], wraplength=900, justify="left",
                  foreground="#333").pack(anchor="w", pady=(4, 0))

    state = app.state_for(f"learner:{learner_id}")
    book = ttk.Notebook(parent)
    book.pack(fill="both", expand=True, pady=(10, 0))
    tabs: dict[str, tuple[ttk.Frame, object]] = {}
    for label, key in routing.PROFILE_TABS:
        frame = ttk.Frame(book, padding=6)
        book.add(frame, text=label)
        tabs[str(frame)] = (frame, r.REGISTRY[key])
    chron = ttk.Frame(book, padding=6)
    book.add(chron, text="Chronology")
    tabs[str(chron)] = (chron, "chronology")
    drawn: set[str] = set()

    def on_tab(_e=None) -> None:
        key = book.select()
        state["tab"] = key and book.index(key)
        if not key or key in drawn:
            return
        drawn.add(key)
        frame, rt = tabs[key]
        if rt == "chronology":
            _draw_history(frame, r.history(learner_id=learner_id))
        else:
            kit.draw_records(frame, rt, principal=app.principal,  # type: ignore[arg-type]
                             state=state.setdefault(rt.key, {}),  # type: ignore[attr-defined]
                             learner_id=learner_id, on_status=app.status, show_heading=False)

    book.bind("<<NotebookTabChanged>>", on_tab)
    if state.get("tab"):
        book.select(state["tab"])
    on_tab()


def _draw_history(parent: tk.Misc, rows: list[dict], with_learner: bool = False) -> None:
    cols = [("at", "When", 140), ("actor", "Who", 100)]
    if with_learner:
        cols.append(("learner", "Child", 180))
    cols.append(("summary", "What happened", 560))
    tree = kit.make_tree(parent, cols)
    names = dict(children.learner_options(include_archived=True)) if with_learner else {}
    for row in rows:
        values = [row["at"], row["actor"]]
        if with_learner:
            values.append(names.get(row.get("learner_id"), ""))
        tree.insert("", "end", values=[*values, row["summary"]])
    if not rows:
        ttk.Label(parent, text="Nothing recorded yet.", foreground=kit.MUTED).pack(anchor="w")


def draw_chronology(parent: ttk.Frame, app: "LAMainGUI") -> None:  # noqa: ARG001
    kit.heading(parent, "Chronology", "Every change to the records, newest first. Pick a "
                                      "child to see only theirs.")
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 6))
    ids = {label: i for i, label in children.learner_options(include_archived=True)}
    var = tk.StringVar(value="All children")
    ttk.Label(bar, text="Child:").pack(side="left")
    box = ttk.Combobox(bar, textvariable=var, values=["All children", *ids],
                       state="readonly", width=40)
    box.pack(side="left", padx=4)
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)

    def refresh(_e=None) -> None:
        for w in holder.winfo_children():
            w.destroy()
        lid = ids.get(var.get())
        _draw_history(holder, r.history(learner_id=lid, limit=500), with_learner=lid is None)

    box.bind("<<ComboboxSelected>>", refresh)
    refresh()


# ── reports ─────────────────────────────────────────────────────────

def draw_due(parent: ttk.Frame, app: "LAMainGUI") -> None:
    kit.heading(parent, "Due & Overdue", "Admission decisions, appeal hearings and letters, "
                                         "fair access targets, attendance reviews, penalty "
                                         "notice deadlines, CME enquiries, EHE reviews, "
                                         "exclusion reviews and day-6 provision, EHC "
                                         "timescales and reviews, tribunals, transport "
                                         "decisions and route contracts in the next 60 days, "
                                         "plus anything overdue.")
    items = reports.due_items(60)
    tree = kit.make_tree(parent, [("due", "Due", 100), ("when", "", 110),
                                  ("what", "What", 460), ("learner", "Child", 180)])
    by_iid: dict[str, reports.DueItem] = {}
    for item in items:
        days = (item.due - date.today()).days
        when = f"{-days}d overdue" if days < 0 else ("today" if days == 0 else f"in {days}d")
        iid = tree.insert("", "end", values=[dates.uk(item.due), when, item.what, item.learner],
                          tags=("overdue",) if item.overdue else ())
        by_iid[iid] = item

    def open_item(_e) -> None:
        sel = tree.selection()
        if sel and by_iid[sel[0]].learner_id:
            app.show_learner(by_iid[sel[0]].learner_id)  # type: ignore[arg-type]
        elif sel:
            app.open_page(by_iid[sel[0]].area)

    tree.bind("<Double-1>", open_item)
    if not items:
        ttk.Label(parent, text="Nothing due.", foreground=kit.MUTED).pack(anchor="w")


def draw_school_notifications(parent: ttk.Frame, app: "LAMainGUI") -> None:
    kit.heading(parent, "School Notifications", "What the schools linked on the platform "
                                                "have sent - attendance referrals, "
                                                "suspensions and exclusions, children "
                                                "missing education, home education, EHC "
                                                "needs assessment requests - and the school "
                                                "places handed to them. Mark a school as "
                                                "this platform's primary or secondary in "
                                                "the Schools Register.")
    items = reports.school_notifications()
    tree = kit.make_tree(parent, [("on", "Date", 100), ("what", "What", 300),
                                  ("learner", "Child", 190), ("school", "School", 170),
                                  ("status", "Status", 200)])
    by_iid: dict[str, reports.LinkedItem] = {}
    for item in items:
        on = r.to_date(item.on)
        iid = tree.insert("", "end", values=[dates.uk(on) if on else "", item.what,
                                             item.learner, item.school, item.status])
        by_iid[iid] = item

    def open_item(_e) -> None:
        sel = tree.selection()
        if sel and by_iid[sel[0]].learner_id:
            app.show_learner(by_iid[sel[0]].learner_id)  # type: ignore[arg-type]
        elif sel:
            app.open_page(by_iid[sel[0]].area)

    tree.bind("<Double-1>", open_item)
    if not items:
        ttk.Label(parent, text="Nothing from the linked schools yet.",
                  foreground=kit.MUTED).pack(anchor="w")


def _table(parent: tk.Misc, cols: list[tuple[str, str, int]], rows: list[list],
           overdue: list[bool] | None = None) -> ttk.Treeview:
    tree = kit.make_tree(parent, cols)
    for i, values in enumerate(rows):
        tree.insert("", "end", values=values,
                    tags=("overdue",) if overdue and overdue[i] else ())
    if not rows:
        ttk.Label(parent, text="Nothing to show yet.", foreground=kit.MUTED).pack(anchor="w")
    return tree


def _counts(parent: tk.Misc, groups: dict[str, Counter], per_row: int = 3) -> None:
    grid = ttk.Frame(parent)
    grid.pack(fill="both", expand=True)
    for i, (title, counts) in enumerate(groups.items()):
        box = ttk.LabelFrame(grid, text=title, padding=8)
        box.grid(row=i // per_row, column=i % per_row, sticky="nsew", padx=4, pady=4)
        grid.columnconfigure(i % per_row, weight=1, uniform="sum")
        total = sum(counts.values())
        for name, n in sorted(counts.items(), key=lambda x: -x[1]):
            line = ttk.Frame(box)
            line.pack(fill="x")
            ttk.Label(line, text=name).pack(side="left")
            shown = f"{n:g}" if isinstance(n, float) else str(n)
            ttk.Label(line, text=f"{shown}  ({round(100 * n / total)}%)").pack(side="right")
        if not counts:
            ttk.Label(box, text="Nothing yet.", foreground=kit.MUTED).pack(anchor="w")


def draw_admissions_report(parent: ttk.Frame, app: "LAMainGUI") -> None:  # noqa: ARG001
    rate = reports.first_preference_rate()
    kit.heading(parent, "Admissions Summary", "Applications, offers, appeals and fair access. "
                + (f"Normal-round offers of a first preference: {rate}%." if rate is not None
                   else "No normal-round offers yet."))
    _counts(parent, reports.admissions_summary())


def draw_places_report(parent: ttk.Frame, app: "LAMainGUI") -> None:  # noqa: ARG001
    kit.heading(parent, "School Places", "Open schools: admission number, first preferences "
                                         "and offers across the rounds on record, capacity "
                                         "and surplus places. Red: more first preferences "
                                         "than places (oversubscribed).")
    rows = reports.school_places()
    _table(parent, [("s", "School", 240), ("p", "Phase", 100), ("pan", "PAN", 60),
                    ("f", "1st prefs", 80), ("o", "Offers", 70), ("c", "Capacity", 80),
                    ("r", "On roll", 70), ("x", "Surplus", 100)],
           [[x["school"], x["phase"], x["pan"] if x["pan"] is not None else "",
             x["first_prefs"], x["offers"], x["capacity"] or "", x["on_roll"] or "",
             x["surplus"]] for x in rows], [x["over"] for x in rows])


def draw_welfare_report(parent: ttk.Frame, app: "LAMainGUI") -> None:  # noqa: ARG001
    kit.heading(parent, "Attendance & Welfare", "Attendance casework, penalty notices, "
                                                "children missing education, home education "
                                                "and how children of compulsory school age "
                                                "are educated.")
    _counts(parent, reports.welfare_summary())


def draw_exclusions_report(parent: ttk.Frame, app: "LAMainGUI") -> None:  # noqa: ARG001
    kit.heading(parent, "Exclusions Summary", "Suspensions and permanent exclusions this "
                                              "school year, by reason and school.")
    _counts(parent, reports.exclusions_summary())


def draw_send_report(parent: ttk.Frame, app: "LAMainGUI") -> None:  # noqa: ARG001
    t = reports.send_timeliness()
    kit.heading(parent, "SEND Summary",
                (f"{t['on_time']} of {t['issued']} final EHC plans issued within 20 weeks "
                 f"({t['rate']}%). " if t["issued"] else "No final plans issued yet. ")
                + f"High-needs top-ups running now: £{reports.high_needs_cost():,.0f} a year.")
    _counts(parent, reports.send_summary(), per_row=2)


def draw_transport_report(parent: ttk.Frame, app: "LAMainGUI") -> None:  # noqa: ARG001
    rows = transport.route_costs()
    kit.heading(parent, "Transport Costs", f"Active routes by annual cost "
                                           f"({transport.SCHOOL_DAYS} school days).")
    _table(parent, [("r", "Route", 90), ("o", "Operator", 200), ("v", "Vehicle", 120),
                    ("c", "Children", 80), ("d", "Per day", 90), ("a", "Per year", 110),
                    ("p", "Per child", 110)],
           [[x["route"], x["operator"], x["vehicle"], x["children"], f"£{x['daily']:,.2f}",
             f"£{x['annual']:,.0f}", "—" if x["per_child"] is None
             else f"£{x['per_child']:,.0f}"] for x in rows])
    if rows:
        ttk.Label(parent, text=f"Total £{sum(x['annual'] for x in rows):,.0f} a year",
                  font=("", 10, "bold")).pack(anchor="w", pady=(6, 0))


#: Menu keys with their own page (everything else in the catalogue is a record type).
CUSTOM = {
    "learners": ("Children Directory", draw_directory),
    "learner_profile": ("Child Profile", draw_learner_picker),
    "chronology": ("Chronology", draw_chronology),
    "due_report": ("Due & Overdue", draw_due),
    "school_notifications": ("School Notifications", draw_school_notifications),
    "admissions_report": ("Admissions Summary", draw_admissions_report),
    "places_report": ("School Places", draw_places_report),
    "welfare_report": ("Attendance & Welfare", draw_welfare_report),
    "exclusions_report": ("Exclusions Summary", draw_exclusions_report),
    "send_report": ("SEND Summary", draw_send_report),
    "transport_report": ("Transport Costs", draw_transport_report),
}

