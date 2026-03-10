"""Incident management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.facilities.incidents.services.incident_service import IncidentService
import traceback


INCIDENT_TYPES = ["Accident", "Injury", "Near Miss", "Property Damage",
                  "Medical", "Behavioural", "Other"]
SEVERITIES = ["Minor", "Moderate", "Major", "Critical"]


class _IncidentDialog(tk.Toplevel):
    """Add / Edit incident dialog."""

    def __init__(self, parent, db_path, record=None):
        super().__init__(parent)
        self.result = None
        self._record = record
        self.title("Edit Incident" if record else "Report Incident")
        self.geometry("520x580")
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

        self._add_combo(scroll_frame, "incident_type", "Incident Type *", INCIDENT_TYPES)
        self._add_field(scroll_frame, "location", "Location")
        self._add_combo(scroll_frame, "severity", "Severity *", SEVERITIES)
        self._add_field(scroll_frame, "pupil_ids", "Pupil IDs (comma-separated)")
        self._add_field(scroll_frame, "staff_ids", "Staff IDs (comma-separated)")
        self._add_field(scroll_frame, "reported_by", "Reported By *")
        self._add_field(scroll_frame, "incident_time", "Incident Time (HH:MM)")
        self._add_field(scroll_frame, "action_taken", "Action Taken")
        self._add_check(scroll_frame, "parent_notified", "Parent Notified")
        self._add_check(scroll_frame, "first_aid_given", "First Aid Given")

        # Description text area
        tk.Label(scroll_frame, text="Description *:", anchor="w").pack(fill="x", padx=10, pady=(5, 0))
        self._description_text = tk.Text(scroll_frame, height=5, width=50, wrap="word")
        self._description_text.pack(fill="x", padx=10, pady=2)

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
            if record.get("description"):
                self._description_text.insert("1.0", record["description"])

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def _add_field(self, parent, key, label, default=""):
        frm = tk.Frame(parent)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=24, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
        if default:
            entry.insert(0, default)
        self._entries[key] = entry

    def _add_combo(self, parent, key, label, values):
        frm = tk.Frame(parent)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=24, anchor="w").pack(side="left")
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
        data["description"] = self._description_text.get("1.0", tk.END).strip()
        if not data.get("incident_type"):
            messagebox.showwarning("Validation", "Incident type is required.", parent=self)
            return
        if not data.get("severity"):
            messagebox.showwarning("Validation", "Severity is required.", parent=self)
            return
        if not data.get("reported_by"):
            messagebox.showwarning("Validation", "Reported by is required.", parent=self)
            return
        if not data.get("description"):
            messagebox.showwarning("Validation", "Description is required.", parent=self)
            return
        self.result = data
        self.destroy()


class IncidentFrame(tk.Frame):
    """Main incident management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = IncidentService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Incident Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Report Incident", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(toolbar, text="Type:", bg="#d5dbdb").pack(side="left")
        self._type_filter = ttk.Combobox(toolbar, values=["All"] + INCIDENT_TYPES,
                                          state="readonly", width=15)
        self._type_filter.set("All")
        self._type_filter.pack(side="left", padx=3)
        self._type_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        tk.Label(toolbar, text="Severity:", bg="#d5dbdb").pack(side="left", padx=(10, 0))
        self._severity_filter = ttk.Combobox(toolbar, values=["All"] + SEVERITIES,
                                              state="readonly", width=10)
        self._severity_filter.set("All")
        self._severity_filter.pack(side="left", padx=3)
        self._severity_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        tk.Label(toolbar, text="Status:", bg="#d5dbdb").pack(side="left", padx=(10, 0))
        self._status_filter = ttk.Combobox(toolbar, values=["All", "Open", "Investigating",
                                                              "Resolved", "Closed"],
                                            state="readonly", width=12)
        self._status_filter.set("All")
        self._status_filter.pack(side="left", padx=3)
        self._status_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        # Treeview
        columns = ("incident_id", "incident_type", "description", "location",
                   "severity", "reported_by", "incident_date", "status")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=110)
        self._tree.column("incident_id", width=80)
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
        type_val = self._type_filter.get()
        incident_type = None if type_val == "All" else type_val
        sev_val = self._severity_filter.get()
        severity = None if sev_val == "All" else sev_val
        stat_val = self._status_filter.get()
        status = None if stat_val == "All" else stat_val
        try:
            records = self._service.list_incidents(
                incident_type=incident_type, severity=severity, status=status)
            for r in records:
                rid = r.get("incident_id", r.get("id"))
                desc = r.get("description", "")
                if len(desc) > 50:
                    desc = desc[:50] + "..."
                self._tree.insert("", tk.END, iid=rid, values=(
                    rid, r.get("incident_type", ""), desc,
                    r.get("location", ""), r.get("severity", ""),
                    r.get("reported_by", ""), r.get("incident_date", ""),
                    r.get("status", ""),
                ))
            self._status_var.set(f"{len(records)} incident(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load incidents: {e}")

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select an incident first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _IncidentDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_incident(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        rid = self._selected_id()
        if not rid:
            return
        record = self._service.get_incident(rid)
        if not record:
            messagebox.showerror("Error", "Incident not found.")
            return
        dlg = _IncidentDialog(self, self._db_path, record=record)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_incident(rid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        rid = self._selected_id()
        if not rid:
            return
        if not messagebox.askyesno("Confirm", f"Delete incident {rid}?"):
            return
        try:
            self._service.delete_incident(rid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
