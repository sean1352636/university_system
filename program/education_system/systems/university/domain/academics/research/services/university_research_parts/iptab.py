"""Extracted class implementation."""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class IPTab(TableModule):
    title = "IP & Commercialisation"
    subtitle = "Disclosures, filings, licences and tech-transfer revenue."
    table_name = "ip_assets"

    IP_TYPES = ["Patent", "Copyright", "Trademark", "Know-how",
                "Software", "Design"]
    IP_STATUSES = ["Disclosed", "Evaluating", "Filed", "Granted",
                   "Licensed", "Abandoned"]
    ROUTES = ["None yet", "License", "Spin-out", "Assignment", "Open release"]

    def get_columns(self):
        cols = ("reference", "title", "type", "inventor", "status", "route",
                "revenue")
        heads = ("Reference", "Title", "Type", "Inventor", "Status",
                 "Route", "Revenue (£)")
        widths = (95, 280, 95, 160, 110, 110, 100)
        return cols, heads, widths

    def fetch_rows(self, search):
        q = f"%{search.lower()}%" if search else None
        if q:
            return self.db.query("""SELECT i.*, p.name AS inv_name
                FROM research_ip_assets i
                LEFT JOIN research_people p ON p.id=i.inventor_id
                WHERE LOWER(i.reference) LIKE ? OR LOWER(i.title) LIKE ?
                   OR LOWER(COALESCE(p.name,'')) LIKE ?
                   OR LOWER(COALESCE(i.status,'')) LIKE ?
                ORDER BY i.disclosure_date DESC""", (q, q, q, q))
        return self.db.query("""SELECT i.*, p.name AS inv_name
            FROM research_ip_assets i
            LEFT JOIN research_people p ON p.id=i.inventor_id
            ORDER BY i.disclosure_date DESC""")

    def row_to_tree_values(self, row):
        return (row["reference"], row["title"], row["ip_type"],
                row["inv_name"] or "—", row["status"],
                row["commercial_route"] or "—",
                f"{(row['revenue_to_date'] or 0):,.0f}")

    def get_field_specs(self, record=None):
        return [
            FieldSpec("reference", "Reference", required=True,
                      hint="e.g. IP-2026-003"),
            FieldSpec("title", "Title / short description", required=True),
            FieldSpec("ip_type", "IP type", kind="combo",
                      choices=self.IP_TYPES, required=True),
            FieldSpec("inventor_id", "Lead inventor", kind="people",
                      choices=self.people_choices(role="staff")),
            FieldSpec("disclosure_date", "Disclosure date", kind="date"),
            FieldSpec("filing_date", "Filing date", kind="date"),
            FieldSpec("grant_date", "Grant date", kind="date"),
            FieldSpec("jurisdiction", "Jurisdiction(s)",
                      hint="e.g. UK/US/EU"),
            FieldSpec("status", "Status", kind="combo",
                      choices=self.IP_STATUSES, required=True),
            FieldSpec("commercial_route", "Commercial route",
                      kind="combo", choices=self.ROUTES),
            FieldSpec("licensee", "Licensee / partner"),
            FieldSpec("revenue_to_date", "Revenue to date (£)",
                      kind="float"),
            FieldSpec("notes", "Notes", kind="multiline"),
        ]

    def render_detail(self, row):
        inv_name = "—"
        if row.get("inventor_id"):
            r = self.db.query("SELECT name FROM research_people WHERE id=?",
                              (row["inventor_id"],))
            if r:
                inv_name = r[0]["name"]
        self.detail_text.insert("end", f"{row['reference']}\n", ("section",))
        self.detail_text.insert("end", f"{row['title']}\n\n", ("value",))
        rev = row.get("revenue_to_date") or 0
        self._write_detail([
            ("IP type", row.get("ip_type")),
            ("Status", row.get("status")),
            ("Lead inventor", inv_name),
            ("Disclosure date", fmt_date(row.get("disclosure_date"))),
            ("Filing date", fmt_date(row.get("filing_date"))),
            ("Grant date", fmt_date(row.get("grant_date"))),
            ("Jurisdiction", row.get("jurisdiction")),
            ("Commercial route", row.get("commercial_route")),
            ("Licensee", row.get("licensee")),
            ("Revenue to date", f"£{rev:,.2f}"),
            ("Notes", row.get("notes")),
        ])

    def insert_sql(self, d):
        self.db.execute("""INSERT INTO research_ip_assets
            (reference,title,ip_type,inventor_id,disclosure_date,filing_date,
             grant_date,jurisdiction,status,commercial_route,licensee,
             revenue_to_date,notes)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d.get("reference"), d.get("title"), d.get("ip_type"),
             d.get("inventor_id"), d.get("disclosure_date"),
             d.get("filing_date"), d.get("grant_date"),
             d.get("jurisdiction"), d.get("status"),
             d.get("commercial_route"), d.get("licensee"),
             d.get("revenue_to_date") or 0, d.get("notes")))

    def update_sql(self, d, pk):
        self.db.execute("""UPDATE research_ip_assets SET
            reference=?,title=?,ip_type=?,inventor_id=?,disclosure_date=?,
            filing_date=?,grant_date=?,jurisdiction=?,status=?,
            commercial_route=?,licensee=?,revenue_to_date=?,notes=?
            WHERE id=?""",
            (d.get("reference"), d.get("title"), d.get("ip_type"),
             d.get("inventor_id"), d.get("disclosure_date"),
             d.get("filing_date"), d.get("grant_date"),
             d.get("jurisdiction"), d.get("status"),
             d.get("commercial_route"), d.get("licensee"),
             d.get("revenue_to_date") or 0, d.get("notes"), pk))
