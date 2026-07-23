# dialogs/accommodation_dialog.py
# Dialog for adding/editing accommodation records.

from education_system.post_18.university_system.modules.domain.health.gui.medical_accommodation._common import (
    tk, ttk, messagebox, datetime, sqlite3,
    CLI_AVAILABLE, get_connection,
)

if CLI_AVAILABLE:
    from education_system.post_18.university_system.modules.domain.health.gui.medical_accommodation._common import get_accommodation_types

# Try to import tkcalendar for date picker
try:
    from tkcalendar import DateEntry
    DATEPICKER_AVAILABLE = True
except ImportError:
    DATEPICKER_AVAILABLE = False


def _load_students():
    """Load students for dropdown: returns list of 'ID - Name' strings and a mapping dict."""
    students = []
    student_map = {}
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT student_id, first_name, last_name FROM students ORDER BY last_name, first_name"
            )
            for row in cursor.fetchall():
                sid, first, last = row
                label = f"{sid} - {(first or '')} {(last or '')}".strip()
                students.append(label)
                student_map[label] = sid
    except Exception:
        pass
    return students, student_map


class AccommodationDialog:
    """Dialog for adding/editing accommodations"""

    def __init__(self, parent, title, current_data=None):
        self.result = None
        self.student_map = {}

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

        # Student ID - dropdown with search
        ttk.Label(main_frame, text="Student:").grid(row=0, column=0, sticky='w', pady=5)
        self.student_id_var = tk.StringVar()
        students_list, self.student_map = _load_students()

        student_combo = ttk.Combobox(main_frame, textvariable=self.student_id_var, width=28)
        student_combo['values'] = students_list
        student_combo.grid(row=0, column=1, pady=5, sticky='ew')

        # Pre-select if editing
        if current_data and current_data['student_id']:
            sid = current_data['student_id']
            # Find matching entry or fall back to raw ID
            matched = False
            for label, mapped_id in self.student_map.items():
                if mapped_id == sid:
                    self.student_id_var.set(label)
                    matched = True
                    break
            if not matched:
                self.student_id_var.set(sid)

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
        ttk.Label(main_frame, text="Start Date:").grid(row=3, column=0, sticky='w', pady=5)
        if DATEPICKER_AVAILABLE:
            start_val = current_data['start_date'] if current_data and current_data['start_date'] else ''
            self.start_date_entry = DateEntry(main_frame, width=28, date_pattern='yyyy-mm-dd')
            if start_val:
                try:
                    self.start_date_entry.set_date(datetime.strptime(start_val, '%Y-%m-%d'))
                except ValueError:
                    pass
            self.start_date_entry.grid(row=3, column=1, pady=5, sticky='ew')
        else:
            self.start_date_var = tk.StringVar(value=current_data['start_date'] if current_data else '')
            ttk.Entry(main_frame, textvariable=self.start_date_var, width=30).grid(row=3, column=1, pady=5, sticky='ew')

        # End Date
        ttk.Label(main_frame, text="End Date:").grid(row=4, column=0, sticky='w', pady=5)
        if DATEPICKER_AVAILABLE:
            end_val = current_data['end_date'] if current_data and current_data['end_date'] else ''
            self.end_date_entry = DateEntry(main_frame, width=28, date_pattern='yyyy-mm-dd')
            if end_val:
                try:
                    self.end_date_entry.set_date(datetime.strptime(end_val, '%Y-%m-%d'))
                except ValueError:
                    pass
            self.end_date_entry.grid(row=4, column=1, pady=5, sticky='ew')
        else:
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

    def _get_student_id(self):
        """Extract student ID from dropdown selection or raw input."""
        raw = self.student_id_var.get().strip()
        # If it matches a dropdown label, map it back to the ID
        if raw in self.student_map:
            return self.student_map[raw]
        # Could be a raw student ID typed directly
        return raw

    def _get_date_str(self, which):
        """Get date string from DateEntry or fallback Entry widget."""
        if DATEPICKER_AVAILABLE:
            entry = self.start_date_entry if which == 'start' else self.end_date_entry
            return entry.get_date().strftime('%Y-%m-%d')
        else:
            var = self.start_date_var if which == 'start' else self.end_date_var
            return var.get().strip()

    def save(self):
        """Save the accommodation data"""
        # Validate required fields
        student_id = self._get_student_id()
        if not student_id:
            messagebox.showerror("Error", "Student is required")
            return

        if not self.type_var.get().strip():
            messagebox.showerror("Error", "Accommodation type is required")
            return

        # Validate and parse dates
        start_date_str = self._get_date_str('start')
        end_date_str = self._get_date_str('end')

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
            'student_id': student_id,
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
