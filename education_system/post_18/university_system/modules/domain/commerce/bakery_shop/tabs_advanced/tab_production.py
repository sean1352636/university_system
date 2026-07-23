"""ProductionTabMixin — auto-split from bakery_shop.py."""
from education_system.post_18.university_system.modules.domain.commerce.bakery_shop._common import *  # noqa: F401,F403


class ProductionTabMixin:
    WASTE_REASONS = ["burnt", "dropped", "expired", "sampled", "deformed", "other"]

    def build_production_tab(self):
        panels = [
            ("📅 Daily Planner",     self._build_planner_panel),
            ("📜 Recipes / BOM",     self._build_bom_panel),
            ("⚠️ Allergen Matrix",   self._build_allergen_panel),
            ("🌾 Ingredient Stock",  self._build_ingredient_stock_panel),
            ("⏳ FEFO Expiry",       self._build_fefo_panel),
            ("🗑️ Waste Log",         self._build_waste_panel),
            ("📐 Yield Variance",    self._build_yield_panel),
            ("⏲️ Oven Timers",       self._build_timer_panel),
            ("🥖 Sourdough",         self._build_starter_panel),
            ("🔁 Substitutions",     self._build_substitution_panel),
        ]
        sub, self._prod_panels = self._lazy_subnotebook(
            self.production_tab, panels, "Production")
        self.production_sub = sub

        # Tick oven timers once a second to update countdowns.
        self._timer_tick_scheduled = False
        self._schedule_timer_tick()

    def _build_planner_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Label(top, text="Plan for:", bg=bg, font=("Arial", 11, "bold")).pack(side="left")
        self._planner_date = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        tk.Entry(top, textvariable=self._planner_date, width=12).pack(side="left", padx=5)
        tk.Button(top, text="Auto-forecast from last 7d sales",
                  command=self._planner_autoforecast,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=8)
        tk.Button(top, text="Save plan", command=self._planner_save_plan,
                  bg=self.colors["accent"], relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="Commit (record planned bakes)",
                  command=self._planner_commit,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)

        cols = ("item", "category", "forecast", "batch_size", "batches", "planned_qty")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        headers = {"item": "Item", "category": "Category", "forecast": "Forecast",
                   "batch_size": "Batch size", "batches": "Batches",
                   "planned_qty": "Planned qty"}
        for c in cols:
            tv.heading(c, text=headers[c])
            tv.column(c, width=130, anchor="center")
        tv.column("item", width=180, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=8)
        self._planner_tree = tv
        tv.bind("<Double-1>", self._planner_edit_forecast)

        self._planner_forecasts = {}
        self._planner_refresh()

    def _planner_default_forecast(self, item):
        # 60% of current stock as a starting baseline
        for cat, items in self.products.items():
            if item in items:
                return max(0, int(round(items[item].get("stock", 0) * 0.6)))
        return 0

    def _planner_refresh(self):
        tv = self._planner_tree
        tv.delete(*tv.get_children())
        for cat, items in self.products.items():
            for item in items:
                forecast = self._planner_forecasts.get(item,
                                                       self._planner_default_forecast(item))
                bs = self._prod_batch_size(item)
                batches = (forecast + bs - 1) // bs if forecast > 0 else 0
                planned = batches * bs
                tv.insert("", "end", iid=item, values=(item, cat, forecast,
                                                       bs, batches, planned))

    def _planner_edit_forecast(self, _evt):
        tv = self._planner_tree
        sel = tv.focus()
        if not sel:
            return
        cur = self._planner_forecasts.get(sel, self._planner_default_forecast(sel))
        new = simpledialog.askinteger("Forecast qty",
                                      f"Forecast units of {sel}:",
                                      initialvalue=cur, minvalue=0,
                                      parent=self.root)
        if new is None:
            return
        self._planner_forecasts[sel] = new
        self._planner_refresh()

    def _planner_autoforecast(self):
        # Average daily sales from last 7 days of orders → forecast.
        cutoff = (datetime.now() - timedelta(days=7))
        sold = {}
        for o in self.orders:
            try:
                ts = datetime.strptime(o["timestamp"], "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            if ts < cutoff:
                continue
            for it, info in (o.get("items") or {}).items():
                q = info.get("quantity", 0) if isinstance(info, dict) else int(info)
                sold[it] = sold.get(it, 0) + q
        for item, total in sold.items():
            self._planner_forecasts[item] = max(1, int(round(total / 7.0)))
        if not sold:
            messagebox.showinfo("Forecast",
                                "No sales in the last 7 days — using defaults.",
                                parent=self.root)
        self._planner_refresh()
        self.set_status("Production forecast updated from sales history.")

    def _planner_save_plan(self):
        date = self._planner_date.get().strip()
        if not date:
            messagebox.showerror("Plan", "Pick a date.", parent=self.root); return
        conn = self._connect()
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for item, forecast in self._planner_forecasts.items():
                bs = self._prod_batch_size(item)
                batches = (forecast + bs - 1) // bs if forecast > 0 else 0
                planned = batches * bs
                conn.execute(
                    "INSERT INTO bakery_production_plans "
                    "(plan_date, item_name, forecast_qty, batch_size, "
                    "planned_batches, planned_qty, created_by, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(plan_date, item_name) DO UPDATE SET "
                    "forecast_qty=excluded.forecast_qty, "
                    "batch_size=excluded.batch_size, "
                    "planned_batches=excluded.planned_batches, "
                    "planned_qty=excluded.planned_qty",
                    (date, item, forecast, bs, batches, planned,
                     self.current_user or "system", now),
                )
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo("Plan",
                            f"Saved production plan for {date}.",
                            parent=self.root)

    def _planner_commit(self):
        """Push planned quantities into FEFO expiry batches (per item)."""
        date = self._planner_date.get().strip() or datetime.now().strftime("%Y-%m-%d")
        bake_dt = datetime.now().strftime("%Y-%m-%d")
        conn = self._connect()
        n = 0
        try:
            for item in self._all_product_names():
                forecast = self._planner_forecasts.get(item)
                if forecast is None:
                    continue
                bs = self._prod_batch_size(item)
                batches = (forecast + bs - 1) // bs if forecast > 0 else 0
                planned = batches * bs
                if planned <= 0:
                    continue
                shelf = self._prod_shelf_life(item)
                expiry = (datetime.now() + timedelta(days=shelf)).strftime("%Y-%m-%d")
                conn.execute(
                    "INSERT INTO bakery_product_expiry "
                    "(item_name, quantity, bake_date, expiry_date, "
                    "shelf_life_days, status, notes) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (item, planned, bake_dt, expiry, shelf, "fresh",
                     f"Plan {date}"),
                )
                n += 1
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo("Commit",
                            f"Recorded {n} fresh bake batches into FEFO.",
                            parent=self.root)
        if hasattr(self, "_fefo_tree"):
            self._fefo_refresh()

    def _build_bom_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Label(top, text="Product:", bg=bg, font=("Arial", 11, "bold")).pack(side="left")
        self._bom_product = tk.StringVar()
        cb = ttk.Combobox(top, textvariable=self._bom_product,
                          values=self._all_product_names(), width=28,
                          state="readonly")
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda _e: self._bom_refresh())
        tk.Button(top, text="Add ingredient", command=self._bom_add,
                  bg=self.colors["accent"], relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="Remove selected", command=self._bom_remove,
                  relief="flat", padx=10).pack(side="left", padx=4)

        cols = ("ingredient", "unit", "qty_per_unit", "unit_cost", "line_cost")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c, h, w in [("ingredient", "Ingredient", 200),
                        ("unit", "Unit", 80),
                        ("qty_per_unit", "Qty / product", 120),
                        ("unit_cost", "Unit cost", 120),
                        ("line_cost", "Line cost", 120)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="center")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._bom_tree = tv

        self._bom_total_lbl = tk.Label(parent, text="",
                                       font=("Arial", 12, "bold"),
                                       bg=bg, fg=self.colors["text"])
        self._bom_total_lbl.pack(anchor="e", padx=14, pady=6)

        if self._all_product_names():
            self._bom_product.set(self._all_product_names()[0])
            self._bom_refresh()

    def _bom_refresh(self):
        tv = self._bom_tree
        tv.delete(*tv.get_children())
        item = self._bom_product.get()
        if not item:
            self._bom_total_lbl.config(text=""); return
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT r.ingredient, i.unit, r.quantity, i.unit_cost "
                "FROM bakery_recipes r LEFT JOIN bakery_ingredients i "
                "ON r.ingredient = i.name WHERE r.item_name = ? "
                "ORDER BY r.ingredient", (item,),
            ).fetchall()
        finally:
            conn.close()
        total = 0.0
        for ing, unit, qty, ucost in rows:
            ucost = ucost or 0.0
            line = (qty or 0) * ucost
            total += line
            tv.insert("", "end", values=(ing, unit or "?", f"{qty:g}",
                                         f"£{ucost:.4f}", f"£{line:.4f}"))
        sell_price = 0.0
        for cat, items in self.products.items():
            if item in items:
                sell_price = items[item].get("price", 0.0)
                break
        margin = sell_price - total
        margin_pct = (margin / sell_price * 100) if sell_price else 0
        self._bom_total_lbl.config(
            text=f"Ingredient cost: £{total:.3f}   "
                 f"Sell: £{sell_price:.2f}   "
                 f"Margin: £{margin:.2f}  ({margin_pct:.1f}%)"
        )

    def _bom_add(self):
        item = self._bom_product.get()
        if not item:
            return
        conn = self._connect()
        try:
            ings = [r[0] for r in conn.execute(
                "SELECT name FROM bakery_ingredients ORDER BY name").fetchall()]
        finally:
            conn.close()
        if not ings:
            messagebox.showinfo("BOM", "No ingredients defined.", parent=self.root); return
        d = tk.Toplevel(self.root); d.title("Add ingredient")
        d.transient(self.root); d.grab_set()
        tk.Label(d, text="Ingredient:").grid(row=0, column=0, padx=8, pady=6, sticky="e")
        ing_var = tk.StringVar(value=ings[0])
        ttk.Combobox(d, textvariable=ing_var, values=ings, state="readonly",
                     width=24).grid(row=0, column=1, padx=8, pady=6)
        tk.Label(d, text="Qty / product:").grid(row=1, column=0, padx=8, pady=6, sticky="e")
        qty_var = tk.StringVar(value="0")
        tk.Entry(d, textvariable=qty_var, width=10).grid(row=1, column=1, padx=8, pady=6, sticky="w")
        def save():
            try:
                qty = float(qty_var.get())
            except ValueError:
                messagebox.showerror("BOM", "Qty must be numeric.", parent=d); return
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_recipes (item_name, ingredient, quantity) "
                    "VALUES (?,?,?) ON CONFLICT(item_name, ingredient) "
                    "DO UPDATE SET quantity = excluded.quantity",
                    (item, ing_var.get(), qty),
                )
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._bom_refresh()
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat", padx=12).grid(row=2, column=0,
                                                            columnspan=2, pady=10)

    def _bom_remove(self):
        item = self._bom_product.get()
        sel = self._bom_tree.focus()
        if not item or not sel:
            return
        ing = self._bom_tree.item(sel, "values")[0]
        if not messagebox.askyesno("BOM", f"Remove {ing} from {item}?",
                                   parent=self.root):
            return
        conn = self._connect()
        try:
            conn.execute("DELETE FROM bakery_recipes "
                         "WHERE item_name=? AND ingredient=?", (item, ing))
            conn.commit()
        finally:
            conn.close()
        self._bom_refresh()

    def _build_allergen_panel(self, parent):
        bg = self.colors["background"]
        info = tk.Label(parent,
                        text="Allergen presence per product "
                             "(rolled up from BOM ingredients + product tags).",
                        bg=bg, font=("Arial", 10, "italic"))
        info.pack(anchor="w", padx=10, pady=6)
        tk.Button(parent, text="Refresh",
                  command=self._allergen_refresh, relief="flat",
                  bg=self.colors["accent"]).pack(anchor="e", padx=10)

        self._allergen_tree_frame = tk.Frame(parent, bg=bg)
        self._allergen_tree_frame.pack(fill="both", expand=True, padx=10, pady=6)
        self._allergen_refresh()

    def _allergen_refresh(self):
        from tkinter import ttk as _ttk
        for w in self._allergen_tree_frame.winfo_children():
            w.destroy()

        # Build canonical allergen list from products + ingredient table.
        allergens = set()
        for cat, items in self.products.items():
            for it, meta in items.items():
                for a in meta.get("allergens", []):
                    allergens.add(a)
        conn = self._connect()
        try:
            for (a_csv,) in conn.execute(
                "SELECT allergens FROM bakery_ingredients").fetchall():
                if a_csv:
                    for a in a_csv.split(","):
                        a = a.strip()
                        if a: allergens.add(a)
            ing_allerg = {n: (a or "").split(",") if a else []
                          for n, a in conn.execute(
                              "SELECT name, allergens FROM bakery_ingredients"
                          ).fetchall()}
            bom_map = {}
            for it, ing in conn.execute(
                "SELECT item_name, ingredient FROM bakery_recipes").fetchall():
                bom_map.setdefault(it, []).append(ing)
        finally:
            conn.close()

        allergens = sorted(allergens)
        cols = ["item"] + allergens
        tv = _ttk.Treeview(self._allergen_tree_frame,
                           columns=cols, show="headings", height=18)
        tv.heading("item", text="Item"); tv.column("item", width=180, anchor="w")
        for a in allergens:
            tv.heading(a, text=a)
            tv.column(a, width=80, anchor="center")
        tv.pack(fill="both", expand=True)
        for cat, items in self.products.items():
            for it, meta in items.items():
                present = set(meta.get("allergens", []))
                for ing in bom_map.get(it, []):
                    for a in ing_allerg.get(ing, []):
                        a = a.strip()
                        if a: present.add(a)
                row = [it] + ["●" if a in present else "" for a in allergens]
                tv.insert("", "end", values=row)

    def _build_ingredient_stock_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="+ Receive stock", command=self._ing_receive,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="✎ Edit reorder level", command=self._ing_edit_reorder,
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._ingredient_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        self._ing_alert_lbl = tk.Label(top, text="", bg=bg,
                                       fg="#B00020", font=("Arial", 10, "bold"))
        self._ing_alert_lbl.pack(side="left", padx=14)

        cols = ("name", "unit", "stock", "reorder_level", "unit_cost", "value", "status")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c, h, w in [("name", "Ingredient", 180), ("unit", "Unit", 70),
                        ("stock", "Stock", 110), ("reorder_level", "Reorder lvl", 110),
                        ("unit_cost", "Unit cost", 110), ("value", "Stock value", 120),
                        ("status", "Status", 100)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="center")
        tv.column("name", anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._ing_tree = tv
        self._ingredient_refresh()

    def _ingredient_refresh(self):
        tv = self._ing_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT name, unit, stock, reorder_level, unit_cost "
                "FROM bakery_ingredients ORDER BY name").fetchall()
        finally:
            conn.close()
        alerts = 0
        for name, unit, stock, reorder, ucost in rows:
            stock = stock or 0; reorder = reorder or 0; ucost = ucost or 0
            value = stock * ucost
            status = "OK"
            tag = ""
            if stock <= 0:
                status = "OUT"; tag = "out"; alerts += 1
            elif stock < reorder:
                status = "LOW"; tag = "low"; alerts += 1
            tv.insert("", "end", values=(name, unit, f"{stock:g}",
                                         f"{reorder:g}", f"£{ucost:.4f}",
                                         f"£{value:.2f}", status), tags=(tag,))
        tv.tag_configure("low", background="#FFF2CC")
        tv.tag_configure("out", background="#FFD9D9")
        self._ing_alert_lbl.config(
            text=(f"⚠ {alerts} ingredient(s) at/under reorder level"
                  if alerts else ""))

    def _ing_receive(self):
        sel = self._ing_tree.focus()
        ing = self._ing_tree.item(sel, "values")[0] if sel else None
        conn = self._connect()
        try:
            names = [r[0] for r in conn.execute(
                "SELECT name FROM bakery_ingredients ORDER BY name").fetchall()]
        finally:
            conn.close()
        if not names:
            return
        d = tk.Toplevel(self.root); d.title("Receive stock")
        d.transient(self.root); d.grab_set()
        tk.Label(d, text="Ingredient:").grid(row=0, column=0, padx=8, pady=6, sticky="e")
        ing_var = tk.StringVar(value=ing or names[0])
        ttk.Combobox(d, textvariable=ing_var, values=names, state="readonly",
                     width=24).grid(row=0, column=1, padx=8, pady=6)
        tk.Label(d, text="Qty received:").grid(row=1, column=0, padx=8, pady=6, sticky="e")
        qty_var = tk.StringVar(value="0")
        tk.Entry(d, textvariable=qty_var, width=12).grid(row=1, column=1, padx=8, pady=6, sticky="w")
        def save():
            try:
                qty = float(qty_var.get())
            except ValueError:
                messagebox.showerror("Receive", "Qty must be numeric.", parent=d); return
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                conn.execute("UPDATE bakery_ingredients "
                             "SET stock = COALESCE(stock,0) + ?, updated_at=? "
                             "WHERE name=?", (qty, now, ing_var.get()))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._ingredient_refresh()
        tk.Button(d, text="Receive", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat", padx=14).grid(row=2, column=0,
                                                            columnspan=2, pady=10)

    def _ing_edit_reorder(self):
        sel = self._ing_tree.focus()
        if not sel:
            messagebox.showinfo("Reorder", "Select an ingredient first.",
                                parent=self.root); return
        ing = self._ing_tree.item(sel, "values")[0]
        cur = float(self._ing_tree.item(sel, "values")[3])
        new = simpledialog.askfloat("Reorder level",
                                    f"Reorder level for {ing}:",
                                    initialvalue=cur, minvalue=0,
                                    parent=self.root)
        if new is None:
            return
        conn = self._connect()
        try:
            conn.execute("UPDATE bakery_ingredients SET reorder_level=? "
                         "WHERE name=?", (new, ing))
            conn.commit()
        finally:
            conn.close()
        self._ingredient_refresh()

    def _build_fefo_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="+ Record bake batch", command=self._fefo_add,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="Mark sold-through",
                  command=lambda: self._fefo_set_status("sold-through"),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="Mark expired (→ waste)",
                  command=self._fefo_mark_expired,
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._fefo_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)

        cols = ("id", "item", "qty", "bake_date", "expiry", "shelf", "status")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c, h, w in [("id", "ID", 60), ("item", "Item", 180),
                        ("qty", "Qty", 80), ("bake_date", "Baked", 110),
                        ("expiry", "Expires", 110), ("shelf", "Shelf (d)", 80),
                        ("status", "Status", 110)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="center")
        tv.column("item", anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._fefo_tree = tv
        self._fefo_refresh()

    def _fefo_refresh(self):
        tv = self._fefo_tree
        tv.delete(*tv.get_children())
        today = datetime.now().strftime("%Y-%m-%d")
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, item_name, quantity, bake_date, expiry_date, "
                "shelf_life_days, status FROM bakery_product_expiry "
                "ORDER BY expiry_date ASC, id ASC").fetchall()
        finally:
            conn.close()
        for rid, item, qty, baked, expiry, shelf, status in rows:
            tag = ""
            if status == "fresh":
                if expiry <= today:
                    tag = "expired"
                elif expiry == today:
                    tag = "today"
            elif status == "expired":
                tag = "expired"
            tv.insert("", "end", iid=str(rid),
                      values=(rid, item, qty, baked, expiry, shelf or "", status),
                      tags=(tag,))
        tv.tag_configure("today", background="#FFF2CC")
        tv.tag_configure("expired", background="#FFD9D9")

    def _fefo_add(self):
        names = self._all_product_names()
        if not names:
            return
        d = tk.Toplevel(self.root); d.title("Record bake batch")
        d.transient(self.root); d.grab_set()
        tk.Label(d, text="Item:").grid(row=0, column=0, padx=8, pady=6, sticky="e")
        item_var = tk.StringVar(value=names[0])
        cb = ttk.Combobox(d, textvariable=item_var, values=names,
                          state="readonly", width=28)
        cb.grid(row=0, column=1, padx=8, pady=6)
        tk.Label(d, text="Qty:").grid(row=1, column=0, padx=8, pady=6, sticky="e")
        qty_var = tk.StringVar(value="12")
        tk.Entry(d, textvariable=qty_var, width=10).grid(row=1, column=1, padx=8, pady=6, sticky="w")
        tk.Label(d, text="Shelf life (days):").grid(row=2, column=0, padx=8, pady=6, sticky="e")
        shelf_var = tk.StringVar(value=str(self._prod_shelf_life(names[0])))
        tk.Entry(d, textvariable=shelf_var, width=10).grid(row=2, column=1, padx=8, pady=6, sticky="w")
        def on_item_change(_e=None):
            shelf_var.set(str(self._prod_shelf_life(item_var.get())))
        cb.bind("<<ComboboxSelected>>", on_item_change)
        def save():
            try:
                qty = int(qty_var.get()); shelf = int(shelf_var.get())
            except ValueError:
                messagebox.showerror("Batch", "Numeric only.", parent=d); return
            today = datetime.now().strftime("%Y-%m-%d")
            expiry = (datetime.now() + timedelta(days=shelf)).strftime("%Y-%m-%d")
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_product_expiry "
                    "(item_name, quantity, bake_date, expiry_date, "
                    "shelf_life_days, status, notes) VALUES (?,?,?,?,?,?,?)",
                    (item_var.get(), qty, today, expiry, shelf, "fresh", ""),
                )
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._fefo_refresh()
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat", padx=14).grid(row=3, column=0,
                                                            columnspan=2, pady=10)

    def _fefo_set_status(self, status):
        sel = self._fefo_tree.focus()
        if not sel:
            return
        conn = self._connect()
        try:
            conn.execute("UPDATE bakery_product_expiry SET status=? WHERE id=?",
                         (status, int(sel)))
            conn.commit()
        finally:
            conn.close()
        self._fefo_refresh()

    def _fefo_mark_expired(self):
        sel = self._fefo_tree.focus()
        if not sel:
            return
        vals = self._fefo_tree.item(sel, "values")
        item, qty = vals[1], int(vals[2])
        conn = self._connect()
        try:
            conn.execute("UPDATE bakery_product_expiry SET status='expired' "
                         "WHERE id=?", (int(sel),))
            conn.execute(
                "INSERT INTO bakery_waste_log "
                "(timestamp, item_name, quantity, reason_code, cost, notes, logged_by) "
                "VALUES (?,?,?,?,?,?,?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 item, qty, "expired", 0.0, f"FEFO batch #{sel}",
                 self.current_user or "system"),
            )
            conn.commit()
        finally:
            conn.close()
        self._fefo_refresh()
        if hasattr(self, "_waste_tree"):
            self._waste_refresh()

    def _build_waste_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="+ Log waste", command=self._waste_add,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._waste_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        self._waste_summary_lbl = tk.Label(top, text="", bg=bg,
                                           font=("Arial", 10, "bold"))
        self._waste_summary_lbl.pack(side="left", padx=14)

        cols = ("ts", "item", "qty", "reason", "cost", "by", "notes")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c, h, w in [("ts", "When", 140), ("item", "Item", 160),
                        ("qty", "Qty", 70), ("reason", "Reason", 100),
                        ("cost", "Cost", 90), ("by", "By", 110),
                        ("notes", "Notes", 220)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="center")
        tv.column("notes", anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._waste_tree = tv
        self._waste_refresh()

    def _waste_refresh(self):
        tv = self._waste_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT timestamp, item_name, quantity, reason_code, cost, "
                "logged_by, notes FROM bakery_waste_log "
                "ORDER BY timestamp DESC LIMIT 500").fetchall()
            week_ago = (datetime.now() - timedelta(days=7)
                        ).strftime("%Y-%m-%d %H:%M:%S")
            wk_total = conn.execute(
                "SELECT COALESCE(SUM(cost),0), COALESCE(SUM(quantity),0) "
                "FROM bakery_waste_log WHERE timestamp >= ?",
                (week_ago,)).fetchone()
        finally:
            conn.close()
        for ts, item, qty, reason, cost, by, notes in rows:
            tv.insert("", "end", values=(ts, item, qty, reason,
                                         f"£{(cost or 0):.2f}",
                                         by or "", notes or ""))
        self._waste_summary_lbl.config(
            text=f"Last 7 days: {wk_total[1]:g} units · £{wk_total[0]:.2f} waste")

    def _waste_add(self):
        names = self._all_product_names()
        d = tk.Toplevel(self.root); d.title("Log waste")
        d.transient(self.root); d.grab_set()
        tk.Label(d, text="Item:").grid(row=0, column=0, padx=8, pady=6, sticky="e")
        item_var = tk.StringVar(value=names[0] if names else "")
        ttk.Combobox(d, textvariable=item_var, values=names, state="readonly",
                     width=28).grid(row=0, column=1, padx=8, pady=6)
        tk.Label(d, text="Qty:").grid(row=1, column=0, padx=8, pady=6, sticky="e")
        qty_var = tk.StringVar(value="1")
        tk.Entry(d, textvariable=qty_var, width=10).grid(row=1, column=1, padx=8, pady=6, sticky="w")
        tk.Label(d, text="Reason:").grid(row=2, column=0, padx=8, pady=6, sticky="e")
        reason_var = tk.StringVar(value=self.WASTE_REASONS[0])
        ttk.Combobox(d, textvariable=reason_var, values=self.WASTE_REASONS,
                     state="readonly", width=20).grid(row=2, column=1, padx=8, pady=6, sticky="w")
        tk.Label(d, text="Cost (£):").grid(row=3, column=0, padx=8, pady=6, sticky="e")
        cost_var = tk.StringVar(value="0.00")
        tk.Entry(d, textvariable=cost_var, width=10).grid(row=3, column=1, padx=8, pady=6, sticky="w")
        tk.Label(d, text="Notes:").grid(row=4, column=0, padx=8, pady=6, sticky="ne")
        notes_var = tk.StringVar(value="")
        tk.Entry(d, textvariable=notes_var, width=32).grid(row=4, column=1, padx=8, pady=6, sticky="w")
        def save():
            try:
                qty = float(qty_var.get()); cost = float(cost_var.get())
            except ValueError:
                messagebox.showerror("Waste", "Numeric only.", parent=d); return
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_waste_log "
                    "(timestamp, item_name, quantity, reason_code, cost, "
                    "notes, logged_by) VALUES (?,?,?,?,?,?,?)",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                     item_var.get(), qty, reason_var.get(), cost,
                     notes_var.get(), self.current_user or "system"),
                )
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._waste_refresh()
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat", padx=14).grid(row=5, column=0,
                                                            columnspan=2, pady=10)

    def _build_yield_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="+ Record batch", command=self._yield_add,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._yield_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        self._yield_summary_lbl = tk.Label(top, text="", bg=bg,
                                           font=("Arial", 10, "bold"))
        self._yield_summary_lbl.pack(side="left", padx=14)

        cols = ("ts", "item", "expected", "actual", "variance", "pct", "baker", "notes")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c, h, w in [("ts", "When", 140), ("item", "Item", 160),
                        ("expected", "Expected", 90), ("actual", "Actual", 90),
                        ("variance", "Variance", 90), ("pct", "%", 80),
                        ("baker", "Baker", 110), ("notes", "Notes", 200)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="center")
        tv.column("notes", anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._yield_tree = tv
        self._yield_refresh()

    def _yield_refresh(self):
        tv = self._yield_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT timestamp, item_name, expected_qty, actual_qty, "
                "variance, variance_pct, baker, notes FROM bakery_yield_variance "
                "ORDER BY timestamp DESC LIMIT 500").fetchall()
            avg = conn.execute(
                "SELECT AVG(variance_pct) FROM bakery_yield_variance "
                "WHERE timestamp >= ?",
                ((datetime.now() - timedelta(days=30)
                  ).strftime("%Y-%m-%d %H:%M:%S"),)).fetchone()[0]
        finally:
            conn.close()
        for ts, item, exp, act, var, pct, baker, notes in rows:
            tag = "bad" if (pct or 0) < -5 else ("good" if (pct or 0) > 0 else "")
            tv.insert("", "end", values=(ts, item, exp, act, var,
                                         f"{(pct or 0):+.1f}%",
                                         baker or "", notes or ""),
                      tags=(tag,))
        tv.tag_configure("bad", background="#FFD9D9")
        tv.tag_configure("good", background="#E6F4EA")
        self._yield_summary_lbl.config(
            text=(f"30-day avg variance: {avg:+.1f}%" if avg is not None
                  else "30-day avg variance: n/a"))

    def _yield_add(self):
        names = self._all_product_names()
        d = tk.Toplevel(self.root); d.title("Record yield")
        d.transient(self.root); d.grab_set()
        tk.Label(d, text="Item:").grid(row=0, column=0, padx=8, pady=6, sticky="e")
        item_var = tk.StringVar(value=names[0] if names else "")
        ttk.Combobox(d, textvariable=item_var, values=names, state="readonly",
                     width=28).grid(row=0, column=1, padx=8, pady=6)
        tk.Label(d, text="Expected:").grid(row=1, column=0, padx=8, pady=6, sticky="e")
        exp_var = tk.StringVar(value="12")
        tk.Entry(d, textvariable=exp_var, width=10).grid(row=1, column=1, padx=8, pady=6, sticky="w")
        tk.Label(d, text="Actual:").grid(row=2, column=0, padx=8, pady=6, sticky="e")
        act_var = tk.StringVar(value="12")
        tk.Entry(d, textvariable=act_var, width=10).grid(row=2, column=1, padx=8, pady=6, sticky="w")
        tk.Label(d, text="Notes:").grid(row=3, column=0, padx=8, pady=6, sticky="ne")
        notes_var = tk.StringVar(value="")
        tk.Entry(d, textvariable=notes_var, width=32).grid(row=3, column=1, padx=8, pady=6, sticky="w")
        def save():
            try:
                exp = int(exp_var.get()); act = int(act_var.get())
            except ValueError:
                messagebox.showerror("Yield", "Numeric only.", parent=d); return
            var = act - exp
            pct = (var / exp * 100.0) if exp else 0.0
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_yield_variance "
                    "(timestamp, item_name, expected_qty, actual_qty, "
                    "variance, variance_pct, baker, notes) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                     item_var.get(), exp, act, var, pct,
                     self.current_user or "system", notes_var.get()),
                )
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._yield_refresh()
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat", padx=14).grid(row=4, column=0,
                                                            columnspan=2, pady=10)

    def _build_timer_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Label(top, text="Label:", bg=bg).pack(side="left")
        self._timer_label = tk.StringVar(value="Oven 1")
        tk.Entry(top, textvariable=self._timer_label, width=14).pack(side="left", padx=4)
        tk.Label(top, text="Item:", bg=bg).pack(side="left")
        self._timer_item = tk.StringVar(value="")
        ttk.Combobox(top, textvariable=self._timer_item,
                     values=[""] + self._all_product_names(),
                     state="readonly", width=20).pack(side="left", padx=4)
        tk.Label(top, text="Stage:", bg=bg).pack(side="left")
        self._timer_stage = tk.StringVar(value="oven")
        ttk.Combobox(top, textvariable=self._timer_stage,
                     values=["oven", "proofing", "cooling"], state="readonly",
                     width=10).pack(side="left", padx=4)
        tk.Label(top, text="Mins:", bg=bg).pack(side="left")
        self._timer_mins = tk.StringVar(value="20")
        tk.Entry(top, textvariable=self._timer_mins, width=6).pack(side="left", padx=4)
        tk.Button(top, text="▶ Start", command=self._timer_start,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="⏹ Finish", command=lambda: self._timer_set("done"),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="✖ Cancel", command=lambda: self._timer_set("cancelled"),
                  relief="flat", padx=10).pack(side="left", padx=4)

        cols = ("id", "label", "item", "stage", "started", "ends", "remaining", "status")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=16)
        for c, h, w in [("id", "ID", 50), ("label", "Label", 110),
                        ("item", "Item", 150), ("stage", "Stage", 90),
                        ("started", "Started", 150), ("ends", "Ends", 150),
                        ("remaining", "Remaining", 100), ("status", "Status", 90)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="center")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._timer_tree = tv
        self._timer_refresh()

    def _timer_refresh(self):
        if not hasattr(self, "_timer_tree"):
            return
        tv = self._timer_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, label, item_name, stage, started_at, ends_at, "
                "status FROM bakery_oven_timers "
                "ORDER BY (status='running') DESC, id DESC LIMIT 200"
            ).fetchall()
        finally:
            conn.close()
        now = datetime.now()
        for rid, label, item, stage, started, ends, status in rows:
            try:
                end_dt = datetime.strptime(ends, "%Y-%m-%d %H:%M:%S")
            except Exception:
                end_dt = now
            rem_secs = int((end_dt - now).total_seconds())
            if status == "running":
                if rem_secs <= 0:
                    rem = "DONE"
                    tag = "ready"
                elif rem_secs < 60:
                    rem = f"{rem_secs}s"
                    tag = "soon"
                else:
                    rem = f"{rem_secs // 60}m {rem_secs % 60}s"
                    tag = ""
            else:
                rem = "—"; tag = ""
            tv.insert("", "end", iid=str(rid),
                      values=(rid, label, item or "", stage, started, ends,
                              rem, status), tags=(tag,))
        tv.tag_configure("ready", background="#FFD9D9")
        tv.tag_configure("soon", background="#FFF2CC")

    def _schedule_timer_tick(self):
        if self._timer_tick_scheduled:
            return
        self._timer_tick_scheduled = True
        def tick():
            try:
                # Check for any newly-finished timers and bell + flag them.
                conn = self._connect()
                try:
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    finished = conn.execute(
                        "SELECT id, label, item_name FROM bakery_oven_timers "
                        "WHERE status='running' AND ends_at <= ? "
                        "AND finished_at IS NULL",
                        (now_str,)).fetchall()
                    if finished:
                        for fid, lbl, item in finished:
                            conn.execute(
                                "UPDATE bakery_oven_timers SET finished_at=? "
                                "WHERE id=?", (now_str, fid))
                        conn.commit()
                        try:
                            self.root.bell()
                        except Exception:
                            pass
                        msg = ", ".join(f"{lbl}" + (f" ({it})" if it else "")
                                        for _i, lbl, it in finished)
                        self.set_status(f"⏰ Timer finished: {msg}")
                finally:
                    conn.close()
                self._timer_refresh()
            except Exception:
                logger.debug("timer tick failed", exc_info=True)
            self.root.after(1000, tick)
        self.root.after(1000, tick)

    def _timer_start(self):
        try:
            mins = int(self._timer_mins.get())
        except ValueError:
            messagebox.showerror("Timer", "Mins must be integer.",
                                 parent=self.root); return
        if mins <= 0:
            return
        now = datetime.now()
        ends = now + timedelta(minutes=mins)
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO bakery_oven_timers "
                "(label, item_name, started_at, duration_seconds, ends_at, "
                "stage, status, started_by) VALUES (?,?,?,?,?,?, 'running', ?)",
                (self._timer_label.get() or "Timer",
                 self._timer_item.get() or None,
                 now.strftime("%Y-%m-%d %H:%M:%S"),
                 mins * 60,
                 ends.strftime("%Y-%m-%d %H:%M:%S"),
                 self._timer_stage.get(),
                 self.current_user or "system"),
            )
            conn.commit()
        finally:
            conn.close()
        self._timer_refresh()

    def _timer_set(self, status):
        sel = self._timer_tree.focus()
        if not sel:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE bakery_oven_timers SET status=?, finished_at=? "
                "WHERE id=?", (status, now, int(sel)))
            conn.commit()
        finally:
            conn.close()
        self._timer_refresh()

    def _build_starter_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="+ Add starter", command=self._starter_add,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="🍞 Log feed (selected)", command=self._starter_feed,
                  bg=self.colors["accent"], relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._starter_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)

        cols = ("name", "interval_h", "last_fed", "next_due", "due_in", "active")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=8)
        for c, h, w in [("name", "Starter", 200),
                        ("interval_h", "Interval (h)", 110),
                        ("last_fed", "Last fed", 150),
                        ("next_due", "Next due", 150),
                        ("due_in", "Due in", 110),
                        ("active", "Active", 70)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="center")
        tv.column("name", anchor="w")
        tv.pack(fill="x", padx=10, pady=6)
        self._starter_tree = tv

        tk.Label(parent, text="Recent feeds", bg=bg,
                 font=("Arial", 11, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
        cols2 = ("ts", "name", "flour_g", "water_g", "by", "notes")
        tv2 = ttk.Treeview(parent, columns=cols2, show="headings", height=10)
        for c, h, w in [("ts", "When", 140), ("name", "Starter", 180),
                        ("flour_g", "Flour (g)", 90), ("water_g", "Water (g)", 90),
                        ("by", "By", 110), ("notes", "Notes", 200)]:
            tv2.heading(c, text=h); tv2.column(c, width=w, anchor="center")
        tv2.column("notes", anchor="w")
        tv2.pack(fill="both", expand=True, padx=10, pady=6)
        self._starter_feeds_tree = tv2
        self._starter_refresh()

    def _starter_refresh(self):
        tv = self._starter_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            starters = conn.execute(
                "SELECT name, feed_interval_hours, last_fed, next_due, active "
                "FROM bakery_starters ORDER BY name").fetchall()
            feeds = conn.execute(
                "SELECT fed_at, starter_name, flour_grams, water_grams, "
                "fed_by, notes FROM bakery_sourdough_feeds "
                "ORDER BY fed_at DESC LIMIT 100").fetchall()
        finally:
            conn.close()
        now = datetime.now()
        for name, ih, last, nxt, active in starters:
            due_in = "—"
            tag = ""
            if nxt:
                try:
                    nxt_dt = datetime.strptime(nxt, "%Y-%m-%d %H:%M:%S")
                    secs = int((nxt_dt - now).total_seconds())
                    if secs <= 0:
                        due_in = "OVERDUE"; tag = "overdue"
                    elif secs < 3600:
                        due_in = f"{secs // 60}m"; tag = "soon"
                    else:
                        due_in = f"{secs // 3600}h {(secs % 3600) // 60}m"
                except Exception:
                    pass
            tv.insert("", "end", iid=name,
                      values=(name, ih, last or "—", nxt or "—", due_in,
                              "yes" if active else "no"), tags=(tag,))
        tv.tag_configure("overdue", background="#FFD9D9")
        tv.tag_configure("soon", background="#FFF2CC")

        tv2 = self._starter_feeds_tree
        tv2.delete(*tv2.get_children())
        for ts, n, f, w, by, notes in feeds:
            tv2.insert("", "end", values=(ts, n, f or "", w or "",
                                          by or "", notes or ""))

    def _starter_add(self):
        name = simpledialog.askstring("Starter", "Starter name:",
                                      parent=self.root)
        if not name:
            return
        interval = simpledialog.askinteger("Starter",
                                           "Feed interval (hours):",
                                           initialvalue=24, minvalue=1,
                                           parent=self.root)
        if interval is None:
            return
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO bakery_starters "
                "(name, feed_interval_hours, active) VALUES (?,?,1)",
                (name, interval),
            )
            conn.commit()
        finally:
            conn.close()
        self._starter_refresh()

    def _starter_feed(self):
        sel = self._starter_tree.focus()
        if not sel:
            messagebox.showinfo("Feed", "Pick a starter first.",
                                parent=self.root); return
        d = tk.Toplevel(self.root); d.title(f"Feed {sel}")
        d.transient(self.root); d.grab_set()
        tk.Label(d, text="Flour (g):").grid(row=0, column=0, padx=8, pady=6, sticky="e")
        f_var = tk.StringVar(value="50")
        tk.Entry(d, textvariable=f_var, width=10).grid(row=0, column=1, padx=8, pady=6, sticky="w")
        tk.Label(d, text="Water (g):").grid(row=1, column=0, padx=8, pady=6, sticky="e")
        w_var = tk.StringVar(value="50")
        tk.Entry(d, textvariable=w_var, width=10).grid(row=1, column=1, padx=8, pady=6, sticky="w")
        tk.Label(d, text="Notes:").grid(row=2, column=0, padx=8, pady=6, sticky="ne")
        n_var = tk.StringVar(value="")
        tk.Entry(d, textvariable=n_var, width=32).grid(row=2, column=1, padx=8, pady=6, sticky="w")
        def save():
            try:
                f = float(f_var.get()); w = float(w_var.get())
            except ValueError:
                messagebox.showerror("Feed", "Numeric only.", parent=d); return
            now = datetime.now()
            now_str = now.strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                ih = conn.execute(
                    "SELECT feed_interval_hours FROM bakery_starters WHERE name=?",
                    (sel,)).fetchone()
                interval = (ih[0] if ih else 24) or 24
                nxt = (now + timedelta(hours=interval)
                       ).strftime("%Y-%m-%d %H:%M:%S")
                conn.execute(
                    "INSERT INTO bakery_sourdough_feeds "
                    "(starter_name, fed_at, flour_grams, water_grams, notes, fed_by) "
                    "VALUES (?,?,?,?,?,?)",
                    (sel, now_str, f, w, n_var.get(),
                     self.current_user or "system"),
                )
                conn.execute(
                    "UPDATE bakery_starters SET last_fed=?, next_due=? "
                    "WHERE name=?", (now_str, nxt, sel),
                )
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._starter_refresh()
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat", padx=14).grid(row=3, column=0,
                                                            columnspan=2, pady=10)

    def _build_substitution_panel(self, parent):
        bg = self.colors["background"]
        info = tk.Label(parent,
                        text="Suggested substitutes for ingredients that "
                             "are low in stock or unavailable.",
                        bg=bg, font=("Arial", 10, "italic"))
        info.pack(anchor="w", padx=10, pady=6)
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=4)
        tk.Button(top, text="+ Add substitution", command=self._sub_add,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="Remove selected", command=self._sub_remove,
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._sub_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)

        tk.Label(parent, text="Low-stock ingredients → suggestions",
                 bg=bg, font=("Arial", 11, "bold")).pack(anchor="w", padx=12,
                                                          pady=(10, 0))
        cols1 = ("ing", "stock", "reorder", "subs")
        tv1 = ttk.Treeview(parent, columns=cols1, show="headings", height=8)
        for c, h, w in [("ing", "Ingredient", 160),
                        ("stock", "Stock", 90),
                        ("reorder", "Reorder lvl", 110),
                        ("subs", "Suggested substitutes", 480)]:
            tv1.heading(c, text=h); tv1.column(c, width=w, anchor="w")
        tv1.pack(fill="x", padx=10, pady=6)
        self._sub_suggest_tree = tv1

        tk.Label(parent, text="All substitutions",
                 bg=bg, font=("Arial", 11, "bold")).pack(anchor="w", padx=12,
                                                          pady=(10, 0))
        cols2 = ("ing", "sub", "ratio", "notes")
        tv2 = ttk.Treeview(parent, columns=cols2, show="headings", height=10)
        for c, h, w in [("ing", "Ingredient", 160),
                        ("sub", "Substitute", 160),
                        ("ratio", "Ratio", 80),
                        ("notes", "Notes", 360)]:
            tv2.heading(c, text=h); tv2.column(c, width=w, anchor="w")
        tv2.pack(fill="both", expand=True, padx=10, pady=6)
        self._sub_tree = tv2
        self._sub_refresh()

    def _sub_refresh(self):
        conn = self._connect()
        try:
            subs = conn.execute(
                "SELECT id, ingredient, substitute, ratio, notes "
                "FROM bakery_substitutions ORDER BY ingredient, substitute"
            ).fetchall()
            ings = conn.execute(
                "SELECT name, stock, reorder_level FROM bakery_ingredients "
                "ORDER BY name").fetchall()
        finally:
            conn.close()
        sub_map = {}
        for _id, ing, sub, ratio, notes in subs:
            sub_map.setdefault(ing, []).append((sub, ratio))

        tv1 = self._sub_suggest_tree
        tv1.delete(*tv1.get_children())
        for name, stock, reorder in ings:
            if (stock or 0) >= (reorder or 0) and (stock or 0) > 0:
                continue
            opts = sub_map.get(name, [])
            text = ", ".join(f"{s} (×{r:g})" for s, r in opts) or "— no substitute on file —"
            tv1.insert("", "end", values=(name, f"{(stock or 0):g}",
                                          f"{(reorder or 0):g}", text))

        tv2 = self._sub_tree
        tv2.delete(*tv2.get_children())
        for sid, ing, sub, ratio, notes in subs:
            tv2.insert("", "end", iid=str(sid),
                       values=(ing, sub, f"{ratio:g}", notes or ""))

    def _sub_add(self):
        conn = self._connect()
        try:
            ings = [r[0] for r in conn.execute(
                "SELECT name FROM bakery_ingredients ORDER BY name").fetchall()]
        finally:
            conn.close()
        if not ings:
            return
        d = tk.Toplevel(self.root); d.title("Add substitution")
        d.transient(self.root); d.grab_set()
        tk.Label(d, text="Ingredient:").grid(row=0, column=0, padx=8, pady=6, sticky="e")
        ing_var = tk.StringVar(value=ings[0])
        ttk.Combobox(d, textvariable=ing_var, values=ings, state="readonly",
                     width=24).grid(row=0, column=1, padx=8, pady=6)
        tk.Label(d, text="Substitute:").grid(row=1, column=0, padx=8, pady=6, sticky="e")
        sub_var = tk.StringVar(value="")
        tk.Entry(d, textvariable=sub_var, width=26).grid(row=1, column=1, padx=8, pady=6, sticky="w")
        tk.Label(d, text="Ratio:").grid(row=2, column=0, padx=8, pady=6, sticky="e")
        r_var = tk.StringVar(value="1.0")
        tk.Entry(d, textvariable=r_var, width=10).grid(row=2, column=1, padx=8, pady=6, sticky="w")
        tk.Label(d, text="Notes:").grid(row=3, column=0, padx=8, pady=6, sticky="ne")
        n_var = tk.StringVar(value="")
        tk.Entry(d, textvariable=n_var, width=32).grid(row=3, column=1, padx=8, pady=6, sticky="w")
        def save():
            try:
                ratio = float(r_var.get())
            except ValueError:
                messagebox.showerror("Sub", "Ratio must be numeric.", parent=d); return
            sub = sub_var.get().strip()
            if not sub:
                messagebox.showerror("Sub", "Substitute required.", parent=d); return
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO bakery_substitutions "
                    "(ingredient, substitute, ratio, notes) VALUES (?,?,?,?)",
                    (ing_var.get(), sub, ratio, n_var.get()),
                )
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._sub_refresh()
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat", padx=14).grid(row=4, column=0,
                                                            columnspan=2, pady=10)

    def _sub_remove(self):
        sel = self._sub_tree.focus()
        if not sel:
            return
        if not messagebox.askyesno("Substitution", "Remove substitution?",
                                   parent=self.root):
            return
        conn = self._connect()
        try:
            conn.execute("DELETE FROM bakery_substitutions WHERE id=?",
                         (int(sel),))
            conn.commit()
        finally:
            conn.close()
        self._sub_refresh()

