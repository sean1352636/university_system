"""Group assignment creation GUI and logic"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH


class AssignmentCreationMixin:
    """Mixin for group assignment creation functionality"""

    def show_create_group_assignment(self):
        """Show enhanced group assignment creation"""
        if not self._check_permission('manage_assignments'):
            return

        self.gui.layout.clear_content_area()

        title = ttk.Label(self.gui.layout.content_area, text="Create Group Assignment", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Create scrollable frame
        canvas = tk.Canvas(self.gui.layout.content_area)
        scrollbar = ttk.Scrollbar(self.gui.layout.content_area, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Basic assignment details
        basic_frame = ttk.LabelFrame(scrollable_frame, text="Basic Assignment Details", padding=20)
        basic_frame.pack(fill='x', padx=10, pady=10)

        # Module selection
        ttk.Label(basic_frame, text="Module:").grid(row=0, column=0, sticky='w', pady=5)
        self.group_module_var = tk.StringVar()
        module_combo = ttk.Combobox(basic_frame, textvariable=self.group_module_var, width=30)
        module_combo.grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))
        self.load_modules(module_combo)

        # Title
        ttk.Label(basic_frame, text="Title:").grid(row=1, column=0, sticky='w', pady=5)
        self.group_title_var = tk.StringVar()
        ttk.Entry(basic_frame, textvariable=self.group_title_var, width=50).grid(row=1, column=1, sticky='ew', pady=5, padx=(10, 0))

        # Description
        ttk.Label(basic_frame, text="Description:").grid(row=2, column=0, sticky='nw', pady=5)
        self.group_description_text = scrolledtext.ScrolledText(basic_frame, height=4, width=50)
        self.group_description_text.grid(row=2, column=1, sticky='ew', pady=5, padx=(10, 0))

        # Due date
        ttk.Label(basic_frame, text="Due Date:").grid(row=3, column=0, sticky='w', pady=5)
        due_frame = ttk.Frame(basic_frame)
        due_frame.grid(row=3, column=1, sticky='w', pady=5, padx=(10, 0))

        self.group_due_date_var = tk.StringVar()
        self.group_due_time_var = tk.StringVar(value="23:59")

        ttk.Entry(due_frame, textvariable=self.group_due_date_var, width=12).pack(side='left')
        ttk.Label(due_frame, text="Time:").pack(side='left', padx=(10, 5))
        ttk.Combobox(due_frame, textvariable=self.group_due_time_var, width=8,
                    values=["08:00", "12:00", "17:00", "23:59"]).pack(side='left')

        # Group settings frame
        group_frame = ttk.LabelFrame(scrollable_frame, text="Group Settings", padding=20)
        group_frame.pack(fill='x', padx=10, pady=10)

        # Group size
        ttk.Label(group_frame, text="Group Size:").grid(row=0, column=0, sticky='w', pady=5)
        size_frame = ttk.Frame(group_frame)
        size_frame.grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))

        ttk.Label(size_frame, text="Min:").pack(side='left')
        self.group_min_var = tk.StringVar(value="2")
        ttk.Entry(size_frame, textvariable=self.group_min_var, width=5).pack(side='left', padx=5)

        ttk.Label(size_frame, text="Max:").pack(side='left', padx=(10, 0))
        self.group_max_var = tk.StringVar(value="4")
        ttk.Entry(size_frame, textvariable=self.group_max_var, width=5).pack(side='left', padx=5)

        # Group formation method
        ttk.Label(group_frame, text="Group Formation:").grid(row=1, column=0, sticky='w', pady=5)
        self.group_formation_var = tk.StringVar(value="self_select")

        formation_frame = ttk.Frame(group_frame)
        formation_frame.grid(row=1, column=1, sticky='w', pady=5, padx=(10, 0))

        ttk.Radiobutton(formation_frame, text="Students self-select",
                       variable=self.group_formation_var, value="self_select").pack(anchor='w')
        ttk.Radiobutton(formation_frame, text="Instructor assigns",
                       variable=self.group_formation_var, value="instructor_assign").pack(anchor='w')
        ttk.Radiobutton(formation_frame, text="Random assignment",
                       variable=self.group_formation_var, value="random").pack(anchor='w')

        # Collaboration settings
        collab_frame = ttk.LabelFrame(group_frame, text="Collaboration Settings", padding=10)
        collab_frame.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(20, 0))

        self.allow_member_removal_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(collab_frame, text="Allow groups to remove members",
                       variable=self.allow_member_removal_var).pack(anchor='w')

        self.require_peer_eval_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(collab_frame, text="Require peer evaluation",
                       variable=self.require_peer_eval_var).pack(anchor='w')

        self.individual_grades_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(collab_frame, text="Allow individual grades within group",
                       variable=self.individual_grades_var).pack(anchor='w')

        # Submission settings
        submission_frame = ttk.LabelFrame(scrollable_frame, text="Submission Settings", padding=20)
        submission_frame.pack(fill='x', padx=10, pady=10)

        # Max marks
        ttk.Label(submission_frame, text="Max Marks:").grid(row=0, column=0, sticky='w', pady=5)
        self.group_max_marks_var = tk.StringVar(value="100")
        ttk.Entry(submission_frame, textvariable=self.group_max_marks_var, width=10).grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))

        # File settings
        ttk.Label(submission_frame, text="Allowed File Types:").grid(row=1, column=0, sticky='w', pady=5)
        self.group_file_types_var = tk.StringVar(value=".pdf,.docx,.zip")
        ttk.Entry(submission_frame, textvariable=self.group_file_types_var, width=30).grid(row=1, column=1, sticky='w', pady=5, padx=(10, 0))

        ttk.Label(submission_frame, text="Max File Size (MB):").grid(row=2, column=0, sticky='w', pady=5)
        self.group_max_size_var = tk.StringVar(value="50")
        ttk.Entry(submission_frame, textvariable=self.group_max_size_var, width=10).grid(row=2, column=1, sticky='w', pady=5, padx=(10, 0))

        # Submission method
        ttk.Label(submission_frame, text="Submission Method:").grid(row=3, column=0, sticky='w', pady=5)
        self.submission_method_var = tk.StringVar(value="one_per_group")

        method_frame = ttk.Frame(submission_frame)
        method_frame.grid(row=3, column=1, sticky='w', pady=5, padx=(10, 0))

        ttk.Radiobutton(method_frame, text="One submission per group",
                       variable=self.submission_method_var, value="one_per_group").pack(anchor='w')
        ttk.Radiobutton(method_frame, text="All members must submit",
                       variable=self.submission_method_var, value="all_submit").pack(anchor='w')

        # Instructions
        instructions_frame = ttk.LabelFrame(scrollable_frame, text="Instructions", padding=20)
        instructions_frame.pack(fill='x', padx=10, pady=10)

        self.group_instructions_text = scrolledtext.ScrolledText(instructions_frame, height=6, width=70)
        self.group_instructions_text.pack(fill='both', expand=True)

        # Default group assignment instructions
        default_instructions = "Group Assignment Instructions: Please work in groups as assigned."
        self.group_instructions_text.insert(tk.END, default_instructions)

        # Action buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill='x', padx=10, pady=20)

        ttk.Button(button_frame, text="Save Group Assignment",
                  command=self.create_group_assignment_gui,
                  style='Accent.TButton').pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Group Configuration",
                  command=self.show_group_configuration).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Clear Form",
                  command=self.clear_group_assignment_form).pack(side='left')

        # Pack the canvas and scrollbar
        canvas.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        scrollbar.pack(side='right', fill='y', pady=10)

    def create_group_assignment_gui(self):
        """Create group assignment through GUI"""
        try:
            # Validate form
            if not self.group_module_var.get() or not self.group_title_var.get():
                messagebox.showerror("Error", "Module and title are required")
                return

            if not self.group_due_date_var.get():
                messagebox.showerror("Error", "Due date is required")
                return

            # Validate group size
            try:
                min_size = int(self.group_min_var.get())
                max_size = int(self.group_max_var.get())
                if min_size < 1 or max_size < min_size:
                    messagebox.showerror("Error", "Invalid group size")
                    return
            except ValueError:
                messagebox.showerror("Error", "Group size must be numbers")
                return

            # Get module code
            module_code = self.module_map.get(self.group_module_var.get())

            # Parse due date
            due_date_str = f"{self.group_due_date_var.get()} {self.group_due_time_var.get()}"
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M")

            # Create assignment
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Temporarily disable foreign key checks to avoid module_code issues
            cursor.execute("PRAGMA foreign_keys = OFF")

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT INTO assignments
            (module_code, title, description, instructions, due_date, max_marks,
             file_types_allowed, max_file_size_mb, assignment_type, group_size_min, group_size_max,
             created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                module_code,
                self.group_title_var.get().strip(),
                self.group_description_text.get(1.0, tk.END).strip(),
                self.group_instructions_text.get(1.0, tk.END).strip(),
                due_date.strftime('%Y-%m-%d %H:%M:%S'),
                int(self.group_max_marks_var.get()),
                self.group_file_types_var.get().strip(),
                int(self.group_max_size_var.get()),
                'group',
                min_size,
                max_size,
                self.auth.current_user['id'],
                timestamp,
                timestamp
            ))

            assignment_id = cursor.lastrowid

            # Handle group formation if instructor assigns or random
            formation_method = self.group_formation_var.get()
            if formation_method in ['instructor_assign', 'random']:
                self.create_initial_groups(cursor, assignment_id, module_code, formation_method, min_size, max_size)

            # Re-enable foreign key checks
            cursor.execute("PRAGMA foreign_keys = ON")

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Group assignment '{self.group_title_var.get()}' created successfully!")
            self.clear_group_assignment_form()

        except ValueError as e:
            messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create group assignment: {e}")


    def create_initial_groups(self, cursor, assignment_id, module_code, method, min_size, max_size):
        """Create initial groups for assignment"""
        try:
            # Get students in module
            cursor.execute('''
            SELECT student_id FROM student_modules WHERE module_code = ?
            ''', (module_code,))

            students = [row[0] for row in cursor.fetchall()]

            if len(students) < min_size:
                messagebox.showwarning("Warning", f"Not enough students ({len(students)}) to form groups of minimum size {min_size}")
                return

            if method == 'random':
                import random
                random.shuffle(students)

            # Create groups
            group_number = 1
            i = 0

            while i < len(students):
                remaining_students = len(students) - i

                # Determine group size
                if remaining_students <= max_size:
                    group_size = remaining_students
                elif remaining_students < min_size + max_size:
                    # Adjust to avoid leaving too few students
                    group_size = remaining_students // 2
                else:
                    group_size = max_size

                if group_size < min_size:
                    break

                # Create group
                group_name = f"Group {group_number}"
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO groups (assignment_id, group_name, created_at, created_by)
                VALUES (?, ?, ?, ?)
                ''', (assignment_id, group_name, timestamp, 'system'))

                group_id = cursor.lastrowid

                # Add students to group
                for j in range(group_size):
                    if i + j < len(students):
                        student_id = students[i + j]
                        role = 'leader' if j == 0 else 'member'

                        cursor.execute('''
                        INSERT INTO group_members (group_id, student_id, role, joined_at)
                        VALUES (?, ?, ?, ?)
                        ''', (group_id, student_id, role, timestamp))

                i += group_size
                group_number += 1

            messagebox.showinfo("Groups Created", f"Created {group_number - 1} groups with {method} method")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create initial groups: {e}")


    def clear_group_assignment_form(self):
        """Clear group assignment form"""
        self.group_module_var.set('')
        self.group_title_var.set('')
        self.group_description_text.delete(1.0, tk.END)
        self.group_due_date_var.set('')
        self.group_due_time_var.set('23:59')
        self.group_min_var.set('2')
        self.group_max_var.set('4')
        self.group_formation_var.set('self_select')
        self.group_max_marks_var.set('100')
        self.group_file_types_var.set('.pdf,.docx,.zip')
        self.group_max_size_var.set('50')
        self.submission_method_var.set('one_per_group')
        self.allow_member_removal_var.set(False)
        self.require_peer_eval_var.set(True)
        self.individual_grades_var.set(False)
        # Reset instructions to default
        self.group_instructions_text.delete(1.0, tk.END)
        self.group_instructions_text.insert(tk.END, "Group Assignment Instructions: Please work in groups as assigned.")
