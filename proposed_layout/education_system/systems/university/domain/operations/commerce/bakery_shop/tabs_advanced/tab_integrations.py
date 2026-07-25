"""IntegrationsTabMixin — auto-split from bakery_shop.py."""
from education_system.systems.university.domain.operations.commerce.bakery_shop._common import *  # noqa: F401,F403


class IntegrationsTabMixin:
    DEFAULT_LABEL_TEMPLATE = (
        "{item}\nPrice: £{price}\n"
        "Allergens: {allergens}\nBest before: {expiry}"
    )

    def build_integrations_tab(self):
        panels = [
            ("📺 Kitchen Display (KDS)", self._build_kds_panel),
            ("🏷 Label Printer",         self._build_label_panel),
            ("⚖ Scale (by-weight)",      self._build_scale_panel),
            ("📡 Menu-board Sync",      self._build_menuboard_panel),
        ]
        self._lazy_subnotebook(
            self.integrations_tab, panels, "Integrations")

    def _build_kds_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Label(top, text="Station:", bg=bg).pack(side="left")
        self._kds_station = tk.StringVar(value="main")
        ttk.Combobox(top, textvariable=self._kds_station,
                     values=["main", "espresso", "decorating"],
                     state="readonly", width=14).pack(side="left", padx=4)
        tk.Button(top, text="+ Push new ticket", command=self._kds_new,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="▶ Start", command=lambda: self._kds_set("prepping"),
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="🔔 Ready", command=lambda: self._kds_set("ready"),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="✅ Served", command=lambda: self._kds_set("served"),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._kds_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        self._kds_station.trace_add("write",
                                     lambda *_: self._kds_refresh())

        # Lanes
        board = tk.Frame(parent, bg=bg); board.pack(fill="both", expand=True,
                                                     padx=10, pady=6)
        self._kds_lanes = {}
        for col, lane in enumerate(["queued", "prepping", "ready"]):
            lf = tk.LabelFrame(board, text=lane.upper(), bg=bg,
                               font=("Arial", 11, "bold"))
            lf.grid(row=0, column=col, sticky="nsew", padx=4)
            board.grid_columnconfigure(col, weight=1)
            tv = ttk.Treeview(lf, columns=("id", "order", "items", "received",
                                            "wait"),
                              show="headings", height=18)
            for c, h, w in [("id", "ID", 50), ("order", "Order", 90),
                            ("items", "Items", 200),
                            ("received", "In", 150), ("wait", "Age", 80)]:
                tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
            tv.pack(fill="both", expand=True)
            self._kds_lanes[lane] = tv
        board.grid_rowconfigure(0, weight=1)
        self._kds_refresh()

    def _kds_refresh(self):
        station = self._kds_station.get()
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, order_id, items_json, received_at, status "
                "FROM bakery_kds_tickets WHERE station=? "
                "AND status != 'served' "
                "ORDER BY priority ASC, id ASC", (station,)).fetchall()
        finally:
            conn.close()
        now = datetime.now()
        for tv in self._kds_lanes.values():
            tv.delete(*tv.get_children())
        for rid, oid, items, ra, st in rows:
            try:
                d = json.loads(items)
                desc = ", ".join(f"{k}×{v}" for k, v in d.items())
            except Exception:
                desc = items
            try:
                dt = datetime.strptime(ra, "%Y-%m-%d %H:%M:%S")
                mins = int((now - dt).total_seconds() // 60)
                wait = f"{mins}m"
            except Exception:
                wait = "—"
            lane = st if st in self._kds_lanes else "queued"
            self._kds_lanes[lane].insert("", "end", iid=str(rid),
                values=(rid, oid or "", desc, ra, wait))

    def _kds_new(self):
        oid = simpledialog.askstring("KDS",
                                     "Order ID (eg POS-...):",
                                     parent=self.root) or ""
        items_text = simpledialog.askstring(
            "KDS", "Items (Item1=2, Item2=1):", parent=self.root) or ""
        items = {}
        for chunk in items_text.split(","):
            if "=" in chunk:
                k, v = chunk.split("=", 1)
                try:
                    items[k.strip()] = int(v.strip())
                except ValueError:
                    continue
        if not items:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO bakery_kds_tickets "
                "(order_id, station, items_json, status, received_at) "
                "VALUES (?,?,?, 'queued', ?)",
                (oid, self._kds_station.get(), json.dumps(items), now))
            conn.commit()
        finally:
            conn.close()
        self._kds_refresh()

    def _kds_set(self, status):
        sel = None
        for tv in self._kds_lanes.values():
            if tv.focus():
                sel = tv.focus(); break
        if not sel:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        col = {"prepping": "started_at", "ready": "ready_at",
               "served": "served_at"}.get(status)
        conn = self._connect()
        try:
            if col:
                conn.execute(
                    f"UPDATE bakery_kds_tickets SET status=?, {col}=? "
                    "WHERE id=?", (status, now, int(sel)))
            else:
                conn.execute(
                    "UPDATE bakery_kds_tickets SET status=? WHERE id=?",
                    (status, int(sel)))
            conn.commit()
        finally:
            conn.close()
        if status == "ready":
            try: self.root.bell()
            except Exception: pass
        self._kds_refresh()

    def _build_label_panel(self, parent):
        bg = self.colors["background"]
        info = tk.Label(parent,
            text="Queue labels for the price-tag/allergen printer. "
                 "Mark printed once the device confirms.",
            bg=bg, font=("Arial", 11, "italic"), justify="left")
        info.pack(anchor="w", padx=14, pady=6)
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=4)
        tk.Button(top, text="+ Queue label", command=self._label_queue,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="🖨 Mark printed",
                  command=lambda: self._label_set("printed"),
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="✖ Mark failed",
                  command=lambda: self._label_set("failed"),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._label_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        cols = ("id", "item", "qty", "payload", "status", "queued", "printed")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c, h, w in [("id", "ID", 50), ("item", "Item", 150),
                        ("qty", "Qty", 50), ("payload", "Payload", 320),
                        ("status", "Status", 80), ("queued", "Queued", 150),
                        ("printed", "Printed", 150)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._label_tree = tv
        self._label_refresh()

    def _label_refresh(self):
        tv = self._label_tree; tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, item_name, qty, payload, status, queued_at, "
                "printed_at FROM bakery_label_jobs "
                "ORDER BY id DESC LIMIT 200").fetchall()
        finally:
            conn.close()
        for rid, it, q, p, st, qa, pa in rows:
            tag = {"printed": "ok", "failed": "bad"}.get(st, "")
            tv.insert("", "end", iid=str(rid),
                      values=(rid, it, q, (p or "")[:80], st,
                              qa, pa or ""), tags=(tag,))
        tv.tag_configure("ok", background="#E6F4EA")
        tv.tag_configure("bad", background="#FFD9D9")

    def _label_queue(self):
        names = self._all_product_names()
        d = tk.Toplevel(self.root); d.title("Queue label")
        d.transient(self.root); d.grab_set()
        item_var = tk.StringVar(value=names[0] if names else "")
        qty_var = tk.StringVar(value="1")
        tk.Label(d, text="Item:").grid(row=0, column=0, padx=8, pady=4, sticky="e")
        ttk.Combobox(d, textvariable=item_var, values=names,
                     state="readonly", width=24).grid(row=0, column=1, padx=8, pady=4)
        tk.Label(d, text="Qty:").grid(row=1, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=qty_var, width=6).grid(row=1, column=1, padx=8, pady=4, sticky="w")
        def save():
            try:
                q = int(qty_var.get())
            except ValueError:
                messagebox.showerror("Label", "Bad qty.", parent=d); return
            it = item_var.get()
            price = 0.0; allergens = []
            for cat, items in self.products.items():
                if it in items:
                    price = items[it].get("price", 0.0)
                    allergens = items[it].get("allergens", [])
                    break
            expiry = (datetime.now() + timedelta(
                days=self._prod_shelf_life(it))).strftime("%Y-%m-%d")
            payload = self.DEFAULT_LABEL_TEMPLATE.format(
                item=it, price=f"{price:.2f}",
                allergens=",".join(allergens) or "none",
                expiry=expiry)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_label_jobs "
                    "(item_name, qty, payload, status, queued_at) "
                    "VALUES (?,?,?, 'queued', ?)",
                    (it, q, payload, now))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._label_refresh()
        tk.Button(d, text="Queue", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).grid(row=2, column=0, columnspan=2, pady=10)

    def _label_set(self, status):
        sel = self._label_tree.focus()
        if not sel:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            if status == "printed":
                conn.execute(
                    "UPDATE bakery_label_jobs SET status=?, printed_at=?, "
                    "printed_by=? WHERE id=?",
                    (status, now, self.current_user or "system", int(sel)))
            else:
                conn.execute(
                    "UPDATE bakery_label_jobs SET status=? WHERE id=?",
                    (status, int(sel)))
            conn.commit()
        finally:
            conn.close()
        self._label_refresh()

    def _build_scale_panel(self, parent):
        bg = self.colors["background"]
        info = tk.Label(parent,
            text="Configure by-weight items and capture scale readings. "
                 "Total = weight (g) × price/kg ÷ 1000.",
            bg=bg, font=("Arial", 11, "italic"), justify="left")
        info.pack(anchor="w", padx=14, pady=6)
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=4)
        tk.Button(top, text="+ Add by-weight item",
                  command=self._scale_item_add,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="⚖ Capture reading",
                  command=self._scale_reading,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._scale_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)

        tk.Label(parent, text="By-weight items", bg=bg,
                 font=("Arial", 11, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
        cols = ("item", "price_kg", "tare", "active")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=6)
        for c, h, w in [("item", "Item", 220),
                        ("price_kg", "Price / kg", 120),
                        ("tare", "Tare (g)", 100),
                        ("active", "Active", 80)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="x", padx=10, pady=4)
        self._scale_items_tree = tv

        tk.Label(parent, text="Recent readings", bg=bg,
                 font=("Arial", 11, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
        cols2 = ("ts", "item", "weight", "price_kg", "total", "operator")
        tv2 = ttk.Treeview(parent, columns=cols2, show="headings", height=12)
        for c, h, w in [("ts", "When", 150), ("item", "Item", 180),
                        ("weight", "Weight (g)", 100),
                        ("price_kg", "£/kg", 90),
                        ("total", "Total £", 100),
                        ("operator", "Operator", 110)]:
            tv2.heading(c, text=h); tv2.column(c, width=w, anchor="w")
        tv2.pack(fill="both", expand=True, padx=10, pady=4)
        self._scale_readings_tree = tv2
        self._scale_refresh()

    def _scale_refresh(self):
        conn = self._connect()
        try:
            items = conn.execute(
                "SELECT item_name, price_per_kg, tare_g, active "
                "FROM bakery_scale_items ORDER BY item_name").fetchall()
            readings = conn.execute(
                "SELECT timestamp, item_name, weight_g, price_per_kg, "
                "total_price, operator FROM bakery_scale_readings "
                "ORDER BY id DESC LIMIT 200").fetchall()
        finally:
            conn.close()
        tv = self._scale_items_tree; tv.delete(*tv.get_children())
        for it, pp, t, a in items:
            tv.insert("", "end", iid=it,
                      values=(it, f"£{(pp or 0):.2f}", f"{(t or 0):g}",
                              "yes" if a else "no"))
        tv2 = self._scale_readings_tree; tv2.delete(*tv2.get_children())
        for ts, it, wg, pp, tot, op in readings:
            tv2.insert("", "end",
                       values=(ts, it, f"{wg:g}", f"£{(pp or 0):.2f}",
                               f"£{(tot or 0):.2f}", op or ""))

    def _scale_item_add(self):
        names = self._all_product_names() + ["(custom)"]
        d = tk.Toplevel(self.root); d.title("By-weight item")
        d.transient(self.root); d.grab_set()
        item_var = tk.StringVar(value=names[0])
        pp_var = tk.StringVar(value="10.00")
        t_var = tk.StringVar(value="0")
        tk.Label(d, text="Item:").grid(row=0, column=0, padx=8, pady=4, sticky="e")
        ttk.Combobox(d, textvariable=item_var, values=names,
                     width=24).grid(row=0, column=1, padx=8, pady=4)
        tk.Label(d, text="Price / kg £:").grid(row=1, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=pp_var, width=12).grid(row=1, column=1, padx=8, pady=4, sticky="w")
        tk.Label(d, text="Tare (g):").grid(row=2, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=t_var, width=12).grid(row=2, column=1, padx=8, pady=4, sticky="w")
        def save():
            try:
                pp = float(pp_var.get()); tr = float(t_var.get())
            except ValueError:
                messagebox.showerror("Scale", "Numeric.", parent=d); return
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_scale_items "
                    "(item_name, price_per_kg, tare_g, active) "
                    "VALUES (?,?,?,1) ON CONFLICT(item_name) "
                    "DO UPDATE SET price_per_kg=excluded.price_per_kg, "
                    "tare_g=excluded.tare_g, active=1",
                    (item_var.get(), pp, tr))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._scale_refresh()
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).grid(row=3, column=0, columnspan=2, pady=10)

    def _scale_reading(self):
        conn = self._connect()
        try:
            items = [r[0] for r in conn.execute(
                "SELECT item_name FROM bakery_scale_items WHERE active=1 "
                "ORDER BY item_name").fetchall()]
        finally:
            conn.close()
        if not items:
            messagebox.showinfo("Scale", "Add a by-weight item first.",
                                parent=self.root); return
        d = tk.Toplevel(self.root); d.title("Capture reading")
        d.transient(self.root); d.grab_set()
        item_var = tk.StringVar(value=items[0])
        w_var = tk.StringVar(value="500")
        tk.Label(d, text="Item:").grid(row=0, column=0, padx=8, pady=4, sticky="e")
        ttk.Combobox(d, textvariable=item_var, values=items,
                     state="readonly", width=24).grid(row=0, column=1, padx=8, pady=4)
        tk.Label(d, text="Weight (g):").grid(row=1, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=w_var, width=10).grid(row=1, column=1, padx=8, pady=4, sticky="w")
        total_lbl = tk.Label(d, text="", font=("Arial", 12, "bold"))
        total_lbl.grid(row=2, column=0, columnspan=2, pady=6)
        def update_total(*_):
            try:
                w = float(w_var.get())
            except ValueError:
                total_lbl.config(text=""); return
            conn = self._connect()
            try:
                r = conn.execute(
                    "SELECT price_per_kg, tare_g FROM bakery_scale_items "
                    "WHERE item_name=?", (item_var.get(),)).fetchone()
            finally:
                conn.close()
            if not r:
                return
            net = max(0.0, w - (r[1] or 0))
            total = net * (r[0] or 0) / 1000.0
            total_lbl.config(text=f"Net {net:g} g · Total £{total:.2f}")
        w_var.trace_add("write", update_total)
        item_var.trace_add("write", update_total)
        update_total()
        def save():
            try:
                w = float(w_var.get())
            except ValueError:
                messagebox.showerror("Scale", "Numeric.", parent=d); return
            conn = self._connect()
            try:
                r = conn.execute(
                    "SELECT price_per_kg, tare_g FROM bakery_scale_items "
                    "WHERE item_name=?", (item_var.get(),)).fetchone()
                pp = (r[0] or 0); tare = (r[1] or 0)
                net = max(0.0, w - tare)
                total = net * pp / 1000.0
                conn.execute(
                    "INSERT INTO bakery_scale_readings "
                    "(item_name, weight_g, price_per_kg, total_price, "
                    "timestamp, operator) VALUES (?,?,?,?,?,?)",
                    (item_var.get(), w, pp, total,
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                     self.current_user or "system"))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._scale_refresh()
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).grid(row=3, column=0, columnspan=2, pady=10)

    def _build_menuboard_panel(self, parent):
        bg = self.colors["background"]
        info = tk.Label(parent,
            text="Push the current product catalog to each dining-hall "
                 "menu board endpoint. Per-board sync status is recorded.",
            bg=bg, font=("Arial", 11, "italic"), justify="left")
        info.pack(anchor="w", padx=14, pady=6)
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=4)
        tk.Button(top, text="+ Add board", command=self._menuboard_add,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Sync selected",
                  command=self._menuboard_sync,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="🔄 Sync all", command=self._menuboard_sync_all,
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._menuboard_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        cols = ("id", "location", "feed_url", "last_synced", "status", "error")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c, h, w in [("id", "ID", 50), ("location", "Location", 180),
                        ("feed_url", "Feed URL", 280),
                        ("last_synced", "Last synced", 150),
                        ("status", "Status", 80), ("error", "Error", 200)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._menuboard_tree = tv
        self._menuboard_refresh()

    def _menuboard_refresh(self):
        tv = self._menuboard_tree; tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, location, feed_url, last_synced_at, "
                "sync_status, error FROM bakery_menu_board "
                "ORDER BY id DESC").fetchall()
        finally:
            conn.close()
        for rid, loc, url, ls, st, err in rows:
            tag = {"ok": "ok", "error": "bad"}.get(st, "")
            tv.insert("", "end", iid=str(rid),
                      values=(rid, loc, url or "", ls or "—", st,
                              err or ""), tags=(tag,))
        tv.tag_configure("ok", background="#E6F4EA")
        tv.tag_configure("bad", background="#FFD9D9")

    def _menuboard_add(self):
        loc = simpledialog.askstring("Menu board",
                                     "Location (eg 'Dining Hall North'):",
                                     parent=self.root)
        if not loc:
            return
        url = simpledialog.askstring("Menu board",
                                     "Feed URL (optional, can be blank):",
                                     parent=self.root) or ""
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO bakery_menu_board (location, feed_url, "
                "sync_status) VALUES (?,?, 'idle')", (loc, url))
            conn.commit()
        finally:
            conn.close()
        self._menuboard_refresh()

    def _build_menu_payload(self):
        """Compose the menu-board payload from the live catalog."""
        out = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
               "categories": []}
        for cat, items in self.products.items():
            entry = {"category": cat, "items": []}
            for it, meta in items.items():
                if meta.get("stock", 0) <= 0:
                    continue
                entry["items"].append({
                    "name": it,
                    "price": meta.get("price", 0),
                    "allergens": meta.get("allergens", []),
                    "dietary": meta.get("dietary", []),
                })
            out["categories"].append(entry)
        return out

    def _menuboard_sync(self):
        sel = self._menuboard_tree.focus()
        if not sel:
            return
        self._menuboard_sync_ids([int(sel)])

    def _menuboard_sync_all(self):
        conn = self._connect()
        try:
            ids = [r[0] for r in conn.execute(
                "SELECT id FROM bakery_menu_board").fetchall()]
        finally:
            conn.close()
        self._menuboard_sync_ids(ids)

    def _menuboard_sync_ids(self, ids):
        if not ids:
            return
        payload = json.dumps(self._build_menu_payload())
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            for rid in ids:
                # Local-only sync: store the payload, mark ok. In production
                # a worker would POST to feed_url.
                conn.execute(
                    "UPDATE bakery_menu_board SET last_payload=?, "
                    "last_synced_at=?, sync_status='ok', error=NULL "
                    "WHERE id=?", (payload, now, rid))
            conn.commit()
        finally:
            conn.close()
        self._menuboard_refresh()
        self.set_status(f"Synced {len(ids)} menu-board(s).")

