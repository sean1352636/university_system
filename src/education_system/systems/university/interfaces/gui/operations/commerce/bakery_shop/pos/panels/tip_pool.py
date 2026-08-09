
from education_system.systems.university.infrastructure.i18n import get_text as _t
from ..context import *  # noqa: F401,F403


class TipPoolPanelMixin:
    def _build_tippool_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.tip_pool.buttons.start_period', default="▶ Start period"), command=self._tippool_start,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.tip_pool.buttons.distribute_close', default="🧮 Distribute & close"),
                  command=self._tippool_close,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.tip_pool.buttons.refresh', default="↻ Refresh"), command=self._tippool_refresh,
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
                messagebox.showerror(_t('gui.operations.commerce.bakery_shop.pos.panels.tip_pool.dialogs.tip_pool', default="Tip pool"), _t('gui.operations.commerce.bakery_shop.pos.panels.tip_pool.dialogs.not_an_open_period', default="Not an open period."),
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
            _t('gui.operations.commerce.bakery_shop.pos.panels.tip_pool.dialogs.tip_pool', default="Tip pool"),
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
        messagebox.showinfo(_t('gui.operations.commerce.bakery_shop.pos.panels.tip_pool.dialogs.tip_pool', default="Tip pool"),
                            "Distribution:\n" + "\n".join(
                                f"{n}: £{a:.2f}" for n, a in dist.items()),
                            parent=self.root)
        self._tippool_refresh()

