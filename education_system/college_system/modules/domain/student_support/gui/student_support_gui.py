"""Student Support GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.student_support.services.student_support_service import StudentSupportService


class StudentSupportFrame(tk.Frame):
    """Student support management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = StudentSupportService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Student Support",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_interventions_tab()
        self._build_risks_tab()
        self._build_documents_tab()

    def _build_interventions_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Interventions")

        cols = ("id", "student_id", "type", "status", "sessions", "impact")
        self._int_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("student_id", "Student", 60),
                         ("type", "Type", 100), ("status", "Status", 80),
                         ("sessions", "Sessions", 80), ("impact", "Impact", 80)]:
            self._int_tree.heading(c, text=h)
            self._int_tree.column(c, width=w, anchor="center")
        self._int_tree.pack(fill="both", expand=True)

    def _build_risks_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Risk Register")

        cols = ("id", "student_id", "risk_type", "risk_level", "status")
        self._risk_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("student_id", "Student", 60),
                         ("risk_type", "Type", 120), ("risk_level", "Level", 80),
                         ("status", "Status", 80)]:
            self._risk_tree.heading(c, text=h)
            self._risk_tree.column(c, width=w, anchor="center")
        self._risk_tree.pack(fill="both", expand=True)

    def _build_documents_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Documents")

        cols = ("id", "student_id", "document_type", "title", "verified")
        self._doc_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("student_id", "Student", 60),
                         ("document_type", "Type", 120), ("title", "Title", 180),
                         ("verified", "Verified", 60)]:
            self._doc_tree.heading(c, text=h)
            self._doc_tree.column(c, width=w, anchor="center")
        self._doc_tree.pack(fill="both", expand=True)

    def refresh(self):
        self._load_interventions()
        self._load_risks()
        self._load_documents()

    def _load_interventions(self):
        self._int_tree.delete(*self._int_tree.get_children())
        try:
            for i in self._svc.list_interventions():
                sessions = f"{i['sessions_attended']}/{i['sessions_planned']}"
                self._int_tree.insert("", "end", values=(
                    i["id"], i["student_id"], i["intervention_type"],
                    i["status"], sessions, i.get("impact_rating") or "-"))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_risks(self):
        self._risk_tree.delete(*self._risk_tree.get_children())
        try:
            for r in self._svc.list_risks():
                self._risk_tree.insert("", "end", values=(
                    r["id"], r["student_id"], r["risk_type"],
                    r["risk_level"], r["status"]))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_documents(self):
        self._doc_tree.delete(*self._doc_tree.get_children())
        try:
            for d in self._svc.list_documents():
                self._doc_tree.insert("", "end", values=(
                    d["id"], d["student_id"], d["document_type"],
                    d["title"], "Yes" if d["verified"] else "No"))
        except Exception as e:
            messagebox.showerror("Error", str(e))
