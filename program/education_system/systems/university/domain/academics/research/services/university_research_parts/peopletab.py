"""Extracted class implementation."""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class PeopleTab(TableModule):
    title = "People Directory"
    subtitle = "Staff, students and external examiners."
    table_name = "people"

    ROLES = ["staff", "student", "examiner", "external"]

    def get_columns(self):
        cols = ("name", "role", "department", "email")
        heads = ("Name", "Role", "Department", "Email")
        widths = (220, 110, 200, 260)
        return cols, heads, widths

    def fetch_rows(self, search):
        q = f"%{search.lower()}%" if search else None
        if q:
            return self.db.query("""SELECT * FROM research_people
                WHERE LOWER(name) LIKE ? OR LOWER(COALESCE(email,'')) LIKE ?
                   OR LOWER(COALESCE(department,'')) LIKE ?
                   OR LOWER(role) LIKE ?
                ORDER BY name""", (q, q, q, q))
        return self.db.query("SELECT * FROM research_people ORDER BY name")

    def row_to_tree_values(self, row):
        return (row["name"], row["role"],
                row["department"] or "—", row["email"] or "—")

    def get_field_specs(self, record=None):
        return [
            FieldSpec("name", "Full name", required=True),
            FieldSpec("email", "Email"),
            FieldSpec("role", "Role", kind="combo",
                      choices=self.ROLES, required=True),
            FieldSpec("department", "Department"),
        ]

    def render_detail(self, row):
        self.detail_text.insert("end", f"{row['name']}\n", ("section",))
        self.detail_text.insert("end", f"{row['role']}\n\n", ("muted",))
        self._write_detail([
            ("Email", row.get("email")),
            ("Department", row.get("department")),
            ("Created", fmt_date(row.get("created_at"))),
        ])

        # Quick links — what this person is involved in
        pid = row["id"]
        ethics = self.db.query(
            "SELECT reference,title FROM research_ethics_applications "
            "WHERE principal_investigator_id=?", (pid,))
        outputs = self.db.query(
            "SELECT title FROM research_outputs WHERE lead_author_id=?",
            (pid,))
        ip = self.db.query(
            "SELECT reference,title FROM research_ip_assets WHERE inventor_id=?",
            (pid,))
        theses = self.db.query(
            "SELECT title FROM research_theses WHERE student_id=? "
            "OR primary_supervisor_id=? OR secondary_supervisor_id=? "
            "OR internal_examiner_id=? OR external_examiner_id=?",
            (pid, pid, pid, pid, pid))

        self.detail_text.insert("end", "Involvement\n", ("section",))
        for label, items in [
            ("Ethics (as PI)", [f"{r['reference']} — {r['title']}" for r in ethics]),
            ("Outputs (as lead)", [r["title"] for r in outputs]),
            ("IP (as inventor)",
             [f"{r['reference']} — {r['title']}" for r in ip]),
            ("Theses", [r["title"] for r in theses]),
        ]:
            self.detail_text.insert("end", f"\n{label}\n", ("label",))
            if not items:
                self.detail_text.insert("end", "  —\n", ("muted",))
            else:
                for it in items[:6]:
                    self.detail_text.insert("end", f"  • {it}\n", ("value",))
                if len(items) > 6:
                    self.detail_text.insert(
                        "end", f"  … and {len(items) - 6} more\n", ("muted",))

    def insert_sql(self, d):
        self.db.execute("""INSERT INTO research_people(name,email,role,department,created_at)
            VALUES(?,?,?,?,?)""",
            (d.get("name"), d.get("email"), d.get("role"),
             d.get("department"), datetime.now().isoformat()))

    def update_sql(self, d, pk):
        self.db.execute("""UPDATE research_people SET name=?,email=?,role=?,department=?
            WHERE id=?""",
            (d.get("name"), d.get("email"), d.get("role"),
             d.get("department"), pk))
