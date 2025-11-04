"""
Course Evaluation System GUI

Full-featured GUI for managing course evaluations, templates, responses,
and viewing results analytics.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional

from university_system.infrastructure.auth.user_authentication import UserAuth
from university_system.modules.domain.academics.services.evaluation.course_evaluation_core import (
    EvaluationTemplateManager,
    CourseEvaluationManager,
    ResponseManager,
    ResultsAnalyticsManager
)
from university_system.modules.domain.academics.services.evaluation.db_schema import initialize_evaluation_database
from university_system.infrastructure.database.db import get_connection
from university_system.modules.shared.utils.activity_logger import log_activity


class CourseEvaluationGUI:
    """Main GUI for Course Evaluation System"""

    def __init__(self, parent, auth: UserAuth):
        self.root = tk.Toplevel(parent)
        self.root.title("Course Evaluation System")
        self.root.geometry("1200x700")
        self.auth = auth

        # Initialize database
        try:
            initialize_evaluation_database()
        except Exception as e:
            print(f"Database initialization warning: {e}")

        self.create_widgets()
        self.load_evaluations()

    def create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title = ttk.Label(main_frame, text="Course Evaluation System",
                         font=('Arial', 16, 'bold'))
        title.pack(pady=10)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self.create_templates_tab()
        self.create_evaluations_tab()
        self.create_responses_tab()
        self.create_results_tab()

    def create_templates_tab(self):
        """Create Evaluation Templates management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Evaluation Templates")

        # Top frame for buttons
        button_frame = ttk.Frame(tab)
        button_frame.pack(fill=tk.X, pady=5)

        ttk.Button(button_frame, text="Create Template",
                  command=self.create_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Add Questions",
                  command=self.add_questions).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh",
                  command=self.load_templates).pack(side=tk.LEFT, padx=5)

        # Templates list
        list_frame = ttk.LabelFrame(tab, text="Evaluation Templates", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Treeview for templates
        columns = ('ID', 'Name', 'Type', 'Description', 'Created By', 'Created Date')
        self.templates_tree = ttk.Treeview(list_frame, columns=columns, show='headings',
                                          height=15)

        for col in columns:
            self.templates_tree.heading(col, text=col)
            width = 150 if col == 'Description' else 100
            self.templates_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                 command=self.templates_tree.yview)
        self.templates_tree.configure(yscrollcommand=scrollbar.set)

        self.templates_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_evaluations_tab(self):
        """Create Course Evaluations tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Course Evaluations")

        # Top frame for buttons
        button_frame = ttk.Frame(tab)
        button_frame.pack(fill=tk.X, pady=5)

        ttk.Button(button_frame, text="Launch Evaluation",
                  command=self.launch_evaluation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="View Details",
                  command=self.view_evaluation_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh",
                  command=self.load_evaluations).pack(side=tk.LEFT, padx=5)

        # Evaluations list
        list_frame = ttk.LabelFrame(tab, text="Active Evaluations", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ('ID', 'Module', 'Year', 'Semester', 'Instructor',
                  'Start Date', 'End Date', 'Responses')
        self.evaluations_tree = ttk.Treeview(list_frame, columns=columns,
                                            show='headings', height=15)

        for col in columns:
            self.evaluations_tree.heading(col, text=col)
            self.evaluations_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                 command=self.evaluations_tree.yview)
        self.evaluations_tree.configure(yscrollcommand=scrollbar.set)

        self.evaluations_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_responses_tab(self):
        """Create Student Responses tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Submit Response")

        ttk.Label(tab, text="Submit Course Evaluation Response",
                 font=('Arial', 12, 'bold')).pack(pady=10)

        # Evaluation selection
        select_frame = ttk.LabelFrame(tab, text="Select Evaluation", padding="10")
        select_frame.pack(fill=tk.X, pady=5)

        ttk.Label(select_frame, text="Evaluation:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.response_eval_combo = ttk.Combobox(select_frame, width=50, state='readonly')
        self.response_eval_combo.grid(row=0, column=1, padx=5, pady=5)
        self.response_eval_combo.bind('<<ComboboxSelected>>', self.load_evaluation_questions)

        ttk.Button(select_frame, text="Load Questions",
                  command=self.load_evaluation_questions).grid(row=0, column=2, padx=5)

        # Questions frame
        self.questions_frame = ttk.LabelFrame(tab, text="Questions", padding="10")
        self.questions_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Submit button
        ttk.Button(tab, text="Submit Evaluation",
                  command=self.submit_response).pack(pady=10)

    def create_results_tab(self):
        """Create Results & Analytics tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Results & Analytics")

        # Evaluation selection
        select_frame = ttk.Frame(tab)
        select_frame.pack(fill=tk.X, pady=5)

        ttk.Label(select_frame, text="Select Evaluation:").pack(side=tk.LEFT, padx=5)
        self.results_eval_combo = ttk.Combobox(select_frame, width=50, state='readonly')
        self.results_eval_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(select_frame, text="Calculate Results",
                  command=self.calculate_results).pack(side=tk.LEFT, padx=5)
        ttk.Button(select_frame, text="Export Report",
                  command=self.export_results).pack(side=tk.LEFT, padx=5)

        # Results display
        results_frame = ttk.LabelFrame(tab, text="Evaluation Results", padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD,
                                                      width=80, height=25)
        self.results_text.pack(fill=tk.BOTH, expand=True)

    # ======================== Helper Methods ========================

    def load_templates(self):
        """Load all evaluation templates"""
        try:
            self.templates_tree.delete(*self.templates_tree.get_children())

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT template_id, template_name, template_type, description,
                           created_by, created_at
                    FROM evaluation_templates
                    WHERE is_active = 1
                    ORDER BY created_at DESC
                ''')

                for row in cursor.fetchall():
                    self.templates_tree.insert('', tk.END, values=row)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load templates: {e}")

    def load_evaluations(self):
        """Load all course evaluations"""
        try:
            # Clear both treeviews
            self.evaluations_tree.delete(*self.evaluations_tree.get_children())

            # Load for main tab
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT evaluation_id, module_code, academic_year, semester,
                           instructor_id, start_date, end_date, response_count
                    FROM course_evaluations
                    WHERE is_active = 1
                    ORDER BY start_date DESC
                ''')

                rows = cursor.fetchall()
                for row in rows:
                    self.evaluations_tree.insert('', tk.END, values=row)

                # Update combo boxes
                eval_list = [f"{row[0]}: {row[1]} - {row[2]} {row[3]}" for row in rows]
                self.response_eval_combo['values'] = eval_list
                self.results_eval_combo['values'] = eval_list

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load evaluations: {e}")

    def create_template(self):
        """Create a new evaluation template"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Evaluation Template")
        dialog.geometry("500x400")

        # Form fields
        ttk.Label(dialog, text="Template Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        name_entry = ttk.Entry(dialog, width=40)
        name_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Template Type:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        type_combo = ttk.Combobox(dialog, values=['Course', 'Instructor', 'Program', 'Custom'],
                                 width=38, state='readonly')
        type_combo.grid(row=1, column=1, padx=5, pady=5)
        type_combo.current(0)

        ttk.Label(dialog, text="Description:").grid(row=2, column=0, sticky=tk.NW, padx=5, pady=5)
        desc_text = tk.Text(dialog, width=40, height=8)
        desc_text.grid(row=2, column=1, padx=5, pady=5)

        def save_template():
            try:
                name = name_entry.get().strip()
                template_type = type_combo.get()
                description = desc_text.get('1.0', tk.END).strip()

                if not name:
                    messagebox.showerror("Error", "Template name is required")
                    return

                created_by = self.auth.current_user.get('username', 'Unknown') if self.auth.current_user else 'Unknown'

                template_id = EvaluationTemplateManager.create_template(
                    template_name=name,
                    template_type=template_type,
                    description=description,
                    created_by=created_by
                )

                log_activity('create', 'evaluation_template', str(template_id),
                           {'name': name, 'type': template_type})

                messagebox.showinfo("Success",
                                  f"Template created successfully! ID: {template_id}")
                dialog.destroy()
                self.load_templates()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to create template: {e}")

        ttk.Button(dialog, text="Create Template",
                  command=save_template).grid(row=3, column=0, columnspan=2, pady=20)

    def add_questions(self):
        """Add questions to a template"""
        selected = self.templates_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a template first")
            return

        template_id = self.templates_tree.item(selected[0])['values'][0]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Add Questions to Template {template_id}")
        dialog.geometry("600x500")

        # Question form
        ttk.Label(dialog, text="Question Text:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        question_text = tk.Text(dialog, width=50, height=4)
        question_text.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Type:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        type_combo = ttk.Combobox(dialog, values=['Rating', 'Multiple Choice', 'Text', 'Yes/No'],
                                 width=48, state='readonly')
        type_combo.grid(row=1, column=1, padx=5, pady=5)
        type_combo.current(0)

        ttk.Label(dialog, text="Category:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        category_combo = ttk.Combobox(dialog,
                                     values=['Course Content', 'Instructor', 'Materials', 'Assessment', 'General'],
                                     width=48, state='readonly')
        category_combo.grid(row=2, column=1, padx=5, pady=5)
        category_combo.current(0)

        ttk.Label(dialog, text="Scale Min:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        min_entry = ttk.Entry(dialog, width=50)
        min_entry.insert(0, "1")
        min_entry.grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Scale Max:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        max_entry = ttk.Entry(dialog, width=50)
        max_entry.insert(0, "5")
        max_entry.grid(row=4, column=1, padx=5, pady=5)

        def save_question():
            try:
                text = question_text.get('1.0', tk.END).strip()
                if not text:
                    messagebox.showerror("Error", "Question text is required")
                    return

                question_id = EvaluationTemplateManager.add_question(
                    template_id=template_id,
                    question_text=text,
                    question_type=type_combo.get(),
                    question_category=category_combo.get(),
                    scale_min=int(min_entry.get()),
                    scale_max=int(max_entry.get())
                )

                messagebox.showinfo("Success", f"Question added! ID: {question_id}")
                question_text.delete('1.0', tk.END)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add question: {e}")

        ttk.Button(dialog, text="Add Question",
                  command=save_question).grid(row=5, column=0, columnspan=2, pady=20)

    def launch_evaluation(self):
        """Launch a new course evaluation"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Launch Course Evaluation")
        dialog.geometry("500x450")

        fields = {}

        ttk.Label(dialog, text="Module Code:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        fields['module'] = ttk.Entry(dialog, width=40)
        fields['module'].grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Academic Year:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        fields['year'] = ttk.Entry(dialog, width=40)
        fields['year'].insert(0, "2024/2025")
        fields['year'].grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Semester:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        fields['semester'] = ttk.Combobox(dialog, values=['Fall', 'Spring', 'Summer'],
                                         width=38, state='readonly')
        fields['semester'].current(0)
        fields['semester'].grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Instructor ID:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        fields['instructor'] = ttk.Entry(dialog, width=40)
        fields['instructor'].grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Template ID:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        fields['template'] = ttk.Entry(dialog, width=40)
        fields['template'].grid(row=4, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="Start Date:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        fields['start'] = ttk.Entry(dialog, width=40)
        fields['start'].insert(0, datetime.now().strftime('%Y-%m-%d'))
        fields['start'].grid(row=5, column=1, padx=5, pady=5)

        ttk.Label(dialog, text="End Date:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        fields['end'] = ttk.Entry(dialog, width=40)
        fields['end'].grid(row=6, column=1, padx=5, pady=5)

        def save_evaluation():
            try:
                eval_id = CourseEvaluationManager.create_evaluation(
                    module_code=fields['module'].get().strip(),
                    academic_year=fields['year'].get().strip(),
                    semester=fields['semester'].get(),
                    instructor_id=fields['instructor'].get().strip(),
                    template_id=int(fields['template'].get()),
                    start_date=fields['start'].get(),
                    end_date=fields['end'].get()
                )

                log_activity('create', 'course_evaluation', str(eval_id))

                messagebox.showinfo("Success",
                                  f"Evaluation launched successfully! ID: {eval_id}")
                dialog.destroy()
                self.load_evaluations()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to launch evaluation: {e}")

        ttk.Button(dialog, text="Launch Evaluation",
                  command=save_evaluation).grid(row=7, column=0, columnspan=2, pady=20)

    def load_evaluation_questions(self, event=None):
        """Load questions for selected evaluation"""
        try:
            selection = self.response_eval_combo.get()
            if not selection:
                return

            eval_id = int(selection.split(':')[0])

            # Clear previous questions
            for widget in self.questions_frame.winfo_children():
                widget.destroy()

            # Get evaluation template
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT template_id FROM course_evaluations
                    WHERE evaluation_id = ?
                ''', (eval_id,))

                row = cursor.fetchone()
                if not row:
                    return

                template_id = row[0]

                # Get questions
                cursor.execute('''
                    SELECT question_id, question_text, question_type,
                           scale_min, scale_max
                    FROM evaluation_questions
                    WHERE template_id = ?
                    ORDER BY display_order, question_id
                ''', (template_id,))

                self.question_widgets = {}
                row_num = 0

                for question in cursor.fetchall():
                    q_id, text, q_type, min_val, max_val = question

                    ttk.Label(self.questions_frame, text=f"Q{row_num+1}: {text}",
                             wraplength=700).grid(row=row_num, column=0, sticky=tk.W,
                                                 padx=5, pady=10)

                    if q_type == 'Rating':
                        scale_frame = ttk.Frame(self.questions_frame)
                        scale_frame.grid(row=row_num, column=1, padx=5, pady=10)

                        var = tk.IntVar(value=min_val)
                        for i in range(min_val, max_val + 1):
                            ttk.Radiobutton(scale_frame, text=str(i), value=i,
                                          variable=var).pack(side=tk.LEFT)
                        self.question_widgets[q_id] = var

                    elif q_type == 'Yes/No':
                        var = tk.StringVar(value="Yes")
                        frame = ttk.Frame(self.questions_frame)
                        frame.grid(row=row_num, column=1, padx=5, pady=10)
                        ttk.Radiobutton(frame, text="Yes", value="Yes",
                                      variable=var).pack(side=tk.LEFT)
                        ttk.Radiobutton(frame, text="No", value="No",
                                      variable=var).pack(side=tk.LEFT)
                        self.question_widgets[q_id] = var

                    else:  # Text
                        entry = ttk.Entry(self.questions_frame, width=50)
                        entry.grid(row=row_num, column=1, padx=5, pady=10)
                        self.question_widgets[q_id] = entry

                    row_num += 1

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load questions: {e}")

    def submit_response(self):
        """Submit evaluation response"""
        try:
            selection = self.response_eval_combo.get()
            if not selection:
                messagebox.showwarning("Warning", "Please select an evaluation")
                return

            eval_id = int(selection.split(':')[0])
            student_id = self.auth.current_user.get('username') if self.auth.current_user else None

            # Start response
            response_id = ResponseManager.start_response(eval_id, student_id)

            # Record answers
            for q_id, widget in self.question_widgets.items():
                if isinstance(widget, tk.IntVar):
                    value = str(widget.get())
                    numeric_value = float(widget.get())
                elif isinstance(widget, tk.StringVar):
                    value = widget.get()
                    numeric_value = 1.0 if value == "Yes" else 0.0
                else:  # Entry
                    value = widget.get()
                    numeric_value = None

                ResponseManager.record_answer(response_id, q_id, value, numeric_value)

            # Complete response
            ResponseManager.complete_response(response_id, 10)  # Assume 10 minutes

            log_activity('submit', 'evaluation_response', str(response_id),
                       {'evaluation_id': eval_id})

            messagebox.showinfo("Success", "Thank you for your feedback!")

            # Clear form
            for widget in self.questions_frame.winfo_children():
                widget.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to submit response: {e}")

    def calculate_results(self):
        """Calculate and display results"""
        try:
            selection = self.results_eval_combo.get()
            if not selection:
                messagebox.showwarning("Warning", "Please select an evaluation")
                return

            eval_id = int(selection.split(':')[0])

            results = ResultsAnalyticsManager.calculate_results(eval_id)

            # Display results
            self.results_text.delete('1.0', tk.END)
            self.results_text.insert(tk.END, f"EVALUATION RESULTS - ID: {eval_id}\n")
            self.results_text.insert(tk.END, "=" * 80 + "\n\n")

            for result in results:
                self.results_text.insert(tk.END,
                    f"Question ID: {result['question_id']}\n"
                    f"Question: {result['question_text']}\n"
                    f"Average Score: {result['average_score']:.2f}\n"
                    f"Responses: {result['response_count']}\n"
                    f"{'-' * 80}\n\n"
                )

            messagebox.showinfo("Success", "Results calculated successfully!")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to calculate results: {e}")

    def export_results(self):
        """Export results to file"""
        messagebox.showinfo("Export", "Export feature coming soon!")

    def view_evaluation_details(self):
        """View detailed evaluation information"""
        selected = self.evaluations_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an evaluation first")
            return

        eval_id = self.evaluations_tree.item(selected[0])['values'][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM course_evaluations
                    WHERE evaluation_id = ?
                ''', (eval_id,))

                eval_data = cursor.fetchone()
                if eval_data:
                    info = (
                        f"Evaluation ID: {eval_data[0]}\n"
                        f"Module: {eval_data[1]}\n"
                        f"Academic Year: {eval_data[2]}\n"
                        f"Semester: {eval_data[3]}\n"
                        f"Instructor: {eval_data[4]}\n"
                        f"Start Date: {eval_data[6]}\n"
                        f"End Date: {eval_data[7]}\n"
                        f"Responses: {eval_data[8]}\n"
                    )
                    messagebox.showinfo("Evaluation Details", info)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load details: {e}")


def launch_course_evaluation_gui(root, auth):
    """Launch the Course Evaluation GUI"""
    try:
        if not auth or not hasattr(auth, 'current_user') or not auth.current_user:
            messagebox.showerror("Error", "You must be logged in to access Course Evaluation System.")
            return

        CourseEvaluationGUI(root, auth)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch Course Evaluation System: {e}")


__all__ = ['CourseEvaluationGUI', 'launch_course_evaluation_gui']
