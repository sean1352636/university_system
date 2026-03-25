"""Disciplinary & Appeals GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.disciplinary.services.disciplinary_service import DisciplinaryService
from education_system.college_system.core.i18n import t


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
        tk.Label(header, text=t("disciplinary.management"),
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._cases_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._cases_tab, text=t("disciplinary.cases"))
        self._build_cases_tab()

        self._evidence_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._evidence_tab, text=t("disciplinary.evidence"))
        self._build_evidence_tab()

        self._appeals_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._appeals_tab, text=t("disciplinary.appeals"))
        self._build_appeals_tab()

        self._stats_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._stats_tab, text=t("common.summary"))
        self._build_stats_tab()

    # ---- Cases Tab ----

    def _build_cases_tab(self):
        toolbar = tk.Frame(self._cases_tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text=t("common.status") + ":", bg="#ecf0f1").pack(side="left", padx=(5, 2))
        self._case_status_filter = ttk.Combobox(
            toolbar, width=16, state="readonly",
            values=[""] + CASE_STATUSES)
        self._case_status_filter.set("")
        self._case_status_filter.pack(side="left", padx=2)

        tk.Label(toolbar, text=t("disciplinary.person_type") + ":", bg="#ecf0f1").pack(
            side="left", padx=(8, 2))
        self._case_person_filter = ttk.Combobox(
            toolbar, width=10, state="readonly",
            values=[""] + PERSON_TYPES)
        self._case_person_filter.set("")
        self._case_person_filter.pack(side="left", padx=2)

        ttk.Button(toolbar, text=t("common.search"),
                   command=self._load_cases).pack(side="left", padx=5)

        btn_frame = tk.Frame(self._cases_tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", padx=5, pady=(0, 5))
        ttk.Button(btn_frame, text=t("common.refresh"),
                   command=self._load_cases).pack(side="left", padx=2)
        ttk.Button(btn_frame, text=t("disciplinary.log_case"),
                   command=self._new_case).pack(side="left", padx=2)
        ttk.Button(btn_frame, text=t("common.view"),
                   command=self._view_case).pack(side="left", padx=2)
        ttk.Button(btn_frame, text=t("common.update"),
                   command=self._update_case).pack(side="left", padx=2)
        ttk.Button(btn_frame, text=t("disciplinary.schedule_hearing"),
                   command=self._schedule_hearing).pack(side="left", padx=2)
        ttk.Button(btn_frame, text=t("disciplinary.record_outcome"),
                   command=self._record_outcome).pack(side="left", padx=2)
        ttk.Button(btn_frame, text=t("common.delete"),
                   command=self._delete_case).pack(side="right", padx=2)
        ttk.Button(btn_frame, text="Export CSV",
                   command=self._export_cases_csv).pack(side="left", padx=2)

        cols = ("id", "reference", "person_type", "person_id",
                "case_type", "allegation", "status")
        self._case_tree = ttk.Treeview(
            self._cases_tab, columns=cols, show="headings", height=16)
        for c, w, label in [
            ("id", 40, t("common.id")), ("reference", 100, t("disciplinary.reference")),
            ("person_type", 80, t("disciplinary.person_type")), ("person_id", 70, t("disciplinary.person_id")),
            ("case_type", 120, t("common.type")), ("allegation", 260, t("disciplinary.allegation")),
            ("status", 130, t("common.status")),
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
            messagebox.showerror(t("common.error"), str(e))

    def _selected_case_id(self):
        sel = self._case_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"),
                                   t("common.select_first"))
            return None
        return int(sel[0])

    def _new_case(self):
        win = tk.Toplevel(self)
        win.title(t("disciplinary.new_case"))
        win.geometry("500x520")
        win.resizable(False, False)

        fields = {}
        row = 0

        tk.Label(win, text=t("disciplinary.person_type") + "*:").grid(
            row=row, column=0, padx=10, pady=4, sticky="e")
        ptype_cb = ttk.Combobox(win, width=29, state="readonly",
                                values=PERSON_TYPES)
        ptype_cb.set("student")
        ptype_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        for label, key in [
            (t("disciplinary.person_id") + "*:", "person_id"),
            (t("disciplinary.reference") + ":", "case_reference"),
            (t("disciplinary.reported_by") + ":", "reported_by"),
            (t("disciplinary.reported_date") + ":", "reported_date"),
            (t("disciplinary.investigating_officer") + ":", "investigating_officer"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10,
                                           pady=4, sticky="e")
            e = tk.Entry(win, width=32)
            e.grid(row=row, column=1, padx=10, pady=4)
            fields[key] = e
            row += 1

        tk.Label(win, text=t("common.type") + ":").grid(
            row=row, column=0, padx=10, pady=4, sticky="e")
        ctype_cb = ttk.Combobox(win, width=29, state="readonly",
                                values=CASE_TYPES)
        ctype_cb.set("misconduct")
        ctype_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text=t("disciplinary.allegation") + "*:").grid(
            row=row, column=0, padx=10, pady=4, sticky="ne")
        allg_txt = tk.Text(win, width=32, height=5)
        allg_txt.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text=t("common.notes") + ":").grid(
            row=row, column=0, padx=10, pady=4, sticky="ne")
        notes_txt = tk.Text(win, width=32, height=3)
        notes_txt.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        def save():
            person_id_str = fields["person_id"].get().strip()
            allegation = allg_txt.get("1.0", "end-1c").strip()
            if not person_id_str or not allegation:
                messagebox.showwarning(t("common.validation"),
                                       t("common.field_required"))
                return
            try:
                person_id = int(person_id_str)
            except ValueError:
                messagebox.showwarning(t("common.validation"),
                                       t("common.invalid_input"))
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
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                win.destroy()
                self._load_cases()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.save"), command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _view_case(self):
        cid = self._selected_case_id()
        if not cid:
            return
        rec = self._svc.get_case(cid)
        if not rec:
            messagebox.showwarning(t("common.warning"), t("common.no_data"))
            return

        win = tk.Toplevel(self)
        win.title(f"{t('disciplinary.case')} #{cid}")
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
            (t("common.id"), rec.get("id")),
            (t("disciplinary.reference"), rec.get("case_reference")),
            (t("disciplinary.person_type"), rec.get("person_type")),
            (t("disciplinary.person_id"), rec.get("person_id")),
            (t("common.type"), rec.get("case_type")),
            (t("disciplinary.allegation"), rec.get("allegation")),
            (t("disciplinary.reported_by"), rec.get("reported_by")),
            (t("disciplinary.reported_date"), rec.get("reported_date")),
            (t("disciplinary.investigating_officer"), rec.get("investigating_officer")),
            (t("disciplinary.hearing_date"), rec.get("hearing_date")),
            (t("disciplinary.hearing_panel"), rec.get("hearing_panel")),
            (t("disciplinary.hearing_outcome"), rec.get("hearing_outcome")),
            (t("disciplinary.sanction"), rec.get("sanction")),
            (t("disciplinary.sanction_start"), rec.get("sanction_start_date")),
            (t("disciplinary.sanction_end"), rec.get("sanction_end_date")),
            (t("disciplinary.appeal_deadline"), rec.get("appeal_deadline")),
            (t("common.status"), rec.get("status")),
            (t("common.notes"), rec.get("notes")),
            (t("common.created_at"), rec.get("created_at")),
            (t("common.updated_at"), rec.get("updated_at")),
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
            messagebox.showwarning(t("common.warning"), t("common.no_data"))
            return

        win = tk.Toplevel(self)
        win.title(f"{t('common.update')} #{cid}")
        win.geometry("520x580")
        win.resizable(False, False)

        fields = {}
        row = 0

        tk.Label(win, text=t("disciplinary.person_type") + ":").grid(
            row=row, column=0, padx=10, pady=4, sticky="e")
        ptype_cb = ttk.Combobox(win, width=29, state="readonly",
                                values=PERSON_TYPES)
        ptype_cb.set(rec.get("person_type", "student"))
        ptype_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        for label, key in [
            (t("disciplinary.person_id") + ":", "person_id"),
            (t("disciplinary.reference") + ":", "case_reference"),
            (t("disciplinary.reported_by") + ":", "reported_by"),
            (t("disciplinary.reported_date") + ":", "reported_date"),
            (t("disciplinary.investigating_officer") + ":", "investigating_officer"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10,
                                           pady=4, sticky="e")
            e = tk.Entry(win, width=32)
            e.insert(0, str(rec.get(key, "") or ""))
            e.grid(row=row, column=1, padx=10, pady=4)
            fields[key] = e
            row += 1

        tk.Label(win, text=t("common.type") + ":").grid(
            row=row, column=0, padx=10, pady=4, sticky="e")
        ctype_cb = ttk.Combobox(win, width=29, state="readonly",
                                values=CASE_TYPES)
        ctype_cb.set(rec.get("case_type", "misconduct"))
        ctype_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text=t("common.status") + ":").grid(
            row=row, column=0, padx=10, pady=4, sticky="e")
        status_cb = ttk.Combobox(win, width=29, state="readonly",
                                 values=CASE_STATUSES)
        status_cb.set(rec.get("status", "under_investigation"))
        status_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text=t("disciplinary.allegation") + ":").grid(
            row=row, column=0, padx=10, pady=4, sticky="ne")
        allg_txt = tk.Text(win, width=32, height=4)
        allg_txt.insert("1.0", rec.get("allegation", "") or "")
        allg_txt.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text=t("common.notes") + ":").grid(
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
                messagebox.showinfo(t("common.success"), t("common.updated_success"))
                win.destroy()
                self._load_cases()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.save"), command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _schedule_hearing(self):
        cid = self._selected_case_id()
        if not cid:
            return

        win = tk.Toplevel(self)
        win.title(f"{t('disciplinary.schedule_hearing')} - #{cid}")
        win.geometry("420x200")
        win.resizable(False, False)

        tk.Label(win, text=t("disciplinary.hearing_date") + "*:").grid(
            row=0, column=0, padx=10, pady=8, sticky="e")
        date_entry = tk.Entry(win, width=24)
        date_entry.grid(row=0, column=1, padx=10, pady=8)

        tk.Label(win, text=t("disciplinary.hearing_panel") + ":").grid(
            row=1, column=0, padx=10, pady=8, sticky="e")
        panel_entry = tk.Entry(win, width=24)
        panel_entry.grid(row=1, column=1, padx=10, pady=8)

        def save():
            hdate = date_entry.get().strip()
            if not hdate:
                messagebox.showwarning(t("common.validation"),
                                       t("common.field_required"))
                return
            panel = panel_entry.get().strip() or None
            try:
                self._svc.schedule_hearing(cid, hdate, panel)
                messagebox.showinfo(t("common.success"), t("common.success"))
                win.destroy()
                self._load_cases()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("disciplinary.schedule"), command=save).grid(
            row=2, column=0, columnspan=2, pady=12)

    def _record_outcome(self):
        cid = self._selected_case_id()
        if not cid:
            return

        win = tk.Toplevel(self)
        win.title(f"{t('disciplinary.record_outcome')} - #{cid}")
        win.geometry("460x380")
        win.resizable(False, False)

        tk.Label(win, text=t("disciplinary.outcome") + "*:").grid(
            row=0, column=0, padx=10, pady=6, sticky="ne")
        outcome_txt = tk.Text(win, width=30, height=3)
        outcome_txt.grid(row=0, column=1, padx=10, pady=6)

        tk.Label(win, text=t("disciplinary.sanction") + ":").grid(
            row=1, column=0, padx=10, pady=6, sticky="ne")
        sanction_txt = tk.Text(win, width=30, height=2)
        sanction_txt.grid(row=1, column=1, padx=10, pady=6)

        fields = {}
        row = 2
        for label, key in [
            (t("disciplinary.sanction_start") + ":", "sanction_start"),
            (t("disciplinary.sanction_end") + ":", "sanction_end"),
            (t("disciplinary.appeal_deadline") + ":", "appeal_deadline"),
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
                messagebox.showwarning(t("common.validation"),
                                       t("common.field_required"))
                return
            sanction = sanction_txt.get("1.0", "end-1c").strip() or None
            try:
                self._svc.record_outcome(
                    cid, outcome,
                    sanction=sanction,
                    sanction_start=fields["sanction_start"].get().strip() or None,
                    sanction_end=fields["sanction_end"].get().strip() or None,
                    appeal_deadline=fields["appeal_deadline"].get().strip() or None)
                messagebox.showinfo(t("common.success"), t("common.success"))
                win.destroy()
                self._load_cases()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.save"), command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _delete_case(self):
        cid = self._selected_case_id()
        if not cid:
            return
        if not messagebox.askyesno(
                t("common.confirm"),
                t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_case(cid)
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_cases()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ---- Evidence Tab ----

    def _build_evidence_tab(self):
        toolbar = tk.Frame(self._evidence_tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text=t("common.id") + ":", bg="#ecf0f1").pack(
            side="left", padx=(5, 2))
        self._ev_case_id = tk.Entry(toolbar, width=8)
        self._ev_case_id.pack(side="left", padx=2)

        ttk.Button(toolbar, text=t("disciplinary.load_evidence"),
                   command=self._load_evidence).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("disciplinary.add_evidence"),
                   command=self._add_evidence).pack(side="right", padx=5)
        ttk.Button(toolbar, text=t("disciplinary.delete_evidence"),
                   command=self._delete_evidence).pack(side="right", padx=2)
        ttk.Button(toolbar, text="Export CSV",
                   command=self._export_evidence_csv).pack(side="left", padx=5)

        cols = ("id", "case_id", "type", "description", "submitted_by", "date")
        self._ev_tree = ttk.Treeview(
            self._evidence_tab, columns=cols, show="headings", height=18)
        for c, w, label in [
            ("id", 40, t("common.id")), ("case_id", 60, t("disciplinary.case_id")),
            ("type", 110, t("common.type")), ("description", 300, t("common.description")),
            ("submitted_by", 90, t("disciplinary.submitted_by")), ("date", 100, t("common.date")),
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
            messagebox.showwarning(t("common.input"), t("common.field_required"))
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
                messagebox.showinfo(t("common.info"), t("common.no_data"))
        except ValueError:
            messagebox.showerror(t("common.error"), t("common.invalid_input"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _add_evidence(self):
        cid = self._ev_case_id.get().strip()
        if not cid:
            messagebox.showwarning(t("common.input"),
                                   t("common.field_required"))
            return

        win = tk.Toplevel(self)
        win.title(f"{t('disciplinary.add_evidence')} - #{cid}")
        win.geometry("460x340")
        win.resizable(False, False)

        row = 0
        tk.Label(win, text=t("disciplinary.evidence_type") + ":").grid(
            row=row, column=0, padx=10, pady=5, sticky="e")
        type_cb = ttk.Combobox(win, width=28, state="readonly",
                               values=EVIDENCE_TYPES)
        type_cb.set("document")
        type_cb.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text=t("disciplinary.submitted_by") + ":").grid(
            row=row, column=0, padx=10, pady=5, sticky="e")
        sub_entry = tk.Entry(win, width=30)
        sub_entry.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text=t("common.date") + ":").grid(
            row=row, column=0, padx=10, pady=5, sticky="e")
        date_entry = tk.Entry(win, width=30)
        date_entry.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text=t("disciplinary.file_path") + ":").grid(
            row=row, column=0, padx=10, pady=5, sticky="e")
        path_entry = tk.Entry(win, width=30)
        path_entry.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text=t("common.description") + "*:").grid(
            row=row, column=0, padx=10, pady=5, sticky="ne")
        desc_txt = tk.Text(win, width=30, height=5)
        desc_txt.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            description = desc_txt.get("1.0", "end-1c").strip()
            if not description:
                messagebox.showwarning(t("common.validation"),
                                       t("common.field_required"))
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
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                win.destroy()
                self._load_evidence()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.save"), command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _delete_evidence(self):
        sel = self._ev_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"),
                                   t("common.select_first"))
            return
        eid = int(sel[0])
        if not messagebox.askyesno(t("common.confirm"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_evidence(eid)
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_evidence()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ---- Appeals Tab ----

    def _build_appeals_tab(self):
        toolbar = tk.Frame(self._appeals_tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text=t("common.status") + ":", bg="#ecf0f1").pack(
            side="left", padx=(5, 2))
        self._appeal_status_filter = ttk.Combobox(
            toolbar, width=14, state="readonly",
            values=[""] + APPEAL_STATUSES)
        self._appeal_status_filter.set("")
        self._appeal_status_filter.pack(side="left", padx=2)

        ttk.Button(toolbar, text=t("common.search"),
                   command=self._load_appeals).pack(side="left", padx=5)

        btn_frame = tk.Frame(self._appeals_tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", padx=5, pady=(0, 5))
        ttk.Button(btn_frame, text=t("common.refresh"),
                   command=self._load_appeals).pack(side="left", padx=2)
        ttk.Button(btn_frame, text=t("disciplinary.lodge_appeal"),
                   command=self._lodge_appeal).pack(side="left", padx=2)
        ttk.Button(btn_frame, text=t("disciplinary.schedule_hearing"),
                   command=self._schedule_appeal_hearing).pack(side="left", padx=2)
        ttk.Button(btn_frame, text=t("disciplinary.record_outcome"),
                   command=self._record_appeal_outcome).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Export CSV",
                   command=self._export_appeals_csv).pack(side="left", padx=2)

        cols = ("id", "case_id", "appellant", "appeal_date",
                "grounds", "status", "outcome")
        self._appeal_tree = ttk.Treeview(
            self._appeals_tab, columns=cols, show="headings", height=16)
        for c, w, label in [
            ("id", 40, t("common.id")), ("case_id", 60, t("disciplinary.case_id")),
            ("appellant", 80, t("disciplinary.appellant")), ("appeal_date", 100, t("disciplinary.appeal_date")),
            ("grounds", 250, t("disciplinary.grounds")), ("status", 110, t("common.status")),
            ("outcome", 160, t("disciplinary.outcome")),
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
            messagebox.showerror(t("common.error"), str(e))

    def _selected_appeal_id(self):
        sel = self._appeal_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"),
                                   t("common.select_first"))
            return None
        return int(sel[0])

    def _lodge_appeal(self):
        win = tk.Toplevel(self)
        win.title(t("disciplinary.lodge_appeal"))
        win.geometry("460x320")
        win.resizable(False, False)

        fields = {}
        row = 0
        for label, key in [
            (t("disciplinary.case_id") + "*:", "case_id"),
            (t("disciplinary.appellant") + "*:", "appellant_id"),
            (t("disciplinary.appeal_date") + "*:", "appeal_date"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10,
                                           pady=6, sticky="e")
            e = tk.Entry(win, width=28)
            e.grid(row=row, column=1, padx=10, pady=6)
            fields[key] = e
            row += 1

        tk.Label(win, text=t("disciplinary.grounds") + "*:").grid(
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
                messagebox.showwarning(t("common.validation"),
                                       t("common.field_required"))
                return
            try:
                self._svc.lodge_appeal(
                    int(case_id), int(appellant_id), appeal_date, grounds)
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                win.destroy()
                self._load_appeals()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("disciplinary.lodge_appeal"), command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _schedule_appeal_hearing(self):
        aid = self._selected_appeal_id()
        if not aid:
            return

        win = tk.Toplevel(self)
        win.title(f"{t('disciplinary.schedule_hearing')} - #{aid}")
        win.geometry("420x200")
        win.resizable(False, False)

        tk.Label(win, text=t("disciplinary.hearing_date") + "*:").grid(
            row=0, column=0, padx=10, pady=8, sticky="e")
        date_entry = tk.Entry(win, width=24)
        date_entry.grid(row=0, column=1, padx=10, pady=8)

        tk.Label(win, text=t("disciplinary.hearing_panel") + ":").grid(
            row=1, column=0, padx=10, pady=8, sticky="e")
        panel_entry = tk.Entry(win, width=24)
        panel_entry.grid(row=1, column=1, padx=10, pady=8)

        def save():
            hdate = date_entry.get().strip()
            if not hdate:
                messagebox.showwarning(t("common.validation"),
                                       t("common.field_required"))
                return
            panel = panel_entry.get().strip() or None
            try:
                self._svc.schedule_appeal_hearing(aid, hdate, panel)
                messagebox.showinfo(t("common.success"), t("common.success"))
                win.destroy()
                self._load_appeals()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("disciplinary.schedule"), command=save).grid(
            row=2, column=0, columnspan=2, pady=12)

    def _record_appeal_outcome(self):
        aid = self._selected_appeal_id()
        if not aid:
            return

        win = tk.Toplevel(self)
        win.title(f"{t('disciplinary.record_outcome')} - #{aid}")
        win.geometry("440x200")
        win.resizable(False, False)

        tk.Label(win, text=t("disciplinary.outcome") + "*:").grid(
            row=0, column=0, padx=10, pady=8, sticky="ne")
        outcome_txt = tk.Text(win, width=28, height=4)
        outcome_txt.grid(row=0, column=1, padx=10, pady=8)

        def save():
            outcome = outcome_txt.get("1.0", "end-1c").strip()
            if not outcome:
                messagebox.showwarning(t("common.validation"),
                                       t("common.field_required"))
                return
            try:
                self._svc.record_appeal_outcome(aid, outcome)
                messagebox.showinfo(t("common.success"), t("common.success"))
                win.destroy()
                self._load_appeals()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.save"), command=save).grid(
            row=1, column=0, columnspan=2, pady=12)

    # ---- Statistics Tab ----

    def _build_stats_tab(self):
        self._stats_frame = tk.Frame(self._stats_tab, bg="#ecf0f1",
                                     padx=20, pady=20)
        self._stats_frame.pack(fill="both", expand=True)

        ttk.Button(self._stats_frame, text=t("common.refresh") + " " + t("common.summary"),
                   command=self._load_stats).pack(anchor="w", pady=(0, 15))

        self._stats_labels = {}
        for key, label in [
            ("total_cases", t("disciplinary.total_cases")),
            ("active_cases", t("disciplinary.active_cases")),
            ("total_appeals", t("disciplinary.total_appeals")),
            ("pending_appeals", t("disciplinary.pending_appeals")),
            ("total_evidence", t("disciplinary.total_evidence")),
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
        tk.Label(self._stats_frame, text=t("disciplinary.by_status") + ":",
                 font=("Helvetica", 11, "bold"), bg="#ecf0f1"
                 ).pack(anchor="w", pady=(15, 5))
        self._status_lbl = tk.Label(self._stats_frame, text="--",
                                    font=("Helvetica", 10), bg="#ecf0f1",
                                    justify="left", anchor="w")
        self._status_lbl.pack(anchor="w", padx=(20, 0))

        # By Type breakdown
        tk.Label(self._stats_frame, text=t("disciplinary.by_type") + ":",
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
                self._status_lbl.config(text=t("common.no_data"))

            by_type = stats.get("by_type", {})
            if by_type:
                self._type_lbl.config(
                    text="\n".join(f"{k}: {v}" for k, v in by_type.items()))
            else:
                self._type_lbl.config(text=t("common.no_data"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ---- Refresh ----

    def _export_cases_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._case_tree, "disciplinary_cases_export.csv")

    def _export_evidence_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._ev_tree, "disciplinary_evidence_export.csv")

    def _export_appeals_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._appeal_tree, "disciplinary_appeals_export.csv")

    def refresh(self):
        self._load_cases()
        self._load_stats()
