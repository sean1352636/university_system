"""Extracted class implementation."""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class DashboardTab(ModuleTab):

    def _build(self):
        container = ttk.Frame(self, style="TFrame")
        container.pack(fill="both", expand=True, padx=24, pady=20)

        ttk.Label(container, text="Research Management Overview",
                  font=("Segoe UI", 18, "bold"),
                  foreground=PALETTE["header"]).pack(anchor="w")
        ttk.Label(container,
                  text="A consolidated view across ethics, outputs, IP and research degrees.",
                  foreground=PALETTE["muted"]).pack(anchor="w", pady=(0, 18))

        # KPI cards
        self.cards_frame = ttk.Frame(container, style="TFrame")
        self.cards_frame.pack(fill="x")

        # Two-column lower region
        lower = ttk.Frame(container, style="TFrame")
        lower.pack(fill="both", expand=True, pady=(18, 0))
        lower.columnconfigure(0, weight=1, uniform="col")
        lower.columnconfigure(1, weight=1, uniform="col")
        lower.rowconfigure(0, weight=1)

        self.left_panel = self._panel(lower, "Upcoming & overdue milestones")
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.left_list = self._listbox(self.left_panel)

        self.right_panel = self._panel(lower, "Attention needed")
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        self.right_list = self._listbox(self.right_panel)

    def _panel(self, parent, title):
        p = ttk.Frame(parent, style="Panel.TFrame")
        inner = ttk.Frame(p, style="Panel.TFrame")
        inner.pack(fill="both", expand=True, padx=18, pady=16)
        ttk.Label(inner, text=title, style="SectionTitle.TLabel").pack(anchor="w")
        ttk.Separator(inner).pack(fill="x", pady=(6, 10))
        p.inner = inner
        return p

    def _listbox(self, panel):
        frame = ttk.Frame(panel.inner, style="Panel.TFrame")
        frame.pack(fill="both", expand=True)
        lb = tk.Listbox(frame, font=("Segoe UI", 10),
                        bg="white", fg=PALETTE["text"],
                        selectbackground=PALETTE["accent_soft"],
                        selectforeground=PALETTE["header"],
                        relief="solid", borderwidth=1, highlightthickness=0,
                        activestyle="none")
        lb.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(frame, command=lb.yview)
        sb.pack(side="right", fill="y")
        lb.config(yscrollcommand=sb.set)
        return lb

    def refresh(self):
        # clear cards
        for w in self.cards_frame.winfo_children():
            w.destroy()

        stats = [
            ("Active ethics apps",
             self.db.query("SELECT COUNT(*) c FROM research_ethics_applications "
                           "WHERE status IN ('Submitted','Under Review',"
                           "'Revisions Required')")[0]["c"],
             PALETTE["accent"]),
            ("Approved (current)",
             self.db.query("SELECT COUNT(*) c FROM research_ethics_applications "
                           "WHERE status='Approved'")[0]["c"],
             PALETTE["success"]),
            ("Outputs (REF-tagged)",
             self.db.query("SELECT COUNT(*) c FROM research_outputs "
                           "WHERE ref_submitted=1")[0]["c"],
             PALETTE["accent"]),
            ("IP assets",
             self.db.query("SELECT COUNT(*) c FROM research_ip_assets")[0]["c"],
             PALETTE["header"]),
            ("Active theses",
             self.db.query("SELECT COUNT(*) c FROM research_theses "
                           "WHERE status IN ('Active','Submitted',"
                           "'Under Examination','Viva Scheduled',"
                           "'Minor Corrections','Major Corrections')")[0]["c"],
             PALETTE["warn"]),
            ("IP revenue (total)",
             f"£{self.db.query('SELECT COALESCE(SUM(revenue_to_date),0) s FROM research_ip_assets')[0]['s']:,.0f}",
             PALETTE["success"]),
        ]

        for i, (lbl, val, colour) in enumerate(stats):
            card = tk.Frame(self.cards_frame, bg=PALETTE["panel"],
                            highlightbackground=PALETTE["border"],
                            highlightthickness=1)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))
            self.cards_frame.columnconfigure(i, weight=1, uniform="kpi")

            strip = tk.Frame(card, bg=colour, height=4)
            strip.pack(fill="x")

            inner = tk.Frame(card, bg=PALETTE["panel"])
            inner.pack(fill="both", expand=True, padx=16, pady=14)
            tk.Label(inner, text=str(val), bg=PALETTE["panel"],
                     fg=PALETTE["header"],
                     font=("Segoe UI", 20, "bold")).pack(anchor="w")
            tk.Label(inner, text=lbl, bg=PALETTE["panel"],
                     fg=PALETTE["muted"],
                     font=("Segoe UI", 9)).pack(anchor="w")

        # Upcoming & overdue milestones
        self.left_list.delete(0, "end")
        today = date.today().isoformat()
        rows = self.db.query("""
            SELECT m.name, m.due_date, m.status, p.name AS student, t.title
            FROM research_thesis_milestones m
            JOIN research_theses t ON t.id = m.thesis_id
            JOIN research_people p ON p.id = t.student_id
            WHERE m.status='Pending' OR (m.status='Pending' AND m.due_date < ?)
            ORDER BY COALESCE(m.due_date,'9999-12-31')
            LIMIT 12
        """, (today,))
        if not rows:
            self.left_list.insert("end", "  No pending milestones.")
        for r in rows:
            overdue = r["due_date"] and r["due_date"] < today
            tag = "  [OVERDUE] " if overdue else "  "
            self.left_list.insert(
                "end",
                f"{tag}{fmt_date(r['due_date'])} — {r['name']}  ·  {r['student']}")
            if overdue:
                self.left_list.itemconfig("end",
                                          foreground=PALETTE["danger"])

        # Attention needed
        self.right_list.delete(0, "end")
        attention = []
        rows = self.db.query(
            "SELECT reference,title,status FROM research_ethics_applications "
            "WHERE status IN ('Revisions Required','Expired')")
        for r in rows:
            attention.append(("Ethics", f"{r['reference']}: {r['status']}",
                              r["title"], PALETTE["danger"]))

        rows = self.db.query(
            "SELECT reference,title,status FROM research_ethics_applications "
            "WHERE status='Approved' AND approval_expiry IS NOT NULL "
            "AND approval_expiry < date('now','+90 days')")
        for r in rows:
            attention.append(("Ethics",
                              f"{r['reference']}: approval expiring",
                              r["title"], PALETTE["warn"]))

        rows = self.db.query(
            "SELECT t.title, p.name FROM research_theses t JOIN research_people p ON p.id=t.student_id "
            "WHERE t.status='Minor Corrections' OR t.status='Major Corrections'")
        for r in rows:
            attention.append(("Thesis", "Corrections outstanding",
                              f"{r['name']} — {r['title']}", PALETTE["warn"]))

        rows = self.db.query(
            "SELECT reference,title FROM research_ip_assets WHERE status='Disclosed'")
        for r in rows:
            attention.append(("IP", f"{r['reference']}: awaiting evaluation",
                              r["title"], PALETTE["accent"]))

        if not attention:
            self.right_list.insert("end", "  Nothing requires immediate attention.")
        for kind, head, body, colour in attention:
            self.right_list.insert("end", f"  [{kind}] {head}")
            self.right_list.itemconfig("end", foreground=colour)
            self.right_list.insert("end", f"         {body}")
