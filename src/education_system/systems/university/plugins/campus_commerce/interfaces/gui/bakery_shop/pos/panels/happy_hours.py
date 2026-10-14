
from education_system.systems.university.infrastructure.i18n import get_text as _t
from ..context import *  # noqa: F401,F403


class HappyHoursPanelMixin:
    def _build_happy_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.happy_hours.buttons.add_rule', default="+ Add rule"), command=self._happy_add,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.happy_hours.buttons.disable_selected', default="✖ Disable selected"),
                  command=lambda: self._happy_toggle(0),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.happy_hours.buttons.enable_selected', default="✓ Enable selected"),
                  command=lambda: self._happy_toggle(1),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text=_t('gui.operations.commerce.bakery_shop.pos.panels.happy_hours.buttons.refresh', default="↻ Refresh"), command=self._happy_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)

        cols = ("id", "name", "start", "end", "days", "category", "pct", "active")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=16)
        for c, h, w in [("id", "ID", 60), ("name", "Name", 160),
                        ("start", "Start", 80), ("end", "End", 80),
                        ("days", "Days", 130), ("category", "Category", 110),
                        ("pct", "%", 60), ("active", "Active", 70)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._happy_tree = tv
        self._happy_refresh()

    def _happy_refresh(self):
        tv = self._happy_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, name, start_time, end_time, days_of_week, "
                "category, discount_pct, active FROM bakery_happy_hours "
                "ORDER BY id DESC").fetchall()
        finally:
            conn.close()
        for rid, n, s, e, d, c, p, a in rows:
            tv.insert("", "end", iid=str(rid),
                      values=(rid, n, s, e, d or "all", c or "all",
                              f"{p:g}%", "yes" if a else "no"))

    def _happy_add(self):
        cats = ["all"] + list(self.products.keys())
        d = tk.Toplevel(self.root); d.title(_t('gui.operations.commerce.bakery_shop.pos.panels.happy_hours.windows.happy_hour', default="Happy hour"))
        d.transient(self.root); d.grab_set()
        fields = [("Name", "Afternoon Pastry"),
                  ("Start (HH:MM)", "14:00"),
                  ("End (HH:MM)", "16:00"),
                  ("Days (all or Mon,Tue,...)", "all"),
                  ("Category", "all"),
                  ("Discount %", "20")]
        vars_ = []
        for i, (lbl, val) in enumerate(fields):
            tk.Label(d, text=lbl + ":").grid(row=i, column=0, padx=8,
                                             pady=4, sticky="e")
            v = tk.StringVar(value=val); vars_.append(v)
            if lbl == "Category":
                ttk.Combobox(d, textvariable=v, values=cats, state="readonly",
                             width=18).grid(row=i, column=1, padx=8, pady=4,
                                            sticky="w")
            else:
                tk.Entry(d, textvariable=v, width=22).grid(row=i, column=1,
                                                            padx=8, pady=4, sticky="w")
        def save():
            try:
                pct = float(vars_[5].get())
            except ValueError:
                messagebox.showerror(_t('gui.operations.commerce.bakery_shop.pos.panels.happy_hours.dialogs.happy_hour', default="Happy hour"), _t('gui.operations.commerce.bakery_shop.pos.panels.happy_hours.dialogs.bad', default="Bad %."), parent=d); return
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_happy_hours "
                    "(name, start_time, end_time, days_of_week, category, "
                    "discount_pct, active, created_at) "
                    "VALUES (?,?,?,?,?,?,1,?)",
                    (vars_[0].get(), vars_[1].get(), vars_[2].get(),
                     vars_[3].get(), vars_[4].get(), pct, now))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._happy_refresh()
        tk.Button(d, text=_t('gui.operations.commerce.bakery_shop.pos.panels.happy_hours.buttons.save', default="Save"), command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).grid(row=len(fields), column=0, columnspan=2, pady=10)

    def _happy_toggle(self, active):
        sel = self._happy_tree.focus()
        if not sel:
            return
        conn = self._connect()
        try:
            conn.execute("UPDATE bakery_happy_hours SET active=? WHERE id=?",
                         (active, int(sel)))
            conn.commit()
        finally:
            conn.close()
        self._happy_refresh()

