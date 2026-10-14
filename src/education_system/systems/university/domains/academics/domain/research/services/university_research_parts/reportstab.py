"""Output, IP and funding trends.

Ported from the standalone Research Portal's ReportsPage. The prototype
charted publications and project funding; the same shapes are drawn here
over the portal's real tables, with funding read from ``research_projects``
(``total_budget`` / ``funding_source``) rather than a second funding model.
"""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class ReportsTab(ModuleTab):
    """Six charts plus a per-department CSV summary."""

    def _build(self):
        self.outer = ttk.Frame(self, style="TFrame")
        self.outer.pack(fill="both", expand=True, padx=24, pady=20)

        top = ttk.Frame(self.outer, style="TFrame")
        top.pack(fill="x")
        ttk.Label(top, text="Reports",
                  font=("Segoe UI", 18, "bold"),
                  foreground=PALETTE["header"]).pack(side="left")
        ttk.Button(top, text="Refresh",
                   command=self.refresh).pack(side="right")
        ttk.Button(top, text="Export summary CSV",
                   command=self.export_summary).pack(side="right", padx=6)
        ttk.Label(self.outer,
                  text="Output, research-degree and funding trends across the university.",
                  foreground=PALETTE["muted"]).pack(anchor="w", pady=(0, 14))

        grid = ttk.Frame(self.outer, style="TFrame")
        grid.pack(fill="both", expand=True)
        for c in (0, 1, 2):
            grid.columnconfigure(c, weight=1, uniform="rep")
        for r in (0, 1):
            grid.rowconfigure(r, weight=1)

        self.charts = {}
        spec = [
            ("outputs_year", "Outputs per year", PALETTE["accent"], 0, 0),
            # Not PALETTE["header"] — it is #f0f0f0 since the 8.117.65 flatten,
            # which would draw the bars invisibly against the panel.
            ("outputs_type", "Output by type", PALETTE["muted"], 0, 1),
            ("people_dept", "People by department", PALETTE["success"], 0, 2),
            ("thesis_status", "Theses by status", PALETTE["warn"], 1, 0),
            ("funding_source", "Funding by source", PALETTE["accent"], 1, 1),
            ("ip_revenue", "IP revenue by asset", PALETTE["success"], 1, 2),
        ]
        for key, heading, colour, row, col in spec:
            card, chart = self._chart_card(grid, heading, colour)
            card.grid(row=row, column=col, sticky="nsew",
                      padx=(0 if col == 0 else 12, 0),
                      pady=(0 if row == 0 else 12, 0))
            self.charts[key] = chart

    def _chart_card(self, parent, heading, colour):
        card = ttk.Frame(parent, style="Panel.TFrame")
        inner = ttk.Frame(card, style="Panel.TFrame")
        inner.pack(fill="both", expand=True, padx=16, pady=14)
        ttk.Label(inner, text=heading,
                  style="SectionTitle.TLabel").pack(anchor="w")
        ttk.Separator(inner).pack(fill="x", pady=(6, 8))
        chart = BarChart(inner, height=170, accent=colour)
        chart.pack(fill="both", expand=True)
        return card, chart

    # -- data --------------------------------------------------------------

    def refresh(self):
        if "charts" not in self.__dict__:
            return

        year_rows = self.db.query(
            "SELECT substr(publication_date,1,4) AS yr, COUNT(*) c "
            "FROM research_publications WHERE publication_date IS NOT NULL "
            "AND publication_date != '' GROUP BY yr ORDER BY yr")
        self.charts["outputs_year"].set_data(
            [(r["yr"], r["c"]) for r in year_rows])

        type_rows = self.db.query(
            "SELECT COALESCE(NULLIF(publication_type,''),'Unspecified') t, COUNT(*) c "
            "FROM research_publications GROUP BY t ORDER BY c DESC LIMIT 8")
        self.charts["outputs_type"].set_data(
            [(r["t"], r["c"]) for r in type_rows])

        tally = {}
        for _k, _n, _role, dept, _e in fetch_people(self.db):
            key = dept or "Unassigned"
            tally[key] = tally.get(key, 0) + 1
        self.charts["people_dept"].set_data(
            sorted(tally.items(), key=lambda kv: -kv[1])[:8])

        thesis_rows = self.db.query(
            "SELECT COALESCE(NULLIF(status,''),'Unknown') s, COUNT(*) c "
            "FROM student_supervisions GROUP BY s ORDER BY c DESC LIMIT 8")
        self.charts["thesis_status"].set_data(
            [(r["s"], r["c"]) for r in thesis_rows])

        funding_rows = self.db.query(
            "SELECT COALESCE(NULLIF(funding_source,''),'Unspecified') f, "
            "COALESCE(SUM(total_budget),0) total FROM research_projects "
            "GROUP BY f ORDER BY total DESC LIMIT 8")
        self.charts["funding_source"].set_data(
            [(r["f"], r["total"]) for r in funding_rows], formatter=money)

        ip_rows = self.db.query(
            "SELECT COALESCE(d.reference, d.title) AS reference, "
            "       COALESCE(SUM(rv.total_revenue),0) rev "
            "  FROM ip_disclosures d "
            "  LEFT JOIN ip_licenses l ON l.disclosure_id = d.disclosure_id "
            "  LEFT JOIN ip_revenue_shares rv ON rv.license_id = l.license_id "
            " GROUP BY d.disclosure_id HAVING rev > 0 "
            " ORDER BY rev DESC LIMIT 8")
        self.charts["ip_revenue"].set_data(
            [(r["reference"], r["rev"]) for r in ip_rows], formatter=money)

    # -- export ------------------------------------------------------------

    def export_summary(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV file", "*.csv")],
            initialfile="research_summary.csv",
            parent=self)
        if not path:
            return

        # One row per department, pulled from each table separately: the
        # tables have no shared key, so a join would drop departments that
        # only appear on one side.
        departments = {}

        def bucket(name):
            return departments.setdefault(
                name or "Unassigned",
                {"people": 0, "ethics": 0, "outputs": 0, "theses": 0,
                 "projects": 0, "funding": 0.0})

        for _k, _n, _role, dept, _e in fetch_people(self.db):
            bucket(dept or "Unassigned")["people"] += 1
        for r in self.db.query(
                "SELECT COALESCE(NULLIF(department,''),'Unassigned') d, "
                "COUNT(*) c FROM ethics_reviews GROUP BY d"):
            bucket(r["d"])["ethics"] = r["c"]
        for r in self.db.query(
                "SELECT COALESCE(NULLIF(department,''),'Unassigned') d, "
                "COUNT(*) c FROM student_supervisions GROUP BY d"):
            bucket(r["d"])["theses"] = r["c"]
        for r in self.db.query(
                "SELECT COALESCE(NULLIF(department,''),'Unassigned') d, "
                "COUNT(*) c, COALESCE(SUM(total_budget),0) f "
                "FROM research_projects GROUP BY d"):
            b = bucket(r["d"])
            b["projects"] = r["c"]
            b["funding"] = float(r["f"] or 0)

        # Outputs carry no department, so they are reported as one total
        # rather than silently attributed to a department they do not have.
        outputs_total = self.db.query(
            "SELECT COUNT(*) c FROM research_publications")[0]["c"]

        import csv
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["Department", "People", "Ethics applications",
                                 "Theses", "Projects", "Total budget (GBP)"])
                for name in sorted(departments,
                                   key=lambda n: -departments[n]["funding"]):
                    b = departments[name]
                    writer.writerow([name, b["people"], b["ethics"],
                                     b["theses"], b["projects"],
                                     f"{b['funding']:.2f}"])
                writer.writerow([])
                writer.writerow(["Outputs (all departments)", outputs_total])
        except OSError as e:
            messagebox.showerror("Export failed", str(e), parent=self)
            return
        messagebox.showinfo(
            "Export complete",
            f"Summary written to {os.path.basename(path)}.", parent=self)


__all__ = ["ReportsTab"]
