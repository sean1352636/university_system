"""The Delivery window's remaining tabs: blocked addresses, bulk sends,
the audit, e-mail roles (administrators only), settings, and a person's
subject-access export or erasure. See ``delivery_screen``."""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import filedialog, ttk

from education_system.systems.university.application.mail import admin as email_admin
from education_system.systems.university.application.mail import outbox
from education_system.systems.university.infrastructure.ui import record_screens as rs


class _ListTab(ttk.Frame):
    """A list with its buttons pinned to the bottom."""

    admin_only = False
    columns: list = []

    def __init__(self, parent, screen):
        super().__init__(parent, padding=6)
        self.screen = screen
        self.who = screen.who
        bar = ttk.Frame(self)
        bar.pack(side="bottom", fill="x", pady=(4, 0))     # before the list
        for label, command in self.buttons():
            ttk.Button(bar, text=label, command=command).pack(side="left", padx=3)
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="right", padx=3)
        self.tree = rs.make_tree(self, self.columns)

    def buttons(self):
        return []

    def rows(self, conn):
        return []

    def iid(self, row):
        return id(row)

    def values(self, row):
        return []

    def refresh(self):
        rows = rs.call(self, self.rows, quiet=True) or []
        self._rows = {str(self.iid(r)): r for r in rows}
        rs.fill(self.tree, rows, self.iid, self.values)

    def current(self):
        key = rs.selected(self.tree)
        if key is None:
            rs.info(self, "Select a row first.")
        return None if key is None else self._rows.get(key)

    def write(self, fn, *args, **kwargs):
        if rs.call(self, fn, *args, write=True, **kwargs) is not None:
            self.screen.changed()
            return True
        return False


class SuppressionsTab(_ListTab):
    columns = [("address", "Address", 260), ("category", "Category", 110),
               ("reason", "Reason", 100), ("detail", "Detail", 260),
               ("by", "Added by", 110), ("at", "Added", 140)]

    def buttons(self):
        return [("Block an address", self.add), ("Unblock", self.remove)]

    def rows(self, conn):
        return outbox.suppressions(conn)

    def iid(self, row):
        return f"{row['address']}|{row['category']}"

    def values(self, row):
        return [row["address"], row["category"], row["reason"], row["detail"],
                row["added_by"], row["added_at"]]

    def add(self):
        values = rs.ask(self, "Block an address", [
            rs.Field("address", "E-mail address", required=True),
            rs.Field("detail", "Why")])
        if values:
            self.write(outbox.add_suppression, *self.who, values["address"], values["detail"])

    def remove(self):
        row = self.current()
        if row and rs.confirm(self, f"Unblock {row['address']} ({row['category']})?"):
            self.write(outbox.remove_suppression, *self.who, row["address"], row["category"])


class BulkTab(rs.RecordTab):
    admin_only = False
    columns = [("id", "#", 50), ("subject", "Subject", 220), ("audience", "Audience", 90),
               ("category", "Category", 100), ("n", "Recipients", 80), ("by", "Sent by", 90),
               ("at", "Sent", 140)]

    def load(self, conn, search, status):
        rows = email_admin.bulk_sends(conn)
        if search:
            rows = [r for r in rows if search.lower() in str(r["subject"]).lower()]
        return rows

    def values(self, row):
        return [row["bulk_id"], row["subject"], row["audience"], row["category"],
                row["recipients"], row["sent_by"], row["sent_at"]]

    def row_id(self, row):
        return row["bulk_id"]

    def fetch(self, conn, record_id):
        found = [r for r in email_admin.bulk_sends(conn, 1000)
                 if str(r["bulk_id"]) == str(record_id)]
        if not found:
            return None
        record = dict(found[0])
        record["messages"] = outbox.messages(conn, bulk_id=int(record_id), limit=1000)
        return record

    def render(self, record):
        by_status: dict = {}
        for m in record["messages"]:
            by_status[m["status"]] = by_status.get(m["status"], 0) + 1
        self.detail.show(record["subject"], [
            ("Send", [("Audience", record["audience"]), ("Category", record["category"]),
                      ("Kind", record["kind"]), ("Recipients", record["recipients"]),
                      ("Skipped", record["suppressed"]), ("Sent by", record["sent_by"]),
                      ("Sent", record["sent_at"])]),
            ("Delivery", sorted(by_status.items()) or ["No messages."]),
            ("Recipients", [f"{m['to_address']}  {m['status']}"
                            + (f"  — {m['last_error']}" if m.get("last_error") else "")
                            for m in record["messages"]]),
        ])


class AuditTab(_ListTab):
    columns = [("at", "When", 140), ("actor", "Who", 110), ("entity", "What", 90),
               ("id", "Which", 160), ("action", "Action", 120), ("detail", "Detail", 380)]

    def rows(self, conn):
        return outbox.recent_audit(conn, 500)

    def iid(self, row):
        return row["audit_id"]

    def values(self, row):
        return [row["at"], row["actor"], row["entity"], row["entity_id"], row["action"],
                row["detail"]]


class RolesTab(_ListTab):
    admin_only = True
    columns = [("user", "Username", 160), ("role", "Role", 120), ("by", "Granted by", 120),
               ("at", "Granted", 150)]

    def buttons(self):
        return [("Grant", self.grant), ("Revoke", self.revoke)]

    def rows(self, conn):
        return outbox.roles(conn)

    def iid(self, row):
        return f"{row['username']}|{row['role']}"

    def values(self, row):
        return [row["username"], row["role"], row["granted_by"], row["granted_at"]]

    def grant(self):
        values = rs.ask(self, "Grant an e-mail role", [
            rs.Field("username", "Member of staff", "staff", rs.staff_choices(self),
                     required=True),
            rs.Field("role", "Role", "combo", [
                ("bulk_sender", "bulk_sender — may send to students / staff / lists"),
                ("email_admin", "email_admin — delivery, settings, everyone")],
                required=True)])
        if values:
            self.write(outbox.grant, *self.who, values["username"], values["role"])

    def revoke(self):
        row = self.current()
        if row and rs.confirm(self, f"Remove {row['role']} from {row['username']}?"):
            self.write(outbox.revoke, *self.who, row["username"], row["role"])


class SettingsTab(ttk.Frame):
    admin_only = False
    LABELS = {"retention_days": "Keep message bodies for (days)",
              "max_attempts": "Delivery attempts before giving up",
              "public_base_url": "Public web address for unsubscribe links (https://…)"}

    def __init__(self, parent, screen):
        super().__init__(parent, padding=10)
        self.screen = screen
        self.vars = {}
        bar = ttk.Frame(self)
        bar.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Button(bar, text="Save", command=self.save).pack(side="left", padx=3)
        form = ttk.Frame(self)
        form.pack(side="top", fill="x")
        for n, (key, label) in enumerate(self.LABELS.items()):
            ttk.Label(form, text=label).grid(row=n, column=0, sticky="w", pady=4, padx=(0, 8))
            self.vars[key] = tk.StringVar()
            ttk.Entry(form, textvariable=self.vars[key], width=50).grid(row=n, column=1,
                                                                        sticky="w")
        self.styled_var = tk.BooleanVar(value=True)
        styled = ttk.Frame(self)
        styled.pack(side="top", fill="x", pady=(10, 0))
        ttk.Checkbutton(styled, variable=self.styled_var,
                        text="Send e-mail in the branded design (colours from Branding & "
                             "Customization, with a plain-text copy)").pack(side="left")
        ttk.Button(styled, text="Preview design", command=self.preview).pack(side="left", padx=8)
        ttk.Label(self, foreground="#555555", wraplength=700, justify="left",
                  text="Without a public address, bulk e-mail tells people to turn the "
                       "category off under E-mail preferences in the University app.").pack(
            side="top", anchor="w", pady=(10, 0))

    def refresh(self):
        def read(conn):
            return {key: outbox.setting(conn, key) for key in (*self.LABELS, "html_layout")}
        values = rs.call(self, read, quiet=True) or {}
        for key, value in values.items():
            if key == "html_layout":
                self.styled_var.set(value != "0")
            else:
                self.vars[key].set(value)

    def save(self):
        def write(conn):
            for key, var in self.vars.items():
                if var.get().strip() != outbox.setting(conn, key):
                    outbox.set_setting(conn, *self.screen.who, key, var.get())
            styled = "1" if self.styled_var.get() else "0"
            if styled != outbox.setting(conn, "html_layout"):
                outbox.set_setting(conn, *self.screen.who, "html_layout", styled)
        if rs.call(self, write, write=True) is not None:
            from education_system.systems.university.infrastructure.email import html_layout
            html_layout.clear_cache()
            rs.info(self, "Settings saved.")
            self.screen.changed()

    def preview(self):
        from education_system.systems.university.shell.gui.email.email_preview import (
            open_sample,
        )
        open_sample(self)


class AccessTab(ttk.Frame):
    """Subject access: export or erase the e-mails sent to one address."""

    admin_only = False

    def __init__(self, parent, screen):
        super().__init__(parent, padding=10)
        self.screen = screen
        row = ttk.Frame(self)
        row.pack(side="top", fill="x")
        ttk.Label(row, text="E-mail address").pack(side="left")
        self.address = tk.StringVar()
        ttk.Entry(row, textvariable=self.address, width=40).pack(side="left", padx=6)
        ttk.Button(row, text="Export…", command=self.export).pack(side="left", padx=3)
        ttk.Button(row, text="Erase…", command=self.erase).pack(side="left", padx=3)
        ttk.Label(self, foreground="#555555", wraplength=760, justify="left",
                  text="Export saves everything held about e-mail sent to the address "
                       "(outbox, stored copies, send log, blocks) as JSON. Erase deletes the "
                       "messages; a block on the address is kept so they are not mailed "
                       "again.").pack(side="top", anchor="w", pady=10)

    def refresh(self):
        pass

    def export(self):
        address = self.address.get().strip()
        data = rs.call(self, email_admin.export, *self.screen.who, address, write=True)
        if data is None:
            return
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".json",
                                            initialfile=f"email-records-{address}.json",
                                            filetypes=[("JSON", "*.json")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, default=str)
            rs.info(self, f"Saved to {path}")

    def erase(self):
        address = self.address.get().strip()
        if not address or not rs.confirm(
                self, f"Permanently delete every e-mail sent to {address}? This cannot be "
                      "undone."):
            return
        done = rs.call(self, email_admin.erase, *self.screen.who, address, write=True)
        if done is not None:
            rs.info(self, "Deleted: " + ", ".join(f"{k} {v}" for k, v in done.items()))
            self.screen.changed()


TABS = (("Blocked addresses", SuppressionsTab), ("Bulk sends", BulkTab),
        ("Audit", AuditTab), ("Roles", RolesTab), ("Settings", SettingsTab),
        ("Subject access", AccessTab))
