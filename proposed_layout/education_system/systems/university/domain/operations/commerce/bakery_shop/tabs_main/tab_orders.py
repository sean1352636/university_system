"""OrdersTabMixin — auto-split from bakery_shop.py."""
from education_system.systems.university.domain.operations.commerce.bakery_shop._common import *  # noqa: F401,F403


class OrdersTabMixin:
    def build_orders_tab(self):
        """Build the order history tab."""
        header = tk.Label(
            self.orders_tab,
            text="📋 Order History",
            font=("Georgia", 18, "bold"),
            bg=self.colors["background"],
            fg=self.colors["text"],
        )
        header.pack(pady=15)

        # Treeview of orders
        tree_frame = tk.Frame(self.orders_tab, bg=self.colors["background"])
        tree_frame.pack(fill="both", expand=True, padx=20, pady=10)

        columns = ("Order ID", "Date", "Customer", "Items", "Total")
        self.orders_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)

        widths = {"Order ID": 100, "Date": 150, "Customer": 150, "Items": 80, "Total": 100}
        for col in columns:
            self.orders_tree.heading(col, text=col)
            self.orders_tree.column(col, width=widths[col], anchor="w")

        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.orders_tree.yview)
        self.orders_tree.configure(yscrollcommand=scroll.set)
        self.orders_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.orders_tree.bind("<Double-1>", self.show_order_details)

        info_label = tk.Label(
            self.orders_tab,
            text="💡 Double-click an order to view details",
            font=("Arial", 10, "italic"),
            bg=self.colors["background"],
            fg=self.colors["text"],
        )
        info_label.pack(pady=5)

        actions = tk.Frame(self.orders_tab, bg=self.colors["background"])
        actions.pack(fill="x", padx=20, pady=4)
        tk.Button(actions, text="↩ Request Refund",
                  font=("Arial", 10, "bold"),
                  bg=self.colors["danger"], fg="white", relief="flat",
                  padx=12, pady=4,
                  command=self._open_customer_refund_request
                  ).pack(side="left", padx=4)
        tk.Button(actions, text="📜 Refund Audit (this order)",
                  font=("Arial", 10),
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  padx=12, pady=4,
                  command=self._show_refund_audit_for_selected
                  ).pack(side="left", padx=4)
        tk.Button(actions, text="🧾 Print PDF Receipt",
                  font=("Arial", 10, "bold"),
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=12, pady=4,
                  command=self._print_receipt_for_selected
                  ).pack(side="left", padx=4)

        self.refresh_orders()

    def _open_customer_refund_request(self):
        sel = self.orders_tree.selection()
        if not sel:
            messagebox.showinfo("Select an order",
                                "Select one of your orders first.")
            return
        order_id = self.orders_tree.item(sel[0])["values"][0]
        order = next((o for o in self.orders if o["order_id"] == order_id), None)
        if not order:
            return
        if order.get("user") != self.current_user and self.user_type != "Admin":
            messagebox.showerror("Not your order",
                                 "You can only request refunds on your own orders.")
            return
        if order.get("refunded"):
            messagebox.showinfo("Already refunded",
                                f"Order {order_id} has already been refunded.")
            return

        d = tk.Toplevel(self.root); d.title("Request Refund")
        d.geometry("480x520"); d.transient(self.root); d.grab_set()
        tk.Label(d, text=f"↩ Refund Request: {order_id}",
                 font=("Georgia", 14, "bold"),
                 bg=self.colors["background"]).pack(pady=10)

        tk.Label(d, text="Reason category",
                 bg=self.colors["background"]).pack(anchor="w", padx=20)
        cat_var = tk.StringVar(value=REFUND_REASON_CATEGORIES[0])
        ttk.Combobox(d, textvariable=cat_var,
                     values=REFUND_REASON_CATEGORIES,
                     state="readonly", width=44).pack(padx=20)

        tk.Label(d, text="Tell us what happened",
                 bg=self.colors["background"]).pack(anchor="w", padx=20, pady=(8, 0))
        reason_t = tk.Text(d, width=58, height=5); reason_t.pack(padx=20)

        tk.Label(d, text="Items affected (leave 0 if not relevant)",
                 bg=self.colors["background"], font=("Arial", 10, "bold")
                 ).pack(anchor="w", padx=20, pady=(8, 2))
        qty_vars = {}
        for name, qty in (order.get("items") or {}).items():
            row = tk.Frame(d, bg=self.colors["background"])
            row.pack(fill="x", padx=20)
            tk.Label(row, text=f"  {name}  (ordered: {qty})",
                     width=28, anchor="w",
                     bg=self.colors["background"]).pack(side="left")
            v = tk.IntVar(value=0)
            tk.Spinbox(row, from_=0, to=int(qty), textvariable=v,
                       width=5).pack(side="left", padx=4)
            qty_vars[name] = v

        def submit():
            items = {n: v.get() for n, v in qty_vars.items() if v.get() > 0}
            reason = reason_t.get("1.0", "end").strip()
            if not reason:
                messagebox.showerror("Reason required",
                                     "Please describe the issue.",
                                     parent=d)
                return
            rid = self.create_refund_request(
                order_id, reason=reason,
                reason_category=cat_var.get(),
                items=items or None,
            )
            if rid:
                messagebox.showinfo(
                    "Submitted",
                    f"Refund request #{rid} submitted. "
                    "An admin will review it shortly.")
                d.destroy()
                self.refresh_refunds()
            else:
                messagebox.showerror("Error", "Could not submit request.",
                                     parent=d)

        tk.Button(d, text="Submit",
                  bg=self.colors["success"], fg="white", relief="flat",
                  padx=20, pady=6, command=submit
                  ).pack(side="right", padx=20, pady=14)
        tk.Button(d, text="Cancel",
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  padx=20, pady=6, command=d.destroy
                  ).pack(side="right", pady=14)

    def _show_refund_audit_for_selected(self):
        sel = self.orders_tree.selection()
        if not sel:
            return
        order_id = self.orders_tree.item(sel[0])["values"][0]
        rows = self.list_refund_audit(order_id=order_id)
        if not rows:
            messagebox.showinfo("No refunds",
                                f"No refund history for {order_id}.")
            return
        d = tk.Toplevel(self.root); d.title(f"Refund Audit — {order_id}")
        d.geometry("760x340"); d.transient(self.root); d.grab_set()
        cols = ("id", "ref", "amount", "reason", "method", "by", "when")
        tree = ttk.Treeview(d, columns=cols, show="headings", height=12)
        for c, w in zip(cols, (40, 220, 80, 200, 110, 110, 130)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for r in rows:
            tree.insert("", "end", values=(
                r[0], r[2], f"£{(r[3] or 0):.2f}",
                f"{r[6] or ''} • {r[5] or ''}".strip(" •"),
                r[7] or "—", r[8] or "—", r[10],
            ))
        tk.Button(d, text="Close",
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  padx=20, pady=6, command=d.destroy
                  ).pack(side="bottom", pady=8)

    def refresh_orders(self):
        """Repopulate the order history list."""
        if not getattr(self, "orders_tab", None) or not getattr(self.orders_tab, "_lazy_built", False):
            return
        for item in self.orders_tree.get_children():
            self.orders_tree.delete(item)

        # Filter to current user's orders if logged in (admins see everything)
        visible_orders = self.orders
        if self.current_user and self.user_type != "Admin":
            visible_orders = [o for o in self.orders if o.get("user") == self.current_user]

        for order in reversed(visible_orders):
            item_count = sum(order["items"].values())
            self.orders_tree.insert(
                "",
                "end",
                values=(
                    order["order_id"],
                    order["timestamp"],
                    f"{order['user']} ({order['user_type']})",
                    f"{item_count} items",
                    f"£{order['total']:.2f}",
                ),
            )

    def show_order_details(self, event):
        """Show full details of a selected order."""
        selection = self.orders_tree.selection()
        if not selection:
            return

        order_id = self.orders_tree.item(selection[0])["values"][0]
        order = next((o for o in self.orders if o["order_id"] == order_id), None)

        if not order:
            return

        details = (
            f"Order ID: {order['order_id']}\n"
            f"Date: {order['timestamp']}\n"
            f"Customer: {order['user']} ({order['user_type']})\n\n"
            f"Items:\n"
        )
        for item, qty in order["items"].items():
            details += f"  • {item} x {qty}\n"
        details += (
            f"\nSubtotal: £{order['subtotal']:.2f}\n"
            f"Discount: £{order['discount']:.2f}\n"
            f"Total: £{order['total']:.2f}"
        )

        messagebox.showinfo(f"Order {order['order_id']}", details)

