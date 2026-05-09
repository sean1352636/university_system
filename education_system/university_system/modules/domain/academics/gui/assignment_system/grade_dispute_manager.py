"""Grade dispute and appeal workflow management"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import json
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH


class GradeDisputeManager:
    """Grade dispute and appeal workflow management"""

    STATUSES = ['pending', 'under_review', 'approved', 'denied']

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style
        self._ensure_table()

    def _ensure_table(self):
        """Create the grade_disputes table if it does not exist"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS grade_disputes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER,
                    student_id TEXT NOT NULL,
                    assignment_id INTEGER NOT NULL,
                    original_grade REAL,
                    requested_action TEXT,
                    reason TEXT NOT NULL,
                    evidence_path TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    reviewer_id TEXT,
                    reviewer_comments TEXT,
                    new_grade REAL,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT
                )
                ''')
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"Error creating grade_disputes table: {e}")

    def _check_permission(self, permission):
        """Check if user has permission"""
        try:
            return self.auth.check_permission(permission)
        except (AttributeError, Exception):
            return self.auth.user_role in ['Admin', 'Faculty']

    def _get_student_id_safe(self):
        """Safely get student ID with fallback"""
        try:
            if hasattr(self.assignment_system, '_get_student_id'):
                return self.assignment_system._get_student_id()
            if self.auth and self.auth.current_user:
                return self.auth.current_user.get('id') or self.auth.current_user.get('student_id')
            return None
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    #  Student: Submit a grade dispute
    # ------------------------------------------------------------------ #

    def show_dispute_form(self):
        """Student form to submit a grade dispute"""
        self.gui.layout.clear_content_area()
        parent = self.gui.layout.content_area

        title = ttk.Label(parent, text="Submit Grade Dispute", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        form_frame = ttk.LabelFrame(parent, text="Dispute Details", padding=15)
        form_frame.pack(fill='x', pady=(0, 10))

        # Assignment selector
        ttk.Label(form_frame, text="Assignment:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.dispute_assignment_combo = ttk.Combobox(form_frame, state='readonly', width=50)
        self.dispute_assignment_combo.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
        self.dispute_assignment_combo.bind('<<ComboboxSelected>>', self._on_dispute_assignment_selected)

        # Original grade (read-only, populated on assignment select)
        ttk.Label(form_frame, text="Original Grade:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.dispute_original_grade_var = tk.StringVar(value="--")
        ttk.Label(form_frame, textvariable=self.dispute_original_grade_var).grid(
            row=1, column=1, sticky='w', padx=5, pady=5
        )

        # Requested action
        ttk.Label(form_frame, text="Requested Action:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.dispute_action_combo = ttk.Combobox(
            form_frame, state='readonly', width=50,
            values=['Full regrade', 'Partial regrade', 'Grade review', 'Rubric clarification']
        )
        self.dispute_action_combo.grid(row=2, column=1, sticky='ew', padx=5, pady=5)
        self.dispute_action_combo.current(0)

        # Reason
        ttk.Label(form_frame, text="Reason:").grid(row=3, column=0, sticky='nw', padx=5, pady=5)
        self.dispute_reason_text = scrolledtext.ScrolledText(form_frame, width=50, height=6)
        self.dispute_reason_text.grid(row=3, column=1, sticky='ew', padx=5, pady=5)

        # Evidence attachment
        ttk.Label(form_frame, text="Evidence:").grid(row=4, column=0, sticky='w', padx=5, pady=5)
        evidence_frame = ttk.Frame(form_frame)
        evidence_frame.grid(row=4, column=1, sticky='ew', padx=5, pady=5)

        self.dispute_evidence_var = tk.StringVar(value="No file selected")
        ttk.Label(evidence_frame, textvariable=self.dispute_evidence_var).pack(side='left', padx=(0, 10))
        ttk.Button(evidence_frame, text="Browse...", command=self._browse_evidence).pack(side='left')

        form_frame.columnconfigure(1, weight=1)

        # Submit button
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill='x', pady=10)
        ttk.Button(btn_frame, text="Submit Dispute", command=self._submit_dispute).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.show_my_disputes).pack(side='left', padx=5)

        # Load assignments for this student
        self._load_graded_assignments()

        # Internal state
        self._dispute_assignment_map = {}
        self._dispute_submission_map = {}
        self._dispute_evidence_path = None

    def _load_graded_assignments(self):
        """Load assignments that have been graded for the current student"""
        student_id = self._get_student_id_safe()
        if not student_id:
            messagebox.showwarning("Warning", "Could not determine student ID.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute('''
                SELECT s.id, s.assignment_id, a.title, a.module_code, s.grade
                FROM assignment_submissions s
                JOIN assignments a ON s.assignment_id = a.id
                WHERE s.student_id = ? AND s.grade IS NOT NULL
                ORDER BY s.submission_date DESC
                ''', (student_id,))

                rows = cursor.fetchall()
                self._dispute_assignment_map = {}
                self._dispute_submission_map = {}
                display_list = []

                for sub_id, assign_id, atitle, module, grade in rows:
                    display = f"{atitle} ({module}) - Grade: {grade}"
                    display_list.append(display)
                    self._dispute_assignment_map[display] = assign_id
                    self._dispute_submission_map[display] = {
                        'submission_id': sub_id,
                        'assignment_id': assign_id,
                        'grade': grade,
                    }

                self.dispute_assignment_combo['values'] = display_list
            finally:
                conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load assignments: {e}")

    def _on_dispute_assignment_selected(self, _event=None):
        """Update original grade when assignment is selected"""
        sel = self.dispute_assignment_combo.get()
        info = self._dispute_submission_map.get(sel)
        if info:
            self.dispute_original_grade_var.set(str(info['grade']))
        else:
            self.dispute_original_grade_var.set("--")

    def _browse_evidence(self):
        """Open file dialog to attach evidence"""
        path = filedialog.askopenfilename(
            title="Select Evidence File",
            filetypes=[
                ("Documents", "*.pdf *.docx *.txt"),
                ("Images", "*.png *.jpg *.jpeg"),
                ("All Files", "*.*"),
            ]
        )
        if path:
            self._dispute_evidence_path = path
            self.dispute_evidence_var.set(path.split('/')[-1] if '/' in path else path.split('\\')[-1])

    def _submit_dispute(self):
        """Validate and submit the grade dispute"""
        sel = self.dispute_assignment_combo.get()
        if not sel:
            messagebox.showwarning("Validation", "Please select an assignment.")
            return

        reason = self.dispute_reason_text.get("1.0", tk.END).strip()
        if not reason:
            messagebox.showwarning("Validation", "Please provide a reason for the dispute.")
            return

        info = self._dispute_submission_map.get(sel, {})
        student_id = self._get_student_id_safe()
        if not student_id:
            messagebox.showerror("Error", "Could not determine student ID.")
            return

        requested_action = self.dispute_action_combo.get()
        evidence_path = getattr(self, '_dispute_evidence_path', None)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute('''
                INSERT INTO grade_disputes
                    (submission_id, student_id, assignment_id, original_grade,
                     requested_action, reason, evidence_path, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                ''', (
                    info.get('submission_id'),
                    student_id,
                    info.get('assignment_id'),
                    info.get('grade'),
                    requested_action,
                    reason,
                    evidence_path,
                    datetime.now().isoformat(),
                ))
                dispute_id = cursor.lastrowid
                conn.commit()

                # Escalate to the helpdesk so support can track it too
                ticket_id = None
                try:
                    from education_system.university_system.modules.domain.academics.gui.assignment_system.integrations import (
                        escalate_dispute_to_helpdesk,
                    )
                    user = (self.auth.current_user or {}) if self.auth else {}
                    ticket_id = escalate_dispute_to_helpdesk(
                        user_id=user.get('id'),
                        student_id=student_id,
                        dispute_id=dispute_id,
                        assignment_title=info.get('assignment_title') or sel,
                        reason=reason,
                    )
                except Exception as helpdesk_err:
                    import logging
                    logging.warning(
                        "helpdesk escalation failed for dispute %s: %s",
                        dispute_id, helpdesk_err,
                    )

                # MC link: if this student has a non-rejected MC claim
                # against the same assessment, surface it on the success
                # dialog so the reviewer can read both records together.
                # Disputes are post-result; MC is pre-result — they often
                # arise from the same underlying event.
                mc_note = ""
                try:
                    from education_system.university_system.modules.domain.academics.mitigating_circumstances.integration import (
                        claims_for_student,
                    )
                    related = [c for c in claims_for_student(student_id)
                               if c.get('module_code') and
                               c.get('module_code') == info.get('module_code')]
                    if related:
                        ids = ", ".join(f"#{c['id']} ({c['status']})" for c in related[:5])
                        mc_note = f"\nRelated MC claim(s): {ids}"
                except Exception:
                    pass

                msg = "Grade dispute submitted successfully."
                if ticket_id:
                    msg += f"\nHelpdesk ticket #{ticket_id} opened."
                msg += mc_note
                messagebox.showinfo("Success", msg)
                self.show_my_disputes()
            finally:
                conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to submit dispute: {e}")

    # ------------------------------------------------------------------ #
    #  Student: View my disputes
    # ------------------------------------------------------------------ #

    def show_my_disputes(self):
        """Student view of their submitted disputes with status"""
        self.gui.layout.clear_content_area()
        parent = self.gui.layout.content_area

        title = ttk.Label(parent, text="My Grade Disputes", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Toolbar
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill='x', pady=(0, 10))
        ttk.Button(toolbar, text="New Dispute", command=self.show_dispute_form).pack(side='left', padx=5)
        ttk.Button(toolbar, text="Refresh", command=self.show_my_disputes).pack(side='left', padx=5)

        # Treeview
        columns = ('ID', 'Assignment', 'Original Grade', 'Action', 'Status', 'Submitted')
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill='both', expand=True)

        self.my_disputes_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        widths = {'ID': 50, 'Assignment': 200, 'Original Grade': 100, 'Action': 140, 'Status': 100, 'Submitted': 150}
        for col in columns:
            self.my_disputes_tree.heading(col, text=col)
            self.my_disputes_tree.column(col, width=widths.get(col, 120))

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.my_disputes_tree.yview)
        self.my_disputes_tree.configure(yscrollcommand=scrollbar.set)
        self.my_disputes_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Detail panel
        detail_frame = ttk.LabelFrame(parent, text="Dispute Details", padding=10)
        detail_frame.pack(fill='x', pady=(10, 0))
        self.my_dispute_detail_text = scrolledtext.ScrolledText(detail_frame, height=6, state='disabled')
        self.my_dispute_detail_text.pack(fill='x')

        self.my_disputes_tree.bind('<<TreeviewSelect>>', self._on_my_dispute_select)

        # Load data
        student_id = self._get_student_id_safe()
        if not student_id:
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute('''
                SELECT d.id, a.title, d.original_grade, d.requested_action,
                       d.status, d.created_at, d.reason, d.reviewer_comments,
                       d.new_grade, d.resolved_at
                FROM grade_disputes d
                JOIN assignments a ON d.assignment_id = a.id
                WHERE d.student_id = ?
                ORDER BY d.created_at DESC
                ''', (student_id,))

                self._my_disputes_data = {}
                for row in cursor.fetchall():
                    did, atitle, orig, action, status, created, reason, comments, new_g, resolved = row
                    self.my_disputes_tree.insert('', 'end', iid=str(did), values=(
                        did, atitle, orig, action, status, created
                    ))
                    self._my_disputes_data[str(did)] = {
                        'reason': reason,
                        'reviewer_comments': comments,
                        'new_grade': new_g,
                        'resolved_at': resolved,
                    }
            finally:
                conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load disputes: {e}")

    def _on_my_dispute_select(self, _event=None):
        """Show details when a dispute is selected"""
        selection = self.my_disputes_tree.selection()
        if not selection:
            return
        did = selection[0]
        data = self._my_disputes_data.get(did, {})

        self.my_dispute_detail_text.configure(state='normal')
        self.my_dispute_detail_text.delete("1.0", tk.END)
        lines = [
            f"Reason: {data.get('reason', '')}",
            f"Reviewer Comments: {data.get('reviewer_comments') or 'N/A'}",
            f"New Grade: {data.get('new_grade') or 'N/A'}",
            f"Resolved At: {data.get('resolved_at') or 'N/A'}",
        ]
        self.my_dispute_detail_text.insert(tk.END, "\n".join(lines))
        self.my_dispute_detail_text.configure(state='disabled')

    # ------------------------------------------------------------------ #
    #  Instructor: Regrade request queue
    # ------------------------------------------------------------------ #

    def show_regrade_queue(self):
        """Instructor view of all pending regrade requests"""
        if not self._check_permission('manage_assignments'):
            messagebox.showwarning("Access Denied", "You do not have permission to view the regrade queue.")
            return

        self.gui.layout.clear_content_area()
        parent = self.gui.layout.content_area

        title = ttk.Label(parent, text="Regrade Request Queue", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Filter bar
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(filter_frame, text="Status:").pack(side='left', padx=(0, 5))
        self.queue_status_var = tk.StringVar(value='pending')
        status_combo = ttk.Combobox(
            filter_frame, textvariable=self.queue_status_var,
            values=['all'] + self.STATUSES, state='readonly', width=15
        )
        status_combo.pack(side='left', padx=(0, 10))

        ttk.Button(filter_frame, text="Filter", command=self._load_regrade_queue).pack(side='left', padx=5)
        ttk.Button(filter_frame, text="Refresh", command=self._load_regrade_queue).pack(side='left', padx=5)

        # Treeview
        columns = ('ID', 'Student', 'Assignment', 'Original Grade', 'Action', 'Status', 'Submitted')
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill='both', expand=True)

        self.queue_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=18)
        col_widths = {'ID': 50, 'Student': 150, 'Assignment': 200, 'Original Grade': 100,
                      'Action': 140, 'Status': 100, 'Submitted': 150}
        for col in columns:
            self.queue_tree.heading(col, text=col)
            self.queue_tree.column(col, width=col_widths.get(col, 120))

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.queue_tree.yview)
        self.queue_tree.configure(yscrollcommand=scrollbar.set)
        self.queue_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Action buttons
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(btn_frame, text="Review Selected", command=self._review_selected_dispute).pack(side='left', padx=5)

        self._load_regrade_queue()

    def _load_regrade_queue(self):
        """Load disputes into the queue treeview"""
        for item in self.queue_tree.get_children():
            self.queue_tree.delete(item)

        status_filter = self.queue_status_var.get()

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                query = '''
                SELECT d.id, d.student_id, a.title, d.original_grade,
                       d.requested_action, d.status, d.created_at
                FROM grade_disputes d
                JOIN assignments a ON d.assignment_id = a.id
                '''
                params = []
                if status_filter and status_filter != 'all':
                    query += ' WHERE d.status = ?'
                    params.append(status_filter)
                query += ' ORDER BY d.created_at ASC'

                cursor.execute(query, params)
                for row in cursor.fetchall():
                    did, student_id, atitle, orig, action, status, created = row
                    self.queue_tree.insert('', 'end', iid=str(did), values=(
                        did, student_id, atitle, orig, action, status, created
                    ))
            finally:
                conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load regrade queue: {e}")

    def _review_selected_dispute(self):
        """Open review dialog for the selected dispute"""
        selection = self.queue_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a dispute to review.")
            return
        dispute_id = int(selection[0])
        self.review_dispute(dispute_id)

    # ------------------------------------------------------------------ #
    #  Instructor: Review a dispute
    # ------------------------------------------------------------------ #

    def review_dispute(self, dispute_id):
        """Instructor dialog to review a dispute, add comments, approve/deny, adjust grade"""
        if not self._check_permission('manage_assignments'):
            messagebox.showwarning("Access Denied", "You do not have permission to review disputes.")
            return

        # Fetch dispute data
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute('''
                SELECT d.id, d.student_id, a.title, d.original_grade,
                       d.requested_action, d.reason, d.evidence_path,
                       d.status, d.reviewer_comments, d.new_grade
                FROM grade_disputes d
                JOIN assignments a ON d.assignment_id = a.id
                WHERE d.id = ?
                ''', (dispute_id,))
                row = cursor.fetchone()
            finally:
                conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load dispute: {e}")
            return

        if not row:
            messagebox.showerror("Error", "Dispute not found.")
            return

        did, student_id, atitle, orig_grade, action, reason, evidence, status, prev_comments, prev_new = row

        # Build dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Review Dispute #{did}")
        dialog.geometry("550x600")
        dialog.transient(self.root)
        dialog.grab_set()

        main = ttk.Frame(dialog, padding=15)
        main.pack(fill='both', expand=True)

        # Info section
        info_frame = ttk.LabelFrame(main, text="Dispute Information", padding=10)
        info_frame.pack(fill='x', pady=(0, 10))

        labels = [
            ("Dispute ID:", str(did)),
            ("Student:", student_id),
            ("Assignment:", atitle),
            ("Original Grade:", str(orig_grade)),
            ("Requested Action:", action),
            ("Status:", status),
        ]
        for i, (lbl, val) in enumerate(labels):
            ttk.Label(info_frame, text=lbl, font=('TkDefaultFont', 9, 'bold')).grid(
                row=i, column=0, sticky='w', padx=5, pady=2
            )
            ttk.Label(info_frame, text=val).grid(row=i, column=1, sticky='w', padx=5, pady=2)

        # Student reason
        reason_frame = ttk.LabelFrame(main, text="Student Reason", padding=10)
        reason_frame.pack(fill='x', pady=(0, 10))
        reason_text = scrolledtext.ScrolledText(reason_frame, height=4, state='normal')
        reason_text.insert(tk.END, reason or "")
        reason_text.configure(state='disabled')
        reason_text.pack(fill='x')

        # Evidence link
        if evidence:
            ev_frame = ttk.Frame(main)
            ev_frame.pack(fill='x', pady=(0, 10))
            ttk.Label(ev_frame, text="Evidence:").pack(side='left', padx=(0, 5))
            ttk.Label(ev_frame, text=evidence, foreground='blue').pack(side='left')

        # Reviewer section
        review_frame = ttk.LabelFrame(main, text="Review", padding=10)
        review_frame.pack(fill='both', expand=True, pady=(0, 10))

        ttk.Label(review_frame, text="Decision:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        decision_var = tk.StringVar(value=status if status in ('approved', 'denied') else 'under_review')
        decision_combo = ttk.Combobox(
            review_frame, textvariable=decision_var,
            values=['under_review', 'approved', 'denied'], state='readonly', width=20
        )
        decision_combo.grid(row=0, column=1, sticky='w', padx=5, pady=5)

        ttk.Label(review_frame, text="New Grade:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        new_grade_var = tk.StringVar(value=str(prev_new) if prev_new is not None else "")
        new_grade_entry = ttk.Entry(review_frame, textvariable=new_grade_var, width=15)
        new_grade_entry.grid(row=1, column=1, sticky='w', padx=5, pady=5)

        ttk.Label(review_frame, text="Comments:").grid(row=2, column=0, sticky='nw', padx=5, pady=5)
        comments_text = scrolledtext.ScrolledText(review_frame, height=5, width=40)
        comments_text.grid(row=2, column=1, sticky='ew', padx=5, pady=5)
        if prev_comments:
            comments_text.insert(tk.END, prev_comments)

        review_frame.columnconfigure(1, weight=1)

        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill='x')

        def save_review():
            decision = decision_var.get()
            comments = comments_text.get("1.0", tk.END).strip()
            new_grade_str = new_grade_var.get().strip()
            new_grade = None
            if new_grade_str:
                try:
                    new_grade = float(new_grade_str)
                except ValueError:
                    messagebox.showwarning("Validation", "New grade must be a number.")
                    return

            reviewer_id = None
            if self.auth and self.auth.current_user:
                reviewer_id = self.auth.current_user.get('id') or self.auth.current_user.get('username')

            resolved_at = datetime.now().isoformat() if decision in ('approved', 'denied') else None

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                try:
                    cursor = conn.cursor()
                    cursor.execute('''
                    UPDATE grade_disputes
                    SET status = ?, reviewer_id = ?, reviewer_comments = ?,
                        new_grade = ?, resolved_at = ?
                    WHERE id = ?
                    ''', (decision, reviewer_id, comments, new_grade, resolved_at, dispute_id))

                    # If approved and new grade provided, update the submission grade
                    if decision == 'approved' and new_grade is not None:
                        cursor.execute('''
                        UPDATE assignment_submissions SET grade = ?
                        WHERE id = (SELECT submission_id FROM grade_disputes WHERE id = ?)
                        ''', (new_grade, dispute_id))

                    conn.commit()
                    messagebox.showinfo("Success", "Dispute review saved.")
                    dialog.destroy()
                    # Refresh queue if visible
                    if hasattr(self, 'queue_tree'):
                        self._load_regrade_queue()
                finally:
                    conn.close()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save review: {e}")

        def view_related_mc():
            """Open the MC GUI focused on this student so the reviewer can
            see whether a pre-result claim was already lodged for the same
            event — critical context for an appeal decision."""
            try:
                from education_system.university_system.modules.domain.academics.mitigating_circumstances.integration import (
                    open_mc_gui_for_student, claims_for_student,
                )
                claims = claims_for_student(student_id)
                if not claims:
                    messagebox.showinfo("MC", "No MC claims on file for this student.",
                                        parent=dialog)
                    return
                open_mc_gui_for_student(dialog, student_id=student_id)
            except Exception as exc:
                messagebox.showerror("MC", f"Could not open MC GUI: {exc}",
                                     parent=dialog)

        ttk.Button(btn_frame, text="Save Review", command=save_review).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="View related MC claims",
                   command=view_related_mc).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

    # ------------------------------------------------------------------ #
    #  Dispute history with filters
    # ------------------------------------------------------------------ #

    def show_dispute_history(self):
        """Full history of all disputes with filters"""
        if not self._check_permission('manage_assignments'):
            messagebox.showwarning("Access Denied", "You do not have permission to view dispute history.")
            return

        self.gui.layout.clear_content_area()
        parent = self.gui.layout.content_area

        title = ttk.Label(parent, text="Dispute History", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Filters
        filter_frame = ttk.LabelFrame(parent, text="Filters", padding=10)
        filter_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(filter_frame, text="Status:").grid(row=0, column=0, sticky='w', padx=5, pady=3)
        self.hist_status_var = tk.StringVar(value='all')
        ttk.Combobox(
            filter_frame, textvariable=self.hist_status_var,
            values=['all'] + self.STATUSES, state='readonly', width=15
        ).grid(row=0, column=1, sticky='w', padx=5, pady=3)

        ttk.Label(filter_frame, text="Student ID:").grid(row=0, column=2, sticky='w', padx=5, pady=3)
        self.hist_student_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.hist_student_var, width=15).grid(
            row=0, column=3, sticky='w', padx=5, pady=3
        )

        ttk.Label(filter_frame, text="From:").grid(row=1, column=0, sticky='w', padx=5, pady=3)
        self.hist_from_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.hist_from_var, width=15).grid(
            row=1, column=1, sticky='w', padx=5, pady=3
        )
        ttk.Label(filter_frame, text="(YYYY-MM-DD)").grid(row=1, column=2, sticky='w', padx=5, pady=3)

        ttk.Label(filter_frame, text="To:").grid(row=2, column=0, sticky='w', padx=5, pady=3)
        self.hist_to_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.hist_to_var, width=15).grid(
            row=2, column=1, sticky='w', padx=5, pady=3
        )

        ttk.Button(filter_frame, text="Apply Filters", command=self._load_dispute_history).grid(
            row=2, column=3, padx=5, pady=3
        )

        # Treeview
        columns = ('ID', 'Student', 'Assignment', 'Original', 'New', 'Status', 'Submitted', 'Resolved')
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill='both', expand=True)

        self.history_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=16)
        col_widths = {'ID': 50, 'Student': 120, 'Assignment': 180, 'Original': 80,
                      'New': 80, 'Status': 90, 'Submitted': 140, 'Resolved': 140}
        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=col_widths.get(col, 100))

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        self.history_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Double-click to review
        self.history_tree.bind('<Double-1>', lambda e: self._review_from_history())

        self._load_dispute_history()

    def _load_dispute_history(self):
        """Load dispute history with applied filters"""
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        status_filter = self.hist_status_var.get()
        student_filter = self.hist_student_var.get().strip()
        from_date = self.hist_from_var.get().strip()
        to_date = self.hist_to_var.get().strip()

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                query = '''
                SELECT d.id, d.student_id, a.title, d.original_grade,
                       d.new_grade, d.status, d.created_at, d.resolved_at
                FROM grade_disputes d
                JOIN assignments a ON d.assignment_id = a.id
                WHERE 1=1
                '''
                params = []

                if status_filter and status_filter != 'all':
                    query += ' AND d.status = ?'
                    params.append(status_filter)
                if student_filter:
                    query += ' AND d.student_id LIKE ?'
                    params.append(f'%{student_filter}%')
                if from_date:
                    query += ' AND d.created_at >= ?'
                    params.append(from_date)
                if to_date:
                    query += ' AND d.created_at <= ?'
                    params.append(to_date + 'T23:59:59')

                query += ' ORDER BY d.created_at DESC'

                cursor.execute(query, params)
                for row in cursor.fetchall():
                    did, student, atitle, orig, new_g, status, created, resolved = row
                    self.history_tree.insert('', 'end', iid=str(did), values=(
                        did, student, atitle, orig,
                        new_g if new_g is not None else '--',
                        status, created,
                        resolved if resolved else '--'
                    ))
            finally:
                conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load dispute history: {e}")

    def _review_from_history(self):
        """Open review dialog from history treeview"""
        selection = self.history_tree.selection()
        if selection:
            self.review_dispute(int(selection[0]))

    # ------------------------------------------------------------------ #
    #  Dispute analytics
    # ------------------------------------------------------------------ #

    def show_dispute_analytics(self):
        """Stats on disputes: count by status, average resolution time, common reasons"""
        if not self._check_permission('manage_assignments'):
            messagebox.showwarning("Access Denied", "You do not have permission to view analytics.")
            return

        self.gui.layout.clear_content_area()
        parent = self.gui.layout.content_area

        title = ttk.Label(parent, text="Dispute Analytics", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                # Count by status
                cursor.execute('''
                SELECT status, COUNT(*) FROM grade_disputes GROUP BY status
                ''')
                status_counts = dict(cursor.fetchall())

                # Average resolution time (for resolved disputes)
                cursor.execute('''
                SELECT created_at, resolved_at FROM grade_disputes
                WHERE resolved_at IS NOT NULL
                ''')
                resolution_times = []
                for created_str, resolved_str in cursor.fetchall():
                    try:
                        created = datetime.fromisoformat(created_str)
                        resolved = datetime.fromisoformat(resolved_str)
                        delta = (resolved - created).total_seconds() / 3600.0
                        resolution_times.append(delta)
                    except (ValueError, TypeError):
                        pass

                avg_resolution = (
                    sum(resolution_times) / len(resolution_times)
                    if resolution_times else 0
                )

                # Common requested actions
                cursor.execute('''
                SELECT requested_action, COUNT(*) as cnt
                FROM grade_disputes
                GROUP BY requested_action
                ORDER BY cnt DESC
                ''')
                action_counts = cursor.fetchall()

                # Total disputes
                cursor.execute('SELECT COUNT(*) FROM grade_disputes')
                total = cursor.fetchone()[0]

                # Recent disputes (last 30 days)
                cursor.execute('''
                SELECT COUNT(*) FROM grade_disputes
                WHERE created_at >= datetime('now', '-30 days')
                ''')
                recent = cursor.fetchone()[0]

            finally:
                conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load analytics: {e}")
            return

        # Summary cards
        summary_frame = ttk.Frame(parent)
        summary_frame.pack(fill='x', pady=(0, 15))

        cards = [
            ("Total Disputes", str(total)),
            ("Last 30 Days", str(recent)),
            ("Avg Resolution (hrs)", f"{avg_resolution:.1f}"),
            ("Pending", str(status_counts.get('pending', 0))),
            ("Under Review", str(status_counts.get('under_review', 0))),
            ("Approved", str(status_counts.get('approved', 0))),
            ("Denied", str(status_counts.get('denied', 0))),
        ]

        for i, (label, value) in enumerate(cards):
            card = ttk.LabelFrame(summary_frame, text=label, padding=10)
            card.grid(row=i // 4, column=i % 4, padx=8, pady=5, sticky='nsew')
            ttk.Label(card, text=value, font=('TkDefaultFont', 16, 'bold')).pack()

        for c in range(4):
            summary_frame.columnconfigure(c, weight=1)

        # Status breakdown
        breakdown_frame = ttk.LabelFrame(parent, text="Status Breakdown", padding=10)
        breakdown_frame.pack(fill='x', pady=(0, 10))

        status_tree = ttk.Treeview(breakdown_frame, columns=('Status', 'Count'), show='headings', height=4)
        status_tree.heading('Status', text='Status')
        status_tree.heading('Count', text='Count')
        status_tree.column('Status', width=200)
        status_tree.column('Count', width=100)
        for s in self.STATUSES:
            status_tree.insert('', 'end', values=(s.replace('_', ' ').title(), status_counts.get(s, 0)))
        status_tree.pack(fill='x')

        # Common requested actions
        actions_frame = ttk.LabelFrame(parent, text="Common Requested Actions", padding=10)
        actions_frame.pack(fill='x', pady=(0, 10))

        action_tree = ttk.Treeview(actions_frame, columns=('Action', 'Count'), show='headings', height=5)
        action_tree.heading('Action', text='Requested Action')
        action_tree.heading('Count', text='Count')
        action_tree.column('Action', width=250)
        action_tree.column('Count', width=100)
        for action_name, cnt in action_counts:
            action_tree.insert('', 'end', values=(action_name, cnt))
        action_tree.pack(fill='x')

        # Refresh button
        ttk.Button(parent, text="Refresh", command=self.show_dispute_analytics).pack(anchor='w', pady=(10, 0))
