"""Destinations & NEET GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.destinations.services.destination_service import DestinationService


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
        tk.Label(header, text="Destinations & NEET",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_destinations_tab()
        self._build_neet_tab()
        self._build_stats_tab()

    def _build_destinations_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Destinations")

        cols = ("id", "student_id", "type", "confirmed", "neet_risk", "contact")
        self._dest_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("student_id", "Student", 60),
                         ("type", "Type", 120), ("confirmed", "Confirmed", 150),
                         ("neet_risk", "NEET", 50), ("contact", "Contact", 50)]:
            self._dest_tree.heading(c, text=h)
            self._dest_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._dest_tree.yview)
        self._dest_tree.configure(yscrollcommand=vsb.set)
        self._dest_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_neet_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="NEET Risk")

        cols = ("id", "sid", "name", "type", "confirmed")
        self._neet_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("sid", "Student ID", 80),
                         ("name", "Name", 160), ("type", "Type", 120),
                         ("confirmed", "Confirmed", 150)]:
            self._neet_tree.heading(c, text=h)
            self._neet_tree.column(c, width=w, anchor="center")
        self._neet_tree.pack(fill="both", expand=True)

    def _build_stats_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Statistics")

        self._stats_frame = tk.Frame(tab, bg="#ecf0f1")
        self._stats_frame.pack(fill="both", expand=True)

        self._stats_labels: dict[str, tk.StringVar] = {}
        for label in ("Total", "Confirmed", "Unconfirmed", "NEET Risk"):
            row = tk.Frame(self._stats_frame, bg="#ecf0f1")
            row.pack(fill="x", pady=4, padx=10)
            tk.Label(row, text=f"{label}:", font=("Helvetica", 11, "bold"),
                     bg="#ecf0f1", width=15, anchor="w").pack(side="left")
            var = tk.StringVar(value="--")
            tk.Label(row, textvariable=var, font=("Helvetica", 11),
                     bg="#ecf0f1", fg="#2980b9").pack(side="left")
            self._stats_labels[label] = var

        tk.Label(self._stats_frame, text="By Type:",
                 font=("Helvetica", 11, "bold"), bg="#ecf0f1"
                 ).pack(anchor="w", padx=10, pady=(10, 4))

        cols = ("type", "count")
        self._type_tree = ttk.Treeview(self._stats_frame, columns=cols,
                                        show="headings", height=8)
        for c, h, w in [("type", "Type", 150), ("count", "Count", 80)]:
            self._type_tree.heading(c, text=h)
            self._type_tree.column(c, width=w, anchor="center")
        self._type_tree.pack(fill="x", padx=10)

    def refresh(self):
        self._load_destinations()
        self._load_neet()
        self._load_stats()

    def _load_destinations(self):
        self._dest_tree.delete(*self._dest_tree.get_children())
        try:
            for d in self._svc.list_destinations():
                self._dest_tree.insert("", "end", values=(
                    d["id"], d["student_id"], d["destination_type"],
                    d.get("confirmed_destination") or "-",
                    "Yes" if d["neet_risk"] else "-",
                    "Yes" if d["contact_made"] else "No"))
        except Exception as e:
            messagebox.showerror("Error", str(e))

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
            messagebox.showerror("Error", str(e))

    def _load_stats(self):
        try:
            stats = self._svc.get_destination_stats()
            self._stats_labels["Total"].set(str(stats["total"]))
            self._stats_labels["Confirmed"].set(str(stats["confirmed"]))
            self._stats_labels["Unconfirmed"].set(str(stats["unconfirmed"]))
            self._stats_labels["NEET Risk"].set(str(stats["neet_risk"]))

            self._type_tree.delete(*self._type_tree.get_children())
            for t in stats.get("by_type", []):
                self._type_tree.insert("", "end", values=(
                    t["destination_type"], t["count"]))
        except Exception as e:
            messagebox.showerror("Error", str(e))
