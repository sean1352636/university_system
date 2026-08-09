
from education_system.systems.university.infrastructure.i18n import get_text as _t
from ..context import *  # noqa: F401,F403


class SubscriptionsPanelMixin:
    def _build_subs_panel(self, parent):
        bg = self.colors["background"]
        info = tk.Label(parent,
            text=_t('gui.operations.commerce.bakery_shop.pos.panels.subscriptions.labels.subscription_boxes_e_g_weekly_bread_share_each_subscription_auto', default="Subscription boxes — e.g. weekly bread share. "
                 "Each subscription auto-schedules deliveries."),
            bg=bg, font=("Arial", 11, "italic"), justify="left")
        info.pack(anchor="w", padx=14, pady=6)
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.subscriptions.buttons.new_subscription', default="+ New subscription"), command=self._subs_new,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.subscriptions.buttons.mark_next_delivery_done', default="🚚 Mark next delivery done"),
                  command=self._subs_deliver,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.subscriptions.buttons.pause_resume', default="⏸ Pause / resume"),
                  command=self._subs_toggle,
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.subscriptions.buttons.cancel', default="✖ Cancel"), command=self._subs_cancel,
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.subscriptions.buttons.refresh', default="↻ Refresh"), command=self._subs_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        cols = ("id", "user", "plan", "items", "freq", "next", "price", "active")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=10)
        for c, h, w in [("id", "ID", 50), ("user", "User", 120),
                        ("plan", "Plan", 140), ("items", "Items", 240),
                        ("freq", "Frequency", 90),
                        ("next", "Next delivery", 110),
                        ("price", "Per delivery", 110),
                        ("active", "Active", 70)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="x", padx=10, pady=6)
        self._subs_tree = tv

        tk.Label(parent, text=_t('gui.operations.commerce.bakery_shop.pos.panels.subscriptions.labels.recent_deliveries', default="Recent deliveries"),
                 bg=bg, font=("Arial", 11, "bold")).pack(anchor="w",
                                                          padx=12, pady=(8, 0))
        cols2 = ("id", "sub", "scheduled", "delivered", "order", "status")
        tv2 = ttk.Treeview(parent, columns=cols2, show="headings", height=10)
        for c, h, w in [("id", "ID", 50), ("sub", "Sub", 50),
                        ("scheduled", "Scheduled", 120),
                        ("delivered", "Delivered", 120),
                        ("order", "Order", 130), ("status", "Status", 100)]:
            tv2.heading(c, text=h); tv2.column(c, width=w, anchor="w")
        tv2.pack(fill="both", expand=True, padx=10, pady=6)
        self._subs_deliv_tree = tv2
        self._subs_refresh()

    def _subs_refresh(self):
        conn = self._connect()
        try:
            subs = conn.execute(
                "SELECT id, user, plan_name, items_json, frequency, "
                "next_delivery, price_per_delivery, active "
                "FROM bakery_subscriptions ORDER BY id DESC").fetchall()
            deliv = conn.execute(
                "SELECT id, subscription_id, scheduled_for, delivered_at, "
                "order_id, status FROM bakery_subscription_deliveries "
                "ORDER BY id DESC LIMIT 200").fetchall()
        finally:
            conn.close()
        tv = self._subs_tree; tv.delete(*tv.get_children())
        for rid, u, pl, items, fq, nx, pp, active in subs:
            try:
                d = json.loads(items)
                desc = ", ".join(f"{k}×{v}" for k, v in d.items())
            except Exception:
                desc = items or ""
            tv.insert("", "end", iid=str(rid),
                      values=(rid, u, pl, desc, fq, nx or "",
                              f"£{(pp or 0):.2f}",
                              "yes" if active else "no"))
        tv2 = self._subs_deliv_tree; tv2.delete(*tv2.get_children())
        for did, sid, sched, deli, oid, st in deliv:
            tv2.insert("", "end", values=(did, sid, sched, deli or "",
                                          oid or "", st))

    def _subs_deliver(self):
        sel = self._subs_tree.focus()
        if not sel:
            return
        sid = int(sel)
        now = datetime.now()
        now_s = now.strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            r = conn.execute(
                "SELECT frequency, next_delivery FROM bakery_subscriptions "
                "WHERE id=?", (sid,)).fetchone()
            if not r:
                return
            fq, nd = r
            # Mark current delivery delivered
            conn.execute(
                "UPDATE bakery_subscription_deliveries "
                "SET delivered_at=?, status='delivered' "
                "WHERE subscription_id=? AND status='scheduled' "
                "AND scheduled_for=?", (now_s, sid, nd))
            # Schedule next
            days = self.FREQ_DAYS.get(fq, 7)
            next_d = (now + timedelta(days=days)).strftime("%Y-%m-%d")
            conn.execute(
                "UPDATE bakery_subscriptions SET next_delivery=? "
                "WHERE id=?", (next_d, sid))
            conn.execute(
                "INSERT INTO bakery_subscription_deliveries "
                "(subscription_id, scheduled_for, status) "
                "VALUES (?, ?, 'scheduled')", (sid, next_d))
            conn.commit()
        finally:
            conn.close()
        self._subs_refresh()

    def _subs_toggle(self):
        sel = self._subs_tree.focus()
        if not sel:
            return
        conn = self._connect()
        try:
            r = conn.execute(
                "SELECT active FROM bakery_subscriptions WHERE id=?",
                (int(sel),)).fetchone()
            if not r:
                return
            new = 0 if r[0] else 1
            conn.execute(
                "UPDATE bakery_subscriptions SET active=? WHERE id=?",
                (new, int(sel)))
            conn.commit()
        finally:
            conn.close()
        self._subs_refresh()

    def _subs_cancel(self):
        sel = self._subs_tree.focus()
        if not sel:
            return
        if not messagebox.askyesno(_t('gui.operations.commerce.bakery_shop.pos.panels.subscriptions.dialogs.cancel', default="Cancel"),
                                   _t('gui.operations.commerce.bakery_shop.pos.panels.subscriptions.dialogs.cancel_this_subscription', default="Cancel this subscription?"),
                                   parent=self.root):
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE bakery_subscriptions SET active=0, cancelled_at=? "
                "WHERE id=?", (now, int(sel)))
            conn.commit()
        finally:
            conn.close()
        self._subs_refresh()

