"""BettingShopBase mixin."""

from .shared import *


class BettingShopBaseMixin:
    def __init__(self, root, auth):
        """Initialize the Betting Shop GUI"""
        self.root = root
        self.auth = auth

        # Authentication check
        if not auth or not hasattr(auth, 'current_user') or not auth.current_user:
            messagebox.showerror(
                _t("common.error", default="Error"),
                _t("betting.errors.login_required", default="You must be logged in to access the Betting Shop")
            )
            return

        self.current_user = auth.current_user
        self.user_role = self.current_user.get('role', 'student')
        self.user_id = self.current_user.get('id', self.current_user.get('username'))

        # Use passed window (root is already a Toplevel from the launcher)
        self.window = root
        self.window.title(_t("betting.window_title", default="University Betting Shop"))
        # Centre on screen, but never place the window off the top/left edge
        # (on screens smaller than 1400x900 the naive centre offset goes
        # negative, hiding the header buttons above/left of the visible area).
        win_w, win_h = 1400, 900
        pos_x = max(0, (self.window.winfo_screenwidth() - win_w) // 2)
        pos_y = max(0, (self.window.winfo_screenheight() - win_h) // 2)
        self.window.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        self.window.minsize(1200, 800)

        # Initialize data
        self.account = None
        self.current_session = None
        self.admin_email = "admin@university.edu"

        # Initialize database
        self._init_database()

        # Get or create betting account
        self._init_account()

        # Create UI
        self.create_widgets()

        # Log access
        log_activity('Accessed Betting Shop GUI', user=self.current_user.get('username'))
        print("Betting Shop GUI opened successfully")

    def create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title and balance bar
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            title_frame,
            text=_t("betting.title", default="===== BETTING ====="),
            font=('Arial', 18, 'bold')
        ).pack(side=tk.LEFT)

        # Balance display
        balance_frame = ttk.Frame(title_frame)
        balance_frame.pack(side=tk.RIGHT)

        ttk.Label(balance_frame, text=_t("betting.labels.balance", default="Balance") + ": ", font=('Arial', 11)).pack(side=tk.LEFT)
        self.balance_var = tk.StringVar(value=f"GBP {self.account['balance']:.2f}" if self.account else "GBP 0.00")
        ttk.Label(balance_frame, textvariable=self.balance_var, font=('Arial', 12, 'bold'), foreground='green').pack(side=tk.LEFT)

        ttk.Button(balance_frame, text=_t("betting.btn.deposit", default="Deposit"), command=self.deposit_funds).pack(side=tk.LEFT, padx=10)
        ttk.Button(balance_frame, text=_t("betting.btn.withdraw", default="Withdraw"), command=self.withdraw_funds).pack(side=tk.LEFT)

        # Bottom button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

        ttk.Button(
            button_frame,
            text=_t("common.return_to_main_menu", default="Return to Homescreen"),
            command=self.return_to_homescreen
        ).pack(side=tk.LEFT, pady=5)

        ttk.Button(
            button_frame,
            text=_t("common.refresh", default="Refresh"),
            command=self.refresh_all_data
        ).pack(side=tk.RIGHT, pady=5)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Create all tabs
        self.create_sports_tab()
        self.create_predictions_tab()
        self.create_casino_tab()
        self.create_account_tab()

        # Admin tab for staff
        if self.user_role in ['admin', 'staff']:
            self.create_admin_tab()

    def _init_database(self):
        """Initialize database tables for betting"""
        try:
            result = init_betting_db()
            if not result:
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("betting.warnings.db_init", default="Database initialization had issues")
                )
        except Exception as e:
            print(f"Warning: Database initialization error: {e}")

    def _get_user_details_from_db(self):
        """Fetch user name and email from the users table"""
        try:
            user_id = self.current_user.get('id')
            username = self.current_user.get('username')
            with get_connection() as conn:
                cursor = conn.execute(
                    """SELECT first_name, last_name, email
                       FROM users WHERE id = ? OR username = ?""",
                    (user_id, username)
                )
                row = cursor.fetchone()
            if row:
                first_name = row[0] or ''
                last_name = row[1] or ''
                email = row[2] or ''
                full_name = f"{first_name} {last_name}".strip() or username or 'Unknown'
                return full_name, email
            else:
                return username or 'Unknown', ''
        except Exception as e:
            logger.error(f"Error fetching user details: {e}")
            return self.current_user.get('username', 'Unknown'), ''

    def _init_account(self):
        """Initialize or get user betting account"""
        # Get user details from database
        user_name, user_email = self._get_user_details_from_db()
        self.user_name = user_name
        self.user_email = user_email

        self.account = AccountManager.get_or_create_account(
            user_id=self.user_id,
            username=self.current_user.get('username'),
            email=user_email
        )

    def return_to_homescreen(self):
        """Close the window and return to homescreen"""
        try:
            self.window.destroy()
        except Exception as e:
            print(f"Error closing window: {e}")

    def refresh_all_data(self):
        """Refresh all data in all tabs"""
        try:
            self._init_account()
            self.update_balance_display()
            self.load_sports_events()
            self.load_predictions()
            self.load_bet_history()
            messagebox.showinfo(
                _t("common.success", default="Success"),
                _t("betting.messages.data_refreshed", default="All data refreshed successfully")
            )
        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    def update_balance_display(self):
        """Update the balance display"""
        if self.account:
            self.account = AccountManager.get_account(self.user_id)
            self.balance_var.set(f"GBP {self.account['balance']:.2f}")
