"""Extracted class implementation."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import dialogs_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class EditScheduleDialog:
    def __init__(self, parent, scheduler, schedule_id, gui=None):
        self.parent = parent
        self.scheduler = scheduler
        self.gui = gui
        self.schedule_id = schedule_id
        self.result = False

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.windows.edit_schedule', default="Edit Schedule"))
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)

        self.load_current_data()
        self.create_widgets()
        self.center_window()

        # Set grab after window is fully initialized and visible
        self.dialog.update_idletasks()  # Ensure window is ready
        try:
            self.dialog.grab_set()
        except tk.TclError:
            # If grab fails, continue without it - dialog will still work
            pass

    def load_current_data(self):
        """Load current schedule data"""
        try:
            from education_system.systems.university.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()

                # PRAGMA-driven so the dialog tolerates the schema before
                # the migration has run on a stale DB (e.g. test fixtures).
                cursor.execute("PRAGMA table_info(module_schedule)")
                cols = {row[1] for row in cursor.fetchall()}
                want = ["module_code", "day_of_week", "start_time", "end_time",
                        "room_id", "instructor_id", "session_type",
                        "semester", "year", "status", "recurrence",
                        "recurrence_until"]
                select_cols = [c if c in cols else f"NULL AS {c}" for c in want]
                # db-audit: ignore[DBW001] - join over a code-controlled list
                cursor.execute(
                    f"SELECT {', '.join(select_cols)} FROM module_schedule WHERE id = ?",
                    (self.schedule_id,),
                )
                schedule = cursor.fetchone()

            if schedule:
                self.current_data = dict(zip(want, schedule))
            else:
                raise CourseNotFoundError(f"Schedule {self.schedule_id}")

        except (CourseNotFoundError, sqlite3.Error) as e:
            messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.dialogs.error', default="Error"), f"Failed to load schedule data: {str(e)}", parent=self.dialog)
            self.dialog.destroy()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Module selection
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.labels.module_code', default="Module Code:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.module_var = tk.StringVar(value=self.current_data['module_code'])
        module_combo = ttk.Combobox(main_frame, textvariable=self.module_var, width=30)

        # Load modules
        try:
            modules = self.scheduler._get_known_modules()
            module_combo['values'] = list(modules.keys())
        except (AttributeError, Exception):
            pass

        module_combo.grid(row=0, column=1, pady=5, sticky=tk.W)

        # Day of week
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.labels.day_of_week', default="Day of Week:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.day_var = tk.StringVar(value=self.current_data['day_of_week'])
        day_combo = ttk.Combobox(main_frame, textvariable=self.day_var, values=DAYS_OF_WEEK, width=30)
        day_combo.grid(row=1, column=1, pady=5, sticky=tk.W)

        # Time
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.labels.start_time', default="Start Time:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.start_time_var = tk.StringVar(value=self.current_data['start_time'])
        start_combo = ttk.Combobox(main_frame, textvariable=self.start_time_var, values=TIME_SLOTS, width=30)
        start_combo.grid(row=2, column=1, pady=5, sticky=tk.W)

        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.labels.end_time', default="End Time:")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.end_time_var = tk.StringVar(value=self.current_data['end_time'])
        end_combo = ttk.Combobox(main_frame, textvariable=self.end_time_var, values=TIME_SLOTS, width=30)
        end_combo.grid(row=3, column=1, pady=5, sticky=tk.W)

        # Room
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.labels.room', default="Room:")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.room_var = tk.StringVar()
        room_combo = ttk.Combobox(main_frame, textvariable=self.room_var, width=30)

        # Load rooms and set current
        try:
            from education_system.systems.university.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id, building, room_number FROM rooms WHERE is_active = 1')
                rooms = cursor.fetchall()

            room_values = [f"{room[0]} - {room[1]}-{room[2]}" for room in rooms]
            room_combo['values'] = room_values

            # Set current room
            for room in rooms:
                if room[0] == self.current_data['room_id']:
                    self.room_var.set(f"{room[0]} - {room[1]}-{room[2]}")
                    break
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        room_combo.grid(row=4, column=1, pady=5, sticky=tk.W)

        # Instructor
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.labels.instructor', default="Instructor:")).grid(row=5, column=0, sticky=tk.W, pady=5)
        self.instructor_var = tk.StringVar()
        instructor_combo = ttk.Combobox(main_frame, textvariable=self.instructor_var, width=30)

        # Load instructors and set current
        try:
            from education_system.systems.university.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, first_name, last_name FROM instructors WHERE CASE WHEN status = 'Active' THEN 1 ELSE COALESCE(is_active, 1) END = 1")
                instructors = cursor.fetchall()

            instructor_values = [f"{inst[0]} - {inst[1]} {inst[2]}" for inst in instructors]
            instructor_combo['values'] = instructor_values

            # Set current instructor
            for inst in instructors:
                if inst[0] == self.current_data['instructor_id']:
                    self.instructor_var.set(f"{inst[0]} - {inst[1]} {inst[2]}")
                    break
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        instructor_combo.grid(row=5, column=1, pady=5, sticky=tk.W)

        # Session type
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.labels.session_type', default="Session Type:")).grid(row=6, column=0, sticky=tk.W, pady=5)
        self.session_type_var = tk.StringVar(value=self.current_data['session_type'])
        session_combo = ttk.Combobox(main_frame, textvariable=self.session_type_var, values=SESSION_TYPES, width=30)
        session_combo.grid(row=6, column=1, pady=5, sticky=tk.W)

        # --- New: Term ---
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.labels.term', default="Term:")).grid(row=7, column=0, sticky=tk.W, pady=5)
        term_frame = ttk.Frame(main_frame)
        term_frame.grid(row=7, column=1, pady=5, sticky=tk.W)
        self.semester_var = tk.StringVar(value=self.current_data.get('semester') or 'Fall')
        ttk.Combobox(term_frame, textvariable=self.semester_var,
                     values=["Fall", "Spring", "Summer", "Winter"],
                     width=10, state="readonly").pack(side=tk.LEFT)
        year_default = self.current_data.get('year') or datetime.now().year
        try:
            year_default = int(year_default) if year_default else datetime.now().year
        except (TypeError, ValueError):
            year_default = datetime.now().year
        if year_default <= 0:
            year_default = datetime.now().year
        self.year_var = tk.StringVar(value=str(year_default))
        ttk.Spinbox(term_frame, from_=year_default - 5, to=year_default + 5,
                    textvariable=self.year_var, width=6).pack(side=tk.LEFT, padx=(8, 0))

        # --- New: Status ---
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.labels.status', default="Status:")).grid(row=8, column=0, sticky=tk.W, pady=5)
        self.status_var = tk.StringVar(value=self.current_data.get('status') or 'published')
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=8, column=1, pady=5, sticky=tk.W)
        for label, value in (("Published", "published"),
                             ("Draft", "draft"),
                             ("Archived", "archived")):
            ttk.Radiobutton(status_frame, text=label, variable=self.status_var,
                            value=value).pack(side=tk.LEFT, padx=(0, 8))

        # --- New: Recurrence ---
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.labels.recurrence', default="Recurrence:")).grid(row=9, column=0, sticky=tk.W, pady=5)
        rec_frame = ttk.Frame(main_frame)
        rec_frame.grid(row=9, column=1, pady=5, sticky=tk.W)
        self.recurrence_var = tk.StringVar(value=self.current_data.get('recurrence') or 'weekly')
        ttk.Combobox(rec_frame, textvariable=self.recurrence_var,
                     values=["none", "weekly", "biweekly"], width=10,
                     state="readonly").pack(side=tk.LEFT)
        ttk.Label(rec_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.labels.until', default=" until ")).pack(side=tk.LEFT)
        self.recurrence_until_var = tk.StringVar(
            value=self.current_data.get('recurrence_until') or '')
        ttk.Entry(rec_frame, textvariable=self.recurrence_until_var,
                  width=12).pack(side=tk.LEFT)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=10, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.buttons.view_history', default="View History"),
                   command=self._show_history).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.buttons.update', default="Update"), command=self.update_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _show_history(self):
        """Open the read-only schedule_history viewer for this row."""
        try:
            from education_system.systems.university.domains.academics.interfaces.gui.module_scheduling.history_dialog import ScheduleHistoryDialog
            ScheduleHistoryDialog(self.dialog, self.schedule_id)
        except Exception as e:
            messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.dialogs.error', default="Error"),
                                 f"Failed to open history viewer: {e}",
                                 parent=self.dialog)

    def update_schedule(self):
        try:
            # Get new values
            updates = {}

            if self.day_var.get() != self.current_data['day_of_week']:
                updates['day_of_week'] = self.day_var.get()

            if self.start_time_var.get() != self.current_data['start_time']:
                updates['start_time'] = self.start_time_var.get()

            if self.end_time_var.get() != self.current_data['end_time']:
                updates['end_time'] = self.end_time_var.get()

            room_str = self.room_var.get()
            if room_str:
                room_id = int(room_str.split(' - ')[0])
                if room_id != self.current_data['room_id']:
                    updates['room_id'] = room_id

            instructor_str = self.instructor_var.get()
            if instructor_str:
                instructor_id = int(instructor_str.split(' - ')[0])
                if instructor_id != self.current_data['instructor_id']:
                    updates['instructor_id'] = instructor_id

            if self.session_type_var.get() != self.current_data['session_type']:
                updates['session_type'] = self.session_type_var.get()

            # New fields — only push when the user actually changed them.
            cur_sem = self.current_data.get('semester') or 'Fall'
            if self.semester_var.get() != cur_sem:
                updates['semester'] = self.semester_var.get()
            try:
                year_int = int(self.year_var.get())
            except (TypeError, ValueError):
                messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.dialogs.error', default="Error"), _t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.dialogs.year_must_be_a_whole_number', default="Year must be a whole number."),
                                     parent=self.dialog)
                return
            cur_year = self.current_data.get('year') or 0
            if year_int != cur_year:
                updates['year'] = year_int
            cur_status = self.current_data.get('status') or 'published'
            if self.status_var.get() != cur_status:
                updates['status'] = self.status_var.get()
            cur_rec = self.current_data.get('recurrence') or 'weekly'
            if self.recurrence_var.get() != cur_rec:
                updates['recurrence'] = self.recurrence_var.get()
            new_rec_until = (self.recurrence_until_var.get() or '').strip() or None
            if new_rec_until:
                try:
                    datetime.strptime(new_rec_until, "%Y-%m-%d")
                except ValueError:
                    messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.dialogs.error', default="Error"),
                                         _t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.dialogs.recurrence_end_date_must_be_yyyy_mm_dd_or_blank', default="Recurrence end date must be YYYY-MM-DD or blank."),
                                         parent=self.dialog)
                    return
            cur_rec_until = self.current_data.get('recurrence_until') or None
            if new_rec_until != cur_rec_until:
                updates['recurrence_until'] = new_rec_until

            if not updates:
                messagebox.showinfo(_t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.dialogs.info', default="Info"), _t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.dialogs.no_changes_detected', default="No changes detected."), parent=self.dialog)
                return

            # Resolve calling user for the schedule_history audit row.
            changed_by = "gui"
            try:
                if self.gui and hasattr(self.gui, "auth") and self.gui.auth:
                    user = getattr(self.gui.auth, "current_user", None)
                    if isinstance(user, dict):
                        changed_by = str(user.get("username") or user.get("user_id") or "gui")
                    elif user and hasattr(user, "username"):
                        changed_by = str(user.username)
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
            updates['changed_by'] = changed_by

            # Update schedule
            success = self.scheduler.update_module_schedule(self.schedule_id, **updates)

            if success:
                # Send notifications about schedule changes to instructor and students
                try:
                    with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                        cursor = conn.cursor()

                        # Get schedule details
                        cursor.execute('''
                            SELECT ms.module_code, ms.instructor_id
                            FROM module_schedule ms
                            WHERE ms.id = ?
                        ''', (self.schedule_id,))
                        schedule = cursor.fetchone()

                        if schedule:
                            module_code, instructor_id = schedule

                            # Get module name
                            cursor.execute('SELECT module_name FROM modules WHERE module_code = ?', (module_code,))
                            module_result = cursor.fetchone()
                            module_name = module_result[0] if module_result else module_code

                            # Create change description
                            changes = []
                            for key, value in updates.items():
                                if key == 'day_of_week':
                                    changes.append(f"Day: {value}")
                                elif key == 'start_time':
                                    changes.append(f"Start: {value}")
                                elif key == 'end_time':
                                    changes.append(f"End: {value}")
                                elif key == 'room_id':
                                    cursor.execute('SELECT building, room_number FROM rooms WHERE id = ?', (value,))
                                    room = cursor.fetchone()
                                    if room:
                                        changes.append(f"Room: {room[0]}-{room[1]}")

                            change_desc = ", ".join(changes) if changes else "schedule updated"
                            message = f"The schedule for {module_name} ({module_code}) has been updated:\n\nChanges: {change_desc}"

                            # Email all students and instructor using the new function
                            try:
                                target = self.gui or self.parent
                                summary = target.email_all_students_on_module(
                                    module_code,
                                    f"Schedule Changed: {module_code}",
                                    message,
                                    include_instructor=True
                                )
                                print(f"Schedule change emails sent: {summary['students_emailed']} students, instructor: {summary['instructor_emailed']}")
                                if summary['errors']:
                                    for error in summary['errors']:
                                        print(f"  - {error}")
                            except Exception as e:
                                print(f"Note: Notifications may not have been sent: {e}")

                        conn.commit()

                except Exception as notif_error:
                    # Don't fail the update if notifications fail
                    print(f"Note: Notifications may not have been sent: {notif_error}")

                self.result = True
                self.dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.editscheduledialog.dialogs.error', default="Error"), f"Failed to update schedule: {str(e)}", parent=self.dialog)

    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
