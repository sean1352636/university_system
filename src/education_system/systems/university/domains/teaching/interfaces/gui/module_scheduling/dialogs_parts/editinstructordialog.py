"""Extracted class implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import dialogs_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class EditInstructorDialog:
    def __init__(self, parent, scheduler, instructor_id):
        self.parent = parent
        self.scheduler = scheduler
        self.instructor_id = instructor_id
        self.result = False

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.academics.module_scheduling.dialogs_parts.editinstructordialog.windows.edit_instructor', default="Edit Instructor"))
        self.dialog.geometry("400x500")
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
        """Load current instructor data"""
        try:
            from education_system.systems.university.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT id, first_name, last_name, email, department,
                       COALESCE(max_hours_per_week, max_courses_per_semester * 8, 40) as max_hours_per_week,
                       preferred_days, preferred_times
                FROM instructors WHERE id = ?
                ''', (self.instructor_id,))
                instructor = cursor.fetchone()

            if instructor:
                self.current_data = {
                    'first_name': instructor[1],
                    'last_name': instructor[2],
                    'email': instructor[3],
                    'department': instructor[4],
                    'max_hours_per_week': instructor[5],
                    'preferred_days': instructor[6] or "",
                    'preferred_times': instructor[7] or ""
                }
            else:
                raise CourseNotFoundError(f"Instructor {self.instructor_id}")

        except (CourseNotFoundError, sqlite3.Error) as e:
            messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.editinstructordialog.dialogs.error', default="Error"), f"Failed to load instructor data: {str(e)}", parent=self.dialog)
            self.dialog.destroy()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Name (read-only)
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editinstructordialog.labels.name', default="Name:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        name_label = ttk.Label(main_frame, text=f"{self.current_data['first_name']} {self.current_data['last_name']}",
                              font=('Arial', 10, 'bold'))
        name_label.grid(row=0, column=1, sticky=tk.W, pady=5)

        # Email
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editinstructordialog.labels.email', default="Email:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.email_var = tk.StringVar(value=self.current_data['email'])
        ttk.Entry(main_frame, textvariable=self.email_var, width=30).grid(row=1, column=1, pady=5)

        # Department
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editinstructordialog.labels.department', default="Department:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.department_var = tk.StringVar(value=self.current_data['department'])
        ttk.Entry(main_frame, textvariable=self.department_var, width=30).grid(row=2, column=1, pady=5)

        # Max hours
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editinstructordialog.labels.max_hours_week', default="Max Hours/Week:")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.max_hours_var = tk.StringVar(value=str(self.current_data['max_hours_per_week']))
        ttk.Entry(main_frame, textvariable=self.max_hours_var, width=30).grid(row=3, column=1, pady=5)

        # Preferred days
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editinstructordialog.labels.preferred_days', default="Preferred Days:")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.preferred_days_var = tk.StringVar(value=self.current_data['preferred_days'])
        ttk.Entry(main_frame, textvariable=self.preferred_days_var, width=30).grid(row=4, column=1, pady=5)

        # Preferred times
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editinstructordialog.labels.preferred_times', default="Preferred Times:")).grid(row=5, column=0, sticky=tk.W, pady=5)
        self.preferred_times_var = tk.StringVar(value=self.current_data['preferred_times'])
        ttk.Entry(main_frame, textvariable=self.preferred_times_var, width=30).grid(row=5, column=1, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editinstructordialog.buttons.update', default="Update"), command=self.update_instructor).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.editinstructordialog.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def update_instructor(self):
        try:
            new_email = self.email_var.get()
            new_department = self.department_var.get()
            new_max_hours = int(self.max_hours_var.get())
            new_preferred_days = self.preferred_days_var.get()
            new_preferred_times = self.preferred_times_var.get()

            from education_system.systems.university.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()

                # Check which column exists for max hours
                cursor.execute("PRAGMA table_info(instructors)")
                columns = [column[1] for column in cursor.fetchall()]

                if 'max_hours_per_week' in columns:
                    cursor.execute('''
                    UPDATE instructors
                    SET email = ?, department = ?, max_hours_per_week = ?, preferred_days = ?, preferred_times = ?
                    WHERE id = ?
                    ''', (new_email, new_department, new_max_hours, new_preferred_days, new_preferred_times, self.instructor_id))
                elif 'max_courses_per_semester' in columns:
                    # Convert hours to courses (assuming 8 hours per course)
                    max_courses = max(1, round(float(new_max_hours) / 8))
                    cursor.execute('''
                    UPDATE instructors
                    SET email = ?, department = ?, max_courses_per_semester = ?, preferred_days = ?, preferred_times = ?
                    WHERE id = ?
                    ''', (new_email, new_department, max_courses, new_preferred_days, new_preferred_times, self.instructor_id))
                else:
                    # Fallback - update without max hours column
                    cursor.execute('''
                    UPDATE instructors
                    SET email = ?, department = ?, preferred_days = ?, preferred_times = ?
                    WHERE id = ?
                    ''', (new_email, new_department, new_preferred_days, new_preferred_times, self.instructor_id))

                conn.commit()

            self.result = True
            # Confirm first, then close — see addholidaydialog.save_holiday.
            messagebox.showinfo(_t('gui.academics.module_scheduling.dialogs_parts.editinstructordialog.dialogs.success', default="Success"), _t('gui.academics.module_scheduling.dialogs_parts.editinstructordialog.dialogs.instructor_updated_successfully', default="Instructor updated successfully."), parent=self.dialog)
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.editinstructordialog.dialogs.error', default="Error"), _t('gui.academics.module_scheduling.dialogs_parts.editinstructordialog.dialogs.max_hours_must_be_a_number', default="Max hours must be a number."), parent=self.dialog)
        except Exception as e:
            messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.editinstructordialog.dialogs.error', default="Error"), f"Failed to update instructor: {str(e)}", parent=self.dialog)

    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
