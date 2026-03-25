# dialogs/export_filter.py
# Dialog for selecting export filters.

from education_system.university_system.modules.domain.health.gui.medical_accommodation._common import tk, ttk, messagebox, CLI_AVAILABLE

if CLI_AVAILABLE:
    from education_system.university_system.modules.domain.health.gui.medical_accommodation._common import get_accommodation_types


class ExportFilterDialog:
    """Dialog for export filters"""

    def __init__(self, parent):
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Export Filters")
        self.dialog.geometry("400x250")
        self.dialog.transient(parent)

        self.create_widgets()

        # Ensure window is visible before grabbing focus
        self.dialog.update_idletasks()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass  # Ignore grab errors if window not ready

        self.dialog.wait_window()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Filter Options (leave blank for all):").grid(row=0, column=0, columnspan=2, pady=10)

        # Student ID
        ttk.Label(main_frame, text="Student ID:").grid(row=1, column=0, sticky='w', pady=5)
        self.student_id_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.student_id_var, width=30).grid(row=1, column=1, pady=5, sticky='ew')

        # Accommodation Type
        ttk.Label(main_frame, text="Accommodation Type:").grid(row=2, column=0, sticky='w', pady=5)
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, width=28)
        if CLI_AVAILABLE:
            type_combo['values'] = [''] + get_accommodation_types()
        type_combo.grid(row=2, column=1, pady=5, sticky='ew')

        # Status
        ttk.Label(main_frame, text="Status:").grid(row=3, column=0, sticky='w', pady=5)
        self.status_var = tk.StringVar()
        status_combo = ttk.Combobox(main_frame, textvariable=self.status_var, width=28)
        status_combo['values'] = ['', 'active', 'pending', 'suspended', 'expired']
        status_combo.grid(row=3, column=1, pady=5, sticky='ew')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Export", command=self.export).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def export(self):
        """Set export filters"""
        self.result = {
            'student_id': self.student_id_var.get().strip() or None,
            'accommodation_type': self.type_var.get().strip() or None,
            'status': self.status_var.get().strip() or None
        }

        self.dialog.destroy()

    def cancel(self):
        """Cancel export"""
        self.dialog.destroy()
