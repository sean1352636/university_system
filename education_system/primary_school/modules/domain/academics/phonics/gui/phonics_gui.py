"""Phonics screening management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.academics.phonics.services.phonics_service import PhonicsService
import traceback


class _PhonicsDialog(tk.Toplevel):
    """Add / Edit phonics screening result dialog."""

    def __init__(self, parent, db_path, record=None):
        super().__init__(parent)
        self.result = None
        self._record = record
        self.title("Edit Phonics Result" if record else "Add Phonics Result")
        self.geometry("450x380")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        frm = tk.Frame(self, padx=15, pady=10)
        frm.pack(fill="both", expand=True)

        self._add_field(frm, "pupil_id", "Pupil ID *")
        self._add_field(frm, "academic_year", "Academic Year *")
        self._add_combo(frm, "year_group", "Year Group *", ["Year 1", "Year 2"])
        self._add_field(frm, "score", "Score *")
        self._add_field(frm, "threshold", "Threshold", default="32")
        self._add_check(frm, "is_resit", "Is Resit")

        # Buttons
        btn_frame = tk.Frame(frm)
        btn_frame.pack(fill="x", pady=10)
        tk.Button(btn_frame, text="Save", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="right", padx=5)

        # Pre-fill for edit
        if record:
            for key, widget in self._entries.items():
                val = record.get(key)
                if val is None:
                    continue
                if isinstance(widget, tk.BooleanVar):
                    widget.set(bool(val))
                elif isinstance(widget, ttk.Combobox):
                    widget.set(str(val))
                else:
                    widget.delete(0, tk.END)
                    widget.insert(0, str(val))

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def _add_field(self, parent, key, label, default=""):
        frm = tk.Frame(parent)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=28, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
        if default:
            entry.insert(0, default)
        self._entries[key] = entry

    def _add_combo(self, parent, key, label, values):
        frm = tk.Frame(parent)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=28, anchor="w").pack(side="left")
        combo = ttk.Combobox(frm, values=values, state="readonly", width=27)
        combo.pack(side="left", fill="x", expand=True)
        if values:
            combo.set(values[0])
        self._entries[key] = combo

    def _add_check(self, parent, key, label, default=False):
        frm = tk.Frame(parent)
        frm.pack(fill="x", padx=10, pady=2)
        var = tk.BooleanVar(value=default)
        tk.Checkbutton(frm, text=label, variable=var).pack(anchor="w")
        self._entries[key] = var

    def _save(self):
        data = {}
        for key, widget in self._entries.items():
            if isinstance(widget, tk.BooleanVar):
                data[key] = int(widget.get())
            elif isinstance(widget, ttk.Combobox):
                data[key] = widget.get()
            else:
                data[key] = widget.get().strip()
        if not data.get("pupil_id"):
            messagebox.showwarning("Validation", "Pupil ID is required.", parent=self)
            return
        if not data.get("academic_year"):
            messagebox.showwarning("Validation", "Academic year is required.", parent=self)
            return
        if not data.get("score"):
            messagebox.showwarning("Validation", "Score is required.", parent=self)
            return
        self.result = data
        self.destroy()


class PhonicsFrame(tk.Frame):
    """Main phonics screening management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = PhonicsService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Phonics Screening Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Result", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(toolbar, text="Academic Year:", bg="#d5dbdb").pack(side="left")
        self._year_filter = ttk.Combobox(toolbar, values=["All"], state="readonly", width=12)
        self._year_filter.set("All")
        self._year_filter.pack(side="left", padx=3)
        self._year_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        tk.Label(toolbar, text="Year Group:", bg="#d5dbdb").pack(side="left", padx=(5, 0))
        self._yg_filter = ttk.Combobox(toolbar, values=["All", "Year 1", "Year 2"],
                                        state="readonly", width=10)
        self._yg_filter.set("All")
        self._yg_filter.pack(side="left", padx=3)
        self._yg_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        # Treeview
        columns = ("pupil_id", "academic_year", "year_group", "score",
                    "threshold", "passed", "is_resit")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=110)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, anchor="w", bg="#ecf0f1",
                 padx=10).pack(fill="x", side="bottom")

        self._load_items()

    def refresh(self):
        self._load_items()

    def _load_items(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        academic_year = self._year_filter.get()
        academic_year = None if academic_year == "All" else academic_year
        year_group = self._yg_filter.get()
        year_group = None if year_group == "All" else year_group
        try:
            records = self._service.get_results(
                academic_year=academic_year, year_group=year_group
            )
            for r in records:
                score = r.get("score", 0)
                threshold = r.get("threshold", 32)
                try:
                    passed = "Yes" if int(score) >= int(threshold) else "No"
                except (ValueError, TypeError):
                    passed = ""
                self._tree.insert("", tk.END, iid=r.get("phonics_id", ""), values=(
                    r.get("pupil_id", ""),
                    r.get("academic_year", ""),
                    r.get("year_group", ""),
                    score,
                    threshold,
                    passed,
                    "Yes" if r.get("is_resit") else "No",
                ))
            self._status_var.set(f"{len(records)} phonics result(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load phonics results: {e}")

    def _clear_search(self):
        self._year_filter.set("All")
        self._yg_filter.set("All")
        self._load_items()

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a phonics result first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _PhonicsDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.record_result(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        pid = self._selected_id()
        if not pid:
            return
        results = self._service.get_results()
        record = next((r for r in results if str(r.get("id")) == str(pid)), None)
        if not record:
            messagebox.showerror("Error", "Phonics result not found.")
            return
        dlg = _PhonicsDialog(self, self._db_path, record=record)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_result(pid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        pid = self._selected_id()
        if not pid:
            return
        if not messagebox.askyesno("Confirm", f"Delete phonics result {pid}?"):
            return
        try:
            self._service.delete_result(pid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
