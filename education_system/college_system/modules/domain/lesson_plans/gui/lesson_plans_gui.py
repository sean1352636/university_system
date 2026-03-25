"""GUI for lesson plans management."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.lesson_plans.services.lesson_plans_service import LessonPlanService
from education_system.college_system.core.exceptions import LessonPlanError
from education_system.college_system.core.i18n import t


class _PlanDialog(tk.Toplevel):
    """Modal dialog for adding or editing a plan."""

    def __init__(self, parent, title="Plan", item=None):
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

        tk.Label(container, text="Course ID", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("course_id", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=0, column=1, sticky="ew", **pad)
        self._vars["course_id"] = var
        tk.Label(container, text="Teacher ID", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("teacher_id", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=1, column=1, sticky="ew", **pad)
        self._vars["teacher_id"] = var
        tk.Label(container, text="Date", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=2, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("lesson_date", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=2, column=1, sticky="ew", **pad)
        self._vars["lesson_date"] = var
        tk.Label(container, text="Topic", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=3, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("topic", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=3, column=1, sticky="ew", **pad)
        self._vars["topic"] = var
        tk.Label(container, text="Objectives", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=4, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("learning_objectives", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=4, column=1, sticky="ew", **pad)
        self._vars["learning_objectives"] = var
        tk.Label(container, text="Starter", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=5, column=0, sticky="w", **pad)
        var = tk.StringVar(value=self._item.get("starter_activity", "") if self._item else "")
        ttk.Entry(container, textvariable=var, width=36).grid(row=5, column=1, sticky="ew", **pad)
        self._vars["starter_activity"] = var

        btn_frame = tk.Frame(container)
        btn_frame.grid(row=99, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn_frame, text=t("common.save"), command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=t("common.cancel"), command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        self.destroy()


class LessonPlanFrame(tk.Frame):
    """Lesson Plans management screen."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = LessonPlanService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("lesson_plans.management"),
                 font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        toolbar = tk.Frame(self, bg="#ecf0f1", pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text=t("lesson_plans.add"), command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.edit"), command=self._on_edit).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.delete"), command=self._on_delete).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_items).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.export_csv", default="Export CSV"), command=self._export_csv).pack(side="right", padx=4)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        columns = ('course_id', 'teacher_id', 'lesson_date', 'topic', 'learning_objectives', 'starter_activity')
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        self._tree.heading("course_id", text="Course ID")
        self._tree.column("course_id", width=80, anchor="center")
        self._tree.heading("teacher_id", text="Teacher ID")
        self._tree.column("teacher_id", width=80, anchor="center")
        self._tree.heading("lesson_date", text="Date")
        self._tree.column("lesson_date", width=100, anchor="center")
        self._tree.heading("topic", text="Topic")
        self._tree.column("topic", width=200, anchor="center")
        self._tree.heading("learning_objectives", text="Objectives")
        self._tree.column("learning_objectives", width=200, anchor="center")
        self._tree.heading("starter_activity", text="Starter")
        self._tree.column("starter_activity", width=150, anchor="center")

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
            items = self._svc.list_plans()
            for item in items:
                self._tree.insert("", "end", iid=item["id"], values=(
                    item.get("course_id", ""), item.get("teacher_id", ""), item.get("lesson_date", ""), item.get("topic", ""), item.get("learning_objectives", ""), item.get("starter_activity", ""),
                ))
            self._status_var.set(t("lesson_plans.count_loaded", count=len(items)))
        except Exception as exc:
            messagebox.showerror(t("common.error"), f"Failed to load:\n{exc}")

    def _selected_pk(self) -> int | None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"))
            return None
        return int(sel[0])

    def _on_add(self):
        dlg = _PlanDialog(self, title="Add Plan")
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.create_plan(**dlg.result)
            messagebox.showinfo(t("common.success"), t("common.created_success"))
            self._load_items()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _on_edit(self):
        pk = self._selected_pk()
        if pk is None:
            return
        item = self._svc.get_plan(pk)
        if not item:
            messagebox.showerror(t("common.error"), t("common.no_data"))
            return
        dlg = _PlanDialog(self, title=t("lesson_plans.edit_title"), item=item)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.update_plan(pk, **dlg.result)
            messagebox.showinfo(t("common.success"), t("common.updated_success"))
            self._load_items()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._tree, "lesson_plans.csv")

    def _on_delete(self):
        pk = self._selected_pk()
        if pk is None:
            return
        if not messagebox.askyesno(t("common.confirm"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_plan(pk)
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_items()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))
