# dialogs/database_info.py
# Dialog for displaying database information.

from education_system.university_system.modules.domain.health.gui.health_portal.medical_accommodation._common import (
    tk, ttk, ScrolledText, os, datetime,
    CLI_AVAILABLE, get_connection, logger,
)


class DatabaseInfoDialog:
    """Dialog for database information"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Database Information")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)

        self.create_widgets()
        self.load_info()

    def create_widgets(self):
        """Create info widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self.info_text = ScrolledText(main_frame, width=60, height=20)
        self.info_text.pack(fill=tk.BOTH, expand=True)

        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)

    def load_info(self):
        """Load database information"""
        if not CLI_AVAILABLE:
            self.info_text.insert(tk.END, "CLI module not available")
            return

        try:
            from education_system.university_system.core import paths
            db_path = str(paths.DEFAULT_DB_PATH)

            info_text = "DATABASE INFORMATION\n"
            info_text += "=" * 50 + "\n\n"

            # Database file info
            if os.path.exists(db_path):
                stat = os.stat(db_path)
                info_text += f"Database File: {db_path}\n"
                info_text += f"File Size: {stat.st_size:,} bytes\n"
                info_text += f"Last Modified: {datetime.fromtimestamp(stat.st_mtime)}\n\n"

            # Table information
            with get_connection() as conn:
                cursor = conn.cursor()

                # Get table names
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]

                info_text += f"Tables: {len(tables)}\n\n"

                for table in tables:
                    from education_system.university_system.core.sql_safety import validate_table_name
                    validated_table = validate_table_name(table, conn=conn)
                    cursor.execute("SELECT COUNT(*) FROM [" + validated_table + "]")
                    count = cursor.fetchone()[0]
                    info_text += f"{table}: {count:,} records\n"

                info_text += "\n"

                # Schema information
                for table in tables:
                    validated_table = validate_table_name(table, conn=conn)
                    cursor.execute("PRAGMA table_info([" + validated_table + "])")
                    columns = cursor.fetchall()

                    info_text += f"\n{table.upper()} TABLE SCHEMA:\n"
                    info_text += "-" * 30 + "\n"

                    for col in columns:
                        info_text += f"  {col[1]} ({col[2]})\n"

            self.info_text.insert(tk.END, info_text)

        except Exception as e:
            self.info_text.insert(tk.END, f"Error loading database info: {str(e)}")
