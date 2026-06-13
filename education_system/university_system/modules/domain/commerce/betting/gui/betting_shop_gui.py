"""
Betting Shop GUI

Comprehensive GUI for university betting shop providing sports betting,
prediction markets, casino games, and account management with full
email and finance integration.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import traceback
import random

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.domain.commerce.betting.services.betting_core import (
    AccountManager, SportsBettingManager, PredictionMarketManager,
    CasinoManager, ReportManager, init_betting_db,
    MIN_BET, MAX_BET, MIN_DEPOSIT, MAX_DEPOSIT,
    CASINO_GAMES, PREDICTION_CATEGORIES, BET_STATUSES
)
from education_system.university_system.core.activity_logger import log_activity

# Import internationalization (i18n)
try:
    from education_system.university_system.core.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Import email service
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    from education_system.university_system.infrastructure.email.template_utils import render_template
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    def send_email(*args, **kwargs):
        print("Email service not available")
        return False
    render_template = None

# Import finance integration
try:
    from education_system.university_system.modules.domain.finance.core.finance_db_operations import (
        record_payment_to_finance,
        get_student_finance_account_balance,
        process_student_finance_account_payment
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False
    def record_payment_to_finance(*args, **kwargs):
        return None
    def get_student_finance_account_balance(*args, **kwargs):
        return 0.0
    def process_student_finance_account_payment(*args, **kwargs):
        return False

import logging
logger = logging.getLogger(__name__)


class BettingShopGUI:
    """Main Betting Shop GUI with 25 fully implemented functions"""

    # =========================================================================
    # FUNCTION 1: __init__ - Initialize GUI, auth check, database init
    # =========================================================================
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
        self.window.geometry("1400x900+%d+%d" % ((self.window.winfo_screenwidth() - 1400) // 2, (self.window.winfo_screenheight() - 900) // 2))
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

    # =========================================================================
    # FUNCTION 2: create_widgets - Build main UI with notebook tabs
    # =========================================================================
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
            text=_t("betting.title", default="University Betting Shop"),
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

    # =========================================================================
    # FUNCTION 3: _init_database - Initialize betting database tables
    # =========================================================================
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

    # =========================================================================
    # FUNCTION 4: return_to_homescreen - Close window and return to main menu
    # =========================================================================
    def return_to_homescreen(self):
        """Close the window and return to homescreen"""
        try:
            self.window.destroy()
        except Exception as e:
            print(f"Error closing window: {e}")

    # =========================================================================
    # FUNCTION 5: refresh_all_data - Reload all lists and data
    # =========================================================================
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

    # =========================================================================
    # FUNCTION 6: create_sports_tab - Tab for sports betting
    # =========================================================================
    def create_sports_tab(self):
        """Create sports betting tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("betting.tabs.sports", default="Sports Betting"))

        # Split view
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left: Events list
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(
            left_frame,
            text=_t("betting.upcoming_events", default="Upcoming Events"),
            font=('Arial', 12, 'bold')
        ).pack(pady=5)

        # Sport type filter
        filter_frame = ttk.Frame(left_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filter_frame, text=_t("betting.labels.sport", default="Sport") + ":").pack(side=tk.LEFT)
        self.sport_filter = ttk.Combobox(filter_frame, values=[
            _t("common.all", default="All"), 'Football', 'Basketball', 'Tennis', 'Cricket', 'Rugby', 'eSports'
        ], state='readonly', width=15)
        self.sport_filter.set(_t("common.all", default="All"))
        self.sport_filter.pack(side=tk.LEFT, padx=5)
        self.sport_filter.bind('<<ComboboxSelected>>', lambda e: self.load_sports_events())

        ttk.Button(filter_frame, text=_t("common.refresh", default="Refresh"), command=self.load_sports_events).pack(side=tk.RIGHT)

        # Events treeview
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ('id', 'event', 'date', 'odds_a', 'odds_b', 'draw')
        self.events_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        self.events_tree.heading('id', text='ID')
        self.events_tree.heading('event', text=_t("betting.labels.event", default="Event"))
        self.events_tree.heading('date', text=_t("betting.labels.date", default="Date"))
        self.events_tree.heading('odds_a', text=_t("betting.labels.home", default="Home"))
        self.events_tree.heading('odds_b', text=_t("betting.labels.away", default="Away"))
        self.events_tree.heading('draw', text=_t("betting.labels.draw", default="Draw"))

        self.events_tree.column('id', width=40)
        self.events_tree.column('event', width=200)
        self.events_tree.column('date', width=100)
        self.events_tree.column('odds_a', width=60)
        self.events_tree.column('odds_b', width=60)
        self.events_tree.column('draw', width=60)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.events_tree.yview)
        self.events_tree.configure(yscrollcommand=scrollbar.set)

        self.events_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.events_tree.bind('<<TreeviewSelect>>', self.on_event_select)

        # Right: Bet slip
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        bet_frame = ttk.LabelFrame(right_frame, text=_t("betting.bet_slip", default="Bet Slip"), padding="10")
        bet_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Event display
        ttk.Label(bet_frame, text=_t("betting.labels.selected_event", default="Selected Event") + ":").pack(anchor=tk.W)
        self.selected_event_var = tk.StringVar(value=_t("betting.select_event", default="Select an event to bet"))
        ttk.Label(bet_frame, textvariable=self.selected_event_var, font=('Arial', 10, 'bold'), wraplength=300).pack(anchor=tk.W, pady=5)

        # Selection
        ttk.Label(bet_frame, text=_t("betting.labels.your_selection", default="Your Selection") + ":").pack(anchor=tk.W, pady=(10, 0))
        self.selection_var = tk.StringVar(value='team_a')
        selections_frame = ttk.Frame(bet_frame)
        selections_frame.pack(fill=tk.X, pady=5)

        self.team_a_radio = ttk.Radiobutton(selections_frame, text=_t("betting.selections.home", default="Home"), variable=self.selection_var, value='team_a')
        self.team_a_radio.pack(side=tk.LEFT, padx=5)
        self.draw_radio = ttk.Radiobutton(selections_frame, text=_t("betting.selections.draw", default="Draw"), variable=self.selection_var, value='draw')
        self.draw_radio.pack(side=tk.LEFT, padx=5)
        self.team_b_radio = ttk.Radiobutton(selections_frame, text=_t("betting.selections.away", default="Away"), variable=self.selection_var, value='team_b')
        self.team_b_radio.pack(side=tk.LEFT, padx=5)

        # Odds display
        ttk.Label(bet_frame, text=_t("betting.labels.odds", default="Odds") + ":").pack(anchor=tk.W, pady=(10, 0))
        self.odds_display_var = tk.StringVar(value="-")
        ttk.Label(bet_frame, textvariable=self.odds_display_var, font=('Arial', 14, 'bold')).pack(anchor=tk.W)

        # Stake
        ttk.Label(bet_frame, text=_t("betting.labels.stake", default="Stake (GBP)") + ":").pack(anchor=tk.W, pady=(10, 0))
        self.stake_entry = ttk.Entry(bet_frame, width=15)
        self.stake_entry.insert(0, "10.00")
        self.stake_entry.pack(anchor=tk.W, pady=5)

        # Potential return
        ttk.Label(bet_frame, text=_t("betting.labels.potential_return", default="Potential Return") + ":").pack(anchor=tk.W, pady=(10, 0))
        self.return_var = tk.StringVar(value="GBP 0.00")
        ttk.Label(bet_frame, textvariable=self.return_var, font=('Arial', 12, 'bold'), foreground='green').pack(anchor=tk.W)

        # Update return when stake changes
        self.stake_entry.bind('<KeyRelease>', self.calculate_potential_return)
        self.selection_var.trace_add('write', lambda *args: self.calculate_potential_return(None))

        # Place bet button
        ttk.Button(
            bet_frame,
            text=_t("betting.btn.place_bet", default="Place Bet"),
            command=self.place_sports_bet
        ).pack(pady=20)

        # Load events
        self.load_sports_events()
        self.selected_event = None

    def load_sports_events(self):
        """Load sports events"""
        try:
            for item in self.events_tree.get_children():
                self.events_tree.delete(item)

            sport_filter = self.sport_filter.get()
            sport = None if sport_filter == _t("common.all", default="All") else sport_filter

            events = SportsBettingManager.get_upcoming_events(sport)
            self.events_data = events

            for event in events:
                self.events_tree.insert('', tk.END, values=(
                    event['event_id'],
                    f"{event['team_a']} vs {event['team_b']}",
                    event['event_date'],
                    f"{event['odds_a']:.2f}",
                    f"{event['odds_b']:.2f}",
                    f"{event['odds_draw']:.2f}" if event['odds_draw'] else '-'
                ))

        except Exception as e:
            print(f"Error loading events: {e}")

    def on_event_select(self, event):
        """Handle event selection"""
        selected = self.events_tree.selection()
        if selected:
            item = self.events_tree.item(selected[0])
            event_id = item['values'][0]
            self.selected_event = next((e for e in self.events_data if e['event_id'] == event_id), None)

            if self.selected_event:
                self.selected_event_var.set(f"{self.selected_event['team_a']} vs {self.selected_event['team_b']}")
                self.team_a_radio.config(text=f"{self.selected_event['team_a']} ({self.selected_event['odds_a']:.2f})")
                self.team_b_radio.config(text=f"{self.selected_event['team_b']} ({self.selected_event['odds_b']:.2f})")
                if self.selected_event['odds_draw']:
                    self.draw_radio.config(text=f"Draw ({self.selected_event['odds_draw']:.2f})")
                self.calculate_potential_return(None)

    def calculate_potential_return(self, event):
        """Calculate potential return"""
        if not self.selected_event:
            return

        try:
            stake = float(self.stake_entry.get())
            selection = self.selection_var.get()

            if selection == 'team_a':
                odds = self.selected_event['odds_a']
            elif selection == 'team_b':
                odds = self.selected_event['odds_b']
            else:
                odds = self.selected_event['odds_draw'] or 3.50

            potential = stake * odds
            self.odds_display_var.set(f"{odds:.2f}")
            self.return_var.set(f"GBP {potential:.2f}")

        except ValueError:
            self.return_var.set("GBP 0.00")

    # =========================================================================
    # FUNCTION 7: place_sports_bet - Place a bet on sports event
    # =========================================================================
    def place_sports_bet(self):
        """Place a sports bet"""
        if not self.selected_event:
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("betting.errors.select_event", default="Please select an event first")
            )
            return

        try:
            stake = float(self.stake_entry.get())

            if stake < MIN_BET or stake > MAX_BET:
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("betting.errors.invalid_stake", default="Stake must be between GBP {min} and GBP {max}").format(min=MIN_BET, max=MAX_BET)
                )
                return

            if self.account['balance'] < stake:
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("betting.errors.insufficient_balance", default="Insufficient balance. Please deposit more funds.")
                )
                return

            selection = self.selection_var.get()

            bet_id = SportsBettingManager.place_bet(
                user_id=self.user_id,
                event_id=self.selected_event['event_id'],
                selection=selection,
                stake=stake
            )

            if bet_id:
                self.update_balance_display()

                # Send receipt
                if self.account.get('email'):
                    self.send_bet_receipt(bet_id, 'sports', stake)

                messagebox.showinfo(
                    _t("common.success", default="Success"),
                    _t("betting.messages.bet_placed", default="Bet placed successfully! Bet ID: {bet_id}").format(bet_id=bet_id)
                )

                self.load_bet_history()
            else:
                messagebox.showerror(
                    _t("common.error", default="Error"),
                    _t("betting.errors.bet_failed", default="Failed to place bet")
                )

        except ValueError:
            messagebox.showwarning(_t("common.warning", default="Warning"), _t("betting.errors.invalid_stake_amount", default="Please enter a valid stake amount"))
        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    # =========================================================================
    # FUNCTION 8: view_bet_history - View user's betting history
    # =========================================================================
    def view_bet_history(self):
        """Show bet history in a dialog"""
        try:
            bets = SportsBettingManager.get_user_bets(self.user_id)

            dialog = tk.Toplevel(self.window)
            dialog.title(_t("betting.bet_history", default="Bet History"))
            dialog.geometry("700x500")
            dialog.transient(self.window)

            text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD)
            text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            if bets:
                history = "YOUR BET HISTORY\n" + "="*60 + "\n\n"
                for bet in bets:
                    history += f"Bet ID: {bet['bet_id']}\n"
                    history += f"Event: {bet.get('event_name', 'Unknown')}\n"
                    history += f"Selection: {bet['selection']} @ {bet['odds']:.2f}\n"
                    history += f"Stake: GBP {bet['stake']:.2f}\n"
                    history += f"Potential Return: GBP {bet['potential_return']:.2f}\n"
                    history += f"Status: {bet['status'].upper()}\n"
                    if bet['status'] in ['won', 'cashed_out']:
                        history += f"Return: GBP {bet['actual_return']:.2f}\n"
                    history += f"Placed: {bet['placed_at']}\n"
                    history += "-"*40 + "\n\n"
            else:
                history = "No bets placed yet."

            text.insert('1.0', history)
            text.config(state='disabled')

            ttk.Button(dialog, text=_t("common.close", default="Close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    # =========================================================================
    # FUNCTION 9: cash_out_bet - Cash out a pending bet early
    # =========================================================================
    def cash_out_bet(self):
        """Cash out a pending bet"""
        # Get pending bets
        bets = SportsBettingManager.get_user_bets(self.user_id, status='pending')

        if not bets:
            messagebox.showinfo(
                _t("common.info", default="Info"),
                _t("betting.messages.no_pending_bets", default="You have no pending bets to cash out")
            )
            return

        # Create selection dialog
        dialog = tk.Toplevel(self.window)
        dialog.title(_t("betting.btn.cash_out", default="Cash Out"))
        dialog.geometry("500x400")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(dialog, text=_t("betting.select_bet_to_cash_out", default="Select a bet to cash out:"), font=('Arial', 11, 'bold')).pack(pady=10)

        # Listbox
        listbox = tk.Listbox(dialog, height=10, width=60)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        bet_map = {}
        for bet in bets:
            cash_out_value = round(bet['stake'] + (bet['potential_return'] - bet['stake']) * 0.5, 2)
            display = f"Bet #{bet['bet_id']} - {bet.get('event_name', 'Event')} - Cash Out: GBP {cash_out_value:.2f}"
            listbox.insert(tk.END, display)
            bet_map[listbox.size() - 1] = bet

        def confirm_cash_out():
            selection = listbox.curselection()
            if not selection:
                messagebox.showwarning(_t("common.warning", default="Warning"), _t("betting.errors.select_bet", default="Please select a bet"))
                return

            bet = bet_map[selection[0]]
            cash_out_value = SportsBettingManager.cash_out_bet(bet['bet_id'], self.user_id)

            if cash_out_value:
                self.update_balance_display()
                messagebox.showinfo(
                    _t("common.success", default="Success"),
                    _t("betting.messages.cashed_out", default="Bet cashed out for GBP {amount:.2f}").format(amount=cash_out_value)
                )
                dialog.destroy()
                self.load_bet_history()
            else:
                messagebox.showerror(_t("common.error", default="Error"), "Cash out failed")

        ttk.Button(dialog, text=_t("betting.btn.cash_out", default="Cash Out"), command=confirm_cash_out).pack(pady=10)

    # =========================================================================
    # FUNCTION 10: view_odds - View current odds for events
    # =========================================================================
    def view_odds(self):
        """Display current odds in a dialog"""
        try:
            events = SportsBettingManager.get_upcoming_events()

            dialog = tk.Toplevel(self.window)
            dialog.title(_t("betting.current_odds", default="Current Odds"))
            dialog.geometry("600x500")
            dialog.transient(self.window)

            text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, font=('Courier', 10))
            text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            odds_text = "CURRENT BETTING ODDS\n" + "="*60 + "\n\n"

            if events:
                for event in events:
                    odds_text += f"Event: {event['team_a']} vs {event['team_b']}\n"
                    odds_text += f"Date: {event['event_date']} {event.get('event_time', '')}\n"
                    odds_text += f"Sport: {event.get('sport_type', 'Unknown')}\n"
                    odds_text += "-"*40 + "\n"
                    odds_text += f"  {event['team_a']:20} : {event['odds_a']:.2f}\n"
                    if event.get('odds_draw'):
                        odds_text += f"  {'Draw':20} : {event['odds_draw']:.2f}\n"
                    odds_text += f"  {event['team_b']:20} : {event['odds_b']:.2f}\n"
                    odds_text += "\n"
            else:
                odds_text += "No upcoming events available."

            text.insert('1.0', odds_text)
            text.config(state='disabled')

            ttk.Button(dialog, text=_t("common.close", default="Close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    # =========================================================================
    # FUNCTION 11: create_predictions_tab - Tab for prediction markets
    # =========================================================================
    def create_predictions_tab(self):
        """Create prediction markets tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("betting.tabs.predictions", default="Prediction Markets"))

        # Split view
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left: Markets list
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(
            left_frame,
            text=_t("betting.open_markets", default="Open Prediction Markets"),
            font=('Arial', 12, 'bold')
        ).pack(pady=5)

        # Category filter
        filter_frame = ttk.Frame(left_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filter_frame, text=_t("betting.labels.category", default="Category") + ":").pack(side=tk.LEFT)
        self.pred_category_filter = ttk.Combobox(filter_frame, values=[
            _t("common.all", default="All")] + PREDICTION_CATEGORIES, state='readonly', width=15)
        self.pred_category_filter.set(_t("common.all", default="All"))
        self.pred_category_filter.pack(side=tk.LEFT, padx=5)
        self.pred_category_filter.bind('<<ComboboxSelected>>', lambda e: self.load_predictions())

        # Markets treeview
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ('id', 'title', 'prob_a', 'prob_b', 'pool', 'closes')
        self.markets_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        self.markets_tree.heading('id', text='ID')
        self.markets_tree.heading('title', text=_t("betting.labels.market", default="Market"))
        self.markets_tree.heading('prob_a', text=_t("betting.labels.yes", default="Yes %"))
        self.markets_tree.heading('prob_b', text=_t("betting.labels.no", default="No %"))
        self.markets_tree.heading('pool', text=_t("betting.labels.pool", default="Pool"))
        self.markets_tree.heading('closes', text=_t("betting.labels.closes", default="Closes"))

        self.markets_tree.column('id', width=40)
        self.markets_tree.column('title', width=200)
        self.markets_tree.column('prob_a', width=60)
        self.markets_tree.column('prob_b', width=60)
        self.markets_tree.column('pool', width=80)
        self.markets_tree.column('closes', width=90)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.markets_tree.yview)
        self.markets_tree.configure(yscrollcommand=scrollbar.set)

        self.markets_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.markets_tree.bind('<<TreeviewSelect>>', self.on_market_select)

        # Right: Prediction bet form
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        pred_frame = ttk.LabelFrame(right_frame, text=_t("betting.place_prediction", default="Place Prediction"), padding="10")
        pred_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Market display
        ttk.Label(pred_frame, text=_t("betting.labels.selected_market", default="Selected Market") + ":").pack(anchor=tk.W)
        self.selected_market_var = tk.StringVar(value=_t("betting.select_market", default="Select a market"))
        ttk.Label(pred_frame, textvariable=self.selected_market_var, font=('Arial', 10, 'bold'), wraplength=300).pack(anchor=tk.W, pady=5)

        # Outcomes display
        self.outcome_a_var = tk.StringVar(value="Outcome A")
        self.outcome_b_var = tk.StringVar(value="Outcome B")

        ttk.Label(pred_frame, text=_t("betting.labels.your_prediction", default="Your Prediction") + ":").pack(anchor=tk.W, pady=(10, 0))
        self.pred_selection_var = tk.StringVar(value='outcome_a')

        self.outcome_a_radio = ttk.Radiobutton(pred_frame, textvariable=self.outcome_a_var, variable=self.pred_selection_var, value='outcome_a')
        self.outcome_a_radio.pack(anchor=tk.W, pady=2)
        self.outcome_b_radio = ttk.Radiobutton(pred_frame, textvariable=self.outcome_b_var, variable=self.pred_selection_var, value='outcome_b')
        self.outcome_b_radio.pack(anchor=tk.W, pady=2)

        # Stake
        ttk.Label(pred_frame, text=_t("betting.labels.stake", default="Stake (GBP)") + ":").pack(anchor=tk.W, pady=(10, 0))
        self.pred_stake_entry = ttk.Entry(pred_frame, width=15)
        self.pred_stake_entry.insert(0, "10.00")
        self.pred_stake_entry.pack(anchor=tk.W, pady=5)

        # Place prediction button
        ttk.Button(
            pred_frame,
            text=_t("betting.btn.place_prediction", default="Place Prediction"),
            command=self.place_prediction_bet
        ).pack(pady=20)

        # Admin: Create market button
        if self.user_role in ['admin', 'staff']:
            ttk.Separator(pred_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
            ttk.Button(
                pred_frame,
                text=_t("betting.btn.create_market", default="Create New Market"),
                command=self.create_prediction
            ).pack(pady=5)

        # Load predictions
        self.load_predictions()
        self.selected_market = None

    def load_predictions(self):
        """Load prediction markets"""
        try:
            for item in self.markets_tree.get_children():
                self.markets_tree.delete(item)

            category = self.pred_category_filter.get()
            cat = None if category == _t("common.all", default="All") else category

            markets = PredictionMarketManager.get_open_markets(cat)
            self.markets_data = markets

            for market in markets:
                self.markets_tree.insert('', tk.END, values=(
                    market['market_id'],
                    market['title'][:30] + '...' if len(market['title']) > 30 else market['title'],
                    f"{market['probability_a']:.0f}%",
                    f"{market['probability_b']:.0f}%",
                    f"GBP {market['total_pool']:.0f}",
                    market['resolution_date']
                ))

        except Exception as e:
            print(f"Error loading predictions: {e}")

    def on_market_select(self, event):
        """Handle market selection"""
        selected = self.markets_tree.selection()
        if selected:
            item = self.markets_tree.item(selected[0])
            market_id = item['values'][0]
            self.selected_market = next((m for m in self.markets_data if m['market_id'] == market_id), None)

            if self.selected_market:
                self.selected_market_var.set(self.selected_market['title'])
                self.outcome_a_var.set(f"{self.selected_market['outcome_a']} ({self.selected_market['probability_a']:.0f}%)")
                self.outcome_b_var.set(f"{self.selected_market['outcome_b']} ({self.selected_market['probability_b']:.0f}%)")

    # =========================================================================
    # FUNCTION 12: create_prediction - Create a new prediction market (admin)
    # =========================================================================
    def create_prediction(self):
        """Create a new prediction market"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_t("betting.btn.create_market", default="Create Prediction Market"))
        dialog.geometry("450x400")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(dialog, text=_t("betting.labels.title", default="Title") + ":").pack(anchor=tk.W, padx=20, pady=(10, 0))
        title_entry = ttk.Entry(dialog, width=45)
        title_entry.pack(padx=20, pady=5)

        ttk.Label(dialog, text=_t("betting.labels.description", default="Description") + ":").pack(anchor=tk.W, padx=20)
        desc_text = scrolledtext.ScrolledText(dialog, width=40, height=3)
        desc_text.pack(padx=20, pady=5)

        ttk.Label(dialog, text=_t("betting.labels.category", default="Category") + ":").pack(anchor=tk.W, padx=20)
        category_combo = ttk.Combobox(dialog, values=PREDICTION_CATEGORIES, state='readonly', width=42)
        category_combo.set('sports')
        category_combo.pack(padx=20, pady=5)

        ttk.Label(dialog, text=_t("betting.labels.outcome_a", default="Outcome A (Yes)") + ":").pack(anchor=tk.W, padx=20)
        outcome_a_entry = ttk.Entry(dialog, width=45)
        outcome_a_entry.pack(padx=20, pady=5)

        ttk.Label(dialog, text=_t("betting.labels.outcome_b", default="Outcome B (No)") + ":").pack(anchor=tk.W, padx=20)
        outcome_b_entry = ttk.Entry(dialog, width=45)
        outcome_b_entry.pack(padx=20, pady=5)

        ttk.Label(dialog, text=_t("betting.labels.resolution_date", default="Resolution Date (YYYY-MM-DD)") + ":").pack(anchor=tk.W, padx=20)
        date_entry = ttk.Entry(dialog, width=45)
        date_entry.insert(0, (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))
        date_entry.pack(padx=20, pady=5)

        def create():
            title = title_entry.get().strip()
            description = desc_text.get('1.0', tk.END).strip()
            category = category_combo.get()
            outcome_a = outcome_a_entry.get().strip()
            outcome_b = outcome_b_entry.get().strip()
            resolution_date = date_entry.get().strip()

            if not all([title, outcome_a, outcome_b, resolution_date]):
                messagebox.showwarning(_t("common.warning", default="Warning"), _t("betting.errors.all_fields_required", default="Please fill all required fields"))
                return

            market_id = PredictionMarketManager.create_market(
                title=title,
                description=description,
                category=category,
                outcome_a=outcome_a,
                outcome_b=outcome_b,
                resolution_date=resolution_date,
                created_by=self.current_user.get('username')
            )

            if market_id:
                messagebox.showinfo(
                    _t("common.success", default="Success"),
                    _t("betting.messages.market_created", default="Prediction market created successfully!")
                )
                dialog.destroy()
                self.load_predictions()
            else:
                messagebox.showerror(_t("common.error", default="Error"), _t("betting.errors.failed_create_market", default="Failed to create market"))

        ttk.Button(dialog, text=_t("betting.btn.create_market", default="Create Market"), command=create).pack(pady=15)

    # =========================================================================
    # FUNCTION 13: place_prediction_bet - Place bet on prediction market
    # =========================================================================
    def place_prediction_bet(self):
        """Place a bet on a prediction market"""
        if not self.selected_market:
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("betting.errors.select_market", default="Please select a market first")
            )
            return

        try:
            stake = float(self.pred_stake_entry.get())

            if stake < MIN_BET or stake > MAX_BET:
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("betting.errors.invalid_stake", default="Stake must be between GBP {min} and GBP {max}").format(min=MIN_BET, max=MAX_BET)
                )
                return

            if self.account['balance'] < stake:
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("betting.errors.insufficient_balance", default="Insufficient balance")
                )
                return

            selection = self.pred_selection_var.get()

            bet_id = PredictionMarketManager.place_prediction_bet(
                user_id=self.user_id,
                market_id=self.selected_market['market_id'],
                selection=selection,
                stake=stake
            )

            if bet_id:
                self.update_balance_display()

                messagebox.showinfo(
                    _t("common.success", default="Success"),
                    _t("betting.messages.prediction_placed", default="Prediction placed successfully!")
                )

                self.load_predictions()
            else:
                messagebox.showerror(_t("common.error", default="Error"), _t("betting.errors.failed_place_prediction", default="Failed to place prediction"))

        except ValueError:
            messagebox.showwarning(_t("common.warning", default="Warning"), _t("betting.errors.invalid_stake_simple", default="Please enter a valid stake"))
        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    # =========================================================================
    # FUNCTION 14: resolve_prediction - Resolve a prediction market (admin)
    # =========================================================================
    def resolve_prediction(self):
        """Resolve a prediction market"""
        markets = PredictionMarketManager.get_open_markets()

        if not markets:
            messagebox.showinfo(_t("common.info", default="Info"), _t("betting.errors.no_open_markets", default="No open markets to resolve"))
            return

        dialog = tk.Toplevel(self.window)
        dialog.title(_t("betting.resolve_market", default="Resolve Market"))
        dialog.geometry("500x350")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(dialog, text=_t("betting.select_market_to_resolve", default="Select market to resolve:")).pack(pady=10)

        listbox = tk.Listbox(dialog, height=8, width=60)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        market_map = {}
        for market in markets:
            display = f"{market['market_id']}: {market['title'][:40]}"
            listbox.insert(tk.END, display)
            market_map[listbox.size() - 1] = market

        ttk.Label(dialog, text=_t("betting.labels.result", default="Result") + ":").pack(pady=(10, 0))
        result_var = tk.StringVar(value='outcome_a')

        def update_options(*args):
            selection = listbox.curselection()
            if selection:
                market = market_map[selection[0]]
                outcome_a_radio.config(text=market['outcome_a'])
                outcome_b_radio.config(text=market['outcome_b'])

        outcome_a_radio = ttk.Radiobutton(dialog, text=_t("betting.selections.outcome_a", default="Outcome A"), variable=result_var, value='outcome_a')
        outcome_a_radio.pack()
        outcome_b_radio = ttk.Radiobutton(dialog, text=_t("betting.selections.outcome_b", default="Outcome B"), variable=result_var, value='outcome_b')
        outcome_b_radio.pack()

        listbox.bind('<<ListboxSelect>>', update_options)

        def resolve():
            selection = listbox.curselection()
            if not selection:
                messagebox.showwarning(_t("common.warning", default="Warning"), _t("betting.errors.select_market_simple", default="Please select a market"))
                return

            market = market_map[selection[0]]
            result = result_var.get()

            if PredictionMarketManager.resolve_market(market['market_id'], result, self.current_user.get('username')):
                messagebox.showinfo(_t("common.success", default="Success"), _t("betting.messages.market_resolved", default="Market resolved successfully"))
                dialog.destroy()
                self.load_predictions()
            else:
                messagebox.showerror(_t("common.error", default="Error"), _t("betting.errors.failed_resolve_market", default="Failed to resolve market"))

        ttk.Button(dialog, text=_t("betting.btn.resolve", default="Resolve"), command=resolve).pack(pady=15)

    # =========================================================================
    # FUNCTION 15: create_casino_tab - Tab for casino games
    # =========================================================================
    def create_casino_tab(self):
        """Create casino games tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("betting.tabs.casino", default="Casino"))

        # Games selection
        games_frame = ttk.LabelFrame(tab, text=_t("betting.select_game", default="Select Game"), padding="10")
        games_frame.pack(fill=tk.X, padx=10, pady=10)

        btn_frame = ttk.Frame(games_frame)
        btn_frame.pack()

        ttk.Button(btn_frame, text=_t("betting.casino.slots", default="Slots"), command=self.play_slots, width=15).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t("betting.casino.blackjack", default="Blackjack"), command=self.play_blackjack, width=15).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t("betting.casino.roulette", default="Roulette"), command=self.play_roulette, width=15).pack(side=tk.LEFT, padx=10)

        # Game area
        self.game_frame = ttk.LabelFrame(tab, text=_t("betting.game_area", default="Game Area"), padding="10")
        self.game_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.game_display = scrolledtext.ScrolledText(self.game_frame, wrap=tk.WORD, font=('Courier', 12), height=15)
        self.game_display.pack(fill=tk.BOTH, expand=True)
        self.game_display.insert('1.0', _t("betting.select_game_to_play", default="Select a game above to start playing!"))
        self.game_display.config(state='disabled')

        # History button
        btn_frame2 = ttk.Frame(tab)
        btn_frame2.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame2, text=_t("betting.btn.view_history", default="View Game History"), command=self.view_game_history).pack(side=tk.RIGHT)

    # =========================================================================
    # FUNCTION 16: play_slots - Play slot machine game
    # =========================================================================
    def play_slots(self):
        """Play slots game"""
        bet = simpledialog.askfloat(
            _t("betting.slots", default="Slots"),
            _t("betting.prompts.enter_bet", default="Enter bet amount (GBP {min}-{max}):").format(min=MIN_BET, max=MAX_BET),
            initialvalue=5.0,
            minvalue=MIN_BET,
            maxvalue=MAX_BET
        )

        if bet is None:
            return

        if self.account['balance'] < bet:
            messagebox.showwarning(_t("common.warning", default="Warning"), _t("betting.errors.insufficient_balance_simple", default="Insufficient balance"))
            return

        result = CasinoManager.play_slots(self.user_id, bet)

        if result['success']:
            self.update_balance_display()

            reels = result['reels']
            win = result['win_amount']

            display = f"""
{'='*50}
              SLOTS
{'='*50}

    [ {reels[0]:^7} ] [ {reels[1]:^7} ] [ {reels[2]:^7} ]

{'='*50}

Bet Amount:     GBP {bet:.2f}
"""
            if result['is_jackpot']:
                display += f"""
    JACKPOT!!!

Win Amount:     GBP {win:.2f}
"""
            elif win > 0:
                display += f"""
    WINNER!

Win Amount:     GBP {win:.2f}
"""
            else:
                display += """
    No win this time. Try again!
"""

            display += f"""
{'='*50}
Balance:        GBP {self.account['balance']:.2f}
{'='*50}
"""

            self.game_display.config(state='normal')
            self.game_display.delete('1.0', tk.END)
            self.game_display.insert('1.0', display)
            self.game_display.config(state='disabled')

        else:
            messagebox.showerror(_t("common.error", default="Error"), result.get('error', 'Game failed'))

    # =========================================================================
    # FUNCTION 17: play_blackjack - Play blackjack game
    # =========================================================================
    def play_blackjack(self):
        """Play blackjack game"""
        bet = simpledialog.askfloat(
            _t("betting.blackjack", default="Blackjack"),
            _t("betting.prompts.enter_bet", default="Enter bet amount (GBP {min}-{max}):").format(min=MIN_BET, max=MAX_BET),
            initialvalue=10.0,
            minvalue=MIN_BET,
            maxvalue=MAX_BET
        )

        if bet is None:
            return

        if self.account['balance'] < bet:
            messagebox.showwarning(_t("common.warning", default="Warning"), _t("betting.errors.insufficient_balance_simple", default="Insufficient balance"))
            return

        result = CasinoManager.play_blackjack(self.user_id, bet)

        if result['success']:
            self.update_balance_display()

            display = f"""
{'='*50}
              BLACKJACK
{'='*50}

Your Hand:    {' '.join(result['player_hand'])}
              Total: {result['player_total']}

Dealer Hand:  {' '.join(result['dealer_hand'])}
              Total: {result['dealer_total']}

{'='*50}

Bet Amount:   GBP {bet:.2f}
Result:       {result['result'].upper()}
"""
            if result['result'] == 'blackjack':
                display += f"""
    BLACKJACK! 3:2 Payout!

Win Amount:   GBP {result['win_amount']:.2f}
"""
            elif result['result'] == 'win':
                display += f"""
    YOU WIN!

Win Amount:   GBP {result['win_amount']:.2f}
"""
            elif result['result'] == 'push':
                display += f"""
    PUSH - Stake Returned

Returned:     GBP {result['win_amount']:.2f}
"""
            elif result['result'] == 'bust':
                display += """
    BUST! You went over 21.
"""
            else:
                display += """
    Dealer wins.
"""

            display += f"""
{'='*50}
Balance:      GBP {self.account['balance']:.2f}
{'='*50}
"""

            self.game_display.config(state='normal')
            self.game_display.delete('1.0', tk.END)
            self.game_display.insert('1.0', display)
            self.game_display.config(state='disabled')

        else:
            messagebox.showerror(_t("common.error", default="Error"), result.get('error', 'Game failed'))

    # =========================================================================
    # FUNCTION 18: play_roulette - Play roulette game
    # =========================================================================
    def play_roulette(self):
        """Play roulette game"""
        # Bet type dialog
        dialog = tk.Toplevel(self.window)
        dialog.title(_t("betting.roulette", default="Roulette"))
        dialog.geometry("350x350")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(dialog, text=_t("betting.roulette", default="Roulette"), font=('Arial', 14, 'bold')).pack(pady=10)

        # Bet type
        ttk.Label(dialog, text=_t("betting.labels.bet_type", default="Bet Type") + ":").pack(pady=5)
        bet_type_var = tk.StringVar(value='color')
        ttk.Radiobutton(dialog, text=_t("betting.casino.bet_types.color", default="Color (Red/Black)"), variable=bet_type_var, value='color').pack()
        ttk.Radiobutton(dialog, text=_t("betting.casino.bet_types.odd_even", default="Odd/Even"), variable=bet_type_var, value='odd_even').pack()
        ttk.Radiobutton(dialog, text=_t("betting.casino.bet_types.high_low", default="High/Low (1-18/19-36)"), variable=bet_type_var, value='high_low').pack()
        ttk.Radiobutton(dialog, text=_t("betting.casino.bet_types.number", default="Straight Number (35:1)"), variable=bet_type_var, value='number').pack()

        # Bet value
        ttk.Label(dialog, text=_t("betting.labels.selection", default="Selection") + ":").pack(pady=(10, 5))
        bet_value_entry = ttk.Entry(dialog, width=20)
        bet_value_entry.insert(0, "red")
        bet_value_entry.pack()
        ttk.Label(dialog, text=_t("betting.casino.bet_help", default="(red/black, odd/even, high/low, or 0-36)"), font=('Arial', 8)).pack()

        # Stake
        ttk.Label(dialog, text=_t("betting.labels.stake", default="Stake (GBP)") + ":").pack(pady=(10, 5))
        stake_entry = ttk.Entry(dialog, width=20)
        stake_entry.insert(0, "10.00")
        stake_entry.pack()

        def spin():
            try:
                bet_type = bet_type_var.get()
                bet_value = bet_value_entry.get().strip().lower()
                stake = float(stake_entry.get())

                if self.account['balance'] < stake:
                    messagebox.showwarning(_t("common.warning", default="Warning"), "Insufficient balance")
                    return

                result = CasinoManager.play_roulette(self.user_id, stake, bet_type, bet_value)

                if result['success']:
                    self.update_balance_display()
                    dialog.destroy()

                    color_symbol = ""
                    if result['result_color'] == 'red':
                        color_symbol = "RED"
                    elif result['result_color'] == 'black':
                        color_symbol = "BLACK"
                    else:
                        color_symbol = "GREEN"

                    display = f"""
{'='*50}
              ROULETTE
{'='*50}

         The wheel spins...

              [ {result['result_number']} ]
              {color_symbol}

{'='*50}

Your Bet:     {bet_type} = {bet_value}
Stake:        GBP {stake:.2f}

"""
                    if result['win']:
                        display += f"""Result:       WIN!
Win Amount:   GBP {result['win_amount']:.2f}
"""
                    else:
                        display += """Result:       No win
"""

                    display += f"""
{'='*50}
Balance:      GBP {self.account['balance']:.2f}
{'='*50}
"""

                    self.game_display.config(state='normal')
                    self.game_display.delete('1.0', tk.END)
                    self.game_display.insert('1.0', display)
                    self.game_display.config(state='disabled')

                else:
                    messagebox.showerror(_t("common.error", default="Error"), result.get('error', 'Game failed'))

            except ValueError:
                messagebox.showwarning(_t("common.warning", default="Warning"), _t("betting.errors.invalid_values", default="Please enter valid values"))

        ttk.Button(dialog, text=_t("betting.btn.spin", default="Spin!"), command=spin).pack(pady=20)

    # =========================================================================
    # FUNCTION 19: view_game_history - View casino game history
    # =========================================================================
    def view_game_history(self):
        """View casino game history"""
        try:
            games = CasinoManager.get_game_history(self.user_id)

            dialog = tk.Toplevel(self.window)
            dialog.title(_t("betting.game_history", default="Game History"))
            dialog.geometry("600x500")
            dialog.transient(self.window)

            text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, font=('Courier', 10))
            text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            if games:
                history = "CASINO GAME HISTORY\n" + "="*60 + "\n\n"
                for game in games:
                    history += f"Game: {game['game_type'].upper()}\n"
                    history += f"Bet: GBP {game['bet_amount']:.2f}\n"
                    history += f"Result: {game['result'].upper()}\n"
                    history += f"Win: GBP {game['win_amount']:.2f}\n"
                    history += f"Played: {game['played_at']}\n"
                    history += "-"*40 + "\n\n"
            else:
                history = "No games played yet."

            text.insert('1.0', history)
            text.config(state='disabled')

            ttk.Button(dialog, text=_t("common.close", default="Close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    # =========================================================================
    # FUNCTION 20: create_account_tab - Tab for account management
    # =========================================================================
    def create_account_tab(self):
        """Create account management tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("betting.tabs.account", default="My Account"))

        # Account info
        info_frame = ttk.LabelFrame(tab, text=_t("betting.account_info", default="Account Information"), padding="15")
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        info_grid = ttk.Frame(info_frame)
        info_grid.pack()

        ttk.Label(info_grid, text=_t("betting.labels.username", default="Username") + ":").grid(row=0, column=0, sticky=tk.W, pady=3)
        ttk.Label(info_grid, text=self.current_user.get('username', 'N/A'), font=('Arial', 10, 'bold')).grid(row=0, column=1, sticky=tk.W, padx=10)

        ttk.Label(info_grid, text=_t("betting.labels.balance", default="Balance") + ":").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.account_balance_var = tk.StringVar(value=f"GBP {self.account['balance']:.2f}" if self.account else "GBP 0.00")
        ttk.Label(info_grid, textvariable=self.account_balance_var, font=('Arial', 12, 'bold'), foreground='green').grid(row=1, column=1, sticky=tk.W, padx=10)

        ttk.Label(info_grid, text=_t("betting.labels.total_deposited", default="Total Deposited") + ":").grid(row=2, column=0, sticky=tk.W, pady=3)
        ttk.Label(info_grid, text=f"GBP {self.account.get('total_deposited', 0):.2f}" if self.account else "GBP 0.00").grid(row=2, column=1, sticky=tk.W, padx=10)

        ttk.Label(info_grid, text=_t("betting.labels.total_wagered", default="Total Wagered") + ":").grid(row=3, column=0, sticky=tk.W, pady=3)
        ttk.Label(info_grid, text=f"GBP {self.account.get('total_wagered', 0):.2f}" if self.account else "GBP 0.00").grid(row=3, column=1, sticky=tk.W, padx=10)

        ttk.Label(info_grid, text=_t("betting.labels.total_won", default="Total Won") + ":").grid(row=4, column=0, sticky=tk.W, pady=3)
        ttk.Label(info_grid, text=f"GBP {self.account.get('total_won', 0):.2f}" if self.account else "GBP 0.00").grid(row=4, column=1, sticky=tk.W, padx=10)

        # Actions
        action_frame = ttk.LabelFrame(tab, text=_t("betting.actions", default="Actions"), padding="10")
        action_frame.pack(fill=tk.X, padx=10, pady=10)

        btn_grid = ttk.Frame(action_frame)
        btn_grid.pack()

        ttk.Button(btn_grid, text=_t("betting.btn.deposit", default="Deposit Funds"), command=self.deposit_funds, width=20).grid(row=0, column=0, padx=10, pady=5)
        ttk.Button(btn_grid, text=_t("betting.btn.withdraw", default="Withdraw Funds"), command=self.withdraw_funds, width=20).grid(row=0, column=1, padx=10, pady=5)
        ttk.Button(btn_grid, text=_t("betting.btn.view_history", default="View Bet History"), command=self.view_bet_history, width=20).grid(row=1, column=0, padx=10, pady=5)
        ttk.Button(btn_grid, text=_t("betting.btn.cash_out", default="Cash Out Bet"), command=self.cash_out_bet, width=20).grid(row=1, column=1, padx=10, pady=5)
        ttk.Button(btn_grid, text=_t("betting.btn.view_transactions", default="View Transactions"), command=self.view_transactions, width=20).grid(row=2, column=0, padx=10, pady=5)
        ttk.Button(btn_grid, text=_t("betting.btn.view_odds", default="View Current Odds"), command=self.view_odds, width=20).grid(row=2, column=1, padx=10, pady=5)

        # Transaction history
        history_frame = ttk.LabelFrame(tab, text=_t("betting.recent_transactions", default="Recent Transactions"), padding="10")
        history_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ('date', 'type', 'amount', 'balance')
        self.trans_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=8)

        self.trans_tree.heading('date', text=_t("betting.labels.date", default="Date"))
        self.trans_tree.heading('type', text=_t("betting.labels.type", default="Type"))
        self.trans_tree.heading('amount', text=_t("betting.labels.amount", default="Amount"))
        self.trans_tree.heading('balance', text=_t("betting.labels.balance", default="Balance"))

        self.trans_tree.column('date', width=150)
        self.trans_tree.column('type', width=100)
        self.trans_tree.column('amount', width=100)
        self.trans_tree.column('balance', width=100)

        self.trans_tree.pack(fill=tk.BOTH, expand=True)

        self.load_transactions()

    def load_transactions(self):
        """Load recent transactions"""
        try:
            for item in self.trans_tree.get_children():
                self.trans_tree.delete(item)

            transactions = AccountManager.get_transaction_history(self.user_id, limit=20)

            for trans in transactions:
                self.trans_tree.insert('', tk.END, values=(
                    trans['created_at'][:19],
                    trans['transaction_type'].title(),
                    f"GBP {trans['amount']:.2f}",
                    f"GBP {trans['balance_after']:.2f}"
                ))

        except Exception as e:
            print(f"Error loading transactions: {e}")

    def view_transactions(self):
        """View full transaction history"""
        try:
            transactions = AccountManager.get_transaction_history(self.user_id, limit=100)

            dialog = tk.Toplevel(self.window)
            dialog.title(_t("betting.transaction_history", default="Transaction History"))
            dialog.geometry("600x500")
            dialog.transient(self.window)

            text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, font=('Courier', 10))
            text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            if transactions:
                history = "TRANSACTION HISTORY\n" + "="*60 + "\n\n"
                for trans in transactions:
                    history += f"Date: {trans['created_at']}\n"
                    history += f"Type: {trans['transaction_type'].upper()}\n"
                    history += f"Amount: GBP {trans['amount']:.2f}\n"
                    history += f"Balance: GBP {trans['balance_after']:.2f}\n"
                    history += f"Reference: {trans.get('reference', 'N/A')}\n"
                    history += "-"*40 + "\n\n"
            else:
                history = "No transactions yet."

            text.insert('1.0', history)
            text.config(state='disabled')

            ttk.Button(dialog, text=_t("common.close", default="Close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    # =========================================================================
    # FUNCTION 21: deposit_funds - Deposit funds to betting account
    # =========================================================================
    def deposit_funds(self):
        """Deposit funds to account"""
        # Get student account balance - try student_id, then username, then user_id
        student_id = self.current_user.get('student_id') or self.current_user.get('username') or self.user_id
        student_balance = get_student_finance_account_balance(student_id)

        dialog = tk.Toplevel(self.window)
        dialog.title(_t("betting.btn.deposit", default="Deposit Funds"))
        dialog.geometry("400x350")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(dialog, text=_t("betting.deposit_funds", default="Deposit Funds"), font=('Arial', 14, 'bold')).pack(pady=10)
        ttk.Label(dialog, text=f"User: {self.user_name}", font=('Arial', 10)).pack(pady=2)

        ttk.Label(dialog, text=_t("betting.labels.amount", default="Amount (GBP)") + f" ({MIN_DEPOSIT}-{MAX_DEPOSIT}):").pack(pady=5)
        amount_entry = ttk.Entry(dialog, width=20)
        amount_entry.insert(0, "50.00")
        amount_entry.pack(pady=5)

        ttk.Label(dialog, text=_t("betting.labels.payment_method", default="Payment Method") + ":", font=('Arial', 10, 'bold')).pack(pady=(10, 5))

        # Payment method radio buttons
        payment_method_var = tk.StringVar(value="Cash")
        methods_frame = ttk.Frame(dialog)
        methods_frame.pack(pady=5)

        ttk.Radiobutton(methods_frame, text=_t("betting.payment_methods.cash", default="Cash"), variable=payment_method_var, value="Cash").pack(anchor=tk.W)
        ttk.Radiobutton(methods_frame, text=_t("betting.payment_methods.card", default="Card"), variable=payment_method_var, value="Card").pack(anchor=tk.W)

        # Student Account option with balance display
        student_frame = ttk.Frame(methods_frame)
        student_frame.pack(anchor=tk.W)
        ttk.Radiobutton(student_frame, text=_t("betting.payment_methods.student_account", default="Student Account"), variable=payment_method_var, value="Student Account").pack(side=tk.LEFT)
        balance_text = f" (Balance: £{student_balance:.2f})" if student_balance else " (No account)"
        ttk.Label(student_frame, text=balance_text, font=('Arial', 9)).pack(side=tk.LEFT)

        def confirm_deposit():
            try:
                amount = float(amount_entry.get())

                if amount < MIN_DEPOSIT or amount > MAX_DEPOSIT:
                    messagebox.showwarning(
                        _t("common.warning", default="Warning"),
                        f"Amount must be between GBP {MIN_DEPOSIT} and GBP {MAX_DEPOSIT}"
                    )
                    return

                method = payment_method_var.get()

                # Handle Student Account payment
                if method == "Student Account":
                    if student_balance < amount:
                        messagebox.showerror(
                            _t("common.error", default="Error"),
                            f"Insufficient balance. Current balance: £{student_balance:.2f}"
                        )
                        return
                    # Process student account payment
                    payment_result = process_student_finance_account_payment(
                        student_id=student_id,
                        amount=amount,
                        description="Betting shop deposit",
                        transaction_source="BettingShop",
                        transaction_ref=f"deposit_{self.user_id}",
                        processed_by=self.current_user.get('username', 'System')
                    )
                    if not payment_result.get('success'):
                        messagebox.showerror(_t("common.error", default="Error"), payment_result.get('message', "Failed to process student account payment"))
                        return

                transaction_id = AccountManager.deposit(
                    self.user_id, amount, method, self.current_user.get('username')
                )

                if transaction_id:
                    # Record revenue in central finance system
                    record_payment_to_finance(
                        student_id=student_id,
                        amount=amount,
                        payment_method=method,
                        transaction_source='BettingShop',
                        transaction_ref=f"DEP-{transaction_id}",
                        notes=f"Betting deposit via {method}",
                        created_by=self.current_user.get('username')
                    )
                    logger.info(f"Revenue recorded: £{amount:.2f} for betting deposit")

                    # Send receipt
                    self.send_deposit_receipt(amount, method, transaction_id)

                    self.update_balance_display()
                    self.load_transactions()

                    messagebox.showinfo(
                        _t("common.success", default="Success"),
                        _t("betting.messages.deposit_success", default="GBP {amount:.2f} deposited successfully!").format(amount=amount)
                    )
                    dialog.destroy()
                else:
                    messagebox.showerror(_t("common.error", default="Error"), "Deposit failed")

            except ValueError:
                messagebox.showwarning(_t("common.warning", default="Warning"), "Please enter a valid amount")

        ttk.Button(dialog, text=_t("betting.btn.deposit", default="Deposit"), command=confirm_deposit).pack(pady=20)

    # =========================================================================
    # FUNCTION 22: withdraw_funds - Withdraw funds from betting account
    # =========================================================================
    def withdraw_funds(self):
        """Withdraw funds from account"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_t("betting.btn.withdraw", default="Withdraw Funds"))
        dialog.geometry("400x350")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(dialog, text=_t("betting.withdraw_funds", default="Withdraw Funds"), font=('Arial', 14, 'bold')).pack(pady=10)
        ttk.Label(dialog, text=f"Available: GBP {self.account['balance']:.2f}", font=('Arial', 11)).pack()

        ttk.Label(dialog, text=_t("betting.labels.amount", default="Amount (GBP)") + ":").pack(pady=5)
        amount_entry = ttk.Entry(dialog, width=20)
        amount_entry.pack(pady=5)

        # Get student info for student account option
        student_id = self.current_user.get('student_id') or self.current_user.get('username') or self.user_id
        student_balance = None
        if FINANCE_AVAILABLE and student_id:
            try:
                student_balance = get_student_finance_account_balance(student_id)
            except Exception as e:
                logger.warning(f"Could not get student balance: {e}")

        ttk.Label(dialog, text=_t("betting.labels.payment_method", default="Withdraw To") + ":").pack(pady=5)

        # Add Student Finance Account option if available
        withdrawal_options = ['Bank Account', 'PayPal', 'Debit Card']
        if FINANCE_AVAILABLE and student_balance is not None:
            withdrawal_options.append('Student Finance Account')

        method_combo = ttk.Combobox(dialog, values=withdrawal_options, state='readonly', width=25)
        method_combo.set('Bank Account')
        method_combo.pack(pady=5)

        # Display student account balance if available
        balance_label = ttk.Label(dialog, text="", font=('Arial', 9), foreground='blue')
        balance_label.pack(pady=2)

        def update_balance_display(*args):
            if method_combo.get() == 'Student Finance Account' and student_balance is not None:
                balance_label.config(text=f"Current Student Account Balance: GBP {student_balance:.2f}")
            else:
                balance_label.config(text="")

        method_combo.bind('<<ComboboxSelected>>', update_balance_display)

        def confirm_withdrawal():
            try:
                amount = float(amount_entry.get())

                if amount > self.account['balance']:
                    messagebox.showwarning(_t("common.warning", default="Warning"), "Insufficient balance")
                    return

                if amount < 10:
                    messagebox.showwarning(_t("common.warning", default="Warning"), "Minimum withdrawal is GBP 10")
                    return

                method = method_combo.get()

                # Handle Student Finance Account withdrawal separately
                if method == 'Student Finance Account':
                    if not FINANCE_AVAILABLE:
                        messagebox.showerror(_t("common.error", default="Error"),
                                           "Student finance system is not available")
                        return

                    success = self.withdraw_to_student_account(amount, student_id, student_balance)
                    if success:
                        dialog.destroy()
                    return

                # Regular withdrawal for other methods
                transaction_id = AccountManager.withdraw(
                    self.user_id, amount, method, self.current_user.get('username')
                )

                if transaction_id:
                    self.update_balance_display()
                    self.load_transactions()

                    # Send withdrawal confirmation email
                    self.send_withdrawal_receipt(amount, method, transaction_id)

                    messagebox.showinfo(
                        _t("common.success", default="Success"),
                        _t("betting.messages.withdrawal_success", default="GBP {amount:.2f} withdrawal processed!").format(amount=amount)
                    )
                    dialog.destroy()
                else:
                    messagebox.showerror(_t("common.error", default="Error"), "Withdrawal failed")

            except ValueError:
                messagebox.showwarning(_t("common.warning", default="Warning"), "Please enter a valid amount")

        ttk.Button(dialog, text=_t("betting.btn.withdraw", default="Withdraw"), command=confirm_withdrawal).pack(pady=20)

    def withdraw_to_student_account(self, amount: float, student_id: str, current_balance: float):
        """Withdraw betting funds to student finance account"""
        try:
            # Import the function to ensure student account exists
            from education_system.university_system.modules.shared.utils.finance_integration import ensure_student_finance_account_exists

            # Ensure student account exists
            ensure_student_finance_account_exists(student_id)

            # Get old balance
            old_balance = current_balance if current_balance is not None else 0.0
            new_balance = old_balance + amount

            # Withdraw from betting account first
            transaction_id = AccountManager.withdraw(
                self.user_id, amount, 'Student Finance Account', self.current_user.get('username')
            )

            if not transaction_id:
                messagebox.showerror(_t("common.error", default="Error"),
                                   "Failed to withdraw from betting account")
                return False

            # Generate withdrawal reference
            withdrawal_ref = f"BETTING-WITHDRAWAL-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Add funds to student finance account
            with transaction() as conn:
                cursor = conn.cursor()

                # Update student account balance
                cursor.execute('''
                    UPDATE student_finance_accounts
                    SET balance = balance + ?
                    WHERE student_id = ?
                ''', (amount, student_id))

                # Get account_id for the transaction
                cursor.execute('''
                    SELECT account_id FROM student_finance_accounts WHERE student_id = ?
                ''', (student_id,))
                account_result = cursor.fetchone()
                account_id = account_result[0] if account_result else None

                # Log transaction in student finance system
                cursor.execute('''
                    INSERT INTO transactions
                    (source_type, account_id, student_id, transaction_type, amount, balance_after, description,
                     reference_id, processed_by, created_at)
                    VALUES ('student_finance', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (account_id, student_id, 'credit', amount, new_balance,
                      f'Betting shop withdrawal - {withdrawal_ref}',
                      withdrawal_ref,
                      self.current_user.get('username', 'System'),
                      datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

            # Update UI
            self.update_balance_display()
            self.load_transactions()

            # Send confirmation email
            self.send_withdrawal_receipt(amount, 'Student Finance Account', transaction_id,
                                        old_balance, new_balance, withdrawal_ref)

            # Show success message
            messagebox.showinfo(
                _t("common.success", default="Success"),
                f"GBP {amount:.2f} successfully withdrawn to your student account!\n\n"
                f"Withdrawal Reference: {withdrawal_ref}\n"
                f"Old Balance: GBP {old_balance:.2f}\n"
                f"New Balance: GBP {new_balance:.2f}"
            )

            # Log activity
            log_activity(
                'betting_withdrawal_to_student_account',
                'betting_shop',
                user=self.current_user.get('username'),
                details={
                    'amount': amount,
                    'withdrawal_ref': withdrawal_ref,
                    'student_id': student_id
                }
            )

            return True

        except Exception as e:
            logger.error(f"Error withdrawing to student account: {e}")
            messagebox.showerror(_t("common.error", default="Error"),
                               f"Error processing withdrawal to student account: {str(e)}")
            return False

    def send_withdrawal_receipt(self, amount: float, method: str, transaction_id: int,
                                old_balance: float = None, new_balance: float = None,
                                withdrawal_ref: str = None):
        """Send withdrawal confirmation email"""
        user_email = self.user_email or self.account.get('email', '')
        if not EMAIL_AVAILABLE or not user_email or '@' not in user_email:
            logger.info(f"Withdrawal receipt email skipped - invalid email: {user_email}")
            return

        # Build conditional sections
        withdrawal_ref_line = f"Withdrawal Reference:  {withdrawal_ref}" if withdrawal_ref else ""

        student_account_section = ""
        if method == 'Student Finance Account' and old_balance is not None and new_balance is not None:
            student_account_section = f"""
------------------------------------------------------------
            STUDENT FINANCE ACCOUNT
------------------------------------------------------------
Previous Balance:      GBP {old_balance:.2f}
Withdrawal Amount:     GBP {amount:.2f}
New Balance:           GBP {new_balance:.2f}
"""

        method_note = "The funds have been added to your student finance account." if method == 'Student Finance Account' else f"Your funds will be transferred to your {method}."

        # Try to render from template
        subject = None
        body = None
        if render_template:
            subject, body = render_template('commerce/betting/withdrawal_confirmation', {
                'user_name': self.user_name,
                'transaction_id': transaction_id,
                'withdrawal_ref_line': withdrawal_ref_line,
                'withdrawal_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'amount': f"GBP {amount:.2f}",
                'method': method,
                'betting_balance': f"GBP {self.account['balance']:.2f}",
                'student_account_section': student_account_section,
                'method_note': method_note
            })

        # Fallback if template not found
        if not subject or not body:
            subject = f"Withdrawal Confirmation - GBP {amount:.2f}"
            body = f"""
Dear {self.user_name},

This confirms your withdrawal from your University Betting Shop account.

{'='*60}
                    WITHDRAWAL CONFIRMATION
{'='*60}

Transaction ID:        {transaction_id}
{withdrawal_ref_line}
Date:                  {datetime.now().strftime('%Y-%m-%d %H:%M')}
Amount:                GBP {amount:.2f}
Withdrawal Method:     {method}
Betting Account Balance: GBP {self.account['balance']:.2f}
{student_account_section}
{'='*60}

Your withdrawal has been processed successfully.
{method_note}

Please gamble responsibly.

University Betting Shop

---
This is an automated message. Please do not reply.
"""

        # Send email
        try:
            result = send_email(
                recipient_email=user_email,
                subject=subject,
                body=body
            )

            if result:
                logger.info(f"Withdrawal receipt email sent to {user_email}")
            else:
                logger.warning(f"Failed to send withdrawal receipt email to {user_email}")

        except Exception as e:
            logger.error(f"Error sending withdrawal receipt email: {e}")

    def record_revenue_transaction(self, amount: float, description: str):
        """Record deposit as revenue in finance system.

        8.117.104: routed through unified record_payment() with
        source_type='betting'.
        """
        try:
            from education_system.university_system.modules.domain.finance.core.unified_payments import (
                record_payment as _record_payment,
            )
            _record_payment(
                student_id=self.user_id,
                amount=amount,
                payment_method='betting_deposit',
                source_type='betting',
                payment_type='deposit',
                department='betting',
                description=description,
                created_by=self.current_user.get('username'),
            )
        except Exception as e:
            print(f"Error recording revenue: {e}")

    def send_deposit_receipt(self, amount: float, method: str, transaction_id: int):
        """Send deposit receipt email"""
        user_email = self.user_email or self.account.get('email', '')
        if not EMAIL_AVAILABLE or not user_email or '@' not in user_email:
            logger.info(f"Deposit receipt email skipped - invalid email: {user_email}")
            return

        # Try to render from template
        subject = None
        body = None
        if render_template:
            subject, body = render_template('commerce/betting/deposit_confirmation', {
                'user_name': self.user_name,
                'transaction_id': transaction_id,
                'deposit_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'amount': f"GBP {amount:.2f}",
                'method': method,
                'new_balance': f"GBP {self.account['balance'] + amount:.2f}"
            })

        # Fallback if template not found
        if not subject or not body:
            subject = f"Deposit Confirmation - GBP {amount:.2f}"
            body = f"""
Dear {self.user_name},

This confirms your deposit to your University Betting Shop account.

{'='*50}
                    DEPOSIT RECEIPT
{'='*50}

Transaction ID:   {transaction_id}
Date:             {datetime.now().strftime('%Y-%m-%d %H:%M')}
Amount:           GBP {amount:.2f}
Payment Method:   {method}
New Balance:      GBP {self.account['balance'] + amount:.2f}

{'='*50}

Please gamble responsibly.

University Betting Shop
"""

        send_email(
            recipient_email=user_email,
            subject=subject,
            body=body
        )
        logger.info(f"Deposit receipt email sent to {user_email}")

    def send_bet_receipt(self, bet_id: int, bet_type: str, stake: float):
        """Send bet receipt email"""
        user_email = self.user_email or self.account.get('email', '')
        if not EMAIL_AVAILABLE or not user_email or '@' not in user_email:
            logger.info(f"Bet receipt email skipped - invalid email: {user_email}")
            return

        # Try to render from template
        subject = None
        body = None
        if render_template:
            subject, body = render_template('commerce/betting/bet_confirmation', {
                'user_name': self.user_name,
                'bet_id': bet_id,
                'bet_type': f"{bet_type.title()} Bet",
                'bet_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'stake': f"GBP {stake:.2f}"
            })

        # Fallback if template not found
        if not subject or not body:
            subject = f"Bet Confirmation - #{bet_id}"
            body = f"""
Dear {self.user_name},

This confirms your bet placement.

{'='*50}
                    BET RECEIPT
{'='*50}

Bet ID:           {bet_id}
Type:             {bet_type.title()} Bet
Date:             {datetime.now().strftime('%Y-%m-%d %H:%M')}
Stake:            GBP {stake:.2f}

{'='*50}

Good luck! Please gamble responsibly.

University Betting Shop
"""

        send_email(
            recipient_email=user_email,
            subject=subject,
            body=body
        )
        logger.info(f"Bet receipt email sent to {user_email}")

    # =========================================================================
    # FUNCTION 23: create_admin_tab - Tab for admin functions
    # =========================================================================
    def create_admin_tab(self):
        """Create admin tab for staff/admin users"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("betting.tabs.admin", default="Admin"))

        # Admin actions
        actions_frame = ttk.LabelFrame(tab, text=_t("betting.admin_actions", default="Admin Actions"), padding="15")
        actions_frame.pack(fill=tk.X, padx=10, pady=10)

        btn_grid = ttk.Frame(actions_frame)
        btn_grid.pack()

        ttk.Button(btn_grid, text=_t("betting.btn.create_event", default="Create Sports Event"), command=self.create_sports_event, width=25).grid(row=0, column=0, padx=10, pady=5)
        ttk.Button(btn_grid, text=_t("betting.btn.settle_event", default="Settle Event"), command=self.settle_event, width=25).grid(row=0, column=1, padx=10, pady=5)
        ttk.Button(btn_grid, text=_t("betting.btn.create_market", default="Create Prediction Market"), command=self.create_prediction, width=25).grid(row=1, column=0, padx=10, pady=5)
        ttk.Button(btn_grid, text=_t("betting.btn.resolve_market", default="Resolve Market"), command=self.resolve_prediction, width=25).grid(row=1, column=1, padx=10, pady=5)

        # Reports section
        report_frame = ttk.LabelFrame(tab, text=_t("betting.reports", default="Reports"), padding="10")
        report_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Date range
        date_frame = ttk.Frame(report_frame)
        date_frame.pack(fill=tk.X, pady=5)

        ttk.Label(date_frame, text=_t("betting.labels.start_date", default="Start Date") + ":").pack(side=tk.LEFT, padx=5)
        self.admin_start = ttk.Entry(date_frame, width=12)
        self.admin_start.insert(0, datetime.now().replace(day=1).strftime('%Y-%m-%d'))
        self.admin_start.pack(side=tk.LEFT, padx=5)

        ttk.Label(date_frame, text=_t("betting.labels.end_date", default="End Date") + ":").pack(side=tk.LEFT, padx=5)
        self.admin_end = ttk.Entry(date_frame, width=12)
        self.admin_end.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.admin_end.pack(side=tk.LEFT, padx=5)

        ttk.Button(date_frame, text=_t("betting.btn.generate_report", default="Generate Report"), command=self.generate_admin_report).pack(side=tk.LEFT, padx=20)
        ttk.Button(date_frame, text=_t("betting.btn.email_report", default="Email Report"), command=self.email_admin_report).pack(side=tk.LEFT, padx=5)

        # Report display
        self.admin_report_text = scrolledtext.ScrolledText(report_frame, wrap=tk.WORD, font=('Courier', 10))
        self.admin_report_text.pack(fill=tk.BOTH, expand=True, pady=10)

    def create_sports_event(self):
        """Create a new sports event"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_t("betting.btn.create_event", default="Create Sports Event"))
        dialog.geometry("400x450")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(dialog, text=_t("betting.labels.event_name", default="Event Name") + ":").pack(anchor=tk.W, padx=20, pady=(10, 0))
        name_entry = ttk.Entry(dialog, width=40)
        name_entry.pack(padx=20, pady=5)

        ttk.Label(dialog, text=_t("betting.labels.sport", default="Sport") + ":").pack(anchor=tk.W, padx=20)
        sport_combo = ttk.Combobox(dialog, values=['Football', 'Basketball', 'Tennis', 'Cricket', 'Rugby', 'eSports'], width=37)
        sport_combo.set('Football')
        sport_combo.pack(padx=20, pady=5)

        ttk.Label(dialog, text=_t("betting.labels.team_a", default="Team A (Home)") + ":").pack(anchor=tk.W, padx=20)
        team_a_entry = ttk.Entry(dialog, width=40)
        team_a_entry.pack(padx=20, pady=5)

        ttk.Label(dialog, text=_t("betting.labels.team_b", default="Team B (Away)") + ":").pack(anchor=tk.W, padx=20)
        team_b_entry = ttk.Entry(dialog, width=40)
        team_b_entry.pack(padx=20, pady=5)

        ttk.Label(dialog, text=_t("betting.labels.odds_a", default="Odds Team A") + ":").pack(anchor=tk.W, padx=20)
        odds_a_entry = ttk.Entry(dialog, width=40)
        odds_a_entry.insert(0, "2.00")
        odds_a_entry.pack(padx=20, pady=5)

        ttk.Label(dialog, text=_t("betting.labels.odds_b", default="Odds Team B") + ":").pack(anchor=tk.W, padx=20)
        odds_b_entry = ttk.Entry(dialog, width=40)
        odds_b_entry.insert(0, "2.00")
        odds_b_entry.pack(padx=20, pady=5)

        ttk.Label(dialog, text=_t("betting.labels.odds_draw", default="Odds Draw") + ":").pack(anchor=tk.W, padx=20)
        odds_draw_entry = ttk.Entry(dialog, width=40)
        odds_draw_entry.insert(0, "3.50")
        odds_draw_entry.pack(padx=20, pady=5)

        ttk.Label(dialog, text=_t("betting.labels.event_date", default="Event Date (YYYY-MM-DD)") + ":").pack(anchor=tk.W, padx=20)
        date_entry = ttk.Entry(dialog, width=40)
        date_entry.insert(0, (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'))
        date_entry.pack(padx=20, pady=5)

        def create():
            try:
                event_id = SportsBettingManager.create_event(
                    event_name=name_entry.get().strip(),
                    event_type='match',
                    sport_type=sport_combo.get(),
                    team_a=team_a_entry.get().strip(),
                    team_b=team_b_entry.get().strip(),
                    odds_a=float(odds_a_entry.get()),
                    odds_b=float(odds_b_entry.get()),
                    odds_draw=float(odds_draw_entry.get()) if odds_draw_entry.get() else None,
                    event_date=date_entry.get().strip(),
                    created_by=self.current_user.get('username')
                )

                if event_id:
                    messagebox.showinfo(_t("common.success", default="Success"), "Event created successfully!")
                    dialog.destroy()
                    self.load_sports_events()
                else:
                    messagebox.showerror(_t("common.error", default="Error"), "Failed to create event")

            except ValueError:
                messagebox.showwarning(_t("common.warning", default="Warning"), "Please enter valid odds values")

        ttk.Button(dialog, text=_t("betting.btn.create_event", default="Create Event"), command=create).pack(pady=15)

    def settle_event(self):
        """Settle a sports event"""
        events = SportsBettingManager.get_upcoming_events()

        if not events:
            messagebox.showinfo(_t("common.info", default="Info"), "No events to settle")
            return

        dialog = tk.Toplevel(self.window)
        dialog.title(_t("betting.btn.settle_event", default="Settle Event"))
        dialog.geometry("500x350")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(dialog, text=_t("betting.select_event_to_settle", default="Select event to settle:")).pack(pady=10)

        listbox = tk.Listbox(dialog, height=8, width=60)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        event_map = {}
        for event in events:
            display = f"{event['event_id']}: {event['team_a']} vs {event['team_b']} ({event['event_date']})"
            listbox.insert(tk.END, display)
            event_map[listbox.size() - 1] = event

        ttk.Label(dialog, text=_t("betting.labels.result", default="Result") + ":").pack(pady=(10, 0))
        result_var = tk.StringVar(value='team_a')

        result_frame = ttk.Frame(dialog)
        result_frame.pack()

        team_a_radio = ttk.Radiobutton(result_frame, text=_t("betting.selections.home_win", default="Home Win"), variable=result_var, value='team_a')
        team_a_radio.pack(side=tk.LEFT, padx=10)
        draw_radio = ttk.Radiobutton(result_frame, text=_t("betting.selections.draw", default="Draw"), variable=result_var, value='draw')
        draw_radio.pack(side=tk.LEFT, padx=10)
        team_b_radio = ttk.Radiobutton(result_frame, text=_t("betting.selections.away_win", default="Away Win"), variable=result_var, value='team_b')
        team_b_radio.pack(side=tk.LEFT, padx=10)

        def update_options(*args):
            selection = listbox.curselection()
            if selection:
                event = event_map[selection[0]]
                team_a_radio.config(text=f"{event['team_a']} Win")
                team_b_radio.config(text=f"{event['team_b']} Win")

        listbox.bind('<<ListboxSelect>>', update_options)

        def settle():
            selection = listbox.curselection()
            if not selection:
                messagebox.showwarning(_t("common.warning", default="Warning"), "Please select an event")
                return

            event = event_map[selection[0]]
            result = result_var.get()

            if SportsBettingManager.settle_event(event['event_id'], result, self.current_user.get('username')):
                messagebox.showinfo(_t("common.success", default="Success"), "Event settled successfully")
                dialog.destroy()
                self.load_sports_events()
            else:
                messagebox.showerror(_t("common.error", default="Error"), "Failed to settle event")

        ttk.Button(dialog, text=_t("betting.btn.settle", default="Settle"), command=settle).pack(pady=15)

    # =========================================================================
    # FUNCTION 24: generate_admin_report - Generate comprehensive admin report
    # =========================================================================
    def generate_admin_report(self):
        """Generate admin report"""
        try:
            start_date = self.admin_start.get().strip()
            end_date = self.admin_end.get().strip()

            report = ReportManager.generate_admin_report(start_date, end_date)

            self.admin_report_text.delete('1.0', tk.END)
            self.admin_report_text.insert('1.0', report)

            messagebox.showinfo(
                _t("common.success", default="Success"),
                _t("betting.messages.report_generated", default="Report generated successfully")
            )

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    # =========================================================================
    # FUNCTION 25: email_admin_report - Email report to admin
    # =========================================================================
    def email_admin_report(self):
        """Email the admin report"""
        report = self.admin_report_text.get('1.0', tk.END).strip()

        if not report:
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("betting.warnings.generate_report_first", default="Please generate a report first")
            )
            return

        admin_email = simpledialog.askstring(
            _t("betting.btn.email_report", default="Email Report"),
            _t("betting.prompts.admin_email", default="Enter admin email:"),
            initialvalue=self.admin_email
        )

        if not admin_email:
            return

        try:
            if EMAIL_AVAILABLE:
                result = send_email(
                    recipient_email=admin_email,
                    subject=f"Betting Shop Report - {datetime.now().strftime('%Y-%m-%d')}",
                    body=report
                )

                if result:
                    messagebox.showinfo(
                        _t("common.success", default="Success"),
                        _t("betting.messages.report_emailed", default="Report sent successfully")
                    )
                    log_activity('email_report', 'betting_shop', details={'recipient': admin_email})
                else:
                    messagebox.showerror(_t("common.error", default="Error"), "Failed to send email")
            else:
                messagebox.showwarning(_t("common.warning", default="Warning"), "Email service not available")

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    # =========================================================================
    # Helper: Load bet history for account tab
    # =========================================================================
    def load_bet_history(self):
        """Load bet history (called by refresh)"""
        pass  # History is loaded on-demand via view_bet_history


def launch_betting_shop_gui(root, auth):
    """Launch the Betting Shop GUI"""
    try:
        BettingShopGUI(root, auth)
    except Exception as e:
        messagebox.showerror(
            _t("common.error", default="Error"),
            _t("betting.errors.launch_failed", default="Failed to launch Betting Shop: {error}").format(error=str(e))
        )
        print(f"Betting Shop GUI error: {traceback.format_exc()}")


__all__ = ['BettingShopGUI', 'launch_betting_shop_gui']
