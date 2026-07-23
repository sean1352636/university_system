"""Standalone Timetable Manager.

Extracted from the Module Scheduling GUI's old "Timetables" tab so the
timetable feature can live in its own window and be launched from the main
GUI. Generates, displays, emails and exports student / instructor
timetables.

Data access goes through the two module-level helpers below
(``get_student_schedule_data`` / ``get_instructor_schedule_data``), which are
the single source of truth shared with ``module_scheduling/exports.py`` and
``module_scheduling/instructors_tab.py``. Both only surface *published*
schedule rows so what-if drafts don't leak into personal timetables.
"""
from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.post_18.university_system.infrastructure.database.db import (
    DEFAULT_DB_PATH,
    get_connection,
)

# i18n with fallback
try:
    from education_system.post_18.university_system.core.i18n import get_text as _t
except ImportError:  # pragma: no cover - fallback
    _t = lambda key, **kwargs: key  # noqa: E731

# Schedule constants + scheduler service, with defaults if unavailable.
try:
    from education_system.post_18.university_system.modules.domain.academics.services.module_scheduling import (
        ModuleScheduler,
        DAYS_OF_WEEK,
        TIME_SLOTS,
    )
except ImportError:  # pragma: no cover - fallback
    DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    TIME_SLOTS = ["09:00", "10:00", "11:00", "12:00", "13:00",
                  "14:00", "15:00", "16:00", "17:00"]

    class ModuleScheduler:  # type: ignore
        pass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared schedule-data helpers (single source of truth)
# ---------------------------------------------------------------------------
def _schedule_rows(where_clause: str, params: list) -> list[dict]:
    """Run the common schedule query and shape rows into dicts.

    Only ``published`` schedule rows are returned so draft / what-if rows
    stay out of personal timetables.
    """
    query = f"""
        SELECT ms.module_code, m.module_name, ms.day_of_week, ms.start_time,
               ms.end_time, r.building, r.room_number, i.first_name,
               i.last_name, ms.session_type, ms.recurrence, ms.recurrence_until
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN instructors i ON ms.instructor_id = i.id
        LEFT JOIN modules m ON ms.module_code = m.module_code
        WHERE {where_clause}
          AND COALESCE(ms.status, 'published') = 'published'
        ORDER BY ms.day_of_week, ms.start_time
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

    schedule_data = []
    for row in rows:
        (module_code, module_name, day, start, end, building, room,
         first_name, last_name, session_type, recurrence,
         recurrence_until) = row
        schedule_data.append({
            "module_code": module_code,
            "module_name": module_name or "Unknown",
            "day": day,
            "start_time": start,
            "end_time": end,
            "room": f"{building}-{room}" if building and room else "TBA",
            "instructor": (f"{first_name} {last_name}"
                           if first_name and last_name else "TBA"),
            "session_type": session_type,
            "recurrence": recurrence or "weekly",
            "recurrence_until": recurrence_until,
        })
    return schedule_data


def get_student_schedule_data(student_id) -> list[dict]:
    """Published schedule rows for every module a student is enrolled in."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT module_code FROM student_modules WHERE student_id = ?",
            (student_id,),
        )
        modules = [row[0] for row in cursor.fetchall()]
    if not modules:
        return []
    placeholders = ",".join("?" for _ in modules)
    return _schedule_rows(f"ms.module_code IN ({placeholders})", modules)


def get_instructor_schedule_data(instructor_id) -> list[dict]:
    """Published schedule rows taught by a given instructor."""
    return _schedule_rows("ms.instructor_id = ?", [instructor_id])


# ---------------------------------------------------------------------------
# Standalone window
# ---------------------------------------------------------------------------
class TimetableManagementGUI:
    """Self-contained timetable window (student & instructor timetables)."""

    def __init__(self, parent=None, auth=None):
        self.parent = parent
        self.auth = auth
        self.scheduler = ModuleScheduler()
        self.last_timetable_data = None
        self.last_timetable_type = None
        self.last_timetable_id = None

        self.window = tk.Toplevel(parent) if parent else tk.Tk()
        # ``self.root`` mirrors the attribute the moved methods (and the
        # reused export helpers) expect as their messagebox parent.
        self.root = self.window
        self.window.title(_t("scheduling.tabs.timetables") or "Timetable Manager")
        self.window.geometry("1100x700")
        if parent:
            try:
                self.window.transient(parent)
            except Exception:
                pass
        self._build_ui()

    # -- misc host surface the moved methods rely on -----------------------
    def set_auth(self, auth):
        self.auth = auth

    def update_activity_log(self, message):
        logger.info("[timetable] %s", message)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        # Left panel: controls
        left = ttk.Frame(self.window, width=260)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        left.pack_propagate(False)

        # Student timetable section
        student_frame = ttk.LabelFrame(
            left, text=_t("scheduling.student_timetables"), padding=10)
        student_frame.pack(fill=tk.X, pady=5)
        ttk.Label(student_frame,
                  text=_t("scheduling.student_id") + ":").pack(anchor=tk.W)
        self.student_id_var = tk.StringVar()
        ttk.Entry(student_frame, textvariable=self.student_id_var,
                  width=20).pack(fill=tk.X, pady=2)
        ttk.Button(student_frame,
                   text=_t("scheduling.generate_student_timetable"),
                   command=self.generate_student_timetable).pack(fill=tk.X, pady=2)
        ttk.Button(student_frame,
                   text=_t("scheduling.email_timetable_to_student"),
                   command=self.email_student_timetable).pack(fill=tk.X, pady=2)
        ttk.Button(student_frame,
                   text=_t("scheduling.check_student_conflicts"),
                   command=self.check_student_conflicts).pack(fill=tk.X, pady=2)
        ttk.Button(student_frame, text="Open Student Timetable Viewer…",
                   command=self._show_student_timetable_dialog).pack(fill=tk.X, pady=2)

        # Instructor timetable section
        instructor_frame = ttk.LabelFrame(
            left, text=_t("scheduling.instructor_timetables"), padding=10)
        instructor_frame.pack(fill=tk.X, pady=5)
        ttk.Label(instructor_frame,
                  text=_t("scheduling.instructor_id") + ":").pack(anchor=tk.W)
        self.instructor_id_var = tk.StringVar()
        ttk.Entry(instructor_frame, textvariable=self.instructor_id_var,
                  width=20).pack(fill=tk.X, pady=2)
        ttk.Button(instructor_frame,
                   text=_t("scheduling.generate_instructor_timetable"),
                   command=self.generate_instructor_timetable).pack(fill=tk.X, pady=2)
        ttk.Button(instructor_frame,
                   text=_t("scheduling.email_timetable_to_instructor"),
                   command=self.email_instructor_timetable).pack(fill=tk.X, pady=2)

        # Export options
        export_frame = ttk.LabelFrame(
            left, text=_t("scheduling.export_options"), padding=10)
        export_frame.pack(fill=tk.X, pady=5)
        self.export_format_var = tk.StringVar(value="PDF")
        for fmt in ("PDF", "CSV", "Excel", "iCal"):
            ttk.Radiobutton(export_frame, text=fmt,
                            variable=self.export_format_var,
                            value=fmt).pack(anchor=tk.W)
        ttk.Button(export_frame, text=_t("scheduling.export_last_generated"),
                   command=self.export_last_timetable).pack(fill=tk.X, pady=5)

        # Right panel: scrollable timetable display
        right = ttk.Frame(self.window)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        display_frame = ttk.LabelFrame(
            right, text=_t("scheduling.timetable_display"), padding=10)
        display_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(display_frame)
        v_scroll = ttk.Scrollbar(display_frame, orient=tk.VERTICAL,
                                 command=canvas.yview)
        h_scroll = ttk.Scrollbar(display_frame, orient=tk.HORIZONTAL,
                                 command=canvas.xview)
        self.timetable_frame = ttk.Frame(canvas)
        self.timetable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.timetable_frame, anchor="nw")
        canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

    # ---- schedule-data (instance wrappers over the shared helpers) -------
    def _get_student_schedule_data(self, student_id):
        return get_student_schedule_data(student_id)

    def _get_instructor_schedule_data(self, instructor_id):
        return get_instructor_schedule_data(instructor_id)

    # ------------------------------------------------------------ actions
    def generate_student_timetable(self):
        student_id = self.student_id_var.get().strip()
        if not student_id:
            messagebox.showwarning("Warning", "Please enter a student ID.",
                                   parent=self.root)
            return
        try:
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT first_name, last_name FROM students WHERE student_id = ?",
                    (student_id,))
                student = cursor.fetchone()
            if not student:
                messagebox.showerror(
                    "Error", f"Student ID {student_id} does not exist.",
                    parent=self.root)
                return
            student_name = f"{student[0]} {student[1]}"
            schedule_data = get_student_schedule_data(student_id)
            if not schedule_data:
                for widget in self.timetable_frame.winfo_children():
                    widget.destroy()
                tk.Label(self.timetable_frame,
                         text=f"No schedule found for student {student_id}",
                         font=("Arial", 12)).pack(pady=20)
                return
            self._display_timetable_grid(
                schedule_data,
                f"Timetable for {student_name} ({student_id})")
            conflicts = self.scheduler.check_student_conflicts(student_id)
            if conflicts:
                tk.Label(
                    self.timetable_frame,
                    text=f"⚠️ {len(conflicts)} scheduling conflict(s) detected",
                    font=("Arial", 10, "bold"), fg="red").pack(pady=10)
            self.update_activity_log(f"Generated timetable for student {student_id}")
            self.last_timetable_data = schedule_data
            self.last_timetable_type = "student"
            self.last_timetable_id = student_id
        except Exception as e:
            messagebox.showerror(
                "Error", f"Failed to generate student timetable: {e}",
                parent=self.root)

    def generate_instructor_timetable(self):
        instructor_id_str = self.instructor_id_var.get().strip()
        if not instructor_id_str:
            messagebox.showwarning("Warning", "Please enter an instructor ID.",
                                   parent=self.root)
            return
        try:
            instructor_id = int(instructor_id_str)
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT first_name, last_name FROM instructors WHERE id = ?",
                    (instructor_id,))
                instructor = cursor.fetchone()
            if not instructor:
                messagebox.showerror(
                    "Error", f"Instructor ID {instructor_id} does not exist.",
                    parent=self.root)
                return
            instructor_name = f"{instructor[0]} {instructor[1]}"
            schedule_data = get_instructor_schedule_data(instructor_id)
            if not schedule_data:
                for widget in self.timetable_frame.winfo_children():
                    widget.destroy()
                tk.Label(self.timetable_frame,
                         text=f"No schedule found for instructor {instructor_name}",
                         font=("Arial", 12)).pack(pady=20)
                return
            self._display_timetable_grid(
                schedule_data,
                f"Timetable for {instructor_name} (ID: {instructor_id})")
            self.update_activity_log(
                f"Generated timetable for instructor {instructor_name}")
            self.last_timetable_data = schedule_data
            self.last_timetable_type = "instructor"
            self.last_timetable_id = instructor_id
        except ValueError:
            messagebox.showerror(
                "Error", "Invalid instructor ID. Please enter a number.",
                parent=self.root)
        except Exception as e:
            messagebox.showerror(
                "Error", f"Failed to generate instructor timetable: {e}",
                parent=self.root)

    def email_student_timetable(self):
        student_id = self.student_id_var.get().strip()
        if not student_id:
            messagebox.showwarning("Warning", "Please enter a student ID.",
                                   parent=self.root)
            return
        try:
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT first_name, last_name, email_address FROM students "
                    "WHERE student_id = ?", (student_id,))
                student = cursor.fetchone()
            if not student:
                messagebox.showerror("Error", f"Student ID {student_id} not found.",
                                     parent=self.root)
                return
            first_name, last_name, email = student
            student_name = f"{first_name} {last_name}"
            if not email:
                messagebox.showerror(
                    "Error", f"No email address found for student {student_name}.",
                    parent=self.root)
                return
            schedule_data = get_student_schedule_data(student_id)
            if not schedule_data:
                messagebox.showinfo(
                    "Info", f"No schedule found for student {student_id}.",
                    parent=self.root)
                return
            body = self._format_timetable_email(schedule_data, student_name, "student")
            from education_system.post_18.university_system.infrastructure.email.email_service import (
                send_email,
            )
            success = send_email(email, f"Your Timetable - {student_name}", body)
            if success:
                messagebox.showinfo("Success", f"Timetable emailed to {email}",
                                    parent=self.root)
                self.update_activity_log(
                    f"Emailed timetable to student {student_id} ({email})")
            else:
                messagebox.showerror("Error", "Failed to send timetable email.",
                                     parent=self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to email timetable: {e}",
                                 parent=self.root)

    def email_instructor_timetable(self):
        instructor_id_str = self.instructor_id_var.get().strip()
        if not instructor_id_str:
            messagebox.showwarning("Warning", "Please enter an instructor ID.",
                                   parent=self.root)
            return
        try:
            instructor_id = int(instructor_id_str)
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT first_name, last_name, email FROM instructors WHERE id = ?",
                    (instructor_id,))
                instructor = cursor.fetchone()
            if not instructor:
                messagebox.showerror("Error",
                                     f"Instructor ID {instructor_id} not found.",
                                     parent=self.root)
                return
            first_name, last_name, email = instructor
            instructor_name = f"{first_name} {last_name}"
            if not email:
                messagebox.showerror(
                    "Error",
                    f"No email address found for instructor {instructor_name}.",
                    parent=self.root)
                return
            schedule_data = get_instructor_schedule_data(instructor_id)
            if not schedule_data:
                messagebox.showinfo(
                    "Info", f"No schedule found for instructor {instructor_id}.",
                    parent=self.root)
                return
            body = self._format_timetable_email(
                schedule_data, instructor_name, "instructor")
            from education_system.post_18.university_system.infrastructure.email.email_service import (
                send_email,
            )
            success = send_email(
                email, f"Your Teaching Schedule - {instructor_name}", body)
            if success:
                messagebox.showinfo("Success", f"Timetable emailed to {email}",
                                    parent=self.root)
                self.update_activity_log(
                    f"Emailed timetable to instructor {instructor_id} ({email})")
            else:
                messagebox.showerror("Error", "Failed to send timetable email.",
                                     parent=self.root)
        except ValueError:
            messagebox.showerror("Error",
                                 "Invalid instructor ID. Please enter a number.",
                                 parent=self.root)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to email timetable: {e}",
                                 parent=self.root)

    def _format_timetable_email(self, schedule_data, name, recipient_type):
        lines = [f"Dear {name},\n"]
        lines.append("Here is your class timetable:\n"
                     if recipient_type == "student"
                     else "Here is your teaching schedule:\n")
        lines.append("=" * 60)
        lines.append("")
        days_data: dict = {}
        for entry in schedule_data:
            day = entry.get("day", entry.get("day_of_week", "Unknown"))
            days_data.setdefault(day, []).append(entry)
        day_order = {"Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4,
                     "Friday": 5, "Saturday": 6, "Sunday": 7}
        for day in sorted(days_data.keys(), key=lambda d: day_order.get(d, 8)):
            lines.append(f"\n{day.upper()}")
            lines.append("-" * 40)
            for entry in sorted(days_data[day],
                                key=lambda x: x.get("start_time", "")):
                module_code = entry.get("module_code", "N/A")
                module_name = entry.get("module_name", "")
                lines.append(f"  {entry.get('start_time', 'TBA')} - "
                             f"{entry.get('end_time', 'TBA')}")
                lines.append(f"    {module_code}: {module_name}"
                             if module_name else f"    {module_code}")
                lines.append(f"    Type: {entry.get('session_type', 'Session')}")
                lines.append(f"    Room: {entry.get('room', 'TBA')}")
                lines.append("")
        lines.append("=" * 60)
        lines.append("\nIf you have any questions about your schedule, please "
                     "contact the Academic Office.")
        lines.append("\nBest regards,")
        lines.append("Academic Scheduling System")
        lines.append("University Management System")
        return "\n".join(lines)

    def _display_timetable_grid(self, schedule_data, title):
        for widget in self.timetable_frame.winfo_children():
            widget.destroy()
        tk.Label(self.timetable_frame, text=title,
                 font=("Arial", 14, "bold")).pack(pady=10)

        grid_data = {day: {slot: [] for slot in TIME_SLOTS}
                     for day in DAYS_OF_WEEK}
        for entry in schedule_data:
            day = entry.get("day", entry.get("day_of_week", ""))
            start_time = entry.get("start_time", "")
            if not day or not start_time:
                continue
            try:
                closest_slot = min(
                    TIME_SLOTS, key=lambda x: abs(int(x[:2]) - int(start_time[:2])))
            except (ValueError, TypeError, IndexError):
                continue
            session_info = {
                "module": entry.get("module_code", "N/A"),
                "type": entry.get("session_type", "Session"),
                "room": entry.get("room", "TBA"),
                "time": f"{entry.get('start_time', '')}-{entry.get('end_time', '')}",
            }
            if day in grid_data and closest_slot in grid_data[day]:
                grid_data[day][closest_slot].append(session_info)

        grid_frame = tk.Frame(self.timetable_frame)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        tk.Label(grid_frame, text="Time", font=("Arial", 10, "bold"),
                 relief=tk.SOLID, borderwidth=2, bg="#4a90e2", fg="white",
                 width=10, height=2).grid(row=0, column=0, padx=1, pady=1,
                                          sticky="nsew")
        for col, day in enumerate(DAYS_OF_WEEK, 1):
            tk.Label(grid_frame, text=day, font=("Arial", 10, "bold"),
                     relief=tk.SOLID, borderwidth=2, bg="#4a90e2", fg="white",
                     width=18, height=2).grid(row=0, column=col, padx=1, pady=1,
                                              sticky="nsew")
        for row, time_slot in enumerate(TIME_SLOTS, 1):
            tk.Label(grid_frame, text=time_slot, font=("Arial", 9, "bold"),
                     relief=tk.SOLID, borderwidth=2, bg="#e8f4f8",
                     width=10, height=4).grid(row=row, column=0, padx=1, pady=1,
                                              sticky="nsew")
            for col, day in enumerate(DAYS_OF_WEEK, 1):
                entries = grid_data[day][time_slot]
                cell_frame = tk.Frame(grid_frame, relief=tk.SOLID, borderwidth=2,
                                      bg="#d4edda" if entries else "white",
                                      width=160, height=80)
                cell_frame.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")
                cell_frame.grid_propagate(False)
                if not entries:
                    continue
                inner = tk.Frame(cell_frame, bg="#d4edda")
                inner.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
                for i, entry in enumerate(entries):
                    if i < 2:
                        box = tk.Frame(inner, relief=tk.RAISED, borderwidth=1,
                                       bg="#c3e6cb", padx=2, pady=2)
                        box.pack(fill=tk.X, pady=1)
                        tk.Label(box, text=entry["module"], font=("Arial", 8, "bold"),
                                 bg="#c3e6cb", fg="#155724").pack(anchor="w")
                        tk.Label(box, text=entry["type"], font=("Arial", 7),
                                 bg="#c3e6cb", fg="#155724").pack(anchor="w")
                        tk.Label(box, text=f"Room: {entry['room']}",
                                 font=("Arial", 6), bg="#c3e6cb",
                                 fg="#155724").pack(anchor="w")
                if len(entries) > 2:
                    tk.Label(inner, text=f"+ {len(entries) - 2} more...",
                             font=("Arial", 7, "italic"), bg="#d4edda",
                             fg="#155724").pack(anchor="w", pady=2)

    def check_student_conflicts(self):
        student_id = self.student_id_var.get().strip()
        if not student_id:
            messagebox.showwarning("Warning", "Please enter a student ID.",
                                   parent=self.root)
            return
        try:
            conflicts = self.scheduler.check_student_conflicts(student_id)
            for widget in self.timetable_frame.winfo_children():
                widget.destroy()
            if not conflicts:
                tk.Label(
                    self.timetable_frame,
                    text=f"No scheduling conflicts found for student {student_id}",
                    font=("Arial", 12)).pack(pady=20)
            else:
                tk.Label(self.timetable_frame,
                         text=f"Scheduling Conflicts for Student {student_id}",
                         font=("Arial", 14, "bold")).pack(pady=10)
                for i, conflict in enumerate(conflicts, 1):
                    module1 = conflict.get("module1", {}) if hasattr(conflict, "get") else {}
                    module2 = conflict.get("module2", {}) if hasattr(conflict, "get") else {}
                    frame = ttk.LabelFrame(self.timetable_frame,
                                           text=f"Conflict {i}", padding=10)
                    frame.pack(fill=tk.X, padx=10, pady=5)
                    tk.Label(frame,
                             text=f"Module 1: {module1.get('code', '?')} - "
                                  f"{module1.get('name', '')}",
                             font=("Arial", 10, "bold"), fg="red").pack(anchor="w")
                    tk.Label(frame,
                             text=f"    {module1.get('day', '')} "
                                  f"{module1.get('time', '')} in "
                                  f"{module1.get('room', '')}",
                             font=("Arial", 10)).pack(anchor="w")
                    tk.Label(frame,
                             text=f"Module 2: {module2.get('code', '?')} - "
                                  f"{module2.get('name', '')}",
                             font=("Arial", 10, "bold"),
                             fg="red").pack(anchor="w", pady=(5, 0))
                    tk.Label(frame,
                             text=f"    {module2.get('day', '')} "
                                  f"{module2.get('time', '')} in "
                                  f"{module2.get('room', '')}",
                             font=("Arial", 10)).pack(anchor="w")
            self.update_activity_log(f"Checked conflicts for student {student_id}")
        except Exception as e:
            messagebox.showerror("Error",
                                 f"Failed to check student conflicts: {e}",
                                 parent=self.root)

    def export_last_timetable(self):
        if not self.last_timetable_data:
            messagebox.showwarning(
                "Warning",
                "No timetable to export. Please generate a timetable first.",
                parent=self.root)
            return
        fmt = self.export_format_var.get()
        # Reuse the module-scheduling export implementations (they operate on
        # ``self`` and only need ``self.root`` as a messagebox parent).
        from education_system.post_18.university_system.modules.domain.academics.gui.module_scheduling import (
            exports as _exports,
        )
        try:
            if fmt == "iCal":
                _exports._export_timetable_to_ical(self, self.last_timetable_data)
            elif fmt == "PDF":
                _exports._export_timetable_to_pdf(self, self.last_timetable_data)
            elif fmt == "CSV":
                _exports._export_timetable_to_csv(self, self.last_timetable_data)
            elif fmt == "Excel":
                _exports._export_timetable_to_excel(self, self.last_timetable_data)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export timetable: {e}",
                                 parent=self.root)

    def _show_student_timetable_dialog(self):
        try:
            from education_system.post_18.university_system.modules.domain.academics.gui.module_scheduling.student_timetable_dialog import (
                StudentTimetableDialog,
            )
            StudentTimetableDialog(self.root, self.scheduler)
        except Exception as e:
            messagebox.showerror(
                "Error", f"Failed to open student timetable viewer: {e}",
                parent=self.root)
