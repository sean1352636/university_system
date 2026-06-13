"""POSTabMixin — auto-split from bakery_shop.py."""
from education_system.university_system.modules.domain.commerce.bakery_shop._common import *  # noqa: F401,F403


class POSTabMixin:
    CAKE_SIZES = ["6\" round (serves 8)", "8\" round (serves 12)",
                  "10\" round (serves 20)", "1/4 sheet (serves 25)",
                  "1/2 sheet (serves 50)"]

    CAKE_FLAVOURS = ["Chocolate", "Vanilla", "Lemon", "Red Velvet",
                     "Carrot", "Funfetti", "Coffee"]

    CAKE_FILLINGS = ["None", "Buttercream", "Ganache", "Cream cheese",
                     "Jam", "Lemon curd"]

    FREQ_DAYS = {"weekly": 7, "biweekly": 14, "monthly": 30}

    def build_pos_tab(self):
        panels = [
            ("🟦 Tile POS",          self._build_tilepos_panel),
            ("💵 Split-tender",      self._build_split_panel),
            ("🪪 Campus Card",       self._build_campus_panel),
            ("⭐ Loyalty Stamps",    self._build_stamps_panel),
            ("⏰ Happy Hours",       self._build_happy_panel),
            ("🎁 Combos",            self._build_combos_panel),
            ("🧺 Catering Trays",    self._build_catering_panel),
            ("🔐 Void / Quick Refund", self._build_void_panel),
            ("💰 Tip Pool",          self._build_tippool_panel),
            ("📡 Offline Mode",      self._build_offline_panel),
            ("🕒 Pickup Slots",      self._build_slots_panel),
            ("🎂 Cake Builder",      self._build_cakebuilder_panel),
            ("✉️ Notifications",     self._build_notif_panel),
            ("💍 Event Quotes",      self._build_quote_panel),
            ("📦 Subscriptions",     self._build_subs_panel),
        ]
        sub, self._pos_panels = self._lazy_subnotebook(
            self.pos_tab, panels, "POS")
        self.pos_sub = sub

    def _build_tilepos_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Label(top, text="Category:", bg=bg,
                 font=("Arial", 12, "bold")).pack(side="left")
        self._tilepos_cat = tk.StringVar(value="All")
        cats = ["All"] + list(self.products.keys())
        for cat in cats:
            tk.Radiobutton(top, text=cat, variable=self._tilepos_cat, value=cat,
                           indicatoron=False, width=10, height=2,
                           bg=self.colors["accent"], relief="flat",
                           font=("Arial", 11, "bold"),
                           command=self._tilepos_refresh).pack(side="left", padx=3)
        self._tilepos_search = tk.StringVar()
        e = tk.Entry(top, textvariable=self._tilepos_search,
                     font=("Arial", 12), width=18)
        e.pack(side="right", padx=4)
        tk.Label(top, text="Search:", bg=bg).pack(side="right")
        self._tilepos_search.trace_add("write",
                                        lambda *_: self._tilepos_refresh())

        main = tk.Frame(parent, bg=bg); main.pack(fill="both", expand=True,
                                                  padx=10, pady=6)
        # left tiles
        left = tk.Frame(main, bg=bg); left.pack(side="left", fill="both", expand=True)
        cnv = tk.Canvas(left, bg=bg, highlightthickness=0)
        sb = ttk.Scrollbar(left, orient="vertical", command=cnv.yview)
        self._tilepos_inner = tk.Frame(cnv, bg=bg)
        self._tilepos_inner.bind("<Configure>",
            lambda e: cnv.configure(scrollregion=cnv.bbox("all")))
        cnv.create_window((0, 0), window=self._tilepos_inner, anchor="nw")
        cnv.configure(yscrollcommand=sb.set)
        cnv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # right: ticket
        right = tk.Frame(main, bg=bg, width=320); right.pack(side="right", fill="y")
        right.pack_propagate(False)
        tk.Label(right, text="Ticket", bg=bg,
                 font=("Arial", 14, "bold")).pack(pady=4)
        self._tilepos_ticket_tree = ttk.Treeview(
            right, columns=("item", "qty", "line"),
            show="headings", height=18)
        for c, h, w in [("item", "Item", 160), ("qty", "Qty", 50),
                        ("line", "Line", 80)]:
            self._tilepos_ticket_tree.heading(c, text=h)
            self._tilepos_ticket_tree.column(c, width=w, anchor="w")
        self._tilepos_ticket_tree.pack(fill="both", expand=True, padx=6)
        self._tilepos_total_lbl = tk.Label(right, text="Total: £0.00",
                                            font=("Arial", 14, "bold"), bg=bg)
        self._tilepos_total_lbl.pack(pady=6)
        btns = tk.Frame(right, bg=bg); btns.pack(fill="x", padx=6, pady=4)
        tk.Button(btns, text="− Remove", command=self._tilepos_remove,
                  relief="flat").pack(side="left", padx=2)
        tk.Button(btns, text="Clear", command=self._tilepos_clear,
                  relief="flat").pack(side="left", padx=2)
        tk.Button(right, text="💵 Pay (split-tender)",
                  command=self._tilepos_pay,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  font=("Arial", 12, "bold"), pady=10).pack(fill="x", padx=6, pady=4)
        tk.Button(right, text="➕ Send to cart",
                  command=self._tilepos_send_to_cart,
                  bg=self.colors["accent"], relief="flat",
                  font=("Arial", 11), pady=6).pack(fill="x", padx=6, pady=2)

        self._tilepos_ticket = {}
        self._tilepos_refresh()

    def _tilepos_refresh(self):
        for w in self._tilepos_inner.winfo_children():
            w.destroy()
        cat_sel = self._tilepos_cat.get()
        q = (self._tilepos_search.get() or "").strip().lower()
        col = 0; row = 0
        for cat, items in self.products.items():
            if cat_sel != "All" and cat != cat_sel:
                continue
            for it, meta in items.items():
                if q and q not in it.lower():
                    continue
                price = meta.get("price", 0.0)
                emoji = meta.get("emoji", "🍞")
                btn = tk.Button(
                    self._tilepos_inner,
                    text=f"{emoji}\n{it}\n£{price:.2f}",
                    width=14, height=4, relief="raised",
                    bg=self.colors["secondary"],
                    fg=self.colors["text"],
                    font=("Arial", 11, "bold"),
                    cursor="hand2",
                    command=lambda i=it: self._tilepos_add(i),
                )
                btn.grid(row=row, column=col, padx=4, pady=4)
                col += 1
                if col >= 5:
                    col = 0; row += 1
        self._tilepos_refresh_ticket()

    def _tilepos_add(self, item):
        self._tilepos_ticket[item] = self._tilepos_ticket.get(item, 0) + 1
        self._tilepos_refresh_ticket()

    def _tilepos_remove(self):
        sel = self._tilepos_ticket_tree.focus()
        if not sel:
            return
        item = self._tilepos_ticket_tree.item(sel, "values")[0]
        if item in self._tilepos_ticket:
            self._tilepos_ticket[item] -= 1
            if self._tilepos_ticket[item] <= 0:
                del self._tilepos_ticket[item]
        self._tilepos_refresh_ticket()

    def _tilepos_clear(self):
        self._tilepos_ticket = {}
        self._tilepos_refresh_ticket()

    def _tilepos_refresh_ticket(self):
        tv = self._tilepos_ticket_tree
        tv.delete(*tv.get_children())
        total = 0.0
        for item, qty in self._tilepos_ticket.items():
            price = 0.0
            for cat, items in self.products.items():
                if item in items:
                    price = items[item].get("price", 0.0); break
            line = price * qty
            total += line
            tv.insert("", "end", values=(item, qty, f"£{line:.2f}"))
        self._tilepos_total_lbl.config(text=f"Total: £{total:.2f}")
        self._tilepos_total = total

    def _tilepos_send_to_cart(self):
        if not self._tilepos_ticket:
            return
        for item, qty in self._tilepos_ticket.items():
            self.cart[item] = self.cart.get(item, 0) + qty
        self._tilepos_clear()
        try:
            self.refresh_cart(); self.update_cart_tab_title()
        except Exception:
            pass
        self.set_status("Tickets sent to cart.")

    def _tilepos_pay(self):
        if not self._tilepos_ticket:
            messagebox.showinfo("Pay", "Ticket is empty.", parent=self.root)
            return
        total = self._tilepos_total
        self._split_tender_dialog(total, list(self._tilepos_ticket.items()))

    def _build_split_panel(self, parent):
        bg = self.colors["background"]
        info = tk.Label(parent,
            text="Split-tender accepts multiple payment methods on one order.\n"
                 "Methods: Cash, Card, Campus Card, Meal Swipe, Gift Card.\n"
                 "Use the Tile POS to start a sale, or use the manual dialog below.",
            bg=bg, font=("Arial", 11), justify="left")
        info.pack(anchor="w", padx=14, pady=10)
        tk.Button(parent, text="🧾 Open split-tender dialog (manual amount)",
                  command=self._split_manual,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  font=("Arial", 12, "bold"),
                  padx=14, pady=10).pack(padx=14, pady=10)
        tk.Label(parent, text="Recent split-tender orders",
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
        amt = simpledialog.askfloat("Split-tender",
                                    "Total amount to charge (£):",
                                    minvalue=0.01, parent=self.root)
        if not amt:
            return
        self._split_tender_dialog(amt, [])

    def _split_tender_dialog(self, total, items):
        d = tk.Toplevel(self.root); d.title("Split-tender payment")
        d.geometry("520x520"); d.transient(self.root); d.grab_set()
        bg = self.colors["background"]; d.configure(bg=bg)

        tk.Label(d, text=f"Total due: £{total:.2f}",
                 font=("Arial", 16, "bold"), bg=bg).pack(pady=10)
        rem_var = tk.StringVar(value=f"Remaining: £{total:.2f}")
        tk.Label(d, textvariable=rem_var, font=("Arial", 12, "bold"),
                 fg=self.colors["primary"], bg=bg).pack()

        splits = []
        list_frame = tk.Frame(d, bg=bg); list_frame.pack(fill="both", expand=True,
                                                          padx=14, pady=6)
        cols = ("method", "amount", "ref")
        tv = ttk.Treeview(list_frame, columns=cols, show="headings", height=8)
        for c, h, w in [("method", "Method", 140), ("amount", "Amount", 100),
                        ("ref", "Reference", 220)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True)

        def update_rem():
            paid = sum(s["amount"] for s in splits)
            rem = total - paid
            rem_var.set(f"Remaining: £{rem:.2f}")
            return rem

        add_frame = tk.Frame(d, bg=bg); add_frame.pack(fill="x", padx=14, pady=6)
        tk.Label(add_frame, text="Method:", bg=bg).grid(row=0, column=0, sticky="e")
        m_var = tk.StringVar(value="Cash")
        ttk.Combobox(add_frame, textvariable=m_var,
                     values=["Cash", "Card", "Campus Card", "Meal Swipe", "Gift Card"],
                     state="readonly", width=14).grid(row=0, column=1, padx=4)
        tk.Label(add_frame, text="Amount £:", bg=bg).grid(row=0, column=2, sticky="e")
        a_var = tk.StringVar(value=f"{total:.2f}")
        tk.Entry(add_frame, textvariable=a_var, width=10).grid(row=0, column=3, padx=4)
        tk.Label(add_frame, text="Ref:", bg=bg).grid(row=0, column=4, sticky="e")
        r_var = tk.StringVar()
        tk.Entry(add_frame, textvariable=r_var, width=14).grid(row=0, column=5, padx=4)

        def add_split():
            try:
                a = float(a_var.get())
            except ValueError:
                messagebox.showerror("Split", "Amount must be numeric.",
                                     parent=d); return
            if a <= 0:
                return
            s = {"method": m_var.get(), "amount": a, "ref": r_var.get()}
            splits.append(s)
            tv.insert("", "end", values=(s["method"], f"£{a:.2f}", s["ref"]))
            rem = update_rem()
            a_var.set(f"{max(rem, 0):.2f}"); r_var.set("")

        tk.Button(add_frame, text="+ Add", command=add_split,
                  bg=self.colors["accent"], relief="flat").grid(row=0, column=6,
                                                                  padx=4)

        def remove_sel():
            sel = tv.focus()
            if not sel:
                return
            idx = tv.index(sel)
            tv.delete(sel)
            splits.pop(idx)
            update_rem()

        def commit():
            rem = update_rem()
            if abs(rem) > 0.01:
                messagebox.showerror("Split",
                                     f"Cannot commit — £{rem:.2f} unpaid.",
                                     parent=d); return
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            order_id = f"POS-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            items_d = {i: {"quantity": q,
                           "price": next((it[i]["price"] for it in self.products.values()
                                          if i in it), 0.0)}
                       for i, q in (items or [])}
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_orders "
                    "(order_id, timestamp, username, user_type, items_json, "
                    "subtotal, discount, total, payment_method, "
                    "split_payments_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (order_id, now, self.current_user or "POS",
                     self.user_type, json.dumps(items_d),
                     total, 0.0, total, "split",
                     json.dumps(splits)),
                )
                # Decrement campus card balance/swipes for matching splits.
                for s in splits:
                    if s["method"] in ("Campus Card", "Meal Swipe") and s.get("ref"):
                        if s["method"] == "Meal Swipe":
                            conn.execute(
                                "UPDATE bakery_campus_cards SET "
                                "meal_swipes = MAX(0, meal_swipes - 1), "
                                "updated_at=? WHERE card_id=?",
                                (now, s["ref"]))
                            conn.execute(
                                "INSERT INTO bakery_campus_card_txns "
                                "(card_id, txn_type, amount, swipes, "
                                "order_id, timestamp) VALUES (?,?,?,?,?,?)",
                                (s["ref"], "swipe", 0.0, 1, order_id, now))
                        else:
                            conn.execute(
                                "UPDATE bakery_campus_cards SET "
                                "balance = balance - ?, updated_at=? "
                                "WHERE card_id=?",
                                (s["amount"], now, s["ref"]))
                            conn.execute(
                                "INSERT INTO bakery_campus_card_txns "
                                "(card_id, txn_type, amount, order_id, "
                                "timestamp) VALUES (?,?,?,?,?)",
                                (s["ref"], "spend", s["amount"], order_id, now))
                conn.commit()
            finally:
                conn.close()
            d.destroy()
            if hasattr(self, "_tilepos_ticket"):
                self._tilepos_clear()
            messagebox.showinfo("Paid",
                                f"Order {order_id} paid in full.",
                                parent=self.root)
            self._split_refresh()

        btns = tk.Frame(d, bg=bg); btns.pack(fill="x", padx=14, pady=10)
        tk.Button(btns, text="− Remove split", command=remove_sel,
                  relief="flat").pack(side="left")
        tk.Button(btns, text="Cancel", command=d.destroy,
                  relief="flat").pack(side="right", padx=4)
        tk.Button(btns, text="✅ Commit payment", command=commit,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=14, pady=6,
                  font=("Arial", 11, "bold")).pack(side="right")

    def _build_campus_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="+ Issue card", command=self._campus_issue,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="💷 Top up", command=self._campus_topup,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="🍽 Add meal swipes",
                  command=self._campus_add_swipes,
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._campus_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)

        cols = ("card", "user", "balance", "swipes", "active", "updated")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c, h, w in [("card", "Card ID", 140), ("user", "User", 140),
                        ("balance", "Balance", 100), ("swipes", "Swipes", 80),
                        ("active", "Active", 70), ("updated", "Updated", 150)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="x", padx=10, pady=6)
        self._campus_tree = tv

        tk.Label(parent, text="Recent transactions",
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
        cid = simpledialog.askstring("Issue card", "Card ID (e.g. S12345):",
                                     parent=self.root)
        if not cid:
            return
        user = simpledialog.askstring("Issue card", "Linked user (optional):",
                                      parent=self.root) or ""
        bal = simpledialog.askfloat("Issue card", "Opening balance £:",
                                    initialvalue=0.0, parent=self.root) or 0.0
        sw = simpledialog.askinteger("Issue card", "Meal swipes:",
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
        amt = simpledialog.askfloat("Top up", f"Add £ to {cid}:",
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
        n = simpledialog.askinteger("Swipes", f"Add swipes to {cid}:",
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

    def _build_stamps_panel(self, parent):
        bg = self.colors["background"]
        tk.Label(parent,
                 text="Loyalty stamp cards — buy 9 in a category, 10th free.",
                 bg=bg, font=("Arial", 11, "italic")).pack(anchor="w",
                                                            padx=12, pady=6)
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=4)
        tk.Button(top, text="+ Add stamp", command=self._stamp_add,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="🎁 Redeem free", command=self._stamp_redeem,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._stamps_refresh,
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
        u = simpledialog.askstring("Stamp", "User:", parent=self.root,
                                   initialvalue=self.current_user or "")
        if not u:
            return
        cats = list(self.products.keys())
        d = tk.Toplevel(self.root); d.title("Add stamp")
        d.transient(self.root); d.grab_set()
        tk.Label(d, text="Category:").grid(row=0, column=0, padx=8, pady=8, sticky="e")
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
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat", padx=14).grid(row=1, column=0,
                                                            columnspan=2, pady=10)

    def _stamp_redeem(self):
        sel = self._stamps_tree.focus()
        if not sel:
            return
        u, c, cnt, *_ = self._stamps_tree.item(sel, "values")
        cnt = int(cnt)
        if cnt < 10:
            messagebox.showinfo("Redeem",
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
        messagebox.showinfo("Redeem", f"Free {c} item issued to {u}.",
                            parent=self.root)
        self._stamps_refresh()

    def _build_happy_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="+ Add rule", command=self._happy_add,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="✖ Disable selected",
                  command=lambda: self._happy_toggle(0),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="✓ Enable selected",
                  command=lambda: self._happy_toggle(1),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._happy_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)

        cols = ("id", "name", "start", "end", "days", "category", "pct", "active")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=16)
        for c, h, w in [("id", "ID", 60), ("name", "Name", 160),
                        ("start", "Start", 80), ("end", "End", 80),
                        ("days", "Days", 130), ("category", "Category", 110),
                        ("pct", "%", 60), ("active", "Active", 70)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._happy_tree = tv
        self._happy_refresh()

    def _happy_refresh(self):
        tv = self._happy_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, name, start_time, end_time, days_of_week, "
                "category, discount_pct, active FROM bakery_happy_hours "
                "ORDER BY id DESC").fetchall()
        finally:
            conn.close()
        for rid, n, s, e, d, c, p, a in rows:
            tv.insert("", "end", iid=str(rid),
                      values=(rid, n, s, e, d or "all", c or "all",
                              f"{p:g}%", "yes" if a else "no"))

    def _happy_add(self):
        cats = ["all"] + list(self.products.keys())
        d = tk.Toplevel(self.root); d.title("Happy hour")
        d.transient(self.root); d.grab_set()
        fields = [("Name", "Afternoon Pastry"),
                  ("Start (HH:MM)", "14:00"),
                  ("End (HH:MM)", "16:00"),
                  ("Days (all or Mon,Tue,...)", "all"),
                  ("Category", "all"),
                  ("Discount %", "20")]
        vars_ = []
        for i, (lbl, val) in enumerate(fields):
            tk.Label(d, text=lbl + ":").grid(row=i, column=0, padx=8,
                                             pady=4, sticky="e")
            v = tk.StringVar(value=val); vars_.append(v)
            if lbl == "Category":
                ttk.Combobox(d, textvariable=v, values=cats, state="readonly",
                             width=18).grid(row=i, column=1, padx=8, pady=4,
                                            sticky="w")
            else:
                tk.Entry(d, textvariable=v, width=22).grid(row=i, column=1,
                                                            padx=8, pady=4, sticky="w")
        def save():
            try:
                pct = float(vars_[5].get())
            except ValueError:
                messagebox.showerror("Happy hour", "Bad %.", parent=d); return
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_happy_hours "
                    "(name, start_time, end_time, days_of_week, category, "
                    "discount_pct, active, created_at) "
                    "VALUES (?,?,?,?,?,?,1,?)",
                    (vars_[0].get(), vars_[1].get(), vars_[2].get(),
                     vars_[3].get(), vars_[4].get(), pct, now))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._happy_refresh()
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).grid(row=len(fields), column=0, columnspan=2, pady=10)

    def _happy_toggle(self, active):
        sel = self._happy_tree.focus()
        if not sel:
            return
        conn = self._connect()
        try:
            conn.execute("UPDATE bakery_happy_hours SET active=? WHERE id=?",
                         (active, int(sel)))
            conn.commit()
        finally:
            conn.close()
        self._happy_refresh()

    def _build_combos_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="+ Add combo", command=self._combo_add,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="✖ Disable", command=lambda: self._combo_toggle(0),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="✓ Enable", command=lambda: self._combo_toggle(1),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._combos_refresh,
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
        d = tk.Toplevel(self.root); d.title("New combo")
        d.transient(self.root); d.grab_set(); d.geometry("520x440")
        tk.Label(d, text="Name:").grid(row=0, column=0, padx=8, pady=6, sticky="e")
        n_var = tk.StringVar(value="Coffee + Pastry")
        tk.Entry(d, textvariable=n_var, width=30).grid(row=0, column=1, padx=8, pady=6)
        tk.Label(d, text="Price £:").grid(row=1, column=0, padx=8, pady=6, sticky="e")
        p_var = tk.StringVar(value="4.50")
        tk.Entry(d, textvariable=p_var, width=10).grid(row=1, column=1, padx=8, pady=6, sticky="w")
        tk.Label(d, text="Items:").grid(row=2, column=0, padx=8, pady=6, sticky="ne")
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
        tk.Button(d, text="+ row", command=add_row,
                  relief="flat").grid(row=3, column=1, sticky="w", padx=8)
        def save():
            try:
                price = float(p_var.get())
            except ValueError:
                messagebox.showerror("Combo", "Bad price.", parent=d); return
            items = {}
            for iv, qv in items_vars:
                try:
                    q = int(qv.get())
                except ValueError:
                    continue
                if q > 0:
                    items[iv.get()] = items.get(iv.get(), 0) + q
            if not items:
                messagebox.showerror("Combo", "No items.", parent=d); return
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
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
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

    def _build_catering_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="+ Add tray", command=self._tray_add,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="🛒 Quick-add to cart", command=self._tray_to_cart,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="✖ Disable", command=lambda: self._tray_toggle(0),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="✓ Enable", command=lambda: self._tray_toggle(1),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._catering_refresh,
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
        d = tk.Toplevel(self.root); d.title("New catering tray")
        d.transient(self.root); d.grab_set(); d.geometry("520x500")
        tk.Label(d, text="Tray name:").grid(row=0, column=0, padx=8, pady=6, sticky="e")
        n_var = tk.StringVar(value="Mixed Pastry Tray (12)")
        tk.Entry(d, textvariable=n_var, width=30).grid(row=0, column=1, padx=8, pady=6)
        tk.Label(d, text="Serves:").grid(row=1, column=0, padx=8, pady=6, sticky="e")
        s_var = tk.StringVar(value="12")
        tk.Entry(d, textvariable=s_var, width=8).grid(row=1, column=1, padx=8, pady=6, sticky="w")
        tk.Label(d, text="Price £:").grid(row=2, column=0, padx=8, pady=6, sticky="e")
        p_var = tk.StringVar(value="30.00")
        tk.Entry(d, textvariable=p_var, width=10).grid(row=2, column=1, padx=8, pady=6, sticky="w")
        tk.Label(d, text="Items:").grid(row=3, column=0, padx=8, pady=6, sticky="ne")
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
        tk.Button(d, text="+ row", command=add_row,
                  relief="flat").grid(row=4, column=1, sticky="w", padx=8)
        def save():
            try:
                serves = int(s_var.get()); price = float(p_var.get())
            except ValueError:
                messagebox.showerror("Tray", "Numeric.", parent=d); return
            items = {}
            for iv, qv in rows_v:
                try:
                    q = int(qv.get())
                except ValueError:
                    continue
                if q > 0:
                    items[iv.get()] = items.get(iv.get(), 0) + q
            if not items:
                messagebox.showerror("Tray", "Add items.", parent=d); return
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
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
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

    def _build_void_panel(self, parent):
        bg = self.colors["background"]
        tk.Label(parent,
                 text="Voiding an order or issuing a quick refund requires a "
                      "manager PIN. Each event is audited below.",
                 bg=bg, font=("Arial", 11, "italic"),
                 justify="left").pack(anchor="w", padx=14, pady=8)
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=14, pady=4)
        tk.Button(top, text="🔑 Set / change manager PIN",
                  command=self._set_manager_pin,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="❌ Void order", command=self._void_order,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="💸 Quick refund",
                  command=self._quick_refund,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._void_refresh,
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
        u = simpledialog.askstring("Manager PIN", "Manager username:",
                                   parent=self.root)
        if not u:
            return
        pin = simpledialog.askstring("Manager PIN", f"New 4-digit PIN for {u}:",
                                     parent=self.root, show="*")
        if not pin or not pin.isdigit() or len(pin) < 4:
            messagebox.showerror("PIN", "PIN must be 4+ digits.",
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
        messagebox.showinfo("PIN", f"PIN set for {u}.", parent=self.root)

    def _verify_manager_pin(self):
        u = simpledialog.askstring("Manager PIN", "Manager username:",
                                   parent=self.root)
        if not u:
            return None
        pin = simpledialog.askstring("Manager PIN", f"PIN for {u}:",
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
        messagebox.showerror("PIN", "Invalid PIN.", parent=self.root)
        return None

    def _void_order(self):
        oid = simpledialog.askstring("Void", "Order ID to void:",
                                     parent=self.root)
        if not oid:
            return
        mgr = self._verify_manager_pin()
        if not mgr:
            return
        reason = simpledialog.askstring("Void", "Reason:", parent=self.root) or ""
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
        oid = simpledialog.askstring("Quick refund", "Order ID:",
                                     parent=self.root)
        if not oid:
            return
        amt = simpledialog.askfloat("Quick refund", "Amount £:",
                                    minvalue=0.01, parent=self.root)
        if not amt:
            return
        mgr = self._verify_manager_pin()
        if not mgr:
            return
        reason = simpledialog.askstring("Quick refund", "Reason:",
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

    def _build_tippool_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="▶ Start period", command=self._tippool_start,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="🧮 Distribute & close",
                  command=self._tippool_close,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._tippool_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)

        cols = ("id", "started", "ended", "total", "status", "distribution")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=16)
        for c, h, w in [("id", "ID", 50), ("started", "Started", 150),
                        ("ended", "Ended", 150), ("total", "Total tips", 110),
                        ("status", "Status", 80),
                        ("distribution", "Distribution", 360)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._tippool_tree = tv
        self._tippool_refresh()

    def _tippool_refresh(self):
        tv = self._tippool_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, started_at, ended_at, total_pool, status, "
                "distribution_json FROM bakery_tip_pool_periods "
                "ORDER BY id DESC LIMIT 50").fetchall()
        finally:
            conn.close()
        for rid, st, en, total, status, dist in rows:
            try:
                d = json.loads(dist) if dist else {}
                desc = ", ".join(f"{k}: £{v:.2f}" for k, v in d.items())
            except Exception:
                desc = dist or ""
            tv.insert("", "end", iid=str(rid),
                      values=(rid, st, en or "—",
                              f"£{(total or 0):.2f}", status, desc))

    def _tippool_start(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO bakery_tip_pool_periods "
                "(started_at, status) VALUES (?, 'open')", (now,))
            conn.commit()
        finally:
            conn.close()
        self._tippool_refresh()

    def _tippool_close(self):
        sel = self._tippool_tree.focus()
        if not sel:
            return
        # Sum tips in period; ask for staff list to split evenly.
        conn = self._connect()
        try:
            r = conn.execute(
                "SELECT started_at, status FROM bakery_tip_pool_periods "
                "WHERE id=?", (int(sel),)).fetchone()
            if not r or r[1] != "open":
                messagebox.showerror("Tip pool", "Not an open period.",
                                     parent=self.root); return
            started_at = r[0]
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            total = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM bakery_tips "
                "WHERE timestamp >= ? AND timestamp <= ?",
                (started_at, now)).fetchone()[0]
        finally:
            conn.close()
        staff = simpledialog.askstring(
            "Tip pool",
            f"Total £{total:.2f}. Staff to split among "
            "(comma-separated usernames):", parent=self.root)
        if not staff:
            return
        names = [s.strip() for s in staff.split(",") if s.strip()]
        if not names:
            return
        share = round(total / len(names), 2)
        dist = {n: share for n in names}
        # Fix rounding remainder onto first staff member.
        rem = round(total - share * len(names), 2)
        if rem and names:
            dist[names[0]] = round(dist[names[0]] + rem, 2)
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE bakery_tip_pool_periods SET ended_at=?, "
                "total_pool=?, distribution_json=?, closed_by=?, "
                "status='closed' WHERE id=?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 total, json.dumps(dist),
                 self.current_user or "system", int(sel)))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo("Tip pool",
                            "Distribution:\n" + "\n".join(
                                f"{n}: £{a:.2f}" for n, a in dist.items()),
                            parent=self.root)
        self._tippool_refresh()

    def _build_offline_panel(self, parent):
        bg = self.colors["background"]
        info = tk.Label(parent,
            text="Offline mode queues orders locally; they sync to the\n"
                 "central DB when you return online.",
            bg=bg, font=("Arial", 11, "italic"), justify="left")
        info.pack(anchor="w", padx=14, pady=8)
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=14, pady=6)
        self._offline_state_lbl = tk.Label(top, text="",
                                           font=("Arial", 12, "bold"), bg=bg)
        self._offline_state_lbl.pack(side="left", padx=8)
        tk.Button(top, text="Toggle offline mode",
                  command=self._offline_toggle,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="⇪ Sync queued now", command=self._offline_sync,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._offline_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)

        cols = ("id", "queued_at", "kind", "synced", "synced_at", "error")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=16)
        for c, h, w in [("id", "ID", 60), ("queued_at", "Queued", 150),
                        ("kind", "Kind", 100), ("synced", "Synced", 80),
                        ("synced_at", "Synced at", 150), ("error", "Error", 240)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=14, pady=6)
        self._offline_tree = tv
        self._offline_refresh()

    def _offline_state(self):
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT offline_mode FROM bakery_offline_state "
                "WHERE id=1").fetchone()
        finally:
            conn.close()
        return bool(row[0]) if row else False

    def _offline_refresh(self):
        on = self._offline_state()
        self._offline_state_lbl.config(
            text=f"Mode: {'OFFLINE' if on else 'ONLINE'}",
            fg=("#B00020" if on else "#1B7F3A"))
        tv = self._offline_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, queued_at, payload_kind, synced, synced_at, error "
                "FROM bakery_offline_queue ORDER BY id DESC LIMIT 200"
            ).fetchall()
        finally:
            conn.close()
        for rid, qa, kind, syn, sa, err in rows:
            tv.insert("", "end", values=(rid, qa, kind,
                                         "yes" if syn else "no",
                                         sa or "", err or ""))

    def _offline_toggle(self):
        on = self._offline_state()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO bakery_offline_state "
                "(id, offline_mode, last_toggled_at, toggled_by) "
                "VALUES (1, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                "offline_mode=excluded.offline_mode, "
                "last_toggled_at=excluded.last_toggled_at, "
                "toggled_by=excluded.toggled_by",
                (0 if on else 1, now, self.current_user or "system"))
            conn.commit()
        finally:
            conn.close()
        self._offline_refresh()

    def _offline_sync(self):
        if self._offline_state():
            messagebox.showinfo("Sync", "Still in OFFLINE mode — toggle first.",
                                parent=self.root); return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        n = 0
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, payload_kind, payload_json FROM bakery_offline_queue "
                "WHERE synced = 0 ORDER BY id").fetchall()
            for rid, kind, payload in rows:
                try:
                    if kind == "order":
                        data = json.loads(payload)
                        conn.execute(
                            "INSERT INTO bakery_orders "
                            "(order_id, timestamp, username, user_type, "
                            "items_json, subtotal, discount, total, "
                            "payment_method) VALUES (?,?,?,?,?,?,?,?,?)",
                            (data.get("order_id"),
                             data.get("timestamp", now),
                             data.get("username"),
                             data.get("user_type"),
                             json.dumps(data.get("items", {})),
                             data.get("subtotal", 0),
                             data.get("discount", 0),
                             data.get("total", 0),
                             data.get("payment_method", "offline")))
                    conn.execute(
                        "UPDATE bakery_offline_queue SET synced=1, synced_at=?, "
                        "error=NULL WHERE id=?", (now, rid))
                    n += 1
                except Exception as e:
                    conn.execute(
                        "UPDATE bakery_offline_queue SET error=? WHERE id=?",
                        (str(e)[:200], rid))
            conn.commit()
        finally:
            conn.close()
        self.set_status(f"Synced {n} queued items.")
        self._offline_refresh()

    def _build_slots_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="+ Generate slots (today)",
                  command=lambda: self._slots_generate(0),
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="+ Generate slots (tomorrow)",
                  command=lambda: self._slots_generate(1),
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="📚 Book selected", command=self._slots_book,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="✖ Release a booking",
                  command=self._slots_release,
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._slots_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        cols = ("id", "date", "time", "capacity", "booked", "remaining", "notes")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c, h, w in [("id", "ID", 50), ("date", "Date", 110),
                        ("time", "Time", 80), ("capacity", "Capacity", 90),
                        ("booked", "Booked", 90), ("remaining", "Remaining", 100),
                        ("notes", "Notes", 240)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._slots_tree = tv
        self._slots_refresh()

    def _slots_refresh(self):
        tv = self._slots_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, slot_date, slot_time, capacity, booked, notes "
                "FROM bakery_pickup_slots "
                "ORDER BY slot_date ASC, slot_time ASC LIMIT 500").fetchall()
        finally:
            conn.close()
        for rid, d, t, cap, bk, notes in rows:
            rem = (cap or 0) - (bk or 0)
            tag = "full" if rem <= 0 else ""
            tv.insert("", "end", iid=str(rid),
                      values=(rid, d, t, cap, bk, rem, notes or ""),
                      tags=(tag,))
        tv.tag_configure("full", background="#FFD9D9")

    def _slots_generate(self, day_offset):
        date = (datetime.now() + timedelta(days=day_offset)).strftime("%Y-%m-%d")
        capacity = simpledialog.askinteger("Capacity",
                                           "Capacity per 30-min slot:",
                                           initialvalue=3, minvalue=1,
                                           parent=self.root)
        if not capacity:
            return
        conn = self._connect()
        try:
            for hour in range(8, 18):
                for minute in (0, 30):
                    t = f"{hour:02d}:{minute:02d}"
                    conn.execute(
                        "INSERT OR IGNORE INTO bakery_pickup_slots "
                        "(slot_date, slot_time, capacity, booked) "
                        "VALUES (?,?,?,0)", (date, t, capacity))
            conn.commit()
        finally:
            conn.close()
        self._slots_refresh()

    def _slots_book(self):
        sel = self._slots_tree.focus()
        if not sel:
            return
        conn = self._connect()
        try:
            r = conn.execute(
                "SELECT capacity, booked FROM bakery_pickup_slots WHERE id=?",
                (int(sel),)).fetchone()
            if not r or r[1] >= r[0]:
                messagebox.showerror("Slot", "Slot is full.",
                                     parent=self.root); return
            conn.execute(
                "UPDATE bakery_pickup_slots SET booked = booked + 1 "
                "WHERE id=?", (int(sel),))
            conn.commit()
        finally:
            conn.close()
        self._slots_refresh()

    def _slots_release(self):
        sel = self._slots_tree.focus()
        if not sel:
            return
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE bakery_pickup_slots SET booked = MAX(0, booked - 1) "
                "WHERE id=?", (int(sel),))
            conn.commit()
        finally:
            conn.close()
        self._slots_refresh()

    def _build_cakebuilder_panel(self, parent):
        bg = self.colors["background"]
        tk.Label(parent, text="🎂 Custom Cake Builder",
                 bg=bg, font=("Georgia", 16, "bold")).pack(pady=8)
        tk.Button(parent, text="▶ Open builder",
                  command=self._cakebuilder_open,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  font=("Arial", 12, "bold"),
                  padx=14, pady=10).pack(pady=6)
        tk.Label(parent, text="Existing custom cake orders",
                 bg=bg, font=("Arial", 12, "bold")).pack(anchor="w",
                                                          padx=14, pady=6)
        cols = ("id", "user", "type", "size", "flavours",
                "collection", "price", "status")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c, h, w in [("id", "ID", 60), ("user", "User", 110),
                        ("type", "Type", 130), ("size", "Size", 160),
                        ("flavours", "Flavours", 160),
                        ("collection", "Collection", 110),
                        ("price", "Quoted £", 90),
                        ("status", "Status", 100)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=14, pady=6)
        self._cakebuilder_tree = tv
        self._cakebuilder_refresh()

    def _cakebuilder_refresh(self):
        tv = self._cakebuilder_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, user, cake_type, size, flavours, collection_date, "
                "quoted_price, status FROM bakery_custom_orders "
                "ORDER BY id DESC LIMIT 100").fetchall()
        finally:
            conn.close()
        for rid, u, ct, sz, fl, cd, qp, st in rows:
            tv.insert("", "end", values=(rid, u, ct or "", sz or "",
                                         fl or "", cd or "",
                                         f"£{(qp or 0):.2f}", st))

    def _cakebuilder_open(self):
        d = tk.Toplevel(self.root); d.title("Cake Builder")
        d.geometry("520x560"); d.transient(self.root); d.grab_set()
        bg = self.colors["background"]; d.configure(bg=bg)

        fields = {}
        def row(label, widget, r):
            tk.Label(d, text=label, bg=bg).grid(row=r, column=0,
                                                 padx=8, pady=6, sticky="e")
            widget.grid(row=r, column=1, padx=8, pady=6, sticky="w")

        size_v = tk.StringVar(value=self.CAKE_SIZES[0])
        row("Size:", ttk.Combobox(d, textvariable=size_v,
                                  values=self.CAKE_SIZES, state="readonly",
                                  width=28), 0)
        fields["size"] = size_v
        flav_v = tk.StringVar(value=self.CAKE_FLAVOURS[0])
        row("Flavour:", ttk.Combobox(d, textvariable=flav_v,
                                     values=self.CAKE_FLAVOURS, state="readonly",
                                     width=28), 1)
        fields["flavour"] = flav_v
        fill_v = tk.StringVar(value=self.CAKE_FILLINGS[0])
        row("Filling:", ttk.Combobox(d, textvariable=fill_v,
                                     values=self.CAKE_FILLINGS, state="readonly",
                                     width=28), 2)
        fields["filling"] = fill_v
        msg_v = tk.StringVar()
        row("Message on cake:", tk.Entry(d, textvariable=msg_v, width=30), 3)
        fields["message"] = msg_v
        diet_v = tk.StringVar()
        row("Dietary (eg. gluten-free):",
            tk.Entry(d, textvariable=diet_v, width=30), 4)
        fields["dietary"] = diet_v
        date_v = tk.StringVar(value=(datetime.now() + timedelta(days=3)
                                     ).strftime("%Y-%m-%d"))
        row("Collection date:",
            tk.Entry(d, textvariable=date_v, width=14), 5)
        fields["date"] = date_v
        email_v = tk.StringVar()
        row("Email:", tk.Entry(d, textvariable=email_v, width=30), 6)
        fields["email"] = email_v
        phone_v = tk.StringVar()
        row("Phone:", tk.Entry(d, textvariable=phone_v, width=20), 7)
        fields["phone"] = phone_v

        # Auto-quote based on size keyword
        def quote():
            sz = size_v.get().lower()
            if "serves 50" in sz: return 95.00
            if "serves 25" in sz: return 55.00
            if "serves 20" in sz: return 45.00
            if "serves 12" in sz: return 32.00
            return 22.00
        quote_lbl = tk.Label(d, text="", bg=bg, font=("Arial", 13, "bold"),
                             fg=self.colors["primary"])
        quote_lbl.grid(row=8, column=0, columnspan=2, pady=6)
        def refresh_quote(*_):
            quote_lbl.config(text=f"Auto-quoted price: £{quote():.2f}")
        size_v.trace_add("write", refresh_quote)
        refresh_quote()

        def save():
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            qprice = quote()
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_custom_orders "
                    "(user, cake_type, size, flavours, message_on_cake, "
                    "dietary_requirements, collection_date, contact_email, "
                    "contact_phone, quoted_price, status, created_at, "
                    "updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (self.current_user or "guest",
                     fields["filling"].get() and "Custom" or "Custom",
                     fields["size"].get(),
                     f"{fields['flavour'].get()} / {fields['filling'].get()}",
                     fields["message"].get(),
                     fields["dietary"].get(),
                     fields["date"].get(),
                     fields["email"].get(),
                     fields["phone"].get(),
                     qprice, "requested", now, now))
                conn.commit()
            finally:
                conn.close()
            messagebox.showinfo("Cake",
                                f"Order saved. Quoted £{qprice:.2f}.",
                                parent=d)
            d.destroy(); self._cakebuilder_refresh()
        tk.Button(d, text="✅ Submit order", command=save,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  font=("Arial", 12, "bold"),
                  padx=14, pady=8).grid(row=9, column=0, columnspan=2, pady=12)

    def _build_notif_panel(self, parent):
        bg = self.colors["background"]
        info = tk.Label(parent,
            text="Pickup-ready and order-status notifications. "
                 "Messages are queued here; an external worker would dispatch them.",
            bg=bg, font=("Arial", 11, "italic"), justify="left")
        info.pack(anchor="w", padx=14, pady=8)
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=14, pady=4)
        tk.Button(top, text="📨 Queue new notification",
                  command=self._notif_new,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="🚀 Mark selected sent",
                  command=lambda: self._notif_set("sent"),
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="✖ Mark failed",
                  command=lambda: self._notif_set("failed"),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._notif_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        cols = ("id", "queued", "channel", "recipient", "subject",
                "order", "status", "sent")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=16)
        for c, h, w in [("id", "ID", 50), ("queued", "Queued", 150),
                        ("channel", "Ch", 60), ("recipient", "To", 180),
                        ("subject", "Subject", 200),
                        ("order", "Order", 110), ("status", "Status", 80),
                        ("sent", "Sent", 150)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=14, pady=6)
        self._notif_tree = tv
        self._notif_refresh()

    def _notif_refresh(self):
        tv = self._notif_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, queued_at, channel, recipient, subject, "
                "related_order, status, sent_at FROM bakery_notifications "
                "ORDER BY id DESC LIMIT 200").fetchall()
        finally:
            conn.close()
        for rid, qa, ch, rcp, subj, oid, st, sa in rows:
            tag = {"sent": "ok", "failed": "bad"}.get(st, "")
            tv.insert("", "end", iid=str(rid),
                      values=(rid, qa, ch, rcp, subj or "",
                              oid or "", st, sa or ""), tags=(tag,))
        tv.tag_configure("ok", background="#E6F4EA")
        tv.tag_configure("bad", background="#FFD9D9")

    def _notif_new(self):
        d = tk.Toplevel(self.root); d.title("New notification")
        d.transient(self.root); d.grab_set()
        ch_var = tk.StringVar(value="sms")
        rcp_var = tk.StringVar()
        subj_var = tk.StringVar(value="Your order is ready!")
        body_var = tk.StringVar(
            value="Hi — your bakery order is ready for pickup.")
        ord_var = tk.StringVar()
        tk.Label(d, text="Channel:").grid(row=0, column=0, padx=8, pady=4, sticky="e")
        ttk.Combobox(d, textvariable=ch_var, values=["sms", "email"],
                     state="readonly", width=10).grid(row=0, column=1, padx=8, pady=4, sticky="w")
        tk.Label(d, text="Recipient:").grid(row=1, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=rcp_var, width=30).grid(row=1, column=1, padx=8, pady=4)
        tk.Label(d, text="Subject:").grid(row=2, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=subj_var, width=30).grid(row=2, column=1, padx=8, pady=4)
        tk.Label(d, text="Body:").grid(row=3, column=0, padx=8, pady=4, sticky="ne")
        tk.Entry(d, textvariable=body_var, width=30).grid(row=3, column=1, padx=8, pady=4)
        tk.Label(d, text="Order ID:").grid(row=4, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=ord_var, width=22).grid(row=4, column=1, padx=8, pady=4, sticky="w")
        def save():
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_notifications "
                    "(channel, recipient, subject, body, related_order, "
                    "status, queued_at) VALUES (?,?,?,?,?,?, ?)",
                    (ch_var.get(), rcp_var.get(), subj_var.get(),
                     body_var.get(), ord_var.get(), "queued", now))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._notif_refresh()
        tk.Button(d, text="Queue", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).grid(row=5, column=0, columnspan=2, pady=10)

    def _notif_set(self, status):
        sel = self._notif_tree.focus()
        if not sel:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            if status == "sent":
                conn.execute(
                    "UPDATE bakery_notifications SET status=?, sent_at=? "
                    "WHERE id=?", (status, now, int(sel)))
            else:
                conn.execute(
                    "UPDATE bakery_notifications SET status=? WHERE id=?",
                    (status, int(sel)))
            conn.commit()
        finally:
            conn.close()
        self._notif_refresh()

    def _build_quote_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="+ New quote", command=self._quote_new,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="💷 Mark deposit paid",
                  command=self._quote_deposit_paid,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="Set status…", command=self._quote_set_status,
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._quote_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        cols = ("id", "customer", "type", "event_date", "servings",
                "quoted", "deposit", "paid", "status")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=16)
        for c, h, w in [("id", "ID", 60), ("customer", "Customer", 140),
                        ("type", "Type", 110), ("event_date", "Event", 110),
                        ("servings", "Serves", 80),
                        ("quoted", "Quoted £", 100),
                        ("deposit", "Deposit £", 100),
                        ("paid", "Deposit", 100),
                        ("status", "Status", 100)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._quote_tree = tv
        self._quote_refresh()

    def _quote_refresh(self):
        tv = self._quote_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, customer, event_type, event_date, servings, "
                "quoted_price, deposit_amount, deposit_paid, status "
                "FROM bakery_event_quotes ORDER BY id DESC LIMIT 200"
            ).fetchall()
        finally:
            conn.close()
        for rid, cust, et, ed, sv, qp, da, dp, st in rows:
            tv.insert("", "end", iid=str(rid),
                      values=(rid, cust, et or "", ed,
                              sv or "", f"£{(qp or 0):.2f}",
                              f"£{(da or 0):.2f}",
                              "PAID" if dp else "unpaid", st))

    def _quote_new(self):
        d = tk.Toplevel(self.root); d.title("Event quote")
        d.transient(self.root); d.grab_set()
        fields = [("Customer name", ""),
                  ("Contact (email/phone)", ""),
                  ("Event type", "wedding"),
                  ("Event date (YYYY-MM-DD)",
                   (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")),
                  ("Servings", "80"),
                  ("Details", ""),
                  ("Quoted price £", "350.00"),
                  ("Deposit £", "100.00")]
        vars_ = []
        for i, (lbl, val) in enumerate(fields):
            tk.Label(d, text=lbl + ":").grid(row=i, column=0,
                                              padx=8, pady=4, sticky="e")
            v = tk.StringVar(value=val); vars_.append(v)
            w = tk.Entry(d, textvariable=v, width=30)
            w.grid(row=i, column=1, padx=8, pady=4, sticky="w")
        def save():
            try:
                servings = int(vars_[4].get())
                qp = float(vars_[6].get()); dp = float(vars_[7].get())
            except ValueError:
                messagebox.showerror("Quote", "Numeric fields invalid.",
                                     parent=d); return
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_event_quotes "
                    "(customer, contact, event_type, event_date, details, "
                    "servings, quoted_price, deposit_amount, deposit_paid, "
                    "status, created_at, updated_at, created_by) "
                    "VALUES (?,?,?,?,?,?,?,?,0,'draft',?,?,?)",
                    (vars_[0].get(), vars_[1].get(), vars_[2].get(),
                     vars_[3].get(), vars_[5].get(), servings,
                     qp, dp, now, now, self.current_user or "system"))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._quote_refresh()
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).grid(row=len(fields), column=0, columnspan=2, pady=10)

    def _quote_deposit_paid(self):
        sel = self._quote_tree.focus()
        if not sel:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE bakery_event_quotes SET deposit_paid=1, "
                "deposit_paid_at=?, status=CASE WHEN status='draft' "
                "THEN 'accepted' ELSE status END, updated_at=? WHERE id=?",
                (now, now, int(sel)))
            conn.commit()
        finally:
            conn.close()
        self._quote_refresh()

    def _quote_set_status(self):
        sel = self._quote_tree.focus()
        if not sel:
            return
        d = tk.Toplevel(self.root); d.title("Set status")
        d.transient(self.root); d.grab_set()
        v = tk.StringVar(value="sent")
        ttk.Combobox(d, textvariable=v,
                     values=["draft", "sent", "accepted",
                             "declined", "completed"],
                     state="readonly", width=14).pack(padx=12, pady=8)
        def save():
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                conn.execute(
                    "UPDATE bakery_event_quotes SET status=?, updated_at=? "
                    "WHERE id=?", (v.get(), now, int(sel)))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._quote_refresh()
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).pack(pady=8)

    def _build_subs_panel(self, parent):
        bg = self.colors["background"]
        info = tk.Label(parent,
            text="Subscription boxes — e.g. weekly bread share. "
                 "Each subscription auto-schedules deliveries.",
            bg=bg, font=("Arial", 11, "italic"), justify="left")
        info.pack(anchor="w", padx=14, pady=6)
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=4)
        tk.Button(top, text="+ New subscription", command=self._subs_new,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="🚚 Mark next delivery done",
                  command=self._subs_deliver,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="⏸ Pause / resume",
                  command=self._subs_toggle,
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="✖ Cancel", command=self._subs_cancel,
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._subs_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        cols = ("id", "user", "plan", "items", "freq", "next", "price", "active")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=10)
        for c, h, w in [("id", "ID", 50), ("user", "User", 120),
                        ("plan", "Plan", 140), ("items", "Items", 240),
                        ("freq", "Frequency", 90),
                        ("next", "Next delivery", 110),
                        ("price", "Per delivery", 110),
                        ("active", "Active", 70)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="x", padx=10, pady=6)
        self._subs_tree = tv

        tk.Label(parent, text="Recent deliveries",
                 bg=bg, font=("Arial", 11, "bold")).pack(anchor="w",
                                                          padx=12, pady=(8, 0))
        cols2 = ("id", "sub", "scheduled", "delivered", "order", "status")
        tv2 = ttk.Treeview(parent, columns=cols2, show="headings", height=10)
        for c, h, w in [("id", "ID", 50), ("sub", "Sub", 50),
                        ("scheduled", "Scheduled", 120),
                        ("delivered", "Delivered", 120),
                        ("order", "Order", 130), ("status", "Status", 100)]:
            tv2.heading(c, text=h); tv2.column(c, width=w, anchor="w")
        tv2.pack(fill="both", expand=True, padx=10, pady=6)
        self._subs_deliv_tree = tv2
        self._subs_refresh()

    def _subs_refresh(self):
        conn = self._connect()
        try:
            subs = conn.execute(
                "SELECT id, user, plan_name, items_json, frequency, "
                "next_delivery, price_per_delivery, active "
                "FROM bakery_subscriptions ORDER BY id DESC").fetchall()
            deliv = conn.execute(
                "SELECT id, subscription_id, scheduled_for, delivered_at, "
                "order_id, status FROM bakery_subscription_deliveries "
                "ORDER BY id DESC LIMIT 200").fetchall()
        finally:
            conn.close()
        tv = self._subs_tree; tv.delete(*tv.get_children())
        for rid, u, pl, items, fq, nx, pp, active in subs:
            try:
                d = json.loads(items)
                desc = ", ".join(f"{k}×{v}" for k, v in d.items())
            except Exception:
                desc = items or ""
            tv.insert("", "end", iid=str(rid),
                      values=(rid, u, pl, desc, fq, nx or "",
                              f"£{(pp or 0):.2f}",
                              "yes" if active else "no"))
        tv2 = self._subs_deliv_tree; tv2.delete(*tv2.get_children())
        for did, sid, sched, deli, oid, st in deliv:
            tv2.insert("", "end", values=(did, sid, sched, deli or "",
                                          oid or "", st))

    def _subs_new(self):
        names = self._all_product_names()
        d = tk.Toplevel(self.root); d.title("New subscription")
        d.transient(self.root); d.grab_set(); d.geometry("520x520")
        bg = self.colors["background"]; d.configure(bg=bg)
        u_var = tk.StringVar(value=self.current_user or "")
        plan_var = tk.StringVar(value="Weekly Bread Share")
        freq_var = tk.StringVar(value="weekly")
        price_var = tk.StringVar(value="12.00")
        tk.Label(d, text="User:", bg=bg).grid(row=0, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=u_var, width=22).grid(row=0, column=1, padx=8, pady=4, sticky="w")
        tk.Label(d, text="Plan name:", bg=bg).grid(row=1, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=plan_var, width=28).grid(row=1, column=1, padx=8, pady=4, sticky="w")
        tk.Label(d, text="Frequency:", bg=bg).grid(row=2, column=0, padx=8, pady=4, sticky="e")
        ttk.Combobox(d, textvariable=freq_var,
                     values=["weekly", "biweekly", "monthly"],
                     state="readonly", width=14).grid(row=2, column=1,
                                                       padx=8, pady=4, sticky="w")
        tk.Label(d, text="Price / delivery £:", bg=bg).grid(row=3, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=price_var, width=10).grid(row=3, column=1,
                                                            padx=8, pady=4, sticky="w")
        tk.Label(d, text="Items:", bg=bg).grid(row=4, column=0, padx=8, pady=4, sticky="ne")
        f = tk.Frame(d, bg=bg); f.grid(row=4, column=1, padx=8, pady=4, sticky="w")
        rows_v = []
        def add_row():
            r = len(rows_v)
            iv = tk.StringVar(value=names[0] if names else "")
            qv = tk.StringVar(value="1")
            ttk.Combobox(f, textvariable=iv, values=names, state="readonly",
                         width=22).grid(row=r, column=0, padx=2)
            tk.Entry(f, textvariable=qv, width=4).grid(row=r, column=1, padx=2)
            rows_v.append((iv, qv))
        for _ in range(3):
            add_row()
        tk.Button(d, text="+ row", command=add_row,
                  relief="flat").grid(row=5, column=1, sticky="w", padx=8)
        def save():
            try:
                price = float(price_var.get())
            except ValueError:
                messagebox.showerror("Sub", "Bad price.", parent=d); return
            items = {}
            for iv, qv in rows_v:
                try:
                    q = int(qv.get())
                except ValueError:
                    continue
                if q > 0:
                    items[iv.get()] = items.get(iv.get(), 0) + q
            if not items:
                messagebox.showerror("Sub", "Add items.", parent=d); return
            now = datetime.now()
            now_s = now.strftime("%Y-%m-%d %H:%M:%S")
            days = self.FREQ_DAYS.get(freq_var.get(), 7)
            next_d = (now + timedelta(days=days)).strftime("%Y-%m-%d")
            conn = self._connect()
            try:
                cur = conn.execute(
                    "INSERT INTO bakery_subscriptions "
                    "(user, plan_name, items_json, frequency, "
                    "price_per_delivery, next_delivery, active, created_at) "
                    "VALUES (?,?,?,?,?,?,1,?)",
                    (u_var.get(), plan_var.get(), json.dumps(items),
                     freq_var.get(), price, next_d, now_s))
                sid = cur.lastrowid
                conn.execute(
                    "INSERT INTO bakery_subscription_deliveries "
                    "(subscription_id, scheduled_for, status) "
                    "VALUES (?, ?, 'scheduled')", (sid, next_d))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._subs_refresh()
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).grid(row=6, column=0, columnspan=2, pady=12)

    def _subs_deliver(self):
        sel = self._subs_tree.focus()
        if not sel:
            return
        sid = int(sel)
        now = datetime.now()
        now_s = now.strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            r = conn.execute(
                "SELECT frequency, next_delivery FROM bakery_subscriptions "
                "WHERE id=?", (sid,)).fetchone()
            if not r:
                return
            fq, nd = r
            # Mark current delivery delivered
            conn.execute(
                "UPDATE bakery_subscription_deliveries "
                "SET delivered_at=?, status='delivered' "
                "WHERE subscription_id=? AND status='scheduled' "
                "AND scheduled_for=?", (now_s, sid, nd))
            # Schedule next
            days = self.FREQ_DAYS.get(fq, 7)
            next_d = (now + timedelta(days=days)).strftime("%Y-%m-%d")
            conn.execute(
                "UPDATE bakery_subscriptions SET next_delivery=? "
                "WHERE id=?", (next_d, sid))
            conn.execute(
                "INSERT INTO bakery_subscription_deliveries "
                "(subscription_id, scheduled_for, status) "
                "VALUES (?, ?, 'scheduled')", (sid, next_d))
            conn.commit()
        finally:
            conn.close()
        self._subs_refresh()

    def _subs_toggle(self):
        sel = self._subs_tree.focus()
        if not sel:
            return
        conn = self._connect()
        try:
            r = conn.execute(
                "SELECT active FROM bakery_subscriptions WHERE id=?",
                (int(sel),)).fetchone()
            if not r:
                return
            new = 0 if r[0] else 1
            conn.execute(
                "UPDATE bakery_subscriptions SET active=? WHERE id=?",
                (new, int(sel)))
            conn.commit()
        finally:
            conn.close()
        self._subs_refresh()

    def _subs_cancel(self):
        sel = self._subs_tree.focus()
        if not sel:
            return
        if not messagebox.askyesno("Cancel",
                                   "Cancel this subscription?",
                                   parent=self.root):
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE bakery_subscriptions SET active=0, cancelled_at=? "
                "WHERE id=?", (now, int(sel)))
            conn.commit()
        finally:
            conn.close()
        self._subs_refresh()

