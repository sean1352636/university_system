"""The AI Content Detector window (staff).

It always runs as the person signed in to the University window that
opened it; with nobody signed in, or a signed-in student, it refuses to open
(students see their own readings in the Academic Integrity window). Every
reading is an indication to review with the student, never a verdict.

The views live in sibling modules and are imported the first time they are
opened (:data:`_VIEW_METHODS`); the detector backend is built on first use.
"""

import logging
import sys

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)

STAFF_ROLES = ("staff", "instructor", "lecturer", "teacher", "faculty", "admin",
               "administrator", "superadmin")

sys.modules.setdefault(
    "education_system.systems.university.domains.integrity.interfaces.gui.ai_detector_gui",
    sys.modules[__name__],
)


def _signed_in_user(auth):
    """The ``current_user`` dict behind any of the university's auth objects."""
    if isinstance(auth, dict):
        return auth if auth.get("username") else None
    user = getattr(auth, "current_user", None) if auth is not None else None
    if callable(user):
        try:
            user = user()
        except Exception:
            user = None
    if user is None and hasattr(auth, "get_current_user"):
        try:
            user = auth.get_current_user()
        except Exception:
            user = None
    return user if isinstance(user, dict) and user.get("username") else None


class AIDetectorGUI:
    """The AI Content Detector, for the signed-in member of staff."""

    def __init__(self, root=None, auth=None, detector_instance=None):
        self.root = root if root else tk.Tk()
        self.colors = {
            'bg_primary': '#f0f0f0',
            'bg_secondary': '#e0e0e0',
            'bg_tertiary': '#ffffff',
            'accent': '#0078d4',
            'accent_hover': '#106ebe',
            'success': '#107c10',
            'warning': '#ff8c00',
            'danger': '#d13438',
            'text_primary': '#000000',
            'text_secondary': '#5a5a5a',
            'border': '#d0d0d0'
        }
        self.auth = auth
        self.user = _signed_in_user(auth)
        self._detector = detector_instance
        self.status_text = None
        self.progress_var = None
        self.progress_bar = None
        self.analysis_results = {}
        self.current_submission_id = None
        self.refused = False

        refusal = self._refusal()
        if refusal:
            self.refused = True
            messagebox.showerror(_t('gui.academics.ai_detector.main.dialogs.initialization_error',
                                    default="AI Content Detector"), refusal, parent=self.root)
            self.root.after(10, self.root.destroy)
            return

        self.setup_window()
        self.setup_styles()
        self.create_main_interface()

    def _refusal(self):
        """Why this person may not open the detector, or ``None``."""
        if self.user is None:
            return "Sign in to the University system to use the AI Content Detector."
        role = str(self.user.get("role") or "").lower()
        if not role:
            from education_system.systems.university.application.integrity import (
                access as integrity_access,
            )
            from education_system.systems.university.infrastructure.database.db import (
                get_connection,
            )
            conn = get_connection(row_factory=False)
            try:
                who = integrity_access.from_user(conn, self.user)
                role = who.role if who else ""
            finally:
                conn.close()
        if role not in STAFF_ROLES:
            return ("The AI Content Detector is for staff. Your own readings are in Academic "
                    "Integrity (My AI-writing readings).")
        return None

    @property
    def detector(self):
        """The detector backend, built on first use as the signed-in person."""
        if self._detector is None:
            from education_system.systems.university.shared.ai.ai_detector.detector import (
                AIDetector,
            )
            self._detector = AIDetector(auth=self.auth)
        elif getattr(self._detector, "current_user", None) is None and self.auth is not None:
            self._detector.set_auth(self.auth)
        return self._detector

    @detector.setter
    def detector(self, value):
        self._detector = value

    def setup_window(self):
        """Setup main window properties"""
        self.root.title(_t('gui.academics.ai_detector.main.windows.ai_content_detector', default="AI Content Detector — indicators for review") + f" — {self.user.get('username')}")

        # Centre from the size actually applied. This used to compute the
        # offsets from a hard-coded 1400x900, which on a 1366x768 display is
        # larger than the screen and gives negative offsets — putting the
        # title bar above the top edge.
        from education_system.platform.delivery.gui.window_sizing import center
        center(self.root, 1400, 900, minsize=(1200, 800))

        # Configure window icon (if available)
        try:
            self.root.iconbitmap('ai_detector_icon.ico')
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)


    def setup_styles(self):
        """Setup basic theme to match main GUI"""
        # ttk.Style is process-global. Only switch themes when this is
        # the standalone Tk root; inherit the parent's theme otherwise.
        self.style = ttk.Style()
        prev_theme = self.style.theme_use()
        if not isinstance(self.root, tk.Toplevel):
            try:
                self.style.theme_use('clam')
            except tk.TclError:
                pass
            self.root.bind(
                "<Destroy>",
                lambda _e, p=prev_theme, s=self.style: (
                    s.theme_use(p) if _e.widget is self.root else None
                ),
                add="+",
            )


    def create_main_interface(self):
        """Create the main interface with button navigation and scrollbar"""
        # Add return to main menu button at the top
        return_btn = ttk.Button(
            self.root,
            text=_t('gui.academics.ai_detector.main.buttons.return_to_main_menu', default="← Return to Main Menu"),
            command=self.return_to_main_menu
        )
        return_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title bar
        self.create_title_bar(main_frame)

        # Status bar first so update_status/show_progress are safe
        self.create_status_bar(main_frame)

        # Create main content area with sidebar navigation
        content_container = ttk.Frame(main_frame)
        content_container.pack(fill='both', expand=True, pady=(10, 0))

        # Left sidebar with scrollable button navigation
        sidebar_container = ttk.Frame(content_container, style='Card.TFrame')
        sidebar_container.pack(side='left', fill='y', padx=(0, 10))

        # Add scrollbar to sidebar
        sidebar_canvas = tk.Canvas(sidebar_container, width=200, bg=self.colors['bg_tertiary'],
                                   highlightthickness=0)
        scrollbar = ttk.Scrollbar(sidebar_container, orient='vertical', command=sidebar_canvas.yview)
        self.nav_frame = ttk.Frame(sidebar_canvas)

        self.nav_frame.bind('<Configure>',
                           lambda e: sidebar_canvas.configure(scrollregion=sidebar_canvas.bbox('all')))

        sidebar_canvas.create_window((0, 0), window=self.nav_frame, anchor='nw')
        sidebar_canvas.configure(yscrollcommand=scrollbar.set)

        sidebar_canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Right content area for displaying selected view
        self.content_area = ttk.Frame(content_container)
        self.content_area.pack(side='left', fill='both', expand=True)

        # Create navigation buttons
        self.current_view = None
        ttk.Button(self.nav_frame, text=_t('gui.academics.ai_detector.main.buttons.return_to_homescreen', default="🏠 Return to Homescreen"), width=25,
                   command=self.return_to_main_menu).pack(fill='x', padx=5, pady=(0, 6))
        self.create_navigation_buttons()

        # Show default view (the other views load when first opened)
        self.show_view('analysis')


    def create_navigation_buttons(self):
        """Create navigation buttons in sidebar"""
        nav_buttons = [
            ("📝 Text Analysis", 'analysis'),
            ("📜 History", 'history'),
            ("📊 Statistics", 'statistics'),
            ("⚙️ Settings", 'settings'),
            ("🚀 Advanced", 'advanced'),
            ("🔄 Real-Time Monitor", 'realtime'),
            ("🤝 Federated Learning", 'federated'),
            ("🔒 Compliance", 'compliance'),
            ("⚖️ Bias Detection", 'bias'),
            ("🔮 Predictive Analytics", 'predictive'),
            ("✅ Self-Check", 'selfcheck'),
            ("🛡️ Anti-Evasion", 'adversarial'),
            ("🔗 Blockchain Audit", 'blockchain'),
            ("📊 Benchmarking", 'benchmarking'),
            ("🎨 Multi-Modal", 'multimodal'),
            ("📚 Citation Check", 'citation'),
            ("⏱️ Temporal Analysis", 'temporal'),
            ("🔌 API Integration", 'api'),
            ("📸 Visual Analysis", 'visual'),
            ("🔔 Alerts & Notifications", 'alerts'),
            ("📝 Batch Processing", 'batch'),
            ("🎓 Course Management", 'course'),
            ("🔧 Model Management", 'model'),
            ("🛡️ Security & Audit", 'security'),
            ("🔗 Integrations", 'integrations'),
            ("🔬 Enhanced Detection", 'enhanced_detection'),
            ("👥 Student Management", 'student_mgmt'),
            ("📊 Advanced Analytics", 'advanced_analytics'),
            ("💾 Data Management", 'data'),
            ("🖥️ System Monitoring", 'system')
        ]

        for text, view_id in nav_buttons:
            btn = ttk.Button(self.nav_frame, text=text, width=25,
                           command=lambda v=view_id: self.show_view(v))
            btn.pack(fill='x', padx=5, pady=2)


    def create_title_bar(self, parent):
        """Create application title bar"""
        title_frame = ttk.Frame(parent, style='Card.TFrame')
        title_frame.pack(fill='x', pady=(0, 10))

        # Title and subtitle
        title_label = ttk.Label(title_frame, text=_t('gui.academics.ai_detector.main.labels.ai_content_detector', default="AI Content Detector"), style='Title.TLabel')
        title_label.pack(side='left', padx=15, pady=10)

        subtitle_label = ttk.Label(title_frame, text=_t('gui.academics.ai_detector.main.labels.indicators_not_evidence', default="Indicators for review — not evidence"),
                                 style='Subtitle.TLabel')
        subtitle_label.pack(side='left', padx=(10, 0), pady=10)

        # Status indicator
        self.status_indicator = ttk.Label(title_frame, text=_t('gui.academics.ai_detector.main.labels.ready_variant_2', default="● Ready"),
                                        foreground=self.colors['success'])
        self.status_indicator.pack(side='right', padx=15, pady=10)


    def create_status_bar(self, parent):
        """Create status bar"""
        self.status_frame = ttk.Frame(parent)
        self.status_frame.pack(fill='x', pady=(10, 0))

        # Status text
        self.status_text = ttk.Label(self.status_frame, text=_t('gui.academics.ai_detector.main.labels.ready', default="Ready"), style='Subtitle.TLabel')
        self.status_text.pack(side='left')

        # Progress bar (initially hidden)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.status_frame, variable=self.progress_var,
                                          mode='determinate', length=200)

        # Right side info
        self.info_label = ttk.Label(self.status_frame, text="", style='Subtitle.TLabel')
        self.info_label.pack(side='right')


    def show_view(self, view_id):
        """Show the selected view in content area"""
        if self.current_view == view_id:
            return

        # Clear current content
        for widget in self.content_area.winfo_children():
            widget.destroy()

        self.current_view = view_id

        # Create the appropriate view
        view_frame = ttk.Frame(self.content_area)
        view_frame.pack(fill='both', expand=True)

        try:
            self._create_view_content(view_id, view_frame)
        except Exception as e:
            logger.exception("AI detector view %s failed", view_id)
            for widget in view_frame.winfo_children():
                widget.destroy()
            ttk.Label(view_frame, text=f"Error loading view '{view_id}': {e}",
                      foreground='red', wraplength=600).pack(expand=True, pady=20)

    def _create_view_content(self, view_id, view_frame):
        """Create the content for a specific view"""
        if view_id == 'analysis':
            self.create_analysis_view(view_frame)
        elif view_id == 'history':
            self.create_history_view(view_frame)
        elif view_id == 'statistics':
            self.create_statistics_view(view_frame)
        elif view_id == 'settings':
            self.create_settings_view(view_frame)
        elif view_id == 'advanced':
            self.create_advanced_view(view_frame)
        elif view_id == 'realtime':
            self.create_real_time_monitoring_view(view_frame)
        elif view_id == 'federated':
            self.create_federated_learning_view(view_frame)
        elif view_id == 'compliance':
            self.create_compliance_view(view_frame)
        elif view_id == 'bias':
            self.create_bias_detection_view(view_frame)
        elif view_id == 'predictive':
            self.create_predictive_analytics_view(view_frame)
        elif view_id == 'selfcheck':
            self.create_student_self_check_view(view_frame)
        elif view_id == 'adversarial':
            self.create_adversarial_detection_view(view_frame)
        elif view_id == 'blockchain':
            self.create_blockchain_audit_view(view_frame)
        elif view_id == 'benchmarking':
            self.create_benchmarking_view(view_frame)
        elif view_id == 'multimodal':
            self.create_multi_modal_analysis_view(view_frame)
        elif view_id == 'citation':
            self.create_citation_verification_view(view_frame)
        elif view_id == 'temporal':
            self.create_temporal_analysis_view(view_frame)
        elif view_id == 'api':
            self.create_api_integration_view(view_frame)
        elif view_id == 'visual':
            self.create_visual_analysis_view(view_frame)
        elif view_id == 'alerts':
            self.create_alerts_notifications_view(view_frame)
        elif view_id == 'batch':
            self.create_batch_processing_view(view_frame)
        elif view_id == 'course':
            self.create_course_management_view(view_frame)
        elif view_id == 'model':
            self.create_model_management_view(view_frame)
        elif view_id == 'security':
            self.create_security_audit_view(view_frame)
        elif view_id == 'integrations':
            self.create_integrations_view(view_frame)
        elif view_id == 'enhanced_detection':
            self.create_enhanced_detection_view(view_frame)
        elif view_id == 'student_mgmt':
            self.create_student_management_view(view_frame)
        elif view_id == 'advanced_analytics':
            self.create_advanced_analytics_view(view_frame)
        elif view_id == 'data':
            self.create_data_export_import_view(view_frame)
        elif view_id == 'system':
            self.create_system_monitoring_view(view_frame)


    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            if isinstance(self.root, tk.Toplevel):
                # Just close the child window
                self.root.destroy()
            else:
                # Running standalone, need to create main GUI
                self.root.destroy()
                from education_system.systems.university.shell.gui.main import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception:
            logger.exception("Returning to the main menu failed")


    def update_status(self, message):
        """Update status bar message safely, or print as fallback"""
        try:
            if getattr(self, "status_text", None) is not None:
                self.status_text.config(text=message)
                if getattr(self, "root", None):
                    self.root.update_idletasks()
                return
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
        logger.info("AI detector: %s", message)


    def show_progress(self, show=True):
        """Show/hide progress bar safely"""
        bar = getattr(self, "progress_bar", None)
        if bar is None:
            return
        try:
            if show:
                bar.pack(side='right', padx=(10, 0))
                bar.start()
            else:
                bar.stop()
                bar.pack_forget()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)


    def run(self):
        """Start the GUI application"""
        try:
            if self.refused:
                return
            self.root.deiconify()

            # Start the main loop
            self.root.mainloop()

        except Exception as e:
            messagebox.showerror(_t('gui.academics.ai_detector.main.dialogs.application_error', default="Application Error"), f"Failed to start application: {str(e)}")


# The views' functions are bound to the window class lazily: each view
# module is imported the first time one of its functions is used, so opening
# the window imports only the views shown.
_PACKAGE = "education_system.systems.university.domains.integrity.interfaces.gui.ai_detector"

_VIEW_METHODS = {
    'analysis_view': (
        'create_analysis_view', 'create_sentences_tab', 'create_input_section',
        'create_results_section',
        'show_empty_results', 'load_file', 'clear_input', 'analyze_text', 'display_results',
        'create_score_display', 'create_detailed_analysis', 'create_pattern_tab',
        'create_pattern_indicator', 'create_sentence_tab', 'create_advanced_analysis_tab',
        'create_advanced_analysis_section', 'create_recommendations', 'analysis_error',
        'get_risk_color', 'get_risk_text', 'update_word_count',
    ),
    'history_view': (
        'create_history_view', 'refresh_history', 'clear_filter', 'view_submission_details',
        'show_submission_details_window',
    ),
    'statistics_view': (
        'create_statistics_view', 'create_stats_cards', 'create_stat_card',
        'create_charts_section', 'create_risk_distribution_chart', 'refresh_statistics',
    ),
    'settings_advanced_view': (
        'create_settings_view', 'apply_settings', 'create_advanced_view', 'create_ml_section',
        'train_models', 'training_complete', 'training_error', 'show_model_status',
    ),
    'realtime_federated_view': (
        'create_real_time_monitoring_view', 'start_real_time_monitoring',
        'stop_real_time_monitoring', 'sweep_missing_readings', 'queue_text_for_reading',
        'update_queue_status', 'create_federated_learning_view', 'initialize_federation',
        'contribute_model_update', 'import_federated_update', 'download_global_model',
    ),
    'compliance_bias_view': (
        'create_compliance_view', 'generate_compliance_report',
        'show_compliance_report_window', 'show_data_retention_status',
        'show_consent_management', 'create_bias_detection_view', 'analyze_institutional_bias',
        'display_bias_analysis', 'create_predictive_analytics_view', 'predict_student_risk',
        'display_risk_prediction', 'train_risk_model', 'show_model_performance',
        'create_student_self_check_view', 'run_self_check', 'show_self_check_results',
    ),
    'blockchain_adversarial_view': (
        'create_adversarial_detection_tab', 'create_adversarial_detection_view',
        'test_adversarial_detection', 'show_adversarial_results',
        'create_blockchain_audit_tab', 'create_blockchain_audit_view', 'mine_blockchain_block',
        'verify_blockchain_integrity', 'view_blockchain_history', 'update_blockchain_display',
        'create_benchmarking_tab', 'create_benchmarking_view', 'generate_benchmark_report',
        'display_benchmark_report',
    ),
    'multimodal_citation_view': (
        'create_multi_modal_analysis_tab', 'create_multi_modal_analysis_view',
        'upload_images_for_analysis', 'analyze_image_text_consistency',
        'analyze_code_submission', 'show_multimodal_results', 'show_code_analysis_results',
        'create_citation_verification_tab', 'create_citation_verification_view',
        'verify_citations', 'show_citation_results', 'create_temporal_analysis_tab',
        'create_temporal_analysis_view', 'analyze_writing_speed',
        'analyze_submission_patterns', 'show_temporal_results', 'show_submission_patterns',
    ),
    'api_visual_view': (
        'create_api_integration_view', 'register_external_api', 'test_api_connection',
        'show_api_performance', 'compare_api_results', 'run_ensemble_prediction',
        'show_ensemble_results', 'create_visual_analysis_view', 'generate_text_heatmap',
        'display_text_heatmap', 'generate_writing_flow', 'display_writing_flow',
        'generate_complexity_viz',
    ),
    'alerts_course_view': (
        'create_alerts_notifications_view', 'view_alert_queue', 'dismiss_alert',
        'escalate_to_dean', 'configure_alert_thresholds', 'setup_email_alerts',
        'create_course_management_view', '_load_assignment_profiles',
        '_load_courses_for_dashboard', 'create_assignment_profile', 'set_assignment_baseline',
        'compare_against_assignment_baseline', 'view_course_integrity_dashboard',
        'generate_course_end_report',
    ),
    'batch_processing_view': (
        'create_batch_processing_section', 'create_batch_processing_view',
        'select_batch_files', 'process_batch', '_select_batch_folder', '_select_lms_file',
        'batch_analyze_folder', 'batch_analyze_lms_export', 'schedule_batch_job',
        'view_batch_job_status', 'cancel_batch_job', 'retry_failed_analyses',
        'run_due_batch_jobs', '_extract_text_from_file',
    ),
    'model_security_view': (
        'create_model_management_view', '_load_model_version', '_view_training_progress',
        '_refresh_cache_info', 'retrain_detection_model', 'rollback_model_version',
        'compare_model_versions', 'try_text_on_versions', 'export_model_weights',
        'import_model_weights', 'clear_analysis_cache', 'create_security_audit_view', 'view_user_activity_log',
        '_export_activity_log', 'export_chain_of_custody', 'anonymize_student_data',
        'generate_gdpr_data_export',
    ),
    'export_import_view': (
        'create_export_section', 'create_data_export_import_view', 'export_results',
        'export_detailed_report', 'export_analytics_data', 'export_audit_log', 'import_data',
        'import_submissions', '_process_import_record', '_format_csv_record',
        'import_student_data', 'import_settings', 'archive_old_data', 'optimize_database',
        'clean_duplicates',
    ),
    'student_analytics_view': (
        'create_integrations_view', '_load_integration_status', 'push_to_academic_record',
        'create_enhanced_detection_view', 'analyze_writing_style_fingerprint',
        'detect_paraphrasing_tools', 'analyze_prompt_artifacts',
        'detect_translation_artifacts', 'analyze_knowledge_consistency',
        'detect_copy_paste_patterns', 'analyze_reference_authenticity', '_load_draft_files',
        'compare_draft_versions', 'create_student_management_view', 'view_student_profile',
        'compare_students', 'generate_student_report_card', 'flag_student_for_review',
        'view_student_progression', 'bulk_student_analysis', 'create_advanced_analytics_view',
        'show_detection_confidence_distribution', 'generate_word_cloud',
        'plot_submission_timeline', 'show_correlation_matrix', 'cluster_similar_submissions',
        'generate_department_comparison', 'show_weekly_trends', 'export_visualization_pack',
    ),
    'misc_view': (
        '_load_database_data', '_on_module_selected', '_send_email_via_gui',
        '_show_ai_detection_email_fallback', 'auto_send_ai_report_on_completion',
        'send_ai_detection_report_via_email', 'check_api_health', 'check_database_health',
        'check_filesystem_health', 'check_memory_health', 'check_model_health',
        'collect_performance_data', 'format_performance_report',
        'create_system_monitoring_view', 'refresh_system_metrics', 'run_system_health_check',
        'generate_performance_report', 'start_system_monitoring', 'update_error_log',
        'show_db_status', 'gather_analytics_data', 'generate_comprehensive_report',
        'get_audit_log_data', 'create_api_integration_tab', 'create_bias_detection_tab',
        'create_compliance_tab', 'create_data_export_import_tab',
        'create_federated_learning_tab', 'create_predictive_analytics_tab',
        'create_statistics_tab', 'create_student_self_check_tab',
        'create_system_monitoring_tab', 'create_visual_analysis_tab',
        'create_real_time_monitoring_tab',
    ),
}


class _ViewMethod:
    """Imports ``module`` on first use and binds the function to the class."""

    def __init__(self, module, name):
        self.module, self.name = module, name

    def __get__(self, obj, owner=None):
        import importlib
        func = getattr(importlib.import_module(f"{_PACKAGE}.{self.module}"), self.name)
        setattr(owner or type(obj), self.name, func)
        return func if obj is None else func.__get__(obj, owner)


for _module, _names in _VIEW_METHODS.items():
    for _name in _names:
        setattr(AIDetectorGUI, _name, _ViewMethod(_module, _name))


class GUILauncher:
    """Opens the detector standalone, for a signed-in member of staff."""

    @staticmethod
    def launch_gui(detector_instance=None, fullscreen=False, auth=None):
        """Open the detector in its own Tk root as ``auth``'s user."""
        app = AIDetectorGUI(root=None, auth=auth, detector_instance=detector_instance)
        if app.refused:
            return app
        if fullscreen:
            try:
                app.root.attributes('-fullscreen', True)
                app.root.bind('<Escape>', lambda e: app.root.attributes('-fullscreen', False))
            except tk.TclError:
                logger.debug("Fullscreen not available", exc_info=True)
        app.run()
        return app

    @staticmethod
    def launch_with_sample_data(fullscreen=False, auth=None):
        """Kept for old callers: demonstration data is no longer added (it
        made up students and readings); this opens the detector as usual."""
        return GUILauncher.launch_gui(fullscreen=fullscreen, auth=auth)
