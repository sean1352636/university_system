"""Notification management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.communication.notifications.services.notification_service import NotificationService
import traceback


NOTIFICATION_TYPES = ["Info", "Warning", "Alert", "Reminder"]


class _NotificationDialog(tk.Toplevel):
    """Create notification dialog."""

    def __init__(self, parent, db_path, record=None):
        super().__init__(parent)
        self.result = None
        self._record = record
        self.title("Edit Notification" if record else "Create Notification")
        self.geometry("450x300")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        self._add_field("user_id", "User ID")
        self._add_field("title", "Title *")
        self._add_field("message", "Message *")
        self._add_combo("notification_type", "Type", NOTIFICATION_TYPES)

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
        if not data.get("title"):
            messagebox.showwarning("Validation", "Title is required.", parent=self)
            return
        if not data.get("message"):
            messagebox.showwarning("Validation", "Message is required.", parent=self)
            return
        self.result = data
        self.destroy()


class NotificationFrame(tk.Frame):
    """Main notification management screen."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = NotificationService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Notifications", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Toolbar
        toolbar = tk.Frame(self, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Create Notification", command=self._on_add).pack(side="left", padx=3)
        tk.Button(toolbar, text="Mark Read", command=self._on_mark_read).pack(side="left", padx=3)
        tk.Button(toolbar, text="Mark All Read", command=self._on_mark_all_read).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=3)

        # Treeview
        columns = ("notification_id", "title", "message", "notification_type",
                   "is_read", "created_at")
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=120)
        self._tree.column("notification_id", width=80)
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
            user_id = self._auth.current_user.get("id") if self._auth else None
            records = self._service.get_notifications(user_id) if user_id else []
            for r in records:
                rid = r.get("notification_id", r.get("id"))
                is_read = "Yes" if r.get("is_read") else "No"
                self._tree.insert("", tk.END, iid=rid, values=(
                    rid, r.get("title", ""), r.get("message", ""),
                    r.get("notification_type", r.get("type", "")),
                    is_read, r.get("created_at", ""),
                ))
            self._status_var.set(f"{len(records)} notification(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load notifications: {e}")

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a notification first.")
            return None
        return sel[0]

    def _on_add(self):
        dlg = _NotificationDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_notification(**dlg.result)
                self._load_items()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_mark_read(self):
        rid = self._selected_id()
        if not rid:
            return
        try:
            self._service.mark_read(rid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))

    def _on_mark_all_read(self):
        try:
            user_id = self._auth.current_user.get("id") if self._auth else None
            if user_id:
                self._service.mark_all_read(user_id)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))

    def _on_delete(self):
        rid = self._selected_id()
        if not rid:
            return
        if not messagebox.askyesno("Confirm", f"Delete notification {rid}?"):
            return
        try:
            self._service.delete_notification(rid)
            self._load_items()
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))
