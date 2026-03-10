# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import logging

# Alias for translation function (ensure _t is available for i18n)
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

# Import GUI availability flags
from education_system.university_system.modules.shared.gui.main.imports.gui_imports import (
    SECURITY_DASHBOARD_AVAILABLE,
    SecurityDashboard,
    ACTIVITY_LOGGER_GUI_AVAILABLE,
    ActivityLoggerGUI,
)

logger = logging.getLogger(__name__)

def edit_system_settings(self):
    """Edit system settings"""
    try:
        settings_window = tk.Toplevel(self.root)
        settings_window.title(_t("config_gui.system_settings.title"))
        settings_window.geometry("600x500")

        ttk.Label(settings_window, text=_t("config_gui.system_settings.header"),
                 font=('Arial', 14, 'bold')).pack(pady=10)

        settings_text = scrolledtext.ScrolledText(settings_window, wrap=tk.WORD, height=20,
                                                  fg="#000000", bg="#FFFFFF")
        settings_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        settings_info = _t("config_gui.system_settings.info_header") + """
================================

""" + _t("config_gui.system_settings.current_settings") + """
- """ + _t("config_gui.system_settings.session_timeout") + """
- """ + _t("config_gui.system_settings.auto_save") + """
- """ + _t("config_gui.system_settings.debug_mode") + """
- """ + _t("config_gui.system_settings.log_level") + """
- """ + _t("config_gui.system_settings.database") + """
- """ + _t("config_gui.system_settings.connection_pool") + """

""" + _t("config_gui.system_settings.authentication") + """
- """ + _t("config_gui.system_settings.password_policy") + """
- """ + _t("config_gui.system_settings.mfa_available") + """
- """ + _t("config_gui.system_settings.session_tokens") + """
- """ + _t("config_gui.system_settings.max_login_attempts") + """

""" + _t("config_gui.system_settings.email_configuration") + """
- """ + _t("config_gui.system_settings.smtp_configured") + """
- """ + _t("config_gui.system_settings.email_queue") + """
- """ + _t("config_gui.system_settings.template_support") + """

""" + _t("config_gui.system_settings.modify_settings") + """
1. """ + _t("config_gui.system_settings.modify_step_1") + """
2. """ + _t("config_gui.system_settings.modify_step_2") + """
3. """ + _t("config_gui.system_settings.modify_step_3") + """

""" + _t("config_gui.system_settings.admin_note")
        settings_text.insert("1.0", settings_info)
        settings_text.config(state=tk.DISABLED)

        ttk.Button(settings_window, text=_t("config_gui.buttons.close"), command=settings_window.destroy).pack(pady=10)

    except Exception as e:
        messagebox.showerror(_t("config_gui.errors.error"), _t("config_gui.errors.failed_to_edit_settings", error=str(e)))

def configure_email(self):
    """Configure email settings"""
    try:
        email_window = tk.Toplevel(self.root)
        email_window.title(_t("config_gui.email.title"))
        email_window.geometry("600x500")

        ttk.Label(email_window, text=_t("config_gui.email.header"),
                 font=('Arial', 14, 'bold')).pack(pady=10)

        email_text = scrolledtext.ScrolledText(email_window, wrap=tk.WORD, height=20,
                                               fg="#000000", bg="#FFFFFF")
        email_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        from education_system.university_system.modules.shared.constants import paths
        import os

        env_exists = os.path.exists(paths.PROJECT_ROOT / '.env')
        status_text = _t("config_gui.email.status_configured") if env_exists else _t("config_gui.email.status_not_configured")

        email_info = _t("config_gui.email.info_header") + """
================================

""" + _t("config_gui.email.status") + f""" {status_text}

""" + _t("config_gui.email.config_file") + """ .env
""" + _t("config_gui.email.location") + f""" {paths.PROJECT_ROOT}

""" + _t("config_gui.email.required_settings") + """
- """ + _t("config_gui.email.smtp_host") + """
- """ + _t("config_gui.email.smtp_port") + """
- """ + _t("config_gui.email.smtp_user") + """
- """ + _t("config_gui.email.smtp_password") + """

""" + _t("config_gui.email.features") + """
- """ + _t("config_gui.email.async_queue") + """
- """ + _t("config_gui.email.template_support") + """
- """ + _t("config_gui.email.bulk_capability") + """
- """ + _t("config_gui.email.email_logging") + """

""" + _t("config_gui.email.config_steps") + """
1. """ + _t("config_gui.email.step_1") + """
2. """ + _t("config_gui.email.step_2") + """
3. """ + _t("config_gui.email.step_3") + """
4. """ + _t("config_gui.email.step_4") + """

""" + _t("config_gui.email.note")
        email_text.insert("1.0", email_info)
        email_text.config(state=tk.DISABLED)

        ttk.Button(email_window, text=_t("config_gui.buttons.close"), command=email_window.destroy).pack(pady=10)

    except Exception as e:
        messagebox.showerror(_t("config_gui.errors.error"), _t("config_gui.errors.failed_to_configure_email", error=str(e)))

def configure_backup(self):
    """Configure backup settings"""
    try:
        backup_window = tk.Toplevel(self.root)
        backup_window.title(_t("config_gui.backup.title"))
        backup_window.geometry("600x500")

        ttk.Label(backup_window, text=_t("config_gui.backup.header"),
                 font=('Arial', 14, 'bold')).pack(pady=10)

        backup_text = scrolledtext.ScrolledText(backup_window, wrap=tk.WORD, height=20,
                                                fg="#000000", bg="#FFFFFF")
        backup_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        from education_system.university_system.modules.shared.constants import paths

        backup_info = _t("config_gui.backup.info_header") + """
================================

""" + _t("config_gui.backup.location") + f""" {paths.BACKUP_DIR}

""" + _t("config_gui.backup.current_settings") + """
- """ + _t("config_gui.backup.auto_backup") + """
- """ + _t("config_gui.backup.frequency") + """
- """ + _t("config_gui.backup.retention") + """
- """ + _t("config_gui.backup.compression") + """

""" + _t("config_gui.backup.types") + """
1. """ + _t("config_gui.backup.full_backup") + """
   - """ + _t("config_gui.backup.full_desc_1") + """
   - """ + _t("config_gui.backup.full_desc_2") + """

2. """ + _t("config_gui.backup.incremental") + """
   - """ + _t("config_gui.backup.incremental_desc_1") + """
   - """ + _t("config_gui.backup.incremental_desc_2") + """

""" + _t("config_gui.backup.manual_backup") + """
- """ + _t("config_gui.backup.manual_step_1") + """
- """ + _t("config_gui.backup.manual_step_2") + """
- """ + _t("config_gui.backup.manual_step_3") + """

""" + _t("config_gui.backup.restore_process") + """
- """ + _t("config_gui.backup.restore_step_1") + """
- """ + _t("config_gui.backup.restore_step_2") + """
- """ + _t("config_gui.backup.restore_step_3") + """

""" + _t("config_gui.backup.recommendations") + """
- """ + _t("config_gui.backup.rec_1") + """
- """ + _t("config_gui.backup.rec_2") + """
- """ + _t("config_gui.backup.rec_3") + """
- """ + _t("config_gui.backup.rec_4")
        backup_text.insert("1.0", backup_info)
        backup_text.config(state=tk.DISABLED)

        ttk.Button(backup_window, text=_t("config_gui.buttons.close"), command=backup_window.destroy).pack(pady=10)

    except Exception as e:
        messagebox.showerror(_t("config_gui.errors.error"), _t("config_gui.errors.failed_to_configure_backup", error=str(e)))

def configure_security(self):
    """Configure security settings"""
    try:
        security_window = tk.Toplevel(self.root)
        security_window.title(_t("config_gui.security.title"))
        security_window.geometry("600x500")

        ttk.Label(security_window, text=_t("config_gui.security.header"),
                 font=('Arial', 14, 'bold')).pack(pady=10)

        security_text = scrolledtext.ScrolledText(security_window, wrap=tk.WORD, height=20,
                                                  fg="#000000", bg="#FFFFFF")
        security_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        security_info = _t("config_gui.security.info_header") + """
================================

""" + _t("config_gui.security.authentication") + """
- """ + _t("config_gui.security.password_hashing") + """
- """ + _t("config_gui.security.hash_iterations") + """
- """ + _t("config_gui.security.salt") + """
- """ + _t("config_gui.security.mfa_support") + """

""" + _t("config_gui.security.session_management") + """
- """ + _t("config_gui.security.token_sessions") + """
- """ + _t("config_gui.security.session_timeout") + """
- """ + _t("config_gui.security.concurrent_limits") + """
- """ + _t("config_gui.security.auto_logout") + """

""" + _t("config_gui.security.authorization") + """
- """ + _t("config_gui.security.rbac") + """
- """ + _t("config_gui.security.permission_checking") + """
- """ + _t("config_gui.security.roles") + """
- """ + _t("config_gui.security.granular_permissions") + """

""" + _t("config_gui.security.data_protection") + """
- """ + _t("config_gui.security.sql_injection") + """
- """ + _t("config_gui.security.xss_protection") + """
- """ + _t("config_gui.security.csrf_protection") + """
- """ + _t("config_gui.security.input_validation") + """

""" + _t("config_gui.security.audit_trail") + """
- """ + _t("config_gui.security.modifications_logged") + """
- """ + _t("config_gui.security.user_attribution") + """
- """ + _t("config_gui.security.timestamp_tracking") + """
- """ + _t("config_gui.security.compliance_ready") + """

""" + _t("config_gui.security.best_practices") + """
- """ + _t("config_gui.security.password_updates") + """
- """ + _t("config_gui.security.enable_mfa") + """
- """ + _t("config_gui.security.monitor_logs") + """
- """ + _t("config_gui.security.review_permissions") + """
- """ + _t("config_gui.security.keep_updated") + """

""" + _t("config_gui.security.contact_note")
        security_text.insert("1.0", security_info)
        security_text.config(state=tk.DISABLED)

        ttk.Button(security_window, text=_t("config_gui.buttons.close"), command=security_window.destroy).pack(pady=10)

    except Exception as e:
        messagebox.showerror(_t("config_gui.errors.error"), _t("config_gui.errors.failed_to_configure_security", error=str(e)))

def show_security_dashboard(self):
    """Launch comprehensive security & compliance dashboard"""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("config_gui.access.denied"), _t("config_gui.access.admin_required_security_dashboard"))
        return

    if not SECURITY_DASHBOARD_AVAILABLE:
        messagebox.showerror(_t("config_gui.errors.error"), _t("config_gui.errors.security_dashboard_unavailable"))
        return

    try:
        user_id = self.auth.current_user.get('id', 1)
        dashboard = SecurityDashboard(self.root, user_id)
        print(_t("config_gui.messages.security_dashboard_opened"))
    except Exception as e:
        messagebox.showerror(_t("config_gui.errors.error"), _t("config_gui.errors.failed_to_open_security_dashboard", error=str(e)))
def show_audit_log_viewer(self):
    """Launch audit log viewer for searching and analyzing audit logs"""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("config_gui.access.denied"), _t("config_gui.access.admin_required_audit_log"))
        return

    if not AUDIT_LOG_VIEWER_AVAILABLE:
        messagebox.showerror(_t("config_gui.errors.error"), _t("config_gui.errors.audit_log_viewer_unavailable"))
        return

    try:
        user_id = self.auth.current_user.get('id', 1)
        viewer = show_audit_log_viewer(self.root, user_id)
        print(_t("config_gui.messages.audit_log_viewer_opened"))
    except Exception as e:
        messagebox.showerror(_t("config_gui.errors.error"), _t("config_gui.errors.failed_to_open_audit_log_viewer", error=str(e)))
def show_activity_logger(self):
    """Launch the Enhanced Activity Logger GUI in a child window"""
    if not self.auth.current_user:
        messagebox.showerror(_t("config_gui.errors.error"), _t("config_gui.access.login_required_activity_logger"))
        return

    # Check permissions - allow admin and staff
    user_role = self.auth.current_user.get('role', '')
    if user_role not in ['admin', 'staff']:
        messagebox.showerror(_t("config_gui.errors.error"), _t("config_gui.access.no_permission_activity_logger"))
        return

    try:
        if not ACTIVITY_LOGGER_GUI_AVAILABLE:
            messagebox.showerror(_t("config_gui.activity_logger.title"), _t("config_gui.errors.activity_logger_unavailable", error="Module not available"))
            return

        # Create a new window for the Activity Logger GUI
        logger_window = tk.Toplevel(self.root)
        logger_window.title(_t("config_gui.activity_logger.window_title"))
        logger_window.geometry("1400x900")
        logger_window.minsize(1200, 800)

        # Center the window
        logger_window.update_idletasks()
        x = (logger_window.winfo_screenwidth() - logger_window.winfo_width()) // 2
        y = (logger_window.winfo_screenheight() - logger_window.winfo_height()) // 2
        logger_window.geometry(f"+{x}+{y}")

        try:
            logger_window.transient(self.root)
        except Exception:
            pass  # Continue if transient fails

        # Initialize the Activity Logger GUI in the new window using parent parameter
        activity_logger_gui = ActivityLoggerGUI(auth=self.auth, parent=logger_window)

        print(_t("config_gui.messages.activity_logger_opened", default="Activity Logger opened"))

    except Exception as e:
        messagebox.showerror(_t("config_gui.errors.error"), _t("config_gui.errors.failed_to_open_activity_logger", error=str(e)))
        print(f"Activity Logger error: {e}")
def show_activity_log(self):
    """Open Log Management GUI (in a separate window)"""
    try:
        # Prefer the local file the user provided
        from education_system.university_system.utils.logging.gui.log_management_gui import LogManagementGUI
    except Exception:
        # Optional fallback to the refactored package if present
        try:
            from education_system.university_system.utils.logging.gui.log_management_gui import LogManagementGUI
        except Exception as e:
            messagebox.showerror(_t("config_gui.log_management.unavailable"), _t("config_gui.errors.log_management_not_found", error=str(e)))
            return

    try:
        # Open inside the existing app as a child window (no extra mainloop)
        win = tk.Toplevel(self.root)
        win.title(_t("config_gui.log_management.title"))
        win.geometry("1200x800")
        LogManagementGUI(win, auth=self.auth)   # instantiate GUI from the file
    except Exception as e:
        messagebox.showerror(_t("config_gui.errors.error"), _t("config_gui.errors.failed_to_open_log_management", error=str(e)))
