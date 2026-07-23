import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import threading
import logging
from datetime import datetime
import os

from education_system.post_18.university_system.core.i18n import get_text as _t
from education_system.post_18.university_system.infrastructure.database.db import DEFAULT_DB_PATH

from education_system.post_18.university_system.modules.domain.academics.gui.plagiarism_main_gui.config import GuiConfig
from education_system.post_18.university_system.modules.domain.academics.gui.plagiarism_main_gui.common import logger


class BackupRestoreDialog:
    """Dialog for system backup and restore operations"""

    def __init__(self, parent, checker):
        self.parent = parent
        self.checker = checker
        self.dialog = None

    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Repository Search")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")

        # Create interface first
        self.create_search_interface()
        self.load_all_documents()

        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab
        self.create_interface()

    def create_interface(self):
        """Create the backup/restore interface"""
        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text=_t("plagiarism.backup_restore"), font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))

        # Backup section
        backup_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.create_backup"), padding=GuiConfig.PADDING_MEDIUM)
        backup_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        ttk.Label(backup_frame, text="Create a backup of the plagiarism checker database and documents.").pack(anchor=tk.W, pady=(0, GuiConfig.PADDING_SMALL))

        backup_options_frame = ttk.Frame(backup_frame)
        backup_options_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_SMALL))

        self.include_documents_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(backup_options_frame, text="Include document content", variable=self.include_documents_var).pack(anchor=tk.W)

        self.include_results_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(backup_options_frame, text="Include plagiarism results", variable=self.include_results_var).pack(anchor=tk.W)

        ttk.Button(backup_frame, text=_t("plagiarism.create_backup"), command=self.create_backup).pack(anchor=tk.W, pady=(GuiConfig.PADDING_SMALL, 0))

        # Restore section
        restore_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.restore_from_backup"), padding=GuiConfig.PADDING_MEDIUM)
        restore_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        ttk.Label(restore_frame, text="Restore system from a previous backup file.").pack(anchor=tk.W, pady=(0, GuiConfig.PADDING_SMALL))

        self.backup_file_var = tk.StringVar()
        backup_file_frame = ttk.Frame(restore_frame)
        backup_file_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_SMALL))

        ttk.Entry(backup_file_frame, textvariable=self.backup_file_var, state='readonly').pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(backup_file_frame, text="Browse...", command=self.select_backup_file).pack(side=tk.RIGHT, padx=(GuiConfig.PADDING_SMALL, 0))

        ttk.Button(restore_frame, text=_t("plagiarism.restore_from_backup"), command=self.restore_backup).pack(anchor=tk.W, pady=(GuiConfig.PADDING_SMALL, 0))

        # Progress
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        ttk.Label(main_frame, textvariable=self.status_var).pack()

        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=(GuiConfig.PADDING_MEDIUM, 0))

    def create_backup(self):
        """Create a system backup"""
        try:
            from tkinter import filedialog
            import zipfile
            import json

            # Select backup location
            filename = filedialog.asksaveasfilename(
                defaultextension=".backup",
                filetypes=[("Backup files", "*.backup"), ("ZIP files", "*.zip"), ("All files", "*.*")],
                title="Save Backup"
            )

            if not filename:
                return

            def backup_task():
                try:
                    self.dialog.after(0, lambda: self.status_var.set("Creating backup..."))
                    self.dialog.after(0, lambda: self.progress_var.set(10))

                    with zipfile.ZipFile(filename, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
                        # Backup database
                        if os.path.exists(str(DEFAULT_DB_PATH)):
                            backup_zip.write(str(DEFAULT_DB_PATH), 'database/student_records.db')
                            self.dialog.after(0, lambda: self.progress_var.set(30))

                        # Backup configuration
                        config = {
                            'backup_date': datetime.now().isoformat(),
                            'include_documents': self.include_documents_var.get(),
                            'include_results': self.include_results_var.get(),
                            'version': '2.0'
                        }

                        backup_zip.writestr('config.json', json.dumps(config, indent=2))
                        self.dialog.after(0, lambda: self.progress_var.set(50))

                        # Backup documents if requested
                        if self.include_documents_var.get():
                            self.dialog.after(0, lambda: self.status_var.set("Backing up documents..."))

                            with self.checker.get_db_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute('SELECT id, title, content FROM document_repository')
                                documents = cursor.fetchall()

                                for i, (doc_id, title, content) in enumerate(documents):
                                    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                                    backup_zip.writestr(f'documents/{doc_id}_{safe_title}.txt', content)

                                    progress = 50 + (i / len(documents)) * 30
                                    self.dialog.after(0, lambda p=progress: self.progress_var.set(p))

                        self.dialog.after(0, lambda: self.progress_var.set(100))
                        self.dialog.after(0, lambda: self.status_var.set("Backup completed"))
                        self.dialog.after(0, lambda: messagebox.showinfo("Success", f"Backup created successfully!\nLocation: {filename}"))

                except Exception as e:
                    error_msg = str(e)
                    self.dialog.after(0, lambda: self.status_var.set("Backup failed"))
                    self.dialog.after(0, lambda err=error_msg: messagebox.showerror("Error", f"Backup failed: {err}"))

            thread = threading.Thread(target=backup_task, daemon=True)
            thread.start()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create backup: {e}")

    def select_backup_file(self):
        """Select backup file for restore"""
        filename = filedialog.askopenfilename(
            title="Select Backup File",
            filetypes=[("Backup files", "*.backup"), ("ZIP files", "*.zip"), ("All files", "*.*")]
        )

        if filename:
            self.backup_file_var.set(filename)

    def restore_backup(self):
        """Restore from backup file"""
        backup_file = self.backup_file_var.get()
        if not backup_file:
            messagebox.showwarning("No File", "Please select a backup file.")
            return

        if not messagebox.askyesno("Confirm Restore",
                                   "This will replace the current system data. Are you sure?"):
            return

        try:
            import zipfile
            import json

            def restore_task():
                try:
                    self.dialog.after(0, lambda: self.status_var.set("Restoring from backup..."))
                    self.dialog.after(0, lambda: self.progress_var.set(10))

                    with zipfile.ZipFile(backup_file, 'r') as backup_zip:
                        # Read configuration
                        try:
                            config_data = backup_zip.read('config.json')
                            config = json.loads(config_data.decode('utf-8'))
                            self.dialog.after(0, lambda: self.status_var.set(f"Restoring backup from {config['backup_date']}..."))
                        except Exception:
                            config = {}

                        self.dialog.after(0, lambda: self.progress_var.set(30))

                        # Restore database
                        if 'database/student_records.db' in backup_zip.namelist():
                            backup_zip.extract('database/student_records.db', '.')
                            os.rename('database/student_records.db', str(DEFAULT_DB_PATH))
                            self.dialog.after(0, lambda: self.progress_var.set(70))

                        self.dialog.after(0, lambda: self.progress_var.set(100))
                        self.dialog.after(0, lambda: self.status_var.set("Restore completed"))
                        self.dialog.after(0, lambda: messagebox.showinfo("Success", "System restored successfully!\nPlease restart the application."))

                except Exception as e:
                    error_msg = str(e)
                    self.dialog.after(0, lambda: self.status_var.set("Restore failed"))
                    self.dialog.after(0, lambda err=error_msg: messagebox.showerror("Error", f"Restore failed: {err}"))

            thread = threading.Thread(target=restore_task, daemon=True)
            thread.start()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to restore backup: {e}")
