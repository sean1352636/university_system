
from education_system.systems.university.infrastructure.i18n import get_text as _t
from ..context import *  # noqa: F401,F403


class VoidRefundPanelMixin:
    def _build_void_panel(self, parent):
        bg = self.colors["background"]
        tk.Label(parent,
                 text=_t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.labels.voiding_an_order_or_issuing_a_quick_refund_requires_a_manager_pi', default="Voiding an order or issuing a quick refund requires a "
                      "manager PIN. Each event is audited below."),
                 bg=bg, font=("Arial", 11, "italic"),
                 justify="left").pack(anchor="w", padx=14, pady=8)
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=14, pady=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.buttons.set_change_manager_pin', default="🔑 Set / change manager PIN"),
                  command=self._set_manager_pin,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.buttons.void_order', default="❌ Void order"), command=self._void_order,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.buttons.quick_refund', default="💸 Quick refund"),
                  command=self._quick_refund,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.buttons.refresh', default="↻ Refresh"), command=self._void_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)

        cols = ("ts", "action", "order", "amount", "manager", "operator", "reason")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=16)
        for c, h, w in [("ts", "When", 150), ("action", "Action", 110),
                        ("order", "Order", 140), ("amount", "Amount", 100),
                        ("manager", "Manager", 110),
                        ("operator", "Operator", 110), ("reason", "Reason", 220)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=14, pady=6)
        self._void_tree = tv
        self._void_refresh()

    def _void_refresh(self):
        tv = self._void_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT timestamp, action, order_id, amount, manager, "
                "operator, reason FROM bakery_void_audit "
                "ORDER BY id DESC LIMIT 200").fetchall()
        finally:
            conn.close()
        for ts, a, oid, amt, mgr, op, rsn in rows:
            tv.insert("", "end", values=(ts, a, oid or "",
                                         f"£{(amt or 0):.2f}",
                                         mgr or "", op or "", rsn or ""))

    def _set_manager_pin(self):
        u = simpledialog.askstring(_t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.dialogs.manager_pin', default="Manager PIN"), _t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.dialogs.manager_username', default="Manager username:"),
                                   parent=self.root)
        if not u:
            return
        pin = simpledialog.askstring(_t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.dialogs.manager_pin', default="Manager PIN"), f"New 4-digit PIN for {u}:",
                                     parent=self.root, show="*")
        if not pin or not pin.isdigit() or len(pin) < 4:
            messagebox.showerror(_t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.dialogs.pin', default="PIN"), _t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.dialogs.pin_must_be_4_digits', default="PIN must be 4+ digits."),
                                 parent=self.root); return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO bakery_manager_pins (user, pin, active, created_at) "
                "VALUES (?,?,1,?) ON CONFLICT(user) DO UPDATE SET "
                "pin=excluded.pin, active=1", (u, pin, now))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo(_t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.dialogs.pin', default="PIN"), f"PIN set for {u}.", parent=self.root)

    def _verify_manager_pin(self):
        u = simpledialog.askstring(_t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.dialogs.manager_pin', default="Manager PIN"), _t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.dialogs.manager_username', default="Manager username:"),
                                   parent=self.root)
        if not u:
            return None
        pin = simpledialog.askstring(_t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.dialogs.manager_pin', default="Manager PIN"), f"PIN for {u}:",
                                     parent=self.root, show="*")
        if not pin:
            return None
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT pin FROM bakery_manager_pins "
                "WHERE user=? AND active=1", (u,)).fetchone()
        finally:
            conn.close()
        if row and row[0] == pin:
            return u
        messagebox.showerror(_t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.dialogs.pin', default="PIN"), _t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.dialogs.invalid_pin', default="Invalid PIN."), parent=self.root)
        return None

    def _void_order(self):
        oid = simpledialog.askstring(_t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.dialogs.void', default="Void"), _t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.dialogs.order_id_to_void', default="Order ID to void:"),
                                     parent=self.root)
        if not oid:
            return
        mgr = self._verify_manager_pin()
        if not mgr:
            return
        reason = simpledialog.askstring(_t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.dialogs.void', default="Void"), _t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.dialogs.reason', default="Reason:"), parent=self.root) or ""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT total FROM bakery_orders WHERE order_id=?",
                (oid,)).fetchone()
            amt = (row[0] if row else 0.0) or 0.0
            conn.execute(
                "UPDATE bakery_orders SET refunded=1, refund_ref=?, "
                "refund_timestamp=? WHERE order_id=?",
                (f"VOID-{mgr}", now, oid))
            conn.execute(
                "INSERT INTO bakery_void_audit "
                "(order_id, action, amount, reason, manager, operator, "
                "timestamp) VALUES (?,?,?,?,?,?,?)",
                (oid, "void", amt, reason, mgr,
                 self.current_user or "system", now))
            conn.commit()
        finally:
            conn.close()
        self._void_refresh()

    def _quick_refund(self):
        oid = simpledialog.askstring(_t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.dialogs.quick_refund', default="Quick refund"), _t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.dialogs.order_id', default="Order ID:"),
                                     parent=self.root)
        if not oid:
            return
        amt = simpledialog.askfloat(_t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.dialogs.quick_refund', default="Quick refund"), _t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.dialogs.amount', default="Amount £:"),
                                    minvalue=0.01, parent=self.root)
        if not amt:
            return
        mgr = self._verify_manager_pin()
        if not mgr:
            return
        reason = simpledialog.askstring(_t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.dialogs.quick_refund', default="Quick refund"), _t('gui.operations.commerce.bakery_shop.pos.panels.void_refund.dialogs.reason', default="Reason:"),
                                        parent=self.root) or ""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO bakery_void_audit "
                "(order_id, action, amount, reason, manager, operator, "
                "timestamp) VALUES (?,?,?,?,?,?,?)",
                (oid, "quick_refund", amt, reason, mgr,
                 self.current_user or "system", now))
            conn.commit()
        finally:
            conn.close()
        self._void_refresh()

