"""Grade Tracking — Staff/Instructor portal.

A focused grade-entry window for staff and instructors. Unlike the full
admin GradeTrackingApp, this exposes only the flows an instructor needs:
pick a module -> pick an assessment -> view and edit the grade for each
enrolled student. No curve analysis, no predictive analytics, no
database tooling.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from education_system.university_system.infrastructure.database.db import get_connection


_LETTER_CUTOFFS = [
    (93, 'A+'), (90, 'A'), (87, 'A-'),
    (83, 'B+'), (80, 'B'), (77, 'B-'),
    (73, 'C+'), (70, 'C'), (67, 'C-'),
    (63, 'D+'), (60, 'D'), (57, 'D-'),
]


def _percentage_to_letter(pct):
    for cutoff, letter in _LETTER_CUTOFFS:
        if pct >= cutoff:
            return letter
    return 'F'


class GradeTrackingStaffPortal:
    """Simplified grade entry portal for staff/instructors."""

    def __init__(self, parent, auth):
        self.auth = auth

        self.window = tk.Toplevel(parent)
        self.window.title("Grade Tracking — Staff Portal")
        self.window.geometry("1100x720")
        self.window.minsize(900, 600)
        self.window.configure(bg='#f0f0f0')
        try:
            self.window.transient(parent)
        except Exception:
            pass

        self.module_var = tk.StringVar()
        self.assessment_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Select a module to begin.")

        self._modules = []
        self._assessments = []
        self._current_assessment_id = None
        self._current_max_points = 100.0
        self._edits = {}

        self._build_ui()
        self._load_modules()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        header = tk.Frame(self.window, bg='#34495e', height=52)
        header.pack(fill='x')
        header.pack_propagate(False)

        display = ''
        if self.auth and self.auth.current_user:
            display = self.auth.current_user.get('display_name') or \
                      self.auth.current_user.get('username', '')
        tk.Label(header, text=f"Grade Entry — {display}",
                 font=('Arial', 14, 'bold'), bg='#34495e', fg='white'
                 ).pack(side='left', padx=18, pady=12)

        # Filter bar
        bar = ttk.Frame(self.window, padding=(10, 8))
        bar.pack(fill='x')

        ttk.Label(bar, text="Module:").pack(side='left', padx=(0, 4))
        self.module_combo = ttk.Combobox(bar, textvariable=self.module_var,
                                         state='readonly', width=40)
        self.module_combo.pack(side='left', padx=(0, 16))
        self.module_combo.bind('<<ComboboxSelected>>', self._on_module_selected)

        ttk.Label(bar, text="Assessment:").pack(side='left', padx=(0, 4))
        self.assessment_combo = ttk.Combobox(bar, textvariable=self.assessment_var,
                                             state='readonly', width=36)
        self.assessment_combo.pack(side='left', padx=(0, 16))
        self.assessment_combo.bind('<<ComboboxSelected>>', self._on_assessment_selected)

        ttk.Button(bar, text="Refresh", command=self._refresh).pack(side='right')

        # Info strip — shows max points, student count, class average
        info = ttk.Frame(self.window, padding=(12, 0, 12, 6))
        info.pack(fill='x')
        self.info_var = tk.StringVar(value="")
        ttk.Label(info, textvariable=self.info_var,
                  foreground='#2c3e50').pack(side='left')

        # Grade table
        table_frame = ttk.Frame(self.window, padding=(10, 4, 10, 4))
        table_frame.pack(fill='both', expand=True)

        cols = ('student_id', 'name', 'course', 'score', 'percent', 'letter')
        self.tree = ttk.Treeview(table_frame, columns=cols, show='headings',
                                 selectmode='browse')
        headings = [
            ('student_id', 'Student ID', 110),
            ('name', 'Name', 220),
            ('course', 'Course', 140),
            ('score', 'Score', 100),
            ('percent', '%', 80),
            ('letter', 'Letter', 80),
        ]
        for key, title, width in headings:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor='w' if key in ('name', 'course') else 'center')

        vsb = ttk.Scrollbar(table_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        self.tree.bind('<Double-1>', self._edit_selected)
        self.tree.tag_configure('edited', background='#fff4c2')

        # Action buttons
        actions = ttk.Frame(self.window, padding=(10, 6))
        actions.pack(fill='x')

        ttk.Button(actions, text="Edit Grade…",
                   command=self._edit_selected).pack(side='left', padx=(0, 6))
        ttk.Button(actions, text="Save Changes",
                   command=self._save_edits).pack(side='left', padx=(0, 6))
        ttk.Button(actions, text="Discard Changes",
                   command=self._discard_edits).pack(side='left', padx=(0, 6))
        ttk.Button(actions, text="Close",
                   command=self.window.destroy).pack(side='right')

        status = ttk.Frame(self.window, relief='sunken')
        status.pack(fill='x', side='bottom')
        ttk.Label(status, textvariable=self.status_var,
                  anchor='w', padding=(8, 2)).pack(fill='x')

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_modules(self):
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT module_code, module_name FROM modules "
                    "ORDER BY module_code"
                )
                self._modules = [(r[0], r[1]) for r in cur.fetchall()]
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load modules: {e}",
                                 parent=self.window)
            self._modules = []

        values = [f"{code} — {name}" for code, name in self._modules]
        self.module_combo['values'] = values
        if values:
            self.status_var.set(f"{len(values)} module(s) available.")
        else:
            self.status_var.set("No modules found.")

    def _on_module_selected(self, _event=None):
        idx = self.module_combo.current()
        if idx < 0:
            return
        module_code = self._modules[idx][0]
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT assessment_id, assessment_name, max_points, weight "
                    "FROM assessments WHERE module_code = ? ORDER BY assessment_id",
                    (module_code,)
                )
                self._assessments = [
                    (r[0], r[1], r[2], r[3]) for r in cur.fetchall()
                ]
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load assessments: {e}",
                                 parent=self.window)
            self._assessments = []

        values = [f"{a[1]} (max {a[2]:g}, w{a[3]:g}%)" for a in self._assessments]
        self.assessment_combo['values'] = values
        self.assessment_var.set('')
        self._clear_table()
        if values:
            self.status_var.set(f"{len(values)} assessment(s) in {module_code}.")
        else:
            self.status_var.set(f"No assessments for {module_code}.")

    def _on_assessment_selected(self, _event=None):
        idx = self.assessment_combo.current()
        if idx < 0:
            return
        assessment_id, name, max_points, _weight = self._assessments[idx]
        self._current_assessment_id = assessment_id
        self._current_max_points = float(max_points) if max_points else 100.0
        self._edits.clear()
        self._load_grades()

    def _load_grades(self):
        self._clear_table()
        module_idx = self.module_combo.current()
        if module_idx < 0 or self._current_assessment_id is None:
            return
        module_code = self._modules[module_idx][0]

        try:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT s.student_id, s.first_name, s.last_name, s.course,
                           g.score, g.letter_grade
                    FROM students s
                    JOIN student_modules sm ON sm.student_id = s.student_id
                    LEFT JOIN grades g ON g.student_id = s.student_id
                                      AND g.assessment_id = ?
                    WHERE sm.module_code = ?
                    ORDER BY s.last_name, s.first_name
                    """,
                    (self._current_assessment_id, module_code)
                )
                rows = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Database Error",
                                 f"Could not load grades: {e}",
                                 parent=self.window)
            return

        total_score = 0.0
        scored = 0
        for student_id, first, last, course, score, letter in rows:
            name = f"{first or ''} {last or ''}".strip()
            if score is not None:
                pct = (score / self._current_max_points * 100.0) if self._current_max_points else 0
                self.tree.insert('', 'end', iid=student_id, values=(
                    student_id, name, course or '',
                    f"{score:g}", f"{pct:.1f}%", letter or _percentage_to_letter(pct)
                ))
                total_score += pct
                scored += 1
            else:
                self.tree.insert('', 'end', iid=student_id, values=(
                    student_id, name, course or '', '—', '—', '—'
                ))

        avg = (total_score / scored) if scored else 0
        self.info_var.set(
            f"Max: {self._current_max_points:g}   |   "
            f"Students enrolled: {len(rows)}   |   "
            f"Graded: {scored}/{len(rows)}   |   "
            f"Class avg (graded): {avg:.1f}%"
        )
        self.status_var.set("Double-click a row or press Edit Grade… to change a score.")

    def _clear_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

    # ------------------------------------------------------------------
    # Edits
    # ------------------------------------------------------------------

    def _edit_selected(self, _event=None):
        if self._current_assessment_id is None:
            messagebox.showinfo("No Assessment",
                                "Pick a module and assessment first.",
                                parent=self.window)
            return
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select a student first.",
                                parent=self.window)
            return
        student_id = sel[0]
        current = self.tree.item(student_id, 'values')
        EditGradeDialog(self.window, student_id, current[1],
                        self._current_max_points, current[3],
                        on_save=lambda score, comment: self._apply_edit(
                            student_id, score, comment))

    def _apply_edit(self, student_id, score, comment):
        pct = (score / self._current_max_points * 100.0) if self._current_max_points else 0
        letter = _percentage_to_letter(pct)
        name_row = self.tree.item(student_id, 'values')
        self.tree.item(student_id, values=(
            name_row[0], name_row[1], name_row[2],
            f"{score:g}", f"{pct:.1f}%", letter
        ), tags=('edited',))
        self._edits[student_id] = {
            'score': score, 'letter': letter, 'comment': comment
        }
        self.status_var.set(
            f"{len(self._edits)} unsaved change(s). Click Save Changes to commit."
        )

    def _discard_edits(self):
        if not self._edits:
            return
        self._edits.clear()
        self._load_grades()
        self.status_var.set("Unsaved changes discarded.")

    def _save_edits(self):
        if not self._edits:
            messagebox.showinfo("Nothing to Save",
                                "No grade changes to save.",
                                parent=self.window)
            return
        if self._current_assessment_id is None:
            return

        today = datetime.now().strftime('%Y-%m-%d')
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                for student_id, edit in self._edits.items():
                    cur.execute(
                        "SELECT grade_id FROM grades "
                        "WHERE student_id = ? AND assessment_id = ?",
                        (student_id, self._current_assessment_id)
                    )
                    row = cur.fetchone()
                    if row:
                        cur.execute(
                            "UPDATE grades SET score = ?, letter_grade = ?, "
                            "submission_date = ?, comments = ? "
                            "WHERE grade_id = ?",
                            (edit['score'], edit['letter'], today,
                             edit['comment'], row[0])
                        )
                    else:
                        cur.execute(
                            "INSERT INTO grades (student_id, assessment_id, "
                            "score, letter_grade, submission_date, comments) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            (student_id, self._current_assessment_id,
                             edit['score'], edit['letter'], today, edit['comment'])
                        )
                conn.commit()
        except Exception as e:
            messagebox.showerror("Save Failed",
                                 f"Could not save grades: {e}",
                                 parent=self.window)
            return

        count = len(self._edits)
        self._edits.clear()
        self._load_grades()
        self.status_var.set(f"Saved {count} grade change(s).")

    def _refresh(self):
        if self._current_assessment_id is not None:
            self._edits.clear()
            self._load_grades()
        else:
            self._load_modules()


class EditGradeDialog:
    """Modal dialog for editing a single student's score + comment."""

    def __init__(self, parent, student_id, student_name, max_points,
                 current_score, on_save):
        self.on_save = on_save
        self.max_points = max_points

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Edit Grade — {student_name}")
        self.dialog.geometry("420x240")
        self.dialog.transient(parent)
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        frame = ttk.Frame(self.dialog, padding=14)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text=f"Student: {student_id} — {student_name}",
                  font=('Arial', 10, 'bold')).grid(row=0, column=0, columnspan=2,
                                                    sticky='w', pady=(0, 8))
        ttk.Label(frame, text=f"Max points: {max_points:g}").grid(
            row=1, column=0, columnspan=2, sticky='w', pady=(0, 8))

        ttk.Label(frame, text="Score:").grid(row=2, column=0, sticky='w', pady=4)
        self.score_var = tk.StringVar(
            value='' if current_score in ('—', '', None) else str(current_score)
        )
        ttk.Entry(frame, textvariable=self.score_var, width=18).grid(
            row=2, column=1, sticky='w', pady=4)

        ttk.Label(frame, text="Comment:").grid(row=3, column=0, sticky='nw', pady=4)
        self.comment_text = tk.Text(frame, width=34, height=4, wrap='word')
        self.comment_text.grid(row=3, column=1, sticky='w', pady=4)

        btns = ttk.Frame(frame)
        btns.grid(row=4, column=0, columnspan=2, pady=(10, 0), sticky='e')
        ttk.Button(btns, text="Save",
                   command=self._save).pack(side='left', padx=4)
        ttk.Button(btns, text="Cancel",
                   command=self.dialog.destroy).pack(side='left', padx=4)

    def _save(self):
        raw = self.score_var.get().strip()
        try:
            score = float(raw)
        except ValueError:
            messagebox.showerror("Invalid Score",
                                 "Score must be a number.",
                                 parent=self.dialog)
            return
        if score < 0 or score > self.max_points:
            if not messagebox.askyesno(
                    "Score Out of Range",
                    f"Score {score:g} is outside 0–{self.max_points:g}. Save anyway?",
                    parent=self.dialog):
                return
        comment = self.comment_text.get('1.0', 'end').strip()
        self.on_save(score, comment)
        self.dialog.destroy()


def launch_grade_tracking_staff_portal(parent, auth):
    """Module-level entry point."""
    return GradeTrackingStaffPortal(parent, auth)
