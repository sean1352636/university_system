import tkinter as tk
from tkinter import ttk, messagebox
import threading
import traceback

from education_system.university_system.modules.shared.utils.i18n import get_text as _

from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui._imports import (
    GradeTrackingApp,
    GRADE_TRACKING_GUI_AVAILABLE,
    GRADE_TRACKING_CLI_AVAILABLE,
    init_basic_database,
    init_enhanced_grades_db,
    display_enhanced_grade_menu,
    grade_curve_analysis_menu,
    learning_outcome_menu,
    competency_assessment_menu,
    predictive_analytics_menu,
    performance_analysis_menu,
)
from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui.learning_outcomes import LearningOutcomesMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui.performance_analytics import PerformanceAnalyticsMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui.curve_analysis import CurveAnalysisMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui.competency import CompetencyMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui.predictive_analytics import PredictiveAnalyticsMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui.grade_calculations import GradeCalculationsMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui.student_management import StudentManagementMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui.statistics import StatisticsMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui.trends import TrendsMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui.predictions import PredictionsMixin


class GradeTrackingManagementGUI(
    LearningOutcomesMixin,
    PerformanceAnalyticsMixin,
    CurveAnalysisMixin,
    CompetencyMixin,
    PredictiveAnalyticsMixin,
    GradeCalculationsMixin,
    StudentManagementMixin,
    StatisticsMixin,
    TrendsMixin,
    PredictionsMixin,
):
    """Grade Tracking management GUI wrapper"""

    def __init__(self, parent_root, auth_manager):
        self.root = parent_root
        self.auth = auth_manager

    def show_grade_tracking_gui(self):
        """Launch the Grade Tracking GUI in a child window"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.messages.login_required"))
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_own_grades') or
                self.auth.check_permission('manage_module_grades')):
            messagebox.showerror(_("common.error"), _("grades.messages.no_permission_access"))
            return

        try:
            if GRADE_TRACKING_GUI_AVAILABLE and GradeTrackingApp:
                # Withdraw → set centered geometry → build → deiconify so
                # the WM maps the window once, at the right place. Setting
                # geometry on an already-mapped window after ``transient``
                # let some WMs ignore the new position.
                grade_window = tk.Toplevel(self.root)
                grade_window.withdraw()
                _w, _h = 1400, 900
                grade_window.geometry("%dx%d+%d+%d" % (
                    _w, _h,
                    (grade_window.winfo_screenwidth() - _w) // 2,
                    (grade_window.winfo_screenheight() - _h) // 2))
                grade_window.minsize(1200, 800)
                grade_window.configure(bg='#f0f0f0')
                grade_window.title(_("grades.title"))

                try:
                    grade_window.transient(self.root)
                except Exception:
                    pass

                # Initialize the Grade Tracking GUI
                grade_gui = GradeTrackingApp(grade_window)

                # Pass auth context if supported
                if hasattr(grade_gui, 'set_auth'):
                    grade_gui.set_auth(self.auth)
                elif hasattr(grade_gui, 'auth'):
                    grade_gui.auth = self.auth

                grade_window.deiconify()
                print("Grade Tracking GUI opened successfully")

            else:
                # Fallback to CLI menu
                messagebox.showinfo(_("grades.title"), _("grades.messages.gui_not_available"))
                try:
                    display_enhanced_grade_menu()
                except ImportError:
                    messagebox.showerror(_("common.error"), _("grades.messages.system_not_available"))

        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.messages.failed_to_open").format(error=str(e)))
            print(f"Grade Tracking error: {e}")

    def show_grades(self):
        """Alias method for compatibility"""
        self.show_grade_tracking_gui()

    # Database initialization methods
    def initialize_basic_database(self):
        """Initialize basic grade tracking database tables"""
        try:
            return init_basic_database()
        except Exception as e:
            messagebox.showerror(_("grades.errors.database_error"), _("grades.messages.failed_init_db").format(error=str(e)))
            print(f"Database initialization error: {e}")
            return False

    def initialize_enhanced_database(self):
        """Initialize enhanced grades database with all required tables"""
        try:
            return init_enhanced_grades_db()
        except Exception as e:
            messagebox.showerror(_("grades.errors.database_error"), _("grades.messages.failed_init_enhanced_db").format(error=str(e)))
            print(f"Enhanced database initialization error: {e}")
            return False

    # Menu access methods
    def show_enhanced_grade_menu(self):
        """Display the enhanced grade and performance tracking menu (CLI fallback)"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.messages.login_required"))
            return

        try:
            if GRADE_TRACKING_CLI_AVAILABLE:
                # Run CLI menu in a separate thread to prevent GUI blocking
                thread = threading.Thread(target=display_enhanced_grade_menu, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.messages.menu_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.messages.failed_open_menu").format(error=str(e)))
            print(f"Grade menu error: {e}")

    def show_curve_analysis_menu(self):
        """Display the grade curve analysis menu"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.messages.login_required_curve"))
            return

        try:
            if GRADE_TRACKING_CLI_AVAILABLE:
                thread = threading.Thread(target=grade_curve_analysis_menu, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.messages.curve_menu_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.messages.failed_open_curve_menu").format(error=str(e)))
            print(f"Curve analysis menu error: {e}")

    def show_learning_outcome_menu(self):
        """Display the learning outcome tracking menu"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.messages.login_required_outcomes"))
            return

        try:
            if GRADE_TRACKING_CLI_AVAILABLE:
                thread = threading.Thread(target=learning_outcome_menu, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.messages.outcome_menu_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.messages.failed_open_outcome_menu").format(error=str(e)))
            print(f"Learning outcome menu error: {e}")

    def show_competency_assessment_menu(self):
        """Display the competency-based assessment menu"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.messages.login_required_competency"))
            return

        try:
            if GRADE_TRACKING_CLI_AVAILABLE:
                thread = threading.Thread(target=competency_assessment_menu, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.messages.competency_menu_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.messages.failed_open_competency_menu").format(error=str(e)))
            print(f"Competency assessment menu error: {e}")

    def show_predictive_analytics_menu(self):
        """Display the predictive analytics menu"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.messages.login_required_analytics"))
            return

        try:
            if GRADE_TRACKING_CLI_AVAILABLE:
                thread = threading.Thread(target=predictive_analytics_menu, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.messages.analytics_menu_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.messages.failed_open_analytics_menu").format(error=str(e)))
            print(f"Predictive analytics menu error: {e}")

    def show_performance_analysis_menu(self):
        """Display the performance analysis menu"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.messages.login_required_performance"))
            return

        try:
            if GRADE_TRACKING_CLI_AVAILABLE:
                thread = threading.Thread(target=performance_analysis_menu, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.messages.performance_menu_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.messages.failed_open_performance_menu").format(error=str(e)))
            print(f"Performance analysis menu error: {e}")

    # --- AI Auto-Grading (staff/admin only) ---

    def show_auto_grading(self):
        """Launch AI Auto-Grading window (staff/admin only)"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.messages.login_required"))
            return

        role = (self.auth.current_user.get('role') or '').lower()
        if role not in ('admin', 'staff', 'instructor', 'faculty'):
            messagebox.showerror(_("common.error"), _("grades.messages.no_permission_access"))
            return

        try:
            from education_system.university_system.infrastructure.database.db import get_connection, transaction
            from education_system.university_system.infrastructure.database.schemas.ai_features_schemas import init_ai_features_system_db
            try:
                init_ai_features_system_db()
            except Exception:
                pass

            window = tk.Toplevel(self.root)
            window.title(_("ai_features.autograding.title"))
            window.geometry("1000x700")
            window.minsize(800, 500)
            try:
                window.transient(self.root)
            except Exception:
                pass

            # Header
            header = ttk.Frame(window)
            header.pack(fill=tk.X, padx=10, pady=(10, 5))
            ttk.Label(header, text=_("ai_features.autograding.title"),
                      font=('Arial', 16, 'bold')).pack(side=tk.LEFT)
            ttk.Button(header, text=_("ai_features.autograding.grade_submission"),
                       command=lambda: self._auto_grade_submission(window)).pack(side=tk.RIGHT, padx=5)
            ttk.Button(header, text=_("common.refresh"),
                       command=lambda: self._load_grading_results(grading_tree, window)).pack(side=tk.RIGHT, padx=5)

            # Grading results treeview
            tree_frame = ttk.Frame(window)
            tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
            grading_tree = ttk.Treeview(tree_frame,
                                        columns=('ID', 'Submission', 'Type', 'Score',
                                                 'Max', 'Confidence', 'Review', 'Graded'),
                                        show='tree headings',
                                        yscrollcommand=v_scroll.set)
            v_scroll.config(command=grading_tree.yview)
            grading_tree.heading('#0', text='')
            grading_tree.column('#0', width=30)

            column_names = ['id', 'submission', 'type', 'score', 'max', 'confidence', 'review', 'graded']
            columns_config = [
                ('ID', 60), ('Submission', 100), ('Type', 150), ('Score', 80),
                ('Max', 80), ('Confidence', 90), ('Review', 120), ('Graded', 150)
            ]
            for (col, width), name in zip(columns_config, column_names):
                grading_tree.heading(col, text=_("ai_features.columns." + name))
                grading_tree.column(col, width=width)

            grading_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

            grading_tree.bind('<Double-1>', lambda e: self._view_grading_details(grading_tree, window))

            self._load_grading_results(grading_tree, window)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to open auto-grading: {e}")
            traceback.print_exc()

    def _load_grading_results(self, tree, parent_window):
        """Load auto-grading results into treeview"""
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            for item in tree.get_children():
                tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM ai_grading_results
                    ORDER BY graded_at DESC LIMIT 500
                ''')
                for row in cursor.fetchall():
                    values = (
                        row['grading_id'],
                        row['submission_id'],
                        row['assignment_type'],
                        f"{row['auto_score']:.1f}" if row['auto_score'] is not None else '0.0',
                        f"{row['max_score']:.1f}" if row['max_score'] is not None else '0.0',
                        f"{row['confidence_score']:.2f}" if row['confidence_score'] else '0.00',
                        'Yes' if row['requires_manual_review'] else 'No',
                        row['graded_at'][:16] if row['graded_at'] else ''
                    )
                    tree.insert('', 'end', values=values)
        except Exception as e:
            messagebox.showerror(_("common.error"), _("ai_features.autograding.load_error").format(error=str(e)))

    def _auto_grade_submission(self, parent_window):
        """Grade a submission dialog"""
        from education_system.university_system.infrastructure.database.db import transaction

        dialog = tk.Toplevel(parent_window)
        dialog.title(_("ai_features.autograding.grade_title"))
        dialog.geometry("600x550")
        dialog.transient(parent_window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=_("ai_features.labels.submission_id")).grid(row=0, column=0, sticky='w', pady=5)
        sub_id_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=sub_id_var, width=40).grid(row=0, column=1, pady=5)

        ttk.Label(main_frame, text=_("ai_features.labels.assignment_type")).grid(row=1, column=0, sticky='w', pady=5)
        type_var = tk.StringVar()
        ttk.Combobox(main_frame, textvariable=type_var, width=38,
                     values=['essay', 'quiz', 'project', 'homework', 'exam']).grid(row=1, column=1, pady=5)

        ttk.Label(main_frame, text=_("ai_features.labels.auto_score")).grid(row=2, column=0, sticky='w', pady=5)
        score_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=score_var, width=40).grid(row=2, column=1, pady=5)

        ttk.Label(main_frame, text=_("ai_features.labels.max_score")).grid(row=3, column=0, sticky='w', pady=5)
        max_var = tk.StringVar(value='100')
        ttk.Entry(main_frame, textvariable=max_var, width=40).grid(row=3, column=1, pady=5)

        ttk.Label(main_frame, text=_("ai_features.labels.criteria")).grid(row=4, column=0, sticky='nw', pady=5)
        criteria_text = tk.Text(main_frame, width=40, height=4)
        criteria_text.grid(row=4, column=1, pady=5)

        ttk.Label(main_frame, text=_("ai_features.labels.feedback")).grid(row=5, column=0, sticky='nw', pady=5)
        feedback_text = tk.Text(main_frame, width=40, height=6)
        feedback_text.grid(row=5, column=1, pady=5)

        ttk.Label(main_frame, text=_("ai_features.labels.confidence_score")).grid(row=6, column=0, sticky='w', pady=5)
        conf_var = tk.StringVar(value='0.8')
        ttk.Entry(main_frame, textvariable=conf_var, width=40).grid(row=6, column=1, pady=5)

        review_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(main_frame, text=_("ai_features.labels.requires_review"),
                        variable=review_var).grid(row=7, column=1, sticky='w', pady=5)

        def save_grading():
            try:
                sub_id = int(sub_id_var.get())
                asgn_type = type_var.get().strip()
                auto_score = float(score_var.get())
                max_score = float(max_var.get())
                criteria = criteria_text.get('1.0', 'end').strip()
                feedback = feedback_text.get('1.0', 'end').strip()
                confidence = float(conf_var.get())
                requires_review = 1 if review_var.get() else 0

                with transaction() as conn:
                    conn.execute('''
                        INSERT INTO ai_grading_results
                        (submission_id, assignment_type, auto_score, max_score,
                         grading_criteria, feedback_generated, confidence_score, requires_manual_review)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (sub_id, asgn_type, auto_score, max_score, criteria, feedback, confidence, requires_review))

                messagebox.showinfo(_("common.success"), _("ai_features.autograding.save_success"))
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"), _("ai_features.autograding.save_error").format(error=str(e)))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=8, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text=_("ai_features.buttons.save"), command=save_grading).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_("ai_features.buttons.cancel"), command=dialog.destroy).pack(side='left', padx=5)

    def _view_grading_details(self, tree, parent_window):
        """View grading details"""
        selection = tree.selection()
        if not selection:
            messagebox.showinfo(_("common.info"), _("ai_features.autograding.no_selection"))
            return

        item = tree.item(selection[0])
        grading_id = item['values'][0]

        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM ai_grading_results WHERE grading_id = ?', (grading_id,))
                grading = cursor.fetchone()

                if not grading:
                    messagebox.showerror(_("common.error"), _("ai_features.autograding.not_found"))
                    return

                dialog = tk.Toplevel(parent_window)
                dialog.title(_("ai_features.autograding.details_title").format(id=grading_id))
                dialog.geometry("700x600")
                dialog.transient(parent_window)

                main_frame = ttk.Frame(dialog, padding=20)
                main_frame.pack(fill='both', expand=True)

                percentage = (grading['auto_score'] / grading['max_score'] * 100) if grading['max_score'] > 0 else 0
                confidence_str = f"{grading['confidence_score']:.2f}" if grading['confidence_score'] is not None else 'N/A'

                details = (
                    f"Grading ID: {grading['grading_id']}\n"
                    f"Submission ID: {grading['submission_id']}\n"
                    f"Assignment Type: {grading['assignment_type']}\n"
                    f"Auto Score: {grading['auto_score']}/{grading['max_score']} ({percentage:.1f}%)\n"
                    f"Confidence Score: {confidence_str}\n"
                    f"Requires Manual Review: {'Yes' if grading['requires_manual_review'] else 'No'}\n"
                    f"Manual Override Score: {grading['manual_override_score'] if grading['manual_override_score'] else 'None'}\n"
                    f"Graded At: {grading['graded_at']}\n\n"
                    f"Grading Criteria:\n{grading['grading_criteria'] or 'Not specified'}\n\n"
                    f"Feedback Generated:\n{grading['feedback_generated'] or 'No feedback'}"
                )

                text_widget = tk.Text(main_frame, wrap='word', width=80, height=30)
                text_widget.pack(fill='both', expand=True)
                text_widget.insert('1.0', details)
                text_widget.config(state='disabled')

                ttk.Button(main_frame, text=_("ai_features.buttons.close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("ai_features.autograding.details_error").format(error=str(e)))
