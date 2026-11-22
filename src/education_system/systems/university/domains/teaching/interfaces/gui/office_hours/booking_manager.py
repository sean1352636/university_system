"""Student-side office hours: find office hours (by default those of the
people teaching your modules), book a real date and appointment time, join
the waitlist when full, move or cancel a booking, and save bookings to a
calendar. Rules are ``university/application/teaching/office_hours``."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox
import logging

from education_system.systems.university.application.teaching import office_hours as rules
from education_system.systems.university.domains.teaching.interfaces.gui.office_hours._rules_ui import (  # noqa: E501
    PAD, call, fill, save_ics, selected, tree, username, where,
)

logger = logging.getLogger(__name__)


class BookingManager:
    """Manages the student booking view for office hours."""

    def __init__(self, parent, service, auth):
        self.parent = parent
        self.service = service
        self.auth = auth
        self.student_id, _role = username(auth)
        self._setup_ui()
        call(rules.send_reminders, write=True, parent=self.parent)
        self._refresh_available()

    # ------------------------------------------------------------------ #
    #  UI setup
    # ------------------------------------------------------------------ #

    def _setup_ui(self):
        main = ttk.Frame(self.parent, padding="10")
        main.pack(fill=tk.BOTH, expand=True)
        top = ttk.Frame(main)
        top.pack(fill=tk.X)
        ttk.Label(top, text=_t('gui.academics.office_hours.booking_manager.labels.available_office_hours',
                               default="Available Office Hours"),
                  font=("Arial", 11, "bold")).pack(side=tk.LEFT)
        self.mine_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Only staff who teach my modules", variable=self.mine_var,
                        command=self._refresh_available).pack(side=tk.LEFT, padx=12)
        self.avail_tree = tree(main, [("who", "Staff"), ("when", "When"), ("where", "Where"),
                                      ("how", "Appointments"), ("next", "Next date"),
                                      ("mods", "Teaches you")],
                               [110, 170, 160, 140, 100, 160], height=7)
        bar = ttk.Frame(main)
        bar.pack(fill=tk.X, **PAD)
        ttk.Button(bar, text=_t('gui.academics.office_hours.booking_manager.buttons.book_selected',
                                default="Book Selected"), command=self._book_selected).pack(
            side=tk.LEFT)
        ttk.Button(bar, text=_t('gui.academics.office_hours.booking_manager.buttons.refresh',
                                default="Refresh"), command=self._refresh_available).pack(
            side=tk.LEFT, padx=5)
        ttk.Label(main, text=_t('gui.academics.office_hours.booking_manager.labels.my_bookings',
                                default="My Bookings"),
                  font=("Arial", 11, "bold")).pack(anchor="w", pady=(8, 0))
        self.bookings_tree = tree(main, [("who", "Staff"), ("date", "Date"), ("time", "Time"),
                                         ("where", "Where"), ("module", "Module"),
                                         ("status", "Status")],
                                  [110, 100, 110, 220, 90, 160], height=5)
        bar2 = ttk.Frame(main)
        bar2.pack(fill=tk.X, **PAD)
        ttk.Button(bar2, text=_t('gui.academics.office_hours.booking_manager.buttons.cancel_selected',
                                 default="Cancel Selected"), command=self._cancel_selected).pack(
            side=tk.LEFT)
        ttk.Button(bar2, text="Move to another date…", command=self._reschedule_selected).pack(
            side=tk.LEFT, padx=5)
        ttk.Button(bar2, text="Save to my calendar (.ics)", command=self._export).pack(
            side=tk.LEFT)
        self.show_past = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar2, text="Show past", variable=self.show_past,
                        command=self._refresh_bookings).pack(side=tk.RIGHT)
        self._refresh_bookings()

    # ------------------------------------------------------------------ #
    #  Data
    # ------------------------------------------------------------------ #

    def _get_student_id(self):
        return self.student_id

    def _refresh_available(self):
        rows = call(rules.available, student_id=self.student_id,
                    mine_only=self.mine_var.get(), parent=self.parent) or []
        self._blocks = {str(r["id"]): r for r in rows}
        fill(self.avail_tree, rows, lambda r: (
            r["instructor_id"], f"{r['day_of_week']} {r['start_time']}–{r['end_time']}", where(r),
            f"{r['slot_minutes']}-minute slots" if r["slot_minutes"] else f"drop-in ({r['capacity']})",
            r["next_date"] or "none soon", ", ".join(r["my_modules"])), lambda r: r["id"])

    def _refresh_bookings(self):
        rows = call(rules.bookings_for, student_id=self.student_id,
                    include_past=self.show_past.get(), parent=self.parent) or []
        self._bookings = {str(r["id"]): r for r in rows}
        fill(self.bookings_tree, rows, lambda r: (
            r["instructor_id"], r["booking_date"],
            f"{r['slot_start'] or r['start_time']}–{r['slot_end'] or r['end_time']}",
            r["online_url"] if r.get("mode") == "online" else where(r), r["module_code"] or "",
            r["status"] + (f" · {r['attendance'].replace('_', ' ')}" if r["attendance"] else "")),
            lambda r: r["id"])

    # ------------------------------------------------------------------ #
    #  Booking dialog
    # ------------------------------------------------------------------ #

    def _date_and_slot(self, dialog, block, row0=0):
        """Date and appointment-time pickers; returns (date_var, slot_combo)."""
        ttk.Label(dialog, text="Date:").grid(row=row0, column=0, sticky="w", **PAD)
        date_combo = ttk.Combobox(dialog, values=call(rules.dates, block["id"], 8) or [],
                                  width=14, state="readonly")
        date_combo.grid(row=row0, column=1, sticky="w", **PAD)
        ttk.Label(dialog, text="Time:").grid(row=row0 + 1, column=0, sticky="w", **PAD)
        slot_combo = ttk.Combobox(dialog, width=24, state="readonly")
        slot_combo.grid(row=row0 + 1, column=1, sticky="w", **PAD)

        def load_slots(_e=None):
            rows = call(rules.slots, block["id"], date_combo.get(), parent=dialog) or []
            labels = [f"{s['start']}–{s['end']}" + ("" if s["free"] else " (taken)")
                      if block["slot_minutes"] else
                      f"{s['start']}–{s['end']} ({s.get('places_left', 0)} places left)"
                      for s in rows]
            slot_combo["values"] = labels
            free = [lbl for lbl, s in zip(labels, rows) if s["free"]]
            slot_combo.set(free[0] if free else (labels[0] if labels else ""))
        date_combo.bind("<<ComboboxSelected>>", load_slots)
        if date_combo["values"]:
            date_combo.set(date_combo["values"][0])
            load_slots()
        return date_combo, slot_combo

    def _book_selected(self):
        block = self._blocks.get(selected(self.avail_tree) or "")
        if not block:
            messagebox.showwarning("Office hours", "Select office hours first.", parent=self.parent)
            return
        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Book office hours with {block['instructor_id']}")
        dialog.transient(self.parent.winfo_toplevel())
        date_combo, slot_combo = self._date_and_slot(dialog, block)
        ttk.Label(dialog, text="About module:").grid(row=2, column=0, sticky="w", **PAD)
        modules = call(self._my_modules, parent=dialog) or []
        module_combo = ttk.Combobox(dialog, values=[""] + modules, width=14, state="readonly")
        module_combo.set(block["my_modules"][0] if block["my_modules"] else "")
        module_combo.grid(row=2, column=1, sticky="w", **PAD)
        mode_combo = None
        if block["mode"] == "either":
            ttk.Label(dialog, text="Meet:").grid(row=3, column=0, sticky="w", **PAD)
            mode_combo = ttk.Combobox(dialog, values=("in_person", "online"), width=14,
                                      state="readonly")
            mode_combo.set("in_person")
            mode_combo.grid(row=3, column=1, sticky="w", **PAD)
        ttk.Label(dialog, text="What would you like to discuss?").grid(row=4, column=0,
                                                                       sticky="nw", **PAD)
        notes = tk.Text(dialog, width=40, height=4)
        notes.grid(row=4, column=1, **PAD)

        def book():
            slot = slot_combo.get().split("–")[0] if slot_combo.get() else None
            args = (block["id"], self.student_id, date_combo.get())
            kwargs = dict(slot_start=slot if block["slot_minutes"] else None,
                          module_code=module_combo.get() or None,
                          notes=notes.get("1.0", "end-1c").strip(),
                          mode=mode_combo.get() if mode_combo else None)
            try:
                made = call(rules.book, *args, write=True, parent=dialog,
                            quiet_errors=(rules.FullError,), **kwargs)
            except rules.FullError as exc:
                if messagebox.askyesno("Full", f"{exc}\n\nJoin the waitlist for that date?",
                                       parent=dialog):
                    pos = call(rules.join_waitlist, block["id"], self.student_id,
                               date_combo.get(), kwargs["module_code"], kwargs["notes"],
                               write=True, parent=dialog)
                    if pos:
                        messagebox.showinfo("Waitlist", f"You are #{pos} on the waitlist; you "
                                            "will be booked in if a place comes free.",
                                            parent=dialog)
                        dialog.destroy()
                return
            if made:
                messagebox.showinfo("Booked", f"Booked: {made['when']}.", parent=dialog)
                dialog.destroy()
                self._refresh_bookings()
                self._refresh_available()

        buttons = ttk.Frame(dialog)
        buttons.grid(row=5, column=0, columnspan=2, sticky="w", **PAD)
        ttk.Button(buttons, text="Book", command=book).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=6)

    def _my_modules(self, conn):
        return [r[0] for r in conn.execute(
            "SELECT module_code FROM student_modules WHERE student_id = ? AND "
            "LOWER(COALESCE(status, '')) = 'enrolled' ORDER BY module_code", (self.student_id,))]

    # ------------------------------------------------------------------ #
    #  Cancel / move / export
    # ------------------------------------------------------------------ #

    def _cancel_selected(self):
        bk = self._bookings.get(selected(self.bookings_tree) or "")
        if not bk or bk["status"] != "confirmed":
            messagebox.showwarning("Office hours", "Select an active booking.", parent=self.parent)
            return
        if messagebox.askyesno("Cancel booking", f"Cancel your booking on {bk['booking_date']}?",
                               parent=self.parent):
            if call(rules.cancel, bk["id"], self.student_id, write=True, parent=self.parent):
                self._refresh_bookings()

    def _reschedule_selected(self):
        bk = self._bookings.get(selected(self.bookings_tree) or "")
        if not bk or bk["status"] != "confirmed":
            messagebox.showwarning("Office hours", "Select an active booking.", parent=self.parent)
            return
        block = call(rules.block, bk["office_hour_id"], parent=self.parent)
        if not block:
            return
        dialog = tk.Toplevel(self.parent)
        dialog.title("Move booking")
        dialog.transient(self.parent.winfo_toplevel())
        date_combo, slot_combo = self._date_and_slot(dialog, block)

        def move():
            slot = slot_combo.get().split("–")[0] if slot_combo.get() else None
            made = call(rules.reschedule, bk["id"], self.student_id, date_combo.get(),
                        slot_start=slot if block["slot_minutes"] else None, write=True,
                        parent=dialog)
            if made:
                messagebox.showinfo("Moved", f"Now: {made['when']}.", parent=dialog)
                dialog.destroy()
                self._refresh_bookings()
        ttk.Button(dialog, text="Move", command=move).grid(row=2, column=1, sticky="w", **PAD)

    def _export(self):
        rows = call(rules.bookings_for, student_id=self.student_id, parent=self.parent) or []
        save_ics(self.parent, rules.ical(rows), "my-office-hours.ics")

    # Kept for older callers.
    _cancel_booking = _cancel_selected
