"""Extracted class implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import dialogs_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AddHolidayDialog:
    def __init__(self, parent, scheduler):
        self.parent = parent
        self.scheduler = scheduler
        self.result = False

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.academics.module_scheduling.dialogs_parts.addholidaydialog.windows.add_holiday', default="Add Holiday"))
        self.dialog.geometry("400x350")
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

        # Holiday name
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addholidaydialog.labels.holiday_name', default="Holiday Name:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=30).grid(row=0, column=1, pady=5)

        # Start date
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addholidaydialog.labels.start_date', default="Start Date:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.start_date_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.start_date_var, width=30).grid(row=1, column=1, pady=5)
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addholidaydialog.labels.yyyy_mm_dd_format', default="(YYYY-MM-DD format)"), font=('Arial', 8)).grid(row=1, column=2, sticky=tk.W)

        # End date
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addholidaydialog.labels.end_date', default="End Date:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.end_date_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.end_date_var, width=30).grid(row=2, column=1, pady=5)
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addholidaydialog.labels.leave_blank_if_same_as_start', default="(leave blank if same as start)"), font=('Arial', 8)).grid(row=2, column=2, sticky=tk.W)

        # Description
        ttk.Label(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addholidaydialog.labels.description', default="Description:")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.description_text = tk.Text(main_frame, width=30, height=3)
        self.description_text.grid(row=3, column=1, pady=5)

        # Recurring
        self.recurring_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addholidaydialog.buttons.recurring_annually', default="Recurring annually"), variable=self.recurring_var).grid(row=4, column=1, sticky=tk.W, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=3, pady=20)

        ttk.Button(button_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addholidaydialog.buttons.save', default="Save"), command=self.save_holiday).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.academics.module_scheduling.dialogs_parts.addholidaydialog.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def save_holiday(self):
        try:
            name = self.name_var.get()
            start_date = self.start_date_var.get()
            end_date = self.end_date_var.get() or start_date
            description = self.description_text.get(1.0, tk.END).strip()
            recurring = self.recurring_var.get()

            if not all([name, start_date]):
                messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.addholidaydialog.dialogs.error', default="Error"), _t('gui.academics.module_scheduling.dialogs_parts.addholidaydialog.dialogs.please_fill_in_name_and_start_date', default="Please fill in name and start date."), parent=self.dialog)
                return

            # Validate date format
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
                if end_date != start_date:
                    datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.addholidaydialog.dialogs.error', default="Error"), _t('gui.academics.module_scheduling.dialogs_parts.addholidaydialog.dialogs.invalid_date_format_use_yyyy_mm_dd', default="Invalid date format. Use YYYY-MM-DD."), parent=self.dialog)
                return

            self.scheduler.add_holiday(name, start_date, end_date, description, recurring)

            self.result = True
            # Confirm first, then close. Destroying the dialog and *then*
            # parenting the confirmation to it raised "bad window path name",
            # which the except clause below reported as "Failed to save
            # holiday" — even though the holiday had already been written.
            messagebox.showinfo(_t('gui.academics.module_scheduling.dialogs_parts.addholidaydialog.dialogs.success', default="Success"), _t('gui.academics.module_scheduling.dialogs_parts.addholidaydialog.dialogs.holiday_added_successfully', default="Holiday added successfully."), parent=self.dialog)
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t('gui.academics.module_scheduling.dialogs_parts.addholidaydialog.dialogs.error', default="Error"), f"Failed to save holiday: {str(e)}", parent=self.dialog)

    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
