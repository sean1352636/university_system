"""Extracted class implementation."""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class OutputsTab(TableModule):
    title = "Research Outputs (REF)"
    subtitle = "Publications repository and REF submission tracking."
    table_name = "research_outputs"

    TYPES = ["Journal article", "Conference paper", "Book", "Book chapter",
             "Dataset", "Software", "Report", "Other"]
    RATINGS = ["", "1*", "2*", "3*", "4*"]
    UOAS = [f"UoA {n}" for n in range(1, 35)]

    def get_columns(self):
        cols = ("title", "type", "lead", "venue", "date", "ref", "rating")
        heads = ("Title", "Type", "Lead author", "Venue",
                 "Published", "REF?", "Rating")
        widths = (330, 120, 150, 180, 100, 55, 70)
        return cols, heads, widths

    def fetch_rows(self, search):
        q = f"%{search.lower()}%" if search else None
        if q:
            return self.db.query("""SELECT o.*, p.name AS lead_name
                FROM research_outputs o
                LEFT JOIN research_people p ON p.id=o.lead_author_id
                WHERE LOWER(o.title) LIKE ? OR LOWER(COALESCE(o.authors,'')) LIKE ?
                   OR LOWER(COALESCE(o.venue,'')) LIKE ?
                   OR LOWER(COALESCE(p.name,'')) LIKE ?
                ORDER BY o.publication_date DESC""", (q, q, q, q))
        return self.db.query("""SELECT o.*, p.name AS lead_name
            FROM research_outputs o
            LEFT JOIN research_people p ON p.id=o.lead_author_id
            ORDER BY o.publication_date DESC""")

    def row_to_tree_values(self, row):
        return (row["title"], row["output_type"],
                row["lead_name"] or "—", row["venue"] or "—",
                fmt_date(row["publication_date"]),
                "Yes" if row["ref_submitted"] else "No",
                row["quality_rating"] or "—")

    def get_field_specs(self, record=None):
        return [
            FieldSpec("title", "Title", required=True),
            FieldSpec("output_type", "Type", kind="combo",
                      choices=self.TYPES, required=True),
            FieldSpec("authors", "Authors (comma separated)"),
            FieldSpec("lead_author_id", "Lead author", kind="people",
                      choices=self.people_choices(role="staff")),
            FieldSpec("venue", "Venue (journal/conf/publisher)"),
            FieldSpec("publication_date", "Publication date", kind="date",
                      hint="YYYY-MM-DD"),
            FieldSpec("doi", "DOI / identifier"),
            FieldSpec("uoa", "Unit of Assessment", kind="combo",
                      choices=self.UOAS),
            FieldSpec("ref_submitted", "Submitted to REF?", kind="bool"),
            FieldSpec("open_access", "Open access compliant?", kind="bool"),
            FieldSpec("quality_rating", "Internal quality rating",
                      kind="combo", choices=self.RATINGS),
            FieldSpec("abstract", "Abstract / summary", kind="multiline"),
        ]

    def render_detail(self, row):
        lead_name = "—"
        if row.get("lead_author_id"):
            r = self.db.query("SELECT name FROM research_people WHERE id=?",
                              (row["lead_author_id"],))
            if r:
                lead_name = r[0]["name"]
        self.detail_text.insert("end", f"{row['title']}\n", ("section",))
        self.detail_text.insert("end", f"{row['output_type']}\n\n",
                                ("muted",))
        self._write_detail([
            ("Authors", row.get("authors")),
            ("Lead author", lead_name),
            ("Venue", row.get("venue")),
            ("Published", fmt_date(row.get("publication_date"))),
            ("DOI", row.get("doi")),
            ("Unit of Assessment", row.get("uoa")),
            ("REF submitted", "Yes" if row.get("ref_submitted") else "No"),
            ("Open access", "Yes" if row.get("open_access") else "No"),
            ("Quality rating", row.get("quality_rating")),
            ("Abstract", row.get("abstract")),
        ])

    def insert_sql(self, d):
        self.db.execute("""INSERT INTO research_outputs
            (title,output_type,authors,lead_author_id,venue,publication_date,
             doi,uoa,ref_submitted,open_access,quality_rating,abstract)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d.get("title"), d.get("output_type"), d.get("authors"),
             d.get("lead_author_id"), d.get("venue"),
             d.get("publication_date"), d.get("doi"), d.get("uoa"),
             1 if d.get("ref_submitted") else 0,
             1 if d.get("open_access") else 0,
             d.get("quality_rating"), d.get("abstract")))

    def update_sql(self, d, pk):
        self.db.execute("""UPDATE research_outputs SET
            title=?,output_type=?,authors=?,lead_author_id=?,venue=?,
            publication_date=?,doi=?,uoa=?,ref_submitted=?,open_access=?,
            quality_rating=?,abstract=? WHERE id=?""",
            (d.get("title"), d.get("output_type"), d.get("authors"),
             d.get("lead_author_id"), d.get("venue"),
             d.get("publication_date"), d.get("doi"), d.get("uoa"),
             1 if d.get("ref_submitted") else 0,
             1 if d.get("open_access") else 0,
             d.get("quality_rating"), d.get("abstract"), pk))
