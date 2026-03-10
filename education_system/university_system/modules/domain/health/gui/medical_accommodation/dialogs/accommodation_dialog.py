# dialogs/accommodation_dialog.py
# Dialog for adding/editing accommodation records.

from .._common import (
    tk, ttk, messagebox, datetime,
    CLI_AVAILABLE,
)

if CLI_AVAILABLE:
    from .._common import get_accommodation_types


class AccommodationDialog:
    """Dialog for adding/editing accommodations"""

    def __init__(self, parent, title, current_data=None):
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)

        # Center the dialog
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))

        self.create_widgets(current_data)

        # Ensure window is visible before grabbing focus
        self.dialog.update_idletasks()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass  # Ignore grab errors if window not ready

        # Wait for dialog to close
        self.dialog.wait_window()

    def create_widgets(self, current_data):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Student ID
        ttk.Label(main_frame, text="Student ID:").grid(row=0, column=0, sticky='w', pady=5)
        self.student_id_var = tk.StringVar(value=current_data['student_id'] if current_data else '')
        ttk.Entry(main_frame, textvariable=self.student_id_var, width=30).grid(row=0, column=1, pady=5, sticky='ew')

        # Accommodation Type
        ttk.Label(main_frame, text="Accommodation Type:").grid(row=1, column=0, sticky='w', pady=5)
        self.type_var = tk.StringVar(value=current_data['accommodation_type'] if current_data else '')
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, width=28)
        if CLI_AVAILABLE:
            type_combo['values'] = get_accommodation_types()
        type_combo.grid(row=1, column=1, pady=5, sticky='ew')

        # Description
        ttk.Label(main_frame, text="Description:").grid(row=2, column=0, sticky='nw', pady=5)
        self.description_text = tk.Text(main_frame, height=3, width=30)
        if current_data and current_data['description']:
            self.description_text.insert(tk.END, current_data['description'])
        self.description_text.grid(row=2, column=1, pady=5, sticky='ew')

        # Start Date
        ttk.Label(main_frame, text="Start Date (YYYY-MM-DD):").grid(row=3, column=0, sticky='w', pady=5)
        self.start_date_var = tk.StringVar(value=current_data['start_date'] if current_data else '')
        ttk.Entry(main_frame, textvariable=self.start_date_var, width=30).grid(row=3, column=1, pady=5, sticky='ew')

        # End Date
        ttk.Label(main_frame, text="End Date (YYYY-MM-DD):").grid(row=4, column=0, sticky='w', pady=5)
        self.end_date_var = tk.StringVar(value=current_data['end_date'] if current_data else '')
        ttk.Entry(main_frame, textvariable=self.end_date_var, width=30).grid(row=4, column=1, pady=5, sticky='ew')

        # Status
        ttk.Label(main_frame, text="Status:").grid(row=5, column=0, sticky='w', pady=5)
        self.status_var = tk.StringVar(value=current_data['status'] if current_data else 'active')
        status_combo = ttk.Combobox(main_frame, textvariable=self.status_var, width=28)
        status_combo['values'] = ['active', 'pending', 'suspended', 'expired']
        status_combo.grid(row=5, column=1, pady=5, sticky='ew')

        # Notes
        ttk.Label(main_frame, text="Notes:").grid(row=6, column=0, sticky='nw', pady=5)
        self.notes_text = tk.Text(main_frame, height=3, width=30)
        if current_data and current_data['notes']:
            self.notes_text.insert(tk.END, current_data['notes'])
        self.notes_text.grid(row=6, column=1, pady=5, sticky='ew')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)

        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)

    def save(self):
        """Save the accommodation data"""
        # Validate required fields
        if not self.student_id_var.get().strip():
            messagebox.showerror("Error", "Student ID is required")
            return

        if not self.type_var.get().strip():
            messagebox.showerror("Error", "Accommodation type is required")
            return

        # Validate and parse dates
        start_date_str = self.start_date_var.get().strip()
        end_date_str = self.end_date_var.get().strip()

        start_date = None
        end_date = None

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            except ValueError:
                messagebox.showerror("Error", "Invalid start date format. Use YYYY-MM-DD")
                return

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            except ValueError:
                messagebox.showerror("Error", "Invalid end date format. Use YYYY-MM-DD")
                return

        # Check date range
        if start_date and end_date and end_date <= start_date:
            messagebox.showerror("Error", "End date must be after start date")
            return

        # Collect data
        self.result = {
            'student_id': self.student_id_var.get().strip(),
            'accommodation_type': self.type_var.get().strip(),
            'description': self.description_text.get(1.0, tk.END).strip() or None,
            'start_date': start_date_str or None,
            'end_date': end_date_str or None,
            'status': self.status_var.get(),
            'notes': self.notes_text.get(1.0, tk.END).strip() or None
        }

        self.dialog.destroy()

    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()
