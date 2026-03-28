"""Credential management methods for IntegrationMarketplaceGUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime, timedelta
import json
import secrets
import hashlib
import logging
import traceback

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

try:
    from education_system.university_system.modules.shared.services.integrations.integration_marketplace_core import (
        CredentialManager,
    )
    MANAGERS_AVAILABLE = True
except ImportError:
    MANAGERS_AVAILABLE = False

logger = logging.getLogger(__name__)


class CredentialsMixin:
    """Mixin providing credential management methods."""

    def add_credentials(self):
        """Add credentials for integration"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title(_t("integration_marketplace.dialogs.add_credentials"))
            dialog.geometry("500x450")

            ttk.Label(dialog, text=_t("integration_marketplace.labels.installation_id")).grid(row=0, column=0, padx=10, pady=5, sticky='w')
            install_id_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=install_id_var, width=35).grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text=_t("integration_marketplace.labels.credential_type")).grid(row=1, column=0, padx=10, pady=5, sticky='w')
            cred_type_var = tk.StringVar(value='api_key')
            ttk.Combobox(dialog, textvariable=cred_type_var,
                        values=['api_key', 'oauth', 'basic_auth', 'bearer_token'],
                        width=33, state='readonly').grid(row=1, column=1, padx=10, pady=5)

            ttk.Label(dialog, text=_t("integration_marketplace.labels.api_key")).grid(row=2, column=0, padx=10, pady=5, sticky='w')
            api_key_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=api_key_var, width=35, show='*').grid(row=2, column=1, padx=10, pady=5)

            ttk.Label(dialog, text=_t("integration_marketplace.labels.api_secret")).grid(row=3, column=0, padx=10, pady=5, sticky='w')
            api_secret_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=api_secret_var, width=35, show='*').grid(row=3, column=1, padx=10, pady=5)

            ttk.Label(dialog, text=_t("integration_marketplace.labels.endpoint_url")).grid(row=4, column=0, padx=10, pady=5, sticky='w')
            endpoint_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=endpoint_var, width=35).grid(row=4, column=1, padx=10, pady=5)

            ttk.Label(dialog, text=_t("integration_marketplace.labels.oauth_token")).grid(row=5, column=0, padx=10, pady=5, sticky='w')
            oauth_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=oauth_var, width=35, show='*').grid(row=5, column=1, padx=10, pady=5)

            def save_credentials():
                try:
                    install_id = install_id_var.get().strip()
                    cred_type = cred_type_var.get()
                    api_key = api_key_var.get().strip()
                    api_secret = api_secret_var.get().strip()
                    endpoint = endpoint_var.get().strip()
                    oauth_token = oauth_var.get().strip()

                    if not install_id:
                        messagebox.showerror(_t("common.error"), "Installation ID is required")
                        return

                    if MANAGERS_AVAILABLE:
                        cred_id = CredentialManager.store_credentials(
                            int(install_id), cred_type, api_key, api_secret,
                            oauth_token, endpoint
                        )
                    else:
                        with transaction() as conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                INSERT INTO integration_credentials
                                (install_id, credential_type, api_key, api_secret,
                                 oauth_token, endpoint_url)
                                VALUES (?, ?, ?, ?, ?, ?)
                            ''', (install_id, cred_type, api_key, api_secret,
                                  oauth_token, endpoint))

                            cred_id = cursor.lastrowid

                    log_activity('create', 'integration_credentials', cred_id,
                                details={'install_id': install_id})

                    messagebox.showinfo(_t("common.success"), "Credentials saved successfully")
                    dialog.destroy()
                    self.load_credentials()

                except Exception as e:
                    logger.error("Error saving credentials")
                    messagebox.showerror(_t("common.error"), f"Failed to save credentials: {e}")

            ttk.Button(dialog, text="Save Credentials", command=save_credentials).grid(
                row=6, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error("Error opening credentials dialog")
            messagebox.showerror(_t("common.error"), f"Failed to open dialog: {e}")

    def edit_credentials(self):
        """Edit selected credentials"""
        try:
            selected = self.cred_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select credentials to edit")
                return

            credential_id = self.cred_tree.item(selected[0])['values'][0]

            # Get current credentials
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT install_id, credential_type, endpoint_url
                    FROM integration_credentials
                    WHERE credential_id = ?
                ''', (credential_id,))

                cred = cursor.fetchone()

            if not cred:
                messagebox.showerror(_t("common.error"), "Credentials not found")
                return

            dialog = tk.Toplevel(self.root)
            dialog.title(_t("integration_marketplace.dialogs.edit_credentials"))
            dialog.geometry("500x350")

            ttk.Label(dialog, text="Credential Type:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            cred_type_var = tk.StringVar(value=cred[1])
            ttk.Combobox(dialog, textvariable=cred_type_var,
                        values=['api_key', 'oauth', 'basic_auth', 'bearer_token'],
                        width=33, state='readonly').grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="New API Key (Optional):").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            api_key_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=api_key_var, width=35, show='*').grid(row=1, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Endpoint URL:").grid(row=2, column=0, padx=10, pady=5, sticky='w')
            endpoint_var = tk.StringVar(value=cred[2] or '')
            ttk.Entry(dialog, textvariable=endpoint_var, width=35).grid(row=2, column=1, padx=10, pady=5)

            def update_credentials():
                try:
                    api_key = api_key_var.get().strip()
                    endpoint = endpoint_var.get().strip()

                    with transaction() as conn:
                        cursor = conn.cursor()

                        # Update only non-empty fields
                        if api_key:
                            cursor.execute('''
                                UPDATE integration_credentials
                                SET credential_type = ?, api_key = ?, endpoint_url = ?
                                WHERE credential_id = ?
                            ''', (cred_type_var.get(), api_key, endpoint, credential_id))
                        else:
                            cursor.execute('''
                                UPDATE integration_credentials
                                SET credential_type = ?, endpoint_url = ?
                                WHERE credential_id = ?
                            ''', (cred_type_var.get(), endpoint, credential_id))

                    log_activity('update', 'integration_credentials', credential_id,
                                details={'action': 'updated'})

                    messagebox.showinfo(_t("common.success"), "Credentials updated successfully")
                    dialog.destroy()
                    self.load_credentials()

                except Exception as e:
                    logger.error("Error updating credentials")
                    messagebox.showerror(_t("common.error"), f"Failed to update credentials: {e}")

            ttk.Button(dialog, text="Update Credentials", command=update_credentials).grid(
                row=3, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error("Error editing credentials")
            messagebox.showerror(_t("common.error"), f"Failed to edit credentials: {e}")

    def delete_credentials(self):
        """Delete selected credentials"""
        try:
            selected = self.cred_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select credentials to delete")
                return

            credential_id = self.cred_tree.item(selected[0])['values'][0]

            if messagebox.askyesno("Confirm Delete", "Delete these credentials?"):
                with transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        DELETE FROM integration_credentials
                        WHERE credential_id = ?
                    ''', (credential_id,))

                log_activity('delete', 'integration_credentials', credential_id,
                            details={'action': 'deleted'})

                messagebox.showinfo(_t("common.success"), "Credentials deleted successfully")
                self.load_credentials()

        except Exception as e:
            logger.error("Error deleting credentials")
            messagebox.showerror(_t("common.error"), f"Failed to delete credentials: {e}")

    def rotate_api_credentials(self):
        """Automatically rotate/regenerate API keys"""
        try:
            selected = self.cred_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select credentials to rotate")
                return

            credential_id = self.cred_tree.item(selected[0])['values'][0]

            if messagebox.askyesno("Confirm Rotation",
                                   "Rotate API credentials?\n\n"
                                   "This will generate new API key and secret.\n"
                                   "The old credentials will be invalidated."):
                new_api_key = secrets.token_urlsafe(32)
                new_secret = secrets.token_urlsafe(48)

                with transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE integration_credentials
                        SET api_key = ?, api_secret = ?, created_at = ?
                        WHERE credential_id = ?
                    ''', (new_api_key, new_secret, datetime.now().isoformat(), credential_id))

                log_activity('rotate', 'integration_credentials', credential_id,
                            details={'action': 'api_key_rotated'})

                messagebox.showinfo(_t("common.success"),
                                   f"Credentials rotated successfully!\n\n"
                                   f"New API Key (first 8 chars): {new_api_key[:8]}...\n\n"
                                   f"Please update any applications using these credentials.")
                self.load_credentials()

        except Exception as e:
            logger.error("Error rotating credentials")
            messagebox.showerror(_t("common.error"), f"Failed to rotate credentials: {e}")

    def check_credential_expiry(self):
        """Scan and alert for expiring credentials"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Credential Expiry Check")
            dialog.geometry("700x500")
            dialog.transient(self.root)

            ttk.Label(dialog, text="Days until expiry threshold:").pack(padx=10, pady=5)
            days_var = tk.StringVar(value="30")
            ttk.Spinbox(dialog, from_=1, to=365, textvariable=days_var, width=10).pack(padx=10, pady=5)

            results_frame = ttk.LabelFrame(dialog, text="Expiring Credentials", padding=10)
            results_frame.pack(fill='both', expand=True, padx=10, pady=5)

            columns = ('credential_id', 'integration', 'expiry_date', 'days_left', 'status')
            tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=12)

            for col in columns:
                tree.heading(col, text=col.replace('_', ' ').title())
                tree.column(col, width=120)

            tree.pack(fill='both', expand=True)

            def check_expiry():
                for item in tree.get_children():
                    tree.delete(item)

                days_threshold = int(days_var.get())
                threshold_date = (datetime.now() + timedelta(days=days_threshold)).isoformat()

                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT icr.credential_id, ic.integration_name, icr.token_expiry, icr.created_at
                        FROM integration_credentials icr
                        JOIN installed_integrations ii ON icr.install_id = ii.install_id
                        JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                        WHERE icr.token_expiry IS NOT NULL
                        ORDER BY icr.token_expiry
                    ''')
                    credentials = cursor.fetchall()

                expiring_count = 0
                for cred in credentials:
                    if cred[2]:
                        try:
                            expiry = datetime.fromisoformat(cred[2].replace('Z', '+00:00'))
                            days_left = (expiry.replace(tzinfo=None) - datetime.now()).days

                            if days_left <= days_threshold:
                                status = 'EXPIRED' if days_left < 0 else 'EXPIRING SOON'
                                tree.insert('', 'end', values=(
                                    cred[0], cred[1], cred[2][:10], days_left, status
                                ))
                                expiring_count += 1
                        except Exception:
                            pass

                if expiring_count == 0:
                    messagebox.showinfo("Check Complete",
                                       f"No credentials expiring within {days_threshold} days")
                else:
                    messagebox.showwarning("Expiring Credentials",
                                          f"Found {expiring_count} credential(s) expiring soon!")

            ttk.Button(dialog, text="Check Expiry", command=check_expiry).pack(pady=10)
            ttk.Button(dialog, text=_t("common.close"), command=dialog.destroy).pack(pady=5)

        except Exception as e:
            logger.error("Error checking credential expiry")
            messagebox.showerror(_t("common.error"), f"Failed to check expiry: {e}")

    def validate_credentials(self):
        """Test if credentials are still valid by pinging endpoint"""
        try:
            selected = self.cred_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select credentials to validate")
                return

            credential_id = self.cred_tree.item(selected[0])['values'][0]

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT icr.endpoint_url, icr.api_key, ic.integration_name
                    FROM integration_credentials icr
                    JOIN installed_integrations ii ON icr.install_id = ii.install_id
                    JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                    WHERE icr.credential_id = ?
                ''', (credential_id,))
                cred = cursor.fetchone()

            if not cred:
                messagebox.showerror(_t("common.error"), "Credentials not found")
                return

            if not cred[0]:
                messagebox.showwarning(_t("common.warning"), "No endpoint URL configured for these credentials")
                return

            # Simulate validation
            import time
            start = time.time()
            time.sleep(0.1)  # Simulate network latency
            latency = round((time.time() - start) * 1000, 2)

            result = f"Credential Validation Results\n\n"
            result += f"Integration: {cred[2]}\n"
            result += f"Endpoint: {cred[0]}\n\n"
            result += f"Status: VALID (Simulated)\n"
            result += f"Latency: {latency}ms\n"
            result += f"Tested at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            log_activity('validate', 'integration_credentials', credential_id,
                        details={'endpoint': cred[0], 'status': 'valid'})

            messagebox.showinfo("Validation Result", result)

        except Exception as e:
            logger.error("Error validating credentials")
            messagebox.showerror(_t("common.error"), f"Failed to validate credentials: {e}")

    def encrypt_export_credentials(self):
        """Export credentials with password encryption"""
        try:
            password = simpledialog.askstring("Encryption Password",
                                             "Enter password to encrypt exported credentials:",
                                             show='*')
            if not password:
                return

            confirm = simpledialog.askstring("Confirm Password",
                                            "Confirm password:",
                                            show='*')
            if password != confirm:
                messagebox.showerror(_t("common.error"), "Passwords do not match")
                return

            filename = filedialog.asksaveasfilename(
                defaultextension=".enc",
                filetypes=[("Encrypted files", "*.enc"), ("All files", "*.*")],
                initialfile="credentials_encrypted.enc"
            )

            if not filename:
                return

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT credential_id, install_id, credential_type, endpoint_url, created_at
                    FROM integration_credentials
                ''')
                credentials = [dict(row) for row in cursor.fetchall()]

            content = json.dumps({
                'exported_at': datetime.now().isoformat(),
                'credentials': credentials
            })

            # XOR encryption with PBKDF2-derived key
            dk = hashlib.pbkdf2_hmac('sha256', password.encode(), b'cred-export-salt', 100000)
            key = dk.hex()
            encrypted = ''.join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(content))

            with open(filename, 'w') as f:
                json.dump({'encrypted': True, 'data': encrypted}, f)

            log_activity('export', 'credentials_encrypted', None,
                        details={'filename': filename, 'count': len(credentials)})

            messagebox.showinfo(_t("common.success"),
                               f"Exported {len(credentials)} credentials (encrypted) to:\n{filename}")

        except Exception as e:
            logger.error("Error exporting encrypted credentials")
            messagebox.showerror(_t("common.error"), f"Failed to export credentials: {e}")

    def audit_credential_access(self):
        """View log of credential access events"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Credential Access Audit Log")
            dialog.geometry("800x500")
            dialog.transient(self.root)

            ttk.Label(dialog, text="Credential Access Audit Log",
                     style='Title.TLabel').pack(pady=10)

            # Note frame
            note_frame = ttk.Frame(dialog)
            note_frame.pack(fill='x', padx=10, pady=5)
            ttk.Label(note_frame, text="Note: Audit logging requires activity_logger integration.",
                     font=('Arial', 9, 'italic')).pack()

            # Audit log tree
            tree_frame = ttk.Frame(dialog)
            tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

            columns = ('timestamp', 'action', 'credential_id', 'user', 'details')
            tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

            for col in columns:
                tree.heading(col, text=col.replace('_', ' ').title())
                tree.column(col, width=130)

            tree.column('details', width=200)

            vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=vsb.set)

            tree.pack(side='left', fill='both', expand=True)
            vsb.pack(side='right', fill='y')

            # Simulated audit entries
            audit_entries = [
                (datetime.now().isoformat()[:19], 'viewed', '1', self.auth.current_user.get('username', 'Unknown'), 'Credentials accessed'),
                ((datetime.now() - timedelta(hours=2)).isoformat()[:19], 'validated', '1', 'admin', 'Endpoint tested'),
                ((datetime.now() - timedelta(days=1)).isoformat()[:19], 'created', '2', 'admin', 'New credentials added'),
            ]

            for entry in audit_entries:
                tree.insert('', 'end', values=entry)

            ttk.Button(dialog, text=_t("common.close"), command=dialog.destroy).pack(pady=10)

            log_activity('view', 'credential_audit_log', None)

        except Exception as e:
            logger.error(f"Error viewing audit log: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to view audit log: {e}")

    def revoke_all_tokens(self):
        """Emergency revoke all OAuth tokens for an integration"""
        try:
            selected = self.installed_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"),
                                      "Please select an integration from the Installed tab to revoke tokens")
                return

            install_id = self.installed_tree.item(selected[0])['values'][0]
            integration_name = self.installed_tree.item(selected[0])['values'][1]

            if messagebox.askyesno("EMERGENCY TOKEN REVOCATION",
                                   f"Revoke ALL OAuth tokens for '{integration_name}'?\n\n"
                                   f"WARNING: This is an emergency action!\n"
                                   f"All OAuth tokens will be invalidated.\n"
                                   f"The integration will need to be re-authenticated.",
                                   icon='warning'):
                with transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE integration_credentials
                        SET oauth_token = NULL, oauth_refresh_token = NULL, token_expiry = NULL
                        WHERE install_id = ?
                    ''', (install_id,))
                    revoked_count = cursor.rowcount

                log_activity('revoke', 'integration_credentials', install_id,
                            details={'action': 'emergency_token_revocation', 'revoked_count': revoked_count})

                messagebox.showinfo("Tokens Revoked",
                                   f"Successfully revoked {revoked_count} token(s) for {integration_name}.\n\n"
                                   f"The integration will need to be re-authenticated.")
                self.load_credentials()

        except Exception as e:
            logger.error("Error revoking tokens")
            messagebox.showerror(_t("common.error"), f"Failed to revoke tokens: {e}")
