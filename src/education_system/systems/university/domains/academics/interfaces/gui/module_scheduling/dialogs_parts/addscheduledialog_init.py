"""Methods __init__ through update_conflict_text."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import dialogs_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AddScheduleDialog:
    def __init__(self, parent, scheduler, gui=None):
        self.parent = parent
        self.scheduler = scheduler
        self.gui = gui
        self.result = False

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.windows.add_new_schedule', default="Add New Schedule"))
        self.dialog.geometry("550x700")
        self.dialog.transient(parent)

        self.create_widgets()
        self.center_window()

        # Set grab after window is fully initialized and visible
        self.dialog.update_idletasks()  # Ensure window is ready
        try:
            self.dialog.grab_set()
        except tk.TclError:
            # If grab fails, continue without it - dialog will still work
            pass

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Course selection. Scoping the module list by course turns a flat
        # list of ~380 module codes into the handful that belong to the course
        # being scheduled.
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.labels.course', default="Course:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.course_var = tk.StringVar()
        self.course_combo = ttk.Combobox(main_frame, textvariable=self.course_var,
                                         width=30, state="readonly")
        self.course_combo.grid(row=0, column=1, pady=5, sticky=tk.W)
        self.course_combo.bind('<<ComboboxSelected>>', self.on_course_selected)

        # Module selection
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.labels.module_code', default="Module Code:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.module_var = tk.StringVar()
        self.module_combo = ttk.Combobox(main_frame, textvariable=self.module_var, width=30)
        self.module_combo.grid(row=1, column=1, pady=5, sticky=tk.W)

        self.load_courses()
        self.on_course_selected()

        # Day of week
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.labels.day_of_week', default="Day of Week:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.day_var = tk.StringVar()
        day_combo = ttk.Combobox(main_frame, textvariable=self.day_var, values=DAYS_OF_WEEK, width=30)
        day_combo.grid(row=2, column=1, pady=5, sticky=tk.W)

        # Time
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.labels.start_time', default="Start Time:")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.start_time_var = tk.StringVar()
        start_combo = ttk.Combobox(main_frame, textvariable=self.start_time_var, values=TIME_SLOTS, width=30)
        start_combo.grid(row=3, column=1, pady=5, sticky=tk.W)

        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.labels.end_time', default="End Time:")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.end_time_var = tk.StringVar()
        end_combo = ttk.Combobox(main_frame, textvariable=self.end_time_var, values=TIME_SLOTS, width=30)
        end_combo.grid(row=4, column=1, pady=5, sticky=tk.W)

        # Building selection
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.labels.building', default="Building:")).grid(row=5, column=0, sticky=tk.W, pady=5)
        self.building_var = tk.StringVar()
        self.building_combo = ttk.Combobox(main_frame, textvariable=self.building_var, width=30)

        # Load buildings from database
        buildings = self.get_buildings_from_db()
        self.building_combo['values'] = buildings
        self.building_combo.grid(row=5, column=1, pady=5, sticky=tk.W)

        # Bind building selection to update rooms
        self.building_combo.bind('<<ComboboxSelected>>', self.on_building_selected)

        # Room
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.labels.room', default="Room:")).grid(row=6, column=0, sticky=tk.W, pady=5)
        self.room_var = tk.StringVar()
        self.room_combo = ttk.Combobox(main_frame, textvariable=self.room_var, width=30)
        self.room_combo.grid(row=6, column=1, pady=5, sticky=tk.W)

        # Store all rooms for filtering. on_building_selected is what fills
        # the combo, and it only ran on a building change — so the Room box
        # opened empty even with rooms in the database. Call it once here so
        # every room is offered until a building narrows the list.
        self.all_rooms = []
        self.load_all_rooms()
        self.on_building_selected()

        # Instructor
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.labels.instructor', default="Instructor:")).grid(row=7, column=0, sticky=tk.W, pady=5)
        self.instructor_var = tk.StringVar()
        instructor_combo = ttk.Combobox(main_frame, textvariable=self.instructor_var, width=30)

        # Load instructors
        try:
            from education_system.systems.university.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, first_name, last_name FROM instructors WHERE CASE WHEN status = 'Active' THEN 1 ELSE COALESCE(is_active, 1) END = 1")
                instructors = cursor.fetchall()

            instructor_values = [f"{inst[0]} - {inst[1]} {inst[2]}" for inst in instructors]
            instructor_combo['values'] = instructor_values
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        instructor_combo.grid(row=6, column=1, pady=5, sticky=tk.W)

        # Session type
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.labels.session_type', default="Session Type:")).grid(row=7, column=0, sticky=tk.W, pady=5)
        self.session_type_var = tk.StringVar()
        session_combo = ttk.Combobox(main_frame, textvariable=self.session_type_var, values=SESSION_TYPES, width=30)
        session_combo.grid(row=7, column=1, pady=5, sticky=tk.W)

        # --- New: Term (Semester + Year) ---
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.labels.term', default="Term:")).grid(row=8, column=0, sticky=tk.W, pady=5)
        term_frame = ttk.Frame(main_frame)
        term_frame.grid(row=8, column=1, pady=5, sticky=tk.W)
        # Default to current calendar inference (matches the service layer).
        _now = datetime.now()
        default_semester = "Spring" if _now.month <= 5 else ("Summer" if _now.month <= 7 else "Fall")
        self.semester_var = tk.StringVar(value=default_semester)
        ttk.Combobox(term_frame, textvariable=self.semester_var,
                     values=["Fall", "Spring", "Summer", "Winter"],
                     width=10, state="readonly").pack(side=tk.LEFT)
        self.year_var = tk.StringVar(value=str(_now.year))
        ttk.Spinbox(term_frame, from_=_now.year - 1, to=_now.year + 5,
                    textvariable=self.year_var, width=6).pack(side=tk.LEFT, padx=(8, 0))

        # --- New: Status (Draft / Publish) ---
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.labels.status', default="Status:")).grid(row=9, column=0, sticky=tk.W, pady=5)
        self.status_var = tk.StringVar(value=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.values.published', default="published"))
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=9, column=1, pady=5, sticky=tk.W)
        ttk.Radiobutton(status_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.buttons.publish', default="Publish"), variable=self.status_var,
                        value="published").pack(side=tk.LEFT)
        ttk.Radiobutton(status_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.buttons.save_as_draft', default="Save as draft"), variable=self.status_var,
                        value="draft").pack(side=tk.LEFT, padx=(10, 0))

        # --- New: Recurrence ---
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.labels.recurrence', default="Recurrence:")).grid(row=10, column=0, sticky=tk.W, pady=5)
        rec_frame = ttk.Frame(main_frame)
        rec_frame.grid(row=10, column=1, pady=5, sticky=tk.W)
        self.recurrence_var = tk.StringVar(value=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.values.weekly', default="weekly"))
        ttk.Combobox(rec_frame, textvariable=self.recurrence_var,
                     values=["none", "weekly", "biweekly"], width=10,
                     state="readonly").pack(side=tk.LEFT)
        ttk.Label(rec_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.labels.until', default=" until ")).pack(side=tk.LEFT)
        # End-date picker. Use plain Entry — the codebase doesn't bring a
        # date-picker widget, and YYYY-MM-DD is what the service expects.
        self.recurrence_until_var = tk.StringVar()
        ttk.Entry(rec_frame, textvariable=self.recurrence_until_var,
                  width=12).pack(side=tk.LEFT)
        ttk.Label(rec_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.labels.yyyy_mm_dd_blank_open_ended', default=" (YYYY-MM-DD, blank = open-ended)"),
                  font=("Arial", 8), foreground="#666").pack(side=tk.LEFT)

        # Conflict notification area
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.labels.conflicts_warnings', default="Conflicts/Warnings:")).grid(row=11, column=0, sticky=tk.NW, pady=5)
        self.conflict_text = tk.Text(main_frame, width=30, height=4, state='disabled', bg='#f0f0f0')
        self.conflict_text.grid(row=11, column=1, pady=5, sticky=tk.W)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=12, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.buttons.check_conflicts', default="Check Conflicts"), command=self.check_conflicts).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.buttons.suggest_free_rooms', default="Suggest Free Rooms"),
                   command=self._suggest_free_rooms).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.buttons.save', default="Save"), command=self.save_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _suggest_free_rooms(self):
        """Pop a list of rooms free for the current day/start/end (#9).

        Routes through the shared ``find_free_rooms`` helper so Module
        Scheduling, Exam, and the chatbot all use the same algorithm.
        """
        try:
            day = self.day_var.get()
            start = self.start_time_var.get()
            end = self.end_time_var.get()
        except Exception:
            return
        if not all([day, start, end]):
            messagebox.showwarning(
                _t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.dialogs.missing_fields', default="Missing fields"),
                _t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.dialogs.pick_a_day_start_time_and_end_time_first', default="Pick a day, start time, and end time first."),
                parent=self.dialog,
            )
            return
        try:
            from education_system.systems.university.domains.academics.interfaces.gui._cross_services import (
                find_free_rooms,
            )
            rows = find_free_rooms(
                day_of_week=day, start_time=start, end_time=end,
            )
        except Exception as exc:
            messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.dialogs.error', default="Error"), f"Could not query rooms: {exc}",
                                 parent=self.dialog)
            return

        win = tk.Toplevel(self.dialog)
        win.title(f"Free rooms — {day} {start}–{end}")
        win.geometry("520x360")
        win.transient(self.dialog)

        if not rows:
            ttk.Label(win, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.labels.no_rooms_free_in_that_window', default="No rooms free in that window."),
                      foreground="#7f8c8d").pack(padx=15, pady=20)
        else:
            cols = ("name", "building", "capacity")
            tree = ttk.Treeview(win, columns=cols, show="headings", height=12)
            for c, w in zip(cols, (140, 160, 100)):
                tree.heading(c, text=c.capitalize())
                tree.column(c, width=w, anchor="w")
            tree.pack(fill="both", expand=True, padx=10, pady=10)
            for r in sorted(rows, key=lambda x: -(x.get("capacity") or 0)):
                tree.insert("", "end", values=(
                    r.get("name", ""), r.get("building", ""),
                    r.get("capacity", 0),
                ))

            def _pick():
                sel = tree.selection()
                if not sel:
                    return
                vals = tree.item(sel[0], "values")
                if vals and self.room_var is not None:
                    try:
                        self.room_var.set(vals[0])
                    except Exception:
                        logger.debug("Suppressed exception", exc_info=True)
                win.destroy()

            ttk.Button(win, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.buttons.use_selected_room', default="Use selected room"),
                       command=_pick).pack(pady=8)
        ttk.Button(win, text=_t('gui.academics.module_scheduling.dialogs_parts.addscheduledialog_init.buttons.close', default="Close"), command=win.destroy).pack(pady=(0, 10))

    def get_buildings_from_db(self):
        """Fetch list of buildings from facilities management database"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Check if buildings table exists
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='buildings'
                """)

                if cursor.fetchone():
                    # Get all building names
                    cursor.execute("""
                        SELECT DISTINCT building_name FROM buildings
                        ORDER BY building_name
                    """)
                    buildings = [row[0] for row in cursor.fetchall()]

                    if buildings:
                        return buildings

                # Fallback: Get buildings from rooms table
                cursor.execute("""
                    SELECT DISTINCT building FROM rooms
                    WHERE building IS NOT NULL AND building != ''
                    ORDER BY building
                """)
                buildings = [row[0] for row in cursor.fetchall()]

                if not buildings:
                    return ["Main Building", "Science Building", "Library"]

                return buildings

        except Exception as e:
            print(f"Error fetching buildings: {e}")
            return ["Main Building", "Science Building", "Library"]

    def load_courses(self):
        """Fill the course dropdown from the courses table."""
        self._course_codes = []
        values = []
        try:
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                rows = conn.execute(
                    "SELECT COALESCE(NULLIF(TRIM(course_code), ''), code), "
                    "       COALESCE(NULLIF(TRIM(course_name), ''), name) "
                    "  FROM courses "
                    " WHERE COALESCE(NULLIF(TRIM(course_code), ''), code) IS NOT NULL "
                    " ORDER BY 1").fetchall()
            for code, name in rows:
                self._course_codes.append(code)
                values.append(f"{code} - {name}" if name else code)
        except Exception as exc:
            print(f"Error loading courses: {exc}")
        # "All courses" keeps every module reachable for anything unmapped.
        self.course_combo['values'] = ["(all courses)"] + values
        self.course_combo.current(0)

    def on_course_selected(self, event=None):
        """Scope the module dropdown to the selected course."""
        selection = self.course_var.get()
        course_code = None
        if selection and selection != "(all courses)":
            course_code = selection.split(" - ", 1)[0].strip()

        modules = []
        try:
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                if course_code:
                    rows = conn.execute(
                        "SELECT module_code, module_name FROM modules "
                        " WHERE COALESCE(TRIM(module_code), '') <> '' "
                        "   AND TRIM(COALESCE(course, '')) = ? "
                        " ORDER BY module_code", (course_code,)).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT module_code, module_name FROM modules "
                        " WHERE COALESCE(TRIM(module_code), '') <> '' "
                        " ORDER BY module_code").fetchall()
            modules = [f"{code} - {name}" if name else code for code, name in rows]
        except Exception as exc:
            print(f"Error loading modules: {exc}")

        if not modules and course_code:
            # A course with no modules mapped would otherwise leave the box
            # empty with no reason given.
            modules = []
        self.module_combo['values'] = modules
        if self.module_var.get() not in modules:
            self.module_var.set("")

    def load_all_rooms(self):
        """Load all rooms from database"""
        try:
            from education_system.systems.university.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id, building, room_number, capacity, room_type FROM rooms WHERE is_active = 1 ORDER BY building, room_number')
                self.all_rooms = cursor.fetchall()

        except Exception as e:
            print(f"Error loading rooms: {e}")
            self.all_rooms = []

    def on_building_selected(self, event=None):
        """Filter rooms by selected building"""
        selected_building = self.building_var.get()

        if not selected_building:
            # No building selected, show all rooms
            filtered_rooms = self.all_rooms
        else:
            # Filter rooms by building
            filtered_rooms = [room for room in self.all_rooms if room[1] == selected_building]

        # Update room combobox
        room_values = [f"{room[0]} - {room[1]}-{room[2]} (Cap: {room[3]}, {room[4]})" for room in filtered_rooms]
        self.room_combo['values'] = room_values

        # Clear current selection if not in filtered list
        if self.room_var.get() and not any(str(room[0]) in self.room_var.get() for room in filtered_rooms):
            self.room_var.set('')

    def check_conflicts(self):
        """Check for scheduling conflicts and display in textbox"""
        try:
            day = self.day_var.get()
            start_time = self.start_time_var.get()
            end_time = self.end_time_var.get()
            room_str = self.room_var.get()
            instructor_str = self.instructor_var.get()

            if not all([day, start_time, end_time, room_str, instructor_str]):
                self.update_conflict_text("Please fill in all fields to check conflicts.")
                return

            # Extract IDs
            room_id = int(room_str.split(' - ')[0])
            instructor_id = int(instructor_str.split(' - ')[0])

            conflicts = []

            # Check room conflicts
            from education_system.systems.university.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()

                # Check if room is already booked for this time slot
                cursor.execute('''
                    SELECT module_code, start_time, end_time
                    FROM module_schedule
                    WHERE room_id = ? AND day_of_week = ?
                    AND ((start_time < ? AND end_time > ?) OR (start_time < ? AND end_time > ?))
                ''', (room_id, day, end_time, start_time, end_time, end_time))

                room_conflicts = cursor.fetchall()
                if room_conflicts:
                    conflicts.append("ROOM CONFLICTS:")
                    for conflict in room_conflicts:
                        conflicts.append(f"  • {conflict[0]} ({conflict[1]}-{conflict[2]})")

                # Check instructor conflicts
                cursor.execute('''
                    SELECT module_code, start_time, end_time
                    FROM module_schedule
                    WHERE instructor_id = ? AND day_of_week = ?
                    AND ((start_time < ? AND end_time > ?) OR (start_time < ? AND end_time > ?))
                ''', (instructor_id, day, end_time, start_time, end_time, end_time))

                instructor_conflicts = cursor.fetchall()
                if instructor_conflicts:
                    if conflicts:
                        conflicts.append("")
                    conflicts.append("INSTRUCTOR CONFLICTS:")
                    for conflict in instructor_conflicts:
                        conflicts.append(f"  • {conflict[0]} ({conflict[1]}-{conflict[2]})")

            if conflicts:
                self.update_conflict_text("\n".join(conflicts))
            else:
                self.update_conflict_text("✓ No conflicts found. Room and instructor are available.")

        except Exception as e:
            self.update_conflict_text(f"Error checking conflicts: {str(e)}")

    def update_conflict_text(self, message):
        """Update the conflict text widget"""
        self.conflict_text.config(state='normal')
        self.conflict_text.delete(1.0, tk.END)
        self.conflict_text.insert(1.0, message)
        self.conflict_text.config(state='disabled')
