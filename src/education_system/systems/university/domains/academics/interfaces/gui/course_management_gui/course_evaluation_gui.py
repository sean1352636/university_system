"""
Course Evaluation System GUI

Full-featured GUI for managing course evaluations, templates, responses,
and viewing results analytics.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from education_system.systems.university.domains.academics.interfaces.gui.course_management_gui import report_widgets as _report
from datetime import datetime
from typing import Optional
import json
import os

from education_system.systems.university.infrastructure.i18n import get_text as _, init_i18n
init_i18n()

from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.domains.academics.domain.services.evaluation.course_evaluation_core import (
    EvaluationTemplateManager,
    CourseEvaluationManager,
    ResponseManager,
    ResultsAnalyticsManager
)
from education_system.systems.university.domains.academics.domain.services.evaluation.db_schema import initialize_evaluation_database
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.domains.academics.interfaces.gui.course_management_gui._student_enrolment import enrolment_summary
import logging

logger = logging.getLogger(__name__)


class CourseEvaluationGUI:
    """Main GUI for Course Evaluation System"""

    def __init__(self, parent, auth: UserAuth):
        self.root = tk.Toplevel(parent)
        # 8.117.89: renamed from "Course Evaluation" to "Evaluation Admin".
        # The student-facing form (with Submit Response) lives in the
        # main GUI's Course Evaluation app; this dialog is now strictly
        # the admin surface — Templates, Evaluations and Results.
        self.root.title(_t('gui.academics.course_management_gui.course_evaluation.windows.evaluation_admin', default="Evaluation Admin"))
        self.root.geometry("1400x900+%d+%d" % ((self.root.winfo_screenwidth() - 1400) // 2, (self.root.winfo_screenheight() - 900) // 2))
        self.root.minsize(1200, 800)
        self.root.configure(bg='#f0f0f0')
        self.auth = auth

        # Initialize database
        try:
            initialize_evaluation_database()
        except Exception as e:
            print(f"Database initialization warning: {e}")

        # Auto-import the bundled JSON templates from
        # ``templates/course_evaluation/`` (8.117.95). Pre-fix, those
        # templates were only reachable via the manual "Load Template
        # From File" dialog, so the Launch Evaluation dropdown only
        # showed admin-created templates and the 15 bundled ones were
        # invisible. Idempotent: each template name is created once;
        # subsequent runs skip rows that already exist.
        try:
            self._auto_import_bundled_templates()
        except Exception as e:
            print(f"Bundled-template auto-import warning: {e}")

        self.create_widgets()
        self.load_evaluations()

    def _auto_import_bundled_templates(self):
        """Import every JSON template from ``templates/course_evaluation/``
        into the ``evaluation_templates`` table on first sight.

        Idempotent — a template name that already exists is skipped, so
        repeated launches don't create duplicates and admin edits to the
        DB row aren't overwritten by what's on disk.
        """
        import json
        from education_system import paths
        templates_dir = paths.UNIVERSITY_COURSE_EVALUATION_TEMPLATES_DIR
        if not templates_dir.is_dir():
            return

        # Collect existing template names so we don't INSERT duplicates.
        with get_connection() as conn:
            existing = {row[0] for row in conn.execute(
                "SELECT template_name FROM evaluation_templates").fetchall()}

        created_by = (self.auth.current_user or {}).get('username', 'system') \
            if self.auth else 'system'

        imported = 0
        for path in sorted(templates_dir.glob("*.json")):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except (OSError, ValueError) as e:
                print(f"Could not read {path.name}: {e}")
                continue
            name = data.get('template_name')
            if not name or name in existing:
                continue
            try:
                template_id = EvaluationTemplateManager.create_template(
                    template_name=name,
                    template_type=data.get('template_type', 'Course'),
                    description=data.get('description', ''),
                    created_by=created_by,
                )
                for q in data.get('questions', []):
                    EvaluationTemplateManager.add_question(
                        template_id=template_id,
                        question_text=q.get('question_text', ''),
                        question_type=q.get('question_type', 'Rating'),
                        question_category=q.get('question_category', ''),
                        scale_min=q.get('scale_min', 1),
                        scale_max=q.get('scale_max', 5),
                    )
                existing.add(name)
                imported += 1
            except Exception as e:
                print(f"Failed to import bundled template {path.name}: {e}")

        if imported:
            print(f"Auto-imported {imported} bundled course-evaluation template(s)")

    def create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title = ttk.Label(main_frame, text=_t('gui.academics.course_management_gui.course_evaluation.labels.evaluation_admin', default="Evaluation Admin"),
                         font=('Arial', 16, 'bold'))
        title.pack(pady=10)
        ttk.Label(main_frame,
                  text=_t('gui.academics.course_management_gui.course_evaluation.labels.templates_evaluations_and_results_the_student_submit_response_fo', default="Templates, evaluations and results. The student "
                       "Submit Response form lives in the main GUI's "
                       "Course Evaluation app (8.117.89)."),
                  foreground="#666").pack()

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs — Submit Response moved out in 8.117.89; admins
        # use the main GUI's student-facing form for any test
        # submissions. The methods below (create_responses_tab,
        # submit_response, load_evaluation_questions) are kept as
        # dead code so the bridge work in a future commit can re-enable
        # the tab without re-implementing the wiring.
        self.create_templates_tab()
        self.create_evaluations_tab()
        self.create_results_tab()

    def create_templates_tab(self):
        """Create Evaluation Templates management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("course_evaluation.tabs.templates"))

        # Top frame for buttons
        button_frame = ttk.Frame(tab)
        button_frame.pack(fill=tk.X, pady=5)

        ttk.Button(button_frame, text=_("course_evaluation.buttons.create_template"),
                  command=self.create_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_("course_evaluation.buttons.load_template_from_file"),
                  command=self.load_template_from_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_("course_evaluation.buttons.add_questions"),
                  command=self.add_questions).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_("common.refresh"),
                  command=self.load_templates).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.academics.course_management_gui.course_evaluation.buttons.survey_designer', default="Survey Designer…"),
                  command=self.open_survey_designer).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.academics.course_management_gui.course_evaluation.buttons.operations', default="Operations…"),
                  command=self.open_operations).pack(side=tk.LEFT, padx=5)

        # Templates list
        list_frame = ttk.LabelFrame(tab, text=_("course_evaluation.tabs.templates"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Treeview for templates
        columns = ('ID', 'Name', 'Type', 'Description', 'Created By', 'Created Date')
        self.templates_tree = ttk.Treeview(list_frame, columns=columns, show='headings',
                                          height=15)

        column_headers = {
            'ID': _("course_evaluation.columns.id"),
            'Name': _("course_evaluation.columns.name"),
            'Type': _("course_evaluation.columns.type"),
            'Description': _("course_evaluation.columns.description"),
            'Created By': _("course_evaluation.columns.created_by"),
            'Created Date': _("course_evaluation.columns.created_date")
        }
        for col in columns:
            self.templates_tree.heading(col, text=column_headers[col])
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
        self.notebook.add(tab, text=_("course_evaluation.tabs.evaluations"))

        # Top frame for buttons
        button_frame = ttk.Frame(tab)
        button_frame.pack(fill=tk.X, pady=5)

        ttk.Button(button_frame, text=_("course_evaluation.buttons.launch_evaluation"),
                  command=self.launch_evaluation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_("course_evaluation.buttons.view_details"),
                  command=self.view_evaluation_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_("common.refresh"),
                  command=self.load_evaluations).pack(side=tk.LEFT, padx=5)

        # Evaluations list
        list_frame = ttk.LabelFrame(tab, text=_("course_evaluation.labels.active_evaluations"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ('ID', 'Module', 'Year', 'Semester', 'Instructor',
                  'Start Date', 'End Date', 'Responses')
        self.evaluations_tree = ttk.Treeview(list_frame, columns=columns,
                                            show='headings', height=15)

        column_headers = {
            'ID': _("course_evaluation.columns.id"),
            'Module': _("course_evaluation.columns.module"),
            'Year': _("course_evaluation.columns.year"),
            'Semester': _("course_evaluation.columns.semester"),
            'Instructor': _("course_evaluation.columns.instructor"),
            'Start Date': _("course_evaluation.columns.start_date"),
            'End Date': _("course_evaluation.columns.end_date"),
            'Responses': _("course_evaluation.columns.responses")
        }
        for col in columns:
            self.evaluations_tree.heading(col, text=column_headers[col])
            self.evaluations_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                 command=self.evaluations_tree.yview)
        self.evaluations_tree.configure(yscrollcommand=scrollbar.set)

        self.evaluations_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_responses_tab(self):
        """Create Student Responses tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("course_evaluation.tabs.submit_response"))

        ttk.Label(tab, text=_("course_evaluation.labels.submit_response_title"),
                 font=('Arial', 12, 'bold')).pack(pady=10)

        # Evaluation selection
        select_frame = ttk.LabelFrame(tab, text=_("course_evaluation.labels.select_evaluation"), padding="10")
        select_frame.pack(fill=tk.X, pady=5)

        ttk.Label(select_frame, text=_("course_evaluation.labels.evaluation")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.response_eval_combo = ttk.Combobox(select_frame, width=50, state='readonly')
        self.response_eval_combo.grid(row=0, column=1, padx=5, pady=5)
        self.response_eval_combo.bind('<<ComboboxSelected>>', self.load_evaluation_questions)

        ttk.Button(select_frame, text=_("course_evaluation.buttons.load_questions"),
                  command=self.load_evaluation_questions).grid(row=0, column=2, padx=5)

        # Questions frame
        self.questions_frame = ttk.LabelFrame(tab, text=_("course_evaluation.labels.questions"), padding="10")
        self.questions_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Submit button
        ttk.Button(tab, text=_("course_evaluation.buttons.submit_evaluation"),
                  command=self.submit_response).pack(pady=10)

    def create_results_tab(self):
        """Create Results & Analytics tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("course_evaluation.tabs.results"))

        # Evaluation selection
        select_frame = ttk.Frame(tab)
        select_frame.pack(fill=tk.X, pady=5)

        ttk.Label(select_frame, text=_("course_evaluation.labels.select_evaluation_colon")).pack(side=tk.LEFT, padx=5)
        self.results_eval_combo = ttk.Combobox(select_frame, width=50, state='readonly')
        self.results_eval_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(select_frame, text=_("course_evaluation.buttons.calculate_results"),
                  command=self.calculate_results).pack(side=tk.LEFT, padx=5)
        ttk.Button(select_frame, text=_("course_evaluation.buttons.export_report"),
                  command=self.export_results).pack(side=tk.LEFT, padx=5)
        ttk.Button(select_frame, text=_t('gui.academics.course_management_gui.course_evaluation.buttons.email_report_to_admin', default="Email Report to Admin"),
                  command=self.email_results_to_admin).pack(side=tk.LEFT, padx=5)

        ttk.Label(select_frame,
                  text="Double-click a question for its full breakdown",
                  foreground="#7f8c8d").pack(side=tk.LEFT, padx=12)

        # Results display: cards and a sortable question table on a scrolling
        # surface, rather than a fixed-height wall of text.
        results_frame = ttk.LabelFrame(tab, text=_("course_evaluation.labels.evaluation_results"), padding="6")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.results_surface = _report.scrollable(results_frame)
        self._results_placeholder()
        # Kept so the export and email actions still have the plain-text
        # rendering they write out.
        self._results_plain = ""
        self._results_rows = []

    # ======================== Helper Methods ========================

    def open_operations(self):
        """Open the Operations window (features 26-50)."""
        try:
            from education_system.systems.university.domains.academics.interfaces.gui.course_management_gui.course_evaluation_operations import (
                launch_operations_gui,
            )
        except ImportError as e:
            messagebox.showerror(_t('gui.academics.course_management_gui.course_evaluation.dialogs.operations', default="Operations"), f"Operations unavailable: {e}")
            return
        launch_operations_gui(self.root, self.auth)

    def open_survey_designer(self):
        """Open the Survey Designer window (features 1-8)."""
        try:
            from education_system.systems.university.domains.academics.interfaces.gui.course_management_gui.course_evaluation_designer import (
                launch_survey_designer,
            )
        except ImportError as e:
            messagebox.showerror(_t('gui.academics.course_management_gui.course_evaluation.dialogs.survey_designer', default="Survey Designer"), f"Designer unavailable: {e}")
            return
        launch_survey_designer(self.root, self.auth)

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
                    self.templates_tree.insert('', tk.END, values=tuple(row))

        except Exception as e:
            messagebox.showerror(_("common.error"), _("course_evaluation.messages.failed_load_templates").format(error=e))

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
                    self.evaluations_tree.insert('', tk.END, values=tuple(row))

                # Update whichever combo boxes exist. ``response_eval_combo``
                # belongs to create_response_tab, which create_widgets never
                # calls — so this line raised AttributeError every time and
                # took the whole loader with it, leaving the Results tab's
                # dropdown permanently empty and "Calculate Results" unusable.
                eval_list = [f"{row[0]}: {row[1]} - {row[2]} {row[3]}" for row in rows]
                for attr in ("response_eval_combo", "results_eval_combo"):
                    combo = getattr(self, attr, None)
                    if combo is not None:
                        combo['values'] = eval_list

        except Exception as e:
            messagebox.showerror(_("common.error"), _("course_evaluation.messages.failed_load_evaluations").format(error=e))

    def create_template(self):
        """Create a new evaluation template"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("course_evaluation.dialogs.create_template_title"))
        dialog.geometry("500x400")

        # Form fields
        ttk.Label(dialog, text=_("course_evaluation.labels.template_name")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        name_entry = ttk.Entry(dialog, width=40)
        name_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dialog, text=_("course_evaluation.labels.template_type")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        type_combo = ttk.Combobox(dialog, values=[_("course_evaluation.types.course"), _("course_evaluation.types.instructor"), _("course_evaluation.types.program"), _("course_evaluation.types.custom")],
                                 width=38, state='readonly')
        type_combo.grid(row=1, column=1, padx=5, pady=5)
        type_combo.current(0)

        ttk.Label(dialog, text=_("course_evaluation.labels.description")).grid(row=2, column=0, sticky=tk.NW, padx=5, pady=5)
        desc_text = tk.Text(dialog, width=40, height=8)
        desc_text.grid(row=2, column=1, padx=5, pady=5)

        def save_template():
            try:
                name = name_entry.get().strip()
                template_type = type_combo.get()
                description = desc_text.get('1.0', tk.END).strip()

                if not name:
                    messagebox.showerror(_("common.error"), _("course_evaluation.messages.template_name_required"))
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

                messagebox.showinfo(_("common.success"),
                                  _("course_evaluation.messages.template_created").format(id=template_id))
                dialog.destroy()
                self.load_templates()

            except Exception as e:
                messagebox.showerror(_("common.error"), _("course_evaluation.messages.failed_create_template").format(error=e))

        ttk.Button(dialog, text=_("course_evaluation.buttons.create_template"),
                  command=save_template).grid(row=3, column=0, columnspan=2, pady=20)

    def load_template_from_file(self):
        """Load evaluation template from JSON file"""
        # 8.117.94: pre-fix this computed the path with four
        # ``os.path.dirname`` hops, landing in ``modules/`` instead of
        # ``university_system/`` and producing the error
        # "Templates directory not found: …/modules/templates/course_evaluation".
        # Use the canonical constant from ``paths`` instead of building
        # a relative path by hand.
        from education_system import paths
        templates_dir = str(paths.UNIVERSITY_COURSE_EVALUATION_TEMPLATES_DIR)

        # Check if templates directory exists
        if not os.path.exists(templates_dir):
            messagebox.showerror(_("common.error"), f"Templates directory not found: {templates_dir}")
            return

        # Get list of template files
        template_files = [f for f in os.listdir(templates_dir) if f.endswith('.json')]

        if not template_files:
            messagebox.showwarning(_("common.warning"), _("course_evaluation.messages.no_template_files_found"))
            return

        # Create selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(_("course_evaluation.buttons.load_template_from_file"))
        dialog.geometry("600x500")

        ttk.Label(dialog, text=_("course_evaluation.labels.select_template_to_load"), font=('Arial', 12, 'bold')).pack(pady=10)

        # Listbox to show templates
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        listbox = tk.Listbox(list_frame, width=70, height=15)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)

        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load template names
        template_data = {}
        for filename in sorted(template_files):
            filepath = os.path.join(templates_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    template_name = data.get('template_name', filename)
                    template_desc = data.get('description', '')
                    display_text = f"{template_name} - {template_desc}"
                    listbox.insert(tk.END, display_text)
                    template_data[display_text] = (filepath, data)
            except Exception as e:
                print(f"Error loading {filename}: {e}")

        # Preview text area
        preview_frame = ttk.LabelFrame(dialog, text=_("course_evaluation.labels.preview"), padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        preview_text = scrolledtext.ScrolledText(preview_frame, wrap=tk.WORD, width=60, height=8)
        preview_text.pack(fill=tk.BOTH, expand=True)

        def show_preview(event):
            """Show template preview when selected"""
            selection = listbox.curselection()
            if selection:
                selected_item = listbox.get(selection[0])
                if selected_item in template_data:
                    _, data = template_data[selected_item]
                    preview_text.delete('1.0', tk.END)
                    preview_text.insert('1.0', f"Template: {data.get('template_name', 'N/A')}\n")
                    preview_text.insert(tk.END, f"Type: {data.get('template_type', 'N/A')}\n")
                    preview_text.insert(tk.END, f"Description: {data.get('description', 'N/A')}\n\n")
                    preview_text.insert(tk.END, f"Questions: {len(data.get('questions', []))}\n\n")

                    for i, q in enumerate(data.get('questions', []), 1):
                        preview_text.insert(tk.END, f"Q{i}: {q.get('question_text', '')}\n")
                        preview_text.insert(tk.END, f"    Type: {q.get('question_type', '')}\n\n")

        listbox.bind('<<ListboxSelect>>', show_preview)

        def load_selected_template():
            """Load the selected template into database"""
            selection = listbox.curselection()
            if not selection:
                messagebox.showwarning(_("common.warning"), _("course_evaluation.messages.please_select_template_to_load"))
                return

            selected_item = listbox.get(selection[0])
            if selected_item not in template_data:
                return

            filepath, data = template_data[selected_item]

            try:
                # Create template in database
                created_by = self.auth.current_user.get('username', 'System') if self.auth.current_user else 'System'

                template_id = EvaluationTemplateManager.create_template(
                    template_name=data.get('template_name'),
                    template_type=data.get('template_type'),
                    description=data.get('description'),
                    created_by=created_by
                )

                # Add questions
                questions_added = 0
                for question in data.get('questions', []):
                    EvaluationTemplateManager.add_question(
                        template_id=template_id,
                        question_text=question.get('question_text'),
                        question_type=question.get('question_type'),
                        question_category=question.get('question_category'),
                        scale_min=question.get('scale_min', 1),
                        scale_max=question.get('scale_max', 5)
                    )
                    questions_added += 1

                log_activity('import', 'evaluation_template', str(template_id),
                           {'source': filepath, 'questions': questions_added})

                messagebox.showinfo(_("common.success"),
                                  f"Template '{data.get('template_name')}' loaded successfully!\n"
                                  f"Template ID: {template_id}\n"
                                  f"Questions added: {questions_added}")

                dialog.destroy()
                self.load_templates()

            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to load template: {e}")

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text=_("course_evaluation.buttons.load_selected_template"),
                  command=load_selected_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_("common.cancel"),
                  command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def add_questions(self):
        """Add questions to a template"""
        selected = self.templates_tree.selection()
        if not selected:
            messagebox.showwarning(_("common.warning"), _("course_evaluation.messages.select_template_first"))
            return

        template_id = self.templates_tree.item(selected[0])['values'][0]

        dialog = tk.Toplevel(self.root)
        dialog.title(_("course_evaluation.dialogs.add_questions_title").format(id=template_id))
        dialog.geometry("600x500")

        # Question form
        ttk.Label(dialog, text=_("course_evaluation.labels.question_text")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        question_text = tk.Text(dialog, width=50, height=4)
        question_text.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(dialog, text=_("course_evaluation.labels.type")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        type_combo = ttk.Combobox(dialog, values=[_("course_evaluation.question_types.rating"), _("course_evaluation.question_types.multiple_choice"), _("course_evaluation.question_types.text"), _("course_evaluation.question_types.yes_no")],
                                 width=48, state='readonly')
        type_combo.grid(row=1, column=1, padx=5, pady=5)
        type_combo.current(0)

        ttk.Label(dialog, text=_("course_evaluation.labels.category")).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        category_combo = ttk.Combobox(dialog,
                                     values=[_("course_evaluation.categories.course_content"), _("course_evaluation.categories.instructor"), _("course_evaluation.categories.materials"), _("course_evaluation.categories.assessment"), _("course_evaluation.categories.general")],
                                     width=48, state='readonly')
        category_combo.grid(row=2, column=1, padx=5, pady=5)
        category_combo.current(0)

        ttk.Label(dialog, text=_("course_evaluation.labels.scale_min")).grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        min_entry = ttk.Entry(dialog, width=50)
        min_entry.insert(0, "1")
        min_entry.grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(dialog, text=_("course_evaluation.labels.scale_max")).grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        max_entry = ttk.Entry(dialog, width=50)
        max_entry.insert(0, "5")
        max_entry.grid(row=4, column=1, padx=5, pady=5)

        def save_question():
            try:
                text = question_text.get('1.0', tk.END).strip()
                if not text:
                    messagebox.showerror(_("common.error"), _("course_evaluation.messages.question_text_required"))
                    return

                question_id = EvaluationTemplateManager.add_question(
                    template_id=template_id,
                    question_text=text,
                    question_type=type_combo.get(),
                    question_category=category_combo.get(),
                    scale_min=int(min_entry.get()),
                    scale_max=int(max_entry.get())
                )

                messagebox.showinfo(_("common.success"), _("course_evaluation.messages.question_added").format(id=question_id))
                question_text.delete('1.0', tk.END)

            except Exception as e:
                messagebox.showerror(_("common.error"), _("course_evaluation.messages.failed_add_question").format(error=e))

        ttk.Button(dialog, text=_("course_evaluation.buttons.add_question"),
                  command=save_question).grid(row=5, column=0, columnspan=2, pady=20)

    def _student_scope(self):
        """Enrolment scope for the signed-in user, or None for staff.

        Returns None when the user is not a student (or has no student
        record), which leaves the dialogs showing the full catalogue —
        staff launch evaluations on other people's behalf.
        """
        user = getattr(self.auth, "current_user", None) or {}
        role = str(user.get("role", "")).lower()
        if role and role != "student":
            return None
        student_id = user.get("student_id") or user.get("username")
        if not student_id:
            return None
        try:
            summary = enrolment_summary(str(student_id))
        except Exception:
            logger.debug("Could not resolve enrolment scope", exc_info=True)
            return None
        return summary if (summary.get("course") or summary.get("lecturers")) else None

    def launch_evaluation(self):
        """Launch a new course evaluation"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("course_evaluation.dialogs.launch_evaluation_title"))
        dialog.geometry("500x450")

        fields = {}

        ttk.Label(dialog, text=_t('gui.academics.course_management_gui.course_evaluation.labels.course', default="Course:")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        fields['module'] = ttk.Combobox(dialog, width=45, state='readonly')
        fields['module'].grid(row=0, column=1, padx=5, pady=5)

        # A student evaluates their own course, not any course in the
        # catalogue. Staff and admins launch evaluations on behalf of
        # others, so they still get the full list.
        summary = self._student_scope()
        course_codes = {}
        course_list = []
        try:
            if summary and summary.get("course"):
                course = summary["course"]
                label = f"{course['code']} - {course['name']}"
                course_list = [label]
                course_codes[label] = course["code"]
            else:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT COALESCE(course_code, code), COALESCE(course_name, name) "
                        "FROM courses "
                        "WHERE COALESCE(course_code, code) IS NOT NULL "
                        "AND COALESCE(course_name, name) IS NOT NULL "
                        "AND LOWER(COALESCE(status, 'active')) = 'active' "
                        "ORDER BY COALESCE(course_code, code)"
                    )
                    for code, name in cursor.fetchall():
                        label = f"{code} - {name}"
                        course_list.append(label)
                        course_codes[label] = code
            fields['module']['values'] = course_list
            if course_list:
                fields['module'].current(0)
        except Exception as e:
            print(f"Could not load courses: {e}")

        ttk.Label(dialog, text=_("course_evaluation.labels.academic_year")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        current_year = datetime.now().year
        fields['year'] = ttk.Combobox(dialog, width=38, state='readonly',
                                      values=[f"{y}/{y+1}" for y in range(current_year - 1, current_year + 3)])
        fields['year'].current(1)
        fields['year'].grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(dialog, text=_("course_evaluation.labels.semester")).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        fields['semester'] = ttk.Combobox(dialog, values=[_("course_evaluation.semesters.fall"), _("course_evaluation.semesters.spring"), _("course_evaluation.semesters.summer")],
                                         width=38, state='readonly')
        fields['semester'].current(0)
        fields['semester'].grid(row=2, column=1, padx=5, pady=5)

        # Load available instructors
        ttk.Label(dialog, text=_("course_evaluation.labels.instructor_id")).grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        fields['instructor'] = ttk.Combobox(dialog, width=38, state='readonly')
        fields['instructor'].grid(row=3, column=1, padx=5, pady=5)

        # Populate instructors dropdown. For a student this is limited to
        # the lecturers who teach the modules they are enrolled on —
        # rating someone who has never taught you is not feedback.
        instructor_data = {}
        try:
            if summary and summary.get("lecturers"):
                instructors = [
                    (l["id"], l["name"].split(" ")[0],
                     " ".join(l["name"].split(" ")[1:]), l["department"], l["email"])
                    for l in summary["lecturers"]
                ]
            else:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT id, first_name, last_name, department, email
                        FROM instructors
                        WHERE is_active = 1 AND status = 'Active'
                        ORDER BY last_name, first_name
                    ''')
                    instructors = cursor.fetchall()

            if instructors:
                instructor_list = []
                for row in instructors:
                    i_id, first_name, last_name, dept, email = tuple(row)
                    display = f"{i_id}: {first_name} {last_name}"
                    if dept:
                        display += f" ({dept})"
                    instructor_list.append(display)
                    instructor_data[display] = str(i_id)

                fields['instructor']['values'] = instructor_list
                if instructor_list:
                    fields['instructor'].current(0)
            else:
                messagebox.showwarning(_("common.warning"),
                                     _("course_evaluation.messages.no_instructors_available"))
        except Exception as e:
            print(f"Could not load instructors: {e}")
            messagebox.showwarning(_("common.warning"), f"Could not load instructors: {e}")

        # Load available templates
        ttk.Label(dialog, text=_("course_evaluation.labels.template")).grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        fields['template'] = ttk.Combobox(dialog, width=38, state='readonly')
        fields['template'].grid(row=4, column=1, padx=5, pady=5)

        # Populate templates dropdown
        template_data = {}
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT template_id, template_name, template_type
                    FROM evaluation_templates
                    WHERE is_active = 1
                    ORDER BY template_name
                ''')
                templates = cursor.fetchall()

                if templates:
                    template_list = []
                    for row in templates:
                        t_id, t_name, t_type = tuple(row)
                        display = f"{t_id}: {t_name} ({t_type})"
                        template_list.append(display)
                        template_data[display] = t_id

                    fields['template']['values'] = template_list
                    if template_list:
                        fields['template'].current(0)
                else:
                    messagebox.showwarning(_("common.warning"),
                                         _("course_evaluation.messages.no_templates_available"))
                    dialog.destroy()
                    return
        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to load templates: {e}")
            dialog.destroy()
            return

        ttk.Label(dialog, text=_("course_evaluation.labels.start_date")).grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        fields['start'] = ttk.Entry(dialog, width=40)
        fields['start'].insert(0, datetime.now().strftime('%Y-%m-%d'))
        fields['start'].grid(row=5, column=1, padx=5, pady=5)

        ttk.Label(dialog, text=_("course_evaluation.labels.end_date")).grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        fields['end'] = ttk.Entry(dialog, width=40)
        fields['end'].grid(row=6, column=1, padx=5, pady=5)

        def save_evaluation():
            try:
                selected_template = fields['template'].get()
                if not selected_template:
                    messagebox.showerror(_("common.error"), _("course_evaluation.messages.please_select_template"))
                    return

                template_id = template_data[selected_template]

                # Get instructor ID from dropdown
                selected_instructor = fields['instructor'].get()
                if not selected_instructor:
                    messagebox.showerror(_("common.error"), _("course_evaluation.messages.please_select_instructor"))
                    return
                instructor_id = instructor_data[selected_instructor]

                selected_course = fields['module'].get()
                module_code = course_codes.get(selected_course, selected_course)

                eval_id = CourseEvaluationManager.create_evaluation(
                    module_code=module_code,
                    academic_year=fields['year'].get().strip(),
                    semester=fields['semester'].get(),
                    instructor_id=instructor_id,
                    template_id=template_id,
                    start_date=fields['start'].get(),
                    end_date=fields['end'].get()
                )

                log_activity('create', 'course_evaluation', str(eval_id))

                messagebox.showinfo(_("common.success"),
                                  _("course_evaluation.messages.evaluation_launched").format(id=eval_id))
                dialog.destroy()
                self.load_evaluations()

            except Exception as e:
                messagebox.showerror(_("common.error"), _("course_evaluation.messages.failed_launch_evaluation").format(error=e))

        ttk.Button(dialog, text=_("course_evaluation.buttons.launch_evaluation"),
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
                        var = tk.StringVar(value=_t('gui.academics.course_management_gui.course_evaluation.values.yes', default="Yes"))
                        frame = ttk.Frame(self.questions_frame)
                        frame.grid(row=row_num, column=1, padx=5, pady=10)
                        ttk.Radiobutton(frame, text=_("common.yes"), value="Yes",
                                      variable=var).pack(side=tk.LEFT)
                        ttk.Radiobutton(frame, text=_("common.no"), value="No",
                                      variable=var).pack(side=tk.LEFT)
                        self.question_widgets[q_id] = var

                    else:  # Text
                        entry = ttk.Entry(self.questions_frame, width=50)
                        entry.grid(row=row_num, column=1, padx=5, pady=10)
                        self.question_widgets[q_id] = entry

                    row_num += 1

        except Exception as e:
            messagebox.showerror(_("common.error"), _("course_evaluation.messages.failed_load_questions").format(error=e))

    def submit_response(self):
        """Submit evaluation response"""
        try:
            selection = self.response_eval_combo.get()
            if not selection:
                messagebox.showwarning(_("common.warning"), _("course_evaluation.messages.select_evaluation"))
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

            messagebox.showinfo(_("common.success"), _("course_evaluation.messages.thank_you_feedback"))

            # Clear form
            for widget in self.questions_frame.winfo_children():
                widget.destroy()

        except Exception as e:
            messagebox.showerror(_("common.error"), _("course_evaluation.messages.failed_submit_response").format(error=e))

    def calculate_results(self):
        """Calculate results and render them as cards plus a question table."""
        try:
            selection = self.results_eval_combo.get()
            if not selection:
                messagebox.showwarning(_("common.warning"), _("course_evaluation.messages.select_evaluation"))
                return

            eval_id = int(selection.split(':')[0])
            results = ResultsAnalyticsManager.calculate_results(eval_id)
            self._current_eval_id = eval_id
            self._results_rows = results
            self._results_plain = self._plain_results_text(eval_id, results)
            self._render_results(eval_id, selection, results)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("course_evaluation.messages.failed_calculate_results").format(error=e))

    def _plain_results_text(self, eval_id, results):
        """The old text rendering, kept for export and the emailed report."""
        lines = [_("course_evaluation.results.header").format(id=eval_id), "=" * 80, ""]
        for result in results:
            avg = result['average_score']
            lines += [
                _("course_evaluation.results.question_id").format(id=result['question_id']),
                _("course_evaluation.results.question").format(text=result['question_text']),
                _("course_evaluation.results.average_score").format(
                    score=f"{avg:.2f}" if avg is not None else "N/A"),
                _("course_evaluation.results.responses").format(count=result['response_count']),
                "-" * 80, "",
            ]
        return "\n".join(lines)

    def _results_placeholder(self):
        _report.clear(self.results_surface)
        body = _report.card(self.results_surface, accent=_report.MUTED)
        tk.Label(body,
                 text="Choose an evaluation and click Calculate Results.",
                 bg=_report.CARD, fg=_report.MUTED,
                 font=(_report.FONT, 9)).pack(anchor="w")

    def _render_results(self, eval_id, selection, results):
        surface = self.results_surface
        _report.clear(surface)

        scored = [r for r in results if r['average_score'] is not None]
        overall = (sum(r['average_score'] for r in scored) / len(scored)) if scored else None
        responses = max((r['response_count'] or 0) for r in results) if results else 0

        _report.banner(surface, selection, f"Evaluation {eval_id}")
        _report.stat_strip(surface, [
            (len(results), "Questions"),
            (responses, "Responses"),
            (f"{overall:.2f}" if overall is not None else "N/A", "Overall average",
             _report.OK if (overall or 0) >= 3.5 else _report.WARN),
            (len(results) - len(scored), "Free-text only"),
        ])

        if not results:
            _report.verdict(surface, None, "No completed responses yet",
                            "Nothing has been submitted for this evaluation.",
                            neutral=True)
            return

        _report.card(surface, "Per-question results", accent="#9b59b6")
        rows = []
        for r in results:
            avg = r['average_score']
            rows.append((r['question_id'], r['question_text'],
                         f"{avg:.2f}" if avg is not None else "—",
                         r['response_count'] or 0))
        tree = _report.table(
            surface, ("ID", "Question", "Average", "Responses"), rows,
            widths={"ID": 60, "Question": 380, "Average": 90, "Responses": 90},
            height=14)

        def _open(_event=None):
            sel = tree.selection()
            if not sel:
                return
            qid = tree.item(sel[0])["values"][0]
            self.show_question_results(eval_id, qid)
        tree.bind("<Double-1>", _open)

        # Weakest questions are what a module leader acts on, so surface them
        # rather than making someone scan the table for them.
        weak = sorted(scored, key=lambda r: r['average_score'])[:3]
        if weak and overall is not None:
            body = _report.card(surface, "Lowest scoring", accent=_report.WARN)
            _report.status_list(body, [
                (r['average_score'] >= 3.0, r['question_text'],
                 f"{r['average_score']:.2f} from {r['response_count']} response(s)")
                for r in weak
            ])

    def show_question_results(self, eval_id, question_id):
        """Open one question's full breakdown in its own window."""
        try:
            data = ResultsAnalyticsManager.question_breakdown(eval_id, int(question_id))
        except Exception as e:
            messagebox.showerror(_("common.error"), f"Could not load question results: {e}")
            return

        window, surface = _report.report_window(
            self.root, f"Question {question_id} — results", "760x640")

        _report.banner(surface, data["question_text"],
                       f"Question {question_id} · {data['question_type'] or 'unknown type'}")

        average = data["average"]
        _report.stat_strip(surface, [
            (data["response_count"], "Responses"),
            (f"{average:.2f}" if average is not None else "—", "Average"),
            (f"{data['median']:.2f}" if data["median"] is not None else "—", "Median"),
            (f"{data['lowest']:.0f}–{data['highest']:.0f}"
             if data["lowest"] is not None else "—", "Range"),
        ])

        if data["distribution"]:
            _report.card(surface, "Answer distribution", accent="#3498db")
            total = sum(count for _v, count in data["distribution"]) or 1
            _report.table(
                surface, ("Answer", "Count", "Share"),
                [(value, count, f"{count / total * 100:.0f}%")
                 for value, count in data["distribution"]],
                widths={"Answer": 200, "Count": 90, "Share": 90})

        if data["comments"]:
            _report.card(surface, f"Comments ({len(data['comments'])})",
                         accent="#16a34a")
            _report.table(surface, ("Response",),
                          [(c,) for c in data["comments"]],
                          widths={"Response": 620}, height=12)

        if not data["distribution"] and not data["comments"]:
            _report.verdict(surface, None, "No answers recorded",
                            "Nobody has answered this question yet.", neutral=True)
        window.lift()

    def export_results(self):
        """Export results to CSV or text file"""
        try:
            selection = self.results_eval_combo.get()
            if not selection:
                messagebox.showwarning(_("common.warning"), _("course_evaluation.messages.select_evaluation_first"))
                return

            eval_id = int(selection.split(':')[0])

            # Get results data
            results = ResultsAnalyticsManager.calculate_results(eval_id)

            if not results:
                messagebox.showwarning(_("common.warning"), _("course_evaluation.messages.no_results_available"))
                return

            # Ask user for file type and location
            from tkinter import filedialog
            file_path = filedialog.asksaveasfilename(
                parent=self.root,
                title=_("course_evaluation.dialogs.export_results_title"),
                defaultextension=".csv",
                filetypes=[
                    (_("course_evaluation.filetypes.csv"), "*.csv"),
                    (_("course_evaluation.filetypes.text"), "*.txt"),
                    (_("course_evaluation.filetypes.all"), "*.*")
                ],
                initialfile=f"evaluation_{eval_id}_results"
            )

            if not file_path:
                return  # User cancelled

            # Export based on file type
            if file_path.endswith('.csv'):
                import csv
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)

                    # Header row
                    writer.writerow([_("course_evaluation.export.evaluation_id"), eval_id])
                    writer.writerow([_("course_evaluation.export.export_date"), datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
                    writer.writerow([])  # Empty row

                    # Column headers
                    writer.writerow([_("course_evaluation.export.question_id"), _("course_evaluation.export.question_text"), _("course_evaluation.export.average_score"), _("course_evaluation.export.response_count")])

                    # Data rows
                    for result in results:
                        avg_score = result.get('average_score')
                        score_display = f"{avg_score:.2f}" if avg_score is not None else "N/A"
                        writer.writerow([
                            result.get('question_id', ''),
                            result.get('question_text', ''),
                            score_display,
                            result.get('response_count', 0)
                        ])

                    # Summary statistics
                    writer.writerow([])
                    writer.writerow([_("course_evaluation.export.summary_statistics")])
                    total_responses = sum(r.get('response_count', 0) for r in results) // max(len(results), 1)
                    # Calculate average, excluding None values
                    valid_scores = [r.get('average_score') for r in results if r.get('average_score') is not None]
                    avg_overall = sum(valid_scores) / len(valid_scores) if valid_scores else 0
                    writer.writerow([_("course_evaluation.export.total_questions"), len(results)])
                    writer.writerow([_("course_evaluation.export.avg_responses_per_question"), total_responses])
                    writer.writerow([_("course_evaluation.export.overall_avg_score"), f"{avg_overall:.2f}"])
            else:
                # Plain text export
                with open(file_path, 'w', encoding='utf-8') as txtfile:
                    txtfile.write(_("course_evaluation.results.header").format(id=eval_id) + "\n")
                    txtfile.write(_("course_evaluation.export.export_date_line").format(date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')) + "\n")
                    txtfile.write("=" * 80 + "\n\n")

                    for result in results:
                        avg_score = result.get('average_score')
                        score_display = f"{avg_score:.2f}" if avg_score is not None else "N/A"
                        txtfile.write(_("course_evaluation.results.question_id").format(id=result.get('question_id', '')) + "\n")
                        txtfile.write(_("course_evaluation.results.question").format(text=result.get('question_text', '')) + "\n")
                        txtfile.write(_("course_evaluation.results.average_score").format(score=score_display) + "\n")
                        txtfile.write(_("course_evaluation.results.responses").format(count=result.get('response_count', 0)) + "\n")
                        txtfile.write("-" * 80 + "\n\n")

                    # Summary
                    txtfile.write("=" * 80 + "\n")
                    txtfile.write(_("course_evaluation.export.summary_statistics") + "\n")
                    txtfile.write("=" * 80 + "\n")
                    total_responses = sum(r.get('response_count', 0) for r in results) // max(len(results), 1)
                    # Calculate average, excluding None values
                    valid_scores = [r.get('average_score') for r in results if r.get('average_score') is not None]
                    avg_overall = sum(valid_scores) / len(valid_scores) if valid_scores else 0
                    txtfile.write(_("course_evaluation.export.total_questions_line").format(count=len(results)) + "\n")
                    txtfile.write(_("course_evaluation.export.avg_responses_line").format(count=total_responses) + "\n")
                    txtfile.write(_("course_evaluation.export.overall_avg_line").format(score=f"{avg_overall:.2f}") + "\n")

            log_activity('export', 'evaluation_results', str(eval_id), {'file_path': file_path})
            messagebox.showinfo(_("common.success"), _("course_evaluation.messages.results_exported").format(path=file_path))

        except Exception as e:
            messagebox.showerror(_("common.error"), _("course_evaluation.messages.failed_export_results").format(error=e))

    def email_results_to_admin(self):
        """Email evaluation results report to admin users"""
        try:
            # Get report content from the results text widget
            report_content = (getattr(self, '_results_plain', '') or '').strip()
            if not report_content:
                messagebox.showwarning(_("common.warning"),
                                       _t('gui.academics.course_management_gui.course_evaluation.dialogs.no_results_to_email_please_calculate_results_first', default="No results to email. Please calculate results first."))
                return

            selection = self.results_eval_combo.get()
            eval_label = selection if selection else "Unknown"

            # Get admin emails from DB
            admin_emails = []
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT email FROM users WHERE role = 'admin' AND email IS NOT NULL AND email != ''"
                )
                admin_emails = [row[0] for row in cursor.fetchall()]

            if not admin_emails:
                messagebox.showerror(_("common.error"),
                                     _t('gui.academics.course_management_gui.course_evaluation.dialogs.no_admin_email_addresses_found_in_the_database', default="No admin email addresses found in the database."))
                return

            from education_system.systems.university.infrastructure.email.email_service import send_email

            subject = f"Course Evaluation Results - {eval_label} - {datetime.now().strftime('%Y-%m-%d')}"
            body = (
                f"COURSE EVALUATION RESULTS REPORT\n"
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"{'=' * 60}\n\n"
                f"{report_content}\n"
            )

            success = 0
            failed = []
            for email_addr in admin_emails:
                try:
                    result = send_email(recipient_email=email_addr, subject=subject, body=body)
                    if result is not False:
                        success += 1
                    else:
                        failed.append(email_addr)
                except Exception:
                    failed.append(email_addr)

            if success and not failed:
                messagebox.showinfo(_("common.success"),
                                    f"Report emailed to {success} admin(s):\n" + "\n".join(admin_emails))
            elif success:
                messagebox.showwarning(_t('gui.academics.course_management_gui.course_evaluation.dialogs.partial_success', default="Partial Success"),
                                       f"Sent to {success}, failed for:\n" + "\n".join(failed))
            else:
                messagebox.showerror(_("common.error"), _t('gui.academics.course_management_gui.course_evaluation.dialogs.failed_to_send_report_to_any_admin_address', default="Failed to send report to any admin address."))

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to email results: {e}")

    def view_evaluation_details(self):
        """View detailed evaluation information"""
        selected = self.evaluations_tree.selection()
        if not selected:
            messagebox.showwarning(_("common.warning"), _("course_evaluation.messages.select_evaluation_first"))
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
                        _("course_evaluation.details.evaluation_id").format(id=eval_data[0]) + "\n" +
                        _("course_evaluation.details.module").format(module=eval_data[1]) + "\n" +
                        _("course_evaluation.details.academic_year").format(year=eval_data[2]) + "\n" +
                        _("course_evaluation.details.semester").format(semester=eval_data[3]) + "\n" +
                        _("course_evaluation.details.instructor").format(instructor=eval_data[4]) + "\n" +
                        _("course_evaluation.details.start_date").format(date=eval_data[6]) + "\n" +
                        _("course_evaluation.details.end_date").format(date=eval_data[7]) + "\n" +
                        _("course_evaluation.details.responses").format(count=eval_data[8]) + "\n"
                    )
                    messagebox.showinfo(_("course_evaluation.dialogs.evaluation_details_title"), info)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("course_evaluation.messages.failed_load_details").format(error=e))


def launch_course_evaluation_gui(root, auth):
    """Launch the Course Evaluation GUI"""
    try:
        if not auth or not hasattr(auth, 'current_user') or not auth.current_user:
            messagebox.showerror(_("common.error"), _("course_evaluation.messages.must_be_logged_in"))
            return

        CourseEvaluationGUI(root, auth)

    except Exception as e:
        messagebox.showerror(_("common.error"), _("course_evaluation.messages.failed_launch").format(error=e))


__all__ = ['CourseEvaluationGUI', 'launch_course_evaluation_gui']
