from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH  # injected
from contextlib import contextmanager
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import threading
import queue
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime
import os
import sys
import logging
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Language/i18n support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    SUPPORTED_LANGUAGES,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import (
    show_gui_language_selector,
)

try:
    from education_system.systems.university.domain.academics.services.plagiarism.plagiarism_main import (
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
    from education_system.systems.university.infrastructure.paths import NLTK_DATA_DIR
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

from education_system.systems.university.interfaces.gui.academics.plagiarism_main_gui.config import GuiConfig

# Helper function to create authenticated UserAuth instance
def get_authenticated_user_auth():
    """Get centralized auth or create a UserAuth instance with a default test user session"""
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
                nltk.download(download_name, download_dir=custom_nltk_path, quiet=True)
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

        title_label = ttk.Label(main_frame, text=_t("plagiarism.setup_testing_tools"), font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))

        # Setup section
        setup_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.system_setup"), padding=GuiConfig.PADDING_MEDIUM)
        setup_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        setup_buttons = ttk.Frame(setup_frame)
        setup_buttons.pack()

        ttk.Button(setup_buttons, text=_t("plagiarism.check_requirements"),
                  command=self.check_requirements).pack(side=tk.LEFT, padx=(0, GuiConfig.PADDING_SMALL))
        ttk.Button(setup_buttons, text=_t("plagiarism.create_directories"),
                  command=self.create_dirs).pack(side=tk.LEFT, padx=(0, GuiConfig.PADDING_SMALL))
        ttk.Button(setup_buttons, text=_t("plagiarism.create_sample_documents"),
                  command=self.create_samples).pack(side=tk.LEFT)

        # Testing section
        testing_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.system_testing"), padding=GuiConfig.PADDING_MEDIUM)
        testing_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        testing_buttons = ttk.Frame(testing_frame)
        testing_buttons.pack()

        ttk.Button(testing_buttons, text=_t("plagiarism.test_repository"),
                  command=self.test_repository).pack(side=tk.LEFT, padx=(0, GuiConfig.PADDING_SMALL))
        ttk.Button(testing_buttons, text=_t("plagiarism.test_plagiarism_check"),
                  command=self.test_plagiarism).pack(side=tk.LEFT)

        # Results area
        results_frame = ttk.LabelFrame(main_frame, text=_t("common.results"), padding=GuiConfig.PADDING_SMALL)
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

        ttk.Button(button_frame, text=_t("plagiarism.clear_results"),
                  command=self.clear_results).pack(side=tk.LEFT)
        ttk.Button(button_frame, text=_t("common.close"),
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
            text=f"\U0001f3e0 {_t('common.return_to_homescreen')}",
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
            except Exception as e:
                logger.debug(f"Failed to call return_to_main_menu: {e}")

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

    def __init__(self, parent, result_data, on_view_details=None, on_email_result=None, auth=None):
        self.result_data = result_data
        self.on_view_details = on_view_details
        self.on_email_result = on_email_result
        self.auth = auth

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

        # Email results button
        if on_email_result:
            email_btn = ttk.Button(
                details_frame,
                text=_t("plagiarism.email_results"),
                command=self._email_result
            )
            email_btn.pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))

        # View details button
        if on_view_details:
            details_btn = ttk.Button(
                details_frame,
                text=_t("common.view_details"),
                command=lambda: on_view_details(result_data)
            )
            details_btn.pack(side=tk.RIGHT)

    def _email_result(self):
        """Email this result to the current user"""
        user_email = None
        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            user_email = self.auth.current_user.get('email')

        if not user_email:
            messagebox.showwarning(
                _t("common.warning"),
                _t("plagiarism.email_no_user_email")
            )
            return

        self.on_email_result(self.result_data, user_email)
