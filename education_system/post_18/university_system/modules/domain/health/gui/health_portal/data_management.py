import os
import csv
import json
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from datetime import datetime

from education_system.post_18.university_system.core import paths


class DataManagementMixin:
    """Mixin for data export and database backup features."""

    def create_data_management(self):
        """Create data management interface"""
        title = ttk.Label(self.content_frame, text="Data Management", style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)

        notebook = ttk.Notebook(self.content_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        export_tab = ttk.Frame(notebook)
        notebook.add(export_tab, text="Data Export")
        self.create_data_export_form(export_tab)

        backup_tab = ttk.Frame(notebook)
        notebook.add(backup_tab, text="Database Backup")
        self.create_database_backup_form(backup_tab)

        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(1, weight=1)

    def create_data_export_form(self, parent):
        """Create data export form"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        options_frame = ttk.LabelFrame(main_frame, text="Export Options", padding="10")
        options_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(options_frame, text="Data Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.export_data_type = tk.StringVar(value="health_records")
        data_type_combo = ttk.Combobox(options_frame, textvariable=self.export_data_type,
                                      values=['health_records', 'vaccination_records', 'health_appointments',
                                             'students', 'all_data'], state='readonly')
        data_type_combo.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(options_frame, text="Format:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.export_format = tk.StringVar(value="CSV")
        format_combo = ttk.Combobox(options_frame, textvariable=self.export_format,
                                   values=['CSV', 'JSON'], state='readonly')
        format_combo.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(options_frame, text="Date From (optional):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.export_date_from = tk.StringVar()
        ttk.Entry(options_frame, textvariable=self.export_date_from, width=15).grid(row=2, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(options_frame, text="Date To (optional):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.export_date_to = tk.StringVar()
        ttk.Entry(options_frame, textvariable=self.export_date_to, width=15).grid(row=3, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Button(options_frame, text="Export Data", command=self.export_data).grid(row=4, column=0, columnspan=2, pady=15)

        log_frame = ttk.LabelFrame(main_frame, text="Export Log", padding="10")
        log_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.export_log_text = scrolledtext.ScrolledText(log_frame, width=70, height=15)
        self.export_log_text.pack(fill=tk.BOTH, expand=True)

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

    def export_data(self):
        """Export data based on selected options"""
        try:
            data_type = self.export_data_type.get()
            export_format = self.export_format.get()
            date_from = self.export_date_from.get().strip()
            date_to = self.export_date_to.get().strip()

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            extension = '.csv' if export_format == 'CSV' else '.json'
            default_filename = f"{data_type}_export_{timestamp}{extension}"

            filename = filedialog.asksaveasfilename(
                initialfile=default_filename,
                defaultextension=extension,
                filetypes=[("CSV files", "*.csv"), ("JSON files", "*.json"), ("All files", "*.*")],
                title="Save Export File"
            )

            if not filename:
                return

            self.export_log_text.insert(tk.END, f"Starting export of {data_type} to {filename}...\n")
            self.export_log_text.see(tk.END)
            self.root.update()

            conn = self.get_connection()
            cursor = conn.cursor()

            if data_type == 'health_records':
                query = '''
                    SELECT hr.id, hr.student_id, s.first_name, s.last_name, hr.record_type,
                           hr.record_date, hr.provider, hr.description, hr.confidential, hr.created_at
                    FROM health_records hr
                    JOIN students s ON hr.student_id = s.student_id
                '''
                headers = ['ID', 'Student ID', 'First Name', 'Last Name', 'Record Type',
                          'Record Date', 'Provider', 'Description', 'Confidential', 'Created At']
                date_column = 'hr.record_date'

            elif data_type == 'vaccination_records':
                query = '''
                    SELECT vr.id, vr.student_id, s.first_name, s.last_name, vr.vaccine_name,
                           vr.administered_date, vr.lot_number, vr.manufacturer, vr.administered_by,
                           vr.adverse_reaction, vr.verified, vr.created_at
                    FROM vaccination_records vr
                    JOIN students s ON vr.student_id = s.student_id
                '''
                headers = ['ID', 'Student ID', 'First Name', 'Last Name', 'Vaccine Name',
                          'Administered Date', 'Lot Number', 'Manufacturer', 'Administered By',
                          'Adverse Reaction', 'Verified', 'Created At']
                date_column = 'vr.administered_date'

            elif data_type == 'health_appointments':
                query = '''
                    SELECT ha.id, ha.student_id, s.first_name, s.last_name, ha.appointment_type,
                           ha.appointment_date, ha.appointment_time, ha.provider, ha.reason,
                           ha.status, ha.scheduled_at
                    FROM health_appointments ha
                    JOIN students s ON ha.student_id = s.student_id
                '''
                headers = ['ID', 'Student ID', 'First Name', 'Last Name', 'Appointment Type',
                          'Appointment Date', 'Appointment Time', 'Provider', 'Reason',
                          'Status', 'Scheduled At']
                date_column = 'ha.appointment_date'

            elif data_type == 'students':
                query = '''
                    SELECT student_id, first_name, last_name, age, gender, email_address
                    FROM students
                '''
                headers = ['Student ID', 'First Name', 'Last Name', 'Age', 'Gender', 'Email']
                date_column = None

            params = []
            if date_column and (date_from or date_to):
                if date_from and date_to:
                    query += f" WHERE {date_column} BETWEEN ? AND ?"
                    params = [date_from, date_to]
                elif date_from:
                    query += f" WHERE {date_column} >= ?"
                    params = [date_from]
                elif date_to:
                    query += f" WHERE {date_column} <= ?"
                    params = [date_to]

            query += " ORDER BY " + (date_column or headers[0])

            cursor.execute(query, params)
            data = cursor.fetchall()

            self.export_log_text.insert(tk.END, f"Retrieved {len(data)} records...\n")
            self.export_log_text.see(tk.END)
            self.root.update()

            if export_format == 'CSV':
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(headers)
                    writer.writerows(data)

            elif export_format == 'JSON':
                json_data = []
                for row in data:
                    record = dict(zip(headers, row))
                    json_data.append(record)

                with open(filename, 'w', encoding='utf-8') as jsonfile:
                    json.dump(json_data, jsonfile, indent=2, default=str)

            conn.close()

            self.export_log_text.insert(tk.END, "Export completed successfully!\n")
            self.export_log_text.insert(tk.END, f"File saved: {filename}\n")
            self.export_log_text.insert(tk.END, f"Records exported: {len(data)}\n\n")
            self.export_log_text.see(tk.END)

            self.log_audit_event('export_data', 'data_export', filename, f"Type: {data_type}, Format: {export_format}")
            messagebox.showinfo("Success", f"Data exported successfully to {filename}")

        except Exception as e:
            error_msg = f"Export failed: {str(e)}\n\n"
            self.export_log_text.insert(tk.END, error_msg)
            self.export_log_text.see(tk.END)
            messagebox.showerror("Error", f"Failed to export data: {str(e)}")

    def create_database_backup_form(self, parent):
        """Create database backup form"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        options_frame = ttk.LabelFrame(main_frame, text="Backup Options", padding="10")
        options_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(options_frame, text="Backup Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.backup_type = tk.StringVar(value="Full Backup")
        backup_type_combo = ttk.Combobox(options_frame, textvariable=self.backup_type,
                                        values=['Full Backup', 'Data Only', 'Schema Only'], state='readonly')
        backup_type_combo.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(options_frame, text="Backup Location:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.backup_location = tk.StringVar(value=str(paths.BACKUP_HEALTH_DIR / ""))

        location_frame = ttk.Frame(options_frame)
        location_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))

        ttk.Entry(location_frame, textvariable=self.backup_location, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(location_frame, text="Browse", command=self.browse_backup_location).pack(side=tk.RIGHT, padx=(5, 0))

        ttk.Button(options_frame, text="Create Backup", command=self.create_backup).grid(row=2, column=0, columnspan=2, pady=15)

        log_frame = ttk.LabelFrame(main_frame, text="Backup Log", padding="10")
        log_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.backup_log_text = scrolledtext.ScrolledText(log_frame, width=70, height=15)
        self.backup_log_text.pack(fill=tk.BOTH, expand=True)

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        options_frame.columnconfigure(1, weight=1)
        location_frame.columnconfigure(0, weight=1)

        self.backup_log_text.insert(tk.END, "Ready to create database backup...\n")

    def browse_backup_location(self):
        """Browse for backup location"""
        location = filedialog.askdirectory(initialdir=self.backup_location.get())
        if location:
            self.backup_location.set(location + "/")

    def create_backup(self):
        """Create database backup"""
        try:
            backup_dir = self.backup_location.get()
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"health_portal_backup_{timestamp}.sql"
            backup_path = os.path.join(backup_dir, backup_filename)

            self.backup_log_text.insert(tk.END, f"Starting backup to {backup_path}...\n")
            self.backup_log_text.see(tk.END)
            self.root.update()

            source_db = str(paths.DEFAULT_DB_PATH)
            if os.path.exists(source_db):
                import shutil
                backup_db_path = os.path.join(backup_dir, f"student_records_backup_{timestamp}.db")
                shutil.copy2(source_db, backup_db_path)

                conn = self.get_connection()
                with open(backup_path, 'w', encoding='utf-8') as f:
                    for line in conn.iterdump():
                        f.write('%s\n' % line)
                conn.close()

                file_size = os.path.getsize(backup_path) / 1024

                self.backup_log_text.insert(tk.END, "Backup completed successfully!\n")
                self.backup_log_text.insert(tk.END, f"SQL dump: {backup_path}\n")
                self.backup_log_text.insert(tk.END, f"Database copy: {backup_db_path}\n")
                self.backup_log_text.insert(tk.END, f"Size: {file_size:.1f} KB\n\n")
                self.backup_log_text.see(tk.END)

                self.log_audit_event('create_backup', 'database_backup', backup_path)
                messagebox.showinfo("Success", f"Database backup created successfully!\n\n"
                                  f"SQL dump: {backup_path}\n"
                                  f"Database copy: {backup_db_path}")

            else:
                raise Exception("Database file not found")

        except Exception as e:
            error_msg = f"Backup failed: {str(e)}\n\n"
            self.backup_log_text.insert(tk.END, error_msg)
            self.backup_log_text.see(tk.END)
            messagebox.showerror("Error", f"Failed to create backup: {str(e)}")
