"""Medical records management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.pupil_life.medical.services.medical_service import MedicalService
import traceback


ALLERGY_SEVERITIES = ["None", "Mild", "Moderate", "Severe", "Life-threatening"]


class _MedicalDialog(tk.Toplevel):
    """Add / Edit medical record dialog."""

    def __init__(self, parent, db_path, record=None):
        super().__init__(parent)
        self.result = None
        self._record = record
        self.title("Edit Medical Record" if record else "Add Medical Record")
        self.geometry("500x550")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._add_field(scroll_frame, "pupil_id", "Pupil ID *")
        self._add_field(scroll_frame, "condition", "Condition")
        self._add_field(scroll_frame, "medication", "Medication")
        self._add_field(scroll_frame, "dosage", "Dosage")
        self._add_field(scroll_frame, "administration_time", "Administration Time")
        self._add_check(scroll_frame, "care_plan", "Care Plan Required")
        self._add_field(scroll_frame, "allergy", "Allergy")
        self._add_combo(scroll_frame, "allergy_severity", "Allergy Severity", ALLERGY_SEVERITIES)
        self._add_field(scroll_frame, "emergency_protocol", "Emergency Protocol")
        self._add_field(scroll_frame, "doctor_name", "Doctor Name")
        self._add_field(scroll_frame, "doctor_phone", "Doctor Phone")
        self._add_field(scroll_frame, "notes", "Notes")

        # Buttons
        btn_frame = tk.Frame(scroll_frame)
        btn_frame.pack(fill="x", pady=10, padx=10)
        tk.Button(btn_frame, text="Save", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="right", padx=5)

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
        tk.Label(frm, text=label, width=22, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
        if default:
            entry.insert(0, default)
        self._entries[key] = entry

    def _add_combo(self, parent, key, label, values):
        frm = tk.Frame(parent)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=22, anchor="w").pack(side="left")
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
        self.result = data
        self.destroy()


class MedicalFrame(tk.Frame):
    """Main medical records management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = MedicalService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Medical Records", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Record", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Button(toolbar, text="View Allergies", command=self._on_view_allergies).pack(side="left", padx=3)

        # Treeview
        columns = ("medical_id", "pupil_id", "condition", "medication",
                   "allergy", "allergy_severity", "care_plan")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=110)
        self._tree.column("medical_id", width=80)
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
        try:
            records = self._service.get_records()
            for r in records:
                rid = r.get("medical_id", r.get("id"))
                care_plan = "Yes" if r.get("care_plan") else "No"
                self._tree.insert("", tk.END, iid=rid, values=(
                    rid, r.get("pupil_id", ""), r.get("condition", ""),
                    r.get("medication", ""), r.get("allergy", ""),
                    r.get("allergy_severity", ""), care_plan,
                ))
            self._status_var.set(f"{len(records)} record(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load medical records: {e}")

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a record first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _MedicalDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_record(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        rid = self._selected_id()
        if not rid:
            return
        results = self._service.get_records()
        record = next((r for r in results if str(r.get("id")) == str(rid)), None)
        if not record:
            messagebox.showerror("Error", "Record not found.")
            return
        dlg = _MedicalDialog(self, self._db_path, record=record)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_record(rid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        rid = self._selected_id()
        if not rid:
            return
        if not messagebox.askyesno("Confirm", f"Delete medical record {rid}?"):
            return
        try:
            self._service.delete_record(rid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))

    def _on_view_allergies(self):
        try:
            records = self._service.get_records()
            allergies = [r for r in records if r.get("allergy")]
            if not allergies:
                messagebox.showinfo("Allergies", "No allergies recorded.")
                return
            summary = "Pupil Allergies\n\n"
            for r in allergies:
                severity = r.get("allergy_severity", "Unknown")
                summary += f"Pupil {r.get('pupil_id', '?')}: {r.get('allergy', '')} ({severity})\n"
            messagebox.showinfo("Allergies", summary)
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
