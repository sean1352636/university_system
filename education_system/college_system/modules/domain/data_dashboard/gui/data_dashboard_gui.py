"""GUI for data dashboard management."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.data_dashboard.services.data_dashboard_service import DataDashboardService
from education_system.college_system.core.exceptions import DataDashboardError
from education_system.college_system.core.i18n import t


class _WidgetDialog(tk.Toplevel):
    """Modal dialog for adding or editing a widget."""

    def __init__(self, parent, title="Widget", item=None):
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
        tk.Label(container, text="Type", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("widget_type", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=1, column=1, sticky="ew", **pad)
        self._vars["widget_type"] = var
        tk.Label(container, text="Config", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=2, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("config", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=2, column=1, sticky="ew", **pad)
        self._vars["config"] = var

        btn_frame = tk.Frame(container)
        btn_frame.grid(row=99, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn_frame, text=t("common.save"), command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=t("common.cancel"), command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        self.destroy()


class DataDashboardFrame(tk.Frame):
    """Data Dashboard management screen."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = DataDashboardService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("data_dashboard.management"),
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

        columns = ('user_id', 'widget_type', 'config', 'display_order', 'is_visible')
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        self._tree.heading("user_id", text="User ID")
        self._tree.column("user_id", width=80, anchor="center")
        self._tree.heading("widget_type", text="Type")
        self._tree.column("widget_type", width=120, anchor="center")
        self._tree.heading("config", text="Config")
        self._tree.column("config", width=200, anchor="center")
        self._tree.heading("display_order", text="Order")
        self._tree.column("display_order", width=60, anchor="center")
        self._tree.heading("is_visible", text="Visible")
        self._tree.column("is_visible", width=60, anchor="center")

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
            items = self._svc.list_widgets()
            for item in items:
                self._tree.insert("", "end", iid=item["id"], values=(
                    item.get("user_id", ""), item.get("widget_type", ""), item.get("config", ""), item.get("display_order", ""), item.get("is_visible", ""),
                ))
            self._status_var.set(t("common.count_loaded", count=len(items)))
        except Exception as exc:
            messagebox.showerror(t("common.error"), f"Failed to load:\n{exc}")

    def _selected_pk(self) -> int | None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"))
            return None
        return int(sel[0])

    def _on_add(self):
        dlg = _WidgetDialog(self, title="Add Widget")
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.create_widget(**dlg.result)
            messagebox.showinfo(t("common.success"), t("data_dashboard.widget_created", default="Widget created."))
            self._load_items()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _on_edit(self):
        pk = self._selected_pk()
        if pk is None:
            return
        item = self._svc.get_widget(pk)
        if not item:
            messagebox.showerror(t("common.error"), t("data_dashboard.widget_not_found", default="Widget not found."))
            return
        dlg = _WidgetDialog(self, title="Edit Widget", item=item)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.update_widget(pk, **dlg.result)
            messagebox.showinfo(t("common.success"), t("data_dashboard.widget_updated", default="Widget updated."))
            self._load_items()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _on_delete(self):
        pk = self._selected_pk()
        if pk is None:
            return
        if not messagebox.askyesno(t("common.confirm"), t("data_dashboard.delete_widget_confirm", default="Delete this widget?")):
            return
        try:
            self._svc.delete_widget(pk)
            messagebox.showinfo(t("common.success"), t("data_dashboard.widget_deleted", default="Widget deleted."))
            self._load_items()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._tree, "data_dashboard_export.csv")
