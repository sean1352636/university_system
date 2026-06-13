"""RewardsTabMixin — auto-split from bakery_shop.py."""
from education_system.university_system.modules.domain.commerce.bakery_shop._common import *  # noqa: F401,F403


class RewardsTabMixin:
    def build_rewards_tab(self):
        self.rewards_content = tk.Frame(self.rewards_tab, bg=self.colors["background"])
        self.rewards_content.pack(fill="both", expand=True)
        self.refresh_loyalty()

    def refresh_loyalty(self):
        """Render the rewards tab. Customers see their points and punch
        cards. Admins additionally see promo / happy-hour / combo
        management buttons."""
        if not getattr(self, "rewards_tab", None) or not getattr(self.rewards_tab, "_lazy_built", False):
            return
        if not hasattr(self, "rewards_content"):
            return
        for w in self.rewards_content.winfo_children():
            w.destroy()

        tk.Label(self.rewards_content, text="⭐ Rewards & Promotions",
                 font=("Georgia", 18, "bold"),
                 bg=self.colors["background"], fg=self.colors["text"]
                 ).pack(pady=15)

        # ---- Customer-facing: loyalty + punch + referral ----
        if self.current_user:
            balance, lifetime = self.get_loyalty_points(self.current_user)

            card = tk.Frame(self.rewards_content, bg=self.colors["card"],
                            relief="ridge", bd=2)
            card.pack(fill="x", padx=30, pady=8)
            tk.Label(card, text=f"⭐ Loyalty: {balance} pts available "
                                f"  •  Lifetime: {lifetime} pts",
                     bg=self.colors["card"], fg=self.colors["primary"],
                     font=("Arial", 13, "bold")).pack(anchor="w", padx=12, pady=8)
            tk.Label(card, text=f"Earn 1 pt per £1 spent. "
                                f"Redeem 100 pts for £1 off at checkout.",
                     bg=self.colors["card"], fg=self.colors["text"],
                     font=("Arial", 10, "italic")).pack(anchor="w", padx=12, pady=(0, 6))

            # Punch cards
            for cat, threshold in PUNCH_CARD_CATEGORIES.items():
                count = self.get_punch_count(self.current_user, cat)
                pf = tk.Frame(self.rewards_content, bg=self.colors["card"],
                              relief="ridge", bd=2)
                pf.pack(fill="x", padx=30, pady=4)
                tk.Label(pf, text=f"🥤 {cat} punch card: "
                                  f"{min(count, threshold)}/{threshold} stamps",
                         bg=self.colors["card"], fg=self.colors["text"],
                         font=("Arial", 11, "bold")
                         ).pack(anchor="w", padx=12, pady=4)
                stamps = "".join("●" if i < count else "○" for i in range(threshold))
                tk.Label(pf, text=stamps, bg=self.colors["card"],
                         fg=self.colors["secondary"],
                         font=("Courier", 14)
                         ).pack(anchor="w", padx=12, pady=(0, 6))

            # Active promotions visible to all
            self._render_active_promos(self.rewards_content)

            # Refer-a-friend section
            ref_frame = tk.LabelFrame(self.rewards_content,
                                      text="🤝 Refer a Friend",
                                      bg=self.colors["background"],
                                      fg=self.colors["text"],
                                      font=("Arial", 11, "bold"))
            ref_frame.pack(fill="x", padx=30, pady=10)
            tk.Label(ref_frame,
                     text=f"Earn {REFERRAL_BONUS_GBP:.0f} GBP × {LOYALTY_POINTS_PER_GBP_REDEEM} pts "
                          "when a friend joins and shops.",
                     bg=self.colors["background"], fg=self.colors["text"]
                     ).pack(anchor="w", padx=10, pady=4)
            tk.Button(ref_frame, text="Generate Referral",
                      bg=self.colors["secondary"], fg="white", relief="flat",
                      command=self._referral_dialog
                      ).pack(anchor="w", padx=10, pady=6)
        else:
            tk.Label(self.rewards_content,
                     text="Log in to earn loyalty points and claim rewards.",
                     bg=self.colors["background"], fg=self.colors["text"],
                     font=("Arial", 11, "italic")).pack(pady=10)

        # ---- Admin management ----
        if self.user_type == "Admin":
            adm = tk.LabelFrame(self.rewards_content,
                                text="🛠 Admin — Promotion Management",
                                bg=self.colors["background"],
                                fg=self.colors["text"],
                                font=("Arial", 11, "bold"))
            adm.pack(fill="x", padx=30, pady=15)
            row = tk.Frame(adm, bg=self.colors["background"])
            row.pack(padx=8, pady=8)
            for label, cmd, color in (
                ("🎟 Promo Codes", self._open_promo_admin,    self.colors["primary"]),
                ("⏰ Happy Hours", self._open_happy_admin,    self.colors["secondary"]),
                ("🍱 Combo Deals", self._open_combo_admin,    self.colors["success"]),
                ("🤝 Referrals",   self._open_referral_admin, self.colors["accent"]),
            ):
                tk.Button(row, text=label, font=("Arial", 10, "bold"),
                          bg=color,
                          fg="white" if color != self.colors["accent"] else self.colors["text"],
                          relief="flat", padx=14, pady=8,
                          command=cmd).pack(side="left", padx=6)

    def _render_active_promos(self, parent):
        """Show currently-active happy hours and combos to the customer."""
        promos_frame = tk.LabelFrame(parent, text="🔥 Active Right Now",
                                     bg=self.colors["background"],
                                     fg=self.colors["text"],
                                     font=("Arial", 11, "bold"))
        promos_frame.pack(fill="x", padx=30, pady=10)
        any_shown = False
        for hh in self._active_happy_hours():
            tk.Label(promos_frame,
                     text=f"⏰ {hh['name']}: {hh['pct']:.0f}% off "
                          f"{hh['category']} until {hh['end']}",
                     bg=self.colors["background"], fg=self.colors["text"]
                     ).pack(anchor="w", padx=10, pady=2)
            any_shown = True
        for combo in self._active_combos():
            items_desc = ", ".join(f"{n}×{q}" for n, q in combo["items"].items())
            tk.Label(promos_frame,
                     text=f"🍱 {combo['name']}: {items_desc} for £{combo['combo_price']:.2f}",
                     bg=self.colors["background"], fg=self.colors["text"]
                     ).pack(anchor="w", padx=10, pady=2)
            any_shown = True
        if not any_shown:
            tk.Label(promos_frame, text="No active promotions right now.",
                     bg=self.colors["background"],
                     fg=self.colors["text"],
                     font=("Arial", 10, "italic")).pack(anchor="w", padx=10, pady=4)

    def _referral_dialog(self):
        if not self.current_user:
            return
        referee = simpledialog.askstring(
            "Refer a Friend",
            "Enter the username or student ID of your friend:",
            parent=self.root)
        if not referee:
            return
        referee = referee.strip()
        if referee == self.current_user:
            messagebox.showerror("Invalid", "You can't refer yourself.")
            return
        try:
            self._exec("""
                INSERT INTO bakery_referrals
                    (referrer, referee, status, bonus_referrer, bonus_referee, created_at)
                VALUES (?, ?, 'pending', ?, ?, ?)
            """, (self.current_user, referee,
                  REFERRAL_BONUS_GBP, REFERRAL_BONUS_GBP,
                  datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            messagebox.showinfo(
                "Referral Created",
                f"Tell {referee} that £{REFERRAL_BONUS_GBP:.0f} off will be "
                "automatically applied to their first bakery order."
            )
            logger.info("Referral created %s -> %s", self.current_user, referee)
        except Exception:
            logger.exception("Failed to create referral")
            messagebox.showerror("Error",
                                 "Could not create referral (already exists?).")

    def _open_promo_admin(self):
        self._open_simple_crud_dialog(
            title="🎟 Promo Codes",
            columns=("code", "description", "type", "value", "min",
                     "expiry", "uses", "max", "active"),
            select_sql="""SELECT code, description, discount_type,
                                 discount_value, min_subtotal, expiry_date,
                                 current_uses, max_uses, active
                          FROM bakery_promo_codes ORDER BY code""",
            add_fn=self._add_promo_dialog,
            delete_sql="DELETE FROM bakery_promo_codes WHERE code = ?",
            id_col_index=0,
            toggle_sql="UPDATE bakery_promo_codes SET active = 1 - active WHERE code = ?",
        )

    def _add_promo_dialog(self, refresh_cb):
        d = tk.Toplevel(self.root)
        d.title("New Promo Code")
        d.geometry("400x420")
        d.transient(self.root)
        d.grab_set()
        fields = {}
        for label, default in (
            ("Code",          ""),
            ("Description",   ""),
            ("Type (percent/fixed)", "percent"),
            ("Discount value", "10"),
            ("Min subtotal", "0"),
            ("Expiry (YYYY-MM-DD)", ""),
            ("Max uses",      ""),
        ):
            tk.Label(d, text=label).pack(anchor="w", padx=12, pady=(8, 0))
            e = tk.Entry(d, width=40)
            e.insert(0, default)
            e.pack(padx=12)
            fields[label] = e

        def save():
            try:
                code = fields["Code"].get().strip().upper()
                if not code:
                    messagebox.showerror("Error", "Code required", parent=d); return
                ptype = fields["Type (percent/fixed)"].get().strip().lower()
                if ptype not in ("percent", "fixed"):
                    messagebox.showerror("Error", "Type must be percent or fixed",
                                         parent=d); return
                value = float(fields["Discount value"].get() or 0)
                min_sub = float(fields["Min subtotal"].get() or 0)
                expiry = fields["Expiry (YYYY-MM-DD)"].get().strip() or None
                max_uses = fields["Max uses"].get().strip()
                max_uses = int(max_uses) if max_uses else None
                self._exec("""INSERT OR REPLACE INTO bakery_promo_codes
                              (code, description, discount_type, discount_value,
                               min_subtotal, expiry_date, max_uses, current_uses,
                               active, created_at)
                              VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1, ?)""",
                           (code, fields["Description"].get(), ptype, value,
                            min_sub, expiry, max_uses,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                logger.info("Promo created code=%s type=%s value=%s",
                            code, ptype, value)
                d.destroy()
                refresh_cb()
            except Exception as e:
                logger.exception("Failed to add promo")
                messagebox.showerror("Error", str(e), parent=d)

        tk.Button(d, text="Save", bg=self.colors["success"], fg="white",
                  relief="flat", padx=20, pady=6, command=save
                  ).pack(side="right", padx=12, pady=12)
        tk.Button(d, text="Cancel", bg=self.colors["secondary"], fg="white",
                  relief="flat", padx=20, pady=6, command=d.destroy
                  ).pack(side="right", pady=12)

    def _open_happy_admin(self):
        self._open_simple_crud_dialog(
            title="⏰ Happy Hours",
            columns=("id", "name", "start", "end", "days", "category", "%", "active"),
            select_sql="""SELECT id, name, start_time, end_time, days_of_week,
                                 category, discount_pct, active
                          FROM bakery_happy_hours ORDER BY start_time""",
            add_fn=self._add_happy_dialog,
            delete_sql="DELETE FROM bakery_happy_hours WHERE id = ?",
            id_col_index=0,
            toggle_sql="UPDATE bakery_happy_hours SET active = 1 - active WHERE id = ?",
        )

    def _add_happy_dialog(self, refresh_cb):
        d = tk.Toplevel(self.root)
        d.title("New Happy Hour")
        d.geometry("400x380")
        d.transient(self.root); d.grab_set()
        fields = {}
        cats = ["all"] + list(self.products.keys())
        for label, default in (
            ("Name", "Afternoon Treat"),
            ("Start (HH:MM)", "15:00"),
            ("End (HH:MM)", "17:00"),
            ("Days (csv Mon..Sun or 'all')", "all"),
            ("Discount %", "20"),
        ):
            tk.Label(d, text=label).pack(anchor="w", padx=12, pady=(8, 0))
            e = tk.Entry(d, width=40)
            e.insert(0, default)
            e.pack(padx=12)
            fields[label] = e
        tk.Label(d, text="Category").pack(anchor="w", padx=12, pady=(8, 0))
        cat_var = tk.StringVar(value="all")
        ttk.Combobox(d, textvariable=cat_var, values=cats,
                     state="readonly", width=37).pack(padx=12)

        def save():
            try:
                self._exec("""INSERT INTO bakery_happy_hours
                              (name, start_time, end_time, days_of_week,
                               category, discount_pct, active, created_at)
                              VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
                           (fields["Name"].get(), fields["Start (HH:MM)"].get(),
                            fields["End (HH:MM)"].get(),
                            fields["Days (csv Mon..Sun or 'all')"].get(),
                            cat_var.get(), float(fields["Discount %"].get() or 0),
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                logger.info("Happy hour created %s", fields["Name"].get())
                d.destroy()
                refresh_cb()
            except Exception as e:
                logger.exception("Failed to add happy hour")
                messagebox.showerror("Error", str(e), parent=d)

        tk.Button(d, text="Save", bg=self.colors["success"], fg="white",
                  relief="flat", padx=20, pady=6, command=save
                  ).pack(side="right", padx=12, pady=12)
        tk.Button(d, text="Cancel", bg=self.colors["secondary"], fg="white",
                  relief="flat", padx=20, pady=6, command=d.destroy
                  ).pack(side="right", pady=12)

    def _open_combo_admin(self):
        self._open_simple_crud_dialog(
            title="🍱 Combo Deals",
            columns=("id", "name", "items", "combo £", "active"),
            select_sql="""SELECT id, name, items_json, combo_price, active
                          FROM bakery_combos ORDER BY name""",
            add_fn=self._add_combo_dialog,
            delete_sql="DELETE FROM bakery_combos WHERE id = ?",
            id_col_index=0,
            toggle_sql="UPDATE bakery_combos SET active = 1 - active WHERE id = ?",
        )

    def _add_combo_dialog(self, refresh_cb):
        d = tk.Toplevel(self.root)
        d.title("New Combo")
        d.geometry("440x380")
        d.transient(self.root); d.grab_set()
        tk.Label(d, text="Name").pack(anchor="w", padx=12, pady=(8, 0))
        name_e = tk.Entry(d, width=44); name_e.pack(padx=12)
        tk.Label(d, text="Items (one per line: 'Item Name x Qty')"
                 ).pack(anchor="w", padx=12, pady=(8, 0))
        items_t = tk.Text(d, width=44, height=8)
        items_t.pack(padx=12)
        items_t.insert("1.0", "Coffee x 1\nCroissant x 1")
        tk.Label(d, text="Combo price (£)").pack(anchor="w", padx=12, pady=(8, 0))
        price_e = tk.Entry(d, width=20); price_e.insert(0, "4.50"); price_e.pack(padx=12)

        def save():
            try:
                lines = [ln.strip() for ln in items_t.get("1.0", "end").splitlines()
                         if ln.strip()]
                items = {}
                for ln in lines:
                    if " x " not in ln.lower():
                        raise ValueError(f"Bad line: {ln!r} (use 'Name x Qty')")
                    name, qty = ln.rsplit("x", 1) if "x" in ln else (ln, "1")
                    name = name.strip()
                    qty = int(qty.strip())
                    if not self._product_info(name):
                        raise ValueError(f"Unknown product: {name}")
                    items[name] = qty
                self._exec("""INSERT INTO bakery_combos
                              (name, items_json, combo_price, active, created_at)
                              VALUES (?, ?, ?, 1, ?)""",
                           (name_e.get(), json.dumps(items),
                            float(price_e.get() or 0),
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                logger.info("Combo created %s items=%s", name_e.get(), items)
                d.destroy()
                refresh_cb()
            except Exception as e:
                logger.exception("Failed to add combo")
                messagebox.showerror("Error", str(e), parent=d)

        tk.Button(d, text="Save", bg=self.colors["success"], fg="white",
                  relief="flat", padx=20, pady=6, command=save
                  ).pack(side="right", padx=12, pady=12)
        tk.Button(d, text="Cancel", bg=self.colors["secondary"], fg="white",
                  relief="flat", padx=20, pady=6, command=d.destroy
                  ).pack(side="right", pady=12)

    def _open_referral_admin(self):
        self._open_simple_crud_dialog(
            title="🤝 Referrals",
            columns=("id", "referrer", "referee", "status", "created", "redeemed"),
            select_sql="""SELECT id, referrer, referee, status,
                                 created_at, redeemed_at
                          FROM bakery_referrals ORDER BY id DESC""",
            add_fn=None,
            delete_sql="DELETE FROM bakery_referrals WHERE id = ?",
            id_col_index=0,
        )

    def _open_simple_crud_dialog(self, *, title, columns, select_sql,
                                 add_fn, delete_sql, id_col_index,
                                 toggle_sql=None):
        d = tk.Toplevel(self.root)
        d.title(title)
        d.geometry("780x460")
        d.transient(self.root); d.grab_set()

        tree = ttk.Treeview(d, columns=columns, show="headings", height=14)
        for c in columns:
            tree.heading(c, text=c)
            tree.column(c, width=110, anchor="w")
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        def refresh():
            for it in tree.get_children():
                tree.delete(it)
            for row in self._query(select_sql):
                tree.insert("", "end", values=row)

        def do_delete():
            sel = tree.selection()
            if not sel:
                return
            rid = tree.item(sel[0])["values"][id_col_index]
            if not messagebox.askyesno("Confirm",
                                       f"Delete row {rid}?", parent=d):
                return
            self._exec(delete_sql, (rid,))
            logger.info("CRUD delete from %s id=%s", title, rid)
            refresh()

        def do_toggle():
            sel = tree.selection()
            if not sel or not toggle_sql:
                return
            rid = tree.item(sel[0])["values"][id_col_index]
            self._exec(toggle_sql, (rid,))
            logger.info("CRUD toggle in %s id=%s", title, rid)
            refresh()

        btns = tk.Frame(d)
        btns.pack(fill="x", padx=10, pady=6)
        if add_fn:
            tk.Button(btns, text="➕ Add",
                      bg=self.colors["success"], fg="white", relief="flat",
                      command=lambda: add_fn(refresh)
                      ).pack(side="left", padx=4)
        if toggle_sql:
            tk.Button(btns, text="🔁 Toggle Active",
                      bg=self.colors["accent"], fg=self.colors["text"],
                      relief="flat", command=do_toggle
                      ).pack(side="left", padx=4)
        tk.Button(btns, text="🗑 Delete",
                  bg=self.colors["danger"], fg="white", relief="flat",
                  command=do_delete).pack(side="left", padx=4)
        tk.Button(btns, text="Close",
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  command=d.destroy).pack(side="right", padx=4)

        refresh()

