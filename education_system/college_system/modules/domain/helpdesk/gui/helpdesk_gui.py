"""Helpdesk GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.helpdesk.services.helpdesk_service import HelpdeskService


class HelpdeskFrame(tk.Frame):
    """Helpdesk ticket management screen."""

    _CATEGORIES = ("general", "it", "facilities", "academic", "finance", "other")
    _PRIORITIES = ("low", "medium", "high", "urgent")
    _STATUSES = ("open", "in_progress", "resolved", "closed")

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = HelpdeskService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Helpdesk",
                 font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        # Notebook
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        # --- My Tickets tab ---
        my_tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(my_tab, text="My Tickets")

        my_top = tk.Frame(my_tab, bg="#ecf0f1")
        my_top.pack(fill="x", pady=(0, 5))
        ttk.Button(my_top, text="New Ticket",
                   command=self._on_new_ticket).pack(side="left")
        ttk.Button(my_top, text="Refresh",
                   command=self._load_my_tickets).pack(side="left", padx=10)

        my_cols = ("id", "subject", "category", "priority", "status", "created")
        self._my_tree = ttk.Treeview(my_tab, columns=my_cols,
                                     show="headings", height=8)
        for col, heading, w in [
            ("id", "ID", 40), ("subject", "Subject", 200),
            ("category", "Category", 80), ("priority", "Priority", 70),
            ("status", "Status", 80), ("created", "Created", 120),
        ]:
            self._my_tree.heading(col, text=heading)
            self._my_tree.column(col, width=w, anchor="center")
        self._my_tree.pack(fill="both", expand=True)
        self._my_tree.bind("<<TreeviewSelect>>", self._on_select_my_ticket)

        # Detail/response pane
        my_detail = tk.LabelFrame(my_tab, text="Ticket Detail",
                                  bg="#ecf0f1", font=("Helvetica", 10, "bold"))
        my_detail.pack(fill="x", pady=(5, 0))

        self._my_detail_text = tk.Text(my_detail, height=6, wrap="word",
                                       state="disabled", font=("Helvetica", 9))
        self._my_detail_text.pack(fill="x", padx=5, pady=(5, 2))

        resp_row = tk.Frame(my_detail, bg="#ecf0f1")
        resp_row.pack(fill="x", padx=5, pady=(0, 5))
        self._my_response_var = tk.StringVar()
        ttk.Entry(resp_row, textvariable=self._my_response_var,
                  width=50).pack(side="left", fill="x", expand=True)
        ttk.Button(resp_row, text="Reply",
                   command=self._on_reply_my_ticket).pack(side="left", padx=5)

        # --- All Tickets tab (admin/staff) ---
        self._all_tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(self._all_tab, text="All Tickets")

        all_filter = tk.Frame(self._all_tab, bg="#ecf0f1")
        all_filter.pack(fill="x", pady=(0, 5))
        tk.Label(all_filter, text="Status:", bg="#ecf0f1").pack(side="left")
        self._all_status_var = tk.StringVar(value="All")
        ttk.Combobox(all_filter, textvariable=self._all_status_var,
                     values=["All"] + list(self._STATUSES), state="readonly",
                     width=12).pack(side="left", padx=5)
        ttk.Button(all_filter, text="Load",
                   command=self._load_all_tickets).pack(side="left", padx=5)

        all_cols = ("id", "user", "subject", "category", "priority", "status", "created")
        self._all_tree = ttk.Treeview(self._all_tab, columns=all_cols,
                                      show="headings", height=8)
        for col, heading, w in [
            ("id", "ID", 40), ("user", "User", 80), ("subject", "Subject", 180),
            ("category", "Cat", 70), ("priority", "Priority", 70),
            ("status", "Status", 80), ("created", "Created", 110),
        ]:
            self._all_tree.heading(col, text=heading)
            self._all_tree.column(col, width=w, anchor="center")
        self._all_tree.pack(fill="both", expand=True)
        self._all_tree.bind("<<TreeviewSelect>>", self._on_select_all_ticket)

        # Admin detail pane
        all_detail = tk.LabelFrame(self._all_tab, text="Manage Ticket",
                                   bg="#ecf0f1", font=("Helvetica", 10, "bold"))
        all_detail.pack(fill="x", pady=(5, 0))

        self._all_detail_text = tk.Text(all_detail, height=5, wrap="word",
                                        state="disabled", font=("Helvetica", 9))
        self._all_detail_text.pack(fill="x", padx=5, pady=(5, 2))

        admin_row = tk.Frame(all_detail, bg="#ecf0f1")
        admin_row.pack(fill="x", padx=5, pady=(0, 5))
        tk.Label(admin_row, text="Set Status:", bg="#ecf0f1").pack(side="left")
        self._admin_status_var = tk.StringVar(value="open")
        ttk.Combobox(admin_row, textvariable=self._admin_status_var,
                     values=list(self._STATUSES), state="readonly",
                     width=12).pack(side="left", padx=5)
        ttk.Button(admin_row, text="Update Status",
                   command=self._on_update_status).pack(side="left", padx=5)

        self._admin_resp_var = tk.StringVar()
        ttk.Entry(admin_row, textvariable=self._admin_resp_var,
                  width=30).pack(side="left", padx=5)
        ttk.Button(admin_row, text="Reply",
                   command=self._on_reply_all_ticket).pack(side="left", padx=5)

    def refresh(self):
        self._apply_permissions()
        self._load_my_tickets()

    def _apply_permissions(self):
        role = ""
        if self._auth and self._auth.current_user:
            role = self._auth.current_user.get("role", "student")
        is_staff = role in ("admin", "staff")
        try:
            self._nb.tab(self._all_tab,
                         state="normal" if is_staff else "hidden")
        except Exception:
            pass

    def _get_user_id(self) -> int:
        if self._auth and self._auth.current_user:
            return self._auth.current_user["user_id"]
        return 0

    def _load_my_tickets(self):
        self._my_tree.delete(*self._my_tree.get_children())
        try:
            tickets = self._svc.list_tickets(user_id=self._get_user_id())
            for t in tickets:
                self._my_tree.insert("", "end", values=(
                    t["id"], t["subject"], t["category"],
                    t["priority"], t["status"],
                    t["created_at"][:16] if t.get("created_at") else "",
                ))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_all_tickets(self):
        self._all_tree.delete(*self._all_tree.get_children())
        try:
            status_filter = self._all_status_var.get()
            status = None if status_filter == "All" else status_filter
            tickets = self._svc.list_tickets(status=status)
            for t in tickets:
                self._all_tree.insert("", "end", values=(
                    t["id"], t.get("created_by_name", ""),
                    t["subject"], t["category"],
                    t["priority"], t["status"],
                    t["created_at"][:16] if t.get("created_at") else "",
                ))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _show_ticket_detail(self, text_widget, ticket_id):
        try:
            ticket = self._svc.get_ticket(ticket_id)
        except Exception:
            return
        text_widget.configure(state="normal")
        text_widget.delete("1.0", "end")
        text_widget.insert("end",
            f"#{ticket['id']} - {ticket['subject']} "
            f"[{ticket['status']}] ({ticket['priority']})\n"
            f"Category: {ticket['category']} | "
            f"By: {ticket.get('created_by_name', 'N/A')}\n"
            f"{ticket['description']}\n"
            f"--- Responses ---\n")
        for resp in ticket.get("responses", []):
            text_widget.insert("end",
                f"  [{resp.get('username', '?')}] {resp['message']}\n")
        text_widget.configure(state="disabled")

    def _on_select_my_ticket(self, event=None):
        sel = self._my_tree.selection()
        if not sel:
            return
        ticket_id = int(self._my_tree.item(sel[0], "values")[0])
        self._show_ticket_detail(self._my_detail_text, ticket_id)

    def _on_select_all_ticket(self, event=None):
        sel = self._all_tree.selection()
        if not sel:
            return
        ticket_id = int(self._all_tree.item(sel[0], "values")[0])
        self._show_ticket_detail(self._all_detail_text, ticket_id)
        self._admin_status_var.set(self._all_tree.item(sel[0], "values")[5])

    def _on_new_ticket(self):
        dlg = _TicketDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._svc.create_ticket(self._get_user_id(), **dlg.result)
                messagebox.showinfo("Success", "Ticket created.")
                self._load_my_tickets()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _on_reply_my_ticket(self):
        sel = self._my_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a ticket first.")
            return
        msg = self._my_response_var.get().strip()
        if not msg:
            return
        ticket_id = int(self._my_tree.item(sel[0], "values")[0])
        try:
            self._svc.add_response(ticket_id, self._get_user_id(), msg)
            self._my_response_var.set("")
            self._on_select_my_ticket()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_reply_all_ticket(self):
        sel = self._all_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a ticket first.")
            return
        msg = self._admin_resp_var.get().strip()
        if not msg:
            return
        ticket_id = int(self._all_tree.item(sel[0], "values")[0])
        try:
            self._svc.add_response(ticket_id, self._get_user_id(), msg)
            self._admin_resp_var.set("")
            self._on_select_all_ticket()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_update_status(self):
        sel = self._all_tree.selection()
        if not sel:
            messagebox.showwarning("Select", "Select a ticket first.")
            return
        ticket_id = int(self._all_tree.item(sel[0], "values")[0])
        try:
            self._svc.update_ticket(ticket_id,
                                    status=self._admin_status_var.get())
            self._load_all_tickets()
        except Exception as e:
            messagebox.showerror("Error", str(e))


class _TicketDialog(tk.Toplevel):
    """Create new helpdesk ticket dialog."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("New Ticket")
        self.geometry("430x300")
        self.resizable(False, False)
        self.grab_set()
        self.result = None

        frame = tk.Frame(self, padx=15, pady=15)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Subject:").grid(row=0, column=0, sticky="w", pady=3)
        self._subject_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self._subject_var, width=35).grid(
            row=0, column=1, pady=3)

        tk.Label(frame, text="Category:").grid(row=1, column=0, sticky="w", pady=3)
        self._category_var = tk.StringVar(value="general")
        ttk.Combobox(frame, textvariable=self._category_var,
                     values=["general", "it", "facilities", "academic",
                             "finance", "other"],
                     state="readonly", width=12).grid(
            row=1, column=1, sticky="w", pady=3)

        tk.Label(frame, text="Priority:").grid(row=2, column=0, sticky="w", pady=3)
        self._priority_var = tk.StringVar(value="medium")
        ttk.Combobox(frame, textvariable=self._priority_var,
                     values=["low", "medium", "high", "urgent"],
                     state="readonly", width=12).grid(
            row=2, column=1, sticky="w", pady=3)

        tk.Label(frame, text="Description:").grid(row=3, column=0, sticky="nw", pady=3)
        self._desc_text = tk.Text(frame, width=27, height=5)
        self._desc_text.grid(row=3, column=1, pady=3)

        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_frame, text="Submit", command=self._save).pack(
            side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(
            side="left", padx=5)

    def _save(self):
        subject = self._subject_var.get().strip()
        desc = self._desc_text.get("1.0", "end").strip()
        if not subject:
            messagebox.showwarning("Input", "Subject is required.", parent=self)
            return
        if not desc:
            messagebox.showwarning("Input", "Description is required.", parent=self)
            return
        self.result = {
            "subject": subject,
            "description": desc,
            "category": self._category_var.get(),
            "priority": self._priority_var.get(),
        }
        self.destroy()
