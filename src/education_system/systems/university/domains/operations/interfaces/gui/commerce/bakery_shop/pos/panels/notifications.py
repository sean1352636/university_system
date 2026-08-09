
from education_system.systems.university.infrastructure.i18n import get_text as _t
from ..context import *  # noqa: F401,F403


class NotificationsPanelMixin:
    def _build_notif_panel(self, parent):
        bg = self.colors["background"]
        info = tk.Label(parent,
            text=_t('gui.operations.commerce.bakery_shop.pos.panels.notifications.labels.pickup_ready_and_order_status_notifications_messages_are_queued', default="Pickup-ready and order-status notifications. "
                 "Messages are queued here; an external worker would dispatch them."),
            bg=bg, font=("Arial", 11, "italic"), justify="left")
        info.pack(anchor="w", padx=14, pady=8)
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=14, pady=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.notifications.buttons.queue_new_notification', default="📨 Queue new notification"),
                  command=self._notif_new,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.notifications.buttons.mark_selected_sent', default="🚀 Mark selected sent"),
                  command=lambda: self._notif_set("sent"),
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.notifications.buttons.mark_failed', default="✖ Mark failed"),
                  command=lambda: self._notif_set("failed"),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.notifications.buttons.refresh', default="↻ Refresh"), command=self._notif_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        cols = ("id", "queued", "channel", "recipient", "subject",
                "order", "status", "sent")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=16)
        for c, h, w in [("id", "ID", 50), ("queued", "Queued", 150),
                        ("channel", "Ch", 60), ("recipient", "To", 180),
                        ("subject", "Subject", 200),
                        ("order", "Order", 110), ("status", "Status", 80),
                        ("sent", "Sent", 150)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=14, pady=6)
        self._notif_tree = tv
        self._notif_refresh()

    def _notif_refresh(self):
        tv = self._notif_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, queued_at, channel, recipient, subject, "
                "related_order, status, sent_at FROM bakery_notifications "
                "ORDER BY id DESC LIMIT 200").fetchall()
        finally:
            conn.close()
        for rid, qa, ch, rcp, subj, oid, st, sa in rows:
            tag = {"sent": "ok", "failed": "bad"}.get(st, "")
            tv.insert("", "end", iid=str(rid),
                      values=(rid, qa, ch, rcp, subj or "",
                              oid or "", st, sa or ""), tags=(tag,))
        tv.tag_configure("ok", background="#E6F4EA")
        tv.tag_configure("bad", background="#FFD9D9")

    def _notif_new(self):
        d = tk.Toplevel(self.root); d.title(_t('gui.operations.commerce.bakery_shop.pos.panels.notifications.windows.new_notification', default="New notification"))
        d.transient(self.root); d.grab_set()
        ch_var = tk.StringVar(value=_t('gui.operations.commerce.bakery_shop.pos.panels.notifications.values.sms', default="sms"))
        rcp_var = tk.StringVar()
        subj_var = tk.StringVar(value=_t('gui.operations.commerce.bakery_shop.pos.panels.notifications.values.your_order_is_ready', default="Your order is ready!"))
        body_var = tk.StringVar(
            value=_t('gui.operations.commerce.bakery_shop.pos.panels.notifications.values.hi_your_bakery_order_is_ready_for_pickup', default="Hi — your bakery order is ready for pickup."))
        ord_var = tk.StringVar()
        tk.Label(d, text=_t('gui.operations.commerce.bakery_shop.pos.panels.notifications.labels.channel', default="Channel:")).grid(row=0, column=0, padx=8, pady=4, sticky="e")
        ttk.Combobox(d, textvariable=ch_var, values=["sms", "email"],
                     state="readonly", width=10).grid(row=0, column=1, padx=8, pady=4, sticky="w")
        tk.Label(d, text=_t('gui.operations.commerce.bakery_shop.pos.panels.notifications.labels.recipient', default="Recipient:")).grid(row=1, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=rcp_var, width=30).grid(row=1, column=1, padx=8, pady=4)
        tk.Label(d, text=_t('gui.operations.commerce.bakery_shop.pos.panels.notifications.labels.subject', default="Subject:")).grid(row=2, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=subj_var, width=30).grid(row=2, column=1, padx=8, pady=4)
        tk.Label(d, text=_t('gui.operations.commerce.bakery_shop.pos.panels.notifications.labels.body', default="Body:")).grid(row=3, column=0, padx=8, pady=4, sticky="ne")
        tk.Entry(d, textvariable=body_var, width=30).grid(row=3, column=1, padx=8, pady=4)
        tk.Label(d, text=_t('gui.operations.commerce.bakery_shop.pos.panels.notifications.labels.order_id', default="Order ID:")).grid(row=4, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=ord_var, width=22).grid(row=4, column=1, padx=8, pady=4, sticky="w")
        def save():
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_notifications "
                    "(channel, recipient, subject, body, related_order, "
                    "status, queued_at) VALUES (?,?,?,?,?,?, ?)",
                    (ch_var.get(), rcp_var.get(), subj_var.get(),
                     body_var.get(), ord_var.get(), "queued", now))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._notif_refresh()
        tk.Button(d, text=_t('gui.operations.commerce.bakery_shop.pos.panels.notifications.buttons.queue', default="Queue"), command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).grid(row=5, column=0, columnspan=2, pady=10)

    def _notif_set(self, status):
        sel = self._notif_tree.focus()
        if not sel:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            if status == "sent":
                conn.execute(
                    "UPDATE bakery_notifications SET status=?, sent_at=? "
                    "WHERE id=?", (status, now, int(sel)))
            else:
                conn.execute(
                    "UPDATE bakery_notifications SET status=? WHERE id=?",
                    (status, int(sel)))
            conn.commit()
        finally:
            conn.close()
        self._notif_refresh()

