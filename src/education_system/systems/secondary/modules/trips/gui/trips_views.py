"""Trips & Payments screen.

The old window's four tabs keep their place, toolbars and columns:

* **Trips** - Year / Status filters, Open only, Apply, Clear; View, New,
  Edit, Status, Delete, Refresh; ID, Start, End, Name, Destination, Year,
  Cost, Deposit, Cap, Status (open-for-booking rows green, cancelled grey).
  Added: Approval column, Schedule, Risk assessment, Submit to EVC, Invite
  pupils, Consent requests, Readiness, History, Export.
* **Bookings** - Trip / Status / Payment filters, Consent missing, Apply;
  View, New, Edit, Status, Add Payment, Delete, Refresh; #, Student, Name,
  Booked, Status, Consent, Paid, Balance, Payment, Notes. Added: Consent,
  Remission, Refund, Pupil ledger, Open pupil, Export CSV.
* **Payments** - Trip ID, Student, Method, Status, From, To, Apply, Clear;
  Edit, Delete, Refresh; ID, Booking, Paid on, Amount, Method, Status, Ref,
  By, Notes. Added: Kind (payment / refund) and Export CSV.
* **Summary** - Refresh and the text summary.

New tabs: **Arrears** (behind the payment plan, reminder e-mails, refunds
due), **On the day** (departed / returned register, headcount, ratio,
attendance code V) and **Approvals** (the EVC's queue). The rules are in
:mod:`modules.trips.domain.trips`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.trips.domain import trips as TR
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
_ERRORS = W.ERRORS
_problems = W.problems
_text_window = W.text_window
_form = W.form_dialog
_m = TR.money
_TAGS = {**W.STANDARD_TAGS, "open": {"background": "#e6f7e0"},
         "cancelled": {"foreground": "#888"}, "Unpaid": {"background": "#ffe0e0"},
         "Paid": {"background": "#e6f7e0"}, "Waitlist": {"background": "#fff7d0"},
         "Pending": {"background": "#fff7d0"}, "Failed": {"background": "#ffe0e0"}}


def _tree(parent, columns, height: int = 14, select: str = "browse") -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select=select,
                  stretch={"name", "notes", "pupil", "item", "note", "destination"},
                  tags=_TAGS)


def _trip_fields(t: TR.Trip | None) -> list:
    """The old trip form's fields in order, then the new ones."""
    g = (lambda k, d="": getattr(t, k) if t and getattr(t, k) is not None else d)
    return [
        ("title", "Trip name", g("title"), None),
        ("destination", "Destination", g("destination"), None),
        ("start_date", "Start date (YYYY-MM-DD)", g("start_date"), None),
        ("end_date", "End date", g("end_date"), None),
        ("year_group", "Year group", g("year_group", TR.DEFAULT_YEAR_GROUP), TR.YEAR_GROUPS),
        ("cost_pence", "Cost per place (£)", TR.plain(t.cost_pence) if t else "0.00", None),
        ("deposit_pence", "Deposit (£)", TR.plain(t.deposit_pence) if t else "0.00", None),
        ("capacity", "Capacity", g("capacity"), None),
        ("payment_due", "Payment due", g("payment_due"), None),
        ("status", "Status", g("status", TR.DEFAULT_TRIP_STATUS), TR.TRIP_STATUSES),
        ("leader", "Lead staff", g("leader"), None),
        ("description", "Description", g("description"), "text"),
        ("notes", "Notes", g("notes"), "text"),
        ("depart_time", "Depart time (HH:MM)", g("depart_time"), None),
        ("return_time", "Return time (HH:MM)", g("return_time"), None),
        ("staff", "Accompanying staff (comma list)", g("staff"), None),
        ("group_label", "Group invited", g("group_label"), None),
        ("deposit_due", "Deposit due", g("deposit_due"), None),
        ("consent_due", "Consent due", g("consent_due"), None),
        ("charging", "Charging", g("charging", TR.VOLUNTARY), TR.CHARGING),
        ("charge_basis", "Charge basis (if chargeable)", g("charge_basis"),
         ["", *TR.CHARGE_BASES]),
        ("residential", "Residential", bool(t and t.residential), "check"),
        ("overseas", "Overseas", bool(t and t.overseas), "check"),
        ("adventurous", "Adventurous activity", bool(t and t.adventurous), "check"),
        ("ratio", "Pupils per adult (blank = default)", g("ratio"), None),
    ]


def _trip_text(t: TR.Trip) -> str:
    rows = [("Trip", f"#{t.trip_id} {t.title}"), ("Destination", t.destination),
            ("Dates", t.period), ("Times", " - ".join(x for x in (t.depart_time, t.return_time)
                                                      if x)),
            ("Year group", t.year_group), ("Group", t.group_label), ("Type", t.flags),
            ("Leader", t.leader), ("Staff", ", ".join(t.staff_names)),
            ("Ratio", f"1 adult : {t.pupils_per_adult} pupils"),
            ("Capacity", t.capacity), ("Places taken", t.places_taken),
            ("Waiting", t.waiting), ("Cost", _m(t.cost_pence)), ("Charging", t.charging),
            ("Charge basis", t.charge_basis), ("Deposit", _m(t.deposit_pence) if
                                               t.deposit_pence else None),
            ("Payment due", t.payment_due), ("Consent due", t.consent_due),
            ("Status", t.status), ("EVC approval", TR.APPROVAL_LABELS[t.approval]),
            ("Approval note", t.approval_note),
            ("Risk assessment", t.risk_file or ("(text)" if t.risk_assessment else None)),
            ("Reviewed", f"{t.risk_reviewed_by or ''} {t.risk_reviewed_on or ''}".strip()),
            ("Description", t.description), ("Notes", t.notes)]
    lines = [f"{k + ':':<18} {v}" for k, v in rows if v not in (None, "")]
    lines += ["", "Payment plan:"] + [f"  {x['label']:<14} {x['due'] or '-':<10} "
                                      f"{_m(x['amount_pence']):>10}  (total "
                                      f"{_m(x['cumulative_pence'])})" for x in TR.schedule(t)]
    return "\n".join(lines)


class TripsPage:
    TABS = ("Trips", "Bookings", "Payments", "Summary", "Arrears", "On the day", "Approvals")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = TR.is_editor(principal)
        activity_log.record("trips.view")
        ttk.Label(parent, text="Trips & Payments", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        start = state.get("tab") if state.get("tab") in self.TABS else "Trips"
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    # ── helpers ──────────────────────────────────────────────────────

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, _problems(e), parent=self._top())

    def _info(self, title: str, text: str) -> None:
        messagebox.showinfo(title, text, parent=self._top())

    def _button(self, bar, text: str, command, editor_only: bool = False,
                side: str = "left") -> ttk.Button:
        b = ttk.Button(bar, text=text, command=command)
        if editor_only and not self.editor:
            b.state(["disabled"])
        b.pack(side=side, padx=2)
        return b

    def _run(self, title: str, fn, *a, **kw) -> Any:
        try:
            return fn(*a, **kw)
        except _ERRORS as e:
            self._err(title, e)
            return None

    def _views(self) -> dict[str, tuple[Callable, Callable]]:
        return {"Trips": (self._build_trips, self.refresh_trips),
                "Bookings": (self._build_bookings, self.refresh_bookings),
                "Payments": (self._build_payments, self.refresh_payments),
                "Summary": (self._build_summary, self.refresh_summary),
                "Arrears": (self._build_arrears, self.refresh_arrears),
                "On the day": (self._build_day, self.refresh_day),
                "Approvals": (self._build_approvals, self.refresh_approvals)}

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        build, refresh = self._views()[name]
        if name not in self._built:
            self._built.add(name)
            build(self.tabs[name])
        refresh()

    def _refresh_all(self) -> None:
        for name, (_b, fn) in self._views().items():
            if name in self._built:
                fn()

    def _deliver(self, title: str, res: dict[str, Any]) -> None:
        if not res.get("message_id"):
            self._info(title, "No contact with parental responsibility has an e-mail address."
                       + (f"\n\nNo e-mail for: {', '.join(b.pupil_name for b in res['no_email'])}"
                          if res.get("no_email") else ""))
            return
        text = f"{res['emails']} e-mail(s) prepared."
        if res.get("no_email"):
            text += f"\nNo e-mail address for {len(res['no_email'])} pupil(s)."
        from education_system.systems.secondary.modules.communication.gui import email_views

        def done(_report, error) -> None:
            try:
                self._info(title, text + (f"\n\nQueued - delivery failed: {error}"
                                          if error else "\n\nSent."))
            except tk.TclError:
                pass
        email_views.deliver_in_background(self.parent, res["message_id"], self.principal, done)

    def _trip_choices(self) -> list[str]:
        return [f"{t.trip_id} - {t.start_date} {t.title}" for t in TR.list_trips()]

    @staticmethod
    def _trip_id(text: str) -> int | None:
        head = (text or "").split(" - ", 1)[0].strip()
        return int(head) if head.isdigit() else None

    # ── Trips (old tab) ──────────────────────────────────────────────

    def _build_trips(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.f_year = tk.StringVar(value=self.state.get("year", ""))
        self.f_status = tk.StringVar(value=self.state.get("status", ""))
        self.f_open = tk.BooleanVar(value=self.state.get("open_only", False))
        for label, var, values, width in (("Year:", self.f_year, ["", *TR.YEAR_GROUPS], 9),
                                          ("Status:", self.f_status, ["", *TR.TRIP_STATUSES],
                                           18)):
            ttk.Label(bar, text=label).pack(side="left", padx=(0, 4))
            ttk.Combobox(bar, textvariable=var, values=values, state="readonly",
                         width=width).pack(side="left", padx=(0, 6))
        ttk.Checkbutton(bar, text="Open only", variable=self.f_open).pack(side="left", padx=4)
        self._button(bar, "Apply", self.refresh_trips)
        self._button(bar, "Clear", self._clear_trips)
        self.trip_tree = _tree(tab, [
            ("id", "Id", 50), ("start", "Start", 90), ("end", "End", 90), ("name", "Name", 220),
            ("destination", "Destination", 160), ("year", "Year", 70), ("cost", "Cost", 80),
            ("deposit", "Deposit", 80), ("cap", "Cap", 60), ("status", "Status", 130),
            ("approval", "Approval", 110)])
        self.trip_tree.bind("<Double-1>", lambda _e: self.view_trip())
        self.trip_count = tk.StringVar()
        ttk.Label(tab, textvariable=self.trip_count, anchor="w").pack(fill="x")
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(4, 2))
        for text, cmd, lead in (("View", self.view_trip, False), ("New", self.new_trip, False),
                                ("Edit", self.edit_trip, False),
                                ("Status", self.trip_status, True),
                                ("Delete", self.delete_trip, False)):
            self._button(bar2, text, cmd, lead)
        self._button(bar2, "Refresh", self.refresh_trips, side="right")
        bar3 = ttk.Frame(tab)
        bar3.pack(fill="x", pady=(2, 0))
        for text, cmd, lead in (("Schedule…", self.schedule, False),
                                ("Risk assessment…", self.risk, False),
                                ("Submit to EVC", self.submit, False),
                                ("Invite pupils…", self.invite, True),
                                ("Consent requests", self.consent_requests, True),
                                ("Readiness", self.readiness, False),
                                ("History", self.trip_history, False),
                                ("Export bookings…", self.export_bookings, False)):
            self._button(bar3, text, cmd, lead)
        self.trip_rows: dict[str, TR.Trip] = {}

    def _clear_trips(self) -> None:
        self.f_year.set("")
        self.f_status.set("")
        self.f_open.set(False)
        self.refresh_trips()

    def refresh_trips(self) -> None:
        self.state.update(year=self.f_year.get(), status=self.f_status.get(),
                          open_only=self.f_open.get())
        rows = TR.list_trips(year_group=self.f_year.get() or None,
                             status=self.f_status.get() or None, open_only=self.f_open.get())
        self.trip_tree.delete(*self.trip_tree.get_children())
        self.trip_rows = {}
        for t in rows:
            self.trip_rows[str(t.trip_id)] = t
            tag = "cancelled" if t.status == "Cancelled" else (
                "open" if t.status == "Open for Booking" else "")
            self.trip_tree.insert("", "end", iid=str(t.trip_id), tags=(tag,), values=(
                t.trip_id, t.start_date, t.end_date or "", t.title, t.destination or "",
                t.year_group, _m(t.cost_pence), _m(t.deposit_pence),
                t.capacity if t.capacity is not None else "", t.status,
                TR.APPROVAL_LABELS[t.approval]))
        self.trip_count.set(f"{len(rows)} trip(s)")
        s = TR.summary()
        self.summary_var.set(
            f"Upcoming: {s['upcoming_trips']}    Awaiting approval: {s['awaiting_approval']}    "
            f"Places: {s['active_bookings']}    Consent missing: {s['consent_missing']}    "
            f"Paid: {_m(s['total_paid'])}    Outstanding: {_m(s['total_outstanding'])}    "
            f"Behind plan: {_m(s['overdue_balance'])}")

    def _trip(self, title: str) -> TR.Trip | None:
        sel = self.trip_tree.selection()
        if not sel:
            self._info(title, "Select a trip first.")
            return None
        return TR.get(int(sel[0]))

    def view_trip(self) -> None:
        t = self._trip("View trip")
        if t:
            _text_window(self.parent, f"Trip #{t.trip_id}", _trip_text(t),
                         save_name=f"trip-{t.trip_id}.txt")

    def new_trip(self) -> None:
        def save(v):
            TR.create_trip({k: x for k, x in v.items() if x not in ("", None)}, actor=self.principal)
            self._refresh_all()
        _form(self.parent, "New trip", _trip_fields(None), save,
              note="Trips start as drafts. Submit to the EVC with a risk assessment before "
                   "opening for booking. A voluntary contribution can never stop a pupil going.")

    def edit_trip(self) -> None:
        t = self._trip("Edit trip")
        if t is None:
            return

        def save(v):
            changes = {k: x for k, x in v.items()
                       if str(x if x is not None else "") != str(
                           TR.plain(getattr(t, k)) if k.endswith("_pence")
                           else (bool(getattr(t, k)) if isinstance(x, bool)
                                 else (getattr(t, k) if getattr(t, k) is not None else "")))}
            done = TR.update_trip(t.trip_id, changes, actor=self.principal)
            self._refresh_all()
            if t.approved and not done.approved:
                self._info("Edit trip", "The dates, destination or type changed - the trip "
                                        "has gone back to the EVC for approval.")
        _form(self.parent, f"Edit trip #{t.trip_id}", _trip_fields(t), save)

    def trip_status(self) -> None:
        t = self._trip("Trip status")
        if t is None:
            return

        def save(v):
            TR.set_trip_status(t.trip_id, v["status"], actor=self.principal)
            self._refresh_all()
            if v["status"] == "Cancelled" and TR.refunds_due(t.trip_id):
                self._info("Trip status", f"{len(TR.refunds_due(t.trip_id))} booking(s) hold "
                                          "money - see Arrears > Refunds due.")
        _form(self.parent, f"Status - trip #{t.trip_id}",
              [("status", "New status", t.status, TR.TRIP_STATUSES)], save)

    def delete_trip(self) -> None:
        t = self._trip("Delete trip")
        if t is None or not messagebox.askyesno(
                "Delete trip", f"Delete trip #{t.trip_id} ({t.title}) with all its bookings "
                               "and payments?", parent=self._top()):
            return
        if self._run("Delete trip", TR.delete_trip, t.trip_id, actor=self.principal):
            self._refresh_all()

    def schedule(self) -> None:
        t = self._trip("Schedule")
        if t is None:
            return
        win, frm = W.dialog(self.parent, f"Payment plan - {t.title}", size="560x360")
        tree = _tree(frm, [("label", "Payment", 160), ("due", "Due", 100),
                           ("amount", "Amount", 90), ("total", "Total", 90)], height=8)
        ids: dict[str, int] = {}

        def refresh() -> None:
            tree.delete(*tree.get_children())
            ids.clear()
            inst = {(i.label, i.due_date, i.amount_pence): i.instalment_id
                    for i in TR.list_instalments(t.trip_id)}
            for n, x in enumerate(TR.schedule(t.trip_id)):
                iid = str(n)
                key = (x["label"], x["due"], x["amount_pence"])
                if key in inst:
                    ids[iid] = inst[key]
                tree.insert("", "end", iid=iid, values=(x["label"], x["due"] or "-",
                                                        _m(x["amount_pence"]),
                                                        _m(x["cumulative_pence"])))

        def add() -> None:
            def save(v):
                TR.add_instalment(t.trip_id, v, actor=self.principal)
                refresh()
            _form(win, "Add instalment", [("label", "Label", "", None),
                                          ("due_date", "Due date", "", None),
                                          ("amount", "Amount (£)", "", None)], save,
                  note="The deposit is set on the trip; the balance is due by the payment "
                       "due date.")

        def remove() -> None:
            sel = tree.selection()
            if not sel or sel[0] not in ids:
                messagebox.showinfo("Schedule", "Select an instalment (not the deposit or "
                                    "balance).", parent=win)
                return
            try:
                TR.delete_instalment(ids[sel[0]], actor=self.principal)
            except _ERRORS as e:
                messagebox.showerror("Schedule", _problems(e), parent=win)
            refresh()
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(6, 0))
        manage = TR.can_manage(self.principal, t)
        for text, cmd in (("Add instalment…", add), ("Remove", remove)):
            b = ttk.Button(bar, text=text, command=cmd)
            if not manage:
                b.state(["disabled"])
            b.pack(side="left", padx=2)
        refresh()

    def risk(self) -> None:
        t = self._trip("Risk assessment")
        if t is None:
            return

        def browse_note() -> str:
            return "Give the file's path (the uploaded assessment) and / or the text."

        def save(v):
            path = v["file"]
            TR.record_risk_assessment(t.trip_id, actor=self.principal, text=v["text"],
                                      file_path=path, reviewed_by=v["by"] or None,
                                      reviewed_on=v["on"] or None)
            self._refresh_all()
        win = _form(self.parent, f"Risk assessment - {t.title}", [
            ("file", "File (path)", t.risk_file or "", None),
            ("text", "Assessment", t.risk_assessment or "", "text"),
            ("by", "Reviewed by", t.risk_reviewed_by or "", None),
            ("on", "Reviewed on (blank = today)", t.risk_reviewed_on or "", None)], save,
            note=browse_note())

        try:
            frm = win.winfo_children()[0]
        except (tk.TclError, IndexError):
            return      # the form already closed

        def pick() -> None:
            path = filedialog.askopenfilename(parent=win, title="Risk assessment file")
            if path:
                entry = next((c for c in frm.winfo_children() if isinstance(c, ttk.Entry)),
                             None)    # the first entry is the file path
                if entry is not None:
                    entry.delete(0, "end")
                    entry.insert(0, path)
        ttk.Button(frm, text="Choose file…", command=pick).grid(row=99, column=0, sticky="w",
                                                                pady=(6, 0))

    def submit(self) -> None:
        t = self._trip("Submit to EVC")
        if t is None:
            return
        if self._run("Submit to EVC", TR.submit_for_approval, t.trip_id,
                     actor=self.principal):
            self._refresh_all()
            self._info("Submit to EVC", "Submitted. The EVC approves it under Approvals.")

    def invite(self) -> None:
        t = self._trip("Invite pupils")
        if t is None:
            return

        def save(v):
            r = TR.invite(t.trip_id, actor=self.principal, year_group=v["year"] or None,
                          form_group=v["form"] or None, teaching_group=v["group"] or None,
                          status=v["status"])
            self._refresh_all()
            self._info("Invite pupils", f"Added {r['added']} pupil(s); {r['already']} already "
                                        f"on the trip; {r['waitlist']} on the waiting list.")
        _form(self.parent, f"Invite pupils - {t.title}", [
            ("year", "Year group", "", ["", "7", "8", "9", "10", "11"]),
            ("form", "Form", "", None), ("group", "Teaching group code", "", None),
            ("status", "Add as", "Interested", ["Interested", "Confirmed"])], save,
            note="Confirmed places are given while there is room; the rest go on the "
                 "waiting list in order.")

    def consent_requests(self) -> None:
        t = self._trip("Consent requests")
        if t is None:
            return
        res = self._run("Consent requests", TR.send_consent_requests, t.trip_id,
                        actor=self.principal)
        if res:
            self._deliver("Consent requests", res)

    def readiness(self) -> None:
        t = self._trip("Readiness")
        if t is None:
            return
        lines = [f"{t.title} - {t.period}", ""] + [
            f"[{'x' if c['ok'] else ' '}] {c['item']:<32} {c['note']}"
            for c in TR.readiness(t.trip_id)]
        _text_window(self.parent, "Readiness", "\n".join(lines))

    def trip_history(self) -> None:
        t = self._trip("History")
        if t:
            _text_window(self.parent, "History", "\n".join(
                f"{h['at']}  {h['actor']:<12} {h['action']:<16} "
                + (f"booking {h['booking_id']} " if h["booking_id"] else "")
                + ", ".join(f"{k}={v}" for k, v in h["detail"].items())
                for h in TR.history(t.trip_id)) or "No changes recorded.")

    def export_bookings(self) -> None:
        sel = self.trip_tree.selection()
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="trip-bookings.csv")
        if path:
            n = self._run("Export", TR.export_bookings_csv, path, actor=self.principal,
                          trip_id=int(sel[0]) if sel else None)
            if n is not None:
                self._info("Export", f"Exported {n} booking(s).")

    # ── Bookings (old tab) ───────────────────────────────────────────

    def _build_bookings(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.b_trip = tk.StringVar(value=self.state.get("b_trip", ""))
        self.b_status = tk.StringVar(value="")
        self.b_state = tk.StringVar(value="")
        self.b_consent = tk.BooleanVar(value=False)
        ttk.Label(bar, text="Trip:").pack(side="left")
        self.b_trip_box = ttk.Combobox(bar, textvariable=self.b_trip, width=34,
                                       state="readonly")
        self.b_trip_box.pack(side="left", padx=(4, 6))
        for label, var, values in (("Status:", self.b_status, ["", *TR.BOOKING_STATUSES]),
                                   ("Payment:", self.b_state, ["", *TR.PAYMENT_STATES])):
            ttk.Label(bar, text=label).pack(side="left")
            ttk.Combobox(bar, textvariable=var, values=values, state="readonly",
                         width=11).pack(side="left", padx=(4, 6))
        ttk.Checkbutton(bar, text="Consent missing", variable=self.b_consent).pack(side="left")
        self._button(bar, "Apply", self.refresh_bookings)
        self.b_tree = _tree(tab, [
            ("id", "#", 50), ("student", "Student", 90), ("name", "Name", 190),
            ("booked", "Booked", 90), ("status", "Status", 90), ("consent", "Consent", 70),
            ("paid", "Paid", 80), ("balance", "Balance", 80), ("state", "Payment", 80),
            ("notes", "Notes", 220)], select="extended")
        self.b_tree.bind("<Double-1>", lambda _e: self.view_booking())
        self.b_totals = tk.StringVar()
        ttk.Label(tab, textvariable=self.b_totals, anchor="w").pack(fill="x")
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(4, 2))
        for text, cmd, lead in (("View", self.view_booking, False),
                                ("New", self.new_booking, True),
                                ("Edit", self.edit_booking, False),
                                ("Status", self.booking_status, True),
                                ("Add Payment", self.add_payment, True),
                                ("Delete", self.delete_booking, True)):
            self._button(bar2, text, cmd, lead)
        self._button(bar2, "Refresh", self.refresh_bookings, side="right")
        bar3 = ttk.Frame(tab)
        bar3.pack(fill="x", pady=(2, 0))
        for text, cmd, lead in (("Consent…", self.consent, False),
                                ("Remission…", self.remission, True),
                                ("Refund…", self.refund, True),
                                ("Pupil ledger", self.ledger, False),
                                ("Open pupil", self._open_pupil, False)):
            self._button(bar3, text, cmd, lead)
        self.b_rows: dict[str, TR.Booking] = {}

    def refresh_bookings(self) -> None:
        self.b_trip_box.configure(values=["", *self._trip_choices()])
        self.state["b_trip"] = self.b_trip.get()
        rows = TR.list_bookings(self._trip_id(self.b_trip.get()),
                                status=self.b_status.get() or None,
                                payment_state=self.b_state.get() or None,
                                consent_missing=self.b_consent.get())
        self.b_tree.delete(*self.b_tree.get_children())
        self.b_rows = {}
        for b in rows:
            self.b_rows[str(b.booking_id)] = b
            tag = "cancelled" if b.status in TR.RELEASED else (
                "Waitlist" if b.status == "Waitlist" else b.payment_state)
            self.b_tree.insert("", "end", iid=str(b.booking_id), tags=(tag,), values=(
                b.booking_id, b.admission_no, b.pupil_name, b.booking_date, b.status,
                b.consent or "-", _m(b.paid_pence), _m(b.balance_pence), b.payment_state,
                (b.notes or "").replace("\n", " ")[:80]))
        self.b_totals.set(f"{len(rows)} booking(s)    Charged: "
                          f"{_m(sum(b.charge_pence for b in rows))}    Paid: "
                          f"{_m(sum(b.paid_pence for b in rows))}    Balance: "
                          f"{_m(sum(max(0, b.balance_pence) for b in rows))}")

    def _booking(self, title: str) -> TR.Booking | None:
        sel = self.b_tree.selection()
        if not sel:
            self._info(title, "Select a booking first.")
            return None
        return TR.get_booking(int(sel[0]))

    def view_booking(self) -> None:
        b = self._booking("View booking")
        if b is None:
            return
        rows = [("Booking", f"#{b.booking_id}"), ("Trip", f"#{b.trip_id} {b.trip_title}"),
                ("Pupil", f"{b.pupil_name} ({b.admission_no}), Year {b.pupil_year}"),
                ("Booked", b.booking_date), ("Status", b.status),
                ("Consent", f"{b.consent or 'not given'} {b.consent_date or ''} "
                            f"{b.consent_by or ''}".strip()),
                ("Consent note", b.consent_note), ("Medical", b.medical_note),
                ("Dietary", b.dietary_note), ("Charging", b.charging),
                ("Cost", _m(b.cost_pence)),
                ("Remission", f"{_m(b.remission_pence)} ({b.remission_reason})"
                 if b.remission_pence else None),
                ("Asked for", _m(b.charge_pence)), ("Paid", _m(b.paid_pence)),
                ("Balance", _m(b.balance_pence)), ("Payment", b.payment_state),
                ("Last reminder", b.last_reminder_at), ("Departed", b.departed_at),
                ("Returned", b.returned_at), ("Notes", b.notes)]
        text = "\n".join(f"{k + ':':<15} {v}" for k, v in rows if v not in (None, ""))
        pays = TR.list_payments(booking_id=b.booking_id)
        text += "\n\nPayments:\n" + ("\n".join(
            f"  #{p.payment_id:<4} {p.paid_on} {p.kind:<8} {_m(p.amount_pence):>9} {p.method:<14}"
            f" {p.status:<9} {p.reference or ''}" for p in pays) or "  (none)")
        _text_window(self.parent, f"Booking #{b.booking_id}", text)

    def _booking_form(self, b: TR.Booking | None) -> list:
        g = (lambda k: getattr(b, k) or "" if b else "")
        return [("booking_date", "Booking date", g("booking_date"), None),
                ("consent", "Consent", (b.consent or "") if b else "", ["", "Yes", "No"]),
                ("consent_note", "Consent note", g("consent_note"), None),
                ("medical_note", "Medical note", g("medical_note"), "text"),
                ("dietary_note", "Dietary note", g("dietary_note"), None),
                ("notes", "Notes", g("notes"), "text")]

    def new_booking(self) -> None:
        tid = self._trip_id(self.b_trip.get())
        trips = self._trip_choices()

        def save(v):
            trip = self._trip_id(v.pop("trip"))
            if trip is None:
                raise TR.ValidationError(["Choose the trip"])
            b = TR.create_booking(trip, {k: x for k, x in v.items() if x not in ("", None)},
                                  actor=self.principal)
            self._refresh_all()
            if b.status == "Waitlist":
                self._info("New booking", "The trip is full - the pupil is on the waiting "
                                          "list.")
        _form(self.parent, "New booking", [
            ("trip", "Trip", next((x for x in trips if self._trip_id(x) == tid), ""), trips),
            ("pupil_id", "Student (ID / admission no.)", "", None),
            ("status", "Status", TR.DEFAULT_BOOKING_STATUS, TR.BOOKING_STATUSES),
            *self._booking_form(None)], save)

    def edit_booking(self) -> None:
        b = self._booking("Edit booking")
        if b is None:
            return

        def save(v):
            TR.update_booking(b.booking_id, {k: x for k, x in v.items()
                                             if str(x or "") != str(getattr(b, k) or "")},
                              actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Edit booking #{b.booking_id} - {b.pupil_name}",
              self._booking_form(b), save)

    def booking_status(self) -> None:
        b = self._booking("Booking status")
        if b is None:
            return

        def save(v):
            done, promoted = TR.set_booking_status(b.booking_id, v["status"],
                                                   actor=self.principal, reason=v["reason"])
            self._refresh_all()
            msg = f"{done.pupil_name}: {done.status}."
            if promoted:
                msg += f"\n\nThe place went to {promoted.pupil_name} (first on the waiting list)."
            if done.status in TR.RELEASED and done.paid_pence:
                msg += f"\n\n{_m(done.paid_pence)} has been paid - record the refund."
            self._info("Booking status", msg)
        _form(self.parent, f"Status - {b.pupil_name}", [
            ("status", "New status", b.status, TR.BOOKING_STATUSES),
            ("reason", "Reason (needed to cancel / withdraw)", "", None)], save,
            note="On a voluntary-contribution trip no pupil can be left out for not paying.")

    def add_payment(self) -> None:
        b = self._booking("Add payment")
        if b is None:
            return

        def save(v):
            TR.add_payment(b.booking_id, v, actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Record payment - {b.pupil_name} (balance {_m(b.balance_pence)})", [
            ("amount", "Amount (£)", TR.plain(max(0, b.balance_pence)), None),
            ("paid_on", "Paid on (blank = today)", "", None),
            ("method", "Method", TR.DEFAULT_METHOD, TR.PAYMENT_METHODS),
            ("status", "Status", TR.DEFAULT_PAYMENT_STATUS, TR.PAYMENT_STATUSES),
            ("reference", "Reference", "", None),
            ("recorded_by", "Recorded by (blank = you)", "", None),
            ("notes", "Notes", "", "text")], save)

    def delete_booking(self) -> None:
        b = self._booking("Delete booking")
        if b is None or not messagebox.askyesno(
                "Delete booking", f"Delete {b.pupil_name}'s booking and its payments?",
                parent=self._top()):
            return
        if self._run("Delete booking", TR.delete_booking, b.booking_id, actor=self.principal):
            self._refresh_all()

    def consent(self) -> None:
        b = self._booking("Consent")
        if b is None:
            return

        def save(v):
            TR.record_consent(b.booking_id, v["given"], actor=self.principal,
                              day=v["day"] or None, by=v["by"], medical_note=v["medical"],
                              dietary_note=v["dietary"], note=v["note"])
            self._refresh_all()
        _form(self.parent, f"Consent - {b.pupil_name}", [
            ("given", "Consent given", b.consent or "Yes", ["Yes", "No"]),
            ("day", "Date (blank = today)", b.consent_date or "", None),
            ("by", "Given by", b.consent_by or "", None),
            ("medical", "Medical needs / medication", b.medical_note or "", "text"),
            ("dietary", "Dietary requirements", b.dietary_note or "", None),
            ("note", "Note", b.consent_note or "", None)], save)

    def remission(self) -> None:
        b = self._booking("Remission")
        if b is None:
            return

        def save(v):
            TR.set_remission(b.booking_id, v["amount"] or "0", actor=self.principal,
                             reason=v["reason"] or None)
            self._refresh_all()
        _form(self.parent, f"Remission - {b.pupil_name} (cost {_m(b.cost_pence)})", [
            ("amount", "Amount off (£)", TR.plain(b.remission_pence), None),
            ("reason", "Reason", b.remission_reason or "", ["", *TR.REMISSION_REASONS])],
            save, note="Pupil premium or the remissions policy reduces what the family is "
                       "asked for.")

    def refund(self) -> None:
        b = self._booking("Refund")
        if b is None:
            return

        def save(v):
            TR.refund(b.booking_id, v, actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Refund - {b.pupil_name} (paid {_m(b.paid_pence)})", [
            ("amount", "Amount (£, blank = all paid)", "", None),
            ("method", "Method", "Bank Transfer", TR.PAYMENT_METHODS),
            ("reference", "Reference", "", None), ("notes", "Why (required)", "", "text")],
            save)

    def ledger(self) -> None:
        b = self._booking("Pupil ledger")
        if b is None:
            return
        led = TR.pupil_ledger(b.pupil_id)
        lines = [f"{b.pupil_name} ({b.admission_no})", ""]
        for x in led["bookings"]:
            lines.append(f"#{x.booking_id:<4} {x.trip_start} {x.trip_title[:28]:<28} {x.status:<10}"
                         f" asked {_m(x.charge_pence):>9} paid {_m(x.paid_pence):>9}")
        lines += ["", "Payments:"] + [f"  {p.paid_on} {p.kind:<8} {_m(p.signed_pence):>10} "
                                      f"{p.method:<14} {p.status:<8} {p.trip_title[:24]}"
                                      for p in led["payments"]]
        lines += ["", f"Total paid {_m(led['paid_pence'])}, balance {_m(led['balance_pence'])}"]
        _text_window(self.parent, "Pupil ledger", "\n".join(lines))

    def _open_pupil(self) -> None:
        b = self._booking("Open pupil")
        if b and self.open_pupil:
            self.open_pupil(b.pupil_id)

    # ── Payments (old tab) ───────────────────────────────────────────

    def _build_payments(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.p_vars = {k: tk.StringVar() for k in ("trip", "pupil", "method", "status",
                                                    "from", "to")}
        for label, key, values, width in (("Trip ID:", "trip", None, 6),
                                          ("Student:", "pupil", None, 10),
                                          ("Method:", "method", ["", *TR.PAYMENT_METHODS], 13),
                                          ("Status:", "status", ["", *TR.PAYMENT_STATUSES], 9),
                                          ("From:", "from", None, 11), ("To:", "to", None, 11)):
            ttk.Label(bar, text=label).pack(side="left")
            if values:
                ttk.Combobox(bar, textvariable=self.p_vars[key], values=values,
                             state="readonly", width=width).pack(side="left", padx=(2, 6))
            else:
                ttk.Entry(bar, textvariable=self.p_vars[key], width=width).pack(
                    side="left", padx=(2, 6))
        self._button(bar, "Apply", self.refresh_payments)
        self._button(bar, "Clear", self._clear_payments)
        self.p_tree = _tree(tab, [
            ("id", "Id", 50), ("booking", "Booking", 60), ("paid_on", "Paid on", 90),
            ("kind", "Kind", 70), ("amount", "Amount", 80), ("method", "Method", 110),
            ("status", "Status", 80), ("ref", "Ref", 120), ("by", "By", 100),
            ("notes", "Notes", 200)])
        self.p_tree.bind("<Double-1>", lambda _e: self.edit_payment())
        self.p_totals = tk.StringVar()
        ttk.Label(tab, textvariable=self.p_totals, anchor="w").pack(fill="x")
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(4, 0))
        self._button(bar2, "Edit", self.edit_payment, True)
        self._button(bar2, "Delete", self.delete_payment, True)
        self._button(bar2, "Export CSV…", self.export_payments)
        self._button(bar2, "Refresh", self.refresh_payments, side="right")

    def _clear_payments(self) -> None:
        for v in self.p_vars.values():
            v.set("")
        self.refresh_payments()

    def refresh_payments(self) -> None:
        f = {k: v.get().strip() for k, v in self.p_vars.items()}
        pupil = TR._pupil(f["pupil"]) if f["pupil"] else None
        rows = TR.list_payments(trip_id=int(f["trip"]) if f["trip"].isdigit() else None,
                                pupil_id=pupil.pupil_id if pupil else (-1 if f["pupil"]
                                                                       else None),
                                method=f["method"] or None, status=f["status"] or None,
                                date_from=f["from"] or None, date_to=f["to"] or None)
        self.p_tree.delete(*self.p_tree.get_children())
        self.p_rows = {}
        for p in rows:
            self.p_rows[str(p.payment_id)] = p
            self.p_tree.insert("", "end", iid=str(p.payment_id),
                               tags=(p.status if p.status in ("Pending", "Failed") else
                                     ("cancelled" if p.kind == "Refund" else ""),),
                               values=(p.payment_id, p.booking_id, p.paid_on, p.kind,
                                       _m(p.amount_pence), p.method, p.status,
                                       p.reference or "", p.received_by or "", p.notes or ""))
        self.p_totals.set(f"{len(rows)} line(s)    Net cleared: "
                          f"{_m(sum(p.signed_pence for p in rows))}")

    def _payment(self, title: str) -> TR.Payment | None:
        sel = self.p_tree.selection()
        if not sel:
            self._info(title, "Select a payment first.")
            return None
        return TR.get_payment(int(sel[0]))

    def edit_payment(self) -> None:
        p = self._payment("Edit payment")
        if p is None or not self.editor:
            return

        def save(v):
            TR.update_payment(p.payment_id, v, actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Edit {p.kind.lower()} #{p.payment_id}", [
            ("amount", "Amount (£)", TR.plain(p.amount_pence), None),
            ("paid_on", "Paid on", p.paid_on, None),
            ("method", "Method", p.method, TR.PAYMENT_METHODS),
            ("status", "Status", p.status, TR.PAYMENT_STATUSES),
            ("reference", "Reference", p.reference or "", None),
            ("recorded_by", "Recorded by", p.received_by or "", None),
            ("notes", "Notes", p.notes or "", "text")], save)

    def delete_payment(self) -> None:
        p = self._payment("Delete payment")
        if p is None or not messagebox.askyesno(
                "Delete payment", f"Delete {p.kind.lower()} #{p.payment_id} "
                                  f"({_m(p.amount_pence)})?", parent=self._top()):
            return
        if self._run("Delete payment", TR.delete_payment, p.payment_id, actor=self.principal):
            self._refresh_all()

    def export_payments(self) -> None:
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="trip-payments.csv")
        if path:
            n = self._run("Export", TR.export_payments_csv, path, actor=self.principal)
            if n is not None:
                self._info("Export", f"Exported {n} line(s).")

    # ── Summary (old tab) ────────────────────────────────────────────

    def _build_summary(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self._button(bar, "Refresh", self.refresh_summary)
        self.sum_text = tk.Text(tab, wrap="word", font=("TkFixedFont", 10), state="disabled")
        self.sum_text.pack(fill="both", expand=True)

    def refresh_summary(self) -> None:
        s = TR.summary()
        L = ["Trips", "-----", f"  Total              : {s['total_trips']}",
             f"  Upcoming           : {s['upcoming_trips']}",
             f"  Open for booking   : {s['open_for_booking']}",
             f"  Awaiting approval  : {s['awaiting_approval']}",
             f"  Completed          : {s['completed']}",
             f"  Cancelled          : {s['cancelled']}"]
        if s["next_trip"]:
            t = s["next_trip"]
            L += ["", f"  Next: #{t.trip_id}  {t.start_date}  {t.title}  ({t.status})"]
        L += ["", "Bookings", "--------", f"  Total              : {s['total_bookings']}",
              f"  Active             : {s['active_bookings']}",
              f"  Waitlist           : {s['waitlist_count']}",
              f"  Consent missing    : {s['consent_missing']}", "",
              "Money (active bookings)", "-----------------------",
              f"  Charged            : {_m(s['total_charged'])}",
              f"  Paid               : {_m(s['total_paid'])}",
              f"  Outstanding        : {_m(s['total_outstanding'])}",
              f"  Remissions         : {_m(s['total_remitted'])}",
              f"  Behind plan        : {_m(s['overdue_balance'])}"]
        for title, data, fmt in (("Trips by status", s["by_trip_status"], str),
                                 ("Bookings by status", s["by_booking_status"], str),
                                 ("Payment states (active bookings)", s["by_payment_state"],
                                  str), ("Payments by method", s["by_method"], _m)):
            L += ["", title, "-" * len(title)]
            L += [f"  {k:<22} : {fmt(v)}" for k, v in data.items() if v]
        if s["top_trips_by_revenue"]:
            L += ["", "Top trips by revenue", "--------------------"]
            L += [f"  #{tid:<3}  {name[:30]:<30}  {_m(rev)}"
                  for tid, name, rev in s["top_trips_by_revenue"]]
        self.sum_text.configure(state="normal")
        self.sum_text.delete("1.0", "end")
        self.sum_text.insert("1.0", "\n".join(L))
        self.sum_text.configure(state="disabled")

    # ── Arrears ──────────────────────────────────────────────────────

    def _build_arrears(self, tab) -> None:
        ttk.Label(tab, text="Families behind the payment plan (a voluntary contribution is "
                            "asked for, never chased as a debt).",
                  foreground="#555").pack(anchor="w", pady=(0, 4))
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self._button(bar, "Send reminders to selected", lambda: self.remind(True), True)
        self._button(bar, "Send reminders to all", lambda: self.remind(False), True)
        self._button(bar, "Refresh", self.refresh_arrears, side="right")
        self.a_tree = _tree(tab, [("pupil", "Pupil", 200), ("trip", "Trip", 200),
                                  ("type", "Charging", 140), ("due", "Due so far", 90),
                                  ("paid", "Paid", 80), ("behind", "Behind", 80),
                                  ("last", "Last reminder", 130)], select="extended", height=10)
        self.a_rows: dict[str, dict] = {}
        ttk.Label(tab, text="Refunds due (cancelled trips or places still holding money)",
                  font=("", 11, "bold")).pack(anchor="w", pady=(8, 4))
        self.r_tree = _tree(tab, [("pupil", "Pupil", 220), ("trip", "Trip", 220),
                                  ("status", "Status", 100), ("paid", "Held", 90)], height=5)

    def refresh_arrears(self) -> None:
        self.a_tree.delete(*self.a_tree.get_children())
        self.a_rows = {}
        for r in TR.arrears():
            b = r["booking"]
            self.a_rows[str(b.booking_id)] = r
            self.a_tree.insert("", "end", iid=str(b.booking_id), values=(
                f"{b.pupil_name} ({b.admission_no})", b.trip_title,
                "Voluntary" if r["voluntary"] else "Chargeable", _m(r["due_pence"]),
                _m(b.paid_pence), _m(r["behind_pence"]), (b.last_reminder_at or "")[:16]))
        self.r_tree.delete(*self.r_tree.get_children())
        for t in TR.list_trips():
            for b in TR.refunds_due(t.trip_id):
                self.r_tree.insert("", "end", values=(b.pupil_name, t.title, b.status,
                                                      _m(b.paid_pence)))

    def remind(self, selected: bool) -> None:
        ids = [int(x) for x in self.a_tree.selection()] if selected else None
        if selected and not ids:
            self._info("Reminders", "Select families first.")
            return
        res = self._run("Reminders", TR.send_reminders, actor=self.principal, booking_ids=ids)
        if res:
            self.refresh_arrears()
            self._deliver("Reminders", res)

    # ── On the day ───────────────────────────────────────────────────

    def _build_day(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="Trip:").pack(side="left")
        self.d_trip = tk.StringVar(value=self.state.get("d_trip", ""))
        self.d_box = ttk.Combobox(bar, textvariable=self.d_trip, width=40, state="readonly")
        self.d_box.pack(side="left", padx=(4, 8))
        self.d_box.bind("<<ComboboxSelected>>", lambda _e: self.refresh_day())
        self._button(bar, "Refresh", self.refresh_day)
        self.d_count = tk.StringVar()
        ttk.Label(tab, textvariable=self.d_count, font=("", 11, "bold")).pack(anchor="w")
        self.d_tree = _tree(tab, [("pupil", "Pupil", 220), ("form", "Form", 60),
                                  ("consent", "Consent", 70), ("medical", "Medical", 200),
                                  ("dietary", "Dietary", 140), ("out", "Departed", 120),
                                  ("back", "Returned", 120)], select="extended")
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(4, 0))
        for text, cmd, lead in (("Departed", lambda: self._mark("departed", True), False),
                                ("Returned", lambda: self._mark("returned", True), False),
                                ("Undo departed", lambda: self._mark("departed", False), False),
                                ("Undo returned", lambda: self._mark("returned", False), False),
                                ("Ratio check", self.ratio, False),
                                ("Mark registers (V)", self.mark_registers, True)):
            self._button(bar2, text, cmd, lead)
        self.d_rows: dict[str, TR.Booking] = {}

    def _day_trip(self) -> TR.Trip | None:
        tid = self._trip_id(self.d_trip.get())
        return TR.get(tid) if tid else None

    def refresh_day(self) -> None:
        trips = [t for t in TR.list_trips() if t.approved and t.status != "Cancelled"]
        today = TR._today().isoformat()
        choices = [f"{t.trip_id} - {t.start_date} {t.title}" for t in sorted(
            trips, key=lambda t: (not (t.start_date <= today <= t.last_day), t.start_date))]
        self.d_box.configure(values=choices)
        if not self._trip_id(self.d_trip.get()) and choices:
            self.d_trip.set(choices[0])
        self.state["d_trip"] = self.d_trip.get()
        self.d_tree.delete(*self.d_tree.get_children())
        self.d_rows = {}
        t = self._day_trip()
        if t is None:
            self.d_count.set("No approved trips.")
            return
        for b in TR.list_bookings(t.trip_id):
            if b.status not in TR.PLACE_STATUSES:
                continue
            self.d_rows[str(b.booking_id)] = b
            tag = "bad" if b.departed and not b.returned else ("good" if b.returned else (
                "warn" if not b.consent_received else ""))
            self.d_tree.insert("", "end", iid=str(b.booking_id), tags=(tag,), values=(
                f"{b.pupil_name} ({b.admission_no})", b.form_group or "", b.consent or "-",
                b.medical_note or "", b.dietary_note or "", (b.departed_at or "")[11:16]
                or ("" if not b.departed else "yes"), (b.returned_at or "")[11:16]))
        h = TR.headcount(t.trip_id)
        r = h["ratio"]
        self.d_count.set(f"{t.title} ({t.period})    Places {h['places']}    Departed "
                         f"{h['departed']}    Returned {h['returned']}    Still out "
                         f"{len(h['still_out'])}    Adults {r['staff']} / needed {r['needed']}"
                         + ("" if r["ok"] else "  - RATIO NOT MET"))

    def _mark(self, field: str, value: bool) -> None:
        t = self._day_trip()
        ids = [int(x) for x in self.d_tree.selection()]
        if t is None or not ids:
            self._info("Trip register", "Choose the trip and select pupils.")
            return
        fn = TR.mark_departed if field == "departed" else TR.mark_returned
        kw = {field: value}
        if self._run("Trip register", fn, t.trip_id, ids, actor=self.principal, **kw) is not None:
            self.refresh_day()

    def ratio(self) -> None:
        t = self._day_trip()
        if t:
            r = TR.ratio_check(t)
            self._info("Ratio check", f"{r['staff']} adult(s): {', '.join(t.staff_names) or '-'}"
                                      f"\n{r['pupils']} pupil(s) at 1:{r['per_adult']} needs "
                                      f"{r['needed']} adult(s).\n\n"
                                      + ("Ratio met." if r["ok"] else "Ratio NOT met."))

    def mark_registers(self) -> None:
        t = self._day_trip()
        if t is None or not messagebox.askyesno(
                "Mark registers", "Put code V (educational visit) on the AM and PM registers "
                                  "for the pupils who went, up to today?", parent=self._top()):
            return
        r = self._run("Mark registers", TR.mark_attendance, t.trip_id, actor=self.principal)
        if r:
            self._info("Mark registers", f"Marked {r['saved']} session(s) for {r['pupils']} "
                                         f"pupil(s); kept {r['skipped']} already marked.")

    # ── Approvals ────────────────────────────────────────────────────

    def _build_approvals(self, tab) -> None:
        ttk.Label(tab, text="Trips waiting for the educational visits coordinator.",
                  foreground="#555").pack(anchor="w", pady=(0, 4))
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self._button(bar, "View", lambda: self._approval_view())
        self._button(bar, "Risk assessment", lambda: self._approval_risk())
        self._button(bar, "Approve…", lambda: self._decide("approved"), True)
        self._button(bar, "Decline…", lambda: self._decide("declined"), True)
        self._button(bar, "Refresh", self.refresh_approvals, side="right")
        self.ap_tree = _tree(tab, [("id", "Id", 50), ("name", "Trip", 240),
                                   ("start", "Start", 90), ("type", "Type", 180),
                                   ("leader", "Leader", 140), ("by", "Submitted by", 120),
                                   ("risk", "Risk reviewed", 120)])

    def refresh_approvals(self) -> None:
        self.ap_tree.delete(*self.ap_tree.get_children())
        for t in TR.awaiting_approval():
            self.ap_tree.insert("", "end", iid=str(t.trip_id), values=(
                t.trip_id, t.title, t.start_date, t.flags, t.leader or "",
                t.submitted_by or "", t.risk_reviewed_on or "NOT REVIEWED"))

    def _ap_trip(self) -> TR.Trip | None:
        sel = self.ap_tree.selection()
        if not sel:
            self._info("Approvals", "Select a trip first.")
            return None
        return TR.get(int(sel[0]))

    def _approval_view(self) -> None:
        t = self._ap_trip()
        if t:
            _text_window(self.parent, f"Trip #{t.trip_id}", _trip_text(t))

    def _approval_risk(self) -> None:
        t = self._ap_trip()
        if t:
            _text_window(self.parent, "Risk assessment",
                         (f"File: {t.risk_file}\n\n" if t.risk_file else "")
                         + (t.risk_assessment or "(no text)"))

    def _decide(self, decision: str) -> None:
        t = self._ap_trip()
        if t is None:
            return

        def save(v):
            TR.decide_approval(t.trip_id, decision, actor=self.principal, note=v["note"])
            self._refresh_all()
        _form(self.parent, f"{'Approve' if decision == 'approved' else 'Decline'} - {t.title}",
              [("note", "Note" + (" (required)" if decision == "declined" else ""), "",
                "text")], save)


def draw_trips(parent: ttk.Frame, *, principal: Principal, state: dict,
               open_pupil: Callable[[int], None] | None = None) -> TripsPage:
    return TripsPage(parent, principal=principal, state=state, open_pupil=open_pupil)
