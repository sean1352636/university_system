from education_system.university_system.core.sql_safety import escape_like
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import threading
import queue
from datetime import datetime
import os
import sys
import logging

from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
)

from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.config import GuiConfig
from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.common import (
    logger,
    get_authenticated_user_auth,
    download_nltk_data,
    PLAGIARISM_BACKEND_AVAILABLE,
    PLAGIARISM_IMPORT_ERROR,
    PlagiarismChecker,
    TEXTRACT_AVAILABLE,
    StatusBar,
    ScrollableFrame,
    ResultCard,
    SetupTestingDialog,
    get_safe_db_connection,
)
from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.dialogs.submission import DocumentSubmissionDialog
from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.dialogs.check import PlagiarismCheckDialog
from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.dialogs.search import RepositorySearchDialog
from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.dialogs.advanced_search import AdvancedRepositorySearchDialog
from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.dialogs.bulk_operations import BulkOperationsDialog
from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.dialogs.system_testing import SystemTestingDialog
from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.dialogs.comparison import DocumentComparisonDialog
from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.dialogs.converter import FileFormatConverterDialog
from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.dialogs.backup_restore import BackupRestoreDialog
from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.dialogs.workflow import DocumentWorkflowDialog
from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.dialogs.results import CheckResultDialog, ResultDetailsDialog
from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.dialogs.statistics import StatisticsDialog
from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.dialogs.document_details import DocumentDetailsDialog

try:
    import textract
except ImportError:
    pass


class PlagiarismCheckerGUI:
    """Main GUI application for the plagiarism checker"""

    def __init__(self, parent=None, auth=None):
        # Use provided parent window or create new root
        if parent:
            self.root = parent
            self.launched_from_main = True
        else:
            self.root = tk.Tk()
            self.launched_from_main = False

        # Initialize i18n system
        init_i18n()

        self.root.title(_t("plagiarism.title"))
        self.root.geometry(f"{GuiConfig.MAIN_WINDOW_WIDTH}x{GuiConfig.MAIN_WINDOW_HEIGHT}")

        # Initialize components
        self.checker = None
        self.auth = auth  # Use provided auth or None
        self.task_queue = queue.Queue()
        self._task_after_id = None

        # Set up styles
        self.setup_styles()

        # Create GUI components
        self.create_menu()
        self.create_main_interface()
        self.create_status_bar()

        # Initialize system
        self.initialize_system()

        # Start periodic task processor
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
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
        menubar.add_cascade(label=_t("plagiarism.menu_file"), menu=file_menu)
        file_menu.add_command(label=_t("plagiarism.submit_document"), command=self.show_submit_dialog)
        file_menu.add_separator()
        file_menu.add_command(label=_t("plagiarism.import_documents"), command=self.import_documents)
        file_menu.add_command(label=_t("plagiarism.export_documents"), command=self.export_documents)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("plagiarism.menu_tools"), menu=tools_menu)
        tools_menu.add_command(label=_t("plagiarism.check_document"), command=self.show_check_dialog)
        tools_menu.add_command(label=_t("plagiarism.search_repository"), command=self.show_search_dialog)
        tools_menu.add_command(label=_t("plagiarism.view_my_documents"), command=self.show_my_documents)
        tools_menu.add_command(label=_t("plagiarism.view_results"), command=self.show_view_results)
        tools_menu.add_command(label=_t("plagiarism.advanced_search"), command=self.show_advanced_repository_search)
        tools_menu.add_command(label=_t("plagiarism.bulk_operations"), command=self.show_bulk_operations)
        tools_menu.add_separator()
        tools_menu.add_command(label=_t("plagiarism.system_testing"), command=self.show_system_testing)
        tools_menu.add_command(label=_t("plagiarism.generate_reports"), command=self.generate_reports_gui)
        tools_menu.add_command(label=_t("plagiarism.compare_documents"), command=self.show_document_comparison)
        tools_menu.add_command(label=_t("plagiarism.file_converter"), command=self.show_file_converter)
        tools_menu.add_command(label=_t("plagiarism.advanced_search"), command=self.show_advanced_repository_search)
        tools_menu.add_command(label=_t("plagiarism.bulk_operations"), command=self.show_bulk_operations)
        tools_menu.add_command(label=_t("plagiarism.document_workflow"), command=self.show_document_workflow)
        tools_menu.add_separator()
        tools_menu.add_command(label=_t("plagiarism.system_testing"), command=self.show_system_testing)
        tools_menu.add_command(label=_t("plagiarism.generate_reports"), command=self.generate_reports_gui)

        repo_menu = tk.Menu(tools_menu, tearoff=0)
        repo_menu.add_command(label=_t("plagiarism.delete_document"), command=self.show_delete_document_dialog)
        repo_menu.add_command(label=_t("plagiarism.check_repository_integrity"), command=self.show_repository_integrity_dialog)
        repo_menu.add_command(label=_t("plagiarism.check_integrity"), command=self.check_repository_integrity_gui)
        repo_menu.add_command(label=_t("plagiarism.backup_restore"), command=self.show_backup_restore)
        tools_menu.add_cascade(label=_t("plagiarism.repository"), menu=repo_menu)
        repo_menu.add_command(label=_t("plagiarism.check_integrity"), command=self.check_repository_integrity_gui)
        tools_menu.add_separator()
        tools_menu.add_command(label=_t("plagiarism.statistics"), command=self.show_statistics)
        tools_menu.add_command(label=_t("plagiarism.setup_testing"), command=self.show_setup_testing)

        # Language menu
        language_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=f"\U0001f310 {_t('gui.language')}", menu=language_menu)
        language_menu.add_command(label=_t("gui.change_language"), command=self.change_language)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("plagiarism.menu_help"), menu=help_menu)
        help_menu.add_command(label=_t("plagiarism.about"), command=self.show_about)

        self.create_main_menu_button()

    def change_language(self):
        """Open language selector and refresh UI if language changes"""
        old_lang = get_current_language()
        show_gui_language_selector(self.root)
        new_lang = get_current_language()
        if old_lang != new_lang:
            # Refresh the entire interface with new language
            self.refresh_interface()

    def create_main_menu_button(self):
        """Place a navigation button in the top-right corner"""
        try:
            if hasattr(self, "main_menu_button") and self.main_menu_button.winfo_exists():
                return
        except Exception as e:
            logger.debug(f"Error checking main_menu_button existence: {e}")

        self.main_menu_button = ttk.Button(
            self.root,
            text=f"\U0001f3e0 {_t('common.return_to_main_menu')}",
            command=self.return_to_main_menu,
        )
        self.main_menu_button.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

    def refresh_interface(self):
        """Refresh the entire interface after language change"""
        # Update window title
        self.root.title(_t("plagiarism.title"))

        # Clear and recreate menu
        self.root.config(menu=None)
        self.create_menu()

        # Clear and recreate main interface
        for widget in self.root.winfo_children():
            if widget != getattr(self, 'main_menu_button', None):
                widget.destroy()

        self.create_main_interface()
        self.create_status_bar()
        self.create_main_menu_button()

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
        self.notebook.add(dashboard_frame, text=_t("plagiarism.dashboard"))

        # Welcome section
        welcome_frame = ttk.LabelFrame(dashboard_frame, text=_t("plagiarism.welcome"), padding=GuiConfig.PADDING_MEDIUM)
        welcome_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        welcome_label = ttk.Label(
            welcome_frame,
            text=_t("plagiarism.title"),
            font=GuiConfig.HEADER_FONT
        )
        welcome_label.pack()

        subtitle_label = ttk.Label(
            welcome_frame,
            text=_t("plagiarism.subtitle"),
            font=GuiConfig.BODY_FONT
        )
        subtitle_label.pack()

        # Quick actions
        actions_frame = ttk.LabelFrame(dashboard_frame, text=_t("plagiarism.quick_actions"), padding=GuiConfig.PADDING_MEDIUM)
        actions_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        # Action buttons
        btn_frame = ttk.Frame(actions_frame)
        btn_frame.pack()

        submit_btn = ttk.Button(
            btn_frame,
            text=_t("plagiarism.submit_document"),
            style='Accent.TButton',
            command=self.show_submit_dialog
        )
        submit_btn.pack(side=tk.LEFT, padx=(0, GuiConfig.PADDING_MEDIUM))

        check_btn = ttk.Button(
            btn_frame,
            text=_t("plagiarism.check_for_plagiarism"),
            command=self.show_check_dialog
        )
        check_btn.pack(side=tk.LEFT, padx=(0, GuiConfig.PADDING_MEDIUM))

        search_btn = ttk.Button(
            btn_frame,
            text=_t("plagiarism.search_repository"),
            command=self.show_search_dialog
        )
        search_btn.pack(side=tk.LEFT)

        # Statistics summary
        self.stats_frame = ttk.LabelFrame(dashboard_frame, text=_t("plagiarism.system_statistics"), padding=GuiConfig.PADDING_MEDIUM)
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
        self.notebook.add(documents_frame, text=_t("plagiarism.documents_tab"))

        # Controls frame
        controls_frame = ttk.Frame(documents_frame)
        controls_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        # Search controls
        search_frame = ttk.LabelFrame(controls_frame, text=_t("plagiarism.search_documents"), padding=GuiConfig.PADDING_SMALL)
        search_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_SMALL))

        ttk.Label(search_frame, text=_t("plagiarism.title_label")).grid(row=0, column=0, sticky=tk.W, padx=(0, GuiConfig.PADDING_SMALL))
        self.doc_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.doc_search_var, width=30)
        search_entry.grid(row=0, column=1, padx=(0, GuiConfig.PADDING_SMALL))

        search_btn = ttk.Button(search_frame, text=_t("common.search"), command=self.search_documents)
        search_btn.grid(row=0, column=2, padx=(0, GuiConfig.PADDING_SMALL))

        refresh_btn = ttk.Button(search_frame, text=_t("common.refresh"), command=self.load_documents)
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
        self.notebook.add(results_frame, text=_t("plagiarism.check_results_tab"))

        # Controls
        controls_frame = ttk.Frame(results_frame)
        controls_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        refresh_results_btn = ttk.Button(
            controls_frame,
            text=_t("plagiarism.refresh_results"),
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
        self.notebook.add(settings_frame, text=_t("plagiarism.settings_tab"))

        # Plagiarism detection settings
        detection_frame = ttk.LabelFrame(settings_frame, text=_t("plagiarism.detection_settings"), padding=GuiConfig.PADDING_MEDIUM)
        detection_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        # Similarity threshold
        ttk.Label(detection_frame, text=_t("plagiarism.similarity_threshold")).grid(row=0, column=0, sticky=tk.W)
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
        info_frame = ttk.LabelFrame(settings_frame, text=_t("plagiarism.system_information"), padding=GuiConfig.PADDING_MEDIUM)
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

    def _on_close(self):
        """Cancel pending after callbacks and destroy the window."""
        if self._task_after_id is not None:
            try:
                self.root.after_cancel(self._task_after_id)
            except tk.TclError:
                pass
        self.root.destroy()

    def process_tasks(self):
        """Process background tasks"""
        try:
            if not self.root.winfo_exists():
                return
        except tk.TclError:
            return

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
        try:
            self._task_after_id = self.root.after(100, self.process_tasks)
        except tk.TclError:
            pass

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

        ttk.Label(main_frame, text=_t("plagiarism.repository_integrity_check"), font=GuiConfig.HEADER_FONT).pack(pady=(0, GuiConfig.PADDING_LARGE))

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

                        fix_button = ttk.Button(main_frame, text=_t("plagiarism.fix_issues"),
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

        ttk.Label(main_frame, text=_t("plagiarism.system_reports"), font=GuiConfig.HEADER_FONT).pack(pady=(0, GuiConfig.PADDING_LARGE))

        # Report types
        reports_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.available_reports"), padding=GuiConfig.PADDING_MEDIUM)
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
        options_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.report_options"), padding=GuiConfig.PADDING_MEDIUM)
        options_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        include_charts_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text=_t("plagiarism.include_charts_graphs"), variable=include_charts_var).pack(anchor=tk.W)

        export_format_var = tk.StringVar(value="html")
        format_frame = ttk.Frame(options_frame)
        format_frame.pack(fill=tk.X, pady=GuiConfig.PADDING_SMALL)

        ttk.Label(format_frame, text=_t("plagiarism.export_format")).pack(side=tk.LEFT)
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

        ttk.Button(main_frame, text=_t("plagiarism.generate_report"), command=generate_report).pack(pady=GuiConfig.PADDING_MEDIUM)

        ttk.Button(main_frame, text=_t("common.close"), command=reports_dialog.destroy).pack()

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
                ''', (f"%{escape_like(author_name)}%", f"%{escape_like(author_name)}%"))

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

                ttk.Label(main_frame, text=_t("plagiarism.select_author"), font=GuiConfig.SUBHEADER_FONT).pack(pady=(0, GuiConfig.PADDING_MEDIUM))

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
                ttk.Button(button_frame, text=_t("common.ok"), command=on_ok).pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))

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
                ''', (f"%{escape_like(module_name)}%", f"%{escape_like(module_name)}%"))

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

                ttk.Label(main_frame, text=_t("plagiarism.select_module"), font=GuiConfig.SUBHEADER_FONT).pack(pady=(0, GuiConfig.PADDING_MEDIUM))

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
                ttk.Button(button_frame, text=_t("common.ok"), command=on_ok).pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))

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
\u2022 Document repository management
\u2022 Advanced similarity detection
\u2022 Multiple file format support
\u2022 Detailed reporting
\u2022 User-friendly GUI interface

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
            notebook.add(checks_frame, text=_t("plagiarism.plagiarism_checks"))

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
            text=_t("plagiarism.check_plagiarism"),
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
                on_view_details=self.show_result_details,
                on_email_result=self.send_plagiarism_report_via_email,
                auth=self.auth
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
\u2022 Document Repository: SQLite Database
\u2022 Text Processing: NLTK (if available)
\u2022 File Support: textract (if available)
\u2022 Similarity Algorithm: N-gram Jaccard Similarity

Database Location: student_records.db
Log Directory: logs/

System Status: {"Ready" if self.checker else "Not Initialized"}
Authentication: Mock Auth (GUI Mode)

Features Enabled:
\u2022 Document Submission \u2713
\u2022 Plagiarism Detection \u2713
\u2022 Repository Search \u2713
\u2022 Statistical Reports \u2713
\u2022 GUI Interface \u2713

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

        ttk.Label(main_frame, text=_t("plagiarism.import_documents"), font=GuiConfig.HEADER_FONT).pack(pady=(0, GuiConfig.PADDING_LARGE))

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

        ttk.Label(main_frame, text=_t("plagiarism.export_documents"), font=GuiConfig.HEADER_FONT).pack(pady=(0, GuiConfig.PADDING_LARGE))

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
        format_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.export_format"), padding=GuiConfig.PADDING_SMALL)
        format_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        format_var = tk.StringVar(value="txt")
        ttk.Radiobutton(format_frame, text=_t("plagiarism.text_files"), variable=format_var, value="txt").pack(anchor=tk.W)
        ttk.Radiobutton(format_frame, text=_t("plagiarism.zip_archive"), variable=format_var, value="zip").pack(anchor=tk.W)

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

        ttk.Button(button_frame, text=_t("common.select_all"), command=lambda: tree.selection_set(tree.get_children())).pack(side=tk.LEFT)
        ttk.Button(button_frame, text=_t("common.deselect_all"), command=lambda: tree.selection_remove(tree.get_children())).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        ttk.Button(button_frame, text=_t("plagiarism.export_selected"), command=export_selected).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text=_t("common.cancel"), command=export_dialog.destroy).pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))

        # Load documents after dialog is ready
        export_dialog.after(100, load_docs)

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

        ttk.Label(main_frame, text=_t("plagiarism.delete_document"), font=GuiConfig.HEADER_FONT).pack(pady=(0, GuiConfig.PADDING_LARGE))

        # Warning label
        warning_frame = ttk.Frame(main_frame)
        warning_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))
        ttk.Label(warning_frame, text=_t("plagiarism.delete_warning"),
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
        info_label = ttk.Label(main_frame, text=_t("plagiarism.select_document_delete"))
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

        ttk.Button(button_frame, text=_t("plagiarism.delete_selected"), command=delete_selected).pack(side=tk.LEFT)
        ttk.Button(button_frame, text=_t("common.close"), command=delete_dialog.destroy).pack(side=tk.RIGHT)

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
        dialog = CheckResultDialog(self.root, self.checker, result,
                                   auth=self.auth,
                                   on_email_result=self.send_plagiarism_report_via_email)
        dialog.show()

    def show_result_details(self, result_data):
        """Show detailed result information"""
        dialog = ResultDetailsDialog(self.root, self.checker, result_data['result_id'],
                                     auth=self.auth,
                                     on_email_result=self.send_plagiarism_report_via_email)
        dialog.show()

    def send_plagiarism_report_via_email(self, result_data, user_email=None):
        """Send plagiarism report via email GUI"""
        try:
            # Extract result information
            result_id = result_data.get('result_id', 'Unknown')
            similarity_score = result_data.get('similarity_score', 0)
            document_name = result_data.get('document_name', 'Unknown Document')

            # Generate email content
            from education_system.university_system.infrastructure.email.template_utils import render_template

            status = '\u26a0\ufe0f ATTENTION REQUIRED' if similarity_score > 30 else '\u2705 WITHIN ACCEPTABLE LIMITS'
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
        """Send email using the core email service"""
        try:
            from education_system.university_system.infrastructure.email.email_service.core import send_email
            return send_email(
                recipient_email=to_email,
                subject=subject,
                body=message
            )
        except Exception as e:
            print(f"Error sending email: {e}")
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
                from education_system.university_system.modules.shared.gui.main import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def run(self):
        """Run the GUI application"""
        self.root.mainloop()
