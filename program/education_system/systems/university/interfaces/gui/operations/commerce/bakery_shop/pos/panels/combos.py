
from education_system.systems.university.infrastructure.i18n import get_text as _t
from ..context import *  # noqa: F401,F403


class CombosPanelMixin:
    def _build_combos_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.combos.buttons.add_combo', default="+ Add combo"), command=self._combo_add,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.combos.buttons.disable', default="✖ Disable"), command=lambda: self._combo_toggle(0),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.combos.buttons.enable', default="✓ Enable"), command=lambda: self._combo_toggle(1),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.combos.buttons.refresh', default="↻ Refresh"), command=self._combos_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        cols = ("id", "name", "items", "price", "active")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c, h, w in [("id", "ID", 60), ("name", "Name", 200),
                        ("items", "Items", 380), ("price", "Combo £", 100),
                        ("active", "Active", 70)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._combos_tree = tv
        self._combos_refresh()

    def _combos_refresh(self):
        tv = self._combos_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, name, items_json, combo_price, active "
                "FROM bakery_combos ORDER BY id DESC").fetchall()
        finally:
            conn.close()
        for rid, n, items, price, active in rows:
            try:
                d = json.loads(items)
                desc = ", ".join(f"{k}×{v}" for k, v in d.items())
            except Exception:
                desc = items or ""
            tv.insert("", "end", iid=str(rid),
                      values=(rid, n, desc, f"£{(price or 0):.2f}",
                              "yes" if active else "no"))

    def _combo_add(self):
        names = self._all_product_names()
        d = tk.Toplevel(self.root); d.title(_t('gui.operations.commerce.bakery_shop.pos.panels.combos.windows.new_combo', default="New combo"))
        d.transient(self.root); d.grab_set(); d.geometry("520x440")
        tk.Label(d, text=_t('gui.operations.commerce.bakery_shop.pos.panels.combos.labels.name', default="Name:")).grid(row=0, column=0, padx=8, pady=6, sticky="e")
        n_var = tk.StringVar(value=_t('gui.operations.commerce.bakery_shop.pos.panels.combos.values.coffee_pastry', default="Coffee + Pastry"))
        tk.Entry(d, textvariable=n_var, width=30).grid(row=0, column=1, padx=8, pady=6)
        tk.Label(d, text=_t('gui.operations.commerce.bakery_shop.pos.panels.combos.labels.price', default="Price £:")).grid(row=1, column=0, padx=8, pady=6, sticky="e")
        p_var = tk.StringVar(value="4.50")
        tk.Entry(d, textvariable=p_var, width=10).grid(row=1, column=1, padx=8, pady=6, sticky="w")
        tk.Label(d, text=_t('gui.operations.commerce.bakery_shop.pos.panels.combos.labels.items', default="Items:")).grid(row=2, column=0, padx=8, pady=6, sticky="ne")
        items_frame = tk.Frame(d); items_frame.grid(row=2, column=1, padx=8, pady=6, sticky="w")
        items_vars = []
        def add_row():
            r = len(items_vars)
            iv = tk.StringVar(value=names[0])
            qv = tk.StringVar(value="1")
            ttk.Combobox(items_frame, textvariable=iv, values=names,
                         state="readonly", width=22).grid(row=r, column=0, padx=2)
            tk.Entry(items_frame, textvariable=qv, width=4).grid(row=r, column=1, padx=2)
            items_vars.append((iv, qv))
        add_row(); add_row()
        tk.Button(d, text=_t('gui.operations.commerce.bakery_shop.pos.panels.combos.buttons.row', default="+ row"), command=add_row,
                  relief="flat").grid(row=3, column=1, sticky="w", padx=8)
        def save():
            try:
                price = float(p_var.get())
            except ValueError:
                messagebox.showerror(_t('gui.operations.commerce.bakery_shop.pos.panels.combos.dialogs.combo', default="Combo"), _t('gui.operations.commerce.bakery_shop.pos.panels.combos.dialogs.bad_price', default="Bad price."), parent=d); return
            items = {}
            for iv, qv in items_vars:
                try:
                    q = int(qv.get())
                except ValueError:
                    continue
                if q > 0:
                    items[iv.get()] = items.get(iv.get(), 0) + q
            if not items:
                messagebox.showerror(_t('gui.operations.commerce.bakery_shop.pos.panels.combos.dialogs.combo', default="Combo"), _t('gui.operations.commerce.bakery_shop.pos.panels.combos.dialogs.no_items', default="No items."), parent=d); return
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_combos "
                    "(name, items_json, combo_price, active, created_at) "
                    "VALUES (?,?,?,1,?)",
                    (n_var.get(), json.dumps(items), price, now))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._combos_refresh()
        tk.Button(d, text=_t('gui.operations.commerce.bakery_shop.pos.panels.combos.buttons.save', default="Save"), command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).grid(row=4, column=0, columnspan=2, pady=12)

    def _combo_toggle(self, active):
        sel = self._combos_tree.focus()
        if not sel:
            return
        conn = self._connect()
        try:
            conn.execute("UPDATE bakery_combos SET active=? WHERE id=?",
                         (active, int(sel)))
            conn.commit()
        finally:
            conn.close()
        self._combos_refresh()

