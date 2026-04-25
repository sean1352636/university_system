"""WellbeingFrame GUI for the University System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.modules.domain.student_affairs.student_wellbeing.services.wellbeing_service import WellbeingService


class WellbeingFrame(tk.Frame):
    """GUI for managing wellbeing."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = WellbeingService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Wellbeing",
                 fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Tabs
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=5, pady=5)

        self._referrals_tab = tk.Frame(self._notebook)
        self._notebook.add(self._referrals_tab, text="Referrals")
        self._check_ins_tab = tk.Frame(self._notebook)
        self._notebook.add(self._check_ins_tab, text="Check-ins")
        self._counselling_tab = tk.Frame(self._notebook)
        self._notebook.add(self._counselling_tab, text="Counselling")
        self._summary_tab = tk.Frame(self._notebook)
        self._notebook.add(self._summary_tab, text="Summary")

        self._build_list_tab()

    # Filter labels → corresponding referred_by SQL filter (None = all rows).
    _SOURCE_FILTERS = {
        "All sources":              None,
        "Auto (absence tracker)":   "absence_tracker",
        "Manual referrals":         "__not_absence_tracker__",
    }

    _COLUMNS = ("id", "student_id", "concern_type", "urgency",
                "status", "referred_by", "created_at")
    _COL_WIDTHS = {"id": 60, "student_id": 110, "concern_type": 130,
                   "urgency": 80, "status": 80, "referred_by": 140,
                   "created_at": 160}

    def _build_list_tab(self):
        """Build the main list tab with toolbar, filter, and treeview."""
        tab = self._notebook.tabs()[0]
        frame = self._notebook.nametowidget(tab)

        toolbar = tk.Frame(frame, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")
        tk.Button(toolbar, text="Refresh",
                  command=self.refresh).pack(side="left", padx=3)
        tk.Label(toolbar, text="Source:",
                 bg="#d5dbdb").pack(side="left", padx=(20, 4))
        self._source_var = tk.StringVar(value="All sources")
        cb = ttk.Combobox(toolbar, textvariable=self._source_var,
                          values=list(self._SOURCE_FILTERS.keys()),
                          state="readonly", width=22)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh())

        self._tree = ttk.Treeview(
            frame, columns=self._COLUMNS, show="headings",
            selectmode="browse")
        for col in self._COLUMNS:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=self._COL_WIDTHS.get(col, 100),
                              minwidth=40, anchor="w")
        self._tree.tag_configure("auto", background="#fff7d6")
        self._tree.tag_configure("high", foreground="#b91c1c")

        vsb = ttk.Scrollbar(frame, orient="vertical",
                            command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True,
                        padx=5, pady=5)
        vsb.pack(side="right", fill="y", pady=5)

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(frame, textvariable=self._status_var, anchor="w",
                 bg="#ecf0f1", padx=10).pack(fill="x", side="bottom")

        # Initial populate
        self.refresh()

    def refresh(self):
        """Reload referrals into the tree, honouring the source filter."""
        try:
            for item in self._tree.get_children():
                self._tree.delete(item)
            choice = self._source_var.get() if hasattr(self, "_source_var") \
                                            else "All sources"
            sentinel = self._SOURCE_FILTERS.get(choice)
            if sentinel == "__not_absence_tracker__":
                # Pull everything, exclude auto rows in Python — the service
                # doesn't currently support a NOT-EQUAL filter and we'd
                # rather not bypass its identifier validation.
                records = [
                    r for r in self._service.list_all()
                    if (r.get("referred_by") or "") != "absence_tracker"
                ]
            elif sentinel:
                records = self._service.list_all(referred_by=sentinel)
            else:
                records = self._service.list_all()

            for rec in records:
                values = tuple(rec.get(c, "") for c in self._COLUMNS)
                tags = []
                if (rec.get("referred_by") or "") == "absence_tracker":
                    tags.append("auto")
                if (rec.get("urgency") or "").lower() == "high":
                    tags.append("high")
                self._tree.insert("", "end", values=values, tags=tags)

            self._status_var.set(
                f"{len(records)} record(s) — filter: {choice}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
