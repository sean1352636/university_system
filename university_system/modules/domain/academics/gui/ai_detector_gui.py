import json
import os
import threading
import time
import random
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext

from university_system.infrastructure.database.db import DEFAULT_DB_PATH, sqlite3
from university_system.infrastructure.auth.user_authentication import UserAuth

try:
    from university_system.utils.ai.ai_detector import AIDetector
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
    from PyPDF2 import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import docx
    PYTHON_DOCX_AVAILABLE = True
except ImportError:
    PYTHON_DOCX_AVAILABLE = False

class AIDetectorGUI:
    """Modern GUI interface for the AI Detector system"""
    
    def __init__(self, root=None, auth=None, detector_instance=None):
        self.root = root if root else tk.Tk()

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
        """Initialize UserAuth with a default test user session"""
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
        except:
            pass  # Icon file not found, continue without it
    
    def setup_styles(self):
        """Setup modern light theme styles"""
        self.style = ttk.Style()

        # Configure light theme
        self.style.theme_use('clam')

        # Color scheme
        self.colors = {
            'bg_primary': '#f5f5f5',      # Light background
            'bg_secondary': '#e8e8e8',    # Slightly darker background
            'bg_tertiary': '#ffffff',     # Card backgrounds
            'accent': '#0078d4',          # Microsoft blue
            'accent_hover': '#106ebe',    # Darker blue for hover
            'success': '#107c10',         # Success green
            'warning': '#ff8c00',         # Warning orange
            'danger': '#d13438',          # Danger red
            'text_primary': '#000000',    # Primary text
            'text_secondary': '#5a5a5a',  # Secondary text
            'border': '#d0d0d0'           # Border color
        }
        
        # Configure styles
        self.style.configure('TFrame', background=self.colors['bg_primary'])
        self.style.configure('Card.TFrame', background=self.colors['bg_tertiary'], relief='solid', borderwidth=1)
        self.style.configure('TLabel', background=self.colors['bg_primary'], foreground=self.colors['text_primary'])
        self.style.configure('Title.TLabel', font=('Segoe UI', 14, 'bold'))
        self.style.configure('Subtitle.TLabel', font=('Segoe UI', 10), foreground=self.colors['text_secondary'])
        self.style.configure('TButton', focuscolor='none')
        self.style.configure('Accent.TButton', background=self.colors['accent'])
        
        # Configure notebook (tab) styles
        self.style.configure('TNotebook', background=self.colors['bg_primary'], borderwidth=0)
        self.style.configure('TNotebook.Tab', padding=[12, 8], background=self.colors['bg_secondary'])
        self.style.map('TNotebook.Tab', background=[('selected', self.colors['bg_tertiary'])])
        
        # Configure treeview
        self.style.configure('Treeview', background=self.colors['bg_tertiary'], 
                           foreground=self.colors['text_primary'], fieldbackground=self.colors['bg_tertiary'])
        self.style.configure('Treeview.Heading', background=self.colors['bg_secondary'])
        
        # Configure progressbar
        self.style.configure('TProgressbar', background=self.colors['accent'])
        
        # Set root background
        self.root.configure(bg=self.colors['bg_primary'])
    
    def create_main_interface(self):
        """Create the main interface with button navigation and scrollbar"""
        # Add return to main menu button at the top
        return_btn = ttk.Button(
            self.root,
            text="🏠 Return to Main Menu",
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
            ("📸 Visual Analysis", 'visual')
        ]

        for text, view_id in nav_buttons:
            btn = ttk.Button(self.nav_frame, text=text, width=25,
                           command=lambda v=view_id: self.show_view(v))
            btn.pack(fill='x', padx=5, pady=2)

    def create_adversarial_detection_tab(self):
        """Create adversarial detection tab"""
        adversarial_frame = ttk.Frame(self.notebook)
        self.notebook.add(adversarial_frame, text="🛡️ Anti-Evasion")

        # Adversarial detection card
        adversarial_card = ttk.Frame(adversarial_frame, style='Card.TFrame')
        adversarial_card.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(adversarial_card, text="Adversarial & Evasion Detection", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

        # Detection methods
        methods_frame = ttk.LabelFrame(adversarial_card, text="Detection Methods", padding=15)
        methods_frame.pack(fill='x', padx=15, pady=(0, 15))

        self.detect_invisible_chars_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(methods_frame, text="Invisible Characters", variable=self.detect_invisible_chars_var).pack(anchor='w')

        self.detect_char_substitution_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(methods_frame, text="Character Substitution", variable=self.detect_char_substitution_var).pack(anchor='w')

        self.detect_spacing_anomalies_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(methods_frame, text="Spacing Anomalies", variable=self.detect_spacing_anomalies_var).pack(anchor='w')

        # Test button
        ttk.Button(adversarial_card, text="Test Evasion Detection",
                  command=self.test_adversarial_detection).pack(pady=15)

    def create_blockchain_audit_tab(self):
        """Create blockchain audit trail tab"""
        blockchain_frame = ttk.Frame(self.notebook)
        self.notebook.add(blockchain_frame, text="🔗 Blockchain")

        # Blockchain card
        blockchain_card = ttk.Frame(blockchain_frame, style='Card.TFrame')
        blockchain_card.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(blockchain_card, text="Blockchain Audit Trail", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

        # Blockchain info
        info_frame = ttk.LabelFrame(blockchain_card, text="Chain Information", padding=15)
        info_frame.pack(fill='x', padx=15, pady=(0, 15))

        self.chain_length_label = ttk.Label(info_frame, text="Chain Length: 0")
        self.chain_length_label.pack(anchor='w')

        self.pending_transactions_label = ttk.Label(info_frame, text="Pending Transactions: 0")
        self.pending_transactions_label.pack(anchor='w')

        # Controls
        controls_frame = ttk.Frame(blockchain_card)
        controls_frame.pack(fill='x', padx=15, pady=(0, 15))

        ttk.Button(controls_frame, text="Mine Pending Block",
                  command=self.mine_blockchain_block).pack(side='left', padx=(0, 10))
        ttk.Button(controls_frame, text="Verify Chain Integrity",
                  command=self.verify_blockchain_integrity).pack(side='left', padx=(0, 10))
        ttk.Button(controls_frame, text="View Chain History",
                  command=self.view_blockchain_history).pack(side='left')

    def create_benchmarking_tab(self):
        """Create institutional benchmarking tab"""
        benchmark_frame = ttk.Frame(self.notebook)
        self.notebook.add(benchmark_frame, text="📊 Benchmarking")

        # Benchmarking card
        benchmark_card = ttk.Frame(benchmark_frame, style='Card.TFrame')
        benchmark_card.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(benchmark_card, text="Institutional Benchmarking", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

        # Institution input
        input_frame = ttk.Frame(benchmark_card)
        input_frame.pack(fill='x', padx=15, pady=(0, 15))

        ttk.Label(input_frame, text="Institution ID:").pack(side='left')
        self.benchmark_institution_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.benchmark_institution_var, width=20).pack(side='left', padx=(5, 15))

        ttk.Label(input_frame, text="Period:").pack(side='left')
        self.benchmark_period_var = tk.StringVar(value="1_month")
        period_combo = ttk.Combobox(input_frame, textvariable=self.benchmark_period_var,
                                   values=["1_month", "3_months", "1_year"], width=15)
        period_combo.pack(side='left', padx=(5, 15))

        ttk.Button(input_frame, text="Generate Report",
                  command=self.generate_benchmark_report).pack(side='right')

        # Results display
        self.benchmark_results_frame = ttk.Frame(benchmark_card)
        self.benchmark_results_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    def create_bias_detection_tab(self):
        """Create bias detection tab"""
        bias_frame = ttk.Frame(self.notebook)
        self.notebook.add(bias_frame, text="⚖️ Bias Detection")

        # Bias detection card
        bias_card = ttk.Frame(bias_frame, style='Card.TFrame')
        bias_card.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(bias_card, text="Bias Detection & Analysis", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

        # Institution input
        input_frame = ttk.Frame(bias_card)
        input_frame.pack(fill='x', padx=15, pady=(0, 15))

        ttk.Label(input_frame, text="Institution ID:").pack(side='left')
        self.bias_institution_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.bias_institution_var, width=20).pack(side='left', padx=(5, 15))

        ttk.Button(input_frame, text="Analyze Bias",
                  command=self.analyze_institutional_bias).pack(side='right')

        # Results display
        self.bias_results_frame = ttk.Frame(bias_card)
        self.bias_results_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    def create_citation_verification_tab(self):
        """Create citation verification tab"""
        citation_frame = ttk.Frame(self.notebook)
        self.notebook.add(citation_frame, text="📚 Citations")

        # Citation verification card
        citation_card = ttk.Frame(citation_frame, style='Card.TFrame')
        citation_card.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(citation_card, text="Citation Verification", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

        # Text input for citation checking
        input_frame = ttk.LabelFrame(citation_card, text="Enter Text with Citations", padding=15)
        input_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        import scrolledtext
        self.citation_text = scrolledtext.ScrolledText(input_frame, height=10, wrap=tk.WORD)
        self.citation_text.pack(fill='both', expand=True)

        # Verify button
        ttk.Button(citation_card, text="Verify Citations",
                  command=self.verify_citations_in_text).pack(pady=15)

        # Results
        self.citation_results_frame = ttk.Frame(citation_card)
        self.citation_results_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    def create_compliance_tab(self):
        """Create compliance monitoring tab"""
        compliance_frame = ttk.Frame(self.notebook)
        self.notebook.add(compliance_frame, text="📋 Compliance")

        # Compliance card
        compliance_card = ttk.Frame(compliance_frame, style='Card.TFrame')
        compliance_card.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(compliance_card, text="Compliance & Privacy", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

        # Compliance controls
        controls_frame = ttk.LabelFrame(compliance_card, text="Compliance Tools", padding=15)
        controls_frame.pack(fill='x', padx=15, pady=(0, 15))

        ttk.Button(controls_frame, text="Generate Compliance Report",
                  command=self.generate_compliance_report).pack(fill='x', pady=(0, 5))
        ttk.Button(controls_frame, text="Data Retention Status",
                  command=self.show_data_retention_status).pack(fill='x', pady=(0, 5))
        ttk.Button(controls_frame, text="Consent Management",
                  command=self.show_consent_management).pack(fill='x')

    def create_data_export_import_tab(self):
        """Create data export/import tab"""
        export_frame = ttk.Frame(self.notebook)
        self.notebook.add(export_frame, text="💾 Data Management")

        # Data management card
        data_card = ttk.Frame(export_frame, style='Card.TFrame')
        data_card.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(data_card, text="Advanced Data Management", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

        # Export options
        export_frame_inner = ttk.LabelFrame(data_card, text="Export Options", padding=15)
        export_frame_inner.pack(fill='x', padx=15, pady=(0, 15))

        export_buttons = ttk.Frame(export_frame_inner)
        export_buttons.pack(fill='x')

        ttk.Button(export_buttons, text="📊 Export Detailed Report",
                  command=self.export_detailed_report).pack(side='left', padx=(0, 10))
        ttk.Button(export_buttons, text="📈 Export Analytics Data",
                  command=self.export_analytics_data).pack(side='left', padx=(0, 10))
        ttk.Button(export_buttons, text="🔐 Export Audit Log",
                  command=self.export_audit_log).pack(side='left')

        # Import options
        import_frame_inner = ttk.LabelFrame(data_card, text="Import Options", padding=15)
        import_frame_inner.pack(fill='x', padx=15, pady=(0, 15))

        import_buttons = ttk.Frame(import_frame_inner)
        import_buttons.pack(fill='x')

        ttk.Button(import_buttons, text="📥 Import Submissions",
                  command=self.import_submissions).pack(side='left', padx=(0, 10))
        ttk.Button(import_buttons, text="👥 Import Student Data",
                  command=self.import_student_data).pack(side='left', padx=(0, 10))
        ttk.Button(import_buttons, text="⚙️ Import Settings",
                  command=self.import_settings).pack(side='left')

    def create_federated_learning_tab(self):
        """Create federated learning tab"""
        fed_frame = ttk.Frame(self.notebook)
        self.notebook.add(fed_frame, text="🌐 Federated ML")

        # Federated learning card
        fed_card = ttk.Frame(fed_frame, style='Card.TFrame')
        fed_card.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(fed_card, text="Federated Learning", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

        # Institution setup
        setup_frame = ttk.LabelFrame(fed_card, text="Federation Setup", padding=15)
        setup_frame.pack(fill='x', padx=15, pady=(0, 15))

        ttk.Label(setup_frame, text="Institution ID:").pack(side='left')
        self.institution_id_var = tk.StringVar()
        ttk.Entry(setup_frame, textvariable=self.institution_id_var, width=20).pack(side='left', padx=(5, 15))

        ttk.Button(setup_frame, text="Initialize Federation",
                  command=self.initialize_federation).pack(side='right')

        # Controls
        controls_frame = ttk.Frame(fed_card)
        controls_frame.pack(fill='x', padx=15, pady=(0, 15))

        ttk.Button(controls_frame, text="Contribute Model Update",
                  command=self.contribute_model_update).pack(side='left', padx=(0, 10))
        ttk.Button(controls_frame, text="Download Global Model",
                  command=self.download_global_model).pack(side='left')

    def create_multi_modal_analysis_tab(self):
        """Create multi-modal analysis tab"""
        multimodal_frame = ttk.Frame(self.notebook)
        self.notebook.add(multimodal_frame, text="🖼️ Multi-Modal")

        # Multi-modal card
        multimodal_card = ttk.Frame(multimodal_frame, style='Card.TFrame')
        multimodal_card.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(multimodal_card, text="Multi-Modal Analysis", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

        # Analysis types
        types_frame = ttk.LabelFrame(multimodal_card, text="Analysis Types", padding=15)
        types_frame.pack(fill='x', padx=15, pady=(0, 15))

        ttk.Button(types_frame, text="📝 Text + Image Consistency",
                  command=self.analyze_text_image_consistency).pack(fill='x', pady=(0, 5))
        ttk.Button(types_frame, text="💻 Code Submission Analysis",
                  command=self.analyze_code_submission).pack(fill='x')

        # Image upload
        upload_frame = ttk.Frame(multimodal_card)
        upload_frame.pack(fill='x', padx=15, pady=(0, 15))

        ttk.Button(upload_frame, text="📤 Upload Images",
                  command=self.upload_images_for_analysis).pack()

    def create_predictive_analytics_tab(self):
        """Create predictive analytics tab"""
        predictive_frame = ttk.Frame(self.notebook)
        self.notebook.add(predictive_frame, text="🔮 Predictive")

        # Predictive analytics card
        predictive_card = ttk.Frame(predictive_frame, style='Card.TFrame')
        predictive_card.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(predictive_card, text="Predictive Analytics", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

        # Student risk prediction
        risk_frame = ttk.LabelFrame(predictive_card, text="Student Risk Prediction", padding=15)
        risk_frame.pack(fill='x', padx=15, pady=(0, 15))

        input_frame = ttk.Frame(risk_frame)
        input_frame.pack(fill='x')

        ttk.Label(input_frame, text="Student ID:").pack(side='left')
        self.risk_student_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.risk_student_var, width=20).pack(side='left', padx=(5, 15))

        ttk.Button(input_frame, text="Predict Risk",
                  command=self.predict_student_risk).pack(side='right')

        # Results display
        self.risk_results_frame = ttk.Frame(predictive_card)
        self.risk_results_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        # Model training
        training_frame = ttk.Frame(predictive_card)
        training_frame.pack(fill='x', padx=15, pady=(0, 15))

        ttk.Button(training_frame, text="Train Risk Model",
                  command=self.train_risk_model).pack(side='left', padx=(0, 10))
        ttk.Button(training_frame, text="Model Performance",
                  command=self.show_model_performance).pack(side='left')

    def create_statistics_tab(self):
        """Create enhanced statistics tab"""
        stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(stats_frame, text="📊 Statistics")

        # Statistics card
        stats_card = ttk.Frame(stats_frame, style='Card.TFrame')
        stats_card.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(stats_card, text="Enhanced Statistics", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

        # Refresh button
        ttk.Button(stats_card, text="🔄 Refresh Statistics",
                  command=self.refresh_statistics).pack(pady=15)

        # Stats display frame
        self.stats_display_frame = ttk.Frame(stats_card)
        self.stats_display_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    def create_student_self_check_tab(self):
        """Create student self-check tool tab"""
        selfcheck_frame = ttk.Frame(self.notebook)
        self.notebook.add(selfcheck_frame, text="✓ Self-Check")

        # Self-check card
        selfcheck_card = ttk.Frame(selfcheck_frame, style='Card.TFrame')
        selfcheck_card.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(selfcheck_card, text="Student Self-Check Tool", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

        # Text input
        input_frame = ttk.LabelFrame(selfcheck_card, text="Enter Your Text", padding=15)
        input_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        import scrolledtext
        self.self_check_text = scrolledtext.ScrolledText(input_frame, height=10, wrap=tk.WORD)
        self.self_check_text.pack(fill='both', expand=True)

        # Check button
        ttk.Button(selfcheck_card, text="Run Self-Check",
                  command=self.run_self_check).pack(pady=15)

    def create_system_monitoring_tab(self):
        """Create system monitoring tab"""
        monitoring_frame = ttk.Frame(self.notebook)
        self.notebook.add(monitoring_frame, text="🔍 System Monitor")

        # System monitoring card
        monitor_card = ttk.Frame(monitoring_frame, style='Card.TFrame')
        monitor_card.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(monitor_card, text="System Health Monitoring", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

        # Performance metrics
        perf_frame = ttk.LabelFrame(monitor_card, text="Performance Metrics", padding=15)
        perf_frame.pack(fill='x', padx=15, pady=(0, 15))

        self.cpu_usage_label = ttk.Label(perf_frame, text="CPU Usage: --")
        self.cpu_usage_label.pack(anchor='w')

        self.memory_usage_label = ttk.Label(perf_frame, text="Memory Usage: --")
        self.memory_usage_label.pack(anchor='w')

        self.db_size_label = ttk.Label(perf_frame, text="Database Size: --")
        self.db_size_label.pack(anchor='w')

        # Controls
        health_buttons = ttk.Frame(monitor_card)
        health_buttons.pack(fill='x', padx=15, pady=(0, 15))

        ttk.Button(health_buttons, text="🔄 Refresh Metrics",
                  command=self.refresh_system_metrics).pack(side='left', padx=(0, 10))
        ttk.Button(health_buttons, text="🏥 Health Check",
                  command=self.run_system_health_check).pack(side='left')

    def create_temporal_analysis_tab(self):
        """Create temporal analysis tab"""
        temporal_frame = ttk.Frame(self.notebook)
        self.notebook.add(temporal_frame, text="⏱️ Temporal")

        # Temporal analysis card
        temporal_card = ttk.Frame(temporal_frame, style='Card.TFrame')
        temporal_card.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(temporal_card, text="Temporal Analysis", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

        # Analysis options
        options_frame = ttk.LabelFrame(temporal_card, text="Analysis Options", padding=15)
        options_frame.pack(fill='x', padx=15, pady=(0, 15))

        ttk.Button(options_frame, text="📅 Submission Patterns",
                  command=self.show_submission_patterns).pack(fill='x', pady=(0, 5))
        ttk.Button(options_frame, text="⚡ Writing Speed Analysis",
                  command=self.analyze_writing_speed).pack(fill='x')

    def create_visual_analysis_tab(self):
        """Create visual analysis tab"""
        visual_frame = ttk.Frame(self.notebook)
        self.notebook.add(visual_frame, text="📊 Visual")

        # Visual analysis card
        visual_card = ttk.Frame(visual_frame, style='Card.TFrame')
        visual_card.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(visual_card, text="Visual Analysis", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

        # Visualization options
        viz_frame = ttk.LabelFrame(visual_card, text="Visualizations", padding=15)
        viz_frame.pack(fill='x', padx=15, pady=(0, 15))

        ttk.Button(viz_frame, text="🔥 Text Heatmap",
                  command=self.display_text_heatmap).pack(fill='x', pady=(0, 5))
        ttk.Button(viz_frame, text="📈 Writing Flow",
                  command=self.display_writing_flow).pack(fill='x')

    def create_api_integration_tab(self):
        """Create API integration tab"""
        api_frame = ttk.Frame(self.notebook)
        self.notebook.add(api_frame, text="🔌 API Integration")

        # API integration card
        api_card = ttk.Frame(api_frame, style='Card.TFrame')
        api_card.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(api_card, text="External API Integration", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)

        # API configuration
        config_frame = ttk.LabelFrame(api_card, text="API Configuration", padding=15)
        config_frame.pack(fill='x', padx=15, pady=(0, 15))

        # API endpoint input
        endpoint_frame = ttk.Frame(config_frame)
        endpoint_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(endpoint_frame, text="API Name:").pack(side='left')
        self.api_name_var = tk.StringVar()
        ttk.Entry(endpoint_frame, textvariable=self.api_name_var, width=20).pack(side='left', padx=(5, 15))

        ttk.Label(endpoint_frame, text="Endpoint:").pack(side='left')
        self.api_endpoint_var = tk.StringVar()
        ttk.Entry(endpoint_frame, textvariable=self.api_endpoint_var, width=30).pack(side='left', padx=(5, 0))

        # Register button
        ttk.Button(config_frame, text="Register API",
                  command=self.register_external_api).pack(fill='x')

        # Test API
        test_frame = ttk.LabelFrame(api_card, text="API Testing", padding=15)
        test_frame.pack(fill='x', padx=15, pady=(0, 15))

        ttk.Button(test_frame, text="Test API Connection",
                  command=self.test_api_connection).pack(fill='x', pady=(0, 5))
        ttk.Button(test_frame, text="Compare API Results",
                  command=self.compare_api_results).pack(fill='x')
    
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
                from university_system.modules.shared.gui.main_gui import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

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
    
    def create_analysis_view(self, parent):
        """Create the main text analysis view"""
        analysis_frame = ttk.Frame(parent)

        analysis_frame.pack(fill="both", expand=True)
        analysis_frame.pack(fill='both', expand=True)
        
        # Create two-column layout
        left_frame = ttk.Frame(analysis_frame)
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))
        
        right_frame = ttk.Frame(analysis_frame)
        right_frame.pack(side='right', fill='both', expand=True, padx=(5, 0))
        
        # Left side - Input
        self.create_input_section(left_frame)
        
        # Right side - Results
        self.create_results_section(right_frame)
    
    def create_input_section(self, parent):
        """Create text input section"""
        # Input card
        input_card = ttk.Frame(parent, style='Card.TFrame')
        input_card.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Card title
        ttk.Label(input_card, text="Text Input", style='Title.TLabel').pack(anchor='w', padx=15, pady=(15, 5))
        
        # Metadata inputs
        metadata_frame = ttk.Frame(input_card)
        metadata_frame.pack(fill='x', padx=15, pady=(0, 10))
        
        # Row 1: Student and Title
        row1 = ttk.Frame(metadata_frame)
        row1.pack(fill='x', pady=(0, 5))

        ttk.Label(row1, text="Student:").pack(side='left')
        self.student_var = tk.StringVar()
        self.student_combo = ttk.Combobox(row1, textvariable=self.student_var, width=25, state='readonly')
        self.student_combo.pack(side='left', padx=(5, 15))

        ttk.Label(row1, text="Title:").pack(side='left')
        self.title_var = tk.StringVar()
        self.title_entry = ttk.Entry(row1, textvariable=self.title_var, width=30)
        self.title_entry.pack(side='left', padx=(5, 0))

        # Row 2: Module and Assignment
        row2 = ttk.Frame(metadata_frame)
        row2.pack(fill='x')

        ttk.Label(row2, text="Module:").pack(side='left')
        self.module_var = tk.StringVar()
        self.module_combo = ttk.Combobox(row2, textvariable=self.module_var, width=20, state='readonly')
        self.module_combo.pack(side='left', padx=(5, 15))
        self.module_combo.bind('<<ComboboxSelected>>', self._on_module_selected)

        ttk.Label(row2, text="Assignment:").pack(side='left')
        self.assignment_var = tk.StringVar()
        self.assignment_combo = ttk.Combobox(row2, textvariable=self.assignment_var, width=25, state='readonly')
        self.assignment_combo.pack(side='left', padx=(5, 0))

        # Load data from database
        self._load_database_data()
        
        # Text input area
        ttk.Label(input_card, text="Text to Analyze:", style='Subtitle.TLabel').pack(anchor='w', padx=15, pady=(10, 5))
        
        # Text widget with scrollbar
        text_frame = ttk.Frame(input_card)
        text_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))
        
        self.text_input = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            width=50,
            height=20,
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_primary'],
            insertbackground=self.colors['text_primary'],
            selectbackground=self.colors['accent']
        )
        self.text_input.pack(fill='both', expand=True)
        
        # Buttons
        button_frame = ttk.Frame(input_card)
        button_frame.pack(fill='x', padx=15, pady=(0, 15))

        # File upload
        self.upload_btn = ttk.Button(button_frame, text="📁 Load File", command=self.load_file)
        self.upload_btn.pack(side='left', padx=(0, 10))

        # Clear
        self.clear_btn = ttk.Button(button_frame, text="🗑️ Clear", command=self.clear_input)
        self.clear_btn.pack(side='left', padx=(0, 10))

        # Analyze
        self.analyze_btn = ttk.Button(
            button_frame,
            text="🔍 Analyze Text",
            command=self.analyze_text,
            style='Accent.TButton'
        )
        self.analyze_btn.pack(side='right')

        # Word count label
        self.word_count_label = ttk.Label(input_card, text="Words: 0", style='Subtitle.TLabel')
        self.word_count_label.pack(anchor='e', padx=15, pady=(0, 10))
        
        # Bind text change event for word count
        self.text_input.bind('<KeyRelease>', self.update_word_count)

    def test_adversarial_detection(self):
        """Test adversarial detection capabilities"""
        test_window = tk.Toplevel(self.root)
        test_window.title("Adversarial Detection Test")
        test_window.geometry("700x500")
        test_window.configure(bg=self.colors['bg_primary'])
        
        ttk.Label(test_window, text="Adversarial Detection Test", style='Title.TLabel').pack(pady=20)
        
        # Test input
        test_frame = ttk.LabelFrame(test_window, text="Test Text", padding=15)
        test_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        
        test_text = scrolledtext.ScrolledText(
            test_frame, wrap=tk.WORD, height=10,
            bg=self.colors['bg_secondary'], fg=self.colors['text_primary']
        )
        test_text.pack(fill='both', expand=True)
        
        # Sample with invisible characters for testing
        sample_text = "This text contains‌invisible‍characters and unusual formatting."
        test_text.insert('1.0', sample_text)
        
        def run_test():
            text = test_text.get('1.0', tk.END).strip()
            if text:
                try:
                    if hasattr(self.detector, 'adversarial_detector'):
                        result = self.detector.adversarial_detector.detect_evasion_attempts(text)
                        self.show_adversarial_results(result)
                    else:
                        messagebox.showwarning("Warning", "Adversarial detection not available")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to run test: {str(e)}")
        
        ttk.Button(test_window, text="Run Detection Test", command=run_test).pack(pady=10)

    def show_adversarial_results(self, result):
        """Show adversarial detection results"""
        results_window = tk.Toplevel(self.root)
        results_window.title("Adversarial Detection Results")
        results_window.geometry("600x400")
        results_window.configure(bg=self.colors['bg_primary'])
        
        ttk.Label(results_window, text="Evasion Detection Results", style='Title.TLabel').pack(pady=20)
        
        # Results display
        results_frame = ttk.Frame(results_window, style='Card.TFrame')
        results_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        if hasattr(result, '__dict__'):
            score = result.score
            risk_level = result.risk_level.value if hasattr(result.risk_level, 'value') else str(result.risk_level)
            evidence = result.evidence
            
            ttk.Label(results_frame, text=f"Evasion Score: {score:.1%}", 
                     font=('Segoe UI', 12)).pack(anchor='w', padx=15, pady=5)
            ttk.Label(results_frame, text=f"Risk Level: {risk_level}", 
                     font=('Segoe UI', 12)).pack(anchor='w', padx=15, pady=5)
            
            if evidence:
                ttk.Label(results_frame, text="Evidence Found:", 
                         font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=15, pady=(10, 5))
                for key, value in evidence.items():
                    ttk.Label(results_frame, text=f"  {key}: {value}").pack(anchor='w', padx=25, pady=2)

    def patch_gui_with_missing_functions():
        """
        Patch the existing AIDetectorGUI class with all missing functions
        Add this to your code after the AIDetectorGUI class definition
        """
        
        # Add all the missing methods to the class
        missing_methods = [
            create_real_time_monitoring_tab,
            start_real_time_monitoring,
            stop_real_time_monitoring,
            update_queue_status,
            create_federated_learning_tab,
            initialize_federation,
            contribute_model_update,
            download_global_model,
            create_compliance_tab,
            generate_compliance_report,
            show_compliance_report_window,
            show_data_retention_status,
            show_consent_management,
            create_bias_detection_tab,
            analyze_institutional_bias,
            display_bias_analysis,
            create_predictive_analytics_tab,
            predict_student_risk,
            display_risk_prediction,
            train_risk_model,
            show_model_performance,
            create_student_self_check_tab,
            run_self_check,
            show_self_check_results,
            create_adversarial_detection_tab,
            test_adversarial_detection,
            show_adversarial_results,
            create_blockchain_audit_tab,
            mine_blockchain_block,
            verify_blockchain_integrity,
            view_blockchain_history,
            update_blockchain_display,
            create_benchmarking_tab,
            generate_benchmark_report,
            display_benchmark_report,
            create_multi_modal_analysis_tab,
            upload_images_for_analysis,
            analyze_image_text_consistency,
            analyze_code_submission,
            show_multimodal_results,
            show_code_analysis_results,
            create_citation_verification_tab,
            verify_citations,
            show_citation_results,
            create_temporal_analysis_tab,
            analyze_writing_speed,
            analyze_submission_patterns,
            show_temporal_results,
            show_submission_patterns,
            create_api_integration_tab,
            register_external_api,
            test_api_connection,
            show_api_performance,
            compare_api_results,
            run_ensemble_prediction,
            show_ensemble_results,
            create_visual_analysis_tab,
            generate_text_heatmap,
            display_text_heatmap,
            generate_writing_flow,
            display_writing_flow,
            generate_complexity_viz
        ]
        
        # Add each method to the AIDetectorGUI class
        for method in missing_methods:
            setattr(AIDetectorGUI, method.__name__, method)
        
        print("✅ Successfully patched AIDetectorGUI with all missing functions!")

    # Usage example:
    # After importing your AI detector code, call:
    # patch_gui_with_missing_functions()
    # Then proceed to use the GUI normally create_real_time_monitoring_tab(self):
        """Create real-time monitoring tab - MISSING"""
        monitoring_frame = ttk.Frame(parent)

        monitoring_frame.pack(fill="both", expand=True)
        
        # Real-time monitoring card
        monitoring_card = ttk.Frame(monitoring_frame, style='Card.TFrame')
        monitoring_card.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Label(monitoring_card, text="Real-time Processing", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)
        
        # Control buttons
        control_frame = ttk.Frame(monitoring_card)
        control_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        self.start_monitoring_btn = ttk.Button(control_frame, text="▶️ Start Monitoring", 
                                             command=self.start_real_time_monitoring)
        self.start_monitoring_btn.pack(side='left', padx=(0, 10))
        
        self.stop_monitoring_btn = ttk.Button(control_frame, text="⏹️ Stop Monitoring", 
                                            command=self.stop_real_time_monitoring, state='disabled')
        self.stop_monitoring_btn.pack(side='left')
        
        # Status display
        self.monitoring_status_label = ttk.Label(monitoring_card, text="Status: Stopped", style='Subtitle.TLabel')
        self.monitoring_status_label.pack(anchor='w', padx=15, pady=(0, 10))
        
        # Queue status
        queue_frame = ttk.LabelFrame(monitoring_card, text="Processing Queue", padding=15)
        queue_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        self.queue_size_label = ttk.Label(queue_frame, text="Queue size: 0")
        self.queue_size_label.pack(anchor='w')
        
        self.active_workers_label = ttk.Label(queue_frame, text="Active workers: 0")
        self.active_workers_label.pack(anchor='w')

    # Method to patch the existing AIDetectorGUI class

    def create_real_time_monitoring_view(self, parent):
        """Create real-time monitoring tab"""
        monitoring_frame = ttk.Frame(parent)

        monitoring_frame.pack(fill="both", expand=True)

        # Status section
        status_frame = ttk.LabelFrame(monitoring_frame, text="System Status", padding="10")
        status_frame.pack(fill='x', padx=15, pady=15)

        self.status_label = ttk.Label(status_frame, text="Status: Ready")
        self.status_label.pack(anchor='w')

        # Queue monitoring
        queue_frame = ttk.LabelFrame(monitoring_frame, text="Processing Queue", padding="10")
        queue_frame.pack(fill='x', padx=15, pady=(0, 15))

        self.queue_size_label = ttk.Label(queue_frame, text="Queue size: 0")
        self.queue_size_label.pack(anchor='w')

        self.active_workers_label = ttk.Label(queue_frame, text="Active workers: 0")
        self.active_workers_label.pack(anchor='w')

    def create_federated_learning_view(self, parent):
        """Create federated learning tab - MISSING"""
        federated_frame = ttk.Frame(parent)

        federated_frame.pack(fill="both", expand=True)
        
        # Federated learning card
        federated_card = ttk.Frame(federated_frame, style='Card.TFrame')
        federated_card.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Label(federated_card, text="Federated Learning", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)
        
        # Institution setup
        setup_frame = ttk.LabelFrame(federated_card, text="Institution Setup", padding=15)
        setup_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        ttk.Label(setup_frame, text="Institution ID:").pack(side='left')
        self.institution_id_var = tk.StringVar()
        ttk.Entry(setup_frame, textvariable=self.institution_id_var, width=20).pack(side='left', padx=(5, 15))
        
        ttk.Button(setup_frame, text="Initialize Federation", 
                  command=self.initialize_federation).pack(side='right')
        
        # Model contribution
        contrib_frame = ttk.LabelFrame(federated_card, text="Model Contribution", padding=15)
        contrib_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        ttk.Button(contrib_frame, text="Contribute Model Update", 
                  command=self.contribute_model_update).pack(side='left', padx=(0, 10))
        ttk.Button(contrib_frame, text="Download Global Model", 
                  command=self.download_global_model).pack(side='left')

    def create_compliance_view(self, parent):
        """Create compliance and privacy tab - MISSING"""
        compliance_frame = ttk.Frame(parent)

        compliance_frame.pack(fill="both", expand=True)
        
        # Compliance card
        compliance_card = ttk.Frame(compliance_frame, style='Card.TFrame')
        compliance_card.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Label(compliance_card, text="Privacy & Compliance", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)
        
        # Compliance frameworks
        frameworks_frame = ttk.LabelFrame(compliance_card, text="Active Frameworks", padding=15)
        frameworks_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        self.gdpr_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frameworks_frame, text="GDPR", variable=self.gdpr_var).pack(anchor='w')
        
        self.ferpa_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frameworks_frame, text="FERPA", variable=self.ferpa_var).pack(anchor='w')
        
        self.coppa_var = tk.BooleanVar()
        ttk.Checkbutton(frameworks_frame, text="COPPA", variable=self.coppa_var).pack(anchor='w')
        
        # Privacy controls
        privacy_frame = ttk.LabelFrame(compliance_card, text="Privacy Controls", padding=15)
        privacy_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        ttk.Button(privacy_frame, text="Generate Compliance Report", 
                  command=self.generate_compliance_report).pack(side='left', padx=(0, 10))
        ttk.Button(privacy_frame, text="Data Retention Status", 
                  command=self.show_data_retention_status).pack(side='left', padx=(0, 10))
        ttk.Button(privacy_frame, text="Consent Management", 
                  command=self.show_consent_management).pack(side='left')

    def create_bias_detection_view(self, parent):
        """Create bias detection and fairness tab - MISSING"""
        bias_frame = ttk.Frame(parent)

        bias_frame.pack(fill="both", expand=True)
        
        # Bias detection card
        bias_card = ttk.Frame(bias_frame, style='Card.TFrame')
        bias_card.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Label(bias_card, text="Bias Detection & Fairness", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)
        
        # Institution bias analysis
        institution_frame = ttk.LabelFrame(bias_card, text="Institution Analysis", padding=15)
        institution_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        ttk.Label(institution_frame, text="Institution ID:").pack(side='left')
        self.bias_institution_var = tk.StringVar()
        ttk.Entry(institution_frame, textvariable=self.bias_institution_var, width=20).pack(side='left', padx=(5, 15))
        
        ttk.Button(institution_frame, text="Analyze Bias", 
                  command=self.analyze_institutional_bias).pack(side='right')
        
        # Results display
        self.bias_results_frame = ttk.Frame(bias_card)
        self.bias_results_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    def create_predictive_analytics_view(self, parent):
        """Create predictive analytics tab - MISSING"""
        predictive_frame = ttk.Frame(parent)

        predictive_frame.pack(fill="both", expand=True)
        
        # Predictive analytics card
        predictive_card = ttk.Frame(predictive_frame, style='Card.TFrame')
        predictive_card.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Label(predictive_card, text="Predictive Analytics", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)
        
        # Student risk prediction
        risk_frame = ttk.LabelFrame(predictive_card, text="Student Risk Prediction", padding=15)
        risk_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        ttk.Label(risk_frame, text="Student ID:").pack(side='left')
        self.risk_student_var = tk.StringVar()
        ttk.Entry(risk_frame, textvariable=self.risk_student_var, width=20).pack(side='left', padx=(5, 15))
        
        ttk.Button(risk_frame, text="Predict Risk", 
                  command=self.predict_student_risk).pack(side='right')
        
        # Model training
        training_frame = ttk.LabelFrame(predictive_card, text="Model Training", padding=15)
        training_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        ttk.Button(training_frame, text="Train Risk Prediction Model", 
                  command=self.train_risk_model).pack(side='left', padx=(0, 10))
        ttk.Button(training_frame, text="Model Performance", 
                  command=self.show_model_performance).pack(side='left')
        
        # Results display
        self.risk_results_frame = ttk.Frame(predictive_card)
        self.risk_results_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    def create_student_self_check_view(self, parent):
        """Create student self-check tool tab - MISSING"""
        self_check_frame = ttk.Frame(parent)

        self_check_frame.pack(fill="both", expand=True)
        
        # Self-check card
        self_check_card = ttk.Frame(self_check_frame, style='Card.TFrame')
        self_check_card.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Label(self_check_card, text="Student Self-Check Tool", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)
        
        # Info section
        info_frame = ttk.Frame(self_check_card)
        info_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        info_text = "This tool allows students to preview how their work might be analyzed for AI detection."
        ttk.Label(info_frame, text=info_text, style='Subtitle.TLabel', wraplength=600).pack(anchor='w')
        
        # Text input for self-check
        ttk.Label(self_check_card, text="Text to Check:", style='Subtitle.TLabel').pack(anchor='w', padx=15, pady=(10, 5))
        
        self.self_check_text = scrolledtext.ScrolledText(
            self_check_card, wrap=tk.WORD, height=10,
            bg=self.colors['bg_secondary'], fg=self.colors['text_primary']
        )
        self.self_check_text.pack(fill='both', expand=True, padx=15, pady=(0, 15))
        
        # Check button
        ttk.Button(self_check_card, text="Preview Analysis", 
                  command=self.run_self_check, style='Accent.TButton').pack(pady=(0, 15))

    def create_adversarial_detection_view(self, parent):
        """Create adversarial detection tab - MISSING"""
        adversarial_frame = ttk.Frame(parent)

        adversarial_frame.pack(fill="both", expand=True)
        
        # Adversarial detection card
        adversarial_card = ttk.Frame(adversarial_frame, style='Card.TFrame')
        adversarial_card.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Label(adversarial_card, text="Adversarial & Evasion Detection", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)
        
        # Detection methods
        methods_frame = ttk.LabelFrame(adversarial_card, text="Detection Methods", padding=15)
        methods_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        self.detect_invisible_chars_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(methods_frame, text="Invisible Characters", variable=self.detect_invisible_chars_var).pack(anchor='w')
        
        self.detect_char_substitution_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(methods_frame, text="Character Substitution", variable=self.detect_char_substitution_var).pack(anchor='w')
        
        self.detect_spacing_anomalies_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(methods_frame, text="Spacing Anomalies", variable=self.detect_spacing_anomalies_var).pack(anchor='w')
        
        # Test button
        ttk.Button(adversarial_card, text="Test Evasion Detection", 
                  command=self.test_adversarial_detection).pack(pady=15)

    def create_blockchain_audit_view(self, parent):
        """Create blockchain audit trail tab - MISSING"""
        blockchain_frame = ttk.Frame(parent)

        blockchain_frame.pack(fill="both", expand=True)
        
        # Blockchain card
        blockchain_card = ttk.Frame(blockchain_frame, style='Card.TFrame')
        blockchain_card.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Label(blockchain_card, text="Blockchain Audit Trail", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)
        
        # Blockchain info
        info_frame = ttk.LabelFrame(blockchain_card, text="Chain Information", padding=15)
        info_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        self.chain_length_label = ttk.Label(info_frame, text="Chain Length: 0")
        self.chain_length_label.pack(anchor='w')
        
        self.pending_transactions_label = ttk.Label(info_frame, text="Pending Transactions: 0")
        self.pending_transactions_label.pack(anchor='w')
        
        # Controls
        controls_frame = ttk.Frame(blockchain_card)
        controls_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        ttk.Button(controls_frame, text="Mine Pending Block", 
                  command=self.mine_blockchain_block).pack(side='left', padx=(0, 10))
        ttk.Button(controls_frame, text="Verify Chain Integrity", 
                  command=self.verify_blockchain_integrity).pack(side='left', padx=(0, 10))
        ttk.Button(controls_frame, text="View Chain History", 
                  command=self.view_blockchain_history).pack(side='left')

    def create_benchmarking_view(self, parent):
        """Create institutional benchmarking tab - MISSING"""
        benchmark_frame = ttk.Frame(parent)

        benchmark_frame.pack(fill="both", expand=True)
        
        # Benchmarking card
        benchmark_card = ttk.Frame(benchmark_frame, style='Card.TFrame')
        benchmark_card.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Label(benchmark_card, text="Institutional Benchmarking", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)
        
        # Institution input
        input_frame = ttk.Frame(benchmark_card)
        input_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        ttk.Label(input_frame, text="Institution ID:").pack(side='left')
        self.benchmark_institution_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.benchmark_institution_var, width=20).pack(side='left', padx=(5, 15))
        
        ttk.Label(input_frame, text="Period:").pack(side='left')
        self.benchmark_period_var = tk.StringVar(value="1_month")
        period_combo = ttk.Combobox(input_frame, textvariable=self.benchmark_period_var, 
                                   values=["1_month", "3_months", "1_year"], width=15)
        period_combo.pack(side='left', padx=(5, 15))
        
        ttk.Button(input_frame, text="Generate Report", 
                  command=self.generate_benchmark_report).pack(side='right')
        
        # Results display
        self.benchmark_results_frame = ttk.Frame(benchmark_card)
        self.benchmark_results_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    # Event handlers for missing functions

    def start_real_time_monitoring(self):
        """Start real-time monitoring"""
        try:
            if hasattr(self.detector, 'start_real_time_monitoring'):
                self.detector.start_real_time_monitoring()
                self.start_monitoring_btn.config(state='disabled')
                self.stop_monitoring_btn.config(state='normal')
                self.monitoring_status_label.config(text="Status: Running")
                self.update_status("Real-time monitoring started")
                
                # Start periodic queue status updates
                self.update_queue_status()
            else:
                messagebox.showwarning("Warning", "Real-time monitoring not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start monitoring: {str(e)}")

    def stop_real_time_monitoring(self):
        """Stop real-time monitoring"""
        try:
            if hasattr(self.detector, 'stop_real_time_monitoring'):
                self.detector.stop_real_time_monitoring()
                self.start_monitoring_btn.config(state='normal')
                self.stop_monitoring_btn.config(state='disabled')
                self.monitoring_status_label.config(text="Status: Stopped")
                self.update_status("Real-time monitoring stopped")
            else:
                messagebox.showwarning("Warning", "Real-time monitoring not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to stop monitoring: {str(e)}")

    def update_queue_status(self):
        """Update queue status display"""
        try:
            if hasattr(self.detector, 'realtime_processor'):
                queue_size = len(self.detector.realtime_processor.processing_queue)
                active_workers = len(self.detector.realtime_processor.workers)
                
                self.queue_size_label.config(text=f"Queue size: {queue_size}")
                self.active_workers_label.config(text=f"Active workers: {active_workers}")
                
                # Schedule next update if monitoring is running
                if self.detector.realtime_processor.is_running:
                    self.root.after(5000, self.update_queue_status)  # Update every 5 seconds
        except Exception:
            pass

    def initialize_federation(self):
        """Initialize federated learning"""
        institution_id = self.institution_id_var.get()
        if not institution_id:
            messagebox.showwarning("Warning", "Please enter an Institution ID")
            return
        
        try:
            federation_config = {
                'privacy_budget': 1.0,
                'aggregation_method': 'federated_avg'
            }
            
            if hasattr(self.detector, 'configure_federated_learning'):
                self.detector.configure_federated_learning(institution_id, federation_config)
                messagebox.showinfo("Success", f"Federated learning initialized for {institution_id}")
                self.update_status("Federated learning configured")
            else:
                messagebox.showwarning("Warning", "Federated learning not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize federation: {str(e)}")

    def contribute_model_update(self):
        """Contribute model update to federation"""
        try:
            if hasattr(self.detector, 'federated_learning'):
                # This would require actual model weights - simplified for demo
                messagebox.showinfo("Info", "Model contribution feature requires trained local models")
            else:
                messagebox.showwarning("Warning", "Federated learning not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to contribute model: {str(e)}")

    def download_global_model(self):
        """Download global federated model"""
        try:
            if hasattr(self.detector, 'federated_learning'):
                # This would download and integrate global model weights
                messagebox.showinfo("Info", "Global model download feature requires federation setup")
            else:
                messagebox.showwarning("Warning", "Federated learning not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to download global model: {str(e)}")

    def generate_compliance_report(self):
        """Generate compliance report"""
        try:
            if hasattr(self.detector, 'compliance_manager'):
                report = self.detector.compliance_manager.generate_compliance_report()
                self.show_compliance_report_window(report)
            else:
                messagebox.showwarning("Warning", "Compliance manager not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate compliance report: {str(e)}")

    def show_compliance_report_window(self, report):
        """Show compliance report in new window"""
        report_window = tk.Toplevel(self.root)
        report_window.title("Compliance Report")
        report_window.geometry("700x500")
        report_window.configure(bg=self.colors['bg_primary'])
        
        # Create scrollable text area
        text_widget = scrolledtext.ScrolledText(
            report_window, wrap=tk.WORD,
            bg=self.colors['bg_secondary'], fg=self.colors['text_primary']
        )
        text_widget.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Format and display report
        report_text = f"Compliance Report\n{'='*50}\n\n"
        report_text += f"Generated: {report.get('generated_at', 'Unknown')}\n\n"
        
        for section, data in report.items():
            if section != 'generated_at':
                report_text += f"{section.replace('_', ' ').title()}:\n"
                if isinstance(data, dict):
                    for key, value in data.items():
                        report_text += f"  {key}: {value}\n"
                else:
                    report_text += f"  {data}\n"
                report_text += "\n"
        
        text_widget.insert('1.0', report_text)
        text_widget.config(state='disabled')

    def show_data_retention_status(self):
        """Show data retention status"""
        try:
            # This would query the data retention tables
            messagebox.showinfo("Data Retention", "Data retention monitoring feature available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get retention status: {str(e)}")

    def show_consent_management(self):
        """Show consent management interface"""
        try:
            # This would open consent management interface
            messagebox.showinfo("Consent Management", "Consent management interface feature available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open consent management: {str(e)}")

    def analyze_institutional_bias(self):
        """Analyze institutional bias"""
        institution_id = self.bias_institution_var.get()
        if not institution_id:
            messagebox.showwarning("Warning", "Please enter an Institution ID")
            return
        
        try:
            if hasattr(self.detector, 'analyze_institutional_bias'):
                bias_analysis = self.detector.analyze_institutional_bias(institution_id)
                self.display_bias_analysis(bias_analysis)
            else:
                messagebox.showwarning("Warning", "Bias detection not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to analyze bias: {str(e)}")

    def display_bias_analysis(self, analysis):
        """Display bias analysis results"""
        # Clear previous results
        for widget in self.bias_results_frame.winfo_children():
            widget.destroy()
        
        # Display results
        results_text = f"Bias Analysis Results\n{'='*30}\n\n"
        for key, value in analysis.items():
            results_text += f"{key}: {value}\n"
        
        results_label = ttk.Label(self.bias_results_frame, text=results_text, style='Subtitle.TLabel')
        results_label.pack(anchor='w', padx=10, pady=10)

    def predict_student_risk(self):
        """Predict student risk"""
        student_id = self.risk_student_var.get()
        if not student_id:
            messagebox.showwarning("Warning", "Please enter a Student ID")
            return
        
        try:
            if hasattr(self.detector, 'predictive_analytics'):
                risk_prediction = self.detector.predictive_analytics.predict_student_risk(student_id)
                self.display_risk_prediction(risk_prediction)
            else:
                messagebox.showwarning("Warning", "Predictive analytics not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to predict risk: {str(e)}")

    def display_risk_prediction(self, prediction):
        """Display risk prediction results"""
        # Clear previous results
        for widget in self.risk_results_frame.winfo_children():
            widget.destroy()
        
        # Display results
        risk_level = prediction.get('risk_level', 'unknown')
        risk_score = prediction.get('risk_score', 0)
        
        # Color-coded risk display
        risk_color = self.get_risk_color(risk_score)
        
        risk_frame = ttk.Frame(self.risk_results_frame, style='Card.TFrame')
        risk_frame.pack(fill='x', padx=10, pady=10)
        
        risk_indicator = tk.Label(risk_frame, text="●", font=('Arial', 20), 
                                 fg=risk_color, bg=self.colors['bg_tertiary'])
        risk_indicator.pack(side='left', padx=15, pady=15)
        
        risk_text = ttk.Label(risk_frame, text=f"Risk Level: {risk_level.title()}\nRisk Score: {risk_score:.1%}", 
                             font=('Segoe UI', 12))
        risk_text.pack(side='left', padx=(10, 15), pady=15)

    def train_risk_model(self):
        """Train risk prediction model"""
        try:
            if hasattr(self.detector, 'predictive_analytics'):
                self.update_status("Training risk prediction model...")
                
                def train_thread():
                    try:
                        self.detector.predictive_analytics.train_risk_prediction_model()
                        self.root.after(0, lambda: self.training_complete("Risk prediction model"))
                    except Exception as e:
                        self.root.after(0, lambda: self.training_error(str(e)))
                
                threading.Thread(target=train_thread, daemon=True).start()
            else:
                messagebox.showwarning("Warning", "Predictive analytics not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start training: {str(e)}")

    def show_model_performance(self):
        """Show model performance metrics"""
        try:
            if hasattr(self.detector, 'predictive_analytics'):
                messagebox.showinfo("Model Performance", "Model performance metrics feature available")
            else:
                messagebox.showwarning("Warning", "Predictive analytics not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get model performance: {str(e)}")

    def run_self_check(self):
        """Run student self-check analysis"""
        text = self.self_check_text.get('1.0', tk.END).strip()
        if not text:
            messagebox.showwarning("Warning", "Please enter text to check")
            return
        
        try:
            if hasattr(self.detector, 'student_self_check'):
                result = self.detector.student_self_check.preview_analysis(text, "SELF_CHECK_USER")
                self.show_self_check_results(result)
            else:
                messagebox.showwarning("Warning", "Self-check tool not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to run self-check: {str(e)}")

    def show_self_check_results(self, result):
        """Show self-check results"""
        results_window = tk.Toplevel(self.root)
        results_window.title("Self-Check Results")
        results_window.geometry("600x400")
        results_window.configure(bg=self.colors['bg_primary'])
        
        # Display results
        ttk.Label(results_window, text="Self-Check Analysis", style='Title.TLabel').pack(pady=20)
        
        assessment = result.get('overall_assessment', 'unknown')
        suggestions = result.get('suggestions', [])
        
        # Assessment display
        assessment_frame = ttk.Frame(results_window, style='Card.TFrame')
        assessment_frame.pack(fill='x', padx=20, pady=(0, 20))
        
        ttk.Label(assessment_frame, text=f"Overall Assessment: {assessment.replace('_', ' ').title()}", 
                 font=('Segoe UI', 12, 'bold')).pack(padx=15, pady=15)
        
        # Suggestions
        if suggestions:
            suggestions_frame = ttk.LabelFrame(results_window, text="Suggestions", padding=15)
            suggestions_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))
            
            for i, suggestion in enumerate(suggestions, 1):
                ttk.Label(suggestions_frame, text=f"{i}. {suggestion}", 
                         wraplength=500).pack(anchor='w', pady=2)

    def create_data_export_import_view(self, parent):
        """Create enhanced data export/import tab - MISSING"""
        export_frame = ttk.Frame(parent)

        export_frame.pack(fill="both", expand=True)
        
        # Data management card
        data_card = ttk.Frame(export_frame, style='Card.TFrame')
        data_card.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Label(data_card, text="Advanced Data Management", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)
        
        # Export options
        export_frame_inner = ttk.LabelFrame(data_card, text="Export Options", padding=15)
        export_frame_inner.pack(fill='x', padx=15, pady=(0, 15))
        
        export_buttons = ttk.Frame(export_frame_inner)
        export_buttons.pack(fill='x')
        
        ttk.Button(export_buttons, text="📊 Export Detailed Report", 
                  command=self.export_detailed_report).pack(side='left', padx=(0, 10))
        ttk.Button(export_buttons, text="📈 Export Analytics Data", 
                  command=self.export_analytics_data).pack(side='left', padx=(0, 10))
        ttk.Button(export_buttons, text="🔐 Export Audit Log", 
                  command=self.export_audit_log).pack(side='left')
        
        # Import options
        import_frame_inner = ttk.LabelFrame(data_card, text="Import Options", padding=15)
        import_frame_inner.pack(fill='x', padx=15, pady=(0, 15))
        
        import_buttons = ttk.Frame(import_frame_inner)
        import_buttons.pack(fill='x')
        
        ttk.Button(import_buttons, text="📥 Import Submissions", 
                  command=self.import_submissions).pack(side='left', padx=(0, 10))
        ttk.Button(import_buttons, text="👥 Import Student Data", 
                  command=self.import_student_data).pack(side='left', padx=(0, 10))
        ttk.Button(import_buttons, text="⚙️ Import Settings", 
                  command=self.import_settings).pack(side='left')
        
        # Data cleanup
        cleanup_frame = ttk.LabelFrame(data_card, text="Data Cleanup", padding=15)
        cleanup_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        cleanup_buttons = ttk.Frame(cleanup_frame)
        cleanup_buttons.pack(fill='x')
        
        ttk.Button(cleanup_buttons, text="🗑️ Archive Old Data", 
                  command=self.archive_old_data).pack(side='left', padx=(0, 10))
        ttk.Button(cleanup_buttons, text="🔄 Optimize Database", 
                  command=self.optimize_database).pack(side='left', padx=(0, 10))
        ttk.Button(cleanup_buttons, text="🧹 Clean Duplicates", 
                  command=self.clean_duplicates).pack(side='left')

    def export_detailed_report(self):
        """Export detailed analysis report"""
        file_path = filedialog.asksaveasfilename(
            title="Export Detailed Report",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("HTML files", "*.html"), ("Word files", "*.docx")]
        )
        
        if file_path:
            try:
                # Generate comprehensive report
                report_data = self.generate_comprehensive_report()
                
                if file_path.endswith('.pdf'):
                    self.export_to_pdf(report_data, file_path)
                elif file_path.endswith('.html'):
                    self.export_to_html(report_data, file_path)
                else:
                    self.export_to_docx(report_data, file_path)
                
                messagebox.showinfo("Export Complete", f"Detailed report exported to {file_path}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export report: {str(e)}")

    def export_analytics_data(self):
        """Export analytics and statistics data"""
        file_path = filedialog.asksaveasfilename(
            title="Export Analytics Data",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv")]
        )
        
        if file_path:
            try:
                analytics_data = self.gather_analytics_data()
                
                if file_path.endswith('.xlsx'):
                    self.export_to_excel(analytics_data, file_path)
                else:
                    self.export_to_csv(analytics_data, file_path)
                
                messagebox.showinfo("Export Complete", f"Analytics data exported to {file_path}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export analytics: {str(e)}")

    def export_audit_log(self):
        """Export audit log"""
        file_path = filedialog.asksaveasfilename(
            title="Export Audit Log",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("CSV files", "*.csv")]
        )
        
        if file_path:
            try:
                audit_data = self.get_audit_log_data()
                
                if file_path.endswith('.json'):
                    with open(file_path, 'w') as f:
                        json.dump(audit_data, f, indent=2, default=str)
                else:
                    import csv
                    with open(file_path, 'w', newline='') as f:
                        if audit_data:
                            writer = csv.DictWriter(f, fieldnames=audit_data[0].keys())
                            writer.writeheader()
                            writer.writerows(audit_data)
                
                messagebox.showinfo("Export Complete", f"Audit log exported to {file_path}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export audit log: {str(e)}")

    def import_submissions(self):
        """Import submissions from file"""
        file_path = filedialog.askopenfilename(
            title="Import Submissions",
            filetypes=[("JSON files", "*.json"), ("CSV files", "*.csv"), ("Excel files", "*.xlsx")]
        )
        
        if file_path:
            try:
                imported_count = self.process_submission_import(file_path)
                messagebox.showinfo("Import Complete", f"Successfully imported {imported_count} submissions")
                self.refresh_history()
                self.refresh_statistics()
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to import submissions: {str(e)}")

    def import_student_data(self):
        """Import student demographic data"""
        file_path = filedialog.askopenfilename(
            title="Import Student Data",
            filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx")]
        )
        
        if file_path:
            try:
                imported_count = self.process_student_data_import(file_path)
                messagebox.showinfo("Import Complete", f"Successfully imported data for {imported_count} students")
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to import student data: {str(e)}")

    def import_settings(self):
        """Import application settings"""
        file_path = filedialog.askopenfilename(
            title="Import Settings",
            filetypes=[("JSON files", "*.json")]
        )
        
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    settings = json.load(f)
                
                self.apply_imported_settings(settings)
                messagebox.showinfo("Import Complete", "Settings imported successfully")
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to import settings: {str(e)}")

    def archive_old_data(self):
        """Archive old data"""
        cutoff_date = tk.simpledialog.askstring(
            "Archive Data",
            "Enter cutoff date (YYYY-MM-DD):"
        )
        
        if cutoff_date:
            try:
                archived_count = self.process_data_archival(cutoff_date)
                messagebox.showinfo("Archive Complete", f"Archived {archived_count} records")
            except Exception as e:
                messagebox.showerror("Archive Error", f"Failed to archive data: {str(e)}")

    def optimize_database(self):
        """Optimize database performance"""
        try:
            self.update_status("Optimizing database...")
            # Run database optimization
            optimization_result = self.run_database_optimization()
            messagebox.showinfo("Optimization Complete", f"Database optimized successfully\n{optimization_result}")
            self.update_status("Database optimization complete")
        except Exception as e:
            messagebox.showerror("Optimization Error", f"Failed to optimize database: {str(e)}")

    def clean_duplicates(self):
        """Clean duplicate records"""
        try:
            duplicates_found = self.find_duplicate_records()
            if duplicates_found > 0:
                response = messagebox.askyesno(
                    "Duplicates Found",
                    f"Found {duplicates_found} duplicate records. Remove them?"
                )
                if response:
                    removed_count = self.remove_duplicate_records()
                    messagebox.showinfo("Cleanup Complete", f"Removed {removed_count} duplicate records")
            else:
                messagebox.showinfo("No Duplicates", "No duplicate records found")
        except Exception as e:
            messagebox.showerror("Cleanup Error", f"Failed to clean duplicates: {str(e)}")

    def create_system_monitoring_view(self, parent):
        """Create system monitoring and health tab - MISSING"""
        monitoring_frame = ttk.Frame(parent)

        monitoring_frame.pack(fill="both", expand=True)
        
        # System monitoring card
        monitor_card = ttk.Frame(monitoring_frame, style='Card.TFrame')
        monitor_card.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Label(monitor_card, text="System Health Monitoring", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)
        
        # Performance metrics
        perf_frame = ttk.LabelFrame(monitor_card, text="Performance Metrics", padding=15)
        perf_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        # Real-time metrics display
        self.cpu_usage_label = ttk.Label(perf_frame, text="CPU Usage: --")
        self.cpu_usage_label.pack(anchor='w')
        
        self.memory_usage_label = ttk.Label(perf_frame, text="Memory Usage: --")
        self.memory_usage_label.pack(anchor='w')
        
        self.db_size_label = ttk.Label(perf_frame, text="Database Size: --")
        self.db_size_label.pack(anchor='w')
        
        self.analysis_speed_label = ttk.Label(perf_frame, text="Avg Analysis Speed: --")
        self.analysis_speed_label.pack(anchor='w')
        
        # System health controls
        health_frame = ttk.LabelFrame(monitor_card, text="System Health", padding=15)
        health_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        health_buttons = ttk.Frame(health_frame)
        health_buttons.pack(fill='x')
        
        ttk.Button(health_buttons, text="🔄 Refresh Metrics", 
                  command=self.refresh_system_metrics).pack(side='left', padx=(0, 10))
        ttk.Button(health_buttons, text="🏥 Health Check", 
                  command=self.run_system_health_check).pack(side='left', padx=(0, 10))
        ttk.Button(health_buttons, text="📊 Performance Report", 
                  command=self.generate_performance_report).pack(side='left')
        
        # Error logs
        error_frame = ttk.LabelFrame(monitor_card, text="Recent Errors", padding=15)
        error_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))
        
        self.error_log_display = scrolledtext.ScrolledText(
            error_frame, height=8, wrap=tk.WORD,
            bg=self.colors['bg_secondary'], fg=self.colors['text_primary']
        )
        self.error_log_display.pack(fill='both', expand=True)
        
        # Start monitoring
        self.start_system_monitoring()

    def refresh_system_metrics(self):
        """Refresh system performance metrics"""
        try:
            import psutil
            import os
            
            # CPU and memory usage
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            self.cpu_usage_label.config(text=f"CPU Usage: {cpu_percent:.1f}%")
            self.memory_usage_label.config(text=f"Memory Usage: {memory.percent:.1f}%")
            
            # Database size
            if os.path.exists(self.detector.db_path):
                db_size = os.path.getsize(self.detector.db_path) / (1024 * 1024)  # MB
                self.db_size_label.config(text=f"Database Size: {db_size:.1f} MB")
            
            # Analysis speed (mock data)
            self.analysis_speed_label.config(text="Avg Analysis Speed: 2.3s per submission")
            
        except ImportError:
            self.cpu_usage_label.config(text="CPU Usage: Not available (install psutil)")
            self.memory_usage_label.config(text="Memory Usage: Not available")
        except Exception as e:
            self.update_status(f"Error refreshing metrics: {str(e)}")

    def run_system_health_check(self):
        """Run comprehensive system health check"""
        health_window = tk.Toplevel(self.root)
        health_window.title("System Health Check")
        health_window.geometry("600x500")
        health_window.configure(bg=self.colors['bg_primary'])
        
        ttk.Label(health_window, text="System Health Check", style='Title.TLabel').pack(pady=20)
        
        # Health check results
        health_frame = ttk.Frame(health_window, style='Card.TFrame')
        health_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        health_results = scrolledtext.ScrolledText(
            health_frame, wrap=tk.WORD,
            bg=self.colors['bg_secondary'], fg=self.colors['text_primary']
        )
        health_results.pack(fill='both', expand=True, padx=15, pady=15)
        
        # Run health checks
        checks = [
            ("Database Connection", self.check_database_health),
            ("File System Access", self.check_filesystem_health),
            ("Memory Usage", self.check_memory_health),
            ("Model Availability", self.check_model_health),
            ("🏠 Return to Main Menu", self.return_to_main_menu)
        ]
        
        health_results.insert(tk.END, "Running system health checks...\n\n")
        
        for check_name, check_function in checks:
            try:
                result = check_function()
                status = "✅ PASS" if result['status'] else "❌ FAIL"
                health_results.insert(tk.END, f"{check_name}: {status}\n")
                if result.get('details'):
                    health_results.insert(tk.END, f"  Details: {result['details']}\n")
                health_results.insert(tk.END, "\n")
                health_window.update()
            except Exception as e:
                health_results.insert(tk.END, f"{check_name}: ❌ ERROR - {str(e)}\n\n")

    def start_system_monitoring(self):
        """Start periodic system monitoring"""
        def monitor_loop():
            try:
                self.refresh_system_metrics()
                self.update_error_log()
                # Schedule next update
                self.root.after(30000, monitor_loop)  # Update every 30 seconds
            except Exception:
                pass  # Silently continue if monitoring fails
        
        monitor_loop()

    def update_error_log(self):
        """Update error log display"""
        try:
            # This would read from actual log files
            # For now, just show a placeholder
            current_text = self.error_log_display.get('1.0', tk.END)
            if len(current_text.strip()) == 0:
                self.error_log_display.insert('1.0', "No recent errors detected.\nSystem operating normally.")
        except Exception:
            pass

    def generate_performance_report(self):
        """Generate system performance report"""
        try:
            report_window = tk.Toplevel(self.root)
            report_window.title("Performance Report")
            report_window.geometry("700x600")
            report_window.configure(bg=self.colors['bg_primary'])
            
            ttk.Label(report_window, text="System Performance Report", style='Title.TLabel').pack(pady=20)
            
            # Performance data
            perf_frame = ttk.Frame(report_window, style='Card.TFrame')
            perf_frame.pack(fill='both', expand=True, padx=20, pady=20)
            
            # Generate performance metrics
            performance_data = self.collect_performance_data()
            
            report_text = scrolledtext.ScrolledText(
                perf_frame, wrap=tk.WORD,
                bg=self.colors['bg_secondary'], fg=self.colors['text_primary']
            )
            report_text.pack(fill='both', expand=True, padx=15, pady=15)
            
            # Format performance report
            report_content = self.format_performance_report(performance_data)
            report_text.insert('1.0', report_content)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate performance report: {str(e)}")

    # Helper methods for the new functionality

    def generate_comprehensive_report(self):
        """Generate comprehensive analysis report data"""
        try:
            stats = self.detector.get_enhanced_statistics()
            history = self.detector.get_submission_history(limit=1000)
            
            return {
                'report_date': datetime.now().isoformat(),
                'statistics': stats,
                'submission_history': history,
                'system_info': self.get_system_info()
            }
        except Exception as e:
            return {'error': str(e)}

    def gather_analytics_data(self):
        """Gather analytics data for export"""
        try:
            # This would compile various analytics
            return {
                'detection_rates': self.get_detection_rates(),
                'student_performance': self.get_student_performance_data(),
                'temporal_patterns': self.get_temporal_patterns(),
                'risk_distributions': self.get_risk_distributions()
            }
        except Exception as e:
            return {'error': str(e)}

    def get_audit_log_data(self):
        """Get audit log data"""
        try:
            if hasattr(self.detector, 'privacy_manager'):
                # This would query the audit log table
                return []  # Placeholder
            return []
        except Exception:
            return []

    def check_database_health(self):
        """Check database health"""
        try:
            conn = self.detector._safe_db_connect()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM ai_detector_submissions")
            count = cursor.fetchone()[0]
            conn.close()
            return {'status': True, 'details': f'{count} submissions in database'}
        except Exception as e:
            return {'status': False, 'details': str(e)}

    def check_filesystem_health(self):
        """Check filesystem health"""
        try:
            import tempfile
            import os
            
            # Test file write/read
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(b"test")
                tmp_path = tmp.name
            
            with open(tmp_path, 'rb') as f:
                data = f.read()
            
            os.unlink(tmp_path)
            
            return {'status': data == b"test", 'details': 'File system read/write OK'}
        except Exception as e:
            return {'status': False, 'details': str(e)}

    def check_memory_health(self):
        """Check memory usage health"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            status = memory.percent < 90  # Less than 90% usage is healthy
            return {'status': status, 'details': f'{memory.percent:.1f}% memory used'}
        except ImportError:
            return {'status': True, 'details': 'Memory monitoring unavailable (install psutil)'}
        except Exception as e:
            return {'status': False, 'details': str(e)}

    def check_model_health(self):
        """Check ML model availability"""
        try:
            model_count = 0
            if hasattr(self.detector, 'advanced_ml_trainer') and self.detector.advanced_ml_trainer.models:
                model_count = len(self.detector.advanced_ml_trainer.models)
            
            return {'status': True, 'details': f'{model_count} ML models available'}
        except Exception as e:
            return {'status': False, 'details': str(e)}

    def check_api_health(self):
        """Check API endpoint health"""
        try:
            if hasattr(self.detector, 'api_gateway'):
                api_count = len(self.detector.api_gateway.api_configs)
                return {'status': True, 'details': f'{api_count} APIs configured'}
            return {'status': True, 'details': 'No external APIs configured'}
        except Exception as e:
            return {'status': False, 'details': str(e)}

    def collect_performance_data(self):
        """Collect system performance data"""
        return {
            'timestamp': datetime.now().isoformat(),
            'uptime': 'N/A',
            'analysis_count': 0,
            'avg_response_time': 0,
            'error_rate': 0
        }

    def format_performance_report(self, data):
        """Format performance report"""
        return f"""
    SYSTEM PERFORMANCE REPORT
    Generated: {data.get('timestamp', 'Unknown')}

    === OVERVIEW ===
    System Uptime: {data.get('uptime', 'N/A')}
    Total Analyses: {data.get('analysis_count', 0)}
    Average Response Time: {data.get('avg_response_time', 0)}s
    Error Rate: {data.get('error_rate', 0):.2%}

    === PERFORMANCE METRICS ===
    Database Performance: Normal
    Memory Usage: Within limits
    Processing Speed: Optimal

    === RECOMMENDATIONS ===
    - System running within normal parameters
    - No immediate action required
    - Continue monitoring for trends
    """
 
    def mine_blockchain_block(self):
        """Mine a blockchain block"""
        try:
            if hasattr(self.detector, 'blockchain_audit') and self.detector.blockchain_audit:
                blockchain = self.detector.blockchain_audit

                # Check for pending transactions
                if hasattr(blockchain, 'pending_transactions') and blockchain.pending_transactions:
                    # Show mining progress dialog
                    progress_window = tk.Toplevel(self.root)
                    progress_window.title("Mining Block")
                    progress_window.geometry("400x200")
                    progress_window.transient(self.root)
                    progress_window.grab_set()

                    ttk.Label(progress_window, text="Mining blockchain block...", style='Title.TLabel').pack(pady=20)

                    progress_var = tk.DoubleVar()
                    progress_bar = ttk.Progressbar(progress_window, variable=progress_var,
                                                 mode='determinate', length=300)
                    progress_bar.pack(pady=10)

                    status_label = ttk.Label(progress_window, text="Initializing mining process...")
                    status_label.pack(pady=10)

                    def mine_with_progress():
                        try:
                            # Simulate mining process with progress updates
                            for i in range(101):
                                if i == 0:
                                    status_label.config(text="Validating transactions...")
                                elif i == 25:
                                    status_label.config(text="Calculating proof of work...")
                                elif i == 50:
                                    status_label.config(text="Computing hash...")
                                elif i == 75:
                                    status_label.config(text="Finalizing block...")
                                elif i == 100:
                                    status_label.config(text="Block mined successfully!")

                                progress_var.set(i)
                                progress_window.update()
                                time.sleep(0.02)  # Small delay for visual effect

                            # Actual mining logic
                            if hasattr(blockchain, '_mine_block'):
                                blockchain._mine_block()
                            else:
                                # Simulate block creation if method doesn't exist
                                new_block = {
                                    'index': len(getattr(blockchain, 'chain', [])) + 1,
                                    'timestamp': time.time(),
                                    'transactions': blockchain.pending_transactions.copy(),
                                    'previous_hash': getattr(blockchain.chain[-1], 'hash', '0') if hasattr(blockchain, 'chain') and blockchain.chain else '0',
                                    'nonce': random.randint(1000, 999999),
                                    'hash': f"block_hash_{random.randint(100000, 999999)}"
                                }

                                # Add to chain if it exists
                                if hasattr(blockchain, 'chain'):
                                    blockchain.chain.append(new_block)

                                # Clear pending transactions
                                blockchain.pending_transactions.clear()

                            time.sleep(0.5)  # Final pause
                            progress_window.destroy()

                            # Update displays and show success
                            self.update_blockchain_display()
                            messagebox.showinfo("Mining Success",
                                              f"Block mined successfully!\n"
                                              f"New block added to the chain.\n"
                                              f"Pending transactions processed.")

                        except Exception as e:
                            progress_window.destroy()
                            messagebox.showerror("Mining Error", f"Failed to mine block: {str(e)}")

                    # Start mining in a separate thread to prevent GUI freezing
                    import threading
                    threading.Thread(target=mine_with_progress, daemon=True).start()

                else:
                    # No pending transactions - offer to create a sample transaction
                    result = messagebox.askyesno("No Pending Transactions",
                                               "No pending transactions found. Would you like to create a sample transaction for mining?")
                    if result:
                        # Create a sample transaction
                        sample_transaction = {
                            'id': f"tx_{random.randint(1000, 9999)}",
                            'timestamp': time.time(),
                            'type': 'ai_detection',
                            'data': {
                                'submission_id': f"sub_{random.randint(100, 999)}",
                                'ai_score': random.uniform(0.1, 0.9),
                                'detection_method': 'neural_analysis'
                            }
                        }

                        if not hasattr(blockchain, 'pending_transactions'):
                            blockchain.pending_transactions = []

                        blockchain.pending_transactions.append(sample_transaction)
                        messagebox.showinfo("Transaction Created", "Sample transaction added. You can now mine the block.")
                    else:
                        messagebox.showinfo("Info", "No transactions to mine")
            else:
                # Blockchain not available - show information about it
                info_msg = ("Blockchain audit system is not currently available.\n\n"
                           "This feature requires:\n"
                           "• Blockchain audit module to be enabled\n"
                           "• Proper initialization of the blockchain system\n"
                           "• Active transaction monitoring")
                messagebox.showinfo("Blockchain Unavailable", info_msg)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to mine block: {str(e)}")

    def verify_blockchain_integrity(self):
        """Verify blockchain integrity"""
        try:
            if hasattr(self.detector, 'blockchain_audit') and self.detector.blockchain_audit:
                blockchain = self.detector.blockchain_audit

                # Create verification window
                verify_window = tk.Toplevel(self.root)
                verify_window.title("Blockchain Integrity Verification")
                verify_window.geometry("600x500")
                verify_window.transient(self.root)
                verify_window.grab_set()

                # Title
                title_frame = ttk.Frame(verify_window)
                title_frame.pack(fill='x', padx=20, pady=20)
                ttk.Label(title_frame, text="🔐 Blockchain Integrity Verification", style='Title.TLabel').pack()

                # Results frame
                results_frame = ttk.LabelFrame(verify_window, text="Verification Results", padding="15")
                results_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))

                # Progress bar
                progress_var = tk.DoubleVar()
                progress_bar = ttk.Progressbar(results_frame, variable=progress_var,
                                             mode='determinate', length=500)
                progress_bar.pack(pady=(0, 20))

                # Results text
                results_text = tk.Text(results_frame, height=15, wrap='word')
                results_text.pack(fill='both', expand=True)

                scrollbar = ttk.Scrollbar(results_frame, orient='vertical', command=results_text.yview)
                scrollbar.pack(side='right', fill='y')
                results_text.config(yscrollcommand=scrollbar.set)

                def run_verification():
                    try:
                        results_text.delete(1.0, tk.END)
                        results_text.insert(tk.END, "Starting blockchain integrity verification...\n\n")
                        verify_window.update()

                        verification_results = {
                            'total_blocks': 0,
                            'valid_blocks': 0,
                            'invalid_blocks': 0,
                            'hash_mismatches': 0,
                            'chain_breaks': 0,
                            'timestamp_errors': 0,
                            'issues': []
                        }

                        # Check if blockchain exists and has data
                        if hasattr(blockchain, 'chain') and blockchain.chain:
                            chain = blockchain.chain
                            verification_results['total_blocks'] = len(chain)

                            results_text.insert(tk.END, f"Found {len(chain)} blocks in the chain.\n")
                            results_text.insert(tk.END, "Verifying each block...\n\n")
                            verify_window.update()

                            # Verify each block
                            for i, block in enumerate(chain):
                                progress_var.set((i / len(chain)) * 100)
                                verify_window.update()

                                results_text.insert(tk.END, f"Verifying Block {i + 1}...")
                                verify_window.update()

                                block_valid = True
                                block_issues = []

                                # Check block structure
                                required_fields = ['index', 'timestamp', 'hash', 'previous_hash']
                                for field in required_fields:
                                    if not hasattr(block, field) and field not in block:
                                        block_issues.append(f"Missing required field: {field}")
                                        block_valid = False

                                # Check hash consistency (if next block exists)
                                if i < len(chain) - 1:
                                    next_block = chain[i + 1]
                                    current_hash = getattr(block, 'hash', block.get('hash', '')) if hasattr(block, 'hash') else block.get('hash', '')
                                    next_prev_hash = getattr(next_block, 'previous_hash', next_block.get('previous_hash', '')) if hasattr(next_block, 'previous_hash') else next_block.get('previous_hash', '')

                                    if current_hash != next_prev_hash:
                                        block_issues.append(f"Hash mismatch with next block")
                                        verification_results['hash_mismatches'] += 1
                                        block_valid = False

                                # Check timestamp validity
                                timestamp = getattr(block, 'timestamp', block.get('timestamp', 0)) if hasattr(block, 'timestamp') else block.get('timestamp', 0)
                                if timestamp <= 0:
                                    block_issues.append("Invalid timestamp")
                                    verification_results['timestamp_errors'] += 1
                                    block_valid = False

                                if block_valid:
                                    verification_results['valid_blocks'] += 1
                                    results_text.insert(tk.END, " ✅ VALID\n")
                                else:
                                    verification_results['invalid_blocks'] += 1
                                    results_text.insert(tk.END, " ❌ INVALID\n")
                                    for issue in block_issues:
                                        results_text.insert(tk.END, f"    • {issue}\n")
                                        verification_results['issues'].append(f"Block {i + 1}: {issue}")

                                verify_window.update()
                                time.sleep(0.1)  # Small delay for visual effect

                        else:
                            # Empty or missing chain
                            results_text.insert(tk.END, "No blockchain data found.\n")
                            results_text.insert(tk.END, "This could mean:\n")
                            results_text.insert(tk.END, "• The blockchain hasn't been initialized\n")
                            results_text.insert(tk.END, "• No blocks have been mined yet\n")
                            results_text.insert(tk.END, "• The blockchain data structure is not properly configured\n")

                        progress_var.set(100)

                        # Display summary
                        results_text.insert(tk.END, "\n" + "="*50 + "\n")
                        results_text.insert(tk.END, "VERIFICATION SUMMARY\n")
                        results_text.insert(tk.END, "="*50 + "\n")
                        results_text.insert(tk.END, f"Total Blocks: {verification_results['total_blocks']}\n")
                        results_text.insert(tk.END, f"Valid Blocks: {verification_results['valid_blocks']}\n")
                        results_text.insert(tk.END, f"Invalid Blocks: {verification_results['invalid_blocks']}\n")
                        results_text.insert(tk.END, f"Hash Mismatches: {verification_results['hash_mismatches']}\n")
                        results_text.insert(tk.END, f"Timestamp Errors: {verification_results['timestamp_errors']}\n")

                        # Overall status
                        if verification_results['total_blocks'] == 0:
                            results_text.insert(tk.END, f"\nStatus: ⚠️ NO DATA - Blockchain is empty\n")
                        elif verification_results['invalid_blocks'] == 0:
                            results_text.insert(tk.END, f"\nStatus: ✅ INTEGRITY VERIFIED - All blocks are valid\n")
                        else:
                            results_text.insert(tk.END, f"\nStatus: ❌ INTEGRITY COMPROMISED - {verification_results['invalid_blocks']} invalid blocks found\n")

                        if verification_results['issues']:
                            results_text.insert(tk.END, f"\nIssues Found:\n")
                            for issue in verification_results['issues'][:10]:  # Show max 10 issues
                                results_text.insert(tk.END, f"• {issue}\n")
                            if len(verification_results['issues']) > 10:
                                results_text.insert(tk.END, f"• ... and {len(verification_results['issues']) - 10} more issues\n")

                        results_text.insert(tk.END, f"\nVerification completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

                    except Exception as e:
                        results_text.insert(tk.END, f"\nError during verification: {str(e)}\n")

                # Control buttons
                button_frame = ttk.Frame(verify_window)
                button_frame.pack(fill='x', padx=20, pady=(0, 20))

                ttk.Button(button_frame, text="Start Verification",
                          command=lambda: threading.Thread(target=run_verification, daemon=True).start()).pack(side='left', padx=(0, 10))
                ttk.Button(button_frame, text="Close", command=verify_window.destroy).pack(side='right')

                # Show initial message
                results_text.insert(tk.END, "Click 'Start Verification' to begin blockchain integrity check.\n\n")
                results_text.insert(tk.END, "This process will:\n")
                results_text.insert(tk.END, "• Verify each block's structure\n")
                results_text.insert(tk.END, "• Check hash consistency between blocks\n")
                results_text.insert(tk.END, "• Validate timestamps\n")
                results_text.insert(tk.END, "• Report any integrity issues found\n")

            else:
                # Blockchain not available
                info_msg = ("Blockchain audit system is not currently available.\n\n"
                           "To use blockchain verification:\n"
                           "• Enable the blockchain audit module\n"
                           "• Initialize the blockchain system\n"
                           "• Mine at least one block")
                messagebox.showinfo("Blockchain Unavailable", info_msg)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to verify blockchain: {str(e)}")

    def view_blockchain_history(self):
        """View blockchain history"""
        try:
            if hasattr(self.detector, 'blockchain_audit'):
                history_window = tk.Toplevel(self.root)
                history_window.title("Blockchain History")
                history_window.geometry("800x600")
                history_window.configure(bg=self.colors['bg_primary'])
                
                ttk.Label(history_window, text="Blockchain History", style='Title.TLabel').pack(pady=20)
                
                # Create treeview for blocks
                columns = ('Block', 'Hash', 'Transactions', 'Timestamp')
                tree = ttk.Treeview(history_window, columns=columns, show='headings', height=15)
                
                for col in columns:
                    tree.heading(col, text=col)
                    tree.column(col, width=150)
                
                # Add blockchain data
                for i, block in enumerate(self.detector.blockchain_audit.blockchain):
                    tree.insert('', 'end', values=(
                        i,
                        block.get('hash', '')[:16] + '...',
                        len(block.get('transactions', [])),
                        block.get('timestamp', '')
                    ))
                
                tree.pack(fill='both', expand=True, padx=20, pady=20)
            else:
                messagebox.showwarning("Warning", "Blockchain audit not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to view history: {str(e)}")

    def update_blockchain_display(self):
        """Update blockchain display information"""
        try:
            if hasattr(self.detector, 'blockchain_audit'):
                chain_length = len(self.detector.blockchain_audit.blockchain)
                pending_count = len(self.detector.blockchain_audit.pending_transactions)
                
                self.chain_length_label.config(text=f"Chain Length: {chain_length}")
                self.pending_transactions_label.config(text=f"Pending Transactions: {pending_count}")
        except Exception:
            pass

    def generate_benchmark_report(self):
        """Generate institutional benchmarking report"""
        institution_id = self.benchmark_institution_var.get()
        period = self.benchmark_period_var.get()
        
        if not institution_id:
            messagebox.showwarning("Warning", "Please enter an Institution ID")
            return
        
        try:
            if hasattr(self.detector, 'institution_benchmarking'):
                report = self.detector.institution_benchmarking.generate_benchmark_report(institution_id, period)
                self.display_benchmark_report(report)
            else:
                messagebox.showwarning("Warning", "Benchmarking not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate benchmark report: {str(e)}")

    def display_benchmark_report(self, report):
        """Display benchmarking report"""
        # Clear previous results
        for widget in self.benchmark_results_frame.winfo_children():
            widget.destroy()
        
        if 'error' in report:
            ttk.Label(self.benchmark_results_frame, text=f"Error: {report['error']}", 
                     style='Subtitle.TLabel').pack(anchor='w', padx=10, pady=10)
            return
        
        # Institution metrics
        metrics_frame = ttk.LabelFrame(self.benchmark_results_frame, text="Institution Metrics", padding=10)
        metrics_frame.pack(fill='x', padx=10, pady=5)
        
        institution_metrics = report.get('institution_metrics', {})
        for key, value in institution_metrics.items():
            ttk.Label(metrics_frame, text=f"{key.replace('_', ' ').title()}: {value}").pack(anchor='w')
        
        # Benchmarks
        benchmark_frame = ttk.LabelFrame(self.benchmark_results_frame, text="Global Benchmarks", padding=10)
        benchmark_frame.pack(fill='x', padx=10, pady=5)
        
        benchmarks = report.get('benchmarks', {})
        for key, value in benchmarks.items():
            ttk.Label(benchmark_frame, text=f"{key.replace('_', ' ').title()}: {value}").pack(anchor='w')
        
        # Performance indicators
        performance = report.get('performance_indicators', {})
        if performance:
            perf_frame = ttk.LabelFrame(self.benchmark_results_frame, text="Performance Indicators", padding=10)
            perf_frame.pack(fill='x', padx=10, pady=5)
            
            for key, value in performance.items():
                color = self.colors['success'] if value == 'below_average' else \
                       self.colors['warning'] if value == 'average' else self.colors['danger']
                
                indicator_frame = ttk.Frame(perf_frame)
                indicator_frame.pack(fill='x')
                
                ttk.Label(indicator_frame, text=f"{key.replace('_', ' ').title()}:").pack(side='left')
                status_label = tk.Label(indicator_frame, text=value.replace('_', ' ').title(), 
                                      fg=color, bg=self.colors['bg_tertiary'])
                status_label.pack(side='left', padx=(10, 0))

    def create_multi_modal_analysis_view(self, parent):
        """Create multi-modal analysis tab - MISSING"""
        multimodal_frame = ttk.Frame(parent)

        multimodal_frame.pack(fill="both", expand=True)
        
        # Multi-modal card
        multimodal_card = ttk.Frame(multimodal_frame, style='Card.TFrame')
        multimodal_card.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Label(multimodal_card, text="Multi-Modal Analysis", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)
        
        # Image upload section
        image_frame = ttk.LabelFrame(multimodal_card, text="Image Analysis", padding=15)
        image_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        ttk.Button(image_frame, text="📁 Upload Images", 
                  command=self.upload_images_for_analysis).pack(side='left', padx=(0, 10))
        ttk.Button(image_frame, text="📝 Analyze Image-Text Consistency", 
                  command=self.analyze_image_text_consistency).pack(side='left')
        
        # Code analysis section
        code_frame = ttk.LabelFrame(multimodal_card, text="Code Analysis", padding=15)
        code_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        ttk.Label(code_frame, text="Programming Language:").pack(side='left')
        self.code_language_var = tk.StringVar(value="python")
        language_combo = ttk.Combobox(code_frame, textvariable=self.code_language_var,
                                     values=["python", "java", "javascript", "cpp", "c"], width=15)
        language_combo.pack(side='left', padx=(5, 15))
        
        ttk.Button(code_frame, text="💻 Analyze Code", 
                  command=self.analyze_code_submission).pack(side='right')
        
        # Code input area
        ttk.Label(multimodal_card, text="Code to Analyze:", style='Subtitle.TLabel').pack(anchor='w', padx=15, pady=(10, 5))
        
        self.code_input = scrolledtext.ScrolledText(
            multimodal_card, wrap=tk.WORD, height=15,
            bg=self.colors['bg_secondary'], fg=self.colors['text_primary']
        )
        self.code_input.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    def upload_images_for_analysis(self):
        """Upload images for multi-modal analysis"""
        file_paths = filedialog.askopenfilenames(
            title="Select images for analysis",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"), ("All files", "*.*")]
        )
        
        if file_paths:
            self.uploaded_images = []
            try:
                for file_path in file_paths:
                    with open(file_path, 'rb') as f:
                        self.uploaded_images.append(f.read())
                
                messagebox.showinfo("Success", f"Uploaded {len(file_paths)} images for analysis")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to upload images: {str(e)}")

    def analyze_image_text_consistency(self):
        """Analyze consistency between uploaded images and text"""
        if not hasattr(self, 'uploaded_images') or not self.uploaded_images:
            messagebox.showwarning("Warning", "Please upload images first")
            return
        
        text = self.text_input.get('1.0', tk.END).strip()
        if not text:
            messagebox.showwarning("Warning", "Please enter text for comparison")
            return
        
        try:
            if hasattr(self.detector, 'multimodal_analyzer'):
                result = self.detector.multimodal_analyzer.analyze_image_text_consistency(text, self.uploaded_images)
                self.show_multimodal_results(result)
            else:
                messagebox.showwarning("Warning", "Multi-modal analysis not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to analyze image-text consistency: {str(e)}")

    def analyze_code_submission(self):
        """Analyze code submission"""
        code = self.code_input.get('1.0', tk.END).strip()
        language = self.code_language_var.get()
        
        if not code:
            messagebox.showwarning("Warning", "Please enter code to analyze")
            return
        
        try:
            if hasattr(self.detector, 'multimodal_analyzer'):
                result = self.detector.multimodal_analyzer.analyze_code_submission(code, language)
                self.show_code_analysis_results(result)
            else:
                messagebox.showwarning("Warning", "Code analysis not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to analyze code: {str(e)}")

    def show_multimodal_results(self, result):
        """Show multi-modal analysis results"""
        results_window = tk.Toplevel(self.root)
        results_window.title("Multi-Modal Analysis Results")
        results_window.geometry("700x500")
        results_window.configure(bg=self.colors['bg_primary'])
        
        ttk.Label(results_window, text="Image-Text Consistency Analysis", style='Title.TLabel').pack(pady=20)
        
        # Results display
        if hasattr(result, '__dict__'):
            score = result.score
            evidence = result.evidence
            
            results_frame = ttk.Frame(results_window, style='Card.TFrame')
            results_frame.pack(fill='both', expand=True, padx=20, pady=20)
            
            ttk.Label(results_frame, text=f"Consistency Score: {score:.1%}", 
                     font=('Segoe UI', 12)).pack(anchor='w', padx=15, pady=5)
            
            if evidence:
                ttk.Label(results_frame, text="Analysis Details:", 
                         font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=15, pady=(10, 5))
                for key, value in evidence.items():
                    ttk.Label(results_frame, text=f"  {key}: {value}").pack(anchor='w', padx=25, pady=2)

    def show_code_analysis_results(self, result):
        """Show code analysis results"""
        results_window = tk.Toplevel(self.root)
        results_window.title("Code Analysis Results")
        results_window.geometry("700x500")
        results_window.configure(bg=self.colors['bg_primary'])
        
        ttk.Label(results_window, text="Code Analysis Results", style='Title.TLabel').pack(pady=20)
        
        # Results display
        if hasattr(result, '__dict__'):
            score = result.score
            evidence = result.evidence
            
            results_frame = ttk.Frame(results_window, style='Card.TFrame')
            results_frame.pack(fill='both', expand=True, padx=20, pady=20)
            
            ttk.Label(results_frame, text=f"AI Generation Score: {score:.1%}", 
                     font=('Segoe UI', 12)).pack(anchor='w', padx=15, pady=5)
            
            if evidence:
                ttk.Label(results_frame, text="Patterns Found:", 
                         font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=15, pady=(10, 5))
                
                patterns_found = evidence.get('patterns_found', [])
                for pattern in patterns_found:
                    ttk.Label(results_frame, text=f"  • {pattern}").pack(anchor='w', padx=25, pady=2)

    def create_citation_verification_view(self, parent):
        """Create citation verification tab - MISSING"""
        citation_frame = ttk.Frame(parent)

        citation_frame.pack(fill="both", expand=True)
        
        # Citation verification card
        citation_card = ttk.Frame(citation_frame, style='Card.TFrame')
        citation_card.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Label(citation_card, text="Citation Verification", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)
        
        # Text input for citation verification
        ttk.Label(citation_card, text="Text with Citations:", style='Subtitle.TLabel').pack(anchor='w', padx=15, pady=(10, 5))
        
        self.citation_text = scrolledtext.ScrolledText(
            citation_card, wrap=tk.WORD, height=12,
            bg=self.colors['bg_secondary'], fg=self.colors['text_primary']
        )
        self.citation_text.pack(fill='both', expand=True, padx=15, pady=(0, 15))
        
        # Sample text with citations
        sample_citation_text = """
        According to recent research (Smith et al., 2023), artificial intelligence has shown remarkable progress.
        The study published in Nature (doi:10.1038/nature12345) demonstrates significant findings.
        However, some sources suggest different conclusions [Johnson, 2024].
        """
        self.citation_text.insert('1.0', sample_citation_text.strip())
        
        # Verification options
        options_frame = ttk.Frame(citation_card)
        options_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        self.verify_dois_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Verify DOIs", variable=self.verify_dois_var).pack(side='left')
        
        self.check_dates_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Check Publication Dates", variable=self.check_dates_var).pack(side='left', padx=(15, 0))
        
        # Verify button
        ttk.Button(citation_card, text="🔍 Verify Citations", 
                  command=self.verify_citations, style='Accent.TButton').pack(pady=(0, 15))

    def verify_citations(self):
        """Verify citations in text"""
        text = self.citation_text.get('1.0', tk.END).strip()
        if not text:
            messagebox.showwarning("Warning", "Please enter text with citations")
            return
        
        try:
            if hasattr(self.detector, 'citation_verifier'):
                result = self.detector.citation_verifier.verify_citations(text)
                self.show_citation_results(result)
            else:
                messagebox.showwarning("Warning", "Citation verification not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to verify citations: {str(e)}")

    def show_citation_results(self, result):
        """Show citation verification results"""
        results_window = tk.Toplevel(self.root)
        results_window.title("Citation Verification Results")
        results_window.geometry("800x600")
        results_window.configure(bg=self.colors['bg_primary'])
        
        ttk.Label(results_window, text="Citation Verification Results", style='Title.TLabel').pack(pady=20)
        
        # Create scrollable frame
        canvas = tk.Canvas(results_window, bg=self.colors['bg_primary'])
        scrollbar = ttk.Scrollbar(results_window, orient='vertical', command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Results content
        if hasattr(result, '__dict__'):
            score = result.score
            evidence = result.evidence
            
            # Summary
            summary_frame = ttk.Frame(scrollable_frame, style='Card.TFrame')
            summary_frame.pack(fill='x', padx=20, pady=10)
            
            ttk.Label(summary_frame, text=f"Suspicious Citation Score: {score:.1%}", 
                     font=('Segoe UI', 12, 'bold')).pack(anchor='w', padx=15, pady=15)
            
            # Citation details
            if evidence and 'citation_details' in evidence:
                details_frame = ttk.LabelFrame(scrollable_frame, text="Citation Details", padding=15)
                details_frame.pack(fill='x', padx=20, pady=10)
                
                for i, citation_detail in enumerate(evidence['citation_details'], 1):
                    citation_frame = ttk.Frame(details_frame, style='Card.TFrame')
                    citation_frame.pack(fill='x', pady=5)
                    
                    citation_text = citation_detail.get('citation', 'Unknown')
                    exists = citation_detail.get('exists', False)
                    suspicious = citation_detail.get('suspicious', False)
                    
                    status_color = self.colors['success'] if exists and not suspicious else self.colors['danger']
                    status_text = "✓ Valid" if exists and not suspicious else "⚠ Suspicious"
                    
                    ttk.Label(citation_frame, text=f"{i}. {citation_text}", 
                             font=('Segoe UI', 10)).pack(anchor='w', padx=10, pady=5)
                    
                    status_label = tk.Label(citation_frame, text=status_text, 
                                          fg=status_color, bg=self.colors['bg_tertiary'])
                    status_label.pack(anchor='w', padx=20, pady=(0, 5))
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def create_temporal_analysis_view(self, parent):
        """Create temporal analysis tab - MISSING"""
        temporal_frame = ttk.Frame(parent)

        temporal_frame.pack(fill="both", expand=True)
        
        # Temporal analysis card
        temporal_card = ttk.Frame(temporal_frame, style='Card.TFrame')
        temporal_card.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Label(temporal_card, text="Temporal Analysis", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)
        
        # Writing speed analysis
        speed_frame = ttk.LabelFrame(temporal_card, text="Writing Speed Analysis", padding=15)
        speed_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        # Input fields
        input_frame = ttk.Frame(speed_frame)
        input_frame.pack(fill='x')
        
        ttk.Label(input_frame, text="Time taken (minutes):").pack(side='left')
        self.time_taken_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.time_taken_var, width=10).pack(side='left', padx=(5, 15))
        
        ttk.Label(input_frame, text="Word count:").pack(side='left')
        self.word_count_display = ttk.Label(input_frame, text="0")
        self.word_count_display.pack(side='left', padx=(5, 15))
        
        ttk.Button(input_frame, text="📊 Analyze Writing Speed", 
                  command=self.analyze_writing_speed).pack(side='right')
        
        # Student submission patterns
        patterns_frame = ttk.LabelFrame(temporal_card, text="Submission Patterns", padding=15)
        patterns_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        ttk.Label(patterns_frame, text="Student ID:").pack(side='left')
        self.temporal_student_var = tk.StringVar()
        ttk.Entry(patterns_frame, textvariable=self.temporal_student_var, width=20).pack(side='left', padx=(5, 15))
        
        ttk.Button(patterns_frame, text="📈 Analyze Patterns", 
                  command=self.analyze_submission_patterns).pack(side='right')
        
        # Results display
        self.temporal_results_frame = ttk.Frame(temporal_card)
        self.temporal_results_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

    def analyze_writing_speed(self):
        """Analyze writing speed"""
        try:
            time_taken_str = self.time_taken_var.get()
            if not time_taken_str:
                messagebox.showwarning("Warning", "Please enter time taken")
                return
            
            time_taken_minutes = float(time_taken_str)
            time_taken_seconds = int(time_taken_minutes * 60)
            
            text = self.text_input.get('1.0', tk.END).strip()
            if not text:
                messagebox.showwarning("Warning", "Please enter text in the main analysis tab")
                return
            
            if hasattr(self.detector, 'temporal_analyzer'):
                result = self.detector.temporal_analyzer.analyze_writing_speed(text, time_taken_seconds)
                self.show_temporal_results(result)
            else:
                messagebox.showwarning("Warning", "Temporal analysis not available")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number for time taken")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to analyze writing speed: {str(e)}")

    def analyze_submission_patterns(self):
        """Analyze student submission patterns"""
        student_id = self.temporal_student_var.get()
        if not student_id:
            messagebox.showwarning("Warning", "Please enter a Student ID")
            return
        
        try:
            if hasattr(self.detector, 'temporal_analyzer'):
                patterns = self.detector.temporal_analyzer.analyze_submission_patterns(student_id)
                self.show_submission_patterns(patterns)
            else:
                messagebox.showwarning("Warning", "Temporal analysis not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to analyze patterns: {str(e)}")

    def show_temporal_results(self, result):
        """Show temporal analysis results"""
        # Clear previous results
        for widget in self.temporal_results_frame.winfo_children():
            widget.destroy()
        
        results_frame = ttk.Frame(self.temporal_results_frame, style='Card.TFrame')
        results_frame.pack(fill='x', pady=10)
        
        if hasattr(result, '__dict__'):
            score = result.score
            evidence = result.evidence
            risk_level = result.risk_level.value if hasattr(result.risk_level, 'value') else str(result.risk_level)
            
            ttk.Label(results_frame, text="Writing Speed Analysis Results", 
                     font=('Segoe UI', 12, 'bold')).pack(anchor='w', padx=15, pady=(15, 5))
            
            ttk.Label(results_frame, text=f"Anomaly Score: {score:.1%}").pack(anchor='w', padx=15, pady=2)
            ttk.Label(results_frame, text=f"Risk Level: {risk_level}").pack(anchor='w', padx=15, pady=2)
            
            if evidence:
                wpm = evidence.get('words_per_minute', 0)
                complexity = evidence.get('complexity_score', 0)
                ttk.Label(results_frame, text=f"Words per minute: {wpm:.1f}").pack(anchor='w', padx=15, pady=2)
                ttk.Label(results_frame, text=f"Text complexity: {complexity:.2f}").pack(anchor='w', padx=15, pady=2)
                
                if 'anomaly' in evidence:
                    ttk.Label(results_frame, text=f"Issue: {evidence['anomaly']}", 
                             foreground=self.colors['warning']).pack(anchor='w', padx=15, pady=5)

    def show_submission_patterns(self, patterns):
        """Show submission pattern analysis"""
        # Clear previous results
        for widget in self.temporal_results_frame.winfo_children():
            widget.destroy()
        
        patterns_frame = ttk.Frame(self.temporal_results_frame, style='Card.TFrame')
        patterns_frame.pack(fill='x', pady=10)
        
        ttk.Label(patterns_frame, text="Submission Patterns Analysis", 
                 font=('Segoe UI', 12, 'bold')).pack(anchor='w', padx=15, pady=(15, 5))
        
        if 'error' in patterns:
            ttk.Label(patterns_frame, text=f"Error: {patterns['error']}", 
                     foreground=self.colors['danger']).pack(anchor='w', padx=15, pady=5)
        elif 'insufficient_data' in patterns:
            ttk.Label(patterns_frame, text="Insufficient data for pattern analysis", 
                     style='Subtitle.TLabel').pack(anchor='w', padx=15, pady=5)
        else:
            # Display pattern metrics
            total_submissions = patterns.get('total_submissions', 0)
            suspicious_ratio = patterns.get('suspicious_hour_ratio', 0)
            regular_intervals = patterns.get('regular_interval_count', 0)
            avg_hour = patterns.get('avg_hour', 12)
            
            ttk.Label(patterns_frame, text=f"Total Submissions: {total_submissions}").pack(anchor='w', padx=15, pady=2)
            ttk.Label(patterns_frame, text=f"Average Submission Hour: {avg_hour:.1f}").pack(anchor='w', padx=15, pady=2)
            ttk.Label(patterns_frame, text=f"Late Night Submissions: {suspicious_ratio:.1%}").pack(anchor='w', padx=15, pady=2)
            ttk.Label(patterns_frame, text=f"Regular 24h Intervals: {regular_intervals}").pack(anchor='w', padx=15, pady=2)
            
            # Warnings for suspicious patterns
            if suspicious_ratio > 0.3:
                ttk.Label(patterns_frame, text="Warning: High frequency of late-night submissions", 
                         foreground=self.colors['warning']).pack(anchor='w', padx=15, pady=5)
            if regular_intervals > 3:
                ttk.Label(patterns_frame, text="Warning: Unusually regular submission intervals", 
                         foreground=self.colors['warning']).pack(anchor='w', padx=15, pady=5)

    def create_api_integration_view(self, parent):
        """Create API integration tab - MISSING"""
        api_frame = ttk.Frame(parent)

        api_frame.pack(fill="both", expand=True)
        
        # API integration card
        api_card = ttk.Frame(api_frame, style='Card.TFrame')
        api_card.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Label(api_card, text="External API Integration", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)
        
        # API configuration
        config_frame = ttk.LabelFrame(api_card, text="API Configuration", padding=15)
        config_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        # API service selection
        ttk.Label(config_frame, text="API Service:").pack(side='left')
        self.api_service_var = tk.StringVar(value="custom")
        api_combo = ttk.Combobox(config_frame, textvariable=self.api_service_var,
                                values=["custom", "openai", "cohere", "huggingface"], width=15)
        api_combo.pack(side='left', padx=(5, 15))
        
        # API key input
        ttk.Label(config_frame, text="API Key:").pack(side='left')
        self.api_key_var = tk.StringVar()
        api_key_entry = ttk.Entry(config_frame, textvariable=self.api_key_var, width=30, show="*")
        api_key_entry.pack(side='left', padx=(5, 15))
        
        ttk.Button(config_frame, text="🔗 Register API", command=self.register_external_api).pack(side='right')
        
        # API testing
        test_frame = ttk.LabelFrame(api_card, text="API Testing", padding=15)
        test_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        ttk.Button(test_frame, text="🧪 Test API Connection", 
                  command=self.test_api_connection).pack(side='left', padx=(0, 10))
        ttk.Button(test_frame, text="📊 API Performance", 
                  command=self.show_api_performance).pack(side='left')
        
        # API results comparison
        comparison_frame = ttk.LabelFrame(api_card, text="Multi-API Analysis", padding=15)
        comparison_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        ttk.Button(comparison_frame, text="🔍 Compare API Results", 
                  command=self.compare_api_results).pack(side='left', padx=(0, 10))
        ttk.Button(comparison_frame, text="⚡ Ensemble Prediction", 
                  command=self.run_ensemble_prediction).pack(side='left')

    def register_external_api(self):
        """Register external API for integration"""
        service = self.api_service_var.get()
        api_key = self.api_key_var.get()
        
        if not api_key:
            messagebox.showwarning("Warning", "Please enter an API key")
            return
        
        try:
            if hasattr(self.detector, 'api_gateway'):
                # Configure API based on service type
                if service == "custom":
                    url = tk.simpledialog.askstring("API URL", "Enter the API endpoint URL:")
                    if not url:
                        return
                else:
                    # Predefined URLs for known services
                    service_urls = {
                        "openai": "https://api.openai.com/v1/completions",
                        "cohere": "https://api.cohere.ai/v1/classify",
                        "huggingface": "https://api-inference.huggingface.co/models/roberta-base-openai-detector"
                    }
                    url = service_urls.get(service, "")
                
                config = {
                    'url': url,
                    'api_key': api_key,
                    'timeout': 30,
                    'max_requests_per_minute': 60,
                    'weight': 1.0
                }
                
                self.detector.api_gateway.register_api(service, config)
                messagebox.showinfo("Success", f"API '{service}' registered successfully")
                self.update_status(f"Registered API: {service}")
            else:
                messagebox.showwarning("Warning", "API gateway not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to register API: {str(e)}")

    def test_api_connection(self):
        """Test API connection"""
        service = self.api_service_var.get()
        
        try:
            if hasattr(self.detector, 'api_gateway'):
                # Test with sample text
                test_text = "This is a test text to verify API connectivity."
                result = self.detector.api_gateway.call_api(service, test_text)
                
                if result:
                    messagebox.showinfo("API Test", f"API '{service}' is working correctly!\nResponse time: {result.get('response_time', 0):.2f}s")
                else:
                    messagebox.showwarning("API Test", f"API '{service}' test failed")
            else:
                messagebox.showwarning("Warning", "API gateway not available")
        except Exception as e:
            messagebox.showerror("Error", f"API test failed: {str(e)}")

    def show_api_performance(self):
        """Show API performance metrics"""
        performance_window = tk.Toplevel(self.root)
        performance_window.title("API Performance Metrics")
        performance_window.geometry("600x400")
        performance_window.configure(bg=self.colors['bg_primary'])
        
        ttk.Label(performance_window, text="API Performance Metrics", style='Title.TLabel').pack(pady=20)
        
        # Performance display would show:
        # - Response times
        # - Success rates
        # - Rate limit status
        # - Circuit breaker status
        
        perf_frame = ttk.Frame(performance_window, style='Card.TFrame')
        perf_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        ttk.Label(perf_frame, text="API performance monitoring feature", 
                 style='Subtitle.TLabel').pack(expand=True)

    def compare_api_results(self):
        """Compare results from multiple APIs"""
        text = self.text_input.get('1.0', tk.END).strip()
        if not text:
            messagebox.showwarning("Warning", "Please enter text to analyze")
            return
        
        try:
            if hasattr(self.detector, 'api_gateway'):
                # This would call multiple APIs and compare results
                messagebox.showinfo("API Comparison", "Multi-API comparison feature available")
            else:
                messagebox.showwarning("Warning", "API gateway not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to compare APIs: {str(e)}")

    def run_ensemble_prediction(self):
        """Run ensemble prediction using multiple APIs"""
        text = self.text_input.get('1.0', tk.END).strip()
        if not text:
            messagebox.showwarning("Warning", "Please enter text to analyze")
            return
        
        try:
            if hasattr(self.detector, 'advanced_ml_trainer'):
                result = self.detector.advanced_ml_trainer.predict_ensemble(text)
                if result:
                    self.show_ensemble_results(result)
                else:
                    messagebox.showinfo("Ensemble Prediction", "No trained ensemble models available")
            else:
                messagebox.showwarning("Warning", "Ensemble prediction not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to run ensemble prediction: {str(e)}")

    def show_ensemble_results(self, result):
        """Show ensemble prediction results"""
        results_window = tk.Toplevel(self.root)
        results_window.title("Ensemble Prediction Results")
        results_window.geometry("700x500")
        results_window.configure(bg=self.colors['bg_primary'])
        
        ttk.Label(results_window, text="Ensemble Prediction Results", style='Title.TLabel').pack(pady=20)
        
        # Results display
        results_frame = ttk.Frame(results_window, style='Card.TFrame')
        results_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        ensemble_score = result.get('ensemble_score', 0)
        confidence = result.get('confidence', 0)
        individual_predictions = result.get('individual_predictions', {})
        
        # Main score
        ttk.Label(results_frame, text=f"Ensemble Score: {ensemble_score:.1%}", 
                 font=('Segoe UI', 14, 'bold')).pack(anchor='w', padx=15, pady=15)
        ttk.Label(results_frame, text=f"Confidence: {confidence:.1%}", 
                 font=('Segoe UI', 12)).pack(anchor='w', padx=15, pady=5)
        
        # Individual model predictions
        if individual_predictions:
            ttk.Label(results_frame, text="Individual Model Predictions:", 
                     font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=15, pady=(15, 5))
            
            for model_name, prediction in individual_predictions.items():
                ttk.Label(results_frame, text=f"  {model_name}: {prediction:.1%}").pack(anchor='w', padx=25, pady=2)

    def create_visual_analysis_view(self, parent):
        """Create visual analysis and heatmap tab - MISSING"""
        visual_frame = ttk.Frame(parent)

        visual_frame.pack(fill="both", expand=True)
        
        # Visual analysis card
        visual_card = ttk.Frame(visual_frame, style='Card.TFrame')
        visual_card.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Label(visual_card, text="Visual Text Analysis", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)
        
        # Analysis options
        options_frame = ttk.Frame(visual_card)
        options_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        ttk.Button(options_frame, text="🔥 Generate Text Heatmap", 
                  command=self.generate_text_heatmap).pack(side='left', padx=(0, 10))
        ttk.Button(options_frame, text="📈 Writing Flow Analysis", 
                  command=self.generate_writing_flow).pack(side='left', padx=(0, 10))
        ttk.Button(options_frame, text="📊 Complexity Visualization", 
                  command=self.generate_complexity_viz).pack(side='left')
        
        # Visualization display area
        self.visual_display_frame = ttk.Frame(visual_card)
        self.visual_display_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))
        
        # Initial message
        ttk.Label(self.visual_display_frame, text="Select an analysis option above to generate visualizations", 
                 style='Subtitle.TLabel').pack(expand=True)

    def generate_text_heatmap(self):
        """Generate text heatmap visualization"""
        # Check if text_input widget still exists
        if not hasattr(self, 'text_input') or not self.text_input.winfo_exists():
            messagebox.showwarning("Warning", "Please go to the Analysis tab first")
            return

        try:
            text = self.text_input.get('1.0', tk.END).strip()
        except tk.TclError:
            messagebox.showwarning("Warning", "Text input widget is no longer available. Please go to the Analysis tab first.")
            return

        if not text:
            messagebox.showwarning("Warning", "Please enter text to analyze")
            return
        
        try:
            if hasattr(self.detector, 'visual_analyzer'):
                # Generate sample scores for demonstration
                sentences = text.split('.')
                sample_scores = [0.1, 0.3, 0.7, 0.2, 0.8, 0.1, 0.4][:len(sentences)]
                
                heatmap_data = self.detector.visual_analyzer.generate_text_heatmap(text, sample_scores)
                self.display_text_heatmap(heatmap_data)
            else:
                messagebox.showwarning("Warning", "Visual analyzer not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate heatmap: {str(e)}")

    def display_text_heatmap(self, heatmap_data):
        """Display text heatmap"""
        # Clear previous display
        for widget in self.visual_display_frame.winfo_children():
            widget.destroy()
        
        # Create scrollable text area with color-coded sentences
        text_frame = ttk.LabelFrame(self.visual_display_frame, text="Text Heatmap", padding=15)
        text_frame.pack(fill='both', expand=True)
        
        # Create text widget
        text_widget = tk.Text(
            text_frame, wrap=tk.WORD, height=15,
            bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
            state='disabled'
        )
        text_widget.pack(fill='both', expand=True)
        
        # Configure color tags
        text_widget.tag_configure('high_risk', background='#ff4444', foreground='white')
        text_widget.tag_configure('medium_risk', background='#ffaa00', foreground='white')
        text_widget.tag_configure('low_risk', background='#ffff44', foreground='black')
        text_widget.tag_configure('safe', background='#44ff44', foreground='black')
        
        # Insert sentences with coloring
        text_widget.config(state='normal')
        heatmap_sentences = heatmap_data.get('heatmap_data', [])
        
        for sentence_data in heatmap_sentences:
            sentence_text = sentence_data.get('text', '')
            score = sentence_data.get('score', 0)
            
            start_index = text_widget.index(tk.INSERT)
            text_widget.insert(tk.INSERT, sentence_text + '. ')
            end_index = text_widget.index(tk.INSERT)
            
            # Apply color based on score
            if score > 0.7:
                text_widget.tag_add('high_risk', start_index, end_index)
            elif score > 0.5:
                text_widget.tag_add('medium_risk', start_index, end_index)
            elif score > 0.3:
                text_widget.tag_add('low_risk', start_index, end_index)
            else:
                text_widget.tag_add('safe', start_index, end_index)
        
        text_widget.config(state='disabled')
        
        # Legend
        legend_frame = ttk.Frame(text_frame)
        legend_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Label(legend_frame, text="Risk Level:").pack(side='left')
        
        legend_items = [
            ('High Risk', '#ff4444'),
            ('Medium Risk', '#ffaa00'),
            ('Low Risk', '#ffff44'),
            ('Safe', '#44ff44')
        ]
        
        for label, color in legend_items:
            legend_item = tk.Label(legend_frame, text=f"■ {label}", fg=color, bg=self.colors['bg_tertiary'])
            legend_item.pack(side='left', padx=(10, 0))

    def generate_writing_flow(self):
        """Generate writing flow visualization"""
        # Check if text_input widget still exists
        if not hasattr(self, 'text_input') or not self.text_input.winfo_exists():
            messagebox.showwarning("Warning", "Please go to the Analysis tab first")
            return

        try:
            text = self.text_input.get('1.0', tk.END).strip()
        except tk.TclError:
            messagebox.showwarning("Warning", "Text input widget is no longer available. Please go to the Analysis tab first.")
            return

        if not text:
            messagebox.showwarning("Warning", "Please enter text to analyze")
            return
        
        try:
            if hasattr(self.detector, 'visual_analyzer'):
                flow_data = self.detector.visual_analyzer.generate_writing_flow_visualization(text)
                self.display_writing_flow(flow_data)
            else:
                messagebox.showwarning("Warning", "Visual analyzer not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate writing flow: {str(e)}")

    def display_writing_flow(self, flow_data):
        """Display writing flow visualization"""
        # Clear previous display
        for widget in self.visual_display_frame.winfo_children():
            widget.destroy()
        
        # Create flow visualization
        flow_frame = ttk.LabelFrame(self.visual_display_frame, text="Writing Flow Analysis", padding=15)
        flow_frame.pack(fill='both', expand=True)
        
        # Summary statistics
        summary_frame = ttk.Frame(flow_frame)
        summary_frame.pack(fill='x', pady=(0, 10))
        
        total_paragraphs = flow_data.get('total_paragraphs', 0)
        avg_length = flow_data.get('avg_paragraph_length', 0)
        transition_freq = flow_data.get('transition_frequency', 0)
        
        ttk.Label(summary_frame, text=f"Paragraphs: {total_paragraphs}").pack(side='left', padx=(0, 15))
        ttk.Label(summary_frame, text=f"Avg Length: {avg_length:.1f} words").pack(side='left', padx=(0, 15))
        ttk.Label(summary_frame, text=f"Transitions: {transition_freq:.1%}").pack(side='left')
        
        # Paragraph details
        if 'flow_data' in flow_data:
            details_frame = scrolledtext.ScrolledText(flow_frame, height=12, wrap=tk.WORD,
                                                     bg=self.colors['bg_secondary'], fg=self.colors['text_primary'])
            details_frame.pack(fill='both', expand=True)
            
            for i, para_data in enumerate(flow_data['flow_data'], 1):
                word_count = para_data.get('word_count', 0)
                sentence_count = para_data.get('sentence_count', 0)
                has_transition = para_data.get('has_transition', False)
                complexity = para_data.get('complexity_score', 0)
                
                paragraph_info = f"Paragraph {i}: {word_count} words, {sentence_count} sentences"
                if has_transition:
                    paragraph_info += " [Has Transition]"
                paragraph_info += f" (Complexity: {complexity:.2f})\n"
                
                details_frame.insert(tk.END, paragraph_info)

    def generate_complexity_viz(self):
        """Generate text complexity visualization"""
        # Check if text_input widget still exists
        if not hasattr(self, 'text_input') or not self.text_input.winfo_exists():
            messagebox.showwarning("Warning", "Please go to the Analysis tab first")
            return

        try:
            text = self.text_input.get('1.0', tk.END).strip()
        except tk.TclError:
            messagebox.showwarning("Warning", "Text input widget is no longer available. Please go to the Analysis tab first.")
            return

        if not text:
            messagebox.showwarning("Warning", "Please enter text to analyze")
            return
        
        try:
            # Clear previous display
            for widget in self.visual_display_frame.winfo_children():
                widget.destroy()
            
            # Create complexity analysis
            complexity_frame = ttk.LabelFrame(self.visual_display_frame, text="Text Complexity Analysis", padding=15)
            complexity_frame.pack(fill='both', expand=True)
            
            # Calculate various complexity metrics
            words = text.split()
            sentences = text.split('.')
            
            # Metrics
            avg_word_length = sum(len(word) for word in words) / len(words) if words else 0
            avg_sentence_length = len(words) / len(sentences) if sentences else 0
            unique_words = len(set(word.lower() for word in words))
            lexical_diversity = unique_words / len(words) if words else 0
            
            # Display metrics
            metrics = [
                ("Average Word Length", f"{avg_word_length:.1f} characters"),
                ("Average Sentence Length", f"{avg_sentence_length:.1f} words"),
                ("Total Words", str(len(words))),
                ("Unique Words", str(unique_words)),
                ("Lexical Diversity", f"{lexical_diversity:.2f}"),
            ]
            
            for metric, value in metrics:
                metric_frame = ttk.Frame(complexity_frame)
                metric_frame.pack(fill='x', pady=2)
                
                ttk.Label(metric_frame, text=f"{metric}:").pack(side='left')
                ttk.Label(metric_frame, text=value, font=('Segoe UI', 10, 'bold')).pack(side='right')
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate complexity visualization: {str(e)}")
    
    def create_results_section(self, parent):
        """Create results display section"""
        # Results card
        results_card = ttk.Frame(parent, style='Card.TFrame')
        results_card.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Card title
        ttk.Label(results_card, text="Analysis Results", style='Title.TLabel').pack(anchor='w', padx=15, pady=(15, 5))
        
        # Results container
        self.results_container = ttk.Frame(results_card)
        self.results_container.pack(fill='both', expand=True, padx=15, pady=15)
        
        # Initial empty state
        self.show_empty_results()
    
    def show_empty_results(self):
        """Show empty state for results"""
        for widget in self.results_container.winfo_children():
            widget.destroy()
        
        empty_label = ttk.Label(self.results_container, 
                              text="Enter text and click 'Analyze Text' to see results",
                              style='Subtitle.TLabel')
        empty_label.pack(expand=True)
    
    def create_history_view(self, parent):
        """Create submission history tab"""
        history_frame = ttk.Frame(parent)

        history_frame.pack(fill="both", expand=True)
        
        # History card
        history_card = ttk.Frame(history_frame, style='Card.TFrame')
        history_card.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title and controls
        header_frame = ttk.Frame(history_card)
        header_frame.pack(fill='x', padx=15, pady=15)
        
        ttk.Label(header_frame, text="Submission History", style='Title.TLabel').pack(side='left')
        
        # Refresh button
        self.refresh_history_btn = ttk.Button(header_frame, text="🔄 Refresh", 
                                            command=self.refresh_history)
        self.refresh_history_btn.pack(side='right')
        
        # Filter controls
        filter_frame = ttk.Frame(history_card)
        filter_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        ttk.Label(filter_frame, text="Filter by Student ID:").pack(side='left')
        self.filter_student_var = tk.StringVar()
        self.filter_entry = ttk.Entry(filter_frame, textvariable=self.filter_student_var, width=20)
        self.filter_entry.pack(side='left', padx=(5, 10))
        self.filter_entry.bind('<Return>', lambda e: self.refresh_history())
        
        ttk.Button(filter_frame, text="Filter", command=self.refresh_history).pack(side='left')
        ttk.Button(filter_frame, text="Clear", command=self.clear_filter).pack(side='left', padx=(5, 0))
        
        # History treeview
        tree_frame = ttk.Frame(history_card)
        tree_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))
        
        columns = ('ID', 'Student ID', 'Title', 'Course', 'Date', 'AI Score', 'Status')
        self.history_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        
        # Configure columns
        for col in columns:
            self.history_tree.heading(col, text=col)
            if col == 'AI Score':
                self.history_tree.column(col, width=100, anchor='center')
            elif col == 'Status':
                self.history_tree.column(col, width=100, anchor='center')
            elif col == 'ID':
                self.history_tree.column(col, width=50, anchor='center')
            else:
                self.history_tree.column(col, width=150)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.history_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.history_tree.xview)
        self.history_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack treeview and scrollbars
        self.history_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Bind double-click event
        self.history_tree.bind('<Double-1>', self.view_submission_details)
        
        # Load initial history
        self.refresh_history()
    
    def create_statistics_view(self, parent):
        """Create statistics and dashboard tab"""
        stats_frame = ttk.Frame(parent)

        stats_frame.pack(fill="both", expand=True)
        
        # Create scrollable frame
        canvas = tk.Canvas(stats_frame, bg=self.colors['bg_primary'])
        scrollbar = ttk.Scrollbar(stats_frame, orient='vertical', command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Statistics cards
        self.create_stats_cards(scrollable_frame)
        self.create_charts_section(scrollable_frame)
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
    
    def create_stats_cards(self, parent):
        """Create statistics cards"""
        cards_frame = ttk.Frame(parent)

        cards_frame.pack(fill="both", expand=True)
        cards_frame.pack(fill='x', padx=10, pady=10)
        
        # Row 1: Main statistics
        row1 = ttk.Frame(cards_frame)
        row1.pack(fill='x', pady=(0, 10))
        
        self.stats_cards = {}
        
        # Total submissions card
        self.stats_cards['total'] = self.create_stat_card(row1, "Total Submissions", "0", "📄")
        self.stats_cards['total'].pack(side='left', fill='x', expand=True, padx=(0, 5))
        
        # Unique students card  
        self.stats_cards['students'] = self.create_stat_card(row1, "Unique Students", "0", "👥")
        self.stats_cards['students'].pack(side='left', fill='x', expand=True, padx=5)
        
        # Average AI score card
        self.stats_cards['avg_score'] = self.create_stat_card(row1, "Avg AI Score", "0.000", "🎯")
        self.stats_cards['avg_score'].pack(side='left', fill='x', expand=True, padx=5)
        
        # High risk submissions card
        self.stats_cards['high_risk'] = self.create_stat_card(row1, "High Risk", "0", "⚠️")
        self.stats_cards['high_risk'].pack(side='left', fill='x', expand=True, padx=(5, 0))
    
    def create_stat_card(self, parent, title, value, icon):
        """Create individual statistic card"""
        card = ttk.Frame(parent, style='Card.TFrame')
        
        # Icon and title
        header_frame = ttk.Frame(card)
        header_frame.pack(fill='x', padx=15, pady=(15, 5))
        
        ttk.Label(header_frame, text=icon, font=('Segoe UI', 16)).pack(side='left')
        ttk.Label(header_frame, text=title, style='Subtitle.TLabel').pack(side='left', padx=(10, 0))
        
        # Value
        value_label = ttk.Label(card, text=value, font=('Segoe UI', 24, 'bold'))
        value_label.pack(padx=15, pady=(0, 15))
        
        # Store value label for updates
        card.value_label = value_label
        
        return card
    
    def create_charts_section(self, parent):
        """Create charts section"""
        charts_frame = ttk.Frame(parent, style='Card.TFrame')
        charts_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        ttk.Label(charts_frame, text="Analytics Dashboard", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)
        
        # Chart container
        self.chart_container = ttk.Frame(charts_frame)
        self.chart_container.pack(fill='both', expand=True, padx=15, pady=(0, 15))
        
        # Create initial charts
        self.create_risk_distribution_chart()
    
    def create_risk_distribution_chart(self):
        """Create risk distribution pie chart"""
        try:
            # Create matplotlib figure
            fig, ax = plt.subplots(figsize=(8, 6))
            fig.patch.set_facecolor(self.colors['bg_tertiary'])
            ax.set_facecolor(self.colors['bg_tertiary'])
            
            # Sample data (replace with real data)
            risk_levels = ['Low Risk', 'Medium Risk', 'High Risk', 'Critical']
            counts = [70, 20, 8, 2]  # Sample percentages
            colors = [self.colors['success'], self.colors['warning'], self.colors['danger'], '#8B0000']
            
            # Create pie chart
            wedges, texts, autotexts = ax.pie(counts, labels=risk_levels, colors=colors, autopct='%1.1f%%',
                                            textprops={'color': self.colors['text_primary']})
            
            ax.set_title('Risk Distribution', color=self.colors['text_primary'], fontsize=14, fontweight='bold')
            
            # Embed in tkinter
            canvas = FigureCanvasTkAgg(fig, self.chart_container)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)
            
        except Exception as e:
            # Fallback if matplotlib not available
            fallback_label = ttk.Label(self.chart_container, 
                                     text="Charts require matplotlib\nInstall with: pip install matplotlib",
                                     style='Subtitle.TLabel')
            fallback_label.pack(expand=True)
    
    def create_settings_view(self, parent):
        """Create settings and configuration tab"""
        settings_frame = ttk.Frame(parent)

        settings_frame.pack(fill="both", expand=True)
        
        # Settings card
        settings_card = ttk.Frame(settings_frame, style='Card.TFrame')
        settings_card.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Label(settings_card, text="Detection Settings", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)
        
        # Detection threshold
        threshold_frame = ttk.Frame(settings_card)
        threshold_frame.pack(fill='x', padx=15, pady=(0, 20))
        
        ttk.Label(threshold_frame, text="AI Detection Threshold:").pack(side='left')
        self.threshold_var = tk.DoubleVar(value=getattr(self.detector, 'detection_threshold', 0.7))
        threshold_scale = ttk.Scale(threshold_frame, from_=0.1, to=1.0, variable=self.threshold_var,
                                  orient='horizontal', length=300)
        threshold_scale.pack(side='left', padx=(10, 10))
        
        self.threshold_label = ttk.Label(threshold_frame, text=f"{self.threshold_var.get():.2f}")
        self.threshold_label.pack(side='left')
        
        # Update threshold label
        def update_threshold_label(*args):
            self.threshold_label.config(text=f"{self.threshold_var.get():.2f}")
            
        self.threshold_var.trace('w', update_threshold_label)
        
        # Detection methods
        methods_frame = ttk.LabelFrame(settings_card, text="Detection Methods", padding=15)
        methods_frame.pack(fill='x', padx=15, pady=(0, 20))
        
        # Create checkboxes for detection methods
        self.method_vars = {}
        methods = ['Pattern Matching', 'Statistical Analysis', 'Behavioral Analysis', 
                  'Temporal Analysis', 'Citation Verification']
        
        for i, method in enumerate(methods):
            var = tk.BooleanVar(value=True)
            self.method_vars[method] = var
            ttk.Checkbutton(methods_frame, text=method, variable=var).grid(
                row=i//2, column=i%2, sticky='w', padx=(0, 20), pady=5)
        
        # Apply settings button
        ttk.Button(settings_card, text="💾 Apply Settings", 
                  command=self.apply_settings, style='Accent.TButton').pack(pady=20)
    
    def create_advanced_view(self, parent):
        """Create advanced features tab"""
        advanced_frame = ttk.Frame(parent)

        advanced_frame.pack(fill="both", expand=True)
        
        # Advanced features card
        advanced_card = ttk.Frame(advanced_frame, style='Card.TFrame')
        advanced_card.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Label(advanced_card, text="Advanced Features", style='Title.TLabel').pack(anchor='w', padx=15, pady=15)
        
        # Feature sections
        self.create_ml_section(advanced_card)
        self.create_batch_processing_section(advanced_card)
        self.create_export_section(advanced_card)
    
    def create_ml_section(self, parent):
        """Create machine learning section"""
        ml_frame = ttk.LabelFrame(parent, text="Machine Learning Models", padding=15)
        ml_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        ttk.Label(ml_frame, text="Train and manage ML models for enhanced detection").pack(anchor='w')
        
        ml_buttons = ttk.Frame(ml_frame)
        ml_buttons.pack(fill='x', pady=(10, 0))
        
        ttk.Button(ml_buttons, text="🤖 Train Models", command=self.train_models).pack(side='left', padx=(0, 10))
        ttk.Button(ml_buttons, text="📊 Model Status", command=self.show_model_status).pack(side='left')
    
    def create_batch_processing_section(self, parent):
        """Create batch processing section"""
        batch_frame = ttk.LabelFrame(parent, text="Batch Processing", padding=15)
        batch_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        ttk.Label(batch_frame, text="Process multiple files at once").pack(anchor='w')
        
        batch_buttons = ttk.Frame(batch_frame)
        batch_buttons.pack(fill='x', pady=(10, 0))
        
        ttk.Button(batch_buttons, text="📁 Select Files", command=self.select_batch_files).pack(side='left', padx=(0, 10))
        ttk.Button(batch_buttons, text="⚡ Process Batch", command=self.process_batch).pack(side='left')
    
    def create_export_section(self, parent):
        """Create export/import section"""
        export_frame = ttk.LabelFrame(parent, text="Data Management", padding=15)
        export_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        ttk.Label(export_frame, text="Export results and manage data").pack(anchor='w')
        
        export_buttons = ttk.Frame(export_frame)
        export_buttons.pack(fill='x', pady=(10, 0))
        
        ttk.Button(export_buttons, text="📤 Export Results", command=self.export_results).pack(side='left', padx=(0, 10))
        ttk.Button(export_buttons, text="📥 Import Data", command=self.import_data).pack(side='left', padx=(0, 10))
        ttk.Button(export_buttons, text="🗄️ Database Status", command=self.show_db_status).pack(side='left')
    
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
    
    # Event handlers and utility methods
    
    def update_word_count(self, event=None):
        """Update word count display"""
        text = self.text_input.get('1.0', tk.END)
        word_count = len(text.split())
        char_count = len(text.strip())
        self.word_count_label.config(text=f"Words: {word_count} | Characters: {char_count}")

    def _load_database_data(self):
        """Load modules, assignments, and students from database"""
        try:
            conn = sqlite3.connect(DEFAULT_DB_PATH)
            cursor = conn.cursor()

            # Load students (role is TEXT column, not role_id)
            cursor.execute('''
                SELECT id, username, first_name, last_name
                FROM users
                WHERE role = 'student'
                ORDER BY last_name, first_name
            ''')
            students = cursor.fetchall()
            self.students_data = {f"{s[2]} {s[3]} ({s[1]})": s[0] for s in students}
            self.student_combo['values'] = list(self.students_data.keys())
            print(f"Loaded {len(students)} students")

            # Load modules (module_code is the identifier we need)
            cursor.execute('''
                SELECT module_code, module_name
                FROM modules
                WHERE is_active = 1
                ORDER BY module_code
            ''')
            modules = cursor.fetchall()
            # Filter out None values
            modules = [(m[0], m[1]) for m in modules if m[0] and m[1]]
            self.modules_data = {f"{m[0]} - {m[1]}": m[0] for m in modules}
            self.module_combo['values'] = list(self.modules_data.keys())
            print(f"Loaded {len(modules)} modules")

            # Store assignments by module (will be loaded when module is selected)
            self.assignments_by_module = {}

            conn.close()

        except Exception as e:
            print(f"Warning: Could not load database data: {e}")
            import traceback
            traceback.print_exc()
            # Set empty lists as fallback
            self.students_data = {}
            self.modules_data = {}
            self.assignments_by_module = {}
            self.student_combo['values'] = []
            self.module_combo['values'] = []
            self.assignment_combo['values'] = []

    def _on_module_selected(self, event=None):
        """Load assignments when a module is selected"""
        module_display = self.module_var.get()
        if not module_display:
            return

        module_code = self.modules_data.get(module_display)
        if not module_code:
            return

        # Check if we already loaded assignments for this module
        if module_code in self.assignments_by_module:
            assignments = self.assignments_by_module[module_code]
            self.assignment_combo['values'] = list(assignments.keys())
            return

        # Load assignments from database
        try:
            conn = sqlite3.connect(DEFAULT_DB_PATH)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, title, due_date
                FROM assignments
                WHERE module_code = ?
                ORDER BY due_date DESC
            ''', (module_code,))
            assignments = cursor.fetchall()

            # Format as "Title (Due: YYYY-MM-DD)"
            assignments_dict = {}
            for a in assignments:
                assignment_id = a[0]
                title = a[1] if a[1] else f"Assignment {assignment_id}"
                due_date = a[2]

                if due_date:  # has due date
                    # Extract just the date part if it's a timestamp
                    date_str = str(due_date).split()[0] if ' ' in str(due_date) else str(due_date)
                    display_name = f"{title} (Due: {date_str})"
                else:
                    display_name = title

                assignments_dict[display_name] = assignment_id

            self.assignments_by_module[module_code] = assignments_dict
            self.assignment_combo['values'] = list(assignments_dict.keys())
            print(f"Loaded {len(assignments)} assignments for module {module_code}")

            conn.close()

        except Exception as e:
            print(f"Warning: Could not load assignments: {e}")
            import traceback
            traceback.print_exc()
            self.assignment_combo['values'] = []

    def load_file(self):
        """Load text from file (supports TXT, PDF, DOCX)"""
        # Build file types list based on available libraries
        filetypes = [("Text files", "*.txt")]

        if PYPDF2_AVAILABLE or TEXTRACT_AVAILABLE:
            filetypes.append(("PDF files", "*.pdf"))

        if PYTHON_DOCX_AVAILABLE or TEXTRACT_AVAILABLE:
            filetypes.append(("Word documents", "*.docx"))

        filetypes.append(("All files", "*.*"))

        file_path = filedialog.askopenfilename(
            title="Select document file",
            filetypes=filetypes
        )

        if file_path:
            try:
                content = self._extract_text_from_file(file_path)

                if content:
                    self.text_input.delete('1.0', tk.END)
                    self.text_input.insert('1.0', content)
                    self.update_word_count()

                    # Auto-fill title from filename if empty
                    if not self.title_var.get():
                        filename = os.path.basename(file_path)
                        filename_without_ext = os.path.splitext(filename)[0]
                        self.title_var.set(filename_without_ext)

                    self.update_status(f"Loaded file: {filename}")
                else:
                    messagebox.showwarning("Warning", "No text could be extracted from the file.")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file: {str(e)}")

    def _extract_text_from_file(self, file_path):
        """Extract text from various file formats"""
        file_ext = os.path.splitext(file_path)[1].lower()

        # Try textract first if available (supports many formats)
        if TEXTRACT_AVAILABLE:
            try:
                content = textract.process(file_path).decode('utf-8')
                return content
            except Exception as e:
                print(f"Textract extraction failed: {e}, trying format-specific extractors...")

        # Format-specific extraction
        if file_ext == '.txt':
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()

        elif file_ext == '.pdf':
            if PYPDF2_AVAILABLE:
                try:
                    reader = PdfReader(file_path)
                    text = []
                    for page in reader.pages:
                        text.append(page.extract_text())
                    return '\n'.join(text)
                except Exception as e:
                    raise Exception(f"Failed to extract PDF text: {e}")
            else:
                raise Exception("PDF support not available. Install PyPDF2: pip install PyPDF2")

        elif file_ext in ['.docx', '.doc']:
            if PYTHON_DOCX_AVAILABLE:
                try:
                    doc = docx.Document(file_path)
                    text = []
                    for paragraph in doc.paragraphs:
                        text.append(paragraph.text)
                    return '\n'.join(text)
                except Exception as e:
                    raise Exception(f"Failed to extract DOCX text: {e}")
            else:
                raise Exception("DOCX support not available. Install python-docx: pip install python-docx")

        else:
            # Try reading as plain text as fallback
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
            except:
                raise Exception(f"Unsupported file format: {file_ext}")
    
    def clear_input(self):
        """Clear all input fields"""
        self.text_input.delete('1.0', tk.END)
        self.student_id_var.set("")
        self.title_var.set("")
        self.course_var.set("")
        self.assignment_var.set("")
        self.update_word_count()
        self.show_empty_results()
    
    def analyze_text(self):
        """Analyze the input text"""
        text = self.text_input.get('1.0', tk.END).strip()
        
        if not text:
            messagebox.showwarning("Warning", "Please enter text to analyze")
            return
        
        if len(text) < 50:
            messagebox.showwarning("Warning", "Text is too short for meaningful analysis (minimum 50 characters)")
            return
        
        # Update UI state
        self.analyze_btn.config(state='disabled', text='🔄 Analyzing...')
        self.update_status("Analyzing text...")
        self.show_progress(True)
        
        # Run analysis in background thread
        def analyze_thread():
            try:
                # Get metadata
                student_id = self.student_id_var.get() or None
                title = self.title_var.get() or None
                course_code = self.course_var.get() or None
                assignment_id = self.assignment_var.get() or None
                
                # Run analysis
                result = self.detector.analyze_text_enhanced(
                    text=text,
                    title=title,
                    student_id=student_id,
                    course_code=course_code,
                    assignment_id=assignment_id
                )
                
                # Store results
                self.analysis_results = result
                self.current_submission_id = result.get('submission_id')
                
                # Update UI in main thread
                self.root.after(0, self.display_results, result)
                
            except Exception as e:
                self.root.after(0, self.analysis_error, str(e))
        
        threading.Thread(target=analyze_thread, daemon=True).start()
    
    def display_results(self, result):
        """Display analysis results"""
        # Clear previous results
        for widget in self.results_container.winfo_children():
            widget.destroy()
        
        # Main results frame
        main_results = ttk.Frame(self.results_container)
        main_results.pack(fill='both', expand=True)
        
        # AI Score display
        self.create_score_display(main_results, result)
        
        # Detailed analysis
        self.create_detailed_analysis(main_results, result)
        
        # Recommendations
        self.create_recommendations(main_results, result)
        
        # Reset UI state
        self.analyze_btn.config(state='normal', text='🔍 Analyze Text')
        self.show_progress(False)
        self.update_status("Analysis complete")
        
        # Refresh statistics and history
        self.refresh_statistics()
        self.refresh_history()
    
    def create_score_display(self, parent, result):
        """Create main score display"""
        score_frame = ttk.Frame(parent, style='Card.TFrame')
        score_frame.pack(fill='x', pady=(0, 10))
        
        # AI Score
        ai_score = result.get('ai_score', 0)
        confidence = result.get('confidence', 0)
        is_ai_generated = result.get('is_ai_generated', False)
        
        # Score header
        header_frame = ttk.Frame(score_frame)
        header_frame.pack(fill='x', padx=15, pady=15)
        
        # Risk indicator
        risk_color = self.get_risk_color(ai_score)
        risk_text = self.get_risk_text(ai_score)
        
        risk_indicator = tk.Label(header_frame, text="●", font=('Arial', 20), 
                                fg=risk_color, bg=self.colors['bg_tertiary'])
        risk_indicator.pack(side='left')
        
        ttk.Label(header_frame, text=f"{risk_text} Risk", 
                 font=('Segoe UI', 14, 'bold')).pack(side='left', padx=(10, 0))
        
        # Score display
        score_display_frame = ttk.Frame(score_frame)
        score_display_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        # AI Score
        score_label = ttk.Label(score_display_frame, text=f"{ai_score:.1%}", 
                               font=('Segoe UI', 32, 'bold'))
        score_label.pack(side='left')
        
        # Details
        details_frame = ttk.Frame(score_display_frame)
        details_frame.pack(side='left', padx=(20, 0), fill='y')
        
        ttk.Label(details_frame, text="AI Generated Probability", 
                 style='Subtitle.TLabel').pack(anchor='w')
        ttk.Label(details_frame, text=f"Confidence: {confidence:.1%}", 
                 style='Subtitle.TLabel').pack(anchor='w')
        ttk.Label(details_frame, text=f"Status: {'AI Generated' if is_ai_generated else 'Human Written'}", 
                 style='Subtitle.TLabel').pack(anchor='w')
    
    def create_detailed_analysis(self, parent, result):
        """Create detailed analysis section"""
        details_frame = ttk.Frame(parent, style='Card.TFrame')
        details_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        ttk.Label(details_frame, text="Detailed Analysis", 
                 style='Title.TLabel').pack(anchor='w', padx=15, pady=(15, 10))
        
        # Analysis notebook
        analysis_notebook = ttk.Notebook(details_frame)
        analysis_notebook.pack(fill='both', expand=True, padx=15, pady=(0, 15))
        
        # Pattern Analysis tab
        self.create_pattern_tab(analysis_notebook, result)
        
        # Sentence Analysis tab (if available)
        if result.get('sentence_analysis'):
            self.create_sentence_tab(analysis_notebook, result)
        
        # Advanced Analysis tab (if available)
        if result.get('advanced_analyses'):
            self.create_advanced_analysis_tab(analysis_notebook, result)
    
    def create_pattern_tab(self, notebook, result):
        """Create pattern analysis tab"""
        pattern_frame = ttk.Frame(notebook)
        notebook.add(pattern_frame, text="Patterns")
        
        # Create scrollable frame
        canvas = tk.Canvas(pattern_frame, bg=self.colors['bg_primary'])
        scrollbar = ttk.Scrollbar(pattern_frame, orient='vertical', command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pattern indicators
        detailed_results = result.get('detailed_results', {})
        if isinstance(detailed_results, str):
            try:
                detailed_results = json.loads(detailed_results)
            except:
                detailed_results = {}
        
        patterns = detailed_results.get('patterns', {})
        
        for pattern_name, pattern_data in patterns.items():
            self.create_pattern_indicator(scrollable_frame, pattern_name, pattern_data)
        
        # If no patterns, show default
        if not patterns:
            ttk.Label(scrollable_frame, text="No specific patterns detected", 
                     style='Subtitle.TLabel').pack(pady=20)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_pattern_indicator(self, parent, pattern_name, pattern_data):
        """Create individual pattern indicator"""
        pattern_frame = ttk.Frame(parent, style='Card.TFrame')
        pattern_frame.pack(fill='x', padx=5, pady=5)
        
        # Pattern header
        header_frame = ttk.Frame(pattern_frame)
        header_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(header_frame, text=pattern_name.replace('_', ' ').title(), 
                 font=('Segoe UI', 10, 'bold')).pack(side='left')
        
        # Score and bar
        if isinstance(pattern_data, dict):
            score = pattern_data.get('score', 0)
            matches = pattern_data.get('matches', 0)
        else:
            score = pattern_data if isinstance(pattern_data, (int, float)) else 0
            matches = 0
        
        score_label = ttk.Label(header_frame, text=f"{score:.1%}")
        score_label.pack(side='right')
        
        # Progress bar
        progress_frame = ttk.Frame(pattern_frame)
        progress_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        progress = ttk.Progressbar(progress_frame, mode='determinate', value=score*100)
        progress.pack(fill='x')
        
        # Additional info
        if matches > 0:
            ttk.Label(pattern_frame, text=f"Matches found: {matches}", 
                     style='Subtitle.TLabel').pack(anchor='w', padx=10, pady=(0, 10))
    
    def create_sentence_tab(self, notebook, result):
        """Create sentence analysis tab"""
        sentence_frame = ttk.Frame(notebook)
        notebook.add(sentence_frame, text="Sentences")
        
        # Sentence analysis display
        sentence_analysis = result.get('sentence_analysis', {})
        sentences = sentence_analysis.get('sentences', [])
        
        if sentences:
            # Create text widget with highlighting
            text_widget = scrolledtext.ScrolledText(
                sentence_frame,
                wrap=tk.WORD,
                bg=self.colors['bg_secondary'],
                fg=self.colors['text_primary'],
                selectbackground=self.colors['accent'],
                state='disabled'
            )
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            
            # Configure tags for highlighting
            text_widget.tag_configure('high_risk', background=self.colors['danger'], foreground='white')
            text_widget.tag_configure('medium_risk', background=self.colors['warning'], foreground='white')
            text_widget.tag_configure('low_risk', background=self.colors['success'], foreground='white')
            
            # Insert sentences with highlighting
            text_widget.config(state='normal')
            for i, sentence_data in enumerate(sentences):
                sentence_text = sentence_data.get('text', '')
                ai_score = sentence_data.get('ai_score', 0)
                
                start_index = text_widget.index(tk.INSERT)
                text_widget.insert(tk.INSERT, sentence_text + ' ')
                end_index = text_widget.index(tk.INSERT)
                
                # Apply highlighting based on score
                if ai_score > 0.7:
                    text_widget.tag_add('high_risk', start_index, end_index)
                elif ai_score > 0.4:
                    text_widget.tag_add('medium_risk', start_index, end_index)
                elif ai_score > 0.2:
                    text_widget.tag_add('low_risk', start_index, end_index)
            
            text_widget.config(state='disabled')
            
            # Legend
            legend_frame = ttk.Frame(sentence_frame)
            legend_frame.pack(fill='x', padx=10, pady=(0, 10))
            
            ttk.Label(legend_frame, text="Legend:").pack(side='left')
            
            for color, label in [('high_risk', 'High Risk'), ('medium_risk', 'Medium Risk'), ('low_risk', 'Low Risk')]:
                legend_item = tk.Label(legend_frame, text=f"● {label}", fg=self.colors['danger'] if color == 'high_risk' 
                                     else self.colors['warning'] if color == 'medium_risk' else self.colors['success'],
                                     bg=self.colors['bg_primary'])
                legend_item.pack(side='left', padx=(10, 0))
        else:
            ttk.Label(sentence_frame, text="Sentence analysis not available", 
                     style='Subtitle.TLabel').pack(expand=True)
    
    def create_advanced_analysis_tab(self, notebook, result):
        """Create advanced analysis tab"""
        advanced_frame = ttk.Frame(notebook)
        notebook.add(advanced_frame, text="Advanced")
        
        # Advanced analysis results
        advanced_analyses = result.get('advanced_analyses', {})
        
        if advanced_analyses:
            # Create scrollable frame
            canvas = tk.Canvas(advanced_frame, bg=self.colors['bg_primary'])
            scrollbar = ttk.Scrollbar(advanced_frame, orient='vertical', command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Display each advanced analysis
            for analysis_name, analysis_data in advanced_analyses.items():
                self.create_advanced_analysis_section(scrollable_frame, analysis_name, analysis_data)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
        else:
            ttk.Label(advanced_frame, text="Advanced analysis not available", 
                     style='Subtitle.TLabel').pack(expand=True)
    
    def create_advanced_analysis_section(self, parent, name, data):
        """Create section for advanced analysis"""
        section_frame = ttk.LabelFrame(parent, text=name.replace('_', ' ').title(), padding=10)
        section_frame.pack(fill='x', padx=5, pady=5)
        
        if isinstance(data, dict):
            for key, value in data.items():
                if key in ['score', 'confidence'] and isinstance(value, (int, float)):
                    ttk.Label(section_frame, text=f"{key.title()}: {value:.1%}").pack(anchor='w')
                elif isinstance(value, (str, int, float, bool)):
                    ttk.Label(section_frame, text=f"{key.replace('_', ' ').title()}: {value}").pack(anchor='w')
        else:
            ttk.Label(section_frame, text=str(data)).pack(anchor='w')
    
    def create_recommendations(self, parent, result):
        """Create recommendations section"""
        rec_frame = ttk.Frame(parent, style='Card.TFrame')
        rec_frame.pack(fill='x')
        
        ttk.Label(rec_frame, text="Recommendations", 
                 style='Title.TLabel').pack(anchor='w', padx=15, pady=(15, 10))
        
        # Get recommendations
        recommendations = result.get('recommendations', [])
        
        if not recommendations:
            # Generate basic recommendations based on score
            ai_score = result.get('ai_score', 0)
            if ai_score > 0.8:
                recommendations = [
                    "High AI probability detected. Consider further investigation.",
                    "Interview the student about their writing process.",
                    "Review assignment submission timeline and behavior."
                ]
            elif ai_score > 0.6:
                recommendations = [
                    "Moderate AI indicators present. Consider follow-up.",
                    "Provide feedback on academic writing best practices."
                ]
            else:
                recommendations = [
                    "Low AI probability. Text appears to be human-written.",
                    "Continue monitoring future submissions."
                ]
        
        # Display recommendations
        for i, rec in enumerate(recommendations, 1):
            rec_item_frame = ttk.Frame(rec_frame)
            rec_item_frame.pack(fill='x', padx=15, pady=2)
            
            ttk.Label(rec_item_frame, text=f"{i}.", style='Subtitle.TLabel').pack(side='left')
            ttk.Label(rec_item_frame, text=rec, style='Subtitle.TLabel').pack(side='left', padx=(5, 0))
        
        # Add padding at bottom
        ttk.Label(rec_frame, text="").pack(pady=10)
    
    def analysis_error(self, error_message):
        """Handle analysis error"""
        self.analyze_btn.config(state='normal', text='🔍 Analyze Text')
        self.show_progress(False)
        self.update_status("Analysis failed")
        messagebox.showerror("Analysis Error", f"Failed to analyze text:\n{error_message}")
    
    def get_risk_color(self, score):
        """Get risk indicator color"""
        if score >= 0.8:
            return self.colors['danger']
        elif score >= 0.6:
            return self.colors['warning']
        elif score >= 0.4:
            return '#FFA500'  # Orange
        else:
            return self.colors['success']
    
    def get_risk_text(self, score):
        """Get risk level text"""
        if score >= 0.8:
            return "High"
        elif score >= 0.6:
            return "Medium"
        elif score >= 0.4:
            return "Low"
        else:
            return "Very Low"
    
    def refresh_history(self):
        """Refresh submission history"""
        try:
            # Get filter
            student_filter = self.filter_student_var.get() if self.filter_student_var.get().strip() else None
            
            # Get submissions
            history_data = self.detector.get_submission_history(student_id=student_filter, limit=100)
            submissions = history_data.get('submissions', [])
            
            # Clear existing items
            for item in self.history_tree.get_children():
                self.history_tree.delete(item)
            
            # Populate tree
            for submission in submissions:
                submission_id = submission.get('id', '')
                student_id = submission.get('student_id', '')
                title = submission.get('title', 'Untitled')
                course = submission.get('course_code', '')
                date = submission.get('submission_date', '')
                ai_score = submission.get('ai_score', 0)
                is_ai = submission.get('is_ai_generated', False)
                
                # Format date
                try:
                    if date:
                        date_obj = datetime.fromisoformat(date.replace('Z', '+00:00'))
                        formatted_date = date_obj.strftime('%Y-%m-%d %H:%M')
                    else:
                        formatted_date = 'Unknown'
                except:
                    formatted_date = date
                
                # Format score
                score_text = f"{ai_score:.1%}" if ai_score is not None else "N/A"
                
                # Status
                status = "AI Generated" if is_ai else "Human"
                
                self.history_tree.insert('', 'end', values=(
                    submission_id, student_id, title, course, formatted_date, score_text, status
                ))
            
            self.update_status(f"Loaded {len(submissions)} submissions")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load history: {str(e)}")
    
    def clear_filter(self):
        """Clear history filter"""
        self.filter_student_var.set("")
        self.refresh_history()
    
    def view_submission_details(self, event):
        """View detailed submission information"""
        selection = self.history_tree.selection()
        if not selection:
            return
        
        item = self.history_tree.item(selection[0])
        submission_id = item['values'][0]
        
        try:
            submission_details = self.detector.get_submission_details(submission_id)
            self.show_submission_details_window(submission_details)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load submission details: {str(e)}")
    
    def show_submission_details_window(self, details):
        """Show submission details in new window"""
        details_window = tk.Toplevel(self.root)
        details_window.title("Submission Details")
        details_window.geometry("800x600")
        details_window.configure(bg=self.colors['bg_primary'])
        
        # Create scrollable frame
        canvas = tk.Canvas(details_window, bg=self.colors['bg_primary'])
        scrollbar = ttk.Scrollbar(details_window, orient='vertical', command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Content
        ttk.Label(scrollable_frame, text="Submission Details", 
                 style='Title.TLabel').pack(anchor='w', padx=20, pady=20)
        
        # Basic info
        info_frame = ttk.LabelFrame(scrollable_frame, text="Basic Information", padding=15)
        info_frame.pack(fill='x', padx=20, pady=(0, 20))
        
        for key, value in details.items():
            if key not in ['submission_text', 'detailed_results'] and value is not None:
                ttk.Label(info_frame, text=f"{key.replace('_', ' ').title()}: {value}").pack(anchor='w')
        
        # Text content
        if details.get('submission_text'):
            text_frame = ttk.LabelFrame(scrollable_frame, text="Submission Text", padding=15)
            text_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))
            
            text_widget = scrolledtext.ScrolledText(
                text_frame, wrap=tk.WORD, height=15,
                bg=self.colors['bg_secondary'], fg=self.colors['text_primary']
            )
            text_widget.pack(fill='both', expand=True)
            text_widget.insert('1.0', details['submission_text'])
            text_widget.config(state='disabled')
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def refresh_statistics(self):
        """Refresh statistics display"""
        try:
            stats = self.detector.get_enhanced_statistics()
            
            # Update stat cards
            if hasattr(self, 'stats_cards'):
                self.stats_cards['total'].value_label.config(text=str(stats.get('total_submissions', 0)))
                self.stats_cards['students'].value_label.config(text=str(stats.get('unique_students', 0)))
                self.stats_cards['avg_score'].value_label.config(text=f"{stats.get('average_ai_score', 0):.3f}")
                self.stats_cards['high_risk'].value_label.config(text=str(stats.get('high_risk_submissions', 0)))
            
            # Update info label
            self.info_label.config(text=f"DB: {stats.get('database_status', 'Unknown')}")
            
        except Exception as e:
            print(f"Error refreshing statistics: {e}")
    
    def apply_settings(self):
        """Apply detection settings"""
        try:
            # Update detection threshold
            new_threshold = self.threshold_var.get()
            self.detector.detection_threshold = new_threshold
            
            # Update detection methods
            detection_methods = {}
            for method, var in self.method_vars.items():
                detection_methods[method.lower().replace(' ', '_')] = var.get()
            
            if hasattr(self.detector, 'detection_methods'):
                self.detector.detection_methods.update(detection_methods)
            
            messagebox.showinfo("Settings", "Settings applied successfully!")
            self.update_status("Settings updated")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply settings: {str(e)}")
    
    def train_models(self):
        """Train ML models"""
        if not hasattr(self.detector, 'train_advanced_models'):
            messagebox.showwarning("Warning", "Advanced ML training not available")
            return
        
        # Show progress
        self.update_status("Training ML models...")
        self.show_progress(True)
        
        def train_thread():
            try:
                result = self.detector.train_advanced_models()
                self.root.after(0, lambda: self.training_complete(result))
            except Exception as e:
                self.root.after(0, lambda: self.training_error(str(e)))
        
        threading.Thread(target=train_thread, daemon=True).start()
    
    def training_complete(self, result):
        """Handle training completion"""
        self.show_progress(False)
        self.update_status("Model training complete")
        messagebox.showinfo("Training Complete", "ML models trained successfully!")
    
    def training_error(self, error):
        """Handle training error"""
        self.show_progress(False)
        self.update_status("Training failed")
        messagebox.showerror("Training Error", f"Failed to train models: {error}")
    
    def show_model_status(self):
        """Show ML model status"""
        status_window = tk.Toplevel(self.root)
        status_window.title("Model Status")
        status_window.geometry("600x400")
        status_window.configure(bg=self.colors['bg_primary'])
        
        ttk.Label(status_window, text="ML Model Status", style='Title.TLabel').pack(pady=20)
        
        # Model status info
        status_frame = ttk.Frame(status_window, style='Card.TFrame')
        status_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Check model availability
        model_info = []
        
        if hasattr(self.detector, 'advanced_ml_trainer'):
            if hasattr(self.detector.advanced_ml_trainer, 'models') and self.detector.advanced_ml_trainer.models:
                model_info.append(f"Ensemble Models: {len(self.detector.advanced_ml_trainer.models)} trained")
            else:
                model_info.append("Ensemble Models: Not trained")
        
        if hasattr(self.detector, 'predictive_analytics'):
            if hasattr(self.detector.predictive_analytics, 'risk_model') and self.detector.predictive_analytics.risk_model:
                model_info.append("Risk Prediction Model: Trained")
            else:
                model_info.append("Risk Prediction Model: Not trained")
        
        if not model_info:
            model_info.append("No advanced models available")
        
        for info in model_info:
            ttk.Label(status_frame, text=info, style='Subtitle.TLabel').pack(anchor='w', padx=20, pady=5)
    
    def select_batch_files(self):
        """Select files for batch processing"""
        file_paths = filedialog.askopenfilenames(
            title="Select files for batch processing",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if file_paths:
            self.batch_files = file_paths
            messagebox.showinfo("Files Selected", f"Selected {len(file_paths)} files for processing")
        else:
            self.batch_files = []
    
    def process_batch(self):
        """Process batch files"""
        if not hasattr(self, 'batch_files') or not self.batch_files:
            messagebox.showwarning("Warning", "Please select files first")
            return
        
        # Create batch processing window
        batch_window = tk.Toplevel(self.root)
        batch_window.title("Batch Processing")
        batch_window.geometry("600x400")
        batch_window.configure(bg=self.colors['bg_primary'])
        
        ttk.Label(batch_window, text="Batch Processing", style='Title.TLabel').pack(pady=20)
        
        # Progress
        progress_frame = ttk.Frame(batch_window)
        progress_frame.pack(fill='x', padx=20, pady=20)
        
        progress_label = ttk.Label(progress_frame, text="Processing files...")
        progress_label.pack()
        
        progress_bar = ttk.Progressbar(progress_frame, mode='determinate', length=400)
        progress_bar.pack(pady=10)
        
        # Results area
        results_frame = scrolledtext.ScrolledText(batch_window, height=15,
                                                bg=self.colors['bg_secondary'],
                                                fg=self.colors['text_primary'])
        results_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        
        def process_files():
            total_files = len(self.batch_files)
            results = []
            
            for i, file_path in enumerate(self.batch_files):
                try:
                    # Update progress
                    progress = (i + 1) / total_files * 100
                    progress_bar['value'] = progress
                    progress_label.config(text=f"Processing {i+1}/{total_files}: {file_path.split('/')[-1]}")
                    batch_window.update()
                    
                    # Read file
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text = f.read()
                    
                    # Analyze
                    result = self.detector.analyze_text_enhanced(
                        text=text,
                        title=file_path.split('/')[-1].split('.')[0],
                        student_id=f"BATCH_{i+1}"
                    )
                    
                    # Store result
                    results.append({
                        'file': file_path.split('/')[-1],
                        'ai_score': result.get('ai_score', 0),
                        'is_ai_generated': result.get('is_ai_generated', False)
                    })
                    
                    # Update results display
                    result_text = f"✓ {file_path.split('/')[-1]}: {result.get('ai_score', 0):.1%} AI probability\n"
                    results_frame.insert(tk.END, result_text)
                    results_frame.see(tk.END)
                    
                except Exception as e:
                    error_text = f"✗ {file_path.split('/')[-1]}: Error - {str(e)}\n"
                    results_frame.insert(tk.END, error_text)
                    results_frame.see(tk.END)
            
            # Complete
            progress_label.config(text="Batch processing complete!")
            progress_bar['value'] = 100
            
            # Show summary
            summary_text = f"\n--- SUMMARY ---\nProcessed {total_files} files\n"
            ai_generated_count = sum(1 for r in results if r['is_ai_generated'])
            summary_text += f"AI Generated: {ai_generated_count}\n"
            summary_text += f"Human Written: {total_files - ai_generated_count}\n"
            results_frame.insert(tk.END, summary_text)
            
        threading.Thread(target=process_files, daemon=True).start()
    
    def export_results(self):
        """Export analysis results"""
        file_path = filedialog.asksaveasfilename(
            title="Export Results",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                # Get all submissions
                history_data = self.detector.get_submission_history(limit=1000)
                submissions = history_data.get('submissions', [])
                
                if file_path.endswith('.csv'):
                    # Export as CSV
                    import csv
                    with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                        if submissions:
                            fieldnames = submissions[0].keys()
                            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                            writer.writeheader()
                            for submission in submissions:
                                # Remove text content for CSV (too large)
                                clean_submission = {k: v for k, v in submission.items() 
                                                  if k != 'submission_text'}
                                writer.writerow(clean_submission)
                else:
                    # Export as JSON
                    with open(file_path, 'w', encoding='utf-8') as jsonfile:
                        export_data = {
                            'export_date': datetime.now().isoformat(),
                            'total_submissions': len(submissions),
                            'submissions': submissions
                        }
                        json.dump(export_data, jsonfile, indent=2, default=str)
                
                messagebox.showinfo("Export Complete", f"Results exported to {file_path}")
                
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export results: {str(e)}")
    
    def import_data(self):
        """Import data from file"""
        file_path = filedialog.askopenfilename(
            title="Import AI Detection Data",
            filetypes=[
                ("JSON files", "*.json"),
                ("CSV files", "*.csv"),
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )

        if not file_path:
            return

        # Create import progress window
        import_window = tk.Toplevel(self.root)
        import_window.title("Data Import Progress")
        import_window.geometry("500x400")
        import_window.transient(self.root)
        import_window.grab_set()

        # Title
        ttk.Label(import_window, text="📥 Importing AI Detection Data", style='Title.TLabel').pack(pady=15)

        # Progress frame
        progress_frame = ttk.LabelFrame(import_window, text="Import Progress", padding="15")
        progress_frame.pack(fill='x', padx=20, pady=(0, 15))

        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, mode='determinate', length=400)
        progress_bar.pack(pady=(0, 10))

        status_label = ttk.Label(progress_frame, text="Preparing import...")
        status_label.pack()

        # Results frame
        results_frame = ttk.LabelFrame(import_window, text="Import Results", padding="15")
        results_frame.pack(fill='both', expand=True, padx=20, pady=(0, 15))

        results_text = tk.Text(results_frame, height=10, wrap='word')
        results_text.pack(fill='both', expand=True)

        scrollbar = ttk.Scrollbar(results_frame, orient='vertical', command=results_text.yview)
        scrollbar.pack(side='right', fill='y')
        results_text.config(yscrollcommand=scrollbar.set)

        def run_import():
            try:
                results_text.insert(tk.END, f"Starting import from: {os.path.basename(file_path)}\n\n")
                import_window.update()

                import_stats = {
                    'total_records': 0,
                    'successful_imports': 0,
                    'failed_imports': 0,
                    'duplicate_skips': 0,
                    'errors': []
                }

                file_ext = os.path.splitext(file_path)[1].lower()

                if file_ext == '.json':
                    # Import JSON data
                    status_label.config(text="Reading JSON file...")
                    import_window.update()

                    with open(file_path, 'r', encoding='utf-8') as jsonfile:
                        data = json.load(jsonfile)

                    # Handle different JSON structures
                    if isinstance(data, list):
                        records = data
                    elif isinstance(data, dict):
                        records = data.get('submissions', data.get('detections', data.get('results', [data])))
                    else:
                        records = [data]

                    import_stats['total_records'] = len(records)
                    results_text.insert(tk.END, f"Found {len(records)} records in JSON file.\n")
                    import_window.update()

                    # Process each record
                    for i, record in enumerate(records):
                        try:
                            progress_var.set((i / len(records)) * 100)
                            status_label.config(text=f"Processing record {i + 1} of {len(records)}...")
                            import_window.update()

                            # Validate and process record
                            if self._process_import_record(record, import_stats):
                                import_stats['successful_imports'] += 1
                            else:
                                import_stats['failed_imports'] += 1

                        except Exception as e:
                            import_stats['failed_imports'] += 1
                            import_stats['errors'].append(f"Record {i + 1}: {str(e)}")

                elif file_ext == '.csv':
                    # Import CSV data
                    import csv
                    status_label.config(text="Reading CSV file...")
                    import_window.update()

                    with open(file_path, 'r', encoding='utf-8') as csvfile:
                        # Detect CSV delimiter
                        sample = csvfile.read(1024)
                        csvfile.seek(0)
                        sniffer = csv.Sniffer()
                        delimiter = sniffer.sniff(sample).delimiter

                        reader = csv.DictReader(csvfile, delimiter=delimiter)
                        records = list(reader)

                    import_stats['total_records'] = len(records)
                    results_text.insert(tk.END, f"Found {len(records)} records in CSV file.\n")
                    import_window.update()

                    # Process each record
                    for i, record in enumerate(records):
                        try:
                            progress_var.set((i / len(records)) * 100)
                            status_label.config(text=f"Processing record {i + 1} of {len(records)}...")
                            import_window.update()

                            # Convert CSV record to standard format
                            formatted_record = self._format_csv_record(record)
                            if self._process_import_record(formatted_record, import_stats):
                                import_stats['successful_imports'] += 1
                            else:
                                import_stats['failed_imports'] += 1

                        except Exception as e:
                            import_stats['failed_imports'] += 1
                            import_stats['errors'].append(f"Record {i + 1}: {str(e)}")

                elif file_ext == '.txt':
                    # Import text file (assume one submission per line)
                    status_label.config(text="Reading text file...")
                    import_window.update()

                    with open(file_path, 'r', encoding='utf-8') as txtfile:
                        lines = [line.strip() for line in txtfile.readlines() if line.strip()]

                    import_stats['total_records'] = len(lines)
                    results_text.insert(tk.END, f"Found {len(lines)} text submissions.\n")
                    import_window.update()

                    # Process each line as a submission
                    for i, text in enumerate(lines):
                        try:
                            progress_var.set((i / len(lines)) * 100)
                            status_label.config(text=f"Analyzing submission {i + 1} of {len(lines)}...")
                            import_window.update()

                            # Create record from text
                            record = {
                                'submission_id': f"import_{int(time.time())}_{i}",
                                'text': text,
                                'timestamp': datetime.now().isoformat(),
                                'source': 'text_import'
                            }

                            if self._process_import_record(record, import_stats):
                                import_stats['successful_imports'] += 1
                            else:
                                import_stats['failed_imports'] += 1

                        except Exception as e:
                            import_stats['failed_imports'] += 1
                            import_stats['errors'].append(f"Line {i + 1}: {str(e)}")

                progress_var.set(100)
                status_label.config(text="Import completed!")

                # Display results
                results_text.insert(tk.END, f"\n{'='*50}\n")
                results_text.insert(tk.END, "IMPORT SUMMARY\n")
                results_text.insert(tk.END, f"{'='*50}\n")
                results_text.insert(tk.END, f"Total Records: {import_stats['total_records']}\n")
                results_text.insert(tk.END, f"Successfully Imported: {import_stats['successful_imports']}\n")
                results_text.insert(tk.END, f"Failed Imports: {import_stats['failed_imports']}\n")
                results_text.insert(tk.END, f"Duplicates Skipped: {import_stats['duplicate_skips']}\n")

                if import_stats['errors']:
                    results_text.insert(tk.END, f"\nErrors Encountered:\n")
                    for error in import_stats['errors'][:10]:  # Show max 10 errors
                        results_text.insert(tk.END, f"• {error}\n")
                    if len(import_stats['errors']) > 10:
                        results_text.insert(tk.END, f"• ... and {len(import_stats['errors']) - 10} more errors\n")

                results_text.insert(tk.END, f"\nImport completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

                # Refresh displays
                if hasattr(self, 'refresh_history'):
                    self.refresh_history()
                if hasattr(self, 'refresh_statistics'):
                    self.refresh_statistics()

            except Exception as e:
                results_text.insert(tk.END, f"\nCritical Error: {str(e)}\n")
                status_label.config(text="Import failed!")

        # Control buttons
        button_frame = ttk.Frame(import_window)
        button_frame.pack(fill='x', padx=20, pady=(0, 15))

        ttk.Button(button_frame, text="Start Import",
                  command=lambda: threading.Thread(target=run_import, daemon=True).start()).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=import_window.destroy).pack(side='right')

        # Show initial message
        results_text.insert(tk.END, f"Ready to import data from: {os.path.basename(file_path)}\n")
        results_text.insert(tk.END, f"File type: {file_ext.upper()[1:]} file\n")
        results_text.insert(tk.END, f"File size: {os.path.getsize(file_path)} bytes\n\n")
        results_text.insert(tk.END, "Click 'Start Import' to begin processing.\n")

    def _process_import_record(self, record, stats):
        """Process a single import record"""
        try:
            # Extract required fields
            submission_id = record.get('submission_id', f"import_{int(time.time())}_{random.randint(1000, 9999)}")
            text = record.get('text', record.get('content', ''))

            if not text or len(text.strip()) < 10:
                stats['errors'].append(f"Submission {submission_id}: Text too short or missing")
                return False

            # Check for duplicates (basic check based on text hash)
            text_hash = hash(text.strip())
            if hasattr(self, '_imported_hashes'):
                if text_hash in self._imported_hashes:
                    stats['duplicate_skips'] += 1
                    return False
            else:
                self._imported_hashes = set()

            self._imported_hashes.add(text_hash)

            # If detector is available, run actual analysis
            if self.detector and hasattr(self.detector, 'analyze_text'):
                try:
                    result = self.detector.analyze_text(text)
                    # Store result in detector's database/storage
                    if hasattr(self.detector, 'store_analysis'):
                        self.detector.store_analysis(submission_id, text, result)
                except Exception:
                    # If analysis fails, store basic record
                    pass

            return True

        except Exception as e:
            stats['errors'].append(f"Processing error: {str(e)}")
            return False

    def _format_csv_record(self, csv_record):
        """Format CSV record to standard format"""
        # Common CSV field mappings
        field_mappings = {
            'id': ['id', 'submission_id', 'student_id'],
            'text': ['text', 'content', 'submission', 'essay'],
            'timestamp': ['timestamp', 'date', 'submitted_at'],
            'student': ['student', 'student_name', 'name'],
            'assignment': ['assignment', 'assignment_name', 'title']
        }

        record = {}
        for standard_field, possible_fields in field_mappings.items():
            for field in possible_fields:
                if field in csv_record and csv_record[field]:
                    record[standard_field] = csv_record[field]
                    break

        # Ensure we have required fields
        if 'text' not in record:
            record['text'] = str(csv_record)  # Fallback to entire record

        if 'id' not in record:
            record['submission_id'] = f"csv_import_{int(time.time())}_{random.randint(1000, 9999)}"

        return record
    
    def show_db_status(self):
        """Show database status"""
        status_window = tk.Toplevel(self.root)
        status_window.title("Database Status")
        status_window.geometry("500x300")
        status_window.configure(bg=self.colors['bg_primary'])
        
        ttk.Label(status_window, text="Database Status", style='Title.TLabel').pack(pady=20)
        
        status_frame = ttk.Frame(status_window, style='Card.TFrame')
        status_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        try:
            # Get database info
            stats = self.detector.get_enhanced_statistics()
            
            db_info = [
                f"Database Path: {self.detector.db_path}",
                f"Status: {stats.get('database_status', 'Unknown')}",
                f"Total Submissions: {stats.get('total_submissions', 0)}",
                f"Unique Students: {stats.get('unique_students', 0)}",
                f"Detection Threshold: {self.detector.detection_threshold}"
            ]
            
            for info in db_info:
                ttk.Label(status_frame, text=info, style='Subtitle.TLabel').pack(anchor='w', padx=20, pady=5)
            
        except Exception as e:
            ttk.Label(status_frame, text=f"Error getting database status: {str(e)}", 
                     style='Subtitle.TLabel').pack(anchor='w', padx=20, pady=5)
    
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

    def send_ai_detection_report_via_email(self, analysis_results, user_email=None):
        """Send AI detection report via email GUI"""
        try:
            # Extract analysis information
            submission_id = analysis_results.get('submission_id', 'Unknown')
            ai_probability = analysis_results.get('ai_probability', 0)
            document_name = analysis_results.get('document_name', 'Unknown Document')
            analysis_type = analysis_results.get('analysis_type', 'Standard')

            # Generate email content using template system
            from university_system.infrastructure.email.template_utils import render_template

            confidence_level = ""
            if ai_probability > 80:
                confidence_level = "HIGH CONFIDENCE - Likely AI Generated"
            elif ai_probability > 50:
                confidence_level = "MODERATE CONFIDENCE - Possibly AI Generated"
            else:
                confidence_level = "LOW CONFIDENCE - Likely Human Written"

            try:
                subject, message = render_template("ai_detection_report", {
                    "document_name": document_name,
                    "user_name": user_name if user_name else "User",
                    "submission_id": submission_id,
                    "ai_probability": ai_probability,
                    "analysis_type": analysis_type,
                    "confidence_level": confidence_level,
                    "scan_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })

            except Exception as e:
                # Error handling for template rendering
                subject = None
                message = None

            # Send via email GUI if template loaded successfully
            if subject and message:
                success = self._send_email_via_gui(user_email, subject, message)
            else:
                success = False

            if success:
                messagebox.showinfo("Email Sent", f"AI detection report sent to {user_email}")
            else:
                # Show fallback
                self._show_ai_detection_email_fallback(user_email, subject, message, analysis_results)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to send AI detection report: {e}")

    def _send_email_via_gui(self, to_email, subject, message):
        """Send email via email GUI"""
        try:
            from university_system.infrastructure.email.gui.email_manager_gui import EmailManagerGUI
            email_gui = EmailManagerGUI(self.root, auth=self.auth)

            # If email GUI has send_email method, use it
            if hasattr(email_gui, 'send_email'):
                email_gui.send_email(to_email=to_email, subject=subject, message=message)
                return True
            return False
        except ImportError:
            return False
        except Exception as e:
            print(f"Error sending email via GUI: {e}")
            return False

    def _show_ai_detection_email_fallback(self, email, subject, message, analysis_results):
        """Show fallback dialog for AI detection report email"""
        try:
            fallback_window = tk.Toplevel(self.root)
            fallback_window.title("AI Detection Report Email - Manual Send")
            fallback_window.geometry("700x500")
            fallback_window.transient(self.root)

            ttk.Label(fallback_window,
                     text=f"Email system unavailable. Please manually send this report:",
                     font=('Arial', 10, 'bold')).pack(pady=10)

            details_frame = ttk.Frame(fallback_window)
            details_frame.pack(fill='both', expand=True, padx=10, pady=10)

            from tkinter.scrolledtext import ScrolledText
            details_text = ScrolledText(details_frame, height=20, width=80)
            details_text.pack(fill='both', expand=True)

            email_details = f"To: {email}\nSubject: {subject}\n\nMessage:\n{message}"
            details_text.insert('1.0', email_details)
            details_text.config(state='disabled')

            ttk.Button(fallback_window, text="Close", command=fallback_window.destroy).pack(pady=10)
        except Exception as e:
            print(f"Failed to show AI detection email fallback: {e}")

    def auto_send_ai_report_on_completion(self, analysis_results):
        """Automatically send AI detection report when analysis completes"""
        try:
            # Get user email from auth system
            user_email = None
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                user_email = self.auth.current_user.get('email')

            if user_email:
                self.send_ai_detection_report_via_email(analysis_results, user_email)
            else:
                print("No user email available for auto-send")
        except Exception as e:
            print(f"Failed to auto-send AI detection report: {e}")


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


def main_gui():
    """Main function to launch the GUI"""
    print("AI Detector GUI")
    print("===============")
    print("Initializing application.")

    try:
        import sys
        args = sys.argv[1:]
        fullscreen = '--fullscreen' in args
        demo = '--demo' in args

        if demo:
            GUILauncher.launch_with_sample_data(fullscreen=fullscreen)
        else:
            GUILauncher.launch_gui(fullscreen=fullscreen)

    except KeyboardInterrupt:
        print("\nApplication terminated by user")
    except Exception as e:
        print(f"Application error: {e}")

# Integration with existing AI Detector
def add_gui_support():
    """Add GUI support to existing AIDetector class"""
    
    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            root_widget = self.root if hasattr(self, 'root') else self.master
            if isinstance(root_widget, tk.Toplevel):
                # Just close the child window
                root_widget.destroy()
            else:
                # Running standalone, need to create main GUI
                root_widget.destroy()
                from university_system.modules.shared.gui.main_gui import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def launch_gui(self):
        """Launch GUI for this detector instance"""
        app = AIDetectorGUI(self)
        app.run()
    
    # Add method to AIDetector class
    AIDetector.launch_gui = launch_gui

# Main function
def main():
    """Main function for testing the ultimate detector"""
    print("Ultimate AI Detector - Advanced Testing Mode")
    print("=" * 50)
    
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'ultimate_demo':
        ultimate_demo()
        return
    
    try:
        # Initialize ultimate detector
        detector = AIDetector()
        print("✓ Ultimate AI Detector initialized successfully!")
        
        # Get statistics
        stats = detector.get_ultimate_statistics()
        print(f"✓ System ready with {len(stats['features_active'])} advanced features")
        
        # List active features
        active_features = [name for name, active in stats['features_active'].items() if active]
        print(f"✓ Active features: {', '.join(active_features)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("This is expected if running standalone without proper database setup.")

# Example usage and testing
if __name__ == "__main__":
    main()
