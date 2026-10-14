"""Extracted class implementation."""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class PeopleTab(TableModule):
    """Read-only directory over the university's own registers.

    Staff come from ``staff`` (+ ``staff_profiles`` for department),
    research-degree students from ``students``, and external examiners from
    ``external_examiners``. The portal no longer keeps a people table of its
    own, so rows are addressed by a composite key such as ``"staff:12"``.

    Deliberately not editable here: creating a member of staff means
    creating a login, which belongs to Staff HR. The New/Edit/Delete buttons
    are removed rather than left to fail on click.
    """

    title = "People Directory"
    subtitle = "Staff, students and external examiners — read from the university registers."
    table_name = ""      # a union of three tables; TableModule must not guess
    pk = "key"

    def get_columns(self):
        cols = ("name", "role", "department", "email")
        heads = ("Name", "Source", "Department / institution", "Email")
        widths = (220, 110, 220, 260)
        return cols, heads, widths

    def _build(self):
        super()._build()
        # Records are owned by Staff HR / Student Records / the examiner
        # register, so drop the mutating buttons entirely.
        for child in self.walk_buttons():
            if child.cget("text") in ("+ New", "Edit", "Delete"):
                child.destroy()

    def walk_buttons(self, parent=None):
        parent = self if parent is None else parent
        found = []
        for child in parent.winfo_children():
            if isinstance(child, ttk.Button):
                found.append(child)
            found.extend(self.walk_buttons(child))
        return found

    def fetch_rows(self, search):
        needle = (search or "").strip().lower()
        rows = []
        for key, name, role, dept, email in fetch_people(self.db):
            if needle and needle not in " ".join(
                    (name or "", role or "", dept or "", email or "")).lower():
                continue
            rows.append({"key": key, "name": name, "role": role,
                         "department": dept, "email": email})
        return rows

    def row_to_tree_values(self, row):
        return (row["name"], row["role"],
                row["department"] or "—", row["email"] or "—")

    def _fetch_one(self, pk_val):
        # Overridden: the pk is a composite string key, not an integer, and
        # there is no single table to SELECT from.
        for row in self.fetch_rows(""):
            if row["key"] == str(pk_val):
                return row
        return None

    def on_select(self):
        sel = self.tree.selection()
        if not sel:
            return
        row = self._fetch_one(sel[0])
        if row is None:
            self._show_detail_error()
            return
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.render_detail(row)
        self.detail_text.configure(state="disabled")

    def render_detail(self, row):
        key = row["key"]
        self.detail_text.insert("end", f"{row['name']}\n", ("section",))
        self.detail_text.insert("end", f"{row['role']}\n\n", ("muted",))
        self._write_detail([
            ("Email", row.get("email")),
            ("Department / institution", row.get("department")),
            ("Record", key),
        ])

        ethics = self.db.query(
            "SELECT reference, title FROM ethics_reviews "
            "WHERE principal_investigator_id=?", (key,))
        outputs = self.db.query(
            "SELECT title FROM research_publications WHERE lead_author_id=?",
            (key,))
        ip = self.db.query(
            "SELECT reference, title FROM ip_disclosures WHERE inventor_id=?",
            (key,))
        theses = self.db.query(
            "SELECT thesis_title AS title FROM student_supervisions "
            "WHERE student_id=? OR supervisor_id=? OR secondary_supervisor_id=? "
            "OR internal_examiner_id=? OR external_examiner_id=?",
            (key, key, key, key, key))

        self.detail_text.insert("end", "Involvement\n", ("section",))
        for label, items in [
            ("Ethics (as PI)",
             [f"{r['reference'] or '—'} — {r['title'] or '(untitled)'}" for r in ethics]),
            ("Outputs (as lead)", [r["title"] for r in outputs]),
            ("IP (as inventor)",
             [f"{r['reference'] or '—'} — {r['title']}" for r in ip]),
            ("Theses", [r["title"] or "(untitled)" for r in theses]),
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

    # -- mutation is owned elsewhere ---------------------------------------
    def _refuse(self):
        messagebox.showinfo(
            "Managed elsewhere",
            "People are read from the staff, student and external-examiner "
            "registers. Add or change them in Staff HR, Student Records, or "
            "the external examiner register.",
            parent=self)

    def get_field_specs(self, record=None):
        return []

    def on_new(self):
        self._refuse()

    def on_edit(self):
        self._refuse()

    def on_delete(self):
        self._refuse()
