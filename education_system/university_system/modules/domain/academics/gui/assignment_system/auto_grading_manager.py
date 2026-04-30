"""Auto-grading management for MCQ, fill-in-the-blank, and coding questions"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH


class AutoGradingManager:
    """Auto-grading management for MCQ, fill-in-the-blank, and coding questions"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style

    def _check_permission(self, permission):
        """Check if user has permission"""
        try:
            return self.auth.check_permission(permission)
        except (AttributeError, Exception):
            return self.auth.user_role in ['Admin', 'Faculty']

    # ------------------------------------------------------------------ #
    #  Main Dashboard
    # ------------------------------------------------------------------ #

    def show_auto_grading(self):
        """Main auto-grading dashboard"""
        if not self._check_permission('manage_assignments'):
            return

        self.gui.layout.clear_content_area()

        title = ttk.Label(
            self.gui.layout.content_area,
            text="Auto-Grading Dashboard",
            style='Title.TLabel',
        )
        title.pack(anchor='w', pady=(0, 20))

        # --- Action buttons row ---
        btn_frame = ttk.Frame(self.gui.layout.content_area)
        btn_frame.pack(fill='x', pady=(0, 15))

        ttk.Button(
            btn_frame, text="Manage Question Banks",
            command=self.manage_question_banks,
        ).pack(side='left', padx=(0, 10))
        ttk.Button(
            btn_frame, text="Create Question",
            command=self.create_question,
        ).pack(side='left', padx=(0, 10))
        ttk.Button(
            btn_frame, text="Run Auto-Grading",
            command=self.run_auto_grading,
        ).pack(side='left', padx=(0, 10))
        ttk.Button(
            btn_frame, text="Question Bank Stats",
            command=self.show_question_bank_stats,
        ).pack(side='left')

        # --- Pending submissions ---
        pending_frame = ttk.LabelFrame(
            self.gui.layout.content_area, text="Pending Submissions", padding=10,
        )
        pending_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('ID', 'Student', 'Question', 'Type', 'Submitted')
        self.pending_tree = ttk.Treeview(
            pending_frame, columns=columns, show='headings', height=12,
        )
        for col in columns:
            self.pending_tree.heading(col, text=col)
            self.pending_tree.column(col, width=130)

        scroll = ttk.Scrollbar(pending_frame, orient='vertical', command=self.pending_tree.yview)
        self.pending_tree.configure(yscrollcommand=scroll.set)
        self.pending_tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

        self._load_pending_submissions()

        # --- Grade selected ---
        grade_btn_frame = ttk.Frame(self.gui.layout.content_area)
        grade_btn_frame.pack(fill='x', pady=(0, 10))
        ttk.Button(
            grade_btn_frame, text="Auto-Grade Selected",
            command=self._grade_selected_submission,
        ).pack(side='left')
        ttk.Button(
            grade_btn_frame, text="Refresh",
            command=self._load_pending_submissions,
        ).pack(side='left', padx=(10, 0))

    def _load_pending_submissions(self):
        """Load ungraded student answers into the pending tree"""
        if not hasattr(self, 'pending_tree'):
            return
        for item in self.pending_tree.get_children():
            self.pending_tree.delete(item)
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sa.id, sa.student_id, q.question_text, q.question_type, sa.answered_at
                FROM student_answers sa
                JOIN questions q ON sa.question_id = q.id
                WHERE sa.is_correct IS NULL
                ORDER BY sa.answered_at
            ''')
            for row in cursor.fetchall():
                sid, student, text, qtype, answered = row
                display_text = (text[:40] + '...') if len(text) > 40 else text
                self.pending_tree.insert(
                    '', 'end', values=(sid, student, display_text, qtype, answered),
                )
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load pending submissions: {e}")

    def _grade_selected_submission(self):
        """Grade the submission selected in the pending tree"""
        selection = self.pending_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a submission to grade.")
            return

        item = self.pending_tree.item(selection[0])
        submission_id = item['values'][0]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                SELECT q.question_type FROM student_answers sa
                JOIN questions q ON sa.question_id = q.id
                WHERE sa.id = ?
            ''', (submission_id,))
            row = cursor.fetchone()
            conn.close()
            if not row:
                messagebox.showerror("Error", "Submission not found.")
                return

            qtype = row[0]
            if qtype == 'mcq':
                self.auto_grade_mcq(submission_id)
            elif qtype == 'fill_blank':
                self.auto_grade_fill_blank(submission_id)
            elif qtype == 'coding':
                self.auto_grade_coding(submission_id)
            else:
                messagebox.showinfo("Info", f"Unknown question type: {qtype}")

            self._load_pending_submissions()

        except Exception as e:
            messagebox.showerror("Error", f"Grading failed: {e}")

    # ------------------------------------------------------------------ #
    #  Question Bank Management
    # ------------------------------------------------------------------ #

    def manage_question_banks(self):
        """Question bank CRUD interface"""
        if not self._check_permission('manage_assignments'):
            return

        self.gui.layout.clear_content_area()

        title = ttk.Label(
            self.gui.layout.content_area,
            text="Question Banks",
            style='Title.TLabel',
        )
        title.pack(anchor='w', pady=(0, 20))

        # --- Create / Edit form ---
        form_frame = ttk.LabelFrame(
            self.gui.layout.content_area, text="Create / Edit Question Bank", padding=15,
        )
        form_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(form_frame, text="Name:").grid(row=0, column=0, sticky='w', pady=5)
        self.bank_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.bank_name_var, width=40).grid(
            row=0, column=1, sticky='w', pady=5, padx=(10, 0),
        )

        ttk.Label(form_frame, text="Module Code:").grid(row=1, column=0, sticky='w', pady=5)
        self.bank_module_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.bank_module_var, width=20).grid(
            row=1, column=1, sticky='w', pady=5, padx=(10, 0),
        )

        ttk.Label(form_frame, text="Description:").grid(row=2, column=0, sticky='nw', pady=5)
        self.bank_desc_text = scrolledtext.ScrolledText(form_frame, height=3, width=50)
        self.bank_desc_text.grid(row=2, column=1, sticky='ew', pady=5, padx=(10, 0))

        form_frame.grid_columnconfigure(1, weight=1)

        btn_row = ttk.Frame(form_frame)
        btn_row.grid(row=3, column=0, columnspan=2, sticky='e', pady=(10, 0))
        ttk.Button(btn_row, text="Save Bank", command=self._save_question_bank).pack(
            side='left', padx=(0, 10),
        )
        ttk.Button(btn_row, text="Clear", command=self._clear_bank_form).pack(side='left')

        # Hidden var to track editing
        self._editing_bank_id = None

        # --- Existing banks list ---
        list_frame = ttk.LabelFrame(
            self.gui.layout.content_area, text="Existing Question Banks", padding=10,
        )
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('ID', 'Name', 'Module', 'Description', 'Created By', 'Created At')
        self.bank_tree = ttk.Treeview(
            list_frame, columns=columns, show='headings', height=10,
        )
        for col in columns:
            self.bank_tree.heading(col, text=col)
        self.bank_tree.column('ID', width=50)
        self.bank_tree.column('Name', width=180)
        self.bank_tree.column('Module', width=100)
        self.bank_tree.column('Description', width=250)
        self.bank_tree.column('Created By', width=100)
        self.bank_tree.column('Created At', width=140)

        scroll = ttk.Scrollbar(list_frame, orient='vertical', command=self.bank_tree.yview)
        self.bank_tree.configure(yscrollcommand=scroll.set)
        self.bank_tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

        # Action buttons
        action_frame = ttk.Frame(self.gui.layout.content_area)
        action_frame.pack(fill='x')
        ttk.Button(
            action_frame, text="Edit Selected", command=self._edit_selected_bank,
        ).pack(side='left', padx=(0, 10))
        ttk.Button(
            action_frame, text="Delete Selected", command=self._delete_selected_bank,
        ).pack(side='left', padx=(0, 10))
        ttk.Button(
            action_frame, text="Back to Dashboard", command=self.show_auto_grading,
        ).pack(side='right')

        self._load_question_banks()

    def _load_question_banks(self):
        """Reload the question banks tree"""
        for item in self.bank_tree.get_children():
            self.bank_tree.delete(item)
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, module_code, description, created_by, created_at
                FROM question_banks ORDER BY created_at DESC
            ''')
            for row in cursor.fetchall():
                self.bank_tree.insert('', 'end', values=row)
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load question banks: {e}")

    def _save_question_bank(self):
        """Save (create or update) a question bank"""
        name = self.bank_name_var.get().strip()
        module_code = self.bank_module_var.get().strip()
        description = self.bank_desc_text.get('1.0', 'end').strip()

        if not name:
            messagebox.showwarning("Warning", "Bank name is required.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            if self._editing_bank_id:
                cursor.execute('''
                    UPDATE question_banks
                    SET name = ?, module_code = ?, description = ?
                    WHERE id = ?
                ''', (name, module_code, description, self._editing_bank_id))
                msg = "Question bank updated successfully."
            else:
                created_by = getattr(self.auth, 'username', 'system')
                cursor.execute('''
                    INSERT INTO question_banks (name, module_code, description, created_by, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (name, module_code, description, created_by,
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                msg = "Question bank created successfully."

            conn.commit()
            conn.close()
            messagebox.showinfo("Success", msg)
            self._clear_bank_form()
            self._load_question_banks()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save question bank: {e}")

    def _edit_selected_bank(self):
        """Populate form with selected bank for editing"""
        selection = self.bank_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a question bank to edit.")
            return

        values = self.bank_tree.item(selection[0])['values']
        self._editing_bank_id = values[0]
        self.bank_name_var.set(values[1])
        self.bank_module_var.set(values[2] if values[2] else '')
        self.bank_desc_text.delete('1.0', 'end')
        self.bank_desc_text.insert('1.0', values[3] if values[3] else '')

    def _delete_selected_bank(self):
        """Delete the selected question bank"""
        selection = self.bank_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a question bank to delete.")
            return

        bank_id = self.bank_tree.item(selection[0])['values'][0]
        bank_name = self.bank_tree.item(selection[0])['values'][1]

        if not messagebox.askyesno(
            "Confirm Delete",
            f"Delete question bank '{bank_name}' and all its questions?",
        ):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('DELETE FROM questions WHERE bank_id = ?', (bank_id,))
            cursor.execute('DELETE FROM question_banks WHERE id = ?', (bank_id,))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", "Question bank deleted.")
            self._load_question_banks()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete question bank: {e}")

    def _clear_bank_form(self):
        """Reset the bank form fields"""
        self._editing_bank_id = None
        self.bank_name_var.set('')
        self.bank_module_var.set('')
        self.bank_desc_text.delete('1.0', 'end')

    # ------------------------------------------------------------------ #
    #  Create Question
    # ------------------------------------------------------------------ #

    def create_question(self):
        """Form to create MCQ / fill-in-the-blank / coding questions"""
        if not self._check_permission('manage_assignments'):
            return

        self.gui.layout.clear_content_area()

        title = ttk.Label(
            self.gui.layout.content_area,
            text="Create Question",
            style='Title.TLabel',
        )
        title.pack(anchor='w', pady=(0, 20))

        # Scrollable form area
        canvas = tk.Canvas(self.gui.layout.content_area, highlightthickness=0)
        v_scroll = ttk.Scrollbar(self.gui.layout.content_area, orient='vertical', command=canvas.yview)
        form_container = ttk.Frame(canvas)

        form_container.bind(
            '<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all')),
        )
        canvas.create_window((0, 0), window=form_container, anchor='nw')
        canvas.configure(yscrollcommand=v_scroll.set)

        canvas.pack(side='left', fill='both', expand=True)
        v_scroll.pack(side='right', fill='y')

        # --- Basic info ---
        basic_frame = ttk.LabelFrame(form_container, text="Basic Information", padding=15)
        basic_frame.pack(fill='x', pady=(0, 15), padx=5)

        ttk.Label(basic_frame, text="Question Bank:").grid(row=0, column=0, sticky='w', pady=5)
        self.q_bank_var = tk.StringVar()
        self.q_bank_combo = ttk.Combobox(
            basic_frame, textvariable=self.q_bank_var, width=35, state='readonly',
        )
        self.q_bank_combo.grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))
        self._populate_bank_combo()

        ttk.Label(basic_frame, text="Question Type:").grid(row=1, column=0, sticky='w', pady=5)
        self.q_type_var = tk.StringVar(value='mcq')
        type_combo = ttk.Combobox(
            basic_frame, textvariable=self.q_type_var,
            values=['mcq', 'fill_blank', 'coding'],
            width=20, state='readonly',
        )
        type_combo.grid(row=1, column=1, sticky='w', pady=5, padx=(10, 0))
        type_combo.bind('<<ComboboxSelected>>', lambda e: self._toggle_question_fields())

        ttk.Label(basic_frame, text="Topic:").grid(row=2, column=0, sticky='w', pady=5)
        self.q_topic_var = tk.StringVar()
        ttk.Entry(basic_frame, textvariable=self.q_topic_var, width=30).grid(
            row=2, column=1, sticky='w', pady=5, padx=(10, 0),
        )

        ttk.Label(basic_frame, text="Difficulty:").grid(row=3, column=0, sticky='w', pady=5)
        self.q_difficulty_var = tk.StringVar(value='medium')
        ttk.Combobox(
            basic_frame, textvariable=self.q_difficulty_var,
            values=['easy', 'medium', 'hard'],
            width=15, state='readonly',
        ).grid(row=3, column=1, sticky='w', pady=5, padx=(10, 0))

        ttk.Label(basic_frame, text="Points:").grid(row=4, column=0, sticky='w', pady=5)
        self.q_points_var = tk.StringVar(value='10')
        ttk.Entry(basic_frame, textvariable=self.q_points_var, width=10).grid(
            row=4, column=1, sticky='w', pady=5, padx=(10, 0),
        )

        ttk.Label(basic_frame, text="Time Limit (sec):").grid(row=5, column=0, sticky='w', pady=5)
        self.q_time_limit_var = tk.StringVar(value='60')
        ttk.Entry(basic_frame, textvariable=self.q_time_limit_var, width=10).grid(
            row=5, column=1, sticky='w', pady=5, padx=(10, 0),
        )

        basic_frame.grid_columnconfigure(1, weight=1)

        # --- Question text ---
        text_frame = ttk.LabelFrame(form_container, text="Question Text", padding=10)
        text_frame.pack(fill='x', pady=(0, 15), padx=5)
        self.q_text_widget = scrolledtext.ScrolledText(text_frame, height=4, width=70)
        self.q_text_widget.pack(fill='x')

        # --- MCQ options ---
        self.mcq_frame = ttk.LabelFrame(form_container, text="MCQ Options", padding=10)
        self.mcq_frame.pack(fill='x', pady=(0, 15), padx=5)

        self.mcq_option_vars = []
        for i in range(4):
            lbl = chr(65 + i)  # A, B, C, D
            ttk.Label(self.mcq_frame, text=f"Option {lbl}:").grid(
                row=i, column=0, sticky='w', pady=3,
            )
            var = tk.StringVar()
            ttk.Entry(self.mcq_frame, textvariable=var, width=50).grid(
                row=i, column=1, sticky='w', pady=3, padx=(10, 0),
            )
            self.mcq_option_vars.append(var)

        ttk.Label(self.mcq_frame, text="Correct Answer (A/B/C/D):").grid(
            row=4, column=0, sticky='w', pady=5,
        )
        self.mcq_correct_var = tk.StringVar(value='A')
        ttk.Combobox(
            self.mcq_frame, textvariable=self.mcq_correct_var,
            values=['A', 'B', 'C', 'D'], width=5, state='readonly',
        ).grid(row=4, column=1, sticky='w', pady=5, padx=(10, 0))

        self.mcq_frame.grid_columnconfigure(1, weight=1)

        # --- Fill-in-the-blank options ---
        self.fill_frame = ttk.LabelFrame(
            form_container, text="Fill-in-the-Blank Options", padding=10,
        )
        self.fill_frame.pack(fill='x', pady=(0, 15), padx=5)

        ttk.Label(self.fill_frame, text="Acceptable Answers (one per line):").pack(anchor='w')
        self.fill_answers_text = scrolledtext.ScrolledText(self.fill_frame, height=4, width=50)
        self.fill_answers_text.pack(fill='x', pady=(5, 5))

        ttk.Label(self.fill_frame, text="Fuzzy Match Tolerance (0-100):").pack(anchor='w')
        self.fill_tolerance_var = tk.StringVar(value='80')
        ttk.Entry(self.fill_frame, textvariable=self.fill_tolerance_var, width=10).pack(
            anchor='w', pady=(0, 5),
        )

        # --- Coding question options ---
        self.coding_frame = ttk.LabelFrame(
            form_container, text="Coding Question - Test Cases", padding=10,
        )
        self.coding_frame.pack(fill='x', pady=(0, 15), padx=5)

        ttk.Label(
            self.coding_frame,
            text="Test cases (JSON array of {\"input\": ..., \"expected_output\": ...}):",
        ).pack(anchor='w')
        self.coding_tests_text = scrolledtext.ScrolledText(self.coding_frame, height=6, width=70)
        self.coding_tests_text.pack(fill='x', pady=(5, 0))
        self.coding_tests_text.insert('1.0', json.dumps([
            {"input": "", "expected_output": ""}
        ], indent=2))

        # Initially show MCQ fields, hide others
        self._toggle_question_fields()

        # --- Save / back buttons ---
        btn_frame = ttk.Frame(form_container)
        btn_frame.pack(fill='x', pady=(10, 20), padx=5)
        ttk.Button(
            btn_frame, text="Save Question", command=self._save_question,
        ).pack(side='left', padx=(0, 10))
        ttk.Button(
            btn_frame, text="Back to Dashboard", command=self.show_auto_grading,
        ).pack(side='right')

    def _populate_bank_combo(self):
        """Load question bank names into the combo box"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('SELECT id, name FROM question_banks ORDER BY name')
            banks = cursor.fetchall()
            conn.close()
            self._bank_map = {f"{bid} - {name}": bid for bid, name in banks}
            self.q_bank_combo['values'] = list(self._bank_map.keys())
        except Exception:
            self.q_bank_combo['values'] = []
            self._bank_map = {}

    def _toggle_question_fields(self):
        """Show / hide type-specific fields based on selected question type"""
        qtype = self.q_type_var.get()
        if qtype == 'mcq':
            self.mcq_frame.pack(fill='x', pady=(0, 15), padx=5)
            self.fill_frame.pack_forget()
            self.coding_frame.pack_forget()
        elif qtype == 'fill_blank':
            self.mcq_frame.pack_forget()
            self.fill_frame.pack(fill='x', pady=(0, 15), padx=5)
            self.coding_frame.pack_forget()
        elif qtype == 'coding':
            self.mcq_frame.pack_forget()
            self.fill_frame.pack_forget()
            self.coding_frame.pack(fill='x', pady=(0, 15), padx=5)

    def _save_question(self):
        """Persist the question to the database"""
        bank_key = self.q_bank_var.get()
        if not bank_key or bank_key not in self._bank_map:
            messagebox.showwarning("Warning", "Please select a question bank.")
            return

        bank_id = self._bank_map[bank_key]
        qtype = self.q_type_var.get()
        question_text = self.q_text_widget.get('1.0', 'end').strip()

        if not question_text:
            messagebox.showwarning("Warning", "Question text is required.")
            return

        try:
            points = int(self.q_points_var.get())
        except ValueError:
            messagebox.showwarning("Warning", "Points must be a number.")
            return

        try:
            time_limit = int(self.q_time_limit_var.get())
        except ValueError:
            time_limit = 60

        topic = self.q_topic_var.get().strip()
        difficulty = self.q_difficulty_var.get()
        options_json = None
        correct_answer = None
        test_cases_json = None

        if qtype == 'mcq':
            options = {chr(65 + i): v.get().strip() for i, v in enumerate(self.mcq_option_vars)}
            if not all(options.values()):
                messagebox.showwarning("Warning", "All MCQ options are required.")
                return
            options_json = json.dumps(options)
            correct_answer = self.mcq_correct_var.get()

        elif qtype == 'fill_blank':
            raw = self.fill_answers_text.get('1.0', 'end').strip()
            answers = [a.strip() for a in raw.splitlines() if a.strip()]
            if not answers:
                messagebox.showwarning("Warning", "At least one acceptable answer is required.")
                return
            tolerance = self.fill_tolerance_var.get().strip()
            correct_answer = json.dumps({
                "answers": answers,
                "tolerance": int(tolerance) if tolerance.isdigit() else 80,
            })

        elif qtype == 'coding':
            raw_tests = self.coding_tests_text.get('1.0', 'end').strip()
            try:
                test_cases = json.loads(raw_tests)
                if not isinstance(test_cases, list):
                    raise ValueError("Must be a JSON array")
                test_cases_json = json.dumps(test_cases)
            except (json.JSONDecodeError, ValueError) as exc:
                messagebox.showerror("Error", f"Invalid test cases JSON: {exc}")
                return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO questions
                    (bank_id, question_type, question_text, options_json,
                     correct_answer, points, difficulty, topic,
                     time_limit_seconds, test_cases_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                bank_id, qtype, question_text, options_json,
                correct_answer, points, difficulty, topic,
                time_limit, test_cases_json,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            ))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", "Question saved successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save question: {e}")

    # ------------------------------------------------------------------ #
    #  Auto-Grading: MCQ
    # ------------------------------------------------------------------ #

    def auto_grade_mcq(self, submission_id):
        """Auto-grade a single MCQ submission"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
                SELECT sa.id, sa.answer_text, q.correct_answer, q.points
                FROM student_answers sa
                JOIN questions q ON sa.question_id = q.id
                WHERE sa.id = ? AND q.question_type = 'mcq'
            ''', (submission_id,))
            row = cursor.fetchone()

            if not row:
                conn.close()
                messagebox.showwarning("Warning", "MCQ submission not found.")
                return

            sa_id, student_answer, correct_answer, points = row
            student_answer = (student_answer or '').strip().upper()
            correct_answer = (correct_answer or '').strip().upper()

            is_correct = 1 if student_answer == correct_answer else 0
            points_earned = points if is_correct else 0

            cursor.execute('''
                UPDATE student_answers
                SET is_correct = ?, points_earned = ?
                WHERE id = ?
            ''', (is_correct, points_earned, sa_id))

            conn.commit()
            conn.close()

            result = "Correct" if is_correct else "Incorrect"
            messagebox.showinfo(
                "Graded", f"Submission {sa_id}: {result} ({points_earned}/{points} points)",
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to grade MCQ: {e}")

    # ------------------------------------------------------------------ #
    #  Auto-Grading: Fill-in-the-Blank
    # ------------------------------------------------------------------ #

    def auto_grade_fill_blank(self, submission_id):
        """Auto-grade a fill-in-the-blank submission using fuzzy matching"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
                SELECT sa.id, sa.answer_text, q.correct_answer, q.points
                FROM student_answers sa
                JOIN questions q ON sa.question_id = q.id
                WHERE sa.id = ? AND q.question_type = 'fill_blank'
            ''', (submission_id,))
            row = cursor.fetchone()

            if not row:
                conn.close()
                messagebox.showwarning("Warning", "Fill-in-the-blank submission not found.")
                return

            sa_id, student_answer, correct_json, points = row
            student_answer = (student_answer or '').strip().lower()

            answer_data = json.loads(correct_json)
            acceptable = [a.lower() for a in answer_data.get('answers', [])]
            tolerance = answer_data.get('tolerance', 80)

            is_correct = 0
            for accepted in acceptable:
                similarity = self._similarity_ratio(student_answer, accepted)
                if similarity >= tolerance:
                    is_correct = 1
                    break

            points_earned = points if is_correct else 0

            cursor.execute('''
                UPDATE student_answers
                SET is_correct = ?, points_earned = ?
                WHERE id = ?
            ''', (is_correct, points_earned, sa_id))

            conn.commit()
            conn.close()

            result = "Correct" if is_correct else "Incorrect"
            messagebox.showinfo(
                "Graded", f"Submission {sa_id}: {result} ({points_earned}/{points} points)",
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to grade fill-in-the-blank: {e}")

    @staticmethod
    def _similarity_ratio(a, b):
        """Compute similarity between two strings as a percentage (0-100).

        Uses a simple longest-common-subsequence approach so we avoid
        external dependencies while still providing fuzzy matching.
        """
        if a == b:
            return 100
        if not a or not b:
            return 0

        len_a, len_b = len(a), len(b)
        # Build LCS length table (space-optimised to two rows)
        prev = [0] * (len_b + 1)
        for i in range(1, len_a + 1):
            curr = [0] * (len_b + 1)
            for j in range(1, len_b + 1):
                if a[i - 1] == b[j - 1]:
                    curr[j] = prev[j - 1] + 1
                else:
                    curr[j] = max(prev[j], curr[j - 1])
            prev = curr

        lcs_len = prev[len_b]
        return int((2.0 * lcs_len / (len_a + len_b)) * 100)

    # ------------------------------------------------------------------ #
    #  Auto-Grading: Coding
    # ------------------------------------------------------------------ #

    def auto_grade_coding(self, submission_id):
        """Auto-grade a coding submission by running test cases in a sandbox"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
                SELECT sa.id, sa.answer_text, q.test_cases_json, q.points
                FROM student_answers sa
                JOIN questions q ON sa.question_id = q.id
                WHERE sa.id = ? AND q.question_type = 'coding'
            ''', (submission_id,))
            row = cursor.fetchone()

            if not row:
                conn.close()
                messagebox.showwarning("Warning", "Coding submission not found.")
                return

            sa_id, student_code, test_cases_json, total_points = row
            test_cases = json.loads(test_cases_json) if test_cases_json else []

            if not test_cases:
                conn.close()
                messagebox.showinfo("Info", "No test cases defined for this question.")
                return

            passed = 0
            results = []
            for i, tc in enumerate(test_cases):
                tc_input = tc.get('input', '')
                expected = str(tc.get('expected_output', '')).strip()
                actual, error = self._run_code_sandbox(student_code, tc_input)

                if error:
                    results.append(f"Test {i + 1}: ERROR - {error}")
                elif actual.strip() == expected:
                    passed += 1
                    results.append(f"Test {i + 1}: PASS")
                else:
                    results.append(
                        f"Test {i + 1}: FAIL (expected '{expected}', got '{actual.strip()}')"
                    )

            fraction = passed / len(test_cases) if test_cases else 0
            points_earned = round(total_points * fraction)
            is_correct = 1 if passed == len(test_cases) else 0

            cursor.execute('''
                UPDATE student_answers
                SET is_correct = ?, points_earned = ?
                WHERE id = ?
            ''', (is_correct, points_earned, sa_id))

            conn.commit()
            conn.close()

            detail = "\n".join(results)
            messagebox.showinfo(
                "Graded",
                f"Submission {sa_id}: {passed}/{len(test_cases)} tests passed\n"
                f"Points: {points_earned}/{total_points}\n\n{detail}",
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to grade coding submission: {e}")

    @staticmethod
    def _run_code_sandbox(code, stdin_input):
        """Execute student code in a restricted subprocess and capture output.

        Returns (stdout, error_message).  The process is killed after 10
        seconds to prevent infinite loops.
        """
        import subprocess
        import tempfile
        import os

        try:
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.py', delete=False,
            ) as tmp:
                tmp.write(code or '')
                tmp_path = tmp.name

            result = subprocess.run(
                ['python3', tmp_path],
                input=stdin_input,
                capture_output=True,
                text=True,
                timeout=10,
            )

            os.unlink(tmp_path)

            if result.returncode != 0:
                return '', result.stderr.strip()
            return result.stdout, ''

        except subprocess.TimeoutExpired:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            return '', 'Execution timed out (10s limit)'
        except Exception as exc:
            return '', str(exc)

    # ------------------------------------------------------------------ #
    #  Batch Auto-Grading
    # ------------------------------------------------------------------ #

    def run_auto_grading(self):
        """Batch auto-grade all pending submissions"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sa.id, q.question_type
                FROM student_answers sa
                JOIN questions q ON sa.question_id = q.id
                WHERE sa.is_correct IS NULL
            ''')
            pending = cursor.fetchall()
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch pending submissions: {e}")
            return

        if not pending:
            messagebox.showinfo("Info", "No pending submissions to grade.")
            return

        graded = 0
        errors = 0
        for sa_id, qtype in pending:
            try:
                if qtype == 'mcq':
                    self.auto_grade_mcq(sa_id)
                elif qtype == 'fill_blank':
                    self.auto_grade_fill_blank(sa_id)
                elif qtype == 'coding':
                    self.auto_grade_coding(sa_id)
                else:
                    continue
                graded += 1
            except Exception:
                errors += 1

        # Closed-loop write-back: every distinct (student, module) we just
        # auto-graded gets marked 'attended' on any exam scheduled for that
        # module today. Mirrors the manual exam-invigilation path so a
        # computer-marked test counts toward attendance/eligibility.
        try:
            self._writeback_exam_attendance(pending)
        except Exception as wb_err:
            print(f"Warning: exam attendance write-back failed: {wb_err}")

        messagebox.showinfo(
            "Batch Grading Complete",
            f"Graded: {graded}\nErrors: {errors}\nTotal pending: {len(pending)}",
        )

        # Refresh dashboard if visible
        if hasattr(self, 'pending_tree'):
            self._load_pending_submissions()

    def _writeback_exam_attendance(self, pending_rows):
        """Mark each just-graded student 'attended' on today's matching exam.

        ``pending_rows`` is the list of ``(student_answer_id, qtype)`` we
        iterated in ``run_auto_grading``. Walk back through them to learn
        each (student_id, module_code) pair, then look up exams scheduled
        for that module on today's date and call the canonical writer.
        """
        if not pending_rows:
            return
        from datetime import date
        from education_system.university_system.modules.domain.academics.gui._exam_attendance_writer import (
            record_exam_attendance,
        )
        from education_system.university_system.modules.domain.academics.gui._event_bus import (
            publish, EVENT_EXAM_CHANGED,
        )

        today = date.today().strftime('%Y-%m-%d')
        sa_ids = [row[0] for row in pending_rows]
        if not sa_ids:
            return

        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        try:
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(sa_ids))
            # Map answer-id → (student_id, module_code) via the question's bank.
            cursor.execute(
                f"""
                SELECT DISTINCT sa.student_id, qb.module_code
                FROM student_answers sa
                JOIN questions q       ON sa.question_id = q.id
                JOIN question_banks qb ON q.bank_id = qb.id
                WHERE sa.id IN ({placeholders})
                  AND sa.student_id IS NOT NULL
                  AND qb.module_code IS NOT NULL
                """,
                sa_ids,
            )
            pairs = cursor.fetchall()

            written = 0
            for student_id, module_code in pairs:
                cursor.execute(
                    "SELECT id FROM exams WHERE module_code = ? AND date = ? "
                    "ORDER BY start_time LIMIT 1",
                    (module_code, today),
                )
                exam_row = cursor.fetchone()
                if not exam_row:
                    continue
                exam_id = exam_row[0]
                if record_exam_attendance(
                    exam_id, student_id, status='attended',
                    module_code=module_code, exam_date=today,
                    recorded_by='auto_grader',
                    notes='Marked attended via auto-grading completion.',
                ):
                    written += 1
                    publish(
                        EVENT_EXAM_CHANGED,
                        exam_id=exam_id, module_code=module_code,
                        student_id=student_id, source='auto_grading',
                    )
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    #  Question Bank Stats
    # ------------------------------------------------------------------ #

    def show_question_bank_stats(self):
        """Per-question difficulty stats: how many got it wrong, average time spent"""
        if not self._check_permission('manage_assignments'):
            return

        self.gui.layout.clear_content_area()

        title = ttk.Label(
            self.gui.layout.content_area,
            text="Question Bank Statistics",
            style='Title.TLabel',
        )
        title.pack(anchor='w', pady=(0, 20))

        # --- Bank selector ---
        sel_frame = ttk.Frame(self.gui.layout.content_area)
        sel_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(sel_frame, text="Question Bank:").pack(side='left')
        self.stats_bank_var = tk.StringVar()
        self.stats_bank_combo = ttk.Combobox(
            sel_frame, textvariable=self.stats_bank_var, width=35, state='readonly',
        )
        self.stats_bank_combo.pack(side='left', padx=(10, 10))

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('SELECT id, name FROM question_banks ORDER BY name')
            banks = cursor.fetchall()
            conn.close()
            self._stats_bank_map = {f"{bid} - {name}": bid for bid, name in banks}
            self.stats_bank_combo['values'] = list(self._stats_bank_map.keys())
        except Exception:
            self._stats_bank_map = {}

        ttk.Button(sel_frame, text="Load Stats", command=self._load_stats).pack(side='left')

        # --- Stats tree ---
        stats_frame = ttk.LabelFrame(
            self.gui.layout.content_area, text="Per-Question Statistics", padding=10,
        )
        stats_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = (
            'ID', 'Question', 'Type', 'Difficulty', 'Total Attempts',
            'Correct', 'Incorrect', '% Wrong', 'Avg Time (s)',
        )
        self.stats_tree = ttk.Treeview(
            stats_frame, columns=columns, show='headings', height=15,
        )
        for col in columns:
            self.stats_tree.heading(col, text=col)
        self.stats_tree.column('ID', width=40)
        self.stats_tree.column('Question', width=220)
        self.stats_tree.column('Type', width=80)
        self.stats_tree.column('Difficulty', width=80)
        self.stats_tree.column('Total Attempts', width=100)
        self.stats_tree.column('Correct', width=70)
        self.stats_tree.column('Incorrect', width=70)
        self.stats_tree.column('% Wrong', width=70)
        self.stats_tree.column('Avg Time (s)', width=90)

        scroll = ttk.Scrollbar(stats_frame, orient='vertical', command=self.stats_tree.yview)
        self.stats_tree.configure(yscrollcommand=scroll.set)
        self.stats_tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

        # --- Summary ---
        self.stats_summary_var = tk.StringVar(value="Select a bank and click Load Stats.")
        ttk.Label(
            self.gui.layout.content_area,
            textvariable=self.stats_summary_var,
        ).pack(anchor='w', pady=(0, 10))

        # Back button
        ttk.Button(
            self.gui.layout.content_area, text="Back to Dashboard",
            command=self.show_auto_grading,
        ).pack(anchor='w')

    def _load_stats(self):
        """Populate the stats tree for the selected question bank"""
        bank_key = self.stats_bank_var.get()
        if not bank_key or bank_key not in self._stats_bank_map:
            messagebox.showwarning("Warning", "Please select a question bank.")
            return

        bank_id = self._stats_bank_map[bank_key]

        for item in self.stats_tree.get_children():
            self.stats_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
                SELECT
                    q.id,
                    q.question_text,
                    q.question_type,
                    q.difficulty,
                    COUNT(sa.id) AS total,
                    SUM(CASE WHEN sa.is_correct = 1 THEN 1 ELSE 0 END) AS correct,
                    SUM(CASE WHEN sa.is_correct = 0 THEN 1 ELSE 0 END) AS incorrect,
                    AVG(sa.time_spent_seconds) AS avg_time
                FROM questions q
                LEFT JOIN student_answers sa ON sa.question_id = q.id
                WHERE q.bank_id = ?
                GROUP BY q.id
                ORDER BY q.id
            ''', (bank_id,))

            rows = cursor.fetchall()
            conn.close()

            total_questions = len(rows)
            total_attempts = 0
            total_wrong = 0

            for row in rows:
                qid, text, qtype, diff, attempts, correct, incorrect, avg_time = row
                attempts = attempts or 0
                correct = correct or 0
                incorrect = incorrect or 0
                avg_time = round(avg_time, 1) if avg_time else 0

                pct_wrong = round((incorrect / attempts * 100), 1) if attempts > 0 else 0
                display_text = (text[:50] + '...') if len(text) > 50 else text

                self.stats_tree.insert('', 'end', values=(
                    qid, display_text, qtype, diff,
                    attempts, correct, incorrect, f"{pct_wrong}%", avg_time,
                ))

                total_attempts += attempts
                total_wrong += incorrect

            overall_pct = (
                round(total_wrong / total_attempts * 100, 1) if total_attempts > 0 else 0
            )
            self.stats_summary_var.set(
                f"Questions: {total_questions} | "
                f"Total attempts: {total_attempts} | "
                f"Overall % wrong: {overall_pct}%"
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load statistics: {e}")
