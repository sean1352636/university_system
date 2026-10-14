"""Lesson Plans tab — the former Lesson Planner, over the real timetable.

The standalone planner kept its own timetable in ``lesson_plans`` (free-text
day/time/room, no term, invisible to conflict detection). This tab replaces it:
the slots listed here are the actual ``module_schedule`` rows that Module
Scheduling and Timetable Management already work with, and a lesson attaches
content — title, delivery type, notes — to one of them.

The planner's cross-system actions come with it and now work for *any*
scheduled slot, not only lessons someone typed into the planner: reserving a
room or equipment through facilities, seeding an attendance session, and
checking planned contact hours against the approved curriculum descriptor.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import logging
import tkinter as tk
from tkinter import ttk
from education_system.systems.university.domains.academics.interfaces.gui.module_scheduling._dialogs import messagebox

from education_system.systems.university.domains.academics.domain.services.module_scheduling.lesson_plans import (
    LESSON_TYPES,
    delete_lesson,
    save_lesson,
    scheduled_slots,
    unscheduled_lessons,
)
from education_system.systems.university.domains.academics.interfaces.gui.module_scheduling.main_gui import (
    ModuleSchedulingGUI,
)

logger = logging.getLogger(__name__)


def create_lesson_plans_tab(self):
    """Create the lesson planning tab."""
    frame = ttk.Frame(self.notebook)
    self.notebook.add(frame, text=_t("scheduling.tabs.lesson_plans",
                                     default="Lesson Plans"))

    controls = ttk.Frame(frame)
    controls.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(controls, text=_t("common.refresh"),
               command=self.refresh_lesson_plans).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls, text=_t("scheduling.buttons.reserve_room",
                                 default="Reserve Room"),
               command=self.lesson_reserve_room).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls, text=_t("scheduling.buttons.attendance_session",
                                 default="Create Attendance Session"),
               command=self.lesson_create_attendance_session).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls, text=_t("scheduling.buttons.check_hours",
                                 default="Check Contact Hours"),
               command=self.lesson_validate_hours).pack(side=tk.LEFT, padx=5)

    filter_frame = ttk.Frame(controls)
    filter_frame.pack(side=tk.RIGHT, padx=5)
    ttk.Label(filter_frame, text=_t("scheduling.labels.semester",
                                    default="Semester") + ":").pack(side=tk.LEFT)
    self.lesson_semester_var = tk.StringVar(value="All")
    self.lesson_semester_combo = ttk.Combobox(
        filter_frame, textvariable=self.lesson_semester_var, width=12,
        state="readonly", values=("All",))
    self.lesson_semester_combo.pack(side=tk.LEFT, padx=5)
    self.lesson_semester_combo.bind(
        "<<ComboboxSelected>>", lambda _e: self.refresh_lesson_plans())

    # Slots on the left, the lesson for the selected slot on the right.
    body = ttk.PanedWindow(frame, orient=tk.HORIZONTAL)
    body.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    left = ttk.Frame(body)
    body.add(left, weight=3)

    columns = ("Module", "Day", "Time", "Type", "Room", "Instructor",
               "Status", "Lesson")
    self.lesson_tree = ttk.Treeview(left, columns=columns, show="headings",
                                    style='Data.Treeview')
    widths = {"Module": 90, "Day": 85, "Time": 105, "Type": 80, "Room": 110,
              "Instructor": 130, "Status": 75, "Lesson": 190}
    for col in columns:
        self.lesson_tree.heading(col, text=col)
        self.lesson_tree.column(col, width=widths[col])
    scroll = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.lesson_tree.yview)
    self.lesson_tree.configure(yscrollcommand=scroll.set)
    self.lesson_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    self.lesson_tree.bind("<<TreeviewSelect>>", self.on_lesson_slot_select)

    right = ttk.LabelFrame(body, text=_t("scheduling.labels.lesson_detail",
                                         default="Lesson"), padding=10)
    body.add(right, weight=2)

    ttk.Label(right, text=_t("scheduling.labels.title", default="Title:")).grid(
        row=0, column=0, sticky=tk.W, pady=3)
    self.lesson_title_var = tk.StringVar()
    ttk.Entry(right, textvariable=self.lesson_title_var, width=32).grid(
        row=0, column=1, sticky=tk.EW, pady=3)

    ttk.Label(right, text=_t("scheduling.labels.type", default="Type:")).grid(
        row=1, column=0, sticky=tk.W, pady=3)
    self.lesson_type_var = tk.StringVar()
    ttk.Combobox(right, textvariable=self.lesson_type_var, values=list(LESSON_TYPES),
                 state="readonly", width=30).grid(row=1, column=1, sticky=tk.EW, pady=3)

    ttk.Label(right, text=_t("scheduling.labels.notes", default="Notes:")).grid(
        row=2, column=0, sticky=tk.NW, pady=3)
    self.lesson_notes_text = tk.Text(right, width=32, height=10, wrap=tk.WORD)
    self.lesson_notes_text.grid(row=2, column=1, sticky=tk.NSEW, pady=3)

    buttons = ttk.Frame(right)
    buttons.grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=(8, 0))
    ttk.Button(buttons, text=_t("common.save"),
               command=self.save_lesson_plan).pack(side=tk.LEFT, padx=3)
    ttk.Button(buttons, text=_t("common.delete"),
               command=self.delete_lesson_plan).pack(side=tk.LEFT, padx=3)
    ttk.Button(buttons, text=_t("common.clear", default="Clear"),
               command=self.clear_lesson_form).pack(side=tk.LEFT, padx=3)

    right.columnconfigure(1, weight=1)
    right.rowconfigure(2, weight=1)

    self.lesson_slot_hint = ttk.Label(right, text="", foreground="#555555",
                                      wraplength=260, justify=tk.LEFT)
    self.lesson_slot_hint.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(8, 0))

    self._lesson_rows = {}
    self.refresh_lesson_plans()


def refresh_lesson_plans(self):
    """Reload the slot list from module_schedule.

    The selected row is restored afterwards: rebuilding the tree clears the
    selection, and without this a save (which refreshes) left the form
    pointing at nothing, so an immediate second save silently did nothing.
    """
    if not hasattr(self, "lesson_tree"):
        return
    previous = self.lesson_tree.selection()
    previous_iid = previous[0] if previous else None
    for item in self.lesson_tree.get_children():
        self.lesson_tree.delete(item)

    semester = getattr(self, "lesson_semester_var", None)
    chosen = semester.get() if semester else "All"
    slots = scheduled_slots(semester=None if chosen in ("", "All") else chosen)

    # Keep the semester filter's options in step with the data.
    if hasattr(self, "lesson_semester_combo"):
        options = ["All"] + sorted({str(s.get("semester") or "") for s in
                                    scheduled_slots() if s.get("semester")})
        self.lesson_semester_combo["values"] = options

    self._lesson_rows = {}
    for slot in slots:
        iid = f"slot:{slot['schedule_id']}"
        self._lesson_rows[iid] = slot
        self.lesson_tree.insert(
            "", tk.END, iid=iid,
            values=(slot.get("module_code") or "",
                    slot.get("day_of_week") or "",
                    f"{slot.get('start_time') or ''}–{slot.get('end_time') or ''}",
                    slot.get("session_type") or "",
                    slot.get("room") or "—",
                    slot.get("instructor") or "—",
                    slot.get("status") or "",
                    slot.get("title") or ""))

    # Lessons whose module no longer exists cannot hold a slot; show them
    # rather than let them disappear.
    for lesson in unscheduled_lessons():
        iid = f"lesson:{lesson['lesson_id']}"
        self._lesson_rows[iid] = lesson
        self.lesson_tree.insert(
            "", tk.END, iid=iid,
            values=(lesson.get("module_code") or "?", "—",
                    lesson.get("legacy_slot") or "—",
                    lesson.get("lesson_type") or "", "—", "—",
                    _t("scheduling.values.unscheduled", default="unscheduled"),
                    lesson.get("title") or ""),
            tags=("unscheduled",))
    self.lesson_tree.tag_configure("unscheduled", foreground="#a05000")

    if previous_iid and previous_iid in self._lesson_rows:
        self.lesson_tree.selection_set(previous_iid)
        self.lesson_tree.see(previous_iid)

    if hasattr(self, "update_status"):
        try:
            self.update_status(f"{len(slots)} scheduled slot(s)")
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)


def on_lesson_slot_select(self, _event=None):
    """Load the selected slot's lesson into the form."""
    entry = _selected(self)
    if not entry:
        return
    self.lesson_title_var.set(entry.get("title") or "")
    self.lesson_type_var.set(entry.get("lesson_type")
                             or entry.get("session_type") or "")
    self.lesson_notes_text.delete("1.0", tk.END)
    if entry.get("notes"):
        self.lesson_notes_text.insert("1.0", entry["notes"])

    if entry.get("schedule_id"):
        self.lesson_slot_hint.config(text=_t(
            "scheduling.labels.lesson_slot_hint",
            default="Times, room and instructor come from the schedule slot — "
                    "change them on the Schedules tab."))
    else:
        self.lesson_slot_hint.config(text=_t(
            "scheduling.labels.lesson_unscheduled_hint",
            default="This lesson has no slot: its module is not in the "
                    "catalogue. Create the module and a schedule slot, then "
                    "re-save the lesson against it."))


def save_lesson_plan(self):
    """Write the form back to the selected slot."""
    entry = _selected(self)
    if not entry:
        messagebox.showinfo(_t("common.info", default="Info"),
                            _t("scheduling.dialogs.select_a_slot",
                               default="Select a scheduled slot first."),
                            parent=self.root)
        return
    title = self.lesson_title_var.get().strip()
    if not title:
        messagebox.showwarning(_t("common.error"),
                               _t("scheduling.dialogs.lesson_needs_title",
                                  default="Give the lesson a title."),
                               parent=self.root)
        return

    lesson_id = save_lesson(
        entry.get("schedule_id"),
        title=title,
        lesson_type=self.lesson_type_var.get().strip(),
        notes=self.lesson_notes_text.get("1.0", tk.END).strip(),
        module_code=entry.get("module_code"),
        lesson_id=entry.get("lesson_id"),
        updated_by=_current_user(self),
    )
    if lesson_id is None:
        messagebox.showerror(_t("common.error"),
                             _t("scheduling.dialogs.lesson_save_failed",
                                default="Could not save the lesson."),
                             parent=self.root)
        return
    self.refresh_lesson_plans()
    _publish_lesson_event(self, "updated", entry, title)


def delete_lesson_plan(self):
    """Remove the lesson content, leaving the slot in place."""
    entry = _selected(self)
    if not entry or not entry.get("lesson_id"):
        messagebox.showinfo(_t("common.info", default="Info"),
                            _t("scheduling.dialogs.no_lesson_here",
                               default="That slot has no lesson to delete."),
                            parent=self.root)
        return
    if not messagebox.askyesno(
            _t("common.confirm", default="Confirm"),
            _t("scheduling.dialogs.confirm_delete_lesson",
               default="Delete this lesson plan? The scheduled slot stays on "
                       "the timetable."),
            parent=self.root):
        return
    delete_lesson(entry["lesson_id"])
    self.clear_lesson_form()
    self.refresh_lesson_plans()


def clear_lesson_form(self):
    self.lesson_title_var.set("")
    self.lesson_type_var.set("")
    self.lesson_notes_text.delete("1.0", tk.END)


# ---------------------------------------------------------------------------
# Cross-system actions carried over from the planner
# ---------------------------------------------------------------------------

def _integrations(self):
    from education_system.systems.university.domains.academics.domain.course_planning.lesson_planner_integrations import (
        PlannerIntegrations,
    )
    user = getattr(self, "current_user", None) or getattr(self, "user", None)
    return PlannerIntegrations(user=user, user_display=_current_user(self) or "")


def _as_planner_lesson(entry: dict) -> dict:
    """Shape a slot like the dict PlannerIntegrations expects."""
    return {
        "course": entry.get("module_code") or "",
        "title": entry.get("title") or "",
        "instructor": entry.get("instructor") or "",
        "type": entry.get("lesson_type") or entry.get("session_type") or "",
        "day": entry.get("day_of_week") or "",
        "start": entry.get("start_time") or "",
        "end": entry.get("end_time") or "",
        "room": entry.get("room") or "",
        "notes": entry.get("notes") or "",
    }


def lesson_reserve_room(self):
    """Reserve a real room for the selected slot through facilities."""
    entry = _selected(self, require_slot=True)
    if not entry:
        return
    lesson = _as_planner_lesson(entry)
    try:
        integrations = _integrations(self)
        rooms = integrations.find_available_rooms(lesson)
    except Exception:
        logger.warning("room lookup failed", exc_info=True)
        rooms = []
    if not rooms:
        messagebox.showinfo(_t("common.info", default="Info"),
                            _t("scheduling.dialogs.no_rooms_free",
                               default="No rooms are free for that slot."),
                            parent=self.root)
        return
    _choose_room_dialog(self, lesson, rooms)


def _choose_room_dialog(self, lesson, rooms):
    dialog = tk.Toplevel(self.root)
    dialog.title(_t("scheduling.windows.reserve_room", default="Reserve Room"))
    dialog.transient(self.root)
    dialog.grab_set()

    listbox = tk.Listbox(dialog, width=52, height=min(12, max(3, len(rooms))))
    for room in rooms:
        label = room.get("name") or room.get("room_number") or room.get("id")
        capacity = room.get("capacity")
        listbox.insert(tk.END, f"{label}"
                               + (f"  (capacity {capacity})" if capacity else ""))
    listbox.pack(padx=12, pady=12, fill=tk.BOTH, expand=True)
    listbox.selection_set(0)

    def _do_reserve():
        selection = listbox.curselection()
        if not selection:
            return
        room = rooms[selection[0]]
        try:
            booking = _integrations(self).reserve_room(lesson, room.get("id"))
        except Exception:
            logger.warning("room reservation failed", exc_info=True)
            booking = None
        dialog.destroy()
        if booking:
            messagebox.showinfo(_t("common.success", default="Success"),
                                f"Room reserved (booking {booking}).",
                                parent=self.root)
        else:
            messagebox.showerror(_t("common.error"),
                                 _t("scheduling.dialogs.reserve_failed",
                                    default="The room could not be reserved."),
                                 parent=self.root)

    bar = ttk.Frame(dialog)
    bar.pack(fill=tk.X, padx=12, pady=(0, 12))
    ttk.Button(bar, text=_t("common.cancel"), command=dialog.destroy).pack(side=tk.RIGHT)
    ttk.Button(bar, text=_t("scheduling.buttons.reserve", default="Reserve"),
               command=_do_reserve).pack(side=tk.RIGHT, padx=6)


def lesson_create_attendance_session(self):
    """Seed an attendance session for the selected slot."""
    entry = _selected(self, require_slot=True)
    if not entry:
        return
    try:
        session = _integrations(self).create_attendance_session(
            _as_planner_lesson(entry))
    except Exception:
        logger.warning("attendance session creation failed", exc_info=True)
        session = None
    if session:
        messagebox.showinfo(_t("common.success", default="Success"),
                            _t("scheduling.dialogs.attendance_created",
                               default="Attendance session created."),
                            parent=self.root)
    else:
        messagebox.showerror(_t("common.error"),
                             _t("scheduling.dialogs.attendance_failed",
                                default="Could not create the attendance session."),
                             parent=self.root)


def lesson_validate_hours(self):
    """Compare the module's scheduled weekly hours with its descriptor."""
    entry = _selected(self, require_slot=True)
    if not entry:
        return
    module_code = entry.get("module_code")
    weekly = 0.0
    for slot in scheduled_slots(module_code=module_code):
        weekly += _slot_hours(slot)
    try:
        verdict = _integrations(self).validate_contact_hours(module_code, weekly)
    except Exception:
        logger.warning("contact hour validation failed", exc_info=True)
        verdict = None
    if not verdict:
        messagebox.showinfo(_t("common.info", default="Info"),
                            f"{module_code}: {weekly:g} scheduled hours per week. "
                            "No approved descriptor to compare against.",
                            parent=self.root)
        return
    messagebox.showinfo(
        _t("scheduling.windows.contact_hours", default="Contact Hours"),
        f"{module_code}: {weekly:g} scheduled hours per week.\n\n"
        f"{verdict.get('message') or verdict}",
        parent=self.root)


def _slot_hours(slot) -> float:
    def minutes(value):
        try:
            hours, mins = str(value).split(":")[:2]
            return int(hours) * 60 + int(mins)
        except (ValueError, AttributeError):
            return None
    start, end = minutes(slot.get("start_time")), minutes(slot.get("end_time"))
    if start is None or end is None or end <= start:
        return 0.0
    return (end - start) / 60.0


def _publish_lesson_event(self, action, entry, title):
    """Best-effort fan-out so attendance/exam consumers can react."""
    try:
        lesson = _as_planner_lesson(entry)
        lesson["title"] = title
        _integrations(self).publish_lesson_event(action, lesson)
    except Exception:
        logger.debug("lesson event publish skipped", exc_info=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _selected(self, require_slot: bool = False):
    selection = self.lesson_tree.selection() if hasattr(self, "lesson_tree") else ()
    if not selection:
        return None
    entry = getattr(self, "_lesson_rows", {}).get(selection[0])
    if entry is None:
        return None
    if require_slot and not entry.get("schedule_id"):
        messagebox.showinfo(_t("common.info", default="Info"),
                            _t("scheduling.dialogs.needs_a_slot",
                               default="That lesson has no scheduled slot yet."),
                            parent=self.root)
        return None
    return entry


def _current_user(self):
    user = getattr(self, "current_user", None) or getattr(self, "user", None)
    if isinstance(user, dict):
        return user.get("username") or user.get("display_name")
    return getattr(user, "username", None)


ModuleSchedulingGUI.create_lesson_plans_tab = create_lesson_plans_tab
ModuleSchedulingGUI.refresh_lesson_plans = refresh_lesson_plans
ModuleSchedulingGUI.on_lesson_slot_select = on_lesson_slot_select
ModuleSchedulingGUI.save_lesson_plan = save_lesson_plan
ModuleSchedulingGUI.delete_lesson_plan = delete_lesson_plan
ModuleSchedulingGUI.clear_lesson_form = clear_lesson_form
ModuleSchedulingGUI.lesson_reserve_room = lesson_reserve_room
ModuleSchedulingGUI.lesson_create_attendance_session = lesson_create_attendance_session
ModuleSchedulingGUI.lesson_validate_hours = lesson_validate_hours
