"""Meal management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.pupil_life.meals.services.meal_service import MealService
from education_system.primary_school.infrastructure.database.constants import MEAL_TYPES, MEAL_ENTITLEMENTS
import traceback


class _MealDialog(tk.Toplevel):
    """Add / Edit meal record dialog."""

    def __init__(self, parent, db_path, record=None):
        super().__init__(parent)
        self.result = None
        self._record = record
        self.title("Edit Meal Record" if record else "Add Meal Record")
        self.geometry("450x350")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        self._add_field("pupil_id", "Pupil ID *")
        self._add_field("date", "Date (YYYY-MM-DD) *")
        self._add_combo("meal_type", "Meal Type *", list(MEAL_TYPES))
        self._add_field("meal_choice", "Meal Choice")
        self._add_combo("entitlement", "Entitlement", list(MEAL_ENTITLEMENTS))

        # Buttons
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", pady=10, padx=10)
        tk.Button(btn_frame, text="Save", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="right", padx=5)

        if record:
            for key, widget in self._entries.items():
                val = record.get(key)
                if val is None:
                    continue
                if isinstance(widget, ttk.Combobox):
                    widget.set(str(val))
                else:
                    widget.delete(0, tk.END)
                    widget.insert(0, str(val))

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def _add_field(self, key, label, default=""):
        frm = tk.Frame(self)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=20, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
        if default:
            entry.insert(0, default)
        self._entries[key] = entry

    def _add_combo(self, key, label, values):
        frm = tk.Frame(self)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=20, anchor="w").pack(side="left")
        combo = ttk.Combobox(frm, values=values, state="readonly", width=27)
        combo.pack(side="left", fill="x", expand=True)
        if values:
            combo.set(values[0])
        self._entries[key] = combo

    def _save(self):
        data = {}
        for key, widget in self._entries.items():
            if isinstance(widget, ttk.Combobox):
                data[key] = widget.get()
            else:
                data[key] = widget.get().strip()
        if not data.get("pupil_id"):
            messagebox.showwarning("Validation", "Pupil ID is required.", parent=self)
            return
        if not data.get("date"):
            messagebox.showwarning("Validation", "Date is required.", parent=self)
            return
        self.result = data
        self.destroy()


class MealFrame(tk.Frame):
    """Main meal management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = MealService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Meal Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Record", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Button(toolbar, text="Daily Summary", command=self._on_daily_summary).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(toolbar, text="Date:", bg="#d5dbdb").pack(side="left")
        self._date_filter = tk.Entry(toolbar, width=12)
        self._date_filter.pack(side="left", padx=3)

        tk.Label(toolbar, text="Meal Type:", bg="#d5dbdb").pack(side="left", padx=(10, 0))
        self._type_filter = ttk.Combobox(toolbar, values=["All"] + list(MEAL_TYPES),
                                          state="readonly", width=12)
        self._type_filter.set("All")
        self._type_filter.pack(side="left", padx=3)
        self._type_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        tk.Button(toolbar, text="Filter", command=self._load_items).pack(side="left", padx=3)

        # Treeview
        columns = ("meal_id", "pupil_id", "date", "meal_type", "meal_choice", "entitlement")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=110)
        self._tree.column("meal_id", width=70)
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
        date_val = self._date_filter.get().strip() or None
        type_val = self._type_filter.get()
        meal_type = None if type_val == "All" else type_val
        try:
            records = self._service.get_meals(date=date_val, meal_type=meal_type)
            for r in records:
                rid = r.get("meal_id", r.get("id"))
                self._tree.insert("", tk.END, iid=rid, values=(
                    rid, r.get("pupil_id", ""), r.get("date", ""),
                    r.get("meal_type", ""), r.get("meal_choice", ""),
                    r.get("entitlement", ""),
                ))
            self._status_var.set(f"{len(records)} record(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load meals: {e}")

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a record first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _MealDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.record_meal(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        rid = self._selected_id()
        if not rid:
            return
        results = self._service.get_meals()
        record = next((r for r in results if str(r.get("id")) == str(rid)), None)
        if not record:
            messagebox.showerror("Error", "Record not found.")
            return
        dlg = _MealDialog(self, self._db_path, record=record)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_meal(rid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        rid = self._selected_id()
        if not rid:
            return
        if not messagebox.askyesno("Confirm", f"Delete meal record {rid}?"):
            return
        try:
            # Note: meal service does not support delete
            messagebox.showwarning("Not Supported", "Deleting meal records is not supported.")
            return
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))

    def _on_daily_summary(self):
        date_val = self._date_filter.get().strip()
        if not date_val:
            messagebox.showinfo("Daily Summary", "Enter a date in the filter field first.")
            return
        try:
            records = self._service.get_meals(date=date_val)
            counts = {}
            for r in records:
                mt = r.get("meal_type", "Unknown")
                counts[mt] = counts.get(mt, 0) + 1
            summary = f"Daily Meal Summary for {date_val}\n\n"
            summary += f"Total meals: {len(records)}\n\n"
            for mt, count in sorted(counts.items()):
                summary += f"  {mt}: {count}\n"
            messagebox.showinfo("Daily Summary", summary)
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
