"""Governance & Board GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.core.i18n import t
from education_system.college_system.modules.domain.governance.services.governance_service import GovernanceService


class GovernanceFrame(tk.Frame):
    """Governance & Board management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = GovernanceService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("governance.management"),
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)
        ttk.Button(header, text="Export CSV", command=self._export_csv).pack(side="right", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_governors_tab()
        self._build_meetings_tab()
        self._build_actions_tab()
        self._build_strategic_plan_tab()
        

    def _build_governors_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("governance.governors"))
        cols = ("id", "first_name", "last_name", "governor_type", "role_on_board", "status",)
        self._tree_0 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_0.heading("id", text=t("common.id"))
        self._tree_0.column("id", width=40, anchor="center")
        self._tree_0.heading("first_name", text=t("common.name"))
        self._tree_0.column("first_name", width=100, anchor="center")
        self._tree_0.heading("last_name", text=t("common.name"))
        self._tree_0.column("last_name", width=100, anchor="center")
        self._tree_0.heading("governor_type", text=t("common.type"))
        self._tree_0.column("governor_type", width=100, anchor="center")
        self._tree_0.heading("role_on_board", text=t("common.position"))
        self._tree_0.column("role_on_board", width=120, anchor="center")
        self._tree_0.heading("status", text=t("common.status"))
        self._tree_0.column("status", width=70, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_0.yview)
        self._tree_0.configure(yscrollcommand=vsb.set)
        self._tree_0.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_meetings_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("governance.meetings"))
        cols = ("id", "meeting_date", "meeting_type", "status",)
        self._tree_1 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_1.heading("id", text=t("common.id"))
        self._tree_1.column("id", width=40, anchor="center")
        self._tree_1.heading("meeting_date", text=t("common.date"))
        self._tree_1.column("meeting_date", width=90, anchor="center")
        self._tree_1.heading("meeting_type", text=t("common.type"))
        self._tree_1.column("meeting_type", width=100, anchor="center")
        self._tree_1.heading("status", text=t("common.status"))
        self._tree_1.column("status", width=80, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_1.yview)
        self._tree_1.configure(yscrollcommand=vsb.set)
        self._tree_1.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_actions_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("common.actions"))
        cols = ("id", "action_description", "due_date", "status",)
        self._tree_2 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_2.heading("id", text=t("common.id"))
        self._tree_2.column("id", width=40, anchor="center")
        self._tree_2.heading("action_description", text=t("common.description"))
        self._tree_2.column("action_description", width=250, anchor="center")
        self._tree_2.heading("due_date", text=t("common.end_date"))
        self._tree_2.column("due_date", width=90, anchor="center")
        self._tree_2.heading("status", text=t("common.status"))
        self._tree_2.column("status", width=80, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_2.yview)
        self._tree_2.configure(yscrollcommand=vsb.set)
        self._tree_2.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_strategic_plan_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("governance.committees"))
        cols = ("id", "title", "priority_area", "status",)
        self._tree_3 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_3.heading("id", text=t("common.id"))
        self._tree_3.column("id", width=40, anchor="center")
        self._tree_3.heading("title", text=t("common.title"))
        self._tree_3.column("title", width=200, anchor="center")
        self._tree_3.heading("priority_area", text=t("common.priority"))
        self._tree_3.column("priority_area", width=120, anchor="center")
        self._tree_3.heading("status", text=t("common.status"))
        self._tree_3.column("status", width=80, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_3.yview)
        self._tree_3.configure(yscrollcommand=vsb.set)
        self._tree_3.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")


    def _load_governors(self):
        self._tree_0.delete(*self._tree_0.get_children())
        try:
            for g in self._svc.list_governors():
                self._tree_0.insert("", "end", values=(
                    g["id"], g.get("first_name", ""),
                    g.get("last_name", ""),
                    g.get("governor_type") or "-",
                    g.get("role_on_board") or "-",
                    g.get("status") or "-"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_meetings(self):
        self._tree_1.delete(*self._tree_1.get_children())
        try:
            for m in self._svc.list_meetings():
                self._tree_1.insert("", "end", values=(
                    m["id"], m.get("meeting_date") or "-",
                    m.get("meeting_type") or "-",
                    m.get("status") or "-"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_actions(self):
        self._tree_2.delete(*self._tree_2.get_children())
        try:
            for a in self._svc.list_actions():
                self._tree_2.insert("", "end", values=(
                    a["id"], a.get("action_description") or "-",
                    a.get("due_date") or "-",
                    a.get("status") or "-"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_strategic_plan(self):
        self._tree_3.delete(*self._tree_3.get_children())
        try:
            for p in self._svc.list_strategic_plans():
                self._tree_3.insert("", "end", values=(
                    p["id"], p.get("title") or "-",
                    p.get("priority_area") or "-",
                    p.get("status") or "-"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _export_csv(self):
        """Export the currently visible tab's treeview to CSV."""
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        tab_index = self._nb.index(self._nb.select())
        trees = [
            (self._tree_0, "governance_governors_export.csv"),
            (self._tree_1, "governance_meetings_export.csv"),
            (self._tree_2, "governance_actions_export.csv"),
            (self._tree_3, "governance_strategic_plans_export.csv"),
        ]
        if tab_index < len(trees):
            tree, filename = trees[tab_index]
            export_treeview_to_csv(tree, filename)

    def refresh(self):
        self._load_governors()
        self._load_meetings()
        self._load_actions()
        self._load_strategic_plan()

