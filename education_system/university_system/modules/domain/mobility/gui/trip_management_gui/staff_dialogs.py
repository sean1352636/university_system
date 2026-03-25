import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.simpledialog import Dialog
from datetime import datetime

from education_system.university_system.modules.domain.mobility.gui.trip_management_gui._imports import safe_db_operation, sqlite3


class AssignStaffDialog(Dialog):
    def __init__(self, parent, auth, trip_id, refresh_callback):
        self.auth = auth
        self.trip_id = trip_id
        self.refresh_callback = refresh_callback
        super().__init__(parent, "Assign Staff to Trip")

    def body(self, master):
        """Create the dialog body"""
        # Available staff
        ttk.Label(master, text="Available Staff:").pack(anchor=tk.W)

        self.staff_listbox = tk.Listbox(master, width=60, height=10)
        self.staff_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Role selection
        ttk.Label(master, text="Role:").pack(anchor=tk.W)
        self.role_var = tk.StringVar(value="supervisor")

        role_frame = ttk.Frame(master)
        role_frame.pack(fill=tk.X, pady=5)

        roles = ['supervisor', 'coordinator', 'medical', 'transport']
        for role in roles:
            ttk.Radiobutton(role_frame, text=role.title(), variable=self.role_var,
                           value=role).pack(side=tk.LEFT, padx=(0, 20))

        # Load available staff
        self.load_available_staff()

        return self.staff_listbox

    def load_available_staff(self):
        """Load available staff members"""
        def get_available_staff_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            SELECT u.id, u.first_name, u.last_name, u.username, r.role_name
            FROM users u
            JOIN roles r ON u.role_id = r.id
            WHERE r.role_name IN ('admin', 'staff', 'instructor')
            AND u.id NOT IN (
                SELECT staff_user_id FROM trip_staff WHERE trip_id = ?
            )
            ORDER BY r.role_name, u.last_name
            ''', (self.trip_id,))

            return cursor.fetchall()

        staff = safe_db_operation(get_available_staff_operation)

        if staff:
            for staff_member in staff:
                user_id, first_name, last_name, username, role = staff_member
                display_text = f"{user_id}: {first_name} {last_name} ({username}) - {role.title()}"
                self.staff_listbox.insert(tk.END, display_text)

    def validate(self):
        """Validate staff selection"""
        selection = self.staff_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a staff member.")
            return False
        return True

    def apply(self):
        """Assign the staff member"""
        selection = self.staff_listbox.curselection()
        if not selection:
            return

        # Extract staff ID from selection
        selected_text = self.staff_listbox.get(selection[0])
        staff_id = int(selected_text.split(':')[0])

        def assign_staff_operation(conn):
            cursor = conn.cursor()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT INTO trip_staff (trip_id, staff_user_id, role, assigned_date)
            VALUES (?, ?, ?, ?)
            ''', (self.trip_id, staff_id, self.role_var.get(), timestamp))

            return True


        try:
            if safe_db_operation(assign_staff_operation):
                messagebox.showinfo("Success", "Staff member assigned successfully!")
                if self.refresh_callback:
                    self.refresh_callback()
            else:
                messagebox.showerror("Error", "Failed to assign staff member.")
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Staff member is already assigned to this trip.")
