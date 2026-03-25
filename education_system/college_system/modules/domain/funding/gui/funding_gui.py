"""Funding & ILR GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.funding.services.funding_service import FundingService
from education_system.college_system.core.i18n import t


class FundingFrame(tk.Frame):
    """Funding & ILR management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = FundingService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("funding.management"),
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_records_tab()
        self._build_evidence_tab()
        self._build_rules_tab()
        self._build_resits_tab()

    def _build_records_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("funding.management"))
        cols = ("id", "student_id", "learning_aim", "funding_model", "hours", "status")
        self._rec_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("student_id", "Student", 60),
                         ("learning_aim", "Learning Aim", 160), ("funding_model", "Model", 60),
                         ("hours", "Hours", 80), ("status", "Status", 90)]:
            self._rec_tree.heading(c, text=h)
            self._rec_tree.column(c, width=w, anchor="center")
        self._rec_tree.pack(fill="both", expand=True)

        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(5, 0))
        ttk.Button(btn_frame, text="Export CSV", command=self._export_csv).pack(side="left", padx=4)

    def _build_evidence_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("funding.evidence"))
        cols = ("id", "funding_record_id", "evidence_type", "verified")
        self._ev_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("funding_record_id", "Record", 60),
                         ("evidence_type", "Type", 160), ("verified", "Verified", 60)]:
            self._ev_tree.heading(c, text=h)
            self._ev_tree.column(c, width=w, anchor="center")
        self._ev_tree.pack(fill="both", expand=True)

        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(5, 0))
        ttk.Button(btn_frame, text="Export CSV", command=self._export_evidence_csv).pack(side="left", padx=4)

    def _build_rules_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("funding.rules"))
        cols = ("id", "rule_code", "description", "rule_type", "active")
        self._rule_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("rule_code", "Code", 100),
                         ("description", "Description", 200), ("rule_type", "Type", 80),
                         ("active", "Active", 50)]:
            self._rule_tree.heading(c, text=h)
            self._rule_tree.column(c, width=w, anchor="center")
        self._rule_tree.pack(fill="both", expand=True)

        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(5, 0))
        ttk.Button(btn_frame, text="Export CSV", command=self._export_rules_csv).pack(side="left", padx=4)

    def _build_resits_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("funding.resit_tracking"))
        cols = ("id", "student_id", "subject", "gcse_grade", "status", "result")
        self._resit_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("student_id", "Student", 60),
                         ("subject", "Subject", 80), ("gcse_grade", "Entry Grade", 80),
                         ("status", "Status", 80), ("result", "Result", 80)]:
            self._resit_tree.heading(c, text=h)
            self._resit_tree.column(c, width=w, anchor="center")
        self._resit_tree.pack(fill="both", expand=True)

        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(5, 0))
        ttk.Button(btn_frame, text="Export CSV", command=self._export_resits_csv).pack(side="left", padx=4)

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._rec_tree, "funding_records_export.csv")

    def _export_evidence_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._ev_tree, "funding_evidence_export.csv")

    def _export_rules_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._rule_tree, "funding_rules_export.csv")

    def _export_resits_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._resit_tree, "funding_resits_export.csv")

    def refresh(self):
        self._load_records()
        self._load_evidence()
        self._load_rules()
        self._load_resits()

    def _load_records(self):
        self._rec_tree.delete(*self._rec_tree.get_children())
        try:
            for r in self._svc.list_funding_records():
                hours = f"{r['actual_hours']}/{r['planned_hours']}"
                self._rec_tree.insert("", "end", values=(
                    r["id"], r["student_id"], r.get("learning_aim") or "-",
                    r["funding_model"], hours, r["completion_status"]))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_evidence(self):
        self._ev_tree.delete(*self._ev_tree.get_children())
        try:
            for e in self._svc.list_evidence():
                self._ev_tree.insert("", "end", values=(
                    e["id"], e["funding_record_id"], e["evidence_type"],
                    "Yes" if e["verified"] else "No"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_rules(self):
        self._rule_tree.delete(*self._rule_tree.get_children())
        try:
            for r in self._svc.list_rules(active_only=False):
                self._rule_tree.insert("", "end", values=(
                    r["id"], r["rule_code"], r.get("description") or "-",
                    r["rule_type"], "Yes" if r["is_active"] else "No"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_resits(self):
        self._resit_tree.delete(*self._resit_tree.get_children())
        try:
            for r in self._svc.list_resits():
                self._resit_tree.insert("", "end", values=(
                    r["id"], r["student_id"], r["subject"],
                    r.get("gcse_grade_on_entry") or "-",
                    r["status"], r.get("latest_result") or "-"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
