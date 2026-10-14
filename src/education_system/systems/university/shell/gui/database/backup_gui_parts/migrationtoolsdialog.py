"""Extracted class implementation."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import backup_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class MigrationToolsDialog:
    """Dialog exposing real database maintenance/migration actions.

    Each button runs a genuine SQLite maintenance command against the live
    database via ``get_connection()`` and reports the result in the output
    area. All statements are fixed maintenance PRAGMAs / VACUUM (no user
    input is interpolated into SQL).
    """

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.database.backup_gui_parts.migrationtoolsdialog.windows.database_maintenance_migration_tools', default="Database Maintenance & Migration Tools"))
        self.dialog.geometry("600x450")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Create dialog widgets."""
        controls_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.backup_gui_parts.migrationtoolsdialog.labels.maintenance_actions', default="Maintenance Actions"), padding=10)
        controls_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(controls_frame, text=_t('gui.shell.database.backup_gui_parts.migrationtoolsdialog.buttons.integrity_check', default="Integrity Check"),
                   command=self.run_integrity_check).grid(row=0, column=0, padx=4, pady=4, sticky="ew")
        ttk.Button(controls_frame, text=_t('gui.shell.database.backup_gui_parts.migrationtoolsdialog.buttons.quick_check', default="Quick Check"),
                   command=self.run_quick_check).grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        ttk.Button(controls_frame, text=_t('gui.shell.database.backup_gui_parts.migrationtoolsdialog.buttons.vacuum_compact', default="VACUUM (compact)"),
                   command=self.run_vacuum).grid(row=0, column=2, padx=4, pady=4, sticky="ew")
        ttk.Button(controls_frame, text=_t('gui.shell.database.backup_gui_parts.migrationtoolsdialog.buttons.checkpoint_wal', default="Checkpoint WAL"),
                   command=self.run_checkpoint).grid(row=1, column=0, padx=4, pady=4, sticky="ew")
        ttk.Button(controls_frame, text=_t('gui.shell.database.backup_gui_parts.migrationtoolsdialog.buttons.foreign_key_check', default="Foreign Key Check"),
                   command=self.run_foreign_key_check).grid(row=1, column=1, padx=4, pady=4, sticky="ew")
        ttk.Button(controls_frame, text=_t('gui.shell.database.backup_gui_parts.migrationtoolsdialog.buttons.show_schema_info', default="Show Schema Info"),
                   command=self.show_schema_info).grid(row=1, column=2, padx=4, pady=4, sticky="ew")

        for col in range(3):
            controls_frame.columnconfigure(col, weight=1)

        output_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.backup_gui_parts.migrationtoolsdialog.labels.output', default="Output"), padding=10)
        output_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.output = scrolledtext.ScrolledText(output_frame, wrap="word", height=14)
        self.output.pack(fill="both", expand=True)

        ttk.Button(self.dialog, text=_t('gui.shell.database.backup_gui_parts.migrationtoolsdialog.buttons.close', default="Close"),
                   command=self.dialog.destroy).pack(pady=8)

    def _log(self, message):
        """Append a timestamped line to the output area."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.output.insert("end", f"[{timestamp}] {message}\n")
        self.output.see("end")
        self.dialog.update_idletasks()

    def _run_maintenance(self, label, sql):
        """Run a fixed maintenance statement and report all returned rows."""
        self._log(f"Running: {label} ...")
        try:
            conn = get_connection()
            try:
                cursor = conn.execute(sql)
                rows = cursor.fetchall()
                conn.commit()
            finally:
                try:
                    conn.close()
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)

            if rows:
                for row in rows:
                    self._log("  " + " | ".join(str(v) for v in row))
            else:
                self._log("  (no rows returned)")
            self._log(f"{label}: done.")
        except Exception as e:
            logger.error(f"{label} failed: {e}")
            self._log(f"{label}: ERROR - {e}")
            messagebox.showerror(_t('gui.shell.database.backup_gui_parts.migrationtoolsdialog.dialogs.maintenance_error', default="Maintenance Error"),
                                 f"{label} failed: {e}", parent=self.dialog)

    def run_integrity_check(self):
        """PRAGMA integrity_check on the live database."""
        self._run_maintenance("Integrity check", "PRAGMA integrity_check")

    def run_quick_check(self):
        """PRAGMA quick_check (faster, lighter than integrity_check)."""
        self._run_maintenance("Quick check", "PRAGMA quick_check")

    def run_vacuum(self):
        """Rebuild/compact the database file."""
        if not messagebox.askyesno(_t('gui.shell.database.backup_gui_parts.migrationtoolsdialog.dialogs.confirm_vacuum', default="Confirm VACUUM"),
                                    _t('gui.shell.database.backup_gui_parts.migrationtoolsdialog.dialogs.vacuum_rebuilds_the_entire_database_file_and_may_take_a_while_co', default="VACUUM rebuilds the entire database file and may "
                                    "take a while.\n\nContinue?"), parent=self.dialog):
            return
        self._run_maintenance("VACUUM", "VACUUM")

    def run_checkpoint(self):
        """Checkpoint the write-ahead log back into the main database."""
        self._run_maintenance("WAL checkpoint", "PRAGMA wal_checkpoint(TRUNCATE)")

    def run_foreign_key_check(self):
        """Report any foreign-key constraint violations."""
        self._run_maintenance("Foreign key check", "PRAGMA foreign_key_check")

    def show_schema_info(self):
        """List tables and row counts from the live database schema."""
        self._log("Reading schema info ...")
        try:
            conn = get_connection()
            try:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = ? ORDER BY name",
                    ("table",),
                )
                tables = [r[0] for r in cursor.fetchall()]
                self._log(f"  {len(tables)} table(s) found.")
                for name in tables:
                    # Validate the identifier before embedding it in a
                    # count query (table names cannot be bound as params).
                    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                        self._log(f"  {name}: (skipped - invalid identifier)")
                        continue
                    try:
                        c = conn.execute(f'SELECT COUNT(*) FROM "{name}"')
                        count = c.fetchone()[0]
                        self._log(f"  {name}: {count} row(s)")
                    except Exception as inner:
                        self._log(f"  {name}: (count failed - {inner})")
            finally:
                try:
                    conn.close()
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)
            self._log("Schema info: done.")
        except Exception as e:
            logger.error(f"Schema info failed: {e}")
            self._log(f"Schema info: ERROR - {e}")
            messagebox.showerror(_t('gui.shell.database.backup_gui_parts.migrationtoolsdialog.dialogs.schema_error', default="Schema Error"),
                                 f"Could not read schema: {e}", parent=self.dialog)
