import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import threading
import logging
from datetime import datetime
import os

from education_system.university_system.modules.shared.utils.i18n import get_text as _t

from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.config import GuiConfig
from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.common import logger


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
        title_label = ttk.Label(main_frame, text=_t("plagiarism.repository_search"), font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))

        # Search controls
        search_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.search_criteria"), padding=GuiConfig.PADDING_SMALL)
        search_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        # Search term
        ttk.Label(search_frame, text=_t("plagiarism.title_content")).grid(row=0, column=0, sticky=tk.W, padx=(0, GuiConfig.PADDING_SMALL))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        search_entry.grid(row=0, column=1, padx=(0, GuiConfig.PADDING_SMALL))

        search_btn = ttk.Button(search_frame, text="Search", command=self.perform_search)
        search_btn.grid(row=0, column=2, padx=(0, GuiConfig.PADDING_SMALL))

        clear_btn = ttk.Button(search_frame, text="Clear", command=self.clear_search)
        clear_btn.grid(row=0, column=3)

        # Results
        results_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.search_results"), padding=GuiConfig.PADDING_SMALL)
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

        view_btn = ttk.Button(button_frame, text=_t("common.view_details"), command=self.view_selected_document)
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
        from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui.dialogs.document_details import DocumentDetailsDialog
        details_dialog = DocumentDetailsDialog(self.dialog, self.checker, doc_id)
        details_dialog.show()
