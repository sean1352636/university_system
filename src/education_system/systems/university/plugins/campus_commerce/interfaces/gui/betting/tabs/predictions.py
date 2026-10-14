"""PredictionsTab mixin."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from ..shared import *


class PredictionsTabMixin:
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

        self.markets_tree.heading('id', text=_t('gui.operations.commerce.betting.tabs.predictions.headings.id', default='ID'))
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
        self.outcome_a_var = tk.StringVar(value=_t('gui.operations.commerce.betting.tabs.predictions.values.outcome_a', default="Outcome A"))
        self.outcome_b_var = tk.StringVar(value=_t('gui.operations.commerce.betting.tabs.predictions.values.outcome_b', default="Outcome B"))

        ttk.Label(pred_frame, text=_t("betting.labels.your_prediction", default="Your Prediction") + ":").pack(anchor=tk.W, pady=(10, 0))
        self.pred_selection_var = tk.StringVar(value=_t('gui.operations.commerce.betting.tabs.predictions.values.outcome_a_variant_2', default='outcome_a'))

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

    def create_prediction(self):
        """Create a new prediction market"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_t("betting.btn.create_market", default="Create Prediction Market"))
        dialog.geometry("450x400")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(dialog, text=_t("betting.labels.title", default="===== LABELS =====") + ":").pack(anchor=tk.W, padx=20, pady=(10, 0))
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
        result_var = tk.StringVar(value=_t('gui.operations.commerce.betting.tabs.predictions.values.outcome_a_variant_2', default='outcome_a'))

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
