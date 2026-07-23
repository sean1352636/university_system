"""Bulk operation methods for IntegrationMarketplaceGUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
import logging

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity
from education_system.post_18.university_system.core.i18n import get_text as _t

logger = logging.getLogger(__name__)


class BulkOperationsMixin:
    """Mixin providing bulk operation methods."""

    def bulk_install_integrations(self):
        """Install multiple selected integrations at once"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title(_t("integration_marketplace.dialogs.bulk_install"))
            dialog.geometry("700x500")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text="Select integrations to install:",
                     style='Title.TLabel').pack(pady=10)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT ic.integration_id, ic.integration_name, ic.provider_name, ic.category
                    FROM integration_catalog ic
                    WHERE ic.is_active = 1
                      AND ic.integration_id NOT IN (
                          SELECT integration_id FROM installed_integrations
                          WHERE status = 'active'
                      )
                    ORDER BY ic.integration_name
                ''')
                available = cursor.fetchall()

            if not available:
                messagebox.showinfo(_t("common.info"), "No available integrations to install")
                dialog.destroy()
                return

            frame = ttk.Frame(dialog)
            frame.pack(fill='both', expand=True, padx=10, pady=5)

            listbox = tk.Listbox(frame, selectmode=tk.MULTIPLE, height=15)
            scrollbar = ttk.Scrollbar(frame, orient='vertical', command=listbox.yview)
            listbox.configure(yscrollcommand=scrollbar.set)

            for item in available:
                listbox.insert(tk.END, f"{item[1]} ({item[2]}) - {item[3]}")

            listbox.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            def install_selected():
                try:
                    selected_indices = listbox.curselection()
                    if not selected_indices:
                        messagebox.showwarning(_t("common.warning"), "Please select at least one integration")
                        return

                    installed_by = self.auth.current_user.get('username', 'Unknown')
                    success_count = 0
                    error_count = 0

                    for idx in selected_indices:
                        integration_id = available[idx][0]
                        try:
                            with transaction() as conn:
                                cursor = conn.cursor()
                                cursor.execute('SELECT version FROM integration_catalog WHERE integration_id = ?',
                                             (integration_id,))
                                version = cursor.fetchone()[0]

                                cursor.execute('''
                                    INSERT INTO installed_integrations
                                    (integration_id, installed_by, version_installed, status, is_enabled)
                                    VALUES (?, ?, ?, 'active', 1)
                                ''', (integration_id, installed_by, version))

                                cursor.execute('''
                                    UPDATE integration_catalog
                                    SET install_count = install_count + 1
                                    WHERE integration_id = ?
                                ''', (integration_id,))

                            success_count += 1
                        except Exception as e:
                            logger.error(f"Error installing integration {integration_id}: {e}")
                            error_count += 1

                    log_activity('bulk_install', 'installed_integrations', None,
                                details={'success_count': success_count, 'error_count': error_count})

                    messagebox.showinfo("Bulk Install Complete",
                                      f"Successfully installed: {success_count}\nErrors: {error_count}")
                    dialog.destroy()
                    self.load_catalog()
                    self.load_installed()

                except Exception as e:
                    logger.error(f"Error in bulk install: {e}")
                    messagebox.showerror(_t("common.error"), f"Bulk install failed: {e}")

            ttk.Button(dialog, text="Install Selected", command=install_selected,
                      style='Accent.TButton').pack(pady=10)

        except Exception as e:
            logger.error(f"Error opening bulk install dialog: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to open dialog: {e}")

    def bulk_uninstall_integrations(self):
        """Uninstall multiple integrations simultaneously"""
        try:
            selected = self.installed_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select integrations to uninstall")
                return

            if not messagebox.askyesno("Confirm Bulk Uninstall",
                                       f"Uninstall {len(selected)} selected integration(s)?"):
                return

            success_count = 0
            error_count = 0

            for item in selected:
                install_id = self.installed_tree.item(item)['values'][0]
                try:
                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE installed_integrations
                            SET status = 'uninstalled', is_enabled = 0
                            WHERE install_id = ?
                        ''', (install_id,))
                    success_count += 1
                except Exception as e:
                    logger.error(f"Error uninstalling {install_id}: {e}")
                    error_count += 1

            log_activity('bulk_uninstall', 'installed_integrations', None,
                        details={'success_count': success_count, 'error_count': error_count})

            messagebox.showinfo("Bulk Uninstall Complete",
                              f"Successfully uninstalled: {success_count}\nErrors: {error_count}")
            self.load_installed()

        except Exception as e:
            logger.error(f"Error in bulk uninstall: {e}")
            messagebox.showerror(_t("common.error"), f"Bulk uninstall failed: {e}")

    def bulk_enable_integrations(self):
        """Enable multiple disabled integrations"""
        try:
            selected = self.installed_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select integrations to enable")
                return

            success_count = 0
            error_count = 0

            for item in selected:
                install_id = self.installed_tree.item(item)['values'][0]
                try:
                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE installed_integrations
                            SET is_enabled = 1, status = 'active'
                            WHERE install_id = ?
                        ''', (install_id,))
                    success_count += 1
                except Exception as e:
                    logger.error(f"Error enabling {install_id}: {e}")
                    error_count += 1

            log_activity('bulk_enable', 'installed_integrations', None,
                        details={'success_count': success_count, 'error_count': error_count})

            messagebox.showinfo("Bulk Enable Complete",
                              f"Successfully enabled: {success_count}\nErrors: {error_count}")
            self.load_installed()

        except Exception as e:
            logger.error(f"Error in bulk enable: {e}")
            messagebox.showerror(_t("common.error"), f"Bulk enable failed: {e}")

    def bulk_disable_integrations(self):
        """Disable multiple integrations without uninstalling"""
        try:
            selected = self.installed_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select integrations to disable")
                return

            success_count = 0
            error_count = 0

            for item in selected:
                install_id = self.installed_tree.item(item)['values'][0]
                try:
                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE installed_integrations
                            SET is_enabled = 0, status = 'inactive'
                            WHERE install_id = ?
                        ''', (install_id,))
                    success_count += 1
                except Exception as e:
                    logger.error(f"Error disabling {install_id}: {e}")
                    error_count += 1

            log_activity('bulk_disable', 'installed_integrations', None,
                        details={'success_count': success_count, 'error_count': error_count})

            messagebox.showinfo("Bulk Disable Complete",
                              f"Successfully disabled: {success_count}\nErrors: {error_count}")
            self.load_installed()

        except Exception as e:
            logger.error(f"Error in bulk disable: {e}")
            messagebox.showerror(_t("common.error"), f"Bulk disable failed: {e}")

    def bulk_sync_integrations(self):
        """Trigger sync for all selected/enabled integrations"""
        try:
            selected = self.installed_tree.selection()
            if not selected:
                # If none selected, sync all enabled
                if not messagebox.askyesno("Bulk Sync",
                                          "No integrations selected. Sync all enabled integrations?"):
                    return

                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT install_id FROM installed_integrations
                        WHERE is_enabled = 1 AND status = 'active'
                    ''')
                    install_ids = [row[0] for row in cursor.fetchall()]
            else:
                install_ids = [self.installed_tree.item(item)['values'][0] for item in selected]

            if not install_ids:
                messagebox.showinfo(_t("common.info"), "No integrations to sync")
                return

            success_count = 0
            error_count = 0

            for install_id in install_ids:
                try:
                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO integration_sync_logs
                            (install_id, sync_status, records_synced)
                            VALUES (?, 'success', ?)
                        ''', (install_id, 50))  # Simulated sync

                        cursor.execute('''
                            UPDATE installed_integrations
                            SET last_sync_date = ?
                            WHERE install_id = ?
                        ''', (datetime.now().isoformat(), install_id))
                    success_count += 1
                except Exception as e:
                    logger.error(f"Error syncing {install_id}: {e}")
                    error_count += 1

            log_activity('bulk_sync', 'installed_integrations', None,
                        details={'success_count': success_count, 'error_count': error_count})

            messagebox.showinfo("Bulk Sync Complete",
                              f"Successfully synced: {success_count}\nErrors: {error_count}")
            self.load_installed()
            self.load_sync_logs()

        except Exception as e:
            logger.error(f"Error in bulk sync: {e}")
            messagebox.showerror(_t("common.error"), f"Bulk sync failed: {e}")

    def bulk_update_credentials(self):
        """Update endpoint URLs for multiple credentials at once"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Bulk Update Credential Endpoints")
            dialog.geometry("600x400")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text="Bulk Update Endpoint URLs",
                     style='Title.TLabel').pack(pady=10)

            ttk.Label(dialog, text="Old URL Pattern (will be replaced):").pack(anchor='w', padx=10)
            old_url_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=old_url_var, width=60).pack(padx=10, pady=5)

            ttk.Label(dialog, text="New URL Pattern:").pack(anchor='w', padx=10)
            new_url_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=new_url_var, width=60).pack(padx=10, pady=5)

            # Preview frame
            preview_frame = ttk.LabelFrame(dialog, text=_t("integration_marketplace.mappings.preview"), padding=10)
            preview_frame.pack(fill='both', expand=True, padx=10, pady=10)

            preview_text = scrolledtext.ScrolledText(preview_frame, height=10)
            preview_text.pack(fill='both', expand=True)

            def preview_changes():
                old_pattern = old_url_var.get().strip()
                new_pattern = new_url_var.get().strip()

                if not old_pattern:
                    messagebox.showwarning(_t("common.warning"), "Please enter old URL pattern")
                    return

                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT credential_id, endpoint_url
                        FROM integration_credentials
                        WHERE endpoint_url LIKE ?
                    ''', (f'%{old_pattern}%',))
                    credentials = cursor.fetchall()

                preview_text.delete('1.0', 'end')
                if not credentials:
                    preview_text.insert('1.0', "No matching credentials found")
                else:
                    for cred in credentials:
                        old_url = cred[1] or ''
                        new_url = old_url.replace(old_pattern, new_pattern)
                        preview_text.insert('end', f"ID {cred[0]}:\n  Old: {old_url}\n  New: {new_url}\n\n")

            def apply_changes():
                old_pattern = old_url_var.get().strip()
                new_pattern = new_url_var.get().strip()

                if not old_pattern:
                    messagebox.showwarning(_t("common.warning"), "Please enter old URL pattern")
                    return

                if not messagebox.askyesno(_t("common.confirm"), "Apply URL changes to all matching credentials?"):
                    return

                try:
                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE integration_credentials
                            SET endpoint_url = REPLACE(endpoint_url, ?, ?)
                            WHERE endpoint_url LIKE ?
                        ''', (old_pattern, new_pattern, f'%{old_pattern}%'))
                        updated_count = cursor.rowcount

                    log_activity('bulk_update', 'integration_credentials', None,
                                details={'old_pattern': old_pattern, 'new_pattern': new_pattern,
                                        'updated_count': updated_count})

                    messagebox.showinfo(_t("common.success"), f"Updated {updated_count} credential(s)")
                    dialog.destroy()
                    self.load_credentials()

                except Exception as e:
                    logger.error(f"Error updating credentials: {e}")
                    messagebox.showerror(_t("common.error"), f"Failed to update: {e}")

            button_frame = ttk.Frame(dialog)
            button_frame.pack(pady=10)

            ttk.Button(button_frame, text=_t("integration_marketplace.mappings.preview"), command=preview_changes).pack(side='left', padx=5)
            ttk.Button(button_frame, text=_t("common.apply"), command=apply_changes,
                      style='Accent.TButton').pack(side='left', padx=5)
            ttk.Button(button_frame, text=_t("common.cancel"), command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            logger.error(f"Error opening bulk update dialog: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to open dialog: {e}")
