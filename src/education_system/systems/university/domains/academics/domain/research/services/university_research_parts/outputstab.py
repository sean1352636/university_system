"""Extracted class implementation."""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class OutputsTab(TableModule):
    """Research outputs, stored in the university's ``research_publications``.

    That table already held title/authors/type/venue/doi/abstract; the REF
    fields it lacked (``uoa``, ``ref_submitted``, ``open_access``,
    ``quality_rating``, ``lead_author_id``, ``venue``) were added by
    migration b4e19d7a3c62 rather than duplicated into a portal-owned table.
    """

    title = "Research Outputs (REF)"
    subtitle = "Publications repository and REF submission tracking."
    table_name = "research_publications"
    pk = "publication_id"

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

    # ``venue`` is the portal's single field; the table also carries the
    # older journal_name/conference_name pair, so fall back to those for
    # rows created outside the portal.
    _BASE = (
        "SELECT p.*, COALESCE(NULLIF(p.venue,''), p.journal_name, "
        "p.conference_name, '') AS venue_display "
        "FROM research_publications p"
    )

    def fetch_rows(self, search):
        q = f"%{search.lower()}%" if search else None
        base = self._BASE
        if q:
            return self.db.query(
                base +
                " WHERE LOWER(p.title) LIKE ? OR LOWER(COALESCE(p.authors,'')) LIKE ?"
                "    OR LOWER(COALESCE(p.venue,'')) LIKE ?"
                "    OR LOWER(COALESCE(p.journal_name,'')) LIKE ?"
                "    OR LOWER(COALESCE(p.conference_name,'')) LIKE ?"
                " ORDER BY p.publication_date DESC", (q, q, q, q, q))
        return self.db.query(base + " ORDER BY p.publication_date DESC")

    def row_to_tree_values(self, row):
        return (row["title"],
                row["publication_type"] or "—",
                self.person_name(row["lead_author_id"]),
                row["venue_display"] or "—",
                fmt_date(row["publication_date"]),
                "Yes" if row["ref_submitted"] else "No",
                row["quality_rating"] or "—")

    def get_field_specs(self, record=None):
        return [
            FieldSpec("title", "Title", required=True),
            FieldSpec("publication_type", "Type", kind="combo",
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
        self.detail_text.insert("end", f"{row['title']}\n", ("section",))
        self.detail_text.insert(
            "end", f"{row.get('publication_type') or '—'}\n\n", ("muted",))
        venue = (row.get("venue") or row.get("journal_name")
                 or row.get("conference_name"))
        self._write_detail([
            ("Authors", row.get("authors")),
            ("Lead author", self.person_name(row.get("lead_author_id"))),
            ("Venue", venue),
            ("Published", fmt_date(row.get("publication_date"))),
            ("DOI", row.get("doi")),
            ("Unit of Assessment", row.get("uoa")),
            ("REF submitted", "Yes" if row.get("ref_submitted") else "No"),
            ("Open access", "Yes" if row.get("open_access") else "No"),
            ("Quality rating", row.get("quality_rating")),
            ("Citations", row.get("citation_count")),
            ("Peer reviewed", "Yes" if row.get("is_peer_reviewed") else "No"),
            ("Abstract", row.get("abstract")),
        ])

    def insert_sql(self, d):
        self.db.execute("""INSERT INTO research_publications
            (title,publication_type,authors,lead_author_id,venue,
             publication_date,doi,uoa,ref_submitted,open_access,
             quality_rating,abstract)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d.get("title"), d.get("publication_type"),
             d.get("authors") or "", d.get("lead_author_id"), d.get("venue"),
             d.get("publication_date"), d.get("doi"), d.get("uoa"),
             1 if d.get("ref_submitted") else 0,
             1 if d.get("open_access") else 0,
             d.get("quality_rating"), d.get("abstract")))

    def update_sql(self, d, pk):
        self.db.execute("""UPDATE research_publications SET
            title=?,publication_type=?,authors=?,lead_author_id=?,venue=?,
            publication_date=?,doi=?,uoa=?,ref_submitted=?,open_access=?,
            quality_rating=?,abstract=? WHERE publication_id=?""",
            (d.get("title"), d.get("publication_type"),
             d.get("authors") or "", d.get("lead_author_id"), d.get("venue"),
             d.get("publication_date"), d.get("doi"), d.get("uoa"),
             1 if d.get("ref_submitted") else 0,
             1 if d.get("open_access") else 0,
             d.get("quality_rating"), d.get("abstract"), pk))
