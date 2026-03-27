"""Unified cross-system communications GUI – notifications + messaging in one frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.shared.notifications.service import CrossSystemNotificationService
from education_system.shared.messaging.messaging_service import InterSystemMessagingService

SYSTEM_NAMES = {
    "university": "University",
    "college": "Sixth Form College",
    "school": "Secondary School",
    "primary": "Primary School",
}

ALL_SYSTEMS_KEYS = ["primary", "school", "college", "university"]


class CrossSystemCommunicationsFrame(tk.Frame):
    """Unified frame for cross-system notifications and inter-system messaging."""

    def __init__(self, parent, db_path=None, auth=None, system_key=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._system_key = system_key
        self._notif_svc = CrossSystemNotificationService()
        self._msg_svc = InterSystemMessagingService(db_path=db_path)
        self._inbox_data = {}
        self._sent_data = {}
        self._staff_map = {}
        self._build_ui()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _get_user_id(self):
        if isinstance(self._auth, dict):
            return self._auth.get("user_id") or self._auth.get("id")
        if hasattr(self._auth, "current_user") and self._auth.current_user:
            return self._auth.current_user.get("user_id") or self._auth.current_user.get("id")
        return None

    def _get_user_name(self):
        if isinstance(self._auth, dict):
            return self._auth.get("display_name") or self._auth.get("username", "")
        if hasattr(self._auth, "current_user") and self._auth.current_user:
            return self._auth.current_user.get("display_name") or self._auth.current_user.get("username", "")
        return ""

    def _get_system(self):
        if self._system_key:
            return self._system_key
        if isinstance(self._auth, dict):
            return self._auth.get("system_key", "")
        if hasattr(self._auth, "current_user") and self._auth.current_user:
            return self._auth.current_user.get("system_key", "")
        return ""

    def _get_role(self):
        if isinstance(self._auth, dict):
            return self._auth.get("role", "")
        if hasattr(self._auth, "current_user") and self._auth.current_user:
            return self._auth.current_user.get("role", "")
        return ""

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
            header, text="Cross-System Communications",
            font=("Helvetica", 15, "bold"), bg="#1a5276", fg="white",
        ).pack(side="left", padx=20, pady=10)

        self._badge_var = tk.StringVar(value="")
        tk.Label(
            header, textvariable=self._badge_var,
            font=("Helvetica", 10, "bold"), bg="#1a5276", fg="#f39c12",
        ).pack(side="right", padx=20, pady=10)

        # Notebook tabs
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        # --- Notifications tab ---
        notif_frame = tk.Frame(self._notebook, bg="#ecf0f1")
        self._notebook.add(notif_frame, text="Notifications")
        self._build_notifications_tab(notif_frame)

        # --- Inbox tab ---
        inbox_frame = tk.Frame(self._notebook, bg="#ecf0f1")
        self._notebook.add(inbox_frame, text="Inbox")
        self._build_inbox_tab(inbox_frame)

        # --- Sent tab ---
        sent_frame = tk.Frame(self._notebook, bg="#ecf0f1")
        self._notebook.add(sent_frame, text="Sent")
        self._build_sent_tab(sent_frame)

        # --- Compose tab ---
        compose_frame = tk.Frame(self._notebook, bg="#ecf0f1")
        self._notebook.add(compose_frame, text="Compose")
        self._build_compose_tab(compose_frame)

    # ------------------------------------------------------------------
    # Notifications tab
    # ------------------------------------------------------------------

    def _build_notifications_tab(self, parent):
        toolbar = tk.Frame(parent, bg="#ecf0f1", pady=5)
        toolbar.pack(fill="x", padx=10)
        ttk.Button(toolbar, text="Refresh", command=self._refresh_notifications).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Mark All Read", command=self._mark_all_read).pack(side="left", padx=4)

        role = self._get_role()
        if role in ("admin", "staff", "teacher", "instructor"):
            ttk.Button(toolbar, text="Send to Role", command=self._send_notification_dialog).pack(side="left", padx=4)

        self._notif_count_var = tk.StringVar(value="")
        tk.Label(toolbar, textvariable=self._notif_count_var, bg="#ecf0f1",
                 font=("Helvetica", 10, "bold"), fg="#e74c3c").pack(side="right", padx=10)

        tree_frame = tk.Frame(parent)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        columns = ("from_system", "sender", "title", "date", "status")
        self._notif_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col, heading, width in [
            ("from_system", "From System", 120),
            ("sender", "Sender", 120),
            ("title", "Title", 250),
            ("date", "Date", 140),
            ("status", "Status", 70),
        ]:
            self._notif_tree.heading(col, text=heading)
            self._notif_tree.column(col, width=width, anchor="center" if col in ("status", "date") else "w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._notif_tree.yview)
        self._notif_tree.configure(yscrollcommand=vsb.set)
        self._notif_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._notif_tree.bind("<Double-1>", self._on_view_notification)

        detail = tk.LabelFrame(parent, text="Message", bg="#ecf0f1", padx=10, pady=5)
        detail.pack(fill="x", padx=10, pady=(0, 10))
        self._notif_detail = tk.Text(detail, height=4, state="disabled",
                                      font=("Helvetica", 10), wrap="word")
        self._notif_detail.pack(fill="x")

    # ------------------------------------------------------------------
    # Inbox tab
    # ------------------------------------------------------------------

    def _build_inbox_tab(self, parent):
        toolbar = tk.Frame(parent, bg="#ecf0f1", pady=5)
        toolbar.pack(fill="x", padx=10)
        ttk.Button(toolbar, text="Refresh", command=self._refresh_inbox).pack(side="left", padx=4)
        ttk.Button(toolbar, text="View Selected", command=self._view_inbox_msg).pack(side="left", padx=4)

        tree_frame = tk.Frame(parent)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        columns = ("from", "system", "subject", "student", "date", "status")
        self._inbox_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col, heading, width in [
            ("from", "From", 130),
            ("system", "System", 120),
            ("subject", "Subject", 200),
            ("student", "Student", 130),
            ("date", "Date", 130),
            ("status", "Status", 70),
        ]:
            self._inbox_tree.heading(col, text=heading)
            self._inbox_tree.column(col, width=width, anchor="center" if col in ("date", "status") else "w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._inbox_tree.yview)
        self._inbox_tree.configure(yscrollcommand=vsb.set)
        self._inbox_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._inbox_tree.bind("<Double-1>", lambda e: self._view_inbox_msg())

        detail = tk.LabelFrame(parent, text="Message", bg="#ecf0f1", padx=10, pady=5)
        detail.pack(fill="x", padx=10, pady=(0, 10))
        self._inbox_detail = tk.Text(detail, height=5, state="disabled",
                                      font=("Helvetica", 10), wrap="word")
        self._inbox_detail.pack(fill="x")

    # ------------------------------------------------------------------
    # Sent tab
    # ------------------------------------------------------------------

    def _build_sent_tab(self, parent):
        toolbar = tk.Frame(parent, bg="#ecf0f1", pady=5)
        toolbar.pack(fill="x", padx=10)
        ttk.Button(toolbar, text="Refresh", command=self._refresh_sent).pack(side="left", padx=4)
        ttk.Button(toolbar, text="View Selected", command=self._view_sent_msg).pack(side="left", padx=4)

        tree_frame = tk.Frame(parent)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        columns = ("to", "system", "subject", "student", "date", "status")
        self._sent_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col, heading, width in [
            ("to", "To", 130),
            ("system", "System", 120),
            ("subject", "Subject", 200),
            ("student", "Student", 130),
            ("date", "Date", 130),
            ("status", "Read?", 70),
        ]:
            self._sent_tree.heading(col, text=heading)
            self._sent_tree.column(col, width=width, anchor="center" if col in ("date", "status") else "w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._sent_tree.yview)
        self._sent_tree.configure(yscrollcommand=vsb.set)
        self._sent_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._sent_tree.bind("<Double-1>", lambda e: self._view_sent_msg())

        detail = tk.LabelFrame(parent, text="Message", bg="#ecf0f1", padx=10, pady=5)
        detail.pack(fill="x", padx=10, pady=(0, 10))
        self._sent_detail = tk.Text(detail, height=5, state="disabled",
                                     font=("Helvetica", 10), wrap="word")
        self._sent_detail.pack(fill="x")

    # ------------------------------------------------------------------
    # Compose tab
    # ------------------------------------------------------------------

    def _build_compose_tab(self, parent):
        frm = tk.Frame(parent, bg="#ecf0f1", padx=15, pady=10)
        frm.pack(fill="both", expand=True)

        pad = {"padx": 8, "pady": 4}
        row = 0

        # Recipient system
        tk.Label(frm, text="Recipient System:", font=("Helvetica", 10, "bold"),
                 bg="#ecf0f1").grid(row=row, column=0, sticky="w", **pad)
        self._compose_system_var = tk.StringVar()
        self._compose_system_combo = ttk.Combobox(
            frm, textvariable=self._compose_system_var,
            values=ALL_SYSTEMS_KEYS, state="readonly", width=20,
        )
        self._compose_system_combo.grid(row=row, column=1, sticky="w", **pad)
        self._compose_system_combo.bind("<<ComboboxSelected>>", self._on_system_changed)
        row += 1

        # Recipient
        tk.Label(frm, text="Recipient:", font=("Helvetica", 10, "bold"),
                 bg="#ecf0f1").grid(row=row, column=0, sticky="w", **pad)
        self._compose_recipient_var = tk.StringVar()
        self._compose_recipient_combo = ttk.Combobox(
            frm, textvariable=self._compose_recipient_var,
            state="readonly", width=30,
        )
        self._compose_recipient_combo.grid(row=row, column=1, sticky="w", **pad)
        row += 1

        # Student name (optional)
        tk.Label(frm, text="Student Name:", font=("Helvetica", 10, "bold"),
                 bg="#ecf0f1").grid(row=row, column=0, sticky="w", **pad)
        self._compose_student_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self._compose_student_var, width=30).grid(row=row, column=1, sticky="w", **pad)
        row += 1

        # Subject
        tk.Label(frm, text="Subject:", font=("Helvetica", 10, "bold"),
                 bg="#ecf0f1").grid(row=row, column=0, sticky="w", **pad)
        self._compose_subject_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self._compose_subject_var, width=40).grid(row=row, column=1, sticky="w", **pad)
        row += 1

        # Body
        tk.Label(frm, text="Message:", font=("Helvetica", 10, "bold"),
                 bg="#ecf0f1").grid(row=row, column=0, sticky="nw", **pad)
        self._compose_body = tk.Text(frm, height=8, width=45, font=("Helvetica", 10))
        self._compose_body.grid(row=row, column=1, **pad)
        row += 1

        # Send button
        btn_frame = tk.Frame(frm, bg="#ecf0f1")
        btn_frame.grid(row=row, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Send", command=self._send_message).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Clear", command=self._clear_compose).pack(side="left", padx=5)

    def _on_system_changed(self, event=None):
        system = self._compose_system_var.get()
        if not system:
            return
        try:
            staff = self._msg_svc.get_staff_list(system)
            self._staff_map.clear()
            display_list = []
            for s in staff:
                label = f"{s['display_name'] or s['username']} ({s['role']})"
                display_list.append(label)
                self._staff_map[label] = s
            self._compose_recipient_combo["values"] = display_list
            if display_list:
                self._compose_recipient_combo.set(display_list[0])
            else:
                self._compose_recipient_combo.set("")
        except Exception:
            self._compose_recipient_combo["values"] = []

    # ------------------------------------------------------------------
    # actions – notifications
    # ------------------------------------------------------------------

    def _refresh_notifications(self):
        user_id = self._get_user_id()
        if not user_id:
            return
        self._notif_tree.delete(*self._notif_tree.get_children())
        try:
            notifs = self._notif_svc.get_all(user_id, self._get_system(), limit=100)
            unread = sum(1 for n in notifs if not n.get("is_read"))
            self._notif_count_var.set(f"{unread} unread" if unread else "")
            for n in notifs:
                system_name = SYSTEM_NAMES.get(n.get("sender_system", ""), n.get("sender_system", ""))
                status = "Unread" if not n.get("is_read") else "Read"
                self._notif_tree.insert("", "end", iid=n["id"], values=(
                    system_name,
                    n.get("sender_name") or "System",
                    n.get("title", ""),
                    (n.get("created_at") or "")[:16],
                    status,
                ))
        except Exception as e:
            self._notif_count_var.set(f"Error: {e}")

    def _on_view_notification(self, event):
        sel = self._notif_tree.selection()
        if not sel:
            return
        nid = int(sel[0])
        user_id = self._get_user_id()
        if not user_id:
            return
        try:
            notifs = self._notif_svc.get_all(user_id, self._get_system(), limit=200)
            notif = next((n for n in notifs if n["id"] == nid), None)
            if notif:
                self._notif_detail.config(state="normal")
                self._notif_detail.delete("1.0", "end")
                self._notif_detail.insert("end", notif.get("message") or "(no message body)")
                self._notif_detail.config(state="disabled")
                if not notif.get("is_read"):
                    self._notif_svc.mark_read(nid)
                    self._refresh_notifications()
        except Exception:
            pass

    def _mark_all_read(self):
        user_id = self._get_user_id()
        if user_id:
            self._notif_svc.mark_all_read(user_id, self._get_system())
            self._refresh_notifications()

    def _send_notification_dialog(self):
        user_id = self._get_user_id()
        if not user_id:
            messagebox.showerror("Error", "No user session.", parent=self)
            return

        dlg = tk.Toplevel(self)
        dlg.title("Send Cross-System Notification")
        dlg.geometry("450x350")
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()

        pad = {"padx": 10, "pady": 5}
        frm = tk.Frame(dlg, padx=15, pady=15)
        frm.pack(fill="both", expand=True)

        system_key = self._get_system()
        tk.Label(frm, text="Target System:", font=("Helvetica", 10, "bold")).grid(
            row=0, column=0, sticky="w", **pad)
        target_systems = [k for k in SYSTEM_NAMES if k != system_key]
        target_var = tk.StringVar(value=target_systems[0] if target_systems else "")
        ttk.Combobox(frm, textvariable=target_var, values=target_systems,
                     state="readonly", width=25).grid(row=0, column=1, **pad)

        tk.Label(frm, text="Target Role:", font=("Helvetica", 10, "bold")).grid(
            row=1, column=0, sticky="w", **pad)
        role_var = tk.StringVar(value="admin")
        ttk.Combobox(frm, textvariable=role_var,
                     values=["admin", "staff", "teacher", "student", "parent"],
                     state="readonly", width=25).grid(row=1, column=1, **pad)

        tk.Label(frm, text="Title:", font=("Helvetica", 10, "bold")).grid(
            row=2, column=0, sticky="w", **pad)
        title_var = tk.StringVar()
        ttk.Entry(frm, textvariable=title_var, width=28).grid(row=2, column=1, **pad)

        tk.Label(frm, text="Message:", font=("Helvetica", 10, "bold")).grid(
            row=3, column=0, sticky="nw", **pad)
        msg_text = tk.Text(frm, height=5, width=30, font=("Helvetica", 10))
        msg_text.grid(row=3, column=1, **pad)

        def _send():
            target = target_var.get()
            role = role_var.get()
            title = title_var.get().strip()
            message = msg_text.get("1.0", "end").strip()
            if not title:
                messagebox.showwarning("Validation", "Title is required.", parent=dlg)
                return
            try:
                count = self._notif_svc.send_to_role(
                    user_id, system_key or "",
                    target, role, title, message,
                )
                messagebox.showinfo("Sent", f"Notification sent to {count} {role}(s) in "
                                    f"{SYSTEM_NAMES.get(target, target)}.", parent=dlg)
                dlg.destroy()
                self._refresh_notifications()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        btn_frame = tk.Frame(frm)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Send", command=_send).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dlg.destroy).pack(side="left", padx=5)

    # ------------------------------------------------------------------
    # actions – messaging
    # ------------------------------------------------------------------

    def _refresh_inbox(self):
        user_id = self._get_user_id()
        if not user_id:
            return
        self._inbox_tree.delete(*self._inbox_tree.get_children())
        self._inbox_data.clear()
        system = self._get_system()
        try:
            msgs = self._msg_svc.get_inbox(user_id, system=system or None)
            unread = 0
            for m in msgs:
                iid = str(m["id"])
                status = "Unread" if not m["is_read"] else "Read"
                if not m["is_read"]:
                    unread += 1
                sys_display = SYSTEM_NAMES.get(m.get("sender_system", ""), m.get("sender_system", ""))
                self._inbox_tree.insert("", "end", iid=iid, values=(
                    m.get("sender_name", ""),
                    sys_display,
                    m.get("subject", ""),
                    m.get("student_name", ""),
                    (m.get("created_at") or "")[:16],
                    status,
                ))
                self._inbox_data[iid] = m
            self._badge_var.set(f"{unread} unread" if unread else "")
        except Exception as e:
            self._badge_var.set(f"Error: {e}")

    def _refresh_sent(self):
        user_id = self._get_user_id()
        if not user_id:
            return
        self._sent_tree.delete(*self._sent_tree.get_children())
        self._sent_data.clear()
        system = self._get_system()
        try:
            msgs = self._msg_svc.get_sent(user_id, system=system or None)
            for m in msgs:
                iid = str(m["id"])
                status = "Yes" if m["is_read"] else "No"
                sys_display = SYSTEM_NAMES.get(m.get("recipient_system", ""), m.get("recipient_system", ""))
                self._sent_tree.insert("", "end", iid=iid, values=(
                    m.get("recipient_name", ""),
                    sys_display,
                    m.get("subject", ""),
                    m.get("student_name", ""),
                    (m.get("created_at") or "")[:16],
                    status,
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
        header_text = (
            f"From: {msg.get('sender_name', '')} ({SYSTEM_NAMES.get(msg.get('sender_system', ''), '')})\n"
            f"Subject: {msg.get('subject', '')}\n"
            f"Student: {msg.get('student_name', 'N/A')}\n"
            f"Date: {msg.get('created_at', '')}\n"
            f"---\n"
        )
        self._inbox_detail.insert("end", header_text + (msg.get("body") or ""))
        self._inbox_detail.config(state="disabled")
        if not msg.get("is_read"):
            self._msg_svc.mark_read(msg["id"])
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
        header_text = (
            f"To: {msg.get('recipient_name', '')} ({SYSTEM_NAMES.get(msg.get('recipient_system', ''), '')})\n"
            f"Subject: {msg.get('subject', '')}\n"
            f"Student: {msg.get('student_name', 'N/A')}\n"
            f"Date: {msg.get('created_at', '')}\n"
            f"---\n"
        )
        self._sent_detail.insert("end", header_text + (msg.get("body") or ""))
        self._sent_detail.config(state="disabled")

    def _send_message(self):
        user_id = self._get_user_id()
        if not user_id:
            messagebox.showerror("Error", "No user session.", parent=self)
            return
        recipient_label = self._compose_recipient_var.get()
        recipient = self._staff_map.get(recipient_label)
        if not recipient:
            messagebox.showwarning("Validation", "Please select a recipient.", parent=self)
            return
        subject = self._compose_subject_var.get().strip()
        if not subject:
            messagebox.showwarning("Validation", "Subject is required.", parent=self)
            return
        body = self._compose_body.get("1.0", "end").strip()
        student_name = self._compose_student_var.get().strip()
        dest_system = self._compose_system_var.get()
        try:
            msg = self._msg_svc.send_message(
                sender_id=user_id,
                sender_system=self._get_system(),
                sender_name=self._get_user_name(),
                recipient_id=recipient["id"],
                recipient_system=dest_system,
                recipient_name=recipient.get("display_name") or recipient.get("username", ""),
                student_name=student_name,
                student_id="",
                subject=subject,
                body=body,
            )
            if msg:
                messagebox.showinfo("Sent", "Message sent successfully.", parent=self)
                self._clear_compose()
                self._refresh_sent()
            else:
                messagebox.showerror("Error", "Failed to send message.", parent=self)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _clear_compose(self):
        self._compose_subject_var.set("")
        self._compose_student_var.set("")
        self._compose_body.delete("1.0", "end")

    # ------------------------------------------------------------------
    # public
    # ------------------------------------------------------------------

    def refresh(self):
        """Refresh all tabs."""
        self._refresh_notifications()
        self._refresh_inbox()
        self._refresh_sent()


# Backward-compatible aliases
InterSystemMessagingFrame = CrossSystemCommunicationsFrame
CrossSystemNotificationsFrame = CrossSystemCommunicationsFrame
