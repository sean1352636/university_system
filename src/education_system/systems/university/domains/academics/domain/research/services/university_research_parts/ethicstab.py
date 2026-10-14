"""Extracted class implementation."""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class EthicsTab(TableModule):
    title = "Research Ethics / IRB"
    subtitle = "Track applications, approvals and expiry across the institution."
    # ethics_reviews is the university's existing table. The portal's
    # extra fields (reference/title/PI/department/risk_level/category/notes)
    # were added to it by migration b4e19d7a3c62; `status` maps onto its
    # `decision` column and `approval_expiry` onto `approval_expiry_date`.
    # Its project_id was NOT NULL and is now nullable: a portal application
    # is standalone, not a review of an existing grant project.
    table_name = "ethics_reviews"
    pk = "review_id"

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

    _BASE = ("SELECT e.*, e.decision AS status, "
             "e.approval_expiry_date AS approval_expiry "
             "FROM ethics_reviews e")

    def fetch_rows(self, search):
        q = f"%{search.lower()}%" if search else None
        if q:
            return self.db.query(
                self._BASE +
                " WHERE LOWER(COALESCE(e.reference,'')) LIKE ?"
                "    OR LOWER(COALESCE(e.title,'')) LIKE ?"
                "    OR LOWER(COALESCE(e.department,'')) LIKE ?"
                "    OR LOWER(COALESCE(e.decision,'')) LIKE ?"
                " ORDER BY e.submission_date DESC, e.review_id DESC",
                (q, q, q, q))
        return self.db.query(
            self._BASE +
            " ORDER BY e.submission_date DESC, e.review_id DESC")

    def row_to_tree_values(self, row):
        return (row["reference"] or "—", row["title"] or "(untitled)",
                self.person_name(row["principal_investigator_id"]),
                row["category"] or "—", row["risk_level"] or "—",
                row["status"] or "—", fmt_date(row["decision_date"]))

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
            FieldSpec("submission_date", "Submitted date", kind="date",
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
        pi_name = self.person_name(row.get("principal_investigator_id"))
        self.detail_text.insert(
            "end", f"{row.get('reference') or '(no reference)'}\n", ("section",))
        self.detail_text.insert(
            "end", f"{row.get('title') or '(untitled)'}\n\n", ("value",))
        self._write_detail([
            ("Status", row.get("status")),
            ("Principal Investigator", pi_name),
            ("Department", row.get("department")),
            ("Category", row.get("category")),
            ("Risk level", row.get("risk_level")),
            ("Submitted", fmt_date(row.get("submission_date"))),
            ("Decision", fmt_date(row.get("decision_date"))),
            ("Approval expiry", fmt_date(row.get("approval_expiry"))),
            ("Notes", row.get("notes")),
            ("Reviewer comments", row.get("reviewer_comments")),
            ("Conditions", row.get("conditions")),
        ])

    def insert_sql(self, d):
        # review_type and submission_date are NOT NULL on the shared table.
        self.db.execute("""INSERT INTO ethics_reviews
            (reference,title,principal_investigator_id,department,risk_level,
             category,submission_date,decision_date,decision,
             approval_expiry_date,notes,review_type)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d.get("reference"), d.get("title"),
             d.get("principal_investigator_id"), d.get("department"),
             d.get("risk_level"), d.get("category"),
             d.get("submission_date") or date.today().isoformat(),
             d.get("decision_date"), d.get("status"),
             d.get("approval_expiry"), d.get("notes"),
             d.get("category") or "Research ethics application"))

    def update_sql(self, d, pk):
        self.db.execute("""UPDATE ethics_reviews SET
            reference=?,title=?,principal_investigator_id=?,department=?,
            risk_level=?,category=?,submission_date=?,decision_date=?,
            decision=?,approval_expiry_date=?,notes=? WHERE review_id=?""",
            (d.get("reference"), d.get("title"),
             d.get("principal_investigator_id"), d.get("department"),
             d.get("risk_level"), d.get("category"),
             d.get("submission_date") or date.today().isoformat(),
             d.get("decision_date"), d.get("status"),
             d.get("approval_expiry"), d.get("notes"), pk))
