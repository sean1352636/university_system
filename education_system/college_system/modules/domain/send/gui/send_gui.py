"""SEND/ALS GUI for managing special educational needs and interventions."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.send.services.send_service import SENDService
from education_system.college_system.core.i18n import t


class SENDFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = SENDService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("send.title"), font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        # SEND Records tab
        self._records_tab = tk.Frame(self._nb)
        self._nb.add(self._records_tab, text=t("send.send_records"))
        self._build_records_tab()

        # Interventions tab
        self._int_tab = tk.Frame(self._nb)
        self._nb.add(self._int_tab, text=t("send.interventions"))
        self._build_interventions_tab()

    def _build_records_tab(self):
        toolbar = tk.Frame(self._records_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_records).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Export CSV", command=self._export_records_csv).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("send.new_record"), command=self._new_record).pack(side="right", padx=5)

        cols = ("id", "student", "need_type", "ehcp", "status", "review_date")
        self._rec_tree = ttk.Treeview(self._records_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 120, 120, 50, 80, 100)):
            self._rec_tree.heading(c, text=c.replace("_", " ").title())
            self._rec_tree.column(c, width=w)
        self._rec_tree.pack(fill="both", expand=True, padx=5, pady=5)

        self._rec_detail = tk.Text(self._records_tab, height=4, state="disabled")
        self._rec_detail.pack(fill="x", padx=5, pady=5)
        self._rec_tree.bind("<<TreeviewSelect>>", self._on_record_select)

    def _build_interventions_tab(self):
        toolbar = tk.Frame(self._int_tab)
        toolbar.pack(fill="x", padx=5, pady=5)
        tk.Label(toolbar, text=t("common.student_id_colon")).pack(side="left", padx=5)
        self._int_sid = tk.Entry(toolbar, width=10)
        self._int_sid.pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("common.search"), command=self._load_interventions).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Export CSV", command=self._export_interventions_csv).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("send.new_intervention"), command=self._new_intervention).pack(side="right", padx=5)

        cols = ("id", "student", "type", "status", "start", "end")
        self._int_tree = ttk.Treeview(self._int_tab, columns=cols, show="headings", height=15)
        for c, w in zip(cols, (50, 120, 120, 80, 100, 100)):
            self._int_tree.heading(c, text=c.title())
            self._int_tree.column(c, width=w)
        self._int_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _load_records(self):
        for item in self._rec_tree.get_children():
            self._rec_tree.delete(item)
        try:
            records = self._svc.list_records()
            for r in records:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                self._rec_tree.insert("", "end", iid=str(r["id"]), values=(
                    r["id"], name, r.get("need_type", ""),
                    "Yes" if r.get("ehcp") else "No",
                    r.get("status", ""), r.get("review_date", "")))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _on_record_select(self, _event=None):
        sel = self._rec_tree.selection()
        if not sel:
            return
        try:
            rec = self._svc.get_record(int(sel[0]))
            self._rec_detail.configure(state="normal")
            self._rec_detail.delete("1.0", "end")
            self._rec_detail.insert("end", f"Description: {rec.get('description', '')}\n")
            self._rec_detail.insert("end", f"Support Plan: {rec.get('support_plan', '')}\n")
            self._rec_detail.insert("end", f"Access Arrangements: {rec.get('exam_access_arrangements', '')}")
            self._rec_detail.configure(state="disabled")
        except Exception:
            pass

    def _new_record(self):
        win = tk.Toplevel(self)
        win.title(t("send.new_send_record"))
        win.geometry("400x350")
        fields = {}
        row = 0
        for label, key in [(t("common.student_id_required"), "student_id"), (t("send.need_type_required"), "need_type")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1
        tk.Label(win, text=t("common.description_required")).grid(row=row, column=0, padx=10, pady=5, sticky="ne")
        desc = tk.Text(win, width=30, height=4)
        desc.grid(row=row, column=1, padx=10, pady=5)
        row += 1
        tk.Label(win, text=t("send.support_plan_colon")).grid(row=row, column=0, padx=10, pady=5, sticky="ne")
        plan = tk.Text(win, width=30, height=3)
        plan.grid(row=row, column=1, padx=10, pady=5)
        row += 1
        ehcp_var = tk.BooleanVar()
        ttk.Checkbutton(win, text=t("send.ehcp_in_place"), variable=ehcp_var).grid(row=row, column=1, sticky="w", padx=10)
        row += 1

        def save():
            try:
                self._svc.create_record(
                    student_id=int(fields["student_id"].get().strip()),
                    need_type=fields["need_type"].get().strip(),
                    description=desc.get("1.0", "end").strip(),
                    ehcp=1 if ehcp_var.get() else 0,
                    support_plan=plan.get("1.0", "end").strip() or None)
                messagebox.showinfo(t("common.success"), t("send.record_created"))
                win.destroy()
                self._load_records()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.save"), command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _load_interventions(self):
        for item in self._int_tree.get_children():
            self._int_tree.delete(item)
        try:
            sid = self._int_sid.get().strip()
            interventions = self._svc.list_interventions(
                student_id=int(sid) if sid else None)
            for iv in interventions:
                name = f"{iv.get('first_name', '')} {iv.get('last_name', '')}".strip() or str(iv.get("student_id", ""))
                self._int_tree.insert("", "end", values=(
                    iv["id"], name, iv.get("intervention_type", ""),
                    iv.get("status", ""), iv.get("start_date", ""),
                    iv.get("target_end_date", "")))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _new_intervention(self):
        win = tk.Toplevel(self)
        win.title(t("send.new_intervention"))
        win.geometry("400x300")
        fields = {}
        row = 0
        for label, key in [(t("common.student_id_required"), "student_id"), (t("send.type_required"), "intervention_type"),
                           (t("send.start_date_colon"), "start_date"), (t("send.target_end_date_colon"), "target_end_date")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1
        tk.Label(win, text=t("common.description_required")).grid(row=row, column=0, padx=10, pady=5, sticky="ne")
        desc = tk.Text(win, width=30, height=4)
        desc.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            try:
                self._svc.create_intervention(
                    student_id=int(fields["student_id"].get().strip()),
                    intervention_type=fields["intervention_type"].get().strip(),
                    description=desc.get("1.0", "end").strip(),
                    start_date=fields["start_date"].get().strip() or None,
                    target_end_date=fields["target_end_date"].get().strip() or None)
                messagebox.showinfo(t("common.success"), t("send.intervention_created"))
                win.destroy()
                self._load_interventions()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))
        ttk.Button(win, text=t("common.save"), command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _export_records_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._rec_tree, "send_records_export.csv")

    def _export_interventions_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._int_tree, "send_interventions_export.csv")

    def refresh(self):
        self._load_records()
