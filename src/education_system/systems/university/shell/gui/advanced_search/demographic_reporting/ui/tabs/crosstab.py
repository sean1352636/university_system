"""Cross-tabulation tab.

Was a Courier ``tk.Text`` with the matrix laid out by hand — column
widths computed from the longest label, rows built by ``f"{v:>{w}}"``
padding, and separator lines of dashes sized to match. That alignment
breaks the moment a course name is longer than expected, and the whole
thing needs a horizontal scrollbar.

It is now two real tables: counts and row percentages. Column widths are
the widget's problem, not ours.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.shell.gui import report_view as rv
from ... import *


#: Which column of a raw student row each variable lives in.
VAR_INDEX = {'gender': 2, 'age_group': 8, 'course': 4, 'status': 5}

CROSSTAB_VARS = ('gender', 'age_group', 'course', 'status')


class AdvancedUiTabsCrosstabMixin:
    def _create_crosstab_tab(self):
        """Create cross-tabulation tab"""
        controls = ttk.Frame(self.crosstab_frame)
        controls.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(controls, text=_t(
            'gui.shell.advanced_search.demographic_reporting.ui.tabs.'
            'crosstab.labels.row_variable', default="Row Variable:")
        ).pack(side=tk.LEFT, padx=(0, 5))
        self.crosstab_row_var = tk.StringVar(value='gender')
        ttk.Combobox(controls, textvariable=self.crosstab_row_var,
                     values=list(CROSSTAB_VARS), state='readonly', width=15
                     ).pack(side=tk.LEFT, padx=(0, 20))

        ttk.Label(controls, text=_t(
            'gui.shell.advanced_search.demographic_reporting.ui.tabs.'
            'crosstab.labels.column_variable', default="Column Variable:")
        ).pack(side=tk.LEFT, padx=(0, 5))
        self.crosstab_col_var = tk.StringVar(value='status')
        ttk.Combobox(controls, textvariable=self.crosstab_col_var,
                     values=list(CROSSTAB_VARS), state='readonly', width=15
                     ).pack(side=tk.LEFT, padx=(0, 20))

        ttk.Button(controls, text=_t(
            'gui.shell.advanced_search.demographic_reporting.ui.tabs.'
            'crosstab.buttons.generate_cross_tab', default="Generate Cross-Tab"),
            command=self._generate_crosstab).pack(side=tk.LEFT)

        self.crosstab_view = rv.ReportView(self.crosstab_frame)
        self.crosstab_view.pack(fill=tk.BOTH, expand=True)
        self.crosstab_view.empty(_t(
            'gui.shell.advanced_search.demographic_reporting.ui.tabs.'
            'crosstab.labels.choose_variables',
            default="Choose two variables and select Generate Cross-Tab."))

    def _generate_crosstab(self):
        """Generate cross-tabulation report"""
        if not self.raw_data:
            messagebox.showwarning(
                _t('gui.shell.advanced_search.demographic_reporting.ui.tabs.'
                   'crosstab.dialogs.no_data', default="No Data"),
                _t('gui.shell.advanced_search.demographic_reporting.ui.tabs.'
                   'crosstab.dialogs.please_generate_report_first',
                   default="Please generate report first."))
            return

        row_var = self.crosstab_row_var.get()
        col_var = self.crosstab_col_var.get()
        if row_var == col_var:
            messagebox.showwarning(
                _t('gui.shell.advanced_search.demographic_reporting.ui.tabs.'
                   'crosstab.dialogs.invalid_selection',
                   default="Invalid Selection"),
                _t('gui.shell.advanced_search.demographic_reporting.ui.tabs.'
                   'crosstab.dialogs.please_select_different_variables_for_'
                   'rows_and_columns',
                   default="Please select different variables for rows and columns."))
            return
        if row_var not in VAR_INDEX or col_var not in VAR_INDEX:
            messagebox.showwarning(
                _t('gui.shell.advanced_search.demographic_reporting.ui.tabs.'
                   'crosstab.dialogs.invalid_selection',
                   default="Invalid Selection"),
                f"Unknown variable: {row_var} / {col_var}")
            return

        row_idx, col_idx = VAR_INDEX[row_var], VAR_INDEX[col_var]
        crosstab, col_totals, row_totals = {}, {}, {}
        for row in self.raw_data:
            try:
                row_val = row[row_idx] or 'Unknown'
                col_val = row[col_idx] or 'Unknown'
            except (IndexError, TypeError):
                # A short row is a data fault, not a reason to abandon
                # the whole cross-tab.
                continue
            crosstab.setdefault(row_val, {})
            crosstab[row_val][col_val] = crosstab[row_val].get(col_val, 0) + 1
            col_totals[col_val] = col_totals.get(col_val, 0) + 1
            row_totals[row_val] = row_totals.get(row_val, 0) + 1

        view = self.crosstab_view
        view.clear()
        view.title(f"{row_var.replace('_', ' ').title()} "
                   f"× {col_var.replace('_', ' ').title()}",
                   _t('advanced_search.demographics.crosstab_subtitle',
                      "Cross-tabulation"))

        if not crosstab:
            view.empty(_t('advanced_search.demographics.no_crosstab_data',
                          "No rows carried both variables."))
            view.freeze()
            return

        cols = sorted(col_totals)
        rows = sorted(row_totals)
        grand = sum(row_totals.values())

        view.scorecard([
            (_t('advanced_search.demographics.students', "Students"),
             f"{grand:,}", 'info'),
            (row_var.replace('_', ' ').title(), f"{len(rows):,}", 'info'),
            (col_var.replace('_', ' ').title(), f"{len(cols):,}", 'info'),
        ])

        view.section(_t('advanced_search.demographics.counts', "Counts"))
        headers = [row_var.replace('_', ' ').title()] + [str(c) for c in cols] \
            + [_t('advanced_search.demographics.total', "Total")]
        body = []
        for row_val in rows:
            body.append([str(row_val)]
                        + [crosstab.get(row_val, {}).get(c, 0) for c in cols]
                        + [row_totals[row_val]])
        body.append([_t('advanced_search.demographics.total', "Total")]
                    + [col_totals[c] for c in cols] + [grand])
        view.table(headers, body, height=min(len(body), 16))

        view.section(_t('advanced_search.demographics.row_percentages',
                        "Row percentages"))
        pct_body = []
        for row_val in rows:
            row_total = row_totals[row_val] or 1
            pct_body.append(
                [str(row_val)]
                + [f"{crosstab.get(row_val, {}).get(c, 0) / row_total * 100:.1f}%"
                   for c in cols]
                + ["100.0%"])
        view.table(headers, pct_body, height=min(len(pct_body), 16))
        view.freeze()
