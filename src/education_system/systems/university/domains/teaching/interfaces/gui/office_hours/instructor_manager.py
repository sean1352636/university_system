"""Staff-side office hours: weekly blocks (appointment slots or drop-in, in
person / online / either, booking rules), cancelling a single date, the
bookings with their meeting records, directory entries that are not yet
bookable, and reminders. Rules are ``university/application/teaching/office_hours``."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import logging

from education_system.systems.university.application.teaching import office_hours as rules
from education_system.systems.university.domains.teaching.interfaces.gui.office_hours._rules_ui import (  # noqa: E501
    PAD, call, fill, save_ics, selected, tree, username, where,
)

logger = logging.getLogger(__name__)

_FIELDS = (("day_of_week", "Day"), ("start_time", "Start (HH:MM)"), ("end_time", "End (HH:MM)"),
           ("location", "Location"), ("mode", "Mode"), ("online_url", "Meeting link"),
           ("slot_minutes", "Appointment length (min, blank = drop-in)"),
           ("capacity", "Drop-in capacity"), ("module_code", "For module (optional)"),
           ("min_notice_hours", "Book at least (hours ahead)"),
           ("cancel_cutoff_hours", "Students may cancel up to (hours before)"),
           ("max_per_student_week", "Bookings per student per week"), ("notes", "Notes"))


class InstructorManager:
    """Manages the instructor view for office hours."""

    def __init__(self, parent, service, auth):
        self.parent = parent
        self.service = service
        self.auth = auth
        self.me, role = username(auth)
        self.is_admin = role == "admin"
        self._setup_ui()
        call(rules.send_reminders, write=True, parent=self.parent)
        self._refresh_hours()

    # ------------------------------------------------------------------ #
    #  UI setup
    # ------------------------------------------------------------------ #

    def _setup_ui(self):
        main = ttk.Frame(self.parent, padding="10")
        main.pack(fill=tk.BOTH, expand=True)
        head = ttk.Frame(main)
        head.pack(fill=tk.X)
        ttk.Label(head, text=_t('gui.academics.office_hours.instructor_manager.labels.my_office_hours',
                                default="My Office Hours"),
                  font=("Arial", 11, "bold")).pack(side=tk.LEFT)
        self.whose = tk.StringVar(value=self.me)
        if self.is_admin:
            ttk.Label(head, text="   Staff member:").pack(side=tk.LEFT)
            ttk.Entry(head, textvariable=self.whose, width=14).pack(side=tk.LEFT, padx=4)
            ttk.Button(head, text="Show", command=self._refresh_hours).pack(side=tk.LEFT)
        self.hours_tree = tree(main, [("when", "When"), ("where", "Where"), ("how", "Appointments"),
                                      ("module", "Module"), ("rules", "Rules"),
                                      ("off", "Cancelled dates")],
                               [160, 170, 130, 80, 220, 140], height=5)
        bar = ttk.Frame(main)
        bar.pack(fill=tk.X, **PAD)
        for label, command in ((_t('gui.academics.office_hours.instructor_manager.buttons.create',
                                   default="Create"), self._create_hours),
                               (_t('gui.academics.office_hours.instructor_manager.buttons.edit',
                                   default="Edit"), self._edit_hours),
                               (_t('gui.academics.office_hours.instructor_manager.buttons.delete',
                                   default="Delete"), self._delete_hours),
                               ("Cancel one date…", self._cancel_date),
                               ("Reinstate a date…", self._reinstate_date),
                               (_t('gui.academics.office_hours.instructor_manager.buttons.refresh',
                                   default="Refresh"), self._refresh_hours)):
            ttk.Button(bar, text=label, command=command).pack(side=tk.LEFT, padx=2)
        self.directory_var = tk.StringVar()
        ttk.Label(main, textvariable=self.directory_var, foreground="#b9770e").pack(anchor="w")
        ttk.Label(main, text=_t('gui.academics.office_hours.instructor_manager.labels.bookings_for_my_hours',
                                default="Bookings for My Hours"),
                  font=("Arial", 11, "bold")).pack(anchor="w", pady=(6, 0))
        self.bookings_tree = tree(main, [("date", "Date"), ("time", "Time"),
                                         ("student", "Student"), ("module", "Module"),
                                         ("topic", "To discuss"), ("status", "Status")],
                                  [95, 100, 90, 80, 300, 160], height=7)
        bar2 = ttk.Frame(main)
        bar2.pack(fill=tk.X, **PAD)
        ttk.Button(bar2, text="Record meeting…", command=self._record_meeting).pack(side=tk.LEFT)
        ttk.Button(bar2, text="Cancel booking…", command=self._cancel_booking).pack(
            side=tk.LEFT, padx=4)
        ttk.Button(bar2, text="Save to calendar (.ics)", command=self._export).pack(side=tk.LEFT)
        ttk.Button(bar2, text="Make a directory entry bookable…",
                   command=self._make_bookable).pack(side=tk.LEFT, padx=4)
        self.show_past = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar2, text="Include past (to record meetings)", variable=self.show_past,
                        command=self._refresh_bookings).pack(side=tk.RIGHT)

    # ------------------------------------------------------------------ #
    #  Data
    # ------------------------------------------------------------------ #

    def _get_instructor_id(self):
        return self.whose.get().strip() or self.me

    def _blocks_for(self, conn, who):
        rules.ensure(conn)
        rows = rules._dicts(conn.execute("SELECT id FROM office_hours WHERE instructor_id = ? "
                                         "AND is_active = 1 ORDER BY id", (who,)))
        return [dict(rules.block(conn, r["id"]), off=rules.exceptions(conn, r["id"]))
                for r in rows]

    def _refresh_hours(self):
        who = self._get_instructor_id()
        rows = call(self._blocks_for, who, parent=self.parent) or []
        self._blocks = {str(r["id"]): r for r in rows}
        fill(self.hours_tree, rows, lambda r: (
            f"{r['day_of_week']} {r['start_time']}–{r['end_time']}", where(r),
            f"{r['slot_minutes']}-min slots" if r["slot_minutes"] else f"drop-in ({r['capacity']})",
            r["module_code"] or "",
            f"{r['min_notice_hours']}h notice, cancel {r['cancel_cutoff_hours']}h before, "
            f"{r['max_per_student_week']}/week",
            ", ".join(e["exception_date"] for e in r["off"][-3:])), lambda r: r["id"])
        loose = call(rules.directory_only, who, parent=self.parent) or []
        self._loose = loose
        self.directory_var.set(
            f"{len(loose)} office-hours entr{'y' if len(loose) == 1 else 'ies'} in the staff "
            "directory cannot be booked yet — use 'Make a directory entry bookable'." if loose
            else "")
        self._refresh_bookings()

    def _refresh_bookings(self):
        rows = call(rules.bookings_for, instructor=self._get_instructor_id(),
                    include_past=self.show_past.get(), parent=self.parent) or []
        self._bookings = {str(r["id"]): r for r in rows}
        fill(self.bookings_tree, rows, lambda r: (
            r["booking_date"], f"{r['slot_start'] or r['start_time']}–{r['slot_end'] or r['end_time']}",
            r["student_id"], r["module_code"] or "", (r["notes"] or "")[:80],
            r["status"] + (f" · {r['attendance'].replace('_', ' ')}" if r["attendance"] else "")
            + (" · online" if r.get("mode") == "online" else "")), lambda r: r["id"])

    def _selected_block(self):
        block = self._blocks.get(selected(self.hours_tree) or "")
        if not block:
            messagebox.showwarning("Office hours", "Select office hours first.", parent=self.parent)
        return block

    # ------------------------------------------------------------------ #
    #  Create / edit / retire
    # ------------------------------------------------------------------ #

    def _locations(self):
        def load(conn):
            try:
                return [f"{r[0]} ({r[1]})" for r in conn.execute(
                    "SELECT building_name, building_code FROM buildings WHERE is_active = 1 "
                    "ORDER BY building_name")]
            except Exception:
                return []
        return call(load, parent=self.parent) or []

    def _block_dialog(self, existing=None):
        dialog = tk.Toplevel(self.parent)
        dialog.title("Edit office hours" if existing else "New office hours")
        dialog.transient(self.parent.winfo_toplevel())
        values = {}
        for row, (key, label) in enumerate(_FIELDS):
            ttk.Label(dialog, text=label + ":").grid(row=row, column=0, sticky="w", **PAD)
            current = "" if not existing or existing.get(key) is None else str(existing[key])
            if key in ("day_of_week", "mode", "location"):
                choices = {"day_of_week": rules.DAYS,
                           "mode": rules.schema.MODES, "location": self._locations()}[key]
                widget = ttk.Combobox(dialog, values=list(choices), width=32,
                                      state="readonly" if key != "location" else "normal")
                widget.set(current or ("in_person" if key == "mode" else
                                       "Monday" if key == "day_of_week" else ""))
                values[key] = widget
            else:
                var = tk.StringVar(value=current)
                ttk.Entry(dialog, textvariable=var, width=34).grid(row=row, column=1, **PAD)
                values[key] = var
                continue
            widget.grid(row=row, column=1, **PAD)

        def save():
            data = {k: w.get() for k, w in values.items()}
            data["instructor_id"] = existing["instructor_id"] if existing else self._get_instructor_id()
            saved = call(rules.save_block, data, existing["id"] if existing else None, self.me,
                         write=True, parent=dialog)
            if saved:
                dialog.destroy()
                self._refresh_hours()
        ttk.Button(dialog, text="Save", command=save).grid(row=len(_FIELDS), column=1,
                                                          sticky="w", **PAD)

    def _create_hours(self):
        self._block_dialog()

    def _edit_hours(self):
        block = self._selected_block()
        if block:
            self._block_dialog(block)

    def _delete_hours(self):
        block = self._selected_block()
        if block and messagebox.askyesno(
                "Delete office hours", "Stop these weekly office hours? Students booked on "
                "future dates are told their bookings are cancelled.", parent=self.parent):
            if call(rules.retire_block, block["id"], self.me, write=True, parent=self.parent):
                self._refresh_hours()

    def _cancel_date(self):
        block = self._selected_block()
        if not block:
            return
        upcoming = call(rules.dates, block["id"], 8, parent=self.parent) or []
        when = simpledialog.askstring("Cancel one date", "Date to cancel (YYYY-MM-DD):\n"
                                      f"Next: {', '.join(upcoming[:4])}", parent=self.parent,
                                      initialvalue=upcoming[0] if upcoming else "")
        reason = when and simpledialog.askstring("Cancel one date", "Reason (sent to the students):",
                                                 parent=self.parent)
        if reason:
            result = call(rules.cancel_date, block["id"], when, reason, self.me, write=True,
                          parent=self.parent)
            if result:
                messagebox.showinfo("Cancelled", f"{when} cancelled; {result['cancelled']} "
                                    "booked student(s) told.", parent=self.parent)
                self._refresh_hours()

    def _reinstate_date(self):
        block = self._selected_block()
        if not block or not block["off"]:
            return
        choice = simpledialog.askstring("Reinstate a date", "Which date? " + ", ".join(
            e["exception_date"] for e in block["off"]), parent=self.parent)
        match = next((e for e in block["off"] if e["exception_date"] == (choice or "").strip()), None)
        if match and call(rules.reinstate_date, match["id"], write=True, parent=self.parent):
            self._refresh_hours()

    # ------------------------------------------------------------------ #
    #  Bookings
    # ------------------------------------------------------------------ #

    def _selected_booking(self):
        bk = self._bookings.get(selected(self.bookings_tree) or "")
        if not bk:
            messagebox.showwarning("Office hours", "Select a booking first.", parent=self.parent)
        return bk

    def _record_meeting(self):
        bk = self._selected_booking()
        if not bk:
            return
        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Meeting with {bk['student_id']} on {bk['booking_date']}")
        dialog.transient(self.parent.winfo_toplevel())
        ttk.Label(dialog, text="Attendance:").grid(row=0, column=0, sticky="w", **PAD)
        attendance = ttk.Combobox(dialog, values=rules.schema.ATTENDANCE, width=14,
                                  state="readonly")
        attendance.set(bk["attendance"] or "attended")
        attendance.grid(row=0, column=1, sticky="w", **PAD)
        boxes = {}
        for row, (key, label) in enumerate((("meeting_notes", "Notes"),
                                            ("actions", "Agreed actions")), start=1):
            ttk.Label(dialog, text=label + ":").grid(row=row, column=0, sticky="nw", **PAD)
            box = tk.Text(dialog, width=48, height=5)
            box.insert("1.0", bk.get(key) or "")
            box.grid(row=row, column=1, **PAD)
            boxes[key] = box

        def save():
            if call(rules.record_meeting, bk["id"], attendance.get(),
                    boxes["meeting_notes"].get("1.0", "end-1c"),
                    boxes["actions"].get("1.0", "end-1c"), self.me, write=True, parent=dialog):
                dialog.destroy()
                self._refresh_bookings()
        ttk.Button(dialog, text="Save", command=save).grid(row=3, column=1, sticky="w", **PAD)

    def _cancel_booking(self):
        bk = self._selected_booking()
        reason = bk and simpledialog.askstring("Cancel booking", "Reason (sent to the student):",
                                               parent=self.parent)
        if reason and call(rules.cancel, bk["id"], self.me, staff=True, reason=reason,
                           write=True, parent=self.parent):
            self._refresh_bookings()

    def _export(self):
        rows = call(rules.bookings_for, instructor=self._get_instructor_id(),
                    parent=self.parent) or []
        save_ics(self.parent, rules.ical(rows), "office-hours-bookings.ics")

    def _make_bookable(self):
        if not self._loose:
            messagebox.showinfo("Directory", "Every directory entry is already bookable.",
                                parent=self.parent)
            return
        labels = [f"{e['hours_id']}: {e['day_of_week']} {e['start_time']}–{e['end_time']} "
                  f"{e['location'] or e['virtual_link'] or ''}" for e in self._loose]
        choice = simpledialog.askstring("Make bookable", "Which entry (number)?\n" +
                                        "\n".join(labels), parent=self.parent)
        slot = choice and simpledialog.askinteger(
            "Make bookable", "Appointment length in minutes (Cancel = drop-in):",
            parent=self.parent, minvalue=5)
        if choice and str(choice).strip().isdigit():
            made = call(rules.make_bookable, int(choice), 5, slot, self.me, write=True,
                        parent=self.parent)
            if made:
                self._refresh_hours()
