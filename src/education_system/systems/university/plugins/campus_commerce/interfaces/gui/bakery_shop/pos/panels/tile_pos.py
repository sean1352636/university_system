
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t
from ..context import *  # noqa: F401,F403


class TilePOSPanelMixin:
    def _build_tilepos_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Label(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.tile_pos.labels.category', default="Category:"), bg=bg,
                 font=("Arial", 12, "bold")).pack(side="left")
        self._tilepos_cat = tk.StringVar(value=_t('gui.operations.commerce.bakery_shop.pos.panels.tile_pos.values.all', default="All"))
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
        tk.Label(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.tile_pos.labels.search', default="Search:"), bg=bg).pack(side="right")
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
        tk.Label(right, text=_t('gui.operations.commerce.bakery_shop.pos.panels.tile_pos.labels.ticket', default="Ticket"), bg=bg,
                 font=("Arial", 14, "bold")).pack(pady=4)
        self._tilepos_ticket_tree = ttk.Treeview(
            right, columns=("item", "qty", "line"),
            show="headings", height=18)
        for c, h, w in [("item", "Item", 160), ("qty", "Qty", 50),
                        ("line", "Line", 80)]:
            self._tilepos_ticket_tree.heading(c, text=h)
            self._tilepos_ticket_tree.column(c, width=w, anchor="w")
        self._tilepos_ticket_tree.pack(fill="both", expand=True, padx=6)
        self._tilepos_total_lbl = tk.Label(right, text=_t('gui.operations.commerce.bakery_shop.pos.panels.tile_pos.labels.total_0_00', default="Total: £0.00"),
                                            font=("Arial", 14, "bold"), bg=bg)
        self._tilepos_total_lbl.pack(pady=6)
        btns = tk.Frame(right, bg=bg); btns.pack(fill="x", padx=6, pady=4)
        tk.Button(btns, text=_t('gui.operations.commerce.bakery_shop.pos.panels.tile_pos.buttons.remove', default="− Remove"), command=self._tilepos_remove,
                  relief="flat").pack(side="left", padx=2)
        tk.Button(btns, text=_t('gui.operations.commerce.bakery_shop.pos.panels.tile_pos.buttons.clear', default="Clear"), command=self._tilepos_clear,
                  relief="flat").pack(side="left", padx=2)
        tk.Button(right, text=_t('gui.operations.commerce.bakery_shop.pos.panels.tile_pos.buttons.pay_split_tender', default="💵 Pay (split-tender)"),
                  command=self._tilepos_pay,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  font=("Arial", 12, "bold"), pady=10).pack(fill="x", padx=6, pady=4)
        tk.Button(right, text=_t('gui.operations.commerce.bakery_shop.pos.panels.tile_pos.buttons.send_to_cart', default="➕ Send to cart"),
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
            logger.debug("Suppressed exception", exc_info=True)
        self.set_status("Tickets sent to cart.")

    def _tilepos_pay(self):
        if not self._tilepos_ticket:
            messagebox.showinfo(_t('gui.operations.commerce.bakery_shop.pos.panels.tile_pos.dialogs.pay', default="Pay"), _t('gui.operations.commerce.bakery_shop.pos.panels.tile_pos.dialogs.ticket_is_empty', default="Ticket is empty."), parent=self.root)
            return
        total = self._tilepos_total
        self._split_tender_dialog(total, list(self._tilepos_ticket.items()))

