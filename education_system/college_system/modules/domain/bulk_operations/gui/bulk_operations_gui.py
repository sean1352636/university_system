"""GUI for bulk operations management."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.bulk_operations.services.bulk_operations_service import BulkOperationService
from education_system.college_system.core.exceptions import BulkOperationError
from education_system.college_system.core.i18n import t


class _JobDialog(tk.Toplevel):
    """Modal dialog for adding or editing a job."""

    def __init__(self, parent, title="Job", item=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.result: dict | None = None
        self._item = item
        self._build_ui()
        self._center(parent)

    def _center(self, parent):
        self.update_idletasks()
        pw = parent.winfo_rootx() + parent.winfo_width() // 2
        ph = parent.winfo_rooty() + parent.winfo_height() // 2
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{pw - w // 2}+{ph - h // 2}")

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}
        container = tk.Frame(self, padx=20, pady=15)
        container.pack(fill="both", expand=True)
        self._vars: dict[str, tk.StringVar] = {}

        tk.Label(container, text=t("common.type"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("job_type", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=0, column=1, sticky="ew", **pad)
        self._vars["job_type"] = var
        tk.Label(container, text=t("bulk_operations.file_format", default="File"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("file_path", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=1, column=1, sticky="ew", **pad)
        self._vars["file_path"] = var
        tk.Label(container, text=t("bulk_operations.error_log", default="Error Log"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=2, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("error_log", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=2, column=1, sticky="ew", **pad)
        self._vars["error_log"] = var
        tk.Label(container, text=t("common.status"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=3, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("status", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=3, column=1, sticky="ew", **pad)
        self._vars["status"] = var

        btn_frame = tk.Frame(container)
        btn_frame.grid(row=99, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn_frame, text=t("common.save"), command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=t("common.cancel"), command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        self.destroy()


class BulkOperationFrame(tk.Frame):
    """Bulk Operations management screen."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = BulkOperationService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("bulk_operations.management"),
                 font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        toolbar = tk.Frame(self, bg="#ecf0f1", pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text=t("common.add"), command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.edit"), command=self._on_edit).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.delete"), command=self._on_delete).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_items).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Export CSV", command=self._export_csv).pack(side="left", padx=4)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        columns = ('job_type', 'initiated_by', 'file_path', 'total_rows', 'processed_rows', 'success_count')
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        self._tree.heading("job_type", text=t("common.type"))
        self._tree.column("job_type", width=120, anchor="center")
        self._tree.heading("initiated_by", text=t("bulk_operations.initiated_by", default="By"))
        self._tree.column("initiated_by", width=80, anchor="center")
        self._tree.heading("file_path", text=t("bulk_operations.file_format", default="File"))
        self._tree.column("file_path", width=200, anchor="center")
        self._tree.heading("total_rows", text=t("common.total"))
        self._tree.column("total_rows", width=60, anchor="center")
        self._tree.heading("processed_rows", text=t("bulk_operations.processed", default="Processed"))
        self._tree.column("processed_rows", width=70, anchor="center")
        self._tree.heading("success_count", text=t("common.success"))
        self._tree.column("success_count", width=60, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._status_var = tk.StringVar(value=t("common.ready"))
        tk.Label(self, textvariable=self._status_var, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load_items()

    def _load_items(self):
        self._tree.delete(*self._tree.get_children())
        try:
            items = self._svc.list_jobs()
            for item in items:
                self._tree.insert("", "end", iid=item["id"], values=(
                    item.get("job_type", ""), item.get("initiated_by", ""), item.get("file_path", ""), item.get("total_rows", ""), item.get("processed_rows", ""), item.get("success_count", ""),
                ))
            self._status_var.set(t("common.count_loaded", count=len(items)))
        except Exception as exc:
            messagebox.showerror(t("common.error"), f"{t('common.failed_to_load')}\n{exc}")

    def _selected_pk(self) -> int | None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"))
            return None
        return int(sel[0])

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._tree, "bulk_operations.csv")

    def _on_add(self):
        dlg = _JobDialog(self, title=t("bulk_operations.add_job", default="Add Job"))
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.create_job(**dlg.result)
            messagebox.showinfo(t("common.success"), t("bulk_operations.job_created", default="Job created."))
            self._load_items()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _on_edit(self):
        pk = self._selected_pk()
        if pk is None:
            return
        item = self._svc.get_job(pk)
        if not item:
            messagebox.showerror(t("common.error"), t("bulk_operations.job_not_found", default="Job not found."))
            return
        dlg = _JobDialog(self, title=t("bulk_operations.edit_job", default="Edit Job"), item=item)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.update_job(pk, **dlg.result)
            messagebox.showinfo(t("common.success"), t("bulk_operations.job_updated", default="Job updated."))
            self._load_items()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _on_delete(self):
        pk = self._selected_pk()
        if pk is None:
            return
        if not messagebox.askyesno(t("common.confirm"), t("bulk_operations.delete_job_confirm", default="Delete this job?")):
            return
        try:
            self._svc.delete_job(pk)
            messagebox.showinfo(t("common.success"), t("bulk_operations.job_deleted", default="Job deleted."))
            self._load_items()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))
