"""InventoryTabMixin — auto-split from bakery_shop.py."""
from education_system.university_system.modules.domain.commerce.bakery_shop._common import *  # noqa: F401,F403


class InventoryTabMixin:
    def build_inventory_tab(self):
        self.inventory_content = tk.Frame(self.inventory_tab,
                                          bg=self.colors["background"])
        self.inventory_content.pack(fill="both", expand=True)
        self.refresh_inventory()

    def refresh_inventory(self):
        if not getattr(self, "inventory_tab", None) or not getattr(self.inventory_tab, "_lazy_built", False):
            return
        if not hasattr(self, "inventory_content"):
            return
        for w in self.inventory_content.winfo_children():
            w.destroy()

        if self.user_type != "Admin":
            tk.Label(self.inventory_content,
                     text="🔒 Admin access required\n\n"
                          "Inventory operations are admin-only.",
                     font=("Arial", 14),
                     bg=self.colors["background"], fg=self.colors["text"],
                     justify="center").pack(expand=True, pady=50)
            return

        # Run housekeeping once per render (expiry sweep is idempotent).
        try:
            expired = self._expire_batches()
            if expired:
                logger.info("Inventory refresh expired %d batch(es)", expired)
        except Exception:
            logger.exception("Batch expiry sweep failed")

        tk.Label(self.inventory_content,
                 text="🏭 Inventory Operations",
                 font=("Georgia", 18, "bold"),
                 bg=self.colors["background"], fg=self.colors["text"]
                 ).pack(pady=12)

        # ---- Active stock alerts -----------------------------------------
        alerts_frame = tk.LabelFrame(
            self.inventory_content, text="⚠ Active Stock Alerts",
            bg=self.colors["background"], fg=self.colors["danger"],
            font=("Arial", 11, "bold"))
        alerts_frame.pack(fill="x", padx=20, pady=6)

        alerts_tree = ttk.Treeview(alerts_frame,
            columns=("id", "item", "threshold", "stock", "when"),
            show="headings", height=5)
        for c, w in (("id", 50), ("item", 150), ("threshold", 90),
                     ("stock", 70), ("when", 150)):
            alerts_tree.heading(c, text=c.title())
            alerts_tree.column(c, width=w, anchor="w")
        for r in self._query("""SELECT id, item_name, threshold,
                                       current_stock, triggered_at
                                FROM bakery_stock_alerts
                                WHERE acknowledged=0
                                ORDER BY triggered_at DESC"""):
            alerts_tree.insert("", "end", values=r)
        alerts_tree.pack(fill="x", padx=8, pady=4)

        def ack_alert():
            sel = alerts_tree.selection()
            if not sel:
                return
            rid = alerts_tree.item(sel[0])["values"][0]
            self._exec("""UPDATE bakery_stock_alerts
                          SET acknowledged=1, acknowledged_by=?,
                              acknowledged_at=?
                          WHERE id=?""",
                       (self.current_user or "admin",
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), rid))
            logger.info("Stock alert id=%s acknowledged by %s",
                        rid, self.current_user)
            self.refresh_inventory()

        def reorder_from_alert():
            sel = alerts_tree.selection()
            if not sel:
                return
            vals = alerts_tree.item(sel[0])["values"]
            item = vals[1]
            rule = self.get_reorder_rule(item)
            if not rule:
                messagebox.showinfo("No rule",
                                    f"No reorder rule configured for {item}.")
                return
            po = self.create_purchase_order(
                {item: rule["reorder_qty"]},
                supplier_id=rule.get("supplier_id"),
                status="sent",
                notes=f"Manual reorder triggered from alert for {item}",
            )
            if po:
                messagebox.showinfo("PO Created", f"Purchase order {po} created.")
                ack_alert()

        ab = tk.Frame(alerts_frame, bg=self.colors["background"])
        ab.pack(fill="x", padx=8, pady=4)
        tk.Button(ab, text="✓ Acknowledge",
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  command=ack_alert).pack(side="left", padx=4)
        tk.Button(ab, text="📦 Reorder Now",
                  bg=self.colors["primary"], fg="white", relief="flat",
                  command=reorder_from_alert).pack(side="left", padx=4)

        # ---- Section action buttons --------------------------------------
        sections = tk.Frame(self.inventory_content, bg=self.colors["background"])
        sections.pack(fill="x", padx=20, pady=10)
        for label, cmd, color in (
            ("🚚 Suppliers",     self._open_suppliers_admin,    self.colors["primary"]),
            ("📦 Purchase Orders", self._open_po_admin,         self.colors["secondary"]),
            ("⚙ Reorder Rules", self._open_reorder_admin,       self.colors["success"]),
            ("🍞 Batches & Expiry", self._open_batches_admin,   self.colors["danger"]),
            ("🔍 Run Stock Check", self._manual_stock_check,    self.colors["accent"]),
        ):
            tk.Button(sections, text=label, font=("Arial", 10, "bold"),
                      bg=color,
                      fg="white" if color != self.colors["accent"] else self.colors["text"],
                      relief="flat", padx=14, pady=8, command=cmd
                      ).pack(side="left", padx=6)

        # ---- Quick stock summary -----------------------------------------
        summary = tk.LabelFrame(self.inventory_content,
                                text="📊 Stock at a Glance",
                                bg=self.colors["background"],
                                fg=self.colors["text"],
                                font=("Arial", 11, "bold"))
        summary.pack(fill="both", expand=True, padx=20, pady=10)

        tree = ttk.Treeview(summary,
            columns=("category", "item", "stock", "min", "reorder", "supplier", "auto"),
            show="headings", height=14)
        widths = {"category": 90, "item": 160, "stock": 70, "min": 60,
                  "reorder": 80, "supplier": 140, "auto": 60}
        for c, w in widths.items():
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        for cat, items in self.products.items():
            for name, info in items.items():
                rule = self.get_reorder_rule(name)
                supplier_name = ""
                if rule and rule.get("supplier_id"):
                    s = self._query("SELECT name FROM bakery_suppliers WHERE id=?",
                                    (rule["supplier_id"],))
                    supplier_name = s[0][0] if s else ""
                tree.insert("", "end", values=(
                    cat, name, info.get("stock", 0),
                    rule["min_stock"] if rule else "—",
                    rule["reorder_qty"] if rule else "—",
                    supplier_name or "—",
                    "✓" if (rule and rule["auto"]) else "—",
                ))
        scroll = ttk.Scrollbar(summary, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        scroll.pack(side="right", fill="y")

    def _manual_stock_check(self):
        try:
            newly = self.check_low_stock()
        except Exception:
            logger.exception("Manual stock check failed")
            messagebox.showerror("Error", "Stock check raised; see log.")
            return
        if newly:
            messagebox.showinfo("Stock Check",
                                f"Created {len(newly)} new alert(s) for: "
                                f"{', '.join(newly)}")
        else:
            messagebox.showinfo("Stock Check",
                                "No new alerts — all stocked items are above "
                                "their reorder thresholds.")
        self.refresh_inventory()

    def _open_suppliers_admin(self):
        self._open_simple_crud_dialog(
            title="🚚 Suppliers",
            columns=("id", "name", "contact", "email", "phone",
                     "lead_days", "active"),
            select_sql="""SELECT id, name, contact, email, phone,
                                 lead_time_days, active
                          FROM bakery_suppliers ORDER BY name""",
            add_fn=self._add_supplier_dialog,
            delete_sql="DELETE FROM bakery_suppliers WHERE id=?",
            id_col_index=0,
            toggle_sql="UPDATE bakery_suppliers SET active = 1 - active WHERE id=?",
        )

    def _add_supplier_dialog(self, refresh_cb):
        d = tk.Toplevel(self.root); d.title("New Supplier")
        d.geometry("400x340"); d.transient(self.root); d.grab_set()
        fields = {}
        for label, default in (
            ("Name", ""), ("Contact name", ""),
            ("Email", ""), ("Phone", ""),
            ("Lead time (days)", "3"),
        ):
            tk.Label(d, text=label).pack(anchor="w", padx=12, pady=(8, 0))
            e = tk.Entry(d, width=40); e.insert(0, default); e.pack(padx=12)
            fields[label] = e

        def save():
            try:
                ok = self.add_supplier(
                    fields["Name"].get().strip(),
                    contact=fields["Contact name"].get().strip() or None,
                    email=fields["Email"].get().strip() or None,
                    phone=fields["Phone"].get().strip() or None,
                    lead_time_days=int(fields["Lead time (days)"].get() or 3),
                )
                if not ok:
                    messagebox.showerror("Error",
                                         "Could not add supplier "
                                         "(duplicate name?)", parent=d)
                    return
                d.destroy(); refresh_cb()
            except Exception as e:
                logger.exception("Add supplier failed")
                messagebox.showerror("Error", str(e), parent=d)

        tk.Button(d, text="Save", bg=self.colors["success"], fg="white",
                  relief="flat", padx=20, pady=6, command=save
                  ).pack(side="right", padx=12, pady=12)
        tk.Button(d, text="Cancel", bg=self.colors["secondary"], fg="white",
                  relief="flat", padx=20, pady=6, command=d.destroy
                  ).pack(side="right", pady=12)

    def _open_po_admin(self):
        d = tk.Toplevel(self.root); d.title("📦 Purchase Orders")
        d.geometry("900x500"); d.transient(self.root); d.grab_set()

        cols = ("id", "po_number", "supplier", "status",
                "created", "expected", "received", "total")
        tree = ttk.Treeview(d, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 150, 130, 90, 130, 110, 130, 80)):
            tree.heading(c, text=c.title()); tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        def refresh():
            for it in tree.get_children():
                tree.delete(it)
            rows = self._query("""
                SELECT p.id, p.po_number, COALESCE(s.name, '—'), p.status,
                       p.created_at, p.expected_delivery, p.received_at,
                       p.total_cost
                FROM bakery_purchase_orders p
                LEFT JOIN bakery_suppliers s ON s.id = p.supplier_id
                ORDER BY p.id DESC""")
            for r in rows:
                tree.insert("", "end", values=(
                    r[0], r[1], r[2], r[3], r[4], r[5], r[6] or "—",
                    f"£{(r[7] or 0):.2f}",
                ))

        def view_details():
            sel = tree.selection()
            if not sel:
                return
            pid = tree.item(sel[0])["values"][0]
            rows = self._query("""SELECT po_number, status, items_json,
                                         notes FROM bakery_purchase_orders
                                  WHERE id=?""", (pid,))
            if not rows:
                return
            po_num, status, items_json, notes = rows[0]
            try:
                items = json.loads(items_json or "[]")
            except Exception:
                items = []
            lines = [f"PO {po_num}  •  status: {status}\n"]
            for it in items:
                lines.append(f"  • {it.get('item')} × {it.get('qty')} "
                             f"@ £{it.get('unit_cost', 0):.2f}")
            if notes:
                lines.append(f"\nNotes: {notes}")
            messagebox.showinfo(f"PO {po_num}", "\n".join(lines))

        def mark_received():
            sel = tree.selection()
            if not sel:
                return
            pid = tree.item(sel[0])["values"][0]
            if not messagebox.askyesno("Confirm",
                                       f"Mark PO {pid} as received? "
                                       "This will increase stock and create "
                                       "a batch per item."):
                return
            ok = self.receive_purchase_order(pid)
            if ok:
                messagebox.showinfo("Received", "Stock updated and batches recorded.")
                self.refresh_products()
            else:
                messagebox.showerror("Error",
                                     "Could not receive PO (already received "
                                     "or DB error).")
            refresh()

        def new_po():
            self._new_po_dialog(refresh)

        btns = tk.Frame(d); btns.pack(fill="x", padx=8, pady=6)
        tk.Button(btns, text="➕ New PO", bg=self.colors["success"], fg="white",
                  relief="flat", command=new_po).pack(side="left", padx=4)
        tk.Button(btns, text="👁 Details", bg=self.colors["accent"],
                  fg=self.colors["text"], relief="flat",
                  command=view_details).pack(side="left", padx=4)
        tk.Button(btns, text="📥 Mark Received",
                  bg=self.colors["primary"], fg="white", relief="flat",
                  command=mark_received).pack(side="left", padx=4)
        tk.Button(btns, text="Close",
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  command=d.destroy).pack(side="right", padx=4)

        refresh()

    def _new_po_dialog(self, refresh_cb):
        d = tk.Toplevel(self.root); d.title("New Purchase Order")
        d.geometry("500x460"); d.transient(self.root); d.grab_set()

        tk.Label(d, text="Supplier").pack(anchor="w", padx=12, pady=(8, 0))
        suppliers = self.list_suppliers()
        sup_map = {f"{r[1]} (id={r[0]})": r[0] for r in suppliers}
        sup_var = tk.StringVar(value=(next(iter(sup_map)) if sup_map else ""))
        ttk.Combobox(d, textvariable=sup_var, values=list(sup_map.keys()),
                     state="readonly", width=46).pack(padx=12)

        tk.Label(d, text="Items (one per line: 'Item Name x Qty @ unit_cost')"
                 ).pack(anchor="w", padx=12, pady=(8, 0))
        items_t = tk.Text(d, width=58, height=10); items_t.pack(padx=12)
        items_t.insert("1.0", "Coffee x 50 @ 0.80\nCroissant x 30 @ 1.20")

        tk.Label(d, text="Notes").pack(anchor="w", padx=12, pady=(8, 0))
        notes_e = tk.Entry(d, width=58); notes_e.pack(padx=12)

        def save():
            try:
                lines = [ln.strip() for ln in items_t.get("1.0", "end").splitlines()
                         if ln.strip()]
                items = []
                for ln in lines:
                    # 'Name x qty @ cost'
                    cost = 0.0
                    if "@" in ln:
                        head, cost_s = ln.rsplit("@", 1)
                        cost = float(cost_s.strip())
                    else:
                        head = ln
                    name, qty = head.rsplit("x", 1)
                    items.append({"item": name.strip(),
                                  "qty": int(qty.strip()),
                                  "unit_cost": cost})
                supplier_id = sup_map.get(sup_var.get())
                po = self.create_purchase_order(items,
                                                supplier_id=supplier_id,
                                                status="sent",
                                                notes=notes_e.get())
                if not po:
                    messagebox.showerror("Error", "Could not create PO.",
                                         parent=d)
                    return
                d.destroy(); refresh_cb()
            except Exception as e:
                logger.exception("New PO dialog failed")
                messagebox.showerror("Error", str(e), parent=d)

        tk.Button(d, text="Save", bg=self.colors["success"], fg="white",
                  relief="flat", padx=20, pady=6, command=save
                  ).pack(side="right", padx=12, pady=12)
        tk.Button(d, text="Cancel", bg=self.colors["secondary"], fg="white",
                  relief="flat", padx=20, pady=6, command=d.destroy
                  ).pack(side="right", pady=12)

    def _open_reorder_admin(self):
        d = tk.Toplevel(self.root); d.title("⚙ Reorder Rules")
        d.geometry("700x500"); d.transient(self.root); d.grab_set()

        cols = ("item", "stock", "min", "reorder_qty",
                "supplier", "unit_cost", "auto")
        tree = ttk.Treeview(d, columns=cols, show="headings", height=16)
        for c, w in zip(cols, (160, 60, 60, 100, 130, 100, 60)):
            tree.heading(c, text=c.title()); tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        def refresh():
            for it in tree.get_children():
                tree.delete(it)
            for cat, items in self.products.items():
                for name, info in items.items():
                    rule = self.get_reorder_rule(name)
                    s_name = ""
                    if rule and rule.get("supplier_id"):
                        s = self._query("SELECT name FROM bakery_suppliers WHERE id=?",
                                        (rule["supplier_id"],))
                        s_name = s[0][0] if s else ""
                    tree.insert("", "end", values=(
                        name, info.get("stock", 0),
                        rule["min_stock"] if rule else "—",
                        rule["reorder_qty"] if rule else "—",
                        s_name or "—",
                        f"£{rule['unit_cost']:.2f}" if rule else "—",
                        "✓" if (rule and rule["auto"]) else "—",
                    ))

        def edit_rule():
            sel = tree.selection()
            if not sel:
                return
            item = tree.item(sel[0])["values"][0]
            self._edit_reorder_rule_dialog(item, refresh)

        btns = tk.Frame(d); btns.pack(fill="x", padx=8, pady=6)
        tk.Button(btns, text="✏ Set / Edit Rule",
                  bg=self.colors["primary"], fg="white", relief="flat",
                  command=edit_rule).pack(side="left", padx=4)
        tk.Button(btns, text="Close",
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  command=d.destroy).pack(side="right", padx=4)
        refresh()

    def _edit_reorder_rule_dialog(self, item_name, refresh_cb):
        existing = self.get_reorder_rule(item_name) or {}
        d = tk.Toplevel(self.root); d.title(f"Reorder rule — {item_name}")
        d.geometry("420x340"); d.transient(self.root); d.grab_set()
        tk.Label(d, text=item_name, font=("Georgia", 14, "bold")
                 ).pack(pady=8)
        fields = {}
        for label, default in (
            ("Min stock", str(existing.get("min_stock", 5))),
            ("Reorder qty", str(existing.get("reorder_qty", 30))),
            ("Unit cost", str(existing.get("unit_cost", 0.0))),
        ):
            tk.Label(d, text=label).pack(anchor="w", padx=12, pady=(8, 0))
            e = tk.Entry(d, width=40); e.insert(0, default); e.pack(padx=12)
            fields[label] = e
        tk.Label(d, text="Supplier").pack(anchor="w", padx=12, pady=(8, 0))
        suppliers = self.list_suppliers()
        sup_map = {"(none)": None}
        for s in suppliers:
            sup_map[f"{s[1]} (id={s[0]})"] = s[0]
        current_label = "(none)"
        for lbl, sid in sup_map.items():
            if sid == existing.get("supplier_id"):
                current_label = lbl
                break
        sup_var = tk.StringVar(value=current_label)
        ttk.Combobox(d, textvariable=sup_var, values=list(sup_map.keys()),
                     state="readonly", width=37).pack(padx=12)

        auto_var = tk.BooleanVar(value=existing.get("auto", False))
        tk.Checkbutton(d, text="Auto-create PO when stock drops below min",
                       variable=auto_var).pack(anchor="w", padx=12, pady=8)

        def save():
            try:
                ok = self.set_reorder_rule(
                    item_name,
                    min_stock=int(fields["Min stock"].get() or 0),
                    reorder_qty=int(fields["Reorder qty"].get() or 0),
                    supplier_id=sup_map.get(sup_var.get()),
                    unit_cost=float(fields["Unit cost"].get() or 0),
                    auto=auto_var.get(),
                )
                if ok:
                    d.destroy(); refresh_cb()
                else:
                    messagebox.showerror("Error", "Could not save rule.", parent=d)
            except Exception as e:
                logger.exception("save reorder rule failed")
                messagebox.showerror("Error", str(e), parent=d)

        tk.Button(d, text="Save", bg=self.colors["success"], fg="white",
                  relief="flat", padx=20, pady=6, command=save
                  ).pack(side="right", padx=12, pady=12)
        tk.Button(d, text="Cancel", bg=self.colors["secondary"], fg="white",
                  relief="flat", padx=20, pady=6, command=d.destroy
                  ).pack(side="right", pady=12)

    def _open_batches_admin(self):
        d = tk.Toplevel(self.root); d.title("🍞 Batches & Expiry")
        d.geometry("780x500"); d.transient(self.root); d.grab_set()

        show_all_var = tk.BooleanVar(value=False)

        cols = ("id", "item", "qty", "initial", "expiry",
                "received", "lot", "status")
        tree = ttk.Treeview(d, columns=cols, show="headings", height=16)
        for c, w in zip(cols, (50, 150, 60, 70, 100, 130, 100, 90)):
            tree.heading(c, text=c.title()); tree.column(c, width=w, anchor="w")
        tree.tag_configure("expired", foreground=self.colors["danger"])
        tree.tag_configure("warn", foreground=self.colors["secondary"])
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        def refresh():
            for it in tree.get_children():
                tree.delete(it)
            self._expire_batches()
            for r in self.list_batches(include_depleted=show_all_var.get()):
                tags = ()
                if r[7] == "expired":
                    tags = ("expired",)
                else:
                    try:
                        days = (datetime.strptime(r[4], "%Y-%m-%d")
                                - datetime.now()).days
                        if days <= 1:
                            tags = ("warn",)
                    except Exception:
                        pass
                tree.insert("", "end", values=r, tags=tags)

        ctl = tk.Frame(d); ctl.pack(fill="x", padx=8, pady=4)
        tk.Checkbutton(ctl, text="Show depleted/expired",
                       variable=show_all_var,
                       command=refresh).pack(side="left", padx=4)
        tk.Button(ctl, text="🔄 Refresh",
                  bg=self.colors["accent"], fg=self.colors["text"],
                  relief="flat", command=refresh).pack(side="left", padx=4)
        tk.Button(ctl, text="Close",
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  command=d.destroy).pack(side="right", padx=4)
        refresh()

