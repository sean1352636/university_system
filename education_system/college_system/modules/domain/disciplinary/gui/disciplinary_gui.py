"""Disciplinary & Appeals GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.disciplinary.services.disciplinary_service import DisciplinaryService


CASE_TYPES = ["misconduct", "gross_misconduct", "academic_misconduct", "behavioural"]

CASE_STATUSES = ["under_investigation", "hearing_scheduled", "hearing_completed",
                 "sanctioned", "appealed", "closed"]

PERSON_TYPES = ["student", "staff"]

EVIDENCE_TYPES = ["document", "witness_statement", "cctv", "digital",
                  "physical", "other"]

APPEAL_STATUSES = ["submitted", "hearing_scheduled", "upheld", "rejected",
                   "modified"]


class DisciplinaryFrame(tk.Frame):
    """Disciplinary & Appeals management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = DisciplinaryService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Disciplinary & Appeals",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._cases_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._cases_tab, text="Cases")
        self._build_cases_tab()

        self._evidence_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._evidence_tab, text="Evidence")
        self._build_evidence_tab()

        self._appeals_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._appeals_tab, text="Appeals")
        self._build_appeals_tab()

        self._stats_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._stats_tab, text="Statistics")
        self._build_stats_tab()

    # ---- Cases Tab ----

    def _build_cases_tab(self):
        toolbar = tk.Frame(self._cases_tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text="Status:", bg="#ecf0f1").pack(side="left", padx=(5, 2))
        self._case_status_filter = ttk.Combobox(
            toolbar, width=16, state="readonly",
            values=[""] + CASE_STATUSES)
        self._case_status_filter.set("")
        self._case_status_filter.pack(side="left", padx=2)

        tk.Label(toolbar, text="Person Type:", bg="#ecf0f1").pack(
            side="left", padx=(8, 2))
        self._case_person_filter = ttk.Combobox(
            toolbar, width=10, state="readonly",
            values=[""] + PERSON_TYPES)
        self._case_person_filter.set("")
        self._case_person_filter.pack(side="left", padx=2)

        ttk.Button(toolbar, text="Search",
                   command=self._load_cases).pack(side="left", padx=5)

        btn_frame = tk.Frame(self._cases_tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", padx=5, pady=(0, 5))
        ttk.Button(btn_frame, text="Refresh",
                   command=self._load_cases).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="New Case",
                   command=self._new_case).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="View",
                   command=self._view_case).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Update",
                   command=self._update_case).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Schedule Hearing",
                   command=self._schedule_hearing).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Record Outcome",
                   command=self._record_outcome).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Delete",
                   command=self._delete_case).pack(side="right", padx=2)

        cols = ("id", "reference", "person_type", "person_id",
                "case_type", "allegation", "status")
        self._case_tree = ttk.Treeview(
            self._cases_tab, columns=cols, show="headings", height=16)
        for c, w, label in [
            ("id", 40, "ID"), ("reference", 100, "Reference"),
            ("person_type", 80, "Person Type"), ("person_id", 70, "Person ID"),
            ("case_type", 120, "Type"), ("allegation", 260, "Allegation"),
            ("status", 130, "Status"),
        ]:
            self._case_tree.heading(c, text=label)
            self._case_tree.column(c, width=w,
                                   anchor="center" if w < 80 else "w")
        self._case_tree.bind("<Double-1>", lambda e: self._view_case())

        vsb = ttk.Scrollbar(self._cases_tab, orient="vertical",
                            command=self._case_tree.yview)
        self._case_tree.configure(yscrollcommand=vsb.set)
        self._case_tree.pack(side="left", fill="both", expand=True,
                             padx=(5, 0), pady=5)
        vsb.pack(side="right", fill="y", padx=(0, 5), pady=5)

    def _load_cases(self):
        for item in self._case_tree.get_children():
            self._case_tree.delete(item)
        try:
            status = self._case_status_filter.get().strip() or None
            person_type = self._case_person_filter.get().strip() or None
            records = self._svc.list_cases(
                status=status, person_type=person_type)
            for r in records:
                self._case_tree.insert("", "end", iid=r["id"], values=(
                    r["id"], r.get("case_reference", ""),
                    r.get("person_type", ""), r.get("person_id", ""),
                    r.get("case_type", ""),
                    (r.get("allegation", "") or "")[:80],
                    r.get("status", "")))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selected_case_id(self):
        sel = self._case_tree.selection()
        if not sel:
            messagebox.showwarning("Selection",
                                   "Please select a case first.")
            return None
        return int(sel[0])

    def _new_case(self):
        win = tk.Toplevel(self)
        win.title("New Disciplinary Case")
        win.geometry("500x520")
        win.resizable(False, False)

        fields = {}
        row = 0

        tk.Label(win, text="Person Type*:").grid(
            row=row, column=0, padx=10, pady=4, sticky="e")
        ptype_cb = ttk.Combobox(win, width=29, state="readonly",
                                values=PERSON_TYPES)
        ptype_cb.set("student")
        ptype_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        for label, key in [
            ("Person ID*:", "person_id"),
            ("Case Reference:", "case_reference"),
            ("Reported By (User ID):", "reported_by"),
            ("Reported Date (YYYY-MM-DD):", "reported_date"),
            ("Investigating Officer (ID):", "investigating_officer"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10,
                                           pady=4, sticky="e")
            e = tk.Entry(win, width=32)
            e.grid(row=row, column=1, padx=10, pady=4)
            fields[key] = e
            row += 1

        tk.Label(win, text="Case Type:").grid(
            row=row, column=0, padx=10, pady=4, sticky="e")
        ctype_cb = ttk.Combobox(win, width=29, state="readonly",
                                values=CASE_TYPES)
        ctype_cb.set("misconduct")
        ctype_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text="Allegation*:").grid(
            row=row, column=0, padx=10, pady=4, sticky="ne")
        allg_txt = tk.Text(win, width=32, height=5)
        allg_txt.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text="Notes:").grid(
            row=row, column=0, padx=10, pady=4, sticky="ne")
        notes_txt = tk.Text(win, width=32, height=3)
        notes_txt.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        def save():
            person_id_str = fields["person_id"].get().strip()
            allegation = allg_txt.get("1.0", "end-1c").strip()
            if not person_id_str or not allegation:
                messagebox.showwarning("Validation",
                                       "Person ID and allegation are required.")
                return
            try:
                person_id = int(person_id_str)
            except ValueError:
                messagebox.showwarning("Validation",
                                       "Person ID must be a number.")
                return
            kwargs = {
                "case_type": ctype_cb.get(),
            }
            ref = fields["case_reference"].get().strip()
            if ref:
                kwargs["case_reference"] = ref
            reported_by = fields["reported_by"].get().strip()
            if reported_by:
                kwargs["reported_by"] = int(reported_by)
            reported_date = fields["reported_date"].get().strip()
            if reported_date:
                kwargs["reported_date"] = reported_date
            inv_officer = fields["investigating_officer"].get().strip()
            if inv_officer:
                kwargs["investigating_officer"] = int(inv_officer)
            notes = notes_txt.get("1.0", "end-1c").strip()
            if notes:
                kwargs["notes"] = notes
            try:
                self._svc.create_case(ptype_cb.get(), person_id,
                                      allegation, **kwargs)
                messagebox.showinfo("Success", "Disciplinary case created.")
                win.destroy()
                self._load_cases()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _view_case(self):
        cid = self._selected_case_id()
        if not cid:
            return
        rec = self._svc.get_case(cid)
        if not rec:
            messagebox.showwarning("Not Found", "Case not found.")
            return

        win = tk.Toplevel(self)
        win.title(f"Disciplinary Case #{cid}")
        win.geometry("520x560")
        win.resizable(False, False)

        canvas = tk.Canvas(win, borderwidth=0)
        scroll = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, padx=15, pady=10)
        frame.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        display = [
            ("ID", rec.get("id")),
            ("Case Reference", rec.get("case_reference")),
            ("Person Type", rec.get("person_type")),
            ("Person ID", rec.get("person_id")),
            ("Case Type", rec.get("case_type")),
            ("Allegation", rec.get("allegation")),
            ("Reported By", rec.get("reported_by")),
            ("Reported Date", rec.get("reported_date")),
            ("Investigating Officer", rec.get("investigating_officer")),
            ("Hearing Date", rec.get("hearing_date")),
            ("Hearing Panel", rec.get("hearing_panel")),
            ("Hearing Outcome", rec.get("hearing_outcome")),
            ("Sanction", rec.get("sanction")),
            ("Sanction Start", rec.get("sanction_start_date")),
            ("Sanction End", rec.get("sanction_end_date")),
            ("Appeal Deadline", rec.get("appeal_deadline")),
            ("Status", rec.get("status")),
            ("Notes", rec.get("notes")),
            ("Created", rec.get("created_at")),
            ("Updated", rec.get("updated_at")),
        ]

        for i, (lbl, val) in enumerate(display):
            tk.Label(frame, text=f"{lbl}:", font=("Helvetica", 10, "bold"),
                     anchor="e").grid(row=i, column=0, sticky="ne",
                                      padx=(0, 8), pady=2)
            tk.Label(frame, text=str(val or ""), anchor="w",
                     wraplength=340).grid(row=i, column=1, sticky="w", pady=2)

    def _update_case(self):
        cid = self._selected_case_id()
        if not cid:
            return
        rec = self._svc.get_case(cid)
        if not rec:
            messagebox.showwarning("Not Found", "Case not found.")
            return

        win = tk.Toplevel(self)
        win.title(f"Update Case #{cid}")
        win.geometry("520x580")
        win.resizable(False, False)

        fields = {}
        row = 0

        tk.Label(win, text="Person Type:").grid(
            row=row, column=0, padx=10, pady=4, sticky="e")
        ptype_cb = ttk.Combobox(win, width=29, state="readonly",
                                values=PERSON_TYPES)
        ptype_cb.set(rec.get("person_type", "student"))
        ptype_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        for label, key in [
            ("Person ID:", "person_id"),
            ("Case Reference:", "case_reference"),
            ("Reported By:", "reported_by"),
            ("Reported Date:", "reported_date"),
            ("Investigating Officer:", "investigating_officer"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10,
                                           pady=4, sticky="e")
            e = tk.Entry(win, width=32)
            e.insert(0, str(rec.get(key, "") or ""))
            e.grid(row=row, column=1, padx=10, pady=4)
            fields[key] = e
            row += 1

        tk.Label(win, text="Case Type:").grid(
            row=row, column=0, padx=10, pady=4, sticky="e")
        ctype_cb = ttk.Combobox(win, width=29, state="readonly",
                                values=CASE_TYPES)
        ctype_cb.set(rec.get("case_type", "misconduct"))
        ctype_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text="Status:").grid(
            row=row, column=0, padx=10, pady=4, sticky="e")
        status_cb = ttk.Combobox(win, width=29, state="readonly",
                                 values=CASE_STATUSES)
        status_cb.set(rec.get("status", "under_investigation"))
        status_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text="Allegation:").grid(
            row=row, column=0, padx=10, pady=4, sticky="ne")
        allg_txt = tk.Text(win, width=32, height=4)
        allg_txt.insert("1.0", rec.get("allegation", "") or "")
        allg_txt.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text="Notes:").grid(
            row=row, column=0, padx=10, pady=4, sticky="ne")
        notes_txt = tk.Text(win, width=32, height=3)
        notes_txt.insert("1.0", rec.get("notes", "") or "")
        notes_txt.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        def save():
            kwargs = {
                "person_type": ptype_cb.get(),
                "case_type": ctype_cb.get(),
                "status": status_cb.get(),
                "allegation": allg_txt.get("1.0", "end-1c").strip() or None,
                "notes": notes_txt.get("1.0", "end-1c").strip() or None,
            }
            pid = fields["person_id"].get().strip()
            if pid:
                kwargs["person_id"] = int(pid)
            ref = fields["case_reference"].get().strip()
            if ref:
                kwargs["case_reference"] = ref
            rb = fields["reported_by"].get().strip()
            if rb:
                kwargs["reported_by"] = int(rb)
            rd = fields["reported_date"].get().strip()
            if rd:
                kwargs["reported_date"] = rd
            io = fields["investigating_officer"].get().strip()
            if io:
                kwargs["investigating_officer"] = int(io)
            try:
                self._svc.update_case(cid, **kwargs)
                messagebox.showinfo("Success", "Case updated.")
                win.destroy()
                self._load_cases()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _schedule_hearing(self):
        cid = self._selected_case_id()
        if not cid:
            return

        win = tk.Toplevel(self)
        win.title(f"Schedule Hearing - Case #{cid}")
        win.geometry("420x200")
        win.resizable(False, False)

        tk.Label(win, text="Hearing Date* (YYYY-MM-DD):").grid(
            row=0, column=0, padx=10, pady=8, sticky="e")
        date_entry = tk.Entry(win, width=24)
        date_entry.grid(row=0, column=1, padx=10, pady=8)

        tk.Label(win, text="Panel Members:").grid(
            row=1, column=0, padx=10, pady=8, sticky="e")
        panel_entry = tk.Entry(win, width=24)
        panel_entry.grid(row=1, column=1, padx=10, pady=8)

        def save():
            hdate = date_entry.get().strip()
            if not hdate:
                messagebox.showwarning("Validation",
                                       "Hearing date is required.")
                return
            panel = panel_entry.get().strip() or None
            try:
                self._svc.schedule_hearing(cid, hdate, panel)
                messagebox.showinfo("Success", "Hearing scheduled.")
                win.destroy()
                self._load_cases()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Schedule", command=save).grid(
            row=2, column=0, columnspan=2, pady=12)

    def _record_outcome(self):
        cid = self._selected_case_id()
        if not cid:
            return

        win = tk.Toplevel(self)
        win.title(f"Record Outcome - Case #{cid}")
        win.geometry("460x380")
        win.resizable(False, False)

        tk.Label(win, text="Outcome*:").grid(
            row=0, column=0, padx=10, pady=6, sticky="ne")
        outcome_txt = tk.Text(win, width=30, height=3)
        outcome_txt.grid(row=0, column=1, padx=10, pady=6)

        tk.Label(win, text="Sanction:").grid(
            row=1, column=0, padx=10, pady=6, sticky="ne")
        sanction_txt = tk.Text(win, width=30, height=2)
        sanction_txt.grid(row=1, column=1, padx=10, pady=6)

        fields = {}
        row = 2
        for label, key in [
            ("Sanction Start (YYYY-MM-DD):", "sanction_start"),
            ("Sanction End (YYYY-MM-DD):", "sanction_end"),
            ("Appeal Deadline (YYYY-MM-DD):", "appeal_deadline"),
        ]:
            tk.Label(win, text=label).grid(
                row=row, column=0, padx=10, pady=6, sticky="e")
            e = tk.Entry(win, width=24)
            e.grid(row=row, column=1, padx=10, pady=6)
            fields[key] = e
            row += 1

        def save():
            outcome = outcome_txt.get("1.0", "end-1c").strip()
            if not outcome:
                messagebox.showwarning("Validation",
                                       "Outcome is required.")
                return
            sanction = sanction_txt.get("1.0", "end-1c").strip() or None
            try:
                self._svc.record_outcome(
                    cid, outcome,
                    sanction=sanction,
                    sanction_start=fields["sanction_start"].get().strip() or None,
                    sanction_end=fields["sanction_end"].get().strip() or None,
                    appeal_deadline=fields["appeal_deadline"].get().strip() or None)
                messagebox.showinfo("Success", "Outcome recorded.")
                win.destroy()
                self._load_cases()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _delete_case(self):
        cid = self._selected_case_id()
        if not cid:
            return
        if not messagebox.askyesno(
                "Confirm",
                f"Delete case #{cid} and all related evidence and appeals?"):
            return
        try:
            self._svc.delete_case(cid)
            messagebox.showinfo("Deleted", "Case deleted.")
            self._load_cases()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---- Evidence Tab ----

    def _build_evidence_tab(self):
        toolbar = tk.Frame(self._evidence_tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text="Case ID:", bg="#ecf0f1").pack(
            side="left", padx=(5, 2))
        self._ev_case_id = tk.Entry(toolbar, width=8)
        self._ev_case_id.pack(side="left", padx=2)

        ttk.Button(toolbar, text="Load Evidence",
                   command=self._load_evidence).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Add Evidence",
                   command=self._add_evidence).pack(side="right", padx=5)
        ttk.Button(toolbar, text="Delete Evidence",
                   command=self._delete_evidence).pack(side="right", padx=2)

        cols = ("id", "case_id", "type", "description", "submitted_by", "date")
        self._ev_tree = ttk.Treeview(
            self._evidence_tab, columns=cols, show="headings", height=18)
        for c, w, label in [
            ("id", 40, "ID"), ("case_id", 60, "Case ID"),
            ("type", 110, "Type"), ("description", 300, "Description"),
            ("submitted_by", 90, "Submitted By"), ("date", 100, "Date"),
        ]:
            self._ev_tree.heading(c, text=label)
            self._ev_tree.column(c, width=w,
                                 anchor="center" if w < 80 else "w")

        vsb = ttk.Scrollbar(self._evidence_tab, orient="vertical",
                            command=self._ev_tree.yview)
        self._ev_tree.configure(yscrollcommand=vsb.set)
        self._ev_tree.pack(side="left", fill="both", expand=True,
                           padx=(5, 0), pady=5)
        vsb.pack(side="right", fill="y", padx=(0, 5), pady=5)

    def _load_evidence(self):
        for item in self._ev_tree.get_children():
            self._ev_tree.delete(item)
        cid = self._ev_case_id.get().strip()
        if not cid:
            messagebox.showwarning("Input", "Enter a Case ID.")
            return
        try:
            records = self._svc.list_evidence(int(cid))
            for r in records:
                self._ev_tree.insert("", "end", iid=r["id"], values=(
                    r["id"], r.get("case_id", ""),
                    r.get("evidence_type", ""),
                    (r.get("description", "") or "")[:100],
                    r.get("submitted_by", ""),
                    r.get("submitted_date", "")))
            if not records:
                messagebox.showinfo("Info", "No evidence for this case.")
        except ValueError:
            messagebox.showerror("Error", "Invalid Case ID.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _add_evidence(self):
        cid = self._ev_case_id.get().strip()
        if not cid:
            messagebox.showwarning("Input",
                                   "Enter a Case ID in the toolbar first.")
            return

        win = tk.Toplevel(self)
        win.title(f"Add Evidence - Case #{cid}")
        win.geometry("460x340")
        win.resizable(False, False)

        row = 0
        tk.Label(win, text="Evidence Type:").grid(
            row=row, column=0, padx=10, pady=5, sticky="e")
        type_cb = ttk.Combobox(win, width=28, state="readonly",
                               values=EVIDENCE_TYPES)
        type_cb.set("document")
        type_cb.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text="Submitted By (User ID):").grid(
            row=row, column=0, padx=10, pady=5, sticky="e")
        sub_entry = tk.Entry(win, width=30)
        sub_entry.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text="Date (YYYY-MM-DD):").grid(
            row=row, column=0, padx=10, pady=5, sticky="e")
        date_entry = tk.Entry(win, width=30)
        date_entry.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text="File Path:").grid(
            row=row, column=0, padx=10, pady=5, sticky="e")
        path_entry = tk.Entry(win, width=30)
        path_entry.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text="Description*:").grid(
            row=row, column=0, padx=10, pady=5, sticky="ne")
        desc_txt = tk.Text(win, width=30, height=5)
        desc_txt.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            description = desc_txt.get("1.0", "end-1c").strip()
            if not description:
                messagebox.showwarning("Validation",
                                       "Description is required.")
                return
            kwargs = {}
            sub = sub_entry.get().strip()
            if sub:
                kwargs["submitted_by"] = int(sub)
            sd = date_entry.get().strip()
            if sd:
                kwargs["submitted_date"] = sd
            fp = path_entry.get().strip()
            if fp:
                kwargs["file_path"] = fp
            try:
                self._svc.add_evidence(int(cid), type_cb.get(),
                                       description, **kwargs)
                messagebox.showinfo("Success", "Evidence added.")
                win.destroy()
                self._load_evidence()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _delete_evidence(self):
        sel = self._ev_tree.selection()
        if not sel:
            messagebox.showwarning("Selection",
                                   "Please select an evidence record first.")
            return
        eid = int(sel[0])
        if not messagebox.askyesno("Confirm", f"Delete evidence #{eid}?"):
            return
        try:
            self._svc.delete_evidence(eid)
            messagebox.showinfo("Deleted", "Evidence deleted.")
            self._load_evidence()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---- Appeals Tab ----

    def _build_appeals_tab(self):
        toolbar = tk.Frame(self._appeals_tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text="Status:", bg="#ecf0f1").pack(
            side="left", padx=(5, 2))
        self._appeal_status_filter = ttk.Combobox(
            toolbar, width=14, state="readonly",
            values=[""] + APPEAL_STATUSES)
        self._appeal_status_filter.set("")
        self._appeal_status_filter.pack(side="left", padx=2)

        ttk.Button(toolbar, text="Search",
                   command=self._load_appeals).pack(side="left", padx=5)

        btn_frame = tk.Frame(self._appeals_tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", padx=5, pady=(0, 5))
        ttk.Button(btn_frame, text="Refresh",
                   command=self._load_appeals).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Lodge Appeal",
                   command=self._lodge_appeal).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Schedule Hearing",
                   command=self._schedule_appeal_hearing).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Record Outcome",
                   command=self._record_appeal_outcome).pack(side="left", padx=2)

        cols = ("id", "case_id", "appellant", "appeal_date",
                "grounds", "status", "outcome")
        self._appeal_tree = ttk.Treeview(
            self._appeals_tab, columns=cols, show="headings", height=16)
        for c, w, label in [
            ("id", 40, "ID"), ("case_id", 60, "Case ID"),
            ("appellant", 80, "Appellant"), ("appeal_date", 100, "Appeal Date"),
            ("grounds", 250, "Grounds"), ("status", 110, "Status"),
            ("outcome", 160, "Outcome"),
        ]:
            self._appeal_tree.heading(c, text=label)
            self._appeal_tree.column(c, width=w,
                                     anchor="center" if w < 80 else "w")

        vsb = ttk.Scrollbar(self._appeals_tab, orient="vertical",
                            command=self._appeal_tree.yview)
        self._appeal_tree.configure(yscrollcommand=vsb.set)
        self._appeal_tree.pack(side="left", fill="both", expand=True,
                               padx=(5, 0), pady=5)
        vsb.pack(side="right", fill="y", padx=(0, 5), pady=5)

    def _load_appeals(self):
        for item in self._appeal_tree.get_children():
            self._appeal_tree.delete(item)
        try:
            status = self._appeal_status_filter.get().strip() or None
            records = self._svc.list_appeals(status=status)
            for r in records:
                self._appeal_tree.insert("", "end", iid=r["id"], values=(
                    r["id"], r.get("case_id", ""),
                    r.get("appellant_id", ""),
                    r.get("appeal_date", ""),
                    (r.get("grounds", "") or "")[:80],
                    r.get("status", ""),
                    (r.get("outcome", "") or "")[:60]))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selected_appeal_id(self):
        sel = self._appeal_tree.selection()
        if not sel:
            messagebox.showwarning("Selection",
                                   "Please select an appeal first.")
            return None
        return int(sel[0])

    def _lodge_appeal(self):
        win = tk.Toplevel(self)
        win.title("Lodge Appeal")
        win.geometry("460x320")
        win.resizable(False, False)

        fields = {}
        row = 0
        for label, key in [
            ("Case ID*:", "case_id"),
            ("Appellant ID*:", "appellant_id"),
            ("Appeal Date* (YYYY-MM-DD):", "appeal_date"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10,
                                           pady=6, sticky="e")
            e = tk.Entry(win, width=28)
            e.grid(row=row, column=1, padx=10, pady=6)
            fields[key] = e
            row += 1

        tk.Label(win, text="Grounds*:").grid(
            row=row, column=0, padx=10, pady=6, sticky="ne")
        grounds_txt = tk.Text(win, width=28, height=5)
        grounds_txt.grid(row=row, column=1, padx=10, pady=6)
        row += 1

        def save():
            case_id = fields["case_id"].get().strip()
            appellant_id = fields["appellant_id"].get().strip()
            appeal_date = fields["appeal_date"].get().strip()
            grounds = grounds_txt.get("1.0", "end-1c").strip()
            if not case_id or not appellant_id or not appeal_date or not grounds:
                messagebox.showwarning("Validation",
                                       "All fields are required.")
                return
            try:
                self._svc.lodge_appeal(
                    int(case_id), int(appellant_id), appeal_date, grounds)
                messagebox.showinfo("Success", "Appeal lodged.")
                win.destroy()
                self._load_appeals()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Lodge Appeal", command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _schedule_appeal_hearing(self):
        aid = self._selected_appeal_id()
        if not aid:
            return

        win = tk.Toplevel(self)
        win.title(f"Schedule Appeal Hearing - Appeal #{aid}")
        win.geometry("420x200")
        win.resizable(False, False)

        tk.Label(win, text="Hearing Date* (YYYY-MM-DD):").grid(
            row=0, column=0, padx=10, pady=8, sticky="e")
        date_entry = tk.Entry(win, width=24)
        date_entry.grid(row=0, column=1, padx=10, pady=8)

        tk.Label(win, text="Panel Members:").grid(
            row=1, column=0, padx=10, pady=8, sticky="e")
        panel_entry = tk.Entry(win, width=24)
        panel_entry.grid(row=1, column=1, padx=10, pady=8)

        def save():
            hdate = date_entry.get().strip()
            if not hdate:
                messagebox.showwarning("Validation",
                                       "Hearing date is required.")
                return
            panel = panel_entry.get().strip() or None
            try:
                self._svc.schedule_appeal_hearing(aid, hdate, panel)
                messagebox.showinfo("Success", "Appeal hearing scheduled.")
                win.destroy()
                self._load_appeals()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Schedule", command=save).grid(
            row=2, column=0, columnspan=2, pady=12)

    def _record_appeal_outcome(self):
        aid = self._selected_appeal_id()
        if not aid:
            return

        win = tk.Toplevel(self)
        win.title(f"Record Appeal Outcome - Appeal #{aid}")
        win.geometry("440x200")
        win.resizable(False, False)

        tk.Label(win, text="Outcome*:").grid(
            row=0, column=0, padx=10, pady=8, sticky="ne")
        outcome_txt = tk.Text(win, width=28, height=4)
        outcome_txt.grid(row=0, column=1, padx=10, pady=8)

        def save():
            outcome = outcome_txt.get("1.0", "end-1c").strip()
            if not outcome:
                messagebox.showwarning("Validation",
                                       "Outcome is required.")
                return
            try:
                self._svc.record_appeal_outcome(aid, outcome)
                messagebox.showinfo("Success", "Appeal outcome recorded.")
                win.destroy()
                self._load_appeals()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=1, column=0, columnspan=2, pady=12)

    # ---- Statistics Tab ----

    def _build_stats_tab(self):
        self._stats_frame = tk.Frame(self._stats_tab, bg="#ecf0f1",
                                     padx=20, pady=20)
        self._stats_frame.pack(fill="both", expand=True)

        ttk.Button(self._stats_frame, text="Refresh Statistics",
                   command=self._load_stats).pack(anchor="w", pady=(0, 15))

        self._stats_labels = {}
        for key, label in [
            ("total_cases", "Total Cases"),
            ("active_cases", "Active Cases"),
            ("total_appeals", "Total Appeals"),
            ("pending_appeals", "Pending Appeals"),
            ("total_evidence", "Total Evidence"),
        ]:
            row_frame = tk.Frame(self._stats_frame, bg="#ecf0f1")
            row_frame.pack(fill="x", pady=3)
            tk.Label(row_frame, text=f"{label}:",
                     font=("Helvetica", 11, "bold"),
                     bg="#ecf0f1", width=22, anchor="e").pack(side="left")
            lbl = tk.Label(row_frame, text="--",
                           font=("Helvetica", 11), bg="#ecf0f1", anchor="w")
            lbl.pack(side="left", padx=(10, 0))
            self._stats_labels[key] = lbl

        # By Status breakdown
        tk.Label(self._stats_frame, text="By Status:",
                 font=("Helvetica", 11, "bold"), bg="#ecf0f1"
                 ).pack(anchor="w", pady=(15, 5))
        self._status_lbl = tk.Label(self._stats_frame, text="--",
                                    font=("Helvetica", 10), bg="#ecf0f1",
                                    justify="left", anchor="w")
        self._status_lbl.pack(anchor="w", padx=(20, 0))

        # By Type breakdown
        tk.Label(self._stats_frame, text="By Type:",
                 font=("Helvetica", 11, "bold"), bg="#ecf0f1"
                 ).pack(anchor="w", pady=(10, 5))
        self._type_lbl = tk.Label(self._stats_frame, text="--",
                                  font=("Helvetica", 10), bg="#ecf0f1",
                                  justify="left", anchor="w")
        self._type_lbl.pack(anchor="w", padx=(20, 0))

    def _load_stats(self):
        try:
            stats = self._svc.get_stats()
            for key, lbl in self._stats_labels.items():
                lbl.config(text=str(stats.get(key, 0)))

            by_status = stats.get("by_status", {})
            if by_status:
                self._status_lbl.config(
                    text="\n".join(f"{k}: {v}" for k, v in by_status.items()))
            else:
                self._status_lbl.config(text="No data")

            by_type = stats.get("by_type", {})
            if by_type:
                self._type_lbl.config(
                    text="\n".join(f"{k}: {v}" for k, v in by_type.items()))
            else:
                self._type_lbl.config(text="No data")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---- Refresh ----

    def refresh(self):
        self._load_cases()
        self._load_stats()
