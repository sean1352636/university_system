
from education_system.systems.university.infrastructure.i18n import get_text as _t
from ..context import *  # noqa: F401,F403


class OfflineModePanelMixin:
    def _build_offline_panel(self, parent):
        bg = self.colors["background"]
        info = tk.Label(parent,
            text=_t('gui.operations.commerce.bakery_shop.pos.panels.offline_mode.labels.offline_mode_queues_orders_locally_they_sync_to_the_central_db_w', default="Offline mode queues orders locally; they sync to the\n"
                 "central DB when you return online."),
            bg=bg, font=("Arial", 11, "italic"), justify="left")
        info.pack(anchor="w", padx=14, pady=8)
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=14, pady=6)
        self._offline_state_lbl = tk.Label(top, text="",
                                           font=("Arial", 12, "bold"), bg=bg)
        self._offline_state_lbl.pack(side="left", padx=8)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.offline_mode.buttons.toggle_offline_mode', default="Toggle offline mode"),
                  command=self._offline_toggle,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.offline_mode.buttons.sync_queued_now', default="⇪ Sync queued now"), command=self._offline_sync,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.offline_mode.buttons.refresh', default="↻ Refresh"), command=self._offline_refresh,
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
            messagebox.showinfo(_t('gui.operations.commerce.bakery_shop.pos.panels.offline_mode.dialogs.sync', default="Sync"), _t('gui.operations.commerce.bakery_shop.pos.panels.offline_mode.dialogs.still_in_offline_mode_toggle_first', default="Still in OFFLINE mode — toggle first."),
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

