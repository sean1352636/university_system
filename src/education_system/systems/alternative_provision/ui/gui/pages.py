"""The Alternative Provision pages that aren't a plain record list: pupil
profile, chronology, Take Register and the reports. Each is
``draw(parent, app)``, where *app* is the main window (for ``principal``,
``show_learner``, ``status`` and ``state_for``)."""

from __future__ import annotations

import tkinter as tk
from collections import Counter
from datetime import date, datetime
from tkinter import ttk
from typing import TYPE_CHECKING

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.alternative_provision.app import routing
from education_system.systems.alternative_provision.core import dates
from education_system.systems.alternative_provision.core import records as r
from education_system.systems.alternative_provision.modules import (
    attendance,
    learners,
    placements,
    referrals,
    reports,
    safeguarding,
)
from education_system.systems.alternative_provision.ui.gui import kit

if TYPE_CHECKING:
    from education_system.systems.alternative_provision.app.gui_main import APMainGUI


# ── pupils ──────────────────────────────────────────────────────────

def draw_directory(parent: ttk.Frame, app: "APMainGUI") -> None:
    kit.draw_records(parent, learners.LEARNERS, principal=app.principal,
                     state=app.state_for("learners"), on_status=app.status,
                     on_open=lambda row: app.show_learner(row["id"]),
                     subtitle="Every pupil, from referral on. Double-click a pupil to open "
                              "their profile.")


def draw_learner_picker(parent: ttk.Frame, app: "APMainGUI") -> None:
    kit.heading(parent, "Pupil Profile", "Choose a pupil to see everything about them in one "
                                         "place.")
    kit.draw_records(parent, learners.LEARNERS, principal=app.principal,
                     state=app.state_for("learner_picker"), on_status=app.status,
                     on_open=lambda row: app.show_learner(row["id"]), show_heading=False)


def _alerts(row: dict, learner_id: int) -> list[str]:
    out = []
    if row.get("looked_after"):
        out.append("Looked after")
    if row.get("social_care") in ("Child in need", "Child protection plan"):
        out.append(row["social_care"])
    if row.get("sen_status") not in (None, "No SEN"):
        out.append(row["sen_status"])
    risk = referrals.current_risk(learner_id)
    if risk and risk["overall"] != "Low":
        out.append(f"{risk['overall']} risk")
    open_concerns = r.list_records(safeguarding.CONCERNS, learner_id=learner_id,
                                   equals={"status": "Open"})
    if open_concerns:
        out.append(f"{len(open_concerns)} open safeguarding concern(s)")
    if row.get("medical_notes"):
        out.append("Medical needs")
    if any(c.get("no_contact") for c in r.list_records(learners.CONTACTS,
                                                         learner_id=learner_id)):
        out.append("Contact restriction")
    return out


def draw_learner(parent: ttk.Frame, app: "APMainGUI", learner_id: int) -> None:
    row = r.get(learners.LEARNERS, learner_id)
    if row is None:
        kit.heading(parent, "Pupil not found", "They may have been deleted.")
        return
    top = ttk.Frame(parent)
    top.pack(fill="x")
    name = f"{row['first_name']} {row['last_name']}"
    if row.get("preferred_name"):
        name += f" ({row['preferred_name']})"
    ttk.Label(top, text=name, font=("", 18, "bold")).pack(side="left")
    ttk.Label(top, text=f"  {row['pupil_ref']} · {row['year_group']} · {row['status']}",
              foreground=kit.MUTED, font=("", 12)).pack(side="left")
    buttons = ttk.Frame(top)
    buttons.pack(side="right")

    def edit() -> None:
        kit.open_form(parent, learners.LEARNERS, row, principal=app.principal,
                      on_saved=lambda _id: app.show_learner(learner_id))

    def toggle_archive() -> None:
        archived = row["status"] == "Archived"
        new = (row.get("status_before_archive") or "Referred") if archived else "Archived"
        if not archived and not messagebox.askyesno(
                "Archive", f"Archive {name}? Their records are kept and can be restored.",
                parent=parent):
            return
        try:
            r.save(learners.LEARNERS, {"status": new}, record_id=learner_id,
                   actor=app.principal.username)
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

    dob = r.to_date(row.get("dob"))
    live = placements.active_placements(learner_id)
    providers = {p["id"]: p["name"] for p in r.list_records(placements.PROVIDERS)}
    placed = "; ".join(f"{providers.get(p['provider_id'], '?')} "
                       f"({float(p['hours_per_week']):g}h)" for p in live)
    rate = attendance.rate(learner_id, days=(date.today() -
                                             dates.school_year_start(date.today())).days)
    contact = learners.main_contact(learner_id)
    facts = [
        ("Date of birth", f"{dates.uk(dob)} (age {dates.age_on(dob, date.today())})" if dob else ""),
        ("UPN", row.get("upn")),
        ("Home / main school", row.get("home_school")),
        ("Registration", row.get("registration")),
        ("Placed with", placed or "No active placement"),
        ("Attendance this year", "—" if rate is None else f"{rate:g}%"
         + (" (persistent absence)" if rate < attendance.PERSISTENT_ABSENCE else "")),
        ("Key worker", row.get("key_worker")),
        ("Main contact", f"{contact['name']} ({contact['relationship']}) "
                         f"{contact.get('phone') or contact.get('email') or ''}"
         if contact else "None recorded"),
        ("Local authority", row.get("local_authority")),
        ("Pupil premium / FSM", f"{'Yes' if row.get('pupil_premium') else 'No'} / "
                                f"{'Yes' if row.get('free_school_meals') else 'No'}"),
        ("Started", dates.uk(r.to_date(row.get("start_date")))),
        ("Left", dates.uk(r.to_date(row.get("leave_date")))),
    ]
    grid = ttk.Frame(parent)
    grid.pack(fill="x", pady=(6, 4))
    for i, (k, v) in enumerate(facts):
        ttk.Label(grid, text=f"{k}:", foreground=kit.MUTED).grid(
            row=i // 2, column=(i % 2) * 2, sticky="w", padx=(0, 6), pady=1)
        ttk.Label(grid, text=v or "—").grid(row=i // 2, column=(i % 2) * 2 + 1, sticky="w",
                                            padx=(0, 30), pady=1)
    for key in ("medical_notes", "notes"):
        if row.get(key):
            ttk.Label(parent, text=row[key], wraplength=900, justify="left",
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
        cols.append(("learner", "Pupil", 180))
    cols.append(("summary", "What happened", 560))
    tree = kit.make_tree(parent, cols)
    names = dict(learners.learner_options(include_archived=True)) if with_learner else {}
    for row in rows:
        values = [row["at"], row["actor"]]
        if with_learner:
            values.append(names.get(row.get("learner_id"), ""))
        tree.insert("", "end", values=[*values, row["summary"]])
    if not rows:
        ttk.Label(parent, text="Nothing recorded yet.", foreground=kit.MUTED).pack(anchor="w")


def draw_chronology(parent: ttk.Frame, app: "APMainGUI") -> None:  # noqa: ARG001
    kit.heading(parent, "Chronology", "Every change to pupil records, newest first. Pick a "
                                      "pupil to see only theirs.")
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 6))
    ids = {label: i for i, label in learners.learner_options(include_archived=True)}
    var = tk.StringVar(value="All pupils")
    ttk.Label(bar, text="Pupil:").pack(side="left")
    box = ttk.Combobox(bar, textvariable=var, values=["All pupils", *ids], state="readonly",
                       width=40)
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


# ── take register ───────────────────────────────────────────────────

def draw_take_register(parent: ttk.Frame, app: "APMainGUI") -> None:
    kit.heading(parent, "Take Register", "Pick the date and session, mark every pupil on roll, "
                                         "then save. Marks already made are shown. An "
                                         "authorised absence needs a reason.")
    state = app.state_for("take_register")
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    date_var = tk.StringVar(value=state.get("date") or date.today().strftime("%d/%m/%Y"))
    session_var = tk.StringVar(value=state.get("session") or
                               ("AM" if datetime.now().hour < 12 else "PM"))
    ttk.Label(bar, text="Date:").pack(side="left")
    ttk.Entry(bar, textvariable=date_var, width=12).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Session:").pack(side="left")
    ttk.Combobox(bar, textvariable=session_var, values=attendance.SESSIONS, state="readonly",
                 width=5).pack(side="left", padx=4)
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    rows_vars: dict[int, tuple[tk.StringVar, tk.StringVar]] = {}

    def load() -> None:
        for w in holder.winfo_children():
            w.destroy()
        rows_vars.clear()
        try:
            on = date.fromisoformat(r.parse_date(date_var.get()) or "")
        except (ValueError, r.ValidationError) as exc:
            ttk.Label(holder, text=str(exc), foreground=kit.OVERDUE_FG).pack(anchor="w")
            return
        state.update({"date": date_var.get(), "session": session_var.get()})
        rows = attendance.register(on, session_var.get())
        if not rows:
            ttk.Label(holder, text="Nobody was on roll on that day.",
                      foreground=kit.MUTED).pack(anchor="w")
            return
        for col, text in enumerate(("Pupil", "Mark", "Reason / note")):
            ttk.Label(holder, text=text, foreground=kit.MUTED).grid(row=0, column=col,
                                                                   sticky="w", padx=(0, 12))
        for i, row in enumerate(rows, start=1):
            ttk.Label(holder, text=f"{row['name']}  ({row['pupil_ref']})").grid(
                row=i, column=0, sticky="w", pady=2, padx=(0, 12))
            mark = tk.StringVar(value=row["mark"] or "")
            reason = tk.StringVar(value=row["reason"] or "")
            ttk.Combobox(holder, textvariable=mark, values=attendance.MARKS, state="readonly",
                         width=30).grid(row=i, column=1, sticky="w", padx=(0, 12))
            ttk.Entry(holder, textvariable=reason, width=40).grid(row=i, column=2, sticky="w")
            rows_vars[row["learner_id"]] = (mark, reason)

    def all_present() -> None:
        for mark, _reason in rows_vars.values():
            if not mark.get():
                mark.set(attendance.MARKS[0])

    def save() -> None:
        try:
            on = date.fromisoformat(r.parse_date(date_var.get()) or "")
            n = attendance.save_register(on, session_var.get(),
                                         {k: (m.get(), why.get())
                                          for k, (m, why) in rows_vars.items()},
                                         actor=app.principal.username)
        except r.ValidationError as exc:
            messagebox.showwarning("Register not saved", str(exc), parent=parent)
            return
        except ValueError:
            messagebox.showwarning("Register not saved", "Check the date.", parent=parent)
            return
        app.status(f"Register saved: {n} mark(s)")
        load()

    ttk.Button(bar, text="Load", command=load).pack(side="left", padx=4)
    actions = ttk.Frame(parent)
    actions.pack(fill="x", pady=(8, 0))
    ttk.Button(actions, text="Mark the rest present", command=all_present).pack(side="left")
    ttk.Button(actions, text="Save register", command=save).pack(side="left", padx=6)
    load()


# ── reports ─────────────────────────────────────────────────────────

def draw_due(parent: ttk.Frame, app: "APMainGUI") -> None:
    kit.heading(parent, "Due & Overdue", "Sixth-day provision deadlines, referral decisions, "
                                         "placement and part-time timetable reviews, risk and "
                                         "plan reviews, return interviews, DSL reviews, "
                                         "reintegration follow-ups, provider QA visits and "
                                         "invoices in the next 60 days, plus anything overdue.")
    items = reports.due_items(60)
    tree = kit.make_tree(parent, [("due", "Due", 100), ("when", "", 110),
                                  ("what", "What", 420), ("learner", "Pupil", 200)])
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


def draw_roll_report(parent: ttk.Frame, app: "APMainGUI") -> None:  # noqa: ARG001
    kit.heading(parent, "Roll Summary", "Who is on roll now: year groups, SEN, social care, "
                                        "disadvantage, why they were referred and where they "
                                        "are placed.")
    _counts(parent, reports.roll_summary())


def draw_attendance_report(parent: ttk.Frame, app: "APMainGUI") -> None:
    kit.heading(parent, "Attendance Report", "Every pupil on roll, lowest attendance first. "
                                             "Under 90% (persistent absence) is shown in red. "
                                             "Double-click to open the pupil.")
    rows = reports.attendance_report()

    def pct(v: float | None) -> str:
        return "—" if v is None else f"{v:g}%"

    tree = _table(parent, [("l", "Pupil", 260), ("y", "This school year", 140),
                           ("m", "Last 30 days", 120)],
                  [[x["learner"], pct(x["rate"]), pct(x["last_30"])] for x in rows],
                  [x["persistent"] for x in rows])
    ids = {iid: rows[i]["learner_id"] for i, iid in enumerate(tree.get_children())}
    tree.bind("<Double-1>", lambda _e: tree.selection() and
              app.show_learner(ids[tree.selection()[0]]))


def draw_behaviour_report(parent: ttk.Frame, app: "APMainGUI") -> None:  # noqa: ARG001
    kit.heading(parent, "Behaviour Summary", "Incidents, use of force, suspensions and "
                                             "exclusions this school year.")
    _counts(parent, reports.behaviour_summary())


def draw_costs_report(parent: ttk.Frame, app: "APMainGUI") -> None:
    kit.heading(parent, "Placement Costs", "Active placements by weekly cost (days a week x "
                                           "daily rate). Double-click to open the pupil.")
    rows = reports.placement_costs()
    tree = _table(parent, [("l", "Pupil", 200), ("p", "Provider", 240), ("h", "Hours", 70),
                           ("c", "Commissioned by", 160), ("w", "Cost / week", 110)],
                  [[x["learner"], x["provider"], f"{x['hours']:g}", x["commissioned_by"],
                    f"£{x['weekly']:,.2f}"] for x in rows])
    ids = {iid: rows[i]["learner_id"] for i, iid in enumerate(tree.get_children())}
    tree.bind("<Double-1>", lambda _e: tree.selection() and
              app.show_learner(ids[tree.selection()[0]]))
    if rows:
        week = sum(x["weekly"] for x in rows)
        ttk.Label(parent, text=f"Total £{week:,.2f} a week (about £{week * 39:,.0f} over a "
                               "39-week school year)",
                  font=("", 10, "bold")).pack(anchor="w", pady=(6, 0))


def draw_outcomes_report(parent: ttk.Frame, app: "APMainGUI") -> None:  # noqa: ARG001
    rate = reports.reintegration_rate()
    kit.heading(parent, "Outcomes", "Reintegration plans, why placements ended and each "
                                    "pupil's latest destination. "
                                    + (f"Reintegration success rate: {rate}%." if rate is not None
                                       else "No reintegrations finished yet."))
    _counts(parent, reports.outcomes())


#: Menu keys with their own page (everything else in the catalogue is a record type).
CUSTOM = {
    "learners": ("Pupil Directory", draw_directory),
    "learner_profile": ("Pupil Profile", draw_learner_picker),
    "chronology": ("Chronology", draw_chronology),
    "take_register": ("Take Register", draw_take_register),
    "due_report": ("Due & Overdue", draw_due),
    "roll_report": ("Roll Summary", draw_roll_report),
    "attendance_report": ("Attendance Report", draw_attendance_report),
    "behaviour_report": ("Behaviour Summary", draw_behaviour_report),
    "costs_report": ("Placement Costs", draw_costs_report),
    "outcomes_report": ("Outcomes", draw_outcomes_report),
}
