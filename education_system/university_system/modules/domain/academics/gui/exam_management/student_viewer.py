"""Read-only student exam viewer for the Exam Scheduling System."""

import logging
import tkinter as tk
from tkinter import ttk
from datetime import datetime

from education_system.university_system.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

try:
    from education_system.university_system.core.i18n import get_text as _
except ImportError:
    def _(key, **kwargs):
        return key


class StudentExamViewer(tk.Toplevel):
    """Read-only Toplevel window showing exams for an enrolled student."""

    def __init__(self, parent, *, auth=None):
        super().__init__(parent)
        self.auth = auth
        self.title("My Exam Schedule")
        self.geometry("900x500")
        self.minsize(700, 350)
        self.transient(parent)
        self._student_id = self._resolve_student_id()
        self._build_ui()
        self._load_exams()

    def _resolve_student_id(self):
        """Extract the student_id from the auth object."""
        if self.auth is None:
            return None
        try:
            current_user = getattr(self.auth, "current_user", None)
            if isinstance(current_user, dict):
                return current_user.get("student_id") or current_user.get("id")
        except Exception:
            pass
        return None

    # ---- UI ----

    def _build_ui(self):
        """Assemble the Toplevel layout."""
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            main_frame, text="My Exam Schedule", font=("Helvetica", 14, "bold")
        ).pack(anchor=tk.W, pady=(0, 8))

        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("module", "exam_name", "date", "time", "room", "duration", "mc")
        self.tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", selectmode="browse"
        )
        for col, text, width in (
            ("module", "Module", 100),
            ("exam_name", "Exam Name", 200),
            ("date", "Date", 100),
            ("time", "Time", 120),
            ("room", "Room", 120),
            ("duration", "Duration", 90),
            ("mc", "MC", 100),
        ):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, minwidth=60)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_frame, text="Refresh", command=self._load_exams).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Close", command=self.destroy).pack(side=tk.RIGHT)

    # ---- Data loading ----

    @staticmethod
    def _compute_duration(start_time, end_time):
        """Return a human-readable duration string (e.g. '2h 00m')."""
        try:
            fmt = "%H:%M"
            start = datetime.strptime(start_time, fmt)
            end = datetime.strptime(end_time, fmt)
            total_minutes = int((end - start).total_seconds() // 60)
            hours, minutes = divmod(total_minutes, 60)
            return f"{hours}h {minutes:02d}m"
        except (ValueError, TypeError):
            return ""

    def _load_exams(self):
        """Query the database for the student's enrolled exams and populate the tree."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not self._student_id:
            return

        try:
            with get_connection() as conn:
                cursor = conn.execute(
                    "SELECT module_code FROM student_modules WHERE student_id = ?",
                    (self._student_id,),
                )
                module_codes = [row[0] for row in cursor.fetchall()]

            if not module_codes:
                return

            # Build per-module MC outcome lookup (deferral / capped resit /
            # uncapped resit) so each exam row can flag whether the student
            # is sitting it under MC arrangements.
            mc_by_module = {}
            try:
                from education_system.university_system.modules.domain.academics.mitigating_circumstances.integration import (
                    deferred_assessments_for_student,
                )
                for entry in deferred_assessments_for_student(self._student_id):
                    mc_by_module.setdefault(entry.get('module_code'), []).append(entry)
            except Exception:
                pass

            with get_connection() as conn:
                placeholders = ",".join("?" for _ in module_codes)
                cursor = conn.execute(
                    f"SELECT module_code, module_name, date, start_time, end_time, room "
                    f"FROM exams WHERE module_code IN ({placeholders}) "
                    f"ORDER BY date, start_time",
                    module_codes,
                )
                for row in cursor.fetchall():
                    code, name, date, start, end, room = row
                    mc_label = ""
                    entries = mc_by_module.get(code) or []
                    if entries:
                        outcomes = {e.get('outcome') for e in entries if e.get('outcome')}
                        if 'deferral_granted' in outcomes:
                            mc_label = "Deferred"
                        elif 'uncapped_resit' in outcomes:
                            mc_label = "Resit (uncapped)"
                        elif 'capped_resit' in outcomes:
                            mc_label = "Resit (capped)"
                    self.tree.insert("", tk.END, values=(
                        code,
                        name or "",
                        date or "",
                        f"{start} - {end}",
                        room or "",
                        self._compute_duration(start, end),
                        mc_label,
                    ))
        except Exception as exc:
            logger.warning("Failed to load student exams: %s", exc)
