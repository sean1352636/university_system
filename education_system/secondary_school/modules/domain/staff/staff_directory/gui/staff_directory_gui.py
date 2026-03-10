"""Staff Directory GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.staff.staff_directory.services.staff_directory_service import StaffDirectoryService

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"
TITLES = ("Mr", "Mrs", "Ms", "Miss", "Dr", "Prof")


class StaffDirectoryFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = StaffDirectoryService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Staff Directory", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)
        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        if self._auth and self._auth.get("role") == "admin":
            ttk.Button(toolbar, text="Add Staff", command=self._on_add).pack(side="left", padx=4)
            ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("title", "name", "role", "department", "email", "ext", "room", "subjects")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("title", "Title", 35), ("name", "Name", 130), ("role", "Role", 90),
                           ("department", "Dept", 80), ("email", "Email", 150),
                           ("ext", "Ext", 40), ("room", "Room", 50), ("subjects", "Subjects", 150)]:
            self._tree.heading(col, text=h)
            self._tree.column(col, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg=MAIN_BG, anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load()

    def _load(self):
        self._tree.delete(*self._tree.get_children())
        try:
            staff = self._svc.list_staff()
            for s in staff:
                self._tree.insert("", "end", iid=s["id"], values=(
                    s.get("title") or "", f"{s['first_name']} {s['last_name']}",
                    s.get("role") or "", s.get("department") or "",
                    s.get("email") or "", s.get("phone_ext") or "",
                    s.get("room") or "", s.get("subjects") or ""))
            self._status_var.set(f"{len(staff)} staff member(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add(self):
        dlg = tk.Toplevel(self)
        dlg.title("Add Staff")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        fields = [("Title", "title", "Mr", list(TITLES)), ("First Name", "first_name", "", None),
                  ("Last Name", "last_name", "", None), ("Role", "role", "Teacher", None),
                  ("Department", "department", "", None), ("Email", "email", "", None),
                  ("Phone Ext", "phone_ext", "", None), ("Room", "room", "", None),
                  ("Subjects", "subjects", "", None), ("Responsibilities", "responsibilities", "", None)]
        for row, (l, k, d, vals) in enumerate(fields):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            if vals:
                ttk.Combobox(c, textvariable=vars_[k], values=vals, state="readonly", width=20).grid(row=row, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[k], width=22).grid(row=row, column=1, **pad)
        result = [None]
        def save():
            fn = vars_["first_name"].get().strip()
            ln = vars_["last_name"].get().strip()
            if not fn or not ln:
                messagebox.showwarning("Validation", "First and last name required.")
                return
            result[0] = {k: v.get().strip() for k, v in vars_.items()}
            dlg.destroy()
        ttk.Button(c, text="Save", command=save).grid(row=len(fields), column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            self._svc.add_entry(d["first_name"], d["last_name"], d.get("title") or "Mr",
                                d.get("role") or "Teacher", d.get("department") or None,
                                d.get("email") or None, d.get("phone_ext") or None,
                                d.get("room") or None, d.get("subjects") or None,
                                d.get("responsibilities") or None)
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this staff entry?"):
            self._svc.delete_entry(int(sel[0]))
            self._load()
