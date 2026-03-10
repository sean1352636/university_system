"""SATs management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.academics.sats.services.sats_service import SATsService
import traceback
from education_system.primary_school.infrastructure.database.constants import (
    SATS_KS1_SUBJECTS,
    SATS_KS2_SUBJECTS,
    SATS_OUTCOMES,
)


class _SATsDialog(tk.Toplevel):
    """Add / Edit SATs result dialog."""

    def __init__(self, parent, db_path, result_data=None):
        super().__init__(parent)
        self.result = None
        self._result_data = result_data
        self.title("Edit SATs Result" if result_data else "Add SATs Result")
        self.geometry("480x480")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        frm = tk.Frame(self, padx=15, pady=10)
        frm.pack(fill="both", expand=True)

        self._add_field(frm, "pupil_id", "Pupil ID *")
        self._add_field(frm, "academic_year", "Academic Year *")
        self._add_combo(frm, "key_stage", "Key Stage *", ["KS1", "KS2"])
        self._add_combo(frm, "subject", "Subject *", SATS_KS1_SUBJECTS + SATS_KS2_SUBJECTS)
        self._add_field(frm, "raw_score", "Raw Score")
        self._add_field(frm, "scaled_score", "Scaled Score")
        self._add_combo(frm, "outcome", "Outcome", [""] + list(SATS_OUTCOMES))
        self._add_field(frm, "teacher_assessment", "Teacher Assessment")

        # Bind key_stage change to update subject list
        ks_combo = self._entries.get("key_stage")
        if ks_combo:
            ks_combo.bind("<<ComboboxSelected>>", self._on_ks_change)

        # Buttons
        btn_frame = tk.Frame(frm)
        btn_frame.pack(fill="x", pady=10)
        tk.Button(btn_frame, text="Save", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="right", padx=5)

        # Pre-fill for edit
        if result_data:
            for key, widget in self._entries.items():
                val = result_data.get(key)
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

    def _on_ks_change(self, event=None):
        ks = self._entries["key_stage"].get()
        subject_combo = self._entries.get("subject")
        if subject_combo:
            if ks == "KS1":
                subject_combo["values"] = SATS_KS1_SUBJECTS
            elif ks == "KS2":
                subject_combo["values"] = SATS_KS2_SUBJECTS
            else:
                subject_combo["values"] = SATS_KS1_SUBJECTS + SATS_KS2_SUBJECTS
            if subject_combo.get() not in subject_combo["values"]:
                subject_combo.set(subject_combo["values"][0] if subject_combo["values"] else "")

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
        if not data.get("key_stage"):
            messagebox.showwarning("Validation", "Key stage is required.", parent=self)
            return
        if not data.get("subject"):
            messagebox.showwarning("Validation", "Subject is required.", parent=self)
            return
        self.result = data
        self.destroy()


class SATsFrame(tk.Frame):
    """Main SATs results management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = SATsService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="SATs Results Management", fg="white", bg=self.HEADER_BG,
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

        tk.Label(toolbar, text="Key Stage:", bg="#d5dbdb").pack(side="left", padx=(5, 0))
        self._ks_filter = ttk.Combobox(toolbar, values=["All", "KS1", "KS2"],
                                        state="readonly", width=8)
        self._ks_filter.set("All")
        self._ks_filter.pack(side="left", padx=3)
        self._ks_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        # Treeview
        columns = ("pupil_id", "academic_year", "key_stage", "subject",
                    "raw_score", "scaled_score", "outcome")
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
        key_stage = self._ks_filter.get()
        key_stage = None if key_stage == "All" else key_stage
        try:
            results = self._service.get_results(
                academic_year=academic_year, key_stage=key_stage
            )
            for r in results:
                self._tree.insert("", tk.END, iid=r.get("sats_id", ""), values=(
                    r.get("pupil_id", ""),
                    r.get("academic_year", ""),
                    r.get("key_stage", ""),
                    r.get("subject", ""),
                    r.get("raw_score", ""),
                    r.get("scaled_score", ""),
                    r.get("outcome", ""),
                ))
            self._status_var.set(f"{len(results)} SATs result(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load SATs results: {e}")

    def _clear_search(self):
        self._year_filter.set("All")
        self._ks_filter.set("All")
        self._load_items()

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a SATs result first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _SATsDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.record_result(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        sid = self._selected_id()
        if not sid:
            return
        results = self._service.get_results()
        result_data = next((r for r in results if str(r.get("id")) == str(sid)), None)
        if not result_data:
            messagebox.showerror("Error", "SATs result not found.")
            return
        dlg = _SATsDialog(self, self._db_path, result_data=result_data)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_result(sid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        sid = self._selected_id()
        if not sid:
            return
        if not messagebox.askyesno("Confirm", f"Delete SATs result {sid}?"):
            return
        try:
            self._service.delete_result(sid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
