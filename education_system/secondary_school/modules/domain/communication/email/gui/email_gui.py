"""Internal email GUI — inbox, sent, compose, and read views."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.secondary_school.modules.domain.communication.email.services.email_service import EmailService
from education_system.secondary_school.core.exceptions import EmailError

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class _ComposeDialog(tk.Toplevel):
    """Dialog to compose and send an email."""

    def __init__(self, parent, users, reply_to=None):
        super().__init__(parent)
        self.title("Compose Email")
        self.geometry("500x400")
        self.resizable(False, False)
        self.grab_set()
        self.result = None
        self._users = users
        self._reply_to = reply_to
        self._build_ui()
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        self.geometry(f"+{px - self.winfo_width() // 2}+{py - self.winfo_height() // 2}")

    def _build_ui(self):
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(self, padx=15, pady=10)
        c.pack(fill="both", expand=True)

        # To
        tk.Label(c, text="To:", font=("Helvetica", 9, "bold")).grid(
            row=0, column=0, sticky="w", **pad)
        user_labels = [f"{u['username']} ({u['role']})" for u in self._users]
        self._to_var = tk.StringVar()
        self._to_combo = ttk.Combobox(c, textvariable=self._to_var,
                                      values=user_labels, state="readonly", width=40)
        self._to_combo.grid(row=0, column=1, sticky="ew", **pad)

        # Pre-select recipient for replies
        if self._reply_to:
            for i, u in enumerate(self._users):
                if u["id"] == self._reply_to.get("sender_id"):
                    self._to_combo.current(i)
                    break

        # Subject
        tk.Label(c, text="Subject:", font=("Helvetica", 9, "bold")).grid(
            row=1, column=0, sticky="w", **pad)
        self._subject_var = tk.StringVar()
        if self._reply_to:
            subj = self._reply_to.get("subject", "")
            if not subj.startswith("Re: "):
                subj = f"Re: {subj}"
            self._subject_var.set(subj)
        ttk.Entry(c, textvariable=self._subject_var, width=43).grid(
            row=1, column=1, sticky="ew", **pad)

        # Body
        tk.Label(c, text="Message:", font=("Helvetica", 9, "bold")).grid(
            row=2, column=0, sticky="nw", **pad)
        self._body_text = tk.Text(c, width=43, height=12, wrap="word",
                                  font=("Helvetica", 10))
        self._body_text.grid(row=2, column=1, sticky="nsew", **pad)

        if self._reply_to:
            original = self._reply_to.get("body", "")
            sender = self._reply_to.get("sender_name", "")
            self._body_text.insert("1.0",
                                   f"\n\n--- Original message from {sender} ---\n{original}")
            self._body_text.mark_set("insert", "1.0")

        c.grid_rowconfigure(2, weight=1)
        c.grid_columnconfigure(1, weight=1)

        # Buttons
        btn = tk.Frame(c)
        btn.grid(row=3, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn, text="Send", command=self._on_send).pack(side="left", padx=5)
        ttk.Button(btn, text="Cancel", command=self.destroy).pack(side="left", padx=5)

    def _on_send(self):
        to_val = self._to_var.get()
        if not to_val:
            messagebox.showwarning("Validation", "Select a recipient.")
            return

        idx = self._to_combo.current()
        if idx < 0:
            messagebox.showwarning("Validation", "Select a recipient.")
            return

        self.result = {
            "recipient_id": self._users[idx]["id"],
            "subject": self._subject_var.get().strip(),
            "body": self._body_text.get("1.0", "end").strip(),
        }
        self.destroy()


class EmailFrame(tk.Frame):
    """Email module: inbox, sent, compose, read."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = EmailService(db_path)
        self._current_view = "inbox"
        self._build_ui()

    def _user_id(self):
        return self._auth["id"] if self._auth else None

    def _build_ui(self):
        self.configure(bg=MAIN_BG)

        # Header
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        self._header_label = tk.Label(header, text="Email - Inbox",
                                      font=("Helvetica", 15, "bold"),
                                      bg=HEADER_BG, fg="white")
        self._header_label.pack(side="left", padx=20, pady=10)

        self._unread_label = tk.Label(header, text="", font=("Helvetica", 10),
                                      bg=HEADER_BG, fg="#f9e79f")
        self._unread_label.pack(side="right", padx=20)

        # Toolbar
        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Compose", command=self._on_compose).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Inbox", command=self._show_inbox).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Sent", command=self._show_sent).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Refresh", command=self._load_emails).pack(side="left", padx=4)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(toolbar, text="Read", command=self._on_read).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Reply", command=self._on_reply).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)

        # Email list
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 5))

        self._tree = ttk.Treeview(tree_frame,
                                  columns=("status", "from_to", "subject", "date"),
                                  show="headings", selectmode="browse")
        self._tree.heading("status", text="")
        self._tree.heading("from_to", text="From")
        self._tree.heading("subject", text="Subject")
        self._tree.heading("date", text="Date")

        self._tree.column("status", width=30, anchor="center")
        self._tree.column("from_to", width=140, anchor="w")
        self._tree.column("subject", width=350, anchor="w")
        self._tree.column("date", width=130, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._tree.bind("<Double-1>", lambda _: self._on_read())

        # Preview pane
        preview_frame = tk.LabelFrame(self, text="Preview", bg=MAIN_BG,
                                      font=("Helvetica", 9))
        preview_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        self._preview_text = tk.Text(preview_frame, height=8, wrap="word",
                                     font=("Helvetica", 10), state="disabled",
                                     bg="white", bd=0)
        self._preview_text.pack(fill="both", expand=True, padx=5, pady=5)

        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg=MAIN_BG, anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

        # Store email data keyed by tree iid
        self._email_data: dict[str, dict] = {}

    def refresh(self):
        self._load_emails()

    def _show_inbox(self):
        self._current_view = "inbox"
        self._header_label.configure(text="Email - Inbox")
        self._tree.heading("from_to", text="From")
        self._load_emails()

    def _show_sent(self):
        self._current_view = "sent"
        self._header_label.configure(text="Email - Sent")
        self._tree.heading("from_to", text="To")
        self._load_emails()

    def _load_emails(self):
        self._tree.delete(*self._tree.get_children())
        self._email_data.clear()
        self._clear_preview()

        uid = self._user_id()
        if not uid:
            return

        try:
            if self._current_view == "inbox":
                emails = self._svc.get_inbox(uid)
            else:
                emails = self._svc.get_sent(uid)

            for e in emails:
                iid = str(e["id"])
                if self._current_view == "inbox":
                    status = "" if e["is_read"] else "\u2709"  # envelope
                    from_to = e.get("sender_name", "")
                else:
                    status = ""
                    from_to = e.get("recipient_name", "")

                date_str = e["sent_at"][:16] if e.get("sent_at") else ""
                self._tree.insert("", "end", iid=iid, values=(
                    status, from_to, e["subject"], date_str,
                ))
                # Bold unread in inbox
                if self._current_view == "inbox" and not e["is_read"]:
                    self._tree.item(iid, tags=("unread",))

                self._email_data[iid] = e

            self._tree.tag_configure("unread", font=("Helvetica", 10, "bold"))

            # Update unread count
            unread = self._svc.get_unread_count(uid)
            if unread > 0:
                self._unread_label.configure(text=f"{unread} unread")
            else:
                self._unread_label.configure(text="")

            self._status_var.set(f"{len(emails)} email(s)")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_select(self, _event=None):
        sel = self._tree.selection()
        if not sel:
            self._clear_preview()
            return

        email = self._email_data.get(sel[0])
        if not email:
            return

        # Mark as read if inbox
        if self._current_view == "inbox" and not email["is_read"]:
            self._svc.mark_read(email["id"], self._user_id())
            email["is_read"] = 1
            self._tree.set(sel[0], "status", "")
            self._tree.item(sel[0], tags=())
            # Refresh unread count
            unread = self._svc.get_unread_count(self._user_id())
            self._unread_label.configure(text=f"{unread} unread" if unread else "")

        # Show preview
        if self._current_view == "inbox":
            header = f"From: {email.get('sender_name', '')}"
        else:
            header = f"To: {email.get('recipient_name', '')}"
        date_str = email["sent_at"][:16] if email.get("sent_at") else ""

        self._preview_text.configure(state="normal")
        self._preview_text.delete("1.0", "end")
        self._preview_text.insert("1.0",
                                  f"{header}\n"
                                  f"Subject: {email['subject']}\n"
                                  f"Date: {date_str}\n"
                                  f"{'─' * 50}\n\n"
                                  f"{email.get('body', '')}")
        self._preview_text.configure(state="disabled")

    def _clear_preview(self):
        self._preview_text.configure(state="normal")
        self._preview_text.delete("1.0", "end")
        self._preview_text.configure(state="disabled")

    def _on_compose(self):
        uid = self._user_id()
        if not uid:
            return
        users = self._svc.get_all_users(exclude_id=uid)
        if not users:
            messagebox.showwarning("Warning", "No other users in the system.")
            return

        dlg = _ComposeDialog(self, users)
        self.wait_window(dlg)
        if dlg.result is None:
            return

        try:
            self._svc.send(
                sender_id=uid,
                recipient_id=dlg.result["recipient_id"],
                subject=dlg.result["subject"],
                body=dlg.result["body"],
            )
            messagebox.showinfo("Sent", "Email sent successfully.")
            self._load_emails()
        except EmailError as exc:
            messagebox.showerror("Error", str(exc))

    def _on_read(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select an email first.")
            return

        email = self._email_data.get(sel[0])
        if not email:
            return

        # Open in a read-only dialog
        uid = self._user_id()
        full = self._svc.get_email(email["id"], uid)
        if not full:
            return

        if self._current_view == "inbox" and not full["is_read"]:
            self._svc.mark_read(full["id"], uid)

        dlg = tk.Toplevel(self)
        dlg.title(f"Email: {full['subject']}")
        dlg.geometry("550x400")

        info = tk.Frame(dlg, padx=15, pady=10, bg="white")
        info.pack(fill="x")

        tk.Label(info, text=f"From:  {full.get('sender_name', '')}",
                 font=("Helvetica", 10), bg="white", anchor="w").pack(fill="x")
        tk.Label(info, text=f"To:  {full.get('recipient_name', '')}",
                 font=("Helvetica", 10), bg="white", anchor="w").pack(fill="x")
        tk.Label(info, text=f"Subject:  {full['subject']}",
                 font=("Helvetica", 10, "bold"), bg="white", anchor="w").pack(fill="x")
        date_str = full["sent_at"][:16] if full.get("sent_at") else ""
        tk.Label(info, text=f"Date:  {date_str}",
                 font=("Helvetica", 9), bg="white", fg="#7f8c8d",
                 anchor="w").pack(fill="x")

        ttk.Separator(dlg).pack(fill="x")

        body = tk.Text(dlg, wrap="word", font=("Helvetica", 10),
                       padx=15, pady=10, state="normal", bd=0)
        body.pack(fill="both", expand=True)
        body.insert("1.0", full.get("body", ""))
        body.configure(state="disabled")

        btn_frame = tk.Frame(dlg, pady=8)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="Reply", command=lambda: [dlg.destroy(), self._reply_to_email(full)]).pack(side="left", padx=15)
        ttk.Button(btn_frame, text="Close", command=dlg.destroy).pack(side="right", padx=15)

        self._load_emails()

    def _on_reply(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select an email to reply to.")
            return
        email = self._email_data.get(sel[0])
        if email:
            self._reply_to_email(email)

    def _reply_to_email(self, email: dict):
        uid = self._user_id()
        if not uid:
            return
        users = self._svc.get_all_users(exclude_id=uid)
        if not users:
            return

        dlg = _ComposeDialog(self, users, reply_to=email)
        self.wait_window(dlg)
        if dlg.result is None:
            return

        try:
            self._svc.send(
                sender_id=uid,
                recipient_id=dlg.result["recipient_id"],
                subject=dlg.result["subject"],
                body=dlg.result["body"],
            )
            messagebox.showinfo("Sent", "Reply sent successfully.")
            self._load_emails()
        except EmailError as exc:
            messagebox.showerror("Error", str(exc))

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select an email first.")
            return
        if not messagebox.askyesno("Confirm", "Delete this email?"):
            return

        email = self._email_data.get(sel[0])
        if email:
            self._svc.delete_email(email["id"], self._user_id())
            self._load_emails()
