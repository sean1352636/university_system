"""GUI panels for Sixth Form Attendance.

Opens in its own window, with every section listed down a sidebar:

  * Take register — pick slot + date, fill in the roster, save once.
    Bulk marking, keyboard marking, arrival/departure stamps, copy
    forward, undo and submit-to-lock all live on this tab.
  * Records — flat directory with filters and per-record edit/delete.
  * Summary — per-student attendance % for a chosen group/date range.
  * Sessions / Bulk & range — the lifecycle tabs, built next door in
    :mod:`attendance_register_views`.
  * Codes & reasons / Authorisation / Audit — the statutory vocabulary,
    the absence-decision queue and the amendment trail, built in
    :mod:`attendance_codes_views`.
  * Expected & AM/PM — coverage against the timetable and the statutory
    session marks, built in :mod:`attendance_sessions_views`.

After those, the rest of the attendance package, one sidebar entry per
page under three headings (each page built only when first opened):

  * Absence & site — leave & absence (the one absence store), signing in
    and out of site, kiosk, offline capture, bulk import.
  * Study & interventions — supervised study / activities, punctuality,
    cases & contracts, CME alerts, register nudges.
  * Policy & returns — thresholds, the governor report, the census
    extract.
"""

from __future__ import annotations
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import ttk
from education_system.platform import branding
from education_system.platform.delivery.gui import window_sizing
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog
from typing import Any
from education_system.systems.sixth_form.domain.academics.attendance import attendance
from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance_register as register,
)
from education_system.systems.sixth_form.interfaces.gui.academics.attendance import (
    attendance_codes_views as codes_views,
    attendance_register_views as register_views,
    attendance_sessions_views as sessions_views,
)
from education_system.systems.sixth_form.domain.academics.class_groups import class_groups
from education_system.systems.sixth_form.domain.learners.students import students
from education_system.systems.sixth_form.domain.academics.attendance import attendance as data
from education_system.systems.sixth_form.domain.academics.class_groups import class_groups as cg_data
from education_system.systems.sixth_form.domain.academics.courses import courses as course_data
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.academics.timetable import timetable as tt_data
from education_system.systems.sixth_form.domain.academics.attendance.attendance import (
    DEFAULT_STATUS,
    STATUSES,
    AttendanceRecord,
    AttendanceSummary,
    ValidationError,
)
from education_system.systems.sixth_form.domain.academics.timetable.timetable import day_name

logger = logging.getLogger(__name__)

_GUI_PKG = "education_system.systems.sixth_form.interfaces.gui.academics.attendance"


def _builder(module: str, func: str):
    """A tab builder imported only when its tab is first opened."""
    def build(gui, parent) -> None:
        import importlib
        getattr(importlib.import_module(f"{_GUI_PKG}.{module}"), func)(
            gui, parent)
    return build


# The grouped tabs after the original nine: (tab title, [(page, builder)]).
# Each page is built the first time it is shown, so opening Attendance
# does not open every table in the package.
_GROUPED_TABS: list[tuple[str, list[tuple[str, Any]]]] = [
    ("Absence & site", [
        ("Leave & absence", _builder("attendance_absence_views",
                                     "build_leave_tab")),
        ("Sign in / out", _builder("attendance_absence_views",
                                   "build_signout_tab")),
        ("Kiosk", _builder("attendance_capture_views", "build_kiosk_tab")),
        ("Offline capture", _builder("attendance_capture_views",
                                     "build_offline_tab")),
        ("Import", _builder("attendance_capture_views", "build_import_tab")),
    ]),
    ("Study & interventions", [
        ("Study & activities", _builder("attendance_capture_views",
                                        "build_activities_tab")),
        ("Punctuality", _builder("attendance_capture_views",
                                 "build_punctuality_tab")),
        ("Cases & contracts", _builder("attendance_oversight_views",
                                       "build_escalation_tab")),
        ("CME alerts", _builder("attendance_oversight_views",
                                "build_safeguarding_tab")),
        ("Nudges", _builder("attendance_oversight_views",
                            "build_nudges_tab")),
        # Reserved: "Bursary holds" (attendance_bursary) is added here by
        # the finance work, as ("Bursary holds", _builder(<module>, <fn>)).
    ]),
    ("Policy & returns", [
        ("Thresholds", _builder("attendance_oversight_views",
                                "build_thresholds_tab")),
        ("Governor report", _builder("attendance_oversight_views",
                                     "build_governor_tab")),
        ("Census extract", _builder("attendance_oversight_views",
                                    "build_census_tab")),
    ]),
]


# Shown next to the bulk-mark buttons and in the draft banner.
_KEY_HINT = "  ".join(f"{k.upper()}={v}"
                      for k, v in register.STATUS_KEYS.items())


def _actor(gui) -> str | None:
    """Whoever is signed into the GUI, for the submitted-by stamp."""
    auth = getattr(gui, "auth", None)
    return ((getattr(auth, "current_user", None) or {}).get("username")
            if auth else None)


def _slot_label(slot, group=None, course=None) -> str:
    if group is None:
        group = cg_data.get_group(slot.group_id)
    if course is None and group is not None:
        course = course_data.get_course(group.course_id)
    code = course.course_code if course else f"#{slot.group_id}"
    gname = group.group_name if group else "?"
    return (f"#{slot.slot_id} {day_name(slot.day)} P{slot.period} "
            f"· {code} {gname}")


def _today() -> str:
    return _date.today().isoformat()


# ── Top-level window ───────────────────────────────────────────────

class _WindowGui:
    """The main GUI, seen from the Attendance window.

    The tab builders take ``gui`` and parent their dialogs and pop-ups on
    ``gui.root``. Here ``root`` is the Attendance window, so those open
    over it rather than behind it on the main window; everything else
    (auth, the signed-in user, ...) comes from the real GUI.
    """

    def __init__(self, gui, win: tk.Misc) -> None:
        self.__dict__["_gui"] = gui
        self.__dict__["root"] = win
        # Messages go to this window's own status bar.
        self.__dict__["status_var"] = tk.StringVar(win, value="Ready.")

    def __getattr__(self, name: str):
        return getattr(self.__dict__["_gui"], name)


# Sidebar headings for the register pages; the grouped pages take their
# group's title.
_CORE_SECTIONS = {
    "Take register": "Registers", "Records": "Registers",
    "Summary": "Registers", "Sessions": "Registers",
    "Expected & AM/PM": "Registers", "Bulk & range": "Registers",
    "Codes & reasons": "Codes & audit", "Authorisation": "Codes & audit",
    "Audit": "Codes & audit",
}

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_directory(gui) -> None:
    """Attendance in its own window, with its sections down a sidebar."""
    master = getattr(gui, "root", None)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Attendance — {branding.SYSTEM_NAME}")
    window_sizing.fit(win, WIN_GEOMETRY, WIN_MINSIZE)
    wgui = _WindowGui(gui, win)

    ttk.Label(win, textvariable=wgui.status_var, anchor="w",
              relief="sunken", padding=(6, 2)).pack(
        side="bottom", fill="x", padx=10, pady=(0, 6))
    nb = SidebarBook(win, title="Attendance")
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    take_tab = ttk.Frame(nb, padding=8)
    records_tab = ttk.Frame(nb, padding=8)
    summary_tab = ttk.Frame(nb, padding=8)
    sessions_tab = ttk.Frame(nb, padding=8)
    bulk_tab = ttk.Frame(nb, padding=8)
    codes_tab = ttk.Frame(nb, padding=8)
    authz_tab = ttk.Frame(nb, padding=8)
    audit_tab = ttk.Frame(nb, padding=8)
    expected_tab = ttk.Frame(nb, padding=8)
    for frame, text in ((take_tab, "Take register"),
                        (records_tab, "Records"),
                        (summary_tab, "Summary"),
                        (sessions_tab, "Sessions"),
                        (expected_tab, "Expected & AM/PM"),
                        (bulk_tab, "Bulk & range"),
                        (codes_tab, "Codes & reasons"),
                        (authz_tab, "Authorisation"),
                        (audit_tab, "Audit")):
        nb.add(frame, text=text, group=_CORE_SECTIONS[text])

    has_unsaved = _build_take_tab(wgui, take_tab)
    _build_records_tab(wgui, records_tab)
    _build_summary_tab(wgui, summary_tab)
    register_views.build_sessions_tab(wgui, sessions_tab)
    register_views.build_bulk_tab(wgui, bulk_tab)
    codes_views.build_codes_tab(wgui, codes_tab)
    codes_views.build_authorisation_tab(wgui, authz_tab)
    codes_views.build_audit_tab(wgui, audit_tab)
    sessions_views.build_sessions_tab(wgui, expected_tab)

    # The rest of the package, one sidebar entry per page under its
    # group. Each page is built the first time it is shown, so opening
    # Attendance does not open every table in the package.
    def _lazy(frame: ttk.Frame, build):
        state = {"built": False}

        def show() -> None:
            if state["built"]:
                return
            state["built"] = True
            try:
                build(wgui, frame)
            except Exception as e:          # pragma: no cover - UI guard
                logger.exception("Attendance page failed to build")
                ttk.Label(frame, text=f"This page could not be opened: {e}",
                          foreground="#a33").pack(anchor="w")
        return show

    for group, pages in _GROUPED_TABS:
        for title, build in pages:
            frame = ttk.Frame(nb, padding=8)
            nb.add(frame, text=title, group=group,
                   on_show=_lazy(frame, build))

    # Leaving the register with marks that were never saved is the
    # easiest way to lose a period's attendance, so make it deliberate.
    def _guard_tab_change(_event=None) -> None:
        if nb.select() == str(take_tab) or not has_unsaved():
            return
        if messagebox.askyesno(
                "Unsaved marks",
                "This register has marks that have not been saved.\n\n"
                "Leave the register and discard them?",
                default="no", parent=win):
            return
        nb.select(take_tab)

    nb.bind("<<NotebookTabChanged>>", _guard_tab_change)

    def _on_close() -> None:
        if has_unsaved() and not messagebox.askyesno(
                "Unsaved marks",
                "This register has marks that have not been saved.\n\n"
                "Close Attendance and discard them?",
                default="no", parent=win):
            return
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", _on_close)


# ─── Take register tab ──────────────────────────────────────────────

def _build_take_tab(gui, parent: ttk.Frame):
    """Build the register tab. Returns a ``has_unsaved()`` predicate."""
    slots = tt_data.list_slots()
    groups = {g.group_id: g for g in cg_data.list_groups()}
    courses = {c.course_id: c for c in course_data.list_courses()}
    slot_labels = [
        _slot_label(s, groups.get(s.group_id), courses.get(
            groups[s.group_id].course_id if s.group_id in groups else 0))
        for s in slots
    ]
    slot_by_label = {lbl: s.slot_id for lbl, s in zip(slot_labels, slots)}

    if not slots:
        ttk.Label(
            parent,
            text="No timetable slots yet — create a slot before taking registers.",
            foreground="#a33",
        ).pack(anchor="w")
        return lambda: False

    # ── Selector bar ──
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))

    slot_var = tk.StringVar(value=slot_labels[0])
    date_var = tk.StringVar(value=_today())

    ttk.Label(bar, text="Slot:").pack(side="left")
    ttk.Combobox(bar, textvariable=slot_var, values=slot_labels,
                 state="readonly", width=58).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Date (YYYY-MM-DD):").pack(side="left")
    ttk.Entry(bar, textvariable=date_var, width=14).pack(
        side="left", padx=(4, 12))

    banner = ttk.Label(parent, text="", foreground="#555")
    banner.pack(anchor="w", pady=(0, 4))

    register_holder = ttk.Frame(parent)
    register_holder.pack(fill="both", expand=True, pady=(0, 8))

    # Row widgets keyed by student_id, kept in scope so submit() can read them.
    row_state: dict[str, dict[str, Any]] = {}
    row_order: list[str] = []
    # What was on screen the moment the register finished loading. Every
    # unsaved-change question is answered by comparing against this
    # rather than by trying to notice each keystroke.
    baseline: dict[str, str] = {"digest": ""}
    locked: dict[str, bool] = {"value": False}

    def _slot_id() -> int | None:
        return slot_by_label.get(slot_var.get())

    def _payload() -> dict[str, dict[str, Any]]:
        return {
            sid_s: {
                "status":       vs["status"].get(),
                "minutes_late": vs["minutes_late"].get(),
                "notes":        vs["notes"].get(),
            }
            for sid_s, vs in row_state.items()
        }

    def has_unsaved() -> bool:
        if not row_state or locked["value"]:
            return False
        return register.payload_digest(_payload()) != baseline["digest"]

    def _confirm_discard() -> bool:
        """True if it's safe to blow away what's on screen."""
        if not has_unsaved():
            return True
        return messagebox.askyesno(
            "Unsaved marks",
            "This register has marks that have not been saved.\n\n"
            "Reload and discard them?",
            default="no", parent=gui.root)

    def _selected_ids() -> list[str]:
        return [sid_s for sid_s in row_order
                if row_state[sid_s]["selected"].get()]

    def _apply_status(status: str, *, selected_only: bool) -> None:
        targets = _selected_ids() if selected_only else row_order
        if selected_only and not targets:
            messagebox.showinfo(
                "Nothing selected",
                "Tick the students you want to mark, or untick "
                "'selected only' to mark the whole register.",
                parent=gui.root)
            return
        for sid_s in targets:
            row_state[sid_s]["status"].set(status)
            if status != "Late":
                row_state[sid_s]["minutes_late"].set("")

    def load(*, force: bool = False) -> None:
        nonlocal row_state, row_order
        if not force and not _confirm_discard():
            return
        for w in register_holder.winfo_children():
            w.destroy()
        row_state = {}
        row_order = []
        locked["value"] = False
        baseline["digest"] = ""

        sid = _slot_id()
        if sid is None:
            banner.configure(text="")
            ttk.Label(register_holder, text="Pick a slot.",
                      foreground="#a33").pack(anchor="w")
            return
        try:
            entries = data.register_view(sid, date_var.get())
            session = register.get_session(sid, date_var.get())
        except ValidationError as e:
            banner.configure(text="")
            ttk.Label(register_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("register_view failed")
            banner.configure(text="")
            ttk.Label(register_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        if not entries:
            banner.configure(text="")
            ttk.Label(
                register_holder,
                text="This slot's class group has no members yet.",
                foreground="#a33",
            ).pack(anchor="w")
            return

        locked["value"] = bool(session is not None and session.is_submitted)
        if session is not None and session.is_submitted:
            banner.configure(
                text=(f"🔒 Submitted {session.submitted_at} by "
                      f"{session.submitted_by or '?'} — reopen to edit."),
                foreground="#a33")
        else:
            marked = sum(1 for entry in entries if entry.record is not None)
            banner.configure(
                text=(f"Draft — {marked}/{len(entries)} marked. "
                      f"Keys: {_KEY_HINT}"),
                foreground="#555")
        field_state = "disabled" if locked["value"] else "normal"
        combo_state = "disabled" if locked["value"] else "readonly"

        # Header row
        header = ttk.Frame(register_holder)
        header.pack(fill="x")
        ttk.Label(header, text="", width=3).pack(side="left", padx=2)
        for _col, text, width in [
            ("id",      "Student ID",   12),
            ("name",    "Name",         26),
            ("status",  "Status",       18),
            ("late",    "Mins late",     8),
            ("in",      "In",            6),
            ("out",     "Out",           6),
            ("notes",   "Notes",        26),
        ]:
            ttk.Label(header, text=text, font=("", 10, "bold"),
                      width=width, anchor="w").pack(side="left", padx=2)

        for entry in entries:
            row = ttk.Frame(register_holder)
            row.pack(fill="x", pady=1)

            selected_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(row, variable=selected_var, width=2,
                            state=field_state).pack(side="left", padx=2)
            ttk.Label(row, text=entry.student_id, width=12, anchor="w"
                      ).pack(side="left", padx=2)
            ttk.Label(row, text=entry.full_name, width=26, anchor="w"
                      ).pack(side="left", padx=2)

            status_var = tk.StringVar(
                value=entry.record.status if entry.record else DEFAULT_STATUS)
            late_var = tk.StringVar(
                value=str(entry.record.minutes_late)
                if (entry.record and entry.record.minutes_late is not None) else "")
            in_var = tk.StringVar(
                value=(entry.record.arrival_time or "") if entry.record else "")
            out_var = tk.StringVar(
                value=(entry.record.departure_time or "") if entry.record else "")
            notes_var = tk.StringVar(
                value=(entry.record.notes or "") if entry.record else "")

            combo = ttk.Combobox(row, textvariable=status_var,
                                 values=list(STATUSES),
                                 state=combo_state, width=16)
            combo.pack(side="left", padx=2)
            ttk.Entry(row, textvariable=late_var, width=8, state=field_state
                      ).pack(side="left", padx=2)
            ttk.Entry(row, textvariable=in_var, width=6, state=field_state
                      ).pack(side="left", padx=2)
            ttk.Entry(row, textvariable=out_var, width=6, state=field_state
                      ).pack(side="left", padx=2)
            ttk.Entry(row, textvariable=notes_var, width=26, state=field_state
                      ).pack(side="left", padx=2)

            row_state[entry.student_id] = {
                "status": status_var,
                "minutes_late": late_var,
                "notes": notes_var,
                "arrival": in_var,
                "departure": out_var,
                "was_arrival": (entry.record.arrival_time if entry.record else None),
                "was_departure": (entry.record.departure_time if entry.record else None),
                "selected": selected_var,
                "combo": combo,
            }
            row_order.append(entry.student_id)
            if not locked["value"]:
                combo.bind("<Key>", lambda ev, s=entry.student_id: _on_key(ev, s))

        baseline["digest"] = register.payload_digest(_payload())
        if row_order and not locked["value"]:
            row_state[row_order[0]]["combo"].focus_set()
        gui.status_var.set(f"Loaded register: slot #{sid}, {date_var.get()} "
                           f"({len(entries)} student(s))")

    def _on_key(event, student_id: str):
        """Single-key marking: P/L/A/U marks the row and drops to the next.

        Taking a register of thirty is a rhythm, not thirty mouse
        journeys to a dropdown.
        """
        key = (event.char or "").lower()
        if key not in register.STATUS_KEYS:
            return None
        row_state[student_id]["status"].set(register.STATUS_KEYS[key])
        if register.STATUS_KEYS[key] != "Late":
            row_state[student_id]["minutes_late"].set("")
        index = row_order.index(student_id)
        if index + 1 < len(row_order):
            row_state[row_order[index + 1]]["combo"].focus_set()
        return "break"   # don't let the combobox do its own key search

    def _apply_stamps(sid: int, date_s: str) -> list[str]:
        """Push changed In/Out times through the stamp API. Returns problems."""
        problems: list[str] = []
        for student_id in row_order:
            vs = row_state[student_id]
            arrival = vs["arrival"].get().strip()
            if arrival and arrival != (vs["was_arrival"] or ""):
                try:
                    register.record_arrival(sid, date_s, student_id, arrival)
                except ValidationError as e:
                    problems.append(f"{student_id} arrival: {e}")
            departure = vs["departure"].get().strip()
            if departure and departure != (vs["was_departure"] or ""):
                try:
                    register.record_departure(sid, date_s, student_id,
                                              departure)
                except ValidationError as e:
                    problems.append(f"{student_id} departure: {e}")
        return problems

    def submit() -> None:
        sid = _slot_id()
        if sid is None:
            messagebox.showerror("Cannot save",
                                 "Pick a slot.", parent=gui.root)
            return
        if not row_state:
            messagebox.showinfo("Nothing to save",
                                "Load the register first.", parent=gui.root)
            return
        date_s = date_var.get()
        try:
            n = data.save_register(sid, date_s, _payload())
        except ValidationError as e:
            logger.warning("save_register rejected: %s", e)
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("save_register crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=gui.root)
            return

        problems = _apply_stamps(sid, date_s)
        gui.status_var.set(f"Saved register: slot #{sid}, {date_s}")
        message = f"Saved {n} row(s) for slot #{sid} on {date_s}."
        if problems:
            message += "\n\nTimes not applied:\n  " + "\n  ".join(problems)
        messagebox.showinfo("Register saved", message, parent=gui.root)
        load(force=True)

    def copy_previous() -> None:
        sid = _slot_id()
        if sid is None or not _confirm_discard():
            return
        date_s = date_var.get()
        try:
            source = register.previous_register_date(sid, date_s)
            if source is None:
                messagebox.showinfo(
                    "Nothing to copy",
                    "This slot has not been marked before that date.",
                    parent=gui.root)
                return
            overwrite = messagebox.askyesno(
                "Copy previous session",
                f"Copy the marks from {source}?\n\n"
                "Yes: overwrite marks already taken today.\n"
                "No: only fill in students with no mark yet.",
                parent=gui.root)
            result = register.copy_previous_register(sid, date_s,
                                                     overwrite=overwrite)
        except ValidationError as e:
            messagebox.showerror("Cannot copy", str(e), parent=gui.root)
            return
        messagebox.showinfo(
            "Copied forward",
            f"Copied {result.copied} mark(s) from {result.source_date}.",
            parent=gui.root)
        load(force=True)

    def undo() -> None:
        sid = _slot_id()
        if sid is None:
            return
        date_s = date_var.get()
        steps = register.snapshot_count(sid, date_s)
        if not steps:
            messagebox.showinfo("Nothing to undo",
                                "This register has no saved changes to roll "
                                "back.", parent=gui.root)
            return
        if not messagebox.askyesno(
                "Undo last save",
                f"Roll this register back to before the last save?\n\n"
                f"{steps} step(s) available.",
                parent=gui.root):
            return
        try:
            result = register.undo_last_save(sid, date_s)
        except ValidationError as e:
            messagebox.showerror("Cannot undo", str(e), parent=gui.root)
            return
        gui.status_var.set(
            f"Undid last save: {result.restored} restored, "
            f"{result.deleted} removed")
        load(force=True)

    def submit_and_lock() -> None:
        sid = _slot_id()
        if sid is None:
            return
        date_s = date_var.get()
        if has_unsaved() and messagebox.askyesno(
                "Unsaved marks",
                "Save the marks on screen before submitting?",
                parent=gui.root):
            submit()
        try:
            register.submit_register(sid, date_s,
                                     submitted_by=_actor(gui))
        except ValidationError as e:
            if "unmarked" not in str(e):
                messagebox.showerror("Cannot submit", str(e), parent=gui.root)
                return
            if not messagebox.askyesno(
                    "Incomplete register",
                    f"{e}\n\nSubmit it anyway?", default="no",
                    parent=gui.root):
                return
            try:
                register.submit_register(sid, date_s, allow_incomplete=True,
                                         submitted_by=_actor(gui))
            except ValidationError as e2:
                messagebox.showerror("Cannot submit", str(e2), parent=gui.root)
                return
        gui.status_var.set(f"Register submitted: slot #{sid}, {date_s}")
        load(force=True)

    def reopen() -> None:
        sid = _slot_id()
        if sid is None:
            return
        date_s = date_var.get()
        reason = (simpledialog.askstring(
            "Reopen register",
            "Why is this register being reopened?", parent=gui.root) or "").strip()
        if not reason:
            return
        try:
            register.reopen_register(sid, date_s, reason=reason,
                                     reopened_by=_actor(gui))
        except ValidationError as e:
            messagebox.showerror("Cannot reopen", str(e), parent=gui.root)
            return
        gui.status_var.set(f"Register reopened: slot #{sid}, {date_s}")
        load(force=True)

    # ── Bulk-mark toolbar ──
    marks = ttk.Frame(parent)
    marks.pack(anchor="w", pady=(0, 4))
    selected_only = tk.BooleanVar(value=False)
    ttk.Label(marks, text="Mark:").pack(side="left", padx=(0, 4))
    for status in STATUSES:
        ttk.Button(
            marks, text=status, width=11,
            command=lambda s=status: _apply_status(
                s, selected_only=selected_only.get()),
        ).pack(side="left", padx=(0, 4))
    ttk.Checkbutton(marks, text="selected only",
                    variable=selected_only).pack(side="left", padx=(8, 0))
    ttk.Label(marks, text=f"  ({_KEY_HINT})", foreground="#777"
              ).pack(side="left")

    actions = ttk.Frame(parent)
    actions.pack(anchor="w", pady=(0, 4))
    for text, command in (
        ("Load",             lambda: load()),
        ("Save register",    submit),
        ("Copy previous",    copy_previous),
        ("Undo last save",   undo),
        ("Submit & lock",    submit_and_lock),
        ("Reopen",           reopen),
    ):
        ttk.Button(actions, text=text, command=command
                   ).pack(side="left", padx=(0, 6))

    load(force=True)
    return has_unsaved


# ─── Records tab ────────────────────────────────────────────────────

def _build_records_tab(gui, parent: ttk.Frame) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    sid_var = tk.StringVar()
    slot_var = tk.StringVar()
    from_var = tk.StringVar()
    to_var = tk.StringVar()
    status_var = tk.StringVar()

    ttk.Label(filt, text="Student ID:").pack(side="left")
    ttk.Entry(filt, textvariable=sid_var, width=12).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Slot ID:").pack(side="left")
    ttk.Entry(filt, textvariable=slot_var, width=6).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="From:").pack(side="left")
    ttk.Entry(filt, textvariable=from_var, width=12).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="To:").pack(side="left")
    ttk.Entry(filt, textvariable=to_var, width=12).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Status:").pack(side="left")
    ttk.Combobox(filt, textvariable=status_var,
                 values=["", *STATUSES], state="readonly", width=12
                 ).pack(side="left", padx=(4, 4))

    table_holder = ttk.Frame(parent)
    table_holder.pack(fill="both", expand=True)
    summary = ttk.Label(parent, text="", foreground="#555")
    summary.pack(anchor="w", pady=(4, 8))
    actions_holder = ttk.Frame(parent)
    actions_holder.pack(anchor="w", pady=(0, 4))

    def refresh() -> None:
        for w in table_holder.winfo_children():
            w.destroy()
        for w in actions_holder.winfo_children():
            w.destroy()
        try:
            kwargs: dict[str, Any] = {
                "student_id": sid_var.get().strip() or None,
                "status": status_var.get().strip() or None,
                "date_from": from_var.get().strip() or None,
                "date_to": to_var.get().strip() or None,
            }
            if slot_var.get().strip():
                try:
                    kwargs["slot_id"] = int(slot_var.get())
                except ValueError:
                    messagebox.showerror("Bad filter",
                                         "Slot ID must be a number.",
                                         parent=gui.root)
                    return
            rows = data.list_records(**kwargs)
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("list_records failed")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("record_id", "date", "slot", "student", "status",
                "minutes_late", "notes")
        headings = {
            "record_id":    ("#",      50),
            "date":         ("Date",   100),
            "slot":         ("Slot",    60),
            "student":      ("Student", 110),
            "status":       ("Status", 110),
            "minutes_late": ("Mins",    50),
            "notes":        ("Notes",  240),
        }
        tree = ttk.Treeview(table_holder, columns=cols, show="headings", height=14)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        for r in rows:
            tree.insert("", "end", iid=str(r.record_id), values=(
                r.record_id, r.date, r.slot_id, r.student_id,
                r.status,
                r.minutes_late if r.minutes_late is not None else "—",
                r.notes or "",
            ))
        summary.configure(text=f"{len(rows)} record(s).")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _edit_status() -> None:
            rid = _selected()
            if rid is None:
                messagebox.showinfo("No selection",
                                    "Pick a record first.", parent=gui.root)
                return
            _quick_edit_dialog(gui, rid, on_saved=refresh)

        def _delete() -> None:
            rid = _selected()
            if rid is None:
                messagebox.showinfo("No selection",
                                    "Pick a record first.", parent=gui.root)
                return
            if not messagebox.askyesno(
                    "Delete record",
                    f"Delete attendance record #{rid}?",
                    parent=gui.root):
                return
            try:
                data.delete_record(rid)
            except Exception as e:
                logger.exception("delete_record failed")
                messagebox.showerror("Error", f"Could not delete: {e}",
                                     parent=gui.root)
                return
            refresh()

        ttk.Button(actions_holder, text="Edit",
                   command=_edit_status).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Delete",
                   command=_delete).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Refresh",
                   command=refresh).pack(side="left", padx=(12, 0))
        gui.status_var.set(f"Attendance records: {len(rows)} match(es)")

    ttk.Button(filt, text="Apply", command=refresh
               ).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
               command=lambda: (sid_var.set(""), slot_var.set(""),
                                from_var.set(""), to_var.set(""),
                                status_var.set(""), refresh())
               ).pack(side="left", padx=(4, 0))
    refresh()


def _quick_edit_dialog(gui, record_id: int, on_saved) -> None:
    rec = data.get_record(record_id)
    if rec is None:
        messagebox.showerror("Not found", f"No record #{record_id}",
                             parent=gui.root)
        return

    win = tk.Toplevel(gui.root)
    win.title(f"Edit attendance #{record_id}")
    win.transient(gui.root)
    grab_when_viewable(win)

    frm = ttk.Frame(win, padding=12)
    frm.grid()

    status_var = tk.StringVar(value=rec.status)
    late_var = tk.StringVar(value=str(rec.minutes_late) if rec.minutes_late is not None else "")
    notes_var = tk.StringVar(value=rec.notes or "")

    ttk.Label(frm, text=f"{rec.student_id}  ·  slot #{rec.slot_id}  ·  {rec.date}",
              foreground="#555").grid(row=0, column=0, columnspan=2,
                                       sticky="w", pady=(0, 8))
    ttk.Label(frm, text="Status:").grid(row=1, column=0, sticky="e", padx=(0, 6), pady=2)
    ttk.Combobox(frm, textvariable=status_var, values=list(STATUSES),
                 state="readonly", width=18
                 ).grid(row=1, column=1, sticky="w", pady=2)
    ttk.Label(frm, text="Minutes late:").grid(row=2, column=0, sticky="e", padx=(0, 6), pady=2)
    ttk.Entry(frm, textvariable=late_var, width=10
              ).grid(row=2, column=1, sticky="w", pady=2)
    ttk.Label(frm, text="Notes:").grid(row=3, column=0, sticky="e", padx=(0, 6), pady=2)
    ttk.Entry(frm, textvariable=notes_var, width=42
              ).grid(row=3, column=1, sticky="w", pady=2)

    def save() -> None:
        try:
            data.update_record(record_id, {
                "status": status_var.get(),
                "minutes_late": late_var.get(),
                "notes": notes_var.get(),
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("update_record crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()
        on_saved()

    bar = ttk.Frame(frm)
    bar.grid(row=4, column=0, columnspan=2, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


# ─── Summary tab ────────────────────────────────────────────────────

def _build_summary_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))

    groups = cg_data.list_groups()
    courses_by_id = {c.course_id: c for c in course_data.list_courses()}
    group_labels = [
        f"#{g.group_id} {g.group_name} "
        f"({courses_by_id.get(g.course_id).course_code if g.course_id in courses_by_id else '?'})"
        for g in groups
    ]
    group_by_label = {lbl: g.group_id for lbl, g in zip(group_labels, groups)}

    group_var = tk.StringVar(value=group_labels[0] if group_labels else "")
    from_var = tk.StringVar()
    to_var = tk.StringVar()

    ttk.Label(bar, text="Group:").pack(side="left")
    ttk.Combobox(bar, textvariable=group_var, values=group_labels,
                 state="readonly", width=40).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="From:").pack(side="left")
    ttk.Entry(bar, textvariable=from_var, width=12).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="To:").pack(side="left")
    ttk.Entry(bar, textvariable=to_var, width=12).pack(side="left", padx=(4, 12))

    table_holder = ttk.Frame(parent)
    table_holder.pack(fill="both", expand=True)
    grp_label = ttk.Label(parent, text="", foreground="#333")
    grp_label.pack(anchor="w", pady=(8, 0))

    def render() -> None:
        for w in table_holder.winfo_children():
            w.destroy()
        gid = group_by_label.get(group_var.get())
        if gid is None:
            ttk.Label(table_holder, text="Pick a group.",
                      foreground="#a33").pack(anchor="w")
            return
        try:
            per_student = data.per_student_summary_for_group(
                gid,
                date_from=from_var.get().strip() or None,
                date_to=to_var.get().strip() or None,
            )
            group_summary = data.summary_for_group(
                gid,
                date_from=from_var.get().strip() or None,
                date_to=to_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("summary failed")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        students_index = {s.student_id: s for s in student_data.list_students()}

        cols = ("student_id", "name", "total", "present", "late",
                "absent", "authorised", "pct")
        headings = {
            "student_id": ("Student ID", 110),
            "name":       ("Name",       220),
            "total":      ("Sessions",    70),
            "present":    ("Present",     70),
            "late":       ("Late",        50),
            "absent":     ("Absent",      70),
            "authorised": ("Auth.",       60),
            "pct":        ("%",           60),
        }
        tree = ttk.Treeview(table_holder, columns=cols, show="headings", height=12)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        for sid, s in sorted(per_student.items()):
            student = students_index.get(sid)
            name = student.full_name if student else "(deleted)"
            tree.insert("", "end", iid=sid, values=(
                sid, name, s.total, s.present, s.late, s.absent,
                s.authorised, f"{s.percentage}%" if s.percentage is not None else "—",
            ))

        pct = (f"{group_summary.percentage}%"
               if group_summary.percentage is not None else "—")
        grp_label.configure(
            text=(f"Group: total sessions={group_summary.total}, "
                  f"present={group_summary.present}, late={group_summary.late}, "
                  f"absent={group_summary.absent}, "
                  f"authorised={group_summary.authorised}, attending={pct}")
        )
        gui.status_var.set("Attendance summary loaded")

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))
    if group_labels:
        render()
    else:
        ttk.Label(table_holder, text="No class groups yet.",
                  foreground="#a33").pack(anchor="w")
