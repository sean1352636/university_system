import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
from education_system.university_system.infrastructure.database.db import sqlite3
import datetime
import os
import shutil
import csv
import json

# Import internationalization support
from education_system.university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()

# Import path constants
from education_system.university_system.modules.shared.constants.paths import BACKUP_DIR, DEFAULT_DB_PATH, LOG_DIR

# Import main database connection
try:
    from education_system.university_system.infrastructure.database.db import get_db_connection
    MAIN_DB_AVAILABLE = True
except ImportError:
    MAIN_DB_AVAILABLE = False

# Import all original functions and classes
try:
    from education_system.university_system.modules.domain.academics.services.attendance.attendance_tracker import (
        get_enhanced_setting, set_enhanced_setting
    )
    ORIGINAL_FUNCTIONS_AVAILABLE = True
except ImportError:
    ORIGINAL_FUNCTIONS_AVAILABLE = False

# Import window classes
from education_system.university_system.modules.domain.academics.gui.attendance_tracker.qr_windows import QRGeneratorWindow
from education_system.university_system.modules.domain.academics.gui.attendance_tracker.face_recognition_windows import FaceRecognitionWindow, BiometricsManagementWindow
from education_system.university_system.modules.domain.academics.gui.attendance_tracker.misc_windows import (
    GeofencingWindow, LMSIntegrationWindow, CalendarSyncWindow,
    ImportPreviewWindow, ExportDataWindow, AttendancePoliciesWindow
)
from education_system.university_system.modules.domain.academics.gui.attendance_tracker.admin_windows import APIManagementWindow, AuditLogsViewer, SystemDiagnosticsWindow
from education_system.university_system.modules.domain.academics.gui.attendance_tracker.backup_database_windows import BackupRecoveryWindow, DatabaseMaintenanceWindow
from education_system.university_system.modules.domain.academics.gui.attendance_tracker.alerts_predictive_windows import AlertsWindow, PredictiveAnalyticsWindow, AttendanceAlertsWindow
from education_system.university_system.modules.domain.academics.gui.attendance_tracker.notifications_windows import ParentNotificationWindow, NotificationSettingsWindow


def open_lms_integration(self):
        """Open LMS integration interface"""
        LMSIntegrationWindow(self.root)

def export_audit_logs(self):
        """Export audit logs"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if filename:
            try:
                # Get all audit log data
                logs_data = []
                for item in self.audit_tree.get_children():
                    logs_data.append(self.audit_tree.item(item)['values'])

                # Create DataFrame and save
                df = pd.DataFrame(logs_data, columns=["Timestamp", "User", "Action", "Table", "Record ID"])
                df.to_csv(filename, index=False)

                messagebox.showinfo(_("common.success"), _("attendance.messages.audit_logs_exported").format(filename=filename))

            except Exception as e:
                messagebox.showerror(_("common.error"), _("attendance.messages.audit_logs_export_failed").format(error=e))

def database_maintenance(self):
        """Open database maintenance tools"""
        DatabaseMaintenanceWindow(self.root)

def open_parent_notifications(self):
        """Open parent notification system"""
        ParentNotificationWindow(self.root)

def open_geofencing(self):
        """Open geofencing setup"""
        if not self.geo_system:
            messagebox.showerror(_("common.error"), _("attendance.messages.geofencing_not_available_simple"))
            return

        GeofencingWindow(self.root, self.geo_system)

def backup_database(self):
        """Backup database"""
        if not self.backup_system:
            messagebox.showwarning(_("common.warning"), _("attendance.messages.backup_not_available"))
            return

        try:
            backup_path = self.backup_system.create_backup("manual")
            if backup_path:
                messagebox.showinfo(_("common.success"), _("attendance.messages.backup_success").format(path=backup_path))
            else:
                messagebox.showerror(_("common.error"), _("attendance.messages.backup_failed"))

        except Exception as e:
            messagebox.showerror(_("common.error"), _("attendance.messages.backup_error").format(error=e))

def refresh_audit_logs(self):
        """Refresh audit logs from activity.log file"""
        # Clear existing items
        for item in self.audit_tree.get_children():
            self.audit_tree.delete(item)

        # Read from actual activity.log file
        activity_log_path = os.path.join(LOG_DIR, 'activity.log')

        try:
            if os.path.exists(activity_log_path):
                with open(activity_log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                # Parse and display the most recent 100 entries (reversed for newest first)
                for line in reversed(lines[-100:]):
                    line = line.strip()
                    if not line:
                        continue

                    # Parse log format: "user - action - timestamp" or similar
                    parts = line.split(' - ')
                    if len(parts) >= 3:
                        user = parts[0].strip()
                        action = parts[1].strip()
                        timestamp = parts[2].strip() if len(parts) > 2 else ""
                        table = parts[3].strip() if len(parts) > 3 else "-"
                        record_id = parts[4].strip() if len(parts) > 4 else "-"
                        self.audit_tree.insert('', 'end', values=(timestamp, user, action, table, record_id))
                    elif len(parts) == 2:
                        # Simpler format
                        self.audit_tree.insert('', 'end', values=("", parts[0], parts[1], "-", "-"))
                    else:
                        # Single entry - just show the whole line
                        self.audit_tree.insert('', 'end', values=("", "-", line[:50], "-", "-"))
            else:
                # No log file found - show message
                self.audit_tree.insert('', 'end', values=("", "System", f"No activity log found at {activity_log_path}", "-", "-"))

        except Exception as e:
            self.audit_tree.insert('', 'end', values=("", "Error", f"Failed to read logs: {str(e)}", "-", "-"))

def manage_attendance_policies(self):
        """Manage attendance policies"""
        AttendancePoliciesWindow(self.root)

def run_diagnostics(self):
        """Run system diagnostics"""
        DiagnosticsWindow(self.root)

def open_face_recognition(self):
        """Open face recognition setup"""
        if not self.face_system:
            messagebox.showerror(_("common.error"), _("attendance.messages.face_recognition_not_available_simple"))
            return

        FaceRecognitionWindow(self.root, self.face_system)

def create_features_settings(self, parent):
        """Create features settings widgets"""
        features_frame = ttk.LabelFrame(parent, text=_("attendance.settings.feature_toggles"), padding=10)
        features_frame.pack(fill=tk.X, pady=(0, 10))

        # Feature checkboxes
        self.qr_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(features_frame, text=_("attendance.settings.qr_checkin"),
                       variable=self.qr_enabled_var).pack(anchor=tk.W)

        self.geo_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(features_frame, text=_("attendance.settings.geofencing"),
                       variable=self.geo_enabled_var).pack(anchor=tk.W)

        self.face_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(features_frame, text=_("attendance.settings.face_recognition"),
                       variable=self.face_enabled_var).pack(anchor=tk.W)

        self.gamification_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(features_frame, text=_("attendance.settings.gamification"),
                       variable=self.gamification_enabled_var).pack(anchor=tk.W)

        self.analytics_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(features_frame, text=_("attendance.settings.predictive_analytics"),
                       variable=self.analytics_enabled_var).pack(anchor=tk.W)

        # Save button
        ttk.Button(features_frame, text=_("attendance.settings.save_features"),
                  command=self.save_feature_settings, style='Success.TButton').pack(pady=(10, 0))

def update_notification_settings(self):
        """Update notification settings"""
        NotificationSettingsWindow(self.root)

def open_attendance_alerts(self):
        """Open attendance alerts manager"""
        AttendanceAlertsWindow(self.root)

def open_predictive_analytics(self):
        """Open predictive analytics window"""
        PredictiveAnalyticsWindow(self.root)

def create_admin_tab(self):
        """Create admin tab"""
        admin_frame = ttk.Frame(self.notebook)
        self.notebook.add(admin_frame, text=_("attendance.tabs.admin"))

        # Database management
        db_frame = ttk.LabelFrame(admin_frame, text=_("attendance.admin.database_management"), padding=10)
        db_frame.pack(fill=tk.X, pady=(0, 10))

        db_buttons = ttk.Frame(db_frame)
        db_buttons.pack(fill=tk.X)

        ttk.Button(db_buttons, text=_("attendance.admin.backup_database"),
                  command=self.backup_database, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(db_buttons, text=_("attendance.admin.restore_database"),
                  command=self.restore_database, style='Warning.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(db_buttons, text=_("attendance.admin.cleanup_old_data"),
                  command=self.cleanup_old_data, style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 5))

        # System information
        info_frame = ttk.LabelFrame(admin_frame, text=_("attendance.admin.system_information"), padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        self.system_info = tk.Text(info_frame, height=10, wrap=tk.WORD)
        info_scrollbar = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=self.system_info.yview)
        self.system_info.configure(yscrollcommand=info_scrollbar.set)

        self.system_info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        info_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Audit logs
        audit_frame = ttk.LabelFrame(admin_frame, text=_("attendance.admin.audit_logs"), padding=10)
        audit_frame.pack(fill=tk.BOTH, expand=True)

        # Audit controls
        audit_controls = ttk.Frame(audit_frame)
        audit_controls.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(audit_controls, text=_("attendance.admin.refresh_logs"),
                  command=self.refresh_audit_logs, style='Primary.TButton').pack(side=tk.LEFT)
        ttk.Button(audit_controls, text=_("attendance.admin.export_logs"),
                  command=self.export_audit_logs, style='Success.TButton').pack(side=tk.LEFT, padx=(5, 0))

        # Audit treeview
        audit_columns = (_("attendance.columns.timestamp"), _("attendance.columns.user"), _("attendance.columns.action"), _("attendance.columns.table"), _("attendance.columns.record_id"))
        self.audit_tree = ttk.Treeview(audit_frame, columns=audit_columns, show="headings")

        for col in audit_columns:
            self.audit_tree.heading(col, text=col)
            self.audit_tree.column(col, width=120)

        audit_scrollbar = ttk.Scrollbar(audit_frame, orient=tk.VERTICAL, command=self.audit_tree.yview)
        self.audit_tree.configure(yscrollcommand=audit_scrollbar.set)

        self.audit_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        audit_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load system info
        self.load_system_info()

def load_system_info(self):
        """Load system information"""
        yes_text = _("attendance.system_info.yes")
        no_text = _("attendance.system_info.no")
        available_text = _("attendance.system_info.available")
        not_available_text = _("attendance.system_info.not_available")

        info_text = _("attendance.system_info.title") + "\n"
        info_text += _("attendance.system_info.separator") + "\n\n"
        info_text += f"{_('attendance.system_info.version')}: 2.0.0\n"
        info_text += f"{_('attendance.system_info.database')}: SQLite\n"
        info_text += f"{_('attendance.system_info.original_functions')}: {available_text if ORIGINAL_FUNCTIONS_AVAILABLE else not_available_text}\n"
        info_text += f"{_('attendance.system_info.qr_support')}: {yes_text if self.qr_system else no_text}\n"
        info_text += f"{_('attendance.system_info.geofencing_support')}: {yes_text if self.geo_system else no_text}\n"
        info_text += f"{_('attendance.system_info.face_recognition_support')}: {yes_text if self.face_system else no_text}\n"
        info_text += f"{_('attendance.system_info.analytics_support')}: {yes_text if self.analytics else no_text}\n"
        info_text += f"{_('attendance.system_info.backup_support')}: {yes_text if self.backup_system else no_text}\n\n"

        info_text += f"{_('attendance.system_info.system_status')}: {_('attendance.system_info.operational')}\n"
        info_text += f"{_('attendance.system_info.last_refresh')}: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

        self.system_info.delete(1.0, tk.END)
        self.system_info.insert(tk.END, info_text)

def create_notifications_settings(self, parent):
        """Create notifications settings widgets"""
        # Email settings
        email_frame = ttk.LabelFrame(parent, text=_("attendance.settings.email_settings"), padding=10)
        email_frame.pack(fill=tk.X, pady=(0, 10))

        self.auto_email_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(email_frame, text=_("attendance.settings.auto_email_warnings"),
                       variable=self.auto_email_var).pack(anchor=tk.W)

        # SMS settings
        sms_frame = ttk.LabelFrame(parent, text=_("attendance.settings.sms_settings"), padding=10)
        sms_frame.pack(fill=tk.X, pady=(0, 10))

        self.sms_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(sms_frame, text=_("attendance.settings.sms_enabled"),
                       variable=self.sms_enabled_var).pack(anchor=tk.W)

        ttk.Label(sms_frame, text=_("attendance.settings.sms_api_key")).pack(anchor=tk.W, pady=(10, 0))
        self.sms_api_var = tk.StringVar()
        ttk.Entry(sms_frame, textvariable=self.sms_api_var, width=40, show="*").pack(fill=tk.X, pady=(5, 0))

        # Save button
        ttk.Button(sms_frame, text=_("attendance.settings.save_notifications"),
                  command=self.save_notification_settings, style='Success.TButton').pack(pady=(10, 0))

def cleanup_old_data(self):
        """Cleanup old attendance data beyond a specified number of days"""
        days = simpledialog.askinteger(_("attendance.dialogs.cleanup"), _("attendance.messages.cleanup_prompt"), initialvalue=365)
        if not days or days < 1:
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime('%Y-%m-%d')

            # Count records that would be deleted
            cursor.execute("SELECT COUNT(*) as cnt FROM attendance_records WHERE date < ?", (cutoff_date,))
            count = cursor.fetchone()['cnt']

            if count == 0:
                messagebox.showinfo(_("attendance.dialogs.cleanup"),
                                    f"No attendance records older than {days} days found.",
                                    parent=self.root)
                conn.close()
                return

            if not messagebox.askyesno(_("attendance.messages.cleanup_confirm"),
                                       f"This will permanently delete {count} attendance records older than {cutoff_date}.\n\nContinue?",
                                       parent=self.root):
                conn.close()
                return

            # Perform deletion
            cursor.execute("DELETE FROM attendance_records WHERE date < ?", (cutoff_date,))
            deleted = cursor.rowcount
            conn.commit()
            conn.close()

            messagebox.showinfo(_("attendance.dialogs.cleanup"),
                                f"Cleanup complete.\n\nDeleted {deleted} records older than {cutoff_date}.",
                                parent=self.root)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Cleanup failed: {e}", parent=self.root)

def import_data(self):
        """Import data from file"""
        filename = filedialog.askopenfilename(
            title=_("attendance.dialogs.select_data_file"),
            filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx"), ("All files", "*.*")]
        )

        if filename:
            ImportDataWindow(self.root, filename, self.refresh_data)

def restore_database(self):
        """Restore database from backup"""
        if not self.backup_system:
            messagebox.showwarning(_("common.warning"), _("attendance.messages.backup_not_available"))
            return

        filename = filedialog.askopenfilename(
            title=_("attendance.dialogs.select_backup_file"),
            filetypes=[("Database files", "*.db"), ("All files", "*.*")]
        )

        if filename:
            if messagebox.askyesno(_("attendance.messages.restore_confirm"), _("attendance.messages.restore_confirm_message")):
                try:
                    success, message = self.backup_system.restore_backup(filename)
                    if success:
                        messagebox.showinfo(_("common.success"), message)
                        self.refresh_data()
                    else:
                        messagebox.showerror(_("common.error"), message)

                except Exception as e:
                    messagebox.showerror(_("common.error"), _("attendance.messages.restore_error").format(error=e))

def create_thresholds_settings(self, parent):
        """Create thresholds settings widgets"""
        consec_frame = ttk.LabelFrame(parent, text=_("attendance.settings.consecutive_absences"), padding=10)
        consec_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(consec_frame, text=_("attendance.settings.warning_after")).grid(row=0, column=0, sticky=tk.W)
        self.consec_warning_var = tk.StringVar(value="2")
        ttk.Entry(consec_frame, textvariable=self.consec_warning_var, width=10).grid(row=0, column=1, padx=(5, 0))
        ttk.Label(consec_frame, text=_("attendance.settings.absences")).grid(row=0, column=2, sticky=tk.W, padx=(5, 0))

        ttk.Label(consec_frame, text=_("attendance.settings.critical_after")).grid(row=1, column=0, sticky=tk.W)
        self.consec_critical_var = tk.StringVar(value="3")
        ttk.Entry(consec_frame, textvariable=self.consec_critical_var, width=10).grid(row=1, column=1, padx=(5, 0))
        ttk.Label(consec_frame, text=_("attendance.settings.absences")).grid(row=1, column=2, sticky=tk.W, padx=(5, 0))

        ttk.Button(consec_frame, text=_("common.save"), style='Success.TButton').grid(row=2, column=0, columnspan=3, pady=(10, 0))

def save_feature_settings(self):
        """Save feature settings"""
        if ORIGINAL_FUNCTIONS_AVAILABLE:
            set_enhanced_setting('enable_qr_checkin', self.qr_enabled_var.get(), data_type='boolean')
            set_enhanced_setting('enable_geofencing', self.geo_enabled_var.get(), data_type='boolean')
            set_enhanced_setting('enable_face_recognition', self.face_enabled_var.get(), data_type='boolean')
            set_enhanced_setting('enable_gamification', self.gamification_enabled_var.get(), data_type='boolean')
            set_enhanced_setting('enable_predictive_analytics', self.analytics_enabled_var.get(), data_type='boolean')

        messagebox.showinfo(_("common.success"), _("attendance.messages.feature_settings_saved"))

def open_biometrics_management(self):
        """Open biometrics management window"""
        BiometricsManagementWindow(self.root)

def open_api_management(self):
        """Open API management interface"""
        ApiManagementWindow(self.root)

def create_general_settings(self, parent):
        """Create general settings widgets"""
        # Attendance thresholds
        thresholds_frame = ttk.LabelFrame(parent, text=_("attendance.settings.attendance_thresholds"), padding=10)
        thresholds_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(thresholds_frame, text=_("attendance.settings.warning_threshold")).grid(row=0, column=0, sticky=tk.W)
        self.warning_threshold_var = tk.StringVar(value="80")
        ttk.Entry(thresholds_frame, textvariable=self.warning_threshold_var, width=10).grid(row=0, column=1, padx=(5, 0))

        ttk.Label(thresholds_frame, text=_("attendance.settings.critical_threshold")).grid(row=1, column=0, sticky=tk.W)
        self.critical_threshold_var = tk.StringVar(value="70")
        ttk.Entry(thresholds_frame, textvariable=self.critical_threshold_var, width=10).grid(row=1, column=1, padx=(5, 0))

        # Save button
        ttk.Button(thresholds_frame, text=_("attendance.settings.save_thresholds"),
                  command=self.save_thresholds, style='Success.TButton').grid(row=2, column=0, columnspan=2, pady=(10, 0))

def save_notification_settings(self):
        """Save notification settings"""
        if ORIGINAL_FUNCTIONS_AVAILABLE:
            set_enhanced_setting('auto_email_warnings', self.auto_email_var.get(), data_type='boolean')
            set_enhanced_setting('enable_sms_notifications', self.sms_enabled_var.get(), data_type='boolean')
            set_enhanced_setting('sms_api_key', self.sms_api_var.get(), data_type='string')

        messagebox.showinfo(_("common.success"), _("attendance.messages.notification_settings_saved"))

def create_settings_tab(self):
        """Create settings tab"""
        settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(settings_frame, text=_("attendance.tabs.settings"))

        # Settings notebook
        settings_notebook = ttk.Notebook(settings_frame)
        settings_notebook.pack(fill=tk.BOTH, expand=True)

        # General settings
        general_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(general_frame, text=_("attendance.settings.general"))

        self.create_general_settings(general_frame)

        # Notifications settings
        notifications_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(notifications_frame, text=_("attendance.settings.notifications"))

        self.create_notifications_settings(notifications_frame)

        # Features settings
        features_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(features_frame, text=_("attendance.settings.features"))

        self.create_features_settings(features_frame)

        # Thresholds settings
        thresholds_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(thresholds_frame, text=_("attendance.settings.thresholds"))

        self.create_thresholds_settings(thresholds_frame)

def view_audit_logs(self):
        """View system audit logs"""
        AuditLogsWindow(self.root)

def open_backup_recovery(self):
        """Open backup and recovery window"""
        BackupRecoveryWindow(self.root)

def open_calendar_sync(self):
        """Open calendar sync interface"""
        CalendarSyncWindow(self.root)

def open_qr_generator(self):
        """Open QR code generator"""
        if not self.qr_system:
            messagebox.showerror(_("common.error"), _("attendance.messages.qr_system_not_available"))
            return

        QRGeneratorWindow(self.root, self.qr_system)

def save_thresholds(self):
        """Save attendance thresholds"""
        try:
            warning = int(self.warning_threshold_var.get())
            critical = int(self.critical_threshold_var.get())

            if 0 <= critical <= warning <= 100:
                if ORIGINAL_FUNCTIONS_AVAILABLE:
                    set_enhanced_setting('attendance_threshold_warning', warning, data_type='integer')
                    set_enhanced_setting('attendance_threshold_critical', critical, data_type='integer')

                messagebox.showinfo(_("common.success"), _("attendance.messages.thresholds_saved"))
            else:
                messagebox.showerror(_("common.error"), _("attendance.messages.thresholds_invalid"))

        except ValueError:
            messagebox.showerror(_("common.error"), _("attendance.messages.thresholds_invalid_numbers"))

def export_data(self):
        """Export data to file"""
        ExportDataWindow(self.root)

