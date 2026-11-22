"""Parameter forms for finance operations.

Split out of ``bulk_operations_views.py``, which re-exports every name here.
"""

from __future__ import annotations

from tkinter import ttk

from education_system.systems.sixth_form.interfaces.gui.learners.bulk_operations.view_common import (
    _today,
)


class FinanceFormsMixin:
    """Parameter forms for finance operations."""

    def _build_bursary_form(self) -> None:
        from education_system.systems.sixth_form.domains.finance.domain.bursaries.bursaries import (
            BURSARY_TYPES, ELIGIBILITY_BASES, DEFAULT_TYPE,
        )
        f = self.params_frame
        self.p_btype = self._combo(f, 0, "Bursary type:",
                                       list(BURSARY_TYPES),
                                       default=DEFAULT_TYPE)
        self.p_amount = self._entry(f, 1, "Amount (£):", width=10)
        self.p_year = self._entry(f, 2, "Academic year:", width=10)
        self.p_basis = self._combo(f, 3, "Eligibility basis:",
                                       [""] + list(ELIGIBILITY_BASES),
                                       default="")
        self.p_note = self._entry(f, 4, "Decision note:")
        self.p_by = self._entry(f, 5, "Assessed by:")

    def _build_invoice_form(self) -> None:
        from education_system.systems.sixth_form.domains.finance.domain.fees.fees import (
            CATEGORIES, DEFAULT_CATEGORY,
        )
        f = self.params_frame
        self.p_desc = self._entry(f, 0, "Description:")
        self.p_cat = self._combo(f, 1, "Category:", list(CATEGORIES),
                                     default=DEFAULT_CATEGORY)
        self.p_amount = self._entry(f, 2, "Amount (£):", width=10)
        self.p_issued = self._entry(f, 3, "Issued date:",
                                        _today(), width=14)
        self.p_due = self._entry(f, 4, "Due date:", width=14)
        self.p_year = self._entry(f, 5, "Academic year:", width=10)

    def _build_discount_form(self) -> None:
        from education_system.systems.sixth_form.domains.finance.domain.fees.fees import (
            CATEGORIES, DEFAULT_CATEGORY,
        )
        f = self.params_frame
        self.p_desc = self._entry(f, 0, "Description:")
        self.p_amount = self._entry(
            f, 1, "Discount £ (positive):", width=10)
        self.p_cat = self._combo(f, 2, "Category:", list(CATEGORIES),
                                     default=DEFAULT_CATEGORY)
        self.p_issued = self._entry(f, 3, "Issued date:",
                                        _today(), width=14)
        self.p_year = self._entry(f, 4, "Academic year:", width=10)

    def _build_import_payments_form(self) -> None:
        f = self.params_frame
        ttk.Label(f, text=("Required: fee_id, amount, paid_on, method\n"
                            "Optional: reference, notes"),
                   foreground="#555").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        self.p_csv = self._entry(f, 1, "CSV path:", width=46)
        from education_system.platform.delivery.gui.parented_dialogs import filedialog

        def _browse() -> None:
            path = filedialog.askopenfilename(
                title="Pick payments CSV",
                filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
            if path:
                self.p_csv.delete(0, "end")
                self.p_csv.insert(0, path)

        ttk.Button(f, text="Browse…", command=_browse).grid(
            row=1, column=2, sticky="w", padx=4)

    def _build_statements_form(self) -> None:
        f = self.params_frame
        self.p_outdir = self._entry(f, 0, "Output dir:", width=46)
        self.p_year = self._entry(f, 1, "Academic year (filter):",
                                      width=10)
        from education_system.platform.delivery.gui.parented_dialogs import filedialog

        def _browse() -> None:
            path = filedialog.askdirectory(
                title="Pick output directory")
            if path:
                self.p_outdir.delete(0, "end")
                self.p_outdir.insert(0, path)

        ttk.Button(f, text="Browse…", command=_browse).grid(
            row=0, column=2, sticky="w", padx=4)
