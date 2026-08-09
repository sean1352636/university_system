"""Extracted class implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import backup_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class DatabaseSettingsDialog:
    """Dialog to view and edit database-related backup settings.

    Fields are wired to the real ``config`` dictionary persisted by
    ``save_config()`` (``backup_config.json``). The live database path and
    journal mode are read directly from the running database and shown
    read-only, since those are managed by the infrastructure DB layer.
    """

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.database.backup_gui_parts.databasesettingsdialog.windows.database_backup_settings', default="Database Backup Settings"))
        self.dialog.geometry("600x450")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_current_settings()

    def create_widgets(self):
        """Create dialog widgets."""
        # Live database info (read-only)
        info_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.backup_gui_parts.databasesettingsdialog.labels.database_read_only', default="Database (read-only)"), padding=10)
        info_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(info_frame, text=_t('gui.shell.database.backup_gui_parts.databasesettingsdialog.labels.database_path', default="Database path:")).grid(row=0, column=0, sticky="w", pady=2)
        self.db_path_var = tk.StringVar(value=str(DEFAULT_DB_PATH))
        ttk.Entry(info_frame, textvariable=self.db_path_var, width=55,
                  state="readonly").grid(row=0, column=1, sticky="w", padx=5)

        ttk.Label(info_frame, text=_t('gui.shell.database.backup_gui_parts.databasesettingsdialog.labels.journal_mode', default="Journal mode:")).grid(row=1, column=0, sticky="w", pady=2)
        self.journal_mode_var = tk.StringVar(value=_t('gui.shell.database.backup_gui_parts.databasesettingsdialog.values.unknown', default="(unknown)"))
        ttk.Entry(info_frame, textvariable=self.journal_mode_var, width=20,
                  state="readonly").grid(row=1, column=1, sticky="w", padx=5)

        # Editable backup settings
        settings_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.backup_gui_parts.databasesettingsdialog.labels.backup_settings', default="Backup Settings"), padding=10)
        settings_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(settings_frame, text=_t('gui.shell.database.backup_gui_parts.databasesettingsdialog.labels.backup_directory', default="Backup directory:")).grid(row=0, column=0, sticky="w", pady=4)
        self.backup_dir_var = tk.StringVar()
        ttk.Entry(settings_frame, textvariable=self.backup_dir_var,
                  width=45).grid(row=0, column=1, sticky="w", padx=5)
        ttk.Button(settings_frame, text=_t('gui.shell.database.backup_gui_parts.databasesettingsdialog.buttons.browse', default="Browse..."),
                   command=self.browse_directory).grid(row=0, column=2, padx=5)

        ttk.Label(settings_frame, text=_t('gui.shell.database.backup_gui_parts.databasesettingsdialog.labels.max_backups_to_keep', default="Max backups to keep:")).grid(row=1, column=0, sticky="w", pady=4)
        self.max_backups_var = tk.StringVar()
        ttk.Spinbox(settings_frame, textvariable=self.max_backups_var,
                    from_=1, to=999, width=10).grid(row=1, column=1, sticky="w", padx=5)

        self.auto_backup_var = tk.BooleanVar()
        ttk.Checkbutton(settings_frame, text=_t('gui.shell.database.backup_gui_parts.databasesettingsdialog.buttons.enable_automatic_scheduled_backups', default="Enable automatic scheduled backups"),
                        variable=self.auto_backup_var).grid(row=2, column=0, columnspan=2,
                                                            sticky="w", pady=4)

        self.verify_var = tk.BooleanVar()
        ttk.Checkbutton(settings_frame, text=_t('gui.shell.database.backup_gui_parts.databasesettingsdialog.buttons.verify_backup_integrity_after_creation', default="Verify backup integrity after creation"),
                        variable=self.verify_var).grid(row=3, column=0, columnspan=2,
                                                       sticky="w", pady=4)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        ttk.Button(button_frame, text=_t('gui.shell.database.backup_gui_parts.databasesettingsdialog.buttons.save', default="Save"), command=self.save_settings).pack(side="right", padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.database.backup_gui_parts.databasesettingsdialog.buttons.close', default="Close"), command=self.dialog.destroy).pack(side="right")

    def load_current_settings(self):
        """Populate widgets from the live config and database."""
        self.backup_dir_var.set(str(config.get("backup_directory", "")))
        self.max_backups_var.set(str(config.get("max_backups", 10)))
        self.auto_backup_var.set(bool(config.get("auto_backup_enabled", True)))
        self.verify_var.set(bool(config.get("verify_integrity", True)))

        # Read the live journal mode from the running database
        try:
            conn = get_connection()
            try:
                cursor = conn.execute("PRAGMA journal_mode")
                row = cursor.fetchone()
                if row:
                    self.journal_mode_var.set(str(row[0]).upper())
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Could not read journal mode: {e}")
            self.journal_mode_var.set("(unavailable)")

    def browse_directory(self):
        """Choose a backup directory."""
        directory = filedialog.askdirectory(
            title=_t('gui.shell.database.backup_gui_parts.databasesettingsdialog.dialogs.select_backup_directory', default="Select Backup Directory"),
            initialdir=self.backup_dir_var.get() or str(DEFAULT_DB_PATH),
            parent=self.dialog,
        )
        if directory:
            self.backup_dir_var.set(directory)

    def save_settings(self):
        """Persist edited settings via the shared config mechanism."""
        try:
            backup_dir = self.backup_dir_var.get().strip()
            if not backup_dir:
                messagebox.showwarning(_t('gui.shell.database.backup_gui_parts.databasesettingsdialog.dialogs.invalid_input', default="Invalid Input"),
                                       _t('gui.shell.database.backup_gui_parts.databasesettingsdialog.dialogs.backup_directory_cannot_be_empty', default="Backup directory cannot be empty."),
                                       parent=self.dialog)
                return

            config["backup_directory"] = backup_dir
            config["max_backups"] = int(self.max_backups_var.get())
            config["auto_backup_enabled"] = self.auto_backup_var.get()
            config["verify_integrity"] = self.verify_var.get()

            save_config()
            messagebox.showinfo(_t('gui.shell.database.backup_gui_parts.databasesettingsdialog.dialogs.success', default="Success"), _t('gui.shell.database.backup_gui_parts.databasesettingsdialog.dialogs.database_settings_saved', default="Database settings saved."), parent=self.dialog)
            self.dialog.destroy()
        except ValueError as e:
            messagebox.showerror(_t('gui.shell.database.backup_gui_parts.databasesettingsdialog.dialogs.invalid_input', default="Invalid Input"),
                                 f"Please check your input values: {e}",
                                 parent=self.dialog)
        except Exception as e:
            messagebox.showerror(_t('gui.shell.database.backup_gui_parts.databasesettingsdialog.dialogs.error', default="Error"), f"Failed to save settings: {e}", parent=self.dialog)
