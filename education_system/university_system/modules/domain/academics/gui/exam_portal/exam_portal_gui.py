"""Exam Portal GUI — full exam management and taking interface.

Supports three role-based views:
- Student: browse exams, take timed exams, view results
- Instructor: create/edit exams, manage questions, grade essays, analytics
- Admin: all instructor features plus exam deletion and bulk operations
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import json
import logging
import threading
from datetime import datetime

from education_system.university_system.modules.domain.academics.services.exam_portal import ExamPortalService

logger = logging.getLogger(__name__)

QUESTION_TYPES = [
    ("mcq", "Multiple Choice"),
    ("true_false", "True / False"),
    ("short_answer", "Short Answer"),
    ("essay", "Essay"),
    ("fill_blank", "Fill in the Blank"),
]


class ExamPortalGUI:
    """Main exam portal GUI window."""

    def __init__(self, parent=None, auth=None):
        self.svc = ExamPortalService()
        self.auth = auth

        if parent:
            self.root = parent
        else:
            self.root = tk.Tk()
            self.root.title("Exam Portal")
            self.root.geometry("1200x800")

        self.style = ttk.Style()
        self.style.theme_use("clam")

        self._user = self._get_user_info()
        self._role = self._user.get("role", "student")
        self._timer_id = None
        self._current_attempt = None
        self._current_questions = []
        self._current_question_idx = 0
        self._answer_vars = {}

        self._build_ui()

    def _get_user_info(self):
        if self.auth and hasattr(self.auth, "current_user") and self.auth.current_user:
            return self.auth.current_user
        return {"username": "guest", "role": "student", "id": 0}

    # ── Main Layout ─────────────────────────────────────────────────

    def _build_ui(self):
        # Toolbar
        toolbar = ttk.Frame(self.root, padding=(10, 5))
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Return to Main Menu",
                   command=self._close).pack(side="left")
        ttk.Label(toolbar, text=f"Exam Portal  |  {self._user.get('username', '')} ({self._role})",
                  font=("Arial", 11, "bold")).pack(side="left", padx=20)

        # Main notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Student tabs
        self._build_browse_tab()
        self._build_results_tab()

        # Instructor/Admin tabs
        if self._role in ("admin", "staff", "instructor"):
            self._build_manage_tab()
            self._build_grading_tab()
            self._build_analytics_tab()

    def _close(self):
        if self._timer_id:
            self.root.after_cancel(self._timer_id)
        try:
            self.root.destroy()
        except Exception:
            pass

    # ── Browse Exams Tab (Student) ──────────────────────────────────

    def _build_browse_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Available Exams")

        header = ttk.Frame(tab)
        header.pack(fill="x", padx=10, pady=10)
        ttk.Label(header, text="Available Exams", font=("Arial", 14, "bold")).pack(side="left")
        ttk.Button(header, text="Refresh", command=self._refresh_browse).pack(side="right")

        cols = ("ID", "Title", "Module", "Duration", "Start", "End", "Attempts", "Status")
        self.browse_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c in cols:
            self.browse_tree.heading(c, text=c)
        self.browse_tree.column("ID", width=40)
        self.browse_tree.column("Title", width=250)
        self.browse_tree.column("Module", width=100)
        self.browse_tree.column("Duration", width=70)
        self.browse_tree.column("Start", width=130)
        self.browse_tree.column("End", width=130)
        self.browse_tree.column("Attempts", width=70)
        self.browse_tree.column("Status", width=80)

        scroll = ttk.Scrollbar(tab, orient="vertical", command=self.browse_tree.yview)
        self.browse_tree.configure(yscrollcommand=scroll.set)
        self.browse_tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 10))
        scroll.pack(side="right", fill="y", pady=(0, 10))

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btn_frame, text="Start Exam", command=self._start_exam).pack(side="left")

        self._refresh_browse()

    def _refresh_browse(self):
        for item in self.browse_tree.get_children():
            self.browse_tree.delete(item)
        sid = self._user.get("username", "")
        exams = self.svc.list_available_exams(sid)
        for e in exams:
            self.browse_tree.insert("", "end", values=(
                e["id"], e["title"], e.get("module_code", ""),
                f"{e['duration_minutes']} min",
                e.get("start_time", "Open"), e.get("end_time", "Open"),
                f"{e.get('attempt_count', 0)}/{e['max_attempts']}",
                e["status"],
            ))

    # ── Take Exam ───────────────────────────────────────────────────

    def _start_exam(self):
        sel = self.browse_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select an exam to start.")
            return
        exam_id = self.browse_tree.item(sel[0])["values"][0]
        exam = self.svc.get_exam(exam_id)
        if not exam:
            messagebox.showerror("Error", "Exam not found.")
            return

        if not messagebox.askyesno("Start Exam",
                                   f"Start '{exam['title']}'?\n\n"
                                   f"Duration: {exam['duration_minutes']} minutes\n"
                                   f"Questions: {self.svc.get_question_count(exam_id)}\n"
                                   f"Pass mark: {exam.get('pass_mark', 50)}%\n\n"
                                   "Once started, the timer cannot be paused."):
            return

        sid = self._user.get("username", "")
        attempt = self.svc.start_attempt(exam_id, sid, student_name=sid)
        if not attempt:
            messagebox.showerror("Error", "Cannot start exam. You may have reached the maximum attempts.")
            return

        self._current_attempt = attempt
        shuffle = bool(exam.get("shuffle_questions"))
        self._current_questions = self.svc.get_questions(exam_id, shuffle=shuffle)
        self._current_question_idx = 0
        self._answer_vars = {}
        self._show_exam_window(exam, attempt)

    def _show_exam_window(self, exam, attempt):
        self.exam_win = tk.Toplevel(self.root)
        self.exam_win.title(f"Exam: {exam['title']}")
        self.exam_win.geometry("900x650")
        self.exam_win.protocol("WM_DELETE_WINDOW", lambda: None)  # Prevent close

        # Timer bar
        timer_frame = ttk.Frame(self.exam_win)
        timer_frame.pack(fill="x", padx=10, pady=5)
        self._timer_var = tk.StringVar(value="Loading...")
        ttk.Label(timer_frame, text=exam["title"], font=("Arial", 12, "bold")).pack(side="left")
        self._timer_label = ttk.Label(timer_frame, textvariable=self._timer_var,
                                       font=("Arial", 12, "bold"), foreground="red")
        self._timer_label.pack(side="right")
        self._time_remaining = attempt.get("time_remaining", exam["duration_minutes"] * 60)

        # Question navigation
        nav_frame = ttk.Frame(self.exam_win)
        nav_frame.pack(fill="x", padx=10, pady=5)
        self._q_nav_frame = nav_frame
        self._build_question_nav()

        # Question display
        self._q_display = ttk.Frame(self.exam_win)
        self._q_display.pack(fill="both", expand=True, padx=10, pady=5)

        # Bottom buttons
        btn_frame = ttk.Frame(self.exam_win)
        btn_frame.pack(fill="x", padx=10, pady=10)
        ttk.Button(btn_frame, text="Previous", command=self._prev_question).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Next", command=self._next_question).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Flag for Review",
                   command=self._flag_question).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Submit Exam",
                   command=self._confirm_submit).pack(side="right", padx=5)

        self._show_question(0)
        self._tick_timer()

    def _build_question_nav(self):
        for w in self._q_nav_frame.winfo_children():
            w.destroy()
        ttk.Label(self._q_nav_frame, text="Questions:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        self._nav_buttons = []
        for i, q in enumerate(self._current_questions):
            qid = q["id"]
            flagged = self._answer_vars.get(qid, {}).get("flagged", False)
            answered = bool(self._answer_vars.get(qid, {}).get("answer", ""))
            text = f"{i+1}"
            if flagged:
                text += "*"
            btn = ttk.Button(self._q_nav_frame, text=text, width=3,
                             command=lambda idx=i: self._show_question(idx))
            btn.pack(side="left", padx=1)
            self._nav_buttons.append(btn)

    def _show_question(self, idx):
        self._save_current_answer()
        self._current_question_idx = idx
        for w in self._q_display.winfo_children():
            w.destroy()

        q = self._current_questions[idx]
        qid = q["id"]

        ttk.Label(self._q_display,
                  text=f"Question {idx + 1} of {len(self._current_questions)}  "
                       f"({q['marks']} marks)  [{q['question_type'].upper()}]",
                  font=("Arial", 10, "bold")).pack(anchor="w", pady=(0, 10))

        # Question text
        q_text = scrolledtext.ScrolledText(self._q_display, wrap=tk.WORD, height=4,
                                           font=("Arial", 11), state=tk.DISABLED)
        q_text.pack(fill="x", pady=(0, 10))
        q_text.config(state=tk.NORMAL)
        q_text.insert("1.0", q["question_text"])
        q_text.config(state=tk.DISABLED)

        # Answer area
        saved = self._answer_vars.get(qid, {}).get("answer", "")
        qtype = q["question_type"]

        if qtype in ("mcq", "true_false"):
            options = q.get("options", [])
            if qtype == "true_false":
                options = ["True", "False"]
            var = tk.StringVar(value=saved)
            for opt in options:
                ttk.Radiobutton(self._q_display, text=opt, value=opt,
                                variable=var).pack(anchor="w", padx=20, pady=2)
            self._answer_vars.setdefault(qid, {})["var"] = var

        elif qtype in ("short_answer", "fill_blank"):
            var = tk.StringVar(value=saved)
            ttk.Entry(self._q_display, textvariable=var, width=60,
                      font=("Arial", 11)).pack(anchor="w", padx=20, pady=5)
            self._answer_vars.setdefault(qid, {})["var"] = var

        elif qtype == "essay":
            text_w = scrolledtext.ScrolledText(self._q_display, wrap=tk.WORD, height=10,
                                               font=("Arial", 11))
            text_w.pack(fill="both", expand=True, padx=20, pady=5)
            if saved:
                text_w.insert("1.0", saved)
            self._answer_vars.setdefault(qid, {})["widget"] = text_w

        self._build_question_nav()

    def _save_current_answer(self):
        if not self._current_questions:
            return
        q = self._current_questions[self._current_question_idx]
        qid = q["id"]
        entry = self._answer_vars.get(qid, {})

        if "var" in entry:
            answer = entry["var"].get()
        elif "widget" in entry:
            answer = entry["widget"].get("1.0", tk.END).strip()
        else:
            return

        entry["answer"] = answer
        self._answer_vars[qid] = entry

        # Auto-save to server
        if self._current_attempt:
            self.svc.save_answer(
                self._current_attempt["id"], qid, answer,
                flagged=entry.get("flagged", False),
            )

    def _next_question(self):
        if self._current_question_idx < len(self._current_questions) - 1:
            self._show_question(self._current_question_idx + 1)

    def _prev_question(self):
        if self._current_question_idx > 0:
            self._show_question(self._current_question_idx - 1)

    def _flag_question(self):
        q = self._current_questions[self._current_question_idx]
        qid = q["id"]
        entry = self._answer_vars.setdefault(qid, {})
        entry["flagged"] = not entry.get("flagged", False)
        self._build_question_nav()
        status = "flagged" if entry["flagged"] else "unflagged"
        messagebox.showinfo("Flag", f"Question {self._current_question_idx + 1} {status} for review.")

    def _tick_timer(self):
        if self._time_remaining <= 0:
            self._auto_submit()
            return
        mins, secs = divmod(self._time_remaining, 60)
        self._timer_var.set(f"Time: {mins:02d}:{secs:02d}")
        if self._time_remaining <= 300:
            self._timer_label.configure(foreground="red")
        self._time_remaining -= 1
        if self._time_remaining % 30 == 0 and self._current_attempt:
            self.svc.update_time_remaining(self._current_attempt["id"], self._time_remaining)
        self._timer_id = self.exam_win.after(1000, self._tick_timer)

    def _auto_submit(self):
        self._save_current_answer()
        messagebox.showwarning("Time's Up", "Your exam has been auto-submitted.")
        self._do_submit(auto=True)

    def _confirm_submit(self):
        self._save_current_answer()
        total = len(self._current_questions)
        answered = sum(1 for q in self._current_questions
                       if self._answer_vars.get(q["id"], {}).get("answer"))
        flagged = sum(1 for q in self._current_questions
                      if self._answer_vars.get(q["id"], {}).get("flagged"))

        msg = (f"Answered: {answered}/{total}\n"
               f"Flagged: {flagged}\n"
               f"Unanswered: {total - answered}\n\n"
               "Are you sure you want to submit?")
        if messagebox.askyesno("Confirm Submission", msg):
            self._do_submit(auto=False)

    def _do_submit(self, auto=False):
        if self._timer_id:
            self.exam_win.after_cancel(self._timer_id)
            self._timer_id = None

        result = self.svc.submit_attempt(self._current_attempt["id"], auto=auto)
        self.exam_win.destroy()
        self._current_attempt = None
        self._refresh_browse()
        self._refresh_results()

        msg = (f"Score: {result['score']}/{result['total_marks']}\n"
               f"Percentage: {result['percentage']}%\n"
               f"Result: {'PASSED' if result['passed'] else 'FAILED'}")
        if result.get("needs_manual_grading"):
            msg += "\n\nSome questions require manual grading."
        messagebox.showinfo("Exam Submitted", msg)

    # ── Results Tab ─────────────────────────────────────────────────

    def _build_results_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Results")

        header = ttk.Frame(tab)
        header.pack(fill="x", padx=10, pady=10)
        ttk.Label(header, text="My Exam Results", font=("Arial", 14, "bold")).pack(side="left")
        ttk.Button(header, text="Refresh", command=self._refresh_results).pack(side="right")

        cols = ("ID", "Exam", "Score", "Percentage", "Result", "Submitted", "Status")
        self.results_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self.results_tree.heading(c, text=c)
        self.results_tree.column("ID", width=40)
        self.results_tree.column("Exam", width=250)
        self.results_tree.column("Score", width=80)
        self.results_tree.column("Percentage", width=80)
        self.results_tree.column("Result", width=80)
        self.results_tree.column("Submitted", width=150)
        self.results_tree.column("Status", width=80)
        self.results_tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.results_tree.bind("<Double-1>", self._view_result_detail)
        self._refresh_results()

    def _refresh_results(self):
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        sid = self._user.get("username", "")
        attempts = self.svc.get_student_attempts(sid)
        for a in attempts:
            result = "PASSED" if a.get("passed") else ("FAILED" if a.get("passed") is not None else "Pending")
            self.results_tree.insert("", "end", values=(
                a["id"], a.get("exam_title", ""),
                f"{a.get('score', '-')}/{a.get('total_marks', '-')}",
                f"{a.get('percentage', '-')}%", result,
                a.get("submitted_at", ""), a["status"],
            ))

    def _view_result_detail(self, event=None):
        sel = self.results_tree.selection()
        if not sel:
            return
        attempt_id = self.results_tree.item(sel[0])["values"][0]
        attempt = self.svc.get_attempt(attempt_id)
        if not attempt:
            return

        exam = self.svc.get_exam(attempt["exam_id"])
        if not exam or not exam.get("allow_review"):
            messagebox.showinfo("Review", "Review is not available for this exam.")
            return

        questions = self.svc.get_questions(attempt["exam_id"])
        answers = self.svc.get_answers(attempt_id)
        answer_map = {a["question_id"]: a for a in answers}

        win = tk.Toplevel(self.root)
        win.title(f"Exam Review — {exam['title']}")
        win.geometry("800x600")

        text = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Arial", 11))
        text.pack(fill="both", expand=True, padx=10, pady=10)

        text.insert("end", f"Exam: {exam['title']}\n")
        text.insert("end", f"Score: {attempt.get('score', '-')}/{exam['total_marks']}  "
                           f"({attempt.get('percentage', '-')}%)\n")
        text.insert("end", f"Result: {'PASSED' if attempt.get('passed') else 'FAILED'}\n")
        text.insert("end", "=" * 60 + "\n\n")

        for i, q in enumerate(questions, 1):
            a = answer_map.get(q["id"], {})
            text.insert("end", f"Q{i}. [{q['question_type'].upper()}] ({q['marks']} marks)\n")
            text.insert("end", f"   {q['question_text']}\n")
            text.insert("end", f"   Your answer: {a.get('answer_text', '(no answer)')}\n")
            if q.get("correct_answer"):
                text.insert("end", f"   Correct answer: {q['correct_answer']}\n")
            text.insert("end", f"   Marks: {a.get('marks_awarded', 0)}/{q['marks']}\n")
            if a.get("feedback"):
                text.insert("end", f"   Feedback: {a['feedback']}\n")
            text.insert("end", "\n")

        text.config(state=tk.DISABLED)
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=10)

    # ── Manage Exams Tab (Instructor/Admin) ─────────────────────────

    def _build_manage_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Manage Exams")

        # Exam list
        header = ttk.Frame(tab)
        header.pack(fill="x", padx=10, pady=10)
        ttk.Label(header, text="Exam Management", font=("Arial", 14, "bold")).pack(side="left")
        ttk.Button(header, text="Create Exam", command=self._create_exam_dialog).pack(side="right", padx=5)
        ttk.Button(header, text="Refresh", command=self._refresh_manage).pack(side="right")

        cols = ("ID", "Title", "Module", "Status", "Questions", "Duration", "Created")
        self.manage_tree = ttk.Treeview(tab, columns=cols, show="headings", height=8)
        for c in cols:
            self.manage_tree.heading(c, text=c)
        self.manage_tree.column("ID", width=40)
        self.manage_tree.column("Title", width=220)
        self.manage_tree.column("Module", width=100)
        self.manage_tree.column("Status", width=80)
        self.manage_tree.column("Questions", width=70)
        self.manage_tree.column("Duration", width=70)
        self.manage_tree.column("Created", width=130)
        self.manage_tree.pack(fill="x", padx=10)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(btn_frame, text="Edit Exam", command=self._edit_exam).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Manage Questions", command=self._manage_questions).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Publish", command=self._publish_exam).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Unpublish", command=self._unpublish_exam).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Delete", command=self._delete_exam).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="View Results", command=self._view_exam_results).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Export CSV", command=self._export_csv).pack(side="left", padx=2)

        self._refresh_manage()

    def _get_selected_exam_id(self):
        sel = self.manage_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select an exam.")
            return None
        return self.manage_tree.item(sel[0])["values"][0]

    def _refresh_manage(self):
        for item in self.manage_tree.get_children():
            self.manage_tree.delete(item)
        user = self._user.get("username", "")
        exams = self.svc.list_exams(created_by=user if self._role != "admin" else None)
        for e in exams:
            qcount = self.svc.get_question_count(e["id"])
            self.manage_tree.insert("", "end", values=(
                e["id"], e["title"], e.get("module_code", ""),
                e["status"], qcount, f"{e['duration_minutes']} min",
                e.get("created_at", "")[:16],
            ))

    def _create_exam_dialog(self):
        self._exam_form_dialog(None)

    def _edit_exam(self):
        eid = self._get_selected_exam_id()
        if eid:
            self._exam_form_dialog(eid)

    def _exam_form_dialog(self, exam_id):
        exam = self.svc.get_exam(exam_id) if exam_id else {}
        is_edit = bool(exam_id)

        win = tk.Toplevel(self.root)
        win.title("Edit Exam" if is_edit else "Create Exam")
        win.geometry("550x600")
        win.transient(self.root)

        canvas = tk.Canvas(win, highlightthickness=0)
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas, padding=15)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        fields = {}

        def add_field(label, key, default="", widget_type="entry", **kw):
            ttk.Label(inner, text=label, font=("Arial", 10, "bold")).pack(anchor="w", pady=(8, 2))
            if widget_type == "entry":
                var = tk.StringVar(value=str(exam.get(key, default)))
                ttk.Entry(inner, textvariable=var, width=50).pack(fill="x")
                fields[key] = var
            elif widget_type == "spinbox":
                var = tk.StringVar(value=str(exam.get(key, default)))
                ttk.Spinbox(inner, from_=kw.get("from_", 1), to=kw.get("to", 999),
                            textvariable=var, width=10).pack(anchor="w")
                fields[key] = var
            elif widget_type == "combo":
                var = tk.StringVar(value=str(exam.get(key, default)))
                ttk.Combobox(inner, textvariable=var, values=kw.get("values", []),
                             state="readonly", width=20).pack(anchor="w")
                fields[key] = var
            elif widget_type == "check":
                var = tk.BooleanVar(value=bool(exam.get(key, default)))
                ttk.Checkbutton(inner, text=label, variable=var).pack(anchor="w")
                fields[key] = var
                return  # label already in checkbutton
            elif widget_type == "text":
                tw = tk.Text(inner, height=4, width=50, wrap=tk.WORD)
                tw.pack(fill="x")
                tw.insert("1.0", exam.get(key, default) or "")
                fields[key] = tw

        add_field("Title", "title")
        add_field("Module Code", "module_code")
        add_field("Description", "description", widget_type="text")
        add_field("Duration (minutes)", "duration_minutes", 60, "spinbox", from_=5, to=480)
        add_field("Total Marks", "total_marks", 100, "spinbox", from_=1, to=1000)
        add_field("Pass Mark (%)", "pass_mark", 50, "spinbox", from_=0, to=100)
        add_field("Max Attempts", "max_attempts", 1, "spinbox", from_=1, to=10)
        add_field("Start Time (YYYY-MM-DD HH:MM)", "start_time")
        add_field("End Time (YYYY-MM-DD HH:MM)", "end_time")
        add_field("Results Visibility", "show_results", "after_submit", "combo",
                  values=["after_submit", "after_grading", "scheduled", "never"])
        add_field("Instructions", "instructions", widget_type="text")
        add_field("Shuffle Questions", "shuffle_questions", 0, "check")
        add_field("Shuffle Answers", "shuffle_answers", 0, "check")
        add_field("Auto-Submit on Timeout", "auto_submit", 1, "check")
        add_field("Allow Review After Submit", "allow_review", 1, "check")

        def _save():
            data = {}
            for key, widget in fields.items():
                if isinstance(widget, tk.Text):
                    data[key] = widget.get("1.0", tk.END).strip()
                elif isinstance(widget, tk.BooleanVar):
                    data[key] = int(widget.get())
                else:
                    val = widget.get()
                    if key in ("duration_minutes", "total_marks", "max_attempts"):
                        try:
                            val = int(val)
                        except ValueError:
                            pass
                    elif key == "pass_mark":
                        try:
                            val = float(val)
                        except ValueError:
                            pass
                    data[key] = val

            title = data.pop("title", "")
            if not title:
                messagebox.showerror("Validation", "Title is required.", parent=win)
                return

            if is_edit:
                data["title"] = title
                self.svc.update_exam(exam_id, **data)
                messagebox.showinfo("Saved", "Exam updated.", parent=win)
            else:
                self.svc.create_exam(title, self._user.get("username", ""), **data)
                messagebox.showinfo("Created", "Exam created. Add questions next.", parent=win)
            win.destroy()
            self._refresh_manage()

        btn_f = ttk.Frame(inner)
        btn_f.pack(fill="x", pady=15)
        ttk.Button(btn_f, text="Save", command=_save).pack(side="right", padx=5)
        ttk.Button(btn_f, text="Cancel", command=win.destroy).pack(side="right")

    def _publish_exam(self):
        eid = self._get_selected_exam_id()
        if eid:
            if self.svc.get_question_count(eid) == 0:
                messagebox.showwarning("No Questions", "Add questions before publishing.")
                return
            self.svc.publish_exam(eid)
            self._refresh_manage()

    def _unpublish_exam(self):
        eid = self._get_selected_exam_id()
        if eid:
            self.svc.unpublish_exam(eid)
            self._refresh_manage()

    def _delete_exam(self):
        eid = self._get_selected_exam_id()
        if eid and messagebox.askyesno("Delete", "Delete this exam and all its data?"):
            self.svc.delete_exam(eid)
            self._refresh_manage()

    def _export_csv(self):
        eid = self._get_selected_exam_id()
        if not eid:
            return
        csv_data = self.svc.export_results_csv(eid)
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")])
        if path:
            with open(path, "w") as f:
                f.write(csv_data)
            messagebox.showinfo("Export", f"Results exported to {path}")

    def _view_exam_results(self):
        eid = self._get_selected_exam_id()
        if not eid:
            return
        results = self.svc.get_exam_results(eid)
        exam = self.svc.get_exam(eid)

        win = tk.Toplevel(self.root)
        win.title(f"Results — {exam['title']}")
        win.geometry("700x400")

        cols = ("Student", "Score", "Percentage", "Result", "Submitted", "Status")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c)
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        for r in results:
            tree.insert("", "end", values=(
                r.get("student_name", r["student_id"]),
                f"{r.get('score', '-')}/{exam['total_marks']}",
                f"{r.get('percentage', '-')}%",
                "PASS" if r.get("passed") else "FAIL",
                r.get("submitted_at", ""), r["status"],
            ))

        ttk.Button(win, text="Close", command=win.destroy).pack(pady=5)

    # ── Question Management ─────────────────────────────────────────

    def _manage_questions(self):
        eid = self._get_selected_exam_id()
        if not eid:
            return
        exam = self.svc.get_exam(eid)

        win = tk.Toplevel(self.root)
        win.title(f"Questions — {exam['title']}")
        win.geometry("900x550")
        win.transient(self.root)

        cols = ("ID", "Type", "Question", "Marks", "Difficulty")
        q_tree = ttk.Treeview(win, columns=cols, show="headings", height=12)
        for c in cols:
            q_tree.heading(c, text=c)
        q_tree.column("ID", width=40)
        q_tree.column("Type", width=90)
        q_tree.column("Question", width=450)
        q_tree.column("Marks", width=60)
        q_tree.column("Difficulty", width=80)
        q_tree.pack(fill="both", expand=True, padx=10, pady=10)

        def refresh():
            for item in q_tree.get_children():
                q_tree.delete(item)
            for q in self.svc.get_questions(eid):
                q_tree.insert("", "end", values=(
                    q["id"], q["question_type"],
                    q["question_text"][:80], q["marks"], q.get("difficulty", ""),
                ))

        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))

        def add_q():
            self._question_form(eid, None, refresh)

        def edit_q():
            sel = q_tree.selection()
            if sel:
                qid = q_tree.item(sel[0])["values"][0]
                self._question_form(eid, qid, refresh)

        def del_q():
            sel = q_tree.selection()
            if sel and messagebox.askyesno("Delete", "Delete this question?", parent=win):
                qid = q_tree.item(sel[0])["values"][0]
                self.svc.delete_question(qid)
                refresh()

        ttk.Button(btn_frame, text="Add Question", command=add_q).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Edit", command=edit_q).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Delete", command=del_q).pack(side="left", padx=2)

        refresh()

    def _question_form(self, exam_id, question_id, on_save):
        existing = None
        if question_id:
            qs = self.svc.get_questions(exam_id)
            existing = next((q for q in qs if q["id"] == question_id), None)

        win = tk.Toplevel(self.root)
        win.title("Edit Question" if existing else "Add Question")
        win.geometry("600x550")
        win.transient(self.root)
        f = ttk.Frame(win, padding=15)
        f.pack(fill="both", expand=True)

        ttk.Label(f, text="Question Type:").pack(anchor="w")
        type_var = tk.StringVar(value=existing["question_type"] if existing else "mcq")
        type_combo = ttk.Combobox(f, textvariable=type_var,
                                  values=[t[0] for t in QUESTION_TYPES],
                                  state="readonly", width=20)
        type_combo.pack(anchor="w", pady=(0, 8))

        ttk.Label(f, text="Question Text:").pack(anchor="w")
        q_text = tk.Text(f, height=4, wrap=tk.WORD)
        q_text.pack(fill="x", pady=(0, 8))
        if existing:
            q_text.insert("1.0", existing["question_text"])

        ttk.Label(f, text="Options (one per line, for MCQ):").pack(anchor="w")
        opts_text = tk.Text(f, height=4, wrap=tk.WORD)
        opts_text.pack(fill="x", pady=(0, 8))
        if existing and existing.get("options"):
            opts_text.insert("1.0", "\n".join(existing["options"]))

        ttk.Label(f, text="Correct Answer:").pack(anchor="w")
        ans_var = tk.StringVar(value=existing.get("correct_answer", "") if existing else "")
        ttk.Entry(f, textvariable=ans_var, width=50).pack(fill="x", pady=(0, 8))

        row = ttk.Frame(f)
        row.pack(fill="x", pady=(0, 8))
        ttk.Label(row, text="Marks:").pack(side="left")
        marks_var = tk.StringVar(value=str(existing["marks"]) if existing else "1")
        ttk.Spinbox(row, from_=0.5, to=100, increment=0.5, textvariable=marks_var,
                     width=8).pack(side="left", padx=10)
        ttk.Label(row, text="Difficulty:").pack(side="left", padx=(20, 0))
        diff_var = tk.StringVar(value=existing.get("difficulty", "medium") if existing else "medium")
        ttk.Combobox(row, textvariable=diff_var,
                      values=["easy", "medium", "hard"], state="readonly",
                      width=10).pack(side="left", padx=5)

        ttk.Label(f, text="Explanation (shown after grading):").pack(anchor="w")
        expl_text = tk.Text(f, height=2, wrap=tk.WORD)
        expl_text.pack(fill="x", pady=(0, 8))
        if existing and existing.get("explanation"):
            expl_text.insert("1.0", existing["explanation"])

        def _save_q():
            text = q_text.get("1.0", tk.END).strip()
            if not text:
                messagebox.showerror("Validation", "Question text is required.", parent=win)
                return
            opts_raw = opts_text.get("1.0", tk.END).strip()
            options = [o.strip() for o in opts_raw.split("\n") if o.strip()] if opts_raw else None

            data = {
                "question_type": type_var.get(),
                "question_text": text,
                "options": options,
                "correct_answer": ans_var.get().strip() or None,
                "marks": float(marks_var.get()),
                "difficulty": diff_var.get(),
                "explanation": expl_text.get("1.0", tk.END).strip() or None,
            }

            if existing:
                self.svc.update_question(question_id, **data)
            else:
                self.svc.add_question(exam_id, **data)
            win.destroy()
            on_save()

        btn_f = ttk.Frame(f)
        btn_f.pack(fill="x", pady=10)
        ttk.Button(btn_f, text="Save", command=_save_q).pack(side="right", padx=5)
        ttk.Button(btn_f, text="Cancel", command=win.destroy).pack(side="right")

    # ── Grading Tab ─────────────────────────────────────────────────

    def _build_grading_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Grading")

        header = ttk.Frame(tab)
        header.pack(fill="x", padx=10, pady=10)
        ttk.Label(header, text="Manual Grading Queue", font=("Arial", 14, "bold")).pack(side="left")
        ttk.Button(header, text="Refresh", command=self._refresh_grading).pack(side="right")

        cols = ("ID", "Exam", "Student", "Submitted", "Score", "Status")
        self.grading_tree = ttk.Treeview(tab, columns=cols, show="headings", height=10)
        for c in cols:
            self.grading_tree.heading(c, text=c)
        self.grading_tree.column("ID", width=40)
        self.grading_tree.column("Exam", width=200)
        self.grading_tree.column("Student", width=120)
        self.grading_tree.column("Submitted", width=150)
        self.grading_tree.column("Score", width=80)
        self.grading_tree.column("Status", width=80)
        self.grading_tree.pack(fill="both", expand=True, padx=10)

        ttk.Button(tab, text="Grade Selected", command=self._grade_attempt).pack(padx=10, pady=10, anchor="w")
        self._refresh_grading()

    def _refresh_grading(self):
        for item in self.grading_tree.get_children():
            self.grading_tree.delete(item)
        attempts = self.svc.get_ungraded_attempts()
        for a in attempts:
            self.grading_tree.insert("", "end", values=(
                a["id"], a.get("exam_title", ""), a.get("student_name", a["student_id"]),
                a.get("submitted_at", ""), a.get("score", "-"), a["status"],
            ))

    def _grade_attempt(self):
        sel = self.grading_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select an attempt to grade.")
            return
        attempt_id = self.grading_tree.item(sel[0])["values"][0]
        attempt = self.svc.get_attempt(attempt_id)
        if not attempt:
            return

        questions = self.svc.get_questions(attempt["exam_id"])
        answers = self.svc.get_answers(attempt_id)
        answer_map = {a["question_id"]: a for a in answers}

        win = tk.Toplevel(self.root)
        win.title(f"Grade — {attempt.get('student_name', attempt['student_id'])}")
        win.geometry("800x600")

        canvas = tk.Canvas(win, highlightthickness=0)
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas, padding=10)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        mark_widgets = []
        for i, q in enumerate(questions, 1):
            a = answer_map.get(q["id"], {})
            frame = ttk.LabelFrame(inner, text=f"Q{i}. {q['question_type'].upper()} ({q['marks']} marks)")
            frame.pack(fill="x", pady=5, padx=5)

            ttk.Label(frame, text=q["question_text"], wraplength=700).pack(anchor="w", padx=5, pady=2)
            ttk.Label(frame, text=f"Answer: {a.get('answer_text', '(none)')}",
                      wraplength=700).pack(anchor="w", padx=5)
            if q.get("correct_answer"):
                ttk.Label(frame, text=f"Model answer: {q['correct_answer']}",
                          foreground="green").pack(anchor="w", padx=5)

            row = ttk.Frame(frame)
            row.pack(fill="x", padx=5, pady=5)
            ttk.Label(row, text="Marks:").pack(side="left")
            mark_var = tk.StringVar(value=str(a.get("marks_awarded", 0) or 0))
            ttk.Spinbox(row, from_=0, to=q["marks"], increment=0.5,
                         textvariable=mark_var, width=8).pack(side="left", padx=5)
            ttk.Label(row, text=f"/ {q['marks']}").pack(side="left")

            ttk.Label(row, text="Feedback:").pack(side="left", padx=(20, 5))
            fb_var = tk.StringVar(value=a.get("feedback", "") or "")
            ttk.Entry(row, textvariable=fb_var, width=30).pack(side="left", fill="x", expand=True)

            mark_widgets.append((a.get("id"), mark_var, fb_var))

        def _save_grades():
            for answer_id, mark_var, fb_var in mark_widgets:
                if answer_id:
                    self.svc.grade_answer(answer_id, float(mark_var.get()), fb_var.get())
            result = self.svc.finalise_grading(attempt_id, self._user.get("username", ""))
            messagebox.showinfo("Graded",
                                f"Score: {result['score']} ({result['percentage']}%)\n"
                                f"Result: {'PASSED' if result['passed'] else 'FAILED'}",
                                parent=win)
            win.destroy()
            self._refresh_grading()

        ttk.Button(inner, text="Save Grades & Finalise", command=_save_grades).pack(pady=15)

    # ── Analytics Tab ───────────────────────────────────────────────

    def _build_analytics_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Analytics")

        header = ttk.Frame(tab)
        header.pack(fill="x", padx=10, pady=10)
        ttk.Label(header, text="Exam Analytics", font=("Arial", 14, "bold")).pack(side="left")

        # Exam selector
        ttk.Label(header, text="Select Exam:").pack(side="left", padx=(30, 5))
        self._analytics_exam_var = tk.StringVar()
        self._analytics_combo = ttk.Combobox(header, textvariable=self._analytics_exam_var,
                                              state="readonly", width=40)
        self._analytics_combo.pack(side="left", padx=5)
        ttk.Button(header, text="Load", command=self._load_analytics).pack(side="left", padx=5)

        self._analytics_text = scrolledtext.ScrolledText(tab, wrap=tk.WORD, font=("Courier", 10))
        self._analytics_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Populate exam list
        exams = self.svc.list_exams()
        self._analytics_exam_map = {f"{e['id']}: {e['title']}": e["id"] for e in exams}
        self._analytics_combo["values"] = list(self._analytics_exam_map.keys())

    def _load_analytics(self):
        key = self._analytics_exam_var.get()
        eid = self._analytics_exam_map.get(key)
        if not eid:
            return

        analytics = self.svc.get_exam_analytics(eid)
        self._analytics_text.config(state=tk.NORMAL)
        self._analytics_text.delete("1.0", tk.END)

        text = f"""EXAM ANALYTICS
{'='*50}

Total Attempts:  {analytics['total_attempts']}
Average Score:   {analytics['average_score']}%
Min Score:       {analytics['min_score']}%
Max Score:       {analytics['max_score']}%
Pass Count:      {analytics['pass_count']}
Pass Rate:       {analytics['pass_rate']}%

QUESTION ANALYSIS
{'='*50}
{'#':<4} {'Type':<12} {'Marks':<7} {'Correct%':<10} {'Avg Marks':<10} Question
{'-'*80}
"""
        for i, q in enumerate(analytics["questions"], 1):
            text += f"{i:<4} {q['type']:<12} {q['marks']:<7} {q['difficulty_pct']:<10} {q['avg_marks']:<10} {q['text']}\n"

        self._analytics_text.insert("1.0", text)
        self._analytics_text.config(state=tk.DISABLED)

    def run(self):
        if hasattr(self.root, "mainloop"):
            self.root.mainloop()


def launch_exam_portal(auth=None):
    """Launch the exam portal GUI."""
    gui = ExamPortalGUI(auth=auth)
    gui.run()
