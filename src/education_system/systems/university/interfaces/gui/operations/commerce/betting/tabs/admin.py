"""AdminTab mixin."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from ..shared import *


class AdminTabMixin:
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
                    messagebox.showinfo(_t("common.success", default="Success"), _t('gui.operations.commerce.betting.tabs.admin.dialogs.event_created_successfully', default="Event created successfully!"))
                    dialog.destroy()
                    self.load_sports_events()
                else:
                    messagebox.showerror(_t("common.error", default="Error"), _t('gui.operations.commerce.betting.tabs.admin.dialogs.failed_to_create_event', default="Failed to create event"))

            except ValueError:
                messagebox.showwarning(_t("common.warning", default="Warning"), _t('gui.operations.commerce.betting.tabs.admin.dialogs.please_enter_valid_odds_values', default="Please enter valid odds values"))

        ttk.Button(dialog, text=_t("betting.btn.create_event", default="Create Event"), command=create).pack(pady=15)

    def settle_event(self):
        """Settle a sports event"""
        events = SportsBettingManager.get_upcoming_events()

        if not events:
            messagebox.showinfo(_t("common.info", default="Info"), _t('gui.operations.commerce.betting.tabs.admin.dialogs.no_events_to_settle', default="No events to settle"))
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
        result_var = tk.StringVar(value=_t('gui.operations.commerce.betting.tabs.admin.values.team_a', default='team_a'))

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
                messagebox.showwarning(_t("common.warning", default="Warning"), _t('gui.operations.commerce.betting.tabs.admin.dialogs.please_select_an_event', default="Please select an event"))
                return

            event = event_map[selection[0]]
            result = result_var.get()

            if SportsBettingManager.settle_event(event['event_id'], result, self.current_user.get('username')):
                messagebox.showinfo(_t("common.success", default="Success"), _t('gui.operations.commerce.betting.tabs.admin.dialogs.event_settled_successfully', default="Event settled successfully"))
                dialog.destroy()
                self.load_sports_events()
            else:
                messagebox.showerror(_t("common.error", default="Error"), _t('gui.operations.commerce.betting.tabs.admin.dialogs.failed_to_settle_event', default="Failed to settle event"))

        ttk.Button(dialog, text=_t("betting.btn.settle", default="Settle"), command=settle).pack(pady=15)

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
                    messagebox.showerror(_t("common.error", default="Error"), _t('gui.operations.commerce.betting.tabs.admin.dialogs.failed_to_send_email', default="Failed to send email"))
            else:
                messagebox.showwarning(_t("common.warning", default="Warning"), _t('gui.operations.commerce.betting.tabs.admin.dialogs.email_service_not_available', default="Email service not available"))

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    def load_bet_history(self):
        """Load bet history (called by refresh)"""
        pass  # History is loaded on-demand via view_bet_history
