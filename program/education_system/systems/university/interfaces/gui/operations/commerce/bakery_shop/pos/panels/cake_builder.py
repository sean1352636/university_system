
from education_system.systems.university.infrastructure.i18n import get_text as _t
from ..context import *  # noqa: F401,F403


class CakeBuilderPanelMixin:
    def _build_cakebuilder_panel(self, parent):
        bg = self.colors["background"]
        tk.Label(parent, text=_t('gui.operations.commerce.bakery_shop.pos.panels.cake_builder.labels.custom_cake_builder', default="🎂 Custom Cake Builder"),
                 bg=bg, font=("Georgia", 16, "bold")).pack(pady=8)
        tk.Button(parent, text=_t('gui.operations.commerce.bakery_shop.pos.panels.cake_builder.buttons.open_builder', default="▶ Open builder"),
                  command=self._cakebuilder_open,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  font=("Arial", 12, "bold"),
                  padx=14, pady=10).pack(pady=6)
        tk.Label(parent, text=_t('gui.operations.commerce.bakery_shop.pos.panels.cake_builder.labels.existing_custom_cake_orders', default="Existing custom cake orders"),
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

