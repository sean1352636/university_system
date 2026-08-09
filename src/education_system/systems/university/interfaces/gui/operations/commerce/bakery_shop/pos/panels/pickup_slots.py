
from education_system.systems.university.infrastructure.i18n import get_text as _t
from ..context import *  # noqa: F401,F403


class PickupSlotsPanelMixin:
    def _build_slots_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.pickup_slots.buttons.generate_slots_today', default="+ Generate slots (today)"),
                  command=lambda: self._slots_generate(0),
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.pickup_slots.buttons.generate_slots_tomorrow', default="+ Generate slots (tomorrow)"),
                  command=lambda: self._slots_generate(1),
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.pickup_slots.buttons.book_selected', default="📚 Book selected"), command=self._slots_book,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.pickup_slots.buttons.release_a_booking', default="✖ Release a booking"),
                  command=self._slots_release,
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.pickup_slots.buttons.refresh', default="↻ Refresh"), command=self._slots_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        cols = ("id", "date", "time", "capacity", "booked", "remaining", "notes")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c, h, w in [("id", "ID", 50), ("date", "Date", 110),
                        ("time", "Time", 80), ("capacity", "Capacity", 90),
                        ("booked", "Booked", 90), ("remaining", "Remaining", 100),
                        ("notes", "Notes", 240)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._slots_tree = tv
        self._slots_refresh()

    def _slots_refresh(self):
        tv = self._slots_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, slot_date, slot_time, capacity, booked, notes "
                "FROM bakery_pickup_slots "
                "ORDER BY slot_date ASC, slot_time ASC LIMIT 500").fetchall()
        finally:
            conn.close()
        for rid, d, t, cap, bk, notes in rows:
            rem = (cap or 0) - (bk or 0)
            tag = "full" if rem <= 0 else ""
            tv.insert("", "end", iid=str(rid),
                      values=(rid, d, t, cap, bk, rem, notes or ""),
                      tags=(tag,))
        tv.tag_configure("full", background="#FFD9D9")

    def _slots_generate(self, day_offset):
        date = (datetime.now() + timedelta(days=day_offset)).strftime("%Y-%m-%d")
        capacity = simpledialog.askinteger(_t('gui.operations.commerce.bakery_shop.pos.panels.pickup_slots.dialogs.capacity', default="Capacity"),
                                           _t('gui.operations.commerce.bakery_shop.pos.panels.pickup_slots.dialogs.capacity_per_30_min_slot', default="Capacity per 30-min slot:"),
                                           initialvalue=3, minvalue=1,
                                           parent=self.root)
        if not capacity:
            return
        conn = self._connect()
        try:
            for hour in range(8, 18):
                for minute in (0, 30):
                    t = f"{hour:02d}:{minute:02d}"
                    conn.execute(
                        "INSERT OR IGNORE INTO bakery_pickup_slots "
                        "(slot_date, slot_time, capacity, booked) "
                        "VALUES (?,?,?,0)", (date, t, capacity))
            conn.commit()
        finally:
            conn.close()
        self._slots_refresh()

    def _slots_book(self):
        sel = self._slots_tree.focus()
        if not sel:
            return
        conn = self._connect()
        try:
            r = conn.execute(
                "SELECT capacity, booked FROM bakery_pickup_slots WHERE id=?",
                (int(sel),)).fetchone()
            if not r or r[1] >= r[0]:
                messagebox.showerror(_t('gui.operations.commerce.bakery_shop.pos.panels.pickup_slots.dialogs.slot', default="Slot"), _t('gui.operations.commerce.bakery_shop.pos.panels.pickup_slots.dialogs.slot_is_full', default="Slot is full."),
                                     parent=self.root); return
            conn.execute(
                "UPDATE bakery_pickup_slots SET booked = booked + 1 "
                "WHERE id=?", (int(sel),))
            conn.commit()
        finally:
            conn.close()
        self._slots_refresh()

    def _slots_release(self):
        sel = self._slots_tree.focus()
        if not sel:
            return
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE bakery_pickup_slots SET booked = MAX(0, booked - 1) "
                "WHERE id=?", (int(sel),))
            conn.commit()
        finally:
            conn.close()
        self._slots_refresh()

