"""
Academic Misconduct Frame

A tk.Frame wrapper that embeds the Academic Misconduct Panel into any
education system's sidebar navigation. Compatible with all 4 systems.
"""

import tkinter as tk
from tkinter import ttk, messagebox


class MisconductFrame(tk.Frame):
    """Frame that launches the Academic Misconduct Panel.

    Accepts the standard constructor: (parent, db_path=..., auth=..., system_key=...).
    system_key should be one of: 'university', 'college', 'secondary', 'primary', or None for superadmin.
    """

    def __init__(self, parent, db_path=None, auth=None, system_key=None, **kwargs):
        super().__init__(parent, bg="#f5f6fa", **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._system_key = system_key
        self._panel = None
        self._build_ui()

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg="#2c3e50", height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="Academic Misconduct", font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=15, pady=10)

        # Content
        content = tk.Frame(self, bg="#f5f6fa")
        content.pack(fill="both", expand=True, padx=20, pady=20)

        tk.Label(content, text="Academic Misconduct Management",
                 font=("Helvetica", 16, "bold"), bg="#f5f6fa").pack(pady=(0, 10))

        desc = (
            "Manage academic misconduct cases including:\n\n"
            "  - Case filing and tracking\n"
            "  - Evidence management with chain-of-custody\n"
            "  - SHA-256 file integrity verification\n"
            "  - Hearing scheduling\n"
            "  - Panel decisions and rulings\n"
            "  - Student notifications\n"
            "  - Analytics and reporting\n"
            "  - Evidence tagging and search"
        )
        tk.Label(content, text=desc, font=("Helvetica", 11),
                 bg="#f5f6fa", justify="left", anchor="w").pack(fill="x", pady=(0, 20))

        tk.Button(content, text="Open Misconduct Panel",
                  font=("Helvetica", 12, "bold"),
                  bg="#e74c3c", fg="white", activebackground="#c0392b",
                  activeforeground="white", relief="flat", cursor="hand2",
                  padx=20, pady=10,
                  command=self._open_panel).pack()

        # Quick stats frame
        self._stats_frame = ttk.LabelFrame(content, text="Quick Stats", padding="10")
        self._stats_frame.pack(fill="x", pady=(20, 0))
        self._load_stats()

    def _load_stats(self):
        """Load and display quick case stats."""
        for w in self._stats_frame.winfo_children():
            w.destroy()

        try:
            import sqlite3
            from education_system.shared.academic_misconduct._imports import DEFAULT_DB_PATH
            db = str(self._db_path or DEFAULT_DB_PATH)

            conn = sqlite3.connect(db)
            try:
                cursor = conn.cursor()

                # Build system_key filter using parameterized queries
                if self._system_key:
                    params = (self._system_key,)
                    q_total = "SELECT COUNT(*) FROM academic_misconduct_cases WHERE system_key = ?"
                    q_active = "SELECT COUNT(*) FROM academic_misconduct_cases WHERE status='Under Review' AND system_key = ?"
                    q_pending = "SELECT COUNT(*) FROM academic_misconduct_cases WHERE hearing_date IS NOT NULL AND ruling IS NULL AND system_key = ?"
                else:
                    params = ()
                    q_total = "SELECT COUNT(*) FROM academic_misconduct_cases"
                    q_active = "SELECT COUNT(*) FROM academic_misconduct_cases WHERE status='Under Review'"
                    q_pending = "SELECT COUNT(*) FROM academic_misconduct_cases WHERE hearing_date IS NOT NULL AND ruling IS NULL"

                try:
                    cursor.execute(q_total, params)
                    total = cursor.fetchone()[0]
                except Exception:
                    total = 0

                try:
                    cursor.execute(q_active, params)
                    active = cursor.fetchone()[0]
                except Exception:
                    active = 0

                try:
                    cursor.execute(q_pending, params)
                    pending = cursor.fetchone()[0]
                except Exception:
                    pending = 0
            finally:
                conn.close()

            stats = [
                ("Total Cases", str(total)),
                ("Under Review", str(active)),
                ("Pending Hearings", str(pending)),
            ]
            for i, (label, value) in enumerate(stats):
                ttk.Label(self._stats_frame, text=label,
                          font=("Helvetica", 10)).grid(row=0, column=i * 2, padx=(10, 5))
                ttk.Label(self._stats_frame, text=value,
                          font=("Helvetica", 14, "bold")).grid(row=0, column=i * 2 + 1, padx=(0, 20))

        except Exception:
            ttk.Label(self._stats_frame,
                      text="No misconduct data yet. Open the panel to get started.").pack()

    def _open_panel(self):
        """Launch the full misconduct panel in a Toplevel window."""
        try:
            from education_system.shared.academic_misconduct.database import init_misconduct_tables
            from education_system.shared.academic_misconduct.academic_misconduct_gui import AcademicMisconductPanel

            top = tk.Toplevel(self.winfo_toplevel())
            init_misconduct_tables(self._db_path)
            AcademicMisconductPanel(top, auth=self._auth, system_key=self._system_key)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open misconduct panel:\n{e}")
