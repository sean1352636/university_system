"""UCAS Applications GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.ucas.services.ucas_service import UCASService


class UCASFrame(tk.Frame):
    """UCAS Applications management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = UCASService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="UCAS Applications",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_applications_tab()
        self._build_choices_tab()
        self._build_statistics_tab()
        

    def _build_applications_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Applications")
        cols = ("id", "sid", "first_name", "application_status", "predicted_tariff",)
        self._tree_0 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_0.heading("id", text="ID")
        self._tree_0.column("id", width=40, anchor="center")
        self._tree_0.heading("sid", text="Student")
        self._tree_0.column("sid", width=80, anchor="center")
        self._tree_0.heading("first_name", text="Name")
        self._tree_0.column("first_name", width=120, anchor="center")
        self._tree_0.heading("application_status", text="Status")
        self._tree_0.column("application_status", width=100, anchor="center")
        self._tree_0.heading("predicted_tariff", text="Tariff")
        self._tree_0.column("predicted_tariff", width=60, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_0.yview)
        self._tree_0.configure(yscrollcommand=vsb.set)
        self._tree_0.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_choices_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Choices")
        cols = ("id", "university_name", "course_title", "offer_status", "is_firm",)
        self._tree_1 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_1.heading("id", text="ID")
        self._tree_1.column("id", width=40, anchor="center")
        self._tree_1.heading("university_name", text="University")
        self._tree_1.column("university_name", width=180, anchor="center")
        self._tree_1.heading("course_title", text="Course")
        self._tree_1.column("course_title", width=150, anchor="center")
        self._tree_1.heading("offer_status", text="Offer")
        self._tree_1.column("offer_status", width=80, anchor="center")
        self._tree_1.heading("is_firm", text="Firm")
        self._tree_1.column("is_firm", width=40, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_1.yview)
        self._tree_1.configure(yscrollcommand=vsb.set)
        self._tree_1.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_statistics_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Statistics")
        self._statistics_frame = tk.Frame(tab, bg="#ecf0f1")
        self._statistics_frame.pack(fill="both", expand=True)
        tk.Label(self._statistics_frame, text="Statistics view",
                 font=("Helvetica", 12), bg="#ecf0f1").pack(pady=20)


    def _load_applications(self):
        self._tree_0.delete(*self._tree_0.get_children())

    def _load_choices(self):
        self._tree_1.delete(*self._tree_1.get_children())

    def refresh(self):
        self._load_applications()
        self._load_choices()

