"""User Management GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.admin.users.services.user_service import (
    UserService, ROLES,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class UserFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = UserService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="User Management", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)
        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Add User", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Reset Password", command=self._on_reset_pw).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Toggle Active", command=self._on_toggle).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Change Role", command=self._on_change_role).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)

        tk.Label(toolbar, text="Role:", bg=MAIN_BG).pack(side="left", padx=(15, 4))
        self._role_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._role_var,
                     values=["All"] + list(ROLES), state="readonly", width=10).pack(side="left", padx=4)
        self._role_var.trace_add("write", lambda *_: self._load())

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("username", "role", "email", "active", "created")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("username", "Username", 140), ("role", "Role", 80),
                           ("email", "Email", 180), ("active", "Active", 55), ("created", "Created", 130)]:
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
        r = self._role_var.get()
        try:
            users = self._svc.list_users(role=r if r != "All" else None)
            for u in users:
                self._tree.insert("", "end", iid=u["id"], values=(
                    u["username"], u["role"], u.get("email") or "",
                    "Yes" if u["is_active"] else "No",
                    u["created_at"][:16] if u.get("created_at") else ""))
            self._status_var.set(f"{len(users)} user(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add(self):
        dlg = tk.Toplevel(self)
        dlg.title("Add User")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        for row, (l, k, d) in enumerate([("Username", "username", ""),
                                           ("Password", "password", ""),
                                           ("Email", "email", "")]):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            e = ttk.Entry(c, textvariable=vars_[k], width=25)
            if k == "password":
                e.configure(show="*")
            e.grid(row=row, column=1, **pad)
        row = 3
        tk.Label(c, text="Role", font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        vars_["role"] = tk.StringVar(value="student")
        ttk.Combobox(c, textvariable=vars_["role"], values=list(ROLES), state="readonly", width=22).grid(row=row, column=1, **pad)
        result = [None]

        def save():
            u = vars_["username"].get().strip()
            p = vars_["password"].get().strip()
            if not u or not p:
                messagebox.showwarning("Validation", "Username and password required.")
                return
            result[0] = {k: v.get().strip() for k, v in vars_.items()}
            dlg.destroy()
        row += 1
        ttk.Button(c, text="Create", command=save).grid(row=row, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            self._svc.create_user(d["username"], d["password"], d["role"], d["email"] or None)
            messagebox.showinfo("Success", "User created.")
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_reset_pw(self):
        sel = self._tree.selection()
        if not sel:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Reset Password")
        dlg.resizable(False, False)
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        tk.Label(c, text="New Password:", font=("Helvetica", 9, "bold")).pack(anchor="w")
        pw_var = tk.StringVar()
        ttk.Entry(c, textvariable=pw_var, show="*", width=25).pack(pady=5)
        result = [None]

        def save():
            p = pw_var.get().strip()
            if not p:
                messagebox.showwarning("Validation", "Password required.")
                return
            result[0] = p
            dlg.destroy()
        ttk.Button(c, text="Reset", command=save).pack(pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        try:
            self._svc.reset_password(int(sel[0]), result[0])
            messagebox.showinfo("Success", "Password reset.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_toggle(self):
        sel = self._tree.selection()
        if not sel:
            return
        self._svc.toggle_active(int(sel[0]))
        self._load()

    def _on_change_role(self):
        sel = self._tree.selection()
        if not sel:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Change Role")
        dlg.resizable(False, False)
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        tk.Label(c, text="New Role:", font=("Helvetica", 9, "bold")).pack(anchor="w")
        role_var = tk.StringVar(value="student")
        ttk.Combobox(c, textvariable=role_var, values=list(ROLES), state="readonly", width=15).pack(pady=5)
        result = [None]

        def save():
            result[0] = role_var.get()
            dlg.destroy()
        ttk.Button(c, text="Save", command=save).pack(pady=10)
        self.wait_window(dlg)
        if result[0]:
            try:
                self._svc.update_role(int(sel[0]), result[0])
                self._load()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this user permanently?"):
            self._svc.delete_user(int(sel[0]))
            self._load()
