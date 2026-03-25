"""GUI for print credits management."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.print_credits.services.print_credits_service import PrintCreditService
from education_system.college_system.core.exceptions import PrintCreditError
from education_system.college_system.core.i18n import t


class _AccountDialog(tk.Toplevel):
    """Modal dialog for adding or editing a account."""

    def __init__(self, parent, title="Account", item=None):
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

        tk.Label(container, text=t("common.student_id"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("student_id", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=0, column=1, sticky="ew", **pad)
        self._vars["student_id"] = var
        tk.Label(container, text=t("print_credits.balance"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("balance", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=1, column=1, sticky="ew", **pad)
        self._vars["balance"] = var
        tk.Label(container, text=t("print_credits.reset_date"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=2, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("quota_reset_date", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=2, column=1, sticky="ew", **pad)
        self._vars["quota_reset_date"] = var

        btn_frame = tk.Frame(container)
        btn_frame.grid(row=99, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn_frame, text=t("common.save"), command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=t("common.cancel"), command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        self.destroy()


class PrintCreditFrame(tk.Frame):
    """Print Credits management screen."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = PrintCreditService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("print_credits.management"),
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

        columns = ('student_id', 'balance', 'quota_remaining', 'quota_reset_date')
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        self._tree.heading("student_id", text=t("common.student_id"))
        self._tree.column("student_id", width=80, anchor="center")
        self._tree.heading("balance", text=t("print_credits.balance"))
        self._tree.column("balance", width=80, anchor="center")
        self._tree.heading("quota_remaining", text=t("print_credits.quota"))
        self._tree.column("quota_remaining", width=60, anchor="center")
        self._tree.heading("quota_reset_date", text=t("print_credits.reset_date"))
        self._tree.column("quota_reset_date", width=100, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._status_var = tk.StringVar(value=t("common.ready"))
        tk.Label(self, textvariable=self._status_var, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._tree, "print_credits_export.csv")

    def refresh(self):
        self._load_items()

    def _load_items(self):
        self._tree.delete(*self._tree.get_children())
        try:
            items = self._svc.list_accounts()
            for item in items:
                self._tree.insert("", "end", iid=item["id"], values=(
                    item.get("student_id", ""), item.get("balance", ""), item.get("quota_remaining", ""), item.get("quota_reset_date", ""),
                ))
            self._status_var.set(t("common.count_loaded", count=len(items)))
        except Exception as exc:
            messagebox.showerror(t("common.error"), f"Failed to load:\n{exc}")

    def _selected_pk(self) -> int | None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection"), t("common.select_item_first"))
            return None
        return int(sel[0])

    def _on_add(self):
        dlg = _AccountDialog(self, title=t("print_credits.add_account"))
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.create_account(**dlg.result)
            messagebox.showinfo(t("common.success"), t("print_credits.account_created"))
            self._load_items()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _on_edit(self):
        pk = self._selected_pk()
        if pk is None:
            return
        item = self._svc.get_account(pk)
        if not item:
            messagebox.showerror(t("common.error"), t("print_credits.account_not_found"))
            return
        dlg = _AccountDialog(self, title=t("print_credits.edit_account"), item=item)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.update_account(pk, **dlg.result)
            messagebox.showinfo(t("common.success"), t("print_credits.account_updated"))
            self._load_items()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _on_delete(self):
        pk = self._selected_pk()
        if pk is None:
            return
        if not messagebox.askyesno(t("common.confirm"), t("print_credits.delete_account_confirm")):
            return
        try:
            self._svc.delete_account(pk)
            messagebox.showinfo(t("common.success"), t("print_credits.account_deleted"))
            self._load_items()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))
