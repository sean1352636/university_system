"""Parent Portal GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.parent_portal.services.parent_service import ParentService


class ParentFrame(tk.Frame):
    """Parent Portal screen."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = ParentService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Parent Portal",
                 font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        # Notebook
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Overview tab (parent) ---
        self._overview_tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(self._overview_tab, text="Overview")

        child_select = tk.Frame(self._overview_tab, bg="#ecf0f1")
        child_select.pack(fill="x", pady=(0, 10))
        tk.Label(child_select, text="Select Child:", bg="#ecf0f1",
                 font=("Helvetica", 10, "bold")).pack(side="left")
        self._child_var = tk.StringVar()
        self._child_combo = ttk.Combobox(child_select, textvariable=self._child_var,
                                         state="readonly", width=30)
        self._child_combo.pack(side="left", padx=10)
        self._child_combo.bind("<<ComboboxSelected>>", self._on_child_selected)

        self._overview_text = tk.Text(self._overview_tab, height=6, wrap="word",
                                      state="disabled", font=("Helvetica", 10))
        self._overview_text.pack(fill="x")

        self._children_data: list[dict] = []

        # --- Grades tab (parent) ---
        self._grades_tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(self._grades_tab, text="Grades")

        grades_cols = ("course", "title", "grade", "score", "type")
        self._grades_tree = ttk.Treeview(self._grades_tab, columns=grades_cols,
                                         show="headings", height=10)
        for col, heading, w in [
            ("course", "Course", 90), ("title", "Title", 180),
            ("grade", "Grade", 60), ("score", "Score", 60),
            ("type", "Type", 70),
        ]:
            self._grades_tree.heading(col, text=heading)
            self._grades_tree.column(col, width=w, anchor="center")
        self._grades_tree.pack(fill="both", expand=True)

        # --- Attendance tab (parent) ---
        self._attendance_tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(self._attendance_tab, text="Attendance")

        att_cols = ("course", "title", "total", "present", "absent", "late", "rate")
        self._att_tree = ttk.Treeview(self._attendance_tab, columns=att_cols,
                                      show="headings", height=10)
        for col, heading, w in [
            ("course", "Course", 80), ("title", "Title", 160),
            ("total", "Total", 50), ("present", "Present", 55),
            ("absent", "Absent", 55), ("late", "Late", 50),
            ("rate", "Rate %", 60),
        ]:
            self._att_tree.heading(col, text=heading)
            self._att_tree.column(col, width=w, anchor="center")
        self._att_tree.pack(fill="both", expand=True)

        # --- Timetable tab (parent) ---
        self._timetable_tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(self._timetable_tab, text="Timetable")

        tt_cols = ("day", "time", "course", "room", "instructor")
        self._tt_tree = ttk.Treeview(self._timetable_tab, columns=tt_cols,
                                     show="headings", height=10)
        for col, heading, w in [
            ("day", "Day", 60), ("time", "Time", 100),
            ("course", "Course", 140), ("room", "Room", 80),
            ("instructor", "Instructor", 120),
        ]:
            self._tt_tree.heading(col, text=heading)
            self._tt_tree.column(col, width=w, anchor="center")
        self._tt_tree.pack(fill="both", expand=True)

        # --- Manage Links tab (admin) ---
        self._manage_tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(self._manage_tab, text="Manage Links")

        link_form = tk.Frame(self._manage_tab, bg="#ecf0f1")
        link_form.pack(fill="x", pady=(0, 10))

        tk.Label(link_form, text="Parent User ID:", bg="#ecf0f1").grid(
            row=0, column=0, sticky="w", padx=5, pady=3)
        self._link_parent_var = tk.StringVar()
        ttk.Entry(link_form, textvariable=self._link_parent_var,
                  width=10).grid(row=0, column=1, sticky="w", padx=5, pady=3)

        tk.Label(link_form, text="Student ID (PK):", bg="#ecf0f1").grid(
            row=0, column=2, sticky="w", padx=5, pady=3)
        self._link_student_var = tk.StringVar()
        ttk.Entry(link_form, textvariable=self._link_student_var,
                  width=10).grid(row=0, column=3, sticky="w", padx=5, pady=3)

        ttk.Button(link_form, text="Link",
                   command=self._on_link).grid(row=0, column=4, padx=5)
        ttk.Button(link_form, text="Unlink",
                   command=self._on_unlink).grid(row=0, column=5, padx=5)
        ttk.Button(link_form, text="Refresh Links",
                   command=self._load_all_links).grid(row=0, column=6, padx=5)

        link_cols = ("parent_id", "parent_name", "student_id", "student_name", "relationship")
        self._link_tree = ttk.Treeview(self._manage_tab, columns=link_cols,
                                       show="headings", height=8)
        for col, heading, w in [
            ("parent_id", "Parent ID", 70), ("parent_name", "Parent", 100),
            ("student_id", "Student ID", 80), ("student_name", "Student", 140),
            ("relationship", "Relationship", 90),
        ]:
            self._link_tree.heading(col, text=heading)
            self._link_tree.column(col, width=w, anchor="center")
        self._link_tree.pack(fill="both", expand=True)

    def refresh(self):
        self._apply_permissions()
        role = self._get_role()
        if role == "parent":
            self._load_children()
        elif role == "admin":
            self._load_all_links()

    def _get_user_id(self) -> int:
        if self._auth and self._auth.current_user:
            return self._auth.current_user["user_id"]
        return 0

    def _get_role(self) -> str:
        if self._auth and self._auth.current_user:
            return self._auth.current_user.get("role", "student")
        return "student"

    def _apply_permissions(self):
        role = self._get_role()
        is_parent = role == "parent"
        is_admin = role == "admin"
        try:
            self._nb.tab(self._overview_tab, state="normal" if is_parent else "hidden")
            self._nb.tab(self._grades_tab, state="normal" if is_parent else "hidden")
            self._nb.tab(self._attendance_tab, state="normal" if is_parent else "hidden")
            self._nb.tab(self._timetable_tab, state="normal" if is_parent else "hidden")
            self._nb.tab(self._manage_tab, state="normal" if is_admin else "hidden")
        except Exception:
            pass

    def _load_children(self):
        try:
            self._children_data = self._svc.get_linked_students(self._get_user_id())
            names = [f"{c['first_name']} {c['last_name']} ({c['student_id']})"
                     for c in self._children_data]
            self._child_combo["values"] = names
            if names:
                self._child_combo.current(0)
                self._on_child_selected()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _get_selected_child_pk(self) -> int | None:
        idx = self._child_combo.current()
        if idx < 0 or idx >= len(self._children_data):
            return None
        return self._children_data[idx]["id"]

    def _on_child_selected(self, event=None):
        child_pk = self._get_selected_child_pk()
        if child_pk is None:
            return
        child = self._children_data[self._child_combo.current()]

        # Overview
        self._overview_text.configure(state="normal")
        self._overview_text.delete("1.0", "end")
        self._overview_text.insert("end",
            f"Name: {child['first_name']} {child['last_name']}\n"
            f"Student ID: {child['student_id']}\n"
            f"Year Group: {child.get('year_group', 'N/A')}\n"
            f"Form Group: {child.get('form_group', 'N/A')}\n"
            f"Form Tutor: {child.get('form_tutor', 'N/A')}\n"
            f"Status: {child.get('status', 'N/A')}")
        self._overview_text.configure(state="disabled")

        self._load_child_grades(child_pk)
        self._load_child_attendance(child_pk)
        self._load_child_timetable(child_pk)

    def _load_child_grades(self, child_pk):
        self._grades_tree.delete(*self._grades_tree.get_children())
        try:
            grades = self._svc.get_child_grades(self._get_user_id(), child_pk)
            for g in grades:
                self._grades_tree.insert("", "end", values=(
                    g["course_code"], g["course_title"],
                    g.get("letter_grade") or "", g.get("score") or "",
                    g.get("grade_type") or "",
                ))
        except Exception:
            pass

    def _load_child_attendance(self, child_pk):
        self._att_tree.delete(*self._att_tree.get_children())
        try:
            summaries = self._svc.get_child_attendance(self._get_user_id(), child_pk)
            for s in summaries:
                self._att_tree.insert("", "end", values=(
                    s["course_code"], s["course_title"],
                    s["total"], s["present"], s["absent"], s["late"],
                    f"{s['rate']:.1f}",
                ))
        except Exception:
            pass

    def _load_child_timetable(self, child_pk):
        self._tt_tree.delete(*self._tt_tree.get_children())
        try:
            slots = self._svc.get_child_timetable(self._get_user_id(), child_pk)
            for sl in slots:
                time_str = f"{sl['start_time']}-{sl['end_time']}"
                self._tt_tree.insert("", "end", values=(
                    sl["day_of_week"], time_str, sl["course_title"],
                    sl.get("room") or "", sl.get("instructor_name") or "",
                ))
        except Exception:
            pass

    def _load_all_links(self):
        self._link_tree.delete(*self._link_tree.get_children())
        try:
            from education_system.college_system.infrastructure.database.db import connect
            conn = connect(self._db_path)
            try:
                rows = conn.execute(
                    """SELECT pl.*, u.username, s.student_id as sid,
                              s.first_name, s.last_name
                       FROM parent_links pl
                       JOIN users u ON pl.parent_user_id = u.id
                       JOIN students s ON pl.student_id = s.id
                       ORDER BY u.username"""
                ).fetchall()
            finally:
                conn.close()
            for r in rows:
                self._link_tree.insert("", "end", values=(
                    r["parent_user_id"], r["username"],
                    r["sid"], f"{r['first_name']} {r['last_name']}",
                    r.get("relationship") or "parent",
                ))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_link(self):
        try:
            parent_id = int(self._link_parent_var.get().strip())
            student_id = int(self._link_student_var.get().strip())
        except ValueError:
            messagebox.showwarning("Input", "Enter valid numeric IDs.")
            return
        try:
            self._svc.admin_link_parent(parent_id, student_id)
            messagebox.showinfo("Success", "Parent linked to student.")
            self._load_all_links()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_unlink(self):
        try:
            parent_id = int(self._link_parent_var.get().strip())
            student_id = int(self._link_student_var.get().strip())
        except ValueError:
            messagebox.showwarning("Input", "Enter valid numeric IDs.")
            return
        try:
            self._svc.unlink_parent(parent_id, student_id)
            messagebox.showinfo("Success", "Link removed.")
            self._load_all_links()
        except Exception as e:
            messagebox.showerror("Error", str(e))
