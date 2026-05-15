"""Unified inbox panel.

Single-feed view (laid out like the original Messages tab) that
aggregates three formerly-separate streams:

* University user-to-user messages (from the local CommunicationDashboard).
* Cross-system staff messages (InterSystemMessagingService).
* System notifications (NotificationsService).

Layout mirrors the original Messages tab: top toolbar + a horizontal
paned window with a list (left) and a message viewer (right). A small
filter strip sits between them. Compose actions open modal dialogs
rather than living in a separate tab, matching the original feel.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from education_system.shared.messaging.messaging_service import InterSystemMessagingService

logger = logging.getLogger(__name__)

SYSTEM_NAMES = {
    "university": "University",
    "college": "Sixth Form College",
    "school": "Secondary School",
    "primary": "Primary School",
}
ALL_SYSTEM_KEYS = ["primary", "school", "college", "university"]

NOTIF_CHANNELS = ["academic", "social", "financial", "health", "housing", "events", "system"]
NOTIF_PRIORITIES = ["low", "medium", "high", "urgent"]
PRIORITY_RANK = {"urgent": 0, "high": 1, "medium": 2, "low": 3, "": 4}

KIND_LABEL = {
    "university": "Message",
    "message": "Cross-System",
    "notification": "Notification",
}


class UnifiedInboxPanel(tk.Frame):
    """Unified inbox laid out like the original Messages tab."""

    def __init__(self, parent, auth=None, system_key="university", db_path=None,
                 dashboard=None, root=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._auth = auth
        self._system_key = system_key
        self._dashboard = dashboard
        self._root = root or parent.winfo_toplevel()
        self._msg_svc = InterSystemMessagingService(db_path=db_path)
        self._notif_svc = self._init_notif_service()
        self._items: dict[str, dict] = {}
        self._restoring_selection = False
        self._build_ui()
        self.refresh()

    @staticmethod
    def _init_notif_service():
        try:
            from education_system.university_system.modules.domain.communications.notifications.services.notifications_service import (
                NotificationsService,
            )
            return NotificationsService()
        except Exception as exc:
            logger.warning("Notifications service unavailable: %s", exc)
            return None

    def _user_id(self):
        # Cross-system messaging keys off auth.db `users.id` (what
        # `get_staff_list()` returns). University auth's `current_user["id"]`
        # is a *legacy* university user id and does NOT match — using it
        # would silently break inbox lookups for the recipient. Prefer
        # `shared_auth_id` which `core.py` always sets to the auth.db id.
        cu = self._auth if isinstance(self._auth, dict) else getattr(self._auth, "current_user", None)
        if isinstance(cu, dict):
            return cu.get("shared_auth_id") or cu.get("user_id") or cu.get("id")
        return None

    def _user_name(self):
        if isinstance(self._auth, dict):
            return self._auth.get("display_name") or self._auth.get("username", "")
        cu = getattr(self._auth, "current_user", None)
        if isinstance(cu, dict):
            return cu.get("display_name") or cu.get("username", "")
        return ""

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Toolbar (matches original Messages tab style).
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(toolbar, text="Compose",
                   command=self._open_compose).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Reply",
                   command=self._reply_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Delete",
                   command=self._delete_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Mark Read",
                   command=self._mark_selected_read).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Mark All Read",
                   command=self._mark_all_read).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Notification Settings",
                   command=self._open_notif_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Refresh",
                   command=self.refresh).pack(side=tk.RIGHT, padx=5)

        # Filter strip.
        filt = ttk.Frame(self)
        filt.pack(fill=tk.X, padx=10)
        ttk.Label(filt, text="Type:").pack(side=tk.LEFT, padx=(0, 2))
        self._type_var = tk.StringVar(value="All")
        type_combo = ttk.Combobox(
            filt, textvariable=self._type_var, state="readonly", width=20,
            values=["All", "University Message", "Cross-System Message", "Notification"],
        )
        type_combo.pack(side=tk.LEFT, padx=2)
        type_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_feed())

        ttk.Label(filt, text="Channel:").pack(side=tk.LEFT, padx=(10, 2))
        self._channel_var = tk.StringVar(value="All")
        chan_combo = ttk.Combobox(
            filt, textvariable=self._channel_var, state="readonly", width=12,
            values=["All"] + [c.title() for c in NOTIF_CHANNELS],
        )
        chan_combo.pack(side=tk.LEFT, padx=2)
        chan_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_feed())

        ttk.Label(filt, text="Priority:").pack(side=tk.LEFT, padx=(10, 2))
        self._prio_var = tk.StringVar(value="All")
        prio_combo = ttk.Combobox(
            filt, textvariable=self._prio_var, state="readonly", width=10,
            values=["All"] + [p.title() for p in NOTIF_PRIORITIES],
        )
        prio_combo.pack(side=tk.LEFT, padx=2)
        prio_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_feed())

        self._unread_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filt, text="Unread only", variable=self._unread_only_var,
                        command=self._refresh_feed).pack(side=tk.LEFT, padx=10)

        self._status_var = tk.StringVar(value="")
        ttk.Label(filt, textvariable=self._status_var,
                  font=("Arial", 9, "bold"), foreground="#e74c3c").pack(side=tk.RIGHT, padx=4)

        # Paned window: list (left) + viewer (right) — like the original.
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Left pane: inbox list ---
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text="Inbox",
                  font=("Arial", 12, "bold")).pack(pady=(0, 5))

        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        cols = ("Type", "From", "Subject", "Date", "Status")
        self._tree = ttk.Treeview(
            tree_frame, columns=cols, show="headings", selectmode="browse",
            yscrollcommand=vsb.set, xscrollcommand=hsb.set,
        )
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.config(command=self._tree.yview)
        hsb.config(command=self._tree.xview)

        col_cfg = [
            ("Type", "Type", 100, 80),
            ("From", "From", 150, 100),
            ("Subject", "Subject", 250, 150),
            ("Date", "Date", 140, 110),
            ("Status", "Status", 80, 60),
        ]
        for col_id, heading, width, minwidth in col_cfg:
            self._tree.heading(col_id, text=heading)
            self._tree.column(col_id, width=width, minwidth=minwidth)

        self._tree.tag_configure("unread", background="#E8F4F8")
        self._tree.tag_configure("read", background="white")
        self._tree.tag_configure("urgent", background="#fdecea")
        self._tree.tag_configure("high", background="#fff4e5")

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Double-1>", self._on_double_click)
        self._tree.bind("<Button-3>", self._show_context_menu)

        ttk.Label(
            left_frame,
            text="Click a message to view — Double-click or use Reply button to respond",
            font=("Arial", 9, "italic"), foreground="#666",
        ).pack(pady=(5, 0))

        # --- Right pane: message viewer ---
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)

        header_frame = ttk.Frame(right_frame)
        header_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(header_frame, text="Message Content",
                  font=("Arial", 12, "bold")).pack(side=tk.LEFT)

        self._selected_indicator = ttk.Label(
            header_frame, text="No message selected",
            font=("Arial", 9, "italic"), foreground="#666",
        )
        self._selected_indicator.pack(side=tk.RIGHT, padx=5)

        self._message_text = scrolledtext.ScrolledText(
            right_frame, state=tk.DISABLED, wrap=tk.WORD,
        )
        self._message_text.pack(fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def refresh(self):
        self._refresh_feed()

    def _refresh_feed(self):
        uid = self._user_id()
        self._tree.delete(*self._tree.get_children())
        self._items.clear()

        type_filter = self._type_var.get()
        chan_filter = self._channel_var.get()
        prio_filter = self._prio_var.get().lower() if self._prio_var.get() != "All" else None
        unread_only = self._unread_only_var.get()
        only_messages = chan_filter == "All"

        items: list[dict] = []

        if (self._dashboard and type_filter in ("All", "University Message")
                and only_messages):
            try:
                inbox = self._dashboard.get_inbox()
                if isinstance(inbox, dict):
                    for m in inbox.get("messages", []):
                        if unread_only and m.get("is_read"):
                            continue
                        items.append(self._normalize_university_message(m))
            except Exception as exc:
                logger.warning("University inbox load failed: %s", exc)

        if (uid and type_filter in ("All", "Cross-System Message")
                and only_messages):
            try:
                for m in self._msg_svc.get_inbox(uid):
                    if unread_only and m.get("is_read"):
                        continue
                    items.append(self._normalize_message(m))
            except Exception as exc:
                logger.warning("Cross-system inbox load failed: %s", exc)

        if uid and self._notif_svc and type_filter in ("All", "Notification"):
            notif_chan = chan_filter.lower() if chan_filter != "All" else None
            try:
                notifs = self._notif_svc.get_notifications(
                    uid, unread_only=unread_only, channel=notif_chan,
                    priority=prio_filter, limit=200,
                )
                for n in notifs:
                    items.append(self._normalize_notification(n))
            except Exception as exc:
                logger.warning("Notifications load failed: %s", exc)

        if prio_filter:
            items = [it for it in items if it.get("priority", "").lower() == prio_filter]

        items.sort(key=lambda it: it.get("date", ""), reverse=True)

        unread_count = 0
        for it in items:
            tags: list[str] = []
            if not it["is_read"]:
                tags.append("unread")
                unread_count += 1
            else:
                tags.append("read")
            if it["priority"] == "urgent":
                tags.append("urgent")
            elif it["priority"] == "high":
                tags.append("high")

            subject = it["subject"] or ""
            if len(subject) > 60:
                subject = subject[:57] + "..."

            status = "NEW" if not it["is_read"] else "READ"
            iid = self._tree.insert("", tk.END, values=(
                KIND_LABEL.get(it["kind"], it["kind"].title()),
                it["sender"],
                subject,
                it["date"][:16],
                status,
            ), tags=tags)
            self._items[iid] = it

        if not items:
            self._tree.insert("", tk.END, values=("", "No messages", "Your inbox is empty", "", ""))
            self._status_var.set("")
        else:
            self._status_var.set(f"{len(items)} item(s) — {unread_count} unread"
                                 if unread_count else f"{len(items)} item(s)")

        self._clear_viewer()

    @staticmethod
    def _normalize_university_message(m: dict) -> dict:
        return {
            "kind": "university",
            "id": m.get("id"),
            "date": m.get("sent_at") or "",
            "sender": m.get("sender", ""),
            "recipient": m.get("recipient", ""),
            "subject": m.get("subject", "") or "",
            "body": m.get("content", "") or "",
            "channel": "",
            "priority": "",
            "is_read": bool(m.get("is_read")),
            "raw": m,
        }

    @staticmethod
    def _normalize_message(m: dict) -> dict:
        sys_disp = SYSTEM_NAMES.get(m.get("sender_system", ""), m.get("sender_system", ""))
        sender = m.get("sender_name", "")
        if sys_disp:
            sender = f"{sender} ({sys_disp})" if sender else sys_disp
        return {
            "kind": "message",
            "id": m["id"],
            "date": m.get("created_at") or "",
            "sender": sender,
            "recipient": m.get("recipient_name", ""),
            "subject": m.get("subject", ""),
            "body": m.get("body", ""),
            "channel": "",
            "priority": "",
            "is_read": bool(m.get("is_read")),
            "raw": m,
        }

    @staticmethod
    def _normalize_notification(n: dict) -> dict:
        return {
            "kind": "notification",
            "id": n["notification_id"],
            "date": n.get("created_at") or "",
            "sender": n.get("source_system") or "System",
            "recipient": "",
            "subject": n.get("title", ""),
            "body": n.get("message", ""),
            "channel": n.get("channel", "") or "",
            "priority": n.get("priority", "") or "",
            "is_read": bool(n.get("is_read")),
            "raw": n,
        }

    # ------------------------------------------------------------------
    # Selection / viewer
    # ------------------------------------------------------------------

    def _selected_item(self):
        sel = self._tree.selection()
        if not sel:
            return None
        return self._items.get(sel[0])

    def _on_select(self, _event=None):
        if self._restoring_selection:
            return
        item = self._selected_item()
        if not item:
            self._clear_viewer()
            return
        self._show_message(item)
        # Auto-mark read on view, and restore the selection after refresh.
        if not item["is_read"]:
            try:
                self._mark_read_dispatch(item, self._user_id())
                msg_id = item["id"]
                self._refresh_feed()
                self._reselect(msg_id, item["kind"])
            except Exception as exc:
                logger.warning("auto mark-read failed: %s", exc)

    def _on_double_click(self, _event=None):
        item = self._selected_item()
        if not item:
            return
        if item["kind"] in ("university", "message"):
            self._reply_selected()

    def _show_message(self, item: dict):
        self._message_text.config(state=tk.NORMAL)
        self._message_text.delete("1.0", tk.END)

        lines = []
        lines.append(f"From: {item['sender']}")
        if item.get("recipient"):
            lines.append(f"To: {item['recipient']}")
        lines.append(f"Subject: {item['subject'] or '(no subject)'}")
        lines.append(f"Date: {item['date']}")
        lines.append(f"Type: {KIND_LABEL.get(item['kind'], item['kind'])}")
        if item["kind"] == "notification":
            if item["channel"]:
                lines.append(f"Channel: {item['channel'].title()}")
            if item["priority"]:
                lines.append(f"Priority: {item['priority'].title()}")
        if item["kind"] == "message":
            student = item["raw"].get("student_name")
            if student:
                lines.append(f"Student: {student}")
        lines.append(f"Status: {'Read' if item['is_read'] else 'Unread'}")
        header = "\n".join(lines) + "\n" + ("-" * 50) + "\n\n"

        self._message_text.insert("1.0", header + (item["body"] or ""))
        self._message_text.config(state=tk.DISABLED)

        if item["kind"] in ("university", "message"):
            self._selected_indicator.config(
                text="✓ Message selected — Ready to reply",
                foreground="#2E86AB", font=("Arial", 9, "bold"),
            )
        else:
            self._selected_indicator.config(
                text="Notification selected",
                foreground="#666", font=("Arial", 9, "italic"),
            )

    def _clear_viewer(self):
        self._message_text.config(state=tk.NORMAL)
        self._message_text.delete("1.0", tk.END)
        self._message_text.config(state=tk.DISABLED)
        self._selected_indicator.config(
            text="No message selected", foreground="#666",
            font=("Arial", 9, "italic"),
        )

    def _reselect(self, item_id, kind):
        self._restoring_selection = True
        try:
            for iid, it in self._items.items():
                if it["id"] == item_id and it["kind"] == kind:
                    self._tree.selection_set(iid)
                    self._tree.see(iid)
                    break
        finally:
            self._root.after_idle(lambda: setattr(self, "_restoring_selection", False))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _mark_read_dispatch(self, item: dict, uid: str) -> bool:
        if item["kind"] == "message":
            self._msg_svc.mark_read(item["id"])
            return True
        if item["kind"] == "notification" and self._notif_svc:
            return bool(self._notif_svc.mark_as_read(item["id"], uid))
        if item["kind"] == "university" and self._dashboard:
            try:
                self._dashboard.read_message(item["id"])
                return True
            except Exception as exc:
                logger.warning("dashboard.read_message failed: %s", exc)
        return False

    def _mark_selected_read(self):
        item = self._selected_item()
        if not item:
            messagebox.showinfo("Info", "Please select an item first.", parent=self)
            return
        if item["is_read"]:
            return
        try:
            self._mark_read_dispatch(item, self._user_id())
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to mark read: {exc}", parent=self)
            return
        self._refresh_feed()

    def _mark_all_read(self):
        uid = self._user_id()
        if not uid:
            return
        marked = 0
        for it in list(self._items.values()):
            if it["is_read"]:
                continue
            try:
                if self._mark_read_dispatch(it, uid):
                    marked += 1
            except Exception as exc:
                logger.warning("mark_all_read failed for %s: %s", it["id"], exc)
        self._status_var.set(f"Marked {marked} as read")
        self._refresh_feed()

    def _reply_selected(self):
        item = self._selected_item()
        if not item:
            messagebox.showwarning("No Selection", "Please select a message to reply to.", parent=self)
            return
        if item["kind"] == "university":
            if not self._dashboard:
                messagebox.showinfo("Info", "Dashboard unavailable.", parent=self)
                return
            try:
                from education_system.university_system.modules.shared.gui.email.email_gui.chat_dialogs import (
                    ReplyMessageDialog,
                )
                ReplyMessageDialog(self._root, self._dashboard, item["id"])
            except Exception as exc:
                messagebox.showerror("Error", f"Failed to open reply: {exc}", parent=self)
            return
        if item["kind"] == "message":
            self._open_compose(reply_to=item)
            return
        messagebox.showinfo("Info", "Reply is only available for messages.", parent=self)

    def _delete_selected(self):
        item = self._selected_item()
        if not item:
            messagebox.showwarning("No Selection", "Please select a message to delete.", parent=self)
            return
        if not messagebox.askyesno("Confirm Delete", "Delete this item?", parent=self):
            return
        try:
            if item["kind"] == "university" and self._dashboard:
                self._dashboard.update_message_status(item["id"], "delete")
            elif item["kind"] == "notification" and self._notif_svc:
                self._notif_svc.archive_notification(item["id"], self._user_id())
            else:
                # Cross-system has no delete endpoint; mark read as best-effort.
                self._mark_read_dispatch(item, self._user_id())
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to delete: {exc}", parent=self)
            return
        self._refresh_feed()

    def _show_context_menu(self, event):
        iid = self._tree.identify_row(event.y)
        if not iid:
            return
        self._tree.selection_set(iid)
        item = self._items.get(iid)
        if not item:
            return
        menu = tk.Menu(self._root, tearoff=0)
        if item["kind"] in ("university", "message"):
            menu.add_command(label="Reply", command=self._reply_selected)
        menu.add_command(label="Mark Read", command=self._mark_selected_read)
        menu.add_command(label="Delete", command=self._delete_selected)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ------------------------------------------------------------------
    # Compose dialogs
    # ------------------------------------------------------------------

    def _build_recipient_directory(self) -> list[dict]:
        """Return one merged list of recipients across all systems.

        Each entry: {label, kind: 'university'|'cross', id, system_key,
        display_name, role}. The kind drives which backend the send
        path uses; the system_key is the target system (own system for
        'university', another for 'cross').
        """
        directory: list[dict] = []

        # University intra-system users (legacy users table — that's what
        # CommunicationDashboard.send_message expects for recipient_id).
        if self._dashboard:
            try:
                from education_system.university_system.infrastructure.database.db import (
                    get_db_connection,
                )
                conn = get_db_connection()
                # The legacy university ``users`` table stores names
                # as ``first_name`` + ``last_name`` (no ``display_name``
                # column). Synthesise the display name in SQL so the
                # rest of this method can treat it uniformly.
                rows = conn.execute(
                    "SELECT id, username, "
                    "TRIM(COALESCE(first_name, '') || ' ' || "
                    "COALESCE(last_name, '')) AS display_name, role "
                    "FROM users "
                    "WHERE COALESCE(role, '') IN ('admin', 'staff', 'teacher', 'instructor', 'student') "
                    "ORDER BY display_name, username"
                ).fetchall()
                conn.close()
                for r in rows:
                    rd = dict(r) if not isinstance(r, dict) else r
                    name = rd.get("display_name") or rd.get("username") or ""
                    directory.append({
                        "label": f"{name} ({rd.get('role', '')}) — University",
                        "kind": "university",
                        "id": rd.get("id"),
                        "system_key": "university",
                        "display_name": name,
                        "role": rd.get("role", ""),
                    })
            except Exception as exc:
                logger.warning("Could not load university users: %s", exc)

        # Cross-system staff (auth.db) — every system except this one.
        for sys_key in ALL_SYSTEM_KEYS:
            if sys_key == self._system_key:
                continue
            try:
                for s in self._msg_svc.get_staff_list(sys_key):
                    name = s.get("display_name") or s.get("username") or ""
                    directory.append({
                        "label": f"{name} ({s.get('role', '')}) — {SYSTEM_NAMES.get(sys_key, sys_key)}",
                        "kind": "cross",
                        "id": s.get("id"),
                        "system_key": sys_key,
                        "display_name": name,
                        "role": s.get("role", ""),
                    })
            except Exception as exc:
                logger.warning("Staff list for %s failed: %s", sys_key, exc)

        return directory

    def _open_compose(self, reply_to: dict | None = None):
        """Single unified compose dialog covering university + cross-system."""
        directory = self._build_recipient_directory()
        if not directory:
            messagebox.showinfo("Info", "No recipients available.", parent=self)
            return
        by_label = {entry["label"]: entry for entry in directory}
        all_labels = sorted(by_label.keys(), key=str.lower)

        dlg = tk.Toplevel(self._root)
        dlg.title("Compose Message")
        dlg.geometry("580x500")
        dlg.transient(self._root)

        def _grab():
            try:
                dlg.wait_visibility()
                dlg.grab_set()
            except tk.TclError as exc:
                logger.debug("grab_set deferred failed: %s", exc)
        dlg.after(50, _grab)

        frm = ttk.Frame(dlg, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)
        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(4, weight=1)

        # --- Recipient with autocomplete ---
        ttk.Label(frm, text="To:").grid(row=0, column=0, sticky="w", pady=4)
        recip_var = tk.StringVar()
        recip_combo = ttk.Combobox(frm, textvariable=recip_var, values=all_labels, width=52)
        recip_combo.grid(row=0, column=1, sticky="ew", pady=4, padx=4)

        # Live filter the dropdown list as the user types.
        def on_recip_keyrelease(_e=None):
            typed = recip_var.get().lower()
            if not typed:
                recip_combo["values"] = all_labels
                return
            recip_combo["values"] = [lbl for lbl in all_labels if typed in lbl.lower()]
        recip_combo.bind("<KeyRelease>", on_recip_keyrelease)

        # Routing chip — updates as the recipient changes.
        chip_var = tk.StringVar(value="Pick a recipient — university or another system")
        chip = ttk.Label(frm, textvariable=chip_var, foreground="#666",
                         font=("Arial", 9, "italic"))
        chip.grid(row=1, column=1, sticky="w", padx=4)

        # --- Student (only shown for cross-system) ---
        student_label = ttk.Label(frm, text="Student (optional):")
        student_var = tk.StringVar()
        student_entry = ttk.Entry(frm, textvariable=student_var)

        def update_chip_and_student(*_):
            entry = by_label.get(recip_var.get())
            if not entry:
                chip_var.set("Pick a recipient — university or another system")
                chip.configure(foreground="#666")
                student_label.grid_remove()
                student_entry.grid_remove()
                return
            if entry["kind"] == "cross":
                chip_var.set(f"[Cross-system] → {SYSTEM_NAMES.get(entry['system_key'], entry['system_key'])}")
                chip.configure(foreground="#2E86AB")
                student_label.grid(row=2, column=0, sticky="w", pady=4)
                student_entry.grid(row=2, column=1, sticky="ew", pady=4, padx=4)
            else:
                chip_var.set("[University] internal message")
                chip.configure(foreground="#2E86AB")
                student_label.grid_remove()
                student_entry.grid_remove()
        recip_var.trace_add("write", update_chip_and_student)

        # --- Subject ---
        ttk.Label(frm, text="Subject:").grid(row=3, column=0, sticky="w", pady=4)
        subject_var = tk.StringVar()
        ttk.Entry(frm, textvariable=subject_var).grid(row=3, column=1, sticky="ew", pady=4, padx=4)

        # --- Message body ---
        ttk.Label(frm, text="Message:").grid(row=4, column=0, sticky="nw", pady=4)
        body_text = tk.Text(frm, height=12, wrap="word")
        body_text.grid(row=4, column=1, sticky="nsew", pady=4, padx=4)

        # --- Pre-fill on reply ---
        if reply_to:
            raw = reply_to.get("raw", {})
            if reply_to["kind"] == "message":
                # Cross-system reply — find the original sender in the directory.
                target_id = raw.get("sender_id")
                target_sys = raw.get("sender_system")
                for entry in directory:
                    if (entry["kind"] == "cross"
                            and entry["id"] == target_id
                            and entry["system_key"] == target_sys):
                        recip_var.set(entry["label"])
                        break
                student_var.set(raw.get("student_name") or "")
            elif reply_to["kind"] == "university":
                target_id = raw.get("sender_id") or raw.get("sender_user_id")
                for entry in directory:
                    if entry["kind"] == "university" and entry["id"] == target_id:
                        recip_var.set(entry["label"])
                        break
            subj = raw.get("subject", "") or reply_to.get("subject", "")
            if subj and not subj.lower().startswith("re:"):
                subj = f"Re: {subj}"
            subject_var.set(subj)
            body_text.insert("1.0", "\n\n--- Original message ---\n" + (raw.get("body") or reply_to.get("body", "")))

        def do_send():
            entry = by_label.get(recip_var.get())
            if not entry:
                messagebox.showwarning("Validation",
                                       "Please pick a recipient from the list.", parent=dlg)
                return
            subject = subject_var.get().strip()
            if not subject:
                messagebox.showwarning("Validation", "Subject is required.", parent=dlg)
                return
            body = body_text.get("1.0", tk.END).strip()
            if not body:
                messagebox.showwarning("Validation", "Message body is empty.", parent=dlg)
                return
            try:
                if entry["kind"] == "university":
                    if not self._dashboard:
                        messagebox.showerror("Error",
                                             "University messaging unavailable.", parent=dlg)
                        return
                    ok = self._dashboard.send_message(entry["id"], subject, body)
                    if not ok:
                        messagebox.showerror("Error", "Failed to send message.", parent=dlg)
                        return
                else:  # cross-system
                    uid = self._user_id()
                    if not uid:
                        messagebox.showerror("Error", "No user session.", parent=dlg)
                        return
                    msg = self._msg_svc.send_message(
                        sender_id=uid, sender_system=self._system_key,
                        sender_name=self._user_name(),
                        recipient_id=entry["id"],
                        recipient_system=entry["system_key"],
                        recipient_name=entry["display_name"],
                        student_name=student_var.get().strip(), student_id="",
                        subject=subject, body=body,
                    )
                    if not msg:
                        messagebox.showerror("Error", "Failed to send message.", parent=dlg)
                        return
                messagebox.showinfo("Sent", "Message sent.", parent=dlg)
                dlg.destroy()
                self._refresh_feed()
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=dlg)

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=2, pady=12)
        ttk.Button(btns, text="Send", command=do_send).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side=tk.LEFT, padx=6)

        # Initial chip state.
        update_chip_and_student()

    def _open_notif_settings(self):
        if not self._notif_svc:
            messagebox.showinfo("Info", "Notifications service unavailable.", parent=self)
            return
        try:
            from education_system.university_system.modules.domain.communications.notifications.gui.notifications_gui import (
                NotificationsGUI,
            )
            gui = NotificationsGUI(parent=self._root)
            gui._open_settings_dialog()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to open settings: {exc}", parent=self)
