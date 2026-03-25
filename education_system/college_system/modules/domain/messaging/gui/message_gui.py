"""Messaging GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.messaging.services.message_service import MessageService
from education_system.college_system.core.i18n import t


class _ComposeDialog(tk.Toplevel):
    """Modal dialog for composing a new message."""

    def __init__(self, parent, users: list[dict], **kwargs):
        super().__init__(parent, **kwargs)
        self.title(t("messaging.compose_message"))
        self.geometry("500x400")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result: dict | None = None
        self._users = users
        self._user_map: dict[str, int] = {}

        self._build_ui()
        self.wait_window()

    def _build_ui(self):
        pad = {"padx": 15, "pady": 5}

        # Recipient
        tk.Label(self, text=t("messaging.to_colon")).grid(row=0, column=0, sticky="w", **pad)
        self._recipient_var = tk.StringVar()
        combo = ttk.Combobox(self, textvariable=self._recipient_var,
                             width=45, state="readonly")

        values = []
        for u in self._users:
            label = f"{u['username']} ({u['display_name']}, {u['role']})"
            values.append(label)
            self._user_map[label] = u["id"]
        combo["values"] = values
        combo.grid(row=0, column=1, sticky="ew", **pad)

        # Subject
        tk.Label(self, text=t("messaging.subject_colon")).grid(row=1, column=0, sticky="w", **pad)
        self._subject_var = tk.StringVar()
        ttk.Entry(self, textvariable=self._subject_var, width=47).grid(
            row=1, column=1, sticky="ew", **pad)

        # Body
        tk.Label(self, text=t("messaging.message_colon")).grid(row=2, column=0, sticky="nw", **pad)
        self._body_text = tk.Text(self, width=45, height=12, wrap="word")
        self._body_text.grid(row=2, column=1, sticky="nsew", **pad)

        # Buttons
        btn_frame = tk.Frame(self)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text=t("messaging.send"), command=self._send).pack(
            side="left", padx=10)
        ttk.Button(btn_frame, text=t("common.cancel"), command=self.destroy).pack(
            side="left", padx=10)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

    def _send(self):
        recipient_label = self._recipient_var.get()
        if not recipient_label:
            messagebox.showwarning(t("common.warning"), t("messaging.select_recipient"),
                                   parent=self)
            return
        subject = self._subject_var.get().strip()
        if not subject:
            messagebox.showwarning(t("common.warning"), t("messaging.subject_required"),
                                   parent=self)
            return

        self.result = {
            "recipient_id": self._user_map[recipient_label],
            "subject": subject,
            "body": self._body_text.get("1.0", "end-1c"),
        }
        self.destroy()


class MessageFrame(tk.Frame):
    """Internal messaging frame with inbox/sent views and compose dialog."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = MessageService(db_path)
        self._view = "inbox"  # "inbox" or "sent"
        self._messages: dict[int, dict] = {}
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("messaging.title"),
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._unread_label = tk.StringVar(value="Unread: --")
        tk.Label(header, textvariable=self._unread_label,
                 font=("Helvetica", 11), bg="#2c3e50", fg="#bdc3c7"
                 ).pack(side="right", padx=20, pady=10)

        # Toolbar
        toolbar = tk.Frame(self, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=20, pady=(10, 0))

        ttk.Button(toolbar, text=t("messaging.compose"), command=self._compose).pack(
            side="left", padx=(0, 10))

        self._inbox_btn = ttk.Button(toolbar, text=t("messaging.inbox"),
                                     command=self._show_inbox)
        self._inbox_btn.pack(side="left", padx=2)

        self._sent_btn = ttk.Button(toolbar, text=t("messaging.sent"),
                                    command=self._show_sent)
        self._sent_btn.pack(side="left", padx=2)

        ttk.Button(toolbar, text=t("common.delete"), command=self._delete).pack(
            side="left", padx=10)
        ttk.Button(toolbar, text=t("common.export_csv", default="Export CSV"),
                   command=self._export_csv).pack(side="right", padx=(0, 10))
        ttk.Button(toolbar, text=t("common.refresh"),
                   command=self._load_messages).pack(side="right")

        # Treeview
        tree_frame = tk.Frame(self, bg="#ecf0f1")
        tree_frame.pack(fill="both", expand=True, padx=20, pady=10)

        cols = ("id", "from_to", "subject", "read", "date")
        self._tree = ttk.Treeview(tree_frame, columns=cols,
                                  show="headings", height=12)
        self._tree.heading("id", text="ID")
        self._tree.heading("from_to", text="From")
        self._tree.heading("subject", text="Subject")
        self._tree.heading("read", text="Read")
        self._tree.heading("date", text="Date")

        self._tree.column("id", width=40)
        self._tree.column("from_to", width=150)
        self._tree.column("subject", width=250)
        self._tree.column("read", width=50)
        self._tree.column("date", width=150)

        scroll = ttk.Scrollbar(tree_frame, orient="vertical",
                               command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        self._tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # Detail pane
        detail_frame = tk.LabelFrame(self, text=t("messaging.message_label"), bg="#ecf0f1",
                                     padx=10, pady=5)
        detail_frame.pack(fill="x", padx=20, pady=(0, 10))

        self._detail_var = tk.StringVar(value="Select a message to view.")
        tk.Label(detail_frame, textvariable=self._detail_var, bg="#ecf0f1",
                 wraplength=600, justify="left").pack(fill="x")

    # ------------------------------------------------------------------
    # View switching
    # ------------------------------------------------------------------

    def _show_inbox(self):
        self._view = "inbox"
        self._tree.heading("from_to", text="From")
        self._load_messages()

    def _show_sent(self):
        self._view = "sent"
        self._tree.heading("from_to", text="To")
        self._load_messages()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def refresh(self):
        self._load_messages()

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

    def _load_messages(self):
        self._tree.delete(*self._tree.get_children())
        self._detail_var.set("Select a message to view.")
        try:
            user_id = self._get_user_id()
            if not user_id:
                return
            unread = self._svc.count_unread(user_id)
            self._unread_label.set(f"Unread: {unread}")

            if self._view == "inbox":
                messages = self._svc.get_inbox(user_id)
            else:
                messages = self._svc.get_sent(user_id)

            self._messages = {m["id"]: m for m in messages}

            for m in messages:
                if self._view == "inbox":
                    name = m.get("sender_name", "?")
                    read_str = "Yes" if m["is_read"] else "No"
                else:
                    name = m.get("recipient_name", "?")
                    read_str = "-"

                self._tree.insert("", "end", iid=str(m["id"]), values=(
                    m["id"], name, m["subject"], read_str,
                    m["created_at"][:19],
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_select(self, _event):
        sel = self._tree.selection()
        if not sel:
            return
        mid = int(sel[0])
        try:
            user_id = self._get_user_id()
            if not user_id:
                return
            msg = self._svc.get_message(mid, user_id)
            if msg:
                body = msg.get("body") or "(no body)"
                header = (f"From: {msg.get('sender_name', '?')}  |  "
                          f"To: {msg.get('recipient_name', '?')}  |  "
                          f"{msg['created_at'][:19]}")
                self._detail_var.set(f"{header}\n\n{body}")
                # Refresh list to update read status
                if self._view == "inbox":
                    self._load_messages()
                    # Re-select the item
                    if self._tree.exists(str(mid)):
                        self._tree.selection_set(str(mid))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _compose(self):
        try:
            user_id = self._get_user_id()
            if not user_id:
                messagebox.showwarning(t("common.warning"), "Not logged in.")
                return
            users = [u for u in self._svc.get_all_users() if u["id"] != user_id]
            dlg = _ComposeDialog(self, users)
            if dlg.result:
                self._svc.send_message(
                    sender_id=user_id,
                    recipient_id=dlg.result["recipient_id"],
                    subject=dlg.result["subject"],
                    body=dlg.result["body"],
                )
                messagebox.showinfo(t("common.success"), t("messaging.message_sent"))
                self._load_messages()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._tree, "messages.csv")

    def _delete(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning(t("common.warning"), t("messaging.select_message_first"))
            return
        if not messagebox.askyesno(t("common.confirm_delete"), t("messaging.confirm_delete_message")):
            return
        try:
            mid = int(sel[0])
            user_id = self._get_user_id()
            if not user_id:
                return
            self._svc.delete_message(mid, user_id)
            self._load_messages()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
