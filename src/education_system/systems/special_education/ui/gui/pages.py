"""The SEND pages that aren't a plain record list: learner profile,
chronology and the reports. Each is ``draw(parent, app)``, where *app* is the
main window (for ``principal``, ``open_learner``, ``status`` and state)."""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import ttk
from typing import TYPE_CHECKING

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.special_education.app import routing
from education_system.systems.special_education.core import dates
from education_system.systems.special_education.core import records as r
from education_system.systems.special_education.modules import ehcp, learners, reports
from education_system.systems.special_education.ui.gui import kit

if TYPE_CHECKING:
    from education_system.systems.special_education.app.gui_main import SendMainGUI



# ── learners ────────────────────────────────────────────────────────

def draw_register(parent: ttk.Frame, app: "SendMainGUI") -> None:
    kit.draw_records(parent, learners.LEARNERS, principal=app.principal,
                     state=app.state_for("learners"), on_status=app.status,
                     on_open=lambda row: app.show_learner(row["id"]),
                     subtitle="Everyone on the SEND register. Double-click a learner to open "
                              "their profile.")


def draw_learner_picker(parent: ttk.Frame, app: "SendMainGUI") -> None:
    kit.heading(parent, "Learner Profile", "Choose a learner to see everything about them "
                                           "in one place.")
    kit.draw_records(parent, learners.LEARNERS, principal=app.principal,
                     state=app.state_for("learner_picker"), on_status=app.status,
                     on_open=lambda row: app.show_learner(row["id"]), show_heading=False)


def draw_learner(parent: ttk.Frame, app: "SendMainGUI", learner_id: int) -> None:
    row = r.get(learners.LEARNERS, learner_id)
    if row is None:
        kit.heading(parent, "Learner not found", "They may have been deleted.")
        return
    F = learners.LEARNERS.fields_by_name
    top = ttk.Frame(parent)
    top.pack(fill="x")
    name = f"{row['first_name']} {row['last_name']}"
    if row.get("preferred_name"):
        name += f" ({row['preferred_name']})"
    ttk.Label(top, text=name, font=("", 18, "bold")).pack(side="left")
    buttons = ttk.Frame(top)
    buttons.pack(side="right")

    def edit() -> None:
        kit.open_form(parent, learners.LEARNERS, row, principal=app.principal,
                      on_saved=lambda _id: app.show_learner(learner_id))

    def toggle_archive() -> None:
        new = "Active" if row["status"] == "Archived" else "Archived"
        if new == "Archived" and not messagebox.askyesno(
                "Archive", f"Archive {name}? Their records are kept and can be restored.",
                parent=parent):
            return
        r.save(learners.LEARNERS, {"status": new}, record_id=learner_id,
               actor=app.principal.username)
        app.status(f"{name} {'archived' if new == 'Archived' else 'restored'}")
        app.show_learner(learner_id)

    ttk.Button(buttons, text="Edit details", command=edit).pack(side="left", padx=4)
    ttk.Button(buttons, text="Restore" if row["status"] == "Archived" else "Archive",
               command=toggle_archive).pack(side="left")

    dob = r.to_date(row.get("dob"))
    facts = [
        ("SEN status", row.get("sen_status")),
        ("Primary need", row.get("primary_need")),
        ("Secondary need", row.get("secondary_need")),
        ("Date of birth", f"{dates.uk(dob)} (age {dates.age_on(dob, date.today())})" if dob else ""),
        ("Year group", row.get("year_group")),
        ("School / setting", row.get("setting")),
        ("Key worker", row.get("key_worker")),
        ("UPN", row.get("upn")),
        ("Identified", r.fmt(F["date_identified"], row.get("date_identified"))),
        ("Record", row.get("status")),
    ]
    grid = ttk.Frame(parent)
    grid.pack(fill="x", pady=(6, 4))
    for i, (k, v) in enumerate(facts):
        ttk.Label(grid, text=f"{k}:", foreground=kit.MUTED).grid(
            row=i // 2, column=(i % 2) * 2, sticky="w", padx=(0, 6), pady=1)
        ttk.Label(grid, text=v or "—").grid(row=i // 2, column=(i % 2) * 2 + 1, sticky="w",
                                            padx=(0, 30), pady=1)
    if row.get("notes"):
        ttk.Label(parent, text=row["notes"], wraplength=900, justify="left",
                  foreground="#333").pack(anchor="w", pady=(4, 0))

    open_ehcp = [x for x in ehcp.open_plans() if x["learner_id"] == learner_id]
    if open_ehcp:
        nxt = ehcp.next_deadline(open_ehcp[0])
        if nxt:
            ttk.Label(parent, text=f"EHCP ({open_ehcp[0]['stage']}): next - {nxt.what} "
                                   f"{dates.uk(nxt.due)}",
                      foreground=kit.OVERDUE_FG if nxt.overdue else "#1a5d1a").pack(
                anchor="w", pady=(4, 0))

    state = app.state_for(f"learner:{learner_id}")
    book = ttk.Notebook(parent)
    book.pack(fill="both", expand=True, pady=(10, 0))
    tabs: dict[str, tuple[ttk.Frame, object]] = {}
    for label, key in routing.PROFILE_TABS:
        rt = r.REGISTRY[key]
        frame = ttk.Frame(book, padding=6)
        book.add(frame, text=label)
        tabs[str(frame)] = (frame, rt)
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
        cols.append(("learner", "Learner", 160))
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


def draw_chronology(parent: ttk.Frame, app: "SendMainGUI") -> None:
    kit.heading(parent, "Chronology", "Every change to SEND records, newest first. Pick a "
                                      "learner to see only theirs.")
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 6))
    options = learners.learner_options(include_archived=True)
    ids = {label: i for i, label in options}
    var = tk.StringVar(value="All learners")
    ttk.Label(bar, text="Learner:").pack(side="left")
    box = ttk.Combobox(bar, textvariable=var, values=["All learners", *ids], state="readonly",
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


# ── reports ─────────────────────────────────────────────────────────

def draw_due(parent: ttk.Frame, app: "SendMainGUI") -> None:
    kit.heading(parent, "Due & Overdue", "Reviews, statutory EHCP deadlines, advice, care "
                                         "plans, equipment and meetings due in the next 60 "
                                         "days, plus anything overdue. Double-click to open "
                                         "the learner.")
    items = reports.due_items(60)
    tree = kit.make_tree(parent, [("due", "Due", 100), ("when", "", 110),
                                  ("what", "What", 340), ("learner", "Learner", 200)])
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

    tree.bind("<Double-1>", open_item)
    if not items:
        ttk.Label(parent, text="Nothing due.", foreground=kit.MUTED).pack(anchor="w")


def draw_register_summary(parent: ttk.Frame, app: "SendMainGUI") -> None:  # noqa: ARG001
    kit.heading(parent, "SEN Register Summary", "Active learners on the register (not "
                                                "archived, not 'No longer SEN').")
    summary = reports.register_summary()
    row = ttk.Frame(parent)
    row.pack(fill="both", expand=True)
    for i, (title, counts) in enumerate(summary.items()):
        box = ttk.LabelFrame(row, text=title, padding=8)
        box.grid(row=0, column=i, sticky="nsew", padx=4)
        row.columnconfigure(i, weight=1, uniform="sum")
        total = sum(counts.values())
        for name, n in sorted(counts.items(), key=lambda x: -x[1]):
            line = ttk.Frame(box)
            line.pack(fill="x")
            ttk.Label(line, text=name).pack(side="left")
            ttk.Label(line, text=f"{n}  ({round(100 * n / total)}%)").pack(side="right")
        if not counts:
            ttk.Label(box, text="No learners yet.", foreground=kit.MUTED).pack(anchor="w")


def draw_timeliness(parent: ttk.Frame, app: "SendMainGUI") -> None:
    kit.heading(parent, "EHCP 20-Week Timeliness",
                "Plans issued within 20 weeks of the request, and open requests already "
                "past 20 weeks.")
    t = ehcp.timeliness()
    pct = "—" if t["percent"] is None else f"{t['percent']}%"
    tiles = ttk.Frame(parent)
    tiles.pack(fill="x", pady=(0, 10))
    for i, (label, value) in enumerate([("Plans issued", t["issued"]),
                                        ("Within 20 weeks", t["on_time"]),
                                        ("Timeliness", pct),
                                        ("Open, past 20 weeks", len(t["overdue_open"]))]):
        tile = ttk.LabelFrame(tiles, padding=10)
        tile.grid(row=0, column=i, sticky="nsew", padx=4)
        tiles.columnconfigure(i, weight=1, uniform="t")
        ttk.Label(tile, text=label, foreground=kit.MUTED).pack(anchor="w")
        ttk.Label(tile, text=str(value), font=("", 20, "bold")).pack(anchor="w")
    if t["overdue_open"]:
        ttk.Label(parent, text="Open requests past 20 weeks", font=("", 11, "bold")).pack(
            anchor="w", pady=(6, 4))
        tree = kit.make_tree(parent, [("learner", "Learner", 200), ("req", "Requested", 100),
                                      ("stage", "Stage", 120), ("week", "Week", 80)], height=10)
        for row in t["overdue_open"]:
            tree.insert("", "end", tags=("overdue",), values=[
                row["learner_name"], dates.uk(r.to_date(row["request_date"])), row["stage"],
                ehcp._week(row)])


def draw_costs(parent: ttk.Frame, app: "SendMainGUI") -> None:  # noqa: ARG001
    kit.heading(parent, "Provision Costs", "Active provision per learner, with agreed "
                                           "high-needs funding for comparison.")
    rows = reports.provision_costs()
    tree = kit.make_tree(parent, [("learner", "Learner", 200), ("items", "Provisions", 90),
                                  ("hours", "Hours / week", 100),
                                  ("weekly", "Cost / week", 110),
                                  ("year", "Cost / year (39 wks)", 140),
                                  ("funding", "Funding / year", 120)])
    tot = {"hours": 0.0, "weekly": 0.0, "funding": 0.0}
    for row in rows:
        for k in tot:
            tot[k] += row[k]
        tree.insert("", "end", values=[row["learner"], row["items"], f"{row['hours']:g}",
                                       f"£{row['weekly']:,.2f}", f"£{row['weekly'] * 39:,.2f}",
                                       f"£{row['funding']:,.2f}"])
    ttk.Label(parent, text=(f"Total: {tot['hours']:g} hours a week · £{tot['weekly']:,.2f} a week "
                            f"(£{tot['weekly'] * 39:,.2f} over a 39-week school year) · "
                            f"£{tot['funding']:,.2f} funding a year"),
              font=("", 10, "bold")).pack(anchor="w", pady=(6, 0))


#: Menu keys with their own page (everything else in the catalogue is a record type).
CUSTOM = {
    "learners": ("SEND Register", draw_register),
    "learner_profile": ("Learner Profile", draw_learner_picker),
    "chronology": ("Chronology", draw_chronology),
    "due_report": ("Due & Overdue", draw_due),
    "register_report": ("SEN Register Summary", draw_register_summary),
    "timeliness_report": ("EHCP 20-Week Timeliness", draw_timeliness),
    "costs_report": ("Provision Costs", draw_costs),
}
