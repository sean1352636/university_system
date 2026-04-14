"""Barber Shop GUI - Finance tab creation."""

from education_system.university_system.modules.domain.commerce.barber.gui.common import tk, ttk


class FinanceTabMixin:
    """Mixin that creates the finance management tab."""

    def create_finance_tab(self):
        """Create the finance management tab."""
        finance_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(finance_frame, text="Finance")

        # Daily summary frame
        summary_frame = ttk.LabelFrame(finance_frame, text="Daily Summary", padding="10")
        summary_frame.pack(fill=tk.X, pady=(0, 10))

        self.daily_sales_label = ttk.Label(summary_frame, text="Today's Sales: £0.00", font=('Helvetica', 12, 'bold'))
        self.daily_sales_label.pack(side=tk.LEFT, padx=20)

        self.cash_drawer_label = ttk.Label(summary_frame, text="Cash Drawer: £0.00")
        self.cash_drawer_label.pack(side=tk.LEFT, padx=20)

        self.outstanding_label = ttk.Label(summary_frame, text="Outstanding: £0.00")
        self.outstanding_label.pack(side=tk.LEFT, padx=20)

        ttk.Button(summary_frame, text="Refresh", command=self._update_finance_summary).pack(side=tk.RIGHT, padx=5)

        # Transactions list
        trans_frame = ttk.LabelFrame(finance_frame, text="Recent Transactions", padding="5")
        trans_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('id', 'date', 'customer', 'service', 'amount', 'method', 'status')
        self.finance_tree = ttk.Treeview(trans_frame, columns=columns, show='headings', height=10)

        self.finance_tree.heading('id', text='ID')
        self.finance_tree.heading('date', text='Date')
        self.finance_tree.heading('customer', text='Customer')
        self.finance_tree.heading('service', text='Service')
        self.finance_tree.heading('amount', text='Amount')
        self.finance_tree.heading('method', text='Method')
        self.finance_tree.heading('status', text='Status')

        self.finance_tree.column('id', width=50)
        self.finance_tree.column('date', width=100)
        self.finance_tree.column('customer', width=150)
        self.finance_tree.column('service', width=150)
        self.finance_tree.column('amount', width=80)
        self.finance_tree.column('method', width=100)
        self.finance_tree.column('status', width=80)

        scrollbar = ttk.Scrollbar(trans_frame, orient=tk.VERTICAL, command=self.finance_tree.yview)
        self.finance_tree.configure(yscrollcommand=scrollbar.set)

        self.finance_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons
        action_frame = ttk.Frame(finance_frame)
        action_frame.pack(fill=tk.X, pady=5)

        ttk.Button(action_frame, text="Apply Discount", command=self.apply_discount).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="Issue Refund", command=self.issue_refund).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="Daily Sales", command=self.view_daily_sales).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="Financial Report", command=self.generate_financial_report).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="Cash Drawer", command=self.track_cash_drawer).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="Create Gift Card", command=self.create_gift_card).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="Redeem Gift Card", command=self.redeem_gift_card).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text="Outstanding Payments", command=self.view_outstanding_payments).pack(side=tk.LEFT, padx=3)
