"""Admin tab, system initialization, database wrappers, and system status."""

import threading
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from datetime import datetime

from education_system.university_system.core.i18n import get_text as _


class AdminMixin:
    """Admin tab, DB maintenance wrappers, and system-status display."""

    def create_admin_tab(self):
        """Create admin and system management tab"""
        tab = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['admin'] = tab

        main_frame = ttk.Frame(tab, padding=20)
        main_frame.pack(fill='both', expand=True)

        # System controls
        system_frame = ttk.LabelFrame(main_frame, text=_("finance_gui.settings.system_management_frame"), padding=15)
        system_frame.pack(fill='x', pady=(0, 20))

        # Add this button in the admin_buttons list in create_admin_tab method
        admin_buttons = [
            (_("finance_gui.settings.initialize_system_btn"), self.gui_initialize_system),
            (_("finance_gui.settings.create_sample_data_btn"), self.gui_create_sample_students),
            (_("finance_gui.settings.setup_notifications_btn"), self.gui_setup_automated_notifications),
            (_("finance_gui.settings.send_notifications_btn"), self.gui_send_automated_notifications),
            (_("finance_gui.settings.view_audit_logs_btn"), self.gui.collections.gui_view_audit_logs),
            (_("finance_gui.settings.system_settings_btn"), self.gui_system_settings),
            (_("finance_gui.settings.advanced_reporting_btn"), self.launch_reporting_gui),
            (_("finance_gui.settings.database_verification_btn"), self.gui_verify_fix),
            (_("finance_gui.settings.check_packages_btn"), self.gui_check_required_packages),
            (_("finance_gui.settings.setup_workflows_btn"), self.gui_setup_collection_workflows),
            (_("finance_gui.settings.email_config_btn"), self.gui_setup_email_config),
            (_("finance_gui.settings.sms_config_btn"), self.gui_setup_sms_config),
            (_("finance_gui.settings.test_email_btn"), self.gui_test_email_service),
            (_("finance_gui.settings.test_sms_btn"), self.gui_test_sms_service),
            (_("finance_gui.settings.analyze_admin_menu_btn"), self.update_admin_menu_with_missing_functions),
            (_("finance_gui.settings.analyze_reports_menu_btn"), self.update_reports_menu_with_missing_functions),
        ]

        for i, (text, command) in enumerate(admin_buttons):
            ttk.Button(system_frame, text=text, command=command, width=25).grid(row=i//2, column=i%2, padx=10, pady=5)
        # System status
        status_frame = ttk.LabelFrame(main_frame, text=_("finance_gui.settings.system_status_frame"), padding=15)
        status_frame.pack(fill='both', expand=True)

        self.status_text = ScrolledText(status_frame, height=15, width=80, font=('Courier', 10))
        self.status_text.pack(fill='both', expand=True)

        # Update system status
        self.update_system_status()


    def gui_initialize_system(self):
        """GUI wrapper for system initialization"""
        if messagebox.askyesno(_("finance_gui.settings.confirm_title"), _("finance_gui.settings.confirm_init_system")):
            try:
                self.update_status(_("finance_gui.settings.initializing_system"))

                def initialize():
                    init_enhanced_finance_db()
                    messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.system_initialized"))
                    self.update_system_status()
                    self.update_status(_("finance_gui.settings.system_initialization_completed"))

                thread = threading.Thread(target=initialize)
                thread.daemon = True
                thread.start()

            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.system_initialization_failed", error=str(e)))


    def gui_create_sample_students(self):
        """GUI wrapper for creating sample students"""
        if messagebox.askyesno(_("finance_gui.settings.confirm_title"), _("finance_gui.settings.confirm_create_sample_data")):
            try:
                create_sample_students()
                messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.sample_students_created"))
                self.update_status(_("finance_gui.settings.sample_students_created_status"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_create_sample_students", error=str(e)))


    def initialize_database(self):
        """Wrapper to call database manager's initialize function"""
        if hasattr(self.gui, 'db'):
            self.gui.db.initialize_database()
        else:
            messagebox.showwarning(_("finance_gui.settings.not_available_title"), _("finance_gui.settings.db_manager_not_initialized"))

    def clean_database(self):
        """Wrapper to call database manager's clean function"""
        if hasattr(self.gui, 'db'):
            self.gui.db.clean_database()
        else:
            messagebox.showwarning(_("finance_gui.settings.not_available_title"), _("finance_gui.settings.db_manager_not_initialized"))

    def backup_database(self):
        """Wrapper to call database manager's backup function"""
        if hasattr(self.gui, 'db'):
            self.gui.db.backup_database()
        else:
            messagebox.showwarning(_("finance_gui.settings.not_available_title"), _("finance_gui.settings.db_manager_not_initialized"))

    def show_database_stats(self):
        """Wrapper to call database manager's stats function"""
        if hasattr(self.gui, 'db'):
            self.gui.db.show_database_stats()
        else:
            messagebox.showwarning(_("finance_gui.settings.not_available_title"), _("finance_gui.settings.db_manager_not_initialized"))

    def update_system_status(self):
        """Update system status display"""
        if hasattr(self, 'status_text'):
            try:
                status = _("finance_gui.settings.system_status_title") + "\n"
                status += "=" * 50 + "\n"
                status += _("finance_gui.settings.database_connected") + "\n"
                status += _("finance_gui.settings.last_updated", timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')) + "\n"

                # Add more status info as needed
                self.status_text.delete('1.0', tk.END)
                self.status_text.insert('1.0', status)
            except Exception as e:
                print(_("finance_gui.settings.failed_update_system_status", error=str(e)))
