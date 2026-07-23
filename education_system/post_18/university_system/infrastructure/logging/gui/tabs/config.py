import tkinter as tk
from tkinter import ttk, messagebox
import logging

from education_system.post_18.university_system.infrastructure.logging.gui.helpers import _t

logger = logging.getLogger(__name__)


class ConfigMixin:
    """Mixin providing configuration tab functionality."""

    def setup_config_tab(self):
        """Setup the configuration tab"""
        self.config_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.config_frame, text="⚙️ " + _t("log_management.tabs.config"))

        # Main config frame with scrollbar
        canvas = tk.Canvas(self.config_frame)
        scrollbar = ttk.Scrollbar(self.config_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # General Settings
        general_frame = ttk.LabelFrame(scrollable_frame, text=_t("log_management.config.general_settings"))
        general_frame.pack(fill=tk.X, padx=10, pady=5)

        # Retention settings
        ttk.Label(general_frame, text=_t("log_management.config.log_retention")).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.retention_var = tk.StringVar()
        ttk.Entry(general_frame, textvariable=self.retention_var, width=10).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(general_frame, text=_t("log_management.config.auto_archive")).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.archive_var = tk.StringVar()
        ttk.Entry(general_frame, textvariable=self.archive_var, width=10).grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(general_frame, text=_t("log_management.config.max_log_size")).grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.max_size_var = tk.StringVar()
        ttk.Entry(general_frame, textvariable=self.max_size_var, width=10).grid(row=2, column=1, padx=5, pady=2)

        # Feature toggles
        features_frame = ttk.LabelFrame(scrollable_frame, text=_t("log_management.config.feature_settings"))
        features_frame.pack(fill=tk.X, padx=10, pady=5)

        self.realtime_var = tk.BooleanVar()
        ttk.Checkbutton(features_frame, text=_t("log_management.config.enable_realtime"),
                       variable=self.realtime_var).pack(anchor="w", padx=5, pady=2)

        self.alerts_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(features_frame, text=_t("log_management.config.enable_alerts"),
                       variable=self.alerts_enabled_var).pack(anchor="w", padx=5, pady=2)

        self.analytics_var = tk.BooleanVar()
        ttk.Checkbutton(features_frame, text=_t("log_management.config.enable_analytics"),
                       variable=self.analytics_var).pack(anchor="w", padx=5, pady=2)

        self.encryption_var = tk.BooleanVar()
        ttk.Checkbutton(features_frame, text=_t("log_management.config.enable_encryption"),
                       variable=self.encryption_var).pack(anchor="w", padx=5, pady=2)

        # Email Settings
        email_frame = ttk.LabelFrame(scrollable_frame, text=_t("log_management.config.email_notifications"))
        email_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(email_frame, text=_t("log_management.config.alert_email")).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.alert_email_var = tk.StringVar()
        ttk.Entry(email_frame, textvariable=self.alert_email_var, width=30).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(email_frame, text=_t("log_management.config.smtp_server")).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.smtp_server_var = tk.StringVar()
        ttk.Entry(email_frame, textvariable=self.smtp_server_var, width=30).grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(email_frame, text=_t("log_management.config.smtp_port")).grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.smtp_port_var = tk.StringVar()
        ttk.Entry(email_frame, textvariable=self.smtp_port_var, width=10).grid(row=2, column=1, padx=5, pady=2)

        # SMTP Configuration
        smtp_frame = ttk.LabelFrame(scrollable_frame, text=_t("log_management.config.smtp_config"))
        smtp_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(smtp_frame, text=_t("log_management.config.smtp_username")).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.smtp_username_var = tk.StringVar()
        ttk.Entry(smtp_frame, textvariable=self.smtp_username_var, width=30).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(smtp_frame, text=_t("log_management.config.smtp_password")).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.smtp_password_var = tk.StringVar()
        ttk.Entry(smtp_frame, textvariable=self.smtp_password_var, width=30, show="*").grid(row=1, column=1, padx=5, pady=2)

        # Webhook Configuration
        webhook_frame = ttk.LabelFrame(scrollable_frame, text=_t("log_management.config.webhook_config"))
        webhook_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(webhook_frame, text=_t("log_management.config.webhook_secret")).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.webhook_secret_var = tk.StringVar()
        ttk.Entry(webhook_frame, textvariable=self.webhook_secret_var, width=30, show="*").grid(row=0, column=1, padx=5, pady=2)

        # API Settings
        api_frame = ttk.LabelFrame(scrollable_frame, text=_t("log_management.config.api_settings"))
        api_frame.pack(fill=tk.X, padx=10, pady=5)

        self.api_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(api_frame, text=_t("log_management.config.enable_api"),
                       variable=self.api_enabled_var).pack(anchor="w", padx=5, pady=2)

        ttk.Label(api_frame, text=_t("log_management.config.api_secret_key")).pack(anchor="w", padx=5)
        self.api_key_var = tk.StringVar()
        api_key_frame = ttk.Frame(api_frame)
        api_key_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Entry(api_key_frame, textvariable=self.api_key_var, width=40, show="*").pack(side=tk.LEFT)
        ttk.Button(api_key_frame, text=_t("log_management.config.generate"), command=self.generate_api_key).pack(side=tk.LEFT, padx=(5, 0))

        api_control_frame = ttk.Frame(api_frame)
        api_control_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Button(api_control_frame, text=_t("log_management.config.start_api_server"),
                  command=self.start_api_server).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(api_control_frame, text=_t("log_management.config.view_api_stats"),
                  command=lambda: self.view_api_stats(self.log_manager)).pack(side=tk.LEFT)

        # Config buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="💾 " + _t("log_management.config.buttons.save"),
                  command=self.save_configuration).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="🔄 " + _t("log_management.config.buttons.load"),
                  command=self.load_configuration).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="🔄 " + _t("log_management.config.buttons.reset"),
                  command=self.reset_configuration).pack(side=tk.LEFT)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Load current configuration
        self.load_configuration()

    def load_configuration(self):
        """Load current configuration into form"""
        if not self.log_manager:
            return

        try:
            config = self.log_manager.config.config

            self.retention_var.set(str(config.get('retention_days', 90)))
            self.archive_var.set(str(config.get('auto_archive_days', 30)))
            self.max_size_var.set(str(config.get('max_log_size_mb', 100)))

            self.realtime_var.set(config.get('enable_real_time', True))
            self.alerts_enabled_var.set(config.get('enable_alerts', True))
            self.analytics_var.set(config.get('enable_analytics', True))
            self.encryption_var.set(config.get('enable_encryption', True))
            self.smtp_username_var.set(config.get('smtp_username', ''))
            self.smtp_password_var.set(config.get('smtp_password', ''))
            self.webhook_secret_var.set(config.get('webhook_secret', ''))
            self.alert_email_var.set(config.get('alert_email', ''))
            self.smtp_server_var.set(config.get('smtp_server', ''))
            self.smtp_port_var.set(str(config.get('smtp_port', 587)))

            self.api_enabled_var.set(config.get('api_enabled', False))
            self.api_key_var.set(config.get('api_secret_key', ''))

        except Exception as e:
            print(f"Error loading configuration: {e}")

    def save_configuration(self):
        """Save configuration changes"""
        if not self.log_manager:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.messages.log_manager_not_available"))
            return

        try:
            # Validate and save each setting
            try:
                retention_days = int(self.retention_var.get())
                self.log_manager.config.set('retention_days', retention_days)
            except ValueError as e:
                logger.warning(f"Invalid retention_days value: {e}")

            try:
                archive_days = int(self.archive_var.get())
                self.log_manager.config.set('auto_archive_days', archive_days)
            except ValueError as e:
                logger.warning(f"Invalid auto_archive_days value: {e}")

            try:
                max_size = int(self.max_size_var.get())
                self.log_manager.config.set('max_log_size_mb', max_size)
            except ValueError as e:
                logger.warning(f"Invalid max_log_size_mb value: {e}")

            self.log_manager.config.set('enable_real_time', self.realtime_var.get())
            self.log_manager.config.set('enable_alerts', self.alerts_enabled_var.get())
            self.log_manager.config.set('enable_analytics', self.analytics_var.get())
            self.log_manager.config.set('enable_encryption', self.encryption_var.get())
            self.log_manager.config.set('smtp_username', self.smtp_username_var.get())
            self.log_manager.config.set('smtp_password', self.smtp_password_var.get())
            self.log_manager.config.set('webhook_secret', self.webhook_secret_var.get())
            self.log_manager.config.set('alert_email', self.alert_email_var.get())
            self.log_manager.config.set('smtp_server', self.smtp_server_var.get())

            try:
                smtp_port = int(self.smtp_port_var.get())
                self.log_manager.config.set('smtp_port', smtp_port)
            except ValueError as e:
                logger.warning(f"Invalid smtp_port value: {e}")

            self.log_manager.config.set('api_enabled', self.api_enabled_var.get())
            self.log_manager.config.set('api_secret_key', self.api_key_var.get())

            messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.config.messages.saved"))
            self.update_status(_t("log_management.messages.config_saved"))

        except Exception as e:
            messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.config_save", error=str(e)))

    def reset_configuration(self):
        """Reset configuration to defaults"""
        if messagebox.askyesno(_t("log_management.messages.confirm"), _t("log_management.config.messages.reset_confirm")):
            try:
                self.log_manager.config.config = self.log_manager.config.default_config.copy()
                self.log_manager.config.save_config()
                self.load_configuration()
                messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.config.messages.reset_done"))
            except Exception as e:
                messagebox.showerror(_t("log_management.messages.error"), _t("log_management.errors.config_load", error=str(e)))

    def generate_api_key(self):
        """Generate new API key"""
        import secrets
        new_key = secrets.token_urlsafe(32)
        self.api_key_var.set(new_key)
        messagebox.showinfo(_t("log_management.config.api_key_generated"), _t("log_management.config.api_key_message"))
