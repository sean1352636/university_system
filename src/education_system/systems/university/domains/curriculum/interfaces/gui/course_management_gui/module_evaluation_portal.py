"""
University Module Evaluation Survey Portal

Students rate modules against a fixed Likert-scale questionnaire.
Admins can view aggregate response data.

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. The app dispatches straight to the survey
flow; there is no in-app login screen.

Persistence: rows live in the central university `student_records.db`.
The portal uses the existing `evaluation_forms`, `eval_form_questions`,
`eval_form_responses`, and `eval_form_answers` tables — exactly the
shape the survey needs — and reads the module catalog from `modules`.
On first use of a module within an academic year, an `evaluation_forms`
row is lazily created and seeded with the standard question set.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import hashlib
import json
import logging
import os
import sqlite3
import sys
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, scrolledtext
from education_system.systems.university.domains.curriculum.interfaces.gui.course_management_gui._student_enrolment import enrolment_summary

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


def _current_academic_year():
    """UK-style academic year string for today, e.g. '2025/2026'."""
    now = datetime.now()
    if now.month >= 9:
        return f"{now.year}/{now.year + 1}"
    return f"{now.year - 1}/{now.year}"


# ---------------------------------------------------------------------------
# RULES PLUMBING
# ---------------------------------------------------------------------------
# Every survey rule lives in ``university/application/evaluation/module``:
# the survey window, invitations, anonymity, screening, results and the
# response to students. This module only presents them.

STAFF_ROLES = ('admin', 'administrator', 'superadmin', 'staff', 'instructor', 'lecturer',
               'faculty', 'teacher')


def _rules():
    from education_system.systems.university.application.evaluation import (
        module as module_evaluation,
    )
    return module_evaluation


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
        messagebox.showerror("Module evaluation", str(exc), parent=parent)
        return None
    except Exception as exc:
        conn.rollback()
        logger.exception("module evaluation action failed")
        messagebox.showerror("Module evaluation", f"That did not work: {exc}", parent=parent)
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
    view = ttk.Treeview(frame, columns=[c for c, _t in columns], show="headings", height=height)
    for (key, title), width in zip(columns, widths):
        view.heading(key, text=title)
        view.column(key, width=width, anchor="w")
    bar = ttk.Scrollbar(frame, orient="vertical", command=view.yview)
    view.configure(yscrollcommand=bar.set)
    bar.pack(side="right", fill="y")
    view.pack(side="left", fill="both", expand=True)
    return view


STATE_LABELS = {"open": "Open — please respond", "answered": "Done — thank you",
                "scheduled": "Not open yet", "closed": "Closed",
                "closed_marks": "Closed (marks released)"}


class ModuleEvaluationPortal:
    def __init__(self, root):
        self.root = root
        if hasattr(self.root, "wm_title"):
            self.root.title(_t('gui.academics.course_management_gui.module_evaluation_portal.windows.university_module_evaluation_portal', default="University Module Evaluation Portal"))
            self.root.geometry("1000x680")
        self.user = _get_current_user()
        self.is_admin = _is_admin_user(self.user)
        role = str((self.user or {}).get('role') or '').lower()
        self.is_staff = self.is_admin or role in STAFF_ROLES
        self.full_name, self.student_id = _resolve_student_identity(self.user)
        self.username = (self.user or {}).get('username') or ''
        if not self.user:
            self.show_no_auth_screen()
            return
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)
        if self.is_staff:
            _call(self.root, _rules().send_reminders, write=True)
            self._build_staff()
            if self.is_admin:
                self._build_review()
                self._build_bank()
        else:
            self._build_student()

    def show_no_auth_screen(self):
        container = tk.Frame(self.root)
        container.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Label(container, text=_t('gui.academics.course_management_gui.module_evaluation_portal.labels.authentication_required', default="🔒 Authentication Required"),
                  font=("Helvetica", 18, "bold")).pack(pady=(0, 10))
        ttk.Label(container,
                  text=_t('gui.academics.course_management_gui.module_evaluation_portal.labels.please_launch_this_module_from_the_main_university_system_after', default="Please launch this module from the\n"
                       "main University System after signing in."),
                  justify="center").pack(pady=10)
        ttk.Button(container, text=_t('gui.academics.course_management_gui.module_evaluation_portal.buttons.close', default="Close"),
                   command=self.root.destroy).pack(pady=20)

    # ------------------------------------------------------------------
    # Students
    # ------------------------------------------------------------------
    def _build_student(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My module surveys")
        ttk.Label(tab, wraplength=900, justify="left", text=(
            f"Hello {self.full_name}. Surveys are anonymous: staff never see who said what, and "
            "results are only shown once enough students have answered.")).pack(
            anchor="w", padx=8, pady=6)
        self.survey_tree = _tree(tab, [("module", "Module"), ("name", "Name"), ("year", "Year"),
                                       ("state", "Status"), ("closes", "Closes")],
                                 [100, 300, 100, 200, 110], height=12)
        bar = ttk.Frame(tab)
        bar.pack(fill="x", padx=8, pady=4)
        ttk.Button(bar, text="Answer selected survey", command=self._start).pack(side="left")
        ttk.Button(bar, text="Refresh", command=self._load_student).pack(side="left", padx=6)
        loop = ttk.Frame(self.notebook)
        self.notebook.add(loop, text="You said, we did")
        self.loop_tree = _tree(loop, [("module", "Module"), ("year", "Year"),
                                      ("said", "You said"), ("did", "We did")],
                               [90, 90, 380, 380], height=16)
        self._load_student()

    def _load_student(self):
        rows = _call(self.root, _rules().student_surveys, self.student_id, write=True) or []
        self._surveys = {str(r["id"]): r for r in rows}
        self.survey_tree.delete(*self.survey_tree.get_children())
        for r in rows:
            self.survey_tree.insert("", "end", iid=str(r["id"]), values=(
                r["module_code"], r["module_name"], r["academic_year"],
                STATE_LABELS.get(r["state"], r["state"]), str(r["closes_at"] or "")[:10]))
        self.loop_tree.delete(*self.loop_tree.get_children())
        for i, r in enumerate(_call(self.root, _rules().published_for_student,
                                    self.student_id) or []):
            self.loop_tree.insert("", "end", iid=str(i), values=(
                r["module_code"], r["academic_year"], r["you_said"], r["we_did"]))

    def _start(self):
        survey = self._surveys.get((self.survey_tree.selection() or [""])[0])
        if not survey:
            return
        if survey["state"] != "open":
            messagebox.showinfo("Module evaluation", STATE_LABELS.get(survey["state"], ""),
                                parent=self.root)
            return
        qs = _call(self.root, _rules().questions, survey["id"]) or []
        win = tk.Toplevel(self.root)
        win.title(f"Evaluate {survey['module_code']} — anonymous")
        win.geometry("760x620")
        canvas = tk.Canvas(win, highlightthickness=0)
        bar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        body = ttk.Frame(canvas)
        body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=bar.set)
        buttons = ttk.Frame(win)
        buttons.pack(side="bottom", fill="x", padx=8, pady=6)
        bar.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        answers = {}
        for q in qs:
            frame = ttk.LabelFrame(body, text=q["question_text"]
                                   + ("" if q["is_required"] else "  (optional)"), padding=6)
            frame.pack(fill="x", padx=8, pady=4)
            if q["question_type"] == "text":
                box = tk.Text(frame, width=80, height=4, wrap="word")
                box.pack(fill="x")
                answers[q["id"]] = ("text", box)
                continue
            var = tk.IntVar(value=0)
            labels = _rules().LIKERT if q["question_type"] == "likert" else \
                ["1", "2", "3", "4", "5"]
            for value, label in enumerate(labels, start=1):
                ttk.Radiobutton(frame, text=label, variable=var, value=value).pack(
                    side="left", padx=6)
            answers[q["id"]] = ("rating", var)

        def submit():
            given = {}
            for qid, (kind, widget) in answers.items():
                if kind == "text":
                    given[qid] = (None, widget.get("1.0", "end-1c").strip() or None)
                else:
                    given[qid] = (widget.get() or None, None)
            result = _call(win, _rules().submit, survey["id"], self.student_id, given, write=True)
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
        self.notebook.add(tab, text="Module surveys")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", padx=8, pady=6)
        for label, command in (("Open / schedule a survey…", self._open_dialog),
                               ("Results…", self._results),
                               ("Respond to students…", self._respond),
                               ("Close now", self._close),
                               ("Send reminders", self._remind),
                               ("Refresh", self._load_staff)):
            ttk.Button(bar, text=label, command=command).pack(side="left", padx=2)
        self.form_tree = _tree(tab, [("module", "Module"), ("year", "Year"), ("state", "Status"),
                                     ("window", "Window"), ("resp", "Responses"),
                                     ("rate", "Response rate"), ("role", "You")],
                               [100, 90, 160, 200, 80, 100, 90], height=16)
        self._load_staff()

    def _load_staff(self):
        rows = _call(self.root, _rules().forms_for, staff=self.username, admin=self.is_admin) or []
        self._forms = {str(r["id"]): r for r in rows}
        self.form_tree.delete(*self.form_tree.get_children())
        for r in rows:
            rate = f"{r['responses'] / r['invited'] * 100:.0f}%" if r["invited"] else "—"
            self.form_tree.insert("", "end", iid=str(r["id"]), values=(
                r["module_code"], r["academic_year"],
                {"open": "Open"}.get(r["state"], STATE_LABELS.get(r["state"], r["state"])),
                f"{str(r.get('opens_at') or '')[:10]} → {str(r['closes_at'] or '')[:10]}",
                r["responses"], rate, "leader" if r["leads"] else "team"))

    def _selected_form(self):
        f = self._forms.get((self.form_tree.selection() or [""])[0])
        if not f:
            messagebox.showinfo("Module evaluation", "Select a survey first.", parent=self.root)
        return f

    def _my_modules(self, conn):
        from education_system.systems.university.application.modules import (
            delivery as module_delivery,
        )
        rows = conn.execute("SELECT module_code, module_name FROM modules WHERE "
                            "COALESCE(is_active, 1) = 1 AND TRIM(COALESCE(module_code, '')) <> '' "
                            "ORDER BY module_code").fetchall()
        return [f"{c} - {n or ''}" for c, n in rows
                if self.is_admin or module_delivery.is_leader(conn, c, self.username)]

    def _open_dialog(self):
        modules = _call(self.root, self._my_modules) or []
        if not modules:
            messagebox.showinfo("Module evaluation", "You do not lead any module. Module leaders "
                                "are set on Module Management's Team tab.", parent=self.root)
            return
        win = tk.Toplevel(self.root)
        win.title("Open a module survey")
        form = ttk.Frame(win, padding=10)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="Module").grid(row=0, column=0, sticky="w")
        module = ttk.Combobox(form, values=modules, width=40, state="readonly")
        module.grid(row=0, column=1, sticky="w", pady=2)
        opens, closes = tk.StringVar(), tk.StringVar()
        threshold = tk.StringVar(value="5")
        for row, (label, var) in enumerate((("Opens (YYYY-MM-DD)", opens),
                                            ("Closes (YYYY-MM-DD)", closes),
                                            ("Show results after (responses)", threshold)), 1):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w")
            ttk.Entry(form, textvariable=var, width=14).grid(row=row, column=1, sticky="w", pady=2)

        def suggest(_e=None):
            code = module.get().split(" - ")[0]
            window = _call(win, _rules().default_window, code)
            if window:
                opens.set(window[0].isoformat())
                closes.set(window[1].isoformat())
        module.bind("<<ComboboxSelected>>", suggest)
        staff_qs = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Also ask about each lecturer here (students already rate "
                                   "them in Lecturer Evaluation)",
                        variable=staff_qs).grid(row=4, column=1, sticky="w")
        ttk.Label(form, text="Extra questions from the bank\n(required ones are always "
                             "included)").grid(row=5, column=0, sticky="nw")
        bank_rows = _call(win, _rules().bank) or []
        bank_list = tk.Listbox(form, selectmode="multiple", height=6, width=60)
        for b in bank_rows:
            bank_list.insert("end", ("[required] " if b["required"] else "") + b["question_text"])
        bank_list.grid(row=5, column=1, sticky="w", pady=2)
        ttk.Label(form, text="Your own questions\n(one per line; start with 'text:' for a "
                             "written answer)").grid(row=6, column=0, sticky="nw")
        custom = tk.Text(form, width=60, height=4)
        custom.grid(row=6, column=1, sticky="w", pady=2)

        def open_it():
            code = module.get().split(" - ")[0]
            if not code:
                return
            lines = [ln.strip() for ln in custom.get("1.0", "end-1c").splitlines() if ln.strip()]
            extra = [(ln[5:].strip(), "text") if ln.lower().startswith("text:") else (ln, "likert")
                     for ln in lines]
            chosen = [bank_rows[i]["bank_id"] for i in bank_list.curselection()]
            result = _call(win, _rules().open_survey, code, opens_at=opens.get() or None,
                           closes_at=closes.get() or None, bank_ids=chosen, custom=extra,
                           include_staff=staff_qs.get(), min_responses=threshold.get(),
                           actor=self.username, write=True)
            if result:
                messagebox.showinfo("Survey opened", f"{code}: {result['opens']} → "
                                    f"{result['closes']}; {result['invited']} student(s) invited.",
                                    parent=win)
                win.destroy()
                self._load_staff()
        ttk.Button(form, text="Open survey", command=open_it).grid(row=7, column=1, sticky="w",
                                                                  pady=6)

    def _results(self):
        f = self._selected_form()
        result = f and _call(self.root, _rules().results, f["id"], self.username, self.is_admin)
        if not result:
            return
        win = tk.Toplevel(self.root)
        win.title(f"{f['module_code']} {f['academic_year']} — results")
        win.geometry("940x620")
        rate = f"{result['rate']}%" if result["rate"] is not None else "—"
        ttk.Label(win, padding=8, font=("Helvetica", 11, "bold"), text=(
            f"{result['responses']} response(s) from {result['invited']} invited ({rate}) · "
            f"{STATE_LABELS.get(result['state'], result['state'])}")).pack(anchor="w")
        if result["withheld"]:
            ttk.Label(win, padding=8, wraplength=880, text=(
                f"Results are hidden until {result['threshold']} students have answered, so "
                "that nobody can be identified from their answers.")).pack(anchor="w")
            return
        comp = result["comparison"]
        ttk.Label(win, padding=(8, 0), text=(
            f"Overall: {result['overall'] or '—'}   ·   last year: "
            f"{comp['last_year'] and round(comp['last_year'], 2) or '—'}   ·   department "
            f"({comp['department_modules']} modules): "
            f"{comp['department'] and round(comp['department'], 2) or '—'}")).pack(anchor="w")
        view = _tree(win, [("q", "Question"), ("scope", "About"), ("n", "Answers"),
                           ("mean", "Mean"), ("dist", "1 / 2 / 3 / 4 / 5")],
                     [420, 110, 70, 60, 160], height=12)
        for q in result["questions"]:
            view.insert("", "end", values=(
                q["question_text"], q["staff_username"] or "module", q["n"], q["mean"] or "—",
                " / ".join(str(q["distribution"][i]) for i in range(1, 6))))
        ttk.Label(win, text="Comments:", padding=(8, 4)).pack(anchor="w")
        box = scrolledtext.ScrolledText(win, height=7, wrap="word")
        box.pack(fill="both", expand=True, padx=8, pady=(0, 6))
        box.insert("1.0", "\n\n".join(f"• {c}" for c in result["comments"]) or "No comments.")
        box.configure(state="disabled")

        def export():
            from tkinter import filedialog
            path = filedialog.asksaveasfilename(parent=win, defaultextension=".csv",
                                                initialfile=f"{f['module_code']}-evaluation.csv")
            if path:
                _rules().export_csv(result, path)
                messagebox.showinfo("Export", f"Saved to {path}", parent=win)
        ttk.Button(win, text="Export results (CSV)", command=export).pack(anchor="w", padx=8,
                                                                         pady=4)

    def _respond(self):
        f = self._selected_form()
        if not f:
            return
        if not f["leads"]:
            messagebox.showinfo("Module evaluation", "Only the module leader responds to the "
                                "students.", parent=self.root)
            return
        win = tk.Toplevel(self.root)
        win.title(f"Respond to {f['module_code']} students")
        boxes = {}
        for row, (key, label) in enumerate((("summary", "What the results told us"),
                                            ("actions", "Actions we will take"),
                                            ("you_said", "You said (for students)"),
                                            ("we_did", "We did / will do (for students)"))):
            ttk.Label(win, text=label).grid(row=row, column=0, sticky="nw", padx=6, pady=3)
            boxes[key] = tk.Text(win, width=70, height=3, wrap="word")
            boxes[key].grid(row=row, column=1, padx=6, pady=3)
        records = _call(win, _rules().loop_records, f["id"]) or []
        ttk.Label(win, text="Earlier responses: " + (", ".join(
            f"#{r['id']} ({'published' if r['published'] else 'draft'})" for r in records)
            or "none")).grid(row=4, column=1, sticky="w", padx=6)

        def save(publish):
            values = {k: b.get("1.0", "end-1c").strip() for k, b in boxes.items()}
            rid = _call(win, _rules().respond, f["id"], values["summary"], values["actions"],
                        values["you_said"], values["we_did"], self.username, write=True)
            if rid and publish:
                result = _call(win, _rules().publish, rid, self.username, write=True)
                if result:
                    messagebox.showinfo("Published", f"Sent to {result['notified']} student "
                                        "email address(es) and their inboxes.", parent=win)
            if rid:
                win.destroy()
        buttons = ttk.Frame(win)
        buttons.grid(row=5, column=1, sticky="w", padx=6, pady=6)
        ttk.Button(buttons, text="Save draft", command=lambda: save(False)).pack(side="left")
        ttk.Button(buttons, text="Save and publish to students",
                   command=lambda: save(True)).pack(side="left", padx=6)

    def _close(self):
        f = self._selected_form()
        if f and messagebox.askyesno("Close survey", f"Close the {f['module_code']} survey now?",
                                     parent=self.root):
            _call(self.root, _rules().close_survey, f["id"], write=True)
            self._load_staff()

    def _remind(self):
        result = _call(self.root, _rules().send_reminders, write=True)
        if result:
            messagebox.showinfo("Reminders", f"{result['sent']} reminder(s) sent to students "
                                "who have not answered yet.", parent=self.root)

    # ------------------------------------------------------------------
    # Admin
    # ------------------------------------------------------------------
    def _build_review(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Comments to review")
        ttk.Label(tab, padding=6, wraplength=900, text=(
            "Comments that matched a screening rule are held here. Staff only see a comment "
            "once it is released.")).pack(anchor="w")
        self.review_tree = _tree(tab, [("module", "Module"), ("why", "Held because"),
                                       ("text", "Comment")], [100, 200, 600], height=14)
        bar = ttk.Frame(tab)
        bar.pack(fill="x", padx=8, pady=4)
        ttk.Button(bar, text="Release to staff", command=lambda: self._review(True)).pack(
            side="left")
        ttk.Button(bar, text="Withhold", command=lambda: self._review(False)).pack(
            side="left", padx=6)
        self._load_review()

    def _load_review(self):
        self.review_tree.delete(*self.review_tree.get_children())
        for r in _call(self.root, _rules().review_queue) or []:
            self.review_tree.insert("", "end", iid=str(r["answer_id"]), values=(
                r["module_code"], r["reason"], r["text_value"]))

    def _review(self, release):
        sel = self.review_tree.selection()
        if sel and _call(self.root, _rules().review_comment, int(sel[0]), release,
                         self.username, write=True):
            self._load_review()

    def _build_bank(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Required questions")
        ttk.Label(tab, padding=6, wraplength=900, text=(
            "Questions marked required are added to every module survey opened from now on.")
        ).pack(anchor="w")
        self.bank_tree = _tree(tab, [("q", "Question"), ("type", "Type"),
                                     ("req", "Required")], [600, 100, 90], height=14)
        bar = ttk.Frame(tab)
        bar.pack(fill="x", padx=8, pady=4)
        ttk.Button(bar, text="Make required", command=lambda: self._required(True)).pack(
            side="left")
        ttk.Button(bar, text="Make optional", command=lambda: self._required(False)).pack(
            side="left", padx=6)
        self._load_bank()

    def _load_bank(self):
        self.bank_tree.delete(*self.bank_tree.get_children())
        for b in _call(self.root, _rules().bank) or []:
            self.bank_tree.insert("", "end", iid=str(b["bank_id"]), values=(
                b["question_text"], b["question_type"], "yes" if b["required"] else ""))

    def _required(self, required):
        sel = self.bank_tree.selection()
        if sel and _call(self.root, _rules().set_required, int(sel[0]), required, write=True):
            self._load_bank()


def main():
    root = tk.Tk()
    ModuleEvaluationPortal(root)
    root.mainloop()


if __name__ == "__main__":
    main()
