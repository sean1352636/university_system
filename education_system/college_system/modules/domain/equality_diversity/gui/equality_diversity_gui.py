"""Equality & Diversity GUI frame for protected characteristics, impact assessments, and objectives."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.equality_diversity.services.equality_diversity_service import EqualityDiversityService

PERSON_TYPES = ["student", "staff", "governor", "visitor"]
IMPACT_TYPES = ["positive", "neutral", "negative", "mixed"]
OBJ_STATUSES = ["active", "completed", "on_hold", "archived"]


class EqualityDiversityFrame(tk.Frame):
    """Equality & Diversity management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = EqualityDiversityService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Equality & Diversity",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._chars_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._chars_tab, text="Protected Characteristics")
        self._build_chars_tab()

        self._eia_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._eia_tab, text="Impact Assessments")
        self._build_eia_tab()

        self._obj_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._obj_tab, text="Objectives")
        self._build_obj_tab()

        self._stats_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._stats_tab, text="Statistics")
        self._build_stats_tab()

    # ---- Protected Characteristics Tab ----

    def _build_chars_tab(self):
        toolbar = tk.Frame(self._chars_tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text="Person Type:", bg="#ecf0f1").pack(side="left", padx=(5, 2))
        self._char_type = ttk.Combobox(toolbar, width=10, state="readonly",
                                        values=[""] + PERSON_TYPES)
        self._char_type.set("")
        self._char_type.pack(side="left", padx=2)

        tk.Label(toolbar, text="Person ID:", bg="#ecf0f1").pack(side="left", padx=(8, 2))
        self._char_pid = tk.Entry(toolbar, width=8)
        self._char_pid.pack(side="left", padx=2)

        ttk.Button(toolbar, text="Search", command=self._load_chars).pack(side="left", padx=5)
        ttk.Button(toolbar, text="New Record", command=self._new_char).pack(side="right", padx=5)
        ttk.Button(toolbar, text="Delete", command=self._delete_char).pack(side="right", padx=2)
        ttk.Button(toolbar, text="Edit", command=self._edit_char).pack(side="right", padx=2)
        ttk.Button(toolbar, text="View", command=self._view_char).pack(side="right", padx=2)

        cols = ("id", "person_type", "person_id", "ethnicity", "religion",
                "gender_identity", "disability", "pronouns")
        self._char_tree = ttk.Treeview(self._chars_tab, columns=cols,
                                        show="headings", height=15)
        for c, w, label in [
            ("id", 40, "ID"), ("person_type", 80, "Type"),
            ("person_id", 70, "Person ID"), ("ethnicity", 110, "Ethnicity"),
            ("religion", 90, "Religion"), ("gender_identity", 100, "Gender"),
            ("disability", 90, "Disability"), ("pronouns", 80, "Pronouns"),
        ]:
            self._char_tree.heading(c, text=label)
            self._char_tree.column(c, width=w,
                                    anchor="center" if w < 80 else "w")
        self._char_tree.bind("<Double-1>", lambda e: self._view_char())

        vsb = ttk.Scrollbar(self._chars_tab, orient="vertical",
                             command=self._char_tree.yview)
        self._char_tree.configure(yscrollcommand=vsb.set)
        self._char_tree.pack(side="left", fill="both", expand=True,
                              padx=(5, 0), pady=5)
        vsb.pack(side="right", fill="y", padx=(0, 5), pady=5)

    def _load_chars(self):
        for item in self._char_tree.get_children():
            self._char_tree.delete(item)
        try:
            ptype = self._char_type.get().strip() or None
            pid = self._char_pid.get().strip()
            records = self._svc.list_characteristics(
                person_type=ptype,
                person_id=int(pid) if pid else None)
            for r in records:
                self._char_tree.insert("", "end", iid=r["id"], values=(
                    r["id"], r.get("person_type", ""),
                    r.get("person_id", ""), r.get("ethnicity", ""),
                    r.get("religion", ""), r.get("gender_identity", ""),
                    r.get("disability_status", ""),
                    r.get("preferred_pronouns", "")))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selected_char_id(self):
        sel = self._char_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a record first.")
            return None
        return int(sel[0])

    def _char_form(self, win, rec=None):
        """Build common form fields for characteristics. Returns (fields dict, row)."""
        rec = rec or {}
        fields = {}
        row = 0

        tk.Label(win, text="Person Type*:").grid(row=row, column=0, padx=10,
                                                  pady=4, sticky="e")
        ptype_cb = ttk.Combobox(win, width=25, state="readonly",
                                 values=PERSON_TYPES)
        ptype_cb.set(rec.get("person_type", "student"))
        ptype_cb.grid(row=row, column=1, padx=10, pady=4)
        fields["_ptype_cb"] = ptype_cb
        row += 1

        for label, key in [
            ("Person ID*:", "person_id"),
            ("Ethnicity:", "ethnicity"), ("Religion:", "religion"),
            ("Sexual Orientation:", "sexual_orientation"),
            ("Gender Identity:", "gender_identity"),
            ("Disability Status:", "disability_status"),
            ("Disability Details:", "disability_details"),
            ("Marital Status:", "marital_status"),
            ("Pregnancy/Maternity:", "pregnancy_maternity"),
            ("Preferred Pronouns:", "preferred_pronouns"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10,
                                            pady=4, sticky="e")
            e = tk.Entry(win, width=28)
            e.insert(0, str(rec.get(key, "") or ""))
            e.grid(row=row, column=1, padx=10, pady=4)
            fields[key] = e
            row += 1

        consent_var = tk.BooleanVar(value=bool(rec.get("consent_given", 1)))
        ttk.Checkbutton(win, text="Consent Given", variable=consent_var).grid(
            row=row, column=1, sticky="w", padx=10, pady=2)
        fields["_consent_var"] = consent_var
        row += 1

        return fields, row

    def _new_char(self):
        win = tk.Toplevel(self)
        win.title("New Protected Characteristics Record")
        win.geometry("480x500")
        win.resizable(False, False)

        fields, row = self._char_form(win)

        def save():
            pid = fields["person_id"].get().strip()
            if not pid:
                messagebox.showwarning("Validation", "Person ID is required.")
                return
            try:
                self._svc.create_characteristic(
                    fields["_ptype_cb"].get(), int(pid),
                    ethnicity=fields["ethnicity"].get().strip() or None,
                    religion=fields["religion"].get().strip() or None,
                    sexual_orientation=fields["sexual_orientation"].get().strip() or None,
                    gender_identity=fields["gender_identity"].get().strip() or None,
                    disability_status=fields["disability_status"].get().strip() or None,
                    disability_details=fields["disability_details"].get().strip() or None,
                    marital_status=fields["marital_status"].get().strip() or None,
                    pregnancy_maternity=fields["pregnancy_maternity"].get().strip() or None,
                    preferred_pronouns=fields["preferred_pronouns"].get().strip() or None,
                    consent_given=1 if fields["_consent_var"].get() else 0)
                messagebox.showinfo("Success", "Record created.")
                win.destroy()
                self._load_chars()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _view_char(self):
        cid = self._selected_char_id()
        if not cid:
            return
        rec = self._svc.get_characteristic(cid)
        if not rec:
            messagebox.showwarning("Not Found", "Record not found.")
            return

        win = tk.Toplevel(self)
        win.title(f"Characteristics #{cid}")
        win.geometry("440x440")
        win.resizable(False, False)

        display = [
            ("ID", rec.get("id")),
            ("Person Type", rec.get("person_type")),
            ("Person ID", rec.get("person_id")),
            ("Ethnicity", rec.get("ethnicity")),
            ("Religion", rec.get("religion")),
            ("Sexual Orientation", rec.get("sexual_orientation")),
            ("Gender Identity", rec.get("gender_identity")),
            ("Disability Status", rec.get("disability_status")),
            ("Disability Details", rec.get("disability_details")),
            ("Marital Status", rec.get("marital_status")),
            ("Pregnancy/Maternity", rec.get("pregnancy_maternity")),
            ("Preferred Pronouns", rec.get("preferred_pronouns")),
            ("Consent Given", "Yes" if rec.get("consent_given") else "No"),
            ("Collected", rec.get("collection_date")),
        ]
        frame = tk.Frame(win, padx=15, pady=10)
        frame.pack(fill="both", expand=True)
        for i, (lbl, val) in enumerate(display):
            tk.Label(frame, text=f"{lbl}:", font=("Helvetica", 10, "bold"),
                     anchor="e").grid(row=i, column=0, sticky="ne",
                                       padx=(0, 8), pady=2)
            tk.Label(frame, text=str(val or ""), anchor="w",
                     wraplength=260).grid(row=i, column=1, sticky="w", pady=2)

    def _edit_char(self):
        cid = self._selected_char_id()
        if not cid:
            return
        rec = self._svc.get_characteristic(cid)
        if not rec:
            return

        win = tk.Toplevel(self)
        win.title(f"Edit Characteristics #{cid}")
        win.geometry("480x500")
        win.resizable(False, False)

        fields, row = self._char_form(win, rec)

        def save():
            try:
                self._svc.update_characteristic(
                    cid,
                    ethnicity=fields["ethnicity"].get().strip() or None,
                    religion=fields["religion"].get().strip() or None,
                    sexual_orientation=fields["sexual_orientation"].get().strip() or None,
                    gender_identity=fields["gender_identity"].get().strip() or None,
                    disability_status=fields["disability_status"].get().strip() or None,
                    disability_details=fields["disability_details"].get().strip() or None,
                    marital_status=fields["marital_status"].get().strip() or None,
                    pregnancy_maternity=fields["pregnancy_maternity"].get().strip() or None,
                    preferred_pronouns=fields["preferred_pronouns"].get().strip() or None,
                    consent_given=1 if fields["_consent_var"].get() else 0)
                messagebox.showinfo("Success", "Record updated.")
                win.destroy()
                self._load_chars()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _delete_char(self):
        cid = self._selected_char_id()
        if not cid:
            return
        if not messagebox.askyesno("Confirm", f"Delete record #{cid}?"):
            return
        try:
            self._svc.delete_characteristic(cid)
            messagebox.showinfo("Deleted", "Record deleted.")
            self._load_chars()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---- Impact Assessments Tab ----

    def _build_eia_tab(self):
        toolbar = tk.Frame(self._eia_tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text="Impact:", bg="#ecf0f1").pack(side="left", padx=(5, 2))
        self._eia_impact = ttk.Combobox(toolbar, width=10, state="readonly",
                                         values=[""] + IMPACT_TYPES)
        self._eia_impact.set("")
        self._eia_impact.pack(side="left", padx=2)

        ttk.Button(toolbar, text="Refresh", command=self._load_eia).pack(side="left", padx=5)
        ttk.Button(toolbar, text="New Assessment", command=self._new_eia).pack(side="right", padx=5)
        ttk.Button(toolbar, text="Delete", command=self._delete_eia).pack(side="right", padx=2)
        ttk.Button(toolbar, text="Edit", command=self._edit_eia).pack(side="right", padx=2)

        cols = ("id", "policy", "assessor", "date", "group",
                "impact_type", "status")
        self._eia_tree = ttk.Treeview(self._eia_tab, columns=cols,
                                       show="headings", height=15)
        for c, w, label in [
            ("id", 40, "ID"), ("policy", 200, "Policy/Practice"),
            ("assessor", 110, "Assessor"), ("date", 90, "Date"),
            ("group", 110, "Protected Group"),
            ("impact_type", 80, "Impact"), ("status", 70, "Status"),
        ]:
            self._eia_tree.heading(c, text=label)
            self._eia_tree.column(c, width=w,
                                   anchor="center" if w < 80 else "w")

        vsb = ttk.Scrollbar(self._eia_tab, orient="vertical",
                             command=self._eia_tree.yview)
        self._eia_tree.configure(yscrollcommand=vsb.set)
        self._eia_tree.pack(side="left", fill="both", expand=True,
                             padx=(5, 0), pady=5)
        vsb.pack(side="right", fill="y", padx=(0, 5), pady=5)

    def _load_eia(self):
        for item in self._eia_tree.get_children():
            self._eia_tree.delete(item)
        try:
            impact = self._eia_impact.get().strip() or None
            records = self._svc.list_assessments(impact_type=impact)
            for r in records:
                self._eia_tree.insert("", "end", iid=r["id"], values=(
                    r["id"], r.get("policy_or_practice", ""),
                    r.get("assessor", ""), r.get("assessment_date", ""),
                    r.get("protected_group", ""),
                    r.get("impact_type", ""), r.get("status", "")))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _new_eia(self):
        win = tk.Toplevel(self)
        win.title("New Equality Impact Assessment")
        win.geometry("480x420")
        win.resizable(False, False)

        fields = {}
        row = 0
        for label, key in [
            ("Policy/Practice*:", "policy_or_practice"),
            ("Assessor:", "assessor"),
            ("Date (YYYY-MM-DD):", "assessment_date"),
            ("Protected Group:", "protected_group"),
            ("Review Date:", "review_date"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10,
                                            pady=4, sticky="e")
            e = tk.Entry(win, width=30)
            e.grid(row=row, column=1, padx=10, pady=4)
            fields[key] = e
            row += 1

        tk.Label(win, text="Impact Type:").grid(row=row, column=0, padx=10,
                                                 pady=4, sticky="e")
        impact_cb = ttk.Combobox(win, width=27, state="readonly",
                                  values=IMPACT_TYPES)
        impact_cb.set("neutral")
        impact_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text="Potential Impact:").grid(row=row, column=0,
                                                      padx=10, pady=4, sticky="ne")
        pi_txt = tk.Text(win, width=30, height=3)
        pi_txt.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text="Mitigating Actions:").grid(row=row, column=0,
                                                        padx=10, pady=4, sticky="ne")
        ma_txt = tk.Text(win, width=30, height=3)
        ma_txt.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        def save():
            policy = fields["policy_or_practice"].get().strip()
            if not policy:
                messagebox.showwarning("Validation",
                                        "Policy/Practice is required.")
                return
            try:
                self._svc.create_assessment(
                    policy,
                    assessor=fields["assessor"].get().strip() or None,
                    assessment_date=fields["assessment_date"].get().strip() or None,
                    protected_group=fields["protected_group"].get().strip() or None,
                    impact_type=impact_cb.get(),
                    potential_impact=pi_txt.get("1.0", "end-1c").strip() or None,
                    mitigating_actions=ma_txt.get("1.0", "end-1c").strip() or None,
                    review_date=fields["review_date"].get().strip() or None)
                messagebox.showinfo("Success", "Assessment created.")
                win.destroy()
                self._load_eia()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _edit_eia(self):
        sel = self._eia_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select an assessment.")
            return
        eid = int(sel[0])
        rec = self._svc.get_assessment(eid)
        if not rec:
            return

        win = tk.Toplevel(self)
        win.title(f"Edit Assessment #{eid}")
        win.geometry("480x480")
        win.resizable(False, False)

        fields = {}
        row = 0
        for label, key in [
            ("Policy/Practice*:", "policy_or_practice"),
            ("Assessor:", "assessor"),
            ("Date:", "assessment_date"),
            ("Protected Group:", "protected_group"),
            ("Review Date:", "review_date"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10,
                                            pady=4, sticky="e")
            e = tk.Entry(win, width=30)
            e.insert(0, str(rec.get(key, "") or ""))
            e.grid(row=row, column=1, padx=10, pady=4)
            fields[key] = e
            row += 1

        tk.Label(win, text="Impact Type:").grid(row=row, column=0, padx=10,
                                                 pady=4, sticky="e")
        impact_cb = ttk.Combobox(win, width=27, state="readonly",
                                  values=IMPACT_TYPES)
        impact_cb.set(rec.get("impact_type", "neutral"))
        impact_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text="Status:").grid(row=row, column=0, padx=10,
                                            pady=4, sticky="e")
        status_cb = ttk.Combobox(win, width=27, state="readonly",
                                  values=["active", "archived", "under_review"])
        status_cb.set(rec.get("status", "active"))
        status_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text="Potential Impact:").grid(row=row, column=0,
                                                      padx=10, pady=4, sticky="ne")
        pi_txt = tk.Text(win, width=30, height=3)
        pi_txt.insert("1.0", rec.get("potential_impact", "") or "")
        pi_txt.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text="Mitigating Actions:").grid(row=row, column=0,
                                                        padx=10, pady=4, sticky="ne")
        ma_txt = tk.Text(win, width=30, height=3)
        ma_txt.insert("1.0", rec.get("mitigating_actions", "") or "")
        ma_txt.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        def save():
            try:
                self._svc.update_assessment(
                    eid,
                    policy_or_practice=fields["policy_or_practice"].get().strip(),
                    assessor=fields["assessor"].get().strip() or None,
                    assessment_date=fields["assessment_date"].get().strip() or None,
                    protected_group=fields["protected_group"].get().strip() or None,
                    impact_type=impact_cb.get(),
                    status=status_cb.get(),
                    potential_impact=pi_txt.get("1.0", "end-1c").strip() or None,
                    mitigating_actions=ma_txt.get("1.0", "end-1c").strip() or None,
                    review_date=fields["review_date"].get().strip() or None)
                messagebox.showinfo("Success", "Assessment updated.")
                win.destroy()
                self._load_eia()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _delete_eia(self):
        sel = self._eia_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select an assessment.")
            return
        eid = int(sel[0])
        if not messagebox.askyesno("Confirm", f"Delete assessment #{eid}?"):
            return
        try:
            self._svc.delete_assessment(eid)
            messagebox.showinfo("Deleted", "Assessment deleted.")
            self._load_eia()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---- Objectives Tab ----

    def _build_obj_tab(self):
        toolbar = tk.Frame(self._obj_tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text="Status:", bg="#ecf0f1").pack(side="left", padx=(5, 2))
        self._obj_status = ttk.Combobox(toolbar, width=10, state="readonly",
                                         values=[""] + OBJ_STATUSES)
        self._obj_status.set("")
        self._obj_status.pack(side="left", padx=2)

        tk.Label(toolbar, text="Year:", bg="#ecf0f1").pack(side="left", padx=(8, 2))
        self._obj_year = tk.Entry(toolbar, width=8)
        self._obj_year.pack(side="left", padx=2)

        ttk.Button(toolbar, text="Refresh", command=self._load_obj).pack(side="left", padx=5)
        ttk.Button(toolbar, text="New Objective", command=self._new_obj).pack(side="right", padx=5)
        ttk.Button(toolbar, text="Delete", command=self._delete_obj).pack(side="right", padx=2)
        ttk.Button(toolbar, text="Edit", command=self._edit_obj).pack(side="right", padx=2)

        cols = ("id", "objective", "group", "target", "progress",
                "year", "status")
        self._obj_tree = ttk.Treeview(self._obj_tab, columns=cols,
                                       show="headings", height=15)
        for c, w, label in [
            ("id", 40, "ID"), ("objective", 220, "Objective"),
            ("group", 110, "Protected Group"), ("target", 110, "Target"),
            ("progress", 110, "Progress"), ("year", 70, "Year"),
            ("status", 70, "Status"),
        ]:
            self._obj_tree.heading(c, text=label)
            self._obj_tree.column(c, width=w,
                                   anchor="center" if w < 80 else "w")

        vsb = ttk.Scrollbar(self._obj_tab, orient="vertical",
                             command=self._obj_tree.yview)
        self._obj_tree.configure(yscrollcommand=vsb.set)
        self._obj_tree.pack(side="left", fill="both", expand=True,
                             padx=(5, 0), pady=5)
        vsb.pack(side="right", fill="y", padx=(0, 5), pady=5)

    def _load_obj(self):
        for item in self._obj_tree.get_children():
            self._obj_tree.delete(item)
        try:
            status = self._obj_status.get().strip() or None
            year = self._obj_year.get().strip() or None
            records = self._svc.list_objectives(status=status,
                                                 academic_year=year)
            for r in records:
                self._obj_tree.insert("", "end", iid=r["id"], values=(
                    r["id"], (r.get("objective", "") or "")[:60],
                    r.get("protected_group", ""), r.get("target", ""),
                    r.get("progress", ""), r.get("academic_year", ""),
                    r.get("status", "")))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _new_obj(self):
        win = tk.Toplevel(self)
        win.title("New Equality Objective")
        win.geometry("460x360")
        win.resizable(False, False)

        fields = {}
        row = 0
        for label, key in [
            ("Protected Group:", "protected_group"),
            ("Target:", "target"),
            ("Academic Year:", "academic_year"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10,
                                            pady=5, sticky="e")
            e = tk.Entry(win, width=30)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1

        tk.Label(win, text="Objective*:").grid(row=row, column=0, padx=10,
                                                pady=5, sticky="ne")
        obj_txt = tk.Text(win, width=30, height=3)
        obj_txt.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text="Progress:").grid(row=row, column=0, padx=10,
                                              pady=5, sticky="ne")
        prog_txt = tk.Text(win, width=30, height=3)
        prog_txt.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            obj = obj_txt.get("1.0", "end-1c").strip()
            if not obj:
                messagebox.showwarning("Validation", "Objective is required.")
                return
            try:
                self._svc.create_objective(
                    obj,
                    protected_group=fields["protected_group"].get().strip() or None,
                    target=fields["target"].get().strip() or None,
                    progress=prog_txt.get("1.0", "end-1c").strip() or None,
                    academic_year=fields["academic_year"].get().strip() or None)
                messagebox.showinfo("Success", "Objective created.")
                win.destroy()
                self._load_obj()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _edit_obj(self):
        sel = self._obj_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select an objective.")
            return
        oid = int(sel[0])
        rec = self._svc.get_objective(oid)
        if not rec:
            return

        win = tk.Toplevel(self)
        win.title(f"Edit Objective #{oid}")
        win.geometry("460x420")
        win.resizable(False, False)

        fields = {}
        row = 0
        for label, key in [
            ("Protected Group:", "protected_group"),
            ("Target:", "target"),
            ("Academic Year:", "academic_year"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10,
                                            pady=5, sticky="e")
            e = tk.Entry(win, width=30)
            e.insert(0, str(rec.get(key, "") or ""))
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1

        tk.Label(win, text="Status:").grid(row=row, column=0, padx=10,
                                            pady=5, sticky="e")
        status_cb = ttk.Combobox(win, width=27, state="readonly",
                                  values=OBJ_STATUSES)
        status_cb.set(rec.get("status", "active"))
        status_cb.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text="Objective*:").grid(row=row, column=0, padx=10,
                                                pady=5, sticky="ne")
        obj_txt = tk.Text(win, width=30, height=3)
        obj_txt.insert("1.0", rec.get("objective", "") or "")
        obj_txt.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text="Progress:").grid(row=row, column=0, padx=10,
                                              pady=5, sticky="ne")
        prog_txt = tk.Text(win, width=30, height=3)
        prog_txt.insert("1.0", rec.get("progress", "") or "")
        prog_txt.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            try:
                self._svc.update_objective(
                    oid,
                    objective=obj_txt.get("1.0", "end-1c").strip(),
                    protected_group=fields["protected_group"].get().strip() or None,
                    target=fields["target"].get().strip() or None,
                    progress=prog_txt.get("1.0", "end-1c").strip() or None,
                    academic_year=fields["academic_year"].get().strip() or None,
                    status=status_cb.get())
                messagebox.showinfo("Success", "Objective updated.")
                win.destroy()
                self._load_obj()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _delete_obj(self):
        sel = self._obj_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select an objective.")
            return
        oid = int(sel[0])
        if not messagebox.askyesno("Confirm", f"Delete objective #{oid}?"):
            return
        try:
            self._svc.delete_objective(oid)
            messagebox.showinfo("Deleted", "Objective deleted.")
            self._load_obj()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---- Statistics Tab ----

    def _build_stats_tab(self):
        self._stats_frame = tk.Frame(self._stats_tab, bg="#ecf0f1",
                                      padx=20, pady=20)
        self._stats_frame.pack(fill="both", expand=True)

        ttk.Button(self._stats_frame, text="Refresh Statistics",
                   command=self._load_stats).pack(anchor="w", pady=(0, 15))

        self._stats_labels = {}
        for key, label in [
            ("total_records", "Total Characteristics Records"),
            ("student_records", "Student Records"),
            ("staff_records", "Staff Records"),
            ("disability_declared", "Disability Declared"),
            ("total_assessments", "Total Impact Assessments"),
            ("active_assessments", "Active Assessments"),
            ("total_objectives", "Total Objectives"),
            ("active_objectives", "Active Objectives"),
        ]:
            row_frame = tk.Frame(self._stats_frame, bg="#ecf0f1")
            row_frame.pack(fill="x", pady=3)
            tk.Label(row_frame, text=f"{label}:",
                     font=("Helvetica", 11, "bold"), bg="#ecf0f1",
                     width=28, anchor="e").pack(side="left")
            lbl = tk.Label(row_frame, text="—", font=("Helvetica", 11),
                           bg="#ecf0f1", anchor="w")
            lbl.pack(side="left", padx=(10, 0))
            self._stats_labels[key] = lbl

    def _load_stats(self):
        try:
            stats = self._svc.get_stats()
            for key, lbl in self._stats_labels.items():
                lbl.config(text=str(stats.get(key, 0)))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refresh(self):
        self._load_chars()
        self._load_eia()
        self._load_obj()
        self._load_stats()
