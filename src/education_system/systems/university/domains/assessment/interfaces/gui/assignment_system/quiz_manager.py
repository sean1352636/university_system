"""Quizzes, in the Assignment GUI with the rest of the assessed work.

Quizzes used to be a sub-tab of the LMS tab in Course Management, storing to
``lms_quizzes`` — a table separate from ``assignments``, where every other
piece of a module's assessed work lives, and separate again from
``exam_portal_*``, the platform's actual quiz engine.

A quiz created here is an ``assignments`` row like any other (so it appears in
Manage Assignments, the student's My Assignments, grading, late policies and
the rest), backed by an ``exam_portal_exams`` row that holds the questions and
the sitting. See ``domain.services.assignments.quiz_service``.
"""

import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

from education_system.systems.university.domains.assessment.interfaces.gui.assignment_system._dialogs import (
    make_toplevel,
    messagebox,
)
from education_system.systems.university.domains.assessment.domain.assignments import (
    quiz_service,
)
from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH, get_connection, sqlite3

QUESTION_TYPES = ("multiple_choice", "true_false", "short_answer", "essay")


class QuizManager:
    """Create, list and delete quizzes from the Assignment GUI."""

    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.tree = None

    # ------------------------------------------------------------------
    def _check_permission(self, permission):
        checker = getattr(self.gui, "_check_permission", None)
        if callable(checker):
            return checker(permission)
        return True

    def _creator(self):
        """Who to record as the author — a users.id or username; the service
        resolves either."""
        current = getattr(self.auth, "current_user", None) if self.auth else None
        if isinstance(current, dict):
            return current.get("id") or current.get("username")
        return None

    def _modules(self):
        """Module codes a quiz can be attached to.

        ``assignments.module_code`` is a foreign key onto ``modules``, so the
        list has to come from there — a free-text box would fail the
        constraint on anything that is not a real module.
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT module_code, module_name FROM modules "
                    "WHERE COALESCE(TRIM(module_code), '') <> '' "
                    "ORDER BY module_code"
                ).fetchall()
            return [(r[0], r[1] or "") for r in rows]
        except Exception:
            logger.warning("could not load modules for the quiz form", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Manage
    # ------------------------------------------------------------------
    def show_my_quizzes(self):
        """The published quizzes on a student's modules. They are sat in the
        Exam portal, which owns timing, marking and accommodations."""
        from education_system.systems.university.domains.assessment.domain.assignments.assignment_rules import quizzes as student_quizzes
        self.gui.layout.clear_content_area()
        area = self.gui.layout.content_area
        ttk.Label(area, text=_t('gui.academics.assignment_system.quiz_manager.labels.my_quizzes', default="My Quizzes"),
                  style='Title.TLabel').pack(anchor='w', pady=(0, 10))
        student_id = self.gui._get_student_id()
        if not student_id:
            ttk.Label(area, text="Your account has no student record, so there are no quizzes to sit.").pack(anchor='w')
            return
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        try:
            rows = student_quizzes.for_student(conn, student_id)
        except Exception as e:
            messagebox.showerror("My Quizzes", f"Could not load your quizzes: {e}")
            return
        finally:
            conn.close()
        cols = ("Quiz", "Module", "Duration", "Closes", "Attempts Left", "Status")
        tree = ttk.Treeview(area, columns=cols, show='headings', height=14)
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=240 if col == "Quiz" else 110)
        tree.pack(fill='both', expand=True)
        for row in rows:
            tree.insert('', tk.END, values=(
                row["title"], row["module_code"],
                f'{row["minutes"]} min' if row["minutes"] else "—", row["closes"] or "—",
                row["attempts_left"], row["state"]))
        if not rows:
            ttk.Label(area, text="You have no quizzes to sit at the moment.").pack(anchor='w', pady=5)
        ttk.Button(area, text=_t('gui.academics.assignment_system.quiz_manager.buttons.open_exam_portal', default="Sit a Quiz in the Exam Portal"),
                   command=self._open_exam_portal).pack(anchor='w', pady=10)

    def _open_exam_portal(self):
        from education_system.systems.university.domains.assessment.interfaces.gui.exam_management.exam_portal_gui import ExamPortalGUI
        window = make_toplevel(self.root)
        window.title("Exam Portal")
        window.geometry("1400x900")
        window.minsize(1200, 800)
        ExamPortalGUI(parent=window, auth=self.auth)

    def publish_quiz(self):
        """Open the selected quiz to students."""
        assignment_id, _title = self._selected()
        if not assignment_id:
            return
        exam_id = quiz_service.exam_id_for_assignment(assignment_id)
        if not exam_id:
            messagebox.showerror("Publish Quiz", "This quiz has no exam behind it.")
            return
        from education_system.systems.university.domains.assessment.domain.exam_management.exam_service import ExamPortalService
        try:
            done = ExamPortalService().publish_exam(exam_id)
        except ValueError as refused:
            messagebox.showwarning("Publish Quiz", str(refused))
            return
        if done:
            messagebox.showinfo("Publish Quiz", "Published. Students can now sit it from My Quizzes.")
        else:
            messagebox.showwarning("Publish Quiz", "It couldn't be published. Check it has questions.")

    def show_quizzes(self):
        """List every quiz, with its question count and backing exam."""
        if not self._check_permission('manage_assignments'):
            return

        self.gui.layout.clear_content_area()
        area = self.gui.layout.content_area

        ttk.Label(area, text=_t('gui.academics.assignment_system.quiz_manager.labels.quizzes',
                                default="Quizzes"), style='Title.TLabel').pack(anchor='w', pady=(0, 6))
        ttk.Label(
            area,
            text=_t('gui.academics.assignment_system.quiz_manager.labels.blurb',
                    default="Quizzes are assignments, so they also appear in Manage "
                            "Assignments and in students' My Assignments."),
            foreground="#7f8c8d",
        ).pack(anchor='w', pady=(0, 14))

        # Action bar before the table, so it keeps its height.
        actions = ttk.Frame(area)
        actions.pack(fill='x', pady=(0, 10))
        ttk.Button(actions, text=_t('gui.academics.assignment_system.quiz_manager.buttons.create_quiz', default="➕ Create Quiz"),
                   command=self.show_create_quiz).pack(side='left', padx=5)
        ttk.Button(actions, text=_t('gui.academics.assignment_system.quiz_manager.buttons.manage_questions', default="📝 Manage Questions"),
                   command=self.manage_questions).pack(side='left', padx=5)
        ttk.Button(actions, text=_t('gui.academics.assignment_system.quiz_manager.buttons.delete_quiz', default="🗑 Delete Quiz"),
                   command=self.delete_quiz).pack(side='left', padx=5)
        ttk.Button(actions, text=_t('gui.academics.assignment_system.quiz_manager.buttons.publish_quiz', default="Publish to Students"),
                   command=self.publish_quiz).pack(side='left', padx=5)
        ttk.Button(actions, text=_t('common.refresh', default="🔄 Refresh"),
                   command=self.show_quizzes).pack(side='left', padx=5)

        box = ttk.LabelFrame(area, text=_t('gui.academics.assignment_system.quiz_manager.labels.all_quizzes', default="All Quizzes"), padding=10)
        box.pack(fill='both', expand=True)

        cols = ("Assignment", "Module", "Title", "Questions", "Marks",
                "Duration", "Due", "Status")
        self.tree = ttk.Treeview(box, columns=cols, show='headings', height=16)
        widths = {"Assignment": 90, "Module": 110, "Title": 240, "Questions": 80,
                  "Marks": 70, "Duration": 80, "Due": 150, "Status": 80}
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=widths.get(col, 100))
        scroll = ttk.Scrollbar(box, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.tree.bind('<Double-1>', lambda e: self.manage_questions())

        quizzes = quiz_service.list_quizzes()
        for quiz in quizzes:
            self.tree.insert('', tk.END, values=(
                quiz["assignment_id"], quiz["module_code"], quiz["title"],
                quiz["question_count"], quiz["max_marks"],
                f'{quiz["duration_minutes"]} min' if quiz["duration_minutes"] else "—",
                quiz["due_date"] or "—", quiz["status"] or "—"))
        if not quizzes:
            self.tree.insert('', tk.END, values=(
                "", "", "No quizzes yet — use Create Quiz.", "", "", "", "", ""))

    def _selected(self):
        """(assignment_id, title) of the highlighted quiz, or (None, None)."""
        sel = self.tree.selection() if self.tree else None
        if not sel:
            messagebox.showwarning(_t('common.warning', default="Warning"),
                                   "Select a quiz first.")
            return None, None
        values = self.tree.item(sel[0])['values']
        if not values or not values[0]:
            return None, None
        return values[0], values[2]

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------
    def show_create_quiz(self):
        if not self._check_permission('manage_assignments'):
            return

        dlg = make_toplevel(self.root)
        dlg.title(_t('gui.academics.assignment_system.quiz_manager.windows.create_quiz', default="Create Quiz"))
        dlg.geometry("560x520")
        dlg.transient(self.root)
        dlg.grab_set()

        frm = ttk.Frame(dlg, padding=14)
        frm.pack(fill='both', expand=True)

        ttk.Label(frm, text=_t('gui.academics.assignment_system.quiz_manager.labels.title', default="Title:")).grid(row=0, column=0, sticky='w', pady=6)
        title_var = tk.StringVar()
        ttk.Entry(frm, textvariable=title_var, width=40).grid(row=0, column=1, sticky='w', pady=6)

        ttk.Label(frm, text=_t('gui.academics.assignment_system.quiz_manager.labels.module', default="Module:")).grid(row=1, column=0, sticky='w', pady=6)
        modules = self._modules()
        module_combo = ttk.Combobox(frm, width=38, state='readonly',
                                    values=[f"{code} - {name}" if name else code
                                            for code, name in modules])
        module_combo.grid(row=1, column=1, sticky='w', pady=6)
        if modules:
            module_combo.current(0)

        ttk.Label(frm, text=_t('gui.academics.assignment_system.quiz_manager.labels.description', default="Description:")).grid(row=2, column=0, sticky='nw', pady=6)
        desc = tk.Text(frm, width=40, height=4)
        desc.grid(row=2, column=1, sticky='w', pady=6)

        ttk.Label(frm, text=_t('gui.academics.assignment_system.quiz_manager.labels.due_date', default="Due date:")).grid(row=3, column=0, sticky='w', pady=6)
        from education_system.platform.delivery.gui.date_picker import DatePicker
        due_picker = DatePicker(
            frm, value=(datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d'))
        due_picker.grid(row=3, column=1, sticky='w', pady=6)

        numeric = {}
        for i, (label, key, default) in enumerate([
            ("Duration (minutes):", "duration", "30"),
            ("Total marks:", "marks", "20"),
            ("Pass mark (%):", "pass_mark", "50"),
            ("Max attempts:", "attempts", "1"),
        ], start=4):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky='w', pady=6)
            numeric[key] = ttk.Entry(frm, width=40)
            numeric[key].insert(0, default)
            numeric[key].grid(row=i, column=1, sticky='w', pady=6)

        shuffle_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text=_t('gui.academics.assignment_system.quiz_manager.buttons.shuffle', default="Shuffle questions"),
                        variable=shuffle_var).grid(row=8, column=1, sticky='w', pady=6)

        def save():
            title = title_var.get().strip()
            if not title:
                messagebox.showerror(_t('common.error', default="Error"), "A title is required.", parent=dlg)
                return
            if not modules or module_combo.current() < 0:
                messagebox.showerror(_t('common.error', default="Error"), "Select a module.", parent=dlg)
                return
            module_code = modules[module_combo.current()][0]
            try:
                duration = int(numeric["duration"].get().strip() or 0)
                marks = float(numeric["marks"].get().strip() or 0)
                pass_mark = float(numeric["pass_mark"].get().strip() or 0)
                attempts = int(numeric["attempts"].get().strip() or 1)
            except ValueError:
                messagebox.showerror(_t('common.error', default="Error"),
                                     "Duration, marks, pass mark and attempts must be numbers.",
                                     parent=dlg)
                return

            due = due_picker.get()
            # assignments.due_date carries a time; quizzes are due end of day.
            due_date = f"{due} 23:59:00" if due else None

            try:
                assignment_id, exam_id = quiz_service.create_quiz(
                    module_code=module_code, title=title,
                    created_by=self._creator(),
                    description=desc.get('1.0', tk.END).strip(),
                    due_date=due_date, duration_minutes=duration,
                    total_marks=marks, pass_mark=pass_mark,
                    max_attempts=attempts,
                    shuffle_questions=shuffle_var.get())
            except Exception as e:
                messagebox.showerror(_t('common.error', default="Error"),
                                     f"Failed to create the quiz: {e}", parent=dlg)
                return

            dlg.destroy()
            messagebox.showinfo(
                _t('common.success', default="Success"),
                f"Quiz created as assignment {assignment_id}.\n\n"
                f"It now appears in Manage Assignments. Add its questions with "
                f"Manage Questions.")
            self.show_quizzes()
            self.manage_questions(assignment_id, title)

        buttons = ttk.Frame(frm)
        buttons.grid(row=9, column=0, columnspan=2, pady=18)
        ttk.Button(buttons, text=_t('gui.academics.assignment_system.quiz_manager.buttons.create', default="Create Quiz"),
                   command=save).pack(side='left', padx=5)
        ttk.Button(buttons, text=_t('common.cancel', default="Cancel"),
                   command=dlg.destroy).pack(side='left', padx=5)

    # ------------------------------------------------------------------
    # Questions
    # ------------------------------------------------------------------
    def manage_questions(self, assignment_id=None, title=None):
        """Add and remove the questions on a quiz."""
        if assignment_id is None:
            assignment_id, title = self._selected()
            if assignment_id is None:
                return

        exam_id = quiz_service.exam_id_for_assignment(assignment_id)
        if exam_id is None:
            messagebox.showerror(
                _t('common.error', default="Error"),
                "This quiz has no exam behind it, so questions cannot be added.")
            return

        dlg = make_toplevel(self.root)
        dlg.title(f"Questions — {title}")
        dlg.geometry("820x560")
        dlg.transient(self.root)

        actions = ttk.Frame(dlg, padding=10)
        actions.pack(fill='x')
        tree = ttk.Treeview(dlg, columns=("ID", "Type", "Question", "Answer", "Marks"),
                            show='headings', height=14)
        for col, width in (("ID", 60), ("Type", 130), ("Question", 340),
                           ("Answer", 160), ("Marks", 70)):
            tree.heading(col, text=col)
            tree.column(col, width=width)
        tree.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        def refresh():
            tree.delete(*tree.get_children())
            try:
                with get_connection() as conn:
                    rows = conn.execute(
                        "SELECT id, question_type, question_text, correct_answer, marks "
                        "FROM exam_portal_questions WHERE exam_id = ? "
                        "ORDER BY order_index, id", (exam_id,)).fetchall()
            except Exception as e:
                messagebox.showerror(_t('common.error', default="Error"),
                                     f"Failed to load questions: {e}", parent=dlg)
                return
            for row in rows:
                tree.insert('', tk.END, values=tuple(row))
            if not rows:
                tree.insert('', tk.END, values=("", "", "No questions yet.", "", ""))

        def add_question():
            sub = make_toplevel(dlg)
            sub.title("Add Question")
            sub.geometry("520x460")
            sub.transient(dlg)
            sub.grab_set()
            f = ttk.Frame(sub, padding=14)
            f.pack(fill='both', expand=True)

            ttk.Label(f, text="Type:").grid(row=0, column=0, sticky='w', pady=6)
            qtype = ttk.Combobox(f, values=list(QUESTION_TYPES), width=36, state='readonly')
            qtype.current(0)
            qtype.grid(row=0, column=1, sticky='w', pady=6)

            ttk.Label(f, text="Question:").grid(row=1, column=0, sticky='nw', pady=6)
            qtext = tk.Text(f, width=38, height=5)
            qtext.grid(row=1, column=1, sticky='w', pady=6)

            ttk.Label(f, text="Options (one per line):").grid(row=2, column=0, sticky='nw', pady=6)
            options = tk.Text(f, width=38, height=4)
            options.grid(row=2, column=1, sticky='w', pady=6)

            ttk.Label(f, text="Correct answer:").grid(row=3, column=0, sticky='w', pady=6)
            answer = ttk.Entry(f, width=38)
            answer.grid(row=3, column=1, sticky='w', pady=6)

            ttk.Label(f, text="Marks:").grid(row=4, column=0, sticky='w', pady=6)
            marks = ttk.Entry(f, width=38)
            marks.insert(0, "1")
            marks.grid(row=4, column=1, sticky='w', pady=6)

            def save_question():
                text = qtext.get('1.0', tk.END).strip()
                if not text:
                    messagebox.showerror(_t('common.error', default="Error"),
                                         "The question text is required.", parent=sub)
                    return
                try:
                    mark_value = float(marks.get().strip() or 1)
                except ValueError:
                    messagebox.showerror(_t('common.error', default="Error"),
                                         "Marks must be a number.", parent=sub)
                    return
                import json
                opts = [o.strip() for o in options.get('1.0', tk.END).splitlines() if o.strip()]
                try:
                    with get_connection() as conn:
                        next_order = conn.execute(
                            "SELECT COALESCE(MAX(order_index), 0) + 1 "
                            "FROM exam_portal_questions WHERE exam_id = ?",
                            (exam_id,)).fetchone()[0]
                        conn.execute(
                            "INSERT INTO exam_portal_questions "
                            "(exam_id, question_type, question_text, options_json, "
                            " correct_answer, marks, order_index) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (exam_id, qtype.get(), text,
                             json.dumps(opts) if opts else None,
                             answer.get().strip(), mark_value, next_order))
                        conn.commit()
                except Exception as e:
                    messagebox.showerror(_t('common.error', default="Error"),
                                         f"Failed to add the question: {e}", parent=sub)
                    return
                sub.destroy()
                refresh()

            row = ttk.Frame(f)
            row.grid(row=5, column=0, columnspan=2, pady=16)
            ttk.Button(row, text="Add", command=save_question).pack(side='left', padx=5)
            ttk.Button(row, text=_t('common.cancel', default="Cancel"),
                       command=sub.destroy).pack(side='left', padx=5)

        def delete_question():
            sel = tree.selection()
            if not sel:
                return
            values = tree.item(sel[0])['values']
            if not values or not values[0]:
                return
            if not messagebox.askyesno("Delete Question",
                                       f"Delete question {values[0]}?", parent=dlg):
                return
            try:
                with get_connection() as conn:
                    conn.execute("DELETE FROM exam_portal_questions WHERE id = ?",
                                 (values[0],))
                    conn.commit()
            except Exception as e:
                messagebox.showerror(_t('common.error', default="Error"),
                                     f"Failed to delete: {e}", parent=dlg)
                return
            refresh()

        ttk.Button(actions, text="➕ Add Question", command=add_question).pack(side='left', padx=5)
        ttk.Button(actions, text="🗑 Delete Question", command=delete_question).pack(side='left', padx=5)
        ttk.Button(actions, text=_t('common.close', default="Close"),
                   command=dlg.destroy).pack(side='right', padx=5)
        refresh()

    # ------------------------------------------------------------------
    def delete_quiz(self):
        assignment_id, title = self._selected()
        if assignment_id is None:
            return
        if not messagebox.askyesno(
                _t('gui.academics.assignment_system.quiz_manager.dialogs.delete_quiz', default="Delete Quiz"),
                f"Delete the quiz '{title}'?\n\n"
                f"Its assignment row, questions and any student attempts are "
                f"deleted with it. This cannot be undone."):
            return
        try:
            quiz_service.delete_quiz(assignment_id)
        except Exception as e:
            messagebox.showerror(_t('common.error', default="Error"),
                                 f"Failed to delete the quiz: {e}")
            return
        messagebox.showinfo(_t('common.success', default="Success"), "Quiz deleted.")
        self.show_quizzes()


__all__ = ["QuizManager", "QUESTION_TYPES"]
