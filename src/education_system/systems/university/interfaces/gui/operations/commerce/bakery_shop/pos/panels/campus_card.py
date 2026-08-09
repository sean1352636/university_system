
from education_system.systems.university.infrastructure.i18n import get_text as _t
from ..context import *  # noqa: F401,F403


class CampusCardPanelMixin:
    def _build_campus_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.campus_card.buttons.issue_card', default="+ Issue card"), command=self._campus_issue,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.campus_card.buttons.top_up', default="💷 Top up"), command=self._campus_topup,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.campus_card.buttons.add_meal_swipes', default="🍽 Add meal swipes"),
                  command=self._campus_add_swipes,
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.campus_card.buttons.refresh', default="↻ Refresh"), command=self._campus_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)

        cols = ("card", "user", "balance", "swipes", "active", "updated")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c, h, w in [("card", "Card ID", 140), ("user", "User", 140),
                        ("balance", "Balance", 100), ("swipes", "Swipes", 80),
                        ("active", "Active", 70), ("updated", "Updated", 150)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="x", padx=10, pady=6)
        self._campus_tree = tv

        tk.Label(parent, text=_t('gui.operations.commerce.bakery_shop.pos.panels.campus_card.labels.recent_transactions', default="Recent transactions"),
                 bg=bg, font=("Arial", 11, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
        cols2 = ("ts", "card", "type", "amount", "swipes", "order")
        tv2 = ttk.Treeview(parent, columns=cols2, show="headings", height=10)
        for c, h, w in [("ts", "When", 150), ("card", "Card", 140),
                        ("type", "Type", 90), ("amount", "Amount", 90),
                        ("swipes", "Swipes", 80), ("order", "Order", 140)]:
            tv2.heading(c, text=h); tv2.column(c, width=w, anchor="w")
        tv2.pack(fill="both", expand=True, padx=10, pady=6)
        self._campus_txn_tree = tv2
        self._campus_refresh()

    def _campus_refresh(self):
        conn = self._connect()
        try:
            cards = conn.execute(
                "SELECT card_id, user, balance, meal_swipes, active, updated_at "
                "FROM bakery_campus_cards ORDER BY card_id"
            ).fetchall()
            txns = conn.execute(
                "SELECT timestamp, card_id, txn_type, amount, swipes, order_id "
                "FROM bakery_campus_card_txns ORDER BY id DESC LIMIT 100"
            ).fetchall()
        finally:
            conn.close()
        tv = self._campus_tree; tv.delete(*tv.get_children())
        for cid, u, bal, sw, active, upd in cards:
            tv.insert("", "end", values=(cid, u or "", f"£{(bal or 0):.2f}",
                                         sw or 0, "yes" if active else "no",
                                         upd or ""))
        tv2 = self._campus_txn_tree; tv2.delete(*tv2.get_children())
        for ts, cid, tp, amt, sw, oid in txns:
            tv2.insert("", "end", values=(ts, cid, tp,
                                          f"£{(amt or 0):.2f}",
                                          sw or 0, oid or ""))

    def _campus_issue(self):
        cid = simpledialog.askstring(_t('gui.operations.commerce.bakery_shop.pos.panels.campus_card.dialogs.issue_card', default="Issue card"), _t('gui.operations.commerce.bakery_shop.pos.panels.campus_card.dialogs.card_id_e_g_s12345', default="Card ID (e.g. S12345):"),
                                     parent=self.root)
        if not cid:
            return
        user = simpledialog.askstring(_t('gui.operations.commerce.bakery_shop.pos.panels.campus_card.dialogs.issue_card', default="Issue card"), _t('gui.operations.commerce.bakery_shop.pos.panels.campus_card.dialogs.linked_user_optional', default="Linked user (optional):"),
                                      parent=self.root) or ""
        bal = simpledialog.askfloat(_t('gui.operations.commerce.bakery_shop.pos.panels.campus_card.dialogs.issue_card', default="Issue card"), _t('gui.operations.commerce.bakery_shop.pos.panels.campus_card.dialogs.opening_balance', default="Opening balance £:"),
                                    initialvalue=0.0, parent=self.root) or 0.0
        sw = simpledialog.askinteger(_t('gui.operations.commerce.bakery_shop.pos.panels.campus_card.dialogs.issue_card', default="Issue card"), _t('gui.operations.commerce.bakery_shop.pos.panels.campus_card.dialogs.meal_swipes', default="Meal swipes:"),
                                     initialvalue=0, parent=self.root) or 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO bakery_campus_cards "
                "(card_id, user, balance, meal_swipes, active, "
                "created_at, updated_at) VALUES (?,?,?,?,1,?,?)",
                (cid, user, bal, sw, now, now))
            conn.commit()
        finally:
            conn.close()
        self._campus_refresh()

    def _campus_topup(self):
        sel = self._campus_tree.focus()
        if not sel:
            return
        cid = self._campus_tree.item(sel, "values")[0]
        amt = simpledialog.askfloat(_t('gui.operations.commerce.bakery_shop.pos.panels.campus_card.dialogs.top_up', default="Top up"), f"Add £ to {cid}:",
                                    minvalue=0.01, parent=self.root)
        if not amt:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE bakery_campus_cards SET balance = balance + ?, "
                "updated_at=? WHERE card_id=?", (amt, now, cid))
            conn.execute(
                "INSERT INTO bakery_campus_card_txns "
                "(card_id, txn_type, amount, timestamp) VALUES (?,?,?,?)",
                (cid, "topup", amt, now))
            conn.commit()
        finally:
            conn.close()
        self._campus_refresh()

    def _campus_add_swipes(self):
        sel = self._campus_tree.focus()
        if not sel:
            return
        cid = self._campus_tree.item(sel, "values")[0]
        n = simpledialog.askinteger(_t('gui.operations.commerce.bakery_shop.pos.panels.campus_card.dialogs.swipes', default="Swipes"), f"Add swipes to {cid}:",
                                    minvalue=1, parent=self.root)
        if not n:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE bakery_campus_cards SET meal_swipes = meal_swipes + ?, "
                "updated_at=? WHERE card_id=?", (n, now, cid))
            conn.execute(
                "INSERT INTO bakery_campus_card_txns "
                "(card_id, txn_type, swipes, timestamp) VALUES (?,?,?,?)",
                (cid, "topup", n, now))
            conn.commit()
        finally:
            conn.close()
        self._campus_refresh()

