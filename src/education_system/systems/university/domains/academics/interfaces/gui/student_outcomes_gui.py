"""Student Learning Outcomes GUI.

Provides a Tkinter frame for students to view their learning outcome
achievements, including summary statistics and a detailed treeview of
each outcome with its current achievement level.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
import logging
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import get_connection, sqlite3

# i18n with fallback
try:
    from education_system.systems.university.infrastructure.i18n import get_text as _t
except ImportError:
    _t = lambda key, **kwargs: key

logger = logging.getLogger(__name__)


class StudentOutcomesGUI:
    """GUI for viewing student learning outcome achievements."""

    def __init__(self, parent_frame, auth_instance=None):
        self.parent = parent_frame
        self.auth = auth_instance
        self.student_id = self._resolve_student_id()
        self.outcomes_data = []

        self._build_ui()
        self.refresh_data()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_student_id(self):
        """Extract student_id from the auth object."""
        if self.auth and getattr(self.auth, "current_user", None):
            user = self.auth.current_user
            sid = user.get("student_id") or user.get("username")
            return sid
        return None

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        """Construct the full interface inside parent_frame."""
        # Title
        title_lbl = ttk.Label(
            self.parent,
            text=_t("Learning Outcomes", default="Learning outcomes"),
            font=("Arial", 16, "bold"),
        )
        title_lbl.pack(pady=(10, 5))

        # --- Summary statistics frame ---
        self.summary_frame = ttk.LabelFrame(
            self.parent, text=_t("Summary", default="Summary"), padding=10
        )
        self.summary_frame.pack(fill=tk.X, padx=10, pady=(5, 10))

        self._stat_labels = {}
        stats_inner = tk.Frame(self.summary_frame)
        stats_inner.pack(fill=tk.X)

        stat_defs = [
            ("total", _t("Total Outcomes", default="Total outcomes"), "#2196F3"),
            ("achieved", _t("Achieved", default="Achieved"), "#4CAF50"),
            ("in_progress", _t("In Progress", default="In progress"), "#FF9800"),
            ("not_started", _t("Not Started", default="Not started"), "#9E9E9E"),
        ]
        for idx, (key, label_text, colour) in enumerate(stat_defs):
            frame = tk.Frame(stats_inner)
            frame.grid(row=0, column=idx, padx=15, pady=5, sticky="n")

            val_lbl = tk.Label(
                frame, text="0", font=("Arial", 20, "bold"), fg=colour
            )
            val_lbl.pack()
            tk.Label(frame, text=label_text, font=("Arial", 10)).pack()
            self._stat_labels[key] = val_lbl

        stats_inner.columnconfigure(list(range(len(stat_defs))), weight=1)

        # --- Treeview ---
        tree_frame = ttk.Frame(self.parent)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))

        columns = (
            "outcome_code",
            "category",
            "description",
            "achievement_level",
            "date_assessed",
        )
        self.tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", height=12
        )

        col_headings = {
            "outcome_code": (_t("Outcome Code", default="Outcome code"), 110),
            "category": (_t("Category", default="Category"), 110),
            "description": (_t("Description", default="Description"), 300),
            "achievement_level": (_t("Achievement Level", default="Achievement level"), 130),
            "date_assessed": (_t("Date Assessed", default="Date assessed"), 120),
        }
        for col, (heading, width) in col_headings.items():
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=width, minwidth=60)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        # --- Buttons ---
        btn_frame = ttk.Frame(self.parent)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(
            btn_frame, text=_t("Refresh", default="Refresh"), command=self.refresh_data
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            btn_frame, text=_t("Export to CSV", default="Export to csv"), command=self._export_csv
        ).pack(side=tk.LEFT, padx=5)

        # Status / message label (used for error states)
        self.status_lbl = ttk.Label(self.parent, text="", foreground="gray")
        self.status_lbl.pack(pady=(0, 5))

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def refresh_data(self):
        """Reload outcome data from the database."""
        self.tree.delete(*self.tree.get_children())
        self.outcomes_data.clear()
        self.status_lbl.config(text="")

        if not self.student_id:
            self.status_lbl.config(text=_t("No student ID available.", default=""))
            self._update_summary(0, 0, 0, 0)
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Fetch student course
            cursor.execute(
                "SELECT first_name, last_name, course FROM students WHERE student_id = ?",
                (self.student_id,),
            )
            student = cursor.fetchone()
            if not student:
                conn.close()
                self.status_lbl.config(text=_t("Student record not found.", default=""))
                self._update_summary(0, 0, 0, 0)
                return

            _first, _last, course = student

            # Join outcomes with results
            cursor.execute(
                """
                SELECT lo.outcome_code, lo.category, lo.description,
                       orr.achievement_level, orr.assessment_date
                FROM learning_outcomes lo
                LEFT JOIN outcome_results orr
                    ON lo.outcome_id = orr.outcome_id AND orr.student_id = ?
                ORDER BY lo.outcome_code
                """,
                (self.student_id,),
            )
            rows = cursor.fetchall()
            conn.close()

            achieved = 0
            in_progress = 0
            not_started = 0

            for row in rows:
                code, category, desc, level, date_assessed = row
                if level is not None:
                    level_display = f"{level:.1f}/5.0" if isinstance(level, (int, float)) else str(level)
                    if isinstance(level, (int, float)) and level >= 3.0:
                        achieved += 1
                    else:
                        in_progress += 1
                else:
                    level_display = _t("Not assessed", default="Not assessed")
                    not_started += 1

                date_display = date_assessed if date_assessed else ""
                record = (code, category, desc, level_display, date_display)
                self.outcomes_data.append(record)
                self.tree.insert("", tk.END, values=record)

            total = len(rows)
            self._update_summary(total, achieved, in_progress, not_started)

        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                self.status_lbl.config(
                    text=_t("Learning outcomes data not available", default="Learning outcomes data not available")
                )
            else:
                logger.exception("Database error loading outcomes")
                self.status_lbl.config(text=_t("Database error occurred.", default=""))
            self._update_summary(0, 0, 0, 0)
        except Exception:
            logger.exception("Unexpected error loading outcomes")
            self.status_lbl.config(text=_t("An error occurred loading data.", default=""))
            self._update_summary(0, 0, 0, 0)

    def _update_summary(self, total, achieved, in_progress, not_started):
        """Refresh the summary stat labels."""
        self._stat_labels["total"].config(text=str(total))
        self._stat_labels["achieved"].config(text=str(achieved))
        self._stat_labels["in_progress"].config(text=str(in_progress))
        self._stat_labels["not_started"].config(text=str(not_started))

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export_csv(self):
        """Export displayed outcomes to a CSV file."""
        if not self.outcomes_data:
            messagebox.showinfo(
                _t("Export", default="Export"), _t("No data to export.", default="")
            )
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title=_t("Export Learning Outcomes", default="Export learning outcomes"),
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow([
                    "Outcome Code", "Category", "Description",
                    "Achievement Level", "Date Assessed",
                ])
                writer.writerows(self.outcomes_data)
            messagebox.showinfo(
                _t("Export", default="Export"), _t("Data exported successfully.", default="")
            )
        except Exception:
            logger.exception("Export failed")
            messagebox.showerror(
                _t("Export Error", default="Export error"), _t("Failed to export data.", default="")
            )
