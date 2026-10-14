"""Extracted class implementation."""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class IPTab(TableModule):
    title = "IP & Commercialisation"
    subtitle = "Disclosures, filings, licences and tech-transfer revenue."
    # ip_disclosures is the university's master IP record. filing/grant
    # dates live on `patents`, and licensee/revenue on `ip_licenses` +
    # `ip_revenue_shares` — those three are read via LEFT JOIN and are not
    # editable here, because they belong to the licensing workflow rather
    # than to research administration.
    table_name = "ip_disclosures"
    pk = "disclosure_id"

    IP_TYPES = ["Patent", "Copyright", "Trademark", "Know-how",
                "Software", "Design"]
    IP_STATUSES = ["Disclosed", "Evaluating", "Filed", "Granted",
                   "Licensed", "Abandoned"]
    ROUTES = ["None yet", "License", "Spin-out", "Assignment", "Open release"]

    #: Right-aligned and sorted as a number, not as "£1,000" < "£9".
    numeric_columns = ("revenue",)

    def get_columns(self):
        cols = ("reference", "title", "type", "inventor", "status", "route",
                "revenue")
        heads = ("Reference", "Title", "Type", "Inventor", "Status",
                 "Route", "Revenue (£)")
        widths = (95, 280, 95, 160, 110, 110, 100)
        return cols, heads, widths

    _BASE = """
        SELECT d.*,
               d.submitted_date            AS disclosure_date,
               pt.filing_date              AS filing_date,
               pt.grant_date               AS grant_date,
               lic.licensee_name           AS licensee,
               COALESCE(rev.total, 0)      AS revenue_to_date,
               d.review_comments           AS notes
          FROM ip_disclosures d
          LEFT JOIN patents pt      ON pt.disclosure_id = d.disclosure_id
          LEFT JOIN ip_licenses lic ON lic.disclosure_id = d.disclosure_id
          LEFT JOIN (SELECT license_id, SUM(total_revenue) AS total
                       FROM ip_revenue_shares GROUP BY license_id) rev
                 ON rev.license_id = lic.license_id
    """

    def fetch_rows(self, search):
        q = f"%{search.lower()}%" if search else None
        if q:
            return self.db.query(
                self._BASE +
                " WHERE LOWER(COALESCE(d.reference,'')) LIKE ?"
                "    OR LOWER(d.title) LIKE ?"
                "    OR LOWER(COALESCE(d.department,'')) LIKE ?"
                "    OR LOWER(COALESCE(d.status,'')) LIKE ?"
                " ORDER BY d.submitted_date DESC", (q, q, q, q))
        return self.db.query(self._BASE + " ORDER BY d.submitted_date DESC")

    def row_to_tree_values(self, row):
        return (row["reference"] or "—", row["title"],
                row["ip_type"] or "—",
                self.person_name(row["inventor_id"]),
                row["status"] or "—",
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
            FieldSpec("department", "Department"),
            FieldSpec("jurisdiction", "Jurisdiction(s)",
                      hint="e.g. UK/US/EU"),
            FieldSpec("status", "Status", kind="combo",
                      choices=self.IP_STATUSES, required=True),
            FieldSpec("commercial_route", "Commercial route",
                      kind="combo", choices=self.ROUTES),
            FieldSpec("notes", "Notes", kind="multiline"),
        ]

    def render_detail(self, row):
        inv_name = self.person_name(row.get("inventor_id"))
        self.detail_text.insert(
            "end", f"{row.get('reference') or '(no reference)'}\n", ("section",))
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
            ("Department", row.get("department")),
            ("Development stage", row.get("development_stage")),
        ])

    def insert_sql(self, d):
        # created_by is NOT NULL on the shared table.
        actor = (getattr(self.app, "user", None) or {}).get("username") or "portal"
        self.db.execute("""INSERT INTO ip_disclosures
            (reference,title,ip_type,inventor_id,submitted_date,jurisdiction,
             status,commercial_route,review_comments,department,created_by)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (d.get("reference"), d.get("title"), d.get("ip_type"),
             d.get("inventor_id"), d.get("disclosure_date"),
             d.get("jurisdiction"), d.get("status"),
             d.get("commercial_route"), d.get("notes"),
             d.get("department"), actor))

    def update_sql(self, d, pk):
        self.db.execute("""UPDATE ip_disclosures SET
            reference=?,title=?,ip_type=?,inventor_id=?,submitted_date=?,
            jurisdiction=?,status=?,commercial_route=?,review_comments=?,
            department=?, updated_at=CURRENT_TIMESTAMP
            WHERE disclosure_id=?""",
            (d.get("reference"), d.get("title"), d.get("ip_type"),
             d.get("inventor_id"), d.get("disclosure_date"),
             d.get("jurisdiction"), d.get("status"),
             d.get("commercial_route"), d.get("notes"),
             d.get("department"), pk))
