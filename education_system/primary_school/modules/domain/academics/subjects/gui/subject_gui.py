"""Subject management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.academics.subjects.services.subject_service import SubjectService
import traceback


class _SubjectDialog(tk.Toplevel):
    """Add / Edit subject dialog."""

    def __init__(self, parent, db_path, subject=None):
        super().__init__(parent)
        self.result = None
        self._subject = subject
        self.title("Edit Subject" if subject else "Add Subject")
        self.geometry("450x350")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        frm = tk.Frame(self, padx=15, pady=10)
        frm.pack(fill="both", expand=True)

        self._add_field(frm, "subject_code", "Subject Code *")
        self._add_field(frm, "title", "Title *")
        self._add_field(frm, "description", "Description")
        self._add_check(frm, "is_core", "Core Subject")
        self._add_combo(frm, "key_stage", "Key Stage",
                        ["All", "EYFS", "KS1", "KS2"])

        # Buttons
        btn_frame = tk.Frame(frm)
        btn_frame.pack(fill="x", pady=10)
        tk.Button(btn_frame, text="Save", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="right", padx=5)

        # Pre-fill for edit
        if subject:
            for key, widget in self._entries.items():
                val = subject.get(key)
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
        if not data.get("subject_code"):
            messagebox.showwarning("Validation", "Subject code is required.", parent=self)
            return
        if not data.get("title"):
            messagebox.showwarning("Validation", "Title is required.", parent=self)
            return
        self.result = data
        self.destroy()


class SubjectFrame(tk.Frame):
    """Main subject management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = SubjectService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Subject Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Subject", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)

        tk.Label(toolbar, text="Search:", bg="#d5dbdb").pack(side="left", padx=(10, 0))
        self._search_var = tk.StringVar()
        search_entry = tk.Entry(toolbar, textvariable=self._search_var, width=18)
        search_entry.pack(side="left", padx=3)
        tk.Button(toolbar, text="Go", command=self._load_items).pack(side="left")
        tk.Button(toolbar, text="Clear", command=self._clear_search).pack(side="left", padx=3)

        # Treeview
        columns = ("subject_code", "title", "is_core", "key_stage")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=120)
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
        search = self._search_var.get().strip() or None
        try:
            subjects = self._service.list_subjects()
            for s in subjects:
                self._tree.insert("", tk.END, iid=s.get("subject_code", ""), values=(
                    s.get("subject_code", ""),
                    s.get("title", ""),
                    "Yes" if s.get("is_core") else "No",
                    s.get("key_stage", ""),
                ))
            self._status_var.set(f"{len(subjects)} subject(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load subjects: {e}")

    def _clear_search(self):
        self._search_var.set("")
        self._load_items()

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a subject first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _SubjectDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_subject(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        sid = self._selected_id()
        if not sid:
            return
        subject = self._service.get_subject(sid)
        if not subject:
            messagebox.showerror("Error", "Subject not found.")
            return
        dlg = _SubjectDialog(self, self._db_path, subject=subject)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_subject(sid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        sid = self._selected_id()
        if not sid:
            return
        if not messagebox.askyesno("Confirm", f"Delete subject {sid}?"):
            return
        try:
            self._service.delete_subject(sid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
