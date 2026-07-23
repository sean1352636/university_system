"""Course Catalog & Self-Registration GUI (Feature 36).

Allows students to search the course catalog, view enrollment counts, and
register for (or drop) courses.  If a course is full the student is offered
a spot on the waitlist.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.post_18.university_system.core.sql_safety import escape_like
from education_system.post_18.university_system.infrastructure.database.db import get_connection, sqlite3, transaction
from education_system.post_18.university_system.modules.shared.utils.simple_activity_logger import log_activity

logger = logging.getLogger(__name__)


class CourseCatalogGUI:
    """Toplevel window for browsing and registering for courses."""

    TYPE_CHOICES = ['All', 'core', 'elective', 'lab']

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.student_id = ''
        if auth and auth.current_user:
            self.student_id = auth.current_user.get('username', '')

        self.window = tk.Toplevel(parent)
        self.window.title("Course Catalog & Registration")
        self.window.geometry("1100x700")
        self.window.transient(parent)

        self._setup_ui()
        self._search_courses()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        """Build the catalog layout."""
        ttk.Label(
            self.window,
            text="Course Catalog & Registration",
            font=('Arial', 16, 'bold'),
        ).pack(pady=(10, 5))

        # ---- Search / filter bar ----
        search_frame = ttk.Frame(self.window)
        search_frame.pack(fill=tk.X, padx=15, pady=5)

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=(0, 10))
        search_entry.bind('<Return>', lambda e: self._search_courses())

        ttk.Label(search_frame, text="Type:").pack(side=tk.LEFT, padx=(0, 5))
        self.type_var = tk.StringVar(value='All')
        type_combo = ttk.Combobox(
            search_frame, textvariable=self.type_var,
            values=self.TYPE_CHOICES, state='readonly', width=12,
        )
        type_combo.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(search_frame, text="Search", command=self._search_courses).pack(side=tk.LEFT)

        # ---- Results treeview ----
        tree_frame = ttk.Frame(self.window)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        cols = ('code', 'name', 'credits', 'type', 'instructor', 'enrolled_capacity', 'status')
        self.tree = ttk.Treeview(tree_frame, columns=cols, show='headings', height=20)
        self.tree.heading('code', text='Code')
        self.tree.heading('name', text='Course Name')
        self.tree.heading('credits', text='Credits')
        self.tree.heading('type', text='Type')
        self.tree.heading('instructor', text='Instructor')
        self.tree.heading('enrolled_capacity', text='Enrolled/Cap')
        self.tree.heading('status', text='Status')

        self.tree.column('code', width=110)
        self.tree.column('name', width=280)
        self.tree.column('credits', width=70, anchor='center')
        self.tree.column('type', width=90, anchor='center')
        self.tree.column('instructor', width=130)
        self.tree.column('enrolled_capacity', width=110, anchor='center')
        self.tree.column('status', width=100, anchor='center')

        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- Action buttons ----
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(fill=tk.X, padx=15, pady=(5, 10))

        ttk.Button(btn_frame, text="Register", command=self._register).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Drop", command=self._drop).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._search_courses).pack(side=tk.RIGHT, padx=5)

        self.status_var = tk.StringVar(value="")
        ttk.Label(self.window, textvariable=self.status_var).pack(anchor='w', padx=15, pady=(0, 5))

    # ------------------------------------------------------------------
    # Searching
    # ------------------------------------------------------------------

    def _search_courses(self):
        """Query the modules table with optional search term and type filter."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        search_term = self.search_var.get().strip()
        type_filter = self.type_var.get()

        try:
            with get_connection() as conn:
                query = (
                    "SELECT m.module_code, m.module_name, m.credits, m.module_type, "
                    "(SELECT COUNT(*) FROM student_modules sm "
                    "  WHERE sm.module_code = m.module_code AND sm.status = 'Enrolled') "
                    "  AS enrolled "
                    "FROM modules m WHERE 1=1"
                )
                params = []

                if search_term:
                    query += " AND (m.module_code LIKE ? OR m.module_name LIKE ?)"
                    like = f"%{escape_like(search_term)}%"
                    params.extend([like, like])

                if type_filter and type_filter != 'All':
                    query += " AND m.module_type = ?"
                    params.append(type_filter)

                query += " ORDER BY m.module_code"

                rows = conn.execute(query, params).fetchall()

                # Build a set of modules the student is enrolled in
                enrolled_set = set()
                if self.student_id:
                    enrolled_rows = conn.execute(
                        "SELECT module_code FROM student_modules "
                        "WHERE student_id = ? AND status = 'Enrolled'",
                        (self.student_id,),
                    ).fetchall()
                    enrolled_set = {r['module_code'] for r in (enrolled_rows or [])}

                count = 0
                for row in rows or []:
                    code = row['module_code']
                    name = row['module_name'] or ''
                    credits = row['credits'] or ''
                    mtype = row['module_type'] or ''
                    enrolled = row['enrolled'] or 0

                    if code in enrolled_set:
                        status = 'Enrolled'
                    else:
                        status = 'Available'

                    self.tree.insert('', tk.END, values=(
                        code, name, credits, mtype, '', str(enrolled), status,
                    ))
                    count += 1

                self.status_var.set(f"{count} course(s) found.")

        except Exception as e:
            logger.error(f"Error searching courses: {e}")
            self.status_var.set(f"Error: {e}")
            messagebox.showerror("Error", f"Failed to search courses: {e}", parent=self.window)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def _get_selected_code(self):
        """Return the module_code of the selected treeview row, or None."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select a course first.", parent=self.window)
            return None
        values = self.tree.item(sel[0], 'values')
        return values[0] if values else None

    def _register(self):
        """Register the student for the selected course, or offer waitlist if full."""
        if not self.student_id:
            messagebox.showwarning("Warning", "No student logged in.", parent=self.window)
            return

        module_code = self._get_selected_code()
        if not module_code:
            return

        try:
            with get_connection() as conn:
                # Check if already enrolled
                existing = conn.execute(
                    "SELECT status FROM student_modules "
                    "WHERE student_id = ? AND module_code = ? AND status = 'Enrolled'",
                    (self.student_id, module_code),
                ).fetchone()
                if existing:
                    messagebox.showinfo(
                        "Already Enrolled",
                        f"You are already enrolled in {module_code}.",
                        parent=self.window,
                    )
                    return

                # Fetch capacity and current enrollment. `modules` doesn't
                # always have a capacity column — treat missing as uncapped.
                capacity = 0
                try:
                    mod = conn.execute(
                        "SELECT capacity FROM modules WHERE module_code = ?",
                        (module_code,),
                    ).fetchone()
                    capacity = (mod['capacity'] or 0) if mod else 0
                except sqlite3.OperationalError:
                    capacity = 0

                enrolled_count = conn.execute(
                    "SELECT COUNT(*) as cnt FROM student_modules "
                    "WHERE module_code = ? AND status = 'Enrolled'",
                    (module_code,),
                ).fetchone()
                enrolled = (enrolled_count['cnt'] or 0) if enrolled_count else 0

            if capacity and enrolled >= capacity:
                # Course is full -- offer waitlist
                if messagebox.askyesno(
                    "Course Full",
                    f"{module_code} is full ({enrolled}/{capacity}). "
                    "Would you like to join the waitlist?",
                    parent=self.window,
                ):
                    self._add_to_waitlist(module_code)
                return

            # Perform enrollment inside a transaction
            with transaction() as conn:
                # Check for a dropped record to update, otherwise insert
                dropped = conn.execute(
                    "SELECT rowid FROM student_modules "
                    "WHERE student_id = ? AND module_code = ? AND status = 'Dropped'",
                    (self.student_id, module_code),
                ).fetchone()

                if dropped:
                    conn.execute(
                        "UPDATE student_modules SET status = 'Enrolled', "
                        "enrollment_date = datetime('now') "
                        "WHERE student_id = ? AND module_code = ? AND status = 'Dropped'",
                        (self.student_id, module_code),
                    )
                else:
                    conn.execute(
                        "INSERT INTO student_modules "
                        "(student_id, module_code, status, enrollment_date) "
                        "VALUES (?, ?, 'Enrolled', datetime('now'))",
                        (self.student_id, module_code),
                    )

            try:
                log_activity(
                    self.student_id, self.student_id, 'student',
                    'create', 'enrollment',
                    details=f"Enrolled in {module_code}",
                )
            except Exception:
                pass

            messagebox.showinfo(
                "Enrolled",
                f"Successfully enrolled in {module_code}.",
                parent=self.window,
            )
            self._search_courses()

        except Exception as e:
            logger.error(f"Error registering for {module_code}: {e}")
            messagebox.showerror(
                "Error", f"Registration failed: {e}", parent=self.window
            )

    def _add_to_waitlist(self, module_code):
        """Add the student to the course waitlist."""
        try:
            with transaction() as conn:
                # Determine next position
                pos_row = conn.execute(
                    "SELECT COALESCE(MAX(position), 0) + 1 AS next_pos "
                    "FROM course_waitlist WHERE module_code = ?",
                    (module_code,),
                ).fetchone()
                next_pos = pos_row['next_pos'] if pos_row else 1

                conn.execute(
                    "INSERT INTO course_waitlist (student_id, module_code, position) "
                    "VALUES (?, ?, ?)",
                    (self.student_id, module_code, next_pos),
                )

            try:
                log_activity(
                    self.student_id, self.student_id, 'student',
                    'create', 'waitlist',
                    details=f"Added to waitlist for {module_code} at position {next_pos}",
                )
            except Exception:
                pass

            messagebox.showinfo(
                "Waitlisted",
                f"You have been added to the waitlist for {module_code} "
                f"at position {next_pos}.",
                parent=self.window,
            )
            self._search_courses()

        except Exception as e:
            logger.error(f"Error adding to waitlist for {module_code}: {e}")
            messagebox.showerror(
                "Error", f"Failed to join waitlist: {e}", parent=self.window
            )

    # ------------------------------------------------------------------
    # Drop
    # ------------------------------------------------------------------

    def _drop(self):
        """Drop the student from the selected course."""
        if not self.student_id:
            messagebox.showwarning("Warning", "No student logged in.", parent=self.window)
            return

        module_code = self._get_selected_code()
        if not module_code:
            return

        if not messagebox.askyesno(
            "Confirm Drop",
            f"Are you sure you want to drop {module_code}?",
            parent=self.window,
        ):
            return

        try:
            with transaction() as conn:
                conn.execute(
                    "UPDATE student_modules SET status = 'Dropped' "
                    "WHERE student_id = ? AND module_code = ? AND status = 'Enrolled'",
                    (self.student_id, module_code),
                )

            try:
                log_activity(
                    self.student_id, self.student_id, 'student',
                    'update', 'enrollment',
                    details=f"Dropped {module_code}",
                )
            except Exception:
                pass

            messagebox.showinfo(
                "Dropped",
                f"You have been dropped from {module_code}.",
                parent=self.window,
            )
            self._search_courses()

        except Exception as e:
            logger.error(f"Error dropping {module_code}: {e}")
            messagebox.showerror(
                "Error", f"Failed to drop course: {e}", parent=self.window
            )
