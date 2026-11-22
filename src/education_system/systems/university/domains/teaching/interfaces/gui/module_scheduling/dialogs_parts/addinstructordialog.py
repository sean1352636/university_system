"""Extracted class implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import dialogs_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AddInstructorDialog:
    def __init__(self, parent, scheduler):
        self.parent = parent
        self.scheduler = scheduler
        self.result = False

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.windows.add_new_instructor', default="Add New Instructor"))
        self.dialog.geometry("500x550")
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
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Personal Information
        personal_frame = ttk.LabelFrame(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.labels.personal_information', default="Personal Information"), padding=10)
        personal_frame.pack(fill=tk.X, pady=5)

        ttk.Label(personal_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.labels.first_name', default="First Name:")).grid(row=0, column=0, sticky=tk.W)
        self.first_name_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.first_name_var, width=25).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(personal_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.labels.last_name', default="Last Name:")).grid(row=1, column=0, sticky=tk.W)
        self.last_name_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.last_name_var, width=25).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(personal_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.labels.email', default="Email:")).grid(row=2, column=0, sticky=tk.W)
        self.email_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.email_var, width=35).grid(row=2, column=1, sticky=tk.W, padx=5)

        # Professional Information
        prof_frame = ttk.LabelFrame(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.labels.professional_information', default="Professional Information"), padding=10)
        prof_frame.pack(fill=tk.X, pady=5)

        ttk.Label(prof_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.labels.department', default="Department:")).grid(row=0, column=0, sticky=tk.W)
        self.department_var = tk.StringVar()
        ttk.Entry(prof_frame, textvariable=self.department_var, width=25).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(prof_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.labels.specialization', default="Specialization:")).grid(row=1, column=0, sticky=tk.W)
        self.specialization_var = tk.StringVar()
        ttk.Entry(prof_frame, textvariable=self.specialization_var, width=35).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(prof_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.labels.max_courses_semester', default="Max Courses/Semester:")).grid(row=2, column=0, sticky=tk.W)
        self.max_courses_var = tk.StringVar(value="4")
        ttk.Entry(prof_frame, textvariable=self.max_courses_var, width=10).grid(row=2, column=1, sticky=tk.W, padx=5)

        ttk.Label(prof_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.labels.max_hours_week', default="Max Hours/Week:")).grid(row=3, column=0, sticky=tk.W)
        self.max_hours_var = tk.StringVar(value="40")
        ttk.Entry(prof_frame, textvariable=self.max_hours_var, width=10).grid(row=3, column=1, sticky=tk.W, padx=5)

        # Scheduling Preferences
        sched_frame = ttk.LabelFrame(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.labels.scheduling_preferences', default="Scheduling Preferences"), padding=10)
        sched_frame.pack(fill=tk.X, pady=5)

        ttk.Label(sched_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.labels.preferred_days', default="Preferred Days:")).grid(row=0, column=0, sticky=tk.W)
        self.preferred_days_var = tk.StringVar()
        ttk.Entry(sched_frame, textvariable=self.preferred_days_var, width=35).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Label(sched_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.labels.comma_separated_e_g_monday_tuesday', default="(comma-separated, e.g., Monday,Tuesday)"), font=('Arial', 8)).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(sched_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.labels.preferred_times', default="Preferred Times:")).grid(row=2, column=0, sticky=tk.W)
        self.preferred_times_var = tk.StringVar()
        ttk.Entry(sched_frame, textvariable=self.preferred_times_var, width=35).grid(row=2, column=1, sticky=tk.W, padx=5)
        ttk.Label(sched_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.labels.comma_separated_e_g_09_00_10_00', default="(comma-separated, e.g., 09:00,10:00)"), font=('Arial', 8)).grid(row=3, column=1, sticky=tk.W, padx=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.buttons.add_instructor', default="Add Instructor"), command=self.save_instructor).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def save_instructor(self):
        try:
            # Validate inputs
            first_name = self.first_name_var.get().strip()
            last_name = self.last_name_var.get().strip()
            email = self.email_var.get().strip()

            if not first_name or not last_name or not email:
                messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.dialogs.validation_error', default="Validation Error"), _t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.dialogs.first_name_last_name_and_email_are_required', default="First name, last name, and email are required."), parent=self.dialog)
                return

            # Validate email format
            import re
            email_pattern = r'^[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}$'
            if not re.match(email_pattern, email):
                messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.dialogs.validation_error', default="Validation Error"), _t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.dialogs.please_enter_a_valid_email_address', default="Please enter a valid email address."), parent=self.dialog)
                return

            department = self.department_var.get().strip()
            specialization = self.specialization_var.get().strip()

            try:
                max_courses = int(self.max_courses_var.get())
            except ValueError:
                messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.dialogs.validation_error', default="Validation Error"), _t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.dialogs.max_courses_must_be_a_number', default="Max courses must be a number."), parent=self.dialog)
                return

            try:
                max_hours = int(self.max_hours_var.get())
            except ValueError:
                messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.dialogs.validation_error', default="Validation Error"), _t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.dialogs.max_hours_must_be_a_number', default="Max hours must be a number."), parent=self.dialog)
                return

            preferred_days = self.preferred_days_var.get().strip()
            preferred_times = self.preferred_times_var.get().strip()

            # Delegate to the unified service so an instructor added here also
            # lands in the staff directory / login stores — not just the
            # instructors table. (One code path shared with course management.)
            from education_system.systems.university.domains.curriculum.domain.course_management.instructor_service import (
                create_instructor as create_instructor_service,
            )

            result = create_instructor_service(
                first_name=first_name,
                last_name=last_name,
                email=email,  # user-typed address
                department=department,
                specialization=specialization,
                max_courses=max_courses,
                max_hours=max_hours,
                preferred_days=preferred_days,
                preferred_times=preferred_times,
                auth=getattr(self, "auth", None),
            )

            if not result.ok:
                messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.dialogs.error', default="Error"), result.error or "Failed to save instructor.",
                                     parent=self.dialog)
                return

            self.result = True
            msg = f"Instructor {first_name} {last_name} added successfully."
            for warning in result.warnings:
                msg += f"\n⚠ {warning}"
            messagebox.showinfo(_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.dialogs.success', default="Success"), msg, parent=self.dialog)
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.addinstructordialog.dialogs.error', default="Error"), f"Failed to save instructor: {str(e)}", parent=self.dialog)

    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
