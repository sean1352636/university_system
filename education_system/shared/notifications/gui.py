"""Cross-system notification GUI components."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.shared.notifications.service import CrossSystemNotificationService

# System display names
SYSTEM_NAMES = {
    "university": "University",
    "college": "Sixth Form College",
    "school": "Secondary School",
    "primary": "Primary School",
}


class CrossSystemNotificationsFrame(tk.Frame):
    """Frame displaying cross-system notifications and allowing sending."""

    def __init__(self, parent, db_path=None, auth=None, system_key=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._system_key = system_key
        self._svc = CrossSystemNotificationService()
        self._build_ui()

    def _get_user_id(self):
        if isinstance(self._auth, dict):
            return self._auth.get("user_id") or self._auth.get("id")
        if hasattr(self._auth, "current_user") and self._auth.current_user:
            return self._auth.current_user.get("user_id") or self._auth.current_user.get("id")
        return None

    def _get_role(self):
        if isinstance(self._auth, dict):
            return self._auth.get("role", "")
        if hasattr(self._auth, "current_user") and self._auth.current_user:
            return self._auth.current_user.get("role", "")
        return ""

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Cross-System Notifications",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        # Toolbar
        toolbar = tk.Frame(self, bg="#ecf0f1", pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Refresh", command=self.refresh).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Mark All Read",
                   command=self._mark_all_read).pack(side="left", padx=4)

        # Only admin/staff can send
        role = self._get_role()
        if role in ("admin", "staff", "teacher", "instructor"):
            ttk.Button(toolbar, text="Send Message",
                       command=self._send_dialog).pack(side="left", padx=4)

        # Unread count
        self._count_var = tk.StringVar(value="")
        tk.Label(toolbar, textvariable=self._count_var, bg="#ecf0f1",
                 font=("Helvetica", 10, "bold"), fg="#e74c3c").pack(side="right", padx=10)

        # Notification list
        list_frame = tk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        columns = ("from_system", "sender", "title", "date", "status")
        self._tree = ttk.Treeview(list_frame, columns=columns, show="headings",
                                  selectmode="browse")
        for col, heading, width in [
            ("from_system", "From System", 120),
            ("sender", "Sender", 120),
            ("title", "Title", 250),
            ("date", "Date", 140),
            ("status", "Status", 70),
        ]:
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=width, anchor="center" if col in ("status", "date") else "w")

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._tree.bind("<Double-1>", self._on_view)

        # Detail area
        detail_frame = tk.LabelFrame(self, text="Message", bg="#ecf0f1", padx=10, pady=5)
        detail_frame.pack(fill="x", padx=15, pady=(0, 10))
        self._detail_text = tk.Text(detail_frame, height=4, state="disabled",
                                     font=("Helvetica", 10), wrap="word")
        self._detail_text.pack(fill="x")

    def refresh(self):
        user_id = self._get_user_id()
        if not user_id:
            return

        self._tree.delete(*self._tree.get_children())
        try:
            notifs = self._svc.get_all(user_id, self._system_key, limit=100)
            unread = sum(1 for n in notifs if not n.get("is_read"))
            self._count_var.set(f"{unread} unread" if unread else "")

            for n in notifs:
                system_name = SYSTEM_NAMES.get(n.get("sender_system", ""), n.get("sender_system", ""))
                status = "Unread" if not n.get("is_read") else "Read"
                self._tree.insert("", "end", iid=n["id"], values=(
                    system_name,
                    n.get("sender_name") or "System",
                    n.get("title", ""),
                    (n.get("created_at") or "")[:16],
                    status,
                ))
        except Exception as e:
            self._count_var.set(f"Error: {e}")

    def _on_view(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        nid = int(sel[0])
        user_id = self._get_user_id()
        if not user_id:
            return
        try:
            notifs = self._svc.get_all(user_id, self._system_key, limit=200)
            notif = next((n for n in notifs if n["id"] == nid), None)
            if notif:
                self._detail_text.config(state="normal")
                self._detail_text.delete("1.0", "end")
                self._detail_text.insert("end", notif.get("message") or "(no message body)")
                self._detail_text.config(state="disabled")
                if not notif.get("is_read"):
                    self._svc.mark_read(nid)
                    self.refresh()
        except Exception:
            pass

    def _mark_all_read(self):
        user_id = self._get_user_id()
        if user_id:
            self._svc.mark_all_read(user_id, self._system_key)
            self.refresh()

    def _send_dialog(self):
        user_id = self._get_user_id()
        if not user_id:
            messagebox.showerror("Error", "No user session.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Send Cross-System Message")
        dlg.geometry("450x350")
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()

        pad = {"padx": 10, "pady": 5}
        frm = tk.Frame(dlg, padx=15, pady=15)
        frm.pack(fill="both", expand=True)

        # Target system
        tk.Label(frm, text="Target System:", font=("Helvetica", 10, "bold")).grid(
            row=0, column=0, sticky="w", **pad)
        target_systems = [k for k in SYSTEM_NAMES if k != self._system_key]
        target_var = tk.StringVar(value=target_systems[0] if target_systems else "")
        ttk.Combobox(frm, textvariable=target_var, values=target_systems,
                     state="readonly", width=25).grid(row=0, column=1, **pad)

        # Target role
        tk.Label(frm, text="Target Role:", font=("Helvetica", 10, "bold")).grid(
            row=1, column=0, sticky="w", **pad)
        role_var = tk.StringVar(value="admin")
        ttk.Combobox(frm, textvariable=role_var,
                     values=["admin", "staff", "teacher", "student", "parent"],
                     state="readonly", width=25).grid(row=1, column=1, **pad)

        # Title
        tk.Label(frm, text="Title:", font=("Helvetica", 10, "bold")).grid(
            row=2, column=0, sticky="w", **pad)
        title_var = tk.StringVar()
        ttk.Entry(frm, textvariable=title_var, width=28).grid(row=2, column=1, **pad)

        # Message
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
                count = self._svc.send_to_role(
                    user_id, self._system_key or "",
                    target, role, title, message,
                )
                messagebox.showinfo("Sent", f"Message sent to {count} {role}(s) in "
                                    f"{SYSTEM_NAMES.get(target, target)}.", parent=dlg)
                dlg.destroy()
                self.refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        btn_frame = tk.Frame(frm)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Send", command=_send).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dlg.destroy).pack(side="left", padx=5)
