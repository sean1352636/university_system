"""Reusable cross-system messaging panel.

Embedded inside each per-system Email GUI so users can send and receive
messages between the four education systems without leaving the email screen.

Wraps :class:`InterSystemMessagingService` and exposes Inbox / Sent / Compose
tabs.  This replaces the standalone ``CrossSystemCommunicationsFrame``.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.shared.messaging.messaging_service import InterSystemMessagingService

SYSTEM_NAMES = {
    "university": "University",
    "sixth_form": "Sixth Form College",
    "secondary": "Secondary School",
    "primary": "Primary School",
    "nursery": "Nursery",
}

ALL_SYSTEM_KEYS = ["nursery", "primary", "secondary", "sixth_form", "university"]


class CrossSystemMessagePanel(tk.Frame):
    """Inbox / Sent / Compose UI for messages between education systems."""

    def __init__(self, parent, auth=None, system_key=None, db_path=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._auth = auth
        self._system_key = system_key
        self._svc = InterSystemMessagingService(db_path=db_path)
        self._inbox_data: dict[str, dict] = {}
        self._sent_data: dict[str, dict] = {}
        self._staff_map: dict[str, dict] = {}
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # auth helpers
    # ------------------------------------------------------------------

    def _user_id(self):
        # Cross-system messaging IDs are auth.db users.id values (what
        # get_staff_list returns). University auth stores a legacy id in
        # current_user["id"] which does NOT match — prefer shared_auth_id
        # so sender/recipient ids line up between INSERT and SELECT.
        cu = self._auth if isinstance(self._auth, dict) else getattr(self._auth, "current_user", None)
        if isinstance(cu, dict):
            return cu.get("shared_auth_id") or cu.get("user_id") or cu.get("id")
        return None

    def _user_name(self):
        if isinstance(self._auth, dict):
            return self._auth.get("display_name") or self._auth.get("username", "")
        if hasattr(self._auth, "current_user") and self._auth.current_user:
            cu = self._auth.current_user
            return cu.get("display_name") or cu.get("username", "")
        return ""

    def _system(self):
        if self._system_key:
            return self._system_key
        if isinstance(self._auth, dict):
            return self._auth.get("system_key", "")
        if hasattr(self._auth, "current_user") and self._auth.current_user:
            return self._auth.current_user.get("system_key", "")
        return ""

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        inbox_tab = tk.Frame(nb, bg="#ecf0f1")
        nb.add(inbox_tab, text="Inbox")
        self._build_inbox_tab(inbox_tab)

        sent_tab = tk.Frame(nb, bg="#ecf0f1")
        nb.add(sent_tab, text="Sent")
        self._build_sent_tab(sent_tab)

        compose_tab = tk.Frame(nb, bg="#ecf0f1")
        nb.add(compose_tab, text="Compose")
        self._build_compose_tab(compose_tab)

    def _build_inbox_tab(self, parent):
        toolbar = tk.Frame(parent, bg="#ecf0f1", pady=5)
        toolbar.pack(fill="x", padx=8)
        ttk.Button(toolbar, text="Refresh", command=self._refresh_inbox).pack(side="left", padx=4)
        ttk.Button(toolbar, text="View", command=self._view_inbox_msg).pack(side="left", padx=4)
        self._inbox_status = tk.StringVar(value="")
        tk.Label(toolbar, textvariable=self._inbox_status, bg="#ecf0f1",
                 font=("Helvetica", 9, "bold"), fg="#e74c3c").pack(side="right", padx=8)

        tree_frame = tk.Frame(parent)
        tree_frame.pack(fill="both", expand=True, padx=8, pady=4)

        cols = ("from", "system", "subject", "student", "date", "status")
        self._inbox_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, hd, w in [
            ("from", "From", 130),
            ("system", "System", 120),
            ("subject", "Subject", 200),
            ("student", "Student", 120),
            ("date", "Date", 130),
            ("status", "Status", 70),
        ]:
            self._inbox_tree.heading(col, text=hd)
            self._inbox_tree.column(col, width=w,
                                    anchor="center" if col in ("date", "status") else "w")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._inbox_tree.yview)
        self._inbox_tree.configure(yscrollcommand=vsb.set)
        self._inbox_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._inbox_tree.bind("<Double-1>", lambda _e: self._view_inbox_msg())

        detail = tk.LabelFrame(parent, text="Message", bg="#ecf0f1", padx=8, pady=4)
        detail.pack(fill="x", padx=8, pady=(0, 8))
        self._inbox_detail = tk.Text(detail, height=5, state="disabled",
                                     font=("Helvetica", 10), wrap="word")
        self._inbox_detail.pack(fill="x")

    def _build_sent_tab(self, parent):
        toolbar = tk.Frame(parent, bg="#ecf0f1", pady=5)
        toolbar.pack(fill="x", padx=8)
        ttk.Button(toolbar, text="Refresh", command=self._refresh_sent).pack(side="left", padx=4)
        ttk.Button(toolbar, text="View", command=self._view_sent_msg).pack(side="left", padx=4)

        tree_frame = tk.Frame(parent)
        tree_frame.pack(fill="both", expand=True, padx=8, pady=4)

        cols = ("to", "system", "subject", "student", "date", "read")
        self._sent_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, hd, w in [
            ("to", "To", 130),
            ("system", "System", 120),
            ("subject", "Subject", 200),
            ("student", "Student", 120),
            ("date", "Date", 130),
            ("read", "Read?", 70),
        ]:
            self._sent_tree.heading(col, text=hd)
            self._sent_tree.column(col, width=w,
                                   anchor="center" if col in ("date", "read") else "w")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._sent_tree.yview)
        self._sent_tree.configure(yscrollcommand=vsb.set)
        self._sent_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._sent_tree.bind("<Double-1>", lambda _e: self._view_sent_msg())

        detail = tk.LabelFrame(parent, text="Message", bg="#ecf0f1", padx=8, pady=4)
        detail.pack(fill="x", padx=8, pady=(0, 8))
        self._sent_detail = tk.Text(detail, height=5, state="disabled",
                                    font=("Helvetica", 10), wrap="word")
        self._sent_detail.pack(fill="x")

    def _build_compose_tab(self, parent):
        frm = tk.Frame(parent, bg="#ecf0f1", padx=15, pady=10)
        frm.pack(fill="both", expand=True)
        pad = {"padx": 8, "pady": 4}
        row = 0

        tk.Label(frm, text="To System:", font=("Helvetica", 10, "bold"),
                 bg="#ecf0f1").grid(row=row, column=0, sticky="w", **pad)
        self._sys_var = tk.StringVar()
        self._sys_combo = ttk.Combobox(
            frm, textvariable=self._sys_var,
            values=ALL_SYSTEM_KEYS, state="readonly", width=20,
        )
        self._sys_combo.grid(row=row, column=1, sticky="w", **pad)
        self._sys_combo.bind("<<ComboboxSelected>>", self._on_system_changed)
        row += 1

        tk.Label(frm, text="Recipient:", font=("Helvetica", 10, "bold"),
                 bg="#ecf0f1").grid(row=row, column=0, sticky="w", **pad)
        self._recip_var = tk.StringVar()
        self._recip_combo = ttk.Combobox(
            frm, textvariable=self._recip_var, state="readonly", width=35,
        )
        self._recip_combo.grid(row=row, column=1, sticky="w", **pad)
        row += 1

        tk.Label(frm, text="Student (optional):", font=("Helvetica", 10, "bold"),
                 bg="#ecf0f1").grid(row=row, column=0, sticky="w", **pad)
        self._student_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self._student_var, width=37).grid(
            row=row, column=1, sticky="w", **pad)
        row += 1

        tk.Label(frm, text="Subject:", font=("Helvetica", 10, "bold"),
                 bg="#ecf0f1").grid(row=row, column=0, sticky="w", **pad)
        self._subject_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self._subject_var, width=45).grid(
            row=row, column=1, sticky="w", **pad)
        row += 1

        tk.Label(frm, text="Message:", font=("Helvetica", 10, "bold"),
                 bg="#ecf0f1").grid(row=row, column=0, sticky="nw", **pad)
        self._body_text = tk.Text(frm, height=10, width=50, font=("Helvetica", 10))
        self._body_text.grid(row=row, column=1, **pad)
        row += 1

        btn_frame = tk.Frame(frm, bg="#ecf0f1")
        btn_frame.grid(row=row, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Send", command=self._send).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Clear", command=self._clear).pack(side="left", padx=5)

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------

    def refresh(self):
        self._refresh_inbox()
        self._refresh_sent()

    def _refresh_inbox(self):
        uid = self._user_id()
        if not uid:
            return
        self._inbox_tree.delete(*self._inbox_tree.get_children())
        self._inbox_data.clear()
        try:
            msgs = self._svc.get_inbox(uid)
            unread = 0
            for m in msgs:
                iid = str(m["id"])
                status = "Unread" if not m["is_read"] else "Read"
                if not m["is_read"]:
                    unread += 1
                sys_disp = SYSTEM_NAMES.get(m.get("sender_system", ""), m.get("sender_system", ""))
                self._inbox_tree.insert("", "end", iid=iid, values=(
                    m.get("sender_name", ""),
                    sys_disp,
                    m.get("subject", ""),
                    m.get("student_name", ""),
                    (m.get("created_at") or "")[:16],
                    status,
                ))
                self._inbox_data[iid] = m
            self._inbox_status.set(f"{unread} unread" if unread else "")
        except Exception as e:
            self._inbox_status.set(f"Error: {e}")

    def _refresh_sent(self):
        uid = self._user_id()
        if not uid:
            return
        self._sent_tree.delete(*self._sent_tree.get_children())
        self._sent_data.clear()
        try:
            msgs = self._svc.get_sent(uid)
            for m in msgs:
                iid = str(m["id"])
                read = "Yes" if m["is_read"] else "No"
                sys_disp = SYSTEM_NAMES.get(m.get("recipient_system", ""), m.get("recipient_system", ""))
                self._sent_tree.insert("", "end", iid=iid, values=(
                    m.get("recipient_name", ""),
                    sys_disp,
                    m.get("subject", ""),
                    m.get("student_name", ""),
                    (m.get("created_at") or "")[:16],
                    read,
                ))
                self._sent_data[iid] = m
        except Exception:
            pass

    def _view_inbox_msg(self):
        sel = self._inbox_tree.selection()
        if not sel:
            return
        msg = self._inbox_data.get(sel[0])
        if not msg:
            return
        self._inbox_detail.config(state="normal")
        self._inbox_detail.delete("1.0", "end")
        header = (
            f"From: {msg.get('sender_name', '')} "
            f"({SYSTEM_NAMES.get(msg.get('sender_system', ''), '')})\n"
            f"Subject: {msg.get('subject', '')}\n"
            f"Student: {msg.get('student_name', 'N/A')}\n"
            f"Date: {msg.get('created_at', '')}\n"
            f"---\n"
        )
        self._inbox_detail.insert("end", header + (msg.get("body") or ""))
        self._inbox_detail.config(state="disabled")
        if not msg.get("is_read"):
            self._svc.mark_read(msg["id"])
            self._refresh_inbox()

    def _view_sent_msg(self):
        sel = self._sent_tree.selection()
        if not sel:
            return
        msg = self._sent_data.get(sel[0])
        if not msg:
            return
        self._sent_detail.config(state="normal")
        self._sent_detail.delete("1.0", "end")
        header = (
            f"To: {msg.get('recipient_name', '')} "
            f"({SYSTEM_NAMES.get(msg.get('recipient_system', ''), '')})\n"
            f"Subject: {msg.get('subject', '')}\n"
            f"Student: {msg.get('student_name', 'N/A')}\n"
            f"Date: {msg.get('created_at', '')}\n"
            f"---\n"
        )
        self._sent_detail.insert("end", header + (msg.get("body") or ""))
        self._sent_detail.config(state="disabled")

    def _on_system_changed(self, _event=None):
        system = self._sys_var.get()
        if not system:
            return
        try:
            staff = self._svc.get_staff_list(system)
            self._staff_map.clear()
            labels = []
            for s in staff:
                label = f"{s['display_name'] or s['username']} ({s['role']})"
                labels.append(label)
                self._staff_map[label] = s
            self._recip_combo["values"] = labels
            self._recip_combo.set(labels[0] if labels else "")
        except Exception:
            self._recip_combo["values"] = []
            self._recip_combo.set("")

    def _send(self):
        uid = self._user_id()
        if not uid:
            messagebox.showerror("Error", "No user session.", parent=self)
            return
        recipient = self._staff_map.get(self._recip_var.get())
        if not recipient:
            messagebox.showwarning("Validation", "Please select a recipient.", parent=self)
            return
        subject = self._subject_var.get().strip()
        if not subject:
            messagebox.showwarning("Validation", "Subject is required.", parent=self)
            return
        body = self._body_text.get("1.0", "end").strip()
        try:
            msg = self._svc.send_message(
                sender_id=uid,
                sender_system=self._system(),
                sender_name=self._user_name(),
                recipient_id=recipient["id"],
                recipient_system=self._sys_var.get(),
                recipient_name=recipient.get("display_name") or recipient.get("username", ""),
                student_name=self._student_var.get().strip(),
                student_id="",
                subject=subject,
                body=body,
            )
            if msg:
                messagebox.showinfo("Sent", "Message sent successfully.", parent=self)
                self._clear()
                self._refresh_sent()
            else:
                messagebox.showerror("Error", "Failed to send message.", parent=self)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _clear(self):
        self._subject_var.set("")
        self._student_var.set("")
        self._body_text.delete("1.0", "end")
