
from education_system.systems.university.infrastructure.i18n import get_text as _t
from ..context import *  # noqa: F401,F403


class CateringTraysPanelMixin:
    def _build_catering_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.catering_trays.buttons.add_tray', default="+ Add tray"), command=self._tray_add,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.catering_trays.buttons.quick_add_to_cart', default="🛒 Quick-add to cart"), command=self._tray_to_cart,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.catering_trays.buttons.disable', default="✖ Disable"), command=lambda: self._tray_toggle(0),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.catering_trays.buttons.enable', default="✓ Enable"), command=lambda: self._tray_toggle(1),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.catering_trays.buttons.refresh', default="↻ Refresh"), command=self._catering_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        cols = ("id", "name", "serves", "items", "price", "active")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c, h, w in [("id", "ID", 50), ("name", "Tray", 180),
                        ("serves", "Serves", 70), ("items", "Items", 400),
                        ("price", "Price", 90), ("active", "Active", 70)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._catering_tree = tv
        self._catering_refresh()

    def _catering_refresh(self):
        tv = self._catering_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, name, serves, items_json, price, active "
                "FROM bakery_catering_trays ORDER BY id DESC").fetchall()
        finally:
            conn.close()
        for rid, n, sv, items, price, active in rows:
            try:
                d = json.loads(items)
                desc = ", ".join(f"{k}×{v}" for k, v in d.items())
            except Exception:
                desc = items or ""
            tv.insert("", "end", iid=str(rid),
                      values=(rid, n, sv or "", desc,
                              f"£{(price or 0):.2f}",
                              "yes" if active else "no"))

    def _tray_add(self):
        names = self._all_product_names()
        d = tk.Toplevel(self.root); d.title(_t('gui.operations.commerce.bakery_shop.pos.panels.catering_trays.windows.new_catering_tray', default="New catering tray"))
        d.transient(self.root); d.grab_set(); d.geometry("520x500")
        tk.Label(d, text=_t('gui.operations.commerce.bakery_shop.pos.panels.catering_trays.labels.tray_name', default="Tray name:")).grid(row=0, column=0, padx=8, pady=6, sticky="e")
        n_var = tk.StringVar(value=_t('gui.operations.commerce.bakery_shop.pos.panels.catering_trays.values.mixed_pastry_tray_12', default="Mixed Pastry Tray (12)"))
        tk.Entry(d, textvariable=n_var, width=30).grid(row=0, column=1, padx=8, pady=6)
        tk.Label(d, text=_t('gui.operations.commerce.bakery_shop.pos.panels.catering_trays.labels.serves', default="Serves:")).grid(row=1, column=0, padx=8, pady=6, sticky="e")
        s_var = tk.StringVar(value="12")
        tk.Entry(d, textvariable=s_var, width=8).grid(row=1, column=1, padx=8, pady=6, sticky="w")
        tk.Label(d, text=_t('gui.operations.commerce.bakery_shop.pos.panels.catering_trays.labels.price', default="Price £:")).grid(row=2, column=0, padx=8, pady=6, sticky="e")
        p_var = tk.StringVar(value="30.00")
        tk.Entry(d, textvariable=p_var, width=10).grid(row=2, column=1, padx=8, pady=6, sticky="w")
        tk.Label(d, text=_t('gui.operations.commerce.bakery_shop.pos.panels.catering_trays.labels.items', default="Items:")).grid(row=3, column=0, padx=8, pady=6, sticky="ne")
        f = tk.Frame(d); f.grid(row=3, column=1, padx=8, pady=6, sticky="w")
        rows_v = []
        def add_row():
            r = len(rows_v)
            iv = tk.StringVar(value=names[0]); qv = tk.StringVar(value="2")
            ttk.Combobox(f, textvariable=iv, values=names, state="readonly",
                         width=22).grid(row=r, column=0, padx=2)
            tk.Entry(f, textvariable=qv, width=4).grid(row=r, column=1, padx=2)
            rows_v.append((iv, qv))
        for _ in range(4):
            add_row()
        tk.Button(d, text=_t('gui.operations.commerce.bakery_shop.pos.panels.catering_trays.buttons.row', default="+ row"), command=add_row,
                  relief="flat").grid(row=4, column=1, sticky="w", padx=8)
        def save():
            try:
                serves = int(s_var.get()); price = float(p_var.get())
            except ValueError:
                messagebox.showerror(_t('gui.operations.commerce.bakery_shop.pos.panels.catering_trays.dialogs.tray', default="Tray"), _t('gui.operations.commerce.bakery_shop.pos.panels.catering_trays.dialogs.numeric', default="Numeric."), parent=d); return
            items = {}
            for iv, qv in rows_v:
                try:
                    q = int(qv.get())
                except ValueError:
                    continue
                if q > 0:
                    items[iv.get()] = items.get(iv.get(), 0) + q
            if not items:
                messagebox.showerror(_t('gui.operations.commerce.bakery_shop.pos.panels.catering_trays.dialogs.tray', default="Tray"), _t('gui.operations.commerce.bakery_shop.pos.panels.catering_trays.dialogs.add_items', default="Add items."), parent=d); return
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO bakery_catering_trays "
                    "(name, description, items_json, serves, price, active, "
                    "created_at) VALUES (?,?,?,?,?,1,?)",
                    (n_var.get(), "", json.dumps(items), serves, price, now))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._catering_refresh()
        tk.Button(d, text=_t('gui.operations.commerce.bakery_shop.pos.panels.catering_trays.buttons.save', default="Save"), command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).grid(row=5, column=0, columnspan=2, pady=12)

    def _tray_to_cart(self):
        sel = self._catering_tree.focus()
        if not sel:
            return
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT items_json FROM bakery_catering_trays WHERE id=?",
                (int(sel),)).fetchone()
        finally:
            conn.close()
        if not row:
            return
        try:
            items = json.loads(row[0])
        except Exception:
            return
        for it, q in items.items():
            self.cart[it] = self.cart.get(it, 0) + q
        try:
            self.refresh_cart(); self.update_cart_tab_title()
        except Exception:
            pass
        self.set_status("Catering tray added to cart.")

    def _tray_toggle(self, active):
        sel = self._catering_tree.focus()
        if not sel:
            return
        conn = self._connect()
        try:
            conn.execute("UPDATE bakery_catering_trays SET active=? WHERE id=?",
                         (active, int(sel)))
            conn.commit()
        finally:
            conn.close()
        self._catering_refresh()

