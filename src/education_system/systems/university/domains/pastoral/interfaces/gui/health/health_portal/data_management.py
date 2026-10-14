
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t
import os
import csv
import json
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog, simpledialog
from datetime import datetime, timedelta

from education_system import paths
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608 - identifier validation


class DataManagementMixin:
    """Mixin for data export and database backup features."""

    def create_data_management(self):
        """Create data management interface"""
        title = ttk.Label(self.content_frame, text=_t('gui.pastoral.health.health_portal.data_management.labels.data_management', default="Data Management"), style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)

        notebook = ttk.Notebook(self.content_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        export_tab = ttk.Frame(notebook)
        notebook.add(export_tab, text=_t('gui.pastoral.health.health_portal.data_management.tabs.data_export', default="Data Export"))
        self.create_data_export_form(export_tab)

        backup_tab = ttk.Frame(notebook)
        notebook.add(backup_tab, text=_t('gui.pastoral.health.health_portal.data_management.tabs.database_backup', default="Database Backup"))
        self.create_database_backup_form(backup_tab)

        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(1, weight=1)

    def create_data_export_form(self, parent):
        """Create data export form"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        options_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.health.health_portal.data_management.labels.export_options', default="Export Options"), padding="10")
        options_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(options_frame, text=_t('gui.pastoral.health.health_portal.data_management.labels.data_type', default="Data Type:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.export_data_type = tk.StringVar(value=_t('gui.pastoral.health.health_portal.data_management.values.health_records', default="health_records"))
        data_type_combo = ttk.Combobox(options_frame, textvariable=self.export_data_type,
                                      values=['health_records', 'vaccination_records', 'health_appointments',
                                             'students', 'all_data'], state='readonly')
        data_type_combo.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(options_frame, text=_t('gui.pastoral.health.health_portal.data_management.labels.format', default="Format:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.export_format = tk.StringVar(value=_t('gui.pastoral.health.health_portal.data_management.values.csv', default="CSV"))
        format_combo = ttk.Combobox(options_frame, textvariable=self.export_format,
                                   values=['CSV', 'JSON'], state='readonly')
        format_combo.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(options_frame, text=_t('gui.pastoral.health.health_portal.data_management.labels.date_from_optional', default="Date From (optional):")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.export_date_from = tk.StringVar()
        ttk.Entry(options_frame, textvariable=self.export_date_from, width=15).grid(row=2, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(options_frame, text=_t('gui.pastoral.health.health_portal.data_management.labels.date_to_optional', default="Date To (optional):")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.export_date_to = tk.StringVar()
        ttk.Entry(options_frame, textvariable=self.export_date_to, width=15).grid(row=3, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Button(options_frame, text=_t('gui.pastoral.health.health_portal.data_management.buttons.export_data', default="Export Data"), command=self.export_data).grid(row=4, column=0, columnspan=2, pady=15)

        log_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.health.health_portal.data_management.labels.export_log', default="Export Log"), padding="10")
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
                title=_t('gui.pastoral.health.health_portal.data_management.dialogs.save_export_file', default="Save Export File")
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
            messagebox.showinfo(_t('gui.pastoral.health.health_portal.data_management.dialogs.success', default="Success"), f"Data exported successfully to {filename}")

        except Exception as e:
            error_msg = f"Export failed: {str(e)}\n\n"
            self.export_log_text.insert(tk.END, error_msg)
            self.export_log_text.see(tk.END)
            messagebox.showerror(_t('gui.pastoral.health.health_portal.data_management.dialogs.error', default="Error"), f"Failed to export data: {str(e)}")

    def create_database_backup_form(self, parent):
        """Create database backup form"""
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        options_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.health.health_portal.data_management.labels.backup_options', default="Backup Options"), padding="10")
        options_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(options_frame, text=_t('gui.pastoral.health.health_portal.data_management.labels.backup_type', default="Backup Type:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.backup_type = tk.StringVar(value=_t('gui.pastoral.health.health_portal.data_management.values.full_backup', default="Full Backup"))
        backup_type_combo = ttk.Combobox(options_frame, textvariable=self.backup_type,
                                        values=['Full Backup', 'Data Only', 'Schema Only'], state='readonly')
        backup_type_combo.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        ttk.Label(options_frame, text=_t('gui.pastoral.health.health_portal.data_management.labels.backup_location', default="Backup Location:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.backup_location = tk.StringVar(value=str(paths.UNIVERSITY_BACKUP_HEALTH_DIR / ""))

        location_frame = ttk.Frame(options_frame)
        location_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))

        ttk.Entry(location_frame, textvariable=self.backup_location, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(location_frame, text=_t('gui.pastoral.health.health_portal.data_management.buttons.browse', default="Browse"), command=self.browse_backup_location).pack(side=tk.RIGHT, padx=(5, 0))

        ttk.Button(options_frame, text=_t('gui.pastoral.health.health_portal.data_management.buttons.create_backup', default="Create Backup"), command=self.create_backup).grid(row=2, column=0, columnspan=2, pady=15)

        log_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.health.health_portal.data_management.labels.backup_log', default="Backup Log"), padding="10")
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

            source_db = str(paths.UNIVERSITY_DEFAULT_DB_PATH)
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
                messagebox.showinfo(_t('gui.pastoral.health.health_portal.data_management.dialogs.success', default="Success"), f"Database backup created successfully!\n\n"
                                  f"SQL dump: {backup_path}\n"
                                  f"Database copy: {backup_db_path}")

            else:
                raise Exception("Database file not found")

        except Exception as e:
            error_msg = f"Backup failed: {str(e)}\n\n"
            self.backup_log_text.insert(tk.END, error_msg)
            self.backup_log_text.see(tk.END)
            messagebox.showerror(_t('gui.pastoral.health.health_portal.data_management.dialogs.error', default="Error"), f"Failed to create backup: {str(e)}")


class IntegrationManagementMixin:
    """Integration logs and sync-queue status.

    The GUI had no view of either, so the only way to see whether the lab /
    insurance integrations were working was the CLI — where both screens were
    broken until recently. Both queries below are the corrected ones from
    ``portal/data_privacy/integrations.py``:

    * ``integration_logs`` has no ``level`` column; severity lives in
      ``status``, and ``system`` is an optional vendor name that is often
      NULL, so ``provider`` is the identifier to lead with.
    * ``sync_queue`` has no ``system`` column and never holds the status
      ``'synced'`` — it writes pending/locked/failed/done.
    """

    INTEGRATION_LOG_LIMIT = 200
    _SYNC_DONE_STATUSES = ("done", "synced", "completed")

    def create_integration_management(self):
        """Create the integration management interface."""
        title = ttk.Label(self.content_frame,
                          text=_t('gui.pastoral.health.health_portal.data_management.labels.integration_management',
                                  default="Integration Management"),
                          style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)

        notebook = ttk.Notebook(self.content_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        logs_tab = ttk.Frame(notebook)
        notebook.add(logs_tab, text=_t('gui.pastoral.health.health_portal.data_management.tabs.integration_logs',
                                       default="Integration Logs"))
        self.create_integration_logs_view(logs_tab)

        sync_tab = ttk.Frame(notebook)
        notebook.add(sync_tab, text=_t('gui.pastoral.health.health_portal.data_management.tabs.sync_status',
                                       default="Data Sync Status"))
        self.create_sync_status_view(sync_tab)

        conn_tab = ttk.Frame(notebook)
        notebook.add(conn_tab, text=_t('gui.pastoral.health.health_portal.data_management.tabs.connections',
                                       default="Connections"))
        self.create_external_connections_view(conn_tab)

        keys_tab = ttk.Frame(notebook)
        notebook.add(keys_tab, text=_t('gui.pastoral.health.health_portal.data_management.tabs.api_keys',
                                       default="API Keys"))
        self.create_api_keys_view(keys_tab)

        lab_tab = ttk.Frame(notebook)
        notebook.add(lab_tab, text=_t('gui.pastoral.health.health_portal.data_management.tabs.laboratory',
                                      default="Laboratory"))
        self.create_lab_events_view(lab_tab)

        insurance_tab = ttk.Frame(notebook)
        notebook.add(insurance_tab, text=_t('gui.pastoral.health.health_portal.data_management.tabs.insurance',
                                            default="Insurance"))
        self.create_insurance_events_view(insurance_tab)

        health_tab = ttk.Frame(notebook)
        notebook.add(health_tab, text=_t('gui.pastoral.health.health_portal.data_management.tabs.health_check',
                                         default="Health Check"))
        self.create_integration_health_view(health_tab)

        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(1, weight=1)

    # ------------------------------------------------------------------
    # Integration logs
    # ------------------------------------------------------------------
    def create_integration_logs_view(self, parent):
        frame = ttk.Frame(parent, padding="10")
        frame.pack(fill='both', expand=True)

        controls = ttk.Frame(frame)
        controls.pack(fill='x', pady=(0, 8))

        ttk.Label(controls, text=_t('gui.pastoral.health.health_portal.data_management.labels.status_filter',
                                    default="Status:")).pack(side='left')
        self.integration_status_filter = ttk.Combobox(
            controls, width=14, state='readonly',
            values=['All', 'success', 'error', 'pending'])
        self.integration_status_filter.set('All')
        self.integration_status_filter.pack(side='left', padx=(6, 14))

        ttk.Button(controls, text=_t('gui.pastoral.health.health_portal.data_management.buttons.refresh',
                                     default="Refresh"),
                   command=self.refresh_integration_logs).pack(side='left')

        self.integration_summary_label = ttk.Label(controls, text="")
        self.integration_summary_label.pack(side='right')

        columns = ('When', 'Source', 'Event', 'Status', 'Message')
        self.integration_logs_tree = ttk.Treeview(frame, columns=columns,
                                                  show='headings', height=18)
        widths = {'When': 150, 'Source': 120, 'Event': 150, 'Status': 90, 'Message': 420}
        for col in columns:
            self.integration_logs_tree.heading(col, text=col)
            self.integration_logs_tree.column(col, width=widths[col])

        scroll = ttk.Scrollbar(frame, orient='vertical',
                               command=self.integration_logs_tree.yview)
        self.integration_logs_tree.configure(yscrollcommand=scroll.set)
        self.integration_logs_tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

        # Errors stand out — that is the whole point of looking at this screen.
        self.integration_logs_tree.tag_configure('error', foreground='#b00020')
        self.integration_logs_tree.tag_configure('pending', foreground='#8a6d00')

        self.refresh_integration_logs()

    def refresh_integration_logs(self):
        tree = getattr(self, 'integration_logs_tree', None)
        if tree is None:
            return
        for item in tree.get_children():
            tree.delete(item)

        try:
            conn = self.get_connection()
            try:
                if not self._table_exists(conn, 'integration_logs'):
                    self.integration_summary_label.config(
                        text="No integration_logs table.")
                    return

                status_filter = self.integration_status_filter.get()
                query = (
                    "SELECT created_at, COALESCE(provider, system, 'unknown'),"
                    "       COALESCE(event_type, ''), COALESCE(status, '-'),"
                    "       COALESCE(message, '')"
                    " FROM integration_logs")
                params = []
                if status_filter and status_filter != 'All':
                    query += " WHERE status = ?"
                    params.append(status_filter)
                query += " ORDER BY created_at DESC LIMIT ?"
                params.append(self.INTEGRATION_LOG_LIMIT)

                rows = conn.execute(query, params).fetchall()
                errors = 0
                for when, source, event, status, message in rows:
                    tags = ()
                    if (status or '').lower() == 'error':
                        tags = ('error',)
                        errors += 1
                    elif (status or '').lower() == 'pending':
                        tags = ('pending',)
                    tree.insert('', 'end',
                                values=(when, source, event, status, message),
                                tags=tags)

                if rows:
                    self.integration_summary_label.config(
                        text=f"{len(rows)} entr{'y' if len(rows) == 1 else 'ies'}"
                             + (f" · {errors} error(s)" if errors else ""))
                else:
                    self.integration_summary_label.config(
                        text="No integration log entries recorded yet.")
            finally:
                conn.close()
        except Exception as exc:
            messagebox.showerror(
                _t('gui.pastoral.health.health_portal.data_management.dialogs.error', default="Error"),
                f"Failed to load integration logs: {exc}")

    # ------------------------------------------------------------------
    # Sync queue
    # ------------------------------------------------------------------
    def create_sync_status_view(self, parent):
        frame = ttk.Frame(parent, padding="10")
        frame.pack(fill='both', expand=True)

        controls = ttk.Frame(frame)
        controls.pack(fill='x', pady=(0, 8))
        ttk.Button(controls, text=_t('gui.pastoral.health.health_portal.data_management.buttons.refresh',
                                     default="Refresh"),
                   command=self.refresh_sync_status).pack(side='left')
        self.sync_summary_label = ttk.Label(controls, text="")
        self.sync_summary_label.pack(side='right')

        columns = ('Queue', 'Status', 'Items', 'Oldest')
        self.sync_status_tree = ttk.Treeview(frame, columns=columns,
                                             show='headings', height=16)
        widths = {'Queue': 200, 'Status': 140, 'Items': 90, 'Oldest': 180}
        for col in columns:
            self.sync_status_tree.heading(col, text=col)
            self.sync_status_tree.column(col, width=widths[col])

        scroll = ttk.Scrollbar(frame, orient='vertical',
                               command=self.sync_status_tree.yview)
        self.sync_status_tree.configure(yscrollcommand=scroll.set)
        self.sync_status_tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

        self.sync_status_tree.tag_configure('failed', foreground='#b00020')

        self.refresh_sync_status()

    def refresh_sync_status(self):
        tree = getattr(self, 'sync_status_tree', None)
        if tree is None:
            return
        for item in tree.get_children():
            tree.delete(item)

        try:
            conn = self.get_connection()
            try:
                if not self._table_exists(conn, 'sync_queue'):
                    self.sync_summary_label.config(text="No sync_queue table.")
                    return

                placeholders = ','.join('?' * len(self._SYNC_DONE_STATUSES))
                # db-audit: ignore[DBW001] - join of placeholders
                rows = conn.execute(
                    "SELECT COALESCE(queue_name, entity_type, 'default') AS queue,"
                    "       COALESCE(status, 'pending') AS state,"
                    "       COUNT(*), MIN(created_at)"
                    " FROM sync_queue"
                    " WHERE LOWER(COALESCE(status, 'pending')) NOT IN "
                    f"({placeholders})"
                    " GROUP BY queue, state"
                    " ORDER BY queue, state",
                    self._SYNC_DONE_STATUSES,
                ).fetchall()

                outstanding = 0
                for queue, state, count, oldest in rows:
                    outstanding += count
                    tags = ('failed',) if (state or '').lower() == 'failed' else ()
                    tree.insert('', 'end',
                                values=(queue, state, count, oldest or '-'),
                                tags=tags)

                self.sync_summary_label.config(
                    text=(f"{outstanding} item(s) outstanding" if outstanding
                          else "All queues clear — nothing waiting to sync."))
            finally:
                conn.close()
        except Exception as exc:
            messagebox.showerror(
                _t('gui.pastoral.health.health_portal.data_management.dialogs.error', default="Error"),
                f"Failed to load sync status: {exc}")

    # ------------------------------------------------------------------
    # Shared helper for the simple "recent events" tables
    # ------------------------------------------------------------------
    def _build_events_view(self, parent, tree_attr, label_attr, refresh):
        frame = ttk.Frame(parent, padding="10")
        frame.pack(fill='both', expand=True)

        controls = ttk.Frame(frame)
        controls.pack(fill='x', pady=(0, 8))
        ttk.Button(controls, text=_t('gui.pastoral.health.health_portal.data_management.buttons.refresh',
                                     default="Refresh"),
                   command=refresh).pack(side='left')
        label = ttk.Label(controls, text="")
        label.pack(side='right')
        setattr(self, label_attr, label)

        columns = ('When', 'Reference', 'Event', 'Status')
        tree = ttk.Treeview(frame, columns=columns, show='headings', height=16)
        widths = {'When': 160, 'Reference': 180, 'Event': 200, 'Status': 140}
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=widths[col])
        scroll = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        tree.tag_configure('error', foreground='#b00020')
        setattr(self, tree_attr, tree)
        refresh()

    def _refresh_events(self, tree_attr, label_attr, table, reference_column):
        # Identifiers cannot be parameterised, so they are validated instead.
        table = validate_identifier(table)
        reference_column = validate_identifier(reference_column)
        tree = getattr(self, tree_attr, None)
        label = getattr(self, label_attr, None)
        if tree is None:
            return
        for item in tree.get_children():
            tree.delete(item)
        try:
            conn = self.get_connection()
            try:
                if not self._table_exists(conn, table):
                    if label:
                        label.config(text=f"No {table} table.")
                    return
                rows = conn.execute(
                    f"SELECT created_at, COALESCE({reference_column}, '-'),"
                    "        COALESCE(event_type, ''), COALESCE(status, '-')"
                    f" FROM {table} ORDER BY created_at DESC LIMIT 200").fetchall()
                errors = 0
                for when, reference, event, status in rows:
                    tags = ()
                    if (status or '').lower() in ('error', 'failed', 'denied'):
                        tags = ('error',)
                        errors += 1
                    tree.insert('', 'end', values=(when, reference, event, status), tags=tags)
                if label:
                    label.config(text=(f"{len(rows)} event(s)"
                                       + (f" · {errors} error(s)" if errors else ""))
                                 if rows else "No events recorded yet.")
            finally:
                conn.close()
        except Exception as exc:
            messagebox.showerror(
                _t('gui.pastoral.health.health_portal.data_management.dialogs.error', default="Error"),
                f"Failed to load {table}: {exc}")

    # ------------------------------------------------------------------
    # External system connections
    # ------------------------------------------------------------------
    def create_external_connections_view(self, parent):
        frame = ttk.Frame(parent, padding="10")
        frame.pack(fill='both', expand=True)

        controls = ttk.Frame(frame)
        controls.pack(fill='x', pady=(0, 8))
        ttk.Button(controls, text=_t('gui.pastoral.health.health_portal.data_management.buttons.refresh',
                                     default="Refresh"),
                   command=self.refresh_external_connections).pack(side='left')
        ttk.Button(controls, text=_t('gui.pastoral.health.health_portal.data_management.buttons.configure',
                                     default="Configure New"),
                   command=self.configure_integration).pack(side='left', padx=(6, 0))
        ttk.Button(controls, text=_t('gui.pastoral.health.health_portal.data_management.buttons.test_connection',
                                     default="Test Connection"),
                   command=self.test_integration_connection).pack(side='left', padx=(6, 0))
        ttk.Button(controls, text=_t('gui.pastoral.health.health_portal.data_management.buttons.disconnect',
                                     default="Disconnect"),
                   command=self.disconnect_integration).pack(side='left', padx=(6, 0))
        self.connections_summary_label = ttk.Label(controls, text="")
        self.connections_summary_label.pack(side='right')

        columns = ('System', 'Type', 'Active', 'Sync Status', 'Last Sync')
        self.connections_tree = ttk.Treeview(frame, columns=columns, show='headings', height=16)
        widths = {'System': 220, 'Type': 130, 'Active': 80, 'Sync Status': 130, 'Last Sync': 170}
        for col in columns:
            self.connections_tree.heading(col, text=col)
            self.connections_tree.column(col, width=widths[col])
        scroll = ttk.Scrollbar(frame, orient='vertical', command=self.connections_tree.yview)
        self.connections_tree.configure(yscrollcommand=scroll.set)
        self.connections_tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.connections_tree.tag_configure('inactive', foreground='#8a6d00')
        self.connections_tree.tag_configure('error', foreground='#b00020')

        self.refresh_external_connections()

    def refresh_external_connections(self):
        """List configured integrations from system_integrations.

        The CLI screen prints a hardcoded list — "LabCorp Integration,
        Connected, last sync 2024-01-15" and so on — that is invented, not
        read from anywhere. Showing the real table means an empty result says
        "nothing configured", which is true and actionable, rather than
        implying four healthy connections that do not exist.
        """
        tree = getattr(self, 'connections_tree', None)
        if tree is None:
            return
        for item in tree.get_children():
            tree.delete(item)
        try:
            conn = self.get_connection()
            try:
                if not self._table_exists(conn, 'system_integrations'):
                    self.connections_summary_label.config(
                        text="No system_integrations table.")
                    return
                rows = conn.execute(
                    "SELECT name, COALESCE(type, '-'), COALESCE(is_active, 0),"
                    "       COALESCE(sync_status, '-'),"
                    "       COALESCE(last_sync_datetime, 'Never'),"
                    "       COALESCE(error_log, '')"
                    " FROM system_integrations ORDER BY name").fetchall()
                active = 0
                for name, kind, is_active, sync_status, last_sync, error_log in rows:
                    if is_active:
                        active += 1
                    tags = ()
                    if error_log:
                        tags = ('error',)
                    elif not is_active:
                        tags = ('inactive',)
                    tree.insert('', 'end', values=(
                        name, kind, 'Yes' if is_active else 'No',
                        sync_status, last_sync), tags=tags)
                self.connections_summary_label.config(
                    text=(f"{active} of {len(rows)} active" if rows
                          else "No external systems configured."))
            finally:
                conn.close()
        except Exception as exc:
            messagebox.showerror(
                _t('gui.pastoral.health.health_portal.data_management.dialogs.error', default="Error"),
                f"Failed to load external connections: {exc}")

    # ------------------------------------------------------------------
    # API keys
    # ------------------------------------------------------------------
    def create_api_keys_view(self, parent):
        frame = ttk.Frame(parent, padding="10")
        frame.pack(fill='both', expand=True)

        controls = ttk.Frame(frame)
        controls.pack(fill='x', pady=(0, 8))
        ttk.Button(controls, text=_t('gui.pastoral.health.health_portal.data_management.buttons.refresh',
                                     default="Refresh"),
                   command=self.refresh_api_keys).pack(side='left')
        ttk.Button(controls, text=_t('gui.pastoral.health.health_portal.data_management.buttons.generate_key',
                                     default="Generate Key"),
                   command=self.generate_api_key).pack(side='left', padx=(6, 0))
        ttk.Button(controls, text=_t('gui.pastoral.health.health_portal.data_management.buttons.rotate_key',
                                     default="Rotate Key"),
                   command=self.rotate_api_key).pack(side='left', padx=(6, 0))
        ttk.Button(controls, text=_t('gui.pastoral.health.health_portal.data_management.buttons.revoke_key',
                                     default="Revoke Key"),
                   command=self.revoke_api_key).pack(side='left', padx=(6, 0))
        ttk.Label(controls,
                  text="Existing key material is never displayed.",
                  foreground='#666666').pack(side='left', padx=(12, 0))
        self.api_keys_summary_label = ttk.Label(controls, text="")
        self.api_keys_summary_label.pack(side='right')

        columns = ('Name', 'Active', 'Expires', 'Last Used', 'Created')
        self.api_keys_tree = ttk.Treeview(frame, columns=columns, show='headings', height=16)
        widths = {'Name': 220, 'Active': 80, 'Expires': 150, 'Last Used': 160, 'Created': 160}
        for col in columns:
            self.api_keys_tree.heading(col, text=col)
            self.api_keys_tree.column(col, width=widths[col])
        scroll = ttk.Scrollbar(frame, orient='vertical', command=self.api_keys_tree.yview)
        self.api_keys_tree.configure(yscrollcommand=scroll.set)
        self.api_keys_tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.api_keys_tree.tag_configure('expired', foreground='#b00020')
        self.api_keys_tree.tag_configure('expiring', foreground='#8a6d00')

        self.refresh_api_keys()

    def refresh_api_keys(self):
        """List API keys from api_keys — names and lifecycle only.

        The CLI prints invented keys ("lc_***************", expiring 2024).
        This reads the real table, and deliberately selects neither api_key
        nor key_hash: a management screen needs to know which keys exist and
        when they expire, never their material.
        """
        tree = getattr(self, 'api_keys_tree', None)
        if tree is None:
            return
        for item in tree.get_children():
            tree.delete(item)
        try:
            conn = self.get_connection()
            try:
                if not self._table_exists(conn, 'api_keys'):
                    self.api_keys_summary_label.config(text="No api_keys table.")
                    return
                rows = conn.execute(
                    "SELECT COALESCE(key_name, '(unnamed)'), COALESCE(is_active, 0),"
                    "       COALESCE(expires_at, ''), COALESCE(last_used_at, 'Never'),"
                    "       COALESCE(created_at, '')"
                    " FROM api_keys ORDER BY COALESCE(is_active, 0) DESC, key_name").fetchall()
                now = datetime.now()
                expired = expiring = 0
                for name, is_active, expires, last_used, created in rows:
                    tags = ()
                    if expires:
                        try:
                            when = datetime.fromisoformat(str(expires)[:19])
                            days = (when - now).days
                            if days < 0:
                                tags, expired = ('expired',), expired + 1
                            elif days <= 30:
                                tags, expiring = ('expiring',), expiring + 1
                        except ValueError:
                            pass
                    tree.insert('', 'end', values=(
                        name, 'Yes' if is_active else 'No',
                        expires or 'No expiry', last_used, created), tags=tags)
                if rows:
                    note = f"{len(rows)} key(s)"
                    if expired:
                        note += f" · {expired} expired"
                    if expiring:
                        note += f" · {expiring} expiring within 30 days"
                    self.api_keys_summary_label.config(text=note)
                else:
                    self.api_keys_summary_label.config(text="No API keys configured.")
            finally:
                conn.close()
        except Exception as exc:
            messagebox.showerror(
                _t('gui.pastoral.health.health_portal.data_management.dialogs.error', default="Error"),
                f"Failed to load API keys: {exc}")

    # ------------------------------------------------------------------
    # Lab / insurance event feeds
    # ------------------------------------------------------------------
    def create_lab_events_view(self, parent):
        self._build_events_view(parent, 'lab_events_tree', 'lab_events_label',
                                self.refresh_lab_events)

    def refresh_lab_events(self):
        self._refresh_events('lab_events_tree', 'lab_events_label',
                             'lab_integration_events', 'order_id')

    def create_insurance_events_view(self, parent):
        self._build_events_view(parent, 'insurance_events_tree', 'insurance_events_label',
                                self.refresh_insurance_events)

    def refresh_insurance_events(self):
        self._refresh_events('insurance_events_tree', 'insurance_events_label',
                             'insurance_integration_events', 'claim_id')

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------
    def create_integration_health_view(self, parent):
        frame = ttk.Frame(parent, padding="10")
        frame.pack(fill='both', expand=True)

        controls = ttk.Frame(frame)
        controls.pack(fill='x', pady=(0, 8))
        ttk.Button(controls, text=_t('gui.pastoral.health.health_portal.data_management.buttons.run_check',
                                     default="Run Check"),
                   command=self.refresh_integration_health).pack(side='left')
        self.health_summary_label = ttk.Label(controls, text="")
        self.health_summary_label.pack(side='right')

        columns = ('Integration', 'Health', 'Events (7d)', 'Errors (7d)', 'Last Activity', 'Last Error')
        self.health_tree = ttk.Treeview(frame, columns=columns, show='headings', height=16)
        widths = {'Integration': 150, 'Health': 100, 'Events (7d)': 100,
                  'Errors (7d)': 100, 'Last Activity': 160, 'Last Error': 300}
        for col in columns:
            self.health_tree.heading(col, text=col)
            self.health_tree.column(col, width=widths[col])
        scroll = ttk.Scrollbar(frame, orient='vertical', command=self.health_tree.yview)
        self.health_tree.configure(yscrollcommand=scroll.set)
        self.health_tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.health_tree.tag_configure('down', foreground='#b00020')
        self.health_tree.tag_configure('degraded', foreground='#8a6d00')

        self.refresh_integration_health()

    def refresh_integration_health(self):
        """Derive integration health from what actually happened.

        The CLI reports fixed results — LabCorp healthy at 245ms, Hospital EMR
        down — that are hardcoded and never measured. Health here is computed
        from the last seven days of integration_logs: every error is degraded,
        only errors and no successes is down, no traffic at all is unknown.
        That can be wrong about a silent system, but it is never invented.
        """
        tree = getattr(self, 'health_tree', None)
        if tree is None:
            return
        for item in tree.get_children():
            tree.delete(item)
        try:
            conn = self.get_connection()
            try:
                if not self._table_exists(conn, 'integration_logs'):
                    self.health_summary_label.config(text="No integration_logs table.")
                    return
                rows = conn.execute(
                    "SELECT COALESCE(provider, system, 'unknown') AS source,"
                    "       COUNT(*),"
                    "       SUM(CASE WHEN LOWER(COALESCE(status,'')) = 'error' THEN 1 ELSE 0 END),"
                    "       MAX(created_at)"
                    " FROM integration_logs"
                    " WHERE datetime(created_at) >= datetime('now','localtime','-7 day')"
                    " GROUP BY source ORDER BY source").fetchall()

                healthy = 0
                for source, total, errors, last_activity in rows:
                    errors = errors or 0
                    if errors == 0:
                        health, tags = 'Healthy', ()
                        healthy += 1
                    elif errors >= total:
                        health, tags = 'Down', ('down',)
                    else:
                        health, tags = 'Degraded', ('degraded',)

                    last_error = ''
                    if errors:
                        row = conn.execute(
                            "SELECT COALESCE(message, '') FROM integration_logs"
                            " WHERE COALESCE(provider, system, 'unknown') = ?"
                            "   AND LOWER(COALESCE(status,'')) = 'error'"
                            " ORDER BY created_at DESC LIMIT 1", (source,)).fetchone()
                        last_error = row[0] if row else ''

                    tree.insert('', 'end', values=(
                        source, health, total, errors, last_activity, last_error), tags=tags)

                if rows:
                    self.health_summary_label.config(
                        text=f"{healthy}/{len(rows)} integrations healthy (last 7 days)")
                else:
                    self.health_summary_label.config(
                        text="No integration activity in the last 7 days.")
            finally:
                conn.close()
        except Exception as exc:
            messagebox.showerror(
                _t('gui.pastoral.health.health_portal.data_management.dialogs.error', default="Error"),
                f"Failed to run the integration health check: {exc}")

    # ------------------------------------------------------------------
    # Write actions
    # ------------------------------------------------------------------
    # The CLI's equivalents only print a fake success — "New API key generated
    # for X", "Connection test successful" — without writing anything or
    # contacting anything. These do the real thing, and every one of them
    # records what happened in integration_logs so the audit trail matches
    # reality.

    @staticmethod
    def _key_service_error(error):
        """Turn a key-manager failure into something an admin can act on.

        The manager fails closed when API_KEY_PEPPER is unset — correct, since
        the built-in default is public and would defeat the pepper against a
        stolen database — but the raw message does not say what to do about it.
        """
        text = str(error or 'unknown error')
        if 'PEPPER' in text.upper():
            return ("API key generation is disabled because API_KEY_PEPPER is "
                    "not set on this deployment.\n\nSet that environment "
                    "variable to a strong secret and restart, then try again. "
                    "Keys minted without it would not survive a stolen "
                    "database, so the service refuses rather than issuing a "
                    "weak key.")
        return f"Failed to generate the key: {text}"

    def _current_user_id(self):
        user = getattr(self.auth, 'current_user', None) or {}
        return user.get('id')

    def _current_username(self):
        user = getattr(self.auth, 'current_user', None) or {}
        return user.get('username', 'unknown')

    def _require_admin(self, action):
        """Gate a write action. Returns True when the user may proceed."""
        try:
            if self.is_admin():
                return True
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
        messagebox.showerror(
            _t('gui.pastoral.health.health_portal.data_management.dialogs.error', default="Error"),
            f"Only administrators can {action}.")
        return False

    def _log_integration_event(self, provider, event_type, status, message):
        """Record an integration action. Never receives key material."""
        try:
            conn = self.get_connection()
            try:
                if not self._table_exists(conn, 'integration_logs'):
                    return
                conn.execute(
                    "INSERT INTO integration_logs"
                    " (provider, event_type, status, message, created_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (provider, event_type, status, message,
                     datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                conn.commit()
            finally:
                conn.close()
        except Exception:
            # Logging the action must never be what breaks the action.
            logger.debug("Suppressed exception", exc_info=True)

    def _show_secret_once(self, title, key_name, secret):
        """Display a freshly issued key once, with no copy left behind.

        The value is not written to the log, not stored in an attribute and
        not printed — the database only ever holds its PBKDF2 hash, so if the
        operator loses this dialog the key is genuinely unrecoverable and must
        be reissued. The dialog says so.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text=f"API key for: {key_name}",
                  font=('TkDefaultFont', 10, 'bold')).pack(anchor='w')
        ttk.Label(frame, foreground='#b00020', wraplength=520, justify='left',
                  text=("Copy this now. Only a one-way hash is stored, so this "
                        "value cannot be shown again — if you lose it you must "
                        "issue a new key.")).pack(anchor='w', pady=(6, 10))

        entry = ttk.Entry(frame, width=64)
        entry.insert(0, secret)
        entry.configure(state='readonly')
        entry.pack(fill='x')

        def copy_to_clipboard():
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(secret)
                messagebox.showinfo("Copied", "Key copied to the clipboard.",
                                    parent=dialog)
            except Exception as exc:
                messagebox.showerror("Error", f"Could not copy: {exc}", parent=dialog)

        buttons = ttk.Frame(frame)
        buttons.pack(fill='x', pady=(12, 0))
        ttk.Button(buttons, text="Copy to clipboard",
                   command=copy_to_clipboard).pack(side='left')
        ttk.Button(buttons, text="Done", command=dialog.destroy).pack(side='right')

    # --- API keys -----------------------------------------------------
    def generate_api_key(self):
        """Issue a real API key through the shared security manager."""
        if not self._require_admin("generate API keys"):
            return
        name = simpledialog.askstring(
            "Generate API Key", "Name for the new key (e.g. 'LabCorp API'):",
            parent=self.root)
        if not name or not name.strip():
            return
        name = name.strip()

        try:
            from education_system.systems.university.infrastructure.security.comprehensive_security import (
                APISecurityManager,
            )
        except Exception as exc:
            messagebox.showerror(
                _t('gui.pastoral.health.health_portal.data_management.dialogs.error', default="Error"),
                f"Key management service unavailable: {exc}")
            return

        # Generation, hashing and storage all happen in the shared manager —
        # secrets.token_urlsafe + PBKDF2-HMAC-SHA256 with a pepper. Nothing
        # about key material is reimplemented here.
        result = APISecurityManager().create_api_key(
            user_id=self._current_user_id(), key_name=name,
            permissions=['health.read'])

        if not result.get('success'):
            messagebox.showerror(
                _t('gui.pastoral.health.health_portal.data_management.dialogs.error', default="Error"),
                self._key_service_error(result.get('error')))
            return

        self._log_integration_event('api_keys', 'key_generated', 'success',
                                    f"Key '{name}' issued by {self._current_username()}")
        self._show_secret_once("New API Key", name, result['api_key'])
        self.refresh_api_keys()

    def rotate_api_key(self):
        """Issue a replacement key and time-box the old one.

        The old key is not killed instantly: its expires_at is moved to 24
        hours out, so callers have a real transition window. api_keys has no
        previous-key columns, so the expiry column is what makes that window
        representable rather than pretended.
        """
        if not self._require_admin("rotate API keys"):
            return
        selected = self.api_keys_tree.selection()
        if not selected:
            messagebox.showwarning("No selection", "Select the key to rotate first.")
            return
        old_name = self.api_keys_tree.item(selected[0])['values'][0]

        if not messagebox.askyesno(
                "Rotate API key",
                f"Issue a replacement for '{old_name}'?\n\n"
                "The existing key keeps working for 24 hours, then expires. "
                "Update anything using it before then."):
            return

        try:
            from education_system.systems.university.infrastructure.security.comprehensive_security import (
                APISecurityManager,
            )
        except Exception as exc:
            messagebox.showerror("Error", f"Key management service unavailable: {exc}")
            return

        # Note which rows already exist BEFORE issuing the replacement. Using
        # a timestamp to tell old from new does not work: both keys can be
        # created inside the same second, so "created before now" matches
        # neither and the old key is left running to its original expiry.
        try:
            conn = self.get_connection()
            try:
                previous_ids = [row[0] for row in conn.execute(
                    "SELECT key_id FROM api_keys"
                    " WHERE key_name = ? AND COALESCE(is_active, 1) = 1",
                    (old_name,)).fetchall()]
            finally:
                conn.close()
        except Exception as exc:
            messagebox.showerror("Error", f"Could not read the existing key: {exc}")
            return

        result = APISecurityManager().create_api_key(
            user_id=self._current_user_id(), key_name=old_name,
            permissions=['health.read'])
        if not result.get('success'):
            messagebox.showerror("Error", self._key_service_error(result.get('error')))
            return

        grace_until = (datetime.now() + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
        if previous_ids:
            try:
                conn = self.get_connection()
                try:
                    placeholders = ','.join('?' * len(previous_ids))
                    # db-audit: ignore[DBW001] - join of placeholders
                    conn.execute(
                        f"UPDATE api_keys SET expires_at = ? WHERE key_id IN ({placeholders})",
                        [grace_until] + previous_ids)
                    conn.commit()
                finally:
                    conn.close()
            except Exception as exc:
                messagebox.showwarning(
                    "Partial rotation",
                    f"The new key was issued, but the old one could not be "
                    f"time-boxed: {exc}\n\nRevoke it by hand.")

        self._log_integration_event(
            'api_keys', 'key_rotated', 'success',
            f"Key '{old_name}' rotated by {self._current_username()}; "
            f"previous key expires {grace_until}")
        self._show_secret_once("Rotated API Key", old_name, result['api_key'])
        self.refresh_api_keys()

    def revoke_api_key(self):
        """Deactivate a key immediately."""
        if not self._require_admin("revoke API keys"):
            return
        selected = self.api_keys_tree.selection()
        if not selected:
            messagebox.showwarning("No selection", "Select the key to revoke first.")
            return
        name = self.api_keys_tree.item(selected[0])['values'][0]

        if not messagebox.askyesno(
                "Revoke API key",
                f"Revoke '{name}' now?\n\nAnything using this key stops "
                "working immediately. This cannot be undone — a new key would "
                "have to be issued."):
            return

        try:
            conn = self.get_connection()
            try:
                cur = conn.execute(
                    "UPDATE api_keys SET is_active = 0 WHERE key_name = ?", (name,))
                conn.commit()
                affected = cur.rowcount or 0
            finally:
                conn.close()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to revoke the key: {exc}")
            return

        self._log_integration_event('api_keys', 'key_revoked', 'success',
                                    f"Key '{name}' revoked by {self._current_username()}")
        messagebox.showinfo("Revoked", f"'{name}' revoked ({affected} row(s) updated).")
        self.refresh_api_keys()

    # --- Connections --------------------------------------------------
    def configure_integration(self):
        """Add a real row to system_integrations."""
        if not self._require_admin("configure integrations"):
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Configure Integration")
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill='both', expand=True)

        fields = {}
        for row, (key, label, default) in enumerate([
                ('name', 'System name:', ''),
                ('type', 'Type (lab / insurance / emr / registry):', 'lab'),
                ('endpoint', 'API endpoint URL:', '')]):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w', pady=4)
            var = tk.StringVar(value=default)
            ttk.Entry(frame, textvariable=var, width=44).grid(
                row=row, column=1, pady=4, padx=(8, 0))
            fields[key] = var

        def save():
            name = fields['name'].get().strip()
            kind = fields['type'].get().strip() or 'other'
            endpoint = fields['endpoint'].get().strip()
            if not name:
                messagebox.showwarning("Name required",
                                       "Give the integration a name.", parent=dialog)
                return
            config = json.dumps({'endpoint': endpoint} if endpoint else {})
            try:
                conn = self.get_connection()
                try:
                    conn.execute(
                        "INSERT INTO system_integrations"
                        " (name, type, config, is_active, sync_status, last_sync_datetime)"
                        " VALUES (?, ?, ?, 1, 'never', NULL)",
                        (name, kind, config))
                    conn.commit()
                finally:
                    conn.close()
            except Exception as exc:
                messagebox.showerror("Error",
                                     f"Failed to save the integration: {exc}", parent=dialog)
                return

            self._log_integration_event(
                kind, 'integration_configured', 'success',
                f"'{name}' configured by {self._current_username()}"
                + (f" ({endpoint})" if endpoint else " (no endpoint set)"))
            dialog.destroy()
            messagebox.showinfo("Configured", f"'{name}' added and set active.")
            self.refresh_external_connections()

        buttons = ttk.Frame(frame)
        buttons.grid(row=3, column=1, sticky='e', pady=(12, 0))
        ttk.Button(buttons, text="Save", command=save).pack(side='left', padx=4)
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side='left')

    def disconnect_integration(self):
        """Mark an integration inactive."""
        if not self._require_admin("disconnect integrations"):
            return
        selected = self.connections_tree.selection()
        if not selected:
            messagebox.showwarning("No selection",
                                   "Select the integration to disconnect first.")
            return
        name = self.connections_tree.item(selected[0])['values'][0]

        if not messagebox.askyesno(
                "Disconnect integration",
                f"Disconnect '{name}'?\n\nIt stops being treated as active. "
                "The configuration is kept, so it can be re-enabled."):
            return

        try:
            conn = self.get_connection()
            try:
                conn.execute(
                    "UPDATE system_integrations SET is_active = 0,"
                    " sync_status = 'disconnected' WHERE name = ?", (name,))
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to disconnect: {exc}")
            return

        self._log_integration_event('system', 'integration_disconnected', 'success',
                                    f"'{name}' disconnected by {self._current_username()}")
        messagebox.showinfo("Disconnected", f"'{name}' is no longer active.")
        self.refresh_external_connections()

    def test_integration_connection(self):
        """Actually contact the configured endpoint and record the result.

        The CLI prints "Connection test successful" unconditionally. This
        performs a real request against the endpoint stored in the
        integration's config and reports what came back — including that no
        endpoint is configured, which is the common case and is not a pass.
        """
        if not self._require_admin("test connections"):
            return
        selected = self.connections_tree.selection()
        if not selected:
            messagebox.showwarning("No selection",
                                   "Select the integration to test first.")
            return
        name = self.connections_tree.item(selected[0])['values'][0]

        try:
            conn = self.get_connection()
            try:
                row = conn.execute(
                    "SELECT COALESCE(config, ''), COALESCE(type, 'other')"
                    " FROM system_integrations WHERE name = ? LIMIT 1",
                    (name,)).fetchone()
            finally:
                conn.close()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to read the integration: {exc}")
            return

        if not row:
            messagebox.showerror("Error", f"'{name}' not found.")
            return

        raw_config, kind = row
        try:
            endpoint = (json.loads(raw_config) or {}).get('endpoint') if raw_config else None
        except (ValueError, TypeError):
            endpoint = None

        if not endpoint:
            self._log_integration_event(
                kind, 'connection_test', 'error',
                f"'{name}': no endpoint configured, nothing to test")
            messagebox.showwarning(
                "No endpoint",
                f"'{name}' has no endpoint URL configured, so there is nothing "
                "to contact. Add one via Configure Integration.")
            self.refresh_integration_logs()
            return

        started = datetime.now()
        try:
            import urllib.request
            request = urllib.request.Request(endpoint, method='GET')
            with urllib.request.urlopen(request, timeout=10) as response:
                code = response.status
            elapsed = int((datetime.now() - started).total_seconds() * 1000)
            ok = 200 <= code < 400
            self._log_integration_event(
                kind, 'connection_test', 'success' if ok else 'error',
                f"'{name}' -> HTTP {code} in {elapsed}ms")
            if ok:
                messagebox.showinfo("Connection OK",
                                    f"{name} responded HTTP {code} in {elapsed}ms.")
            else:
                messagebox.showwarning("Connection problem",
                                       f"{name} responded HTTP {code} in {elapsed}ms.")
        except Exception as exc:
            elapsed = int((datetime.now() - started).total_seconds() * 1000)
            self._log_integration_event(
                kind, 'connection_test', 'error',
                f"'{name}' -> {type(exc).__name__}: {exc} after {elapsed}ms")
            messagebox.showerror(
                "Connection failed",
                f"Could not reach {name}:\n\n{type(exc).__name__}: {exc}")

        self.refresh_external_connections()
        self.refresh_integration_logs()

    @staticmethod
    def _table_exists(conn, name):
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ? LIMIT 1",
            (name,)).fetchone()
        return row is not None
