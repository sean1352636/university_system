
from education_system.systems.university.infrastructure.i18n import get_text as _t
from ..context import *  # noqa: F401,F403


class EventQuotesPanelMixin:
    def _build_quote_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.event_quotes.buttons.new_quote', default="+ New quote"), command=self._quote_new,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.event_quotes.buttons.mark_deposit_paid', default="💷 Mark deposit paid"),
                  command=self._quote_deposit_paid,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.event_quotes.buttons.set_status', default="Set status…"), command=self._quote_set_status,
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.event_quotes.buttons.refresh', default="↻ Refresh"), command=self._quote_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        cols = ("id", "customer", "type", "event_date", "servings",
                "quoted", "deposit", "paid", "status")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=16)
        for c, h, w in [("id", "ID", 60), ("customer", "Customer", 140),
                        ("type", "Type", 110), ("event_date", "Event", 110),
                        ("servings", "Serves", 80),
                        ("quoted", "Quoted £", 100),
                        ("deposit", "Deposit £", 100),
                        ("paid", "Deposit", 100),
                        ("status", "Status", 100)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._quote_tree = tv
        self._quote_refresh()

    def _quote_refresh(self):
        tv = self._quote_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, customer, event_type, event_date, servings, "
                "quoted_price, deposit_amount, deposit_paid, status "
                "FROM bakery_event_quotes ORDER BY id DESC LIMIT 200"
            ).fetchall()
        finally:
            conn.close()
        for rid, cust, et, ed, sv, qp, da, dp, st in rows:
            tv.insert("", "end", iid=str(rid),
                      values=(rid, cust, et or "", ed,
                              sv or "", f"£{(qp or 0):.2f}",
                              f"£{(da or 0):.2f}",
                              "PAID" if dp else "unpaid", st))

    def _quote_deposit_paid(self):
        sel = self._quote_tree.focus()
        if not sel:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE bakery_event_quotes SET deposit_paid=1, "
                "deposit_paid_at=?, status=CASE WHEN status='draft' "
                "THEN 'accepted' ELSE status END, updated_at=? WHERE id=?",
                (now, now, int(sel)))
            conn.commit()
        finally:
            conn.close()
        self._quote_refresh()

    def _quote_set_status(self):
        sel = self._quote_tree.focus()
        if not sel:
            return
        d = tk.Toplevel(self.root); d.title(_t('gui.operations.commerce.bakery_shop.pos.panels.event_quotes.windows.set_status', default="Set status"))
        d.transient(self.root); d.grab_set()
        v = tk.StringVar(value=_t('gui.operations.commerce.bakery_shop.pos.panels.event_quotes.values.sent', default="sent"))
        ttk.Combobox(d, textvariable=v,
                     values=["draft", "sent", "accepted",
                             "declined", "completed"],
                     state="readonly", width=14).pack(padx=12, pady=8)
        def save():
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                conn.execute(
                    "UPDATE bakery_event_quotes SET status=?, updated_at=? "
                    "WHERE id=?", (v.get(), now, int(sel)))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._quote_refresh()
        tk.Button(d, text=_t('gui.operations.commerce.bakery_shop.pos.panels.event_quotes.buttons.save', default="Save"), command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).pack(pady=8)

