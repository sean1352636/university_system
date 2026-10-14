
from education_system.systems.university.infrastructure.i18n import get_text as _t
from ..context import *  # noqa: F401,F403


class LoyaltyStampsPanelMixin:
    def _build_stamps_panel(self, parent):
        bg = self.colors["background"]
        tk.Label(parent,
                 text=_t('gui.operations.commerce.bakery_shop.pos.panels.loyalty_stamps.labels.loyalty_stamp_cards_buy_9_in_a_category_10th_free', default="Loyalty stamp cards — buy 9 in a category, 10th free."),
                 bg=bg, font=("Arial", 11, "italic")).pack(anchor="w",
                                                            padx=12, pady=6)
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.loyalty_stamps.buttons.add_stamp', default="+ Add stamp"), command=self._stamp_add,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.loyalty_stamps.buttons.redeem_free', default="🎁 Redeem free"), command=self._stamp_redeem,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.loyalty_stamps.buttons.refresh', default="↻ Refresh"), command=self._stamps_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)

        cols = ("user", "category", "count", "redemptions", "progress", "updated")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=16)
        for c, h, w in [("user", "User", 130), ("category", "Category", 130),
                        ("count", "Stamps", 80), ("redemptions", "Free claimed", 110),
                        ("progress", "Progress", 200),
                        ("updated", "Updated", 150)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._stamps_tree = tv
        self._stamps_refresh()

    def _stamps_refresh(self):
        tv = self._stamps_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT user, category, count, redemptions, updated_at "
                "FROM bakery_punch_cards ORDER BY user, category"
            ).fetchall()
        finally:
            conn.close()
        for u, c, cnt, red, upd in rows:
            pos = (cnt or 0) % 10
            bar = "●" * pos + "○" * (10 - pos)
            tv.insert("", "end", values=(u, c, cnt, red or 0, bar, upd or ""))

    def _stamp_add(self):
        u = simpledialog.askstring(_t('gui.operations.commerce.bakery_shop.pos.panels.loyalty_stamps.dialogs.stamp', default="Stamp"), _t('gui.operations.commerce.bakery_shop.pos.panels.loyalty_stamps.dialogs.user', default="User:"), parent=self.root,
                                   initialvalue=self.current_user or "")
        if not u:
            return
        cats = list(self.products.keys())
        d = tk.Toplevel(self.root); d.title(_t('gui.operations.commerce.bakery_shop.pos.panels.loyalty_stamps.windows.add_stamp', default="Add stamp"))
        d.transient(self.root); d.grab_set()
        tk.Label(d, text=_t('gui.operations.commerce.bakery_shop.pos.panels.loyalty_stamps.labels.category', default="Category:")).grid(row=0, column=0, padx=8, pady=8, sticky="e")
        c_var = tk.StringVar(value=cats[0])
        ttk.Combobox(d, textvariable=c_var, values=cats, state="readonly",
                     width=20).grid(row=0, column=1, padx=8, pady=8)
        def save():
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_punch_cards (user, category, count, "
                    "redemptions, updated_at) VALUES (?,?,1,0,?) "
                    "ON CONFLICT(user, category) DO UPDATE SET "
                    "count = count + 1, updated_at=excluded.updated_at",
                    (u, c_var.get(), now))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._stamps_refresh()
        tk.Button(d, text=_t('gui.operations.commerce.bakery_shop.pos.panels.loyalty_stamps.buttons.save', default="Save"), command=save, bg=self.colors["primary"],
                  fg="white", relief="flat", padx=14).grid(row=1, column=0,
                                                            columnspan=2, pady=10)

    def _stamp_redeem(self):
        sel = self._stamps_tree.focus()
        if not sel:
            return
        u, c, cnt, *_ = self._stamps_tree.item(sel, "values")
        cnt = int(cnt)
        if cnt < 10:
            messagebox.showinfo(_t('gui.operations.commerce.bakery_shop.pos.panels.loyalty_stamps.dialogs.redeem', default="Redeem"),
                                f"{u}/{c} has only {cnt} stamps — need 10.",
                                parent=self.root); return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute("UPDATE bakery_punch_cards SET count = count - 10, "
                         "redemptions = redemptions + 1, updated_at=? "
                         "WHERE user=? AND category=?", (now, u, c))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo(_t('gui.operations.commerce.bakery_shop.pos.panels.loyalty_stamps.dialogs.redeem', default="Redeem"), f"Free {c} item issued to {u}.",
                            parent=self.root)
        self._stamps_refresh()

