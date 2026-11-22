"""Exam marking and module results: Grade Tracking's QA screen.

The rules live in ``university/application`` (exam_marking, module_results,
classification); this screen collects input and shows results, on Grade
Tracking's own connection so it shares the app's transactions.
"""
import logging

logger = logging.getLogger(__name__)

import tkinter as tk
from tkinter import ttk, simpledialog

from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking._dialogs import messagebox
from education_system.systems.university.application.assessment import classification
from education_system.systems.university.application.exams import marking as exam_marking
from education_system.systems.university.application.assessment import module_results
from education_system.systems.university.application.exams.marking import ExamMarkingError

_TABS = ("Settings", "Absences", "Moderation", "Release", "Resits", "Module Results",
         "Classification", "Change Log")


def _tree(parent, columns, widths, height=12):
    frame = ttk.Frame(parent)
    frame.pack(fill='both', expand=True)
    tree = ttk.Treeview(frame, columns=[c for c, _ in columns], show='headings', height=height)
    for (key, heading), width in zip(columns, widths):
        tree.heading(key, text=heading)
        tree.column(key, width=width, anchor='w')
    bar = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    bar.pack(side='right', fill='y')
    tree.pack(side='left', fill='both', expand=True)
    return tree


def _fmt(value, suffix=""):
    if value is None or value == "":
        return "—"
    if isinstance(value, float):
        return f"{value:.1f}{suffix}"
    return f"{value}{suffix}"


class ExamQAManager:
    """Exam/test marking control, module results and classification."""

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.auth = app.auth
        self._assessments = {}

    @property
    def conn(self):
        return self.app.conn

    def _user(self):
        user = getattr(self.auth, 'current_user', None) or {}
        return user.get('username') or str(user.get('id') or '')

    def _is_staff(self):
        user = getattr(self.auth, 'current_user', None) or {}
        return str(user.get('role', '')).lower() in {'admin', 'staff', 'instructor', 'faculty'}

    def _run(self, action, success=None, commit=True):
        """Run a rule; commit on success, roll back and explain on refusal."""
        try:
            result = action()
            if commit:
                self.conn.commit()
        except (ExamMarkingError, ValueError) as e:
            self.conn.rollback()
            messagebox.showwarning("Exam marking", str(e))
            return None
        except Exception as e:
            self.conn.rollback()
            logger.exception("Exam QA action failed")
            messagebox.showerror("Exam marking", f"Failed: {e}")
            return None
        if success:
            messagebox.showinfo("Exam marking", success(result) if callable(success) else success)
        return result if result is not None else True

    def _aid(self):
        aid = self._assessments.get(self.assessment_var.get())
        if not aid:
            messagebox.showwarning("Exam marking", "Choose an exam or test first.")
        return aid

    # ── screen ──────────────────────────────────────────────────────────

    def create_exam_qa_content(self):
        parent = self.app.layout.content_frame
        for child in parent.winfo_children():
            child.destroy()
        if not self._is_staff():
            ttk.Label(parent, text="Exam marking is for staff.").pack(pady=20)
            return
        ttk.Label(parent, text="Exam Marking & Module Results", font=("Arial", 14, "bold")).pack(anchor='w', pady=(0, 8))
        picker = ttk.Frame(parent)
        picker.pack(fill='x', pady=(0, 8))
        ttk.Label(picker, text="Exam / test:").pack(side='left')
        self.assessment_var = tk.StringVar()
        self._combo = ttk.Combobox(picker, textvariable=self.assessment_var, width=70, state='readonly')
        self._combo.pack(side='left', padx=6)
        self._combo.bind('<<ComboboxSelected>>', lambda e: self._refresh_assessment_tabs())
        ttk.Button(picker, text="Refresh", command=self._load_assessments).pack(side='left')

        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill='both', expand=True)
        self._build_settings()
        self._build_absences()
        self._build_moderation()
        self._build_release()
        self._build_resits()
        self._build_results()
        self._build_classification()
        self._build_change_log()
        self._load_assessments()

    def _load_assessments(self):
        try:
            rows = self.conn.execute(
                "SELECT assessment_id, module_code, assessment_name, assessment_type, due_date "
                "FROM assessments WHERE COALESCE(status, 'Active') <> 'Archived' "
                "ORDER BY module_code, due_date").fetchall()
        except Exception as e:
            messagebox.showerror("Exam marking", f"Could not load assessments: {e}")
            rows = []
        self._assessments = {f"#{r[0]}  {r[1]} — {r[2]} ({r[3]}, {str(r[4] or '')[:10]})": r[0] for r in rows}
        self._combo['values'] = list(self._assessments)
        if self.assessment_var.get() not in self._assessments and self._assessments:
            self.assessment_var.set(next(iter(self._assessments)))
        self._refresh_assessment_tabs()
        self._load_results()
        self._load_change_log()

    def _refresh_assessment_tabs(self):
        aid = self._assessments.get(self.assessment_var.get())
        if not aid:
            return
        for loader in (self._load_settings, self._load_absences, self._load_moderation,
                       self._load_release, self._load_resits):
            try:
                loader(aid)
            except Exception:
                logger.debug("Exam QA tab load failed", exc_info=True)

    # ── settings ────────────────────────────────────────────────────────

    def _build_settings(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Settings")
        self.anon_var = tk.BooleanVar()
        self.mod_var = tk.BooleanVar()
        self.sample_var = tk.StringVar(value="10")
        ttk.Checkbutton(tab, text="Anonymous marking (candidate numbers until release)",
                        variable=self.anon_var).pack(anchor='w', pady=2)
        ttk.Checkbutton(tab, text="Moderation required before release",
                        variable=self.mod_var).pack(anchor='w', pady=2)
        row = ttk.Frame(tab)
        row.pack(anchor='w', pady=2)
        ttk.Label(row, text="Moderation sample %:").pack(side='left')
        ttk.Entry(row, textvariable=self.sample_var, width=8).pack(side='left', padx=6)
        self.settings_info = tk.StringVar()
        ttk.Label(tab, textvariable=self.settings_info, foreground='#1565c0').pack(anchor='w', pady=8)
        ttk.Button(tab, text="Save Settings", command=self._save_settings).pack(anchor='w')

    def _load_settings(self, aid):
        a = exam_marking.get_settings(self.conn, aid)
        self.anon_var.set(bool(a.get('anonymous_marking')))
        self.mod_var.set(bool(a.get('moderation_required')))
        self.sample_var.set(f"{a.get('moderation_sample_pct') or 10:g}")
        parts = [f"Weight {a.get('weight') or 0:g}% of {a['module_code']}",
                 f"max {a.get('max_points'):g} points"]
        if a.get('reassessment_of'):
            parts.append(f"resit ({a.get('reassessment_type')}) of #{a['reassessment_of']}")
        parts.append(f"released {a['marks_released_at'][:16]}" if a.get('marks_released_at') else "not released")
        self.settings_info.set("   ".join(parts))

    def _save_settings(self):
        aid = self._aid()
        if aid and self._run(lambda: exam_marking.update_settings(
                self.conn, aid, anonymous_marking=self.anon_var.get(),
                moderation_required=self.mod_var.get(), moderation_sample_pct=self.sample_var.get()),
                "Settings saved."):
            self._refresh_assessment_tabs()

    # ── absences ────────────────────────────────────────────────────────

    def _build_absences(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Absences")
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Button(bar, text="Mark Absent (ABS)", command=lambda: self._absence("ABS")).pack(side='left')
        ttk.Button(bar, text="Absent with Mitigation (ABS-MC)",
                   command=lambda: self._absence("ABS-MC")).pack(side='left', padx=6)
        ttk.Label(tab, text="Enrolled students with no mark yet. ABS counts as 0 and leads to a "
                            "referral; ABS-MC leaves the component outstanding for a deferred sitting.",
                  foreground='#666', wraplength=900).pack(anchor='w', pady=(0, 6))
        self.absence_tree = _tree(tab, [("student", "Student"), ("label", "Shown to markers as")],
                                  [160, 300])

    def _load_absences(self, aid):
        tree = self.absence_tree
        tree.delete(*tree.get_children())
        for sid in exam_marking.unmarked_students(self.conn, aid):
            tree.insert('', 'end', iid=str(sid), values=(sid, exam_marking.marker_label(self.conn, aid, sid, sid)))
        self.conn.commit()  # candidate numbers allocated while listing

    def _absence(self, code):
        aid = self._aid()
        sel = self.absence_tree.selection()
        if not aid or not sel:
            messagebox.showwarning("Exam marking", "Select one or more students.")
            return
        note = simpledialog.askstring("Absence", "Note (optional):", parent=self.root)
        if self._run(lambda: [exam_marking.record_absence(self.conn, aid, sid, code, self._user(), note)
                              for sid in sel], lambda r: f"{len(r)} absence(s) recorded."):
            self._refresh_assessment_tabs()

    # ── moderation ──────────────────────────────────────────────────────

    def _build_moderation(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Moderation")
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(0, 6))
        for label, cmd in (("Draw Sample", self._draw), ("Second Mark", self._second),
                           ("Agree Mark", self._agree), ("Complete Moderation", self._complete)):
            ttk.Button(bar, text=label, command=cmd).pack(side='left', padx=(0, 6))
        self.mod_info = tk.StringVar()
        ttk.Label(tab, textvariable=self.mod_info, foreground='#1565c0').pack(anchor='w', pady=(0, 6))
        self.mod_tree = _tree(tab, [("id", "#"), ("student", "Script"), ("first", "First %"),
                                    ("second", "Second %"), ("diff", "Diff"), ("agreed", "Agreed %"),
                                    ("status", "Status")], [50, 200, 80, 80, 70, 80, 110])

    def _load_moderation(self, aid):
        tree = self.mod_tree
        tree.delete(*tree.get_children())
        rows = exam_marking.moderation_rows(self.conn, aid)
        for r in rows:
            tree.insert('', 'end', iid=str(r['id']), values=(
                r['id'], r['label'], _fmt(r['first_mark']), _fmt(r['second_mark']),
                _fmt(r['difference']), _fmt(r['agreed_mark']), r['status']))
        a = exam_marking.get_settings(self.conn, aid)
        self.mod_info.set(f"Moderation {'required' if a.get('moderation_required') else 'optional'}; "
                          f"status {a.get('moderation_status') or 'not_started'}; {len(rows)} sampled.")
        self.conn.commit()

    def _selected_mod(self):
        sel = self.mod_tree.selection()
        if not sel:
            messagebox.showwarning("Exam marking", "Select a sampled script.")
            return None
        return int(sel[0])

    def _draw(self):
        aid = self._aid()
        if aid and self._run(lambda: exam_marking.draw_sample(self.conn, aid),
                             lambda n: f"{n} script(s) in the sample."):
            self._load_moderation(aid)

    def _second(self):
        mid = self._selected_mod()
        if mid is None:
            return
        mark = simpledialog.askfloat("Second mark", "Second marker's mark (%):", minvalue=0, maxvalue=100,
                                     parent=self.root)
        if mark is not None and self._run(lambda: exam_marking.record_second_mark(self.conn, mid, mark, self._user())):
            self._load_moderation(self._aid())

    def _agree(self):
        mid = self._selected_mod()
        if mid is None:
            return
        mark = simpledialog.askfloat("Agreed mark", "Agreed mark (%):", minvalue=0, maxvalue=100, parent=self.root)
        if mark is None:
            return
        note = simpledialog.askstring("Agreed mark", "How was it resolved?", parent=self.root)
        if self._run(lambda: exam_marking.agree_mark(self.conn, mid, mark, self._user(), note)):
            self._load_moderation(self._aid())

    def _complete(self):
        aid = self._aid()
        if aid and self._run(lambda: exam_marking.complete_moderation(self.conn, aid),
                             "Moderation complete."):
            self._refresh_assessment_tabs()

    # ── release ─────────────────────────────────────────────────────────

    def _build_release(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Release")
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Button(bar, text="Release Marks", command=lambda: self._release(False)).pack(side='left')
        ttk.Button(bar, text="Release Anyway (outstanding marks)",
                   command=lambda: self._release(True)).pack(side='left', padx=6)
        self.release_text = tk.Text(tab, height=12, wrap='word')
        self.release_text.pack(fill='both', expand=True)

    def _load_release(self, aid):
        a = exam_marking.get_settings(self.conn, aid)
        blockers = exam_marking.release_blockers(self.conn, aid)
        text = self.release_text
        text.configure(state='normal')
        text.delete('1.0', 'end')
        if a.get('marks_released_at'):
            text.insert('end', f"Released {a['marks_released_at']} by {a.get('marks_released_by') or '—'}.")
        elif blockers:
            text.insert('end', "Not ready:\n\n" + "\n".join(f"  • {b}" for b in blockers))
        else:
            text.insert('end', "Ready to release. Students are emailed and can then see their marks.")
        text.insert('end', "\n\nMarks are hidden from students and parents until released. "
                           "Module results stay provisional until an exam board ratifies them.")
        text.configure(state='disabled')

    def _release(self, force):
        aid = self._aid()
        if not aid or not messagebox.askyesno("Release marks", "Release every mark on this assessment?"):
            return
        rows = self._run(lambda: exam_marking.release(self.conn, aid, self._user(), force=force))
        if rows:
            sent = self._email_release(aid, rows)
            messagebox.showinfo("Exam marking", f"Released {len(rows)} mark(s); {sent} email(s) sent.")
            self._refresh_assessment_tabs()

    def _email_release(self, aid, rows):
        try:
            from education_system.systems.university.infrastructure.email.email_service import send_email
        except Exception:
            return 0
        a = exam_marking.get_settings(self.conn, aid)
        sent = 0
        for r in rows:
            if not r.get('email_address'):
                continue
            result = r['result_code'] or (f"{r['score'] / (a['max_points'] or 100) * 100:.1f}%"
                                          if r['score'] is not None else "—")
            try:
                send_email(recipient_email=r['email_address'],
                           subject=f"Marks released: {a['assessment_name']}",
                           body=(f"Dear {r.get('first_name') or 'student'},\n\nYour mark for "
                                 f"{a['assessment_name']} ({a['module_code']}) has been released: {result}.\n\n"
                                 "Module results are provisional until confirmed by the exam board."))
                sent += 1
            except Exception:
                logger.debug("Release email failed", exc_info=True)
        return sent

    # ── resits ──────────────────────────────────────────────────────────

    def _build_resits(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Resits")
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="Resit date (YYYY-MM-DD HH:MM):").pack(side='left')
        self.resit_due = tk.StringVar()
        ttk.Entry(bar, textvariable=self.resit_due, width=18).pack(side='left', padx=6)
        ttk.Button(bar, text="Toggle Referral/Deferral", command=self._toggle).pack(side='left', padx=6)
        ttk.Button(bar, text="Create Resit for Selected", command=self._create_resit).pack(side='left')
        ttk.Label(tab, text=f"Referral marks are capped at {classification.PASS_MARK:g}%; deferrals "
                            "(accepted mitigation) are uncapped. The resit mark replaces the first attempt.",
                  foreground='#666').pack(anchor='w', pady=(0, 6))
        self.cand_tree = _tree(tab, [("student", "Student"), ("mark", "Mark"), ("reason", "Reason"),
                                     ("type", "Attempt")], [140, 80, 160, 110], height=8)
        ttk.Label(tab, text="Resits already set:").pack(anchor='w', pady=(8, 4))
        self.resit_tree = _tree(tab, [("student", "Student"), ("type", "Attempt"), ("name", "Sitting"),
                                      ("due", "Date"), ("mark", "Mark")], [140, 90, 260, 140, 80], height=6)
        self._claims = {}

    def _load_resits(self, aid):
        for tree in (self.cand_tree, self.resit_tree):
            tree.delete(*tree.get_children())
        try:
            candidates = exam_marking.resit_candidates(self.conn, aid)
        except ExamMarkingError:
            candidates = []
        self._claims = {c['student_id']: c.get('mc_claim_id') for c in candidates}
        for c in candidates:
            self.cand_tree.insert('', 'end', iid=str(c['student_id']), values=(
                c['student_id'], _fmt(c['mark'], '%'), c['reason'], c['suggested_type']))
        for r in exam_marking.resits(self.conn, aid):
            self.resit_tree.insert('', 'end', values=(r['student_id'], r['attempt_type'], r['name'],
                                                      str(r['due_date'] or '')[:16], _fmt(r['mark'])))

    def _toggle(self):
        for iid in self.cand_tree.selection():
            values = list(self.cand_tree.item(iid)['values'])
            values[3] = 'deferral' if values[3] == 'referral' else 'referral'
            self.cand_tree.item(iid, values=values)

    def _create_resit(self):
        aid = self._aid()
        sel = self.cand_tree.selection()
        if not aid or not sel:
            messagebox.showwarning("Exam marking", "Select the students to resit.")
            return
        students = [{"student_id": iid, "attempt_type": self.cand_tree.item(iid)['values'][3],
                     "mc_claim_id": self._claims.get(iid)} for iid in sel]
        if self._run(lambda: exam_marking.create_resit(self.conn, aid, students, self.resit_due.get().strip(),
                                                       self._user()),
                     lambda new_id: f"Resit created as assessment #{new_id}."):
            self._load_assessments()

    # ── module results ──────────────────────────────────────────────────

    def _build_results(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Module Results")
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="Module code:").pack(side='left')
        self.module_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self.module_var, width=14).pack(side='left', padx=6)
        ttk.Button(bar, text="Show", command=self._load_results).pack(side='left')
        ttk.Button(bar, text="Recalculate Module", command=self._recalculate).pack(side='left', padx=6)
        self.weight_info = tk.StringVar()
        ttk.Label(tab, textvariable=self.weight_info, foreground='#b26a00', wraplength=950).pack(anchor='w', pady=(0, 6))
        self.results_tree = _tree(tab, [("student", "Student"), ("module", "Module"), ("score", "Mark %"),
                                        ("band", "Band"), ("outcome", "Outcome"), ("status", "Status"),
                                        ("credits", "Credits"), ("complete", "Complete")],
                                  [110, 100, 70, 70, 100, 110, 70, 80])

    def _load_results(self):
        tree = self.results_tree
        tree.delete(*tree.get_children())
        code = (self.module_var.get() or '').strip()
        a = exam_marking.get_settings(self.conn, self._assessments[self.assessment_var.get()]) \
            if not code and self.assessment_var.get() in self._assessments else None
        if a:
            code = a['module_code']
            self.module_var.set(code)
        if not code:
            return
        rows = self.conn.execute(
            "SELECT student_id, module_code, final_score, final_grade, outcome, status, "
            "       credits_awarded, is_complete, locked FROM module_grades WHERE module_code = ? "
            "ORDER BY student_id", (code,)).fetchall()
        for r in rows:
            status = (r[5] or 'provisional') + (' (locked)' if r[8] else '')
            tree.insert('', 'end', values=(r[0], r[1], _fmt(r[2]), r[3] or '—', r[4] or '—', status,
                                           _fmt(r[6]), 'yes' if r[7] else 'no'))
        report = module_results.weight_report(self.conn, code)
        if report:
            w = report[0]
            text = (f"Weightings: assignments {w['assignments_pct']:g}% + exams/tests {w['exams_pct']:g}% "
                    f"= {w['total_pct']:g}%.")
            if w['state'] == 'check':
                text += " These should total 100%."
            if w['unweighted'] and w['total_pct']:
                text += f" Not counted (no weighting): {', '.join(w['unweighted'])}."
            if w['state'] == 'equal weights':
                text += " No weightings set: every component counts equally."
            if w['mirrors']:
                text += f" Counted once (assignment and assessment share a name): {', '.join(w['mirrors'])}."
            self.weight_info.set(text)

    def _recalculate(self):
        code = (self.module_var.get() or '').strip()
        if not code:
            messagebox.showwarning("Exam marking", "Enter a module code.")
            return
        if self._run(lambda: module_results.recompute_module(self.conn, code),
                     lambda n: f"{n} result(s) recalculated. Ratified results are not changed."):
            self._load_results()

    # ── classification ──────────────────────────────────────────────────

    def _build_classification(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Classification")
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="Student ID:").pack(side='left')
        self.class_student = tk.StringVar()
        ttk.Entry(bar, textvariable=self.class_student, width=14).pack(side='left', padx=6)
        ttk.Button(bar, text="Calculate", command=self._classify).pack(side='left')
        self.class_text = tk.Text(tab, height=16, wrap='word')
        self.class_text.pack(fill='both', expand=True)

    def _classify(self):
        sid = self.class_student.get().strip()
        if not sid:
            return
        result = classification.degree_classification(self.conn, sid)
        lines = [f"Student {sid}", ""]
        for level, v in sorted(result['levels'].items()):
            lines.append(f"  Level {level}: average {v['average']:.1f}% over {v['modules']} module(s), "
                         f"{v['credits']:g} credits")
        lines.append("")
        if result['classification']:
            lines.append(f"Proposed classification: {result['classification']} ({result['average']:.2f}%)")
            if result['borderline']:
                lines.append(f"Borderline: within {classification.BORDERLINE_MARGIN:g}% of the next boundary.")
        if result['note']:
            lines.append(result['note'])
        comp = classification.compensation_candidates(self.conn, sid)
        if comp:
            lines.append("\nFails a board could compensate: " +
                         ", ".join(f"{c['module_code']} ({c['mark']:.1f}%)" for c in comp))
        lines.append(f"\nLevel 6 counts {classification.LEVEL_WEIGHTS[6]:g}x Level 5; modules are "
                     "credit-weighted (equally where credits are not recorded).")
        self.class_text.delete('1.0', 'end')
        self.class_text.insert('end', "\n".join(lines))

    # ── change log ──────────────────────────────────────────────────────

    def _build_change_log(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Change Log")
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Label(bar, text="Student ID:").pack(side='left')
        self.log_student = tk.StringVar()
        ttk.Entry(bar, textvariable=self.log_student, width=14).pack(side='left', padx=6)
        ttk.Button(bar, text="Filter", command=self._load_change_log).pack(side='left')
        self.log_tree = _tree(tab, [("when", "When"), ("student", "Student"), ("module", "Module"),
                                    ("old", "Old"), ("new", "New"), ("reason", "Reason"), ("by", "By")],
                              [140, 100, 90, 70, 70, 330, 90])

    def _load_change_log(self):
        tree = self.log_tree
        tree.delete(*tree.get_children())
        try:
            rows = exam_marking.change_log(self.conn, self.log_student.get().strip() or None)
        except Exception:
            logger.debug("Change log unavailable", exc_info=True)
            return
        for r in rows:
            tree.insert('', 'end', values=(str(r['changed_at'])[:16], r['student_id'] or '—',
                                           r['module_code'] or '—', r['old_value'] or '—',
                                           r['new_value'] or '—', r['reason'], r['changed_by'] or '—'))
