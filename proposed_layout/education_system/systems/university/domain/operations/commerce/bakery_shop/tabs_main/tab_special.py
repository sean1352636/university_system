"""SpecialTabMixin — auto-split from bakery_shop.py."""
from education_system.systems.university.domain.operations.commerce.bakery_shop._common import *  # noqa: F401,F403


class SpecialTabMixin:
    def build_special_tab(self):
        self.special_content = tk.Frame(self.special_tab,
                                         bg=self.colors["background"])
        self.special_content.pack(fill="both", expand=True)
        self.refresh_special()

    def refresh_special(self):
        if not getattr(self, "special_tab", None) or not getattr(self.special_tab, "_lazy_built", False):
            return
        if not hasattr(self, "special_content"):
            return
        for w in self.special_content.winfo_children():
            w.destroy()

        nb = ttk.Notebook(self.special_content)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        pre_tab = tk.Frame(nb, bg=self.colors["background"])
        custom_tab = tk.Frame(nb, bg=self.colors["background"])
        bulk_tab = tk.Frame(nb, bg=self.colors["background"])
        rec_tab = tk.Frame(nb, bg=self.colors["background"])
        kitchen_tab = tk.Frame(nb, bg=self.colors["background"])
        feedback_tab = tk.Frame(nb, bg=self.colors["background"])
        nb.add(pre_tab,      text="📅 Pre-Orders")
        nb.add(custom_tab,   text="🎂 Custom Cakes")
        nb.add(bulk_tab,     text="📦 Bulk / Event")
        nb.add(rec_tab,      text="🔁 Standing Orders")
        nb.add(kitchen_tab,  text="🍳 Kitchen Display")
        nb.add(feedback_tab, text="💬 Feedback")

        self._render_preorders(pre_tab)
        self._render_custom_orders(custom_tab)
        self._render_bulk_orders(bulk_tab)
        self._render_recurring_orders(rec_tab)
        self._render_kitchen_display(kitchen_tab)
        self._render_feedback_view(feedback_tab)

    def _render_preorders(self, parent):
        top = tk.Frame(parent, bg=self.colors["background"])
        top.pack(fill="x", padx=12, pady=8)
        tk.Button(top, text="📅 Schedule a Pre-Order from Cart",
                  font=("Arial", 11, "bold"),
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=14, pady=6,
                  command=self._open_preorder_dialog).pack(side="left")

        cols = ("id", "order_id", "user", "pickup", "status", "total")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c, w in zip(cols, (50, 110, 130, 150, 100, 90)):
            tree.heading(c, text=c.title()); tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, padx=12, pady=6)

        user_filter = None if self.user_type == "Admin" else self.current_user
        rows = self.list_preorders(user=user_filter, include_completed=True)
        for r in rows:
            tree.insert("", "end", values=(
                r[0], r[1], r[2], r[4], r[5], self.fmt_money(r[6] or 0)
            ))

        if self.user_type == "Admin":
            ctl = tk.Frame(parent, bg=self.colors["background"])
            ctl.pack(fill="x", padx=12, pady=6)
            tk.Label(ctl, text="Admin actions:",
                     bg=self.colors["background"]).pack(side="left")
            for status in ("ready", "collected", "cancelled"):
                tk.Button(ctl, text=f"Set {status}",
                          bg=self.colors["secondary"], fg="white",
                          relief="flat", padx=10, pady=4,
                          command=lambda s=status, t=tree:
                              self._set_selected_preorder_status(t, s)
                          ).pack(side="left", padx=4)

    def _set_selected_preorder_status(self, tree, status):
        sel = tree.selection()
        if not sel:
            return
        pid = tree.item(sel[0])["values"][0]
        if self.update_preorder_status(pid, status):
            self.refresh_special()

    def _open_preorder_dialog(self):
        if not self.current_user:
            messagebox.showinfo("Login Required",
                                "Log in to schedule a pre-order.")
            return
        if not self.cart:
            messagebox.showinfo("Empty Cart",
                                "Add items to your cart, then schedule.")
            return
        d = tk.Toplevel(self.root); d.title("📅 Schedule Pre-Order")
        d.geometry("440x360"); d.transient(self.root); d.grab_set()

        tk.Label(d, text="📅 Schedule Collection",
                 font=("Georgia", 14, "bold"),
                 bg=self.colors["background"], fg=self.colors["text"]
                 ).pack(pady=10)
        info = tk.Label(d, text=f"Items: {sum(self.cart.values())} units, "
                                f"est. {self.fmt_money(self.compute_discounts(self.cart)['total'])}",
                        bg=self.colors["background"]); info.pack(pady=4)
        tk.Label(d, text="Pickup date").pack(anchor="w", padx=20, pady=(8, 0))
        date_e = tk.Entry(d, width=30)
        date_e.insert(0, (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"))
        date_e.pack(padx=20)
        tk.Label(d, text="Pickup time (HH:MM)").pack(anchor="w", padx=20, pady=(8, 0))
        time_e = tk.Entry(d, width=30); time_e.insert(0, "09:00"); time_e.pack(padx=20)
        tk.Label(d, text="Notes").pack(anchor="w", padx=20, pady=(8, 0))
        notes_e = tk.Entry(d, width=30); notes_e.pack(padx=20)

        def submit():
            collection = f"{date_e.get().strip()} {time_e.get().strip()}"
            try:
                datetime.strptime(collection, "%Y-%m-%d %H:%M")
            except ValueError:
                messagebox.showerror("Invalid", "Use YYYY-MM-DD and HH:MM.",
                                     parent=d); return
            oid = self.create_preorder(dict(self.cart), collection,
                                       notes=notes_e.get())
            if not oid:
                messagebox.showerror("Error",
                                     "Could not create pre-order.",
                                     parent=d); return
            self.cart.clear()
            self.refresh_cart(); self.update_cart_tab_title()
            self.refresh_special()
            messagebox.showinfo("Pre-Order Scheduled",
                                f"Order {oid} scheduled for {collection}.\n"
                                "Payment is due on collection.")
            d.destroy()

        tk.Button(d, text="Schedule",
                  bg=self.colors["success"], fg="white", relief="flat",
                  padx=20, pady=6, command=submit
                  ).pack(side="right", padx=20, pady=15)
        tk.Button(d, text="Cancel",
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  padx=20, pady=6, command=d.destroy
                  ).pack(side="right", pady=15)

    def _render_custom_orders(self, parent):
        top = tk.Frame(parent, bg=self.colors["background"])
        top.pack(fill="x", padx=12, pady=8)
        tk.Button(top, text="🎂 Request a Custom Cake",
                  font=("Arial", 11, "bold"),
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=14, pady=6,
                  command=self._open_custom_cake_dialog).pack(side="left")

        cols = ("id", "user", "type", "size", "pickup", "status",
                "quoted_price", "email")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c, w in zip(cols, (50, 120, 110, 80, 110, 110, 90, 160)):
            tree.heading(c, text=c.title()); tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, padx=12, pady=6)

        user_filter = None if self.user_type == "Admin" else self.current_user
        rows = self.list_custom_orders(user=user_filter)
        for r in rows:
            tree.insert("", "end", values=(
                r[0], r[1], r[2], r[3], r[4], r[5],
                self.fmt_money(r[6] or 0) if r[6] else "—",
                r[7] or "—",
            ))

        if self.user_type == "Admin":
            ctl = tk.Frame(parent, bg=self.colors["background"])
            ctl.pack(fill="x", padx=12, pady=6)
            tk.Button(ctl, text="✏ Quote / Update",
                      bg=self.colors["primary"], fg="white", relief="flat",
                      padx=10, pady=4,
                      command=lambda t=tree: self._quote_custom_order(t)
                      ).pack(side="left", padx=4)
            for status in ("accepted", "in_progress", "ready",
                           "collected", "cancelled"):
                tk.Button(ctl, text=status.title(),
                          bg=self.colors["secondary"], fg="white",
                          relief="flat", padx=8, pady=4,
                          command=lambda s=status, t=tree:
                              self._set_custom_status(t, s)
                          ).pack(side="left", padx=2)

    def _set_custom_status(self, tree, status):
        sel = tree.selection()
        if not sel:
            return
        cid = tree.item(sel[0])["values"][0]
        if self.update_custom_order(cid, status=status):
            self.refresh_special()

    def _quote_custom_order(self, tree):
        sel = tree.selection()
        if not sel:
            return
        cid = tree.item(sel[0])["values"][0]
        price = simpledialog.askfloat(
            "Quote Price",
            "Enter quoted price (£, in GBP — converted on display):",
            parent=self.root, minvalue=0.0)
        if price is None:
            return
        notes = simpledialog.askstring(
            "Admin Notes", "Optional notes for the customer:",
            parent=self.root) or ""
        if self.update_custom_order(cid, quoted_price=price,
                                    admin_notes=notes, status="quoted"):
            self.refresh_special()

    def _open_custom_cake_dialog(self):
        if not self.current_user:
            messagebox.showinfo("Login Required",
                                "Log in to request a custom cake.")
            return
        d = tk.Toplevel(self.root); d.title("🎂 Custom Cake Request")
        d.geometry("500x620"); d.transient(self.root); d.grab_set()
        tk.Label(d, text="🎂 Custom Cake Request",
                 font=("Georgia", 14, "bold"),
                 bg=self.colors["background"]).pack(pady=8)

        fields = {}
        for label, default in (
            ("Cake type (e.g. Birthday)", ""),
            ("Size (e.g. 8\" round, 12 servings)", ""),
            ("Flavours (sponge / filling / icing)", ""),
            ("Message on cake", ""),
            ("Dietary requirements", ""),
            ("Collection date (YYYY-MM-DD)",
             (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")),
            ("Contact email", ""),
            ("Contact phone", ""),
        ):
            tk.Label(d, text=label, bg=self.colors["background"]
                     ).pack(anchor="w", padx=18, pady=(6, 0))
            e = tk.Entry(d, width=54); e.insert(0, default); e.pack(padx=18)
            fields[label] = e

        def submit():
            try:
                collection_date = fields["Collection date (YYYY-MM-DD)"].get().strip()
                datetime.strptime(collection_date, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Invalid",
                                     "Collection date must be YYYY-MM-DD.",
                                     parent=d); return
            cid = self.create_custom_order(
                cake_type=fields["Cake type (e.g. Birthday)"].get(),
                size=fields["Size (e.g. 8\" round, 12 servings)"].get(),
                flavours=fields["Flavours (sponge / filling / icing)"].get(),
                message=fields["Message on cake"].get(),
                dietary=fields["Dietary requirements"].get(),
                collection_date=collection_date,
                contact_email=fields["Contact email"].get(),
                contact_phone=fields["Contact phone"].get(),
            )
            if cid:
                messagebox.showinfo(
                    "Request Submitted",
                    f"Your custom cake request (#{cid}) has been received.\n"
                    "An admin will quote a price and confirm shortly.")
                self.refresh_special()
                d.destroy()
            else:
                messagebox.showerror("Error",
                                     "Could not submit request.",
                                     parent=d)

        tk.Button(d, text="Submit Request",
                  bg=self.colors["success"], fg="white", relief="flat",
                  padx=20, pady=6, command=submit
                  ).pack(side="right", padx=18, pady=12)
        tk.Button(d, text="Cancel",
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  padx=20, pady=6, command=d.destroy
                  ).pack(side="right", pady=12)

    def _render_bulk_orders(self, parent):
        top = tk.Frame(parent, bg=self.colors["background"])
        top.pack(fill="x", padx=12, pady=8)
        tk.Button(top, text="📦 New Bulk / Event Order",
                  font=("Arial", 11, "bold"),
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=14, pady=6,
                  command=self._open_bulk_dialog).pack(side="left")

        cols = ("id", "user", "dept", "event_date", "location",
                "attendees", "total", "status")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c, w in zip(cols, (50, 120, 120, 110, 140, 70, 90, 100)):
            tree.heading(c, text=c.title()); tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, padx=12, pady=6)

        user_filter = None if self.user_type == "Admin" else self.current_user
        for r in self.list_bulk_orders(user=user_filter):
            tree.insert("", "end", values=(
                r[0], r[1], r[2], r[3], r[4], r[5],
                self.fmt_money(r[6] or 0), r[7]
            ))

        if self.user_type == "Admin":
            ctl = tk.Frame(parent, bg=self.colors["background"])
            ctl.pack(fill="x", padx=12, pady=6)
            for status in ("confirmed", "in_progress", "delivered", "cancelled"):
                tk.Button(ctl, text=status.replace("_", " ").title(),
                          bg=self.colors["secondary"], fg="white",
                          relief="flat", padx=8, pady=4,
                          command=lambda s=status, t=tree:
                              self._set_bulk_status(t, s)
                          ).pack(side="left", padx=2)

    def _set_bulk_status(self, tree, status):
        sel = tree.selection()
        if not sel:
            return
        bid = tree.item(sel[0])["values"][0]
        if self.update_bulk_order_status(bid, status):
            self.refresh_special()

    def _open_bulk_dialog(self):
        if not self.current_user:
            messagebox.showinfo("Login Required",
                                "Log in to submit a bulk order.")
            return
        d = tk.Toplevel(self.root); d.title("📦 Bulk / Event Order")
        d.geometry("520x600"); d.transient(self.root); d.grab_set()
        tk.Label(d, text="📦 Bulk / Event Order",
                 font=("Georgia", 14, "bold"),
                 bg=self.colors["background"]).pack(pady=8)

        fields = {}
        for label, default in (
            ("Department", ""),
            ("Billing code", ""),
            ("Event date (YYYY-MM-DD)",
             (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")),
            ("Event location", ""),
            ("Attendees (number)", "20"),
        ):
            tk.Label(d, text=label,
                     bg=self.colors["background"]).pack(anchor="w",
                                                         padx=18, pady=(6, 0))
            e = tk.Entry(d, width=54); e.insert(0, default); e.pack(padx=18)
            fields[label] = e

        tk.Label(d, text="Items (one per line: 'Item Name x Qty')",
                 bg=self.colors["background"]).pack(anchor="w",
                                                     padx=18, pady=(6, 0))
        items_t = tk.Text(d, width=58, height=8); items_t.pack(padx=18)
        items_t.insert("1.0", "Croissant x 30\nCoffee x 30")
        tk.Label(d, text="Notes", bg=self.colors["background"]
                 ).pack(anchor="w", padx=18, pady=(6, 0))
        notes_e = tk.Entry(d, width=54); notes_e.pack(padx=18)

        def submit():
            try:
                event_date = fields["Event date (YYYY-MM-DD)"].get().strip()
                datetime.strptime(event_date, "%Y-%m-%d")
                items = {}
                for ln in items_t.get("1.0", "end").splitlines():
                    ln = ln.strip()
                    if not ln:
                        continue
                    name, qty = ln.rsplit("x", 1)
                    name = name.strip()
                    if not self._product_info(name):
                        raise ValueError(f"Unknown product: {name}")
                    items[name] = int(qty.strip())
                if not items:
                    raise ValueError("Add at least one item")
                bid = self.create_bulk_order(
                    items,
                    department=fields["Department"].get(),
                    billing_code=fields["Billing code"].get(),
                    event_date=event_date,
                    event_location=fields["Event location"].get(),
                    attendees=fields["Attendees (number)"].get() or 0,
                    notes=notes_e.get(),
                )
                if not bid:
                    raise RuntimeError("Could not create bulk order")
                messagebox.showinfo("Submitted",
                                    f"Bulk order #{bid} submitted. "
                                    "An admin will confirm shortly.")
                self.refresh_special()
                d.destroy()
            except Exception as e:
                logger.exception("Bulk dialog submit failed")
                messagebox.showerror("Error", str(e), parent=d)

        tk.Button(d, text="Submit",
                  bg=self.colors["success"], fg="white", relief="flat",
                  padx=20, pady=6, command=submit
                  ).pack(side="right", padx=18, pady=12)
        tk.Button(d, text="Cancel",
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  padx=20, pady=6, command=d.destroy
                  ).pack(side="right", pady=12)

    def _render_recurring_orders(self, parent):
        top = tk.Frame(parent, bg=self.colors["background"])
        top.pack(fill="x", padx=12, pady=8)
        tk.Button(top, text="🔁 New Standing Order from Cart",
                  font=("Arial", 11, "bold"),
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=14, pady=6,
                  command=self._open_new_recurring_dialog).pack(side="left")

        cols = ("id", "user", "name", "schedule", "next_run",
                "last_run", "active")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c, w in zip(cols, (50, 120, 160, 130, 110, 110, 60)):
            tree.heading(c, text=c.title()); tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, padx=12, pady=6)

        user_filter = None if self.user_type == "Admin" else self.current_user
        for r in self.list_recurring_orders(user=user_filter):
            tree.insert("", "end", values=(
                r[0], r[1], r[2] or "—", r[4], r[5] or "—",
                r[6] or "—", "✓" if r[7] else "✗",
            ))

        ctl = tk.Frame(parent, bg=self.colors["background"])
        ctl.pack(fill="x", padx=12, pady=6)
        tk.Button(ctl, text="🔁 Toggle Active",
                  bg=self.colors["accent"], fg=self.colors["text"],
                  relief="flat", padx=10, pady=4,
                  command=lambda t=tree:
                      (self.toggle_recurring(
                          t.item(t.selection()[0])["values"][0])
                       if t.selection() else None,
                       self.refresh_special())
                  ).pack(side="left", padx=4)
        tk.Button(ctl, text="🗑 Delete",
                  bg=self.colors["danger"], fg="white", relief="flat",
                  padx=10, pady=4,
                  command=lambda t=tree:
                      (self.delete_recurring(
                          t.item(t.selection()[0])["values"][0])
                       if t.selection() else None,
                       self.refresh_special())
                  ).pack(side="left", padx=4)

    def _open_new_recurring_dialog(self):
        if not self.current_user:
            messagebox.showinfo("Login Required",
                                "Log in to create a standing order.")
            return
        if not self.cart:
            messagebox.showinfo("Empty Cart",
                                "Add items first, then schedule them.")
            return
        d = tk.Toplevel(self.root); d.title("🔁 New Standing Order")
        d.geometry("420x320"); d.transient(self.root); d.grab_set()
        tk.Label(d, text="🔁 Standing Order",
                 font=("Georgia", 14, "bold"),
                 bg=self.colors["background"]).pack(pady=8)
        tk.Label(d, text=f"Items: {sum(self.cart.values())} units",
                 bg=self.colors["background"]).pack(pady=2)

        tk.Label(d, text="Name (optional)",
                 bg=self.colors["background"]).pack(anchor="w", padx=20)
        name_e = tk.Entry(d, width=40)
        name_e.insert(0, "Friday breakfast")
        name_e.pack(padx=20)

        tk.Label(d, text="Schedule",
                 bg=self.colors["background"]).pack(anchor="w", padx=20, pady=(8, 0))
        sched_var = tk.StringVar(value="weekly:Fri")
        ttk.Combobox(d, textvariable=sched_var, width=37,
                     values=["daily", "weekly:Mon", "weekly:Tue",
                             "weekly:Wed", "weekly:Thu", "weekly:Fri",
                             "weekly:Mon,Wed,Fri", "monthly:1",
                             "monthly:15"]).pack(padx=20)

        def submit():
            rid = self.create_recurring_order(dict(self.cart),
                                              sched_var.get(),
                                              name=name_e.get())
            if rid:
                messagebox.showinfo("Created",
                                    f"Standing order #{rid} active. "
                                    f"Next run: "
                                    f"{self._compute_next_run(sched_var.get()) or '—'}.")
                self.refresh_special()
                d.destroy()
            else:
                messagebox.showerror("Error",
                                     "Could not create standing order.",
                                     parent=d)

        tk.Button(d, text="Save",
                  bg=self.colors["success"], fg="white", relief="flat",
                  padx=20, pady=6, command=submit
                  ).pack(side="right", padx=20, pady=15)
        tk.Button(d, text="Cancel",
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  padx=20, pady=6, command=d.destroy
                  ).pack(side="right", pady=15)

    def _render_kitchen_display(self, parent):
        if self.user_type not in ("Admin", "Staff"):
            tk.Label(parent,
                     text="🔒 Kitchen display is for staff/admin.",
                     bg=self.colors["background"]).pack(pady=40)
            return
        top = tk.Frame(parent, bg=self.colors["background"])
        top.pack(fill="x", padx=8, pady=6)
        tk.Label(top, text="🍳 Kitchen Display",
                 font=("Georgia", 14, "bold"),
                 bg=self.colors["background"]).pack(side="left")
        tk.Button(top, text="🔄 Refresh",
                  bg=self.colors["accent"], fg=self.colors["text"],
                  relief="flat", padx=10, pady=4,
                  command=self.refresh_special).pack(side="right", padx=6)

        grid = tk.Frame(parent, bg=self.colors["background"])
        grid.pack(fill="both", expand=True, padx=8, pady=6)
        cols = [("queued", "📥 Queued", self.colors["secondary"]),
                ("prepping", "🥐 In Prep", self.colors["primary"]),
                ("ready", "✅ Ready", self.colors["success"])]
        col_frames = {}
        for key, label, color in cols:
            frame = tk.LabelFrame(grid, text=label,
                                   bg=self.colors["background"], fg=color,
                                   font=("Arial", 11, "bold"))
            frame.pack(side="left", fill="both", expand=True, padx=4)
            col_frames[key] = frame

        for r in self.list_preorders(include_completed=False):
            pid, order_id, user, items_json, collection_time, status, total, *_ = r
            try:
                items = json.loads(items_json or "{}")
            except Exception:
                items = {}
            stage = self.get_kitchen_stage(pid)
            if stage not in col_frames:
                stage = "queued"
            card = tk.Frame(col_frames[stage], bg=self.colors["card"],
                             relief="ridge", bd=2)
            card.pack(fill="x", padx=6, pady=4)
            tk.Label(card,
                     text=f"#{order_id}  •  {collection_time}",
                     font=("Arial", 11, "bold"),
                     bg=self.colors["card"]).pack(anchor="w", padx=6, pady=(4, 0))
            tk.Label(card, text=f"{user}",
                     bg=self.colors["card"],
                     fg=self.colors["text"]).pack(anchor="w", padx=6)
            for n, q in items.items():
                tk.Label(card, text=f"  • {n} × {q}",
                         font=("Courier", 9),
                         bg=self.colors["card"]).pack(anchor="w", padx=10)
            row = tk.Frame(card, bg=self.colors["card"])
            row.pack(fill="x", padx=4, pady=4)
            if stage == "queued":
                tk.Button(row, text="▶ Start",
                          bg=self.colors["primary"], fg="white",
                          relief="flat", padx=8, pady=2,
                          command=lambda pid=pid:
                              (self.set_kitchen_stage(pid, "prepping"),
                               self.refresh_special())).pack(side="left", padx=2)
            elif stage == "prepping":
                tk.Button(row, text="✓ Ready",
                          bg=self.colors["success"], fg="white",
                          relief="flat", padx=8, pady=2,
                          command=lambda pid=pid:
                              (self.set_kitchen_stage(pid, "ready"),
                               self.refresh_special())).pack(side="left", padx=2)
            elif stage == "ready":
                tk.Button(row, text="📦 Mark Collected",
                          bg=self.colors["secondary"], fg="white",
                          relief="flat", padx=8, pady=2,
                          command=lambda pid=pid:
                              (self.update_preorder_status(pid, "collected"),
                               self.refresh_special())).pack(side="left", padx=2)
            tk.Label(row, text=f"  £{total or 0:.2f}",
                     bg=self.colors["card"]).pack(side="right", padx=4)

    def _render_feedback_view(self, parent):
        top = tk.Frame(parent, bg=self.colors["background"])
        top.pack(fill="x", padx=8, pady=6)
        tk.Label(top, text="💬 Customer Feedback",
                 font=("Georgia", 14, "bold"),
                 bg=self.colors["background"]).pack(side="left")
        tk.Button(top, text="💬 Send Feedback",
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10, pady=4,
                  command=lambda: self._open_feedback_dialog()
                  ).pack(side="right", padx=4)
        if self.user_type == "Admin":
            tk.Button(top, text="🛠 Open admin queue",
                      bg=self.colors["secondary"], fg="white", relief="flat",
                      padx=10, pady=4,
                      command=self._open_feedback_admin
                      ).pack(side="right", padx=4)

        cols = ("id", "user", "category", "subject", "rating",
                "ticket", "status", "when")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c, w in zip(cols, (40, 130, 130, 220, 60, 110, 80, 130)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=6)
        user_filter = None if self.user_type == "Admin" else self.current_user
        for r in self.list_feedback():
            if user_filter and r[1] != user_filter:
                continue
            tree.insert("", "end", values=(
                r[0], r[1] or "—", r[3] or "—", r[4] or "—",
                r[6] or "—", r[7] or "—", r[8],
                r[10],
            ))

