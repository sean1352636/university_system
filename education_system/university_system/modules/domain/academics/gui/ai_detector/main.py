import json
import os
import threading
import time
import random
import sys
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext

from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH, sqlite3
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

try:
    from education_system.university_system.utils.ai.ai_detector.detector import AIDetector
    _AI_DETECTOR_IMPORT_ERROR = None
except Exception as import_error:
    AIDetector = None
    _AI_DETECTOR_IMPORT_ERROR = import_error

try:
    import textract
    TEXTRACT_AVAILABLE = True
except ImportError:
    TEXTRACT_AVAILABLE = False

try:
    from pypdf import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import docx
    PYTHON_DOCX_AVAILABLE = True
except ImportError:
    PYTHON_DOCX_AVAILABLE = False

from education_system.university_system.modules.shared.utils.i18n import get_text, _

# Import view functions from modular files
from education_system.university_system.modules.domain.academics.gui.ai_detector import alerts_course_view
from education_system.university_system.modules.domain.academics.gui.ai_detector import analysis_view
from education_system.university_system.modules.domain.academics.gui.ai_detector import api_visual_view
from education_system.university_system.modules.domain.academics.gui.ai_detector import batch_processing_view
from education_system.university_system.modules.domain.academics.gui.ai_detector import blockchain_adversarial_view
from education_system.university_system.modules.domain.academics.gui.ai_detector import compliance_bias_view
from education_system.university_system.modules.domain.academics.gui.ai_detector import export_import_view
from education_system.university_system.modules.domain.academics.gui.ai_detector import history_view
from education_system.university_system.modules.domain.academics.gui.ai_detector import misc_view
from education_system.university_system.modules.domain.academics.gui.ai_detector import model_security_view
from education_system.university_system.modules.domain.academics.gui.ai_detector import multimodal_citation_view
from education_system.university_system.modules.domain.academics.gui.ai_detector import realtime_federated_view
from education_system.university_system.modules.domain.academics.gui.ai_detector import settings_advanced_view
from education_system.university_system.modules.domain.academics.gui.ai_detector import statistics_view
from education_system.university_system.modules.domain.academics.gui.ai_detector import student_analytics_view

sys.modules.setdefault(
    "education_system.university_system.modules.domain.academics.gui.ai_detector_gui",
    sys.modules[__name__],
)

class AIDetectorGUI:
    """Modern GUI interface for the AI Detector system"""

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

        if detector_instance:
            self.detector = detector_instance
        elif AIDetector:
            self.detector = AIDetector()
        else:
            error_message = "AI Detector backend is not available."
            if _AI_DETECTOR_IMPORT_ERROR:
                error_message += f" Details: {_AI_DETECTOR_IMPORT_ERROR}"
            messagebox.showerror("Initialization Error", error_message)
            raise RuntimeError(error_message)

        # Initialize or use provided authentication
        if auth:
            self.auth = auth
        else:
            # Create UserAuth and set up default user session
            self.auth = self._initialize_auth()

        self.status_text = None
        self.progress_var = None
        self.progress_bar = None
        self.setup_window()
        self.setup_styles()
        self.create_main_interface()
        self.analysis_results = {}
        self.current_submission_id = None


    def _initialize_auth(self):
        """Get centralized auth or initialize UserAuth with a default test user session"""
        # Try to get centralized auth first
        auth = get_auth()
        if auth is None:
            auth = UserAuth()

        # Set up a default user session for testing
        if not auth.current_user:
            try:
                conn = sqlite3.connect(DEFAULT_DB_PATH)
                cursor = conn.cursor()
                cursor.execute('SELECT id, username, first_name, last_name, email FROM users WHERE id = 1 LIMIT 1')
                user_row = cursor.fetchone()
                conn.close()

                if user_row:
                    auth.current_user = {
                        'id': user_row[0],
                        'username': user_row[1],
                        'first_name': user_row[2] or 'Admin',
                        'last_name': user_row[3] or 'User',
                        'email': user_row[4] or 'admin@university.edu'
                    }
                else:
                    # Fallback to default admin user
                    auth.current_user = {
                        'id': 1,
                        'username': 'admin',
                        'first_name': 'System',
                        'last_name': 'Administrator',
                        'email': 'admin@university.edu'
                    }
            except Exception as e:
                print(f"Warning: Could not fetch user from database: {e}")
                # Fallback to default admin user
                auth.current_user = {
                    'id': 1,
                    'username': 'admin',
                    'first_name': 'System',
                    'last_name': 'Administrator',
                    'email': 'admin@university.edu'
                }

        return auth


    def setup_window(self):
        """Setup main window properties"""
        self.root.title("Ultimate AI Detector - Academic Integrity Suite")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 700)

        # Center window on screen
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - 1400) // 2
        y = (screen_height - 900) // 2
        self.root.geometry(f"1400x900+{x}+{y}")

        # Configure window icon (if available)
        try:
            self.root.iconbitmap('ai_detector_icon.ico')
        except Exception:
            pass  # Icon file not found, continue without it


    def setup_styles(self):
        """Setup basic theme to match main GUI"""
        self.style = ttk.Style()
        self.style.theme_use('clam')


    def create_main_interface(self):
        """Create the main interface with button navigation and scrollbar"""
        # Add return to main menu button at the top
        return_btn = ttk.Button(
            self.root,
            text="← Return to Main Menu",
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
        ttk.Button(self.nav_frame, text="🏠 Return to Homescreen", width=25,
                   command=self.return_to_main_menu).pack(fill='x', padx=5, pady=(0, 6))
        self.create_navigation_buttons()

        # Show default view
        self.show_view('analysis')

        # Load initial data
        self.refresh_statistics()
        self.update_blockchain_display()


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
            ("📊 Advanced Analytics", 'advanced_analytics')
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
        title_label = ttk.Label(title_frame, text="Ultimate AI Detector", style='Title.TLabel')
        title_label.pack(side='left', padx=15, pady=10)

        subtitle_label = ttk.Label(title_frame, text="Advanced Academic Integrity Detection Suite",
                                 style='Subtitle.TLabel')
        subtitle_label.pack(side='left', padx=(10, 0), pady=10)

        # Status indicator
        self.status_indicator = ttk.Label(title_frame, text="● Ready",
                                        foreground=self.colors['success'])
        self.status_indicator.pack(side='right', padx=15, pady=10)


    def create_status_bar(self, parent):
        """Create status bar"""
        self.status_frame = ttk.Frame(parent)
        self.status_frame.pack(fill='x', pady=(10, 0))

        # Status text
        self.status_text = ttk.Label(self.status_frame, text="Ready", style='Subtitle.TLabel')
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
                from education_system.university_system.modules.shared.gui.main import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()


    def update_status(self, message):
        """Update status bar message safely, or print as fallback"""
        try:
            if getattr(self, "status_text", None) is not None:
                self.status_text.config(text=message)
                if getattr(self, "root", None):
                    self.root.update_idletasks()
                return
        except Exception:
            pass
        # Fallback (e.g., if UI didn’t finish building)
        try:
            print(f"[status] {message}")
        except Exception:
            pass


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
            pass


    def run(self):
        """Start the GUI application"""
        try:
            # Initialize detector if not provided
            if not hasattr(self.detector, 'get_enhanced_statistics'):
                print("Warning: Detector instance may not be fully initialized")

            # Center and show window
            self.root.deiconify()

            # Start the main loop
            self.root.mainloop()

        except Exception as e:
            messagebox.showerror("Application Error", f"Failed to start application: {str(e)}")


# Bind functions from analysis_view module
AIDetectorGUI.create_analysis_view = analysis_view.create_analysis_view
AIDetectorGUI.create_input_section = analysis_view.create_input_section
AIDetectorGUI.create_results_section = analysis_view.create_results_section
AIDetectorGUI.show_empty_results = analysis_view.show_empty_results
AIDetectorGUI.load_file = analysis_view.load_file
AIDetectorGUI.clear_input = analysis_view.clear_input
AIDetectorGUI.analyze_text = analysis_view.analyze_text
AIDetectorGUI.display_results = analysis_view.display_results
AIDetectorGUI.create_score_display = analysis_view.create_score_display
AIDetectorGUI.create_detailed_analysis = analysis_view.create_detailed_analysis
AIDetectorGUI.create_pattern_tab = analysis_view.create_pattern_tab
AIDetectorGUI.create_pattern_indicator = analysis_view.create_pattern_indicator
AIDetectorGUI.create_sentence_tab = analysis_view.create_sentence_tab
AIDetectorGUI.create_advanced_analysis_tab = analysis_view.create_advanced_analysis_tab
AIDetectorGUI.create_advanced_analysis_section = analysis_view.create_advanced_analysis_section
AIDetectorGUI.create_recommendations = analysis_view.create_recommendations
AIDetectorGUI.analysis_error = analysis_view.analysis_error
AIDetectorGUI.get_risk_color = analysis_view.get_risk_color
AIDetectorGUI.get_risk_text = analysis_view.get_risk_text
AIDetectorGUI.update_word_count = analysis_view.update_word_count

# Bind functions from history_view module
AIDetectorGUI.create_history_view = history_view.create_history_view
AIDetectorGUI.refresh_history = history_view.refresh_history
AIDetectorGUI.clear_filter = history_view.clear_filter
AIDetectorGUI.view_submission_details = history_view.view_submission_details
AIDetectorGUI.show_submission_details_window = history_view.show_submission_details_window

# Bind functions from statistics_view module
AIDetectorGUI.create_statistics_view = statistics_view.create_statistics_view
AIDetectorGUI.create_stats_cards = statistics_view.create_stats_cards
AIDetectorGUI.create_stat_card = statistics_view.create_stat_card
AIDetectorGUI.create_charts_section = statistics_view.create_charts_section
AIDetectorGUI.create_risk_distribution_chart = statistics_view.create_risk_distribution_chart
AIDetectorGUI.refresh_statistics = statistics_view.refresh_statistics

# Bind functions from settings_advanced_view module
AIDetectorGUI.create_settings_view = settings_advanced_view.create_settings_view
AIDetectorGUI.apply_settings = settings_advanced_view.apply_settings
AIDetectorGUI.create_advanced_view = settings_advanced_view.create_advanced_view
AIDetectorGUI.create_ml_section = settings_advanced_view.create_ml_section
AIDetectorGUI.train_models = settings_advanced_view.train_models
AIDetectorGUI.training_complete = settings_advanced_view.training_complete
AIDetectorGUI.training_error = settings_advanced_view.training_error
AIDetectorGUI.show_model_status = settings_advanced_view.show_model_status

# Bind functions from realtime_federated_view module
AIDetectorGUI.create_real_time_monitoring_view = realtime_federated_view.create_real_time_monitoring_view
AIDetectorGUI.start_real_time_monitoring = realtime_federated_view.start_real_time_monitoring
AIDetectorGUI.stop_real_time_monitoring = realtime_federated_view.stop_real_time_monitoring
AIDetectorGUI.update_queue_status = realtime_federated_view.update_queue_status
AIDetectorGUI.create_federated_learning_view = realtime_federated_view.create_federated_learning_view
AIDetectorGUI.initialize_federation = realtime_federated_view.initialize_federation
AIDetectorGUI.contribute_model_update = realtime_federated_view.contribute_model_update
AIDetectorGUI.download_global_model = realtime_federated_view.download_global_model

# Bind functions from compliance_bias_view module
AIDetectorGUI.create_compliance_view = compliance_bias_view.create_compliance_view
AIDetectorGUI.generate_compliance_report = compliance_bias_view.generate_compliance_report
AIDetectorGUI.show_compliance_report_window = compliance_bias_view.show_compliance_report_window
AIDetectorGUI.show_data_retention_status = compliance_bias_view.show_data_retention_status
AIDetectorGUI.show_consent_management = compliance_bias_view.show_consent_management
AIDetectorGUI.create_bias_detection_view = compliance_bias_view.create_bias_detection_view
AIDetectorGUI.analyze_institutional_bias = compliance_bias_view.analyze_institutional_bias
AIDetectorGUI.display_bias_analysis = compliance_bias_view.display_bias_analysis
AIDetectorGUI.create_predictive_analytics_view = compliance_bias_view.create_predictive_analytics_view
AIDetectorGUI.predict_student_risk = compliance_bias_view.predict_student_risk
AIDetectorGUI.display_risk_prediction = compliance_bias_view.display_risk_prediction
AIDetectorGUI.train_risk_model = compliance_bias_view.train_risk_model
AIDetectorGUI.show_model_performance = compliance_bias_view.show_model_performance
AIDetectorGUI.create_student_self_check_view = compliance_bias_view.create_student_self_check_view
AIDetectorGUI.run_self_check = compliance_bias_view.run_self_check
AIDetectorGUI.show_self_check_results = compliance_bias_view.show_self_check_results

# Bind functions from blockchain_adversarial_view module
AIDetectorGUI.create_adversarial_detection_tab = blockchain_adversarial_view.create_adversarial_detection_tab
AIDetectorGUI.create_adversarial_detection_view = blockchain_adversarial_view.create_adversarial_detection_view
AIDetectorGUI.test_adversarial_detection = blockchain_adversarial_view.test_adversarial_detection
AIDetectorGUI.show_adversarial_results = blockchain_adversarial_view.show_adversarial_results
AIDetectorGUI.create_blockchain_audit_tab = blockchain_adversarial_view.create_blockchain_audit_tab
AIDetectorGUI.create_blockchain_audit_view = blockchain_adversarial_view.create_blockchain_audit_view
AIDetectorGUI.mine_blockchain_block = blockchain_adversarial_view.mine_blockchain_block
AIDetectorGUI.verify_blockchain_integrity = blockchain_adversarial_view.verify_blockchain_integrity
AIDetectorGUI.view_blockchain_history = blockchain_adversarial_view.view_blockchain_history
AIDetectorGUI.update_blockchain_display = blockchain_adversarial_view.update_blockchain_display
AIDetectorGUI.create_benchmarking_tab = blockchain_adversarial_view.create_benchmarking_tab
AIDetectorGUI.create_benchmarking_view = blockchain_adversarial_view.create_benchmarking_view
AIDetectorGUI.generate_benchmark_report = blockchain_adversarial_view.generate_benchmark_report
AIDetectorGUI.display_benchmark_report = blockchain_adversarial_view.display_benchmark_report

# Bind functions from multimodal_citation_view module
AIDetectorGUI.create_multi_modal_analysis_tab = multimodal_citation_view.create_multi_modal_analysis_tab
AIDetectorGUI.create_multi_modal_analysis_view = multimodal_citation_view.create_multi_modal_analysis_view
AIDetectorGUI.upload_images_for_analysis = multimodal_citation_view.upload_images_for_analysis
AIDetectorGUI.analyze_image_text_consistency = multimodal_citation_view.analyze_image_text_consistency
AIDetectorGUI.analyze_code_submission = multimodal_citation_view.analyze_code_submission
AIDetectorGUI.show_multimodal_results = multimodal_citation_view.show_multimodal_results
AIDetectorGUI.show_code_analysis_results = multimodal_citation_view.show_code_analysis_results
AIDetectorGUI.create_citation_verification_tab = multimodal_citation_view.create_citation_verification_tab
AIDetectorGUI.create_citation_verification_view = multimodal_citation_view.create_citation_verification_view
AIDetectorGUI.verify_citations = multimodal_citation_view.verify_citations
AIDetectorGUI.show_citation_results = multimodal_citation_view.show_citation_results
AIDetectorGUI.create_temporal_analysis_tab = multimodal_citation_view.create_temporal_analysis_tab
AIDetectorGUI.create_temporal_analysis_view = multimodal_citation_view.create_temporal_analysis_view
AIDetectorGUI.analyze_writing_speed = multimodal_citation_view.analyze_writing_speed
AIDetectorGUI.analyze_submission_patterns = multimodal_citation_view.analyze_submission_patterns
AIDetectorGUI.show_temporal_results = multimodal_citation_view.show_temporal_results
AIDetectorGUI.show_submission_patterns = multimodal_citation_view.show_submission_patterns

# Bind functions from api_visual_view module
AIDetectorGUI.create_api_integration_view = api_visual_view.create_api_integration_view
AIDetectorGUI.register_external_api = api_visual_view.register_external_api
AIDetectorGUI.test_api_connection = api_visual_view.test_api_connection
AIDetectorGUI.show_api_performance = api_visual_view.show_api_performance
AIDetectorGUI.compare_api_results = api_visual_view.compare_api_results
AIDetectorGUI.run_ensemble_prediction = api_visual_view.run_ensemble_prediction
AIDetectorGUI.show_ensemble_results = api_visual_view.show_ensemble_results
AIDetectorGUI.create_visual_analysis_view = api_visual_view.create_visual_analysis_view
AIDetectorGUI.generate_text_heatmap = api_visual_view.generate_text_heatmap
AIDetectorGUI.display_text_heatmap = api_visual_view.display_text_heatmap
AIDetectorGUI.generate_writing_flow = api_visual_view.generate_writing_flow
AIDetectorGUI.display_writing_flow = api_visual_view.display_writing_flow
AIDetectorGUI.generate_complexity_viz = api_visual_view.generate_complexity_viz

# Bind functions from alerts_course_view module
AIDetectorGUI.create_alerts_notifications_view = alerts_course_view.create_alerts_notifications_view
AIDetectorGUI.configure_alert_thresholds = alerts_course_view.configure_alert_thresholds
AIDetectorGUI.setup_email_alerts = alerts_course_view.setup_email_alerts
AIDetectorGUI.view_alert_queue = alerts_course_view.view_alert_queue
AIDetectorGUI.dismiss_alert = alerts_course_view.dismiss_alert
AIDetectorGUI.escalate_to_dean = alerts_course_view.escalate_to_dean
AIDetectorGUI.create_course_management_view = alerts_course_view.create_course_management_view
AIDetectorGUI._load_assignment_profiles = alerts_course_view._load_assignment_profiles
AIDetectorGUI._load_courses_for_dashboard = alerts_course_view._load_courses_for_dashboard
AIDetectorGUI.create_assignment_profile = alerts_course_view.create_assignment_profile
AIDetectorGUI.set_assignment_baseline = alerts_course_view.set_assignment_baseline
AIDetectorGUI.compare_against_assignment_baseline = alerts_course_view.compare_against_assignment_baseline
AIDetectorGUI.view_course_integrity_dashboard = alerts_course_view.view_course_integrity_dashboard
AIDetectorGUI.generate_course_end_report = alerts_course_view.generate_course_end_report

# Bind functions from batch_processing_view module
AIDetectorGUI.create_batch_processing_section = batch_processing_view.create_batch_processing_section
AIDetectorGUI.create_batch_processing_view = batch_processing_view.create_batch_processing_view
AIDetectorGUI.select_batch_files = batch_processing_view.select_batch_files
AIDetectorGUI.process_batch = batch_processing_view.process_batch
AIDetectorGUI._select_batch_folder = batch_processing_view._select_batch_folder
AIDetectorGUI._select_lms_file = batch_processing_view._select_lms_file
AIDetectorGUI.batch_analyze_folder = batch_processing_view.batch_analyze_folder
AIDetectorGUI.batch_analyze_lms_export = batch_processing_view.batch_analyze_lms_export
AIDetectorGUI.schedule_batch_job = batch_processing_view.schedule_batch_job
AIDetectorGUI.view_batch_job_status = batch_processing_view.view_batch_job_status
AIDetectorGUI.cancel_batch_job = batch_processing_view.cancel_batch_job
AIDetectorGUI.retry_failed_analyses = batch_processing_view.retry_failed_analyses
AIDetectorGUI._extract_text_from_file = batch_processing_view._extract_text_from_file

# Bind functions from model_security_view module
AIDetectorGUI.create_model_management_view = model_security_view.create_model_management_view
AIDetectorGUI._load_model_version = model_security_view._load_model_version
AIDetectorGUI._view_training_progress = model_security_view._view_training_progress
AIDetectorGUI._refresh_cache_info = model_security_view._refresh_cache_info
AIDetectorGUI.retrain_detection_model = model_security_view.retrain_detection_model
AIDetectorGUI.rollback_model_version = model_security_view.rollback_model_version
AIDetectorGUI.compare_model_versions = model_security_view.compare_model_versions
AIDetectorGUI.export_model_weights = model_security_view.export_model_weights
AIDetectorGUI.import_model_weights = model_security_view.import_model_weights
AIDetectorGUI.clear_analysis_cache = model_security_view.clear_analysis_cache
AIDetectorGUI.create_security_audit_view = model_security_view.create_security_audit_view
AIDetectorGUI._export_activity_log = model_security_view._export_activity_log
AIDetectorGUI.view_user_activity_log = model_security_view.view_user_activity_log
AIDetectorGUI.export_chain_of_custody = model_security_view.export_chain_of_custody
AIDetectorGUI.anonymize_student_data = model_security_view.anonymize_student_data
AIDetectorGUI.generate_gdpr_data_export = model_security_view.generate_gdpr_data_export

# Bind functions from export_import_view module
AIDetectorGUI.create_export_section = export_import_view.create_export_section
AIDetectorGUI.create_data_export_import_view = export_import_view.create_data_export_import_view
AIDetectorGUI.export_results = export_import_view.export_results
AIDetectorGUI.export_detailed_report = export_import_view.export_detailed_report
AIDetectorGUI.export_analytics_data = export_import_view.export_analytics_data
AIDetectorGUI.export_audit_log = export_import_view.export_audit_log
AIDetectorGUI.import_data = export_import_view.import_data
AIDetectorGUI.import_submissions = export_import_view.import_submissions
AIDetectorGUI.import_student_data = export_import_view.import_student_data
AIDetectorGUI.import_settings = export_import_view.import_settings
AIDetectorGUI.archive_old_data = export_import_view.archive_old_data
AIDetectorGUI.optimize_database = export_import_view.optimize_database
AIDetectorGUI.clean_duplicates = export_import_view.clean_duplicates
AIDetectorGUI._process_import_record = export_import_view._process_import_record
AIDetectorGUI._format_csv_record = export_import_view._format_csv_record

# Bind functions from student_analytics_view module
AIDetectorGUI.create_integrations_view = student_analytics_view.create_integrations_view
AIDetectorGUI._save_plagiarism_config = student_analytics_view._save_plagiarism_config
AIDetectorGUI._test_plagiarism_connection = student_analytics_view._test_plagiarism_connection
AIDetectorGUI._load_integration_status = student_analytics_view._load_integration_status
AIDetectorGUI.sync_with_plagiarism_checker = student_analytics_view.sync_with_plagiarism_checker
AIDetectorGUI.push_to_academic_record = student_analytics_view.push_to_academic_record
AIDetectorGUI.create_enhanced_detection_view = student_analytics_view.create_enhanced_detection_view
AIDetectorGUI._load_draft_files = student_analytics_view._load_draft_files
AIDetectorGUI.analyze_writing_style_fingerprint = student_analytics_view.analyze_writing_style_fingerprint
AIDetectorGUI.detect_paraphrasing_tools = student_analytics_view.detect_paraphrasing_tools
AIDetectorGUI.analyze_prompt_artifacts = student_analytics_view.analyze_prompt_artifacts
AIDetectorGUI.compare_draft_versions = student_analytics_view.compare_draft_versions
AIDetectorGUI.detect_translation_artifacts = student_analytics_view.detect_translation_artifacts
AIDetectorGUI.analyze_knowledge_consistency = student_analytics_view.analyze_knowledge_consistency
AIDetectorGUI.detect_copy_paste_patterns = student_analytics_view.detect_copy_paste_patterns
AIDetectorGUI.analyze_reference_authenticity = student_analytics_view.analyze_reference_authenticity
AIDetectorGUI.create_student_management_view = student_analytics_view.create_student_management_view
AIDetectorGUI.view_student_profile = student_analytics_view.view_student_profile
AIDetectorGUI.compare_students = student_analytics_view.compare_students
AIDetectorGUI.generate_student_report_card = student_analytics_view.generate_student_report_card
AIDetectorGUI.flag_student_for_review = student_analytics_view.flag_student_for_review
AIDetectorGUI.view_student_progression = student_analytics_view.view_student_progression
AIDetectorGUI.bulk_student_analysis = student_analytics_view.bulk_student_analysis
AIDetectorGUI.create_advanced_analytics_view = student_analytics_view.create_advanced_analytics_view
AIDetectorGUI.show_detection_confidence_distribution = student_analytics_view.show_detection_confidence_distribution
AIDetectorGUI.generate_word_cloud = student_analytics_view.generate_word_cloud
AIDetectorGUI.plot_submission_timeline = student_analytics_view.plot_submission_timeline
AIDetectorGUI.show_correlation_matrix = student_analytics_view.show_correlation_matrix
AIDetectorGUI.cluster_similar_submissions = student_analytics_view.cluster_similar_submissions
AIDetectorGUI.generate_department_comparison = student_analytics_view.generate_department_comparison
AIDetectorGUI.show_weekly_trends = student_analytics_view.show_weekly_trends
AIDetectorGUI.export_visualization_pack = student_analytics_view.export_visualization_pack

# Bind functions from misc_view module
AIDetectorGUI._load_database_data = misc_view._load_database_data
AIDetectorGUI._on_module_selected = misc_view._on_module_selected
AIDetectorGUI._send_email_via_gui = misc_view._send_email_via_gui
AIDetectorGUI._show_ai_detection_email_fallback = misc_view._show_ai_detection_email_fallback
AIDetectorGUI.auto_send_ai_report_on_completion = misc_view.auto_send_ai_report_on_completion
AIDetectorGUI.check_api_health = misc_view.check_api_health
AIDetectorGUI.check_database_health = misc_view.check_database_health
AIDetectorGUI.check_filesystem_health = misc_view.check_filesystem_health
AIDetectorGUI.check_memory_health = misc_view.check_memory_health
AIDetectorGUI.check_model_health = misc_view.check_model_health
AIDetectorGUI.collect_performance_data = misc_view.collect_performance_data
AIDetectorGUI.create_api_integration_tab = misc_view.create_api_integration_tab
AIDetectorGUI.create_bias_detection_tab = misc_view.create_bias_detection_tab
AIDetectorGUI.create_compliance_tab = misc_view.create_compliance_tab
AIDetectorGUI.create_data_export_import_tab = misc_view.create_data_export_import_tab
AIDetectorGUI.create_federated_learning_tab = misc_view.create_federated_learning_tab
AIDetectorGUI.create_predictive_analytics_tab = misc_view.create_predictive_analytics_tab
AIDetectorGUI.create_statistics_tab = misc_view.create_statistics_tab
AIDetectorGUI.create_student_self_check_tab = misc_view.create_student_self_check_tab
AIDetectorGUI.create_system_monitoring_tab = misc_view.create_system_monitoring_tab
AIDetectorGUI.create_system_monitoring_view = misc_view.create_system_monitoring_view
AIDetectorGUI.create_visual_analysis_tab = misc_view.create_visual_analysis_tab
AIDetectorGUI.format_performance_report = misc_view.format_performance_report
AIDetectorGUI.gather_analytics_data = misc_view.gather_analytics_data
AIDetectorGUI.generate_comprehensive_report = misc_view.generate_comprehensive_report
AIDetectorGUI.generate_performance_report = misc_view.generate_performance_report
AIDetectorGUI.get_audit_log_data = misc_view.get_audit_log_data
AIDetectorGUI.refresh_system_metrics = misc_view.refresh_system_metrics
AIDetectorGUI.run_system_health_check = misc_view.run_system_health_check
AIDetectorGUI.send_ai_detection_report_via_email = misc_view.send_ai_detection_report_via_email
AIDetectorGUI.show_db_status = misc_view.show_db_status
AIDetectorGUI.start_system_monitoring = misc_view.start_system_monitoring
AIDetectorGUI.update_error_log = misc_view.update_error_log


class GUILauncher:

    """Launcher class for the GUI application"""



    @staticmethod

    def launch_gui(detector_instance=None, fullscreen=False):

        """Launch the GUI with optional detector instance"""

        try:

            if detector_instance is None:

                print("Initializing AI Detector.")

                detector_instance = AIDetector()

                print("✓ AI Detector initialized")



            print("Starting GUI.")

            app = AIDetectorGUI(detector_instance)



            # Fullscreen handling

            if fullscreen:

                try:

                    app.root.attributes('-fullscreen', True)  # cross-platform

                    # Windows maximize fallback (won't harm others)

                    try:

                        app.root.state('zoomed')

                    except Exception:

                        pass

                    # Esc to exit fullscreen

                    app.root.bind('<Escape>', lambda e: app.root.attributes('-fullscreen', False))

                except Exception as _:

                    pass



            app.run()



        except Exception as e:

            print(f"Failed to launch GUI: {e}")

            import traceback

            traceback.print_exc()



    @staticmethod

    def launch_with_sample_data():

        """Launch GUI with sample data for demonstration"""

        try:

            # Initialize detector

            detector = AIDetector()



            # Add some sample data

            sample_texts = [

                {

                    'text': "Artificial intelligence represents a significant advancement in technological capabilities. However, it is important to note that these developments present both opportunities and challenges for society.",

                    'student_id': 'DEMO_001',

                    'title': 'AI Essay Sample',

                    'course': 'CS101'

                },

                {

                    'text': "I think AI is really cool and can help us do lots of things. My friend told me about ChatGPT and how it can write essays, which is pretty neat but also kind of scary.",

                    'student_id': 'DEMO_002',

                    'title': 'My thoughts on AI',

                    'course': 'CS101'

                }

            ]



            print("Adding sample data...")

            for sample in sample_texts:

                try:

                    detector.analyze_text_enhanced(

                        text=sample['text'],

                        title=sample['title'],

                        student_id=sample['student_id'],

                        course_code=sample['course']

                    )

                    print(f"✓ Added sample: {sample['title']}")

                except Exception as e:

                    print(f"Warning: Could not add sample data: {e}")



            # Launch GUI

            app = AIDetectorGUI(detector)

            app.run()



        except Exception as e:

            print(f"Failed to launch GUI with sample data: {e}")

            import traceback

            traceback.print_exc()
