"""
AI Study Companion GUI

Provides graphical interface for AI-powered study features.
"""
import logging

logger = logging.getLogger(__name__)

import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from datetime import date, datetime, timedelta
from typing import Optional

from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.domains.student_life.domain.ai_study.services.ai_study_service import AIStudyService
from education_system.systems.university.domains.student_life.domain.study_hub.services import (
    study_context,
)
from education_system.systems.university.infrastructure.shared_context import get_auth
from education_system.systems.university.infrastructure.i18n import get_text as get_translation

_t = get_translation

_SOURCE_LABELS = {
    "claude": "Written by Claude (AI) — check it against your course materials.",
    "course_materials": "From your module records and your own cards (AI is not configured).",
    "extracted": "Taken from definitions in your notes (AI is not configured).",
    "explanation": "Made from an explanation.",
    "template": "Saved explanation.",
}


class AIStudyGUI:
    """GUI for AI Study Companion features."""

    def __init__(self, parent=None, auth=None):
        """Initialize the AI Study GUI."""
        self.service = AIStudyService()
        self.auth = auth or get_auth()
        user = getattr(self.auth, 'current_user', None) or {}
        # Companion rows key on the student number (or a staff username) —
        # never current_user['id'], the users-table row id.
        self.owner = study_context.owner_id(user)
        self.is_staff = study_context.is_staff(user)
        self.current_explanation_id = None
        self._jobs = queue.Queue()

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
        if self.owner and not self.is_staff:
            self.window.after(1500, self._send_own_reminder)

    # ── background work ─────────────────────────────────────────────────

    def _background(self, work, done, busy_text=None):
        """Run ``work()`` off the Tk thread (Claude can take a while) and
        hand its result — or the exception — to ``done(result, error)``."""
        if busy_text and hasattr(self, 'status_var'):
            self.status_var.set(busy_text)

        def run():
            try:
                self._jobs.put((done, work(), None))
            except Exception as exc:  # reported on the Tk thread
                self._jobs.put((done, None, exc))

        self._pending = getattr(self, '_pending', 0) + 1
        threading.Thread(target=run, daemon=True).start()
        if self._pending == 1:
            self.window.after(100, self._drain_jobs)

    def _drain_jobs(self):
        try:
            while True:
                done, result, error = self._jobs.get_nowait()
                self._pending -= 1
                try:
                    if hasattr(self, 'status_var'):
                        self.status_var.set("")
                    done(result, error)
                except tk.TclError:
                    # The window was closed while the work ran.
                    logger.debug("AI Study window closed before a job finished")
        except queue.Empty:
            pass
        if self._pending > 0:
            try:
                self.window.after(150, self._drain_jobs)
            except tk.TclError:
                pass

    def _send_own_reminder(self):
        def done(result, error):
            if error:
                logger.debug("Study reminder failed", exc_info=error)
        self._background(lambda: self.service.send_my_reminder(self.owner), done)

    def _error(self, error):
        if isinstance(error, (ValueError, PermissionError)):
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"), str(error),
                                 parent=self.window)
        else:
            logger.exception("AI Study Companion error", exc_info=error)
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"),
                                 str(error), parent=self.window)

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
        self.status_var = tk.StringVar()
        ttk.Label(header_frame, textvariable=self.status_var, foreground='gray').pack(side='right')

        # Create notebook for tabs
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        self.notebook = notebook

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

        # This Week Tab
        self.week_frame = ttk.Frame(notebook)
        notebook.add(self.week_frame, text=_t("ai_study.tabs.this_week", default="This Week"))
        self.setup_week_tab()

        # Settings Tab
        self.settings_frame = ttk.Frame(notebook)
        notebook.add(self.settings_frame, text=_t("ai_study.tabs.settings", default="Settings"))
        self.setup_settings_tab()

        # Student Overview Tab (staff)
        if self.is_staff:
            self.staff_frame = ttk.Frame(notebook)
            notebook.add(self.staff_frame, text=_t("ai_study.tabs.student_overview", default="Student Overview"))
            self.setup_staff_tab()

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
        self.exam_info_var = tk.StringVar()
        ttk.Label(create_frame, textvariable=self.exam_info_var, foreground='gray').grid(row=1, column=2, columnspan=2, sticky='w', padx=5)

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

        # Buttons (packed before the tree so they stay visible on short screens)
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(side='bottom', fill='x', pady=5)

        ttk.Button(btn_frame, text=_t("ai_study.study_plans.view_tasks", default="View Tasks"),
                  command=self.view_plan_tasks).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t("ai_study.study_plans.complete_task", default="Complete Task"),
                  command=self.complete_task_gui).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t("ai_study.study_plans.refresh", default="Refresh"),
                  command=self.load_study_plans).pack(side='left', padx=5)
        ttk.Separator(btn_frame, orient='vertical').pack(side='left', fill='y', padx=6)
        ttk.Button(btn_frame, text=_t("ai_study.study_plans.edit_plan", default="Edit Plan"),
                  command=self.edit_plan).pack(side='left', padx=3)
        ttk.Button(btn_frame, text=_t("ai_study.study_plans.reschedule_missed", default="Reschedule Missed"),
                  command=self.reschedule_missed).pack(side='left', padx=3)
        ttk.Button(btn_frame, text=_t("ai_study.study_plans.pause_resume", default="Pause / Resume"),
                  command=self.toggle_pause_plan).pack(side='left', padx=3)
        ttk.Button(btn_frame, text=_t("ai_study.study_plans.archive", default="Archive"),
                  command=self.archive_plan).pack(side='left', padx=3)
        ttk.Button(btn_frame, text=_t("ai_study.study_plans.delete_plan", default="Delete Plan"),
                  command=self.delete_plan).pack(side='left', padx=3)

        # Plans treeview
        columns = (
            _t("ai_study.study_plans.plan_id", default="Plan ID"),
            _t("ai_study.study_plans.course", default="Course"),
            _t("ai_study.study_plans.exam_date_col", default="Exam Date"),
            _t("ai_study.study_plans.total_hours", default="Total Hours"),
            _t("ai_study.study_plans.status", default="Status"),
            _t("ai_study.study_plans.name", default="Name"),
            _t("ai_study.study_plans.progress", default="Progress"),
        )
        self.plans_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)

        for col in columns:
            self.plans_tree.heading(col, text=col)
            self.plans_tree.column(col, width=130)

        self.plans_tree.pack(fill='both', expand=True)
        self.plans_tree.bind('<Double-1>', lambda e: self.view_plan_tasks())

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

        # Module (optional)
        ttk.Label(create_frame, text=_t("ai_study.flashcards.module", default="Module (optional):")).grid(row=0, column=2, sticky='w', pady=5, padx=(15, 0))
        self.card_module_var = tk.StringVar()
        self.card_module_combo = ttk.Combobox(create_frame, textvariable=self.card_module_var, width=26, state='readonly')
        self.card_module_combo.grid(row=0, column=3, pady=5, padx=5)
        self.card_module_combo['values'] = self._module_choices()
        if self.card_module_combo['values']:
            self.card_module_combo.current(0)

        # Create button
        ttk.Button(create_frame, text=_t("ai_study.flashcards.create_button", default="Create Flashcard"),
                  command=self.create_flashcard).grid(row=3, column=0, columnspan=2, pady=10)
        ttk.Button(create_frame, text=_t("ai_study.flashcards.generate_button", default="✨ Generate from Notes…"),
                  command=self.generate_flashcards_dialog).grid(row=3, column=2, columnspan=2, pady=10)

        # Review section
        review_frame = ttk.LabelFrame(self.flashcards_frame, text=_t("ai_study.flashcards.review_section", default="Review Flashcards"), padding=10)
        review_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Decks list
        ttk.Label(review_frame, text=_t("ai_study.flashcards.select_deck", default="Select Deck:")).pack(anchor='w')
        self.deck_listbox = tk.Listbox(review_frame, height=8)
        self.deck_listbox.pack(fill='x', pady=5)
        self.deck_names = []

        ttk.Button(review_frame, text=_t("ai_study.flashcards.start_review", default="Start Review Session"),
                  command=self.start_review_session).pack(pady=5)

        ttk.Button(review_frame, text=_t("ai_study.flashcards.refresh_decks", default="Refresh Decks"),
                  command=self.load_flashcard_decks).pack(pady=5)

        manage = ttk.Frame(review_frame)
        manage.pack(pady=5)
        ttk.Button(manage, text=_t("ai_study.flashcards.manage_cards", default="Manage Cards…"),
                   command=self.manage_cards).pack(side='left', padx=4)
        ttk.Button(manage, text=_t("ai_study.flashcards.rename_deck", default="Rename Deck"),
                   command=self.rename_deck).pack(side='left', padx=4)
        ttk.Button(manage, text=_t("ai_study.flashcards.delete_deck", default="Delete Deck"),
                   command=self.delete_deck).pack(side='left', padx=4)

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

        # Module (optional) — grounds the explanation in the module's records
        ttk.Label(input_frame, text=_t("ai_study.concept_explainer.module", default="Module (optional):")).grid(row=0, column=2, sticky='w', pady=5, padx=(15, 0))
        self.explain_module_var = tk.StringVar()
        self.explain_module_combo = ttk.Combobox(input_frame, textvariable=self.explain_module_var, width=26, state='readonly')
        self.explain_module_combo.grid(row=0, column=3, pady=5, padx=5)
        self.explain_module_combo['values'] = self._module_choices()
        if self.explain_module_combo['values']:
            self.explain_module_combo.current(0)

        # Explain button
        self.explain_button = ttk.Button(input_frame, text=_t("ai_study.concept_explainer.explain_button", default="Explain Concept"),
                  command=self.explain_concept)
        self.explain_button.grid(row=2, column=0, columnspan=2, pady=10)

        # Explanation section
        output_frame = ttk.LabelFrame(self.explainer_frame, text=_t("ai_study.concept_explainer.output_section", default="Explanation"), padding=10)
        output_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.explanation_source_var = tk.StringVar()
        ttk.Label(output_frame, textvariable=self.explanation_source_var, foreground='gray').pack(anchor='w')

        # Rating section (packed before the text so it stays visible)
        rating_frame = ttk.Frame(output_frame)
        rating_frame.pack(side='bottom', fill='x', pady=5)

        self.explanation_text = scrolledtext.ScrolledText(output_frame, height=20, wrap='word')
        self.explanation_text.pack(fill='both', expand=True)

        ttk.Label(rating_frame, text=_t("ai_study.concept_explainer.rate_explanation", default="Rate this explanation:")).pack(side='left')
        self.rating_var = tk.IntVar(value=3)
        for i in range(1, 6):
            ttk.Radiobutton(rating_frame, text=str(i), variable=self.rating_var,
                          value=i).pack(side='left', padx=5)

        ttk.Button(rating_frame, text=_t("ai_study.concept_explainer.submit_rating", default="Submit Rating"),
                  command=self.rate_current_explanation).pack(side='left', padx=15)
        ttk.Button(rating_frame, text=_t("ai_study.concept_explainer.history_button", default="Explanation History"),
                  command=self.show_explanation_history).pack(side='left', padx=5)
        ttk.Button(rating_frame, text=_t("ai_study.concept_explainer.make_flashcards", default="Make Flashcards"),
                  command=self.flashcards_from_current_explanation).pack(side='left', padx=5)

    def setup_analytics_tab(self):
        """Set up analytics tab."""
        # Analytics display
        analytics_frame = ttk.LabelFrame(self.analytics_frame, text=_t("ai_study.analytics.section_title", default="Study Analytics"), padding=10)
        analytics_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Button(analytics_frame, text=_t("ai_study.analytics.refresh_button", default="Refresh Analytics"),
                  command=self.load_analytics).pack(side='bottom', pady=10)

        self.analytics_text = scrolledtext.ScrolledText(analytics_frame, height=25, wrap='word')
        self.analytics_text.pack(fill='both', expand=True)

        # Load analytics
        self.load_analytics()

    def setup_week_tab(self):
        """Today's work and the next four weeks' exams and deadlines."""
        frame = ttk.LabelFrame(self.week_frame, text=_t("ai_study.week.section_title", default="Today and the Weeks Ahead"), padding=10)
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        buttons = ttk.Frame(frame)
        buttons.pack(side='bottom', fill='x', pady=5)
        ttk.Button(buttons, text=_t("ai_study.week.refresh", default="Refresh"),
                   command=self.load_week).pack(side='left', padx=5)
        ttk.Button(buttons, text=_t("ai_study.week.review_due", default="Review Due Cards"),
                   command=self.review_all_due).pack(side='left', padx=5)
        self.week_text = scrolledtext.ScrolledText(frame, height=25, wrap='word')
        self.week_text.pack(fill='both', expand=True)
        self.load_week()

    def setup_settings_tab(self):
        """Reminder and sharing choices."""
        frame = ttk.LabelFrame(self.settings_frame, text=_t("ai_study.settings.section_title", default="Reminders and Sharing"), padding=15)
        frame.pack(fill='x', padx=10, pady=10)
        prefs = self.service.get_settings(self.owner) if self.owner else {}
        self.pref_reminders = tk.BooleanVar(value=bool(prefs.get('reminders_enabled', 1)))
        self.pref_email = tk.BooleanVar(value=bool(prefs.get('email_reminders', 0)))
        self.pref_share = tk.BooleanVar(value=bool(prefs.get('share_with_tutor', 1)))
        ttk.Checkbutton(frame, text=_t("ai_study.settings.reminders", default="Send me a daily reminder in my Hub inbox when cards or tasks are due"),
                        variable=self.pref_reminders).pack(anchor='w', pady=3)
        ttk.Checkbutton(frame, text=_t("ai_study.settings.email", default="Also email the reminder to me"),
                        variable=self.pref_email).pack(anchor='w', pady=3)
        ttk.Checkbutton(frame, text=_t("ai_study.settings.share", default="Let my tutors and module staff see my study activity (not my cards or explanations)"),
                        variable=self.pref_share).pack(anchor='w', pady=3)
        row = ttk.Frame(frame)
        row.pack(anchor='w', pady=6)
        ttk.Label(row, text=_t("ai_study.settings.card_limit", default="Cards per review session:")).pack(side='left')
        self.pref_limit = ttk.Spinbox(row, from_=5, to=200, width=6)
        self.pref_limit.set(prefs.get('daily_card_limit', 20))
        self.pref_limit.pack(side='left', padx=5)
        ttk.Button(frame, text=_t("ai_study.settings.save", default="Save Settings"),
                   command=self.save_settings).pack(anchor='w', pady=10)

    def setup_staff_tab(self):
        """Companion activity for the students this member of staff teaches."""
        top = ttk.Frame(self.staff_frame, padding=10)
        top.pack(fill='x')
        ttk.Label(top, text=_t("ai_study.staff.module", default="Module (optional):")).pack(side='left')
        self.staff_module_var = tk.StringVar()
        self.staff_module_combo = ttk.Combobox(top, textvariable=self.staff_module_var, width=28, state='readonly')
        self.staff_module_combo['values'] = self._module_choices()
        if self.staff_module_combo['values']:
            self.staff_module_combo.current(0)
        self.staff_module_combo.pack(side='left', padx=5)
        ttk.Button(top, text=_t("ai_study.staff.refresh", default="Refresh"),
                   command=self.load_staff_overview).pack(side='left', padx=5)
        ttk.Button(top, text=_t("ai_study.staff.details", default="Student Details"),
                   command=self.show_staff_student).pack(side='left', padx=5)
        ttk.Button(top, text=_t("ai_study.staff.send_reminders", default="Send Reminders Now"),
                   command=self.send_all_reminders).pack(side='left', padx=5)
        ttk.Button(top, text=_t("ai_study.staff.engagement_scan", default="Check Plan Slippage"),
                   command=self.run_engagement_scan).pack(side='left', padx=5)
        columns = ("Student", "Name", "Shared", "Active plans", "Done (14d)", "Missed (14d)",
                   "Completion", "Cards (14d)", "Recall", "Last active")
        self.staff_tree = ttk.Treeview(self.staff_frame, columns=columns, show='headings', height=16)
        for col in columns:
            self.staff_tree.heading(col, text=col)
            self.staff_tree.column(col, width=95)
        self.staff_tree.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        self.staff_tree.bind('<Double-1>', lambda e: self.show_staff_student())
        self.load_staff_overview()

    # Helper methods

    def _module_choices(self):
        none_option = _t("ai_study.study_plans.none_general", default="None (General Study)")
        try:
            modules = self.service.available_modules(self.owner, all_active=self.is_staff)
        except Exception:
            logger.debug("Could not load modules", exc_info=True)
            modules = []
        return [none_option] + [f"{m['module_code']} - {m['module_name']}" for m in modules]

    @staticmethod
    def _code_from(selection):
        none_option = _t("ai_study.study_plans.none_general", default="None (General Study)")
        if not selection or selection == none_option:
            return None
        return selection.split(' - ')[0].strip()

    def _load_available_modules(self):
        """Load available modules: staff see every active module, students
        the modules they are enrolled on."""
        try:
            self.course_id_combo['values'] = self._module_choices()
            if self.course_id_combo['values']:
                self.course_id_combo.current(0)
        except Exception as e:
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"),
                               _t("ai_study.errors.load_modules_failed", default="Failed to load modules: {error}").format(error=str(e)))

    def _on_module_selected(self, event=None):
        """Auto-fill the exam date from the published exam timetable."""
        module_code = self._code_from(self.course_id_var.get())
        self.exam_info_var.set("")

        # Clear exam date if "None (General Study)" is selected
        if not module_code:
            self.exam_date_entry.delete(0, tk.END)
            return

        exam_date = None
        try:
            exam = self.service.exam_for_module(self.owner, module_code)
            if exam:
                exam_date = exam['date']
                self.exam_info_var.set(f"{exam['name']} {exam.get('start_time') or ''}"
                                       + (f", {exam['room']}" if exam.get('room') else ""))
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        if not exam_date:
            # Fall back to an exam on the academic calendar named for the module.
            from education_system.systems.university.infrastructure.database.db import get_connection
            try:
                with get_connection() as conn:
                    exam_event = conn.execute("""
                        SELECT start_datetime AS date_start, event_date AS date FROM unified_events
                        WHERE source_type = 'academic_calendar' AND event_type = 'Exam'
                        AND (title LIKE ? OR title LIKE ?) AND event_date >= ?
                        ORDER BY event_date LIMIT 1
                    """, (f"%{escape_like(module_code)}%", f"%Exam: {escape_like(module_code)}%",
                          date.today().isoformat())).fetchone()
                if exam_event:
                    exam_date = str(exam_event['date_start'] or exam_event['date']).split(' ')[0]
            except Exception:
                # Silently fail - user can still enter date manually
                logger.debug("Suppressed exception", exc_info=True)

        self.exam_date_entry.delete(0, tk.END)
        if exam_date:
            self.exam_date_entry.insert(0, exam_date)
            self.exam_date_entry.config(foreground='green')
            self.window.after(2000, lambda: self.exam_date_entry.config(foreground='black'))
        else:
            self.exam_info_var.set(_t("ai_study.study_plans.no_published_exam", default="No published exam found — enter the date"))

    def _selected_plan_id(self):
        selection = self.plans_tree.selection()
        if not selection:
            messagebox.showwarning(_t("ai_study.messages.warning", default="Warning"),
                                 _t("ai_study.study_plans.select_plan_warning", default="Please select a study plan"))
            return None
        return int(self.plans_tree.item(selection[0])['values'][0])

    # Event handlers

    def generate_plan(self):
        """Generate a new study plan."""
        if not self.auth.current_user:
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"),
                               _t("ai_study.auth.please_login", default="Please login first"))
            return

        course_id = self._code_from(self.course_id_var.get())
        exam_date = self.exam_date_entry.get().strip()
        try:
            hours = float(self.hours_per_day.get())
        except ValueError:
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"),
                                 _t("ai_study.study_plans.bad_hours", default="Hours per day must be a number"))
            return

        if not exam_date:
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"),
                               _t("ai_study.study_plans.no_exam_date", default="Please enter exam date"))
            return

        try:
            result = self.service.generate_study_plan(self.owner, course_id, exam_date, hours)
            message = _t("ai_study.study_plans.success_message",
                         default="Study plan created!\nPlan ID: {plan_id}\nDays until exam: {days_until_exam}\nTasks generated: {tasks_generated}").format(
                             plan_id=result['plan_id'],
                             days_until_exam=result['days_until_exam'],
                             tasks_generated=result['tasks_generated'])
            if result.get('warnings'):
                message += "\n\n" + "\n".join(f"• {w}" for w in result['warnings'])
            messagebox.showinfo(_t("ai_study.messages.success", default="Success"), message)
            self.load_study_plans()
            self.load_week()

            # Clear entries
            self.course_id_combo.current(0)
            self.exam_date_entry.delete(0, tk.END)
            self.exam_info_var.set("")
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

        plans = self.service.get_student_study_plans(self.owner)

        for plan in plans:
            total = plan.get('task_count') or 0
            done = plan.get('done_count') or 0
            self.plans_tree.insert('', 'end', values=(
                plan.get('plan_id', 0),
                plan.get('course_id') or _t("ai_study.columns.n_a", default="N/A"),
                plan.get('end_date', _t("ai_study.columns.n_a", default="N/A")),
                plan.get('total_hours', 0) or 0,
                plan.get('status') or _t("ai_study.columns.unknown", default="Unknown"),
                plan.get('plan_name') or '',
                f"{done}/{total}" if total else "0/0",
            ))

    def view_plan_tasks(self):
        """View and manage the tasks of the selected plan."""
        plan_id = self._selected_plan_id()
        if plan_id is None:
            return

        plan_data = self.service.get_study_plan(plan_id)
        if not plan_data:
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"),
                               _t("ai_study.study_plans.plan_not_found", default="Plan not found"))
            return

        # Create tasks window
        tasks_window = tk.Toplevel(self.window)
        tasks_window.title(f"{_t('ai_study.window.tasks_title', default='Study Plan Tasks - Plan #')}{plan_id}")
        tasks_window.geometry("1000x560")

        progress_var = tk.StringVar()
        ttk.Label(tasks_window, textvariable=progress_var, font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 0))

        btns = ttk.Frame(tasks_window)
        btns.pack(side='bottom', fill='x', padx=10, pady=8)

        # Tasks tree
        columns = (
            _t("ai_study.tasks.task", default="Task"),
            _t("ai_study.tasks.date", default="Date"),
            _t("ai_study.tasks.duration", default="Duration"),
            _t("ai_study.tasks.priority", default="Priority"),
            _t("ai_study.tasks.status", default="Status"),
            _t("ai_study.tasks.module", default="Module"),
        )
        tree = ttk.Treeview(tasks_window, columns=columns, show='headings')

        for col in columns:
            tree.heading(col, text=col)
        tree.column(columns[0], width=360)

        tree.pack(fill='both', expand=True, padx=10, pady=10)
        detail = ttk.Label(tasks_window, text="", wraplength=950, foreground='gray')
        detail.pack(side='bottom', fill='x', padx=10)
        by_item = {}
        today = date.today().isoformat()

        def fill():
            data = self.service.get_study_plan(plan_id)
            for item in tree.get_children():
                tree.delete(item)
            by_item.clear()
            p = data['progress']
            progress_var.set(f"{data['plan']['plan_name']} — {p['done']}/{p['total']} done "
                             f"({p['percent']:.0f}%), {p['overdue']} missed · "
                             f"{data['plan'].get('status') or 'Active'}")
            for task in data['tasks']:
                state = task.get('status') or ('done' if task.get('completed') else 'pending')
                if state == 'done':
                    status = _t("ai_study.tasks.completed", default="Completed")
                elif state == 'skipped':
                    status = _t("ai_study.tasks.skipped", default="Skipped")
                elif str(task.get('scheduled_date'))[:10] < today:
                    status = _t("ai_study.tasks.missed", default="Missed")
                else:
                    status = _t("ai_study.tasks.pending", default="Pending")
                duration = task.get('duration_minutes', 0) or 0
                iid = tree.insert('', 'end', values=(
                    task.get('task_title', _t("ai_study.tasks.untitled", default="Untitled")),
                    task.get('scheduled_date', _t("ai_study.columns.n_a", default="N/A")),
                    f"{duration}{_t('ai_study.tasks.minutes_suffix', default=' min')}",
                    task.get('priority', _t("ai_study.tasks.normal_priority", default="Normal")),
                    status,
                    task.get('module_code') or '',
                ))
                by_item[iid] = task

        def on_select(event=None):
            sel = tree.selection()
            if sel:
                t = by_item[sel[0]]
                detail.config(text=(t.get('task_description') or '') +
                              (f"\nNotes: {t['notes']}" if t.get('notes') else ''))

        tree.bind('<<TreeviewSelect>>', on_select)

        def selected():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning(_t("ai_study.messages.warning", default="Warning"),
                                       _t("ai_study.study_plans.select_task", default="Please select a task."),
                                       parent=tasks_window)
                return None
            return by_item[sel[0]]

        def act(fn, *args):
            task = selected()
            if not task:
                return
            try:
                fn(task['task_id'], *args)
            except Exception as e:
                messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"), str(e),
                                     parent=tasks_window)
            fill()
            self.load_study_plans()

        def complete():
            act(lambda tid: self.service.complete_study_task(tid, student_id=self.owner))

        def undo():
            act(lambda tid: self.service.uncomplete_task(tid, self.owner))

        def skip():
            act(lambda tid: self.service.skip_task(tid, self.owner))

        def move():
            task = selected()
            if not task:
                return
            new = simpledialog.askstring(_t("ai_study.tasks.reschedule", default="Reschedule"),
                                         _t("ai_study.tasks.new_date", default="New date (YYYY-MM-DD):"),
                                         initialvalue=task.get('scheduled_date'), parent=tasks_window)
            if new:
                act(lambda tid: self.service.reschedule_task(tid, new, self.owner))

        def edit():
            task = selected()
            if task:
                self._task_dialog(tasks_window, plan_id, task, fill)

        def add():
            self._task_dialog(tasks_window, plan_id, None, fill)

        def remove():
            task = selected()
            if task and messagebox.askyesno(_t("ai_study.tasks.delete", default="Delete task"),
                                            _t("ai_study.tasks.confirm_delete", default="Delete this task?"),
                                            parent=tasks_window):
                act(lambda tid: self.service.delete_task(tid, self.owner))

        for label, key, command in (
                ("Mark Complete", "ai_study.study_plans.mark_complete", complete),
                ("Undo Complete", "ai_study.tasks.undo", undo),
                ("Skip", "ai_study.tasks.skip", skip),
                ("Reschedule…", "ai_study.tasks.reschedule_button", move),
                ("Edit…", "ai_study.tasks.edit", edit),
                ("Add Task…", "ai_study.tasks.add", add),
                ("Delete", "ai_study.tasks.delete_button", remove)):
            ttk.Button(btns, text=_t(key, default=label), command=command).pack(side='left', padx=3)
        ttk.Button(btns, text=_t("ai_study.buttons.close", default="Close"),
                   command=tasks_window.destroy).pack(side='right', padx=3)
        fill()

    def _task_dialog(self, parent, plan_id, task, refresh):
        """Add a task to a plan, or edit one."""
        dlg = tk.Toplevel(parent)
        dlg.title(_t("ai_study.tasks.edit_title", default="Edit Task") if task else _t("ai_study.tasks.add_title", default="Add Task"))
        dlg.transient(parent)
        fields = {}
        rows = (("title", "Title", task.get('task_title') if task else ""),
                ("date", "Date (YYYY-MM-DD)", task.get('scheduled_date') if task else date.today().isoformat()),
                ("minutes", "Minutes", task.get('duration_minutes') if task else 60),
                ("description", "Description", (task.get('task_description') or "") if task else ""),
                ("notes", "Notes", (task.get('notes') or "") if task else ""))
        for r, (key, label, value) in enumerate(rows):
            ttk.Label(dlg, text=label + ":").grid(row=r, column=0, sticky='w', padx=8, pady=4)
            entry = ttk.Entry(dlg, width=55)
            entry.insert(0, str(value or ""))
            entry.grid(row=r, column=1, padx=8, pady=4)
            fields[key] = entry
        ttk.Label(dlg, text="Priority:").grid(row=len(rows), column=0, sticky='w', padx=8, pady=4)
        priority = ttk.Combobox(dlg, values=("Low", "Medium", "High"), state='readonly', width=12)
        priority.set((task.get('priority') if task else None) or "Medium")
        priority.grid(row=len(rows), column=1, sticky='w', padx=8, pady=4)

        def save():
            try:
                minutes = int(fields['minutes'].get())
                if task:
                    self.service.update_task(task['task_id'], self.owner,
                                             title=fields['title'].get(),
                                             scheduled_date=fields['date'].get(),
                                             duration_minutes=minutes, priority=priority.get(),
                                             description=fields['description'].get(),
                                             notes=fields['notes'].get())
                else:
                    self.service.add_task(plan_id, fields['title'].get(), fields['date'].get(),
                                          minutes, priority.get(), fields['description'].get(),
                                          student_id=self.owner)
            except Exception as e:
                messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"), str(e), parent=dlg)
                return
            dlg.destroy()
            refresh()
            self.load_study_plans()

        bar = ttk.Frame(dlg)
        bar.grid(row=len(rows) + 1, column=0, columnspan=2, pady=10)
        ttk.Button(bar, text=_t("ai_study.buttons.save", default="Save"), command=save).pack(side='left', padx=5)
        ttk.Button(bar, text=_t("ai_study.buttons.cancel", default="Cancel"), command=dlg.destroy).pack(side='left', padx=5)

    def edit_plan(self):
        plan_id = self._selected_plan_id()
        if plan_id is None:
            return
        plan = self.service.get_study_plan(plan_id)['plan']
        dlg = tk.Toplevel(self.window)
        dlg.title(_t("ai_study.study_plans.edit_plan", default="Edit Plan"))
        dlg.transient(self.window)
        entries = {}
        for r, (key, label, value) in enumerate((
                ("name", "Name", plan.get('plan_name')),
                ("exam", "Exam date (YYYY-MM-DD)", plan.get('end_date')),
                ("notes", "Notes", plan.get('notes') or ""))):
            ttk.Label(dlg, text=label + ":").grid(row=r, column=0, sticky='w', padx=8, pady=4)
            e = ttk.Entry(dlg, width=50)
            e.insert(0, str(value or ""))
            e.grid(row=r, column=1, padx=8, pady=4)
            entries[key] = e

        def save():
            try:
                exam = entries['exam'].get().strip()
                result = self.service.update_plan(
                    plan_id, self.owner, plan_name=entries['name'].get(),
                    exam_date=exam if exam != plan.get('end_date') else None,
                    notes=entries['notes'].get())
            except Exception as e:
                messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"), str(e), parent=dlg)
                return
            dlg.destroy()
            if result.get('tasks_skipped'):
                messagebox.showinfo(_t("ai_study.messages.info", default="Info"),
                                    f"{result['tasks_skipped']} task(s) after the new exam date were skipped.")
            self.load_study_plans()

        ttk.Button(dlg, text=_t("ai_study.buttons.save", default="Save"), command=save).grid(row=3, column=0, columnspan=2, pady=10)

    def reschedule_missed(self):
        plan_id = self._selected_plan_id()
        if plan_id is None:
            return
        try:
            result = self.service.reschedule_missed(plan_id, self.owner)
        except Exception as e:
            self._error(e)
            return
        messagebox.showinfo(_t("ai_study.messages.info", default="Info"),
                            _t("ai_study.study_plans.rescheduled", default="Moved {moved} missed task(s) onto the days before your exam; {skipped} could not fit.").format(**result))
        self.load_study_plans()
        self.load_week()

    def toggle_pause_plan(self):
        plan_id = self._selected_plan_id()
        if plan_id is None:
            return
        status = self.service.get_study_plan(plan_id)['plan'].get('status') or 'Active'
        try:
            self.service.set_plan_status(plan_id, 'Active' if status == 'Paused' else 'Paused', self.owner)
        except Exception as e:
            self._error(e)
        self.load_study_plans()

    def archive_plan(self):
        plan_id = self._selected_plan_id()
        if plan_id is None:
            return
        try:
            self.service.set_plan_status(plan_id, 'Archived', self.owner)
        except Exception as e:
            self._error(e)
        self.load_study_plans()

    def delete_plan(self):
        plan_id = self._selected_plan_id()
        if plan_id is None:
            return
        if not messagebox.askyesno(_t("ai_study.study_plans.delete_plan", default="Delete Plan"),
                                   _t("ai_study.study_plans.confirm_delete", default="Delete this plan and all its tasks? Study time you have already logged is kept.")):
            return
        try:
            self.service.delete_plan(plan_id, self.owner)
        except Exception as e:
            self._error(e)
        self.load_study_plans()
        self.load_week()

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
            flashcard_id = self.service.create_flashcard(self.owner, self._code_from(self.card_module_var.get()),
                                                        deck_name, question, answer)
            messagebox.showinfo(_t("ai_study.messages.success", default="Success"),
                              _t("ai_study.flashcards.success_message", default="Flashcard created! ID: {flashcard_id}").format(flashcard_id=flashcard_id))

            # Clear entries
            self.question_entry.delete(0, tk.END)
            self.answer_entry.delete(0, tk.END)
            self.load_flashcard_decks()
        except Exception as e:
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"),
                               _t("ai_study.flashcards.creation_failed", default="Failed to create flashcard: {error}").format(error=str(e)))

    def generate_flashcards_dialog(self):
        """Paste notes; Claude (or the definitions in them) writes the cards."""
        dlg = tk.Toplevel(self.window)
        dlg.title(_t("ai_study.flashcards.generate_title", default="Generate Flashcards from Notes"))
        dlg.geometry("720x560")
        top = ttk.Frame(dlg, padding=8)
        top.pack(fill='x')
        ttk.Label(top, text=_t("ai_study.flashcards.deck_name", default="Deck Name:")).pack(side='left')
        deck = ttk.Entry(top, width=28)
        deck.insert(0, self.deck_name_entry.get().strip())
        deck.pack(side='left', padx=5)
        ttk.Label(top, text=_t("ai_study.flashcards.how_many", default="Cards:")).pack(side='left', padx=(10, 0))
        count = ttk.Spinbox(top, from_=1, to=40, width=5)
        count.set(10)
        count.pack(side='left', padx=5)
        ttk.Label(dlg, text=_t("ai_study.flashcards.paste_notes", default="Paste your notes:")).pack(anchor='w', padx=8)
        bar = ttk.Frame(dlg, padding=8)
        bar.pack(side='bottom', fill='x')
        notes = scrolledtext.ScrolledText(dlg, wrap='word', height=20)
        notes.pack(fill='both', expand=True, padx=8)
        state = tk.StringVar()
        ttk.Label(bar, textvariable=state, foreground='gray').pack(side='left')
        module = self._code_from(self.card_module_var.get())

        def go():
            name = deck.get().strip()
            text = notes.get(1.0, tk.END).strip()
            if not name or not text:
                messagebox.showwarning(_t("ai_study.messages.warning", default="Warning"),
                                       _t("ai_study.flashcards.need_deck_and_notes", default="Give a deck name and paste some notes."), parent=dlg)
                return
            button.config(state='disabled')
            state.set(_t("ai_study.flashcards.generating", default="Writing cards…"))

            def done(result, error):
                try:
                    button.config(state='normal')
                    state.set("")
                except tk.TclError:
                    return
                if error:
                    self._error(error)
                    return
                if not result['created']:
                    messagebox.showinfo(_t("ai_study.messages.info", default="Info"),
                                        _t("ai_study.flashcards.none_found", default="No cards could be made from those notes. Without AI, cards come from lines like 'Term: definition' or 'X is a …'."), parent=dlg)
                    return
                messagebox.showinfo(_t("ai_study.messages.success", default="Success"),
                                    f"{len(result['created'])} card(s) added to '{name}'.\n"
                                    f"{_SOURCE_LABELS.get(result['source'], '')}", parent=dlg)
                dlg.destroy()
                self.load_flashcard_decks()

            self._background(lambda: self.service.generate_flashcards(
                self.owner, module, name, text, int(count.get())), done)

        button = ttk.Button(bar, text=_t("ai_study.flashcards.generate", default="Generate"), command=go)
        button.pack(side='right', padx=5)

    def load_flashcard_decks(self):
        """Load flashcard decks."""
        if not self.auth.current_user:
            return

        self.deck_listbox.delete(0, tk.END)
        self.deck_names = []

        decks = self.service.get_flashcard_decks(self.owner)

        for deck in decks:
            accuracy = deck.get('accuracy', 0) or 0
            total_cards = deck.get('total_cards', 0) or 0
            due_count = deck.get('due_count', 0) or 0
            deck_name = deck.get('deck_name', _t("ai_study.columns.unknown", default="Unknown"))
            self.deck_names.append(deck_name)
            self.deck_listbox.insert(tk.END,
                _t("ai_study.flashcards.deck_info",
                   default="{deck_name} - {total_cards} cards, {due_count} due, {accuracy}% accuracy").format(
                    deck_name=deck_name,
                    total_cards=total_cards,
                    due_count=due_count,
                    accuracy=f"{accuracy:.1f}"
                ))

    def _selected_deck(self):
        selection = self.deck_listbox.curselection()
        if not selection:
            messagebox.showwarning(_t("ai_study.messages.warning", default="Warning"),
                                 _t("ai_study.flashcards.select_deck_warning", default="Please select a deck"))
            return None
        return self.deck_names[selection[0]]

    def start_review_session(self):
        """Start a flashcard review session."""
        deck_name = self._selected_deck()
        if deck_name is None:
            return

        flashcards = self.service.get_due_flashcards(self.owner, deck_name)

        if not flashcards:
            messagebox.showinfo(_t("ai_study.messages.info", default="Info"),
                              _t("ai_study.flashcards.no_cards_due", default="No flashcards due for review!"))
            return

        # Create review window
        self._show_review_window(flashcards)

    def review_all_due(self):
        flashcards = self.service.get_due_flashcards(self.owner)
        if not flashcards:
            messagebox.showinfo(_t("ai_study.messages.info", default="Info"),
                                _t("ai_study.flashcards.no_cards_due", default="No flashcards due for review!"))
            return
        self._show_review_window(flashcards)

    def _show_review_window(self, flashcards):
        """Show flashcard review window."""
        review_window = tk.Toplevel(self.window)
        review_window.title(_t("ai_study.flashcards.review_window_title", default="Flashcard Review"))
        review_window.geometry("680x460")

        current_index = [0]  # Use list to allow modification in nested function
        show_answer = [False]
        last_wrong = [None]

        counter_label = ttk.Label(review_window, text="", foreground='gray')
        counter_label.pack(pady=(10, 0))

        question_label = ttk.Label(review_window, text="", font=('Arial', 14), wraplength=620)
        question_label.pack(pady=20)

        answer_label = ttk.Label(review_window, text="", font=('Arial', 12), wraplength=620)
        answer_label.pack(pady=20)

        def show_card():
            """Display current flashcard."""
            if current_index[0] >= len(flashcards):
                messagebox.showinfo(_t("ai_study.messages.complete", default="Complete"),
                                  _t("ai_study.flashcards.review_complete", default="Review session complete!"))
                review_window.destroy()
                self.load_flashcard_decks()
                return

            card = flashcards[current_index[0]]
            counter_label.config(text=f"{current_index[0] + 1} / {len(flashcards)} · {card.get('deck_name', '')}")
            question_label.config(text=_t("ai_study.flashcards.question_label", default="Question:\n{question}").format(question=card['question']))

            if show_answer[0]:
                answer_label.config(text=_t("ai_study.flashcards.answer_label", default="Answer:\n{answer}").format(answer=card['answer']))
            else:
                answer_label.config(text=_t("ai_study.flashcards.show_answer_prompt", default="Click 'Show Answer' to reveal"))

        def toggle_answer():
            """Toggle answer visibility."""
            show_answer[0] = not show_answer[0]
            show_card()

        def grade(quality):
            card = flashcards[current_index[0]]
            try:
                result = self.service.review_flashcard(card['flashcard_id'], quality=quality,
                                                       student_id=self.owner)
            except Exception as e:
                self._error(e)
                return
            last_wrong[0] = None if result['correct'] else card
            mistake_button.config(state='normal' if last_wrong[0] else 'disabled')
            current_index[0] += 1
            show_answer[0] = False
            show_card()

        def mark_correct():
            """Mark flashcard as correct."""
            grade('good')

        def mark_incorrect():
            """Mark flashcard as incorrect."""
            grade('again')

        def card_from_mistake():
            card = last_wrong[0]
            if not card:
                return
            given = simpledialog.askstring(
                _t("ai_study.flashcards.from_mistake", default="Card from Mistake"),
                _t("ai_study.flashcards.what_did_you_answer", default="What did you answer? (optional — leave blank for a reversed card)"),
                parent=review_window)

            def done(result, error):
                if error:
                    self._error(error)
                    return
                mistake_button.config(state='disabled')
                messagebox.showinfo(_t("ai_study.messages.success", default="Success"),
                                    _t("ai_study.flashcards.mistake_card_added", default="A follow-up card was added to this deck."),
                                    parent=review_window)

            self._background(lambda: self.service.card_from_mistake(card['flashcard_id'], given, self.owner), done)

        # Buttons
        btn_frame = ttk.Frame(review_window)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text=_t("ai_study.flashcards.show_answer_button", default="Show Answer"),
                  command=toggle_answer).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t("ai_study.flashcards.correct_button", default="✓ Correct"),
                  command=mark_correct).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t("ai_study.flashcards.incorrect_button", default="✗ Incorrect"),
                  command=mark_incorrect).pack(side='left', padx=5)

        grade_frame = ttk.Frame(review_window)
        grade_frame.pack(pady=5)
        ttk.Label(grade_frame, text=_t("ai_study.flashcards.or_grade", default="Or grade it:")).pack(side='left', padx=5)
        ttk.Button(grade_frame, text=_t("ai_study.flashcards.hard_button", default="Hard"),
                   command=lambda: grade('hard')).pack(side='left', padx=5)
        ttk.Button(grade_frame, text=_t("ai_study.flashcards.easy_button", default="Easy"),
                   command=lambda: grade('easy')).pack(side='left', padx=5)
        mistake_button = ttk.Button(grade_frame, text=_t("ai_study.flashcards.from_mistake_button", default="Make Card from Last Mistake"),
                                    command=card_from_mistake, state='disabled')
        mistake_button.pack(side='left', padx=15)

        show_card()

    def manage_cards(self):
        """Edit, suspend or delete the cards in the selected deck."""
        deck_name = self._selected_deck()
        if deck_name is None:
            return
        win = tk.Toplevel(self.window)
        win.title(f"{_t('ai_study.flashcards.manage_title', default='Cards in ')}{deck_name}")
        win.geometry("900x500")
        bar = ttk.Frame(win)
        bar.pack(side='bottom', fill='x', padx=10, pady=8)
        columns = ("Question", "Answer", "Next review", "Interval", "Reviews", "Status", "Source")
        tree = ttk.Treeview(win, columns=columns, show='headings')
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=90)
        tree.column("Question", width=250)
        tree.column("Answer", width=250)
        tree.pack(fill='both', expand=True, padx=10, pady=10)
        by_item = {}

        def fill():
            for item in tree.get_children():
                tree.delete(item)
            by_item.clear()
            for card in self.service.list_flashcards(self.owner, deck_name):
                iid = tree.insert('', 'end', values=(
                    card['question'], card['answer'], card.get('next_review') or '',
                    f"{card.get('interval_days') or 0} d", card.get('review_count') or 0,
                    "Suspended" if card.get('suspended') else "Active", card.get('source') or 'manual'))
                by_item[iid] = card

        def selected():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning(_t("ai_study.messages.warning", default="Warning"),
                                       _t("ai_study.flashcards.select_card", default="Select a card."), parent=win)
                return None
            return by_item[sel[0]]

        def edit():
            card = selected()
            if not card:
                return
            q = simpledialog.askstring("Question", "Question:", initialvalue=card['question'], parent=win)
            if q is None:
                return
            a = simpledialog.askstring("Answer", "Answer:", initialvalue=card['answer'], parent=win)
            if a is None:
                return
            try:
                self.service.update_flashcard(card['flashcard_id'], self.owner, question=q, answer=a)
            except Exception as e:
                self._error(e)
            fill()

        def suspend():
            card = selected()
            if card:
                self.service.set_flashcard_suspended(card['flashcard_id'], not card.get('suspended'), self.owner)
                fill()

        def remove():
            card = selected()
            if card and messagebox.askyesno("Delete card", "Delete this card and its review history?", parent=win):
                self.service.delete_flashcard(card['flashcard_id'], self.owner)
                fill()

        ttk.Button(bar, text=_t("ai_study.flashcards.edit_card", default="Edit…"), command=edit).pack(side='left', padx=3)
        ttk.Button(bar, text=_t("ai_study.flashcards.suspend_card", default="Suspend / Unsuspend"), command=suspend).pack(side='left', padx=3)
        ttk.Button(bar, text=_t("ai_study.flashcards.delete_card", default="Delete"), command=remove).pack(side='left', padx=3)
        ttk.Button(bar, text=_t("ai_study.buttons.close", default="Close"),
                   command=lambda: (win.destroy(), self.load_flashcard_decks())).pack(side='right', padx=3)
        fill()

    def rename_deck(self):
        deck_name = self._selected_deck()
        if deck_name is None:
            return
        new = simpledialog.askstring(_t("ai_study.flashcards.rename_deck", default="Rename Deck"),
                                     _t("ai_study.flashcards.new_deck_name", default="New name:"),
                                     initialvalue=deck_name, parent=self.window)
        if new and new.strip() != deck_name:
            try:
                self.service.rename_deck(self.owner, deck_name, new)
            except Exception as e:
                self._error(e)
            self.load_flashcard_decks()

    def delete_deck(self):
        deck_name = self._selected_deck()
        if deck_name is None:
            return
        if messagebox.askyesno(_t("ai_study.flashcards.delete_deck", default="Delete Deck"),
                               f"Delete the deck '{deck_name}' and all its cards?"):
            self.service.delete_deck(self.owner, deck_name)
            self.load_flashcard_decks()

    def explain_concept(self):
        """Get an explanation for a concept (Claude, or the course records)."""
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
        module = self._code_from(self.explain_module_var.get())
        self.explain_button.config(state='disabled')
        self.explanation_text.delete(1.0, tk.END)
        self.explanation_text.insert(1.0, _t("ai_study.concept_explainer.working", default="Working on it…"))

        def done(result, error):
            self.explain_button.config(state='normal')
            self.explanation_text.delete(1.0, tk.END)
            if error:
                messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"),
                                   _t("ai_study.concept_explainer.explanation_failed", default="Failed to explain concept: {error}").format(error=str(error)))
                return
            self.explanation_text.insert(1.0, result['explanation'])
            self.explanation_source_var.set(_SOURCE_LABELS.get(result.get('source'), ''))
            self.current_explanation_id = result['explanation_id']

        self._background(lambda: self.service.explain_concept(self.owner, module, concept, difficulty), done)

    def flashcards_from_current_explanation(self):
        explanation_id = getattr(self, 'current_explanation_id', None)
        if not explanation_id:
            messagebox.showwarning(_t("ai_study.messages.warning", default="Warning"),
                                   _t("ai_study.concept_explainer.no_explanation_to_rate", default="Generate an explanation first."))
            return

        def done(result, error):
            if error:
                self._error(error)
                return
            if not result['created']:
                messagebox.showinfo(_t("ai_study.messages.info", default="Info"),
                                    _t("ai_study.concept_explainer.no_cards", default="No cards could be made from this explanation."))
                return
            messagebox.showinfo(_t("ai_study.messages.success", default="Success"),
                                f"{len(result['created'])} card(s) added to the '{self.concept_entry.get().strip()}' deck.")
            self.load_flashcard_decks()

        self._background(lambda: self.service.flashcards_from_explanation(
            explanation_id, student_id=self.owner), done)

    def complete_task_gui(self):
        """Mark a pending task of the selected study plan as completed."""
        if not self.auth.current_user:
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"),
                                 _t("ai_study.auth.please_login", default="Please login first"))
            return

        plan_id = self._selected_plan_id()
        if plan_id is None:
            return

        plan_data = self.service.get_study_plan(plan_id)
        if not plan_data:
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"),
                                 _t("ai_study.study_plans.plan_not_found", default="Plan not found"))
            return

        pending = [t for t in plan_data['tasks'] if (t.get('status') or 'pending') == 'pending']
        if not pending:
            messagebox.showinfo(_t("ai_study.messages.info", default="Info"),
                                _t("ai_study.study_plans.no_pending_tasks", default="No pending tasks. Great job!"))
            return

        # Task picker dialog
        dialog = tk.Toplevel(self.window)
        dialog.title(_t("ai_study.study_plans.complete_task", default="Complete Task"))
        dialog.geometry("500x400")

        ttk.Label(dialog, text=_t("ai_study.study_plans.select_task_to_complete", default="Select a task to mark complete:"),
                  font=('Arial', 11, 'bold')).pack(pady=10)

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(side='bottom', pady=10)

        listbox = tk.Listbox(dialog, height=12)
        listbox.pack(fill='both', expand=True, padx=10, pady=5)
        for task in pending:
            duration = task.get('duration_minutes', 0) or 0
            listbox.insert(tk.END, f"{task.get('task_title', 'Untitled')} "
                                   f"({task.get('scheduled_date', 'N/A')}, {duration} min)")

        def do_complete():
            sel = listbox.curselection()
            if not sel:
                messagebox.showwarning(_t("ai_study.messages.warning", default="Warning"),
                                       _t("ai_study.study_plans.select_task_to_complete", default="Please select a task."))
                return
            task = pending[sel[0]]
            try:
                self.service.complete_study_task(task['task_id'], student_id=self.owner)
                messagebox.showinfo(_t("ai_study.messages.success", default="Success"),
                                    _t("ai_study.study_plans.task_completed", default="Task completed! Keep up the good work!"))
                dialog.destroy()
                self.load_study_plans()
            except Exception as e:
                messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"), str(e))

        ttk.Button(btn_frame, text=_t("ai_study.study_plans.mark_complete", default="Mark Complete"),
                  command=do_complete).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t("ai_study.buttons.cancel", default="Cancel"),
                  command=dialog.destroy).pack(side='left', padx=5)

    def rate_current_explanation(self):
        """Rate the most recently generated explanation."""
        explanation_id = getattr(self, 'current_explanation_id', None)
        if not explanation_id:
            messagebox.showwarning(_t("ai_study.messages.warning", default="Warning"),
                                   _t("ai_study.concept_explainer.no_explanation_to_rate", default="Generate an explanation before rating."))
            return
        try:
            self.service.rate_explanation(explanation_id, self.rating_var.get(), student_id=self.owner)
            messagebox.showinfo(_t("ai_study.messages.success", default="Success"),
                                _t("ai_study.concept_explainer.rating_saved", default="Thank you for your feedback!"))
        except Exception as e:
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"), str(e))

    def show_explanation_history(self):
        """Show the student's concept explanation history with rating support."""
        if not self.auth.current_user:
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"),
                                 _t("ai_study.auth.please_login", default="Please login first"))
            return

        try:
            explanations = self.service.get_explanation_history(self.owner)
        except Exception as e:
            messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"), str(e))
            return

        hist_window = tk.Toplevel(self.window)
        hist_window.title(_t("ai_study.concept_explainer.history_title", default="Explanation History"))
        hist_window.geometry("800x520")

        if not explanations:
            ttk.Label(hist_window, text=_t("ai_study.concept_explainer.no_history", default="No explanation history found."),
                      font=('Arial', 12)).pack(pady=40)
            return

        btns = ttk.Frame(hist_window)
        btns.pack(side='bottom', pady=(0, 10))

        columns = ("Concept", "Level", "Course", "Rating", "Date", "Source")
        tree = ttk.Treeview(hist_window, columns=columns, show='headings', height=12)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=125)
        tree.pack(fill='both', expand=True, padx=10, pady=10)

        id_by_item = {}
        for exp in explanations:
            rating = exp.get('helpful_rating', 0) or 0
            rating_disp = f"{rating}/5" if rating > 0 else "Not rated"
            iid = tree.insert('', 'end', values=(
                exp.get('concept_name', 'N/A'),
                exp.get('difficulty_level', 'N/A'),
                exp.get('course_id') or 'N/A',
                rating_disp,
                exp.get('created_at', 'N/A'),
                {"claude": "AI", "course_materials": "Course records"}.get(exp.get('source'), "Saved"),
            ))
            id_by_item[iid] = exp

        # Full-text viewer
        detail = scrolledtext.ScrolledText(hist_window, height=8, wrap='word')
        detail.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        def on_select(event=None):
            sel = tree.selection()
            if not sel:
                return
            exp = id_by_item[sel[0]]
            detail.delete(1.0, tk.END)
            detail.insert(1.0, exp.get('explanation', ''))

        tree.bind('<<TreeviewSelect>>', on_select)

        def rate_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning(_t("ai_study.messages.warning", default="Warning"),
                                       _t("ai_study.concept_explainer.select_explanation", default="Please select an explanation."))
                return
            exp = id_by_item[sel[0]]
            rating = simpledialog.askinteger(
                _t("ai_study.concept_explainer.rate_explanation", default="Rate this explanation"),
                _t("ai_study.concept_explainer.enter_rating", default="Rating (1-5 stars):"),
                parent=hist_window, minvalue=1, maxvalue=5)
            if rating is None:
                return
            try:
                self.service.rate_explanation(exp['explanation_id'], rating, student_id=self.owner)
                tree.set(sel[0], "Rating", f"{rating}/5")
                messagebox.showinfo(_t("ai_study.messages.success", default="Success"),
                                    _t("ai_study.concept_explainer.rating_saved", default="Thank you for your feedback!"))
            except Exception as e:
                messagebox.showerror(_t("ai_study.errors.generic_error", default="Error"), str(e))

        def delete_selected():
            sel = tree.selection()
            if not sel:
                return
            exp = id_by_item[sel[0]]
            if messagebox.askyesno("Delete", "Delete this explanation?", parent=hist_window):
                self.service.delete_explanation(exp['explanation_id'], self.owner)
                tree.delete(sel[0])
                detail.delete(1.0, tk.END)

        ttk.Button(btns, text=_t("ai_study.concept_explainer.rate_selected", default="Rate Selected"),
                  command=rate_selected).pack(side='left', padx=5)
        ttk.Button(btns, text=_t("ai_study.concept_explainer.delete_selected", default="Delete Selected"),
                  command=delete_selected).pack(side='left', padx=5)

    def load_analytics(self):
        """Load study analytics."""
        if not self.auth.current_user:
            return

        analytics = self.service.get_study_analytics(self.owner)

        self.analytics_text.delete(1.0, tk.END)

        text = f"{_t('ai_study.analytics.header', default='=== STUDY ANALYTICS ===')}\n\n"

        # Study Plans
        text += f"{_t('ai_study.analytics.study_plans_header', default='📚 STUDY PLANS')}\n"
        plans = analytics.get('study_plans', {}) or {}
        text += f"{_t('ai_study.analytics.total_plans', default='Total Plans: {total_plans}').format(total_plans=plans.get('total_plans', 0) or 0)}\n"
        text += f"{_t('ai_study.analytics.active_plans', default='Active Plans: {active_plans}').format(active_plans=plans.get('active_plans', 0) or 0)}\n"
        text += f"Completed Plans: {plans.get('completed_plans', 0) or 0}\n"
        text += f"{_t('ai_study.analytics.planned_hours', default='Total Hours Planned: {planned_hours}').format(planned_hours=plans.get('planned_hours', 0) or 0)}\n\n"

        # Tasks
        text += f"{_t('ai_study.analytics.tasks_header', default='✓ TASKS')}\n"
        tasks = analytics.get('tasks', {}) or {}
        text += f"{_t('ai_study.analytics.total_tasks', default='Total Tasks: {total_tasks}').format(total_tasks=tasks.get('total_tasks', 0) or 0)}\n"
        text += f"{_t('ai_study.analytics.completed_tasks', default='Completed Tasks: {completed_tasks}').format(completed_tasks=tasks.get('completed_tasks', 0) or 0)}\n"
        text += f"Missed (not yet done): {tasks.get('overdue_tasks', 0) or 0}   Skipped: {tasks.get('skipped_tasks', 0) or 0}\n"
        total_tasks = tasks.get('total_tasks', 0) or 0
        if total_tasks > 0:
            completed_tasks = tasks.get('completed_tasks', 0) or 0
            completion_rate = (completed_tasks / total_tasks) * 100
            text += f"{_t('ai_study.analytics.completion_rate', default='Completion Rate: {completion_rate}%').format(completion_rate=f'{completion_rate:.1f}')}\n"
        text += f"{_t('ai_study.analytics.total_study_time', default='Total Study Time: {total_minutes} minutes').format(total_minutes=tasks.get('completed_minutes', 0) or 0)}\n"
        text += f"Study streak: {analytics.get('streak_days', 0)} day(s)\n\n"

        # Flashcards
        text += f"{_t('ai_study.analytics.flashcards_header', default='🃏 FLASHCARDS')}\n"
        cards = analytics.get('flashcards', {}) or {}
        text += f"{_t('ai_study.analytics.total_cards', default='Total Cards: {total_cards}').format(total_cards=cards.get('total_cards', 0) or 0)}\n"
        text += f"{_t('ai_study.analytics.total_decks', default='Total Decks: {total_decks}').format(total_decks=cards.get('total_decks', 0) or 0)}\n"
        avg_accuracy = cards.get('avg_accuracy', 0) or 0
        text += f"{_t('ai_study.analytics.average_accuracy', default='Average Accuracy: {avg_accuracy}%').format(avg_accuracy=f'{avg_accuracy:.1f}')}\n"
        text += f"Well-learned cards (3+ correct in a row): {cards.get('mature_cards', 0) or 0}\n"
        reviews = analytics.get('reviews', {}) or {}
        retention = reviews.get('retention_pct')
        text += (f"Reviews in the last 30 days: {reviews.get('last_30_days', 0)}"
                 + (f" (recalled {retention:.0f}%)" if retention is not None else "") + "\n")

        weak = analytics.get('weak_modules') or []
        if weak:
            text += "\n⚠ MODULES TO GIVE MORE TIME\n"
            for w in weak:
                text += f"• {w['module_code']}: {'; '.join(w['reasons'])}\n"

        self.analytics_text.insert(1.0, text)

    def load_week(self):
        if not self.owner:
            return
        try:
            today = self.service.today(self.owner)
            ahead = self.service.upcoming(self.owner, 28)
        except Exception as e:
            logger.exception("Could not load the week")
            self.week_text.delete(1.0, tk.END)
            self.week_text.insert(1.0, f"Could not load: {e}")
            return
        lines = [f"TODAY — {today['date']}", ""]
        lines.append(f"🃏 {today['due_cards']} flashcard(s) due for review")
        if today['tasks_today']:
            lines.append("\n✓ Today's tasks:")
            lines += [f"   • {t['task_title']} ({t['duration_minutes'] or 0} min) — {t['plan_name']}"
                      for t in today['tasks_today']]
        else:
            lines.append("\n✓ No plan tasks today.")
        if today['overdue_tasks']:
            lines.append(f"\n⚠ {len(today['overdue_tasks'])} missed task(s). Select the plan in Study "
                         "Plans and press 'Reschedule Missed' to fit them back in.")
        lines.append("\n📅 EXAMS IN THE NEXT FOUR WEEKS")
        lines += [f"   • {e['date']} {e.get('start_time') or ''} — {e['module_code']} {e['name']}"
                  + (f" ({e['room']})" if e.get('room') else "") for e in ahead['exams']] or ["   None published."]
        lines.append("\n📝 DEADLINES IN THE NEXT FOUR WEEKS")
        lines += [f"   • {str(d['due_date'])[:16]} — {d['module_code']} {d['title']}"
                  for d in ahead['deadlines']] or ["   None outstanding."]
        self.week_text.delete(1.0, tk.END)
        self.week_text.insert(1.0, "\n".join(lines))

    def save_settings(self):
        try:
            self.service.save_settings(self.owner, reminders_enabled=self.pref_reminders.get(),
                                       email_reminders=self.pref_email.get(),
                                       share_with_tutor=self.pref_share.get(),
                                       daily_card_limit=int(self.pref_limit.get()))
        except Exception as e:
            self._error(e)
            return
        messagebox.showinfo(_t("ai_study.messages.success", default="Success"),
                            _t("ai_study.settings.saved", default="Settings saved."))

    def load_staff_overview(self):
        for item in self.staff_tree.get_children():
            self.staff_tree.delete(item)
        try:
            rows = self.service.staff_overview(self.auth.current_user,
                                               self._code_from(self.staff_module_var.get()))
        except Exception as e:
            self._error(e)
            return
        for r in rows:
            if not r['shared']:
                values = (r['student_id'], r['name'], "No", "", "", "", "", "", "", "")
            else:
                values = (r['student_id'], r['name'], "Yes", r['active_plans'], r['tasks_done'],
                          r['tasks_missed'],
                          f"{r['completion_pct']:.0f}%" if r['completion_pct'] is not None else "—",
                          r['cards_reviewed'],
                          f"{r['recall_pct']:.0f}%" if r['recall_pct'] is not None else "—",
                          r['last_active'] or "—")
            self.staff_tree.insert('', 'end', values=values)

    def show_staff_student(self):
        sel = self.staff_tree.selection()
        if not sel:
            messagebox.showwarning(_t("ai_study.messages.warning", default="Warning"),
                                   _t("ai_study.staff.select_student", default="Select a student."))
            return
        student_id = str(self.staff_tree.item(sel[0])['values'][0])
        try:
            d = self.service.staff_student_detail(self.auth.current_user, student_id)
        except Exception as e:
            self._error(e)
            return
        win = tk.Toplevel(self.window)
        win.title(f"Study companion — {d['name']} ({student_id})")
        win.geometry("760x520")
        text = scrolledtext.ScrolledText(win, wrap='word')
        text.pack(fill='both', expand=True, padx=10, pady=10)
        if not d.get('shared'):
            text.insert(1.0, "This student has chosen not to share their study activity.")
            return
        lines = [f"{d['name']} ({student_id})", "",
                 f"Active plans: {d['active_plans']}   Next exam on a plan: {d.get('next_plan_exam') or '—'}",
                 f"Last 14 days: {d['tasks_done']} task(s) done, {d['tasks_missed']} missed of {d['tasks_due']} due",
                 f"Cards reviewed (14 days): {d['cards_reviewed']}"
                 + (f", recalled {d['recall_pct']:.0f}%" if d.get('recall_pct') is not None else ""),
                 f"Last active: {d.get('last_active') or '—'}", "", "PLANS"]
        lines += [f"  • {p['plan_name']} ({p['course_id'] or 'general'}) — exam {p['end_date']}, "
                  f"{p['done'] or 0}/{p['tasks'] or 0} done, {p['status']}" for p in d.get('plans', [])] or ["  None"]
        lines += ["", "DECKS"]
        lines += [f"  • {k['deck_name']} ({k['course_id'] or '—'}): {k['cards']} cards, {k['due']} due"
                  for k in d.get('decks', [])] or ["  None"]
        if d.get('weak_modules'):
            lines += ["", "MODULES NEEDING TIME"]
            lines += [f"  • {w['module_code']}: {'; '.join(w['reasons'])}" for w in d['weak_modules']]
        text.insert(1.0, "\n".join(lines))

    def send_all_reminders(self):
        def done(result, error):
            if error:
                self._error(error)
                return
            messagebox.showinfo(_t("ai_study.messages.info", default="Info"),
                                f"Reminders sent: {result['sent']} of {result['checked']} companion user(s) "
                                f"(emails: {result['emailed']}). Each student gets at most one a day.")
        self._background(self.service.send_all_reminders, done)

    def run_engagement_scan(self):
        try:
            result = self.service.engagement_scan(actor=(self.auth.current_user or {}).get('username') or 'staff')
        except Exception as e:
            self._error(e)
            return
        messagebox.showinfo(_t("ai_study.messages.info", default="Info"),
                            f"Early-warning indicators raised: {result['raised']}; resolved: {result['resolved']}.\n"
                            "They appear in the Early Warning system as 'study_plan_slippage'.")
        self.load_staff_overview()

    def run(self):
        """Run the GUI."""
        self.window.mainloop()


def main():
    """Main entry point."""
    app = AIStudyGUI()
    app.run()


if __name__ == "__main__":
    main()
