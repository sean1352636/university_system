"""RefundsTabMixin — auto-split from bakery_shop.py."""
from education_system.post_18.university_system.modules.domain.commerce.bakery_shop._common import *  # noqa: F401,F403


class RefundsTabMixin:
    def build_refunds_tab(self):
        """Build the refunds tab. Visible content is admin-only."""
        self.refunds_content = tk.Frame(self.refunds_tab, bg=self.colors["background"])
        self.refunds_content.pack(fill="both", expand=True)
        self.refresh_refunds()

    def refresh_refunds(self):
        """Render the refunds tab. Admins see all purchases; others see a notice."""
        if not getattr(self, "refunds_tab", None) or not getattr(self.refunds_tab, "_lazy_built", False):
            return
        if not hasattr(self, "refunds_content"):
            return
        for w in self.refunds_content.winfo_children():
            w.destroy()

        if self.user_type != "Admin":
            tk.Label(
                self.refunds_content,
                text="🔒 Admin access required\n\nOnly administrators can process refunds.",
                font=("Arial", 14),
                bg=self.colors["background"], fg=self.colors["text"],
                justify="center",
            ).pack(expand=True, pady=50)
            return

        tk.Label(
            self.refunds_content,
            text="💳 Refund Management",
            font=("Georgia", 18, "bold"),
            bg=self.colors["background"], fg=self.colors["text"],
        ).pack(pady=15)

        tree_frame = tk.Frame(self.refunds_content, bg=self.colors["background"])
        tree_frame.pack(fill="both", expand=True, padx=20, pady=10)

        columns = ("Order ID", "Date", "Customer", "Payment", "Total", "Status")
        self.refunds_tree = ttk.Treeview(tree_frame, columns=columns,
                                         show="headings", height=16)
        widths = {"Order ID": 110, "Date": 150, "Customer": 170,
                  "Payment": 130, "Total": 90, "Status": 110}
        for col in columns:
            self.refunds_tree.heading(col, text=col)
            self.refunds_tree.column(col, width=widths[col], anchor="w")

        scroll = ttk.Scrollbar(tree_frame, orient="vertical",
                               command=self.refunds_tree.yview)
        self.refunds_tree.configure(yscrollcommand=scroll.set)
        self.refunds_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        for order in reversed(self.orders):
            status = "✅ Refunded" if order.get("refunded") else "Purchased"
            method = (order.get("payment_method") or "cash").replace("_", " ").title()
            self.refunds_tree.insert("", "end", values=(
                order["order_id"],
                order["timestamp"],
                f"{order['user']} ({order['user_type']})",
                method,
                f"£{order['total']:.2f}",
                status,
            ))

        btn_frame = tk.Frame(self.refunds_content, bg=self.colors["background"])
        btn_frame.pack(fill="x", pady=10)
        tk.Button(
            btn_frame, text="💸 Issue Refund",
            font=("Arial", 11, "bold"),
            bg=self.colors["danger"], fg="white", relief="flat",
            padx=20, pady=8, cursor="hand2",
            command=self._issue_refund_from_selection,
        ).pack(side="left", padx=20)

        tk.Label(
            btn_frame,
            text="Select a purchase above, then click Issue Refund.",
            font=("Arial", 10, "italic"),
            bg=self.colors["background"], fg=self.colors["text"],
        ).pack(side="left", padx=10)

        # --- Pending customer refund requests ---
        req_frame = tk.LabelFrame(
            self.refunds_content, text="⏳ Pending Refund Requests",
            bg=self.colors["background"], fg=self.colors["danger"],
            font=("Arial", 11, "bold"))
        req_frame.pack(fill="x", padx=20, pady=8)

        req_cols = ("id", "order_id", "user", "category", "amount",
                    "status", "when")
        req_tree = ttk.Treeview(req_frame, columns=req_cols,
                                show="headings", height=5)
        for c, w in zip(req_cols, (40, 110, 130, 170, 80, 90, 140)):
            req_tree.heading(c, text=c.title())
            req_tree.column(c, width=w, anchor="w")
        req_tree.pack(fill="x", padx=4, pady=4)

        for r in self.list_refund_requests(status="pending"):
            req_tree.insert("", "end", values=(
                r[0], r[1], r[2], r[4],
                f"£{(r[6] or 0):.2f}" if r[6] else "—",
                r[7], r[10]
            ))

        def approve_request():
            sel = req_tree.selection()
            if not sel:
                return
            rid = req_tree.item(sel[0])["values"][0]
            order_id = req_tree.item(sel[0])["values"][1]
            order = next((o for o in self.orders
                          if o["order_id"] == order_id), None)
            if not order:
                messagebox.showerror("Missing order",
                                     "Original order not found.")
                return
            full_request = next(
                (rr for rr in self.list_refund_requests()
                 if rr[0] == rid), None)
            try:
                requested_items = json.loads(full_request[5]) if full_request and full_request[5] else None
            except Exception:
                requested_items = None
            self._open_refund_dialog(
                order, refund_request_id=rid,
                prefill_reason=full_request[3] if full_request else None,
                prefill_category=full_request[4] if full_request else None,
                prefill_items=requested_items,
            )

        def reject_request():
            sel = req_tree.selection()
            if not sel:
                return
            rid = req_tree.item(sel[0])["values"][0]
            notes = simpledialog.askstring(
                "Reject", "Reason for rejecting (sent to admin notes):",
                parent=self.root) or ""
            self.update_refund_request(rid, status="rejected",
                                        admin_notes=notes)
            self.refresh_refunds()

        req_btns = tk.Frame(req_frame, bg=self.colors["background"])
        req_btns.pack(fill="x", padx=4, pady=4)
        tk.Button(req_btns, text="✓ Approve & Issue",
                  bg=self.colors["success"], fg="white", relief="flat",
                  padx=10, pady=4, command=approve_request
                  ).pack(side="left", padx=4)
        tk.Button(req_btns, text="✗ Reject",
                  bg=self.colors["danger"], fg="white", relief="flat",
                  padx=10, pady=4, command=reject_request
                  ).pack(side="left", padx=4)
        tk.Button(req_btns, text="📜 Full Audit Log",
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  padx=10, pady=4,
                  command=self._show_refund_audit_all
                  ).pack(side="right", padx=4)

    def _show_refund_audit_all(self):
        rows = self.list_refund_audit()
        d = tk.Toplevel(self.root); d.title("Refund Audit Log")
        d.geometry("900x500"); d.transient(self.root); d.grab_set()
        cols = ("id", "order_id", "ref", "amount", "reason", "category",
                "method", "by", "when")
        tree = ttk.Treeview(d, columns=cols, show="headings", height=18)
        for c, w in zip(cols, (50, 100, 220, 80, 200, 160, 100, 100, 130)):
            tree.heading(c, text=c.title())
            tree.column(c, width=w, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for r in rows:
            tree.insert("", "end", values=(
                r[0], r[1], r[2], f"£{(r[3] or 0):.2f}",
                r[5] or "", r[6] or "", r[7] or "—",
                r[8] or "—", r[10],
            ))
        tk.Button(d, text="Close",
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  padx=20, pady=6, command=d.destroy
                  ).pack(side="bottom", pady=8)

    def _issue_refund_from_selection(self):
        sel = self.refunds_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection",
                                "Select a purchase to refund.")
            return
        order_id = self.refunds_tree.item(sel[0])["values"][0]
        order = next((o for o in self.orders if o["order_id"] == order_id), None)
        if not order:
            return
        if order.get("refunded"):
            messagebox.showinfo("Already Refunded",
                                f"Order {order_id} has already been refunded.")
            return
        self._open_refund_dialog(order)

    def _open_refund_dialog(self, order, *, refund_request_id=None,
                            prefill_reason=None,
                            prefill_category=None,
                            prefill_items=None):
        """Refund dialog with reason picker, item selection (partial),
        and admin notes. Used both for admin-initiated refunds and for
        approving customer refund requests."""
        d = tk.Toplevel(self.root); d.title(f"Refund — {order['order_id']}")
        d.geometry("520x600"); d.transient(self.root); d.grab_set()

        tk.Label(d, text=f"💸 Refund: {order['order_id']}",
                 font=("Georgia", 14, "bold"),
                 bg=self.colors["background"], fg=self.colors["text"]
                 ).pack(pady=10)
        tk.Label(d,
                 text=f"Original total: £{order['total']:.2f}   "
                      f"Method: {(order.get('payment_method') or 'cash').replace('_', ' ').title()}",
                 bg=self.colors["background"]).pack(pady=2)

        # Reason category
        tk.Label(d, text="Reason category",
                 bg=self.colors["background"]).pack(anchor="w", padx=20, pady=(8, 0))
        cat_var = tk.StringVar(value=prefill_category or REFUND_REASON_CATEGORIES[0])
        ttk.Combobox(d, textvariable=cat_var, values=REFUND_REASON_CATEGORIES,
                     state="readonly", width=44).pack(padx=20)

        tk.Label(d, text="Reason notes",
                 bg=self.colors["background"]).pack(anchor="w", padx=20, pady=(8, 0))
        reason_t = tk.Text(d, width=58, height=3); reason_t.pack(padx=20)
        if prefill_reason:
            reason_t.insert("1.0", prefill_reason)

        # Item selection — partial refund
        tk.Label(d, text="Refund items (set qty 0 to skip an item)",
                 bg=self.colors["background"], font=("Arial", 10, "bold")
                 ).pack(anchor="w", padx=20, pady=(10, 2))
        items_frame = tk.Frame(d, bg=self.colors["background"])
        items_frame.pack(fill="x", padx=20)
        qty_vars = {}
        for name, qty in (order.get("items") or {}).items():
            row = tk.Frame(items_frame, bg=self.colors["background"])
            row.pack(fill="x", pady=1)
            tk.Label(row, text=f"  {name}  (ordered: {qty})", width=28,
                     anchor="w", bg=self.colors["background"]).pack(side="left")
            default_qty = int(prefill_items.get(name)) if (prefill_items
                                                             and name in prefill_items) else int(qty)
            v = tk.IntVar(value=default_qty)
            tk.Spinbox(row, from_=0, to=int(qty), textvariable=v,
                       width=5).pack(side="left", padx=4)
            qty_vars[name] = v

        # Admin notes
        tk.Label(d, text="Admin notes (internal)",
                 bg=self.colors["background"]).pack(anchor="w", padx=20, pady=(8, 0))
        notes_e = tk.Entry(d, width=58); notes_e.pack(padx=20)

        def do_refund():
            try:
                requested_items = {n: v.get() for n, v in qty_vars.items()
                                   if v.get() > 0}
                if not requested_items:
                    messagebox.showerror("Nothing to refund",
                                         "Select at least one item.",
                                         parent=d)
                    return
                amount = self.compute_partial_refund_amount(order,
                                                            requested_items)
                if amount <= 0:
                    messagebox.showerror("Zero refund",
                                         "Computed refund value is zero.",
                                         parent=d)
                    return
                if not messagebox.askyesno(
                    "Confirm Refund",
                    f"Refund £{amount:.2f} for order {order['order_id']}?\n"
                    f"Reason: {cat_var.get()}\n"
                    f"Stock for refunded items will be restored.",
                    parent=d,
                ):
                    return
                self._issue_refund(
                    order,
                    items=requested_items,
                    amount=amount,
                    reason=reason_t.get("1.0", "end").strip(),
                    reason_category=cat_var.get(),
                    admin_notes=notes_e.get().strip(),
                    refund_request_id=refund_request_id,
                )
                d.destroy()
            except Exception as e:
                logger.exception("refund dialog do_refund failed")
                messagebox.showerror("Error", str(e), parent=d)

        btns = tk.Frame(d, bg=self.colors["background"])
        btns.pack(side="bottom", fill="x", pady=12)
        tk.Button(btns, text="Cancel",
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  padx=20, pady=6, command=d.destroy
                  ).pack(side="right", padx=20)
        tk.Button(btns, text="Issue Refund",
                  bg=self.colors["danger"], fg="white", relief="flat",
                  padx=20, pady=6, command=do_refund
                  ).pack(side="right", padx=4)

    def _issue_refund(self, order, *, items=None, amount=None,
                      reason="", reason_category="", admin_notes="",
                      refund_request_id=None):
        """Restore stock for refunded items, refund via the order's
        original payment method(s), email the customer a refund receipt,
        and write an audit-trail entry. `items=None` means a full
        refund."""
        full_refund = items is None
        if full_refund:
            items = dict(order.get("items") or {})
            amount = float(order.get("total") or 0)
        else:
            if amount is None:
                amount = self.compute_partial_refund_amount(order, items)

        payment_method = order.get("payment_method") or "cash"

        # Re-credit student account if that was the original method.
        if payment_method == "student_account":
            try:
                from education_system.post_18.university_system.modules.shared.utils.finance_integration import (
                    top_up_student_finance_account,
                )
                result = top_up_student_finance_account(
                    student_id=str(order.get("user")),
                    amount=float(amount),
                    payment_method="Bakery Refund",
                    processed_by=self.current_user or "system",
                    description=f"Bakery refund for {order['order_id']}",
                )
                if not result.get("success"):
                    messagebox.showerror(
                        "Refund Failed",
                        result.get("message",
                                   "Could not credit student account."),
                    )
                    return
            except Exception as e:
                logger.exception("Student account refund failed")
                messagebox.showerror("Refund Failed",
                                     f"Could not credit student account: {e}")
                return

        # Re-credit gift card if used
        if order.get("gift_card_code"):
            try:
                self._redeem_gift_card(order["gift_card_code"],
                                       float(amount),
                                       order_id=order["order_id"],
                                       txn_type="refund")
            except Exception:
                logger.exception("Gift card refund credit failed")

        # Record refund against finance system (best-effort, non-blocking).
        try:
            from education_system.post_18.university_system.modules.shared.utils.finance_integration import (
                record_refund_to_finance,
            )
            record_refund_to_finance(
                student_id=str(order.get("user") or ""),
                refund_amount=float(amount),
                original_payment_id=None,
                refund_reason=reason or f"Refund for {order['order_id']}",
                refund_type="full" if full_refund else "partial",
                transaction_source="Bakery",
                transaction_ref=order["order_id"],
                refund_method=payment_method.replace("_", " ").title(),
                requested_by=self.current_user or "system",
                notes=f"{reason_category} • {admin_notes}".strip(" •"),
            )
        except Exception:
            logger.debug("record_refund_to_finance failed", exc_info=True)

        # Restore stock for the refunded items
        for item_name, qty in items.items():
            info = self._product_info(item_name)
            if info:
                info["stock"] = info.get("stock", 0) + int(qty)

        # Update order state.
        refund_ref = f"REF-{order['order_id']}-{int(datetime.now().timestamp())}"
        if full_refund:
            order["refunded"] = True
        order["refund_ref"] = refund_ref
        order["refund_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_data()

        # Audit
        self._record_refund_audit(
            order_id=order["order_id"], refund_ref=refund_ref,
            amount=amount, items=items, reason=reason,
            reason_category=reason_category,
            method=payment_method, notes=admin_notes,
            refund_request_id=refund_request_id,
        )

        # If this resolves a refund request, close it.
        if refund_request_id is not None:
            self.update_refund_request(refund_request_id,
                                       status="approved",
                                       admin_notes=admin_notes)

        logger.info(
            "Bakery refund issued order=%s ref=%s amount=%.2f "
            "method=%s reason=%s by=%s",
            order["order_id"], refund_ref, float(amount), payment_method,
            reason_category, self.current_user)

        # Build a partial-refund-aware copy for the receipt email.
        receipt_order = dict(order)
        receipt_order["items"] = items
        receipt_order["total"] = float(amount)
        emailed = self._send_refund_receipt(receipt_order)

        msg = (f"Refund Issued\n\n"
               f"Order: {order['order_id']}\n"
               f"Amount: £{amount:.2f} ({'full' if full_refund else 'partial'})\n"
               f"Reason: {reason_category}\n"
               f"Reference: {refund_ref}\n\n")
        msg += ("Refund receipt emailed to the customer."
                if emailed else "(Email receipt could not be sent.)")
        messagebox.showinfo("Refund Successful", msg)

        self.refresh_refunds()
        self.refresh_orders()
        self.refresh_products()

