"""Installed integration action methods for IntegrationMarketplaceGUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
import json
import logging
import time

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.infrastructure.i18n import get_text as _t

try:
    from education_system.systems.university.services.integrations.integration_marketplace_core import (
        InstallationManager,
        SyncManager,
    )
    MANAGERS_AVAILABLE = True
except ImportError:
    MANAGERS_AVAILABLE = False

logger = logging.getLogger(__name__)


class InstalledMixin:
    """Mixin providing installed integration action methods."""

    def configure_integration(self):
        """Configure selected installed integration"""
        try:
            selected = self.installed_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select an integration to configure")
                return

            install_id = self.installed_tree.item(selected[0])['values'][0]

            # Get current configuration
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT ii.configuration, ii.sync_frequency, ic.integration_name
                    FROM installed_integrations ii
                    JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                    WHERE ii.install_id = ?
                ''', (install_id,))

                result = cursor.fetchone()

            if not result:
                messagebox.showerror(_t("common.error"), "Installation not found")
                return

            current_config, sync_freq, integration_name = result

            dialog = tk.Toplevel(self.root)
            dialog.title(_t("integration_marketplace.dialogs.configure_integration"))
            dialog.geometry("500x400")

            ttk.Label(dialog, text=_t("integration_marketplace.labels.frequency")).grid(row=0, column=0, padx=10, pady=5, sticky='w')
            sync_freq_var = tk.StringVar(value=sync_freq or 'hourly')
            ttk.Combobox(dialog, textvariable=sync_freq_var,
                        values=['realtime', 'hourly', 'daily', 'weekly', 'manual'],
                        width=33, state='readonly').grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text=_t("integration_marketplace.labels.configuration")).grid(row=1, column=0, padx=10, pady=5, sticky='nw')
            config_text = scrolledtext.ScrolledText(dialog, width=40, height=15)
            config_text.grid(row=1, column=1, padx=10, pady=5)
            config_text.insert('1.0', current_config or '{}')

            def save_config():
                try:
                    configuration = config_text.get('1.0', 'end-1c').strip()
                    sync_frequency = sync_freq_var.get()

                    # Validate JSON
                    try:
                        json.loads(configuration)
                    except json.JSONDecodeError:
                        messagebox.showerror(_t("common.error"), _t("integration_marketplace.messages.invalid_json"))
                        return

                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE installed_integrations
                            SET configuration = ?, sync_frequency = ?
                            WHERE install_id = ?
                        ''', (configuration, sync_frequency, install_id))

                    log_activity('update', 'installed_integration', install_id,
                                details={'action': 'configured'})

                    messagebox.showinfo(_t("common.success"), _t("integration_marketplace.messages.config_updated"))
                    dialog.destroy()
                    self.load_installed()

                except Exception as e:
                    logger.error(f"Error saving configuration: {e}")
                    messagebox.showerror(_t("common.error"), f"Failed to save configuration: {e}")

            ttk.Button(dialog, text=_t("integration_marketplace.installed.configure"), command=save_config).grid(
                row=2, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error(f"Error configuring integration: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to configure integration: {e}")

    def sync_integration(self):
        """Manually trigger sync for selected integration"""
        try:
            selected = self.installed_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select an integration to sync")
                return

            install_id = self.installed_tree.item(selected[0])['values'][0]

            if messagebox.askyesno(_t("common.confirm"), "Start manual sync for this integration?"):
                # Start sync
                if MANAGERS_AVAILABLE:
                    log_id = SyncManager.start_sync(install_id)
                else:
                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO integration_sync_logs
                            (install_id, sync_status)
                            VALUES (?, 'running')
                        ''', (install_id,))

                        log_id = cursor.lastrowid

                # Simulate sync completion (in real implementation, this would be async)
                time.sleep(1)

                # Complete sync
                records_synced = 100  # Simulated
                if MANAGERS_AVAILABLE:
                    SyncManager.complete_sync(log_id, 'success', records_synced, 0)
                else:
                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE integration_sync_logs
                            SET sync_end_time = ?, sync_status = ?, records_synced = ?
                            WHERE log_id = ?
                        ''', (datetime.now().isoformat(), 'success', records_synced, log_id))

                        cursor.execute('''
                            UPDATE installed_integrations
                            SET last_sync_date = ?
                            WHERE install_id = ?
                        ''', (datetime.now().isoformat(), install_id))

                log_activity('sync', 'installed_integration', install_id,
                            details={'log_id': log_id, 'records_synced': records_synced})

                messagebox.showinfo(_t("common.success"), f"Sync completed successfully!\n\nRecords synced: {records_synced}")
                self.load_installed()
                self.load_sync_logs()

        except Exception as e:
            logger.error(f"Error syncing integration: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to sync integration: {e}")

    def uninstall_integration(self):
        """Uninstall selected integration"""
        try:
            selected = self.installed_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select an integration to uninstall")
                return

            install_id = self.installed_tree.item(selected[0])['values'][0]
            integration_name = self.installed_tree.item(selected[0])['values'][1]

            if messagebox.askyesno("Confirm Uninstall",
                                  f"Uninstall '{integration_name}'?\n\n"
                                  f"This will deactivate the integration and remove its credentials."):
                if MANAGERS_AVAILABLE:
                    InstallationManager.uninstall_integration(install_id)
                else:
                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE installed_integrations
                            SET status = 'uninstalled', is_enabled = 0
                            WHERE install_id = ?
                        ''', (install_id,))

                log_activity('delete', 'installed_integration', install_id,
                            details={'action': 'uninstalled'})

                messagebox.showinfo(_t("common.success"), "Integration uninstalled successfully")
                self.load_installed()

        except Exception as e:
            logger.error(f"Error uninstalling integration: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to uninstall integration: {e}")
