"""Extracted class implementation."""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class EthicsTab(TableModule):
    title = "Research Ethics / IRB"
    subtitle = "Track applications, approvals and expiry across the institution."
    table_name = "ethics_applications"

    ETHICS_STATUSES = ["Draft", "Submitted", "Under Review",
                       "Revisions Required", "Approved", "Rejected",
                       "Expired"]
    RISK_LEVELS = ["Low", "Medium", "High"]
    CATEGORIES = ["Human participants", "Animal", "Data-only",
                  "Clinical", "Environmental", "Other"]

    def get_columns(self):
        cols = ("reference", "title", "pi", "category", "risk", "status",
                "decision")
        heads = ("Reference", "Title", "Principal Investigator",
                 "Category", "Risk", "Status", "Decision date")
        widths = (95, 280, 170, 130, 70, 140, 110)
        return cols, heads, widths

    def fetch_rows(self, search):
        q = f"%{search.lower()}%" if search else None
        if q:
            sql = """SELECT e.*, p.name AS pi_name FROM research_ethics_applications e
                     LEFT JOIN research_people p ON p.id=e.principal_investigator_id
                     WHERE LOWER(e.reference) LIKE ? OR LOWER(e.title) LIKE ?
                        OR LOWER(COALESCE(p.name,'')) LIKE ?
                        OR LOWER(COALESCE(e.status,'')) LIKE ?
                     ORDER BY e.submitted_date DESC NULLS LAST, e.id DESC"""
            return self.db.query(sql, (q, q, q, q))
        return self.db.query("""SELECT e.*, p.name AS pi_name
            FROM research_ethics_applications e
            LEFT JOIN research_people p ON p.id=e.principal_investigator_id
            ORDER BY e.submitted_date DESC, e.id DESC""")

    def row_to_tree_values(self, row):
        return (row["reference"], row["title"], row["pi_name"] or "—",
                row["category"] or "—", row["risk_level"] or "—",
                row["status"], fmt_date(row["decision_date"]))

    def get_field_specs(self, record=None):
        return [
            FieldSpec("reference", "Reference", required=True,
                      hint="e.g. ETH-2026-005"),
            FieldSpec("title", "Study title", required=True),
            FieldSpec("principal_investigator_id",
                      "Principal Investigator", kind="people",
                      choices=self.people_choices(role="staff")),
            FieldSpec("department", "Department"),
            FieldSpec("category", "Category", kind="combo",
                      choices=self.CATEGORIES),
            FieldSpec("risk_level", "Risk level", kind="combo",
                      choices=self.RISK_LEVELS),
            FieldSpec("submitted_date", "Submitted date", kind="date",
                      hint="YYYY-MM-DD"),
            FieldSpec("decision_date", "Decision date", kind="date",
                      hint="YYYY-MM-DD"),
            FieldSpec("status", "Status", kind="combo",
                      choices=self.ETHICS_STATUSES, required=True),
            FieldSpec("approval_expiry", "Approval expiry", kind="date",
                      hint="YYYY-MM-DD"),
            FieldSpec("notes", "Notes", kind="multiline"),
        ]

    def render_detail(self, row):
        pi_name = "—"
        if row.get("principal_investigator_id"):
            r = self.db.query("SELECT name FROM research_people WHERE id=?",
                              (row["principal_investigator_id"],))
            if r:
                pi_name = r[0]["name"]
        self.detail_text.insert("end", f"{row['reference']}\n", ("section",))
        self.detail_text.insert("end", f"{row['title']}\n\n", ("value",))
        self._write_detail([
            ("Status", row.get("status")),
            ("Principal Investigator", pi_name),
            ("Department", row.get("department")),
            ("Category", row.get("category")),
            ("Risk level", row.get("risk_level")),
            ("Submitted", fmt_date(row.get("submitted_date"))),
            ("Decision", fmt_date(row.get("decision_date"))),
            ("Approval expiry", fmt_date(row.get("approval_expiry"))),
            ("Notes", row.get("notes")),
        ])

    def insert_sql(self, d):
        self.db.execute("""INSERT INTO research_ethics_applications
            (reference,title,principal_investigator_id,department,risk_level,
             category,submitted_date,decision_date,status,approval_expiry,notes)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (d.get("reference"), d.get("title"),
             d.get("principal_investigator_id"), d.get("department"),
             d.get("risk_level"), d.get("category"),
             d.get("submitted_date"), d.get("decision_date"),
             d.get("status"), d.get("approval_expiry"), d.get("notes")))

    def update_sql(self, d, pk):
        self.db.execute("""UPDATE research_ethics_applications SET
            reference=?,title=?,principal_investigator_id=?,department=?,
            risk_level=?,category=?,submitted_date=?,decision_date=?,
            status=?,approval_expiry=?,notes=? WHERE id=?""",
            (d.get("reference"), d.get("title"),
             d.get("principal_investigator_id"), d.get("department"),
             d.get("risk_level"), d.get("category"),
             d.get("submitted_date"), d.get("decision_date"),
             d.get("status"), d.get("approval_expiry"),
             d.get("notes"), pk))
