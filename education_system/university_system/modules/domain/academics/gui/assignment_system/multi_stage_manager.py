"""Multi-stage assignment and external tool submission management"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import re
from datetime import datetime, timedelta
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH


class MultiStageManager:
    """Manages multi-stage assignments and external tool submissions"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style
        self._init_db()

    def _init_db(self):
        """Create database tables if they do not exist"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS assignment_stages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        assignment_id INTEGER NOT NULL,
                        stage_number INTEGER NOT NULL,
                        stage_name TEXT NOT NULL,
                        description TEXT,
                        weight_percent REAL NOT NULL DEFAULT 0,
                        deadline TEXT NOT NULL,
                        feedback_required INTEGER NOT NULL DEFAULT 1,
                        created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                ''')
                # Must match the canonical definition in db_manager.py.
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS stage_submissions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        stage_id INTEGER NOT NULL,
                        student_id TEXT NOT NULL,
                        content TEXT,
                        file_path TEXT,
                        status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'submitted', 'reviewed', 'approved')),
                        feedback TEXT,
                        submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        reviewed_at TEXT,
                        FOREIGN KEY (stage_id) REFERENCES assignment_stages (id) ON DELETE CASCADE,
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS external_submissions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        assignment_id INTEGER NOT NULL,
                        student_id TEXT NOT NULL,
                        url TEXT NOT NULL,
                        link_type TEXT NOT NULL DEFAULT 'other',
                        is_validated INTEGER NOT NULL DEFAULT 0,
                        submitted_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                ''')
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"Error initializing multi-stage DB tables: {e}")

    def _check_permission(self, permission):
        """Check if user has permission"""
        try:
            return self.auth.check_permission(permission)
        except (AttributeError, Exception):
            return self.auth.user_role in ['Admin', 'Faculty']

    def _get_student_id(self):
        """Safely get the current student ID"""
        try:
            if hasattr(self.assignment_system, '_get_student_id'):
                return self.assignment_system._get_student_id()
            if self.auth and self.auth.current_user:
                return self.auth.current_user.get('id') or self.auth.current_user.get('student_id')
            return None
        except Exception:
            return None

    # ──────────────────────────────────────────────────────────────────
    # Multi-stage assignment dashboard
    # ──────────────────────────────────────────────────────────────────

    def show_multi_stage_assignments(self):
        """Dashboard showing all multi-stage assignments"""
        self.gui.layout.clear_content_area()
        content = self.gui.layout.content_area

        # Header
        header_frame = ttk.Frame(content)
        header_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Label(header_frame, text="Multi-Stage Assignments", font=("Segoe UI", 16, "bold")).pack(
            side=tk.LEFT
        )

        if self._check_permission('manage_assignments'):
            ttk.Button(
                header_frame, text="+ Create Multi-Stage", command=self.create_multi_stage_assignment
            ).pack(side=tk.RIGHT, padx=5)

        # Treeview
        tree_frame = ttk.Frame(content)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("id", "title", "stages", "total_weight", "next_deadline", "status")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=18)

        tree.heading("id", text="ID")
        tree.heading("title", text="Assignment Title")
        tree.heading("stages", text="Stages")
        tree.heading("total_weight", text="Total Weight %")
        tree.heading("next_deadline", text="Next Deadline")
        tree.heading("status", text="Status")

        tree.column("id", width=50, anchor=tk.CENTER)
        tree.column("title", width=250)
        tree.column("stages", width=80, anchor=tk.CENTER)
        tree.column("total_weight", width=110, anchor=tk.CENTER)
        tree.column("next_deadline", width=150, anchor=tk.CENTER)
        tree.column("status", width=100, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load data
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT
                        s.assignment_id,
                        COALESCE(a.title, 'Assignment #' || s.assignment_id),
                        COUNT(s.id),
                        SUM(s.weight_percent),
                        MIN(CASE WHEN s.deadline >= datetime('now') THEN s.deadline END)
                    FROM assignment_stages s
                    LEFT JOIN assignments a ON a.id = s.assignment_id
                    GROUP BY s.assignment_id
                    ORDER BY MIN(s.deadline) DESC
                ''')
                rows = cursor.fetchall()

                for row in rows:
                    aid, title, stage_count, total_weight, next_dl = row
                    status = "Active" if next_dl else "Completed"
                    next_dl_display = next_dl if next_dl else "All passed"
                    tree.insert("", tk.END, values=(
                        aid, title, stage_count,
                        f"{total_weight:.0f}%", next_dl_display, status
                    ))
            finally:
                conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load assignments: {e}")

        # Double-click to view progress
        def on_select(event):
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                assignment_id = item['values'][0]
                self.show_stage_progress(assignment_id)

        tree.bind("<Double-1>", on_select)

        # Button bar
        btn_frame = ttk.Frame(content)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(btn_frame, text="View Progress", command=lambda: on_select(None) if tree.selection() else None).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(btn_frame, text="External Submissions", command=self.show_external_submissions).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(btn_frame, text="Refresh", command=self.show_multi_stage_assignments).pack(
            side=tk.RIGHT, padx=5
        )

    # ──────────────────────────────────────────────────────────────────
    # Create multi-stage assignment
    # ──────────────────────────────────────────────────────────────────

    def create_multi_stage_assignment(self):
        """Form to create an assignment with multiple stages"""
        if not self._check_permission('manage_assignments'):
            messagebox.showwarning("Permission Denied", "You do not have permission to create assignments.")
            return

        self.gui.layout.clear_content_area()
        content = self.gui.layout.content_area

        ttk.Label(content, text="Create Multi-Stage Assignment", font=("Segoe UI", 16, "bold")).pack(
            padx=10, pady=(10, 5), anchor=tk.W
        )

        # Scrollable form
        canvas = tk.Canvas(content, highlightthickness=0)
        form_scroll = ttk.Scrollbar(content, orient=tk.VERTICAL, command=canvas.yview)
        form_frame = ttk.Frame(canvas)

        form_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=form_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=form_scroll.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=5)
        form_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Assignment selection
        ttk.Label(form_frame, text="Assignment ID:", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=5
        )
        assignment_id_var = tk.StringVar()
        assignment_combo = ttk.Combobox(form_frame, textvariable=assignment_id_var, width=40)
        assignment_combo.grid(row=0, column=1, columnspan=2, sticky=tk.W, padx=5, pady=5)

        # Load assignments into combo
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT id, title FROM assignments WHERE is_active = 1 ORDER BY title")
                assignments = cursor.fetchall()
                assignment_combo['values'] = [f"{a[0]} - {a[1]}" for a in assignments]
                self._assignment_map = {f"{a[0]} - {a[1]}": a[0] for a in assignments}
            finally:
                conn.close()
        except Exception:
            self._assignment_map = {}

        # Stages container
        ttk.Separator(form_frame, orient=tk.HORIZONTAL).grid(
            row=1, column=0, columnspan=4, sticky=tk.EW, pady=10
        )
        ttk.Label(form_frame, text="Stages", font=("Segoe UI", 12, "bold")).grid(
            row=2, column=0, sticky=tk.W, padx=5, pady=5
        )

        stages_frame = ttk.Frame(form_frame)
        stages_frame.grid(row=3, column=0, columnspan=4, sticky=tk.EW, padx=5, pady=5)

        stage_widgets = []

        def add_stage_row(stage_num=None):
            idx = len(stage_widgets)
            if stage_num is None:
                stage_num = idx + 1

            row_frame = ttk.LabelFrame(stages_frame, text=f"Stage {stage_num}")
            row_frame.pack(fill=tk.X, padx=5, pady=5)

            # Stage name
            ttk.Label(row_frame, text="Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=3)
            name_var = tk.StringVar()
            default_names = {1: "Outline", 2: "Draft", 3: "Final"}
            name_var.set(default_names.get(stage_num, f"Stage {stage_num}"))
            name_entry = ttk.Entry(row_frame, textvariable=name_var, width=30)
            name_entry.grid(row=0, column=1, padx=5, pady=3)

            # Description
            ttk.Label(row_frame, text="Description:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=3)
            desc_var = tk.StringVar()
            desc_entry = ttk.Entry(row_frame, textvariable=desc_var, width=40)
            desc_entry.grid(row=0, column=3, padx=5, pady=3)

            # Weight
            ttk.Label(row_frame, text="Weight %:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=3)
            weight_var = tk.StringVar(value="0")
            weight_entry = ttk.Entry(row_frame, textvariable=weight_var, width=10)
            weight_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=3)

            # Deadline
            ttk.Label(row_frame, text="Deadline (YYYY-MM-DD HH:MM):").grid(
                row=1, column=2, sticky=tk.W, padx=5, pady=3
            )
            deadline_var = tk.StringVar()
            default_deadline = (datetime.now() + timedelta(days=7 * (stage_num))).strftime("%Y-%m-%d 23:59")
            deadline_var.set(default_deadline)
            deadline_entry = ttk.Entry(row_frame, textvariable=deadline_var, width=20)
            deadline_entry.grid(row=1, column=3, sticky=tk.W, padx=5, pady=3)

            # Feedback required
            feedback_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(row_frame, text="Feedback required before next stage", variable=feedback_var).grid(
                row=2, column=0, columnspan=3, sticky=tk.W, padx=5, pady=3
            )

            # Remove button
            def remove_this():
                row_frame.destroy()
                stage_widgets[:] = [w for w in stage_widgets if w['frame'].winfo_exists()]
                # Renumber remaining stages
                for i, w in enumerate(stage_widgets):
                    w['frame'].configure(text=f"Stage {i + 1}")

            ttk.Button(row_frame, text="Remove", command=remove_this).grid(
                row=2, column=3, sticky=tk.E, padx=5, pady=3
            )

            stage_widgets.append({
                'frame': row_frame,
                'name': name_var,
                'description': desc_var,
                'weight': weight_var,
                'deadline': deadline_var,
                'feedback_required': feedback_var,
            })

        # Add default stages (outline, draft, final)
        for i in range(1, 4):
            add_stage_row(i)

        # Add/remove stage buttons
        stage_btn_frame = ttk.Frame(form_frame)
        stage_btn_frame.grid(row=4, column=0, columnspan=4, sticky=tk.W, padx=5, pady=5)

        ttk.Button(stage_btn_frame, text="+ Add Stage", command=lambda: add_stage_row()).pack(side=tk.LEFT, padx=5)

        # Save button
        ttk.Separator(form_frame, orient=tk.HORIZONTAL).grid(
            row=5, column=0, columnspan=4, sticky=tk.EW, pady=10
        )

        def save_assignment():
            # Validate assignment selection
            selected = assignment_id_var.get().strip()
            if not selected:
                messagebox.showwarning("Validation", "Please select an assignment.")
                return

            aid = self._assignment_map.get(selected)
            if aid is None:
                # Try parsing as raw ID
                try:
                    aid = int(selected.split(" - ")[0])
                except (ValueError, IndexError):
                    messagebox.showwarning("Validation", "Invalid assignment selection.")
                    return

            # Collect live stage widgets
            live_stages = [w for w in stage_widgets if w['frame'].winfo_exists()]
            if not live_stages:
                messagebox.showwarning("Validation", "Add at least one stage.")
                return

            # Validate weights
            total_weight = 0
            stage_data = []
            for i, w in enumerate(live_stages):
                name = w['name'].get().strip()
                if not name:
                    messagebox.showwarning("Validation", f"Stage {i + 1} needs a name.")
                    return

                try:
                    weight = float(w['weight'].get())
                except ValueError:
                    messagebox.showwarning("Validation", f"Stage {i + 1} has an invalid weight.")
                    return

                deadline = w['deadline'].get().strip()
                if not deadline:
                    messagebox.showwarning("Validation", f"Stage {i + 1} needs a deadline.")
                    return

                # Basic deadline format check
                try:
                    datetime.strptime(deadline, "%Y-%m-%d %H:%M")
                except ValueError:
                    messagebox.showwarning(
                        "Validation",
                        f"Stage {i + 1} deadline must be in YYYY-MM-DD HH:MM format."
                    )
                    return

                total_weight += weight
                stage_data.append({
                    'stage_number': i + 1,
                    'name': name,
                    'description': w['description'].get().strip(),
                    'weight': weight,
                    'deadline': deadline,
                    'feedback_required': 1 if w['feedback_required'].get() else 0,
                })

            if total_weight > 0 and abs(total_weight - 100) > 0.01:
                if not messagebox.askyesno(
                    "Weight Warning",
                    f"Stage weights sum to {total_weight:.1f}%, not 100%. Continue anyway?"
                ):
                    return

            # Insert into database
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                try:
                    cursor = conn.cursor()
                    for sd in stage_data:
                        cursor.execute('''
                            INSERT INTO assignment_stages
                            (assignment_id, stage_number, stage_name, description,
                             weight_percent, deadline, feedback_required)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            aid, sd['stage_number'], sd['name'], sd['description'],
                            sd['weight'], sd['deadline'], sd['feedback_required']
                        ))
                    conn.commit()
                    messagebox.showinfo("Success", f"Created {len(stage_data)} stages for assignment.")
                    self.show_multi_stage_assignments()
                finally:
                    conn.close()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save stages: {e}")

        btn_row = ttk.Frame(form_frame)
        btn_row.grid(row=6, column=0, columnspan=4, sticky=tk.E, padx=5, pady=10)
        ttk.Button(btn_row, text="Save", command=save_assignment).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_row, text="Cancel", command=self.show_multi_stage_assignments).pack(side=tk.RIGHT, padx=5)

    # ──────────────────────────────────────────────────────────────────
    # Stage progress view
    # ──────────────────────────────────────────────────────────────────

    def show_stage_progress(self, assignment_id):
        """View all students' progress through the stages of an assignment"""
        self.gui.layout.clear_content_area()
        content = self.gui.layout.content_area

        # Header
        header_frame = ttk.Frame(content)
        header_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Label(
            header_frame, text=f"Stage Progress - Assignment #{assignment_id}",
            font=("Segoe UI", 16, "bold")
        ).pack(side=tk.LEFT)

        ttk.Button(header_frame, text="Back", command=self.show_multi_stage_assignments).pack(
            side=tk.RIGHT, padx=5
        )

        # Load stages
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, stage_number, stage_name, weight_percent, deadline, feedback_required
                    FROM assignment_stages
                    WHERE assignment_id = ?
                    ORDER BY stage_number
                ''', (assignment_id,))
                stages = cursor.fetchall()

                if not stages:
                    ttk.Label(content, text="No stages defined for this assignment.").pack(padx=10, pady=20)
                    return

                # Stage summary
                summary_frame = ttk.LabelFrame(content, text="Stages Overview")
                summary_frame.pack(fill=tk.X, padx=10, pady=5)

                for stage in stages:
                    sid, snum, sname, weight, deadline, fb_req = stage
                    stage_label = f"  Stage {snum}: {sname} | Weight: {weight:.0f}% | Deadline: {deadline}"
                    if fb_req:
                        stage_label += " | Feedback Required"
                    ttk.Label(summary_frame, text=stage_label).pack(anchor=tk.W, padx=5, pady=2)

                # Student progress treeview
                ttk.Separator(content, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)

                tree_frame = ttk.Frame(content)
                tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

                # Build columns: student + one per stage
                columns = ["student_id", "student_name"] + [f"stage_{s[1]}" for s in stages]
                tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

                tree.heading("student_id", text="Student ID")
                tree.heading("student_name", text="Student")
                tree.column("student_id", width=100, anchor=tk.CENTER)
                tree.column("student_name", width=150)

                for stage in stages:
                    col = f"stage_{stage[1]}"
                    tree.heading(col, text=f"S{stage[1]}: {stage[2]}")
                    tree.column(col, width=120, anchor=tk.CENTER)

                scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
                tree.configure(yscrollcommand=scrollbar.set)
                tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                # Fetch submission data
                stage_ids = [s[0] for s in stages]
                placeholders = ",".join("?" * len(stage_ids))
                cursor.execute(f'''
                    SELECT ss.stage_id, ss.student_id, ss.status
                    FROM stage_submissions ss
                    WHERE ss.stage_id IN ({placeholders})
                ''', stage_ids)
                submissions = cursor.fetchall()

                # Build lookup: (stage_id, student_id) -> status
                sub_map = {}
                student_ids = set()
                for stage_id, student_id, status in submissions:
                    sub_map[(stage_id, student_id)] = status
                    student_ids.add(student_id)

                # If no submissions yet, check enrolled students
                if not student_ids:
                    cursor.execute('''
                        SELECT DISTINCT sm.student_id
                        FROM student_modules sm
                        JOIN assignments a ON a.module_code = sm.module_code
                        WHERE a.id = ?
                    ''', (assignment_id,))
                    for row in cursor.fetchall():
                        student_ids.add(row[0])

                # Get student names
                name_map = {}
                if student_ids:
                    id_placeholders = ",".join("?" * len(student_ids))
                    sid_list = list(student_ids)
                    cursor.execute(f'''
                        SELECT student_id, first_name || ' ' || last_name
                        FROM students WHERE student_id IN ({id_placeholders})
                    ''', sid_list)
                    for sid, name in cursor.fetchall():
                        name_map[sid] = name

                # Populate tree
                for student_id in sorted(student_ids):
                    values = [student_id, name_map.get(student_id, "Unknown")]
                    for stage in stages:
                        status = sub_map.get((stage[0], student_id), "-")
                        values.append(status)
                    tree.insert("", tk.END, values=values)

                # Double-click to review
                def on_tree_double_click(event):
                    sel = tree.selection()
                    if not sel:
                        return
                    item = tree.item(sel[0])
                    vals = item['values']
                    student_id = vals[0]

                    # Determine which column was clicked
                    col_id = tree.identify_column(event.x)
                    col_idx = int(col_id.replace('#', '')) - 1
                    if col_idx >= 2:
                        stage_num = stages[col_idx - 2][1]
                        if self._check_permission('manage_assignments'):
                            self.review_stage(assignment_id, student_id, stage_num)
                        else:
                            self.submit_stage(assignment_id, stage_num)

                tree.bind("<Double-1>", on_tree_double_click)

            finally:
                conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load stage progress: {e}")

        # Action buttons
        action_frame = ttk.Frame(content)
        action_frame.pack(fill=tk.X, padx=10, pady=5)

        student_id = self._get_student_id()
        if student_id:
            for stage in stages if 'stages' in dir() else []:
                ttk.Button(
                    action_frame,
                    text=f"Submit Stage {stage[1]}",
                    command=lambda sn=stage[1]: self.submit_stage(assignment_id, sn)
                ).pack(side=tk.LEFT, padx=3)

    # ──────────────────────────────────────────────────────────────────
    # Submit a stage
    # ──────────────────────────────────────────────────────────────────

    def submit_stage(self, assignment_id, stage_number):
        """Student form to submit work for a specific stage"""
        student_id = self._get_student_id()
        if not student_id:
            messagebox.showwarning("Auth Required", "Cannot determine your student ID.")
            return

        self.gui.layout.clear_content_area()
        content = self.gui.layout.content_area

        # Load stage info
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, stage_name, description, deadline, feedback_required
                    FROM assignment_stages
                    WHERE assignment_id = ? AND stage_number = ?
                ''', (assignment_id, stage_number))
                stage = cursor.fetchone()

                if not stage:
                    messagebox.showerror("Error", "Stage not found.")
                    self.show_stage_progress(assignment_id)
                    return

                stage_id, stage_name, description, deadline, feedback_required = stage

                # Check if previous stage requires feedback before this one
                if stage_number > 1 and feedback_required:
                    cursor.execute('''
                        SELECT id FROM assignment_stages
                        WHERE assignment_id = ? AND stage_number = ?
                    ''', (assignment_id, stage_number - 1))
                    prev_stage = cursor.fetchone()

                    if prev_stage:
                        cursor.execute('''
                            SELECT status FROM stage_submissions
                            WHERE stage_id = ? AND student_id = ?
                            ORDER BY submitted_at DESC LIMIT 1
                        ''', (prev_stage[0], student_id))
                        prev_sub = cursor.fetchone()

                        if not prev_sub:
                            messagebox.showwarning(
                                "Stage Locked",
                                f"You must complete Stage {stage_number - 1} before submitting Stage {stage_number}."
                            )
                            self.show_stage_progress(assignment_id)
                            return

                        if prev_sub[0] not in ('approved', 'reviewed'):
                            # Check if previous stage requires feedback
                            cursor.execute('''
                                SELECT feedback_required FROM assignment_stages
                                WHERE assignment_id = ? AND stage_number = ?
                            ''', (assignment_id, stage_number - 1))
                            prev_stage_info = cursor.fetchone()
                            if prev_stage_info and prev_stage_info[0]:
                                messagebox.showwarning(
                                    "Stage Locked",
                                    f"Stage {stage_number - 1} must be reviewed/approved before you can submit Stage {stage_number}."
                                )
                                self.show_stage_progress(assignment_id)
                                return

                # Check for existing submission
                cursor.execute('''
                    SELECT id, content, file_path, status, feedback
                    FROM stage_submissions
                    WHERE stage_id = ? AND student_id = ?
                    ORDER BY submitted_at DESC LIMIT 1
                ''', (stage_id, student_id))
                existing = cursor.fetchone()

            finally:
                conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load stage: {e}")
            return

        # Header
        ttk.Label(
            content,
            text=f"Submit Stage {stage_number}: {stage_name}",
            font=("Segoe UI", 16, "bold")
        ).pack(padx=10, pady=(10, 5), anchor=tk.W)

        info_frame = ttk.LabelFrame(content, text="Stage Information")
        info_frame.pack(fill=tk.X, padx=10, pady=5)

        if description:
            ttk.Label(info_frame, text=f"Description: {description}", wraplength=600).pack(
                anchor=tk.W, padx=5, pady=3
            )
        ttk.Label(info_frame, text=f"Deadline: {deadline}").pack(anchor=tk.W, padx=5, pady=3)

        # Show existing feedback if present
        if existing and existing[4]:
            fb_frame = ttk.LabelFrame(content, text="Instructor Feedback on Previous Submission")
            fb_frame.pack(fill=tk.X, padx=10, pady=5)
            ttk.Label(
                fb_frame, text=existing[4], wraplength=600,
                foreground="blue"
            ).pack(padx=5, pady=5, anchor=tk.W)

        # Submission form
        form_frame = ttk.LabelFrame(content, text="Your Submission")
        form_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        ttk.Label(form_frame, text="Content:").pack(anchor=tk.W, padx=5, pady=(5, 0))
        content_text = scrolledtext.ScrolledText(form_frame, height=12, width=80, wrap=tk.WORD)
        content_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Pre-fill if existing draft
        if existing and existing[1]:
            content_text.insert("1.0", existing[1])

        ttk.Label(form_frame, text="File Path (optional):").pack(anchor=tk.W, padx=5, pady=(5, 0))
        file_var = tk.StringVar(value=existing[2] if existing and existing[2] else "")
        ttk.Entry(form_frame, textvariable=file_var, width=60).pack(anchor=tk.W, padx=5, pady=3)

        # Status indicator
        if existing:
            ttk.Label(
                form_frame, text=f"Current status: {existing[3]}",
                font=("Segoe UI", 9, "italic")
            ).pack(anchor=tk.W, padx=5, pady=3)

        # Buttons
        btn_frame = ttk.Frame(content)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        def do_submit(status='submitted'):
            text_content = content_text.get("1.0", tk.END).strip()
            file_path = file_var.get().strip()

            if not text_content and not file_path:
                messagebox.showwarning("Validation", "Please provide content or a file path.")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                try:
                    cursor = conn.cursor()
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    if existing:
                        cursor.execute('''
                            UPDATE stage_submissions
                            SET content = ?, file_path = ?, status = ?, submitted_at = ?
                            WHERE id = ?
                        ''', (text_content, file_path or None, status, now, existing[0]))
                    else:
                        cursor.execute('''
                            INSERT INTO stage_submissions
                            (stage_id, student_id, content, file_path, status, submitted_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (stage_id, student_id, text_content, file_path or None, status, now))

                    conn.commit()
                    messagebox.showinfo("Success", f"Stage {stage_number} {status} successfully.")
                    self.show_stage_progress(assignment_id)
                finally:
                    conn.close()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to submit: {e}")

        ttk.Button(btn_frame, text="Save Draft", command=lambda: do_submit('draft')).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(btn_frame, text="Submit", command=lambda: do_submit('submitted')).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(
            btn_frame, text="Cancel",
            command=lambda: self.show_stage_progress(assignment_id)
        ).pack(side=tk.RIGHT, padx=5)

    # ──────────────────────────────────────────────────────────────────
    # Review a stage submission (instructor)
    # ──────────────────────────────────────────────────────────────────

    def review_stage(self, assignment_id, student_id, stage_number):
        """Instructor review form for a student's stage submission"""
        if not self._check_permission('manage_assignments'):
            messagebox.showwarning("Permission Denied", "You do not have permission to review submissions.")
            return

        self.gui.layout.clear_content_area()
        content = self.gui.layout.content_area

        # Load data
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT id, stage_name, description, weight_percent, deadline
                    FROM assignment_stages
                    WHERE assignment_id = ? AND stage_number = ?
                ''', (assignment_id, stage_number))
                stage = cursor.fetchone()

                if not stage:
                    messagebox.showerror("Error", "Stage not found.")
                    self.show_stage_progress(assignment_id)
                    return

                stage_id, stage_name, description, weight, deadline = stage

                cursor.execute('''
                    SELECT id, content, file_path, status, feedback, submitted_at
                    FROM stage_submissions
                    WHERE stage_id = ? AND student_id = ?
                    ORDER BY submitted_at DESC LIMIT 1
                ''', (stage_id, student_id))
                submission = cursor.fetchone()

                # Get student name
                cursor.execute('''
                    SELECT first_name || ' ' || last_name FROM students WHERE student_id = ?
                ''', (student_id,))
                name_row = cursor.fetchone()
                student_name = name_row[0] if name_row else str(student_id)

            finally:
                conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load review data: {e}")
            return

        # Header
        ttk.Label(
            content,
            text=f"Review Stage {stage_number}: {stage_name}",
            font=("Segoe UI", 16, "bold")
        ).pack(padx=10, pady=(10, 5), anchor=tk.W)

        ttk.Label(content, text=f"Student: {student_name} ({student_id})").pack(
            padx=10, pady=2, anchor=tk.W
        )
        ttk.Label(content, text=f"Weight: {weight:.0f}% | Deadline: {deadline}").pack(
            padx=10, pady=2, anchor=tk.W
        )

        if not submission:
            ttk.Label(
                content, text="No submission found for this stage.",
                font=("Segoe UI", 11, "italic"), foreground="gray"
            ).pack(padx=10, pady=20)
            ttk.Button(
                content, text="Back",
                command=lambda: self.show_stage_progress(assignment_id)
            ).pack(padx=10, pady=5)
            return

        sub_id, sub_content, sub_file, sub_status, sub_feedback, sub_date = submission

        # Submission details
        info_frame = ttk.LabelFrame(content, text="Submission Details")
        info_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(info_frame, text=f"Status: {sub_status} | Submitted: {sub_date}").pack(
            anchor=tk.W, padx=5, pady=3
        )
        if sub_file:
            ttk.Label(info_frame, text=f"File: {sub_file}").pack(anchor=tk.W, padx=5, pady=3)

        # Show content
        content_frame = ttk.LabelFrame(content, text="Submission Content")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        content_display = scrolledtext.ScrolledText(
            content_frame, height=10, width=80, wrap=tk.WORD, state=tk.NORMAL
        )
        content_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        if sub_content:
            content_display.insert("1.0", sub_content)
        content_display.configure(state=tk.DISABLED)

        # Feedback entry
        feedback_frame = ttk.LabelFrame(content, text="Feedback")
        feedback_frame.pack(fill=tk.X, padx=10, pady=5)

        feedback_text = scrolledtext.ScrolledText(feedback_frame, height=5, width=80, wrap=tk.WORD)
        feedback_text.pack(fill=tk.X, padx=5, pady=5)
        if sub_feedback:
            feedback_text.insert("1.0", sub_feedback)

        # Action buttons
        btn_frame = ttk.Frame(content)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        def do_review(new_status):
            feedback = feedback_text.get("1.0", tk.END).strip()
            if new_status == 'approved' and not feedback:
                if not messagebox.askyesno("No Feedback", "Approve without feedback?"):
                    return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                try:
                    cursor = conn.cursor()
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute('''
                        UPDATE stage_submissions
                        SET status = ?, feedback = ?, reviewed_at = ?
                        WHERE id = ?
                    ''', (new_status, feedback or None, now, sub_id))
                    conn.commit()
                    messagebox.showinfo("Success", f"Submission marked as {new_status}.")
                    self.show_stage_progress(assignment_id)
                finally:
                    conn.close()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save review: {e}")

        ttk.Button(btn_frame, text="Approve", command=lambda: do_review('approved')).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(btn_frame, text="Request Revision", command=lambda: do_review('reviewed')).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(
            btn_frame, text="Back",
            command=lambda: self.show_stage_progress(assignment_id)
        ).pack(side=tk.RIGHT, padx=5)

    # ──────────────────────────────────────────────────────────────────
    # External submissions dashboard
    # ──────────────────────────────────────────────────────────────────

    def show_external_submissions(self):
        """Dashboard for external tool submissions"""
        self.gui.layout.clear_content_area()
        content = self.gui.layout.content_area

        header_frame = ttk.Frame(content)
        header_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Label(
            header_frame, text="External Tool Submissions",
            font=("Segoe UI", 16, "bold")
        ).pack(side=tk.LEFT)

        ttk.Button(header_frame, text="Back", command=self.show_multi_stage_assignments).pack(
            side=tk.RIGHT, padx=5
        )

        # Treeview
        tree_frame = ttk.Frame(content)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("id", "assignment", "student", "link_type", "url", "validated", "submitted_at")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=16)

        tree.heading("id", text="ID")
        tree.heading("assignment", text="Assignment")
        tree.heading("student", text="Student")
        tree.heading("link_type", text="Type")
        tree.heading("url", text="URL")
        tree.heading("validated", text="Validated")
        tree.heading("submitted_at", text="Submitted")

        tree.column("id", width=40, anchor=tk.CENTER)
        tree.column("assignment", width=160)
        tree.column("student", width=120)
        tree.column("link_type", width=90, anchor=tk.CENTER)
        tree.column("url", width=250)
        tree.column("validated", width=70, anchor=tk.CENTER)
        tree.column("submitted_at", width=140, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load data
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                student_id = self._get_student_id()
                is_instructor = self._check_permission('manage_assignments')

                if is_instructor:
                    cursor.execute('''
                        SELECT es.id, COALESCE(a.title, 'Assignment #' || es.assignment_id),
                               es.student_id, es.link_type, es.url, es.is_validated, es.submitted_at
                        FROM external_submissions es
                        LEFT JOIN assignments a ON a.id = es.assignment_id
                        ORDER BY es.submitted_at DESC
                    ''')
                elif student_id:
                    cursor.execute('''
                        SELECT es.id, COALESCE(a.title, 'Assignment #' || es.assignment_id),
                               es.student_id, es.link_type, es.url, es.is_validated, es.submitted_at
                        FROM external_submissions es
                        LEFT JOIN assignments a ON a.id = es.assignment_id
                        WHERE es.student_id = ?
                        ORDER BY es.submitted_at DESC
                    ''', (student_id,))
                else:
                    cursor.execute('''
                        SELECT es.id, COALESCE(a.title, 'Assignment #' || es.assignment_id),
                               es.student_id, es.link_type, es.url, es.is_validated, es.submitted_at
                        FROM external_submissions es
                        LEFT JOIN assignments a ON a.id = es.assignment_id
                        ORDER BY es.submitted_at DESC
                    ''')

                rows = cursor.fetchall()
                for row in rows:
                    eid, title, sid, ltype, url, validated, submitted = row
                    validated_str = "Yes" if validated else "No"
                    tree.insert("", tk.END, values=(
                        eid, title, sid, ltype, url, validated_str, submitted
                    ))
            finally:
                conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load external submissions: {e}")

        # Action buttons
        btn_frame = ttk.Frame(content)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        # Submit new external link - assignment selector popup
        def prompt_submit():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, title FROM assignments WHERE is_active = 1 ORDER BY title")
                    assignments = cursor.fetchall()
                finally:
                    conn.close()
            except Exception:
                assignments = []

            if not assignments:
                messagebox.showinfo("Info", "No active assignments available.")
                return

            # Quick selection dialog
            win = tk.Toplevel(self.root)
            win.title("Select Assignment")
            win.geometry("400x300")
            win.transient(self.root)
            win.grab_set()

            ttk.Label(win, text="Select assignment:", font=("Segoe UI", 10, "bold")).pack(
                padx=10, pady=10
            )
            listbox = tk.Listbox(win, height=10)
            listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            for a in assignments:
                listbox.insert(tk.END, f"{a[0]} - {a[1]}")

            def on_ok():
                sel = listbox.curselection()
                if sel:
                    aid = assignments[sel[0]][0]
                    win.destroy()
                    self.submit_external_link(aid)
                else:
                    messagebox.showwarning("Selection", "Please select an assignment.", parent=win)

            ttk.Button(win, text="OK", command=on_ok).pack(pady=10)

        ttk.Button(btn_frame, text="Submit External Link", command=prompt_submit).pack(
            side=tk.LEFT, padx=5
        )

        def validate_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Info", "Select a submission to validate.")
                return
            item = tree.item(sel[0])
            url = item['values'][4]
            sub_id = item['values'][0]
            is_valid = self.validate_external_link(url)
            # Update DB
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE external_submissions SET is_validated = ? WHERE id = ?",
                        (1 if is_valid else 0, sub_id)
                    )
                    conn.commit()
                finally:
                    conn.close()
            except Exception:
                pass
            self.show_external_submissions()

        ttk.Button(btn_frame, text="Validate Selected", command=validate_selected).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(btn_frame, text="Refresh", command=self.show_external_submissions).pack(
            side=tk.RIGHT, padx=5
        )

    # ──────────────────────────────────────────────────────────────────
    # Submit external link
    # ──────────────────────────────────────────────────────────────────

    def submit_external_link(self, assignment_id):
        """Student form to submit an external URL for an assignment"""
        student_id = self._get_student_id()
        if not student_id:
            messagebox.showwarning("Auth Required", "Cannot determine your student ID.")
            return

        self.gui.layout.clear_content_area()
        content = self.gui.layout.content_area

        ttk.Label(
            content,
            text=f"Submit External Link - Assignment #{assignment_id}",
            font=("Segoe UI", 16, "bold")
        ).pack(padx=10, pady=(10, 5), anchor=tk.W)

        form_frame = ttk.LabelFrame(content, text="External Submission")
        form_frame.pack(fill=tk.X, padx=10, pady=10)

        # Link type
        ttk.Label(form_frame, text="Link Type:", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=8
        )
        link_type_var = tk.StringVar(value="github")
        type_combo = ttk.Combobox(
            form_frame, textvariable=link_type_var, state="readonly", width=20,
            values=["github", "google_docs", "figma", "other"]
        )
        type_combo.grid(row=0, column=1, sticky=tk.W, padx=10, pady=8)

        # URL hints per type
        hints = {
            "github": "e.g. https://github.com/user/repo",
            "google_docs": "e.g. https://docs.google.com/document/d/...",
            "figma": "e.g. https://www.figma.com/file/...",
            "other": "Any valid URL",
        }
        hint_label = ttk.Label(form_frame, text=hints["github"], foreground="gray")
        hint_label.grid(row=0, column=2, sticky=tk.W, padx=5, pady=8)

        def update_hint(event=None):
            lt = link_type_var.get()
            hint_label.configure(text=hints.get(lt, ""))

        type_combo.bind("<<ComboboxSelected>>", update_hint)

        # URL entry
        ttk.Label(form_frame, text="URL:", font=("Segoe UI", 10, "bold")).grid(
            row=1, column=0, sticky=tk.W, padx=10, pady=8
        )
        url_var = tk.StringVar()
        url_entry = ttk.Entry(form_frame, textvariable=url_var, width=60)
        url_entry.grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=10, pady=8)

        # Validation status
        validation_label = ttk.Label(form_frame, text="", font=("Segoe UI", 9))
        validation_label.grid(row=2, column=1, columnspan=2, sticky=tk.W, padx=10, pady=3)

        def do_validate():
            url = url_var.get().strip()
            if not url:
                messagebox.showwarning("Validation", "Please enter a URL.")
                return
            is_valid = self.validate_external_link(url)
            if is_valid:
                validation_label.configure(text="Link is accessible.", foreground="green")
            else:
                validation_label.configure(text="Link could not be validated.", foreground="red")

        ttk.Button(form_frame, text="Validate", command=do_validate).grid(
            row=2, column=0, sticky=tk.W, padx=10, pady=3
        )

        # Buttons
        btn_frame = ttk.Frame(content)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        def do_submit():
            url = url_var.get().strip()
            link_type = link_type_var.get()

            if not url:
                messagebox.showwarning("Validation", "Please enter a URL.")
                return

            # Basic URL format check
            url_pattern = re.compile(
                r'^https?://'
                r'(?:[a-zA-Z0-9\-]+\.)+[a-zA-Z]{2,}'
                r'(?:/[^\s]*)?$'
            )
            if not url_pattern.match(url):
                messagebox.showwarning("Validation", "Please enter a valid URL starting with http:// or https://")
                return

            # Type-specific URL validation
            type_patterns = {
                'github': r'https?://(?:www\.)?github\.com/',
                'google_docs': r'https?://docs\.google\.com/',
                'figma': r'https?://(?:www\.)?figma\.com/',
            }
            if link_type in type_patterns:
                if not re.match(type_patterns[link_type], url):
                    if not messagebox.askyesno(
                        "URL Mismatch",
                        f"The URL does not appear to be a {link_type.replace('_', ' ')} link. Submit anyway?"
                    ):
                        return

            # Auto-validate
            is_valid = self.validate_external_link(url)

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                try:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO external_submissions
                        (assignment_id, student_id, url, link_type, is_validated, submitted_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        assignment_id, student_id, url, link_type,
                        1 if is_valid else 0,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))
                    conn.commit()

                    valid_msg = " (validated)" if is_valid else " (not validated - link may be inaccessible)"
                    messagebox.showinfo("Success", f"External link submitted{valid_msg}.")
                    self.show_external_submissions()
                finally:
                    conn.close()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to submit external link: {e}")

        ttk.Button(btn_frame, text="Submit", command=do_submit).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.show_external_submissions).pack(
            side=tk.RIGHT, padx=5
        )

    # ──────────────────────────────────────────────────────────────────
    # External link validation
    # ──────────────────────────────────────────────────────────────────

    def validate_external_link(self, url):
        """Check if an external URL is accessible. Returns True if reachable, False otherwise."""
        if not url or not url.strip():
            return False

        url = url.strip()

        # Basic format check
        url_pattern = re.compile(
            r'^https?://'
            r'(?:[a-zA-Z0-9\-]+\.)+[a-zA-Z]{2,}'
            r'(?:/[^\s]*)?$'
        )
        if not url_pattern.match(url):
            return False

        try:
            import urllib.request
            import urllib.error

            req = urllib.request.Request(url, method='HEAD')
            req.add_header('User-Agent', 'Mozilla/5.0 (EducationSystem LinkValidator)')
            response = urllib.request.urlopen(req, timeout=10)
            return response.status < 400
        except Exception:
            # Try GET as fallback since some servers reject HEAD
            try:
                import urllib.request

                req = urllib.request.Request(url, method='GET')
                req.add_header('User-Agent', 'Mozilla/5.0 (EducationSystem LinkValidator)')
                response = urllib.request.urlopen(req, timeout=10)
                return response.status < 400
            except Exception:
                return False
