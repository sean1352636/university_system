"""Textbook management"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.systems.university.domains.finance.interfaces.gui.finance.budget_manager.constants import logger


class TextbooksMixin:
    """Textbook comparison and tracking methods"""

    def create_textbooks_tab(self, notebook):
        """Create textbook comparison and tracking tab"""
        tab = ttk.Frame(notebook, padding="10")
        notebook.add(tab, text=_t('gui.finance.finance.budget_manager.textbooks.tabs.textbooks', default="Textbooks"))

        # Search frame
        search_frame = ttk.LabelFrame(tab, text=_t('gui.finance.finance.budget_manager.textbooks.labels.compare_textbook_prices', default="Compare Textbook Prices"), padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10))

        fields = ttk.Frame(search_frame)
        fields.pack(fill=tk.X)

        ttk.Label(fields, text=_t('gui.finance.finance.budget_manager.textbooks.labels.isbn', default="ISBN:")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.textbook_isbn_entry = ttk.Entry(fields, width=20)
        self.textbook_isbn_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(fields, text=_t('gui.finance.finance.budget_manager.textbooks.labels.course_code', default="Course Code:")).grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.textbook_course_entry = ttk.Entry(fields, width=15)
        self.textbook_course_entry.grid(row=0, column=3, padx=5, pady=5)

        ttk.Button(fields, text=_t('gui.finance.finance.budget_manager.textbooks.buttons.search_prices', default="Search Prices"),
                  command=self.search_textbooks).grid(row=0, column=4, padx=5, pady=5)

        # Search results
        results_frame = ttk.LabelFrame(tab, text=_t('gui.finance.finance.budget_manager.textbooks.labels.available_listings', default="Available Listings"), padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.textbook_results_tree = ttk.Treeview(results_frame,
            columns=('Title', 'Vendor', 'Condition', 'Price', 'Shipping', 'Total'),
            show='headings', height=8)

        for col in self.textbook_results_tree['columns']:
            self.textbook_results_tree.heading(col, text=col)
            width = 250 if col == 'Title' else 100 if col == 'Vendor' else 80
            self.textbook_results_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL,
                                 command=self.textbook_results_tree.yview)
        self.textbook_results_tree.configure(yscrollcommand=scrollbar.set)

        self.textbook_results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # My textbooks
        my_books_frame = ttk.LabelFrame(tab, text=_t('gui.finance.finance.budget_manager.textbooks.labels.my_textbook_purchases', default="My Textbook Purchases"), padding="10")
        my_books_frame.pack(fill=tk.BOTH, expand=True)

        self.my_textbooks_tree = ttk.Treeview(my_books_frame,
            columns=('Title', 'Course', 'Purchase Date', 'Vendor', 'Type', 'Price'),
            show='headings', height=8)

        for col in self.my_textbooks_tree['columns']:
            self.my_textbooks_tree.heading(col, text=col)
            width = 250 if col == 'Title' else 100 if col in ('Course', 'Purchase Date', 'Type') else 120
            self.my_textbooks_tree.column(col, width=width)

        scrollbar2 = ttk.Scrollbar(my_books_frame, orient=tk.VERTICAL,
                                  command=self.my_textbooks_tree.yview)
        self.my_textbooks_tree.configure(yscrollcommand=scrollbar2.set)

        self.my_textbooks_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar2.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Button(tab, text=_t('gui.finance.finance.budget_manager.textbooks.buttons.refresh_my_textbooks', default="Refresh My Textbooks"),
                  command=self.load_my_textbooks).pack(pady=5)

    def search_textbooks(self):
        """Search for textbook prices"""
        self.textbook_results_tree.delete(*self.textbook_results_tree.get_children())
        try:
            isbn = self.textbook_isbn_entry.get().strip() or None
            course_code = self.textbook_course_entry.get().strip() or None

            if not isbn and not course_code:
                messagebox.showwarning(_t('gui.finance.finance.budget_manager.textbooks.dialogs.warning', default="Warning"), _t('gui.finance.finance.budget_manager.textbooks.dialogs.please_enter_isbn_or_course_code', default="Please enter ISBN or Course Code."))
                return

            from education_system.systems.university.domains.finance.domain.budget.services.budget_service import TextbookComparisonManager
            listings = TextbookComparisonManager.compare_textbook_prices(
                isbn=isbn, course_code=course_code)

            for listing in listings:
                total = listing['price'] + listing['shipping_cost']
                self.textbook_results_tree.insert('', 'end', values=(
                    listing['title'][:40],
                    listing['vendor'],
                    listing['condition'],
                    f"\u00a3{listing['price']:.2f}",
                    f"\u00a3{listing['shipping_cost']:.2f}",
                    f"\u00a3{total:.2f}"
                ))

            if not listings:
                messagebox.showinfo(_t('gui.finance.finance.budget_manager.textbooks.dialogs.info', default="Info"), _t('gui.finance.finance.budget_manager.textbooks.dialogs.no_listings_found', default="No listings found."))

        except Exception as e:
            messagebox.showerror(_t('gui.finance.finance.budget_manager.textbooks.dialogs.error', default="Error"), f"Failed to search textbooks: {e}")

    def load_my_textbooks(self):
        """Load student's textbook purchases"""
        self.my_textbooks_tree.delete(*self.my_textbooks_tree.get_children())
        try:
            current_user = self.gui.auth.get_current_user() if self.gui.auth else None
            student_id = current_user.get('username') if current_user else 'guest'

            from education_system.systems.university.domains.finance.domain.budget.services.budget_service import TextbookComparisonManager
            textbooks = TextbookComparisonManager.get_student_textbooks(student_id)

            for book in textbooks:
                self.my_textbooks_tree.insert('', 'end', values=(
                    book['title'],
                    book['course_code'] or 'N/A',
                    book['purchase_date'],
                    book['vendor'],
                    book['purchase_type'],
                    f"\u00a3{book['price_paid']:.2f}"
                ))
        except Exception as e:
            logger.error(f"Error loading textbooks: {e}")
