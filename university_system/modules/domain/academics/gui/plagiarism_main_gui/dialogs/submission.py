import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import threading
import logging
from datetime import datetime
import os

from university_system.modules.shared.utils.i18n import get_text as _t

from ..config import GuiConfig
from ..common import logger

from university_system.infrastructure.database.db import DEFAULT_DB_PATH, sqlite3


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
        title_label = ttk.Label(main_frame, text=_t("plagiarism.submit_document"), font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))

        # Form fields
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Document title
        ttk.Label(form_frame, text=_t("plagiarism.document_title")).grid(row=0, column=0, sticky=tk.W, pady=GuiConfig.PADDING_SMALL)
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
        preview_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.file_preview"), padding=GuiConfig.PADDING_SMALL)
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
        """Placeholder for CLI 'view_my_documents' --- filters Documents to current user (future)."""
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
