"""Notifications section and its dialogs.

Split out of the former single-file ``superadmin_dashboard.py``; methods are
mixed into :class:`education_system.platform.delivery.gui.superadmin_dashboard.app.SuperAdminDashboard`.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from education_system.platform.delivery.gui.superadmin_dashboard.theme import (
    CONTENT_BG,
    SYSTEM_ORDER,
    TEXT_DARK,
    TEXT_LIGHT,
    TEXT_MUTED,
)


class NotificationsMixin:
    # ------------------------------------------------------------------
    # Section: Cross-System Notifications
    # ------------------------------------------------------------------

    def _build_notifications(self):
        tk.Label(
            self._content_frame,
            text="Cross-System Notifications",
            font=("Segoe UI", 18, "bold"),
            bg=CONTENT_BG,
            fg=TEXT_DARK,
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))

        notif_svc = self._get_notification_service()
        user_id = self.user_info.get("id") or self.user_info.get("user_id")

        # Unread count badge
        unread_count = 0
        if notif_svc and user_id:
            try:
                unread_count = notif_svc.get_unread_count(user_id)
            except Exception:
                pass

        badge_frame = tk.Frame(self._content_frame, bg=CONTENT_BG)
        badge_frame.pack(fill=tk.X, padx=24, pady=(0, 12))

        badge_color = "#e74c3c" if unread_count > 0 else "#27ae60"
        tk.Label(
            badge_frame,
            text=f"  {unread_count} unread  ",
            font=("Segoe UI", 10, "bold"),
            bg=badge_color,
            fg=TEXT_LIGHT,
        ).pack(side=tk.LEFT)

        if unread_count > 0 and notif_svc and user_id:
            mark_btn = tk.Button(
                badge_frame,
                text="Mark All Read",
                font=("Segoe UI", 9),
                bg="#27ae60",
                fg=TEXT_LIGHT,
                relief=tk.FLAT,
                cursor="hand2",
                padx=10,
                command=lambda: self._mark_all_read_and_refresh(notif_svc, user_id),
            )
            mark_btn.pack(side=tk.LEFT, padx=10)

        # Send notification / broadcast buttons
        tk.Button(
            badge_frame, text="Send Notification", font=("Segoe UI", 9),
            bg="#2980b9", fg=TEXT_LIGHT, relief=tk.FLAT, cursor="hand2", padx=10,
            command=lambda: self._show_send_notification_dialog(notif_svc, user_id),
        ).pack(side=tk.LEFT, padx=(10, 4))

        tk.Button(
            badge_frame, text="Broadcast to Role", font=("Segoe UI", 9),
            bg="#8e44ad", fg=TEXT_LIGHT, relief=tk.FLAT, cursor="hand2", padx=10,
            command=lambda: self._show_broadcast_dialog(notif_svc, user_id),
        ).pack(side=tk.LEFT, padx=4)

        # Notifications list
        tree_frame = tk.Frame(self._content_frame, bg=CONTENT_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 12))

        columns = ("id", "from_system", "title", "message", "priority", "read", "date")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=18)

        headings_map = {
            "id": ("ID", 40),
            "from_system": ("From System", 120),
            "title": ("Title", 200),
            "message": ("Message", 250),
            "priority": ("Priority", 80),
            "read": ("Read", 50),
            "date": ("Date", 140),
        }
        for col, (heading, width) in headings_map.items():
            tree.heading(col, text=heading)
            tree.column(col, width=width, minwidth=40)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        notifications = []
        if notif_svc and user_id:
            try:
                notifications = notif_svc.get_all(user_id, limit=100)
            except Exception:
                pass

        for n in notifications:
            tree.insert("", tk.END, values=(
                n.get("id", ""),
                n.get("sender_system", ""),
                n.get("title", ""),
                (n.get("message", "") or "")[:80],
                n.get("priority", "normal"),
                "No" if not n.get("is_read") else "Yes",
                str(n.get("created_at", ""))[:16],
            ))

        if not notifications:
            tk.Label(
                self._content_frame,
                text="No notifications found.",
                font=("Segoe UI", 10),
                bg=CONTENT_BG,
                fg=TEXT_MUTED,
            ).pack(pady=8)

    def _mark_all_read_and_refresh(self, notif_svc, user_id):
        try:
            notif_svc.mark_all_read(user_id)
        except Exception:
            pass
        self._show_section("notifications")

    def _show_send_notification_dialog(self, notif_svc, sender_user_id):
        dlg = tk.Toplevel(self)
        dlg.title("Send Notification")
        dlg.geometry("440x360")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="Send Notification", font=("Segoe UI", 14, "bold")).pack(pady=(12, 8))
        form = tk.Frame(dlg)
        form.pack(padx=20, fill=tk.X)

        # Recipient user ID
        row = tk.Frame(form); row.pack(fill=tk.X, pady=3)
        tk.Label(row, text="Recipient User ID:", font=("Segoe UI", 10), width=16, anchor=tk.W).pack(side=tk.LEFT)
        recip_var = tk.StringVar()
        tk.Entry(row, textvariable=recip_var, font=("Segoe UI", 10), width=24).pack(side=tk.LEFT)

        # Target system
        row2 = tk.Frame(form); row2.pack(fill=tk.X, pady=3)
        tk.Label(row2, text="Target System:", font=("Segoe UI", 10), width=16, anchor=tk.W).pack(side=tk.LEFT)
        sys_var = tk.StringVar(value="university")
        ttk.Combobox(
            row2, textvariable=sys_var, values=list(SYSTEM_ORDER), state="readonly", width=14,
        ).pack(side=tk.LEFT)

        # Title
        row3 = tk.Frame(form); row3.pack(fill=tk.X, pady=3)
        tk.Label(row3, text="Title:", font=("Segoe UI", 10), width=16, anchor=tk.W).pack(side=tk.LEFT)
        title_var = tk.StringVar()
        tk.Entry(row3, textvariable=title_var, font=("Segoe UI", 10), width=24).pack(side=tk.LEFT)

        # Priority
        row4 = tk.Frame(form); row4.pack(fill=tk.X, pady=3)
        tk.Label(row4, text="Priority:", font=("Segoe UI", 10), width=16, anchor=tk.W).pack(side=tk.LEFT)
        prio_var = tk.StringVar(value="normal")
        ttk.Combobox(
            row4, textvariable=prio_var, values=["low", "normal", "high", "urgent"], state="readonly", width=14,
        ).pack(side=tk.LEFT)

        # Message
        tk.Label(form, text="Message:", font=("Segoe UI", 10), anchor=tk.W).pack(fill=tk.X, pady=(6, 2))
        msg_text = tk.Text(form, font=("Segoe UI", 10), height=4, width=40)
        msg_text.pack(fill=tk.X)

        def _send():
            if not title_var.get().strip():
                messagebox.showwarning("Validation", "Title is required.", parent=dlg)
                return
            if not notif_svc or not sender_user_id:
                messagebox.showerror("Error", "Notification service unavailable.", parent=dlg)
                return
            try:
                recip = int(recip_var.get().strip())
                notif_svc.send(
                    sender_user_id=sender_user_id,
                    sender_system="superadmin",
                    recipient_user_id=recip,
                    recipient_system=sys_var.get(),
                    title=title_var.get().strip(),
                    message=msg_text.get("1.0", tk.END).strip() or None,
                    priority=prio_var.get(),
                )
                messagebox.showinfo("Sent", "Notification sent.", parent=dlg)
                dlg.destroy()
                self._show_section("notifications")
            except ValueError:
                messagebox.showwarning("Validation", "Recipient User ID must be a number.", parent=dlg)
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=dlg)

        tk.Button(
            dlg, text="Send", font=("Segoe UI", 11), bg="#2980b9", fg=TEXT_LIGHT,
            relief=tk.FLAT, padx=16, pady=4, cursor="hand2", command=_send,
        ).pack(pady=12)

    def _show_broadcast_dialog(self, notif_svc, sender_user_id):
        dlg = tk.Toplevel(self)
        dlg.title("Broadcast to Role")
        dlg.geometry("440x360")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="Broadcast Announcement", font=("Segoe UI", 14, "bold")).pack(pady=(12, 8))
        form = tk.Frame(dlg)
        form.pack(padx=20, fill=tk.X)

        # Target system
        row = tk.Frame(form); row.pack(fill=tk.X, pady=3)
        tk.Label(row, text="Target System:", font=("Segoe UI", 10), width=14, anchor=tk.W).pack(side=tk.LEFT)
        sys_var = tk.StringVar(value="university")
        ttk.Combobox(
            row, textvariable=sys_var, values=list(SYSTEM_ORDER), state="readonly", width=14,
        ).pack(side=tk.LEFT)

        # Target role
        row2 = tk.Frame(form); row2.pack(fill=tk.X, pady=3)
        tk.Label(row2, text="Target Role:", font=("Segoe UI", 10), width=14, anchor=tk.W).pack(side=tk.LEFT)
        role_var = tk.StringVar(value="student")
        ttk.Combobox(
            row2, textvariable=role_var,
            values=["superadmin", "admin", "staff", "student", "parent"],
            state="readonly", width=14,
        ).pack(side=tk.LEFT)

        # Title
        row3 = tk.Frame(form); row3.pack(fill=tk.X, pady=3)
        tk.Label(row3, text="Title:", font=("Segoe UI", 10), width=14, anchor=tk.W).pack(side=tk.LEFT)
        title_var = tk.StringVar()
        tk.Entry(row3, textvariable=title_var, font=("Segoe UI", 10), width=24).pack(side=tk.LEFT)

        # Priority
        row4 = tk.Frame(form); row4.pack(fill=tk.X, pady=3)
        tk.Label(row4, text="Priority:", font=("Segoe UI", 10), width=14, anchor=tk.W).pack(side=tk.LEFT)
        prio_var = tk.StringVar(value="normal")
        ttk.Combobox(
            row4, textvariable=prio_var, values=["low", "normal", "high", "urgent"], state="readonly", width=14,
        ).pack(side=tk.LEFT)

        # Message
        tk.Label(form, text="Message:", font=("Segoe UI", 10), anchor=tk.W).pack(fill=tk.X, pady=(6, 2))
        msg_text = tk.Text(form, font=("Segoe UI", 10), height=4, width=40)
        msg_text.pack(fill=tk.X)

        def _broadcast():
            if not title_var.get().strip():
                messagebox.showwarning("Validation", "Title is required.", parent=dlg)
                return
            if not notif_svc or not sender_user_id:
                messagebox.showerror("Error", "Notification service unavailable.", parent=dlg)
                return
            try:
                count = notif_svc.send_to_role(
                    sender_user_id=sender_user_id,
                    sender_system="superadmin",
                    target_system=sys_var.get(),
                    target_role=role_var.get(),
                    title=title_var.get().strip(),
                    message=msg_text.get("1.0", tk.END).strip() or None,
                    priority=prio_var.get(),
                )
                messagebox.showinfo("Broadcast Sent", f"Notification sent to {count} user(s).", parent=dlg)
                dlg.destroy()
                self._show_section("notifications")
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=dlg)

        tk.Button(
            dlg, text="Broadcast", font=("Segoe UI", 11), bg="#8e44ad", fg=TEXT_LIGHT,
            relief=tk.FLAT, padx=16, pady=4, cursor="hand2", command=_broadcast,
        ).pack(pady=12)
