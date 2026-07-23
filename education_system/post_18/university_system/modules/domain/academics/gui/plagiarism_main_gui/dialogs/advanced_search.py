import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import threading
import logging
from datetime import datetime
import os

from education_system.post_18.university_system.core.i18n import get_text as _t

from education_system.post_18.university_system.modules.domain.academics.gui.plagiarism_main_gui.config import GuiConfig
from education_system.post_18.university_system.modules.domain.academics.gui.plagiarism_main_gui.common import logger


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
        title_label = ttk.Label(main_frame, text=_t("plagiarism.advanced_repository_search"), font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))

        # Search criteria notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))

        # Basic search tab
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text=_t("plagiarism.basic_search"))
        self.create_basic_search_tab(basic_frame)

        # Advanced filters tab
        advanced_frame = ttk.Frame(notebook)
        notebook.add(advanced_frame, text=_t("plagiarism.advanced_filters"))
        self.create_advanced_filters_tab(advanced_frame)

        # Results frame
        self.results_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.search_results"), padding=GuiConfig.PADDING_SMALL)
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
        ttk.Button(button_frame, text=_t("plagiarism.export_results"), command=self.export_results).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="View Details", command=self.view_selected_details).pack(side=tk.RIGHT, padx=(0, GuiConfig.PADDING_SMALL))

    def create_basic_search_tab(self, parent):
        """Create basic search tab"""
        # Search term
        ttk.Label(parent, text=_t("plagiarism.search_term"), font=GuiConfig.SUBHEADER_FONT).grid(row=0, column=0, sticky=tk.W, pady=GuiConfig.PADDING_SMALL)
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
        date_frame = ttk.LabelFrame(parent, text=_t("plagiarism.date_range"), padding=GuiConfig.PADDING_SMALL)
        date_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        ttk.Label(date_frame, text="From:").grid(row=0, column=0, sticky=tk.W)
        self.date_from_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.date_from_var, width=15).grid(row=0, column=1, padx=GuiConfig.PADDING_SMALL)

        ttk.Label(date_frame, text="To:").grid(row=0, column=2, sticky=tk.W, padx=(GuiConfig.PADDING_MEDIUM, 0))
        self.date_to_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.date_to_var, width=15).grid(row=0, column=3, padx=GuiConfig.PADDING_SMALL)

        ttk.Label(date_frame, text="(YYYY-MM-DD format)", font=("Arial", 8)).grid(row=1, column=0, columnspan=4, sticky=tk.W)

        # File type filter
        type_frame = ttk.LabelFrame(parent, text=_t("plagiarism.file_type"), padding=GuiConfig.PADDING_SMALL)
        type_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        self.file_type_var = tk.StringVar()
        file_types = ['All', 'txt', 'pdf', 'docx', 'doc']
        type_combo = ttk.Combobox(type_frame, textvariable=self.file_type_var, values=file_types, state='readonly')
        type_combo.set('All')
        type_combo.pack(anchor=tk.W)

        # Word count range
        words_frame = ttk.LabelFrame(parent, text=_t("plagiarism.word_count_range"), padding=GuiConfig.PADDING_SMALL)
        words_frame.pack(fill=tk.X)

        ttk.Label(words_frame, text=_t("plagiarism.min_words")).grid(row=0, column=0, sticky=tk.W)
        self.min_words_var = tk.StringVar()
        ttk.Entry(words_frame, textvariable=self.min_words_var, width=10).grid(row=0, column=1, padx=GuiConfig.PADDING_SMALL)

        ttk.Label(words_frame, text=_t("plagiarism.max_words")).grid(row=0, column=2, sticky=tk.W, padx=(GuiConfig.PADDING_MEDIUM, 0))
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
        except ValueError as e:
            logger.debug(f"Invalid min_words value: {e}")

        try:
            max_words = self.max_words_var.get().strip()
            if max_words:
                max_words = int(max_words)
                filtered = [doc for doc in filtered if doc.get('word_count', 0) <= max_words]
        except ValueError as e:
            logger.debug(f"Invalid max_words value: {e}")

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
        from education_system.post_18.university_system.modules.domain.academics.gui.plagiarism_main_gui.dialogs.document_details import DocumentDetailsDialog
        details_dialog = DocumentDetailsDialog(self.dialog, self.checker, doc_id)
        details_dialog.show()
