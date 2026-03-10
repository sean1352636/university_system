"""Departments & Groups GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.departments.services.department_service import (
    DepartmentService, GroupService,
)


class DepartmentsFrame(tk.Frame):
    """Departments & Groups management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._dept_svc = DepartmentService(db_path)
        self._grp_svc = GroupService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Departments & Groups",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_dept_tab()
        self._build_tutor_tab()
        self._build_teaching_tab()

    def _build_dept_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Departments")

        form = tk.LabelFrame(tab, text="New Department", bg="#ecf0f1", padx=10, pady=8)
        self._dept_form = form
        form.pack(fill="x", pady=(0, 8))

        row = tk.Frame(form, bg="#ecf0f1")
        row.pack(fill="x", pady=2)
        tk.Label(row, text="Code:", bg="#ecf0f1").pack(side="left")
        self._dept_code_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._dept_code_var, width=10).pack(side="left", padx=5)
        tk.Label(row, text="Name:", bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._dept_name_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._dept_name_var, width=20).pack(side="left", padx=5)
        tk.Label(row, text="Faculty:", bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._dept_faculty_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._dept_faculty_var, width=15).pack(side="left", padx=5)
        ttk.Button(row, text="Create", command=self._create_dept).pack(side="left", padx=10)

        cols = ("id", "code", "name", "faculty", "status")
        self._dept_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("code", "Code", 80), ("name", "Name", 180),
                         ("faculty", "Faculty", 140), ("status", "Status", 80)]:
            self._dept_tree.heading(c, text=h)
            self._dept_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._dept_tree.yview)
        self._dept_tree.configure(yscrollcommand=vsb.set)
        self._dept_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_tutor_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Tutor Groups")

        form = tk.LabelFrame(tab, text="New Tutor Group", bg="#ecf0f1", padx=10, pady=8)
        self._tutor_form = form
        form.pack(fill="x", pady=(0, 8))

        row = tk.Frame(form, bg="#ecf0f1")
        row.pack(fill="x", pady=2)
        tk.Label(row, text="Name:", bg="#ecf0f1").pack(side="left")
        self._tg_name_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._tg_name_var, width=15).pack(side="left", padx=5)
        tk.Label(row, text="Year:", bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._tg_year_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._tg_year_var, width=6).pack(side="left", padx=5)
        ttk.Button(row, text="Create", command=self._create_tutor_group).pack(side="left", padx=10)

        cols = ("id", "name", "year_group", "max_size")
        self._tutor_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("name", "Name", 140),
                         ("year_group", "Year", 60), ("max_size", "Max", 50)]:
            self._tutor_tree.heading(c, text=h)
            self._tutor_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tutor_tree.yview)
        self._tutor_tree.configure(yscrollcommand=vsb.set)
        self._tutor_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_teaching_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Teaching Groups")

        form = tk.LabelFrame(tab, text="New Teaching Group", bg="#ecf0f1", padx=10, pady=8)
        self._teach_form = form
        form.pack(fill="x", pady=(0, 8))

        row = tk.Frame(form, bg="#ecf0f1")
        row.pack(fill="x", pady=2)
        tk.Label(row, text="Name:", bg="#ecf0f1").pack(side="left")
        self._teg_name_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._teg_name_var, width=15).pack(side="left", padx=5)
        tk.Label(row, text="Course ID:", bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._teg_course_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._teg_course_var, width=8).pack(side="left", padx=5)
        ttk.Button(row, text="Create", command=self._create_teaching_group).pack(side="left", padx=10)

        cols = ("id", "name", "course_id", "academic_year", "max_size")
        self._teach_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("name", "Name", 140), ("course_id", "Course", 60),
                         ("academic_year", "Year", 80), ("max_size", "Max", 50)]:
            self._teach_tree.heading(c, text=h)
            self._teach_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._teach_tree.yview)
        self._teach_tree.configure(yscrollcommand=vsb.set)
        self._teach_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def refresh(self):
        role = ""
        if self._auth and self._auth.current_user:
            role = self._auth.current_user.get("role", "student")
        if role not in ("admin", "staff"):
            self._dept_form.pack_forget()
            self._tutor_form.pack_forget()
            self._teach_form.pack_forget()
        self._load_depts()
        self._load_tutor_groups()
        self._load_teaching_groups()

    def _load_depts(self):
        self._dept_tree.delete(*self._dept_tree.get_children())
        try:
            for d in self._dept_svc.list_departments():
                self._dept_tree.insert("", "end", values=(
                    d["id"], d["code"], d["name"],
                    d.get("faculty") or "-", d["status"]))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_tutor_groups(self):
        self._tutor_tree.delete(*self._tutor_tree.get_children())
        try:
            for g in self._grp_svc.list_tutor_groups():
                self._tutor_tree.insert("", "end", values=(
                    g["id"], g["name"], g.get("year_group") or "-", g["max_size"]))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_teaching_groups(self):
        self._teach_tree.delete(*self._teach_tree.get_children())
        try:
            for g in self._grp_svc.list_teaching_groups():
                self._teach_tree.insert("", "end", values=(
                    g["id"], g["name"], g["course_id"],
                    g.get("academic_year") or "-", g["max_size"]))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _create_dept(self):
        try:
            dept = self._dept_svc.create_department(
                self._dept_code_var.get().strip(),
                self._dept_name_var.get().strip(),
                faculty=self._dept_faculty_var.get().strip() or None,
            )
            messagebox.showinfo("Success", f"Department created (ID: {dept['id']}).")
            self._dept_code_var.set("")
            self._dept_name_var.set("")
            self._dept_faculty_var.set("")
            self._load_depts()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _create_tutor_group(self):
        try:
            group = self._grp_svc.create_tutor_group(
                self._tg_name_var.get().strip(),
                year_group=self._tg_year_var.get().strip() or None,
            )
            messagebox.showinfo("Success", f"Tutor group created (ID: {group['id']}).")
            self._tg_name_var.set("")
            self._tg_year_var.set("")
            self._load_tutor_groups()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _create_teaching_group(self):
        try:
            group = self._grp_svc.create_teaching_group(
                self._teg_name_var.get().strip(),
                int(self._teg_course_var.get().strip()),
            )
            messagebox.showinfo("Success", f"Teaching group created (ID: {group['id']}).")
            self._teg_name_var.set("")
            self._teg_course_var.set("")
            self._load_teaching_groups()
        except Exception as e:
            messagebox.showerror("Error", str(e))
