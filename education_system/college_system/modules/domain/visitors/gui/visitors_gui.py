"""GUI for visitor management management."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.visitors.services.visitors_service import VisitorService
from education_system.college_system.core.exceptions import VisitorError


class _VisitorDialog(tk.Toplevel):
    """Modal dialog for adding or editing a visitor."""

    def __init__(self, parent, title="Visitor", item=None):
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

        tk.Label(container, text="First Name", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("first_name", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=0, column=1, sticky="ew", **pad)
        self._vars["first_name"] = var
        tk.Label(container, text="Last Name", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("last_name", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=1, column=1, sticky="ew", **pad)
        self._vars["last_name"] = var
        tk.Label(container, text="Organisation", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=2, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("organization", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=2, column=1, sticky="ew", **pad)
        self._vars["organization"] = var
        tk.Label(container, text="Purpose", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=3, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("purpose", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=3, column=1, sticky="ew", **pad)
        self._vars["purpose"] = var
        tk.Label(container, text="Badge", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=4, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("badge_number", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=4, column=1, sticky="ew", **pad)
        self._vars["badge_number"] = var
        tk.Label(container, text="Sign In", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=5, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("sign_in_time", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=5, column=1, sticky="ew", **pad)
        self._vars["sign_in_time"] = var

        btn_frame = tk.Frame(container)
        btn_frame.grid(row=99, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        self.destroy()


class VisitorFrame(tk.Frame):
    """Visitor Management management screen."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = VisitorService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Visitor Management",
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

        columns = ('first_name', 'last_name', 'organization', 'purpose', 'visiting_staff_id', 'dbs_checked')
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        self._tree.heading("first_name", text="First Name")
        self._tree.column("first_name", width=100, anchor="center")
        self._tree.heading("last_name", text="Last Name")
        self._tree.column("last_name", width=100, anchor="center")
        self._tree.heading("organization", text="Organisation")
        self._tree.column("organization", width=150, anchor="center")
        self._tree.heading("purpose", text="Purpose")
        self._tree.column("purpose", width=200, anchor="center")
        self._tree.heading("visiting_staff_id", text="Visiting")
        self._tree.column("visiting_staff_id", width=80, anchor="center")
        self._tree.heading("dbs_checked", text="DBS")
        self._tree.column("dbs_checked", width=50, anchor="center")

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
            items = self._svc.list_visitors()
            for item in items:
                self._tree.insert("", "end", iid=item["id"], values=(
                    item.get("first_name", ""), item.get("last_name", ""), item.get("organization", ""), item.get("purpose", ""), item.get("visiting_staff_id", ""), item.get("dbs_checked", ""),
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
        dlg = _VisitorDialog(self, title="Add Visitor")
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.create_visitor(**dlg.result)
            messagebox.showinfo("Success", "Visitor created.")
            self._load_items()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_edit(self):
        pk = self._selected_pk()
        if pk is None:
            return
        item = self._svc.get_visitor(pk)
        if not item:
            messagebox.showerror("Error", "Visitor not found.")
            return
        dlg = _VisitorDialog(self, title="Edit Visitor", item=item)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.update_visitor(pk, **dlg.result)
            messagebox.showinfo("Success", "Visitor updated.")
            self._load_items()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_delete(self):
        pk = self._selected_pk()
        if pk is None:
            return
        if not messagebox.askyesno("Confirm", "Delete this visitor?"):
            return
        try:
            self._svc.delete_visitor(pk)
            messagebox.showinfo("Success", "Visitor deleted.")
            self._load_items()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
