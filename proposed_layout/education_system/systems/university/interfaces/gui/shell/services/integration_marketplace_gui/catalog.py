"""Catalog action methods for IntegrationMarketplaceGUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
import json
import logging
import traceback

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.infrastructure.i18n import get_text as _t

try:
    from education_system.systems.university.services.integrations.integration_marketplace_core import (
        IntegrationCatalogManager,
    )
    MANAGERS_AVAILABLE = True
except ImportError:
    MANAGERS_AVAILABLE = False

logger = logging.getLogger(__name__)


class CatalogMixin:
    """Mixin providing catalog action methods."""

    def on_catalog_select(self, event):
        """Handle catalog tree selection"""
        try:
            selected = self.catalog_tree.selection()
            if not selected:
                return

            integration_id = self.catalog_tree.item(selected[0])['values'][0]

            # Get integration details
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT description FROM integration_catalog
                    WHERE integration_id = ?
                ''', (integration_id,))

                result = cursor.fetchone()
                if result:
                    description = result[0] or "No description available."
                    self.catalog_description.delete('1.0', 'end')
                    self.catalog_description.insert('1.0', description)

        except Exception as e:
            logger.error(f"Error loading integration details: {e}")

    def add_integration(self):
        """Add new integration to catalog"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title(_t("integration_marketplace.dialogs.add_integration"))
            dialog.geometry("500x500")
            dialog.transient(self.root)  # Make dialog transient to parent
            dialog.grab_set()  # Make dialog modal

            # Form fields
            ttk.Label(dialog, text=_t("integration_marketplace.labels.integration_name")).grid(row=0, column=0, padx=10, pady=5, sticky='w')
            name_var = tk.StringVar()
            name_entry = ttk.Entry(dialog, textvariable=name_var, width=35)
            name_entry.grid(row=0, column=1, padx=10, pady=5)
            name_entry.focus_set()  # Set initial focus

            ttk.Label(dialog, text=_t("integration_marketplace.labels.provider_name")).grid(row=1, column=0, padx=10, pady=5, sticky='w')
            provider_var = tk.StringVar()
            provider_entry = ttk.Entry(dialog, textvariable=provider_var, width=35)
            provider_entry.grid(row=1, column=1, padx=10, pady=5)

            ttk.Label(dialog, text=_t("integration_marketplace.labels.integration_type")).grid(row=2, column=0, padx=10, pady=5, sticky='w')
            type_var = tk.StringVar(value='API')
            ttk.Combobox(dialog, textvariable=type_var,
                        values=['API', 'OAuth', 'SAML', 'Database', 'Webhook'],
                        width=33, state='readonly').grid(row=2, column=1, padx=10, pady=5)

            ttk.Label(dialog, text=_t("integration_marketplace.labels.category")).grid(row=3, column=0, padx=10, pady=5, sticky='w')
            category_var = tk.StringVar(value='LMS')
            ttk.Combobox(dialog, textvariable=category_var,
                        values=['LMS', 'SIS', 'CRM', 'Analytics', 'Communication', 'Storage'],
                        width=33, state='readonly').grid(row=3, column=1, padx=10, pady=5)

            ttk.Label(dialog, text=_t("integration_marketplace.labels.version")).grid(row=4, column=0, padx=10, pady=5, sticky='w')
            version_var = tk.StringVar(value='1.0.0')
            ttk.Entry(dialog, textvariable=version_var, width=35).grid(row=4, column=1, padx=10, pady=5)

            ttk.Label(dialog, text=_t("integration_marketplace.labels.description")).grid(row=5, column=0, padx=10, pady=5, sticky='nw')
            description_text = scrolledtext.ScrolledText(dialog, width=35, height=6)
            description_text.grid(row=5, column=1, padx=10, pady=5)

            ttk.Label(dialog, text=_t("integration_marketplace.columns.is_official")).grid(row=6, column=0, padx=10, pady=5, sticky='w')
            is_official_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(dialog, variable=is_official_var).grid(row=6, column=1, padx=10, pady=5, sticky='w')

            def save_integration():
                try:
                    integration_name = name_var.get().strip()
                    provider_name = provider_var.get().strip()
                    integration_type = type_var.get()
                    category = category_var.get()
                    version = version_var.get().strip()
                    description = description_text.get('1.0', 'end-1c').strip()
                    is_official = int(is_official_var.get())

                    # Enhanced validation with specific error messages
                    if not integration_name:
                        messagebox.showerror(_t("common.error"), _t("integration_marketplace.messages.fill_required_fields"))
                        name_entry.focus_set()
                        return

                    if not provider_name:
                        messagebox.showerror(_t("common.error"), _t("integration_marketplace.messages.fill_required_fields"))
                        provider_entry.focus_set()
                        return

                    # Log for debugging
                    logger.info(f"Adding integration: name='{integration_name}', provider='{provider_name}', type='{integration_type}'")

                    if MANAGERS_AVAILABLE:
                        integration_id = IntegrationCatalogManager.add_integration(
                            integration_name, provider_name, integration_type,
                            category, description, version, bool(is_official)
                        )
                    else:
                        with transaction() as conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                INSERT INTO integration_catalog
                                (integration_name, provider_name, integration_type, category,
                                 description, version, is_official, is_active)
                                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                            ''', (integration_name, provider_name, integration_type, category,
                                  description, version, is_official))

                            integration_id = cursor.lastrowid

                    log_activity('create', 'integration_catalog', integration_id,
                                details={'integration_name': integration_name})

                    messagebox.showinfo(_t("common.success"), f"{_t('integration_marketplace.messages.integration_added')}\nIntegration ID: {integration_id}")
                    dialog.destroy()
                    self.load_catalog()

                except Exception as e:
                    logger.error(f"Error adding integration: {e}\n{traceback.format_exc()}")
                    messagebox.showerror(_t("common.error"), f"Failed to add integration: {e}")

            ttk.Button(dialog, text=_t("integration_marketplace.catalog.add_integration"), command=save_integration).grid(
                row=7, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error(f"Error opening add integration dialog: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to open dialog: {e}")

    def view_integration_details(self):
        """View detailed integration information"""
        try:
            selected = self.catalog_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select an integration to view details")
                return

            integration_id = self.catalog_tree.item(selected[0])['values'][0]

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT integration_name, provider_name, integration_type, category,
                           description, version, rating, install_count, pricing_model,
                           documentation_url
                    FROM integration_catalog
                    WHERE integration_id = ?
                ''', (integration_id,))

                integration = cursor.fetchone()

            if not integration:
                messagebox.showerror(_t("common.error"), "Integration not found")
                return

            details = "Integration Details\n\n"
            details += f"Name: {integration[0]}\n"
            details += f"Provider: {integration[1]}\n"
            details += f"Type: {integration[2]}\n"
            details += f"Category: {integration[3]}\n"
            details += f"Version: {integration[5]}\n"
            details += f"Rating: {integration[6] or 'Not rated'}\n"
            details += f"Installs: {integration[7] or 0}\n"
            details += f"Pricing: {integration[8] or 'Contact provider'}\n"
            details += f"Documentation: {integration[9] or _t('common.na')}\n\n"
            details += f"Description:\n{integration[4] or 'No description available.'}"

            messagebox.showinfo("Integration Details", details)

        except Exception as e:
            logger.error(f"Error viewing integration details: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to view details: {e}")

    def install_integration(self):
        """Install selected integration"""
        try:
            selected = self.catalog_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select an integration to install")
                return

            values = self.catalog_tree.item(selected[0])['values']
            integration_id = values[0]
            integration_name = values[1]

            if messagebox.askyesno("Confirm Installation",
                                  f"Install '{integration_name}'?\n\nThis will add the integration to your system."):
                try:
                    installed_by = self.auth.current_user.get('username', 'Unknown')

                    if MANAGERS_AVAILABLE:
                        from education_system.systems.university.services.integrations.integration_marketplace_core import InstallationManager
                        install_id = InstallationManager.install_integration(integration_id, installed_by)
                    else:
                        with transaction() as conn:
                            cursor = conn.cursor()

                            # Get version
                            cursor.execute('SELECT version FROM integration_catalog WHERE integration_id = ?',
                                          (integration_id,))
                            version = cursor.fetchone()[0]

                            cursor.execute('''
                                INSERT INTO installed_integrations
                                (integration_id, installed_by, version_installed, status, is_enabled)
                                VALUES (?, ?, ?, 'active', 1)
                            ''', (integration_id, installed_by, version))

                            install_id = cursor.lastrowid

                            # Update install count
                            cursor.execute('''
                                UPDATE integration_catalog
                                SET install_count = install_count + 1
                                WHERE integration_id = ?
                            ''', (integration_id,))

                    log_activity('create', 'installed_integration', install_id,
                                details={'integration_id': integration_id, 'integration_name': integration_name})

                    # Send notification
                    try:
                        from education_system.systems.university.infrastructure.email.email_service import send_email
                        send_email(
                            recipient_email=f"{installed_by}@university.edu",
                            subject=f"Integration Installed: {integration_name}",
                            body=f"The integration '{integration_name}' has been successfully installed.\n\n"
                                 f"Installation ID: {install_id}\n"
                                 f"Installed by: {installed_by}\n"
                                 f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                                 f"You can now configure and use this integration."
                        )
                    except (ImportError, Exception) as e:
                        logger.warning(f"Failed to send notification: {e}")

                    messagebox.showinfo(_t("common.success"),
                                      f"Integration installed successfully!\n\n"
                                      f"Installation ID: {install_id}\n\n"
                                      f"Go to the 'Installed' tab to configure it.")

                    self.load_catalog()
                    self.load_installed()

                except Exception as e:
                    logger.error(f"Error installing integration: {e}\n{traceback.format_exc()}")
                    messagebox.showerror(_t("common.error"), f"Failed to install integration: {e}")

        except Exception as e:
            logger.error(f"Error in install_integration: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to process installation: {e}")
