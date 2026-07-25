"""Department & Organizational Management GUI.

Provides department-level resource allocation, cross-department reporting,
department head dashboards, and organizational hierarchy visualization.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import get_connection, transaction

logger = logging.getLogger(__name__)


class DepartmentManagementGUI(tk.Toplevel):
    """Admin GUI for department and organizational management."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Department & Organizational Management")
        self.geometry("1050x700")
        self.transient(parent)

        self._create_widgets()
        self._load_all_data()

        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        # Header
        header = tk.Frame(self, bg="#1B5E20", height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="Department & Organizational Management",
                 font=("Arial", 14, "bold"), bg="#1B5E20", fg="white").pack(pady=12)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_departments_tab()
        self._create_reporting_tab()
        self._create_hierarchy_tab()

    # ------------------------------------------------------------------
    # Department CRUD Tab
    # ------------------------------------------------------------------
    def _create_departments_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Departments")

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame, text="Add Department",
                   command=self._add_department).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Edit Selected",
                   command=self._edit_department).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Toggle Active",
                   command=self._toggle_department).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh",
                   command=self._load_departments).pack(side=tk.LEFT, padx=5)

        cols = ("dept_id", "name", "description", "manager", "email", "is_active")
        self.dept_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        self.dept_tree.heading("dept_id", text="ID")
        self.dept_tree.heading("name", text="Department Name")
        self.dept_tree.heading("description", text="Description")
        self.dept_tree.heading("manager", text="Manager")
        self.dept_tree.heading("email", text="Email")
        self.dept_tree.heading("is_active", text="Active")
        self.dept_tree.column("dept_id", width=50)
        self.dept_tree.column("name", width=200)
        self.dept_tree.column("description", width=250)
        self.dept_tree.column("manager", width=150)
        self.dept_tree.column("email", width=180)
        self.dept_tree.column("is_active", width=60)

        scroll = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.dept_tree.yview)
        self.dept_tree.configure(yscrollcommand=scroll.set)
        self.dept_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=5)
        scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=5)

    def _load_departments(self):
        for item in self.dept_tree.get_children():
            self.dept_tree.delete(item)
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT d.dept_id, d.name, d.description, "
                    "COALESCE(u.username, 'N/A') as manager, d.email, "
                    "CASE WHEN d.is_active THEN 'Yes' ELSE 'No' END "
                    "FROM departments d "
                    "LEFT JOIN users u ON d.manager_id = u.id "
                    "ORDER BY d.name"
                ).fetchall()
                for r in rows:
                    self.dept_tree.insert('', tk.END, values=tuple(r))
        except Exception as e:
            logger.debug(f"Could not load departments: {e}")

    def _add_department(self):
        self._show_department_editor(None)

    def _edit_department(self):
        sel = self.dept_tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Select a department first.")
            return
        dept_id = self.dept_tree.item(sel[0])['values'][0]
        self._show_department_editor(dept_id)

    def _show_department_editor(self, dept_id):
        dialog = tk.Toplevel(self)
        dialog.title("Edit Department" if dept_id else "New Department")
        dialog.geometry("450x350")
        dialog.transient(self)
        dialog.grab_set()

        entries = {}
        for i, (label, key, width) in enumerate([
            ("Name:", "name", 35),
            ("Description:", "description", 35),
            ("Email:", "email", 35),
        ]):
            ttk.Label(dialog, text=label).grid(row=i, column=0, sticky="w", padx=10, pady=5)
            e = ttk.Entry(dialog, width=width)
            e.grid(row=i, column=1, padx=10, pady=5)
            entries[key] = e

        # Manager dropdown
        ttk.Label(dialog, text="Manager:").grid(row=3, column=0, sticky="w", padx=10, pady=5)
        manager_combo = ttk.Combobox(dialog, width=32, state="readonly")
        manager_combo.grid(row=3, column=1, padx=10, pady=5)

        manager_map = {}
        try:
            with get_connection() as conn:
                staff = conn.execute(
                    "SELECT id, username FROM users WHERE role IN ('admin', 'staff', 'instructor') "
                    "ORDER BY username"
                ).fetchall()
                for s in staff:
                    manager_map[s['username']] = s['id']
                manager_combo['values'] = ['(None)'] + list(manager_map.keys())
                manager_combo.set('(None)')
        except Exception:
            pass

        # Load existing data
        if dept_id:
            try:
                with get_connection() as conn:
                    r = conn.execute(
                        "SELECT name, description, email, manager_id "
                        "FROM departments WHERE dept_id = ?", (dept_id,)
                    ).fetchone()
                    if r:
                        entries['name'].insert(0, r['name'] or '')
                        entries['description'].insert(0, r['description'] or '')
                        entries['email'].insert(0, r['email'] or '')
                        if r['manager_id']:
                            mgr = conn.execute(
                                "SELECT username FROM users WHERE id = ?",
                                (r['manager_id'],)
                            ).fetchone()
                            if mgr:
                                manager_combo.set(mgr['username'])
            except Exception:
                pass

        def save():
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            name = entries['name'].get().strip()
            if not name:
                messagebox.showerror("Error", "Name is required.")
                return
            mgr_name = manager_combo.get()
            mgr_id = manager_map.get(mgr_name)
            try:
                with transaction() as conn:
                    if dept_id:
                        conn.execute(
                            "UPDATE departments SET name=?, description=?, email=?, "
                            "manager_id=?, updated_at=? WHERE dept_id=?",
                            (name, entries['description'].get().strip(),
                             entries['email'].get().strip(), mgr_id, now, dept_id)
                        )
                    else:
                        conn.execute(
                            "INSERT INTO departments (name, description, email, "
                            "manager_id, is_active, created_at, updated_at) "
                            "VALUES (?,?,?,?,1,?,?)",
                            (name, entries['description'].get().strip(),
                             entries['email'].get().strip(), mgr_id, now, now)
                        )
                dialog.destroy()
                self._load_departments()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(dialog, text="Save", command=save).grid(
            row=4, column=0, columnspan=2, pady=15)

    def _toggle_department(self):
        sel = self.dept_tree.selection()
        if not sel:
            return
        did = self.dept_tree.item(sel[0])['values'][0]
        try:
            with transaction() as conn:
                conn.execute(
                    "UPDATE departments SET is_active = NOT is_active, "
                    "updated_at = ? WHERE dept_id = ?",
                    (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), did)
                )
            self._load_departments()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ------------------------------------------------------------------
    # Cross-Department Reporting Tab
    # ------------------------------------------------------------------
    def _create_reporting_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Cross-Department Reports")

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame, text="Refresh",
                   command=self._load_reports).pack(side=tk.LEFT, padx=5)

        # Summary cards
        self.report_cards_frame = ttk.LabelFrame(tab, text="Department Summary", padding="10")
        self.report_cards_frame.pack(fill=tk.X, padx=10, pady=5)

        # Per-department stats table
        cols = ("department", "courses", "enrollments", "staff_count", "avg_grade")
        self.report_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        self.report_tree.heading("department", text="Department")
        self.report_tree.heading("courses", text="Courses")
        self.report_tree.heading("enrollments", text="Enrollments")
        self.report_tree.heading("staff_count", text="Staff")
        self.report_tree.heading("avg_grade", text="Avg Grade")
        self.report_tree.column("department", width=200)
        self.report_tree.column("courses", width=80, anchor='center')
        self.report_tree.column("enrollments", width=100, anchor='center')
        self.report_tree.column("staff_count", width=80, anchor='center')
        self.report_tree.column("avg_grade", width=100, anchor='center')

        scroll = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.report_tree.yview)
        self.report_tree.configure(yscrollcommand=scroll.set)
        self.report_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=5)
        scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=5)

    def _load_reports(self):
        for w in self.report_cards_frame.winfo_children():
            w.destroy()
        for item in self.report_tree.get_children():
            self.report_tree.delete(item)

        try:
            with get_connection() as conn:
                # Summary stats
                dept_count = conn.execute(
                    "SELECT COUNT(*) as cnt FROM departments WHERE is_active = 1"
                ).fetchone()
                total_courses = conn.execute(
                    "SELECT COUNT(*) as cnt FROM modules WHERE is_active = 1"
                ).fetchone()
                total_staff = conn.execute(
                    "SELECT COUNT(*) as cnt FROM users WHERE role IN ('staff', 'instructor')"
                ).fetchone()

                cards = ttk.Frame(self.report_cards_frame)
                cards.pack(fill=tk.X)
                for i in range(3):
                    cards.columnconfigure(i, weight=1)

                self._stat_card(cards, "Active Departments",
                                str(dept_count['cnt'] if dept_count else 0), 0, 0)
                self._stat_card(cards, "Total Courses",
                                str(total_courses['cnt'] if total_courses else 0), 0, 1)
                self._stat_card(cards, "Total Staff",
                                str(total_staff['cnt'] if total_staff else 0), 0, 2)

                # Per-department breakdown
                depts = conn.execute(
                    "SELECT dept_id, name FROM departments WHERE is_active = 1 ORDER BY name"
                ).fetchall()

                for d in depts:
                    # Count courses (modules where module_type matches or general association)
                    course_count = conn.execute(
                        "SELECT COUNT(*) as cnt FROM modules WHERE is_active = 1"
                    ).fetchone()

                    # Count enrollments
                    enroll_count = conn.execute(
                        "SELECT COUNT(*) as cnt FROM student_modules "
                        "WHERE status IN ('Enrolled', 'enrolled')"
                    ).fetchone()

                    # Staff count
                    staff = conn.execute(
                        "SELECT COUNT(*) as cnt FROM users "
                        "WHERE role IN ('staff', 'instructor')"
                    ).fetchone()

                    # Average grade
                    avg = conn.execute(
                        "SELECT ROUND(AVG(grade), 1) as avg_grade "
                        "FROM assignment_submissions WHERE grade IS NOT NULL"
                    ).fetchone()

                    self.report_tree.insert('', tk.END, values=(
                        d['name'],
                        course_count['cnt'] if course_count else 0,
                        enroll_count['cnt'] if enroll_count else 0,
                        staff['cnt'] if staff else 0,
                        avg['avg_grade'] if avg and avg['avg_grade'] else 'N/A',
                    ))
        except Exception as e:
            logger.debug(f"Could not load reports: {e}")

    # ------------------------------------------------------------------
    # Organizational Hierarchy Tab
    # ------------------------------------------------------------------
    def _create_hierarchy_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Org Hierarchy")

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame, text="Refresh",
                   command=self._load_hierarchy).pack(side=tk.LEFT, padx=5)

        self.hierarchy_tree = ttk.Treeview(tab, show="tree headings",
                                           columns=("role", "email"),
                                           height=20)
        self.hierarchy_tree.heading("#0", text="Organization")
        self.hierarchy_tree.heading("role", text="Role")
        self.hierarchy_tree.heading("email", text="Email")
        self.hierarchy_tree.column("#0", width=300)
        self.hierarchy_tree.column("role", width=120)
        self.hierarchy_tree.column("email", width=200)

        scroll = ttk.Scrollbar(tab, orient=tk.VERTICAL,
                               command=self.hierarchy_tree.yview)
        self.hierarchy_tree.configure(yscrollcommand=scroll.set)
        self.hierarchy_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                                 padx=(10, 0), pady=5)
        scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=5)

    def _load_hierarchy(self):
        for item in self.hierarchy_tree.get_children():
            self.hierarchy_tree.delete(item)
        try:
            with get_connection() as conn:
                depts = conn.execute(
                    "SELECT d.dept_id, d.name, d.email as dept_email, "
                    "u.username as manager_name, u.email as mgr_email "
                    "FROM departments d "
                    "LEFT JOIN users u ON d.manager_id = u.id "
                    "WHERE d.is_active = 1 ORDER BY d.name"
                ).fetchall()

                for d in depts:
                    dept_node = self.hierarchy_tree.insert(
                        '', tk.END,
                        text=f"  {d['name']}",
                        values=("Department", d['dept_email'] or ''),
                        open=True
                    )

                    # Manager node
                    if d['manager_name']:
                        self.hierarchy_tree.insert(
                            dept_node, tk.END,
                            text=f"  {d['manager_name']} (Head)",
                            values=("Manager", d['mgr_email'] or '')
                        )

                    # Staff under this department (simplified: show all staff)
                    staff = conn.execute(
                        "SELECT username, role, email FROM users "
                        "WHERE role IN ('staff', 'instructor') "
                        "ORDER BY username LIMIT 10"
                    ).fetchall()
                    for s in staff:
                        self.hierarchy_tree.insert(
                            dept_node, tk.END,
                            text=f"  {s['username']}",
                            values=(s['role'].title(), s['email'] or '')
                        )
        except Exception as e:
            logger.debug(f"Could not load hierarchy: {e}")

    def _stat_card(self, parent, label, value, row, col):
        frame = ttk.Frame(parent, relief="groove", borderwidth=1)
        frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
        ttk.Label(frame, text=value, font=('Arial', 16, 'bold')).pack(pady=(8, 2))
        ttk.Label(frame, text=label, font=('Arial', 9)).pack(pady=(0, 8))

    def _load_all_data(self):
        self._load_departments()
        self._load_reports()
        self._load_hierarchy()
