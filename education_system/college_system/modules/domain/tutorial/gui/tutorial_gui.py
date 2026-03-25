"""Tutorial System GUI module."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.core.i18n import t
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
        tk.Label(header, text=t("tutorial.management"),
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_assignments_tab()
        self._build_sessions_tab()
        self._build_records_tab()
        self._build_stats_tab()

    # -- Assignments Tab --

    def _build_assignments_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("tutorial.assignments"))

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))
        tk.Label(filt, text=t("common.status") + ":", bg="#ecf0f1").pack(side="left")
        self._asgn_status_var = tk.StringVar(value="")
        ttk.Combobox(filt, textvariable=self._asgn_status_var, width=12,
                     values=["", "active", "ended", "transferred"],
                     state="readonly").pack(side="left", padx=5)
        tk.Label(filt, text=t("tutorial.group") + ":", bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._asgn_group_var = tk.StringVar(value="")
        ttk.Entry(filt, textvariable=self._asgn_group_var, width=12).pack(side="left", padx=5)
        ttk.Button(filt, text=t("common.filter"), command=self._load_assignments).pack(side="left", padx=5)

        # Treeview
        cols = ("id", "student_id", "tutor_id", "academic_year", "tutor_group", "status")
        self._asgn_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", t("common.id"), 40), ("student_id", t("common.student_id"), 80),
                         ("tutor_id", t("tutorial.tutor_id"), 80),
                         ("academic_year", t("tutorial.academic_year"), 100),
                         ("tutor_group", t("tutorial.tutor_group"), 100),
                         ("status", t("common.status"), 80)]:
            self._asgn_tree.heading(c, text=h)
            self._asgn_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._asgn_tree.yview)
        self._asgn_tree.configure(yscrollcommand=vsb.set)
        self._asgn_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        # Buttons
        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(side="right", fill="y", padx=(10, 0))
        for txt, cmd in [(t("common.new"), self._new_assignment),
                          (t("common.view"), self._view_assignment),
                          (t("common.update"), self._update_assignment),
                          (t("tutorial.end"), self._end_assignment),
                          (t("common.delete"), self._delete_assignment)]:
            ttk.Button(btn_frame, text=txt, command=cmd, width=12).pack(pady=3)
        ttk.Button(btn_frame, text="Export CSV", command=self._export_csv, width=12).pack(pady=3)

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._asgn_tree, "tutorial.csv")

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
            messagebox.showerror(t("common.error"), str(e))

    def _selected_asgn_id(self):
        sel = self._asgn_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"))
            return None
        return self._asgn_tree.item(sel[0], "values")[0]

    def _new_assignment(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("tutorial.new_assignment"))
        dlg.geometry("350x260")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        for i, (label, key) in enumerate([
            (t("common.student_id") + " *:", "student_id"),
            (t("tutorial.tutor_id") + " *:", "tutor_id"),
            (t("tutorial.academic_year") + ":", "academic_year"),
            (t("tutorial.tutor_group") + ":", "tutor_group"),
        ]):
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=i, column=0, sticky="e", padx=10, pady=5)
            var = tk.StringVar()
            ttk.Entry(dlg, textvariable=var, width=20).grid(row=i, column=1, padx=10, pady=5)
            fields[key] = var

        tk.Label(dlg, text=t("common.status") + ":", bg="#ecf0f1").grid(row=4, column=0, sticky="e", padx=10, pady=5)
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
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                dlg.destroy()
                self._load_assignments()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("common.save"), command=save).grid(row=5, column=0, columnspan=2, pady=15)

    def _view_assignment(self):
        aid = self._selected_asgn_id()
        if aid is None:
            return
        try:
            r = self._svc.get_assignment(int(aid))
            if not r:
                messagebox.showwarning(t("common.warning"), t("common.no_data"))
                return
            dlg = tk.Toplevel(self)
            dlg.title(f"{t('tutorial.assignment')} #{r['id']}")
            dlg.geometry("400x300")
            dlg.configure(bg="#ecf0f1")
            dlg.transient(self)

            info = (
                f"{t('common.id')}: {r['id']}\n"
                f"{t('tutorial.student')}: {r.get('student_first', '')} {r.get('student_last', '')} ({t('common.id')}: {r['student_id']})\n"
                f"{t('tutorial.tutor')}: {r.get('tutor_first', '')} {r.get('tutor_last', '')} ({t('common.id')}: {r['tutor_id']})\n"
                f"{t('tutorial.academic_year')}: {r.get('academic_year') or '-'}\n"
                f"{t('tutorial.tutor_group')}: {r.get('tutor_group') or '-'}\n"
                f"{t('common.status')}: {r['status']}\n"
                f"{t('common.created_at')}: {r.get('created_at') or '-'}"
            )
            tk.Label(dlg, text=info, bg="#ecf0f1", justify="left",
                     font=("Helvetica", 11)).pack(padx=20, pady=20, anchor="w")
            ttk.Button(dlg, text=t("common.close"), command=dlg.destroy).pack(pady=10)
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _update_assignment(self):
        aid = self._selected_asgn_id()
        if aid is None:
            return
        try:
            r = self._svc.get_assignment(int(aid))
            if not r:
                messagebox.showwarning(t("common.warning"), t("common.no_data"))
                return
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"{t('tutorial.update_assignment')} #{r['id']}")
        dlg.geometry("350x260")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        defaults = [
            (t("tutorial.academic_year") + ":", "academic_year", r.get("academic_year") or ""),
            (t("tutorial.tutor_group") + ":", "tutor_group", r.get("tutor_group") or ""),
        ]
        for i, (label, key, default) in enumerate(defaults):
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=i, column=0, sticky="e", padx=10, pady=5)
            var = tk.StringVar(value=default)
            ttk.Entry(dlg, textvariable=var, width=20).grid(row=i, column=1, padx=10, pady=5)
            fields[key] = var

        tk.Label(dlg, text=t("common.status") + ":", bg="#ecf0f1").grid(row=2, column=0, sticky="e", padx=10, pady=5)
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
                    messagebox.showinfo(t("common.success"), t("common.updated_success"))
                    dlg.destroy()
                    self._load_assignments()
                else:
                    messagebox.showwarning(t("common.warning"), t("tutorial.no_changes"))
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("common.save"), command=save).grid(row=3, column=0, columnspan=2, pady=15)

    def _end_assignment(self):
        aid = self._selected_asgn_id()
        if aid is None:
            return
        if not messagebox.askyesno(t("common.confirm"), t("tutorial.end_assignment_confirm")):
            return
        try:
            self._svc.end_assignment(int(aid))
            messagebox.showinfo(t("common.success"), t("tutorial.assignment_ended"))
            self._load_assignments()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _delete_assignment(self):
        aid = self._selected_asgn_id()
        if aid is None:
            return
        if not messagebox.askyesno(t("common.confirm"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_assignment(int(aid))
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_assignments()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # -- Sessions Tab --

    def _build_sessions_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("tutorial.sessions"))

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))
        tk.Label(filt, text=t("common.status") + ":", bg="#ecf0f1").pack(side="left")
        self._sess_status_var = tk.StringVar(value="")
        ttk.Combobox(filt, textvariable=self._sess_status_var, width=12,
                     values=["", "scheduled", "completed", "cancelled"],
                     state="readonly").pack(side="left", padx=5)
        tk.Label(filt, text=t("common.type") + ":", bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._sess_type_var = tk.StringVar(value="")
        ttk.Combobox(filt, textvariable=self._sess_type_var, width=12,
                     values=["", "group", "1to1", "assembly", "enrichment", "careers"],
                     state="readonly").pack(side="left", padx=5)
        tk.Label(filt, text=t("tutorial.group") + ":", bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._sess_group_var = tk.StringVar(value="")
        ttk.Entry(filt, textvariable=self._sess_group_var, width=12).pack(side="left", padx=5)
        ttk.Button(filt, text=t("common.filter"), command=self._load_sessions).pack(side="left", padx=5)

        # Treeview
        cols = ("id", "tutor_id", "tutor_group", "session_date", "session_type", "topic", "status")
        self._sess_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", t("common.id"), 40), ("tutor_id", t("tutorial.tutor_id"), 70),
                         ("tutor_group", t("tutorial.group"), 80),
                         ("session_date", t("common.date"), 90),
                         ("session_type", t("common.type"), 80),
                         ("topic", t("tutorial.topic"), 160),
                         ("status", t("common.status"), 80)]:
            self._sess_tree.heading(c, text=h)
            self._sess_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._sess_tree.yview)
        self._sess_tree.configure(yscrollcommand=vsb.set)
        self._sess_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        # Buttons
        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(side="right", fill="y", padx=(10, 0))
        for txt, cmd in [(t("common.new"), self._new_session),
                          (t("common.view"), self._view_session),
                          (t("common.update"), self._update_session),
                          (t("common.completed"), self._complete_session),
                          (t("common.delete"), self._delete_session)]:
            ttk.Button(btn_frame, text=txt, command=cmd, width=12).pack(pady=3)

    def _load_sessions(self):
        self._sess_tree.delete(*self._sess_tree.get_children())
        try:
            status = self._sess_status_var.get() or None
            group = self._sess_group_var.get().strip() or None
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
            messagebox.showerror(t("common.error"), str(e))

    def _selected_sess_id(self):
        sel = self._sess_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"))
            return None
        return self._sess_tree.item(sel[0], "values")[0]

    def _new_session(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("tutorial.new_session"))
        dlg.geometry("400x350")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        entries = [
            (t("tutorial.tutor_id") + " *:", "tutor_id"),
            (t("tutorial.session_date") + " *:", "session_date"),
            (t("tutorial.tutor_group") + ":", "tutor_group"),
            (t("tutorial.topic") + ":", "topic"),
            (t("tutorial.resources") + ":", "resources"),
        ]
        for i, (label, key) in enumerate(entries):
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=i, column=0, sticky="e", padx=10, pady=5)
            var = tk.StringVar()
            ttk.Entry(dlg, textvariable=var, width=22).grid(row=i, column=1, padx=10, pady=5)
            fields[key] = var

        row_idx = len(entries)
        tk.Label(dlg, text=t("common.type") + ":", bg="#ecf0f1").grid(row=row_idx, column=0, sticky="e", padx=10, pady=5)
        type_var = tk.StringVar(value="group")
        ttk.Combobox(dlg, textvariable=type_var, width=19,
                     values=["group", "1to1", "assembly", "enrichment", "careers"],
                     state="readonly").grid(row=row_idx, column=1, padx=10, pady=5)
        fields["session_type"] = type_var

        tk.Label(dlg, text=t("common.notes") + ":", bg="#ecf0f1").grid(row=row_idx + 1, column=0, sticky="ne", padx=10, pady=5)
        notes_text = tk.Text(dlg, width=22, height=3)
        notes_text.grid(row=row_idx + 1, column=1, padx=10, pady=5)

        def save():
            try:
                tid = int(fields["tutor_id"].get())
                sdate = fields["session_date"].get().strip()
                if not sdate:
                    messagebox.showwarning(t("common.validation"), t("common.field_required"))
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
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                dlg.destroy()
                self._load_sessions()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("common.save"), command=save).grid(row=row_idx + 2, column=0, columnspan=2, pady=10)

    def _view_session(self):
        sid = self._selected_sess_id()
        if sid is None:
            return
        try:
            r = self._svc.get_session(int(sid))
            if not r:
                messagebox.showwarning(t("common.warning"), t("common.no_data"))
                return
            dlg = tk.Toplevel(self)
            dlg.title(f"{t('tutorial.session')} #{r['id']}")
            dlg.geometry("450x350")
            dlg.configure(bg="#ecf0f1")
            dlg.transient(self)

            info = (
                f"{t('common.id')}: {r['id']}\n"
                f"{t('tutorial.tutor')}: {r.get('tutor_first', '')} {r.get('tutor_last', '')} ({t('common.id')}: {r['tutor_id']})\n"
                f"{t('tutorial.group')}: {r.get('tutor_group') or '-'}\n"
                f"{t('common.date')}: {r['session_date']}\n"
                f"{t('common.type')}: {r.get('session_type') or 'group'}\n"
                f"{t('tutorial.topic')}: {r.get('topic') or '-'}\n"
                f"{t('tutorial.resources')}: {r.get('resources') or '-'}\n"
                f"{t('common.status')}: {r['status']}\n"
                f"{t('common.notes')}: {r.get('notes') or '-'}\n"
                f"{t('common.created_at')}: {r.get('created_at') or '-'}"
            )
            tk.Label(dlg, text=info, bg="#ecf0f1", justify="left",
                     font=("Helvetica", 11)).pack(padx=20, pady=20, anchor="w")
            ttk.Button(dlg, text=t("common.close"), command=dlg.destroy).pack(pady=10)
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _update_session(self):
        sid = self._selected_sess_id()
        if sid is None:
            return
        try:
            r = self._svc.get_session(int(sid))
            if not r:
                messagebox.showwarning(t("common.warning"), t("common.no_data"))
                return
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"{t('tutorial.update_session')} #{r['id']}")
        dlg.geometry("400x350")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        entries = [
            (t("tutorial.session_date") + ":", "session_date", r["session_date"]),
            (t("tutorial.tutor_group") + ":", "tutor_group", r.get("tutor_group") or ""),
            (t("tutorial.topic") + ":", "topic", r.get("topic") or ""),
            (t("tutorial.resources") + ":", "resources", r.get("resources") or ""),
        ]
        for i, (label, key, default) in enumerate(entries):
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=i, column=0, sticky="e", padx=10, pady=5)
            var = tk.StringVar(value=default)
            ttk.Entry(dlg, textvariable=var, width=22).grid(row=i, column=1, padx=10, pady=5)
            fields[key] = var

        row_idx = len(entries)
        tk.Label(dlg, text=t("common.type") + ":", bg="#ecf0f1").grid(row=row_idx, column=0, sticky="e", padx=10, pady=5)
        type_var = tk.StringVar(value=r.get("session_type") or "group")
        ttk.Combobox(dlg, textvariable=type_var, width=19,
                     values=["group", "1to1", "assembly", "enrichment", "careers"],
                     state="readonly").grid(row=row_idx, column=1, padx=10, pady=5)
        fields["session_type"] = type_var

        tk.Label(dlg, text=t("common.status") + ":", bg="#ecf0f1").grid(row=row_idx + 1, column=0, sticky="e", padx=10, pady=5)
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
                    messagebox.showinfo(t("common.success"), t("common.updated_success"))
                    dlg.destroy()
                    self._load_sessions()
                else:
                    messagebox.showwarning(t("common.warning"), t("tutorial.no_changes"))
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("common.save"), command=save).grid(row=row_idx + 2, column=0, columnspan=2, pady=10)

    def _complete_session(self):
        sid = self._selected_sess_id()
        if sid is None:
            return
        if not messagebox.askyesno(t("common.confirm"), t("tutorial.complete_session_confirm")):
            return
        try:
            self._svc.complete_session(int(sid))
            messagebox.showinfo(t("common.success"), t("tutorial.session_completed"))
            self._load_sessions()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _delete_session(self):
        sid = self._selected_sess_id()
        if sid is None:
            return
        if not messagebox.askyesno(t("common.confirm"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_session(int(sid))
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_sessions()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # -- Records Tab --

    def _build_records_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("tutorial.records"))

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))
        tk.Label(filt, text=t("common.student_id") + ":", bg="#ecf0f1").pack(side="left")
        self._rec_student_var = tk.StringVar(value="")
        ttk.Entry(filt, textvariable=self._rec_student_var, width=8).pack(side="left", padx=5)
        tk.Label(filt, text=t("common.type") + ":", bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._rec_type_var = tk.StringVar(value="")
        ttk.Combobox(filt, textvariable=self._rec_type_var, width=14,
                     values=["", "1to1", "progress_review", "pastoral",
                             "target_setting", "careers", "other"],
                     state="readonly").pack(side="left", padx=5)
        ttk.Button(filt, text=t("common.filter"), command=self._load_records).pack(side="left", padx=5)

        # Treeview
        cols = ("id", "student_id", "tutor_id", "meeting_date", "meeting_type",
                "targets_set", "follow_up")
        self._rec_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", t("common.id"), 40), ("student_id", t("common.student_id"), 80),
                         ("tutor_id", t("tutorial.tutor_id"), 70),
                         ("meeting_date", t("common.date"), 90),
                         ("meeting_type", t("common.type"), 110),
                         ("targets_set", t("tutorial.targets"), 150),
                         ("follow_up", t("tutorial.follow_up"), 70)]:
            self._rec_tree.heading(c, text=h)
            self._rec_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._rec_tree.yview)
        self._rec_tree.configure(yscrollcommand=vsb.set)
        self._rec_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        # Buttons
        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(side="right", fill="y", padx=(10, 0))
        for txt, cmd in [(t("common.new"), self._new_record),
                          (t("common.view"), self._view_record),
                          (t("common.update"), self._update_record),
                          (t("common.delete"), self._delete_record),
                          (t("tutorial.follow_ups"), self._show_follow_ups)]:
            ttk.Button(btn_frame, text=txt, command=cmd, width=12).pack(pady=3)

    def _load_records(self):
        self._rec_tree.delete(*self._rec_tree.get_children())
        try:
            student_id = None
            sid_str = self._rec_student_var.get().strip()
            if sid_str:
                student_id = int(sid_str)
            mtype = self._rec_type_var.get() or None
            for r in self._svc.list_records(student_id=student_id, meeting_type=mtype):
                follow = t("common.yes") if r.get("follow_up_required") else t("common.no")
                self._rec_tree.insert("", "end", values=(
                    r["id"], r["student_id"], r["tutor_id"],
                    r["meeting_date"], r.get("meeting_type") or "1to1",
                    (r.get("targets_set") or "-")[:40], follow))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _selected_rec_id(self):
        sel = self._rec_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"))
            return None
        return self._rec_tree.item(sel[0], "values")[0]

    def _new_record(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("tutorial.new_record"))
        dlg.geometry("450x480")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        entries = [
            (t("common.student_id") + " *:", "student_id"),
            (t("tutorial.tutor_id") + " *:", "tutor_id"),
            (t("tutorial.meeting_date") + " *:", "meeting_date"),
            (t("tutorial.session_id") + ":", "session_id"),
            (t("tutorial.targets_set") + ":", "targets_set"),
        ]
        for i, (label, key) in enumerate(entries):
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=i, column=0, sticky="e", padx=10, pady=4)
            var = tk.StringVar()
            ttk.Entry(dlg, textvariable=var, width=22).grid(row=i, column=1, padx=10, pady=4)
            fields[key] = var

        row_idx = len(entries)
        tk.Label(dlg, text=t("common.type") + ":", bg="#ecf0f1").grid(row=row_idx, column=0, sticky="e", padx=10, pady=4)
        type_var = tk.StringVar(value="1to1")
        ttk.Combobox(dlg, textvariable=type_var, width=19,
                     values=["1to1", "progress_review", "pastoral",
                             "target_setting", "careers", "other"],
                     state="readonly").grid(row=row_idx, column=1, padx=10, pady=4)
        fields["meeting_type"] = type_var

        tk.Label(dlg, text=t("tutorial.discussion_notes") + ":", bg="#ecf0f1").grid(
            row=row_idx + 1, column=0, sticky="ne", padx=10, pady=4)
        notes_text = tk.Text(dlg, width=22, height=3)
        notes_text.grid(row=row_idx + 1, column=1, padx=10, pady=4)

        tk.Label(dlg, text=t("tutorial.student_concerns") + ":", bg="#ecf0f1").grid(
            row=row_idx + 2, column=0, sticky="ne", padx=10, pady=4)
        concerns_text = tk.Text(dlg, width=22, height=2)
        concerns_text.grid(row=row_idx + 2, column=1, padx=10, pady=4)

        follow_var = tk.IntVar(value=0)
        ttk.Checkbutton(dlg, text=t("tutorial.follow_up_required"), variable=follow_var
                        ).grid(row=row_idx + 3, column=0, columnspan=2, pady=4)

        tk.Label(dlg, text=t("tutorial.follow_up_notes") + ":", bg="#ecf0f1").grid(
            row=row_idx + 4, column=0, sticky="ne", padx=10, pady=4)
        follow_text = tk.Text(dlg, width=22, height=2)
        follow_text.grid(row=row_idx + 4, column=1, padx=10, pady=4)

        def save():
            try:
                sid = int(fields["student_id"].get())
                tid = int(fields["tutor_id"].get())
                mdate = fields["meeting_date"].get().strip()
                if not mdate:
                    messagebox.showwarning(t("common.validation"), t("common.field_required"))
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
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                dlg.destroy()
                self._load_records()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("common.save"), command=save).grid(row=row_idx + 5, column=0, columnspan=2, pady=10)

    def _view_record(self):
        rid = self._selected_rec_id()
        if rid is None:
            return
        try:
            r = self._svc.get_record(int(rid))
            if not r:
                messagebox.showwarning(t("common.warning"), t("common.no_data"))
                return
            dlg = tk.Toplevel(self)
            dlg.title(f"{t('tutorial.record')} #{r['id']}")
            dlg.geometry("500x420")
            dlg.configure(bg="#ecf0f1")
            dlg.transient(self)

            follow = t("common.yes") if r.get("follow_up_required") else t("common.no")
            info = (
                f"{t('common.id')}: {r['id']}\n"
                f"{t('tutorial.student')}: {r.get('student_first', '')} {r.get('student_last', '')} ({t('common.id')}: {r['student_id']})\n"
                f"{t('tutorial.tutor')}: {r.get('tutor_first', '')} {r.get('tutor_last', '')} ({t('common.id')}: {r['tutor_id']})\n"
                f"{t('tutorial.session_id')}: {r.get('session_id') or '-'}\n"
                f"{t('common.date')}: {r['meeting_date']}\n"
                f"{t('common.type')}: {r.get('meeting_type') or '1to1'}\n"
                f"{t('tutorial.discussion_notes')}: {r.get('discussion_notes') or '-'}\n"
                f"{t('tutorial.targets_set')}: {r.get('targets_set') or '-'}\n"
                f"{t('tutorial.student_concerns')}: {r.get('student_concerns') or '-'}\n"
                f"{t('tutorial.follow_up_required')}: {follow}\n"
                f"{t('tutorial.follow_up_notes')}: {r.get('follow_up_notes') or '-'}\n"
                f"{t('common.created_at')}: {r.get('created_at') or '-'}"
            )
            tk.Label(dlg, text=info, bg="#ecf0f1", justify="left",
                     font=("Helvetica", 11), wraplength=460).pack(padx=20, pady=20, anchor="w")
            ttk.Button(dlg, text=t("common.close"), command=dlg.destroy).pack(pady=10)
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _update_record(self):
        rid = self._selected_rec_id()
        if rid is None:
            return
        try:
            r = self._svc.get_record(int(rid))
            if not r:
                messagebox.showwarning(t("common.warning"), t("common.no_data"))
                return
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"{t('tutorial.update_record')} #{r['id']}")
        dlg.geometry("450x440")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        entries = [
            (t("tutorial.meeting_date") + ":", "meeting_date", r["meeting_date"]),
            (t("tutorial.targets_set") + ":", "targets_set", r.get("targets_set") or ""),
        ]
        for i, (label, key, default) in enumerate(entries):
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=i, column=0, sticky="e", padx=10, pady=4)
            var = tk.StringVar(value=default)
            ttk.Entry(dlg, textvariable=var, width=22).grid(row=i, column=1, padx=10, pady=4)
            fields[key] = var

        row_idx = len(entries)
        tk.Label(dlg, text=t("common.type") + ":", bg="#ecf0f1").grid(row=row_idx, column=0, sticky="e", padx=10, pady=4)
        type_var = tk.StringVar(value=r.get("meeting_type") or "1to1")
        ttk.Combobox(dlg, textvariable=type_var, width=19,
                     values=["1to1", "progress_review", "pastoral",
                             "target_setting", "careers", "other"],
                     state="readonly").grid(row=row_idx, column=1, padx=10, pady=4)
        fields["meeting_type"] = type_var

        tk.Label(dlg, text=t("tutorial.discussion_notes") + ":", bg="#ecf0f1").grid(
            row=row_idx + 1, column=0, sticky="ne", padx=10, pady=4)
        notes_text = tk.Text(dlg, width=22, height=3)
        notes_text.insert("1.0", r.get("discussion_notes") or "")
        notes_text.grid(row=row_idx + 1, column=1, padx=10, pady=4)

        tk.Label(dlg, text=t("tutorial.student_concerns") + ":", bg="#ecf0f1").grid(
            row=row_idx + 2, column=0, sticky="ne", padx=10, pady=4)
        concerns_text = tk.Text(dlg, width=22, height=2)
        concerns_text.insert("1.0", r.get("student_concerns") or "")
        concerns_text.grid(row=row_idx + 2, column=1, padx=10, pady=4)

        follow_var = tk.IntVar(value=1 if r.get("follow_up_required") else 0)
        ttk.Checkbutton(dlg, text=t("tutorial.follow_up_required"), variable=follow_var
                        ).grid(row=row_idx + 3, column=0, columnspan=2, pady=4)

        tk.Label(dlg, text=t("tutorial.follow_up_notes") + ":", bg="#ecf0f1").grid(
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
                    messagebox.showinfo(t("common.success"), t("common.updated_success"))
                    dlg.destroy()
                    self._load_records()
                else:
                    messagebox.showwarning(t("common.warning"), t("tutorial.no_changes"))
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("common.save"), command=save).grid(row=row_idx + 5, column=0, columnspan=2, pady=10)

    def _delete_record(self):
        rid = self._selected_rec_id()
        if rid is None:
            return
        if not messagebox.askyesno(t("common.confirm"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_record(int(rid))
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_records()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _show_follow_ups(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("tutorial.follow_ups_due"))
        dlg.geometry("650x400")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)

        cols = ("id", "student", "tutor", "date", "type", "follow_up_notes")
        tree = ttk.Treeview(dlg, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", t("common.id"), 40), ("student", t("tutorial.student"), 120),
                         ("tutor", t("tutorial.tutor"), 120), ("date", t("common.date"), 90),
                         ("type", t("common.type"), 100),
                         ("follow_up_notes", t("tutorial.follow_up_notes"), 180)]:
            tree.heading(c, text=h)
            tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(dlg, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        vsb.pack(side="left", fill="y", pady=10)

        try:
            for r in self._svc.get_follow_ups():
                student = f"{r.get('student_first', '')} {r.get('student_last', '')}".strip() or str(r['student_id'])
                tutor_name = f"{r.get('tutor_first', '')} {r.get('tutor_last', '')}".strip() or str(r['tutor_id'])
                tree.insert("", "end", values=(
                    r["id"], student, tutor_name, r["meeting_date"],
                    r.get("meeting_type") or "1to1",
                    (r.get("follow_up_notes") or "-")[:50]))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # -- Statistics Tab --

    def _build_stats_tab(self):
        self._stats_tab = tk.Frame(self._nb, bg="#ecf0f1", padx=20, pady=20)
        self._nb.add(self._stats_tab, text=t("common.summary"))

        self._stats_labels = {}
        stat_items = [
            ("total_assignments", t("tutorial.total_assignments") + ":"),
            ("active_assignments", t("tutorial.active_assignments") + ":"),
            ("tutor_groups_count", t("tutorial.tutor_groups") + ":"),
            ("total_sessions", t("tutorial.total_sessions") + ":"),
            ("completed_sessions", t("tutorial.completed_sessions") + ":"),
            ("by_session_type", t("tutorial.sessions_by_type") + ":"),
            ("total_records", t("tutorial.total_records") + ":"),
            ("by_meeting_type", t("tutorial.records_by_type") + ":"),
            ("follow_ups_pending", t("tutorial.follow_ups_pending") + ":"),
        ]
        for i, (key, label) in enumerate(stat_items):
            tk.Label(self._stats_tab, text=label, bg="#ecf0f1",
                     font=("Helvetica", 11, "bold"), anchor="e"
                     ).grid(row=i, column=0, sticky="e", padx=(0, 10), pady=4)
            lbl = tk.Label(self._stats_tab, text="-", bg="#ecf0f1",
                           font=("Helvetica", 11), anchor="w")
            lbl.grid(row=i, column=1, sticky="w", pady=4)
            self._stats_labels[key] = lbl

        ttk.Button(self._stats_tab, text=t("common.refresh"),
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
            st_text = ", ".join(f"{k}: {v}" for k, v in st.items()) if st else t("common.none")
            self._stats_labels["by_session_type"].config(text=st_text)

            self._stats_labels["total_records"].config(text=str(stats["total_records"]))

            mt = stats.get("by_meeting_type", {})
            mt_text = ", ".join(f"{k}: {v}" for k, v in mt.items()) if mt else t("common.none")
            self._stats_labels["by_meeting_type"].config(text=mt_text)

            self._stats_labels["follow_ups_pending"].config(text=str(stats["follow_ups_pending"]))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # -- Public refresh --

    def refresh(self):
        self._load_assignments()
        self._load_sessions()
        self._load_records()
        self._load_stats()
