"""Methods __init__ through create_products_tab."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import butcher_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class ButcherGUI:
    def __init__(self, parent: tk.Toplevel, auth):
        """Initialize the Butcher Shop GUI - Function 1"""
        self.parent = parent
        self.auth = auth
        self.current_user = auth.current_user if auth else None

        if not self.current_user:
            messagebox.showerror(_t("butcher.window_title"), _t("butcher.errors.login_required"))
            if parent:
                parent.destroy()
            return

        self.parent.title(_t("butcher.window_title"))
        self.parent.geometry("1400x900")
        self.parent.minsize(1200, 800)

        # Initialize database
        self._init_database()

        # Create main interface
        self.create_widgets()

        # Load initial data
        self.refresh_all_data()

        log_activity('access', 'butcher_shop', user_id=self.current_user.get('user_id'))

    def create_widgets(self):
        """Create the main GUI widgets - Function 2"""
        # Header frame
        header_frame = ttk.Frame(self.parent, padding="10")
        header_frame.pack(fill=tk.X)

        ttk.Label(header_frame, text=_t("butcher.title"),
                 font=('Helvetica', 16, 'bold')).pack(side=tk.LEFT)

        user_info = f"{self.current_user.get('username')} ({self.current_user.get('role')})"
        ttk.Label(header_frame, text=user_info).pack(side=tk.RIGHT)

        # Main notebook for tabs
        self.notebook = ttk.Notebook(self.parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Create tabs
        self.create_products_tab()
        self.create_orders_tab()
        self.create_refunds_tab()
        self.create_inventory_tab()
        self.create_reports_tab()

        # Bottom buttons
        btn_frame = ttk.Frame(self.parent, padding="10")
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text=_t("common.refresh"),
                  command=self.refresh_all_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("butcher.btn.return_home"),
                  command=self.return_to_homescreen).pack(side=tk.RIGHT, padx=5)

    def _init_database(self):
        """Initialize database tables - Function 3"""
        from education_system.systems.university.domain.operations.commerce.butcher.services.butcher_core import init_butcher_db
        try:
            init_butcher_db()
        except Exception as e:
            logger.error(f"Failed to initialize butcher database: {e}")

    def return_to_homescreen(self):
        """Return to the main homescreen - Function 4"""
        if messagebox.askyesno(_t("common.confirm"), _t("butcher.confirm.exit")):
            self.parent.destroy()

    def _get_user_email(self) -> str:
        """Fetch user email from the users table."""
        try:
            with get_connection() as conn:
                cursor = conn.execute(
                    "SELECT email FROM users WHERE username = ?",
                    (self.current_user.get('username'),)
                )
                row = cursor.fetchone()
                if row and row[0]:
                    return row[0]
        except Exception as e:
            print(f"Error fetching user email: {e}")
        return ''

    def _get_student_account_balance(self) -> Optional[float]:
        """Get student's finance account balance."""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT balance FROM student_finance_accounts
                    WHERE student_id = ? AND account_status = 'active'
                ''', (self.current_user.get('username'),))
                row = cursor.fetchone()
                return float(row[0]) if row else None
        except Exception as e:
            print(f"Error getting student balance: {e}")
            return None

    def _deduct_from_student_account(self, amount: float) -> bool:
        """Deduct amount from student's finance account."""
        try:
            with transaction() as conn:
                # Get account details
                cursor = conn.execute('''
                    SELECT account_id, balance FROM student_finance_accounts
                    WHERE student_id = ? AND account_status = 'active'
                ''', (self.current_user.get('username'),))
                row = cursor.fetchone()
                if not row:
                    messagebox.showerror(_t("butcher.window_title"), _t('gui.operations.commerce.butcher.butcher_gui_parts.butchergui_init.dialogs.no_active_student_finance_account_found', default="No active student finance account found."))
                    return False

                account_id = row[0]
                current_balance = float(row[1])

                if current_balance < amount:
                    messagebox.showerror(_t("butcher.window_title"),
                                        f"Insufficient balance. Available: GBP {current_balance:.2f}")
                    return False

                new_balance = current_balance - amount

                # Update balance
                conn.execute('''
                    UPDATE student_finance_accounts
                    SET balance = ?, updated_at = ?
                    WHERE account_id = ?
                ''', (new_balance, datetime.now().isoformat(), account_id))

                # Record transaction
                conn.execute('''
                    INSERT INTO transactions
                    (source_type, account_id, student_id, transaction_type, amount, balance_before, balance_after,
                     description, reference_id, processed_by, created_at)
                    VALUES ('student_finance', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (account_id, self.current_user.get('username'), 'debit', amount,
                      current_balance, new_balance, 'Butcher Shop Purchase',
                      f"BUTCHER-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                      self.current_user.get('username'), datetime.now().isoformat()))

                return True
        except Exception as e:
            print(f"Error deducting from student account: {e}")
            return False

    def _add_to_revenue(self, amount: float, description: str, reference: str):
        """Add payment to central finance revenue.

        8.117.104: routed through unified record_payment() with
        ``source_type='butcher'``.
        """
        try:
            student_id = self.current_user.get('student_id') or self.current_user.get('username')
            from education_system.systems.university.domains.finance.domain.core.unified_payments import (
                record_payment,
            )
            record_payment(
                student_id=student_id,
                amount=amount,
                payment_method='butcher_shop',
                source_type='butcher',
                source_payment_id=reference,
                payment_type='revenue',
                department='butcher',
                description=description,
                created_by=self.current_user.get('username'),
            )
            with transaction() as conn:

                # Try to add to finance revenue tracking if table exists
                try:
                    conn.execute('''
                        INSERT INTO finance_revenue (source, amount, category, description,
                                                    recorded_by, recorded_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', ('butcher_shop', amount, 'food_services', description,
                          self.current_user.get('username'), datetime.now().isoformat()))
                except Exception:
                    pass  # Table may not exist

                log_activity('revenue', 'butcher_shop',
                            details={'amount': amount, 'reference': reference})
        except Exception as e:
            print(f"Finance integration error: {e}")

    def _show_payment_dialog(self, amount: float, description: str) -> Optional[str]:
        """Show payment method selection dialog."""
        result = {'method': None}

        dialog = tk.Toplevel(self.parent)
        dialog.title(_t("butcher.labels.payment_method"))
        dialog.geometry("400x350")
        dialog.transient(self.parent)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = self.parent.winfo_x() + (self.parent.winfo_width() - 400) // 2
        y = self.parent.winfo_y() + (self.parent.winfo_height() - 350) // 2
        dialog.geometry(f"+{x}+{y}")

        # Header
        ttk.Label(dialog, text=_t("butcher.labels.select_payment_method"),
                 font=('Helvetica', 14, 'bold')).pack(pady=15)

        # Amount display
        ttk.Label(dialog, text=description,
                 font=('Helvetica', 10)).pack(pady=5)
        ttk.Label(dialog, text=f"Total: GBP {amount:.2f}",
                 font=('Helvetica', 16, 'bold'), foreground='green').pack(pady=10)

        # Payment options frame
        options_frame = ttk.LabelFrame(dialog, text=_t("butcher.labels.payment_options"), padding="15")
        options_frame.pack(fill=tk.X, padx=20, pady=10)

        payment_var = tk.StringVar(value=_t('gui.operations.commerce.butcher.butcher_gui_parts.butchergui_init.values.card', default="Card"))

        # Cash option
        ttk.Radiobutton(options_frame, text=_t("butcher.btn.cash"), variable=payment_var,
                       value="Cash").pack(anchor=tk.W, pady=5)

        # Card option
        ttk.Radiobutton(options_frame, text=_t("butcher.btn.card"), variable=payment_var,
                       value="Card").pack(anchor=tk.W, pady=5)

        # Student Account option with balance
        student_balance = self._get_student_account_balance()
        if student_balance is not None:
            balance_text = f"Student Account (Balance: GBP {student_balance:.2f})"
            if student_balance < amount:
                balance_text += " - INSUFFICIENT"
            rb = ttk.Radiobutton(options_frame, text=balance_text, variable=payment_var,
                                value="Student Account")
            rb.pack(anchor=tk.W, pady=5)
            if student_balance < amount:
                rb.configure(state='disabled')
        else:
            ttk.Label(options_frame, text=_t("butcher.labels.student_account_na"),
                     foreground='gray').pack(anchor=tk.W, pady=5)

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)

        def confirm():
            result['method'] = payment_var.get()
            dialog.destroy()

        def cancel():
            dialog.destroy()

        ttk.Button(btn_frame, text=_t("butcher.btn.confirm_payment"), command=confirm).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t("butcher.btn.cancel"), command=cancel).pack(side=tk.LEFT, padx=10)

        dialog.wait_window()
        return result['method']

    def _get_admin_emails(self) -> List[str]:
        """Get email addresses of all admin users."""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT email FROM users
                    WHERE role = 'admin' AND email IS NOT NULL AND email != ''
                ''')
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting admin emails: {e}")
            return []

    def refresh_all_data(self):
        """Refresh all data in the GUI - Function 5"""
        try:
            self._load_products()
            self._load_orders()
            self._load_inventory()
        except Exception as e:
            logger.error(f"Error refreshing data: {e}")

    def create_products_tab(self):
        """Create the products management tab - Function 6"""
        products_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(products_frame, text=_t("butcher.tabs.products"))

        # Left side - Product list
        list_frame = ttk.LabelFrame(products_frame, text=_t("butcher.labels.product_list"), padding="5")
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # Category filter
        filter_frame = ttk.Frame(list_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(filter_frame, text=_t("butcher.labels.category") + ":").pack(side=tk.LEFT)
        self.category_filter = ttk.Combobox(filter_frame, state="readonly", width=20)
        self.category_filter['values'] = ['All'] + list(self._get_categories().values())
        self.category_filter.set('All')
        self.category_filter.pack(side=tk.LEFT, padx=5)
        self.category_filter.bind('<<ComboboxSelected>>', lambda e: self._load_products())

        # Products treeview
        columns = ('id', 'name', 'category', 'price', 'stock', 'unit')
        self.products_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        self.products_tree.heading('id', text=_t('butcher.columns.id'))
        self.products_tree.heading('name', text=_t("butcher.labels.product_name"))
        self.products_tree.heading('category', text=_t("butcher.labels.category"))
        self.products_tree.heading('price', text=_t("butcher.labels.price"))
        self.products_tree.heading('stock', text=_t("butcher.labels.stock"))
        self.products_tree.heading('unit', text=_t("butcher.labels.unit"))

        self.products_tree.column('id', width=50)
        self.products_tree.column('name', width=150)
        self.products_tree.column('category', width=100)
        self.products_tree.column('price', width=80)
        self.products_tree.column('stock', width=80)
        self.products_tree.column('unit', width=60)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.products_tree.yview)
        self.products_tree.configure(yscrollcommand=scrollbar.set)

        self.products_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Right side - Add/Edit product
        edit_frame = ttk.LabelFrame(products_frame, text=_t("butcher.labels.add_product"), padding="10")
        edit_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        # Product form fields
        ttk.Label(edit_frame, text=_t("butcher.labels.product_name") + ":").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.product_name_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.product_name_var, width=25).grid(row=0, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("butcher.labels.category") + ":").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.product_category_var = ttk.Combobox(edit_frame, state="readonly", width=22)
        self.product_category_var['values'] = list(self._get_categories().values())
        self.product_category_var.grid(row=1, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("butcher.labels.price") + " (£):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.product_price_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.product_price_var, width=25).grid(row=2, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("butcher.labels.unit") + ":").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.product_unit_var = ttk.Combobox(edit_frame, state="readonly", width=22)
        self.product_unit_var['values'] = ['kg', 'g', 'lb', 'oz', 'each', 'pack']
        self.product_unit_var.set('kg')
        self.product_unit_var.grid(row=3, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("butcher.labels.stock") + ":").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.product_stock_var = tk.StringVar(value="0")
        ttk.Entry(edit_frame, textvariable=self.product_stock_var, width=25).grid(row=4, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("butcher.labels.description") + ":").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.product_desc_text = tk.Text(edit_frame, width=25, height=3)
        self.product_desc_text.grid(row=5, column=1, pady=2)

        # Buttons
        btn_frame = ttk.Frame(edit_frame)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text=_t("butcher.btn.add_product"),
                  command=self.add_product).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t("butcher.btn.update_product"),
                  command=self.update_product).pack(side=tk.LEFT, padx=2)
