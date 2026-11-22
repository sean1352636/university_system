# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import logging
from education_system.platform.delivery.gui.tk_callback_filter import install_clean_close as _install_clean_close

# Alias for translation function (ensure _t is available for i18n)
from education_system.systems.university.infrastructure.i18n import get_text as _t

# Import GUI availability flags
from education_system.systems.university.shell.gui.main.imports.gui_imports import (
    SECURITY_DASHBOARD_AVAILABLE,
    SecurityDashboard,
    ACTIVITY_LOGGER_GUI_AVAILABLE,
    ActivityLoggerGUI,
    AUDIT_LOG_VIEWER_AVAILABLE,
    show_audit_log_viewer as _open_audit_log_viewer,
)

logger = logging.getLogger(__name__)

def edit_system_settings(self):
    """Edit system settings with functional controls"""
    try:
        from education_system.platform.identity.auth.core import UserAuth as _SharedAuth
        shared_auth = _SharedAuth()

        settings_window = tk.Toplevel(self.root)
        _install_clean_close(settings_window)
        settings_window.title(_t("config_gui.system_settings.title", default="===== SYSTEM SETTINGS ====="))
        settings_window.geometry("650x550")

        ttk.Label(settings_window, text=_t("config_gui.system_settings.header", default="Header"),
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Scrollable frame for settings
        canvas = tk.Canvas(settings_window, highlightthickness=0)
        scrollbar = ttk.Scrollbar(settings_window, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10)
        scrollbar.pack(side="right", fill="y")

        # ── Session & Security ─────────────────────────────────────
        sec_frame = ttk.LabelFrame(inner, text=_t('gui.shell.main.admin.config.labels.session_security', default="Session & Security"), padding=10)
        sec_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(sec_frame, text=_t('gui.shell.main.admin.config.labels.session_timeout_minutes', default="Session Timeout (minutes):")).grid(row=0, column=0, sticky="w", pady=3)
        timeout_var = tk.StringVar(value=str(shared_auth.get_setting("session_timeout", "30")))
        ttk.Spinbox(sec_frame, from_=5, to=480, textvariable=timeout_var, width=8).grid(row=0, column=1, sticky="w", padx=10)

        ttk.Label(sec_frame, text=_t('gui.shell.main.admin.config.labels.max_login_attempts', default="Max Login Attempts:")).grid(row=1, column=0, sticky="w", pady=3)
        attempts_var = tk.StringVar(value=str(shared_auth.get_setting("max_login_attempts", "5")))
        ttk.Spinbox(sec_frame, from_=3, to=20, textvariable=attempts_var, width=8).grid(row=1, column=1, sticky="w", padx=10)

        ttk.Label(sec_frame, text=_t('gui.shell.main.admin.config.labels.password_expiry_days', default="Password Expiry (days):")).grid(row=2, column=0, sticky="w", pady=3)
        expiry_var = tk.StringVar(value=str(shared_auth.get_setting("password_expiry_days", "90")))
        ttk.Spinbox(sec_frame, from_=30, to=365, textvariable=expiry_var, width=8).grid(row=2, column=1, sticky="w", padx=10)

        # ── Application ────────────────────────────────────────────
        app_frame = ttk.LabelFrame(inner, text=_t('gui.shell.main.admin.config.labels.application', default="Application"), padding=10)
        app_frame.pack(fill="x", padx=5, pady=5)

        debug_var = tk.BooleanVar(value=shared_auth.get_setting("debug_mode", False))
        ttk.Checkbutton(app_frame, text=_t('gui.shell.main.admin.config.buttons.debug_mode', default="Debug Mode"), variable=debug_var).pack(anchor="w")

        auto_save_var = tk.BooleanVar(value=shared_auth.get_setting("auto_save", True))
        ttk.Checkbutton(app_frame, text=_t('gui.shell.main.admin.config.buttons.auto_save_enabled', default="Auto-Save Enabled"), variable=auto_save_var).pack(anchor="w")

        ttk.Label(app_frame, text=_t('gui.shell.main.admin.config.labels.log_level', default="Log Level:")).pack(anchor="w", pady=(8, 0))
        log_level_var = tk.StringVar(value=str(shared_auth.get_setting("log_level", "INFO")))
        ttk.Combobox(app_frame, textvariable=log_level_var,
                     values=["DEBUG", "INFO", "WARNING", "ERROR"], state="readonly",
                     width=12).pack(anchor="w", pady=2)

        # ── Save / Close ───────────────────────────────────────────
        btn_frame = ttk.Frame(inner)
        btn_frame.pack(fill="x", padx=5, pady=15)

        def _save_settings():
            shared_auth.set_setting("session_timeout", timeout_var.get())
            shared_auth.set_setting("max_login_attempts", attempts_var.get())
            shared_auth.set_setting("password_expiry_days", expiry_var.get())
            shared_auth.set_setting("debug_mode", debug_var.get())
            shared_auth.set_setting("auto_save", auto_save_var.get())
            shared_auth.set_setting("log_level", log_level_var.get())
            messagebox.showinfo(_t('gui.shell.main.admin.config.dialogs.settings_saved', default="Settings Saved"), _t('gui.shell.main.admin.config.dialogs.system_settings_updated_successfully', default="System settings updated successfully."),
                                parent=settings_window)

        ttk.Button(btn_frame, text=_t('gui.shell.main.admin.config.buttons.save_settings', default="Save Settings"), command=_save_settings).pack(side="right", padx=5)
        ttk.Button(btn_frame, text=_t('gui.shell.main.admin.config.buttons.close', default="Close"), command=settings_window.destroy).pack(side="right")

    except Exception as e:
        messagebox.showerror(_t("config_gui.errors.error", default="Error"), _t("config_gui.errors.failed_to_edit_settings", error=str(e), default="Failed To Edit Settings {error}"))

def configure_email(self):
    """Configure email SMTP settings with functional controls"""
    try:
        from education_system import paths
        import os

        email_window = tk.Toplevel(self.root)
        _install_clean_close(email_window)
        email_window.title(_t("config_gui.email.title", default="===== EMAIL ====="))
        email_window.geometry("550x480")

        ttk.Label(email_window, text=_t("config_gui.email.header", default="Header"),
                 font=('Arial', 14, 'bold')).pack(pady=10)

        env_path = paths.UNIVERSITY_PROJECT_ROOT / '.env'
        env_vars = {}
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, _, v = line.partition('=')
                    env_vars[k.strip()] = v.strip()

        # ── SMTP Settings ──────────────────────────────────────────
        smtp_frame = ttk.LabelFrame(email_window, text=_t('gui.shell.main.admin.config.labels.smtp_configuration', default="SMTP Configuration"), padding=12)
        smtp_frame.pack(fill="x", padx=15, pady=(0, 10))

        labels = ["SMTP Host:", "SMTP Port:", "SMTP User:", "SMTP Password:"]
        keys = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD"]
        defaults = ["", "587", "", ""]
        entry_vars = []

        for i, (label, key, default) in enumerate(zip(labels, keys, defaults)):
            ttk.Label(smtp_frame, text=label).grid(row=i, column=0, sticky="w", pady=4)
            var = tk.StringVar(value=env_vars.get(key, default))
            show = "*" if "PASSWORD" in key else ""
            ttk.Entry(smtp_frame, textvariable=var, width=35, show=show).grid(
                row=i, column=1, sticky="ew", padx=(10, 0), pady=4)
            entry_vars.append((key, var))
        smtp_frame.columnconfigure(1, weight=1)

        # ── Features ───────────────────────────────────────────────
        feat_frame = ttk.LabelFrame(email_window, text=_t('gui.shell.main.admin.config.labels.features', default="Features"), padding=12)
        feat_frame.pack(fill="x", padx=15, pady=(0, 10))

        ttk.Label(feat_frame, text=_t('gui.shell.main.admin.config.labels.async_email_queue_template_support_bulk_sending_and_email_loggin', default="Async email queue, template support, bulk sending,\n"
                  "and email logging are built-in and always active."),
                  font=('Arial', 9), foreground="#555").pack(anchor="w")

        # ── Status ─────────────────────────────────────────────────
        status_text = "Configured" if env_vars.get("SMTP_HOST") else "Not configured"
        status_color = "#27ae60" if env_vars.get("SMTP_HOST") else "#e74c3c"
        status_frame = ttk.Frame(email_window)
        status_frame.pack(fill="x", padx=15)
        tk.Label(status_frame, text=f"Status: {status_text}",
                 font=('Arial', 10, 'bold'), fg=status_color).pack(anchor="w")
        tk.Label(status_frame, text=f"Config file: {env_path}",
                 font=('Arial', 8), fg="#888").pack(anchor="w")

        # ── Save / Close ──────────────────────────────────────────
        btn_frame = ttk.Frame(email_window)
        btn_frame.pack(fill="x", padx=15, pady=15)

        def _save_email():
            # Read existing .env, update SMTP keys, write back
            existing_lines = []
            if env_path.exists():
                existing_lines = env_path.read_text().splitlines()

            updated_keys = set()
            new_lines = []
            for line in existing_lines:
                stripped = line.strip()
                matched = False
                for key, var in entry_vars:
                    if stripped.startswith(f"{key}=") or stripped.startswith(f"# {key}="):
                        new_lines.append(f"{key}={var.get()}")
                        updated_keys.add(key)
                        matched = True
                        break
                if not matched:
                    new_lines.append(line)

            # Append any keys not already in the file
            for key, var in entry_vars:
                if key not in updated_keys:
                    new_lines.append(f"{key}={var.get()}")

            env_path.write_text("\n".join(new_lines) + "\n")
            messagebox.showinfo(_t('gui.shell.main.admin.config.dialogs.email_settings', default="Email Settings"), _t('gui.shell.main.admin.config.dialogs.smtp_settings_saved_to_env', default="SMTP settings saved to .env"),
                                parent=email_window)

        ttk.Button(btn_frame, text=_t('gui.shell.main.admin.config.buttons.save_to_env', default="Save to .env"), command=_save_email).pack(side="right", padx=5)
        ttk.Button(btn_frame, text=_t('gui.shell.main.admin.config.buttons.close', default="Close"), command=email_window.destroy).pack(side="right")

    except Exception as e:
        messagebox.showerror(_t("config_gui.errors.error", default="Error"), _t("config_gui.errors.failed_to_configure_email", error=str(e), default="Failed To Configure Email {error}"))

def configure_backup(self):
    """Configure backup settings with functional controls"""
    try:
        from education_system import paths
        from education_system.platform.identity.auth.core import UserAuth as _SharedAuth
        shared_auth = _SharedAuth()

        backup_window = tk.Toplevel(self.root)
        _install_clean_close(backup_window)
        backup_window.title(_t("config_gui.backup.title", default="===== BACKUP ====="))
        backup_window.geometry("600x520")

        ttk.Label(backup_window, text=_t("config_gui.backup.header", default="Header"),
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # ── Backup Location ────────────────────────────────────────
        loc_frame = ttk.LabelFrame(backup_window, text=_t('gui.shell.main.admin.config.labels.backup_location', default="Backup Location"), padding=10)
        loc_frame.pack(fill="x", padx=15, pady=(0, 8))
        ttk.Label(loc_frame, text=str(paths.UNIVERSITY_BACKUP_DIR), font=('Arial', 9)).pack(anchor="w")

        # ── Schedule ───────────────────────────────────────────────
        sched_frame = ttk.LabelFrame(backup_window, text=_t('gui.shell.main.admin.config.labels.schedule', default="Schedule"), padding=10)
        sched_frame.pack(fill="x", padx=15, pady=(0, 8))

        auto_var = tk.BooleanVar(value=shared_auth.get_setting("backup_auto", True))
        ttk.Checkbutton(sched_frame, text=_t('gui.shell.main.admin.config.buttons.auto_backup_enabled', default="Auto-Backup Enabled"), variable=auto_var).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=3)

        ttk.Label(sched_frame, text=_t('gui.shell.main.admin.config.labels.frequency', default="Frequency:")).grid(row=1, column=0, sticky="w", pady=3)
        freq_var = tk.StringVar(value=str(shared_auth.get_setting("backup_frequency", "Daily")))
        ttk.Combobox(sched_frame, textvariable=freq_var,
                     values=["Hourly", "Daily", "Weekly", "Monthly"],
                     state="readonly", width=12).grid(row=1, column=1, sticky="w", padx=10)

        ttk.Label(sched_frame, text=_t('gui.shell.main.admin.config.labels.retention_days', default="Retention (days):")).grid(row=2, column=0, sticky="w", pady=3)
        retention_var = tk.StringVar(value=str(shared_auth.get_setting("backup_retention_days", "30")))
        ttk.Spinbox(sched_frame, from_=7, to=365, textvariable=retention_var, width=8).grid(
            row=2, column=1, sticky="w", padx=10)

        # ── Options ────────────────────────────────────────────────
        opt_frame = ttk.LabelFrame(backup_window, text=_t('gui.shell.main.admin.config.labels.options', default="Options"), padding=10)
        opt_frame.pack(fill="x", padx=15, pady=(0, 8))

        compress_var = tk.BooleanVar(value=shared_auth.get_setting("backup_compression", True))
        ttk.Checkbutton(opt_frame, text=_t('gui.shell.main.admin.config.buttons.enable_compression_gzip', default="Enable Compression (GZIP)"), variable=compress_var).pack(anchor="w")

        encrypt_var = tk.BooleanVar(value=shared_auth.get_setting("backup_encryption", False))
        ttk.Checkbutton(opt_frame, text=_t('gui.shell.main.admin.config.buttons.enable_encryption_aes', default="Enable Encryption (AES)"), variable=encrypt_var).pack(anchor="w")

        ttk.Label(opt_frame, text=_t('gui.shell.main.admin.config.labels.backup_type', default="Backup Type:")).pack(anchor="w", pady=(8, 0))
        type_var = tk.StringVar(value=str(shared_auth.get_setting("backup_type", "Full")))
        ttk.Combobox(opt_frame, textvariable=type_var,
                     values=["Full", "Incremental", "Differential"],
                     state="readonly", width=15).pack(anchor="w", pady=2)

        # ── Save / Close ──────────────────────────────────────────
        btn_frame = ttk.Frame(backup_window)
        btn_frame.pack(fill="x", padx=15, pady=15)

        def _save_backup():
            shared_auth.set_setting("backup_auto", auto_var.get())
            shared_auth.set_setting("backup_frequency", freq_var.get())
            shared_auth.set_setting("backup_retention_days", retention_var.get())
            shared_auth.set_setting("backup_compression", compress_var.get())
            shared_auth.set_setting("backup_encryption", encrypt_var.get())
            shared_auth.set_setting("backup_type", type_var.get())
            messagebox.showinfo(_t('gui.shell.main.admin.config.dialogs.backup_settings', default="Backup Settings"), _t('gui.shell.main.admin.config.dialogs.backup_configuration_saved', default="Backup configuration saved."),
                                parent=backup_window)

        ttk.Button(btn_frame, text=_t('gui.shell.main.admin.config.buttons.save_settings', default="Save Settings"), command=_save_backup).pack(side="right", padx=5)
        ttk.Button(btn_frame, text=_t('gui.shell.main.admin.config.buttons.close', default="Close"), command=backup_window.destroy).pack(side="right")

    except Exception as e:
        messagebox.showerror(_t("config_gui.errors.error", default="Error"), _t("config_gui.errors.failed_to_configure_backup", error=str(e), default="Failed To Configure Backup {error}"))

def configure_security(self):
    """Configure security settings with toggleable password reset policy"""
    try:
        security_window = tk.Toplevel(self.root)
        _install_clean_close(security_window)
        security_window.title(_t("config_gui.security.title", default="===== SECURITY ====="))
        security_window.geometry("650x600")

        ttk.Label(security_window, text=_t("config_gui.security.header", default="Header"),
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # ── Forced Password Reset toggle ──────────────────────────────
        toggle_frame = ttk.LabelFrame(security_window,
                                       text=_t('gui.shell.main.admin.config.labels.password_reset_policy', default="Password Reset Policy"), padding=15)
        toggle_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Read current setting from shared auth
        from education_system.platform.identity.auth.core import UserAuth as _SharedAuth
        _shared_auth = _SharedAuth()
        force_reset_on = _shared_auth.get_system_password_policy("university")

        force_reset_var = tk.BooleanVar(value=bool(force_reset_on))

        desc_label = ttk.Label(
            toggle_frame,
            text=_t('gui.shell.main.admin.config.labels.when_enabled_university_users_whose_password_has_expired_90_days', default="When enabled, University users whose password has expired\n"
                 "(>90 days) or was never set must change it on login.\n"
                 "(This setting applies to the University system only.)"),
            wraplength=550, justify=tk.LEFT,
        )
        desc_label.pack(anchor=tk.W, pady=(0, 8))

        status_var = tk.StringVar()
        def _update_status():
            if force_reset_var.get():
                status_var.set("Status: ON — users with expired passwords must reset on login")
            else:
                status_var.set("Status: OFF — password expiry checks are skipped")
        _update_status()

        def _toggle_force_reset():
            new_val = force_reset_var.get()
            try:
                _shared_auth.set_system_password_policy("university", new_val)
                _update_status()
                state_text = "enabled" if new_val else "disabled"
                messagebox.showinfo(_t('gui.shell.main.admin.config.dialogs.setting_updated', default="Setting Updated"),
                                    f"Forced password reset has been {state_text}.",
                                    parent=security_window)
            except Exception as exc:
                messagebox.showerror(_t('gui.shell.main.admin.config.dialogs.error', default="Error"),
                                     f"Failed to update setting: {exc}",
                                     parent=security_window)

        toggle_btn = ttk.Checkbutton(
            toggle_frame,
            text=_t('gui.shell.main.admin.config.buttons.force_password_reset_for_expired_passwords', default="Force password reset for expired passwords"),
            variable=force_reset_var,
            command=_toggle_force_reset,
        )
        toggle_btn.pack(anchor=tk.W)

        status_label = ttk.Label(toggle_frame, textvariable=status_var,
                                  font=('Arial', 9, 'italic'))
        status_label.pack(anchor=tk.W, pady=(4, 0))

        # ── Security info (read-only) ─────────────────────────────────
        security_text = scrolledtext.ScrolledText(security_window, wrap=tk.WORD, height=16,
                                                  fg="#000000", bg="#FFFFFF")
        security_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        security_info = _t("config_gui.security.info_header", default="Info:") + """
================================

""" + _t("config_gui.security.authentication", default="Authentication") + """
- """ + _t("config_gui.security.password_hashing", default="Password Hashing") + """
- """ + _t("config_gui.security.hash_iterations", default="Hash Iterations") + """
- """ + _t("config_gui.security.salt", default="Salt") + """
- """ + _t("config_gui.security.mfa_support", default="Mfa Support") + """

""" + _t("config_gui.security.session_management", default="Session Management") + """
- """ + _t("config_gui.security.token_sessions", default="Token Sessions") + """
- """ + _t("config_gui.security.session_timeout", default="Session Timeout") + """
- """ + _t("config_gui.security.concurrent_limits", default="Concurrent Limits") + """
- """ + _t("config_gui.security.auto_logout", default="Auto Logout") + """

""" + _t("config_gui.security.authorization", default="Authorization") + """
- """ + _t("config_gui.security.rbac", default="Rbac") + """
- """ + _t("config_gui.security.permission_checking", default="Permission Checking.") + """
- """ + _t("config_gui.security.roles", default="Roles") + """
- """ + _t("config_gui.security.granular_permissions", default="Granular Permissions") + """

""" + _t("config_gui.security.data_protection", default="Data Protection") + """
- """ + _t("config_gui.security.sql_injection", default="Sql Injection") + """
- """ + _t("config_gui.security.xss_protection", default="Xss Protection") + """
- """ + _t("config_gui.security.csrf_protection", default="Csrf Protection") + """
- """ + _t("config_gui.security.input_validation", default="Input Validation") + """

""" + _t("config_gui.security.audit_trail", default="Audit Trail") + """
- """ + _t("config_gui.security.modifications_logged", default="Modifications Logged") + """
- """ + _t("config_gui.security.user_attribution", default="User Attribution") + """
- """ + _t("config_gui.security.timestamp_tracking", default="Timestamp Tracking") + """
- """ + _t("config_gui.security.compliance_ready", default="Compliance Ready") + """

""" + _t("config_gui.security.best_practices", default="Best Practices") + """
- """ + _t("config_gui.security.password_updates", default="Password Updates") + """
- """ + _t("config_gui.security.enable_mfa", default="Enable Mfa") + """
- """ + _t("config_gui.security.monitor_logs", default="Monitor Logs") + """
- """ + _t("config_gui.security.review_permissions", default="Review Permissions") + """
- """ + _t("config_gui.security.keep_updated", default="Keep Updated") + """

""" + _t("config_gui.security.contact_note", default="Contact Note")
        security_text.insert("1.0", security_info)
        security_text.config(state=tk.DISABLED)

        ttk.Button(security_window, text=_t("config_gui.buttons.close", default="Close"), command=security_window.destroy).pack(pady=10)

    except Exception as e:
        messagebox.showerror(_t("config_gui.errors.error", default="Error"), _t("config_gui.errors.failed_to_configure_security", error=str(e), default="Failed To Configure Security {error}"))

def show_security_dashboard(self):
    """Launch comprehensive security & compliance dashboard"""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("config_gui.access.denied", default="Denied"), _t("config_gui.access.admin_required_security_dashboard", default="Admin Required Security Dashboard"))
        return

    if not SECURITY_DASHBOARD_AVAILABLE:
        messagebox.showerror(_t("config_gui.errors.error", default="Error"), _t("config_gui.errors.security_dashboard_unavailable", default="Security Dashboard Unavailable"))
        return

    try:
        user_id = self.auth.current_user.get('id', 1)
        dashboard = SecurityDashboard(self.root, user_id)
        try:
            from education_system.systems.university.domains.research.interfaces.gui.research.external_quality_assurance.qa_receivers import consume_eqa_context
            consume_eqa_context(self, "Security Dashboard", target=dashboard)
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
        print(_t("config_gui.messages.security_dashboard_opened", default="Security Dashboard Opened"))
    except Exception as e:
        messagebox.showerror(_t("config_gui.errors.error", default="Error"), _t("config_gui.errors.failed_to_open_security_dashboard", error=str(e), default="Failed To Open Security Dashboard {error}"))
def show_audit_log_viewer(self):
    """Launch audit log viewer for searching and analyzing audit logs.

    If a contextual right-click brought the user here (e.g. Library →
    "View audit log for this book"), the pending academic context dict
    on ``self._last_academic_context`` is consumed and forwarded as a
    ``prefilter`` so the most-specific id is dropped into the search
    box before the initial query runs."""
    if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
        messagebox.showerror(_t("config_gui.access.denied", default="Denied"), _t("config_gui.access.admin_required_audit_log", default="Admin Required Audit Log"))
        return

    if not AUDIT_LOG_VIEWER_AVAILABLE:
        messagebox.showerror(_t("config_gui.errors.error", default="Error"), _t("config_gui.errors.audit_log_viewer_unavailable", default="Audit Log Viewer Unavailable"))
        return

    prefilter = None
    try:
        from education_system.systems.university.shell.gui.main.features.academic_link_bar import (
            consume_context as _consume_academic_context,
        )
        prefilter = _consume_academic_context(self)
    except Exception:
        logger.debug("audit viewer: could not consume academic context", exc_info=True)

    try:
        user_id = self.auth.current_user.get('id', 1)
        viewer = _open_audit_log_viewer(self.root, user_id, prefilter=prefilter)
        print(_t("config_gui.messages.audit_log_viewer_opened", default="Audit Log Viewer Opened"))
    except Exception as e:
        messagebox.showerror(_t("config_gui.errors.error", default="Error"), _t("config_gui.errors.failed_to_open_audit_log_viewer", error=str(e), default="Failed To Open Audit Log Viewer {error}"))
def show_activity_logger(self):
    """Launch the Enhanced Activity Logger GUI in a child window"""
    if not self.auth.current_user:
        messagebox.showerror(_t("config_gui.errors.error", default="Error"), _t("config_gui.access.login_required_activity_logger", default="Login Required Activity Logger"))
        return

    # Check permissions - allow admin and staff
    user_role = self.auth.current_user.get('role', '')
    if user_role not in ['admin', 'staff']:
        messagebox.showerror(_t("config_gui.errors.error", default="Error"), _t("config_gui.access.no_permission_activity_logger", default="No Permission Activity Logger."))
        return

    try:
        if not ACTIVITY_LOGGER_GUI_AVAILABLE:
            messagebox.showerror(_t("config_gui.activity_logger.title", default="===== ACTIVITY LOGGER ====="), _t("config_gui.errors.activity_logger_unavailable", error="Module not available", default="Activity Logger Unavailable {error}"))
            return

        # Create a new window for the Activity Logger GUI
        logger_window = tk.Toplevel(self.root)
        _install_clean_close(logger_window)
        logger_window.title(_t("config_gui.activity_logger.window_title", default="===== WINDOW ====="))
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
            logger.debug("Suppressed exception", exc_info=True)

        # Initialize the Activity Logger GUI in the new window using parent parameter
        activity_logger_gui = ActivityLoggerGUI(auth=self.auth, parent=logger_window)

        print(_t("config_gui.messages.activity_logger_opened", default="Activity Logger opened"))

    except Exception as e:
        messagebox.showerror(_t("config_gui.errors.error", default="Error"), _t("config_gui.errors.failed_to_open_activity_logger", error=str(e), default="Failed To Open Activity Logger {error}"))
        print(f"Activity Logger error: {e}")
def show_activity_log(self):
    """Open Log Management GUI (in a separate window)"""
    try:
        # Prefer the local file the user provided
        from education_system.systems.university.shell.gui.logging.log_management_gui import LogManagementGUI
    except Exception:
        # Optional fallback to the refactored package if present
        try:
            from education_system.systems.university.shell.gui.logging.log_management_gui import LogManagementGUI
        except Exception as e:
            messagebox.showerror(_t("config_gui.log_management.unavailable", default="Unavailable"), _t("config_gui.errors.log_management_not_found", error=str(e), default="Log Management Not Found {error}"))
            return

    try:
        # Open inside the existing app as a child window (no extra mainloop)
        win = tk.Toplevel(self.root)
        _install_clean_close(win)
        win.title(_t("config_gui.log_management.title", default="===== LOG MANAGEMENT ====="))
        win.geometry("1200x800")
        LogManagementGUI(win, auth=self.auth)   # instantiate GUI from the file
    except Exception as e:
        messagebox.showerror(_t("config_gui.errors.error", default="Error"), _t("config_gui.errors.failed_to_open_log_management", error=str(e), default="Failed To Open Log Management {error}"))
