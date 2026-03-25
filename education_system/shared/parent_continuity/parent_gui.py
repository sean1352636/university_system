"""GUI frame for Parent Account Continuity across education systems."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.shared.parent_continuity.parent_service import ParentContinuityService

SYSTEM_NAMES = {
    "university": "University",
    "college": "Sixth Form College",
    "school": "Secondary School",
    "secondary": "Secondary School",
    "primary": "Primary School",
}


class ParentContinuityFrame(tk.Frame):
    """Frame for viewing and linking unlinked parent accounts after transfers."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = ParentContinuityService()
        self._current_system = self._detect_system()
        self._build_ui()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _detect_system(self):
        """Try to determine the current system from auth info."""
        if isinstance(self._auth, dict):
            return self._auth.get("system_key", "college")
        if hasattr(self._auth, "current_user") and self._auth.current_user:
            return self._auth.current_user.get("system_key", "college")
        return "college"

    def _get_user_id(self):
        if isinstance(self._auth, dict):
            return self._auth.get("user_id") or self._auth.get("id")
        if hasattr(self._auth, "current_user") and self._auth.current_user:
            return self._auth.current_user.get("user_id") or self._auth.current_user.get("id")
        return None

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg="#1a5276", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="Parent Account Continuity",
            font=("Helvetica", 15, "bold"), bg="#1a5276", fg="white",
        ).pack(side="left", padx=20, pady=10)

        # Toolbar
        toolbar = tk.Frame(self, bg="#ecf0f1", pady=8)
        toolbar.pack(fill="x", padx=15)

        ttk.Label(toolbar, text="System:").pack(side="left", padx=(0, 4))
        systems = list(SYSTEM_NAMES.keys())
        self._system_var = tk.StringVar(value=self._current_system)
        ttk.Combobox(
            toolbar, textvariable=self._system_var, values=systems,
            state="readonly", width=14,
        ).pack(side="left", padx=4)

        ttk.Button(toolbar, text="Refresh", command=self.refresh).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Link Selected", command=self._link_selected).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Link All", command=self._link_all).pack(side="left", padx=4)

        # Search bar
        search_frame = tk.Frame(self, bg="#ecf0f1")
        search_frame.pack(fill="x", padx=15, pady=(0, 5))
        ttk.Label(search_frame, text="Search student:").pack(side="left", padx=(0, 4))
        self._search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self._search_var, width=30)
        search_entry.pack(side="left", padx=4)
        ttk.Button(search_frame, text="Search", command=self._search).pack(side="left", padx=4)

        # Status label
        self._status_var = tk.StringVar(value="")
        tk.Label(
            self, textvariable=self._status_var, bg="#ecf0f1",
            font=("Helvetica", 10), fg="#2c3e50",
        ).pack(fill="x", padx=15)

        # Treeview
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(5, 15))

        columns = ("student_name", "parent_name", "source_system", "parent_email", "link_status")
        self._tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", selectmode="browse",
        )
        for col, heading, width in [
            ("student_name", "Student Name", 160),
            ("parent_name", "Parent Name", 160),
            ("source_system", "Source System", 130),
            ("parent_email", "Parent Email", 180),
            ("link_status", "Status", 90),
        ]:
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=width, anchor="w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Store data for linking
        self._row_data = {}

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------

    def refresh(self):
        """Reload unlinked parents for the selected system."""
        self._tree.delete(*self._tree.get_children())
        self._row_data.clear()
        dest = self._system_var.get()

        try:
            parents = self._svc.get_unlinked_parents(dest)
            for i, p in enumerate(parents):
                iid = str(i)
                src_display = SYSTEM_NAMES.get(p["source_system"], p["source_system"])
                self._tree.insert("", "end", iid=iid, values=(
                    p["student_name"],
                    p["parent_name"],
                    src_display,
                    p.get("parent_email", ""),
                    p["link_status"],
                ))
                self._row_data[iid] = p

            count = len(parents)
            self._status_var.set(
                f"{count} unlinked parent account(s) found." if count else
                "No unlinked parent accounts found."
            )
        except Exception as e:
            self._status_var.set(f"Error: {e}")

    def _link_selected(self):
        """Link the selected parent to the destination system."""
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Please select a parent to link.", parent=self)
            return

        data = self._row_data.get(sel[0])
        if not data:
            return

        uid = data.get("parent_user_id")
        dest = self._system_var.get()
        if not uid:
            messagebox.showwarning("Warning", "No matching auth account found for this parent.", parent=self)
            return

        ok = self._svc.link_parent_to_system(uid, dest, role="parent")
        if ok:
            messagebox.showinfo("Success", f"Parent '{data['parent_name']}' linked to {SYSTEM_NAMES.get(dest, dest)}.", parent=self)
            self.refresh()
        else:
            messagebox.showerror("Error", "Failed to link parent account.", parent=self)

    def _link_all(self):
        """Link all unlinked parents to the destination system."""
        dest = self._system_var.get()
        linked = 0
        failed = 0

        for iid, data in self._row_data.items():
            uid = data.get("parent_user_id")
            if not uid:
                continue
            ok = self._svc.link_parent_to_system(uid, dest, role="parent")
            if ok:
                linked += 1
            else:
                failed += 1

        messagebox.showinfo(
            "Bulk Link Complete",
            f"Linked: {linked}, Failed: {failed}",
            parent=self,
        )
        self.refresh()

    def _search(self):
        """Search for parent accounts by student name in all source systems."""
        name = self._search_var.get().strip()
        if not name:
            messagebox.showinfo("Info", "Enter a student name to search.", parent=self)
            return

        self._tree.delete(*self._tree.get_children())
        self._row_data.clear()

        all_systems = ["primary", "secondary", "college", "university"]
        found = 0

        for src in all_systems:
            try:
                parents = self._svc.find_parent_accounts(name, src)
                for p in parents:
                    iid = str(found)
                    src_display = SYSTEM_NAMES.get(src, src)
                    uid = p.get("matched_user_id")
                    status = "linked" if uid else "no account"
                    self._tree.insert("", "end", iid=iid, values=(
                        p["student_name"],
                        p["parent_name"],
                        src_display,
                        p.get("parent_email", ""),
                        status,
                    ))
                    self._row_data[iid] = {
                        **p,
                        "source_system": src,
                        "parent_user_id": uid,
                        "link_status": status,
                    }
                    found += 1
            except Exception:
                pass

        self._status_var.set(f"Found {found} parent record(s) matching '{name}'.")
