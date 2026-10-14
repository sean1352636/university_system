
from education_system.systems.university.infrastructure.i18n import get_text as _t
from ..context import *  # noqa: F401,F403


class SplitTenderPanelMixin:
    def _build_split_panel(self, parent):
        bg = self.colors["background"]
        info = tk.Label(parent,
            text=_t('gui.operations.commerce.bakery_shop.pos.panels.split_tender.labels.split_tender_accepts_multiple_payment_methods_on_one_order_metho', default="Split-tender accepts multiple payment methods on one order.\n"
                 "Methods: Cash, Card, Campus Card, Meal Swipe, Gift Card.\n"
                 "Use the Tile POS to start a sale, or use the manual dialog below."),
            bg=bg, font=("Arial", 11), justify="left")
        info.pack(anchor="w", padx=14, pady=10)
        tk.Button(parent, text=_t('gui.operations.commerce.bakery_shop.pos.panels.split_tender.buttons.open_split_tender_dialog_manual_amount', default="🧾 Open split-tender dialog (manual amount)"),
                  command=self._split_manual,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  font=("Arial", 12, "bold"),
                  padx=14, pady=10).pack(padx=14, pady=10)
        tk.Label(parent, text=_t('gui.operations.commerce.bakery_shop.pos.panels.split_tender.labels.recent_split_tender_orders', default="Recent split-tender orders"),
                 bg=bg, font=("Arial", 12, "bold")).pack(anchor="w", padx=14, pady=6)
        cols = ("order_id", "ts", "total", "splits")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=12)
        for c, h, w in [("order_id", "Order", 110), ("ts", "When", 150),
                        ("total", "Total", 90), ("splits", "Splits", 420)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=14, pady=6)
        self._split_tree = tv
        self._split_refresh()

    def _split_refresh(self):
        tv = self._split_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT order_id, timestamp, total, split_payments_json "
                "FROM bakery_orders WHERE split_payments_json IS NOT NULL "
                "AND split_payments_json != '' ORDER BY id DESC LIMIT 100"
            ).fetchall()
        finally:
            conn.close()
        for oid, ts, total, sp in rows:
            try:
                splits = json.loads(sp) if sp else []
                text = ", ".join(f"{s.get('method')} £{s.get('amount',0):.2f}"
                                 for s in splits)
            except Exception:
                text = sp or ""
            tv.insert("", "end", values=(oid, ts, f"£{(total or 0):.2f}", text))

    def _split_manual(self):
        amt = simpledialog.askfloat(_t('gui.operations.commerce.bakery_shop.pos.panels.split_tender.dialogs.split_tender', default="Split-tender"),
                                    _t('gui.operations.commerce.bakery_shop.pos.panels.split_tender.dialogs.total_amount_to_charge', default="Total amount to charge (£):"),
                                    minvalue=0.01, parent=self.root)
        if not amt:
            return
        self._split_tender_dialog(amt, [])

