"""Pastoral notes management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.pastoral_care.pastoral.services.pastoral_service import PastoralService
import traceback

NOTE_TYPES = ["Welfare", "Family", "Academic", "Social", "Medical", "Other"]


class _PastoralDialog(tk.Toplevel):
    """Add / Edit pastoral note dialog."""

    def __init__(self, parent, db_path, record=None):
        super().__init__(parent)
        self.result = None
        self._record = record
        self.title("Edit Pastoral Note" if record else "Add Pastoral Note")
        self.geometry("520x480")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        self._add_field("pupil_id", "Pupil ID *")
        self._add_combo("note_type", "Note Type *", NOTE_TYPES)
        self._add_field("subject", "Subject *")
        self._add_text("details", "Details")
        self._add_check("follow_up_required", "Follow-up Required")
        self._add_field("follow_up_date", "Follow-up Date (YYYY-MM-DD)")

        # Buttons
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", pady=10, padx=10)
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
                elif isinstance(widget, tk.Text):
                    widget.delete("1.0", tk.END)
                    widget.insert("1.0", str(val))
                else:
                    widget.delete(0, tk.END)
                    widget.insert(0, str(val))

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def _add_field(self, key, label, default=""):
        frm = tk.Frame(self)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=24, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
        if default:
            entry.insert(0, default)
        self._entries[key] = entry

    def _add_combo(self, key, label, values):
        frm = tk.Frame(self)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=24, anchor="w").pack(side="left")
        combo = ttk.Combobox(frm, values=values, state="readonly", width=27)
        combo.pack(side="left", fill="x", expand=True)
        if values:
            combo.set(values[0])
        self._entries[key] = combo

    def _add_text(self, key, label):
        frm = tk.Frame(self)
        frm.pack(fill="x", padx=10, pady=2)
        tk.Label(frm, text=label, width=24, anchor="w").pack(side="left", anchor="n")
        text = tk.Text(frm, width=30, height=5, wrap="word")
        text.pack(side="left", fill="x", expand=True)
        self._entries[key] = text

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
            elif isinstance(widget, tk.Text):
                data[key] = widget.get("1.0", tk.END).strip()
            else:
                data[key] = widget.get().strip()
        if not data.get("pupil_id"):
            messagebox.showwarning("Validation", "Pupil ID is required.", parent=self)
            return
        if not data.get("note_type"):
            messagebox.showwarning("Validation", "Note type is required.", parent=self)
            return
        if not data.get("subject"):
            messagebox.showwarning("Validation", "Subject is required.", parent=self)
            return
        self.result = data
        self.destroy()


class PastoralFrame(tk.Frame):
    """Main pastoral notes management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = PastoralService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Pastoral Notes", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Note", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(toolbar, text="Type:", bg="#d5dbdb").pack(side="left")
        self._type_filter = ttk.Combobox(toolbar, values=["All"] + NOTE_TYPES,
                                          state="readonly", width=12)
        self._type_filter.set("All")
        self._type_filter.pack(side="left", padx=3)
        self._type_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        tk.Label(toolbar, text="Status:", bg="#d5dbdb").pack(side="left", padx=(10, 0))
        self._status_filter = ttk.Combobox(toolbar, values=["All", "Open", "Closed"],
                                            state="readonly", width=10)
        self._status_filter.set("All")
        self._status_filter.pack(side="left", padx=3)
        self._status_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        # Treeview
        columns = ("note_id", "pupil_id", "note_type", "subject", "status",
                    "follow_up", "created_at")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=110)
        self._tree.column("note_id", width=80)
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
        note_type = self._type_filter.get()
        status = self._status_filter.get()
        type_val = None if note_type == "All" else note_type
        status_val = None if status == "All" else status
        try:
            records = self._service.get_notes(note_type=type_val, status=status_val)
            for r in records:
                self._tree.insert("", tk.END, iid=r.get("note_id", r.get("id")), values=(
                    r.get("note_id", r.get("id")), r.get("pupil_id", ""),
                    r.get("note_type", ""), r.get("subject", ""),
                    r.get("status", ""), r.get("follow_up", r.get("follow_up_date", "")),
                    r.get("created_at", ""),
                ))
            self._status_var.set(f"{len(records)} note(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load pastoral notes: {e}")

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a note first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _PastoralDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_note(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        rid = self._selected_id()
        if not rid:
            return
        results = self._service.get_notes()
        record = next((r for r in results if str(r.get("id")) == str(rid)), None)
        if not record:
            messagebox.showerror("Error", "Note not found.")
            return
        dlg = _PastoralDialog(self, self._db_path, record=record)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_note(rid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        rid = self._selected_id()
        if not rid:
            return
        if not messagebox.askyesno("Confirm", f"Delete pastoral note {rid}?"):
            return
        try:
            self._service.delete_note(rid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
