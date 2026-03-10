"""Policy management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.admin.policies.services.policy_service import PolicyService
import traceback


POLICY_CATEGORIES = [
    "Safeguarding", "Teaching & Learning", "Behaviour", "Health & Safety",
    "HR", "Admissions", "SEND", "Data Protection", "Other",
]


class _PolicyDialog(tk.Toplevel):
    """Add / Edit policy dialog."""

    def __init__(self, parent, db_path, policy=None):
        super().__init__(parent)
        self.result = None
        self._policy = policy
        self.title("Edit Policy" if policy else "Add Policy")
        self.geometry("560x580")
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

        self._add_field(scroll_frame, "title", "Title *")
        self._add_combo(scroll_frame, "category", "Category *", POLICY_CATEGORIES)

        # Content (Text widget)
        content_lbl = tk.Label(scroll_frame, text="Content", width=20, anchor="w")
        content_lbl.pack(fill="x", padx=10, pady=(8, 0))
        self._content_text = tk.Text(scroll_frame, width=55, height=12, wrap="word")
        self._content_text.pack(fill="x", padx=10, pady=2)

        self._add_field(scroll_frame, "version", "Version")
        self._add_field(scroll_frame, "approved_by", "Approved By")
        self._add_field(scroll_frame, "review_date", "Review Date (YYYY-MM-DD)")

        if policy:
            self._add_combo(scroll_frame, "status", "Status", ["Active", "Draft", "Archived"])

        # Buttons
        btn_frame = tk.Frame(scroll_frame)
        btn_frame.pack(fill="x", pady=10, padx=10)
        tk.Button(btn_frame, text="Save", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="right", padx=5)

        # Pre-fill for edit
        if policy:
            for key, widget in self._entries.items():
                val = policy.get(key)
                if val is None:
                    continue
                if isinstance(widget, ttk.Combobox):
                    widget.set(str(val))
                else:
                    widget.delete(0, tk.END)
                    widget.insert(0, str(val))
            content = policy.get("content", "")
            if content:
                self._content_text.insert("1.0", content)

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def _add_field(self, parent, key, label):
        frm = tk.Frame(parent)
        frm.pack(fill="x", padx=10, pady=3)
        tk.Label(frm, text=label, width=28, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
        self._entries[key] = entry

    def _add_combo(self, parent, key, label, values):
        frm = tk.Frame(parent)
        frm.pack(fill="x", padx=10, pady=3)
        tk.Label(frm, text=label, width=28, anchor="w").pack(side="left")
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
        data["content"] = self._content_text.get("1.0", tk.END).strip()
        if not data.get("title"):
            messagebox.showwarning("Validation", "Title is required.", parent=self)
            return
        if not data.get("category"):
            messagebox.showwarning("Validation", "Category is required.", parent=self)
            return
        self.result = data
        self.destroy()


class PolicyFrame(tk.Frame):
    """Main policy management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = PolicyService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Policy Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Policy", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        # Treeview
        columns = ("id", "title", "category", "version", "approved_by",
                    "approval_date", "review_date", "status")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=105)
        self._tree.column("id", width=50)
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
            policies = self._service.list_policies()
            for p in policies:
                self._tree.insert("", tk.END, iid=p.get("id"), values=(
                    p.get("id", ""), p.get("title", ""), p.get("category", ""),
                    p.get("version", ""), p.get("approved_by", ""),
                    p.get("approval_date", ""), p.get("review_date", ""),
                    p.get("status", ""),
                ))
            self._status_var.set(f"{len(policies)} policy(ies) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load policies: {e}")

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a policy first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _PolicyDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_policy(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        pid = self._selected_id()
        if not pid:
            return
        policy = self._service.get_policy(pid)
        if not policy:
            messagebox.showerror("Error", "Policy not found.")
            return
        dlg = _PolicyDialog(self, self._db_path, policy=policy)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_policy(pid, **dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        pid = self._selected_id()
        if not pid:
            return
        if not messagebox.askyesno("Confirm", f"Delete policy {pid}?"):
            return
        try:
            self._service.delete_policy(pid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
