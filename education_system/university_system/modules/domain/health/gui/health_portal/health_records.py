import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from education_system.university_system.modules.shared.utils.i18n import get_text as _t


class HealthRecordsMixin:
    """Mixin for health records CRUD operations."""

    def create_manage_health_records(self):
        """Create health records management interface"""
        title = ttk.Label(self.content_frame, text=_t("health_portal.labels.records_management"), style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)

        notebook = ttk.Notebook(self.content_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        add_tab = ttk.Frame(notebook)
        notebook.add(add_tab, text=_t("health_portal.tabs.add_record"))
        self.create_add_health_record_form(add_tab)

        view_tab = ttk.Frame(notebook)
        notebook.add(view_tab, text=_t("health_portal.tabs.view_records"))
        self.create_view_health_records_form(view_tab)

        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(1, weight=1)

    def create_add_health_record_form(self, parent):
        """Create form for adding health records"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        ttk.Label(main_frame, text=_t("health_portal.labels.student_id")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.hr_student_id = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.hr_student_id, width=20).grid(row=0, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(main_frame, text=_t("health_portal.labels.record_type")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.hr_record_type = tk.StringVar()
        record_type_combo = ttk.Combobox(main_frame, textvariable=self.hr_record_type,
                                        values=['General Medical', 'Annual Physical', 'Illness Treatment',
                                               'Injury Treatment', 'Mental Health', 'Vaccination', 'Other'])
        record_type_combo.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(main_frame, text=_t("health_portal.labels.record_date")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.hr_record_date = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(main_frame, textvariable=self.hr_record_date, width=20).grid(row=2, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(main_frame, text=_t("health_portal.labels.provider")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.hr_provider = tk.StringVar(value=f"Dr. {self.auth.current_user['username']}")
        ttk.Entry(main_frame, textvariable=self.hr_provider, width=30).grid(row=3, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(main_frame, text=_t("health_portal.labels.description")).grid(row=4, column=0, sticky=(tk.W, tk.N), pady=5)
        self.hr_description = tk.Text(main_frame, width=50, height=6)
        self.hr_description.grid(row=4, column=1, pady=5, padx=(5, 0))

        ttk.Label(main_frame, text=_t("health_portal.labels.confidential")).grid(row=5, column=0, sticky=tk.W, pady=5)
        self.hr_confidential = tk.BooleanVar()
        ttk.Checkbutton(main_frame, variable=self.hr_confidential).grid(row=5, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text=_t("health_portal.buttons.save_record"), command=self.save_health_record).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("health_portal.buttons.clear_form"), command=self.clear_health_record_form).pack(side=tk.LEFT, padx=5)

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

    def save_health_record(self):
        """Save health record to database"""
        try:
            if not self.hr_student_id.get().strip():
                messagebox.showerror("Error", "Student ID is required")
                return

            if not self.hr_record_type.get().strip():
                messagebox.showerror("Error", "Record type is required")
                return

            if not self.hr_description.get(1.0, tk.END).strip():
                messagebox.showerror("Error", "Description is required")
                return

            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (self.hr_student_id.get().strip(),))
            if cursor.fetchone()[0] == 0:
                messagebox.showerror("Error", "Student ID not found")
                conn.close()
                return

            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO health_records
                (student_id, record_type, record_date, provider, description, confidential, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.hr_student_id.get().strip(),
                self.hr_record_type.get(),
                self.hr_record_date.get(),
                self.hr_provider.get(),
                self.hr_description.get(1.0, tk.END).strip(),
                1 if self.hr_confidential.get() else 0,
                created_at
            ))

            conn.commit()
            record_id = cursor.lastrowid

            cursor.execute("SELECT first_name, last_name, email_address FROM students WHERE student_id = ?",
                          (self.hr_student_id.get().strip(),))
            patient_info = cursor.fetchone()

            conn.close()

            if patient_info:
                patient_name = f"{patient_info[0]} {patient_info[1]}"
                patient_email = patient_info[2]
                record_type = self.hr_record_type.get()
                self.send_health_record_creation_confirmation(patient_email, patient_name, record_type)

            self.log_audit_event('add_health_record', 'health_record', record_id)
            messagebox.showinfo("Success", "Health record added successfully!\nConfirmation email sent.")
            self.clear_health_record_form()

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")

    def clear_health_record_form(self):
        """Clear the health record form"""
        self.hr_student_id.set("")
        self.hr_record_type.set("")
        self.hr_record_date.set(datetime.now().strftime('%Y-%m-%d'))
        self.hr_provider.set(f"Dr. {self.auth.current_user['username']}")
        self.hr_description.delete(1.0, tk.END)
        self.hr_confidential.set(False)

    def create_view_health_records_form(self, parent):
        """Create interface for viewing health records"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        search_frame = ttk.LabelFrame(main_frame, text=_t("health_portal.labels.search_filters"), padding="5")
        search_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(search_frame, text=_t("health_portal.labels.student_id")).grid(row=0, column=0, sticky=tk.W, pady=2)
        self.hr_search_student = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.hr_search_student, width=20).grid(row=0, column=1, sticky=tk.W, pady=2, padx=(5, 10))

        ttk.Label(search_frame, text=_t("health_portal.labels.date_from")).grid(row=0, column=2, sticky=tk.W, pady=2)
        self.hr_search_date_from = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.hr_search_date_from, width=12).grid(row=0, column=3, sticky=tk.W, pady=2, padx=(5, 10))

        ttk.Label(search_frame, text=_t("health_portal.labels.date_to")).grid(row=0, column=4, sticky=tk.W, pady=2)
        self.hr_search_date_to = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.hr_search_date_to, width=12).grid(row=0, column=5, sticky=tk.W, pady=2, padx=(5, 10))

        ttk.Button(search_frame, text=_t("health_portal.buttons.search"), command=self.search_health_records).grid(row=0, column=6, padx=10)

        tree_frame = ttk.Frame(main_frame)
        tree_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        columns = ('ID', 'Student ID', 'Type', 'Date', 'Provider', 'Confidential')
        self.hr_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.hr_tree.heading(col, text=col)
            if col == 'ID':
                self.hr_tree.column(col, width=50)
            elif col in ['Student ID', 'Type', 'Provider']:
                self.hr_tree.column(col, width=120)
            elif col == 'Date':
                self.hr_tree.column(col, width=100)
            else:
                self.hr_tree.column(col, width=80)

        self.hr_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.hr_tree.yview)
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.hr_tree.configure(yscrollcommand=v_scrollbar.set)

        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.hr_tree.xview)
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.hr_tree.configure(xscrollcommand=h_scrollbar.set)

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=2, column=0, pady=10)

        ttk.Button(buttons_frame, text=_t("health_portal.buttons.view_details"), command=self.view_health_record_details).pack(side=tk.LEFT, padx=5)
        if self.auth.check_permission('manage_health_records'):
            ttk.Button(buttons_frame, text=_t("health_portal.buttons.update"), command=self.update_health_record).pack(side=tk.LEFT, padx=5)
            ttk.Button(buttons_frame, text=_t("health_portal.buttons.delete"), command=self.delete_health_record).pack(side=tk.LEFT, padx=5)

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self.search_health_records()

    def search_health_records(self):
        """Search and load health records"""
        for item in self.hr_tree.get_children():
            self.hr_tree.delete(item)

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            query = '''
                SELECT hr.id, hr.student_id, hr.record_type, hr.record_date,
                       hr.provider, hr.confidential
                FROM health_records hr
                JOIN students s ON hr.student_id = s.student_id
                WHERE 1=1
            '''

            params = []

            if self.hr_search_student.get().strip():
                query += " AND hr.student_id LIKE ?"
                params.append(f"%{self.hr_search_student.get().strip()}%")

            if self.hr_search_date_from.get().strip():
                query += " AND hr.record_date >= ?"
                params.append(self.hr_search_date_from.get().strip())

            if self.hr_search_date_to.get().strip():
                query += " AND hr.record_date <= ?"
                params.append(self.hr_search_date_to.get().strip())

            if not self.auth.check_permission('view_any_health_record'):
                if self.auth.current_user['role'] == 'student':
                    query += " AND hr.student_id = ?"
                    params.append(self.auth.current_user['id'])
                else:
                    query += " AND hr.confidential = 0"

            query += " ORDER BY hr.record_date DESC, hr.id DESC LIMIT 100"

            cursor.execute(query, params)
            records = cursor.fetchall()

            for record in records:
                confidential = "Yes" if record[5] else "No"
                self.hr_tree.insert('', tk.END, values=(
                    record[0], record[1], record[2], record[3], record[4], confidential
                ))

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load health records: {str(e)}")

    def view_health_record_details(self):
        """Show detailed view of selected health record"""
        selection = self.hr_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a record to view.")
            return

        record_id = self.hr_tree.item(selection[0])['values'][0]

        details_window = tk.Toplevel(self.root)
        details_window.title("Health Record Details")
        details_window.geometry("600x500")
        details_window.transient(self.root)
        details_window.grab_set()

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT hr.id, hr.student_id, s.first_name, s.last_name, hr.record_type,
                       hr.record_date, hr.provider, hr.description, hr.confidential, hr.created_at
                FROM health_records hr
                JOIN students s ON hr.student_id = s.student_id
                WHERE hr.id = ?
            ''', (record_id,))

            record = cursor.fetchone()
            conn.close()

            if not record:
                messagebox.showerror("Error", "Record not found")
                details_window.destroy()
                return

            main_frame = ttk.Frame(details_window, padding="20")
            main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

            ttk.Label(main_frame, text=_t("health_portal.labels.health_record_details"), style='Title.TLabel').grid(row=0, column=0, columnspan=2, pady=10)

            fields = [
                (_t("health_portal.fields.record_id"), record[0]),
                (_t("health_portal.fields.student_id"), record[1]),
                (_t("health_portal.fields.student_name"), f"{record[2]} {record[3]}"),
                (_t("health_portal.fields.record_type"), record[4]),
                (_t("health_portal.fields.date"), record[5]),
                (_t("health_portal.fields.provider"), record[6]),
                (_t("health_portal.fields.confidential"), _t("common.yes") if record[8] else _t("common.no")),
                (_t("health_portal.fields.created"), record[9])
            ]

            row = 1
            for label, value in fields:
                ttk.Label(main_frame, text=label, font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky=tk.W, pady=5)
                ttk.Label(main_frame, text=str(value)).grid(row=row, column=1, sticky=tk.W, pady=5, padx=(10, 0))
                row += 1

            ttk.Label(main_frame, text=_t("health_portal.fields.description"), font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky=(tk.W, tk.N), pady=5)

            desc_frame = ttk.Frame(main_frame)
            desc_frame.grid(row=row, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5, padx=(10, 0))

            desc_text = tk.Text(desc_frame, width=50, height=8, state=tk.DISABLED, wrap=tk.WORD)
            desc_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

            desc_scroll = ttk.Scrollbar(desc_frame, orient=tk.VERTICAL, command=desc_text.yview)
            desc_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
            desc_text.configure(yscrollcommand=desc_scroll.set)

            desc_text.config(state=tk.NORMAL)
            desc_text.insert(1.0, record[7] or _t("health_portal.messages.no_description"))
            desc_text.config(state=tk.DISABLED)

            ttk.Button(main_frame, text=_t("common.close"), command=details_window.destroy).grid(row=row+1, column=0, columnspan=2, pady=20)

            details_window.columnconfigure(0, weight=1)
            details_window.rowconfigure(0, weight=1)
            main_frame.columnconfigure(1, weight=1)
            desc_frame.columnconfigure(0, weight=1)
            desc_frame.rowconfigure(0, weight=1)

        except Exception as e:
            messagebox.showerror(_t("common.error"), f"{_t('health_portal.messages.load_details_failed')}: {str(e)}")
            details_window.destroy()

    def update_health_record(self):
        """Update selected health record"""
        selection = self.hr_tree.selection()
        if not selection:
            messagebox.showwarning(_t("health_portal.messages.no_selection"), _t("health_portal.messages.select_record_to_update"))
            return

        record_id = self.hr_tree.item(selection[0])['values'][0]

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT student_id, record_type, record_date, description, provider, confidential
                FROM health_records
                WHERE id = ?
            ''', (record_id,))
            record = cursor.fetchone()

            if not record:
                messagebox.showerror(_t("common.error"), _t("health_portal.messages.record_not_found"))
                conn.close()
                return

            dialog = tk.Toplevel(self.root)
            dialog.title(_t("health_portal.dialogs.update_health_record"))
            dialog.geometry("600x500")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=_t("health_portal.dialogs.update_health_record"), font=('Arial', 12, 'bold')).pack(pady=10)

            form_frame = ttk.Frame(main_frame)
            form_frame.pack(fill='both', expand=True, pady=10)

            ttk.Label(form_frame, text=_t("health_portal.labels.student_id")).grid(row=0, column=0, sticky='w', pady=5)
            student_id_label = ttk.Label(form_frame, text=record[0], font=('Arial', 10, 'bold'))
            student_id_label.grid(row=0, column=1, sticky='w', pady=5)

            ttk.Label(form_frame, text=_t("health_portal.labels.record_type_required")).grid(row=1, column=0, sticky='w', pady=5)
            record_type_var = tk.StringVar(value=record[1])
            record_type_combo = ttk.Combobox(form_frame, textvariable=record_type_var,
                                            values=[_t("health_portal.record_types.checkup"), _t("health_portal.record_types.vaccination"), _t("health_portal.record_types.emergency"), _t("health_portal.record_types.prescription"),
                                                   _t("health_portal.record_types.lab_result"), _t("health_portal.record_types.consultation"), _t("health_portal.record_types.treatment"), _t("health_portal.record_types.other")],
                                            width=30)
            record_type_combo.grid(row=1, column=1, pady=5, padx=10)

            ttk.Label(form_frame, text=_t("health_portal.labels.record_date_required")).grid(row=2, column=0, sticky='w', pady=5)
            date_var = tk.StringVar(value=record[2])
            date_entry = ttk.Entry(form_frame, textvariable=date_var, width=32)
            date_entry.grid(row=2, column=1, pady=5, padx=10)

            ttk.Label(form_frame, text=_t("health_portal.labels.description")).grid(row=3, column=0, sticky='nw', pady=5)
            description_text = tk.Text(form_frame, width=32, height=8)
            description_text.grid(row=3, column=1, pady=5, padx=10)
            if record[3]:
                description_text.insert("1.0", record[3])

            ttk.Label(form_frame, text=_t("health_portal.labels.provider")).grid(row=4, column=0, sticky='w', pady=5)
            provider_var = tk.StringVar(value=record[4] or "")
            provider_entry = ttk.Entry(form_frame, textvariable=provider_var, width=32)
            provider_entry.grid(row=4, column=1, pady=5, padx=10)

            confidential_var = tk.BooleanVar(value=bool(record[5]))
            ttk.Checkbutton(form_frame, text=_t("health_portal.labels.confidential"), variable=confidential_var).grid(
                row=5, column=0, columnspan=2, sticky='w', pady=5
            )

            def save_updates():
                try:
                    cursor.execute('''
                        UPDATE health_records
                        SET record_type = ?, record_date = ?, description = ?,
                            provider = ?, confidential = ?
                        WHERE id = ?
                    ''', (
                        record_type_var.get(),
                        date_var.get(),
                        description_text.get("1.0", tk.END).strip(),
                        provider_var.get(),
                        1 if confidential_var.get() else 0,
                        record_id
                    ))

                    conn.commit()
                    conn.close()
                    messagebox.showinfo(_t("common.success"), _t("health_portal.messages.record_updated"))
                    self.search_health_records()
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror(_t("common.error"), f"{_t('health_portal.messages.update_failed')}: {e}")
                    if conn:
                        conn.close()

            def on_cancel():
                conn.close()
                dialog.destroy()

            buttons_frame = ttk.Frame(main_frame)
            buttons_frame.pack(pady=10)

            ttk.Button(buttons_frame, text=_t("common.save"), command=save_updates).pack(side='left', padx=5)
            ttk.Button(buttons_frame, text=_t("common.cancel"), command=on_cancel).pack(side='left', padx=5)

            dialog.protocol("WM_DELETE_WINDOW", on_cancel)

        except Exception as e:
            messagebox.showerror(_t("common.error"), f"{_t('health_portal.messages.load_record_failed')}: {e}")

    def delete_health_record(self):
        """Delete selected health record"""
        selection = self.hr_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a record to delete.")
            return

        record_id = self.hr_tree.item(selection[0])['values'][0]

        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this health record?"):
            try:
                conn = self.get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT hr.record_type, hr.student_id, s.first_name, s.last_name, s.email_address
                    FROM health_records hr
                    JOIN students s ON hr.student_id = s.student_id
                    WHERE hr.id = ?
                ''', (record_id,))

                record_info = cursor.fetchone()

                cursor.execute('DELETE FROM health_records WHERE id = ?', (record_id,))
                conn.commit()
                conn.close()

                if record_info:
                    patient_name = f"{record_info[2]} {record_info[3]}"
                    patient_email = record_info[4]
                    record_type = record_info[0]
                    self.send_health_record_deletion_confirmation(patient_email, patient_name, record_type)

                self.log_audit_event('delete_health_record', 'health_record', record_id)
                messagebox.showinfo("Success", "Health record deleted successfully!\nConfirmation email sent.")
                self.search_health_records()

            except Exception as e:
                messagebox.showerror(_t("common.error"), f"{_t('health_portal.messages.delete_failed')}: {str(e)}")
