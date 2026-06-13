"""AdminTabMixin — auto-split from bakery_shop.py."""
from education_system.university_system.modules.domain.commerce.bakery_shop._common import *  # noqa: F401,F403


class AdminTabMixin:
    def build_admin_tab(self):
        """Build the admin dashboard."""
        header = tk.Label(
            self.admin_tab,
            text="⚙️ Admin Dashboard",
            font=("Georgia", 18, "bold"),
            bg=self.colors["background"],
            fg=self.colors["text"],
        )
        header.pack(pady=15)

        self.admin_content = tk.Frame(self.admin_tab, bg=self.colors["background"])
        self.admin_content.pack(fill="both", expand=True, padx=20, pady=10)

        self.refresh_admin()

    def refresh_admin(self):
        """Render the admin dashboard contents."""
        if not getattr(self, "admin_tab", None) or not getattr(self.admin_tab, "_lazy_built", False):
            return
        for widget in self.admin_content.winfo_children():
            widget.destroy()

        if self.user_type != "Admin":
            tk.Label(
                self.admin_content,
                text="🔒 Admin access required\n\nLogin as 'admin' (password: admin123) to access this section.",
                font=("Arial", 14),
                bg=self.colors["background"],
                fg=self.colors["text"],
                justify="center",
            ).pack(expand=True, pady=50)
            return

        # Statistics row
        stats_frame = tk.Frame(self.admin_content, bg=self.colors["background"])
        stats_frame.pack(fill="x", pady=10)

        total_revenue = sum(o["total"] for o in self.orders)
        total_orders = len(self.orders)
        total_items = sum(sum(o["items"].values()) for o in self.orders)

        stats = [
            ("Total Orders", str(total_orders), self.colors["primary"]),
            ("Total Revenue", f"£{total_revenue:.2f}", self.colors["success"]),
            ("Items Sold", str(total_items), self.colors["secondary"]),
        ]

        for label, value, color in stats:
            card = tk.Frame(stats_frame, bg=color, width=250, height=100)
            card.pack(side="left", padx=10, pady=5, fill="x", expand=True)
            card.pack_propagate(False)

            tk.Label(card, text=label, font=("Arial", 11), bg=color, fg="white").pack(pady=(15, 5))
            tk.Label(card, text=value, font=("Georgia", 20, "bold"), bg=color, fg="white").pack()

        # Inventory management
        inv_label = tk.Label(
            self.admin_content,
            text="📦 Inventory Management",
            font=("Georgia", 14, "bold"),
            bg=self.colors["background"],
            fg=self.colors["text"],
        )
        inv_label.pack(pady=(20, 10), anchor="w")

        # Inventory table
        inv_frame = tk.Frame(self.admin_content, bg=self.colors["background"])
        inv_frame.pack(fill="both", expand=True)

        columns = ("Category", "Product", "Price", "Stock", "Status")
        inv_tree = ttk.Treeview(inv_frame, columns=columns, show="headings", height=12)

        for col in columns:
            inv_tree.heading(col, text=col)
            inv_tree.column(col, width=150, anchor="w")

        for category, items in self.products.items():
            for name, info in items.items():
                status = "✅ Good" if info["stock"] > 10 else "⚠️ Low" if info["stock"] > 0 else "❌ Out"
                inv_tree.insert(
                    "",
                    "end",
                    values=(category, name, f"£{info['price']:.2f}", info["stock"], status),
                )

        scroll = ttk.Scrollbar(inv_frame, orient="vertical", command=inv_tree.yview)
        inv_tree.configure(yscrollcommand=scroll.set)
        inv_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # Restock button
        btn_frame = tk.Frame(self.admin_content, bg=self.colors["background"])
        btn_frame.pack(fill="x", pady=10)

        tk.Button(
            btn_frame,
            text="🔄 Restock All (+50 each)",
            font=("Arial", 11, "bold"),
            bg=self.colors["success"],
            fg="white",
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self.restock_all,
        ).pack(side="left", padx=5)

        tk.Button(
            btn_frame,
            text="📊 Export Sales Report",
            font=("Arial", 11, "bold"),
            bg=self.colors["primary"],
            fg="white",
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self.export_report,
        ).pack(side="left", padx=5)

        tk.Button(
            btn_frame,
            text="💰 Finance (gift cards / drawer / billing / tips)",
            font=("Arial", 11, "bold"),
            bg=self.colors["secondary"],
            fg="white",
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._open_finance_admin,
        ).pack(side="left", padx=5)

    def _open_finance_admin(self):
        """Single dialog with sub-tabs for gift cards, billing codes,
        cash drawer, and the tips ledger."""
        d = tk.Toplevel(self.root); d.title("💰 Finance Admin")
        d.geometry("900x540"); d.transient(self.root); d.grab_set()

        nb = ttk.Notebook(d); nb.pack(fill="both", expand=True, padx=8, pady=8)

        gc_tab = tk.Frame(nb); nb.add(gc_tab, text="🎁 Gift Cards")
        bc_tab = tk.Frame(nb); nb.add(bc_tab, text="🏛 Billing Codes")
        cd_tab = tk.Frame(nb); nb.add(cd_tab, text="💵 Cash Drawer")
        tp_tab = tk.Frame(nb); nb.add(tp_tab, text="💝 Tips Ledger")

        # ---- Gift cards ----
        gc_cols = ("code", "initial", "balance", "issued_to",
                   "expiry", "active", "created")
        gc_tree = ttk.Treeview(gc_tab, columns=gc_cols, show="headings", height=14)
        for c, w in zip(gc_cols, (110, 80, 80, 140, 100, 60, 140)):
            gc_tree.heading(c, text=c.title())
            gc_tree.column(c, width=w, anchor="w")
        gc_tree.pack(fill="both", expand=True, padx=6, pady=6)

        def reload_gc():
            for it in gc_tree.get_children():
                gc_tree.delete(it)
            for r in self.list_gift_cards():
                gc_tree.insert("", "end", values=(
                    r[0], f"£{r[1]:.2f}", f"£{r[2]:.2f}",
                    r[3] or "—", r[4] or "—",
                    "✓" if r[5] else "✗", r[6],
                ))

        def issue_dialog():
            amt = simpledialog.askfloat("Issue Gift Card",
                                        "Initial balance (£):",
                                        parent=d, minvalue=0.01)
            if amt is None:
                return
            to = simpledialog.askstring("Issue Gift Card",
                                        "Issue to (name/username, optional):",
                                        parent=d) or None
            code = self.issue_gift_card(amt, issued_to=to)
            if code:
                messagebox.showinfo("Issued",
                                    f"Gift card {code} for £{amt:.2f}.",
                                    parent=d)
                reload_gc()
            else:
                messagebox.showerror("Error",
                                     "Could not issue gift card.", parent=d)

        gc_btns = tk.Frame(gc_tab); gc_btns.pack(fill="x", padx=6, pady=4)
        tk.Button(gc_btns, text="➕ Issue New",
                  bg=self.colors["success"], fg="white", relief="flat",
                  command=issue_dialog).pack(side="left", padx=4)
        tk.Button(gc_btns, text="🔄 Refresh",
                  bg=self.colors["accent"], fg=self.colors["text"],
                  relief="flat", command=reload_gc).pack(side="left", padx=4)
        reload_gc()

        # ---- Billing codes ----
        bc_cols = ("code", "department", "contact", "email", "active")
        bc_tree = ttk.Treeview(bc_tab, columns=bc_cols, show="headings", height=14)
        for c, w in zip(bc_cols, (120, 180, 140, 200, 60)):
            bc_tree.heading(c, text=c.title())
            bc_tree.column(c, width=w, anchor="w")
        bc_tree.pack(fill="both", expand=True, padx=6, pady=6)

        def reload_bc():
            for it in bc_tree.get_children():
                bc_tree.delete(it)
            for r in self.list_billing_codes(only_active=False):
                bc_tree.insert("", "end", values=(
                    r[0], r[1] or "—", r[2] or "—",
                    r[3] or "—", "✓" if r[4] else "✗",
                ))

        def add_bc():
            code = simpledialog.askstring("Billing Code", "Code:",
                                           parent=d)
            if not code:
                return
            dept = simpledialog.askstring("Billing Code", "Department:",
                                           parent=d) or ""
            email = simpledialog.askstring("Billing Code",
                                            "Contact email:",
                                            parent=d) or ""
            if self.upsert_billing_code(code, department=dept,
                                         contact_email=email):
                reload_bc()
            else:
                messagebox.showerror("Error", "Could not save code.", parent=d)

        bc_btns = tk.Frame(bc_tab); bc_btns.pack(fill="x", padx=6, pady=4)
        tk.Button(bc_btns, text="➕ Add / Update",
                  bg=self.colors["success"], fg="white", relief="flat",
                  command=add_bc).pack(side="left", padx=4)
        tk.Button(bc_btns, text="🔄 Refresh",
                  bg=self.colors["accent"], fg=self.colors["text"],
                  relief="flat", command=reload_bc).pack(side="left", padx=4)
        reload_bc()

        # ---- Cash drawer ----
        cd_summary = tk.Frame(cd_tab); cd_summary.pack(fill="x", padx=6, pady=6)
        cd_label = tk.Label(cd_summary, text="", font=("Arial", 11),
                            justify="left", anchor="w")
        cd_label.pack(anchor="w")

        cd_cols = ("id", "opened", "float", "closed", "counted",
                   "expected", "variance", "operator", "status")
        cd_tree = ttk.Treeview(cd_tab, columns=cd_cols, show="headings", height=10)
        for c, w in zip(cd_cols, (40, 140, 70, 140, 80, 80, 80, 100, 70)):
            cd_tree.heading(c, text=c.title())
            cd_tree.column(c, width=w, anchor="w")
        cd_tree.pack(fill="both", expand=True, padx=6, pady=6)

        def reload_cd():
            for it in cd_tree.get_children():
                cd_tree.delete(it)
            for r in self.list_drawer_sessions():
                cd_tree.insert("", "end", values=(
                    r[0], r[1], f"£{(r[2] or 0):.2f}",
                    r[3] or "—",
                    (f"£{r[4]:.2f}" if r[4] is not None else "—"),
                    (f"£{r[5]:.2f}" if r[5] is not None else "—"),
                    (f"£{r[6]:+.2f}" if r[6] is not None else "—"),
                    r[7] or "—", r[8],
                ))
            cur = self.current_open_drawer()
            if cur:
                cd_label.config(text=(f"Drawer OPEN id={cur['id']} "
                                       f"by {cur['operator']} since {cur['opened_at']} "
                                       f"— opening float £{cur['opening_float']:.2f}"))
            else:
                cd_label.config(text="No drawer currently open.")

        def open_drawer_dialog():
            if self.current_open_drawer():
                messagebox.showinfo("Already open",
                                    "A drawer is already open. Close it first.",
                                    parent=d)
                return
            f = simpledialog.askfloat("Open drawer",
                                      "Opening float (£):",
                                      parent=d, minvalue=0.0)
            if f is None:
                return
            did = self.open_cash_drawer(f)
            if did:
                reload_cd()
            else:
                messagebox.showerror("Error", "Could not open drawer.",
                                     parent=d)

        def close_drawer_dialog():
            cur = self.current_open_drawer()
            if not cur:
                messagebox.showinfo("No open drawer",
                                    "No drawer is currently open.",
                                    parent=d)
                return
            counted = simpledialog.askfloat("Close drawer",
                                             "Counted closing amount (£):",
                                             parent=d, minvalue=0.0)
            if counted is None:
                return
            notes = simpledialog.askstring("Close drawer",
                                            "Notes (optional):",
                                            parent=d) or ""
            result = self.close_cash_drawer(cur["id"], counted, notes=notes)
            if result:
                msg = (f"Opening float: £{result['opening_float']:.2f}\n"
                       f"Cash sales: £{result['cash_sales']:.2f}\n"
                       f"Expected: £{result['expected']:.2f}\n"
                       f"Counted: £{result['counted']:.2f}\n"
                       f"Variance: £{result['variance']:+.2f}")
                messagebox.showinfo("Drawer closed", msg, parent=d)
                reload_cd()
            else:
                messagebox.showerror("Error", "Could not close drawer.",
                                     parent=d)

        cd_btns = tk.Frame(cd_tab); cd_btns.pack(fill="x", padx=6, pady=4)
        tk.Button(cd_btns, text="🔓 Open Drawer",
                  bg=self.colors["success"], fg="white", relief="flat",
                  command=open_drawer_dialog).pack(side="left", padx=4)
        tk.Button(cd_btns, text="🔒 Close & Reconcile",
                  bg=self.colors["danger"], fg="white", relief="flat",
                  command=close_drawer_dialog).pack(side="left", padx=4)
        tk.Button(cd_btns, text="🔄 Refresh",
                  bg=self.colors["accent"], fg=self.colors["text"],
                  relief="flat", command=reload_cd).pack(side="left", padx=4)
        reload_cd()

        # ---- Tips ledger ----
        tp_cols = ("id", "order_id", "user", "amount", "when")
        tp_tree = ttk.Treeview(tp_tab, columns=tp_cols, show="headings", height=16)
        for c, w in zip(tp_cols, (50, 130, 140, 80, 160)):
            tp_tree.heading(c, text=c.title())
            tp_tree.column(c, width=w, anchor="w")
        tp_tree.pack(fill="both", expand=True, padx=6, pady=6)
        total_tip = 0.0
        for r in self.list_tips():
            tp_tree.insert("", "end", values=(r[0], r[1], r[3],
                                              f"£{r[2]:.2f}", r[4]))
            total_tip += float(r[2] or 0)
        tk.Label(tp_tab, text=f"Total tips on record: £{total_tip:.2f}",
                 font=("Arial", 11, "bold")
                 ).pack(side="bottom", padx=8, pady=8)

    def restock_all(self):
        """Add 50 units to every product."""
        for category in self.products.values():
            for info in category.values():
                info["stock"] += 50
        messagebox.showinfo("Restocked", "All items have been restocked (+50 each)!")
        self.refresh_admin()
        self.refresh_products()

    def export_report(self):
        """Save a plain-text sales report to the working directory."""
        if not self.orders:
            messagebox.showinfo("No Data", "No orders to export!")
            return

        try:
            filename = f"sales_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, "w") as f:
                f.write("=" * 60 + "\n")
                f.write("UNIVERSITY BAKERY SHOP - SALES REPORT\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 60 + "\n\n")

                total_revenue = sum(o["total"] for o in self.orders)
                f.write(f"Total Orders: {len(self.orders)}\n")
                f.write(f"Total Revenue: £{total_revenue:.2f}\n\n")
                f.write("-" * 60 + "\n")
                f.write("ORDER DETAILS\n")
                f.write("-" * 60 + "\n\n")

                for order in self.orders:
                    f.write(f"Order: {order['order_id']}\n")
                    f.write(f"Date: {order['timestamp']}\n")
                    f.write(f"Customer: {order['user']} ({order['user_type']})\n")
                    f.write("Items:\n")
                    for item, qty in order["items"].items():
                        f.write(f"  - {item} x {qty}\n")
                    f.write(f"Total: £{order['total']:.2f}\n")
                    f.write("-" * 40 + "\n")

            messagebox.showinfo("Export Complete", f"Sales report saved as:\n{filename}")
        except IOError as e:
            messagebox.showerror("Export Error", f"Could not save report: {e}")

