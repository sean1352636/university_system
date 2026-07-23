"""Feature 5 — Course approval workflow.

A lightweight state machine distinct from a course's Active/Inactive status:

    Draft → Submitted → Under Review → Approved
                                   └─→ Rejected → (re-submit) Draft

Every transition is recorded in ``course_approval_history`` with the actor and
a comment, giving a full audit trail. Courses with no approval row are treated
as *Draft*.
"""

from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.core.ext_common import (
    ExtFormDialog, tk, ttk, messagebox, _, logger,
)

# Allowed transitions out of each stage.
TRANSITIONS = {
    "Draft": ["Submitted"],
    "Submitted": ["Under Review", "Draft"],
    "Under Review": ["Approved", "Rejected"],
    "Approved": ["Draft"],          # re-open for revision
    "Rejected": ["Draft"],          # send back for rework
}

STAGE_COLORS = {
    "Draft": "#6b7280",
    "Submitted": "#2563eb",
    "Under Review": "#d97706",
    "Approved": "#16a34a",
    "Rejected": "#c0392b",
}


class ApprovalsTabMixin:
    """Course-approval workflow tab."""

    def create_approvals_tab(self):
        if not self._ensure_extension_schema():
            return
        try:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=_("course_management.tabs.approvals",
                                            default="Approvals"))

            bar = ttk.Frame(frame)
            bar.pack(fill=tk.X, padx=5, pady=5)
            ttk.Label(bar, text="Filter:").pack(side=tk.LEFT, padx=5)
            self._appr_filter = ttk.Combobox(
                bar, width=18, state="readonly",
                values=["All", "Draft", "Submitted", "Under Review",
                        "Approved", "Rejected"])
            self._appr_filter.set("All")
            self._appr_filter.pack(side=tk.LEFT, padx=5)
            self._appr_filter.bind("<<ComboboxSelected>>", self._reload_approvals)

            if self._ext_can_edit():
                ttk.Button(bar, text="Advance / Transition…",
                           command=self._transition_approval).pack(side=tk.LEFT, padx=5)
            ttk.Button(bar, text="History…",
                       command=self._show_approval_history).pack(side=tk.LEFT, padx=5)
            ttk.Button(bar, text=_("common.refresh", default="Refresh"),
                       command=self._reload_approvals).pack(side=tk.LEFT, padx=5)

            list_frame = ttk.Frame(frame)
            list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            cols = ("Course", "Name", "Stage", "Submitted By", "Reviewer", "Updated")
            self._appr_tree = ttk.Treeview(list_frame, columns=cols,
                                           show="headings", height=18)
            widths = {"Course": 90, "Name": 240, "Stage": 110,
                      "Submitted By": 130, "Reviewer": 130, "Updated": 150}
            for c in cols:
                self._appr_tree.heading(c, text=c)
                self._appr_tree.column(c, width=widths.get(c, 100))
            for stage, colour in STAGE_COLORS.items():
                self._appr_tree.tag_configure(f"stage_{stage}", foreground=colour)
            self._appr_tree.bind("<Double-1>", lambda _e: self._show_approval_history())
            sb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                               command=self._appr_tree.yview)
            self._appr_tree.configure(yscrollcommand=sb.set)
            self._appr_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb.pack(side=tk.RIGHT, fill=tk.Y)

            self._reload_approvals()
        except Exception as exc:
            self._ext_report_error("build Approvals tab", exc)

    def _reload_approvals(self, *_a):
        if not hasattr(self, "_appr_tree"):
            return
        self._ext_clear_tree(self._appr_tree)
        try:
            # LEFT JOIN so courses without an approval row appear as 'Draft'.
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT COALESCE(c.course_code, c.code) AS cc, "
                    "       COALESCE(c.course_name, c.name) AS cn, "
                    "       COALESCE(a.stage, 'Draft'), "
                    "       COALESCE(a.submitted_by, ''), "
                    "       COALESCE(a.reviewer, ''), "
                    "       COALESCE(a.updated_at, '') "
                    "FROM courses c "
                    "LEFT JOIN course_approvals a "
                    "       ON a.course_code = COALESCE(c.course_code, c.code) "
                    "WHERE COALESCE(c.course_code, c.code) IS NOT NULL "
                    "ORDER BY cc")
                rows = cur.fetchall()
            wanted = self._appr_filter.get() if hasattr(self, "_appr_filter") else "All"
            shown = 0
            for cc, cn, stage, sub_by, reviewer, updated in rows:
                if wanted != "All" and stage != wanted:
                    continue
                self._appr_tree.insert("", tk.END,
                                       values=(cc, cn, stage, sub_by, reviewer, updated),
                                       tags=(f"stage_{stage}",))
                shown += 1
            self.update_status(_("course_management.status.approvals_loaded",
                                 default="Loaded {n} course approval record(s).").format(n=shown))
        except Exception as exc:
            self._ext_report_error("load approvals", exc)

    def _selected_approval(self):
        vals = self._ext_selected_values(self._appr_tree)
        if not vals:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a course first.")
            return None
        return vals

    def _current_stage(self, course_code):
        """Return the current stage for a course (defaults to 'Draft')."""
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT stage FROM course_approvals WHERE course_code=?",
                            (course_code,))
                row = cur.fetchone()
            return row[0] if row else "Draft"
        except Exception as exc:
            self._ext_report_error("read approval stage", exc)
            return "Draft"

    def _transition_approval(self):
        if not self._ext_can_edit():
            return
        vals = self._selected_approval()
        if not vals:
            return
        course_code = vals[0]
        current = self._current_stage(course_code)
        targets = TRANSITIONS.get(current, [])
        if not targets:
            messagebox.showinfo(_("common.info", default="Info"),
                                f"No transitions available from '{current}'.")
            return

        def submit(values):
            target = values.get("target_stage")
            if target not in targets:
                messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                     "Choose a valid target stage.")
                return False
            comment = (values.get("comment") or "").strip()
            # Require a reason when rejecting.
            if target == "Rejected" and not comment:
                messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                     "A comment is required when rejecting.")
                return False
            actor = self._ext_username()
            try:
                with self._ext_db(write=True) as conn:
                    cur = conn.cursor()
                    # Upsert current state.
                    cur.execute("SELECT id FROM course_approvals WHERE course_code=?",
                                (course_code,))
                    existing = cur.fetchone()
                    if existing:
                        cur.execute(
                            "UPDATE course_approvals SET stage=?, "
                            "submitted_by=CASE WHEN ?='Submitted' THEN ? ELSE submitted_by END, "
                            "reviewer=CASE WHEN ? IN ('Approved','Rejected','Under Review') "
                            "             THEN ? ELSE reviewer END, "
                            "comments=?, updated_at=? WHERE course_code=?",
                            (target, target, actor, target, actor, comment,
                             self._ext_now(), course_code))
                    else:
                        cur.execute(
                            "INSERT INTO course_approvals "
                            "(course_code, stage, submitted_by, reviewer, comments, "
                            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (course_code, target,
                             actor if target == "Submitted" else "",
                             actor if target in ("Approved", "Rejected", "Under Review") else "",
                             comment, self._ext_now(), self._ext_now()))
                    # Append to the audit trail.
                    cur.execute(
                        "INSERT INTO course_approval_history "
                        "(course_code, from_stage, to_stage, actor, comments, changed_at) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (course_code, current, target, actor, comment, self._ext_now()))
            except Exception as exc:
                self._ext_report_error("record approval transition", exc)
                return False
            self._ext_audit("transition", "course_approval", course_code=course_code,
                            from_stage=current, to_stage=target)
            self._ext_notify_course_changed(course_code, "approval_changed")
            self._reload_approvals()
            return True

        ExtFormDialog(
            self.root, self,
            f"Transition {course_code} (currently: {current})",
            [("current_stage", "Current stage:",
              {"type": "readonly", "default": current}),
             ("target_stage", "Move to:",
              {"type": "combo", "values": targets, "default": targets[0]}),
             ("comment", "Comment:", {"type": "text", "height": 4})],
            submit, submit_label="Apply", geometry="500x340")

    def _show_approval_history(self):
        vals = self._selected_approval()
        if not vals:
            return
        course_code = vals[0]
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT changed_at, from_stage, to_stage, actor, comments "
                    "FROM course_approval_history WHERE course_code=? "
                    "ORDER BY id DESC", (course_code,))
                rows = cur.fetchall()
        except Exception as exc:
            self._ext_report_error("load approval history", exc)
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Approval History — {course_code}")
        dlg.geometry("760x420")
        dlg.transient(self.root)
        cols = ("When", "From", "To", "Actor", "Comment")
        tree = ttk.Treeview(dlg, columns=cols, show="headings")
        widths = {"When": 150, "From": 110, "To": 110, "Actor": 120, "Comment": 250}
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=widths.get(c, 120))
        sb = ttk.Scrollbar(dlg, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        sb.pack(side=tk.RIGHT, fill=tk.Y, pady=10)
        if rows:
            for row in rows:
                tree.insert("", tk.END, values=row)
        else:
            tree.insert("", tk.END, values=("(no transitions recorded)", "", "", "", ""))
