"""
University Course Evaluation

Once a year the students on a course (programme) rate the course as a
whole. Students answer the survey for their own course; the course leader
opens and closes it and responds to students; the course team (including
the leaders of the course's modules) reads results; admins also review
held comments, choose the required questions and rebuild staff teaching
history. Every rule is in ``university/application/evaluation/course``.

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity; there is no in-app login screen.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import logging
import os
import sys
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, scrolledtext, ttk

logger = logging.getLogger(__name__)


# When the main GUI launches us as a subprocess, the child Python is
# invoked directly on this file's path with no PYTHONPATH set, so
# `education_system` isn't importable. Walk up from this file until we
# find the dir that contains the `education_system` package and put
# that on sys.path. No-op when imported normally.
if 'education_system' not in sys.modules:
    _here = os.path.abspath(os.path.dirname(__file__))
    while _here and not os.path.isdir(os.path.join(_here, 'education_system')):
        _parent = os.path.dirname(_here)
        if _parent == _here:
            break
        _here = _parent
    if _here and _here not in sys.path:
        sys.path.insert(0, _here)


try:
    from education_system.systems.university.infrastructure.logging.log_config import configure_logging
    configure_logging(name=__name__)
except Exception:
    logger.debug("Central log config unavailable; falling back to default handlers", exc_info=True)


# ---------------------------------------------------------------------------
# AUTH BOOTSTRAP
# ---------------------------------------------------------------------------
def _get_current_user():
    """Resolve the logged-in user dict from EDU_AUTH_* env vars."""
    user_id = os.environ.get('EDU_AUTH_USER_ID') or ''
    username = os.environ.get('EDU_AUTH_USERNAME') or ''
    role = os.environ.get('EDU_AUTH_ROLE') or ''
    email = os.environ.get('EDU_AUTH_EMAIL') or ''
    perms_raw = os.environ.get('EDU_AUTH_PERMISSIONS') or ''

    if user_id or username:
        return {
            'id': user_id or None,
            'user_id': user_id or None,
            'username': username,
            'role': role,
            'email': email,
            'permissions': [p for p in perms_raw.split(',') if p],
        }

    try:
        from education_system.systems.university.infrastructure.auth import get_global_auth
        ga = get_global_auth()
        if ga and getattr(ga, 'current_user', None):
            return ga.current_user
    except Exception:
        logger.debug("get_global_auth fallback failed", exc_info=True)
    return None


def _is_admin_user(user):
    if not user:
        return False
    return (user.get('role') or '').lower() in ('admin', 'administrator', 'superadmin')


def _resolve_student_identity(user):
    """Return (display_name, student_id) for the logged-in user."""
    if not user:
        return '', ''
    env_user_id = (user.get('user_id') or user.get('id') or '') or ''
    username = user.get('username') or ''
    full_name = ''
    resolved_sid = ''
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection
        conn = get_connection()
        cur = conn.cursor()
        row = None
        if env_user_id:
            row = cur.execute(
                "SELECT s.student_id, s.first_name, s.last_name "
                "FROM users u LEFT JOIN students s ON s.student_id = u.student_id "
                "WHERE u.id = ?", (env_user_id,)).fetchone()
        if not row and username:
            row = cur.execute(
                "SELECT s.student_id, s.first_name, s.last_name "
                "FROM users u LEFT JOIN students s ON s.student_id = u.student_id "
                "WHERE u.username = ?", (username,)).fetchone()
        if not row and env_user_id:
            row = cur.execute(
                "SELECT student_id, first_name, last_name FROM students WHERE student_id = ?",
                (env_user_id,)).fetchone()
        conn.close()
        if row:
            sid, first, last = row
            resolved_sid = str(sid or '')
            full_name = ' '.join(p for p in (first or '', last or '') if p).strip()
    except Exception:
        logger.debug("Student identity lookup failed", exc_info=True)

    if not full_name:
        full_name = username or env_user_id or 'Unknown User'
    return full_name, resolved_sid or env_user_id or username or ''


# ---------------------------------------------------------------------------
# RULES PLUMBING
# ---------------------------------------------------------------------------
# Every survey rule lives in ``university/application/evaluation/course``:
# eligibility, the window, anonymity, the threshold, screening, results and
# the response to students. This module only presents them.

STAFF_ROLES = ('admin', 'administrator', 'superadmin', 'staff', 'instructor', 'lecturer',
               'faculty', 'teacher')
STATE_LABELS = {"open": "Open — please respond", "answered": "Done — thank you",
                "scheduled": "Not open yet", "closed": "Closed"}
TITLE = "Course evaluation"


def _rules():
    from education_system.systems.university.application.evaluation import (
        course as course_evaluation,
    )
    return course_evaluation


def _call(parent, fn, *args, write=False, **kwargs):
    """Run a rule in its own transaction; a refusal becomes a dialog (None)."""
    from education_system.systems.university.application.teaching import (
        occurrences as timetable_occurrences,
    )
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection(row_factory=False)
    try:
        result = fn(conn, *args, **kwargs)
        if write:
            conn.commit()
    except ValueError as exc:
        conn.rollback()
        messagebox.showerror(TITLE, str(exc), parent=parent)
        return None
    except Exception as exc:
        conn.rollback()
        logger.exception("course evaluation action failed")
        messagebox.showerror(TITLE, f"That did not work: {exc}", parent=parent)
        return None
    finally:
        conn.close()
    emails = result.get("emails") if isinstance(result, dict) else None
    if write and emails:
        timetable_occurrences.send_emails(emails)
    return True if result is None else result


def _tree(parent, columns, widths, height=8):
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True, padx=6, pady=4)
    view = ttk.Treeview(frame, columns=[c for c, _h in columns], show="headings", height=height)
    for (key, title), width in zip(columns, widths):
        view.heading(key, text=title)
        view.column(key, width=width, anchor="w")
    bar = ttk.Scrollbar(frame, orient="vertical", command=view.yview)
    view.configure(yscrollcommand=bar.set)
    bar.pack(side="right", fill="y")
    view.pack(side="left", fill="both", expand=True)
    return view


def _bar(parent, buttons):
    bar = ttk.Frame(parent)
    bar.pack(fill="x", padx=8, pady=6)
    for label, command in buttons:
        ttk.Button(bar, text=label, command=command).pack(side="left", padx=2)
    return bar


class _QuestionForm:
    """The answer form for one survey: one widget per question type, no
    pre-selected rating, and branching questions shown only when their
    condition is met."""

    def __init__(self, body, questions, on_change):
        self.questions = questions
        self.frames, self.values = {}, {}
        for row, q in enumerate(questions):
            frame = ttk.LabelFrame(body, padding=6, text=q["question_text"]
                                   + ("" if q["is_required"] else "  (optional)"))
            self.frames[q["question_id"]] = (row, frame)
            self.values[q["question_id"]] = self._widget(frame, q, on_change)
        self.refresh()

    @staticmethod
    def _widget(frame, q, on_change):
        kind = q["question_type"]
        if kind == "text":
            box = tk.Text(frame, width=80, height=4, wrap="word")
            box.pack(fill="x")
            return ("text", box)
        if kind in _rules().NUMERIC:
            var = tk.IntVar(value=0)
            low, high = q["scale_min"], q["scale_max"]
            ttk.Label(frame, text="Strongly disagree" if kind == "likert" else "Poor").pack(
                side="left")
            for value in range(low, high + 1):
                ttk.Radiobutton(frame, text=str(value), variable=var, value=value,
                                command=on_change).pack(side="left", padx=6)
            ttk.Label(frame, text="Strongly agree" if kind == "likert" else "Excellent").pack(
                side="left")
            return ("number", var)
        var = tk.StringVar(value="")
        for choice in q["choices"]:
            ttk.Radiobutton(frame, text=choice, variable=var, value=choice,
                            command=on_change).pack(side="left", padx=6)
        return ("choice", var)

    def answers(self) -> dict:
        given = {}
        for qid, (kind, widget) in self.values.items():
            if kind == "text":
                value = widget.get("1.0", "end-1c").strip()
            else:
                value = widget.get()
            if value not in ("", 0):
                given[qid] = value
        return given

    def refresh(self):
        given = self.answers()
        for q in self.questions:
            row, frame = self.frames[q["question_id"]]
            if _rules().should_show(q, given):
                frame.grid(row=row, column=0, sticky="ew", padx=8, pady=4)
            else:
                frame.grid_remove()


class CourseEvaluationApp:
    def __init__(self, root):
        self.root = root
        # When ``root`` is a workspace tab Frame (passed by
        # ``open_in_workspace``), it has no ``wm_title`` — skip window chrome.
        if hasattr(self.root, "wm_title"):
            self.root.title(_t('gui.academics.course_management_gui.course_evaluation_system.windows.university_course_evaluation_system', default="University Course Evaluation System"))
            try:
                already_sized = (self.root.winfo_width() > 1000
                                 and self.root.winfo_height() > 700)
            except tk.TclError:
                already_sized = False
            if not already_sized:
                self.root.geometry("1000x680")
        self.user = _get_current_user()
        self.is_admin = _is_admin_user(self.user)
        role = str((self.user or {}).get('role') or '').lower()
        self.is_staff = self.is_admin or role in STAFF_ROLES
        self.full_name, self.student_id = _resolve_student_identity(self.user)
        self.username = (self.user or {}).get('username') or ''
        self.create_header()
        if not self.user:
            self._show_no_auth()
            return
        logger.info("Course Evaluation starting user=%s admin=%s", self.username, self.is_admin)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)
        if self.is_staff:
            _call(self.root, _rules().send_reminders, write=True)
            self._build_staff()
            self._build_team()
            if self.is_admin:
                self._build_review()
                self._build_bank()
                self._build_history()
        else:
            self._build_student()

    def _show_no_auth(self):
        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=40, pady=60)
        ttk.Label(body, text=_t('gui.academics.course_management_gui.course_evaluation_system.labels.authentication_required', default="🔒 Authentication Required"),
                  font=("Arial", 16, "bold")).pack(pady=(40, 10))
        ttk.Label(body,
                  text=_t('gui.academics.course_management_gui.course_evaluation_system.labels.please_launch_this_module_from_the_main_university_system_after', default="Please launch this module from the main\n"
                       "University System after signing in."),
                  justify="center").pack(pady=10)
        ttk.Button(body, text=_t('gui.academics.course_management_gui.course_evaluation_system.buttons.close', default="Close"),
                   command=self.root.destroy).pack(pady=20)

    def create_header(self):
        header = tk.Frame(self.root, bg="#f0f0f0", height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=_t('gui.academics.course_management_gui.course_evaluation_system.labels.university_course_evaluation_system', default="🎓 University Course Evaluation System"),
                 font=("Arial", 16, "bold"), bg="#f0f0f0", fg="#000000"
                 ).pack(side="left", padx=20, pady=14)
        if self.user:
            tk.Label(header, text=f"👤 {self.full_name}", font=("Arial", 10), bg="#f0f0f0",
                     fg="#555555").pack(side="right", padx=20, pady=18)
        if self.is_admin:
            tk.Button(header, text=_t('gui.academics.course_management_gui.course_evaluation_system.buttons.operations', default="Operations…"), bg="#f0f0f0",
                      command=self._launch_operations).pack(side="right", padx=4, pady=16)
            tk.Button(header, text=_t('gui.academics.course_management_gui.course_evaluation_system.buttons.survey_designer', default="Survey Designer…"), bg="#f0f0f0",
                      command=self._launch_designer).pack(side="right", padx=4, pady=16)

    def _launch_designer(self):
        try:
            from education_system.systems.university.domains.curriculum.interfaces.gui.course_management_gui.course_evaluation_designer import (
                launch_survey_designer,
            )
        except ImportError as e:
            messagebox.showerror(_t('gui.academics.course_management_gui.course_evaluation_system.dialogs.survey_designer', default="Survey Designer"), str(e))
            return
        launch_survey_designer(self.root, getattr(self, "auth", None))

    def _launch_operations(self):
        try:
            from education_system.systems.university.domains.curriculum.interfaces.gui.course_management_gui.course_evaluation_operations import (
                launch_operations_gui,
            )
        except ImportError as e:
            messagebox.showerror(_t('gui.academics.course_management_gui.course_evaluation_system.dialogs.operations', default="Operations"), str(e))
            return
        launch_operations_gui(self.root, getattr(self, "auth", None))

    # ------------------------------------------------------------------
    # Students
    # ------------------------------------------------------------------
    def _build_student(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My course survey")
        ttk.Label(tab, wraplength=900, justify="left", text=(
            f"Hello {self.full_name}. Once a year you are asked about your course as a whole. "
            "The survey is anonymous: staff never see who said what, and results are only "
            "shown once enough students have answered.")).pack(anchor="w", padx=8, pady=6)
        self.survey_tree = _tree(tab, [("course", "Course"), ("year", "Year"),
                                       ("state", "Status"), ("closes", "Closes")],
                                 [120, 120, 220, 120], height=10)
        _bar(tab, (("Answer selected survey", self._start), ("Refresh", self._load_student)))
        loop = ttk.Frame(self.notebook)
        self.notebook.add(loop, text="You said, we did")
        self.loop_tree = _tree(loop, [("year", "Year"), ("said", "You said"),
                                      ("did", "We did"), ("summary", "What the results told us")],
                               [90, 280, 280, 300], height=16)
        self._load_student()

    def _load_student(self):
        rows = _call(self.root, _rules().student_surveys, self.student_id, write=True) or []
        self._surveys = {str(r["evaluation_id"]): r for r in rows}
        self.survey_tree.delete(*self.survey_tree.get_children())
        for r in rows:
            self.survey_tree.insert("", "end", iid=str(r["evaluation_id"]), values=(
                r["course_code"], r["academic_year"], STATE_LABELS.get(r["state"], r["state"]),
                str(r["end_date"] or "")[:10]))
        if not rows:
            self.survey_tree.insert("", "end", values=("", "", "No course survey for you yet",
                                                       ""))
        self.loop_tree.delete(*self.loop_tree.get_children())
        for i, r in enumerate(_call(self.root, _rules().published_for_student,
                                    self.student_id) or []):
            self.loop_tree.insert("", "end", iid=str(i), values=(
                r["academic_year"], r["you_said"], r["we_did"], r["summary"]))

    def _start(self):
        survey = self._surveys.get((self.survey_tree.selection() or [""])[0])
        if not survey:
            return
        if survey["state"] != "open":
            messagebox.showinfo(TITLE, STATE_LABELS.get(survey["state"], ""), parent=self.root)
            return
        qs = _call(self.root, _rules().questions, survey["evaluation_id"]) or []
        win = tk.Toplevel(self.root)
        win.title(f"Your course: {survey['course_code']} — anonymous")
        win.geometry("820x640")
        canvas = tk.Canvas(win, highlightthickness=0)
        bar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        body = ttk.Frame(canvas)
        body.columnconfigure(0, weight=1)
        body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=bar.set)
        buttons = ttk.Frame(win)
        buttons.pack(side="bottom", fill="x", padx=8, pady=6)
        bar.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        form = _QuestionForm(body, qs, on_change=lambda: form.refresh())

        def submit():
            result = _call(win, _rules().submit, survey["evaluation_id"], self.student_id,
                           form.answers(), write=True)
            if result:
                messagebox.showinfo("Thank you", "Your response has been recorded anonymously."
                                    + ("\n\nOne or more comments will be checked before staff "
                                       "see them." if result["flagged"] else ""), parent=win)
                win.destroy()
                self._load_student()
        ttk.Button(buttons, text="Submit anonymously", command=submit).pack(side="left")
        ttk.Button(buttons, text="Cancel", command=win.destroy).pack(side="left", padx=6)

    # ------------------------------------------------------------------
    # Staff
    # ------------------------------------------------------------------
    def _build_staff(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Course surveys")
        _bar(tab, (("Open / schedule a survey…", self._open_dialog), ("Results…", self._results),
                   ("Respond to students…", self._respond), ("Close now", self._close),
                   ("Send reminders", self._remind), ("Refresh", self._load_staff)))
        self.staff_note = ttk.Label(tab, padding=(8, 0), wraplength=900)
        self.staff_note.pack(anchor="w")
        self.form_tree = _tree(tab, [("course", "Course"), ("year", "Year"), ("state", "Status"),
                                     ("window", "Window"), ("resp", "Responses"),
                                     ("rate", "Response rate"), ("role", "You")],
                               [90, 90, 120, 200, 80, 100, 110], height=16)
        self._load_staff()

    def _load_staff(self):
        rows = _call(self.root, _rules().surveys, viewer=self.username, admin=self.is_admin) or []
        self._forms = {str(r["evaluation_id"]): r for r in rows}
        self.form_tree.delete(*self.form_tree.get_children())
        for r in rows:
            rate = f"{r['responses'] / r['invited'] * 100:.0f}%" if r["invited"] else "—"
            self.form_tree.insert("", "end", iid=str(r["evaluation_id"]), values=(
                r["course_code"], r["academic_year"],
                "Open" if r["state"] == "open" else STATE_LABELS.get(r["state"], r["state"]),
                f"{str(r['start_date'] or '')[:10]} → {str(r['end_date'] or '')[:10]}",
                r["responses"], rate, r["access"]))
        self.staff_note.configure(text="" if rows else (
            "You are not on any course team yet. An admin adds course leaders and team members "
            "on the Course team tab; module leaders see their course automatically."))

    def _selected_form(self):
        f = self._forms.get((self.form_tree.selection() or [""])[0])
        if not f:
            messagebox.showinfo(TITLE, "Select a survey first.", parent=self.root)
        return f

    def _my_courses(self, conn):
        rules = _rules()
        return [f"{c['code']} - {c['name'] or ''}" for c in rules.courses(conn)
                if self.is_admin or rules.leader(conn, c["code"]) == self.username]

    def _open_dialog(self):
        courses = _call(self.root, self._my_courses) or []
        if not courses:
            messagebox.showinfo(TITLE, "Only a course leader or an admin opens course surveys. "
                                "Course leaders are set on the Course team tab.", parent=self.root)
            return
        templates = _call(self.root, _rules().templates) or []
        window = _call(self.root, _rules().default_window) or ("", "")
        win = tk.Toplevel(self.root)
        win.title("Open a course survey")
        form = ttk.Frame(win, padding=10)
        form.pack(fill="both", expand=True)
        course = ttk.Combobox(form, values=courses, width=44, state="readonly")
        template = ttk.Combobox(form, width=44, state="readonly", values=[
            f"{t['template_id']}: {t['template_name']}" + (" (default)" if t["is_default"] else "")
            for t in templates])
        opens, closes = tk.StringVar(value=str(window[0])), tk.StringVar(value=str(window[1]))
        threshold = tk.StringVar(value="5")
        rows = (("Course", course), ("Questions from template\n(blank = default form)", template),
                ("Opens (YYYY-MM-DD)", ttk.Entry(form, textvariable=opens, width=14)),
                ("Closes (YYYY-MM-DD)", ttk.Entry(form, textvariable=closes, width=14)),
                ("Show results after (responses)", ttk.Entry(form, textvariable=threshold,
                                                             width=14)))
        for row, (label, widget) in enumerate(rows):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="nw", pady=2)
            widget.grid(row=row, column=1, sticky="w", pady=2)
        ttk.Label(form, wraplength=460, foreground="#555555", text=(
            "The institution's required questions, an overall satisfaction question and a "
            "comments box are added if the template lacks them. Questions are fixed once the "
            "first student answers.")).grid(row=5, column=0, columnspan=2, sticky="w", pady=4)

        def open_it():
            code = course.get().split(" - ")[0]
            if not code:
                return
            chosen = template.get().split(":")[0] or None
            result = _call(win, _rules().open_survey, code, template_id=chosen,
                           opens_at=opens.get() or None, closes_at=closes.get() or None,
                           min_responses=threshold.get(), actor=self.username,
                           admin=self.is_admin, write=True)
            if result:
                messagebox.showinfo("Survey opened", f"{code}: {result['opens']} → "
                                    f"{result['closes']}; {result['invited']} student(s) invited.",
                                    parent=win)
                win.destroy()
                self._load_staff()
        ttk.Button(form, text="Open survey", command=open_it).grid(row=6, column=1, sticky="w",
                                                                  pady=6)

    def _results(self):
        f = self._selected_form()
        result = f and _call(self.root, _rules().results, f["evaluation_id"], self.username,
                             self.is_admin)
        if not result:
            return
        win = tk.Toplevel(self.root)
        win.title(f"{f['course_code']} {f['academic_year']} — results")
        win.geometry("980x680")
        rate = f"{result['rate']}%" if result["rate"] is not None else "—"
        ttk.Label(win, padding=8, font=("Helvetica", 11, "bold"), text=(
            f"{result['responses']} response(s) from {result['invited']} invited ({rate}) · "
            f"{'Open' if result['state'] == 'open' else STATE_LABELS.get(result['state'], result['state'])}"
        )).pack(anchor="w")
        if result["withheld"]:
            ttk.Label(win, padding=8, wraplength=900, text=(
                f"Results are hidden until {result['threshold']} students have answered, so "
                "that nobody can be identified from their answers.")).pack(anchor="w")
        else:
            self._result_body(win, f, result)
        self._module_rollup(win, result["modules"])

    def _result_body(self, win, f, result):
        comp = result["comparison"]
        ttk.Label(win, padding=(8, 0), text=(
            f"Overall: {result['overall'] or '—'}   ·   last year: {comp['last_year'] or '—'}"
            f"   ·   department ({comp['department_courses']} other course(s)): "
            f"{comp['department'] or '—'}")).pack(anchor="w")
        view = _tree(win, [("q", "Question"), ("n", "Answers"), ("mean", "Mean"),
                           ("dist", "Spread")], [460, 70, 60, 300], height=9)
        for q in result["questions"]:
            view.insert("", "end", values=(
                q["question_text"], q["n"], q["mean"] or "—",
                " / ".join(f"{k}: {v}" for k, v in q["distribution"].items())))
        ttk.Label(win, text="Comments:", padding=(8, 4)).pack(anchor="w")
        box = scrolledtext.ScrolledText(win, height=6, wrap="word")
        box.pack(fill="both", expand=True, padx=8, pady=(0, 6))
        box.insert("1.0", "\n\n".join(f"• {c}" for c in result["comments"]) or "No comments.")
        box.configure(state="disabled")

        def export():
            from tkinter import filedialog
            path = filedialog.asksaveasfilename(
                parent=win, defaultextension=".csv",
                initialfile=f"{f['course_code']}-course-survey.csv")
            if path:
                _rules().export_csv(result, path)
                messagebox.showinfo("Export", f"Saved to {path}", parent=win)
        ttk.Button(win, text="Export results (CSV)", command=export).pack(anchor="w", padx=8,
                                                                         pady=4)

    @staticmethod
    def _module_rollup(win, modules):
        ttk.Label(win, text="Module surveys on this course this year:",
                  padding=(8, 4)).pack(anchor="w")
        view = _tree(win, [("m", "Module"), ("n", "Responses"), ("o", "Overall")],
                     [420, 100, 100], height=5)
        for m in modules:
            view.insert("", "end", values=(
                f"{m['module_code']} {m['module_name'] or ''}", f"{m['responses']}/{m['invited']}",
                "hidden (too few)" if m["withheld"] else (m["overall"] or "—")))

    def _respond(self):
        f = self._selected_form()
        if not f:
            return
        if f["access"] not in ("admin", "leader"):
            messagebox.showinfo(TITLE, "Only the course leader responds to the students.",
                                parent=self.root)
            return
        win = tk.Toplevel(self.root)
        win.title(f"Respond to {f['course_code']} students")
        boxes = {}
        for row, (key, label) in enumerate((("summary", "What the results told us"),
                                            ("actions", "Actions we will take"),
                                            ("you_said", "You said (for students)"),
                                            ("we_did", "We did / will do (for students)"))):
            ttk.Label(win, text=label).grid(row=row, column=0, sticky="nw", padx=6, pady=3)
            boxes[key] = tk.Text(win, width=70, height=3, wrap="word")
            boxes[key].grid(row=row, column=1, padx=6, pady=3)
        records = _call(win, _rules().loop_records, f["evaluation_id"]) or []
        ttk.Label(win, text="Earlier responses: " + (", ".join(
            f"#{r['id']} ({'published' if r['published'] else 'draft'})" for r in records)
            or "none")).grid(row=4, column=1, sticky="w", padx=6)

        def save(publish):
            values = {k: b.get("1.0", "end-1c").strip() for k, b in boxes.items()}
            rid = _call(win, _rules().respond, f["evaluation_id"], values["summary"],
                        values["actions"], values["you_said"], values["we_did"],
                        self.username, self.is_admin, write=True)
            if rid and publish:
                result = _call(win, _rules().publish, rid, self.username, self.is_admin,
                               write=True)
                if result:
                    messagebox.showinfo("Published", f"Sent to {result['notified']} student(s) "
                                        "by inbox and email.", parent=win)
            if rid:
                win.destroy()
        buttons = ttk.Frame(win)
        buttons.grid(row=5, column=1, sticky="w", padx=6, pady=6)
        ttk.Button(buttons, text="Save draft", command=lambda: save(False)).pack(side="left")
        ttk.Button(buttons, text="Save and publish to students",
                   command=lambda: save(True)).pack(side="left", padx=6)

    def _close(self):
        f = self._selected_form()
        if f and messagebox.askyesno("Close survey", f"Close the {f['course_code']} survey now?",
                                     parent=self.root):
            _call(self.root, _rules().close_survey, f["evaluation_id"], self.username,
                  self.is_admin, write=True)
            self._load_staff()

    def _remind(self):
        result = _call(self.root, _rules().send_reminders, write=True)
        if result:
            messagebox.showinfo("Reminders", f"{result['sent']} reminder(s) sent to students "
                                "who have not answered yet.", parent=self.root)

    # ------------------------------------------------------------------
    # Course team
    # ------------------------------------------------------------------
    def _build_team(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Course team")
        top = ttk.Frame(tab, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Course").pack(side="left")
        codes = [f"{c['code']} - {c['name'] or ''}" for c in _call(self.root,
                                                                   _rules().courses) or []]
        self.team_course = ttk.Combobox(top, values=codes, width=40, state="readonly")
        self.team_course.pack(side="left", padx=6)
        self.team_course.bind("<<ComboboxSelected>>", lambda _e: self._load_team())
        ttk.Label(tab, padding=(8, 0), wraplength=900, text=(
            "The course leader opens the survey and responds to students; the team and the "
            "leaders of the course's modules can read the results.")).pack(anchor="w")
        buttons = [("Add member…", lambda: self._add_member("member")),
                   ("Remove", self._remove_member)]
        if self.is_admin:
            buttons.insert(0, ("Set leader…", lambda: self._add_member("leader")))
        _bar(tab, buttons)
        self.team_tree = _tree(tab, [("user", "Username"), ("name", "Name"), ("role", "Role")],
                               [160, 300, 160], height=12)

    def _team_code(self):
        return self.team_course.get().split(" - ")[0]

    def _load_team(self):
        self.team_tree.delete(*self.team_tree.get_children())
        code = self._team_code()
        for p in (_call(self.root, _rules().team, code) or []) if code else []:
            self.team_tree.insert("", "end", iid=p["username"], values=(
                p["username"], p["name"], p["role"]))

    def _may_edit_team(self, conn, code):
        return self.is_admin or _rules().leader(conn, code) == self.username

    def _add_member(self, role):
        from tkinter import simpledialog
        code = self._team_code()
        if not code or not _call(self.root, self._may_edit_team, code):
            messagebox.showinfo(TITLE, "Pick a course you lead (admins can edit any course).",
                                parent=self.root)
            return
        username = simpledialog.askstring(TITLE, f"Staff username to add as {role}:",
                                          parent=self.root)
        if username and _call(self.root, _rules().set_team_member, code, username, role,
                              self.username, write=True):
            self._load_team()

    def _remove_member(self):
        code, sel = self._team_code(), self.team_tree.selection()
        if not (code and sel) or not _call(self.root, self._may_edit_team, code):
            return
        if _call(self.root, _rules().remove_team_member, code, sel[0], write=True):
            self._load_team()

    # ------------------------------------------------------------------
    # Admin
    # ------------------------------------------------------------------
    def _build_review(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Comments to review")
        ttk.Label(tab, padding=6, wraplength=900, text=(
            "Comments that matched a screening rule are held here. The course team only sees "
            "a comment once it is released.")).pack(anchor="w")
        self.review_tree = _tree(tab, [("course", "Course"), ("why", "Held because"),
                                       ("text", "Comment")], [100, 200, 600], height=14)
        _bar(tab, (("Release to staff", lambda: self._review(True)),
                   ("Withhold", lambda: self._review(False))))
        self._load_review()

    def _load_review(self):
        self.review_tree.delete(*self.review_tree.get_children())
        for r in _call(self.root, _rules().review_queue) or []:
            self.review_tree.insert("", "end", iid=str(r["answer_id"]), values=(
                r["course_code"], r["reason"], r["text_value"]))

    def _review(self, release):
        sel = self.review_tree.selection()
        if sel and _call(self.root, _rules().review_comment, int(sel[0]), release,
                         self.username, write=True):
            self._load_review()

    def _build_bank(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Required questions")
        ttk.Label(tab, padding=6, wraplength=900, text=(
            "Questions marked required are added to every course and module survey opened "
            "from now on.")).pack(anchor="w")
        self.bank_tree = _tree(tab, [("q", "Question"), ("type", "Type"),
                                     ("req", "Required")], [600, 100, 90], height=14)
        _bar(tab, (("Make required", lambda: self._required(True)),
                   ("Make optional", lambda: self._required(False))))
        self._load_bank()

    def _load_bank(self):
        from education_system.systems.university.application.evaluation import (
            module as module_evaluation,
        )
        self.bank_tree.delete(*self.bank_tree.get_children())
        for b in _call(self.root, module_evaluation.bank) or []:
            self.bank_tree.insert("", "end", iid=str(b["bank_id"]), values=(
                b["question_text"], b["question_type"], "yes" if b["required"] else ""))

    def _required(self, required):
        from education_system.systems.university.application.evaluation import (
            module as module_evaluation,
        )
        sel = self.bank_tree.selection()
        if sel and _call(self.root, module_evaluation.set_required, int(sel[0]), required,
                         write=True):
            self._load_bank()

    def _build_history(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Teaching history")
        ttk.Label(tab, padding=6, wraplength=900, text=(
            "Per member of staff and year, from module surveys that met their anonymity "
            "threshold: the overall rating of modules they lead and the questions about them "
            "by name.")).pack(anchor="w")
        self.history_year = tk.StringVar(value=_current_academic_year())
        bar = _bar(tab, (("Rebuild for year", self._rebuild_history),))
        ttk.Entry(bar, textvariable=self.history_year, width=12).pack(side="left", padx=6)
        self.history_tree = _tree(tab, [("who", "Staff"), ("year", "Year"),
                                        ("overall", "Modules led (overall)"),
                                        ("teaching", "About them"), ("forms", "Surveys"),
                                        ("resp", "Responses")],
                                  [160, 100, 160, 110, 80, 90], height=14)
        self._load_history()

    def _load_history(self):
        self.history_tree.delete(*self.history_tree.get_children())
        for i, r in enumerate(_call(self.root, _rules().instructor_history) or []):
            self.history_tree.insert("", "end", iid=str(i), values=(
                r["instructor_id"], r["academic_year"], r["avg_overall_rating"] or "—",
                r["avg_teaching_effectiveness"] or "—", r["total_evaluations"],
                r["total_responses"]))

    def _rebuild_history(self):
        count = _call(self.root, _rules().refresh_instructor_history,
                      self.history_year.get().strip(), write=True)
        if count is not None:
            self._load_history()


def _current_academic_year():
    now = datetime.now()
    start = now.year if now.month >= 9 else now.year - 1
    return f"{start}/{start + 1}"


def main():
    root = tk.Tk()
    CourseEvaluationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
