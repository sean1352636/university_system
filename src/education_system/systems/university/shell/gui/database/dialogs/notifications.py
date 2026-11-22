"""Notification configuration dialogs for the data backup GUI.

Provides EmailConfigDialog for configuring SMTP email notifications
and WebhookConfigDialog for configuring Slack and Discord webhook
integrations used by the backup notification system.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from education_system.systems.university.shell.gui.database.config import config, save_config
from education_system.systems.university.shell.gui.database.operations.backup_ops import send_email_notification, send_slack_notification, send_discord_notification


class EmailConfigDialog:
    """Dialog for configuring email notifications"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.database.dialogs.notifications.windows.email_configuration', default="Email Configuration"))
        self.dialog.geometry("440x380")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_current_settings()

        parent.wait_window(self.dialog)

    def create_widgets(self):
        """Create dialog widgets"""
        # SMTP settings
        smtp_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.notifications.labels.smtp_settings', default="SMTP Settings"), padding=10)
        smtp_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(smtp_frame, text=_t('gui.shell.database.dialogs.notifications.labels.smtp_server', default="SMTP Server:")).grid(row=0, column=0, sticky="w", pady=2)
        self.smtp_server_var = tk.StringVar()
        ttk.Entry(smtp_frame, textvariable=self.smtp_server_var, width=30).grid(row=0, column=1, padx=5)

        ttk.Label(smtp_frame, text=_t('gui.shell.database.dialogs.notifications.labels.port', default="Port:")).grid(row=1, column=0, sticky="w", pady=2)
        self.smtp_port_var = tk.StringVar()
        ttk.Entry(smtp_frame, textvariable=self.smtp_port_var, width=10).grid(row=1, column=1, sticky="w", padx=5)

        ttk.Label(smtp_frame, text=_t('gui.shell.database.dialogs.notifications.labels.username', default="Username:")).grid(row=2, column=0, sticky="w", pady=2)
        self.email_username_var = tk.StringVar()
        ttk.Entry(smtp_frame, textvariable=self.email_username_var, width=30).grid(row=2, column=1, padx=5)

        # No password here: backup alerts go through the university e-mail
        # outbox, which uses the e-mail system's securely stored SMTP login.
        ttk.Label(smtp_frame, foreground="#555555", wraplength=340,
                  text="Alerts are sent by the university e-mail system (Communication Hub "
                       "› Delivery); its password is kept in secure storage.").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=2)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(side="bottom", fill="x", padx=10, pady=10)

        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.notifications.buttons.test_email', default="Test Email"), command=self.test_email).pack(side="left", padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.notifications.buttons.save', default="Save"), command=self.save_settings).pack(side="right", padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.notifications.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side="right")

        # Recipients
        recipients_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.notifications.labels.recipients', default="Recipients"), padding=10)
        recipients_frame.pack(fill="both", expand=True, padx=10, pady=5)

        ttk.Label(recipients_frame, text=_t('gui.shell.database.dialogs.notifications.labels.email_addresses_one_per_line', default="Email addresses (one per line):")).pack(anchor="w")
        self.recipients_text = scrolledtext.ScrolledText(recipients_frame, height=6, wrap=tk.WORD)
        self.recipients_text.pack(fill="both", expand=True, pady=5)

    def load_current_settings(self):
        """Load current email settings"""
        self.smtp_server_var.set(config.get("smtp_server", "smtp.gmail.com"))
        self.smtp_port_var.set(str(config.get("smtp_port", 587)))
        self.email_username_var.set(config.get("email_username", ""))

        recipients = config.get("notification_recipients", [])
        self.recipients_text.insert(1.0, "\n".join(recipients))

    def test_email(self):
        """Test email configuration"""
        try:
            # Temporarily update config
            test_config = {
                "smtp_server": self.smtp_server_var.get(),
                "smtp_port": int(self.smtp_port_var.get()),
                "email_username": self.email_username_var.get(),
                "notification_recipients": [self.email_username_var.get()],
                "email_notifications": True
            }

            # Save current config
            old_config = {}
            for key in test_config:
                old_config[key] = config.get(key)

            # Apply test config
            config.update(test_config)

            # Send test email
            send_email_notification("Backup System Test", "This is a test email from the backup system.",
                                   [self.email_username_var.get()])

            # Restore config
            config.update(old_config)

            messagebox.showinfo(_t('gui.shell.database.dialogs.notifications.dialogs.test_successful', default="Test Successful"), _t('gui.shell.database.dialogs.notifications.dialogs.test_email_sent_successfully', default="Test email sent successfully!"))

        except Exception as e:
            messagebox.showerror(_t('gui.shell.database.dialogs.notifications.dialogs.test_failed', default="Test Failed"), f"Email test failed: {e}")

    def save_settings(self):
        """Save email settings"""
        try:
            config["smtp_server"] = self.smtp_server_var.get()
            config["smtp_port"] = int(self.smtp_port_var.get())
            config["email_username"] = self.email_username_var.get()
            config["email_password"] = ""   # never kept in the backup config

            recipients_text = self.recipients_text.get(1.0, tk.END).strip()
            recipients = [email.strip() for email in recipients_text.split('\n') if email.strip()]
            config["notification_recipients"] = recipients

            save_config()

            messagebox.showinfo(_t('gui.shell.database.dialogs.notifications.dialogs.success', default="Success"), _t('gui.shell.database.dialogs.notifications.dialogs.email_configuration_saved', default="Email configuration saved!"))
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror(_t('gui.shell.database.dialogs.notifications.dialogs.invalid_port', default="Invalid Port"), _t('gui.shell.database.dialogs.notifications.dialogs.please_enter_a_valid_port_number', default="Please enter a valid port number"))
        except Exception as e:
            messagebox.showerror(_t('gui.shell.database.dialogs.notifications.dialogs.error', default="Error"), f"Failed to save email configuration: {e}")

class WebhookConfigDialog:
    """Dialog for configuring webhooks"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.database.dialogs.notifications.windows.webhook_configuration', default="Webhook Configuration"))
        self.dialog.geometry("450x250")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_current_settings()

        parent.wait_window(self.dialog)

    def create_widgets(self):
        """Create dialog widgets"""
        # Slack webhook
        slack_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.notifications.labels.slack_webhook', default="Slack Webhook"), padding=10)
        slack_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(slack_frame, text=_t('gui.shell.database.dialogs.notifications.labels.webhook_url', default="Webhook URL:")).pack(anchor="w")
        self.slack_webhook_var = tk.StringVar()
        ttk.Entry(slack_frame, textvariable=self.slack_webhook_var, width=50).pack(fill="x", pady=2)

        ttk.Button(slack_frame, text=_t('gui.shell.database.dialogs.notifications.buttons.test_slack', default="Test Slack"), command=self.test_slack).pack(pady=5)

        # Discord webhook
        discord_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.notifications.labels.discord_webhook', default="Discord Webhook"), padding=10)
        discord_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(discord_frame, text=_t('gui.shell.database.dialogs.notifications.labels.webhook_url', default="Webhook URL:")).pack(anchor="w")
        self.discord_webhook_var = tk.StringVar()
        ttk.Entry(discord_frame, textvariable=self.discord_webhook_var, width=50).pack(fill="x", pady=2)

        ttk.Button(discord_frame, text=_t('gui.shell.database.dialogs.notifications.buttons.test_discord', default="Test Discord"), command=self.test_discord).pack(pady=5)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.notifications.buttons.save', default="Save"), command=self.save_settings).pack(side="right", padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.notifications.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side="right")

    def load_current_settings(self):
        """Load current webhook settings"""
        self.slack_webhook_var.set(config.get("slack_webhook", ""))
        self.discord_webhook_var.set(config.get("discord_webhook", ""))

    def test_slack(self):
        """Test Slack webhook"""
        try:
            old_webhook = config.get("slack_webhook", "")
            config["slack_webhook"] = self.slack_webhook_var.get()

            send_slack_notification("Test message from backup system GUI")

            config["slack_webhook"] = old_webhook

            messagebox.showinfo(_t('gui.shell.database.dialogs.notifications.dialogs.test_successful', default="Test Successful"), _t('gui.shell.database.dialogs.notifications.dialogs.slack_test_message_sent', default="Slack test message sent!"))

        except Exception as e:
            messagebox.showerror(_t('gui.shell.database.dialogs.notifications.dialogs.test_failed', default="Test Failed"), f"Slack test failed: {e}")

    def test_discord(self):
        """Test Discord webhook"""
        try:
            old_webhook = config.get("discord_webhook", "")
            config["discord_webhook"] = self.discord_webhook_var.get()

            send_discord_notification("Test message from backup system GUI")

            config["discord_webhook"] = old_webhook

            messagebox.showinfo(_t('gui.shell.database.dialogs.notifications.dialogs.test_successful', default="Test Successful"), _t('gui.shell.database.dialogs.notifications.dialogs.discord_test_message_sent', default="Discord test message sent!"))

        except Exception as e:
            messagebox.showerror(_t('gui.shell.database.dialogs.notifications.dialogs.test_failed', default="Test Failed"), f"Discord test failed: {e}")

    def save_settings(self):
        """Save webhook settings"""
        try:
            config["slack_webhook"] = self.slack_webhook_var.get()
            config["discord_webhook"] = self.discord_webhook_var.get()

            save_config()

            messagebox.showinfo(_t('gui.shell.database.dialogs.notifications.dialogs.success', default="Success"), _t('gui.shell.database.dialogs.notifications.dialogs.webhook_configuration_saved', default="Webhook configuration saved!"))
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t('gui.shell.database.dialogs.notifications.dialogs.error', default="Error"), f"Failed to save webhook configuration: {e}")
