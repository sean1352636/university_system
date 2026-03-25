"""Census ILR GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.college_system.modules.domain.census_ilr.services.census_ilr_service import (
    CensusILRService,
)
from education_system.college_system.core.i18n import t


class CensusILRFrame(tk.Frame):
    """GUI for DfE School Census and ILR data extraction."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = CensusILRService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text=t("census_ilr.title", "Census / ILR Data Extraction"),
            font=("Helvetica", 15, "bold"),
            bg="#2c3e50",
            fg="white",
        ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_returns_tab()
        self._build_generate_tab()
        self._build_export_tab()

    # ── Returns List Tab ──

    def _build_returns_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("census_ilr.returns", "Returns List"))

        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text=t("census_ilr.type", "Type:"), bg="#ecf0f1").pack(side="left", padx=2)
        self._filter_type = ttk.Combobox(toolbar, values=["", "census", "ilr", "hesa"], width=10, state="readonly")
        self._filter_type.pack(side="left", padx=2)
        self._filter_type.set("")

        tk.Label(toolbar, text=t("census_ilr.year", "Year:"), bg="#ecf0f1").pack(side="left", padx=2)
        self._filter_year = ttk.Entry(toolbar, width=12)
        self._filter_year.pack(side="left", padx=2)

        ttk.Button(toolbar, text=t("census_ilr.search", "Search"), command=self._load_returns).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("census_ilr.new", "New Return"), command=self._new_return_dialog).pack(side="left", padx=5)

        cols = ("id", "return_type", "academic_year", "term", "collection_period", "status", "record_count", "submission_deadline")
        self._returns_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self._returns_tree.heading(c, text=c.replace("_", " ").title())
            self._returns_tree.column(c, width=110)
        self._returns_tree.pack(fill="both", expand=True, padx=5, pady=5)

        scroll = ttk.Scrollbar(tab, orient="vertical", command=self._returns_tree.yview)
        self._returns_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

    def _load_returns(self):
        for row in self._returns_tree.get_children():
            self._returns_tree.delete(row)
        try:
            rt = self._filter_type.get() or None
            yr = self._filter_year.get().strip() or None
            returns = self._svc.list_returns(return_type=rt, academic_year=yr)
            for r in returns:
                self._returns_tree.insert("", "end", values=(
                    r["id"], r["return_type"], r["academic_year"], r.get("term", ""),
                    r.get("collection_period", ""), r["status"], r.get("record_count", 0),
                    r.get("submission_deadline", ""),
                ))
        except Exception as exc:
            messagebox.showerror(t("census_ilr.error", "Error"), str(exc))

    def _new_return_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("census_ilr.new_return", "New Return"))
        dlg.geometry("400x300")
        dlg.transient(self)

        fields = {}
        for i, (label, key) in enumerate([
            ("Return Type:", "return_type"),
            ("Academic Year:", "academic_year"),
            ("Term:", "term"),
            ("Collection Period:", "collection_period"),
            ("Submission Deadline:", "submission_deadline"),
        ]):
            tk.Label(dlg, text=label).grid(row=i, column=0, padx=10, pady=5, sticky="e")
            if key == "return_type":
                w = ttk.Combobox(dlg, values=["census", "ilr", "hesa"], state="readonly", width=20)
                w.set("census")
            else:
                w = ttk.Entry(dlg, width=22)
            w.grid(row=i, column=1, padx=10, pady=5)
            fields[key] = w

        def _save():
            try:
                self._svc.create_return(
                    fields["return_type"].get(),
                    fields["academic_year"].get(),
                    fields["term"].get(),
                    fields["collection_period"].get(),
                    fields["submission_deadline"].get(),
                )
                dlg.destroy()
                self._load_returns()
                messagebox.showinfo(t("census_ilr.success", "Success"), t("census_ilr.return_created", "Return created."))
            except Exception as exc:
                messagebox.showerror(t("census_ilr.error", "Error"), str(exc))

        ttk.Button(dlg, text=t("census_ilr.save", "Save"), command=_save).grid(row=5, column=0, columnspan=2, pady=15)

    # ── Generate & Validate Tab ──

    def _build_generate_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("census_ilr.generate", "Generate & Validate"))

        frame = tk.Frame(tab, bg="#ecf0f1")
        frame.pack(padx=20, pady=20, fill="x")

        tk.Label(frame, text=t("census_ilr.return_id", "Return ID:"), bg="#ecf0f1").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self._gen_return_id = ttk.Entry(frame, width=10)
        self._gen_return_id.grid(row=0, column=1, padx=5, pady=5)

        ttk.Button(frame, text=t("census_ilr.gen_census", "Generate Census Data"), command=self._generate_census).grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(frame, text=t("census_ilr.gen_ilr", "Generate ILR Data"), command=self._generate_ilr).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(frame, text=t("census_ilr.validate", "Validate Return"), command=self._validate_return).grid(row=2, column=0, padx=5, pady=5)
        ttk.Button(frame, text=t("census_ilr.submit", "Submit Return"), command=self._submit_return).grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(frame, text=t("census_ilr.stats", "View Stats"), command=self._view_stats).grid(row=3, column=0, columnspan=2, pady=5)

        self._gen_output = tk.Text(tab, height=15, wrap="word")
        self._gen_output.pack(fill="both", expand=True, padx=20, pady=10)

    def _get_gen_return_id(self):
        val = self._gen_return_id.get().strip()
        if not val or not val.isdigit():
            messagebox.showwarning(t("census_ilr.warning", "Warning"), t("census_ilr.enter_id", "Enter a valid Return ID."))
            return None
        return int(val)

    def _generate_census(self):
        rid = self._get_gen_return_id()
        if rid is None:
            return
        try:
            count = self._svc.generate_census_data(rid)
            self._gen_output.delete("1.0", "end")
            self._gen_output.insert("end", f"Generated {count} census student records.\n")
        except Exception as exc:
            messagebox.showerror(t("census_ilr.error", "Error"), str(exc))

    def _generate_ilr(self):
        rid = self._get_gen_return_id()
        if rid is None:
            return
        try:
            count = self._svc.generate_ilr_data(rid)
            self._gen_output.delete("1.0", "end")
            self._gen_output.insert("end", f"Generated {count} ILR learning aim records.\n")
        except Exception as exc:
            messagebox.showerror(t("census_ilr.error", "Error"), str(exc))

    def _validate_return(self):
        rid = self._get_gen_return_id()
        if rid is None:
            return
        try:
            errors = self._svc.validate_return(rid)
            self._gen_output.delete("1.0", "end")
            if errors:
                self._gen_output.insert("end", f"Validation found {len(errors)} error(s):\n\n")
                for e in errors:
                    self._gen_output.insert("end", f"  - {e}\n")
            else:
                self._gen_output.insert("end", "Validation passed - no errors found.\n")
        except Exception as exc:
            messagebox.showerror(t("census_ilr.error", "Error"), str(exc))

    def _submit_return(self):
        rid = self._get_gen_return_id()
        if rid is None:
            return
        try:
            user_id = self._auth.get("user_id", 0) if self._auth else 0
            self._svc.submit_return(rid, user_id)
            self._gen_output.delete("1.0", "end")
            self._gen_output.insert("end", f"Return {rid} submitted successfully.\n")
            self._load_returns()
        except Exception as exc:
            messagebox.showerror(t("census_ilr.error", "Error"), str(exc))

    def _view_stats(self):
        rid = self._get_gen_return_id()
        if rid is None:
            return
        try:
            stats = self._svc.get_return_stats(rid)
            self._gen_output.delete("1.0", "end")
            self._gen_output.insert("end", f"Return Stats for ID {rid}:\n")
            for k, v in stats.items():
                self._gen_output.insert("end", f"  {k}: {v}\n")
        except Exception as exc:
            messagebox.showerror(t("census_ilr.error", "Error"), str(exc))

    # ── Export Tab ──

    def _build_export_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("census_ilr.export", "Export"))

        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=10, pady=10)

        tk.Label(toolbar, text=t("census_ilr.return_id", "Return ID:"), bg="#ecf0f1").pack(side="left", padx=5)
        self._export_return_id = ttk.Entry(toolbar, width=10)
        self._export_return_id.pack(side="left", padx=5)

        ttk.Button(toolbar, text=t("census_ilr.export_census_xml", "Export Census XML"), command=self._export_census).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("census_ilr.export_ilr_xml", "Export ILR XML"), command=self._export_ilr).pack(side="left", padx=5)

        self._export_output = tk.Text(tab, height=20, wrap="word")
        self._export_output.pack(fill="both", expand=True, padx=10, pady=5)

    def _export_census(self):
        val = self._export_return_id.get().strip()
        if not val or not val.isdigit():
            messagebox.showwarning(t("census_ilr.warning", "Warning"), t("census_ilr.enter_id", "Enter a valid Return ID."))
            return
        try:
            xml = self._svc.export_census_xml(int(val))
            self._export_output.delete("1.0", "end")
            self._export_output.insert("end", xml)
        except Exception as exc:
            messagebox.showerror(t("census_ilr.error", "Error"), str(exc))

    def _export_ilr(self):
        val = self._export_return_id.get().strip()
        if not val or not val.isdigit():
            messagebox.showwarning(t("census_ilr.warning", "Warning"), t("census_ilr.enter_id", "Enter a valid Return ID."))
            return
        try:
            xml = self._svc.export_ilr_xml(int(val))
            self._export_output.delete("1.0", "end")
            self._export_output.insert("end", xml)
        except Exception as exc:
            messagebox.showerror(t("census_ilr.error", "Error"), str(exc))

    def refresh(self):
        """Reload data in all tabs."""
        self._load_returns()
