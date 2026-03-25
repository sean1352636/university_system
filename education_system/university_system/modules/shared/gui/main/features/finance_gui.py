# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox
import logging

# Alias for translation function (underscore names not exported by import *)
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

# Import database connection
from education_system.university_system.infrastructure.database.db import get_db_connection, get_connection, transaction

# Import GUI availability flags and classes
from education_system.university_system.modules.shared.gui.main.imports.gui_imports import (
    FINANCE_REPORTING_GUI_AVAILABLE,
    FinancialManagementGUI,
    FinancialAidGUI,
)

logger = logging.getLogger(__name__)

def show_finance_management(self):
    """Launch the Finance Management GUI in a child window, fallback to CLI if needed."""
    if self.finance_gui:
        self.finance_gui.show_finance_management()
    else:
        try:
            from education_system.university_system.modules.shared.cli.cli_main import display_finance_menu
            from education_system.university_system.modules.domain.finance.core.financial_core import set_finance_auth
            if self.auth:
                try:
                    set_finance_auth(self.auth)
                except Exception as e:
                    logger.warning(f"Failed to set finance auth: {e}")
            display_finance_menu()
        except ImportError:
            messagebox.showerror(_t("finance_gui.errors.title"), _t("finance_gui.errors.gui_and_cli_unavailable"))
def show_finance_reporting_dashboard(self):
    """Launch the Finance Reporting Dashboard GUI in a child window."""
    try:
        if not FINANCE_REPORTING_GUI_AVAILABLE:
            messagebox.showerror(_t("finance_gui.errors.title"), _t("finance_gui.errors.reporting_unavailable"))
            return

        # Create new window for Finance Reporting
        finance_window = tk.Toplevel(self.root)
        finance_window.title(_t("finance_gui.reporting.title"))
        finance_window.geometry("1200x800")

        # Initialize Finance Reporting GUI
        finance_gui = FinancialManagementGUI(finance_window, self.auth)
        print("✅ Finance Reporting GUI opened successfully")

    except Exception as e:
        messagebox.showerror(_t("finance_gui.errors.title"), _t("finance_gui.errors.failed_to_open_reporting", error=str(e)))
        print(f"❌ Finance Reporting error: {e}")
def show_student_finance_account(self):
    """Launch the Enhanced Student Finance Account GUI for students to view their balance and transactions."""
    if not self.auth or not self.auth.current_user:
        messagebox.showerror(_t("common.error"), _t("finance_gui.errors.login_required"))
        return

    try:
        from education_system.university_system.modules.shared.utils.finance_integration import (
            ensure_student_finance_account_exists,
            top_up_student_finance_account
        )
        from education_system.university_system.infrastructure.database.db import get_connection

        # Get current user's student ID
        current_user = self.auth.current_user
        student_id = current_user.get('student_id') or current_user.get('username')
        first_name = current_user.get('first_name', '')
        last_name = current_user.get('last_name', '')
        student_name = f"{first_name} {last_name}".strip() or student_id

        # Ensure account exists
        ensure_student_finance_account_exists(student_id)

        # Create window
        account_window = tk.Toplevel(self.root)
        account_window.title(_t("finance_gui.account.title"))
        account_window.geometry("1000x800")
        account_window.minsize(900, 700)

        # Create main scrollable container
        main_canvas = tk.Canvas(account_window, bg='white', highlightthickness=0)
        scrollbar = ttk.Scrollbar(account_window, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )

        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)

        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling
        def on_mousewheel(event):
            main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        main_canvas.bind_all("<MouseWheel>", on_mousewheel)

        # Variables for dynamic updates
        balance_var = tk.StringVar(value="Loading...")
        total_deposited_var = tk.StringVar(value="£0.00")
        total_spent_var = tk.StringVar(value="£0.00")
        transaction_count_var = tk.StringVar(value="0")

        def refresh_all_data():
            """Refresh balance and statistics"""
            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Get balance
                cursor.execute('SELECT balance FROM student_finance_accounts WHERE student_id = ?', (student_id,))
                result = cursor.fetchone()
                balance = result[0] if result else 0.0
                balance_var.set(f"£{balance:,.2f}")

                # Get statistics
                cursor.execute('''
                    SELECT
                        COUNT(*) as total_transactions,
                        COALESCE(SUM(CASE WHEN transaction_type IN ('top_up', 'deposit', 'refund') THEN amount ELSE 0 END), 0) as total_deposited,
                        COALESCE(SUM(CASE WHEN transaction_type IN ('use', 'withdrawal', 'payment') THEN amount ELSE 0 END), 0) as total_spent
                    FROM transactions
                    WHERE source_type = 'student_finance' AND student_id = ?
                ''', (student_id,))
                stats = cursor.fetchone()

                if stats:
                    transaction_count_var.set(str(stats[0]))
                    total_deposited_var.set(f"£{stats[1]:,.2f}")
                    total_spent_var.set(f"£{stats[2]:,.2f}")

                # Refresh transaction list
                load_transactions()

                conn.close()
            except Exception as e:
                balance_var.set(f"Error: {e}")

        # ==== HEADER SECTION ====
        header_frame = tk.Frame(scrollable_frame, bg='#2c3e50')
        header_frame.pack(fill='x', pady=(0, 20))

        tk.Label(header_frame, text=_t("finance_gui.account.header", name=student_name),
                font=('Arial', 16, 'bold'), bg='#2c3e50', fg='white', pady=15).pack()

        # ==== BALANCE CARD ====
        balance_card = tk.Frame(scrollable_frame, bg='#27ae60', relief='raised', bd=2)
        balance_card.pack(fill='x', padx=20, pady=10)

        tk.Label(balance_card, text=_t("finance_gui.account.current_balance"),
                font=('Arial', 12, 'bold'), bg='#27ae60', fg='white').pack(pady=(15, 5))
        tk.Label(balance_card, textvariable=balance_var,
                font=('Arial', 32, 'bold'), bg='#27ae60', fg='white').pack(pady=5)

        refresh_btn = tk.Button(balance_card, text="🔄 Refresh", command=refresh_all_data,
                               bg='#229954', fg='white', font=('Arial', 10, 'bold'),
                               relief='flat', padx=20, pady=5, cursor='hand2')
        refresh_btn.pack(pady=(5, 15))

        # ==== STATISTICS CARDS ====
        stats_container = tk.Frame(scrollable_frame, bg='white')
        stats_container.pack(fill='x', padx=20, pady=10)

        # Total Deposited Card
        deposit_card = tk.Frame(stats_container, bg='#3498db', relief='raised', bd=2)
        deposit_card.pack(side='left', expand=True, fill='both', padx=5)
        tk.Label(deposit_card, text=_t("finance_gui.account.total_deposited"), font=('Arial', 10, 'bold'),
                bg='#3498db', fg='white').pack(pady=(10, 5))
        tk.Label(deposit_card, textvariable=total_deposited_var, font=('Arial', 18, 'bold'),
                bg='#3498db', fg='white').pack(pady=(0, 10))

        # Total Spent Card
        spent_card = tk.Frame(stats_container, bg='#e74c3c', relief='raised', bd=2)
        spent_card.pack(side='left', expand=True, fill='both', padx=5)
        tk.Label(spent_card, text=_t("finance_gui.account.total_spent"), font=('Arial', 10, 'bold'),
                bg='#e74c3c', fg='white').pack(pady=(10, 5))
        tk.Label(spent_card, textvariable=total_spent_var, font=('Arial', 18, 'bold'),
                bg='#e74c3c', fg='white').pack(pady=(0, 10))

        # Transactions Count Card
        count_card = tk.Frame(stats_container, bg='#f39c12', relief='raised', bd=2)
        count_card.pack(side='left', expand=True, fill='both', padx=5)
        tk.Label(count_card, text=_t("finance_gui.account.transactions"), font=('Arial', 10, 'bold'),
                bg='#f39c12', fg='white').pack(pady=(10, 5))
        tk.Label(count_card, textvariable=transaction_count_var, font=('Arial', 18, 'bold'),
                bg='#f39c12', fg='white').pack(pady=(0, 10))

        # ==== QUICK ACTIONS ====
        actions_frame = ttk.LabelFrame(scrollable_frame, text=_t("finance_gui.account.quick_actions"), padding=15)
        actions_frame.pack(fill='x', padx=20, pady=15)

        # Quick amount buttons
        tk.Label(actions_frame, text=_t("finance_gui.account.quick_top_up_amounts"), font=('Arial', 9, 'bold')).pack(anchor='w', pady=(0, 5))
        quick_amounts = tk.Frame(actions_frame, bg='white')
        quick_amounts.pack(fill='x')

        def quick_top_up(amount):
            """Quick top-up with preset amount"""
            try:
                processed_by = self.auth.current_user.get('username', 'Unknown') if self.auth.current_user else 'Unknown'

                result = top_up_student_finance_account(
                    student_id=student_id,
                    amount=amount,
                    payment_method='quick_topup',
                    processed_by=processed_by
                )

                if result['success']:
                    messagebox.showinfo(_t("common.success"), _t("finance_gui.account.top_up_success", amount=amount, balance=result['new_balance']))
                    refresh_all_data()
                else:
                    messagebox.showerror(_t("common.error"), result['message'])
            except Exception as e:
                messagebox.showerror(_t("common.error"), _t("finance_gui.account.top_up_failed", error=str(e)))

        for amount in [10, 20, 50, 100]:
            tk.Button(quick_amounts, text=f"£{amount}", command=lambda amt=amount: quick_top_up(amt),
                     bg='#ecf0f1', fg='#2c3e50', font=('Arial', 10, 'bold'),
                     relief='flat', padx=15, pady=5, cursor='hand2').pack(side='left', padx=3)

        # ==== RECENT TRANSACTIONS ====
        trans_frame = ttk.LabelFrame(scrollable_frame, text="📜 Recent Transactions (Last 20)", padding=10)
        trans_frame.pack(fill='both', expand=True, padx=20, pady=15)

        # Filter buttons
        filter_frame = tk.Frame(trans_frame)
        filter_frame.pack(fill='x', pady=(0, 10))

        filter_var = tk.StringVar(value='all')

        def apply_filter():
            load_transactions(filter_var.get())

        tk.Radiobutton(filter_frame, text="All", variable=filter_var, value='all',
                      command=apply_filter).pack(side='left', padx=5)
        tk.Radiobutton(filter_frame, text="Deposits ⬆️", variable=filter_var, value='deposit',
                      command=apply_filter).pack(side='left', padx=5)
        tk.Radiobutton(filter_frame, text="Spending ⬇️", variable=filter_var, value='spend',
                      command=apply_filter).pack(side='left', padx=5)

        # Export button
        def export_transactions():
            try:
                import csv
                from tkinter import filedialog

                filename = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    initialfile=f"finance_account_{student_id}.csv"
                )

                if not filename:
                    return

                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT created_at, transaction_type, amount, balance_after, description
                    FROM transactions
                    WHERE source_type = 'student_finance' AND student_id = ?
                    ORDER BY created_at DESC
                ''', (student_id,))

                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Date/Time', 'Type', 'Amount', 'Balance After', 'Description'])
                    writer.writerows(cursor.fetchall())

                conn.close()
                messagebox.showinfo(_t("common.success"), _t("finance_gui.account.export_success", filename=filename))
            except Exception as e:
                messagebox.showerror(_t("common.error"), _t("finance_gui.account.export_failed", error=str(e)))

        tk.Button(filter_frame, text="📥 Export CSV", command=export_transactions,
                 bg='#34495e', fg='white', font=('Arial', 9, 'bold'),
                 relief='flat', padx=10, pady=3, cursor='hand2').pack(side='right', padx=5)

        # Transaction table
        trans_table_frame = tk.Frame(trans_frame)
        trans_table_frame.pack(fill='both', expand=True)

        columns = ('Date', 'Type', 'Amount', 'Balance', 'Description')
        trans_tree = ttk.Treeview(trans_table_frame, columns=columns, show='headings', height=10)

        trans_tree.heading('Date', text='Date/Time')
        trans_tree.heading('Type', text='Type')
        trans_tree.heading('Amount', text='Amount')
        trans_tree.heading('Balance', text='Balance After')
        trans_tree.heading('Description', text='Description')

        trans_tree.column('Date', width=150, anchor='center')
        trans_tree.column('Type', width=100, anchor='center')
        trans_tree.column('Amount', width=100, anchor='e')
        trans_tree.column('Balance', width=100, anchor='e')
        trans_tree.column('Description', width=250, anchor='w')

        trans_scrollbar = ttk.Scrollbar(trans_table_frame, orient='vertical', command=trans_tree.yview)
        trans_tree.configure(yscrollcommand=trans_scrollbar.set)

        trans_tree.pack(side='left', fill='both', expand=True)
        trans_scrollbar.pack(side='right', fill='y')

        def load_transactions(filter_type='all'):
            """Load and display transactions"""
            for item in trans_tree.get_children():
                trans_tree.delete(item)

            try:
                conn = get_connection()
                cursor = conn.cursor()

                if filter_type == 'deposit':
                    cursor.execute('''
                        SELECT created_at, transaction_type, amount, balance_after, description
                        FROM transactions
                        WHERE source_type = 'student_finance' AND student_id = ? AND transaction_type IN ('top_up', 'deposit', 'refund')
                        ORDER BY created_at DESC
                        LIMIT 20
                    ''', (student_id,))
                elif filter_type == 'spend':
                    cursor.execute('''
                        SELECT created_at, transaction_type, amount, balance_after, description
                        FROM transactions
                        WHERE source_type = 'student_finance' AND student_id = ? AND transaction_type IN ('use', 'withdrawal', 'payment')
                        ORDER BY created_at DESC
                        LIMIT 20
                    ''', (student_id,))
                else:
                    cursor.execute('''
                        SELECT created_at, transaction_type, amount, balance_after, description
                        FROM transactions
                        WHERE source_type = 'student_finance' AND student_id = ?
                        ORDER BY created_at DESC
                        LIMIT 20
                    ''', (student_id,))

                for row in cursor.fetchall():
                    trans_type = row[1].replace('_', ' ').title()

                    # Format amount with +/- indicator
                    if row[1] in ['use', 'withdrawal', 'payment']:
                        amount_str = f"-£{row[2]:.2f}"
                        tag = 'negative'
                    else:
                        amount_str = f"+£{row[2]:.2f}"
                        tag = 'positive'

                    trans_tree.insert('', 'end', values=(
                        row[0], trans_type, amount_str, f"£{row[3]:.2f}", row[4] or ''
                    ), tags=(tag,))

                # Configure tag colors
                trans_tree.tag_configure('positive', foreground='#27ae60')
                trans_tree.tag_configure('negative', foreground='#e74c3c')

                conn.close()
            except Exception as e:
                print(f"Error loading transactions: {e}")

        # Initial data load
        refresh_all_data()

        print("✅ Enhanced Student Finance Account GUI opened successfully")

    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("finance_gui.account.failed_to_open", error=str(e)))
        print(f"❌ Student Finance Account error: {e}")
        import traceback
        traceback.print_exc()
def show_financial_aid(self):
    """Launch the Financial Aid & Scholarships GUI in a child window."""
    if not self.auth.current_user:
        messagebox.showerror(_t("finance_gui.errors.title"), _t("finance_gui.errors.login_required_aid"))
        return

    try:
        # Create new window for Financial Aid
        aid_window = tk.Toplevel(self.root)
        aid_window.title(_t("finance_gui.aid.title"))
        aid_window.geometry("1200x800")

        # Initialize Financial Aid GUI
        aid_gui = FinancialAidGUI(auth_instance=self.auth, parent=aid_window)
        aid_gui.create_embedded_interface()
        print("✅ Financial Aid GUI opened successfully")

    except Exception as e:
        messagebox.showerror(_t("finance_gui.errors.title"), _t("finance_gui.errors.failed_to_open_aid", error=str(e)))
        print(f"❌ Financial Aid error: {e}")
def show_club_payment_management(self):
    """Launch the Club Payment Management interface in a child window."""
    if not self.auth.current_user:
        messagebox.showerror(_t("finance_gui.errors.title"), _t("finance_gui.errors.login_required_club_payment"))
        return

    try:
        # Create new window for Club Payment Management
        payment_window = tk.Toplevel(self.root)
        payment_window.title(_t("finance_gui.club_payment.title"))
        payment_window.geometry("1200x800")

        # Create main frame
        main_frame = ttk.Frame(payment_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text=_t("finance_gui.club_payment.header"),
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)

        # Create notebook for different sections
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=10)

        # Payment Overview Tab
        overview_frame = ttk.Frame(notebook, padding="10")
        notebook.add(overview_frame, text=_t("finance_gui.club_payment.tabs.overview"))
        self._create_payment_overview_tab_finance(overview_frame)

        # Record Payment Tab
        record_frame = ttk.Frame(notebook, padding="10")
        notebook.add(record_frame, text=_t("finance_gui.club_payment.tabs.record"))
        self._create_record_payment_tab_finance(record_frame)

        # Payment History Tab
        history_frame = ttk.Frame(notebook, padding="10")
        notebook.add(history_frame, text=_t("finance_gui.club_payment.tabs.history"))
        self._create_payment_history_tab_finance(history_frame)

        print("✅ Club Payment Management opened successfully")

    except Exception as e:
        messagebox.showerror(_t("finance_gui.errors.title"), _t("finance_gui.errors.failed_to_open_club_payment", error=str(e)))
        print(f"❌ Club Payment Management error: {e}")
def _create_payment_overview_tab_finance(self, parent):
    """Create payment overview tab for club payments"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get summary statistics
        cursor.execute('''
            SELECT
                COUNT(*) as total_payments,
                SUM(amount) as total_amount,
                COUNT(DISTINCT reference_id) as clubs_with_payments
            FROM payments
            WHERE source_type = 'club'
              AND payment_date >= date('now', '-30 days')
        ''')
        stats = cursor.fetchone()

        # Display statistics
        stats_frame = ttk.LabelFrame(parent, text=_t("finance_gui.club_payment.stats_section"), padding="10")
        stats_frame.pack(fill=tk.X, pady=10)

        if stats:
            ttk.Label(stats_frame, text=_t("finance_gui.club_payment.total_payments", count=stats[0] or 0),
                     font=('Arial', 12)).pack(anchor='w', pady=5)
            ttk.Label(stats_frame, text=_t("finance_gui.club_payment.total_amount", amount=f"{stats[1] or 0:.2f}"),
                     font=('Arial', 12)).pack(anchor='w', pady=5)
            ttk.Label(stats_frame, text=_t("finance_gui.club_payment.clubs_with_payments", count=stats[2] or 0),
                     font=('Arial', 12)).pack(anchor='w', pady=5)

        conn.close()

    except Exception as e:
        ttk.Label(parent, text=_t("finance_gui.errors.loading_stats", error=str(e))).pack()
def _create_record_payment_tab_finance(self, parent):
    """Create tab for recording new club payments"""
    ttk.Label(parent, text=_t("finance_gui.club_payment.record_description"),
             font=('Arial', 12)).pack(pady=20)
    ttk.Label(parent, text=_t("finance_gui.club_payment.integration_note"),
             font=('Arial', 10), foreground='gray').pack()
def _create_payment_history_tab_finance(self, parent):
    """Create tab for viewing payment history"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Create treeview for payment history
        columns = ('Date', 'Club', 'Amount', 'Type', 'Status')
        tree = ttk.Treeview(parent, columns=columns, show='headings', height=15)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150)

        tree.pack(fill=tk.BOTH, expand=True, pady=10)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)

        # Load recent payments
        cursor.execute('''
            SELECT cp.payment_date, sc.club_name, cp.amount, cp.payment_type, cp.status
            FROM payments cp
            JOIN student_clubs sc ON CAST(cp.reference_id AS INTEGER) = sc.club_id
            WHERE cp.source_type = 'club'
            ORDER BY cp.payment_date DESC
            LIMIT 100
        ''')
        payments = cursor.fetchall()

        for payment in payments:
            tree.insert('', tk.END, values=payment)

        conn.close()

    except Exception as e:
        ttk.Label(parent, text=_t("finance_gui.errors.loading_history", error=str(e))).pack()
