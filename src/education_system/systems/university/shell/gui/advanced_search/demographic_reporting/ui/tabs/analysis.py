"""Extracted demographic-reporting behaviour."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
from ... import *

class AdvancedUiTabsAnalysisMixin:
    def _create_analysis_tab(self, parent, analysis_type):
        """Create analysis tab with treeview for breakdown"""
        ttk.Label(
            parent,
            text=f"{analysis_type.title()} Distribution Analysis",
            style='SectionTitle.TLabel'
        ).pack(anchor='w', pady=(0, 10))

        # Treeview for data
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('category', 'count', 'percentage', 'bar')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        tree.heading('category', text=analysis_type.title())
        tree.heading('count', text=_t('gui.shell.advanced_search.demographic_reporting.ui.tabs.analysis.headings.count', default='Count'))
        tree.heading('percentage', text=_t('gui.shell.advanced_search.demographic_reporting.ui.tabs.analysis.headings.percentage', default='Percentage'))
        tree.heading('bar', text=_t('gui.shell.advanced_search.demographic_reporting.ui.tabs.analysis.headings.visual', default='Visual'))

        tree.column('category', width=200)
        tree.column('count', width=100, anchor='center')
        tree.column('percentage', width=100, anchor='center')
        tree.column('bar', width=300)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=y_scroll.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Store reference
        setattr(self, f'{analysis_type}_tree', tree)

    def _update_analysis_tree(self, tree, data_dict, total):
        """Update a treeview with analysis data"""
        # Clear existing
        for item in tree.get_children():
            tree.delete(item)

        # Insert sorted data
        for category, count in sorted(data_dict.items(), key=lambda x: -x[1]):
            pct = (count / total * 100) if total > 0 else 0
            bar = self._create_visual_bar(pct, 25)
            tree.insert('', tk.END, values=(category, f"{count:,}", f"{pct:.1f}%", bar))

    def _update_gender_analysis(self):
        """Update gender analysis tab"""
        if hasattr(self, 'gender_tree'):
            self._update_analysis_tree(
                self.gender_tree,
                self.report_data['gender'],
                self.report_data['total']
            )

    def _update_age_analysis(self):
        """Update age analysis tab"""
        if hasattr(self, 'age_tree'):
            self._update_analysis_tree(
                self.age_tree,
                self.report_data['age'],
                self.report_data['total']
            )

    def _update_course_analysis(self):
        """Update course analysis tab"""
        if hasattr(self, 'course_tree'):
            self._update_analysis_tree(
                self.course_tree,
                self.report_data['course'],
                self.report_data['total']
            )
