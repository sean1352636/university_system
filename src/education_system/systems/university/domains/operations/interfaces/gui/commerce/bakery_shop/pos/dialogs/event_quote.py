
from education_system.systems.university.infrastructure.i18n import get_text as _t
from ..context import *  # noqa: F401,F403


class EventQuoteDialogMixin:
    def _quote_new(self):
        d = tk.Toplevel(self.root); d.title(_t('gui.operations.commerce.bakery_shop.pos.dialogs.event_quote.windows.event_quote', default="Event quote"))
        d.transient(self.root); d.grab_set()
        fields = [("Customer name", ""),
                  ("Contact (email/phone)", ""),
                  ("Event type", "wedding"),
                  ("Event date (YYYY-MM-DD)",
                   (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")),
                  ("Servings", "80"),
                  ("Details", ""),
                  ("Quoted price £", "350.00"),
                  ("Deposit £", "100.00")]
        vars_ = []
        for i, (lbl, val) in enumerate(fields):
            tk.Label(d, text=lbl + ":").grid(row=i, column=0,
                                              padx=8, pady=4, sticky="e")
            v = tk.StringVar(value=val); vars_.append(v)
            w = tk.Entry(d, textvariable=v, width=30)
            w.grid(row=i, column=1, padx=8, pady=4, sticky="w")
        def save():
            try:
                servings = int(vars_[4].get())
                qp = float(vars_[6].get()); dp = float(vars_[7].get())
            except ValueError:
                messagebox.showerror(_t('gui.operations.commerce.bakery_shop.pos.dialogs.event_quote.dialogs.quote', default="Quote"), _t('gui.operations.commerce.bakery_shop.pos.dialogs.event_quote.dialogs.numeric_fields_invalid', default="Numeric fields invalid."),
                                     parent=d); return
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_event_quotes "
                    "(customer, contact, event_type, event_date, details, "
                    "servings, quoted_price, deposit_amount, deposit_paid, "
                    "status, created_at, updated_at, created_by) "
                    "VALUES (?,?,?,?,?,?,?,?,0,'draft',?,?,?)",
                    (vars_[0].get(), vars_[1].get(), vars_[2].get(),
                     vars_[3].get(), vars_[5].get(), servings,
                     qp, dp, now, now, self.current_user or "system"))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._quote_refresh()
        tk.Button(d, text=_t('gui.operations.commerce.bakery_shop.pos.dialogs.event_quote.buttons.save', default="Save"), command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).grid(row=len(fields), column=0, columnspan=2, pady=10)

