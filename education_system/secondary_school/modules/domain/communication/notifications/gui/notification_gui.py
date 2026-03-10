"""Notifications Centre GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.communication.notifications.services.notification_service import NotificationService

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class NotificationFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = NotificationService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Notifications", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)
        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Mark Read", command=self._on_mark_read).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Mark All Read", command=self._on_mark_all_read).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)
        self._unread_var = tk.BooleanVar()
        ttk.Checkbutton(toolbar, text="Unread Only", variable=self._unread_var,
                        command=self._load).pack(side="left", padx=10)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 5))
        cols = ("read", "title", "message", "date")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("read", "", 30), ("title", "Title", 180),
                           ("message", "Message", 320), ("date", "Date", 130)]:
            self._tree.heading(col, text=h)
            self._tree.column(col, width=w, anchor="w" if col in ("title", "message") else "center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._preview = tk.Text(self, height=4, wrap="word", font=("Helvetica", 10),
                                state="disabled", bg="white")
        self._preview.pack(fill="x", padx=15, pady=(0, 10))

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg=MAIN_BG, anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))
        self._data = {}

    def refresh(self):
        self._load()

    def _get_user_id(self):
        return self._auth.get("user_id") if self._auth else None

    def _load(self):
        self._tree.delete(*self._tree.get_children())
        self._data.clear()
        user_id = self._get_user_id()
        if not user_id:
            return
        try:
            notifs = self._svc.list_notifications(user_id, unread_only=self._unread_var.get())
            for n in notifs:
                iid = str(n["id"])
                marker = "" if n["is_read"] else "NEW"
                msg_preview = (n["message"][:60] + "...") if len(n["message"]) > 60 else n["message"]
                self._tree.insert("", "end", iid=iid, values=(
                    marker, n["title"], msg_preview,
                    n["created_at"][:16] if n.get("created_at") else ""))
                self._data[iid] = n
                if not n["is_read"]:
                    self._tree.item(iid, tags=("unread",))
            self._tree.tag_configure("unread", font=("Helvetica", 10, "bold"))
            unread = self._svc.unread_count(user_id)
            self._status_var.set(f"{len(notifs)} notification(s) | {unread} unread")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_select(self, _=None):
        sel = self._tree.selection()
        self._preview.configure(state="normal")
        self._preview.delete("1.0", "end")
        if sel and sel[0] in self._data:
            n = self._data[sel[0]]
            self._preview.insert("1.0", f"{n['title']}\n\n{n['message']}")
        self._preview.configure(state="disabled")

    def _on_mark_read(self):
        sel = self._tree.selection()
        if not sel:
            return
        self._svc.mark_read(int(sel[0]))
        self._load()

    def _on_mark_all_read(self):
        user_id = self._get_user_id()
        if user_id:
            self._svc.mark_all_read(user_id)
            self._load()

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        self._svc.delete_notification(int(sel[0]))
        self._load()
