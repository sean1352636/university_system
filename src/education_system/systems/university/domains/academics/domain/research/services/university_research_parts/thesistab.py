"""Extracted class implementation."""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class ThesisTab(TableModule):
    title = "Theses, Vivas & Supervision"
    subtitle = "Supervisor allocation, milestones, submission and examination."
    # student_supervisions is the university's existing supervision record.
    # `thesis_title` is its title column, `expected_end_date` the expected
    # submission, `program_type` the degree. The viva/examiner/outcome
    # fields it lacked were added by migration b4e19d7a3c62.
    table_name = "student_supervisions"
    pk = "supervision_id"

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

    _BASE = """
        SELECT v.*,
               v.thesis_title       AS title,
               v.expected_end_date  AS expected_submission,
               COALESCE(NULLIF(v.degree,''), v.program_type) AS degree_display
          FROM student_supervisions v
    """

    def fetch_rows(self, search):
        q = f"%{search.lower()}%" if search else None
        if q:
            return self.db.query(
                self._BASE +
                " WHERE LOWER(COALESCE(v.student_name,'')) LIKE ?"
                "    OR LOWER(COALESCE(v.thesis_title,'')) LIKE ?"
                "    OR LOWER(COALESCE(v.department,'')) LIKE ?"
                "    OR LOWER(COALESCE(v.status,'')) LIKE ?"
                " ORDER BY v.start_date DESC", (q, q, q, q))
        return self.db.query(self._BASE + " ORDER BY v.start_date DESC")

    def row_to_tree_values(self, row):
        # student_name is denormalised on the table; fall back to the
        # register when it is blank.
        student = row["student_name"] or self.person_name(row["student_id"])
        return (student,
                row["title"] or "(untitled)",
                row["degree_display"] or "—",
                self.person_name(row["supervisor_id"]),
                fmt_date(row["viva_date"]),
                row["status"] or "—")

    def get_field_specs(self, record=None):
        return [
            FieldSpec("student_id", "Student", kind="people",
                      choices=self.people_choices(role="student"),
                      required=True),
            FieldSpec("title", "Thesis title", required=True),
            FieldSpec("degree", "Degree", kind="combo",
                      choices=self.DEGREES, required=True),
            FieldSpec("department", "Department"),
            FieldSpec("supervisor_id", "Primary supervisor",
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
        person = self.person_name

        student = row.get("student_name") or person(row.get("student_id"))
        degree = row.get("degree") or row.get("program_type") or "—"
        self.detail_text.insert(
            "end", f"{row.get('title') or '(untitled)'}\n", ("section",))
        self.detail_text.insert("end", f"{degree} — {student}\n\n", ("muted",))
        self._write_detail([
            ("Status", row.get("status")),
            ("Department", row.get("department")),
            ("Primary supervisor", person(row.get("supervisor_id"))),
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
        # Keyed on the table's own pk (supervision_id), not a literal "id".
        self._refresh_milestones(row[self.pk])

    def _clear_detail(self):
        super()._clear_detail()
        if hasattr(self, "ms_tree"):
            for iid in self.ms_tree.get_children():
                self.ms_tree.delete(iid)

    def _refresh_milestones(self, thesis_id):
        for iid in self.ms_tree.get_children():
            self.ms_tree.delete(iid)
        rows = self.db.query(
            "SELECT milestone_id AS id, milestone_name AS name, "
            "       target_date AS due_date, completion_date AS completed_date, "
            "       status, notes "
            "  FROM research_milestones WHERE thesis_id=? "
            " ORDER BY COALESCE(target_date,'9999-12-31')", (thesis_id,))
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
            self.db.execute("""INSERT INTO research_milestones
                (thesis_id,milestone_name,target_date,status,notes)
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
            "UPDATE research_milestones SET status='Completed', "
            "completion_date=? WHERE milestone_id=?",
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
        self.db.execute(
            "DELETE FROM research_milestones WHERE milestone_id=?",
            (int(sel[0]),))
        self._refresh_milestones(tid)
        self.app.dashboard.refresh()

    def insert_sql(self, d):
        # supervisor_id and student_id are NOT NULL on the shared table.
        self.db.execute("""INSERT INTO student_supervisions
            (student_id,student_name,thesis_title,degree,program_type,
             department,supervisor_id,secondary_supervisor_id,start_date,
             expected_end_date,submission_date,viva_date,
             internal_examiner_id,external_examiner_id,status,outcome,
             supervision_role)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'primary')""",
            (d.get("student_id") or "", self.person_name(d.get("student_id")),
             d.get("title"), d.get("degree"), d.get("degree"),
             d.get("department"), d.get("supervisor_id") or "",
             d.get("secondary_supervisor_id"), d.get("start_date"),
             d.get("expected_submission"), d.get("submission_date"),
             d.get("viva_date"), d.get("internal_examiner_id"),
             d.get("external_examiner_id"), d.get("status"),
             d.get("outcome")))

    def update_sql(self, d, pk):
        self.db.execute("""UPDATE student_supervisions SET
            student_id=?,student_name=?,thesis_title=?,degree=?,
            program_type=?,department=?,supervisor_id=?,
            secondary_supervisor_id=?,start_date=?,expected_end_date=?,
            submission_date=?,viva_date=?,internal_examiner_id=?,
            external_examiner_id=?,status=?,outcome=?,
            updated_at=CURRENT_TIMESTAMP
            WHERE supervision_id=?""",
            (d.get("student_id") or "", self.person_name(d.get("student_id")),
             d.get("title"), d.get("degree"), d.get("degree"),
             d.get("department"), d.get("supervisor_id") or "",
             d.get("secondary_supervisor_id"), d.get("start_date"),
             d.get("expected_submission"), d.get("submission_date"),
             d.get("viva_date"), d.get("internal_examiner_id"),
             d.get("external_examiner_id"), d.get("status"),
             d.get("outcome"), pk))
