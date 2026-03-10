"""Communication log management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.communication.communication_log.services.communication_log_service import CommunicationLogService
import traceback


CONTACT_TYPES = ["Phone", "Email", "Meeting", "Letter", "Home Visit", "Other"]


class _LogDialog(tk.Toplevel):
    """Add / Edit communication log entry dialog."""

    def __init__(self, parent, db_path, record=None):
        super().__init__(parent)
        self.result = None
        self._record = record
        self.title("Edit Log Entry" if record else "Add Log Entry")
        self.geometry("500x500")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        self._add_field("pupil_id", "Pupil ID *")
        self._add_combo("contact_type", "Contact Type *", CONTACT_TYPES)
        self._add_field("contact_with", "Contact With *")
        self._add_field("subject", "Subject *")
        self._add_field("outcome", "Outcome")
        self._add_check("follow_up_required", "Follow-up Required")
        self._add_field("follow_up_date", "Follow-up Date (YYYY-MM-DD)")

        # Details text area
        tk.Label(self, text="Details:", anchor="w").pack(fill="x", padx=10, pady=(5, 0))
        self._details_text = tk.Text(self, height=6, width=50, wrap="word")
        self._details_text.pack(fill="x", padx=10, pady=2)

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
                if isinstance(widget, tk.BooleanVar):
                    widget.set(bool(val))
                elif isinstance(widget, ttk.Combobox):
                    widget.set(str(val))
                else:
                    widget.delete(0, tk.END)
                    widget.insert(0, str(val))
            if record.get("details"):
                self._details_text.insert("1.0", record["details"])

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def _add_field(self, key, label, default=""):
        frm = tk.Frame(self)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=22, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
        if default:
            entry.insert(0, default)
        self._entries[key] = entry

    def _add_combo(self, key, label, values):
        frm = tk.Frame(self)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=22, anchor="w").pack(side="left")
        combo = ttk.Combobox(frm, values=values, state="readonly", width=27)
        combo.pack(side="left", fill="x", expand=True)
        if values:
            combo.set(values[0])
        self._entries[key] = combo

    def _add_check(self, key, label, default=False):
        frm = tk.Frame(self)
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
        data["details"] = self._details_text.get("1.0", tk.END).strip()
        if not data.get("pupil_id"):
            messagebox.showwarning("Validation", "Pupil ID is required.", parent=self)
            return
        if not data.get("contact_with"):
            messagebox.showwarning("Validation", "Contact with is required.", parent=self)
            return
        if not data.get("subject"):
            messagebox.showwarning("Validation", "Subject is required.", parent=self)
            return
        self.result = data
        self.destroy()


class CommunicationLogFrame(tk.Frame):
    """Main communication log management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = CommunicationLogService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Communication Log", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Entry", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Button(toolbar, text="Follow-ups Due", command=self._on_followups).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(toolbar, text="Contact Type:", bg="#d5dbdb").pack(side="left")
        self._type_filter = ttk.Combobox(toolbar, values=["All"] + CONTACT_TYPES,
                                          state="readonly", width=12)
        self._type_filter.set("All")
        self._type_filter.pack(side="left", padx=3)
        self._type_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        # Treeview
        columns = ("log_id", "pupil_id", "contact_type", "contact_with",
                   "subject", "outcome", "contact_date", "follow_up")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=110)
        self._tree.column("log_id", width=70)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, anchor="w", bg="#ecf0f1",
                 padx=10).pack(fill="x", side="bottom")

        self._show_followups = False
        self._load_items()

    def refresh(self):
        self._load_items()

    def _load_items(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        type_val = self._type_filter.get()
        contact_type = None if type_val == "All" else type_val
        try:
            records = self._service.get_entries(contact_type=contact_type)
            if self._show_followups:
                records = [r for r in records if r.get("follow_up_required")]
            for r in records:
                rid = r.get("log_id", r.get("id"))
                follow_up = "Yes" if r.get("follow_up_required") else ""
                self._tree.insert("", tk.END, iid=rid, values=(
                    rid, r.get("pupil_id", ""), r.get("contact_type", ""),
                    r.get("contact_with", ""), r.get("subject", ""),
                    r.get("outcome", ""), r.get("contact_date", ""),
                    follow_up,
                ))
            label = "follow-up " if self._show_followups else ""
            self._status_var.set(f"{len(records)} {label}log(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load communication logs: {e}")

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a log entry first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _LogDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_entry(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        rid = self._selected_id()
        if not rid:
            return
        results = self._service.get_entries()
        record = next((r for r in results if str(r.get("id")) == str(rid)), None)
        if not record:
            messagebox.showerror("Error", "Log entry not found.")
            return
        dlg = _LogDialog(self, self._db_path, record=record)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_entry(rid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        rid = self._selected_id()
        if not rid:
            return
        if not messagebox.askyesno("Confirm", f"Delete log entry {rid}?"):
            return
        try:
            self._service.delete_entry(rid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))

    def _on_followups(self):
        self._show_followups = not self._show_followups
        self._load_items()
