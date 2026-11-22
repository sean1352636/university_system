"""The Training Provider pages that aren't a plain record list: learner
profile, chronology, Take Register, Issue Certificates, Raise Invoices and
the reports. Each is ``draw(parent, app)``, where *app* is the main window
(for ``principal``, ``show_learner``, ``open_page``, ``status`` and
``state_for``)."""

from __future__ import annotations

import tkinter as tk
from collections import Counter
from datetime import date
from tkinter import ttk
from typing import TYPE_CHECKING

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.training_provider.app import routing
from education_system.systems.training_provider.core import dates
from education_system.systems.training_provider.core import records as r
from education_system.systems.training_provider.modules import (
    assessment,
    clients,
    finance,
    learners,
    reports,
    sessions,
)
from education_system.systems.training_provider.ui.gui import kit

if TYPE_CHECKING:
    from education_system.systems.training_provider.app.gui_main import TPMainGUI


# ── learners ────────────────────────────────────────────────────────

def draw_directory(parent: ttk.Frame, app: "TPMainGUI") -> None:
    kit.draw_records(parent, learners.LEARNERS, principal=app.principal,
                     state=app.state_for("learners"), on_status=app.status,
                     on_open=lambda row: app.show_learner(row["id"]),
                     subtitle="Everyone who has booked or been booked. Double-click a learner "
                              "to open their profile.")


def draw_learner_picker(parent: ttk.Frame, app: "TPMainGUI") -> None:
    kit.heading(parent, "Learner Profile", "Choose a learner to see their bookings, results, "
                                           "certificates and invoices in one place.")
    kit.draw_records(parent, learners.LEARNERS, principal=app.principal,
                     state=app.state_for("learner_picker"), on_status=app.status,
                     on_open=lambda row: app.show_learner(row["id"]), show_heading=False)


def _alerts(row: dict, learner_id: int) -> list[str]:
    out = []
    if row.get("support_needs"):
        out.append("Support needs")
    for c in r.list_records(assessment.CERTIFICATES, learner_id=learner_id,
                            equals={"status": "Issued"}):
        until = r.to_date(c.get("expires_on"))
        if until and until < date.today():
            out.append(f"Certificate {c['cert_no']} expired")
        elif until and assessment.renewal_due(c) <= date.today():
            out.append(f"Certificate {c['cert_no']} due for renewal")
    owed = sum(finance.outstanding(i) for i in
               r.list_records(finance.INVOICES, learner_id=learner_id))
    if owed > 0:
        out.append(f"Owes £{owed:,.2f}")
    return out


def draw_learner(parent: ttk.Frame, app: "TPMainGUI", learner_id: int) -> None:
    row = r.get(learners.LEARNERS, learner_id)
    if row is None:
        kit.heading(parent, "Learner not found", "They may have been deleted.")
        return
    top = ttk.Frame(parent)
    top.pack(fill="x")
    name = f"{row['first_name']} {row['last_name']}"
    ttk.Label(top, text=name, font=("", 18, "bold")).pack(side="left")
    ttk.Label(top, text=f"  {row['learner_ref']} · {row['funding']} · {row['status']}",
              foreground=kit.MUTED, font=("", 12)).pack(side="left")
    buttons = ttk.Frame(top)
    buttons.pack(side="right")

    def edit() -> None:
        kit.open_form(parent, learners.LEARNERS, row, principal=app.principal,
                      on_saved=lambda _id: app.show_learner(learner_id))

    def toggle_archive() -> None:
        archived = row["status"] == "Archived"
        if not archived and not messagebox.askyesno(
                "Archive", f"Archive {name}? Their records are kept and can be restored.",
                parent=parent):
            return
        try:
            r.save(learners.LEARNERS, {"status": "Active" if archived else "Archived"},
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

    dob = r.to_date(row.get("dob"))
    employer = r.get(clients.CLIENTS, row["client_id"]) if row.get("client_id") else None
    bookings = r.list_records(sessions.BOOKINGS, learner_id=learner_id)
    upcoming = [b for b in bookings if b["status"] in ("Booked", "Waiting list")]
    certs = r.list_records(assessment.CERTIFICATES, learner_id=learner_id,
                           equals={"status": "Issued"})
    facts = [
        ("Date of birth", f"{dates.uk(dob)} (age {dates.age_on(dob, date.today())})"
         if dob else ""),
        ("Employer", employer["name"] if employer else ""),
        ("Job title", row.get("job_title")),
        ("E-mail", row.get("email")),
        ("Phone", row.get("phone")),
        ("ULN", row.get("uln")),
        ("Booked on", "; ".join(sessions.booking_label(b).split(" - ", 1)[-1]
                                + (" (waiting)" if b["status"] == "Waiting list" else "")
                                for b in upcoming) or "Nothing upcoming"),
        ("Courses done", str(sum(b["status"] == "Attended" for b in bookings))),
        ("Certificates held", str(len(certs))),
        ("Emergency contact", " ".join(x for x in (row.get("emergency_contact"),
                                                   row.get("emergency_phone")) if x)),
    ]
    grid = ttk.Frame(parent)
    grid.pack(fill="x", pady=(6, 4))
    for i, (k, v) in enumerate(facts):
        ttk.Label(grid, text=f"{k}:", foreground=kit.MUTED).grid(
            row=i // 2, column=(i % 2) * 2, sticky="w", padx=(0, 6), pady=1)
        ttk.Label(grid, text=v or "—", wraplength=380, justify="left").grid(
            row=i // 2, column=(i % 2) * 2 + 1, sticky="w", padx=(0, 30), pady=1)
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


def draw_chronology(parent: ttk.Frame, app: "TPMainGUI") -> None:  # noqa: ARG001
    kit.heading(parent, "Chronology", "Every change to the records, newest first. Pick a "
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

def _session_choices() -> dict[str, int]:
    """Live sessions that have started (newest first), for the register."""
    today = date.today()
    out = {}
    for s in r.list_records(sessions.SESSIONS):
        start = r.to_date(s["start_date"])
        if s["status"] in sessions.LIVE and start and start <= today:
            out[sessions.session_label(s)] = s["id"]
    return out


def draw_take_register(parent: ttk.Frame, app: "TPMainGUI") -> None:
    kit.heading(parent, "Take Register", "Pick a session that has started and one of its "
                                         "days, mark every learner with a place, then save. "
                                         "Saving the last day settles each booking as "
                                         "Attended or Did not attend.")
    state = app.state_for("take_register")
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    choices = _session_choices()
    session_var = tk.StringVar(value=state.get("session") if state.get("session") in choices
                               else next(iter(choices), ""))
    day_var = tk.StringVar(value=state.get("day") or "")
    ttk.Label(bar, text="Session:").pack(side="left")
    session_box = ttk.Combobox(bar, textvariable=session_var, values=list(choices),
                               state="readonly", width=34)
    session_box.pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Day:").pack(side="left")
    day_box = ttk.Combobox(bar, textvariable=day_var, state="readonly", width=12)
    day_box.pack(side="left", padx=4)
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    rows_vars: dict[int, tk.StringVar] = {}

    def days_for_session(_e=None) -> None:
        sid = choices.get(session_var.get())
        if sid is None:
            day_box.configure(values=[])
            return
        days = [d for d in sessions.session_days(r.get(sessions.SESSIONS, sid))
                if d <= date.today()]
        labels = [dates.uk(d) for d in days]
        day_box.configure(values=labels)
        if day_var.get() not in labels:
            day_var.set(labels[-1] if labels else "")
        load()

    def load(_e=None) -> None:
        for w in holder.winfo_children():
            w.destroy()
        rows_vars.clear()
        sid = choices.get(session_var.get())
        if sid is None:
            ttk.Label(holder, text="No session has started yet (or they're all completed "
                                   "or cancelled).", foreground=kit.MUTED).pack(anchor="w")
            return
        try:
            on = date.fromisoformat(r.parse_date(day_var.get()) or "")
        except (ValueError, r.ValidationError):
            return
        state.update({"session": session_var.get(), "day": day_var.get()})
        people = sessions.session_bookings(sid)
        if not people:
            ttk.Label(holder, text="Nobody has a place on this session.",
                      foreground=kit.MUTED).pack(anchor="w")
            return
        marks = sessions.marks_for(sid, on)
        for col, text in enumerate(("Learner", "Mark", "Booking")):
            ttk.Label(holder, text=text, foreground=kit.MUTED).grid(row=0, column=col,
                                                                   sticky="w", padx=(0, 12))
        for i, b in enumerate(people, start=1):
            ttk.Label(holder, text=b["learner_name"] or "?").grid(
                row=i, column=0, sticky="w", pady=2, padx=(0, 12))
            mark = tk.StringVar(value=(marks.get((b["learner_id"], on.isoformat())) or {})
                                .get("mark", ""))
            ttk.Combobox(holder, textvariable=mark, values=sessions.MARKS, state="readonly",
                         width=14).grid(row=i, column=1, sticky="w", padx=(0, 12))
            ttk.Label(holder, text=b["status"], foreground=kit.MUTED).grid(
                row=i, column=2, sticky="w")
            rows_vars[b["learner_id"]] = mark

    def all_present() -> None:
        for mark in rows_vars.values():
            if not mark.get():
                mark.set(sessions.MARKS[0])

    def save() -> None:
        sid = choices.get(session_var.get())
        try:
            on = date.fromisoformat(r.parse_date(day_var.get()) or "")
            n = sessions.take_register(sid, on, {k: m.get() for k, m in rows_vars.items()},
                                       actor=app.principal.username)
        except r.ValidationError as exc:
            messagebox.showwarning("Register not saved", str(exc), parent=parent)
            return
        except (ValueError, TypeError):
            messagebox.showwarning("Register not saved", "Choose the session and day.",
                                   parent=parent)
            return
        app.status(f"Register saved: {n} mark(s)")
        load()

    session_box.bind("<<ComboboxSelected>>", days_for_session)
    day_box.bind("<<ComboboxSelected>>", load)
    actions = ttk.Frame(parent)
    actions.pack(fill="x", pady=(8, 0))
    ttk.Button(actions, text="Mark the rest present", command=all_present).pack(side="left")
    ttk.Button(actions, text="Save register", command=save).pack(side="left", padx=6)
    days_for_session()


# ── certificates / invoices ─────────────────────────────────────────

def draw_issue_certificates(parent: ttk.Frame, app: "TPMainGUI") -> None:
    kit.heading(parent, "Issue Certificates", "Sessions with learners who qualify for a "
                                              "certificate but don't have one yet (a Pass on "
                                              "accredited courses; attended, for the rest). "
                                              "Issue them a session at a time.")
    rows = []
    for s in r.list_records(sessions.SESSIONS):
        if s["status"] == "Cancelled":
            continue
        have = {c["learner_id"] for c in r.list_records(assessment.CERTIFICATES,
                                                        equals={"session_id": s["id"],
                                                                "status": "Issued"})}
        due = [b for b in sessions.session_bookings(s["id"])
               if b["learner_id"] not in have and assessment.eligible(b["learner_id"], s["id"])]
        if due:
            rows.append((s, due))
    tree = kit.make_tree(parent, [("s", "Session", 260), ("n", "Ready", 70),
                                  ("who", "Learners", 520)])
    ids = {}
    for s, due in rows:
        iid = tree.insert("", "end", values=[sessions.session_label(s), len(due),
                                             ", ".join(b["learner_name"] or "?" for b in due)])
        ids[iid] = s["id"]
    if not rows:
        ttk.Label(parent, text="Nobody is waiting for a certificate.",
                  foreground=kit.MUTED).pack(anchor="w")

    def issue() -> None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Issue Certificates", "Choose a session first.", parent=parent)
            return
        n = sum(assessment.issue_due(ids[i], actor=app.principal.username) for i in sel)
        notices = r.take_notices()
        app.status(f"{n} certificate(s) issued")
        app.open_page("issue_certificates")
        if notices:   # linked systems told of the certificates
            messagebox.showinfo("Linked systems", "\n\n".join(notices), parent=app.root)

    if rows and app.principal.can_edit("certificates"):
        ttk.Button(parent, text="Issue for the selected session(s)", command=issue).pack(
            anchor="w", pady=(8, 0))


def draw_raise_invoices(parent: ttk.Frame, app: "TPMainGUI") -> None:
    kit.heading(parent, "Raise Invoices", "Who has chargeable bookings (places, no-shows and "
                                          "late-cancellation charges) not yet invoiced. "
                                          "Raising makes one Draft invoice per payer; check it "
                                          "and set it to Sent under Invoices.")
    rows = finance.payers_to_invoice()
    tree = kit.make_tree(parent, [("who", "Bill to", 300), ("k", "Type", 90),
                                  ("amt", "Net to invoice", 130)])
    ids = {}
    for kind, pid, name, amount in rows:
        iid = tree.insert("", "end", values=[name, "Client" if kind == "client" else
                                             "Learner", f"£{amount:,.2f}"])
        ids[iid] = (kind, pid)
    if not rows:
        ttk.Label(parent, text="Everything chargeable has been invoiced.",
                  foreground=kit.MUTED).pack(anchor="w")
    else:
        ttk.Label(parent, text=f"Total £{sum(x[3] for x in rows):,.2f}",
                  font=("", 10, "bold")).pack(anchor="w", pady=(6, 0))

    def raise_selected() -> None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Raise Invoices", "Choose who to invoice first.", parent=parent)
            return
        made, problems = [], []
        for iid in sel:
            kind, pid = ids[iid]
            try:
                inv = finance.raise_invoice(client_id=pid if kind == "client" else None,
                                            learner_id=pid if kind == "learner" else None,
                                            actor=app.principal.username)
                made.append(r.get(finance.INVOICES, inv)["invoice_no"])
            except r.ValidationError as exc:
                problems.append(f"{tree.item(iid)['values'][0]}: {exc}")
        if problems:
            messagebox.showwarning("Some invoices not raised", "\n".join(problems),
                                   parent=parent)
        app.status(f"Raised {', '.join(made) or 'no invoices'}")
        app.open_page("raise_invoices")

    if rows and app.principal.can_edit("invoices"):
        ttk.Button(parent, text="Raise draft invoice(s) for the selected",
                   command=raise_selected).pack(anchor="w", pady=(8, 0))


# ── reports ─────────────────────────────────────────────────────────

def draw_due(parent: ttk.Frame, app: "TPMainGUI") -> None:
    kit.heading(parent, "Due & Overdue", "Sessions to confirm, staff or close, under-booked "
                                         "sessions, DBS renewals, trainer approvals, teaching "
                                         "observations, certificate renewals, complaint "
                                         "responses, invoice payments and contract renewals "
                                         "in the next 60 days, plus anything overdue.")
    items = reports.due_items(60)
    tree = kit.make_tree(parent, [("due", "Due", 100), ("when", "", 110),
                                  ("what", "What", 460), ("learner", "Learner", 180)])
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


def draw_fill_report(parent: ttk.Frame, app: "TPMainGUI") -> None:  # noqa: ARG001
    kit.heading(parent, "Session Fill", "Planned and confirmed sessions in the next 90 days. "
                                        "Red: below the course minimum - run it or cancel "
                                        "it in good time.")
    rows = reports.session_fill(90)
    _table(parent, [("s", "Session", 170), ("t", "Course", 260), ("b", "Booked", 80),
                    ("c", "Places", 70), ("w", "Waiting", 70), ("f", "Full", 70),
                    ("st", "Status", 90)],
           [[x["session"], x["title"], x["booked"], x["capacity"], x["waiting"],
             f"{x['fill']}%", x["status"]] for x in rows],
           [x["under"] for x in rows])


def draw_booking_report(parent: ttk.Frame, app: "TPMainGUI") -> None:  # noqa: ARG001
    kit.heading(parent, "Bookings Summary", "All bookings by status, places by course and "
                                            "client, and how active learners are funded.")
    _counts(parent, reports.booking_summary(), per_row=2)


def draw_achievement_report(parent: ttk.Frame, app: "TPMainGUI") -> None:  # noqa: ARG001
    rate = reports.achievement_rate()
    kit.heading(parent, "Achievement Rates", "Accredited courses: learners who finished "
                                             "(attended or no-show) and how many passed. "
                                             + (f"Overall: {rate}%." if rate is not None
                                                else "Nobody has finished yet."))
    rows = reports.achievement()
    _table(parent, [("c", "Course", 340), ("f", "Finished", 90), ("p", "Passed", 90),
                    ("r", "Rate", 80)],
           [[x["course"], x["finished"], x["passed"],
             "—" if x["rate"] is None else f"{x['rate']}%"] for x in rows])


def draw_expiry_report(parent: ttk.Frame, app: "TPMainGUI") -> None:
    kit.heading(parent, "Expiring Certificates", "Certificates expiring in the next 180 "
                                                 "days (and any already expired) - a "
                                                 "renewal booking is due 90 days before. "
                                                 "Double-click to open the learner.")
    rows = assessment.expiring(180)
    tree = _table(parent, [("n", "Certificate", 140), ("l", "Learner", 200),
                           ("c", "Course", 200), ("e", "Expires", 100), ("v", "", 160)],
                  [[c["cert_no"], c["learner_name"] or "",
                    sessions.session_label(r.get(sessions.SESSIONS, c["session_id"]) or {}),
                    dates.uk(r.to_date(c["expires_on"])), assessment.validity(c)]
                   for c in rows],
                  [r.to_date(c["expires_on"]) < date.today() for c in rows])
    ids = {iid: rows[i]["learner_id"] for i, iid in enumerate(tree.get_children())}
    tree.bind("<Double-1>", lambda _e: tree.selection() and
              app.show_learner(ids[tree.selection()[0]]))


def draw_debt_report(parent: ttk.Frame, app: "TPMainGUI") -> None:
    kit.heading(parent, "Aged Debt & Revenue", "What's owed on sent invoices by how late it "
                                               "is, the overdue invoices, and invoiced vs "
                                               "received by month.")
    bands = finance.aged_debt()
    _table(parent, [("b", "Age", 160), ("a", "Outstanding", 140)],
           [[k, f"£{v:,.2f}"] for k, v in bands.items()])
    ttk.Label(parent, text=f"Total owed £{sum(bands.values()):,.2f}",
              font=("", 10, "bold")).pack(anchor="w", pady=(6, 10))
    ttk.Label(parent, text="Overdue invoices", font=("", 11, "bold")).pack(anchor="w")
    late = finance.overdue_invoices()
    tree = _table(parent, [("n", "Invoice", 130), ("w", "Bill to", 240), ("d", "Due", 100),
                           ("o", "Outstanding", 120)],
                  [[i["invoice_no"], finance.payer(i), dates.uk(r.to_date(i["due_on"])),
                    f"£{finance.outstanding(i):,.2f}"] for i in late], [True] * len(late))
    tree.bind("<Double-1>", lambda _e: app.open_page("invoices"))
    ttk.Label(parent, text="By month", font=("", 11, "bold")).pack(anchor="w", pady=(10, 0))
    _table(parent, [("m", "Month", 100), ("i", "Invoiced", 130), ("p", "Received", 130)],
           [[m, f"£{i:,.2f}", f"£{p:,.2f}"] for m, i, p in reports.revenue_by_month()])


def draw_quality_report(parent: ttk.Frame, app: "TPMainGUI") -> None:  # noqa: ARG001
    q = reports.quality_summary()
    rate, rating = q.pop("sample_rate"), q.pop("rating")
    kit.heading(parent, "Quality Summary",
                "Latest observation grades, IQA decisions and learner feedback. "
                + (f"IQA has sampled {rate}% of assessment decisions. " if rate is not None
                   else "")
                + (f"Average rating {rating:g}/5." if rating is not None else ""))
    _counts(parent, q, per_row=2)


# ── linked systems (the platform's boards) ──────────────────────────

def draw_apprenticeship_progression(parent: ttk.Frame, app: "TPMainGUI") -> None:
    """Training Provider → Apprenticeships: the platform's application board."""
    from education_system.platform.cross_system import apprenticeship_applications_gui
    apprenticeship_applications_gui.render(app, "training_provider", parent=parent)


def draw_refer_to_fe(parent: ttk.Frame, app: "TPMainGUI") -> None:
    """Training Provider → FE College: the platform's referral board."""
    from education_system.platform.cross_system import fe_applications_gui
    fe_applications_gui.render(app, "training_provider", parent=parent,
                               read_only=not app.principal.is_staff)


#: Menu keys with their own page (everything else in the catalogue is a record type).
CUSTOM = {
    "learners": ("Learner Directory", draw_directory),
    "learner_profile": ("Learner Profile", draw_learner_picker),
    "chronology": ("Chronology", draw_chronology),
    "take_register": ("Take Register", draw_take_register),
    "issue_certificates": ("Issue Certificates", draw_issue_certificates),
    "raise_invoices": ("Raise Invoices", draw_raise_invoices),
    "due_report": ("Due & Overdue", draw_due),
    "fill_report": ("Session Fill", draw_fill_report),
    "booking_report": ("Bookings Summary", draw_booking_report),
    "achievement_report": ("Achievement Rates", draw_achievement_report),
    "expiry_report": ("Expiring Certificates", draw_expiry_report),
    "debt_report": ("Aged Debt & Revenue", draw_debt_report),
    "quality_report": ("Quality Summary", draw_quality_report),
    "apprenticeship_progression": ("Progress to Apprenticeship",
                                   draw_apprenticeship_progression),
    "refer_to_fe": ("Refer to FE College", draw_refer_to_fe),
}
