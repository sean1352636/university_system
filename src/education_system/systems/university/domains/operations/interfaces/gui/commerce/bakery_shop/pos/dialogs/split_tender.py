
from education_system.systems.university.infrastructure.i18n import get_text as _t
from ..context import *  # noqa: F401,F403


class SplitTenderDialogMixin:
    def _split_tender_dialog(self, total, items):
        d = tk.Toplevel(self.root); d.title(_t('gui.operations.commerce.bakery_shop.pos.dialogs.split_tender.windows.split_tender_payment', default="Split-tender payment"))
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
        tk.Label(add_frame, text=_t('gui.operations.commerce.bakery_shop.pos.dialogs.split_tender.labels.method', default="Method:"), bg=bg).grid(row=0, column=0, sticky="e")
        m_var = tk.StringVar(value=_t('gui.operations.commerce.bakery_shop.pos.dialogs.split_tender.values.cash', default="Cash"))
        ttk.Combobox(add_frame, textvariable=m_var,
                     values=["Cash", "Card", "Campus Card", "Meal Swipe", "Gift Card"],
                     state="readonly", width=14).grid(row=0, column=1, padx=4)
        tk.Label(add_frame, text=_t('gui.operations.commerce.bakery_shop.pos.dialogs.split_tender.labels.amount', default="Amount £:"), bg=bg).grid(row=0, column=2, sticky="e")
        a_var = tk.StringVar(value=f"{total:.2f}")
        tk.Entry(add_frame, textvariable=a_var, width=10).grid(row=0, column=3, padx=4)
        tk.Label(add_frame, text=_t('gui.operations.commerce.bakery_shop.pos.dialogs.split_tender.labels.ref', default="Ref:"), bg=bg).grid(row=0, column=4, sticky="e")
        r_var = tk.StringVar()
        tk.Entry(add_frame, textvariable=r_var, width=14).grid(row=0, column=5, padx=4)

        def add_split():
            try:
                a = float(a_var.get())
            except ValueError:
                messagebox.showerror(_t('gui.operations.commerce.bakery_shop.pos.dialogs.split_tender.dialogs.split', default="Split"), _t('gui.operations.commerce.bakery_shop.pos.dialogs.split_tender.dialogs.amount_must_be_numeric', default="Amount must be numeric."),
                                     parent=d); return
            if a <= 0:
                return
            s = {"method": m_var.get(), "amount": a, "ref": r_var.get()}
            splits.append(s)
            tv.insert("", "end", values=(s["method"], f"£{a:.2f}", s["ref"]))
            rem = update_rem()
            a_var.set(f"{max(rem, 0):.2f}"); r_var.set("")

        tk.Button(add_frame, text=_t('gui.operations.commerce.bakery_shop.pos.dialogs.split_tender.buttons.add', default="+ Add"), command=add_split,
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
                messagebox.showerror(_t('gui.operations.commerce.bakery_shop.pos.dialogs.split_tender.dialogs.split', default="Split"),
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
            messagebox.showinfo(_t('gui.operations.commerce.bakery_shop.pos.dialogs.split_tender.dialogs.paid', default="Paid"),
                                f"Order {order_id} paid in full.",
                                parent=self.root)
            self._split_refresh()

        btns = tk.Frame(d, bg=bg); btns.pack(fill="x", padx=14, pady=10)
        tk.Button(btns, text=_t('gui.operations.commerce.bakery_shop.pos.dialogs.split_tender.buttons.remove_split', default="− Remove split"), command=remove_sel,
                  relief="flat").pack(side="left")
        tk.Button(btns, text=_t('gui.operations.commerce.bakery_shop.pos.dialogs.split_tender.buttons.cancel', default="Cancel"), command=d.destroy,
                  relief="flat").pack(side="right", padx=4)
        tk.Button(btns, text=_t('gui.operations.commerce.bakery_shop.pos.dialogs.split_tender.buttons.commit_payment', default="✅ Commit payment"), command=commit,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=14, pady=6,
                  font=("Arial", 11, "bold")).pack(side="right")

