import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import threading
import logging
from datetime import datetime
import os

from university_system.modules.shared.utils.i18n import get_text as _t

from ..config import GuiConfig
from ..common import logger

from ..common import NLTK_AVAILABLE
try:
    from nltk.tokenize import word_tokenize
except ImportError:
    pass


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
        title_label = ttk.Label(main_frame, text=_t("plagiarism.document_comparison"), font=GuiConfig.HEADER_FONT)
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

        ttk.Button(doc1_frame, text=_t("plagiarism.select_document_1"), command=lambda: self.select_document(1)).pack()

        # Document 2 selection
        doc2_frame = ttk.LabelFrame(selection_frame, text="Document 2", padding=GuiConfig.PADDING_SMALL)
        doc2_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(GuiConfig.PADDING_SMALL, 0))

        self.doc2_var = tk.StringVar()
        doc2_entry = ttk.Entry(doc2_frame, textvariable=self.doc2_var, state='readonly')
        doc2_entry.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_SMALL))

        ttk.Button(doc2_frame, text=_t("plagiarism.select_document_2"), command=lambda: self.select_document(2)).pack()

        # Comparison controls
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(0, GuiConfig.PADDING_MEDIUM))

        ttk.Button(controls_frame, text=_t("plagiarism.compare_documents"), command=self.compare_documents).pack(side=tk.LEFT)
        ttk.Button(controls_frame, text=_t("plagiarism.highlight_similarities"), command=self.highlight_similarities).pack(side=tk.LEFT, padx=(GuiConfig.PADDING_SMALL, 0))

        # Similarity score display
        self.similarity_var = tk.StringVar()
        self.similarity_var.set("Similarity: Not calculated")
        ttk.Label(controls_frame, textvariable=self.similarity_var, font=GuiConfig.SUBHEADER_FONT).pack(side=tk.RIGHT)

        # Comparison display
        comparison_frame = ttk.Frame(main_frame)
        comparison_frame.pack(fill=tk.BOTH, expand=True, pady=(0, GuiConfig.PADDING_MEDIUM))

        # Document 1 text
        doc1_text_frame = ttk.LabelFrame(comparison_frame, text=_t("plagiarism.document_1_content"), padding=GuiConfig.PADDING_SMALL)
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
        doc2_text_frame = ttk.LabelFrame(comparison_frame, text=_t("plagiarism.document_2_content"), padding=GuiConfig.PADDING_SMALL)
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

        ttk.Button(button_frame, text=_t("plagiarism.export_comparison"), command=self.export_comparison).pack(side=tk.LEFT)
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
                except (LookupError, Exception):
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
                    except Exception as e:
                        logger.debug(f"Failed to add highlight tag to doc1: {e}")

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
                    except Exception as e:
                        logger.debug(f"Failed to add highlight tag to doc2: {e}")

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
