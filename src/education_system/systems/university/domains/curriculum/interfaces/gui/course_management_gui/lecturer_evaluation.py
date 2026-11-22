"""
University Lecturer Evaluation

Students rate each lecturer who teaches them on a module, once, while the
module's survey is open. Lecturers read their own feedback (once enough
students have answered) and reflect on it; line managers, module leaders
and admins see what they are entitled to. Every rule is in
``university/application/evaluation/lecturer`` and ``lecturer_feedback``.

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity; there is no in-app login screen.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import logging
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

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
    """Resolve the logged-in user dict from EDU_AUTH_* env vars.

    Mirrors the pattern used by complaints_portal.py — the main GUI sets
    these env vars on subprocess launch, so we read them directly to
    avoid silent failures inside the auth-infra import chain.
    """
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
    """Return (display_name, student_id) for the logged-in user.

    Looks up the student row in `students` joined to `users` so we get
    the student-facing student_id (e.g. S12345) rather than the auth PK.
    Falls back to env values when the DB lookup misses.
    """
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
# Every rule lives in ``university/application/evaluation/lecturer`` (window,
# eligibility, anonymity, screening, reminders, reflections) and
# ``lecturer_feedback`` (who sees what, thresholds, trends). This module only
# presents them.

STAFF_ROLES = ('admin', 'administrator', 'superadmin', 'staff', 'instructor', 'lecturer',
               'faculty', 'teacher')
STATE_LABELS = {"open": "Open — please rate", "answered": "Done — thank you",
                "scheduled": "Not open yet", "closed": "Closed",
                "closed_marks": "Closed (marks released)"}
TITLE = "Lecturer evaluation"


def _rules():
    from education_system.systems.university.application.evaluation import (
        lecturer as lecturer_evaluation,
    )
    return lecturer_evaluation


def _feedback():
    from education_system.systems.university.application.evaluation import lecturer_feedback
    return lecturer_feedback


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
        logger.exception("lecturer evaluation action failed")
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


def _text_window(parent, title, text, size="760x520"):
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry(size)
    box = scrolledtext.ScrolledText(win, wrap="word")
    box.pack(fill="both", expand=True, padx=8, pady=8)
    box.insert("1.0", text)
    box.configure(state="disabled")
    return win


# ---------------------------------------------------------------------------
# STUDENTS
# ---------------------------------------------------------------------------
class StudentView:
    def __init__(self, notebook, student_id, full_name):
        self.student_id = student_id
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Rate your lecturers")
        ttk.Label(tab, wraplength=900, justify="left", text=(
            f"Hello {full_name}. While a module's survey is open you can rate each lecturer who "
            "teaches it, once. It is anonymous: lecturers never see who said what, and nothing "
            "is shown until enough students have answered.")).pack(anchor="w", padx=8, pady=6)
        self.tree = _tree(tab, [("module", "Module"), ("lecturer", "Lecturer"),
                                ("year", "Year"), ("state", "Status"), ("closes", "Closes")],
                          [220, 200, 90, 180, 100], height=12)
        self.tree.bind("<Double-1>", lambda _e: self.rate())
        _bar(tab, (("Rate selected lecturer", self.rate), ("Refresh", self.load)))
        loop = ttk.Frame(notebook)
        notebook.add(loop, text="You said, we did")
        self.loop = _tree(loop, [("who", "Lecturer"), ("module", "Module"),
                                 ("said", "You said"), ("did", "We did")],
                          [160, 90, 330, 330], height=16)
        self.root = tab
        self.load()

    def load(self):
        rows = _call(self.root, _rules().student_lecturers, self.student_id, write=True) or []
        self.rows = {str(i): r for i, r in enumerate(rows)}
        self.tree.delete(*self.tree.get_children())
        for iid, r in self.rows.items():
            self.tree.insert("", "end", iid=iid, values=(
                f"{r['module_code']} {r['module_name'] or ''}", r["name"], r["academic_year"],
                STATE_LABELS.get(r["state"], r["state"]), r["closes"]))
        if not rows:
            self.tree.insert("", "end", values=("No module survey with lecturers yet", "", "",
                                                "", ""))
        self.loop.delete(*self.loop.get_children())
        for r in _call(self.root, _rules().published_for_student, self.student_id) or []:
            self.loop.insert("", "end", values=(r["name"], r["module_code"], r["you_said"],
                                                r["we_did"]))

    def rate(self):
        r = self.rows.get((self.tree.selection() or [""])[0])
        if not r:
            return
        if r["state"] != "open":
            messagebox.showinfo(TITLE, STATE_LABELS.get(r["state"], r["state"]),
                                parent=self.root)
            return
        win = tk.Toplevel(self.root)
        win.title(f"Rate {r['name']} — {r['module_code']} (anonymous)")
        body = ttk.Frame(win, padding=10)
        body.pack(fill="both", expand=True)
        ratings = {}
        for row, (key, label, desc) in enumerate(_rules().CRITERIA):
            ttk.Label(body, text=label, font=("Arial", 10, "bold")).grid(row=2 * row, column=0,
                                                                         sticky="w")
            ttk.Label(body, text=desc, foreground="#555555").grid(row=2 * row + 1, column=0,
                                                                  sticky="w")
            var = tk.IntVar(value=0)
            cell = ttk.Frame(body)
            cell.grid(row=2 * row, column=1, rowspan=2, sticky="w", padx=12)
            for value in range(1, 6):
                ttk.Radiobutton(cell, text=str(value), variable=var, value=value).pack(
                    side="left", padx=4)
            ratings[key] = var
        ttk.Label(body, text="Comments (optional)").grid(row=20, column=0, sticky="nw", pady=6)
        comments = tk.Text(body, width=60, height=4, wrap="word")
        comments.grid(row=20, column=1, sticky="w", pady=6)

        def submit():
            given = {k: v.get() for k, v in ratings.items() if v.get()}
            result = _call(win, _rules().submit, r["form_id"], r["lecturer"], self.student_id,
                           given, comments.get("1.0", "end-1c"), write=True)
            if result:
                messagebox.showinfo("Thank you", "Recorded anonymously."
                                    + ("\n\nYour comment will be checked before the lecturer "
                                       "sees it." if result["flagged"] else ""), parent=win)
                win.destroy()
                self.load()
        ttk.Button(body, text="Submit anonymously", command=submit).grid(row=21, column=1,
                                                                        sticky="w")


# ---------------------------------------------------------------------------
# STAFF
# ---------------------------------------------------------------------------
class StaffView:
    """Lecturers see their own feedback; line managers their reports';
    module leaders the lecturers on their modules; admins everyone."""

    def __init__(self, notebook, username, is_admin):
        self.username, self.is_admin = username, is_admin
        tab = ttk.Frame(notebook)
        self.root = tab
        notebook.add(tab, text="Lecturer feedback")
        ttk.Label(tab, wraplength=900, padding=(8, 4), text=(
            "Results for a lecturer on a module appear once enough students have rated them "
            "there. You see your own feedback, the people you line-manage, and the lecturers "
            "on modules you lead.")).pack(anchor="w")
        _bar(tab, (("Feedback…", self.show), ("Reflect / respond…", self.reflect),
                   ("Export CSV…", self.export), ("Send reminders", self.remind),
                   ("Refresh", self.load)))
        self.tree = _tree(tab, [("who", "Lecturer"), ("name", "Name"), ("why", "You see this as")],
                          [160, 300, 160], height=14)
        self.load()

    def load(self):
        self.tree.delete(*self.tree.get_children())
        for p in _call(self.root, _rules().visible_lecturers, self.username, self.is_admin) or []:
            self.tree.insert("", "end", iid=p["username"], values=(
                p["username"], p["name"], p["access"]))

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(TITLE, "Select a lecturer first.", parent=self.root)
        return sel[0] if sel else None

    def _result(self):
        lecturer = self._selected()
        return lecturer and _call(self.root, _feedback().results, lecturer, self.username,
                                  self.is_admin)

    def show(self):
        result = self._result()
        if not result:
            return
        lines = [f"{result['name']} ({result['lecturer']})", ""]
        comp = result["comparison"]
        lines.append(f"Overall this year: {result['by_year'].get(result['academic_year'], {}).get('overall', '—')}"
                     f"   ·   last year: {comp['last_year'] or '—'}   ·   department "
                     f"({comp['department']['lecturers']} other lecturer(s)): "
                     f"{comp['department']['overall'] or '—'}")
        lines.append("Trend: " + ", ".join(f"{t['academic_year']} {t['overall'] or '—'} "
                                           f"({t['responses']})" for t in result["trend"]))
        for m in result["modules"]:
            lines += ["", f"{m['module_code']} {m['academic_year']}: {m['responses']} of "
                          f"{m['invited']} rated"]
            if m["withheld"]:
                lines.append(f"  Hidden until {m['threshold']} students have answered.")
                continue
            for key, label, _d in _rules().CRITERIA:
                dist = " ".join(str(m["distribution"][key][i]) for i in range(1, 6))
                lines.append(f"  {label:<24} {m['means'][key]:>5}   [1–5: {dist}]")
            lines += [f"  • {c}" for c in m["comments"]] or ["  No comments."]
        _text_window(self.root, f"Feedback — {result['name']}", "\n".join(lines), "860x600")

    def export(self):
        result = self._result()
        if not result:
            return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".csv",
                                            initialfile=f"{result['lecturer']}-feedback.csv")
        if path:
            _feedback().export_csv(result, path)
            messagebox.showinfo(TITLE, f"Saved to {path}", parent=self.root)

    def remind(self):
        result = _call(self.root, _rules().send_reminders, write=True)
        if result:
            messagebox.showinfo(TITLE, f"Reminded {result['sent']} student(s) with lecturers "
                                "still to rate.", parent=self.root)

    def reflect(self):
        lecturer = self._selected()
        if not lecturer:
            return
        if lecturer != self.username and not self.is_admin:
            records = _call(self.root, _rules().reflections, lecturer, self.username,
                            self.is_admin) or []
            _text_window(self.root, f"Reflections — {lecturer}", "\n\n".join(
                f"{r['module_code']} {r['academic_year']}\n{r['reflection']}\nActions: "
                f"{r['actions'] or '—'}" for r in records) or "No reflections yet.")
            return
        result = _call(self.root, _feedback().results, lecturer, self.username, self.is_admin)
        modules = [m for m in (result or {}).get("modules", [])]
        if not modules:
            messagebox.showinfo(TITLE, "There is no feedback to reflect on yet.",
                                parent=self.root)
            return
        self._reflect_dialog(lecturer, modules)

    def _reflect_dialog(self, lecturer, modules):
        win = tk.Toplevel(self.root)
        win.title(f"Reflect on feedback — {lecturer}")
        choice = ttk.Combobox(win, state="readonly", width=40, values=[
            f"{m['form_id']}: {m['module_code']} {m['academic_year']}" for m in modules])
        choice.grid(row=0, column=1, sticky="w", padx=6, pady=4)
        ttk.Label(win, text="Module survey").grid(row=0, column=0, sticky="w", padx=6)
        boxes = {}
        for row, (key, label) in enumerate((("reflection", "Reflection (seen by you, your line "
                                                           "manager and the module leader)"),
                                            ("actions", "Actions"),
                                            ("you_said", "You said (for students)"),
                                            ("we_did", "We did (for students)")), 1):
            ttk.Label(win, text=label, wraplength=220).grid(row=row, column=0, sticky="nw",
                                                            padx=6, pady=3)
            boxes[key] = tk.Text(win, width=64, height=3, wrap="word")
            boxes[key].grid(row=row, column=1, padx=6, pady=3)

        def save(publish):
            if not choice.get():
                return
            form_id = int(choice.get().split(":")[0])
            v = {k: b.get("1.0", "end-1c").strip() for k, b in boxes.items()}
            rid = _call(win, _rules().reflect, form_id, lecturer, v["reflection"], v["actions"],
                        v["you_said"], v["we_did"], self.username, self.is_admin, write=True)
            if rid and publish:
                sent = _call(win, _rules().publish_reflection, rid, self.username,
                             self.is_admin, write=True)
                if sent:
                    messagebox.showinfo(TITLE, f"Sent to {sent['notified']} student(s).",
                                        parent=win)
            if rid:
                win.destroy()
        buttons = ttk.Frame(win)
        buttons.grid(row=6, column=1, sticky="w", padx=6, pady=6)
        ttk.Button(buttons, text="Save", command=lambda: save(False)).pack(side="left")
        ttk.Button(buttons, text="Save and publish to students",
                   command=lambda: save(True)).pack(side="left", padx=6)


# ---------------------------------------------------------------------------
# ADMIN
# ---------------------------------------------------------------------------
class AdminView:
    def __init__(self, notebook, username):
        self.username = username
        review = ttk.Frame(notebook)
        notebook.add(review, text="Comments to review")
        self.root = review
        ttk.Label(review, padding=6, wraplength=900, text=(
            "Comments that matched a screening rule wait here; the lecturer only sees a "
            "comment once it is released.")).pack(anchor="w")
        self.review = _tree(review, [("who", "Lecturer"), ("module", "Module"),
                                     ("why", "Held because"), ("text", "Comment")],
                            [120, 90, 180, 500], height=14)
        _bar(review, (("Release", lambda: self.decide(True)),
                      ("Withhold", lambda: self.decide(False))))
        links = ttk.Frame(notebook)
        notebook.add(links, text="Instructor logins")
        ttk.Label(links, padding=6, wraplength=900, text=(
            "Timetabled instructors are rated through their staff record's login. Instructors "
            "whose email matched a staff record were linked automatically; link the rest here.")).pack(
            anchor="w")
        self.links = _tree(links, [("id", "Id"), ("name", "Instructor"), ("email", "Email"),
                                   ("user", "Login")], [60, 220, 260, 160], height=12)
        _bar(links, (("Link to login…", self.link), ("Unlink", lambda: self.link(clear=True))))
        self.load()

    def load(self):
        self.review.delete(*self.review.get_children())
        for r in _call(self.root, _rules().review_queue) or []:
            self.review.insert("", "end", iid=str(r["evaluation_id"]), values=(
                r["lecturer"], r["module_code"], r["reason"], r["comments"]))
        self.links.delete(*self.links.get_children())
        for i in _call(self.root, _rules().instructors) or []:
            self.links.insert("", "end", iid=str(i["id"]), values=(
                i["id"], i["name"], i["email"] or "", i["username"] or "— not linked —"))

    def decide(self, release):
        sel = self.review.selection()
        if sel and _call(self.root, _rules().review_comment, int(sel[0]), release,
                         self.username, write=True):
            self.load()

    def link(self, clear=False):
        from tkinter import simpledialog
        sel = self.links.selection()
        if not sel:
            return
        username = "" if clear else simpledialog.askstring(TITLE, "Staff username:",
                                                           parent=self.root)
        if username is not None and _call(self.root, _rules().link_instructor, int(sel[0]),
                                          username, True, write=True):
            self.load()


# ---------------------------------------------------------------------------
# APP
# ---------------------------------------------------------------------------
class App:
    def __init__(self, host=None):
        """Lecturer Evaluation app.

        ``host`` may be ``None`` (subprocess: creates and owns ``tk.Tk()``;
        ``run()`` enters mainloop) or a workspace tab ``Frame`` (embedded;
        the caller owns the mainloop and ``run()`` is a no-op).
        """
        self.user = _get_current_user()
        if host is None:
            self.root = tk.Tk()
            self._owns_root = True
            self.root.title(_t('gui.academics.course_management_gui.lecturer_evaluation.windows.lecturer_evaluation', default="Lecturer Evaluation"))
            self.root.geometry("1000x680")
        else:
            self.root = host
            self._owns_root = False
        if not self.user:
            self._show_no_auth_screen()
            return
        full_name, student_id = _resolve_student_identity(self.user)
        role = str(self.user.get('role') or '').lower()
        username = self.user.get('username') or ''
        logger.info("Lecturer Evaluation starting user=%s role=%s", username, role or '<none>')
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)
        if role in STAFF_ROLES or _is_admin_user(self.user):
            admin = _is_admin_user(self.user)
            _call(self.root, _rules().send_reminders, write=True)
            StaffView(notebook, username, admin)
            if admin:
                AdminView(notebook, username)
        else:
            StudentView(notebook, student_id, full_name)

    def _show_no_auth_screen(self):
        ttk.Label(self.root, text=_t('gui.academics.course_management_gui.lecturer_evaluation.labels.authentication_required', default="🔒  Authentication Required"),
                  font=("Arial", 16, "bold")).pack(pady=(40, 10))
        ttk.Label(self.root, justify="center",
                  text=_t('gui.academics.course_management_gui.lecturer_evaluation.labels.please_launch_this_module_from_the_main_university_system_after', default="Please launch this module from the main\n"
                          "University System after signing in.")).pack(pady=10)
        ttk.Button(self.root, text=_t('gui.academics.course_management_gui.lecturer_evaluation.buttons.close', default="Close"),
                   command=self.root.destroy).pack(pady=20)

    def run(self):
        if self._owns_root:
            self.root.mainloop()


if __name__ == "__main__":
    App().run()
