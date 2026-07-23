"""
University Lesson Planner - A GUI application for managing university lessons,
courses, and schedules.

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. The header shows the signed-in user; key
write actions are stamped with that identity in the log.

Persistence: rows live in the central `student_records.db` tables
`lesson_plans` and `lesson_courses` (module-private — they're
pedagogical scheduling artefacts, distinct from the canonical
`courses` table used by Academic Management). The legacy
`lesson_planner_data.json` sidecar is removed on startup.

Logging: routed through the shared rotating `app.log` via
`infrastructure.logging.log_config.configure_logging`.
"""

import logging
import os
import sqlite3
import sys
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, filedialog


# When the main GUI launches us as a subprocess, the child Python is
# invoked directly on this file's path with no PYTHONPATH set, so
# `education_system` isn't importable. Walk up from this file until we
# find the dir that contains the `education_system` package and put
# that on sys.path. No-op when imported normally.
if 'education_system' not in sys.modules:
    _here = os.path.abspath(os.path.dirname(__file__))
    while _here and not os.path.isdir(os.path.join(_here, 'education_system')):
        _parent = os.path.dirname(_here)
        if _parent == _here:
            break
        _here = _parent
    if _here and _here not in sys.path:
        sys.path.insert(0, _here)


logger = logging.getLogger(__name__)

try:
    from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
    configure_logging(name=__name__)
except Exception:
    logger.debug("Central log config unavailable; falling back to default handlers", exc_info=True)


# ---------------------------------------------------------------------------
# AUTH BOOTSTRAP
# ---------------------------------------------------------------------------
def _get_current_user():
    user_id = os.environ.get('EDU_AUTH_USER_ID') or ''
    username = os.environ.get('EDU_AUTH_USERNAME') or ''
    role = os.environ.get('EDU_AUTH_ROLE') or ''
    email = os.environ.get('EDU_AUTH_EMAIL') or ''
    perms_raw = os.environ.get('EDU_AUTH_PERMISSIONS') or ''
    if user_id or username:
        return {
            'id': user_id or None,
            'user_id': user_id or None,
            'username': username,
            'role': role,
            'email': email,
            'permissions': [p for p in perms_raw.split(',') if p],
        }
    try:
        from education_system.post_18.university_system.infrastructure.auth import get_global_auth
        ga = get_global_auth()
        if ga and getattr(ga, 'current_user', None):
            return ga.current_user
    except Exception:
        logger.debug("get_global_auth fallback failed", exc_info=True)
    return None


def _user_display_name(user):
    if not user:
        return 'Guest'
    return (user.get('username') or user.get('email') or
            user.get('user_id') or user.get('id') or 'Unknown')


_LEGACY_DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "lesson_planner_data.json")


def _remove_legacy_files():
    """Sweep stray sidecar files left by earlier iterations of this
    module. Data now lives in the central student_records.db."""
    here = os.path.dirname(os.path.abspath(__file__))
    targets = [_LEGACY_DATA_FILE,
               os.path.abspath("lesson_planner_data.json")]
    if os.path.isdir(here):
        for fname in os.listdir(here):
            if fname.endswith(('.db', '.db-wal', '.db-shm', '.db-journal')):
                targets.append(os.path.join(here, fname))
    for path in set(targets):
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info("Removed legacy lesson-planner data file: %s", path)
            except OSError:
                logger.warning("Could not remove legacy file %s", path,
                               exc_info=True)


_LESSON_FIELDS = ("course", "title", "instructor", "type", "day",
                  "start", "end", "room", "notes")
_COURSE_FIELDS = ("code", "name", "dept", "credits", "semester", "description")


class LessonPlannerApp:
    """Main application class for the University Lesson Planner."""

    DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    TIME_SLOTS = [f"{h:02d}:00" for h in range(8, 21)]
    LESSON_TYPES = ["Lecture", "Seminar", "Lab", "Tutorial", "Workshop", "Exam"]

    def __init__(self, root):
        self.root = root
        # When ``root`` is a workspace tab Frame (passed by
        # ``open_in_workspace``), it has no ``wm_title`` — skip the
        # window-chrome calls. Same shape Library uses (8.117.34).
        if hasattr(self.root, "wm_title"):
            self.root.title("University Lesson Planner")
            self.root.geometry("1200x720")
        try:
            self.root.configure(bg="#f0f0f0")
        except tk.TclError:
            pass

        self.user = _get_current_user()
        self.user_display = _user_display_name(self.user)
        logger.info("Lesson Planner starting user=%s role=%s",
                    self.user_display,
                    (self.user or {}).get('role') or 'none')

        # Cross-system seam (event bus, room booking, attendance, audit, …).
        # Constructed defensively — a missing integrations module must not
        # stop the planner from opening.
        try:
            from education_system.post_18.university_system.modules.domain.academics.course_planning.lesson_planner_integrations import (
                PlannerIntegrations,
            )
            self.integrations = PlannerIntegrations(self.user, self.user_display)
        except Exception:
            logger.debug("PlannerIntegrations unavailable", exc_info=True)
            self.integrations = None

        # Data storage
        self.lessons = []
        self.courses = []
        self.selected_lesson_index = None

        self._setup_styles()
        self._build_ui()
        self._ensure_schema()
        self._load_data()
        self._refresh_views()

    # ---------- UI Setup ----------

    def _setup_styles(self):
        # ttk.Style is process-global. When this app is embedded in the
        # main GUI workspace via _embed_or_subprocess, configuring base
        # style names (TNotebook, TFrame, TLabel, …) leaks out and
        # recolours the host. Only named styles are safe.
        style = ttk.Style()
        style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"))
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"),
                        background="#f0f0f0", foreground="#000000")

    def _build_ui(self):
        # Top header bar — flat #f0f0f0 bg with dark text to match the
        # main GUI; pre-8.117.66 this was a navy bar (#1e3a8a) with
        # white text, visually disconnected from the rest of the app.
        header = tk.Frame(self.root, bg="#f0f0f0", height=60)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="🎓 University Lesson Planner",
                 bg="#f0f0f0", fg="#000000",
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=20)

        role = (self.user or {}).get('role') or ('—' if self.user else 'not signed in')
        tk.Label(header,
                 text=f"Signed in: {self.user_display}  ({role})",
                 bg="#f0f0f0", fg="#555555",
                 font=("Segoe UI", 9)).pack(side="right", padx=20)

        self.status_label = tk.Label(header, text="", bg="#f0f0f0",
                                     fg="#555555", font=("Segoe UI", 9))
        self.status_label.pack(side="right", padx=20)

        # Main notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_lessons_tab()
        self._build_schedule_tab()
        self._build_courses_tab()

    def _build_lessons_tab(self):
        tab = tk.Frame(self.notebook, bg="#f0f0f0")
        self.notebook.add(tab, text="  📚 Lessons  ")

        # Left panel: form
        form_frame = ttk.LabelFrame(tab, text="Lesson Details", padding=15)
        form_frame.pack(side="left", fill="y", padx=(0, 10))

        fields = [
            ("Course:", "course_var", "combobox"),
            ("Lesson Title:", "title_var", "entry"),
            ("Instructor:", "instructor_var", "entry"),
            ("Type:", "type_var", "combobox_type"),
            ("Day:", "day_var", "combobox_day"),
            ("Start Time:", "start_var", "combobox_time"),
            ("End Time:", "end_var", "combobox_time"),
            ("Room:", "room_var", "entry"),
        ]

        self.form_vars = {}
        for i, (label, var_name, field_type) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=i, column=0,
                                                    sticky="w", pady=6)
            var = tk.StringVar()
            self.form_vars[var_name] = var

            if field_type == "entry":
                widget = ttk.Entry(form_frame, textvariable=var, width=28)
            elif field_type == "combobox":
                widget = ttk.Combobox(form_frame, textvariable=var,
                                      width=26, state="readonly")
                self.course_combo = widget
            elif field_type == "combobox_type":
                widget = ttk.Combobox(form_frame, textvariable=var,
                                      width=26, values=self.LESSON_TYPES,
                                      state="readonly")
            elif field_type == "combobox_day":
                widget = ttk.Combobox(form_frame, textvariable=var,
                                      width=26, values=self.DAYS,
                                      state="readonly")
            elif field_type == "combobox_time":
                widget = ttk.Combobox(form_frame, textvariable=var,
                                      width=26, values=self.TIME_SLOTS,
                                      state="readonly")
            widget.grid(row=i, column=1, pady=6, padx=(10, 0))

        # Notes
        ttk.Label(form_frame, text="Notes:").grid(row=len(fields), column=0,
                                                    sticky="nw", pady=6)
        self.notes_text = tk.Text(form_frame, height=4, width=22,
                                   font=("Segoe UI", 9),
                                   relief="solid", borderwidth=1)
        self.notes_text.grid(row=len(fields), column=1, pady=6, padx=(10, 0))

        # Buttons
        btn_frame = tk.Frame(form_frame, bg="#f0f0f0")
        btn_frame.grid(row=len(fields) + 1, column=0, columnspan=2, pady=15)

        ttk.Button(btn_frame, text="Add Lesson",
                   command=self._add_lesson,
                   style="Accent.TButton").pack(side="left", padx=3)
        ttk.Button(btn_frame, text="Update",
                   command=self._update_lesson).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="Delete",
                   command=self._delete_lesson).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="Clear",
                   command=self._clear_form).pack(side="left", padx=3)

        # Cross-system actions on the selected lesson.
        if self.integrations:
            int_frame = tk.Frame(form_frame, bg="#f0f0f0")
            int_frame.grid(row=len(fields) + 2, column=0, columnspan=2, pady=(0, 5))
            ttk.Button(int_frame, text="🚪 Find / Reserve Room",
                       command=self._reserve_room_for_selected).pack(side="left", padx=3)
            ttk.Button(int_frame, text="🗓 Attendance Session",
                       command=self._make_attendance_session).pack(side="left", padx=3)

        # Right panel: lessons list
        list_frame = ttk.LabelFrame(tab, text="All Lessons", padding=10)
        list_frame.pack(side="right", fill="both", expand=True)

        # Search bar
        search_frame = tk.Frame(list_frame, bg="#f0f0f0")
        search_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(search_frame, text="🔍 Search:").pack(side="left", padx=(0, 6))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self._refresh_lesson_list())
        ttk.Entry(search_frame, textvariable=self.search_var,
                  width=30).pack(side="left")

        # Treeview
        columns = ("Course", "Title", "Type", "Day", "Time", "Room", "Instructor")
        self.lessons_tree = ttk.Treeview(list_frame, columns=columns,
                                          show="headings", height=18)

        widths = {"Course": 120, "Title": 160, "Type": 80, "Day": 90,
                  "Time": 110, "Room": 80, "Instructor": 130}
        for col in columns:
            self.lessons_tree.heading(col, text=col)
            self.lessons_tree.column(col, width=widths.get(col, 100))

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical",
                                   command=self.lessons_tree.yview)
        self.lessons_tree.configure(yscrollcommand=scrollbar.set)

        self.lessons_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.lessons_tree.bind("<<TreeviewSelect>>", self._on_lesson_select)

    def _build_schedule_tab(self):
        tab = tk.Frame(self.notebook, bg="#f0f0f0")
        self.notebook.add(tab, text="  📅 Weekly Schedule  ")

        header_frame = tk.Frame(tab, bg="#f0f0f0")
        header_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(header_frame, text="Weekly Timetable",
                  style="Header.TLabel").pack(side="left")

        ttk.Button(header_frame, text="🔄 Refresh",
                   command=self._refresh_schedule).pack(side="right")
        ttk.Button(header_frame, text="📤 Export",
                   command=self._export_schedule).pack(side="right", padx=6)
        # Cross-system actions — only shown when the integration seam loaded.
        if self.integrations:
            ttk.Button(header_frame, text="📆 Export .ics",
                       command=self._export_ics).pack(side="right", padx=6)
            ttk.Button(header_frame, text="✅ Validate Hours",
                       command=self._validate_hours).pack(side="right", padx=6)
            ttk.Button(header_frame, text="🔒 Lock Timetable",
                       command=self._lock_timetable).pack(side="right", padx=6)

        # Scrollable canvas for schedule grid
        canvas_frame = tk.Frame(tab, bg="#f0f0f0")
        canvas_frame.pack(fill="both", expand=True)

        self.schedule_canvas = tk.Canvas(canvas_frame, bg="white",
                                          highlightthickness=1,
                                          highlightbackground="#cbd5e1")
        v_scroll = ttk.Scrollbar(canvas_frame, orient="vertical",
                                  command=self.schedule_canvas.yview)
        h_scroll = ttk.Scrollbar(canvas_frame, orient="horizontal",
                                  command=self.schedule_canvas.xview)

        self.schedule_canvas.configure(yscrollcommand=v_scroll.set,
                                        xscrollcommand=h_scroll.set)

        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")
        self.schedule_canvas.pack(side="left", fill="both", expand=True)

    def _build_courses_tab(self):
        tab = tk.Frame(self.notebook, bg="#f0f0f0")
        self.notebook.add(tab, text="  🎯 Courses  ")

        # Left: Add course form
        form_frame = ttk.LabelFrame(tab, text="Add New Course", padding=15)
        form_frame.pack(side="left", fill="y", padx=(0, 10))

        self.course_vars = {}
        course_fields = [
            ("Course Code:", "code"),
            ("Course Name:", "name"),
            ("Department:", "dept"),
            ("Credits:", "credits"),
            ("Semester:", "semester"),
        ]

        for i, (label, key) in enumerate(course_fields):
            ttk.Label(form_frame, text=label).grid(row=i, column=0,
                                                    sticky="w", pady=6)
            var = tk.StringVar()
            self.course_vars[key] = var
            ttk.Entry(form_frame, textvariable=var,
                      width=25).grid(row=i, column=1, pady=6, padx=(10, 0))

        ttk.Label(form_frame, text="Description:").grid(
            row=len(course_fields), column=0, sticky="nw", pady=6)
        self.course_desc = tk.Text(form_frame, height=5, width=19,
                                    font=("Segoe UI", 9),
                                    relief="solid", borderwidth=1)
        self.course_desc.grid(row=len(course_fields), column=1,
                              pady=6, padx=(10, 0))

        btn_frame = tk.Frame(form_frame, bg="#f0f0f0")
        btn_frame.grid(row=len(course_fields) + 1, column=0,
                       columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Add Course",
                   command=self._add_course,
                   style="Accent.TButton").pack(side="left", padx=3)
        ttk.Button(btn_frame, text="Delete Selected",
                   command=self._delete_course).pack(side="left", padx=3)

        # Right: Courses list
        list_frame = ttk.LabelFrame(tab, text="Course Catalog", padding=10)
        list_frame.pack(side="right", fill="both", expand=True)

        columns = ("Code", "Name", "Department", "Credits", "Semester")
        self.courses_tree = ttk.Treeview(list_frame, columns=columns,
                                          show="headings", height=18)

        widths = {"Code": 100, "Name": 220, "Department": 150,
                  "Credits": 80, "Semester": 100}
        for col in columns:
            self.courses_tree.heading(col, text=col)
            self.courses_tree.column(col, width=widths.get(col, 100))

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical",
                                   command=self.courses_tree.yview)
        self.courses_tree.configure(yscrollcommand=scrollbar.set)
        self.courses_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    # ---------- Lesson Operations ----------

    def _validate_lesson(self):
        required = ["course_var", "title_var", "instructor_var", "type_var",
                    "day_var", "start_var", "end_var"]
        for field in required:
            if not self.form_vars[field].get().strip():
                messagebox.showerror("Validation Error",
                                     "Please fill in all required fields.")
                return False

        start = self.form_vars["start_var"].get()
        end = self.form_vars["end_var"].get()
        if start >= end:
            messagebox.showerror("Validation Error",
                                 "End time must be after start time.")
            return False
        return True

    def _get_form_data(self):
        return {
            "course": self.form_vars["course_var"].get(),
            "title": self.form_vars["title_var"].get(),
            "instructor": self.form_vars["instructor_var"].get(),
            "type": self.form_vars["type_var"].get(),
            "day": self.form_vars["day_var"].get(),
            "start": self.form_vars["start_var"].get(),
            "end": self.form_vars["end_var"].get(),
            "room": self.form_vars["room_var"].get(),
            "notes": self.notes_text.get("1.0", "end-1c"),
        }

    def _check_conflict(self, new_lesson, ignore_index=None):
        for i, lesson in enumerate(self.lessons):
            if i == ignore_index:
                continue
            if lesson["day"] != new_lesson["day"]:
                continue
            if lesson["room"] and lesson["room"] == new_lesson["room"]:
                if not (new_lesson["end"] <= lesson["start"] or
                        new_lesson["start"] >= lesson["end"]):
                    return f"Room conflict with '{lesson['title']}' ({lesson['start']}–{lesson['end']})"
            if lesson["instructor"] == new_lesson["instructor"]:
                if not (new_lesson["end"] <= lesson["start"] or
                        new_lesson["start"] >= lesson["end"]):
                    return f"Instructor conflict with '{lesson['title']}' ({lesson['start']}–{lesson['end']})"
        return None

    def _add_lesson(self):
        if not self._validate_lesson():
            return
        new_lesson = self._get_form_data()
        conflict = self._check_conflict(new_lesson)
        if conflict:
            if not messagebox.askyesno("Conflict Detected",
                                        f"{conflict}\n\nAdd anyway?"):
                return
        self.lessons.append(new_lesson)
        self._save_data()
        logger.info("Lesson added title=%r course=%r day=%s start=%s by=%s",
                    new_lesson.get('title'), new_lesson.get('course'),
                    new_lesson.get('day'), new_lesson.get('start'), self.user_display)
        if self.integrations:
            self.integrations.on_lesson_changed("created", new_lesson)
        self._refresh_views()
        self._clear_form()
        self._set_status(f"Added lesson: {new_lesson['title']}")

    def _update_lesson(self):
        if self.selected_lesson_index is None:
            messagebox.showwarning("No Selection",
                                    "Please select a lesson to update.")
            return
        if not self._validate_lesson():
            return
        updated = self._get_form_data()
        conflict = self._check_conflict(updated,
                                          ignore_index=self.selected_lesson_index)
        if conflict:
            if not messagebox.askyesno("Conflict Detected",
                                        f"{conflict}\n\nUpdate anyway?"):
                return
        self.lessons[self.selected_lesson_index] = updated
        self._save_data()
        logger.info("Lesson updated title=%r day=%s by=%s",
                    updated.get('title'), updated.get('day'), self.user_display)
        if self.integrations:
            self.integrations.on_lesson_changed("updated", updated)
        self._refresh_views()
        self._clear_form()
        self._set_status(f"Updated lesson: {updated['title']}")

    def _delete_lesson(self):
        if self.selected_lesson_index is None:
            messagebox.showwarning("No Selection",
                                    "Please select a lesson to delete.")
            return
        lesson = self.lessons[self.selected_lesson_index]
        if messagebox.askyesno("Confirm Delete",
                                f"Delete '{lesson['title']}'?"):
            self.lessons.pop(self.selected_lesson_index)
            self._save_data()
            logger.info("Lesson deleted title=%r by=%s",
                        lesson.get('title'), self.user_display)
            if self.integrations:
                self.integrations.on_lesson_changed("deleted", lesson)
            self._refresh_views()
            self._clear_form()
            self._set_status(f"Deleted lesson: {lesson['title']}")

    def _clear_form(self):
        for var in self.form_vars.values():
            var.set("")
        self.notes_text.delete("1.0", "end")
        self.selected_lesson_index = None
        if self.lessons_tree.selection():
            self.lessons_tree.selection_remove(self.lessons_tree.selection())

    def _on_lesson_select(self, event):
        selection = self.lessons_tree.selection()
        if not selection:
            return
        item_id = selection[0]
        index = int(item_id)
        if index >= len(self.lessons):
            return
        self.selected_lesson_index = index
        lesson = self.lessons[index]

        self.form_vars["course_var"].set(lesson["course"])
        self.form_vars["title_var"].set(lesson["title"])
        self.form_vars["instructor_var"].set(lesson["instructor"])
        self.form_vars["type_var"].set(lesson["type"])
        self.form_vars["day_var"].set(lesson["day"])
        self.form_vars["start_var"].set(lesson["start"])
        self.form_vars["end_var"].set(lesson["end"])
        self.form_vars["room_var"].set(lesson["room"])
        self.notes_text.delete("1.0", "end")
        self.notes_text.insert("1.0", lesson.get("notes", ""))

    # ---------- Course Operations ----------

    def _add_course(self):
        code = self.course_vars["code"].get().strip()
        name = self.course_vars["name"].get().strip()
        if not code or not name:
            messagebox.showerror("Validation Error",
                                 "Course Code and Name are required.")
            return
        for course in self.courses:
            if course["code"] == code:
                messagebox.showerror("Duplicate",
                                     f"Course code '{code}' already exists.")
                return

        self.courses.append({
            "code": code,
            "name": name,
            "dept": self.course_vars["dept"].get(),
            "credits": self.course_vars["credits"].get(),
            "semester": self.course_vars["semester"].get(),
            "description": self.course_desc.get("1.0", "end-1c"),
            "_source": "local",
        })
        self._save_data()
        logger.info("Lesson-planner course added code=%s name=%r by=%s",
                    code, name, self.user_display)
        self._refresh_views()
        for var in self.course_vars.values():
            var.set("")
        self.course_desc.delete("1.0", "end")
        self._set_status(f"Added course: {code}")

    def _delete_course(self):
        selection = self.courses_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection",
                                    "Please select a course to delete.")
            return
        index = int(selection[0])
        course = self.courses[index]
        if course.get("_source") == "catalog":
            messagebox.showinfo(
                "Catalog Course",
                f"'{course['code']}' comes from the Academic Management "
                "course catalog and can't be removed from the planner.")
            return
        if messagebox.askyesno("Confirm Delete",
                                f"Delete course '{course['code']}'?"):
            self.courses.pop(index)
            self._save_data()
            logger.info("Lesson-planner course deleted code=%s by=%s",
                        course.get('code'), self.user_display)
            self._refresh_views()
            self._set_status(f"Deleted course: {course['code']}")

    # ---------- Refresh / Render ----------

    def _refresh_views(self):
        self._refresh_course_combo()
        self._refresh_lesson_list()
        self._refresh_course_list()
        self._refresh_schedule()

    def _refresh_course_combo(self):
        codes = [f"{c['code']} - {c['name']}" for c in self.courses]
        self.course_combo["values"] = codes

    def _refresh_lesson_list(self):
        for item in self.lessons_tree.get_children():
            self.lessons_tree.delete(item)

        search = self.search_var.get().lower() if hasattr(self, 'search_var') else ""
        for i, lesson in enumerate(self.lessons):
            if search and not any(search in str(v).lower()
                                   for v in lesson.values()):
                continue
            self.lessons_tree.insert("", "end", iid=str(i), values=(
                lesson["course"][:20],
                lesson["title"],
                lesson["type"],
                lesson["day"],
                f"{lesson['start']}–{lesson['end']}",
                lesson["room"],
                lesson["instructor"],
            ))

    def _refresh_course_list(self):
        for item in self.courses_tree.get_children():
            self.courses_tree.delete(item)
        for i, course in enumerate(self.courses):
            self.courses_tree.insert("", "end", iid=str(i), values=(
                course["code"], course["name"], course["dept"],
                course["credits"], course["semester"],
            ))

    def _refresh_schedule(self):
        self.schedule_canvas.delete("all")

        cell_w = 170
        cell_h = 45
        header_h = 40
        time_col_w = 70

        total_w = time_col_w + cell_w * len(self.DAYS)
        total_h = header_h + cell_h * len(self.TIME_SLOTS)

        # Header row (days)
        self.schedule_canvas.create_rectangle(0, 0, total_w, header_h,
                                                fill="#1e3a8a", outline="")
        for i, day in enumerate(self.DAYS):
            x = time_col_w + i * cell_w
            self.schedule_canvas.create_line(x, 0, x, total_h,
                                              fill="#cbd5e1")
            self.schedule_canvas.create_text(x + cell_w / 2, header_h / 2,
                                              text=day, fill="white",
                                              font=("Segoe UI", 10, "bold"))

        # Time column
        for i, time in enumerate(self.TIME_SLOTS):
            y = header_h + i * cell_h
            self.schedule_canvas.create_line(0, y, total_w, y,
                                              fill="#e2e8f0")
            self.schedule_canvas.create_text(time_col_w / 2, y + cell_h / 2,
                                              text=time,
                                              font=("Segoe UI", 9),
                                              fill="#475569")

        self.schedule_canvas.create_line(time_col_w, 0, time_col_w,
                                          total_h, fill="#94a3b8", width=2)

        # Plot lessons
        colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444",
                  "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16"]

        for idx, lesson in enumerate(self.lessons):
            try:
                day_idx = self.DAYS.index(lesson["day"])
                start_h = int(lesson["start"].split(":")[0])
                end_h = int(lesson["end"].split(":")[0])
                start_slot = start_h - 8
                end_slot = end_h - 8

                if start_slot < 0 or end_slot > len(self.TIME_SLOTS):
                    continue

                x1 = time_col_w + day_idx * cell_w + 3
                x2 = time_col_w + (day_idx + 1) * cell_w - 3
                y1 = header_h + start_slot * cell_h + 2
                y2 = header_h + end_slot * cell_h - 2

                color = colors[idx % len(colors)]
                self.schedule_canvas.create_rectangle(
                    x1, y1, x2, y2, fill=color, outline="white", width=2)

                text = f"{lesson['title']}\n{lesson['type']}\n📍 {lesson['room']}"
                self.schedule_canvas.create_text(
                    (x1 + x2) / 2, (y1 + y2) / 2,
                    text=text, fill="white",
                    font=("Segoe UI", 8, "bold"),
                    width=cell_w - 10)
            except (ValueError, IndexError):
                continue

        self.schedule_canvas.configure(scrollregion=(0, 0, total_w, total_h))

    # ---------- Export / Persistence ----------

    def _export_schedule(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile="schedule.txt")
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("UNIVERSITY LESSON SCHEDULE\n")
                f.write("=" * 60 + "\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")

                for day in self.DAYS:
                    day_lessons = sorted(
                        [l for l in self.lessons if l["day"] == day],
                        key=lambda x: x["start"])
                    if not day_lessons:
                        continue
                    f.write(f"\n{day.upper()}\n{'-' * 60}\n")
                    for lesson in day_lessons:
                        f.write(f"  {lesson['start']}–{lesson['end']}  "
                                f"{lesson['title']} ({lesson['type']})\n")
                        f.write(f"       Course: {lesson['course']}\n")
                        f.write(f"       Instructor: {lesson['instructor']}\n")
                        f.write(f"       Room: {lesson['room']}\n")
            messagebox.showinfo("Export Complete",
                                 f"Schedule exported to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    # ---------- Cross-system integration actions ----------

    def _selected_lesson(self):
        if self.selected_lesson_index is None:
            messagebox.showwarning("No Selection",
                                    "Please select a lesson first.")
            return None
        return self.lessons[self.selected_lesson_index]

    def _export_ics(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".ics",
            filetypes=[("iCalendar", "*.ics"), ("All files", "*.*")],
            initialfile="timetable.ics")
        if not path:
            return
        if self.integrations.export_schedule_ics(self.lessons, path):
            self._set_status("Exported timetable.ics")
            messagebox.showinfo("Export Complete",
                                 f"Calendar exported to:\n{path}")
        else:
            messagebox.showerror("Export Error",
                                 "Could not export the calendar file.")

    def _validate_hours(self):
        """Sum planned weekly contact hours per course and check each
        against the approved curriculum descriptor."""
        hours_by_course = {}
        for lesson in self.lessons:
            try:
                sh = int(lesson["start"].split(":")[0])
                eh = int(lesson["end"].split(":")[0])
            except (ValueError, KeyError, IndexError):
                continue
            code = (lesson.get("course", "").split(" - ", 1)[0].strip()
                    or lesson.get("course", "").strip())
            hours_by_course[code] = hours_by_course.get(code, 0) + max(0, eh - sh)

        if not hours_by_course:
            messagebox.showinfo("Validate Hours", "No lessons to validate.")
            return

        lines = []
        for code, planned in sorted(hours_by_course.items()):
            verdict = self.integrations.validate_contact_hours(code, planned)
            if not verdict.get("known"):
                lines.append(f"• {code}: {planned}h planned — no curriculum record")
            elif verdict.get("ok"):
                lines.append(f"✓ {code}: {planned}h planned ≤ "
                             f"{verdict['approved_contact_hours']}h approved")
            else:
                lines.append(f"✗ {code}: {planned}h planned EXCEEDS "
                             f"{verdict['approved_contact_hours']}h approved")
        messagebox.showinfo("Curriculum Contact-Hour Check", "\n".join(lines))

    def _lock_timetable(self):
        if not self.integrations.can("lock_timetable", min_role="staff"):
            messagebox.showwarning(
                "Not Permitted",
                "You need staff-level access to lock the timetable.")
            return
        if not messagebox.askyesno(
                "Lock Timetable",
                "Publish a timetable-locked event for the current schedule?"):
            return
        uid = self.user.get("user_id") or self.user.get("id")
        ok = self.integrations.publish_timetable_locked(
            [uid] if uid else [])
        if ok:
            self.integrations.audit("timetable.locked",
                                    details={"lessons": len(self.lessons)})
            self._set_status("Timetable locked & published")
            messagebox.showinfo("Timetable Locked",
                                 "Timetable-locked event published.")
        else:
            messagebox.showerror("Lock Failed",
                                 "Could not publish the lock event.")

    def _reserve_room_for_selected(self):
        lesson = self._selected_lesson()
        if not lesson:
            return
        rooms = self.integrations.find_available_rooms(lesson)
        if not rooms:
            messagebox.showinfo(
                "No Rooms",
                "No available rooms found for this slot (or room booking "
                "is unavailable).")
            return
        self._open_room_chooser(lesson, rooms)

    def _open_room_chooser(self, lesson, rooms):
        win = tk.Toplevel(self.root)
        win.title("Available Rooms")
        win.geometry("420x320")
        win.transient(self.root)
        ttk.Label(win, text=f"Rooms free for {lesson['day']} "
                            f"{lesson['start']}–{lesson['end']}:",
                  padding=8).pack(anchor="w")
        listbox = tk.Listbox(win, height=12)
        listbox.pack(fill="both", expand=True, padx=8)
        for room in rooms:
            label = (f"{room.get('room_number', room.get('room_id'))} "
                     f"{room.get('room_name', '')} "
                     f"(cap {room.get('capacity', '?')})").strip()
            listbox.insert("end", label)

        def _do_reserve():
            sel = listbox.curselection()
            if not sel:
                messagebox.showwarning("No Selection",
                                        "Pick a room to reserve.", parent=win)
                return
            room = rooms[sel[0]]
            booking_id = self.integrations.reserve_room(
                lesson, room.get("room_id"))
            if booking_id:
                lesson["room"] = (room.get("room_number")
                                  or room.get("room_name") or lesson["room"])
                self._save_data()
                self._refresh_views()
                self._set_status(f"Reserved room (booking #{booking_id})")
                messagebox.showinfo("Room Reserved",
                                     f"Booking #{booking_id} created.",
                                     parent=win)
                win.destroy()
            else:
                messagebox.showerror(
                    "Reservation Failed",
                    "The room could not be reserved (it may now clash).",
                    parent=win)

        btns = tk.Frame(win)
        btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="Reserve", command=_do_reserve,
                   style="Accent.TButton").pack(side="left", padx=8)
        ttk.Button(btns, text="Cancel",
                   command=win.destroy).pack(side="left")

    def _make_attendance_session(self):
        lesson = self._selected_lesson()
        if not lesson:
            return
        session_id = self.integrations.create_attendance_session(lesson)
        if session_id:
            self._set_status(f"Attendance session {session_id}")
            messagebox.showinfo(
                "Attendance Session",
                f"Created/linked attendance session:\n{session_id}")
        else:
            messagebox.showinfo(
                "Attendance Session",
                "No session created — the course needs a populated "
                "module_schedule slot for this weekday.")

    def _connect(self):
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        return get_connection()

    def _ensure_schema(self):
        conn = self._connect()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS lesson_plans (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    course      TEXT,
                    title       TEXT,
                    instructor  TEXT,
                    type        TEXT,
                    day         TEXT,
                    start       TEXT,
                    end         TEXT,
                    room        TEXT,
                    notes       TEXT,
                    updated_at  TEXT,
                    updated_by  TEXT
                );
                CREATE TABLE IF NOT EXISTS lesson_courses (
                    code        TEXT PRIMARY KEY,
                    name        TEXT,
                    dept        TEXT,
                    credits     TEXT,
                    semester    TEXT,
                    description TEXT,
                    updated_at  TEXT,
                    updated_by  TEXT
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def _save_data(self):
        """Persist the in-memory lessons + courses lists back to the
        central DB. DELETE-all + bulk INSERT inside one transaction
        keeps this in step with the GUI's list-mutation semantics
        (append/replace/pop)."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        actor = getattr(self, 'user_display', '') or ''
        conn = self._connect()
        try:
            conn.execute("BEGIN")
            conn.execute("DELETE FROM lesson_plans")
            for lesson in self.lessons:
                conn.execute(
                    "INSERT INTO lesson_plans (course, title, instructor, type, "
                    "day, start, end, room, notes, updated_at, updated_by) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    tuple(lesson.get(k, "") for k in _LESSON_FIELDS) +
                    (now, actor),
                )
            conn.execute("DELETE FROM lesson_courses")
            # Only planner-local courses live in lesson_courses; courses
            # sourced from the canonical catalog are not copied back.
            for course in self.courses:
                if course.get("_source") == "catalog":
                    continue
                conn.execute(
                    "INSERT INTO lesson_courses (code, name, dept, credits, "
                    "semester, description, updated_at, updated_by) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    tuple(course.get(k, "") for k in _COURSE_FIELDS) +
                    (now, actor),
                )
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            logger.exception("Failed to save lesson planner data")
            messagebox.showerror("Save Error", str(e))
        finally:
            conn.close()

    def _load_canonical_courses(self):
        """Read the canonical Academic-Management ``courses`` catalog so the
        planner's course dropdown and Course Catalog reflect the real
        university courses, not just planner-local additions. Read-only;
        tags each row source='catalog'. A missing table or columns degrades
        to an empty list rather than breaking the planner."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT "
                "  COALESCE(NULLIF(course_code, ''), code) AS code, "
                "  COALESCE(NULLIF(course_name, ''), name) AS name, "
                "  COALESCE(department, '') AS dept, "
                "  COALESCE(credit_hours, credits, '') AS credits, "
                "  COALESCE(NULLIF(availability_periods, ''), '') AS semester, "
                "  COALESCE(description, '') AS description "
                "FROM courses "
                "WHERE COALESCE(NULLIF(course_code, ''), code) IS NOT NULL "
                "ORDER BY code"
            ).fetchall()
        except sqlite3.Error:
            logger.debug("Canonical courses catalog unavailable", exc_info=True)
            return []
        finally:
            conn.close()

        catalog = []
        for r in rows:
            course = dict(zip(_COURSE_FIELDS, r))
            course["_source"] = "catalog"
            # credits/credit_hours can come back as ints — render as text
            course["credits"] = "" if course["credits"] is None else str(course["credits"])
            catalog.append(course)
        return catalog

    def _load_data(self):
        conn = self._connect()
        try:
            lessons = conn.execute(
                "SELECT course, title, instructor, type, day, start, end, room, notes "
                "FROM lesson_plans ORDER BY day, start"
            ).fetchall()
            courses = conn.execute(
                "SELECT code, name, dept, credits, semester, description "
                "FROM lesson_courses ORDER BY code"
            ).fetchall()
        finally:
            conn.close()

        self.lessons = [dict(zip(_LESSON_FIELDS, r)) for r in lessons]
        local_courses = []
        for r in courses:
            course = dict(zip(_COURSE_FIELDS, r))
            course["_source"] = "local"
            local_courses.append(course)

        # The canonical `courses` catalog is the source of truth for the
        # dropdown/catalog; planner-local rows (added via the Courses tab)
        # supplement it. Dedupe by code — canonical wins.
        merged = self._load_canonical_courses()
        seen = {c["code"] for c in merged}
        for c in local_courses:
            if c["code"] not in seen:
                merged.append(c)
                seen.add(c["code"])
        self.courses = merged

    def _set_status(self, message):
        self.status_label.config(text=message)
        self.root.after(4000, lambda: self.status_label.config(text=""))


def main():
    _remove_legacy_files()
    root = tk.Tk()
    LessonPlannerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
