"""The Communication Hub's Delivery window: how e-mail leaves the system
and what happened to each message.

Tabs: Status (mode, sender, server, warnings, counts, mode switch), Outbox
and Failures (each message with its attempt log; Retry / Cancel / Record
bounce), then the tabs in ``delivery_tabs`` (suppressions, bulk sends,
audit, roles, settings, subject access).

Every action is a rule in ``application/mail/outbox`` / ``email_admin``
run through ``record_screens.call``; the rules check permissions again.
There is deliberately no button that moves the SMTP password out of the
config file: that is an administrator's CLI tool.
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.platform.delivery.gui.tk_threads import start_thread, ui
from education_system.systems.university.application.mail import outbox
from education_system.systems.university.infrastructure.email import outbox_delivery
from education_system.systems.university.infrastructure.ui import record_screens as rs
from education_system.systems.university.shell.gui.email import hub_access
from education_system.systems.university.shell.gui.email.hub_dialogs import (
    LIVE_WARNING, MODE_LABELS,
)

logger = logging.getLogger(__name__)

STATUSES = ("queued", "sending", "sent", "failed", "bounced", "suppressed", "stored",
            "cancelled")


def _message_sections(msg) -> list:
    attempts = [f"{a['at']}  {a['mode']}  {a['outcome']}"
                + (f"  — {a['detail']}" if a.get("detail") else "")
                for a in msg.get("attempt_log") or []]
    return [
        ("Message", [("To", msg["to_address"]), ("User", msg.get("to_ref")),
                     ("Kind", msg["kind"]), ("Category", msg["category"]),
                     ("Status", msg["status"], "bad" if msg["status"] in ("failed", "bounced")
                      else ""),
                     ("Mode", msg.get("mode")), ("Attempts", msg["attempts"]),
                     ("Next attempt", msg.get("next_attempt_at")),
                     ("Last error", msg.get("last_error"), "warn"),
                     ("Bulk send", msg.get("bulk_id")), ("Created by", msg.get("created_by")),
                     ("Created", msg["created_at"]), ("Sent", msg.get("sent_at"))]),
        ("Delivery attempts", attempts or ["None yet."]),
        ("Body", "(removed by the retention policy)" if msg.get("body_purged")
         else msg.get("body") or ""),
    ]


class OutboxTab(rs.RecordTab):
    columns = [("id", "#", 60), ("to", "To", 200), ("subject", "Subject", 220),
               ("status", "Status", 90), ("tries", "Tries", 50), ("created", "Created", 140)]
    statuses = STATUSES
    only: tuple = ()

    def load(self, conn, search, status):
        if not self.only:
            return outbox.messages(conn, status=status, search=search)
        rows = []
        for one in self.only:
            if not status or status == one:
                rows += outbox.messages(conn, status=one, search=search)
        return sorted(rows, key=lambda r: r["message_id"], reverse=True)

    def values(self, row):
        return [row["message_id"], row["to_address"], row["subject"], row["status"],
                row["attempts"], row["created_at"]]

    def row_id(self, row):
        return row["message_id"]

    def fetch(self, conn, record_id):
        return outbox.message(conn, int(record_id))

    def render(self, record):
        self.detail.show(record["subject"], _message_sections(record))

    def actions(self, record):
        found = []
        if record["status"] in ("failed", "bounced", "cancelled"):
            found.append(("Retry", self.retry))
        if record["status"] == "queued":
            found.append(("Cancel", self.cancel))
        if record["status"] in ("sent", "failed"):
            found.append(("Record bounce", self.bounce))
        if record.get("body") and not record.get("body_purged"):
            found.append(("Preview", self.preview))
        return found

    def preview(self):
        record = self.record
        if not record:
            return
        from education_system.systems.university.shell.gui.email.email_preview import (
            open_preview,
        )
        open_preview(self, record["subject"], record["body"])

    def retry(self):
        if self.write(outbox.retry, *self.who, self.record["message_id"]) is not None:
            outbox_delivery.kick()

    def cancel(self):
        if rs.confirm(self, "Cancel this queued message?"):
            self.write(outbox.cancel, *self.who, self.record["message_id"])

    def bounce(self):
        values = rs.ask(self, "Record a bounce", [
            rs.Field("detail", "What the returned e-mail said", "multiline", required=True),
            rs.Field("hard", "Permanent (block the address)", "check")], {"hard": True})
        if values:
            self.write(outbox.record_bounce, *self.who, self.record["message_id"],
                       values["detail"], hard=values["hard"])


class FailuresTab(OutboxTab):
    statuses = ("failed", "bounced")
    only = ("failed", "bounced")


class StatusTab(ttk.Frame):
    def __init__(self, parent, screen):
        super().__init__(parent, padding=10)
        self.screen = screen
        bar = ttk.Frame(self)
        bar.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Button(bar, text="Apply mode", command=self.apply_mode).pack(side="left", padx=3)
        ttk.Button(bar, text="Deliver due messages now",
                   command=self.deliver_now).pack(side="left", padx=3)
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="right", padx=3)
        modes = ttk.LabelFrame(self, text="Delivery mode", padding=8)
        modes.pack(side="top", fill="x")
        self.mode = tk.StringVar()
        for value, label in MODE_LABELS.items():
            ttk.Radiobutton(modes, text=label, variable=self.mode, value=value).pack(anchor="w")
        self.detail = rs.Detail(self)
        self.detail.pack(fill="both", expand=True, pady=(6, 0))

    def refresh(self):
        status = outbox_delivery.status()
        summary = rs.call(self, _summary, quiet=True) or {}
        self.mode.set(status["mode"])
        warnings = []
        if status["password_in_config_file"]:
            warnings.append(("Warning", "the SMTP password is stored in plain text in the "
                                        "config file", "bad"))
        if not status["live_ready"]:
            warnings.append(("Live sending", "not ready — " + "; ".join(status["live_problems"]),
                             "warn"))
        counts = [(name, n) for name, n in sorted((summary.get("counts") or {}).items())]
        self.detail.show("E-mail delivery", [
            ("Now", [("Mode", MODE_LABELS.get(status["mode"], status["mode"])),
                     ("Sender", status["sender"]), ("SMTP server", status["smtp_server"]),
                     ("Background worker", "running" if status["worker_running"]
                      else "not running in this window"),
                     ("Sandbox folder", status["sandbox_dir"]), *warnings]),
            ("Messages by status", counts or ["No messages yet."]),
            ("Policy", [("Keep message bodies for", f"{summary.get('retention_days')} days"),
                        ("Delivery attempts", summary.get("max_attempts")),
                        ("Blocked addresses", summary.get("suppressed_addresses"))]),
        ])

    def apply_mode(self):
        mode = self.mode.get()
        if mode == outbox_delivery.delivery_mode():
            rs.info(self, "That is already the delivery mode.")
            return
        if mode == "live" and not rs.confirm(self, LIVE_WARNING.format(
                sender=outbox_delivery.status()["sender"] or "the sender")):
            return
        if rs.call(self, outbox_delivery.set_mode, *self.screen.who, mode,
                   write=True) is not None:
            outbox_delivery.kick()
            self.screen.changed()

    def deliver_now(self):
        if outbox_delivery.delivery_mode() == "inbox_only":
            rs.info(self, "The mode is in-app inbox only, so nothing is sent.")
            return

        def work():
            try:
                done = outbox_delivery.deliver_due()
            except Exception as exc:
                logger.exception("Delivery pass failed")
                ui(self, lambda err=exc: messagebox.showerror(
                    rs.TITLE, f"The delivery pass did not work: {err}", parent=self))
                return
            ui(self, lambda: (rs.info(self, f"Delivery pass: {done}"),
                              self.screen.changed()))
        start_thread(self, work, name="email-deliver-now")


def _summary(conn):
    from education_system.systems.university.application.mail import admin as email_admin
    return email_admin.summary(conn)


class DeliveryScreen:
    """``DeliveryScreen(parent, auth)``: opens nothing unless the user is
    an administrator or holds the ``email_admin`` role."""

    def __init__(self, parent, auth):
        self.auth = auth
        self.window = None
        if not hub_access.require_email_admin(auth, parent):
            return
        self.who = hub_access.user_of(auth)
        self.window = tk.Toplevel(parent)
        self.window.title("E-mail Delivery")
        width = min(1300, self.window.winfo_screenwidth() - 60)
        height = min(820, self.window.winfo_screenheight() - 100)
        self.window.geometry(f"{width}x{height}")
        self.window.minsize(900, 560)
        from education_system.systems.university.shell.gui.email import delivery_tabs
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill="both", expand=True)
        self.status = StatusTab(notebook, self)
        notebook.add(self.status, text="Status")
        self.tabs = [OutboxTab(notebook, self), FailuresTab(notebook, self)]
        notebook.add(self.tabs[0], text="Outbox")
        notebook.add(self.tabs[1], text="Failures")
        for label, cls in delivery_tabs.TABS:
            if cls.admin_only and not outbox.is_admin(self.who[1]):
                continue
            tab = cls(notebook, self)
            self.tabs.append(tab)
            notebook.add(tab, text=label)
        self.changed()

    def changed(self):
        self.status.refresh()
        for tab in self.tabs:
            tab.refresh()
