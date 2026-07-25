"""Comparison dialog for the data backup GUI.

Provides the ComparisonDialog class for comparing two backup files side by side,
showing differences in tables, records, size, and providing recommendations.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import datetime

from education_system.systems.university.interfaces.gui.shell.database.shared_imports import logger
from education_system.systems.university.interfaces.gui.shell.database.operations.backup_ops import list_available_backups, compare_backups


class ComparisonDialog:
    """Dialog for comparing backups"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Compare Backups")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)

        self.create_widgets()
        self.load_backups()

    def create_widgets(self):
        """Create dialog widgets"""
        # Backup selection
        select_frame = ttk.LabelFrame(self.dialog, text="Select Backups to Compare", padding=10)
        select_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(select_frame, text="First Backup:").grid(row=0, column=0, sticky="w", padx=5)
        self.backup1_var = tk.StringVar()
        self.backup1_combo = ttk.Combobox(select_frame, textvariable=self.backup1_var,
                                         state="readonly", width=40)
        self.backup1_combo.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(select_frame, text="Second Backup:").grid(row=1, column=0, sticky="w", padx=5)
        self.backup2_var = tk.StringVar()
        self.backup2_combo = ttk.Combobox(select_frame, textvariable=self.backup2_var,
                                         state="readonly", width=40)
        self.backup2_combo.grid(row=1, column=1, padx=5, pady=2)

        ttk.Button(select_frame, text="Compare", command=self.compare).grid(row=2, column=1, pady=10)

        # Results
        results_frame = ttk.LabelFrame(self.dialog, text="Comparison Results", padding=10)
        results_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD)
        self.results_text.pack(fill="both", expand=True)

    def load_backups(self):
        """Load available backups"""
        try:
            backups = list_available_backups()
            self.backups = backups

            backup_names = [f"{backup['date_formatted']} - {backup['filename']}"
                           for backup in backups]

            self.backup1_combo['values'] = backup_names
            self.backup2_combo['values'] = backup_names

            if len(backup_names) >= 2:
                self.backup1_combo.current(0)
                self.backup2_combo.current(1)

        except Exception as e:
            self.results_text.insert(tk.END, f"Error loading backups: {e}\n")

    def compare(self):
        """Compare selected backups"""
        if not self.backup1_combo.get() or not self.backup2_combo.get():
            messagebox.showwarning("No Selection", "Please select two backups to compare")
            return

        if self.backup1_combo.current() == self.backup2_combo.current():
            messagebox.showwarning("Same Backup", "Please select two different backups")
            return

        try:
            backup1 = self.backups[self.backup1_combo.current()]
            backup2 = self.backups[self.backup2_combo.current()]

            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, "Comparing backups...\n")
            self.dialog.update()

            differences = compare_backups(backup1['path'], backup2['path'])

            if differences:
                self.results_text.delete(1.0, tk.END)
                self.results_text.insert(tk.END, "BACKUP COMPARISON RESULTS\n")
                self.results_text.insert(tk.END, "=" * 40 + "\n\n")

                self.results_text.insert(tk.END, f"Backup 1: {backup1['filename']}\n")
                self.results_text.insert(tk.END, f"Date 1: {backup1['date_formatted']}\n")
                self.results_text.insert(tk.END, f"Size 1: {backup1['size_formatted']}\n\n")

                self.results_text.insert(tk.END, f"Backup 2: {backup2['filename']}\n")
                self.results_text.insert(tk.END, f"Date 2: {backup2['date_formatted']}\n")
                self.results_text.insert(tk.END, f"Size 2: {backup2['size_formatted']}\n\n")

                # Summary
                total_changes = (len(differences['tables_added']) +
                               len(differences['tables_removed']) +
                               len(differences['tables_modified']))

                if total_changes == 0:
                    self.results_text.insert(tk.END, "\u2705 No differences found - backups are identical\n")
                else:
                    self.results_text.insert(tk.END, f"\ud83d\udcca SUMMARY: {total_changes} table(s) changed\n\n")

                # Tables added
                if differences['tables_added']:
                    self.results_text.insert(tk.END, f"\u2795 TABLES ADDED ({len(differences['tables_added'])}):\n")
                    for table in differences['tables_added']:
                        self.results_text.insert(tk.END, f"  + {table}\n")
                    self.results_text.insert(tk.END, "\n")

                # Tables removed
                if differences['tables_removed']:
                    self.results_text.insert(tk.END, f"\u2796 TABLES REMOVED ({len(differences['tables_removed'])}):\n")
                    for table in differences['tables_removed']:
                        self.results_text.insert(tk.END, f"  - {table}\n")
                    self.results_text.insert(tk.END, "\n")

                # Tables modified
                if differences['tables_modified']:
                    self.results_text.insert(tk.END, f"\ud83d\udd04 TABLES MODIFIED ({len(differences['tables_modified'])}):\n")
                    for table in differences['tables_modified']:
                        self.results_text.insert(tk.END, f"  ~ {table}\n")

                        # Show detailed record changes if available
                        if table in differences['record_changes']:
                            changes = differences['record_changes'][table]
                            if changes['records_added'] > 0:
                                self.results_text.insert(tk.END, f"    \ud83d\udcc8 Records added: {changes['records_added']}\n")
                            if changes['records_removed'] > 0:
                                self.results_text.insert(tk.END, f"    \ud83d\udcc9 Records removed: {changes['records_removed']}\n")
                            if changes['records_modified'] > 0:
                                self.results_text.insert(tk.END, f"    \ud83d\udcdd Records modified: {changes['records_modified']}\n")
                        self.results_text.insert(tk.END, "\n")

                # Additional analysis
                self.results_text.insert(tk.END, "DETAILED ANALYSIS:\n")
                self.results_text.insert(tk.END, "-" * 20 + "\n")

                # Calculate time difference
                try:
                    date1 = datetime.datetime.strptime(backup1['timestamp'], "%Y%m%d_%H%M%S")
                    date2 = datetime.datetime.strptime(backup2['timestamp'], "%Y%m%d_%H%M%S")
                    time_diff = abs((date2 - date1).total_seconds())

                    if time_diff < 3600:  # Less than 1 hour
                        time_str = f"{time_diff/60:.0f} minutes"
                    elif time_diff < 86400:  # Less than 1 day
                        time_str = f"{time_diff/3600:.1f} hours"
                    else:
                        time_str = f"{time_diff/86400:.1f} days"

                    self.results_text.insert(tk.END, f"Time between backups: {time_str}\n")
                except (ValueError, KeyError):
                    pass

                # Size comparison
                try:
                    size1 = backup1.get('size', 0)
                    size2 = backup2.get('size', 0)
                    size_diff = size2 - size1
                    size_diff_mb = size_diff / (1024 * 1024)

                    if size_diff > 0:
                        self.results_text.insert(tk.END, f"Size increase: +{size_diff_mb:.2f} MB\n")
                    elif size_diff < 0:
                        self.results_text.insert(tk.END, f"Size decrease: {size_diff_mb:.2f} MB\n")
                    else:
                        self.results_text.insert(tk.END, "Size unchanged\n")
                except (TypeError, KeyError):
                    pass

                # Recommendations
                if total_changes > 0:
                    self.results_text.insert(tk.END, "\n\ud83d\udca1 RECOMMENDATIONS:\n")
                    if len(differences['tables_added']) > 0:
                        self.results_text.insert(tk.END, "\u2022 New tables detected - verify expected schema changes\n")
                    if len(differences['tables_removed']) > 0:
                        self.results_text.insert(tk.END, "\u2022 Tables removed - ensure this was intentional\n")
                    if len(differences['tables_modified']) > 0:
                        self.results_text.insert(tk.END, "\u2022 Data modifications detected - review changes carefully\n")
            else:
                self.results_text.delete(1.0, tk.END)
                self.results_text.insert(tk.END, "\u274c COMPARISON FAILED\n")
                self.results_text.insert(tk.END, "=" * 20 + "\n\n")
                self.results_text.insert(tk.END, "Possible reasons:\n")
                self.results_text.insert(tk.END, "\u2022 One or both backup files are corrupted\n")
                self.results_text.insert(tk.END, "\u2022 Backup files are encrypted and password is incorrect\n")
                self.results_text.insert(tk.END, "\u2022 Backup files are in an unsupported format\n")
                self.results_text.insert(tk.END, "\u2022 Database connection error\n\n")
                self.results_text.insert(tk.END, "Try validating the individual backups first.\n")

        except Exception as e:
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, "\u274c COMPARISON ERROR\n")
            self.results_text.insert(tk.END, "=" * 20 + "\n\n")
            self.results_text.insert(tk.END, f"Error details: {str(e)}\n\n")
            self.results_text.insert(tk.END, "Troubleshooting steps:\n")
            self.results_text.insert(tk.END, "1. Verify both backup files exist and are accessible\n")
            self.results_text.insert(tk.END, "2. Check if backups are encrypted/compressed\n")
            self.results_text.insert(tk.END, "3. Ensure backup files are not corrupted\n")
            self.results_text.insert(tk.END, "4. Try comparing with different backup files\n")

            logger.error(f"Backup comparison failed: {e}")

            # Optionally show a more detailed error dialog
            if messagebox.askyesno("Detailed Error",
                                  f"Comparison failed with error: {str(e)}\n\n"
                                  "Would you like to see the full error details?"):
                import traceback
                error_details = traceback.format_exc()

                # Create a new window to show error details
                error_window = tk.Toplevel(self.dialog)
                error_window.title("Error Details")
                error_window.geometry("600x400")

                error_text = scrolledtext.ScrolledText(error_window, wrap=tk.WORD)
                error_text.pack(fill="both", expand=True, padx=10, pady=10)
                error_text.insert(1.0, error_details)

                ttk.Button(error_window, text="Close",
                          command=error_window.destroy).pack(pady=10)
