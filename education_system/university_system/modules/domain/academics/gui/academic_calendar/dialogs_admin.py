import logging
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict
from education_system.university_system.modules.shared.utils.i18n import get_text as _
from education_system.university_system.modules.domain.academics.gui.academic_calendar.utils import safe_grab_set

gui_logger = logging.getLogger(__name__)

class SystemMaintenanceDialog:
    """Dialog for system maintenance and backup operations"""
    
    def __init__(self, parent, calendar_manager, auth_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.auth_manager = auth_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.system_maintenance.title"))
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text=_("academic_calendar.dialogs.system_maintenance.title"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Backup section
        backup_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.dialogs.system_maintenance.database_backup"), padding=10)
        backup_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Button(backup_frame, text=_("academic_calendar.dialogs.system_maintenance.create_backup"),
                  command=self._create_backup).pack(side=tk.LEFT, padx=5)
        ttk.Button(backup_frame, text=_("academic_calendar.dialogs.system_maintenance.restore_backup"),
                  command=self._restore_backup).pack(side=tk.LEFT, padx=5)

        # Maintenance section
        maintenance_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.dialogs.system_maintenance.database_maintenance"), padding=10)
        maintenance_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Button(maintenance_frame, text=_("academic_calendar.dialogs.system_maintenance.verify_integrity"),
                  command=self._verify_database).pack(side=tk.LEFT, padx=5)
        ttk.Button(maintenance_frame, text=_("academic_calendar.dialogs.system_maintenance.cleanup_data"),
                  command=self._cleanup_data).pack(side=tk.LEFT, padx=5)

        # Configuration section
        config_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.dialogs.system_maintenance.system_config"), padding=10)
        config_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Button(config_frame, text=_("academic_calendar.dialogs.system_maintenance.export_config"),
                  command=self._export_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(config_frame, text=_("academic_calendar.dialogs.system_maintenance.import_config"),
                  command=self._import_config).pack(side=tk.LEFT, padx=5)

        # Status area
        status_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.dialogs.system_maintenance.system_status"), padding=10)
        status_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        self.status_text = scrolledtext.ScrolledText(status_frame, height=15, width=70)
        self.status_text.pack(fill=tk.BOTH, expand=True)
        
        # Get system status
        self._update_status()
        
        # Close button
        ttk.Button(main_frame, text=_("common.close"), command=self.dialog.destroy).pack()
    
    def _create_backup(self):
        """Create database backup"""
        try:
            result = self.calendar_manager.create_backup()
            if result['success']:
                self._log_message(f"SUCCESS: {result['message']}")
            else:
                self._log_message(f"ERROR: {result['message']}")
        except Exception as e:
            self._log_message(f"ERROR: Backup failed: {e}")
    
    def _restore_backup(self):
        """Restore from backup"""
        backup_file = filedialog.askopenfilename(
            title=_("academic_calendar.messages.file_dialog.select_backup_file"),
            filetypes=[(_("academic_calendar.messages.file_dialog.database_files"), "*.db"), (_("academic_calendar.messages.file_dialog.all_files"), "*.*")]
        )

        if backup_file:
            if messagebox.askyesno(_("academic_calendar.messages.confirm_dialog.confirm_restore_title"),
                                 _("academic_calendar.messages.confirm_dialog.confirm_restore_message")):
                try:
                    result = self.calendar_manager.restore_backup(backup_file)
                    if result['success']:
                        self._log_message(f"SUCCESS: {result['message']}")
                    else:
                        self._log_message(f"ERROR: {result['message']}")
                except Exception as e:
                    self._log_message(f"ERROR: Restore failed: {e}")
    
    def _verify_database(self):
        """Verify database integrity"""
        try:
            success = self.calendar_manager.verify_calendar_database_integrity()
            if success:
                self._log_message("SUCCESS: Database integrity verified")
            else:
                self._log_message("WARNING: Database integrity issues found (check logs)")
        except Exception as e:
            self._log_message(f"ERROR: Verification failed: {e}")
    
    def _cleanup_data(self):
        """Cleanup old data"""
        if messagebox.askyesno(_("academic_calendar.messages.confirm_dialog.confirm_cleanup_title"),
                             _("academic_calendar.messages.confirm_dialog.confirm_cleanup_message")):
            try:
                result = self.calendar_manager.cleanup_old_data()
                if result['success']:
                    self._log_message(f"SUCCESS: Cleaned {result['cleaned_events']} events, "
                                    f"{result['cleaned_notifications']} notifications, "
                                    f"{result['cleaned_audit_logs']} audit logs")
                else:
                    self._log_message(f"ERROR: {result['error']}")
            except Exception as e:
                self._log_message(f"ERROR: Cleanup failed: {e}")
    
    def _export_config(self):
        """Export system configuration"""
        try:
            config_data = self.calendar_manager.export_system_configuration()
            
            filename = filedialog.asksaveasfilename(
                title=_("academic_calendar.messages.file_dialog.save_configuration"),
                defaultextension=".json",
                filetypes=[(_("academic_calendar.messages.file_dialog.json_files"), "*.json"), (_("academic_calendar.messages.file_dialog.all_files"), "*.*")]
            )
            
            if filename:
                with open(filename, 'w') as f:
                    json.dump(config_data, f, indent=2)
                self._log_message(f"SUCCESS: Configuration exported to {filename}")
        except Exception as e:
            self._log_message(f"ERROR: Export failed: {e}")
    
    def _import_config(self):
        """Import system configuration"""
        config_file = filedialog.askopenfilename(
            title=_("academic_calendar.messages.file_dialog.select_configuration_file"),
            filetypes=[(_("academic_calendar.messages.file_dialog.json_files"), "*.json"), (_("academic_calendar.messages.file_dialog.all_files"), "*.*")]
        )
        
        if config_file:
            try:
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
                
                result = self.calendar_manager.import_system_configuration(config_data)
                if result['success']:
                    imported = result['imported']
                    self._log_message(f"SUCCESS: Imported {imported['academic_years']} academic years, "
                                    f"{imported['semesters']} semesters, "
                                    f"{imported['event_categories']} categories")
                else:
                    self._log_message(f"ERROR: {result['error']}")
            except Exception as e:
                self._log_message(f"ERROR: Import failed: {e}")
    
    def _update_status(self):
        """Update system status display"""
        try:
            stats = self.calendar_manager.get_system_stats()
            
            status = "SYSTEM STATUS\n" + "="*50 + "\n\n"
            status += f"Current Academic Year: {stats.get('current_academic_year', 'None')}\n"
            status += f"Current Semester: {stats.get('current_semester', 'None')}\n"
            status += f"Total Academic Years: {stats.get('total_academic_years', 0)}\n"
            status += f"Total Semesters: {stats.get('total_semesters', 0)}\n"
            status += f"Upcoming Events: {stats.get('upcoming_events', 0)}\n\n"
            
            status += "Events by Type:\n"
            for event_type, count in stats.get('events_by_type', {}).items():
                status += f"  {event_type}: {count}\n"
            
            status += f"\nDatabase File: {self.calendar_manager.config.db_file}\n"
            
            # Check database file size
            try:
                db_size = os.path.getsize(self.calendar_manager.config.db_file)
                status += f"Database Size: {db_size:,} bytes\n"
            except (OSError, IOError):
                status += "Database Size: Unknown\n"
            
            self.status_text.delete(1.0, tk.END)
            self.status_text.insert(1.0, status)
            
        except Exception as e:
            self._log_message(f"ERROR: Failed to get system status: {e}")
    
    def _log_message(self, message):
        """Log a message to the status area"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.status_text.insert(tk.END, f"\n[{timestamp}] {message}")
        self.status_text.see(tk.END)
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class AuditLogsDialog:
    """Dialog for viewing audit logs"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.audit_logs.title"))
        self.dialog.geometry("1000x600")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._load_audit_logs()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text=_("academic_calendar.dialogs.audit_logs.title"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Filter section
        filter_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.dialogs.audit_logs.filters"), padding=10)
        filter_frame.pack(fill=tk.X, pady=(0, 15))

        # Filter controls
        filter_controls = ttk.Frame(filter_frame)
        filter_controls.pack(fill=tk.X)

        ttk.Label(filter_controls, text=_("academic_calendar.dialogs.audit_logs.table")).pack(side=tk.LEFT)
        self.table_var = tk.StringVar()
        table_combo = ttk.Combobox(filter_controls, textvariable=self.table_var, width=15,
                                  values=["", "events", "academic_years", "semesters", "courses"])
        table_combo.pack(side=tk.LEFT, padx=(5, 15))

        ttk.Label(filter_controls, text=_("academic_calendar.dialogs.audit_logs.user")).pack(side=tk.LEFT)
        self.user_var = tk.StringVar()
        ttk.Entry(filter_controls, textvariable=self.user_var, width=15).pack(side=tk.LEFT, padx=(5, 15))

        ttk.Button(filter_controls, text=_("academic_calendar.buttons.filter"),
                  command=self._load_audit_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_controls, text=_("academic_calendar.buttons.clear"),
                  command=self._clear_filters).pack(side=tk.LEFT, padx=5)
        
        # Audit logs tree
        self.audit_tree = ttk.Treeview(main_frame, 
                                     columns=('Timestamp', 'User', 'Action', 'Table', 'Record'),
                                     show='tree headings')
        self.audit_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Configure columns
        self.audit_tree.heading('#0', text='ID')
        self.audit_tree.heading('Timestamp', text='Timestamp')
        self.audit_tree.heading('User', text='User')
        self.audit_tree.heading('Action', text='Action')
        self.audit_tree.heading('Table', text='Table')
        self.audit_tree.heading('Record', text='Record ID')
        
        self.audit_tree.column('#0', width=50)
        self.audit_tree.column('Timestamp', width=150)
        self.audit_tree.column('User', width=100)
        self.audit_tree.column('Action', width=80)
        self.audit_tree.column('Table', width=120)
        self.audit_tree.column('Record', width=200)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.audit_tree.yview)
        h_scrollbar = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL, command=self.audit_tree.xview)
        
        self.audit_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Double-click to view details
        self.audit_tree.bind('<Double-1>', self._view_audit_details)
        
        # Close button
        ttk.Button(main_frame, text=_("common.close"), command=self.dialog.destroy).pack(pady=(15, 0))
    
    def _load_audit_logs(self):
        """Load audit logs"""
        try:
            # Clear existing items
            for item in self.audit_tree.get_children():
                self.audit_tree.delete(item)
            
            # Get filters
            table_filter = self.table_var.get().strip() or None
            user_filter = self.user_var.get().strip() or None
            
            # Get audit logs
            success, logs = self.calendar_manager.audit_manager.get_audit_trail(
                table_name=table_filter, user_id=user_filter, limit=200
            )
            
            if success:
                # Filter logs to show only current session if login_time is available
                filtered_logs = logs
                if hasattr(self.auth_manager, 'login_time') and self.auth_manager.login_time:
                    from datetime import datetime
                    login_time_str = self.auth_manager.login_time
                    if isinstance(login_time_str, str):
                        filtered_logs = [log for log in logs
                                       if log.get('timestamp', '') >= login_time_str]

                for log in filtered_logs:
                    log_id = str(log.get('id', ''))
                    timestamp = log.get('timestamp', '')[:19]  # Remove microseconds
                    user_id = log.get('user_id', 'System')[:15]  # Truncate long user IDs
                    action = log.get('action', '')
                    table_name = log.get('table_name', '')
                    record_id = log.get('record_id', '')[:30]  # Truncate long IDs

                    self.audit_tree.insert('', 'end',
                                         text=log_id,
                                         values=(timestamp, user_id, action, table_name, record_id),
                                         tags=(log.get('action', '').lower(),))
                
                # Configure action colors
                self.audit_tree.tag_configure('create', foreground='green')
                self.audit_tree.tag_configure('update', foreground='blue')
                self.audit_tree.tag_configure('delete', foreground='red')
            
        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_load_audit_logs", error=str(e)))
    
    def _clear_filters(self):
        """Clear all filters"""
        self.table_var.set("")
        self.user_var.set("")
        self._load_audit_logs()
    
    def _view_audit_details(self, event):
        """View detailed audit information"""
        selection = self.audit_tree.selection()
        if selection:
            item = selection[0]
            log_id = self.audit_tree.item(item, 'text')
            
            # Get full log details
            try:
                logs = self.calendar_manager.db_manager.execute_query(
                    "SELECT * FROM audit_log WHERE id = ?", (log_id,)
                )
                
                if logs:
                    log_data = dict(logs[0])
                    AuditDetailsDialog(self.dialog, log_data)
            except Exception as e:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_get_audit_details", error=str(e)))
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class AuditDetailsDialog:
    """Dialog for viewing detailed audit information"""
    
    def __init__(self, parent, log_data):
        self.log_data = log_data
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.audit_logs.details_title"))
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("academic_calendar.dialogs.audit_logs.details_title"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Basic info
        info_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.dialogs.audit_logs.basic_info"), padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 15))
        
        basic_info = [
            ("ID:", self.log_data.get('id', 'N/A')),
            ("Timestamp:", self.log_data.get('timestamp', 'N/A')),
            ("User ID:", self.log_data.get('user_id', 'N/A')),
            ("Action:", self.log_data.get('action', 'N/A')),
            ("Table:", self.log_data.get('table_name', 'N/A')),
            ("Record ID:", self.log_data.get('record_id', 'N/A')),
            ("IP Address:", self.log_data.get('ip_address', 'N/A'))
        ]
        
        for i, (label, value) in enumerate(basic_info):
            row_frame = ttk.Frame(info_frame)
            row_frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(row_frame, text=label, font=('Arial', 9, 'bold')).pack(side=tk.LEFT)
            ttk.Label(row_frame, text=str(value)).pack(side=tk.LEFT, padx=(10, 0))
        
        # Old values
        if self.log_data.get('old_values'):
            old_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.dialogs.audit_logs.old_values"), padding=10)
            old_frame.pack(fill=tk.X, pady=(0, 15))
            
            old_text = scrolledtext.ScrolledText(old_frame, height=6, wrap=tk.WORD)
            old_text.pack(fill=tk.X)
            
            try:
                old_values = json.loads(self.log_data['old_values'])
                old_text.insert(1.0, json.dumps(old_values, indent=2))
            except (ValueError, TypeError, KeyError):
                old_text.insert(1.0, self.log_data['old_values'])
            
            old_text.config(state=tk.DISABLED)
        
        # New values
        if self.log_data.get('new_values'):
            new_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.dialogs.audit_logs.new_values"), padding=10)
            new_frame.pack(fill=tk.X, pady=(0, 15))
            
            new_text = scrolledtext.ScrolledText(new_frame, height=6, wrap=tk.WORD)
            new_text.pack(fill=tk.X)
            
            try:
                new_values = json.loads(self.log_data['new_values'])
                new_text.insert(1.0, json.dumps(new_values, indent=2))
            except (ValueError, TypeError, KeyError):
                new_text.insert(1.0, self.log_data['new_values'])
            
            new_text.config(state=tk.DISABLED)
        
        # Close button
        ttk.Button(main_frame, text=_("common.close"), command=self.dialog.destroy).pack(pady=(15, 0))
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class SettingsDialog:
    """Dialog for application settings"""
    
    def __init__(self, parent, calendar_manager, auth_manager):
        self.calendar_manager = calendar_manager
        self.auth_manager = auth_manager
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.settings.title"))
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text=_("academic_calendar.dialogs.settings.title"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Notebook for different setting categories
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # General settings
        general_frame = ttk.Frame(notebook, padding=10)
        notebook.add(general_frame, text=_("academic_calendar.dialogs.settings.general"))

        ttk.Label(general_frame, text=_("academic_calendar.dialogs.settings.default_event_type")).pack(anchor=tk.W)
        self.default_type_var = tk.StringVar(value="Academic")
        type_combo = ttk.Combobox(general_frame, textvariable=self.default_type_var,
                                values=["Academic", "Holiday", "Administrative", "Social", "Sports", "Trip"])
        type_combo.pack(fill=tk.X, pady=(5, 15))

        # Database settings
        db_frame = ttk.Frame(notebook, padding=10)
        notebook.add(db_frame, text=_("academic_calendar.dialogs.settings.database"))

        ttk.Label(db_frame, text=_("academic_calendar.dialogs.settings.database_file")).pack(anchor=tk.W)
        self.db_file_var = tk.StringVar(value=self.calendar_manager.config.db_file)
        ttk.Entry(db_frame, textvariable=self.db_file_var, state="readonly").pack(fill=tk.X, pady=(5, 15))

        ttk.Button(db_frame, text=_("academic_calendar.dialogs.system_maintenance.create_backup"),
                  command=self._create_backup).pack(anchor=tk.W, pady=5)
        ttk.Button(db_frame, text=_("academic_calendar.dialogs.settings.verify_database"),
                  command=self._verify_database).pack(anchor=tk.W, pady=5)

        # User info
        user_frame = ttk.Frame(notebook, padding=10)
        notebook.add(user_frame, text=_("academic_calendar.dialogs.settings.user_info"))
        
        if self.auth_manager and self.auth_manager.current_user:
            user_info = [
                ("Username:", self.auth_manager.current_user.get('username', 'N/A')),
                ("Role:", self.auth_manager.current_user.get('role', 'N/A')),
                ("User ID:", self.auth_manager.current_user.get('id', 'N/A'))
            ]
            
            for label, value in user_info:
                info_frame = ttk.Frame(user_frame)
                info_frame.pack(fill=tk.X, pady=5)
                ttk.Label(info_frame, text=label, font=('Arial', 9, 'bold')).pack(side=tk.LEFT)
                ttk.Label(info_frame, text=str(value)).pack(side=tk.LEFT, padx=(10, 0))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text=_("common.cancel"), command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text=_("common.apply"), command=self._apply_settings).pack(side=tk.RIGHT)
    
    def _create_backup(self):
        """Create database backup"""
        try:
            result = self.calendar_manager.create_backup()
            if result['success']:
                messagebox.showinfo(_("common.success"), result['message'])
            else:
                messagebox.showerror(_("common.error"), result['message'])
        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.backup_failed", error=str(e)))

    def _verify_database(self):
        """Verify database integrity"""
        try:
            success = self.calendar_manager.verify_calendar_database_integrity()
            if success:
                messagebox.showinfo(_("common.success"), _("academic_calendar.messages.db_verification_success"))
            else:
                messagebox.showwarning(_("common.warning"), _("academic_calendar.messages.db_verification_issues"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.db_verification_failed", error=str(e)))

    def _apply_settings(self):
        """Apply settings"""
        messagebox.showinfo(_("academic_calendar.dialogs.settings.title"), _("academic_calendar.messages.settings_applied"))
        self.dialog.destroy()
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class TimezoneSettingsDialog:
    """Dialog for timezone settings"""
    
    def __init__(self, parent, calendar_manager, auth_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.auth_manager = auth_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.timezone.title"))
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._load_current_settings()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("academic_calendar.dialogs.timezone.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Current timezone
        current_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.dialogs.timezone.current_settings"), padding=10)
        current_frame.pack(fill=tk.X, pady=(0, 15))

        self.current_tz_label = ttk.Label(current_frame, text=_("academic_calendar.labels.current_timezone_loading"))
        self.current_tz_label.pack(anchor=tk.W)

        # Timezone selection
        selection_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.dialogs.timezone.change_timezone"), padding=10)
        selection_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(selection_frame, text=_("academic_calendar.labels.select_timezone")).pack(anchor=tk.W)
        self.timezone_var = tk.StringVar()
        
        # Common timezones
        common_timezones = [
            "UTC",
            "US/Eastern",
            "US/Central", 
            "US/Mountain",
            "US/Pacific",
            "Europe/London",
            "Europe/Paris",
            "Europe/Berlin",
            "Asia/Tokyo",
            "Asia/Shanghai",
            "Australia/Sydney"
        ]
        
        timezone_combo = ttk.Combobox(selection_frame, textvariable=self.timezone_var, 
                                    width=40, values=common_timezones)
        timezone_combo.pack(fill=tk.X, pady=(5, 15))
        
        # Auto DST
        self.auto_dst_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(selection_frame, text=_("academic_calendar.labels.dst_auto_adjust"),
                       variable=self.auto_dst_var).pack(anchor=tk.W, pady=(0, 15))
        
        # Timezone info
        info_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.dialogs.timezone.information"), padding=10)
        info_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        ttk.Label(info_frame, text=_("academic_calendar.dialogs.timezone.info_text"), wraplength=450).pack(anchor=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))
        
        ttk.Button(button_frame, text=_("common.cancel"), command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text=_("academic_calendar.buttons.apply"), command=self._apply_timezone).pack(side=tk.RIGHT)
    
    def _load_current_settings(self):
        """Load current timezone settings"""
        try:
            if self.auth_manager.current_user:
                user_id = self.auth_manager.current_user['id']
                
                # Get current timezone preference
                prefs = self.calendar_manager.db_manager.execute_query(
                    "SELECT * FROM user_timezone_preferences WHERE user_id = ?", (user_id,)
                )
                
                if prefs:
                    pref = prefs[0]
                    current_tz = pref['timezone_name']
                    self.current_tz_label.config(text=_("academic_calendar.labels.current_timezone", timezone=current_tz))
                    self.timezone_var.set(current_tz)
                    self.auto_dst_var.set(pref.get('auto_dst', True))
                else:
                    self.current_tz_label.config(text=_("academic_calendar.labels.current_timezone_default"))
                    self.timezone_var.set("UTC")
        except Exception as e:
            self.current_tz_label.config(text=_("academic_calendar.messages.error_loading_settings", error=str(e)))
    
    def _apply_timezone(self):
        """Apply timezone settings"""
        try:
            if not self.auth_manager.current_user:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.no_user_logged_in"))
                return

            user_id = self.auth_manager.current_user['id']
            timezone_name = self.timezone_var.get().strip()
            auto_dst = self.auto_dst_var.get()

            if not timezone_name:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.select_timezone"))
                return

            success, message = self.calendar_manager.timezone_manager.set_user_timezone(
                user_id, timezone_name, auto_dst
            )

            if success:
                messagebox.showinfo(_("common.success"), _("academic_calendar.messages.timezone_applied"))
                if self.callback:
                    self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror(_("common.error"), message)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_apply_timezone", error=str(e)))
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class NotificationSettingsDialog:
    """Dialog for managing notification settings"""
    
    def __init__(self, parent, calendar_manager, auth_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.auth_manager = auth_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.notifications.title"))
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._load_preferences()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("academic_calendar.dialogs.notifications.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Notification types
        types_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.labels.notification_types"), padding=10)
        types_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.notification_vars = {}
        notification_types = [
            ("event_reminder", _("academic_calendar.labels.event_reminders")),
            ("deadline_warning", _("academic_calendar.labels.deadline_warnings")),
            ("schedule_change", _("academic_calendar.labels.schedule_changes")),
            ("trip_update", _("academic_calendar.labels.trip_updates"))
        ]

        for i, (type_key, type_label) in enumerate(notification_types):
            frame = ttk.Frame(types_frame)
            frame.pack(fill=tk.X, pady=2)

            var = tk.BooleanVar()
            self.notification_vars[type_key] = var

            ttk.Checkbutton(frame, text=type_label, variable=var).pack(side=tk.LEFT)

            # Advance time
            ttk.Label(frame, text=_("academic_calendar.labels.minutes_before")).pack(side=tk.RIGHT, padx=(10, 5))
            advance_var = tk.StringVar(value="60")
            self.notification_vars[f"{type_key}_advance"] = advance_var
            ttk.Entry(frame, textvariable=advance_var, width=8).pack(side=tk.RIGHT)
        
        # Delivery methods
        method_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.labels.delivery_methods"), padding=10)
        method_frame.pack(fill=tk.X, pady=(0, 15))

        self.method_var = tk.StringVar(value="email")
        ttk.Radiobutton(method_frame, text=_("academic_calendar.labels.email"), variable=self.method_var, value="email").pack(anchor=tk.W)
        ttk.Radiobutton(method_frame, text=_("academic_calendar.labels.sms"), variable=self.method_var, value="sms").pack(anchor=tk.W)
        ttk.Radiobutton(method_frame, text=_("academic_calendar.labels.both"), variable=self.method_var, value="both").pack(anchor=tk.W)

        # Contact info
        contact_frame = ttk.LabelFrame(main_frame, text=_("academic_calendar.labels.contact_info"), padding=10)
        contact_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(contact_frame, text=_("academic_calendar.labels.email_label")).pack(anchor=tk.W)
        self.email_var = tk.StringVar()
        ttk.Entry(contact_frame, textvariable=self.email_var, width=50).pack(fill=tk.X, pady=(5, 10))

        ttk.Label(contact_frame, text=_("academic_calendar.labels.phone_label")).pack(anchor=tk.W)
        self.phone_var = tk.StringVar()
        ttk.Entry(contact_frame, textvariable=self.phone_var, width=50).pack(fill=tk.X, pady=(5, 0))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, text=_("common.cancel"), command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text=_("academic_calendar.buttons.save_settings"), command=self._save_preferences).pack(side=tk.RIGHT)
    
    def _load_preferences(self):
        """Load current notification preferences"""
        try:
            if self.auth_manager.current_user:
                user_id = self.auth_manager.current_user['id']
                
                # Load notification preferences
                prefs = self.calendar_manager.db_manager.execute_query(
                    "SELECT * FROM notification_preferences WHERE user_id = ?", (user_id,)
                )
                
                for pref in prefs:
                    type_key = pref['notification_type']
                    if type_key in self.notification_vars:
                        self.notification_vars[type_key].set(pref['enabled'])
                        self.notification_vars[f"{type_key}_advance"].set(str(pref['advance_time']))
                
                # Load contact info from user data
                self.email_var.set(self.auth_manager.current_user.get('email', ''))
                self.phone_var.set(self.auth_manager.current_user.get('phone', ''))

        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_load_preferences", error=str(e)))
    
    def _save_preferences(self):
        """Save notification preferences"""
        try:
            if not self.auth_manager.current_user:
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.no_user_logged_in"))
                return

            user_id = self.auth_manager.current_user['id']
            method = self.method_var.get()

            # Save each notification type
            for type_key, enabled_var in self.notification_vars.items():
                if not type_key.endswith('_advance') and isinstance(enabled_var, tk.BooleanVar):
                    advance_time = int(self.notification_vars.get(f"{type_key}_advance", tk.StringVar(value="60")).get())

                    success, message = self.calendar_manager.notifications.set_notification_preference(
                        user_id, type_key, enabled_var.get(), advance_time, method
                    )

                    if not success:
                        messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_save_preference", type=type_key, message=message))
                        return

            messagebox.showinfo(_("common.success"), _("academic_calendar.messages.preferences_saved"))
            if self.callback:
                self.callback()
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.invalid_advance_time"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_save_preferences", error=str(e)))
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


