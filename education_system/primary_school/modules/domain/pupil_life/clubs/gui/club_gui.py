"""Club management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.pupil_life.clubs.services.club_service import ClubService
import traceback


class _MembersDialog(tk.Toplevel):
    """Dialog to manage club members."""

    def __init__(self, parent, service, club_id):
        super().__init__(parent)
        self.title("Manage Members")
        self.geometry("400x400")
        self.resizable(False, False)
        self.grab_set()
        self._service = service
        self._club_id = club_id

        tk.Label(self, text="Club Members", font=("Helvetica", 11, "bold")).pack(pady=5)

        # Members list
        list_frame = tk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self._listbox = tk.Listbox(list_frame)
        self._listbox.pack(side="left", fill="both", expand=True)
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        # Add/Remove
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(btn_frame, text="Pupil ID:").pack(side="left")
        self._pupil_entry = tk.Entry(btn_frame, width=15)
        self._pupil_entry.pack(side="left", padx=5)
        tk.Button(btn_frame, text="Add", command=self._add_member).pack(side="left", padx=3)
        tk.Button(btn_frame, text="Remove Selected", command=self._remove_member).pack(side="left", padx=3)

        tk.Button(self, text="Close", command=self.destroy, width=12).pack(pady=10)

        self._load_members()
        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def _load_members(self):
        self._listbox.delete(0, tk.END)
        try:
            members = self._service.list_club_members(self._club_id)
            for m in members:
                self._listbox.insert(tk.END, m.get("pupil_id", m.get("id", "")))
        except Exception:
            traceback.print_exc()
            pass

    def _add_member(self):
        pupil_id = self._pupil_entry.get().strip()
        if not pupil_id:
            messagebox.showwarning("Validation", "Enter a Pupil ID.", parent=self)
            return
        try:
            self._service.add_club_member(self._club_id, pupil_id)
            self._pupil_entry.delete(0, tk.END)
            self._load_members()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e), parent=self)

    def _remove_member(self):
        sel = self._listbox.curselection()
        if not sel:
            messagebox.showwarning("Selection", "Select a member first.", parent=self)
            return
        pupil_id = self._listbox.get(sel[0])
        try:
            self._service.remove_club_member(self._club_id, pupil_id)
            self._load_members()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e), parent=self)


class _ClubDialog(tk.Toplevel):
    """Add / Edit club dialog."""

    def __init__(self, parent, db_path, record=None):
        super().__init__(parent)
        self.result = None
        self._record = record
        self.title("Edit Club" if record else "Add Club")
        self.geometry("480x480")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        self._add_field("club_name", "Club Name *")
        self._add_field("description", "Description")
        self._add_combo("day_of_week", "Day of Week *",
                        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
        self._add_field("start_time", "Start Time (HH:MM)")
        self._add_field("end_time", "End Time (HH:MM)")
        self._add_field("location", "Location")
        self._add_field("staff_id", "Staff ID")
        self._add_field("max_capacity", "Max Capacity")
        self._add_field("year_groups", "Year Groups")
        self._add_combo("term", "Term", ["Autumn", "Spring", "Summer"])

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
        if not data.get("club_name"):
            messagebox.showwarning("Validation", "Club name is required.", parent=self)
            return
        self.result = data
        self.destroy()


class ClubFrame(tk.Frame):
    """Main club management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = ClubService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Club Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Club", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Button(toolbar, text="Manage Members", command=self._on_manage_members).pack(side="left", padx=3)

        # Treeview
        columns = ("club_id", "club_name", "day_of_week", "start_time", "end_time",
                   "location", "staff_id", "status")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=110)
        self._tree.column("club_id", width=70)
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
            records = self._service.list_clubs()
            for r in records:
                rid = r.get("club_id", r.get("id"))
                self._tree.insert("", tk.END, iid=rid, values=(
                    rid, r.get("club_name", ""), r.get("day_of_week", ""),
                    r.get("start_time", ""), r.get("end_time", ""),
                    r.get("location", ""), r.get("staff_id", ""),
                    r.get("status", ""),
                ))
            self._status_var.set(f"{len(records)} club(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load clubs: {e}")

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a club first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _ClubDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_club(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        rid = self._selected_id()
        if not rid:
            return
        record = self._service.get_club(rid)
        if not record:
            messagebox.showerror("Error", "Club not found.")
            return
        dlg = _ClubDialog(self, self._db_path, record=record)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_club(rid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        rid = self._selected_id()
        if not rid:
            return
        if not messagebox.askyesno("Confirm", f"Delete club {rid}?"):
            return
        try:
            self._service.delete_club(rid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))

    def _on_manage_members(self):
        rid = self._selected_id()
        if not rid:
            return
        dlg = _MembersDialog(self, self._service, rid)
        self.wait_window(dlg)
