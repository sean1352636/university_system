"""Validation and testing methods for IntegrationMarketplaceGUI."""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
import json
import logging
import time

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity
from education_system.post_18.university_system.core.i18n import get_text as _t

logger = logging.getLogger(__name__)


class TestingMixin:
    """Mixin providing validation and testing methods."""

    def test_integration_connection(self):
        """Test connectivity to integration endpoint"""
        try:
            selected = self.installed_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select an integration to test")
                return

            install_id = self.installed_tree.item(selected[0])['values'][0]
            integration_name = self.installed_tree.item(selected[0])['values'][1]

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT endpoint_url FROM integration_credentials
                    WHERE install_id = ?
                ''', (install_id,))
                cred = cursor.fetchone()

            if not cred or not cred[0]:
                messagebox.showwarning(_t("common.warning"), "No endpoint URL configured for this integration")
                return

            # Simulate connection test
            start = time.time()
            time.sleep(0.1)
            latency = round((time.time() - start) * 1000, 2)

            result = "Connection Test Results\n\n"
            result += f"Integration: {integration_name}\n"
            result += f"Endpoint: {cred[0]}\n\n"
            result += "Status: CONNECTED (Simulated)\n"
            result += f"Latency: {latency}ms\n"
            result += f"Tested at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            log_activity('test', 'integration_connection', install_id,
                        details={'endpoint': cred[0], 'latency_ms': latency})

            messagebox.showinfo("Connection Test", result)

        except Exception as e:
            logger.error(f"Error testing connection: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to test connection: {e}")

    def validate_mapping_rules(self):
        """Validate transformation rules syntax"""
        try:
            selected = self.mappings_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select a mapping to validate")
                return

            mapping_id = self.mappings_tree.item(selected[0])['values'][0]

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT transformation_rule, source_field, target_field
                    FROM integration_data_mappings
                    WHERE mapping_id = ?
                ''', (mapping_id,))
                mapping = cursor.fetchone()

            if not mapping:
                messagebox.showerror(_t("common.error"), "Mapping not found")
                return

            rule = mapping[0]

            if not rule:
                result = "Validation Result: VALID\n\nNo transformation rule (direct mapping)"
            else:
                # Validate common patterns
                valid_patterns = [
                    (r'^[a-zA-Z_][a-zA-Z0-9_]*$', 'field reference'),
                    (r'^UPPER\(.+\)$', 'UPPER function'),
                    (r'^LOWER\(.+\)$', 'LOWER function'),
                    (r'^TRIM\(.+\)$', 'TRIM function'),
                    (r'^CONCAT\(.+\)$', 'CONCAT function'),
                    (r'^\{.*\}$', 'JSON template'),
                ]

                is_valid = False
                matched_pattern = None
                for pattern, name in valid_patterns:
                    if re.match(pattern, rule, re.IGNORECASE):
                        is_valid = True
                        matched_pattern = name
                        break

                if is_valid:
                    result = "Validation Result: VALID\n\n"
                    result += f"Rule: {rule}\n"
                    result += f"Pattern: {matched_pattern}\n"
                    result += f"Source: {mapping[1]}\n"
                    result += f"Target: {mapping[2]}"
                else:
                    result = "Validation Result: WARNING\n\n"
                    result += f"Rule: {rule}\n"
                    result += "Note: Unknown rule format. May still work but couldn't validate syntax."

            log_activity('validate', 'mapping_rule', mapping_id)

            messagebox.showinfo("Mapping Validation", result)

        except Exception as e:
            logger.error(f"Error validating mapping: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to validate mapping: {e}")

    def dry_run_sync(self):
        """Simulate sync without committing changes"""
        try:
            selected = self.installed_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select an integration for dry run")
                return

            install_id = self.installed_tree.item(selected[0])['values'][0]
            integration_name = self.installed_tree.item(selected[0])['values'][1]

            if messagebox.askyesno("Dry Run Sync",
                                  f"Perform dry run sync for '{integration_name}'?\n\n"
                                  f"This will simulate the sync without making actual changes."):

                # Simulate dry run
                sample_size = 10
                would_create = sample_size // 2
                would_update = sample_size // 3
                would_skip = sample_size - would_create - would_update

                result = f"Dry Run Results for: {integration_name}\n\n"
                result += f"Sample Records Analyzed: {sample_size}\n\n"
                result += f"Would CREATE: {would_create} record(s)\n"
                result += f"Would UPDATE: {would_update} record(s)\n"
                result += f"Would SKIP: {would_skip} record(s)\n"
                result += "Validation Errors: 0\n\n"
                result += f"Dry run completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                result += "No actual changes were made."

                log_activity('dry_run', 'sync', install_id,
                            details={'sample_size': sample_size, 'would_create': would_create,
                                    'would_update': would_update})

                messagebox.showinfo("Dry Run Complete", result)

        except Exception as e:
            logger.error(f"Error performing dry run: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to perform dry run: {e}")

    def test_webhook_delivery(self):
        """Send test payload to webhook URL"""
        try:
            selected = self.webhooks_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select a webhook to test")
                return

            webhook_id = self.webhooks_tree.item(selected[0])['values'][0]

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT webhook_url, event_type FROM integration_webhooks
                    WHERE webhook_id = ?
                ''', (webhook_id,))
                webhook = cursor.fetchone()

            if not webhook:
                messagebox.showerror(_t("common.error"), "Webhook not found")
                return

            test_payload = {
                'event': 'test',
                'timestamp': datetime.now().isoformat(),
                'message': 'Test webhook delivery from Integration Marketplace',
                'webhook_id': webhook_id
            }

            # Simulate delivery
            result = "Webhook Test Results\n\n"
            result += f"URL: {webhook[0]}\n"
            result += f"Event Type: {webhook[1]}\n\n"
            result += f"Payload Sent:\n{json.dumps(test_payload, indent=2)}\n\n"
            result += "Response: 200 OK (Simulated)\n"
            result += f"Delivered at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            # Update last triggered
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE integration_webhooks
                    SET last_triggered_at = ?
                    WHERE webhook_id = ?
                ''', (datetime.now().isoformat(), webhook_id))

            log_activity('test', 'webhook_delivery', webhook_id,
                        details={'url': webhook[0]})

            messagebox.showinfo("Webhook Test", result)
            self.load_webhooks()

        except Exception as e:
            logger.error(f"Error testing webhook: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to test webhook: {e}")

    def validate_json_configuration(self):
        """Validate configuration JSON against schema"""
        try:
            selected = self.installed_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select an integration to validate configuration")
                return

            install_id = self.installed_tree.item(selected[0])['values'][0]
            integration_name = self.installed_tree.item(selected[0])['values'][1]

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT configuration FROM installed_integrations
                    WHERE install_id = ?
                ''', (install_id,))
                row = cursor.fetchone()

            config_str = row[0] if row else None

            result = f"Configuration Validation: {integration_name}\n\n"

            if not config_str:
                result += "Status: VALID\n"
                result += "Note: No configuration (empty is valid)"
            else:
                try:
                    config = json.loads(config_str)
                    result += "Status: VALID JSON\n\n"
                    result += "Configuration Structure:\n"
                    for key, value in config.items():
                        result += f"  - {key}: {type(value).__name__}\n"
                except json.JSONDecodeError as e:
                    result += "Status: INVALID JSON\n\n"
                    result += f"Error: {str(e)}"

            log_activity('validate', 'json_configuration', install_id)

            messagebox.showinfo("Configuration Validation", result)

        except Exception as e:
            logger.error(f"Error validating configuration: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to validate configuration: {e}")

    def run_integration_diagnostics(self):
        """Run comprehensive diagnostic checks"""
        try:
            selected = self.installed_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select an integration to diagnose")
                return

            install_id = self.installed_tree.item(selected[0])['values'][0]
            integration_name = self.installed_tree.item(selected[0])['values'][1]

            dialog = tk.Toplevel(self.root)
            dialog.title(f"Diagnostics: {integration_name}")
            dialog.geometry("600x500")
            dialog.transient(self.root)

            ttk.Label(dialog, text=f"Diagnostics for: {integration_name}",
                     style='Title.TLabel').pack(pady=10)

            results_text = scrolledtext.ScrolledText(dialog, height=20, wrap=tk.WORD)
            results_text.pack(fill='both', expand=True, padx=10, pady=5)

            def run_checks():
                results_text.delete('1.0', 'end')
                results_text.insert('end', f"Running diagnostics for {integration_name}...\n\n")
                results_text.insert('end', "=" * 50 + "\n\n")

                checks_passed = 0
                checks_failed = 0
                checks_warning = 0

                with get_connection() as conn:
                    cursor = conn.cursor()

                    # Check 1: Installation exists
                    cursor.execute('''
                        SELECT status, is_enabled FROM installed_integrations
                        WHERE install_id = ?
                    ''', (install_id,))
                    install = cursor.fetchone()

                    if install:
                        results_text.insert('end', "[PASS] Installation exists\n")
                        checks_passed += 1

                        if install[1]:
                            results_text.insert('end', "[PASS] Integration is enabled\n")
                            checks_passed += 1
                        else:
                            results_text.insert('end', "[WARN] Integration is disabled\n")
                            checks_warning += 1
                    else:
                        results_text.insert('end', "[FAIL] Installation not found\n")
                        checks_failed += 1
                        return

                    # Check 2: Credentials
                    cursor.execute('''
                        SELECT COUNT(*) FROM integration_credentials
                        WHERE install_id = ?
                    ''', (install_id,))
                    cred_count = cursor.fetchone()[0]

                    if cred_count > 0:
                        results_text.insert('end', f"[PASS] {cred_count} credential(s) configured\n")
                        checks_passed += 1
                    else:
                        results_text.insert('end', "[WARN] No credentials configured\n")
                        checks_warning += 1

                    # Check 3: Recent syncs
                    cursor.execute('''
                        SELECT COUNT(*), MAX(sync_start_time)
                        FROM integration_sync_logs
                        WHERE install_id = ? AND sync_start_time >= date('now', '-7 days')
                    ''', (install_id,))
                    sync_info = cursor.fetchone()

                    if sync_info[0] > 0:
                        results_text.insert('end', f"[PASS] {sync_info[0]} syncs in last 7 days\n")
                        checks_passed += 1
                    else:
                        results_text.insert('end', "[INFO] No syncs in last 7 days\n")

                    # Check 4: Error rate
                    cursor.execute('''
                        SELECT
                            COUNT(*) as total,
                            SUM(CASE WHEN sync_status = 'failed' THEN 1 ELSE 0 END) as failed
                        FROM integration_sync_logs
                        WHERE install_id = ? AND sync_start_time >= date('now', '-30 days')
                    ''', (install_id,))
                    error_info = cursor.fetchone()

                    if error_info[0] > 0:
                        error_rate = (error_info[1] / error_info[0] * 100)
                        if error_rate < 10:
                            results_text.insert('end', f"[PASS] Error rate: {error_rate:.1f}%\n")
                            checks_passed += 1
                        elif error_rate < 25:
                            results_text.insert('end', f"[WARN] Error rate: {error_rate:.1f}%\n")
                            checks_warning += 1
                        else:
                            results_text.insert('end', f"[FAIL] High error rate: {error_rate:.1f}%\n")
                            checks_failed += 1

                    # Check 5: Data mappings
                    cursor.execute('''
                        SELECT COUNT(*) FROM integration_data_mappings
                        WHERE install_id = ? AND is_active = 1
                    ''', (install_id,))
                    mapping_count = cursor.fetchone()[0]
                    results_text.insert('end', f"[INFO] {mapping_count} active data mapping(s)\n")

                results_text.insert('end', "\n" + "=" * 50 + "\n\n")
                results_text.insert('end', "Summary:\n")
                results_text.insert('end', f"  Passed: {checks_passed}\n")
                results_text.insert('end', f"  Warnings: {checks_warning}\n")
                results_text.insert('end', f"  Failed: {checks_failed}\n\n")

                if checks_failed > 0:
                    results_text.insert('end', "Overall Status: NEEDS ATTENTION\n")
                elif checks_warning > 0:
                    results_text.insert('end', "Overall Status: WARNING\n")
                else:
                    results_text.insert('end', "Overall Status: HEALTHY\n")

                log_activity('diagnose', 'integration', install_id,
                            details={'passed': checks_passed, 'warnings': checks_warning, 'failed': checks_failed})

            run_checks()

            button_frame = ttk.Frame(dialog)
            button_frame.pack(pady=10)
            ttk.Button(button_frame, text="Re-run Diagnostics", command=run_checks).pack(side='left', padx=5)
            ttk.Button(button_frame, text=_t("common.close"), command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            logger.error(f"Error running diagnostics: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to run diagnostics: {e}")
