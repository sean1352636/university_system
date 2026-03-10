"""To-Do List GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from education_system.college_system.modules.domain.todo.services.todo_service import TodoService


class TodoFrame(tk.Frame):
    """To-Do List management screen."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = TodoService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="To-Do List",
                 font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)
        ttk.Button(header, text="Add Task",
                   command=self._on_add).pack(side="right", padx=20, pady=10)

        # Filter row
        filter_frame = tk.Frame(self, bg="#ecf0f1")
        filter_frame.pack(fill="x", padx=15, pady=(10, 5))

        tk.Label(filter_frame, text="Priority:", bg="#ecf0f1").pack(side="left", padx=(0, 5))
        self._filter_priority = tk.StringVar(value="All")
        ttk.Combobox(filter_frame, textvariable=self._filter_priority,
                     values=["All", "high", "medium", "low"], state="readonly",
                     width=10).pack(side="left", padx=(0, 15))

        self._show_completed_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_frame, text="Show Completed",
                        variable=self._show_completed_var,
                        command=self._load_items).pack(side="left")

        ttk.Button(filter_frame, text="Refresh",
                   command=self._load_items).pack(side="left", padx=10)

        # Treeview
        tree_frame = tk.Frame(self, bg="#ecf0f1")
        tree_frame.pack(fill="both", expand=True, padx=15, pady=5)

        columns = ("id", "title", "priority", "due_date", "status")
        self._tree = ttk.Treeview(tree_frame, columns=columns,
                                  show="headings", selectmode="browse")
        for col, heading, w in [
            ("id", "ID", 40), ("title", "Title", 250),
            ("priority", "Priority", 80), ("due_date", "Due Date", 100),
            ("status", "Status", 80),
        ]:
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=w, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._tree.bind("<Double-1>", lambda e: self._on_edit())

        # Button row
        btn_frame = tk.Frame(self, bg="#ecf0f1")
        btn_frame.pack(fill="x", padx=15, pady=(0, 10))
        ttk.Button(btn_frame, text="Toggle Complete",
                   command=self._on_toggle).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Edit",
                   command=self._on_edit).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Delete",
                   command=self._on_delete).pack(side="left", padx=5)

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(
            fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load_items()

    def _get_user_id(self) -> int:
        if self._auth and self._auth.current_user:
            return self._auth.current_user["user_id"]
        return 0

    def _load_items(self):
        self._tree.delete(*self._tree.get_children())
        try:
            items = self._svc.list_items(
                self._get_user_id(),
                show_completed=self._show_completed_var.get(),
            )
            priority_filter = self._filter_priority.get()
            for item in items:
                if priority_filter != "All" and item["priority"] != priority_filter:
                    continue
                status = "Completed" if item["is_completed"] else "Pending"
                self._tree.insert("", "end", values=(
                    item["id"], item["title"], item["priority"],
                    item.get("due_date") or "", status,
                ))
            self._status_var.set(f"{len(self._tree.get_children())} item(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _get_selected_id(self) -> int | None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Please select an item first.")
            return None
        return int(self._tree.item(sel[0], "values")[0])

    def _on_add(self):
        dlg = _TodoDialog(self, "Add Task")
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._svc.create_item(self._get_user_id(), **dlg.result)
                self._load_items()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _on_edit(self):
        item_id = self._get_selected_id()
        if item_id is None:
            return
        try:
            item = self._svc.get_item(item_id, self._get_user_id())
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        dlg = _TodoDialog(self, "Edit Task", item)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._svc.update_item(item_id, self._get_user_id(), **dlg.result)
                self._load_items()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _on_toggle(self):
        item_id = self._get_selected_id()
        if item_id is None:
            return
        try:
            self._svc.toggle_complete(item_id, self._get_user_id())
            self._load_items()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_delete(self):
        item_id = self._get_selected_id()
        if item_id is None:
            return
        if not messagebox.askyesno("Confirm", "Delete this task?"):
            return
        try:
            self._svc.delete_item(item_id, self._get_user_id())
            self._load_items()
        except Exception as e:
            messagebox.showerror("Error", str(e))


class _TodoDialog(tk.Toplevel):
    """Add/Edit to-do item dialog."""

    def __init__(self, parent, title, item=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x280")
        self.resizable(False, False)
        self.grab_set()
        self.result = None

        frame = tk.Frame(self, padx=15, pady=15)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Title:").grid(row=0, column=0, sticky="w", pady=3)
        self._title_var = tk.StringVar(value=item["title"] if item else "")
        ttk.Entry(frame, textvariable=self._title_var, width=35).grid(
            row=0, column=1, pady=3)

        tk.Label(frame, text="Description:").grid(row=1, column=0, sticky="nw", pady=3)
        self._desc_text = tk.Text(frame, width=27, height=3)
        self._desc_text.grid(row=1, column=1, pady=3)
        if item and item.get("description"):
            self._desc_text.insert("1.0", item["description"])

        tk.Label(frame, text="Priority:").grid(row=2, column=0, sticky="w", pady=3)
        self._priority_var = tk.StringVar(
            value=item["priority"] if item else "medium")
        ttk.Combobox(frame, textvariable=self._priority_var,
                     values=["low", "medium", "high"], state="readonly",
                     width=12).grid(row=2, column=1, sticky="w", pady=3)

        tk.Label(frame, text="Due Date:").grid(row=3, column=0, sticky="w", pady=3)
        self._due_var = tk.StringVar(
            value=item.get("due_date") or "" if item else "")
        ttk.Entry(frame, textvariable=self._due_var, width=15).grid(
            row=3, column=1, sticky="w", pady=3)
        tk.Label(frame, text="(YYYY-MM-DD)", font=("Helvetica", 8),
                 fg="#7f8c8d").grid(row=3, column=1, sticky="e", pady=3)

        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn_frame, text="Save", command=self._save).pack(
            side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(
            side="left", padx=5)

    def _save(self):
        title = self._title_var.get().strip()
        if not title:
            messagebox.showwarning("Input", "Title is required.", parent=self)
            return
        self.result = {
            "title": title,
            "description": self._desc_text.get("1.0", "end").strip() or None,
            "priority": self._priority_var.get(),
            "due_date": self._due_var.get().strip() or None,
        }
        self.destroy()
