"""Staff directory GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.staff.staff_directory.services.staff_directory_service import StaffDirectoryService
import traceback


class StaffDirectoryFrame(tk.Frame):
    """Read-only staff directory screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = StaffDirectoryService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Staff Directory", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Label(toolbar, text="Search:", bg="#d5dbdb").pack(side="left")
        self._search_var = tk.StringVar()
        search_entry = tk.Entry(toolbar, textvariable=self._search_var, width=24)
        search_entry.pack(side="left", padx=3)
        tk.Button(toolbar, text="Go", command=self._load_items).pack(side="left")
        tk.Button(toolbar, text="Clear", command=self._clear_search).pack(side="left", padx=3)

        # Treeview
        columns = ("staff_id", "first_name", "last_name", "role",
                    "email", "class_teacher_of", "status")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=110)
        self._tree.column("staff_id", width=80)
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
            records = self._service.list_all(search=search)
            for r in records:
                self._tree.insert("", tk.END, iid=r.get("staff_id", r.get("id")), values=(
                    r.get("staff_id", r.get("id")), r.get("first_name", ""),
                    r.get("last_name", ""), r.get("role", ""),
                    r.get("email", ""), r.get("class_teacher_of", ""),
                    r.get("status", ""),
                ))
            self._status_var.set(f"{len(records)} staff member(s) found")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load staff directory: {e}")

    def _clear_search(self):
        self._search_var.set("")
        self._load_items()
