"""Shared LMS GUI frame.

Provides a tabbed interface for both staff and students.  Each subsystem
(college, secondary, primary) registers this frame in its sidebar and
passes its own ``db_path`` so that the LMS tables in that subsystem's
database are used.

The university system has its own integrated LMS inside the Course
Management GUI and does not use this frame.
"""

import json
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
import logging

from education_system.shared.lms.course_content_service import CourseContentService
from education_system.shared.lms.learning_progress_service import LearningProgressService
from education_system.shared.lms.quiz_service import QuizService
from education_system.shared.lms.resource_library_service import ResourceLibraryService

logger = logging.getLogger(__name__)

HEADER_BG = "#1a5276"
HEADER_FG = "#ffffff"
MAIN_BG = "#ecf0f1"
ACCENT = "#2980b9"
SUCCESS = "#27ae60"
WARNING = "#e67e22"
DANGER = "#e74c3c"


class LMSFrame(tk.Frame):
    """Learning Management System GUI — a single tk.Frame that subsystem
    main_gui files can embed in their content area."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._role = self._detect_role()

        if db_path:
            self._content_svc = CourseContentService(db_path)
            self._progress_svc = LearningProgressService(db_path)
            self._quiz_svc = QuizService(db_path)
            self._resource_svc = ResourceLibraryService(db_path)
        else:
            self._content_svc = self._progress_svc = self._quiz_svc = self._resource_svc = None

        self._build_ui()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _detect_role(self):
        if isinstance(self._auth, dict):
            return self._auth.get("role", "student")
        if hasattr(self._auth, "current_user") and self._auth.current_user:
            return self._auth.current_user.get("role", "student")
        if hasattr(self._auth, "role"):
            return self._auth.role
        return "student"

    def _is_staff(self):
        return self._role in ("admin", "staff", "teacher", "instructor", "superadmin",
                              "teaching_assistant", "head_teacher", "deputy_head")

    def _get_student_id(self):
        if isinstance(self._auth, dict):
            return str(self._auth.get("student_id", self._auth.get("username", "")))
        if hasattr(self._auth, "current_user") and self._auth.current_user:
            u = self._auth.current_user
            return str(u.get("student_id", u.get("username", "")))
        return ""

    def _get_username(self):
        if isinstance(self._auth, dict):
            return self._auth.get("username", "")
        if hasattr(self._auth, "current_user") and self._auth.current_user:
            return self._auth.current_user.get("username", "")
        return ""

    # ------------------------------------------------------------------
    # Course identifier resolution
    # ------------------------------------------------------------------

    def _resolve_course_id(self, raw):
        """Accept a numeric course id, a course code (e.g. 'CS'), or a
        course name (e.g. 'Computer Science'), and return the numeric
        ``courses.id``. Returns ``None`` when nothing matches.
        """
        if raw is None:
            return None
        val = raw.strip() if isinstance(raw, str) else raw
        if not val:
            return None
        try:
            return int(val)
        except (TypeError, ValueError):
            pass
        if not self._db_path:
            return None
        try:
            conn = sqlite3.connect(self._db_path)
            try:
                row = conn.execute(
                    """
                    SELECT id FROM courses
                    WHERE COALESCE(course_code, code) = ?
                       OR COALESCE(course_name, name) = ?
                    LIMIT 1
                    """,
                    (val, val),
                ).fetchone()
            finally:
                conn.close()
        except Exception as exc:
            logger.debug("LMS course resolution failed for %r: %s", val, exc)
            return None
        return int(row[0]) if row else None

    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x"); header.pack_propagate(False)
        tk.Label(header, text="Learning Management System",
                 font=("Helvetica", 14, "bold"), bg=HEADER_BG, fg=HEADER_FG).pack(side="left", padx=15)

        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=5, pady=5)

        if self._is_staff():
            self._build_staff_tabs()
        else:
            self._build_student_tabs()

    def _build_staff_tabs(self):
        for name, builder in [("Course Content", self._build_content_tab),
                               ("Create Lesson", self._build_create_lesson_tab),
                               ("Quizzes", self._build_quiz_management_tab),
                               ("Resources", self._build_resources_tab),
                               ("Student Progress", self._build_staff_progress_tab)]:
            tab = tk.Frame(self._notebook, bg=MAIN_BG)
            self._notebook.add(tab, text=name); builder(tab)

    def _build_student_tabs(self):
        for name, builder in [("My Courses", self._build_my_courses_tab),
                               ("Current Lesson", self._build_current_lesson_tab),
                               ("Quizzes", self._build_student_quiz_tab),
                               ("Resources", self._build_resources_tab),
                               ("My Progress", self._build_student_progress_tab)]:
            tab = tk.Frame(self._notebook, bg=MAIN_BG)
            self._notebook.add(tab, text=name); builder(tab)

    # ==================================================================
    # Staff: Course Content
    # ==================================================================

    def _build_content_tab(self, parent):
        top = tk.Frame(parent, bg=MAIN_BG); top.pack(fill="x", padx=10, pady=8)
        tk.Label(top, text="Course ID / Code:", bg=MAIN_BG).pack(side="left")
        self._content_course_var = tk.StringVar()
        tk.Entry(top, textvariable=self._content_course_var, width=10).pack(side="left", padx=5)
        tk.Button(top, text="Load Modules", bg=ACCENT, fg="white", command=self._load_modules).pack(side="left", padx=5)
        tk.Button(top, text="New Module", bg=SUCCESS, fg="white", command=self._new_module_dialog).pack(side="left", padx=5)

        cols = ("ID", "Title", "Type", "Published", "Order")
        self._content_tree = ttk.Treeview(parent, columns=cols, show="headings", height=15)
        for c in cols:
            self._content_tree.heading(c, text=c); self._content_tree.column(c, width=120)
        self._content_tree.pack(fill="both", expand=True, padx=10, pady=5)

        btn_row = tk.Frame(parent, bg=MAIN_BG); btn_row.pack(fill="x", padx=10, pady=5)
        tk.Button(btn_row, text="Publish Module", bg=SUCCESS, fg="white", command=self._publish_selected).pack(side="left", padx=3)
        tk.Button(btn_row, text="Unpublish Module", bg=WARNING, fg="white", command=self._unpublish_selected).pack(side="left", padx=3)

    def _load_modules(self):
        if not self._content_svc: return
        cid = self._resolve_course_id(self._content_course_var.get())
        if cid is None:
            messagebox.showwarning("LMS", "Enter a valid Course ID or code (e.g. 1 or CS)."); return
        self._content_tree.delete(*self._content_tree.get_children())
        modules = self._content_svc.list_modules(cid)
        for m in modules:
            self._content_tree.insert("", "end", values=(m["id"], m["title"], "Module", "Yes" if m["published"] else "No", m["order_index"]))
            for ls in self._content_svc.list_lessons(m["id"]):
                self._content_tree.insert("", "end", values=(ls["id"], f"   {ls['title']}", ls["content_type"], "", ls["order_index"]))
        if not modules:
            self._content_tree.insert("", "end", values=(
                "—",
                f"No modules yet for course {cid}. Use 'New Module' to start.",
                "—", "—", "—",
            ))

    def _new_module_dialog(self):
        if not self._content_svc: return
        cid = self._resolve_course_id(self._content_course_var.get())
        if cid is None:
            messagebox.showwarning("LMS", "Enter a valid Course ID or code first (e.g. 1 or CS)."); return
        dlg = tk.Toplevel(self); dlg.title("New Module"); dlg.geometry("380x200"); dlg.grab_set()
        frm = tk.Frame(dlg, padx=20, pady=15); frm.pack(fill="both", expand=True)
        tk.Label(frm, text="Title:").grid(row=0, column=0, sticky="w", pady=4)
        title_var = tk.StringVar(); tk.Entry(frm, textvariable=title_var, width=35).grid(row=0, column=1, pady=4)
        tk.Label(frm, text="Description:").grid(row=1, column=0, sticky="w", pady=4)
        desc_var = tk.StringVar(); tk.Entry(frm, textvariable=desc_var, width=35).grid(row=1, column=1, pady=4)
        def _save():
            t = title_var.get().strip()
            if not t: messagebox.showwarning("LMS", "Title is required"); return
            try: self._content_svc.create_module(cid, t, desc_var.get()); dlg.destroy(); self._load_modules()
            except Exception as e: messagebox.showerror("LMS", str(e))
        tk.Button(frm, text="Save", bg=ACCENT, fg="white", command=_save).grid(row=2, column=1, sticky="e", pady=10)

    def _publish_selected(self):
        sel = self._content_tree.selection()
        if sel and self._content_svc:
            v = self._content_tree.item(sel[0], "values")
            if v[2] == "Module": self._content_svc.publish_module(int(v[0])); self._load_modules()

    def _unpublish_selected(self):
        sel = self._content_tree.selection()
        if sel and self._content_svc:
            v = self._content_tree.item(sel[0], "values")
            if v[2] == "Module": self._content_svc.unpublish_module(int(v[0])); self._load_modules()

    # ==================================================================
    # Staff: Create Lesson
    # ==================================================================

    def _build_create_lesson_tab(self, parent):
        frm = tk.Frame(parent, bg=MAIN_BG, padx=20, pady=15); frm.pack(fill="both", expand=True)
        tk.Label(frm, text="Module ID:", bg=MAIN_BG).grid(row=0, column=0, sticky="w", pady=4)
        self._lesson_mod_var = tk.StringVar(); tk.Entry(frm, textvariable=self._lesson_mod_var, width=10).grid(row=0, column=1, sticky="w", pady=4)
        tk.Label(frm, text="Title:", bg=MAIN_BG).grid(row=1, column=0, sticky="w", pady=4)
        self._lesson_title_var = tk.StringVar(); tk.Entry(frm, textvariable=self._lesson_title_var, width=40).grid(row=1, column=1, sticky="w", pady=4)
        tk.Label(frm, text="Content Type:", bg=MAIN_BG).grid(row=2, column=0, sticky="w", pady=4)
        self._lesson_type_var = tk.StringVar(value="text")
        ttk.Combobox(frm, textvariable=self._lesson_type_var, width=18, values=["text", "video_link", "document", "quiz", "activity"], state="readonly").grid(row=2, column=1, sticky="w", pady=4)
        tk.Label(frm, text="Duration (mins):", bg=MAIN_BG).grid(row=3, column=0, sticky="w", pady=4)
        self._lesson_dur_var = tk.StringVar(); tk.Entry(frm, textvariable=self._lesson_dur_var, width=10).grid(row=3, column=1, sticky="w", pady=4)
        tk.Label(frm, text="Content:", bg=MAIN_BG).grid(row=4, column=0, sticky="nw", pady=4)
        self._lesson_content_txt = tk.Text(frm, width=50, height=8); self._lesson_content_txt.grid(row=4, column=1, sticky="w", pady=4)
        tk.Button(frm, text="Create Lesson", bg=ACCENT, fg="white", font=("Helvetica", 10, "bold"), command=self._create_lesson).grid(row=5, column=1, sticky="e", pady=10)

    def _create_lesson(self):
        if not self._content_svc: return
        try: mod_id = int(self._lesson_mod_var.get())
        except (ValueError, TypeError): messagebox.showwarning("LMS", "Enter a valid Module ID"); return
        title = self._lesson_title_var.get().strip()
        if not title: messagebox.showwarning("LMS", "Title is required"); return
        dur_str = self._lesson_dur_var.get().strip(); dur = int(dur_str) if dur_str.isdigit() else None
        try:
            self._content_svc.create_lesson(mod_id, title, self._lesson_type_var.get(), self._lesson_content_txt.get("1.0", "end-1c"), duration_mins=dur)
            messagebox.showinfo("LMS", f"Lesson '{title}' created successfully")
            self._lesson_title_var.set(""); self._lesson_content_txt.delete("1.0", "end"); self._lesson_dur_var.set("")
        except Exception as e: messagebox.showerror("LMS", str(e))

    # ==================================================================
    # Staff: Quizzes
    # ==================================================================

    def _build_quiz_management_tab(self, parent):
        top = tk.Frame(parent, bg=MAIN_BG, padx=10, pady=8); top.pack(fill="x")
        tk.Label(top, text="Lesson ID:", bg=MAIN_BG).pack(side="left")
        self._quiz_lesson_var = tk.StringVar(); tk.Entry(top, textvariable=self._quiz_lesson_var, width=10).pack(side="left", padx=5)
        tk.Button(top, text="Create Quiz", bg=SUCCESS, fg="white", command=self._create_quiz_dialog).pack(side="left", padx=5)
        cols = ("ID", "Title", "Pass Mark", "Time Limit", "Questions")
        self._quiz_tree = ttk.Treeview(parent, columns=cols, show="headings", height=8)
        for c in cols: self._quiz_tree.heading(c, text=c); self._quiz_tree.column(c, width=100)
        self._quiz_tree.pack(fill="both", expand=True, padx=10, pady=5)
        btn_row = tk.Frame(parent, bg=MAIN_BG); btn_row.pack(fill="x", padx=10, pady=5)
        tk.Button(btn_row, text="Load Quizzes", bg=ACCENT, fg="white", command=self._load_quizzes).pack(side="left", padx=3)
        tk.Button(btn_row, text="Add Question", bg=SUCCESS, fg="white", command=self._add_question_dialog).pack(side="left", padx=3)
        tk.Button(btn_row, text="View Stats", bg=ACCENT, fg="white", command=self._view_quiz_stats).pack(side="left", padx=3)

    def _load_quizzes(self):
        if not self._quiz_svc: return
        try: lid = int(self._quiz_lesson_var.get())
        except (ValueError, TypeError): messagebox.showwarning("LMS", "Enter a valid Lesson ID"); return
        self._quiz_tree.delete(*self._quiz_tree.get_children())
        conn = self._quiz_svc._conn()
        try:
            for q in conn.execute("SELECT * FROM lms_quizzes WHERE lesson_id = ?", (lid,)).fetchall():
                cnt = conn.execute("SELECT COUNT(*) AS cnt FROM lms_questions WHERE quiz_id = ?", (q["id"],)).fetchone()["cnt"]
                tl = f"{q['time_limit_mins']} min" if q["time_limit_mins"] else "None"
                self._quiz_tree.insert("", "end", values=(q["id"], q["title"], f"{q['pass_mark']}%", tl, cnt))
        finally: conn.close()

    def _create_quiz_dialog(self):
        if not self._quiz_svc: return
        try: lid = int(self._quiz_lesson_var.get())
        except (ValueError, TypeError): messagebox.showwarning("LMS", "Enter a valid Lesson ID first"); return
        dlg = tk.Toplevel(self); dlg.title("Create Quiz"); dlg.geometry("350x220"); dlg.grab_set()
        frm = tk.Frame(dlg, padx=20, pady=15); frm.pack(fill="both", expand=True)
        tk.Label(frm, text="Title:").grid(row=0, column=0, sticky="w", pady=4)
        title_var = tk.StringVar(); tk.Entry(frm, textvariable=title_var, width=30).grid(row=0, column=1, pady=4)
        tk.Label(frm, text="Pass Mark (%):").grid(row=1, column=0, sticky="w", pady=4)
        pm_var = tk.StringVar(value="50"); tk.Entry(frm, textvariable=pm_var, width=10).grid(row=1, column=1, sticky="w", pady=4)
        tk.Label(frm, text="Time Limit (mins):").grid(row=2, column=0, sticky="w", pady=4)
        tl_var = tk.StringVar(); tk.Entry(frm, textvariable=tl_var, width=10).grid(row=2, column=1, sticky="w", pady=4)
        def _save():
            t = title_var.get().strip()
            if not t: messagebox.showwarning("LMS", "Title is required"); return
            try: pm = float(pm_var.get())
            except ValueError: pm = 50.0
            tls = tl_var.get().strip(); tl = int(tls) if tls.isdigit() else None
            try: self._quiz_svc.create_quiz(lid, t, pm, tl); dlg.destroy(); self._load_quizzes()
            except Exception as e: messagebox.showerror("LMS", str(e))
        tk.Button(frm, text="Save", bg=ACCENT, fg="white", command=_save).grid(row=3, column=1, sticky="e", pady=10)

    def _add_question_dialog(self):
        sel = self._quiz_tree.selection()
        if not sel or not self._quiz_svc: messagebox.showwarning("LMS", "Select a quiz first"); return
        quiz_id = int(self._quiz_tree.item(sel[0], "values")[0])
        dlg = tk.Toplevel(self); dlg.title("Add Question"); dlg.geometry("450x350"); dlg.grab_set()
        frm = tk.Frame(dlg, padx=15, pady=10); frm.pack(fill="both", expand=True)
        tk.Label(frm, text="Question:").grid(row=0, column=0, sticky="nw", pady=4)
        q_txt = tk.Text(frm, width=40, height=3); q_txt.grid(row=0, column=1, pady=4)
        tk.Label(frm, text="Type:").grid(row=1, column=0, sticky="w", pady=4)
        type_var = tk.StringVar(value="multiple_choice")
        ttk.Combobox(frm, textvariable=type_var, width=18, values=["multiple_choice", "true_false", "short_answer"], state="readonly").grid(row=1, column=1, sticky="w", pady=4)
        tk.Label(frm, text="Options (JSON list):").grid(row=2, column=0, sticky="w", pady=4)
        opts_var = tk.StringVar(value='["A", "B", "C", "D"]'); tk.Entry(frm, textvariable=opts_var, width=40).grid(row=2, column=1, pady=4)
        tk.Label(frm, text="Correct Answer:").grid(row=3, column=0, sticky="w", pady=4)
        ans_var = tk.StringVar(); tk.Entry(frm, textvariable=ans_var, width=30).grid(row=3, column=1, sticky="w", pady=4)
        tk.Label(frm, text="Marks:").grid(row=4, column=0, sticky="w", pady=4)
        marks_var = tk.StringVar(value="1"); tk.Entry(frm, textvariable=marks_var, width=8).grid(row=4, column=1, sticky="w", pady=4)
        def _save():
            qt = q_txt.get("1.0", "end-1c").strip()
            if not qt: messagebox.showwarning("LMS", "Question text required"); return
            try: m = float(marks_var.get())
            except ValueError: m = 1.0
            opts = opts_var.get().strip() if type_var.get() == "multiple_choice" else None
            try: self._quiz_svc.add_question(quiz_id, qt, type_var.get(), correct_answer=ans_var.get(), marks=m, options=opts); dlg.destroy(); self._load_quizzes()
            except Exception as e: messagebox.showerror("LMS", str(e))
        tk.Button(frm, text="Save", bg=ACCENT, fg="white", command=_save).grid(row=5, column=1, sticky="e", pady=10)

    def _view_quiz_stats(self):
        sel = self._quiz_tree.selection()
        if not sel or not self._quiz_svc: messagebox.showwarning("LMS", "Select a quiz first"); return
        stats = self._quiz_svc.get_quiz_stats(int(self._quiz_tree.item(sel[0], "values")[0]))
        messagebox.showinfo("Quiz Stats", f"Attempts: {stats['attempts']}\nUnique Students: {stats['unique_students']}\nAverage Score: {stats['avg_score']}\nPass Rate: {stats['pass_rate']}%")

    # ==================================================================
    # Shared: Resources
    # ==================================================================

    def _build_resources_tab(self, parent):
        top = tk.Frame(parent, bg=MAIN_BG, padx=10, pady=8); top.pack(fill="x")
        tk.Label(top, text="Search:", bg=MAIN_BG).pack(side="left")
        self._res_search_var = tk.StringVar(); tk.Entry(top, textvariable=self._res_search_var, width=25).pack(side="left", padx=5)
        tk.Button(top, text="Search", bg=ACCENT, fg="white", command=self._search_resources).pack(side="left", padx=3)
        tk.Button(top, text="Show All", bg=ACCENT, fg="white", command=self._list_all_resources).pack(side="left", padx=3)
        if self._is_staff(): tk.Button(top, text="Upload", bg=SUCCESS, fg="white", command=self._upload_resource_dialog).pack(side="left", padx=3)
        cols = ("ID", "Title", "Type", "Downloads", "Uploaded By")
        self._res_tree = ttk.Treeview(parent, columns=cols, show="headings", height=12)
        for c in cols: self._res_tree.heading(c, text=c); self._res_tree.column(c, width=120)
        self._res_tree.pack(fill="both", expand=True, padx=10, pady=5)
        btn_row = tk.Frame(parent, bg=MAIN_BG); btn_row.pack(fill="x", padx=10, pady=5)
        tk.Button(btn_row, text="Download", bg=ACCENT, fg="white", command=self._download_resource).pack(side="left", padx=3)
        if self._is_staff(): tk.Button(btn_row, text="Delete", bg=DANGER, fg="white", command=self._delete_resource).pack(side="left", padx=3)

    def _populate_resource_tree(self, resources):
        self._res_tree.delete(*self._res_tree.get_children())
        for r in resources: self._res_tree.insert("", "end", values=(r["id"], r["title"], r["resource_type"], r["download_count"], r.get("uploaded_by", "")))

    def _list_all_resources(self):
        if self._resource_svc: self._populate_resource_tree(self._resource_svc.list_resources())

    def _search_resources(self):
        if not self._resource_svc: return
        q = self._res_search_var.get().strip()
        if not q: self._list_all_resources(); return
        self._populate_resource_tree(self._resource_svc.search_resources(q))

    def _download_resource(self):
        sel = self._res_tree.selection()
        if not sel or not self._resource_svc: return
        res = self._resource_svc.download_resource(int(self._res_tree.item(sel[0], "values")[0]))
        if res: messagebox.showinfo("LMS", f"Resource: {res['title']}\nPath: {res['file_path']}\nDownloads: {res['download_count']}")

    def _upload_resource_dialog(self):
        if not self._resource_svc: return
        dlg = tk.Toplevel(self); dlg.title("Upload Resource"); dlg.geometry("420x300"); dlg.grab_set()
        frm = tk.Frame(dlg, padx=20, pady=15); frm.pack(fill="both", expand=True)
        tk.Label(frm, text="Title:").grid(row=0, column=0, sticky="w", pady=4)
        title_var = tk.StringVar(); tk.Entry(frm, textvariable=title_var, width=35).grid(row=0, column=1, pady=4)
        tk.Label(frm, text="Description:").grid(row=1, column=0, sticky="w", pady=4)
        desc_var = tk.StringVar(); tk.Entry(frm, textvariable=desc_var, width=35).grid(row=1, column=1, pady=4)
        tk.Label(frm, text="File Path / URL:").grid(row=2, column=0, sticky="w", pady=4)
        path_var = tk.StringVar(); tk.Entry(frm, textvariable=path_var, width=35).grid(row=2, column=1, pady=4)
        tk.Label(frm, text="Type:").grid(row=3, column=0, sticky="w", pady=4)
        type_var = tk.StringVar(value="document")
        ttk.Combobox(frm, textvariable=type_var, width=18, values=["document", "presentation", "spreadsheet", "image", "video_link", "audio", "other"], state="readonly").grid(row=3, column=1, sticky="w", pady=4)
        tk.Label(frm, text="Course ID (optional):").grid(row=4, column=0, sticky="w", pady=4)
        cid_var = tk.StringVar(); tk.Entry(frm, textvariable=cid_var, width=10).grid(row=4, column=1, sticky="w", pady=4)
        def _save():
            t = title_var.get().strip()
            if not t: messagebox.showwarning("LMS", "Title is required"); return
            cs = cid_var.get().strip(); cid = int(cs) if cs.isdigit() else None
            try: self._resource_svc.upload_resource(t, desc_var.get(), path_var.get(), type_var.get(), self._get_username(), cid); dlg.destroy(); self._list_all_resources()
            except Exception as e: messagebox.showerror("LMS", str(e))
        tk.Button(frm, text="Upload", bg=ACCENT, fg="white", command=_save).grid(row=5, column=1, sticky="e", pady=10)

    def _delete_resource(self):
        sel = self._res_tree.selection()
        if not sel or not self._resource_svc: return
        if messagebox.askyesno("LMS", "Delete this resource?"):
            self._resource_svc.delete_resource(int(self._res_tree.item(sel[0], "values")[0])); self._list_all_resources()

    # ==================================================================
    # Staff: Student Progress
    # ==================================================================

    def _build_staff_progress_tab(self, parent):
        top = tk.Frame(parent, bg=MAIN_BG, padx=10, pady=8); top.pack(fill="x")
        tk.Label(top, text="Course ID / Code:", bg=MAIN_BG).pack(side="left")
        self._prog_course_var = tk.StringVar(); tk.Entry(top, textvariable=self._prog_course_var, width=10).pack(side="left", padx=5)
        tk.Button(top, text="Load Stats", bg=ACCENT, fg="white", command=self._load_course_stats).pack(side="left", padx=5)
        self._stats_frame = tk.Frame(parent, bg=MAIN_BG, padx=20, pady=15); self._stats_frame.pack(fill="both", expand=True)

    def _load_course_stats(self):
        if not self._progress_svc: return
        cid = self._resolve_course_id(self._prog_course_var.get())
        if cid is None:
            messagebox.showwarning("LMS", "Enter a valid Course ID or code (e.g. 1 or CS)."); return
        for w in self._stats_frame.winfo_children(): w.destroy()
        stats = self._progress_svc.get_course_completion_stats(cid)
        if not stats.get("total_lessons"):
            tk.Label(self._stats_frame,
                     text=f"No published LMS content for course {cid} yet — "
                          "nothing to report on.",
                     font=("Helvetica", 11), bg=MAIN_BG, fg="#7f8c8d",
                     wraplength=640, justify="left").pack(anchor="w")
            return
        for i, (lbl, val) in enumerate([("Total Lessons", str(stats["total_lessons"])), ("Students", str(stats["total_students"])), ("Avg Completion", f"{stats['avg_percentage']}%"), ("Fully Completed", str(stats["fully_completed"]))]):
            card = tk.Frame(self._stats_frame, bg="white", bd=1, relief="solid", padx=20, pady=15); card.grid(row=0, column=i, padx=8, pady=8)
            tk.Label(card, text=val, font=("Helvetica", 22, "bold"), bg="white", fg=ACCENT).pack()
            tk.Label(card, text=lbl, font=("Helvetica", 9), bg="white", fg="#7f8c8d").pack()
        if stats["total_lessons"] > 0 and stats["total_students"] > 0:
            bf = tk.Frame(self._stats_frame, bg=MAIN_BG); bf.grid(row=1, column=0, columnspan=4, pady=15, sticky="ew")
            tk.Label(bf, text="Avg. Completion", bg=MAIN_BG).pack(anchor="w")
            ttk.Progressbar(bf, length=400, mode="determinate", maximum=100, value=stats["avg_percentage"]).pack(fill="x", pady=5)

    # ==================================================================
    # Student: My Courses
    # ==================================================================

    def _build_my_courses_tab(self, parent):
        top = tk.Frame(parent, bg=MAIN_BG, padx=10, pady=8); top.pack(fill="x")
        tk.Label(top, text="Course ID / Code:", bg=MAIN_BG).pack(side="left")
        self._stu_course_var = tk.StringVar(); tk.Entry(top, textvariable=self._stu_course_var, width=10).pack(side="left", padx=5)
        tk.Button(top, text="Load", bg=ACCENT, fg="white", command=self._load_student_modules).pack(side="left", padx=5)
        cols = ("Module", "Lessons", "Completed", "Progress")
        self._stu_mod_tree = ttk.Treeview(parent, columns=cols, show="headings", height=12)
        for c in cols: self._stu_mod_tree.heading(c, text=c); self._stu_mod_tree.column(c, width=120)
        self._stu_mod_tree.pack(fill="both", expand=True, padx=10, pady=5)
        self._stu_empty_var = tk.StringVar(value="")
        tk.Label(parent, textvariable=self._stu_empty_var, bg=MAIN_BG,
                 fg="#7f8c8d", font=("Helvetica", 10, "italic"),
                 wraplength=820, justify="left").pack(fill="x", padx=12, pady=(0, 10))

    def _load_student_modules(self):
        if not self._content_svc or not self._progress_svc: return
        cid = self._resolve_course_id(self._stu_course_var.get())
        if cid is None:
            messagebox.showwarning("LMS", "Enter a valid Course ID or code (e.g. 1 or CS)."); return
        sid = self._get_student_id(); self._stu_mod_tree.delete(*self._stu_mod_tree.get_children())
        all_modules = self._content_svc.list_modules(cid)
        published = [m for m in all_modules if m.get("published")]
        for m in published:
            lessons = self._content_svc.list_lessons(m["id"]); prog = self._progress_svc.get_module_progress(sid, m["id"])
            self._stu_mod_tree.insert("", "end", values=(m["title"], len(lessons), prog["completed"], f"{prog['percentage']}%"))
        if not all_modules:
            self._stu_empty_var.set(
                f"No LMS modules exist for course {cid} yet. Your "
                "instructor creates them in the LMS 'Course Content' tab.")
        elif not published:
            self._stu_empty_var.set(
                f"{len(all_modules)} module(s) exist for course {cid} but "
                "none have been published yet. Ask your instructor to "
                "publish them.")
        else:
            self._stu_empty_var.set("")

    # ==================================================================
    # Student: Current Lesson
    # ==================================================================

    def _build_current_lesson_tab(self, parent):
        top = tk.Frame(parent, bg=MAIN_BG, padx=10, pady=8); top.pack(fill="x")
        tk.Label(top, text="Course ID / Code:", bg=MAIN_BG).pack(side="left")
        self._cur_course_var = tk.StringVar(); tk.Entry(top, textvariable=self._cur_course_var, width=10).pack(side="left", padx=5)
        tk.Button(top, text="Load Next Lesson", bg=ACCENT, fg="white", command=self._load_next_lesson).pack(side="left", padx=5)
        self._lesson_display = tk.Frame(parent, bg="white", padx=20, pady=15); self._lesson_display.pack(fill="both", expand=True, padx=10, pady=5)
        self._lesson_id_loaded = None

    def _load_next_lesson(self):
        if not self._progress_svc: return
        for w in self._lesson_display.winfo_children(): w.destroy()
        cid = self._resolve_course_id(self._cur_course_var.get())
        if cid is None:
            messagebox.showwarning("LMS", "Enter a valid Course ID or code (e.g. 1 or CS)."); return
        lesson = self._progress_svc.get_next_lesson(self._get_student_id(), cid)
        if not lesson:
            # Distinguish "all done" from "no content at all".
            any_lessons = False
            if self._content_svc:
                for m in self._content_svc.list_modules(cid):
                    if m.get("published") and self._content_svc.list_lessons(m["id"]):
                        any_lessons = True
                        break
            if any_lessons:
                tk.Label(self._lesson_display, text="All lessons completed!",
                         font=("Helvetica", 14, "bold"), bg="white",
                         fg=SUCCESS).pack(expand=True)
            else:
                tk.Label(self._lesson_display,
                         text=f"No lessons have been published for course "
                              f"{cid} yet.",
                         font=("Helvetica", 12, "bold"), bg="white",
                         fg="#7f8c8d").pack(pady=(40, 6))
                tk.Label(self._lesson_display,
                         text="Your instructor creates modules and lessons "
                              "from the staff 'Course Content' and "
                              "'Create Lesson' tabs.",
                         bg="white", fg="#7f8c8d",
                         wraplength=520, justify="center"
                         ).pack()
            self._lesson_id_loaded = None; return
        self._lesson_id_loaded = lesson["id"]
        tk.Label(self._lesson_display, text=lesson["title"], font=("Helvetica", 14, "bold"), bg="white").pack(anchor="w")
        tk.Label(self._lesson_display, text=f"Type: {lesson['content_type']}   Duration: {lesson['duration_mins'] or '?'} mins", font=("Helvetica", 9), bg="white", fg="#7f8c8d").pack(anchor="w", pady=(0, 10))
        txt = tk.Text(self._lesson_display, wrap="word", height=12, width=70); txt.insert("1.0", lesson.get("content") or "(No content)"); txt.configure(state="disabled"); txt.pack(fill="both", expand=True, pady=5)
        tk.Button(self._lesson_display, text="Mark Complete", bg=SUCCESS, fg="white", font=("Helvetica", 10, "bold"), command=self._mark_complete).pack(pady=10)

    def _mark_complete(self):
        if not self._progress_svc or not self._lesson_id_loaded: return
        self._progress_svc.mark_lesson_complete(self._get_student_id(), self._lesson_id_loaded)
        messagebox.showinfo("LMS", "Lesson marked as complete!"); self._load_next_lesson()

    # ==================================================================
    # Student: Take Quiz
    # ==================================================================

    def _build_student_quiz_tab(self, parent):
        top = tk.Frame(parent, bg=MAIN_BG, padx=10, pady=8); top.pack(fill="x")
        tk.Label(top, text="Quiz ID:", bg=MAIN_BG).pack(side="left")
        self._stu_quiz_var = tk.StringVar(); tk.Entry(top, textvariable=self._stu_quiz_var, width=10).pack(side="left", padx=5)
        tk.Button(top, text="Start Quiz", bg=ACCENT, fg="white", command=self._start_quiz).pack(side="left", padx=5)
        self._quiz_area = tk.Frame(parent, bg="white", padx=15, pady=10); self._quiz_area.pack(fill="both", expand=True, padx=10, pady=5)
        self._quiz_answer_vars = {}

    def _start_quiz(self):
        if not self._quiz_svc: return
        for w in self._quiz_area.winfo_children(): w.destroy()
        self._quiz_answer_vars.clear()
        try: qid = int(self._stu_quiz_var.get())
        except (ValueError, TypeError): messagebox.showwarning("LMS", "Enter a valid Quiz ID"); return
        questions = self._quiz_svc.list_questions(qid)
        if not questions: tk.Label(self._quiz_area, text="No questions found.", bg="white").pack(); return
        canvas = tk.Canvas(self._quiz_area, bg="white", highlightthickness=0)
        sb = ttk.Scrollbar(self._quiz_area, orient="vertical", command=canvas.yview)
        sf = tk.Frame(canvas, bg="white"); sf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=sf, anchor="nw"); canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        for i, q in enumerate(questions, 1):
            qf = tk.Frame(sf, bg="white", pady=8); qf.pack(fill="x", padx=10)
            tk.Label(qf, text=f"Q{i}. {q['question_text']}", font=("Helvetica", 10, "bold"), bg="white", wraplength=500, justify="left").pack(anchor="w")
            tk.Label(qf, text=f"({q['marks']} marks)", font=("Helvetica", 8), bg="white", fg="#7f8c8d").pack(anchor="w")
            av = tk.StringVar(); self._quiz_answer_vars[q["id"]] = av
            if q["question_type"] == "multiple_choice" and (q.get("options") or q.get("options_json")):
                try: options = q.get("options") or json.loads(q.get("options_json", "[]"))
                except (json.JSONDecodeError, TypeError): options = []
                for opt in options: tk.Radiobutton(qf, text=opt, variable=av, value=opt, bg="white").pack(anchor="w", padx=15)
            elif q["question_type"] == "true_false":
                tk.Radiobutton(qf, text="True", variable=av, value="true", bg="white").pack(anchor="w", padx=15)
                tk.Radiobutton(qf, text="False", variable=av, value="false", bg="white").pack(anchor="w", padx=15)
            else: tk.Entry(qf, textvariable=av, width=40).pack(anchor="w", padx=15)
            ttk.Separator(qf, orient="horizontal").pack(fill="x", pady=5)
        tk.Button(sf, text="Submit Quiz", bg=SUCCESS, fg="white", font=("Helvetica", 11, "bold"), command=lambda qid=qid: self._submit_quiz(qid)).pack(pady=15)

    def _submit_quiz(self, quiz_id):
        if not self._quiz_svc: return
        answers = {str(qid): var.get() for qid, var in self._quiz_answer_vars.items()}
        try:
            result = self._quiz_svc.submit_quiz(quiz_id, self._get_student_id(), answers)
            status = "PASSED" if result["passed"] else "FAILED"
            msg = f"Score: {result['score']}\nResult: {status}"
            (messagebox.showinfo if result["passed"] else messagebox.showwarning)("Quiz Result", msg)
        except Exception as e: messagebox.showerror("LMS", str(e))

    # ==================================================================
    # Student: My Progress
    # ==================================================================

    def _build_student_progress_tab(self, parent):
        top = tk.Frame(parent, bg=MAIN_BG, padx=10, pady=8); top.pack(fill="x")
        tk.Label(top, text="Course ID / Code:", bg=MAIN_BG).pack(side="left")
        self._my_prog_course_var = tk.StringVar(); tk.Entry(top, textvariable=self._my_prog_course_var, width=10).pack(side="left", padx=5)
        tk.Button(top, text="View Progress", bg=ACCENT, fg="white", command=self._view_my_progress).pack(side="left", padx=5)
        self._my_prog_frame = tk.Frame(parent, bg=MAIN_BG, padx=20, pady=15); self._my_prog_frame.pack(fill="both", expand=True)

    def _view_my_progress(self):
        if not self._progress_svc: return
        for w in self._my_prog_frame.winfo_children(): w.destroy()
        cid = self._resolve_course_id(self._my_prog_course_var.get())
        if cid is None:
            messagebox.showwarning("LMS", "Enter a valid Course ID or code (e.g. 1 or CS)."); return
        sid = self._get_student_id(); prog = self._progress_svc.get_student_progress(sid, cid)
        if not prog.get("total"):
            tk.Label(self._my_prog_frame,
                     text=f"No lessons have been published for course {cid} "
                          "yet — there's nothing to report progress on.",
                     font=("Helvetica", 11), bg=MAIN_BG, fg="#7f8c8d",
                     wraplength=640, justify="left").pack(anchor="w")
            return
        tk.Label(self._my_prog_frame, text=f"Completed {prog['completed']} of {prog['total']} lessons", font=("Helvetica", 13, "bold"), bg=MAIN_BG).pack(anchor="w")
        ttk.Progressbar(self._my_prog_frame, length=400, mode="determinate", maximum=100, value=prog["percentage"]).pack(fill="x", pady=10)
        tk.Label(self._my_prog_frame, text=f"{prog['percentage']}% complete", font=("Helvetica", 11), bg=MAIN_BG, fg=ACCENT).pack(anchor="w")
        completed = self._progress_svc.list_completed_lessons(sid, cid)
        if completed:
            tk.Label(self._my_prog_frame, text="Completed Lessons:", font=("Helvetica", 10, "bold"), bg=MAIN_BG).pack(anchor="w", pady=(15, 5))
            for c in completed: tk.Label(self._my_prog_frame, text=f"  - {c['lesson_title']} ({c['module_title']})  {c.get('completed_at', '')}", bg=MAIN_BG, font=("Helvetica", 9)).pack(anchor="w")

    # ------------------------------------------------------------------
    def refresh(self):
        pass
