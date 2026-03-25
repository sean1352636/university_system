"""Ofsted SEF Builder GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.sef_builder.services.sef_builder_service import SEFBuilderService
from education_system.college_system.core.i18n import t


class SEFBuilderFrame(tk.Frame):
    """Ofsted Self-Evaluation Form builder with evidence linking."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = SEFBuilderService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Ofsted SEF Builder",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_documents_tab()
        self._build_judgement_tab()
        self._build_evidence_tab()
        self._build_dashboard_tab()

    def _build_documents_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="SEF Documents")

        cols = ("id", "title", "academic_year", "version", "overall", "status")
        self._doc_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c, h, w in [("id", "ID", 40), ("title", "Title", 200),
                         ("academic_year", "Year", 80), ("version", "Version", 60),
                         ("overall", "Overall", 120), ("status", "Status", 80)]:
            self._doc_tree.heading(c, text=h)
            self._doc_tree.column(c, width=w, anchor="center")
        self._doc_tree.pack(fill="both", expand=True)

        btn = tk.Frame(tab, bg="#ecf0f1")
        btn.pack(fill="x", pady=(5, 0))
        ttk.Button(btn, text="Create SEF", command=self._create_sef).pack(side="left", padx=4)
        ttk.Button(btn, text="Approve", command=self._approve_sef).pack(side="left", padx=4)
        ttk.Button(btn, text="Export", command=self._export_sef).pack(side="left", padx=4)
        ttk.Button(btn, text="Pull System Data", command=self._pull_data).pack(side="left", padx=4)
        ttk.Button(btn, text="Refresh", command=self._load_documents).pack(side="right", padx=4)

    def _build_judgement_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Judgement Areas")

        cols = ("id", "area_number", "area_name", "self_grade")
        self._ja_tree = ttk.Treeview(tab, columns=cols, show="headings", height=10)
        for c, h, w in [("id", "ID", 40), ("area_number", "No.", 50),
                         ("area_name", "Area Name", 250), ("self_grade", "Self-Grade", 120)]:
            self._ja_tree.heading(c, text=h)
            self._ja_tree.column(c, width=w, anchor="center")
        self._ja_tree.pack(fill="both", expand=True)

        form = tk.LabelFrame(tab, text="Add Judgement Area", bg="#ecf0f1")
        form.pack(fill="x", pady=(5, 0))

        r = tk.Frame(form, bg="#ecf0f1")
        r.pack(fill="x", padx=5, pady=2)
        tk.Label(r, text="SEF ID:", bg="#ecf0f1").pack(side="left")
        self._ja_sef_id = tk.Entry(r, width=8)
        self._ja_sef_id.pack(side="left", padx=4)
        tk.Label(r, text="Area No:", bg="#ecf0f1").pack(side="left")
        self._ja_num = tk.Entry(r, width=6)
        self._ja_num.pack(side="left", padx=4)
        tk.Label(r, text="Area Name:", bg="#ecf0f1").pack(side="left")
        self._ja_name = tk.Entry(r, width=30)
        self._ja_name.pack(side="left", padx=4)
        tk.Label(r, text="Grade:", bg="#ecf0f1").pack(side="left")
        self._ja_grade = ttk.Combobox(r, values=["outstanding", "good", "requires_improvement", "inadequate"], width=18, state="readonly")
        self._ja_grade.pack(side="left", padx=4)
        ttk.Button(r, text="Add", command=self._add_judgement).pack(side="left", padx=4)

    def _build_evidence_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Evidence Links")

        cols = ("id", "area_id", "evidence_type", "description", "data_value")
        self._ev_tree = ttk.Treeview(tab, columns=cols, show="headings", height=10)
        for c, h, w in [("id", "ID", 40), ("area_id", "Area ID", 60),
                         ("evidence_type", "Type", 100), ("description", "Description", 250),
                         ("data_value", "Value", 100)]:
            self._ev_tree.heading(c, text=h)
            self._ev_tree.column(c, width=w, anchor="center")
        self._ev_tree.pack(fill="both", expand=True)

        form = tk.Frame(tab, bg="#ecf0f1")
        form.pack(fill="x", pady=(5, 0))
        tk.Label(form, text="Area ID:", bg="#ecf0f1").pack(side="left")
        self._ev_area_id = tk.Entry(form, width=8)
        self._ev_area_id.pack(side="left", padx=4)
        tk.Label(form, text="Type:", bg="#ecf0f1").pack(side="left")
        self._ev_type = ttk.Combobox(form, values=["data", "document", "observation", "survey", "outcome", "external"], width=12, state="readonly")
        self._ev_type.pack(side="left", padx=4)
        tk.Label(form, text="Description:", bg="#ecf0f1").pack(side="left")
        self._ev_desc = tk.Entry(form, width=30)
        self._ev_desc.pack(side="left", padx=4)
        ttk.Button(form, text="Add Evidence", command=self._add_evidence).pack(side="left", padx=4)

    def _build_dashboard_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="SEF Summary")

        self._summary_text = tk.Text(tab, wrap="word", height=20, font=("Helvetica", 10))
        self._summary_text.pack(fill="both", expand=True)
        ttk.Button(tab, text="Load Summary", command=self._load_summary).pack(pady=5)

    def refresh(self):
        self._load_documents()

    def _load_documents(self):
        self._doc_tree.delete(*self._doc_tree.get_children())
        try:
            for s in self._svc.list_sefs():
                self._doc_tree.insert("", "end", values=(
                    s["id"], s["title"], s.get("academic_year", "-"),
                    s.get("version", "1.0"), s.get("overall_effectiveness", "-"),
                    s["status"]))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _create_sef(self):
        dlg = tk.Toplevel(self)
        dlg.title("Create SEF Document")
        dlg.geometry("350x200")
        tk.Label(dlg, text="Academic Year:").pack(pady=4)
        ay = tk.Entry(dlg)
        ay.pack()
        tk.Label(dlg, text="Title:").pack(pady=4)
        title = tk.Entry(dlg, width=30)
        title.pack()
        def _do():
            try:
                self._svc.create_sef(ay.get(), title.get(), created_by=None)
                dlg.destroy()
                self._load_documents()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        ttk.Button(dlg, text="Create", command=_do).pack(pady=10)

    def _approve_sef(self):
        sel = self._doc_tree.selection()
        if not sel:
            return
        sid = self._doc_tree.item(sel[0])["values"][0]
        try:
            self._svc.approve_sef(sid, approved_by=None)
            self._load_documents()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _export_sef(self):
        sel = self._doc_tree.selection()
        if not sel:
            return
        sid = self._doc_tree.item(sel[0])["values"][0]
        try:
            data = self._svc.export_sef(sid)
            messagebox.showinfo("Exported", f"SEF '{data.get('title', '')}' exported successfully")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _pull_data(self):
        sel = self._doc_tree.selection()
        if not sel:
            return
        sid = self._doc_tree.item(sel[0])["values"][0]
        try:
            count = self._svc.pull_system_data(sid)
            messagebox.showinfo("Data Pulled", f"Pulled {count} evidence items from system data")
            self._load_documents()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _add_judgement(self):
        try:
            sid = int(self._ja_sef_id.get())
            self._svc.add_judgement_area(
                sid, self._ja_name.get(), self._ja_num.get(),
                self_grade=self._ja_grade.get() or None)
            messagebox.showinfo("Added", "Judgement area added")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _add_evidence(self):
        try:
            area_id = int(self._ev_area_id.get())
            self._svc.add_evidence_link(
                area_id, self._ev_type.get() or "data", self._ev_desc.get())
            messagebox.showinfo("Added", "Evidence linked")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_summary(self):
        sel = self._doc_tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Select a SEF document first")
            return
        sid = self._doc_tree.item(sel[0])["values"][0]
        try:
            data = self._svc.get_sef_summary(sid)
            self._summary_text.delete("1.0", "end")
            self._summary_text.insert("1.0", f"Title: {data.get('title', '-')}\n")
            self._summary_text.insert("end", f"Academic Year: {data.get('academic_year', '-')}\n")
            self._summary_text.insert("end", f"Status: {data.get('status', '-')}\n")
            self._summary_text.insert("end", f"Overall: {data.get('overall_effectiveness', '-')}\n\n")
            for area in data.get("judgement_areas", []):
                self._summary_text.insert("end", f"\n--- {area.get('area_number', '')}. {area.get('area_name', '')} ---\n")
                self._summary_text.insert("end", f"Grade: {area.get('self_grade', '-')}\n")
                self._summary_text.insert("end", f"Strengths: {area.get('strengths', '-')}\n")
                self._summary_text.insert("end", f"AFI: {area.get('areas_for_improvement', '-')}\n")
        except Exception as e:
            messagebox.showerror("Error", str(e))
