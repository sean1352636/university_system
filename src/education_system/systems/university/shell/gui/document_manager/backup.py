import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import shutil
from datetime import datetime
import logging

from education_system.platform.delivery.gui.tk_threads import start_thread, ui

logger = logging.getLogger(__name__)

try:
    from education_system.systems.university.infrastructure.database.db import get_connection
except ImportError:
    from education_system.systems.university.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

try:
    from education_system.systems.university.infrastructure.i18n import get_text as _t
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")


class BackupManager:
    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def _post(self, callback):
        """Run *callback* on the Tk main loop, from any thread.

        Backup and restore do their file I/O on a worker thread so the UI
        stays responsive, but Tk is single-threaded: configuring a label,
        destroying the progress dialog or opening a messagebox from that
        thread is undefined behaviour — stray TclErrors at best, a wedged
        interpreter at worst. Widget work is queued for the main thread via
        ui(); dropped if the window has already gone.
        """
        def _run():
            if self.root.winfo_exists():
                callback()

        ui(self.root, _run)

    def backup_system(self):
        """Create system backup"""
        try:
            import zipfile
            from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH
            from education_system import paths

            backup_dir = filedialog.askdirectory(title=_t('gui.shell.document_manager.backup.dialogs.select_backup_location', default="Select Backup Location"))
            if backup_dir:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_filename = f"document_system_backup_{timestamp}.zip"
                backup_path = os.path.join(backup_dir, backup_filename)

                with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
                    # Backup database
                    backup_zip.write(str(DEFAULT_DB_PATH), 'database/student_records.db')

                    # Backup document files
                    student_docs_dir = paths.UNIVERSITY_UPLOAD_DIR / 'student_documents'
                    if os.path.exists(student_docs_dir):
                        for root, dirs, files in os.walk(student_docs_dir):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arc_path = os.path.relpath(file_path, student_docs_dir)
                                backup_zip.write(file_path, f'student_documents/{arc_path}')

                messagebox.showinfo(_t('gui.shell.document_manager.backup.dialogs.success', default="Success"), f"System backup created successfully!\nLocation: {backup_path}")

        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.backup.dialogs.backup_error', default="Backup Error"), f"Failed to create backup: {str(e)}")

    def browse_backup_location(self):
        """Browse for backup location"""
        if hasattr(self.gui, 'backup_location'):
            folder = filedialog.askdirectory(title=_t('gui.shell.document_manager.backup.dialogs.select_backup_location', default="Select Backup Location"))
            if folder:
                self.gui.backup_location.delete(0, 'end')
                self.gui.backup_location.insert(0, folder)

    def create_backup_now(self):
        """Create backup immediately"""
        self.backup_system()

    def view_backups(self):
        """View existing backups"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.shell.document_manager.backup.windows.document_database_backups', default="Document Database Backups"))
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=_t('gui.shell.document_manager.backup.labels.database_backups', default="Database Backups"), font=('Arial', 14, 'bold')).pack(pady=10)

        # Backup list
        list_frame = ttk.LabelFrame(main_frame, text=_t('gui.shell.document_manager.backup.labels.available_backups', default="Available Backups"), padding=10)
        list_frame.pack(fill='both', expand=True, pady=10)

        columns = ('file', 'size', 'date', 'path')
        tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        tree.heading('file', text=_t('gui.shell.document_manager.backup.headings.filename', default='Filename'))
        tree.heading('size', text=_t('gui.shell.document_manager.backup.headings.size', default='Size'))
        tree.heading('date', text=_t('gui.shell.document_manager.backup.headings.created', default='Created'))
        tree.heading('path', text=_t('gui.shell.document_manager.backup.headings.full_path', default='Full Path'))

        tree.column('file', width=200)
        tree.column('size', width=100)
        tree.column('date', width=150)
        tree.column('path', width=300)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Load backups from backups directory
        backup_dir = os.path.join(os.path.dirname(get_connection().execute('PRAGMA database_list').fetchone()[2]), '..', 'backups')
        backup_dir = os.path.abspath(backup_dir)

        if os.path.exists(backup_dir):
            for filename in os.listdir(backup_dir):
                if filename.endswith('.db') or filename.endswith('.backup'):
                    filepath = os.path.join(backup_dir, filename)
                    size = os.path.getsize(filepath) / (1024 * 1024)  # MB
                    modified_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                    tree.insert('', 'end', values=(
                        filename,
                        f"{size:.2f} MB",
                        modified_time.strftime('%Y-%m-%d %H:%M:%S'),
                        filepath
                    ))

        # Buttons
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(pady=10)

        def create_new_backup():
            try:
                import shutil
                from tkinter import filedialog

                # Get current DB path
                from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH
                db_path = DEFAULT_DB_PATH

                # Ask where to save
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = filedialog.asksaveasfilename(
                    title=_t('gui.shell.document_manager.backup.dialogs.create_database_backup', default="Create Database Backup"),
                    defaultextension=".db",
                    initialfile=f"documents_backup_{timestamp}.db",
                    initialdir=backup_dir,
                    filetypes=[("Database files", "*.db"), ("Backup files", "*.backup"), ("All files", "*.*")]
                )

                if backup_path:
                    shutil.copy2(db_path, backup_path)
                    messagebox.showinfo(_t('gui.shell.document_manager.backup.dialogs.success', default="Success"), f"Backup created successfully:\n{backup_path}")
                    dialog.destroy()
                    self.view_backups()  # Refresh list

            except Exception as e:
                messagebox.showerror(_t('gui.shell.document_manager.backup.dialogs.error', default="Error"), f"Failed to create backup: {e}")

        def restore_selected():
            selection = tree.selection()
            if not selection:
                messagebox.showerror(_t('gui.shell.document_manager.backup.dialogs.error', default="Error"), _t('gui.shell.document_manager.backup.dialogs.please_select_a_backup_to_restore', default="Please select a backup to restore"))
                return

            values = tree.item(selection[0])['values']
            backup_path = values[3]

            if messagebox.askyesno(_t('gui.shell.document_manager.backup.dialogs.confirm_restore', default="Confirm Restore"),
                                   f"Restore database from:\n{values[0]}\n\n"
                                   "WARNING: This will replace the current database!\n"
                                   "Make sure you have a current backup first.\n\n"
                                   "Continue?"):
                self.restore_backup_from_path(backup_path)
                dialog.destroy()

        ttk.Button(buttons_frame, text=_t('gui.shell.document_manager.backup.buttons.create_new_backup', default="Create New Backup"), command=create_new_backup).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text=_t('gui.shell.document_manager.backup.buttons.restore_selected', default="Restore Selected"), command=restore_selected).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text=_t('gui.shell.document_manager.backup.buttons.close', default="Close"), command=dialog.destroy).pack(side='left', padx=5)

    def restore_backup(self):
        """Restore from backup - wrapper function"""
        from tkinter import filedialog

        backup_file = filedialog.askopenfilename(
            title=_t('gui.shell.document_manager.backup.dialogs.select_backup_file_to_restore', default="Select Backup File to Restore"),
            filetypes=[("Database files", "*.db"), ("Backup files", "*.backup"), ("All files", "*.*")]
        )

        if backup_file:
            if messagebox.askyesno(_t('gui.shell.document_manager.backup.dialogs.confirm_restore', default="Confirm Restore"),
                                   f"Restore database from:\n{backup_file}\n\n"
                                   "WARNING: This will replace the current database!\n"
                                   "Current data will be lost unless backed up.\n\n"
                                   "Continue?"):
                self.restore_backup_from_path(backup_file)

    def restore_backup_from_path(self, backup_path):
        """Restore database from backup file path"""
        try:
            import shutil
            from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH

            # Get current DB path
            db_path = DEFAULT_DB_PATH

            # Create backup of current database before restore
            current_backup = f"{db_path}.before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy2(db_path, current_backup)

            # Restore from backup
            shutil.copy2(backup_path, db_path)

            messagebox.showinfo(_t('gui.shell.document_manager.backup.dialogs.success', default="Success"),
                              f"Database restored successfully!\n\n"
                              f"Your previous database was backed up to:\n{current_backup}\n\n"
                              "Please restart the application for changes to take effect.")

        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.backup.dialogs.error', default="Error"), f"Failed to restore backup: {e}")

    def create_full_backup(self):
        """
        Create full database backup
        """
        try:
            from education_system import paths

            # Ask for backup location
            backup_path = filedialog.asksaveasfilename(
                defaultextension=".db",
                filetypes=[("Database files", "*.db"), ("All files", "*.*")],
                initialfile=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                initialdir="backups"
            )

            if not backup_path:
                return

            # Create backup directory if needed
            backup_dir = os.path.dirname(backup_path)
            if backup_dir:
                os.makedirs(backup_dir, exist_ok=True)

            # Show progress dialog
            progress_dialog = tk.Toplevel(self.root)
            progress_dialog.title(_t('gui.shell.document_manager.backup.windows.creating_backup', default="Creating Backup"))
            progress_dialog.geometry("400x150")
            progress_dialog.transient(self.root)
            progress_dialog.grab_set()

            ttk.Label(progress_dialog, text=_t('gui.shell.document_manager.backup.labels.creating_database_backup', default="Creating database backup..."),
                     font=('Arial', 12)).pack(pady=20)

            progress_bar = ttk.Progressbar(progress_dialog, mode='indeterminate', length=300)
            progress_bar.pack(pady=10)
            progress_bar.start()

            status_label = ttk.Label(progress_dialog, text="", font=('Arial', 9))
            status_label.pack(pady=10)

            def finish(backup_size=None, error=None):
                """Tear down the progress dialog and report. Main loop only."""
                try:
                    progress_bar.stop()
                    if progress_dialog.winfo_exists():
                        progress_dialog.grab_release()
                        progress_dialog.destroy()
                except tk.TclError:
                    pass  # dialog already gone

                if error is not None:
                    messagebox.showerror(_t('gui.shell.document_manager.backup.dialogs.error', default="Error"), f"Backup failed: {error}")
                else:
                    messagebox.showinfo(_t('gui.shell.document_manager.backup.dialogs.success', default="Success"),
                                      f"Backup created successfully!\n\n"
                                      f"Location: {backup_path}\n"
                                      f"Size: {backup_size:.2f} MB")

            def perform_backup():
                # Worker thread: file I/O and the activity-log write only.
                # Everything that touches a widget goes through _post().
                try:
                    self._post(lambda: status_label.config(
                        text=_t('gui.shell.document_manager.backup.text.copying_database_file', default="Copying database file...")))

                    # Copy database file
                    shutil.copy2(paths.UNIVERSITY_DEFAULT_DB_PATH, backup_path)

                    # Get backup size
                    backup_size = os.path.getsize(backup_path) / (1024 * 1024)

                    self.gui.log_event('create', 'backup', None, {
                        'backup_path': backup_path,
                        'size_mb': round(backup_size, 2)
                    })

                    self._post(lambda size=backup_size: finish(backup_size=size))

                except Exception as e:
                    logger.exception("Database backup failed")
                    self._post(lambda err=e: finish(error=err))

            # Run backup in separate thread to keep UI responsive
            start_thread(self.root, perform_backup)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.backup.dialogs.error', default="Error"), f"Failed to create backup: {e}")

    def backup_settings(self):
        """
        Configure automatic backup settings
        """
        try:
            from education_system import paths

            dialog = tk.Toplevel(self.root)
            dialog.title(_t('gui.shell.document_manager.backup.windows.backup_settings', default="Backup Settings"))
            dialog.geometry("700x600")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text=_t('gui.shell.document_manager.backup.labels.backup_settings', default="Backup Settings"),
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Auto backup settings
            auto_frame = ttk.LabelFrame(main_frame, text=_t('gui.shell.document_manager.backup.labels.automatic_backup', default="Automatic Backup"), padding=15)
            auto_frame.pack(fill='x', pady=(0, 15))

            enable_auto = tk.BooleanVar(value=False)
            ttk.Checkbutton(auto_frame, text=_t('gui.shell.document_manager.backup.buttons.enable_automatic_backups_variant_2', default="Enable automatic backups"), variable=enable_auto).pack(anchor='w', pady=5)

            # Frequency
            freq_frame = ttk.Frame(auto_frame)
            freq_frame.pack(fill='x', pady=10)

            ttk.Label(freq_frame, text=_t('gui.shell.document_manager.backup.labels.frequency', default="Frequency:")).pack(side='left', padx=(20, 5))
            frequency = ttk.Combobox(freq_frame, values=['Daily', 'Weekly', 'Monthly'], width=15, state='readonly')
            frequency.set('Daily')
            frequency.pack(side='left', padx=5)

            # Time
            time_frame = ttk.Frame(auto_frame)
            time_frame.pack(fill='x', pady=5)

            ttk.Label(time_frame, text=_t('gui.shell.document_manager.backup.labels.time', default="Time:")).pack(side='left', padx=(20, 5))
            backup_time = ttk.Combobox(time_frame, values=[f"{h:02d}:00" for h in range(24)], width=10, state='readonly')
            backup_time.set('02:00')
            backup_time.pack(side='left', padx=5)

            # Backup location
            location_frame = ttk.LabelFrame(main_frame, text=_t('gui.shell.document_manager.backup.labels.backup_location', default="Backup Location"), padding=15)
            location_frame.pack(fill='x', pady=(0, 15))

            location_var = tk.StringVar(value=str(paths.UNIVERSITY_BACKUP_FILES_DIR) + "/")
            ttk.Label(location_frame, text=_t('gui.shell.document_manager.backup.labels.directory', default="Directory:")).pack(anchor='w', pady=5)
            location_entry = ttk.Entry(location_frame, textvariable=location_var, width=50)
            location_entry.pack(fill='x', pady=5)

            def browse_location():
                directory = filedialog.askdirectory(initialdir="backups", title=_t('gui.shell.document_manager.backup.dialogs.select_backup_directory', default="Select Backup Directory"))
                if directory:
                    location_var.set(directory)

            ttk.Button(location_frame, text=_t('gui.shell.document_manager.backup.buttons.browse', default="Browse..."), command=browse_location).pack(anchor='w', pady=5)

            # Retention settings
            retention_frame = ttk.LabelFrame(main_frame, text=_t('gui.shell.document_manager.backup.labels.backup_retention', default="Backup Retention"), padding=15)
            retention_frame.pack(fill='x', pady=(0, 15))

            ttk.Label(retention_frame, text=_t('gui.shell.document_manager.backup.labels.keep_backups_for', default="Keep backups for:")).pack(anchor='w', pady=5)
            retention_days = tk.StringVar(value="30")
            retention_entry = ttk.Entry(retention_frame, textvariable=retention_days, width=10)
            retention_entry.pack(anchor='w', pady=5)
            ttk.Label(retention_frame, text=_t('gui.shell.document_manager.backup.labels.days_older_backups_will_be_automatically_deleted', default="days (older backups will be automatically deleted)"),
                     font=('Arial', 9), foreground='gray').pack(anchor='w')

            # Compression
            compress_frame = ttk.Frame(main_frame)
            compress_frame.pack(fill='x', pady=(0, 15))

            compress_backups = tk.BooleanVar(value=True)
            ttk.Checkbutton(compress_frame, text=_t('gui.shell.document_manager.backup.buttons.compress_backups_saves_disk_space', default="Compress backups (saves disk space)"),
                          variable=compress_backups).pack(anchor='w')

            # Recent backups
            recent_frame = ttk.LabelFrame(main_frame, text=_t('gui.shell.document_manager.backup.labels.recent_backups', default="Recent Backups"), padding=10)
            recent_frame.pack(fill='both', expand=True)

            backup_list = tk.Listbox(recent_frame, height=8)
            backup_list.pack(fill='both', expand=True)

            # Load recent backups
            try:
                backup_dir = "backups"
                if os.path.exists(backup_dir):
                    backups = [f for f in os.listdir(backup_dir) if f.endswith('.db')]
                    backups.sort(reverse=True)
                    for backup in backups[:10]:
                        bp = os.path.join(backup_dir, backup)
                        size = os.path.getsize(bp) / (1024 * 1024)
                        backup_list.insert(tk.END, f"{backup} ({size:.2f} MB)")
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x', pady=(15, 0))

            def save_settings():
                try:
                    # Save settings (in production, save to config file or database)
                    settings = {
                        'auto_backup': enable_auto.get(),
                        'frequency': frequency.get(),
                        'time': backup_time.get(),
                        'location': location_var.get(),
                        'retention_days': int(retention_days.get()),
                        'compress': compress_backups.get()
                    }

                    self.gui.log_event('update', 'backup_settings', None, settings)

                    messagebox.showinfo(_t('gui.shell.document_manager.backup.dialogs.success', default="Success"), _t('gui.shell.document_manager.backup.dialogs.backup_settings_saved_successfully', default="Backup settings saved successfully"))
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror(_t('gui.shell.document_manager.backup.dialogs.error', default="Error"), f"Failed to save settings: {e}")

            ttk.Button(action_frame, text=_t('gui.shell.document_manager.backup.buttons.save_settings', default="Save Settings"), command=save_settings).pack(side='left', padx=5)
            ttk.Button(action_frame, text=_t('gui.shell.document_manager.backup.buttons.create_backup_now', default="Create Backup Now"), command=self.create_full_backup).pack(side='left', padx=5)
            ttk.Button(action_frame, text=_t('gui.shell.document_manager.backup.buttons.close', default="Close"), command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.backup.dialogs.error', default="Error"), f"Failed to open backup settings: {e}")

    def restore_from_backup(self):
        """
        Restore database from backup file
        """
        try:
            from education_system import paths

            # Warning dialog
            response = messagebox.askyesno(_t('gui.shell.document_manager.backup.dialogs.confirm_restore', default="Confirm Restore"),
                                         _t('gui.shell.document_manager.backup.dialogs.warning_restoring_from_backup_will_replace_the_current_database', default="\u26a0\ufe0f WARNING \u26a0\ufe0f\n\n"
                                         "Restoring from backup will REPLACE the current database.\n"
                                         "All current data will be lost!\n\n"
                                         "Do you want to continue?"),
                                         icon='warning')

            if not response:
                return

            # Select backup file
            backup_file = filedialog.askopenfilename(
                title=_t('gui.shell.document_manager.backup.dialogs.select_backup_file', default="Select Backup File"),
                filetypes=[("Database files", "*.db"), ("All files", "*.*")],
                initialdir="backups"
            )

            if not backup_file:
                return

            # Verify backup file
            if not os.path.exists(backup_file):
                messagebox.showerror(_t('gui.shell.document_manager.backup.dialogs.error', default="Error"), _t('gui.shell.document_manager.backup.dialogs.backup_file_not_found', default="Backup file not found"))
                return

            # Create safety backup of current database
            paths.UNIVERSITY_BACKUP_FILES_DIR.mkdir(parents=True, exist_ok=True)
            safety_backup = paths.UNIVERSITY_BACKUP_FILES_DIR / f"pre_restore_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

            # Show progress dialog
            progress_dialog = tk.Toplevel(self.root)
            progress_dialog.title(_t('gui.shell.document_manager.backup.windows.restoring_database', default="Restoring Database"))
            progress_dialog.geometry("400x200")
            progress_dialog.transient(self.root)
            progress_dialog.grab_set()

            ttk.Label(progress_dialog, text=_t('gui.shell.document_manager.backup.labels.restoring_database_from_backup', default="Restoring database from backup..."),
                     font=('Arial', 12)).pack(pady=20)

            progress_bar = ttk.Progressbar(progress_dialog, mode='indeterminate', length=300)
            progress_bar.pack(pady=10)
            progress_bar.start()

            status_label = ttk.Label(progress_dialog, text="", font=('Arial', 9))
            status_label.pack(pady=10)

            def finish(error=None):
                """Tear down the progress dialog and report. Main loop only."""
                try:
                    progress_bar.stop()
                    if progress_dialog.winfo_exists():
                        progress_dialog.grab_release()
                        progress_dialog.destroy()
                except tk.TclError:
                    pass  # dialog already gone

                if error is not None:
                    messagebox.showerror(_t('gui.shell.document_manager.backup.dialogs.error', default="Error"),
                                       f"Restore failed: {error}\n\n"
                                       f"Your original database was backed up to:\n{safety_backup}")
                else:
                    messagebox.showinfo(_t('gui.shell.document_manager.backup.dialogs.success', default="Success"),
                                      f"Database restored successfully!\n\n"
                                      f"Safety backup created at:\n{safety_backup}\n\n"
                                      f"Please restart the application for changes to take effect.")

            def perform_restore():
                # Worker thread: file I/O and the activity-log write only.
                # Everything that touches a widget goes through _post().
                try:
                    # Create safety backup
                    self._post(lambda: status_label.config(
                        text=_t('gui.shell.document_manager.backup.text.creating_safety_backup', default="Creating safety backup...")))
                    shutil.copy2(paths.UNIVERSITY_DEFAULT_DB_PATH, safety_backup)

                    # Restore from backup
                    self._post(lambda: status_label.config(
                        text=_t('gui.shell.document_manager.backup.text.restoring_database', default="Restoring database...")))
                    shutil.copy2(backup_file, paths.UNIVERSITY_DEFAULT_DB_PATH)

                    self.gui.log_event('restore', 'database', None, {
                        'backup_file': backup_file,
                        'safety_backup': safety_backup
                    })

                    self._post(finish)

                except Exception as e:
                    logger.exception("Database restore failed")
                    self._post(lambda err=e: finish(error=err))

            # Run restore in separate thread
            start_thread(self.root, perform_restore)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.backup.dialogs.error', default="Error"), f"Failed to restore from backup: {e}")

    def view_backup_history(self):
        """View backup history"""
        try:
            from education_system import paths

            history_window = tk.Toplevel(self.root)
            history_window.title(_t('gui.shell.document_manager.backup.windows.backup_history', default="Backup History"))
            history_window.geometry("1000x700")

            main_frame = ttk.Frame(history_window, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=_t('gui.shell.document_manager.backup.labels.backup_history', default="Backup History"),
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Read backup metadata
            backup_metadata_path = paths.UNIVERSITY_DATA_DIR / "backup_metadata.json"
            backups = []

            try:
                import json
                if os.path.exists(backup_metadata_path):
                    with open(backup_metadata_path, 'r') as f:
                        backup_data = json.load(f)
                        backups = backup_data.get('backups', [])
            except Exception as e:
                print(f"Error reading backup metadata: {e}")

            # Create table
            columns = ('Date', 'Type', 'Size', 'Location', 'Status')
            tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)

            widths = [150, 100, 100, 400, 100]
            for i, col in enumerate(columns):
                tree.heading(col, text=col)
                tree.column(col, width=widths[i])

            for backup in backups:
                tree.insert('', 'end', values=(
                    backup.get('timestamp', 'N/A'),
                    backup.get('type', 'N/A'),
                    backup.get('size', 'N/A'),
                    backup.get('path', 'N/A'),
                    backup.get('status', 'N/A')
                ))

            scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Buttons
            button_frame = ttk.Frame(history_window)
            button_frame.pack(pady=10)

            def restore_selected():
                selected = tree.selection()
                if not selected:
                    messagebox.showwarning(_t('gui.shell.document_manager.backup.dialogs.warning', default="Warning"), _t('gui.shell.document_manager.backup.dialogs.please_select_a_backup_to_restore', default="Please select a backup to restore"))
                    return

                backup_path = tree.item(selected[0])['values'][3]
                confirm = messagebox.askyesno(_t('gui.shell.document_manager.backup.dialogs.confirm_restore', default="Confirm Restore"),
                                             f"Are you sure you want to restore from:\n{backup_path}\n\nThis will replace the current database!")
                if confirm:
                    self.restore_backup_from_path(backup_path)

            ttk.Button(button_frame, text=_t('gui.shell.document_manager.backup.buttons.restore_selected', default="Restore Selected"), command=restore_selected).pack(side='left', padx=5)
            ttk.Button(button_frame, text=_t('gui.shell.document_manager.backup.buttons.refresh', default="Refresh"), command=lambda: self.view_backup_history()).pack(side='left', padx=5)
            ttk.Button(button_frame, text=_t('gui.shell.document_manager.backup.buttons.close', default="Close"), command=history_window.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.backup.dialogs.error', default="Error"), f"Failed to view backup history: {e}")

    def schedule_automatic_backup(self):
        """Configure automatic backup schedule"""
        try:
            from education_system import paths

            dialog = tk.Toplevel(self.root)
            dialog.title(_t('gui.shell.document_manager.backup.windows.schedule_automatic_backup', default="Schedule Automatic Backup"))
            dialog.geometry("700x550")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=_t('gui.shell.document_manager.backup.labels.automatic_backup_schedule', default="Automatic Backup Schedule"),
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Enable/disable
            enable_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(main_frame, text=_t('gui.shell.document_manager.backup.buttons.enable_automatic_backups', default="Enable Automatic Backups"),
                           variable=enable_var).pack(anchor='w', pady=10)

            # Frequency
            freq_frame = ttk.LabelFrame(main_frame, text=_t('gui.shell.document_manager.backup.labels.backup_frequency', default="Backup Frequency"), padding=15)
            freq_frame.pack(fill='x', pady=10)

            frequency_var = tk.StringVar(value=_t('gui.shell.document_manager.backup.values.daily', default="daily"))
            ttk.Radiobutton(freq_frame, text=_t('gui.shell.document_manager.backup.buttons.daily', default="Daily"), variable=frequency_var, value="daily").pack(anchor='w')
            ttk.Radiobutton(freq_frame, text=_t('gui.shell.document_manager.backup.buttons.weekly', default="Weekly"), variable=frequency_var, value="weekly").pack(anchor='w')
            ttk.Radiobutton(freq_frame, text=_t('gui.shell.document_manager.backup.buttons.monthly', default="Monthly"), variable=frequency_var, value="monthly").pack(anchor='w')

            # Time
            time_frame = ttk.LabelFrame(main_frame, text=_t('gui.shell.document_manager.backup.labels.backup_time', default="Backup Time"), padding=15)
            time_frame.pack(fill='x', pady=10)

            ttk.Label(time_frame, text=_t('gui.shell.document_manager.backup.labels.hour_0_23', default="Hour (0-23):")).grid(row=0, column=0, padx=5)
            hour_var = tk.StringVar(value="2")
            hour_spin = ttk.Spinbox(time_frame, from_=0, to=23, textvariable=hour_var, width=10)
            hour_spin.grid(row=0, column=1, padx=5)

            ttk.Label(time_frame, text=_t('gui.shell.document_manager.backup.labels.minute_0_59', default="Minute (0-59):")).grid(row=0, column=2, padx=5)
            minute_var = tk.StringVar(value="0")
            minute_spin = ttk.Spinbox(time_frame, from_=0, to=59, textvariable=minute_var, width=10)
            minute_spin.grid(row=0, column=3, padx=5)

            # Retention
            retention_frame = ttk.LabelFrame(main_frame, text=_t('gui.shell.document_manager.backup.labels.backup_retention', default="Backup Retention"), padding=15)
            retention_frame.pack(fill='x', pady=10)

            ttk.Label(retention_frame, text=_t('gui.shell.document_manager.backup.labels.keep_backups_for_days', default="Keep backups for (days):")).grid(row=0, column=0, padx=5)
            retention_var = tk.StringVar(value="30")
            retention_spin = ttk.Spinbox(retention_frame, from_=1, to=365, textvariable=retention_var, width=10)
            retention_spin.grid(row=0, column=1, padx=5)

            def save_schedule():
                config = {
                    'enabled': enable_var.get(),
                    'frequency': frequency_var.get(),
                    'hour': int(hour_var.get()),
                    'minute': int(minute_var.get()),
                    'retention_days': int(retention_var.get())
                }

                # Save configuration
                config_path = paths.UNIVERSITY_DATA_DIR / "backup_schedule.json"
                try:
                    import json
                    with open(config_path, 'w') as f:
                        json.dump(config, f, indent=2)

                    messagebox.showinfo(_t('gui.shell.document_manager.backup.dialogs.success', default="Success"), _t('gui.shell.document_manager.backup.dialogs.backup_schedule_saved_successfully', default="Backup schedule saved successfully!"))
                    dialog.destroy()
                except Exception as e:
                    messagebox.showerror(_t('gui.shell.document_manager.backup.dialogs.error', default="Error"), f"Failed to save schedule: {e}")

            ttk.Button(main_frame, text=_t('gui.shell.document_manager.backup.buttons.save_schedule', default="Save Schedule"), command=save_schedule).pack(pady=20)
            ttk.Button(main_frame, text=_t('gui.shell.document_manager.backup.buttons.cancel', default="Cancel"), command=dialog.destroy).pack()

        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.backup.dialogs.error', default="Error"), f"Failed to open schedule dialog: {e}")
