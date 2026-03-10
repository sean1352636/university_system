"""Student Council GUI module."""

import tkinter as tk
from tkinter import ttk, messagebox

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

    # ── UI construction ──

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Student Council",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_members_tab()
        self._build_meetings_tab()
        self._build_proposals_tab()
        self._build_stats_tab()

    # ── Members tab ──

    def _build_members_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Members")

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))

        tk.Label(filt, text="Status:", bg="#ecf0f1").pack(side="left")
        self._mem_status_var = tk.StringVar(value="")
        mem_status_cb = ttk.Combobox(filt, textvariable=self._mem_status_var, width=12,
                                     values=["", "active", "resigned", "removed", "term_ended"],
                                     state="readonly")
        mem_status_cb.pack(side="left", padx=(2, 10))

        tk.Label(filt, text="Role:", bg="#ecf0f1").pack(side="left")
        self._mem_role_var = tk.StringVar(value="")
        mem_role_cb = ttk.Combobox(filt, textvariable=self._mem_role_var, width=14,
                                   values=["", "representative", "chair", "vice_chair",
                                           "secretary", "treasurer", "welfare_officer"],
                                   state="readonly")
        mem_role_cb.pack(side="left", padx=(2, 10))

        ttk.Button(filt, text="Filter", command=self._load_members).pack(side="left")

        # Treeview
        cols = ("id", "student_id", "role", "year_group", "department",
                "elected", "term_end", "status")
        self._mem_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("student_id", "Student ID", 70),
                         ("role", "Role", 100), ("year_group", "Year Group", 80),
                         ("department", "Department", 100), ("elected", "Elected", 90),
                         ("term_end", "Term End", 90), ("status", "Status", 80)]:
            self._mem_tree.heading(c, text=h)
            self._mem_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._mem_tree.yview)
        self._mem_tree.configure(yscrollcommand=vsb.set)
        self._mem_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Buttons
        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(5, 0))
        for text, cmd in [("New", self._new_member), ("View", self._view_member),
                          ("Update", self._update_member), ("End Term", self._end_term_member),
                          ("Delete", self._delete_member)]:
            ttk.Button(btn_frame, text=text, command=cmd).pack(side="left", padx=2)

    # ── Meetings tab ──

    def _build_meetings_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Meetings")

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))

        tk.Label(filt, text="Status:", bg="#ecf0f1").pack(side="left")
        self._mtg_status_var = tk.StringVar(value="")
        mtg_status_cb = ttk.Combobox(filt, textvariable=self._mtg_status_var, width=12,
                                     values=["", "scheduled", "completed", "cancelled"],
                                     state="readonly")
        mtg_status_cb.pack(side="left", padx=(2, 10))
        ttk.Button(filt, text="Filter", command=self._load_meetings).pack(side="left")

        # Treeview
        cols = ("id", "date", "chair", "agenda", "status")
        self._mtg_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("date", "Date", 100),
                         ("chair", "Chair", 140), ("agenda", "Agenda", 250),
                         ("status", "Status", 90)]:
            self._mtg_tree.heading(c, text=h)
            self._mtg_tree.column(c, width=w, anchor="center" if w < 200 else "w")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._mtg_tree.yview)
        self._mtg_tree.configure(yscrollcommand=vsb.set)
        self._mtg_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Buttons
        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(5, 0))
        for text, cmd in [("New", self._new_meeting), ("View", self._view_meeting),
                          ("Update", self._update_meeting), ("Complete", self._complete_meeting),
                          ("Delete", self._delete_meeting)]:
            ttk.Button(btn_frame, text=text, command=cmd).pack(side="left", padx=2)

    # ── Proposals tab ──

    def _build_proposals_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Proposals")

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))

        tk.Label(filt, text="Category:", bg="#ecf0f1").pack(side="left")
        self._prop_cat_var = tk.StringVar(value="")
        cat_cb = ttk.Combobox(filt, textvariable=self._prop_cat_var, width=14,
                              values=["", "general", "facilities", "welfare", "academic",
                                      "social", "environmental", "financial"],
                              state="readonly")
        cat_cb.pack(side="left", padx=(2, 10))

        tk.Label(filt, text="Status:", bg="#ecf0f1").pack(side="left")
        self._prop_status_var = tk.StringVar(value="")
        status_cb = ttk.Combobox(filt, textvariable=self._prop_status_var, width=14,
                                 values=["", "pending", "approved", "rejected",
                                         "in_progress", "implemented", "deferred"],
                                 state="readonly")
        status_cb.pack(side="left", padx=(2, 10))
        ttk.Button(filt, text="Filter", command=self._load_proposals).pack(side="left")

        # Treeview
        cols = ("id", "title", "proposed_by", "category", "vote_for",
                "vote_against", "outcome", "implementation")
        self._prop_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("title", "Title", 180),
                         ("proposed_by", "Proposed By", 120), ("category", "Category", 90),
                         ("vote_for", "Votes For", 70), ("vote_against", "Votes Against", 80),
                         ("outcome", "Outcome", 100), ("implementation", "Implementation", 100)]:
            self._prop_tree.heading(c, text=h)
            self._prop_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._prop_tree.yview)
        self._prop_tree.configure(yscrollcommand=vsb.set)
        self._prop_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Buttons
        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(5, 0))
        for text, cmd in [("New", self._new_proposal), ("View", self._view_proposal),
                          ("Record Votes", self._record_votes),
                          ("Management Response", self._management_response),
                          ("Delete", self._delete_proposal)]:
            ttk.Button(btn_frame, text=text, command=cmd).pack(side="left", padx=2)

    # ── Statistics tab ──

    def _build_stats_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=20, pady=20)
        self._nb.add(tab, text="Statistics")
        self._stats_frame = tab

    # ── Refresh / Load ──

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
            messagebox.showerror("Error", str(e))

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
            messagebox.showerror("Error", str(e))

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
            messagebox.showerror("Error", str(e))

    def _load_stats(self):
        for w in self._stats_frame.winfo_children():
            w.destroy()
        try:
            stats = self.svc.get_stats()

            tk.Label(self._stats_frame, text="Student Council Statistics",
                     font=("Helvetica", 14, "bold"), bg="#ecf0f1").pack(anchor="w", pady=(0, 10))

            # Members section
            tk.Label(self._stats_frame, text="Members",
                     font=("Helvetica", 12, "bold"), bg="#ecf0f1").pack(anchor="w", pady=(5, 2))
            tk.Label(self._stats_frame,
                     text=f"  Total: {stats['total_members']}  |  Active: {stats['active_members']}",
                     bg="#ecf0f1").pack(anchor="w")
            if stats["by_role"]:
                roles_str = ", ".join(f"{k}: {v}" for k, v in stats["by_role"].items())
                tk.Label(self._stats_frame, text=f"  By Role: {roles_str}",
                         bg="#ecf0f1").pack(anchor="w")

            # Meetings section
            tk.Label(self._stats_frame, text="Meetings",
                     font=("Helvetica", 12, "bold"), bg="#ecf0f1").pack(anchor="w", pady=(10, 2))
            tk.Label(self._stats_frame,
                     text=f"  Total: {stats['total_meetings']}  |  Completed: {stats['completed_meetings']}",
                     bg="#ecf0f1").pack(anchor="w")

            # Proposals section
            tk.Label(self._stats_frame, text="Proposals",
                     font=("Helvetica", 12, "bold"), bg="#ecf0f1").pack(anchor="w", pady=(10, 2))
            tk.Label(self._stats_frame,
                     text=f"  Total: {stats['total_proposals']}  |  Implemented: {stats['proposals_implemented']}",
                     bg="#ecf0f1").pack(anchor="w")
            if stats["by_category"]:
                cat_str = ", ".join(f"{k}: {v}" for k, v in stats["by_category"].items())
                tk.Label(self._stats_frame, text=f"  By Category: {cat_str}",
                         bg="#ecf0f1", wraplength=600, justify="left").pack(anchor="w")
            if stats["by_implementation_status"]:
                impl_str = ", ".join(f"{k}: {v}" for k, v in stats["by_implementation_status"].items())
                tk.Label(self._stats_frame, text=f"  By Status: {impl_str}",
                         bg="#ecf0f1", wraplength=600, justify="left").pack(anchor="w")
        except Exception as e:
            tk.Label(self._stats_frame, text=f"Error loading stats: {e}",
                     bg="#ecf0f1", fg="red").pack(anchor="w")

    # ── Member helpers ──

    def _selected_member_id(self):
        sel = self._mem_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Please select a member.")
            return None
        return self._mem_tree.item(sel[0], "values")[0]

    def _new_member(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Council Member")
        dlg.geometry("400x350")
        dlg.configure(bg="#ecf0f1")
        dlg.grab_set()

        fields = {}
        for row, (label, key, default) in enumerate([
            ("Student ID:", "student_id", ""),
            ("Role:", "role", "representative"),
            ("Year Group:", "year_group", ""),
            ("Department:", "department", ""),
            ("Elected Date (YYYY-MM-DD):", "elected_date", ""),
            ("Term End Date (YYYY-MM-DD):", "term_end_date", ""),
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
                messagebox.showinfo("Success", "Member created.")
                dlg.destroy()
                self._load_members()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(dlg, text="Save", command=save).grid(row=6, column=0, columnspan=2, pady=15)

    def _view_member(self):
        mid = self._selected_member_id()
        if not mid:
            return
        try:
            m = self.svc.get_member(int(mid))
            if not m:
                messagebox.showwarning("Warning", "Member not found.")
                return
            dlg = tk.Toplevel(self)
            dlg.title(f"Member #{m['id']}")
            dlg.geometry("400x320")
            dlg.configure(bg="#ecf0f1")
            name = f"{m.get('first_name', '')} {m.get('last_name', '')}".strip() or "N/A"
            info = (
                f"ID: {m['id']}\n"
                f"Student ID: {m['student_id']}\n"
                f"Name: {name}\n"
                f"Role: {m['role']}\n"
                f"Year Group: {m.get('year_group') or 'N/A'}\n"
                f"Department: {m.get('department') or 'N/A'}\n"
                f"Elected: {m.get('elected_date') or 'N/A'}\n"
                f"Term End: {m.get('term_end_date') or 'N/A'}\n"
                f"Status: {m['status']}\n"
                f"Created: {m.get('created_at') or 'N/A'}"
            )
            tk.Label(dlg, text=info, bg="#ecf0f1", justify="left",
                     font=("Helvetica", 11)).pack(padx=20, pady=20, anchor="w")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _update_member(self):
        mid = self._selected_member_id()
        if not mid:
            return
        try:
            m = self.svc.get_member(int(mid))
            if not m:
                messagebox.showwarning("Warning", "Member not found.")
                return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Update Member #{m['id']}")
        dlg.geometry("400x300")
        dlg.configure(bg="#ecf0f1")
        dlg.grab_set()

        fields = {}
        for row, (label, key, val) in enumerate([
            ("Role:", "role", m["role"]),
            ("Year Group:", "year_group", m.get("year_group") or ""),
            ("Department:", "department", m.get("department") or ""),
            ("Status:", "status", m["status"]),
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
                messagebox.showinfo("Success", "Member updated.")
                dlg.destroy()
                self._load_members()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(dlg, text="Save", command=save).grid(row=4, column=0, columnspan=2, pady=15)

    def _end_term_member(self):
        mid = self._selected_member_id()
        if not mid:
            return
        if not messagebox.askyesno("Confirm", f"End term for member #{mid}?"):
            return
        try:
            self.svc.end_term(int(mid))
            messagebox.showinfo("Success", "Term ended.")
            self._load_members()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _delete_member(self):
        mid = self._selected_member_id()
        if not mid:
            return
        if not messagebox.askyesno("Confirm", f"Delete member #{mid}?"):
            return
        try:
            self.svc.delete_member(int(mid))
            messagebox.showinfo("Success", "Member deleted.")
            self._load_members()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Meeting helpers ──

    def _selected_meeting_id(self):
        sel = self._mtg_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Please select a meeting.")
            return None
        return self._mtg_tree.item(sel[0], "values")[0]

    def _new_meeting(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Council Meeting")
        dlg.geometry("450x250")
        dlg.configure(bg="#ecf0f1")
        dlg.grab_set()

        fields = {}
        for row, (label, key) in enumerate([
            ("Meeting Date (YYYY-MM-DD):", "meeting_date"),
            ("Chair Member ID:", "chair_id"),
        ]):
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=row, column=0, padx=10, pady=5, sticky="e")
            ent = ttk.Entry(dlg, width=22)
            ent.grid(row=row, column=1, padx=10, pady=5, sticky="w")
            fields[key] = ent

        tk.Label(dlg, text="Agenda:", bg="#ecf0f1").grid(row=2, column=0, padx=10, pady=5, sticky="ne")
        agenda_txt = tk.Text(dlg, width=30, height=4)
        agenda_txt.grid(row=2, column=1, padx=10, pady=5, sticky="w")
        fields["agenda"] = agenda_txt

        def save():
            try:
                meeting_date = fields["meeting_date"].get().strip()
                if not meeting_date:
                    messagebox.showwarning("Warning", "Meeting date is required.")
                    return
                chair_str = fields["chair_id"].get().strip()
                chair_id = int(chair_str) if chair_str else None
                agenda = fields["agenda"].get("1.0", "end-1c").strip() or None
                self.svc.create_meeting(meeting_date, chair_id=chair_id, agenda=agenda)
                messagebox.showinfo("Success", "Meeting created.")
                dlg.destroy()
                self._load_meetings()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(dlg, text="Save", command=save).grid(row=3, column=0, columnspan=2, pady=10)

    def _view_meeting(self):
        mid = self._selected_meeting_id()
        if not mid:
            return
        try:
            m = self.svc.get_meeting(int(mid))
            if not m:
                messagebox.showwarning("Warning", "Meeting not found.")
                return
            dlg = tk.Toplevel(self)
            dlg.title(f"Meeting #{m['id']}")
            dlg.geometry("500x400")
            dlg.configure(bg="#ecf0f1")
            chair = ""
            if m.get("chair_first_name"):
                chair = f"{m['chair_first_name']} {m['chair_last_name']}"
            info = (
                f"ID: {m['id']}\n"
                f"Date: {m['meeting_date']}\n"
                f"Chair: {chair or 'N/A'}\n"
                f"Status: {m['status']}\n"
                f"Created: {m.get('created_at') or 'N/A'}\n\n"
                f"Agenda:\n{m.get('agenda') or 'N/A'}\n\n"
                f"Minutes:\n{m.get('minutes') or 'N/A'}\n\n"
                f"Attendees:\n{m.get('attendees') or 'N/A'}"
            )
            txt = tk.Text(dlg, wrap="word", font=("Helvetica", 11))
            txt.insert("1.0", info)
            txt.configure(state="disabled")
            txt.pack(fill="both", expand=True, padx=15, pady=15)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _update_meeting(self):
        mid = self._selected_meeting_id()
        if not mid:
            return
        try:
            m = self.svc.get_meeting(int(mid))
            if not m:
                messagebox.showwarning("Warning", "Meeting not found.")
                return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Update Meeting #{m['id']}")
        dlg.geometry("450x320")
        dlg.configure(bg="#ecf0f1")
        dlg.grab_set()

        fields = {}
        tk.Label(dlg, text="Date:", bg="#ecf0f1").grid(row=0, column=0, padx=10, pady=5, sticky="e")
        date_ent = ttk.Entry(dlg, width=22)
        date_ent.insert(0, m["meeting_date"] or "")
        date_ent.grid(row=0, column=1, padx=10, pady=5, sticky="w")
        fields["meeting_date"] = date_ent

        tk.Label(dlg, text="Chair ID:", bg="#ecf0f1").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        chair_ent = ttk.Entry(dlg, width=22)
        chair_ent.insert(0, str(m.get("chair_id") or ""))
        chair_ent.grid(row=1, column=1, padx=10, pady=5, sticky="w")
        fields["chair_id"] = chair_ent

        tk.Label(dlg, text="Status:", bg="#ecf0f1").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        status_var = tk.StringVar(value=m["status"])
        ttk.Combobox(dlg, textvariable=status_var, width=20,
                     values=["scheduled", "completed", "cancelled"],
                     state="readonly").grid(row=2, column=1, padx=10, pady=5, sticky="w")
        fields["status"] = status_var

        tk.Label(dlg, text="Agenda:", bg="#ecf0f1").grid(row=3, column=0, padx=10, pady=5, sticky="ne")
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
                messagebox.showinfo("Success", "Meeting updated.")
                dlg.destroy()
                self._load_meetings()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(dlg, text="Save", command=save).grid(row=4, column=0, columnspan=2, pady=10)

    def _complete_meeting(self):
        mid = self._selected_meeting_id()
        if not mid:
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Complete Meeting #{mid}")
        dlg.geometry("450x350")
        dlg.configure(bg="#ecf0f1")
        dlg.grab_set()

        tk.Label(dlg, text="Minutes:", bg="#ecf0f1").pack(anchor="w", padx=10, pady=(10, 2))
        minutes_txt = tk.Text(dlg, width=50, height=8)
        minutes_txt.pack(padx=10, pady=2)

        tk.Label(dlg, text="Attendees (comma-separated):", bg="#ecf0f1").pack(anchor="w", padx=10, pady=(10, 2))
        attendees_ent = ttk.Entry(dlg, width=50)
        attendees_ent.pack(padx=10, pady=2)

        def save():
            try:
                minutes = minutes_txt.get("1.0", "end-1c").strip()
                attendees = attendees_ent.get().strip()
                if not minutes:
                    messagebox.showwarning("Warning", "Minutes are required.")
                    return
                if not attendees:
                    messagebox.showwarning("Warning", "Attendees are required.")
                    return
                self.svc.complete_meeting(int(mid), minutes, attendees)
                messagebox.showinfo("Success", "Meeting completed.")
                dlg.destroy()
                self._load_meetings()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(dlg, text="Complete", command=save).pack(pady=15)

    def _delete_meeting(self):
        mid = self._selected_meeting_id()
        if not mid:
            return
        if not messagebox.askyesno("Confirm", f"Delete meeting #{mid}?"):
            return
        try:
            self.svc.delete_meeting(int(mid))
            messagebox.showinfo("Success", "Meeting deleted.")
            self._load_meetings()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Proposal helpers ──

    def _selected_proposal_id(self):
        sel = self._prop_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Please select a proposal.")
            return None
        return self._prop_tree.item(sel[0], "values")[0]

    def _new_proposal(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Proposal")
        dlg.geometry("450x350")
        dlg.configure(bg="#ecf0f1")
        dlg.grab_set()

        fields = {}
        tk.Label(dlg, text="Title:", bg="#ecf0f1").grid(row=0, column=0, padx=10, pady=5, sticky="e")
        title_ent = ttk.Entry(dlg, width=30)
        title_ent.grid(row=0, column=1, padx=10, pady=5, sticky="w")
        fields["title"] = title_ent

        tk.Label(dlg, text="Proposed By (Member ID):", bg="#ecf0f1").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        by_ent = ttk.Entry(dlg, width=30)
        by_ent.grid(row=1, column=1, padx=10, pady=5, sticky="w")
        fields["proposed_by"] = by_ent

        tk.Label(dlg, text="Meeting ID:", bg="#ecf0f1").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        mtg_ent = ttk.Entry(dlg, width=30)
        mtg_ent.grid(row=2, column=1, padx=10, pady=5, sticky="w")
        fields["meeting_id"] = mtg_ent

        tk.Label(dlg, text="Category:", bg="#ecf0f1").grid(row=3, column=0, padx=10, pady=5, sticky="e")
        cat_var = tk.StringVar(value="general")
        ttk.Combobox(dlg, textvariable=cat_var, width=28,
                     values=["general", "facilities", "welfare", "academic",
                             "social", "environmental", "financial"],
                     state="readonly").grid(row=3, column=1, padx=10, pady=5, sticky="w")
        fields["category"] = cat_var

        tk.Label(dlg, text="Description:", bg="#ecf0f1").grid(row=4, column=0, padx=10, pady=5, sticky="ne")
        desc_txt = tk.Text(dlg, width=30, height=4)
        desc_txt.grid(row=4, column=1, padx=10, pady=5, sticky="w")
        fields["description"] = desc_txt

        def save():
            try:
                title = fields["title"].get().strip()
                if not title:
                    messagebox.showwarning("Warning", "Title is required.")
                    return
                by_str = fields["proposed_by"].get().strip()
                proposed_by = int(by_str) if by_str else None
                mtg_str = fields["meeting_id"].get().strip()
                meeting_id = int(mtg_str) if mtg_str else None
                category = fields["category"].get()
                description = fields["description"].get("1.0", "end-1c").strip() or None
                self.svc.create_proposal(title, proposed_by=proposed_by,
                                          meeting_id=meeting_id, description=description,
                                          category=category)
                messagebox.showinfo("Success", "Proposal created.")
                dlg.destroy()
                self._load_proposals()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(dlg, text="Save", command=save).grid(row=5, column=0, columnspan=2, pady=10)

    def _view_proposal(self):
        pid = self._selected_proposal_id()
        if not pid:
            return
        try:
            p = self.svc.get_proposal(int(pid))
            if not p:
                messagebox.showwarning("Warning", "Proposal not found.")
                return
            dlg = tk.Toplevel(self)
            dlg.title(f"Proposal #{p['id']}")
            dlg.geometry("500x450")
            dlg.configure(bg="#ecf0f1")
            proposer = ""
            if p.get("proposer_first_name"):
                proposer = f"{p['proposer_first_name']} {p['proposer_last_name']}"
            info = (
                f"ID: {p['id']}\n"
                f"Title: {p['title']}\n"
                f"Proposed By: {proposer or 'N/A'}\n"
                f"Category: {p['category']}\n"
                f"Meeting ID: {p.get('meeting_id') or 'N/A'}\n\n"
                f"Description:\n{p.get('description') or 'N/A'}\n\n"
                f"Votes: For={p['vote_for']}, Against={p['vote_against']}, "
                f"Abstain={p['vote_abstain']}\n"
                f"Outcome: {p.get('outcome') or 'N/A'}\n\n"
                f"Management Response:\n{p.get('management_response') or 'N/A'}\n\n"
                f"Implementation Status: {p['implementation_status']}\n"
                f"Created: {p.get('created_at') or 'N/A'}"
            )
            txt = tk.Text(dlg, wrap="word", font=("Helvetica", 11))
            txt.insert("1.0", info)
            txt.configure(state="disabled")
            txt.pack(fill="both", expand=True, padx=15, pady=15)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _record_votes(self):
        pid = self._selected_proposal_id()
        if not pid:
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Record Votes - Proposal #{pid}")
        dlg.geometry("350x250")
        dlg.configure(bg="#ecf0f1")
        dlg.grab_set()

        fields = {}
        for row, (label, key) in enumerate([
            ("Votes For:", "vote_for"),
            ("Votes Against:", "vote_against"),
            ("Votes Abstain:", "vote_abstain"),
            ("Outcome:", "outcome"),
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
                    messagebox.showwarning("Warning", "Outcome is required.")
                    return
                self.svc.record_votes(int(pid), vote_for, vote_against, vote_abstain, outcome)
                messagebox.showinfo("Success", "Votes recorded.")
                dlg.destroy()
                self._load_proposals()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(dlg, text="Save", command=save).grid(row=4, column=0, columnspan=2, pady=15)

    def _management_response(self):
        pid = self._selected_proposal_id()
        if not pid:
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Management Response - Proposal #{pid}")
        dlg.geometry("450x320")
        dlg.configure(bg="#ecf0f1")
        dlg.grab_set()

        tk.Label(dlg, text="Management Response:", bg="#ecf0f1").pack(anchor="w", padx=10, pady=(10, 2))
        response_txt = tk.Text(dlg, width=50, height=6)
        response_txt.pack(padx=10, pady=2)

        tk.Label(dlg, text="Implementation Status:", bg="#ecf0f1").pack(anchor="w", padx=10, pady=(10, 2))
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
                    messagebox.showwarning("Warning", "Response is required.")
                    return
                self.svc.respond_to_proposal(int(pid), response, impl_status)
                messagebox.showinfo("Success", "Response recorded.")
                dlg.destroy()
                self._load_proposals()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(dlg, text="Save", command=save).pack(pady=15)

    def _delete_proposal(self):
        pid = self._selected_proposal_id()
        if not pid:
            return
        if not messagebox.askyesno("Confirm", f"Delete proposal #{pid}?"):
            return
        try:
            self.svc.delete_proposal(int(pid))
            messagebox.showinfo("Success", "Proposal deleted.")
            self._load_proposals()
        except Exception as e:
            messagebox.showerror("Error", str(e))
