"""Exam Office tab: timetable publication, invigilation, incidents, papers, absentees.

The rules are in ``university/application`` (exam_timetable, exam_office,
exam_results); this tab collects input and shows results.
"""
import logging
import tkinter as tk
from contextlib import closing
from tkinter import ttk, messagebox, simpledialog

from education_system.systems.university.application.exams import (
    office as exam_office,
    results as exam_results,
    timetable as exam_timetable,
)
from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


def _tree(parent, columns, widths, height=10):
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


class ExamOfficeTabMixin:
    """Running the exam period: publish the timetable, staff it, log what happens."""

    def _office_user(self):
        user = getattr(getattr(self, 'auth', None), 'current_user', None) or {}
        return user.get('username') or 'exam_office'

    def _office_run(self, action, success=None):
        """Run a rule on a fresh connection; commit, or explain a refusal."""
        try:
            with closing(get_connection()) as conn:
                result = action(conn)
                conn.commit()
        except ValueError as e:
            messagebox.showwarning("Exam Office", str(e), parent=self.root)
            return None
        except Exception as e:
            logger.exception("Exam office action failed")
            messagebox.showerror("Exam Office", f"Failed: {e}", parent=self.root)
            return None
        if success:
            messagebox.showinfo("Exam Office", success(result) if callable(success) else success,
                                parent=self.root)
        return result if result is not None else True

    def _exam_choices(self):
        return {f"#{e.id} {e.module_code} {e.date} {e.start_time}"
                f"{' [draft]' if getattr(e, 'status', 'published') == 'draft' else ''}": e.id
                for e in sorted(self.data_manager.exams, key=lambda e: (e.date, e.start_time))}

    def _picker(self, parent, on_change):
        row = ttk.Frame(parent)
        row.pack(fill='x', pady=(0, 6))
        ttk.Label(row, text="Exam:").pack(side='left')
        var = tk.StringVar()
        combo = ttk.Combobox(row, textvariable=var, width=55, state='readonly')
        combo.pack(side='left', padx=6)
        combo['values'] = list(self._exam_choices())
        combo.bind('<<ComboboxSelected>>', lambda e: on_change())
        return var, combo

    def _picked(self, var):
        exam_id = self._exam_choices().get(var.get())
        if not exam_id:
            messagebox.showwarning("Exam Office", "Choose an exam first.", parent=self.root)
        return exam_id

    def create_exam_office_tab(self):
        self.office_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.office_tab, text="Exam Office")
        inner = ttk.Notebook(self.office_tab)
        inner.pack(fill='both', expand=True, padx=6, pady=6)
        for label, builder in (("Timetable", self._office_timetable), ("Invigilation", self._office_invigilation),
                               ("Incidents", self._office_incidents), ("Papers", self._office_papers),
                               ("Absentees", self._office_absentees)):
            frame = ttk.Frame(inner, padding=8)
            inner.add(frame, text=label)
            try:
                builder(frame)
            except Exception:
                logger.exception("Exam Office %s tab failed", label)
                ttk.Label(frame, text=f"{label} could not be loaded.").pack()

    # ── timetable ───────────────────────────────────────────────────────

    def _office_timetable(self, tab):
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Button(bar, text="Publish Selected", command=lambda: self._publish(False)).pack(side='left')
        ttk.Button(bar, text="Publish Anyway (override clashes)",
                   command=lambda: self._publish(True)).pack(side='left', padx=6)
        ttk.Button(bar, text="Back to Draft", command=self._unpublish).pack(side='left')
        ttk.Button(bar, text="Refresh", command=self._load_timetable).pack(side='left', padx=6)
        ttk.Label(tab, text="Drafts are invisible to students. Publishing checks room double-bookings and "
                            "students with two exams at once, then notifies students and adds the "
                            f"sitting to the calendar. More than {exam_timetable.MAX_EXAMS_PER_DAY} exams "
                            "in a day is flagged as a heavy day.",
                  foreground='#555', wraplength=950).pack(anchor='w', pady=(0, 6))
        self.tt_tree = _tree(tab, [("id", "#"), ("exam", "Sitting"), ("status", "Status"), ("issues", "Problems")],
                             [50, 320, 90, 480], height=9)
        ttk.Label(tab, text="Student clashes across the timetable:").pack(anchor='w', pady=(8, 4))
        self.clash_tree = _tree(tab, [("student", "Student"), ("kind", "Problem"), ("exams", "Sittings")],
                                [110, 110, 700], height=8)
        self._load_timetable()

    def _load_timetable(self):
        for tree in (self.tt_tree, self.clash_tree):
            tree.delete(*tree.get_children())
        try:
            with closing(get_connection()) as conn:
                for exam in sorted(self.data_manager.exams, key=lambda e: (e.date, e.start_time)):
                    status = getattr(exam, 'status', 'published')
                    issues = exam_timetable.publish_blockers(conn, exam.id) if status == 'draft' else []
                    self.tt_tree.insert('', 'end', iid=str(exam.id), values=(
                        exam.id, f"{exam.module_code} {exam.date} {exam.start_time}-{exam.end_time} {exam.room}",
                        status, "; ".join(issues) or "—"))
                for c in exam_timetable.student_clashes(conn):
                    self.clash_tree.insert('', 'end', values=(
                        c['student_id'], "same time" if c['kind'] == 'overlap' else "heavy day",
                        " | ".join(c['exams'])))
        except Exception:
            logger.exception("Timetable load failed")

    def _publish(self, force):
        ids = [int(i) for i in self.tt_tree.selection()]
        if not ids:
            messagebox.showwarning("Exam Office", "Select the draft sittings to publish.", parent=self.root)
            return
        try:
            outcome = self.data_manager.publish_exams(ids, self._office_user(), force=force)
        except Exception as e:
            messagebox.showerror("Exam Office", f"Publish failed: {e}", parent=self.root)
            return
        msg = f"Published {len(outcome['published'])} sitting(s); {outcome['notified']} notification(s) sent."
        if outcome['blocked']:
            msg += "\n\nKept in draft:\n" + "\n".join(
                f"  #{eid}: {'; '.join(r)}" for eid, r in outcome['blocked'].items())
        messagebox.showinfo("Exam Office", msg, parent=self.root)
        self._load_timetable()

    def _unpublish(self):
        for iid in self.tt_tree.selection():
            self.data_manager.unpublish_exam(int(iid))
        self._load_timetable()

    # ── invigilation ────────────────────────────────────────────────────

    def _office_invigilation(self, tab):
        self.inv_exam, combo = self._picker(tab, self._load_invigilators)
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Button(bar, text="Add Invigilator", command=self._add_invigilator).pack(side='left')
        ttk.Button(bar, text="Remove Selected", command=self._remove_invigilator).pack(side='left', padx=6)
        self.inv_tree = _tree(tab, [("staff", "Staff ID"), ("name", "Name"), ("role", "Role"), ("room", "Room")],
                              [110, 220, 100, 160], height=6)
        ttk.Label(tab, text=f"Staffing (one invigilator per {exam_timetable.INVIGILATION_RATIO} candidates, "
                            "plus a lead):").pack(anchor='w', pady=(8, 4))
        self.staff_tree = _tree(tab, [("exam", "Sitting"), ("cand", "Candidates"), ("inv", "Invigilators"),
                                      ("need", "Needed"), ("issues", "Problems")], [320, 90, 90, 80, 330], height=8)
        self._load_invigilators()

    def _load_invigilators(self):
        for tree in (self.inv_tree, self.staff_tree):
            tree.delete(*tree.get_children())
        exam_id = self._exam_choices().get(self.inv_exam.get())
        with closing(get_connection()) as conn:
            if exam_id:
                for s in exam_timetable.invigilators(conn, exam_id):
                    self.inv_tree.insert('', 'end', iid=s['staff_id'],
                                         values=(s['staff_id'], s['staff_name'] or '', s['role'], s['room'] or ''))
            for r in exam_timetable.staffing_report(conn):
                self.staff_tree.insert('', 'end', values=(r['label'], r['candidates'], r['invigilators'],
                                                          r['needed'], "; ".join(r['issues']) or "ok"))

    def _add_invigilator(self):
        exam_id = self._picked(self.inv_exam)
        if not exam_id:
            return
        staff_id = simpledialog.askstring("Invigilator", "Staff ID:", parent=self.root)
        if not staff_id:
            return
        name = simpledialog.askstring("Invigilator", "Name:", parent=self.root) or None
        role = simpledialog.askstring("Invigilator", "Role (lead / invigilator / support):",
                                      initialvalue="invigilator", parent=self.root) or "invigilator"
        if self._office_run(lambda c: exam_timetable.assign_invigilator(c, exam_id, staff_id.strip(), name,
                                                                        role.strip().lower())):
            self._load_invigilators()

    def _remove_invigilator(self):
        exam_id = self._picked(self.inv_exam)
        if exam_id and self._office_run(
                lambda c: [exam_timetable.remove_invigilator(c, exam_id, s) for s in self.inv_tree.selection()]):
            self._load_invigilators()

    # ── incidents ───────────────────────────────────────────────────────

    def _office_incidents(self, tab):
        self.inc_exam, combo = self._picker(tab, self._load_incidents)
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Button(bar, text="Log Incident", command=self._log_incident).pack(side='left')
        ttk.Button(bar, text="Refer to Misconduct Case", command=self._refer).pack(side='left', padx=6)
        self.inc_tree = _tree(tab, [("id", "#"), ("when", "When"), ("type", "Type"), ("student", "Student"),
                                    ("desc", "What happened"), ("case", "Case")],
                              [40, 130, 150, 90, 380, 120], height=12)
        self._load_incidents()

    def _load_incidents(self):
        self.inc_tree.delete(*self.inc_tree.get_children())
        exam_id = self._exam_choices().get(self.inc_exam.get())
        with closing(get_connection()) as conn:
            for i in exam_office.incidents(conn, exam_id):
                self.inc_tree.insert('', 'end', iid=str(i['id']), values=(
                    i['id'], str(i['occurred_at'])[:16], exam_office.INCIDENT_TYPES.get(i['incident_type'], i['incident_type']),
                    i['student_id'] or '—', i['description'], i['case_id'] or '—'))

    def _log_incident(self):
        exam_id = self._picked(self.inc_exam)
        if not exam_id:
            return
        kinds = list(exam_office.INCIDENT_TYPES)
        kind = simpledialog.askstring(
            "Incident", "Type — one of:\n" + ", ".join(kinds), initialvalue="late_arrival", parent=self.root)
        if not kind:
            return
        student = simpledialog.askstring("Incident", "Student ID (blank if none):", parent=self.root) or None
        minutes = None
        if kind.strip() == 'late_arrival':
            minutes = simpledialog.askinteger("Incident", "Minutes late:", parent=self.root)
        desc = simpledialog.askstring("Incident", "What happened?", parent=self.root)
        action = simpledialog.askstring("Incident", "Action taken (optional):", parent=self.root) or None
        if self._office_run(lambda c: exam_office.log_incident(
                c, exam_id, kind.strip(), desc or "", student_id=student, minutes_late=minutes,
                action_taken=action, reported_by=self._office_user()), "Incident logged."):
            self._load_incidents()

    def _refer(self):
        sel = self.inc_tree.selection()
        if not sel:
            messagebox.showwarning("Exam Office", "Select a suspected-malpractice incident.", parent=self.root)
            return
        outbox = []
        if self._office_run(lambda c: exam_office.refer_to_misconduct(c, int(sel[0]), self._office_user(),
                                                                      outbox),
                            lambda case: f"Academic integrity case {case} opened."):
            if outbox:
                from education_system.systems.university.infrastructure.ui.record_screens import (
                    send_emails,
                )
                send_emails(outbox)
            self._load_incidents()

    # ── papers ──────────────────────────────────────────────────────────

    def _office_papers(self, tab):
        self.paper_exam, combo = self._picker(tab, self._load_paper)
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(0, 6))
        ttk.Button(bar, text="Advance to Next Stage", command=self._advance_paper).pack(side='left')
        ttk.Button(bar, text="Send Back to Draft", command=lambda: self._advance_paper('draft')).pack(side='left', padx=6)
        self.paper_info = tk.StringVar()
        ttk.Label(tab, textvariable=self.paper_info, foreground='#1565c0', wraplength=950).pack(anchor='w', pady=(0, 6))
        ttk.Label(tab, text=f"Stages: {' → '.join(exam_office.PAPER_STATES)}. Papers not printed for upcoming "
                            "sittings:").pack(anchor='w')
        self.paper_tree = _tree(tab, [("exam", "#"), ("module", "Module"), ("date", "Exam date"), ("status", "Stage"),
                                      ("deadline", "Print by"), ("flag", "Problem")],
                                [50, 110, 100, 150, 100, 300], height=10)
        self._load_paper()

    def _load_paper(self):
        self.paper_tree.delete(*self.paper_tree.get_children())
        exam_id = self._exam_choices().get(self.paper_exam.get())
        with closing(get_connection()) as conn:
            if exam_id:
                p = exam_office.paper(conn, exam_id, create=False)
                if p:
                    self.paper_info.set(
                        f"Stage: {p['status']}   setter: {p['setter'] or '—'}   internal check: "
                        f"{p['internal_checker'] or '—'}   external examiner: {p['external_examiner'] or '—'}   "
                        f"print by: {p['print_deadline'] or '—'}   secured at: {p['secured_location'] or '—'}")
                else:
                    self.paper_info.set("No paper record yet (draft).")
            for r in exam_office.paper_deadline_report(conn):
                flags = []
                if r['overdue']:
                    flags.append("print deadline passed")
                if r['needs_external']:
                    flags.append("no external approval")
                self.paper_tree.insert('', 'end', values=(r['exam_id'], r['module_code'], r['date'], r['status'],
                                                          r['print_deadline'] or '—', "; ".join(flags) or "—"))

    def _advance_paper(self, to_state=None):
        exam_id = self._picked(self.paper_exam)
        if not exam_id:
            return
        with closing(get_connection()) as conn:
            current = exam_office.paper(conn, exam_id)
            conn.commit()
        states = exam_office.PAPER_STATES
        if to_state is None:
            index = states.index(current['status'])
            if index + 1 >= len(states):
                messagebox.showinfo("Exam Office", "This paper is already secured.", parent=self.root)
                return
            to_state = states[index + 1]
        examiner = location = None
        if to_state == 'externally_approved':
            examiner = simpledialog.askstring("External approval", "External examiner who approved it:",
                                              parent=self.root)
        if to_state == 'secured':
            location = simpledialog.askstring("Secured", "Where are the printed papers secured?",
                                              parent=self.root)
        notes = simpledialog.askstring("Paper", f"Notes for '{to_state}' (optional):", parent=self.root)
        if self._office_run(lambda c: exam_office.advance_paper(
                c, exam_id, to_state, self._office_user(), external_examiner=examiner,
                secured_location=location, notes=notes), f"Paper moved to {to_state}."):
            self._load_paper()

    # ── absentees ───────────────────────────────────────────────────────

    def _office_absentees(self, tab):
        self.abs_exam, combo = self._picker(tab, self._load_absentees)
        ttk.Button(tab, text="Record These Absences", command=self._record_absentees).pack(anchor='w', pady=(0, 6))
        ttk.Label(tab, text="Students on the sitting with no result after the exam date. ABS counts as 0 "
                            "(referral); ABS-MC (an approved missed-exam request) leaves the module "
                            "outstanding for a deferred sitting.", foreground='#555', wraplength=950).pack(anchor='w')
        self.abs_tree = _tree(tab, [("student", "Student"), ("code", "Code")], [160, 120], height=12)

    def _load_absentees(self):
        self.abs_tree.delete(*self.abs_tree.get_children())
        exam_id = self._exam_choices().get(self.abs_exam.get())
        if not exam_id:
            return
        with closing(get_connection()) as conn:
            rows = exam_results.absentees(conn, exam_id)
            conn.commit()
        for r in rows:
            self.abs_tree.insert('', 'end', values=(r['student_id'], r['code']))

    def _record_absentees(self):
        exam_id = self._picked(self.abs_exam)
        if exam_id and self._office_run(lambda c: exam_results.record_absentees(c, exam_id, self._office_user()),
                                        lambda n: f"{n} absence(s) recorded."):
            self._load_absentees()
