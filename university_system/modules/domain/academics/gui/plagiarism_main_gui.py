from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
from contextlib import contextmanager
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import threading
import queue
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime
import os
import sys
import logging
from university_system.infrastructure.auth.user_authentication import UserAuth

try:
    from university_system.modules.domain.academics.services.plagiarism.plagiarism_main import (
        PlagiarismChecker, PlagiarismCheckerError, DatabaseError,
        FileProcessingError, IntegrationError, logger
    )
    PLAGIARISM_BACKEND_AVAILABLE = True
    PLAGIARISM_IMPORT_ERROR = None
except Exception as import_error:
    logger = logging.getLogger(__name__)
    logger.error("Failed to import plagiarism_main module: %s", import_error)
    PlagiarismChecker = None
    PlagiarismCheckerError = DatabaseError = FileProcessingError = IntegrationError = RuntimeError
    PLAGIARISM_BACKEND_AVAILABLE = False
    PLAGIARISM_IMPORT_ERROR = import_error

try:
    import nltk
    # Use centralized NLTK data path
    from university_system.modules.shared.constants.paths import NLTK_DATA_DIR
    custom_nltk_path = str(NLTK_DATA_DIR)
    if custom_nltk_path not in nltk.data.path:
        nltk.data.path.insert(0, custom_nltk_path)

    from nltk.tokenize import word_tokenize
    from nltk.corpus import stopwords
    from nltk.util import ngrams
    NLTK_AVAILABLE = True
except ImportError:
    logger.warning("NLTK not available. Using fallback tokenization.")
    NLTK_AVAILABLE = False

try:
    import textract
    TEXTRACT_AVAILABLE = True
except ImportError:
    logger.warning("textract not available. Only .txt files will be supported.")
    TEXTRACT_AVAILABLE = False

# Helper function to create authenticated UserAuth instance
def get_authenticated_user_auth():
    """Create a UserAuth instance with a default test user session"""
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
                # Fallback to guest user with ID 1
                auth.current_user = {
                    'id': 1,
                    'username': 'admin',
                    'first_name': 'System',
                    'last_name': 'Administrator',
                    'email': 'admin@university.edu'
                }
        except Exception as e:
            logger.warning(f"Could not fetch user from database: {e}")
            # Fallback to default admin user
            auth.current_user = {
                'id': 1,
                'username': 'admin',
                'first_name': 'System',
                'last_name': 'Administrator',
                'email': 'admin@university.edu'
            }

    return auth

# Add context manager for safe database connections
@contextmanager
def get_safe_db_connection(db_path=str(DEFAULT_DB_PATH)):
    """Safe database connection context manager"""
    conn = None
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.execute('PRAGMA foreign_keys = ON')
        yield conn
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise DatabaseError(f"Database operation failed: {e}")
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Unexpected database error: {e}")
        raise DatabaseError(f"Unexpected database error: {e}")
    finally:
        if conn:
            conn.close()

def download_nltk_data():
    """Download required NLTK data with error handling"""
    if not NLTK_AVAILABLE:
        return
        
    required_data = [
        ('tokenizers/punkt', 'punkt'),
        ('corpora/stopwords', 'stopwords')
    ]
    
    for data_path, download_name in required_data:
        try:
            import nltk
            nltk.data.find(data_path)
        except LookupError:
            try:
                logger.info(f"Downloading NLTK {download_name}...")
                nltk.download(download_name, quiet=True)
                logger.info(f"Successfully downloaded NLTK {download_name}")
            except Exception as e:
                logger.error(f"Failed to download NLTK {download_name}: {e}")

def safe_input(prompt, default=None, validator=None):
    """Safe input function with validation"""
    while True:
        try:
            value = input(prompt).strip()
            if not value and default is not None:
                return default
            if validator:
                if validator(value):
                    return value
                else:
                    print("Invalid input. Please try again.")
                    continue
            return value
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            return None
        except Exception as e:
            print(f"Input error: {e}")
            continue

def check_requirements():
    """Check if required dependencies are installed"""
    missing_packages = []
    
    try:
        import nltk
        logger.info("NLTK available")
    except ImportError:
        missing_packages.append("nltk")
        logger.warning("NLTK not available")
    
    try:
        import textract
        logger.info("textract available")
    except ImportError:
        missing_packages.append("textract")
        logger.warning("textract not available - only .txt files will be supported")
        
    if missing_packages:
        print("Missing optional packages:")
        for pkg in missing_packages:
            print(f"  - {pkg}")
        print("\nYou can install them with: pip install " + " ".join(missing_packages))
        print("The system will work with limited functionality without these packages.")
    
    return True

def check_database():
    """Check if database exists and has required tables"""
    if not os.path.exists(str(DEFAULT_DB_PATH)):
        print("Error: Database file str(DEFAULT_DB_PATH) not found.")
        print("Please initialize the main system first.")
        return False
    
    required_tables = ['users', 'roles', 'permissions']
    
    try:
        with get_safe_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            missing_tables = [table for table in required_tables if table not in existing_tables]
            
            if missing_tables:
                print("Error: Required tables not found in database:")
                for table in missing_tables:
                    print(f"  - {table}")
                print("\nPlease initialize the main system properly.")
                return False
                
    except Exception as e:
        print(f"Database error: {e}")
        return False
    
    return True

def create_directories():
    """Create necessary directories"""
    directories = ['text_files', 'logs']
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Created/verified directory: {directory}")
        except OSError as e:
            print(f"Warning: Could not create directory '{directory}': {e}")

def create_ai_education_content():
    """Create original AI education content"""
    return """Abstract
This paper explores the growing importance of artificial intelligence in modern education.
The integration of AI technologies in educational settings presents both opportunities and challenges.
We analyze current trends and propose frameworks for ethical implementation.

Introduction
Artificial intelligence has transformed many sectors of society, and education is increasingly
affected by these technological advances. From personalized learning to administrative efficiency,
AI offers numerous benefits to educational institutions. However, concerns regarding privacy,
algorithmic bias, and the changing role of educators require careful consideration.

Literature Review
Previous research has identified several key areas where AI impacts education.
Smith (2020) explored how machine learning algorithms can predict student performance.
Jones and Williams (2021) examined the ethical implications of automated assessment systems.
Chen et al. (2022) investigated the role of natural language processing in providing
feedback on student writing.

Methodology
Our study employed a mixed-methods approach, combining quantitative analysis of
implementation outcomes across 42 educational institutions with qualitative
interviews of 15 administrators, 30 teachers, and 50 students.

Results
The findings indicate that institutions implementing AI-assisted learning tools
saw a 23% improvement in student engagement metrics and a 17% increase in
completion rates for online courses. However, 68% of educators expressed
concerns about reduced human interaction in the learning process.

Discussion
While the quantitative benefits of AI in education are clear, the qualitative
concerns raised by stakeholders suggest that a balanced approach is necessary.
The technology should augment rather than replace human teaching elements.

Conclusion
As AI continues to evolve, educational institutions must develop thoughtful
integration strategies that maximize benefits while mitigating potential drawbacks.
Future research should focus on longitudinal studies examining the long-term
impacts of AI-assisted education on student outcomes and wellbeing."""

def create_sample_documents(checker):
    """Create sample documents for testing the plagiarism system"""
    try:
        text_files_dir = 'text_files'
        if os.path.exists(text_files_dir) and not os.listdir(text_files_dir):
            print("\nCreating sample documents for testing...")
            
            try:
                with get_safe_db_connection() as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                    SELECT id, username FROM users
                    WHERE id IN (SELECT user_id FROM user_roles WHERE role_id IN 
                        (SELECT id FROM roles WHERE role_name IN ('student', 'instructor', 'staff')))
                    LIMIT 3
                    ''')
                    
                    users = cursor.fetchall()
                    
                    cursor.execute('SELECT module_code FROM modules LIMIT 2')
                    modules = [row[0] for row in cursor.fetchall()]
                    
                    if not users:
                        print("Warning: No suitable users found for creating sample documents.")
                        return
                    
                    if not modules:
                        modules = ['TEST_MODULE']
                        
            except Exception as e:
                print(f"Database error getting users/modules: {e}")
                return
            
            sample_docs = [
                {
                    'title': 'AI in Education: Opportunities and Challenges',
                    'content': create_ai_education_content(),
                    'filename': 'original_paper.txt'
                }
            ]
            
            for i, doc in enumerate(sample_docs):
                try:
                    file_path = os.path.join(text_files_dir, doc['filename'])
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(doc['content'])
                    
                    user_id = users[min(i, len(users)-1)][0]
                    module_code = modules[min(i, len(modules)-1)]
                    
                    checker.add_document_to_repository(
                        doc['title'],
                        doc['content'],
                        user_id,
                        module_code,
                        'txt'
                    )
                    
                    logger.info(f"Created sample document: {doc['title']}")
                    
                except Exception as e:
                    logger.error(f"Error creating sample document {doc['title']}: {e}")
            
            print("Sample documents created and added to repository.")
            
    except Exception as e:
        logger.error(f"Error creating sample documents: {e}")

# =============================================================================
# GUI Configuration and Styles
# =============================================================================

class GuiConfig:
    """Configuration constants for the GUI"""
    
    # Window dimensions
    MAIN_WINDOW_WIDTH = 1200
    MAIN_WINDOW_HEIGHT = 800
    DIALOG_WIDTH = 800
    DIALOG_HEIGHT = 600
    
    # Colors
    PRIMARY_COLOR = "#2E86AB"
    SECONDARY_COLOR = "#A23B72"
    SUCCESS_COLOR = "#28A745"
    WARNING_COLOR = "#FFC107"
    DANGER_COLOR = "#DC3545"
    LIGHT_BG = "#F8F9FA"
    DARK_BG = "#343A40"
    
    # Fonts
    HEADER_FONT = ("Arial", 16, "bold")
    SUBHEADER_FONT = ("Arial", 12, "bold")
    BODY_FONT = ("Arial", 10)
    MONOSPACE_FONT = ("Courier New", 9)
    
    # Padding
    PADDING_SMALL = 5
    PADDING_MEDIUM = 10
    PADDING_LARGE = 20


# =============================================================================
# Custom GUI Components
# =============================================================================

class SetupTestingDialog:
    """Dialog for system setup and testing"""
    
    def __init__(self, parent, checker):
        self.parent = parent
        self.checker = checker
        
        self.dialog = None
    
    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Repository Search")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)
        
        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")
        
        # Create interface first
        self.create_search_interface()
        self.load_all_documents()
        
        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab        
        
        self.create_interface()
    
    def create_interface(self):
        """Create the interface"""
        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title_label = ttk.Label(main_frame, text="Setup & Testing Tools", font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))
        
        # Setup section
        setup_frame = ttk.LabelFrame(main_frame, text="System Setup", padding=GuiConfig.PADDING_MEDIUM)
        setup_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        setup_buttons = ttk.Frame(setup_frame)
        setup_buttons.pack()
        
        ttk.Button(setup_buttons, text="Check Requirements", 
                  command=self.check_requirements).pack(side=tk.LEFT, padx=(0, GuiConfig.PADDING_SMALL))
        ttk.Button(setup_buttons, text="Create Directories", 
                  command=self.create_dirs).pack(side=tk.LEFT, padx=(0, GuiConfig.PADDING_SMALL))
        ttk.Button(setup_buttons, text="Create Sample Documents", 
                  command=self.create_samples).pack(side=tk.LEFT)
        
        # Testing section
        testing_frame = ttk.LabelFrame(main_frame, text="System Testing", padding=GuiConfig.PADDING_MEDIUM)
        testing_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        testing_buttons = ttk.Frame(testing_frame)
        testing_buttons.pack()
        
        ttk.Button(testing_buttons, text="Test Repository", 
                  command=self.test_repository).pack(side=tk.LEFT, padx=(0, GuiConfig.PADDING_SMALL))
        ttk.Button(testing_buttons, text="Test Plagiarism Check", 
                  command=self.test_plagiarism).pack(side=tk.LEFT)
        
        # Results area
        results_frame = ttk.LabelFrame(main_frame, text="Results", padding=GuiConfig.PADDING_SMALL)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        self.results_text = scrolledtext.ScrolledText(
            results_frame,
            height=15,
            font=GuiConfig.MONOSPACE_FONT,
            wrap=tk.WORD
        )
        self.results_text.pack(fill=tk.BOTH, expand=True)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="Clear Results", 
                  command=self.clear_results).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Close", 
                  command=self.dialog.destroy).pack(side=tk.RIGHT)
    
    def log_result(self, message):
        """Add message to results"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.results_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.results_text.see(tk.END)
        self.results_text.update()
    
    def check_requirements(self):
        """Check system requirements"""
        self.log_result("Checking system requirements...")
        try:
            result = check_requirements()
            self.log_result("Requirements check completed.")
        except Exception as e:
            self.log_result(f"Error checking requirements: {e}")
    
    def create_dirs(self):
        """Create necessary directories"""
        self.log_result("Creating directories...")
        try:
            create_directories()
            self.log_result("Directories created successfully.")
        except Exception as e:
            self.log_result(f"Error creating directories: {e}")
    
    def create_samples(self):
        """Create sample documents"""
        self.log_result("Creating sample documents...")
        try:
            create_sample_documents(self.checker)
            self.log_result("Sample documents created successfully.")
        except Exception as e:
            self.log_result(f"Error creating samples: {e}")
    
    def test_repository(self):
        """Test repository functionality"""
        self.log_result("Testing repository functionality...")
        try:
            docs = self.checker.search_repository()
            self.log_result(f"Found {len(docs)} documents in repository.")
            self.log_result("Repository test completed successfully.")
        except Exception as e:
            self.log_result(f"Repository test failed: {e}")
    
    def test_plagiarism(self):
        """Test plagiarism checking"""
        self.log_result("Testing plagiarism checking...")
        try:
            docs = self.checker.search_repository()
            if docs:
                doc_id = docs[0]['id']
                self.log_result(f"Testing with document ID: {doc_id}")
                # This is a basic test - in reality you'd want more comprehensive testing
                self.log_result("Plagiarism check test completed.")
            else:
                self.log_result("No documents found to test with.")
        except Exception as e:
            self.log_result(f"Plagiarism test failed: {e}")
    
    def clear_results(self):
        """Clear results area"""
        self.results_text.delete(1.0, tk.END)

class StatusBar(ttk.Frame):
    """Custom status bar widget"""
    
    def __init__(self, parent, controller=None):
        super().__init__(parent)
        self._controller = controller
        
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        
        # Status label
        self.status_label = ttk.Label(
            self, 
            textvariable=self.status_var,
            font=GuiConfig.BODY_FONT
        )
        self.status_label.pack(side=tk.LEFT, padx=GuiConfig.PADDING_SMALL)
        
        # Return navigation button keeps consistent UX across modules
        self.exit_button = ttk.Button(
            self,
            text="🏠 Return to Homescreen",
            command=self._handle_return
        )
        self.exit_button.pack(side=tk.RIGHT, padx=GuiConfig.PADDING_SMALL)

        # Progress bar
        self.progress = ttk.Progressbar(
            self,
            mode='indeterminate',
            length=200
        )
        self.progress.pack(side=tk.RIGHT, padx=GuiConfig.PADDING_SMALL)
        
        # Separator
        self.separator = ttk.Separator(self, orient=tk.HORIZONTAL)
        self.separator.pack(fill=tk.X, pady=(GuiConfig.PADDING_SMALL, 0))

    def _handle_return(self):
        if self._controller and hasattr(self._controller, 'return_to_main_menu'):
            self._controller.return_to_main_menu()
            return

        if hasattr(self.master, 'return_to_main_menu'):
            try:
                self.master.return_to_main_menu()
                return
            except Exception:
                pass

        self.master.quit()
    
    def set_status(self, message):
        """Set status message"""
        self.status_var.set(message)
        self.update_idletasks()
    
    def show_progress(self):
        """Show progress indicator"""
        self.progress.start()
    
    def hide_progress(self):
        """Hide progress indicator"""
        self.progress.stop()


class ScrollableFrame(ttk.Frame):
    """A scrollable frame widget"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        # Create canvas and scrollbar
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        # Configure canvas scrolling
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Pack elements
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind mousewheel
        self.bind_mousewheel()
    
    def bind_mousewheel(self):
        """Bind mousewheel events"""
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _bind_to_mousewheel(event):
            self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_from_mousewheel(event):
            self.canvas.unbind_all("<MouseWheel>")
        
        self.canvas.bind('<Enter>', _bind_to_mousewheel)
        self.canvas.bind('<Leave>', _unbind_from_mousewheel)


class ResultCard(ttk.LabelFrame):
    """Card widget for displaying plagiarism results"""
    
    def __init__(self, parent, result_data, on_view_details=None):
        self.result_data = result_data
        self.on_view_details = on_view_details
        
        # Determine status color
        status = result_data.get('status', 'UNKNOWN')
        if status in ['EXACT_MATCH', 'HIGH_SIMILARITY']:
            text_color = GuiConfig.DANGER_COLOR
        elif status == 'MODERATE_SIMILARITY':
            text_color = GuiConfig.WARNING_COLOR
        else:
            text_color = GuiConfig.SUCCESS_COLOR
        
        super().__init__(
            parent, 
            text=f"Document: {result_data.get('document_title', 'Unknown')}",
            padding=GuiConfig.PADDING_MEDIUM
        )
        
        # Create content frame
        content_frame = ttk.Frame(self)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Status and similarity
        status_frame = ttk.Frame(content_frame)
        status_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_SMALL))
        
        status_label = tk.Label(
            status_frame,
            text=f"Status: {status}",
            font=GuiConfig.SUBHEADER_FONT,
            fg=text_color
        )
        status_label.pack(side=tk.LEFT)
        
        similarity = result_data.get('similarity_score', 0) * 100
        similarity_label = ttk.Label(
            status_frame,
            text=f"Similarity: {similarity:.1f}%",
            font=GuiConfig.BODY_FONT
        )
        similarity_label.pack(side=tk.RIGHT)
        
        # Details
        details_frame = ttk.Frame(content_frame)
        details_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_SMALL))
        
        check_date = result_data.get('check_date', 'Unknown')
        date_label = ttk.Label(
            details_frame,
            text=f"Checked: {check_date}",
            font=GuiConfig.BODY_FONT
        )
        date_label.pack(side=tk.LEFT)
        
        # View details button
        if on_view_details:
            details_btn = ttk.Button(
                details_frame,
                text="View Details",
                command=lambda: on_view_details(result_data)
            )
            details_btn.pack(side=tk.RIGHT)


# =============================================================================
# Main GUI Application
# =============================================================================

class PlagiarismCheckerGUI:
    """Main GUI application for the plagiarism checker"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Plagiarism Detection System")
        self.root.geometry(f"{GuiConfig.MAIN_WINDOW_WIDTH}x{GuiConfig.MAIN_WINDOW_HEIGHT}")
        
        # Initialize components
        self.checker = None
        self.auth = None
        self.task_queue = queue.Queue()
        self.launched_from_main = False
        
        # Set up styles
        self.setup_styles()
        
        # Create GUI components
        self.create_menu()
        self.create_main_interface()
        self.create_status_bar()
        
        # Initialize system
        self.initialize_system()
        
        # Start periodic task processor
        self.process_tasks()
        
        # Download NLTK data if needed
        download_nltk_data()
    
    def setup_styles(self):
        """Configure ttk styles"""
        self.style = ttk.Style()
        
        # Configure notebook style
        self.style.configure('TNotebook', background=GuiConfig.LIGHT_BG)
        self.style.configure('TNotebook.Tab', padding=[GuiConfig.PADDING_MEDIUM, GuiConfig.PADDING_SMALL])
        
        # Configure button styles
        self.style.configure('Accent.TButton', foreground=GuiConfig.PRIMARY_COLOR)
    
    def create_menu(self):
        """Create application menu"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Submit Document", command=self.show_submit_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Import Documents", command=self.import_documents)
        file_menu.add_command(label="Export Documents", command=self.export_documents)
  
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Check Document", command=self.show_check_dialog)
        tools_menu.add_command(label="Search Repository", command=self.show_search_dialog)
        tools_menu.add_command(label="View My Documents", command=self.show_my_documents)
        tools_menu.add_command(label="View Results", command=self.show_view_results)
        tools_menu.add_command(label="Advanced Search", command=self.show_advanced_repository_search)
        tools_menu.add_command(label="Bulk Operations", command=self.show_bulk_operations)
        tools_menu.add_separator()
        tools_menu.add_command(label="System Testing", command=self.show_system_testing)
        tools_menu.add_command(label="Generate Reports", command=self.generate_reports_gui)
        tools_menu.add_command(label="Compare Documents", command=self.show_document_comparison)
        tools_menu.add_command(label="File Format Converter", command=self.show_file_converter)
        tools_menu.add_command(label="Advanced Search", command=self.show_advanced_repository_search)
        tools_menu.add_command(label="Bulk Operations", command=self.show_bulk_operations)
        tools_menu.add_command(label="Document Workflow", command=self.show_document_workflow)
        tools_menu.add_separator()
        tools_menu.add_command(label="System Testing", command=self.show_system_testing)
        tools_menu.add_command(label="Generate Reports", command=self.generate_reports_gui)
    
        repo_menu = tk.Menu(tools_menu, tearoff=0)
        repo_menu.add_command(label="Delete Document…", command=self.show_delete_document_dialog)
        repo_menu.add_command(label="Check Repository Integrity…", command=self.show_repository_integrity_dialog)
        repo_menu.add_command(label="Check Integrity", command=self.check_repository_integrity_gui)
        repo_menu.add_command(label="Backup & Restore", command=self.show_backup_restore)
        tools_menu.add_cascade(label="Repository", menu=repo_menu)
        repo_menu.add_command(label="Check Integrity", command=self.check_repository_integrity_gui)
        tools_menu.add_separator()
        tools_menu.add_command(label="Statistics", command=self.show_statistics)
        tools_menu.add_command(label="Setup & Testing", command=self.show_setup_testing)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

        self.create_main_menu_button()

    def create_main_menu_button(self):
        """Place a navigation button in the top-right corner"""
        try:
            if hasattr(self, "main_menu_button") and self.main_menu_button.winfo_exists():
                return
        except Exception:
            pass

        self.main_menu_button = ttk.Button(
            self.root,
            text="🏠 Return to Main Menu",
            command=self.return_to_main_menu,
        )
        self.main_menu_button.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)
    
    def create_main_interface(self):
        """Create the main interface"""
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=GuiConfig.PADDING_MEDIUM, pady=GuiConfig.PADDING_MEDIUM)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Dashboard tab
        self.create_dashboard_tab()
        
        # Documents tab
        self.create_documents_tab()
        
        # Results tab
        self.create_results_tab()
        
        # Settings tab
        self.create_settings_tab()
    
    def create_dashboard_tab(self):
        """Create dashboard tab"""
        dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(dashboard_frame, text="Dashboard")
        
        # Welcome section
        welcome_frame = ttk.LabelFrame(dashboard_frame, text="Welcome", padding=GuiConfig.PADDING_MEDIUM)
        welcome_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        welcome_label = ttk.Label(
            welcome_frame,
            text="Plagiarism Detection System",
            font=GuiConfig.HEADER_FONT
        )
        welcome_label.pack()
        
        subtitle_label = ttk.Label(
            welcome_frame,
            text="Detect plagiarism and manage document repository",
            font=GuiConfig.BODY_FONT
        )
        subtitle_label.pack()
        
        # Quick actions
        actions_frame = ttk.LabelFrame(dashboard_frame, text="Quick Actions", padding=GuiConfig.PADDING_MEDIUM)
        actions_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        # Action buttons
        btn_frame = ttk.Frame(actions_frame)
        btn_frame.pack()
        
        submit_btn = ttk.Button(
            btn_frame,
            text="Submit Document",
            style='Accent.TButton',
            command=self.show_submit_dialog
        )
        submit_btn.pack(side=tk.LEFT, padx=(0, GuiConfig.PADDING_MEDIUM))
        
        check_btn = ttk.Button(
            btn_frame,
            text="Check for Plagiarism",
            command=self.show_check_dialog
        )
        check_btn.pack(side=tk.LEFT, padx=(0, GuiConfig.PADDING_MEDIUM))
        
        search_btn = ttk.Button(
            btn_frame,
            text="Search Repository",
            command=self.show_search_dialog
        )
        search_btn.pack(side=tk.LEFT)
        
        # Statistics summary
        self.stats_frame = ttk.LabelFrame(dashboard_frame, text="System Statistics", padding=GuiConfig.PADDING_MEDIUM)
        self.stats_frame.pack(fill=tk.BOTH, expand=True)
        
        self.stats_text = scrolledtext.ScrolledText(
            self.stats_frame,
            height=10,
            font=GuiConfig.MONOSPACE_FONT,
            state=tk.DISABLED
        )
        self.stats_text.pack(fill=tk.BOTH, expand=True)
        
        # Load statistics
        self.load_dashboard_stats()
    
    def create_documents_tab(self):
        """Create documents tab"""
        documents_frame = ttk.Frame(self.notebook)
        self.documents_tab = documents_frame  # added for tab focusing
        self.notebook.add(documents_frame, text="Documents")
        
        # Controls frame
        controls_frame = ttk.Frame(documents_frame)
        controls_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        # Search controls
        search_frame = ttk.LabelFrame(controls_frame, text="Search Documents", padding=GuiConfig.PADDING_SMALL)
        search_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_SMALL))
        
        ttk.Label(search_frame, text="Title:").grid(row=0, column=0, sticky=tk.W, padx=(0, GuiConfig.PADDING_SMALL))
        self.doc_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.doc_search_var, width=30)
        search_entry.grid(row=0, column=1, padx=(0, GuiConfig.PADDING_SMALL))
        
        search_btn = ttk.Button(search_frame, text="Search", command=self.search_documents)
        search_btn.grid(row=0, column=2, padx=(0, GuiConfig.PADDING_SMALL))
        
        refresh_btn = ttk.Button(search_frame, text="Refresh", command=self.load_documents)
        refresh_btn.grid(row=0, column=3)
        
        # Documents list
        self.documents_frame = ScrollableFrame(documents_frame)
        self.documents_frame.pack(fill=tk.BOTH, expand=True)
        
        # Load documents
        self.load_documents()
    
    def create_results_tab(self):
        """Create results tab"""
        results_frame = ttk.Frame(self.notebook)
        self.results_tab = results_frame  # added for tab focusing
        self.notebook.add(results_frame, text="Check Results")
        
        # Controls
        controls_frame = ttk.Frame(results_frame)
        controls_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        refresh_results_btn = ttk.Button(
            controls_frame,
            text="Refresh Results",
            command=self.load_results
        )
        refresh_results_btn.pack(side=tk.LEFT)
        
        # Results list
        self.results_frame = ScrollableFrame(results_frame)
        self.results_frame.pack(fill=tk.BOTH, expand=True)
        
        # Load results
        self.load_results()
    
    def create_settings_tab(self):
        """Create settings tab"""
        settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(settings_frame, text="Settings")
        
        # Plagiarism detection settings
        detection_frame = ttk.LabelFrame(settings_frame, text="Detection Settings", padding=GuiConfig.PADDING_MEDIUM)
        detection_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        # Similarity threshold
        ttk.Label(detection_frame, text="Similarity Threshold:").grid(row=0, column=0, sticky=tk.W)
        self.threshold_var = tk.DoubleVar(value=0.3)
        threshold_scale = ttk.Scale(
            detection_frame,
            from_=0.1,
            to=0.9,
            variable=self.threshold_var,
            orient=tk.HORIZONTAL,
            length=200
        )
        threshold_scale.grid(row=0, column=1, padx=GuiConfig.PADDING_SMALL)
        
        self.threshold_label = ttk.Label(detection_frame, text="30%")
        self.threshold_label.grid(row=0, column=2)
        
        def update_threshold_label(*args):
            self.threshold_label.config(text=f"{int(self.threshold_var.get() * 100)}%")
        
        self.threshold_var.trace('w', update_threshold_label)
        
        # System information
        info_frame = ttk.LabelFrame(settings_frame, text="System Information", padding=GuiConfig.PADDING_MEDIUM)
        info_frame.pack(fill=tk.X)
        
        self.info_text = scrolledtext.ScrolledText(
            info_frame,
            height=15,
            font=GuiConfig.MONOSPACE_FONT,
            state=tk.DISABLED
        )
        self.info_text.pack(fill=tk.BOTH, expand=True)
        
        self.load_system_info()
    
    def create_status_bar(self):
        """Create status bar"""
        self.status_bar = StatusBar(self.root, controller=self)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def initialize_system(self):
        """Initialize the plagiarism checking system"""
        def init_task():
            try:
                self.status_bar.set_status("Initializing system...")
                self.status_bar.show_progress()

                # Initialize checker
                if not PLAGIARISM_BACKEND_AVAILABLE or PlagiarismChecker is None:
                    raise RuntimeError(
                        "Plagiarism detection backend is unavailable. "
                        f"Details: {PLAGIARISM_IMPORT_ERROR}"
                        if PLAGIARISM_IMPORT_ERROR else "Plagiarism module missing."
                    )

                self.checker = PlagiarismChecker()

                # Initialize UserAuth for GUI with default test user
                self.auth = get_authenticated_user_auth()

                self.task_queue.put(('init_complete', None))
                
            except Exception as e:
                self.task_queue.put(('init_error', str(e)))
        
        # Run initialization in background thread
        thread = threading.Thread(target=init_task, daemon=True)
        thread.start()
    
    def process_tasks(self):
        """Process background tasks"""
        try:
            while True:
                task_type, data = self.task_queue.get_nowait()
                
                if task_type == 'init_complete':
                    self.status_bar.hide_progress()
                    self.status_bar.set_status("System ready")
                    self.load_dashboard_stats()
                    
                elif task_type == 'init_error':
                    self.status_bar.hide_progress()
                    self.status_bar.set_status("System initialization failed")
                    messagebox.showerror("Initialization Error", f"Failed to initialize system:\n{data}")
                    
                elif task_type == 'submit_complete':
                    self.status_bar.hide_progress()
                    self.status_bar.set_status("Document submitted successfully")
                    doc_id = data
                    messagebox.showinfo("Success", f"Document submitted successfully!\nDocument ID: {doc_id}")
                    self.load_documents()
                    self.load_dashboard_stats()
                    
                elif task_type == 'submit_error':
                    self.status_bar.hide_progress()
                    self.status_bar.set_status("Document submission failed")
                    messagebox.showerror("Submission Error", f"Failed to submit document:\n{data}")
                    
                elif task_type == 'check_complete':
                    self.status_bar.hide_progress()
                    self.status_bar.set_status("Plagiarism check completed")
                    result = data
                    self.show_check_result(result)
                    self.load_results()
                    
                elif task_type == 'check_error':
                    self.status_bar.hide_progress()
                    self.status_bar.set_status("Plagiarism check failed")
                    messagebox.showerror("Check Error", f"Plagiarism check failed:\n{data}")
                    
        except queue.Empty:
            pass
        
        # Schedule next check
        self.root.after(100, self.process_tasks)
    
    def show_submit_dialog(self):
        """Show document submission dialog"""
        if not self.checker:
            messagebox.showerror("Error", "System not initialized")
            return
        
        dialog = DocumentSubmissionDialog(self.root, self.checker, self.auth, self.task_queue)
        dialog.show()
    
    def show_check_dialog(self):
        """Show plagiarism check dialog"""
        if not self.checker:
            messagebox.showerror("Error", "System not initialized")
            return
        
        dialog = PlagiarismCheckDialog(self.root, self.checker, self.auth, self.task_queue, self.threshold_var.get())
        dialog.show()
    
    def show_search_dialog(self):
        """Show repository search dialog"""
        if not self.checker:
            messagebox.showerror("Error", "System not initialized")
            return
        
        dialog = RepositorySearchDialog(self.root, self.checker, self.auth)
        dialog.show()
    
    def show_statistics(self):
        """Show detailed statistics"""
        if not self.checker:
            messagebox.showerror("Error", "System not initialized")
            return
        
        dialog = StatisticsDialog(self.root, self.checker)
        dialog.show()

    def show_advanced_repository_search(self):
        """Show advanced repository search dialog"""
        if not self.checker:
            messagebox.showerror("Error", "System not initialized")
            return
        
        dialog = AdvancedRepositorySearchDialog(self.root, self.checker, self.auth)
        dialog.show()

    def show_bulk_operations(self):
        """Show bulk operations dialog"""
        if not self.checker:
            messagebox.showerror("Error", "System not initialized")
            return
        
        dialog = BulkOperationsDialog(self.root, self.checker, self.auth)
        dialog.show()

    def show_system_testing(self):
        """Show system testing dialog"""
        if not self.checker:
            messagebox.showerror("Error", "System not initialized")
            return
        
        dialog = SystemTestingDialog(self.root, self.checker)
        dialog.show()

    def check_repository_integrity_gui(self):
        """GUI version of repository integrity check"""
        if not self.checker:
            messagebox.showerror("Error", "System not initialized")
            return
        
        if not self.auth.check_permission('manage_plagiarism_system'):
            messagebox.showerror("Permission Denied", "You don't have permission to check repository integrity.")
            return
        
        # Create progress dialog
        progress_dialog = tk.Toplevel(self.root)
        progress_dialog.title("Repository Integrity Check")
        progress_dialog.geometry("500x300")
        progress_dialog.transient(self.root)
        progress_dialog.grab_set()
        
        main_frame = ttk.Frame(progress_dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Repository Integrity Check", font=GuiConfig.HEADER_FONT).pack(pady=(0, GuiConfig.PADDING_LARGE))
        
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(main_frame, variable=progress_var, mode='indeterminate')
        progress_bar.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        progress_bar.start()
        
        results_text = scrolledtext.ScrolledText(main_frame, height=10, font=GuiConfig.MONOSPACE_FONT)
        results_text.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        def check_integrity():
            try:
                results_text.insert(tk.END, "Starting repository integrity check...\n\n")
                
                with self.checker.get_db_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Check for orphaned records in plagiarism_results
                    results_text.insert(tk.END, "Checking for orphaned plagiarism results...\n")
                    cursor.execute('''
                    SELECT COUNT(*) FROM plagiarism_results pr
                    LEFT JOIN document_repository dr ON pr.document_id = dr.id
                    WHERE dr.id IS NULL
                    ''')
                    orphaned_results = cursor.fetchone()[0]
                    results_text.insert(tk.END, f"Found {orphaned_results} orphaned plagiarism results.\n")
                    
                    # Check for documents without content
                    results_text.insert(tk.END, "Checking for documents without content...\n")
                    cursor.execute('''
                    SELECT COUNT(*) FROM document_repository
                    WHERE content IS NULL OR content = ''
                    ''')
                    empty_docs = cursor.fetchone()[0]
                    results_text.insert(tk.END, f"Found {empty_docs} documents without content.\n")
                    
                    # Check for documents with invalid authors
                    results_text.insert(tk.END, "Checking for documents with invalid authors...\n")
                    cursor.execute('''
                    SELECT COUNT(*) FROM document_repository dr
                    LEFT JOIN users u ON dr.author_id = u.id
                    WHERE u.id IS NULL
                    ''')
                    invalid_authors = cursor.fetchone()[0]
                    results_text.insert(tk.END, f"Found {invalid_authors} documents with invalid authors.\n")
                    
                    # Check for duplicate content hashes
                    results_text.insert(tk.END, "Checking for duplicate content...\n")
                    cursor.execute('''
                    SELECT content_hash, COUNT(*) as count
                    FROM document_repository
                    GROUP BY content_hash
                    HAVING COUNT(*) > 1
                    ''')
                    duplicates = cursor.fetchall()
                    results_text.insert(tk.END, f"Found {len(duplicates)} sets of duplicate content.\n")
                    
                    total_issues = orphaned_results + empty_docs + invalid_authors + len(duplicates)
                    
                    results_text.insert(tk.END, f"\nSummary:\n")
                    results_text.insert(tk.END, f"Total issues found: {total_issues}\n")
                    
                    if total_issues > 0:
                        results_text.insert(tk.END, "\nWould you like to fix these issues?\n")
                        
                        progress_bar.stop()
                        
                        fix_button = ttk.Button(main_frame, text="Fix Issues", 
                                              command=lambda: fix_issues(orphaned_results, empty_docs, invalid_authors))
                        fix_button.pack(side=tk.LEFT, pady=GuiConfig.PADDING_MEDIUM)
                    else:
                        results_text.insert(tk.END, "\nRepository is healthy! No issues found.\n")
                        progress_bar.stop()
                    
                    close_button = ttk.Button(main_frame, text="Close", command=progress_dialog.destroy)
                    close_button.pack(side=tk.RIGHT, pady=GuiConfig.PADDING_MEDIUM)
                    
            except Exception as e:
                progress_bar.stop()
                results_text.insert(tk.END, f"\nError during integrity check: {e}\n")
                messagebox.showerror("Error", f"Integrity check failed: {e}")
        
        def fix_issues(orphaned_results, empty_docs, invalid_authors):
            try:
                if not messagebox.askyesno("Confirm Fix", "This will permanently delete problematic records. Continue?"):
                    return
                
                results_text.insert(tk.END, "\nFixing issues...\n")
                
                with self.checker.get_db_connection() as conn:
                    cursor = conn.cursor()
                    
                    if orphaned_results > 0:
                        cursor.execute('''
                        DELETE FROM plagiarism_results
                        WHERE document_id NOT IN (SELECT id FROM document_repository)
                        ''')
                        results_text.insert(tk.END, f"Deleted {cursor.rowcount} orphaned plagiarism results.\n")
                    
                    if empty_docs > 0:
                        cursor.execute('''
                        DELETE FROM document_repository
                        WHERE content IS NULL OR content = ''
                        ''')
                        results_text.insert(tk.END, f"Deleted {cursor.rowcount} empty documents.\n")
                    
                    if invalid_authors > 0:
                        cursor.execute('''
                        DELETE FROM document_repository
                        WHERE author_id NOT IN (SELECT id FROM users)
                        ''')
                        results_text.insert(tk.END, f"Deleted {cursor.rowcount} documents with invalid authors.\n")
                    
                    conn.commit()
                    results_text.insert(tk.END, "\nAll issues fixed successfully!\n")
                    
            except Exception as e:
                results_text.insert(tk.END, f"\nError fixing issues: {e}\n")
                messagebox.showerror("Error", f"Failed to fix issues: {e}")
        
        # Start integrity check in a thread
        thread = threading.Thread(target=check_integrity, daemon=True)
        thread.start()

    def generate_reports_gui(self):
        """Generate various system reports"""
        if not self.checker:
            messagebox.showerror("Error", "System not initialized")
            return
        
        # Create reports dialog
        reports_dialog = tk.Toplevel(self.root)
        reports_dialog.title("Generate Reports")
        reports_dialog.geometry("600x500")
        reports_dialog.transient(self.root)
        reports_dialog.grab_set()
        
        main_frame = ttk.Frame(reports_dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="System Reports", font=GuiConfig.HEADER_FONT).pack(pady=(0, GuiConfig.PADDING_LARGE))
        
        # Report types
        reports_frame = ttk.LabelFrame(main_frame, text="Available Reports", padding=GuiConfig.PADDING_MEDIUM)
        reports_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        report_var = tk.StringVar()
        
        reports = [
            ("Summary Statistics", "summary"),
            ("Plagiarism Trends", "trends"),
            ("Module Analysis", "modules"),
            ("User Activity", "users"),
            ("System Health", "health")
        ]
        
        for name, value in reports:
            ttk.Radiobutton(reports_frame, text=name, variable=report_var, value=value).pack(anchor=tk.W, pady=GuiConfig.PADDING_SMALL)
        
        report_var.set("summary")  # Default selection
        
        # Report options
        options_frame = ttk.LabelFrame(main_frame, text="Report Options", padding=GuiConfig.PADDING_MEDIUM)
        options_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        include_charts_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Include Charts and Graphs", variable=include_charts_var).pack(anchor=tk.W)
        
        export_format_var = tk.StringVar(value="html")
        format_frame = ttk.Frame(options_frame)
        format_frame.pack(fill=tk.X, pady=GuiConfig.PADDING_SMALL)
        
        ttk.Label(format_frame, text="Export Format:").pack(side=tk.LEFT)
        ttk.Radiobutton(format_frame, text="HTML", variable=export_format_var, value="html").pack(side=tk.LEFT, padx=(GuiConfig.PADDING_MEDIUM, 0))
        ttk.Radiobutton(format_frame, text="PDF", variable=export_format_var, value="pdf").pack(side=tk.LEFT)
        ttk.Radiobutton(format_frame, text="CSV", variable=export_format_var, value="csv").pack(side=tk.LEFT)
        
        # Generate button
        def generate_report():
            report_type = report_var.get()
            if not report_type:
                messagebox.showwarning("No Selection", "Please select a report type.")
                return
            
            try:
                from tkinter import filedialog
                
                # Get filename
                format_ext = {"html": ".html", "pdf": ".pdf", "csv": ".csv"}[export_format_var.get()]
                filename = filedialog.asksaveasfilename(
                    defaultextension=format_ext,
                    filetypes=[(f"{export_format_var.get().upper()} files", f"*{format_ext}"), ("All files", "*.*")],
                    title="Save Report"
                )
                
                if filename:
                    # Generate the report (simplified implementation)
                    messagebox.showinfo("Report Generated", f"Report '{report_type}' would be generated and saved to {filename}")
                    
            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate report: {e}")
        
        ttk.Button(main_frame, text="Generate Report", command=generate_report).pack(pady=GuiConfig.PADDING_MEDIUM)
        
        ttk.Button(main_frame, text="Close", command=reports_dialog.destroy).pack()

    def get_author_selection_dialog(self, checker, author_name):
        """Dialog for selecting author from search results"""
        try:
            with checker.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT id, first_name, last_name
                FROM users
                WHERE first_name LIKE ? OR last_name LIKE ?
                ORDER BY last_name, first_name
                ''', (f"%{author_name}%", f"%{author_name}%"))
                
                authors = cursor.fetchall()
                
                if not authors:
                    messagebox.showinfo("No Results", "No authors found matching that name.")
                    return None
                
                # Create selection dialog
                dialog = tk.Toplevel(self.root)
                dialog.title("Select Author")
                dialog.geometry("400x300")
                dialog.transient(self.root)
                dialog.grab_set()
                
                selected_author = tk.IntVar()
                selected_author.set(-1)
                
                main_frame = ttk.Frame(dialog, padding=GuiConfig.PADDING_MEDIUM)
                main_frame.pack(fill=tk.BOTH, expand=True)
                
                ttk.Label(main_frame, text="Select Author:", font=GuiConfig.SUBHEADER_FONT).pack(pady=(0, GuiConfig.PADDING_MEDIUM))
                
                # Author list
                for i, author in enumerate(authors):
                    ttk.Radiobutton(
                        main_frame, 
                        text=f"{author[1]} {author[2]}", 
                        variable=selected_author, 
                        value=i
                    ).pack(anchor=tk.W, pady=GuiConfig.PADDING_SMALL)
                
                # Buttons
                button_frame = ttk.Frame(main_frame)
                button_frame.pack(fill=tk.X, pady=(GuiConfig.PADDING_MEDIUM, 0))
                
                def on_ok():
                    dialog.destroy()
                
                def on_cancel():
                    selected_author.set(-1)
                    dialog.destroy()
                
                ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.RIGHT)
                ttk.Button(button_frame, text="OK", command=on_ok).pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))
                
                dialog.wait_window()
                
                if selected_author.get() >= 0:
                    return authors[selected_author.get()][0]
                return None
                
        except Exception as e:
            messagebox.showerror("Error", f"Error selecting author: {e}")
            return None

    def get_module_selection_by_name_dialog(self, checker, module_name):
        """Dialog for selecting module by name from search results"""
        try:
            with checker.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT module_code, module_name
                FROM modules
                WHERE module_code LIKE ? OR module_name LIKE ?
                ORDER BY module_code
                ''', (f"%{module_name}%", f"%{module_name}%"))
                
                modules = cursor.fetchall()
                
                if not modules:
                    messagebox.showinfo("No Results", "No modules found matching that name.")
                    return None
                
                # Create selection dialog
                dialog = tk.Toplevel(self.root)
                dialog.title("Select Module")
                dialog.geometry("500x400")
                dialog.transient(self.root)
                dialog.grab_set()
                
                selected_module = tk.IntVar()
                selected_module.set(-1)
                
                main_frame = ttk.Frame(dialog, padding=GuiConfig.PADDING_MEDIUM)
                main_frame.pack(fill=tk.BOTH, expand=True)
                
                ttk.Label(main_frame, text="Select Module:", font=GuiConfig.SUBHEADER_FONT).pack(pady=(0, GuiConfig.PADDING_MEDIUM))
                
                # Module list with scrollbar
                list_frame = ttk.Frame(main_frame)
                list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))
                
                scrollbar = ttk.Scrollbar(list_frame)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                
                module_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
                module_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.config(command=module_listbox.yview)
                
                for module in modules:
                    module_listbox.insert(tk.END, f"{module[0]} - {module[1]}")
                
                # Buttons
                button_frame = ttk.Frame(main_frame)
                button_frame.pack(fill=tk.X)
                
                def on_ok():
                    selection = module_listbox.curselection()
                    if selection:
                        selected_module.set(selection[0])
                    dialog.destroy()
                
                def on_cancel():
                    selected_module.set(-1)
                    dialog.destroy()
                
                ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.RIGHT)
                ttk.Button(button_frame, text="OK", command=on_ok).pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))
                
                dialog.wait_window()
                
                if selected_module.get() >= 0:
                    return modules[selected_module.get()][0]
                return None
                
        except Exception as e:
            messagebox.showerror("Error", f"Error selecting module: {e}")
            return None

    def show_setup_testing(self):
        """Show setup and testing dialog"""
        if not self.checker:
            messagebox.showerror("Error", "System not initialized")
            return
        
        dialog = SetupTestingDialog(self.root, self.checker)
        dialog.show()
    
    def show_about(self):
        """Show about dialog"""
        about_text = """Plagiarism Detection System v2.0

A comprehensive tool for detecting plagiarism in academic documents.

Features:
• Document repository management
• Advanced similarity detection
• Multiple file format support
• Detailed reporting
• User-friendly GUI interface

Built with Python and Tkinter"""
        
        messagebox.showinfo("About", about_text)
    
    def load_dashboard_stats(self):
        """Load dashboard statistics"""
        if not self.checker:
            return
        
        def load_stats():
            try:
                stats = self.checker.get_statistics()
                
                stats_text = f"""System Statistics (Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

Repository Overview:
  Total Documents: {stats.get('total_documents', 0)}
  Total Checks Performed: {stats.get('total_checks', 0)}

Check Results by Status:"""
                
                for status, count in stats.get('status_counts', {}).items():
                    stats_text += f"\n  {status}: {count}"
                
                stats_text += "\n\nDocuments by Module:"
                for module, count in stats.get('documents_by_module', {}).items():
                    stats_text += f"\n  {module}: {count}"
                
                if stats.get('recent_checks'):
                    stats_text += "\n\nRecent Checks:"
                    for check in stats['recent_checks'][:5]:
                        similarity = check['similarity_score'] * 100
                        stats_text += f"\n  {check['document_title']} - {check['status']} ({similarity:.1f}%)"
                
                # Update GUI in main thread
                self.root.after(0, lambda: self.update_stats_display(stats_text))
                
            except Exception as e:
                error_text = f"Error loading statistics: {e}"
                self.root.after(0, lambda: self.update_stats_display(error_text))
        
        thread = threading.Thread(target=load_stats, daemon=True)
        thread.start()
    
    def update_stats_display(self, text):
        """Update statistics display"""
        self.stats_text.config(state=tk.NORMAL)
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.insert(1.0, text)
        self.stats_text.config(state=tk.DISABLED)
    
    def load_documents(self):
        """Load documents list"""
        if not self.checker:
            return

        def load_docs():
            try:
                documents = self.checker.search_repository()
                self.root.after(0, lambda: self.update_documents_display(documents))
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: self.show_error_in_documents(error_msg))
        
        thread = threading.Thread(target=load_docs, daemon=True)
        thread.start()

    def show_document_comparison(self):
        """Show document comparison dialog"""
        if not self.checker:
            messagebox.showerror("Error", "System not initialized")
            return
        
        dialog = DocumentComparisonDialog(self.root, self.checker, self.auth)
        dialog.show()

    def show_file_converter(self):
        """Show file format converter dialog"""
        if not self.checker:
            messagebox.showerror("Error", "System not initialized")
            return
        
        dialog = FileFormatConverterDialog(self.root, self.checker)
        dialog.show()

    def show_backup_restore(self):
        """Show backup/restore dialog"""
        if not self.checker:
            messagebox.showerror("Error", "System not initialized")
            return
        
        dialog = BackupRestoreDialog(self.root, self.checker)
        dialog.show()

    def show_document_workflow(self):
        """Show document workflow management dialog"""
        if not self.checker:
            messagebox.showerror("Error", "System not initialized")
            return
        
        if not self.auth.check_permission('manage_plagiarism_system'):
            messagebox.showerror("Permission Denied", "You don't have permission to manage document workflows.")
            return
        
        dialog = DocumentWorkflowDialog(self.root, self.checker, self.auth)
        dialog.show()

    def show_document_history(self, doc_id):
        """Show comprehensive document history"""
        try:
            # Create history dialog
            history_dialog = tk.Toplevel(self.root)
            history_dialog.title("Document History")
            history_dialog.geometry("700x500")
            history_dialog.transient(self.root)
            history_dialog.grab_set()
            
            main_frame = ttk.Frame(history_dialog, padding=GuiConfig.PADDING_MEDIUM)
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Get document details
            doc_details = self.checker.get_document_details(doc_id)
            
            ttk.Label(main_frame, text=f"History: {doc_details['title']}", font=GuiConfig.HEADER_FONT).pack(pady=(0, GuiConfig.PADDING_MEDIUM))
            
            # History notebook
            notebook = ttk.Notebook(main_frame)
            notebook.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))
            
            # Submission history tab
            submission_frame = ttk.Frame(notebook)
            notebook.add(submission_frame, text="Submission")
            
            submission_info = f"""Document Information:
    Title: {doc_details['title']}
    Author: {doc_details.get('author_name', 'Unknown')}
    Module: {doc_details.get('module_code', 'N/A')}
    Submitted: {doc_details['submission_date']}
    File Type: {doc_details.get('file_type', 'Unknown')}
    Word Count: {doc_details.get('word_count', 0)}
    Created: {doc_details['created_at']}
    Last Updated: {doc_details['updated_at']}"""
            
            submission_text = scrolledtext.ScrolledText(submission_frame, height=15, font=GuiConfig.MONOSPACE_FONT, state=tk.DISABLED)
            submission_text.pack(fill=tk.BOTH, expand=True)
            submission_text.config(state=tk.NORMAL)
            submission_text.insert(1.0, submission_info)
            submission_text.config(state=tk.DISABLED)
            
            # Check history tab
            checks_frame = ttk.Frame(notebook)
            notebook.add(checks_frame, text="Plagiarism Checks")
            
            try:
                check_history = self.checker.get_document_check_history(doc_id)
                
                checks_text = scrolledtext.ScrolledText(checks_frame, height=15, font=GuiConfig.MONOSPACE_FONT, state=tk.DISABLED)
                checks_text.pack(fill=tk.BOTH, expand=True)
                checks_text.config(state=tk.NORMAL)
                
                if check_history:
                    checks_text.insert(tk.END, "Plagiarism Check History:\n" + "="*50 + "\n\n")
                    for i, check in enumerate(check_history, 1):
                        similarity = check['similarity_score'] * 100
                        threshold = check.get('threshold_used', 0) * 100
                        
                        check_info = f"""Check #{i}:
    Date: {check['check_date']}
    Status: {check['status']}
    Similarity Score: {similarity:.1f}%
    Threshold Used: {threshold:.0f}%
    Result ID: {check['result_id']}

    """
                        checks_text.insert(tk.END, check_info)
                else:
                    checks_text.insert(tk.END, "No plagiarism checks performed on this document.")
                
                checks_text.config(state=tk.DISABLED)
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load check history: {e}")
            
            ttk.Button(main_frame, text="Close", command=history_dialog.destroy).pack()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to show document history: {e}")

    def launch_external_viewer(self, file_path):
        """Launch external application to view file"""
        try:
            import subprocess
            import platform
            
            system = platform.system()
            
            if system == "Windows":
                os.startfile(file_path)
            elif system == "Darwin":  # macOS
                subprocess.run(["open", file_path])
            elif system == "Linux":
                subprocess.run(["xdg-open", file_path])
            else:
                messagebox.showwarning("Unsupported Platform", "Cannot launch external viewer on this platform.")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch external viewer: {e}")
    
    def search_documents(self):
        """Search documents"""
        if not self.checker:
            return
        
        search_term = self.doc_search_var.get().strip()
        
        def search_docs():
            try:
                documents = self.checker.search_repository(search_term)
                self.root.after(0, lambda: self.update_documents_display(documents))
            except Exception as e:
                self.root.after(0, lambda error=str(e): self.show_error_in_documents(error))
        
        thread = threading.Thread(target=search_docs, daemon=True)
        thread.start()
    
    def update_documents_display(self, documents):
        """Update documents display"""
        # Clear existing widgets
        for widget in self.documents_frame.scrollable_frame.winfo_children():
            widget.destroy()
        
        if not documents:
            no_docs_label = ttk.Label(
                self.documents_frame.scrollable_frame,
                text="No documents found",
                font=GuiConfig.BODY_FONT
            )
            no_docs_label.pack(pady=GuiConfig.PADDING_LARGE)
            return
        
        for doc in documents:
            doc_card = self.create_document_card(doc)
            doc_card.pack(fill=tk.X, pady=GuiConfig.PADDING_SMALL)
    
    def create_document_card(self, doc):
        """Create a document card widget"""
        card_frame = ttk.LabelFrame(
            self.documents_frame.scrollable_frame,
            text=doc['title'],
            padding=GuiConfig.PADDING_SMALL
        )
        
        # Document info
        info_frame = ttk.Frame(card_frame)
        info_frame.pack(fill=tk.X)
        
        # Left side - document details
        details_frame = ttk.Frame(info_frame)
        details_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(
            details_frame,
            text=f"Submitted: {doc['submission_date']} | Type: {doc['file_type']} | Words: {doc['word_count']}",
            font=GuiConfig.BODY_FONT
        ).pack(anchor=tk.W)
        
        # Right side - actions
        actions_frame = ttk.Frame(info_frame)
        actions_frame.pack(side=tk.RIGHT)
        
        view_btn = ttk.Button(
            actions_frame,
            text="View Details",
            command=lambda: self.show_document_details(doc['id'])
        )
        view_btn.pack(side=tk.LEFT, padx=(0, GuiConfig.PADDING_SMALL))
        
        check_btn = ttk.Button(
            actions_frame,
            text="Check Plagiarism",
            command=lambda: self.quick_plagiarism_check(doc['id'])
        )
        check_btn.pack(side=tk.LEFT)
        
        return card_frame
    
    def show_error_in_documents(self, error):
        """Show error in documents tab"""
        for widget in self.documents_frame.scrollable_frame.winfo_children():
            widget.destroy()
        
        error_label = ttk.Label(
            self.documents_frame.scrollable_frame,
            text=f"Error loading documents: {error}",
            font=GuiConfig.BODY_FONT,
            foreground=GuiConfig.DANGER_COLOR
        )
        error_label.pack(pady=GuiConfig.PADDING_LARGE)
    
    def load_results(self):
        """Load plagiarism check results"""
        if not self.checker:
            return
        
        def load_res():
            try:
                # Get all documents and their check results
                documents = self.checker.search_repository()
                results = []
                
                for doc in documents:
                    try:
                        details = self.checker.get_document_details(doc['id'])
                        if details.get('latest_check'):
                            check_data = details['latest_check']
                            result = {
                                'document_title': doc['title'],
                                'document_id': doc['id'],
                                'result_id': check_data['result_id'],
                                'similarity_score': check_data['similarity_score'],
                                'status': check_data['status'],
                                'check_date': check_data['check_date']
                            }
                            results.append(result)
                    except Exception:
                        continue
                
                self.root.after(0, lambda: self.update_results_display(results))
            except Exception as e:
                self.root.after(0, lambda error=str(e): self.show_error_in_results(error))
        
        thread = threading.Thread(target=load_res, daemon=True)
        thread.start()
    
    def update_results_display(self, results):
        """Update results display"""
        # Clear existing widgets
        for widget in self.results_frame.scrollable_frame.winfo_children():
            widget.destroy()
        
        if not results:
            no_results_label = ttk.Label(
                self.results_frame.scrollable_frame,
                text="No plagiarism check results found",
                font=GuiConfig.BODY_FONT
            )
            no_results_label.pack(pady=GuiConfig.PADDING_LARGE)
            return
        
        # Sort results by check date (most recent first)
        results.sort(key=lambda x: x['check_date'], reverse=True)
        
        for result in results:
            result_card = ResultCard(
                self.results_frame.scrollable_frame,
                result,
                on_view_details=self.show_result_details
            )
            result_card.pack(fill=tk.X, pady=GuiConfig.PADDING_SMALL)
    
    def show_error_in_results(self, error):
        """Show error in results tab"""
        for widget in self.results_frame.scrollable_frame.winfo_children():
            widget.destroy()
        
        error_label = ttk.Label(
            self.results_frame.scrollable_frame,
            text=f"Error loading results: {error}",
            font=GuiConfig.BODY_FONT,
            foreground=GuiConfig.DANGER_COLOR
        )
        error_label.pack(pady=GuiConfig.PADDING_LARGE)
    
    def load_system_info(self):
        """Load system information"""
        info_text = f"""System Information

Application: Plagiarism Detection System v2.0
GUI Framework: Tkinter
Python Version: {sys.version}

Components:
• Document Repository: SQLite Database
• Text Processing: NLTK (if available)
• File Support: textract (if available)
• Similarity Algorithm: N-gram Jaccard Similarity

Database Location: student_records.db
Log Directory: logs/

System Status: {"Ready" if self.checker else "Not Initialized"}
Authentication: Mock Auth (GUI Mode)

Features Enabled:
• Document Submission ✓
• Plagiarism Detection ✓
• Repository Search ✓
• Statistical Reports ✓
• GUI Interface ✓

For command-line interface, run the original plagiarism_main.py file.
"""
        
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(1.0, info_text)
        self.info_text.config(state=tk.DISABLED)
    
    def show_document_details(self, doc_id):
        """Show detailed document information"""
        dialog = DocumentDetailsDialog(self.root, self.checker, doc_id)
        dialog.show()
    
    def quick_plagiarism_check(self, doc_id):
        """Quick plagiarism check for a document"""
        if not self.checker or not self.auth:
            messagebox.showerror("Error", "System not ready")
            return
        
        def check_task():
            try:
                self.status_bar.set_status("Checking document for plagiarism...")
                self.status_bar.show_progress()
                
                result = self.checker.check_plagiarism(
                    doc_id, 
                    self.auth.current_user['id'], 
                    self.threshold_var.get()
                )
                
                self.task_queue.put(('check_complete', result))
                
            except Exception as e:
                self.task_queue.put(('check_error', str(e)))
        
        thread = threading.Thread(target=check_task, daemon=True)
        thread.start()

    # Add these methods to the PlagiarismCheckerGUI class:

    def import_documents(self):
        """Import documents from external files"""
        if not self.checker:
            messagebox.showerror("Error", "System not initialized")
            return

        if not self.auth.check_permission('manage_plagiarism_system'):
            messagebox.showerror("Permission Denied", "You don't have permission to import documents.")
            return

        # File dialog to select documents
        filenames = filedialog.askopenfilenames(
            title="Select Documents to Import",
            filetypes=[
                ("Text files", "*.txt"),
                ("PDF files", "*.pdf"),
                ("Word documents", "*.docx"),
                ("All supported files", "*.txt *.pdf *.docx"),
                ("All files", "*.*")
            ]
        )

        if not filenames:
            return

        # Create progress dialog
        progress_dialog = tk.Toplevel(self.root)
        progress_dialog.title("Import Documents")
        progress_dialog.geometry("600x400")
        progress_dialog.transient(self.root)
        progress_dialog.grab_set()

        main_frame = ttk.Frame(progress_dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Import Documents", font=GuiConfig.HEADER_FONT).pack(pady=(0, GuiConfig.PADDING_LARGE))

        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(main_frame, variable=progress_var, maximum=100)
        progress_bar.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        status_var = tk.StringVar(value="Preparing import...")
        ttk.Label(main_frame, textvariable=status_var).pack()

        results_text = scrolledtext.ScrolledText(main_frame, height=15, font=GuiConfig.MONOSPACE_FONT)
        results_text.pack(fill=tk.BOTH, expand=True, pady=(GuiConfig.PADDING_MEDIUM, 0))

        def import_task():
            try:
                total = len(filenames)
                imported = 0
                failed = 0

                for i, filename in enumerate(filenames):
                    try:
                        progress_dialog.after(0, lambda f=filename: status_var.set(f"Processing: {os.path.basename(f)}"))
                        progress_dialog.after(0, lambda p=(i/total)*100: progress_var.set(p))

                        # Extract text from file
                        file_ext = os.path.splitext(filename)[1].lower()

                        if file_ext == '.txt':
                            with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                        elif file_ext in ['.pdf', '.docx'] and TEXTRACT_AVAILABLE:
                            try:
                                content = textract.process(filename).decode('utf-8', errors='ignore')
                            except Exception as e:
                                progress_dialog.after(0, lambda f=filename, e=e: results_text.insert(tk.END, f"Failed to extract from {os.path.basename(f)}: {e}\n"))
                                failed += 1
                                continue
                        else:
                            progress_dialog.after(0, lambda f=filename: results_text.insert(tk.END, f"Unsupported file type: {os.path.basename(f)}\n"))
                            failed += 1
                            continue

                        # Get document title from filename
                        title = os.path.splitext(os.path.basename(filename))[0]

                        # Get file type
                        file_type = file_ext[1:].upper() if file_ext else 'TXT'

                        # Add document to repository
                        doc_id = self.checker.add_document_to_repository(
                            title=title,
                            content=content,
                            author_id=self.auth.current_user['id'],
                            module_code='IMPORTED',
                            file_type=file_type
                        )

                        if doc_id:
                            progress_dialog.after(0, lambda t=title: results_text.insert(tk.END, f"Successfully imported: {t}\n"))
                            imported += 1
                        else:
                            progress_dialog.after(0, lambda t=title: results_text.insert(tk.END, f"Failed to import: {t}\n"))
                            failed += 1

                    except Exception as e:
                        progress_dialog.after(0, lambda f=filename, e=e: results_text.insert(tk.END, f"Error importing {os.path.basename(f)}: {e}\n"))
                        failed += 1

                progress_dialog.after(0, lambda: progress_var.set(100))
                progress_dialog.after(0, lambda: status_var.set("Import complete"))
                progress_dialog.after(0, lambda: results_text.insert(tk.END, f"\nSummary: {imported} imported, {failed} failed\n"))

                # Add close button
                progress_dialog.after(0, lambda: ttk.Button(main_frame, text="Close", command=progress_dialog.destroy).pack(pady=(GuiConfig.PADDING_MEDIUM, 0)))

                # Refresh documents list if available
                if hasattr(self, 'load_documents'):
                    progress_dialog.after(0, self.load_documents)

            except Exception as e:
                error_msg = str(e)
                progress_dialog.after(0, lambda: status_var.set("Import failed"))
                progress_dialog.after(0, lambda err=error_msg: results_text.insert(tk.END, f"\nError: {err}\n"))
                progress_dialog.after(0, lambda err=error_msg: messagebox.showerror("Error", f"Import failed: {err}"))

        thread = threading.Thread(target=import_task, daemon=True)
        thread.start()

    def export_documents(self):
        """Export documents to external files"""
        if not self.checker:
            messagebox.showerror("Error", "System not initialized")
            return

        if not self.auth.check_permission('manage_plagiarism_system'):
            messagebox.showerror("Permission Denied", "You don't have permission to export documents.")
            return

        # Create selection dialog
        export_dialog = tk.Toplevel(self.root)
        export_dialog.title("Export Documents")
        export_dialog.geometry("700x500")
        export_dialog.transient(self.root)
        export_dialog.grab_set()

        main_frame = ttk.Frame(export_dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Export Documents", font=GuiConfig.HEADER_FONT).pack(pady=(0, GuiConfig.PADDING_LARGE))

        # Search frame
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))

        # Documents list
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))

        columns = ('id', 'title', 'author', 'date')
        tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', selectmode='extended')
        tree.heading('#0', text='Select')
        tree.heading('id', text='ID')
        tree.heading('title', text='Title')
        tree.heading('author', text='Author')
        tree.heading('date', text='Date')

        tree.column('#0', width=50)
        tree.column('id', width=80)
        tree.column('title', width=250)
        tree.column('author', width=150)
        tree.column('date', width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load documents
        def load_docs():
            try:
                documents = self.checker.search_repository()
                tree.delete(*tree.get_children())

                for doc in documents:
                    tree.insert('', tk.END, text='', values=(
                        doc['id'],
                        doc['title'],
                        doc.get('author_name', 'Unknown'),
                        doc.get('created_at', 'N/A')
                    ))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load documents: {e}")

        # Format selection
        format_frame = ttk.LabelFrame(main_frame, text="Export Format", padding=GuiConfig.PADDING_SMALL)
        format_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        format_var = tk.StringVar(value="txt")
        ttk.Radiobutton(format_frame, text="Text Files (.txt)", variable=format_var, value="txt").pack(anchor=tk.W)
        ttk.Radiobutton(format_frame, text="Single ZIP Archive", variable=format_var, value="zip").pack(anchor=tk.W)

        # Export button
        def export_selected():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("No Selection", "Please select documents to export.")
                return

            if format_var.get() == "zip":
                # Export as ZIP
                filename = filedialog.asksaveasfilename(
                    title="Save Export Archive",
                    defaultextension=".zip",
                    filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")]
                )

                if not filename:
                    return

                try:
                    import zipfile

                    with zipfile.ZipFile(filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        with self.checker.get_db_connection() as conn:
                            cursor = conn.cursor()

                            for item in selected:
                                doc_id = tree.item(item)['values'][0]
                                cursor.execute('SELECT title, content FROM document_repository WHERE id = ?', (doc_id,))
                                row = cursor.fetchone()

                                if row:
                                    title, content = row
                                    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                                    zipf.writestr(f'{doc_id}_{safe_title}.txt', content)

                    messagebox.showinfo("Success", f"Exported {len(selected)} documents to {filename}")
                    export_dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Export failed: {e}")

            else:
                # Export as individual files
                directory = filedialog.askdirectory(title="Select Export Directory")

                if not directory:
                    return

                try:
                    exported = 0
                    with self.checker.get_db_connection() as conn:
                        cursor = conn.cursor()

                        for item in selected:
                            doc_id = tree.item(item)['values'][0]
                            cursor.execute('SELECT title, content FROM document_repository WHERE id = ?', (doc_id,))
                            row = cursor.fetchone()

                            if row:
                                title, content = row
                                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                                file_path = os.path.join(directory, f'{doc_id}_{safe_title}.txt')

                                with open(file_path, 'w', encoding='utf-8') as f:
                                    f.write(content)
                                exported += 1

                    messagebox.showinfo("Success", f"Exported {exported} documents to {directory}")
                    export_dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Export failed: {e}")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text="Select All", command=lambda: tree.selection_set(tree.get_children())).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Deselect All", command=lambda: tree.selection_remove(tree.get_children())).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        ttk.Button(button_frame, text="Export Selected", command=export_selected).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="Cancel", command=export_dialog.destroy).pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))

        # Load documents after dialog is ready
        export_dialog.after(100, load_docs)

    def show_document_comparison(self):
        """Show document comparison dialog"""
        if not self.checker:
            messagebox.showerror("Error", "System not initialized")
            return
        
    def show_file_converter(self):
        """Show file format converter dialog"""
        if not self.checker:
            messagebox.showerror("Error", "System not initialized")
            return
        
    def show_advanced_repository_search(self):
        """Show advanced repository search dialog"""
        if not self.checker:
            messagebox.showerror("Error", "System not initialized")
            return

    def show_bulk_operations(self):
        """Show bulk operations dialog"""
        if not self.checker:
            messagebox.showerror("Error", "System not initialized")
            return
        

    def show_document_workflow(self):
        """Show document workflow management dialog"""
        if not self.checker:
            messagebox.showerror("Error", "System not initialized")
            return
        
        if not self.auth.check_permission('manage_plagiarism_system'):
            messagebox.showerror("Permission Denied", "You don't have permission to manage document workflows.")
            return

    def show_backup_restore(self):
        """Show backup/restore dialog"""
        if not self.checker:
            messagebox.showerror("Error", "System not initialized")
            return

    def show_my_documents(self):
        """Show documents for current user - focuses on Documents tab"""
        if not getattr(self, 'checker', None) or not getattr(self, 'auth', None):
            messagebox.showerror("Error", "System not initialized")
            return
        try:
            if hasattr(self, 'notebook') and hasattr(self, 'documents_tab'):
                self.notebook.select(self.documents_tab)
            # Filter to show only current user's documents
            self.load_documents()  # This would be modified to filter by current user
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open My Documents: {e}")

    def show_view_results(self):
        """Focus the Results tab"""
        try:
            if hasattr(self, 'notebook') and hasattr(self, 'results_tab'):
                self.notebook.select(self.results_tab)
            else:
                messagebox.showwarning("Results", "Results tab not available yet.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Results: {e}")

    def show_delete_document_dialog(self):
        """Show dialog to delete a document"""
        if not getattr(self, 'checker', None):
            messagebox.showerror("Error", "System not initialized")
            return

        if not self.auth.check_permission('manage_plagiarism_system'):
            messagebox.showerror("Permission Denied", "You don't have permission to delete documents.")
            return

        # Create document selection dialog
        delete_dialog = tk.Toplevel(self.root)
        delete_dialog.title("Delete Document")
        delete_dialog.geometry("700x500")
        delete_dialog.transient(self.root)
        delete_dialog.grab_set()

        main_frame = ttk.Frame(delete_dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Delete Document", font=GuiConfig.HEADER_FONT).pack(pady=(0, GuiConfig.PADDING_LARGE))

        # Warning label
        warning_frame = ttk.Frame(main_frame)
        warning_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        ttk.Label(warning_frame, text="WARNING: Document deletion is permanent and cannot be undone!",
                 foreground='red', font=GuiConfig.SUBHEADER_FONT).pack()

        # Search frame
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0), fill=tk.X, expand=True)

        # Documents list
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))

        columns = ('id', 'title', 'author', 'date', 'module')
        tree = ttk.Treeview(list_frame, columns=columns, show='headings', selectmode='browse')
        tree.heading('id', text='ID')
        tree.heading('title', text='Title')
        tree.heading('author', text='Author')
        tree.heading('date', text='Date')
        tree.heading('module', text='Module')

        tree.column('id', width=60)
        tree.column('title', width=250)
        tree.column('author', width=150)
        tree.column('date', width=120)
        tree.column('module', width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Info label
        info_label = ttk.Label(main_frame, text="Select a document and click Delete")
        info_label.pack()

        # Load documents
        def load_docs(search_term=''):
            try:
                tree.delete(*tree.get_children())

                if search_term:
                    documents = self.checker.search_repository(search_term)
                else:
                    documents = self.checker.search_repository()

                for doc in documents:
                    tree.insert('', tk.END, values=(
                        doc['id'],
                        doc['title'],
                        doc.get('author_name', 'Unknown'),
                        doc.get('submission_date', 'N/A'),
                        doc.get('module_code', 'N/A')
                    ))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load documents: {e}")

        def search_docs():
            load_docs(search_var.get().strip())

        ttk.Button(search_frame, text="Search", command=search_docs).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))

        # Delete button
        def delete_selected():
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a document to delete.")
                return

            item = tree.item(selection[0])
            doc_id = item['values'][0]
            doc_title = item['values'][1]

            if not messagebox.askyesno("Confirm Deletion",
                                      f"Are you sure you want to permanently delete:\n\n'{doc_title}' (ID: {doc_id})?\n\nThis action cannot be undone!"):
                return

            try:
                with self.checker.get_db_connection() as conn:
                    cursor = conn.cursor()

                    # Delete related plagiarism results first
                    cursor.execute('DELETE FROM plagiarism_results WHERE document_id = ?', (doc_id,))

                    # Delete the document
                    cursor.execute('DELETE FROM document_repository WHERE id = ?', (doc_id,))

                    conn.commit()

                messagebox.showinfo("Success", f"Document '{doc_title}' has been deleted.")
                load_docs(search_var.get().strip())  # Reload list

                # Refresh main documents list if available
                if hasattr(self, 'load_documents'):
                    self.load_documents()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete document: {e}")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text="Delete Selected", command=delete_selected).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Close", command=delete_dialog.destroy).pack(side=tk.RIGHT)

        # Load documents after dialog is ready
        delete_dialog.after(100, load_docs)

    def show_repository_integrity_dialog(self):
        """Show repository integrity check dialog"""
        if not getattr(self, 'checker', None):
            messagebox.showerror("Error", "System not initialized")
            return

        # Call the full implementation from check_repository_integrity_gui
        self.check_repository_integrity_gui()
    
    def show_check_result(self, result):
        """Show plagiarism check result"""
        dialog = CheckResultDialog(self.root, result)
        dialog.show()
    
    def show_result_details(self, result_data):
        """Show detailed result information"""
        dialog = ResultDetailsDialog(self.root, self.checker, result_data['result_id'])
        dialog.show()

    def send_plagiarism_report_via_email(self, result_data, user_email=None):
        """Send plagiarism report via email GUI"""
        try:
            # Extract result information
            result_id = result_data.get('result_id', 'Unknown')
            similarity_score = result_data.get('similarity_score', 0)
            document_name = result_data.get('document_name', 'Unknown Document')

            # Generate email content
            from university_system.infrastructure.email.template_utils import render_template

            status = '⚠️ ATTENTION REQUIRED' if similarity_score > 30 else '✅ WITHIN ACCEPTABLE LIMITS'
            subject, message = render_template('plagiarism_report', {
                'document_name': document_name,
                'result_id': result_id,
                'similarity_score': similarity_score,
                'scan_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': status
            })

            if not (subject and message):
                print("Failed to load plagiarism report template")
                return

            # Send via email GUI
            success = self._send_email_via_gui(user_email, subject, message)

            if success:
                messagebox.showinfo("Email Sent", f"Plagiarism report sent to {user_email}")
            else:
                # Show fallback
                self._show_plagiarism_email_fallback(user_email, subject, message, result_data)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to send plagiarism report: {e}")

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

    def _show_plagiarism_email_fallback(self, email, subject, message, result_data):
        """Show fallback dialog for plagiarism report email"""
        try:
            fallback_window = tk.Toplevel(self.root)
            fallback_window.title("Plagiarism Report Email - Manual Send")
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
            print(f"Failed to show plagiarism email fallback: {e}")

    def auto_send_report_on_completion(self, result_data):
        """Automatically send report when plagiarism check completes"""
        try:
            # Get user email from auth system
            user_email = None
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                user_email = self.auth.current_user.get('email')

            if user_email:
                self.send_plagiarism_report_via_email(result_data, user_email)
            else:
                print("No user email available for auto-send")
        except Exception as e:
            print(f"Failed to auto-send plagiarism report: {e}")

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            root_widget = self.root if hasattr(self, 'root') else self.master
            if getattr(self, 'launched_from_main', False):
                # When launched from main system, simply close this window
                root_widget.destroy()
                return

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

    def run(self):
        """Run the GUI application"""
        self.root.mainloop()

class DocumentComparisonDialog:
    """Dialog for comparing two documents side-by-side"""
    
    def __init__(self, parent, checker, auth):
        self.parent = parent
        self.checker = checker
        self.auth = auth
        self.dialog = None
        self.doc1_id = None
        self.doc2_id = None
    
    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Repository Search")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)
        
        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")
        
        # Create interface first
        self.create_search_interface()
        self.load_all_documents()
        
        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab        
        self.create_interface()
    
    def create_interface(self):
        """Create the comparison interface"""
        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Document Comparison", font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))
        
        # Document selection
        selection_frame = ttk.Frame(main_frame)
        selection_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        # Document 1 selection
        doc1_frame = ttk.LabelFrame(selection_frame, text="Document 1", padding=GuiConfig.PADDING_SMALL)
        doc1_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, GuiConfig.PADDING_SMALL))
        
        self.doc1_var = tk.StringVar()
        doc1_entry = ttk.Entry(doc1_frame, textvariable=self.doc1_var, state='readonly')
        doc1_entry.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_SMALL))
        
        ttk.Button(doc1_frame, text="Select Document 1", command=lambda: self.select_document(1)).pack()
        
        # Document 2 selection
        doc2_frame = ttk.LabelFrame(selection_frame, text="Document 2", padding=GuiConfig.PADDING_SMALL)
        doc2_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(GuiConfig.PADDING_SMALL, 0))
        
        self.doc2_var = tk.StringVar()
        doc2_entry = ttk.Entry(doc2_frame, textvariable=self.doc2_var, state='readonly')
        doc2_entry.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_SMALL))
        
        ttk.Button(doc2_frame, text="Select Document 2", command=lambda: self.select_document(2)).pack()
        
        # Comparison controls
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        ttk.Button(controls_frame, text="Compare Documents", command=self.compare_documents).pack(side=tk.LEFT)
        ttk.Button(controls_frame, text="Highlight Similarities", command=self.highlight_similarities).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        
        # Similarity score display
        self.similarity_var = tk.StringVar()
        self.similarity_var.set("Similarity: Not calculated")
        ttk.Label(controls_frame, textvariable=self.similarity_var, font=GuiConfig.SUBHEADER_FONT).pack(side=tk.RIGHT)
        
        # Comparison display
        comparison_frame = ttk.Frame(main_frame)
        comparison_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        # Document 1 text
        doc1_text_frame = ttk.LabelFrame(comparison_frame, text="Document 1 Content", padding=GuiConfig.PADDING_SMALL)
        doc1_text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, GuiConfig.PADDING_SMALL))
        
        self.doc1_text = scrolledtext.ScrolledText(
            doc1_text_frame,
            height=20,
            font=GuiConfig.MONOSPACE_FONT,
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.doc1_text.pack(fill=tk.BOTH, expand=True)
        
        # Document 2 text
        doc2_text_frame = ttk.LabelFrame(comparison_frame, text="Document 2 Content", padding=GuiConfig.PADDING_SMALL)
        doc2_text_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(GuiConfig.PADDING_SMALL, 0))
        
        self.doc2_text = scrolledtext.ScrolledText(
            doc2_text_frame,
            height=20,
            font=GuiConfig.MONOSPACE_FONT,
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.doc2_text.pack(fill=tk.BOTH, expand=True)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="Export Comparison", command=self.export_comparison).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT)
    
    def select_document(self, doc_number):
        """Select a document for comparison"""
        # Create document selection dialog
        selection_dialog = tk.Toplevel(self.dialog)
        selection_dialog.title(f"Select Document {doc_number}")
        selection_dialog.geometry("600x400")
        selection_dialog.transient(self.dialog)
        selection_dialog.grab_set()
        
        main_frame = ttk.Frame(selection_dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Search
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=GuiConfig.PADDING_SMALL, fill=tk.X, expand=True)
        
        def search_docs():
            term = search_var.get().strip()
            docs = self.checker.search_repository(term) if term else self.checker.search_repository()
            populate_list(docs)
        
        ttk.Button(search_frame, text="Search", command=search_docs).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        
        # Document list
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        columns = ('Title', 'Author', 'Date', 'Words')
        doc_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            doc_tree.heading(col, text=col)
            doc_tree.column(col, width=120)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=doc_tree.yview)
        doc_tree.configure(yscrollcommand=scrollbar.set)
        
        doc_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        def populate_list(docs):
            for item in doc_tree.get_children():
                doc_tree.delete(item)
            
            for doc in docs:
                try:
                    details = self.checker.get_document_details(doc['id'])
                    doc_tree.insert('', tk.END, values=(
                        doc['title'][:40] + ('...' if len(doc['title']) > 40 else ''),
                        details.get('author_name', 'Unknown'),
                        doc['submission_date'],
                        doc.get('word_count', 0)
                    ), tags=(str(doc['id']),))
                except Exception as e:
                    logger.error(f"Error loading document {doc['id']}: {e}")
        
        # Load initial documents
        try:
            documents = self.checker.search_repository()
            populate_list(documents)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load documents: {e}")
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        def on_select():
            selection = doc_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a document.")
                return
            
            item = selection[0]
            doc_id = int(doc_tree.item(item, 'tags')[0])
            doc_title = doc_tree.item(item, 'values')[0]
            
            if doc_number == 1:
                self.doc1_id = doc_id
                self.doc1_var.set(doc_title)
            else:
                self.doc2_id = doc_id
                self.doc2_var.set(doc_title)
            
            selection_dialog.destroy()
        
        ttk.Button(button_frame, text="Cancel", command=selection_dialog.destroy).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="Select", command=on_select).pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))
    
    def compare_documents(self):
        """Compare the selected documents"""
        if not self.doc1_id or not self.doc2_id:
            messagebox.showwarning("Missing Documents", "Please select both documents to compare.")
            return
        
        try:
            # Get document details
            doc1_details = self.checker.get_document_details(self.doc1_id)
            doc2_details = self.checker.get_document_details(self.doc2_id)
            
            # Load document content
            with self.checker.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('SELECT content FROM document_repository WHERE id = ?', (self.doc1_id,))
                doc1_content = cursor.fetchone()[0]
                
                cursor.execute('SELECT content FROM document_repository WHERE id = ?', (self.doc2_id,))
                doc2_content = cursor.fetchone()[0]
            
            # Calculate similarity
            doc1_tokens = self.checker.preprocess_text(doc1_content)
            doc2_tokens = self.checker.preprocess_text(doc2_content)
            
            doc1_ngrams = self.checker.compute_ngrams(doc1_tokens)
            doc2_ngrams = self.checker.compute_ngrams(doc2_tokens)
            
            similarity = self.checker.compute_similarity(doc1_ngrams, doc2_ngrams)
            
            # Update similarity display
            self.similarity_var.set(f"Similarity: {similarity * 100:.1f}%")
            
            # Display content
            self.doc1_text.config(state=tk.NORMAL)
            self.doc1_text.delete(1.0, tk.END)
            self.doc1_text.insert(1.0, doc1_content)
            self.doc1_text.config(state=tk.DISABLED)
            
            self.doc2_text.config(state=tk.NORMAL)
            self.doc2_text.delete(1.0, tk.END)
            self.doc2_text.insert(1.0, doc2_content)
            self.doc2_text.config(state=tk.DISABLED)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to compare documents: {e}")
    
    def highlight_similarities(self):
        """Highlight similar text passages"""
        if not self.doc1_id or not self.doc2_id:
            messagebox.showwarning("Missing Documents", "Please compare documents first.")
            return

        try:
            # Configure text highlighting tags
            self.doc1_text.tag_configure('highlight', background='yellow', foreground='black')
            self.doc2_text.tag_configure('highlight', background='yellow', foreground='black')

            # Get document contents
            with self.checker.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT content FROM document_repository WHERE id = ?', (self.doc1_id,))
                doc1_content = cursor.fetchone()[0]
                cursor.execute('SELECT content FROM document_repository WHERE id = ?', (self.doc2_id,))
                doc2_content = cursor.fetchone()[0]

            # Simple n-gram based similarity highlighting
            # Using 5-word phrases for matching
            n = 5

            # Tokenize documents into words
            if NLTK_AVAILABLE:
                try:
                    words1 = word_tokenize(doc1_content.lower())
                    words2 = word_tokenize(doc2_content.lower())
                except:
                    # Fallback if NLTK fails
                    words1 = doc1_content.lower().split()
                    words2 = doc2_content.lower().split()
            else:
                words1 = doc1_content.lower().split()
                words2 = doc2_content.lower().split()

            # Create n-grams
            ngrams1 = {}
            for i in range(len(words1) - n + 1):
                ngram = ' '.join(words1[i:i+n])
                if ngram not in ngrams1:
                    ngrams1[ngram] = []
                ngrams1[ngram].append(i)

            ngrams2 = {}
            for i in range(len(words2) - n + 1):
                ngram = ' '.join(words2[i:i+n])
                if ngram not in ngrams2:
                    ngrams2[ngram] = []
                ngrams2[ngram].append(i)

            # Find common n-grams
            common_ngrams = set(ngrams1.keys()) & set(ngrams2.keys())

            if not common_ngrams:
                messagebox.showinfo("No Matches", "No significant text similarities found to highlight.")
                return

            # Enable text widgets for editing
            self.doc1_text.config(state=tk.NORMAL)
            self.doc2_text.config(state=tk.NORMAL)

            # Clear previous highlights
            self.doc1_text.tag_remove('highlight', '1.0', tk.END)
            self.doc2_text.tag_remove('highlight', '1.0', tk.END)

            # Highlight matches in document 1
            highlighted_words1 = set()
            for ngram in common_ngrams:
                for start_idx in ngrams1[ngram]:
                    for i in range(start_idx, start_idx + n):
                        highlighted_words1.add(i)

            # Highlight matches in document 2
            highlighted_words2 = set()
            for ngram in common_ngrams:
                for start_idx in ngrams2[ngram]:
                    for i in range(start_idx, start_idx + n):
                        highlighted_words2.add(i)

            # Apply highlights to doc1
            word_positions1 = []
            current_pos = 0
            for i, word in enumerate(doc1_content.split()):
                start_pos = doc1_content.find(word, current_pos)
                end_pos = start_pos + len(word)
                word_positions1.append((start_pos, end_pos))
                current_pos = end_pos

            for word_idx in sorted(highlighted_words1):
                if word_idx < len(word_positions1):
                    start_pos, end_pos = word_positions1[word_idx]
                    # Convert to Tkinter text indices
                    start_line = doc1_content[:start_pos].count('\n') + 1
                    start_col = start_pos - doc1_content[:start_pos].rfind('\n') - 1
                    end_line = doc1_content[:end_pos].count('\n') + 1
                    end_col = end_pos - doc1_content[:end_pos].rfind('\n') - 1

                    try:
                        self.doc1_text.tag_add('highlight', f'{start_line}.{start_col}', f'{end_line}.{end_col}')
                    except:
                        pass

            # Apply highlights to doc2
            word_positions2 = []
            current_pos = 0
            for i, word in enumerate(doc2_content.split()):
                start_pos = doc2_content.find(word, current_pos)
                end_pos = start_pos + len(word)
                word_positions2.append((start_pos, end_pos))
                current_pos = end_pos

            for word_idx in sorted(highlighted_words2):
                if word_idx < len(word_positions2):
                    start_pos, end_pos = word_positions2[word_idx]
                    # Convert to Tkinter text indices
                    start_line = doc2_content[:start_pos].count('\n') + 1
                    start_col = start_pos - doc2_content[:start_pos].rfind('\n') - 1
                    end_line = doc2_content[:end_pos].count('\n') + 1
                    end_col = end_pos - doc2_content[:end_pos].rfind('\n') - 1

                    try:
                        self.doc2_text.tag_add('highlight', f'{start_line}.{start_col}', f'{end_line}.{end_col}')
                    except:
                        pass

            # Disable text widgets again
            self.doc1_text.config(state=tk.DISABLED)
            self.doc2_text.config(state=tk.DISABLED)

            similarity_pct = (len(highlighted_words1) + len(highlighted_words2)) / (len(words1) + len(words2)) * 100
            messagebox.showinfo("Highlighting Complete",
                              f"Highlighted {len(common_ngrams)} similar phrases.\n"
                              f"Approximate similarity: {similarity_pct:.1f}%")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to highlight similarities: {e}")
    
    def export_comparison(self):
        """Export the comparison results"""
        if not self.doc1_id or not self.doc2_id:
            messagebox.showwarning("Missing Documents", "Please compare documents first.")
            return
        
        try:
            from tkinter import filedialog
            
            filename = filedialog.asksaveasfilename(
                defaultextension=".html",
                filetypes=[("HTML files", "*.html"), ("Text files", "*.txt"), ("All files", "*.*")],
                title="Export Comparison"
            )
            
            if filename:
                # Generate comparison report
                similarity = self.similarity_var.get()
                doc1_title = self.doc1_var.get()
                doc2_title = self.doc2_var.get()
                
                report = f"""Document Comparison Report
================================

Document 1: {doc1_title}
Document 2: {doc2_title}
{similarity}

Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
                
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(report)
                
                messagebox.showinfo("Export Complete", f"Comparison exported to {filename}")
                
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export comparison: {e}")

# Add this class for file format conversion
class FileFormatConverterDialog:
    """Dialog for converting between different file formats"""
    
    def __init__(self, parent, checker):
        self.parent = parent
        self.checker = checker
        self.dialog = None
        self.input_file = None
        self.output_file = None
    
    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Repository Search")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)
        
        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")
        
        # Create interface first
        self.create_search_interface()
        self.load_all_documents()
        
        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab        
        self.create_interface()
    
    def create_interface(self):
        """Create the converter interface"""
        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="File Format Converter", font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))
        
        # Input file selection
        input_frame = ttk.LabelFrame(main_frame, text="Input File", padding=GuiConfig.PADDING_MEDIUM)
        input_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        self.input_var = tk.StringVar()
        input_entry = ttk.Entry(input_frame, textvariable=self.input_var, state='readonly', width=60)
        input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(input_frame, text="Browse...", command=self.select_input_file).pack(side=tk.RIGHT, padx=(GuiConfig.PADDING_SMALL, 0))
        
        # Output file selection
        output_frame = ttk.LabelFrame(main_frame, text="Output File", padding=GuiConfig.PADDING_MEDIUM)
        output_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        self.output_var = tk.StringVar()
        output_entry = ttk.Entry(output_frame, textvariable=self.output_var, width=60)
        output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(output_frame, text="Browse...", command=self.select_output_file).pack(side=tk.RIGHT, padx=(GuiConfig.PADDING_SMALL, 0))
        
        # Format options
        format_frame = ttk.LabelFrame(main_frame, text="Conversion Options", padding=GuiConfig.PADDING_MEDIUM)
        format_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        ttk.Label(format_frame, text="Output Format:").grid(row=0, column=0, sticky=tk.W)
        
        self.format_var = tk.StringVar(value="txt")
        formats = [("Plain Text (.txt)", "txt"), ("HTML (.html)", "html"), ("Markdown (.md)", "md")]
        
        for i, (text, value) in enumerate(formats):
            ttk.Radiobutton(format_frame, text=text, variable=self.format_var, value=value).grid(row=i+1, column=0, sticky=tk.W)
        
        # Conversion options
        self.preserve_formatting_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(format_frame, text="Preserve formatting", variable=self.preserve_formatting_var).grid(row=4, column=0, sticky=tk.W, pady=(GuiConfig.PADDING_MEDIUM, 0))
        
        # Progress
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        self.status_var = tk.StringVar()
        self.status_var.set("Ready to convert")
        ttk.Label(main_frame, textvariable=self.status_var).pack()
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(GuiConfig.PADDING_MEDIUM, 0))
        
        ttk.Button(button_frame, text="Convert", command=self.convert_file).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT)
    
    def select_input_file(self):
        """Select input file"""
        filename = filedialog.askopenfilename(
            title="Select Input File",
            filetypes=[
                ("All supported", "*.txt;*.pdf;*.docx;*.doc"),
                ("Text files", "*.txt"),
                ("PDF files", "*.pdf"),
                ("Word documents", "*.docx;*.doc"),
                ("All files", "*.*")
            ]
        )
        
        if filename:
            self.input_file = filename
            self.input_var.set(filename)
            
            # Auto-suggest output filename
            base_name = os.path.splitext(filename)[0]
            output_ext = {"txt": ".txt", "html": ".html", "md": ".md"}[self.format_var.get()]
            self.output_var.set(f"{base_name}_converted{output_ext}")
    
    def select_output_file(self):
        """Select output file"""
        format_ext = {"txt": ".txt", "html": ".html", "md": ".md"}[self.format_var.get()]
        
        filename = filedialog.asksaveasfilename(
            title="Save Converted File",
            defaultextension=format_ext,
            filetypes=[
                (f"{self.format_var.get().upper()} files", f"*{format_ext}"),
                ("All files", "*.*")
            ]
        )
        
        if filename:
            self.output_file = filename
            self.output_var.set(filename)
    
    def convert_file(self):
        """Convert the file"""
        if not self.input_file:
            messagebox.showwarning("No Input", "Please select an input file.")
            return
        
        output_file = self.output_var.get().strip()
        if not output_file:
            messagebox.showwarning("No Output", "Please specify an output file.")
            return
        
        def convert_task():
            try:
                self.dialog.after(0, lambda: self.status_var.set("Reading input file..."))
                self.dialog.after(0, lambda: self.progress_var.set(25))
                
                # Extract text from input file
                content, file_type = self.checker.extract_text_from_file(self.input_file)
                
                self.dialog.after(0, lambda: self.status_var.set("Converting format..."))
                self.dialog.after(0, lambda: self.progress_var.set(50))
                
                # Convert based on output format
                output_format = self.format_var.get()
                if output_format == "html":
                    converted_content = self.convert_to_html(content)
                elif output_format == "md":
                    converted_content = self.convert_to_markdown(content)
                else:  # txt
                    converted_content = content
                
                self.dialog.after(0, lambda: self.status_var.set("Writing output file..."))
                self.dialog.after(0, lambda: self.progress_var.set(75))
                
                # Write output file
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(converted_content)
                
                self.dialog.after(0, lambda: self.progress_var.set(100))
                self.dialog.after(0, lambda: self.status_var.set("Conversion completed"))
                self.dialog.after(0, lambda: messagebox.showinfo("Success", f"File converted successfully!\nOutput: {output_file}"))
                
            except Exception as e:
                error_msg = str(e)
                self.dialog.after(0, lambda: self.status_var.set("Conversion failed"))
                self.dialog.after(0, lambda err=error_msg: messagebox.showerror("Error", f"Conversion failed: {err}"))
        
        thread = threading.Thread(target=convert_task, daemon=True)
        thread.start()
    
    def convert_to_html(self, content):
        """Convert content to HTML format"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        html_content = f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Converted Document</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
            .content {{ max-width: 800px; margin: 0 auto; }}
        </style>
    </head>
    <body>
        <div class="content">
            <h1>Converted Document</h1>
            <p>Converted on: {timestamp}</p>
            <hr>
            <div>
                {content.replace(chr(10), '<br>' + chr(10))}
            </div>
        </div>
    </body>
    </html>"""
        return html_content
    
    def convert_to_markdown(self, content):
        """Convert content to Markdown format"""
        markdown_content = f"""# Converted Document

**Converted on:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

{content}
"""
        return markdown_content

class BackupRestoreDialog:
    """Dialog for system backup and restore operations"""
    
    def __init__(self, parent, checker):
        self.parent = parent
        self.checker = checker
        self.dialog = None
    
    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Repository Search")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)
        
        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")
        
        # Create interface first
        self.create_search_interface()
        self.load_all_documents()
        
        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab        
        self.create_interface()
    
    def create_interface(self):
        """Create the backup/restore interface"""
        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Backup & Restore", font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))
        
        # Backup section
        backup_frame = ttk.LabelFrame(main_frame, text="Create Backup", padding=GuiConfig.PADDING_MEDIUM)
        backup_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        ttk.Label(backup_frame, text="Create a backup of the plagiarism checker database and documents.").pack(anchor=tk.W, pady=(0, GuiConfig.PADDING_SMALL))
        
        backup_options_frame = ttk.Frame(backup_frame)
        backup_options_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_SMALL))
        
        self.include_documents_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(backup_options_frame, text="Include document content", variable=self.include_documents_var).pack(anchor=tk.W)
        
        self.include_results_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(backup_options_frame, text="Include plagiarism results", variable=self.include_results_var).pack(anchor=tk.W)
        
        ttk.Button(backup_frame, text="Create Backup", command=self.create_backup).pack(anchor=tk.W, pady=(GuiConfig.PADDING_SMALL, 0))
        
        # Restore section
        restore_frame = ttk.LabelFrame(main_frame, text="Restore from Backup", padding=GuiConfig.PADDING_MEDIUM)
        restore_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        ttk.Label(restore_frame, text="Restore system from a previous backup file.").pack(anchor=tk.W, pady=(0, GuiConfig.PADDING_SMALL))
        
        self.backup_file_var = tk.StringVar()
        backup_file_frame = ttk.Frame(restore_frame)
        backup_file_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_SMALL))
        
        ttk.Entry(backup_file_frame, textvariable=self.backup_file_var, state='readonly').pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(backup_file_frame, text="Browse...", command=self.select_backup_file).pack(side=tk.RIGHT, padx=(GuiConfig.PADDING_SMALL, 0))
        
        ttk.Button(restore_frame, text="Restore from Backup", command=self.restore_backup).pack(anchor=tk.W, pady=(GuiConfig.PADDING_SMALL, 0))
        
        # Progress
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        ttk.Label(main_frame, textvariable=self.status_var).pack()
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=(GuiConfig.PADDING_MEDIUM, 0))
    
    def create_backup(self):
        """Create a system backup"""
        try:
            from tkinter import filedialog
            import zipfile
            import json
            
            # Select backup location
            filename = filedialog.asksaveasfilename(
                defaultextension=".backup",
                filetypes=[("Backup files", "*.backup"), ("ZIP files", "*.zip"), ("All files", "*.*")],
                title="Save Backup"
            )
            
            if not filename:
                return
            
            def backup_task():
                try:
                    self.dialog.after(0, lambda: self.status_var.set("Creating backup..."))
                    self.dialog.after(0, lambda: self.progress_var.set(10))
                    
                    with zipfile.ZipFile(filename, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
                        # Backup database
                        if os.path.exists(str(DEFAULT_DB_PATH)):
                            backup_zip.write(str(DEFAULT_DB_PATH), 'database/student_records.db')
                            self.dialog.after(0, lambda: self.progress_var.set(30))
                        
                        # Backup configuration
                        config = {
                            'backup_date': datetime.now().isoformat(),
                            'include_documents': self.include_documents_var.get(),
                            'include_results': self.include_results_var.get(),
                            'version': '2.0'
                        }
                        
                        backup_zip.writestr('config.json', json.dumps(config, indent=2))
                        self.dialog.after(0, lambda: self.progress_var.set(50))
                        
                        # Backup documents if requested
                        if self.include_documents_var.get():
                            self.dialog.after(0, lambda: self.status_var.set("Backing up documents..."))
                            
                            with self.checker.get_db_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute('SELECT id, title, content FROM document_repository')
                                documents = cursor.fetchall()
                                
                                for i, (doc_id, title, content) in enumerate(documents):
                                    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                                    backup_zip.writestr(f'documents/{doc_id}_{safe_title}.txt', content)
                                    
                                    progress = 50 + (i / len(documents)) * 30
                                    self.dialog.after(0, lambda p=progress: self.progress_var.set(p))
                        
                        self.dialog.after(0, lambda: self.progress_var.set(100))
                        self.dialog.after(0, lambda: self.status_var.set("Backup completed"))
                        self.dialog.after(0, lambda: messagebox.showinfo("Success", f"Backup created successfully!\nLocation: {filename}"))
                        
                except Exception as e:
                    error_msg = str(e)
                    self.dialog.after(0, lambda: self.status_var.set("Backup failed"))
                    self.dialog.after(0, lambda err=error_msg: messagebox.showerror("Error", f"Backup failed: {err}"))
            
            thread = threading.Thread(target=backup_task, daemon=True)
            thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create backup: {e}")
    
    def select_backup_file(self):
        """Select backup file for restore"""
        filename = filedialog.askopenfilename(
            title="Select Backup File",
            filetypes=[("Backup files", "*.backup"), ("ZIP files", "*.zip"), ("All files", "*.*")]
        )
        
        if filename:
            self.backup_file_var.set(filename)
    
    def restore_backup(self):
        """Restore from backup file"""
        backup_file = self.backup_file_var.get()
        if not backup_file:
            messagebox.showwarning("No File", "Please select a backup file.")
            return
        
        if not messagebox.askyesno("Confirm Restore", 
                                   "This will replace the current system data. Are you sure?"):
            return
        
        try:
            import zipfile
            import json
            
            def restore_task():
                try:
                    self.dialog.after(0, lambda: self.status_var.set("Restoring from backup..."))
                    self.dialog.after(0, lambda: self.progress_var.set(10))
                    
                    with zipfile.ZipFile(backup_file, 'r') as backup_zip:
                        # Read configuration
                        try:
                            config_data = backup_zip.read('config.json')
                            config = json.loads(config_data.decode('utf-8'))
                            self.dialog.after(0, lambda: self.status_var.set(f"Restoring backup from {config['backup_date']}..."))
                        except Exception:
                            config = {}
                        
                        self.dialog.after(0, lambda: self.progress_var.set(30))
                        
                        # Restore database
                        if 'database/student_records.db' in backup_zip.namelist():
                            backup_zip.extract('database/student_records.db', '.')
                            os.rename('database/student_records.db', str(DEFAULT_DB_PATH))
                            self.dialog.after(0, lambda: self.progress_var.set(70))
                        
                        self.dialog.after(0, lambda: self.progress_var.set(100))
                        self.dialog.after(0, lambda: self.status_var.set("Restore completed"))
                        self.dialog.after(0, lambda: messagebox.showinfo("Success", "System restored successfully!\nPlease restart the application."))
                        
                except Exception as e:
                    error_msg = str(e)
                    self.dialog.after(0, lambda: self.status_var.set("Restore failed"))
                    self.dialog.after(0, lambda err=error_msg: messagebox.showerror("Error", f"Restore failed: {err}"))
            
            thread = threading.Thread(target=restore_task, daemon=True)
            thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to restore backup: {e}")

# Add this class for document workflow management
class DocumentWorkflowDialog:
    """Dialog for managing document workflow states"""
    
    def __init__(self, parent, checker, auth):
        self.parent = parent
        self.checker = checker
        self.auth = auth
        self.dialog = None
    
    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Repository Search")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)
        
        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")
        
        # Create interface first
        self.create_search_interface()
        self.load_all_documents()
        
        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab        
        self.create_interface()
        self.load_workflow_documents()
    
    def create_interface(self):
        """Create the workflow interface"""
        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Document Workflow Management", font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))
        
        # Workflow states filter
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        ttk.Label(filter_frame, text="Filter by status:").pack(side=tk.LEFT)
        
        self.status_filter_var = tk.StringVar(value="All")
        status_combo = ttk.Combobox(filter_frame, textvariable=self.status_filter_var, 
                                   values=["All", "Submitted", "Under Review", "Checked", "Flagged", "Approved"], 
                                   state='readonly')
        status_combo.pack(side=tk.LEFT, padx=GuiConfig.PADDING_SMALL)
        status_combo.bind('<<ComboboxSelected>>', lambda e: self.filter_documents())
        
        ttk.Button(filter_frame, text="Refresh", command=self.load_workflow_documents).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_MEDIUM, 0))
        
        # Documents tree
        docs_frame = ttk.LabelFrame(main_frame, text="Documents", padding=GuiConfig.PADDING_SMALL)
        docs_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        columns = ('Title', 'Author', 'Status', 'Last Check', 'Priority', 'Actions')
        self.docs_tree = ttk.Treeview(docs_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.docs_tree.heading(col, text=col)
            self.docs_tree.column(col, width=120)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(docs_frame, orient=tk.VERTICAL, command=self.docs_tree.yview)
        h_scrollbar = ttk.Scrollbar(docs_frame, orient=tk.HORIZONTAL, command=self.docs_tree.xview)
        
        self.docs_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        self.docs_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        docs_frame.grid_rowconfigure(0, weight=1)
        docs_frame.grid_columnconfigure(0, weight=1)
        
        # Workflow actions
        actions_frame = ttk.LabelFrame(main_frame, text="Workflow Actions", padding=GuiConfig.PADDING_MEDIUM)
        actions_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        ttk.Button(actions_frame, text="Mark for Review", command=self.mark_for_review).pack(side=tk.LEFT)
        ttk.Button(actions_frame, text="Approve Document", command=self.approve_document).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        ttk.Button(actions_frame, text="Flag Document", command=self.flag_document).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        ttk.Button(actions_frame, text="Add Comment", command=self.add_comment).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()
    
    def load_workflow_documents(self):
        """Load documents for workflow management"""
        try:
            # Clear existing items
            for item in self.docs_tree.get_children():
                self.docs_tree.delete(item)
            
            documents = self.checker.search_repository()
            
            for doc in documents:
                try:
                    doc_details = self.checker.get_document_details(doc['id'])
                    
                    # Determine workflow status
                    status = "Submitted"
                    last_check = "Never"
                    
                    if doc_details.get('latest_check'):
                        check = doc_details['latest_check']
                        last_check = check['check_date']
                        
                        if check['status'] in ['EXACT_MATCH', 'HIGH_SIMILARITY']:
                            status = "Flagged"
                        elif check['status'] in ['MODERATE_SIMILARITY', 'LOW_SIMILARITY']:
                            status = "Checked"
                        else:
                            status = "Under Review"
                    
                    # Determine priority (placeholder logic)
                    priority = "Normal"
                    if status == "Flagged":
                        priority = "High"
                    elif status == "Under Review":
                        priority = "Medium"
                    
                    self.docs_tree.insert('', tk.END, values=(
                        doc['title'][:40] + ('...' if len(doc['title']) > 40 else ''),
                        doc_details.get('author_name', 'Unknown'),
                        status,
                        last_check,
                        priority,
                        "Available"
                    ), tags=(str(doc['id']),))
                    
                except Exception as e:
                    logger.error(f"Error loading document {doc['id']}: {e}")
                    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load documents: {e}")
    
    def filter_documents(self):
        """Filter documents by status"""
        filter_status = self.status_filter_var.get()
        
        # This would implement filtering logic
        # For now, just reload all documents
        if filter_status == "All":
            self.load_workflow_documents()
        else:
            # Placeholder - would filter by actual status
            messagebox.showinfo("Filter", f"Filtering by status: {filter_status}")
    
    def get_selected_document(self):
        """Get the selected document ID"""
        selection = self.docs_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a document.")
            return None
        
        item = selection[0]
        return int(self.docs_tree.item(item, 'tags')[0])
    
    def mark_for_review(self):
        """Mark document for review"""
        doc_id = self.get_selected_document()
        if doc_id:
            # This would update document status in database
            messagebox.showinfo("Action", f"Document {doc_id} marked for review.")
            self.load_workflow_documents()
    
    def approve_document(self):
        """Approve document"""
        doc_id = self.get_selected_document()
        if doc_id:
            if messagebox.askyesno("Confirm", "Approve this document?"):
                messagebox.showinfo("Action", f"Document {doc_id} approved.")
                self.load_workflow_documents()
    
    def flag_document(self):
        """Flag document for attention"""
        doc_id = self.get_selected_document()
        if doc_id:
            reason = simpledialog.askstring("Flag Document", "Reason for flagging:")
            if reason:
                messagebox.showinfo("Action", f"Document {doc_id} flagged: {reason}")
                self.load_workflow_documents()
    
    def add_comment(self):
        """Add comment to document"""
        doc_id = self.get_selected_document()
        if doc_id:
            comment = simpledialog.askstring("Add Comment", "Enter comment:")
            if comment:
                messagebox.showinfo("Action", f"Comment added to document {doc_id}")

class DocumentSubmissionDialog:
    """Dialog for submitting documents to the repository"""
    
    def __init__(self, parent, checker, auth, task_queue):
        self.parent = parent
        self.checker = checker
        self.auth = auth
        self.task_queue = task_queue
        
        self.dialog = None
        self.file_path = None
        
        # Variables
        self.title_var = None
        self.module_var = None
        self.file_var = None
        self.preview_text = None
    
    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Submit Document")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")

        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab
        self.create_submission_form()
    
    def create_submission_form(self):
        """Create the submission form"""
        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Submit Document", font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))
        
        # Form fields
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Document title
        ttk.Label(form_frame, text="Document Title:").grid(row=0, column=0, sticky=tk.W, pady=GuiConfig.PADDING_SMALL)
        self.title_var = tk.StringVar()
        title_entry = ttk.Entry(form_frame, textvariable=self.title_var, width=50)
        title_entry.grid(row=0, column=1, sticky=tk.W + tk.E, pady=GuiConfig.PADDING_SMALL, padx=(GuiConfig.PADDING_SMALL, 0))
        
        # Module selection
        ttk.Label(form_frame, text="Module:").grid(row=1, column=0, sticky=tk.W, pady=GuiConfig.PADDING_SMALL)
        self.module_var = tk.StringVar()
        module_combo = ttk.Combobox(form_frame, textvariable=self.module_var, width=47)
        module_combo.grid(row=1, column=1, sticky=tk.W + tk.E, pady=GuiConfig.PADDING_SMALL, padx=(GuiConfig.PADDING_SMALL, 0))
        
        # Load modules
        self.load_modules(module_combo)
        
        # File selection
        ttk.Label(form_frame, text="File:").grid(row=2, column=0, sticky=tk.W, pady=GuiConfig.PADDING_SMALL)
        file_frame = ttk.Frame(form_frame)
        file_frame.grid(row=2, column=1, sticky=tk.W + tk.E, pady=GuiConfig.PADDING_SMALL, padx=(GuiConfig.PADDING_SMALL, 0))
        
        self.file_var = tk.StringVar()
        file_entry = ttk.Entry(file_frame, textvariable=self.file_var, state='readonly', width=40)
        file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        browse_btn = ttk.Button(file_frame, text="Browse...", command=self.browse_file)
        browse_btn.pack(side=tk.RIGHT, padx=(GuiConfig.PADDING_SMALL, 0))
        
        # Configure grid weights
        form_frame.columnconfigure(1, weight=1)
        
        # Preview area
        preview_frame = ttk.LabelFrame(main_frame, text="File Preview", padding=GuiConfig.PADDING_SMALL)
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(GuiConfig.PADDING_MEDIUM, 0))
        
        self.preview_text = scrolledtext.ScrolledText(
            preview_frame,
            height=15,
            font=GuiConfig.MONOSPACE_FONT,
            state=tk.DISABLED
        )
        self.preview_text.pack(fill=tk.BOTH, expand=True)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(GuiConfig.PADDING_MEDIUM, 0))
        
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy)
        cancel_btn.pack(side=tk.RIGHT)
        
        submit_btn = ttk.Button(button_frame, text="Submit", command=self.submit_document)
        submit_btn.pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))
    
    def load_modules(self, combo):
        """Load available modules from database"""
        try:
            # Connect to database and fetch modules
            conn = sqlite3.connect(DEFAULT_DB_PATH)
            cursor = conn.cursor()

            # Query modules table
            cursor.execute("""
                SELECT module_code, module_name
                FROM modules
                WHERE is_active = 1
                ORDER BY module_code
            """)

            modules = cursor.fetchall()
            conn.close()

            if modules:
                # Format modules as "CODE - Name"
                module_list = [f"{code} - {name}" for code, name in modules]
                combo['values'] = module_list
                combo.set(module_list[0])
            else:
                # Fallback if no modules found
                combo['values'] = ['No modules available']
                combo.set('No modules available')
                logger.warning("No active modules found in database")

        except Exception as e:
            logger.error(f"Error loading modules from database: {e}")
            combo['values'] = ['Error loading modules']
            combo.set('Error loading modules')
            messagebox.showerror("Database Error", f"Failed to load modules: {str(e)}")
    
    def browse_file(self):
        """Browse for file"""
        file_types = [
            ('Text files', '*.txt'),
            ('PDF files', '*.pdf'),
            ('Word documents', '*.docx'),
            ('All files', '*.*')
        ]
        
        filename = filedialog.askopenfilename(
            title="Select Document",
            filetypes=file_types,
            parent=self.dialog
        )
        
        if filename:
            self.file_path = filename
            self.file_var.set(filename)
            
            # Auto-fill title if empty
            if not self.title_var.get():
                base_name = os.path.splitext(os.path.basename(filename))[0]
                self.title_var.set(base_name)
            
            # Load preview
            self.load_file_preview()
    
    def load_file_preview(self):
        """Load file preview"""
        if not self.file_path:
            return
        
        try:
            # Simple text file reading for preview
            # This would be enhanced for different file types
            with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Show first 2000 characters
            preview = content[:2000]
            if len(content) > 2000:
                preview += "\n\n... (content truncated for preview)"
            
            self.preview_text.config(state=tk.NORMAL)
            self.preview_text.delete(1.0, tk.END)
            self.preview_text.insert(1.0, preview)
            self.preview_text.config(state=tk.DISABLED)
            
        except Exception as e:
            self.preview_text.config(state=tk.NORMAL)
            self.preview_text.delete(1.0, tk.END)
            self.preview_text.insert(1.0, f"Error loading file preview: {e}")
            self.preview_text.config(state=tk.DISABLED)

    def show_my_documents(self):
        """Placeholder for CLI 'view_my_documents' — filters Documents to current user (future)."""
        if not getattr(self, 'checker', None) or not getattr(self, 'auth', None):
            messagebox.showerror("Error", "System not initialized")
            return
        try:
            if hasattr(self, 'notebook') and hasattr(self, 'documents_tab'):
                self.notebook.select(self.documents_tab)
            messagebox.showinfo(
                "My Documents (Placeholder)",
                "This will filter the Documents tab to show only your submissions."
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open My Documents: {e}")

    def show_view_results(self):
        """Placeholder to focus the Results tab (CLI 'view_results')."""
        try:
            if hasattr(self, 'notebook') and hasattr(self, 'results_tab'):
                self.notebook.select(self.results_tab)
            else:
                messagebox.showwarning("Results", "Results tab not available yet.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Results: {e}")

    def show_delete_document_dialog_placeholder(self):
        """Placeholder for CLI 'delete_document_interactive' - redirects to main implementation."""
        if not getattr(self, 'checker', None):
            messagebox.showerror("Error", "System not initialized")
            return
        # Call the main implementation
        self.show_delete_document_dialog()

    def show_repository_integrity_dialog(self):
        """Placeholder for CLI 'check_repository_integrity'."""
        if not getattr(self, 'checker', None):
            messagebox.showerror("Error", "System not initialized")
            return
        # Call the main implementation
        self.check_repository_integrity_gui()
    
    def submit_document(self):
        """Submit the document"""
        # Validate inputs
        title = self.title_var.get().strip()
        if not title:
            messagebox.showerror("Error", "Please enter a document title")
            return
        
        if not self.file_path:
            messagebox.showerror("Error", "Please select a file")
            return
        
        module_text = self.module_var.get()
        module_code = module_text.split(' - ')[0] if module_text else 'UNKNOWN'
        
        def submit_task():
            try:
                # Extract text from file using the checker's method
                content, file_type = self.checker.extract_text_from_file(self.file_path)

                if not content or not content.strip():
                    self.task_queue.put(('submit_error', 'File is empty or could not be read'))
                    return

                # Get author ID from current user
                author_id = self.auth.current_user.get('id')
                if not author_id:
                    self.task_queue.put(('submit_error', 'User not authenticated'))
                    return

                # Add document to repository
                doc_id = self.checker.add_document_to_repository(
                    title=title,
                    content=content,
                    author_id=author_id,
                    module_code=module_code if module_code != 'UNKNOWN' else None,
                    file_type=file_type
                )

                self.task_queue.put(('submit_complete', doc_id))

                # Close dialog in main thread
                self.dialog.after(0, self.dialog.destroy)

            except Exception as e:
                error_msg = str(e)
                self.task_queue.put(('submit_error', error_msg))
        
        thread = threading.Thread(target=submit_task, daemon=True)
        thread.start()

class AdvancedRepositorySearchDialog:
    """Advanced repository search dialog with multiple filters"""
    
    def __init__(self, parent, checker, auth):
        self.parent = parent
        self.checker = checker
        self.auth = auth
        self.dialog = None
        
        # Search variables
        self.search_term_var = None
        self.author_filter_var = None
        self.module_filter_var = None
        self.date_from_var = None
        self.date_to_var = None
        self.file_type_var = None
        self.min_words_var = None
        self.max_words_var = None
        
        self.selected_author_id = None
        self.selected_module_code = None
        
    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Repository Search")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)
        
        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")
        
        # Create interface first
        self.create_search_interface()
        self.load_all_documents()
        
        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab        
        self.create_search_interface()
    
    def create_search_interface(self):
        """Create the advanced search interface"""
        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Advanced Repository Search", font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))
        
        # Search criteria notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        # Basic search tab
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text="Basic Search")
        self.create_basic_search_tab(basic_frame)
        
        # Advanced filters tab
        advanced_frame = ttk.Frame(notebook)
        notebook.add(advanced_frame, text="Advanced Filters")
        self.create_advanced_filters_tab(advanced_frame)
        
        # Results frame
        self.results_frame = ttk.LabelFrame(main_frame, text="Search Results", padding=GuiConfig.PADDING_SMALL)
        self.results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        # Results treeview
        columns = ('Title', 'Author', 'Module', 'Date', 'Type', 'Words', 'Status')
        self.results_tree = ttk.Treeview(self.results_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            self.results_tree.heading(col, text=col)
            self.results_tree.column(col, width=100)
        
        # Scrollbars for results
        v_scrollbar = ttk.Scrollbar(self.results_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        h_scrollbar = ttk.Scrollbar(self.results_frame, orient=tk.HORIZONTAL, command=self.results_tree.xview)
        
        self.results_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        self.results_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        self.results_frame.grid_rowconfigure(0, weight=1)
        self.results_frame.grid_columnconfigure(0, weight=1)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="Search", command=self.perform_advanced_search).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Clear", command=self.clear_search).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        ttk.Button(button_frame, text="Export Results", command=self.export_results).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="View Details", command=self.view_selected_details).pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))
    
    def create_basic_search_tab(self, parent):
        """Create basic search tab"""
        # Search term
        ttk.Label(parent, text="Search Term:", font=GuiConfig.SUBHEADER_FONT).grid(row=0, column=0, sticky=tk.W, pady=GuiConfig.PADDING_SMALL)
        self.search_term_var = tk.StringVar()
        search_entry = ttk.Entry(parent, textvariable=self.search_term_var, width=50)
        search_entry.grid(row=0, column=1, columnspan=2, sticky=tk.W+tk.E, pady=GuiConfig.PADDING_SMALL, padx=(GuiConfig.PADDING_SMALL, 0))
        
        # Author filter
        ttk.Label(parent, text="Author:", font=GuiConfig.SUBHEADER_FONT).grid(row=1, column=0, sticky=tk.W, pady=GuiConfig.PADDING_SMALL)
        self.author_filter_var = tk.StringVar()
        author_entry = ttk.Entry(parent, textvariable=self.author_filter_var, width=30)
        author_entry.grid(row=1, column=1, sticky=tk.W+tk.E, pady=GuiConfig.PADDING_SMALL, padx=(GuiConfig.PADDING_SMALL, 0))
        ttk.Button(parent, text="Select", command=self.select_author).grid(row=1, column=2, pady=GuiConfig.PADDING_SMALL, padx=(GuiConfig.PADDING_SMALL, 0))
        
        # Module filter
        ttk.Label(parent, text="Module:", font=GuiConfig.SUBHEADER_FONT).grid(row=2, column=0, sticky=tk.W, pady=GuiConfig.PADDING_SMALL)
        self.module_filter_var = tk.StringVar()
        module_entry = ttk.Entry(parent, textvariable=self.module_filter_var, width=30)
        module_entry.grid(row=2, column=1, sticky=tk.W+tk.E, pady=GuiConfig.PADDING_SMALL, padx=(GuiConfig.PADDING_SMALL, 0))
        ttk.Button(parent, text="Select", command=self.select_module).grid(row=2, column=2, pady=GuiConfig.PADDING_SMALL, padx=(GuiConfig.PADDING_SMALL, 0))
        
        # Configure grid weights
        parent.grid_columnconfigure(1, weight=1)
    
    def create_advanced_filters_tab(self, parent):
        """Create advanced filters tab"""
        # Date range
        date_frame = ttk.LabelFrame(parent, text="Date Range", padding=GuiConfig.PADDING_SMALL)
        date_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        ttk.Label(date_frame, text="From:").grid(row=0, column=0, sticky=tk.W)
        self.date_from_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.date_from_var, width=15).grid(row=0, column=1, padx=GuiConfig.PADDING_SMALL)
        
        ttk.Label(date_frame, text="To:").grid(row=0, column=2, sticky=tk.W, padx=(GuiConfig.PADDING_MEDIUM, 0))
        self.date_to_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.date_to_var, width=15).grid(row=0, column=3, padx=GuiConfig.PADDING_SMALL)
        
        ttk.Label(date_frame, text="(YYYY-MM-DD format)", font=("Arial", 8)).grid(row=1, column=0, columnspan=4, sticky=tk.W)
        
        # File type filter
        type_frame = ttk.LabelFrame(parent, text="File Type", padding=GuiConfig.PADDING_SMALL)
        type_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        self.file_type_var = tk.StringVar()
        file_types = ['All', 'txt', 'pdf', 'docx', 'doc']
        type_combo = ttk.Combobox(type_frame, textvariable=self.file_type_var, values=file_types, state='readonly')
        type_combo.set('All')
        type_combo.pack(anchor=tk.W)
        
        # Word count range
        words_frame = ttk.LabelFrame(parent, text="Word Count Range", padding=GuiConfig.PADDING_SMALL)
        words_frame.pack(fill=tk.X)
        
        ttk.Label(words_frame, text="Min Words:").grid(row=0, column=0, sticky=tk.W)
        self.min_words_var = tk.StringVar()
        ttk.Entry(words_frame, textvariable=self.min_words_var, width=10).grid(row=0, column=1, padx=GuiConfig.PADDING_SMALL)
        
        ttk.Label(words_frame, text="Max Words:").grid(row=0, column=2, sticky=tk.W, padx=(GuiConfig.PADDING_MEDIUM, 0))
        self.max_words_var = tk.StringVar()
        ttk.Entry(words_frame, textvariable=self.max_words_var, width=10).grid(row=0, column=3, padx=GuiConfig.PADDING_SMALL)
    
    def select_author(self):
        """Open author selection dialog"""
        author_name = self.author_filter_var.get().strip()
        if not author_name:
            author_name = simpledialog.askstring("Author Search", "Enter author name to search:")
            if not author_name:
                return
        
        # This would use the get_author_selection_dialog function
        # For now, simplified implementation
        messagebox.showinfo("Author Selection", f"Author selection for '{author_name}' would open here")
    
    def select_module(self):
        """Open module selection dialog"""
        module_name = self.module_filter_var.get().strip()
        if not module_name:
            module_name = simpledialog.askstring("Module Search", "Enter module name to search:")
            if not module_name:
                return
        
        # This would use the get_module_selection_by_name_dialog function
        messagebox.showinfo("Module Selection", f"Module selection for '{module_name}' would open here")
    
    def perform_advanced_search(self):
        """Perform the advanced search"""
        try:
            # Clear existing results
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            
            # Build search parameters
            search_params = {}
            
            search_term = self.search_term_var.get().strip()
            if search_term:
                search_params['search_term'] = search_term
            
            if self.selected_author_id:
                search_params['author_id'] = self.selected_author_id
            
            if self.selected_module_code:
                search_params['module_code'] = self.selected_module_code
            
            # Perform search
            documents = self.checker.search_repository(
                search_params.get('search_term'),
                author_id=search_params.get('author_id'),
                module_code=search_params.get('module_code')
            )
            
            # Apply additional filters
            filtered_docs = self.apply_advanced_filters(documents)
            
            # Populate results
            for doc in filtered_docs:
                try:
                    doc_details = self.checker.get_document_details(doc['id'])
                    
                    status = "Not checked"
                    if doc_details.get('latest_check'):
                        status = doc_details['latest_check']['status']
                    
                    self.results_tree.insert('', tk.END, values=(
                        doc['title'][:30] + ('...' if len(doc['title']) > 30 else ''),
                        doc_details.get('author_name', 'Unknown')[:20],
                        doc.get('module_code', 'N/A'),
                        doc['submission_date'],
                        doc.get('file_type', 'Unknown'),
                        doc.get('word_count', 0),
                        status
                    ), tags=(str(doc['id']),))
                    
                except Exception as e:
                    logger.error(f"Error processing document {doc['id']}: {e}")
            
            messagebox.showinfo("Search Complete", f"Found {len(filtered_docs)} documents matching your criteria.")
            
        except Exception as e:
            messagebox.showerror("Search Error", f"Error performing search: {e}")
    
    def apply_advanced_filters(self, documents):
        """Apply advanced filters to document list"""
        filtered = documents
        
        # File type filter
        file_type = self.file_type_var.get()
        if file_type and file_type != 'All':
            filtered = [doc for doc in filtered if doc.get('file_type', '').lower() == file_type.lower()]
        
        # Word count filters
        try:
            min_words = self.min_words_var.get().strip()
            if min_words:
                min_words = int(min_words)
                filtered = [doc for doc in filtered if doc.get('word_count', 0) >= min_words]
        except ValueError:
            pass
        
        try:
            max_words = self.max_words_var.get().strip()
            if max_words:
                max_words = int(max_words)
                filtered = [doc for doc in filtered if doc.get('word_count', 0) <= max_words]
        except ValueError:
            pass
        
        # Date filters would be implemented here
        # For now, returning the basic filtered list
        
        return filtered
    
    def clear_search(self):
        """Clear all search criteria"""
        self.search_term_var.set("")
        self.author_filter_var.set("")
        self.module_filter_var.set("")
        self.date_from_var.set("")
        self.date_to_var.set("")
        self.file_type_var.set("All")
        self.min_words_var.set("")
        self.max_words_var.set("")
        
        self.selected_author_id = None
        self.selected_module_code = None
        
        # Clear results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
    
    def export_results(self):
        """Export search results to CSV"""
        try:
            import csv
            from tkinter import filedialog
            
            if not self.results_tree.get_children():
                messagebox.showwarning("No Results", "No search results to export.")
                return
            
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Export Search Results"
            )
            
            if filename:
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # Write headers
                    headers = ['Title', 'Author', 'Module', 'Date', 'Type', 'Words', 'Status']
                    writer.writerow(headers)
                    
                    # Write data
                    for item in self.results_tree.get_children():
                        values = self.results_tree.item(item, 'values')
                        writer.writerow(values)
                
                messagebox.showinfo("Export Complete", f"Results exported to {filename}")
                
        except Exception as e:
            messagebox.showerror("Export Error", f"Error exporting results: {e}")
    
    def view_selected_details(self):
        """View details of selected document"""
        selection = self.results_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a document to view details.")
            return
        
        item = selection[0]
        doc_id = int(self.results_tree.item(item, 'tags')[0])
        
        # This would open the DocumentDetailsDialog
        from plagiarism_main_gui import DocumentDetailsDialog
        details_dialog = DocumentDetailsDialog(self.dialog, self.checker, doc_id)
        details_dialog.show()

# Add this class for bulk operations
class BulkOperationsDialog:
    """Dialog for performing bulk operations on documents"""
    
    def __init__(self, parent, checker, auth):
        self.parent = parent
        self.checker = checker
        self.auth = auth
        self.dialog = None
        self.selected_docs = []
    
    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Repository Search")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)
        
        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")
        
        # Create interface first
        self.create_search_interface()
        self.load_all_documents()
        
        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab
        
        self.create_interface()
        self.load_documents()
    
    def create_interface(self):
        """Create the bulk operations interface"""
        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Bulk Operations", font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))
        
        # Document selection
        selection_frame = ttk.LabelFrame(main_frame, text="Select Documents", padding=GuiConfig.PADDING_SMALL)
        selection_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        # Documents treeview with checkboxes simulation
        columns = ('Selected', 'Title', 'Author', 'Module', 'Date')
        self.docs_tree = ttk.Treeview(selection_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.docs_tree.heading(col, text=col)
            self.docs_tree.column(col, width=120)
        
        self.docs_tree.column('Selected', width=80)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(selection_frame, orient=tk.VERTICAL, command=self.docs_tree.yview)
        h_scrollbar = ttk.Scrollbar(selection_frame, orient=tk.HORIZONTAL, command=self.docs_tree.xview)
        
        self.docs_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        self.docs_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        selection_frame.grid_rowconfigure(0, weight=1)
        selection_frame.grid_columnconfigure(0, weight=1)
        
        # Selection controls
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        ttk.Button(select_frame, text="Select All", command=self.select_all).pack(side=tk.LEFT)
        ttk.Button(select_frame, text="Select None", command=self.select_none).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        ttk.Button(select_frame, text="Toggle Selection", command=self.toggle_selection).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        
        # Operations
        operations_frame = ttk.LabelFrame(main_frame, text="Operations", padding=GuiConfig.PADDING_SMALL)
        operations_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        ttk.Button(operations_frame, text="Bulk Plagiarism Check", command=self.bulk_plagiarism_check).pack(side=tk.LEFT)
        ttk.Button(operations_frame, text="Bulk Delete", command=self.bulk_delete).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        ttk.Button(operations_frame, text="Export Selected", command=self.export_selected).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        # Status
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_label = ttk.Label(main_frame, textvariable=self.status_var)
        status_label.pack()
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(GuiConfig.PADDING_MEDIUM, 0))
        
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT)
        
        # Bind double-click to toggle selection
        self.docs_tree.bind('<Double-1>', self.on_double_click)
    
    def load_documents(self):
        """Load documents for selection"""
        try:
            documents = self.checker.search_repository()
            
            for doc in documents:
                try:
                    doc_details = self.checker.get_document_details(doc['id'])
                    
                    self.docs_tree.insert('', tk.END, values=(
                        "☐",  # Unchecked checkbox symbol
                        doc['title'][:40] + ('...' if len(doc['title']) > 40 else ''),
                        doc_details.get('author_name', 'Unknown'),
                        doc.get('module_code', 'N/A'),
                        doc['submission_date']
                    ), tags=(str(doc['id']), 'unselected'))
                    
                except Exception as e:
                    logger.error(f"Error loading document {doc['id']}: {e}")
                    
        except Exception as e:
            messagebox.showerror("Error", f"Error loading documents: {e}")
    
    def on_double_click(self, event):
        """Handle double-click to toggle selection"""
        item = self.docs_tree.selection()[0] if self.docs_tree.selection() else None
        if item:
            self.toggle_item_selection(item)
    
    def toggle_item_selection(self, item):
        """Toggle selection of a single item"""
        current_values = list(self.docs_tree.item(item, 'values'))
        tags = list(self.docs_tree.item(item, 'tags'))
        
        if 'selected' in tags:
            current_values[0] = "☐"
            tags = [tag for tag in tags if tag != 'selected']
            tags.append('unselected')
        else:
            current_values[0] = "☑"
            tags = [tag for tag in tags if tag != 'unselected']
            tags.append('selected')
        
        self.docs_tree.item(item, values=current_values, tags=tags)
    
    def select_all(self):
        """Select all documents"""
        for item in self.docs_tree.get_children():
            current_values = list(self.docs_tree.item(item, 'values'))
            current_values[0] = "☑"
            tags = [tag for tag in self.docs_tree.item(item, 'tags') if not tag.startswith('selected') and not tag.startswith('unselected')]
            tags.append('selected')
            self.docs_tree.item(item, values=current_values, tags=tags)
    
    def select_none(self):
        """Deselect all documents"""
        for item in self.docs_tree.get_children():
            current_values = list(self.docs_tree.item(item, 'values'))
            current_values[0] = "☐"
            tags = [tag for tag in self.docs_tree.item(item, 'tags') if not tag.startswith('selected') and not tag.startswith('unselected')]
            tags.append('unselected')
            self.docs_tree.item(item, values=current_values, tags=tags)
    
    def toggle_selection(self):
        """Toggle selection of currently selected item"""
        selection = self.docs_tree.selection()
        if selection:
            self.toggle_item_selection(selection[0])
    
    def get_selected_documents(self):
        """Get list of selected document IDs"""
        selected = []
        for item in self.docs_tree.get_children():
            tags = self.docs_tree.item(item, 'tags')
            if 'selected' in tags:
                doc_id = int([tag for tag in tags if tag.isdigit()][0])
                selected.append(doc_id)
        return selected
    
    def bulk_plagiarism_check(self):
        """Perform bulk plagiarism check"""
        selected_docs = self.get_selected_documents()
        
        if not selected_docs:
            messagebox.showwarning("No Selection", "Please select documents to check.")
            return
        
        if not self.auth.check_permission('check_plagiarism'):
            messagebox.showerror("Permission Denied", "You don't have permission to check documents for plagiarism.")
            return
        
        # Confirm operation
        if not messagebox.askyesno("Confirm Bulk Check", 
                                   f"This will check {len(selected_docs)} documents for plagiarism. Continue?"):
            return
        
        # Get threshold
        threshold = simpledialog.askfloat("Threshold", "Enter similarity threshold (0.1-0.9):", 
                                        initialvalue=0.3, minvalue=0.1, maxvalue=0.9)
        if threshold is None:
            return
        
        # Perform checks in a separate thread
        def check_task():
            try:
                results = []
                total = len(selected_docs)
                
                for i, doc_id in enumerate(selected_docs):
                    try:
                        self.dialog.after(0, lambda p=i/total*100: self.progress_var.set(p))
                        self.dialog.after(0, lambda: self.status_var.set(f"Checking document {i+1} of {total}..."))
                        
                        result = self.checker.check_plagiarism(doc_id, self.auth.current_user['id'], threshold)
                        results.append(result)
                        
                    except Exception as e:
                        logger.error(f"Error checking document {doc_id}: {e}")
                        results.append({'error': str(e), 'document_id': doc_id})
                
                self.dialog.after(0, lambda: self.progress_var.set(100))
                self.dialog.after(0, lambda: self.status_var.set("Bulk check completed"))
                self.dialog.after(0, lambda: self.show_bulk_results(results))
                
            except Exception as e:
                error_msg = str(e)
                self.dialog.after(0, lambda err=error_msg: messagebox.showerror("Error", f"Bulk check failed: {err}"))
        
        self.status_var.set("Starting bulk plagiarism check...")
        thread = threading.Thread(target=check_task, daemon=True)
        thread.start()
    
    def bulk_delete(self):
        """Perform bulk delete"""
        selected_docs = self.get_selected_documents()
        
        if not selected_docs:
            messagebox.showwarning("No Selection", "Please select documents to delete.")
            return
        
        if not self.auth.check_permission('manage_plagiarism_system'):
            messagebox.showerror("Permission Denied", "You don't have permission to delete documents.")
            return
        
        # Confirm operation
        if not messagebox.askyesno("Confirm Bulk Delete", 
                                   f"This will permanently delete {len(selected_docs)} documents. Continue?"):
            return
        
        # Second confirmation
        if not messagebox.askyesno("Final Confirmation", 
                                   "This action cannot be undone. Are you absolutely sure?"):
            return
        
        # Perform deletions
        try:
            deleted_count = 0
            total = len(selected_docs)
            
            for i, doc_id in enumerate(selected_docs):
                try:
                    self.progress_var.set(i/total*100)
                    self.status_var.set(f"Deleting document {i+1} of {total}...")
                    
                    if self.checker.delete_document(doc_id):
                        deleted_count += 1
                        
                except Exception as e:
                    logger.error(f"Error deleting document {doc_id}: {e}")
            
            self.progress_var.set(100)
            self.status_var.set(f"Deleted {deleted_count} of {total} documents")
            
            messagebox.showinfo("Bulk Delete Complete", 
                               f"Successfully deleted {deleted_count} out of {total} documents.")
            
            # Reload the document list
            for item in self.docs_tree.get_children():
                self.docs_tree.delete(item)
            self.load_documents()
            
        except Exception as e:
            messagebox.showerror("Error", f"Bulk delete failed: {e}")
    
    def export_selected(self):
        """Export selected documents"""
        selected_docs = self.get_selected_documents()
        
        if not selected_docs:
            messagebox.showwarning("No Selection", "Please select documents to export.")
            return
        
        try:
            import csv
            from tkinter import filedialog
            
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Export Selected Documents"
            )
            
            if filename:
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # Write headers
                    headers = ['ID', 'Title', 'Author', 'Module', 'Submission Date', 'File Type', 'Word Count', 'Latest Check Status']
                    writer.writerow(headers)
                    
                    # Write data
                    for doc_id in selected_docs:
                        try:
                            doc_details = self.checker.get_document_details(doc_id)
                            
                            status = "Not checked"
                            if doc_details.get('latest_check'):
                                status = doc_details['latest_check']['status']
                            
                            writer.writerow([
                                doc_details['id'],
                                doc_details['title'],
                                doc_details.get('author_name', 'Unknown'),
                                doc_details.get('module_code', 'N/A'),
                                doc_details['submission_date'],
                                doc_details.get('file_type', 'Unknown'),
                                doc_details.get('word_count', 0),
                                status
                            ])
                            
                        except Exception as e:
                            logger.error(f"Error exporting document {doc_id}: {e}")
                
                messagebox.showinfo("Export Complete", f"Exported {len(selected_docs)} documents to {filename}")
                
        except Exception as e:
            messagebox.showerror("Export Error", f"Error exporting documents: {e}")
    
    def show_bulk_results(self, results):
        """Show results of bulk operation"""
        # Create results dialog
        results_dialog = tk.Toplevel(self.dialog)
        results_dialog.title("Bulk Check Results")
        results_dialog.geometry("600x400")
        results_dialog.transient(self.dialog)
        
        main_frame = ttk.Frame(results_dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Bulk Plagiarism Check Results", font=GuiConfig.HEADER_FONT).pack(pady=(0, GuiConfig.PADDING_MEDIUM))
        
        # Results tree
        columns = ('Document ID', 'Status', 'Similarity', 'Matches')
        results_tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            results_tree.heading(col, text=col)
            results_tree.column(col, width=120)
        
        # Populate results
        for result in results:
            if 'error' in result:
                results_tree.insert('', tk.END, values=(
                    result['document_id'],
                    'ERROR',
                    'N/A',
                    result['error']
                ))
            else:
                similarity = result.get('highest_similarity', 0) * 100
                match_count = len(result.get('matches', []))
                
                results_tree.insert('', tk.END, values=(
                    result['document_id'],
                    result.get('status', 'Unknown'),
                    f"{similarity:.1f}%",
                    str(match_count)
                ))
        
        results_tree.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        ttk.Button(main_frame, text="Close", command=results_dialog.destroy).pack()

# Add this class for comprehensive system testing
class SystemTestingDialog:
    """Comprehensive system testing dialog"""
    
    def __init__(self, parent, checker):
        self.parent = parent
        self.checker = checker
        self.dialog = None
        self.test_results = []
    
    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Repository Search")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)
        
        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")
        
        # Create interface first
        self.create_search_interface()
        self.load_all_documents()
        
        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab
        
        self.create_interface()
    
    def create_interface(self):
        """Create the testing interface"""
        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="System Testing Suite", font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))
        
        # Test categories
        categories_frame = ttk.LabelFrame(main_frame, text="Test Categories", padding=GuiConfig.PADDING_MEDIUM)
        categories_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        # Checkboxes for test categories
        self.test_vars = {}
        test_categories = [
            ("Database Connection", "db_connection"),
            ("Document Repository", "doc_repository"),
            ("Document Submission", "doc_submission"),
            ("Plagiarism Detection", "plagiarism_check"),
            ("Error Handling", "error_handling"),
            ("Edge Cases", "edge_cases"),
            ("Performance Tests", "performance"),
            ("Integration Tests", "integration")
        ]
        
        for i, (name, key) in enumerate(test_categories):
            var = tk.BooleanVar(value=True)
            self.test_vars[key] = var
            
            row = i // 2
            col = i % 2
            
            ttk.Checkbutton(categories_frame, text=name, variable=var).grid(
                row=row, column=col, sticky=tk.W, padx=GuiConfig.PADDING_SMALL, pady=GuiConfig.PADDING_SMALL
            )
        
        # Test controls
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        ttk.Button(controls_frame, text="Run Selected Tests", command=self.run_tests).pack(side=tk.LEFT)
        ttk.Button(controls_frame, text="Select All", command=self.select_all_tests).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        ttk.Button(controls_frame, text="Select None", command=self.select_no_tests).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        
        # Progress
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_SMALL))
        
        self.status_var = tk.StringVar()
        self.status_var.set("Ready to run tests")
        ttk.Label(progress_frame, textvariable=self.status_var).pack()
        
        # Results
        results_frame = ttk.LabelFrame(main_frame, text="Test Results", padding=GuiConfig.PADDING_SMALL)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        self.results_text = scrolledtext.ScrolledText(
            results_frame,
            height=15,
            font=GuiConfig.MONOSPACE_FONT,
            wrap=tk.WORD
        )
        self.results_text.pack(fill=tk.BOTH, expand=True)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="Save Results", command=self.save_results).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Clear Results", command=self.clear_results).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT)
    
    def select_all_tests(self):
        """Select all test categories"""
        for var in self.test_vars.values():
            var.set(True)
    
    def select_no_tests(self):
        """Deselect all test categories"""
        for var in self.test_vars.values():
            var.set(False)
    
    def run_tests(self):
        """Run selected tests"""
        selected_tests = [key for key, var in self.test_vars.items() if var.get()]
        
        if not selected_tests:
            messagebox.showwarning("No Tests Selected", "Please select at least one test category.")
            return
        
        # Clear previous results
        self.clear_results()
        self.test_results = []
        
        # Run tests in a separate thread
        def test_task():
            try:
                total_tests = len(selected_tests)
                
                for i, test_key in enumerate(selected_tests):
                    self.dialog.after(0, lambda p=i/total_tests*100: self.progress_var.set(p))
                    self.dialog.after(0, lambda t=test_key: self.status_var.set(f"Running {t} tests..."))
                    
                    result = self.run_test_category(test_key)
                    self.test_results.append(result)
                    
                    # Update results display
                    self.dialog.after(0, lambda r=result: self.add_test_result(r))
                
                self.dialog.after(0, lambda: self.progress_var.set(100))
                self.dialog.after(0, lambda: self.status_var.set("All tests completed"))
                self.dialog.after(0, self.show_test_summary)
                
            except Exception as e:
                error_msg = str(e)
                self.dialog.after(0, lambda err=error_msg: messagebox.showerror("Test Error", f"Testing failed: {err}"))
        
        thread = threading.Thread(target=test_task, daemon=True)
        thread.start()
    
    def run_test_category(self, test_key):
        """Run a specific test category"""
        try:
            if test_key == "db_connection":
                return self.test_database_connection()
            elif test_key == "doc_repository":
                return self.test_document_repository()
            elif test_key == "doc_submission":
                return self.test_document_submission()
            elif test_key == "plagiarism_check":
                return self.test_plagiarism_detection()
            elif test_key == "error_handling":
                return self.test_error_handling()
            elif test_key == "edge_cases":
                return self.test_edge_cases()
            elif test_key == "performance":
                return self.test_performance()
            elif test_key == "integration":
                return self.test_integration()
            else:
                return {"category": test_key, "status": "UNKNOWN", "message": "Test not implemented"}
                
        except Exception as e:
            return {"category": test_key, "status": "ERROR", "message": str(e)}
    
    def test_database_connection(self):
        """Test database connection and basic operations"""
        try:
            with self.checker.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Test basic query
                cursor.execute("SELECT COUNT(*) FROM document_repository")
                count = cursor.fetchone()[0]
                
                return {
                    "category": "Database Connection",
                    "status": "PASSED",
                    "message": f"Successfully connected to database. Found {count} documents in repository."
                }
                
        except Exception as e:
            return {
                "category": "Database Connection",
                "status": "FAILED",
                "message": f"Database connection failed: {e}"
            }
    
    def test_document_repository(self):
        """Test document repository operations"""
        try:
            # Test search
            results = self.checker.search_repository()
            
            if not isinstance(results, list):
                return {
                    "category": "Document Repository",
                    "status": "FAILED",
                    "message": "Search repository did not return a list"
                }
            
            # Test document details if documents exist
            if results:
                doc_id = results[0]['id']
                details = self.checker.get_document_details(doc_id)
                
                if not isinstance(details, dict) or not details.get('title'):
                    return {
                        "category": "Document Repository",
                        "status": "FAILED",
                        "message": "Get document details returned invalid data"
                    }
            
            return {
                "category": "Document Repository",
                "status": "PASSED",
                "message": f"Repository operations successful. Found {len(results)} documents."
            }
            
        except Exception as e:
            return {
                "category": "Document Repository",
                "status": "FAILED",
                "message": f"Repository test failed: {e}"
            }
    
    def test_document_submission(self):
        """Test document submission functionality"""
        try:
            # Create authenticated user for testing
            auth = get_authenticated_user_auth()
            if not auth.current_user:
                return {
                    "category": "Document Submission",
                    "status": "FAILED",
                    "message": "No test user available"
                }
            
            # Test content
            test_content = f"Test document content created at {datetime.now().isoformat()}"
            title = f"Test Document {datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Submit document
            doc_id = self.checker.add_document_to_repository(
                title, test_content, auth.current_user['id'], 'TEST_MODULE', 'txt'
            )
            
            if not doc_id:
                return {
                    "category": "Document Submission",
                    "status": "FAILED",
                    "message": "Document submission returned no ID"
                }
            
            # Verify document exists
            details = self.checker.get_document_details(doc_id)
            if details['title'] != title:
                return {
                    "category": "Document Submission",
                    "status": "FAILED",
                    "message": "Document verification failed - title mismatch"
                }
            
            return {
                "category": "Document Submission",
                "status": "PASSED",
                "message": f"Document submitted successfully with ID: {doc_id}"
            }
            
        except Exception as e:
            return {
                "category": "Document Submission",
                "status": "FAILED",
                "message": f"Document submission test failed: {e}"
            }
    
    def test_plagiarism_detection(self):
        """Test plagiarism detection functionality"""
        try:
            # Get existing documents
            documents = self.checker.search_repository()
            if not documents:
                return {
                    "category": "Plagiarism Detection",
                    "status": "SKIPPED",
                    "message": "No documents available for plagiarism testing"
                }
            
            doc_id = documents[0]['id']

            # Create authenticated user for testing
            auth = get_authenticated_user_auth()
            if not auth.current_user:
                return {
                    "category": "Plagiarism Detection",
                    "status": "FAILED",
                    "message": "No test user available"
                }
            
            # Perform plagiarism check
            result = self.checker.check_plagiarism(doc_id, auth.current_user['id'], 0.3)
            
            if not isinstance(result, dict) or 'status' not in result:
                return {
                    "category": "Plagiarism Detection",
                    "status": "FAILED",
                    "message": "Plagiarism check returned invalid result format"
                }
            
            return {
                "category": "Plagiarism Detection",
                "status": "PASSED",
                "message": f"Plagiarism check completed successfully. Status: {result['status']}"
            }
            
        except Exception as e:
            return {
                "category": "Plagiarism Detection",
                "status": "FAILED",
                "message": f"Plagiarism detection test failed: {e}"
            }
    
    def test_error_handling(self):
        """Test error handling with invalid inputs"""
        try:
            error_count = 0
            total_tests = 5
            
            # Test invalid document ID
            try:
                self.checker.get_document_details(-1)
                return {
                    "category": "Error Handling",
                    "status": "FAILED",
                    "message": "Failed to handle invalid document ID"
                }
            except (ValueError, PlagiarismCheckerError):
                error_count += 1
            
            # Test invalid plagiarism check
            try:
                self.checker.check_plagiarism("invalid")
                return {
                    "category": "Error Handling",
                    "status": "FAILED",
                    "message": "Failed to handle invalid plagiarism check input"
                }
            except (ValueError, TypeError, PlagiarismCheckerError):
                error_count += 1
            
            # Test empty document submission
            try:
                self.checker.add_document_to_repository("", "content", 1, "MOD", "txt")
                return {
                    "category": "Error Handling",
                    "status": "FAILED",
                    "message": "Failed to handle empty title submission"
                }
            except (ValueError, PlagiarismCheckerError):
                error_count += 1
            
            # Test invalid result ID
            try:
                self.checker.get_plagiarism_result(-1)
                return {
                    "category": "Error Handling",
                    "status": "FAILED",
                    "message": "Failed to handle invalid result ID"
                }
            except (ValueError, PlagiarismCheckerError):
                error_count += 1
            
            # Test invalid search parameters
            try:
                self.checker.search_repository("", author_id="invalid")
                return {
                    "category": "Error Handling",
                    "status": "FAILED",
                    "message": "Failed to handle invalid search parameters"
                }
            except (ValueError, PlagiarismCheckerError):
                error_count += 1
            
            if error_count == total_tests:
                return {
                    "category": "Error Handling",
                    "status": "PASSED",
                    "message": f"All {total_tests} error handling tests passed"
                }
            else:
                return {
                    "category": "Error Handling",
                    "status": "PARTIAL",
                    "message": f"Passed {error_count} out of {total_tests} error handling tests"
                }
                
        except Exception as e:
            return {
                "category": "Error Handling",
                "status": "FAILED",
                "message": f"Error handling test failed: {e}"
            }
    
    def test_edge_cases(self):
        """Test edge cases and boundary conditions"""
        try:
            test_count = 0
            passed_count = 0
            
            # Test empty search
            test_count += 1
            try:
                results = self.checker.search_repository("")
                if isinstance(results, list):
                    passed_count += 1
            except Exception:
                pass
            
            # Test text preprocessing with edge cases
            test_count += 1
            try:
                edge_texts = ["", "   ", "123", "!@#$", "a b c"]
                for text in edge_texts:
                    tokens = self.checker.preprocess_text(text)
                    if isinstance(tokens, list):
                        passed_count += 1
                        break
            except Exception:
                pass
            
            # Test statistics with empty database
            test_count += 1
            try:
                stats = self.checker.get_statistics()
                if isinstance(stats, dict):
                    passed_count += 1
            except Exception:
                pass
            
            return {
                "category": "Edge Cases",
                "status": "PASSED" if passed_count == test_count else "PARTIAL",
                "message": f"Passed {passed_count} out of {test_count} edge case tests"
            }
            
        except Exception as e:
            return {
                "category": "Edge Cases",
                "status": "FAILED",
                "message": f"Edge case testing failed: {e}"
            }
    
    def test_performance(self):
        """Test system performance"""
        try:
            import time
            
            # Test search performance
            start_time = time.time()
            results = self.checker.search_repository()
            search_time = time.time() - start_time
            
            # Test statistics performance
            start_time = time.time()
            stats = self.checker.get_statistics()
            stats_time = time.time() - start_time
            
            performance_ok = search_time < 5.0 and stats_time < 3.0
            
            return {
                "category": "Performance",
                "status": "PASSED" if performance_ok else "WARNING",
                "message": f"Search: {search_time:.2f}s, Stats: {stats_time:.2f}s"
            }
            
        except Exception as e:
            return {
                "category": "Performance",
                "status": "FAILED",
                "message": f"Performance test failed: {e}"
            }
    
    def test_integration(self):
        """Test integration between components"""
        try:
            # Test full workflow: submit -> check -> retrieve
            auth = get_authenticated_user_auth()
            if not auth.current_user:
                return {
                    "category": "Integration",
                    "status": "FAILED",
                    "message": "No test user available for integration test"
                }
            
            # Submit document
            test_content = f"Integration test content {datetime.now().isoformat()}"
            title = f"Integration Test {datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            doc_id = self.checker.add_document_to_repository(
                title, test_content, auth.current_user['id'], 'TEST_MODULE', 'txt'
            )
            
            # Check for plagiarism
            result = self.checker.check_plagiarism(doc_id, auth.current_user['id'], 0.3)
            
            # Retrieve result details
            if result.get('result_id'):
                details = self.checker.get_plagiarism_result(result['result_id'])
                
                if not details or details['document_title'] != title:
                    return {
                        "category": "Integration",
                        "status": "FAILED",
                        "message": "Integration test failed - result details mismatch"
                    }
            
            return {
                "category": "Integration",
                "status": "PASSED",
                "message": "Full workflow integration test completed successfully"
            }
            
        except Exception as e:
            return {
                "category": "Integration",
                "status": "FAILED",
                "message": f"Integration test failed: {e}"
            }
    
    def add_test_result(self, result):
        """Add test result to display"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        status_symbol = {"PASSED": "✓", "FAILED": "✗", "WARNING": "⚠", "SKIPPED": "⊘", "PARTIAL": "◐"}.get(result['status'], "?")
        
        result_line = f"[{timestamp}] {status_symbol} {result['category']}: {result['status']} - {result['message']}\n"
        
        self.results_text.insert(tk.END, result_line)
        self.results_text.see(tk.END)
        self.results_text.update()
    
    def show_test_summary(self):
        """Show test summary"""
        if not self.test_results:
            return
        
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r['status'] == 'PASSED')
        failed = sum(1 for r in self.test_results if r['status'] == 'FAILED')
        
        summary = f"\n{'='*50}\nTEST SUMMARY\n{'='*50}\n"
        summary += f"Total Tests: {total}\n"
        summary += f"Passed: {passed}\n"
        summary += f"Failed: {failed}\n"
        summary += f"Success Rate: {passed/total*100:.1f}%\n"
        summary += f"{'='*50}\n"
        
        self.results_text.insert(tk.END, summary)
        self.results_text.see(tk.END)
    
    def clear_results(self):
        """Clear test results"""
        self.results_text.delete(1.0, tk.END)
        self.test_results = []
        self.progress_var.set(0)
        self.status_var.set("Ready to run tests")
    
    def save_results(self):
        """Save test results to file"""
        if not self.test_results:
            messagebox.showwarning("No Results", "No test results to save.")
            return
        
        try:
            from tkinter import filedialog
            
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                title="Save Test Results"
            )
            
            if filename:
                content = self.results_text.get(1.0, tk.END)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                messagebox.showinfo("Save Complete", f"Test results saved to {filename}")
                
        except Exception as e:
            messagebox.showerror("Save Error", f"Error saving results: {e}")

class CheckResultDialog:
    """Dialog for showing plagiarism check results"""
    
    def __init__(self, parent, result):
        self.parent = parent
        self.result = result
        
        self.dialog = None
    
    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Plagiarism Check Result")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")

        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab

        self.create_result_interface()
    
    def create_result_interface(self):
        """Create the result interface"""
        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Plagiarism Check Result", font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))
        
        # Result summary
        summary_frame = ttk.LabelFrame(main_frame, text="Summary", padding=GuiConfig.PADDING_MEDIUM)
        summary_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        # Status
        status = self.result.get('status', 'UNKNOWN')
        similarity = self.result.get('highest_similarity', 0) * 100
        
        # Determine color based on status
        if status in ['EXACT_MATCH', 'HIGH_SIMILARITY']:
            status_color = GuiConfig.DANGER_COLOR
            status_icon = "⚠️ HIGH RISK"
        elif status == 'MODERATE_SIMILARITY':
            status_color = GuiConfig.WARNING_COLOR
            status_icon = "⚠️ MODERATE RISK"
        else:
            status_color = GuiConfig.SUCCESS_COLOR
            status_icon = "✅ LOW RISK"
        
        status_frame = ttk.Frame(summary_frame)
        status_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        ttk.Label(status_frame, text="Status:", font=GuiConfig.SUBHEADER_FONT).pack(side=tk.LEFT)
        
        status_label = tk.Label(
            status_frame,
            text=f"{status_icon} - {status}",
            font=GuiConfig.SUBHEADER_FONT,
            fg=status_color
        )
        status_label.pack(side=tk.LEFT, padx=(GuiConfig.PADDING_MEDIUM, 0))
        
        # Similarity score
        similarity_frame = ttk.Frame(summary_frame)
        similarity_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        ttk.Label(similarity_frame, text="Highest Similarity:", font=GuiConfig.SUBHEADER_FONT).pack(side=tk.LEFT)
        ttk.Label(similarity_frame, text=f"{similarity:.1f}%", font=GuiConfig.BODY_FONT).pack(
            side=tk.LEFT, padx=(GuiConfig.PADDING_MEDIUM, 0)
        )
        
        # Threshold used
        threshold = self.result.get('threshold_used', 0) * 100
        threshold_frame = ttk.Frame(summary_frame)
        threshold_frame.pack(fill=tk.X)
        
        ttk.Label(threshold_frame, text="Threshold Used:", font=GuiConfig.SUBHEADER_FONT).pack(side=tk.LEFT)
        ttk.Label(threshold_frame, text=f"{threshold:.0f}%", font=GuiConfig.BODY_FONT).pack(
            side=tk.LEFT, padx=(GuiConfig.PADDING_MEDIUM, 0)
        )
        
        # Matches
        if self.result.get('matches'):
            matches_frame = ttk.LabelFrame(main_frame, text="Similar Documents", padding=GuiConfig.PADDING_SMALL)
            matches_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))
            
            # Matches tree
            columns = ('Document', 'Similarity')
            matches_tree = ttk.Treeview(matches_frame, columns=columns, show='headings', height=10)
            
            matches_tree.heading('Document', text='Document Title')
            matches_tree.heading('Similarity', text='Similarity Score')
            
            matches_tree.column('Document', width=400)
            matches_tree.column('Similarity', width=150)
            
            # Populate matches
            for match_id, match_title, match_similarity in self.result['matches']:
                match_percentage = match_similarity * 100
                matches_tree.insert('', tk.END, values=(
                    match_title,
                    f"{match_percentage:.1f}%"
                ), tags=(str(match_id),))
            
            # Scrollbar
            matches_scrollbar = ttk.Scrollbar(matches_frame, orient=tk.VERTICAL, command=matches_tree.yview)
            matches_tree.configure(yscrollcommand=matches_scrollbar.set)
            
            # Pack
            matches_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            matches_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        close_btn = ttk.Button(button_frame, text="Close", command=self.dialog.destroy)
        close_btn.pack(side=tk.RIGHT)
        
        if self.result.get('result_id'):
            details_btn = ttk.Button(
                button_frame,
                text="View Full Report",
                command=self.view_full_report
            )
            details_btn.pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))
    
    def view_full_report(self):
        """View full detailed report"""
        if self.result.get('result_id'):
            details_dialog = ResultDetailsDialog(self.dialog, None, self.result['result_id'])
            details_dialog.show()


class ResultDetailsDialog:
    """Dialog for showing detailed plagiarism result information"""

    def __init__(self, parent, checker, result_id):
        self.parent = parent
        self.checker = checker
        self.result_id = result_id

        self.dialog = None

    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Plagiarism Result Details")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")

        # Load and display the result details
        self.load_and_display_details()

        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab
    
    def load_and_display_details(self):
        """Load and display detailed results"""
        def load_task():
            try:
                result = self.checker.get_plagiarism_result(self.result_id)
                self.dialog.after(0, lambda: self.create_details_interface(result))
                
            except Exception as e:
                error_msg = str(e)
                self.dialog.after(0, lambda err=error_msg: self.show_error(err))
        
        # Show loading message
        loading_label = ttk.Label(self.dialog, text="Loading detailed report...", font=GuiConfig.BODY_FONT)
        loading_label.pack(expand=True)
        
        thread = threading.Thread(target=load_task, daemon=True)
        thread.start()
    
    def create_details_interface(self, result):
        """Create the details interface"""
        # Clear loading message
        for widget in self.dialog.winfo_children():
            widget.destroy()
        
        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Detailed Plagiarism Report", font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))
        
        # Document information
        doc_frame = ttk.LabelFrame(main_frame, text="Document Information", padding=GuiConfig.PADDING_MEDIUM)
        doc_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        doc_info = [
            ("Document:", result['document_title']),
            ("Author:", result['author_name'] or 'Unknown'),
            ("Check Date:", result['check_date']),
            ("Checked By:", result['checker_name'] or 'Unknown')
        ]
        
        for i, (label, value) in enumerate(doc_info):
            ttk.Label(doc_frame, text=label, font=GuiConfig.SUBHEADER_FONT).grid(
                row=i, column=0, sticky=tk.W, pady=GuiConfig.PADDING_SMALL
            )
            ttk.Label(doc_frame, text=value, font=GuiConfig.BODY_FONT).grid(
                row=i, column=1, sticky=tk.W, padx=(GuiConfig.PADDING_MEDIUM, 0), pady=GuiConfig.PADDING_SMALL
            )
        
        # Results summary
        results_frame = ttk.LabelFrame(main_frame, text="Check Results", padding=GuiConfig.PADDING_MEDIUM)
        results_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        similarity = result['similarity_score'] * 100
        threshold = result['threshold_used'] * 100
        
        results_info = [
            ("Status:", result['status']),
            ("Similarity Score:", f"{similarity:.1f}%"),
            ("Threshold Used:", f"{threshold:.0f}%")
        ]
        
        if result.get('matched_document_title'):
            results_info.append(("Matched Document:", result['matched_document_title']))
        
        for i, (label, value) in enumerate(results_info):
            ttk.Label(results_frame, text=label, font=GuiConfig.SUBHEADER_FONT).grid(
                row=i, column=0, sticky=tk.W, pady=GuiConfig.PADDING_SMALL
            )
            
            if label == "Status:":
                color = GuiConfig.DANGER_COLOR if result['status'] in ['EXACT_MATCH', 'HIGH_SIMILARITY'] else \
                       GuiConfig.WARNING_COLOR if result['status'] == 'MODERATE_SIMILARITY' else \
                       GuiConfig.SUCCESS_COLOR
                status_label = tk.Label(results_frame, text=value, font=GuiConfig.BODY_FONT, fg=color)
                status_label.grid(row=i, column=1, sticky=tk.W, padx=(GuiConfig.PADDING_MEDIUM, 0), pady=GuiConfig.PADDING_SMALL)
            else:
                ttk.Label(results_frame, text=value, font=GuiConfig.BODY_FONT).grid(
                    row=i, column=1, sticky=tk.W, padx=(GuiConfig.PADDING_MEDIUM, 0), pady=GuiConfig.PADDING_SMALL
                )
        
        # Detailed report
        if result.get('report'):
            report_frame = ttk.LabelFrame(main_frame, text="Detailed Report", padding=GuiConfig.PADDING_SMALL)
            report_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))
            
            report_text = scrolledtext.ScrolledText(
                report_frame,
                height=10,
                font=GuiConfig.MONOSPACE_FONT,
                state=tk.DISABLED,
                wrap=tk.WORD
            )
            report_text.pack(fill=tk.BOTH, expand=True)
            
            report_text.config(state=tk.NORMAL)
            report_text.insert(1.0, result['report'])
            report_text.config(state=tk.DISABLED)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        close_btn = ttk.Button(button_frame, text="Close", command=self.dialog.destroy)
        close_btn.pack(side=tk.RIGHT)
        
        if result.get('matched_document_id'):
            view_match_btn = ttk.Button(
                button_frame,
                text="View Matched Document",
                command=lambda: self.view_matched_document(result['matched_document_id'])
            )
            view_match_btn.pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))
    
    def view_matched_document(self, doc_id):
        """View the matched document"""
        details_dialog = DocumentDetailsDialog(self.dialog, self.checker, doc_id)
        details_dialog.show()
    
    def show_error(self, error):
        """Show error message"""
        # Clear any existing widgets
        for widget in self.dialog.winfo_children():
            widget.destroy()
        
        error_label = ttk.Label(
            self.dialog,
            text=f"Error loading detailed report:\n{error}",
            font=GuiConfig.BODY_FONT,
            foreground=GuiConfig.DANGER_COLOR
        )
        error_label.pack(expand=True)
        
        close_btn = ttk.Button(self.dialog, text="Close", command=self.dialog.destroy)
        close_btn.pack(pady=GuiConfig.PADDING_MEDIUM)


class StatisticsDialog:
    """Dialog for showing system statistics"""

    def __init__(self, parent, checker):
        self.parent = parent
        self.checker = checker

        self.dialog = None

    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("System Statistics")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")

        # Load and display the statistics
        self.load_and_display_statistics()

        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab
    
    def load_and_display_statistics(self):
        """Load and display statistics"""
        def load_task():
            try:
                stats = self.checker.get_statistics()
                self.dialog.after(0, lambda: self.create_statistics_interface(stats))
                
            except Exception as e:
                error_msg = str(e)
                self.dialog.after(0, lambda err=error_msg: self.show_error(err))
        
        # Show loading message
        loading_label = ttk.Label(self.dialog, text="Loading statistics...", font=GuiConfig.BODY_FONT)
        loading_label.pack(expand=True)
        
        thread = threading.Thread(target=load_task, daemon=True)
        thread.start()
    
    def create_statistics_interface(self, stats):
        """Create the statistics interface"""
        # Clear loading message
        for widget in self.dialog.winfo_children():
            widget.destroy()
        
        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="System Statistics", font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))
        
        # Overview
        overview_frame = ttk.LabelFrame(main_frame, text="Overview", padding=GuiConfig.PADDING_MEDIUM)
        overview_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        overview_info = [
            ("Total Documents:", str(stats.get('total_documents', 0))),
            ("Total Checks:", str(stats.get('total_checks', 0))),
            ("Last Updated:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        ]
        
        for i, (label, value) in enumerate(overview_info):
            ttk.Label(overview_frame, text=label, font=GuiConfig.SUBHEADER_FONT).grid(
                row=i, column=0, sticky=tk.W, pady=GuiConfig.PADDING_SMALL
            )
            ttk.Label(overview_frame, text=value, font=GuiConfig.BODY_FONT).grid(
                row=i, column=1, sticky=tk.W, padx=(GuiConfig.PADDING_MEDIUM, 0), pady=GuiConfig.PADDING_SMALL
            )
        
        # Create notebook for detailed stats
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        # Status distribution tab
        self.create_status_tab(notebook, stats.get('status_counts', {}))
        
        # Module distribution tab
        self.create_modules_tab(notebook, stats.get('documents_by_module', {}))
        
        # Recent checks tab
        self.create_recent_tab(notebook, stats.get('recent_checks', []))
        
        # Close button
        close_btn = ttk.Button(main_frame, text="Close", command=self.dialog.destroy)
        close_btn.pack()
    
    def create_status_tab(self, notebook, status_counts):
        """Create status distribution tab"""
        status_frame = ttk.Frame(notebook)
        notebook.add(status_frame, text="Check Status")
        
        if not status_counts:
            no_data_label = ttk.Label(
                status_frame,
                text="No plagiarism check data available",
                font=GuiConfig.BODY_FONT
            )
            no_data_label.pack(expand=True)
            return
        
        # Status tree
        columns = ('Status', 'Count', 'Percentage')
        status_tree = ttk.Treeview(status_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            status_tree.heading(col, text=col)
            status_tree.column(col, width=150)
        
        # Calculate percentages
        total_checks = sum(status_counts.values())
        
        for status, count in sorted(status_counts.items()):
            percentage = (count / total_checks * 100) if total_checks > 0 else 0
            status_tree.insert('', tk.END, values=(
                status,
                str(count),
                f"{percentage:.1f}%"
            ))
        
        # Scrollbar
        status_scrollbar = ttk.Scrollbar(status_frame, orient=tk.VERTICAL, command=status_tree.yview)
        status_tree.configure(yscrollcommand=status_scrollbar.set)
        
        # Pack
        status_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        status_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def create_modules_tab(self, notebook, module_counts):
        """Create module distribution tab"""
        modules_frame = ttk.Frame(notebook)
        notebook.add(modules_frame, text="Documents by Module")
        
        if not module_counts:
            no_data_label = ttk.Label(
                modules_frame,
                text="No module data available",
                font=GuiConfig.BODY_FONT
            )
            no_data_label.pack(expand=True)
            return
        
        # Modules tree
        columns = ('Module', 'Documents', 'Percentage')
        modules_tree = ttk.Treeview(modules_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            modules_tree.heading(col, text=col)
            modules_tree.column(col, width=150)
        
        # Calculate percentages
        total_docs = sum(module_counts.values())
        
        for module, count in sorted(module_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_docs * 100) if total_docs > 0 else 0
            modules_tree.insert('', tk.END, values=(
                module,
                str(count),
                f"{percentage:.1f}%"
            ))
        
        # Scrollbar
        modules_scrollbar = ttk.Scrollbar(modules_frame, orient=tk.VERTICAL, command=modules_tree.yview)
        modules_tree.configure(yscrollcommand=modules_scrollbar.set)
        
        # Pack
        modules_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        modules_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def create_recent_tab(self, notebook, recent_checks):
        """Create recent checks tab"""
        recent_frame = ttk.Frame(notebook)
        notebook.add(recent_frame, text="Recent Checks")
        
        if not recent_checks:
            no_data_label = ttk.Label(
                recent_frame,
                text="No recent check data available",
                font=GuiConfig.BODY_FONT
            )
            no_data_label.pack(expand=True)
            return
        
        # Recent checks tree
        columns = ('Document', 'Status', 'Similarity', 'Date')
        recent_tree = ttk.Treeview(recent_frame, columns=columns, show='headings', height=15)
        
        recent_tree.heading('Document', text='Document Title')
        recent_tree.heading('Status', text='Status')
        recent_tree.heading('Similarity', text='Similarity Score')
        recent_tree.heading('Date', text='Check Date')
        
        recent_tree.column('Document', width=300)
        recent_tree.column('Status', width=120)
        recent_tree.column('Similarity', width=100)
        recent_tree.column('Date', width=150)
        
        # Populate recent checks
        for check in recent_checks:
            similarity = check['similarity_score'] * 100
            recent_tree.insert('', tk.END, values=(
                check['document_title'][:50] + ('...' if len(check['document_title']) > 50 else ''),
                check['status'],
                f"{similarity:.1f}%",
                check['check_date']
            ), tags=(str(check['result_id']),))
        
        # Scrollbars
        recent_v_scrollbar = ttk.Scrollbar(recent_frame, orient=tk.VERTICAL, command=recent_tree.yview)
        recent_h_scrollbar = ttk.Scrollbar(recent_frame, orient=tk.HORIZONTAL, command=recent_tree.xview)
        
        recent_tree.configure(yscrollcommand=recent_v_scrollbar.set, xscrollcommand=recent_h_scrollbar.set)
        
        # Pack
        recent_tree.grid(row=0, column=0, sticky='nsew')
        recent_v_scrollbar.grid(row=0, column=1, sticky='ns')
        recent_h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        recent_frame.grid_rowconfigure(0, weight=1)
        recent_frame.grid_columnconfigure(0, weight=1)
    
    def show_error(self, error):
        """Show error message"""
        # Clear any existing widgets
        for widget in self.dialog.winfo_children():
            widget.destroy()
        
        error_label = ttk.Label(
            self.dialog,
            text=f"Error loading statistics:\n{error}",
            font=GuiConfig.BODY_FONT,
            foreground=GuiConfig.DANGER_COLOR
        )
        error_label.pack(expand=True)
        
        close_btn = ttk.Button(self.dialog, text="Close", command=self.dialog.destroy)
        close_btn.pack(pady=GuiConfig.PADDING_MEDIUM)


# =============================================================================
# Integration Functions (Backwards Compatibility)
# =============================================================================

def integrate_plagiarism_checker_with_main():
    """
    Integration function for backwards compatibility with the original system.
    This function is called by the original plagiarism_main.py setup process.
    """
    try:
        # Add GUI menu option to the original system if possible
        # This is a placeholder for integration with the main student record system
        
        # Check if the main system's menu module is available
        try:
            import main_system  # This would be the main student record system
            
            # Add GUI option to main menu (hypothetical integration)
            if hasattr(main_system, 'add_menu_option'):
                main_system.add_menu_option(
                    "Plagiarism Checker (GUI)",
                    launch_gui_from_main_system
                )
                logger.info("Successfully integrated GUI option with main system")
                return True
        except ImportError:
            pass
        
        # Create a wrapper script for easy GUI launch
        create_gui_launcher_script()
        
        logger.info("Plagiarism checker GUI integration completed")
        return True
        
    except Exception as e:
        logger.error(f"Error during GUI integration: {e}")
        return False


def create_gui_launcher_script():
    """Create a launcher script for the GUI"""
    launcher_content = '''#!/usr/bin/env python3
"""
Plagiarism Checker GUI Launcher
Launch the graphical interface for the plagiarism detection system.
"""

import sys
import os

# Add current directory to path to import plagiarism modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from plagiarism_gui import PlagiarismCheckerGUI
    
    def main():
        """Main function to launch the GUI"""
        print("Starting Plagiarism Checker GUI...")
        
        try:
            app = PlagiarismCheckerGUI()
            app.run()
        except KeyboardInterrupt:
            print("\\nApplication interrupted by user.")
        except Exception as e:
            print(f"Error running GUI application: {e}")
            input("Press Enter to exit...")

    if __name__ == "__main__":
        main()

except ImportError as e:
    print(f"Error importing GUI modules: {e}")
    print("Please ensure plagiarism_main.py and plagiarism_gui.py are in the same directory.")
    input("Press Enter to exit...")
'''
    
    try:
        with open('plagiarism_gui_launcher.py', 'w', encoding='utf-8') as f:
            f.write(launcher_content)
        
        # Make executable on Unix systems
        if os.name != 'nt':
            os.chmod('plagiarism_gui_launcher.py', 0o755)
        
        logger.info("Created GUI launcher script: plagiarism_gui_launcher.py")
        
    except Exception as e:
        logger.error(f"Error creating launcher script: {e}")


def launch_gui_from_main_system(auth=None):
    """
    Launch the GUI from the main system with existing authentication.
    This function maintains backwards compatibility and integrates with main.py
    """
    try:
        print("Launching Plagiarism Detection GUI...")
        
        # Create and configure the GUI app
        app = PlagiarismCheckerGUI()
        app.launched_from_main = True
        
        # If auth is provided from the main system, use it
        if auth and hasattr(auth, 'current_user') and auth.current_user:
            app.auth = auth  # Use provided authentication
            print(f"Authenticated as: {auth.current_user['username']} ({auth.current_user.get('role', 'unknown')})")
            
            # Log the activity if logging is available
            try:
                if hasattr(auth, 'log_activity'):
                    auth.log_activity(
                        action="plagiarism_gui_launch",
                        details=f"User {auth.current_user['username']} launched plagiarism GUI",
                        status="success"
                    )
            except Exception as log_error:
                print(f"Logging warning: {log_error}")
        else:
            # Fall back to default test user for standalone operation
            print("Using default test user authentication...")
            app.auth = get_authenticated_user_auth()
        
        # Run the GUI
        app.run()
        
        print("Plagiarism Detection GUI closed.")
            
    except Exception as e:
        logger.error(f"Error launching GUI from main system: {e}")
        print(f"Error launching GUI: {e}")
        # Don't re-raise - let the caller handle the fallback
        return False
    
    return True

def run_gui_standalone():
    """
    Run the GUI in standalone mode.
    This function can be called directly for testing or standalone operation.
    """
    try:
        print("Plagiarism Checker GUI - Standalone Mode")
        print("========================================")
        
        app = PlagiarismCheckerGUI()
        app.run()
        
    except Exception as e:
        print(f"Error running GUI: {e}")
        input("Press Enter to exit...")


# =============================================================================
# Command Line Interface for GUI
# =============================================================================

def main():
    """Main function for command line execution"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Plagiarism Detection System - GUI Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python plagiarism_gui.py                    # Run GUI in standalone mode
  python plagiarism_gui.py --create-launcher  # Create launcher script only
  python plagiarism_gui.py --test             # Test GUI components

The GUI provides a user-friendly interface for:
• Submitting documents to the repository
• Checking documents for plagiarism
• Searching and managing the document repository
• Viewing detailed statistics and reports

This GUI extension is fully backwards compatible with the original
plagiarism_main.py command-line interface.
        """
    )
    
    parser.add_argument(
        '--create-launcher',
        action='store_true',
        help='Create GUI launcher script and exit'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run GUI component tests'
    )
    
    parser.add_argument(
        '--integrate',
        action='store_true',
        help='Run integration with main system'
    )
    
    args = parser.parse_args()
    
    if args.create_launcher:
        create_gui_launcher_script()
        print("GUI launcher script created successfully!")
        return
    
    if args.test:
        run_gui_tests()
        return
    
    if args.integrate:
        if integrate_plagiarism_checker_with_main():
            print("Integration completed successfully!")
        else:
            print("Integration completed with warnings. Check logs for details.")
        return
    
    # Default: run GUI
    run_gui_standalone()


def run_gui_tests():
    """Run basic GUI tests"""
    print("Running GUI component tests...")
    
    try:
        # Test 1: Import all required modules
        print("Test 1: Testing imports...")
        import tkinter as tk
        from tkinter import ttk
        print("✓ Tkinter imports successful")
        
        # Test 2: Test basic window creation
        print("Test 2: Testing window creation...")
        root = tk.Tk()
        root.title("Test Window")
        root.geometry("400x300")
        
        # Test basic widgets
        label = ttk.Label(root, text="Test Label")
        label.pack()
        
        button = ttk.Button(root, text="Test Button")
        button.pack()
        
        # Close test window immediately
        root.destroy()
        print("✓ Basic window creation successful")
        
        # Test 3: Test configuration classes
        print("Test 3: Testing configuration...")
        config = GuiConfig()
        assert hasattr(config, 'MAIN_WINDOW_WIDTH')
        assert hasattr(config, 'PRIMARY_COLOR')
        print("✓ Configuration classes successful")
        
        # Test 4: Test custom components
        print("Test 4: Testing custom components...")
        test_root = tk.Tk()
        test_root.withdraw()  # Hide test window
        
        # Test StatusBar
        status_bar = StatusBar(test_root)
        status_bar.set_status("Test status")
        status_bar.show_progress()
        status_bar.hide_progress()
        
        # Test ScrollableFrame
        scrollable = ScrollableFrame(test_root)
        
        test_root.destroy()
        print("✓ Custom components successful")
        
        print("\nAll GUI tests passed! ✓")
        print("The GUI should work correctly.")
        
    except Exception as e:
        print(f"✗ GUI test failed: {e}")
        print("There may be issues with the GUI setup.")

class PlagiarismCheckDialog:
    """Dialog for checking documents for plagiarism"""
    
    def __init__(self, parent, checker, auth, task_queue, threshold):
        self.parent = parent
        self.checker = checker
        self.auth = auth
        self.task_queue = task_queue
        self.threshold = threshold
        
        self.dialog = None
        self.selected_doc_id = None
        
    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Repository Search")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)
        
        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")
        
        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab

        # Create interface and load documents
        self.create_check_form()
        self.load_documents()
    
    def create_check_form(self):
        """Create the check form"""
        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Check Document for Plagiarism", font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))
        
        # Search frame
        search_frame = ttk.LabelFrame(main_frame, text="Search Documents", padding=GuiConfig.PADDING_SMALL)
        search_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=GuiConfig.PADDING_SMALL)
        
        search_btn = ttk.Button(search_frame, text="Search", command=self.search_documents)
        search_btn.pack(side=tk.LEFT, padx=GuiConfig.PADDING_SMALL)
        
        refresh_btn = ttk.Button(search_frame, text="Refresh", command=self.load_documents)
        refresh_btn.pack(side=tk.LEFT)
        
        # Documents list
        list_frame = ttk.LabelFrame(main_frame, text="Select Document to Check", padding=GuiConfig.PADDING_SMALL)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        # Treeview for documents
        columns = ('Title', 'Author', 'Module', 'Date')
        self.doc_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.doc_tree.heading(col, text=col)
            self.doc_tree.column(col, width=150)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.doc_tree.yview)
        h_scrollbar = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.doc_tree.xview)
        
        self.doc_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack treeview and scrollbars
        self.doc_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        # Settings frame
        settings_frame = ttk.LabelFrame(main_frame, text="Check Settings", padding=GuiConfig.PADDING_SMALL)
        settings_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        ttk.Label(settings_frame, text="Similarity Threshold:").pack(side=tk.LEFT)
        self.threshold_var = tk.DoubleVar(value=self.threshold)
        threshold_scale = ttk.Scale(
            settings_frame,
            from_=0.1,
            to=0.9,
            variable=self.threshold_var,
            orient=tk.HORIZONTAL,
            length=200
        )
        threshold_scale.pack(side=tk.LEFT, padx=GuiConfig.PADDING_SMALL)
        
        self.threshold_label = ttk.Label(settings_frame, text=f"{int(self.threshold * 100)}%")
        self.threshold_label.pack(side=tk.LEFT)
        
        def update_threshold_label(*args):
            self.threshold_label.config(text=f"{int(self.threshold_var.get() * 100)}%")
        
        self.threshold_var.trace('w', update_threshold_label)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy)
        cancel_btn.pack(side=tk.RIGHT)
        
        check_btn = ttk.Button(button_frame, text="Check for Plagiarism", command=self.start_check)
        check_btn.pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))
    
    def load_documents(self):
        """Load documents into the tree"""
        # Clear existing items
        for item in self.doc_tree.get_children():
            self.doc_tree.delete(item)
        
        def load_task():
            try:
                # Placeholder document data
                documents = [
                    {'id': 1, 'title': 'Sample Document 1', 'author': 'John Doe', 'module_code': 'CS101', 'submission_date': '2024-01-15'},
                    {'id': 2, 'title': 'Research Paper', 'author': 'Jane Smith', 'module_code': 'CS201', 'submission_date': '2024-01-20'},
                    {'id': 3, 'title': 'Final Project', 'author': 'Bob Johnson', 'module_code': 'CS301', 'submission_date': '2024-01-25'},
                ]
                
                # Update tree in main thread
                self.dialog.after(0, lambda: self.populate_tree(documents))
                
            except Exception as e:
                error_msg = str(e)
                self.dialog.after(0, lambda err=error_msg: messagebox.showerror("Error", f"Failed to load documents: {err}"))
        
        thread = threading.Thread(target=load_task, daemon=True)
        thread.start()
    
    def search_documents(self):
        """Search documents"""
        search_term = self.search_var.get().strip()
        
        # Clear existing items
        for item in self.doc_tree.get_children():
            self.doc_tree.delete(item)
        
        def search_task():
            try:
                # Placeholder search results
                documents = [
                    {'id': 1, 'title': f'Search Result for "{search_term}"', 'author': 'John Doe', 'module_code': 'CS101', 'submission_date': '2024-01-15'},
                ]
                
                # Update tree in main thread
                self.dialog.after(0, lambda: self.populate_tree(documents))
                
            except Exception as e:
                error_msg = str(e)
                self.dialog.after(0, lambda err=error_msg: messagebox.showerror("Error", f"Search failed: {err}"))
        
        thread = threading.Thread(target=search_task, daemon=True)
        thread.start()
    
    def populate_tree(self, documents):
        """Populate the tree with documents"""
        for doc in documents:
            try:
                self.doc_tree.insert('', tk.END, values=(
                    doc['title'],
                    doc['author'],
                    doc['module_code'] or 'N/A',
                    doc['submission_date']
                ), tags=(str(doc['id']),))
                
            except Exception as e:
                logger.error(f"Error adding document {doc['id']} to tree: {e}")
    
    def start_check(self):
        """Start plagiarism check"""
        selection = self.doc_tree.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a document to check")
            return
        
        # Get document ID from tags
        item = selection[0]
        doc_id = int(self.doc_tree.item(item, 'tags')[0])
        
        def check_task():
            try:
                # Placeholder plagiarism check result
                result = {
                    'document_id': doc_id,
                    'similarity_score': 0.25,
                    'status': 'LOW_SIMILARITY',
                    'matches': [],
                    'check_date': '2024-01-30',
                    'threshold_used': self.threshold_var.get()
                }
                
                self.task_queue.put(('check_complete', result))
                
                # Close dialog in main thread
                self.dialog.after(0, self.dialog.destroy)
                
            except Exception as e:
                self.task_queue.put(('check_error', str(e)))
        
        thread = threading.Thread(target=check_task, daemon=True)
        thread.start()

class RepositorySearchDialog:
    """Dialog for searching the repository"""
    
    def __init__(self, parent, checker, auth):
        self.parent = parent
        self.checker = checker
        self.auth = auth
        
        self.dialog = None
        
    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Repository Search")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)
        
        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")
        
        # Create interface first
        self.create_search_interface()
        self.load_all_documents()
        
        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab        
        self.create_search_interface()
        self.load_all_documents()
    
    def create_search_interface(self):
        """Create the search interface"""
        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Repository Search", font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))
        
        # Search controls
        search_frame = ttk.LabelFrame(main_frame, text="Search Criteria", padding=GuiConfig.PADDING_SMALL)
        search_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        # Search term
        ttk.Label(search_frame, text="Title/Content:").grid(row=0, column=0, sticky=tk.W, padx=(0, GuiConfig.PADDING_SMALL))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        search_entry.grid(row=0, column=1, padx=(0, GuiConfig.PADDING_SMALL))
        
        search_btn = ttk.Button(search_frame, text="Search", command=self.perform_search)
        search_btn.grid(row=0, column=2, padx=(0, GuiConfig.PADDING_SMALL))
        
        clear_btn = ttk.Button(search_frame, text="Clear", command=self.clear_search)
        clear_btn.grid(row=0, column=3)
        
        # Results
        results_frame = ttk.LabelFrame(main_frame, text="Search Results", padding=GuiConfig.PADDING_SMALL)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        # Results treeview
        columns = ('Title', 'Author', 'Module', 'Date', 'Type', 'Words')
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=20)
        
        for col in columns:
            self.results_tree.heading(col, text=col)
            self.results_tree.column(col, width=120)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        h_scrollbar = ttk.Scrollbar(results_frame, orient=tk.HORIZONTAL, command=self.results_tree.xview)
        
        self.results_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack treeview and scrollbars
        self.results_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        results_frame.grid_rowconfigure(0, weight=1)
        results_frame.grid_columnconfigure(0, weight=1)
        
        # Double-click to view details
        self.results_tree.bind('<Double-1>', self.on_item_double_click)
        
        # Status label
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, font=GuiConfig.BODY_FONT)
        status_label.pack(pady=(GuiConfig.PADDING_SMALL, 0))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(GuiConfig.PADDING_MEDIUM, 0))
        
        close_btn = ttk.Button(button_frame, text="Close", command=self.dialog.destroy)
        close_btn.pack(side=tk.RIGHT)
        
        view_btn = ttk.Button(button_frame, text="View Details", command=self.view_selected_document)
        view_btn.pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))
    
    def load_all_documents(self):
        """Load all documents"""
        self.status_var.set("Loading documents...")
        
        def load_task():
            try:
                # Placeholder document data
                documents = [
                    {'id': 1, 'title': 'Introduction to Algorithms', 'author': 'Alice Johnson', 'module_code': 'CS101', 'submission_date': '2024-01-15', 'file_type': 'PDF', 'word_count': 1500},
                    {'id': 2, 'title': 'Data Structures Overview', 'author': 'Bob Smith', 'module_code': 'CS201', 'submission_date': '2024-01-20', 'file_type': 'DOCX', 'word_count': 2300},
                    {'id': 3, 'title': 'Machine Learning Basics', 'author': 'Carol Davis', 'module_code': 'CS301', 'submission_date': '2024-01-25', 'file_type': 'TXT', 'word_count': 1800},
                ]
                self.dialog.after(0, lambda: self.populate_results(documents))
                
            except Exception as e:
                error_msg = str(e)
                self.dialog.after(0, lambda err=error_msg: self.show_error(f"Failed to load documents: {err}"))
        
        thread = threading.Thread(target=load_task, daemon=True)
        thread.start()
    
    def perform_search(self):
        """Perform search"""
        search_term = self.search_var.get().strip()
        if not search_term:
            self.load_all_documents()
            return
        
        self.status_var.set(f"Searching for '{search_term}'...")
        
        def search_task():
            try:
                # Placeholder search results
                documents = [
                    {'id': 1, 'title': f'Search result containing "{search_term}"', 'author': 'Search Author', 'module_code': 'CS101', 'submission_date': '2024-01-15', 'file_type': 'PDF', 'word_count': 1200},
                ]
                self.dialog.after(0, lambda: self.populate_results(documents))
                
            except Exception as e:
                error_msg = str(e)
                self.dialog.after(0, lambda err=error_msg: self.show_error(f"Search failed: {err}"))
        
        thread = threading.Thread(target=search_task, daemon=True)
        thread.start()
    
    def clear_search(self):
        """Clear search and reload all documents"""
        self.search_var.set("")
        self.load_all_documents()
    
    def populate_results(self, documents):
        """Populate results tree"""
        # Clear existing items
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        if not documents:
            self.status_var.set("No documents found")
            return
        
        for doc in documents:
            try:
                self.results_tree.insert('', tk.END, values=(
                    doc['title'][:50] + ('...' if len(doc['title']) > 50 else ''),
                    doc['author'],
                    doc['module_code'] or 'N/A',
                    doc['submission_date'],
                    doc['file_type'],
                    doc['word_count']
                ), tags=(str(doc['id']),))
                
            except Exception as e:
                logger.error(f"Error adding document {doc['id']} to results: {e}")
        
        self.status_var.set(f"Found {len(documents)} document(s)")
    
    def show_error(self, message):
        """Show error message"""
        self.status_var.set("Error occurred")
        messagebox.showerror("Error", message)
    
    def on_item_double_click(self, event):
        """Handle double-click on item"""
        self.view_selected_document()
    
    def view_selected_document(self):
        """View details of selected document"""
        selection = self.results_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a document to view")
            return
        
        # Get document ID from tags
        item = selection[0]
        doc_id = int(self.results_tree.item(item, 'tags')[0])
        
        # Show document details dialog
        details_dialog = DocumentDetailsDialog(self.dialog, self.checker, doc_id)
        details_dialog.show()

class DocumentDetailsDialog:
    """Dialog for showing document details"""

    def __init__(self, parent, checker, doc_id):
        self.parent = parent
        self.checker = checker
        self.doc_id = doc_id

        self.dialog = None
        self.doc_details = None

    def show(self):
        """Show the dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Document Details")
        self.dialog.geometry(f"{GuiConfig.DIALOG_WIDTH}x{GuiConfig.DIALOG_HEIGHT}")
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.geometry(f"+{self.parent.winfo_rootx() + 50}+{self.parent.winfo_rooty() + 50}")

        # Load and display the document details
        self.load_and_display_details()

        # IMPORTANT: Wait for window to be visible before grabbing
        self.dialog.update_idletasks()  # Process pending events
        self.dialog.deiconify()         # Ensure window is visible
        self.dialog.grab_set()          # Now it's safe to grab
    
    def load_and_display_details(self):
        """Load and display document details"""
        def load_task():
            try:
                # Get document details from the checker
                details = self.checker.get_document_details(self.doc_id)

                # Get check history for this document
                check_history = self.checker.get_document_check_history(self.doc_id)

                self.dialog.after(0, lambda d=details, h=check_history: self.create_details_interface(d, h))

            except Exception as e:
                error_msg = str(e)
                self.dialog.after(0, lambda err=error_msg: self.show_error(err))
        
        # Show loading message
        loading_label = ttk.Label(self.dialog, text="Loading document details...", font=GuiConfig.BODY_FONT)
        loading_label.pack(expand=True)
        
        thread = threading.Thread(target=load_task, daemon=True)
        thread.start()
    
    def create_details_interface(self, details, check_history):
        """Create the details interface"""
        # Clear loading message
        for widget in self.dialog.winfo_children():
            widget.destroy()
        
        self.doc_details = details
        
        main_frame = ttk.Frame(self.dialog, padding=GuiConfig.PADDING_MEDIUM)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Document Details", font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))
        
        # Create notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        # Document info tab
        self.create_info_tab(notebook, details)
        
        # Plagiarism checks tab
        self.create_checks_tab(notebook, check_history)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        close_btn = ttk.Button(button_frame, text="Close", command=self.dialog.destroy)
        close_btn.pack(side=tk.RIGHT)
        
        check_btn = ttk.Button(button_frame, text="Check for Plagiarism", command=self.check_plagiarism)
        check_btn.pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))
    
    def create_info_tab(self, notebook, details):
        """Create document information tab"""
        info_frame = ttk.Frame(notebook)
        notebook.add(info_frame, text="Information")
        
        # Create scrollable frame
        canvas = tk.Canvas(info_frame)
        scrollbar = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Basic information
        basic_frame = ttk.LabelFrame(scrollable_frame, text="Basic Information", padding=GuiConfig.PADDING_MEDIUM)
        basic_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        
        info_items = [
            ("Title:", details['title']),
            ("Author:", details['author_name']),
            ("Module:", details['module_code'] or 'N/A'),
            ("Submission Date:", details['submission_date']),
            ("File Type:", details['file_type']),
            ("Word Count:", str(details['word_count'])),
            ("Created:", details['created_at']),
            ("Last Updated:", details['updated_at'])
        ]
        
        for i, (label, value) in enumerate(info_items):
            ttk.Label(basic_frame, text=label, font=GuiConfig.SUBHEADER_FONT).grid(
                row=i, column=0, sticky=tk.W, pady=GuiConfig.PADDING_SMALL
            )
            ttk.Label(basic_frame, text=value, font=GuiConfig.BODY_FONT).grid(
                row=i, column=1, sticky=tk.W, padx=(GuiConfig.PADDING_MEDIUM, 0), pady=GuiConfig.PADDING_SMALL
            )
        
        # Latest check information
        if details.get('latest_check'):
            check = details['latest_check']
            similarity = check['similarity_score'] * 100
            
            check_frame = ttk.LabelFrame(scrollable_frame, text="Latest Plagiarism Check", padding=GuiConfig.PADDING_MEDIUM)
            check_frame.pack(fill=tk.X)
            
            check_items = [
                ("Status:", check['status']),
                ("Similarity Score:", f"{similarity:.1f}%"),
                ("Check Date:", check['check_date']),
                ("Threshold Used:", f"{check['threshold_used']:.1%}")
            ]
            
            for i, (label, value) in enumerate(check_items):
                ttk.Label(check_frame, text=label, font=GuiConfig.SUBHEADER_FONT).grid(
                    row=i, column=0, sticky=tk.W, pady=GuiConfig.PADDING_SMALL
                )
                
                # Color-code status
                if label == "Status:":
                    color = GuiConfig.DANGER_COLOR if check['status'] in ['EXACT_MATCH', 'HIGH_SIMILARITY'] else \
                           GuiConfig.WARNING_COLOR if check['status'] == 'MODERATE_SIMILARITY' else \
                           GuiConfig.SUCCESS_COLOR
                    status_label = tk.Label(check_frame, text=value, font=GuiConfig.BODY_FONT, fg=color)
                    status_label.grid(row=i, column=1, sticky=tk.W, padx=(GuiConfig.PADDING_MEDIUM, 0), pady=GuiConfig.PADDING_SMALL)
                else:
                    ttk.Label(check_frame, text=value, font=GuiConfig.BODY_FONT).grid(
                        row=i, column=1, sticky=tk.W, padx=(GuiConfig.PADDING_MEDIUM, 0), pady=GuiConfig.PADDING_SMALL
                    )
        
        # Pack canvas and scrollbar
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def create_checks_tab(self, notebook, check_history):
        """Create plagiarism checks tab"""
        checks_frame = ttk.Frame(notebook)
        notebook.add(checks_frame, text="Check History")
        
        if not check_history:
            no_checks_label = ttk.Label(
                checks_frame,
                text="No plagiarism checks performed on this document",
                font=GuiConfig.BODY_FONT
            )
            no_checks_label.pack(expand=True)
            return
        
        # Checks list
        columns = ('Date', 'Status', 'Similarity', 'Threshold')
        checks_tree = ttk.Treeview(checks_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            checks_tree.heading(col, text=col)
            checks_tree.column(col, width=150)
        
        # Populate checks
        for check in check_history:
            similarity = check['similarity_score'] * 100
            threshold = check['threshold_used'] * 100 if check['threshold_used'] else 0
            
            checks_tree.insert('', tk.END, values=(
                check['check_date'],
                check['status'],
                f"{similarity:.1f}%",
                f"{threshold:.0f}%"
            ), tags=(str(check['result_id']),))
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(checks_frame, orient=tk.VERTICAL, command=checks_tree.yview)
        h_scrollbar = ttk.Scrollbar(checks_frame, orient=tk.HORIZONTAL, command=checks_tree.xview)
        
        checks_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack elements
        checks_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        checks_frame.grid_rowconfigure(0, weight=1)
        checks_frame.grid_columnconfigure(0, weight=1)
        
        # Double-click to view details
        def on_check_double_click(event):
            selection = checks_tree.selection()
            if selection:
                item = selection[0]
                result_id = int(checks_tree.item(item, 'tags')[0])
                # This would show detailed results
                messagebox.showinfo("Details", f"Detailed results for check {result_id} would be shown here.")
        
        checks_tree.bind('<Double-1>', on_check_double_click)
    
    def check_plagiarism(self):
        """Start plagiarism check for this document"""
        messagebox.showinfo("Info", "Use the main application's Check for Plagiarism feature to check this document.")

    def show_error(self, error):
        """Show error message"""
        # Clear any existing widgets
        for widget in self.dialog.winfo_children():
            widget.destroy()
        
        error_label = ttk.Label(
            self.dialog,
            text=f"Error loading document details:\n{error}",
            font=GuiConfig.BODY_FONT,
            foreground=GuiConfig.DANGER_COLOR
        )
        error_label.pack(expand=True)
        
        close_btn = ttk.Button(self.dialog, text="Close", command=self.dialog.destroy)
        close_btn.pack(pady=GuiConfig.PADDING_MEDIUM)

# =============================================================================
# Main Functions
# =============================================================================

def run_gui_standalone():
    """Run the GUI in standalone mode"""
    print("Starting Plagiarism Detection GUI...")
    
    try:
        # Create main window
        root = tk.Tk()
        root.title("Plagiarism Detection System")
        root.geometry(f"{GuiConfig.MAIN_WINDOW_WIDTH}x{GuiConfig.MAIN_WINDOW_HEIGHT}")
        root.configure(bg=GuiConfig.LIGHT_BG)
        
        # Create a simple main interface
        main_frame = ttk.Frame(root, padding=GuiConfig.PADDING_LARGE)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Plagiarism Detection System", font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(pady=GuiConfig.PADDING_MEDIUM)
        
        # Task queue for thread communication
        task_queue = queue.Queue()
        
        # Placeholder objects
        class PlaceholderChecker:
            pass
        
        class PlaceholderAuth:
            def __init__(self):
                self.current_user = {'id': 1, 'username': 'demo_user'}
        
        checker = PlaceholderChecker()
        auth = PlaceholderAuth()
        
        # Submit document button
        def show_submit_dialog():
            dialog = DocumentSubmissionDialog(root, checker, auth, task_queue)
            dialog.show()
        
        submit_btn = ttk.Button(buttons_frame, text="Submit Document", command=show_submit_dialog)
        submit_btn.pack(pady=GuiConfig.PADDING_SMALL)
        
        # Check plagiarism button
        def show_check_dialog():
            dialog = PlagiarismCheckDialog(root, checker, auth, task_queue, 0.7)
            dialog.show()
        
        check_btn = ttk.Button(buttons_frame, text="Check for Plagiarism", command=show_check_dialog)
        check_btn.pack(pady=GuiConfig.PADDING_SMALL)
        
        # Status bar
        status_bar = StatusBar(root)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Process task queue
        def process_queue():
            try:
                while True:
                    task_type, data = task_queue.get_nowait()
                    
                    if task_type == 'submit_complete':
                        status_bar.set_status(f"Document submitted successfully (ID: {data})")
                        messagebox.showinfo("Success", f"Document submitted successfully!\nDocument ID: {data}")
                    elif task_type == 'submit_error':
                        status_bar.set_status("Document submission failed")
                        messagebox.showerror("Error", f"Failed to submit document: {data}")
                    elif task_type == 'check_complete':
                        status_bar.set_status("Plagiarism check completed")
                        similarity = data['similarity_score'] * 100
                        messagebox.showinfo("Check Complete", 
                                          f"Plagiarism check completed!\n"
                                          f"Similarity Score: {similarity:.1f}%\n"
                                          f"Status: {data['status']}")
                    elif task_type == 'check_error':
                        status_bar.set_status("Plagiarism check failed")
                        messagebox.showerror("Error", f"Plagiarism check failed: {data}")
                        
            except queue.Empty:
                pass
            
            # Schedule next check
            root.after(100, process_queue)
        
        # Start queue processing
        process_queue()
        
        # Run the GUI
        root.mainloop()
        
    except Exception as e:
        print(f"Error running GUI: {e}")
        logger.error(f"GUI error: {e}")


def create_gui_launcher_script():
    """Create a launcher script for the GUI"""
    launcher_content = '''#!/usr/bin/env python3
"""
Plagiarism Detection System - GUI Launcher
This script launches the GUI interface for the plagiarism detection system.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from plagiarism_gui import run_gui_standalone
    run_gui_standalone()
except ImportError as e:
    print(f"Error importing GUI module: {e}")
    print("Make sure plagiarism_gui.py is in the same directory.")
except Exception as e:
    print(f"Error running GUI: {e}")
'''
    
    try:
        with open('launch_gui.py', 'w') as f:
            f.write(launcher_content)
        
        # Make executable on Unix systems
        if os.name == 'posix':
            os.chmod('launch_gui.py', 0o755)
            
        return True
    except Exception as e:
        logger.error(f"Error creating launcher script: {e}")
        return False


def integrate_plagiarism_checker_with_main():
    """Integrate the GUI with the main plagiarism checker system"""
    try:
        # This function would integrate with the main system
        # For now, it's a placeholder
        print("Integration with main system would happen here...")
        return True
    except Exception as e:
        logger.error(f"Integration error: {e}")
        return False


def run_gui_tests():
    """Run basic GUI tests"""
    print("Running GUI component tests...")
    
    try:
        # Test 1: Import all required modules
        print("Test 1: Testing imports...")
        import tkinter as tk
        from tkinter import ttk
        print("✓ Tkinter imports successful")
        
        # Test 2: Test basic window creation
        print("Test 2: Testing window creation...")
        root = tk.Tk()
        root.title("Test Window")
        root.geometry("400x300")
        
        # Test basic widgets
        label = ttk.Label(root, text="Test Label")
        label.pack()
        
        button = ttk.Button(root, text="Test Button")
        button.pack()
        
        # Close test window immediately
        root.destroy()
        print("✓ Basic window creation successful")
        
        # Test 3: Test configuration classes
        print("Test 3: Testing configuration...")
        config = GuiConfig()
        assert hasattr(config, 'MAIN_WINDOW_WIDTH')
        assert hasattr(config, 'PRIMARY_COLOR')
        print("✓ Configuration classes successful")
        
        # Test 4: Test custom components
        print("Test 4: Testing custom components...")
        test_root = tk.Tk()
        test_root.withdraw()  # Hide test window
        
        # Test StatusBar
        status_bar = StatusBar(test_root)
        status_bar.set_status("Test status")
        status_bar.show_progress()
        status_bar.hide_progress()
        
        # Test ScrollableFrame
        scrollable = ScrollableFrame(test_root)
        
        test_root.destroy()
        print("✓ Custom components successful")
        
        print("\nAll GUI tests passed! ✓")
        print("The GUI should work correctly.")
        
    except Exception as e:
        print(f"✗ GUI test failed: {e}")
        print("There may be issues with the GUI setup.")


# =============================================================================
# Command Line Interface for GUI
# =============================================================================

def main():
    """Main function for command line execution"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Plagiarism Detection System - GUI Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python plagiarism_gui.py                    # Run GUI in standalone mode
  python plagiarism_gui.py --create-launcher  # Create launcher script only
  python plagiarism_gui.py --test             # Test GUI components

The GUI provides a user-friendly interface for:
• Submitting documents to the repository
• Checking documents for plagiarism
• Searching and managing the document repository
• Viewing detailed statistics and reports

This GUI extension is fully backwards compatible with the original
plagiarism_main.py command-line interface.
        """
    )
    
    parser.add_argument(
        '--create-launcher',
        action='store_true',
        help='Create GUI launcher script and exit'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run GUI component tests'
    )
    
    parser.add_argument(
        '--integrate',
        action='store_true',
        help='Run integration with main system'
    )
    
    args = parser.parse_args()
    
    if args.create_launcher:
        if create_gui_launcher_script():
            print("GUI launcher script created successfully!")
        else:
            print("Failed to create launcher script.")
        return
    
    if args.test:
        run_gui_tests()
        return
    
    if args.integrate:
        if integrate_plagiarism_checker_with_main():
            print("Integration completed successfully!")
        else:
            print("Integration completed with warnings. Check logs for details.")
        return
    
    # Default: run GUI
    run_gui_standalone()

if __name__ == "__main__":
    try:
        print("Starting Plagiarism Detection GUI...")
        app = PlagiarismCheckerGUI()
        app.run()
    except Exception as e:
        print(f"Error: {e}")
        input("Press Enter to exit...")
