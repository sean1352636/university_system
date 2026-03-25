"""GUI for sms & email management."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.sms_email.services.sms_email_service import SmsEmailService
from education_system.college_system.core.exceptions import SmsEmailError
from education_system.college_system.core.i18n import t


class _PreferenceDialog(tk.Toplevel):
    """Modal dialog for adding or editing a preference."""

    def __init__(self, parent, title="Preference", item=None):
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

        tk.Label(container, text=t("common.user_id"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("user_id", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=0, column=1, sticky="ew", **pad)
        self._vars["user_id"] = var
        tk.Label(container, text=t("sms_email.phone"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("phone_number", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=1, column=1, sticky="ew", **pad)
        self._vars["phone_number"] = var
        tk.Label(container, text=t("sms_email.digest"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=2, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("digest_frequency", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=2, column=1, sticky="ew", **pad)
        self._vars["digest_frequency"] = var

        btn_frame = tk.Frame(container)
        btn_frame.grid(row=99, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn_frame, text=t("common.save"), command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=t("common.cancel"), command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        self.destroy()


class SmsEmailFrame(tk.Frame):
    """SMS & Email management screen."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = SmsEmailService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("sms_email.management"),
                 font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        toolbar = tk.Frame(self, bg="#ecf0f1", pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text=t("sms_email.add"), command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.edit"), command=self._on_edit).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.delete"), command=self._on_delete).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_items).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Export CSV", command=self._export_csv).pack(side="left", padx=4)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        columns = ('user_id', 'email_enabled', 'sms_enabled', 'phone_number', 'attendance_alerts', 'grade_alerts')
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        self._tree.heading("user_id", text=t("common.user_id"))
        self._tree.column("user_id", width=80, anchor="center")
        self._tree.heading("email_enabled", text=t("sms_email.email"))
        self._tree.column("email_enabled", width=50, anchor="center")
        self._tree.heading("sms_enabled", text=t("sms_email.sms"))
        self._tree.column("sms_enabled", width=50, anchor="center")
        self._tree.heading("phone_number", text=t("sms_email.phone"))
        self._tree.column("phone_number", width=120, anchor="center")
        self._tree.heading("attendance_alerts", text=t("sms_email.attendance"))
        self._tree.column("attendance_alerts", width=60, anchor="center")
        self._tree.heading("grade_alerts", text=t("sms_email.grades"))
        self._tree.column("grade_alerts", width=60, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._status_var = tk.StringVar(value=t("common.ready"))
        tk.Label(self, textvariable=self._status_var, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._tree, "sms_email_export.csv")

    def refresh(self):
        self._load_items()

    def _load_items(self):
        self._tree.delete(*self._tree.get_children())
        try:
            items = self._svc.list_preferences()
            for item in items:
                self._tree.insert("", "end", iid=item["id"], values=(
                    item.get("user_id", ""), item.get("email_enabled", ""), item.get("sms_enabled", ""), item.get("phone_number", ""), item.get("attendance_alerts", ""), item.get("grade_alerts", ""),
                ))
            self._status_var.set(t("sms_email.count_loaded", count=len(items)))
        except Exception as exc:
            messagebox.showerror(t("common.error"), f"{t('common.failed_to_load')}\n{exc}")

    def _selected_pk(self) -> int | None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection"), t("common.select_item_first"))
            return None
        return int(sel[0])

    def _on_add(self):
        dlg = _PreferenceDialog(self, title="Add Preference")
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.create_preference(**dlg.result)
            messagebox.showinfo(t("common.success"), t("sms_email.created"))
            self._load_items()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _on_edit(self):
        pk = self._selected_pk()
        if pk is None:
            return
        item = self._svc.get_preference(pk)
        if not item:
            messagebox.showerror(t("common.error"), t("sms_email.not_found"))
            return
        dlg = _PreferenceDialog(self, title="Edit Preference", item=item)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.update_preference(pk, **dlg.result)
            messagebox.showinfo(t("common.success"), t("sms_email.updated"))
            self._load_items()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _on_delete(self):
        pk = self._selected_pk()
        if pk is None:
            return
        if not messagebox.askyesno(t("common.confirm"), t("sms_email.delete_confirm")):
            return
        try:
            self._svc.delete_preference(pk)
            messagebox.showinfo(t("common.success"), t("sms_email.deleted"))
            self._load_items()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))
