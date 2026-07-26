"""Institutional budget tab (admin/staff only)"""

import tkinter as tk
from tkinter import ttk


class InstitutionalBudgetMixin:
    """Institutional budget management methods"""

    def create_institutional_budget_tab(self, notebook):
        """Create institutional budget management tab (admin/staff only)"""
        tab = ttk.Frame(notebook, padding="10")
        notebook.add(tab, text="Institutional Budgets")

        # Budget plans section
        plans_frame = ttk.LabelFrame(tab, text="Budget Plans", padding="10")
        plans_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.budget_plans_tree = ttk.Treeview(plans_frame,
            columns=('budget_id', 'name', 'year', 'revenue', 'expenses', 'status'),
            show='headings', height=10)

        for col in self.budget_plans_tree['columns']:
            self.budget_plans_tree.heading(col, text=col.replace('_', ' ').title())
            width = 80 if col == 'budget_id' else 120 if col in ('revenue', 'expenses', 'status') else 200
            self.budget_plans_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(plans_frame, orient=tk.VERTICAL, command=self.budget_plans_tree.yview)
        self.budget_plans_tree.configure(yscrollcommand=scrollbar.set)

        self.budget_plans_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Budget categories section
        categories_frame = ttk.LabelFrame(tab, text="Budget Categories", padding="10")
        categories_frame.pack(fill=tk.BOTH, expand=True)

        self.budget_categories_tree = ttk.Treeview(categories_frame,
            columns=('category_id', 'name', 'type', 'parent'),
            show='headings', height=10)

        for col in self.budget_categories_tree['columns']:
            self.budget_categories_tree.heading(col, text=col.replace('_', ' ').title())
            width = 80 if col == 'category_id' else 150
            self.budget_categories_tree.column(col, width=width)

        cat_scrollbar = ttk.Scrollbar(categories_frame, orient=tk.VERTICAL,
                                      command=self.budget_categories_tree.yview)
        self.budget_categories_tree.configure(yscrollcommand=cat_scrollbar.set)

        self.budget_categories_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cat_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
