"""
AI Study Companion GUI

Provides graphical interface for AI-powered study features.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional

from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.modules.domain.academics.ai_study.services.ai_study_service import AIStudyService
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.infrastructure.localization import get_translation

_t = get_translation


class AIStudyGUI:
    """GUI for AI Study Companion features."""

    def __init__(self, parent=None, auth=None):
        """Initialize the AI Study GUI."""
        self.service = AIStudyService()
        self.auth = auth or get_auth()

        # When ``parent`` is a workspace tab Frame (passed by
        # ``open_in_workspace``), embed inside it directly. Frames
        # have no ``wm_title``; Tk/Toplevel do.
        if parent is not None and not hasattr(parent, "wm_title"):
            self.window = parent
            self._owns_window = False
        else:
            self.window = tk.Toplevel(parent) if parent else tk.Tk()
            self.window.title(_t("ai_study.window.title", default="AI Study Companion"))
            self.window.geometry("1000x700")
            self._owns_window = True

        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface."""
        # Check if user is logged in
        if not self.auth.current_user:
            error_frame = ttk.Frame(self.window, padding=20)
            error_frame.pack(fill='both', expand=True)

            ttk.Label(error_frame,
                     text=_t("ai_study.auth.login_required", default="⚠️ Please log in to access AI Study Companion"),
                     font=('Arial', 14, 'bold'),
                     foreground='red').pack(pady=20)

            ttk.Label(error_frame,
                     text=_t("ai_study.auth.login_required_description", default="You must be logged in through the main GUI to use this feature."),
                     font=('Arial', 11)).pack(pady=10)

            ttk.Button(error_frame,
                      text=_t("ai_study.buttons.close", default="Close"),
                      command=self.window.destroy).pack(pady=20)
            return

        # Display user info header
        user_info = self.auth.get_current_user()
        header_frame = ttk.Frame(self.window, padding=5)
        header_frame.pack(fill='x', padx=10, pady=(10, 0))

        ttk.Label(header_frame,
                 text=f"{_t('ai_study.auth.logged_in_as', default='👤 Logged in as: ')}{user_info.get('username', user_info.get('id', 'Unknown'))}",
                 font=('Arial', 10)).pack(side='left')

        # Create notebook for tabs
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Study Plans Tab
        self.study_plans_frame = ttk.Frame(notebook)
        notebook.add(self.study_plans_frame, text=_t("ai_study.tabs.study_plans", default="Study Plans"))
        self.setup_study_plans_tab()

        # Flashcards Tab
        self.flashcards_frame = ttk.Frame(notebook)
        notebook.add(self.flashcards_frame, text=_t("ai_study.tabs.flashcards", default="Flashcards"))
        self.setup_flashcards_tab()

        # Concept Explainer Tab
        self.explainer_frame = ttk.Frame(notebook)
        notebook.add(self.explainer_frame, text=_t("ai_study.tabs.concept_explainer", default="Concept Explainer"))
        self.setup_explainer_tab()

        # Analytics Tab
        self.analytics_frame = ttk.Frame(notebook)
        notebook.add(self.analytics_frame, text=_t("ai_study.tabs.analytics", default="Analytics"))
        self.setup_analytics_tab()

    def setup_study_plans_tab(self):
        """Set up study plans tab."""
        # Create study plan section
        create_frame = ttk.LabelFrame(self.study_plans_frame, text=_t("ai_study.study_plans.section_title", default="Generate Study Plan"), padding=10)
        create_frame.pack(fill='x', padx=10, pady=10)

        # Module/Course dropdown
        ttk.Label(create_frame, text=_t("ai_study.study_plans.module_course", default="Module/Course:")).grid(row=0, column=0, sticky='w', pady=5)
        self.course_id_var = tk.StringVar()
        self.course_id_combo = ttk.Combobox(create_frame, textvariable=self.course_id_var, width=28, state='readonly')
        self.course_id_combo.grid(row=0, column=1, pady=5, sticky='w')

        # Bind selection event to auto-fill exam date
        self.course_id_combo.bind('<<ComboboxSelected>>', self._on_module_selected)

        # Load available modules
        self._load_available_modules()

        # Refresh button for modules
        ttk.Button(create_frame, text=_t("ai_study.buttons.refresh", default="🔄"), width=3,
                  command=self._load_available_modules).grid(row=0, column=2, padx=5)

        # Exam date
        ttk.Label(create_frame, text=_t("ai_study.study_plans.exam_date", default="Exam Date (YYYY-MM-DD):")).grid(row=1, column=0, sticky='w', pady=5)
        self.exam_date_entry = ttk.Entry(create_frame, width=30)
        self.exam_date_entry.grid(row=1, column=1, pady=5)

        # Hours per day
        ttk.Label(create_frame, text=_t("ai_study.study_plans.hours_per_day", default="Hours Per Day:")).grid(row=2, column=0, sticky='w', pady=5)
        self.hours_per_day = ttk.Spinbox(create_frame, from_=1, to=12, width=28)
        self.hours_per_day.set(2)
        self.hours_per_day.grid(row=2, column=1, pady=5)

        # Generate button
        ttk.Button(create_frame, text=_t("ai_study.study_plans.generate_button", default="Generate Study Plan"),
                  command=self.generate_plan).grid(row=3, column=0, columnspan=2, pady=10)

        # Plans list section
        list_frame = ttk.LabelFrame(self.study_plans_frame, text=_t("ai_study.study_plans.list_title", default="My Study Plans"), padding=10)
        list_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Plans treeview
        columns = (
            _t("ai_study.study_plans.plan_id", default="Plan ID"),
            _t("ai_study.study_plans.course", default="Course"),
            _t("ai_study.study_plans.exam_date_col", default="Exam Date"),
            _t("ai_study.study_plans.total_hours", default="Total Hours"),
            _t("ai_study.study_plans.status", default="Status")
        )
        self.plans_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)

        for col in columns:
            self.plans_tree.heading(col, text=col)
            self.plans_tree.column(col, width=150)

        self.plans_tree.pack(fill='both', expand=True)

        # Buttons
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill='x', pady=5)

        ttk.Button(btn_frame, text=_t("ai_study.study_plans.view_tasks", default="View Tasks"),
                  command=self.view_plan_tasks).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t("ai_study.study_plans.refresh", default="Refresh"),
                  command=self.load_study_plans).pack(side='left', padx=5)

        # Load plans
        self.load_study_plans()

    def setup_flashcards_tab(self):
        """Set up flashcards tab."""
        # Create flashcard section
        create_frame = ttk.LabelFrame(self.flashcards_frame, text=_t("ai_study.flashcards.create_section", default="Create Flashcard"), padding=10)
        create_frame.pack(fill='x', padx=10, pady=10)

        # Deck name
        ttk.Label(create_frame, text=_t("ai_study.flashcards.deck_name", default="Deck Name:")).grid(row=0, column=0, sticky='w', pady=5)
        self.deck_name_entry = ttk.Entry(create_frame, width=40)
        self.deck_name_entry.grid(row=0, column=1, pady=5, padx=5)

        # Question
        ttk.Label(create_frame, text=_t("ai_study.flashcards.question", default="Question:")).grid(row=1, column=0, sticky='w', pady=5)
        self.question_entry = ttk.Entry(create_frame, width=40)
        self.question_entry.grid(row=1, column=1, pady=5, padx=5)

        # Answer
        ttk.Label(create_frame, text=_t("ai_study.flashcards.answer", default="Answer:")).grid(row=2, column=0, sticky='w', pady=5)
        self.answer_entry = ttk.Entry(create_frame, width=40)
        self.answer_entry.grid(row=2, column=1, pady=5, padx=5)

        # Create button
        ttk.Button(create_frame, text=_t("ai_study.flashcards.create_button", default="Create Flashcard"),
                  command=self.create_flashcard).grid(row=3, column=0, columnspan=2, pady=10)

        # Review section
        review_frame = ttk.LabelFrame(self.flashcards_frame, text=_t("ai_study.flashcards.review_section", default="Review Flashcards"), padding=10)
        review_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Decks list
        ttk.Label(review_frame, text=_t("ai_study.flashcards.select_deck", default="Select Deck:")).pack(anchor='w')
        self.deck_listbox = tk.Listbox(review_frame, height=8)
        self.deck_listbox.pack(fill='x', pady=5)

        ttk.Button(review_frame, text=_t("ai_study.flashcards.start_review", default="Start Review Session"),
                  command=self.start_review_session).pack(pady=5)

        ttk.Button(review_frame, text=_t("ai_study.flashcards.refresh_decks", default="Refresh Decks"),
                  command=self.load_flashcard_decks).pack(pady=5)

        # Load decks
        self.load_flashcard_decks()

    def setup_explainer_tab(self):
        """Set up concept explainer tab."""
        # Input section
        input_frame = ttk.LabelFrame(self.explainer_frame, text=_t("ai_study.concept_explainer.section_title", default="Explain a Concept"), padding=10)
        input_frame.pack(fill='x', padx=10, pady=10)

        # Concept name
        ttk.Label(input_frame, text=_t("ai_study.concept_explainer.concept_name", default="Concept Name:")).grid(row=0, column=0, sticky='w', pady=5)
        self.concept_entry = ttk.Entry(input_frame, width=40)
        self.concept_entry.grid(row=0, column=1, pady=5, padx=5)

        # Difficulty level
        ttk.Label(input_frame, text=_t("ai_study.concept_explainer.difficulty_level", default="Difficulty Level:")).grid(row=1, column=0, sticky='w', pady=5)
        self.difficulty_combo = ttk.Combobox(input_frame, width=37,
                                            values=[
                                                _t("ai_study.concept_explainer.difficulty_beginner", default="Beginner"),
                                                _t("ai_study.concept_explainer.difficulty_intermediate", default="Intermediate"),
                                                _t("ai_study.concept_explainer.difficulty_advanced", default="Advanced")
                                            ])
        self.difficulty_combo.set(_t("ai_study.concept_explainer.difficulty_beginner", default="Beginner"))
        self.difficulty_combo.grid(row=1, column=1, pady=5, padx=5)

        # Explain button
        ttk.Button(input_frame, text=_t("ai_study.concept_explainer.explain_button", default="Explain Concept"),
                  command=self.explain_concept).grid(row=2, column=0, columnspan=2, pady=10)

        # Explanation section
        output_frame = ttk.LabelFrame(self.explainer_frame, text=_t("ai_study.concept_explainer.output_section", default="Explanation"), padding=10)
        output_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.explanation_text = scrolledtext.ScrolledText(output_frame, height=20, wrap='word')
        self.explanation_text.pack(fill='both', expand=True)

        # Rating section
        rating_frame = ttk.Frame(output_frame)
        rating_frame.pack(fill='x', pady=5)

        ttk.Label(rating_frame, text=_t("ai_study.concept_explainer.rate_explanation", default="Rate this explanation:")).pack(side='left')
        self.rating_var = tk.IntVar(value=3)
        for i in range(1, 6):
            ttk.Radiobutton(rating_frame, text=str(i), variable=self.rating_var,
                          value=i).pack(side='left', padx=5)

    def setup_analytics_tab(self):
        """Set up analytics tab."""
        # Analytics display
        analytics_frame = ttk.LabelFrame(self.analytics_frame, text=_t("ai_study.analytics.section_title", default="Study Analytics"), padding=10)
        analytics_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.analytics_text = scrolledtext.ScrolledText(analytics_frame, height=25, wrap='word')
        self.analytics_text.pack(fill='both', expand=True)

        ttk.Button(analytics_frame, text=_t("ai_study.analytics.refresh_button", default="Refresh Analytics"),
                  command=self.load_analytics).pack(pady=10)

        # Load analytics
        self.load_analytics()

    # Helper methods

    def _load_available_modules(self):
        """Load available modules based on user role and enrollment."""
        from education_system.university_system.infrastructure.database.db import get_connection

        try:
            user_info = self.auth.get_current_user()
            student_id = user_info.get('id')
            user_role = user_info.get('role', '').lower()

            with get_connection() as conn:
                if user_role == 'admin':
                    # Admin can see all active modules
                    modules = conn.execute("""
                        SELECT DISTINCT module_code, module_name
                        FROM modules
                        WHERE is_active = 1
                        ORDER BY module_code
                    """).fetchall()
                else:
                    # Students see only their enrolled modules
                    modules = conn.execute("""
                        SELECT DISTINCT m.module_code, m.module_name
                        FROM modules m
                        INNER JOIN module_grades mg ON m.module_code = mg.module_code
                        WHERE mg.student_id = ?
                        AND m.is_active = 1
                        ORDER BY m.module_code
                    """, (student_id,)).fetchall()

                # Format module list
                module_list = []
                for module in modules:
                    module_code = module['module_code']
                    module_name = module['module_name']
                    module_list.append(f"{module_code} - {module_name}")

                # Update combobox
                self.course_id_combo['values'] = module_list

                # Add "None (General Study)" option at the beginning
                none_option = _t("ai_study.study_plans.none_general", default="None (General Study)")
                if module_list:
                    all_values = [none_option] + module_list
                    self.course_id_combo['values'] = all_values
                else:
                    self.course_id_combo['values'] = [none_option]

                # Set default
                if self.course_id_combo['values']:
                    self.course_id_combo.current(0)

        except Exception as e:
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"),
                               _t("ai_study.errors.load_modules_failed", default="Failed to load modules: {error}").format(error=str(e)))

    def _on_module_selected(self, event=None):
        """Auto-fill exam date when a module is selected."""
        from education_system.university_system.infrastructure.database.db import get_connection

        selected = self.course_id_var.get()
        none_option = _t("ai_study.study_plans.none_general", default="None (General Study)")

        # Clear exam date if "None (General Study)" is selected
        if not selected or selected == none_option:
            self.exam_date_entry.delete(0, tk.END)
            return

        # Extract module code
        module_code = selected.split(' - ')[0].strip()

        try:
            with get_connection() as conn:
                # Query academic_calendar_events for this module's exam
                exam_event = conn.execute("""
                    SELECT date_start, date, name
                    FROM academic_calendar_events
                    WHERE event_type = 'Exam'
                    AND (name LIKE ? OR name LIKE ?)
                    ORDER BY date_start DESC, date DESC
                    LIMIT 1
                """, (f"%{escape_like(module_code)}%", f"%Exam: {escape_like(module_code)}%")).fetchone()

                if exam_event:
                    # Get the exam date (prefer date_start, fallback to date)
                    exam_date_str = exam_event['date_start'] or exam_event['date']

                    if exam_date_str:
                        # Parse and format the date (extract just YYYY-MM-DD)
                        try:
                            # Handle both "YYYY-MM-DD HH:MM" and "YYYY-MM-DD" formats
                            exam_date = exam_date_str.split(' ')[0]

                            # Update the entry field
                            self.exam_date_entry.delete(0, tk.END)
                            self.exam_date_entry.insert(0, exam_date)

                            # Show a subtle indicator
                            self.exam_date_entry.config(foreground='green')
                            self.window.after(2000, lambda: self.exam_date_entry.config(foreground='black'))

                        except Exception:
                            pass
                else:
                    # No exam found - clear the field
                    self.exam_date_entry.delete(0, tk.END)

        except Exception as e:
            # Silently fail - user can still enter date manually
            pass

    # Event handlers

    def generate_plan(self):
        """Generate a new study plan."""
        if not self.auth.current_user:
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"),
                               _t("ai_study.auth.please_login", default="Please login first"))
            return

        student_id = self.auth.get_current_user()['id']

        # Extract module code from combobox selection
        selected = self.course_id_var.get()
        none_option = _t("ai_study.study_plans.none_general", default="None (General Study)")
        if selected and selected != none_option:
            # Extract module code (format: "CODE - Name")
            course_id = selected.split(' - ')[0].strip()
        else:
            course_id = None

        exam_date = self.exam_date_entry.get().strip()
        hours = int(self.hours_per_day.get())

        if not exam_date:
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"),
                               _t("ai_study.study_plans.no_exam_date", default="Please enter exam date"))
            return

        try:
            result = self.service.generate_study_plan(student_id, course_id, exam_date, hours)
            messagebox.showinfo(_t("ai_study.messages.success", default="Success"),
                              _t("ai_study.study_plans.success_message",
                                 default="Study plan created!\nPlan ID: {plan_id}\nDays until exam: {days_until_exam}\nTasks generated: {tasks_generated}").format(
                                  plan_id=result['plan_id'],
                                  days_until_exam=result['days_until_exam'],
                                  tasks_generated=result['tasks_generated']
                              ))
            self.load_study_plans()

            # Clear entries
            self.course_id_combo.current(0)
            self.exam_date_entry.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"),
                               _t("ai_study.study_plans.generation_failed", default="Failed to generate plan: {error}").format(error=str(e)))

    def load_study_plans(self):
        """Load student's study plans."""
        if not self.auth.current_user:
            return

        # Clear tree
        for item in self.plans_tree.get_children():
            self.plans_tree.delete(item)

        student_id = self.auth.get_current_user()['id']
        plans = self.service.get_student_study_plans(student_id)

        for plan in plans:
            self.plans_tree.insert('', 'end', values=(
                plan.get('plan_id', 0),
                plan.get('course_id', _t("ai_study.columns.n_a", default="N/A")),
                plan.get('end_date', _t("ai_study.columns.n_a", default="N/A")),
                plan.get('total_hours', 0) or 0,
                plan.get('status', _t("ai_study.columns.unknown", default="Unknown"))
            ))

    def view_plan_tasks(self):
        """View tasks for selected plan."""
        selection = self.plans_tree.selection()
        if not selection:
            messagebox.showwarning(_t("ai_study.messages.warning", default="Warning"),
                                 _t("ai_study.study_plans.select_plan_warning", default="Please select a study plan"))
            return

        item = self.plans_tree.item(selection[0])
        plan_id = item['values'][0]

        plan_data = self.service.get_study_plan(plan_id)
        if not plan_data:
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"),
                               _t("ai_study.study_plans.plan_not_found", default="Plan not found"))
            return

        # Create tasks window
        tasks_window = tk.Toplevel(self.window)
        tasks_window.title(f"{_t('ai_study.window.tasks_title', default='Study Plan Tasks - Plan #')}{plan_id}")
        tasks_window.geometry("800x500")

        # Tasks tree
        columns = (
            _t("ai_study.tasks.task", default="Task"),
            _t("ai_study.tasks.date", default="Date"),
            _t("ai_study.tasks.duration", default="Duration"),
            _t("ai_study.tasks.priority", default="Priority"),
            _t("ai_study.tasks.status", default="Status")
        )
        tree = ttk.Treeview(tasks_window, columns=columns, show='headings')

        for col in columns:
            tree.heading(col, text=col)

        tree.pack(fill='both', expand=True, padx=10, pady=10)

        for task in plan_data['tasks']:
            status = _t("ai_study.tasks.completed", default="Completed") if task.get('completed') else _t("ai_study.tasks.pending", default="Pending")
            duration = task.get('duration_minutes', 0) or 0
            tree.insert('', 'end', values=(
                task.get('task_title', _t("ai_study.tasks.untitled", default="Untitled")),
                task.get('scheduled_date', _t("ai_study.columns.n_a", default="N/A")),
                f"{duration}{_t('ai_study.tasks.minutes_suffix', default=' min')}",
                task.get('priority', _t("ai_study.tasks.normal_priority", default="Normal")),
                status
            ))

    def create_flashcard(self):
        """Create a new flashcard."""
        if not self.auth.current_user:
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"),
                               _t("ai_study.auth.please_login", default="Please login first"))
            return

        deck_name = self.deck_name_entry.get().strip()
        question = self.question_entry.get().strip()
        answer = self.answer_entry.get().strip()

        if not all([deck_name, question, answer]):
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"),
                               _t("ai_study.flashcards.fill_all_fields", default="Please fill all fields"))
            return

        try:
            student_id = self.auth.get_current_user()['id']
            flashcard_id = self.service.create_flashcard(student_id, None, deck_name,
                                                        question, answer)
            messagebox.showinfo(_t("ai_study.messages.success", default="Success"),
                              _t("ai_study.flashcards.success_message", default="Flashcard created! ID: {flashcard_id}").format(flashcard_id=flashcard_id))

            # Clear entries
            self.question_entry.delete(0, tk.END)
            self.answer_entry.delete(0, tk.END)
            self.load_flashcard_decks()
        except Exception as e:
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"),
                               _t("ai_study.flashcards.creation_failed", default="Failed to create flashcard: {error}").format(error=str(e)))

    def load_flashcard_decks(self):
        """Load flashcard decks."""
        if not self.auth.current_user:
            return

        self.deck_listbox.delete(0, tk.END)

        student_id = self.auth.get_current_user()['id']
        decks = self.service.get_flashcard_decks(student_id)

        for deck in decks:
            accuracy = deck.get('accuracy', 0) or 0
            total_cards = deck.get('total_cards', 0) or 0
            due_count = deck.get('due_count', 0) or 0
            deck_name = deck.get('deck_name', _t("ai_study.columns.unknown", default="Unknown"))
            self.deck_listbox.insert(tk.END,
                _t("ai_study.flashcards.deck_info",
                   default="{deck_name} - {total_cards} cards, {due_count} due, {accuracy}% accuracy").format(
                    deck_name=deck_name,
                    total_cards=total_cards,
                    due_count=due_count,
                    accuracy=f"{accuracy:.1f}"
                ))

    def start_review_session(self):
        """Start a flashcard review session."""
        selection = self.deck_listbox.curselection()
        if not selection:
            messagebox.showwarning(_t("ai_study.messages.warning", default="Warning"),
                                 _t("ai_study.flashcards.select_deck_warning", default="Please select a deck"))
            return

        deck_text = self.deck_listbox.get(selection[0])
        deck_name = deck_text.split(' - ')[0]

        student_id = self.auth.get_current_user()['id']
        flashcards = self.service.get_due_flashcards(student_id, deck_name)

        if not flashcards:
            messagebox.showinfo(_t("ai_study.messages.info", default="Info"),
                              _t("ai_study.flashcards.no_cards_due", default="No flashcards due for review!"))
            return

        # Create review window
        self._show_review_window(flashcards)

    def _show_review_window(self, flashcards):
        """Show flashcard review window."""
        review_window = tk.Toplevel(self.window)
        review_window.title(_t("ai_study.flashcards.review_window_title", default="Flashcard Review"))
        review_window.geometry("600x400")

        current_index = [0]  # Use list to allow modification in nested function
        show_answer = [False]

        question_label = ttk.Label(review_window, text="", font=('Arial', 14), wraplength=550)
        question_label.pack(pady=20)

        answer_label = ttk.Label(review_window, text="", font=('Arial', 12), wraplength=550)
        answer_label.pack(pady=20)

        def show_card():
            """Display current flashcard."""
            if current_index[0] >= len(flashcards):
                messagebox.showinfo(_t("ai_study.messages.complete", default="Complete"),
                                  _t("ai_study.flashcards.review_complete", default="Review session complete!"))
                review_window.destroy()
                return

            card = flashcards[current_index[0]]
            question_label.config(text=_t("ai_study.flashcards.question_label", default="Question:\n{question}").format(question=card['question']))

            if show_answer[0]:
                answer_label.config(text=_t("ai_study.flashcards.answer_label", default="Answer:\n{answer}").format(answer=card['answer']))
            else:
                answer_label.config(text=_t("ai_study.flashcards.show_answer_prompt", default="Click 'Show Answer' to reveal"))

        def toggle_answer():
            """Toggle answer visibility."""
            show_answer[0] = not show_answer[0]
            show_card()

        def mark_correct():
            """Mark flashcard as correct."""
            card = flashcards[current_index[0]]
            self.service.review_flashcard(card['flashcard_id'], True)
            current_index[0] += 1
            show_answer[0] = False
            show_card()

        def mark_incorrect():
            """Mark flashcard as incorrect."""
            card = flashcards[current_index[0]]
            self.service.review_flashcard(card['flashcard_id'], False)
            current_index[0] += 1
            show_answer[0] = False
            show_card()

        # Buttons
        btn_frame = ttk.Frame(review_window)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text=_t("ai_study.flashcards.show_answer_button", default="Show Answer"),
                  command=toggle_answer).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t("ai_study.flashcards.correct_button", default="✓ Correct"),
                  command=mark_correct).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t("ai_study.flashcards.incorrect_button", default="✗ Incorrect"),
                  command=mark_incorrect).pack(side='left', padx=5)

        show_card()

    def explain_concept(self):
        """Get AI explanation for a concept."""
        if not self.auth.current_user:
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"),
                               _t("ai_study.auth.please_login", default="Please login first"))
            return

        concept = self.concept_entry.get().strip()
        if not concept:
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"),
                               _t("ai_study.concept_explainer.no_concept_name", default="Please enter a concept name"))
            return

        difficulty = self.difficulty_combo.get()
        student_id = self.auth.get_current_user()['id']

        try:
            result = self.service.explain_concept(student_id, None, concept, difficulty)

            self.explanation_text.delete(1.0, tk.END)
            self.explanation_text.insert(1.0, result['explanation'])

            self.current_explanation_id = result['explanation_id']
        except Exception as e:
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"),
                               _t("ai_study.concept_explainer.explanation_failed", default="Failed to explain concept: {error}").format(error=str(e)))

    def load_analytics(self):
        """Load study analytics."""
        if not self.auth.current_user:
            return

        student_id = self.auth.get_current_user()['id']
        analytics = self.service.get_study_analytics(student_id)

        self.analytics_text.delete(1.0, tk.END)

        text = f"{_t('ai_study.analytics.header', default='=== STUDY ANALYTICS ===')}\n\n"

        # Study Plans
        text += f"{_t('ai_study.analytics.study_plans_header', default='📚 STUDY PLANS')}\n"
        plans = analytics.get('study_plans', {}) or {}
        text += f"{_t('ai_study.analytics.total_plans', default='Total Plans: {total_plans}').format(total_plans=plans.get('total_plans', 0) or 0)}\n"
        text += f"{_t('ai_study.analytics.active_plans', default='Active Plans: {active_plans}').format(active_plans=plans.get('active_plans', 0) or 0)}\n"
        text += f"{_t('ai_study.analytics.planned_hours', default='Total Hours Planned: {planned_hours}').format(planned_hours=plans.get('planned_hours', 0) or 0)}\n\n"

        # Tasks
        text += f"{_t('ai_study.analytics.tasks_header', default='✓ TASKS')}\n"
        tasks = analytics.get('tasks', {}) or {}
        text += f"{_t('ai_study.analytics.total_tasks', default='Total Tasks: {total_tasks}').format(total_tasks=tasks.get('total_tasks', 0) or 0)}\n"
        text += f"{_t('ai_study.analytics.completed_tasks', default='Completed Tasks: {completed_tasks}').format(completed_tasks=tasks.get('completed_tasks', 0) or 0)}\n"
        total_tasks = tasks.get('total_tasks', 0) or 0
        if total_tasks > 0:
            completed_tasks = tasks.get('completed_tasks', 0) or 0
            completion_rate = (completed_tasks / total_tasks) * 100
            text += f"{_t('ai_study.analytics.completion_rate', default='Completion Rate: {completion_rate}%').format(completion_rate=f'{completion_rate:.1f}')}\n"
        text += f"{_t('ai_study.analytics.total_study_time', default='Total Study Time: {total_minutes} minutes').format(total_minutes=tasks.get('total_minutes', 0) or 0)}\n\n"

        # Flashcards
        text += f"{_t('ai_study.analytics.flashcards_header', default='🃏 FLASHCARDS')}\n"
        cards = analytics.get('flashcards', {}) or {}
        text += f"{_t('ai_study.analytics.total_cards', default='Total Cards: {total_cards}').format(total_cards=cards.get('total_cards', 0) or 0)}\n"
        text += f"{_t('ai_study.analytics.total_decks', default='Total Decks: {total_decks}').format(total_decks=cards.get('total_decks', 0) or 0)}\n"
        avg_accuracy = cards.get('avg_accuracy', 0) or 0
        text += f"{_t('ai_study.analytics.average_accuracy', default='Average Accuracy: {avg_accuracy}%').format(avg_accuracy=f'{avg_accuracy:.1f}')}\n"

        self.analytics_text.insert(1.0, text)

    def run(self):
        """Run the GUI."""
        self.window.mainloop()


def main():
    """Main entry point."""
    app = AIStudyGUI()
    app.run()


if __name__ == "__main__":
    main()
