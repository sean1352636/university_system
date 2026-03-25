"""Notification GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.notifications.services.notification_service import NotificationService
from education_system.college_system.core.i18n import t


class NotificationFrame(tk.Frame):
    """Notification management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = NotificationService(db_path)
        self._unread_only = tk.BooleanVar(value=False)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("notifications.title"),
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._unread_label = tk.StringVar(value="Unread: --")
        tk.Label(header, textvariable=self._unread_label,
                 font=("Helvetica", 11), bg="#2c3e50", fg="#bdc3c7"
                 ).pack(side="right", padx=20, pady=10)

        # Toolbar
        toolbar = tk.Frame(self, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=20, pady=(10, 0))

        ttk.Checkbutton(toolbar, text=t("notifications.unread_only"),
                        variable=self._unread_only,
                        command=self._load_notifications).pack(side="left")
        ttk.Button(toolbar, text=t("notifications.mark_read"),
                   command=self._mark_read).pack(side="left", padx=10)
        ttk.Button(toolbar, text=t("notifications.mark_all_read"),
                   command=self._mark_all_read).pack(side="left")
        ttk.Button(toolbar, text=t("common.export_csv", default="Export CSV"),
                   command=self._export_csv).pack(side="right", padx=(0, 10))
        ttk.Button(toolbar, text=t("common.refresh"),
                   command=self._load_notifications).pack(side="right")

        # Treeview
        tree_frame = tk.Frame(self, bg="#ecf0f1")
        tree_frame.pack(fill="both", expand=True, padx=20, pady=10)

        cols = ("id", "type", "title", "read", "date")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=12)
        for c, w in zip(cols, (40, 70, 250, 50, 150)):
            self._tree.heading(c, text=c.capitalize())
            self._tree.column(c, width=w)

        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        self._tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # Detail pane
        detail_frame = tk.LabelFrame(self, text=t("common.details"), bg="#ecf0f1", padx=10, pady=5)
        detail_frame.pack(fill="x", padx=20, pady=(0, 10))

        self._detail_var = tk.StringVar(value="Select a notification to view details.")
        tk.Label(detail_frame, textvariable=self._detail_var, bg="#ecf0f1",
                 wraplength=600, justify="left").pack(fill="x")

    def refresh(self):
        self._load_notifications()

    def _get_user_id(self):
        """Get the LOCAL college user ID for the current logged-in user.

        Shared auth returns a shared-auth user ID which doesn't match the
        college local ``users`` table.  We resolve via username lookup.
        """
        if not self._auth:
            return None
        cu = self._auth.current_user if hasattr(self._auth, 'current_user') else None
        if not cu:
            return None
        username = cu.get("username")
        if username:
            try:
                from education_system.college_system.infrastructure.database.db import connect
                conn = connect(self._db_path)
                row = conn.execute(
                    "SELECT id FROM users WHERE username = ?", (username,)
                ).fetchone()
                conn.close()
                if row:
                    return row["id"]
            except Exception:
                pass
        # Fallback to shared auth ID (may not match local DB)
        return cu.get("user_id")

    def _load_notifications(self):
        self._tree.delete(*self._tree.get_children())
        self._detail_var.set("Select a notification to view details.")
        try:
            user_id = self._get_user_id()
            if not user_id:
                return
            notifications = self._svc.get_notifications(
                user_id, unread_only=self._unread_only.get()
            )
            unread = self._svc.count_unread(user_id)
            self._unread_label.set(f"Unread: {unread}")

            self._notifications = {n["id"]: n for n in notifications}

            for n in notifications:
                self._tree.insert("", "end", iid=str(n["id"]), values=(
                    n["id"], n["type"], n["title"],
                    "Yes" if n["is_read"] else "No",
                    n["created_at"][:19],
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _on_select(self, _event):
        sel = self._tree.selection()
        if not sel:
            return
        nid = int(sel[0])
        n = self._notifications.get(nid, {})
        self._detail_var.set(n.get("message", "(no message)"))

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._tree, "notifications.csv")

    def _mark_read(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("notifications.select_first"))
            return
        try:
            nid = int(sel[0])
            user_id = self._get_user_id()
            if not user_id:
                return
            self._svc.mark_read(nid, user_id)
            self._load_notifications()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _mark_all_read(self):
        try:
            user_id = self._get_user_id()
            if not user_id:
                return
            count = self._svc.mark_all_read(user_id)
            messagebox.showinfo(t("common.success"), t("notifications.marked_read_count", count=count))
            self._load_notifications()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
