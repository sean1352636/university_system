"""Timetable management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.academics.timetable.services.timetable_service import TimetableService
import traceback


DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
PERIODS = ["1", "2", "3", "4", "5", "6"]


class _TimetableDialog(tk.Toplevel):
    """Add / Edit timetable entry dialog."""

    def __init__(self, parent, db_path, entry=None):
        super().__init__(parent)
        self.result = None
        self._entry = entry
        self.title("Edit Timetable Entry" if entry else "Add Timetable Entry")
        self.geometry("480x450")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        frm = tk.Frame(self, padx=15, pady=10)
        frm.pack(fill="both", expand=True)

        self._add_field(frm, "class_name", "Class Name *")
        self._add_field(frm, "subject_code", "Subject Code *")
        self._add_combo(frm, "day_of_week", "Day of Week *", DAYS_OF_WEEK)
        self._add_combo(frm, "period", "Period *", PERIODS)
        self._add_field(frm, "start_time", "Start Time (HH:MM)")
        self._add_field(frm, "end_time", "End Time (HH:MM)")
        self._add_field(frm, "room", "Room")
        self._add_field(frm, "teacher_staff_id", "Teacher Staff ID")

        # Buttons
        btn_frame = tk.Frame(frm)
        btn_frame.pack(fill="x", pady=10)
        tk.Button(btn_frame, text="Save", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="right", padx=5)

        # Pre-fill for edit
        if entry:
            for key, widget in self._entries.items():
                val = entry.get(key)
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
        if not data.get("class_name"):
            messagebox.showwarning("Validation", "Class name is required.", parent=self)
            return
        if not data.get("subject_code"):
            messagebox.showwarning("Validation", "Subject code is required.", parent=self)
            return
        self.result = data
        self.destroy()


class TimetableFrame(tk.Frame):
    """Main timetable management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = TimetableService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Timetable Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Entry", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(toolbar, text="Class:", bg="#d5dbdb").pack(side="left")
        self._class_filter = ttk.Combobox(toolbar, values=["All"], state="readonly", width=12)
        self._class_filter.set("All")
        self._class_filter.pack(side="left", padx=3)
        self._class_filter.bind("<<ComboboxSelected>>", lambda e: self._load_items())

        tk.Label(toolbar, text="Search:", bg="#d5dbdb").pack(side="left", padx=(10, 0))
        self._search_var = tk.StringVar()
        search_entry = tk.Entry(toolbar, textvariable=self._search_var, width=18)
        search_entry.pack(side="left", padx=3)
        tk.Button(toolbar, text="Go", command=self._load_items).pack(side="left")
        tk.Button(toolbar, text="Clear", command=self._clear_search).pack(side="left", padx=3)

        # Treeview
        columns = ("class_name", "day", "period", "subject", "start_time", "end_time", "room", "teacher")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=100)
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
        class_name = self._class_filter.get()
        class_name = None if class_name == "All" else class_name
        search = self._search_var.get().strip() or None
        try:
            entries = self._service.get_timetable(class_name=class_name)
            for t in entries:
                self._tree.insert("", tk.END, iid=t.get("timetable_id", ""), values=(
                    t.get("class_name", ""),
                    t.get("day_of_week", t.get("day", "")),
                    t.get("period", ""),
                    t.get("subject_code", t.get("subject", "")),
                    t.get("start_time", ""),
                    t.get("end_time", ""),
                    t.get("room", ""),
                    t.get("teacher", t.get("teacher_staff_id", "")),
                ))
            self._status_var.set(f"{len(entries)} entry(ies) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load timetable: {e}")

    def _clear_search(self):
        self._search_var.set("")
        self._class_filter.set("All")
        self._load_items()

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select an entry first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _TimetableDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_slot(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        tid = self._selected_id()
        if not tid:
            return
        results = self._service.get_timetable()
        entry = next((t for t in results if str(t.get("id")) == str(tid)), None)
        if not entry:
            messagebox.showerror("Error", "Timetable entry not found.")
            return
        dlg = _TimetableDialog(self, self._db_path, entry=entry)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_slot(tid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        tid = self._selected_id()
        if not tid:
            return
        if not messagebox.askyesno("Confirm", f"Delete timetable entry {tid}?"):
            return
        try:
            self._service.delete_slot(tid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
