import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime, timedelta
from education_system.post_18.university_system.core.sql_safety import escape_like


class AppointmentsMixin:
    """Mixin for appointment management operations."""

    def create_schedule_appointment(self):
        """Create appointment scheduling interface"""
        title = ttk.Label(self.content_frame, text="Appointment Management", style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)

        notebook = ttk.Notebook(self.content_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        schedule_tab = ttk.Frame(notebook)
        notebook.add(schedule_tab, text="Schedule Appointment")
        self.create_schedule_appointment_form(schedule_tab)

        view_tab = ttk.Frame(notebook)
        notebook.add(view_tab, text="View Appointments")
        self.create_view_appointments_form(view_tab)

        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(1, weight=1)

    def create_schedule_appointment_form(self, parent):
        """Create form for scheduling appointments"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        ttk.Label(main_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.apt_student_id = tk.StringVar()
        if self.auth.current_user['role'] == 'student':
            self.apt_student_id.set(self.auth.current_user['id'])
        ttk.Entry(main_frame, textvariable=self.apt_student_id, width=20).grid(row=0, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(main_frame, text="Appointment Type:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.apt_type = tk.StringVar()
        apt_type_combo = ttk.Combobox(main_frame, textvariable=self.apt_type,
                                     values=['General Check-up', 'Follow-up Visit', 'Vaccination',
                                            'Mental Health Consultation', 'Injury Assessment',
                                            'Chronic Care Management', 'Preventive Screening',
                                            'Emergency Consultation'])
        apt_type_combo.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(main_frame, text="Date (YYYY-MM-DD):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.apt_date = tk.StringVar()
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        self.apt_date.set(tomorrow)
        ttk.Entry(main_frame, textvariable=self.apt_date, width=20).grid(row=2, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(main_frame, text="Time (HH:MM):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.apt_time = tk.StringVar(value="09:00")
        ttk.Entry(main_frame, textvariable=self.apt_time, width=20).grid(row=3, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(main_frame, text="Provider:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.apt_provider = tk.StringVar(value="Dr. Health Services")
        ttk.Entry(main_frame, textvariable=self.apt_provider, width=30).grid(row=4, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(main_frame, text="Reason:").grid(row=5, column=0, sticky=(tk.W, tk.N), pady=5)
        self.apt_reason = tk.Text(main_frame, width=40, height=4)
        self.apt_reason.grid(row=5, column=1, pady=5, padx=(5, 0))

        ttk.Button(main_frame, text="Schedule Appointment", command=self.save_appointment).grid(row=6, column=0, columnspan=2, pady=20)

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

    def save_appointment(self):
        """Save appointment to database"""
        try:
            if not all([self.apt_student_id.get().strip(), self.apt_type.get().strip(),
                       self.apt_date.get().strip(), self.apt_time.get().strip(),
                       self.apt_provider.get().strip()]):
                messagebox.showerror("Error", "Please fill in all required fields")
                return

            try:
                datetime.strptime(self.apt_date.get(), '%Y-%m-%d')
                datetime.strptime(self.apt_time.get(), '%H:%M')
            except ValueError:
                messagebox.showerror("Error", "Invalid date or time format")
                return

            if datetime.strptime(self.apt_date.get(), '%Y-%m-%d') < datetime.now():
                messagebox.showerror("Error", "Cannot schedule appointments in the past")
                return

            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (self.apt_student_id.get().strip(),))
            if cursor.fetchone()[0] == 0:
                messagebox.showerror("Error", "Student ID not found")
                conn.close()
                return

            scheduled_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            reason = self.apt_reason.get(1.0, tk.END).strip()

            cursor.execute('''
                INSERT INTO health_appointments
                (student_id, appointment_type, appointment_date, appointment_time,
                 provider, reason, status, scheduled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.apt_student_id.get().strip(),
                self.apt_type.get(),
                self.apt_date.get(),
                self.apt_time.get(),
                self.apt_provider.get().strip(),
                reason,
                'scheduled',
                scheduled_at
            ))

            conn.commit()
            apt_id = cursor.lastrowid

            cursor.execute("SELECT first_name, last_name, email_address FROM students WHERE student_id = ?",
                          (self.apt_student_id.get().strip(),))
            patient_info = cursor.fetchone()

            conn.close()

            if patient_info:
                patient_name = f"{patient_info[0]} {patient_info[1]}"
                patient_email = patient_info[2]

                appointment_details = {
                    'date': self.apt_date.get(),
                    'time': self.apt_time.get(),
                    'practitioner': self.apt_provider.get().strip(),
                    'department': self.apt_type.get(),
                    'type': self.apt_type.get(),
                    'preparation_notes': f"Reason for visit: {reason}" if reason else "No special preparation required."
                }

                self.send_appointment_confirmation(patient_email, patient_name, appointment_details)

            self.log_audit_event('schedule_appointment', 'appointment', apt_id)
            messagebox.showinfo("Success", f"Appointment scheduled successfully!\nAppointment ID: {apt_id}\nConfirmation email sent.")

            self.clear_appointment_form()

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")

    def clear_appointment_form(self):
        """Clear the appointment form"""
        if self.auth.current_user['role'] != 'student':
            self.apt_student_id.set("")
        self.apt_type.set("")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        self.apt_date.set(tomorrow)
        self.apt_time.set("09:00")
        self.apt_provider.set("Dr. Health Services")
        self.apt_reason.delete(1.0, tk.END)

    def create_view_appointments_form(self, parent):
        """Create interface for viewing appointments"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        search_frame = ttk.LabelFrame(main_frame, text="Search", padding="5")
        search_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(search_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.apt_search_student = tk.StringVar()
        if self.auth.current_user['role'] == 'student':
            self.apt_search_student.set(self.auth.current_user['id'])
        ttk.Entry(search_frame, textvariable=self.apt_search_student, width=20).grid(row=0, column=1, sticky=tk.W, pady=2, padx=(5, 10))

        ttk.Button(search_frame, text="Search", command=self.search_appointments).grid(row=0, column=2, padx=5)
        ttk.Button(search_frame, text="Show All", command=self.load_all_appointments).grid(row=0, column=3, padx=5)

        tree_frame = ttk.Frame(main_frame)
        tree_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        columns = ('ID', 'Student', 'Type', 'Date', 'Time', 'Provider', 'Status')
        self.apt_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.apt_tree.heading(col, text=col)
            if col == 'ID':
                self.apt_tree.column(col, width=50)
            else:
                self.apt_tree.column(col, width=120)

        self.apt_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        apt_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.apt_tree.yview)
        apt_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.apt_tree.configure(yscrollcommand=apt_scroll.set)

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=2, column=0, pady=10)

        ttk.Button(buttons_frame, text="View Details", command=self.view_appointment_details).pack(side=tk.LEFT, padx=5)
        if self.auth.check_permission('manage_health_appointments') or self.auth.check_permission('cancel_own_appointment'):
            ttk.Button(buttons_frame, text="Update Status", command=self.update_appointment_status).pack(side=tk.LEFT, padx=5)
            ttk.Button(buttons_frame, text="Cancel", command=self.cancel_appointment).pack(side=tk.LEFT, padx=5)

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self.load_all_appointments()

    def search_appointments(self):
        """Search appointments"""
        self.load_appointments(self.apt_search_student.get().strip())

    def load_all_appointments(self):
        """Load all appointments"""
        self.load_appointments()

    def load_appointments(self, student_filter=""):
        """Load appointments with optional student filter"""
        for item in self.apt_tree.get_children():
            self.apt_tree.delete(item)

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            query = '''
                SELECT ha.id, ha.student_id, ha.appointment_type, ha.appointment_date,
                       ha.appointment_time, ha.provider, ha.status
                FROM health_appointments ha
                WHERE 1=1
            '''
            params = []

            if student_filter:
                query += " AND ha.student_id LIKE ?"
                params.append(f"%{escape_like(student_filter)}%")

            if not self.auth.check_permission('manage_health_appointments'):
                if self.auth.current_user['role'] == 'student':
                    query += " AND ha.student_id = ?"
                    params.append(self.auth.current_user['id'])

            query += " ORDER BY ha.appointment_date DESC, ha.appointment_time DESC LIMIT 100"

            cursor.execute(query, params)
            appointments = cursor.fetchall()

            for apt in appointments:
                self.apt_tree.insert('', tk.END, values=apt)

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load appointments: {str(e)}")

    def view_appointment_details(self):
        """View details of selected appointment"""
        selection = self.apt_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an appointment to view.")
            return

        apt_id = self.apt_tree.item(selection[0])['values'][0]

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT apt.student_id, s.first_name, s.last_name, s.email_address,
                       apt.appointment_type, apt.appointment_date, apt.appointment_time,
                       apt.provider, apt.reason, apt.status, apt.notes, apt.scheduled_at
                FROM health_appointments apt
                JOIN students s ON apt.student_id = s.student_id
                WHERE apt.id = ?
            ''', (apt_id,))
            record = cursor.fetchone()
            conn.close()

            if not record:
                messagebox.showerror("Error", "Appointment not found")
                return

            dialog = tk.Toplevel(self.root)
            dialog.title("Appointment Details")
            dialog.geometry("600x600")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Appointment Details", font=('Arial', 14, 'bold')).pack(pady=10)

            details_frame = ttk.LabelFrame(main_frame, text="Appointment Information", padding=15)
            details_frame.pack(fill='both', expand=True, pady=10)

            info_text = tk.Text(details_frame, height=20, width=60, wrap='word', font=('Courier', 10))
            info_text.pack(fill='both', expand=True)

            status_display = record[9].upper() if record[9] else 'SCHEDULED'
            details = f"""
PATIENT INFORMATION
{'='*50}
Student ID:      {record[0]}
Name:            {record[1]} {record[2]}
Email:           {record[3]}

APPOINTMENT DETAILS
{'='*50}
Type:            {record[4]}
Date:            {record[5]}
Time:            {record[6]}
Provider:        {record[7] or 'Not assigned'}
Status:          {status_display}

REASON FOR VISIT
{'='*50}
{record[8] if record[8] else 'No reason provided'}

NOTES
{'='*50}
{record[10] if record[10] else 'No notes'}

SCHEDULING INFORMATION
{'='*50}
Scheduled At:    {record[11] if record[11] else 'N/A'}
"""

            info_text.insert('1.0', details)
            info_text.config(state='disabled')

            ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load appointment details: {e}")

    def update_appointment_status(self):
        """Update appointment status"""
        selection = self.apt_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an appointment to update.")
            return

        apt_id = self.apt_tree.item(selection[0])['values'][0]
        current_status = self.apt_tree.item(selection[0])['values'][6]

        status_dialog = tk.Toplevel(self.root)
        status_dialog.title("Update Appointment Status")
        status_dialog.geometry("300x200")
        status_dialog.transient(self.root)
        status_dialog.grab_set()

        ttk.Label(status_dialog, text=f"Current Status: {current_status}").pack(pady=10)
        ttk.Label(status_dialog, text="New Status:").pack()

        new_status = tk.StringVar()
        status_combo = ttk.Combobox(status_dialog, textvariable=new_status,
                                   values=['scheduled', 'completed', 'cancelled', 'no-show', 'rescheduled'])
        status_combo.pack(pady=5)

        def update_status():
            if new_status.get():
                try:
                    conn = self.get_connection()
                    cursor = conn.cursor()

                    cursor.execute('UPDATE health_appointments SET status = ? WHERE id = ?',
                                  (new_status.get(), apt_id))
                    conn.commit()
                    conn.close()

                    self.log_audit_event('update_appointment_status', 'appointment', apt_id,
                                       f"Status changed from {current_status} to {new_status.get()}")

                    messagebox.showinfo("Success", "Appointment status updated successfully!")
                    status_dialog.destroy()
                    self.load_appointments(self.apt_search_student.get().strip())
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update status: {str(e)}")
            else:
                messagebox.showwarning("Warning", "Please select a status")

        ttk.Button(status_dialog, text="Update", command=update_status).pack(pady=10)
        ttk.Button(status_dialog, text="Cancel", command=status_dialog.destroy).pack()

    def cancel_appointment(self):
        """Cancel selected appointment"""
        selection = self.apt_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an appointment to cancel.")
            return

        apt_id = self.apt_tree.item(selection[0])['values'][0]

        cancellation_reason = simpledialog.askstring(
            "Cancellation Reason",
            "Please provide a reason for cancelling this appointment:",
            initialvalue="Patient request"
        )

        if not cancellation_reason:
            return

        if messagebox.askyesno("Confirm Cancellation", "Are you sure you want to cancel this appointment?"):
            try:
                conn = self.get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT ha.student_id, ha.appointment_date, ha.appointment_time,
                           ha.provider, ha.appointment_type, s.first_name, s.last_name, s.email_address
                    FROM health_appointments ha
                    JOIN students s ON ha.student_id = s.student_id
                    WHERE ha.id = ?
                ''', (apt_id,))

                appointment_info = cursor.fetchone()

                cursor.execute('UPDATE health_appointments SET status = ? WHERE id = ?',
                              ('cancelled', apt_id))
                conn.commit()
                conn.close()

                if appointment_info:
                    patient_name = f"{appointment_info[5]} {appointment_info[6]}"
                    patient_email = appointment_info[7]

                    appointment_details = {
                        'date': appointment_info[1],
                        'time': appointment_info[2],
                        'practitioner': appointment_info[3],
                        'department': appointment_info[4]
                    }

                    self.send_appointment_cancellation(patient_email, patient_name, appointment_details, cancellation_reason)

                self.log_audit_event('cancel_appointment', 'appointment', apt_id, f"Reason: {cancellation_reason}")
                messagebox.showinfo("Success", "Appointment cancelled successfully!\nCancellation email sent.")
                self.load_appointments(self.apt_search_student.get().strip())

            except Exception as e:
                messagebox.showerror("Error", f"Failed to cancel appointment: {str(e)}")
