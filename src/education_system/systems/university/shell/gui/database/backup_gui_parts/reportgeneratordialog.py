"""Extracted class implementation."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import backup_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class ReportGeneratorDialog:
    """Dialog that generates a comprehensive backup & database report.

    Summarises the live database (path, size, journal mode, table count) and
    the contents of the configured backup directory (each backup file's size
    and modification time, plus totals). The report can be saved to a text
    file. All values are read live; nothing is fabricated.
    """

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.database.backup_gui_parts.reportgeneratordialog.windows.backup_database_report', default="Backup & Database Report"))
        self.dialog.geometry("600x450")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.generate_report()

    def create_widgets(self):
        """Create dialog widgets."""
        report_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.backup_gui_parts.reportgeneratordialog.labels.report', default="Report"), padding=10)
        report_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.output = scrolledtext.ScrolledText(report_frame, wrap="word", height=18)
        self.output.pack(fill="both", expand=True)

        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=8)
        ttk.Button(button_frame, text=_t('gui.shell.database.backup_gui_parts.reportgeneratordialog.buttons.refresh', default="Refresh"),
                   command=self.generate_report).pack(side="left")
        ttk.Button(button_frame, text=_t('gui.shell.database.backup_gui_parts.reportgeneratordialog.buttons.save_to_file', default="Save to File..."),
                   command=self.save_report).pack(side="right", padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.database.backup_gui_parts.reportgeneratordialog.buttons.close', default="Close"),
                   command=self.dialog.destroy).pack(side="right")

    def _write(self, line=""):
        self.output.insert("end", line + "\n")

    def generate_report(self):
        """Build the report from live database and backup-directory state."""
        self.output.delete("1.0", "end")
        generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self._write("=" * 60)
        self._write("COMPREHENSIVE BACKUP & DATABASE REPORT")
        self._write(f"Generated: {generated_at}")
        self._write("=" * 60)
        self._write()

        # --- Live database section ---
        self._write("DATABASE")
        self._write("-" * 60)
        db_path = str(DEFAULT_DB_PATH)
        self._write(f"Path: {db_path}")
        try:
            if os.path.exists(db_path):
                db_size = os.path.getsize(db_path)
                self._write(f"Size: {db_size / (1024 * 1024):.2f} MB")
            else:
                self._write("Size: (database file not found)")
        except Exception as e:
            self._write(f"Size: (unavailable - {e})")

        try:
            conn = get_connection()
            try:
                mode = conn.execute("PRAGMA journal_mode").fetchone()
                if mode:
                    self._write(f"Journal mode: {str(mode[0]).upper()}")
                tables = conn.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type = ?",
                    ("table",),
                ).fetchone()
                self._write(f"Tables: {tables[0] if tables else 0}")
            finally:
                try:
                    conn.close()
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)
        except Exception as e:
            logger.error(f"Report: could not read database info: {e}")
            self._write(f"Database stats: (unavailable - {e})")

        self._write()

        # --- Backups section ---
        self._write("BACKUPS")
        self._write("-" * 60)
        backup_dir = config.get("backup_directory", "")
        self._write(f"Backup directory: {backup_dir or '(not configured)'}")

        try:
            if backup_dir and os.path.isdir(backup_dir):
                backups = [
                    f for f in os.listdir(backup_dir)
                    if f.endswith(".db") and os.path.isfile(os.path.join(backup_dir, f))
                ]
                backups.sort(reverse=True)

                if backups:
                    total_size = 0
                    self._write(f"Backup count: {len(backups)}")
                    self._write()
                    for name in backups:
                        path = os.path.join(backup_dir, name)
                        size = os.path.getsize(path)
                        total_size += size
                        mtime = datetime.datetime.fromtimestamp(
                            os.path.getmtime(path)
                        ).strftime("%Y-%m-%d %H:%M:%S")
                        self._write(f"  {name}")
                        self._write(f"      {size / (1024 * 1024):.2f} MB   |   {mtime}")
                    self._write()
                    self._write(f"Total backup size: {total_size / (1024 * 1024):.2f} MB")
                else:
                    self._write("No backup files (*.db) found in the backup directory.")
            else:
                self._write("Backup directory does not exist or is not configured.")
        except Exception as e:
            logger.error(f"Report: could not read backup directory: {e}")
            self._write(f"Backups: (unavailable - {e})")

        self.output.see("1.0")

    def save_report(self):
        """Save the current report text to a file."""
        file_path = filedialog.asksaveasfilename(
            title=_t('gui.shell.database.backup_gui_parts.reportgeneratordialog.dialogs.save_report', default="Save Report"),
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            parent=self.dialog,
        )
        if not file_path:
            return
        try:
            with open(file_path, "w", encoding="utf-8") as fh:
                fh.write(self.output.get("1.0", "end"))
            messagebox.showinfo(_t('gui.shell.database.backup_gui_parts.reportgeneratordialog.dialogs.saved', default="Saved"), f"Report saved to:\n{file_path}", parent=self.dialog)
        except Exception as e:
            messagebox.showerror(_t('gui.shell.database.backup_gui_parts.reportgeneratordialog.dialogs.error', default="Error"), f"Failed to save report: {e}", parent=self.dialog)
