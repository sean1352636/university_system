"""Results-entry tab for the Exam Scheduling System.

Lists scheduled exams with status (graded / pending) and lets an admin
double-click to open a per-student marks-entry dialog. Saving writes
through to ``student_grades`` and ``student_modules`` via
:func:`results.apply_exam_results`.
"""

from __future__ import annotations

import json
import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import List

from education_system.post_18.university_system.modules.domain.academics.gui.exam_management.models import Exam
from education_system.post_18.university_system.modules.domain.academics.gui.exam_management import results as results_service

logger = logging.getLogger(__name__)


def _enrolled_ids(raw) -> List[str]:
    """Tolerate either a JSON string or an already-decoded list."""
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    try:
        return [str(x) for x in json.loads(raw)]
    except Exception:
        return []


class ResultsTabMixin:
    """Tab providing per-exam results entry and writeback."""

    def create_results_tab(self):
        self.results_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.results_tab, text="📝 Results")

        wrap = ttk.Frame(self.results_tab, padding=10)
        wrap.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            wrap,
            text="Double-click an exam to enter marks. Saved results "
                 "propagate to student_grades, student_modules, and the "
                 "grade audit log.",
            wraplength=900, justify="left",
        ).pack(anchor="w", pady=(0, 8))

        cols = ("id", "module", "name", "date", "status", "graded")
        self.results_tree = ttk.Treeview(
            wrap, columns=cols, show="headings", height=15,
        )
        for c, w, h in [
            ("id",     50,  "ID"),
            ("module", 100, "Module"),
            ("name",   220, "Name"),
            ("date",   100, "Date"),
            ("status", 90,  "Status"),
            ("graded", 90,  "Graded"),
        ]:
            self.results_tree.heading(c, text=h)
            self.results_tree.column(c, width=w, anchor="w")
        self.results_tree.tag_configure("graded",  foreground="#27ae60")
        self.results_tree.tag_configure("partial", foreground="#e67e22")
        self.results_tree.tag_configure("pending", foreground="#7f8c8d")
        self.results_tree.pack(fill=tk.BOTH, expand=True)

        self.results_tree.bind("<Double-1>", self._on_results_row_open)

        btns = ttk.Frame(wrap)
        btns.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btns, text="🔄 Refresh",
                   command=self.refresh_results_list).pack(side=tk.LEFT)
        ttk.Button(btns, text="📝 Enter / edit marks",
                   command=self._open_results_dialog_for_selected
                   ).pack(side=tk.LEFT, padx=8)

        self.refresh_results_list()

    def refresh_results_list(self):
        for iid in self.results_tree.get_children():
            self.results_tree.delete(iid)

        today = _date.today().isoformat()
        for exam in sorted(self.data_manager.exams,
                           key=lambda e: (e.date, e.start_time),
                           reverse=True):
            existing = results_service.get_existing_results(exam)
            roster = _enrolled_ids(exam.enrolled_student_ids)
            graded_count = sum(1 for sid in roster if sid in existing)
            roster_size = len(roster) or exam.students_enrolled or 0

            if roster_size == 0:
                graded_label, tag = "—", "pending"
            elif graded_count == 0:
                graded_label, tag = f"0/{roster_size}", "pending"
            elif graded_count < roster_size:
                graded_label, tag = f"{graded_count}/{roster_size}", "partial"
            else:
                graded_label, tag = f"{graded_count}/{roster_size}", "graded"

            status = "Past" if exam.date < today else "Upcoming"
            self.results_tree.insert(
                "", tk.END,
                values=(exam.id, exam.module_code, exam.module_name,
                        exam.date, status, graded_label),
                tags=(tag,),
            )

    def _selected_exam(self) -> Exam | None:
        sel = self.results_tree.selection()
        if not sel:
            return None
        exam_id = self.results_tree.item(sel[0])["values"][0]
        return next((e for e in self.data_manager.exams if e.id == exam_id),
                    None)

    def _on_results_row_open(self, _event):
        self._open_results_dialog_for_selected()

    def _open_results_dialog_for_selected(self):
        exam = self._selected_exam()
        if not exam:
            messagebox.showinfo("Results", "Select an exam first.")
            return
        ResultsEntryDialog(self.root, exam, self.data_manager,
                           on_saved=self.refresh_results_list)


class ResultsEntryDialog(tk.Toplevel):
    """Per-student marks-entry dialog for a single exam."""

    def __init__(self, parent, exam: Exam, data_manager, on_saved=None):
        super().__init__(parent)
        self.title(f"Enter marks — {exam.module_code} ({exam.date})")
        self.geometry("520x520")
        self.transient(parent)
        self.grab_set()

        self._exam = exam
        self._data_manager = data_manager
        self._on_saved = on_saved
        self._entries: dict[str, tk.StringVar] = {}

        students = data_manager.get_enrolled_students(exam.module_code) or []
        existing = results_service.get_existing_results(exam)

        header = ttk.Frame(self, padding=10)
        header.pack(fill=tk.X)
        ttk.Label(
            header,
            text=f"{exam.module_code} — {exam.module_name}\n"
                 f"{exam.date}  {exam.start_time}–{exam.end_time}  "
                 f"in {exam.room}",
            justify="left", font=("Helvetica", 11, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            header,
            text="Enter a percentage (0–100) for each student. Blank "
                 "rows are skipped.",
            foreground="#555",
        ).pack(anchor="w", pady=(4, 0))

        body = ttk.Frame(self, padding=(10, 0, 10, 10))
        body.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(body, borderwidth=0, highlightthickness=0)
        scroll = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        rows = ttk.Frame(canvas)
        rows.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=rows, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Header row
        ttk.Label(rows, text="Student ID", font=("Helvetica", 9, "bold"),
                  width=15, anchor="w").grid(row=0, column=0, padx=4, pady=4)
        ttk.Label(rows, text="Name", font=("Helvetica", 9, "bold"),
                  width=28, anchor="w").grid(row=0, column=1, padx=4, pady=4)
        ttk.Label(rows, text="Mark (%)", font=("Helvetica", 9, "bold"),
                  width=10, anchor="w").grid(row=0, column=2, padx=4, pady=4)

        for i, s in enumerate(students, start=1):
            sid = s.get("student_id")
            var = tk.StringVar(value=(f"{existing[sid]:g}"
                                      if sid in existing else ""))
            self._entries[sid] = var
            ttk.Label(rows, text=sid, anchor="w").grid(
                row=i, column=0, padx=4, pady=2, sticky="w")
            ttk.Label(rows, text=s.get("display_name") or "", anchor="w",
                      width=28).grid(row=i, column=1, padx=4, pady=2,
                                     sticky="w")
            ttk.Entry(rows, textvariable=var, width=10).grid(
                row=i, column=2, padx=4, pady=2, sticky="w")

        if not students:
            ttk.Label(rows, text="No students enrolled in this module.",
                      foreground="#888").grid(row=1, column=0, columnspan=3,
                                              padx=4, pady=12)

        actions = ttk.Frame(self, padding=10)
        actions.pack(fill=tk.X)
        ttk.Button(actions, text="Cancel",
                   command=self.destroy).pack(side=tk.RIGHT, padx=4)
        ttk.Button(actions, text="💾 Save & write back",
                   command=self._save).pack(side=tk.RIGHT)

    def _save(self):
        results: dict[str, float] = {}
        invalid: list[str] = []
        for sid, var in self._entries.items():
            raw = var.get().strip()
            if not raw:
                continue
            try:
                val = float(raw)
            except ValueError:
                invalid.append(sid)
                continue
            if not (0 <= val <= 100):
                invalid.append(sid)
                continue
            results[sid] = val

        if invalid:
            messagebox.showerror(
                "Invalid marks",
                "Some marks aren't valid percentages (0–100):\n"
                + ", ".join(invalid),
                parent=self,
            )
            return

        if not results:
            messagebox.showinfo("Nothing to save",
                                "No marks were entered.", parent=self)
            return

        graded_by = "exam_management"
        try:
            auth = getattr(self.master, "auth", None)
            cu = getattr(auth, "current_user", None)
            if cu and cu.get("username"):
                graded_by = cu["username"]
        except Exception:
            pass

        written, failed = results_service.apply_exam_results(
            self._exam, results, graded_by=graded_by,
        )
        msg = f"Saved {written} result(s)."
        if failed:
            msg += f"\n{failed} row(s) failed — see logs."
        messagebox.showinfo("Results saved", msg, parent=self)

        if callable(self._on_saved):
            try:
                self._on_saved()
            except Exception as exc:
                logger.debug("on_saved callback errored: %s", exc)
        self.destroy()
