"""StaffTabMixin — auto-split from bakery_shop.py."""
from education_system.systems.university.domain.operations.commerce.bakery_shop._common import *  # noqa: F401,F403


class StaffTabMixin:
    SKILL_OPTIONS = ["bread", "pastry", "decorating", "barista", "front"]

    DEFAULT_OPEN_CHECKLIST = [
        "Sanitize counters", "Turn on ovens & proofer",
        "Check fridge/freezer temps", "Brew batch coffee",
        "Stock display cases", "Count opening till float",
    ]

    DEFAULT_CLOSE_CHECKLIST = [
        "Mark down day-old items", "Wipe & sanitize all surfaces",
        "Empty waste bins", "Log final temps", "Lock back door",
        "Count till & deposit",
    ]

    def build_staff_tab(self):
        panels = [
            ("🚶 Walk-in Queue",       self._build_queue_panel),
            ("👤 Customer Profiles",   self._build_profiles_panel),
            ("🎂 Birthday Club",       self._build_birthday_panel),
            ("📱 QR Menus",            self._build_qr_panel),
            ("🎫 Gift Cards",          self._build_giftcard_panel),
            ("📅 Shift Schedule",      self._build_shift_panel),
            ("⏱ Clock & Breaks",      self._build_clock_panel),
            ("📋 Open/Close Checklists", self._build_checklist_panel),
            ("🎨 Decorator Board",     self._build_decorator_panel),
            ("🎓 Training Mode",       self._build_training_panel),
        ]
        sub, self._staff_panels = self._lazy_subnotebook(
            self.staff_tab, panels, "Staff")
        self.staff_sub = sub

    def _build_queue_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="+ Add to queue", command=self._queue_add,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="🔔 Call next", command=self._queue_call_next,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="✅ Mark served",
                  command=lambda: self._queue_set("served"),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="🚪 Abandoned",
                  command=lambda: self._queue_set("abandoned"),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._queue_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        cols = ("pager", "name", "party", "joined", "called", "served",
                "wait", "status")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c, h, w in [("pager", "Pager", 70), ("name", "Customer", 160),
                        ("party", "Party", 60), ("joined", "Joined", 150),
                        ("called", "Called", 150), ("served", "Served", 150),
                        ("wait", "Wait", 80), ("status", "Status", 90)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._queue_tree = tv
        self._queue_refresh()

    def _queue_refresh(self):
        tv = self._queue_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, pager_number, customer_name, party_size, "
                "joined_at, called_at, served_at, status FROM bakery_walkin_queue "
                "WHERE date(joined_at) >= date('now', '-1 day') "
                "ORDER BY (status='waiting') DESC, id ASC").fetchall()
        finally:
            conn.close()
        now = datetime.now()
        for rid, pg, nm, pt, ja, ca, sa, st in rows:
            try:
                joined = datetime.strptime(ja, "%Y-%m-%d %H:%M:%S")
                ref = (datetime.strptime(sa, "%Y-%m-%d %H:%M:%S") if sa
                       else (datetime.strptime(ca, "%Y-%m-%d %H:%M:%S") if ca else now))
                mins = max(0, int((ref - joined).total_seconds() // 60))
                wait = f"{mins}m"
            except Exception:
                wait = "—"
            tag = {"waiting": "wait", "called": "called",
                   "served": "ok"}.get(st, "")
            tv.insert("", "end", iid=str(rid),
                      values=(pg, nm or "", pt, ja, ca or "—", sa or "—",
                              wait, st), tags=(tag,))
        tv.tag_configure("wait", background="#FFF2CC")
        tv.tag_configure("called", background="#E6F0FF")
        tv.tag_configure("ok", background="#E6F4EA")

    def _queue_add(self):
        nm = simpledialog.askstring("Queue", "Customer name (optional):",
                                    parent=self.root)
        pt = simpledialog.askinteger("Queue", "Party size:",
                                     initialvalue=1, minvalue=1,
                                     parent=self.root) or 1
        conn = self._connect()
        try:
            next_pg = (conn.execute(
                "SELECT COALESCE(MAX(pager_number), 0) + 1 "
                "FROM bakery_walkin_queue WHERE date(joined_at)=date('now')"
            ).fetchone()[0]) or 1
            conn.execute(
                "INSERT INTO bakery_walkin_queue "
                "(pager_number, customer_name, party_size, joined_at, status) "
                "VALUES (?,?,?,?,'waiting')",
                (next_pg, nm or "", pt,
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
        finally:
            conn.close()
        self._queue_refresh()
        messagebox.showinfo("Queue", f"Pager #{next_pg} assigned.",
                            parent=self.root)

    def _queue_call_next(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            r = conn.execute(
                "SELECT id, pager_number FROM bakery_walkin_queue "
                "WHERE status='waiting' ORDER BY id ASC LIMIT 1").fetchone()
            if not r:
                messagebox.showinfo("Queue", "Queue is empty.",
                                    parent=self.root); return
            conn.execute(
                "UPDATE bakery_walkin_queue SET status='called', "
                "called_at=? WHERE id=?", (now, r[0]))
            conn.commit()
            try: self.root.bell()
            except Exception: pass
            self.set_status(f"📟 Pager #{r[1]} called.")
        finally:
            conn.close()
        self._queue_refresh()

    def _queue_set(self, status):
        sel = self._queue_tree.focus()
        if not sel:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            col = "served_at" if status == "served" else "served_at"
            conn.execute(
                f"UPDATE bakery_walkin_queue SET status=?, {col}=? "
                "WHERE id=?", (status, now, int(sel)))
            conn.commit()
        finally:
            conn.close()
        self._queue_refresh()

    def _build_profiles_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="+ Add / edit profile", command=self._profile_edit,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._profiles_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        cols = ("user", "name", "dietary", "favourites", "birthday", "notes")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c, h, w in [("user", "User", 110), ("name", "Display name", 140),
                        ("dietary", "Dietary flags", 160),
                        ("favourites", "Favourites", 240),
                        ("birthday", "Birthday", 100),
                        ("notes", "Notes", 200)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._profiles_tree = tv
        self._profiles_refresh()

    def _profiles_refresh(self):
        tv = self._profiles_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT user, display_name, dietary_flags, favourites_json, "
                "birthday, notes FROM bakery_customer_profiles "
                "ORDER BY user").fetchall()
        finally:
            conn.close()
        for u, dn, df, fav, bd, nt in rows:
            try:
                fav_list = json.loads(fav) if fav else []
                fav_s = ", ".join(fav_list)
            except Exception:
                fav_s = fav or ""
            tv.insert("", "end", iid=u, values=(u, dn or "", df or "",
                                                  fav_s, bd or "", nt or ""))

    def _profile_edit(self):
        sel = self._profiles_tree.focus()
        existing = None
        if sel:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT user, display_name, dietary_flags, favourites_json, "
                    "birthday, notes FROM bakery_customer_profiles "
                    "WHERE user=?", (sel,)).fetchone()
                if row:
                    existing = dict(zip(
                        ["user", "display_name", "dietary_flags",
                         "favourites_json", "birthday", "notes"], row))
            finally:
                conn.close()
        d = tk.Toplevel(self.root); d.title("Customer profile")
        d.transient(self.root); d.grab_set()
        e = existing or {}
        fields = [("user", e.get("user") or self.current_user or ""),
                  ("display_name", e.get("display_name") or ""),
                  ("dietary_flags", e.get("dietary_flags") or ""),
                  ("favourites (CSV item names)",
                   ", ".join(json.loads(e["favourites_json"])
                             if e.get("favourites_json") else [])),
                  ("birthday (YYYY-MM-DD)", e.get("birthday") or ""),
                  ("notes", e.get("notes") or "")]
        vars_ = []
        for i, (lbl, val) in enumerate(fields):
            tk.Label(d, text=lbl + ":").grid(row=i, column=0, padx=8,
                                              pady=4, sticky="e")
            v = tk.StringVar(value=val); vars_.append(v)
            tk.Entry(d, textvariable=v, width=34).grid(row=i, column=1,
                                                        padx=8, pady=4, sticky="w")
        def save():
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            favs = [s.strip() for s in vars_[3].get().split(",") if s.strip()]
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_customer_profiles "
                    "(user, display_name, dietary_flags, favourites_json, "
                    "birthday, notes, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(user) DO UPDATE SET "
                    "display_name=excluded.display_name, "
                    "dietary_flags=excluded.dietary_flags, "
                    "favourites_json=excluded.favourites_json, "
                    "birthday=excluded.birthday, "
                    "notes=excluded.notes, "
                    "updated_at=excluded.updated_at",
                    (vars_[0].get(), vars_[1].get(), vars_[2].get(),
                     json.dumps(favs), vars_[4].get(), vars_[5].get(),
                     now, now))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._profiles_refresh()
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).grid(row=len(fields), column=0, columnspan=2, pady=10)

    def _build_birthday_panel(self, parent):
        bg = self.colors["background"]
        tk.Label(parent,
                 text="Customers with a birthday on file get an auto-discount "
                      "this month.",
                 bg=bg, font=("Arial", 11, "italic")).pack(anchor="w",
                                                            padx=14, pady=6)
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=4)
        tk.Button(top, text="🎁 Issue birthday voucher (selected)",
                  command=self._birthday_voucher,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._birthday_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        cols = ("user", "name", "birthday", "this_month", "claimed_this_year")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c, h, w in [("user", "User", 130),
                        ("name", "Name", 160),
                        ("birthday", "Birthday", 100),
                        ("this_month", "This month?", 110),
                        ("claimed_this_year", "Claimed this year", 150)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._birthday_tree = tv
        self._birthday_refresh()

    def _birthday_refresh(self):
        tv = self._birthday_tree
        tv.delete(*tv.get_children())
        this_month = datetime.now().strftime("%m")
        year = datetime.now().year
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT user, display_name, birthday FROM bakery_customer_profiles "
                "WHERE birthday IS NOT NULL AND birthday != ''").fetchall()
            claimed = {r[0] for r in conn.execute(
                "SELECT user FROM bakery_birthday_claims WHERE year=?",
                (year,)).fetchall()}
        finally:
            conn.close()
        for u, dn, bd in rows:
            mm = bd[5:7] if len(bd) >= 7 else ""
            in_month = (mm == this_month)
            tag = "month" if in_month and u not in claimed else ""
            tv.insert("", "end", iid=u,
                      values=(u, dn or "", bd,
                              "YES" if in_month else "no",
                              "yes" if u in claimed else "no"),
                      tags=(tag,))
        tv.tag_configure("month", background="#FFF2CC")

    def _birthday_voucher(self):
        sel = self._birthday_tree.focus()
        if not sel:
            return
        year = datetime.now().year
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO bakery_birthday_claims "
                "(user, year, claimed_at) VALUES (?,?,?)",
                (sel, year, now))
            # Issue a £5 gift card as the voucher.
            code = f"BDAY-{sel}-{year}"
            conn.execute(
                "INSERT OR IGNORE INTO bakery_gift_cards "
                "(code, initial_balance, balance, issued_to, active, "
                "notes, created_at, created_by) "
                "VALUES (?,?,?,?,1,?,?,?)",
                (code, 5.00, 5.00, sel, "Birthday voucher",
                 now, self.current_user or "system"))
            conn.commit()
        finally:
            conn.close()
        messagebox.showinfo("Voucher", f"Issued voucher {code} (£5).",
                            parent=self.root)
        self._birthday_refresh()

    def _build_qr_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="+ Generate menu QR", command=self._qr_generate,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="🖨 Mark printed", command=self._qr_printed,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._qr_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        cols = ("id", "location", "payload", "created", "last_printed")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=16)
        for c, h, w in [("id", "ID", 50), ("location", "Location", 150),
                        ("payload", "Payload", 360),
                        ("created", "Created", 150),
                        ("last_printed", "Last printed", 150)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._qr_tree = tv
        self._qr_refresh()

    def _qr_refresh(self):
        tv = self._qr_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, location, payload, created_at, last_printed "
                "FROM bakery_qr_menus ORDER BY id DESC").fetchall()
        finally:
            conn.close()
        for rid, loc, p, ct, lp in rows:
            tv.insert("", "end", iid=str(rid),
                      values=(rid, loc, p, ct, lp or "—"))

    def _qr_generate(self):
        loc = simpledialog.askstring("QR menu", "Location (eg 'Table 5'):",
                                     parent=self.root)
        if not loc:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload = f"bakery://menu?loc={loc.replace(' ', '_')}&v={int(datetime.now().timestamp())}"
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO bakery_qr_menus (location, payload, created_at) "
                "VALUES (?,?,?)", (loc, payload, now))
            conn.commit()
        finally:
            conn.close()
        self._qr_refresh()
        messagebox.showinfo("QR", f"Payload: {payload}", parent=self.root)

    def _qr_printed(self):
        sel = self._qr_tree.focus()
        if not sel:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute("UPDATE bakery_qr_menus SET last_printed=? "
                         "WHERE id=?", (now, int(sel)))
            conn.commit()
        finally:
            conn.close()
        self._qr_refresh()

    def _build_giftcard_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="+ Issue card", command=self._gc_issue,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="💷 Top-up", command=self._gc_topup,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="🔍 Check balance", command=self._gc_check,
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="✖ Deactivate", command=self._gc_deactivate,
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._gc_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        cols = ("code", "balance", "initial", "to", "active", "expiry", "notes")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c, h, w in [("code", "Code", 160), ("balance", "Balance", 100),
                        ("initial", "Initial", 100), ("to", "Issued to", 130),
                        ("active", "Active", 70), ("expiry", "Expiry", 110),
                        ("notes", "Notes", 220)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=10, pady=6)
        self._gc_tree = tv
        self._gc_refresh()

    def _gc_refresh(self):
        tv = self._gc_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT code, balance, initial_balance, issued_to, active, "
                "expiry, notes FROM bakery_gift_cards ORDER BY created_at DESC"
            ).fetchall()
        finally:
            conn.close()
        for code, bal, init, to, active, exp, nt in rows:
            tv.insert("", "end", iid=code,
                      values=(code, f"£{(bal or 0):.2f}",
                              f"£{(init or 0):.2f}", to or "",
                              "yes" if active else "no",
                              exp or "—", nt or ""))

    def _gc_issue(self):
        code = simpledialog.askstring("Gift card",
                                      "Code (leave blank to auto-generate):",
                                      parent=self.root)
        if not code:
            code = f"GC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        bal = simpledialog.askfloat("Gift card", "Initial balance £:",
                                    initialvalue=25.00, minvalue=0.01,
                                    parent=self.root)
        if not bal:
            return
        to = simpledialog.askstring("Gift card", "Issued to (optional):",
                                    parent=self.root) or ""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO bakery_gift_cards "
                "(code, initial_balance, balance, issued_to, active, "
                "created_at, created_by) VALUES (?,?,?,?,1,?,?)",
                (code, bal, bal, to, now, self.current_user or "system"))
            conn.execute(
                "INSERT INTO bakery_gift_card_txns "
                "(code, txn_type, amount, user, timestamp) "
                "VALUES (?, 'issue', ?, ?, ?)",
                (code, bal, self.current_user or "system", now))
            conn.commit()
        finally:
            conn.close()
        self._gc_refresh()
        messagebox.showinfo("Gift card", f"Issued {code} (£{bal:.2f}).",
                            parent=self.root)

    def _gc_topup(self):
        sel = self._gc_tree.focus()
        if not sel:
            return
        amt = simpledialog.askfloat("Top-up", f"Add £ to {sel}:",
                                    minvalue=0.01, parent=self.root)
        if not amt:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE bakery_gift_cards SET balance = balance + ? "
                "WHERE code=?", (amt, sel))
            conn.execute(
                "INSERT INTO bakery_gift_card_txns "
                "(code, txn_type, amount, user, timestamp) "
                "VALUES (?, 'topup', ?, ?, ?)",
                (sel, amt, self.current_user or "system", now))
            conn.commit()
        finally:
            conn.close()
        self._gc_refresh()

    def _gc_check(self):
        code = simpledialog.askstring("Check", "Card code:", parent=self.root)
        if not code:
            return
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT balance, active FROM bakery_gift_cards WHERE code=?",
                (code,)).fetchone()
        finally:
            conn.close()
        if not row:
            messagebox.showerror("Gift card", "Code not found.",
                                 parent=self.root); return
        messagebox.showinfo(
            "Gift card",
            f"Balance: £{(row[0] or 0):.2f}\n"
            f"Status: {'active' if row[1] else 'INACTIVE'}",
            parent=self.root)

    def _gc_deactivate(self):
        sel = self._gc_tree.focus()
        if not sel:
            return
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE bakery_gift_cards SET active=0 WHERE code=?", (sel,))
            conn.commit()
        finally:
            conn.close()
        self._gc_refresh()

    def _build_shift_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="+ Schedule shift", command=self._shift_add,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="🛠 Assign skill", command=self._skill_add,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="✖ Delete shift", command=self._shift_del,
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._shift_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)

        tk.Label(parent, text="Upcoming shifts", bg=bg,
                 font=("Arial", 11, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
        cols = ("id", "date", "start", "end", "staff", "role", "skill", "notes")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=10)
        for c, h, w in [("id", "ID", 50), ("date", "Date", 100),
                        ("start", "Start", 70), ("end", "End", 70),
                        ("staff", "Staff", 120), ("role", "Role", 110),
                        ("skill", "Skill req", 110), ("notes", "Notes", 200)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="x", padx=10, pady=6)
        self._shift_tree = tv

        tk.Label(parent, text="Skill matrix", bg=bg,
                 font=("Arial", 11, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
        cols2 = ("staff", "skill", "level")
        tv2 = ttk.Treeview(parent, columns=cols2, show="headings", height=10)
        for c, h, w in [("staff", "Staff", 160), ("skill", "Skill", 150),
                        ("level", "Level", 80)]:
            tv2.heading(c, text=h); tv2.column(c, width=w, anchor="w")
        tv2.pack(fill="both", expand=True, padx=10, pady=6)
        self._skills_tree = tv2
        self._shift_refresh()

    def _shift_refresh(self):
        tv = self._shift_tree
        tv.delete(*tv.get_children())
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, shift_date, start_time, end_time, staff, role, "
                "skill_required, notes FROM bakery_shift_schedule "
                "WHERE shift_date >= date('now', '-1 day') "
                "ORDER BY shift_date ASC, start_time ASC").fetchall()
            skills = conn.execute(
                "SELECT staff, skill, level FROM bakery_staff_skills "
                "ORDER BY staff, skill").fetchall()
        finally:
            conn.close()
        for rid, d, s, e, stf, rl, sk, nt in rows:
            tv.insert("", "end", iid=str(rid),
                      values=(rid, d, s, e, stf, rl or "",
                              sk or "", nt or ""))
        tv2 = self._skills_tree
        tv2.delete(*tv2.get_children())
        for stf, sk, lv in skills:
            tv2.insert("", "end", values=(stf, sk, "★" * lv + "☆" * (5 - lv)))

    def _shift_add(self):
        d = tk.Toplevel(self.root); d.title("Schedule shift")
        d.transient(self.root); d.grab_set()
        fields = [("Staff username", ""),
                  ("Role", "baker"),
                  ("Skill required", "bread"),
                  ("Date (YYYY-MM-DD)",
                   (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")),
                  ("Start (HH:MM)", "05:00"),
                  ("End (HH:MM)", "13:00"),
                  ("Notes", "")]
        vars_ = []
        for i, (lbl, val) in enumerate(fields):
            tk.Label(d, text=lbl + ":").grid(row=i, column=0,
                                              padx=8, pady=4, sticky="e")
            v = tk.StringVar(value=val); vars_.append(v)
            if lbl == "Skill required":
                ttk.Combobox(d, textvariable=v, values=self.SKILL_OPTIONS,
                             state="readonly", width=20).grid(
                                 row=i, column=1, padx=8, pady=4, sticky="w")
            else:
                tk.Entry(d, textvariable=v, width=24).grid(
                    row=i, column=1, padx=8, pady=4, sticky="w")
        def save():
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_shift_schedule "
                    "(staff, role, skill_required, shift_date, start_time, "
                    "end_time, notes, created_at, created_by) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (vars_[0].get(), vars_[1].get(), vars_[2].get(),
                     vars_[3].get(), vars_[4].get(), vars_[5].get(),
                     vars_[6].get(), now, self.current_user or "system"))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._shift_refresh()
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).grid(row=len(fields), column=0, columnspan=2, pady=10)

    def _shift_del(self):
        sel = self._shift_tree.focus()
        if not sel:
            return
        if not messagebox.askyesno("Shift", "Delete shift?", parent=self.root):
            return
        conn = self._connect()
        try:
            conn.execute("DELETE FROM bakery_shift_schedule WHERE id=?",
                         (int(sel),))
            conn.commit()
        finally:
            conn.close()
        self._shift_refresh()

    def _skill_add(self):
        d = tk.Toplevel(self.root); d.title("Assign skill")
        d.transient(self.root); d.grab_set()
        u_var = tk.StringVar(); sk_var = tk.StringVar(value="bread")
        lv_var = tk.StringVar(value="3")
        tk.Label(d, text="Staff:").grid(row=0, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=u_var, width=22).grid(row=0, column=1, padx=8, pady=4, sticky="w")
        tk.Label(d, text="Skill:").grid(row=1, column=0, padx=8, pady=4, sticky="e")
        ttk.Combobox(d, textvariable=sk_var, values=self.SKILL_OPTIONS,
                     state="readonly", width=16).grid(row=1, column=1, padx=8, pady=4, sticky="w")
        tk.Label(d, text="Level (1-5):").grid(row=2, column=0, padx=8, pady=4, sticky="e")
        tk.Entry(d, textvariable=lv_var, width=4).grid(row=2, column=1, padx=8, pady=4, sticky="w")
        def save():
            try:
                lv = max(1, min(5, int(lv_var.get())))
            except ValueError:
                messagebox.showerror("Skill", "Level 1-5.", parent=d); return
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_staff_skills (staff, skill, level) "
                    "VALUES (?,?,?) ON CONFLICT(staff, skill) "
                    "DO UPDATE SET level=excluded.level",
                    (u_var.get(), sk_var.get(), lv))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._shift_refresh()
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).grid(row=3, column=0, columnspan=2, pady=10)

    def _build_clock_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="🕐 Clock in", command=self._clock_in,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="🕘 Clock out", command=self._clock_out,
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="☕ Start break", command=self._break_start,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="🍽 End break", command=self._break_end,
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._clock_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)

        tk.Label(parent, text="Open shifts", bg=bg,
                 font=("Arial", 11, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
        cols = ("id", "staff", "role", "clock_in", "elapsed")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=6)
        for c, h, w in [("id", "ID", 50), ("staff", "Staff", 150),
                        ("role", "Role", 110), ("clock_in", "In", 150),
                        ("elapsed", "Elapsed", 100)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="x", padx=10, pady=4)
        self._clock_tree = tv

        tk.Label(parent, text="Recent breaks", bg=bg,
                 font=("Arial", 11, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
        cols2 = ("id", "staff", "started", "ended", "kind", "minutes")
        tv2 = ttk.Treeview(parent, columns=cols2, show="headings", height=12)
        for c, h, w in [("id", "ID", 50), ("staff", "Staff", 150),
                        ("started", "Start", 150), ("ended", "End", 150),
                        ("kind", "Kind", 90), ("minutes", "Mins", 70)]:
            tv2.heading(c, text=h); tv2.column(c, width=w, anchor="w")
        tv2.pack(fill="both", expand=True, padx=10, pady=4)
        self._breaks_tree = tv2
        self._clock_refresh()

    def _clock_refresh(self):
        conn = self._connect()
        try:
            shifts = conn.execute(
                "SELECT id, staff, role, clock_in FROM bakery_staff_shifts "
                "WHERE status='open' ORDER BY id DESC").fetchall()
            breaks = conn.execute(
                "SELECT id, staff, started_at, ended_at, kind "
                "FROM bakery_breaks ORDER BY id DESC LIMIT 50").fetchall()
        finally:
            conn.close()
        now = datetime.now()
        tv = self._clock_tree; tv.delete(*tv.get_children())
        for rid, stf, rl, ci in shifts:
            try:
                dt = datetime.strptime(ci, "%Y-%m-%d %H:%M:%S")
                mins = int((now - dt).total_seconds() // 60)
                el = f"{mins // 60}h {mins % 60}m"
            except Exception:
                el = "—"
            tv.insert("", "end", iid=str(rid),
                      values=(rid, stf, rl or "", ci, el))
        tv2 = self._breaks_tree; tv2.delete(*tv2.get_children())
        for rid, stf, s, e, k in breaks:
            mins = ""
            if s and e:
                try:
                    mins = str(int((datetime.strptime(e, "%Y-%m-%d %H:%M:%S")
                                    - datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
                                    ).total_seconds() // 60))
                except Exception:
                    pass
            tv2.insert("", "end", iid=str(rid),
                       values=(rid, stf, s, e or "—", k, mins))

    def _clock_in(self):
        u = simpledialog.askstring("Clock in", "Staff:",
                                   initialvalue=self.current_user or "",
                                   parent=self.root)
        if not u:
            return
        rl = simpledialog.askstring("Clock in", "Role:",
                                    initialvalue="baker",
                                    parent=self.root) or "baker"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO bakery_staff_shifts (staff, role, clock_in, "
                "status) VALUES (?,?,?,'open')", (u, rl, now))
            conn.commit()
        finally:
            conn.close()
        self._clock_refresh()

    def _clock_out(self):
        sel = self._clock_tree.focus()
        if not sel:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE bakery_staff_shifts SET clock_out=?, status='closed' "
                "WHERE id=?", (now, int(sel)))
            conn.commit()
        finally:
            conn.close()
        self._clock_refresh()

    def _break_start(self):
        sel = self._clock_tree.focus()
        if not sel:
            messagebox.showinfo("Break", "Select a shift first.",
                                parent=self.root); return
        stf = self._clock_tree.item(sel, "values")[1]
        kind = simpledialog.askstring("Break", "Kind (break/meal):",
                                      initialvalue="break",
                                      parent=self.root) or "break"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO bakery_breaks (shift_id, staff, started_at, kind) "
                "VALUES (?,?,?,?)", (int(sel), stf, now, kind))
            conn.commit()
        finally:
            conn.close()
        self._clock_refresh()

    def _break_end(self):
        sel = self._breaks_tree.focus()
        if not sel:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE bakery_breaks SET ended_at=? WHERE id=? "
                "AND ended_at IS NULL", (now, int(sel)))
            conn.commit()
        finally:
            conn.close()
        self._clock_refresh()

    def _build_checklist_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="+ New checklist", command=self._checklist_new,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="🌅 Seed defaults",
                  command=self._checklist_seed_defaults,
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="▶ Run selected", command=self._checklist_run,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._checklist_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)
        cols = ("id", "name", "kind", "items", "active")
        tv = ttk.Treeview(parent, columns=cols, show="headings", height=8)
        for c, h, w in [("id", "ID", 50), ("name", "Name", 180),
                        ("kind", "Kind", 100), ("items", "Items", 360),
                        ("active", "Active", 70)]:
            tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
        tv.pack(fill="x", padx=10, pady=4)
        self._checklist_tree = tv

        tk.Label(parent, text="Recent runs", bg=bg,
                 font=("Arial", 11, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
        cols2 = ("id", "checklist_id", "date", "started", "completed", "by")
        tv2 = ttk.Treeview(parent, columns=cols2, show="headings", height=10)
        for c, h, w in [("id", "ID", 50), ("checklist_id", "CL", 50),
                        ("date", "Date", 100), ("started", "Start", 150),
                        ("completed", "Done", 150), ("by", "By", 120)]:
            tv2.heading(c, text=h); tv2.column(c, width=w, anchor="w")
        tv2.pack(fill="both", expand=True, padx=10, pady=4)
        self._checklist_runs_tree = tv2
        self._checklist_refresh()

    def _checklist_refresh(self):
        conn = self._connect()
        try:
            cls = conn.execute(
                "SELECT id, name, kind, items_json, active "
                "FROM bakery_checklists ORDER BY id").fetchall()
            runs = conn.execute(
                "SELECT id, checklist_id, run_date, started_at, completed_at, "
                "completed_by FROM bakery_checklist_runs "
                "ORDER BY id DESC LIMIT 50").fetchall()
        finally:
            conn.close()
        tv = self._checklist_tree; tv.delete(*tv.get_children())
        for rid, n, k, items, a in cls:
            try:
                ds = ", ".join(json.loads(items))
            except Exception:
                ds = items or ""
            tv.insert("", "end", iid=str(rid),
                      values=(rid, n, k, ds, "yes" if a else "no"))
        tv2 = self._checklist_runs_tree; tv2.delete(*tv2.get_children())
        for rid, cid, d, s, c, by in runs:
            tv2.insert("", "end", values=(rid, cid, d, s or "",
                                          c or "—", by or ""))

    def _checklist_seed_defaults(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            existing = {r[0] for r in conn.execute(
                "SELECT name FROM bakery_checklists").fetchall()}
            for name, kind, items in [
                ("Opening checklist", "opening", self.DEFAULT_OPEN_CHECKLIST),
                ("Closing checklist", "closing", self.DEFAULT_CLOSE_CHECKLIST),
            ]:
                if name in existing:
                    continue
                conn.execute(
                    "INSERT INTO bakery_checklists "
                    "(name, kind, items_json, active, created_at) "
                    "VALUES (?,?,?,1,?)",
                    (name, kind, json.dumps(items), now))
            conn.commit()
        finally:
            conn.close()
        self._checklist_refresh()

    def _checklist_new(self):
        name = simpledialog.askstring("Checklist", "Name:", parent=self.root)
        if not name:
            return
        kind = simpledialog.askstring("Checklist", "Kind (opening/closing/handover):",
                                      initialvalue="opening",
                                      parent=self.root) or "opening"
        items = simpledialog.askstring("Checklist",
                                       "Items, separated by | :",
                                       parent=self.root) or ""
        item_list = [s.strip() for s in items.split("|") if s.strip()]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO bakery_checklists "
                "(name, kind, items_json, active, created_at) "
                "VALUES (?,?,?,1,?)",
                (name, kind, json.dumps(item_list), now))
            conn.commit()
        finally:
            conn.close()
        self._checklist_refresh()

    def _checklist_run(self):
        sel = self._checklist_tree.focus()
        if not sel:
            return
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT name, items_json FROM bakery_checklists WHERE id=?",
                (int(sel),)).fetchone()
        finally:
            conn.close()
        if not row:
            return
        items = json.loads(row[1])
        d = tk.Toplevel(self.root); d.title(f"Run: {row[0]}")
        d.geometry("440x500"); d.transient(self.root); d.grab_set()
        bg = self.colors["background"]; d.configure(bg=bg)
        tk.Label(d, text=row[0], font=("Georgia", 14, "bold"),
                 bg=bg).pack(pady=8)
        vars_ = []
        for it in items:
            v = tk.IntVar(value=0)
            tk.Checkbutton(d, text=it, variable=v, bg=bg, anchor="w",
                           font=("Arial", 11)).pack(fill="x", padx=14, pady=2)
            vars_.append((it, v))
        def complete():
            now = datetime.now()
            now_s = now.strftime("%Y-%m-%d %H:%M:%S")
            today = now.strftime("%Y-%m-%d")
            results = {it: bool(v.get()) for it, v in vars_}
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_checklist_runs "
                    "(checklist_id, run_date, started_at, completed_at, "
                    "completed_by, results_json) VALUES (?,?,?,?,?,?)",
                    (int(sel), today, now_s, now_s,
                     self.current_user or "system", json.dumps(results)))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._checklist_refresh()
        tk.Button(d, text="✅ Complete", command=complete,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=14, pady=8).pack(pady=10)

    def _build_decorator_panel(self, parent):
        bg = self.colors["background"]
        top = tk.Frame(parent, bg=bg); top.pack(fill="x", padx=10, pady=8)
        tk.Button(top, text="+ New task", command=self._decorator_new,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="▶ Start", command=lambda: self._decorator_set("in-progress"),
                  bg=self.colors["accent"], relief="flat",
                  padx=10).pack(side="left", padx=4)
        tk.Button(top, text="✅ Done", command=lambda: self._decorator_set("done"),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="⛔ Blocked", command=lambda: self._decorator_set("blocked"),
                  relief="flat", padx=10).pack(side="left", padx=4)
        tk.Button(top, text="↻ Refresh", command=self._decorator_refresh,
                  relief="flat", padx=10).pack(side="left", padx=4)

        # Three-column board: queued / in-progress / done
        board = tk.Frame(parent, bg=bg); board.pack(fill="both",
                                                     expand=True, padx=10,
                                                     pady=6)
        self._decorator_lanes = {}
        for col, lane in enumerate(["queued", "in-progress", "done"]):
            lf = tk.LabelFrame(board, text=lane.upper(), bg=bg,
                               font=("Arial", 11, "bold"),
                               labelanchor="n", padx=4, pady=4)
            lf.grid(row=0, column=col, sticky="nsew", padx=4)
            board.grid_columnconfigure(col, weight=1)
            tv = ttk.Treeview(lf, columns=("id", "desc", "decorator", "due",
                                            "prio"),
                              show="headings", height=18)
            for c, h, w in [("id", "ID", 40), ("desc", "Task", 200),
                            ("decorator", "Who", 100), ("due", "Due", 100),
                            ("prio", "P", 30)]:
                tv.heading(c, text=h); tv.column(c, width=w, anchor="w")
            tv.pack(fill="both", expand=True)
            self._decorator_lanes[lane] = tv
        board.grid_rowconfigure(0, weight=1)
        self._decorator_refresh()

    def _decorator_refresh(self):
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, description, decorator, due_date, status, priority "
                "FROM bakery_decorator_tasks "
                "ORDER BY priority ASC, due_date ASC NULLS LAST, id DESC"
            ).fetchall()
        finally:
            conn.close()
        for tv in self._decorator_lanes.values():
            tv.delete(*tv.get_children())
        for rid, desc, dec, due, st, prio in rows:
            lane = st if st in self._decorator_lanes else "queued"
            self._decorator_lanes[lane].insert(
                "", "end", iid=str(rid),
                values=(rid, desc, dec or "", due or "", prio))

    def _decorator_new(self):
        d = tk.Toplevel(self.root); d.title("Decorator task")
        d.transient(self.root); d.grab_set()
        fields = [("Description", ""), ("Decorator", ""),
                  ("Due (YYYY-MM-DD)",
                   (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")),
                  ("Priority (1-5, 1=urgent)", "3"),
                  ("Custom order ID (optional)", "")]
        vars_ = []
        for i, (lbl, val) in enumerate(fields):
            tk.Label(d, text=lbl + ":").grid(row=i, column=0, padx=8, pady=4, sticky="e")
            v = tk.StringVar(value=val); vars_.append(v)
            tk.Entry(d, textvariable=v, width=30).grid(row=i, column=1, padx=8, pady=4, sticky="w")
        def save():
            try:
                prio = int(vars_[3].get())
                co = int(vars_[4].get()) if vars_[4].get().strip() else None
            except ValueError:
                messagebox.showerror("Task", "Bad numeric field.", parent=d); return
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO bakery_decorator_tasks "
                    "(custom_order_id, description, decorator, due_date, "
                    "priority, status, created_at) "
                    "VALUES (?,?,?,?,?, 'queued', ?)",
                    (co, vars_[0].get(), vars_[1].get(), vars_[2].get(),
                     prio, now))
                conn.commit()
            finally:
                conn.close()
            d.destroy(); self._decorator_refresh()
        tk.Button(d, text="Save", command=save, bg=self.colors["primary"],
                  fg="white", relief="flat",
                  padx=14).grid(row=len(fields), column=0, columnspan=2, pady=10)

    def _decorator_set(self, status):
        sel = None
        for tv in self._decorator_lanes.values():
            if tv.focus():
                sel = tv.focus(); break
        if not sel:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            sets = ["status=?"]
            params = [status]
            if status == "in-progress":
                sets.append("started_at=COALESCE(started_at, ?)"); params.append(now)
            elif status == "done":
                sets.append("finished_at=?"); params.append(now)
            params.append(int(sel))
            conn.execute(
                f"UPDATE bakery_decorator_tasks SET {', '.join(sets)} WHERE id=?",
                params)
            conn.commit()
        finally:
            conn.close()
        self._decorator_refresh()

    def _build_training_panel(self, parent):
        bg = self.colors["background"]
        tk.Label(parent, text="🎓 Training Mode",
                 bg=bg, font=("Georgia", 16, "bold")).pack(pady=10)
        info = tk.Label(parent,
            text="In training mode, all transactions are tagged with a "
                 "TRAIN- prefix and excluded from real reports.\n"
                 "Use this for onboarding new cashiers without touching live data.",
            bg=bg, font=("Arial", 11), justify="left")
        info.pack(padx=14, pady=6)
        self._training_lbl = tk.Label(parent, text="",
                                       font=("Arial", 14, "bold"), bg=bg)
        self._training_lbl.pack(pady=10)
        tk.Button(parent, text="Toggle training mode",
                  command=self._training_toggle,
                  bg=self.colors["primary"], fg="white", relief="flat",
                  font=("Arial", 12, "bold"),
                  padx=14, pady=10).pack(pady=6)
        tk.Label(parent,
                 text="A quiz-style menu for cashiers practising tile POS / "
                      "split-tender / refunds will appear here when active.",
                 bg=bg, font=("Arial", 10, "italic")).pack(pady=10)
        self._quiz_frame = tk.Frame(parent, bg=bg)
        self._quiz_frame.pack(fill="x", padx=14, pady=10)
        self._training_refresh()

    def _training_active(self):
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT value FROM bakery_app_flags WHERE flag='training_mode'"
            ).fetchone()
        finally:
            conn.close()
        return row and row[0] == "1"

    def _training_refresh(self):
        on = self._training_active()
        self._training_lbl.config(
            text=f"Status: {'🟢 TRAINING ACTIVE' if on else '⚪ off'}",
            fg=("#1B7F3A" if on else self.colors["text"]))
        for w in self._quiz_frame.winfo_children():
            w.destroy()
        if not on:
            return
        for ex in ["Practise: ring up 2× Croissant + 1× Coffee",
                   "Practise: split £12.50 across cash + card",
                   "Practise: void an order with manager PIN",
                   "Practise: redeem a loyalty stamp card"]:
            tk.Label(self._quiz_frame, text="• " + ex,
                     bg=self.colors["background"],
                     font=("Arial", 11)).pack(anchor="w")

    def _training_toggle(self):
        on = self._training_active()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO bakery_app_flags (flag, value, updated_at, updated_by) "
                "VALUES ('training_mode', ?, ?, ?) "
                "ON CONFLICT(flag) DO UPDATE SET "
                "value=excluded.value, updated_at=excluded.updated_at, "
                "updated_by=excluded.updated_by",
                ("0" if on else "1", now, self.current_user or "system"))
            conn.commit()
        finally:
            conn.close()
        self._training_refresh()

