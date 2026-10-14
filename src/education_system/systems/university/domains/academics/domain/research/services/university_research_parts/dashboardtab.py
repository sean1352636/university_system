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

        this_year = str(date.today().year)
        people_total = len(fetch_people(self.db))
        outputs_total = self.db.query(
            "SELECT COUNT(*) c FROM research_publications")[0]["c"]
        outputs_this_year = self.db.query(
            "SELECT COUNT(*) c FROM research_publications "
            "WHERE substr(COALESCE(publication_date,''),1,4)=?",
            (this_year,))[0]["c"]
        projects = self.db.query(
            "SELECT COUNT(*) c, COALESCE(SUM(total_budget),0) s "
            "FROM research_projects")[0]
        licensed = self.db.query(
            "SELECT COUNT(*) c FROM ip_licenses "
            "WHERE COALESCE(licensee_name,'') != ''")[0]["c"]

        stats = [
            ("Active ethics apps",
             self.db.query("SELECT COUNT(*) c FROM ethics_reviews "
                           "WHERE decision IN ('Submitted','Under Review','pending',"
                           "'Revisions Required')")[0]["c"],
             "awaiting a decision",
             PALETTE["accent"]),
            ("Approved (current)",
             self.db.query("SELECT COUNT(*) c FROM ethics_reviews "
                           "WHERE decision='Approved'")[0]["c"],
             "",
             PALETTE["success"]),
            ("Outputs (REF-tagged)",
             self.db.query("SELECT COUNT(*) c FROM research_publications "
                           "WHERE ref_submitted=1")[0]["c"],
             f"{outputs_total} total · {outputs_this_year} in {this_year}",
             PALETTE["accent"]),
            ("IP assets",
             self.db.query("SELECT COUNT(*) c FROM ip_disclosures")[0]["c"],
             f"{licensed} licensed",
             # Not PALETTE["header"] — flattened to the page colour in
             # 8.117.65, which drew this card's strip invisibly.
             PALETTE["muted"]),
            ("Active theses",
             self.db.query("SELECT COUNT(*) c FROM student_supervisions "
                           "WHERE status IN ('Active','Submitted',"
                           "'Under Examination','Viva Scheduled',"
                           "'Minor Corrections','Major Corrections')")[0]["c"],
             f"{people_total} people on the register",
             PALETTE["warn"]),
            ("IP revenue (total)",
             money(self.db.query(
                 "SELECT COALESCE(SUM(rv.total_revenue),0) s "
                 "FROM ip_revenue_shares rv")[0]["s"]),
             "to date",
             PALETTE["success"]),
            # Funding lives on the grants side's research_projects; the
            # portal reported none of it before.
            ("Funded research",
             money(projects["s"]),
             f"across {projects['c']} project{'' if projects['c'] == 1 else 's'}",
             PALETTE["accent"]),
        ]

        for i, (lbl, val, note, colour) in enumerate(stats):
            card = StatCard(self.cards_frame, lbl, val, note=note, colour=colour)
            card.grid(row=0, column=i, sticky="nsew",
                      padx=(0 if i == 0 else 10, 0))
            self.cards_frame.columnconfigure(i, weight=1, uniform="kpi")

        # Upcoming & overdue milestones
        self.left_list.delete(0, "end")
        today = date.today().isoformat()
        rows = self.db.query("""
            SELECT m.milestone_name AS name, m.target_date AS due_date,
                   m.status, COALESCE(v.student_name,'—') AS student,
                   v.thesis_title AS title
            FROM research_milestones m
            JOIN student_supervisions v ON v.supervision_id = m.thesis_id
            WHERE m.status='Pending' OR (m.status='Pending' AND m.target_date < ?)
            ORDER BY COALESCE(m.target_date,'9999-12-31')
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
            "SELECT reference,title,decision AS status FROM ethics_reviews "
            "WHERE decision IN ('Revisions Required','Expired')")
        for r in rows:
            attention.append(("Ethics", f"{r['reference']}: {r['status']}",
                              r["title"], PALETTE["danger"]))

        rows = self.db.query(
            "SELECT reference,title,decision AS status FROM ethics_reviews "
            "WHERE decision='Approved' AND approval_expiry_date IS NOT NULL "
            "AND approval_expiry_date < date('now','+90 days')")
        for r in rows:
            attention.append(("Ethics",
                              f"{r['reference']}: approval expiring",
                              r["title"], PALETTE["warn"]))

        rows = self.db.query(
            "SELECT thesis_title AS title, COALESCE(student_name,'—') AS name "
            "FROM student_supervisions "
            "WHERE status IN ('Minor Corrections','Major Corrections')")
        for r in rows:
            attention.append(("Thesis", "Corrections outstanding",
                              f"{r['name']} — {r['title']}", PALETTE["warn"]))

        rows = self.db.query(
            "SELECT COALESCE(reference,'—') AS reference, title "
            "FROM ip_disclosures WHERE status IN ('Disclosed','draft')")
        for r in rows:
            attention.append(("IP", f"{r['reference']}: awaiting evaluation",
                              r["title"], PALETTE["accent"]))

        if not attention:
            self.right_list.insert("end", "  Nothing requires immediate attention.")
        for kind, head, body, colour in attention:
            self.right_list.insert("end", f"  [{kind}] {head}")
            self.right_list.itemconfig("end", foreground=colour)
            self.right_list.insert("end", f"         {body}")
