"""Complaints GUI frame for managing complaints and responses."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.core.i18n import t
from education_system.college_system.modules.domain.complaints.services.complaints_service import ComplaintService


CATEGORIES = ["general", "teaching", "facilities", "staff_conduct",
              "assessment", "admissions", "safeguarding", "bullying",
              "discrimination", "health_safety", "other"]

STAGES = ["informal", "formal_stage_1", "formal_stage_2",
          "panel_hearing", "appeal"]

STATUSES = ["open", "investigating", "awaiting_response",
            "resolved", "closed", "withdrawn"]

COMPLAINANT_TYPES = ["student", "parent", "staff", "visitor", "other"]

RESPONSE_TYPES = ["acknowledgement", "investigation", "update",
                  "outcome", "appeal_response", "other"]


class ComplaintFrame(tk.Frame):
    """Complaints management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = ComplaintService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("complaints.management"),
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._comp_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._comp_tab, text=t("complaints.management"))
        self._build_complaints_tab()

        self._resp_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._resp_tab, text=t("complaints.resolution"))
        self._build_responses_tab()

        self._stats_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._stats_tab, text=t("common.summary"))
        self._build_stats_tab()

    # ---- Complaints Tab ----

    def _build_complaints_tab(self):
        toolbar = tk.Frame(self._comp_tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text=t("common.search_colon"), bg="#ecf0f1").pack(side="left", padx=(5, 2))
        self._comp_search = tk.Entry(toolbar, width=16)
        self._comp_search.pack(side="left", padx=2)
        self._comp_search.bind("<Return>", lambda e: self._load_complaints())

        tk.Label(toolbar, text=t("common.status") + ":", bg="#ecf0f1").pack(side="left", padx=(8, 2))
        self._comp_status = ttk.Combobox(toolbar, width=12, state="readonly",
                                          values=[""] + STATUSES)
        self._comp_status.set("")
        self._comp_status.pack(side="left", padx=2)

        tk.Label(toolbar, text=t("common.category") + ":", bg="#ecf0f1").pack(side="left", padx=(8, 2))
        self._comp_stage = ttk.Combobox(toolbar, width=12, state="readonly",
                                         values=[""] + STAGES)
        self._comp_stage.set("")
        self._comp_stage.pack(side="left", padx=2)

        ttk.Button(toolbar, text=t("common.search"), command=self._load_complaints).pack(side="left", padx=5)

        btn_frame = tk.Frame(self._comp_tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", padx=5, pady=(0, 5))
        ttk.Button(btn_frame, text=t("common.refresh"), command=self._load_complaints).pack(side="left", padx=2)
        ttk.Button(btn_frame, text=t("complaints.log_complaint"), command=self._new_complaint).pack(side="left", padx=2)
        ttk.Button(btn_frame, text=t("common.view"), command=self._view_complaint).pack(side="left", padx=2)
        ttk.Button(btn_frame, text=t("common.edit"), command=self._edit_complaint).pack(side="left", padx=2)
        ttk.Button(btn_frame, text=t("common.submit"), command=self._escalate_complaint).pack(side="left", padx=2)
        ttk.Button(btn_frame, text=t("complaints.resolution"), command=self._resolve_complaint).pack(side="left", padx=2)
        ttk.Button(btn_frame, text=t("common.delete"), command=self._delete_complaint).pack(side="right", padx=2)
        ttk.Button(btn_frame, text="Export CSV", command=self._export_csv).pack(side="left", padx=2)

        cols = ("id", "date", "complainant", "type", "category",
                "subject", "stage", "status")
        self._comp_tree = ttk.Treeview(self._comp_tab, columns=cols,
                                        show="headings", height=16)
        for c, w, label in [
            ("id", 40, t("common.id")), ("date", 90, t("common.date")),
            ("complainant", 140, t("complaints.complainant")), ("type", 75, t("common.type")),
            ("category", 95, t("common.category")), ("subject", 220, t("common.title")),
            ("stage", 110, t("common.status")), ("status", 90, t("common.status")),
        ]:
            self._comp_tree.heading(c, text=label)
            self._comp_tree.column(c, width=w,
                                    anchor="center" if w < 80 else "w")
        self._comp_tree.bind("<Double-1>", lambda e: self._view_complaint())

        vsb = ttk.Scrollbar(self._comp_tab, orient="vertical",
                             command=self._comp_tree.yview)
        self._comp_tree.configure(yscrollcommand=vsb.set)
        self._comp_tree.pack(side="left", fill="both", expand=True,
                              padx=(5, 0), pady=5)
        vsb.pack(side="right", fill="y", padx=(0, 5), pady=5)

    def _load_complaints(self):
        for item in self._comp_tree.get_children():
            self._comp_tree.delete(item)
        try:
            search = self._comp_search.get().strip() or None
            status = self._comp_status.get().strip() or None
            stage = self._comp_stage.get().strip() or None
            records = self._svc.list_complaints(
                search=search, status=status, stage=stage)
            for r in records:
                self._comp_tree.insert("", "end", iid=r["id"], values=(
                    r["id"], r.get("complaint_date", ""),
                    r.get("complainant_name", ""),
                    r.get("complainant_type", ""),
                    r.get("category", ""), r.get("subject", ""),
                    r.get("stage", ""), r.get("status", "")))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _selected_complaint_id(self):
        sel = self._comp_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"),
                                    t("common.select_first"))
            return None
        return int(sel[0])

    def _new_complaint(self):
        win = tk.Toplevel(self)
        win.title(t("complaints.log_complaint"))
        win.geometry("500x520")
        win.resizable(False, False)

        fields = {}
        row = 0

        for label, key in [
            (t("complaints.complainant") + "*:", "complainant_name"),
            (t("common.email") + ":", "complainant_email"),
            (t("common.phone") + ":", "complainant_phone"),
            (t("common.title") + "*:", "subject"),
            (t("common.date") + ":", "complaint_date"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10,
                                            pady=4, sticky="e")
            e = tk.Entry(win, width=32)
            e.grid(row=row, column=1, padx=10, pady=4)
            fields[key] = e
            row += 1

        tk.Label(win, text=t("common.type") + ":").grid(row=row, column=0,
                                                      padx=10, pady=4, sticky="e")
        type_cb = ttk.Combobox(win, width=29, state="readonly",
                                values=COMPLAINANT_TYPES)
        type_cb.set("parent")
        type_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text=t("common.category") + ":").grid(row=row, column=0, padx=10,
                                              pady=4, sticky="e")
        cat_cb = ttk.Combobox(win, width=29, state="readonly",
                               values=CATEGORIES)
        cat_cb.set("general")
        cat_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text=t("common.status") + ":").grid(row=row, column=0, padx=10,
                                           pady=4, sticky="e")
        stage_cb = ttk.Combobox(win, width=29, state="readonly",
                                 values=STAGES)
        stage_cb.set("informal")
        stage_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text=t("common.description") + "*:").grid(row=row, column=0,
                                                  padx=10, pady=4, sticky="ne")
        desc_txt = tk.Text(win, width=32, height=6)
        desc_txt.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        def save():
            name = fields["complainant_name"].get().strip()
            subj = fields["subject"].get().strip()
            desc = desc_txt.get("1.0", "end-1c").strip()
            if not name or not subj or not desc:
                messagebox.showwarning(t("common.validation"),
                                        t("common.field_required"))
                return
            try:
                self._svc.create_complaint(
                    name, subj, desc,
                    complainant_type=type_cb.get(),
                    complainant_email=fields["complainant_email"].get().strip() or None,
                    complainant_phone=fields["complainant_phone"].get().strip() or None,
                    complaint_date=fields["complaint_date"].get().strip() or None,
                    category=cat_cb.get(),
                    stage=stage_cb.get())
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                win.destroy()
                self._load_complaints()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.save"), command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _view_complaint(self):
        cid = self._selected_complaint_id()
        if not cid:
            return
        rec = self._svc.get_complaint(cid)
        if not rec:
            messagebox.showwarning(t("common.warning"), t("common.no_data"))
            return

        win = tk.Toplevel(self)
        win.title(f"{t('complaints.management')} #{cid}: {rec.get('subject', '')}")
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
            (t("common.title"), rec.get("subject")),
            (t("complaints.complainant"), rec.get("complainant_name")),
            (t("common.type"), rec.get("complainant_type")),
            (t("common.email"), rec.get("complainant_email")),
            (t("common.phone"), rec.get("complainant_phone")),
            (t("common.date"), rec.get("complaint_date")),
            (t("common.category"), rec.get("category")),
            (t("common.status"), rec.get("stage")),
            (t("common.status"), rec.get("status")),
            (t("common.description"), rec.get("description")),
            (t("common.notes"), rec.get("investigation_notes")),
            (t("common.summary"), rec.get("outcome")),
            (t("complaints.resolution"), rec.get("resolution")),
            (t("common.date"), rec.get("resolved_date")),
            (t("common.yes"), t("common.yes") if rec.get("appeal_lodged") else t("common.no")),
            (t("common.created_at"), rec.get("created_at")),
            (t("common.updated_at"), rec.get("updated_at")),
        ]

        for i, (lbl, val) in enumerate(display):
            tk.Label(frame, text=f"{lbl}:", font=("Helvetica", 10, "bold"),
                     anchor="e").grid(row=i, column=0, sticky="ne",
                                       padx=(0, 8), pady=2)
            tk.Label(frame, text=str(val or ""), anchor="w",
                     wraplength=340).grid(row=i, column=1, sticky="w", pady=2)

        # Show responses inline
        responses = self._svc.list_responses(cid)
        if responses:
            r_row = len(display)
            tk.Label(frame, text=t("complaints.resolution") + ":",
                     font=("Helvetica", 11, "bold")).grid(
                row=r_row, column=0, columnspan=2, sticky="w", pady=(12, 4))
            for resp in responses:
                r_row += 1
                who = resp.get("responder_name") or f"User #{resp.get('responder_id', '?')}"
                tk.Label(frame, text=(
                    f"[{resp.get('response_date', '')}] {who} "
                    f"({resp.get('response_type', '')}):\n"
                    f"{resp.get('response_text', '')}"),
                    anchor="w", wraplength=420, justify="left",
                    bg="#dfe6e9", padx=6, pady=4, relief="groove"
                ).grid(row=r_row, column=0, columnspan=2,
                       sticky="ew", pady=2, padx=5)

    def _edit_complaint(self):
        cid = self._selected_complaint_id()
        if not cid:
            return
        rec = self._svc.get_complaint(cid)
        if not rec:
            messagebox.showwarning(t("common.warning"), t("common.no_data"))
            return

        win = tk.Toplevel(self)
        win.title(f"{t('common.edit')} #{cid}")
        win.geometry("520x600")
        win.resizable(False, False)

        fields = {}
        row = 0

        for label, key in [
            (t("complaints.complainant") + "*:", "complainant_name"),
            (t("common.email") + ":", "complainant_email"),
            (t("common.phone") + ":", "complainant_phone"),
            (t("common.title") + "*:", "subject"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10,
                                            pady=4, sticky="e")
            e = tk.Entry(win, width=32)
            e.insert(0, rec.get(key, "") or "")
            e.grid(row=row, column=1, padx=10, pady=4)
            fields[key] = e
            row += 1

        tk.Label(win, text=t("common.type") + ":").grid(row=row, column=0, padx=10,
                                          pady=4, sticky="e")
        type_cb = ttk.Combobox(win, width=29, state="readonly",
                                values=COMPLAINANT_TYPES)
        type_cb.set(rec.get("complainant_type", "parent"))
        type_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text=t("common.category") + ":").grid(row=row, column=0, padx=10,
                                              pady=4, sticky="e")
        cat_cb = ttk.Combobox(win, width=29, state="readonly",
                               values=CATEGORIES)
        cat_cb.set(rec.get("category", "general"))
        cat_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text=t("common.status") + ":").grid(row=row, column=0, padx=10,
                                           pady=4, sticky="e")
        stage_cb = ttk.Combobox(win, width=29, state="readonly",
                                 values=STAGES)
        stage_cb.set(rec.get("stage", "informal"))
        stage_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text=t("common.status") + ":").grid(row=row, column=0, padx=10,
                                            pady=4, sticky="e")
        status_cb = ttk.Combobox(win, width=29, state="readonly",
                                  values=STATUSES)
        status_cb.set(rec.get("status", "open"))
        status_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        appeal_var = tk.BooleanVar(value=bool(rec.get("appeal_lodged")))
        ttk.Checkbutton(win, text=t("common.yes"), variable=appeal_var).grid(
            row=row, column=1, sticky="w", padx=10, pady=2)
        row += 1

        tk.Label(win, text=t("common.description") + "*:").grid(row=row, column=0,
                                                  padx=10, pady=4, sticky="ne")
        desc_txt = tk.Text(win, width=32, height=4)
        desc_txt.insert("1.0", rec.get("description", "") or "")
        desc_txt.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text=t("common.notes") + ":").grid(
            row=row, column=0, padx=10, pady=4, sticky="ne")
        inv_txt = tk.Text(win, width=32, height=3)
        inv_txt.insert("1.0", rec.get("investigation_notes", "") or "")
        inv_txt.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text=t("common.summary") + ":").grid(row=row, column=0, padx=10,
                                             pady=4, sticky="ne")
        out_txt = tk.Text(win, width=32, height=2)
        out_txt.insert("1.0", rec.get("outcome", "") or "")
        out_txt.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        def save():
            name = fields["complainant_name"].get().strip()
            subj = fields["subject"].get().strip()
            desc = desc_txt.get("1.0", "end-1c").strip()
            if not name or not subj or not desc:
                messagebox.showwarning(t("common.validation"),
                                        t("common.field_required"))
                return
            try:
                self._svc.update_complaint(
                    cid,
                    complainant_name=name, subject=subj, description=desc,
                    complainant_type=type_cb.get(),
                    complainant_email=fields["complainant_email"].get().strip() or None,
                    complainant_phone=fields["complainant_phone"].get().strip() or None,
                    category=cat_cb.get(), stage=stage_cb.get(),
                    status=status_cb.get(),
                    appeal_lodged=1 if appeal_var.get() else 0,
                    investigation_notes=inv_txt.get("1.0", "end-1c").strip() or None,
                    outcome=out_txt.get("1.0", "end-1c").strip() or None)
                messagebox.showinfo(t("common.success"), t("common.updated_success"))
                win.destroy()
                self._load_complaints()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.save"), command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _escalate_complaint(self):
        cid = self._selected_complaint_id()
        if not cid:
            return
        rec = self._svc.get_complaint(cid)
        if not rec:
            return
        if not messagebox.askyesno(
                t("common.confirm"),
                f"{t('common.confirm')} #{cid}?"):
            return
        try:
            updated = self._svc.escalate(cid)
            messagebox.showinfo(t("common.success"),
                                 f"{t('common.updated_success')}")
            self._load_complaints()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _resolve_complaint(self):
        cid = self._selected_complaint_id()
        if not cid:
            return

        win = tk.Toplevel(self)
        win.title(f"{t('complaints.resolution')} #{cid}")
        win.geometry("420x250")
        win.resizable(False, False)

        tk.Label(win, text=t("common.summary") + "*:").grid(row=0, column=0, padx=10,
                                              pady=8, sticky="ne")
        out_txt = tk.Text(win, width=30, height=3)
        out_txt.grid(row=0, column=1, padx=10, pady=8)

        tk.Label(win, text=t("complaints.resolution") + ":").grid(row=1, column=0, padx=10,
                                                pady=8, sticky="ne")
        res_txt = tk.Text(win, width=30, height=3)
        res_txt.grid(row=1, column=1, padx=10, pady=8)

        def save():
            outcome = out_txt.get("1.0", "end-1c").strip()
            if not outcome:
                messagebox.showwarning(t("common.validation"), t("common.field_required"))
                return
            try:
                self._svc.resolve(
                    cid, outcome,
                    resolution=res_txt.get("1.0", "end-1c").strip() or None)
                messagebox.showinfo(t("common.success"), t("common.updated_success"))
                win.destroy()
                self._load_complaints()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.save"), command=save).grid(
            row=2, column=0, columnspan=2, pady=12)

    def _delete_complaint(self):
        cid = self._selected_complaint_id()
        if not cid:
            return
        if not messagebox.askyesno(
                t("common.confirm_delete"),
                t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_complaint(cid)
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_complaints()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ---- Responses Tab ----

    def _build_responses_tab(self):
        toolbar = tk.Frame(self._resp_tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text=t("common.id") + ":", bg="#ecf0f1").pack(
            side="left", padx=(5, 2))
        self._resp_comp_id = tk.Entry(toolbar, width=8)
        self._resp_comp_id.pack(side="left", padx=2)

        ttk.Button(toolbar, text=t("common.refresh"),
                   command=self._load_responses).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("common.add"),
                   command=self._add_response).pack(side="right", padx=5)
        ttk.Button(toolbar, text=t("common.delete"),
                   command=self._delete_response).pack(side="right", padx=2)

        cols = ("id", "date", "responder", "type", "text")
        self._resp_tree = ttk.Treeview(self._resp_tab, columns=cols,
                                        show="headings", height=18)
        for c, w, label in [
            ("id", 40, t("common.id")), ("date", 90, t("common.date")),
            ("responder", 120, t("common.name")), ("type", 110, t("common.type")),
            ("text", 400, t("common.description")),
        ]:
            self._resp_tree.heading(c, text=label)
            self._resp_tree.column(c, width=w,
                                    anchor="center" if w < 80 else "w")

        vsb = ttk.Scrollbar(self._resp_tab, orient="vertical",
                             command=self._resp_tree.yview)
        self._resp_tree.configure(yscrollcommand=vsb.set)
        self._resp_tree.pack(side="left", fill="both", expand=True,
                              padx=(5, 0), pady=5)
        vsb.pack(side="right", fill="y", padx=(0, 5), pady=5)

    def _load_responses(self):
        for item in self._resp_tree.get_children():
            self._resp_tree.delete(item)
        cid = self._resp_comp_id.get().strip()
        if not cid:
            messagebox.showwarning(t("common.input"), t("common.field_required"))
            return
        try:
            responses = self._svc.list_responses(int(cid))
            for r in responses:
                who = r.get("responder_name") or f"User #{r.get('responder_id', '?')}"
                self._resp_tree.insert("", "end", iid=r["id"], values=(
                    r["id"], r.get("response_date", ""), who,
                    r.get("response_type", ""),
                    (r.get("response_text", "") or "")[:120]))
            if not responses:
                messagebox.showinfo(t("common.info"), t("common.no_data"))
        except ValueError:
            messagebox.showerror(t("common.error"), t("common.invalid_input"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _add_response(self):
        cid = self._resp_comp_id.get().strip()
        if not cid:
            messagebox.showwarning(t("common.input"),
                                    t("common.field_required"))
            return

        win = tk.Toplevel(self)
        win.title(f"{t('common.add')} #{cid}")
        win.geometry("440x300")
        win.resizable(False, False)

        row = 0
        tk.Label(win, text=t("common.type") + ":").grid(row=row, column=0,
                                                   padx=10, pady=5, sticky="e")
        type_cb = ttk.Combobox(win, width=28, state="readonly",
                                values=RESPONSE_TYPES)
        type_cb.set("investigation")
        type_cb.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text=t("common.date") + ":").grid(row=row, column=0,
                                                       padx=10, pady=5, sticky="e")
        date_entry = tk.Entry(win, width=30)
        date_entry.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text=t("common.description") + "*:").grid(row=row, column=0, padx=10,
                                               pady=5, sticky="ne")
        resp_txt = tk.Text(win, width=30, height=6)
        resp_txt.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            text = resp_txt.get("1.0", "end-1c").strip()
            if not text:
                messagebox.showwarning(t("common.validation"),
                                        t("common.field_required"))
                return
            try:
                self._svc.add_response(
                    int(cid), text,
                    response_type=type_cb.get(),
                    response_date=date_entry.get().strip() or None)
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                win.destroy()
                self._load_responses()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(win, text=t("common.save"), command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _delete_response(self):
        sel = self._resp_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"),
                                    t("common.select_first"))
            return
        rid = int(sel[0])
        if not messagebox.askyesno(t("common.confirm_delete"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_response(rid)
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_responses()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ---- Statistics Tab ----

    def _build_stats_tab(self):
        self._stats_frame = tk.Frame(self._stats_tab, bg="#ecf0f1",
                                      padx=20, pady=20)
        self._stats_frame.pack(fill="both", expand=True)

        ttk.Button(self._stats_frame, text=t("common.refresh"),
                   command=self._load_stats).pack(anchor="w", pady=(0, 15))

        self._stats_labels = {}
        for key, label in [
            ("total", t("common.total")),
            ("open", t("common.active")),
            ("investigating", t("common.in_progress")),
            ("resolved", t("common.completed")),
            ("appealed", t("common.status")),
        ]:
            row_frame = tk.Frame(self._stats_frame, bg="#ecf0f1")
            row_frame.pack(fill="x", pady=3)
            tk.Label(row_frame, text=f"{label}:",
                     font=("Helvetica", 11, "bold"),
                     bg="#ecf0f1", width=22, anchor="e").pack(side="left")
            lbl = tk.Label(row_frame, text="—",
                           font=("Helvetica", 11), bg="#ecf0f1", anchor="w")
            lbl.pack(side="left", padx=(10, 0))
            self._stats_labels[key] = lbl

        # Category breakdown
        tk.Label(self._stats_frame, text=t("common.category") + ":",
                 font=("Helvetica", 11, "bold"), bg="#ecf0f1"
                 ).pack(anchor="w", pady=(15, 5))
        self._cat_lbl = tk.Label(self._stats_frame, text="—",
                                  font=("Helvetica", 10), bg="#ecf0f1",
                                  justify="left", anchor="w")
        self._cat_lbl.pack(anchor="w", padx=(20, 0))

        # Stage breakdown
        tk.Label(self._stats_frame, text=t("common.status") + ":",
                 font=("Helvetica", 11, "bold"), bg="#ecf0f1"
                 ).pack(anchor="w", pady=(10, 5))
        self._stage_lbl = tk.Label(self._stats_frame, text="—",
                                    font=("Helvetica", 10), bg="#ecf0f1",
                                    justify="left", anchor="w")
        self._stage_lbl.pack(anchor="w", padx=(20, 0))

    def _load_stats(self):
        try:
            stats = self._svc.get_stats()
            for key, lbl in self._stats_labels.items():
                lbl.config(text=str(stats.get(key, 0)))

            by_cat = stats.get("by_category", {})
            if by_cat:
                self._cat_lbl.config(
                    text="\n".join(f"{k}: {v}" for k, v in by_cat.items()))
            else:
                self._cat_lbl.config(text=t("common.no_data"))

            by_stage = stats.get("by_stage", {})
            if by_stage:
                self._stage_lbl.config(
                    text="\n".join(f"{k}: {v}" for k, v in by_stage.items()))
            else:
                self._stage_lbl.config(text=t("common.no_data"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._comp_tree, "complaints.csv")

    # ---- Refresh ----

    def refresh(self):
        self._load_complaints()
        self._load_stats()
