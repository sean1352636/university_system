"""Methods __init__ through create_costs_section."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import finance_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class LibraryFinanceManager:
    def __init__(self, root, auth=None):
        """Initialize manager with root window and auth"""
        self.root = root
        self.auth = auth
        self.conn = None

        # Color scheme
        self.colors = {
            'primary': '#2c3e50',
            'secondary': '#3498db',
            'success': '#27ae60',
            'warning': '#f39c12',
            'danger': '#e74c3c',
            'light': '#ecf0f1',
            'dark': '#34495e',
            'info': '#17a2b8',
            'library': '#9b59b6'  # Purple for library-specific items
        }

        # Current filter state
        self.start_date_var = tk.StringVar()
        self.end_date_var = tk.StringVar()
        self.search_var = tk.StringVar()

        # Create the main content frame
        self.content_frame = tk.Frame(root, bg='white')
        self.content_frame.pack(fill='both', expand=True)

        # Create the library finance interface
        self.create_library_finance_interface()

    def get_user_email(self, user_id):
        """Get user email address from database"""
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT email, first_name, last_name FROM users WHERE id = ?', (user_id,))
            result = cursor.fetchone()
            conn.close()

            if result:
                return {
                    'email': result[0],
                    'first_name': result[1],
                    'last_name': result[2],
                    'full_name': f"{result[1]} {result[2]}"
                }
            return None
        except Exception as e:
            print(f"Error getting user email: {e}")
            return None

    def send_fine_notification_email(self, user_info, fine_amount, book_title, due_date, days_overdue):
        """Send email notification when a fine is created"""
        try:
            if not user_info or not user_info.get('email'):
                return False

            # Render email from template
            from education_system.systems.university.infrastructure.email.template_utils import render_template

            subject, body = render_template('library/fine_notice', {
                'student_name': user_info['full_name'],
                'book_title': book_title,
                'due_date': due_date,
                'days_overdue': str(days_overdue),
                'fine_amount': f'{fine_amount:.2f}'
            })

            # Fallback if template not found
            if not subject or not body:
                subject = "Library Fine Notice - Overdue Book"
                body = f"""Dear {user_info['full_name']},

This is to notify you that a library fine has been assessed on your account.

FINE DETAILS:
Book Title:      {book_title}
Due Date:        {due_date}
Days Overdue:    {days_overdue}
Fine Amount:     £{fine_amount:.2f}

Please return the book and pay the fine at your earliest convenience.

Thank you,
University Library System
"""
            send_email_as_system(
                recipient_email=user_info['email'],
                subject=subject,
                body=body,
                system_name="Library System"
            )
            return True
        except Exception as e:
            print(f"Error sending fine notification email: {e}")
            return False

    def send_payment_receipt_email(self, user_info, fine_amount, payment_amount, payment_method,
                                   book_title, transaction_id, payment_date):
        """Send email receipt when a fine is paid"""
        try:
            if not user_info or not user_info.get('email'):
                return False

            # Render email from template
            from education_system.systems.university.infrastructure.email.template_utils import render_template

            subject, body = render_template('campus_services/library/payment_receipt', {
                'student_name': user_info['full_name'],
                'transaction_id': transaction_id,
                'payment_date': payment_date,
                'payment_method': payment_method,
                'book_title': book_title,
                'fine_amount': f'{fine_amount:.2f}',
                'payment_amount': f'{payment_amount:.2f}'
            })

            # Fallback if template not found
            if not subject or not body:
                subject = "Library Fine Payment Receipt"
                body = f"""Dear {user_info['full_name']},

Thank you for your payment. This email confirms your library fine payment.

PAYMENT RECEIPT
Receipt Number:  {transaction_id}
Payment Date:    {payment_date}
Payment Method:  {payment_method}

FINE DETAILS:
Book Title:      {book_title}
Original Fine:   £{fine_amount:.2f}
Amount Paid:     £{payment_amount:.2f}

Your payment has been processed successfully.

Best regards,
University Library System
"""
            send_email_as_system(
                recipient_email=user_info['email'],
                subject=subject,
                body=body,
                system_name="Library System"
            )
            return True
        except Exception as e:
            print(f"Error sending payment receipt email: {e}")
            return False

    def send_fine_waived_email(self, user_info, fine_amount, book_title, waiver_reason="Administrative action"):
        """Send email notification when a fine is deleted/waived"""
        try:
            if not user_info or not user_info.get('email'):
                return False

            # Render email from template
            from education_system.systems.university.infrastructure.email.template_utils import render_template

            subject, body = render_template('library/fine_waived', {
                'student_name': user_info['full_name'],
                'book_title': book_title,
                'fine_amount': f'{fine_amount:.2f}',
                'waiver_reason': waiver_reason
            })

            # Fallback if template not found
            if not subject or not body:
                subject = "Library Fine Waived - Good News!"
                body = f"""Dear {user_info['full_name']},

Good news! A library fine on your account has been waived.

WAIVED FINE DETAILS:
Book Title:      {book_title}
Fine Amount:     £{fine_amount:.2f}
Reason:          {waiver_reason}
Status:          WAIVED - No payment required

Your library account is now in good standing.

Best regards,
University Library System
"""
            send_email_as_system(
                recipient_email=user_info['email'],
                subject=subject,
                body=body,
                system_name="Library System"
            )
            return True
        except Exception as e:
            print(f"Error sending fine waived email: {e}")
            return False

    def create_library_finance_interface(self):
        """Create the Library Finance interface with all sections"""
        # Title
        title_label = tk.Label(
            self.content_frame,
            text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.labels.library_finance_management', default="Library Finance Management"),
            font=('Arial', 18, 'bold'),
            bg='white'
        )
        title_label.pack(pady=10)

        # Create notebook for different sections
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Tab 1: Fine Management
        fines_tab = tk.Frame(notebook, bg='white')
        notebook.add(fines_tab, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.tabs.fine_management', default="Fine Management"))
        self.create_fines_section(fines_tab)

        # Tab 2: Revenue Analytics
        revenue_tab = tk.Frame(notebook, bg='white')
        notebook.add(revenue_tab, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.tabs.revenue_analytics', default="Revenue Analytics"))
        self.create_revenue_section(revenue_tab)

        # Tab 3: Book Costs
        costs_tab = tk.Frame(notebook, bg='white')
        notebook.add(costs_tab, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.tabs.book_costs', default="Book Costs"))
        self.create_costs_section(costs_tab)

        # Tab 4: Financial Overview
        overview_tab = tk.Frame(notebook, bg='white')
        notebook.add(overview_tab, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.tabs.overview', default="Overview"))
        self.create_overview_section(overview_tab)

    def create_fines_section(self, parent):
        """Create fine management section with CRUD operations"""
        # Toolbar
        toolbar = tk.Frame(parent, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Label(toolbar, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.labels.search_user', default="Search User:"), bg='white', font=('Arial', 10)).pack(side='left', padx=5)
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=20)
        search_entry.pack(side='left', padx=5)

        tk.Button(toolbar, text=_("common.search"), command=self.search_fines,
                  bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.buttons.create_fine', default="Create Fine"), command=self.create_fine_dialog,
                  bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.buttons.edit_fine', default="Edit Fine"), command=self.edit_fine_dialog,
                  bg=self.colors['warning'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.buttons.delete_fine', default="Delete Fine"), command=self.delete_fine,
                  bg=self.colors['danger'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.buttons.process_payment', default="Process Payment"), command=self.process_payment_dialog,
                  bg=self.colors['library'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.buttons.process_refund', default="🔄 Process Refund"), command=self.process_refund_dialog,
                  bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text=_("common.refresh"), command=self.load_all_fines,
                  bg=self.colors['info'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        # Fines table
        table_frame = tk.Frame(parent, bg='white')
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(table_frame)
        y_scroll.pack(side='right', fill='y')
        x_scroll = ttk.Scrollbar(table_frame, orient='horizontal')
        x_scroll.pack(side='bottom', fill='x')

        columns = ('Loan ID', 'User ID', 'Name', 'Book ID', 'Title', 'Days Overdue', 'Fine Amount', 'Status')
        self.fines_tree = ttk.Treeview(table_frame, columns=columns, show='headings',
                                        yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        y_scroll.config(command=self.fines_tree.yview)
        x_scroll.config(command=self.fines_tree.xview)

        for col in columns:
            self.fines_tree.heading(col, text=col)
        self.fines_tree.column('Loan ID', width=80, anchor='center')
        self.fines_tree.column('User ID', width=100)
        self.fines_tree.column('Name', width=150)
        self.fines_tree.column('Book ID', width=100)
        self.fines_tree.column('Title', width=200)
        self.fines_tree.column('Days Overdue', width=100, anchor='center')
        self.fines_tree.column('Fine Amount', width=100, anchor='e')
        self.fines_tree.column('Status', width=100, anchor='center')
        self.fines_tree.pack(fill='both', expand=True)

        self.fines_summary_label = tk.Label(parent, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.labels.total_outstanding_fines_0_00_total_items_0', default="Total Outstanding Fines: £0.00 | Total Items: 0"),
                                             font=('Arial', 11, 'bold'), bg='white', fg=self.colors['primary'])
        self.fines_summary_label.pack(pady=10)

        self.root.after(100, self.load_all_fines)

    def create_revenue_section(self, parent):
        """Create revenue analytics section"""
        toolbar = tk.Frame(parent, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Label(toolbar, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.labels.start_date', default="Start Date:"), bg='white', font=('Arial', 10)).pack(side='left', padx=5)
        start_entry = ttk.Entry(toolbar, textvariable=self.start_date_var, width=12)
        start_entry.pack(side='left', padx=5)
        start_entry.insert(0, (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'))

        tk.Label(toolbar, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.labels.end_date', default="End Date:"), bg='white', font=('Arial', 10)).pack(side='left', padx=5)
        end_entry = ttk.Entry(toolbar, textvariable=self.end_date_var, width=12)
        end_entry.pack(side='left', padx=5)
        end_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

        tk.Button(toolbar, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.buttons.generate_report', default="Generate Report"), command=self.generate_revenue_report,
                  bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.buttons.show_charts', default="Show Charts"), command=self.show_revenue_charts,
                  bg=self.colors['info'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.buttons.export_csv', default="Export CSV"), command=self.export_revenue_csv,
                  bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.buttons.email_report_to_admin', default="Email Report to Admin"), command=self.email_revenue_report_to_admin,
                  bg=self.colors.get('warning', '#f39c12'), fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        stats_frame = tk.LabelFrame(parent, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.labels.revenue_statistics', default="Revenue Statistics"), bg='white', font=('Arial', 12, 'bold'))
        stats_frame.pack(fill='both', expand=True, padx=10, pady=10)
        # Headline figures as cards and the monthly breakdown as a table.
        # It was a fixed-width block in a Courier Text widget, whose column
        # padding only lined up while every amount stayed under five digits.
        self.revenue_stats_host = tk.Frame(stats_frame, bg='white', height=260)
        self.revenue_stats_host.pack(fill='both', expand=True, padx=10, pady=10)

        self.revenue_chart_frame = tk.Frame(parent, bg='white')
        self.revenue_chart_frame.pack(fill='both', expand=True, padx=10, pady=10)

    def create_costs_section(self, parent):
        """Create book costs section"""
        toolbar = tk.Frame(parent, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Button(toolbar, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.buttons.add_book_cost', default="Add Book Cost"), command=self.add_book_cost_dialog,
                  bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.buttons.edit_cost', default="Edit Cost"), command=self.edit_book_cost_dialog,
                  bg=self.colors['warning'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.buttons.cost_analysis', default="Cost Analysis"), command=self.show_cost_analysis,
                  bg=self.colors['info'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text=_("common.refresh"), command=self.load_book_costs,
                  bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        table_frame = tk.Frame(parent, bg='white')
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(table_frame)
        y_scroll.pack(side='right', fill='y')
        x_scroll = ttk.Scrollbar(table_frame, orient='horizontal')
        x_scroll.pack(side='bottom', fill='x')

        columns = ('Book ID', 'Title', 'Author', 'ISBN', 'Purchase Price', 'Purchase Date', 'Supplier', 'Quantity')
        self.costs_tree = ttk.Treeview(table_frame, columns=columns, show='headings',
                                        yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        y_scroll.config(command=self.costs_tree.yview)
        x_scroll.config(command=self.costs_tree.xview)

        for col in columns:
            self.costs_tree.heading(col, text=col)
        self.costs_tree.column('Book ID', width=80, anchor='center')
        self.costs_tree.column('Title', width=200)
        self.costs_tree.column('Author', width=150)
        self.costs_tree.column('ISBN', width=120)
        self.costs_tree.column('Purchase Price', width=100, anchor='e')
        self.costs_tree.column('Purchase Date', width=100, anchor='center')
        self.costs_tree.column('Supplier', width=150)
        self.costs_tree.column('Quantity', width=80, anchor='center')
        self.costs_tree.pack(fill='both', expand=True)

        self.costs_summary_label = tk.Label(parent, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_init.labels.total_book_investment_0_00_total_books_0', default="Total Book Investment: £0.00 | Total Books: 0"),
                                             font=('Arial', 11, 'bold'), bg='white', fg=self.colors['primary'])
        self.costs_summary_label.pack(pady=10)

        self.root.after(100, self.load_book_costs)
