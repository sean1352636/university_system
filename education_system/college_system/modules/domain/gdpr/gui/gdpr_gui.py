"""GUI for gdpr & data protection management."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.gdpr.services.gdpr_service import GDPRService
from education_system.college_system.core.exceptions import GDPRError


class _SubjectDialog(tk.Toplevel):
    """Modal dialog for adding or editing a subject."""

    def __init__(self, parent, title="Subject", item=None):
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

        tk.Label(container, text="User ID", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("user_id", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=0, column=1, sticky="ew", **pad)
        self._vars["user_id"] = var
        tk.Label(container, text="Erased At", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("erasure_completed_at", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=1, column=1, sticky="ew", **pad)
        self._vars["erasure_completed_at"] = var

        btn_frame = tk.Frame(container)
        btn_frame.grid(row=99, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        self.destroy()


class GDPRFrame(tk.Frame):
    """GDPR & Data Protection management screen."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = GDPRService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="GDPR & Data Protection",
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

        columns = ('user_id', 'consent_marketing', 'consent_analytics', 'consent_third_party', 'erasure_requested', 'erasure_completed_at')
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        self._tree.heading("user_id", text="User ID")
        self._tree.column("user_id", width=80, anchor="center")
        self._tree.heading("consent_marketing", text="Marketing")
        self._tree.column("consent_marketing", width=70, anchor="center")
        self._tree.heading("consent_analytics", text="Analytics")
        self._tree.column("consent_analytics", width=70, anchor="center")
        self._tree.heading("consent_third_party", text="Third Party")
        self._tree.column("consent_third_party", width=80, anchor="center")
        self._tree.heading("erasure_requested", text="Erasure")
        self._tree.column("erasure_requested", width=60, anchor="center")
        self._tree.heading("erasure_completed_at", text="Erased At")
        self._tree.column("erasure_completed_at", width=100, anchor="center")

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
            items = self._svc.list_subjects()
            for item in items:
                self._tree.insert("", "end", iid=item["id"], values=(
                    item.get("user_id", ""), item.get("consent_marketing", ""), item.get("consent_analytics", ""), item.get("consent_third_party", ""), item.get("erasure_requested", ""), item.get("erasure_completed_at", ""),
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
        dlg = _SubjectDialog(self, title="Add Subject")
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.create_subject(**dlg.result)
            messagebox.showinfo("Success", "Subject created.")
            self._load_items()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_edit(self):
        pk = self._selected_pk()
        if pk is None:
            return
        item = self._svc.get_subject(pk)
        if not item:
            messagebox.showerror("Error", "Subject not found.")
            return
        dlg = _SubjectDialog(self, title="Edit Subject", item=item)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.update_subject(pk, **dlg.result)
            messagebox.showinfo("Success", "Subject updated.")
            self._load_items()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_delete(self):
        pk = self._selected_pk()
        if pk is None:
            return
        if not messagebox.askyesno("Confirm", "Delete this subject?"):
            return
        try:
            self._svc.delete_subject(pk)
            messagebox.showinfo("Success", "Subject deleted.")
            self._load_items()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
