"""Communication Hub dialogs that go through the e-mail rules:

* :class:`BulkEmailDialog` – sends through ``email_admin.send_bulk``, which
  checks the sender's role, applies unsubscribes and preferences, adds the
  unsubscribe footer and records the send in the audit.
* :class:`EmailConfigDialog` – SMTP settings and delivery mode, for e-mail
  administrators only. The mode changes through ``outbox_delivery.set_mode``;
  a password typed here goes to secure storage, never the config file.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from education_system.systems.university.shell.gui.email import hub_access

AUDIENCES = (("students", "All students"), ("staff", "All staff"),
             ("all_users", "Everyone with a login (e-mail admins only)"),
             ("addresses", "These addresses (one per line)"))

MODE_LABELS = {
    "inbox_only": "In-app inbox only (nothing leaves the system)",
    "sandbox": "Sandbox (write .eml files, send nothing)",
    "live": "Live (send real e-mail over SMTP)",
}

LIVE_WARNING = ("Live mode sends real e-mail from {sender} to real external addresses, "
                "including everything already queued. Continue?")


def _templates():
    try:
        from education_system.systems.university.infrastructure.email.template_utils import (
            list_templates, load_template,
        )
        return list_templates, load_template
    except ImportError:
        return None, None


class BulkEmailDialog:
    def __init__(self, parent, auth):
        self.auth = auth
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Bulk Email")
        self.dialog.geometry("720x620")
        self.dialog.minsize(600, 480)
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists()
                          else None)
        self.create_widgets()

    def create_widgets(self):
        buttons = ttk.Frame(self.dialog, padding=(10, 6))
        buttons.pack(side=tk.BOTTOM, fill=tk.X)        # packed first: always visible
        ttk.Button(buttons, text="Send", command=self.send_bulk).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons, text="Preview", command=self.preview_email).pack(side=tk.LEFT,
                                                                             padx=5)
        ttk.Button(buttons, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT,
                                                                             padx=5)
        main = ttk.Frame(self.dialog, padding=10)
        main.pack(fill=tk.BOTH, expand=True)
        main.columnconfigure(1, weight=1)

        ttk.Label(main, text="Audience:").grid(row=0, column=0, sticky=tk.NW, pady=3)
        self.audience_var = tk.StringVar(value="students")
        box = ttk.Frame(main)
        box.grid(row=0, column=1, sticky=tk.W)
        for value, label in AUDIENCES:
            ttk.Radiobutton(box, text=label, variable=self.audience_var, value=value,
                            command=self._audience_changed).pack(anchor=tk.W)
        self.addresses = tk.Text(main, height=3, width=60, state=tk.DISABLED)
        self.addresses.grid(row=1, column=1, sticky=tk.EW, pady=3)

        ttk.Label(main, text="Category:").grid(row=2, column=0, sticky=tk.W, pady=3)
        self.category_var = tk.StringVar(value="announcements")
        ttk.Entry(main, textvariable=self.category_var, width=30).grid(row=2, column=1,
                                                                        sticky=tk.W)
        ttk.Label(main, text="Kind:").grid(row=3, column=0, sticky=tk.W, pady=3)
        self.kind_var = tk.StringVar(value="bulk")
        kinds = ttk.Frame(main)
        kinds.grid(row=3, column=1, sticky=tk.W)
        ttk.Radiobutton(kinds, text="Bulk / announcement", variable=self.kind_var,
                        value="bulk").pack(side=tk.LEFT)
        ttk.Radiobutton(kinds, text="Marketing", variable=self.kind_var,
                        value="marketing").pack(side=tk.LEFT, padx=10)

        ttk.Label(main, text="Subject:").grid(row=4, column=0, sticky=tk.W, pady=3)
        self.subject_entry = ttk.Entry(main, width=60)
        self.subject_entry.grid(row=4, column=1, sticky=tk.EW, pady=3)

        ttk.Label(main, text="Template:").grid(row=5, column=0, sticky=tk.W, pady=3)
        row = ttk.Frame(main)
        row.grid(row=5, column=1, sticky=tk.W)
        self.template_var = tk.StringVar()
        self.template_combo = ttk.Combobox(row, textvariable=self.template_var, width=30)
        self.template_combo.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row, text="Load Template",
                   command=self.load_selected_template).pack(side=tk.LEFT)

        ttk.Label(main, text="Message:").grid(row=6, column=0, sticky=tk.NW, pady=3)
        self.body_text = scrolledtext.ScrolledText(main, width=60, height=10)
        self.body_text.grid(row=6, column=1, sticky=tk.NSEW, pady=3)
        main.rowconfigure(6, weight=1)
        ttk.Label(main, foreground="#555555", wraplength=520,
                  text="Each message gets an unsubscribe footer. People who unsubscribed "
                       "or opted out of this category are skipped.").grid(
            row=7, column=1, sticky=tk.W)
        self.load_templates()

    def _audience_changed(self):
        state = tk.NORMAL if self.audience_var.get() == "addresses" else tk.DISABLED
        self.addresses.configure(state=state)

    def load_templates(self):
        list_templates, _load = _templates()
        try:
            if list_templates:
                self.template_combo["values"] = [t["name"] for t in list_templates()]
        except Exception:
            self.template_combo["values"] = []

    def load_selected_template(self):
        _list, load_template = _templates()
        name = self.template_var.get()
        if not name or not load_template:
            messagebox.showwarning("Template", "Select a template first", parent=self.dialog)
            return
        data = load_template(name) or {}
        if data.get("subject"):
            self.subject_entry.delete(0, tk.END)
            self.subject_entry.insert(0, data["subject"])
        body = data.get("body") or data.get("body_html") or data.get("body_text") or ""
        if body:
            self.body_text.delete("1.0", tk.END)
            self.body_text.insert("1.0", body)

    def _request(self) -> dict:
        addresses = [a.strip() for a in self.addresses.get("1.0", tk.END).split()
                     if a.strip()] if self.audience_var.get() == "addresses" else None
        return {"audience": self.audience_var.get(), "subject": self.subject_entry.get().strip(),
                "body": self.body_text.get("1.0", tk.END).strip(),
                "category": self.category_var.get().strip(), "kind": self.kind_var.get(),
                "addresses": addresses}

    def send_bulk(self):
        from education_system.systems.university.application.mail import admin as email_admin
        from education_system.systems.university.infrastructure.email import outbox_delivery
        from education_system.systems.university.infrastructure.ui import record_screens as rs
        request = self._request()
        if not request["subject"] or not request["body"]:
            messagebox.showerror("Bulk e-mail", "Enter a subject and a message",
                                 parent=self.dialog)
            return
        label = dict(AUDIENCES)[request["audience"]]
        if not messagebox.askyesno("Bulk e-mail", f"Send to: {label}?", parent=self.dialog):
            return
        username, role = hub_access.user_of(self.auth)
        result = rs.call(self.dialog, email_admin.send_bulk, username, role,
                         mode=outbox_delivery.delivery_mode(), write=True, **request)
        if result is None:
            return
        outbox_delivery.kick()
        messagebox.showinfo("Bulk e-mail",
                            f"{result['recipients']} recipient(s): {result['queued']} queued, "
                            f"{result['stored']} kept in the in-app inbox only, "
                            f"{result['suppressed']} skipped (unsubscribed or blocked).",
                            parent=self.dialog)
        self.dialog.destroy()

    def preview_email(self):
        top = tk.Toplevel(self.dialog)
        top.title("Email Preview")
        top.geometry("520x420")
        text = scrolledtext.ScrolledText(top, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert("1.0", f"Subject: {self.subject_entry.get()}\n\n"
                           f"{self.body_text.get('1.0', tk.END).strip()}\n\n--\n"
                           "(an unsubscribe link is added to each message)")
        text.configure(state=tk.DISABLED)


class EmailConfigDialog:
    """SMTP settings and delivery mode (e-mail administrators only)."""

    def __init__(self, parent, auth=None):
        self.auth = auth
        self.parent = parent
        if auth is None or not hub_access.require_email_admin(auth, parent):
            self.dialog = None
            return
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Email Configuration")
        self.dialog.geometry("560x560")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists()
                          else None)
        self.create_widgets()
        self.load_config()

    def create_widgets(self):
        buttons = ttk.Frame(self.dialog, padding=(10, 6))
        buttons.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(buttons, text="Save", command=self.save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT,
                                                                             padx=5)
        main = ttk.Frame(self.dialog, padding=10)
        main.pack(fill=tk.BOTH, expand=True)
        modes = ttk.LabelFrame(main, text="Delivery mode", padding=8)
        modes.pack(fill=tk.X, pady=4)
        self.mode_var = tk.StringVar()
        for value, label in MODE_LABELS.items():
            ttk.Radiobutton(modes, text=label, variable=self.mode_var,
                            value=value).pack(anchor=tk.W)
        self.status_label = ttk.Label(modes, foreground="#b0620a", wraplength=500)
        self.status_label.pack(anchor=tk.W, pady=(4, 0))

        smtp = ttk.LabelFrame(main, text="SMTP settings", padding=8)
        smtp.pack(fill=tk.X, pady=4)
        self.vars = {}
        rows = (("smtp_server", "SMTP server"), ("smtp_port", "Port"),
                ("smtp_username", "Login name"), ("sender_email", "Sender address"),
                ("sender_name", "Sender name"))
        for n, (key, label) in enumerate(rows):
            ttk.Label(smtp, text=label + ":").grid(row=n, column=0, sticky=tk.W, pady=2)
            self.vars[key] = tk.StringVar()
            ttk.Entry(smtp, textvariable=self.vars[key], width=40).grid(row=n, column=1,
                                                                        sticky=tk.W, pady=2)
        ttk.Label(smtp, text="Password:").grid(row=len(rows), column=0, sticky=tk.W)
        self.password_entry = ttk.Entry(smtp, width=30, show="*")
        self.password_entry.grid(row=len(rows), column=1, sticky=tk.W, pady=2)
        ttk.Label(smtp, foreground="#555555",
                  text="Leave blank to keep the current one. It is kept in secure storage, "
                       "never in the config file.", wraplength=480).grid(
            row=len(rows) + 1, column=0, columnspan=2, sticky=tk.W)
        self.use_tls_var = tk.BooleanVar()
        self.use_auth_var = tk.BooleanVar()
        ttk.Checkbutton(smtp, text="Use TLS", variable=self.use_tls_var).grid(
            row=len(rows) + 2, column=0, sticky=tk.W)
        ttk.Checkbutton(smtp, text="Use authentication", variable=self.use_auth_var).grid(
            row=len(rows) + 2, column=1, sticky=tk.W)

    def load_config(self):
        from education_system.systems.university.infrastructure.email import outbox_delivery
        cfg = hub_access.smtp_settings()
        status = outbox_delivery.status()
        self.mode_var.set(status["mode"])
        for key, var in self.vars.items():
            var.set(str(cfg.get(key) if cfg.get(key) is not None else
                        (587 if key == "smtp_port" else "")))
        if not self.vars["smtp_username"].get():
            self.vars["smtp_username"].set(str(cfg.get("username") or ""))
        self.use_tls_var.set(bool(cfg.get("use_tls", True)))
        self.use_auth_var.set(bool(cfg.get("use_authentication", True)))
        notes = []
        if status["password_in_config_file"]:
            notes.append("The SMTP password is still stored in plain text in the config file.")
        if not status["live_ready"]:
            notes.append("Live sending is not ready: " + "; ".join(status["live_problems"]))
        self.status_label.configure(text="\n".join(notes))

    def _values(self) -> dict:
        values = {key: var.get().strip() for key, var in self.vars.items()}
        try:
            values["smtp_port"] = int(values["smtp_port"] or 587)
        except ValueError:
            raise ValueError("The port must be a number") from None
        values["use_tls"] = bool(self.use_tls_var.get())
        values["use_authentication"] = bool(self.use_auth_var.get())
        return values

    def save_config(self):
        from education_system.systems.university.infrastructure.email import outbox_delivery
        from education_system.systems.university.infrastructure.ui import record_screens as rs
        try:
            values = self._values()
        except ValueError as exc:
            messagebox.showerror("Email Configuration", str(exc), parent=self.dialog)
            return
        hub_access.save_smtp_settings(values, self.password_entry.get())
        mode = self.mode_var.get()
        if mode != outbox_delivery.delivery_mode():
            if mode == "live" and not messagebox.askyesno(
                    "Email Configuration",
                    LIVE_WARNING.format(sender=values["sender_email"] or "the sender"),
                    parent=self.dialog):
                return
            username, role = hub_access.user_of(self.auth)
            if rs.call(self.dialog, outbox_delivery.set_mode, username, role, mode,
                       write=True) is None:
                return
            outbox_delivery.kick()
        messagebox.showinfo("Email Configuration", "Saved.", parent=self.dialog)
        self.dialog.destroy()
