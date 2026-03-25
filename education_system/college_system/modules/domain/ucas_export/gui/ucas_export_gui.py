"""UCAS Export GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.college_system.modules.domain.ucas_export.services.ucas_export_service import (
    UCASExportService,
)
from education_system.college_system.core.i18n import t


class UCASExportFrame(tk.Frame):
    """GUI for UCAS data export."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = UCASExportService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text=t("ucas_export.title", "UCAS Data Export"),
            font=("Helvetica", 15, "bold"),
            bg="#2c3e50",
            fg="white",
        ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_batches_tab()
        self._build_generate_tab()
        self._build_xml_tab()

    # ── Export Batches Tab ──

    def _build_batches_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("ucas_export.batches", "Export Batches"))

        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text=t("ucas_export.year", "Academic Year:"), bg="#ecf0f1").pack(side="left", padx=2)
        self._batch_year = ttk.Entry(toolbar, width=12)
        self._batch_year.pack(side="left", padx=2)

        ttk.Button(toolbar, text=t("ucas_export.search", "Search"), command=self._load_batches).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("ucas_export.new", "New Batch"), command=self._new_batch_dialog).pack(side="left", padx=5)

        cols = ("id", "academic_year", "export_type", "record_count", "status", "export_date")
        self._batches_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self._batches_tree.heading(c, text=c.replace("_", " ").title())
            self._batches_tree.column(c, width=120)
        self._batches_tree.pack(fill="both", expand=True, padx=5, pady=5)

        sb = ttk.Scrollbar(tab, orient="vertical", command=self._batches_tree.yview)
        self._batches_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

    def _load_batches(self):
        for row in self._batches_tree.get_children():
            self._batches_tree.delete(row)
        try:
            yr = self._batch_year.get().strip() or None
            batches = self._svc.list_batches(academic_year=yr)
            for b in batches:
                self._batches_tree.insert("", "end", values=(
                    b["id"], b["academic_year"], b["export_type"],
                    b.get("record_count", 0), b["status"], b.get("export_date", ""),
                ))
        except Exception as exc:
            messagebox.showerror(t("ucas_export.error", "Error"), str(exc))

    def _new_batch_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("ucas_export.new_batch", "New Export Batch"))
        dlg.geometry("350x180")
        dlg.transient(self)

        tk.Label(dlg, text="Academic Year:").grid(row=0, column=0, padx=10, pady=8, sticky="e")
        year_entry = ttk.Entry(dlg, width=20)
        year_entry.grid(row=0, column=1, padx=10, pady=8)

        tk.Label(dlg, text="Export Type:").grid(row=1, column=0, padx=10, pady=8, sticky="e")
        type_combo = ttk.Combobox(dlg, values=["applications", "references", "predictions"], state="readonly", width=18)
        type_combo.set("applications")
        type_combo.grid(row=1, column=1, padx=10, pady=8)

        def _save():
            try:
                self._svc.create_batch(year_entry.get().strip(), type_combo.get())
                dlg.destroy()
                self._load_batches()
                messagebox.showinfo(t("ucas_export.success", "Success"), t("ucas_export.batch_created", "Batch created."))
            except Exception as exc:
                messagebox.showerror(t("ucas_export.error", "Error"), str(exc))

        ttk.Button(dlg, text=t("ucas_export.save", "Save"), command=_save).grid(row=2, column=0, columnspan=2, pady=15)

    # ── Generate Data Tab ──

    def _build_generate_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("ucas_export.generate", "Generate Data"))

        frame = tk.Frame(tab, bg="#ecf0f1")
        frame.pack(padx=20, pady=20, fill="x")

        tk.Label(frame, text=t("ucas_export.batch_id", "Batch ID:"), bg="#ecf0f1").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self._gen_batch_id = ttk.Entry(frame, width=10)
        self._gen_batch_id.grid(row=0, column=1, padx=5, pady=5)

        ttk.Button(frame, text=t("ucas_export.generate_data", "Generate Export Data"), command=self._generate_data).grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(frame, text=t("ucas_export.validate", "Validate Batch"), command=self._validate_batch).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(frame, text=t("ucas_export.mark_exported", "Mark Exported"), command=self._mark_exported).grid(row=2, column=0, padx=5, pady=5)
        ttk.Button(frame, text=t("ucas_export.view_stats", "View Stats"), command=self._view_stats).grid(row=2, column=1, padx=5, pady=5)

        self._gen_output = tk.Text(tab, height=15, wrap="word")
        self._gen_output.pack(fill="both", expand=True, padx=20, pady=10)

    def _get_batch_id(self):
        val = self._gen_batch_id.get().strip()
        if not val or not val.isdigit():
            messagebox.showwarning(t("ucas_export.warning", "Warning"), t("ucas_export.enter_id", "Enter a valid Batch ID."))
            return None
        return int(val)

    def _generate_data(self):
        bid = self._get_batch_id()
        if bid is None:
            return
        try:
            count = self._svc.generate_export_data(bid)
            self._gen_output.delete("1.0", "end")
            self._gen_output.insert("end", f"Generated {count} export records.\n")
        except Exception as exc:
            messagebox.showerror(t("ucas_export.error", "Error"), str(exc))

    def _validate_batch(self):
        bid = self._get_batch_id()
        if bid is None:
            return
        try:
            errors = self._svc.validate_batch(bid)
            self._gen_output.delete("1.0", "end")
            if errors:
                self._gen_output.insert("end", f"Validation found {len(errors)} error(s):\n\n")
                for e in errors:
                    self._gen_output.insert("end", f"  - {e}\n")
            else:
                self._gen_output.insert("end", "Validation passed - all records included.\n")
        except Exception as exc:
            messagebox.showerror(t("ucas_export.error", "Error"), str(exc))

    def _mark_exported(self):
        bid = self._get_batch_id()
        if bid is None:
            return
        try:
            user_id = self._auth.get("user_id", 0) if self._auth else 0
            self._svc.mark_exported(bid, user_id)
            self._gen_output.delete("1.0", "end")
            self._gen_output.insert("end", f"Batch {bid} marked as exported.\n")
            self._load_batches()
        except Exception as exc:
            messagebox.showerror(t("ucas_export.error", "Error"), str(exc))

    def _view_stats(self):
        bid = self._get_batch_id()
        if bid is None:
            return
        try:
            stats = self._svc.get_batch_stats(bid)
            self._gen_output.delete("1.0", "end")
            self._gen_output.insert("end", f"Batch Stats for ID {bid}:\n")
            for k, v in stats.items():
                self._gen_output.insert("end", f"  {k}: {v}\n")
        except Exception as exc:
            messagebox.showerror(t("ucas_export.error", "Error"), str(exc))

    # ── XML Preview Tab ──

    def _build_xml_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("ucas_export.xml_preview", "XML Preview"))

        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=10, pady=10)

        tk.Label(toolbar, text=t("ucas_export.batch_id", "Batch ID:"), bg="#ecf0f1").pack(side="left", padx=5)
        self._xml_batch_id = ttk.Entry(toolbar, width=10)
        self._xml_batch_id.pack(side="left", padx=5)

        ttk.Button(toolbar, text=t("ucas_export.generate_xml", "Generate XML"), command=self._preview_xml).pack(side="left", padx=5)

        self._xml_output = tk.Text(tab, height=20, wrap="word")
        self._xml_output.pack(fill="both", expand=True, padx=10, pady=5)

    def _preview_xml(self):
        val = self._xml_batch_id.get().strip()
        if not val or not val.isdigit():
            messagebox.showwarning(t("ucas_export.warning", "Warning"), t("ucas_export.enter_id", "Enter a valid Batch ID."))
            return
        try:
            xml = self._svc.generate_xml(int(val))
            self._xml_output.delete("1.0", "end")
            self._xml_output.insert("end", xml)
        except Exception as exc:
            messagebox.showerror(t("ucas_export.error", "Error"), str(exc))

    def refresh(self):
        """Reload data in all tabs."""
        self._load_batches()
