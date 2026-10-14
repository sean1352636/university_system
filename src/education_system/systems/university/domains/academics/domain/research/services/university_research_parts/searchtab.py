"""One query across every research record type.

Ported from the standalone Research Portal's SearchPage. That version
searched researchers / projects / publications; this one searches what the
portal actually owns — people, ethics applications, outputs, IP assets and
theses — plus the grants side's projects, which is the only place funding
lives.
"""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class SearchTab(ModuleTab):
    """Cross-record search. Double-click a hit to open its tab."""

    SCOPES = ("Everything", "People", "Ethics", "Outputs", "IP", "Theses", "Projects")

    #: scope label -> attribute name on UniversityApp holding that tab
    _TAB_FOR_KIND = {
        "Person": "people",
        "Ethics": "ethics",
        "Output": "outputs",
        "IP": "ip",
        "Thesis": "thesis",
    }

    def _build(self):
        wrapper = ttk.Frame(self, style="TFrame")
        wrapper.pack(fill="both", expand=True, padx=24, pady=20)

        ttk.Label(wrapper, text="Search the portal",
                  font=("Segoe UI", 18, "bold"),
                  foreground=PALETTE["header"]).pack(anchor="w")
        ttk.Label(wrapper,
                  text="One query across people, ethics, outputs, IP, theses and projects.",
                  foreground=PALETTE["muted"]).pack(anchor="w")

        bar = ttk.Frame(wrapper, style="TFrame")
        bar.pack(fill="x", pady=(14, 8))
        self.query_var = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.query_var, width=48,
                          font=("Segoe UI", 11))
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda _e: self.run_search())
        ttk.Button(bar, text="Search", style="Accent.TButton",
                   command=self.run_search).pack(side="left", padx=(10, 0))
        ttk.Button(bar, text="Clear",
                   command=self._clear).pack(side="left", padx=(6, 0))

        filters = ttk.Frame(wrapper, style="TFrame")
        filters.pack(fill="x", pady=(0, 8))
        self.scope = tk.StringVar(value="Everything")
        for label in self.SCOPES:
            ttk.Radiobutton(filters, text=label, variable=self.scope,
                            value=label,
                            command=self.run_search).pack(side="left",
                                                          padx=(0, 12))

        self.status = ttk.Label(wrapper, text="Type a query and press Enter.",
                                foreground=PALETTE["muted"])
        self.status.pack(fill="x", pady=(0, 8))

        table_frame = ttk.Frame(wrapper, style="Panel.TFrame")
        table_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table_frame, columns=("kind", "title", "detail"),
                                 show="headings", selectmode="browse")
        for key, heading, width, stretch in (
                ("kind", "Record", 110, False),
                ("title", "Name / title", 360, True),
                ("detail", "Details", 460, True)):
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=width, stretch=stretch, anchor="w")
        scroll = ttk.Scrollbar(table_frame, orient="vertical",
                               command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        scroll.pack(side="right", fill="y")
        self.tree.tag_configure("alt", background="#fafbfd")
        self.tree.bind("<Double-1>", lambda _e: self._open_selected())

    def refresh(self):
        # Re-run whatever query is in the box; a blank box just resets.
        self.run_search()

    def _clear(self):
        self.query_var.set("")
        self.run_search()

    # -- the query ---------------------------------------------------------

    def run_search(self):
        needle = self.query_var.get().strip()
        self.tree.delete(*self.tree.get_children())
        if not needle:
            self.status.configure(text="Type a query and press Enter.")
            return

        like = f"%{needle}%"
        scope = self.scope.get()
        results = []

        def wanted(name):
            return scope in ("Everything", name)

        if wanted("People"):
            # People are a union of three registers, filtered in Python —
            # there is no single table to LIKE against.
            low = needle.lower()
            for key, name, role, dept, email in fetch_people(self.db):
                haystack = " ".join((name or "", role or "", dept or "",
                                     email or "")).lower()
                if low in haystack:
                    results.append((
                        "Person", key, name,
                        f"{role or '—'} · {dept or '—'} · {email or '—'}"))

        if wanted("Ethics"):
            for r in self.db.query(
                    "SELECT review_id AS id, reference, title, "
                    "       decision AS status, department, risk_level "
                    "  FROM ethics_reviews "
                    " WHERE reference LIKE ? OR title LIKE ? OR decision LIKE ? "
                    "    OR department LIKE ? OR category LIKE ? ORDER BY reference",
                    (like,) * 5):
                results.append((
                    "Ethics", r["id"],
                    f"{r['reference'] or '—'} — {r['title'] or '(untitled)'}",
                    f"{r['status'] or '—'} · {r['department'] or '—'} · "
                    f"risk {r['risk_level'] or '—'}"))

        if wanted("Outputs"):
            for r in self.db.query(
                    "SELECT publication_id AS id, title, "
                    "       publication_type AS output_type, authors, "
                    "       COALESCE(NULLIF(venue,''), journal_name, "
                    "                conference_name, '') AS venue, "
                    "       publication_date, doi FROM research_publications "
                    " WHERE title LIKE ? OR authors LIKE ? OR venue LIKE ? "
                    "    OR doi LIKE ? OR publication_type LIKE ? ORDER BY title",
                    (like,) * 5):
                results.append((
                    "Output", r["id"], r["title"],
                    f"{r['output_type'] or '—'} · {r['authors'] or '—'} · "
                    f"{r['venue'] or '—'} ({fmt_date(r['publication_date'])})"))

        if wanted("IP"):
            for r in self.db.query(
                    "SELECT d.disclosure_id AS id, d.reference, d.title, "
                    "       d.ip_type, d.status, "
                    "       COALESCE(SUM(rv.total_revenue), 0) AS revenue_to_date "
                    "  FROM ip_disclosures d "
                    "  LEFT JOIN ip_licenses l ON l.disclosure_id = d.disclosure_id "
                    "  LEFT JOIN ip_revenue_shares rv ON rv.license_id = l.license_id "
                    " WHERE d.reference LIKE ? OR d.title LIKE ? OR d.ip_type LIKE ? "
                    "    OR d.status LIKE ? OR d.department LIKE ? "
                    "    OR l.licensee_name LIKE ? "
                    " GROUP BY d.disclosure_id ORDER BY d.reference",
                    (like,) * 6):
                results.append((
                    "IP", r["id"],
                    f"{r['reference'] or '—'} — {r['title']}",
                    f"{r['ip_type'] or '—'} · {r['status'] or '—'} · "
                    f"{money(r['revenue_to_date'])} to date"))

        if wanted("Theses"):
            for r in self.db.query(
                    "SELECT supervision_id AS id, thesis_title AS title, "
                    "       COALESCE(NULLIF(degree,''), program_type) AS degree, "
                    "       status, department, "
                    "       COALESCE(student_name,'—') AS student "
                    "  FROM student_supervisions "
                    " WHERE thesis_title LIKE ? OR degree LIKE ? OR status LIKE ? "
                    "    OR department LIKE ? OR student_name LIKE ? "
                    " ORDER BY thesis_title", (like,) * 5):
                results.append((
                    "Thesis", r["id"], r["title"] or "(untitled)",
                    f"{r['degree'] or '—'} · {r['student']} · {r['status'] or '—'}"))

        if wanted("Projects"):
            # Owned by the grants side, but it is where funding is recorded,
            # so a portal-wide search that skipped it would be misleading.
            for r in self.db.query(
                    "SELECT project_id, project_title, status, department, "
                    "total_budget, funding_source FROM research_projects "
                    "WHERE project_title LIKE ? OR status LIKE ? "
                    "OR department LIKE ? OR funding_source LIKE ? "
                    "ORDER BY project_title", (like,) * 4):
                results.append((
                    "Project", r["project_id"], r["project_title"],
                    f"{r['status'] or '—'} · {r['department'] or '—'} · "
                    f"{money(r['total_budget'])} from "
                    f"{r['funding_source'] or 'unspecified'}"))

        for i, (kind, rid, title, detail) in enumerate(results):
            self.tree.insert("", "end", iid=f"{kind}:{rid}",
                             values=(kind, title, detail),
                             tags=("alt",) if i % 2 else ())

        if results:
            self.status.configure(
                text=f"{len(results)} result"
                     f"{'' if len(results) == 1 else 's'} for “{needle}”. "
                     "Double-click a row to open its tab.")
        else:
            self.status.configure(
                text=f"Nothing matched “{needle}”. "
                     "Try a shorter or different term.")

    def _open_selected(self):
        selection = self.tree.selection()
        if not selection:
            return
        kind = selection[0].split(":", 1)[0]
        attr = self._TAB_FOR_KIND.get(kind)
        if not attr:
            # Projects live in the grants GUI, which this portal does not host.
            messagebox.showinfo(
                "Opened elsewhere",
                "Projects are managed in Research & Grants, not this portal.",
                parent=self)
            return
        tab = getattr(self.app, attr, None)
        if tab is None:
            return
        try:
            self.app.notebook.select(tab)
        except tk.TclError:
            logger.debug("could not select tab %s", attr, exc_info=True)


__all__ = ["SearchTab"]
