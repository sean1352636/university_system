"""Extracted class implementation."""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class ThesisTab(TableModule):
    title = "Theses, Vivas & Supervision"
    subtitle = "Supervisor allocation, milestones, submission and examination."
    table_name = "theses"

    DEGREES = ["PhD", "MPhil", "MRes", "Masters"]
    STATUSES = ["Active", "Submitted", "Under Examination",
                "Viva Scheduled", "Passed", "Minor Corrections",
                "Major Corrections", "Failed", "Withdrawn"]

    MILESTONE_STATUSES = ["Pending", "Completed", "Overdue", "Missed"]

    def get_columns(self):
        cols = ("student", "title", "degree", "supervisor",
                "viva", "status")
        heads = ("Student", "Thesis title", "Degree",
                 "Primary supervisor", "Viva date", "Status")
        widths = (150, 300, 70, 170, 110, 140)
        return cols, heads, widths

    def _build(self):
        super()._build()
        # Add milestone pane beneath the detail text
        ms_frame = ttk.Frame(self.detail_text.master, style="Panel.TFrame")
        ms_frame.pack(fill="both", expand=False, pady=(10, 0))
        ttk.Label(ms_frame, text="Milestones",
                  style="SectionTitle.TLabel").pack(anchor="w")
        ttk.Separator(ms_frame).pack(fill="x", pady=(4, 8))

        ms_actions = ttk.Frame(ms_frame, style="Panel.TFrame")
        ms_actions.pack(fill="x", pady=(0, 6))
        ttk.Button(ms_actions, text="+ Add milestone",
                   command=self.add_milestone).pack(side="left")
        ttk.Button(ms_actions, text="Mark completed",
                   command=self.complete_milestone).pack(side="left", padx=6)
        ttk.Button(ms_actions, text="Delete",
                   command=self.delete_milestone).pack(side="left")

        cols = ("name", "due", "completed", "status")
        self.ms_tree = ttk.Treeview(ms_frame, columns=cols, show="headings",
                                    height=6, selectmode="browse")
        for c, h, w in zip(cols, ("Milestone", "Due", "Completed", "Status"),
                           (200, 100, 100, 100)):
            self.ms_tree.heading(c, text=h)
            self.ms_tree.column(c, width=w, anchor="w")
        self.ms_tree.pack(fill="both", expand=True)
        self.ms_tree.tag_configure("overdue", foreground=PALETTE["danger"])
        self.ms_tree.tag_configure("done", foreground=PALETTE["success"])

    def fetch_rows(self, search):
        q = f"%{search.lower()}%" if search else None
        base = """SELECT t.*,
                  s.name AS student_name,
                  sup.name AS supervisor_name
                  FROM research_theses t
                  LEFT JOIN research_people s ON s.id=t.student_id
                  LEFT JOIN research_people sup ON sup.id=t.primary_supervisor_id"""
        if q:
            return self.db.query(base + """
                WHERE LOWER(COALESCE(s.name,'')) LIKE ?
                   OR LOWER(t.title) LIKE ?
                   OR LOWER(COALESCE(sup.name,'')) LIKE ?
                   OR LOWER(t.status) LIKE ?
                ORDER BY t.start_date DESC""", (q, q, q, q))
        return self.db.query(base + " ORDER BY t.start_date DESC")

    def row_to_tree_values(self, row):
        return (row["student_name"] or "—",
                row["title"],
                row["degree"],
                row["supervisor_name"] or "—",
                fmt_date(row["viva_date"]),
                row["status"])

    def get_field_specs(self, record=None):
        return [
            FieldSpec("student_id", "Student", kind="people",
                      choices=self.people_choices(role="student"),
                      required=True),
            FieldSpec("title", "Thesis title", required=True),
            FieldSpec("degree", "Degree", kind="combo",
                      choices=self.DEGREES, required=True),
            FieldSpec("department", "Department"),
            FieldSpec("primary_supervisor_id", "Primary supervisor",
                      kind="people", choices=self.people_choices(role="staff")),
            FieldSpec("secondary_supervisor_id", "Secondary supervisor",
                      kind="people", choices=self.people_choices(role="staff")),
            FieldSpec("start_date", "Start date", kind="date"),
            FieldSpec("expected_submission", "Expected submission",
                      kind="date"),
            FieldSpec("submission_date", "Actual submission", kind="date"),
            FieldSpec("viva_date", "Viva date", kind="date"),
            FieldSpec("internal_examiner_id", "Internal examiner",
                      kind="people", choices=self.people_choices(role="staff")),
            FieldSpec("external_examiner_id", "External examiner",
                      kind="people",
                      choices=self.people_choices(role="external")),
            FieldSpec("status", "Status", kind="combo",
                      choices=self.STATUSES, required=True),
            FieldSpec("outcome", "Outcome / notes", kind="multiline"),
        ]

    def render_detail(self, row):
        def person(pid):
            if not pid:
                return "—"
            r = self.db.query("SELECT name FROM research_people WHERE id=?", (pid,))
            return r[0]["name"] if r else "—"

        self.detail_text.insert("end", f"{row['title']}\n", ("section",))
        self.detail_text.insert("end",
                                f"{row.get('degree')} — {person(row.get('student_id'))}\n\n",
                                ("muted",))
        self._write_detail([
            ("Status", row.get("status")),
            ("Department", row.get("department")),
            ("Primary supervisor", person(row.get("primary_supervisor_id"))),
            ("Secondary supervisor",
             person(row.get("secondary_supervisor_id"))),
            ("Start date", fmt_date(row.get("start_date"))),
            ("Expected submission",
             fmt_date(row.get("expected_submission"))),
            ("Actual submission", fmt_date(row.get("submission_date"))),
            ("Viva date", fmt_date(row.get("viva_date"))),
            ("Internal examiner", person(row.get("internal_examiner_id"))),
            ("External examiner", person(row.get("external_examiner_id"))),
            ("Outcome / notes", row.get("outcome")),
        ])
        self._refresh_milestones(row["id"])

    def _clear_detail(self):
        super()._clear_detail()
        if hasattr(self, "ms_tree"):
            for iid in self.ms_tree.get_children():
                self.ms_tree.delete(iid)

    def _refresh_milestones(self, thesis_id):
        for iid in self.ms_tree.get_children():
            self.ms_tree.delete(iid)
        rows = self.db.query(
            "SELECT * FROM research_thesis_milestones WHERE thesis_id=? "
            "ORDER BY COALESCE(due_date,'9999-12-31')", (thesis_id,))
        today = date.today().isoformat()
        for r in rows:
            tag = ()
            status = r["status"]
            if status == "Pending" and r["due_date"] and r["due_date"] < today:
                status = "Overdue"
                tag = ("overdue",)
            elif status == "Completed":
                tag = ("done",)
            self.ms_tree.insert("", "end", iid=str(r["id"]),
                                values=(r["name"],
                                        fmt_date(r["due_date"]),
                                        fmt_date(r["completed_date"]),
                                        status),
                                tags=tag)

    def _selected_thesis_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def add_milestone(self):
        tid = self._selected_thesis_id()
        if not tid:
            messagebox.showinfo("No thesis selected",
                                "Select a thesis first.", parent=self)
            return
        fields = [
            FieldSpec("name", "Milestone", required=True),
            FieldSpec("due_date", "Due date", kind="date"),
            FieldSpec("status", "Status", kind="combo",
                      choices=self.MILESTONE_STATUSES, default="Pending",
                      required=True),
            FieldSpec("notes", "Notes", kind="multiline"),
        ]
        dlg = RecordDialog(self.app.root, "New milestone", fields)
        self.wait_window(dlg)
        if dlg.result:
            d = dlg.result
            self.db.execute("""INSERT INTO research_thesis_milestones
                (thesis_id,name,due_date,status,notes)
                VALUES(?,?,?,?,?)""",
                (tid, d.get("name"), d.get("due_date"),
                 d.get("status"), d.get("notes")))
            self._refresh_milestones(tid)
            self.app.dashboard.refresh()

    def complete_milestone(self):
        tid = self._selected_thesis_id()
        sel = self.ms_tree.selection()
        if not (tid and sel):
            messagebox.showinfo("No milestone selected",
                                "Select a milestone to complete.", parent=self)
            return
        mid = int(sel[0])
        self.db.execute(
            "UPDATE research_thesis_milestones SET status='Completed', "
            "completed_date=? WHERE id=?",
            (date.today().isoformat(), mid))
        self._refresh_milestones(tid)
        self.app.dashboard.refresh()

    def delete_milestone(self):
        tid = self._selected_thesis_id()
        sel = self.ms_tree.selection()
        if not (tid and sel):
            return
        if not messagebox.askyesno("Confirm",
                                   "Delete the selected milestone?",
                                   parent=self):
            return
        self.db.execute("DELETE FROM research_thesis_milestones WHERE id=?",
                        (int(sel[0]),))
        self._refresh_milestones(tid)
        self.app.dashboard.refresh()

    def insert_sql(self, d):
        self.db.execute("""INSERT INTO research_theses
            (student_id,title,degree,department,primary_supervisor_id,
             secondary_supervisor_id,start_date,expected_submission,
             submission_date,viva_date,internal_examiner_id,
             external_examiner_id,status,outcome)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d.get("student_id"), d.get("title"), d.get("degree"),
             d.get("department"), d.get("primary_supervisor_id"),
             d.get("secondary_supervisor_id"), d.get("start_date"),
             d.get("expected_submission"), d.get("submission_date"),
             d.get("viva_date"), d.get("internal_examiner_id"),
             d.get("external_examiner_id"), d.get("status"),
             d.get("outcome")))

    def update_sql(self, d, pk):
        self.db.execute("""UPDATE research_theses SET
            student_id=?,title=?,degree=?,department=?,
            primary_supervisor_id=?,secondary_supervisor_id=?,
            start_date=?,expected_submission=?,submission_date=?,
            viva_date=?,internal_examiner_id=?,external_examiner_id=?,
            status=?,outcome=? WHERE id=?""",
            (d.get("student_id"), d.get("title"), d.get("degree"),
             d.get("department"), d.get("primary_supervisor_id"),
             d.get("secondary_supervisor_id"), d.get("start_date"),
             d.get("expected_submission"), d.get("submission_date"),
             d.get("viva_date"), d.get("internal_examiner_id"),
             d.get("external_examiner_id"), d.get("status"),
             d.get("outcome"), pk))
