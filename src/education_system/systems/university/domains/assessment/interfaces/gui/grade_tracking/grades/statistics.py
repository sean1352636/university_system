"""Extracted GradeManager behaviour."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t
from . import *
from .scale import GRADE_SYSTEMS, letter_to_gpa, letter_to_percentage, percentage_to_letter
from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking._dialogs import make_toplevel

class GradeStatisticsMixin:
    def calculate_all_gpas(self):
        """Calculate GPAs for all students.

        Delegates per-student GPA math to
        ``grading.grade_calculation.gpa.calculate_student_gpa`` so the
        formula stays in one place; this method only handles the loop
        and the result-dialog rendering.
        """
        try:
            from education_system.systems.university.domains.assessment.domain.grading.grade_calculation.gpa import (
                calculate_student_gpa,
            )
            from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking.integrations import (
                push_grade_kpi,
                notify_aid_of_gpa,
            )

            cursor = self.get_safe_cursor()
            cursor.execute("SELECT student_id, first_name, last_name FROM students")
            students = cursor.fetchall()

            results = []
            updated_count = 0
            gpa_values: list[float] = []

            for student in students:
                student_id = student[0]
                name = f"{student[1]} {student[2]}"

                gpa, credits, _ = calculate_student_gpa(cursor, student_id)
                if gpa is None:
                    results.append((student_id, name, None, 0))
                    continue

                results.append((student_id, name, gpa, credits))
                updated_count += 1
                gpa_values.append(gpa)

                # Cross-domain side-effect: tag the student's aid record(s)
                # with the latest GPA so financial_aid reviewers see the
                # number that's gating their scholarship eligibility.
                try:
                    notify_aid_of_gpa(student_id=student_id, gpa=gpa)
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)

            self.safe_commit()

            # Best-effort KPI push — silent when no matching KPI exists
            if gpa_values:
                try:
                    push_grade_kpi(
                        "Average GPA", sum(gpa_values) / len(gpa_values),
                    )
                    pass_rate = (
                        sum(1 for g in gpa_values if g >= 2.0) / len(gpa_values) * 100.0
                    )
                    push_grade_kpi("Pass Rate %", pass_rate)
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)

            self._show_gpa_results(results, gpa_values, updated_count)

        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.grades.statistics.dialogs.database_error', default="Database Error"), f"Error calculating GPAs: {e}")

    # ------------------------------------------------------------------
    # Results presentation
    # ------------------------------------------------------------------

    #: GPA bands, worst first. Used for the row colour and the summary
    #: counts, so a cohort's shape is visible without reading every row.
    _GPA_BANDS = (
        (2.0, "at_risk", "#c0392b", "Below 2.0"),
        (3.0, "watch", "#e67e22", "2.0 – 2.99"),
        (3.7, "good", "#16a085", "3.0 – 3.69"),
        (4.1, "excellent", "#27ae60", "3.7 and above"),
    )

    @classmethod
    def _gpa_band(cls, gpa):
        for ceiling, tag, colour, label in cls._GPA_BANDS:
            if gpa < ceiling:
                return tag, colour, label
        return cls._GPA_BANDS[-1][1:]

    def _show_gpa_results(self, results, gpa_values, updated_count):
        """Render the GPA run as headline figures and a sortable table.

        This was one line of text per student in a read-only text box:
        unsortable, and on a real cohort the students who actually need
        attention were indistinguishable from a few hundred who don't.
        """
        dialog = make_toplevel(self.root)
        dialog.title(_t('gui.academics.grade_tracking.grades.statistics.windows.gpa_calculation_results', default="GPA Calculation Results"))
        dialog.geometry("760x600")
        dialog.minsize(620, 420)

        no_grades = [r for r in results if r[2] is None]
        average = sum(gpa_values) / len(gpa_values) if gpa_values else 0.0
        passing = sum(1 for g in gpa_values if g >= 2.0)

        header = tk.Frame(dialog, bg="#2c3e50")
        header.pack(fill="x")
        tk.Label(header, text="GPA Calculation Results", font=("Segoe UI", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(anchor="w", padx=16, pady=(12, 0))
        tk.Label(header, text=f"{updated_count} student(s) calculated · "
                              f"{len(no_grades)} with no grades yet",
                 font=("Segoe UI", 9), bg="#2c3e50", fg="#bdc3c7").pack(
                     anchor="w", padx=16, pady=(2, 12))

        cards = tk.Frame(dialog, bg="#eef1f4")
        cards.pack(fill="x", padx=10, pady=10)
        figures = [
            (f"{average:.2f}", "Average GPA", "#3498db"),
            (f"{passing}/{len(gpa_values)}" if gpa_values else "0/0",
             "At or above 2.0", "#27ae60"),
            (str(sum(1 for g in gpa_values if g < 2.0)), "Below 2.0", "#c0392b"),
            (str(len(no_grades)), "No grades yet", "#7f8c8d"),
        ]
        for col, (value, label, colour) in enumerate(figures):
            cards.columnconfigure(col, weight=1, uniform="gpa")
            cell = tk.Frame(cards, bg="white", highlightbackground="#e5e7eb",
                            highlightthickness=1)
            cell.grid(row=0, column=col, sticky="ew", padx=4)
            tk.Label(cell, text=value, font=("Segoe UI", 17, "bold"),
                     bg="white", fg=colour).pack(pady=(10, 0))
            tk.Label(cell, text=label, font=("Segoe UI", 9),
                     bg="white", fg="#6b7280").pack(pady=(0, 10))

        # Action bar before the table: packed against the bottom, a table
        # that fills and expands first would leave it no height.
        actions = ttk.Frame(dialog, padding=(10, 6))
        actions.pack(side="bottom", fill="x")

        table = ttk.Frame(dialog)
        table.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        columns = ("Student ID", "Name", "GPA", "Modules", "Standing")
        tree = ttk.Treeview(table, columns=columns, show="headings")
        for col, width, anchor in (("Student ID", 110, "w"), ("Name", 220, "w"),
                                   ("GPA", 80, "e"), ("Modules", 90, "e"),
                                   ("Standing", 140, "w")):
            tree.heading(col, text=col,
                         command=lambda c=col: self._sort_gpa_tree(tree, c, False))
            tree.column(col, width=width, anchor=anchor)
        for _ceiling, tag, colour, _label in self._GPA_BANDS:
            tree.tag_configure(tag, foreground=colour)
        tree.tag_configure("none", foreground="#7f8c8d")
        tree.tag_configure("odd", background="#f7f9fb")

        # Lowest GPA first: the students needing attention are the reason
        # anyone runs this, so they should not be buried alphabetically.
        ordered = sorted(results, key=lambda r: (r[2] is not None, r[2] or 0))
        for i, (student_id, name, gpa, credits) in enumerate(ordered):
            stripe = ("odd",) if i % 2 else ()
            if gpa is None:
                tree.insert("", "end", tags=stripe + ("none",),
                            values=(student_id, name, "—", "—", "No grades yet"))
            else:
                tag, _colour, label = self._gpa_band(gpa)
                tree.insert("", "end", tags=stripe + (tag,),
                            values=(student_id, name, f"{gpa:.2f}", credits, label))

        scroll = ttk.Scrollbar(table, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        ttk.Button(actions, text=_t('gui.academics.grade_tracking.grades.statistics.buttons.export_csv', default="Export CSV"),
                   command=lambda: self._export_gpa_csv(ordered, dialog)).pack(side="left")
        ttk.Button(actions, text=_t('gui.academics.grade_tracking.grades.statistics.buttons.close', default="Close"),
                   command=dialog.destroy).pack(side="right")

    @staticmethod
    def _sort_gpa_tree(tree, col, reverse):
        """Sort by a column, keeping GPA and Modules numeric."""
        def key(item):
            raw = tree.set(item, col)
            if raw in ("—", ""):
                # Students with no grades sort last either way rather than
                # jumping to the top as "0".
                return (1, 0.0) if not reverse else (1, 0.0)
            try:
                return (0, float(raw))
            except ValueError:
                return (0, raw.lower())
        items = sorted(tree.get_children(""), key=key, reverse=reverse)
        for index, item in enumerate(items):
            tree.move(item, "", index)
        tree.heading(col, command=lambda: GradeStatisticsMixin._sort_gpa_tree(
            tree, col, not reverse))

    def _export_gpa_csv(self, ordered, parent):
        """Save the calculated GPAs as CSV."""
        from tkinter import filedialog
        import csv
        path = filedialog.asksaveasfilename(
            parent=parent, defaultextension=".csv",
            initialfile=f"student_gpas_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["Student ID", "Name", "GPA", "Modules", "Standing"])
                for student_id, name, gpa, credits in ordered:
                    if gpa is None:
                        writer.writerow([student_id, name, "", "", "No grades yet"])
                    else:
                        writer.writerow([student_id, name, f"{gpa:.2f}", credits,
                                         self._gpa_band(gpa)[2]])
            messagebox.showinfo(_t('gui.academics.grade_tracking.grades.statistics.dialogs.saved', default="Saved"),
                                f"Saved to:\n{path}", parent=parent)
        except OSError as exc:
            messagebox.showerror(_t('gui.academics.grade_tracking.grades.statistics.dialogs.save_failed', default="Save failed"),
                                 str(exc), parent=parent)
