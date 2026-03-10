"""GUI for staff appraisals management."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.appraisals.services.appraisals_service import AppraisalService
from education_system.college_system.core.exceptions import AppraisalError


class _AppraisalDialog(tk.Toplevel):
    """Modal dialog for adding or editing a appraisal."""

    def __init__(self, parent, title="Appraisal", item=None):
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

        tk.Label(container, text="Staff ID", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("staff_id", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=0, column=1, sticky="ew", **pad)
        self._vars["staff_id"] = var
        tk.Label(container, text="Year", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("academic_year", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=1, column=1, sticky="ew", **pad)
        self._vars["academic_year"] = var
        tk.Label(container, text="Type", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=2, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("appraisal_type", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=2, column=1, sticky="ew", **pad)
        self._vars["appraisal_type"] = var
        tk.Label(container, text="Rating", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=3, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("overall_rating", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=3, column=1, sticky="ew", **pad)
        self._vars["overall_rating"] = var
        tk.Label(container, text="Status", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=4, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("status", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=4, column=1, sticky="ew", **pad)
        self._vars["status"] = var

        btn_frame = tk.Frame(container)
        btn_frame.grid(row=99, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        self.destroy()


class AppraisalFrame(tk.Frame):
    """Staff Appraisals management screen."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = AppraisalService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Staff Appraisals",
                 font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        toolbar = tk.Frame(self, bg="#ecf0f1", pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Add", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Edit", command=self._on_edit).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Refresh", command=self._load_items).pack(side="left", padx=4)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        columns = ('staff_id', 'appraiser_id', 'academic_year', 'appraisal_type', 'overall_rating', 'status')
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        self._tree.heading("staff_id", text="Staff ID")
        self._tree.column("staff_id", width=80, anchor="center")
        self._tree.heading("appraiser_id", text="Appraiser ID")
        self._tree.column("appraiser_id", width=80, anchor="center")
        self._tree.heading("academic_year", text="Year")
        self._tree.column("academic_year", width=100, anchor="center")
        self._tree.heading("appraisal_type", text="Type")
        self._tree.column("appraisal_type", width=100, anchor="center")
        self._tree.heading("overall_rating", text="Rating")
        self._tree.column("overall_rating", width=60, anchor="center")
        self._tree.heading("status", text="Status")
        self._tree.column("status", width=80, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load_items()

    def _load_items(self):
        self._tree.delete(*self._tree.get_children())
        try:
            items = self._svc.list_appraisals()
            for item in items:
                self._tree.insert("", "end", iid=item["id"], values=(
                    item.get("staff_id", ""), item.get("appraiser_id", ""), item.get("academic_year", ""), item.get("appraisal_type", ""), item.get("overall_rating", ""), item.get("status", ""),
                ))
            self._status_var.set(f"{len(items)} item(s) loaded")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load:\n{exc}")

    def _selected_pk(self) -> int | None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select an item first.")
            return None
        return int(sel[0])

    def _on_add(self):
        dlg = _AppraisalDialog(self, title="Add Appraisal")
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.create_appraisal(**dlg.result)
            messagebox.showinfo("Success", "Appraisal created.")
            self._load_items()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_edit(self):
        pk = self._selected_pk()
        if pk is None:
            return
        item = self._svc.get_appraisal(pk)
        if not item:
            messagebox.showerror("Error", "Appraisal not found.")
            return
        dlg = _AppraisalDialog(self, title="Edit Appraisal", item=item)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.update_appraisal(pk, **dlg.result)
            messagebox.showinfo("Success", "Appraisal updated.")
            self._load_items()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_delete(self):
        pk = self._selected_pk()
        if pk is None:
            return
        if not messagebox.askyesno("Confirm", "Delete this appraisal?"):
            return
        try:
            self._svc.delete_appraisal(pk)
            messagebox.showinfo("Success", "Appraisal deleted.")
            self._load_items()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
