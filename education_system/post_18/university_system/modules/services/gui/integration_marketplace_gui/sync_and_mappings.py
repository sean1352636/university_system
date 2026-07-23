"""Sync log and data mapping/webhook methods for IntegrationMarketplaceGUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from datetime import datetime
import logging
import traceback

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity
from education_system.post_18.university_system.core.i18n import get_text as _t

try:
    from education_system.post_18.university_system.modules.shared.services.integrations.integration_marketplace_core import (
        DataMappingManager,
        WebhookManager,
    )
    MANAGERS_AVAILABLE = True
except ImportError:
    MANAGERS_AVAILABLE = False

logger = logging.getLogger(__name__)


class SyncAndMappingsMixin:
    """Mixin providing sync log viewing, data mapping, and webhook methods."""

    def view_sync_details(self):
        """View sync log details"""
        try:
            selected = self.sync_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select a sync log to view")
                return

            log_id = self.sync_tree.item(selected[0])['values'][0]

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT isl.*, ic.integration_name
                    FROM integration_sync_logs isl
                    JOIN installed_integrations ii ON isl.install_id = ii.install_id
                    JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                    WHERE isl.log_id = ?
                ''', (log_id,))

                log = cursor.fetchone()

            if not log:
                messagebox.showerror(_t("common.error"), "Sync log not found")
                return

            details = "Sync Log Details\n\n"
            details += f"Log ID: {log[0]}\n"
            details += f"Integration: {log[8]}\n"
            details += f"Start Time: {log[2]}\n"
            details += f"End Time: {log[3] or 'Still running'}\n"
            details += f"Status: {log[4]}\n"
            details += f"Records Synced: {log[5] or 0}\n"
            details += f"Errors: {log[6] or 0}\n"
            if log[7]:
                details += f"\nError Details:\n{log[7]}"

            messagebox.showinfo("Sync Log Details", details)

        except Exception as e:
            logger.error(f"Error viewing sync details: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to view sync details: {e}")

    def export_sync_logs(self):
        """Export sync logs to CSV"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )

            if not filename:
                return

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT log_id, install_id, sync_start_time, sync_end_time,
                           sync_status, records_synced, errors_encountered
                    FROM integration_sync_logs
                    ORDER BY sync_start_time DESC
                ''')

                logs = cursor.fetchall()

            import csv
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Log ID', 'Install ID', 'Start Time', 'End Time',
                               'Status', 'Records Synced', 'Errors'])
                writer.writerows(logs)

            messagebox.showinfo(_t("common.success"), f"Sync logs exported to {filename}")
            log_activity('export', 'integration_sync_logs', None,
                        details={'filename': filename, 'record_count': len(logs)})

        except Exception as e:
            logger.error(f"Error exporting sync logs: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to export sync logs: {e}")

    def add_mapping(self):
        """Add data mapping"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Add Data Mapping")
            dialog.geometry("500x350")

            ttk.Label(dialog, text="Installation ID:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            install_id_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=install_id_var, width=35).grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Source Field:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            source_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=source_var, width=35).grid(row=1, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Target Field:").grid(row=2, column=0, padx=10, pady=5, sticky='w')
            target_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=target_var, width=35).grid(row=2, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Transformation Rule (Optional):").grid(row=3, column=0, padx=10, pady=5, sticky='nw')
            transform_text = scrolledtext.ScrolledText(dialog, width=35, height=5)
            transform_text.grid(row=3, column=1, padx=10, pady=5)

            def save_mapping():
                try:
                    install_id = install_id_var.get().strip()
                    source_field = source_var.get().strip()
                    target_field = target_var.get().strip()
                    transformation = transform_text.get('1.0', 'end-1c').strip()

                    if not install_id or not source_field or not target_field:
                        messagebox.showerror(_t("common.error"), "Installation ID, source field, and target field are required")
                        return

                    if MANAGERS_AVAILABLE:
                        mapping_id = DataMappingManager.create_mapping(
                            int(install_id), source_field, target_field, transformation
                        )
                    else:
                        with transaction() as conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                INSERT INTO integration_data_mappings
                                (install_id, source_field, target_field, transformation_rule, is_active)
                                VALUES (?, ?, ?, ?, 1)
                            ''', (install_id, source_field, target_field, transformation))

                            mapping_id = cursor.lastrowid

                    log_activity('create', 'integration_data_mapping', mapping_id,
                                details={'install_id': install_id})

                    messagebox.showinfo(_t("common.success"), "Data mapping created successfully")
                    dialog.destroy()
                    self.load_mappings()

                except Exception as e:
                    logger.error(f"Error creating mapping: {e}")
                    messagebox.showerror(_t("common.error"), f"Failed to create mapping: {e}")

            ttk.Button(dialog, text="Create Mapping", command=save_mapping).grid(
                row=4, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error(f"Error opening mapping dialog: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to open dialog: {e}")

    def edit_mapping(self):
        """Edit selected mapping"""
        try:
            selected = self.mappings_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select a mapping to edit")
                return

            mapping_id = self.mappings_tree.item(selected[0])['values'][0]

            # Fetch current mapping data
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT install_id, source_field, target_field, transformation_rule, is_active
                    FROM integration_data_mappings
                    WHERE mapping_id = ?
                ''', (mapping_id,))
                current_data = cursor.fetchone()

            if not current_data:
                messagebox.showerror(_t("common.error"), "Mapping not found")
                return

            # Create edit dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Edit Data Mapping")
            dialog.geometry("500x400")

            ttk.Label(dialog, text="Installation ID:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            install_id_var = tk.StringVar(value=str(current_data[0]))
            ttk.Entry(dialog, textvariable=install_id_var, width=35).grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Source Field:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            source_var = tk.StringVar(value=current_data[1] or '')
            ttk.Entry(dialog, textvariable=source_var, width=35).grid(row=1, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Target Field:").grid(row=2, column=0, padx=10, pady=5, sticky='w')
            target_var = tk.StringVar(value=current_data[2] or '')
            ttk.Entry(dialog, textvariable=target_var, width=35).grid(row=2, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Transformation Rule (Optional):").grid(row=3, column=0, padx=10, pady=5, sticky='nw')
            transform_text = scrolledtext.ScrolledText(dialog, width=35, height=5)
            transform_text.grid(row=3, column=1, padx=10, pady=5)
            if current_data[3]:
                transform_text.insert('1.0', current_data[3])

            ttk.Label(dialog, text="Status:").grid(row=4, column=0, padx=10, pady=5, sticky='w')
            is_active_var = tk.BooleanVar(value=bool(current_data[4]))
            ttk.Checkbutton(dialog, text="Active", variable=is_active_var).grid(row=4, column=1, padx=10, pady=5, sticky='w')

            def save_changes():
                try:
                    install_id = install_id_var.get().strip()
                    source_field = source_var.get().strip()
                    target_field = target_var.get().strip()
                    transformation = transform_text.get('1.0', 'end-1c').strip()
                    is_active = 1 if is_active_var.get() else 0

                    if not install_id or not source_field or not target_field:
                        messagebox.showerror(_t("common.error"), "Installation ID, source field, and target field are required")
                        return

                    if MANAGERS_AVAILABLE:
                        DataMappingManager.update_mapping(
                            mapping_id, int(install_id), source_field, target_field,
                            transformation, is_active
                        )
                    else:
                        with transaction() as conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                UPDATE integration_data_mappings
                                SET install_id = ?, source_field = ?, target_field = ?,
                                    transformation_rule = ?, is_active = ?
                                WHERE mapping_id = ?
                            ''', (install_id, source_field, target_field, transformation, is_active, mapping_id))

                    log_activity('update', 'integration_data_mapping', mapping_id,
                                details={'install_id': install_id, 'is_active': is_active})

                    messagebox.showinfo(_t("common.success"), "Data mapping updated successfully")
                    dialog.destroy()
                    self.load_mappings()

                except Exception as e:
                    logger.error(f"Error updating mapping: {e}")
                    messagebox.showerror(_t("common.error"), f"Failed to update mapping: {e}")

            button_frame = ttk.Frame(dialog)
            button_frame.grid(row=5, column=0, columnspan=2, pady=20)

            ttk.Button(button_frame, text=_t("common.save_changes"), command=save_changes).pack(side='left', padx=5)
            ttk.Button(button_frame, text=_t("common.cancel"), command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            logger.error(f"Error opening edit mapping dialog: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to open edit dialog: {e}")

    def delete_mapping(self):
        """Delete selected mapping"""
        try:
            selected = self.mappings_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select a mapping to delete")
                return

            mapping_id = self.mappings_tree.item(selected[0])['values'][0]

            if messagebox.askyesno("Confirm Delete", "Delete this data mapping?"):
                with transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM integration_data_mappings WHERE mapping_id = ?',
                                  (mapping_id,))

                log_activity('delete', 'integration_data_mapping', mapping_id,
                            details={'action': 'deleted'})

                messagebox.showinfo(_t("common.success"), "Data mapping deleted successfully")
                self.load_mappings()

        except Exception as e:
            logger.error(f"Error deleting mapping: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to delete mapping: {e}")

    def add_webhook(self):
        """Add webhook"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Add Webhook")
            dialog.geometry("500x300")

            ttk.Label(dialog, text="Installation ID:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            install_id_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=install_id_var, width=35).grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Webhook URL:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            url_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=url_var, width=35).grid(row=1, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Event Type:").grid(row=2, column=0, padx=10, pady=5, sticky='w')
            event_var = tk.StringVar(value='data_update')
            ttk.Combobox(dialog, textvariable=event_var,
                        values=['data_update', 'sync_complete', 'error', 'status_change'],
                        width=33, state='readonly').grid(row=2, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Secret Key (Optional):").grid(row=3, column=0, padx=10, pady=5, sticky='w')
            secret_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=secret_var, width=35, show='*').grid(row=3, column=1, padx=10, pady=5)

            def save_webhook():
                try:
                    install_id = install_id_var.get().strip()
                    webhook_url = url_var.get().strip()
                    event_type = event_var.get()
                    secret_key = secret_var.get().strip()

                    if not install_id or not webhook_url:
                        messagebox.showerror(_t("common.error"), "Installation ID and webhook URL are required")
                        return

                    if MANAGERS_AVAILABLE:
                        webhook_id = WebhookManager.register_webhook(
                            int(install_id), webhook_url, event_type, secret_key
                        )
                    else:
                        with transaction() as conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                INSERT INTO integration_webhooks
                                (install_id, webhook_url, event_type, secret_key, is_active)
                                VALUES (?, ?, ?, ?, 1)
                            ''', (install_id, webhook_url, event_type, secret_key))

                            webhook_id = cursor.lastrowid

                    log_activity('create', 'integration_webhook', webhook_id,
                                details={'install_id': install_id})

                    messagebox.showinfo(_t("common.success"), "Webhook registered successfully")
                    dialog.destroy()
                    self.load_webhooks()

                except Exception as e:
                    logger.error(f"Error registering webhook: {e}")
                    messagebox.showerror(_t("common.error"), f"Failed to register webhook: {e}")

            ttk.Button(dialog, text="Register Webhook", command=save_webhook).grid(
                row=4, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error(f"Error opening webhook dialog: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to open dialog: {e}")

    def edit_webhook(self):
        """Edit selected webhook"""
        messagebox.showinfo("Edit Webhook", "Edit webhook functionality - similar to add_webhook")

    def delete_webhook(self):
        """Delete selected webhook"""
        try:
            selected = self.webhooks_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select a webhook to delete")
                return

            webhook_id = self.webhooks_tree.item(selected[0])['values'][0]

            if messagebox.askyesno("Confirm Delete", "Delete this webhook?"):
                with transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM integration_webhooks WHERE webhook_id = ?',
                                  (webhook_id,))

                log_activity('delete', 'integration_webhook', webhook_id,
                            details={'action': 'deleted'})

                messagebox.showinfo(_t("common.success"), "Webhook deleted successfully")
                self.load_webhooks()

        except Exception as e:
            logger.error(f"Error deleting webhook: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to delete webhook: {e}")
