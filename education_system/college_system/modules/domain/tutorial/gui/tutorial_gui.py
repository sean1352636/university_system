"""Tutorial System GUI module."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.tutorial.services.tutorial_service import TutorialService


class TutorialFrame(tk.Frame):
    """Tutorial System management frame with Assignments, Sessions, Records, and Statistics tabs."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = TutorialService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Tutorial System",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_assignments_tab()
        self._build_sessions_tab()
        self._build_records_tab()
        self._build_stats_tab()

    # ── Assignments Tab ────────────────────────────────────────────────

    def _build_assignments_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Assignments")

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))
        tk.Label(filt, text="Status:", bg="#ecf0f1").pack(side="left")
        self._asgn_status_var = tk.StringVar(value="")
        ttk.Combobox(filt, textvariable=self._asgn_status_var, width=12,
                     values=["", "active", "ended", "transferred"],
                     state="readonly").pack(side="left", padx=5)
        tk.Label(filt, text="Group:", bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._asgn_group_var = tk.StringVar(value="")
        ttk.Entry(filt, textvariable=self._asgn_group_var, width=12).pack(side="left", padx=5)
        ttk.Button(filt, text="Filter", command=self._load_assignments).pack(side="left", padx=5)

        # Treeview
        cols = ("id", "student_id", "tutor_id", "academic_year", "tutor_group", "status")
        self._asgn_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("student_id", "Student ID", 80),
                         ("tutor_id", "Tutor ID", 80), ("academic_year", "Academic Year", 100),
                         ("tutor_group", "Tutor Group", 100), ("status", "Status", 80)]:
            self._asgn_tree.heading(c, text=h)
            self._asgn_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._asgn_tree.yview)
        self._asgn_tree.configure(yscrollcommand=vsb.set)
        self._asgn_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        # Buttons
        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(side="right", fill="y", padx=(10, 0))
        for text, cmd in [("New", self._new_assignment),
                          ("View", self._view_assignment),
                          ("Update", self._update_assignment),
                          ("End", self._end_assignment),
                          ("Delete", self._delete_assignment)]:
            ttk.Button(btn_frame, text=text, command=cmd, width=12).pack(pady=3)

    def _load_assignments(self):
        self._asgn_tree.delete(*self._asgn_tree.get_children())
        try:
            status = self._asgn_status_var.get() or None
            group = self._asgn_group_var.get().strip() or None
            for r in self._svc.list_assignments(status=status, tutor_group=group):
                self._asgn_tree.insert("", "end", values=(
                    r["id"], r["student_id"], r["tutor_id"],
                    r.get("academic_year") or "-",
                    r.get("tutor_group") or "-", r["status"]))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selected_asgn_id(self):
        sel = self._asgn_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select an assignment first.")
            return None
        return self._asgn_tree.item(sel[0], "values")[0]

    def _new_assignment(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Tutor Assignment")
        dlg.geometry("350x260")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        for i, (label, key) in enumerate([
            ("Student ID *:", "student_id"), ("Tutor ID *:", "tutor_id"),
            ("Academic Year:", "academic_year"), ("Tutor Group:", "tutor_group"),
        ]):
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=i, column=0, sticky="e", padx=10, pady=5)
            var = tk.StringVar()
            ttk.Entry(dlg, textvariable=var, width=20).grid(row=i, column=1, padx=10, pady=5)
            fields[key] = var

        tk.Label(dlg, text="Status:", bg="#ecf0f1").grid(row=4, column=0, sticky="e", padx=10, pady=5)
        status_var = tk.StringVar(value="active")
        ttk.Combobox(dlg, textvariable=status_var, width=17,
                     values=["active", "ended", "transferred"],
                     state="readonly").grid(row=4, column=1, padx=10, pady=5)
        fields["status"] = status_var

        def save():
            try:
                sid = int(fields["student_id"].get())
                tid = int(fields["tutor_id"].get())
                kwargs = {}
                if fields["academic_year"].get().strip():
                    kwargs["academic_year"] = fields["academic_year"].get().strip()
                if fields["tutor_group"].get().strip():
                    kwargs["tutor_group"] = fields["tutor_group"].get().strip()
                kwargs["status"] = fields["status"].get()
                self._svc.create_assignment(sid, tid, **kwargs)
                messagebox.showinfo("Success", "Assignment created.")
                dlg.destroy()
                self._load_assignments()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(dlg, text="Save", command=save).grid(row=5, column=0, columnspan=2, pady=15)

    def _view_assignment(self):
        aid = self._selected_asgn_id()
        if aid is None:
            return
        try:
            r = self._svc.get_assignment(int(aid))
            if not r:
                messagebox.showwarning("Not Found", "Assignment not found.")
                return
            dlg = tk.Toplevel(self)
            dlg.title(f"Assignment #{r['id']}")
            dlg.geometry("400x300")
            dlg.configure(bg="#ecf0f1")
            dlg.transient(self)

            info = (
                f"ID: {r['id']}\n"
                f"Student: {r.get('student_first', '')} {r.get('student_last', '')} (ID: {r['student_id']})\n"
                f"Tutor: {r.get('tutor_first', '')} {r.get('tutor_last', '')} (ID: {r['tutor_id']})\n"
                f"Academic Year: {r.get('academic_year') or '-'}\n"
                f"Tutor Group: {r.get('tutor_group') or '-'}\n"
                f"Status: {r['status']}\n"
                f"Created: {r.get('created_at') or '-'}"
            )
            tk.Label(dlg, text=info, bg="#ecf0f1", justify="left",
                     font=("Helvetica", 11)).pack(padx=20, pady=20, anchor="w")
            ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=10)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _update_assignment(self):
        aid = self._selected_asgn_id()
        if aid is None:
            return
        try:
            r = self._svc.get_assignment(int(aid))
            if not r:
                messagebox.showwarning("Not Found", "Assignment not found.")
                return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Update Assignment #{r['id']}")
        dlg.geometry("350x260")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        defaults = [
            ("Academic Year:", "academic_year", r.get("academic_year") or ""),
            ("Tutor Group:", "tutor_group", r.get("tutor_group") or ""),
        ]
        for i, (label, key, default) in enumerate(defaults):
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=i, column=0, sticky="e", padx=10, pady=5)
            var = tk.StringVar(value=default)
            ttk.Entry(dlg, textvariable=var, width=20).grid(row=i, column=1, padx=10, pady=5)
            fields[key] = var

        tk.Label(dlg, text="Status:", bg="#ecf0f1").grid(row=2, column=0, sticky="e", padx=10, pady=5)
        status_var = tk.StringVar(value=r["status"])
        ttk.Combobox(dlg, textvariable=status_var, width=17,
                     values=["active", "ended", "transferred"],
                     state="readonly").grid(row=2, column=1, padx=10, pady=5)
        fields["status"] = status_var

        def save():
            try:
                updates = {}
                for key, var in fields.items():
                    val = var.get().strip()
                    if val:
                        updates[key] = val
                if updates:
                    self._svc.update_assignment(int(aid), **updates)
                    messagebox.showinfo("Success", "Assignment updated.")
                    dlg.destroy()
                    self._load_assignments()
                else:
                    messagebox.showwarning("Warning", "No changes to save.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(dlg, text="Save", command=save).grid(row=3, column=0, columnspan=2, pady=15)

    def _end_assignment(self):
        aid = self._selected_asgn_id()
        if aid is None:
            return
        if not messagebox.askyesno("Confirm", "End this assignment?"):
            return
        try:
            self._svc.end_assignment(int(aid))
            messagebox.showinfo("Success", "Assignment ended.")
            self._load_assignments()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _delete_assignment(self):
        aid = self._selected_asgn_id()
        if aid is None:
            return
        if not messagebox.askyesno("Confirm", "Delete this assignment?"):
            return
        try:
            self._svc.delete_assignment(int(aid))
            messagebox.showinfo("Success", "Assignment deleted.")
            self._load_assignments()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Sessions Tab ───────────────────────────────────────────────────

    def _build_sessions_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Sessions")

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))
        tk.Label(filt, text="Status:", bg="#ecf0f1").pack(side="left")
        self._sess_status_var = tk.StringVar(value="")
        ttk.Combobox(filt, textvariable=self._sess_status_var, width=12,
                     values=["", "scheduled", "completed", "cancelled"],
                     state="readonly").pack(side="left", padx=5)
        tk.Label(filt, text="Type:", bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._sess_type_var = tk.StringVar(value="")
        ttk.Combobox(filt, textvariable=self._sess_type_var, width=12,
                     values=["", "group", "1to1", "assembly", "enrichment", "careers"],
                     state="readonly").pack(side="left", padx=5)
        tk.Label(filt, text="Group:", bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._sess_group_var = tk.StringVar(value="")
        ttk.Entry(filt, textvariable=self._sess_group_var, width=12).pack(side="left", padx=5)
        ttk.Button(filt, text="Filter", command=self._load_sessions).pack(side="left", padx=5)

        # Treeview
        cols = ("id", "tutor_id", "tutor_group", "session_date", "session_type", "topic", "status")
        self._sess_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("tutor_id", "Tutor ID", 70),
                         ("tutor_group", "Group", 80), ("session_date", "Date", 90),
                         ("session_type", "Type", 80), ("topic", "Topic", 160),
                         ("status", "Status", 80)]:
            self._sess_tree.heading(c, text=h)
            self._sess_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._sess_tree.yview)
        self._sess_tree.configure(yscrollcommand=vsb.set)
        self._sess_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        # Buttons
        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(side="right", fill="y", padx=(10, 0))
        for text, cmd in [("New", self._new_session),
                          ("View", self._view_session),
                          ("Update", self._update_session),
                          ("Complete", self._complete_session),
                          ("Delete", self._delete_session)]:
            ttk.Button(btn_frame, text=text, command=cmd, width=12).pack(pady=3)

    def _load_sessions(self):
        self._sess_tree.delete(*self._sess_tree.get_children())
        try:
            status = self._sess_status_var.get() or None
            group = self._sess_group_var.get().strip() or None
            # session_type filter applied client-side since service doesn't have it as param
            stype = self._sess_type_var.get() or None
            sessions = self._svc.list_sessions(status=status, tutor_group=group)
            for r in sessions:
                if stype and r.get("session_type") != stype:
                    continue
                self._sess_tree.insert("", "end", values=(
                    r["id"], r["tutor_id"], r.get("tutor_group") or "-",
                    r["session_date"], r.get("session_type") or "group",
                    r.get("topic") or "-", r["status"]))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selected_sess_id(self):
        sel = self._sess_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a session first.")
            return None
        return self._sess_tree.item(sel[0], "values")[0]

    def _new_session(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Tutorial Session")
        dlg.geometry("400x350")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        entries = [
            ("Tutor ID *:", "tutor_id"),
            ("Session Date * (YYYY-MM-DD):", "session_date"),
            ("Tutor Group:", "tutor_group"),
            ("Topic:", "topic"),
            ("Resources:", "resources"),
        ]
        for i, (label, key) in enumerate(entries):
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=i, column=0, sticky="e", padx=10, pady=5)
            var = tk.StringVar()
            ttk.Entry(dlg, textvariable=var, width=22).grid(row=i, column=1, padx=10, pady=5)
            fields[key] = var

        row_idx = len(entries)
        tk.Label(dlg, text="Type:", bg="#ecf0f1").grid(row=row_idx, column=0, sticky="e", padx=10, pady=5)
        type_var = tk.StringVar(value="group")
        ttk.Combobox(dlg, textvariable=type_var, width=19,
                     values=["group", "1to1", "assembly", "enrichment", "careers"],
                     state="readonly").grid(row=row_idx, column=1, padx=10, pady=5)
        fields["session_type"] = type_var

        tk.Label(dlg, text="Notes:", bg="#ecf0f1").grid(row=row_idx + 1, column=0, sticky="ne", padx=10, pady=5)
        notes_text = tk.Text(dlg, width=22, height=3)
        notes_text.grid(row=row_idx + 1, column=1, padx=10, pady=5)

        def save():
            try:
                tid = int(fields["tutor_id"].get())
                sdate = fields["session_date"].get().strip()
                if not sdate:
                    messagebox.showwarning("Warning", "Session date is required.")
                    return
                kwargs = {}
                for key in ("tutor_group", "topic", "resources", "session_type"):
                    val = fields[key].get().strip()
                    if val:
                        kwargs[key] = val
                notes = notes_text.get("1.0", "end").strip()
                if notes:
                    kwargs["notes"] = notes
                self._svc.create_session(tid, sdate, **kwargs)
                messagebox.showinfo("Success", "Session created.")
                dlg.destroy()
                self._load_sessions()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(dlg, text="Save", command=save).grid(row=row_idx + 2, column=0, columnspan=2, pady=10)

    def _view_session(self):
        sid = self._selected_sess_id()
        if sid is None:
            return
        try:
            r = self._svc.get_session(int(sid))
            if not r:
                messagebox.showwarning("Not Found", "Session not found.")
                return
            dlg = tk.Toplevel(self)
            dlg.title(f"Session #{r['id']}")
            dlg.geometry("450x350")
            dlg.configure(bg="#ecf0f1")
            dlg.transient(self)

            info = (
                f"ID: {r['id']}\n"
                f"Tutor: {r.get('tutor_first', '')} {r.get('tutor_last', '')} (ID: {r['tutor_id']})\n"
                f"Group: {r.get('tutor_group') or '-'}\n"
                f"Date: {r['session_date']}\n"
                f"Type: {r.get('session_type') or 'group'}\n"
                f"Topic: {r.get('topic') or '-'}\n"
                f"Resources: {r.get('resources') or '-'}\n"
                f"Status: {r['status']}\n"
                f"Notes: {r.get('notes') or '-'}\n"
                f"Created: {r.get('created_at') or '-'}"
            )
            tk.Label(dlg, text=info, bg="#ecf0f1", justify="left",
                     font=("Helvetica", 11)).pack(padx=20, pady=20, anchor="w")
            ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=10)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _update_session(self):
        sid = self._selected_sess_id()
        if sid is None:
            return
        try:
            r = self._svc.get_session(int(sid))
            if not r:
                messagebox.showwarning("Not Found", "Session not found.")
                return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Update Session #{r['id']}")
        dlg.geometry("400x350")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        entries = [
            ("Session Date:", "session_date", r["session_date"]),
            ("Tutor Group:", "tutor_group", r.get("tutor_group") or ""),
            ("Topic:", "topic", r.get("topic") or ""),
            ("Resources:", "resources", r.get("resources") or ""),
        ]
        for i, (label, key, default) in enumerate(entries):
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=i, column=0, sticky="e", padx=10, pady=5)
            var = tk.StringVar(value=default)
            ttk.Entry(dlg, textvariable=var, width=22).grid(row=i, column=1, padx=10, pady=5)
            fields[key] = var

        row_idx = len(entries)
        tk.Label(dlg, text="Type:", bg="#ecf0f1").grid(row=row_idx, column=0, sticky="e", padx=10, pady=5)
        type_var = tk.StringVar(value=r.get("session_type") or "group")
        ttk.Combobox(dlg, textvariable=type_var, width=19,
                     values=["group", "1to1", "assembly", "enrichment", "careers"],
                     state="readonly").grid(row=row_idx, column=1, padx=10, pady=5)
        fields["session_type"] = type_var

        tk.Label(dlg, text="Status:", bg="#ecf0f1").grid(row=row_idx + 1, column=0, sticky="e", padx=10, pady=5)
        status_var = tk.StringVar(value=r["status"])
        ttk.Combobox(dlg, textvariable=status_var, width=19,
                     values=["scheduled", "completed", "cancelled"],
                     state="readonly").grid(row=row_idx + 1, column=1, padx=10, pady=5)
        fields["status"] = status_var

        def save():
            try:
                updates = {}
                for key, var in fields.items():
                    val = var.get().strip()
                    if val:
                        updates[key] = val
                if updates:
                    self._svc.update_session(int(sid), **updates)
                    messagebox.showinfo("Success", "Session updated.")
                    dlg.destroy()
                    self._load_sessions()
                else:
                    messagebox.showwarning("Warning", "No changes to save.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(dlg, text="Save", command=save).grid(row=row_idx + 2, column=0, columnspan=2, pady=10)

    def _complete_session(self):
        sid = self._selected_sess_id()
        if sid is None:
            return
        if not messagebox.askyesno("Confirm", "Mark this session as completed?"):
            return
        try:
            self._svc.complete_session(int(sid))
            messagebox.showinfo("Success", "Session completed.")
            self._load_sessions()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _delete_session(self):
        sid = self._selected_sess_id()
        if sid is None:
            return
        if not messagebox.askyesno("Confirm", "Delete this session?"):
            return
        try:
            self._svc.delete_session(int(sid))
            messagebox.showinfo("Success", "Session deleted.")
            self._load_sessions()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Records Tab ────────────────────────────────────────────────────

    def _build_records_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Records")

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))
        tk.Label(filt, text="Student ID:", bg="#ecf0f1").pack(side="left")
        self._rec_student_var = tk.StringVar(value="")
        ttk.Entry(filt, textvariable=self._rec_student_var, width=8).pack(side="left", padx=5)
        tk.Label(filt, text="Type:", bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._rec_type_var = tk.StringVar(value="")
        ttk.Combobox(filt, textvariable=self._rec_type_var, width=14,
                     values=["", "1to1", "progress_review", "pastoral",
                             "target_setting", "careers", "other"],
                     state="readonly").pack(side="left", padx=5)
        ttk.Button(filt, text="Filter", command=self._load_records).pack(side="left", padx=5)

        # Treeview
        cols = ("id", "student_id", "tutor_id", "meeting_date", "meeting_type",
                "targets_set", "follow_up")
        self._rec_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("student_id", "Student ID", 80),
                         ("tutor_id", "Tutor ID", 70), ("meeting_date", "Date", 90),
                         ("meeting_type", "Type", 110), ("targets_set", "Targets", 150),
                         ("follow_up", "Follow Up", 70)]:
            self._rec_tree.heading(c, text=h)
            self._rec_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._rec_tree.yview)
        self._rec_tree.configure(yscrollcommand=vsb.set)
        self._rec_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        # Buttons
        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(side="right", fill="y", padx=(10, 0))
        for text, cmd in [("New", self._new_record),
                          ("View", self._view_record),
                          ("Update", self._update_record),
                          ("Delete", self._delete_record),
                          ("Follow-Ups", self._show_follow_ups)]:
            ttk.Button(btn_frame, text=text, command=cmd, width=12).pack(pady=3)

    def _load_records(self):
        self._rec_tree.delete(*self._rec_tree.get_children())
        try:
            student_id = None
            sid_str = self._rec_student_var.get().strip()
            if sid_str:
                student_id = int(sid_str)
            mtype = self._rec_type_var.get() or None
            for r in self._svc.list_records(student_id=student_id, meeting_type=mtype):
                follow = "Yes" if r.get("follow_up_required") else "No"
                self._rec_tree.insert("", "end", values=(
                    r["id"], r["student_id"], r["tutor_id"],
                    r["meeting_date"], r.get("meeting_type") or "1to1",
                    (r.get("targets_set") or "-")[:40], follow))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selected_rec_id(self):
        sel = self._rec_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a record first.")
            return None
        return self._rec_tree.item(sel[0], "values")[0]

    def _new_record(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Tutorial Record")
        dlg.geometry("450x480")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        entries = [
            ("Student ID *:", "student_id"),
            ("Tutor ID *:", "tutor_id"),
            ("Meeting Date * (YYYY-MM-DD):", "meeting_date"),
            ("Session ID (optional):", "session_id"),
            ("Targets Set:", "targets_set"),
        ]
        for i, (label, key) in enumerate(entries):
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=i, column=0, sticky="e", padx=10, pady=4)
            var = tk.StringVar()
            ttk.Entry(dlg, textvariable=var, width=22).grid(row=i, column=1, padx=10, pady=4)
            fields[key] = var

        row_idx = len(entries)
        tk.Label(dlg, text="Type:", bg="#ecf0f1").grid(row=row_idx, column=0, sticky="e", padx=10, pady=4)
        type_var = tk.StringVar(value="1to1")
        ttk.Combobox(dlg, textvariable=type_var, width=19,
                     values=["1to1", "progress_review", "pastoral",
                             "target_setting", "careers", "other"],
                     state="readonly").grid(row=row_idx, column=1, padx=10, pady=4)
        fields["meeting_type"] = type_var

        tk.Label(dlg, text="Discussion Notes:", bg="#ecf0f1").grid(
            row=row_idx + 1, column=0, sticky="ne", padx=10, pady=4)
        notes_text = tk.Text(dlg, width=22, height=3)
        notes_text.grid(row=row_idx + 1, column=1, padx=10, pady=4)

        tk.Label(dlg, text="Student Concerns:", bg="#ecf0f1").grid(
            row=row_idx + 2, column=0, sticky="ne", padx=10, pady=4)
        concerns_text = tk.Text(dlg, width=22, height=2)
        concerns_text.grid(row=row_idx + 2, column=1, padx=10, pady=4)

        follow_var = tk.IntVar(value=0)
        ttk.Checkbutton(dlg, text="Follow-up Required", variable=follow_var
                        ).grid(row=row_idx + 3, column=0, columnspan=2, pady=4)

        tk.Label(dlg, text="Follow-up Notes:", bg="#ecf0f1").grid(
            row=row_idx + 4, column=0, sticky="ne", padx=10, pady=4)
        follow_text = tk.Text(dlg, width=22, height=2)
        follow_text.grid(row=row_idx + 4, column=1, padx=10, pady=4)

        def save():
            try:
                sid = int(fields["student_id"].get())
                tid = int(fields["tutor_id"].get())
                mdate = fields["meeting_date"].get().strip()
                if not mdate:
                    messagebox.showwarning("Warning", "Meeting date is required.")
                    return
                kwargs = {"meeting_type": fields["meeting_type"].get()}
                session_id_str = fields["session_id"].get().strip()
                if session_id_str:
                    kwargs["session_id"] = int(session_id_str)
                targets = fields["targets_set"].get().strip()
                if targets:
                    kwargs["targets_set"] = targets
                notes = notes_text.get("1.0", "end").strip()
                if notes:
                    kwargs["discussion_notes"] = notes
                concerns = concerns_text.get("1.0", "end").strip()
                if concerns:
                    kwargs["student_concerns"] = concerns
                kwargs["follow_up_required"] = follow_var.get()
                fnotes = follow_text.get("1.0", "end").strip()
                if fnotes:
                    kwargs["follow_up_notes"] = fnotes
                self._svc.create_record(sid, tid, mdate, **kwargs)
                messagebox.showinfo("Success", "Record created.")
                dlg.destroy()
                self._load_records()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(dlg, text="Save", command=save).grid(row=row_idx + 5, column=0, columnspan=2, pady=10)

    def _view_record(self):
        rid = self._selected_rec_id()
        if rid is None:
            return
        try:
            r = self._svc.get_record(int(rid))
            if not r:
                messagebox.showwarning("Not Found", "Record not found.")
                return
            dlg = tk.Toplevel(self)
            dlg.title(f"Record #{r['id']}")
            dlg.geometry("500x420")
            dlg.configure(bg="#ecf0f1")
            dlg.transient(self)

            follow = "Yes" if r.get("follow_up_required") else "No"
            info = (
                f"ID: {r['id']}\n"
                f"Student: {r.get('student_first', '')} {r.get('student_last', '')} (ID: {r['student_id']})\n"
                f"Tutor: {r.get('tutor_first', '')} {r.get('tutor_last', '')} (ID: {r['tutor_id']})\n"
                f"Session ID: {r.get('session_id') or '-'}\n"
                f"Date: {r['meeting_date']}\n"
                f"Type: {r.get('meeting_type') or '1to1'}\n"
                f"Discussion Notes: {r.get('discussion_notes') or '-'}\n"
                f"Targets Set: {r.get('targets_set') or '-'}\n"
                f"Student Concerns: {r.get('student_concerns') or '-'}\n"
                f"Follow-up Required: {follow}\n"
                f"Follow-up Notes: {r.get('follow_up_notes') or '-'}\n"
                f"Created: {r.get('created_at') or '-'}"
            )
            tk.Label(dlg, text=info, bg="#ecf0f1", justify="left",
                     font=("Helvetica", 11), wraplength=460).pack(padx=20, pady=20, anchor="w")
            ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=10)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _update_record(self):
        rid = self._selected_rec_id()
        if rid is None:
            return
        try:
            r = self._svc.get_record(int(rid))
            if not r:
                messagebox.showwarning("Not Found", "Record not found.")
                return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Update Record #{r['id']}")
        dlg.geometry("450x440")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        entries = [
            ("Meeting Date:", "meeting_date", r["meeting_date"]),
            ("Targets Set:", "targets_set", r.get("targets_set") or ""),
        ]
        for i, (label, key, default) in enumerate(entries):
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=i, column=0, sticky="e", padx=10, pady=4)
            var = tk.StringVar(value=default)
            ttk.Entry(dlg, textvariable=var, width=22).grid(row=i, column=1, padx=10, pady=4)
            fields[key] = var

        row_idx = len(entries)
        tk.Label(dlg, text="Type:", bg="#ecf0f1").grid(row=row_idx, column=0, sticky="e", padx=10, pady=4)
        type_var = tk.StringVar(value=r.get("meeting_type") or "1to1")
        ttk.Combobox(dlg, textvariable=type_var, width=19,
                     values=["1to1", "progress_review", "pastoral",
                             "target_setting", "careers", "other"],
                     state="readonly").grid(row=row_idx, column=1, padx=10, pady=4)
        fields["meeting_type"] = type_var

        tk.Label(dlg, text="Discussion Notes:", bg="#ecf0f1").grid(
            row=row_idx + 1, column=0, sticky="ne", padx=10, pady=4)
        notes_text = tk.Text(dlg, width=22, height=3)
        notes_text.insert("1.0", r.get("discussion_notes") or "")
        notes_text.grid(row=row_idx + 1, column=1, padx=10, pady=4)

        tk.Label(dlg, text="Student Concerns:", bg="#ecf0f1").grid(
            row=row_idx + 2, column=0, sticky="ne", padx=10, pady=4)
        concerns_text = tk.Text(dlg, width=22, height=2)
        concerns_text.insert("1.0", r.get("student_concerns") or "")
        concerns_text.grid(row=row_idx + 2, column=1, padx=10, pady=4)

        follow_var = tk.IntVar(value=1 if r.get("follow_up_required") else 0)
        ttk.Checkbutton(dlg, text="Follow-up Required", variable=follow_var
                        ).grid(row=row_idx + 3, column=0, columnspan=2, pady=4)

        tk.Label(dlg, text="Follow-up Notes:", bg="#ecf0f1").grid(
            row=row_idx + 4, column=0, sticky="ne", padx=10, pady=4)
        follow_text = tk.Text(dlg, width=22, height=2)
        follow_text.insert("1.0", r.get("follow_up_notes") or "")
        follow_text.grid(row=row_idx + 4, column=1, padx=10, pady=4)

        def save():
            try:
                updates = {}
                for key, var in fields.items():
                    val = var.get().strip()
                    if val:
                        updates[key] = val
                notes = notes_text.get("1.0", "end").strip()
                if notes:
                    updates["discussion_notes"] = notes
                concerns = concerns_text.get("1.0", "end").strip()
                if concerns:
                    updates["student_concerns"] = concerns
                updates["follow_up_required"] = follow_var.get()
                fnotes = follow_text.get("1.0", "end").strip()
                if fnotes:
                    updates["follow_up_notes"] = fnotes
                if updates:
                    self._svc.update_record(int(rid), **updates)
                    messagebox.showinfo("Success", "Record updated.")
                    dlg.destroy()
                    self._load_records()
                else:
                    messagebox.showwarning("Warning", "No changes to save.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(dlg, text="Save", command=save).grid(row=row_idx + 5, column=0, columnspan=2, pady=10)

    def _delete_record(self):
        rid = self._selected_rec_id()
        if rid is None:
            return
        if not messagebox.askyesno("Confirm", "Delete this record?"):
            return
        try:
            self._svc.delete_record(int(rid))
            messagebox.showinfo("Success", "Record deleted.")
            self._load_records()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _show_follow_ups(self):
        dlg = tk.Toplevel(self)
        dlg.title("Follow-Ups Due")
        dlg.geometry("650x400")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)

        cols = ("id", "student", "tutor", "date", "type", "follow_up_notes")
        tree = ttk.Treeview(dlg, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("student", "Student", 120),
                         ("tutor", "Tutor", 120), ("date", "Date", 90),
                         ("type", "Type", 100), ("follow_up_notes", "Follow-Up Notes", 180)]:
            tree.heading(c, text=h)
            tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(dlg, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        vsb.pack(side="left", fill="y", pady=10)

        try:
            for r in self._svc.get_follow_ups():
                student = f"{r.get('student_first', '')} {r.get('student_last', '')}".strip() or str(r['student_id'])
                tutor = f"{r.get('tutor_first', '')} {r.get('tutor_last', '')}".strip() or str(r['tutor_id'])
                tree.insert("", "end", values=(
                    r["id"], student, tutor, r["meeting_date"],
                    r.get("meeting_type") or "1to1",
                    (r.get("follow_up_notes") or "-")[:50]))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Statistics Tab ─────────────────────────────────────────────────

    def _build_stats_tab(self):
        self._stats_tab = tk.Frame(self._nb, bg="#ecf0f1", padx=20, pady=20)
        self._nb.add(self._stats_tab, text="Statistics")

        self._stats_labels = {}
        stat_items = [
            ("total_assignments", "Total Assignments:"),
            ("active_assignments", "Active Assignments:"),
            ("tutor_groups_count", "Tutor Groups:"),
            ("total_sessions", "Total Sessions:"),
            ("completed_sessions", "Completed Sessions:"),
            ("by_session_type", "Sessions by Type:"),
            ("total_records", "Total Records:"),
            ("by_meeting_type", "Records by Meeting Type:"),
            ("follow_ups_pending", "Follow-Ups Pending:"),
        ]
        for i, (key, label) in enumerate(stat_items):
            tk.Label(self._stats_tab, text=label, bg="#ecf0f1",
                     font=("Helvetica", 11, "bold"), anchor="e"
                     ).grid(row=i, column=0, sticky="e", padx=(0, 10), pady=4)
            lbl = tk.Label(self._stats_tab, text="-", bg="#ecf0f1",
                           font=("Helvetica", 11), anchor="w")
            lbl.grid(row=i, column=1, sticky="w", pady=4)
            self._stats_labels[key] = lbl

        ttk.Button(self._stats_tab, text="Refresh Stats",
                   command=self._load_stats).grid(row=len(stat_items), column=0,
                                                   columnspan=2, pady=15)

    def _load_stats(self):
        try:
            stats = self._svc.get_stats()
            self._stats_labels["total_assignments"].config(text=str(stats["total_assignments"]))
            self._stats_labels["active_assignments"].config(text=str(stats["active_assignments"]))
            self._stats_labels["tutor_groups_count"].config(text=str(stats["tutor_groups_count"]))
            self._stats_labels["total_sessions"].config(text=str(stats["total_sessions"]))
            self._stats_labels["completed_sessions"].config(text=str(stats["completed_sessions"]))

            st = stats.get("by_session_type", {})
            st_text = ", ".join(f"{k}: {v}" for k, v in st.items()) if st else "None"
            self._stats_labels["by_session_type"].config(text=st_text)

            self._stats_labels["total_records"].config(text=str(stats["total_records"]))

            mt = stats.get("by_meeting_type", {})
            mt_text = ", ".join(f"{k}: {v}" for k, v in mt.items()) if mt else "None"
            self._stats_labels["by_meeting_type"].config(text=mt_text)

            self._stats_labels["follow_ups_pending"].config(text=str(stats["follow_ups_pending"]))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Public refresh ─────────────────────────────────────────────────

    def refresh(self):
        self._load_assignments()
        self._load_sessions()
        self._load_records()
        self._load_stats()
