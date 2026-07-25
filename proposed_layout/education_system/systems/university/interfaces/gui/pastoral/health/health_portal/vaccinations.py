import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure import paths

DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH


class VaccinationsMixin:
    """Mixin for vaccination management operations."""

    def create_record_vaccination(self):
        """Create vaccination recording interface"""
        title = ttk.Label(self.content_frame, text=_t("health_portal.labels.vaccination_management"), style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)

        notebook = ttk.Notebook(self.content_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        record_tab = ttk.Frame(notebook)
        notebook.add(record_tab, text=_t("health_portal.tabs.record_vaccination"))
        self.create_record_vaccination_form(record_tab)

        view_tab = ttk.Frame(notebook)
        notebook.add(view_tab, text=_t("health_portal.tabs.view_vaccinations"))
        self.create_view_vaccinations_form(view_tab)

        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(1, weight=1)

    def create_record_vaccination_form(self, parent):
        """Create form for recording vaccinations"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        ttk.Label(main_frame, text=_t("health_portal.labels.student_id")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.vax_student_id = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.vax_student_id, width=20).grid(row=0, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(main_frame, text=_t("health_portal.labels.vaccine")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.vax_name = tk.StringVar()
        vaccine_combo = ttk.Combobox(main_frame, textvariable=self.vax_name,
                                    values=['COVID-19', 'Influenza (Flu)', 'Hepatitis A', 'Hepatitis B',
                                           'Measles, Mumps, Rubella (MMR)', 'Meningococcal',
                                           'Tetanus, Diphtheria, Pertussis (Tdap)',
                                           'Varicella (Chickenpox)', 'HPV', _t("health_portal.record_types.other")])
        vaccine_combo.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(main_frame, text=_t("health_portal.labels.administered_date")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.vax_date = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(main_frame, textvariable=self.vax_date, width=20).grid(row=2, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(main_frame, text=_t("health_portal.labels.lot_number")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.vax_lot = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.vax_lot, width=20).grid(row=3, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(main_frame, text=_t("health_portal.labels.manufacturer")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.vax_manufacturer = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.vax_manufacturer, width=30).grid(row=4, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(main_frame, text=_t("health_portal.labels.administered_by")).grid(row=5, column=0, sticky=tk.W, pady=5)
        self.vax_admin_by = tk.StringVar(value=f"Dr. {self.auth.current_user['username']}")
        ttk.Entry(main_frame, textvariable=self.vax_admin_by, width=30).grid(row=5, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(main_frame, text=_t("health_portal.labels.location")).grid(row=6, column=0, sticky=tk.W, pady=5)
        self.vax_location = tk.StringVar(value=_t("health_portal.defaults.left_arm"))
        ttk.Entry(main_frame, textvariable=self.vax_location, width=20).grid(row=6, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        self.vax_adverse = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text=_t("health_portal.labels.adverse_reaction_reported"),
                       variable=self.vax_adverse, command=self.toggle_adverse_reaction).grid(row=7, column=1, sticky=tk.W, pady=5)

        ttk.Label(main_frame, text=_t("health_portal.labels.reaction_description")).grid(row=8, column=0, sticky=(tk.W, tk.N), pady=5)
        self.vax_reaction = tk.Text(main_frame, width=40, height=3, state=tk.DISABLED)
        self.vax_reaction.grid(row=8, column=1, pady=5, padx=(5, 0))

        ttk.Button(main_frame, text=_t("health_portal.buttons.record_vaccination"), command=self.save_vaccination).grid(row=9, column=0, columnspan=2, pady=20)

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

    def toggle_adverse_reaction(self):
        """Toggle adverse reaction text area"""
        if self.vax_adverse.get():
            self.vax_reaction.config(state=tk.NORMAL)
        else:
            self.vax_reaction.config(state=tk.DISABLED)
            self.vax_reaction.delete(1.0, tk.END)

    def save_vaccination(self):
        """Save vaccination record to database"""
        try:
            if not all([self.vax_student_id.get().strip(), self.vax_name.get().strip(),
                       self.vax_date.get().strip(), self.vax_lot.get().strip(),
                       self.vax_manufacturer.get().strip(), self.vax_admin_by.get().strip()]):
                messagebox.showerror("Error", "Please fill in all required fields")
                return

            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (self.vax_student_id.get().strip(),))
            if cursor.fetchone()[0] == 0:
                messagebox.showerror("Error", "Student ID not found")
                conn.close()
                return

            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            adverse_reaction = 1 if self.vax_adverse.get() else 0
            reaction_desc = self.vax_reaction.get(1.0, tk.END).strip() if adverse_reaction else ""

            cursor.execute('''
                INSERT INTO vaccination_records
                (student_id, vaccine_name, administered_date, lot_number, manufacturer,
                 administered_by, location, adverse_reaction, reaction_description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.vax_student_id.get().strip(),
                self.vax_name.get(),
                self.vax_date.get(),
                self.vax_lot.get().strip(),
                self.vax_manufacturer.get().strip(),
                self.vax_admin_by.get().strip(),
                self.vax_location.get().strip(),
                adverse_reaction,
                reaction_desc,
                created_at
            ))

            conn.commit()
            vax_id = cursor.lastrowid
            conn.close()

            self.log_audit_event('record_vaccination', 'vaccination', vax_id)

            if adverse_reaction:
                messagebox.showwarning("Vaccination Recorded",
                                     "Vaccination recorded successfully!\nADVERSE REACTION REPORTED - Monitor patient closely")
            else:
                messagebox.showinfo("Success", "Vaccination recorded successfully!")

            self.clear_vaccination_form()

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")

    def clear_vaccination_form(self):
        """Clear the vaccination form"""
        self.vax_student_id.set("")
        self.vax_name.set("")
        self.vax_date.set(datetime.now().strftime('%Y-%m-%d'))
        self.vax_lot.set("")
        self.vax_manufacturer.set("")
        self.vax_admin_by.set(f"Dr. {self.auth.current_user['username']}")
        self.vax_location.set("Left arm")
        self.vax_adverse.set(False)
        self.vax_reaction.delete(1.0, tk.END)
        self.vax_reaction.config(state=tk.DISABLED)

    def create_view_vaccinations_form(self, parent):
        """Create interface for viewing vaccination records"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        search_frame = ttk.LabelFrame(main_frame, text="Search", padding="5")
        search_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(search_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.vax_search_student = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.vax_search_student, width=20).grid(row=0, column=1, sticky=tk.W, pady=2, padx=(5, 10))

        ttk.Button(search_frame, text="Search", command=self.search_vaccinations).grid(row=0, column=2, padx=5)
        ttk.Button(search_frame, text="Show All", command=self.load_all_vaccinations).grid(row=0, column=3, padx=5)

        tree_frame = ttk.Frame(main_frame)
        tree_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        columns = ('ID', 'Student', 'Vaccine', 'Date', 'Administered By', 'Adverse Reaction')
        self.vax_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.vax_tree.heading(col, text=col)
            if col == 'ID':
                self.vax_tree.column(col, width=50)
            else:
                self.vax_tree.column(col, width=120)

        self.vax_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        vax_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.vax_tree.yview)
        vax_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.vax_tree.configure(yscrollcommand=vax_scroll.set)

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=2, column=0, pady=10)

        ttk.Button(buttons_frame, text="View Details", command=self.view_vaccination_details).pack(side=tk.LEFT, padx=5)
        if self.auth.check_permission('verify_vaccinations'):
            ttk.Button(buttons_frame, text="Verify Record", command=self.verify_vaccination).pack(side=tk.LEFT, padx=5)

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self.load_all_vaccinations()

    def search_vaccinations(self):
        """Search vaccination records"""
        self.load_vaccinations(self.vax_search_student.get().strip())

    def load_all_vaccinations(self):
        """Load all vaccination records"""
        self.load_vaccinations()

    def load_vaccinations(self, student_filter=""):
        """Load vaccination records with optional student filter"""
        for item in self.vax_tree.get_children():
            self.vax_tree.delete(item)

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            query = '''
                SELECT vr.id, vr.student_id, vr.vaccine_name, vr.administered_date,
                       vr.administered_by, vr.adverse_reaction
                FROM vaccination_records vr
                WHERE 1=1
            '''
            params = []

            if student_filter:
                query += " AND vr.student_id LIKE ?"
                params.append(f"%{escape_like(student_filter)}%")

            if not self.auth.check_permission('view_any_health_record') and self.auth.current_user['role'] == 'student':
                query += " AND vr.student_id = ?"
                params.append(self.auth.current_user['id'])

            query += " ORDER BY vr.administered_date DESC LIMIT 100"

            cursor.execute(query, params)
            records = cursor.fetchall()

            for record in records:
                adverse = "Yes" if record[5] else "No"
                self.vax_tree.insert('', tk.END, values=(
                    record[0], record[1], record[2], record[3], record[4], adverse
                ))

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load vaccination records: {str(e)}")

    def view_vaccination_details(self):
        """View details of selected vaccination record"""
        selection = self.vax_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a vaccination record to view.")
            return

        record_id = self.vax_tree.item(selection[0])['values'][0]

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT vr.student_id, s.first_name, s.last_name, vr.vaccine_name,
                       vr.administered_date, vr.expiry_date, vr.lot_number,
                       vr.manufacturer, vr.administered_by, vr.location,
                       vr.adverse_reaction, vr.reaction_description,
                       vr.verified, vr.verified_by, vr.verified_date
                FROM vaccination_records vr
                JOIN students s ON vr.student_id = s.student_id
                WHERE vr.id = ?
            ''', (record_id,))
            record = cursor.fetchone()
            conn.close()

            if not record:
                messagebox.showerror("Error", "Vaccination record not found")
                return

            dialog = tk.Toplevel(self.root)
            dialog.title("Vaccination Details")
            dialog.geometry("600x700")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Vaccination Record Details", font=('Arial', 14, 'bold')).pack(pady=10)

            details_frame = ttk.LabelFrame(main_frame, text="Record Information", padding=15)
            details_frame.pack(fill='both', expand=True, pady=10)

            info_text = tk.Text(details_frame, height=25, width=60, wrap='word', font=('Courier', 10))
            info_text.pack(fill='both', expand=True)

            details = f"""
STUDENT INFORMATION
{'='*50}
Student ID:      {record[0]}
Name:            {record[1]} {record[2]}

VACCINE INFORMATION
{'='*50}
Vaccine Name:    {record[3]}
Administered:    {record[4]}
Expiry Date:     {record[5] or 'N/A'}
Lot Number:      {record[6] or 'N/A'}
Manufacturer:    {record[7] or 'N/A'}

ADMINISTRATION DETAILS
{'='*50}
Administered By: {record[8] or 'N/A'}
Location:        {record[9] or 'N/A'}

ADVERSE REACTIONS
{'='*50}
Adverse Reaction: {'Yes' if record[10] else 'No'}
Description:     {record[11] if record[11] else 'None reported'}

VERIFICATION STATUS
{'='*50}
Verified:        {'Yes' if record[12] else 'No'}
Verified By:     {record[13] if record[13] else 'N/A'}
Verified Date:   {record[14] if record[14] else 'N/A'}
"""

            info_text.insert('1.0', details)
            info_text.config(state='disabled')

            ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load vaccination details: {e}")

    def verify_vaccination(self):
        """Verify selected vaccination record"""
        selection = self.vax_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a vaccination record to verify.")
            return

        record_id = self.vax_tree.item(selection[0])['values'][0]

        if messagebox.askyesno("Verify Vaccination", "Verify this vaccination record?"):
            try:
                conn = self.get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE vaccination_records
                    SET verified = 1, verified_by = ?, verified_date = ?
                    WHERE id = ?
                ''', (self.auth.current_user['username'], datetime.now().strftime('%Y-%m-%d'), record_id))

                conn.commit()
                conn.close()

                self.log_audit_event('verify_vaccination', 'vaccination', record_id)
                messagebox.showinfo("Success", "Vaccination record verified successfully!")
                self.load_vaccinations(self.vax_search_student.get().strip())

            except Exception as e:
                messagebox.showerror("Error", f"Failed to verify vaccination: {str(e)}")

    def create_view_vaccination_records(self):
        """View and manage vaccination records"""
        content_frame = ttk.Frame(self.content_area)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        title_label = ttk.Label(content_frame, text="Vaccination Records",
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 20))

        add_frame = ttk.LabelFrame(content_frame, text="Add Vaccination Record", padding=15)
        add_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(add_frame, text="Vaccine Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.vaccine_name = ttk.Combobox(add_frame, width=25, values=[
            "COVID-19", "Influenza (Flu)", "Hepatitis B", "MMR", "Tdap", "Meningococcal", "HPV", "Other"
        ])
        self.vaccine_name.grid(row=0, column=1, sticky=tk.W, padx=(10, 20), pady=5)

        ttk.Label(add_frame, text="Date:").grid(row=0, column=2, sticky=tk.W, pady=5)
        self.vaccine_date = ttk.Entry(add_frame, width=15)
        self.vaccine_date.grid(row=0, column=3, sticky=tk.W, padx=(10, 0), pady=5)
        self.vaccine_date.insert(0, datetime.now().strftime('%Y-%m-%d'))

        ttk.Button(add_frame, text="Add Vaccination",
                  command=self.add_vaccination_record).grid(row=0, column=4, padx=(20, 0))

        status_frame = ttk.LabelFrame(content_frame, text="Current Vaccination Status", padding=15)
        status_frame.pack(fill=tk.BOTH, expand=True)

        self.vaccination_text = scrolledtext.ScrolledText(status_frame, wrap=tk.WORD, height=15)
        self.vaccination_text.pack(fill=tk.BOTH, expand=True)

        self.load_vaccination_display()

    def add_vaccination_record(self):
        """Add a new vaccination record"""
        if not self.vaccine_name.get().strip():
            messagebox.showerror("Validation Error", "Vaccine name is required.")
            return

        if not self.vaccine_date.get().strip():
            messagebox.showerror("Validation Error", "Vaccination date is required.")
            return

        try:
            vac_info = f"Vaccine: {self.vaccine_name.get()}\n"
            vac_info += f"Date: {self.vaccine_date.get()}\n"
            vac_info += "Status: Current\n"
            vac_info += f"Recorded: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            vac_info += "-" * 40 + "\n"

            self.vaccination_text.insert(tk.END, vac_info)

            self.vaccine_name.set('')
            self.vaccine_date.delete(0, tk.END)
            self.vaccine_date.insert(0, datetime.now().strftime('%Y-%m-%d'))

            messagebox.showinfo("Success", "Vaccination record added successfully!")
            self.log_audit_event('add_vaccination', 'vaccination', self.vaccine_name.get())

        except Exception as e:
            messagebox.showerror("Error", f"Failed to add vaccination record: {str(e)}")

    def load_vaccination_display(self):
        """Load and display vaccination records"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                user_id = None
                if self.auth and self.auth.current_user:
                    user_id = self.auth.current_user.get('id')

                display_data = "VACCINATION RECORDS\n"
                display_data += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                display_data += "=" * 50 + "\n\n"

                if user_id:
                    cursor.execute("""
                        SELECT vaccine_name, administered_date, manufacturer, lot_number,
                               administered_by, expiry_date, adverse_reaction, reaction_description
                        FROM vaccination_records
                        WHERE student_id = ?
                        ORDER BY administered_date DESC
                    """, (user_id,))
                    vaccination_records = cursor.fetchall()

                    if vaccination_records:
                        display_data += "Your vaccination records:\n\n"
                        for record in vaccination_records:
                            vaccine_name, admin_date, manufacturer, lot_number, admin_by, expiry_date, adverse, reaction_desc = record
                            display_data += f"{vaccine_name}: Administered"
                            if admin_date:
                                display_data += f" (Date: {admin_date})"
                            display_data += "\n"
                            if manufacturer:
                                display_data += f"  Manufacturer: {manufacturer}\n"
                            if admin_by:
                                display_data += f"  Administered by: {admin_by}\n"
                            if expiry_date:
                                display_data += f"  Expires: {expiry_date}\n"
                            if adverse:
                                display_data += "  \u26a0 Adverse reaction reported"
                                if reaction_desc:
                                    display_data += f": {reaction_desc}"
                                display_data += "\n"
                            display_data += "\n"
                    else:
                        cursor.execute("SELECT id FROM students WHERE student_id = ? OR id = ?", (user_id, user_id))
                        if cursor.fetchone():
                            display_data += "No vaccination records found.\n"
                            display_data += "Use the form above to add your vaccination information.\n\n"
                        else:
                            display_data += "User not found in health system.\n"
                else:
                    display_data += "Please log in to view your vaccination records.\n\n"

                display_data += "\nFor official records and updates, contact the health center.\n"
                display_data += "Use the form above to add new vaccination records.\n"

                self.vaccination_text.insert(tk.END, display_data)

        except Exception as e:
            error_msg = "VACCINATION RECORDS\n"
            error_msg += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            error_msg += "=" * 50 + "\n\n"
            error_msg += f"Error loading vaccination records: {str(e)}\n\n"
            error_msg += "Please contact the health center for assistance.\n"
            self.vaccination_text.insert(tk.END, error_msg)
