"""The Adult Education pages that aren't a plain record list: learner
profile, chronology, Take Register and the reports. Each is
``draw(parent, app)``, where *app* is the main window (for ``principal``,
``show_learner``, ``status`` and ``state_for``)."""

from __future__ import annotations

import tkinter as tk
from collections import Counter
from datetime import date
from tkinter import ttk
from typing import TYPE_CHECKING

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.adult_education.app import routing
from education_system.systems.adult_education.core import dates
from education_system.systems.adult_education.core import records as r
from education_system.systems.adult_education.modules import (
    courses, enrolments, funding, learners, reports,
)
from education_system.systems.adult_education.ui.gui import kit

if TYPE_CHECKING:
    from education_system.systems.adult_education.app.gui_main import AdultMainGUI


# ── learners ────────────────────────────────────────────────────────

def draw_directory(parent: ttk.Frame, app: "AdultMainGUI") -> None:
    kit.draw_records(parent, learners.LEARNERS, principal=app.principal,
                     state=app.state_for("learners"), on_status=app.status,
                     on_open=lambda row: app.show_learner(row["id"]),
                     subtitle="Every learner, from first enquiry on. Double-click a learner to "
                              "open their profile.")


def draw_learner_picker(parent: ttk.Frame, app: "AdultMainGUI") -> None:
    kit.heading(parent, "Learner Profile", "Choose a learner to see everything about them "
                                           "in one place.")
    kit.draw_records(parent, learners.LEARNERS, principal=app.principal,
                     state=app.state_for("learner_picker"), on_status=app.status,
                     on_open=lambda row: app.show_learner(row["id"]), show_heading=False)


def draw_learner(parent: ttk.Frame, app: "AdultMainGUI", learner_id: int) -> None:
    row = r.get(learners.LEARNERS, learner_id)
    if row is None:
        kit.heading(parent, "Learner not found", "They may have been deleted.")
        return
    top = ttk.Frame(parent)
    top.pack(fill="x")
    name = f"{row.get('title') + ' ' if row.get('title') else ''}{row['first_name']} " \
           f"{row['last_name']}"
    if row.get("preferred_name"):
        name += f" ({row['preferred_name']})"
    ttk.Label(top, text=name, font=("", 18, "bold")).pack(side="left")
    ttk.Label(top, text=f"  {row['learner_ref']} · {row['status']}",
              foreground=kit.MUTED, font=("", 12)).pack(side="left")
    buttons = ttk.Frame(top)
    buttons.pack(side="right")

    def edit() -> None:
        kit.open_form(parent, learners.LEARNERS, row, principal=app.principal,
                      on_saved=lambda _id: app.show_learner(learner_id))

    def toggle_archive() -> None:
        archived = row["status"] == "Archived"
        new = (row.get("status_before_archive") or "Enquiry") if archived else "Archived"
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

    dob = r.to_date(row.get("dob"))
    address = ", ".join(p for p in (row.get("address_line1"), row.get("address_line2"),
                                    row.get("town"), row.get("postcode")) if p)
    ident = learners.identity_status(learner_id)
    prior = learners.prior_summary(learner_id)
    elig = funding.latest_outcome(learner_id)
    facts = [
        ("Date of birth", f"{dates.uk(dob)} (age {dates.age_on(dob, date.today())})" if dob else ""),
        ("Gender", row.get("gender")),
        ("E-mail", row.get("email")),
        ("Phone", row.get("phone")),
        ("Address", address),
        ("Employment", row.get("employment_status")),
        ("ULN", row.get("uln")),
        ("NI number", row.get("ni_number")),
        ("Identity", "Photo ID ✓" if ident["photo_id"] else "No verified photo ID"),
        ("Proof of address", "✓" if ident["address"] else "Not verified"),
        ("Highest level held", prior["highest_level"] or "None recorded"),
        ("GCSE English / maths", f"{'✓' if prior['gcse_english'] else '✗'} / "
                                 f"{'✓' if prior['gcse_maths'] else '✗'}"),
        ("Latest funding check", elig or "Not assessed"),
        ("Support needs", "Yes" if row.get("has_learning_difficulty") else "None declared"),
    ]
    grid = ttk.Frame(parent)
    grid.pack(fill="x", pady=(6, 4))
    for i, (k, v) in enumerate(facts):
        ttk.Label(grid, text=f"{k}:", foreground=kit.MUTED).grid(
            row=i // 2, column=(i % 2) * 2, sticky="w", padx=(0, 6), pady=1)
        ttk.Label(grid, text=v or "—").grid(row=i // 2, column=(i % 2) * 2 + 1, sticky="w",
                                            padx=(0, 30), pady=1)
    for key in ("support_needs", "notes"):
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
        cols.append(("learner", "Learner", 180))
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


def draw_chronology(parent: ttk.Frame, app: "AdultMainGUI") -> None:  # noqa: ARG001
    kit.heading(parent, "Chronology", "Every change to learner records, newest first. Pick a "
                                      "learner to see only theirs.")
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 6))
    ids = {label: i for i, label in learners.learner_options(include_archived=True)}
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


# ── take register ───────────────────────────────────────────────────

def draw_take_register(parent: ttk.Frame, app: "AdultMainGUI") -> None:
    kit.heading(parent, "Take Register", "Pick a class and session date, mark everyone, then "
                                         "save. Marks already made for that session are shown.")
    state = app.state_for("take_register")
    live = [c for c in r.list_records(courses.CLASSES)
            if c["status"] in ("Running", "Open for enrolment", "Completed")]
    classes = {courses.class_label(c): c["id"] for c in live}
    if not classes:
        ttk.Label(parent, text="No running classes yet. Add one under Classes & Timetable.",
                  foreground=kit.MUTED).pack(anchor="w")
        return
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    class_var = tk.StringVar(value=state.get("class") if state.get("class") in classes
                             else next(iter(classes)))
    date_var = tk.StringVar(value=state.get("date") or date.today().strftime("%d/%m/%Y"))
    ttk.Label(bar, text="Class:").pack(side="left")
    ttk.Combobox(bar, textvariable=class_var, values=list(classes), state="readonly",
                 width=60).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Session date:").pack(side="left")
    ttk.Entry(bar, textvariable=date_var, width=12).pack(side="left", padx=4)
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    mark_vars: dict[int, tk.StringVar] = {}

    def load() -> None:
        for w in holder.winfo_children():
            w.destroy()
        mark_vars.clear()
        try:
            on = date.fromisoformat(r.parse_date(date_var.get()) or "")
        except (ValueError, r.ValidationError) as exc:
            ttk.Label(holder, text=str(exc), foreground=kit.OVERDUE_FG).pack(anchor="w")
            return
        state.update({"class": class_var.get(), "date": date_var.get()})
        rows = enrolments.register(classes[class_var.get()], on)
        if not rows:
            ttk.Label(holder, text="Nobody is enrolled on this class.",
                      foreground=kit.MUTED).pack(anchor="w")
            return
        for i, row in enumerate(rows):
            ttk.Label(holder, text=f"{row['name']}  ({row['learner_ref']})").grid(
                row=i, column=0, sticky="w", pady=2, padx=(0, 12))
            var = tk.StringVar(value=row["mark"] or "")
            for j, mark in enumerate(enrolments.MARKS):
                ttk.Radiobutton(holder, text=mark, value=mark, variable=var).grid(
                    row=i, column=j + 1, sticky="w", padx=4)
            mark_vars[row["learner_id"]] = var

    def all_present() -> None:
        for var in mark_vars.values():
            if not var.get():
                var.set("Present")

    def save() -> None:
        try:
            on = date.fromisoformat(r.parse_date(date_var.get()) or "")
            n = enrolments.save_register(classes[class_var.get()], on,
                                         {k: v.get() for k, v in mark_vars.items()},
                                         actor=app.principal.username)
        except r.ValidationError as exc:
            messagebox.showwarning("Register not saved", str(exc), parent=parent)
            return
        except ValueError:
            messagebox.showwarning("Register not saved", "Check the session date.",
                                   parent=parent)
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

def draw_due(parent: ttk.Frame, app: "AdultMainGUI") -> None:
    kit.heading(parent, "Due & Overdue", "ID documents expiring, goal targets, support "
                                         "reviews, complaint replies, enquiry follow-ups, "
                                         "tutor DBS renewals and classes starting in the next "
                                         "60 days, plus anything overdue.")
    items = reports.due_items(60)
    tree = kit.make_tree(parent, [("due", "Due", 100), ("when", "", 110),
                                  ("what", "What", 420), ("learner", "Learner", 200)])
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


def draw_enrolment_report(parent: ttk.Frame, app: "AdultMainGUI") -> None:  # noqa: ARG001
    kit.heading(parent, "Enrolment Summary", "Places, enrolments and waiting lists for every "
                                             "class.")
    rows = reports.enrolment_summary()
    _table(parent, [("c", "Class", 380), ("s", "Status", 120), ("p", "Places", 70),
                    ("e", "Enrolled", 80), ("w", "Waiting", 80), ("x", "Withdrawn", 90),
                    ("f", "Fill", 70)],
           [[x["class"], x["status"], x["places"], x["enrolled"], x["waiting"], x["withdrawn"],
             f"{round(100 * x['enrolled'] / x['places'])}%" if x["places"] else ""]
            for x in rows])


def draw_attendance_report(parent: ttk.Frame, app: "AdultMainGUI") -> None:
    kit.heading(parent, "Attendance Report", "Each current learner's attendance on each class, "
                                             "lowest first. Under 80% is shown in red. "
                                             "Double-click to open the learner.")
    rows = reports.attendance_report()
    tree = _table(parent, [("l", "Learner", 200), ("c", "Class", 420), ("r", "Attendance", 100)],
                  [[x["learner"], x["class"], f"{x['rate']}%"] for x in rows],
                  [x["rate"] < 80 for x in rows])
    ids = {iid: rows[i]["learner_id"] for i, iid in enumerate(tree.get_children())}
    tree.bind("<Double-1>", lambda _e: tree.selection() and
              app.show_learner(ids[tree.selection()[0]]))


def _counts(parent: tk.Misc, groups: dict[str, Counter]) -> None:
    row = ttk.Frame(parent)
    row.pack(fill="both", expand=True)
    for i, (title, counts) in enumerate(groups.items()):
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
            ttk.Label(box, text="Nothing yet.", foreground=kit.MUTED).pack(anchor="w")


def draw_funding_report(parent: ttk.Frame, app: "AdultMainGUI") -> None:  # noqa: ARG001
    kit.heading(parent, "Funding Summary", "Funding eligibility outcomes, and how current "
                                           "enrolments are funded.")
    _counts(parent, reports.funding_summary())


def draw_fees_report(parent: ttk.Frame, app: "AdultMainGUI") -> None:
    kit.heading(parent, "Fees Outstanding", "Enrolments with fees still to pay, largest first. "
                                            "Double-click to open the learner.")
    rows = reports.outstanding()
    tree = _table(parent, [("l", "Learner", 200), ("e", "Enrolment", 420),
                           ("d", "Fee due", 100), ("b", "Balance", 100)],
                  [[x["learner_name"], enrolments.enrolment_label(x),
                    f"£{x['fee_due'] or 0:,.2f}", f"£{x['balance']:,.2f}"] for x in rows])
    ids = {iid: rows[i]["learner_id"] for i, iid in enumerate(tree.get_children())}
    tree.bind("<Double-1>", lambda _e: tree.selection() and
              app.show_learner(ids[tree.selection()[0]]))
    if rows:
        ttk.Label(parent, text=f"Total outstanding: £{sum(x['balance'] for x in rows):,.2f}",
                  font=("", 10, "bold")).pack(anchor="w", pady=(6, 0))


def draw_achievement(parent: ttk.Frame, app: "AdultMainGUI") -> None:  # noqa: ARG001
    kit.heading(parent, "Achievement Rates", "Per course, of learners who have finished "
                                             "(completed or withdrawn): how many achieved.")
    rows = reports.achievement()
    _table(parent, [("c", "Course", 360), ("l", "Leavers", 80), ("a", "Achieved", 80),
                    ("w", "Withdrew", 80), ("r", "Achievement", 100)],
           [[x["course"], x["leavers"], x["achieved"], x["withdrawn"], f"{x['rate']}%"]
            for x in rows], [x["rate"] < 50 for x in rows])


def draw_destinations(parent: ttk.Frame, app: "AdultMainGUI") -> None:  # noqa: ARG001
    kit.heading(parent, "Destinations Summary", "Each learner's latest recorded destination.")
    _counts(parent, {"Latest destination": reports.destinations_summary()})


# ── linked systems (the platform's boards) ──────────────────────────

def draw_refer_to_fe(parent: ttk.Frame, app: "AdultMainGUI") -> None:
    """Adult Education → FE College: the platform's referral board."""
    from education_system.platform.cross_system import fe_applications_gui
    fe_applications_gui.render(app, "adult_education", parent=parent,
                               read_only=not app.principal.is_staff)


def draw_university_applications(parent: ttk.Frame, app: "AdultMainGUI") -> None:
    """Adult Education → University (Access to HE through UCAS)."""
    from education_system.platform.cross_system import university_applications_gui
    university_applications_gui.render(app, "adult_education", parent=parent,
                                       read_only=not app.principal.is_staff)


#: Menu keys with their own page (everything else in the catalogue is a record type).
CUSTOM = {
    "learners": ("Learner Directory", draw_directory),
    "learner_profile": ("Learner Profile", draw_learner_picker),
    "chronology": ("Chronology", draw_chronology),
    "take_register": ("Take Register", draw_take_register),
    "due_report": ("Due & Overdue", draw_due),
    "enrolment_report": ("Enrolment Summary", draw_enrolment_report),
    "attendance_report": ("Attendance Report", draw_attendance_report),
    "funding_report": ("Funding Summary", draw_funding_report),
    "fees_report": ("Fees Outstanding", draw_fees_report),
    "achievement_report": ("Achievement Rates", draw_achievement),
    "destinations_report": ("Destinations Summary", draw_destinations),
    "refer_to_fe": ("Refer to FE College", draw_refer_to_fe),
    "university_applications": ("University Applications (UCAS)",
                                draw_university_applications),
}
