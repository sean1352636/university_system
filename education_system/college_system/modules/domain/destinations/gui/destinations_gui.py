"""Destinations & NEET GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.destinations.services.destination_service import DestinationService
from education_system.college_system.core.i18n import t


class DestinationsFrame(tk.Frame):
    """Destinations & NEET management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = DestinationService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("destinations.management"),
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_destinations_tab()
        self._build_neet_tab()
        self._build_stats_tab()

    def _build_destinations_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("destinations.tab_destinations"))

        cols = ("id", "student_id", "type", "confirmed", "neet_risk", "contact")
        self._dest_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", t("common.id"), 40), ("student_id", t("destinations.student"), 60),
                         ("type", t("common.type"), 120), ("confirmed", t("destinations.confirmed"), 150),
                         ("neet_risk", t("destinations.neet_risk"), 50), ("contact", t("destinations.contact"), 50)]:
            self._dest_tree.heading(c, text=h)
            self._dest_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._dest_tree.yview)
        self._dest_tree.configure(yscrollcommand=vsb.set)
        self._dest_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(5, 0))
        ttk.Button(btn_frame, text="Export CSV", command=self._export_csv).pack(side="left", padx=4)

    def _build_neet_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("destinations.neet_risk"))

        cols = ("id", "sid", "name", "type", "confirmed")
        self._neet_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", t("common.id"), 40), ("sid", t("common.student_id"), 80),
                         ("name", t("common.name"), 160), ("type", t("common.type"), 120),
                         ("confirmed", t("destinations.confirmed"), 150)]:
            self._neet_tree.heading(c, text=h)
            self._neet_tree.column(c, width=w, anchor="center")
        self._neet_tree.pack(fill="both", expand=True)

        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(5, 0))
        ttk.Button(btn_frame, text="Export CSV", command=self._export_neet_csv).pack(side="left", padx=4)

    def _build_stats_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("destinations.statistics"))

        self._stats_frame = tk.Frame(tab, bg="#ecf0f1")
        self._stats_frame.pack(fill="both", expand=True)

        self._stats_key_total = t("common.total")
        self._stats_key_confirmed = t("destinations.confirmed")
        self._stats_key_unconfirmed = t("destinations.unconfirmed")
        self._stats_key_neet = t("destinations.neet_risk")
        self._stats_labels: dict[str, tk.StringVar] = {}
        for label in (self._stats_key_total, self._stats_key_confirmed, self._stats_key_unconfirmed, self._stats_key_neet):
            row = tk.Frame(self._stats_frame, bg="#ecf0f1")
            row.pack(fill="x", pady=4, padx=10)
            tk.Label(row, text=f"{label}:", font=("Helvetica", 11, "bold"),
                     bg="#ecf0f1", width=15, anchor="w").pack(side="left")
            var = tk.StringVar(value="--")
            tk.Label(row, textvariable=var, font=("Helvetica", 11),
                     bg="#ecf0f1", fg="#2980b9").pack(side="left")
            self._stats_labels[label] = var

        tk.Label(self._stats_frame, text=t("destinations.by_type"),
                 font=("Helvetica", 11, "bold"), bg="#ecf0f1"
                 ).pack(anchor="w", padx=10, pady=(10, 4))

        cols = ("type", "count")
        self._type_tree = ttk.Treeview(self._stats_frame, columns=cols,
                                        show="headings", height=8)
        for c, h, w in [("type", t("common.type"), 150), ("count", t("destinations.count"), 80)]:
            self._type_tree.heading(c, text=h)
            self._type_tree.column(c, width=w, anchor="center")
        self._type_tree.pack(fill="x", padx=10)

    def refresh(self):
        self._load_destinations()
        self._load_neet()
        self._load_stats()

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._dest_tree, "destinations_export.csv")

    def _export_neet_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._neet_tree, "destinations_neet_export.csv")

    def _load_destinations(self):
        self._dest_tree.delete(*self._dest_tree.get_children())
        try:
            for d in self._svc.list_destinations():
                self._dest_tree.insert("", "end", values=(
                    d["id"], d["student_id"], d["destination_type"],
                    d.get("confirmed_destination") or "-",
                    t("common.yes") if d["neet_risk"] else "-",
                    t("common.yes") if d["contact_made"] else t("common.no")))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_neet(self):
        self._neet_tree.delete(*self._neet_tree.get_children())
        try:
            for s in self._svc.get_neet_risk_students():
                name = f"{s.get('first_name', '')} {s.get('last_name', '')}"
                self._neet_tree.insert("", "end", values=(
                    s["id"], s.get("sid", "-"), name,
                    s["destination_type"],
                    s.get("confirmed_destination") or "-"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_stats(self):
        try:
            stats = self._svc.get_destination_stats()
            self._stats_labels[self._stats_key_total].set(str(stats["total"]))
            self._stats_labels[self._stats_key_confirmed].set(str(stats["confirmed"]))
            self._stats_labels[self._stats_key_unconfirmed].set(str(stats["unconfirmed"]))
            self._stats_labels[self._stats_key_neet].set(str(stats["neet_risk"]))

            self._type_tree.delete(*self._type_tree.get_children())
            for row_data in stats.get("by_type", []):
                self._type_tree.insert("", "end", values=(
                    row_data["destination_type"], row_data["count"]))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
