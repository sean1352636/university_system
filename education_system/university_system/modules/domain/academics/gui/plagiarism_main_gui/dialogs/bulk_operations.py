import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import threading
import logging
from datetime import datetime
import os

from education_system.university_system.modules.shared.utils.i18n import get_text as _t

from ..config import GuiConfig
from ..common import logger


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
        title_label = ttk.Label(main_frame, text=_t("plagiarism.bulk_operations"), font=GuiConfig.HEADER_FONT)
        title_label.pack(pady=(0, GuiConfig.PADDING_LARGE))

        # Document selection
        selection_frame = ttk.LabelFrame(main_frame, text=_t("plagiarism.select_documents"), padding=GuiConfig.PADDING_SMALL)
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

        ttk.Button(select_frame, text=_t("common.select_all"), command=self.select_all).pack(side=tk.LEFT)
        ttk.Button(select_frame, text=_t("common.select_none"), command=self.select_none).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        ttk.Button(select_frame, text=_t("plagiarism.toggle_selection"), command=self.toggle_selection).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))

        # Operations
        operations_frame = ttk.LabelFrame(main_frame, text="Operations", padding=GuiConfig.PADDING_SMALL)
        operations_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        ttk.Button(operations_frame, text=_t("plagiarism.bulk_plagiarism_check"), command=self.bulk_plagiarism_check).pack(side=tk.LEFT)
        ttk.Button(operations_frame, text=_t("plagiarism.bulk_delete"), command=self.bulk_delete).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))
        ttk.Button(operations_frame, text=_t("plagiarism.export_selected"), command=self.export_selected).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))

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
                        "\u2610",  # Unchecked checkbox symbol
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
            current_values[0] = "\u2610"
            tags = [tag for tag in tags if tag != 'selected']
            tags.append('unselected')
        else:
            current_values[0] = "\u2611"
            tags = [tag for tag in tags if tag != 'unselected']
            tags.append('selected')

        self.docs_tree.item(item, values=current_values, tags=tags)

    def select_all(self):
        """Select all documents"""
        for item in self.docs_tree.get_children():
            current_values = list(self.docs_tree.item(item, 'values'))
            current_values[0] = "\u2611"
            tags = [tag for tag in self.docs_tree.item(item, 'tags') if not tag.startswith('selected') and not tag.startswith('unselected')]
            tags.append('selected')
            self.docs_tree.item(item, values=current_values, tags=tags)

    def select_none(self):
        """Deselect all documents"""
        for item in self.docs_tree.get_children():
            current_values = list(self.docs_tree.item(item, 'values'))
            current_values[0] = "\u2610"
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

        ttk.Label(main_frame, text=_t("plagiarism.bulk_plagiarism_check_results"), font=GuiConfig.HEADER_FONT).pack(pady=(0, GuiConfig.PADDING_MEDIUM))

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
