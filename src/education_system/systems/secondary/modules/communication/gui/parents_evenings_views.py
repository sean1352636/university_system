"""Parents' Evenings screen.

The old window's tabs keep their place and controls:

* **Events** - Year and Status filters, Open only, Apply, Clear; columns ID,
  Date, Time, Name, Year, Location, Slot, Status; View, New, Edit, Status,
  Delete, Refresh; the event form (Name, Date, Year group, Location, Start
  time, End time, Slot length, Status, Notes). Added: mode, meeting link,
  break slots and the booking window in the form, and Teachers from groups,
  Invite families…, E-mail schedules…, Export CSV… and History.
* **Bookings** - Event and Status filters, Apply; columns #, Slot, Pupil,
  Pupil name, Teacher, Teacher name, Parent, Status; New, Edit, Status,
  Delete, Refresh. Added: Attended, Missed, Teacher notes…, Cancel, Open
  pupil, Export CSV…; New offers only the pupil's teachers and the slots when
  both teacher and family are free.
* **Schedules** - Event, View (Teacher / Pupil), Pick, Load, Refresh; free
  slots greyed. Added: My schedule, Print / save…, Export CSV… and E-mail
  this family.
* **Summary** - Refresh and the overall summary, with the chosen evening's
  figures added.

New tabs: **Teachers** (who takes part, rooms, breaks, availability) and
**Rates** (booking rates by teacher and by form; families not booked yet).
The rules are in :mod:`modules.communication.domain.parents_evenings`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.communication.domain import parents_evenings as PE
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
_ERRORS = W.ERRORS
_problems = W.problems
_text_window = W.text_window
_form = W.form_dialog
_TAGS = {**W.STANDARD_TAGS, "Cancelled": {"foreground": "#888"},
         "No-Show": {"background": "#ffe0e0"}, "Attended": {"background": "#e7f6ea"},
         "FREE": {"foreground": "#888", "background": "#f5f5f5"},
         "BREAK": {"foreground": "#aaa"}, "Open": {"background": "#e6f7e0"}}


def _tree(parent, columns, height: int = 16) -> ttk.Treeview:
    return W.tree(parent, columns, height=height,
                  stretch={"name", "pupil_name", "with_name", "notes", "group", "groups"},
                  tags=_TAGS)


def _event_fields(e: PE.Event | None) -> list:
    """The old event form, in its order, then the new fields."""
    return [
        ("name", "Name", e.name if e else "", None),
        ("event_date", "Date (YYYY-MM-DD)", e.event_date if e else "", None),
        ("year_group", "Year group", e.year_label.replace("Year ", "") if e and e.year_group
         else "All years", list(PE.YEAR_CHOICES)),
        ("location", "Location", e.location if e else "", None),
        ("start_time", "Start time (HH:MM)", e.start_time if e else "16:00", None),
        ("end_time", "End time (HH:MM)", e.end_time if e else "19:00", None),
        ("slot_minutes", "Slot length (min)", e.slot_minutes if e else 10, None),
        ("status", "Status", e.status if e else PE.DEFAULT_EVENT_STATUS,
         list(PE.EVENT_STATUSES)),
        ("notes", "Notes", e.notes if e else "", "text"),
        ("mode", "In person / online", e.mode if e else PE.DEFAULT_MODE, list(PE.MODES)),
        ("meeting_link", "Meeting link (online)", e.meeting_link if e else "", None),
        ("break_slots", "Break slots (e.g. 17:30, 18:00)", e.break_slots if e else "", None),
        ("booking_opens", "Families book from (date)", e.booking_opens if e else "", None),
        ("booking_closes", "Families book until (date)", e.booking_closes if e else "", None),
    ]


class ParentsEveningsPage:
    TABS = ("Events", "Bookings", "Schedules", "Teachers", "Rates", "Summary")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = PE.is_editor(principal)
        self.me = PE.teacher_key_for(principal)
        activity_log.record("parents_evenings.view")
        ttk.Label(parent, text="Parents' Evenings", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        self._event_boxes: list[tuple[ttk.Combobox, tk.StringVar]] = []
        self._event_ids: dict[str, int] = {}
        start = state.get("tab") if state.get("tab") in self.TABS else "Events"
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

    def _button(self, bar, text: str, command, enabled: bool = True) -> ttk.Button:
        b = ttk.Button(bar, text=text, command=command)
        if not enabled:
            b.state(["disabled"])
        b.pack(side="left", padx=2)
        return b

    def _run(self, title: str, fn: Callable[[], Any]) -> Any:
        try:
            return fn()
        except _ERRORS as e:
            self._err(title, e)
            return None

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        build = {"Events": (self._build_events, self.refresh),
                 "Bookings": (self._build_bookings, self.refresh_bookings),
                 "Schedules": (self._build_schedules, self.refresh_schedule),
                 "Teachers": (self._build_teachers, self.refresh_teachers),
                 "Rates": (self._build_rates, self.refresh_rates),
                 "Summary": (self._build_summary, self.refresh_summary)}[name]
        if name not in self._built:
            self._built.add(name)
            build[0](self.tabs[name])
        build[1]()

    def _refresh_all(self) -> None:
        self._load_event_choices()
        for name, fn in (("Events", self.refresh), ("Bookings", self.refresh_bookings),
                         ("Schedules", self.refresh_schedule),
                         ("Teachers", self.refresh_teachers), ("Rates", self.refresh_rates),
                         ("Summary", self.refresh_summary)):
            if name in self._built:
                fn()

    # ── the chosen evening (shared by the tabs) ──────────────────────

    def _event_label(self, e: PE.Event) -> str:
        return f"#{e.event_id}  {e.event_date} {e.times}  {e.name} ({e.status})"

    def _load_event_choices(self) -> None:
        events = PE.list_events()
        self._event_ids = {self._event_label(e): e.event_id for e in events}
        labels = list(self._event_ids)
        want = self.state.get("event")
        current = next((lab for lab, i in self._event_ids.items() if i == want), None)
        if current is None:
            upcoming = PE.list_events(upcoming=True)
            current = self._event_label(upcoming[0]) if upcoming else (labels[-1] if labels
                                                                       else "")
        for cb, var in self._event_boxes:
            cb.configure(values=labels)
            var.set(current)
        self.state["event"] = self._event_ids.get(current)

    def _event_combo(self, bar, on_change: Callable[[], None]) -> tk.StringVar:
        ttk.Label(bar, text="Event:").pack(side="left")
        var = tk.StringVar()
        cb = ttk.Combobox(bar, textvariable=var, state="readonly", width=55)
        cb.pack(side="left", padx=6)

        def changed(_e=None) -> None:
            self.state["event"] = self._event_ids.get(var.get())
            for _cb, v in self._event_boxes:
                v.set(var.get())
            on_change()
        cb.bind("<<ComboboxSelected>>", changed)
        self._event_boxes.append((cb, var))
        self._load_event_choices()
        return var

    def _event(self, title: str) -> PE.Event | None:
        eid = self.state.get("event")
        e = PE.find_event(eid) if eid else None
        if e is None:
            self._info(title, "Choose an evening first (or create one on the Events tab).")
        return e

    # ── Events (the old Events tab) ──────────────────────────────────

    def _build_events(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.f_year = tk.StringVar(value=self.state.get("year", ""))
        self.f_status = tk.StringVar(value=self.state.get("status", ""))
        self.f_open = tk.BooleanVar(value=bool(self.state.get("open_only")))
        ttk.Label(bar, text="Year:").pack(side="left")
        ttk.Combobox(bar, textvariable=self.f_year, values=["", *PE.YEAR_CHOICES[1:]],
                     state="readonly", width=5).pack(side="left", padx=(4, 8))
        ttk.Label(bar, text="Status:").pack(side="left")
        ttk.Combobox(bar, textvariable=self.f_status, values=["", *PE.EVENT_STATUSES],
                     state="readonly", width=18).pack(side="left", padx=(4, 8))
        ttk.Checkbutton(bar, text="Open only", variable=self.f_open).pack(side="left")
        self._button(bar, "Apply", self.refresh)
        self._button(bar, "Clear", self._clear)
        self.tree = _tree(tab, [("id", "ID", 50), ("date", "Date", 95), ("time", "Time", 100),
                                ("name", "Name", 260), ("year", "Year", 80),
                                ("location", "Location", 160), ("slot", "Slot", 50),
                                ("status", "Status", 140), ("mode", "Mode", 120)])
        self.tree.bind("<Double-1>", lambda _e: self.view())
        self.tree.bind("<<TreeviewSelect>>", self._pick_event)
        self.count_var = tk.StringVar()
        ttk.Label(tab, textvariable=self.count_var).pack(anchor="w")
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(4, 0))
        for text, cmd, ok in (("View", self.view, True), ("New", self.new, self.editor),
                              ("Edit", self.edit, self.editor),
                              ("Status", self.set_status, self.editor),
                              ("Delete", self.delete, self.editor),
                              ("Refresh", self.refresh, True)):
            self._button(bar2, text, cmd, ok)
        bar3 = ttk.Frame(tab)
        bar3.pack(fill="x", pady=(4, 0))
        for text, cmd, ok in (("Teachers from groups", self.sync, self.editor),
                              ("Invite families…", self.invite, self.editor),
                              ("E-mail schedules…", self.email_schedules, True),
                              ("Export CSV…", self.export, True),
                              ("History", self.history, True)):
            self._button(bar3, text, cmd, ok)
        self.rows: dict[str, PE.Event] = {}

    def _clear(self) -> None:
        self.f_year.set("")
        self.f_status.set("")
        self.f_open.set(False)
        self.refresh()

    def refresh(self) -> None:
        self.state.update(year=self.f_year.get(), status=self.f_status.get(),
                          open_only=self.f_open.get())
        rows = self._run("Parents' Evenings", lambda: PE.list_events(
            year_group=self.f_year.get() or None, status=self.f_status.get() or None,
            open_only=self.f_open.get()))
        if rows is None:
            return
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for e in rows:
            self.rows[str(e.event_id)] = e
            tag = "Cancelled" if e.status == "Cancelled" else (
                "Open" if e.status == "Open for Booking" else "")
            self.tree.insert("", "end", iid=str(e.event_id), tags=(tag,) if tag else (),
                             values=(e.event_id, e.event_date, e.times, e.name, e.year_label,
                                     e.location or "", e.slot_minutes, e.status, e.mode))
        self.count_var.set(f"{len(rows)} event(s)")
        keep = str(self.state.get("event") or "")
        if keep in self.rows:
            self.tree.selection_set(keep)
            self.tree.see(keep)
        s = PE.summary()
        self.summary_var.set(f"Events: {s.total_events}    Upcoming: {s.upcoming_events}    "
                             f"Open for booking: {s.open_for_booking}    Bookings: "
                             f"{s.total_bookings}")

    def _pick_event(self, _e=None) -> None:
        sel = self.tree.selection()
        if sel:
            self.state["event"] = int(sel[0])
            self._load_event_choices()

    def _selected(self, title: str) -> PE.Event | None:
        sel = self.tree.selection()
        if not sel:
            self._info(title, "Select an event first.")
            return None
        return self.rows[sel[0]]

    def view(self) -> None:
        e = self._selected("View event")
        if e is None:
            return
        s = PE.summarize_event(e.event_id)
        lines = [f"#{e.event_id}  {e.name}", "",
                 f"Date:        {e.event_date}  {e.times}",
                 f"Slots:       {e.slot_minutes} min ({s.total_slots} per teacher)"
                 + (f", breaks {', '.join(e.breaks)}" if e.breaks else ""),
                 f"Year group:  {e.year_label}", f"Where:       {e.venue}",
                 f"Status:      {e.status}",
                 f"Families book: {e.booking_opens or '-'} to {e.booking_closes or '-'}",
                 f"Invitations: {(e.invitations_sent_at or 'not sent')[:16]}", "",
                 f"Teachers: {s.teachers}   Capacity: {s.capacity}   Booked: {s.bookings} "
                 f"({s.fill_rate}%)   Pupils booked: {s.pupils_booked} of {s.pupils_in_year}"]
        if e.notes:
            lines += ["", e.notes]
        _text_window(self.parent, f"Event #{e.event_id}", "\n".join(lines))

    def new(self) -> None:
        def save(v):
            e = PE.create_event(v, actor=self.principal)
            self.state["event"] = e.event_id
            self._refresh_all()
            n = len(PE.list_teachers(e.event_id))
            self._info("New event", f"Event #{e.event_id} saved with {n} teacher(s) from the "
                                    "year's teaching groups.")
        _form(self.parent, "New event", _event_fields(None), save,
              note="Teachers are filled in from the year group's teaching groups.")

    def edit(self) -> None:
        e = self._selected("Edit event")
        if e is None:
            return

        def save(v):
            PE.update_event(e.event_id, v, actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Edit event #{e.event_id}", _event_fields(e), save)

    def set_status(self) -> None:
        e = self._selected("Status")
        if e is None:
            return

        def save(v):
            PE.set_event_status(e.event_id, v["status"], actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Status - event #{e.event_id}",
              [("status", "New status", e.status, list(PE.EVENT_STATUSES))], save,
              note="Families book through the portal while it is Open for Booking.")

    def delete(self) -> None:
        e = self._selected("Delete event")
        if e is None or not messagebox.askyesno(
                "Delete event", f"Delete '{e.name}' and all its bookings?", parent=self._top()):
            return
        if self._run("Delete event", lambda: PE.delete_event(e.event_id, actor=self.principal)):
            self.state["event"] = None
            self._refresh_all()

    def sync(self) -> None:
        e = self._selected("Teachers from groups")
        if e is None:
            return
        r = self._run("Teachers from groups", lambda: PE.sync_teachers(e.event_id,
                                                                       actor=self.principal))
        if r:
            self._refresh_all()
            self._info("Teachers from groups", f"Added {r['added']}, removed {r['removed']}; "
                                               f"{r['teachers']} teacher(s) taking part.")

    def _deliver(self, title: str, res: dict[str, Any], what: str) -> None:
        missing = res.get("no_email") or []
        extra = (f"\n\n{len(missing)} pupil(s) have no contact with an e-mail address: "
                 + ", ".join(p.display_name for p in missing[:10] if p)
                 + ("…" if len(missing) > 10 else "")) if missing else ""
        if not res.get("message_id"):
            self._info(title, "Nobody to e-mail." + extra)
            return
        from education_system.systems.secondary.modules.communication.gui import email_views
        text = f"{res['emails']} {what} prepared." + extra

        def done(_report, error) -> None:
            try:
                self._info(title, text + (f"\n\nQueued - delivery failed: {error}" if error
                                          else "\n\nSent."))
            except tk.TclError:
                pass
        email_views.deliver_in_background(self.parent, res["message_id"], self.principal, done)

    def invite(self) -> None:
        e = self._selected("Invite families")
        if e is None:
            return

        def save(v):
            res = PE.send_invitations(e.event_id, actor=self.principal, note=v["note"])
            self._refresh_all()
            self._deliver("Invite families", res, "invitation(s)")
        _form(self.parent, f"Invite families - {e.name}",
              [("note", "Extra message (optional)", "", "text")], save,
              note=f"An invitation goes to the families of {e.year_label} (one e-mail per "
                   "address, naming each child)" + (f". Already sent "
                                                    f"{e.invitations_sent_at[:16]}."
                                                    if e.invitations_sent_at else "."))

    def email_schedules(self) -> None:
        e = self._selected("E-mail schedules")
        if e is None:
            return

        def save(v):
            res = PE.email_schedules(e.event_id, actor=self.principal,
                                     unsent_only=bool(v["unsent"]))
            self._refresh_all()
            self._deliver("E-mail schedules", res, "schedule(s)")
        _form(self.parent, f"E-mail schedules - {e.name}",
              [("unsent", "Only families not sent one yet", True, "check")], save,
              note="Each family gets their appointments (brothers and sisters together)."
              + ("" if self.editor else " You can send to families booked with you."))

    def export(self) -> None:
        e = self._selected("Export")
        if e is None:
            return
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile=f"parents-evening-{e.event_id}.csv")
        if path:
            n = self._run("Export", lambda: PE.export_csv(path, actor=self.principal,
                                                          event_id=e.event_id))
            if n is not None:
                self._info("Export", f"Exported {n} booking(s).")

    def history(self) -> None:
        e = self._selected("History")
        if e is None:
            return
        _text_window(self.parent, "History", "\n".join(
            f"{h['at']}  {h['actor']:<14} {h['action']:<16} "
            + ", ".join(f"{k}={v}" for k, v in h["detail"].items())
            for h in PE.history(e.event_id)) or "No changes recorded.")

    # ── Bookings (the old Bookings tab) ──────────────────────────────

    def _build_bookings(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self._event_combo(bar, self.refresh_bookings)
        ttk.Label(bar, text="Status:").pack(side="left")
        self.b_status = tk.StringVar(value="")
        ttk.Combobox(bar, textvariable=self.b_status, values=["", *PE.BOOKING_STATUSES],
                     state="readonly", width=12).pack(side="left", padx=(4, 8))
        self.b_mine = tk.BooleanVar(value=not self.editor)
        ttk.Checkbutton(bar, text="Mine only", variable=self.b_mine).pack(side="left")
        self._button(bar, "Apply", self.refresh_bookings)
        self.b_tree = _tree(tab, [("id", "#", 50), ("slot", "Slot", 60),
                                  ("pupil", "Pupil", 90), ("pupil_name", "Pupil name", 180),
                                  ("staff", "Teacher", 90), ("staff_name", "Teacher name", 160),
                                  ("parent", "Parent", 150), ("status", "Status", 90),
                                  ("via", "Booked", 70)])
        self.b_tree.bind("<Double-1>", lambda _e: self.edit_booking())
        self.b_count = tk.StringVar()
        ttk.Label(tab, textvariable=self.b_count).pack(anchor="w")
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(4, 0))
        for text, cmd in (("New", self.new_booking), ("Edit", self.edit_booking),
                          ("Status", self.booking_status), ("Delete", self.delete_booking),
                          ("Refresh", self.refresh_bookings)):
            self._button(bar2, text, cmd, self.editor if text == "Delete" else True)
        bar3 = ttk.Frame(tab)
        bar3.pack(fill="x", pady=(4, 0))
        for text, cmd in (("Attended", lambda: self.attendance(True)),
                          ("Missed", lambda: self.attendance(False)),
                          ("Teacher notes…", self.teacher_notes), ("Cancel", self.cancel),
                          ("Open pupil", self._open_booking_pupil)):
            self._button(bar3, text, cmd)
        self.b_rows: dict[str, PE.Booking] = {}

    def refresh_bookings(self) -> None:
        if not hasattr(self, "b_tree"):
            return
        self.b_tree.delete(*self.b_tree.get_children())
        self.b_rows = {}
        eid = self.state.get("event")
        if not eid:
            self.b_count.set("No evening chosen.")
            return
        rows = PE.list_bookings(event_id=eid, status=self.b_status.get() or None,
                                teacher_key=self.me if self.b_mine.get() else None)
        for b in rows:
            self.b_rows[str(b.booking_id)] = b
            self.b_tree.insert("", "end", iid=str(b.booking_id),
                               tags=(b.status,) if b.status != "Booked" else (),
                               values=(b.booking_id, b.slot_time, b.admission_no, b.pupil_name,
                                       b.teacher_key if not b.teacher_key.startswith("name:")
                                       else "", b.teacher_name, b.parent_name or "", b.status,
                                       b.booked_via))
        self.b_count.set(f"{len(rows)} booking(s)")

    def _booking(self, title: str) -> PE.Booking | None:
        sel = self.b_tree.selection() if hasattr(self, "b_tree") else ()
        if not sel:
            self._info(title, "Select a booking first.")
            return None
        return self.b_rows[sel[0]]

    def new_booking(self) -> None:
        e = self._event("New booking")
        if e is None:
            return

        def save(v):
            p = PE._pupil(v["pupil"])
            if p is None:
                raise PE.ValidationError([f"No pupil {v['pupil'] or ''}".strip()])
            self._booking_dialog(e, p)
        _form(self.parent, f"New booking - {e.name}",
              [("pupil", "Pupil (admission no. or ID)", "", None)], save,
              note="Next you choose one of the pupil's teachers and a time when both the "
                   "teacher and the family are free.")

    def _booking_dialog(self, e: PE.Event, p) -> None:
        mine = PE.teachers_for_pupil(e.event_id, p.pupil_id)
        teachers = {f"{x['teacher'].teacher_name} - {', '.join(x['subjects'])}":
                    x["teacher"].teacher_key for x in mine}
        if self.editor:
            for t in PE.list_teachers(e.event_id, available_only=True):
                teachers.setdefault(f"{t.teacher_name} (does not teach {p.display_name})",
                                    t.teacher_key)
        else:
            teachers = {k: v for k, v in teachers.items() if v == self.me}
        if not teachers:
            self._info("New booking", f"None of {p.display_name}'s teachers you can book is "
                                      "taking part in this evening.")
            return
        win, frm = W.dialog(self.parent, f"Book - {p.display_name}")
        tvar, svar = tk.StringVar(), tk.StringVar()
        pvar, nvar = tk.StringVar(value=PE.parent_names(p.pupil_id)), tk.StringVar()
        ttk.Label(frm, text="Teacher:").grid(row=0, column=0, sticky="w", pady=2)
        tcb = ttk.Combobox(frm, textvariable=tvar, values=list(teachers), state="readonly",
                           width=50)
        tcb.grid(row=0, column=1, sticky="w")
        ttk.Label(frm, text="Slot:").grid(row=1, column=0, sticky="w", pady=2)
        scb = ttk.Combobox(frm, textvariable=svar, state="readonly", width=12)
        scb.grid(row=1, column=1, sticky="w")
        free_var = tk.StringVar()
        ttk.Label(frm, textvariable=free_var, foreground="#666").grid(row=2, column=1,
                                                                      sticky="w")
        for i, (label, var) in enumerate((("Parent name:", pvar), ("Notes:", nvar)), start=3):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=2)
            ttk.Entry(frm, textvariable=var, width=50).grid(row=i, column=1, sticky="w")

        def pick(_e=None) -> None:
            key = teachers.get(tvar.get())
            slots = PE.free_slots(e.event_id, key, pupil_id=p.pupil_id) if key else []
            scb.configure(values=slots)
            svar.set(slots[0] if slots else "")
            free_var.set(f"{len(slots)} free slot(s) for the teacher and the family"
                         if key else "")
        tcb.bind("<<ComboboxSelected>>", pick)

        def save() -> None:
            try:
                PE.create_booking(e.event_id, {"pupil_id": p.pupil_id,
                                               "teacher_key": teachers.get(tvar.get(), ""),
                                               "slot_time": svar.get(),
                                               "parent_name": pvar.get(), "notes": nvar.get()},
                                  actor=self.principal)
            except _ERRORS as ex:
                messagebox.showerror("Book", _problems(ex), parent=win)
                return
            self._refresh_all()
            pick()   # stay open to book the next teacher
        bar = ttk.Frame(frm)
        bar.grid(row=5, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(bar, text="Close", command=win.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(bar, text="Book", command=save).pack(side="right")

    def edit_booking(self) -> None:
        b = self._booking("Edit booking")
        if b is None:
            return
        e = PE.get_event(b.event_id)
        slots = [b.slot_time, *PE.free_slots(e.event_id, b.teacher_key, pupil_id=b.pupil_id,
                                             skip=b.booking_id)]
        teachers = {t.teacher_name: t.teacher_key for t in PE.list_teachers(e.event_id)}

        def save(v):
            PE.update_booking(b.booking_id, {**v, "teacher_key": teachers.get(
                v.pop("teacher"), b.teacher_key)}, actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Edit booking #{b.booking_id} - {b.pupil_name}", [
            ("teacher", "Teacher", b.teacher_name,
             list(teachers) if self.editor else [b.teacher_name]),
            ("slot_time", "Slot", b.slot_time, ("edit", sorted(set(slots)))),
            ("status", "Status", b.status, list(PE.BOOKING_STATUSES)),
            ("parent_name", "Parent name", b.parent_name or "", None),
            ("notes", "Notes", b.notes or "", "text"),
            ("teacher_notes", "Teacher notes", b.teacher_notes or "", "text")], save)

    def booking_status(self) -> None:
        b = self._booking("Status")
        if b is None:
            return

        def save(v):
            PE.set_booking_status(b.booking_id, v["status"], actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Status - booking #{b.booking_id}",
              [("status", "New status", b.status, list(PE.BOOKING_STATUSES))], save)

    def delete_booking(self) -> None:
        b = self._booking("Delete booking")
        if b and messagebox.askyesno("Delete booking", f"Delete booking #{b.booking_id} "
                                     f"({b.pupil_name} with {b.teacher_name})?",
                                     parent=self._top()):
            if self._run("Delete booking", lambda: PE.delete_booking(b.booking_id,
                                                                     actor=self.principal)):
                self._refresh_all()

    def attendance(self, attended: bool) -> None:
        b = self._booking("Attendance")
        if b and self._run("Attendance", lambda: PE.record_attendance(
                b.booking_id, attended, actor=self.principal)):
            self._refresh_all()

    def teacher_notes(self) -> None:
        b = self._booking("Teacher notes")
        if b is None:
            return

        def save(v):
            PE.add_teacher_notes(b.booking_id, v["notes"], actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Notes - {b.pupil_name} with {b.teacher_name}",
              [("notes", "What was discussed / agreed", b.teacher_notes or "", "text")], save)

    def cancel(self) -> None:
        b = self._booking("Cancel")
        if b and messagebox.askyesno("Cancel", f"Cancel {b.pupil_name}'s {b.slot_time} "
                                     f"appointment with {b.teacher_name}?", parent=self._top()):
            if self._run("Cancel", lambda: PE.cancel_booking(b.booking_id,
                                                             actor=self.principal)):
                self._refresh_all()

    def _open_booking_pupil(self) -> None:
        b = self._booking("Open pupil")
        if b and self.open_pupil:
            self.open_pupil(b.pupil_id)

    # ── Schedules (the old Schedules tab) ────────────────────────────

    def _build_schedules(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self._event_combo(bar, self._load_targets)
        ttk.Label(bar, text="View:").pack(side="left", padx=(10, 2))
        self.s_mode = tk.StringVar(value=self.state.get("schedule_mode", "Teacher"))
        mode = ttk.Combobox(bar, textvariable=self.s_mode, values=("Teacher", "Pupil"),
                            state="readonly", width=10)
        mode.pack(side="left", padx=2)
        mode.bind("<<ComboboxSelected>>", lambda _e: self._load_targets())
        ttk.Label(bar, text="Pick:").pack(side="left", padx=(10, 2))
        self.s_target = tk.StringVar()
        self.s_cb = ttk.Combobox(bar, textvariable=self.s_target, state="readonly", width=36)
        self.s_cb.pack(side="left", padx=2)
        self._button(bar, "Load", self.refresh_schedule)
        self._button(bar, "Refresh", self._load_targets)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 4))
        self._button(bar2, "My schedule", self.my_schedule, bool(self.me))
        self._button(bar2, "Print / save…", self.print_schedule)
        self._button(bar2, "Export CSV…", self.export_schedule)
        self._button(bar2, "E-mail this family", self.email_family)
        self.s_tree = _tree(tab, [("slot", "Slot", 70), ("with_id", "With id", 90),
                                  ("with_name", "With name", 220), ("parent", "Parent", 160),
                                  ("status", "Status", 100), ("notes", "Notes", 300)])
        self._targets: dict[str, Any] = {}
        self._load_targets()

    def _load_targets(self) -> None:
        if not hasattr(self, "s_cb"):
            return
        self.state["schedule_mode"] = self.s_mode.get()
        eid = self.state.get("event")
        self._targets = {}
        if eid and PE.find_event(eid):
            if self.s_mode.get() == "Teacher":
                self._targets = {t.teacher_name: t.teacher_key
                                 for t in PE.list_teachers(eid)}
            else:
                seen: dict[int, str] = {}
                for b in PE.list_bookings(event_id=eid, include_cancelled=False):
                    seen.setdefault(b.pupil_id, f"{b.pupil_name} ({b.admission_no})")
                self._targets = {v: k for k, v in sorted(seen.items(), key=lambda x: x[1])}
        self.s_cb.configure(values=list(self._targets))
        if self.s_target.get() not in self._targets:
            mine = next((k for k, v in self._targets.items() if v == self.me), None)
            self.s_target.set(mine or (next(iter(self._targets)) if self._targets else ""))
        self.refresh_schedule()

    def refresh_schedule(self) -> None:
        if not hasattr(self, "s_tree"):
            return
        self.s_tree.delete(*self.s_tree.get_children())
        eid, target = self.state.get("event"), self._targets.get(self.s_target.get())
        if not eid or target is None:
            return
        if self.s_mode.get() == "Teacher":
            for i, x in enumerate(PE.teacher_schedule(eid, target)):
                b = x["booking"]
                if b:
                    self.s_tree.insert("", "end", iid=f"s{i}", values=(
                        x["slot"], b.admission_no, b.pupil_name, b.parent_name or "", b.status,
                        b.teacher_notes or b.notes or ""))
                else:
                    kind = "BREAK" if x["kind"] == "break" else "FREE"
                    self.s_tree.insert("", "end", iid=f"s{i}", tags=(kind,),
                                       values=(x["slot"], "", kind.lower(), "", "", ""))
        else:
            for b in PE.family_schedule(eid, target):
                self.s_tree.insert("", "end", values=(
                    b.slot_time, b.teacher_key if not b.teacher_key.startswith("name:") else "",
                    f"{b.teacher_name} - {b.pupil_name}", b.parent_name or "", b.status,
                    b.notes or ""))

    def my_schedule(self) -> None:
        self.s_mode.set("Teacher")
        self._load_targets()
        mine = next((k for k, v in self._targets.items() if v == self.me), None)
        if mine is None:
            self._info("My schedule", "You aren't taking part in this evening.")
            return
        self.s_target.set(mine)
        self.refresh_schedule()

    def print_schedule(self) -> None:
        eid, target = self.state.get("event"), self._targets.get(self.s_target.get())
        if not eid or target is None:
            self._info("Print", "Load a schedule first.")
            return
        if self.s_mode.get() == "Teacher":
            text = PE.teacher_schedule_text(eid, target)
        else:
            e = PE.get_event(eid)
            text = "\n".join([f"{e.name} - {e.event_date} ({e.venue})", ""] + [
                f"{b.slot_time}  {b.teacher_name}  ({b.pupil_name})"
                for b in PE.family_schedule(eid, target)])
        _text_window(self.parent, "Schedule", text, save_name="schedule.txt")

    def export_schedule(self) -> None:
        eid = self.state.get("event")
        if not eid:
            return
        target = self._targets.get(self.s_target.get()) if self.s_mode.get() == "Teacher" \
            else None
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="schedule.csv")
        if path:
            n = self._run("Export", lambda: PE.export_schedule_csv(
                eid, path, actor=self.principal, teacher_key=target))
            if n is not None:
                self._info("Export", f"Exported {n} row(s).")

    def email_family(self) -> None:
        eid = self.state.get("event")
        if self.s_mode.get() != "Pupil" or not eid or not self._targets.get(self.s_target.get()):
            self._info("E-mail this family", "Choose View: Pupil and pick a pupil first.")
            return
        res = self._run("E-mail this family", lambda: PE.email_schedules(
            eid, actor=self.principal, pupil_ids=[self._targets[self.s_target.get()]]))
        if res:
            self._deliver("E-mail this family", res, "schedule(s)")

    # ── Teachers ─────────────────────────────────────────────────────

    def _build_teachers(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self._event_combo(bar, self.refresh_teachers)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 4))
        self._button(bar2, "Edit slots / room…", self.edit_teacher)
        self._button(bar2, "Add teacher…", self.add_teacher, self.editor)
        self._button(bar2, "Remove", self.remove_teacher, self.editor)
        self._button(bar2, "Teachers from groups", self._sync_current, self.editor)
        self.t_tree = _tree(tab, [("name", "Teacher", 200), ("groups", "Groups", 220),
                                  ("room", "Room", 70), ("breaks", "Breaks", 140),
                                  ("avail", "Available", 80), ("booked", "Booked", 70),
                                  ("free", "Free", 60)])
        self.t_tree.bind("<Double-1>", lambda _e: self.edit_teacher())
        self.t_rows: dict[str, PE.Teacher] = {}

    def refresh_teachers(self) -> None:
        if not hasattr(self, "t_tree"):
            return
        self.t_tree.delete(*self.t_tree.get_children())
        self.t_rows = {}
        eid = self.state.get("event")
        if not eid or not PE.find_event(eid):
            return
        booked: dict[str, int] = {}
        for b in PE.list_bookings(event_id=eid, include_cancelled=False):
            booked[b.teacher_key] = booked.get(b.teacher_key, 0) + 1
        for i, t in enumerate(PE.list_teachers(eid)):
            self.t_rows[str(i)] = t
            self.t_tree.insert("", "end", iid=str(i),
                               tags=("muted",) if not t.available else (
                                   ("good",) if t.teacher_key == self.me else ()),
                               values=(t.teacher_name, t.groups or "(added)", t.room or "",
                                       ", ".join(t.break_list), "yes" if t.available else "no",
                                       booked.get(t.teacher_key, 0),
                                       len(PE.free_slots(eid, t.teacher_key))))

    def _teacher(self, title: str) -> PE.Teacher | None:
        sel = self.t_tree.selection()
        if not sel:
            self._info(title, "Select a teacher first.")
            return None
        return self.t_rows[sel[0]]

    def edit_teacher(self) -> None:
        t = self._teacher("Edit slots")
        if t is None:
            return

        def save(v):
            PE.update_teacher(t.event_id, t.teacher_key, v, actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"{t.teacher_name} - slots", [
            ("room", "Room", t.room or "", None),
            ("breaks", "My breaks (slot times)", t.breaks or "", None),
            ("available", "Taking part", t.available, "check"),
            ("notes", "Notes", t.notes or "", "text")], save,
            note="Slots: " + ", ".join(PE.event_slots(t.event_id)))

    def add_teacher(self) -> None:
        e = self._event("Add teacher")
        if e is None:
            return
        logins = {f"{s['display_name']} ({s['username']})": s["username"]
                  for s in PE.staff_choices()}

        def save(v):
            PE.add_teacher(e.event_id, actor=self.principal,
                           username=logins.get(v["login"]) or None, name=v["name"] or None,
                           room=v["room"] or None)
            self._refresh_all()
        _form(self.parent, "Add teacher", [
            ("login", "Staff login", "", ["", *logins]),
            ("name", "…or name (no login)", "", None), ("room", "Room", "", None)], save,
            note="For staff who don't teach the year (head of year, SENCO).")

    def remove_teacher(self) -> None:
        t = self._teacher("Remove")
        if t and messagebox.askyesno("Remove", f"Take {t.teacher_name} off this evening?",
                                     parent=self._top()):
            if self._run("Remove", lambda: PE.remove_teacher(t.event_id, t.teacher_key,
                                                             actor=self.principal)):
                self._refresh_all()

    def _sync_current(self) -> None:
        e = self._event("Teachers from groups")
        if e:
            r = self._run("Teachers from groups",
                          lambda: PE.sync_teachers(e.event_id, actor=self.principal))
            if r:
                self._refresh_all()

    # ── Rates ────────────────────────────────────────────────────────

    def _build_rates(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self._event_combo(bar, self.refresh_rates)
        ttk.Label(bar, text="By:").pack(side="left", padx=(8, 2))
        self.r_by = tk.StringVar(value=self.state.get("rates_by", "teacher"))
        cb = ttk.Combobox(bar, textvariable=self.r_by, values=("teacher", "form"),
                          state="readonly", width=8)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_rates())
        self._button(bar, "Not booked yet", self.not_booked)
        self.r_tree = _tree(tab, [("group", "Teacher / form", 220), ("pupils", "Pupils", 70),
                                  ("booked", "Booked", 70), ("rate", "Rate %", 70),
                                  ("appts", "Appointments", 100), ("att", "Attended", 80),
                                  ("miss", "Missed", 70)])

    def refresh_rates(self) -> None:
        if not hasattr(self, "r_tree"):
            return
        self.state["rates_by"] = self.r_by.get()
        self.r_tree.delete(*self.r_tree.get_children())
        eid = self.state.get("event")
        if not eid or not PE.find_event(eid):
            return
        for r in PE.booking_rates(eid, by=self.r_by.get()):
            tag = "bad" if r["rate"] < 50 else ("good" if r["rate"] >= 80 else "warn")
            self.r_tree.insert("", "end", tags=(tag,), values=(
                r["group"], r["pupils"], r["booked"], r["rate"], r["appointments"],
                r["attended"], r["missed"]))

    def not_booked(self) -> None:
        e = self._event("Not booked yet")
        if e:
            rows = PE.not_booked(e.event_id)
            _text_window(self.parent, "Not booked yet", "\n".join(
                [f"{len(rows)} pupil(s) in {e.year_label} with no appointment:", ""] +
                [f"{p.admission_no:<10} {p.display_name:<28} {p.form_group or ''}"
                 for p in rows]), save_name="not-booked.txt")

    # ── Summary (the old Summary tab) ────────────────────────────────

    def _build_summary(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self._button(bar, "Refresh", self.refresh_summary)
        self.text = tk.Text(tab, wrap="word", font=("TkFixedFont", 10), state="disabled")
        self.text.pack(fill="both", expand=True, pady=(4, 0))

    def refresh_summary(self) -> None:
        if not hasattr(self, "text"):
            return
        s = PE.summary()
        lines = ["Events", "------", f"  Total events     : {s.total_events}",
                 f"  Upcoming events  : {s.upcoming_events}",
                 f"  Open for booking : {s.open_for_booking}",
                 f"  Completed        : {s.completed}"]
        if s.next_event:
            e = s.next_event
            lines += ["", f"  Next: #{e.event_id}  {e.event_date} {e.times}  {e.name} "
                          f"({e.status})"]
        lines += ["", "Bookings", "--------", f"  Total : {s.total_bookings}", "",
                  "By event status", "---------------"]
        lines += [f"  {k:<22} : {s.by_event_status[k]}" for k in PE.EVENT_STATUSES
                  if s.by_event_status.get(k)]
        lines += ["", "By booking status", "-----------------"]
        lines += [f"  {k:<22} : {s.by_booking_status[k]}" for k in PE.BOOKING_STATUSES
                  if s.by_booking_status.get(k)]
        eid = self.state.get("event")
        if eid and PE.find_event(eid):
            es = PE.summarize_event(eid)
            lines += ["", f"Chosen evening: {es.event.name} ({es.event.event_date})",
                      "-" * 40, f"  Teachers        : {es.teachers}",
                      f"  Capacity        : {es.capacity} appointments",
                      f"  Booked          : {es.bookings} ({es.fill_rate}%)",
                      f"  Pupils booked   : {es.pupils_booked} of {es.pupils_in_year}"]
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


def draw_parents_evenings(parent: ttk.Frame, *, principal: Principal, state: dict,
                          open_pupil: Callable[[int], None] | None = None
                          ) -> ParentsEveningsPage:
    return ParentsEveningsPage(parent, principal=principal, state=state, open_pupil=open_pupil)
