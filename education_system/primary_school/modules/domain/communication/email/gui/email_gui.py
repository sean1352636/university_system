"""Email management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.communication.email.services.email_service import EmailService
from education_system.shared.messaging.cross_system_panel import CrossSystemMessagePanel
import traceback


class EmailFrame(tk.Frame):
    """Email compose and send log screen with cross-system messaging tab."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = EmailService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Email", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Notebook: local email + cross-system messaging
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        local_tab = tk.Frame(notebook)
        notebook.add(local_tab, text="Local Email")

        cross_tab = CrossSystemMessagePanel(notebook, auth=auth, system_key="primary",
                                            db_path=db_path)
        notebook.add(cross_tab, text="Cross-System")
        self._cross_panel = cross_tab

        # Compose form
        compose_frame = tk.LabelFrame(local_tab, text="Compose Email", padx=10, pady=5)
        compose_frame.pack(fill="x", padx=10, pady=5)

        row1 = tk.Frame(compose_frame)
        row1.pack(fill="x", pady=2)
        tk.Label(row1, text="To:", width=10, anchor="w").pack(side="left")
        self._to_entry = tk.Entry(row1, width=50)
        self._to_entry.pack(side="left", fill="x", expand=True)

        row2 = tk.Frame(compose_frame)
        row2.pack(fill="x", pady=2)
        tk.Label(row2, text="Subject:", width=10, anchor="w").pack(side="left")
        self._subject_entry = tk.Entry(row2, width=50)
        self._subject_entry.pack(side="left", fill="x", expand=True)

        row3 = tk.Frame(compose_frame)
        row3.pack(fill="x", pady=2)
        tk.Label(row3, text="Body:", width=10, anchor="nw").pack(side="left")
        self._body_text = tk.Text(row3, height=6, width=50, wrap="word")
        self._body_text.pack(side="left", fill="x", expand=True)

        btn_row = tk.Frame(compose_frame)
        btn_row.pack(fill="x", pady=5)
        tk.Button(btn_row, text="Send", command=self._on_send, width=12).pack(side="left", padx=5)
        tk.Button(btn_row, text="Clear", command=self._on_clear, width=12).pack(side="left", padx=5)

        # Sent log
        tk.Label(local_tab, text="Sent Emails", font=("Helvetica", 11, "bold"),
                 anchor="w").pack(fill="x", padx=10, pady=(10, 2))

        columns = ("email_id", "to_address", "subject", "sent_at", "status")
        tree_frame = tk.Frame(local_tab)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=130)
        self._tree.column("email_id", width=70)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(local_tab, textvariable=self._status_var, anchor="w", bg="#ecf0f1",
                 padx=10).pack(fill="x", side="bottom")

        self._load_items()

    def refresh(self):
        self._load_items()
        try:
            self._cross_panel.refresh()
        except Exception:
            pass

    def _load_items(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        try:
            records = self._service.get_sent_emails()
            for r in records:
                rid = r.get("email_id", r.get("id"))
                self._tree.insert("", tk.END, iid=rid, values=(
                    rid, r.get("to_address", ""), r.get("subject", ""),
                    r.get("sent_at", ""), r.get("status", ""),
                ))
            self._status_var.set(f"{len(records)} email(s) in log")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load emails: {e}")

    def _on_send(self):
        to_addr = self._to_entry.get().strip()
        subject = self._subject_entry.get().strip()
        body = self._body_text.get("1.0", tk.END).strip()
        if not to_addr:
            messagebox.showwarning("Validation", "To address is required.")
            return
        if not subject:
            messagebox.showwarning("Validation", "Subject is required.")
            return
        try:
            self._service.send_email(to_address=to_addr, subject=subject, body=body)
            self._on_clear()
            self._load_items()
            self._status_var.set("Email sent (logged)")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))

    def _on_clear(self):
        self._to_entry.delete(0, tk.END)
        self._subject_entry.delete(0, tk.END)
        self._body_text.delete("1.0", tk.END)
