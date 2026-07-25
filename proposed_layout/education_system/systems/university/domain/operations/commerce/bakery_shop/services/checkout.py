"""CheckoutMixin — auto-split from bakery_shop.py."""
from education_system.systems.university.domain.operations.commerce.bakery_shop._common import *  # noqa: F401,F403


class CheckoutMixin:
    def _finance_user_id(self):
        """Identifier used by the finance subsystem for the current user.

        student_finance_accounts is keyed by username (e.g. 'admin',
        'S12345'), not by the auth row's numeric id — so we prefer
        username here. The numeric user_id is only a last resort for
        records that explicitly use it."""
        u = self._auth_user or {}
        return (u.get('student_id') or u.get('username')
                or u.get('user_id') or self.current_user)

    def _get_user_balance(self):
        """Look up the current user's student finance account balance."""
        try:
            from education_system.systems.university.infrastructure.utils.finance_integration import (
                get_student_finance_account_balance,
            )
            uid = self._finance_user_id()
            if not uid:
                return None
            bal = get_student_finance_account_balance(str(uid))
            return float(bal) if bal is not None else None
        except Exception:
            logger.debug("Finance balance lookup failed", exc_info=True)
            return None

    def _user_email(self):
        """Email of the currently logged-in user, if known."""
        u = self._auth_user or {}
        email = u.get('email')
        if email:
            return email
        try:
            from education_system.systems.university.infrastructure.utils.finance_integration import (
                get_student_info,
            )
            uid = self._finance_user_id()
            if uid:
                info = get_student_info(str(uid)) or {}
                return info.get('email')
        except Exception:
            logger.debug("Email lookup failed", exc_info=True)
        return None

    def _format_items_text(self, items):
        lines = []
        for name, qty in items.items():
            price = 0.0
            for cat in self.products.values():
                if name in cat:
                    price = cat[name]["price"]
                    break
            lines.append(f"  - {name} x{qty} @ £{price:.2f} = £{price * qty:.2f}")
        return "\n".join(lines)

    def _send_purchase_receipt(self, order):
        """Render bakery_purchase_receipt and deliver it via the
        university email pipeline. In the default DB-only mode this
        lands in the recipient's in-app inbox (inbox_messages) and
        is mirrored to stored_emails — same path the student CRUD
        welcome email uses."""
        try:
            email = self._user_email()
            if not email:
                logger.info("Skipping receipt email: no address for user=%s",
                            order.get('user'))
                return False
            from education_system.systems.university.infrastructure.email.email_service import (
                send_template_email,
            )
            account_info = ""
            if order["payment_method"] == "student_account":
                bal = self._get_user_balance()
                if bal is not None:
                    account_info = f"Your new Student Finance Account balance: £{bal:.2f}"
            # Build a human-readable payment line. If splits exist, show them.
            splits = order.get("split_payments") or []
            if splits:
                pay_lines = []
                for s in splits:
                    label = s["method"].replace("_", " ").title()
                    if s.get("ref"):
                        label += f" ({s['ref']})"
                    pay_lines.append(f"{label}: £{s['amount']:.2f}")
                payment_breakdown = "  •  ".join(pay_lines)
            else:
                payment_breakdown = order["payment_method"].replace("_", " ").title()

            billing_block = ""
            if order.get("billing_code"):
                billing_block = (f"Billed to department code: "
                                  f"{order['billing_code']}\n")

            vars_ = {
                "customer_name":     order["user"],
                "customer_type":     order["user_type"],
                "order_id":          order["order_id"],
                "transaction_date":  order["timestamp"],
                "items_text":        self._format_items_text(order["items"]),
                "subtotal":          f"{order['subtotal']:.2f}",
                "discount":          f"{order['discount']:.2f}",
                "vat_amount":        f"{order.get('vat_amount', 0) or 0:.2f}",
                "tip_amount":        f"{order.get('tip_amount', 0) or 0:.2f}",
                "total_amount":      f"{order['total']:.2f}",
                "payment_method":    order["payment_method"].replace("_", " ").title(),
                "payment_breakdown": payment_breakdown,
                "billing_block":     billing_block,
                "account_balance_info": account_info,
            }
            ok = send_template_email('commerce/bakery_purchase_receipt', email, vars_)
            if ok:
                logger.info("Bakery purchase receipt delivered to %s for order=%s",
                            email, order["order_id"])
            return bool(ok)
        except Exception:
            logger.exception("Failed to send bakery purchase receipt")
            return False

    def _send_refund_receipt(self, order):
        """Render bakery_payment_refund_receipt and deliver it via the
        university email pipeline (DB-only mode → in-app inbox)."""
        try:
            email = self._user_email()
            if not email:
                return False
            from education_system.systems.university.infrastructure.email.email_service import (
                send_template_email,
            )
            account_info = ""
            if order["payment_method"] == "student_account":
                bal = self._get_user_balance()
                if bal is not None:
                    account_info = f"Your new Student Finance Account balance: £{bal:.2f}"
            vars_ = {
                "customer_name":     order["user"],
                "order_id":          order["order_id"],
                "refund_ref":        order["refund_ref"],
                "amount":            f"{order['total']:.2f}",
                "method":            order["payment_method"].replace("_", " ").title(),
                "refund_date":       order["refund_timestamp"],
                "items_text":        self._format_items_text(order["items"]),
                "account_balance_info": account_info,
            }
            ok = send_template_email('commerce/bakery_payment_refund_receipt', email, vars_)
            if ok:
                logger.info("Bakery refund receipt delivered to %s for order=%s",
                            email, order["order_id"])
            return bool(ok)
        except Exception:
            logger.exception("Failed to send bakery refund receipt")
            return False

    def checkout(self):
        """Open the checkout dialog. Lets the user enter a promo code,
        redeem loyalty points, claim a birthday treat, and pick a
        payment method. The discount engine recomputes live."""
        if not self.cart:
            messagebox.showinfo("Empty Cart", "Your cart is empty!")
            return

        if self.user_type == "Guest":
            if not messagebox.askyesno(
                "Login Recommended",
                "You're checking out as a guest.\nLogin as Student or Staff to "
                "get a discount and earn loyalty points.\n\nContinue as guest?",
            ):
                return

        dlg = tk.Toplevel(self.root)
        dlg.title("Checkout")
        dlg.geometry("560x720")
        dlg.configure(bg=self.colors["background"])
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text="💳 Checkout",
                 font=("Georgia", 18, "bold"),
                 bg=self.colors["background"], fg=self.colors["text"]).pack(pady=10)

        # Force the empty dialog to paint before we start running the
        # synchronous DB queries below (loyalty, birthday, discounts).
        # Without this the user sees nothing happen for the ~100ms those
        # queries take.
        dlg.update_idletasks()

        # --- State vars for live recompute ---
        promo_var = tk.StringVar(value="")
        loyalty_var = tk.IntVar(value=0)
        bday_eligible = self.is_birthday_today(self.current_user) \
            and not self._birthday_already_claimed(self.current_user) \
            if self.current_user else False
        bday_var = tk.BooleanVar(value=bday_eligible)
        method_var = tk.StringVar(value="card")

        # Phase-4 vars
        tip_var = tk.DoubleVar(value=0.0)          # GBP £
        gc_var = tk.StringVar(value="")
        gc_meta = [None]                            # mutable holder
        billing_var = tk.StringVar(value="")
        billing_meta = [None]

        # --- Loyalty info ---
        loyalty_balance, lifetime = self.get_loyalty_points(self.current_user)
        loyalty_max_redeem = min(
            loyalty_balance,
            int(self.compute_discounts(self.cart)["total"] * LOYALTY_POINTS_PER_GBP_REDEEM),
        )

        # --- Breakdown frame (live) ---
        breakdown_frame = tk.LabelFrame(
            dlg, text="Order Summary",
            bg=self.colors["card"], fg=self.colors["text"],
            font=("Arial", 11, "bold"),
        )
        breakdown_frame.pack(fill="x", padx=15, pady=8)

        def render_breakdown():
            for w in breakdown_frame.winfo_children():
                w.destroy()
            try:
                result = self.compute_discounts(
                    self.cart,
                    promo_code=promo_var.get().strip(),
                    loyalty_redeem_pts=int(loyalty_var.get() or 0),
                    apply_birthday=bool(bday_var.get()),
                )
            except Exception:
                logger.exception("compute_discounts failed during checkout")
                tk.Label(breakdown_frame, text="(could not compute)",
                         bg=self.colors["card"]).pack()
                return None

            tk.Label(breakdown_frame, text=f"Subtotal: £{result['subtotal']:.2f}",
                     bg=self.colors["card"], font=("Arial", 11)
                     ).pack(anchor="w", padx=10, pady=2)
            for label, amount in result["breakdown"]:
                tk.Label(breakdown_frame,
                         text=f"  {label}: £{amount:.2f}",
                         bg=self.colors["card"], fg=self.colors["success"]
                         if amount < 0 else self.colors["text"],
                         font=("Arial", 10)
                         ).pack(anchor="w", padx=10)
            # VAT line (informational; price is VAT-inclusive)
            vat = self.compute_vat(self.cart)
            if vat["vat"] > 0:
                tk.Label(breakdown_frame,
                         text=f"  of which VAT: £{vat['vat']:.2f}",
                         bg=self.colors["card"], fg=self.colors["text"],
                         font=("Arial", 9, "italic")
                         ).pack(anchor="w", padx=10)
            tip_amt = float(tip_var.get() or 0)
            if tip_amt > 0:
                tk.Label(breakdown_frame,
                         text=f"  Tip: £{tip_amt:.2f}",
                         bg=self.colors["card"], fg=self.colors["secondary"],
                         font=("Arial", 10)
                         ).pack(anchor="w", padx=10)
            # Gift card credit (validated on Apply)
            if gc_meta[0]:
                applied = min(gc_meta[0]["balance"],
                              result["total"] + tip_amt)
                tk.Label(breakdown_frame,
                         text=f"  Gift card {gc_meta[0]['code']}: -£{applied:.2f}",
                         bg=self.colors["card"], fg=self.colors["success"],
                         font=("Arial", 10)
                         ).pack(anchor="w", padx=10)
            # Billing-code marker
            if billing_meta[0]:
                tk.Label(breakdown_frame,
                         text=f"  Billed to: {billing_meta[0]['code']} "
                              f"({billing_meta[0]['department']})",
                         bg=self.colors["card"], fg=self.colors["primary"],
                         font=("Arial", 10, "italic")
                         ).pack(anchor="w", padx=10)
            grand = result["total"] + tip_amt
            tk.Label(breakdown_frame,
                     text=f"Total Due: £{grand:.2f}",
                     bg=self.colors["card"], fg=self.colors["primary"],
                     font=("Arial", 13, "bold")
                     ).pack(anchor="w", padx=10, pady=(6, 4))
            if result["loyalty_earned"]:
                tk.Label(breakdown_frame,
                         text=f"You'll earn {result['loyalty_earned']} loyalty pts ✨",
                         bg=self.colors["card"], fg=self.colors["secondary"],
                         font=("Arial", 9, "italic")
                         ).pack(anchor="w", padx=10)
            for w in result.get("warnings", []):
                tk.Label(breakdown_frame, text=f"⚠ {w}",
                         bg=self.colors["card"], fg=self.colors["danger"],
                         font=("Arial", 9)).pack(anchor="w", padx=10)
            return result

        live_result = [render_breakdown()]

        # --- Promo code entry ---
        promo_frame = tk.LabelFrame(
            dlg, text="🎟 Promo Code",
            bg=self.colors["background"], fg=self.colors["text"],
            font=("Arial", 10, "bold"),
        )
        promo_frame.pack(fill="x", padx=15, pady=4)
        row = tk.Frame(promo_frame, bg=self.colors["background"])
        row.pack(fill="x", padx=8, pady=4)
        tk.Entry(row, textvariable=promo_var, font=("Arial", 11),
                 width=20).pack(side="left", padx=4)
        tk.Button(row, text="Apply", font=("Arial", 10),
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  command=lambda: live_result.__setitem__(0, render_breakdown())
                  ).pack(side="left", padx=4)

        # --- Loyalty redemption ---
        if self.current_user and loyalty_balance > 0:
            ly_frame = tk.LabelFrame(
                dlg,
                text=f"⭐ Loyalty Points — balance {loyalty_balance} pts "
                     f"(100 pts = £1)",
                bg=self.colors["background"], fg=self.colors["text"],
                font=("Arial", 10, "bold"),
            )
            ly_frame.pack(fill="x", padx=15, pady=4)
            row2 = tk.Frame(ly_frame, bg=self.colors["background"])
            row2.pack(fill="x", padx=8, pady=4)
            tk.Label(row2, text="Redeem:", bg=self.colors["background"]).pack(side="left")
            spin = tk.Spinbox(row2, from_=0, to=loyalty_max_redeem, increment=100,
                              textvariable=loyalty_var, width=8,
                              command=lambda: live_result.__setitem__(0, render_breakdown()))
            spin.pack(side="left", padx=6)
            tk.Label(row2, text=f"of {loyalty_max_redeem} pts available",
                     bg=self.colors["background"],
                     font=("Arial", 9, "italic")).pack(side="left", padx=6)

        # --- Birthday treat ---
        if bday_eligible:
            tk.Checkbutton(
                dlg,
                text="🎂 Claim your Birthday Treat (20% off, once a year)",
                variable=bday_var, bg=self.colors["background"],
                fg=self.colors["text"], font=("Arial", 10, "bold"),
                command=lambda: live_result.__setitem__(0, render_breakdown()),
            ).pack(padx=15, pady=4, anchor="w")

        # --- Tip ---
        tip_frame = tk.LabelFrame(
            dlg, text="💝 Tip",
            bg=self.colors["background"], fg=self.colors["text"],
            font=("Arial", 10, "bold"),
        )
        tip_frame.pack(fill="x", padx=15, pady=4)
        tip_row = tk.Frame(tip_frame, bg=self.colors["background"])
        tip_row.pack(fill="x", padx=8, pady=4)
        def _set_tip_pct(pct):
            base = (live_result[0] or self.compute_discounts(self.cart))["total"]
            tip_var.set(round(base * pct, 2))
            live_result[0] = render_breakdown()
        for label, pct in (("None", 0), ("5%", 0.05),
                           ("10%", 0.10), ("15%", 0.15)):
            tk.Button(tip_row, text=label,
                      bg=self.colors["secondary"], fg="white",
                      relief="flat", padx=8, pady=2,
                      command=lambda p=pct: _set_tip_pct(p)
                      ).pack(side="left", padx=2)
        tk.Label(tip_row, text="  Custom £:",
                 bg=self.colors["background"]).pack(side="left", padx=4)
        tk.Spinbox(tip_row, from_=0, to=100, increment=0.50,
                   textvariable=tip_var, width=8,
                   command=lambda: live_result.__setitem__(0, render_breakdown())
                   ).pack(side="left", padx=4)

        # --- Gift card ---
        gc_frame = tk.LabelFrame(
            dlg, text="🎁 Gift Card",
            bg=self.colors["background"], fg=self.colors["text"],
            font=("Arial", 10, "bold"),
        )
        gc_frame.pack(fill="x", padx=15, pady=4)
        gc_row = tk.Frame(gc_frame, bg=self.colors["background"])
        gc_row.pack(fill="x", padx=8, pady=4)
        tk.Entry(gc_row, textvariable=gc_var, width=20).pack(side="left", padx=4)

        def apply_gc():
            meta, err = self.validate_gift_card(gc_var.get())
            if not meta:
                gc_meta[0] = None
                messagebox.showerror("Gift Card", err or "Invalid card",
                                     parent=dlg)
            else:
                gc_meta[0] = meta
                messagebox.showinfo("Gift Card",
                                    f"Card {meta['code']} accepted. "
                                    f"Balance £{meta['balance']:.2f}",
                                    parent=dlg)
            live_result[0] = render_breakdown()

        tk.Button(gc_row, text="Apply",
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  command=apply_gc).pack(side="left", padx=4)

        # --- Billing code (departmental) ---
        bc_frame = tk.LabelFrame(
            dlg, text="🏛 Departmental Billing Code",
            bg=self.colors["background"], fg=self.colors["text"],
            font=("Arial", 10, "bold"),
        )
        bc_frame.pack(fill="x", padx=15, pady=4)
        bc_row = tk.Frame(bc_frame, bg=self.colors["background"])
        bc_row.pack(fill="x", padx=8, pady=4)
        tk.Entry(bc_row, textvariable=billing_var, width=20
                 ).pack(side="left", padx=4)

        def apply_bc():
            meta = self.validate_billing_code(billing_var.get())
            if not meta:
                billing_meta[0] = None
                messagebox.showerror("Billing Code",
                                     "Code not recognised or inactive.",
                                     parent=dlg)
            else:
                billing_meta[0] = meta
                messagebox.showinfo("Billing Code",
                                    f"Charge to {meta['department']} "
                                    f"({meta['code']}) confirmed.",
                                    parent=dlg)
            live_result[0] = render_breakdown()

        tk.Button(bc_row, text="Apply",
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  command=apply_bc).pack(side="left", padx=4)

        # --- Payment method ---
        pay_frame = tk.LabelFrame(
            dlg, text="Payment Method (covers remainder)",
            bg=self.colors["background"], fg=self.colors["text"],
            font=("Arial", 11, "bold"),
        )
        pay_frame.pack(fill="x", padx=15, pady=6)

        # Defer the finance-account balance lookup so the dialog appears
        # immediately. _get_user_balance() makes a cross-DB call into
        # finance_integration which can take several hundred ms on a
        # cold open — running it inline blocks the window paint.
        balance_holder = [None]      # populated by _load_balance below
        balance_loaded = [False]

        def _refresh_methods_for(total):
            for w in pay_frame.winfo_children():
                if isinstance(w, tk.Radiobutton):
                    w.destroy()
            balance = balance_holder[0]
            if not balance_loaded[0]:
                sa_text = "🎓 Student Finance Account (loading…)"
                sa_state = "disabled"
            elif balance is None:
                sa_text = "🎓 Student Finance Account (unavailable)"
                sa_state = "disabled"
            else:
                sa_text = f"🎓 Student Finance Account (balance: £{balance:.2f})"
                if balance < total:
                    sa_text += "  — insufficient funds"
                    sa_state = "disabled"
                else:
                    sa_state = "normal"
            for value, label, state in (
                ("cash", "💵 Cash", "normal"),
                ("card", "💳 Card", "normal"),
                ("student_account", sa_text, sa_state),
            ):
                tk.Radiobutton(
                    pay_frame, text=label, variable=method_var, value=value,
                    state=state, bg=self.colors["background"],
                    fg=self.colors["text"], font=("Arial", 11),
                    anchor="w", justify="left", wraplength=480,
                ).pack(fill="x", pady=2, padx=8)

        _refresh_methods_for(live_result[0]["total"] if live_result[0] else 0.0)

        def _load_balance():
            try:
                balance_holder[0] = self._get_user_balance()
            except Exception:
                logger.debug("deferred balance lookup failed", exc_info=True)
                balance_holder[0] = None
            balance_loaded[0] = True
            if dlg.winfo_exists():
                r = live_result[0]
                _refresh_methods_for(r["total"] if r else 0.0)
        dlg.after(1, _load_balance)

        # Re-render also updates payment availability (balance vs total).
        def render_all():
            r = render_breakdown()
            live_result[0] = r
            _refresh_methods_for(r["total"] if r else 0.0)

        # Wire promo Apply + loyalty + birthday handlers to render_all.
        # Re-finding the Apply button is fragile — just rebuild bindings now.
        promo_var.trace_add("write", lambda *a: None)  # placeholder, Apply is explicit

        # --- Buttons ---
        btns = tk.Frame(dlg, bg=self.colors["background"])
        btns.pack(side="bottom", fill="x", pady=12)
        tk.Button(btns, text="Cancel", font=("Arial", 11),
                  bg=self.colors["secondary"], fg="white", relief="flat",
                  padx=20, pady=6, command=dlg.destroy
                  ).pack(side="right", padx=20)
        tk.Button(btns, text="Recalculate", font=("Arial", 11),
                  bg=self.colors["accent"], fg=self.colors["text"],
                  relief="flat", padx=14, pady=6,
                  command=render_all).pack(side="right", padx=4)

        def pay_now():
            r = live_result[0] or self.compute_discounts(self.cart)
            dlg.destroy()
            self._complete_checkout(
                method_var.get(), r,
                promo_var.get().strip(),
                int(loyalty_var.get() or 0),
                bool(bday_var.get()),
                tip_amount=float(tip_var.get() or 0),
                gift_card_meta=gc_meta[0],
                billing_meta=billing_meta[0],
            )
        tk.Button(btns, text="Pay Now", font=("Arial", 11, "bold"),
                  bg=self.colors["success"], fg="white", relief="flat",
                  padx=20, pady=6, command=pay_now
                  ).pack(side="right", padx=5)

    def _complete_checkout(self, payment_method, discount_result,
                           promo_code, loyalty_redeem_pts, apply_birthday,
                           *, tip_amount=0.0, gift_card_meta=None,
                           billing_meta=None):
        """Place the order using the chosen payment method and apply all
        engine side-effects: loyalty points, punch cards, promo
        consumption, referral redemption, birthday/first-purchase
        claims, gift-card redemption, tip ledger, departmental billing,
        VAT breakdown, and split-payment record."""
        order_id = f"ORD-{len(self.orders) + 1001}"
        total = discount_result["total"]
        subtotal = discount_result["subtotal"]
        total_discount = discount_result["total_discount"]
        tip_amount = max(0.0, float(tip_amount or 0))
        grand_due = round(total + tip_amount, 2)

        # Compute splits: gift card → billing code → selected method.
        splits = []
        remaining = grand_due

        gift_card_applied = 0.0
        if gift_card_meta and remaining > 0:
            gift_card_applied = round(min(gift_card_meta["balance"],
                                          remaining), 2)
            if gift_card_applied > 0:
                splits.append({"method": "gift_card",
                                "amount": gift_card_applied,
                                "ref": gift_card_meta["code"]})
                remaining = round(remaining - gift_card_applied, 2)

        if billing_meta and remaining > 0:
            splits.append({"method": "billing_code",
                            "amount": remaining,
                            "ref": billing_meta["code"]})
            remaining_method = remaining
            remaining = 0.0
        else:
            remaining_method = 0.0

        if remaining > 0:
            splits.append({"method": payment_method, "amount": remaining})

        # 1. Charge student account if applicable (only its share).
        if payment_method == "student_account" and remaining > 0:
            try:
                from education_system.systems.university.infrastructure.utils.finance_integration import (
                    process_student_finance_account_payment,
                )
                uid = self._finance_user_id()
                result = process_student_finance_account_payment(
                    student_id=str(uid), amount=remaining,
                    description="Bakery Shop purchase",
                    transaction_source="Bakery",
                    transaction_ref=f"BAKERY_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    processed_by=self.current_user or "system",
                )
                if not result.get("success"):
                    messagebox.showerror(
                        "Payment Failed",
                        result.get("message", "Could not charge student finance account."),
                    )
                    return
            except Exception as e:
                logger.exception("Student account charge failed")
                messagebox.showerror("Payment Failed",
                                     f"Could not charge student account: {e}")
                return

        # Redeem gift card after we know the order will go through.
        if gift_card_applied > 0 and gift_card_meta:
            ok = self._redeem_gift_card(gift_card_meta["code"],
                                        gift_card_applied,
                                        order_id=order_id,
                                        txn_type="redeem")
            if not ok:
                messagebox.showerror("Gift Card",
                                     "Could not redeem gift card.")
                return

        vat_info = self.compute_vat(self.cart)
        order = {
            "order_id": order_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user": self.current_user or "Guest",
            "user_type": self.user_type,
            "items": dict(self.cart),
            "subtotal": round(subtotal, 2),
            "discount": round(total_discount, 2),
            "total": round(grand_due, 2),
            "payment_method": (
                "billing_code" if billing_meta else
                ("gift_card" if (gift_card_applied >= grand_due - 0.01)
                 else payment_method)
            ),
            "refunded": False,
            "refund_ref": None,
            "refund_timestamp": None,
            "promo_code": discount_result["promo_meta"]["code"]
                if discount_result.get("promo_meta") else None,
            "loyalty_earned": discount_result["loyalty_earned"],
            "loyalty_redeemed": discount_result["loyalty_redeemed"],
            "discount_breakdown": discount_result["breakdown"],
            "tip_amount": round(tip_amount, 2),
            "vat_amount": vat_info["vat"],
            "split_payments": splits,
            "billing_code": billing_meta["code"] if billing_meta else None,
            "gift_card_code": gift_card_meta["code"] if gift_card_meta else None,
        }

        # 2. Decrement stock + consume oldest batches FIFO. Capture any
        # items that transitioned from in-stock to 0 in this transaction
        # so we can fire sold-out admin alerts after the order is logged.
        sold_out_items = []  # list of (item_name, category)
        for item_name, qty in self.cart.items():
            info = self._product_info(item_name)
            if info:
                was_in_stock = info.get("stock", 0) > 0
                info["stock"] = max(0, info["stock"] - qty)
                if was_in_stock and info["stock"] == 0:
                    sold_out_items.append(
                        (item_name, self._product_category(item_name))
                    )
                try:
                    self._consume_batches_fifo(item_name, qty)
                except Exception:
                    logger.exception("FIFO consume failed for %s", item_name)

        self.orders.append(order)
        self.save_data()

        # Tip ledger (best-effort).
        if tip_amount > 0:
            self._record_tip(order_id, tip_amount)

        # Low-stock alert check (best-effort, never blocks checkout).
        try:
            self.check_low_stock()
        except Exception:
            logger.exception("check_low_stock failed post-order")

        # 3. Apply discount-engine side effects (best-effort each).
        try:
            if discount_result["loyalty_redeemed"]:
                self._redeem_loyalty_points(self.current_user,
                                            discount_result["loyalty_redeemed"])
            if discount_result["loyalty_earned"] and self.current_user:
                self._add_loyalty_points(self.current_user,
                                         discount_result["loyalty_earned"])

            # Punch card: bump for every beverage purchased; if a free
            # item was redeemed for the category, reset its counter.
            if self.current_user:
                for item, qty in self.cart.items():
                    cat = self._product_category(item)
                    if cat in PUNCH_CARD_CATEGORIES:
                        self._bump_punch(self.current_user, cat, delta=qty)
                redeemed_cat = discount_result.get("punch_redeemed_category")
                if redeemed_cat:
                    self._record_punch_redemption(self.current_user, redeemed_cat)

            # Promo consumption
            if discount_result.get("promo_meta"):
                self._consume_promo(
                    discount_result["promo_meta"]["code"],
                    self.current_user or "Guest", order_id,
                    sum(amt for lbl, amt in discount_result["breakdown"]
                        if lbl.startswith("Promo")) * -1,
                )

            # Referral redemption
            if discount_result.get("referral_id"):
                self._redeem_referral(discount_result["referral_id"])

            # First-purchase / birthday claim
            if discount_result.get("applied_first_purchase") and self.current_user:
                self._mark_first_purchase(self.current_user)
            if discount_result.get("applied_birthday") and self.current_user:
                self._mark_birthday_claim(self.current_user)
        except Exception:
            logger.exception("Discount-engine side effects partially failed")

        # 4. Record revenue
        try:
            from education_system.systems.university.infrastructure.utils.finance_integration import (
                record_revenue_to_finance,
            )
            record_revenue_to_finance(
                student_id=str(self._finance_user_id() or ""),
                amount=total,
                revenue_category="Bakery Sales",
                transaction_source="Bakery",
                transaction_ref=order_id,
                payment_method=payment_method.replace("_", " ").title(),
                notes="University Bakery Shop purchase",
            )
        except Exception:
            logger.debug("record_revenue_to_finance failed", exc_info=True)

        logger.info(
            "Bakery order placed order_id=%s user=%s method=%s subtotal=%.2f "
            "discount=%.2f total=%.2f pts_earned=%d pts_redeemed=%d promo=%s",
            order_id, order['user'], payment_method, subtotal, total_discount,
            total, order["loyalty_earned"], order["loyalty_redeemed"],
            order.get("promo_code") or "-",
        )

        # Send the receipt email off the critical path. send_template_email
        # writes to inbox_messages + stored_emails (and possibly SMTP), all
        # synchronous and slow enough to noticeably delay the success
        # messagebox. Spawn a daemon thread instead — the user gets instant
        # feedback while the email lands in the background.
        import threading
        def _send_receipt_bg():
            try:
                self._send_purchase_receipt(order)
            except Exception:
                logger.exception("Background receipt send failed for order %s",
                                 order_id)
            # Sold-out alerts: same background thread so Pay Now stays
            # snappy even if multiple items hit 0 in one transaction.
            for _name, _cat in sold_out_items:
                try:
                    self._notify_admins_sold_out(_name, _cat)
                except Exception:
                    logger.exception("sold-out alert failed for %s", _name)
        threading.Thread(target=_send_receipt_bg, daemon=True).start()

        msg = (f"Order Confirmed!\n\n"
               f"Order ID: {order_id}\n"
               f"Total: £{total:.2f}\n"
               f"Payment: {payment_method.replace('_', ' ').title()}\n")
        if order["loyalty_earned"]:
            msg += f"⭐ +{order['loyalty_earned']} loyalty pts\n"
        msg += "\nReceipt is being emailed to your inbox."

        self.cart.clear()
        self.refresh_cart()
        self.refresh_products()
        self.refresh_orders()
        self.refresh_refunds()
        self.refresh_loyalty()
        self.update_cart_tab_title()
        self.set_status(f"Order {order_id} placed successfully!")

        messagebox.showinfo("Order Successful", msg)

