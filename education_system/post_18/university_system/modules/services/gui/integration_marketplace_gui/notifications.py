"""Notifications and alerts methods for IntegrationMarketplaceGUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import json
import logging

from education_system.post_18.university_system.infrastructure.database.db import transaction
from education_system.post_18.university_system.core.activity_logger import log_activity
from education_system.post_18.university_system.core.i18n import get_text as _t

logger = logging.getLogger(__name__)


class NotificationsMixin:
    """Mixin providing notifications and alerts methods."""

    def configure_alert_rules(self):
        """Set up custom alerts for error thresholds"""
        try:
            selected = self.installed_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select an integration to configure alerts")
                return

            install_id = self.installed_tree.item(selected[0])['values'][0]
            integration_name = self.installed_tree.item(selected[0])['values'][1]

            dialog = tk.Toplevel(self.root)
            dialog.title(f"Alert Rules: {integration_name}")
            dialog.geometry("500x450")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text="Configure Alert Rules",
                     style='Title.TLabel').pack(pady=10)

            # Error threshold
            ttk.Label(dialog, text="Alert on consecutive failures:").pack(anchor='w', padx=10, pady=5)
            failures_var = tk.StringVar(value="3")
            ttk.Spinbox(dialog, from_=1, to=10, textvariable=failures_var, width=10).pack(anchor='w', padx=10)

            # Error rate threshold
            ttk.Label(dialog, text="Alert when error rate exceeds (%):").pack(anchor='w', padx=10, pady=5)
            rate_var = tk.StringVar(value="20")
            ttk.Spinbox(dialog, from_=1, to=100, textvariable=rate_var, width=10).pack(anchor='w', padx=10)

            # No sync alert
            ttk.Label(dialog, text="Alert if no sync for (hours):").pack(anchor='w', padx=10, pady=5)
            hours_var = tk.StringVar(value="24")
            ttk.Spinbox(dialog, from_=1, to=168, textvariable=hours_var, width=10).pack(anchor='w', padx=10)

            # Notification methods
            ttk.Label(dialog, text="Notification Methods:").pack(anchor='w', padx=10, pady=10)

            email_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(dialog, text="Email", variable=email_var).pack(anchor='w', padx=20)

            webhook_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(dialog, text="Webhook", variable=webhook_var).pack(anchor='w', padx=20)

            def save_rules():
                rules = [
                    {
                        'type': 'consecutive_failures',
                        'threshold': int(failures_var.get()),
                        'notify_email': email_var.get(),
                        'notify_webhook': webhook_var.get()
                    },
                    {
                        'type': 'error_rate',
                        'threshold_percent': int(rate_var.get()),
                        'notify_email': email_var.get(),
                        'notify_webhook': webhook_var.get()
                    },
                    {
                        'type': 'no_sync_hours',
                        'threshold_hours': int(hours_var.get()),
                        'notify_email': email_var.get(),
                        'notify_webhook': webhook_var.get()
                    }
                ]

                with transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE installed_integrations
                        SET configuration = json_set(
                            COALESCE(configuration, '{}'),
                            '$.alert_rules', ?
                        )
                        WHERE install_id = ?
                    ''', (json.dumps(rules), install_id))

                log_activity('configure', 'alert_rules', install_id,
                            details={'rules_count': len(rules)})

                messagebox.showinfo(_t("common.success"), "Alert rules configured successfully!")
                dialog.destroy()

            ttk.Button(dialog, text="Save Alert Rules", command=save_rules).pack(pady=20)

        except Exception as e:
            logger.error(f"Error configuring alert rules: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to configure alerts: {e}")

    def subscribe_to_notifications(self):
        """Subscribe users to integration events"""
        try:
            selected = self.installed_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select an integration to subscribe")
                return

            install_id = self.installed_tree.item(selected[0])['values'][0]
            integration_name = self.installed_tree.item(selected[0])['values'][1]

            dialog = tk.Toplevel(self.root)
            dialog.title(f"Subscribe: {integration_name}")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text="Subscribe to Notifications",
                     style='Title.TLabel').pack(pady=10)

            ttk.Label(dialog, text="Email Address:").pack(anchor='w', padx=10, pady=5)
            email_var = tk.StringVar(value=f"{self.auth.current_user.get('username', 'user')}@university.edu")
            ttk.Entry(dialog, textvariable=email_var, width=40).pack(padx=10)

            ttk.Label(dialog, text="Subscribe to Events:").pack(anchor='w', padx=10, pady=10)

            event_vars = {}
            events = ['sync_complete', 'sync_failed', 'error_threshold', 'credential_expiring', 'status_change']
            for event in events:
                event_vars[event] = tk.BooleanVar(value=event in ['sync_failed', 'error_threshold'])
                ttk.Checkbutton(dialog, text=event.replace('_', ' ').title(),
                               variable=event_vars[event]).pack(anchor='w', padx=20)

            def subscribe():
                email = email_var.get().strip()
                if not email:
                    messagebox.showwarning(_t("common.warning"), "Please enter an email address")
                    return

                selected_events = [event for event, var in event_vars.items() if var.get()]
                if not selected_events:
                    messagebox.showwarning(_t("common.warning"), "Please select at least one event")
                    return

                subscription = {
                    'user_email': email,
                    'event_types': selected_events,
                    'subscribed_at': datetime.now().isoformat()
                }

                with transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT configuration FROM installed_integrations
                        WHERE install_id = ?
                    ''', (install_id,))
                    row = cursor.fetchone()

                    config = json.loads(row[0]) if row and row[0] else {}
                    subscriptions = config.get('subscriptions', [])

                    # Update or add subscription
                    existing = next((s for s in subscriptions if s['user_email'] == email), None)
                    if existing:
                        existing['event_types'] = selected_events
                    else:
                        subscriptions.append(subscription)

                    config['subscriptions'] = subscriptions

                    cursor.execute('''
                        UPDATE installed_integrations
                        SET configuration = ?
                        WHERE install_id = ?
                    ''', (json.dumps(config), install_id))

                log_activity('subscribe', 'notifications', install_id,
                            details={'email': email, 'events': selected_events})

                messagebox.showinfo(_t("common.success"), f"Subscribed {email} to {len(selected_events)} event(s)")
                dialog.destroy()

            ttk.Button(dialog, text="Subscribe", command=subscribe).pack(pady=20)

        except Exception as e:
            logger.error(f"Error subscribing to notifications: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to subscribe: {e}")

    def view_notification_history(self):
        """View past notifications sent"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title(_t("integration_marketplace.dialogs.notification_history"))
            dialog.geometry("800x500")
            dialog.transient(self.root)

            ttk.Label(dialog, text="Notification History",
                     style='Title.TLabel').pack(pady=10)

            # History tree
            tree_frame = ttk.Frame(dialog)
            tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

            columns = ('timestamp', 'integration', 'event_type', 'recipient', 'subject', 'status')
            tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

            for col in columns:
                tree.heading(col, text=col.replace('_', ' ').title())
                tree.column(col, width=120)

            tree.column('subject', width=200)

            vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=vsb.set)

            tree.pack(side='left', fill='both', expand=True)
            vsb.pack(side='right', fill='y')

            # Simulated notification history
            notifications = [
                (datetime.now().isoformat()[:19], 'Canvas LMS', 'sync_failed', 'admin@university.edu',
                 'Sync Failed: Canvas LMS', 'delivered'),
                ((datetime.now() - timedelta(hours=5)).isoformat()[:19], 'Zoom', 'sync_complete', 'admin@university.edu',
                 'Sync Complete: Zoom', 'delivered'),
                ((datetime.now() - timedelta(days=1)).isoformat()[:19], 'Google Workspace', 'error_threshold', 'it@university.edu',
                 'Error Threshold Exceeded', 'delivered'),
            ]

            for notification in notifications:
                tree.insert('', 'end', values=notification)

            ttk.Button(dialog, text=_t("common.close"), command=dialog.destroy).pack(pady=10)

            log_activity('view', 'notification_history', None)

        except Exception as e:
            logger.error(f"Error viewing notification history: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to view history: {e}")

    def test_notification_channel(self):
        """Send test notification to verify setup"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title(_t("integration_marketplace.dialogs.test_channel"))
            dialog.geometry("500x350")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text="Test Notification Channel",
                     style='Title.TLabel').pack(pady=10)

            ttk.Label(dialog, text="Channel Type:").pack(anchor='w', padx=10, pady=5)
            channel_var = tk.StringVar(value='email')
            channel_frame = ttk.Frame(dialog)
            channel_frame.pack(fill='x', padx=10, pady=5)

            for channel in ['email', 'webhook', 'slack']:
                ttk.Radiobutton(channel_frame, text=channel.title(), variable=channel_var,
                               value=channel).pack(side='left', padx=10)

            ttk.Label(dialog, text="Target (email/URL/channel):").pack(anchor='w', padx=10, pady=5)
            target_var = tk.StringVar(value=f"{self.auth.current_user.get('username', 'user')}@university.edu")
            ttk.Entry(dialog, textvariable=target_var, width=50).pack(padx=10)

            result_frame = ttk.LabelFrame(dialog, text="Test Result", padding=10)
            result_frame.pack(fill='both', expand=True, padx=10, pady=10)

            result_label = ttk.Label(result_frame, text="Click 'Send Test' to test the notification channel")
            result_label.pack(pady=20)

            def send_test():
                channel = channel_var.get()
                target = target_var.get().strip()

                if not target:
                    messagebox.showwarning(_t("common.warning"), "Please enter a target")
                    return

                # Simulate test
                success = True
                if channel == 'email':
                    message = f"Test email would be sent to: {target}"
                elif channel == 'webhook':
                    message = f"Test webhook would be sent to: {target}"
                elif channel == 'slack':
                    message = f"Test Slack message would be sent to: {target}"
                else:
                    message = f"Unknown channel type: {channel}"
                    success = False

                if success:
                    result_label.config(text=f"SUCCESS\n\n{message}\n\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    result_label.config(text=f"FAILED\n\n{message}")

                log_activity('test', 'notification_channel', None,
                            details={'channel': channel, 'target': target, 'success': success})

            ttk.Button(dialog, text="Send Test", command=send_test).pack(pady=10)
            ttk.Button(dialog, text=_t("common.close"), command=dialog.destroy).pack(pady=5)

        except Exception as e:
            logger.error(f"Error testing notification channel: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to test channel: {e}")
