"""Barber Shop GUI - Refunds tab creation."""

from education_system.university_system.modules.domain.commerce.barber.gui.common import (
    tk, ttk, _t,
)


class RefundsTabMixin:
    """Mixin that creates the refunds management tab."""

    def create_refunds_tab(self):
        """Create the refunds management tab."""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("Refunds", "Refunds"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(header_frame, text=_t("Barber Shop Refunds", "Barber Shop Refunds"),
                 font=('Arial', 14, 'bold')).pack(side=tk.LEFT)

        # Search frame
        search_frame = ttk.LabelFrame(tab, text=_t("Search", "Search"), padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text=_t("Search:", "Search:")).grid(row=0, column=0, sticky=tk.W, padx=5)
        self.refund_search_var = tk.StringVar()
        self.refund_search_var.trace('w', lambda *args: self.refresh_refunds_list())
        search_entry = ttk.Entry(search_frame, textvariable=self.refund_search_var, width=40)
        search_entry.grid(row=0, column=1, sticky=tk.W, padx=5)

        # Table frame
        table_frame = ttk.Frame(tab)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Create treeview with 7 columns
        columns = ('transaction_id', 'date', 'customer', 'amount', 'payment_method', 'status', 'reference')
        self.refunds_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        # Configure columns
        self.refunds_tree.heading('transaction_id', text=_t('Transaction ID', 'Transaction ID'))
        self.refunds_tree.heading('date', text=_t('Date', 'Date'))
        self.refunds_tree.heading('customer', text=_t('Customer', 'Customer'))
        self.refunds_tree.heading('amount', text=_t('Amount', 'Amount'))
        self.refunds_tree.heading('payment_method', text=_t('Payment Method', 'Payment Method'))
        self.refunds_tree.heading('status', text=_t('Status', 'Status'))
        self.refunds_tree.heading('reference', text=_t('Reference', 'Reference'))

        self.refunds_tree.column('transaction_id', width=100)
        self.refunds_tree.column('date', width=120)
        self.refunds_tree.column('customer', width=150)
        self.refunds_tree.column('amount', width=100)
        self.refunds_tree.column('payment_method', width=120)
        self.refunds_tree.column('status', width=100)
        self.refunds_tree.column('reference', width=150)

        # Scrollbars
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.refunds_tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.refunds_tree.xview)
        self.refunds_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.refunds_tree.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        vsb.grid(row=0, column=1, sticky=(tk.N, tk.S))
        hsb.grid(row=1, column=0, sticky=(tk.E, tk.W))

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Buttons frame
        buttons_frame = ttk.Frame(tab)
        buttons_frame.pack(fill=tk.X)

        ttk.Button(buttons_frame, text=_t("Process Refund", "Process Refund"),
                  command=self.process_barber_refund).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text=_t("View Details", "View Details"),
                  command=self.view_refund_transaction_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text=_t("Refresh", "Refresh"),
                  command=self.refresh_refunds_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text=_t("Export to CSV", "Export to CSV"),
                  command=self.export_refunds_to_csv).pack(side=tk.LEFT, padx=5)

        # Load data
        self.refresh_refunds_list()
