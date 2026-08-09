"""Extracted demographic-reporting behaviour."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
from ... import *

class AdvancedUiTabsCrosstabMixin:
    def _create_crosstab_tab(self):
        """Create cross-tabulation tab"""
        # Controls frame
        controls = ttk.Frame(self.crosstab_frame)
        controls.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(controls, text=_t('gui.shell.advanced_search.demographic_reporting.ui.tabs.crosstab.labels.row_variable', default="Row Variable:")).pack(side=tk.LEFT, padx=(0, 5))
        self.crosstab_row_var = tk.StringVar(value=_t('gui.shell.advanced_search.demographic_reporting.ui.tabs.crosstab.values.gender', default="gender"))
        row_combo = ttk.Combobox(
            controls,
            textvariable=self.crosstab_row_var,
            values=['gender', 'age_group', 'course', 'status'],
            state='readonly',
            width=15
        )
        row_combo.pack(side=tk.LEFT, padx=(0, 20))

        ttk.Label(controls, text=_t('gui.shell.advanced_search.demographic_reporting.ui.tabs.crosstab.labels.column_variable', default="Column Variable:")).pack(side=tk.LEFT, padx=(0, 5))
        self.crosstab_col_var = tk.StringVar(value=_t('gui.shell.advanced_search.demographic_reporting.ui.tabs.crosstab.values.status', default="status"))
        col_combo = ttk.Combobox(
            controls,
            textvariable=self.crosstab_col_var,
            values=['gender', 'age_group', 'course', 'status'],
            state='readonly',
            width=15
        )
        col_combo.pack(side=tk.LEFT, padx=(0, 20))

        ttk.Button(
            controls,
            text=_t('gui.shell.advanced_search.demographic_reporting.ui.tabs.crosstab.buttons.generate_cross_tab', default="Generate Cross-Tab"),
            command=self._generate_crosstab
        ).pack(side=tk.LEFT)

        # Cross-tab display area
        self.crosstab_text = tk.Text(
            self.crosstab_frame,
            wrap=tk.NONE,
            font=('Courier', 10)
        )

        y_scroll = ttk.Scrollbar(self.crosstab_frame, orient=tk.VERTICAL, command=self.crosstab_text.yview)
        x_scroll = ttk.Scrollbar(self.crosstab_frame, orient=tk.HORIZONTAL, command=self.crosstab_text.xview)
        self.crosstab_text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.crosstab_text.pack(fill=tk.BOTH, expand=True)

    def _generate_crosstab(self):
        """Generate cross-tabulation report"""
        if not self.raw_data:
            messagebox.showwarning(_t('gui.shell.advanced_search.demographic_reporting.ui.tabs.crosstab.dialogs.no_data', default="No Data"), _t('gui.shell.advanced_search.demographic_reporting.ui.tabs.crosstab.dialogs.please_generate_report_first', default="Please generate report first."))
            return

        row_var = self.crosstab_row_var.get()
        col_var = self.crosstab_col_var.get()

        if row_var == col_var:
            messagebox.showwarning(_t('gui.shell.advanced_search.demographic_reporting.ui.tabs.crosstab.dialogs.invalid_selection', default="Invalid Selection"), _t('gui.shell.advanced_search.demographic_reporting.ui.tabs.crosstab.dialogs.please_select_different_variables_for_rows_and_columns', default="Please select different variables for rows and columns."))
            return

        # Map variable names to data indices
        var_index = {
            'gender': 2,
            'age_group': 8,
            'course': 4,
            'status': 5
        }

        row_idx = var_index[row_var]
        col_idx = var_index[col_var]

        # Build cross-tab
        crosstab = {}
        col_totals = {}
        row_totals = {}

        for row in self.raw_data:
            row_val = row[row_idx] or 'Unknown'
            col_val = row[col_idx] or 'Unknown'

            if row_val not in crosstab:
                crosstab[row_val] = {}
            crosstab[row_val][col_val] = crosstab[row_val].get(col_val, 0) + 1

            col_totals[col_val] = col_totals.get(col_val, 0) + 1
            row_totals[row_val] = row_totals.get(row_val, 0) + 1

        # Format output
        self.crosstab_text.delete(1.0, tk.END)

        cols = sorted(col_totals.keys())
        rows = sorted(row_totals.keys())

        # Header
        header = f"\n{'CROSS-TABULATION: ' + row_var.upper() + ' x ' + col_var.upper():^80}\n"
        header += "=" * 80 + "\n\n"

        # Calculate column widths
        row_width = max(len(str(r)) for r in rows + [row_var.title()]) + 2
        col_width = max(max(len(str(c)) for c in cols), 8) + 2

        # Column headers
        header += f"{row_var.title():<{row_width}}"
        for col in cols:
            col_display = str(col)[:col_width-2]
            header += f"{col_display:>{col_width}}"
        header += f"{'Total':>{col_width}}\n"
        header += "-" * (row_width + (len(cols) + 1) * col_width) + "\n"

        self.crosstab_text.insert(tk.END, header)

        # Data rows
        for row_val in rows:
            line = f"{str(row_val):<{row_width}}"
            for col in cols:
                count = crosstab.get(row_val, {}).get(col, 0)
                line += f"{count:>{col_width}}"
            line += f"{row_totals[row_val]:>{col_width}}\n"
            self.crosstab_text.insert(tk.END, line)

        # Totals row
        totals_line = "-" * (row_width + (len(cols) + 1) * col_width) + "\n"
        totals_line += f"{'Total':<{row_width}}"
        for col in cols:
            totals_line += f"{col_totals[col]:>{col_width}}"
        totals_line += f"{len(self.raw_data):>{col_width}}\n"

        self.crosstab_text.insert(tk.END, totals_line)

        # Percentage breakdown
        pct_header = f"\n\nPERCENTAGE BY {row_var.upper()} (Row %)\n"
        pct_header += "-" * (row_width + (len(cols) + 1) * col_width) + "\n"
        self.crosstab_text.insert(tk.END, pct_header)

        for row_val in rows:
            line = f"{str(row_val):<{row_width}}"
            row_total = row_totals[row_val]
            for col in cols:
                count = crosstab.get(row_val, {}).get(col, 0)
                pct = (count / row_total * 100) if row_total > 0 else 0
                line += f"{pct:>{col_width-1}.1f}%"
            line += f"{'100.0%':>{col_width}}\n"
            self.crosstab_text.insert(tk.END, line)
