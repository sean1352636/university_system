"""SportsTab mixin."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from ..shared import *


class SportsTabMixin:
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

        self.events_tree.heading('id', text=_t('gui.operations.commerce.betting.tabs.sports.headings.id', default='ID'))
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
        self.selection_var = tk.StringVar(value=_t('gui.operations.commerce.betting.tabs.sports.values.team_a', default='team_a'))
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
        self.return_var = tk.StringVar(value=_t('gui.operations.commerce.betting.tabs.sports.values.gbp_0_00', default="GBP 0.00"))
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
                messagebox.showerror(_t("common.error", default="Error"), _t('gui.operations.commerce.betting.tabs.sports.dialogs.cash_out_failed', default="Cash out failed"))

        ttk.Button(dialog, text=_t("betting.btn.cash_out", default="Cash Out"), command=confirm_cash_out).pack(pady=10)

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
