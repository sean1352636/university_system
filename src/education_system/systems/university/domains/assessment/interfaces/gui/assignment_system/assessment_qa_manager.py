"""Assessment QA: anonymity, word limits, moderation, release, NS, reassessment.

The rules live in ``AssessmentQAService``; this screen only collects input
and shows results.
"""
import logging

logger = logging.getLogger(__name__)

import tkinter as tk
from tkinter import ttk, simpledialog
from education_system.systems.university.domains.assessment.interfaces.gui.assignment_system._dialogs import messagebox
from education_system.systems.university.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
from education_system.systems.university.domains.assessment.domain.assignments.assignment_rules import markers
from education_system.systems.university.domains.assessment.domain.assignments.assessment_qa import (
    AssessmentQAError,
    AssessmentQAService,
)
from education_system.systems.university.domains.assessment.domain.assignments.assessment_qa.service import (
    CLASH_THRESHOLD,
    CLASH_WINDOW_DAYS,
    FEEDBACK_TURNAROUND_WORKING_DAYS,
    PASS_MARK,
)


def _tree(parent, columns, widths, height=12):
    """A treeview with a vertical scrollbar, packed to fill what is left."""
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


class AssessmentQAManager:
    """Assessment quality assurance screens for staff."""

    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style
        self.qa = AssessmentQAService(str(DEFAULT_DB_PATH))
        self._assignment_map = {}

    def _check_permission(self, permission):
        try:
            return self.auth.check_permission(permission)
        except (AttributeError, Exception):
            return self.auth.user_role in ['Admin', 'Faculty']

    def _user(self):
        user = getattr(self.auth, 'current_user', None) or {}
        return user.get('username') or str(user.get('id') or '')

    def _assignment_id(self):
        aid = self._assignment_map.get(self.assignment_var.get())
        if not aid:
            messagebox.showwarning("Assessment QA", "Choose an assignment first.")
        return aid

    def _run(self, action, success=None):
        """Run a service call, turning a refused rule into a message."""
        try:
            result = action()
        except AssessmentQAError as e:
            messagebox.showwarning("Assessment QA", str(e))
            return None
        except Exception as e:
            logger.exception("Assessment QA action failed")
            messagebox.showerror("Assessment QA", f"Failed: {e}")
            return None
        if success:
            messagebox.showinfo("Assessment QA", success(result) if callable(success) else success)
        return result if result is not None else True

    # ── startup hook ────────────────────────────────────────────────────

    def release_due_grades(self):
        """Release assignments whose release date has passed. Called when the GUI opens."""
        try:
            outcome = self.qa.release_due(released_by=self._user() or "scheduled release")
        except Exception:
            logger.debug("Scheduled grade release skipped", exc_info=True)
            return
        released = [aid for aid, r in outcome.items() if "released" in r]
        if released:
            logger.info("Released grades for assignment(s) %s on their release date", released)

    # ── main screen ─────────────────────────────────────────────────────

    def show_assessment_qa(self, tab=0):
        if not self._check_permission('manage_assignments'):
            messagebox.showwarning("Assessment QA", "You do not have permission to manage assignments.")
            return
        self.gui.layout.clear_content_area()
        area = self.gui.layout.content_area

        ttk.Label(area, text="Assessment QA", style='Title.TLabel').pack(anchor='w', pady=(0, 10))

        picker = ttk.Frame(area)
        picker.pack(fill='x', pady=(0, 10))
        ttk.Label(picker, text="Assignment:").pack(side='left')
        self.assignment_var = tk.StringVar()
        combo = ttk.Combobox(picker, textvariable=self.assignment_var, width=70, state='readonly')
        combo.pack(side='left', padx=(5, 10))
        combo.bind('<<ComboboxSelected>>', lambda e: self._refresh_assignment_tabs())
        ttk.Button(picker, text="Refresh", command=self._load_assignments).pack(side='left')
        self._assignment_combo = combo

        self.notebook = ttk.Notebook(area)
        self.notebook.pack(fill='both', expand=True)
        self._build_settings_tab()
        self._build_moderation_tab()
        self._build_release_tab()
        self._build_non_submission_tab()
        self._build_reassessment_tab()
        self._build_turnaround_tab()
        self._build_clash_tab()
        self._build_marker_tab()

        self._load_assignments()
        try:
            self.notebook.select(tab)
        except tk.TclError:
            pass

    def _load_assignments(self):
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        try:
            rows = conn.execute(
                "SELECT id, module_code, title, due_date FROM assignments "
                "WHERE COALESCE(is_active, 1) = 1 ORDER BY due_date DESC").fetchall()
        except Exception as e:
            messagebox.showerror("Assessment QA", f"Failed to load assignments: {e}")
            rows = []
        finally:
            conn.close()
        self._assignment_map = {f"#{r[0]}  {r[1]} — {r[2]} (due {str(r[3])[:16]})": r[0] for r in rows}
        self._assignment_combo['values'] = list(self._assignment_map)
        current = self.assignment_var.get()
        if current not in self._assignment_map and self._assignment_map:
            self.assignment_var.set(next(iter(self._assignment_map)))
        self._refresh_assignment_tabs()
        self._load_turnaround()
        self._load_clashes()

    # ── marker allocation ──────────────────────────────────────────────

    def _build_marker_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Marker Allocation")
        ttk.Label(tab, text="Share the submissions out and each marker sees only their own in "
                            "Grade Tracking. With no allocations, any marker can mark any submission."
                  ).pack(anchor='w', pady=(0, 8))
        top = ttk.Frame(tab)
        top.pack(fill='x', pady=(0, 8))
        ttk.Label(top, text="Markers:").pack(side='left', anchor='n')
        self._marker_list = tk.Listbox(top, selectmode='multiple', height=5, width=28, exportselection=False)
        self._marker_list.pack(side='left', padx=5)
        ttk.Button(top, text="Share Out Evenly", style='Accent.TButton',
                   command=self._share_markers).pack(side='left', padx=5, anchor='n')
        ttk.Button(top, text="Clear Allocations", command=self._clear_markers).pack(side='left', anchor='n')
        self._marker_totals = ttk.Label(top, text="")
        self._marker_totals.pack(side='left', padx=15, anchor='n')
        self._marker_tree = _tree(tab, (("student", "Student"), ("marked", "Marked"), ("marker", "Marker")),
                                  (260, 90, 220), height=12)
        move = ttk.Frame(tab)
        move.pack(fill='x', pady=(8, 0))
        ttk.Label(move, text="Move selected to:").pack(side='left')
        self._marker_move_var = tk.StringVar()
        self._marker_move = ttk.Combobox(move, textvariable=self._marker_move_var, state='readonly', width=26)
        self._marker_move.pack(side='left', padx=5)
        ttk.Button(move, text="Move", command=self._move_marker).pack(side='left')
        ttk.Button(move, text="Remove Allocation", command=lambda: self._move_marker(True)).pack(side='left', padx=5)

    def _load_markers(self, aid):
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        try:
            names = markers.candidates(conn, aid)
            rows = markers.rows(conn, aid)
        finally:
            conn.close()
        chosen = {self._marker_list.get(i) for i in self._marker_list.curselection()}
        self._marker_list.delete(0, tk.END)
        for index, name in enumerate(names):
            self._marker_list.insert(tk.END, name)
            if name in chosen:
                self._marker_list.selection_set(index)
        self._marker_move['values'] = names
        labels = self.qa.marker_labels([(r["submission_id"], r["student_id"]) for r in rows])
        tree = self._marker_tree
        tree.delete(*tree.get_children())
        totals = {}
        for r in rows:
            if r["marker"]:
                totals[r["marker"]] = totals.get(r["marker"], 0) + 1
            tree.insert('', 'end', iid=str(r["student_id"]),
                        values=(labels.get(r["submission_id"], r["student_id"]),
                                "Yes" if r["grade"] is not None else "No", r["marker"] or "Not allocated"))
        self._marker_totals.configure(text="  ".join(f"{k}: {v}" for k, v in sorted(totals.items()))
                                      or "Nothing allocated yet")

    def _marker_write(self, action, aid):
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        try:
            result = action(conn)
            conn.commit()
            return result
        except ValueError as refused:
            conn.rollback()
            messagebox.showwarning("Marker Allocation", str(refused))
            return None
        finally:
            conn.close()
            self._load_markers(aid)

    def _share_markers(self):
        aid = self._assignment_id()
        if not aid:
            return
        names = [self._marker_list.get(i) for i in self._marker_list.curselection()]
        done = self._marker_write(lambda c: markers.share_evenly(c, aid, names, self._user()), aid)
        if done is not None:
            messagebox.showinfo("Marker Allocation", f"{done} submission(s) allocated.")

    def _clear_markers(self):
        aid = self._assignment_id()
        if aid and messagebox.askyesno("Marker Allocation", "Remove every allocation on this assignment?"):
            self._marker_write(lambda c: markers.clear(c, aid), aid)

    def _move_marker(self, remove=False):
        aid = self._assignment_id()
        if not aid:
            return
        chosen = self._marker_tree.selection()
        marker = "" if remove else self._marker_move_var.get()
        if not chosen or (not remove and not marker):
            messagebox.showinfo("Marker Allocation", "Select a submission and a marker first.")
            return

        def action(conn):
            for student in chosen:
                markers.set_marker(conn, aid, student, marker, self._user())
        self._marker_write(action, aid)

    def _refresh_assignment_tabs(self):
        aid = self._assignment_map.get(self.assignment_var.get())
        if not aid:
            return
        try:
            self._load_markers(aid)
        except Exception:
            logger.exception("Could not load marker allocations")
        self._load_settings(aid)
        self._load_moderation(aid)
        self._load_release(aid)
        self._load_non_submissions(aid)
        self._load_reassessment(aid)

    # ── settings tab ────────────────────────────────────────────────────

    def _build_settings_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Settings")
        self.settings_vars = {
            "assessment_kind": tk.StringVar(value="summative"),
            "module_weight_pct": tk.StringVar(),
            "anonymous_marking": tk.BooleanVar(),
            "word_limit": tk.StringVar(),
            "word_limit_tolerance_pct": tk.StringVar(value="10"),
            "word_limit_penalty_pct": tk.StringVar(value="10"),
            "feedback_due_date": tk.StringVar(),
            "grade_release_date": tk.StringVar(),
            "moderation_required": tk.BooleanVar(),
            "moderation_sample_pct": tk.StringVar(value="10"),
        }
        v = self.settings_vars
        grid = ttk.Frame(tab)
        grid.pack(fill='x')
        rows = [
            ("Assessment type", ttk.Combobox(grid, textvariable=v["assessment_kind"],
                                             values=("summative", "formative"), state='readonly', width=14),
             "Formative work is practice only and never counts towards the module result."),
            ("Module weighting (%)", ttk.Entry(grid, textvariable=v["module_weight_pct"], width=10),
             "Leave blank on every assignment in the module to weight them equally."),
            ("Anonymous marking", ttk.Checkbutton(grid, variable=v["anonymous_marking"]),
             "Markers see a candidate number instead of the student's name until release."),
            ("Word limit", ttk.Entry(grid, textvariable=v["word_limit"], width=10),
             "Blank for none."),
            ("Tolerance over limit (%)", ttk.Entry(grid, textvariable=v["word_limit_tolerance_pct"], width=10), ""),
            ("Penalty if exceeded (points)", ttk.Entry(grid, textvariable=v["word_limit_penalty_pct"], width=10),
             "Percentage points taken off the mark."),
            ("Feedback due (YYYY-MM-DD)", ttk.Entry(grid, textvariable=v["feedback_due_date"], width=14),
             f"Blank = {FEEDBACK_TURNAROUND_WORKING_DAYS} working days after the deadline."),
            ("Grade release date", ttk.Entry(grid, textvariable=v["grade_release_date"], width=14),
             "Blank = release by hand. Marks stay hidden until released."),
            ("Moderation required", ttk.Checkbutton(grid, variable=v["moderation_required"]),
             "A sample must be second-marked and agreed before release."),
            ("Moderation sample (%)", ttk.Entry(grid, textvariable=v["moderation_sample_pct"], width=10),
             "All fails are always sampled; minimum five scripts."),
        ]
        for i, (label, widget, hint) in enumerate(rows):
            ttk.Label(grid, text=label + ":").grid(row=i, column=0, sticky='w', pady=3)
            widget.grid(row=i, column=1, sticky='w', padx=8, pady=3)
            ttk.Label(grid, text=hint, foreground='#666').grid(row=i, column=2, sticky='w', pady=3)
        self.settings_info = tk.StringVar()
        ttk.Label(tab, textvariable=self.settings_info, style='Info.TLabel').pack(anchor='w', pady=(10, 5))
        ttk.Button(tab, text="Save Settings", style='Accent.TButton',
                   command=self._save_settings).pack(anchor='w')

    def _load_settings(self, aid):
        try:
            a = self.qa.get_settings(aid)
        except Exception as e:
            self.settings_info.set(f"Could not load settings: {e}")
            return
        for key, var in self.settings_vars.items():
            value = a.get(key)
            if isinstance(var, tk.BooleanVar):
                var.set(bool(value))
            elif key == "assessment_kind":
                var.set(value or "summative")
            else:
                var.set("" if value is None else (f"{value:g}" if isinstance(value, float) else str(value)))
        total = self.qa.module_weight_total(a["module_code"])
        parts = [f"Feedback due: {a.get('effective_feedback_due') or '—'}",
                 f"Module {a['module_code']} weightings total {total:g}%"]
        if total and abs(total - 100) > 0.01:
            parts.append("(should be 100%)")
        if a.get("reassessment_of"):
            parts.append(f"Reassessment ({a.get('reassessment_type')}) of assignment #{a['reassessment_of']}")
        if a.get("grades_released_at"):
            parts.append(f"Released {a['grades_released_at'][:16]}")
        self.settings_info.set("   ".join(parts))

    def _save_settings(self):
        aid = self._assignment_id()
        if not aid:
            return
        values = {k: v.get() for k, v in self.settings_vars.items()}
        if self._run(lambda: self.qa.update_settings(aid, **values), "Settings saved."):
            self._refresh_assignment_tabs()

    # ── moderation tab ──────────────────────────────────────────────────

    def _build_moderation_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Moderation")
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(0, 8))
        ttk.Button(bar, text="Draw Sample", command=self._draw_sample).pack(side='left')
        ttk.Button(bar, text="Enter Second Mark", command=self._second_mark).pack(side='left', padx=5)
        ttk.Button(bar, text="Agree Mark", command=self._agree_mark).pack(side='left')
        ttk.Button(bar, text="Complete Moderation", style='Accent.TButton',
                   command=self._complete_moderation).pack(side='left', padx=5)
        self.moderation_info = tk.StringVar()
        ttk.Label(tab, textvariable=self.moderation_info, style='Info.TLabel').pack(anchor='w', pady=(0, 5))
        self.moderation_tree = _tree(
            tab,
            [("id", "#"), ("student", "Student"), ("first", "First mark"), ("second", "Second mark"),
             ("diff", "Difference"), ("agreed", "Agreed"), ("status", "Status")],
            [50, 200, 90, 100, 90, 90, 120])

    def _load_moderation(self, aid):
        tree = self.moderation_tree
        tree.delete(*tree.get_children())
        try:
            rows = self.qa.moderation_rows(aid)
            a = self.qa.get_settings(aid)
        except Exception as e:
            self.moderation_info.set(f"Could not load moderation: {e}")
            return
        for r in rows:
            tree.insert('', 'end', iid=str(r["id"]), values=(
                r["id"], r["label"], _fmt(r["first_mark"], "%"), _fmt(r["second_mark"], "%"),
                _fmt(r["difference"]), _fmt(r["agreed_mark"], "%"), r["status"]))
        required = "required" if a.get("moderation_required") else "not required"
        self.moderation_info.set(
            f"Moderation {required}; status: {a.get('moderation_status') or 'not_started'}; "
            f"{len(rows)} script(s) sampled.")

    def _selected_moderation(self):
        sel = self.moderation_tree.selection()
        if not sel:
            messagebox.showwarning("Assessment QA", "Select a sampled script.")
            return None
        return int(sel[0])

    def _draw_sample(self):
        aid = self._assignment_id()
        if aid and self._run(lambda: self.qa.draw_moderation_sample(aid, drawn_by=self._user()),
                             lambda rows: f"{len(rows)} script(s) in the sample."):
            self._load_moderation(aid)

    def _second_mark(self):
        mid = self._selected_moderation()
        if mid is None:
            return
        mark = simpledialog.askfloat("Second mark", "Second marker's mark (%):",
                                     minvalue=0, maxvalue=100, parent=self.root)
        if mark is None:
            return
        notes = simpledialog.askstring("Second mark", "Comments (optional):", parent=self.root)
        if self._run(lambda: self.qa.record_second_mark(mid, mark, self._user(), notes or None)):
            self._load_moderation(self._assignment_map.get(self.assignment_var.get()))

    def _agree_mark(self):
        mid = self._selected_moderation()
        if mid is None:
            return
        values = self.moderation_tree.item(str(mid))['values']
        mark = simpledialog.askfloat(
            "Agreed mark", f"First {values[2]}, second {values[3]}.\nAgreed mark (%):",
            minvalue=0, maxvalue=100, parent=self.root)
        if mark is None:
            return
        notes = simpledialog.askstring("Agreed mark", "How was it resolved? (optional):", parent=self.root)
        if self._run(lambda: self.qa.agree_mark(mid, mark, self._user(), notes or None)):
            self._load_moderation(self._assignment_map.get(self.assignment_var.get()))

    def _complete_moderation(self):
        aid = self._assignment_id()
        if aid and self._run(lambda: self.qa.complete_moderation(aid, self._user()),
                             "Moderation complete. Grades can now be released."):
            self._refresh_assignment_tabs()

    # ── release tab ─────────────────────────────────────────────────────

    def _build_release_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Release")
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(0, 8))
        ttk.Button(bar, text="Release Grades", style='Accent.TButton',
                   command=lambda: self._release(False)).pack(side='left')
        ttk.Button(bar, text="Release Now (ignore release date)",
                   command=lambda: self._release(True)).pack(side='left', padx=5)
        self.release_text = tk.Text(tab, height=14, wrap='word')
        self.release_text.pack(fill='both', expand=True)

    def _load_release(self, aid):
        text = self.release_text
        text.configure(state='normal')
        text.delete('1.0', 'end')
        try:
            a = self.qa.get_settings(aid)
            blockers = self.qa.release_blockers(aid)
        except Exception as e:
            text.insert('end', f"Could not load release status: {e}")
            text.configure(state='disabled')
            return
        if a.get("grades_released_at"):
            text.insert('end', f"Released {a['grades_released_at']} by {a.get('grades_released_by') or '—'}.\n\n"
                               "Marks entered from now on are visible to students as soon as they are saved.")
        elif blockers:
            text.insert('end', "Not ready to release:\n\n" + "\n".join(f"  • {b}" for b in blockers))
        else:
            text.insert('end', "Ready to release. Students are emailed their mark and feedback, and "
                               "their module result is recalculated.")
        text.insert('end', f"\n\nRelease date: {a.get('grade_release_date') or 'none (release by hand)'}"
                           f"\nFeedback due: {a.get('effective_feedback_due') or '—'}")
        text.configure(state='disabled')

    def _release(self, ignore_date):
        aid = self._assignment_id()
        if not aid:
            return
        if not messagebox.askyesno("Release grades",
                                   "Release every mark on this assignment to students now?"):
            return
        if self._run(lambda: self.qa.release_grades(aid, self._user(), ignore_release_date=ignore_date),
                     lambda r: f"Released {r['released']} mark(s); "
                               f"{r['non_submissions']} non-submission(s) recorded as 0."):
            self._refresh_assignment_tabs()
            self._load_turnaround()

    # ── non-submission tab ──────────────────────────────────────────────

    def _build_non_submission_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Non-submissions")
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(0, 8))
        ttk.Button(bar, text="Record Non-submissions", style='Accent.TButton',
                   command=self._record_ns).pack(side='left')
        ttk.Button(bar, text="Remove Selected", command=self._void_ns).pack(side='left', padx=5)
        ttk.Label(tab, text="Enrolled students with no submission after their deadline (including "
                            "approved extensions). A non-submission counts as 0 in the module result.",
                  foreground='#666').pack(anchor='w', pady=(0, 5))
        self.ns_tree = _tree(tab, [("student", "Student ID"), ("name", "Name"), ("code", "Code"),
                                   ("when", "Recorded")], [120, 220, 60, 160])

    def _load_non_submissions(self, aid):
        tree = self.ns_tree
        tree.delete(*tree.get_children())
        try:
            rows = self.qa.non_submissions(aid)
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
            return
        for r in rows:
            name = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
            tree.insert('', 'end', iid=r["student_id"],
                        values=(r["student_id"], name or "—", r["code"], r["recorded_at"][:16]))

    def _record_ns(self):
        aid = self._assignment_id()
        if aid and self._run(lambda: self.qa.record_non_submissions(aid, self._user()),
                             lambda n: f"{n} non-submission(s) recorded."):
            self._load_non_submissions(aid)

    def _void_ns(self):
        aid = self._assignment_id()
        sel = self.ns_tree.selection()
        if not aid or not sel:
            return
        if self._run(lambda: [self.qa.void_non_submission(aid, sid) for sid in sel]):
            self._load_non_submissions(aid)

    # ── reassessment tab ────────────────────────────────────────────────

    def _build_reassessment_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Reassessment")
        bar = ttk.Frame(tab)
        bar.pack(fill='x', pady=(0, 8))
        ttk.Label(bar, text="Due date (YYYY-MM-DD HH:MM):").pack(side='left')
        self.reassess_due_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self.reassess_due_var, width=18).pack(side='left', padx=5)
        ttk.Button(bar, text="Toggle Referral/Deferral", command=self._toggle_type).pack(side='left', padx=5)
        ttk.Button(bar, text="Create Reassessment for Selected", style='Accent.TButton',
                   command=self._create_reassessment).pack(side='left')
        ttk.Label(tab, text=f"Fails (under {PASS_MARK:g}%) and non-submissions. A referral is capped at "
                            f"{PASS_MARK:g}%; a deferral (granted by a mitigating-circumstances panel) is "
                            "uncapped. The reassessment mark replaces the original in the module result.",
                  foreground='#666', wraplength=900).pack(anchor='w', pady=(0, 5))
        self.candidate_tree = _tree(tab, [("student", "Student ID"), ("mark", "Mark"),
                                          ("reason", "Reason"), ("type", "Attempt")],
                                    [120, 80, 140, 120], height=8)
        ttk.Label(tab, text="Reassessments already set:", style='Header.TLabel').pack(anchor='w', pady=(10, 5))
        self.reassessment_tree = _tree(tab, [("student", "Student ID"), ("type", "Attempt"),
                                             ("title", "Sitting"), ("due", "Due"), ("mark", "Mark")],
                                       [120, 90, 280, 140, 80], height=6)
        self._candidate_claims = {}

    def _load_reassessment(self, aid):
        for tree in (self.candidate_tree, self.reassessment_tree):
            tree.delete(*tree.get_children())
        self._candidate_claims = {}
        try:
            candidates = self.qa.reassessment_candidates(aid)
        except AssessmentQAError:
            candidates = []
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
            candidates = []
        for c in candidates:
            self._candidate_claims[c["student_id"]] = c.get("mc_claim_id")
            self.candidate_tree.insert('', 'end', iid=c["student_id"], values=(
                c["student_id"], _fmt(float(c["mark"]), "%"), c["reason"], c["suggested_type"]))
        try:
            for r in self.qa.reassessments(aid):
                self.reassessment_tree.insert('', 'end', values=(
                    r["student_id"], r["attempt_type"], r["reassessment_title"],
                    str(r["due_date"])[:16], _fmt(r["mark"], "%")))
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

    def _toggle_type(self):
        for iid in self.candidate_tree.selection():
            values = list(self.candidate_tree.item(iid)['values'])
            values[3] = "deferral" if values[3] == "referral" else "referral"
            self.candidate_tree.item(iid, values=values)

    def _create_reassessment(self):
        aid = self._assignment_id()
        sel = self.candidate_tree.selection()
        if not aid:
            return
        if not sel:
            messagebox.showwarning("Assessment QA", "Select the students to reassess.")
            return
        students = [{"student_id": str(self.candidate_tree.item(i)['values'][0]),
                     "attempt_type": self.candidate_tree.item(i)['values'][3],
                     "mc_claim_id": self._candidate_claims.get(i)} for i in sel]
        user = getattr(self.auth, 'current_user', None) or {}
        if self._run(lambda: self.qa.create_reassessment(aid, students, self.reassess_due_var.get().strip(),
                                                         created_by=user.get('id')),
                     lambda new_id: f"Reassessment created as assignment #{new_id}. "
                                    "Only the selected students will see it."):
            self._load_assignments()

    # ── feedback turnaround tab ─────────────────────────────────────────

    def _build_turnaround_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Feedback Turnaround")
        ttk.Label(tab, text=f"Unreleased assignments against their feedback date (default "
                            f"{FEEDBACK_TURNAROUND_WORKING_DAYS} working days after the deadline).",
                  foreground='#666').pack(anchor='w', pady=(0, 5))
        self.turnaround_tree = _tree(
            tab, [("id", "#"), ("module", "Module"), ("title", "Assignment"), ("due", "Deadline"),
                  ("feedback", "Feedback due"), ("marked", "Marked"), ("state", "State")],
            [50, 100, 260, 130, 110, 90, 120])
        self.turnaround_tree.tag_configure('overdue', background='#ffebee')

    def _load_turnaround(self):
        tree = self.turnaround_tree
        tree.delete(*tree.get_children())
        try:
            rows = self.qa.feedback_turnaround_report()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
            return
        for r in rows:
            if r["overdue"]:
                state = "OVERDUE"
            elif r["days_left"] is not None:
                state = f"{r['days_left']} day(s) left"
            else:
                state = "—"
            tree.insert('', 'end', values=(
                r["id"], r["module_code"], r["title"], str(r["due_date"])[:16], r["feedback_due"] or "—",
                f"{r['marked']}/{r['submissions']}", state), tags=('overdue',) if r["overdue"] else ())

    # ── deadline clash tab ──────────────────────────────────────────────

    def _build_clash_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Deadline Clashes")
        ttk.Label(tab, text=f"Upcoming assignments where students would face {CLASH_THRESHOLD} or more "
                            f"summative deadlines within {CLASH_WINDOW_DAYS} days.",
                  foreground='#666').pack(anchor='w', pady=(0, 5))
        self.clash_tree = _tree(
            tab, [("id", "#"), ("module", "Module"), ("title", "Assignment"), ("due", "Deadline"),
                  ("students", "Students affected"), ("worst", "Most deadlines")],
            [50, 100, 280, 130, 130, 120])

    def _load_clashes(self):
        tree = self.clash_tree
        tree.delete(*tree.get_children())
        try:
            rows = self.qa.clash_report()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
            return
        for r in rows:
            tree.insert('', 'end', values=(r["id"], r["module_code"], r["title"], str(r["due_date"])[:16],
                                           r["students_affected"], r["worst"]))
