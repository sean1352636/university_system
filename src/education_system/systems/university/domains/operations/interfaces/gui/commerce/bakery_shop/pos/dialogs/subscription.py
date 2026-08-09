
from education_system.systems.university.infrastructure.i18n import get_text as _t
from ..context import *  # noqa: F401,F403


class SubscriptionDialogMixin:
    def _subs_new(self):
        names = self._all_product_names()
        d = tk.Toplevel(self.root); d.title(_t('gui.operations.commerce.bakery_shop.pos.dialogs.subscription.windows.new_subscription', default="New subscription"))
        d.transient(self.root); d.grab_set(); d.geometry("520x520")
        bg = self.colors["background"]; d.configure(bg=bg)
        u_var = tk.StringVar(value=self.current_user or "")
        plan_var = tk.StringVar(value=_t('gui.operations.commerce.bakery_shop.pos.dialogs.subscription.values.weekly_bread_share', default="Weekly Bread Share"))
        freq_var = tk.StringVar(value=_t('gui.operations.commerce.bakery_shop.pos.dialogs.subscription.values.weekly', default="weekly"))
        price_var = tk.StringVar(value="12.00")
        tk.Label(d, text=_t('gui.operations.commerce.bakery_shop.pos.dialogs.subscription.labels.user', default="User:"), bg=bg).grid(row=0, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=u_var, width=22).grid(row=0, column=1, padx=8, pady=4, sticky="w")
        tk.Label(d, text=_t('gui.operations.commerce.bakery_shop.pos.dialogs.subscription.labels.plan_name', default="Plan name:"), bg=bg).grid(row=1, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=plan_var, width=28).grid(row=1, column=1, padx=8, pady=4, sticky="w")
        tk.Label(d, text=_t('gui.operations.commerce.bakery_shop.pos.dialogs.subscription.labels.frequency', default="Frequency:"), bg=bg).grid(row=2, column=0, padx=8, pady=4, sticky="e")
        ttk.Combobox(d, textvariable=freq_var,
                     values=["weekly", "biweekly", "monthly"],
                     state="readonly", width=14).grid(row=2, column=1,
                                                       padx=8, pady=4, sticky="w")
        tk.Label(d, text=_t('gui.operations.commerce.bakery_shop.pos.dialogs.subscription.labels.price_delivery', default="Price / delivery £:"), bg=bg).grid(row=3, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=price_var, width=10).grid(row=3, column=1,
                                                            padx=8, pady=4, sticky="w")
        tk.Label(d, text=_t('gui.operations.commerce.bakery_shop.pos.dialogs.subscription.labels.items', default="Items:"), bg=bg).grid(row=4, column=0, padx=8, pady=4, sticky="ne")
        f = tk.Frame(d, bg=bg); f.grid(row=4, column=1, padx=8, pady=4, sticky="w")
        rows_v = []
        def add_row():
            r = len(rows_v)
            iv = tk.StringVar(value=names[0] if names else "")
            qv = tk.StringVar(value="1")
            ttk.Combobox(f, textvariable=iv, values=names, state="readonly",
                         width=22).grid(row=r, column=0, padx=2)
            tk.Entry(f, textvariable=qv, width=4).grid(row=r, column=1, padx=2)
            rows_v.append((iv, qv))
        for _ in range(3):
            add_row()
        tk.Button(d, text=_t('gui.operations.commerce.bakery_shop.pos.dialogs.subscription.buttons.row', default="+ row"), command=add_row,
                  relief="flat").grid(row=5, column=1, sticky="w", padx=8)
        def save():
            try:
                price = float(price_var.get())
            except ValueError:
                messagebox.showerror(_t('gui.operations.commerce.bakery_shop.pos.dialogs.subscription.dialogs.sub', default="Sub"), _t('gui.operations.commerce.bakery_shop.pos.dialogs.subscription.dialogs.bad_price', default="Bad price."), parent=d); return
            items = {}
            for iv, qv in rows_v:
                try:
                    q = int(qv.get())
                except ValueError:
                    continue
                if q > 0:
                    items[iv.get()] = items.get(iv.get(), 0) + q
            if not items:
                messagebox.showerror(_t('gui.operations.commerce.bakery_shop.pos.dialogs.subscription.dialogs.sub', default="Sub"), _t('gui.operations.commerce.bakery_shop.pos.dialogs.subscription.dialogs.add_items', default="Add items."), parent=d); return
            now = datetime.now()
            now_s = now.strftime("%Y-%m-%d %H:%M:%S")
            days = self.FREQ_DAYS.get(freq_var.get(), 7)
            next_d = (now + timedelta(days=days)).strftime("%Y-%m-%d")
            conn = self._connect()
            try:
                cur = conn.execute(
                    "INSERT INTO bakery_subscriptions "
                    "(user, plan_name, items_json, frequency, "
                    "price_per_delivery, next_delivery, active, created_at) "
                    "VALUES (?,?,?,?,?,?,1,?)",
                    (u_var.get(), plan_var.get(), json.dumps(items),
                     freq_var.get(), price, next_d, now_s))
                sid = cur.lastrowid
                conn.execute(
                    "INSERT INTO bakery_subscription_deliveries "
                    "(subscription_id, scheduled_for, status) "
                    "VALUES (?, ?, 'scheduled')", (sid, next_d))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._subs_refresh()
        tk.Button(d, text=_t('gui.operations.commerce.bakery_shop.pos.dialogs.subscription.buttons.save', default="Save"), command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).grid(row=6, column=0, columnspan=2, pady=12)

