"""Student Council GUI module."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.core.i18n import t
from education_system.college_system.modules.domain.student_council.services.student_council_service import (
    StudentCouncilService,
)


class StudentCouncilFrame(tk.Frame):
    """Student Council management frame with Members, Meetings, Proposals, and Statistics tabs."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self.svc = StudentCouncilService(db_path)
        self._build_ui()

    # -- UI construction --

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("student_council.management"),
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_members_tab()
        self._build_meetings_tab()
        self._build_proposals_tab()
        self._build_stats_tab()

    # -- Members tab --

    def _build_members_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("student_council.members"))

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))

        tk.Label(filt, text=t("common.status") + ":", bg="#ecf0f1").pack(side="left")
        self._mem_status_var = tk.StringVar(value="")
        mem_status_cb = ttk.Combobox(filt, textvariable=self._mem_status_var, width=12,
                                     values=["", "active", "resigned", "removed", "term_ended"],
                                     state="readonly")
        mem_status_cb.pack(side="left", padx=(2, 10))

        tk.Label(filt, text=t("student_council.role") + ":", bg="#ecf0f1").pack(side="left")
        self._mem_role_var = tk.StringVar(value="")
        mem_role_cb = ttk.Combobox(filt, textvariable=self._mem_role_var, width=14,
                                   values=["", "representative", "chair", "vice_chair",
                                           "secretary", "treasurer", "welfare_officer"],
                                   state="readonly")
        mem_role_cb.pack(side="left", padx=(2, 10))

        ttk.Button(filt, text=t("common.filter"), command=self._load_members).pack(side="left")

        # Treeview
        cols = ("id", "student_id", "role", "year_group", "department",
                "elected", "term_end", "status")
        self._mem_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", t("common.id"), 40), ("student_id", t("common.student_id"), 70),
                         ("role", t("student_council.role"), 100),
                         ("year_group", t("student_council.year_group"), 80),
                         ("department", t("student_council.department"), 100),
                         ("elected", t("student_council.elected"), 90),
                         ("term_end", t("student_council.term_end"), 90),
                         ("status", t("common.status"), 80)]:
            self._mem_tree.heading(c, text=h)
            self._mem_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._mem_tree.yview)
        self._mem_tree.configure(yscrollcommand=vsb.set)
        self._mem_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Buttons
        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(5, 0))
        for txt, cmd in [(t("common.new"), self._new_member),
                          (t("common.view"), self._view_member),
                          (t("common.update"), self._update_member),
                          (t("student_council.end_term"), self._end_term_member),
                          (t("common.delete"), self._delete_member)]:
            ttk.Button(btn_frame, text=txt, command=cmd).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Export CSV", command=self._export_members_csv).pack(side="left", padx=2)

    # -- Meetings tab --

    def _build_meetings_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("student_council.meetings"))

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))

        tk.Label(filt, text=t("common.status") + ":", bg="#ecf0f1").pack(side="left")
        self._mtg_status_var = tk.StringVar(value="")
        mtg_status_cb = ttk.Combobox(filt, textvariable=self._mtg_status_var, width=12,
                                     values=["", "scheduled", "completed", "cancelled"],
                                     state="readonly")
        mtg_status_cb.pack(side="left", padx=(2, 10))
        ttk.Button(filt, text=t("common.filter"), command=self._load_meetings).pack(side="left")

        # Treeview
        cols = ("id", "date", "chair", "agenda", "status")
        self._mtg_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", t("common.id"), 40), ("date", t("common.date"), 100),
                         ("chair", t("student_council.chair"), 140),
                         ("agenda", t("student_council.agenda"), 250),
                         ("status", t("common.status"), 90)]:
            self._mtg_tree.heading(c, text=h)
            self._mtg_tree.column(c, width=w, anchor="center" if w < 200 else "w")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._mtg_tree.yview)
        self._mtg_tree.configure(yscrollcommand=vsb.set)
        self._mtg_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Buttons
        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(5, 0))
        for txt, cmd in [(t("common.new"), self._new_meeting),
                          (t("common.view"), self._view_meeting),
                          (t("common.update"), self._update_meeting),
                          (t("common.completed"), self._complete_meeting),
                          (t("common.delete"), self._delete_meeting)]:
            ttk.Button(btn_frame, text=txt, command=cmd).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Export CSV", command=self._export_meetings_csv).pack(side="left", padx=2)

    # -- Proposals tab --

    def _build_proposals_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("student_council.proposals"))

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))

        tk.Label(filt, text=t("common.category") + ":", bg="#ecf0f1").pack(side="left")
        self._prop_cat_var = tk.StringVar(value="")
        cat_cb = ttk.Combobox(filt, textvariable=self._prop_cat_var, width=14,
                              values=["", "general", "facilities", "welfare", "academic",
                                      "social", "environmental", "financial"],
                              state="readonly")
        cat_cb.pack(side="left", padx=(2, 10))

        tk.Label(filt, text=t("common.status") + ":", bg="#ecf0f1").pack(side="left")
        self._prop_status_var = tk.StringVar(value="")
        status_cb = ttk.Combobox(filt, textvariable=self._prop_status_var, width=14,
                                 values=["", "pending", "approved", "rejected",
                                         "in_progress", "implemented", "deferred"],
                                 state="readonly")
        status_cb.pack(side="left", padx=(2, 10))
        ttk.Button(filt, text=t("common.filter"), command=self._load_proposals).pack(side="left")

        # Treeview
        cols = ("id", "title", "proposed_by", "category", "vote_for",
                "vote_against", "outcome", "implementation")
        self._prop_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", t("common.id"), 40), ("title", t("common.title"), 180),
                         ("proposed_by", t("student_council.proposed_by"), 120),
                         ("category", t("common.category"), 90),
                         ("vote_for", t("student_council.votes_for"), 70),
                         ("vote_against", t("student_council.votes_against"), 80),
                         ("outcome", t("student_council.outcome"), 100),
                         ("implementation", t("student_council.implementation"), 100)]:
            self._prop_tree.heading(c, text=h)
            self._prop_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._prop_tree.yview)
        self._prop_tree.configure(yscrollcommand=vsb.set)
        self._prop_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Buttons
        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(5, 0))
        for txt, cmd in [(t("common.new"), self._new_proposal),
                          (t("common.view"), self._view_proposal),
                          (t("student_council.record_votes"), self._record_votes),
                          (t("student_council.management_response"), self._management_response),
                          (t("common.delete"), self._delete_proposal)]:
            ttk.Button(btn_frame, text=txt, command=cmd).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Export CSV", command=self._export_proposals_csv).pack(side="left", padx=2)

    # -- Statistics tab --

    def _build_stats_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=20, pady=20)
        self._nb.add(tab, text=t("common.summary"))
        self._stats_frame = tab

    def _export_members_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._mem_tree, "student_council_members_export.csv")

    def _export_meetings_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._mtg_tree, "student_council_meetings_export.csv")

    def _export_proposals_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._prop_tree, "student_council_proposals_export.csv")

    # -- Refresh / Load --

    def refresh(self):
        self._load_members()
        self._load_meetings()
        self._load_proposals()
        self._load_stats()

    def _load_members(self):
        self._mem_tree.delete(*self._mem_tree.get_children())
        try:
            status = self._mem_status_var.get() or None
            role = self._mem_role_var.get() or None
            for m in self.svc.list_members(status=status, role=role):
                self._mem_tree.insert("", "end", values=(
                    m["id"], m["student_id"], m["role"],
                    m.get("year_group") or "-", m.get("department") or "-",
                    m.get("elected_date") or "-", m.get("term_end_date") or "-",
                    m["status"],
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_meetings(self):
        self._mtg_tree.delete(*self._mtg_tree.get_children())
        try:
            status = self._mtg_status_var.get() or None
            for m in self.svc.list_meetings(status=status):
                chair_name = ""
                if m.get("chair_first_name"):
                    chair_name = f"{m['chair_first_name']} {m['chair_last_name']}"
                self._mtg_tree.insert("", "end", values=(
                    m["id"], m["meeting_date"], chair_name or "-",
                    (m.get("agenda") or "-")[:60], m["status"],
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_proposals(self):
        self._prop_tree.delete(*self._prop_tree.get_children())
        try:
            category = self._prop_cat_var.get() or None
            impl_status = self._prop_status_var.get() or None
            for p in self.svc.list_proposals(category=category, implementation_status=impl_status):
                proposer = ""
                if p.get("proposer_first_name"):
                    proposer = f"{p['proposer_first_name']} {p['proposer_last_name']}"
                self._prop_tree.insert("", "end", values=(
                    p["id"], p["title"], proposer or "-", p["category"],
                    p["vote_for"], p["vote_against"],
                    p.get("outcome") or "-", p["implementation_status"],
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_stats(self):
        for w in self._stats_frame.winfo_children():
            w.destroy()
        try:
            stats = self.svc.get_stats()

            tk.Label(self._stats_frame, text=t("student_council.statistics"),
                     font=("Helvetica", 14, "bold"), bg="#ecf0f1").pack(anchor="w", pady=(0, 10))

            # Members section
            tk.Label(self._stats_frame, text=t("student_council.members"),
                     font=("Helvetica", 12, "bold"), bg="#ecf0f1").pack(anchor="w", pady=(5, 2))
            tk.Label(self._stats_frame,
                     text=f"  {t('common.total')}: {stats['total_members']}  |  {t('common.active')}: {stats['active_members']}",
                     bg="#ecf0f1").pack(anchor="w")
            if stats["by_role"]:
                roles_str = ", ".join(f"{k}: {v}" for k, v in stats["by_role"].items())
                tk.Label(self._stats_frame, text=f"  {t('student_council.by_role')}: {roles_str}",
                         bg="#ecf0f1").pack(anchor="w")

            # Meetings section
            tk.Label(self._stats_frame, text=t("student_council.meetings"),
                     font=("Helvetica", 12, "bold"), bg="#ecf0f1").pack(anchor="w", pady=(10, 2))
            tk.Label(self._stats_frame,
                     text=f"  {t('common.total')}: {stats['total_meetings']}  |  {t('common.completed')}: {stats['completed_meetings']}",
                     bg="#ecf0f1").pack(anchor="w")

            # Proposals section
            tk.Label(self._stats_frame, text=t("student_council.proposals"),
                     font=("Helvetica", 12, "bold"), bg="#ecf0f1").pack(anchor="w", pady=(10, 2))
            tk.Label(self._stats_frame,
                     text=f"  {t('common.total')}: {stats['total_proposals']}  |  {t('student_council.implemented')}: {stats['proposals_implemented']}",
                     bg="#ecf0f1").pack(anchor="w")
            if stats["by_category"]:
                cat_str = ", ".join(f"{k}: {v}" for k, v in stats["by_category"].items())
                tk.Label(self._stats_frame, text=f"  {t('student_council.by_category')}: {cat_str}",
                         bg="#ecf0f1", wraplength=600, justify="left").pack(anchor="w")
            if stats["by_implementation_status"]:
                impl_str = ", ".join(f"{k}: {v}" for k, v in stats["by_implementation_status"].items())
                tk.Label(self._stats_frame, text=f"  {t('student_council.by_status')}: {impl_str}",
                         bg="#ecf0f1", wraplength=600, justify="left").pack(anchor="w")
        except Exception as e:
            tk.Label(self._stats_frame, text=f"{t('common.error')}: {e}",
                     bg="#ecf0f1", fg="red").pack(anchor="w")

    # -- Member helpers --

    def _selected_member_id(self):
        sel = self._mem_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"))
            return None
        return self._mem_tree.item(sel[0], "values")[0]

    def _new_member(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("student_council.new_member"))
        dlg.geometry("400x350")
        dlg.configure(bg="#ecf0f1")
        dlg.grab_set()

        fields = {}
        for row, (label, key, default) in enumerate([
            (t("common.student_id") + ":", "student_id", ""),
            (t("student_council.role") + ":", "role", "representative"),
            (t("student_council.year_group") + ":", "year_group", ""),
            (t("student_council.department") + ":", "department", ""),
            (t("student_council.elected_date") + ":", "elected_date", ""),
            (t("student_council.term_end_date") + ":", "term_end_date", ""),
        ]):
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=row, column=0, padx=10, pady=5, sticky="e")
            if key == "role":
                var = tk.StringVar(value=default)
                cb = ttk.Combobox(dlg, textvariable=var, width=20,
                                  values=["representative", "chair", "vice_chair",
                                          "secretary", "treasurer", "welfare_officer"],
                                  state="readonly")
                cb.grid(row=row, column=1, padx=10, pady=5, sticky="w")
                fields[key] = var
            else:
                ent = ttk.Entry(dlg, width=22)
                ent.insert(0, default)
                ent.grid(row=row, column=1, padx=10, pady=5, sticky="w")
                fields[key] = ent

        def save():
            try:
                student_id = int(fields["student_id"].get().strip())
                role = fields["role"].get()
                year_group = fields["year_group"].get().strip() or None
                department = fields["department"].get().strip() or None
                elected = fields["elected_date"].get().strip() or None
                term_end = fields["term_end_date"].get().strip() or None
                self.svc.create_member(student_id, role=role, year_group=year_group,
                                       department=department, elected_date=elected,
                                       term_end_date=term_end)
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                dlg.destroy()
                self._load_members()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("common.save"), command=save).grid(row=6, column=0, columnspan=2, pady=15)

    def _view_member(self):
        mid = self._selected_member_id()
        if not mid:
            return
        try:
            m = self.svc.get_member(int(mid))
            if not m:
                messagebox.showwarning(t("common.warning"), t("common.no_data"))
                return
            dlg = tk.Toplevel(self)
            dlg.title(f"{t('student_council.member')} #{m['id']}")
            dlg.geometry("400x320")
            dlg.configure(bg="#ecf0f1")
            name = f"{m.get('first_name', '')} {m.get('last_name', '')}".strip() or t("common.not_applicable")
            info = (
                f"{t('common.id')}: {m['id']}\n"
                f"{t('common.student_id')}: {m['student_id']}\n"
                f"{t('common.name')}: {name}\n"
                f"{t('student_council.role')}: {m['role']}\n"
                f"{t('student_council.year_group')}: {m.get('year_group') or t('common.not_applicable')}\n"
                f"{t('student_council.department')}: {m.get('department') or t('common.not_applicable')}\n"
                f"{t('student_council.elected')}: {m.get('elected_date') or t('common.not_applicable')}\n"
                f"{t('student_council.term_end')}: {m.get('term_end_date') or t('common.not_applicable')}\n"
                f"{t('common.status')}: {m['status']}\n"
                f"{t('common.created_at')}: {m.get('created_at') or t('common.not_applicable')}"
            )
            tk.Label(dlg, text=info, bg="#ecf0f1", justify="left",
                     font=("Helvetica", 11)).pack(padx=20, pady=20, anchor="w")
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _update_member(self):
        mid = self._selected_member_id()
        if not mid:
            return
        try:
            m = self.svc.get_member(int(mid))
            if not m:
                messagebox.showwarning(t("common.warning"), t("common.no_data"))
                return
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"{t('student_council.update_member')} #{m['id']}")
        dlg.geometry("400x300")
        dlg.configure(bg="#ecf0f1")
        dlg.grab_set()

        fields = {}
        for row, (label, key, val) in enumerate([
            (t("student_council.role") + ":", "role", m["role"]),
            (t("student_council.year_group") + ":", "year_group", m.get("year_group") or ""),
            (t("student_council.department") + ":", "department", m.get("department") or ""),
            (t("common.status") + ":", "status", m["status"]),
        ]):
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=row, column=0, padx=10, pady=5, sticky="e")
            if key == "role":
                var = tk.StringVar(value=val)
                ttk.Combobox(dlg, textvariable=var, width=20,
                             values=["representative", "chair", "vice_chair",
                                     "secretary", "treasurer", "welfare_officer"],
                             state="readonly").grid(row=row, column=1, padx=10, pady=5, sticky="w")
                fields[key] = var
            elif key == "status":
                var = tk.StringVar(value=val)
                ttk.Combobox(dlg, textvariable=var, width=20,
                             values=["active", "resigned", "removed", "term_ended"],
                             state="readonly").grid(row=row, column=1, padx=10, pady=5, sticky="w")
                fields[key] = var
            else:
                ent = ttk.Entry(dlg, width=22)
                ent.insert(0, val)
                ent.grid(row=row, column=1, padx=10, pady=5, sticky="w")
                fields[key] = ent

        def save():
            try:
                updates = {}
                for k, w in fields.items():
                    v = w.get().strip() if hasattr(w, 'get') else w.get()
                    if v:
                        updates[k] = v
                self.svc.update_member(int(mid), **updates)
                messagebox.showinfo(t("common.success"), t("common.updated_success"))
                dlg.destroy()
                self._load_members()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("common.save"), command=save).grid(row=4, column=0, columnspan=2, pady=15)

    def _end_term_member(self):
        mid = self._selected_member_id()
        if not mid:
            return
        if not messagebox.askyesno(t("common.confirm"), t("student_council.end_term_confirm", id=mid)):
            return
        try:
            self.svc.end_term(int(mid))
            messagebox.showinfo(t("common.success"), t("student_council.term_ended"))
            self._load_members()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _delete_member(self):
        mid = self._selected_member_id()
        if not mid:
            return
        if not messagebox.askyesno(t("common.confirm"), t("common.delete_confirm_msg")):
            return
        try:
            self.svc.delete_member(int(mid))
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_members()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # -- Meeting helpers --

    def _selected_meeting_id(self):
        sel = self._mtg_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"))
            return None
        return self._mtg_tree.item(sel[0], "values")[0]

    def _new_meeting(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("student_council.new_meeting"))
        dlg.geometry("450x250")
        dlg.configure(bg="#ecf0f1")
        dlg.grab_set()

        fields = {}
        for row, (label, key) in enumerate([
            (t("student_council.meeting_date") + ":", "meeting_date"),
            (t("student_council.chair_member_id") + ":", "chair_id"),
        ]):
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=row, column=0, padx=10, pady=5, sticky="e")
            ent = ttk.Entry(dlg, width=22)
            ent.grid(row=row, column=1, padx=10, pady=5, sticky="w")
            fields[key] = ent

        tk.Label(dlg, text=t("student_council.agenda") + ":", bg="#ecf0f1").grid(row=2, column=0, padx=10, pady=5, sticky="ne")
        agenda_txt = tk.Text(dlg, width=30, height=4)
        agenda_txt.grid(row=2, column=1, padx=10, pady=5, sticky="w")
        fields["agenda"] = agenda_txt

        def save():
            try:
                meeting_date = fields["meeting_date"].get().strip()
                if not meeting_date:
                    messagebox.showwarning(t("common.validation"), t("common.field_required"))
                    return
                chair_str = fields["chair_id"].get().strip()
                chair_id = int(chair_str) if chair_str else None
                agenda = fields["agenda"].get("1.0", "end-1c").strip() or None
                self.svc.create_meeting(meeting_date, chair_id=chair_id, agenda=agenda)
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                dlg.destroy()
                self._load_meetings()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("common.save"), command=save).grid(row=3, column=0, columnspan=2, pady=10)

    def _view_meeting(self):
        mid = self._selected_meeting_id()
        if not mid:
            return
        try:
            m = self.svc.get_meeting(int(mid))
            if not m:
                messagebox.showwarning(t("common.warning"), t("common.no_data"))
                return
            dlg = tk.Toplevel(self)
            dlg.title(f"{t('student_council.meeting')} #{m['id']}")
            dlg.geometry("500x400")
            dlg.configure(bg="#ecf0f1")
            chair = ""
            if m.get("chair_first_name"):
                chair = f"{m['chair_first_name']} {m['chair_last_name']}"
            info = (
                f"{t('common.id')}: {m['id']}\n"
                f"{t('common.date')}: {m['meeting_date']}\n"
                f"{t('student_council.chair')}: {chair or t('common.not_applicable')}\n"
                f"{t('common.status')}: {m['status']}\n"
                f"{t('common.created_at')}: {m.get('created_at') or t('common.not_applicable')}\n\n"
                f"{t('student_council.agenda')}:\n{m.get('agenda') or t('common.not_applicable')}\n\n"
                f"{t('student_council.minutes')}:\n{m.get('minutes') or t('common.not_applicable')}\n\n"
                f"{t('student_council.attendees')}:\n{m.get('attendees') or t('common.not_applicable')}"
            )
            txt = tk.Text(dlg, wrap="word", font=("Helvetica", 11))
            txt.insert("1.0", info)
            txt.configure(state="disabled")
            txt.pack(fill="both", expand=True, padx=15, pady=15)
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _update_meeting(self):
        mid = self._selected_meeting_id()
        if not mid:
            return
        try:
            m = self.svc.get_meeting(int(mid))
            if not m:
                messagebox.showwarning(t("common.warning"), t("common.no_data"))
                return
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"{t('student_council.update_meeting')} #{m['id']}")
        dlg.geometry("450x320")
        dlg.configure(bg="#ecf0f1")
        dlg.grab_set()

        fields = {}
        tk.Label(dlg, text=t("common.date") + ":", bg="#ecf0f1").grid(row=0, column=0, padx=10, pady=5, sticky="e")
        date_ent = ttk.Entry(dlg, width=22)
        date_ent.insert(0, m["meeting_date"] or "")
        date_ent.grid(row=0, column=1, padx=10, pady=5, sticky="w")
        fields["meeting_date"] = date_ent

        tk.Label(dlg, text=t("student_council.chair_id") + ":", bg="#ecf0f1").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        chair_ent = ttk.Entry(dlg, width=22)
        chair_ent.insert(0, str(m.get("chair_id") or ""))
        chair_ent.grid(row=1, column=1, padx=10, pady=5, sticky="w")
        fields["chair_id"] = chair_ent

        tk.Label(dlg, text=t("common.status") + ":", bg="#ecf0f1").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        status_var = tk.StringVar(value=m["status"])
        ttk.Combobox(dlg, textvariable=status_var, width=20,
                     values=["scheduled", "completed", "cancelled"],
                     state="readonly").grid(row=2, column=1, padx=10, pady=5, sticky="w")
        fields["status"] = status_var

        tk.Label(dlg, text=t("student_council.agenda") + ":", bg="#ecf0f1").grid(row=3, column=0, padx=10, pady=5, sticky="ne")
        agenda_txt = tk.Text(dlg, width=30, height=4)
        agenda_txt.insert("1.0", m.get("agenda") or "")
        agenda_txt.grid(row=3, column=1, padx=10, pady=5, sticky="w")
        fields["agenda"] = agenda_txt

        def save():
            try:
                updates = {}
                date_val = fields["meeting_date"].get().strip()
                if date_val:
                    updates["meeting_date"] = date_val
                chair_val = fields["chair_id"].get().strip()
                if chair_val:
                    updates["chair_id"] = int(chair_val)
                status_val = fields["status"].get()
                if status_val:
                    updates["status"] = status_val
                agenda_val = fields["agenda"].get("1.0", "end-1c").strip()
                if agenda_val:
                    updates["agenda"] = agenda_val
                self.svc.update_meeting(int(mid), **updates)
                messagebox.showinfo(t("common.success"), t("common.updated_success"))
                dlg.destroy()
                self._load_meetings()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("common.save"), command=save).grid(row=4, column=0, columnspan=2, pady=10)

    def _complete_meeting(self):
        mid = self._selected_meeting_id()
        if not mid:
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"{t('student_council.complete_meeting')} #{mid}")
        dlg.geometry("450x350")
        dlg.configure(bg="#ecf0f1")
        dlg.grab_set()

        tk.Label(dlg, text=t("student_council.minutes") + ":", bg="#ecf0f1").pack(anchor="w", padx=10, pady=(10, 2))
        minutes_txt = tk.Text(dlg, width=50, height=8)
        minutes_txt.pack(padx=10, pady=2)

        tk.Label(dlg, text=t("student_council.attendees_csv") + ":", bg="#ecf0f1").pack(anchor="w", padx=10, pady=(10, 2))
        attendees_ent = ttk.Entry(dlg, width=50)
        attendees_ent.pack(padx=10, pady=2)

        def save():
            try:
                minutes = minutes_txt.get("1.0", "end-1c").strip()
                attendees = attendees_ent.get().strip()
                if not minutes:
                    messagebox.showwarning(t("common.validation"), t("student_council.minutes_required"))
                    return
                if not attendees:
                    messagebox.showwarning(t("common.validation"), t("student_council.attendees_required"))
                    return
                self.svc.complete_meeting(int(mid), minutes, attendees)
                messagebox.showinfo(t("common.success"), t("student_council.meeting_completed"))
                dlg.destroy()
                self._load_meetings()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("common.completed"), command=save).pack(pady=15)

    def _delete_meeting(self):
        mid = self._selected_meeting_id()
        if not mid:
            return
        if not messagebox.askyesno(t("common.confirm"), t("common.delete_confirm_msg")):
            return
        try:
            self.svc.delete_meeting(int(mid))
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_meetings()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # -- Proposal helpers --

    def _selected_proposal_id(self):
        sel = self._prop_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"))
            return None
        return self._prop_tree.item(sel[0], "values")[0]

    def _new_proposal(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("student_council.new_proposal"))
        dlg.geometry("450x350")
        dlg.configure(bg="#ecf0f1")
        dlg.grab_set()

        fields = {}
        tk.Label(dlg, text=t("common.title") + ":", bg="#ecf0f1").grid(row=0, column=0, padx=10, pady=5, sticky="e")
        title_ent = ttk.Entry(dlg, width=30)
        title_ent.grid(row=0, column=1, padx=10, pady=5, sticky="w")
        fields["title"] = title_ent

        tk.Label(dlg, text=t("student_council.proposed_by_id") + ":", bg="#ecf0f1").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        by_ent = ttk.Entry(dlg, width=30)
        by_ent.grid(row=1, column=1, padx=10, pady=5, sticky="w")
        fields["proposed_by"] = by_ent

        tk.Label(dlg, text=t("student_council.meeting_id") + ":", bg="#ecf0f1").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        mtg_ent = ttk.Entry(dlg, width=30)
        mtg_ent.grid(row=2, column=1, padx=10, pady=5, sticky="w")
        fields["meeting_id"] = mtg_ent

        tk.Label(dlg, text=t("common.category") + ":", bg="#ecf0f1").grid(row=3, column=0, padx=10, pady=5, sticky="e")
        cat_var = tk.StringVar(value="general")
        ttk.Combobox(dlg, textvariable=cat_var, width=28,
                     values=["general", "facilities", "welfare", "academic",
                             "social", "environmental", "financial"],
                     state="readonly").grid(row=3, column=1, padx=10, pady=5, sticky="w")
        fields["category"] = cat_var

        tk.Label(dlg, text=t("common.description") + ":", bg="#ecf0f1").grid(row=4, column=0, padx=10, pady=5, sticky="ne")
        desc_txt = tk.Text(dlg, width=30, height=4)
        desc_txt.grid(row=4, column=1, padx=10, pady=5, sticky="w")
        fields["description"] = desc_txt

        def save():
            try:
                title_val = fields["title"].get().strip()
                if not title_val:
                    messagebox.showwarning(t("common.validation"), t("common.field_required"))
                    return
                by_str = fields["proposed_by"].get().strip()
                proposed_by = int(by_str) if by_str else None
                mtg_str = fields["meeting_id"].get().strip()
                meeting_id = int(mtg_str) if mtg_str else None
                category = fields["category"].get()
                description = fields["description"].get("1.0", "end-1c").strip() or None
                self.svc.create_proposal(title_val, proposed_by=proposed_by,
                                          meeting_id=meeting_id, description=description,
                                          category=category)
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                dlg.destroy()
                self._load_proposals()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("common.save"), command=save).grid(row=5, column=0, columnspan=2, pady=10)

    def _view_proposal(self):
        pid = self._selected_proposal_id()
        if not pid:
            return
        try:
            p = self.svc.get_proposal(int(pid))
            if not p:
                messagebox.showwarning(t("common.warning"), t("common.no_data"))
                return
            dlg = tk.Toplevel(self)
            dlg.title(f"{t('student_council.proposal')} #{p['id']}")
            dlg.geometry("500x450")
            dlg.configure(bg="#ecf0f1")
            proposer = ""
            if p.get("proposer_first_name"):
                proposer = f"{p['proposer_first_name']} {p['proposer_last_name']}"
            info = (
                f"{t('common.id')}: {p['id']}\n"
                f"{t('common.title')}: {p['title']}\n"
                f"{t('student_council.proposed_by')}: {proposer or t('common.not_applicable')}\n"
                f"{t('common.category')}: {p['category']}\n"
                f"{t('student_council.meeting_id')}: {p.get('meeting_id') or t('common.not_applicable')}\n\n"
                f"{t('common.description')}:\n{p.get('description') or t('common.not_applicable')}\n\n"
                f"{t('student_council.votes')}: {t('student_council.votes_for')}={p['vote_for']}, "
                f"{t('student_council.votes_against')}={p['vote_against']}, "
                f"{t('student_council.votes_abstain')}={p['vote_abstain']}\n"
                f"{t('student_council.outcome')}: {p.get('outcome') or t('common.not_applicable')}\n\n"
                f"{t('student_council.management_response')}:\n{p.get('management_response') or t('common.not_applicable')}\n\n"
                f"{t('student_council.implementation')}: {p['implementation_status']}\n"
                f"{t('common.created_at')}: {p.get('created_at') or t('common.not_applicable')}"
            )
            txt = tk.Text(dlg, wrap="word", font=("Helvetica", 11))
            txt.insert("1.0", info)
            txt.configure(state="disabled")
            txt.pack(fill="both", expand=True, padx=15, pady=15)
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _record_votes(self):
        pid = self._selected_proposal_id()
        if not pid:
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"{t('student_council.record_votes')} - #{pid}")
        dlg.geometry("350x250")
        dlg.configure(bg="#ecf0f1")
        dlg.grab_set()

        fields = {}
        for row, (label, key) in enumerate([
            (t("student_council.votes_for") + ":", "vote_for"),
            (t("student_council.votes_against") + ":", "vote_against"),
            (t("student_council.votes_abstain") + ":", "vote_abstain"),
            (t("student_council.outcome") + ":", "outcome"),
        ]):
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=row, column=0, padx=10, pady=5, sticky="e")
            ent = ttk.Entry(dlg, width=22)
            ent.grid(row=row, column=1, padx=10, pady=5, sticky="w")
            fields[key] = ent

        def save():
            try:
                vote_for = int(fields["vote_for"].get().strip() or "0")
                vote_against = int(fields["vote_against"].get().strip() or "0")
                vote_abstain = int(fields["vote_abstain"].get().strip() or "0")
                outcome = fields["outcome"].get().strip()
                if not outcome:
                    messagebox.showwarning(t("common.validation"), t("common.field_required"))
                    return
                self.svc.record_votes(int(pid), vote_for, vote_against, vote_abstain, outcome)
                messagebox.showinfo(t("common.success"), t("student_council.votes_recorded"))
                dlg.destroy()
                self._load_proposals()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("common.save"), command=save).grid(row=4, column=0, columnspan=2, pady=15)

    def _management_response(self):
        pid = self._selected_proposal_id()
        if not pid:
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"{t('student_council.management_response')} - #{pid}")
        dlg.geometry("450x320")
        dlg.configure(bg="#ecf0f1")
        dlg.grab_set()

        tk.Label(dlg, text=t("student_council.management_response") + ":", bg="#ecf0f1").pack(anchor="w", padx=10, pady=(10, 2))
        response_txt = tk.Text(dlg, width=50, height=6)
        response_txt.pack(padx=10, pady=2)

        tk.Label(dlg, text=t("student_council.implementation_status") + ":", bg="#ecf0f1").pack(anchor="w", padx=10, pady=(10, 2))
        status_var = tk.StringVar(value="pending")
        ttk.Combobox(dlg, textvariable=status_var, width=20,
                     values=["pending", "approved", "rejected", "in_progress",
                             "implemented", "deferred"],
                     state="readonly").pack(padx=10, pady=2, anchor="w")

        def save():
            try:
                response = response_txt.get("1.0", "end-1c").strip()
                impl_status = status_var.get()
                if not response:
                    messagebox.showwarning(t("common.validation"), t("common.field_required"))
                    return
                self.svc.respond_to_proposal(int(pid), response, impl_status)
                messagebox.showinfo(t("common.success"), t("student_council.response_recorded"))
                dlg.destroy()
                self._load_proposals()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("common.save"), command=save).pack(pady=15)

    def _export_members_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._mem_tree, "student_council_members.csv")

    def _export_meetings_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._mtg_tree, "student_council_meetings.csv")

    def _export_proposals_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._prop_tree, "student_council_proposals.csv")

    def _delete_proposal(self):
        pid = self._selected_proposal_id()
        if not pid:
            return
        if not messagebox.askyesno(t("common.confirm"), t("common.delete_confirm_msg")):
            return
        try:
            self.svc.delete_proposal(int(pid))
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_proposals()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
